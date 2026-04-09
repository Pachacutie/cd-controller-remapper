"""PAZ in-place patcher for Crimson Desert inputmap_common.xml.

Pipeline:
  1. Backup vanilla PAZ/PAMT/PAPGT (idempotent).
  2. Repack modified XML into encrypted+compressed payload.
  3. If payload fits at entry.offset, overwrite in place.
     If payload is larger, append to PAZ and update offset.
  4. Patch PAMT: update file record + PAZ hash + PAZ size + outer hash.
  5. Rebuild PAPGT via PapgtManager.

apply_paz_patch(patched_xml, game_dir)  -> {"ok": True}
remove_paz_patch(game_dir)              -> {"ok": True, "message": ...}
"""

import os
import shutil
import struct
from pathlib import Path

from .paz_parse import parse_pamt, PazEntry
from .paz_repack import repack_entry_bytes
from .hashlittle import hashlittle, INTEGRITY_SEED, compute_pamt_hash
from .papgt_manager import PapgtManager

TARGET_FILE = "ui/inputmap_common.xml"
PAZ_FOLDER = "0012"


# ── Backup ────────────────────────────────────────────────────────────

def _backup_dir() -> Path:
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        return Path(appdata) / "cd_remap" / "backup"
    return Path.home() / ".cd_remap" / "backup"


def _create_backup(game_dir: Path, backup: Path, paz_index: int) -> None:
    """Copy vanilla PAZ/PAMT/PAPGT to backup dir. Skips if already exists."""
    paz_file = f"{PAZ_FOLDER}/{paz_index}.paz"
    for rel in (paz_file, f"{PAZ_FOLDER}/0.pamt", "meta/0.papgt"):
        dst = backup / rel
        if dst.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(game_dir / rel, dst)


# ── PAMT PAZ table offset ────────────────────────────────────────────

def _paz_table_offset(paz_index: int, paz_count: int) -> tuple[int, int]:
    """Return (hash_offset, size_offset) in the PAMT for a given PAZ index.

    PAMT PAZ table starts at offset 16. Each entry is 8 bytes (hash + size),
    with 4-byte separators between entries.
    """
    off = 16
    for i in range(paz_index):
        off += 8  # hash + size
        if i < paz_count - 1:
            off += 4  # separator
    return off, off + 4


# ── PAMT binary record update ────────────────────────────────────────

def _apply_pamt_entry_update(
    data: bytearray,
    entry: PazEntry,
    new_offset: int,
    new_comp: int,
    new_orig: int,
) -> None:
    """Patch a PAMT file-record bytearray in place.

    Finds the 20-byte pattern (node_ref, offset, comp_size, orig_size, flags)
    in the file-record section, then overwrites offset/comp_size/orig_size.

    Raises ValueError if the file record is not found.
    """
    needle = struct.pack("<IIII", entry.offset, entry.comp_size, entry.orig_size, entry.flags)
    pos = bytes(data).find(needle)
    if pos == -1:
        raise ValueError(
            f"Record not found for entry at offset={entry.offset} "
            f"comp={entry.comp_size} orig={entry.orig_size} flags={entry.flags:#010x}"
        )

    struct.pack_into("<III", data, pos, new_offset, new_comp, new_orig)


# ── Apply / Remove ───────────────────────────────────────────────────

def apply_paz_patch(patched_xml: bytes, game_dir: Path) -> dict:
    """Write patched XML back into the correct PAZ file and update PAMT + PAPGT.

    Args:
        patched_xml: modified plaintext XML bytes
        game_dir:    Crimson Desert install root

    Returns:
        {"ok": True}
    """
    game_dir = Path(game_dir)

    # Locate entry — parse_pamt resolves the correct PAZ file via paz_index
    pamt_path = str(game_dir / PAZ_FOLDER / "0.pamt")
    paz_dir = str(game_dir / PAZ_FOLDER)
    entries = parse_pamt(pamt_path, paz_dir=paz_dir)
    entry = next(e for e in entries if e.path == TARGET_FILE)

    paz_index = entry.paz_index
    paz_path = Path(entry.paz_file)

    backup = _backup_dir()
    _create_backup(game_dir, backup, paz_index)

    # Repack: allow size growth
    payload, actual_comp, actual_orig = repack_entry_bytes(
        patched_xml, entry, allow_size_change=True
    )

    # Read the correct PAZ file
    buf = bytearray(paz_path.read_bytes())

    if actual_comp <= entry.comp_size:
        # Fits in-place — overwrite at existing offset
        buf[entry.offset: entry.offset + len(payload)] = payload
        new_offset = entry.offset
        new_paz_size = None
    else:
        # Append to PAZ
        new_offset = len(buf)
        buf += payload
        new_paz_size = len(buf)

    paz_path.write_bytes(buf)
    paz_data = bytes(buf)

    # Patch PAMT — file record
    pamt_bytes = bytearray((game_dir / PAZ_FOLDER / "0.pamt").read_bytes())
    _apply_pamt_entry_update(
        pamt_bytes, entry,
        new_offset=new_offset,
        new_comp=actual_comp,
        new_orig=actual_orig,
    )

    # Read PAMT header to get paz_count
    paz_count = struct.unpack_from("<I", pamt_bytes, 4)[0]

    # Update PAZ hash and size at the correct PAZ table offset
    hash_off, size_off = _paz_table_offset(paz_index, paz_count)
    paz_hash = hashlittle(paz_data, INTEGRITY_SEED)
    struct.pack_into("<I", pamt_bytes, hash_off, paz_hash)

    if new_paz_size is not None:
        struct.pack_into("<I", pamt_bytes, size_off, new_paz_size)

    # Recompute outer hash at offset 0
    outer_hash = compute_pamt_hash(bytes(pamt_bytes))
    struct.pack_into("<I", pamt_bytes, 0, outer_hash)

    (game_dir / PAZ_FOLDER / "0.pamt").write_bytes(pamt_bytes)

    # Rebuild PAPGT
    papgt_bytes = PapgtManager(game_dir).rebuild(
        modified_pamts={PAZ_FOLDER: bytes(pamt_bytes)}
    )
    (game_dir / "meta" / "0.papgt").write_bytes(papgt_bytes)

    return {"ok": True}


def remove_paz_patch(game_dir: Path) -> dict:
    """Restore vanilla PAZ/PAMT/PAPGT from backup.

    Args:
        game_dir: Crimson Desert install root

    Returns:
        {"ok": True/False, "message": ...}
    """
    game_dir = Path(game_dir)
    backup = _backup_dir()

    if not (backup / PAZ_FOLDER / "0.pamt").exists():
        return {"ok": False, "message": "No backup found. Nothing to restore."}

    # Restore PAMT and PAPGT always
    for rel in (f"{PAZ_FOLDER}/0.pamt", "meta/0.papgt"):
        src = backup / rel
        if src.exists():
            shutil.copy2(src, game_dir / rel)

    # Restore whichever PAZ files were backed up
    paz_backup_dir = backup / PAZ_FOLDER
    for f in paz_backup_dir.glob("*.paz"):
        shutil.copy2(f, game_dir / PAZ_FOLDER / f.name)

    return {"ok": True, "message": "Vanilla PAZ restored."}

"""PAZ in-place patcher for Crimson Desert input map XMLs.

Supports patching multiple files in a single PAZ folder in one operation.

Pipeline:
  1. Backup vanilla PAZ/PAMT/PAPGT (idempotent).
  2. Repack modified XMLs into encrypted+compressed payloads.
  3. If payload fits at entry.offset, overwrite in place.
     If payload is larger, append to PAZ and update offset.
  4. Patch PAMT: update file records + PAZ hashes + sizes + outer hash.
  5. Rebuild PAPGT via PapgtManager.

apply_paz_patch(patches, game_dir)  -> {"ok": True}
remove_paz_patch(game_dir)          -> {"ok": True, "message": ...}
"""

import os
import shutil
import struct
from pathlib import Path

from .paz_parse import parse_pamt, PazEntry
from .paz_repack import repack_entry_bytes
from .hashlittle import hashlittle, INTEGRITY_SEED, compute_pamt_hash
from .papgt_manager import PapgtManager

PAZ_FOLDER = "0012"


# ── Backup ────────────────────────────────────────────────────────────

def _backup_dir() -> Path:
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        return Path(appdata) / "cd_remap" / "backup"
    return Path.home() / ".cd_remap" / "backup"


def _create_backup(game_dir: Path, backup: Path, paz_indices: set[int]) -> None:
    """Copy vanilla PAZ/PAMT/PAPGT to backup dir. Skips if already exists."""
    rels = [f"{PAZ_FOLDER}/0.pamt", "meta/0.papgt"]
    rels += [f"{PAZ_FOLDER}/{i}.paz" for i in paz_indices]
    for rel in rels:
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

def apply_paz_patch(patches: list[tuple[str, bytes]], game_dir: Path) -> dict:
    """Write patched XMLs back into PAZ files and update PAMT + PAPGT.

    Args:
        patches:  list of (target_path, modified_plaintext_xml) tuples
        game_dir: Crimson Desert install root

    Returns:
        {"ok": True}
    """
    game_dir = Path(game_dir)

    pamt_path = str(game_dir / PAZ_FOLDER / "0.pamt")
    paz_dir = str(game_dir / PAZ_FOLDER)
    all_entries = parse_pamt(pamt_path, paz_dir=paz_dir)
    entry_map = {e.path: e for e in all_entries}

    # Resolve entries for all patches
    resolved = []
    for target, xml_bytes in patches:
        entry = entry_map.get(target)
        if entry is None:
            raise FileNotFoundError(f"{target} not found in PAZ folder {PAZ_FOLDER}")
        resolved.append((target, xml_bytes, entry))

    # Backup all affected PAZ files + shared PAMT/PAPGT
    paz_indices = {entry.paz_index for _, _, entry in resolved}
    backup = _backup_dir()
    _create_backup(game_dir, backup, paz_indices)

    pamt_bytes = bytearray((game_dir / PAZ_FOLDER / "0.pamt").read_bytes())
    paz_count = struct.unpack_from("<I", pamt_bytes, 4)[0]

    # Track which PAZ files were modified (for hash update)
    modified_paz: dict[int, bytes] = {}

    for target, xml_bytes, entry in resolved:
        paz_path = Path(entry.paz_file)

        payload, actual_comp, actual_orig = repack_entry_bytes(
            xml_bytes, entry, allow_size_change=True
        )

        buf = bytearray(paz_path.read_bytes())

        if actual_comp <= entry.comp_size:
            buf[entry.offset: entry.offset + len(payload)] = payload
            new_offset = entry.offset
            new_paz_size = None
        else:
            new_offset = len(buf)
            buf += payload
            new_paz_size = len(buf)

        paz_path.write_bytes(buf)

        # Update PAMT file record
        _apply_pamt_entry_update(
            pamt_bytes, entry,
            new_offset=new_offset,
            new_comp=actual_comp,
            new_orig=actual_orig,
        )

        # Update PAZ hash and size in PAMT
        hash_off, size_off = _paz_table_offset(entry.paz_index, paz_count)
        paz_hash = hashlittle(bytes(buf), INTEGRITY_SEED)
        struct.pack_into("<I", pamt_bytes, hash_off, paz_hash)
        if new_paz_size is not None:
            struct.pack_into("<I", pamt_bytes, size_off, new_paz_size)

    # Recompute PAMT outer hash
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

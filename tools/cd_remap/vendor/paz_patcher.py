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

from cd_remap.vendor.paz_parse import parse_pamt, PazEntry
from cd_remap.vendor.paz_repack import repack_entry_bytes
from cd_remap.vendor.hashlittle import hashlittle, INTEGRITY_SEED, compute_pamt_hash
from cd_remap.vendor.papgt_manager import PapgtManager

TARGET_FILE = "ui/inputmap_common.xml"
PAZ_FOLDER = "0012"


# ── Backup ────────────────────────────────────────────────────────────

def _backup_dir() -> Path:
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        return Path(appdata) / "cd_remap" / "backup"
    return Path.home() / ".cd_remap" / "backup"


def _create_backup(game_dir: Path, backup: Path) -> None:
    """Copy vanilla PAZ/PAMT/PAPGT to backup dir. Skips if already exists."""
    for rel in (f"{PAZ_FOLDER}/0.paz", f"{PAZ_FOLDER}/0.pamt", "meta/0.papgt"):
        dst = backup / rel
        if dst.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(game_dir / rel, dst)


# ── PAMT binary record update ────────────────────────────────────────

def _apply_pamt_entry_update(
    data: bytearray,
    entry: PazEntry,
    new_offset: int,
    new_comp: int,
    new_orig: int,
    new_paz_size: int | None = None,
) -> None:
    """Patch a PAMT bytearray in place.

    Finds the 16-byte pattern (offset, comp_size, orig_size, flags) in the
    file-record section, then overwrites offset/comp_size/orig_size.
    Optionally updates PAZ size at PAMT offset 20 (taking the max of old/new).

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

    if new_paz_size is not None:
        old_size = struct.unpack_from("<I", data, 20)[0]
        struct.pack_into("<I", data, 20, max(old_size, new_paz_size))


# ── Apply / Remove ───────────────────────────────────────────────────

def apply_paz_patch(patched_xml: bytes, game_dir: Path) -> dict:
    """Write patched XML back into PAZ 0012 and update PAMT + PAPGT.

    Args:
        patched_xml: modified plaintext XML bytes
        game_dir:    Crimson Desert install root

    Returns:
        {"ok": True}
    """
    game_dir = Path(game_dir)
    backup = _backup_dir()
    _create_backup(game_dir, backup)

    # Locate entry
    pamt_path = str(game_dir / PAZ_FOLDER / "0.pamt")
    paz_dir = str(game_dir / PAZ_FOLDER)
    entries = parse_pamt(pamt_path, paz_dir=paz_dir)
    entry = next(e for e in entries if e.path == TARGET_FILE)

    # Repack: allow size growth
    payload, actual_comp, actual_orig = repack_entry_bytes(
        patched_xml, entry, allow_size_change=True
    )

    # Read PAZ
    paz_path = game_dir / PAZ_FOLDER / "0.paz"
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

    # Patch PAMT
    pamt_bytes = bytearray((game_dir / PAZ_FOLDER / "0.pamt").read_bytes())
    _apply_pamt_entry_update(
        pamt_bytes, entry,
        new_offset=new_offset,
        new_comp=actual_comp,
        new_orig=actual_orig,
        new_paz_size=new_paz_size,
    )

    # Update PAZ hash at offset 16
    paz_hash = hashlittle(paz_data, INTEGRITY_SEED)
    struct.pack_into("<I", pamt_bytes, 16, paz_hash)

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
        {"ok": True, "message": "Vanilla PAZ restored."}

    Raises:
        FileNotFoundError: if no backup exists
    """
    game_dir = Path(game_dir)
    backup = _backup_dir()
    backup_paz = backup / PAZ_FOLDER / "0.paz"
    if not backup_paz.exists():
        raise FileNotFoundError(f"No backup found at {backup}. Nothing to restore.")

    for rel in (f"{PAZ_FOLDER}/0.paz", f"{PAZ_FOLDER}/0.pamt", "meta/0.papgt"):
        shutil.copy2(backup / rel, game_dir / rel)

    return {"ok": True, "message": "Vanilla PAZ restored."}

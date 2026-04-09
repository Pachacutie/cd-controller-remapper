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
CHUNK_SIZE = 4 * 1024 * 1024  # 4 MB


def _chunked_read(path, progress_cb, phase):
    """Read file into bytearray in chunks, calling progress_cb after each."""
    path = Path(path)
    size = path.stat().st_size
    buf = bytearray(size)
    with open(path, "rb") as f:
        done = 0
        while done < size:
            chunk = f.readinto(memoryview(buf)[done:done + CHUNK_SIZE])
            if not chunk:
                break
            done += chunk
            if progress_cb:
                progress_cb(phase, done, size)
    return buf


def _chunked_write(path, buf, progress_cb, phase):
    """Write bytearray to file in chunks, calling progress_cb after each."""
    path = Path(path)
    total = len(buf)
    with open(path, "wb") as f:
        done = 0
        while done < total:
            end = min(done + CHUNK_SIZE, total)
            f.write(buf[done:end])
            done = end
            if progress_cb:
                progress_cb(phase, done, total)


def _chunked_copy(src, dst, progress_cb, phase):
    """Copy file in chunks with progress callback. Preserves metadata."""
    src, dst = Path(src), Path(dst)
    size = src.stat().st_size
    buf = bytearray(min(CHUNK_SIZE, size)) if size else bytearray()
    mv = memoryview(buf)
    with open(src, "rb") as fin, open(dst, "wb") as fout:
        done = 0
        while done < size:
            n = fin.readinto(mv)
            if not n:
                break
            fout.write(mv[:n])
            done += n
            if progress_cb:
                progress_cb(phase, done, size)
    shutil.copystat(src, dst)


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

    Searches for the 16-byte suffix (offset, comp_size, orig_size, flags)
    of a file record, then overwrites offset/comp_size/orig_size.
    Skips node_ref to avoid ambiguity — the 4-field suffix is unique enough.

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

def apply_paz_patch(patches: list[tuple[str, bytes]], game_dir: Path, *, progress_cb=None) -> dict:
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

    # Aggregate progress: each file is read + written, so total = 2x sum of file sizes
    grand_total = sum(Path(e.paz_file).stat().st_size * 2 for _, _, e in resolved)
    done_so_far = [0]  # mutable for closure

    def _aggregate_cb(phase, bytes_done, file_total):
        if progress_cb:
            progress_cb(phase, done_so_far[0] + bytes_done, grand_total)

    for target, xml_bytes, entry in resolved:
        paz_path = Path(entry.paz_file)
        paz_file_size = paz_path.stat().st_size

        payload, actual_comp, actual_orig = repack_entry_bytes(
            xml_bytes, entry, allow_size_change=True
        )

        paz_name = f"{entry.paz_index}.paz"
        buf = _chunked_read(paz_path, _aggregate_cb, f"Reading {paz_name}")
        done_so_far[0] += paz_file_size

        if actual_comp <= entry.comp_size:
            buf[entry.offset: entry.offset + len(payload)] = payload
            new_offset = entry.offset
            new_paz_size = None
        else:
            new_offset = len(buf)
            buf += payload
            new_paz_size = len(buf)

        _chunked_write(paz_path, buf, _aggregate_cb, f"Writing {paz_name}")
        done_so_far[0] += len(buf)

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

    if progress_cb:
        progress_cb("Updating indexes", grand_total, grand_total)

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


def remove_paz_patch(game_dir: Path, *, progress_cb=None) -> dict:
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

    # Collect all files to restore and compute aggregate size
    restore_files = []
    for rel in (f"{PAZ_FOLDER}/0.pamt", "meta/0.papgt"):
        src = backup / rel
        if src.exists():
            restore_files.append((src, game_dir / rel, Path(rel).name))
    paz_backup_dir = backup / PAZ_FOLDER
    for f in paz_backup_dir.glob("*.paz"):
        restore_files.append((f, game_dir / PAZ_FOLDER / f.name, f.name))

    grand_total = sum(src.stat().st_size for src, _, _ in restore_files)
    done_so_far = [0]

    def _aggregate_cb(phase, bytes_done, file_total):
        if progress_cb:
            progress_cb(phase, done_so_far[0] + bytes_done, grand_total)

    for src, dst, name in restore_files:
        _chunked_copy(src, dst, _aggregate_cb, f"Restoring {name}")
        done_so_far[0] += src.stat().st_size

    return {"ok": True, "message": "Vanilla PAZ restored."}

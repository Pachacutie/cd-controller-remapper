# In-Place PAZ Patching for inputmap_common.xml

**Date:** 2026-04-08
**Status:** Approved
**Replaces:** Overlay VFS approach (0036/ directory)

---

## Problem

The overlay VFS (`0036/`) does not work for `inputmap_common.xml`. The game either loads input maps before the overlay system initializes, or expects XML files to be ChaCha20-encrypted (overlay entries are never encrypted). The remapper's Apply button builds a valid overlay but the game ignores it.

## Solution

Patch the vanilla PAZ 0012 archive in-place using the same algorithm CDUMM's `apply_engine.py` uses. This writes encrypted + compressed data directly into the game's PAZ file, updates the PAMT index, and rebuilds the PAPGT hash registry.

## Architecture

```
extract_xml()          Read from PAZ 0012 (decrypt + decompress)
       |
apply_swaps_contextual()   Pure XML transform (unchanged)
       |
apply_paz_patch()      Compress + encrypt + write back to PAZ 0012
       |               Update PAMT + PAPGT integrity chain
       v
  Game reads patched PAZ 0012 natively
```

Undo restores vanilla PAZ + PAMT + PAPGT from backup.

---

## New Vendor Module: `paz_repack.py`

Ported from CDUMM `paz_repack.py`. Pure functions, no disk I/O.

### `repack_entry_bytes(plaintext: bytes, entry: PazEntry, allow_size_change: bool = False) -> tuple[bytes, int, int]`

Pipeline: plaintext -> LZ4 compress -> ChaCha20 encrypt -> payload

- **Compression type 2 (LZ4):**
  - `allow_size_change=False`: calls `_match_compressed_size()` to produce exactly `entry.comp_size` bytes after compression. Raises `ValueError` if content is too large to fit.
  - `allow_size_change=True`: compresses freely, returns `(payload, actual_comp_size, actual_orig_size)`.
- **Encryption:** Always applied for `.xml` entries via `encrypt(payload, entry.path)`. ChaCha20 with filename-derived key (symmetric — same function for encrypt/decrypt).
- **Returns:** `(payload_bytes, actual_comp_size, actual_orig_size)`

### `_match_compressed_size(plaintext: bytes, target_comp: int, target_orig: int) -> bytes`

Binary search to produce exactly `target_comp` bytes of LZ4 output:

1. Pad plaintext with null bytes to `target_orig`.
2. LZ4-compress and check size.
3. If too small: binary-search for printable ASCII filler (`bytes(range(33, 127))` repeated) appended before null-padding. Filler is incompressible, grows compressed output predictably.
4. If too large: attempt `_strip_whitespace_to_fit()` — collapse trailing whitespace/newlines.
5. If still too large: raise `ValueError`.

For button remapping (swapping similarly-named strings like `PAD_A` <-> `PAD_B`), compressed sizes should be nearly identical. The binary search handles minor LZ4 compression ratio variation.

---

## New Vendor Module: `paz_patcher.py`

Orchestrates the full apply/undo chain. Reads files, calls `repack_entry_bytes`, patches PAMT binary, updates PAPGT.

### `apply_paz_patch(patched_xml: bytes, game_dir: Path) -> dict`

1. **Backup** vanilla `0012/0.paz`, `0012/0.pamt`, `meta/0.papgt` to `%APPDATA%/cd_remap/backup/` (first apply only, never overwritten).
2. **Parse PAMT** to find `inputmap_common.xml` entry (offset, comp_size, orig_size, flags).
3. **Repack:** `repack_entry_bytes(patched_xml, entry, allow_size_change=True)`.
4. **Read PAZ** into `bytearray` buffer.
5. **Write payload:**
   - If `actual_comp <= entry.comp_size`: overwrite at `entry.offset`, null-pad remainder.
   - If `actual_comp > entry.comp_size`: record `new_offset = len(buf)`, append payload to buffer, record `new_paz_size = len(buf)` (after append).
6. **Write PAZ** buffer back to disk.
7. **Patch PAMT binary:**
   - Find the 20-byte file record by matching `(offset, comp_size, orig_size, flags)`.
   - Update offset, comp_size, orig_size fields.
   - If appended: update PAZ size in PAMT header table (use `max(old_size, new_paz_size)` since multiple entries may append).
   - Recompute PAZ CRC: `hashlittle(paz_data, 0xC5EDE)` -> write at PAMT PAZ table hash field.
   - Recompute PAMT outer hash: `hashlittle(pamt[12:], 0xC5EDE)` -> write at PAMT byte 0.
8. **Write PAMT** to disk.
9. **Rebuild PAPGT** via `PapgtManager.rebuild(modified_pamts={"0012": pamt_bytes})`.
10. **Write PAPGT** to disk.
11. **Return** `{"ok": True, "affected": N}`.

### `remove_paz_patch(game_dir: Path) -> dict`

1. Check backup exists at `%APPDATA%/cd_remap/backup/`.
2. Restore `0012/0.paz`, `0012/0.pamt`, `meta/0.papgt` from backup (file copy).
3. Return `{"ok": True, "message": "Vanilla PAZ restored."}`.

### PAMT Binary Patching: `_apply_pamt_entry_update(data: bytearray, entry: PazEntry, new_offset: int, new_comp: int, new_orig: int, new_paz_size: int | None)`

Directly ported from CDUMM `apply_engine.py:253-297`:

- Find the file record by searching for the 16-byte pattern `(offset, comp_size, orig_size, flags)` in the PAMT binary.
- Overwrite offset + comp_size + orig_size at the found position.
- If `new_paz_size` is not None: update the PAZ size field in the PAMT header table.

### Backup Location

`%APPDATA%/cd_remap/backup/` (platform: `Path(os.environ.get("APPDATA", "")) / "cd_remap" / "backup"`).

Contents:
```
backup/
  0012/
    0.paz      # Vanilla PAZ data
    0.pamt     # Vanilla PAMT index
  meta/
    0.papgt    # Vanilla PAPGT registry
```

---

## Changes to `remap.py`

### Replace

| Old | New |
|-----|-----|
| `from .vendor.overlay_builder import build_overlay` | `from .vendor.paz_patcher import apply_paz_patch, remove_paz_patch` |
| `apply_remap()` calls `build_overlay()` | Calls `apply_paz_patch()` |
| `_apply_patched_xml()` calls `build_overlay()` | Calls `apply_paz_patch()` |
| `remove_remap()` deletes `0036/` + restores PAPGT | Calls `remove_paz_patch()` |

### Remove

- `_read_existing_overlay()` helper
- All overlay directory logic (`0036/` creation, overlay entry merging)
- Import of `overlay_builder`
- `BACKUP_DIR` constant (moved into `paz_patcher.py`)

### Keep Unchanged

- `extract_xml()` — reads from PAZ 0012, unchanged
- `validate_swaps()` — pure validation
- `apply_swaps()` / `apply_swaps_contextual()` — pure XML transforms
- `count_affected()` — pure read
- `show_bindings()` — pure read
- `load_config()` — JSON loading
- `_detect_game_dir()` — Steam auto-detect

### Updated `_apply_patched_xml()`

```python
def _apply_patched_xml(patched_xml: bytes, game_dir: Path) -> dict:
    original_xml = extract_xml(game_dir)
    affected = sum(1 for a, b in zip(original_xml.split(b"\n"), patched_xml.split(b"\n")) if a != b)
    result = apply_paz_patch(patched_xml, game_dir)
    result["affected"] = affected
    return result
```

---

## Vendor Cleanup

- **Delete:** `vendor/overlay_builder.py`
- **Update:** `vendor/__init__.py` docstring (remove overlay references)
- **Add:** `vendor/paz_repack.py` (new)
- **Add:** `vendor/paz_patcher.py` (new)
- **Keep:** `paz_parse.py`, `paz_crypto.py`, `hashlittle.py`, `papgt_manager.py`

---

## Testing

### Synthetic Fixtures

All tests use small synthetic PAZ/PAMT files — no real game data. A fixture builder creates:
- A minimal PAMT with one folder, one node, one file record pointing at a known offset
- A small PAZ containing one encrypted + LZ4-compressed XML blob
- A matching PAPGT with one directory entry

### `test_paz_repack.py`

| Test | Verifies |
|------|----------|
| `_match_compressed_size` hits exact target | Binary search produces exactly N bytes |
| `_match_compressed_size` raises on too-large content | ValueError when content can't fit |
| `repack_entry_bytes` round-trip | repack -> decrypt -> decompress == original |
| `repack_entry_bytes` with `allow_size_change=True` | Returns correct actual sizes |

### `test_paz_patcher.py`

| Test | Verifies |
|------|----------|
| `apply_paz_patch` same-size | PAZ updated at original offset, PAMT hash recomputed |
| `apply_paz_patch` larger-than-slot | Data appended, offset updated, PAZ size updated |
| `remove_paz_patch` restores backup | All three files match vanilla originals |
| Backup idempotent | Second apply doesn't overwrite existing backup |
| `_apply_pamt_entry_update` | File record patched correctly in binary |

### `test_remap.py` (integration)

| Test | Verifies |
|------|----------|
| Full apply pipeline | extract -> swap -> patch -> re-extract -> swaps present |
| Full undo pipeline | patch -> remove -> re-extract -> matches vanilla |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Compressed size exceeds slot | Append path handles this — never fails |
| PAZ corruption | Backup created before first write. Undo restores vanilla. |
| Steam detects modification | NTFS timestamps preserved (future enhancement if needed via kernel32 API) |
| Game update changes PAZ 0012 | Backup becomes stale — `remove_paz_patch` should verify backup PAMT matches current before restoring (warn if mismatch) |
| Multiple remaps without undo | Each apply overwrites previous patch. Backup always holds vanilla. |

---

## Out of Scope

- NTFS timestamp preservation (can add later if Steam verification is an issue)
- Overlay support for other mods (sleep mod has its own repo)
- Full PAZ rebuild (append path handles size growth)
- Compression type 1 (DDS split) — not needed for XML

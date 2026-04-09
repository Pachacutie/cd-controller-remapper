# In-Place PAZ Patching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the broken overlay VFS approach with in-place PAZ 0012 patching so the controller remapper actually works in-game.

**Architecture:** Two new vendor modules (`paz_repack.py` for compression/encryption, `paz_patcher.py` for orchestrating PAZ/PAMT/PAPGT writes), wired into the existing `remap.py` in place of the overlay builder. Backup/restore for undo.

**Tech Stack:** Python 3.10+, lz4, cryptography (ChaCha20), struct (binary PAMT patching)

---

### Task 1: Vendor `paz_repack.py` — Size Matching + Repack

**Files:**
- Create: `tools/cd_remap/vendor/paz_repack.py`
- Test: `tests/test_paz_repack.py`

- [ ] **Step 1: Write failing tests for `_match_compressed_size`**

```python
# tests/test_paz_repack.py
"""Tests for PAZ repack — compression size matching and entry repacking."""
import lz4.block
import pytest


class TestMatchCompressedSize:
    def test_hits_exact_target(self):
        """Binary search produces exactly target_comp bytes of LZ4 output."""
        from cd_remap.vendor.paz_repack import _match_compressed_size

        plaintext = b"<GamePad Key=\"buttonA\" Method=\"downonce\"/>" * 20
        # Compute what the "vanilla" compressed size would be
        padded = plaintext + b"\x00" * (2048 - len(plaintext))
        target_comp = len(lz4.block.compress(padded, store_size=False))

        result = _match_compressed_size(plaintext, target_comp, 2048)
        assert len(result) == 2048
        compressed = lz4.block.compress(result, store_size=False)
        assert len(compressed) == target_comp

    def test_slightly_different_content_still_hits_target(self):
        """Modified content (different button names) still matches original compressed size."""
        from cd_remap.vendor.paz_repack import _match_compressed_size

        original = b"<GamePad Key=\"buttonA\" Method=\"downonce\"/>" * 20
        modified = b"<GamePad Key=\"buttonB\" Method=\"downonce\"/>" * 20
        padded_orig = original + b"\x00" * (2048 - len(original))
        target_comp = len(lz4.block.compress(padded_orig, store_size=False))

        result = _match_compressed_size(modified, target_comp, 2048)
        assert len(result) == 2048
        compressed = lz4.block.compress(result, store_size=False)
        assert len(compressed) == target_comp

    def test_raises_when_content_too_large(self):
        """ValueError when content can't possibly fit in target compressed size."""
        from cd_remap.vendor.paz_repack import _match_compressed_size

        # Content is already bigger than orig_size — can't pad down
        huge = b"x" * 3000
        with pytest.raises(ValueError):
            _match_compressed_size(huge, 100, 2048)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:/Games/Workshop/CD_REMAPPER/.claude/worktrees/sad-villani && python -m pytest tests/test_paz_repack.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'cd_remap.vendor.paz_repack'`

- [ ] **Step 3: Implement `_match_compressed_size` and `_pad_to_orig_size`**

```python
# tools/cd_remap/vendor/paz_repack.py
"""PAZ entry repacker — compress, encrypt, size-match.

Ported from CDUMM paz_repack.py. Pure functions, no disk I/O.

Pipeline: plaintext -> LZ4 compress -> ChaCha20 encrypt -> payload
"""
import os
import re

import lz4.block

from .paz_parse import PazEntry
from .paz_crypto import encrypt, lz4_compress


def _pad_to_orig_size(data: bytes, orig_size: int) -> bytes:
    """Pad data to exactly orig_size bytes with zero bytes."""
    if len(data) >= orig_size:
        return data[:orig_size]
    return data + b"\x00" * (orig_size - len(data))


def _match_compressed_size(
    plaintext: bytes, target_comp_size: int, target_orig_size: int
) -> bytes:
    """Adjust plaintext so it LZ4-compresses to exactly target_comp_size bytes.

    Returns adjusted plaintext (exactly target_orig_size bytes).
    Raises ValueError if size matching fails.
    """
    padded = _pad_to_orig_size(plaintext, target_orig_size)
    comp = lz4.block.compress(padded, store_size=False)
    if len(comp) == target_comp_size:
        return padded

    if len(comp) > target_comp_size:
        # Try stripping whitespace to reduce compressed size
        stripped = _strip_whitespace_to_fit(plaintext, target_comp_size, target_orig_size)
        if stripped is not None:
            return stripped
        raise ValueError(
            f"Compressed size {len(comp)} exceeds target {target_comp_size}. "
            f"Reduce file content."
        )

    # Compressed too small — binary search for filler to grow it
    filler = bytes(range(33, 127))  # printable ASCII, hard to compress
    lo, hi = 0, target_orig_size - len(plaintext)
    best = padded
    for _ in range(64):
        mid = (lo + hi) // 2
        if mid <= 0:
            break
        fill = (filler * (mid // len(filler) + 1))[:mid]
        trial = _pad_to_orig_size(plaintext + fill, target_orig_size)
        c = lz4.block.compress(trial, store_size=False)
        if len(c) == target_comp_size:
            return trial
        elif len(c) < target_comp_size:
            lo = mid + 1
            best = trial
        else:
            hi = mid - 1

    # Linear scan near the boundary
    for n in range(max(0, lo - 5), min(hi + 6, target_orig_size - len(plaintext))):
        fill = (filler * (n // len(filler) + 1))[:n] if n > 0 else b""
        trial = _pad_to_orig_size(plaintext + fill, target_orig_size)
        c = lz4.block.compress(trial, store_size=False)
        if len(c) == target_comp_size:
            return trial

    raise ValueError(
        f"Cannot match target comp_size {target_comp_size} "
        f"(best: {len(lz4.block.compress(best, store_size=False))})"
    )


def _strip_whitespace_to_fit(
    plaintext: bytes, target_comp: int, target_orig: int
) -> bytes | None:
    """Strip trailing whitespace to reduce compressed size. Returns None if impossible."""
    try:
        text = plaintext.decode("utf-8", errors="replace")
    except Exception:
        return None

    stripped = "\r\n".join(line.rstrip() for line in text.splitlines())
    candidate = stripped.encode("utf-8")
    padded = _pad_to_orig_size(candidate, target_orig)
    comp = lz4.block.compress(padded, store_size=False)
    if len(comp) <= target_comp:
        return padded

    stripped = re.sub(r"[ \t]+", " ", stripped)
    stripped = re.sub(r"\n{3,}", "\n\n", stripped)
    candidate = stripped.encode("utf-8")
    padded = _pad_to_orig_size(candidate, target_orig)
    comp = lz4.block.compress(padded, store_size=False)
    if len(comp) <= target_comp:
        return padded

    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd D:/Games/Workshop/CD_REMAPPER/.claude/worktrees/sad-villani && python -m pytest tests/test_paz_repack.py::TestMatchCompressedSize -v`
Expected: 3 PASSED

- [ ] **Step 5: Write failing tests for `repack_entry_bytes`**

Add to `tests/test_paz_repack.py`:

```python
class TestRepackEntryBytes:
    def _make_entry(self, plaintext: bytes, orig_size: int = 2048) -> "PazEntry":
        """Create a PazEntry matching what vanilla PAZ would have for this content."""
        from cd_remap.vendor.paz_parse import PazEntry
        from cd_remap.vendor.paz_crypto import encrypt

        padded = plaintext + b"\x00" * (orig_size - len(plaintext))
        compressed = lz4.block.compress(padded, store_size=False)
        return PazEntry(
            path="ui/inputmap_common.xml",
            paz_file="",
            offset=0,
            comp_size=len(compressed),
            orig_size=orig_size,
            flags=0x00020000,  # compression_type=2 (LZ4)
            paz_index=0,
        )

    def test_roundtrip_same_content(self):
        """Repack then decrypt+decompress yields original padded content."""
        from cd_remap.vendor.paz_repack import repack_entry_bytes
        from cd_remap.vendor.paz_crypto import decrypt, lz4_decompress

        plaintext = b"<GamePad Key=\"buttonA\" Method=\"downonce\"/>" * 20
        entry = self._make_entry(plaintext)

        payload, comp_size, orig_size = repack_entry_bytes(plaintext, entry)
        assert comp_size == entry.comp_size
        assert orig_size == entry.orig_size

        # Reverse: decrypt -> decompress -> check content
        decrypted = decrypt(payload[:comp_size], entry.path)
        decompressed = lz4_decompress(decrypted, orig_size)
        assert decompressed[:len(plaintext)] == plaintext

    def test_roundtrip_modified_content(self):
        """Modified content (button swap) round-trips correctly."""
        from cd_remap.vendor.paz_repack import repack_entry_bytes
        from cd_remap.vendor.paz_crypto import decrypt, lz4_decompress

        original = b"<GamePad Key=\"buttonA\" Method=\"downonce\"/>" * 20
        modified = b"<GamePad Key=\"buttonB\" Method=\"downonce\"/>" * 20
        entry = self._make_entry(original)

        payload, comp_size, orig_size = repack_entry_bytes(modified, entry)
        assert comp_size == entry.comp_size  # same-size match

        decrypted = decrypt(payload[:comp_size], entry.path)
        decompressed = lz4_decompress(decrypted, orig_size)
        assert b"buttonB" in decompressed
        assert b"buttonA" not in decompressed[:len(modified)]

    def test_allow_size_change_returns_actual_sizes(self):
        """With allow_size_change=True, returns actual compressed size."""
        from cd_remap.vendor.paz_repack import repack_entry_bytes
        from cd_remap.vendor.paz_crypto import decrypt, lz4_decompress

        plaintext = b"<GamePad Key=\"buttonA\" Method=\"downonce\"/>" * 20
        entry = self._make_entry(plaintext)

        payload, actual_comp, actual_orig = repack_entry_bytes(
            plaintext, entry, allow_size_change=True
        )
        assert actual_orig == len(plaintext)
        # Payload should be decryptable and decompressible
        decrypted = decrypt(payload[:actual_comp], entry.path)
        decompressed = lz4_decompress(decrypted, actual_orig)
        assert decompressed == plaintext
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `cd D:/Games/Workshop/CD_REMAPPER/.claude/worktrees/sad-villani && python -m pytest tests/test_paz_repack.py::TestRepackEntryBytes -v`
Expected: FAIL — `ImportError: cannot import name 'repack_entry_bytes'`

- [ ] **Step 7: Implement `repack_entry_bytes`**

Add to `tools/cd_remap/vendor/paz_repack.py`:

```python
def repack_entry_bytes(
    plaintext: bytes, entry: PazEntry, allow_size_change: bool = False
) -> tuple[bytes, int, int]:
    """Repack modified content into encrypted+compressed payload.

    Args:
        plaintext: decompressed file content
        entry: PazEntry describing the original file slot
        allow_size_change: if True, compress freely and return actual sizes.
            Caller must update PAMT if sizes differ.

    Returns:
        (payload_bytes, actual_comp_size, actual_orig_size)
    """
    basename = os.path.basename(entry.path)
    is_compressed = entry.compressed and entry.compression_type == 2
    actual_comp_size = entry.comp_size
    actual_orig_size = entry.orig_size

    if is_compressed:
        if allow_size_change:
            actual_orig_size = len(plaintext)
            compressed = lz4.block.compress(plaintext, store_size=False)
            actual_comp_size = len(compressed)
            if actual_comp_size <= entry.comp_size:
                # Fits — pad to fill slot
                payload = compressed + b"\x00" * (entry.comp_size - actual_comp_size)
            else:
                # Larger — caller must append to PAZ
                payload = compressed
        else:
            adjusted = _match_compressed_size(plaintext, entry.comp_size, entry.orig_size)
            compressed = lz4.block.compress(adjusted, store_size=False)
            assert len(compressed) == entry.comp_size, (
                f"Size mismatch: {len(compressed)} != {entry.comp_size}"
            )
            payload = compressed
    else:
        if allow_size_change:
            actual_comp_size = len(plaintext)
            actual_orig_size = len(plaintext)
            if len(plaintext) <= entry.comp_size:
                payload = plaintext + b"\x00" * (entry.comp_size - len(plaintext))
            else:
                payload = plaintext
        elif len(plaintext) > entry.comp_size:
            raise ValueError(
                f"Modified file ({len(plaintext)} bytes) exceeds budget "
                f"({entry.comp_size} bytes)"
            )
        else:
            payload = plaintext + b"\x00" * (entry.comp_size - len(plaintext))

    if entry.encrypted:
        payload = encrypt(payload, basename)

    return payload, actual_comp_size, actual_orig_size
```

- [ ] **Step 8: Run all paz_repack tests**

Run: `cd D:/Games/Workshop/CD_REMAPPER/.claude/worktrees/sad-villani && python -m pytest tests/test_paz_repack.py -v`
Expected: 6 PASSED

- [ ] **Step 9: Commit**

```bash
git add tools/cd_remap/vendor/paz_repack.py tests/test_paz_repack.py
git commit -m "feat: vendor paz_repack — LZ4 size-matching and entry repacking"
```

---

### Task 2: PAMT Binary Fixture Builder

**Files:**
- Create: `tests/fixtures.py`

We need synthetic PAZ/PAMT/PAPGT files for testing the patcher. This shared fixture builder creates minimal valid binaries that the patcher tests can use.

- [ ] **Step 1: Write the fixture builder**

```python
# tests/fixtures.py
"""Synthetic PAZ/PAMT/PAPGT fixture builders for testing.

Creates minimal valid binary files matching the Crimson Desert archive format.
No real game data needed.
"""
import struct

import lz4.block

from cd_remap.vendor.paz_crypto import encrypt
from cd_remap.vendor.hashlittle import hashlittle, INTEGRITY_SEED


def build_test_paz_pamt_papgt(
    plaintext: bytes,
    entry_path: str = "ui/inputmap_common.xml",
    paz_dir_name: str = "0012",
) -> tuple[bytes, bytes, bytes, dict]:
    """Build a minimal PAZ + PAMT + PAPGT for one encrypted LZ4 XML file.

    Returns (paz_bytes, pamt_bytes, papgt_bytes, entry_info) where entry_info
    has keys: offset, comp_size, orig_size, flags.
    """
    # Compress and encrypt
    compressed = lz4.block.compress(plaintext, store_size=False)
    encrypted = encrypt(compressed, entry_path)

    comp_size = len(compressed)
    orig_size = len(plaintext)
    offset = 0
    flags = 0x00020000  # compression_type=2 (LZ4), paz_index=0

    paz_bytes = encrypted  # single entry, no alignment needed

    # Build PAMT
    pamt = _build_minimal_pamt(
        paz_bytes, entry_path, offset, comp_size, orig_size, flags
    )

    # Build PAPGT
    papgt = _build_minimal_papgt(pamt, paz_dir_name)

    entry_info = {
        "offset": offset,
        "comp_size": comp_size,
        "orig_size": orig_size,
        "flags": flags,
    }
    return paz_bytes, pamt, papgt, entry_info


def _build_minimal_pamt(
    paz_data: bytes,
    entry_path: str,
    offset: int,
    comp_size: int,
    orig_size: int,
    flags: int,
) -> bytes:
    """Build a minimal PAMT with one folder and one file entry."""
    # Split path into folder + filename
    parts = entry_path.rsplit("/", 1)
    folder_name = parts[0] if len(parts) > 1 else ""
    file_name = parts[-1]

    buf = bytearray()

    # Header placeholder (will fill hash at end)
    buf += struct.pack("<I", 0)           # [0:4] outer hash placeholder
    buf += struct.pack("<I", 1)           # [4:8] paz_count = 1
    buf += struct.pack("<I", 0x610E0232)  # [8:12] magic constant
    buf += struct.pack("<I", 0)           # [12:16] zero

    # PAZ table: one entry (hash + size)
    paz_hash = hashlittle(paz_data, INTEGRITY_SEED)
    buf += struct.pack("<I", paz_hash)
    buf += struct.pack("<I", len(paz_data))

    # Folder section: one root folder
    folder_bytes = bytearray()
    folder_bytes += struct.pack("<I", 0xFFFFFFFF)  # root (no parent)
    folder_name_bytes = folder_name.encode("utf-8")
    folder_bytes += struct.pack("B", len(folder_name_bytes))
    folder_bytes += folder_name_bytes
    buf += struct.pack("<I", len(folder_bytes))
    folder_section_start = len(buf)
    buf += folder_bytes

    # Node section: one leaf node (the filename)
    node_bytes = bytearray()
    node_bytes += struct.pack("<I", 0xFFFFFFFF)  # no parent
    file_name_bytes = file_name.encode("utf-8")
    node_bytes += struct.pack("B", len(file_name_bytes))
    node_bytes += file_name_bytes
    buf += struct.pack("<I", len(node_bytes))
    node_section_start = len(buf)
    buf += node_bytes

    # Folder records: one entry
    path_hash = hashlittle(folder_name.encode("utf-8"), INTEGRITY_SEED)
    folder_ref = 0  # offset into folder section
    buf += struct.pack("<I", 1)  # folder count
    buf += struct.pack("<IIII", path_hash, folder_ref, 0, 1)  # file_index=0, file_count=1

    # File records: one entry
    node_ref = 0  # offset into node section
    buf += struct.pack("<I", 1)  # file count
    buf += struct.pack("<IIIII", node_ref, offset, comp_size, orig_size, flags)

    # Compute and write outer hash
    outer_hash = hashlittle(bytes(buf[12:]), INTEGRITY_SEED)
    struct.pack_into("<I", buf, 0, outer_hash)

    return bytes(buf)


def _build_minimal_papgt(pamt_data: bytes, dir_name: str) -> bytes:
    """Build a minimal PAPGT with one directory entry."""
    buf = bytearray()

    # Header
    buf += struct.pack("<I", 0)           # [0:4] metadata (preserved)
    buf += struct.pack("<I", 0)           # [4:8] hash placeholder
    buf += struct.pack("<I", 1)           # [8:12] metadata (entry count in byte 8)

    # One entry
    dir_flags = 0x003FFF00
    name_offset = 0
    pamt_hash = hashlittle(pamt_data[12:], INTEGRITY_SEED)
    buf += struct.pack("<III", dir_flags, name_offset, pamt_hash)

    # String table
    string_table = dir_name.encode("ascii") + b"\x00"
    buf += struct.pack("<I", len(string_table))
    buf += string_table

    # Compute and write file hash
    file_hash = hashlittle(bytes(buf[12:]), INTEGRITY_SEED)
    struct.pack_into("<I", buf, 4, file_hash)

    return bytes(buf)
```

- [ ] **Step 2: Commit**

```bash
git add tests/fixtures.py
git commit -m "test: synthetic PAZ/PAMT/PAPGT fixture builder"
```

---

### Task 3: Vendor `paz_patcher.py` — PAMT Patching

**Files:**
- Create: `tools/cd_remap/vendor/paz_patcher.py`
- Test: `tests/test_paz_patcher.py`

- [ ] **Step 1: Write failing test for `_apply_pamt_entry_update`**

```python
# tests/test_paz_patcher.py
"""Tests for PAZ patcher — in-place PAZ modification with PAMT/PAPGT updates."""
import struct
import pytest

from fixtures import build_test_paz_pamt_papgt


SAMPLE_XML = b'<Input Name="Attack"><GamePad Key="buttonA" Method="downonce"/></Input>' * 30


class TestApplyPamtEntryUpdate:
    def test_updates_file_record(self):
        """File record offset and comp_size updated in PAMT binary."""
        from cd_remap.vendor.paz_patcher import _apply_pamt_entry_update
        from cd_remap.vendor.paz_parse import PazEntry

        _, pamt, _, info = build_test_paz_pamt_papgt(SAMPLE_XML)
        data = bytearray(pamt)

        entry = PazEntry(
            path="ui/inputmap_common.xml", paz_file="", paz_index=0,
            offset=info["offset"], comp_size=info["comp_size"],
            orig_size=info["orig_size"], flags=info["flags"],
        )

        _apply_pamt_entry_update(
            data, entry, new_offset=9999, new_comp=500, new_orig=2000,
        )

        # Find the file record and verify it was updated
        search = struct.pack("<I", 9999)  # new offset
        pos = bytes(data).find(search)
        assert pos >= 0
        new_comp_val = struct.unpack_from("<I", data, pos + 4)[0]
        assert new_comp_val == 500

    def test_updates_paz_size_in_header(self):
        """PAZ size in PAMT header table updated when entry appended."""
        from cd_remap.vendor.paz_patcher import _apply_pamt_entry_update
        from cd_remap.vendor.paz_parse import PazEntry

        _, pamt, _, info = build_test_paz_pamt_papgt(SAMPLE_XML)
        data = bytearray(pamt)

        entry = PazEntry(
            path="ui/inputmap_common.xml", paz_file="", paz_index=0,
            offset=info["offset"], comp_size=info["comp_size"],
            orig_size=info["orig_size"], flags=info["flags"],
        )

        _apply_pamt_entry_update(
            data, entry, new_offset=9999, new_comp=500,
            new_orig=2000, new_paz_size=12000,
        )

        # PAZ size is at offset 20 (after header 16 bytes + 4 byte hash)
        paz_size = struct.unpack_from("<I", data, 20)[0]
        assert paz_size == 12000
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:/Games/Workshop/CD_REMAPPER/.claude/worktrees/sad-villani && python -m pytest tests/test_paz_patcher.py::TestApplyPamtEntryUpdate -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `_apply_pamt_entry_update`**

```python
# tools/cd_remap/vendor/paz_patcher.py
"""In-place PAZ patcher — modify vanilla archives directly.

Orchestrates: repack entry -> write PAZ -> patch PAMT -> rebuild PAPGT.
"""
import logging
import os
import shutil
import struct
from pathlib import Path

from .hashlittle import hashlittle, INTEGRITY_SEED, compute_pamt_hash
from .papgt_manager import PapgtManager
from .paz_crypto import encrypt, decrypt, lz4_compress, lz4_decompress
from .paz_parse import PazEntry, parse_pamt
from .paz_repack import repack_entry_bytes

logger = logging.getLogger(__name__)

TARGET_FILE = "ui/inputmap_common.xml"
PAZ_FOLDER = "0012"


def _backup_dir() -> Path:
    """Get backup directory: %APPDATA%/cd_remap/backup/."""
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        return Path(appdata) / "cd_remap" / "backup"
    return Path.home() / ".cd_remap" / "backup"


def _apply_pamt_entry_update(
    data: bytearray,
    entry: PazEntry,
    new_offset: int,
    new_comp: int,
    new_orig: int,
    new_paz_size: int | None = None,
) -> None:
    """Update a single file record in a PAMT binary buffer.

    Finds the record by matching (offset, comp_size, orig_size, flags),
    then updates offset, comp_size, and orig_size. Optionally updates
    PAZ size in the header table.
    """
    # Update PAZ size table if entry was appended
    if new_paz_size is not None:
        paz_count = struct.unpack_from("<I", data, 4)[0]
        paz_index = entry.paz_index
        if paz_index < paz_count:
            # Navigate to the correct PAZ table entry
            table_off = 16  # after 16-byte header
            for i in range(paz_index):
                table_off += 8  # hash + size
                if i < paz_count - 1:
                    table_off += 4  # separator
            size_off = table_off + 4  # skip hash, point to size field
            old_size = struct.unpack_from("<I", data, size_off)[0]
            final_size = max(old_size, new_paz_size)
            struct.pack_into("<I", data, size_off, final_size)

    # Find the file record by matching (offset, comp_size, orig_size, flags)
    search = struct.pack("<IIII", entry.offset, entry.comp_size,
                         entry.orig_size, entry.flags)
    pos = data.find(search)
    if pos < 4:  # need at least 4 bytes for node_ref before the match
        raise ValueError(
            f"Could not find PAMT record for {entry.path} "
            f"(offset=0x{entry.offset:X}, comp={entry.comp_size})"
        )
    # The match starts at offset field; node_ref is 4 bytes before
    struct.pack_into("<I", data, pos, new_offset)
    struct.pack_into("<I", data, pos + 4, new_comp)
    struct.pack_into("<I", data, pos + 8, new_orig)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd D:/Games/Workshop/CD_REMAPPER/.claude/worktrees/sad-villani && python -m pytest tests/test_paz_patcher.py::TestApplyPamtEntryUpdate -v`
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add tools/cd_remap/vendor/paz_patcher.py tests/test_paz_patcher.py
git commit -m "feat: PAMT binary record patching"
```

---

### Task 4: `apply_paz_patch` and `remove_paz_patch`

**Files:**
- Modify: `tools/cd_remap/vendor/paz_patcher.py`
- Test: `tests/test_paz_patcher.py`

- [ ] **Step 1: Write failing tests for apply and remove**

Add to `tests/test_paz_patcher.py`:

```python
class TestApplyPazPatch:
    def _setup_game_dir(self, tmp_path):
        """Create a minimal game directory with PAZ 0012 + PAPGT."""
        game_dir = tmp_path / "game"
        paz_dir = game_dir / PAZ_FOLDER
        paz_dir.mkdir(parents=True)
        meta_dir = game_dir / "meta"
        meta_dir.mkdir()

        original_xml = SAMPLE_XML
        paz_bytes, pamt_bytes, papgt_bytes, info = build_test_paz_pamt_papgt(
            original_xml
        )
        (paz_dir / "0.paz").write_bytes(paz_bytes)
        (paz_dir / "0.pamt").write_bytes(pamt_bytes)
        (meta_dir / "0.papgt").write_bytes(papgt_bytes)
        return game_dir, original_xml, info

    def test_apply_same_size(self, tmp_path, monkeypatch):
        """Apply patch where compressed size fits in original slot."""
        from cd_remap.vendor import paz_patcher
        monkeypatch.setattr(paz_patcher, "_backup_dir", lambda: tmp_path / "backup")

        game_dir, original_xml, _ = self._setup_game_dir(tmp_path)
        modified = original_xml.replace(b"buttonA", b"buttonB")

        result = apply_paz_patch(modified, game_dir)
        assert result["ok"]

        # Verify: extract the patched XML and check buttonB is there
        entries = parse_pamt(str(game_dir / PAZ_FOLDER / "0.pamt"),
                            str(game_dir / PAZ_FOLDER))
        entry = next(e for e in entries if e.path == TARGET_FILE)
        with open(entry.paz_file, "rb") as f:
            f.seek(entry.offset)
            raw = f.read(entry.comp_size)
        decrypted = decrypt(raw, entry.path)
        decompressed = lz4_decompress(decrypted, entry.orig_size)
        assert b"buttonB" in decompressed

    def test_backup_created(self, tmp_path, monkeypatch):
        """Backup files created on first apply."""
        from cd_remap.vendor import paz_patcher
        backup = tmp_path / "backup"
        monkeypatch.setattr(paz_patcher, "_backup_dir", lambda: backup)

        game_dir, original_xml, _ = self._setup_game_dir(tmp_path)
        modified = original_xml.replace(b"buttonA", b"buttonB")

        apply_paz_patch(modified, game_dir)

        assert (backup / PAZ_FOLDER / "0.paz").exists()
        assert (backup / PAZ_FOLDER / "0.pamt").exists()
        assert (backup / "meta" / "0.papgt").exists()

    def test_backup_not_overwritten(self, tmp_path, monkeypatch):
        """Second apply does not overwrite existing backup."""
        from cd_remap.vendor import paz_patcher
        backup = tmp_path / "backup"
        monkeypatch.setattr(paz_patcher, "_backup_dir", lambda: backup)

        game_dir, original_xml, _ = self._setup_game_dir(tmp_path)
        modified1 = original_xml.replace(b"buttonA", b"buttonB")
        apply_paz_patch(modified1, game_dir)

        # Save backup content
        backup_paz = (backup / PAZ_FOLDER / "0.paz").read_bytes()

        # Apply again with different content
        modified2 = original_xml.replace(b"buttonA", b"buttonX")
        apply_paz_patch(modified2, game_dir)

        # Backup should still be the original
        assert (backup / PAZ_FOLDER / "0.paz").read_bytes() == backup_paz


class TestRemovePazPatch:
    def test_restores_vanilla(self, tmp_path, monkeypatch):
        """Remove restores vanilla PAZ + PAMT + PAPGT from backup."""
        from cd_remap.vendor import paz_patcher
        backup = tmp_path / "backup"
        monkeypatch.setattr(paz_patcher, "_backup_dir", lambda: backup)

        game_dir = tmp_path / "game"
        paz_dir = game_dir / PAZ_FOLDER
        paz_dir.mkdir(parents=True)
        meta_dir = game_dir / "meta"
        meta_dir.mkdir()

        original_xml = SAMPLE_XML
        paz_bytes, pamt_bytes, papgt_bytes, _ = build_test_paz_pamt_papgt(original_xml)
        (paz_dir / "0.paz").write_bytes(paz_bytes)
        (paz_dir / "0.pamt").write_bytes(pamt_bytes)
        (meta_dir / "0.papgt").write_bytes(papgt_bytes)

        # Apply a patch
        modified = original_xml.replace(b"buttonA", b"buttonB")
        apply_paz_patch(modified, game_dir)

        # Verify it changed
        assert (paz_dir / "0.paz").read_bytes() != paz_bytes

        # Remove
        result = remove_paz_patch(game_dir)
        assert result["ok"]

        # Verify vanilla restored
        assert (paz_dir / "0.paz").read_bytes() == paz_bytes
        assert (paz_dir / "0.pamt").read_bytes() == pamt_bytes
        assert (meta_dir / "0.papgt").read_bytes() == papgt_bytes
```

Also add these imports at the top of `test_paz_patcher.py`:

```python
from cd_remap.vendor.paz_patcher import apply_paz_patch, remove_paz_patch, PAZ_FOLDER, TARGET_FILE
from cd_remap.vendor.paz_parse import parse_pamt
from cd_remap.vendor.paz_crypto import decrypt, lz4_decompress
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:/Games/Workshop/CD_REMAPPER/.claude/worktrees/sad-villani && python -m pytest tests/test_paz_patcher.py::TestApplyPazPatch -v`
Expected: FAIL — `ImportError: cannot import name 'apply_paz_patch'`

- [ ] **Step 3: Implement `apply_paz_patch` and `remove_paz_patch`**

Add to `tools/cd_remap/vendor/paz_patcher.py`:

```python
def apply_paz_patch(patched_xml: bytes, game_dir: Path) -> dict:
    """Patch inputmap_common.xml directly into PAZ 0012.

    1. Backup vanilla files (first time only)
    2. Repack XML (compress + encrypt)
    3. Write to PAZ (in-place or append)
    4. Update PAMT (file record, PAZ CRC, outer hash)
    5. Rebuild PAPGT

    Returns: {"ok": True/False, ...}
    """
    paz_dir = game_dir / PAZ_FOLDER
    pamt_path = paz_dir / "0.pamt"
    papgt_path = game_dir / "meta" / "0.papgt"

    if not pamt_path.exists():
        return {"ok": False, "error": f"PAMT not found: {pamt_path}"}

    # Step 1: Backup
    backup = _backup_dir()
    _create_backup(game_dir, backup)

    # Step 2: Find entry and repack
    entries = parse_pamt(str(pamt_path), str(paz_dir))
    entry = next((e for e in entries if e.path == TARGET_FILE), None)
    if entry is None:
        return {"ok": False, "error": f"{TARGET_FILE} not found in PAMT"}

    payload, actual_comp, actual_orig = repack_entry_bytes(
        patched_xml, entry, allow_size_change=True
    )

    # Step 3: Write to PAZ
    paz_path = Path(entry.paz_file)
    paz_buf = bytearray(paz_path.read_bytes())

    new_offset = entry.offset
    new_paz_size = None

    if actual_comp > entry.comp_size:
        # Doesn't fit — append to end
        new_offset = len(paz_buf)
        paz_buf.extend(payload)
        new_paz_size = len(paz_buf)
    else:
        # Fits in original slot
        paz_buf[entry.offset : entry.offset + len(payload)] = payload

    paz_path.write_bytes(bytes(paz_buf))

    # Step 4: Patch PAMT
    pamt_buf = bytearray(pamt_path.read_bytes())

    _apply_pamt_entry_update(
        pamt_buf, entry,
        new_offset=new_offset,
        new_comp=actual_comp,
        new_orig=actual_orig,
        new_paz_size=new_paz_size,
    )

    # Update PAZ CRC in PAMT header
    paz_hash = hashlittle(bytes(paz_buf), INTEGRITY_SEED)
    struct.pack_into("<I", pamt_buf, 16, paz_hash)  # PAZ hash at offset 16

    # Update PAZ size in header (even for same-size, ensure it's correct)
    struct.pack_into("<I", pamt_buf, 20, len(paz_buf))

    # Recompute PAMT outer hash
    outer_hash = compute_pamt_hash(bytes(pamt_buf))
    struct.pack_into("<I", pamt_buf, 0, outer_hash)

    pamt_bytes = bytes(pamt_buf)
    pamt_path.write_bytes(pamt_bytes)

    # Step 5: Rebuild PAPGT
    papgt_mgr = PapgtManager(game_dir)
    papgt_bytes = papgt_mgr.rebuild(modified_pamts={PAZ_FOLDER: pamt_bytes})
    papgt_path.write_bytes(papgt_bytes)

    return {"ok": True}


def remove_paz_patch(game_dir: Path) -> dict:
    """Restore vanilla PAZ 0012 + PAMT + PAPGT from backup."""
    backup = _backup_dir()

    backup_paz = backup / PAZ_FOLDER / "0.paz"
    backup_pamt = backup / PAZ_FOLDER / "0.pamt"
    backup_papgt = backup / "meta" / "0.papgt"

    if not backup_paz.exists():
        return {"ok": False, "error": "No backup found. Nothing to restore."}

    paz_dir = game_dir / PAZ_FOLDER
    shutil.copy2(backup_paz, paz_dir / "0.paz")
    shutil.copy2(backup_pamt, paz_dir / "0.pamt")
    shutil.copy2(backup_papgt, game_dir / "meta" / "0.papgt")

    return {"ok": True, "message": "Vanilla PAZ restored."}


def _create_backup(game_dir: Path, backup: Path) -> None:
    """Backup vanilla PAZ + PAMT + PAPGT. Only on first call (never overwrites)."""
    paz_backup = backup / PAZ_FOLDER / "0.paz"
    if paz_backup.exists():
        return  # already backed up

    paz_dir = game_dir / PAZ_FOLDER

    (backup / PAZ_FOLDER).mkdir(parents=True, exist_ok=True)
    (backup / "meta").mkdir(parents=True, exist_ok=True)

    shutil.copy2(paz_dir / "0.paz", backup / PAZ_FOLDER / "0.paz")
    shutil.copy2(paz_dir / "0.pamt", backup / PAZ_FOLDER / "0.pamt")
    shutil.copy2(game_dir / "meta" / "0.papgt", backup / "meta" / "0.papgt")
```

- [ ] **Step 4: Run all patcher tests**

Run: `cd D:/Games/Workshop/CD_REMAPPER/.claude/worktrees/sad-villani && python -m pytest tests/test_paz_patcher.py -v`
Expected: 5 PASSED (2 PAMT update + 3 apply/backup + 1 remove — total depends on parametrization, but all should pass)

- [ ] **Step 5: Commit**

```bash
git add tools/cd_remap/vendor/paz_patcher.py tests/test_paz_patcher.py
git commit -m "feat: apply_paz_patch and remove_paz_patch with backup/restore"
```

---

### Task 5: Wire into `remap.py` + Remove Overlay Code

**Files:**
- Modify: `tools/cd_remap/remap.py`
- Delete: `tools/cd_remap/vendor/overlay_builder.py`
- Modify: `tools/cd_remap/vendor/__init__.py`
- Modify: `tests/test_remap.py`

- [ ] **Step 1: Write failing integration test**

Add to `tests/test_remap.py`, replacing the existing `TestIntegration` class:

```python
class TestPazPatchIntegration:
    """Integration test using synthetic game directory."""

    def _setup_game_dir(self, tmp_path):
        from fixtures import build_test_paz_pamt_papgt
        game_dir = tmp_path / "game"
        paz_dir = game_dir / "0012"
        paz_dir.mkdir(parents=True)
        meta_dir = game_dir / "meta"
        meta_dir.mkdir()

        xml = b'<Input Name="Attack"><GamePad Key="buttonA" Method="downonce"/></Input>\n' * 30
        paz_bytes, pamt_bytes, papgt_bytes, _ = build_test_paz_pamt_papgt(xml)
        (paz_dir / "0.paz").write_bytes(paz_bytes)
        (paz_dir / "0.pamt").write_bytes(pamt_bytes)
        (meta_dir / "0.papgt").write_bytes(papgt_bytes)
        return game_dir, xml

    def test_apply_and_extract(self, tmp_path, monkeypatch):
        """Full pipeline: extract -> swap -> patch -> re-extract -> verify."""
        from cd_remap.remap import extract_xml, _apply_patched_xml, apply_swaps
        from cd_remap.vendor import paz_patcher
        monkeypatch.setattr(paz_patcher, "_backup_dir", lambda: tmp_path / "backup")

        game_dir, original_xml = self._setup_game_dir(tmp_path)
        xml = extract_xml(game_dir)
        assert b"buttonA" in xml

        patched = apply_swaps(xml, {"buttonA": "buttonB", "buttonB": "buttonA"})
        result = _apply_patched_xml(patched, game_dir)
        assert result["ok"]

        # Re-extract and verify
        xml2 = extract_xml(game_dir)
        assert b"buttonB" in xml2

    def test_undo_restores_vanilla(self, tmp_path, monkeypatch):
        """Patch -> undo -> extract shows vanilla content."""
        from cd_remap.remap import extract_xml, _apply_patched_xml, apply_swaps, remove_remap
        from cd_remap.vendor import paz_patcher
        monkeypatch.setattr(paz_patcher, "_backup_dir", lambda: tmp_path / "backup")

        game_dir, original_xml = self._setup_game_dir(tmp_path)
        xml = extract_xml(game_dir)
        patched = apply_swaps(xml, {"buttonA": "buttonB", "buttonB": "buttonA"})
        _apply_patched_xml(patched, game_dir)

        result = remove_remap(game_dir)
        assert result["ok"]

        xml3 = extract_xml(game_dir)
        assert b"buttonA" in xml3
        assert xml3 == original_xml
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:/Games/Workshop/CD_REMAPPER/.claude/worktrees/sad-villani && python -m pytest tests/test_remap.py::TestPazPatchIntegration -v`
Expected: FAIL — `_apply_patched_xml` still uses overlay builder

- [ ] **Step 3: Rewrite `remap.py` — replace overlay with PAZ patcher**

Replace the overlay imports and functions in `tools/cd_remap/remap.py`:

1. Remove import of `overlay_builder` and `build_overlay`
2. Add import: `from .vendor.paz_patcher import apply_paz_patch, remove_paz_patch`
3. Remove `BACKUP_DIR` constant
4. Replace `apply_remap()` body to use `apply_paz_patch()`
5. Replace `_apply_patched_xml()` body to use `apply_paz_patch()`
6. Replace `remove_remap()` body to use `remove_paz_patch()`
7. Delete `_read_existing_overlay()` function

Updated `remap.py` imports:

```python
from .vendor.paz_parse import parse_pamt
from .vendor.paz_crypto import decrypt, lz4_decompress
from .vendor.paz_patcher import apply_paz_patch, remove_paz_patch
```

Updated `apply_remap()`:

```python
def apply_remap(
    swaps: dict[str, str],
    game_dir: Path = DEFAULT_GAME_DIR,
    dry_run: bool = False,
) -> dict:
    """Extract XML, apply swaps, patch PAZ. Returns summary dict."""
    errors = validate_swaps(swaps)
    if errors:
        return {"ok": False, "errors": errors}

    xml = extract_xml(game_dir)
    affected = count_affected(xml, swaps)
    patched = apply_swaps(xml, swaps)

    if dry_run:
        return {"ok": True, "affected": affected, "dry_run": True}

    result = apply_paz_patch(patched, game_dir)
    result["affected"] = affected
    return result
```

Updated `_apply_patched_xml()`:

```python
def _apply_patched_xml(
    patched_xml: bytes,
    game_dir: Path = DEFAULT_GAME_DIR,
) -> dict:
    """Patch pre-modified XML into PAZ. Used by GUI for context-aware apply."""
    original_xml = extract_xml(game_dir)
    affected = sum(1 for a, b in zip(original_xml.split(b"\n"), patched_xml.split(b"\n")) if a != b)
    result = apply_paz_patch(patched_xml, game_dir)
    result["affected"] = affected
    return result
```

Updated `remove_remap()`:

```python
def remove_remap(game_dir: Path = DEFAULT_GAME_DIR) -> dict:
    """Restore vanilla PAZ from backup."""
    return remove_paz_patch(game_dir)
```

- [ ] **Step 4: Delete overlay_builder.py and update vendor __init__.py**

Delete: `tools/cd_remap/vendor/overlay_builder.py`

Update `tools/cd_remap/vendor/__init__.py`:

```python
"""Vendored subset of CDUMM (MIT license).

Source: https://github.com/XeNTaXBackup/CDUMM
Commit: 922c5c8 (v2.2.0)
Vendored: 2026-04-08

Only the modules needed for PAZ extraction, repacking, and in-place patching.
"""
```

- [ ] **Step 5: Run all tests**

Run: `cd D:/Games/Workshop/CD_REMAPPER/.claude/worktrees/sad-villani && python -m pytest tests/ -v`
Expected: All tests pass. Old overlay-dependent integration tests (if any) should be updated or removed.

- [ ] **Step 6: Commit**

```bash
git add tools/cd_remap/remap.py tools/cd_remap/vendor/__init__.py tests/test_remap.py
git rm tools/cd_remap/vendor/overlay_builder.py
git commit -m "feat: replace overlay VFS with in-place PAZ patching

Overlay approach (0036/) doesn't work for inputmap_common.xml.
Now patches PAZ 0012 directly with proper ChaCha20 encryption
and LZ4 compression. Backup/restore for undo."
```

---

### Task 6: Update CLAUDE.md + Final Verification

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update CLAUDE.md blocker section**

Replace the `BLOCKER` section in CLAUDE.md with the resolved status. Remove overlay-related content from "What This Is" and "BlackSpace Engine" sections. Update to reflect in-place PAZ patching is now the approach.

Key changes:
- Remove "BLOCKER: Overlay patching does NOT work" section
- Update "How remapping should work" to reflect current implementation
- Note that overlay_builder.py was removed from vendor

- [ ] **Step 2: Run full test suite one final time**

Run: `cd D:/Games/Workshop/CD_REMAPPER/.claude/worktrees/sad-villani && python -m pytest tests/ -v --tb=short`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md — blocker resolved, PAZ patching approach"
```

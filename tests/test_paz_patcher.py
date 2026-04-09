"""Tests for paz_patcher — PAMT binary patching and PAZ apply/remove."""
import struct
import pytest

from cd_remap.vendor.paz_patcher import (
    _apply_pamt_entry_update,
    TARGET_FILE,
    PAZ_FOLDER,
)
from cd_remap.vendor.paz_parse import parse_pamt, PazEntry
from cd_remap.vendor.hashlittle import compute_pamt_hash
from fixtures import build_test_paz_pamt_papgt


# Use repeated content so LZ4 compressed size is clearly smaller than original.
# This ensures the fixture entry has comp_size < orig_size, making entry.compressed=True.
PLAINTEXT = (
    b'<?xml version="1.0" encoding="utf-8"?>\n<InputMap>\n'
    + b'  <Input name="Sprint" GamePad Key="buttonA" />\n' * 20
    + b'</InputMap>\n'
)
MODIFIED = PLAINTEXT.replace(b"buttonA", b"buttonLB", 10)


# ── Helpers ───────────────────────────────────────────────────────────

def _parse_entry_from_pamt(pamt_bytes, paz_bytes, tmp_path):
    paz_dir = tmp_path / PAZ_FOLDER
    paz_dir.mkdir(exist_ok=True)
    (paz_dir / "0.paz").write_bytes(paz_bytes)
    pamt_path = tmp_path / "0.pamt"
    pamt_path.write_bytes(pamt_bytes)
    return parse_pamt(str(pamt_path), paz_dir=str(paz_dir))[0]


# ── TestApplyPamtEntryUpdate ──────────────────────────────────────────

class TestApplyPamtEntryUpdate:
    def test_updates_file_record_offset(self, tmp_path):
        paz_bytes, pamt_bytes, _papgt, _info = build_test_paz_pamt_papgt(
            PLAINTEXT, TARGET_FILE, PAZ_FOLDER
        )
        entry = _parse_entry_from_pamt(pamt_bytes, paz_bytes, tmp_path)

        data = bytearray(pamt_bytes)
        _apply_pamt_entry_update(data, entry, new_offset=9999, new_comp=entry.comp_size,
                                 new_orig=entry.orig_size)

        pattern = struct.pack("<IIII", 9999, entry.comp_size, entry.orig_size, entry.flags)
        assert pattern in bytes(data), "Updated offset not found in PAMT binary"

    def test_updates_file_record_comp_size(self, tmp_path):
        paz_bytes, pamt_bytes, _papgt, _info = build_test_paz_pamt_papgt(
            PLAINTEXT, TARGET_FILE, PAZ_FOLDER
        )
        entry = _parse_entry_from_pamt(pamt_bytes, paz_bytes, tmp_path)

        data = bytearray(pamt_bytes)
        new_comp = entry.comp_size + 100
        _apply_pamt_entry_update(data, entry, new_offset=entry.offset, new_comp=new_comp,
                                 new_orig=entry.orig_size + 100)

        pattern = struct.pack("<IIII", entry.offset, new_comp, entry.orig_size + 100, entry.flags)
        assert pattern in bytes(data)

    def test_updates_paz_size_in_header(self, tmp_path):
        paz_bytes, pamt_bytes, _papgt, _info = build_test_paz_pamt_papgt(
            PLAINTEXT, TARGET_FILE, PAZ_FOLDER
        )
        entry = _parse_entry_from_pamt(pamt_bytes, paz_bytes, tmp_path)

        data = bytearray(pamt_bytes)
        new_paz_size = len(paz_bytes) + 512
        _apply_pamt_entry_update(data, entry, new_offset=entry.offset,
                                 new_comp=entry.comp_size, new_orig=entry.orig_size,
                                 new_paz_size=new_paz_size)

        # PAZ size at header offset 20
        stored_size = struct.unpack_from("<I", data, 20)[0]
        assert stored_size == new_paz_size

    def test_paz_size_not_shrunk(self, tmp_path):
        """max(old_size, new_paz_size) — never write a smaller size."""
        paz_bytes, pamt_bytes, _papgt, _info = build_test_paz_pamt_papgt(
            PLAINTEXT, TARGET_FILE, PAZ_FOLDER
        )
        entry = _parse_entry_from_pamt(pamt_bytes, paz_bytes, tmp_path)

        original_paz_size = struct.unpack_from("<I", pamt_bytes, 20)[0]
        data = bytearray(pamt_bytes)
        _apply_pamt_entry_update(data, entry, new_offset=entry.offset,
                                 new_comp=entry.comp_size, new_orig=entry.orig_size,
                                 new_paz_size=1)

        stored_size = struct.unpack_from("<I", data, 20)[0]
        assert stored_size == original_paz_size

    def test_raises_if_record_not_found(self, tmp_path):
        paz_bytes, pamt_bytes, _papgt, _info = build_test_paz_pamt_papgt(
            PLAINTEXT, TARGET_FILE, PAZ_FOLDER
        )
        entry = _parse_entry_from_pamt(pamt_bytes, paz_bytes, tmp_path)

        bogus_entry = PazEntry(
            path=entry.path,
            paz_file=entry.paz_file,
            offset=0xDEADBEEF,
            comp_size=0xDEADBEEF,
            orig_size=0xDEADBEEF,
            flags=0xDEADBEEF,
            paz_index=0,
        )
        data = bytearray(pamt_bytes)
        with pytest.raises(ValueError, match="[Rr]ecord not found"):
            _apply_pamt_entry_update(data, bogus_entry, 0, 0, 0)

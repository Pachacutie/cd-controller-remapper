"""Sanity tests for the synthetic PAZ/PAMT/PAPGT fixture builder."""
import os
import pytest

from cd_remap.vendor.paz_parse import parse_pamt
from cd_remap.vendor.paz_crypto import decrypt, lz4_decompress
from fixtures import build_test_paz_pamt_papgt


PLAINTEXT = b'<?xml version="1.0"?>\n<InputMap>\n  <Input name="Jump" GamePad Key="buttonA" />\n</InputMap>\n'
ENTRY_PATH = "ui/inputmap_common.xml"
PAZ_DIR = "0012"


@pytest.fixture
def fixture_files(tmp_path):
    """Write fixture binaries to tmp_path and return the paths."""
    paz_bytes, pamt_bytes, _papgt_bytes, entry_info = build_test_paz_pamt_papgt(
        PLAINTEXT, ENTRY_PATH, PAZ_DIR
    )

    paz_dir = tmp_path / PAZ_DIR
    paz_dir.mkdir()
    (paz_dir / "0.paz").write_bytes(paz_bytes)
    (tmp_path / "0.pamt").write_bytes(pamt_bytes)

    return tmp_path, paz_bytes, pamt_bytes, entry_info


class TestFixtureBuilder:
    def test_parse_pamt_finds_entry(self, fixture_files):
        """parse_pamt returns one entry with the correct path."""
        tmp_path, _paz_bytes, _pamt_bytes, _info = fixture_files
        pamt_path = str(tmp_path / "0.pamt")
        paz_dir = str(tmp_path / PAZ_DIR)

        entries = parse_pamt(pamt_path, paz_dir=paz_dir)

        assert len(entries) == 1
        assert entries[0].path == ENTRY_PATH

    def test_parse_pamt_sizes_match(self, fixture_files):
        """Parsed entry has correct comp_size and orig_size."""
        tmp_path, _paz_bytes, _pamt_bytes, info = fixture_files
        pamt_path = str(tmp_path / "0.pamt")
        paz_dir = str(tmp_path / PAZ_DIR)

        entries = parse_pamt(pamt_path, paz_dir=paz_dir)
        entry = entries[0]

        assert entry.comp_size == info["comp_size"]
        assert entry.orig_size == info["orig_size"]
        assert entry.offset == info["offset"]
        assert entry.flags == info["flags"]

    def test_decrypt_decompress_roundtrip(self, fixture_files):
        """Decrypt then decompress yields the original plaintext."""
        tmp_path, paz_bytes, _pamt_bytes, info = fixture_files
        pamt_path = str(tmp_path / "0.pamt")
        paz_dir = str(tmp_path / PAZ_DIR)

        entries = parse_pamt(pamt_path, paz_dir=paz_dir)
        entry = entries[0]

        raw = paz_bytes[entry.offset: entry.offset + entry.comp_size]
        decrypted = decrypt(raw, entry.path)
        plaintext = lz4_decompress(decrypted, entry.orig_size)

        assert plaintext == PLAINTEXT

    def test_compression_type_flag(self, fixture_files):
        """Entry reports compression_type=2 (LZ4)."""
        tmp_path, _paz_bytes, _pamt_bytes, _info = fixture_files
        entries = parse_pamt(str(tmp_path / "0.pamt"), paz_dir=str(tmp_path / PAZ_DIR))
        assert entries[0].compression_type == 2

    def test_encrypted_heuristic(self, fixture_files):
        """XML entry is recognised as encrypted by the heuristic."""
        tmp_path, _paz_bytes, _pamt_bytes, _info = fixture_files
        entries = parse_pamt(str(tmp_path / "0.pamt"), paz_dir=str(tmp_path / PAZ_DIR))
        assert entries[0].encrypted is True

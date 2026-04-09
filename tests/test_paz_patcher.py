"""Tests for paz_patcher — PAMT binary patching and PAZ apply/remove."""
import struct
import pytest

from cd_remap.vendor.paz_patcher import (
    _apply_pamt_entry_update,
    apply_paz_patch,
    remove_paz_patch,
    _backup_dir,
    TARGET_FILE,
    PAZ_FOLDER,
)
from cd_remap.vendor.paz_parse import parse_pamt, PazEntry
from cd_remap.vendor.paz_crypto import decrypt, lz4_decompress
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

def _write_game_dir(tmp_path, paz_bytes, pamt_bytes, papgt_bytes):
    paz_dir = tmp_path / PAZ_FOLDER
    paz_dir.mkdir(parents=True)
    (paz_dir / "0.paz").write_bytes(paz_bytes)
    (paz_dir / "0.pamt").write_bytes(pamt_bytes)
    meta_dir = tmp_path / "meta"
    meta_dir.mkdir()
    (meta_dir / "0.papgt").write_bytes(papgt_bytes)
    return tmp_path


def _parse_entry_from_pamt(pamt_bytes, paz_bytes, tmp_path):
    paz_dir = tmp_path / PAZ_FOLDER
    paz_dir.mkdir(exist_ok=True)
    (paz_dir / "0.paz").write_bytes(paz_bytes)
    pamt_path = tmp_path / "0.pamt"
    pamt_path.write_bytes(pamt_bytes)
    return parse_pamt(str(pamt_path), paz_dir=str(paz_dir))[0]


def _extract_entry(game_dir, entry):
    """Read, decrypt and decompress an entry from the game dir."""
    raw = (game_dir / PAZ_FOLDER / "0.paz").read_bytes()
    chunk = raw[entry.offset: entry.offset + entry.comp_size]
    decrypted = decrypt(chunk, entry.path)
    return lz4_decompress(decrypted, entry.orig_size)


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


# ── TestApplyPazPatch ─────────────────────────────────────────────────

class TestApplyPazPatch:
    def _setup(self, tmp_path, monkeypatch, plaintext=PLAINTEXT):
        paz_bytes, pamt_bytes, papgt_bytes, _info = build_test_paz_pamt_papgt(
            plaintext, TARGET_FILE, PAZ_FOLDER
        )
        game_dir = _write_game_dir(tmp_path / "game", paz_bytes, pamt_bytes, papgt_bytes)
        backup = tmp_path / "backup"
        monkeypatch.setattr("cd_remap.vendor.paz_patcher._backup_dir", lambda: backup)
        return game_dir, paz_bytes, pamt_bytes

    def test_apply_returns_ok(self, tmp_path, monkeypatch):
        game_dir, _paz, _pamt = self._setup(tmp_path, monkeypatch)
        result = apply_paz_patch(MODIFIED, game_dir)
        assert result == {"ok": True}

    def test_apply_same_size_content_readable(self, tmp_path, monkeypatch):
        """Apply a patch and verify modified content is extractable."""
        game_dir, _paz, _pamt = self._setup(tmp_path, monkeypatch)
        apply_paz_patch(MODIFIED, game_dir)

        pamt_path = str(game_dir / PAZ_FOLDER / "0.pamt")
        paz_dir = str(game_dir / PAZ_FOLDER)
        entries = parse_pamt(pamt_path, paz_dir=paz_dir)
        assert len(entries) == 1

        result = _extract_entry(game_dir, entries[0])
        assert result == MODIFIED

    def test_backup_created(self, tmp_path, monkeypatch):
        game_dir, _paz, _pamt = self._setup(tmp_path, monkeypatch)
        backup = tmp_path / "backup"
        monkeypatch.setattr("cd_remap.vendor.paz_patcher._backup_dir", lambda: backup)

        apply_paz_patch(MODIFIED, game_dir)

        assert (backup / PAZ_FOLDER / "0.paz").exists()
        assert (backup / PAZ_FOLDER / "0.pamt").exists()
        assert (backup / "meta" / "0.papgt").exists()

    def test_backup_not_overwritten(self, tmp_path, monkeypatch):
        """Applying twice must not overwrite the original backup."""
        game_dir, orig_paz, _pamt = self._setup(tmp_path, monkeypatch)
        backup = tmp_path / "backup"
        monkeypatch.setattr("cd_remap.vendor.paz_patcher._backup_dir", lambda: backup)

        apply_paz_patch(MODIFIED, game_dir)
        backup_paz_after_first = (backup / PAZ_FOLDER / "0.paz").read_bytes()

        apply_paz_patch(PLAINTEXT, game_dir)
        backup_paz_after_second = (backup / PAZ_FOLDER / "0.paz").read_bytes()

        # Backup should still be the original (pre-first-apply) content
        assert backup_paz_after_first == backup_paz_after_second == orig_paz

    def test_pamt_hash_updated(self, tmp_path, monkeypatch):
        """After apply, PAMT integrity hash is valid."""
        game_dir, _paz, _pamt = self._setup(tmp_path, monkeypatch)
        apply_paz_patch(MODIFIED, game_dir)

        pamt_bytes = (game_dir / PAZ_FOLDER / "0.pamt").read_bytes()
        stored_hash = struct.unpack_from("<I", pamt_bytes, 0)[0]
        expected_hash = compute_pamt_hash(pamt_bytes)
        assert stored_hash == expected_hash

    def test_apply_larger_content_appended(self, tmp_path, monkeypatch):
        """Content that grows beyond comp_size is appended to PAZ."""
        game_dir, orig_paz, _pamt = self._setup(tmp_path, monkeypatch)
        large_content = PLAINTEXT + b"\n<!-- " + b"X" * 10000 + b" -->"
        apply_paz_patch(large_content, game_dir)

        new_paz = (game_dir / PAZ_FOLDER / "0.paz").read_bytes()
        assert len(new_paz) > len(orig_paz)

        pamt_path = str(game_dir / PAZ_FOLDER / "0.pamt")
        paz_dir = str(game_dir / PAZ_FOLDER)
        entries = parse_pamt(pamt_path, paz_dir=paz_dir)
        result = _extract_entry(game_dir, entries[0])
        assert result == large_content


# ── TestRemovePazPatch ────────────────────────────────────────────────

class TestRemovePazPatch:
    def _setup(self, tmp_path, monkeypatch):
        paz_bytes, pamt_bytes, papgt_bytes, _info = build_test_paz_pamt_papgt(
            PLAINTEXT, TARGET_FILE, PAZ_FOLDER
        )
        game_dir = _write_game_dir(tmp_path / "game", paz_bytes, pamt_bytes, papgt_bytes)
        backup = tmp_path / "backup"
        monkeypatch.setattr("cd_remap.vendor.paz_patcher._backup_dir", lambda: backup)
        return game_dir, paz_bytes, pamt_bytes, papgt_bytes

    def test_restores_vanilla(self, tmp_path, monkeypatch):
        game_dir, orig_paz, orig_pamt, orig_papgt = self._setup(tmp_path, monkeypatch)

        apply_paz_patch(MODIFIED, game_dir)
        result = remove_paz_patch(game_dir)

        assert result["ok"] is True
        assert (game_dir / PAZ_FOLDER / "0.paz").read_bytes() == orig_paz
        assert (game_dir / PAZ_FOLDER / "0.pamt").read_bytes() == orig_pamt
        assert (game_dir / "meta" / "0.papgt").read_bytes() == orig_papgt

    def test_remove_returns_message(self, tmp_path, monkeypatch):
        game_dir, _paz, _pamt, _papgt = self._setup(tmp_path, monkeypatch)
        apply_paz_patch(MODIFIED, game_dir)
        result = remove_paz_patch(game_dir)
        assert "message" in result
        assert result["ok"] is True

    def test_remove_without_backup_returns_error(self, tmp_path, monkeypatch):
        game_dir, _paz, _pamt, _papgt = self._setup(tmp_path, monkeypatch)
        result = remove_paz_patch(game_dir)
        assert not result["ok"]
        assert "No backup" in result["message"]

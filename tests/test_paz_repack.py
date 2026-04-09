"""Tests for paz_repack — LZ4 size matching and PAZ entry repacking."""
import pytest
import lz4.block

from cd_remap.vendor.paz_repack import (
    _pad_to_orig_size,
    _match_compressed_size,
    repack_entry_bytes,
)
from cd_remap.vendor.paz_parse import PazEntry
from cd_remap.vendor.paz_crypto import decrypt, lz4_decompress


# ── Helpers ──────────────────────────────────────────────────────────

def make_entry(path="ui/inputmap_common.xml", comp_size=None, orig_size=None,
               flags=0x00020000, encrypted=True):
    """Create a PazEntry for testing."""
    entry = PazEntry(
        path=path,
        paz_file="fake.paz",
        offset=0,
        comp_size=comp_size,
        orig_size=orig_size,
        flags=flags,
        paz_index=0,
    )
    entry._encrypted_override = encrypted
    return entry


def make_xml_content(n_lines=100):
    """Generate realistic XML content for testing."""
    lines = ['<?xml version="1.0" encoding="utf-8"?>']
    lines.append('<InputMap version="1">')
    for i in range(n_lines):
        lines.append(
            f'  <Input name="Action_{i}" GamePad Key="buttonA" />'
        )
    lines.append('</InputMap>')
    return '\n'.join(lines).encode('utf-8')


def compress_exact(data: bytes) -> bytes:
    return lz4.block.compress(data, store_size=False)


# ── TestMatchCompressedSize ───────────────────────────────────────────

class TestMatchCompressedSize:
    def test_hits_exact_target(self):
        """Binary search produces exactly target_comp bytes."""
        plaintext = make_xml_content(200)
        orig_size = len(plaintext) + 500  # leave room for padding
        padded = _pad_to_orig_size(plaintext, orig_size)
        target_comp = len(compress_exact(padded))

        result = _match_compressed_size(plaintext, target_comp, orig_size)

        assert len(result) == orig_size
        assert len(compress_exact(result)) == target_comp

    def test_slightly_different_content_still_hits_target(self):
        """Modified content (different button names) still matches original target."""
        original = make_xml_content(200)
        orig_size = len(original) + 1000
        padded = _pad_to_orig_size(original, orig_size)
        target_comp = len(compress_exact(padded))

        # Simulate a button swap: replace buttonA with buttonLT (shorter name)
        modified = original.replace(b"buttonA", b"buttonLT")[:len(original)]
        modified = modified[:len(original)]

        result = _match_compressed_size(modified, target_comp, orig_size)

        assert len(result) == orig_size
        assert len(compress_exact(result)) == target_comp

    def test_raises_when_content_too_large(self):
        """ValueError raised when content is already too large to compress small enough."""
        # Create tiny target: compress many repeated bytes — very compressible
        # Then use content that's incompressible (random-looking) to exceed it.
        import os
        plaintext = os.urandom(4000)  # nearly incompressible
        orig_size = len(plaintext)
        # Target is the compressed size of highly compressible data (zeros)
        target_comp = len(compress_exact(b'\x00' * orig_size))

        with pytest.raises(ValueError, match="[Cc]ompress"):
            _match_compressed_size(plaintext, target_comp, orig_size)


# ── TestRepackEntryBytes ──────────────────────────────────────────────

class TestRepackEntryBytes:
    def _make_realistic_entry(self, plaintext: bytes, encrypted: bool = True):
        """Build an entry whose comp/orig sizes match a real compress of plaintext."""
        padded = plaintext  # no extra padding needed for these tests
        compressed = compress_exact(padded)
        return make_entry(
            comp_size=len(compressed),
            orig_size=len(padded),
            encrypted=encrypted,
        )

    def test_roundtrip_same_content(self):
        """repack then decrypt+decompress yields original content."""
        plaintext = make_xml_content(150)
        entry = self._make_realistic_entry(plaintext)

        payload, actual_comp, actual_orig = repack_entry_bytes(plaintext, entry)

        basename = "inputmap_common.xml"
        decrypted = decrypt(payload, basename)
        decompressed = lz4_decompress(decrypted[:actual_comp], entry.orig_size)
        assert decompressed == plaintext

    def test_roundtrip_modified_content(self):
        """Modified content (button swap) round-trips correctly."""
        original = make_xml_content(150)
        # Swap buttonA -> buttonLT in a few places, keep same byte count
        modified = original.replace(b'buttonA', b'butLT00')
        assert len(modified) == len(original)

        entry = self._make_realistic_entry(original)

        payload, actual_comp, actual_orig = repack_entry_bytes(modified, entry)

        basename = "inputmap_common.xml"
        decrypted = decrypt(payload, basename)
        decompressed = lz4_decompress(decrypted[:actual_comp], entry.orig_size)
        assert decompressed == _pad_to_orig_size(modified, entry.orig_size)

    def test_allow_size_change_returns_actual_sizes(self):
        """With allow_size_change=True, returns actual compressed size (not entry size)."""
        # Use content larger than what the entry was sized for
        original = make_xml_content(100)
        entry = self._make_realistic_entry(original, encrypted=False)

        # Modified content is longer
        modified = make_xml_content(200)

        payload, actual_comp, actual_orig = repack_entry_bytes(
            modified, entry, allow_size_change=True
        )

        # Sizes should reflect actual compressed size, not original entry
        assert actual_orig == len(modified)
        real_comp = len(compress_exact(modified))
        assert actual_comp == real_comp

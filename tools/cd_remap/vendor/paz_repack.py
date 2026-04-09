"""PAZ asset repacker — LZ4 size-matching and entry repacking.

Ported from CDUMM v2.2.0. Handles only type-2 (LZ4) and uncompressed entries;
DDS type-1 split-header format is not needed for XML remapping.

Pipeline: modified XML -> LZ4 compress (size-matched) -> ChaCha20 encrypt -> payload
"""

import re

import lz4.block

from .paz_parse import PazEntry
from .paz_crypto import encrypt


# ── Size matching ────────────────────────────────────────────────────

def _pad_to_orig_size(data: bytes, orig_size: int) -> bytes:
    """Pad data to exactly orig_size bytes with null bytes, or truncate if larger."""
    if len(data) >= orig_size:
        return data[:orig_size]
    return data + b'\x00' * (orig_size - len(data))


def _strip_whitespace_to_fit(plaintext: bytes, target_comp: int, target_orig: int) -> bytes | None:
    """Strip trailing whitespace to reduce compressed size.

    Returns padded plaintext that compresses within target, or None if impossible.
    """
    text = plaintext.decode('utf-8', errors='replace')

    # First pass: strip trailing whitespace per line
    stripped = '\r\n'.join(line.rstrip() for line in text.splitlines())
    candidate = stripped.encode('utf-8')
    padded = _pad_to_orig_size(candidate, target_orig)
    if len(lz4.block.compress(padded, store_size=False)) <= target_comp:
        return padded

    # Second pass: collapse runs of spaces/newlines
    stripped = re.sub(r'[ \t]+', ' ', stripped)
    stripped = re.sub(r'\n{3,}', '\n\n', stripped)
    candidate = stripped.encode('utf-8')
    padded = _pad_to_orig_size(candidate, target_orig)
    if len(lz4.block.compress(padded, store_size=False)) <= target_comp:
        return padded

    return None


def _match_compressed_size(plaintext: bytes, target_comp_size: int,
                            target_orig_size: int) -> bytes:
    """Adjust plaintext so it LZ4-compresses to exactly target_comp_size bytes.

    Pads with printable ASCII filler via binary search to grow compressed output.
    Strips whitespace if content is already too large.

    Returns adjusted plaintext (exactly target_orig_size bytes).
    Raises ValueError if matching fails.
    """
    padded = _pad_to_orig_size(plaintext, target_orig_size)
    comp = lz4.block.compress(padded, store_size=False)
    if len(comp) == target_comp_size:
        return padded

    filler = bytes(range(33, 127))  # printable ASCII — resists LZ4 compression

    if len(comp) < target_comp_size:
        # Binary search: grow filler suffix to push compressed size up
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

        # Linear scan around the binary-search boundary
        for n in range(max(0, lo - 5), min(hi + 6, target_orig_size - len(plaintext) + 1)):
            fill = (filler * (n // len(filler) + 1))[:n] if n > 0 else b''
            trial = _pad_to_orig_size(plaintext + fill, target_orig_size)
            c = lz4.block.compress(trial, store_size=False)
            if len(c) == target_comp_size:
                return trial

    if len(comp) > target_comp_size:
        # Try whitespace stripping before giving up
        result = _strip_whitespace_to_fit(plaintext, target_comp_size, target_orig_size)
        if result is not None:
            trimmed = lz4.block.compress(result, store_size=False)
            if len(trimmed) == target_comp_size:
                return result
        raise ValueError(
            f"Compressed size {len(comp)} exceeds target {target_comp_size}. "
            "Reduce file content."
        )

    raise ValueError(
        f"Cannot match target comp_size {target_comp_size} "
        f"(best: {len(lz4.block.compress(padded, store_size=False))})"
    )


# ── Core repack ──────────────────────────────────────────────────────

def repack_entry_bytes(plaintext: bytes, entry: PazEntry,
                       allow_size_change: bool = False) -> tuple[bytes, int, int]:
    """Repack modified content into an encrypted/compressed PAZ payload.

    For compression type 2 (LZ4):
      - allow_size_change=False: use _match_compressed_size for exact fit
      - allow_size_change=True: compress freely; pad if smaller, raw if larger

    For uncompressed entries: pad to entry.comp_size or return raw if larger.

    Encrypts with ChaCha20 if entry.encrypted is True.

    Returns:
        (payload_bytes, actual_comp_size, actual_orig_size)
    """
    is_compressed = entry.compressed and entry.compression_type == 2
    actual_comp_size = entry.comp_size
    actual_orig_size = entry.orig_size

    if is_compressed:
        if allow_size_change:
            actual_orig_size = len(plaintext)
            compressed = lz4.block.compress(plaintext, store_size=False)
            actual_comp_size = len(compressed)
            if actual_comp_size > entry.comp_size:
                payload = compressed
            else:
                payload = compressed + b'\x00' * (entry.comp_size - actual_comp_size)
        else:
            adjusted = _match_compressed_size(plaintext, entry.comp_size, entry.orig_size)
            compressed = lz4.block.compress(adjusted, store_size=False)
            if len(compressed) != entry.comp_size:
                raise ValueError(
                    f"Size mismatch after compression: {len(compressed)} != {entry.comp_size}"
                )
            payload = compressed
    else:
        if allow_size_change:
            actual_comp_size = len(plaintext)
            actual_orig_size = len(plaintext)
            if len(plaintext) <= entry.comp_size:
                payload = plaintext + b'\x00' * (entry.comp_size - len(plaintext))
            else:
                payload = plaintext
        elif len(plaintext) > entry.comp_size:
            raise ValueError(
                f"Modified file ({len(plaintext)} bytes) exceeds budget "
                f"({entry.comp_size} bytes)"
            )
        else:
            payload = plaintext + b'\x00' * (entry.comp_size - len(plaintext))

    if entry.encrypted:
        payload = encrypt(payload, entry.path)

    return payload, actual_comp_size, actual_orig_size

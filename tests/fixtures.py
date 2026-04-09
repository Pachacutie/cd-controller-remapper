"""Synthetic PAZ/PAMT/PAPGT fixture builder for testing the patcher.

No real game data needed — creates minimal valid binary archives that
parse_pamt() can parse and that decrypt()/lz4_decompress() can roundtrip.
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
    """Build minimal valid PAZ/PAMT/PAPGT binaries from plaintext.

    Returns:
        (paz_bytes, pamt_bytes, papgt_bytes, entry_info)
        entry_info keys: offset, comp_size, orig_size, flags
    """
    compressed = lz4.block.compress(plaintext, store_size=False)
    encrypted = encrypt(compressed, entry_path)

    comp_size = len(compressed)
    orig_size = len(plaintext)
    offset = 0
    flags = 0x00020000  # compression_type=2 (LZ4), paz_index=0

    paz_bytes = encrypted
    pamt_bytes = _build_minimal_pamt(paz_bytes, entry_path, offset, comp_size, orig_size, flags)
    papgt_bytes = _build_minimal_papgt(pamt_bytes, paz_dir_name)

    return paz_bytes, pamt_bytes, papgt_bytes, {
        "offset": offset,
        "comp_size": comp_size,
        "orig_size": orig_size,
        "flags": flags,
    }


def build_multi_file_paz(
    files: list[tuple[str, bytes]],
    paz_dir_name: str = "0012",
) -> tuple[bytes, bytes, bytes]:
    """Build PAZ/PAMT/PAPGT with multiple files in a single PAZ archive.

    Args:
        files: list of (entry_path, plaintext) tuples — all share folder "ui/"

    Returns:
        (paz_bytes, pamt_bytes, papgt_bytes)
    """
    # Build PAZ: concatenate encrypted+compressed payloads
    paz_parts = []
    entries_info = []
    offset = 0
    for path, plaintext in files:
        compressed = lz4.block.compress(plaintext, store_size=False)
        encrypted = encrypt(compressed, path)
        paz_parts.append(encrypted)
        entries_info.append((path, offset, len(compressed), len(plaintext)))
        offset += len(encrypted)

    paz_bytes = b"".join(paz_parts)
    pamt_bytes = _build_multi_file_pamt(paz_bytes, entries_info)
    papgt_bytes = _build_minimal_papgt(pamt_bytes, paz_dir_name)
    return paz_bytes, pamt_bytes, papgt_bytes


def _build_multi_file_pamt(
    paz_data: bytes,
    entries: list[tuple[str, int, int, int]],
) -> bytes:
    """Build PAMT with multiple file entries in the same folder and PAZ file.

    entries: list of (path, offset, comp_size, orig_size) — all must share a folder prefix.
    """
    # All entries must share the same folder
    folder = entries[0][0].split("/", 1)[0]
    filenames = [path.split("/", 1)[1] for path, *_ in entries]

    folder_name_b = folder.encode("utf-8")
    folder_record = struct.pack("<IB", 0xFFFFFFFF, len(folder_name_b)) + folder_name_b
    folder_section = struct.pack("<I", len(folder_record)) + folder_record

    # Build node section — one node per file
    node_records = b""
    for fn in filenames:
        fn_b = fn.encode("utf-8")
        node_records += struct.pack("<IB", 0xFFFFFFFF, len(fn_b)) + fn_b
    node_section = struct.pack("<I", len(node_records)) + node_records

    # folder_records: 1 folder, file_count = len(entries)
    folder_records = struct.pack("<IIIII", 1, 0, 0, 0, len(entries))

    # file_records: each file is 20 bytes
    file_data = b""
    node_offset = 0
    for i, (path, offset, comp_size, orig_size) in enumerate(entries):
        flags = 0x00020000  # LZ4, paz_index=0
        file_data += struct.pack("<IIIII", node_offset, offset, comp_size, orig_size, flags)
        fn_b = filenames[i].encode("utf-8")
        node_offset += 5 + len(fn_b)  # IB + name
    file_records = struct.pack("<I", len(entries)) + file_data

    paz_hash = hashlittle(paz_data, INTEGRITY_SEED)
    paz_size = len(paz_data)

    body = struct.pack("<IIII", 1, 0x610E0232, 0, paz_hash)
    body += struct.pack("<I", paz_size)
    body += folder_section + node_section + folder_records + file_records

    outer_hash = hashlittle(body[8:], INTEGRITY_SEED)
    return struct.pack("<I", outer_hash) + body


def _build_minimal_pamt(
    paz_data: bytes,
    entry_path: str,
    offset: int,
    comp_size: int,
    orig_size: int,
    flags: int,
) -> bytes:
    """Build a minimal PAMT binary with one folder and one file entry.

    Layout (header):
      [0:4]   outer_hash  (computed last, over pamt[12:])
      [4:8]   paz_count = 1
      [8:12]  magic = 0x610E0232
      [12:16] zero
      [16:20] paz_hash = hashlittle(paz_data, INTEGRITY_SEED)
      [20:24] paz_size = len(paz_data)
    """
    folder, filename = entry_path.split("/", 1)

    folder_name_b = folder.encode("utf-8")
    file_name_b = filename.encode("utf-8")

    # folder_section: one record — parent=0xFFFFFFFF, slen, name
    folder_record = struct.pack("<IB", 0xFFFFFFFF, len(folder_name_b)) + folder_name_b
    folder_section = struct.pack("<I", len(folder_record)) + folder_record

    # node_section: one node at rel=0 — parent=0xFFFFFFFF, slen, name
    node_record = struct.pack("<IB", 0xFFFFFFFF, len(file_name_b)) + file_name_b
    node_section = struct.pack("<I", len(node_record)) + node_record

    # folder_records: count=1, one 16-byte record
    # path_hash(4) + folder_ref(4, =0) + file_index(4, =0) + file_count(4, =1)
    folder_records = struct.pack("<IIIII", 1, 0, 0, 0, 1)

    # file_records: count=1, one 20-byte record
    # node_ref(4, =0) + offset(4) + comp_size(4) + orig_size(4) + flags(4)
    file_records = struct.pack("<IIIIII", 1, 0, offset, comp_size, orig_size, flags)

    paz_hash = hashlittle(paz_data, INTEGRITY_SEED)
    paz_size = len(paz_data)

    # Assemble body (everything after [0:4])
    body = struct.pack("<IIII", 1, 0x610E0232, 0, paz_hash)
    body += struct.pack("<I", paz_size)
    body += folder_section
    body += node_section
    body += folder_records
    body += file_records

    # outer_hash covers pamt[12:], which is body[8:] (body starts at offset 4)
    outer_hash = hashlittle(body[8:], INTEGRITY_SEED)

    return struct.pack("<I", outer_hash) + body


def _build_minimal_papgt(pamt_data: bytes, dir_name: str) -> bytes:
    """Build a minimal PAPGT with one directory entry.

    Layout:
      [0:4]   metadata = 0
      [4:8]   file_hash  (computed last, over papgt[12:])
      [8:12]  metadata (byte 8 = entry count = 1)
      [12:24] entry: flags(4) + name_offset(4, =0) + pamt_hash(4)
      [24:28] string_table_size
      [28:]   string_table (dir_name + null terminator)
    """
    pamt_hash = hashlittle(pamt_data[12:], INTEGRITY_SEED)
    dir_name_b = dir_name.encode("ascii") + b"\x00"

    # Build body (everything after [0:8])
    entry_count = 1
    metadata_8_12 = struct.pack("<I", entry_count)  # byte 8 = 1
    entry = struct.pack("<III", 0x003FFF00, 0, pamt_hash)
    string_table_size = struct.pack("<I", len(dir_name_b))
    body = metadata_8_12 + entry + string_table_size + dir_name_b

    # file_hash covers papgt[12:], which is body[4:] (body starts at offset 8)
    file_hash = hashlittle(body[4:], INTEGRITY_SEED)

    return struct.pack("<II", 0, file_hash) + body

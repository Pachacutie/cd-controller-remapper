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

import struct

from cd_remap.vendor.paz_parse import PazEntry

TARGET_FILE = "ui/inputmap_common.xml"
PAZ_FOLDER = "0012"


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

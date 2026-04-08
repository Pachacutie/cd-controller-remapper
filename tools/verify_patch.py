"""Verify that a JSON byte-patch mod matches the current game files.

Usage:
    python verify_patch.py <mod.json> [--game-dir <path>]

Requires CDUMM installed at CDUMM_PATH below.
"""

import argparse
import json
import sys
from pathlib import Path

# Machine-specific paths — update these per installation
CDUMM_PATH = Path("D:/Games/Modding/Tools/CDUMM/src")
DEFAULT_GAME_DIR = Path("D:/Games/SteamLibrary/steamapps/common/Crimson Desert")

sys.path.insert(0, str(CDUMM_PATH))

from cdumm.archive.paz_parse import parse_pamt
from cdumm.archive.paz_crypto import lz4_decompress


def verify_mod(mod_path: str, game_dir: Path = DEFAULT_GAME_DIR) -> bool:
    with open(mod_path) as f:
        mod = json.load(f)

    print(f"Verifying: {mod['name']} v{mod['version']}")
    print(f"Game dir:  {game_dir}\n")

    # Build a cache of PAMT entries per PAZ folder
    pamt_cache: dict[str, list] = {}
    total_ok = 0
    total_fail = 0

    for patch_group in mod["patches"]:
        game_file = patch_group["game_file"]
        paz_folder = patch_group.get("paz_folder")

        # Use paz_folder hint if provided, otherwise scan all folders
        entry = None
        folders_to_check = [paz_folder] if paz_folder else [f"{n:04d}" for n in range(36)]
        for folder in folders_to_check:
            paz_dir = game_dir / folder
            pamt_path = paz_dir / "0.pamt"
            if not pamt_path.exists():
                continue

            if folder not in pamt_cache:
                pamt_cache[folder] = parse_pamt(str(pamt_path), str(paz_dir))

            matches = [e for e in pamt_cache[folder] if e.path == game_file]
            if matches:
                entry = matches[0]
                break

        if entry is None:
            print(f"  ERROR: {game_file} not found in any PAZ folder")
            total_fail += len(patch_group["changes"])
            continue

        # Extract and decompress
        with open(entry.paz_file, "rb") as f:
            f.seek(entry.offset)
            raw = f.read(entry.comp_size)

        if entry.compressed:
            data = lz4_decompress(raw, entry.orig_size)
        else:
            data = raw

        print(f"  {game_file} ({len(data)} bytes, folder {folder})")

        for change in patch_group["changes"]:
            offset = change["offset"]
            orig_bytes = bytes.fromhex(change["original"])
            actual = data[offset : offset + len(orig_bytes)]

            if actual == orig_bytes:
                print(f"    OK  {change['label']}")
                total_ok += 1
            else:
                print(f"    FAIL {change['label']}")
                print(f"         expected: {change['original']}")
                print(f"         got:      {actual.hex()}")
                total_fail += 1

    print(f"\nResult: {total_ok} OK, {total_fail} FAIL")
    return total_fail == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify JSON byte-patch mod")
    parser.add_argument("mod", help="Path to mod JSON file")
    parser.add_argument("--game-dir", type=Path, default=DEFAULT_GAME_DIR)
    args = parser.parse_args()

    ok = verify_mod(args.mod, args.game_dir)
    sys.exit(0 if ok else 1)

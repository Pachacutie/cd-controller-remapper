"""Apply a JSON byte-patch mod to Crimson Desert via the overlay system.

Creates 0036/ overlay with patched files, updates meta/0.papgt.

Usage:
    python apply_mod.py apply <mod.json> [--game-dir <path>] [--dry-run]
    python apply_mod.py remove [--game-dir <path>]

Requires CDUMM installed at CDUMM_PATH below.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

# Machine-specific paths — update these per installation
CDUMM_PATH = Path("D:/Games/Modding/Tools/CDUMM/src")
DEFAULT_GAME_DIR = Path("D:/Games/SteamLibrary/steamapps/common/Crimson Desert")
BACKUP_DIR = Path("D:/Games/Modding/Crimson Desert/BACKUP_PRISTINE")

sys.path.insert(0, str(CDUMM_PATH))

from cdumm.archive.paz_parse import parse_pamt
from cdumm.archive.paz_crypto import lz4_decompress
from cdumm.archive.overlay_builder import build_overlay
from cdumm.archive.papgt_manager import PapgtManager


def apply_mod(mod_path: str, game_dir: Path = DEFAULT_GAME_DIR, dry_run: bool = False) -> bool:
    with open(mod_path) as f:
        mod = json.load(f)

    print(f"Applying: {mod['name']} v{mod['version']}")
    print(f"Game dir: {game_dir}")
    if dry_run:
        print("DRY RUN — no files will be written\n")
    print()

    # Check for existing overlay
    overlay_dir = game_dir / "0036"
    if overlay_dir.exists() and any(overlay_dir.iterdir()):
        print(f"  WARNING: {overlay_dir} already exists with content.")
        print(f"  Existing overlay will be overwritten.")

    # Build PAMT cache per PAZ folder
    pamt_cache: dict[str, dict[str, object]] = {}
    overlay_inputs = []

    for patch_group in mod["patches"]:
        game_file = patch_group["game_file"]
        paz_folder = patch_group.get("paz_folder", "0014")

        if paz_folder not in pamt_cache:
            paz_dir = game_dir / paz_folder
            entries = parse_pamt(str(paz_dir / "0.pamt"), str(paz_dir))
            pamt_cache[paz_folder] = {e.path: e for e in entries}

        entry = pamt_cache[paz_folder].get(game_file)
        if entry is None:
            print(f"  ERROR: {game_file} not found in {paz_folder}")
            return False

        # Extract and decompress
        with open(entry.paz_file, "rb") as f:
            f.seek(entry.offset)
            raw = f.read(entry.comp_size)

        data = bytearray(lz4_decompress(raw, entry.orig_size) if entry.compressed else raw)

        # Apply patches
        print(f"  {game_file} ({len(data)} bytes, folder {paz_folder})")
        for change in patch_group["changes"]:
            offset = change["offset"]
            orig = bytes.fromhex(change["original"])
            patch = bytes.fromhex(change["patched"])
            actual = bytes(data[offset : offset + len(orig)])

            if actual != orig:
                print(f"    MISMATCH at offset {offset} — file may already be patched or game was updated")
                print(f"      expected: {orig.hex()}")
                print(f"      found:    {actual.hex()}")
                return False

            data[offset : offset + len(patch)] = patch
            print(f"    PATCHED: {change['label']}")

        overlay_inputs.append((
            bytes(data),
            {
                "entry_path": game_file,
                "compression_type": entry.compression_type,
                "pamt_dir": paz_folder,
            },
        ))

    if dry_run:
        print(f"\nDry run complete. {len(overlay_inputs)} files would be written to 0036/")
        return True

    # Backup PAPGT before modifying
    papgt_path = game_dir / "meta" / "0.papgt"
    backup_papgt = BACKUP_DIR / "meta" / "0.papgt"
    if not backup_papgt.exists():
        backup_papgt.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(papgt_path, backup_papgt)
        print(f"  Backed up: meta/0.papgt -> {backup_papgt}")

    # Build overlay PAZ + PAMT
    print("\nBuilding overlay...")
    paz_bytes, pamt_bytes = build_overlay(overlay_inputs, game_dir=str(game_dir))

    # Write overlay first, PAPGT last.
    # If interrupted before PAPGT write, the game ignores the unregistered 0036/.
    overlay_dir.mkdir(exist_ok=True)
    (overlay_dir / "0.paz").write_bytes(paz_bytes)
    (overlay_dir / "0.pamt").write_bytes(pamt_bytes)
    print(f"  Written: 0036/0.paz ({len(paz_bytes)} bytes)")
    print(f"  Written: 0036/0.pamt ({len(pamt_bytes)} bytes)")

    # Rebuild PAPGT — written last for crash safety
    print("Rebuilding PAPGT...")
    papgt_mgr = PapgtManager(game_dir)
    papgt_bytes = papgt_mgr.rebuild(modified_pamts={"0036": pamt_bytes})
    papgt_path.write_bytes(papgt_bytes)
    print(f"  Written: meta/0.papgt ({len(papgt_bytes)} bytes)")

    print(f"\nMod applied successfully. Launch the game to test.")
    return True


def remove_mod(game_dir: Path = DEFAULT_GAME_DIR) -> bool:
    """Remove mod by deleting overlay and restoring vanilla PAPGT."""
    overlay_dir = game_dir / "0036"
    backup_papgt = BACKUP_DIR / "meta" / "0.papgt"

    if overlay_dir.exists():
        shutil.rmtree(overlay_dir)
        print(f"Removed: {overlay_dir}")

    if backup_papgt.exists():
        shutil.copy2(backup_papgt, game_dir / "meta" / "0.papgt")
        print(f"Restored: meta/0.papgt from backup")
    else:
        print("WARNING: No backup PAPGT found — rebuild via Steam 'Verify game files'")

    print("Mod removed.")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apply/remove JSON byte-patch mod")
    sub = parser.add_subparsers(dest="command", required=True)

    apply_p = sub.add_parser("apply")
    apply_p.add_argument("mod", help="Path to mod JSON file")
    apply_p.add_argument("--game-dir", type=Path, default=DEFAULT_GAME_DIR)
    apply_p.add_argument("--dry-run", action="store_true")

    remove_p = sub.add_parser("remove")
    remove_p.add_argument("--game-dir", type=Path, default=DEFAULT_GAME_DIR)

    args = parser.parse_args()

    if args.command == "apply":
        ok = apply_mod(args.mod, args.game_dir, args.dry_run)
    else:
        ok = remove_mod(args.game_dir)

    sys.exit(0 if ok else 1)

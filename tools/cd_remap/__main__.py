"""CLI entry point for CD Controller Remapper."""
import argparse
import sys
from pathlib import Path

from . import VERSION
from .remap import (
    DEFAULT_GAME_DIR,
    ANALOG_BUTTONS,
    apply_remap,
    load_config,
    remove_remap,
    show_bindings,
    validate_swaps,
)


def cmd_apply(args):
    swaps = load_config(args.config)
    errors = validate_swaps(swaps)
    if errors:
        for e in errors:
            print(f"  ERROR: {e}")
        return 1

    analog_swaps = [s for s in swaps if s in ANALOG_BUTTONS or swaps[s] in ANALOG_BUTTONS]
    if analog_swaps:
        print("  WARNING: Swapping analog sticks also swaps their axis scaling.")

    result = apply_remap(swaps, args.game_dir, args.dry_run)
    if not result["ok"]:
        for e in result["errors"]:
            print(f"  ERROR: {e}")
        return 1

    prefix = "[DRY RUN] " if result.get("dry_run") else ""
    print(f"{prefix}Remap applied. {result['affected']} bindings changed.")
    return 0


def cmd_remove(args):
    result = remove_remap(args.game_dir)
    print(result["message"])
    return 0 if result["ok"] else 1


def cmd_show(args):
    bindings = show_bindings(args.game_dir)
    current_action = None
    for b in bindings:
        if b["action"] != current_action:
            current_action = b["action"]
            print(f"\n  {current_action}")
        print(f"    {b['key']:20s} {b['method']}")
    print(f"\n  Total: {len(bindings)} gamepad bindings")
    return 0


def cmd_interactive(args):
    from .tui import run_tui
    return run_tui(args.game_dir)


def main():
    parser = argparse.ArgumentParser(
        prog="cd_remap",
        description=f"CD Controller Remapper v{VERSION} — Crimson Desert gamepad button swap tool",
    )
    parser.add_argument("--game-dir", type=Path, default=DEFAULT_GAME_DIR)
    parser.set_defaults(func=lambda args: cmd_interactive(args))

    sub = parser.add_subparsers(dest="command")

    p_interactive = sub.add_parser("interactive", help="Launch interactive TUI")
    p_interactive.add_argument("--game-dir", type=Path, default=DEFAULT_GAME_DIR)
    p_interactive.set_defaults(func=cmd_interactive)

    p_apply = sub.add_parser("apply", help="Apply remap from JSON config")
    p_apply.add_argument("config", help="Path to remap JSON file")
    p_apply.add_argument("--game-dir", type=Path, default=DEFAULT_GAME_DIR)
    p_apply.add_argument("--dry-run", action="store_true")
    p_apply.set_defaults(func=cmd_apply)

    p_remove = sub.add_parser("remove", help="Remove remap (restore vanilla)")
    p_remove.add_argument("--game-dir", type=Path, default=DEFAULT_GAME_DIR)
    p_remove.set_defaults(func=cmd_remove)

    p_show = sub.add_parser("show", help="Show current vanilla gamepad bindings")
    p_show.add_argument("--game-dir", type=Path, default=DEFAULT_GAME_DIR)
    p_show.set_defaults(func=cmd_show)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()

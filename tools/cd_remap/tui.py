"""Minimal interactive TUI for controller remapping."""
import subprocess
import sys
from pathlib import Path

from .remap import (
    VALID_BUTTONS,
    ANALOG_BUTTONS,
    apply_remap,
    count_affected,
    extract_xml,
    remove_remap,
    validate_swaps,
)
from . import VERSION


# ANSI color helpers — graceful fallback on unsupported terminals
def _supports_ansi() -> bool:
    if not (hasattr(sys.stdout, "isatty") and sys.stdout.isatty()):
        return False
    try:
        sys.stdout.write("\033[0m")
        sys.stdout.flush()
        return True
    except Exception:
        return False

_ANSI = _supports_ansi()

def _green(s: str) -> str:
    return f"\033[32m{s}\033[0m" if _ANSI else s

def _yellow(s: str) -> str:
    return f"\033[33m{s}\033[0m" if _ANSI else s

def _red(s: str) -> str:
    return f"\033[31m{s}\033[0m" if _ANSI else s

def _bold(s: str) -> str:
    return f"\033[1m{s}\033[0m" if _ANSI else s

def _dim(s: str) -> str:
    return f"\033[2m{s}\033[0m" if _ANSI else s


BUTTON_ORDER = [
    "buttonA", "buttonB", "buttonX", "buttonY",
    "buttonLB", "buttonRB", "buttonLT", "buttonRT",
    "buttonLS", "buttonRS", "leftstick", "rightstick",
    "padU", "padD", "padL", "padR", "select", "start",
]

BUTTON_DISPLAY = {
    "buttonA": "A", "buttonB": "B", "buttonX": "X", "buttonY": "Y",
    "buttonLB": "LB", "buttonRB": "RB", "buttonLT": "LT", "buttonRT": "RT",
    "buttonLS": "LS", "buttonRS": "RS", "leftstick": "L-Stick", "rightstick": "R-Stick",
    "padU": "D-Up", "padD": "D-Down", "padL": "D-Left", "padR": "D-Right",
    "select": "Select", "start": "Start",
}


def _clear():
    subprocess.run(["cmd", "/c", "cls"], shell=False)


def _print_header():
    print(_bold(f"CD Controller Remapper v{VERSION}"))
    print("=" * 38)
    print()


def _print_buttons(swaps: dict[str, str]):
    print("  Buttons:")
    for i, btn in enumerate(BUTTON_ORDER):
        num = f"[{i + 1:>2}]"
        display = BUTTON_DISPLAY[btn]
        if btn in swaps:
            target = BUTTON_DISPLAY[swaps[btn]]
            label = f"{display} -> {_green(target)}"
        else:
            label = _dim(display)
        end = "\n" if (i + 1) % 4 == 0 else ""
        print(f"  {num} {label:22s}", end=end)
    if len(BUTTON_ORDER) % 4 != 0:
        print()
    print()


def _print_swaps(swaps: dict[str, str]):
    if not swaps:
        print("  Pending swaps: " + _dim("(none)"))
    else:
        print("  Pending swaps:")
        seen = set()
        for src, tgt in swaps.items():
            pair = tuple(sorted([src, tgt]))
            if pair not in seen:
                seen.add(pair)
                print(f"    {BUTTON_DISPLAY[src]} <-> {BUTTON_DISPLAY[tgt]}")
    print()


def _pick_button(prompt: str, exclude: set[str] | None = None) -> str | None:
    """Show button list, return selected button name or None for cancel."""
    available = [b for b in BUTTON_ORDER if b not in (exclude or set())]
    print(f"  {prompt}")
    for i, btn in enumerate(available):
        print(f"    [{i + 1:>2}] {BUTTON_DISPLAY[btn]}")
    print(f"    [ 0] Cancel")
    print()

    while True:
        try:
            choice = input("  > ").strip()
            if choice == "0" or choice.lower() == "q":
                return None
            idx = int(choice) - 1
            if 0 <= idx < len(available):
                return available[idx]
            print(_red("  Invalid choice."))
        except (ValueError, EOFError):
            return None


def _add_swap(swaps: dict[str, str]):
    already_swapped = set(swaps.keys())
    src = _pick_button("Swap which button?", exclude=already_swapped)
    if src is None:
        return

    tgt = _pick_button(f"Swap {BUTTON_DISPLAY[src]} to?", exclude=already_swapped | {src})
    if tgt is None:
        return

    if src in ANALOG_BUTTONS or tgt in ANALOG_BUTTONS:
        print(_yellow("  Warning: Swapping analog sticks also swaps axis scaling."))
        confirm = input("  Continue? [y/N] ").strip().lower()
        if confirm != "y":
            return

    swaps[src] = tgt
    swaps[tgt] = src
    print(_green(f"  Added: {BUTTON_DISPLAY[src]} <-> {BUTTON_DISPLAY[tgt]}"))


def _remove_swap(swaps: dict[str, str]):
    if not swaps:
        print(_dim("  No swaps to remove."))
        return

    pairs = []
    seen = set()
    for src, tgt in swaps.items():
        pair = tuple(sorted([src, tgt]))
        if pair not in seen:
            seen.add(pair)
            pairs.append((src, tgt))

    print("  Remove which swap?")
    for i, (src, tgt) in enumerate(pairs):
        print(f"    [{i + 1}] {BUTTON_DISPLAY[src]} <-> {BUTTON_DISPLAY[tgt]}")
    print(f"    [0] Cancel")

    try:
        choice = input("  > ").strip()
        if choice == "0":
            return
        idx = int(choice) - 1
        if 0 <= idx < len(pairs):
            src, tgt = pairs[idx]
            del swaps[src]
            del swaps[tgt]
            print(_green(f"  Removed: {BUTTON_DISPLAY[src]} <-> {BUTTON_DISPLAY[tgt]}"))
    except (ValueError, IndexError, EOFError):
        pass


def _view_affected(swaps: dict[str, str], game_dir: Path):
    if not swaps:
        print(_dim("  No swaps configured."))
        return
    try:
        xml = extract_xml(game_dir)
        n = count_affected(xml, swaps)
        print(f"  {n} gamepad bindings would be changed.")
    except Exception as e:
        print(_red(f"  Error reading game files: {e}"))


def _apply_swaps(swaps: dict[str, str], game_dir: Path):
    if not swaps:
        print(_dim("  No swaps to apply."))
        return

    errors = validate_swaps(swaps)
    if errors:
        for e in errors:
            print(_red(f"  {e}"))
        return

    print("  Applying remap...")
    result = apply_remap(swaps, game_dir)
    if result["ok"]:
        print(_green(f"  Done! {result['affected']} bindings remapped."))
        print(_dim("  Launch the game to test."))
    else:
        for e in result.get("errors", []):
            print(_red(f"  {e}"))


def _undo_all(game_dir: Path):
    confirm = input("  Remove all remaps and restore vanilla? [y/N] ").strip().lower()
    if confirm != "y":
        return
    result = remove_remap(game_dir)
    if result["ok"]:
        print(_green(f"  {result['message']}"))
    else:
        print(_red(f"  {result.get('message', 'Failed')}"))


def run_tui(game_dir: Path) -> int:
    swaps: dict[str, str] = {}

    while True:
        _clear()
        _print_header()
        _print_buttons(swaps)
        _print_swaps(swaps)

        print("  [S] Add swap   [R] Remove swap   [A] Apply")
        print("  [V] View affected   [U] Undo all   [Q] Quit")
        print()

        try:
            choice = input("  > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break

        print()
        if choice == "s":
            _add_swap(swaps)
        elif choice == "r":
            _remove_swap(swaps)
        elif choice == "a":
            _apply_swaps(swaps, game_dir)
            input("\n  Press Enter to continue...")
        elif choice == "v":
            _view_affected(swaps, game_dir)
            input("\n  Press Enter to continue...")
        elif choice == "u":
            _undo_all(game_dir)
            input("\n  Press Enter to continue...")
        elif choice == "q":
            break

    return 0

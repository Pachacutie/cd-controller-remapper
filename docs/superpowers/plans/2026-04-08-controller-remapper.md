# Controller Remapper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a user-configurable gamepad button remapper for Crimson Desert that patches `ui/inputmap_common.xml` via the overlay system.

**Architecture:** Vendor minimal CDUMM subset (5 modules + 1 stub) for PAZ extraction and overlay building. Core remap logic uses regex to swap button names in `GamePad Key="..."` attributes. TUI for interactive use, CLI for scripting. PyInstaller exe for Nexus distribution.

**Tech Stack:** Python 3.12, vendored CDUMM (MIT), `cryptography` + `lz4` (pip), PyInstaller for exe.

**Spec:** `docs/superpowers/specs/2026-04-08-controller-remapper-design.md`

---

## File Structure

```
tools/cd_remap/
├── __init__.py             # Version constant
├── __main__.py             # CLI entry — argparse, dispatches to remap/tui
├── remap.py                # Core logic — extract, swap, overlay build/remove
├── tui.py                  # Interactive mode — menus, ANSI colors
└── vendor/
    ├── __init__.py          # Source attribution (CDUMM commit, date)
    ├── paz_parse.py         # PAMT index parsing → PazEntry list
    ├── paz_crypto.py        # ChaCha20 decrypt/encrypt, LZ4 compress/decompress
    ├── overlay_builder.py   # Build PAZ+PAMT overlay from patched files
    ├── papgt_manager.py     # Rebuild PAPGT hash registry
    └── hashlittle.py        # Hash function used by overlay_builder + papgt_manager

tests/
└── test_remap.py           # Unit tests for swap logic + validation

remap_example.json          # Sample config
build/
└── build_exe.py            # PyInstaller build script
```

---

### Task 1: Create feature branch and vendor CDUMM subset

**Files:**
- Create: `tools/cd_remap/__init__.py`
- Create: `tools/cd_remap/vendor/__init__.py`
- Create: `tools/cd_remap/vendor/paz_parse.py`
- Create: `tools/cd_remap/vendor/paz_crypto.py`
- Create: `tools/cd_remap/vendor/overlay_builder.py`
- Create: `tools/cd_remap/vendor/papgt_manager.py`
- Create: `tools/cd_remap/vendor/hashlittle.py`

- [ ] **Step 1: Create feature branch**

```bash
cd D:/Games/Workshop/CRIMSON_DESERT
git checkout -b feat/controller-remap
```

- [ ] **Step 2: Create package init**

Create `tools/cd_remap/__init__.py`:

```python
VERSION = "1.0.0"
```

- [ ] **Step 3: Vendor CDUMM modules**

Copy these 5 files from `D:/Games/Modding/Tools/CDUMM/src/cdumm/archive/` to `tools/cd_remap/vendor/`:

```bash
cp D:/Games/Modding/Tools/CDUMM/src/cdumm/archive/paz_parse.py tools/cd_remap/vendor/
cp D:/Games/Modding/Tools/CDUMM/src/cdumm/archive/paz_crypto.py tools/cd_remap/vendor/
cp D:/Games/Modding/Tools/CDUMM/src/cdumm/archive/overlay_builder.py tools/cd_remap/vendor/
cp D:/Games/Modding/Tools/CDUMM/src/cdumm/archive/papgt_manager.py tools/cd_remap/vendor/
cp D:/Games/Modding/Tools/CDUMM/src/cdumm/archive/hashlittle.py tools/cd_remap/vendor/
```

- [ ] **Step 4: Fix imports in vendored files**

In each vendored file, replace `cdumm.archive.` imports with relative imports:

**overlay_builder.py** — change:
```python
from cdumm.archive.hashlittle import hashlittle
from cdumm.archive.paz_repack import fix_dds_header
```
to:
```python
from .hashlittle import hashlittle
```
Remove the `fix_dds_header` import entirely. Find where it's called (inside `if header[:4] == b"DDS ":` block) and replace the call with `pass` since we never patch DDS files:
```python
if header[:4] == b"DDS ":
    pass  # DDS header fixup not needed for XML mods
```

Also fix the lazy import of `parse_pamt` inside `_build_full_path_map`:
```python
from cdumm.archive.paz_parse import parse_pamt
```
to:
```python
from .paz_parse import parse_pamt
```

**papgt_manager.py** — change:
```python
from cdumm.archive.hashlittle import compute_pamt_hash, compute_papgt_hash
```
to:
```python
from .hashlittle import compute_pamt_hash, compute_papgt_hash
```

**paz_parse.py** and **paz_crypto.py** — no cdumm imports, no changes needed.

**hashlittle.py** — no cdumm imports, no changes needed.

- [ ] **Step 5: Create vendor __init__.py**

Create `tools/cd_remap/vendor/__init__.py`:

```python
"""Vendored subset of CDUMM (MIT license).

Source: https://github.com/XeNTaXBackup/CDUMM
Commit: 922c5c8 (v2.2.0)
Vendored: 2026-04-08

Only the modules needed for PAZ extraction and overlay building.
fix_dds_header from paz_repack.py is stubbed out (not needed for XML mods).
"""
```

- [ ] **Step 6: Verify vendored imports work**

```bash
cd D:/Games/Workshop/CRIMSON_DESERT
python -c "
import sys; sys.path.insert(0, 'tools')
from cd_remap.vendor.paz_parse import parse_pamt, PazEntry
from cd_remap.vendor.paz_crypto import decrypt, lz4_decompress, encrypt, lz4_compress
from cd_remap.vendor.overlay_builder import build_overlay
from cd_remap.vendor.papgt_manager import PapgtManager
print('All vendor imports OK')
"
```

Expected: `All vendor imports OK`

- [ ] **Step 7: Commit**

```bash
git add tools/cd_remap/
git commit -m "chore: vendor CDUMM subset for controller remapper

Vendored from CDUMM 922c5c8 (v2.2.0, MIT license).
5 modules: paz_parse, paz_crypto, overlay_builder, papgt_manager, hashlittle.
paz_repack stubbed out (fix_dds_header not needed for XML mods)."
```

---

### Task 2: Core remap logic — extraction and swap

**Files:**
- Create: `tools/cd_remap/remap.py`
- Create: `tests/test_remap.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write failing tests for swap logic**

Create `tests/test_remap.py`:

```python
"""Tests for controller remap core logic."""
import pytest


VALID_BUTTONS = [
    "buttonA", "buttonB", "buttonX", "buttonY",
    "buttonLB", "buttonRB", "buttonLT", "buttonRT",
    "buttonLS", "buttonRS", "leftstick", "rightstick",
    "padU", "padD", "padL", "padR", "select", "start",
]


# --- Swap validation ---

class TestValidateSwaps:
    def test_valid_swap(self):
        from cd_remap.remap import validate_swaps
        errors = validate_swaps({"buttonA": "buttonB", "buttonB": "buttonA"})
        assert errors == []

    def test_unknown_source(self):
        from cd_remap.remap import validate_swaps
        errors = validate_swaps({"fakeButton": "buttonA"})
        assert any("fakeButton" in e for e in errors)

    def test_unknown_target(self):
        from cd_remap.remap import validate_swaps
        errors = validate_swaps({"buttonA": "fakeButton"})
        assert any("fakeButton" in e for e in errors)

    def test_self_swap(self):
        from cd_remap.remap import validate_swaps
        errors = validate_swaps({"buttonA": "buttonA"})
        assert any("self" in e.lower() for e in errors)

    def test_duplicate_target(self):
        from cd_remap.remap import validate_swaps
        errors = validate_swaps({"buttonA": "buttonX", "buttonB": "buttonX"})
        assert any("duplicate" in e.lower() or "target" in e.lower() for e in errors)


# --- Applying swaps to XML content ---

class TestApplySwaps:
    def test_simple_swap(self):
        from cd_remap.remap import apply_swaps
        xml = b'<GamePad Key="buttonA" Method="downonce"/>'
        result = apply_swaps(xml, {"buttonA": "buttonB", "buttonB": "buttonA"})
        assert b'Key="buttonB"' in result

    def test_reverse_swap(self):
        from cd_remap.remap import apply_swaps
        xml = b'<GamePad Key="buttonB" Method="press"/>'
        result = apply_swaps(xml, {"buttonA": "buttonB", "buttonB": "buttonA"})
        assert b'Key="buttonA"' in result

    def test_simultaneous_no_chain(self):
        """A->B and B->A must not chain into A->A."""
        from cd_remap.remap import apply_swaps
        xml = (
            b'<GamePad Key="buttonA" Method="downonce"/>\n'
            b'<GamePad Key="buttonB" Method="press"/>'
        )
        result = apply_swaps(xml, {"buttonA": "buttonB", "buttonB": "buttonA"})
        assert b'Key="buttonB" Method="downonce"' in result
        assert b'Key="buttonA" Method="press"' in result

    def test_combo_key_swap(self):
        """Swaps inside multi-button combo keys."""
        from cd_remap.remap import apply_swaps
        xml = b'<GamePad Key="select buttonA" Method="press"/>'
        result = apply_swaps(xml, {"buttonA": "buttonB", "buttonB": "buttonA"})
        assert b'Key="select buttonB"' in result

    def test_no_partial_match(self):
        """buttonA must not match inside buttonAB (hypothetical)."""
        from cd_remap.remap import apply_swaps
        xml = b'<GamePad Key="buttonAB" Method="downonce"/>'
        result = apply_swaps(xml, {"buttonA": "buttonB"})
        assert b'Key="buttonAB"' in result  # unchanged

    def test_unswapped_buttons_untouched(self):
        from cd_remap.remap import apply_swaps
        xml = b'<GamePad Key="buttonX" Method="downonce"/>'
        result = apply_swaps(xml, {"buttonA": "buttonB", "buttonB": "buttonA"})
        assert b'Key="buttonX"' in result

    def test_preserves_non_gamepad_content(self):
        from cd_remap.remap import apply_swaps
        xml = b'<Input Name="Attack">\n\t<GamePad Key="buttonA" Method="downonce"/>\n</>'
        result = apply_swaps(xml, {"buttonA": "buttonB", "buttonB": "buttonA"})
        assert b'<Input Name="Attack">' in result
        assert b'</>' in result


# --- Counting affected entries ---

class TestCountAffected:
    def test_counts_affected(self):
        from cd_remap.remap import count_affected
        xml = (
            b'<GamePad Key="buttonA" Method="downonce"/>\n'
            b'<GamePad Key="buttonB" Method="press"/>\n'
            b'<GamePad Key="buttonX" Method="release"/>'
        )
        count = count_affected(xml, {"buttonA": "buttonB", "buttonB": "buttonA"})
        assert count == 2

    def test_zero_affected(self):
        from cd_remap.remap import count_affected
        xml = b'<GamePad Key="buttonX" Method="downonce"/>'
        count = count_affected(xml, {"buttonA": "buttonB", "buttonB": "buttonA"})
        assert count == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd D:/Games/Workshop/CRIMSON_DESERT
python -m pytest tests/test_remap.py -v
```

Expected: All tests FAIL with `ModuleNotFoundError: No module named 'cd_remap'`

- [ ] **Step 3: Create conftest.py for import resolution**

Create `tests/conftest.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
```

- [ ] **Step 4: Implement remap.py**

Create `tools/cd_remap/remap.py`:

```python
"""Core remap logic — extract, swap, rebuild overlay."""
import json
import re
import shutil
from pathlib import Path

from .vendor.paz_parse import parse_pamt
from .vendor.paz_crypto import decrypt, lz4_decompress, encrypt, lz4_compress
from .vendor.overlay_builder import build_overlay
from .vendor.papgt_manager import PapgtManager

TARGET_FILE = "ui/inputmap_common.xml"
PAZ_FOLDER = "0012"

VALID_BUTTONS = frozenset([
    "buttonA", "buttonB", "buttonX", "buttonY",
    "buttonLB", "buttonRB", "buttonLT", "buttonRT",
    "buttonLS", "buttonRS", "leftstick", "rightstick",
    "padU", "padD", "padL", "padR", "select", "start",
])

ANALOG_BUTTONS = frozenset(["leftstick", "rightstick"])

# Matches the Key="..." value inside GamePad elements
_KEY_ATTR_RE = re.compile(rb'(<GamePad\b[^>]*\bKey=")([^"]+)(")')

DEFAULT_GAME_DIR = Path("D:/Games/SteamLibrary/steamapps/common/Crimson Desert")
BACKUP_DIR = Path("D:/Games/Modding/Crimson Desert/BACKUP_PRISTINE")


def validate_swaps(swaps: dict[str, str]) -> list[str]:
    """Return list of error strings. Empty list = valid."""
    errors = []
    for src, tgt in swaps.items():
        if src not in VALID_BUTTONS:
            errors.append(f"Unknown source button: {src}")
        if tgt not in VALID_BUTTONS:
            errors.append(f"Unknown target button: {tgt}")
        if src == tgt:
            errors.append(f"Self-swap not allowed: {src} -> {tgt}")

    targets = list(swaps.values())
    seen = set()
    for t in targets:
        if t in seen:
            errors.append(f"Duplicate target: {t} (two buttons mapped to same target)")
        seen.add(t)

    return errors


def apply_swaps(xml_bytes: bytes, swaps: dict[str, str]) -> bytes:
    """Apply button swaps to all GamePad Key attributes. Simultaneous replacement."""
    # Build swap table with placeholder intermediaries to prevent chaining
    placeholders = {src: f"\x00SWAP_{i}\x00" for i, src in enumerate(swaps)}

    def replace_key(match: re.Match) -> bytes:
        prefix = match.group(1)
        key_val = match.group(2).decode("utf-8")
        suffix = match.group(3)

        # Phase 1: replace source buttons with placeholders
        for src, ph in placeholders.items():
            key_val = re.sub(rf'\b{re.escape(src)}\b', ph, key_val)

        # Phase 2: replace placeholders with targets
        for src, ph in placeholders.items():
            key_val = key_val.replace(ph, swaps[src])

        return prefix + key_val.encode("utf-8") + suffix

    return _KEY_ATTR_RE.sub(replace_key, xml_bytes)


def count_affected(xml_bytes: bytes, swaps: dict[str, str]) -> int:
    """Count how many GamePad entries would be changed by the swap config."""
    count = 0
    for match in _KEY_ATTR_RE.finditer(xml_bytes):
        key_val = match.group(2).decode("utf-8")
        for src in swaps:
            if re.search(rf'\b{re.escape(src)}\b', key_val):
                count += 1
                break
    return count


def extract_xml(game_dir: Path = DEFAULT_GAME_DIR) -> bytes:
    """Extract and decrypt ui/inputmap_common.xml from PAZ 0012."""
    paz_dir = game_dir / PAZ_FOLDER
    entries = parse_pamt(str(paz_dir / "0.pamt"), str(paz_dir))
    entry = next((e for e in entries if e.path == TARGET_FILE), None)
    if entry is None:
        raise FileNotFoundError(f"{TARGET_FILE} not found in PAZ folder {PAZ_FOLDER}")

    with open(entry.paz_file, "rb") as f:
        f.seek(entry.offset)
        raw = f.read(entry.comp_size)

    if entry.encrypted:
        raw = decrypt(raw, entry.path)
    if entry.compressed:
        raw = lz4_decompress(raw, entry.orig_size)

    return raw


def apply_remap(
    swaps: dict[str, str],
    game_dir: Path = DEFAULT_GAME_DIR,
    dry_run: bool = False,
) -> dict:
    """Extract XML, apply swaps, build overlay. Returns summary dict."""
    errors = validate_swaps(swaps)
    if errors:
        return {"ok": False, "errors": errors}

    xml = extract_xml(game_dir)
    affected = count_affected(xml, swaps)
    patched = apply_swaps(xml, swaps)

    if dry_run:
        return {"ok": True, "affected": affected, "dry_run": True}

    # Backup PAPGT
    papgt_path = game_dir / "meta" / "0.papgt"
    backup_papgt = BACKUP_DIR / "meta" / "0.papgt"
    if not backup_papgt.exists():
        backup_papgt.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(papgt_path, backup_papgt)

    # Re-encrypt and compress for overlay
    compressed = lz4_compress(patched)
    encrypted = encrypt(compressed, TARGET_FILE)

    overlay_input = [(
        encrypted,
        {
            "entry_path": TARGET_FILE,
            "compression_type": 2,  # LZ4
            "pamt_dir": PAZ_FOLDER,
            "decomp_size": len(patched),
        },
    )]

    # If existing overlay has other entries (e.g., sleep mod in 0014), preserve them
    overlay_dir = game_dir / "0036"
    existing_entries = _read_existing_overlay(overlay_dir, game_dir) if overlay_dir.exists() else []

    # Remove any previous remap entry, keep others
    existing_entries = [e for e in existing_entries if e[1].get("entry_path") != TARGET_FILE]
    all_entries = existing_entries + overlay_input

    paz_bytes, pamt_bytes = build_overlay(all_entries, game_dir=str(game_dir))

    overlay_dir.mkdir(exist_ok=True)
    (overlay_dir / "0.paz").write_bytes(paz_bytes)
    (overlay_dir / "0.pamt").write_bytes(pamt_bytes)

    papgt_mgr = PapgtManager(game_dir)
    papgt_bytes = papgt_mgr.rebuild(modified_pamts={"0036": pamt_bytes})
    papgt_path.write_bytes(papgt_bytes)

    return {"ok": True, "affected": affected, "dry_run": False}


def remove_remap(game_dir: Path = DEFAULT_GAME_DIR) -> dict:
    """Remove the remap entry from the overlay. Preserve other mod entries."""
    overlay_dir = game_dir / "0036"
    if not overlay_dir.exists():
        return {"ok": True, "message": "No overlay to remove."}

    existing = _read_existing_overlay(overlay_dir, game_dir)
    remaining = [e for e in existing if e[1].get("entry_path") != TARGET_FILE]

    if not remaining:
        # No other mods — remove overlay entirely, restore PAPGT
        shutil.rmtree(overlay_dir)
        backup_papgt = BACKUP_DIR / "meta" / "0.papgt"
        if backup_papgt.exists():
            shutil.copy2(backup_papgt, game_dir / "meta" / "0.papgt")
        return {"ok": True, "message": "Overlay removed, vanilla PAPGT restored."}

    # Rebuild overlay without the remap entry
    paz_bytes, pamt_bytes = build_overlay(remaining, game_dir=str(game_dir))
    (overlay_dir / "0.paz").write_bytes(paz_bytes)
    (overlay_dir / "0.pamt").write_bytes(pamt_bytes)

    papgt_mgr = PapgtManager(game_dir)
    papgt_bytes = papgt_mgr.rebuild(modified_pamts={"0036": pamt_bytes})
    (game_dir / "meta" / "0.papgt").write_bytes(papgt_bytes)

    return {"ok": True, "message": "Remap removed. Other overlay entries preserved."}


def show_bindings(game_dir: Path = DEFAULT_GAME_DIR) -> list[dict]:
    """Extract current vanilla bindings. Returns list of {action, button, method}."""
    xml = extract_xml(game_dir)
    bindings = []
    input_re = re.compile(rb'<Input\s+Name="([^"]+)"')
    gamepad_re = re.compile(rb'<GamePad\s+Key="([^"]+)"\s+Method="([^"]+)"')

    current_action = "unknown"
    for line in xml.split(b"\n"):
        m = input_re.search(line)
        if m:
            current_action = m.group(1).decode("utf-8")
        m = gamepad_re.search(line)
        if m:
            bindings.append({
                "action": current_action,
                "key": m.group(1).decode("utf-8"),
                "method": m.group(2).decode("utf-8"),
            })
    return bindings


def load_config(path: str) -> dict[str, str]:
    """Load remap config JSON. Returns the swaps dict."""
    with open(path) as f:
        data = json.load(f)
    return data.get("swaps", {})


def _read_existing_overlay(overlay_dir: Path, game_dir: Path) -> list[tuple[bytes, dict]]:
    """Read existing overlay entries so we can preserve them during rebuild."""
    pamt_path = overlay_dir / "0.pamt"
    paz_path = overlay_dir / "0.paz"
    if not pamt_path.exists() or not paz_path.exists():
        return []

    entries = parse_pamt(str(pamt_path), str(overlay_dir))
    result = []
    with open(paz_path, "rb") as f:
        for entry in entries:
            f.seek(entry.offset)
            data = f.read(entry.comp_size)
            result.append((
                data,
                {
                    "entry_path": entry.path,
                    "compression_type": entry.compression_type,
                    "pamt_dir": entry.path.split("/")[0] if "/" in entry.path else PAZ_FOLDER,
                    "decomp_size": entry.orig_size,
                },
            ))
    return result
```

- [ ] **Step 5: Run tests**

```bash
cd D:/Games/Workshop/CRIMSON_DESERT
python -m pytest tests/test_remap.py -v
```

Expected: All 11 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add tools/cd_remap/remap.py tests/
git commit -m "feat: core remap logic — extract, swap, overlay build

Validates button names, applies simultaneous swaps via regex,
builds/merges overlay, preserves existing mod entries.
11 unit tests for swap logic and validation."
```

---

### Task 3: CLI entry point

**Files:**
- Create: `tools/cd_remap/__main__.py`

- [ ] **Step 1: Implement CLI**

Create `tools/cd_remap/__main__.py`:

```python
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
```

- [ ] **Step 2: Smoke test CLI help**

```bash
cd D:/Games/Workshop/CRIMSON_DESERT/tools
python -m cd_remap --help
python -m cd_remap apply --help
```

Expected: Help text printed for each command.

- [ ] **Step 3: Commit**

```bash
git add tools/cd_remap/__main__.py
git commit -m "feat: CLI entry point — apply, remove, show, interactive"
```

---

### Task 4: TUI interactive mode

**Files:**
- Create: `tools/cd_remap/tui.py`

- [ ] **Step 1: Implement TUI**

Create `tools/cd_remap/tui.py`:

```python
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
    # Enable VT processing on Windows 10+ by writing an escape sequence
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
```

- [ ] **Step 2: Manual smoke test**

```bash
cd D:/Games/Workshop/CRIMSON_DESERT/tools
python -m cd_remap interactive --game-dir "D:/Games/SteamLibrary/steamapps/common/Crimson Desert"
```

Verify: TUI displays, buttons listed, can navigate menus, Q quits cleanly.

- [ ] **Step 3: Commit**

```bash
git add tools/cd_remap/tui.py
git commit -m "feat: interactive TUI — add/remove swaps, preview, apply, undo"
```

---

### Task 5: Example config and distribution prep

**Files:**
- Create: `remap_example.json`
- Create: `build/build_exe.py`
- Create/modify: `.gitignore`

- [ ] **Step 1: Create example remap config**

Create `remap_example.json`:

```json
{
  "swaps": {
    "buttonA": "buttonB",
    "buttonB": "buttonA"
  }
}
```

- [ ] **Step 2: Create PyInstaller build script**

Create `build/build_exe.py`:

```python
"""Build single-file exe with PyInstaller.

Usage:
    pip install pyinstaller
    python build/build_exe.py
"""
import PyInstaller.__main__
from pathlib import Path

ROOT = Path(__file__).parent.parent

PyInstaller.__main__.run([
    str(ROOT / "tools" / "cd_remap" / "__main__.py"),
    "--name", "cd_remap",
    "--onefile",
    "--console",
    "--distpath", str(ROOT / "dist"),
    "--workpath", str(ROOT / "build" / "pyinstaller_work"),
    "--specpath", str(ROOT / "build"),
    "--clean",
])
```

- [ ] **Step 3: Add build artifacts to .gitignore**

Append to `.gitignore` (create if missing):

```
dist/
build/pyinstaller_work/
build/*.spec
*.pyc
__pycache__/
inputmap_common.xml
extract_inputmap.py
```

- [ ] **Step 4: Commit**

```bash
git add remap_example.json build/build_exe.py .gitignore
git commit -m "chore: example config, PyInstaller build script, gitignore"
```

---

### Task 6: End-to-end integration test

**Files:**
- Modify: `tests/test_remap.py`

- [ ] **Step 1: Add integration test**

Append to `tests/test_remap.py`:

```python
import os

# --- Integration: extract + swap + verify ---

@pytest.mark.skipif(
    not os.path.exists("D:/Games/SteamLibrary/steamapps/common/Crimson Desert/0012/0.pamt"),
    reason="Game not installed",
)
class TestIntegration:
    def test_extract_and_swap_roundtrip(self):
        from cd_remap.remap import extract_xml, apply_swaps, count_affected

        xml = extract_xml()
        assert len(xml) > 200000  # ~220KB
        assert b"GamePad" in xml

        swaps = {"buttonA": "buttonB", "buttonB": "buttonA"}
        affected = count_affected(xml, swaps)
        assert affected > 0  # should be 200+

        patched = apply_swaps(xml, swaps)
        assert len(patched) == len(xml)  # same size — no bytes added/removed

        # After swapping A<->B, applying the same swap again should affect same count
        re_affected = count_affected(patched, swaps)
        assert re_affected == affected

    def test_dry_run(self):
        from cd_remap.remap import apply_remap

        result = apply_remap(
            {"buttonA": "buttonB", "buttonB": "buttonA"},
            dry_run=True,
        )
        assert result["ok"]
        assert result["dry_run"]
        assert result["affected"] > 0
```

- [ ] **Step 2: Run all tests**

```bash
cd D:/Games/Workshop/CRIMSON_DESERT
python -m pytest tests/ -v
```

Expected: All unit tests PASS. Integration tests PASS (game is installed on this machine).

- [ ] **Step 3: Commit**

```bash
git add tests/test_remap.py
git commit -m "test: integration tests — extract, swap roundtrip, dry run"
```

---

### Task 7: Update spec and project docs

**Files:**
- Modify: `docs/superpowers/specs/2026-04-08-controller-remapper-design.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update spec — vendor count correction**

In the design spec, replace the "Vendored CDUMM Subset" table with:

```markdown
| Module | Purpose |
|---|---|
| `paz_parse.py` | PAMT index parsing, file entry lookup |
| `paz_crypto.py` | ChaCha20 decryption/encryption, LZ4 compress/decompress |
| `overlay_builder.py` | PAZ/PAMT overlay construction |
| `papgt_manager.py` | PAPGT hash registry rebuild |
| `hashlittle.py` | Hash function (dep of overlay_builder + papgt_manager) |

Note: `paz_repack.fix_dds_header` stubbed out (not needed for XML mods).
Third-party pip deps: `cryptography`, `lz4` (bundled in PyInstaller exe).
```

- [ ] **Step 2: Update CLAUDE.md active projects table**

Update the CRIMSON_DESERT entry to reflect controller remapper status once it ships.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-04-08-controller-remapper-design.md CLAUDE.md
git commit -m "docs: update spec with vendor correction, update project status"
```

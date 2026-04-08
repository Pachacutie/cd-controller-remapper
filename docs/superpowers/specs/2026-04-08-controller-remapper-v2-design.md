# Controller Remapper v2.0 — Design Spec

**Date:** 2026-04-08
**Project:** CRIMSON_DESERT
**Author:** LUDUS
**Status:** Draft
**Supersedes:** `2026-04-08-controller-remapper-design.md` (v1.0)

---

## Overview

v2.0 replaces the text-based TUI with a Dear PyGui GUI featuring an interactive controller diagram. Users click buttons on a visual gamepad to create swaps. Adds built-in presets, saveable profiles, and simplified per-context remapping (Gameplay / Menus / All).

The core remap engine (extract XML, regex swap, overlay build) is unchanged from v1.0.

---

## Target File (unchanged)

| Property | Value |
|---|---|
| Path in PAMT | `ui/inputmap_common.xml` |
| PAZ folder | `0012` |
| Encryption | ChaCha20 (key derived from filename) |
| Compression | LZ4 (type 2) |
| Decompressed size | ~220 KB, 4813 lines |
| `<Input>` blocks | 928 |
| `<GamePad>` entries | 1254 |

---

## File Structure

```
tools/cd_remap/
├── __init__.py            # VERSION = "2.0.0"
├── __main__.py            # Entry: launch GUI (default) or CLI/TUI
├── remap.py               # Core logic — extract, swap, overlay (extended for contexts)
├── contexts.py            # Layer→context mapping, context-aware filtering
├── presets.py             # Built-in presets + profile save/load/delete
├── gui.py                 # Dear PyGui main window, layout, callbacks
├── controller_draw.py     # Drawlist controller rendering + hit zones
├── tui.py                 # KEPT as --tui fallback
└── vendor/                # (unchanged — CDUMM subset)

profiles/                  # Saved user profiles (JSON), sibling to tools/
build/
└── build_exe.py           # PyInstaller build script (updated for dearpygui)
tests/
├── conftest.py
├── test_remap.py          # Existing 17 tests (unchanged)
├── test_contexts.py       # Context mapping + filtering tests
└── test_presets.py        # Preset loading + profile CRUD tests
```

---

## GUI Layout

Single window, 800x550, dark theme. Three regions: left sidebar, center controller + swap list, bottom action bar.

```
┌──────────────────────────────────────────────────────────┐
│  CD Controller Remapper v2.0                      [—][×] │
├─────────────┬────────────────────────────────────────────┤
│             │                                            │
│  PRESETS    │   ┌──────── CONTROLLER ─────────┐          │
│             │   │                             │          │
│  Soulslike  │   │    [LB]            [RB]     │  Context │
│  Southpaw   │   │   [LT]              [RT]   │          │
│  Triggers   │   │                             │  (●) All │
│  ────────── │   │     ◎     [Y]               │  ( ) Game│
│  PROFILES   │   │    [LS] [X] ● [B]          │  ( ) Menu│
│             │   │           [A]      ◎        │          │
│  My Config  │   │                   [RS]      │          │
│             │   │   [Sel]      [Start]        │          │
│             │   │    ✛ D-pad                  │          │
│             │   └─────────────────────────────┘          │
│             │                                            │
│             │  Active Swaps:                             │
│             │   ● A ↔ B  (All)                    [×]    │
│             │   ● X ↔ Y  (Gameplay)               [×]    │
│             │                                            │
├─────────────┴────────────────────────────────────────────┤
│  [Save] [Save As...] [Delete]    [Dry Run] [Apply] [Undo]│
│  Status: Ready — D:\Games\SteamLibrary\...\Crimson Desert│
└──────────────────────────────────────────────────────────┘
```

### Left Sidebar (~140px)

Two sections separated by a visual divider:

**Presets** — built-in, read-only. Click to load into swap grid. Highlighted if currently active.

**Profiles** — user-saved JSON files from `profiles/`. Click to load. Selected profile name shown in bold.

### Center: Interactive Controller (~450x300 drawlist)

Vector-drawn Xbox-style gamepad using Dear PyGui `drawlist` primitives (rounded rectangles, circles, lines, text). No bitmap assets — everything is code-drawn, scales to any DPI.

**18 clickable button zones** corresponding to the remappable buttons:

| Category | Buttons | Visual |
|---|---|---|
| Face | A, B, X, Y | Circles, labeled, right-center |
| Shoulder | LB, RB | Rounded rects, top |
| Trigger | LT, RT | Rounded rects, above shoulders |
| Stick click | LS, RS | Small circles inside stick outlines |
| D-pad | Up, Down, Left, Right | Cross shape, left-lower |
| Meta | Select, Start | Small rounded rects, center |

Analog sticks are drawn as larger circle outlines (showing their physical position) but the clickable target is the stick-click button inside.

**Button states and colors:**

| State | Appearance |
|---|---|
| Default (no remap) | Dim gray fill, light border |
| Hover | Brightened fill, tooltip shows top 3 actions bound to this button |
| Selected (first click) | Bright highlight, waiting for target pick |
| Swapped pair | Unique accent color per pair (pair 1 = cyan, pair 2 = orange, pair 3 = magenta, etc.) |

**Binding labels:** Small text near each button showing usage count (e.g., "A: 144" meaning 144 GamePad entries use this button). Hover tooltip shows the top 3 action names. Pulled from `show_bindings()` at startup. Labels update after remap to reflect swapped counts.

### Center: Swap Summary List

Below the controller drawing. Read-only table showing active swaps:

| Source | Target | Context | Remove |
|---|---|---|---|
| A | B | All | [×] |
| B | A | All | [×] |

- Rows are colored to match their controller button pair color
- The [×] button removes the entire bidirectional pair (both rows)
- Clicking a row selects it and highlights the pair on the controller

### Right: Context Radio Buttons

Three radio buttons controlling which context the NEXT created swap applies to:

- **All** (default) — swap applies globally to all InputGroups
- **Gameplay** — swap applies only to HUD/action layers
- **Menus** — swap applies only to menu/popup layers

Existing swaps show their context in the summary list. To change a swap's context, remove and re-add it.

### Bottom Action Bar

| Button | Action |
|---|---|
| Save | Overwrite current profile (disabled if preset or no profile loaded) |
| Save As... | Modal text input for profile name, saves to `profiles/<name>.json` |
| Delete | Delete current profile (confirm modal). Disabled for presets. |
| Dry Run | Calls `apply_remap(dry_run=True)`, shows affected count in status bar |
| Apply | Applies remap to game files. Confirm modal: "Apply N changes to game files?" |
| Undo All | Calls `remove_remap()`. Confirm modal. |

**Status bar** at the bottom: one-line status message + game directory path. Shows results of last action ("Applied: 247 bindings remapped", "Dry run: 312 bindings would change", "Error: ...").

---

## Click Flow: Creating a Swap

1. User clicks **[A]** on the controller
2. [A] highlights bright white. All other valid targets brighten slightly. Already-swapped buttons dim (unavailable).
3. User clicks **[B]** as the target
4. Both [A] and [B] turn the next pair accent color (e.g., cyan)
5. Two rows appear in the swap summary: `A → B (All)` and `B → A (All)`
6. Binding labels update to show swapped actions
7. Context was determined by the radio button state at the time of step 1

**Cancel:** Click the already-highlighted source button again, or press Escape, to cancel selection.

**Click on an already-swapped button:** Popup with two options:
- "Remove swap" — removes the bidirectional pair
- "Cancel"

(No "change target" — remove and re-add is simpler and less error-prone.)

---

## Context System

### Layer Mapping (`contexts.py`)

```python
CONTEXT_LAYERS = {
    "gameplay": {
        "UIHud_1", "UIHud_2", "UIHud_3", "UIHud_4",
        "UIHud_HighPriority", "Action", "QuickSlot",
        "QTE", "MiniGameWithAction", "GimmickInput",
    },
    "menus": {
        "UIMainMenu", "UIPopUp1", "UIPopUp2",
        "UIInfo", "UISystemPopup",
    },
}
# "all" = None (no filtering, apply everywhere)
```

The `Debug` layer is excluded from both contexts — debug bindings are never remapped.

### Context-Aware `apply_swaps()`

The existing `apply_swaps()` operates on raw XML bytes with a single regex pass. Context-aware swapping requires knowing which `InputGroup` each `GamePad` entry belongs to.

**Approach:** Parse the XML line-by-line tracking the current `InputGroup`'s `LayerName`. For each `GamePad` match, check if any swap's context includes the current layer. Apply only matching swaps.

```
For each line in XML:
    If <InputGroup LayerName="X">: set current_layer = X
    If <GamePad Key="..."]:
        For each swap:
            if swap.context == "all" OR current_layer in CONTEXT_LAYERS[swap.context]:
                apply this swap to this GamePad entry
```

This replaces the single `_KEY_ATTR_RE.sub()` call with a line-by-line pass. Still regex-based per line, but with layer awareness.

### Validation with Contexts

Swap validation is per-context:
- Two swaps with the same source button are allowed IF they target different contexts
- Within a single context, the existing rules apply: no self-swap, no duplicate targets, bidirectional pairs required
- "All" context conflicts with any other context for the same button (you can't swap A→B globally AND A→X in menus)

---

## Presets (`presets.py`)

### Built-in Presets

Three hardcoded presets, not editable:

**Soulslike:**
```json
{"swaps": [
  {"source": "buttonA", "target": "buttonB", "context": "all"},
  {"source": "buttonB", "target": "buttonA", "context": "all"},
  {"source": "buttonX", "target": "buttonY", "context": "all"},
  {"source": "buttonY", "target": "buttonX", "context": "all"}
]}
```

**Southpaw:**
```json
{"swaps": [
  {"source": "buttonLS", "target": "buttonRS", "context": "all"},
  {"source": "buttonRS", "target": "buttonLS", "context": "all"},
  {"source": "buttonLB", "target": "buttonRB", "context": "all"},
  {"source": "buttonRB", "target": "buttonLB", "context": "all"}
]}
```

**Trigger Swap:**
```json
{"swaps": [
  {"source": "buttonLT", "target": "buttonRT", "context": "all"},
  {"source": "buttonRT", "target": "buttonLT", "context": "all"},
  {"source": "buttonLB", "target": "buttonRB", "context": "all"},
  {"source": "buttonRB", "target": "buttonLB", "context": "all"}
]}
```

### Profile Format (v2)

```json
{
  "format_version": "2.0",
  "name": "My Config",
  "swaps": [
    {"source": "buttonA", "target": "buttonB", "context": "all"},
    {"source": "buttonB", "target": "buttonA", "context": "all"}
  ]
}
```

- Stored in `profiles/` directory as `<slugified-name>.json`
- `format_version` allows future migration
- v1.0 configs (flat `{"swaps": {"A": "B"}}`) are auto-migrated on load: all swaps get `"context": "all"`

### Profile Operations

| Operation | Behavior |
|---|---|
| Load preset | Populate swap grid, clear profile selection |
| Load profile | Populate swap grid, set as active profile |
| Save | Overwrite active profile JSON. Disabled if no profile loaded or preset selected. |
| Save As | Modal text input → new file in `profiles/`. Becomes active profile. |
| Delete | Confirm modal → remove JSON file. Clear swap grid. |

---

## CLI / Entry Points

```
cd_remap                     # Launch GUI (default)
cd_remap --tui               # Fallback text TUI (v1 behavior)
cd_remap apply <config.json> # CLI apply (supports v1 and v2 format)
cd_remap remove              # CLI remove remap
cd_remap show                # CLI show vanilla bindings
cd_remap --game-dir <path>   # Override game directory (all modes)
```

The GUI is the default. `--tui` is kept for systems without GPU support or SSH sessions. CLI commands are unchanged from v1.

---

## PyInstaller Build

`build/build_exe.py` updated:
- Add `--hidden-import=dearpygui` 
- Add `--collect-all=dearpygui` (bundles the DearPyGui renderer DLLs)
- Expected exe size: ~15-20MB
- GUI fallback: if `dearpygui` import fails at runtime, print a message and fall back to TUI

---

## Dependencies

| Package | Purpose | Version |
|---|---|---|
| `dearpygui` | GUI framework | >=1.11 |
| `cryptography` | ChaCha20 encrypt/decrypt | (existing) |
| `lz4` | LZ4 compress/decompress | (existing) |
| `pyinstaller` | Exe build (dev only) | >=6.0 |

---

## Testing Strategy

### Existing Tests (unchanged)

17 tests in `test_remap.py` — swap validation, apply logic, integration with real game files. These continue to validate the core engine.

### New: `test_contexts.py`

- `CONTEXT_LAYERS` covers all non-debug layers (no layer left unmapped)
- "all" context matches any layer
- "gameplay" context matches only gameplay layers
- "menus" context matches only menu layers
- Context-aware `apply_swaps()` applies correct swaps per layer
- Context-aware `apply_swaps()` with "all" matches v1 behavior exactly
- Mixed contexts: A↔B in gameplay + X↔Y in menus applied correctly
- Validation: same button in "all" + specific context = error
- Validation: same button in "gameplay" + "menus" = allowed

### New: `test_presets.py`

- Built-in presets load correctly
- Built-in presets pass validation
- Profile save/load roundtrip
- Profile save creates file in `profiles/`
- Profile delete removes file
- v1 config auto-migration adds `"context": "all"` to all swaps
- Invalid profile JSON handled gracefully
- Duplicate profile name on Save As handled (overwrite confirm or error)

### Manual Testing

1. Build PyInstaller exe
2. Run exe standalone (no Python installed) — GUI launches
3. Click controller buttons, create swaps, verify visual feedback
4. Save/load profiles
5. Apply remap with dry run — verify count
6. Apply remap to live game files
7. Launch Crimson Desert, verify remapped buttons work in-game
8. Undo remap, verify vanilla restored
9. Test `--tui` fallback

---

## Out of Scope (v2.0)

- Per-InputGroup granular remapping (only 3 simplified contexts)
- Keyboard/mouse remapping
- Combo/modifier creation
- Axis sensitivity adjustment (analog sticks swap their scaling but no tuning)
- Auto-update mechanism
- Nexus Mods API integration
- Controller vibration/haptic remapping

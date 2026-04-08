# Controller Remapper — Design Spec

**Date:** 2026-04-08
**Project:** CRIMSON_DESERT
**Author:** LUDUS
**Status:** Draft

---

## Overview

Crimson Desert has no in-game controller remapping (keyboard only). This tool lets users swap gamepad buttons via a minimal TUI or CLI, patching `ui/inputmap_common.xml` through the game's overlay system.

Existing Nexus mods (#171, #28, #592) ship hardcoded presets. This tool is user-configurable.

## Target File

| Property | Value |
|---|---|
| Path in PAMT | `ui/inputmap_common.xml` |
| PAZ folder | `0012` |
| Encryption | ChaCha20 (key derived from filename) |
| Compression | LZ4 (type 2) |
| Compressed size | 34,838 bytes |
| Decompressed size | 220,114 bytes |
| Lines | 4,813 |
| `<Input>` blocks | 928 |
| `<GamePad>` entries | 1,254 |

The file is **not well-formed XML** — uses `</>` self-closing tags and multiple top-level elements. BlackSpace engine uses a custom parser.

## Scope

**In scope:**
- Button-to-button swaps (A↔B, LB↔RB, etc.)
- Swaps applied inside multi-button combo keys (e.g., `Key="select buttonA"` → `Key="select buttonB"`)
- Single remap config (no named profiles)
- TUI interactive mode + CLI mode
- PyInstaller exe for Nexus distribution
- GitHub source release

**Out of scope:**
- Combo/modifier creation (e.g., LB+A → new action)
- Per-context remapping (combat vs. menus vs. horse)
- Multiple saved profiles
- Remapping keyboard/mouse bindings

## Remappable Buttons (18)

| Category | Buttons |
|---|---|
| Face | `buttonA`, `buttonB`, `buttonX`, `buttonY` |
| Shoulder | `buttonLB`, `buttonRB` |
| Trigger | `buttonLT`, `buttonRT` |
| Stick click | `buttonLS`, `buttonRS` |
| Analog stick | `leftstick`, `rightstick` |
| D-pad | `padU`, `padD`, `padL`, `padR` |
| Meta | `select`, `start` |

Analog sticks (`leftstick`, `rightstick`) carry `AnalogScaleX`/`AnalogScaleY` attributes. Swapping sticks also swaps their analog behavior — TUI warns about this.

## Remap Config Format

```json
{
  "swaps": {
    "buttonA": "buttonB",
    "buttonB": "buttonA"
  }
}
```

Swaps are **simultaneous** — all replacements computed before any are written, preventing chain-swaps (A→B→C). Applied via regex on `Key="..."` attribute values with word-boundary matching to avoid partial matches (e.g., `buttonA` doesn't match inside `buttonABC`).

## Core Logic (`remap.py`)

1. **Extract** `ui/inputmap_common.xml` from PAZ 0012 via vendored CDUMM (decrypt + decompress)
2. **Parse** all `GamePad Key="..."` values using regex
3. **Apply swaps** simultaneously — for each Key value, replace all occurrences of source buttons with temporary placeholders, then replace placeholders with targets
4. **Rebuild** patched XML into overlay `0036/` via `build_overlay()`
5. **Update** `meta/0.papgt` to register the overlay

Always patches from **vanilla extraction**, never from an already-patched file. Idempotent — running apply twice with the same config produces the same result.

## TUI (`tui.py`)

Minimal interactive mode. Zero pip dependencies — `input()` + ANSI escape codes.

```
CD Controller Remapper v1.0.0
─────────────────────────────

Current buttons:
  [1] buttonA    [2] buttonB    [3] buttonX    [4] buttonY
  [5] buttonLB   [6] buttonRB   [7] buttonLT   [8] buttonRT
  [9] buttonLS  [10] buttonRS  [11] leftstick  [12] rightstick
 [13] padU      [14] padD      [15] padL       [16] padR
 [17] select    [18] start

Pending swaps: (none)

[S] Add swap  [R] Remove swap  [A] Apply  [V] View affected  [U] Undo all  [Q] Quit
>
```

- **Add swap:** Pick source → pick target → auto-adds reverse (A→B implies B→A). Warns if swapping analog sticks.
- **View affected:** Shows count of affected GamePad entries and sample Input Names (e.g., "Attack", "Dodge").
- **Apply:** Extracts vanilla XML, patches, builds overlay. Shows summary of changes.
- **Remove swap:** Removes a specific swap pair.
- **Undo all:** Removes the remapper's entry from the overlay (rebuilds `0036/` without the XML file). If sleep mod is also installed, its entries are preserved. If remapper was the only mod, removes `0036/` entirely and restores vanilla PAPGT. Equivalent to CLI `remove`.

Colors: green for success, yellow for warnings, red for errors. Graceful fallback if terminal doesn't support ANSI.

## CLI (`__main__.py`)

```
cd_remap interactive                          # launch TUI
cd_remap apply remap.json [--game-dir PATH] [--dry-run]
cd_remap remove [--game-dir PATH]
cd_remap show [--game-dir PATH]              # dump current vanilla bindings
```

Running with no arguments launches the TUI.

## Project Structure

```
CRIMSON_DESERT/
├── tools/
│   └── cd_remap/
│       ├── __main__.py             # CLI entry — argparse, dispatch
│       ├── tui.py                  # Interactive mode
│       ├── remap.py                # Core logic — extract, swap, rebuild
│       └── vendor/
│           ├── __init__.py
│           ├── paz_parse.py        # From CDUMM (MIT)
│           ├── paz_crypto.py       # From CDUMM — ChaCha20 + LZ4
│           ├── overlay_builder.py  # From CDUMM
│           └── papgt_manager.py    # From CDUMM
├── remap_example.json              # Sample config (A↔B)
├── build/
│   └── build_exe.py                # PyInstaller spec
└── ...existing files...
```

## Vendored CDUMM Subset

Extracted from CDUMM (MIT license). Only the five modules needed:

| Module | Purpose |
|---|---|
| `paz_parse.py` | PAMT index parsing, file entry lookup |
| `paz_crypto.py` | ChaCha20 decryption/encryption, LZ4 compress/decompress |
| `overlay_builder.py` | PAZ/PAMT overlay construction |
| `papgt_manager.py` | PAPGT hash registry rebuild |
| `hashlittle.py` | Hash function (dep of overlay_builder + papgt_manager) |

Note: `paz_repack.fix_dds_header` stubbed out (not needed for XML mods).
Third-party pip deps: `cryptography`, `lz4` (bundled in PyInstaller exe).

Vendored copy is pinned to a specific CDUMM commit. `vendor/__init__.py` documents the source commit and date.

## Distribution

| Channel | Format | Contents |
|---|---|---|
| GitHub (Pachacutie/cd-controller-remap) | Source + releases | Full source, MIT license, README |
| Nexus Mods | Zip | `cd_remap.exe` + `remap_example.json` + `README.txt` |

PyInstaller builds a single exe (~15-20MB) bundling Python + all vendor deps.

## Safety

**Backup:** Backs up `meta/0.papgt` before first overlay write. Reuses existing backup if sleep mod already created one.

**Validation:**
- Verifies vanilla XML content matches expected structure before patching (catches game updates)
- Rejects self-swaps (`buttonA` → `buttonA`)
- Rejects duplicate sources (same button mapped to two targets)
- Rejects unknown button names (not in the 18-button list)

**Overlay merging:** If `0036/` already exists (e.g., sleep mod), reads the existing overlay and adds the new file alongside existing entries. Sleep mod targets `0014` (pastage files), remapper targets `0012` (XML) — no file conflicts.

**Game update resilience:** Unlike the sleep mod (byte-offset patches), this tool uses regex on attribute values. Minor file changes from game updates won't break it unless Pearl Abyss renames the button constants.

**Idempotency:** Always extracts from vanilla PAZ, never from overlay. Same config always produces the same output.

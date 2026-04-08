# Crimson Desert Controller Remapper

Remap your gamepad controls in Crimson Desert. The game has no built-in controller remapping — this tool patches the input bindings directly.

Instead of cryptic button swaps, you see actual game actions (Sprint, Dodge, Jump) and assign them to the buttons you want. Auto-swap ensures no two actions share a button.

## Features

- **Action-based remapping** — see game actions, not raw button IDs
- **Three context tabs** — Combat (16 actions), Menus (8), Horse (7)
- **Auto-swap** — reassigning an action automatically moves the displaced action
- **Interactive controller diagram** — click buttons or use your gamepad
- **Built-in presets** — Soulslike, Southpaw, Trigger Swap
- **Custom profiles** — save and load your own layouts
- **Safe** — patches go to the `0036/` overlay directory; vanilla files are never touched
- **Undo** — one click restores all original bindings

## Quick Start

1. Download `cd_remap.exe` from [Releases](https://github.com/Pachacutie/cd-controller-remapper/releases)
2. Run it — the GUI opens automatically
3. Pick a preset or click actions to remap them
4. Click **Apply**
5. Launch Crimson Desert

To undo: reopen the tool and click **Undo All**.

## Built-in Presets

| Preset | What it does |
|---|---|
| **Soulslike** | Sprint on B, Dodge on A, Jump on Y, Kick on X |
| **Southpaw** | Swaps stick clicks and bumpers |
| **Trigger Swap** | Swaps triggers and bumpers |

## Running from Source

Requires Python 3.12+, [Dear PyGui](https://github.com/hoffstadt/DearPyGui), and [XInput-Python](https://github.com/Zuzu-Typ/XInput-Python).

```bash
pip install dearpygui XInput-Python
cd cd-controller-remapper
python -m cd_remap --game-dir "path/to/Crimson Desert"
```

### CLI

```
cd_remap                          # Launch GUI (default)
cd_remap --tui                    # Text-based UI
cd_remap apply config.json        # Apply from JSON config
cd_remap remove                   # Restore vanilla bindings
cd_remap show                     # List current gamepad bindings
cd_remap interactive              # Launch TUI (legacy alias)
```

### Building the exe

```bash
pip install pyinstaller
python build/build_exe.py
# Output: dist/cd_remap.exe
```

## How It Works

Crimson Desert stores gamepad bindings in `inputmap_common.xml` inside PAZ archive `0008`. The tool:

1. Extracts the XML from the encrypted PAZ archive
2. Swaps `GamePad Key=` values based on your assignments
3. Writes the patched XML to the `0036/` mod overlay directory
4. The game loads `0036/` over the originals — vanilla is never modified

Undo deletes the overlay and restores the original PAPGT hash registry from backup.

## Tests

```bash
pip install pytest
python -m pytest tests/ -v    # 72 tests
```

## License

MIT

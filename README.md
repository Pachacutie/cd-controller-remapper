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
- **Safe** — backs up vanilla files before patching; undo restores originals
- **Undo** — one click restores all original bindings

## Quick Start

1. Download `cd_remap.exe` from [Releases](https://github.com/Pachacutie/cd-controller-remapper/releases)
2. **Windows SmartScreen warning:** The exe is not code-signed, so Windows will block it. To unblock: right-click `cd_remap.exe` → Properties → check **Unblock** at the bottom → OK. Then run it normally.
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
git clone https://github.com/Pachacutie/cd-controller-remapper.git
cd cd-controller-remapper
pip install -r requirements.txt
set PYTHONPATH=tools
python -m cd_remap
```

The tool auto-detects your Steam install. If it can't find the game, pass `--game-dir`:

```bash
python -m cd_remap --game-dir "D:\Steam\steamapps\common\Crimson Desert"
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

Crimson Desert has a two-layer input system. `inputmap_common.xml` provides baseline bindings (menus, HUD), while `inputmap.xml` overrides combat and character action bindings. Both live inside encrypted PAZ archive `0012`. The tool patches both files:

1. Backs up the vanilla PAZ files, PAMT index, and PAPGT hash registry
2. Extracts and decrypts both XMLs (ChaCha20 + LZ4)
3. Swaps `GamePad Key=` values based on your assignments
4. Re-compresses, re-encrypts, and patches both XMLs back into the PAZ archive
5. Updates the PAMT index and PAPGT integrity hashes

Undo restores all files from backup.

## Tests

```bash
pip install pytest
python -m pytest tests/ -v    # 98 tests
```

## License

MIT

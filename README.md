# CD_LETSLEEP — Remove Sleep Cooldown for Crimson Desert

Removes the time-gated cooldown on sleeping and resting at beds and campsites in Crimson Desert.

## What It Does

Vanilla Crimson Desert enforces a cooldown between rest interactions — you can't sleep again immediately after waking up. This mod patches the cooldown timer to zero, allowing you to rest whenever you want.

## How It Works

This is a JSON byte-patch mod for the BlackSpace Engine. It modifies specific bytes in the game's PAZ archives via an overlay system (`0036/`), so vanilla game files are never touched.

## Requirements

- Crimson Desert (Steam)
- A mod manager that supports JSON byte-patches:
  - [CDUMM](https://github.com/faisalkindi/CrimsonDesert-UltimateModsManager) (recommended)
  - [JSON Mod Manager](https://github.com/Lathiel/Crimson-Desert-JSON-Mod-Manager)

## Installation

1. Copy `mod/letmesleep.json` into your mod manager's `mods/` folder
2. Enable the mod and click **Apply**
3. Launch the game

## Uninstallation

Disable the mod in your mod manager and click **Apply**. The overlay directory is cleaned up automatically.

## License

MIT

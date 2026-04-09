# CD Controller Remapper
**IDENTITY:** LUDUS
**DIRECTORY:** D:\Games\Workshop\CD_REMAPPER\
**GAME:** Crimson Desert (Steam App ID: 3321460)
**INSTALL:** `D:\Games\SteamLibrary\steamapps\common\Crimson Desert\`
**GITHUB:** Pachacutie/cd-controller-remapper (public)

---

## What This Is

Action-based controller remapper for Crimson Desert (no in-game remapping exists). Users see game actions (Sprint, Dodge, Jump) and reassign them to controller buttons.

- Dear PyGui GUI with interactive controller diagram
- 3 context tabs: Combat (16 actions), Menus (8), Horse (7)
- Auto-swap on reassignment, Escape to cancel, hover shows action name
- 3 built-in presets (Soulslike, Southpaw, Trigger Swap)
- Custom profile save/load (v3 action-assignment format, saved to %APPDATA%/cd_remap/profiles/)
- Settings menu with game directory picker
- Auto-detects Steam install via libraryfolders.vdf
- CLI + TUI fallback
- PyInstaller exe (14MB, --windowed)
- In-place PAZ 0012 patching (ChaCha20 + LZ4, with PAMT/PAPGT integrity chain)
- Backup/restore for undo (%APPDATA%/cd_remap/backup/)
- 98 tests (96 pass + 2 skipped integration)
- BLOCKER: PyInstaller EXE corrupts PAZ files (bundled lz4/cryptography C extension mismatch). CLI/source work perfectly. Plan: `docs/superpowers/plans/2026-04-09-pyinstaller-fix.md`

---

## BlackSpace Engine (relevant context)

Proprietary (Pearl Abyss). No official mod support.

**Two-layer input system:** The engine uses two XML files for gamepad bindings:
- `inputmap_common.xml` (4,813 lines, 1,254 GamePad entries) — baseline bindings for all contexts (menus, HUD, etc.)
- `inputmap.xml` (1,278 lines, 232 GamePad entries) — player customization layer with `CustomizationGroup` definitions that override combat/character action bindings

Both files live in PAZ folder 0012 (different `.paz` files: common in 2.paz, override in 0.paz). Both must be patched for combat remapping to work.

**How remapping works:** Extract both XMLs from PAZ 0012 (ChaCha20 encrypted + LZ4 compressed), swap `GamePad Key=` values per context (InputGroup LayerName), repack (LZ4 compress → ChaCha20 encrypt → write back to PAZ 0012), update PAMT index and PAPGT hash registry. Multi-file patching in a single operation.

**Why not overlays:** The overlay VFS (`0036/`) works for `.pastage` files but NOT for input XMLs — the game either loads input maps before overlay init, or expects XML to be encrypted (overlays are never encrypted). In-place PAZ patching bypasses this.

**Vendored CDUMM modules** (`tools/cd_remap/vendor/`): PAZ parsing, decryption, repacking, PAMT patching, PAPGT rebuilding. From CDUMM v2.2.0.

**Key file details:**
- `inputmap_common.xml`: baseline — 88 InputGroups, covers all layers
- `inputmap.xml`: override — 6 InputGroups (Camera, ActionKeyByCode, Action, CharacterMove, Camera), defines CustomizationGroups for Action_Basic and Action_Battle
- Horse and Combat share UIHud_4 layer in inputmap_common
- PAZ folder `0012` contains all UI XML + textures

---

## Rules
- Backups before any game file modification
- Never commit extracted game data (PAZ, PAMT, PABG files) — .gitignore enforced
- Test mods in isolation
- Steam auto-update disabled for this game (prevents mod breakage)

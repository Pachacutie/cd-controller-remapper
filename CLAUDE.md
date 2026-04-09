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
- 72 tests (70 pass + 2 skipped integration)

---

## BLOCKER: Overlay patching does NOT work for inputmap_common.xml

The overlay VFS (`0036/`) works for `.pastage` files (sleep mod) but the game does NOT load `inputmap_common.xml` from overlays. Likely loaded before VFS overlay system initializes.

**Next approach:** In-place PAZ patching — modify the vanilla PAZ 0012 directly.
- Research CDUMM's `paz_repack.py` at `D:\Games\Modding\Tools\CDUMM\src\cdumm\archive\paz_repack.py`
- Extract XML → swap buttons → encrypt (ChaCha20) → compress (LZ4) → write back to PAZ 0012
- Challenge: if patched data is larger (button names differ in length), may need full PAZ rebuild
- PAPGT must be updated to reflect changed PAZ hash/size

---

## BlackSpace Engine (relevant context)

Proprietary (Pearl Abyss). No official mod support.

**Overlay VFS:** `0036/` directory — game loads overlay entries over originals for MOST files. But NOT for XML input maps.

**Overlay entries are NEVER encrypted.** Only vanilla PAZ files use ChaCha20. The `parse_pamt` heuristic (`.xml` = encrypted) only applies to vanilla archives.

**How remapping should work:** Extract `inputmap_common.xml` from PAZ 0012 (encrypted + LZ4 compressed, 220KB decompressed), swap `GamePad Key=` values per context (InputGroup LayerName), write back to vanilla PAZ 0012.

**Vendored CDUMM modules** (`tools/cd_remap/vendor/`): PAZ parsing, decryption, overlay building. From CDUMM v2.2.0.

**Key file details:**
- `inputmap_common.xml`: 4,813 lines, 928 Input blocks, 1,254 GamePad entries
- 88 InputGroups with LayerName attributes (engine context system)
- Horse and Combat share UIHud_4 layer
- PAZ folder `0012` contains all UI XML + textures

---

## Rules
- Backups before any game file modification
- Never commit extracted game data (PAZ, PAMT, PABG files) — .gitignore enforced
- Test mods in isolation
- Steam auto-update disabled for this game (prevents mod breakage)

# CD Controller Remapper
**IDENTITY:** LUDUS
**DIRECTORY:** D:\Games\Workshop\CD_REMAPPER\
**GAME:** Crimson Desert (Steam App ID: 3321460)
**INSTALL:** `D:\Games\SteamLibrary\steamapps\common\Crimson Desert\`

---

## What This Is

Action-based controller remapper for Crimson Desert (no in-game remapping exists). Users see game actions (Sprint, Dodge, Jump) and reassign them to controller buttons.

- Dear PyGui GUI with interactive controller diagram
- 3 context tabs: Combat (16 actions), Menus (8), Horse (7)
- Auto-swap on reassignment
- 3 built-in presets (Soulslike, Southpaw, Trigger Swap)
- Custom profile save/load (v3 action-assignment format)
- CLI + TUI fallback
- PyInstaller exe for Nexus distribution

---

## BlackSpace Engine (relevant context)

Proprietary (Pearl Abyss). No official mod support.

**Mod overlay:** Patched files go in `0036/` — game loads them over originals. Vanilla never touched.

**How remapping works:** Extract `inputmap_common.xml` from PAZ archive 0008, swap `GamePad Key=` values per context (InputGroup LayerName), write patched XML to `0036/` overlay.

**Vendored CDUMM modules** (`tools/cd_remap/vendor/`): PAZ parsing, decryption, overlay building. From CDUMM v2.2.0.

---

## Rules
- Backups before any game file modification
- Never commit extracted game data (PAZ, PAMT, PABG files) — .gitignore enforced
- Test mods in isolation
- Steam auto-update disabled for this game (prevents mod breakage)

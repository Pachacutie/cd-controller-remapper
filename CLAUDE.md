# CRIMSON_DESERT — Crimson Desert Modding
**IDENTITY:** LUDUS
**DIRECTORY:** D:\Games\Workshop\CRIMSON_DESERT\
**GAME:** Crimson Desert (Steam App ID: 3321460)
**INSTALL:** `D:\Games\SteamLibrary\steamapps\common\Crimson Desert\`

---

## BlackSpace Engine

Proprietary (Pearl Abyss). No official mod support — all community reverse-engineered.

**Archive format:** PAZ (data, ChaCha20 encrypted, LZ4 compressed) + PAMT (index) + PAPGT (root hash registry). Numbered folders `0000`-`0035`, each containing PAZ + PAMT for an asset category.

**Mod overlay:** Patched files go in `0036/` — game loads them over originals. Vanilla never touched.

**Mod types:** JSON byte-patches (most common), folder mods (loose files), ASI plugins (DLL injection), DLL injectors.

**Key PAZ folders:**

| Folder | Content |
|---|---|
| 0008 | Core game data — `.pabgb`/`.pabgh` tables, `.binarygimmick` files. ~20K entries. |
| 0012 | UI textures — minimap.dds, compass.dds, HUD elements |
| 0014 | UI views/logic — minimapview, hudview, sleep.pasf, interactionview |

**PABG format:** `.pabgh` = header (u16 count + N x (u32 hash, u32 offset)). `.pabgb` = data body (variable-length records). No public schema — field types via RE.

---

## Toolchain

**CDUMM** (MIT, Python): `D:\Games\Modding\Tools\CDUMM\`
- Full mod manager: PAZ/PAMT parsing, conflict detection, overlay building
- Run: `.venv\Scripts\python.exe -m cdumm.main`
- Library usage:
  ```python
  from cdumm.archive.paz_parse import parse_pamt
  from cdumm.archive.paz_crypto import lz4_decompress
  entries = parse_pamt('<game>/0008/0.pamt', '<game>/0008')
  ```

**Backups:** `D:\Games\Modding\Crimson Desert\BACKUP_PRISTINE\` (meta/, key PAMT indexes)

**Reference mods:** `D:\Games\Modding\Crimson Desert\` (downloaded from Nexus for RE reference)

---

## Controller Remapper v2.0

- Dear PyGui GUI with interactive controller diagram
- 3 built-in presets (Soulslike, Southpaw, Trigger Swap)
- Custom profile save/load/delete
- Per-context remapping: All / Gameplay / Menus
- CLI + TUI fallback preserved
- PyInstaller exe for Nexus distribution

---

## RE Notes

**interactioninfo.pabgb** (0008, 177KB decompressed): Contains interaction definitions. `Bed_Lie` at offset 0x02362D, `Campfire_Eat` at 0x014FB7, `RideWait` at 0x00C163. Includes positioning/animation data, not cooldown timers.

**actionrestrictionorderinfo.pabgb** (0008, 2562B, uncompressed): 45 records of 50 bytes each. Contains float values 32.0 and 135.0 that may be cooldown-related. Record format not fully decoded.

---

## Rules
- Backups before any game file modification
- Never commit extracted game data (PAZ, PAMT, PABG files) — .gitignore enforced
- Test mods in isolation
- Steam auto-update disabled for this game (prevents mod breakage)

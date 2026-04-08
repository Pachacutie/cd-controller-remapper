# Sleep Cooldown Reverse Engineering Notes

## Target
Remove the cooldown/restriction timer that prevents consecutive sleep/rest interactions in Crimson Desert.

## BlackSpace Engine Archive Structure
- Game data in numbered PAZ folders (0000-0035), encrypted (ChaCha20), compressed (LZ4)
- PAMT files index content within PAZ archives
- PAPGT is the root hash registry
- Mods go in overlay directory `0036/` — game loads patched files over originals

## Research Targets

### PAZ Folder 0008 — Core Game Data
The primary target. Contains 103+ .pabg data tables including:
- `restrictionorderinfo.pabg` — **TOP LEAD** — "restriction order" likely encodes cooldown rules
- `ieventtableinfo.pabg` — event table may reference sleep events
- `globaleffectinfo.pabg` — global effects that may include rest mechanics
- `quicktimeeventinfo.pabg` — timing-related game events
- `.binarygimmick` files with "bed", "tent", "camp" in names — interaction definitions

### PAZ Folder 0014 — UI Views/Logic
- `sleep.pasf` — sleep-related UI/interaction logic
- `interactionview` — general interaction framework
- `timerview` — timer display (might show cooldown countdown)

## Approach
1. Use CDUMM to browse and extract target files from 0008
2. Examine decompressed .pabg structure for timer/cooldown values (likely float or int32)
3. Identify byte offset(s) encoding the cooldown duration
4. Write JSON byte-patch to zero out the cooldown value
5. Test: apply via CDUMM, launch game, verify cooldown removed

## Findings
(To be filled during reverse engineering)

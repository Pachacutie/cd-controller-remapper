# Sleep Cooldown Reverse Engineering Notes

## Target
Remove the cooldown/restriction timer that prevents consecutive sleep/rest interactions in Crimson Desert.

## Findings

The cooldown is NOT a timer value in a data table. It's a **state machine gate** in `.pastage` (sequencer) files.

### Mechanism
Three `.pastage` files in **PAZ folder 0014** control sleep interactions:
1. `sequencer/cd_seq_minigame_sleep.pastage` (7968 bytes) — Main sleep UI sequencer
2. `sequencer/gimmick_sleep_bed_left.pastage` (8033 bytes) — Left-side bed interaction
3. `sequencer/gimmick_sleep_bed_right.pastage` (8033 bytes) — Right-side bed interaction

When on cooldown, the sequencer:
- Sets UI option flags to `"False"` (3h/6h/12h buttons greyed out)
- Transitions to `"NEGATIVE"` state (blocks the interaction)

### Fix
- Patch `"False"` → `"True "` (trailing space for byte-length parity) at UI flag offsets
- Patch `"NEGATIVE)"` → `"START)   "` and `"NEGATIVE"` → `"COMPLETE"` at state transition offsets

This forces the state machine to always accept the interaction and always show options as enabled.

### What we investigated but didn't need
- `actionrestrictionorderinfo.pabgb` (0008) — 45 records of 50 bytes. Contains float values (32.0, 135.0) but these are action restriction rules, not the sleep cooldown mechanism.
- `interactioninfo.pabgb` (0008, 177KB) — Contains interaction definitions (`Bed_Lie` at 0x02362D) with positioning/animation data. Defines what interactions exist, not their cooldown behavior.
- `.binarygimmick` files — Physical object definitions for beds/campfires.

### Key insight
The BlackSpace Engine uses `.pastage` sequencer files as state machines for game logic. Cooldowns are implemented as state gates, not timer values. To bypass a cooldown, patch the state transitions rather than looking for timer floats.

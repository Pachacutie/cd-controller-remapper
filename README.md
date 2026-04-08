# CRIMSON_DESERT — Crimson Desert Modding

Mod creation workspace for Crimson Desert (BlackSpace Engine).

## Mods

### No Sleep Cooldown (`mod/no_sleep_cooldown.json`)

Removes the time-gated cooldown on sleeping and resting at beds. All 3h/6h/12h options always available.

**How it works:** Patches three `.pastage` sequencer files in PAZ folder 0014:
- `cd_seq_minigame_sleep.pastage` — Sleep UI: enables greyed-out duration options
- `gimmick_sleep_bed_left.pastage` — Left bed: bypasses cooldown state gate
- `gimmick_sleep_bed_right.pastage` — Right bed: bypasses cooldown state gate

Two patch types:
- `"False"` → `"True "` — Re-enables disabled UI options
- `"NEGATIVE"` → `"START"`/`"COMPLETE"` — Changes state machine from rejection to acceptance

## Tools

### apply_mod.py

Applies or removes a JSON byte-patch mod by building a PAZ overlay (`0036/`) and updating the PAPGT hash registry. Backs up `meta/0.papgt` before first modification.

```bash
# Apply
python tools/apply_mod.py apply mod/no_sleep_cooldown.json [--dry-run]

# Remove (restores vanilla PAPGT from backup, deletes 0036/)
python tools/apply_mod.py remove
```

### verify_patch.py

Verifies that a JSON byte-patch mod's offsets match the current game files.

```bash
python tools/verify_patch.py mod/no_sleep_cooldown.json
```

Both tools require CDUMM (`D:\Games\Modding\Tools\CDUMM\.venv`).

## Toolchain

- **CDUMM** (MIT, Python): `D:\Games\Modding\Tools\CDUMM\` — PAZ/PAMT parsing, overlay building
- **Backups**: `D:\Games\Modding\Crimson Desert\BACKUP_PRISTINE\`

## License

MIT

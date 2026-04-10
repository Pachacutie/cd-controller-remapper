# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [2.5.0] - 2026-04-09

### Added
- Rollback on failure — mid-write PAZ patching errors auto-restore all files from backup
- Backup manifest — backups bound to game directory; prevents cross-install restore
- Profile validation — rejects corrupted or invalid button assignments on load
- Combat/Horse collision detection — blocks conflicting remaps before apply
- Swap validation (`validate_swaps_contextual`) called before every apply

### Fixed
- Missing `lz4` dependency in requirements.txt (was imported but undeclared)
- Controller image not bundled in PyInstaller exe
- `build/work/` not in .gitignore
- `remove_paz_patch` now returns dict on manifest mismatch (was raising ValueError)
- Manifest skip-if-exists guard matches `_create_backup` idempotent pattern

### Changed
- 131 tests (up from 114)

## [2.4.0] - 2026-04-09

### Added
- Leader-line labels — action names in external columns connected to buttons by lines
- Interactive hover highlights (blue) and selection persistence (gold until Apply/Reset)
- Button tooltips on bottom-bar controls

## [2.3.0] - 2026-04-09

### Added
- Xbox controller image background with interactive hotspot overlays
- Blue hover and gold selection highlight on controller buttons

### Fixed
- Hotspot highlight visibility improved
- PyInstaller SPECPATH-relative path corrected

## [2.2.0] - 2026-04-08

### Added
- Aggregate progress bar for PAZ I/O operations (no more GUI freeze)
- Persist last-applied remap state (reopens with previous mappings)
- Button highlight UX on apply/undo

## [2.1.0] - 2026-04-08

### Added
- In-place PAZ patching for full combat + menu remapping (both XMLs)
- Settings button with game directory picker
- CharacterMove and Camera gameplay context layers

### Fixed
- Replaced `cryptography` C extension with pure-Python ChaCha20 (PyInstaller compatibility)
- Overlay entries encryption handling
- Vendor module hidden imports for PyInstaller build

### Changed
- Switched from overlay-based patching to in-place PAZ patching

## [2.0.0] - 2026-04-08

### Added
- Action-based remapping GUI — see game actions (Sprint, Dodge, Jump) instead of raw buttons
- Three context tabs: Combat (16 actions), Menus (8), Horse (7)
- Auto-swap on reassignment — displaced action moves to the vacated button
- Interactive controller diagram with hover and click support
- XInput gamepad input — remap by pressing physical buttons
- Built-in presets: Soulslike, Southpaw, Trigger Swap
- Custom profile save/load (v3 action-assignment format)
- Escape key cancels active selection
- Auto-detect Steam install directory
- Friendly error messages when game directory not found
- Profiles saved to `%APPDATA%/cd_remap/profiles/`
- 72 automated tests

### Changed
- GUI is now the default entry point (was TUI)
- PyInstaller exe builds as windowed app (no console)

## [1.0.0] - 2026-04-08

### Added
- CLI controller remapper with apply/remove/show commands
- Text-based interactive TUI
- Per-context swap validation (gameplay/menus layers)
- Profile save/load (v2 swap-list format)
- PAZ overlay patching — vanilla files never touched

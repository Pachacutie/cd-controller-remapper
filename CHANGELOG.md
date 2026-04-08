# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

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

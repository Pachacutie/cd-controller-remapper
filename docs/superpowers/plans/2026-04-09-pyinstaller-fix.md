# Plan: Fix PyInstaller EXE PAZ Corruption

## Context

The remapping code works perfectly from source (CLI: 277 bindings, GUI: 146, combat confirmed in-game). The PyInstaller EXE corrupts PAZ files — it writes data that can't be decompressed on re-read. LZ4 error 34805/34821.

Research found [python-lz4 #183](https://github.com/python-lz4/python-lz4/issues/183): `lz4.block.decompress` fails when `uncompressed_size` is off by even 1 byte. The bundled lz4/cryptography C extensions in the EXE may produce slightly different compressed output than the system Python, causing size mismatches.

**Key constraint:** Shell `cp` silently fails writing to game dir. Always use Python `shutil.copy2`.

## Pre-flight

1. Verify game is vanilla: `python -c "from tools.cd_remap.remap import extract_both_xmls; ..."`
2. If corrupted, restore from `%APPDATA%/cd_remap/vanilla_safe/` via Python `shutil.copy2`
3. Clear any stale backup: `rm -rf %APPDATA%/cd_remap/backup`

## Phase 1: Diagnose the Exact Divergence

### Step 1: Build diagnostic EXE

Create `diag_roundtrip.py` that:
- Prints `lz4.version.version`, `cryptography.__version__`, `sys.version`
- Extracts `inputmap_common.xml` from PAZ (decrypt + decompress)
- Prints hex of first 32 bytes at each stage: raw, decrypted, decompressed
- Re-compresses the decompressed XML with `lz4.block.compress(data, store_size=False)`
- Re-encrypts with `encrypt(compressed, path)`
- Prints: `len(original_compressed)`, `len(re_compressed)`, `match: True/False`
- Writes results to `%APPDATA%/cd_remap/diag_output.txt` (avoids CFA/console issues)

Build WITHOUT `--windowed` so CFA errors are visible. Allowlist the EXE in Windows Security if needed.

### Step 2: Run diagnostic from source Python

Run the same logic from source to get the baseline. Save to `diag_source.txt`.

### Step 3: Run diagnostic EXE

Run the EXE. Compare `diag_output.txt` vs `diag_source.txt`:
- If library versions differ → bundling issue
- If decrypt output differs → cryptography CFFI backend problem
- If compress output size differs → lz4 version mismatch
- If both match but apply still fails → the issue is in the write pipeline, not the libraries

## Phase 2: Fix Based on Diagnosis

### Path A: lz4 compress size differs

The EXE's lz4 produces different compressed output. Fix options:
1. Pin `lz4` version in requirements and rebuild
2. Add buffer margin: `lz4.block.decompress(data, uncompressed_size=orig_size + 256)` then truncate
3. Use `lz4.frame` API instead of `lz4.block` (frame API is more portable)

### Path B: cryptography decrypt diverges

The CFFI backend in the EXE behaves differently. Fix options:
1. Add `--collect-all cffi` to PyInstaller build
2. Force ctypes backend instead of CFFI
3. Replace `cryptography.hazmat` ChaCha20 with a pure-Python ChaCha20 implementation (eliminates the dependency entirely — key derivation is already pure Python)

### Path C: Libraries match but write corrupts

The issue is in `paz_patcher.py`'s write logic when running from EXE. Possible causes:
- File handle not flushed before PAMT update
- `bytearray` memory differs in frozen Python
- Path resolution issue in EXE temp directory

### Path D: Cannot fix bundling

Abandon single-EXE distribution. Ship as:
- **Option 1:** `cd_remap.pyz` zipapp + `run.bat` that calls `python cd_remap.pyz` (requires Python installed)
- **Option 2:** Embedded Python distribution (python-3.12-embed-amd64.zip + our code) — no install needed, ~30MB
- **Option 3:** Use `cx_Freeze` or `Nuitka` instead of PyInstaller

## Phase 3: Verify and Release

1. Restore vanilla from `%APPDATA%/cd_remap/vanilla_safe/`
2. Clear backup
3. Run new EXE GUI → apply Soulslike preset → check status bar
4. Verify files extractable from source: `python -c "from tools.cd_remap.remap import extract_both_xmls; ..."`
5. Launch game → test menus + combat
6. Undo via EXE → verify vanilla restored
7. If passing: rebuild with `--windowed`, update GitHub release v2.1.0

## Critical Files

| File | Purpose |
|---|---|
| `build/build_exe.py` | PyInstaller build script |
| `tools/cd_remap/vendor/paz_crypto.py` | ChaCha20 decrypt/encrypt + lz4 compress/decompress |
| `tools/cd_remap/vendor/paz_repack.py` | Repack pipeline (compress → encrypt → payload) |
| `tools/cd_remap/vendor/paz_patcher.py` | Write pipeline (payload → PAZ file → PAMT update) |
| `%APPDATA%/cd_remap/vanilla_safe/` | Permanent vanilla backup (never touch) |

# PAZ I/O Progress Bar — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the GUI freeze during Apply/Undo with a real progress bar that updates as 912MB+ PAZ files are read/written.

**Architecture:** Worker thread runs PAZ I/O with chunked read/write. A shared dict bridges progress from worker to main loop. DearPyGui main loop polls each frame and updates a modal progress bar. Both `apply_paz_patch()` and `remove_paz_patch()` gain an optional `progress_cb` parameter; existing callers are unaffected.

**Tech Stack:** Python `threading`, DearPyGui progress bar widget, chunked file I/O (4MB chunks)

**Spec:** `docs/superpowers/specs/2026-04-09-progress-bar-design.md`

---

### Task 1: Chunked I/O helpers in paz_patcher.py

**Files:**
- Modify: `tools/cd_remap/vendor/paz_patcher.py:1-27` (add constant + helpers after imports)
- Test: `tests/test_paz_patcher.py`

- [ ] **Step 1: Write failing tests for _chunked_read and _chunked_write**

Add to `tests/test_paz_patcher.py` after the existing imports at line 17:

```python
from cd_remap.vendor.paz_patcher import _chunked_read, _chunked_write, _chunked_copy, CHUNK_SIZE
```

Add a new test class at the end of the file:

```python
class TestChunkedIO:
    def test_chunked_read_returns_correct_bytes(self, tmp_path):
        data = b"A" * 100_000
        f = tmp_path / "test.bin"
        f.write_bytes(data)
        result = _chunked_read(f, None, "test")
        assert result == bytearray(data)

    def test_chunked_read_calls_progress(self, tmp_path):
        data = b"A" * (CHUNK_SIZE * 3 + 100)
        f = tmp_path / "test.bin"
        f.write_bytes(data)
        calls = []
        result = _chunked_read(f, lambda p, d, t: calls.append((p, d, t)), "Reading")
        assert result == bytearray(data)
        assert len(calls) == 4  # 3 full chunks + 1 partial
        assert calls[0][0] == "Reading"
        assert calls[-1][1] == len(data)
        assert all(c[2] == len(data) for c in calls)

    def test_chunked_write_produces_correct_file(self, tmp_path):
        data = bytearray(b"B" * 100_000)
        f = tmp_path / "out.bin"
        _chunked_write(f, data, None, "test")
        assert f.read_bytes() == data

    def test_chunked_write_calls_progress(self, tmp_path):
        data = bytearray(b"B" * (CHUNK_SIZE * 2 + 500))
        f = tmp_path / "out.bin"
        calls = []
        _chunked_write(f, data, lambda p, d, t: calls.append((p, d, t)), "Writing")
        assert f.read_bytes() == data
        assert len(calls) == 3  # 2 full chunks + 1 partial
        assert calls[-1][1] == len(data)
        assert calls[0][0] == "Writing"

    def test_chunked_copy_duplicates_file(self, tmp_path):
        data = b"C" * 100_000
        src = tmp_path / "src.bin"
        dst = tmp_path / "dst.bin"
        src.write_bytes(data)
        _chunked_copy(src, dst, None, "test")
        assert dst.read_bytes() == data

    def test_chunked_copy_calls_progress(self, tmp_path):
        data = b"C" * (CHUNK_SIZE * 2)
        src = tmp_path / "src.bin"
        dst = tmp_path / "dst.bin"
        src.write_bytes(data)
        calls = []
        _chunked_copy(src, dst, lambda p, d, t: calls.append((p, d, t)), "Restoring")
        assert dst.read_bytes() == data
        assert len(calls) == 2
        assert calls[-1][1] == len(data)

    def test_chunked_read_empty_file(self, tmp_path):
        f = tmp_path / "empty.bin"
        f.write_bytes(b"")
        result = _chunked_read(f, None, "test")
        assert result == bytearray()

    def test_chunked_write_empty_buffer(self, tmp_path):
        f = tmp_path / "empty.bin"
        _chunked_write(f, bytearray(), None, "test")
        assert f.read_bytes() == b""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:/Games/Workshop/CD_REMAPPER && python -m pytest tests/test_paz_patcher.py::TestChunkedIO -v`
Expected: ImportError — `_chunked_read`, `_chunked_write`, `_chunked_copy`, `CHUNK_SIZE` not found.

- [ ] **Step 3: Implement chunked I/O helpers**

In `tools/cd_remap/vendor/paz_patcher.py`, add after line 27 (`PAZ_FOLDER = "0012"`):

```python
CHUNK_SIZE = 4 * 1024 * 1024  # 4 MB


def _chunked_read(path, progress_cb, phase):
    """Read file into bytearray in chunks, calling progress_cb after each."""
    path = Path(path)
    size = path.stat().st_size
    buf = bytearray(size)
    with open(path, "rb") as f:
        done = 0
        while done < size:
            chunk = f.readinto(memoryview(buf)[done:done + CHUNK_SIZE])
            if not chunk:
                break
            done += chunk
            if progress_cb:
                progress_cb(phase, done, size)
    return buf


def _chunked_write(path, buf, progress_cb, phase):
    """Write bytearray to file in chunks, calling progress_cb after each."""
    path = Path(path)
    total = len(buf)
    with open(path, "wb") as f:
        done = 0
        while done < total:
            end = min(done + CHUNK_SIZE, total)
            f.write(buf[done:end])
            done = end
            if progress_cb:
                progress_cb(phase, done, total)


def _chunked_copy(src, dst, progress_cb, phase):
    """Copy file in chunks with progress callback. Preserves metadata."""
    src, dst = Path(src), Path(dst)
    size = src.stat().st_size
    with open(src, "rb") as fin, open(dst, "wb") as fout:
        done = 0
        while done < size:
            chunk = fin.read(CHUNK_SIZE)
            if not chunk:
                break
            fout.write(chunk)
            done += len(chunk)
            if progress_cb:
                progress_cb(phase, done, size)
    shutil.copystat(src, dst)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd D:/Games/Workshop/CD_REMAPPER && python -m pytest tests/test_paz_patcher.py::TestChunkedIO -v`
Expected: All 8 tests PASS.

- [ ] **Step 5: Run full test suite for regressions**

Run: `cd D:/Games/Workshop/CD_REMAPPER && python -m pytest tests/ -v`
Expected: 98 tests (96 pass, 2 skipped).

- [ ] **Step 6: Commit**

```bash
git add tools/cd_remap/vendor/paz_patcher.py tests/test_paz_patcher.py
git commit -m "feat: add chunked I/O helpers to paz_patcher"
```

---

### Task 2: Wire progress_cb into apply_paz_patch and remove_paz_patch

**Files:**
- Modify: `tools/cd_remap/vendor/paz_patcher.py:97-205` (apply_paz_patch + remove_paz_patch)
- Test: `tests/test_paz_patcher.py`

- [ ] **Step 1: Write failing tests for progress_cb integration**

Add to `tests/test_paz_patcher.py`, new class at end:

```python
class TestProgressCallback:
    def _setup(self, tmp_path, monkeypatch, plaintext=PLAINTEXT):
        paz_bytes, pamt_bytes, papgt_bytes, _info = build_test_paz_pamt_papgt(
            plaintext, TARGET_FILE, PAZ_FOLDER
        )
        game_dir = _write_game_dir(tmp_path / "game", paz_bytes, pamt_bytes, papgt_bytes)
        backup = tmp_path / "backup"
        monkeypatch.setattr("cd_remap.vendor.paz_patcher._backup_dir", lambda: backup)
        return game_dir

    def test_apply_calls_progress_cb(self, tmp_path, monkeypatch):
        game_dir = self._setup(tmp_path, monkeypatch)
        calls = []
        apply_paz_patch([(TARGET_FILE, MODIFIED)], game_dir,
                        progress_cb=lambda p, d, t: calls.append((p, d, t)))
        phases = {c[0] for c in calls}
        assert any("Reading" in p for p in phases)
        assert any("Writing" in p for p in phases)

    def test_apply_without_progress_cb_still_works(self, tmp_path, monkeypatch):
        game_dir = self._setup(tmp_path, monkeypatch)
        result = apply_paz_patch([(TARGET_FILE, MODIFIED)], game_dir)
        assert result == {"ok": True}

    def test_remove_calls_progress_cb(self, tmp_path, monkeypatch):
        game_dir = self._setup(tmp_path, monkeypatch)
        apply_paz_patch([(TARGET_FILE, MODIFIED)], game_dir)
        calls = []
        remove_paz_patch(game_dir,
                         progress_cb=lambda p, d, t: calls.append((p, d, t)))
        phases = {c[0] for c in calls}
        assert any("Restoring" in p for p in phases)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:/Games/Workshop/CD_REMAPPER && python -m pytest tests/test_paz_patcher.py::TestProgressCallback -v`
Expected: TypeError — `apply_paz_patch()` got unexpected keyword argument `progress_cb`.

- [ ] **Step 3: Add progress_cb to apply_paz_patch**

In `tools/cd_remap/vendor/paz_patcher.py`, modify `apply_paz_patch` signature (line 97):

```python
def apply_paz_patch(patches: list[tuple[str, bytes]], game_dir: Path, *, progress_cb=None) -> dict:
```

Replace line 137:
```python
        buf = bytearray(paz_path.read_bytes())
```
with:
```python
        paz_name = f"{entry.paz_index}.paz"
        buf = _chunked_read(paz_path, progress_cb, f"Reading {paz_name}")
```

Replace line 148:
```python
        paz_path.write_bytes(buf)
```
with:
```python
        _chunked_write(paz_path, buf, progress_cb, f"Writing {paz_name}")
```

Add after line 167 (before PAPGT rebuild), call progress for index update phase:
```python
    if progress_cb:
        progress_cb("Updating indexes", 0, 1)
```

- [ ] **Step 4: Add progress_cb to remove_paz_patch**

Modify `remove_paz_patch` signature (line 179):

```python
def remove_paz_patch(game_dir: Path, *, progress_cb=None) -> dict:
```

Replace the PAMT/PAPGT restore loop (lines 195-198):
```python
    for rel in (f"{PAZ_FOLDER}/0.pamt", "meta/0.papgt"):
        src = backup / rel
        if src.exists():
            shutil.copy2(src, game_dir / rel)
```
with:
```python
    for rel in (f"{PAZ_FOLDER}/0.pamt", "meta/0.papgt"):
        src = backup / rel
        if src.exists():
            _chunked_copy(src, game_dir / rel, progress_cb, f"Restoring {Path(rel).name}")
```

Replace the PAZ restore loop (lines 201-203):
```python
    paz_backup_dir = backup / PAZ_FOLDER
    for f in paz_backup_dir.glob("*.paz"):
        shutil.copy2(f, game_dir / PAZ_FOLDER / f.name)
```
with:
```python
    paz_backup_dir = backup / PAZ_FOLDER
    for f in paz_backup_dir.glob("*.paz"):
        _chunked_copy(f, game_dir / PAZ_FOLDER / f.name, progress_cb, f"Restoring {f.name}")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd D:/Games/Workshop/CD_REMAPPER && python -m pytest tests/test_paz_patcher.py::TestProgressCallback -v`
Expected: All 3 tests PASS.

- [ ] **Step 6: Run full test suite for regressions**

Run: `cd D:/Games/Workshop/CD_REMAPPER && python -m pytest tests/ -v`
Expected: 98 tests baseline + 11 new = ~109 total (96+11 pass, 2 skipped).

- [ ] **Step 7: Commit**

```bash
git add tools/cd_remap/vendor/paz_patcher.py tests/test_paz_patcher.py
git commit -m "feat: wire progress_cb into apply_paz_patch and remove_paz_patch"
```

---

### Task 3: Thread progress_cb through remap.py

**Files:**
- Modify: `tools/cd_remap/remap.py:256-278` (_apply_patched_xmls + remove_remap)
- Test: `tests/test_remap.py`

- [ ] **Step 1: Write failing test**

Check existing test patterns first. Add to `tests/test_remap.py`:

```python
def test_apply_patched_xmls_passes_progress_cb(tmp_path, monkeypatch):
    """Verify progress_cb is threaded through to apply_paz_patch."""
    from cd_remap.remap import _apply_patched_xmls
    from fixtures import build_multi_file_paz

    file_a = "ui/inputmap_common.xml"
    file_b = "ui/inputmap.xml"
    content_a = b'<Input><GamePad Key="buttonA"/></Input>\n' * 15
    content_b = b'<Input><GamePad Key="buttonX"/></Input>\n' * 15

    paz_bytes, pamt_bytes, papgt_bytes = build_multi_file_paz(
        [(file_a, content_a), (file_b, content_b)]
    )
    game_dir = tmp_path / "game"
    paz_dir = game_dir / "0012"
    paz_dir.mkdir(parents=True)
    (paz_dir / "0.paz").write_bytes(paz_bytes)
    (paz_dir / "0.pamt").write_bytes(pamt_bytes)
    (game_dir / "meta").mkdir()
    (game_dir / "meta" / "0.papgt").write_bytes(papgt_bytes)

    backup = tmp_path / "backup"
    monkeypatch.setattr("cd_remap.vendor.paz_patcher._backup_dir", lambda: backup)
    monkeypatch.setattr("cd_remap.remap._backup_dir", lambda: backup)

    calls = []
    modified_a = content_a.replace(b"buttonA", b"buttonB")
    modified_b = content_b.replace(b"buttonX", b"buttonY")
    result = _apply_patched_xmls(modified_a, modified_b, game_dir,
                                  progress_cb=lambda p, d, t: calls.append(p))
    assert result["ok"]
    assert len(calls) > 0


def test_remove_remap_passes_progress_cb(tmp_path, monkeypatch):
    """Verify progress_cb is threaded through to remove_paz_patch."""
    from cd_remap.remap import remove_remap
    from cd_remap.vendor.paz_patcher import apply_paz_patch
    from fixtures import build_test_paz_pamt_papgt

    plaintext = b'<Input><GamePad Key="buttonA"/></Input>\n' * 15
    paz_bytes, pamt_bytes, papgt_bytes, _ = build_test_paz_pamt_papgt(
        plaintext, "ui/inputmap_common.xml", "0012"
    )
    game_dir = tmp_path / "game"
    paz_dir = game_dir / "0012"
    paz_dir.mkdir(parents=True)
    (paz_dir / "0.paz").write_bytes(paz_bytes)
    (paz_dir / "0.pamt").write_bytes(pamt_bytes)
    (game_dir / "meta").mkdir()
    (game_dir / "meta" / "0.papgt").write_bytes(papgt_bytes)

    backup = tmp_path / "backup"
    monkeypatch.setattr("cd_remap.vendor.paz_patcher._backup_dir", lambda: backup)

    modified = plaintext.replace(b"buttonA", b"buttonB")
    apply_paz_patch([("ui/inputmap_common.xml", modified)], game_dir)

    calls = []
    result = remove_remap(game_dir, progress_cb=lambda p, d, t: calls.append(p))
    assert result["ok"]
    assert len(calls) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:/Games/Workshop/CD_REMAPPER && python -m pytest tests/test_remap.py::test_apply_patched_xmls_passes_progress_cb tests/test_remap.py::test_remove_remap_passes_progress_cb -v`
Expected: TypeError — unexpected keyword argument `progress_cb`.

- [ ] **Step 3: Add progress_cb parameter to _apply_patched_xmls and remove_remap**

In `tools/cd_remap/remap.py`, modify `_apply_patched_xmls` (line 256):

```python
def _apply_patched_xmls(
    patched_common: bytes,
    patched_override: bytes,
    game_dir: Path = DEFAULT_GAME_DIR,
    *,
    progress_cb=None,
) -> dict:
```

And pass it through on line 268:
```python
    result = apply_paz_patch(
        [(TARGET_FILE, patched_common), (TARGET_FILE_OVERRIDE, patched_override)],
        game_dir,
        progress_cb=progress_cb,
    )
```

Modify `remove_remap` (line 276):

```python
def remove_remap(game_dir: Path = DEFAULT_GAME_DIR, *, progress_cb=None) -> dict:
    """Restore vanilla PAZ/PAMT/PAPGT from backup."""
    return remove_paz_patch(game_dir, progress_cb=progress_cb)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd D:/Games/Workshop/CD_REMAPPER && python -m pytest tests/test_remap.py::test_apply_patched_xmls_passes_progress_cb tests/test_remap.py::test_remove_remap_passes_progress_cb -v`
Expected: PASS.

- [ ] **Step 5: Run full test suite**

Run: `cd D:/Games/Workshop/CD_REMAPPER && python -m pytest tests/ -v`
Expected: All existing tests still pass, 2 new pass.

- [ ] **Step 6: Commit**

```bash
git add tools/cd_remap/remap.py tests/test_remap.py
git commit -m "feat: thread progress_cb through remap.py to paz_patcher"
```

---

### Task 4: Progress modal and worker threads in gui.py

**Files:**
- Modify: `tools/cd_remap/gui.py`

This task has no automated tests — DearPyGui widgets can't be unit-tested without a display context. Manual verification in Task 5.

- [ ] **Step 1: Add threading import**

In `tools/cd_remap/gui.py`, add `import threading` after the existing `from pathlib import Path` import on line 2:

```python
import threading
```

- [ ] **Step 2: Add progress state to __init__**

In `RemapGUI.__init__` (after line 61 `self.drawlist = None`), add:

```python
        self._progress = {}
```

- [ ] **Step 3: Add progress modal to build()**

In `gui.py`, after the apply modal block (after line 420), add:

```python
        # Progress modal
        with dpg.window(label="Working...", modal=True, show=False,
                        tag="progress_modal", width=400, height=100,
                        no_resize=True, no_close=True, no_move=True):
            dpg.add_text("Initializing...", tag="progress_label")
            dpg.add_progress_bar(tag="progress_bar", default_value=0.0, width=-1)
            dpg.add_text("0%", tag="progress_pct")
```

- [ ] **Step 4: Add button tag constants and disable/enable helpers**

Add tags to the bottom-bar buttons. Replace the bottom bar section in `build()` (lines 460-472):

```python
            # Bottom bar
            dpg.add_separator()
            with dpg.group(horizontal=True):
                status = "Connected" if self.gamepad.connected else "Not detected"
                color = (100, 255, 100) if self.gamepad.connected else (150, 150, 150)
                dpg.add_text("Controller:", color=(200, 200, 200))
                dpg.add_text(status, tag="gamepad_status", color=color)
                dpg.add_spacer(width=20)
                dpg.add_button(label="Reset", tag="btn_reset", callback=self._on_reset)
                dpg.add_button(label="Save", tag="btn_save", callback=self._on_save)
                dpg.add_button(label="Apply", tag="btn_apply", callback=self._on_apply)
                dpg.add_button(label="Undo All", tag="btn_undo", callback=self._on_undo)
                dpg.add_spacer(width=20)
                dpg.add_button(label="Settings", tag="btn_settings",
                               callback=lambda: dpg.configure_item("settings_modal", show=True))
```

Add helper methods after `_set_status` (after line 374):

```python
    _DISABLE_TAGS = ("btn_reset", "btn_save", "btn_apply", "btn_undo", "btn_settings")

    def _disable_buttons(self):
        for tag in self._DISABLE_TAGS:
            if dpg.does_item_exist(tag):
                dpg.configure_item(tag, enabled=False)

    def _enable_buttons(self):
        for tag in self._DISABLE_TAGS:
            if dpg.does_item_exist(tag):
                dpg.configure_item(tag, enabled=True)
```

- [ ] **Step 5: Add progress callback and worker methods**

Add after the `_enable_buttons` method:

```python
    def _update_progress(self, phase, bytes_done, total_bytes):
        self._progress["phase"] = phase
        self._progress["bytes_done"] = bytes_done
        self._progress["total_bytes"] = total_bytes

    def _start_worker(self, target, args=()):
        self._progress = {"phase": "", "bytes_done": 0, "total_bytes": 0,
                          "done": False, "result": None, "error": None}
        self._disable_buttons()
        dpg.set_value("progress_bar", 0.0)
        dpg.set_value("progress_label", "Starting...")
        dpg.set_value("progress_pct", "0%")
        dpg.configure_item("progress_modal", show=True)
        threading.Thread(target=target, args=args, daemon=True).start()

    def _worker_apply(self, patched_common, patched_override):
        try:
            result = _apply_patched_xmls(
                patched_common, patched_override, self.game_dir,
                progress_cb=self._update_progress,
            )
            self._progress["result"] = result
        except Exception as e:
            self._progress["error"] = str(e)
        self._progress["done"] = True

    def _worker_undo(self):
        try:
            result = remove_remap(self.game_dir, progress_cb=self._update_progress)
            self._progress["result"] = result
        except Exception as e:
            self._progress["error"] = str(e)
        self._progress["done"] = True
```

- [ ] **Step 6: Rewrite _on_apply_confirm to use worker thread**

Replace `_on_apply_confirm` (lines 317-350):

```python
    def _on_apply_confirm(self):
        dpg.configure_item("apply_modal", show=False)
        try:
            all_swaps = []
            for ctx in ALL_CONTEXTS:
                defaults = get_defaults(ctx)
                swap_ctx = CONTEXT_TO_SWAP_CONTEXT[ctx]
                swaps = diff_to_swaps(defaults, self.assignments[ctx], swap_ctx)
                all_swaps.extend(swaps)

            seen = set()
            unique_swaps = []
            for s in all_swaps:
                key = (s["source"], s["target"], s["context"])
                if key not in seen:
                    seen.add(key)
                    unique_swaps.append(s)

            if not unique_swaps:
                self._set_status("No changes to apply.")
                return

            common, override = extract_both_xmls(self.game_dir)
            patched_common = apply_swaps_contextual(common, unique_swaps)
            patched_override = apply_swaps_contextual(override, unique_swaps)
            self._start_worker(self._worker_apply, (patched_common, patched_override))
        except Exception as e:
            self._set_status(f"Error: {e}")
```

- [ ] **Step 7: Rewrite _on_undo to use worker thread**

Replace `_on_undo` (lines 352-357):

```python
    def _on_undo(self):
        self._start_worker(self._worker_undo)
```

- [ ] **Step 8: Add progress polling to main loop**

In the main loop (lines 489-503), add progress polling after the gamepad connection check block (after line 501) and before `dpg.render_dearpygui_frame()`:

```python
            # Poll worker thread progress
            if self._progress.get("done"):
                dpg.configure_item("progress_modal", show=False)
                self._enable_buttons()
                if self._progress.get("error"):
                    self._set_status(f"Error: {self._progress['error']}")
                elif self._progress.get("result"):
                    r = self._progress["result"]
                    if "affected" in r:
                        self._set_status(f"Applied! {r['affected']} bindings remapped.")
                    else:
                        self._set_status(f"Undo: {r.get('message', 'Done')}")
                self._progress = {}
            elif self._progress.get("phase"):
                total = self._progress["total_bytes"]
                frac = self._progress["bytes_done"] / total if total else 0
                dpg.set_value("progress_bar", frac)
                dpg.set_value("progress_label", self._progress["phase"])
                dpg.set_value("progress_pct", f"{int(frac * 100)}%")
```

Note: the `done` check comes BEFORE the progress update check. This ensures that when the worker finishes, we immediately hide the modal rather than showing one more frame of stale progress.

- [ ] **Step 9: Commit**

```bash
git add tools/cd_remap/gui.py
git commit -m "feat: progress bar modal with worker threads for Apply and Undo"
```

---

### Task 5: Manual integration test and full suite

**Files:** None modified — verification only.

- [ ] **Step 1: Run full test suite**

Run: `cd D:/Games/Workshop/CD_REMAPPER && python -m pytest tests/ -v`
Expected: All tests pass (96 + ~13 new pass, 2 skipped).

- [ ] **Step 2: Manual GUI test (if game installed)**

Run: `cd D:/Games/Workshop/CD_REMAPPER && python -m cd_remap gui`

Verify:
1. Load a preset (e.g. Soulslike)
2. Click Apply → confirmation modal appears
3. Click Apply in modal → progress modal appears with bar updating
4. Buttons are disabled during operation
5. On completion: modal disappears, status bar shows "Applied! N bindings remapped."
6. Buttons re-enabled
7. Click Undo All → progress modal appears for restore
8. On completion: status shows "Undo: Vanilla PAZ restored."

- [ ] **Step 3: Commit any fixes from manual testing**

If any fixes needed, commit with appropriate message.

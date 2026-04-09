# PAZ I/O Progress Bar — Design Spec

**Date:** 2026-04-09
**Status:** Draft
**Scope:** GUI UX fix — real progress feedback during Apply and Undo operations

---

## Problem

`apply_paz_patch()` and `remove_paz_patch()` perform synchronous 912MB+ file I/O on the DearPyGui main thread. The GUI freezes for minutes with no feedback. Users can't tell if the app is working or crashed, and may launch the game too early.

## Solution

Worker thread + chunked I/O with a progress callback. The GUI main loop polls shared state each frame to update a progress bar modal.

## Architecture

Two files modified, no new files:

- **`paz_patcher.py`** — Chunked read/write with optional `progress_cb`
- **`gui.py`** — Progress modal, worker thread dispatch, main-loop polling

## Chunked I/O (paz_patcher.py)

### Progress callback signature

```python
def progress_cb(phase: str, bytes_done: int, total_bytes: int) -> None
```

### Phases

| Phase string | Operation |
|---|---|
| `"Reading 0.paz"` | Chunked read of PAZ file into bytearray |
| `"Writing 0.paz"` | Chunked write of patched PAZ back to disk |
| `"Reading 2.paz"` | Same for second PAZ file |
| `"Writing 2.paz"` | Same for second PAZ file |
| `"Restoring 0.paz"` | Chunked copy from backup during Undo |
| `"Restoring 2.paz"` | Same for second PAZ file |
| `"Updating indexes"` | PAMT recompute + PAPGT rebuild (fast, no chunking) |

### Changes to apply_paz_patch()

Add optional `progress_cb` parameter (default `None`).

Replace `paz_path.read_bytes()` (line 137) with:
```python
def _chunked_read(path, progress_cb, phase):
    size = path.stat().st_size
    buf = bytearray(size)
    with open(path, "rb") as f:
        done = 0
        while done < size:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            buf[done:done + len(chunk)] = chunk
            done += len(chunk)
            if progress_cb:
                progress_cb(phase, done, size)
    return buf
```

Replace `paz_path.write_bytes(buf)` (line 148) with:
```python
def _chunked_write(path, buf, progress_cb, phase):
    total = len(buf)
    with open(path, "wb") as f:
        done = 0
        while done < total:
            end = min(done + CHUNK_SIZE, total)
            f.write(buf[done:end])
            done = end
            if progress_cb:
                progress_cb(phase, done, total)
```

`CHUNK_SIZE = 4 * 1024 * 1024` (4MB). Gives ~228 progress updates for a 912MB file.

### Changes to remove_paz_patch()

Add optional `progress_cb` parameter (default `None`).

Replace `shutil.copy2()` calls with a chunked copy:
```python
def _chunked_copy(src, dst, progress_cb, phase):
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

### Backward compatibility

Both functions keep `progress_cb=None` default. Existing callers (CLI, TUI, tests) are unaffected.

## Progress UI (gui.py)

### Shared state

```python
self._progress = {
    "phase": "",
    "bytes_done": 0,
    "total_bytes": 0,
    "done": False,
    "result": None,
    "error": None,
}
```

Plain dict. Single-writer (worker thread), single-reader (main loop). Simple key assignments are atomic in CPython.

### Progress modal

DearPyGui modal window containing:
- Phase label text (e.g. "Writing 0.paz...")
- Progress bar (`dpg.add_progress_bar`)
- Percentage text (e.g. "67%")
- No close button, no cancel button (PAZ writes must not be interrupted mid-file)

Tag: `"progress_modal"`

### Worker thread dispatch

**Apply flow** (`_on_apply_confirm`):
1. Collect and deduplicate swaps (fast, stays on main thread)
2. Extract XMLs and apply swaps (fast, stays on main thread)
3. Reset `self._progress`, show progress modal, disable all buttons
4. Launch `threading.Thread(target=self._worker_apply, args=(patched_common, patched_override))`

**Undo flow** (`_on_undo`):
1. Reset `self._progress`, show progress modal, disable all buttons
2. Launch `threading.Thread(target=self._worker_undo)`

### Worker methods

```python
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

def _update_progress(self, phase, bytes_done, total_bytes):
    self._progress["phase"] = phase
    self._progress["bytes_done"] = bytes_done
    self._progress["total_bytes"] = total_bytes
```

### Main loop polling

Add to the `while dpg.is_dearpygui_running()` loop, after gamepad polling:

```python
if self._progress.get("phase") and not self._progress["done"]:
    total = self._progress["total_bytes"]
    frac = self._progress["bytes_done"] / total if total else 0
    dpg.set_value("progress_bar", frac)
    dpg.set_value("progress_label", self._progress["phase"])
    dpg.set_value("progress_pct", f"{int(frac * 100)}%")

if self._progress.get("done"):
    # Hide modal, re-enable buttons, show result in status bar
    dpg.configure_item("progress_modal", show=False)
    self._enable_all_buttons()
    if self._progress.get("error"):
        self._set_status(f"Error: {self._progress['error']}")
    elif self._progress["result"]:
        result = self._progress["result"]
        if "affected" in result:
            self._set_status(f"Applied! {result['affected']} bindings remapped.")
        else:
            self._set_status(f"Undo: {result.get('message', 'Done')}")
    self._progress = {}
```

### Button disable/enable

New helper methods:

- `_disable_all_buttons()` — disables Apply, Undo, preset buttons, profile save/load, Settings
- `_enable_all_buttons()` — re-enables all

Uses `dpg.configure_item(tag, enabled=False/True)`.

## Plumbing: progress_cb through remap.py

`_apply_patched_xmls()` and `remove_remap()` in `remap.py` gain an optional `progress_cb=None` parameter and pass it through to `apply_paz_patch()` / `remove_paz_patch()`.

## Error handling

Worker catches all exceptions, writes error string to shared state. Main loop detects `done=True` + `error` set, hides modal, shows error in status bar. Same UX as current behavior, but the GUI stays responsive during the attempt.

If the write fails mid-file, the backup is intact — user can Undo to restore vanilla state.

## Testing

- Unit tests for `_chunked_read`, `_chunked_write`, `_chunked_copy` with a mock `progress_cb` — verify callback is called with correct phases and byte counts
- Unit test that `apply_paz_patch(progress_cb=None)` still works (backward compat)
- Existing 98 tests remain unaffected (no `progress_cb` argument)
- Manual GUI test: Apply with progress bar visible, verify percentage updates, verify buttons disabled during operation

## Out of scope

- Cancel button (interrupting a PAZ write mid-file corrupts the archive)
- Time-remaining estimate (chunked I/O rate varies too much to be useful)
- Multi-file aggregate progress bar (each PAZ file gets its own 0-100% cycle with a phase label — simpler and more informative)

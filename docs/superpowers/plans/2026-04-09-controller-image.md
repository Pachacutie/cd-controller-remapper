# Controller Image Background Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the primitive-drawn controller schematic with a CC0 Xbox 360 controller image for a polished, realistic look.

**Architecture:** Load a pre-rendered PNG of the Wikimedia Xbox360_gamepad.svg as a DPG texture. Draw it as the drawlist background. Replace solid button shapes with transparent hotspot overlays that only show color on hover/select/changed states. All interaction logic (hit_test, hover, labels) stays the same — only coordinates and drawing functions change.

**Tech Stack:** Dear PyGui (drawlist, textures), Pillow (asset verification), PyInstaller (bundling)

**Spec:** `docs/superpowers/specs/2026-04-09-controller-image-design.md`

---

### Task 1: Download and prepare the PNG asset

**Files:**
- Create: `assets/controller.png`
- Existing: `assets/xbox360_gamepad.svg` (already downloaded)

The SVG is already in `assets/`. We need a high-res PNG render. Wikimedia's thumbnail API renders SVGs server-side — no local tools needed.

- [ ] **Step 1: Download the pre-rendered PNG from Wikimedia**

```bash
curl -sL "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5a/Xbox360_gamepad.svg/1000px-Xbox360_gamepad.svg.png" -o assets/controller.png
```

This gives us a 1000px-wide PNG (aspect ratio preserved → ~715px tall). This is 2x our display size (500x358) for crisp rendering.

- [ ] **Step 2: Verify the image dimensions with Pillow**

```bash
python -c "from PIL import Image; img = Image.open('assets/controller.png'); print(f'{img.size[0]}x{img.size[1]}, mode={img.mode}')"
```

Expected: `1000x715` (approximately), mode=`RGBA` or `RGB`.

- [ ] **Step 3: Verify file size is reasonable**

```bash
ls -la assets/controller.png
```

Expected: 50-200KB PNG file.

- [ ] **Step 4: Commit the asset**

```bash
git add assets/controller.png assets/xbox360_gamepad.svg
git commit -m "feat: add Xbox controller image assets (CC0 Wikimedia)"
```

---

### Task 2: Add asset_path() utility

**Files:**
- Create: `tools/cd_remap/asset_util.py`
- Test: `tests/test_asset_util.py`

A small helper to resolve asset paths whether running from source or from a PyInstaller bundle.

- [ ] **Step 1: Write the failing test**

Create `tests/test_asset_util.py`:

```python
"""Tests for asset path resolution."""
import pytest


class TestAssetPath:
    def test_returns_path_object(self):
        from cd_remap.asset_util import asset_path
        result = asset_path("controller.png")
        from pathlib import Path
        assert isinstance(result, Path)

    def test_path_ends_with_requested_file(self):
        from cd_remap.asset_util import asset_path
        result = asset_path("controller.png")
        assert result.name == "controller.png"
        assert result.parent.name == "assets"

    def test_path_points_to_existing_file(self):
        from cd_remap.asset_util import asset_path
        result = asset_path("controller.png")
        assert result.exists(), f"Asset not found at {result}"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_asset_util.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'cd_remap.asset_util'`

- [ ] **Step 3: Write the implementation**

Create `tools/cd_remap/asset_util.py`:

```python
"""Resolve asset paths for both source and PyInstaller bundle."""
import sys
from pathlib import Path


def asset_path(filename: str) -> Path:
    """Return the full path to an asset file.

    Works in both development (source tree) and PyInstaller bundle.
    """
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "assets" / filename
    return Path(__file__).resolve().parent.parent.parent / "assets" / filename
```

The path chain from `asset_util.py` is: `tools/cd_remap/asset_util.py` → `tools/cd_remap/` → `tools/` → project root → `assets/`.

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_asset_util.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add tools/cd_remap/asset_util.py tests/test_asset_util.py
git commit -m "feat: add asset_path utility for resolving bundled assets"
```

---

### Task 3: Update controller_draw.py — image + hotspot drawing

**Files:**
- Modify: `tools/cd_remap/controller_draw.py`

This is the core change. Replace `draw_controller_body()` and `draw_button()` with image rendering and transparent hotspot overlays. Update all coordinates to match the image layout.

**Important:** The new drawlist size is **500 x 358** (matching the image aspect ratio of 751:537).

- [ ] **Step 1: Replace draw_controller_body() with draw_controller_image()**

In `controller_draw.py`, replace the `draw_controller_body` function:

```python
def draw_controller_image(drawlist: int | str, texture_tag: str):
    """Draw the controller image as the drawlist background."""
    dpg.draw_image(
        texture_tag, (0, 0), (500, 358),
        parent=drawlist,
    )
```

- [ ] **Step 2: Update BUTTON_POSITIONS for the image layout**

Replace the entire `BUTTON_POSITIONS` dict. These coordinates are mapped to a 500x358 drawlist displaying the 751x537 SVG. Scale factor: 500/751 = 0.6657.

**Note:** These are initial estimates derived from the SVG geometry. They MUST be calibrated visually in Task 4. Expect adjustments of 5-15px per button.

```python
# Button positions relative to drawlist origin (0,0 = top-left)
# Drawlist size: 500 x 358
# Coordinates mapped from Xbox360_gamepad.svg at 500x358 display scale
BUTTON_POSITIONS = {
    # Face buttons — right cluster
    "buttonA": {"x": 323, "y": 192, "r": 16, "shape": "circle", "label": "A"},
    "buttonB": {"x": 353, "y": 162, "r": 16, "shape": "circle", "label": "B"},
    "buttonX": {"x": 293, "y": 162, "r": 16, "shape": "circle", "label": "X"},
    "buttonY": {"x": 323, "y": 132, "r": 16, "shape": "circle", "label": "Y"},
    # Shoulder buttons
    "buttonLB": {"x": 82, "y": 48, "w": 56, "h": 22, "shape": "rect", "label": "LB"},
    "buttonRB": {"x": 312, "y": 48, "w": 56, "h": 22, "shape": "rect", "label": "RB"},
    # Triggers
    "buttonLT": {"x": 82, "y": 18, "w": 56, "h": 22, "shape": "rect", "label": "LT"},
    "buttonRT": {"x": 312, "y": 18, "w": 56, "h": 22, "shape": "rect", "label": "RT"},
    # Stick clicks
    "buttonLS": {"x": 163, "y": 148, "r": 12, "shape": "circle", "label": "LS"},
    "buttonRS": {"x": 277, "y": 218, "r": 12, "shape": "circle", "label": "RS"},
    # Analog sticks (outer rings — visual only, not clickable)
    "leftstick": {"x": 163, "y": 148, "r": 30, "shape": "ring", "label": "L"},
    "rightstick": {"x": 277, "y": 218, "r": 30, "shape": "ring", "label": "R"},
    # D-pad
    "padU": {"x": 147, "y": 194, "w": 20, "h": 20, "shape": "rect", "label": "^"},
    "padD": {"x": 147, "y": 234, "w": 20, "h": 20, "shape": "rect", "label": "v"},
    "padL": {"x": 127, "y": 214, "w": 20, "h": 20, "shape": "rect", "label": "<"},
    "padR": {"x": 167, "y": 214, "w": 20, "h": 20, "shape": "rect", "label": ">"},
    # Meta
    "select": {"x": 188, "y": 130, "w": 28, "h": 18, "shape": "rect", "label": "Sel"},
    "start": {"x": 234, "y": 130, "w": 28, "h": 18, "shape": "rect", "label": "Sta"},
}
```

- [ ] **Step 3: Update draw_button() to draw transparent hotspots**

Replace the `draw_button` function. Hotspots are invisible by default — they only show color when the GUI sets hover/selected/changed state via `update_button_color()`.

```python
def draw_button(drawlist: int | str, btn_id: str, color: tuple = (0, 0, 0, 0),
                border: tuple = (0, 0, 0, 0), label_override: str | None = None) -> int | str:
    """Draw a transparent hotspot overlay for a button. Returns the item tag."""
    pos = BUTTON_POSITIONS[btn_id]
    tag = f"btn_{btn_id}"

    if pos["shape"] == "circle":
        dpg.draw_circle(
            (pos["x"], pos["y"]), pos["r"],
            color=border, fill=color,
            tag=tag, parent=drawlist,
        )
    elif pos["shape"] == "ring":
        # Rings are not drawn — the image already shows stick outlines
        dpg.draw_circle(
            (pos["x"], pos["y"]), pos["r"],
            color=(0, 0, 0, 0), fill=(0, 0, 0, 0),
            tag=tag, parent=drawlist,
        )
    elif pos["shape"] == "rect":
        x, y, w, h = pos["x"], pos["y"], pos["w"], pos["h"]
        dpg.draw_rectangle(
            (x, y), (x + w, y + h),
            color=border, fill=color,
            rounding=4, tag=tag, parent=drawlist,
        )

    return tag
```

Note: No button label text is drawn on the hotspots — the image already shows the button letters. Action labels (Sprint, Dodge, etc.) are still drawn separately by `draw_action_label()`.

- [ ] **Step 4: Update _LABEL_OFFSETS for new positions**

Replace the `_LABEL_OFFSETS` dict to match the new layout:

```python
_LABEL_OFFSETS = {
    "buttonA": (20, 4), "buttonB": (20, 4), "buttonX": (-50, 4), "buttonY": (20, -2),
    "buttonLB": (0, 24), "buttonRB": (0, 24),
    "buttonLT": (0, 24), "buttonRT": (0, 24),
    "buttonLS": (-16, 34), "buttonRS": (-16, 34),
    "select": (-4, 22), "start": (-4, 22),
}
```

- [ ] **Step 5: Update default color constants**

The hover/selected colors need alpha for overlay transparency. Update the defaults at the top of the file:

```python
COLOR_DEFAULT = (0, 0, 0, 0)        # Transparent — image shows through
COLOR_BORDER = (0, 0, 0, 0)         # No border on hotspots
COLOR_HOVER = (180, 180, 180, 60)   # Subtle white glow
COLOR_SELECTED = (255, 255, 255, 90) # Brighter selection indicator
```

Keep `COLOR_BODY`, `COLOR_BODY_BORDER`, and `COLOR_LABEL` unchanged — labels still need visible text.

- [ ] **Step 6: Run existing tests**

```bash
python -m pytest tests/ -v --tb=short
```

Expected: All tests pass. The drawing module isn't unit tested (DPG calls are visual-only), so existing tests for remap/contexts/presets/etc. should be unaffected.

- [ ] **Step 7: Commit**

```bash
git add tools/cd_remap/controller_draw.py
git commit -m "feat: replace primitive controller drawing with image hotspot overlays"
```

---

### Task 4: Calibrate button positions

**Files:**
- Modify: `tools/cd_remap/controller_draw.py` (BUTTON_POSITIONS values only)

The coordinates from Task 3 are estimates. This task fine-tunes them by running the app with a debug overlay.

- [ ] **Step 1: Add a temporary debug flag to draw_button()**

At the top of `controller_draw.py`, add:

```python
_DEBUG_HOTSPOTS = True  # TEMP: set False after calibration
```

In `draw_button()`, after drawing the hotspot shape, add a visible debug outline:

```python
    # At the end of draw_button(), before `return tag`:
    if _DEBUG_HOTSPOTS and pos["shape"] != "ring":
        debug_tag = f"debug_{btn_id}"
        if pos["shape"] == "circle":
            dpg.draw_circle(
                (pos["x"], pos["y"]), pos["r"],
                color=(255, 0, 0, 120), fill=(0, 0, 0, 0),
                tag=debug_tag, parent=drawlist,
            )
        elif pos["shape"] == "rect":
            x, y, w, h = pos["x"], pos["y"], pos["w"], pos["h"]
            dpg.draw_rectangle(
                (x, y), (x + w, y + h),
                color=(255, 0, 0, 120), fill=(0, 0, 0, 0),
                rounding=4, tag=debug_tag, parent=drawlist,
            )
```

- [ ] **Step 2: Run the app and visually verify hotspot alignment**

```bash
cd D:/Games/Workshop/CD_REMAPPER && python -m tools.cd_remap
```

Red outlines should appear over each button area on the controller image. Adjust any `BUTTON_POSITIONS` coordinates where the red outline doesn't align with the image's button. Pay special attention to:
- Face buttons (A/B/X/Y) — circles must center on the colored button circles
- D-pad — rectangles must cover the cross arms
- Shoulders/triggers — rectangles must align with the bumper/trigger shapes
- Stick clicks — small circles must center inside the stick rings

- [ ] **Step 3: Update coordinates as needed**

Edit `BUTTON_POSITIONS` values based on visual inspection. Iterate: adjust → save → check app → repeat until all hotspots align.

- [ ] **Step 4: Remove debug flag**

Set `_DEBUG_HOTSPOTS = False` (or remove the debug code entirely). Remove the debug drawing block from `draw_button()`.

- [ ] **Step 5: Commit**

```bash
git add tools/cd_remap/controller_draw.py
git commit -m "fix: calibrate button hotspot positions to match controller image"
```

---

### Task 5: Update gui.py — texture loading and drawlist resize

**Files:**
- Modify: `tools/cd_remap/gui.py`

Wire up the image texture loading at startup and update all drawlist size references.

- [ ] **Step 1: Add import for asset_path and draw_controller_image**

At the top of `gui.py`, update imports:

```python
from .asset_util import asset_path
```

Update the `controller_draw` import block — replace `draw_controller_body` with `draw_controller_image`:

```python
from .controller_draw import (
    CLICKABLE_BUTTONS,
    draw_controller_image,
    draw_all_buttons,
    draw_all_action_labels,
    hit_test,
    update_button_color,
    COLOR_DEFAULT,
    COLOR_HOVER,
    COLOR_SELECTED,
)
```

- [ ] **Step 2: Add texture loading in the GUI __init__ or build method**

In the `RemapperGUI` class, add a method to load the controller texture. This must be called after `dpg.create_context()` but before drawing. Find the `_build_gui` method and add texture loading before the drawlist creation:

```python
def _load_controller_texture(self):
    """Load the controller image as a DPG static texture."""
    img_path = str(asset_path("controller.png"))
    width, height, channels, data = dpg.load_image(img_path)
    with dpg.texture_registry():
        dpg.add_static_texture(
            width, height, data,
            tag="controller_texture",
        )
```

Call `self._load_controller_texture()` early in `_build_gui()`, before the drawlist is created.

- [ ] **Step 3: Update drawlist creation — size and drawing calls**

In `_build_gui()`, find the drawlist creation block (currently around line 534):

Replace:
```python
self.drawlist = dpg.add_drawlist(width=450, height=300, tag="controller_drawlist")
draw_controller_body(self.drawlist)
draw_all_buttons(self.drawlist, labels)
```

With:
```python
self.drawlist = dpg.add_drawlist(width=500, height=358, tag="controller_drawlist")
draw_controller_image(self.drawlist, "controller_texture")
draw_all_buttons(self.drawlist)
```

Note: `draw_all_buttons` no longer takes `labels` — button labels come from the image. Action labels are drawn separately below (existing `draw_all_action_labels` call if present, or add after).

- [ ] **Step 4: Update drawlist bounds checks**

Two places in `gui.py` check `450` and `300` as drawlist bounds. Update both:

In `_on_controller_click` (around line 132):
```python
if not (0 <= mouse_pos[0] <= 500 and 0 <= mouse_pos[1] <= 358):
```

In `_on_mouse_move` (around line 200):
```python
in_drawlist = 0 <= mouse_pos[0] <= 500 and 0 <= mouse_pos[1] <= 358
```

- [ ] **Step 5: Update COLOR_CHANGED for transparent overlay**

In `gui.py`, the `COLOR_CHANGED` constant (line 51) should use alpha for overlay mode:

```python
COLOR_CHANGED = (0, 200, 200, 80)
```

- [ ] **Step 6: Update draw_all_buttons call in _build_gui**

The current `draw_all_buttons` takes an optional `labels` dict for button text. Since the image already shows button letters, we no longer pass labels:

Check that `draw_all_buttons(self.drawlist)` is called without the `labels` argument. The function signature already has `labels=None` as default, so this works.

After `draw_all_buttons`, add the action labels:

```python
draw_all_action_labels(self.drawlist, labels)
```

- [ ] **Step 7: Run tests**

```bash
python -m pytest tests/ -v --tb=short
```

Expected: All tests pass.

- [ ] **Step 8: Commit**

```bash
git add tools/cd_remap/gui.py
git commit -m "feat: load controller texture and wire up image-based drawlist"
```

---

### Task 6: Update PyInstaller build spec

**Files:**
- Modify: `build/cd_remap.spec`

- [ ] **Step 1: Add the controller image to datas**

In `build/cd_remap.spec`, after the existing `datas = []` line (line 4), add the asset:

```python
datas = [('D:\\Games\\Workshop\\CD_REMAPPER\\assets\\controller.png', 'assets')]
```

Also add the `asset_util` hidden import to the `hiddenimports` list:

```python
hiddenimports = [...existing imports..., 'cd_remap.asset_util']
```

- [ ] **Step 2: Build the exe**

```bash
cd D:/Games/Workshop/CD_REMAPPER/build && python -m PyInstaller cd_remap.spec --noconfirm
```

- [ ] **Step 3: Test the built exe**

```bash
./build/dist/cd_remap.exe
```

Verify:
- Controller image loads and displays
- Hotspots are clickable
- Action labels appear correctly
- All tabs (Combat/Menus/Horse) work

- [ ] **Step 4: Commit**

```bash
git add build/cd_remap.spec
git commit -m "chore: bundle controller image in PyInstaller build"
```

---

### Task 7: Final integration verification

- [ ] **Step 1: Run full test suite**

```bash
cd D:/Games/Workshop/CD_REMAPPER && python -m pytest tests/ -v
```

Expected: All tests pass (97 tests — 95 existing + 3 new asset_path tests, minus any removed, plus 2 skipped integration).

- [ ] **Step 2: Manual verification checklist**

Run the app: `python -m tools.cd_remap`

Verify each of these:
- [ ] Controller image renders with no stretching or cropping
- [ ] Hovering each button shows a subtle highlight overlay
- [ ] Clicking a button while an action is selected assigns it
- [ ] Changed buttons show the cyan highlight color
- [ ] Action labels (Sprint, Dodge, etc.) appear near correct buttons
- [ ] All 3 context tabs (Combat, Menus, Horse) switch correctly
- [ ] Presets load and highlight changed buttons
- [ ] Escape cancels selection
- [ ] Apply/Undo buttons still work (PAZ patching)

- [ ] **Step 3: Commit any final adjustments**

```bash
git add -A
git commit -m "feat: Xbox controller image background with hotspot overlays"
```

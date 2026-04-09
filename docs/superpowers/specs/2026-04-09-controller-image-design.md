# Controller Image Background Design

**Date:** 2026-04-09
**Status:** Proposed
**Goal:** Replace the primitive-drawn controller schematic with a real Xbox controller image for a polished look.

---

## Approach

Use a CC0 Xbox 360 controller SVG (Wikimedia Commons) as a raster background image in the DPG drawlist. Clickable button regions become transparent hotspot overlays drawn on top of the image. All existing interaction logic (hit_test, hover/selected colors, action labels) remains unchanged.

## Image Asset

- **Source:** [Xbox360_gamepad.svg](https://commons.wikimedia.org/wiki/File:Xbox360_gamepad.svg) by Grumbel (Open Clip Art Library)
- **License:** CC0 1.0 Universal (Public Domain)
- **Native size:** 751 x 537 px
- **Format:** Pre-render SVG to PNG at 2x resolution (1000 x 716) for crisp display. Bundle the PNG in `assets/controller.png`.
- **Why PNG not SVG at runtime:** DPG has no SVG renderer. `dpg.load_image()` supports PNG/JPEG/BMP.

## Architecture Changes

### controller_draw.py — what changes

| Current | New |
|---|---|
| `draw_controller_body()` — 3 rectangles (body + grips) | `draw_controller_image()` — single `dpg.draw_image()` call with the loaded texture |
| `draw_button()` — filled circles/rects with borders and labels | `draw_hotspot()` — transparent shapes (alpha ~0) that only show fill on hover/selected state |
| `BUTTON_POSITIONS` — coordinates for schematic layout (450x300) | `BUTTON_POSITIONS` — re-measured coordinates matching the image (new drawlist size) |
| `_LABEL_OFFSETS` — offsets relative to schematic positions | `_LABEL_OFFSETS` — re-measured for image layout |

### controller_draw.py — what stays the same

- `hit_test()` — same point-in-circle/rect math, just different coordinates
- `update_button_color()` — same `dpg.configure_item(tag, fill=color)` on hotspot shapes
- `draw_action_label()` / `draw_all_action_labels()` — same text drawing, repositioned
- `CLICKABLE_BUTTONS` — same list (still excludes ring shapes)
- `PAIR_COLORS`, `COLOR_DEFAULT`, `COLOR_HOVER`, `COLOR_SELECTED` — unchanged

### gui.py

- Load texture at startup: `dpg.load_image("assets/controller.png")` → register as static texture
- Resize drawlist to match image aspect ratio (~500 x 358 at display scale)
- No other GUI logic changes — all click handling, tab switching, action assignment flows stay the same

### PyInstaller build

- Add to `datas` list in `build/cd_remap.spec`: `('D:\\Games\\Workshop\\CD_REMAPPER\\assets\\controller.png', 'assets')`
- Add an `asset_path()` helper to resolve the image path at runtime — checks `sys._MEIPASS` (PyInstaller bundle) first, falls back to source tree path. No existing pattern for this in the codebase, so this is new.

## Drawlist Sizing

Current drawlist: 450 x 300 (1.5:1 aspect ratio).
Image aspect: 751 x 537 (1.4:1).

New drawlist: **500 x 358** — scales the image down from native while preserving aspect ratio. Slightly wider than current, minimal GUI layout impact.

## Hotspot Overlay Behavior

Buttons are drawn as **transparent shapes** positioned over the image's button locations:
- **Default state:** fully transparent fill `(0, 0, 0, 0)` — image shows through
- **Hover state:** semi-transparent highlight `(140, 140, 140, 80)` — subtle glow over the button
- **Selected state:** brighter overlay `(255, 255, 255, 100)` — clear selection indicator
- **Remapped state:** pair color overlay with alpha `(r, g, b, 80)` — shows which buttons are swapped

Circle hotspots for face buttons (A/B/X/Y) and stick clicks (LS/RS). Rectangle hotspots for shoulders (LB/RB), triggers (LT/RT), d-pad, and meta buttons (Select/Start).

## Button Position Mapping

All coordinates must be re-measured against the rendered PNG. The mapping process:
1. Render SVG to PNG at target resolution
2. Open in an image editor, measure center (x, y) and radius/dimensions for each button
3. Update `BUTTON_POSITIONS` dict with new values
4. Verify hit_test accuracy by running the app and clicking each button

## Asset Pipeline

1. Download SVG (already done: `assets/xbox360_gamepad.svg`)
2. Render to PNG: `cairosvg` or Inkscape CLI (`inkscape --export-type=png --export-width=1000`)
3. Commit PNG to `assets/controller.png`
4. Add SVG source to `assets/` for reference (not used at runtime)

## Testing

- Existing tests don't test drawing (DPG drawlist calls are visual-only)
- `hit_test()` tests should be updated with new coordinates if any exist
- Manual verification: hover each button, confirm highlights align with image
- PyInstaller build: confirm image loads from bundled exe

## Files Modified

| File | Change |
|---|---|
| `tools/cd_remap/controller_draw.py` | Replace body/button drawing with image + hotspots, update all coordinates |
| `tools/cd_remap/gui.py` | Load texture at startup, resize drawlist |
| `assets/controller.png` | New file — pre-rendered controller image |
| `assets/xbox360_gamepad.svg` | New file — source SVG for reference |
| PyInstaller spec / build script | Add `--add-data` for assets |

## Out of Scope

- Modifying the SVG itself (color changes, removing labels, etc.) — use as-is unless it looks wrong at runtime
- Animation or transition effects
- Multiple controller skins/themes
- Dynamic SVG rendering

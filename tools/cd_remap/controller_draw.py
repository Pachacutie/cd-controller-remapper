"""Draw an interactive Xbox-style controller on a Dear PyGui drawlist."""
import dearpygui.dearpygui as dpg

COLOR_DEFAULT = (0, 0, 0, 0)          # Transparent — image shows through
COLOR_BORDER = (0, 0, 0, 0)           # No border on hotspots
COLOR_HOVER = (0, 180, 255, 140)      # Blue glow on hover
COLOR_SELECTED = (255, 180, 0, 230)   # Yellow/gold selection indicator
COLOR_LABEL = (180, 180, 180, 255)
COLOR_LINE = (100, 100, 100, 140)
COLOR_LABEL_HOVER = (255, 255, 255, 255)
COLOR_LINE_HOVER = (0, 180, 255, 220)
COLOR_LABEL_SELECTED = (255, 200, 0, 255)
COLOR_LINE_SELECTED = (255, 180, 0, 230)

# Margin added to each side for external labels with leader lines
LABEL_MARGIN = 100

# Button positions — raw coords calibrated for image at (40,30) size (420,300)
_RAW_BUTTON_POSITIONS = {
    "buttonA": {"x": 370, "y": 131, "r": 16, "shape": "circle", "label": "A"},
    "buttonB": {"x": 402, "y": 101, "r": 16, "shape": "circle", "label": "B"},
    "buttonX": {"x": 341, "y": 99, "r": 16, "shape": "circle", "label": "X"},
    "buttonY": {"x": 373, "y": 70, "r": 16, "shape": "circle", "label": "Y"},
    "buttonLB": {"x": 111, "y": 25, "w": 56, "h": 22, "shape": "rect", "label": "LB"},
    "buttonRB": {"x": 351, "y": 29, "w": 56, "h": 22, "shape": "rect", "label": "RB"},
    "buttonLT": {"x": 111, "y": 3, "w": 56, "h": 22, "shape": "rect", "label": "LT"},
    "buttonRT": {"x": 351, "y": 7, "w": 56, "h": 22, "shape": "rect", "label": "RT"},
    "buttonLS": {"x": 131, "y": 96, "r": 12, "shape": "circle", "label": "LS"},
    "buttonRS": {"x": 314, "y": 168, "r": 12, "shape": "circle", "label": "RS"},
    "leftstick": {"x": 131, "y": 96, "r": 30, "shape": "ring", "label": "L"},
    "rightstick": {"x": 314, "y": 168, "r": 30, "shape": "ring", "label": "R"},
    "padU": {"x": 177, "y": 129, "w": 20, "h": 20, "shape": "rect", "label": "^"},
    "padD": {"x": 180, "y": 182, "w": 20, "h": 20, "shape": "rect", "label": "v"},
    "padL": {"x": 155, "y": 156, "w": 20, "h": 20, "shape": "rect", "label": "<"},
    "padR": {"x": 207, "y": 157, "w": 20, "h": 20, "shape": "rect", "label": ">"},
    "select": {"x": 195, "y": 94, "w": 28, "h": 18, "shape": "rect", "label": "Sel"},
    "start": {"x": 282, "y": 94, "w": 28, "h": 18, "shape": "rect", "label": "Sta"},
}

# Build shifted positions (add LABEL_MARGIN to all x coords)
BUTTON_POSITIONS = {}
for _bid, _raw in _RAW_BUTTON_POSITIONS.items():
    _shifted = dict(_raw)
    _shifted["x"] = _raw["x"] + LABEL_MARGIN
    BUTTON_POSITIONS[_bid] = _shifted

CLICKABLE_BUTTONS = [b for b in BUTTON_POSITIONS if BUTTON_POSITIONS[b]["shape"] != "ring"]

IMG_OFFSET = (40 + LABEL_MARGIN, 30)
IMG_SIZE = (420, 300)

DRAWLIST_W = 500 + 2 * LABEL_MARGIN
DRAWLIST_H = 358


def _btn_center(btn_id: str) -> tuple[float, float]:
    pos = BUTTON_POSITIONS[btn_id]
    if pos["shape"] in ("circle", "ring"):
        return pos["x"], pos["y"]
    return pos["x"] + pos["w"] / 2, pos["y"] + pos["h"] / 2


def draw_controller_image(drawlist: int | str, texture_tag: str):
    x0, y0 = IMG_OFFSET
    dpg.draw_image(
        texture_tag,
        (x0, y0), (x0 + IMG_SIZE[0], y0 + IMG_SIZE[1]),
        parent=drawlist,
    )


def draw_button(drawlist: int | str, btn_id: str, color: tuple = (0, 0, 0, 0),
                border: tuple = (0, 0, 0, 0)) -> int | str:
    pos = BUTTON_POSITIONS[btn_id]
    tag = f"btn_{btn_id}"

    if pos["shape"] == "circle":
        dpg.draw_circle(
            (pos["x"], pos["y"]), pos["r"],
            color=border, fill=color,
            tag=tag, parent=drawlist,
        )
    elif pos["shape"] == "ring":
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


def draw_all_buttons(drawlist: int | str) -> dict[str, str]:
    tags = {}
    for btn_id in BUTTON_POSITIONS:
        tags[btn_id] = draw_button(drawlist, btn_id)
    return tags


def hit_test(mx: float, my: float) -> str | None:
    for btn_id in CLICKABLE_BUTTONS:
        pos = BUTTON_POSITIONS[btn_id]
        if pos["shape"] == "circle":
            dx = mx - pos["x"]
            dy = my - pos["y"]
            if dx * dx + dy * dy <= pos["r"] * pos["r"]:
                return btn_id
        elif pos["shape"] == "rect":
            if (pos["x"] <= mx <= pos["x"] + pos["w"]
                    and pos["y"] <= my <= pos["y"] + pos["h"]):
                return btn_id
    return None


def update_button_color(drawlist: int | str, btn_id: str, color: tuple):
    tag = f"btn_{btn_id}"
    try:
        dpg.configure_item(tag, fill=color)
    except Exception:
        pass


# --- Leader-line label system ---

_LEFT_BUTTONS = [
    "buttonLT", "buttonLB", "select", "buttonLS",
    "padU", "padL", "padR", "padD",
]
_RIGHT_BUTTONS = [
    "buttonRT", "buttonRB", "buttonY", "start",
    "buttonX", "buttonB", "buttonA", "buttonRS",
]

_LABEL_FONT_SIZE = 13
_LABEL_SPACING = 24
_LABEL_TOP = 12
_LEFT_X = 5
_RIGHT_X = DRAWLIST_W - 90
_CHAR_WIDTH = 7  # estimated px per char at font size 13

# Label bounds for hit testing: {btn_id: (x1, y1, x2, y2)}
_label_bounds: dict[str, tuple[float, float, float, float]] = {}


def _label_y(index: int) -> float:
    return _LABEL_TOP + index * _LABEL_SPACING


def draw_action_label(drawlist: int | str, btn_id: str, label: str):
    """Draw a label with underline and leader line to its button."""
    if btn_id not in BUTTON_POSITIONS or not label:
        return

    tag = f"lbl_{btn_id}"
    try:
        dpg.delete_item(tag)
    except Exception:
        pass

    is_left = btn_id in _LEFT_BUTTONS
    if is_left:
        idx = _LEFT_BUTTONS.index(btn_id)
        text_x = _LEFT_X
    elif btn_id in _RIGHT_BUTTONS:
        idx = _RIGHT_BUTTONS.index(btn_id)
        text_x = _RIGHT_X
    else:
        return

    text_y = _label_y(idx)
    text_w = len(label) * _CHAR_WIDTH
    underline_y = text_y + _LABEL_FONT_SIZE + 2
    btn_cx, btn_cy = _btn_center(btn_id)

    # Leader line connects from the underline end nearest the controller
    if is_left:
        anchor_x = text_x + text_w
    else:
        anchor_x = text_x

    # Store bounds for hover hit testing (generous vertical padding)
    _label_bounds[btn_id] = (text_x, text_y - 2, text_x + text_w, underline_y + 4)

    node = dpg.add_draw_node(tag=tag, parent=drawlist)

    # Leader line: underline endpoint → button center
    dpg.draw_line(
        (anchor_x, underline_y), (btn_cx, btn_cy),
        color=COLOR_LINE, thickness=1,
        tag=f"lbl_{btn_id}_line", parent=node,
    )

    # Dot at button end
    dpg.draw_circle(
        (btn_cx, btn_cy), 3,
        color=COLOR_LINE, fill=COLOR_LINE,
        tag=f"lbl_{btn_id}_dot", parent=node,
    )

    # Underline beneath label text
    dpg.draw_line(
        (text_x, underline_y), (text_x + text_w, underline_y),
        color=COLOR_LINE, thickness=1,
        tag=f"lbl_{btn_id}_underline", parent=node,
    )

    # Label text
    dpg.draw_text(
        (text_x, text_y), label,
        color=COLOR_LABEL, size=_LABEL_FONT_SIZE,
        tag=f"lbl_{btn_id}_text", parent=node,
    )


def draw_all_action_labels(drawlist: int | str, labels: dict[str, str]):
    """Draw action labels for all buttons that have one."""
    all_slots = list(_LEFT_BUTTONS) + list(_RIGHT_BUTTONS)
    for btn_id in all_slots:
        if btn_id not in labels:
            try:
                dpg.delete_item(f"lbl_{btn_id}")
            except Exception:
                pass
            _label_bounds.pop(btn_id, None)
    for btn_id, label in labels.items():
        draw_action_label(drawlist, btn_id, label)


def label_hit_test(mx: float, my: float) -> str | None:
    """Return the btn_id if mouse is over a label, else None."""
    for btn_id, (x1, y1, x2, y2) in _label_bounds.items():
        if x1 <= mx <= x2 and y1 <= my <= y2:
            return btn_id
    return None


def highlight_label(btn_id: str):
    """Set label, underline, and leader line to hover colors."""
    try:
        dpg.configure_item(f"lbl_{btn_id}_text", color=COLOR_LABEL_HOVER)
        dpg.configure_item(f"lbl_{btn_id}_underline", color=COLOR_LINE_HOVER)
        dpg.configure_item(f"lbl_{btn_id}_line", color=COLOR_LINE_HOVER, thickness=2)
        dpg.configure_item(f"lbl_{btn_id}_dot", color=COLOR_LINE_HOVER, fill=COLOR_LINE_HOVER)
    except Exception:
        pass


def unhighlight_label(btn_id: str):
    """Restore label, underline, and leader line to default colors."""
    try:
        dpg.configure_item(f"lbl_{btn_id}_text", color=COLOR_LABEL)
        dpg.configure_item(f"lbl_{btn_id}_underline", color=COLOR_LINE)
        dpg.configure_item(f"lbl_{btn_id}_line", color=COLOR_LINE, thickness=1)
        dpg.configure_item(f"lbl_{btn_id}_dot", color=COLOR_LINE, fill=COLOR_LINE)
    except Exception:
        pass


def select_label(btn_id: str):
    """Set label, underline, and leader line to selection (gold) colors."""
    try:
        dpg.configure_item(f"lbl_{btn_id}_text", color=COLOR_LABEL_SELECTED)
        dpg.configure_item(f"lbl_{btn_id}_underline", color=COLOR_LINE_SELECTED)
        dpg.configure_item(f"lbl_{btn_id}_line", color=COLOR_LINE_SELECTED, thickness=2)
        dpg.configure_item(f"lbl_{btn_id}_dot", color=COLOR_LINE_SELECTED, fill=COLOR_LINE_SELECTED)
    except Exception:
        pass

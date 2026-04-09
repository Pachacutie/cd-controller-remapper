"""Draw an interactive Xbox-style controller on a Dear PyGui drawlist."""
import dearpygui.dearpygui as dpg

COLOR_DEFAULT = (0, 0, 0, 0)          # Transparent — image shows through
COLOR_BORDER = (0, 0, 0, 0)           # No border on hotspots
COLOR_HOVER = (0, 180, 255, 140)      # Blue glow on hover
COLOR_SELECTED = (255, 200, 0, 180)   # Yellow/gold selection indicator
COLOR_LABEL = (180, 180, 180, 255)

# Button positions relative to drawlist origin (0,0 = top-left)
# Drawlist size: 500 x 358
# Image drawn at offset (40,30) size (420,300) — see IMG_OFFSET / IMG_SIZE
# Coordinates calibrated from user clicks on the rendered image
BUTTON_POSITIONS = {
    # Face buttons — right cluster
    "buttonA": {"x": 370, "y": 131, "r": 16, "shape": "circle", "label": "A"},
    "buttonB": {"x": 402, "y": 101, "r": 16, "shape": "circle", "label": "B"},
    "buttonX": {"x": 341, "y": 99, "r": 16, "shape": "circle", "label": "X"},
    "buttonY": {"x": 373, "y": 70, "r": 16, "shape": "circle", "label": "Y"},
    # Shoulder buttons
    "buttonLB": {"x": 111, "y": 25, "w": 56, "h": 22, "shape": "rect", "label": "LB"},
    "buttonRB": {"x": 351, "y": 29, "w": 56, "h": 22, "shape": "rect", "label": "RB"},
    # Triggers (above shoulders — partially hidden, use same x as LB/RB)
    "buttonLT": {"x": 111, "y": 3, "w": 56, "h": 22, "shape": "rect", "label": "LT"},
    "buttonRT": {"x": 351, "y": 7, "w": 56, "h": 22, "shape": "rect", "label": "RT"},
    # Stick clicks
    "buttonLS": {"x": 131, "y": 96, "r": 12, "shape": "circle", "label": "LS"},
    "buttonRS": {"x": 314, "y": 168, "r": 12, "shape": "circle", "label": "RS"},
    # Analog sticks (outer rings — visual only, not clickable)
    "leftstick": {"x": 131, "y": 96, "r": 30, "shape": "ring", "label": "L"},
    "rightstick": {"x": 314, "y": 168, "r": 30, "shape": "ring", "label": "R"},
    # D-pad
    "padU": {"x": 177, "y": 129, "w": 20, "h": 20, "shape": "rect", "label": "^"},
    "padD": {"x": 180, "y": 182, "w": 20, "h": 20, "shape": "rect", "label": "v"},
    "padL": {"x": 155, "y": 156, "w": 20, "h": 20, "shape": "rect", "label": "<"},
    "padR": {"x": 207, "y": 157, "w": 20, "h": 20, "shape": "rect", "label": ">"},
    # Meta
    "select": {"x": 195, "y": 94, "w": 28, "h": 18, "shape": "rect", "label": "Sel"},
    "start": {"x": 282, "y": 94, "w": 28, "h": 18, "shape": "rect", "label": "Sta"},
}

# Buttons that are clickable (excludes analog stick rings which are visual)
CLICKABLE_BUTTONS = [b for b in BUTTON_POSITIONS if BUTTON_POSITIONS[b]["shape"] != "ring"]


# Image drawn with margins so triggers fit and labels have room
IMG_OFFSET = (40, 30)  # (x, y) top-left margin
IMG_SIZE = (420, 300)   # display size within the 500x358 drawlist


def draw_controller_image(drawlist: int | str, texture_tag: str):
    """Draw the controller image as the drawlist background."""
    x0, y0 = IMG_OFFSET
    dpg.draw_image(
        texture_tag,
        (x0, y0), (x0 + IMG_SIZE[0], y0 + IMG_SIZE[1]),
        parent=drawlist,
    )


def draw_button(drawlist: int | str, btn_id: str, color: tuple = (0, 0, 0, 0),
                border: tuple = (0, 0, 0, 0)) -> int | str:
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
    """Draw all button hotspot overlays on the controller. Returns {btn_id: item_tag}."""
    tags = {}
    for btn_id in BUTTON_POSITIONS:
        tags[btn_id] = draw_button(drawlist, btn_id)
    return tags


def hit_test(mx: float, my: float) -> str | None:
    """Given mouse coords relative to drawlist, return the clicked button ID or None."""
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
    """Update the fill color of an already-drawn button."""
    tag = f"btn_{btn_id}"
    try:
        dpg.configure_item(tag, fill=color)
    except Exception:
        pass  # Button may not be drawn yet during init


# Label offsets relative to button center (dx, dy)
_LABEL_OFFSETS = {
    "buttonA": (20, 4), "buttonB": (20, 4), "buttonX": (-56, 4), "buttonY": (20, -4),
    "buttonLB": (0, 24), "buttonRB": (0, 24),
    "buttonLT": (0, -14), "buttonRT": (0, -14),
    "buttonLS": (-16, 34), "buttonRS": (-16, 34),
    "select": (-4, 22), "start": (-4, 22),
}


def draw_action_label(drawlist: int | str, btn_id: str, label: str):
    """Draw or update an action label near a button."""
    if btn_id not in BUTTON_POSITIONS or not label:
        return
    tag = f"lbl_{btn_id}"
    pos = BUTTON_POSITIONS[btn_id]
    dx, dy = _LABEL_OFFSETS.get(btn_id, (20, 0))

    x, y = pos["x"] + dx, pos["y"] + dy

    # Delete old label if exists, then redraw
    try:
        dpg.delete_item(tag)
    except Exception:
        pass

    dpg.draw_text(
        (x, y), label, color=COLOR_LABEL, size=10,
        tag=tag, parent=drawlist,
    )


def draw_all_action_labels(drawlist: int | str, labels: dict[str, str]):
    """Draw action labels for all buttons that have one."""
    for btn_id, label in labels.items():
        draw_action_label(drawlist, btn_id, label)

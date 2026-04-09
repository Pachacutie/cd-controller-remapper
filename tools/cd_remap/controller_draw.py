"""Draw an interactive Xbox-style controller on a Dear PyGui drawlist."""
import dearpygui.dearpygui as dpg

# Pair accent colors — assigned to swap pairs in order
PAIR_COLORS = [
    (0, 200, 200, 255),    # cyan
    (255, 165, 0, 255),    # orange
    (200, 0, 200, 255),    # magenta
    (100, 255, 100, 255),  # green
    (255, 100, 100, 255),  # red
    (100, 100, 255, 255),  # blue
    (255, 255, 0, 255),    # yellow
    (200, 150, 255, 255),  # lavender
    (255, 200, 150, 255),  # peach
]

COLOR_DEFAULT = (0, 0, 0, 0)          # Transparent — image shows through
COLOR_BORDER = (0, 0, 0, 0)           # No border on hotspots
COLOR_HOVER = (180, 180, 180, 60)     # Subtle white glow
COLOR_SELECTED = (255, 255, 255, 90)  # Brighter selection indicator
COLOR_LABEL = (180, 180, 180, 255)
COLOR_BODY = (45, 45, 50, 255)
COLOR_BODY_BORDER = (90, 90, 100, 255)

# Button positions relative to drawlist origin (0,0 = top-left)
# Drawlist size: 500 x 358
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
    # Stick clicks (small circles inside stick outlines)
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

# Buttons that are clickable (excludes analog stick rings which are visual)
CLICKABLE_BUTTONS = [b for b in BUTTON_POSITIONS if BUTTON_POSITIONS[b]["shape"] != "ring"]


def draw_controller_image(drawlist: int | str, texture_tag: str):
    """Draw the controller image as the drawlist background."""
    dpg.draw_image(
        texture_tag, (0, 0), (500, 358),
        parent=drawlist,
    )


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


def draw_all_buttons(drawlist: int | str, labels: dict[str, str] | None = None) -> dict[str, str]:
    """Draw all buttons on the controller. Returns {btn_id: item_tag}."""
    tags = {}
    for btn_id in BUTTON_POSITIONS:
        label_override = labels.get(btn_id) if labels else None
        tags[btn_id] = draw_button(drawlist, btn_id, label_override=label_override)
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


def get_pair_color(pair_index: int) -> tuple:
    """Get accent color for swap pair N (wraps around if >9 pairs)."""
    return PAIR_COLORS[pair_index % len(PAIR_COLORS)]


# Label offsets relative to button center (dx, dy)
_LABEL_OFFSETS = {
    "buttonA": (20, 4), "buttonB": (20, 4), "buttonX": (-50, 4), "buttonY": (20, -2),
    "buttonLB": (0, 24), "buttonRB": (0, 24),
    "buttonLT": (0, 24), "buttonRT": (0, 24),
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

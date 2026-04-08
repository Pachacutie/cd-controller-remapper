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

COLOR_DEFAULT = (80, 80, 80, 255)
COLOR_BORDER = (160, 160, 160, 255)
COLOR_HOVER = (140, 140, 140, 255)
COLOR_SELECTED = (255, 255, 255, 255)
COLOR_LABEL = (180, 180, 180, 255)
COLOR_BODY = (45, 45, 50, 255)
COLOR_BODY_BORDER = (90, 90, 100, 255)

# Button positions relative to drawlist origin (0,0 = top-left)
# Drawlist size: 450 x 300
BUTTON_POSITIONS = {
    # Face buttons — right cluster
    "buttonA": {"x": 330, "y": 195, "r": 16, "shape": "circle", "label": "A"},
    "buttonB": {"x": 362, "y": 163, "r": 16, "shape": "circle", "label": "B"},
    "buttonX": {"x": 298, "y": 163, "r": 16, "shape": "circle", "label": "X"},
    "buttonY": {"x": 330, "y": 131, "r": 16, "shape": "circle", "label": "Y"},
    # Shoulder buttons
    "buttonLB": {"x": 80, "y": 52, "w": 60, "h": 24, "shape": "rect", "label": "LB"},
    "buttonRB": {"x": 310, "y": 52, "w": 60, "h": 24, "shape": "rect", "label": "RB"},
    # Triggers
    "buttonLT": {"x": 80, "y": 20, "w": 60, "h": 24, "shape": "rect", "label": "LT"},
    "buttonRT": {"x": 310, "y": 20, "w": 60, "h": 24, "shape": "rect", "label": "RT"},
    # Stick clicks (small circles inside stick outlines)
    "buttonLS": {"x": 150, "y": 145, "r": 10, "shape": "circle", "label": "LS"},
    "buttonRS": {"x": 280, "y": 215, "r": 10, "shape": "circle", "label": "RS"},
    # Analog sticks (outer rings — visual only, not clickable)
    "leftstick": {"x": 150, "y": 145, "r": 28, "shape": "ring", "label": "L"},
    "rightstick": {"x": 280, "y": 215, "r": 28, "shape": "ring", "label": "R"},
    # D-pad
    "padU": {"x": 138, "y": 197, "w": 22, "h": 22, "shape": "rect", "label": "^"},
    "padD": {"x": 138, "y": 241, "w": 22, "h": 22, "shape": "rect", "label": "v"},
    "padL": {"x": 116, "y": 219, "w": 22, "h": 22, "shape": "rect", "label": "<"},
    "padR": {"x": 160, "y": 219, "w": 22, "h": 22, "shape": "rect", "label": ">"},
    # Meta
    "select": {"x": 190, "y": 135, "w": 30, "h": 18, "shape": "rect", "label": "Sel"},
    "start": {"x": 230, "y": 135, "w": 30, "h": 18, "shape": "rect", "label": "Sta"},
}

# Buttons that are clickable (excludes analog stick rings which are visual)
CLICKABLE_BUTTONS = [b for b in BUTTON_POSITIONS if BUTTON_POSITIONS[b]["shape"] != "ring"]


def draw_controller_body(drawlist: int | str):
    """Draw the controller body outline."""
    # Main body — rounded rectangle
    dpg.draw_rectangle(
        (30, 70), (420, 280),
        color=COLOR_BODY_BORDER, fill=COLOR_BODY,
        rounding=30, parent=drawlist,
    )
    # Left grip
    dpg.draw_rectangle(
        (30, 150), (90, 290),
        color=COLOR_BODY_BORDER, fill=COLOR_BODY,
        rounding=20, parent=drawlist,
    )
    # Right grip
    dpg.draw_rectangle(
        (360, 150), (420, 290),
        color=COLOR_BODY_BORDER, fill=COLOR_BODY,
        rounding=20, parent=drawlist,
    )


def draw_button(drawlist: int | str, btn_id: str, color: tuple = COLOR_DEFAULT,
                border: tuple = COLOR_BORDER, label_override: str | None = None) -> int | str:
    """Draw a single button. Returns the drawn item tag for later color updates."""
    pos = BUTTON_POSITIONS[btn_id]
    tag = f"btn_{btn_id}"
    label = label_override if label_override is not None else pos["label"]

    if pos["shape"] == "circle":
        dpg.draw_circle(
            (pos["x"], pos["y"]), pos["r"],
            color=border, fill=color,
            tag=tag, parent=drawlist,
        )
        # Center label text (approximate)
        text_x = pos["x"] - len(label) * 3
        text_y = pos["y"] - 6
        dpg.draw_text(
            (text_x, text_y), label,
            color=(255, 255, 255, 255), size=11,
            parent=drawlist,
        )
    elif pos["shape"] == "ring":
        dpg.draw_circle(
            (pos["x"], pos["y"]), pos["r"],
            color=border, fill=(0, 0, 0, 0),
            tag=tag, parent=drawlist,
        )
    elif pos["shape"] == "rect":
        x, y, w, h = pos["x"], pos["y"], pos["w"], pos["h"]
        dpg.draw_rectangle(
            (x, y), (x + w, y + h),
            color=border, fill=color,
            rounding=4, tag=tag, parent=drawlist,
        )
        dpg.draw_text(
            (x + 3, y + 2), label,
            color=(255, 255, 255, 255), size=10,
            parent=drawlist,
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
    "buttonA": (18, 4), "buttonB": (18, 4), "buttonX": (-46, 4), "buttonY": (18, -2),
    "buttonLB": (0, 26), "buttonRB": (0, 26),
    "buttonLT": (0, 26), "buttonRT": (0, 26),
    "buttonLS": (-14, 26), "buttonRS": (-14, 32),
    "select": (-4, 20), "start": (-4, 20),
}


def draw_action_label(drawlist: int | str, btn_id: str, label: str):
    """Draw or update an action label near a button."""
    if btn_id not in BUTTON_POSITIONS or not label:
        return
    tag = f"lbl_{btn_id}"
    pos = BUTTON_POSITIONS[btn_id]
    dx, dy = _LABEL_OFFSETS.get(btn_id, (20, 0))

    if pos["shape"] == "circle":
        x, y = pos["x"] + dx, pos["y"] + dy
    else:
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

"""Action registry — Crimson Desert control scheme and remap logic."""
from dataclasses import dataclass


@dataclass
class GameAction:
    name: str
    default_btn: str
    short_label: str  # Max 8 chars for controller diagram


ALL_CONTEXTS = ["combat", "menus", "horse"]

COMBAT_ACTIONS = [
    GameAction("Sprint/Run",   "buttonA",  "Sprint"),
    GameAction("Dodge/Roll",   "buttonB",  "Dodge"),
    GameAction("Jump",         "buttonX",  "Jump"),
    GameAction("Kick/Unarmed", "buttonY",  "Kick"),
    GameAction("Block/Parry",  "buttonLB", "Block"),
    GameAction("Basic Attack", "buttonRB", "Attack"),
    GameAction("Aim Ranged",   "buttonLT", "Aim"),
    GameAction("Power Attack", "buttonRT", "Power"),
    GameAction("Crouch/Slide", "buttonLS", "Crouch"),
    GameAction("Force Palm",   "buttonRS", "Force"),
    GameAction("Summon Horse", "padU",     "Horse"),
    GameAction("Sheathe",      "padL",     "Sheathe"),
    GameAction("Eat Food",     "padR",     "Food"),
    GameAction("Camera Lock",  "padD",     "Lock"),
    GameAction("Change Camera","select",   "Camera"),
    GameAction("Map/Menu",     "start",    "Menu"),
]

MENU_ACTIONS = [
    GameAction("Confirm",      "buttonA",  "Confirm"),
    GameAction("Cancel/Back",  "buttonB",  "Cancel"),
    GameAction("Tab Left",     "buttonLB", "Tab L"),
    GameAction("Tab Right",    "buttonRB", "Tab R"),
    GameAction("Sub-Tab Left", "buttonLT", "Sub L"),
    GameAction("Sub-Tab Right","buttonRT", "Sub R"),
    GameAction("Navigate",     "padU",     "Nav"),
    GameAction("Scroll",       "buttonRS", "Scroll"),
]

HORSE_ACTIONS = [
    GameAction("Sprint",              "buttonA",  "Sprint"),
    GameAction("Dismount",            "buttonB",  "Dismnt"),
    GameAction("Jump",                "buttonX",  "Jump"),
    GameAction("Horse Skill",         "buttonY",  "Skill"),
    GameAction("Attack (mounted)",    "buttonRB", "Attack"),
    GameAction("Power Attack (mounted)","buttonRT","Power"),
    GameAction("Summon/Dismiss",      "padU",     "Summon"),
]

_CONTEXT_MAP = {
    "combat": COMBAT_ACTIONS,
    "menus": MENU_ACTIONS,
    "horse": HORSE_ACTIONS,
}

# Maps context tab name to the context string used by apply_swaps_contextual
CONTEXT_TO_SWAP_CONTEXT = {
    "combat": "gameplay",
    "menus": "menus",
    "horse": "gameplay",
}


def get_defaults(context: str) -> dict[str, str]:
    """Returns {action_name: button_id} for the default layout."""
    actions = _CONTEXT_MAP[context]
    return {a.name: a.default_btn for a in actions}


def get_action_list(context: str) -> list[GameAction]:
    """Returns the action list for a context."""
    return _CONTEXT_MAP[context]


def auto_swap(assignments: dict[str, str], action: str, new_btn: str) -> dict[str, str]:
    """Move action to new_btn, auto-swap the displaced action. Returns new dict."""
    result = dict(assignments)
    old_btn = result[action]

    if old_btn == new_btn:
        return result

    # Find action currently on new_btn (if any)
    displaced = None
    for act, btn in result.items():
        if btn == new_btn and act != action:
            displaced = act
            break

    result[action] = new_btn
    if displaced:
        result[displaced] = old_btn

    return result


def diff_to_swaps(
    defaults: dict[str, str],
    current: dict[str, str],
    swap_context: str,
) -> list[dict]:
    """Diff two assignment maps. Returns swap list for apply_swaps_contextual."""
    btn_remap = {}  # default_btn -> current_btn
    for action in defaults:
        default_btn = defaults[action]
        current_btn = current.get(action, default_btn)
        if default_btn != current_btn:
            btn_remap[default_btn] = current_btn

    # Generate bidirectional swap pairs
    swaps = []
    seen = set()
    for old_btn, new_btn in btn_remap.items():
        pair = tuple(sorted([old_btn, new_btn]))
        if pair in seen:
            continue
        seen.add(pair)
        swaps.append({"source": old_btn, "target": new_btn, "context": swap_context})
        swaps.append({"source": new_btn, "target": old_btn, "context": swap_context})

    return swaps


def get_button_action_labels(
    context: str,
    custom_assignments: dict[str, str] | None,
) -> dict[str, str]:
    """Get {button_id: short_label} for the controller diagram."""
    actions = _CONTEXT_MAP[context]
    label_map = {a.default_btn: a.short_label for a in actions}

    if custom_assignments:
        label_map = {}
        name_to_label = {a.name: a.short_label for a in actions}
        for action_name, btn in custom_assignments.items():
            if action_name in name_to_label:
                label_map[btn] = name_to_label[action_name]

    return label_map

# Action-Based Controller Remapper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Overhaul the GUI from button-swap to action-based remapping. Users see game actions (Sprint, Jump, Attack...) and reassign them to controller buttons. Three context tabs (Combat, Menus, Horse). Auto-swap on reassignment.

**Architecture:** New `actions.py` holds the action registry (hard-coded Crimson Desert control scheme), auto-swap logic, and diff-to-swaps translation. `gui.py` is rewritten with action list + controller diagram + tab bar. The existing XML swap engine (`remap.py`, `contexts.py`) is unchanged — `actions.py` produces swap lists in the format they already consume.

**Tech Stack:** Python 3.12, Dear PyGui 2.2, XInput-Python, vendored CDUMM.

**Spec:** `docs/superpowers/specs/2026-04-08-action-remapper-design.md`

---

## File Structure

```
tools/cd_remap/
├── __init__.py            # VERSION stays "2.0.0"
├── __main__.py            # Minor update: show command includes action names
├── remap.py               # UNCHANGED
├── contexts.py            # UNCHANGED
├── actions.py             # NEW: action registry, auto_swap, diff_to_swaps
├── gui.py                 # MAJOR REWRITE: action-based layout
├── controller_draw.py     # MODIFIED: label_override support in draw_button
├── presets.py             # MODIFIED: v3 format, action-assignment presets
├── gamepad.py             # UNCHANGED
├── tui.py                 # UNCHANGED
└── vendor/                # UNCHANGED

tests/
├── conftest.py            # UNCHANGED
├── test_remap.py          # UNCHANGED (17 tests)
├── test_contexts.py       # UNCHANGED (22 tests)
├── test_presets.py        # MODIFIED: add v3 format tests
└── test_actions.py        # NEW: action registry + auto_swap + diff tests
```

---

### Task 1: Action registry — `actions.py` + tests

**Files:**
- Create: `tools/cd_remap/actions.py`
- Create: `tests/test_actions.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_actions.py`:

```python
"""Tests for action registry, auto-swap, and diff-to-swaps."""
import pytest


class TestActionRegistry:
    def test_combat_defaults_complete(self):
        from cd_remap.actions import get_defaults
        defaults = get_defaults("combat")
        assert "Sprint/Run" in defaults
        assert defaults["Sprint/Run"] == "buttonA"
        assert "Jump" in defaults
        assert defaults["Jump"] == "buttonX"
        assert len(defaults) == 16

    def test_menus_defaults_complete(self):
        from cd_remap.actions import get_defaults
        defaults = get_defaults("menus")
        assert "Confirm" in defaults
        assert defaults["Confirm"] == "buttonA"
        assert len(defaults) == 8

    def test_horse_defaults_complete(self):
        from cd_remap.actions import get_defaults
        defaults = get_defaults("horse")
        assert "Sprint" in defaults
        assert defaults["Sprint"] == "buttonA"
        assert len(defaults) == 7

    def test_no_duplicate_buttons_per_context(self):
        from cd_remap.actions import get_defaults
        for ctx in ("combat", "menus", "horse"):
            defaults = get_defaults(ctx)
            buttons = list(defaults.values())
            assert len(buttons) == len(set(buttons)), f"Duplicate buttons in {ctx}"

    def test_unknown_context_raises(self):
        from cd_remap.actions import get_defaults
        with pytest.raises(KeyError):
            get_defaults("swimming")

    def test_all_contexts_returns_list(self):
        from cd_remap.actions import ALL_CONTEXTS
        assert ALL_CONTEXTS == ["combat", "menus", "horse"]


class TestAutoSwap:
    def test_simple_swap(self):
        from cd_remap.actions import auto_swap
        assignments = {"Sprint/Run": "buttonA", "Jump": "buttonX"}
        result = auto_swap(assignments, "Jump", "buttonA")
        assert result["Jump"] == "buttonA"
        assert result["Sprint/Run"] == "buttonX"

    def test_swap_preserves_others(self):
        from cd_remap.actions import auto_swap
        assignments = {"Sprint/Run": "buttonA", "Jump": "buttonX", "Dodge/Roll": "buttonB"}
        result = auto_swap(assignments, "Jump", "buttonA")
        assert result["Dodge/Roll"] == "buttonB"

    def test_swap_to_unassigned_button(self):
        from cd_remap.actions import auto_swap
        assignments = {"Sprint/Run": "buttonA"}
        result = auto_swap(assignments, "Sprint/Run", "buttonY")
        assert result["Sprint/Run"] == "buttonY"

    def test_swap_same_button_noop(self):
        from cd_remap.actions import auto_swap
        assignments = {"Sprint/Run": "buttonA", "Jump": "buttonX"}
        result = auto_swap(assignments, "Sprint/Run", "buttonA")
        assert result == assignments

    def test_returns_new_dict(self):
        from cd_remap.actions import auto_swap
        assignments = {"Sprint/Run": "buttonA", "Jump": "buttonX"}
        result = auto_swap(assignments, "Jump", "buttonA")
        assert result is not assignments


class TestDiffToSwaps:
    def test_no_changes_empty(self):
        from cd_remap.actions import diff_to_swaps
        defaults = {"Sprint/Run": "buttonA", "Jump": "buttonX"}
        current = {"Sprint/Run": "buttonA", "Jump": "buttonX"}
        swaps = diff_to_swaps(defaults, current, "gameplay")
        assert swaps == []

    def test_single_pair_swap(self):
        from cd_remap.actions import diff_to_swaps
        defaults = {"Sprint/Run": "buttonA", "Jump": "buttonX"}
        current = {"Sprint/Run": "buttonX", "Jump": "buttonA"}
        swaps = diff_to_swaps(defaults, current, "gameplay")
        assert len(swaps) == 2
        sources = {s["source"] for s in swaps}
        targets = {s["target"] for s in swaps}
        assert sources == {"buttonA", "buttonX"}
        assert targets == {"buttonA", "buttonX"}
        assert all(s["context"] == "gameplay" for s in swaps)

    def test_two_pair_swaps(self):
        from cd_remap.actions import diff_to_swaps
        defaults = {"A": "buttonA", "B": "buttonB", "X": "buttonX", "Y": "buttonY"}
        current = {"A": "buttonB", "B": "buttonA", "X": "buttonY", "Y": "buttonX"}
        swaps = diff_to_swaps(defaults, current, "gameplay")
        assert len(swaps) == 4

    def test_context_passed_through(self):
        from cd_remap.actions import diff_to_swaps
        defaults = {"Sprint/Run": "buttonA", "Jump": "buttonX"}
        current = {"Sprint/Run": "buttonX", "Jump": "buttonA"}
        swaps = diff_to_swaps(defaults, current, "menus")
        assert all(s["context"] == "menus" for s in swaps)


class TestActionLabelsForButtons:
    def test_returns_action_names_keyed_by_button(self):
        from cd_remap.actions import get_button_action_labels
        labels = get_button_action_labels("combat", None)
        assert labels["buttonA"] == "Sprint"
        assert labels["buttonX"] == "Jump"
        assert labels["buttonB"] == "Dodge"

    def test_custom_assignments_change_labels(self):
        from cd_remap.actions import get_button_action_labels
        custom = {"Sprint/Run": "buttonX", "Jump": "buttonA"}
        labels = get_button_action_labels("combat", custom)
        assert labels["buttonA"] == "Jump"
        assert labels["buttonX"] == "Sprint"

    def test_labels_are_short(self):
        from cd_remap.actions import get_button_action_labels
        labels = get_button_action_labels("combat", None)
        for btn, label in labels.items():
            assert len(label) <= 8, f"Label too long for {btn}: '{label}'"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd D:/Games/Workshop/CRIMSON_DESERT
python -m pytest tests/test_actions.py -v
```

Expected: All FAIL with `ModuleNotFoundError: No module named 'cd_remap.actions'`

- [ ] **Step 3: Implement actions.py**

Create `tools/cd_remap/actions.py`:

```python
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
    # Build button remapping: which default button now maps to which current button
    # defaults: action -> default_btn, current: action -> current_btn
    # We need: for each button that changed, what is its new identity
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
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_actions.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Run ALL tests for regression**

```bash
python -m pytest tests/ -v
```

Expected: All pass (49 existing + new action tests)

- [ ] **Step 6: Commit**

```bash
git add tools/cd_remap/actions.py tests/test_actions.py
git commit -m "feat: action registry — game control scheme, auto-swap, diff-to-swaps

Hard-coded Crimson Desert controls for Combat (16), Menus (8), Horse (7).
auto_swap() handles displacement on reassign. diff_to_swaps() translates
action assignments to XML swap pairs. get_button_action_labels() for diagram."
```

---

### Task 2: Update `controller_draw.py` — label override support

**Files:**
- Modify: `tools/cd_remap/controller_draw.py`

The `draw_button()` function currently hardcodes `pos["label"]` (the button letter). Add support for overriding the label text so the GUI can show action names instead.

- [ ] **Step 1: Modify `draw_button` to accept label_override**

In `tools/cd_remap/controller_draw.py`, replace the `draw_button` function:

```python
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
```

- [ ] **Step 2: Update `draw_all_buttons` to accept labels dict**

Replace the `draw_all_buttons` function:

```python
def draw_all_buttons(drawlist: int | str, labels: dict[str, str] | None = None) -> dict[str, str]:
    """Draw all buttons on the controller. Returns {btn_id: item_tag}."""
    tags = {}
    for btn_id in BUTTON_POSITIONS:
        label_override = labels.get(btn_id) if labels else None
        tags[btn_id] = draw_button(drawlist, btn_id, label_override=label_override)
    return tags
```

- [ ] **Step 3: Run ALL tests**

```bash
python -m pytest tests/ -v
```

Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add tools/cd_remap/controller_draw.py
git commit -m "feat: label_override support in controller drawing

draw_button() and draw_all_buttons() accept optional label overrides
so the GUI can show action names instead of button letters."
```

---

### Task 3: Update `presets.py` — v3 action-assignment format

**Files:**
- Modify: `tools/cd_remap/presets.py`
- Modify: `tests/test_presets.py`

- [ ] **Step 1: Add v3 tests to test_presets.py**

Append to `tests/test_presets.py`:

```python
class TestV3Format:
    def test_save_v3_roundtrip(self, tmp_path):
        from cd_remap.presets import save_profile_v3, load_profile_v3
        assignments = {
            "combat": {"Sprint/Run": "buttonB", "Dodge/Roll": "buttonA"},
            "menus": {},
            "horse": {},
        }
        save_profile_v3("Test V3", assignments, profiles_dir=tmp_path)
        loaded = load_profile_v3("test-v3", profiles_dir=tmp_path)
        assert loaded["name"] == "Test V3"
        assert loaded["format_version"] == "3.0"
        assert loaded["combat"] == {"Sprint/Run": "buttonB", "Dodge/Roll": "buttonA"}

    def test_builtin_presets_v3(self):
        from cd_remap.presets import BUILTIN_PRESETS_V3
        assert "Soulslike" in BUILTIN_PRESETS_V3
        soulslike = BUILTIN_PRESETS_V3["Soulslike"]
        assert "combat" in soulslike
        assert soulslike["combat"]["Sprint/Run"] == "buttonB"
        assert soulslike["combat"]["Dodge/Roll"] == "buttonA"

    def test_v3_only_stores_changes(self, tmp_path):
        from cd_remap.presets import save_profile_v3
        import json
        assignments = {
            "combat": {"Sprint/Run": "buttonB", "Dodge/Roll": "buttonA"},
            "menus": {},
            "horse": {},
        }
        save_profile_v3("Minimal", assignments, profiles_dir=tmp_path)
        data = json.loads((tmp_path / "minimal.json").read_text())
        assert data["menus"] == {}
        assert data["horse"] == {}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_presets.py::TestV3Format -v
```

Expected: FAIL with `ImportError`

- [ ] **Step 3: Add v3 functions to presets.py**

Add to the end of `tools/cd_remap/presets.py`:

```python
BUILTIN_PRESETS_V3: dict[str, dict[str, dict[str, str]]] = {
    "Soulslike": {
        "combat": {
            "Sprint/Run": "buttonB",
            "Dodge/Roll": "buttonA",
            "Jump": "buttonY",
            "Kick/Unarmed": "buttonX",
        },
        "menus": {},
        "horse": {},
    },
    "Southpaw": {
        "combat": {
            "Crouch/Slide": "buttonRS",
            "Force Palm": "buttonLS",
            "Block/Parry": "buttonRB",
            "Basic Attack": "buttonLB",
        },
        "menus": {},
        "horse": {},
    },
    "Trigger Swap": {
        "combat": {
            "Aim Ranged": "buttonRT",
            "Power Attack": "buttonLT",
            "Block/Parry": "buttonRB",
            "Basic Attack": "buttonLB",
        },
        "menus": {},
        "horse": {},
    },
}


def save_profile_v3(
    name: str,
    assignments: dict[str, dict[str, str]],
    profiles_dir: Path = DEFAULT_PROFILES_DIR,
) -> Path:
    """Save a v3 action-assignment profile."""
    profiles_dir.mkdir(parents=True, exist_ok=True)
    slug = _slugify(name)
    data = {
        "format_version": "3.0",
        "name": name,
        **assignments,
    }
    path = profiles_dir / f"{slug}.json"
    path.write_text(json.dumps(data, indent=2))
    return path


def load_profile_v3(
    slug: str,
    profiles_dir: Path = DEFAULT_PROFILES_DIR,
) -> dict:
    """Load a v3 profile. Returns dict with name, format_version, combat, menus, horse."""
    path = profiles_dir / f"{slug}.json"
    data = json.loads(path.read_text())

    # v2 migration: convert swap list to action assignments
    if data.get("format_version") == "2.0" and "swaps" in data:
        from .actions import get_defaults
        combat_defaults = get_defaults("combat")
        assignments = dict(combat_defaults)
        for swap in data["swaps"]:
            # Find which actions were on these buttons
            for action, btn in combat_defaults.items():
                if btn == swap["source"]:
                    assignments[action] = swap["target"]
        changed = {a: b for a, b in assignments.items() if b != combat_defaults[a]}
        data = {
            "format_version": "3.0",
            "name": data.get("name", slug),
            "combat": changed,
            "menus": {},
            "horse": {},
        }

    if "combat" not in data:
        data["combat"] = {}
    if "menus" not in data:
        data["menus"] = {}
    if "horse" not in data:
        data["horse"] = {}

    return data
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_presets.py -v
```

Expected: All pass (existing 10 + new 3)

- [ ] **Step 5: Run ALL tests**

```bash
python -m pytest tests/ -v
```

Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add tools/cd_remap/presets.py tests/test_presets.py
git commit -m "feat: v3 action-assignment profile format

BUILTIN_PRESETS_V3 with Soulslike/Southpaw/Trigger Swap as action assignments.
save_profile_v3/load_profile_v3 with v2 auto-migration. 3 new tests."
```

---

### Task 4: Rewrite `gui.py` — action-based remapping UI

**Files:**
- Rewrite: `tools/cd_remap/gui.py`

This is the major rewrite. The entire `RemapGUI` class changes from swap-based to action-based.

- [ ] **Step 1: Rewrite gui.py**

Replace the entire contents of `tools/cd_remap/gui.py`:

```python
"""Dear PyGui main window — action-based controller remapping."""
import dearpygui.dearpygui as dpg
from pathlib import Path

from . import VERSION
from .gamepad import GamepadPoller
from .remap import (
    _apply_patched_xml,
    apply_swaps_contextual,
    extract_xml,
    remove_remap,
)
from .actions import (
    ALL_CONTEXTS,
    CONTEXT_TO_SWAP_CONTEXT,
    auto_swap,
    diff_to_swaps,
    get_action_list,
    get_button_action_labels,
    get_defaults,
)
from .presets import (
    BUILTIN_PRESETS_V3,
    save_profile_v3,
    load_profile_v3,
    list_profiles,
    delete_profile,
)
from .controller_draw import (
    CLICKABLE_BUTTONS,
    draw_controller_body,
    draw_all_buttons,
    draw_all_action_labels,
    hit_test,
    update_button_color,
    get_pair_color,
    COLOR_DEFAULT,
    COLOR_HOVER,
    COLOR_SELECTED,
)

BUTTON_DISPLAY = {
    "buttonA": "A", "buttonB": "B", "buttonX": "X", "buttonY": "Y",
    "buttonLB": "LB", "buttonRB": "RB", "buttonLT": "LT", "buttonRT": "RT",
    "buttonLS": "LS", "buttonRS": "RS", "leftstick": "L-Stick", "rightstick": "R-Stick",
    "padU": "D-Up", "padD": "D-Down", "padL": "D-Left", "padR": "D-Right",
    "select": "Select", "start": "Start",
}

COLOR_CHANGED = (0, 200, 200, 255)


class RemapGUI:
    def __init__(self, game_dir: Path):
        self.game_dir = game_dir
        self.gamepad = GamepadPoller()
        self.active_tab = "combat"
        self.selected_action: str | None = None
        self.active_profile: str | None = None
        self.hovered_button: str | None = None
        self.drawlist = None

        # Action assignments per context: {context: {action_name: button_id}}
        self.assignments: dict[str, dict[str, str]] = {}
        for ctx in ALL_CONTEXTS:
            self.assignments[ctx] = get_defaults(ctx)

    def _get_changed_buttons(self) -> set[str]:
        """Buttons that differ from default in the active tab."""
        defaults = get_defaults(self.active_tab)
        current = self.assignments[self.active_tab]
        return {current[a] for a in current if current[a] != defaults.get(a)}

    def _on_tab_change(self, sender, app_data):
        tab_map = {"tab_combat": "combat", "tab_menus": "menus", "tab_horse": "horse"}
        self.active_tab = tab_map.get(app_data, "combat")
        self.selected_action = None
        self._refresh_action_list()
        self._refresh_controller()

    def _on_action_click(self, sender, app_data, user_data):
        action_name = user_data
        self.selected_action = action_name
        btn = self.assignments[self.active_tab][action_name]
        update_button_color(self.drawlist, btn, COLOR_SELECTED)
        self._set_status(f"Press a button for {action_name}...")

    def _on_controller_click(self, sender, app_data):
        mouse_pos = dpg.get_drawing_mouse_pos()
        if not (0 <= mouse_pos[0] <= 450 and 0 <= mouse_pos[1] <= 300):
            return
        btn = hit_test(mouse_pos[0], mouse_pos[1])
        self._handle_button_input(btn)

    def _on_gamepad_button(self, btn: str):
        if self.selected_action:
            self._handle_button_input(btn)

    def _handle_button_input(self, btn: str | None):
        if btn is None:
            if self.selected_action:
                self.selected_action = None
                self._refresh_controller()
                self._set_status("Cancelled.")
            return

        if not self.selected_action:
            # No action selected — find what action is on this button and select it
            current = self.assignments[self.active_tab]
            for action_name, assigned_btn in current.items():
                if assigned_btn == btn:
                    self.selected_action = action_name
                    update_button_color(self.drawlist, btn, COLOR_SELECTED)
                    self._set_status(f"Press a button for {action_name}...")
                    return
            return

        # Action is selected — assign it to this button
        action = self.selected_action
        old_btn = self.assignments[self.active_tab][action]

        if btn == old_btn:
            self.selected_action = None
            self._refresh_controller()
            self._set_status("Cancelled.")
            return

        self.assignments[self.active_tab] = auto_swap(
            self.assignments[self.active_tab], action, btn,
        )
        self.selected_action = None

        # Find what was displaced
        displaced = None
        for a, b in self.assignments[self.active_tab].items():
            if b == old_btn and a != action:
                displaced = a
                break

        if displaced:
            self._set_status(
                f"{action} -> [{BUTTON_DISPLAY.get(btn, btn)}], "
                f"{displaced} -> [{BUTTON_DISPLAY.get(old_btn, old_btn)}]"
            )
        else:
            self._set_status(f"{action} -> [{BUTTON_DISPLAY.get(btn, btn)}]")

        self._refresh_action_list()
        self._refresh_controller()

    def _on_mouse_move(self, sender, app_data):
        mouse_pos = dpg.get_drawing_mouse_pos()
        in_drawlist = 0 <= mouse_pos[0] <= 450 and 0 <= mouse_pos[1] <= 300
        if not in_drawlist:
            if self.hovered_button:
                self._unhover()
            return

        btn = hit_test(mouse_pos[0], mouse_pos[1])
        if btn == self.hovered_button:
            return

        if self.hovered_button:
            self._unhover()

        if btn and btn in CLICKABLE_BUTTONS:
            base = self._get_button_color(btn)
            hover_color = COLOR_HOVER if base == COLOR_DEFAULT else tuple(min(255, c + 60) for c in base[:3]) + (255,)
            update_button_color(self.drawlist, btn, hover_color)
            self.hovered_button = btn
        else:
            self.hovered_button = None

    def _unhover(self):
        if self.hovered_button:
            update_button_color(self.drawlist, self.hovered_button,
                                self._get_button_color(self.hovered_button))
            self.hovered_button = None

    def _get_button_color(self, btn_id: str) -> tuple:
        changed = self._get_changed_buttons()
        if btn_id in changed:
            return COLOR_CHANGED
        return COLOR_DEFAULT

    def _refresh_controller(self):
        self.hovered_button = None
        for btn_id in CLICKABLE_BUTTONS:
            update_button_color(self.drawlist, btn_id, self._get_button_color(btn_id))
        labels = get_button_action_labels(self.active_tab, self.assignments[self.active_tab])
        draw_all_action_labels(self.drawlist, labels)

    def _refresh_action_list(self):
        if not dpg.does_item_exist("action_list_group"):
            return
        dpg.delete_item("action_list_group", children_only=True)

        defaults = get_defaults(self.active_tab)
        current = self.assignments[self.active_tab]
        actions = get_action_list(self.active_tab)

        for action in actions:
            btn = current.get(action.name, action.default_btn)
            btn_label = BUTTON_DISPLAY.get(btn, btn)
            is_changed = btn != defaults.get(action.name)
            color = (0, 200, 200) if is_changed else (180, 180, 180)

            with dpg.group(horizontal=True, parent="action_list_group"):
                dpg.add_text(f"{action.name}", color=color)
                dpg.add_spacer(width=10)
                dpg.add_button(
                    label=f"[{btn_label}]",
                    callback=self._on_action_click,
                    user_data=action.name,
                    width=50,
                )

    def _refresh_presets(self):
        if not dpg.does_item_exist("presets_group"):
            return
        dpg.delete_item("presets_group", children_only=True)

        for name in BUILTIN_PRESETS_V3:
            dpg.add_button(
                label=name, width=-1,
                callback=lambda s, a, u: self._load_preset(u),
                user_data=name, parent="presets_group",
            )

        dpg.add_spacer(height=8, parent="presets_group")
        dpg.add_separator(parent="presets_group")
        dpg.add_text("Profiles", color=(200, 200, 200), parent="presets_group")

        for slug in list_profiles():
            dpg.add_button(
                label=slug, width=-1,
                callback=lambda s, a, u: self._load_profile(u),
                user_data=slug, parent="presets_group",
            )

    def _load_preset(self, name: str):
        preset = BUILTIN_PRESETS_V3[name]
        for ctx in ALL_CONTEXTS:
            defaults = get_defaults(ctx)
            self.assignments[ctx] = dict(defaults)
            for action_name, btn in preset.get(ctx, {}).items():
                if action_name in self.assignments[ctx]:
                    self.assignments[ctx] = auto_swap(self.assignments[ctx], action_name, btn)
        self.active_profile = None
        self.selected_action = None
        self._refresh_action_list()
        self._refresh_controller()
        self._set_status(f"Loaded preset: {name}")

    def _load_profile(self, slug: str):
        try:
            data = load_profile_v3(slug)
            for ctx in ALL_CONTEXTS:
                defaults = get_defaults(ctx)
                self.assignments[ctx] = dict(defaults)
                for action_name, btn in data.get(ctx, {}).items():
                    if action_name in self.assignments[ctx]:
                        self.assignments[ctx] = auto_swap(self.assignments[ctx], action_name, btn)
            self.active_profile = slug
            self.selected_action = None
            self._refresh_action_list()
            self._refresh_controller()
            self._set_status(f"Loaded profile: {data.get('name', slug)}")
        except Exception as e:
            self._set_status(f"Error: {e}")

    def _on_reset(self):
        for ctx in ALL_CONTEXTS:
            self.assignments[ctx] = get_defaults(ctx)
        self.selected_action = None
        self._refresh_action_list()
        self._refresh_controller()
        self._set_status("Reset to defaults.")

    def _on_save(self):
        dpg.configure_item("save_as_modal", show=True)

    def _on_save_confirm(self):
        name = dpg.get_value("save_name_input")
        if not name.strip():
            return
        dpg.configure_item("save_as_modal", show=False)
        # Only save changed-from-default actions
        save_data = {}
        for ctx in ALL_CONTEXTS:
            defaults = get_defaults(ctx)
            changed = {a: b for a, b in self.assignments[ctx].items() if b != defaults.get(a)}
            save_data[ctx] = changed
        try:
            path = save_profile_v3(name.strip(), save_data)
            self.active_profile = path.stem
            self._refresh_presets()
            self._set_status(f"Saved: {name.strip()}")
        except Exception as e:
            self._set_status(f"Error: {e}")

    def _on_apply(self):
        dpg.configure_item("apply_modal", show=True)

    def _on_apply_confirm(self):
        dpg.configure_item("apply_modal", show=False)
        try:
            # Collect swaps from all contexts
            all_swaps = []
            for ctx in ALL_CONTEXTS:
                defaults = get_defaults(ctx)
                swap_ctx = CONTEXT_TO_SWAP_CONTEXT[ctx]
                swaps = diff_to_swaps(defaults, self.assignments[ctx], swap_ctx)
                all_swaps.extend(swaps)

            # Deduplicate (combat and horse share gameplay context)
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

            xml = extract_xml(self.game_dir)
            patched = apply_swaps_contextual(xml, unique_swaps)
            result = _apply_patched_xml(patched, self.game_dir)
            if result["ok"]:
                self._set_status(f"Applied! {result['affected']} bindings remapped.")
            else:
                self._set_status("Error applying remap.")
        except Exception as e:
            self._set_status(f"Error: {e}")

    def _on_undo(self):
        try:
            result = remove_remap(self.game_dir)
            self._set_status(f"Undo: {result.get('message', 'Done')}")
        except Exception as e:
            self._set_status(f"Error: {e}")

    def _set_status(self, msg: str):
        if dpg.does_item_exist("status_text"):
            dpg.set_value("status_text", msg)

    def build(self):
        dpg.create_context()

        with dpg.theme() as global_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (30, 30, 35))
                dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (35, 35, 40))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (50, 50, 55))
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 4)
                dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 6)

        # Save modal
        with dpg.window(label="Save Profile", modal=True, show=False,
                        tag="save_as_modal", width=300, height=100, no_resize=True):
            dpg.add_input_text(tag="save_name_input", hint="Profile name...", width=-1)
            with dpg.group(horizontal=True):
                dpg.add_button(label="Save", callback=self._on_save_confirm)
                dpg.add_button(label="Cancel",
                               callback=lambda: dpg.configure_item("save_as_modal", show=False))

        # Apply modal
        with dpg.window(label="Confirm Apply", modal=True, show=False,
                        tag="apply_modal", width=350, height=80, no_resize=True):
            dpg.add_text("Apply remap to game files? (Backup is automatic)")
            with dpg.group(horizontal=True):
                dpg.add_button(label="Apply", callback=self._on_apply_confirm)
                dpg.add_button(label="Cancel",
                               callback=lambda: dpg.configure_item("apply_modal", show=False))

        # Main window
        with dpg.window(tag="main_window"):
            dpg.add_text(f"CD Controller Remapper v{VERSION}")
            dpg.add_separator()

            # Tab bar
            with dpg.tab_bar(callback=self._on_tab_change):
                dpg.add_tab(label="Combat", tag="tab_combat")
                dpg.add_tab(label="Menus", tag="tab_menus")
                dpg.add_tab(label="Horse", tag="tab_horse")

            with dpg.group(horizontal=True):
                # Left: action list + presets
                with dpg.child_window(width=220, height=-60):
                    dpg.add_text("Actions", color=(200, 200, 200))
                    dpg.add_separator()
                    with dpg.group(tag="action_list_group"):
                        pass
                    dpg.add_spacer(height=10)
                    dpg.add_separator()
                    dpg.add_text("Presets", color=(200, 200, 200))
                    with dpg.group(tag="presets_group"):
                        pass

                # Right: controller diagram
                with dpg.child_window(width=-1, height=-60):
                    labels = get_button_action_labels(self.active_tab, None)
                    self.drawlist = dpg.add_drawlist(width=450, height=300, tag="controller_drawlist")
                    draw_controller_body(self.drawlist)
                    draw_all_buttons(self.drawlist, labels)

                    with dpg.handler_registry():
                        dpg.add_mouse_click_handler(callback=self._on_controller_click)
                        dpg.add_mouse_move_handler(callback=self._on_mouse_move)

            # Bottom bar
            dpg.add_separator()
            with dpg.group(horizontal=True):
                status = "Connected" if self.gamepad.connected else "Not detected"
                color = (100, 255, 100) if self.gamepad.connected else (150, 150, 150)
                dpg.add_text("Controller:", color=(200, 200, 200))
                dpg.add_text(status, tag="gamepad_status", color=color)
                dpg.add_spacer(width=20)
                dpg.add_button(label="Reset", callback=self._on_reset)
                dpg.add_button(label="Save", callback=self._on_save)
                dpg.add_button(label="Apply", callback=self._on_apply)
                dpg.add_button(label="Undo All", callback=self._on_undo)

            dpg.add_text(
                f"Ready - {self.game_dir}",
                tag="status_text", color=(150, 150, 150),
            )

        dpg.bind_theme(global_theme)
        self._refresh_action_list()
        self._refresh_presets()

        dpg.create_viewport(title=f"CD Controller Remapper v{VERSION}", width=800, height=550)
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.set_primary_window("main_window", True)

        prev_connected = self.gamepad.connected
        while dpg.is_dearpygui_running():
            btn = self.gamepad.poll()
            if btn:
                self._on_gamepad_button(btn)

            if self.gamepad.connected != prev_connected:
                prev_connected = self.gamepad.connected
                if self.gamepad.connected:
                    dpg.set_value("gamepad_status", "Connected")
                    dpg.configure_item("gamepad_status", color=(100, 255, 100))
                else:
                    dpg.set_value("gamepad_status", "Not detected")
                    dpg.configure_item("gamepad_status", color=(150, 150, 150))

            dpg.render_dearpygui_frame()

        dpg.destroy_context()


def run_gui(game_dir: Path):
    gui = RemapGUI(game_dir)
    gui.build()
```

- [ ] **Step 2: Verify GUI import**

```bash
cd D:/Games/Workshop/CRIMSON_DESERT
python -c "
import sys; sys.path.insert(0, 'tools')
from cd_remap.gui import RemapGUI, run_gui
print('GUI import OK')
"
```

Expected: `GUI import OK`

- [ ] **Step 3: Run ALL tests**

```bash
python -m pytest tests/ -v
```

Expected: All pass (action tests + existing tests)

- [ ] **Step 4: Commit**

```bash
git add tools/cd_remap/gui.py
git commit -m "feat: action-based remapping GUI

Complete rewrite: action list with game controls (Sprint, Dodge, Jump...),
three context tabs (Combat/Menus/Horse), click-then-press remap flow with
auto-swap, controller diagram shows action names, preset/profile support."
```

---

### Task 5: Manual smoke test

**Files:** None (manual testing)

- [ ] **Step 1: Launch GUI**

```bash
cd D:/Games/Workshop/CRIMSON_DESERT
python -c "import sys; sys.path.insert(0, 'tools'); from cd_remap.gui import run_gui; from pathlib import Path; run_gui(Path('D:/Games/SteamLibrary/steamapps/common/Crimson Desert'))"
```

Run in background so conversation is not blocked.

- [ ] **Step 2: Verify action list**

Combat tab should show: Sprint/Run [A], Dodge/Roll [B], Jump [X], Kick [Y], etc.

- [ ] **Step 3: Test remap flow**

Click "Jump" → press A on controller → Jump moves to [A], Sprint moves to [X]. Both rows turn cyan.

- [ ] **Step 4: Test tab switching**

Click Menus tab → should show Confirm [A], Cancel [B], Tab Left [LB], etc.

- [ ] **Step 5: Test presets**

Click Soulslike → Combat actions should rearrange: Sprint [B], Dodge [A], Jump [Y], Kick [X].

- [ ] **Step 6: Test Reset**

Click Reset → all assignments return to defaults.

---

## Self-Review

**Spec coverage:**
- Action registry with 3 contexts: Task 1 ✓
- auto_swap with displacement: Task 1 ✓
- diff_to_swaps for XML generation: Task 1 ✓
- Controller diagram with action labels: Task 2 ✓
- v3 profile format: Task 3 ✓
- Built-in presets v3: Task 3 ✓
- Action-based GUI with tab bar: Task 4 ✓
- Remap flow (click action, press button): Task 4 ✓
- Apply/Undo/Reset/Save: Task 4 ✓
- Manual testing: Task 5 ✓
- Horse/Combat shared context with dedup: Task 4 `_on_apply_confirm` ✓

**Placeholder scan:** Clean.

**Type consistency:**
- `get_defaults(ctx) -> dict[str, str]`: consistent in Task 1 and Task 4
- `auto_swap(assignments, action, btn) -> dict[str, str]`: consistent
- `diff_to_swaps(defaults, current, swap_ctx) -> list[dict]`: consistent
- `get_button_action_labels(ctx, assignments) -> dict[str, str]`: consistent
- `BUILTIN_PRESETS_V3`: consistent between Task 3 and Task 4
- `save_profile_v3`/`load_profile_v3`: consistent

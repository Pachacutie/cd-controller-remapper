# Action-Based Controller Remapper — Design Spec

**Date:** 2026-04-08
**Project:** CRIMSON_DESERT
**Author:** LUDUS
**Status:** Draft
**Supersedes:** `2026-04-08-controller-remapper-v2-design.md` (button-swap GUI)

---

## Overview

Overhaul the GUI from a button-swap tool to an action-based remapping screen. Users see actual Crimson Desert game actions (Sprint, Dodge, Jump, Attack, Block...) and reassign them to different controller buttons — like a proper game settings screen. Three context tabs: Combat, Menus, Horse. The underlying XML swap engine is unchanged.

Crimson Desert has NO in-game controller remapping. This tool is the only way to remap gamepad buttons on PC.

---

## Action Registry

### Combat / Exploration (default context)

| Action | Default Button | Notes |
|---|---|---|
| Sprint/Run | A | Tap to run |
| Dodge/Roll | B | Evasion |
| Jump | X | Also slide while sprinting |
| Kick/Unarmed | Y | Unarmed attack |
| Block/Parry | LB | Also aim lantern |
| Basic Attack | RB | Weak attack |
| Aim Ranged | LT | Hold to aim, release to shoot |
| Power Attack | RT | Strong/heavy attack |
| Crouch/Slide | LS | Hold for Axion Force |
| Force Palm | RS | Hold to activate |
| Summon Horse | D-Up | Hold for weapon quick slot |
| Sheathe | D-Left | Hold for gear quick slot |
| Eat Food | D-Right | Quick consumable |
| Camera Lock | D-Down | Hard lock-on |
| Change Camera | Select | View button |
| Map/Menu | Start | Opens main menu |

### Menus

| Action | Default Button |
|---|---|
| Confirm | A |
| Cancel/Back | B |
| Tab Left | LB |
| Tab Right | RB |
| Sub-Tab Left | LT |
| Sub-Tab Right | RT |
| Navigate | D-Pad |
| Scroll | Right Stick |

### Horse

| Action | Default Button |
|---|---|
| Sprint | A |
| Dismount | B |
| Jump | X |
| Horse Skill | Y |
| Attack (mounted) | RB |
| Power Attack (mounted) | RT |
| Summon/Dismiss | D-Up |

---

## Architecture

### New: `tools/cd_remap/actions.py`

The action registry. Contains the hard-coded default control scheme for each context, organized as lists of action dicts. Provides functions to:
- Get default assignments for a context
- Diff current assignments against defaults to produce button swap pairs
- Validate that an assignment set is complete (every action has a button, no duplicates)

```python
@dataclass
class GameAction:
    name: str           # "Sprint/Run"
    default_btn: str    # "buttonA"
    context: str        # "combat" | "menus" | "horse"

COMBAT_ACTIONS: list[GameAction] = [...]
MENU_ACTIONS: list[GameAction] = [...]
HORSE_ACTIONS: list[GameAction] = [...]

def get_defaults(context: str) -> dict[str, str]:
    """Returns {action_name: button_id} for the default layout."""

def diff_to_swaps(defaults: dict[str, str], current: dict[str, str]) -> list[dict]:
    """Diff two assignment maps. Returns v2-format swap list for apply_swaps_contextual."""

def auto_swap(assignments: dict[str, str], action: str, new_btn: str) -> dict[str, str]:
    """Move action to new_btn, auto-swap the displaced action. Returns updated assignments."""
```

### Modified: `tools/cd_remap/gui.py` (major rewrite)

Complete layout change. The `RemapGUI` class is restructured:

**State:**
- `assignments: dict[str, dict[str, str]]` — `{"combat": {"Sprint/Run": "buttonA", ...}, "menus": {...}, "horse": {...}}`
- `active_tab: str` — current context tab
- `selected_action: str | None` — action waiting for button input
- `active_profile: str | None` — loaded profile slug

**Layout:**

```
┌──────────────────────────────────────────────────────┐
│  CD Controller Remapper v2.0                         │
├──────────────────────────────────────────────────────┤
│  [Combat]  [Menus]  [Horse]               [Presets ▼]│
├───────────────────┬──────────────────────────────────┤
│                   │                                  │
│  ACTION LIST      │   CONTROLLER DIAGRAM             │
│  (scrollable)     │                                  │
│                   │   Each button labeled with its    │
│  Sprint/Run  [A]  │   current action name. Colors    │
│  Dodge/Roll  [B]  │   show changed vs default.       │
│  Jump        [X]  │                                  │
│  Kick        [Y]  │   Unchanged = dim gray           │
│  Block       [LB] │   Reassigned = accent color      │
│  Attack      [RB] │                                  │
│  Aim         [LT] │                                  │
│  Power       [RT] │                                  │
│  Crouch      [LS] │                                  │
│  ...              │                                  │
│                   │                                  │
├───────────────────┴──────────────────────────────────┤
│  Controller: Connected    [Reset] [Save] [Apply]     │
│  Status: Ready — Press a button to remap...          │
└──────────────────────────────────────────────────────┘
```

**Action list (left panel):** Scrollable list of actions for the active context tab. Each row shows: action name, current button assignment (as a short label like [A], [LB], [RT]). Rows that differ from default are highlighted with an accent color. Clicking a row selects that action for reassignment.

**Controller diagram (right panel):** Same drawlist controller from v2, but button labels show the current action name (abbreviated) instead of the button letter. E.g., the A-button circle shows "Sprint" instead of "A". When an action is being reassigned, valid target buttons brighten. Labels update live on reassignment.

**Tab bar:** Three tabs across the top — Combat, Menus, Horse. Switching tabs changes the action list and updates the controller diagram labels.

**Bottom bar:** Controller status, Reset to Default, Save, Apply. Simplified from v2 — no more separate Dry Run (integrated into Apply confirmation which shows the count).

### Remap Flow

1. User clicks "Jump" in the action list (or uses keyboard/controller to navigate to it)
2. "Jump" row highlights. Status bar says "Press a button for Jump..."
3. User presses **A** on controller (via XInput polling) or clicks A on the diagram
4. **Auto-swap:** Jump (was on X) moves to A. Sprint (was on A) moves to X.
5. Action list updates: "Jump [A]" and "Sprint/Run [X]". Both rows get accent color.
6. Controller diagram updates: A-circle label changes to "Jump", X-circle label changes to "Sprint"
7. Status bar says "Jump → A, Sprint/Run → X"

**Cancel:** Press Escape or click empty space to cancel selection.

**Already-reassigned action:** Same flow — clicking it starts a new reassignment. The auto-swap handles the displacement.

### Translating Actions to XML Swaps

When user clicks Apply:

1. For each context tab, `diff_to_swaps()` compares current assignments against defaults
2. Produces a list of button swap pairs (the same `[{"source": "buttonA", "target": "buttonX", "context": "gameplay"}, ...]` format)
3. Passes to existing `apply_swaps_contextual()` → `_apply_patched_xml()` → overlay

Example: If user moved Jump from X to A and Sprint from A to X in Combat:
- `diff_to_swaps` sees: A now does what X did, X now does what A did
- Produces: `[{"source": "buttonA", "target": "buttonX", "context": "gameplay"}, {"source": "buttonX", "target": "buttonA", "context": "gameplay"}]`

Context mapping for Apply:
- Combat tab → applies to `gameplay` context layers (UIHud_*, Action, QuickSlot, etc.)
- Menus tab → applies to `menus` context layers (UIMainMenu, UIPopUp*, etc.)
- Horse tab → also applies to `gameplay` context layers (horse controls share UIHud_4 with combat)

**Important:** Horse and Combat share the same XML layers. This means horse remaps produce the same XML swaps as combat remaps for overlapping buttons. In practice, if a user swaps A↔B in Combat AND differently in Horse, the last-applied context wins for shared buttons. The GUI handles this by merging Combat and Horse assignments before generating swaps — Combat takes priority for buttons that appear in both, with a warning shown if they conflict.

### Modified: `tools/cd_remap/controller_draw.py`

Button labels now show abbreviated action names instead of button letters:
- "Sprint" instead of "A" on the A circle
- "Dodge" instead of "B" on the B circle
- etc.

The `draw_button()` function accepts an optional `label_override` parameter. The `draw_all_buttons()` function accepts a `labels: dict[str, str]` mapping button_id → display text.

Label text is truncated to fit (max ~6 chars for circle buttons, ~4 chars for small rects). Hover tooltip shows the full action name.

### Modified: `tools/cd_remap/presets.py`

Profile format v3 — stores action assignments instead of raw swaps:

```json
{
  "format_version": "3.0",
  "name": "Soulslike",
  "combat": {
    "Sprint/Run": "buttonB",
    "Dodge/Roll": "buttonA",
    "Jump": "buttonY",
    "Kick/Unarmed": "buttonX"
  },
  "menus": {},
  "horse": {}
}
```

Only changed-from-default actions are stored. Omitted actions keep defaults on load.

v2 profiles (raw swap format) are auto-migrated: the tool reverse-engineers which actions moved based on the button swaps.

Built-in presets updated:
- **Soulslike:** Swap A↔B, X↔Y in combat (Sprint↔Dodge, Jump↔Kick)
- **Southpaw:** Swap LS↔RS, LB↔RB in combat
- **Trigger Swap:** Swap LT↔RT, LB↔RB in combat

### Unchanged modules

| Module | Why unchanged |
|---|---|
| `remap.py` | Core XML swap engine — actions layer translates to swaps before calling it |
| `contexts.py` | Layer mapping — still used by `apply_swaps_contextual()` |
| `gamepad.py` | XInput polling — feeds button presses into the new remap flow |
| `tui.py` | Fallback — kept as-is |
| `vendor/` | CDUMM subset — untouched |

### Modified: `tools/cd_remap/__main__.py`

CLI `apply` command updated to accept v3 profile format in addition to v1/v2. The `show` command updated to show action names alongside button/method.

---

## Dependencies

No new dependencies. Same as v2:
- `dearpygui` >=1.11
- `XInput-Python`
- `cryptography`, `lz4` (existing)

---

## Testing Strategy

### New: `tests/test_actions.py`

- Default assignments are complete (every action has a button, no duplicates per context)
- `auto_swap()` correctly swaps two actions' buttons
- `auto_swap()` handles chain swaps (A→B→C→A)
- `diff_to_swaps()` produces correct swap pairs from assignment diff
- `diff_to_swaps()` produces empty list when assignments match defaults
- `diff_to_swaps()` handles multiple contexts
- Round-trip: defaults → modify → diff → apply swaps → verify XML has expected changes

### Modified: `tests/test_presets.py`

- v3 profile format save/load roundtrip
- v2 profile auto-migration to v3
- Built-in presets produce valid assignment diffs

### Existing tests (unchanged)

- `test_remap.py` — 17 tests (core swap engine)
- `test_contexts.py` — 22 tests (context mapping + contextual swapping)

### Manual testing

1. Launch GUI, verify action list shows correct defaults
2. Click "Jump", press A on controller → Jump moves to A, Sprint moves to X
3. Switch to Menus tab, verify separate action list
4. Load Soulslike preset → Combat actions rearranged
5. Apply → verify in-game controls match
6. Reset to Default → verify vanilla restored

---

## Out of Scope

- Reading action names from game files (hardcoded from research — game doesn't expose them)
- Per-action hold/press/release method changes (only button assignments)
- Keyboard/mouse remapping
- Custom action creation
- Macro/combo creation

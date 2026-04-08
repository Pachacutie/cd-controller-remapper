# Controller Remapper v2.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the text TUI with a Dear PyGui GUI featuring an interactive controller diagram, add built-in presets, saveable profiles, and simplified per-context remapping.

**Architecture:** Core remap engine (`remap.py`) extended with context-aware swapping. New `contexts.py` maps 3 user-facing contexts to 16 engine layers. New `presets.py` handles built-in presets and profile CRUD. New `gui.py` + `controller_draw.py` build the Dear PyGui window with a vector-drawn interactive gamepad. Existing TUI kept as `--tui` fallback.

**Tech Stack:** Python 3.12, Dear PyGui >=1.11, vendored CDUMM (MIT), cryptography + lz4 (pip), PyInstaller for exe.

**Spec:** `docs/superpowers/specs/2026-04-08-controller-remapper-v2-design.md`

---

## File Structure

```
tools/cd_remap/
├── __init__.py            # VERSION bumped to "2.0.0"
├── __main__.py            # Updated: GUI default, --tui flag, CLI unchanged
├── remap.py               # Extended: context-aware apply_swaps_contextual(), v2 swap format
├── contexts.py            # NEW: CONTEXT_LAYERS mapping, layer_matches_context()
├── presets.py             # NEW: BUILTIN_PRESETS, profile save/load/delete/list/migrate
├── gui.py                 # NEW: Dear PyGui main window, layout, all callbacks
├── controller_draw.py     # NEW: Drawlist controller rendering, button positions, hit zones
├── tui.py                 # UNCHANGED (kept as --tui fallback)
└── vendor/                # UNCHANGED

profiles/                  # NEW directory (sibling to tools/), user-saved JSON profiles
build/
└── build_exe.py           # Updated for dearpygui hidden imports

tests/
├── conftest.py            # UNCHANGED
├── test_remap.py          # UNCHANGED (17 existing tests)
├── test_contexts.py       # NEW: context mapping + context-aware swap tests
└── test_presets.py        # NEW: preset loading + profile CRUD tests
```

---

### Task 1: Feature branch, install dearpygui, bump version

**Files:**
- Modify: `tools/cd_remap/__init__.py`

- [ ] **Step 1: Create feature branch**

```bash
cd D:/Games/Workshop/CRIMSON_DESERT
git checkout -b feat/gui-v2
```

- [ ] **Step 2: Install dearpygui**

```bash
pip install dearpygui
```

Expected: Successfully installed dearpygui-1.x.x

- [ ] **Step 3: Verify dearpygui works**

```bash
python -c "import dearpygui.dearpygui as dpg; dpg.create_context(); print(f'DearPyGui {dpg.get_dearpygui_version()} OK'); dpg.destroy_context()"
```

Expected: `DearPyGui 1.x.x OK`

- [ ] **Step 4: Bump version to 2.0.0**

Replace contents of `tools/cd_remap/__init__.py`:

```python
VERSION = "2.0.0"
```

- [ ] **Step 5: Verify existing tests still pass**

```bash
cd D:/Games/Workshop/CRIMSON_DESERT
python -m pytest tests/ -v
```

Expected: 17 passed

- [ ] **Step 6: Commit**

```bash
git add tools/cd_remap/__init__.py
git commit -m "chore: create feat/gui-v2 branch, bump version to 2.0.0"
```

---

### Task 2: Context system — `contexts.py` + tests

**Files:**
- Create: `tools/cd_remap/contexts.py`
- Create: `tests/test_contexts.py`

- [ ] **Step 1: Write failing tests for context mapping**

Create `tests/test_contexts.py`:

```python
"""Tests for context layer mapping and filtering."""
import pytest


class TestContextLayers:
    def test_gameplay_layers_defined(self):
        from cd_remap.contexts import CONTEXT_LAYERS
        assert "gameplay" in CONTEXT_LAYERS
        assert "UIHud_4" in CONTEXT_LAYERS["gameplay"]
        assert "Action" in CONTEXT_LAYERS["gameplay"]

    def test_menus_layers_defined(self):
        from cd_remap.contexts import CONTEXT_LAYERS
        assert "menus" in CONTEXT_LAYERS
        assert "UIMainMenu" in CONTEXT_LAYERS["menus"]
        assert "UIPopUp1" in CONTEXT_LAYERS["menus"]

    def test_debug_excluded_from_both(self):
        from cd_remap.contexts import CONTEXT_LAYERS
        all_mapped = set()
        for layers in CONTEXT_LAYERS.values():
            all_mapped |= layers
        assert "Debug" not in all_mapped

    def test_no_overlap_between_contexts(self):
        from cd_remap.contexts import CONTEXT_LAYERS
        gameplay = CONTEXT_LAYERS["gameplay"]
        menus = CONTEXT_LAYERS["menus"]
        assert gameplay & menus == set()


class TestLayerMatchesContext:
    def test_all_matches_any_layer(self):
        from cd_remap.contexts import layer_matches_context
        assert layer_matches_context("UIHud_4", "all") is True
        assert layer_matches_context("UIMainMenu", "all") is True
        assert layer_matches_context("Debug", "all") is True

    def test_gameplay_matches_hud(self):
        from cd_remap.contexts import layer_matches_context
        assert layer_matches_context("UIHud_4", "gameplay") is True
        assert layer_matches_context("Action", "gameplay") is True

    def test_gameplay_rejects_menu(self):
        from cd_remap.contexts import layer_matches_context
        assert layer_matches_context("UIMainMenu", "gameplay") is False

    def test_menus_matches_menu(self):
        from cd_remap.contexts import layer_matches_context
        assert layer_matches_context("UIMainMenu", "menus") is True
        assert layer_matches_context("UIPopUp2", "menus") is True

    def test_menus_rejects_hud(self):
        from cd_remap.contexts import layer_matches_context
        assert layer_matches_context("UIHud_4", "menus") is False

    def test_unknown_context_raises(self):
        from cd_remap.contexts import layer_matches_context
        with pytest.raises(ValueError):
            layer_matches_context("UIHud_4", "combat")


VALID_CONTEXTS = ["all", "gameplay", "menus"]


class TestValidateSwapsContextual:
    def test_valid_same_context(self):
        from cd_remap.contexts import validate_swaps_contextual
        swaps = [
            {"source": "buttonA", "target": "buttonB", "context": "all"},
            {"source": "buttonB", "target": "buttonA", "context": "all"},
        ]
        assert validate_swaps_contextual(swaps) == []

    def test_same_button_different_contexts_ok(self):
        from cd_remap.contexts import validate_swaps_contextual
        swaps = [
            {"source": "buttonA", "target": "buttonB", "context": "gameplay"},
            {"source": "buttonB", "target": "buttonA", "context": "gameplay"},
            {"source": "buttonA", "target": "buttonX", "context": "menus"},
            {"source": "buttonX", "target": "buttonA", "context": "menus"},
        ]
        assert validate_swaps_contextual(swaps) == []

    def test_all_conflicts_with_specific(self):
        from cd_remap.contexts import validate_swaps_contextual
        swaps = [
            {"source": "buttonA", "target": "buttonB", "context": "all"},
            {"source": "buttonB", "target": "buttonA", "context": "all"},
            {"source": "buttonA", "target": "buttonX", "context": "menus"},
            {"source": "buttonX", "target": "buttonA", "context": "menus"},
        ]
        errors = validate_swaps_contextual(swaps)
        assert len(errors) > 0
        assert any("conflict" in e.lower() for e in errors)

    def test_missing_reverse_in_context(self):
        from cd_remap.contexts import validate_swaps_contextual
        swaps = [
            {"source": "buttonA", "target": "buttonB", "context": "gameplay"},
        ]
        errors = validate_swaps_contextual(swaps)
        assert any("collision" in e.lower() or "reverse" in e.lower() for e in errors)

    def test_unknown_context_error(self):
        from cd_remap.contexts import validate_swaps_contextual
        swaps = [
            {"source": "buttonA", "target": "buttonB", "context": "combat"},
            {"source": "buttonB", "target": "buttonA", "context": "combat"},
        ]
        errors = validate_swaps_contextual(swaps)
        assert any("combat" in e for e in errors)

    def test_invalid_button_error(self):
        from cd_remap.contexts import validate_swaps_contextual
        swaps = [
            {"source": "fakeBtn", "target": "buttonB", "context": "all"},
            {"source": "buttonB", "target": "fakeBtn", "context": "all"},
        ]
        errors = validate_swaps_contextual(swaps)
        assert any("fakeBtn" in e for e in errors)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_contexts.py -v
```

Expected: All FAIL with `ModuleNotFoundError: No module named 'cd_remap.contexts'`

- [ ] **Step 3: Implement contexts.py**

Create `tools/cd_remap/contexts.py`:

```python
"""Context system — maps user-facing contexts to engine InputGroup layers."""
from .remap import VALID_BUTTONS

VALID_CONTEXTS = frozenset(["all", "gameplay", "menus"])

CONTEXT_LAYERS = {
    "gameplay": {
        "UIHud_1", "UIHud_2", "UIHud_3", "UIHud_4",
        "UIHud_HighPriority", "Action", "QuickSlot",
        "QTE", "MiniGameWithAction", "GimmickInput",
    },
    "menus": {
        "UIMainMenu", "UIPopUp1", "UIPopUp2",
        "UIInfo", "UISystemPopup",
    },
}


def layer_matches_context(layer_name: str, context: str) -> bool:
    """Check if an InputGroup layer belongs to the given context."""
    if context == "all":
        return True
    if context not in CONTEXT_LAYERS:
        raise ValueError(f"Unknown context: {context}")
    return layer_name in CONTEXT_LAYERS[context]


def validate_swaps_contextual(swaps: list[dict]) -> list[str]:
    """Validate a v2 swap list. Returns list of error strings."""
    errors = []

    for swap in swaps:
        src, tgt, ctx = swap["source"], swap["target"], swap["context"]
        if src not in VALID_BUTTONS:
            errors.append(f"Unknown source button: {src}")
        if tgt not in VALID_BUTTONS:
            errors.append(f"Unknown target button: {tgt}")
        if src == tgt:
            errors.append(f"Self-swap not allowed: {src} -> {tgt}")
        if ctx not in VALID_CONTEXTS:
            errors.append(f"Unknown context: {ctx}")

    # Group swaps by context for per-context validation
    by_context: dict[str, list[dict]] = {}
    for swap in swaps:
        by_context.setdefault(swap["context"], []).append(swap)

    # Check for "all" conflicting with specific contexts
    all_sources = {s["source"] for s in by_context.get("all", [])}
    for ctx_name in ("gameplay", "menus"):
        for swap in by_context.get(ctx_name, []):
            if swap["source"] in all_sources:
                errors.append(
                    f"Conflict: {swap['source']} is swapped in 'all' and '{ctx_name}'. "
                    f"Remove the 'all' swap or the '{ctx_name}' swap."
                )

    # Per-context: check duplicate targets and missing reverse mappings
    for ctx_name, ctx_swaps in by_context.items():
        targets = [s["target"] for s in ctx_swaps]
        seen = set()
        for t in targets:
            if t in seen:
                errors.append(f"Duplicate target in '{ctx_name}': {t}")
            seen.add(t)

        sources = {s["source"] for s in ctx_swaps}
        for swap in ctx_swaps:
            if swap["target"] not in sources:
                errors.append(
                    f"Missing reverse in '{ctx_name}': {swap['target']} is a target "
                    f"but not remapped away. Add reverse mapping."
                )

    return errors
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_contexts.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add tools/cd_remap/contexts.py tests/test_contexts.py
git commit -m "feat: context system — layer mapping and contextual swap validation

Three user-facing contexts (all/gameplay/menus) mapped to 16 engine layers.
Validates per-context swap rules: no all+specific conflicts, reverse pairs required.
13 tests."
```

---

### Task 3: Context-aware swap application in `remap.py`

**Files:**
- Modify: `tools/cd_remap/remap.py`
- Modify: `tests/test_contexts.py`

- [ ] **Step 1: Write failing tests for context-aware swapping**

Append to `tests/test_contexts.py`:

```python
class TestApplySwapsContextual:
    def test_all_context_swaps_everything(self):
        from cd_remap.remap import apply_swaps_contextual
        xml = (
            b'<InputGroup Name="HUD" LayerName="UIHud_4">\n'
            b'<Input Name="Dodge">\n'
            b'\t<GamePad Key="buttonA" Method="downonce"/>\n'
            b'</>\n'
            b'</>\n'
            b'<InputGroup Name="Menu" LayerName="UIMainMenu">\n'
            b'<Input Name="Confirm">\n'
            b'\t<GamePad Key="buttonA" Method="downonce"/>\n'
            b'</>\n'
            b'</>\n'
        )
        swaps = [
            {"source": "buttonA", "target": "buttonB", "context": "all"},
            {"source": "buttonB", "target": "buttonA", "context": "all"},
        ]
        result = apply_swaps_contextual(xml, swaps)
        # Both GamePad entries should be swapped
        assert result.count(b'Key="buttonB"') == 2
        assert result.count(b'Key="buttonA"') == 0

    def test_gameplay_only_swaps_hud(self):
        from cd_remap.remap import apply_swaps_contextual
        xml = (
            b'<InputGroup Name="HUD" LayerName="UIHud_4">\n'
            b'<Input Name="Dodge">\n'
            b'\t<GamePad Key="buttonA" Method="downonce"/>\n'
            b'</>\n'
            b'</>\n'
            b'<InputGroup Name="Menu" LayerName="UIMainMenu">\n'
            b'<Input Name="Confirm">\n'
            b'\t<GamePad Key="buttonA" Method="downonce"/>\n'
            b'</>\n'
            b'</>\n'
        )
        swaps = [
            {"source": "buttonA", "target": "buttonB", "context": "gameplay"},
            {"source": "buttonB", "target": "buttonA", "context": "gameplay"},
        ]
        result = apply_swaps_contextual(xml, swaps)
        lines = result.split(b'\n')
        # HUD entry should be swapped
        assert b'Key="buttonB"' in lines[2]
        # Menu entry should be unchanged
        assert b'Key="buttonA"' in lines[7]

    def test_mixed_contexts(self):
        from cd_remap.remap import apply_swaps_contextual
        xml = (
            b'<InputGroup Name="HUD" LayerName="UIHud_4">\n'
            b'<Input Name="Dodge">\n'
            b'\t<GamePad Key="buttonA" Method="downonce"/>\n'
            b'</>\n'
            b'</>\n'
            b'<InputGroup Name="Menu" LayerName="UIMainMenu">\n'
            b'<Input Name="Confirm">\n'
            b'\t<GamePad Key="buttonX" Method="downonce"/>\n'
            b'</>\n'
            b'</>\n'
        )
        swaps = [
            {"source": "buttonA", "target": "buttonB", "context": "gameplay"},
            {"source": "buttonB", "target": "buttonA", "context": "gameplay"},
            {"source": "buttonX", "target": "buttonY", "context": "menus"},
            {"source": "buttonY", "target": "buttonX", "context": "menus"},
        ]
        result = apply_swaps_contextual(xml, swaps)
        lines = result.split(b'\n')
        assert b'Key="buttonB"' in lines[2]  # HUD: A->B
        assert b'Key="buttonY"' in lines[7]  # Menu: X->Y

    def test_preserves_non_matching_context(self):
        from cd_remap.remap import apply_swaps_contextual
        xml = (
            b'<InputGroup Name="Menu" LayerName="UIMainMenu">\n'
            b'<Input Name="Confirm">\n'
            b'\t<GamePad Key="buttonA" Method="downonce"/>\n'
            b'</>\n'
            b'</>\n'
        )
        swaps = [
            {"source": "buttonA", "target": "buttonB", "context": "gameplay"},
            {"source": "buttonB", "target": "buttonA", "context": "gameplay"},
        ]
        result = apply_swaps_contextual(xml, swaps)
        assert b'Key="buttonA"' in result  # Unchanged — gameplay swap, menu layer

    def test_no_inputgroup_layer_unaffected(self):
        """Lines before any InputGroup are not in any layer — only 'all' affects them."""
        from cd_remap.remap import apply_swaps_contextual
        xml = (
            b'<GamePad Key="buttonA" Method="downonce"/>\n'
            b'<InputGroup Name="HUD" LayerName="UIHud_4">\n'
            b'\t<GamePad Key="buttonA" Method="downonce"/>\n'
            b'</>\n'
        )
        swaps = [
            {"source": "buttonA", "target": "buttonB", "context": "gameplay"},
            {"source": "buttonB", "target": "buttonA", "context": "gameplay"},
        ]
        result = apply_swaps_contextual(xml, swaps)
        lines = result.split(b'\n')
        assert b'Key="buttonA"' in lines[0]  # Before any InputGroup — unchanged
        assert b'Key="buttonB"' in lines[2]  # Inside UIHud_4 — swapped

    def test_all_context_matches_v1_behavior(self):
        """When all swaps are 'all' context, result matches v1 apply_swaps."""
        from cd_remap.remap import apply_swaps, apply_swaps_contextual
        xml = (
            b'<InputGroup Name="HUD" LayerName="UIHud_4">\n'
            b'<Input Name="Attack">\n'
            b'\t<GamePad Key="buttonA" Method="downonce"/>\n'
            b'</>\n'
            b'</>\n'
            b'<InputGroup Name="Menu" LayerName="UIMainMenu">\n'
            b'<Input Name="Confirm">\n'
            b'\t<GamePad Key="buttonA" Method="downonce"/>\n'
            b'</>\n'
            b'</>\n'
        )
        v1_swaps = {"buttonA": "buttonB", "buttonB": "buttonA"}
        v2_swaps = [
            {"source": "buttonA", "target": "buttonB", "context": "all"},
            {"source": "buttonB", "target": "buttonA", "context": "all"},
        ]
        v1_result = apply_swaps(xml, v1_swaps)
        v2_result = apply_swaps_contextual(xml, v2_swaps)
        assert v1_result == v2_result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_contexts.py::TestApplySwapsContextual -v
```

Expected: FAIL with `ImportError: cannot import name 'apply_swaps_contextual'`

- [ ] **Step 3: Implement `apply_swaps_contextual()` in remap.py**

Add the following to `tools/cd_remap/remap.py`, after the existing `apply_swaps()` function (around line 78):

```python
_INPUTGROUP_LAYER_RE = re.compile(rb'<InputGroup\b[^>]*\bLayerName="([^"]+)"')


def apply_swaps_contextual(xml_bytes: bytes, swaps: list[dict]) -> bytes:
    """Apply context-aware button swaps. Each swap has source, target, context."""
    from .contexts import layer_matches_context

    # Group swaps by context for efficient lookup
    by_context: dict[str, dict[str, str]] = {}
    for swap in swaps:
        ctx = swap["context"]
        by_context.setdefault(ctx, {})[swap["source"]] = swap["target"]

    current_layer = None
    result_lines = []

    for line in xml_bytes.split(b"\n"):
        # Track current InputGroup layer
        layer_match = _INPUTGROUP_LAYER_RE.search(line)
        if layer_match:
            current_layer = layer_match.group(1).decode("utf-8")

        # Find applicable swaps for current layer
        applicable_swaps = {}
        for ctx, swap_map in by_context.items():
            if current_layer is None:
                # Before any InputGroup — only "all" applies
                if ctx == "all":
                    applicable_swaps.update(swap_map)
            else:
                if layer_matches_context(current_layer, ctx):
                    applicable_swaps.update(swap_map)

        if applicable_swaps:
            # Apply swaps to this line using the existing placeholder technique
            def replace_key(match: re.Match) -> bytes:
                prefix = match.group(1)
                key_val = match.group(2).decode("utf-8")
                suffix = match.group(3)

                placeholders = {src: f"\x00SWAP_{i}\x00"
                                for i, src in enumerate(applicable_swaps)}

                for src, ph in placeholders.items():
                    key_val = re.sub(rf'\b{re.escape(src)}\b', ph, key_val)
                for src, ph in placeholders.items():
                    key_val = key_val.replace(ph, applicable_swaps[src])

                return prefix + key_val.encode("utf-8") + suffix

            line = _KEY_ATTR_RE.sub(replace_key, line)

        result_lines.append(line)

    return b"\n".join(result_lines)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_contexts.py -v
```

Expected: All tests PASS (original 13 + new 6 = 19)

- [ ] **Step 5: Run ALL tests to check no regression**

```bash
python -m pytest tests/ -v
```

Expected: 36 passed (17 existing + 19 new)

- [ ] **Step 6: Commit**

```bash
git add tools/cd_remap/remap.py tests/test_contexts.py
git commit -m "feat: context-aware swap application

apply_swaps_contextual() tracks InputGroup LayerName and applies
swaps only when context matches. 'all' context matches v1 behavior.
6 new tests."
```

---

### Task 4: Presets and profiles — `presets.py` + tests

**Files:**
- Create: `tools/cd_remap/presets.py`
- Create: `tests/test_presets.py`

- [ ] **Step 1: Write failing tests for presets and profiles**

Create `tests/test_presets.py`:

```python
"""Tests for presets and profile management."""
import json
import pytest
from pathlib import Path


class TestBuiltinPresets:
    def test_presets_exist(self):
        from cd_remap.presets import BUILTIN_PRESETS
        assert "Soulslike" in BUILTIN_PRESETS
        assert "Southpaw" in BUILTIN_PRESETS
        assert "Trigger Swap" in BUILTIN_PRESETS

    def test_presets_have_valid_swaps(self):
        from cd_remap.presets import BUILTIN_PRESETS
        from cd_remap.contexts import validate_swaps_contextual
        for name, swaps in BUILTIN_PRESETS.items():
            errors = validate_swaps_contextual(swaps)
            assert errors == [], f"Preset '{name}' has validation errors: {errors}"

    def test_presets_are_bidirectional(self):
        from cd_remap.presets import BUILTIN_PRESETS
        for name, swaps in BUILTIN_PRESETS.items():
            sources = {(s["source"], s["context"]) for s in swaps}
            for swap in swaps:
                reverse = (swap["target"], swap["context"])
                assert reverse in sources, (
                    f"Preset '{name}': {swap['source']}->{swap['target']} "
                    f"in {swap['context']} has no reverse"
                )


class TestProfileSaveLoad:
    def test_save_and_load_roundtrip(self, tmp_path):
        from cd_remap.presets import save_profile, load_profile
        swaps = [
            {"source": "buttonA", "target": "buttonB", "context": "all"},
            {"source": "buttonB", "target": "buttonA", "context": "all"},
        ]
        save_profile("Test Config", swaps, profiles_dir=tmp_path)
        loaded = load_profile("test-config", profiles_dir=tmp_path)
        assert loaded["name"] == "Test Config"
        assert loaded["swaps"] == swaps
        assert loaded["format_version"] == "2.0"

    def test_save_creates_file(self, tmp_path):
        from cd_remap.presets import save_profile
        swaps = [
            {"source": "buttonA", "target": "buttonB", "context": "all"},
            {"source": "buttonB", "target": "buttonA", "context": "all"},
        ]
        save_profile("My Profile", swaps, profiles_dir=tmp_path)
        assert (tmp_path / "my-profile.json").exists()

    def test_list_profiles(self, tmp_path):
        from cd_remap.presets import save_profile, list_profiles
        save_profile("Alpha", [{"source": "buttonA", "target": "buttonB", "context": "all"},
                                {"source": "buttonB", "target": "buttonA", "context": "all"}],
                     profiles_dir=tmp_path)
        save_profile("Beta", [{"source": "buttonX", "target": "buttonY", "context": "all"},
                               {"source": "buttonY", "target": "buttonX", "context": "all"}],
                     profiles_dir=tmp_path)
        names = list_profiles(profiles_dir=tmp_path)
        assert "alpha" in names
        assert "beta" in names

    def test_delete_profile(self, tmp_path):
        from cd_remap.presets import save_profile, delete_profile, list_profiles
        save_profile("Doomed", [{"source": "buttonA", "target": "buttonB", "context": "all"},
                                 {"source": "buttonB", "target": "buttonA", "context": "all"}],
                     profiles_dir=tmp_path)
        assert "doomed" in list_profiles(profiles_dir=tmp_path)
        delete_profile("doomed", profiles_dir=tmp_path)
        assert "doomed" not in list_profiles(profiles_dir=tmp_path)

    def test_delete_nonexistent_raises(self, tmp_path):
        from cd_remap.presets import delete_profile
        with pytest.raises(FileNotFoundError):
            delete_profile("nonexistent", profiles_dir=tmp_path)


class TestV1Migration:
    def test_migrate_v1_format(self, tmp_path):
        from cd_remap.presets import load_profile
        v1_data = {"swaps": {"buttonA": "buttonB", "buttonB": "buttonA"}}
        (tmp_path / "old-config.json").write_text(json.dumps(v1_data))
        loaded = load_profile("old-config", profiles_dir=tmp_path)
        assert loaded["format_version"] == "2.0"
        assert len(loaded["swaps"]) == 2
        assert all(s["context"] == "all" for s in loaded["swaps"])

    def test_invalid_json_raises(self, tmp_path):
        (tmp_path / "bad.json").write_text("not json")
        from cd_remap.presets import load_profile
        with pytest.raises(json.JSONDecodeError):
            load_profile("bad", profiles_dir=tmp_path)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_presets.py -v
```

Expected: All FAIL with `ModuleNotFoundError: No module named 'cd_remap.presets'`

- [ ] **Step 3: Implement presets.py**

Create `tools/cd_remap/presets.py`:

```python
"""Built-in presets and profile management."""
import json
import re
from pathlib import Path


BUILTIN_PRESETS: dict[str, list[dict]] = {
    "Soulslike": [
        {"source": "buttonA", "target": "buttonB", "context": "all"},
        {"source": "buttonB", "target": "buttonA", "context": "all"},
        {"source": "buttonX", "target": "buttonY", "context": "all"},
        {"source": "buttonY", "target": "buttonX", "context": "all"},
    ],
    "Southpaw": [
        {"source": "buttonLS", "target": "buttonRS", "context": "all"},
        {"source": "buttonRS", "target": "buttonLS", "context": "all"},
        {"source": "buttonLB", "target": "buttonRB", "context": "all"},
        {"source": "buttonRB", "target": "buttonLB", "context": "all"},
    ],
    "Trigger Swap": [
        {"source": "buttonLT", "target": "buttonRT", "context": "all"},
        {"source": "buttonRT", "target": "buttonLT", "context": "all"},
        {"source": "buttonLB", "target": "buttonRB", "context": "all"},
        {"source": "buttonRB", "target": "buttonLB", "context": "all"},
    ],
}

DEFAULT_PROFILES_DIR = Path(__file__).parent.parent.parent / "profiles"


def _slugify(name: str) -> str:
    """Convert display name to filesystem-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def save_profile(
    name: str,
    swaps: list[dict],
    profiles_dir: Path = DEFAULT_PROFILES_DIR,
) -> Path:
    """Save a profile to JSON. Returns the file path."""
    profiles_dir.mkdir(parents=True, exist_ok=True)
    slug = _slugify(name)
    data = {
        "format_version": "2.0",
        "name": name,
        "swaps": swaps,
    }
    path = profiles_dir / f"{slug}.json"
    path.write_text(json.dumps(data, indent=2))
    return path


def load_profile(
    slug: str,
    profiles_dir: Path = DEFAULT_PROFILES_DIR,
) -> dict:
    """Load a profile by slug. Auto-migrates v1 format."""
    path = profiles_dir / f"{slug}.json"
    data = json.loads(path.read_text())

    # v1 migration: {"swaps": {"A": "B"}} -> v2 list format
    if isinstance(data.get("swaps"), dict):
        old_swaps = data["swaps"]
        data = {
            "format_version": "2.0",
            "name": data.get("name", slug),
            "swaps": [
                {"source": src, "target": tgt, "context": "all"}
                for src, tgt in old_swaps.items()
            ],
        }

    return data


def list_profiles(profiles_dir: Path = DEFAULT_PROFILES_DIR) -> list[str]:
    """List saved profile slugs."""
    if not profiles_dir.exists():
        return []
    return [p.stem for p in sorted(profiles_dir.glob("*.json"))]


def delete_profile(
    slug: str,
    profiles_dir: Path = DEFAULT_PROFILES_DIR,
) -> None:
    """Delete a profile by slug."""
    path = profiles_dir / f"{slug}.json"
    if not path.exists():
        raise FileNotFoundError(f"Profile not found: {slug}")
    path.unlink()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_presets.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Run ALL tests**

```bash
python -m pytest tests/ -v
```

Expected: All passed (17 + 19 + 10 = 46)

- [ ] **Step 6: Commit**

```bash
git add tools/cd_remap/presets.py tests/test_presets.py
git commit -m "feat: presets and profile management

Three built-in presets (Soulslike, Southpaw, Trigger Swap).
Profile CRUD: save, load, list, delete. v1 config auto-migration.
Slugified filenames in profiles/ directory. 10 tests."
```

---

### Task 5: Controller drawing — `controller_draw.py`

**Files:**
- Create: `tools/cd_remap/controller_draw.py`

This module is purely visual — it renders the controller and manages button positions/hit zones. No business logic. Tested manually via the GUI (Task 7).

- [ ] **Step 1: Create controller_draw.py**

Create `tools/cd_remap/controller_draw.py`:

```python
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
                border: tuple = COLOR_BORDER) -> int | str:
    """Draw a single button. Returns the drawn item tag for later color updates."""
    pos = BUTTON_POSITIONS[btn_id]
    tag = f"btn_{btn_id}"

    if pos["shape"] == "circle":
        dpg.draw_circle(
            (pos["x"], pos["y"]), pos["r"],
            color=border, fill=color,
            tag=tag, parent=drawlist,
        )
        dpg.draw_text(
            (pos["x"] - 5, pos["y"] - 6), pos["label"],
            color=(255, 255, 255, 255), size=12,
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
            (x + 3, y + 2), pos["label"],
            color=(255, 255, 255, 255), size=11,
            parent=drawlist,
        )

    return tag


def draw_all_buttons(drawlist: int | str) -> dict[str, str]:
    """Draw all buttons on the controller. Returns {btn_id: item_tag}."""
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


def get_pair_color(pair_index: int) -> tuple:
    """Get accent color for swap pair N (wraps around if >9 pairs)."""
    return PAIR_COLORS[pair_index % len(PAIR_COLORS)]
```

- [ ] **Step 2: Smoke test — render the controller in a window**

```bash
cd D:/Games/Workshop/CRIMSON_DESERT
python -c "
import sys; sys.path.insert(0, 'tools')
import dearpygui.dearpygui as dpg
from cd_remap.controller_draw import draw_controller_body, draw_all_buttons

dpg.create_context()
with dpg.window(label='Controller Test', width=500, height=350):
    with dpg.drawlist(width=450, height=300) as dl:
        draw_controller_body(dl)
        draw_all_buttons(dl)

dpg.create_viewport(title='Controller Draw Test', width=520, height=400)
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.start_dearpygui()
dpg.destroy_context()
"
```

Expected: A window appears showing the controller outline with all 18 buttons. Close the window to continue.

- [ ] **Step 3: Commit**

```bash
git add tools/cd_remap/controller_draw.py
git commit -m "feat: controller drawing — vector gamepad with 18 button zones

Drawlist-based Xbox controller rendering with hit testing.
Clickable face/shoulder/trigger/dpad/meta buttons.
Color update API for swap pair visualization."
```

---

### Task 6: GUI main window — `gui.py`

**Files:**
- Create: `tools/cd_remap/gui.py`

This is the largest module. It wires together the controller drawlist, presets sidebar, swap summary, context radio buttons, and action bar.

- [ ] **Step 1: Create gui.py**

Create `tools/cd_remap/gui.py`:

```python
"""Dear PyGui main window — layout, state management, callbacks."""
import dearpygui.dearpygui as dpg
from pathlib import Path

from . import VERSION
from .remap import (
    VALID_BUTTONS,
    ANALOG_BUTTONS,
    apply_remap,
    apply_swaps_contextual,
    count_affected,
    extract_xml,
    remove_remap,
    show_bindings,
)
from .contexts import validate_swaps_contextual, VALID_CONTEXTS
from .presets import (
    BUILTIN_PRESETS,
    save_profile,
    load_profile,
    list_profiles,
    delete_profile,
    DEFAULT_PROFILES_DIR,
)
from .controller_draw import (
    BUTTON_POSITIONS,
    CLICKABLE_BUTTONS,
    draw_controller_body,
    draw_all_buttons,
    hit_test,
    update_button_color,
    get_pair_color,
    COLOR_DEFAULT,
    COLOR_SELECTED,
)

BUTTON_DISPLAY = {
    "buttonA": "A", "buttonB": "B", "buttonX": "X", "buttonY": "Y",
    "buttonLB": "LB", "buttonRB": "RB", "buttonLT": "LT", "buttonRT": "RT",
    "buttonLS": "LS", "buttonRS": "RS", "leftstick": "L-Stick", "rightstick": "R-Stick",
    "padU": "D-Up", "padD": "D-Down", "padL": "D-Left", "padR": "D-Right",
    "select": "Select", "start": "Start",
}


class RemapGUI:
    def __init__(self, game_dir: Path):
        self.game_dir = game_dir
        self.swaps: list[dict] = []
        self.selected_button: str | None = None
        self.active_profile: str | None = None  # slug of loaded profile, None if preset/empty
        self.pair_index = 0  # next color index
        self.button_pair_map: dict[str, int] = {}  # btn_id -> pair_index
        self.drawlist = None
        self.binding_counts: dict[str, int] = {}
        self._load_binding_counts()

    def _load_binding_counts(self):
        """Count how many GamePad entries use each button."""
        try:
            bindings = show_bindings(self.game_dir)
            for b in bindings:
                for btn in VALID_BUTTONS:
                    if btn in b["key"].split():
                        self.binding_counts[btn] = self.binding_counts.get(btn, 0) + 1
        except Exception:
            pass  # Game not installed — counts stay empty

    def _get_context(self) -> str:
        """Get currently selected context from radio buttons."""
        val = dpg.get_value("context_radio")
        mapping = {"All": "all", "Gameplay": "gameplay", "Menus": "menus"}
        return mapping.get(val, "all")

    def _swapped_buttons(self) -> set[str]:
        """Return set of buttons currently involved in any swap."""
        return {s["source"] for s in self.swaps}

    def _add_swap_pair(self, src: str, tgt: str):
        """Add a bidirectional swap pair."""
        ctx = self._get_context()
        self.swaps.append({"source": src, "target": tgt, "context": ctx})
        self.swaps.append({"source": tgt, "target": src, "context": ctx})

        color_idx = self.pair_index
        self.button_pair_map[src] = color_idx
        self.button_pair_map[tgt] = color_idx
        self.pair_index += 1

        self._refresh_controller_colors()
        self._refresh_swap_list()
        self._set_status(f"Added: {BUTTON_DISPLAY[src]} <-> {BUTTON_DISPLAY[tgt]} ({ctx})")

    def _remove_swap_pair(self, btn: str):
        """Remove the bidirectional pair containing btn."""
        partner = None
        ctx = None
        for s in self.swaps:
            if s["source"] == btn:
                partner = s["target"]
                ctx = s["context"]
                break
        if partner is None:
            return

        self.swaps = [s for s in self.swaps
                      if not (s["context"] == ctx and s["source"] in (btn, partner))]
        self.button_pair_map.pop(btn, None)
        self.button_pair_map.pop(partner, None)

        self._refresh_controller_colors()
        self._refresh_swap_list()
        self._set_status(f"Removed: {BUTTON_DISPLAY[btn]} <-> {BUTTON_DISPLAY[partner]}")

    def _clear_all_swaps(self):
        """Clear all swaps and reset state."""
        self.swaps.clear()
        self.button_pair_map.clear()
        self.pair_index = 0
        self.selected_button = None
        self._refresh_controller_colors()
        self._refresh_swap_list()

    def _on_controller_click(self, sender, app_data):
        """Handle click on the controller drawlist."""
        mouse_pos = dpg.get_drawing_mouse_pos()
        btn = hit_test(mouse_pos[0], mouse_pos[1])
        if btn is None:
            # Clicked empty space — cancel selection
            if self.selected_button:
                self.selected_button = None
                self._refresh_controller_colors()
            return

        swapped = self._swapped_buttons()

        if btn in swapped:
            # Already swapped — offer removal
            self._remove_swap_pair(btn)
            self.selected_button = None
            return

        if self.selected_button is None:
            # First click — select source
            if btn in CLICKABLE_BUTTONS:
                self.selected_button = btn
                update_button_color(self.drawlist, btn, COLOR_SELECTED)
                self._set_status(f"Swap {BUTTON_DISPLAY[btn]} with...")
        else:
            # Second click — select target
            if btn == self.selected_button:
                # Cancel
                self.selected_button = None
                self._refresh_controller_colors()
                self._set_status("Cancelled.")
            elif btn in swapped:
                self._set_status(f"{BUTTON_DISPLAY[btn]} is already swapped. Remove it first.")
            else:
                src = self.selected_button
                self.selected_button = None

                if src in ANALOG_BUTTONS or btn in ANALOG_BUTTONS:
                    self._set_status(
                        f"Warning: swapping analog sticks also swaps axis scaling. "
                        f"Added {BUTTON_DISPLAY[src]} <-> {BUTTON_DISPLAY[btn]}"
                    )

                self._add_swap_pair(src, btn)

    def _refresh_controller_colors(self):
        """Repaint all controller buttons based on current swap state."""
        for btn_id in CLICKABLE_BUTTONS:
            if btn_id in self.button_pair_map:
                color = get_pair_color(self.button_pair_map[btn_id])
            elif btn_id == self.selected_button:
                color = COLOR_SELECTED
            else:
                color = COLOR_DEFAULT
            update_button_color(self.drawlist, btn_id, color)

    def _refresh_swap_list(self):
        """Rebuild the swap summary table."""
        if dpg.does_item_exist("swap_list_group"):
            dpg.delete_item("swap_list_group", children_only=True)

        seen_pairs = set()
        for swap in self.swaps:
            pair_key = tuple(sorted([swap["source"], swap["target"]])) + (swap["context"],)
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            src_disp = BUTTON_DISPLAY[swap["source"]]
            tgt_disp = BUTTON_DISPLAY[swap["target"]]
            ctx = swap["context"].capitalize()
            color_idx = self.button_pair_map.get(swap["source"], 0)
            color = get_pair_color(color_idx)

            with dpg.group(horizontal=True, parent="swap_list_group"):
                dpg.add_text(f"{src_disp} <-> {tgt_disp}  ({ctx})", color=color[:3])
                dpg.add_button(
                    label="x",
                    callback=lambda s, a, u=swap["source"]: self._remove_swap_pair(u),
                    width=20, height=20,
                )

    def _refresh_sidebar(self):
        """Rebuild the preset/profile sidebar."""
        if dpg.does_item_exist("sidebar_group"):
            dpg.delete_item("sidebar_group", children_only=True)

        dpg.add_text("PRESETS", color=(200, 200, 200), parent="sidebar_group")
        dpg.add_separator(parent="sidebar_group")
        for name in BUILTIN_PRESETS:
            dpg.add_button(
                label=name, width=-1,
                callback=lambda s, a, u=name: self._load_preset(u),
                parent="sidebar_group",
            )

        dpg.add_spacer(height=10, parent="sidebar_group")
        dpg.add_text("PROFILES", color=(200, 200, 200), parent="sidebar_group")
        dpg.add_separator(parent="sidebar_group")
        for slug in list_profiles():
            dpg.add_button(
                label=slug, width=-1,
                callback=lambda s, a, u=slug: self._load_profile_by_slug(u),
                parent="sidebar_group",
            )

    def _load_preset(self, name: str):
        """Load a built-in preset into the swap grid."""
        self._clear_all_swaps()
        self.active_profile = None
        swaps = BUILTIN_PRESETS[name]
        seen = set()
        for swap in swaps:
            pair = tuple(sorted([swap["source"], swap["target"]]))
            if pair in seen:
                continue
            seen.add(pair)
            self._add_swap_pair(swap["source"], swap["target"])
        self._set_status(f"Loaded preset: {name}")

    def _load_profile_by_slug(self, slug: str):
        """Load a saved profile."""
        try:
            data = load_profile(slug)
            self._clear_all_swaps()
            self.active_profile = slug
            seen = set()
            for swap in data["swaps"]:
                pair = tuple(sorted([swap["source"], swap["target"]]))
                if pair in seen:
                    continue
                seen.add(pair)
                self._add_swap_pair(swap["source"], swap["target"])
            self._set_status(f"Loaded profile: {data.get('name', slug)}")
        except Exception as e:
            self._set_status(f"Error loading profile: {e}")

    def _on_save(self):
        if not self.active_profile:
            self._set_status("No profile loaded. Use 'Save As' to create one.")
            return
        try:
            data = load_profile(self.active_profile)
            save_profile(data["name"], self.swaps)
            self._set_status(f"Saved: {data['name']}")
        except Exception as e:
            self._set_status(f"Error saving: {e}")

    def _on_save_as(self):
        dpg.configure_item("save_as_modal", show=True)

    def _on_save_as_confirm(self):
        name = dpg.get_value("save_as_name_input")
        if not name.strip():
            return
        dpg.configure_item("save_as_modal", show=False)
        try:
            path = save_profile(name.strip(), self.swaps)
            self.active_profile = path.stem
            self._refresh_sidebar()
            self._set_status(f"Saved as: {name.strip()}")
        except Exception as e:
            self._set_status(f"Error: {e}")

    def _on_delete(self):
        if not self.active_profile:
            self._set_status("No profile selected to delete.")
            return
        dpg.configure_item("delete_confirm_modal", show=True)

    def _on_delete_confirm(self):
        dpg.configure_item("delete_confirm_modal", show=False)
        try:
            delete_profile(self.active_profile)
            self._clear_all_swaps()
            self.active_profile = None
            self._refresh_sidebar()
            self._set_status("Profile deleted.")
        except Exception as e:
            self._set_status(f"Error deleting: {e}")

    def _on_dry_run(self):
        errors = validate_swaps_contextual(self.swaps)
        if errors:
            self._set_status(f"Validation error: {errors[0]}")
            return
        try:
            result = apply_remap(
                {s["source"]: s["target"] for s in self.swaps if s["context"] == "all"},
                self.game_dir, dry_run=True,
            )
            if result["ok"]:
                self._set_status(f"Dry run: {result['affected']} bindings would change.")
            else:
                self._set_status(f"Error: {result['errors'][0]}")
        except Exception as e:
            self._set_status(f"Error: {e}")

    def _on_apply(self):
        errors = validate_swaps_contextual(self.swaps)
        if errors:
            self._set_status(f"Validation error: {errors[0]}")
            return
        dpg.configure_item("apply_confirm_modal", show=True)

    def _on_apply_confirm(self):
        dpg.configure_item("apply_confirm_modal", show=False)
        try:
            # For context-aware application, use the contextual path
            xml = extract_xml(self.game_dir)
            patched = apply_swaps_contextual(xml, self.swaps)
            # Use the core apply_remap infrastructure for overlay building
            # but with our pre-patched XML
            from .remap import _apply_patched_xml
            result = _apply_patched_xml(patched, self.game_dir)
            if result["ok"]:
                self._set_status(f"Applied! {result['affected']} bindings remapped.")
            else:
                self._set_status(f"Error: {result.get('errors', ['Unknown'])[0]}")
        except Exception as e:
            self._set_status(f"Error: {e}")

    def _on_undo(self):
        dpg.configure_item("undo_confirm_modal", show=True)

    def _on_undo_confirm(self):
        dpg.configure_item("undo_confirm_modal", show=False)
        try:
            result = remove_remap(self.game_dir)
            if result["ok"]:
                self._set_status(f"Undo: {result['message']}")
            else:
                self._set_status(f"Error: {result.get('message', 'Unknown')}")
        except Exception as e:
            self._set_status(f"Error: {e}")

    def _set_status(self, msg: str):
        if dpg.does_item_exist("status_text"):
            dpg.set_value("status_text", msg)

    def build(self):
        """Build the full GUI layout."""
        dpg.create_context()

        # Dark theme
        with dpg.theme() as global_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (30, 30, 35))
                dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (35, 35, 40))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (50, 50, 55))
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 4)
                dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 6)

        # Save As modal
        with dpg.window(label="Save As", modal=True, show=False,
                        tag="save_as_modal", width=300, height=100, no_resize=True):
            dpg.add_input_text(tag="save_as_name_input", hint="Profile name...", width=-1)
            with dpg.group(horizontal=True):
                dpg.add_button(label="Save", callback=self._on_save_as_confirm)
                dpg.add_button(label="Cancel",
                               callback=lambda: dpg.configure_item("save_as_modal", show=False))

        # Delete confirm modal
        with dpg.window(label="Confirm Delete", modal=True, show=False,
                        tag="delete_confirm_modal", width=300, height=80, no_resize=True):
            dpg.add_text("Delete this profile permanently?")
            with dpg.group(horizontal=True):
                dpg.add_button(label="Delete", callback=self._on_delete_confirm)
                dpg.add_button(label="Cancel",
                               callback=lambda: dpg.configure_item("delete_confirm_modal", show=False))

        # Apply confirm modal
        with dpg.window(label="Confirm Apply", modal=True, show=False,
                        tag="apply_confirm_modal", width=350, height=80, no_resize=True):
            dpg.add_text("Apply remap to game files? (Backup is automatic)")
            with dpg.group(horizontal=True):
                dpg.add_button(label="Apply", callback=self._on_apply_confirm)
                dpg.add_button(label="Cancel",
                               callback=lambda: dpg.configure_item("apply_confirm_modal", show=False))

        # Undo confirm modal
        with dpg.window(label="Confirm Undo", modal=True, show=False,
                        tag="undo_confirm_modal", width=350, height=80, no_resize=True):
            dpg.add_text("Remove all remaps and restore vanilla bindings?")
            with dpg.group(horizontal=True):
                dpg.add_button(label="Undo All", callback=self._on_undo_confirm)
                dpg.add_button(label="Cancel",
                               callback=lambda: dpg.configure_item("undo_confirm_modal", show=False))

        # Main window
        with dpg.window(tag="main_window"):
            dpg.add_text(f"CD Controller Remapper v{VERSION}")
            dpg.add_separator()

            with dpg.group(horizontal=True):
                # Left sidebar
                with dpg.child_window(width=140, height=-60, tag="sidebar_window"):
                    with dpg.group(tag="sidebar_group"):
                        pass  # Populated by _refresh_sidebar

                # Center area
                with dpg.group():
                    # Controller drawlist
                    self.drawlist = dpg.add_drawlist(width=450, height=300, tag="controller_drawlist")
                    draw_controller_body(self.drawlist)
                    draw_all_buttons(self.drawlist)

                    # Click handler
                    with dpg.handler_registry():
                        dpg.add_mouse_click_handler(callback=self._on_controller_click)

                    dpg.add_separator()
                    dpg.add_text("Active Swaps:")
                    with dpg.group(tag="swap_list_group"):
                        pass  # Populated by _refresh_swap_list

                # Right — context radio
                with dpg.child_window(width=100, height=120):
                    dpg.add_text("Context", color=(200, 200, 200))
                    dpg.add_radio_button(
                        items=["All", "Gameplay", "Menus"],
                        tag="context_radio", default_value="All",
                    )

            # Bottom action bar
            dpg.add_separator()
            with dpg.group(horizontal=True):
                dpg.add_button(label="Save", callback=self._on_save)
                dpg.add_button(label="Save As...", callback=self._on_save_as)
                dpg.add_button(label="Delete", callback=self._on_delete)
                dpg.add_spacer(width=40)
                dpg.add_button(label="Dry Run", callback=self._on_dry_run)
                dpg.add_button(label="Apply", callback=self._on_apply)
                dpg.add_button(label="Undo All", callback=self._on_undo)

            dpg.add_text(
                f"Ready - {self.game_dir}",
                tag="status_text", color=(150, 150, 150),
            )

        dpg.bind_theme(global_theme)
        self._refresh_sidebar()

        dpg.create_viewport(title=f"CD Controller Remapper v{VERSION}", width=800, height=550)
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.set_primary_window("main_window", True)
        dpg.start_dearpygui()
        dpg.destroy_context()


def run_gui(game_dir: Path):
    """Entry point for the GUI."""
    gui = RemapGUI(game_dir)
    gui.build()
```

- [ ] **Step 2: Smoke test — launch the GUI**

```bash
cd D:/Games/Workshop/CRIMSON_DESERT
python -c "
import sys; sys.path.insert(0, 'tools')
from cd_remap.gui import run_gui
from pathlib import Path
run_gui(Path('D:/Games/SteamLibrary/steamapps/common/Crimson Desert'))
"
```

Expected: GUI window appears with controller, sidebar, action buttons. Click buttons on the controller to test swap creation. Close window to continue.

- [ ] **Step 3: Run ALL tests to verify no regression**

```bash
python -m pytest tests/ -v
```

Expected: All existing tests still pass (gui.py has no tests — it's manually tested)

- [ ] **Step 4: Commit**

```bash
git add tools/cd_remap/gui.py
git commit -m "feat: Dear PyGui main window with interactive controller

Full GUI layout: sidebar (presets/profiles), interactive controller drawlist
with click-to-swap, swap summary list, context radio buttons, action bar
(save/load/delete/dry-run/apply/undo), modals for confirmations."
```

---

### Task 7: Add `_apply_patched_xml()` helper to `remap.py`

**Files:**
- Modify: `tools/cd_remap/remap.py`

The GUI needs to apply pre-patched XML (from context-aware swapping) through the overlay build pipeline. Extract the overlay-building portion of `apply_remap()` into a reusable helper.

- [ ] **Step 1: Add `_apply_patched_xml()` to remap.py**

Add after the `apply_remap()` function in `tools/cd_remap/remap.py`:

```python
def _apply_patched_xml(
    patched_xml: bytes,
    game_dir: Path = DEFAULT_GAME_DIR,
) -> dict:
    """Build overlay from pre-patched XML bytes. Used by GUI for context-aware apply."""
    papgt_path = game_dir / "meta" / "0.papgt"
    backup_papgt = BACKUP_DIR / "meta" / "0.papgt"
    if not backup_papgt.exists():
        backup_papgt.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(papgt_path, backup_papgt)

    compressed = lz4_compress(patched_xml)
    encrypted = encrypt(compressed, TARGET_FILE)

    overlay_input = [(
        encrypted,
        {
            "entry_path": TARGET_FILE,
            "compression_type": 2,
            "pamt_dir": PAZ_FOLDER,
            "decomp_size": len(patched_xml),
        },
    )]

    overlay_dir = game_dir / "0036"
    existing_entries = _read_existing_overlay(overlay_dir, game_dir) if overlay_dir.exists() else []
    existing_entries = [e for e in existing_entries if e[1].get("entry_path") != TARGET_FILE]
    all_entries = existing_entries + overlay_input

    paz_bytes, pamt_bytes = build_overlay(all_entries, game_dir=str(game_dir))

    overlay_dir.mkdir(exist_ok=True)
    (overlay_dir / "0.paz").write_bytes(paz_bytes)
    (overlay_dir / "0.pamt").write_bytes(pamt_bytes)

    papgt_mgr = PapgtManager(game_dir)
    papgt_bytes = papgt_mgr.rebuild(modified_pamts={"0036": pamt_bytes})
    papgt_path.write_bytes(papgt_bytes)

    original_xml = extract_xml(game_dir)
    affected = sum(1 for a, b in zip(original_xml.split(b"\n"), patched_xml.split(b"\n")) if a != b)

    return {"ok": True, "affected": affected}
```

- [ ] **Step 2: Run ALL tests**

```bash
python -m pytest tests/ -v
```

Expected: All pass (no functional change to existing code paths)

- [ ] **Step 3: Commit**

```bash
git add tools/cd_remap/remap.py
git commit -m "feat: _apply_patched_xml() helper for context-aware overlay build

Extracts overlay building from apply_remap() so the GUI can apply
pre-patched XML from apply_swaps_contextual()."
```

---

### Task 8: Update `__main__.py` — GUI default, --tui fallback

**Files:**
- Modify: `tools/cd_remap/__main__.py`

- [ ] **Step 1: Update __main__.py**

Replace the contents of `tools/cd_remap/__main__.py`:

```python
"""CLI entry point for CD Controller Remapper."""
import argparse
import sys
from pathlib import Path

from . import VERSION
from .remap import (
    DEFAULT_GAME_DIR,
    ANALOG_BUTTONS,
    apply_remap,
    load_config,
    remove_remap,
    show_bindings,
    validate_swaps,
)


def cmd_apply(args):
    swaps = load_config(args.config)
    errors = validate_swaps(swaps)
    if errors:
        for e in errors:
            print(f"  ERROR: {e}")
        return 1

    analog_swaps = [s for s in swaps if s in ANALOG_BUTTONS or swaps[s] in ANALOG_BUTTONS]
    if analog_swaps:
        print("  WARNING: Swapping analog sticks also swaps their axis scaling.")

    result = apply_remap(swaps, args.game_dir, args.dry_run)
    if not result["ok"]:
        for e in result["errors"]:
            print(f"  ERROR: {e}")
        return 1

    prefix = "[DRY RUN] " if result.get("dry_run") else ""
    print(f"{prefix}Remap applied. {result['affected']} bindings changed.")
    return 0


def cmd_remove(args):
    result = remove_remap(args.game_dir)
    print(result["message"])
    return 0 if result["ok"] else 1


def cmd_show(args):
    bindings = show_bindings(args.game_dir)
    current_action = None
    for b in bindings:
        if b["action"] != current_action:
            current_action = b["action"]
            print(f"\n  {current_action}")
        print(f"    {b['key']:20s} {b['method']}")
    print(f"\n  Total: {len(bindings)} gamepad bindings")
    return 0


def cmd_gui(args):
    try:
        from .gui import run_gui
        run_gui(args.game_dir)
        return 0
    except ImportError:
        print("Dear PyGui not available. Install with: pip install dearpygui")
        print("Falling back to TUI mode...")
        return cmd_tui(args)
    except Exception as e:
        print(f"GUI failed to start: {e}")
        print("Falling back to TUI mode...")
        return cmd_tui(args)


def cmd_tui(args):
    from .tui import run_tui
    return run_tui(args.game_dir)


def main():
    parser = argparse.ArgumentParser(
        prog="cd_remap",
        description=f"CD Controller Remapper v{VERSION} -- Crimson Desert gamepad button swap tool",
    )
    parser.add_argument("--game-dir", type=Path, default=DEFAULT_GAME_DIR)
    parser.add_argument("--tui", action="store_true", help="Use text TUI instead of GUI")
    parser.set_defaults(func=lambda args: cmd_tui(args) if args.tui else cmd_gui(args))

    sub = parser.add_subparsers(dest="command")

    p_apply = sub.add_parser("apply", help="Apply remap from JSON config")
    p_apply.add_argument("config", help="Path to remap JSON file")
    p_apply.add_argument("--game-dir", type=Path, default=DEFAULT_GAME_DIR)
    p_apply.add_argument("--dry-run", action="store_true")
    p_apply.set_defaults(func=cmd_apply)

    p_remove = sub.add_parser("remove", help="Remove remap (restore vanilla)")
    p_remove.add_argument("--game-dir", type=Path, default=DEFAULT_GAME_DIR)
    p_remove.set_defaults(func=cmd_remove)

    p_show = sub.add_parser("show", help="Show current vanilla gamepad bindings")
    p_show.add_argument("--game-dir", type=Path, default=DEFAULT_GAME_DIR)
    p_show.set_defaults(func=cmd_show)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test CLI still works**

```bash
cd D:/Games/Workshop/CRIMSON_DESERT
python -m cd_remap show --game-dir "D:/Games/SteamLibrary/steamapps/common/Crimson Desert" 2>&1 | head -20
```

Expected: Shows gamepad bindings (same as v1)

- [ ] **Step 3: Test --tui flag**

```bash
python -c "
import sys; sys.path.insert(0, 'tools')
# Just verify the import path works, don't launch the interactive TUI
from cd_remap.__main__ import cmd_tui
print('TUI import OK')
"
```

Expected: `TUI import OK`

- [ ] **Step 4: Run ALL tests**

```bash
python -m pytest tests/ -v
```

Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add tools/cd_remap/__main__.py
git commit -m "feat: GUI as default entry point, --tui fallback

cd_remap launches Dear PyGui GUI by default. --tui flag for text mode.
GUI falls back to TUI if dearpygui import fails.
CLI commands (apply, remove, show) unchanged."
```

---

### Task 9: Update PyInstaller build script

**Files:**
- Modify: `build/build_exe.py`

- [ ] **Step 1: Update build_exe.py**

Replace contents of `build/build_exe.py`:

```python
"""Build single-file exe with PyInstaller.

Usage:
    pip install pyinstaller
    python build/build_exe.py
"""
import PyInstaller.__main__
from pathlib import Path

ROOT = Path(__file__).parent.parent

PyInstaller.__main__.run([
    str(ROOT / "tools" / "cd_remap" / "__main__.py"),
    "--name", "cd_remap",
    "--onefile",
    "--console",
    "--distpath", str(ROOT / "dist"),
    "--workpath", str(ROOT / "build" / "pyinstaller_work"),
    "--specpath", str(ROOT / "build"),
    "--clean",
    "--hidden-import", "dearpygui",
    "--collect-all", "dearpygui",
])
```

- [ ] **Step 2: Commit**

```bash
git add build/build_exe.py
git commit -m "chore: update PyInstaller script for dearpygui bundling"
```

---

### Task 10: Build exe and manual integration test

**Files:** None (manual testing)

- [ ] **Step 1: Install pyinstaller if needed**

```bash
pip install pyinstaller
```

- [ ] **Step 2: Build the exe**

```bash
cd D:/Games/Workshop/CRIMSON_DESERT
python build/build_exe.py
```

Expected: `dist/cd_remap.exe` created. Size ~15-20MB.

- [ ] **Step 3: Test exe launches GUI**

```bash
dist/cd_remap.exe
```

Expected: GUI window opens with controller diagram.

- [ ] **Step 4: Test exe --tui mode**

```bash
dist/cd_remap.exe --tui
```

Expected: Text TUI launches.

- [ ] **Step 5: Test exe CLI**

```bash
dist/cd_remap.exe show
```

Expected: Shows gamepad bindings.

- [ ] **Step 6: Manual test — apply remap to live game**

In the GUI:
1. Click the Soulslike preset
2. Click "Dry Run" — note the affected count
3. Click "Apply" — confirm in the modal
4. Status should show "Applied! N bindings remapped."

Then launch Crimson Desert and verify:
- A button now does what B used to do (and vice versa)
- X button now does what Y used to do (and vice versa)

- [ ] **Step 7: Manual test — undo remap**

In the GUI:
1. Click "Undo All" — confirm in the modal
2. Status should show "Overlay removed, vanilla PAPGT restored."

Launch the game again and verify vanilla bindings are back.

- [ ] **Step 8: Commit build artifacts gitignore (if needed)**

Verify `dist/` is in `.gitignore`. If the exe build created any new artifact patterns, add them.

```bash
git status
```

Expected: No untracked build artifacts (all covered by .gitignore)

---

### Task 11: Create profiles/ directory and update docs

**Files:**
- Create: `profiles/.gitkeep`
- Modify: `CLAUDE.md` (update active projects table)

- [ ] **Step 1: Create profiles directory**

```bash
mkdir -p D:/Games/Workshop/CRIMSON_DESERT/profiles
touch D:/Games/Workshop/CRIMSON_DESERT/profiles/.gitkeep
```

- [ ] **Step 2: Update CLAUDE.md active projects table**

In `CLAUDE.md`, update the CRIMSON_DESERT entry in the `## RE Notes` section or project status to reflect v2:

Add above `## RE Notes`:

```markdown
## Controller Remapper v2.0

- Dear PyGui GUI with interactive controller diagram
- 3 built-in presets (Soulslike, Southpaw, Trigger Swap)
- Custom profile save/load/delete
- Per-context remapping: All / Gameplay / Menus
- CLI + TUI fallback preserved
- PyInstaller exe for Nexus distribution
```

- [ ] **Step 3: Run ALL tests one final time**

```bash
cd D:/Games/Workshop/CRIMSON_DESERT
python -m pytest tests/ -v
```

Expected: All tests pass (17 original + 19 context + 10 presets = 46)

- [ ] **Step 4: Commit**

```bash
git add profiles/.gitkeep CLAUDE.md
git commit -m "docs: update project docs for v2.0, add profiles directory"
```

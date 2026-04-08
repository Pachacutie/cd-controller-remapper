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
        assert b'Key="buttonB"' in lines[2]
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
        assert b'Key="buttonB"' in lines[2]
        assert b'Key="buttonY"' in lines[7]

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
        assert b'Key="buttonA"' in result

    def test_no_inputgroup_layer_unaffected(self):
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
        assert b'Key="buttonA"' in lines[0]
        assert b'Key="buttonB"' in lines[2]

    def test_all_context_matches_v1_behavior(self):
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

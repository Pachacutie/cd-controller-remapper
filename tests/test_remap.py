"""Tests for controller remap core logic."""
import pytest


VALID_BUTTONS = [
    "buttonA", "buttonB", "buttonX", "buttonY",
    "buttonLB", "buttonRB", "buttonLT", "buttonRT",
    "buttonLS", "buttonRS", "leftstick", "rightstick",
    "padU", "padD", "padL", "padR", "select", "start",
]


# --- Swap validation ---

class TestValidateSwaps:
    def test_valid_swap(self):
        from cd_remap.remap import validate_swaps
        errors = validate_swaps({"buttonA": "buttonB", "buttonB": "buttonA"})
        assert errors == []

    def test_unknown_source(self):
        from cd_remap.remap import validate_swaps
        errors = validate_swaps({"fakeButton": "buttonA"})
        assert any("fakeButton" in e for e in errors)

    def test_unknown_target(self):
        from cd_remap.remap import validate_swaps
        errors = validate_swaps({"buttonA": "fakeButton"})
        assert any("fakeButton" in e for e in errors)

    def test_self_swap(self):
        from cd_remap.remap import validate_swaps
        errors = validate_swaps({"buttonA": "buttonA"})
        assert any("self" in e.lower() for e in errors)

    def test_duplicate_target(self):
        from cd_remap.remap import validate_swaps
        errors = validate_swaps({"buttonA": "buttonX", "buttonB": "buttonX"})
        assert any("duplicate" in e.lower() or "target" in e.lower() for e in errors)

    def test_unidirectional_swap_collision(self):
        from cd_remap.remap import validate_swaps
        errors = validate_swaps({"buttonA": "buttonB"})  # no reverse
        assert any("collision" in e.lower() for e in errors)


# --- Applying swaps to XML content ---

class TestApplySwaps:
    def test_simple_swap(self):
        from cd_remap.remap import apply_swaps
        xml = b'<GamePad Key="buttonA" Method="downonce"/>'
        result = apply_swaps(xml, {"buttonA": "buttonB", "buttonB": "buttonA"})
        assert b'Key="buttonB"' in result

    def test_reverse_swap(self):
        from cd_remap.remap import apply_swaps
        xml = b'<GamePad Key="buttonB" Method="press"/>'
        result = apply_swaps(xml, {"buttonA": "buttonB", "buttonB": "buttonA"})
        assert b'Key="buttonA"' in result

    def test_simultaneous_no_chain(self):
        """A->B and B->A must not chain into A->A."""
        from cd_remap.remap import apply_swaps
        xml = (
            b'<GamePad Key="buttonA" Method="downonce"/>\n'
            b'<GamePad Key="buttonB" Method="press"/>'
        )
        result = apply_swaps(xml, {"buttonA": "buttonB", "buttonB": "buttonA"})
        assert b'Key="buttonB" Method="downonce"' in result
        assert b'Key="buttonA" Method="press"' in result

    def test_combo_key_swap(self):
        """Swaps inside multi-button combo keys."""
        from cd_remap.remap import apply_swaps
        xml = b'<GamePad Key="select buttonA" Method="press"/>'
        result = apply_swaps(xml, {"buttonA": "buttonB", "buttonB": "buttonA"})
        assert b'Key="select buttonB"' in result

    def test_no_partial_match(self):
        """buttonA must not match inside buttonAB (hypothetical)."""
        from cd_remap.remap import apply_swaps
        xml = b'<GamePad Key="buttonAB" Method="downonce"/>'
        result = apply_swaps(xml, {"buttonA": "buttonB"})
        assert b'Key="buttonAB"' in result  # unchanged

    def test_unswapped_buttons_untouched(self):
        from cd_remap.remap import apply_swaps
        xml = b'<GamePad Key="buttonX" Method="downonce"/>'
        result = apply_swaps(xml, {"buttonA": "buttonB", "buttonB": "buttonA"})
        assert b'Key="buttonX"' in result

    def test_preserves_non_gamepad_content(self):
        from cd_remap.remap import apply_swaps
        xml = b'<Input Name="Attack">\n\t<GamePad Key="buttonA" Method="downonce"/>\n</>'
        result = apply_swaps(xml, {"buttonA": "buttonB", "buttonB": "buttonA"})
        assert b'<Input Name="Attack">' in result
        assert b'</>' in result


# --- Counting affected entries ---

class TestCountAffected:
    def test_counts_affected(self):
        from cd_remap.remap import count_affected
        xml = (
            b'<GamePad Key="buttonA" Method="downonce"/>\n'
            b'<GamePad Key="buttonB" Method="press"/>\n'
            b'<GamePad Key="buttonX" Method="release"/>'
        )
        count = count_affected(xml, {"buttonA": "buttonB", "buttonB": "buttonA"})
        assert count == 2

    def test_zero_affected(self):
        from cd_remap.remap import count_affected
        xml = b'<GamePad Key="buttonX" Method="downonce"/>'
        count = count_affected(xml, {"buttonA": "buttonB", "buttonB": "buttonA"})
        assert count == 0


import os

# --- Integration: extract + swap + verify ---

@pytest.mark.skipif(
    not os.path.exists("D:/Games/SteamLibrary/steamapps/common/Crimson Desert/0012/0.pamt"),
    reason="Game not installed",
)
class TestIntegration:
    def test_extract_and_swap_roundtrip(self):
        from cd_remap.remap import extract_xml, apply_swaps, count_affected

        xml = extract_xml()
        assert len(xml) > 200000  # ~220KB
        assert b"GamePad" in xml

        swaps = {"buttonA": "buttonB", "buttonB": "buttonA"}
        affected = count_affected(xml, swaps)
        assert affected > 0  # should be 200+

        patched = apply_swaps(xml, swaps)
        assert len(patched) == len(xml)  # same size — no bytes added/removed

        # After swapping A<->B, applying the same swap again should affect same count
        re_affected = count_affected(patched, swaps)
        assert re_affected == affected

    def test_dry_run(self):
        from cd_remap.remap import apply_remap

        result = apply_remap(
            {"buttonA": "buttonB", "buttonB": "buttonA"},
            dry_run=True,
        )
        assert result["ok"]
        assert result["dry_run"]
        assert result["affected"] > 0

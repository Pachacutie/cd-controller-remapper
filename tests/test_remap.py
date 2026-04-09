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

# --- Integration: extract + swap + verify (requires game install) ---

@pytest.mark.skipif(
    not os.path.exists(os.path.join(os.environ.get("CD_GAME_DIR", "."), "0012", "0.pamt")),
    reason="Game not installed (set CD_GAME_DIR env var to enable)",
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


# --- Integration: PAZ patching pipeline (synthetic game dir) ---

class TestPazPatchIntegration:
    def _setup_game_dir(self, tmp_path):
        from fixtures import build_test_paz_pamt_papgt
        game_dir = tmp_path / "game"
        paz_dir = game_dir / "0012"
        paz_dir.mkdir(parents=True)
        meta_dir = game_dir / "meta"
        meta_dir.mkdir()
        xml = b'<Input Name="Attack"><GamePad Key="buttonA" Method="downonce"/></Input>\n' * 30
        paz_bytes, pamt_bytes, papgt_bytes, _ = build_test_paz_pamt_papgt(xml)
        (paz_dir / "0.paz").write_bytes(paz_bytes)
        (paz_dir / "0.pamt").write_bytes(pamt_bytes)
        (meta_dir / "0.papgt").write_bytes(papgt_bytes)
        return game_dir, xml

    def _setup_dual_xml_game_dir(self, tmp_path):
        """Build a synthetic game dir with both inputmap_common.xml and inputmap.xml."""
        from fixtures import build_multi_file_paz
        game_dir = tmp_path / "game"
        paz_dir = game_dir / "0012"
        paz_dir.mkdir(parents=True)
        meta_dir = game_dir / "meta"
        meta_dir.mkdir()
        common = b'<InputGroup LayerName="UIMainMenu"><Input Name="Menu"><GamePad Key="buttonA" Method="downonce"/></Input></InputGroup>\n' * 15
        override = b'<InputGroup LayerName="Action"><Input Name="Attack"><GamePad Key="buttonA" Method="press"/></Input></InputGroup>\n' * 15
        paz_bytes, pamt_bytes, papgt_bytes = build_multi_file_paz([
            ("ui/inputmap_common.xml", common),
            ("ui/inputmap.xml", override),
        ])
        (paz_dir / "0.paz").write_bytes(paz_bytes)
        (paz_dir / "0.pamt").write_bytes(pamt_bytes)
        (meta_dir / "0.papgt").write_bytes(papgt_bytes)
        return game_dir, common, override

    def test_apply_and_extract(self, tmp_path, monkeypatch):
        """Full pipeline: extract -> swap -> patch -> re-extract -> verify."""
        from cd_remap.remap import extract_xml, apply_swaps, TARGET_FILE
        from cd_remap.vendor.paz_patcher import apply_paz_patch
        from cd_remap.vendor import paz_patcher
        from cd_remap import remap
        backup_fn = lambda: tmp_path / "backup"
        monkeypatch.setattr(paz_patcher, "_backup_dir", backup_fn)
        monkeypatch.setattr(remap, "_backup_dir", backup_fn)
        game_dir, _ = self._setup_game_dir(tmp_path)
        xml = extract_xml(game_dir)
        assert b"buttonA" in xml
        patched = apply_swaps(xml, {"buttonA": "buttonB", "buttonB": "buttonA"})
        result = apply_paz_patch([(TARGET_FILE, patched)], game_dir)
        assert result["ok"]
        xml2 = extract_xml(game_dir)
        assert b"buttonB" in xml2

    def test_undo_restores_vanilla(self, tmp_path, monkeypatch):
        """Patch -> undo -> extract shows vanilla content."""
        from cd_remap.remap import extract_xml, apply_swaps, remove_remap, TARGET_FILE
        from cd_remap.vendor.paz_patcher import apply_paz_patch
        from cd_remap.vendor import paz_patcher
        from cd_remap import remap
        backup_fn = lambda: tmp_path / "backup"
        monkeypatch.setattr(paz_patcher, "_backup_dir", backup_fn)
        monkeypatch.setattr(remap, "_backup_dir", backup_fn)
        game_dir, original_xml = self._setup_game_dir(tmp_path)
        xml = extract_xml(game_dir)
        patched = apply_swaps(xml, {"buttonA": "buttonB", "buttonB": "buttonA"})
        apply_paz_patch([(TARGET_FILE, patched)], game_dir)
        result = remove_remap(game_dir)
        assert result["ok"]
        xml3 = extract_xml(game_dir)
        assert b"buttonA" in xml3
        assert xml3 == original_xml

    def test_dual_xml_apply_and_extract(self, tmp_path, monkeypatch):
        """Full pipeline with both XML files: extract -> swap -> patch -> verify both."""
        from cd_remap.remap import extract_both_xmls, apply_swaps
        from cd_remap.vendor.paz_patcher import apply_paz_patch
        from cd_remap.vendor import paz_patcher
        from cd_remap import remap
        monkeypatch.setattr(paz_patcher, "_backup_dir", lambda: tmp_path / "backup")
        monkeypatch.setattr(remap, "_backup_dir", lambda: tmp_path / "backup")
        game_dir, _, _ = self._setup_dual_xml_game_dir(tmp_path)

        common, override = extract_both_xmls(game_dir)
        assert b"buttonA" in common and b"buttonA" in override

        swaps = {"buttonA": "buttonB", "buttonB": "buttonA"}
        patched_common = apply_swaps(common, swaps)
        patched_override = apply_swaps(override, swaps)
        result = apply_paz_patch(
            [("ui/inputmap_common.xml", patched_common), ("ui/inputmap.xml", patched_override)],
            game_dir,
        )
        assert result["ok"]

        common2, override2 = extract_both_xmls(game_dir)
        assert b"buttonB" in common2 and b"buttonA" not in common2
        assert b"buttonB" in override2 and b"buttonA" not in override2

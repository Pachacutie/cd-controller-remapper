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
        assignments = {
            "combat": {"Sprint/Run": "buttonB", "Dodge/Roll": "buttonA"},
            "menus": {},
            "horse": {},
        }
        save_profile_v3("Minimal", assignments, profiles_dir=tmp_path)
        data = json.loads((tmp_path / "minimal.json").read_text())
        assert data["menus"] == {}
        assert data["horse"] == {}

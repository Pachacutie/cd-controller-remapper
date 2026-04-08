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

    def test_partial_assignments_preserve_default_labels(self):
        from cd_remap.actions import get_button_action_labels
        partial = {"Sprint/Run": "buttonX", "Jump": "buttonA"}
        labels = get_button_action_labels("combat", partial)
        # Changed buttons get new labels
        assert labels["buttonA"] == "Jump"
        assert labels["buttonX"] == "Sprint"
        # Unchanged buttons keep default labels
        assert labels["buttonB"] == "Dodge"
        assert labels["buttonY"] == "Kick"

    def test_labels_are_short(self):
        from cd_remap.actions import get_button_action_labels
        labels = get_button_action_labels("combat", None)
        for btn, label in labels.items():
            assert len(label) <= 8, f"Label too long for {btn}: '{label}'"

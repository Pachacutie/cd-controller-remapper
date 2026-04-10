"""Tests for GUI swap collection and validation (no DearPyGui required)."""
import pytest

from cd_remap.actions import (
    ALL_CONTEXTS,
    CONTEXT_TO_SWAP_CONTEXT,
    auto_swap,
    diff_to_swaps,
    get_defaults,
)
from cd_remap.contexts import validate_swaps_contextual


def _make_stub(assignments):
    """Bind _collect_unique_swaps to a minimal object with .assignments."""
    from cd_remap.gui import RemapGUI

    class Stub:
        pass

    stub = Stub()
    stub.assignments = assignments
    stub._collect_unique_swaps = RemapGUI._collect_unique_swaps.__get__(stub)
    return stub


def _default_assignments():
    return {ctx: dict(get_defaults(ctx)) for ctx in ALL_CONTEXTS}


class TestCollectUniqueSwaps:
    def test_no_changes_returns_empty(self):
        stub = _make_stub(_default_assignments())
        assert stub._collect_unique_swaps() == []

    def test_combat_only_swap_valid(self):
        a = _default_assignments()
        a["combat"] = auto_swap(a["combat"], "Sprint/Run", "buttonB")
        stub = _make_stub(a)
        swaps = stub._collect_unique_swaps()
        assert len(swaps) == 2  # A->B and B->A
        assert all(s["context"] == "gameplay" for s in swaps)

    def test_menus_swap_uses_menus_context(self):
        a = _default_assignments()
        a["menus"] = auto_swap(a["menus"], "Confirm", "buttonB")
        stub = _make_stub(a)
        swaps = stub._collect_unique_swaps()
        assert all(s["context"] == "menus" for s in swaps)

    def test_combat_horse_same_swap_deduplicated(self):
        a = _default_assignments()
        # Both combat and horse swap A<->B (Sprint defaults to buttonA in both)
        a["combat"] = auto_swap(a["combat"], "Sprint/Run", "buttonB")
        a["horse"] = auto_swap(a["horse"], "Sprint", "buttonB")
        stub = _make_stub(a)
        swaps = stub._collect_unique_swaps()
        keys = [(s["source"], s["target"], s["context"]) for s in swaps]
        assert len(keys) == len(set(keys)), "Duplicates not removed"

    def test_combat_horse_conflict_raises(self):
        a = _default_assignments()
        # Combat: Sprint A->B (Dodge B->A)
        a["combat"] = auto_swap(a["combat"], "Sprint/Run", "buttonB")
        # Horse: Sprint A->X (Jump X->A)  — conflict: buttonA in gameplay -> B vs X
        a["horse"] = auto_swap(a["horse"], "Sprint", "buttonX")
        stub = _make_stub(a)
        with pytest.raises(ValueError, match="Conflict"):
            stub._collect_unique_swaps()

    def test_combat_and_menus_no_conflict(self):
        a = _default_assignments()
        # Combat: swap in gameplay context
        a["combat"] = auto_swap(a["combat"], "Sprint/Run", "buttonB")
        # Menus: swap in menus context — different context, no conflict
        a["menus"] = auto_swap(a["menus"], "Confirm", "buttonB")
        stub = _make_stub(a)
        swaps = stub._collect_unique_swaps()
        contexts = {s["context"] for s in swaps}
        assert "gameplay" in contexts
        assert "menus" in contexts

"""Tests for asset path resolution."""
import pytest


class TestAssetPath:
    def test_returns_path_object(self):
        from cd_remap.asset_util import asset_path
        result = asset_path("controller.png")
        from pathlib import Path
        assert isinstance(result, Path)

    def test_path_ends_with_requested_file(self):
        from cd_remap.asset_util import asset_path
        result = asset_path("controller.png")
        assert result.name == "controller.png"
        assert result.parent.name == "assets"

    def test_path_points_to_existing_file(self):
        from cd_remap.asset_util import asset_path
        result = asset_path("controller.png")
        assert result.exists(), f"Asset not found at {result}"

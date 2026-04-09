"""Resolve asset paths for both source and PyInstaller bundle."""
import sys
from pathlib import Path


def asset_path(filename: str) -> Path:
    """Return the full path to an asset file.

    Works in both development (source tree) and PyInstaller bundle.
    """
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "assets" / filename
    return Path(__file__).resolve().parent.parent.parent / "assets" / filename

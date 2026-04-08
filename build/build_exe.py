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
])

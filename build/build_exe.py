"""Build single-file exe with PyInstaller.

Usage:
    pip install pyinstaller
    python build/build_exe.py
"""
import PyInstaller.__main__
from pathlib import Path

ROOT = Path(__file__).parent.parent

PyInstaller.__main__.run([
    str(ROOT / "tools" / "cd_remap_entry.py"),
    "--name", "cd_remap",
    "--onefile",
    "--windowed",
    "--distpath", str(ROOT / "dist"),
    "--workpath", str(ROOT / "build" / "pyinstaller_work"),
    "--specpath", str(ROOT / "build"),
    "--clean",
    "--paths", str(ROOT / "tools"),
    "--hidden-import", "dearpygui",
    "--collect-all", "dearpygui",
    "--hidden-import", "XInput",
    "--hidden-import", "cd_remap",
    "--hidden-import", "cd_remap.gui",
    "--hidden-import", "cd_remap.tui",
    "--hidden-import", "cd_remap.actions",
    "--hidden-import", "cd_remap.contexts",
    "--hidden-import", "cd_remap.presets",
    "--hidden-import", "cd_remap.gamepad",
    "--hidden-import", "cd_remap.controller_draw",
    "--hidden-import", "cd_remap.remap",
    "--hidden-import", "cd_remap.vendor",
    "--hidden-import", "cd_remap.vendor.paz_parse",
    "--hidden-import", "cd_remap.vendor.paz_crypto",
    "--hidden-import", "cd_remap.vendor.paz_repack",
    "--hidden-import", "cd_remap.vendor.paz_patcher",
    "--hidden-import", "cd_remap.vendor.hashlittle",
    "--hidden-import", "cd_remap.vendor.papgt_manager",
])

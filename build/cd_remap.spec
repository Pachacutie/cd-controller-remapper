# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('D:\\Games\\Workshop\\CD_REMAPPER\\assets\\controller.png', 'assets')]
binaries = []
hiddenimports = ['dearpygui', 'XInput', 'cd_remap', 'cd_remap.gui', 'cd_remap.tui', 'cd_remap.actions', 'cd_remap.contexts', 'cd_remap.presets', 'cd_remap.gamepad', 'cd_remap.controller_draw', 'cd_remap.remap', 'cd_remap.vendor', 'cd_remap.vendor.paz_parse', 'cd_remap.vendor.paz_crypto', 'cd_remap.vendor.paz_repack', 'cd_remap.vendor.paz_patcher', 'cd_remap.vendor.hashlittle', 'cd_remap.vendor.papgt_manager', 'cd_remap.asset_util']
tmp_ret = collect_all('dearpygui')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('lz4')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['D:\\Games\\Workshop\\CD_REMAPPER\\tools\\cd_remap_entry.py'],
    pathex=['D:\\Games\\Workshop\\CD_REMAPPER\\tools'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='cd_remap',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

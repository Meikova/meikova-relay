# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

ROOT = Path(__file__).resolve().parent

a = Analysis(
    [str(ROOT / 'host_agent' / 'gui_agent.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / 'host_agent' / 'gui_view.html'), 'host_agent'),
        (str(ROOT / 'host_agent' / 'gui_view.html'), '.'),
        (str(ROOT / 'host_agent' / 'icon.ico'), 'host_agent'),
        (str(ROOT / 'host_agent' / 'icon.ico'), '.'),
        (str(ROOT / 'host_agent' / 'icon.png'), 'host_agent'),
        (str(ROOT / 'host_agent' / 'icon.png'), '.'),
        (str(ROOT / 'host_agent' / 'tray_icon.png'), 'host_agent'),
        (str(ROOT / 'host_agent' / 'tray_icon.png'), '.'),
    ],
    hiddenimports=[],
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
    name='MeikovaRelayHost',
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
    icon=[str(ROOT / 'host_agent' / 'icon.ico')],
)

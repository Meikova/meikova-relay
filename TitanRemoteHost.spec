# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['host_agent/gui_agent.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('host_agent', 'host_agent'),
        ('host_agent/icon.ico', '.'),
        ('host_agent/icon.png', '.'),
        ('host_agent/gui_view.html', 'host_agent'),
        ('host_agent/gui_view.html', '.'),
    ],
    hiddenimports=[
        'clr',
        'webview',
        'webview.platforms.winforms',
        'pystray',
        'PIL',
    ],
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
    name='TitanRemoteHost',
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
    icon='host_agent/icon.ico',
)

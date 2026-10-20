# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['D:\\JOB\\DEV\\titan-remote\\host_agent\\gui_agent.py'],
    pathex=[],
    binaries=[],
    datas=[('D:\\JOB\\DEV\\titan-remote\\host_agent\\gui_view.html', 'host_agent'), ('D:\\JOB\\DEV\\titan-remote\\host_agent\\gui_view.html', '.'), ('D:\\JOB\\DEV\\titan-remote\\host_agent\\icon.ico', 'host_agent'), ('D:\\JOB\\DEV\\titan-remote\\host_agent\\icon.ico', '.'), ('D:\\JOB\\DEV\\titan-remote\\host_agent\\icon.png', 'host_agent'), ('D:\\JOB\\DEV\\titan-remote\\host_agent\\icon.png', '.')],
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
)

# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('D:/JOB/DEV/meikova/meikova-relay/host_agent/gui_view.html', 'host_agent'), ('D:/JOB/DEV/meikova/meikova-relay/host_agent/gui_view.html', '.'), ('D:/JOB/DEV/meikova/meikova-relay/host_agent/icon.ico', 'host_agent'), ('D:/JOB/DEV/meikova/meikova-relay/host_agent/icon.ico', '.'), ('D:/JOB/DEV/meikova/meikova-relay/host_agent/icon.png', 'host_agent'), ('D:/JOB/DEV/meikova/meikova-relay/host_agent/icon.png', '.'), ('D:/JOB/DEV/meikova/meikova-relay/host_agent/tray_icon.png', 'host_agent'), ('D:/JOB/DEV/meikova/meikova-relay/host_agent/tray_icon.png', '.'), ('D:/JOB/DEV/meikova/meikova-relay/host_agent/tray_icons', 'host_agent/tray_icons'), ('D:/JOB/DEV/meikova/meikova-relay/host_agent/tray_icons', 'tray_icons')]
binaries = [('D:/JOB/DEV/meikova/meikova-relay/host_agent/turbojpeg.dll', 'host_agent'), ('D:/JOB/DEV/meikova/meikova-relay/host_agent/turbojpeg.dll', '.')]
hiddenimports = ['host_agent.engines', 'host_agent.engines.base_engine', 'host_agent.engines.windows_engine', 'host_agent.engines.macos_engine', 'host_agent.engines.linux_engine', 'mss', 'websockets', 'numpy', 'cv2', 'turbojpeg', 'PIL', 'PIL.Image', 'PIL.ImageGrab', 'mss.windows', 'dxcam', 'bettercam', 'comtypes', 'webview', 'webview.platforms.winforms', 'webview.platforms.edgechromium', 'clr', 'clr_loader', 'pythonnet']
tmp_ret = collect_all('webview')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['D:/JOB/DEV/meikova/meikova-relay/host_agent/gui_agent.py'],
    pathex=[],
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
    icon=['D:/JOB/DEV/meikova/meikova-relay/host_agent/icon.ico'],
)

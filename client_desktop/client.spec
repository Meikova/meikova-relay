# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller specification for Titan Remote Desktop Client."""
import sys
from pathlib import Path

block_cipher = None
SPEC_DIR = Path(SPECPATH).resolve()
ROOT = SPEC_DIR.parent

datas = [
    (str(ROOT / "web-client"), "web-client"),
    (str(SPEC_DIR / "icon.ico"), "client_desktop"),
    (str(SPEC_DIR / "icon.ico"), "."),
    (str(ROOT / "host_agent" / "icon.ico"), "host_agent"),
    (str(ROOT / "host_agent" / "icon.png"), "host_agent"),
    (str(ROOT / "host_agent" / "tray_icon.png"), "host_agent"),
    (str(SPEC_DIR / "tray_icons"), "client_desktop/tray_icons"),
    (str(SPEC_DIR / "tray_icons"), "tray_icons"),
]

hiddenimports = [
    "webview",
    "client_desktop.desktop_client",
    "client_desktop.local_db",
    "host_agent.make_icon",
    "pystray",
    "PIL",
    "PIL.Image",
    "PIL.ImageDraw",
]

if sys.platform == "win32":
    hiddenimports.extend(["clr", "webview.platforms.winforms", "webview.platforms.edgechromium"])
elif sys.platform == "darwin":
    hiddenimports.extend(["webview.platforms.cocoa", "objc"])
elif sys.platform.startswith("linux"):
    hiddenimports.extend(["webview.platforms.gtk", "gi"])

a = Analysis(
    [str(SPEC_DIR / "desktop_client.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "IPython", "jupyter"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="TitanRemoteClient",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(SPEC_DIR / "icon.ico" if sys.platform == "win32" else ROOT / "host_agent" / "icon.png"),
)

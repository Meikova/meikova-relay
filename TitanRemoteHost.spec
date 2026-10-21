# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

SPEC_DIR = Path(SPECPATH).resolve()
HOST_DIR = SPEC_DIR / "host_agent"

datas = [
    (str(HOST_DIR / "gui_view.html"), "host_agent"),
    (str(HOST_DIR / "gui_view.html"), "."),
    (str(HOST_DIR / "icon.ico"), "host_agent"),
    (str(HOST_DIR / "icon.ico"), "."),
    (str(HOST_DIR / "icon.png"), "host_agent"),
    (str(HOST_DIR / "icon.png"), "."),
    (str(HOST_DIR / "tray_icon.png"), "host_agent"),
    (str(HOST_DIR / "tray_icon.png"), "."),
]

a = Analysis(
    [str(HOST_DIR / "gui_agent.py")],
    pathex=[str(SPEC_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "webview",
        "websockets",
        "pystray",
        "PIL",
        "PIL.Image",
        "PIL.ImageDraw",
        "host_agent.host_service",
        "host_agent.screen_capture",
        "host_agent.input_injector",
        "host_agent.power_manager",
        "host_agent.audio_capture",
        "host_agent.audio_playback",
        "host_agent.clipboard_manager",
        "host_agent.terminal_manager",
        "host_agent.file_manager",
        "host_agent.system_manager",
        "host_agent.deployment_manager",
        "host_agent.tray_menu",
        "host_agent.make_icon"
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "IPython", "jupyter"],
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
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(HOST_DIR / "icon.ico"),
)

# -*- coding: utf-8 -*-
"""
Meikova Relay Desktop Client (Avionics Remote Viewer).
Built on Microsoft Edge WebView2 (pywebview) matching Meikova Loop desktop architecture.

Features:
- Standalone Native Desktop Window (no browser tabs/chrome needed)
- Native Per-Monitor High-DPI Awareness
- Native Win32 Immersive Dark Titlebar (#070D17)
- System Tray Integration with Dark Context Menu & Telemetry
- Global Hotkey Interception in Fullscreen Remote Mode
- Offline-First Local SQLite Cache (%LOCALAPPDATA%\\MeikovaRelayClient)
- Cross-Platform: Windows 10/11, macOS, Linux
"""

import argparse
import json
import logging
import mimetypes
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Optional

# Bootstrap sys.path for local module imports
_current_dir = Path(__file__).resolve().parent
_root_dir = _current_dir.parent
for _p in [str(_root_dir), str(_current_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("meikova.relay.desktop_client")

try:
    import webview
except ImportError:
    webview = None

# Local cache DB
try:
    from client_desktop.local_db import ClientLocalDB, get_client_data_dir
except ImportError:
    from local_db import ClientLocalDB, get_client_data_dir

# Enable file logging in local data dir
try:
    _log_file = get_client_data_dir() / "desktop_client.log"
    _file_handler = logging.FileHandler(str(_log_file), encoding="utf-8", mode="a")
    _file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logging.getLogger().addHandler(_file_handler)
except Exception:
    pass


def find_client_resource(rel_path: str) -> Optional[Path]:
    """Locate bundled asset across development, installed, and PyInstaller frozen modes."""
    meipass = getattr(sys, "_MEIPASS", None)
    candidates = [
        Path(meipass) / rel_path if meipass else None,
        Path(meipass) / "client_desktop" / rel_path if meipass else None,
        Path(meipass) / "host_agent" / rel_path if meipass else None,
        _root_dir / "client_desktop" / rel_path,
        _root_dir / "host_agent" / rel_path,
        _current_dir / rel_path,
        _current_dir / "tray_icons" / rel_path,
        _root_dir / rel_path,
    ]
    for c in candidates:
        if c:
            p = Path(c)
            if p.is_file() or p.is_dir():
                return p.resolve()
    return None

# Win32 High DPI Awareness & DWM Dark Mode
if sys.platform == "win32":
    import ctypes
    from ctypes import byref, c_int, wintypes

    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass


def ensure_interactive_desktop() -> bool:
    """Attaches process and thread to winsta0\\default so windows & tray icon appear on the active user desktop."""
    if sys.platform == "win32":
        try:
            import ctypes
            u = ctypes.windll.user32
            hw = u.OpenWindowStationW('winsta0', False, 0x000F037F)
            if hw:
                u.SetProcessWindowStation(hw)
            hd = u.OpenDesktopW('default', 0, False, 0x000F01FF)
            if hd:
                u.SetThreadDesktop(hd)
            return True
        except Exception:
            pass
    return False

ensure_interactive_desktop()


def hide_console():
    """Hides terminal window if launched via python.exe on Windows."""
    if sys.platform == "win32":
        try:
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0)
        except Exception:
            pass


def apply_dark_titlebar(hwnd):
    """Applies immersive dark theme to Windows titlebar to match #070D17 palette and eliminates white borders."""
    if sys.platform != "win32" or not hwnd:
        return
    try:
        dwmapi = ctypes.windll.dwmapi
        dark = c_int(1)
        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20 (or 19 on older builds)
        dwmapi.DwmSetWindowAttribute(hwnd, 20, byref(dark), ctypes.sizeof(dark))
        dwmapi.DwmSetWindowAttribute(hwnd, 19, byref(dark), ctypes.sizeof(dark))
        # DWMWA_CAPTION_COLOR = 35 -> #070D17 (BGR: 0x00170D07)
        caption_color = c_int(0x00170D07)
        dwmapi.DwmSetWindowAttribute(hwnd, 35, byref(caption_color), ctypes.sizeof(caption_color))
        # DWMWA_BORDER_COLOR = 34 -> #070D17 (BGR: 0x00170D07)
        dwmapi.DwmSetWindowAttribute(hwnd, 34, byref(caption_color), ctypes.sizeof(caption_color))
        # DWMWA_TEXT_COLOR = 36 -> #F8FAFC (BGR: 0x00FCFAF8)
        text_color = c_int(0x00FCFAF8)
        dwmapi.DwmSetWindowAttribute(hwnd, 36, byref(text_color), ctypes.sizeof(text_color))

        # Extend DWM frame over entire client area to completely remove white non-client title/border strip
        class _MARGINS(ctypes.Structure):
            _fields_ = [
                ('cxLeftWidth', ctypes.c_int),
                ('cxRightWidth', ctypes.c_int),
                ('cyTopHeight', ctypes.c_int),
                ('cyBottomHeight', ctypes.c_int)
            ]
        m = _MARGINS(-1, -1, -1, -1)
        dwmapi.DwmExtendFrameIntoClientArea(hwnd, byref(m))
    except Exception as e:
        logger.debug("DWM dark titlebar error: %s", e)


def set_window_icon(hwnd):
    """Sets titlebar and taskbar icon for the window using Win32 API."""
    if sys.platform != "win32" or not hwnd:
        return
    try:
        icon_path = find_client_resource("icon.ico")
        if not icon_path or not icon_path.is_file():
            icon_path = find_client_resource("client_desktop/icon.ico")
        if not icon_path or not icon_path.is_file():
            icon_path = find_client_resource("host_agent/icon.ico")

        if not icon_path or not icon_path.is_file():
            icon_path = get_client_data_dir() / "meikova_relay_icon.ico"

        user32 = ctypes.windll.user32
        # LR_LOADFROMFILE = 0x0010, IMAGE_ICON = 1, WM_SETICON = 0x0080
        hicon_sm = user32.LoadImageW(0, str(icon_path), 1, 16, 16, 0x00000010)
        hicon_lg = user32.LoadImageW(0, str(icon_path), 1, 32, 32, 0x00000010)
        if hicon_sm:
            user32.SendMessageW(hwnd, 0x0080, 0, hicon_sm)
        if hicon_lg:
            user32.SendMessageW(hwnd, 0x0080, 1, hicon_lg)
    except Exception as e:
        logger.debug("Set window icon error: %s", e)


class DesktopBridge:
    """JavaScript-to-Python Native Bridge exposed to web application."""
    def __init__(self, local_db: ClientLocalDB):
        self.db = local_db
        self._window = None
        self._is_fullscreen = False

    def set_window(self, window):
        self._window = window

    # --- System Controls ---
    def is_desktop_client(self) -> bool:
        return True

    def minimize(self):
        if self._window:
            self._window.minimize()

    def toggle_fullscreen(self) -> bool:
        if self._window:
            self._window.toggle_fullscreen()
            self._is_fullscreen = not self._is_fullscreen
            return self._is_fullscreen
        return False

    def is_fullscreen(self) -> bool:
        return self._is_fullscreen

    # --- Clipboard ---
    def copy_to_clipboard(self, text: str) -> bool:
        try:
            import pyperclip
            pyperclip.copy(text)
            return True
        except Exception:
            return False

    def get_clipboard_text(self) -> str:
        try:
            import pyperclip
            return pyperclip.paste() or ""
        except Exception:
            return ""

    # --- Offline Local Storage ---
    def save_local_kv(self, key: str, value: str) -> bool:
        try:
            self.db.set_kv(key, value)
            return True
        except Exception as e:
            logger.error("save_local_kv error: %s", e)
            return False

    def get_local_kv(self, key: str, default=None):
        return self.db.get_kv(key, default)

    def cache_devices(self, devices: list) -> bool:
        try:
            self.db.cache_devices(devices)
            return True
        except Exception as e:
            logger.error("cache_devices error: %s", e)
            return False

    def get_cached_devices(self) -> list:
        return self.db.get_cached_devices()

    def record_quick_connect(self, room_id: str, device_name: str = "") -> bool:
        try:
            self.db.record_connection(room_id, device_name)
            return True
        except Exception as e:
            logger.error("record_quick_connect error: %s", e)
            return False

    def get_recent_history(self) -> list:
        return self.db.get_recent_history()

    # --- OS Integration ---
    def open_external_url(self, url: str):
        import webbrowser
        webbrowser.open(url)

    def notify(self, title: str, message: str):
        logger.info("[NOTIFICATION] %s: %s", title, message)

    def minimize_to_tray(self):
        if self._window:
            try:
                self._window.hide()
            except Exception as e:
                logger.debug("Failed to hide window: %s", e)

    def start_drag(self):
        """Native Win32 window drag initiated from custom titlebar."""
        if sys.platform == "win32":
            try:
                hwnd = ctypes.windll.user32.FindWindowW(None, "Meikova Relay — Avionics Console")
                if hwnd:
                    ctypes.windll.user32.ReleaseCapture()
                    ctypes.windll.user32.SendMessageW(hwnd, 0x00A1, 2, 0)  # WM_NCLBUTTONDOWN, HTCAPTION
            except Exception as e:
                logger.debug("start_drag error: %s", e)

    def minimize_window(self):
        """Minimizes window to OS taskbar."""
        if self._window:
            try:
                self._window.minimize()
            except Exception as e:
                logger.debug("minimize_window error: %s", e)

    def toggle_maximize(self) -> bool:
        """Toggles maximize/restore state and returns new maximized boolean."""
        if self._window:
            if sys.platform == "win32":
                try:
                    hwnd = ctypes.windll.user32.FindWindowW(None, "Meikova Relay — Avionics Console")
                    if hwnd:
                        is_zoomed = bool(ctypes.windll.user32.IsZoomed(hwnd))
                        if is_zoomed:
                            ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                        else:
                            ctypes.windll.user32.ShowWindow(hwnd, 3)  # SW_MAXIMIZE
                        return not is_zoomed
                except Exception as e:
                    logger.debug("toggle_maximize win32 error: %s", e)
            try:
                self._window.toggle_fullscreen()
            except Exception:
                pass
        return False

    def is_maximized(self) -> bool:
        """Returns True if window is currently maximized."""
        if sys.platform == "win32":
            try:
                hwnd = ctypes.windll.user32.FindWindowW(None, "Meikova Relay — Avionics Console")
                if hwnd:
                    return bool(ctypes.windll.user32.IsZoomed(hwnd))
            except Exception:
                pass
        return False

    def close_window(self):
        """Hides window to system tray when custom close button is clicked."""
        if self._window:
            try:
                self._window.hide()
            except Exception as e:
                logger.debug("close_window error: %s", e)


def is_autostart_enabled(app_name: str = "MeikovaRelayClient") -> bool:
    """Checks if the app is registered in system autostart across Windows, macOS, and Linux."""
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_READ,
            ) as k:
                val, _ = winreg.QueryValueEx(k, app_name)
                return bool(val)
        except OSError:
            return False
    elif sys.platform == "darwin":
        plist = Path.home() / "Library" / "LaunchAgents" / "com.meikovarelay.client.plist"
        return plist.is_file()
    else:
        desktop = Path.home() / ".config" / "autostart" / "meikovarelay_client.desktop"
        return desktop.is_file()


def set_autostart(enable: bool, app_name: str = "MeikovaRelayClient") -> bool:
    """Enables or disables auto-start at logon via system configuration across platforms."""
    if getattr(sys, "frozen", False):
        exe_cmd = f'"{sys.executable}"'
    else:
        exe_cmd = f'"{sys.executable}" "{Path(__file__).resolve()}"'

    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE,
            ) as k:
                if enable:
                    winreg.SetValueEx(k, app_name, 0, winreg.REG_SZ, exe_cmd)
                else:
                    try:
                        winreg.DeleteValue(k, app_name)
                    except OSError:
                        pass
            return True
        except Exception as e:
            logger.warning("Failed to update Windows autostart registry: %s", e)
            return False
    elif sys.platform == "darwin":
        plist = Path.home() / "Library" / "LaunchAgents" / "com.meikovarelay.client.plist"
        try:
            if enable:
                plist.parent.mkdir(parents=True, exist_ok=True)
                content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.meikovarelay.client</string>
    <key>ProgramArguments</key>
    <array>
        <string>{sys.executable}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>"""
                plist.write_text(content, encoding="utf-8")
            else:
                if plist.exists():
                    plist.unlink()
            return True
        except Exception:
            return False
    else:
        desktop = Path.home() / ".config" / "autostart" / "meikovarelay_client.desktop"
        try:
            if enable:
                desktop.parent.mkdir(parents=True, exist_ok=True)
                content = f"""[Desktop Entry]
Type=Application
Name=Meikova Relay Client
Comment=Meikova Relay Avionics Desktop Client
Exec={exe_cmd}
Terminal=false
Categories=Network;RemoteAccess;
"""
                desktop.write_text(content, encoding="utf-8")
            else:
                if desktop.exists():
                    desktop.unlink()
            return True
        except Exception:
            return False


if sys.platform == "win32":
    try:
        import clr
        clr.AddReference("System.Windows.Forms")
        clr.AddReference("System.Drawing")
        from System.Windows.Forms import (
            ProfessionalColorTable,
            ToolStripProfessionalRenderer,
            TextRenderer,
            TextFormatFlags,
        )
        from System.Drawing import Color, Pen

        class AmbientDarkColorTable(ProfessionalColorTable):
            """Meikova Relay ambient dark color palette for ContextMenuStrip."""
            @property
            def ToolStripDropDownBackground(self):
                return Color.FromArgb(7, 13, 23)  # #070D17

            @property
            def ImageMarginGradientBegin(self):
                return Color.FromArgb(7, 13, 23)

            @property
            def ImageMarginGradientMiddle(self):
                return Color.FromArgb(7, 13, 23)

            @property
            def ImageMarginGradientEnd(self):
                return Color.FromArgb(7, 13, 23)

            @property
            def MenuBorder(self):
                return Color.FromArgb(30, 41, 59)  # #1e293b

            @property
            def MenuItemBorder(self):
                return Color.FromArgb(34, 197, 94)  # #22c55e neon green border

            @property
            def MenuItemSelected(self):
                return Color.FromArgb(30, 41, 59)

            @property
            def MenuItemSelectedGradientBegin(self):
                return Color.FromArgb(30, 41, 59)

            @property
            def MenuItemSelectedGradientEnd(self):
                return Color.FromArgb(30, 41, 59)

            @property
            def MenuItemPressedGradientBegin(self):
                return Color.FromArgb(15, 23, 42)

            @property
            def MenuItemPressedGradientEnd(self):
                return Color.FromArgb(15, 23, 42)

            @property
            def SeparatorDark(self):
                return Color.FromArgb(30, 41, 59)

            @property
            def SeparatorLight(self):
                return Color.FromArgb(7, 13, 23)

        class AmbientDarkRenderer(ToolStripProfessionalRenderer):
            """Custom renderer ensuring anti-aliased dark mode text, green headers, and clean hairlines."""
            def __init__(self):
                super().__init__(AmbientDarkColorTable())

            def OnRenderItemText(self, e):
                txt = e.Text
                bounds = e.TextRectangle
                item = e.Item
                if not item.Enabled:
                    color = Color.FromArgb(34, 197, 94)  # Brand green header #22c55e
                elif item.Name == "item_quit":
                    color = Color.FromArgb(248, 113, 113) if item.Selected else Color.FromArgb(239, 68, 68)
                elif item.Selected:
                    color = Color.FromArgb(255, 255, 255)
                else:
                    color = Color.FromArgb(226, 232, 240)  # Slate 200

                flags = TextFormatFlags.Left | TextFormatFlags.VerticalCenter | TextFormatFlags.SingleLine
                TextRenderer.DrawText(e.Graphics, txt, e.TextFont, bounds, color, flags)

            def OnRenderSeparator(self, e):
                g = e.Graphics
                y = e.Item.Height // 2
                pen = Pen(Color.FromArgb(30, 41, 59), 1)
                g.DrawLine(pen, 28, y, e.Item.Width - 8, y)
                pen.Dispose()
    except Exception:
        AmbientDarkRenderer = None
else:
    AmbientDarkRenderer = None


_GLOBAL_TRAY_REFS = []


class ClientTray:
    """Cross-platform Ambient-Dark Tray Manager for Meikova Relay Client (Meikova Harvest & Meikova Loop standard)."""

    def __init__(self, window, url: str = "http://localhost:8080", server=None):
        self.window = window
        self.url = url
        self.server = server
        self._tray = None
        self.is_quitting = False
        self._autostart_item = None

    def _get_icon_bitmap(self, name: str):
        if sys.platform != "win32":
            return None
        try:
            from System.Drawing import Bitmap
            p = find_client_resource(f"tray_icons/{name}.png")
            if not p:
                p = find_client_resource(f"{name}.png")
            if p and p.is_file():
                return Bitmap(str(p))
        except Exception as e:
            logger.debug("Failed loading icon bitmap %s: %s", name, e)
        return None

    def show_window(self):
        ensure_interactive_desktop()
        if not self.window:
            return
        try:
            self.window.show()
            self.window.restore()
        except Exception as e:
            logger.debug("Window show/restore error: %s", e)

        if sys.platform == "win32":
            try:
                hwnd = ctypes.windll.user32.FindWindowW(None, "Meikova Relay — Avionics Console")
                if hwnd:
                    ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    ctypes.windll.user32.ShowWindow(hwnd, 5)  # SW_SHOW
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
            except Exception:
                pass
        elif sys.platform == "darwin":
            try:
                import subprocess
                subprocess.run(["osascript", "-e", 'tell application "Meikova Relay Client" to activate'], check=False)
            except Exception:
                pass
        elif sys.platform.startswith("linux"):
            try:
                import subprocess
                subprocess.run(["wmctrl", "-a", "Meikova Relay — Avionics Console"], check=False)
            except Exception:
                pass

    def open_downloads_folder(self):
        try:
            import os, webbrowser
            d = Path.home() / "Downloads"
            if hasattr(os, "startfile"):
                os.startfile(str(d))
            else:
                webbrowser.open(str(d))
        except Exception as e:
            logger.debug("open_downloads_folder error: %s", e)

    def quit(self):
        self.is_quitting = True
        self.stop()
        if self.window:
            try:
                self.window.hide()
            except Exception:
                pass
        if self.server:
            try:
                self.server.stop_local_relay()
            except Exception:
                pass
        if self.window:
            try:
                self.window.destroy()
            except Exception:
                pass
        os._exit(0)

    def start(self):
        if self._tray is not None:
            return
        ensure_interactive_desktop()
        if sys.platform == "win32" and AmbientDarkRenderer:
            try:
                import clr
                clr.AddReference("System.Windows.Forms")
                from System.Windows.Forms import Application, MethodInvoker
                for _ in range(15):
                    if Application.OpenForms.Count > 0:
                        form = Application.OpenForms[0]
                        form.Invoke(MethodInvoker(self._setup_winforms))
                        return
                    time.sleep(0.05)
                self._setup_winforms()
                return
            except Exception as e:
                logger.warning("WinForms tray setup failed, fallback to pystray: %s", e)
        self._setup_pystray()

    def _setup_winforms(self):
        if self._tray is not None:
            return
        ensure_interactive_desktop()
        import clr
        clr.AddReference("System.Windows.Forms")
        clr.AddReference("System.Drawing")
        from System.Windows.Forms import (
            NotifyIcon,
            ContextMenuStrip,
            ToolStripMenuItem,
            ToolStripSeparator,
            MouseButtons,
            MouseEventHandler,
            Padding,
        )
        from System.Drawing import Icon, SystemIcons, Font, FontStyle, Size
        from System import EventHandler

        tray = NotifyIcon()
        ico_file = find_client_resource("icon.ico")
        if not ico_file or not ico_file.is_file():
            ico_file = find_client_resource("client_desktop/icon.ico")
        if not ico_file or not ico_file.is_file():
            ico_file = find_client_resource("host_agent/icon.ico")

        if not ico_file or not ico_file.is_file():
            ico_file = get_client_data_dir() / "meikova_relay_icon.ico"

        try:
            if ico_file and Path(ico_file).is_file():
                tray.Icon = Icon(str(ico_file))
            else:
                tray.Icon = SystemIcons.Application
        except Exception as e:
            logger.debug("Failed loading tray icon from file: %s", e)
            tray.Icon = SystemIcons.Application

        tray.Text = "Meikova Relay — Avionics Console"[:63]

        menu = ContextMenuStrip()
        if AmbientDarkRenderer:
            menu.Renderer = AmbientDarkRenderer()

        menu.ImageScalingSize = Size(18, 18)
        menu.ShowImageMargin = True
        menu.ShowCheckMargin = False

        font_regular = Font("Segoe UI", 9.5, FontStyle.Regular)
        font_bold = Font("Segoe UI", 9.5, FontStyle.Bold)
        item_pad = Padding(4, 5, 4, 5)

        # 1. Header (Branding, Disabled)
        header = ToolStripMenuItem("MEIKOVA RELAY // v1.4.1")
        header.Enabled = False
        header.Font = font_bold
        header.Padding = Padding(4, 6, 4, 6)
        bmp_logo = self._get_icon_bitmap("logo")
        if bmp_logo:
            header.Image = bmp_logo
        menu.Items.Add(header)
        menu.Items.Add(ToolStripSeparator())

        # 2. Show Window
        item_show = ToolStripMenuItem("Mở Meikova Relay")
        item_show.Font = font_bold
        item_show.Padding = item_pad
        bmp_win = self._get_icon_bitmap("window")
        if bmp_win:
            item_show.Image = bmp_win
        item_show.Click += EventHandler(lambda s, e: self.show_window())
        menu.Items.Add(item_show)

        # 3. Open in Browser
        item_web = ToolStripMenuItem("Mở trên trình duyệt Web")
        item_web.Font = font_regular
        item_web.Padding = item_pad
        bmp_web = self._get_icon_bitmap("browser")
        if bmp_web:
            item_web.Image = bmp_web
        item_web.Click += EventHandler(lambda s, e: webbrowser.open(self.url))
        menu.Items.Add(item_web)

        # 4. Open Downloads
        item_dl = ToolStripMenuItem("Mở thư mục tệp tin (Downloads)")
        item_dl.Font = font_regular
        item_dl.Padding = item_pad
        bmp_folder = self._get_icon_bitmap("folder")
        if bmp_folder:
            item_dl.Image = bmp_folder
        item_dl.Click += EventHandler(lambda s, e: self.open_downloads_folder())
        menu.Items.Add(item_dl)

        menu.Items.Add(ToolStripSeparator())

        # 5. Autostart toggle
        auto_on = is_autostart_enabled()
        self._autostart_item = ToolStripMenuItem(
            f"Khởi động cùng Windows: {'Bật' if auto_on else 'Tắt'}"
        )
        self._autostart_item.Font = font_regular
        self._autostart_item.Padding = item_pad
        bmp_auto = self._get_icon_bitmap("autostart_on" if auto_on else "autostart")
        if bmp_auto:
            self._autostart_item.Image = bmp_auto

        def _toggle_autostart(s, e):
            current = is_autostart_enabled()
            nxt = not current
            set_autostart(nxt)
            if self._autostart_item:
                self._autostart_item.Text = f"Khởi động cùng Windows: {'Bật' if nxt else 'Tắt'}"
                new_bmp = self._get_icon_bitmap("autostart_on" if nxt else "autostart")
                if new_bmp:
                    self._autostart_item.Image = new_bmp

        self._autostart_item.Click += EventHandler(_toggle_autostart)
        menu.Items.Add(self._autostart_item)

        # 6. Reload UI
        item_reload = ToolStripMenuItem("Tải lại giao diện (F5)")
        item_reload.Font = font_regular
        item_reload.Padding = item_pad
        bmp_refresh = self._get_icon_bitmap("refresh")
        if bmp_refresh:
            item_reload.Image = bmp_refresh
        item_reload.Click += EventHandler(lambda s, e: self.window.evaluate_js("window.location.reload()"))
        menu.Items.Add(item_reload)

        menu.Items.Add(ToolStripSeparator())

        # 7. Quit
        item_quit = ToolStripMenuItem("Thoát hoàn toàn")
        item_quit.Name = "item_quit"
        item_quit.Font = font_regular
        item_quit.Padding = item_pad
        bmp_quit = self._get_icon_bitmap("quit")
        if bmp_quit:
            item_quit.Image = bmp_quit
        item_quit.Click += EventHandler(lambda s, e: self.quit())
        menu.Items.Add(item_quit)

        tray.ContextMenuStrip = menu

        def _on_mouse_click(s, args):
            if args.Button == MouseButtons.Left:
                self.show_window()

        tray.MouseClick += MouseEventHandler(_on_mouse_click)
        tray.DoubleClick += EventHandler(lambda s, e: self.show_window())

        tray.Visible = True
        self._tray = tray

        _GLOBAL_TRAY_REFS.clear()
        _GLOBAL_TRAY_REFS.extend([tray, menu])
        logger.info("Native Windows WinForms Tray attached with ambient dark theme.")

    def _setup_pystray(self):
        try:
            import pystray
            from PIL import Image
            tray_path = find_client_resource("tray_icon.png") or find_client_resource("host_agent/tray_icon.png") or find_client_resource("icon.png")
            if tray_path and Path(tray_path).is_file():
                with Image.open(str(tray_path)) as im:
                    icon_img = im.resize((64, 64), Image.Resampling.LANCZOS).convert("RGBA")
            else:
                icon_img = Image.new("RGBA", (64, 64), (17, 21, 27, 255))

            def on_show(icon=None, item=None):
                self.show_window()

            def on_fullscreen(icon=None, item=None):
                if self.window:
                    self.window.toggle_fullscreen()

            def on_web(icon=None, item=None):
                webbrowser.open(self.url)

            def on_dl(icon=None, item=None):
                self.open_downloads_folder()

            def on_toggle_auto(icon=None, item=None):
                nxt = not is_autostart_enabled()
                set_autostart(nxt)

            def on_reload(icon=None, item=None):
                if self.window:
                    self.window.evaluate_js("window.location.reload()")

            def on_quit(icon=None, item=None):
                self.quit()

            auto_on = is_autostart_enabled()
            menu = pystray.Menu(
                pystray.MenuItem("MEIKOVA RELAY // v1.4.1", None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Mở Meikova Relay", on_show, default=True),
                pystray.MenuItem("Mở trên trình duyệt Web", on_web),
                pystray.MenuItem("Mở thư mục tệp tin (Downloads)", on_dl),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(f"Khởi động cùng hệ thống: {'Bật' if auto_on else 'Tắt'}", on_toggle_auto),
                pystray.MenuItem("Tải lại giao diện (F5)", on_reload),
                pystray.MenuItem("Toàn màn hình (F11)", on_fullscreen),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Thoát hoàn toàn", on_quit)
            )

            self._tray = pystray.Icon("MeikovaRelayClient", icon_img, "Meikova Relay Client", menu)
            self._tray._thread = threading.current_thread()
            self._tray._running = False
            threading.Thread(target=self._tray.run, daemon=True).start()
        except Exception as e:
            logger.debug("pystray setup failed: %s", e)

    def stop(self):
        if self._tray:
            try:
                if hasattr(self._tray, "Visible"):
                    self._tray.Visible = False
                    self._tray.Dispose()
                else:
                    if hasattr(self._tray, "_hide"):
                        self._tray._hide()
                    if hasattr(self._tray, "visible"):
                        self._tray.visible = False
                    if hasattr(self._tray, "stop"):
                        self._tray.stop()
            except Exception:
                pass
            self._tray = None
        _GLOBAL_TRAY_REFS.clear()


def resolve_web_client_dir() -> Path:
    """Locate bundled web-client directory across development and PyInstaller frozen modes."""
    meipass = getattr(sys, "_MEIPASS", None)
    candidates = [
        Path(meipass) / "web-client" if meipass else None,
        _root_dir / "relay-server" / "public",
        _root_dir / "web-client",
        Path(__file__).resolve().parent.parent / "relay-server" / "public",
        Path(__file__).resolve().parent.parent / "web-client",
        Path.cwd() / "relay-server" / "public",
        Path.cwd() / "web-client",
    ]
    for c in candidates:
        if c and Path(c).is_dir():
            return Path(c).resolve()
    return _root_dir / "relay-server" / "public"


class ClientEmbeddedServer:
    """Internal loopback HTTP server serving bundled web-client static files and reverse-proxying API."""
    def __init__(self, web_client_dir: Path, target_relay_url: str = "http://localhost:8080"):
        self.web_client_dir = web_client_dir
        self.target_relay_url = target_relay_url.rstrip("/")
        self.server = None
        self.port = 0
        self.relay_process = None

    def auto_start_local_relay(self):
        """Auto-spawns node relay-server/server.js if target is localhost, currently offline, and node is present."""
        if "localhost" not in self.target_relay_url and "127.0.0.1" not in self.target_relay_url:
            return
        if is_server_online(self.target_relay_url):
            return
        server_js = _root_dir / "relay-server" / "server.js"
        if server_js.exists() and shutil.which("node"):
            try:
                creationflags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
                self.relay_process = subprocess.Popen(
                    ["node", str(server_js)],
                    cwd=str(server_js.parent),
                    creationflags=creationflags
                )
                logger.info("Auto-spawned local relay server (PID: %d)", self.relay_process.pid)
                # Wait briefly for server to be responsive
                for _ in range(15):
                    time.sleep(0.2)
                    if is_server_online(self.target_relay_url):
                        logger.info("Local relay server online at %s", self.target_relay_url)
                        break
            except Exception as e:
                logger.debug("Failed spawning local relay server: %s", e)

    def stop_local_relay(self):
        if self.relay_process:
            try:
                self.relay_process.terminate()
                self.relay_process.wait(timeout=2)
            except Exception:
                try:
                    self.relay_process.kill()
                except Exception:
                    pass
            self.relay_process = None

    def start(self) -> str:
        app_self = self
        web_dir = str(self.web_client_dir)

        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=web_dir, **kwargs)

            def log_message(self, format, *args):
                pass  # suppress console log spam

            def do_GET(self):
                if self.path.startswith("/api/"):
                    self._proxy_request("GET")
                    return
                super().do_GET()

            def do_POST(self):
                if self.path.startswith("/api/"):
                    self._proxy_request("POST")
                    return
                super().do_POST()

            def do_PUT(self):
                if self.path.startswith("/api/"):
                    self._proxy_request("PUT")
                    return
                super().do_PUT()

            def do_DELETE(self):
                if self.path.startswith("/api/"):
                    self._proxy_request("DELETE")
                    return
                super().do_DELETE()

            def _proxy_request(self, method: str):
                target_url = f"{app_self.target_relay_url}{self.path}"
                content_len = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_len) if content_len > 0 else None
                headers = {k: v for k, v in self.headers.items() if k.lower() not in ("host", "content-length")}
                headers["User-Agent"] = "MeikovaRelayClient"
                try:
                    req = urllib.request.Request(target_url, data=body, headers=headers, method=method)
                    with urllib.request.urlopen(req, timeout=5.0) as resp:
                        resp_data = resp.read()
                        self.send_response(resp.status)
                        for h_key, h_val in resp.getheaders():
                            if h_key.lower() not in ("content-length", "transfer-encoding"):
                                self.send_header(h_key, h_val)
                        self.send_header("Content-Length", str(len(resp_data)))
                        self.end_headers()
                        self.wfile.write(resp_data)
                except urllib.error.HTTPError as he:
                    err_data = he.read()
                    self.send_response(he.code)
                    self.send_header("Content-Type", he.headers.get("Content-Type", "application/json"))
                    self.send_header("Content-Length", str(len(err_data)))
                    self.end_headers()
                    self.wfile.write(err_data)
                except Exception:
                    # Relay server is offline or unreachable - return friendly JSON, NEVER crash WebView
                    err_json = json.dumps({
                        "success": False,
                        "offline": True,
                        "error": "Relay Server is offline",
                        "relay_url": app_self.target_relay_url
                    }).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(err_json)))
                    self.end_headers()
                    self.wfile.write(err_json)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_port
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        logger.info("Embedded Desktop Web Server started at http://127.0.0.1:%d", self.port)
        return f"http://127.0.0.1:{self.port}"


def is_server_online(url: str) -> bool:
    try:
        status_url = f"{url.rstrip('/')}/api/sync/status"
        req = urllib.request.Request(status_url, headers={"User-Agent": "MeikovaRelayClient"})
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            return resp.status == 200
    except Exception:
        return False


def main(argv=None):
    ensure_interactive_desktop()
    parser = argparse.ArgumentParser(prog="MeikovaRelayClient", description="Meikova Relay Desktop Avionics Client")
    parser.add_argument("--url", type=str, default="http://localhost:8080", help="Relay Server URL (default: http://localhost:8080)")
    parser.add_argument("--debug", action="store_true", help="Enable WebView DevTools")
    args = parser.parse_args(argv)

    if not args.debug:
        hide_console()

    # Single-instance protection
    _h_mutex = None
    if sys.platform == "win32":
        try:
            kernel32 = ctypes.windll.kernel32
            mutex_name = "Local\\MeikovaRelay_Desktop_Client_Mutex"
            _h_mutex = kernel32.CreateMutexW(None, False, mutex_name)
            if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
                hwnd = ctypes.windll.user32.FindWindowW(None, "Meikova Relay — Avionics Console")
                if hwnd:
                    logger.info("Meikova Relay Client is already running. Restoring window.")
                    ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
                    sys.exit(0)
                else:
                    logger.info("Mutex exists but no window found. Continuing launch.")
        except Exception as e:
            logger.debug("Mutex check failed: %s", e)

    local_db = ClientLocalDB()
    bridge = DesktopBridge(local_db)

    # Start embedded server serving bundled web-client static files
    web_client_dir = resolve_web_client_dir()
    embedded_server = ClientEmbeddedServer(web_client_dir, target_relay_url=args.url)
    embedded_server.auto_start_local_relay()
    local_base_url = embedded_server.start()
    app_url = f"{local_base_url}/index.html?platform=desktop"

    # AppUserModelID for Windows Taskbar Grouping & Icon
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("MeikovaRelay.DesktopClient.1.0")
        except Exception:
            pass

    # Find icon cross-platform (ico for Windows, png for macOS/Linux)
    if sys.platform == "win32":
        ico_path = find_client_resource("icon.ico")
        if not ico_path:
            ico_path = find_client_resource("client_desktop/icon.ico")
        if not ico_path:
            ico_path = find_client_resource("host_agent/icon.ico")
        icon_str = str(ico_path) if ico_path and ico_path.exists() else None
    else:
        png_path = find_client_resource("icon.png")
        if not png_path:
            png_path = find_client_resource("host_agent/icon.png")
        icon_str = str(png_path) if png_path and png_path.exists() else None

    # Initialize webview window with ambient dark styling and custom frameless titlebar
    window = webview.create_window(
        title="Meikova Relay — Avionics Console",
        url=app_url,
        width=1366,
        height=840,
        min_size=(380, 520),
        background_color="#070D17",
        frameless=True,
        easy_drag=False,
        shadow=True,
        js_api=bridge
    )
    bridge.set_window(window)

    # Initialize system tray (delayed startup after webview creates WinForms context)
    tray = ClientTray(window, url=args.url, server=embedded_server)

    def on_shown():
        try:
            if not tray._tray:
                tray.start()
        except Exception as e:
            logger.debug("Tray setup error in on_shown: %s", e)

        def _apply_theme():
            time.sleep(0.3)
            try:
                hwnd = ctypes.windll.user32.FindWindowW(None, "Meikova Relay — Avionics Console")
                if hwnd:
                    set_window_icon(hwnd)
                    # Enable minimize/maximize styles for taskbar & titlebar controls
                    GWL_STYLE = -16
                    WS_MINIMIZEBOX = 0x00020000
                    WS_MAXIMIZEBOX = 0x00010000
                    style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
                    ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, style | WS_MINIMIZEBOX | WS_MAXIMIZEBOX)
                    apply_dark_titlebar(hwnd)
                    ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0027)
            except Exception as e:
                logger.debug("Failed applying window theme: %s", e)
        if sys.platform == "win32":
            threading.Thread(target=_apply_theme, daemon=True).start()

    window.events.shown += on_shown

    def on_loaded():
        if not tray._tray:
            try:
                tray.start()
            except Exception:
                pass

    window.events.loaded += on_loaded

    def on_closing():
        if tray.is_quitting:
            return True
        try:
            window.hide()
        except Exception as e:
            logger.debug("Failed to hide window on close: %s", e)
        return False

    window.events.closing += on_closing

    # Start Edge WebView2
    try:
        webview.start(debug=args.debug, icon=icon_str)
    finally:
        embedded_server.stop_local_relay()
        tray.stop()


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
Titan Remote Desktop Client (Avionics Remote Viewer).
Built on Microsoft Edge WebView2 (pywebview) matching MashLoop desktop architecture.

Features:
- Standalone Native Desktop Window (no browser tabs/chrome needed)
- Native Per-Monitor High-DPI Awareness
- Native Win32 Immersive Dark Titlebar (#070D17)
- System Tray Integration with Dark Context Menu & Telemetry
- Global Hotkey Interception in Fullscreen Remote Mode
- Offline-First Local SQLite Cache (%LOCALAPPDATA%\\TitanRemoteClient)
- Cross-Platform: Windows 10/11, macOS, Linux
"""

import argparse
import logging
import os
import sys
import threading
import time
import urllib.request
from pathlib import Path

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
logger = logging.getLogger("titan.desktop_client")

import webview

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
    """Applies immersive dark theme to Windows titlebar to match #070D17 palette."""
    if sys.platform != "win32" or not hwnd:
        return
    try:
        dwmapi = ctypes.windll.dwmapi
        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        dark = c_int(1)
        dwmapi.DwmSetWindowAttribute(hwnd, 20, byref(dark), ctypes.sizeof(dark))
        # DWMWA_CAPTION_COLOR = 35 -> #070D17 (BGR: 0x00170D07)
        caption_color = c_int(0x00170D07)
        dwmapi.DwmSetWindowAttribute(hwnd, 35, byref(caption_color), ctypes.sizeof(caption_color))
        # DWMWA_TEXT_COLOR = 36 -> #F8FAFC (BGR: 0x00FCFAF8)
        text_color = c_int(0x00FCFAF8)
        dwmapi.DwmSetWindowAttribute(hwnd, 36, byref(text_color), ctypes.sizeof(text_color))
    except Exception as e:
        logger.debug("DWM dark titlebar error: %s", e)


def set_window_icon(hwnd):
    """Sets titlebar and taskbar icon for the window using Win32 API."""
    if sys.platform != "win32" or not hwnd:
        return
    try:
        from host_agent.make_icon import render_unified_icon
        icon_path = get_client_data_dir() / "titan_icon.ico"
        if not icon_path.exists():
            img = render_unified_icon(256)
            img.save(str(icon_path), format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

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
                hwnd = ctypes.windll.user32.FindWindowW(None, "Titan Remote — Avionics Console")
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
                    hwnd = ctypes.windll.user32.FindWindowW(None, "Titan Remote — Avionics Console")
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
                hwnd = ctypes.windll.user32.FindWindowW(None, "Titan Remote — Avionics Console")
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


def is_autostart_enabled(app_name: str = "TitanRemoteClient") -> bool:
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
        plist = Path.home() / "Library" / "LaunchAgents" / "com.titanremote.client.plist"
        return plist.is_file()
    else:
        desktop = Path.home() / ".config" / "autostart" / "titanremote_client.desktop"
        return desktop.is_file()


def set_autostart(enable: bool, app_name: str = "TitanRemoteClient") -> bool:
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
        plist = Path.home() / "Library" / "LaunchAgents" / "com.titanremote.client.plist"
        try:
            if enable:
                plist.parent.mkdir(parents=True, exist_ok=True)
                content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.titanremote.client</string>
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
        desktop = Path.home() / ".config" / "autostart" / "titanremote_client.desktop"
        try:
            if enable:
                desktop.parent.mkdir(parents=True, exist_ok=True)
                content = f"""[Desktop Entry]
Type=Application
Name=Titan Remote Client
Comment=Titan Remote Avionics Desktop Client
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
            """Titan Remote ambient dark color palette for ContextMenuStrip."""
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
    """Cross-platform Ambient-Dark Tray Manager for Titan Remote Client (EveryThingDownloader & MashLoop standard)."""

    def __init__(self, window, url: str = "http://localhost:8080"):
        self.window = window
        self.url = url
        self._tray = None
        self.is_quitting = False
        self._autostart_item = None

    def _get_icon_bitmap(self, name: str):
        if sys.platform != "win32":
            return None
        try:
            from System.Drawing import Bitmap
            icon_dir = _root_dir / "client_desktop" / "tray_icons"
            p = icon_dir / f"{name}.png"
            if p.is_file():
                return Bitmap(str(p))
        except Exception:
            pass
        return None

    def show_window(self):
        if not self.window:
            return
        try:
            self.window.show()
            self.window.restore()
        except Exception as e:
            logger.debug("Window show/restore error: %s", e)

        if sys.platform == "win32":
            try:
                hwnd = ctypes.windll.user32.FindWindowW(None, "Titan Remote — Avionics Console")
                if hwnd:
                    ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    ctypes.windll.user32.ShowWindow(hwnd, 5)  # SW_SHOW
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
            except Exception:
                pass
        elif sys.platform == "darwin":
            try:
                import subprocess
                subprocess.run(["osascript", "-e", 'tell application "Titan Remote Client" to activate'], check=False)
            except Exception:
                pass
        elif sys.platform.startswith("linux"):
            try:
                import subprocess
                subprocess.run(["wmctrl", "-a", "Titan Remote — Avionics Console"], check=False)
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
                self.window.destroy()
            except Exception:
                pass
        os._exit(0)

    def start(self):
        if sys.platform == "win32" and AmbientDarkRenderer:
            try:
                self._setup_winforms()
                return
            except Exception as e:
                logger.warning("WinForms tray setup failed, fallback to pystray: %s", e)
        self._setup_pystray()

    def _setup_winforms(self):
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
        ico_file = _root_dir / "client_desktop" / "icon.ico"
        if not ico_file.is_file():
            ico_file = _root_dir / "host_agent" / "icon.ico"

        try:
            if ico_file.is_file():
                tray.Icon = Icon(str(ico_file))
            else:
                tray.Icon = SystemIcons.Application
        except Exception:
            tray.Icon = SystemIcons.Application

        tray.Text = "Titan Remote — Avionics Console"[:63]

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
        header = ToolStripMenuItem("TITAN REMOTE // v1.0.25")
        header.Enabled = False
        header.Font = font_bold
        header.Padding = Padding(4, 6, 4, 6)
        bmp_logo = self._get_icon_bitmap("logo")
        if bmp_logo:
            header.Image = bmp_logo
        menu.Items.Add(header)
        menu.Items.Add(ToolStripSeparator())

        # 2. Show Window
        item_show = ToolStripMenuItem("Mở Titan Remote")
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
            f"Khởi động cùng Windows: {'Bật ✓' if auto_on else 'Tắt'}"
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
                self._autostart_item.Text = f"Khởi động cùng Windows: {'Bật ✓' if nxt else 'Tắt'}"
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
            from host_agent.make_icon import render_unified_icon
            icon_img = render_unified_icon(64)

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
                pystray.MenuItem("TITAN REMOTE // v1.0.25", None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Mở Titan Remote", on_show, default=True),
                pystray.MenuItem("Mở trên trình duyệt Web", on_web),
                pystray.MenuItem("Mở thư mục tệp tin (Downloads)", on_dl),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(f"Khởi động cùng hệ thống: {'Bật ✓' if auto_on else 'Tắt'}", on_toggle_auto),
                pystray.MenuItem("Tải lại giao diện (F5)", on_reload),
                pystray.MenuItem("Toàn màn hình (F11)", on_fullscreen),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Thoát hoàn toàn", on_quit)
            )

            self._tray = pystray.Icon("TitanRemoteClient", icon_img, "Titan Remote Client", menu)
            threading.Thread(target=self._tray.run, daemon=True).start()
        except Exception as e:
            logger.debug("pystray setup failed: %s", e)

    def stop(self):
        if self._tray:
            try:
                if hasattr(self._tray, "Visible"):
                    self._tray.Visible = False
                    self._tray.Dispose()
                elif hasattr(self._tray, "stop"):
                    self._tray.stop()
            except Exception:
                pass
            self._tray = None
        _GLOBAL_TRAY_REFS.clear()


def is_server_online(url: str) -> bool:
    try:
        status_url = f"{url.rstrip('/')}/api/sync/status"
        req = urllib.request.Request(status_url, headers={"User-Agent": "TitanDesktopClient"})
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            return resp.status == 200
    except Exception:
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(prog="TitanRemoteClient", description="Titan Remote Desktop Avionics Client")
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
            mutex_name = "Local\\TitanRemote_Desktop_Client_Mutex"
            _h_mutex = kernel32.CreateMutexW(None, False, mutex_name)
            if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
                hwnd = ctypes.windll.user32.FindWindowW(None, "Titan Remote — Avionics Console")
                if hwnd:
                    logger.info("Titan Remote Client is already running. Restoring window.")
                    ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
                    sys.exit(0)
                else:
                    logger.info("Mutex exists but no window found. Continuing launch.")
        except Exception as e:
            logger.debug("Mutex check failed: %s", e)

    local_db = ClientLocalDB()
    bridge = DesktopBridge(local_db)

    # AppUserModelID for Windows Taskbar Grouping & Icon
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TitanRemote.DesktopClient.1.0")
        except Exception:
            pass

    # Find icon cross-platform (ico for Windows, png for macOS/Linux)
    if sys.platform == "win32":
        ico_path = _root_dir / "client_desktop" / "icon.ico"
        if not ico_path.exists():
            ico_path = _root_dir / "host_agent" / "icon.ico"
        icon_str = str(ico_path) if ico_path.exists() else None
    else:
        png_path = _root_dir / "host_agent" / "icon.png"
        icon_str = str(png_path) if png_path.exists() else None

    # Initialize webview window with ambient dark styling and custom frameless titlebar
    window = webview.create_window(
        title="Titan Remote — Avionics Console",
        url=args.url,
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
    tray = ClientTray(window, url=args.url)

    def on_shown():
        try:
            if not tray._tray:
                tray.start()
        except Exception as e:
            logger.debug("Tray setup error in on_shown: %s", e)

        def _apply_theme():
            time.sleep(0.3)
            try:
                hwnd = ctypes.windll.user32.FindWindowW(None, "Titan Remote — Avionics Console")
                if hwnd:
                    set_window_icon(hwnd)
                    # Enable resize borders and minimize/maximize styles for Aero snap & resizing
                    GWL_STYLE = -16
                    WS_THICKFRAME = 0x00040000
                    WS_MINIMIZEBOX = 0x00020000
                    WS_MAXIMIZEBOX = 0x00010000
                    style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
                    ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, style | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX)
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
        tray.stop()


if __name__ == "__main__":
    main()

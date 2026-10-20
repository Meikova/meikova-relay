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


class ClientTray:
    """Native Tray Manager for Titan Remote Client."""
    def __init__(self, window):
        self.window = window
        self._tray = None

    def start(self):
        try:
            import pystray
            from host_agent.make_icon import render_unified_icon
            icon_img = render_unified_icon(64)

            def on_show(icon, item):
                if self.window:
                    self.window.restore()
                    self.window.show()

            def on_fullscreen(icon, item):
                if self.window:
                    self.window.toggle_fullscreen()

            def on_quit(icon, item):
                icon.stop()
                if self.window:
                    self.window.destroy()
                os._exit(0)

            menu = pystray.Menu(
                pystray.MenuItem("Mở Titan Remote", on_show, default=True),
                pystray.MenuItem("Toàn màn hình (F11)", on_fullscreen),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Thoát", on_quit)
            )

            self._tray = pystray.Icon("TitanRemoteClient", icon_img, "Titan Remote Client", menu)
            threading.Thread(target=self._tray.run, daemon=True).start()
        except Exception as e:
            logger.debug("Systray initialization failed: %s", e)

    def stop(self):
        if self._tray:
            try:
                self._tray.stop()
            except Exception:
                pass


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

    # Initialize webview window with ambient dark styling
    window = webview.create_window(
        title="Titan Remote — Avionics Console",
        url=args.url,
        width=1366,
        height=840,
        min_size=(380, 520),
        background_color="#070D17",
        js_api=bridge
    )
    bridge.set_window(window)

    # Start system tray
    tray = ClientTray(window)
    tray.start()

    def on_loaded():
        # Apply dark titlebar and window icon once HWND is created
        if sys.platform == "win32":
            time.sleep(0.3)
            try:
                hwnd = ctypes.windll.user32.FindWindowW(None, "Titan Remote — Avionics Console")
                if hwnd:
                    apply_dark_titlebar(hwnd)
                    set_window_icon(hwnd)
            except Exception as e:
                logger.debug("Failed applying window theme: %s", e)

    window.events.loaded += on_loaded

    # Start Edge WebView2
    try:
        webview.start(debug=args.debug, gui="edgechromium" if sys.platform == "win32" else None)
    finally:
        tray.stop()


if __name__ == "__main__":
    main()

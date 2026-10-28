# -*- coding: utf-8 -*-
"""
Custom System Tray Menu for Meikova Relay Host.
Follows Ambient Dark / Meikova Harvest architecture:
- Dark theme context menu with Windows 10/11 uxtheme enforcement
- Custom vector icons for every menu item (Emerald, Cyan, White, Red)
- Rich telemetry header & status indicator
- In-menu quick toggles (Autostart, Keep Awake)
- Fully cross-platform: safely degrades to native text menu on Linux & macOS
"""

import sys
import os
import math
import webbrowser
from pathlib import Path
from typing import Optional, Dict, Any

current_dir = Path(__file__).resolve().parent

APP_VERSION = "1.4.0"

try:
    from PIL import Image, ImageDraw
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import pystray
    HAS_PYSTRAY = True
except Exception:
    HAS_PYSTRAY = False

# Palette constants
EMERALD = (34, 197, 94, 255)       # #22C55E
CYAN = (56, 189, 248, 255)         # #38BDF8
WHITE = (255, 255, 255, 255)       # #FFFFFF
RED = (239, 68, 68, 255)           # #EF4444
SLATE = (100, 116, 139, 255)       # #64748B
BG_DARK = (7, 13, 23, 255)         # #070D17

_icon_cache: Dict[str, Any] = {}
_hbitmap_cache: Dict[str, int] = {}


def _render_menu_icon(name: str) -> Optional[Any]:
    if not HAS_PIL:
        return None

    if name in _icon_cache:
        return _icon_cache[name]

    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    if name == "logo":
        for candidate_path in [
            current_dir / "tray_icons" / "logo.png",
            current_dir / "tray_icon.png",
            Path(__file__).resolve().parent / "tray_icons" / "logo.png",
            Path(__file__).resolve().parent / "tray_icon.png",
            Path(__file__).resolve().parent / "icon.png",
        ]:
            if candidate_path.is_file():
                try:
                    with Image.open(candidate_path) as im:
                        master = im.resize((size, size), Image.Resampling.LANCZOS)
                        _icon_cache[name] = master
                        return master
                except Exception:
                    pass
        d.rounded_rectangle([0, 0, size, size], radius=14, fill=(17, 21, 27, 255))
        return img

    elif name == "status_online":
        # Glowing green status beacon
        d.ellipse([16, 16, 48, 48], fill=(34, 197, 94, 70))
        d.ellipse([22, 22, 42, 42], fill=EMERALD)
        d.ellipse([28, 28, 36, 36], fill=WHITE)

    elif name == "status_offline":
        # Muted gray status beacon
        d.ellipse([22, 22, 42, 42], fill=SLATE)

    elif name == "window":
        # Desktop app window with titlebar dots
        d.rounded_rectangle([6, 10, 58, 54], radius=8, outline=EMERALD, width=4)
        d.line([6, 22, 58, 22], fill=EMERALD, width=3)
        d.ellipse([14, 14, 18, 18], fill=EMERALD)
        d.ellipse([22, 14, 26, 18], fill=EMERALD)

    elif name == "copy":
        # Overlapping copy cards
        d.rounded_rectangle([18, 8, 54, 44], radius=6, outline=CYAN, width=4)
        d.rounded_rectangle([10, 18, 44, 56], radius=6, outline=WHITE, width=4)

    elif name == "chat":
        # Speech bubble
        d.rounded_rectangle([10, 14, 54, 44], radius=8, outline=CYAN, width=4)
        d.polygon([(18, 44), (18, 54), (28, 44)], fill=CYAN)

    elif name == "browser":
        # Web globe with equator and central meridian
        d.ellipse([8, 8, 56, 56], outline=CYAN, width=4)
        d.line([8, 32, 56, 32], fill=CYAN, width=3)
        d.ellipse([20, 8, 44, 56], outline=CYAN, width=3)

    elif name == "autostart_on":
        # Windows 4-tiles active with checkmark
        d.rounded_rectangle([8, 8, 28, 28], radius=4, outline=EMERALD, width=3, fill=(34, 197, 94, 60))
        d.rounded_rectangle([36, 8, 56, 28], radius=4, outline=EMERALD, width=3, fill=(34, 197, 94, 60))
        d.rounded_rectangle([8, 36, 28, 56], radius=4, outline=EMERALD, width=3, fill=(34, 197, 94, 60))
        d.rounded_rectangle([36, 36, 56, 56], radius=4, outline=EMERALD, width=3, fill=(34, 197, 94, 60))
        d.line([40, 46, 45, 51], fill=WHITE, width=4)
        d.line([45, 51, 54, 40], fill=WHITE, width=4)

    elif name == "autostart_off":
        # Windows 4-tiles muted outline
        d.rounded_rectangle([8, 8, 28, 28], radius=4, outline=SLATE, width=3)
        d.rounded_rectangle([36, 8, 56, 28], radius=4, outline=SLATE, width=3)
        d.rounded_rectangle([8, 36, 28, 56], radius=4, outline=SLATE, width=3)
        d.rounded_rectangle([36, 36, 56, 56], radius=4, outline=SLATE, width=3)

    elif name == "keepawake_on":
        # Active energy beacon / lightning sun
        d.ellipse([20, 20, 44, 44], outline=EMERALD, width=4, fill=(34, 197, 94, 80))
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            x1 = 32 + int(18 * math.cos(rad))
            y1 = 32 + int(18 * math.sin(rad))
            x2 = 32 + int(26 * math.cos(rad))
            y2 = 32 + int(26 * math.sin(rad))
            d.line([x1, y1, x2, y2], fill=EMERALD, width=3)

    elif name == "keepawake_off":
        # Sleep mode / muted moon
        d.ellipse([20, 20, 44, 44], outline=SLATE, width=3)

    elif name == "quit":
        # Power / Exit symbol in neon red
        d.arc([10, 10, 54, 54], start=310, end=230, fill=RED, width=5)
        d.line([32, 6, 32, 28], fill=RED, width=5)

    _icon_cache[name] = img
    return img


def _get_hbitmap_for_icon(name: str, target_size: int = 16) -> Optional[int]:
    """Converts PIL icon to Win32 32-bit PARGB HBITMAP for TrackPopupMenu with caching."""
    if sys.platform != "win32" or not HAS_PIL:
        return None

    cache_key = f"{name}_{target_size}"
    if cache_key in _hbitmap_cache:
        return _hbitmap_cache[cache_key]

    raw_img = _render_menu_icon(name)
    if not raw_img:
        return None

    try:
        import ctypes
        from ctypes import wintypes

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ('biSize', wintypes.DWORD),
                ('biWidth', wintypes.LONG),
                ('biHeight', wintypes.LONG),
                ('biPlanes', wintypes.WORD),
                ('biBitCount', wintypes.WORD),
                ('biCompression', wintypes.DWORD),
                ('biSizeImage', wintypes.DWORD),
                ('biXPelsPerMeter', wintypes.LONG),
                ('biYPelsPerMeter', wintypes.LONG),
                ('biClrUsed', wintypes.DWORD),
                ('biClrImportant', wintypes.DWORD),
            ]

        resized = raw_img.convert("RGBA").resize((target_size, target_size), Image.Resampling.LANCZOS)
        bih = BITMAPINFOHEADER()
        bih.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bih.biWidth = target_size
        bih.biHeight = -target_size  # top-down DIB
        bih.biPlanes = 1
        bih.biBitCount = 32
        bih.biCompression = 0

        ppvBits = ctypes.c_void_p()
        hbitmap = ctypes.windll.gdi32.CreateDIBSection(
            0, ctypes.byref(bih), 0, ctypes.byref(ppvBits), 0, 0
        )
        if hbitmap and ppvBits.value:
            raw = bytearray(resized.tobytes("raw", "BGRA"))
            for i in range(0, len(raw), 4):
                a = raw[i + 3]
                if a < 255:
                    raw[i] = (raw[i] * a) // 255
                    raw[i + 1] = (raw[i + 1] * a) // 255
                    raw[i + 2] = (raw[i + 2] * a) // 255
            ctypes.memmove(ppvBits.value, bytes(raw), len(raw))
            _hbitmap_cache[cache_key] = hbitmap
            return hbitmap
    except Exception:
        pass
    return None


def apply_pystray_dark_theme():
    """Enforces dark theme and item icons for pystray Win32 context menus."""
    if sys.platform != "win32" or not HAS_PYSTRAY:
        return

    try:
        from pystray import _win32 as w
        if hasattr(w, "_patched_dark_menu"):
            return
        w._patched_dark_menu = True

        orig_create_item = w.Icon._create_menu_item
        orig_on_notify = w.Icon._on_notify

        def patched_create_menu_item(self, descriptor, callbacks):
            info = orig_create_item(self, descriptor, callbacks)
            icon_key = getattr(descriptor, "icon_name", None) or getattr(descriptor, "_icon_name", None)
            if icon_key:
                hbmp = _get_hbitmap_for_icon(icon_key, 16)
                if hbmp:
                    info.fMask |= 0x00000080  # MIIM_BITMAP
                    info.hbmpItem = hbmp
            return info

        def patched_on_notify(self, wparam, lparam):
            if lparam == w.win32.WM_RBUTTONUP:
                try:
                    import ctypes
                    uxtheme = ctypes.windll.uxtheme
                    # 1. ForceDark for application menus
                    try:
                        uxtheme[135](2)
                        uxtheme[136]()
                    except Exception:
                        pass

                    # 2. Set dark theme on systray message windows
                    for target_h in (getattr(self, "_hwnd", None), getattr(self, "_menu_hwnd", None)):
                        if target_h:
                            try:
                                uxtheme[133](target_h, True)
                                uxtheme.SetWindowTheme(target_h, "DarkMode_Explorer", None)
                            except Exception:
                                pass
                except Exception:
                    pass
            return orig_on_notify(self, wparam, lparam)

        w.Icon._create_menu_item = patched_create_menu_item
        w.Icon._on_notify = patched_on_notify

        # Apply process-level preferred app mode immediately
        try:
            import ctypes
            ctypes.windll.uxtheme[135](2)
            ctypes.windll.uxtheme[136]()
        except Exception:
            pass

    except Exception:
        pass


class CustomMenuItem(pystray.MenuItem if HAS_PYSTRAY else object):
    """MenuItem subclass holding an icon_name tag for the dark theme painter."""
    def __init__(self, text, action, icon_name: Optional[str] = None, **kwargs):
        if HAS_PYSTRAY:
            super().__init__(text, action, **kwargs)
        self.icon_name = icon_name


def build_tray_menu(api, on_restore, on_exit):
    """
    Builds dynamic Meikova Harvest-style tray menu:
    - Header: Meikova Relay // v1.4.0 (Logo icon)
    - Status: Room ID & Online/Offline (Status beacon)
    - Separator
    - Mở Meikova Relay (Window icon)
    - Sao chép mã kết nối (Copy icon)
    - Mở Dashboard trên Web (Browser icon)
    - Separator
    - Khởi động cùng hệ thống: Bật / Tắt (Autostart icon)
    - Chế độ thức (Keep Awake): Bật / Tắt (Keepawake icon)
    - Separator
    - Thoát ứng dụng (Quit red icon)
    """
    apply_pystray_dark_theme()

    def get_menu_items():
        cfg = getattr(api, "_config", None) or getattr(api, "config", {})
        room_id = cfg.get("room_id", "RD-8888")
        is_running = getattr(api, "_is_running", False) or getattr(api, "is_running", False)

        from host_agent.gui_agent import is_autostart_enabled
        autostart_active = is_autostart_enabled()
        keepawake_active = bool(cfg.get("keep_awake", True))

        status_text = f"Phòng: {room_id} (Trực tuyến)" if is_running else f"Phòng: {room_id} (Dừng)"
        status_icon = "status_online" if is_running else "status_offline"

        def _do_toggle_autostart():
            new_state = not autostart_active
            if hasattr(api, "toggle_autostart"):
                api.toggle_autostart(new_state)
            elif hasattr(api, "_on_autostart_toggle"):
                api.autostart_var.set(new_state)
                api._on_autostart_toggle()
            _tray = getattr(api, "_tray_icon", None) or getattr(api, "tray_icon", None)
            if _tray:
                try:
                    _tray.update_menu()
                except Exception:
                    pass

        def _do_toggle_keepawake():
            new_state = not keepawake_active
            if hasattr(api, "toggle_keepawake"):
                api.toggle_keepawake(new_state)
            elif hasattr(api, "_on_keepawake_toggle"):
                api.keepawake_var.set(new_state)
                api._on_keepawake_toggle()
            _tray = getattr(api, "_tray_icon", None) or getattr(api, "tray_icon", None)
            if _tray:
                try:
                    _tray.update_menu()
                except Exception:
                    pass

        def _do_copy():
            if hasattr(api, "copy_share_info"):
                api.copy_share_info()
            elif hasattr(api, "_copy_share_info"):
                api._copy_share_info()

        def _do_open_web():
            relay = cfg.get("relay") or cfg.get("relay_url") or "wss://meikova-relay.onrender.com"
            http_url = relay.replace("wss://", "https://").replace("ws://", "http://")
            dashboard_url = f"{http_url}/dashboard"
            webbrowser.open(dashboard_url)

        def _do_open_chat():
            chat_win = getattr(api, "chat_window", None)
            if chat_win:
                chat_win.show()

        def _t(k):
            if hasattr(api, "t"):
                return api.t(k)
            return k

        header_ver = getattr(api, "app_version", None) or getattr(api, "APP_VERSION", None) or APP_VERSION
        return (
            # 1. App Title Header
            CustomMenuItem(f"Meikova Relay // v{header_ver}", lambda: None, icon_name="logo", enabled=False),
            # 2. Live telemetry status
            CustomMenuItem(status_text, lambda: None, icon_name=status_icon, enabled=False),
            pystray.Menu.SEPARATOR,
            # 3. Main actions
            CustomMenuItem(_t("tray_open"), on_restore, icon_name="window", default=True),
            CustomMenuItem("Mở cửa sổ Chat", _do_open_chat, icon_name="chat"),
            CustomMenuItem(_t("tray_copy"), _do_copy, icon_name="copy"),
            CustomMenuItem("Mở Dashboard trên Web", _do_open_web, icon_name="browser"),
            pystray.Menu.SEPARATOR,
            # 4. Settings toggles
            CustomMenuItem(
                f"Khởi động cùng hệ thống: {'Bật' if autostart_active else 'Tắt'}",
                _do_toggle_autostart,
                icon_name="autostart_on" if autostart_active else "autostart_off",
                checked=lambda item: autostart_active
            ),
            CustomMenuItem(
                f"Chế độ giữ máy luôn thức: {'Bật' if keepawake_active else 'Tắt'}",
                _do_toggle_keepawake,
                icon_name="keepawake_on" if keepawake_active else "keepawake_off",
                checked=lambda item: keepawake_active
            ),
            pystray.Menu.SEPARATOR,
            # 5. Quit
            CustomMenuItem(_t("tray_exit"), on_exit, icon_name="quit")
        )

    return pystray.Menu(get_menu_items)

import secrets

def generate_secure_room_id() -> str:
    """Generates a 9-digit segmented Room ID (RD-XXX-XXX-XXX) with high entropy."""
    p1 = secrets.randbelow(900) + 100
    p2 = secrets.randbelow(900) + 100
    p3 = secrets.randbelow(900) + 100
    return f"RD-{p1}-{p2}-{p3}"

def generate_secure_pin() -> str:
    """Generates a cryptographically strong 6-digit PIN using system entropy."""
    return f"{secrets.randbelow(900000) + 100000}"

try:
    from .auto_bootstrap import activate_vendor_paths as _activate_vendor_paths
    _activate_vendor_paths()
except Exception:
    try:
        from auto_bootstrap import activate_vendor_paths as _activate_vendor_paths
        _activate_vendor_paths()
    except Exception:
        pass
import os
import sys
import time
import json
try:
    import winreg
except ImportError:
    winreg = None
import threading
import asyncio
import socket
try:
    import tkinter as tk
    from tkinter import messagebox
except ImportError:
    class _TkStub:
        Tk = object
        Toplevel = object
        TclError = RuntimeError
    tk = _TkStub()
    messagebox = None
import random
import string
from pathlib import Path
from typing import Optional
import multiprocessing
multiprocessing.freeze_support()

APP_VERSION = "1.5.2"

# Ensure stdout/stderr exist and use UTF-8 on Windows
if sys.platform == "win32":
    try:
        if sys.stdout is None:
            sys.stdout = open(os.devnull, "w", encoding="utf-8", errors="replace")
        elif hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if sys.stderr is None:
            sys.stderr = open(os.devnull, "w", encoding="utf-8", errors="replace")
        elif hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_interactive_desktop_attached = False

# Ensure package is resolvable
current_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(current_dir.parent))

try:
    from host_agent.engines import create_platform_engine, get_active_os_engine
except ModuleNotFoundError:
    from engines import create_platform_engine, get_active_os_engine


def _get_engine_for_current_platform():
    """Returns OS engine matching current sys.platform (supports unit test sys.platform patching)."""
    eng = get_active_os_engine()
    plat = sys.platform.lower()
    if plat.startswith("win") and eng.platform_key != "win32":
        return create_platform_engine("win32")
    if (plat == "darwin" or plat.startswith("mac")) and eng.platform_key != "darwin":
        return create_platform_engine("darwin")
    if plat.startswith("linux") and eng.platform_key != "linux":
        return create_platform_engine("linux")
    return eng


def ensure_interactive_desktop() -> bool:
    """Attaches process and thread to interactive desktop via active OS Engine."""
    return _get_engine_for_current_platform().ensure_interactive_desktop()


def force_window_foreground(window, cached_hwnd: Optional[int] = None):
    """Restores, unhides, and raises GUI window to foreground cross-platform via OS Engine."""
    if not window:
        return
    _get_engine_for_current_platform().activate_window(window, cached_hwnd=cached_hwnd, title="Meikova Relay Host")


ensure_interactive_desktop()


def get_app_data_dir() -> Path:
    """Returns project-specific data directory for logs, config, and state via OS Engine."""
    return _get_engine_for_current_platform().get_app_data_dir()

try:
    from host_agent.host_service import HostService
    from host_agent.power_manager import PowerManager
    from host_agent.deployment_manager import (
        ensure_permanent_deployment,
        self_deploy_if_needed,
        cleanup_legacy_source_files,
        clean_legacy_registry_keys,
        register_protocol_handler,
        register_firewall_rule,
        setup_task_scheduler_autostart,
        is_task_scheduler_autostart_enabled,
        manage_windows_service,
        is_windows_service_installed,
        install_user_tier,
        uninstall_user_tier,
        install_admin_tier,
        uninstall_admin_tier,
        get_deployment_status,
        is_current_user_admin,
    )
    from host_agent.auto_updater import (
        cleanup_post_update,
        check_for_updates,
        apply_update,
        check_and_apply_update,
        start_auto_update_loop,
    )
except ModuleNotFoundError:
    from host_service import HostService
    from power_manager import PowerManager
    from deployment_manager import (
        ensure_permanent_deployment,
        self_deploy_if_needed,
        cleanup_legacy_source_files,
        clean_legacy_registry_keys,
        register_protocol_handler,
        register_firewall_rule,
        setup_task_scheduler_autostart,
        is_task_scheduler_autostart_enabled,
        manage_windows_service,
        is_windows_service_installed,
        install_user_tier,
        uninstall_user_tier,
        install_admin_tier,
        uninstall_admin_tier,
        get_deployment_status,
        is_current_user_admin,
    )
    from auto_updater import (
        cleanup_post_update,
        check_for_updates,
        apply_update,
        check_and_apply_update,
        start_auto_update_loop,
    )

try:
    from host_agent.chat_window import HostChatWindow
except ModuleNotFoundError:
    try:
        from chat_window import HostChatWindow
    except ModuleNotFoundError:
        HostChatWindow = None

# Optional System Tray Support via pystray & PIL
try:
    import pystray
    from PIL import Image, ImageDraw
    HAS_TRAY = True
    try:
        with open(get_app_data_dir() / "tray.log", "w", encoding="utf-8") as f:
            f.write(f"HAS_TRAY SUCCESS: {pystray}\n")
    except Exception:
        pass
except Exception as e:
    HAS_TRAY = False
    try:
        with open(get_app_data_dir() / "tray.log", "w", encoding="utf-8") as f:
            import traceback
            f.write(f"HAS_TRAY FAILED: {e}\n")
            traceback.print_exc(file=f)
    except Exception:
        pass

try:
    from host_agent.tray_menu import build_tray_menu, show_custom_tk_tray_popup
except ModuleNotFoundError:
    try:
        from tray_menu import build_tray_menu, show_custom_tk_tray_popup
    except Exception:
        build_tray_menu = None
        show_custom_tk_tray_popup = None

# Optional Microsoft Edge WebView2 GUI Support via pywebview
try:
    import webview
    HAS_WEBVIEW = True
except Exception:
    HAS_WEBVIEW = False

def get_tray_icon_image():
    """Returns unified brand icon:
    Meikova Relay Duplex Bridge (#83E8AC on #11151B squircle).
    """
    if not HAS_TRAY:
        return None
    try:
        base_dirs = [
            current_dir,
            current_dir / "tray_icons",
            Path(__file__).resolve().parent,
            Path(__file__).resolve().parent / "tray_icons",
            Path(getattr(sys, "_MEIPASS", current_dir)),
            Path(getattr(sys, "_MEIPASS", current_dir)) / "host_agent",
            Path(getattr(sys, "_MEIPASS", current_dir)) / "host_agent" / "tray_icons",
            get_app_data_dir(),
        ]
        for b in base_dirs:
            for fname in ("tray_icon.png", "logo.png", "icon.png"):
                candidate = b / fname
                if candidate.is_file():
                    with Image.open(candidate) as im:
                        if im.size == (32, 32):
                            return im.copy()
                        return im.resize((32, 32), Image.Resampling.LANCZOS)
    except Exception:
        pass


    # Direct embedded rendering of Duplex Bridge so it NEVER depends on files or imports
    try:
        size = 32
        scale = size / 100.0
        ss = 4
        canvas_size = size * ss
        img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        rx = int(22 * scale * ss)
        d.rounded_rectangle((0, 0, canvas_size, canvas_size), radius=rx, fill="#11151B")
        def t(pt):
            return ((7.0 + 0.86 * pt[0]) * scale * ss, (7.0 + 0.86 * pt[1]) * scale * ss)
        p1 = [(12, 29), (45, 29), (57, 41), (45, 53), (30, 53), (30, 41), (40, 41), (43, 38), (24, 38), (24, 62), (40, 62), (40, 74), (12, 74)]
        p2 = [(88, 71), (55, 71), (43, 59), (55, 47), (70, 47), (70, 59), (60, 59), (57, 62), (76, 62), (76, 38), (60, 38), (60, 26), (88, 26)]
        d.polygon([t(pt) for pt in p1], fill="#83E8AC")
        d.polygon([t(pt) for pt in p2], fill="#83E8AC")
        return img.resize((size, size), Image.Resampling.LANCZOS)
    except Exception:
        pass

    fallback = Image.new("RGBA", (32, 32), (17, 21, 27, 255))
    d = ImageDraw.Draw(fallback)
    d.rounded_rectangle([0, 0, 32, 32], radius=7, fill="#11151B")
    return fallback

def safely_remove_tray_icon(tray_icon):
    """Synchronously unregisters and deletes notification area icon from Windows Explorer with 0 latency."""
    if not tray_icon:
        return
    try:
        if hasattr(tray_icon, "_hide"):
            tray_icon._hide()
    except Exception:
        pass
    try:
        tray_icon.visible = False
    except Exception:
        pass
    try:
        tray_icon.stop()
    except Exception:
        pass

REG_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_REG_NAME = "MeikovaRelayHost"

# Studio-grade dark ambient color tokens (/ambient-instrument-ui)
COLORS = {
    "bg_main": "#111315",         # v1.4.0 Deep ambient ink-0
    "bg_panel": "#16181A",        # v1.4.0 Surface ink-1
    "bg_card": "#1D2024",         # v1.4.0 Card ink-2
    "bg_card_inner": "#0D0E10",   # v1.4.0 Inner input chamber
    "line": "#282B30",            # v1.4.0 Hairline border
    "line_hover": "#3D424A",      # v1.4.0 Focused border
    "text_main": "#F4F6F8",       # v1.4.0 High contrast white
    "text_muted": "#7D8590",      # v1.4.0 Studio muted gray
    "text_sub": "#A0AAB4",        # v1.4.0 Monospace/secondary label
    "accent_green": "#83E8AC",    # v1.4.0 Meikova Emerald
    "accent_green_bg": "#15291E", # v1.4.0 Dark emerald chip
    "accent_green_line": "#285B3E", # v1.4.0 Emerald border
    "accent_cyan": "#83E8AC",     # v1.4.0 Unified emerald/cyan telemetry
    "accent_cyan_bg": "#15291E",  # v1.4.0 Dark emerald chip
    "accent_red": "#FF5E6C",      # v1.4.0 Crimson alert/stop
    "accent_red_bg": "#2B1418",   # v1.4.0 Dark crimson chip
    "accent_amber": "#F6B851",    # v1.4.0 Amber warning
    "accent_amber_bg": "#2A2010", # v1.4.0 Dark amber chip
    "btn_surface": "#23272D",     # v1.4.0 Pill button surface
    "btn_surface_hover": "#2E333B"# v1.4.0 Pill button hover
}

# Master bilingual translation dictionary (VI / EN)
# ponytail: Clean stdlib dictionary; zero external dependencies.
TRANSLATIONS = {
    "vi": {
        "app_title": "Meikova Relay Host - Điều Khiển Máy Trạm",
        "header_title": "MEIKOVA RELAY HOST",
        "workstation_fmt": "MÁY TRẠM: {name} // 120 FPS // TRUY CẬP KÉP",
        "status_stopped": "● ĐÃ DỪNG",
        "status_running": "● ĐANG CHẠY",
        "status_ready": "● SẴN SÀNG KẾT NỐI",
        "status_reconnecting": "● ĐANG KẾT NỐI LẠI...",
        "status_connected": "● ĐANG CÓ KẾT NỐI",
        "tab_ultra": "HỖ TRỢ TỨC THÌ",
        "tab_chrome": "QUẢN TRỊ 24/7",
        "tab_settings": "CẤU HÌNH",
        "btn_start_service": "● BẬT DỊCH VỤ",
        "btn_stop_service": "■ DỪNG DỊCH VỤ",
        "ultra_title": "CHẾ ĐỘ HỖ TRỢ TỨC THÌ",
        "ultra_desc": "Cung cấp Mã Phòng và PIN bên dưới cho người hỗ trợ.",
        "room_id_label": "MÃ PHÒNG // ROOM ID",
        "pin_label": "MẬT KHẨU PHIÊN // ACCESS PIN",
        "btn_renew_room": "ĐỔI MÃ",
        "btn_copy_room": "CHÉP MÃ",
        "btn_renew_pin": "ĐỔI PIN",
        "btn_copy_pin": "CHÉP PIN",
        "btn_share_info": "SAO CHÉP THÔNG TIN KẾT NỐI",
        "session_waiting": "● Đang chờ kết nối từ máy chủ...",
        "session_active": "● ĐANG ĐƯỢC ĐIỀU KHIỂN BỞI: {client}",
        "session_stopped": "● Dịch vụ đang tắt",
        "btn_disconnect": "NGẮT PHIÊN",
        "chrome_title": "Truy cập không giám sát 24/7 (Unattended Access)",
        "chrome_desc": "Liên kết máy tính vào tài khoản của bạn để truy cập từ xa mọi lúc mà không cần người ngồi tại máy chấp nhận.",
        "account_label": "Tài khoản chủ sở hữu (Email / Username Web):",
        "account_ph": "admin / user@domain.com",
        "device_name_label": "Tên máy trạm hiển thị (Device Fleet Name):",
        "device_name_ph": "PC-KeToan-01",
        "perm_pin_label": "Mật khẩu truy cập cố định (Permanent Security PIN):",
        "autostart_label": "Tự động khởi động cùng Windows (Run on boot)",
        "keepawake_label": "Chặn máy tính tự ngủ / tắt màn hình (Anti-Sleep / Keep-Awake)",
        "btn_minimize_tray": "THU NHỎ XUỐNG KHAY HỆ THỐNG (CHẠY NGẦM)",
        "relay_label": "Relay Server WebSocket URL:",
        "relay_ph": "ws://localhost:8080",
        "btn_save_settings": "LƯU CẤU HÌNH",
        "log_title": "Nhật ký hoạt động thời gian thực (Activity Log):",
        "close_to_tray_label": "Thu nhỏ xuống khay hệ thống khi bấm nút đóng [X]",
        "stealth_label": "Chế độ Tàng hình (Ẩn khay hệ thống & chạy ngầm)",
        "admin_lever_label": "Cần gạt Quản trị viên (Admin Mode: Khóa vật lý / Màn hình riêng tư)",
        "tray_status_online": "Phòng: {room_id} (Trực tuyến)",
        "tray_status_offline": "Phòng: {room_id} (Dừng)",
        "tray_chat": "Mở cửa sổ Chat",
        "tray_web": "Mở Dashboard trên Web",
        "tray_autostart_fmt": "Khởi động cùng hệ thống: {state}",
        "tray_keepawake_fmt": "Chế độ giữ máy luôn thức: {state}",
        "state_on": "Bật",
        "state_off": "Tắt",
        "tray_open": "Mở Meikova Relay",
        "tray_copy": "Sao chép mã kết nối",
        "tray_exit": "Thoát",
        "log_service_started": "Khởi động dịch vụ thành công! Room ID: {room_id}",
        "log_service_stopped": "Dịch vụ đã dừng.",
        "log_room_registered": "Đã đăng ký phòng {room_id} trên Relay Server.",
        "log_reconnecting": "Mất kết nối với Relay Server. Đang tự động kết nối lại...",
        "log_new_connection": "Kết nối mới: {client}",
        "log_disconnected": "Phiên điều khiển đã kết thúc. Máy trạm trở về trạng thái sẵn sàng.",
        "log_emergency_disconnect": "Chủ máy trạm đã nhấn ngắt kết nối khẩn cấp.",
        "log_new_room": "Đã tạo Room ID mới: {room_id}",
        "log_restart_req": "Vui lòng khởi động lại dịch vụ để áp dụng mã phòng mới.",
        "log_new_pin": "Đã tạo PIN mới: {pin}",
        "log_copied": "Đã sao chép {name}: {text}",
        "log_copied_all": "Đã sao chép đầy đủ thông tin kết nối! Dán tin nhắn gửi cho người hỗ trợ.",
        "log_saved_relay": "Đã lưu cấu hình Relay Server thành công.",
        "log_autostart_on": "Đã bật tự khởi động cùng Windows (Run on boot)",
        "log_autostart_off": "Đã tắt tự khởi động cùng Windows",
        "log_keepawake": "Chống tắt màn hình / Sleep: {state}",
        "log_minimized": "Đã thu nhỏ ứng dụng vào khay hệ thống (System Tray).",
        "share_header": "--- MEIKOVA RELAY // KẾT NỐI HỖ TRỢ TỪ XA ---",
        "share_dashboard": "Trang điều khiển:",
        "share_room": "Mã phòng (Room ID):",
        "share_pin": "Mật khẩu (PIN):",
    },
    "en": {
        "app_title": "Meikova Relay Host - Workstation Control",
        "header_title": "MEIKOVA RELAY HOST",
        "workstation_fmt": "WORKSTATION: {name} // 120 FPS // DUAL-MODE ACCESS",
        "status_stopped": "● STOPPED",
        "status_running": "● RUNNING",
        "status_ready": "● READY TO CONNECT",
        "status_reconnecting": "● RECONNECTING...",
        "status_connected": "● ACTIVE SESSION",
        "tab_ultra": "INSTANT ASSIST",
        "tab_chrome": "24/7 UNATTENDED",
        "tab_settings": "SETTINGS",
        "btn_start_service": "● START SERVICE",
        "btn_stop_service": "■ STOP SERVICE",
        "ultra_title": "ON-DEMAND REMOTE ASSIST",
        "ultra_desc": "Provide Room ID and PIN below to the remote technician.",
        "room_id_label": "ROOM ID",
        "pin_label": "ACCESS PIN",
        "btn_renew_room": "RENEW",
        "btn_copy_room": "COPY",
        "btn_renew_pin": "RENEW PIN",
        "btn_copy_pin": "COPY PIN",
        "btn_share_info": "COPY CONNECTION INFO",
        "session_waiting": "● Waiting for server connection...",
        "session_active": "● CONTROLLED BY: {client}",
        "session_stopped": "● Service is stopped",
        "btn_disconnect": "DISCONNECT",
        "chrome_title": "24/7 Unattended Remote Access",
        "chrome_desc": "Link this workstation to your account for anytime remote access without physical confirmation.",
        "account_label": "Owner Account (Email / Username):",
        "account_ph": "admin / user@domain.com",
        "device_name_label": "Workstation Device Name (Fleet Name):",
        "device_name_ph": "PC-Accounting-01",
        "perm_pin_label": "Permanent Security PIN:",
        "autostart_label": "Start automatically with Windows (Run on boot)",
        "keepawake_label": "Prevent sleep & screen shutoff (Anti-Sleep / Keep-Awake)",
        "btn_minimize_tray": "MINIMIZE TO SYSTEM TRAY (BACKGROUND)",
        "relay_label": "Relay Server WebSocket URL:",
        "relay_ph": "ws://localhost:8080",
        "btn_save_settings": "SAVE SETTINGS",
        "log_title": "Real-time Activity Log:",
        "close_to_tray_label": "Minimize to system tray when clicking close [X]",
        "stealth_label": "Stealth Mode (Hide tray icon & run in background)",
        "admin_lever_label": "Administrator Lever (Admin Mode: Block Input / Privacy Curtain)",
        "tray_status_online": "Room: {room_id} (Online)",
        "tray_status_offline": "Room: {room_id} (Stopped)",
        "tray_chat": "Open Chat Window",
        "tray_web": "Open Web Dashboard",
        "tray_autostart_fmt": "Run on system boot: {state}",
        "tray_keepawake_fmt": "Keep workstation awake: {state}",
        "state_on": "ON",
        "state_off": "OFF",
        "tray_open": "Open Meikova Relay",
        "tray_copy": "Copy Connection Info",
        "tray_exit": "Exit",
        "log_service_started": "Service started successfully! Room ID: {room_id}",
        "log_service_stopped": "Service stopped.",
        "log_room_registered": "Room {room_id} registered on Relay Server.",
        "log_reconnecting": "Relay Server disconnected. Reconnecting automatically...",
        "log_new_connection": "New connection: {client}",
        "log_disconnected": "Session ended. Workstation returned to ready state.",
        "log_emergency_disconnect": "Host owner triggered emergency disconnect.",
        "log_new_room": "Generated new Room ID: {room_id}",
        "log_restart_req": "Please restart service to apply new room ID.",
        "log_new_pin": "Generated new PIN: {pin}",
        "log_copied": "Copied {name}: {text}",
        "log_copied_all": "Connection info copied! Paste to send to support technician.",
        "log_saved_relay": "Relay Server configuration saved successfully.",
        "log_autostart_on": "Enabled Windows run on boot",
        "log_autostart_off": "Disabled Windows run on boot",
        "log_keepawake": "Anti-Sleep / Screen keep awake: {state}",
        "log_minimized": "Application minimized to system tray.",
        "share_header": "--- MEIKOVA RELAY // REMOTE ASSIST CONNECTION ---",
        "share_dashboard": "Control Portal:",
        "share_room": "Room ID:",
        "share_pin": "Password (PIN):",
    }
}

def resolve_config_path() -> Path:
    candidates = []
    # 1. Executable directory (for installed standalone .exe)
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.append(exe_dir / "config.json")

    # 2. Project AppData directory (SSOT)
    candidates.append(get_app_data_dir() / "config.json")

    # 3. Current Working Directory
    candidates.append(Path.cwd() / "config.json")

    # 4. Script directory (for python gui_agent.py)
    candidates.append(Path(__file__).resolve().parent / "config.json")

    # 5. Legacy migration paths (read-only fallbacks)
    candidates.append(Path.home() / ".meikova-relay" / "config.json")
    candidates.append(Path.home() / ".meikova_relay_config.json")

    for c in candidates:
        if c.exists() and c.is_file():
            return c

    # Default location for writing if none exists
    target = get_app_data_dir() / "config.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    return target

class MeikovaRelayHostGUI:
    def __init__(self, root: tk.Tk):
        import queue
        self.root = root
        self.app_version = APP_VERSION
        self._os_engine = _get_engine_for_current_platform()
        fonts = self._os_engine.get_ui_fonts()
        self.f_sans = fonts.get("sans", "Segoe UI")
        self.f_mono = fonts.get("mono", "Consolas")

        self.root.geometry("560x740")
        self.root.minsize(500, 660)
        self.root.configure(bg=COLORS["bg_main"])

        self._ui_queue: "queue.Queue" = queue.Queue()
        self.service_thread: Optional[threading.Thread] = None
        self.host_service: Optional[HostService] = None
        self.is_running = False
        self._is_running = False
        self.current_tab = "ultra"  # "ultra" | "chrome" | "settings"
        self.connected_client_info: Optional[str] = None
        self.tray_icon = None
        self._tray_icon = None
        self.chat_window: Optional[HostChatWindow] = None
        if HostChatWindow:
            try:
                self.chat_window = HostChatWindow(
                    on_send_reply=lambda text: self.host_service.send_chat_message(text) if self.host_service else None,
                    parent=self.root
                )
            except Exception:
                self.chat_window = None

        try:
            import ctypes
            if hasattr(ctypes, "windll") and hasattr(ctypes.windll, "shell32"):
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("MeikovaRelay.WorkstationHost.2.0")
        except Exception:
            pass

        self._load_config()
        self._config = self.config
        self.root.title(self.t("app_title"))
        self._setup_window_icon()
        self._build_ui()
        self._check_autostart_status()
        self._init_system_tray()
        self._os_engine.apply_window_theme(self.root)

        self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)
        self._schedule_ui_poll()

    def _enqueue_ui_action(self, fn):
        """Thread-safe UI action queue so Linux/macOS/Windows tray and service threads always wake up Tk."""
        if callable(fn):
            self._ui_queue.put(fn)
            try:
                self.root.after_idle(self._drain_ui_queue)
            except Exception:
                pass

    def _drain_ui_queue(self):
        import queue
        while True:
            try:
                fn = self._ui_queue.get_nowait()
            except queue.Empty:
                break
            try:
                fn()
            except Exception:
                pass

    def _schedule_ui_poll(self):
        self._drain_ui_queue()
        try:
            if hasattr(self.root, "winfo_exists") and self.root.winfo_exists():
                self.root.after(80, self._schedule_ui_poll)
        except Exception:
            pass

    def _setup_window_icon(self):
        base_dirs = [
            current_dir,
            Path(__file__).resolve().parent,
            Path(getattr(sys, "_MEIPASS", current_dir)),
            Path(getattr(sys, "_MEIPASS", current_dir)) / "host_agent"
        ]
        ico_path = None
        png_path = None
        for d in base_dirs:
            if (d / "icon.ico").exists() and not ico_path:
                ico_path = d / "icon.ico"
            if (d / "icon.png").exists() and not png_path:
                png_path = d / "icon.png"

        if png_path:
            try:
                from PIL import Image, ImageTk
                with Image.open(png_path) as im:
                    self._app_icon_img = ImageTk.PhotoImage(im)
                    self.root.iconphoto(True, self._app_icon_img)
            except Exception:
                pass

        if ico_path and sys.platform == "win32":
            try:
                self.root.iconbitmap(str(ico_path))
            except Exception:
                pass

    def t(self, key: str, **kwargs) -> str:
        lang_dict = TRANSLATIONS.get(self.lang, TRANSLATIONS["vi"])
        tmpl = lang_dict.get(key, TRANSLATIONS["vi"].get(key, key))
        if kwargs:
            return tmpl.format(**kwargs)
        return tmpl

    def _set_language(self, lang: str):
        if self.lang == lang:
            return
        self.lang = lang
        self.config["lang"] = lang
        self._save_config()
        self._apply_language()
        self._log(f"Switched language to {'Tiếng Việt' if lang == 'vi' else 'English'}")

    def _get_config_path(self):
        return resolve_config_path()

    def _load_config(self):
        default_comp = os.environ.get("COMPUTERNAME") or socket.gethostname() or "Workstation"
        self.config = {
            "relay": "wss://meikova-relay.onrender.com",
            "account": "",
            "device_name": default_comp,
            "room_id": generate_secure_room_id(),
            "pin": generate_secure_pin(),
            "keep_awake": True,
            "open_on_boot": False,
            "close_to_tray": True,
            "show_tray_icon": True,
            "stealth_mode": False,
            "admin_elevated": False,
            "auto_wakeup": False,
            "auto_wakeup_time": "08:00",
            "block_input": False,
            "privacy_curtain": False,
            "start_minimized": False,
            "lang": "vi"
        }
        cfg_file = self._get_config_path()
        if cfg_file.exists():
            try:
                with open(cfg_file, "r", encoding="utf-8") as f:
                    self.config.update(json.load(f))
            except Exception:
                pass
        self.lang = self.config.get("lang", "vi")
        if self.lang not in ("vi", "en"):
            self.lang = "vi"

    def _save_config(self):
        self.config["lang"] = self.lang
        cfg_file = self._get_config_path()
        try:
            with open(cfg_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
        except Exception:
            pass

    # -------------------------------------------------------------
    # UI CONSTRUCTION (v1.4.0 Ambient Dark Instrument UI)
    # -------------------------------------------------------------
    def _build_ui(self):
        # 1. Top Brand Bar + Version Badge + Quick Chat Button (matches v1.4.0 image_2d8f88.png)
        top_bar = tk.Frame(self.root, bg=COLORS["bg_panel"], pady=10, padx=18, highlightthickness=1, highlightbackground=COLORS["line"])
        top_bar.pack(fill="x")

        brand_left = tk.Frame(top_bar, bg=COLORS["bg_panel"])
        brand_left.pack(side="left")

        logo_badge = tk.Label(
            brand_left,
            text="∞",
            font=(self.f_sans, 11, "bold"),
            fg=COLORS["accent_green"],
            bg=COLORS["bg_card"],
            padx=6,
            pady=1,
            highlightthickness=1,
            highlightbackground=COLORS["line"]
        )
        logo_badge.pack(side="left", padx=(0, 8))

        self.lbl_header_title = tk.Label(
            brand_left,
            text=self.t("header_title"),
            font=(self.f_sans, 10, "bold"),
            fg=COLORS["text_main"],
            bg=COLORS["bg_panel"]
        )
        self.lbl_header_title.pack(side="left")

        self.lbl_version_badge = tk.Label(
            brand_left,
            text=f"v{APP_VERSION}",
            font=(self.f_mono, 8, "bold"),
            fg=COLORS["accent_green"],
            bg=COLORS["accent_green_bg"],
            padx=6,
            pady=1,
            highlightthickness=1,
            highlightbackground=COLORS["accent_green_line"]
        )
        self.lbl_version_badge.pack(side="left", padx=(8, 0))

        self.btn_header_chat = tk.Button(
            top_bar,
            text="Chat",
            font=(self.f_sans, 8, "bold"),
            bg=COLORS["bg_card"],
            fg=COLORS["text_sub"],
            activebackground=COLORS["btn_surface_hover"],
            activeforeground=COLORS["accent_green"],
            relief="flat",
            bd=0,
            padx=10,
            pady=3,
            cursor="hand2",
            command=lambda: self.chat_window.show() if self.chat_window else None
        )
        self.btn_header_chat.pack(side="right")

        # 2. Telemetry & Status Sub-Header Bar
        header = tk.Frame(self.root, bg=COLORS["bg_main"], pady=10, padx=18)
        header.pack(fill="x")

        comp_name = self.config.get("device_name") or os.environ.get("COMPUTERNAME") or socket.gethostname() or "Workstation"
        self.lbl_header_subtitle = tk.Label(
            header,
            text=self.t("workstation_fmt", name=comp_name),
            font=(self.f_mono, 8),
            fg=COLORS["text_muted"],
            bg=COLORS["bg_main"]
        )
        self.lbl_header_subtitle.pack(side="left")

        right_header = tk.Frame(header, bg=COLORS["bg_main"])
        right_header.pack(side="right")

        self.status_pill = tk.Label(
            right_header,
            text=self.t("status_stopped"),
            font=(self.f_sans, 8, "bold"),
            fg=COLORS["accent_red"],
            bg=COLORS["accent_red_bg"],
            padx=10,
            pady=3,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=COLORS["line"]
        )
        self.status_pill.pack(side="right", padx=(8, 0))

        lang_box = tk.Frame(right_header, bg=COLORS["bg_card"], padx=2, pady=2, highlightthickness=1, highlightbackground=COLORS["line"])
        lang_box.pack(side="right")

        self.btn_lang_vi = tk.Button(
            lang_box,
            text="VI",
            font=(self.f_sans, 7, "bold"),
            bg=COLORS["accent_green"] if self.lang == "vi" else COLORS["bg_card"],
            fg=COLORS["bg_main"] if self.lang == "vi" else COLORS["text_muted"],
            activebackground=COLORS["accent_green"],
            activeforeground=COLORS["bg_main"],
            relief="flat",
            bd=0,
            padx=7,
            pady=2,
            cursor="hand2",
            command=lambda: self._set_language("vi")
        )
        self.btn_lang_vi.pack(side="left")

        self.btn_lang_en = tk.Button(
            lang_box,
            text="EN",
            font=(self.f_sans, 7, "bold"),
            bg=COLORS["accent_green"] if self.lang == "en" else COLORS["bg_card"],
            fg=COLORS["bg_main"] if self.lang == "en" else COLORS["text_muted"],
            activebackground=COLORS["accent_green"],
            activeforeground=COLORS["bg_main"],
            relief="flat",
            bd=0,
            padx=7,
            pady=2,
            cursor="hand2",
            command=lambda: self._set_language("en")
        )
        self.btn_lang_en.pack(side="left")

        # 3. Segmented Mode Switcher (Pill tabs)
        seg_container = tk.Frame(self.root, bg=COLORS["bg_main"], padx=18)
        seg_container.pack(fill="x", pady=(0, 8))

        seg_frame = tk.Frame(seg_container, bg=COLORS["bg_panel"], padx=3, pady=3, highlightthickness=1, highlightbackground=COLORS["line"])
        seg_frame.pack(fill="x")

        self.btn_tab_ultra = tk.Button(
            seg_frame,
            text=self.t("tab_ultra"),
            font=(self.f_sans, 8, "bold"),
            bg=COLORS["accent_green"],
            fg=COLORS["bg_main"],
            activebackground="#6AD696",
            activeforeground=COLORS["bg_main"],
            relief="flat",
            padx=12,
            pady=6,
            bd=0,
            cursor="hand2",
            command=lambda: self._switch_tab("ultra")
        )
        self.btn_tab_ultra.pack(side="left", expand=True, fill="x", padx=2)

        self.btn_tab_chrome = tk.Button(
            seg_frame,
            text=self.t("tab_chrome"),
            font=(self.f_sans, 8, "bold"),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_sub"],
            activebackground=COLORS["btn_surface"],
            activeforeground=COLORS["text_main"],
            relief="flat",
            padx=12,
            pady=6,
            bd=0,
            cursor="hand2",
            command=lambda: self._switch_tab("chrome")
        )
        self.btn_tab_chrome.pack(side="left", expand=True, fill="x", padx=2)

        self.btn_tab_cfg = tk.Button(
            seg_frame,
            text=self.t("tab_settings"),
            font=(self.f_sans, 8, "bold"),
            bg=COLORS["bg_panel"],
            fg=COLORS["text_sub"],
            activebackground=COLORS["btn_surface"],
            activeforeground=COLORS["text_main"],
            relief="flat",
            padx=12,
            pady=6,
            bd=0,
            cursor="hand2",
            command=lambda: self._switch_tab("settings")
        )
        self.btn_tab_cfg.pack(side="left", expand=True, fill="x", padx=2)

        # 4. Main Content Container
        self.content_container = tk.Frame(self.root, bg=COLORS["bg_main"], padx=18)
        self.content_container.pack(fill="both", expand=True)

        self.panel_ultra = tk.Frame(self.content_container, bg=COLORS["bg_panel"], padx=16, pady=14, highlightthickness=1, highlightbackground=COLORS["line"])
        self.panel_chrome = tk.Frame(self.content_container, bg=COLORS["bg_panel"], padx=16, pady=14, highlightthickness=1, highlightbackground=COLORS["line"])
        self.panel_settings = tk.Frame(self.content_container, bg=COLORS["bg_panel"], padx=16, pady=12, highlightthickness=1, highlightbackground=COLORS["line"])

        self._build_ultra_panel()
        self._build_chrome_panel()
        self._build_settings_panel()

        self._switch_tab("ultra")

        # 5. Persistent Activity Log Dock + Master Control Strip (Bottom, visible across all tabs like v1.4.0)
        bottom_dock = tk.Frame(self.root, bg=COLORS["bg_main"], pady=10, padx=18)
        bottom_dock.pack(fill="x", side="bottom")

        log_card = tk.Frame(bottom_dock, bg=COLORS["bg_panel"], padx=12, pady=8, highlightthickness=1, highlightbackground=COLORS["line"])
        log_card.pack(fill="x", pady=(0, 8))

        self.lbl_log_title = tk.Label(
            log_card,
            text=self.t("log_title"),
            font=(self.f_mono, 8, "bold"),
            fg=COLORS["text_muted"],
            bg=COLORS["bg_panel"]
        )
        self.lbl_log_title.pack(anchor="w", pady=(0, 4))

        self.log_text = tk.Text(
            log_card,
            bg=COLORS["bg_card_inner"],
            fg=COLORS["text_sub"],
            insertbackground=COLORS["accent_green"],
            font=(self.f_mono, 8),
            relief="flat",
            height=4,
            wrap="word",
            state="disabled",
            highlightthickness=1,
            highlightbackground=COLORS["line"]
        )
        self.log_text.pack(fill="x")

        self.btn_master_toggle = tk.Button(
            bottom_dock,
            text=self.t("btn_start_service"),
            font=(self.f_sans, 10, "bold"),
            bg=COLORS["accent_green"],
            fg=COLORS["bg_main"],
            activebackground="#6AD696",
            activeforeground=COLORS["bg_main"],
            relief="flat",
            bd=0,
            pady=10,
            cursor="hand2",
            command=self._toggle_service
        )
        self.btn_master_toggle.pack(fill="x")

    # -------------------------------------------------------------
    # PANEL 1: ON-DEMAND REMOTE ASSIST (ROOM ID)
    # -------------------------------------------------------------
    def _build_ultra_panel(self):
        self.lbl_ultra_title = tk.Label(
            self.panel_ultra,
            text=self.t("ultra_title"),
            font=(self.f_sans, 10, "bold"),
            fg=COLORS["text_main"],
            bg=COLORS["bg_panel"]
        )
        self.lbl_ultra_title.pack(anchor="w")

        self.lbl_ultra_desc = tk.Label(
            self.panel_ultra,
            text=self.t("ultra_desc"),
            font=(self.f_sans, 8),
            fg=COLORS["text_muted"],
            bg=COLORS["bg_panel"]
        )
        self.lbl_ultra_desc.pack(anchor="w", pady=(2, 10))

        # ID Card
        id_card = tk.Frame(self.panel_ultra, bg=COLORS["bg_card"], padx=14, pady=10, highlightthickness=1, highlightbackground=COLORS["line"])
        id_card.pack(fill="x", pady=4)

        self.lbl_room_tag = tk.Label(id_card, text=self.t("room_id_label"), font=(self.f_mono, 8, "bold"), fg=COLORS["text_sub"], bg=COLORS["bg_card"])
        self.lbl_room_tag.pack(anchor="w")

        id_row = tk.Frame(id_card, bg=COLORS["bg_card"])
        id_row.pack(fill="x", pady=(4, 0))

        self.room_var = tk.StringVar(master=self.root, value=self.config.get("room_id", "RD-8888"))
        self.lbl_room_display = tk.Label(
            id_row,
            textvariable=self.room_var,
            font=(self.f_mono, 18, "bold"),
            fg=COLORS["text_main"],
            bg=COLORS["bg_card"]
        )
        self.lbl_room_display.pack(side="left")

        btn_box1 = tk.Frame(id_row, bg=COLORS["bg_card"])
        btn_box1.pack(side="right")

        self.btn_renew_room = tk.Button(
            btn_box1,
            text=self.t("btn_renew_room"),
            font=(self.f_sans, 8, "bold"),
            bg=COLORS["btn_surface"],
            fg=COLORS["text_sub"],
            activebackground=COLORS["btn_surface_hover"],
            activeforeground=COLORS["text_main"],
            relief="flat",
            bd=0,
            padx=10,
            pady=4,
            cursor="hand2",
            command=self._generate_random_room
        )
        self.btn_renew_room.pack(side="right", padx=(5, 0))

        self.btn_copy_room = tk.Button(
            btn_box1,
            text=self.t("btn_copy_room"),
            font=(self.f_sans, 8, "bold"),
            bg=COLORS["btn_surface"],
            fg=COLORS["text_main"],
            activebackground=COLORS["btn_surface_hover"],
            activeforeground=COLORS["accent_green"],
            relief="flat",
            bd=0,
            padx=12,
            pady=4,
            cursor="hand2",
            command=lambda: self._copy_to_clip(self.room_var.get().strip(), "Room ID")
        )
        self.btn_copy_room.pack(side="right")

        # PIN Card
        pin_card = tk.Frame(self.panel_ultra, bg=COLORS["bg_card"], padx=14, pady=10, highlightthickness=1, highlightbackground=COLORS["line"])
        pin_card.pack(fill="x", pady=4)

        self.lbl_pin_tag = tk.Label(pin_card, text=self.t("pin_label"), font=(self.f_mono, 8, "bold"), fg=COLORS["accent_green"], bg=COLORS["bg_card"])
        self.lbl_pin_tag.pack(anchor="w")

        pin_row = tk.Frame(pin_card, bg=COLORS["bg_card"])
        pin_row.pack(fill="x", pady=(4, 0))

        self.pin_var = tk.StringVar(master=self.root, value=self.config.get("pin", "123456"))
        self.lbl_pin_display = tk.Label(
            pin_row,
            textvariable=self.pin_var,
            font=(self.f_mono, 18, "bold"),
            fg=COLORS["accent_green"],
            bg=COLORS["bg_card"]
        )
        self.lbl_pin_display.pack(side="left")

        btn_box2 = tk.Frame(pin_row, bg=COLORS["bg_card"])
        btn_box2.pack(side="right")

        self.btn_renew_pin = tk.Button(
            btn_box2,
            text=self.t("btn_renew_pin"),
            font=(self.f_sans, 8, "bold"),
            bg=COLORS["btn_surface"],
            fg=COLORS["text_sub"],
            activebackground=COLORS["btn_surface_hover"],
            activeforeground=COLORS["text_main"],
            relief="flat",
            bd=0,
            padx=10,
            pady=4,
            cursor="hand2",
            command=self._generate_random_pin
        )
        self.btn_renew_pin.pack(side="right", padx=(5, 0))

        self.btn_copy_pin = tk.Button(
            btn_box2,
            text=self.t("btn_copy_pin"),
            font=(self.f_sans, 8, "bold"),
            bg=COLORS["btn_surface"],
            fg=COLORS["accent_green"],
            activebackground=COLORS["btn_surface_hover"],
            activeforeground=COLORS["accent_green"],
            relief="flat",
            bd=0,
            padx=12,
            pady=4,
            cursor="hand2",
            command=lambda: self._copy_to_clip(self.pin_var.get().strip(), "PIN")
        )
        self.btn_copy_pin.pack(side="right")

        # Share Button
        self.btn_share = tk.Button(
            self.panel_ultra,
            text=self.t("btn_share_info"),
            font=(self.f_sans, 9, "bold"),
            bg=COLORS["btn_surface"],
            fg=COLORS["text_main"],
            activebackground=COLORS["btn_surface_hover"],
            activeforeground=COLORS["accent_green"],
            relief="flat",
            bd=0,
            pady=9,
            cursor="hand2",
            command=self._copy_share_info
        )
        self.btn_share.pack(fill="x", pady=(8, 6))

        # Active Session Live Notification Banner
        self.active_session_card = tk.Frame(self.panel_ultra, bg=COLORS["bg_card_inner"], padx=12, pady=8, highlightthickness=1, highlightbackground=COLORS["line"])
        self.active_session_label = tk.Label(
            self.active_session_card,
            text=self.t("session_waiting"),
            font=(self.f_sans, 8, "bold"),
            fg=COLORS["accent_green"],
            bg=COLORS["bg_card_inner"]
        )
        self.active_session_label.pack(side="left")

        self.btn_open_chat = tk.Button(
            self.active_session_card,
            text="Chat",
            font=(self.f_sans, 7, "bold"),
            bg=COLORS["btn_surface"],
            fg=COLORS["accent_green"],
            activebackground=COLORS["btn_surface_hover"],
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            padx=8,
            pady=3,
            cursor="hand2",
            command=lambda: self.chat_window.show() if self.chat_window else None
        )

        self.btn_disconnect_client = tk.Button(
            self.active_session_card,
            text=self.t("btn_disconnect"),
            font=(self.f_sans, 7, "bold"),
            bg=COLORS["accent_red"],
            fg="#FFFFFF",
            activebackground="#DC2626",
            relief="flat",
            bd=0,
            padx=8,
            pady=3,
            cursor="hand2",
            command=self._disconnect_active_client
        )
        self.active_session_card.pack(fill="x", pady=(4, 0))

    # -------------------------------------------------------------
    # PANEL 2: UNATTENDED / BACKGROUND ACCESS (24/7)
    # -------------------------------------------------------------
    def _build_chrome_panel(self):
        self.lbl_chrome_title = tk.Label(
            self.panel_chrome,
            text=self.t("chrome_title"),
            font=(self.f_sans, 10, "bold"),
            fg=COLORS["text_main"],
            bg=COLORS["bg_panel"]
        )
        self.lbl_chrome_title.pack(anchor="w")

        self.lbl_chrome_desc = tk.Label(
            self.panel_chrome,
            text=self.t("chrome_desc"),
            font=(self.f_sans, 8),
            fg=COLORS["text_muted"],
            bg=COLORS["bg_panel"],
            wraplength=480,
            justify="left"
        )
        self.lbl_chrome_desc.pack(anchor="w", pady=(2, 8))

        self.account_var = tk.StringVar(master=self.root, value=self.config.get("account", ""))
        self.name_var = tk.StringVar(master=self.root, value=self.config.get("device_name", os.environ.get("COMPUTERNAME", socket.gethostname() or "Workstation")))

        card = tk.Frame(self.panel_chrome, bg=COLORS["bg_card"], padx=14, pady=10, highlightthickness=1, highlightbackground=COLORS["line"])
        card.pack(fill="x", pady=(0, 8))

        self.lbl_account = tk.Label(card, text=self.t("account_label"), font=(self.f_sans, 8, "bold"), fg=COLORS["text_sub"], bg=COLORS["bg_card"])
        self.lbl_account.pack(anchor="w", pady=(1, 2))
        entry_account = tk.Entry(
            card,
            textvariable=self.account_var,
            font=(self.f_mono, 9),
            bg=COLORS["bg_card_inner"],
            fg=COLORS["text_main"],
            insertbackground=COLORS["accent_green"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            highlightcolor=COLORS["accent_green"]
        )
        entry_account.pack(fill="x", ipady=4, pady=(0, 6))

        self.lbl_device_name = tk.Label(card, text=self.t("device_name_label"), font=(self.f_sans, 8, "bold"), fg=COLORS["text_sub"], bg=COLORS["bg_card"])
        self.lbl_device_name.pack(anchor="w", pady=(1, 2))
        entry_name = tk.Entry(
            card,
            textvariable=self.name_var,
            font=(self.f_mono, 9),
            bg=COLORS["bg_card_inner"],
            fg=COLORS["text_main"],
            insertbackground=COLORS["accent_green"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            highlightcolor=COLORS["accent_green"]
        )
        entry_name.pack(fill="x", ipady=4, pady=(0, 6))

        self.lbl_perm_pin = tk.Label(card, text=self.t("perm_pin_label"), font=(self.f_sans, 8, "bold"), fg=COLORS["text_sub"], bg=COLORS["bg_card"])
        self.lbl_perm_pin.pack(anchor="w", pady=(1, 2))
        entry_pin = tk.Entry(
            card,
            textvariable=self.pin_var,
            font=(self.f_mono, 10, "bold"),
            bg=COLORS["bg_card_inner"],
            fg=COLORS["accent_green"],
            insertbackground=COLORS["accent_green"],
            relief="flat",
            show="*",
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            highlightcolor=COLORS["accent_green"]
        )
        entry_pin.pack(fill="x", ipady=4, pady=(0, 2))

        self.btn_minimize_tray = tk.Button(
            self.panel_chrome,
            text=self.t("btn_minimize_tray"),
            font=(self.f_sans, 8, "bold"),
            bg=COLORS["btn_surface"],
            fg=COLORS["text_main"],
            activebackground=COLORS["btn_surface_hover"],
            activeforeground=COLORS["accent_green"],
            relief="flat",
            bd=0,
            pady=8,
            cursor="hand2",
            command=self._minimize_to_tray
        )
        self.btn_minimize_tray.pack(fill="x", pady=(2, 0))

    # -------------------------------------------------------------
    # PANEL 3: SETTINGS & PRIVILEGE / SYSTEM SWITCHES (v1.4.0)
    # -------------------------------------------------------------
    def _build_settings_panel(self):
        card = tk.Frame(self.panel_settings, bg=COLORS["bg_card"], padx=12, pady=8, highlightthickness=1, highlightbackground=COLORS["line"])
        card.pack(fill="x", pady=(0, 6))

        self.lbl_relay = tk.Label(card, text=self.t("relay_label"), font=(self.f_sans, 8, "bold"), fg=COLORS["text_sub"], bg=COLORS["bg_card"])
        self.lbl_relay.pack(anchor="w", pady=(0, 3))

        relay_row = tk.Frame(card, bg=COLORS["bg_card"])
        relay_row.pack(fill="x")

        self.relay_var = tk.StringVar(master=self.root, value=self.config.get("relay", "wss://meikova-relay.onrender.com"))
        entry_relay = tk.Entry(
            relay_row,
            textvariable=self.relay_var,
            font=(self.f_mono, 9),
            bg=COLORS["bg_card_inner"],
            fg=COLORS["text_main"],
            insertbackground=COLORS["accent_green"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            highlightcolor=COLORS["accent_green"]
        )
        entry_relay.pack(side="left", fill="x", expand=True, ipady=3)

        self.btn_save_settings = tk.Button(
            relay_row,
            text=self.t("btn_save_settings"),
            font=(self.f_sans, 8, "bold"),
            bg=COLORS["btn_surface"],
            fg=COLORS["accent_green"],
            activebackground=COLORS["btn_surface_hover"],
            activeforeground=COLORS["accent_green"],
            relief="flat",
            bd=0,
            padx=12,
            pady=4,
            cursor="hand2",
            command=self._save_settings_click
        )
        self.btn_save_settings.pack(side="right", padx=(8, 0))

        # Basic & Admin Config Switches Card (matches v1.4.0 gui_view.html)
        chk_card = tk.Frame(self.panel_settings, bg=COLORS["bg_card"], padx=12, pady=8, highlightthickness=1, highlightbackground=COLORS["line"])
        chk_card.pack(fill="both", expand=True)

        self.keepawake_var = tk.BooleanVar(master=self.root, value=bool(self.config.get("keep_awake", True)))
        self.chk_keepawake = tk.Checkbutton(
            chk_card,
            text=self.t("keepawake_label"),
            variable=self.keepawake_var,
            command=self._on_keepawake_toggle,
            bg=COLORS["bg_card"],
            fg=COLORS["text_main"],
            selectcolor=COLORS["bg_card_inner"],
            activebackground=COLORS["bg_card"],
            activeforeground=COLORS["accent_green"],
            font=(self.f_sans, 8)
        )
        self.chk_keepawake.pack(anchor="w", pady=1)

        self.autostart_var = tk.BooleanVar(master=self.root, value=False)
        self.chk_autostart = tk.Checkbutton(
            chk_card,
            text=self.t("autostart_label"),
            variable=self.autostart_var,
            command=self._on_autostart_toggle,
            bg=COLORS["bg_card"],
            fg=COLORS["text_main"],
            selectcolor=COLORS["bg_card_inner"],
            activebackground=COLORS["bg_card"],
            activeforeground=COLORS["accent_green"],
            font=(self.f_sans, 8)
        )
        self.chk_autostart.pack(anchor="w", pady=1)

        self.close_to_tray_var = tk.BooleanVar(master=self.root, value=bool(self.config.get("close_to_tray", True)))
        self.chk_close_to_tray = tk.Checkbutton(
            chk_card,
            text=self.t("close_to_tray_label"),
            variable=self.close_to_tray_var,
            command=self._on_close_to_tray_toggle,
            bg=COLORS["bg_card"],
            fg=COLORS["text_main"],
            selectcolor=COLORS["bg_card_inner"],
            activebackground=COLORS["bg_card"],
            activeforeground=COLORS["accent_green"],
            font=(self.f_sans, 8)
        )
        self.chk_close_to_tray.pack(anchor="w", pady=1)

        self.stealth_var = tk.BooleanVar(master=self.root, value=bool(self.config.get("stealth_mode", False)))
        self.chk_stealth = tk.Checkbutton(
            chk_card,
            text=self.t("stealth_label"),
            variable=self.stealth_var,
            command=self._on_stealth_toggle,
            bg=COLORS["bg_card"],
            fg=COLORS["text_main"],
            selectcolor=COLORS["bg_card_inner"],
            activebackground=COLORS["bg_card"],
            activeforeground=COLORS["accent_green"],
            font=(self.f_sans, 8)
        )
        self.chk_stealth.pack(anchor="w", pady=1)

        self.admin_var = tk.BooleanVar(master=self.root, value=bool(self.config.get("admin_elevated", False) or self._os_engine.is_admin()))
        self.chk_admin = tk.Checkbutton(
            chk_card,
            text=self.t("admin_lever_label"),
            variable=self.admin_var,
            command=self._on_admin_toggle,
            bg=COLORS["bg_card"],
            fg=COLORS["accent_green"],
            selectcolor=COLORS["bg_card_inner"],
            activebackground=COLORS["bg_card"],
            activeforeground=COLORS["accent_green"],
            font=(self.f_sans, 8, "bold")
        )
        self.chk_admin.pack(anchor="w", pady=(4, 1))

    def _on_close_to_tray_toggle(self):
        self.config["close_to_tray"] = bool(self.close_to_tray_var.get())
        self._save_config()

    def _on_stealth_toggle(self):
        is_on = bool(self.stealth_var.get())
        self.config["stealth_mode"] = is_on
        self.config["show_tray_icon"] = not is_on
        self._save_config()
        if self.tray_icon:
            try:
                self.tray_icon.visible = not is_on
            except Exception:
                pass
        self._log(f"Stealth Mode: {'ON' if is_on else 'OFF'}")

    def _on_admin_toggle(self):
        is_on = bool(self.admin_var.get())
        self.config["admin_elevated"] = is_on
        self._save_config()
        self._log(f"Admin Mode: {'ENABLED' if is_on else 'DISABLED'}")

    # -------------------------------------------------------------
    # TAB SWITCHING
    # -------------------------------------------------------------
    def _switch_tab(self, tab: str):
        self.current_tab = tab
        self.panel_ultra.pack_forget()
        self.panel_chrome.pack_forget()
        self.panel_settings.pack_forget()

        for btn, name in [(self.btn_tab_ultra, "ultra"), (self.btn_tab_chrome, "chrome"), (self.btn_tab_cfg, "settings")]:
            if name == tab:
                btn.config(bg=COLORS["accent_green"], fg=COLORS["bg_main"], activebackground="#6AD696", activeforeground=COLORS["bg_main"])
            else:
                btn.config(bg=COLORS["bg_panel"], fg=COLORS["text_sub"], activebackground=COLORS["btn_surface"], activeforeground=COLORS["text_main"])

        if tab == "ultra":
            self.panel_ultra.pack(fill="both", expand=True)
        elif tab == "chrome":
            self.panel_chrome.pack(fill="both", expand=True)
        elif tab == "settings":
            self.panel_settings.pack(fill="both", expand=True)

    # -------------------------------------------------------------
    # DYNAMIC LANGUAGE APPLICATION
    # -------------------------------------------------------------
    def _apply_language(self):
        self.root.title(self.t("app_title"))
        comp_name = self.config.get("device_name") or os.environ.get("COMPUTERNAME") or socket.gethostname() or "Workstation"
        self.lbl_header_subtitle.config(text=self.t("workstation_fmt", name=comp_name))
        self.lbl_header_title.config(text=self.t("header_title"))

        if self.lang == "vi":
            self.btn_lang_vi.config(bg=COLORS["accent_green"], fg=COLORS["bg_main"])
            self.btn_lang_en.config(bg=COLORS["bg_card"], fg=COLORS["text_muted"])
        else:
            self.btn_lang_en.config(bg=COLORS["accent_green"], fg=COLORS["bg_main"])
            self.btn_lang_vi.config(bg=COLORS["bg_card"], fg=COLORS["text_muted"])

        self.btn_tab_ultra.config(text=self.t("tab_ultra"))
        self.btn_tab_chrome.config(text=self.t("tab_chrome"))
        self.btn_tab_cfg.config(text=self.t("tab_settings"))

        if self.is_running:
            self.btn_master_toggle.config(text=self.t("btn_stop_service"))
        else:
            self.btn_master_toggle.config(text=self.t("btn_start_service"))

        if self.is_running:
            if self.connected_client_info:
                self.status_pill.config(text=self.t("status_connected"), fg=COLORS["accent_cyan"], bg=COLORS["accent_cyan_bg"])
            else:
                self.status_pill.config(text=self.t("status_ready"), fg=COLORS["accent_green"], bg=COLORS["accent_green_bg"])
        else:
            self.status_pill.config(text=self.t("status_stopped"), fg=COLORS["accent_red"], bg=COLORS["accent_red_bg"])

        if self.connected_client_info:
            self.active_session_label.config(text=self.t("session_active", client=self.connected_client_info), fg=COLORS["accent_cyan"])
        elif self.is_running:
            self.active_session_label.config(text=self.t("session_waiting"), fg=COLORS["accent_green"])
        else:
            self.active_session_label.config(text=self.t("session_stopped"), fg=COLORS["text_muted"])

        self.lbl_ultra_title.config(text=self.t("ultra_title"))
        self.lbl_ultra_desc.config(text=self.t("ultra_desc"))
        self.lbl_room_tag.config(text=self.t("room_id_label"))
        self.btn_renew_room.config(text=self.t("btn_renew_room"))
        self.btn_copy_room.config(text=self.t("btn_copy_room"))
        self.lbl_pin_tag.config(text=self.t("pin_label"))
        self.btn_renew_pin.config(text=self.t("btn_renew_pin"))
        self.btn_copy_pin.config(text=self.t("btn_copy_pin"))
        self.btn_share.config(text=self.t("btn_share_info"))
        self.btn_disconnect_client.config(text=self.t("btn_disconnect"))

        self.lbl_chrome_title.config(text=self.t("chrome_title"))
        self.lbl_chrome_desc.config(text=self.t("chrome_desc"))
        self.lbl_account.config(text=self.t("account_label"))
        self.lbl_device_name.config(text=self.t("device_name_label"))
        self.lbl_perm_pin.config(text=self.t("perm_pin_label"))
        self.chk_autostart.config(text=self.t("autostart_label"))
        self.chk_keepawake.config(text=self.t("keepawake_label"))
        self.chk_close_to_tray.config(text=self.t("close_to_tray_label"))
        self.chk_stealth.config(text=self.t("stealth_label"))
        self.chk_admin.config(text=self.t("admin_lever_label"))
        self.btn_minimize_tray.config(text=self.t("btn_minimize_tray"))

        self.lbl_relay.config(text=self.t("relay_label"))
        self.btn_save_settings.config(text=self.t("btn_save_settings"))
        self.lbl_log_title.config(text=self.t("log_title"))

        if HAS_TRAY and self.tray_icon:
            try:
                if build_tray_menu:
                    self.tray_icon.menu = build_tray_menu(self, self._restore_from_tray, self._exit_application)
                self.tray_icon.update_menu()
            except Exception:
                pass

    # -------------------------------------------------------------
    # SERVICE CONTROL
    # -------------------------------------------------------------
    def _toggle_service(self):
        if self.is_running:
            self._stop_service()
        else:
            self._start_service()

    def _start_service(self):
        self.config["relay"] = self.relay_var.get().strip()
        self.config["account"] = self.account_var.get().strip()
        self.config["device_name"] = self.name_var.get().strip()
        self.config["room_id"] = self.room_var.get().strip()
        self.config["pin"] = self.pin_var.get().strip()
        self.config["keep_awake"] = self.keepawake_var.get()
        self._save_config()

        if self.config["keep_awake"]:
            PowerManager.prevent_sleep(True)

        fps_cfg = int(self.config.get("fps", 120))
        self.host_service = HostService(
            relay_url=self.config["relay"],
            room_id=self.config["room_id"],
            pin=self.config["pin"],
            device_name=self.config["device_name"],
            account=self.config["account"],
            user_id=self.config.get("user_id"),
            fps=fps_cfg,
            host_config=self.config,
        )

        def _on_cfg_updated(new_cfg):
            self.config.update(new_cfg)
            self._save_config()

        self.host_service.on_config_updated = _on_cfg_updated
        self.host_service.on_status_change = lambda st, detail="": self._enqueue_ui_action(lambda: self._on_service_status(st, detail))
        self.host_service.on_client_connect = lambda ev: self._enqueue_ui_action(lambda: self._on_client_connected(ev))
        self.host_service.on_client_disconnect = lambda: self._enqueue_ui_action(self._on_client_disconnected)

        def _on_chat(sender, text):
            self._log(f"[CHAT] [{sender}]: {text}")
            if self.chat_window:
                self.chat_window.add_message(sender, text, is_local=False)

        self.host_service.on_chat_message = lambda sender, text: self._enqueue_ui_action(lambda: _on_chat(sender, text))

        def runner():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.host_service.start())
            except Exception as e:
                self._enqueue_ui_action(lambda: self._log(f"Service Error: {e}"))

        self.service_thread = threading.Thread(target=runner, daemon=True)
        self.service_thread.start()

        self.is_running = True
        self._is_running = True
        self.status_pill.config(text=self.t("status_running"), fg=COLORS["accent_green"], bg=COLORS["accent_green_bg"])
        self.btn_master_toggle.config(text=self.t("btn_stop_service"), bg=COLORS["accent_red"], fg="#FFFFFF", activebackground="#DC2626")
        self.active_session_label.config(text=self.t("session_waiting"), fg=COLORS["accent_green"])
        self._log(self.t("log_service_started", room_id=self.config['room_id']))

    def _stop_service(self):
        if self.host_service:
            try:
                self.host_service.stop()
            except Exception:
                pass

        PowerManager.prevent_sleep(False)
        self.is_running = False
        self._is_running = False
        self.connected_client_info = None
        self.status_pill.config(text=self.t("status_stopped"), fg=COLORS["accent_red"], bg=COLORS["accent_red_bg"])
        self.btn_master_toggle.config(text=self.t("btn_start_service"), bg=COLORS["accent_green"], fg=COLORS["bg_main"], activebackground="#6AD696")
        self.active_session_label.config(text=self.t("session_stopped"), fg=COLORS["text_muted"])
        if hasattr(self, "btn_open_chat"):
            self.btn_open_chat.pack_forget()
        self.btn_disconnect_client.pack_forget()
        self._log(self.t("log_service_stopped"))

    def _on_service_status(self, status: str, detail: str = ""):
        if status == "ready":
            self.status_pill.config(text=self.t("status_ready"), fg=COLORS["accent_green"], bg=COLORS["accent_green_bg"])
            self.active_session_label.config(text=self.t("session_waiting"), fg=COLORS["accent_green"])
            self._log(self.t("log_room_registered", room_id=self.config['room_id']))
        elif status == "reconnecting":
            self.status_pill.config(text=self.t("status_reconnecting"), fg=COLORS["accent_amber"], bg=COLORS["accent_amber_bg"])
            msg = self.t("log_reconnecting")
            if detail:
                msg = f"{msg} (Chi tiết: {detail})"
            self._log(msg)

    def _on_client_connected(self, event: dict):
        client_user = event.get("clientUser") or event.get("username") or ("Người điều khiển từ xa" if self.lang == "vi" else "Remote Operator")
        client_ip = event.get("clientIp") or "N/A"
        self.connected_client_info = f"{client_user} ({client_ip})"
        self.status_pill.config(text=self.t("status_connected"), fg=COLORS["accent_cyan"], bg=COLORS["accent_cyan_bg"])
        self.active_session_label.config(text=self.t("session_active", client=self.connected_client_info), fg=COLORS["accent_cyan"])
        if self.chat_window:
            self.btn_open_chat.pack(side="right", padx=(0, 6))
        self.btn_disconnect_client.pack(side="right")
        self._log(self.t("log_new_connection", client=self.connected_client_info))

    def _on_client_disconnected(self):
        self.connected_client_info = None
        if hasattr(self, "btn_open_chat"):
            self.btn_open_chat.pack_forget()
        self.btn_disconnect_client.pack_forget()
        if self.is_running:
            self.status_pill.config(text=self.t("status_ready"), fg=COLORS["accent_green"], bg=COLORS["accent_green_bg"])
            self.active_session_label.config(text=self.t("session_waiting"), fg=COLORS["accent_green"])
            self._log(self.t("log_disconnected"))

    def _disconnect_active_client(self):
        if self.host_service and self.host_service.ws and self.host_service.loop:
            self._log(self.t("log_emergency_disconnect"))
            room_id = self.config.get("room_id", "")
            try:
                asyncio.run_coroutine_threadsafe(
                    self.host_service.ws.send(json.dumps({"type": "host_disconnect_clients", "room_id": room_id})),
                    self.host_service.loop
                )
                asyncio.run_coroutine_threadsafe(
                    self.host_service.ws.send(json.dumps({"type": "client_disconnected", "room_id": room_id})),
                    self.host_service.loop
                )
            except Exception:
                pass
            self.host_service.has_active_client = False
            self._on_client_disconnected()

    # -------------------------------------------------------------
    # RANDOM CODES & CLIPBOARD
    # -------------------------------------------------------------
    def _generate_random_room(self):
        rand_id = generate_secure_room_id()
        self.room_var.set(rand_id)
        self.config["room_id"] = rand_id
        self._save_config()
        self._log(self.t("log_new_room", room_id=rand_id))
        if self.is_running:
            self._log(self.t("log_restart_req"))

    def _generate_random_pin(self):
        rand_pin = generate_secure_pin()
        self.pin_var.set(rand_pin)
        self.config["pin"] = rand_pin
        self._save_config()
        self._log(self.t("log_new_pin", pin=rand_pin))

    def _copy_to_clip(self, text: str, name: str):
        self._os_engine.set_clipboard_text(text, tk_root=self.root)
        self._log(self.t("log_copied", name=name, text=text))

    def _copy_share_info(self):
        room = self.room_var.get().strip()
        pin = self.pin_var.get().strip()
        relay = self.relay_var.get().strip()
        http_url = relay.replace("wss://", "https://").replace("ws://", "http://")
        info = (
            f"{self.t('share_header')}\n"
            f"{self.t('share_dashboard')} {http_url}/dashboard\n"
            f"{self.t('share_room')} {room}\n"
            f"{self.t('share_pin')} {pin}\n"
            "--------------------------------------------"
        )
        self._os_engine.set_clipboard_text(info, tk_root=self.root)
        self._log(self.t("log_copied_all"))

    def copy_share_info(self):
        self._copy_share_info()

    def _save_settings_click(self):
        self.config["relay"] = self.relay_var.get().strip()
        self.config["account"] = self.account_var.get().strip()
        self.config["device_name"] = self.name_var.get().strip()
        self._save_config()
        self._log(self.t("log_saved_relay"))

    # -------------------------------------------------------------
    # AUTO-START & SYSTEM TRAY (OS-Engine Powered)
    # -------------------------------------------------------------
    def _check_autostart_status(self):
        try:
            self.autostart_var.set(bool(self._os_engine.is_autostart_enabled()))
        except Exception:
            self.autostart_var.set(False)

    def _on_autostart_toggle(self):
        enable = bool(self.autostart_var.get())
        ok, detail = self._os_engine.set_autostart(enable, config_path=self._get_config_path())
        if ok:
            self._log(f"{self.t('log_autostart_on' if enable else 'log_autostart_off')} ({detail})")
        else:
            self._log(f"Autostart Error: {detail}")

    def toggle_autostart(self, is_on: bool):
        self.autostart_var.set(bool(is_on))
        self._on_autostart_toggle()

    def _on_keepawake_toggle(self):
        enable = bool(self.keepawake_var.get())
        self.config["keep_awake"] = enable
        self._save_config()
        PowerManager.prevent_sleep(enable)
        state_str = "ON" if (enable and self.lang == "en") else ("BẬT" if enable else ("OFF" if self.lang == "en" else "TẮT"))
        self._log(self.t("log_keepawake", state=state_str))

    def toggle_keepawake(self, is_on: bool):
        self.keepawake_var.set(bool(is_on))
        self._on_keepawake_toggle()

    def _init_system_tray(self):
        if not HAS_TRAY:
            return

        if build_tray_menu:
            menu = build_tray_menu(self, self._restore_from_tray, self._exit_application)
        else:
            menu = pystray.Menu(
                pystray.MenuItem(self.t("tray_open"), self._restore_from_tray, default=True),
                pystray.MenuItem(self.t("tray_copy"), self._copy_share_info),
                pystray.MenuItem(self.t("tray_exit"), self._exit_application)
            )
        self.tray_icon = pystray.Icon("MeikovaRelayHost", get_tray_icon_image(), "Meikova Relay Host", menu)
        self.tray_icon._thread = threading.current_thread()
        self.tray_icon._running = False
        self._tray_icon = self.tray_icon

        # Attach Linux/XOrg left & right click hooks directly onto the tray icon instance
        self.tray_icon._meikova_on_left_click = lambda _ic=None, rx=None, ry=None: self._restore_from_tray()
        if show_custom_tk_tray_popup:
            self.tray_icon._meikova_on_right_click = lambda _ic=None, rx=None, ry=None: show_custom_tk_tray_popup(
                self, self._restore_from_tray, self._exit_application, x=rx, y=ry
            )

        show_tray = self.config.get("show_tray_icon", True) and not self.config.get("stealth_mode", False)
        if "--no-tray" in sys.argv:
            show_tray = False
        elif "--tray" in sys.argv:
            show_tray = True

        def setup_tray(icon):
            ensure_interactive_desktop()
            icon.visible = bool(show_tray)

        def tray_worker():
            ensure_interactive_desktop()
            try:
                self.tray_icon.run(setup=setup_tray)
            except Exception:
                pass

        threading.Thread(target=tray_worker, daemon=True).start()

    def _minimize_to_tray(self):
        self.root.withdraw()
        self._log(self.t("log_minimized"))

    def _restore_from_tray(self, icon=None, item=None):
        self._enqueue_ui_action(self._show_window)

    def _show_window(self):
        self._os_engine.activate_window(self.root, title="Meikova Relay Host")

    def _on_window_close(self):
        close_to_tray = self.config.get("close_to_tray", True)
        if close_to_tray and HAS_TRAY:
            self._minimize_to_tray()
        else:
            self._exit_application()

    def _exit_application(self, icon=None, item=None):
        safely_remove_tray_icon(self.tray_icon or icon)
        try:
            self.root.withdraw()
        except Exception:
            pass
        self._stop_service()
        try:
            self.root.destroy()
        except Exception:
            pass
        sys.exit(0)

    def _log(self, msg: str):
        if hasattr(self, "log_text"):
            try:
                self.log_text.config(state="normal")
                self.log_text.insert("end", f"[{time.strftime('%H:%M:%S')}] {msg}\n")
                self.log_text.see("end")
                self.log_text.config(state="disabled")
            except Exception:
                pass

def find_resource(filename: str) -> Optional[Path]:
    base_dirs = [
        current_dir,
        Path(__file__).resolve().parent,
        Path(getattr(sys, "_MEIPASS", current_dir)),
        Path(getattr(sys, "_MEIPASS", current_dir)) / "host_agent",
        current_dir / "host_agent",
    ]
    for d in base_dirs:
        p = d / filename
        if p.exists():
            return p
    return None

def set_clipboard_text(text: str) -> bool:
    return _get_engine_for_current_platform().set_clipboard_text(text)


def is_autostart_enabled() -> bool:
    return _get_engine_for_current_platform().is_autostart_enabled()


def apply_dark_titlebar(hwnd):
    """Apply native dark theme and extend frame into client area to eliminate white borders."""
    if sys.platform != "win32" or not hwnd:
        return
    try:
        import ctypes
        from ctypes import byref, c_int
        dwmapi = ctypes.windll.dwmapi
        dark = c_int(1)
        # DWMWA_USE_IMMERSIVE_DARK_MODE (20 on Win10 20H1+, 19 on older builds)
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
    except Exception:
        pass

def set_window_icon(hwnd, icon_path: Path):
    """Set titlebar and taskbar icon for the window using Win32 API."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hicon_sm = user32.LoadImageW(0, str(icon_path), 1, 16, 16, 0x00000010)
        hicon_lg = user32.LoadImageW(0, str(icon_path), 1, 32, 32, 0x00000010)
        if hicon_sm:
            user32.SendMessageW(hwnd, 0x0080, 0, hicon_sm)
        if hicon_lg:
            user32.SendMessageW(hwnd, 0x0080, 1, hicon_lg)
    except Exception:
        pass

def _get_default_config_path() -> Path:
    return resolve_config_path()

def _load_initial_config(cfg_file: Path) -> dict:
    default_comp = os.environ.get("COMPUTERNAME", socket.gethostname())
    config = {
        "relay": "wss://meikova-relay.onrender.com",
        "account": "",
        "device_name": default_comp,
        "room_id": generate_secure_room_id(),
        "pin": generate_secure_pin(),
        "keep_awake": True,
        "start_minimized": False,
        "lang": "vi"
    }
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                config.update(json.load(f))
        except Exception:
            pass
    if config.get("lang") not in ("vi", "en"):
        config["lang"] = "vi"
    return config

class HostApi:
    def __init__(self, config: dict, config_path: Path):
        self._config = config
        self._config_path = config_path
        self._lang = config.get("lang", "vi")
        self._window = None
        self._hwnd = None
        self._host_service: Optional[HostService] = None
        self._service_thread: Optional[threading.Thread] = None
        self._is_running = False
        self._connected_client_info: Optional[str] = None
        self._tray_icon = None
        self._is_quitting = False
        self._service_lock = threading.Lock()
        self._chat_window: Optional[HostChatWindow] = None

    @property
    def chat_window(self) -> Optional[HostChatWindow]:
        if self._chat_window is None and HostChatWindow:
            try:
                def _handle_reply(text: str):
                    if self._host_service:
                        self._host_service.send_chat_message(text)
                    try:
                        payload = json.dumps({
                            "sender": "Bạn",
                            "text": text,
                            "is_local": True,
                            "time": time.strftime("%H:%M:%S")
                        })
                        self._eval_js(f"window.__onIncomingChat && window.__onIncomingChat({payload});")
                    except Exception:
                        pass

                self._chat_window = HostChatWindow(
                    on_send_reply=_handle_reply,
                    parent=None
                )
            except Exception:
                self._chat_window = None
        return self._chat_window

    @chat_window.setter
    def chat_window(self, val):
        self._chat_window = val

    def destroy(self):
        if getattr(self, '_chat_window', None):
            try:
                self._chat_window.destroy()
            except Exception:
                pass
            self._chat_window = None

    def __del__(self):
        try:
            self.destroy()
        except Exception:
            pass

    def set_window(self, window):
        self._window = window
        self._resolve_hwnd()

    def _resolve_hwnd(self) -> Optional[int]:
        if self._hwnd:
            return self._hwnd
        if sys.platform == "win32" and self._window:
            try:
                if hasattr(self._window, "native") and self._window.native:
                    if hasattr(self._window.native, "Handle"):
                        h_val = self._window.native.Handle
                        self._hwnd = int(h_val.ToInt64()) if hasattr(h_val, "ToInt64") else int(str(h_val))
            except Exception:
                pass
            if not self._hwnd:
                try:
                    import ctypes
                    self._hwnd = ctypes.windll.user32.FindWindowW(None, "Meikova Relay Host")
                except Exception:
                    pass
        return self._hwnd

    def t(self, key: str, **kwargs) -> str:
        lang_dict = TRANSLATIONS.get(self._lang, TRANSLATIONS["vi"])
        tmpl = lang_dict.get(key, TRANSLATIONS["vi"].get(key, key))
        if kwargs:
            return tmpl.format(**kwargs)
        return tmpl

    def _init_js_worker(self):
        import queue
        if hasattr(self, '_js_queue'):
            return
        self._js_queue = queue.Queue(maxsize=100)
        def _js_worker_loop():
            while not getattr(self, '_is_quitting', False):
                try:
                    code = self._js_queue.get(timeout=0.2)
                    if self._window and not getattr(self, '_is_quitting', False):
                        try:
                            self._window.evaluate_js(code)
                        except Exception:
                            pass
                    self._js_queue.task_done()
                except queue.Empty:
                    continue
                except Exception:
                    pass
        self._js_thread = threading.Thread(target=_js_worker_loop, daemon=True, name="HostGuiJsWorker")
        self._js_thread.start()

    def _eval_js(self, js: str):
        if not self._window or getattr(self, '_is_quitting', False):
            return
        if not hasattr(self, '_js_queue'):
            self._init_js_worker()
        try:
            self._js_queue.put_nowait(js)
        except Exception:
            # Queue full: prune oldest item then enqueue
            try:
                self._js_queue.get_nowait()
                self._js_queue.task_done()
            except Exception:
                pass
            try:
                self._js_queue.put_nowait(js)
            except Exception:
                pass

    def _log(self, msg: str):
        t_str = time.strftime("%H:%M:%S")
        try:
            print(f"[{t_str}] {msg}")
        except Exception:
            pass
        safe_msg = json.dumps(msg)
        self._eval_js(f"window.__onLog && window.__onLog({safe_msg});")

    def get_initial_data(self) -> dict:
        cfg_copy = dict(self._config)
        cfg_copy["relay_url"] = cfg_copy.get("relay") or "wss://meikova-relay.onrender.com"
        return {
            "config": cfg_copy,
            "version": f"v{APP_VERSION}",
            "autostart": is_autostart_enabled(),
            "service_installed": is_windows_service_installed(),
            "deployment": get_deployment_status(),
            "is_running": self._is_running
        }

    def drag_window(self):
        if sys.platform == "win32" and self._window:
            try:
                import ctypes
                hwnd = self._resolve_hwnd()
                if hwnd:
                    ctypes.windll.user32.ReleaseCapture()
                    ctypes.windll.user32.SendMessageW(hwnd, 0x00A1, 2, 0)
            except Exception:
                pass

    def minimize_window(self):
        if self._window:
            try:
                self._window.minimize()
            except Exception:
                pass

    def toggle_maximize(self) -> bool:
        if self._window:
            if sys.platform == "win32":
                try:
                    import ctypes
                    hwnd = self._resolve_hwnd()
                    if hwnd:
                        is_zoomed = bool(ctypes.windll.user32.IsZoomed(hwnd))
                        if is_zoomed:
                            ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                        else:
                            ctypes.windll.user32.ShowWindow(hwnd, 3)  # SW_MAXIMIZE
                        return not is_zoomed
                except Exception:
                    pass
            try:
                self._window.toggle_fullscreen()
            except Exception:
                pass
        return False

    def is_maximized(self) -> bool:
        if sys.platform == "win32":
            try:
                import ctypes
                hwnd = self._resolve_hwnd()
                if hwnd:
                    return bool(ctypes.windll.user32.IsZoomed(hwnd))
            except Exception:
                pass
        return False

    def close_window(self):
        close_to_tray = self._config.get("close_to_tray", True)
        if close_to_tray and HAS_TRAY:
            self.minimize_to_tray()
        else:
            self._is_quitting = True
            self.stop_service()
            if self._tray_icon:
                try:
                    self._tray_icon.stop()
                except Exception:
                    pass
            if self._window:
                try:
                    self._window.destroy()
                except Exception:
                    pass
            sys.exit(0)

    def _save_config(self):
        self._config["lang"] = self._lang
        try:
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2)
        except Exception:
            pass

    def start_service(self):
        with self._service_lock:
            if self._is_running:
                return
            self._is_running = True

        relay_url = self._config.get("relay") or self._config.get("relay_url") or "wss://meikova-relay.onrender.com"
        room_id = self._config.get("room_id") or "RD-8888"
        pin = self._config.get("pin") or "123456"
        account = self._config.get("account") or ""
        device_name = self._config.get("device_name") or os.environ.get("COMPUTERNAME", "Workstation")
        perm_pin = self._config.get("perm_pin") or ""

        self._config["relay"] = relay_url
        self._config["room_id"] = room_id
        self._config["pin"] = pin
        self._config["account"] = account
        self._config["device_name"] = device_name
        self._config["perm_pin"] = perm_pin
        self._save_config()

        if self._config.get("keep_awake"):
            PowerManager.prevent_sleep(True)

        if self._config.get("auto_update", True):
            try:
                start_auto_update_loop(relay_url, APP_VERSION)
            except Exception:
                pass

        try:
            fps_cfg = int(self._config.get("fps", 120))
            self._host_service = HostService(
                relay_url=relay_url,
                room_id=room_id,
                pin=pin,
                device_name=device_name,
                account=account,
                user_id=self._config.get("user_id"),
                fps=fps_cfg,
                host_config=self._config,
            )
            def _on_cfg_updated(new_cfg):
                self._config.update(new_cfg)
                self._save_config()
            self._host_service.on_config_updated = _on_cfg_updated
            self._host_service.on_status_change = self._on_service_status
            self._host_service.on_client_connect = self._on_client_connected
            self._host_service.on_client_disconnect = self._on_client_disconnected
            def _on_webview_chat(sender, text):
                self._log(f"[CHAT] [{sender}]: {text}")
                if self.chat_window:
                    self.chat_window.add_message(sender, text, is_local=False)
                payload = json.dumps({
                    "sender": sender,
                    "text": text,
                    "is_local": False,
                    "time": time.strftime("%H:%M:%S")
                })
                self._eval_js(f"window.__onIncomingChat && window.__onIncomingChat({payload});")

            self._host_service.on_chat_message = _on_webview_chat
        except Exception as e:
            self._log(f"Service Init Error: {e}")
            return

        def runner():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._host_service.start())
            except Exception as e:
                self._log(f"Service Error: {e}")

        self._service_thread = threading.Thread(target=runner, daemon=True)
        self._service_thread.start()
        self._is_running = True

        self._eval_js("window.__onServiceStatus && window.__onServiceStatus('ready');")
        self._log(self.t("log_service_started", room_id=room_id))

    def stop_service(self):
        with self._service_lock:
            if self._host_service:
                try:
                    self._host_service.stop()
                except Exception:
                    pass
                self._host_service = None

            PowerManager.prevent_sleep(False)
            self._is_running = False
            self._connected_client_info = None
            self._eval_js("window.__onServiceStatus && window.__onServiceStatus('stopped');")
        self._log(self.t("log_service_stopped"))

    def _on_service_status(self, status: str, detail: str = ""):
        safe_st = json.dumps(status)
        self._eval_js(f"window.__onServiceStatus && window.__onServiceStatus({safe_st});")
        if status == "ready":
            self._log(self.t("log_room_registered", room_id=self._config.get("room_id", "")))
        elif status == "reconnecting":
            msg = self.t("log_reconnecting")
            if detail:
                msg = f"{msg} (Chi tiết: {detail})"
            self._log(msg)

    def _on_client_connected(self, event: dict):
        client_user = event.get("clientUser") or event.get("username") or ("Người điều khiển từ xa" if self._lang == "vi" else "Remote Operator")
        client_ip = event.get("clientIp") or "N/A"
        self._connected_client_info = f"{client_user} ({client_ip})"
        safe_client = json.dumps(self._connected_client_info)
        self._eval_js(f"window.__onClientConnected && window.__onClientConnected({safe_client});")
        self._log(self.t("log_new_connection", client=self._connected_client_info))

    def _on_client_disconnected(self):
        self._connected_client_info = None
        self._eval_js("window.__onClientDisconnected && window.__onClientDisconnected();")
        if self._is_running:
            self._log(self.t("log_disconnected"))

    def renew_room(self) -> str:
        rand_id = generate_secure_room_id()
        self._config["room_id"] = rand_id
        self._save_config()
        self._log(self.t("log_new_room", room_id=rand_id))
        if self._is_running:
            self._log(self.t("log_restart_req"))
        return rand_id

    def renew_pin(self) -> str:
        rand_pin = generate_secure_pin()
        self._config["pin"] = rand_pin
        self._save_config()
        self._log(self.t("log_new_pin", pin=rand_pin))
        return rand_pin

    def open_chat_window(self):
        """Opens/raises host chat window."""
        if self.chat_window:
            self.chat_window.show()
            return {"status": "ok"}
        return {"status": "error", "message": "Chat window not available"}

    def send_host_chat(self, text: str) -> dict:
        """Sends chat message from host GUI to remote client."""
        text = (text or "").strip()
        if not text:
            return {"status": "error", "message": "Tin nhắn trống"}
        if self._host_service:
            ok = self._host_service.send_chat_message(text)
            if self.chat_window:
                self.chat_window.add_message("Bạn", text, is_local=True)
            return {"status": "ok" if ok else "warning", "sent": ok}
        return {"status": "error", "message": "Dịch vụ máy trạm chưa kết nối"}

    def get_chat_history(self) -> list:
        """Returns in-memory chat message history."""
        if self.chat_window:
            return self.chat_window.history
        return []

    def copy_text(self, text: str, name: str):
        set_clipboard_text(text)
        self._log(self.t("log_copied", name=name, text=text))

    def copy_share_info(self):
        room = self._config.get("room_id", "")
        pin = self._config.get("pin", "")
        relay = self._config.get("relay") or self._config.get("relay_url") or "wss://meikova-relay.onrender.com"
        http_url = relay.replace("wss://", "https://").replace("ws://", "http://")
        info = (
            f"{self.t('share_header')}\n"
            f"{self.t('share_dashboard')} {http_url}/dashboard\n"
            f"{self.t('share_room')} {room}\n"
            f"{self.t('share_pin')} {pin}\n"
            "--------------------------------------------"
        )
        set_clipboard_text(info)
    def check_for_updates(self) -> dict:
        relay_url = self._config.get("relay") or "wss://meikova-relay.onrender.com"
        info = check_for_updates(relay_url, APP_VERSION)
        if info:
            return {"success": True, "update": info}
        return {"success": True, "message": "Up to date", "version": APP_VERSION}

    def apply_update_now(self) -> dict:
        relay_url = self._config.get("relay") or "wss://meikova-relay.onrender.com"
        ok = check_and_apply_update(relay_url, APP_VERSION)
        return {"success": ok}

    def disconnect_client(self):
        if self._host_service and self._host_service.ws and self._host_service.loop:
            self._log(self.t("log_emergency_disconnect"))
            room_id = self._config.get("room_id", "")
            try:
                asyncio.run_coroutine_threadsafe(
                    self._host_service.ws.send(json.dumps({"type": "host_disconnect_clients", "room_id": room_id})),
                    self._host_service.loop
                )
                asyncio.run_coroutine_threadsafe(
                    self._host_service.ws.send(json.dumps({"type": "client_disconnected", "room_id": room_id})),
                    self._host_service.loop
                )
            except Exception:
                pass
            self._host_service.has_active_client = False
            self._on_client_disconnected()

    def toggle_admin_elevation(self, is_on: bool) -> dict:
        """Toggles Administrator privilege mode on the Host GUI (triggers UAC elevation on Windows if needed)."""
        from host_agent.deployment_manager import elevate_and_execute, is_current_user_admin
        is_adm = is_current_user_admin()
        if is_on:
            if is_adm:
                self._config["admin_elevated"] = True
                self._save_config()
                msg = "Đã bật Cần gạt Quản trị viên (Quyền Administrator đang hoạt động)."
                self._log(msg)
                return {"success": True, "is_admin": True, "message": msg}
            if sys.platform == "win32" and "unittest" not in sys.modules:
                elevated = elevate_and_execute("--admin --restart")
                if elevated:
                    self._config["admin_elevated"] = True
                    self._save_config()
                    msg = "Đang khởi chạy lại với quyền Quản trị viên (UAC Admin)..."
                    self._log(msg)
                    return {"success": True, "is_admin": True, "message": msg}
                msg = "Người dùng đã từ chối cấp quyền UAC Administrator."
                self._log(msg)
                return {"success": False, "is_admin": False, "message": msg}
            self._config["admin_elevated"] = True
            self._save_config()
            msg = "Đã bật chế độ cấu hình Quản trị viên (Admin)."
            self._log(msg)
            return {"success": True, "is_admin": True, "message": msg}
        else:
            self._config["admin_elevated"] = False
            self._config["block_input"] = False
            self._config["privacy_curtain"] = False
            self._save_config()
            try:
                from host_agent.input_injector import InputInjector
                from host_agent.privacy_curtain import privacy_curtain
                InputInjector.set_block_input(False)
                privacy_curtain.disable()
            except Exception:
                pass
            msg = "Đã tắt Cần gạt Quản trị viên."
            self._log(msg)
            return {"success": True, "is_admin": False, "message": msg}

    def toggle_stealth_mode(self, is_on: bool) -> dict:
        """Enables or disables Stealth Mode (hides tray icon and window)."""
        self._config["stealth_mode"] = bool(is_on)
        self._config["show_tray_icon"] = not bool(is_on)
        self._save_config()
        if self._tray_icon:
            try:
                self._tray_icon.visible = not bool(is_on)
            except Exception:
                pass
        if self._host_service:
            self._host_service.host_config["stealth_mode"] = bool(is_on)
            self._host_service.host_config["show_tray_icon"] = not bool(is_on)
        msg = "Chế độ Tàng hình (Stealth Mode): ĐÃ BẬT" if is_on else "Chế độ Tàng hình (Stealth Mode): ĐÃ TẮT"
        self._log(msg)
        return {"success": True, "stealth_mode": bool(is_on), "message": msg}

    def toggle_auto_wakeup(self, is_on: bool, wake_time: str = "08:00") -> dict:
        """Enables or disables scheduled RTC hardware Auto-Wakeup."""
        res = PowerManager.configure_auto_wakeup(bool(is_on), wake_time)
        self._config["auto_wakeup"] = bool(is_on)
        self._config["auto_wakeup_time"] = str(wake_time or "08:00")
        self._save_config()
        if self._host_service:
            self._host_service.host_config["auto_wakeup"] = bool(is_on)
            self._host_service.host_config["auto_wakeup_time"] = str(wake_time or "08:00")
        self._log(res.get("message", "Cập nhật Auto-Wakeup"))
        return res

    def toggle_block_input(self, is_on: bool) -> dict:
        """Blocks or unblocks physical mouse and keyboard on the host."""
        from host_agent.input_injector import InputInjector
        ok = InputInjector.set_block_input(bool(is_on))
        self._config["block_input"] = bool(is_on) if ok else False
        self._save_config()
        msg = f"Chặn chuột & bàn phím vật lý: {'BẬT' if is_on else 'TẮT'}"
        self._log(msg)
        return {"success": ok, "blocked": bool(is_on) if ok else False, "message": msg}

    def toggle_privacy_curtain(self, is_on: bool) -> dict:
        """Enables or disables Privacy Curtain on the host."""
        from host_agent.privacy_curtain import privacy_curtain
        from host_agent.input_injector import InputInjector
        if is_on:
            res = privacy_curtain.enable()
            InputInjector.set_block_input(True)
        else:
            res = privacy_curtain.disable()
            InputInjector.set_block_input(False)
        self._config["privacy_curtain"] = bool(privacy_curtain.is_active)
        self._save_config()
        self._log(res.get("message", "Cập nhật Màn hình riêng tư"))
        return res

    def toggle_autostart(self, is_on: bool):
        ok, detail = _get_engine_for_current_platform().set_autostart(bool(is_on), config_path=self._config_path)
        if ok:
            self._log(f"{self.t('log_autostart_on' if is_on else 'log_autostart_off')} ({detail})")
        else:
            self._log(f"Autostart Error: {detail}")

    def install_user_tier(self) -> dict:
        ok, msg = install_user_tier(self._config_path)
        self._log(msg)
        return {"success": ok, "message": msg, "deployment": get_deployment_status()}

    def uninstall_user_tier(self) -> dict:
        ok, msg = uninstall_user_tier()
        self._log(msg)
        return {"success": ok, "message": msg, "deployment": get_deployment_status()}

    def install_admin_tier(self) -> dict:
        ok, msg = install_admin_tier(self._config_path)
        self._log(msg)
        return {"success": ok, "message": msg, "deployment": get_deployment_status()}

    def uninstall_admin_tier(self) -> dict:
        ok, msg = uninstall_admin_tier()
        self._log(msg)
        return {"success": ok, "message": msg, "deployment": get_deployment_status()}

    def get_deployment_info(self) -> dict:
        return get_deployment_status()

    def toggle_service(self, is_on: bool) -> dict:
        action = "install" if is_on else "uninstall"
        ok, msg = manage_windows_service(action)
        status_msg = f"Windows Service {action}: {msg}"
        self._log(status_msg)
        return {"success": ok, "message": msg, "installed": is_windows_service_installed()}

    def get_service_status(self) -> dict:
        return {"installed": is_windows_service_installed()}

    def toggle_keepawake(self, is_on: bool):
        self._config["keep_awake"] = bool(is_on)
        self._save_config()
        PowerManager.prevent_sleep(bool(is_on))
        state_str = "ON" if (is_on and self._lang == "en") else ("BẬT" if is_on else ("OFF" if self._lang == "en" else "TẮT"))
        self._log(self.t("log_keepawake", state=state_str))

    def toggle_open_on_boot(self, is_on: bool):
        self._config["open_on_boot"] = bool(is_on)
        self._config["start_minimized"] = not bool(is_on)
        self._save_config()
        state_str = "MỞ CỬA SỔ" if is_on else "THU NHỎ VÀO KHAY"
        self._log(f"Khởi động cùng Windows: {state_str}")

    def toggle_close_to_tray(self, is_on: bool):
        self._config["close_to_tray"] = bool(is_on)
        self._save_config()
        state_str = "THU NHỎ VÀO KHAY" if is_on else "THOÁT ỨNG DỤNG"
        self._log(f"Khi bấm nút đóng [X]: {state_str}")

    def toggle_show_tray(self, is_on: bool):
        self._config["show_tray_icon"] = bool(is_on)
        self._save_config()
        if self._tray_icon:
            try:
                self._tray_icon.visible = bool(is_on)
            except Exception:
                pass
        state_str = "HIỂN THỊ" if is_on else "ẨN (CHẠY NGẦM HOÀN TOÀN)"
        self._log(f"Khay hệ thống: {state_str}")

    def show_window(self):
        """Brings the GUI window to the foreground cross-platform."""
        self._resolve_hwnd()
        force_window_foreground(self._window, self._hwnd)

    def minimize_to_tray(self):
        if self._window:
            try:
                self._window.hide()
                self._log(self.t("log_minimized"))
            except Exception:
                pass

    def save_config(self, json_str: str):
        try:
            data = json.loads(json_str)
            if isinstance(data, dict):
                for k, v in data.items():
                    self._config[k] = v
                if "relay_url" in data:
                    self._config["relay"] = data["relay_url"]

                self._save_config()
                self._log(self.t("log_saved_relay"))
        except Exception as e:
            self._log(f"Config Save Error: {e}")

    def set_language(self, lang: str):
        if lang in ("vi", "en"):
            self._lang = lang
            self._config["lang"] = lang
            self._save_config()
            self._log(f"Switched language to {'Tiếng Việt' if lang == 'vi' else 'English'}")

class SingleInstanceLock:
    """System-wide single instance lock using Win32 Named Mutex on Windows and flock/lockfile on POSIX."""
    def __init__(self, name: str = "MeikovaRelayHost_AppMutex"):
        self.name = name
        self.mutex = None
        self.is_primary = False
        self._lock_file = None

    def acquire(self) -> bool:
        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes
                ERROR_ALREADY_EXISTS = 183
                kernel32 = ctypes.windll.kernel32
                kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
                kernel32.CreateMutexW.restype = wintypes.HANDLE
                self.mutex = kernel32.CreateMutexW(None, True, f"Local\\{self.name}")
                last_err = kernel32.GetLastError()
                if last_err == ERROR_ALREADY_EXISTS:
                    if self.mutex:
                        kernel32.CloseHandle(self.mutex)
                        self.mutex = None
                    self.is_primary = False
                    return False
                self.is_primary = True
                return True
            except Exception:
                pass

        try:
            lock_dir = _get_default_config_path().parent
            lock_dir.mkdir(parents=True, exist_ok=True)
            lock_path = lock_dir / f".{self.name}.lock"
            self._lock_file = open(lock_path, "w")
            if sys.platform == "win32":
                import msvcrt
                try:
                    msvcrt.locking(self._lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                    self.is_primary = True
                    return True
                except (IOError, OSError):
                    try:
                        self._lock_file.close()
                    except Exception:
                        pass
                    self._lock_file = None
                    self.is_primary = False
                    return False
            else:
                import fcntl
                try:
                    fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self.is_primary = True
                    return True
                except (IOError, OSError):
                    try:
                        self._lock_file.close()
                    except Exception:
                        pass
                    self._lock_file = None
                    self.is_primary = False
                    return False
        except Exception:
            return True

    def release(self):
        if sys.platform == "win32" and self.mutex:
            try:
                import ctypes
                ctypes.windll.kernel32.CloseHandle(self.mutex)
                self.mutex = None
            except Exception:
                pass
        if self._lock_file:
            try:
                self._lock_file.close()
                self._lock_file = None
            except Exception:
                pass

IPC_PORT = 48123

def send_ipc_command(cmd: str) -> Optional[str]:
    """Sends command to existing running instance on loopback port."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.5)
            s.connect(("127.0.0.1", IPC_PORT))
            s.sendall(cmd.encode("utf-8") + b"\n")
            return s.recv(4096).decode("utf-8").strip()
    except Exception:
        return None

def start_ipc_server(on_command_callback):
    """Starts background TCP listener on 127.0.0.1:IPC_PORT for single-instance control."""
    def _worker():
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("127.0.0.1", IPC_PORT))
            srv.listen(5)
            while True:
                conn, _ = srv.accept()
                try:
                    conn.settimeout(2.0)
                    line = conn.recv(1024).decode("utf-8").strip()
                    res = on_command_callback(line)
                    conn.sendall(str(res).encode("utf-8") + b"\n")
                except Exception:
                    pass
                finally:
                    conn.close()
        except Exception:
            pass
    threading.Thread(target=_worker, daemon=True).start()

def launch_webview_app(autostart: bool = False):
    if not HAS_WEBVIEW:
        raise ImportError("pywebview module is not installed.")

    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("MeikovaRelay.WorkstationHost.2.0")
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except Exception:
            pass

    html_file = find_resource("gui_view.html")
    if not html_file or not html_file.is_file():
        raise FileNotFoundError("gui_view.html not found in resource paths")

    html_content = html_file.read_text(encoding="utf-8")
    cfg_file = _get_default_config_path()
    config = _load_initial_config(cfg_file)

    api = HostApi(config, cfg_file)

    ico_path = find_resource("icon.ico")
    icon_str = str(ico_path) if (ico_path and ico_path.is_file()) else None

    window = webview.create_window(
        title="Meikova Relay Host",
        html=html_content,
        js_api=api,
        width=560,
        height=740,
        min_size=(460, 600),
        frameless=True,
        easy_drag=False,
        resizable=True,
        shadow=True,
        background_color="#070D17",
        hidden=autostart,
    )
    api.set_window(window)

    def on_shown():
        try:
            hwnd = api._resolve_hwnd()
            if hwnd:
                if ico_path and ico_path.is_file():
                    set_window_icon(hwnd, ico_path)
                if sys.platform == "win32":
                    try:
                        GWL_STYLE = -16
                        WS_MINIMIZEBOX = 0x00020000
                        WS_MAXIMIZEBOX = 0x00010000
                        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
                        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, style | WS_MINIMIZEBOX | WS_MAXIMIZEBOX)
                        apply_dark_titlebar(hwnd)
                        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0027)
                    except Exception:
                        pass
        except Exception:
            pass

    def on_loaded():
        threading.Thread(target=api.start_service, daemon=True).start()
        if autostart:
            open_on_boot = api._config.get("open_on_boot", False)
            if not open_on_boot and HAS_TRAY:
                api.minimize_to_tray()

    def on_closing():
        if api._is_quitting:
            return True
        close_to_tray = api._config.get("close_to_tray", True)
        if close_to_tray and HAS_TRAY:
            api.minimize_to_tray()
            return False
        api._is_quitting = True
        api.stop_service()
        return True

    window.events.shown += on_shown
    window.events.loaded += on_loaded
    window.events.closing += on_closing

    if HAS_TRAY:
        def tray_restore(icon=None, item=None):
            if window:
                api._resolve_hwnd()
                force_window_foreground(window, getattr(api, "_hwnd", None))

        def tray_copy(icon=None, item=None):
            api.copy_share_info()

        def tray_exit(icon=None, item=None):
            api._is_quitting = True
            safely_remove_tray_icon(api._tray_icon or icon)
            if window:
                try:
                    window.hide()
                except Exception:
                    pass
            try:
                api.stop_service()
            except Exception:
                pass
            if window:
                try:
                    window.destroy()
                except Exception:
                    pass
            os._exit(0)

        if build_tray_menu:
            tray_menu = build_tray_menu(api, tray_restore, tray_exit)
        else:
            tray_menu = pystray.Menu(
                pystray.MenuItem(api.t("tray_open"), tray_restore, default=True),
                pystray.MenuItem(api.t("tray_copy"), tray_copy),
                pystray.MenuItem(api.t("tray_exit"), tray_exit),
            )
        api._tray_icon = pystray.Icon("MeikovaRelayHost", get_tray_icon_image(), "Meikova Relay Host", tray_menu)
        api._tray_icon._thread = threading.current_thread()
        api._tray_icon._running = False

        show_tray = config.get("show_tray_icon", True)
        if "--no-tray" in sys.argv:
            show_tray = False
        elif "--tray" in sys.argv:
            show_tray = True

        def setup_tray(icon):
            ensure_interactive_desktop()
            icon.visible = bool(show_tray)

        def tray_worker():
            ensure_interactive_desktop()
            try:
                api._tray_icon.run(setup=setup_tray)
            except Exception as e:
                try:
                    with open(get_app_data_dir() / "tray.log", "a", encoding="utf-8") as f:
                        f.write(f"TRAY RUN ERROR: {e}\n")
                        import traceback
                        traceback.print_exc(file=f)
                except Exception:
                    pass

        threading.Thread(target=tray_worker, daemon=True).start()

    def handle_ipc(cmd: str) -> str:
        c = cmd.strip().upper()
        if c == "SHOW":
            api.show_window()
            return "OK:SHOWN"
        elif c == "STOP":
            api._is_quitting = True
            safely_remove_tray_icon(api._tray_icon)
            if window:
                try:
                    window.hide()
                except Exception:
                    pass
            try:
                api.stop_service()
            except Exception:
                pass
            if window:
                try:
                    window.destroy()
                except Exception:
                    pass
            sys.exit(0)
            return "OK:STOPPING"
        elif c == "STATUS":
            status = "RUNNING" if api._is_running else "STOPPED"
            room = api._config.get("room_id", "N/A")
            return f"OK:STATUS={status};ROOM={room}"
        return "ERR:UNKNOWN_COMMAND"

    start_ipc_server(handle_ipc)

    webview.start(
        debug=False,
        private_mode=True,
        icon=icon_str,
    )

def run_service_headless():
    """Runs the host service headless in background (for Windows Service or CLI daemon)."""
    cfg_file = _get_default_config_path()
    config = _load_initial_config(cfg_file)
    relay_url = config.get("relay") or config.get("relay_url") or "wss://meikova-relay.onrender.com"
    room_id = config.get("room_id") or generate_secure_room_id()
    pin = config.get("pin") or generate_secure_pin()
    account = config.get("account") or ""
    device_name = config.get("device_name") or os.environ.get("COMPUTERNAME", "Workstation")

    PowerManager.prevent_sleep(True)
    service = HostService(
        relay_url=relay_url,
        room_id=room_id,
        pin=pin,
        device_name=device_name,
        account=account, user_id=config.get("user_id")
    )
    chat_window = None
    if HostChatWindow:
        try:
            chat_window = HostChatWindow(
                on_send_reply=lambda text: service.send_chat_message(text),
                parent=None
            )
            service.on_chat_message = lambda sender, text: (
                chat_window.add_message(sender, text, is_local=False)
            )
        except Exception:
            chat_window = None

    def handle_headless_ipc(cmd: str) -> str:
        c = cmd.strip().upper()
        if c in ("CHAT", "OPEN_CHAT", "SHOW_CHAT"):
            if chat_window:
                chat_window.show()
                return "OK:CHAT_OPENED"
            return "ERR:NO_CHAT"
        elif c in ("HIDE_CHAT", "CLOSE_CHAT"):
            if chat_window:
                chat_window.hide()
                return "OK:CHAT_HIDDEN"
            return "ERR:NO_CHAT"
        elif c == "STOP":
            if service:
                service.stop()
            threading.Thread(target=lambda: (time.sleep(0.5), os._exit(0)), daemon=True).start()
            return "OK:STOPPING"
        elif c == "STATUS":
            status = "RUNNING" if (service and service.is_running) else "INITIALIZING"
            return f"OK:STATUS={status};ROOM={room_id};MODE=HEADLESS"
        elif c == "SHOW":
            if chat_window:
                chat_window.show()
                return "OK:CHAT_SHOWN"
            return "OK:HEADLESS_RUNNING"
        return "ERR:UNKNOWN_COMMAND"

    start_ipc_server(handle_headless_ipc)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(service.start())
    except (KeyboardInterrupt, SystemExit):
        pass
    except Exception as e:
        print(f"[ERROR] Service run error: {e}")

def main():
    ensure_interactive_desktop()

    # Handle post-update cleanup when relaunched via --updated
    if "--updated" in sys.argv:
        try:
            cleanup_post_update()
            threading.Thread(target=lambda: (time.sleep(2.0), cleanup_post_update()), daemon=True).start()
        except Exception:
            pass

    # Ensure %LOCALAPPDATA% deployment when run outside target directory
    if "--no-deploy" not in sys.argv and "--in-place" not in sys.argv:
        try:
            self_deploy_if_needed()
        except Exception:
            pass

    # Clean legacy junk files and registry keys unconditionally
    try:
        cleanup_legacy_source_files()
        clean_legacy_registry_keys()
        register_protocol_handler()
        register_firewall_rule()
    except Exception:
        pass

    # If running with Admin rights, configure SoftwareSASGeneration = 3 for remote unlock
    if sys.platform == "win32" and is_current_user_admin():
        try:
            from host_agent.input_injector import InputInjector
            InputInjector.configure_software_sas()
        except Exception:
            pass
    if sys.platform == "win32":
        try:
            if sys.stdout and hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            if sys.stderr and hasattr(sys.stderr, "reconfigure"):
                sys.stderr.reconfigure(encoding="utf-8", errors="replace")
            import ctypes
            if ctypes.windll.kernel32.AttachConsole(-1):
                if sys.stdout is None or not hasattr(sys.stdout, "write"):
                    sys.stdout = open("CONOUT$", "w", encoding="utf-8", errors="replace")
                if sys.stderr is None or not hasattr(sys.stderr, "write"):
                    sys.stderr = open("CONOUT$", "w", encoding="utf-8", errors="replace")
        except Exception:
            pass

    if "--chat" in sys.argv or "--open-chat" in sys.argv:
        resp = send_ipc_command("CHAT")
        if resp and resp.startswith("OK"):
            print("[OK] Đã mở cửa sổ chat trên máy trạm.")
            sys.exit(0)
        else:
            print("[INFO] Máy trạm đang offline hoặc chưa bật dịch vụ.")
            sys.exit(1)

    if "--help" in sys.argv or "-h" in sys.argv:
        from host_agent.host_service import build_cli_parser
        parser = build_cli_parser()
        parser.print_help()
        sys.exit(0)

    cfg_file = _get_default_config_path()
    initial_config = _load_initial_config(cfg_file)

    # Apply direct CLI parameter overrides (--relay, --room, --pin, --fps, --uncapped, --stealth, --admin, etc.)
    argv = sys.argv[1:]
    cli_dirty = False
    for arg in argv:
        if arg.startswith("meikova-relay://") or arg.startswith("meikova-relay:"):
            try:
                from urllib.parse import urlparse, parse_qs
                parsed = urlparse(arg)
                raw_query = parsed.query if parsed.query else (parsed.path.split("?", 1)[-1] if "?" in parsed.path else "")
                qs = parse_qs(raw_query)
                for k, v in qs.items():
                    if v and isinstance(v, list):
                        initial_config[k] = v[0]
                cli_dirty = True
            except Exception:
                pass
    for idx, arg in enumerate(argv):
        nxt = argv[idx + 1] if idx + 1 < len(argv) and not argv[idx + 1].startswith("--") else ""
        if arg == "--relay" and nxt:
            initial_config["relay"] = nxt
            cli_dirty = True
        elif arg == "--room" and nxt:
            initial_config["room_id"] = nxt
            cli_dirty = True
        elif arg in ("--pin", "--perm-pin") and nxt:
            initial_config["pin"] = nxt
            initial_config["perm_pin"] = nxt
            cli_dirty = True
        elif arg == "--name" and nxt:
            initial_config["device_name"] = nxt
            cli_dirty = True
        elif arg == "--account" and nxt:
            initial_config["account"] = nxt
            cli_dirty = True
        elif arg == "--fps" and nxt:
            try:
                initial_config["fps"] = int(nxt)
                cli_dirty = True
            except ValueError:
                pass
        elif arg == "--uncapped":
            initial_config["fps"] = 0
            cli_dirty = True
        elif arg == "--stealth":
            initial_config["stealth_mode"] = True
            initial_config["show_tray_icon"] = False
            cli_dirty = True
        elif arg == "--keep-awake":
            initial_config["keep_awake"] = True
            cli_dirty = True
        elif arg == "--no-keep-awake":
            initial_config["keep_awake"] = False
            cli_dirty = True
        elif arg == "--auto-wakeup" and nxt:
            initial_config["auto_wakeup"] = True
            initial_config["auto_wakeup_time"] = nxt
            cli_dirty = True
        elif arg == "--block-input":
            initial_config["block_input"] = True
            cli_dirty = True
        elif arg == "--curtain":
            initial_config["privacy_curtain"] = True
            cli_dirty = True
        elif arg == "--admin":
            initial_config["admin_elevated"] = True
            cli_dirty = True
    if cli_dirty:
        try:
            with open(cfg_file, "w", encoding="utf-8") as f:
                json.dump(initial_config, f, indent=2)
        except Exception:
            pass

    # Start auto-update polling loop if enabled
    if initial_config.get("auto_update", True):
        relay_target = initial_config.get("relay") or initial_config.get("relay_url")
        if relay_target:
            try:
                start_auto_update_loop(relay_target, APP_VERSION)
            except Exception:
                pass

    # Tắt chế độ headless mặc định theo yêu cầu người dùng.
    # Chỉ chạy headless khi có cờ CLI chỉ định rõ ràng (--headless hoặc --service-headless).
    if (
        ("--headless" in sys.argv or "--service-headless" in sys.argv) and
        "--gui" not in sys.argv and
        "--window" not in sys.argv
    ):
        run_service_headless()
        return

    if "--version" in sys.argv or "-v" in sys.argv:
        print(f"Meikova Relay Host v{APP_VERSION}")
        sys.exit(0)

    if "--restart" in sys.argv or "--reload" in sys.argv:
        send_ipc_command("STOP")
        time.sleep(0.6)

    if "--stop" in sys.argv or "--quit" in sys.argv:
        resp = send_ipc_command("STOP")
        if resp:
            print(f"[OK] Đã gửi lệnh dừng tiến trình: {resp}")
            sys.exit(0)
        else:
            print("[INFO] Không có tiến trình máy trạm nào đang chạy.")
            sys.exit(0)

    if "--status" in sys.argv:
        resp = send_ipc_command("STATUS")
        if resp:
            print(f"[OK] Trạng thái máy trạm: {resp}")
            sys.exit(0)
        else:
            print("[INFO] Máy trạm đang dừng (offline).")
            sys.exit(0)

    # System-wide single instance check (Named Mutex / lockfile)
    global _single_instance_lock
    _single_instance_lock = SingleInstanceLock("MeikovaRelayHost_AppMutex")
    if not _single_instance_lock.acquire():
        # Another instance is already running or initializing. Try IPC SHOW command with retry.
        for _ in range(15):
            resp = send_ipc_command("SHOW")
            if resp:
                break
            time.sleep(0.2)
        print("[INFO] Meikova Relay Host đã đang chạy. Đã kích hoạt mở cửa sổ quản lý.")
        sys.exit(0)

    if "--install-user" in sys.argv:
        ok, msg = install_user_tier()
        print(f"[{'OK' if ok else 'FAIL'}] {msg}")
        sys.exit(0 if ok else 1)

    if "--uninstall-user" in sys.argv:
        ok, msg = uninstall_user_tier()
        print(f"[{'OK' if ok else 'FAIL'}] {msg}")
        sys.exit(0 if ok else 1)

    if "--install-admin" in sys.argv or "--install-service" in sys.argv:
        ok, msg = install_admin_tier()
        print(f"[{'OK' if ok else 'FAIL'}] {msg}")
        sys.exit(0 if ok else 1)

    if "--uninstall-admin" in sys.argv or "--uninstall-service" in sys.argv:
        ok, msg = uninstall_admin_tier()
        print(f"[{'OK' if ok else 'FAIL'}] {msg}")
        sys.exit(0 if ok else 1)

    autostart = "--autostart" in sys.argv
    if "--legacy-tk" in sys.argv or not HAS_WEBVIEW:
        root = tk.Tk()
        app = MeikovaRelayHostGUI(root)
        def handle_tk_ipc(cmd: str) -> str:
            c = cmd.strip().upper()
            if c == "SHOW":
                root.after(0, app._show_window)
                return "OK:SHOWN"
            elif c == "STOP":
                root.after(0, app._exit_application)
                return "OK:STOPPING"
            elif c == "STATUS":
                status = "RUNNING" if app.is_running else "STOPPED"
                room = app.config.get("room_id", "N/A")
                return f"OK:STATUS={status};ROOM={room}"
            return "ERR:UNKNOWN_COMMAND"
        start_ipc_server(handle_tk_ipc)
        root.after(100, app._start_service)
        if autostart:
            if HAS_TRAY:
                root.after(200, app._minimize_to_tray)
            else:
                root.after(200, root.withdraw)
        root.mainloop()
        return

    try:
        launch_webview_app(autostart=autostart)
    except Exception as e:
        try:
            with open(get_app_data_dir() / "gui.log", "a", encoding="utf-8") as f:
                import traceback
                f.write(f"WebView2 launch failed at {time.strftime('%Y-%m-%d %H:%M:%S')}: {e}\n")
                traceback.print_exc(file=f)
        except Exception:
            pass
        print(f"[WARN] WebView2 launch failed ({e}), falling back to Tkinter GUI.")
        root = tk.Tk()
        app = MeikovaRelayHostGUI(root)
        def handle_tk_fallback_ipc(cmd: str) -> str:
            c = cmd.strip().upper()
            if c == "SHOW":
                root.after(0, app._show_window)
                return "OK:SHOWN"
            elif c == "STOP":
                root.after(0, app._exit_application)
                return "OK:STOPPING"
            elif c == "STATUS":
                status = "RUNNING" if app.is_running else "STOPPED"
                room = app.config.get("room_id", "N/A")
                return f"OK:STATUS={status};ROOM={room}"
            return "ERR:UNKNOWN_COMMAND"
        start_ipc_server(handle_tk_fallback_ipc)
        root.after(100, app._start_service)
        if autostart:
            if HAS_TRAY:
                root.after(200, app._minimize_to_tray)
            else:
                root.after(200, root.withdraw)
        root.mainloop()

if __name__ == "__main__":
    multiprocessing.freeze_support()
    try:
        main()
    except Exception as e:
        try:
            import traceback
            crash_log = get_app_data_dir() / "crash.log"
            with open(crash_log, "a", encoding="utf-8") as f:
                f.write(f"\n--- CRASH AT {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                traceback.print_exc(file=f)
        except Exception:
            pass
        raise


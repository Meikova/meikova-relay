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
import tkinter as tk
from tkinter import messagebox
import random
import string
from pathlib import Path
from typing import Optional
import multiprocessing
multiprocessing.freeze_support()

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

def promote_tray_icon():
    """Promotes TitanRemoteHost tray icon to be permanently pinned to the Windows taskbar."""
    if sys.platform == "win32" and winreg:
        try:
            root_key = winreg.HKEY_CURRENT_USER
            sub_key = r"Control Panel\NotifyIconSettings"
            with winreg.OpenKey(root_key, sub_key) as k:
                i = 0
                while True:
                    try:
                        child = winreg.EnumKey(k, i)
                        i += 1
                        with winreg.OpenKey(k, child, 0, winreg.KEY_READ | winreg.KEY_WRITE) as ck:
                            try:
                                exe_path, _ = winreg.QueryValueEx(ck, "ExecutablePath")
                                if "titanremotehost" in exe_path.lower():
                                    winreg.SetValueEx(ck, "IsPromoted", 0, winreg.REG_DWORD, 1)
                            except Exception:
                                pass
                    except OSError:
                        break
        except Exception:
            pass

ensure_interactive_desktop()
promote_tray_icon()

# Ensure package is resolvable
current_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(current_dir.parent))

try:
    from host_agent.host_service import HostService
    from host_agent.power_manager import PowerManager
    from host_agent.deployment_manager import (
        ensure_permanent_deployment,
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
except ModuleNotFoundError:
    from host_service import HostService
    from power_manager import PowerManager
    from deployment_manager import (
        ensure_permanent_deployment,
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

# Optional System Tray Support via pystray & PIL
try:
    import pystray
    from PIL import Image, ImageDraw
    HAS_TRAY = True
    try:
        with open(Path.home() / ".titan_tray.log", "w", encoding="utf-8") as f:
            f.write(f"HAS_TRAY SUCCESS: {pystray}\n")
    except Exception:
        pass
except Exception as e:
    HAS_TRAY = False
    try:
        with open(Path.home() / ".titan_tray.log", "w", encoding="utf-8") as f:
            import traceback
            f.write(f"HAS_TRAY FAILED: {e}\n")
            traceback.print_exc(file=f)
    except Exception:
        pass

# Optional Microsoft Edge WebView2 GUI Support via pywebview
try:
    import webview
    HAS_WEBVIEW = True
except Exception:
    HAS_WEBVIEW = False

def get_tray_icon_image():
    """Returns unified brand icon:
    Black squircle (#070D17), green infinity (#22C55E), and white dot (#FFFFFF).
    """
    if not HAS_TRAY:
        return None
    try:
        base_dirs = [
            current_dir,
            Path(__file__).resolve().parent,
            Path(getattr(sys, "_MEIPASS", current_dir)),
            Path(getattr(sys, "_MEIPASS", current_dir)) / "host_agent",
        ]
        for b in base_dirs:
            candidate = b / "tray_icon.png"
            if candidate.is_file():
                return Image.open(candidate)
    except Exception:
        pass

    try:
        size = 256
        s = size / 32.0
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        # 1. Nền đen squircle (#070D17, rx=7 on 32 scale)
        rx = int(7 * s)
        d.rounded_rectangle((0, 0, size, size), radius=rx, fill="#070D17")

        def bpt(p0, p1, p2, p3, u):
            u1 = 1.0 - u
            return (
                u1**3 * p0[0] + 3 * u1**2 * u * p1[0] + 3 * u1 * u**2 * p2[0] + u**3 * p3[0],
                u1**3 * p0[1] + 3 * u1**2 * u * p1[1] + 3 * u1 * u**2 * p2[1] + u**3 * p3[1]
            )

        segs = [
            ((16*s, 16*s), (19.5*s, 10.5*s), (27*s, 10.5*s), (27*s, 16*s)),
            ((27*s, 16*s), (27*s, 21.5*s), (19.5*s, 21.5*s), (16*s, 16*s)),
            ((16*s, 16*s), (12.5*s, 10.5*s), (5*s, 10.5*s), (5*s, 16*s)),
            ((5*s, 16*s), (5*s, 21.5*s), (12.5*s, 21.5*s), (16*s, 16*s)),
        ]
        points = []
        for p0, p1, p2, p3 in segs:
            for i in range(240):
                points.append(bpt(p0, p1, p2, p3, i / 240.0))

        # 2. Vô cực màu xanh
        w = int(2.8 * s)
        for i in range(len(points)):
            p1 = points[i]
            p2 = points[(i + 1) % len(points)]
            d.line([p1, p2], fill="#22C55E", width=w)

        r_cap = w / 2.0
        for x, y in points[::10]:
            d.ellipse([x - r_cap, y - r_cap, x + r_cap, y + r_cap], fill="#22C55E")

        # 3. Chấm trắng tại (23.2, 12.4)
        cx, cy = 23.2 * s, 12.4 * s
        cr = 2.1 * s
        d.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill="#FFFFFF")

        return img.resize((32, 32), Image.Resampling.LANCZOS)
    except Exception:
        fallback = Image.new("RGBA", (32, 32), (7, 13, 23, 255))
        d = ImageDraw.Draw(fallback)
        d.ellipse([4, 4, 28, 28], outline="#22C55E", width=3)
        d.ellipse([21, 10, 25, 14], fill="#FFFFFF")
        return fallback

REG_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_REG_NAME = "TitanRemoteHost"

# Studio-grade dark ambient color tokens (/ambient-instrument-ui)
COLORS = {
    "bg_main": "#070D17",         # Deep ambient ink-0
    "bg_panel": "#0B1322",        # Surface ink-1
    "bg_card": "#101B2E",         # Card ink-2
    "bg_card_inner": "#0A111E",   # Inner chamber
    "line": "#1C2D4A",            # Hairline border
    "line_hover": "#2B436D",      # Focused border
    "text_main": "#F8FAFC",       # High contrast white
    "text_muted": "#64748B",      # Studio muted gray
    "text_sub": "#94A3B8",        # Monospace/secondary label
    "accent_green": "#22C55E",    # Emerald beacon
    "accent_green_bg": "#082315", # Dark emerald chip
    "accent_green_line": "#15803D", # Emerald border
    "accent_cyan": "#38BDF8",     # Cyan telemetry
    "accent_cyan_bg": "#0A2238",  # Dark cyan chip
    "accent_red": "#EF4444",      # Crimson alert
    "accent_red_bg": "#1F1015",   # Dark crimson chip
    "accent_amber": "#F59E0B",    # Amber warning
    "accent_amber_bg": "#261908", # Dark amber chip
    "btn_surface": "#142138",     # Pill button surface
    "btn_surface_hover": "#1C2F50"# Pill button hover
}

# Master bilingual translation dictionary (VI / EN)
# ponytail: Clean stdlib dictionary; zero external dependencies.
TRANSLATIONS = {
    "vi": {
        "app_title": "Titan Remote Host - Điều Khiển Máy Trạm",
        "header_title": "TITAN REMOTE HOST",
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
        "tray_open": "Mở Titan Remote",
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
        "share_header": "--- TITAN REMOTE // KẾT NỐI HỖ TRỢ TỪ XA ---",
        "share_dashboard": "Trang điều khiển:",
        "share_room": "Mã phòng (Room ID):",
        "share_pin": "Mật khẩu (PIN):",
    },
    "en": {
        "app_title": "Titan Remote Host - Workstation Control",
        "header_title": "TITAN REMOTE HOST",
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
        "tray_open": "Open Titan Remote",
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
        "share_header": "--- TITAN REMOTE // REMOTE ASSIST CONNECTION ---",
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

    # 2. LocalAppData on Windows, ~/.titan-remote on Unix
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            candidates.append(Path(local_app_data) / "TitanRemoteHost" / "config.json")
    else:
        candidates.append(Path.home() / ".titan-remote" / "config.json")

    # 3. Current Working Directory
    candidates.append(Path.cwd() / "config.json")

    # 4. Script directory (for python gui_agent.py)
    candidates.append(Path(__file__).resolve().parent / "config.json")

    # 5. User profile fallback
    candidates.append(Path.home() / ".titan_remote_config.json")

    for c in candidates:
        if c.exists() and c.is_file():
            return c

    # Default location for writing if none exists
    if sys.platform == "win32" and os.environ.get("LOCALAPPDATA"):
        target = Path(os.environ["LOCALAPPDATA"]) / "TitanRemoteHost" / "config.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        return target
    return Path.home() / ".titan_remote_config.json"

class TitanHostGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.geometry("540x720")
        self.root.minsize(500, 660)
        self.root.configure(bg=COLORS["bg_main"])

        self.service_thread: Optional[threading.Thread] = None
        self.host_service: Optional[HostService] = None
        self.is_running = False
        self.current_tab = "ultra"  # "ultra" | "chrome" | "settings"
        self.connected_client_info: Optional[str] = None
        self.tray_icon = None

        # Windows taskbar grouping AppUserModelID for custom icon display
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TitanRemote.WorkstationHost.2.0")
        except Exception:
            pass

        self._load_config()
        self.root.title(self.t("app_title"))
        self._setup_window_icon()
        self._build_ui()
        self._check_autostart_status()
        self._init_system_tray()

        # Handle window close (X button)
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)

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
                from PIL import ImageTk
                self._app_icon_img = ImageTk.PhotoImage(file=str(png_path))
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
        default_comp = os.environ.get("COMPUTERNAME", socket.gethostname())
        self.config = {
            "relay": "wss://titan-remote.onrender.com",
            "account": "",
            "device_name": default_comp,
            "room_id": f"RD-{random.randint(1000, 9999)}",
            "pin": f"{random.randint(100000, 999999)}",
            "keep_awake": True,
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
    # UI CONSTRUCTION (/ambient-instrument-ui)
    # -------------------------------------------------------------
    def _build_ui(self):
        # 1. Header & Studio Telemetry
        header = tk.Frame(self.root, bg=COLORS["bg_main"], pady=14, padx=22)
        header.pack(fill="x")

        title_row = tk.Frame(header, bg=COLORS["bg_main"])
        title_row.pack(fill="x")

        self.lbl_header_title = tk.Label(
            title_row,
            text=self.t("header_title"),
            font=("Segoe UI", 15, "bold"),
            fg=COLORS["text_main"],
            bg=COLORS["bg_main"]
        )
        self.lbl_header_title.pack(side="left")

        # Right header controls (Language switcher + Status pill)
        right_header = tk.Frame(title_row, bg=COLORS["bg_main"])
        right_header.pack(side="right")

        # Language Switcher Pill Box
        lang_box = tk.Frame(right_header, bg=COLORS["bg_card"], padx=2, pady=2, highlightthickness=1, highlightbackground=COLORS["line"])
        lang_box.pack(side="right", padx=(8, 0))

        self.btn_lang_vi = tk.Button(
            lang_box,
            text="VI",
            font=("Segoe UI", 7, "bold"),
            bg=COLORS["accent_cyan"] if self.lang == "vi" else COLORS["bg_card"],
            fg=COLORS["bg_main"] if self.lang == "vi" else COLORS["text_muted"],
            activebackground=COLORS["accent_cyan"],
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
            font=("Segoe UI", 7, "bold"),
            bg=COLORS["accent_cyan"] if self.lang == "en" else COLORS["bg_card"],
            fg=COLORS["bg_main"] if self.lang == "en" else COLORS["text_muted"],
            activebackground=COLORS["accent_cyan"],
            activeforeground=COLORS["bg_main"],
            relief="flat",
            bd=0,
            padx=7,
            pady=2,
            cursor="hand2",
            command=lambda: self._set_language("en")
        )
        self.btn_lang_en.pack(side="left")

        self.status_pill = tk.Label(
            right_header,
            text=self.t("status_stopped"),
            font=("Segoe UI", 8, "bold"),
            fg=COLORS["accent_red"],
            bg=COLORS["accent_red_bg"],
            padx=10,
            pady=3,
            relief="solid",
            bd=1,
            highlightthickness=0
        )
        self.status_pill.pack(side="right")

        comp_name = os.environ.get("COMPUTERNAME", "Workstation")
        self.lbl_header_subtitle = tk.Label(
            header,
            text=self.t("workstation_fmt", name=comp_name),
            font=("Consolas", 8),
            fg=COLORS["text_muted"],
            bg=COLORS["bg_main"]
        )
        self.lbl_header_subtitle.pack(anchor="w", pady=(3, 0))

        # 2. Segmented Mode Switcher (Pill tabs)
        seg_container = tk.Frame(self.root, bg=COLORS["bg_main"], padx=22)
        seg_container.pack(fill="x", pady=(0, 10))

        seg_frame = tk.Frame(seg_container, bg=COLORS["bg_panel"], padx=3, pady=3, highlightthickness=1, highlightbackground=COLORS["line"])
        seg_frame.pack(fill="x")

        self.btn_tab_ultra = tk.Button(
            seg_frame,
            text=self.t("tab_ultra"),
            font=("Segoe UI", 8, "bold"),
            bg=COLORS["accent_green"],
            fg=COLORS["bg_main"],
            activebackground="#16A34A",
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
            font=("Segoe UI", 8, "bold"),
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
            font=("Segoe UI", 8, "bold"),
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

        # 3. Main Content Container
        self.content_container = tk.Frame(self.root, bg=COLORS["bg_main"], padx=22)
        self.content_container.pack(fill="both", expand=True)

        # Build individual panels
        self.panel_ultra = tk.Frame(self.content_container, bg=COLORS["bg_panel"], padx=18, pady=18, highlightthickness=1, highlightbackground=COLORS["line"])
        self.panel_chrome = tk.Frame(self.content_container, bg=COLORS["bg_panel"], padx=18, pady=18, highlightthickness=1, highlightbackground=COLORS["line"])
        self.panel_settings = tk.Frame(self.content_container, bg=COLORS["bg_panel"], padx=18, pady=18, highlightthickness=1, highlightbackground=COLORS["line"])

        self._build_ultra_panel()
        self._build_chrome_panel()
        self._build_settings_panel()

        # Show default tab
        self._switch_tab("ultra")

        # 4. Master Control Strip (Bottom)
        bottom_frame = tk.Frame(self.root, bg=COLORS["bg_main"], pady=14, padx=22)
        bottom_frame.pack(fill="x")

        self.btn_master_toggle = tk.Button(
            bottom_frame,
            text=self.t("btn_start_service"),
            font=("Segoe UI", 10, "bold"),
            bg=COLORS["accent_green"],
            fg=COLORS["bg_main"],
            activebackground="#16A34A",
            activeforeground=COLORS["bg_main"],
            relief="flat",
            bd=0,
            pady=12,
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
            font=("Segoe UI", 10, "bold"),
            fg=COLORS["text_main"],
            bg=COLORS["bg_panel"]
        )
        self.lbl_ultra_title.pack(anchor="w")

        self.lbl_ultra_desc = tk.Label(
            self.panel_ultra,
            text=self.t("ultra_desc"),
            font=("Segoe UI", 8),
            fg=COLORS["text_muted"],
            bg=COLORS["bg_panel"]
        )
        self.lbl_ultra_desc.pack(anchor="w", pady=(2, 12))

        # ID Card
        id_card = tk.Frame(self.panel_ultra, bg=COLORS["bg_card"], padx=14, pady=12, highlightthickness=1, highlightbackground=COLORS["line"])
        id_card.pack(fill="x", pady=4)

        self.lbl_room_tag = tk.Label(id_card, text=self.t("room_id_label"), font=("Consolas", 8, "bold"), fg=COLORS["accent_cyan"], bg=COLORS["bg_card"])
        self.lbl_room_tag.pack(anchor="w")

        id_row = tk.Frame(id_card, bg=COLORS["bg_card"])
        id_row.pack(fill="x", pady=(6, 0))

        self.room_var = tk.StringVar(value=self.config.get("room_id", "RD-8888"))
        self.lbl_room_display = tk.Label(
            id_row,
            textvariable=self.room_var,
            font=("Consolas", 20, "bold"),
            fg=COLORS["text_main"],
            bg=COLORS["bg_card"]
        )
        self.lbl_room_display.pack(side="left")

        btn_box1 = tk.Frame(id_row, bg=COLORS["bg_card"])
        btn_box1.pack(side="right")

        self.btn_renew_room = tk.Button(
            btn_box1,
            text=self.t("btn_renew_room"),
            font=("Segoe UI", 8, "bold"),
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
            font=("Segoe UI", 8, "bold"),
            bg=COLORS["btn_surface"],
            fg=COLORS["accent_cyan"],
            activebackground=COLORS["btn_surface_hover"],
            activeforeground=COLORS["accent_cyan"],
            relief="flat",
            bd=0,
            padx=12,
            pady=4,
            cursor="hand2",
            command=lambda: self._copy_to_clip(self.room_var.get().strip(), "Room ID")
        )
        self.btn_copy_room.pack(side="right")

        # PIN Card
        pin_card = tk.Frame(self.panel_ultra, bg=COLORS["bg_card"], padx=14, pady=12, highlightthickness=1, highlightbackground=COLORS["line"])
        pin_card.pack(fill="x", pady=6)

        self.lbl_pin_tag = tk.Label(pin_card, text=self.t("pin_label"), font=("Consolas", 8, "bold"), fg=COLORS["accent_green"], bg=COLORS["bg_card"])
        self.lbl_pin_tag.pack(anchor="w")

        pin_row = tk.Frame(pin_card, bg=COLORS["bg_card"])
        pin_row.pack(fill="x", pady=(6, 0))

        self.pin_var = tk.StringVar(value=self.config.get("pin", "123456"))
        self.lbl_pin_display = tk.Label(
            pin_row,
            textvariable=self.pin_var,
            font=("Consolas", 20, "bold"),
            fg=COLORS["accent_green"],
            bg=COLORS["bg_card"]
        )
        self.lbl_pin_display.pack(side="left")

        btn_box2 = tk.Frame(pin_row, bg=COLORS["bg_card"])
        btn_box2.pack(side="right")

        self.btn_renew_pin = tk.Button(
            btn_box2,
            text=self.t("btn_renew_pin"),
            font=("Segoe UI", 8, "bold"),
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
            font=("Segoe UI", 8, "bold"),
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
            font=("Segoe UI", 9, "bold"),
            bg=COLORS["btn_surface"],
            fg=COLORS["accent_cyan"],
            activebackground=COLORS["btn_surface_hover"],
            activeforeground=COLORS["text_main"],
            relief="flat",
            bd=0,
            pady=10,
            cursor="hand2",
            command=self._copy_share_info
        )
        self.btn_share.pack(fill="x", pady=(12, 6))

        # Active Session Live Notification Banner
        self.active_session_card = tk.Frame(self.panel_ultra, bg=COLORS["bg_card_inner"], padx=12, pady=10, highlightthickness=1, highlightbackground=COLORS["line"])
        self.active_session_label = tk.Label(
            self.active_session_card,
            text=self.t("session_waiting"),
            font=("Segoe UI", 8, "bold"),
            fg=COLORS["accent_green"],
            bg=COLORS["bg_card_inner"]
        )
        self.active_session_label.pack(side="left")

        self.btn_disconnect_client = tk.Button(
            self.active_session_card,
            text=self.t("btn_disconnect"),
            font=("Segoe UI", 7, "bold"),
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
        self.active_session_card.pack(fill="x", pady=(6, 0))

    # -------------------------------------------------------------
    # PANEL 2: UNATTENDED / BACKGROUND ACCESS
    # -------------------------------------------------------------
    def _build_chrome_panel(self):
        self.lbl_chrome_title = tk.Label(
            self.panel_chrome,
            text=self.t("chrome_title"),
            font=("Segoe UI", 10, "bold"),
            fg=COLORS["text_main"],
            bg=COLORS["bg_panel"]
        )
        self.lbl_chrome_title.pack(anchor="w")

        self.lbl_chrome_desc = tk.Label(
            self.panel_chrome,
            text=self.t("chrome_desc"),
            font=("Segoe UI", 8),
            fg=COLORS["text_muted"],
            bg=COLORS["bg_panel"],
            wraplength=460,
            justify="left"
        )
        self.lbl_chrome_desc.pack(anchor="w", pady=(2, 10))

        self.account_var = tk.StringVar(value=self.config.get("account", ""))
        self.name_var = tk.StringVar(value=self.config.get("device_name", os.environ.get("COMPUTERNAME", "Workstation")))

        card = tk.Frame(self.panel_chrome, bg=COLORS["bg_card"], padx=14, pady=12, highlightthickness=1, highlightbackground=COLORS["line"])
        card.pack(fill="x", pady=(0, 8))

        self.lbl_account = tk.Label(card, text=self.t("account_label"), font=("Segoe UI", 8, "bold"), fg=COLORS["text_sub"], bg=COLORS["bg_card"])
        self.lbl_account.pack(anchor="w", pady=(2, 2))
        entry_account = tk.Entry(
            card,
            textvariable=self.account_var,
            font=("Consolas", 9),
            bg=COLORS["bg_card_inner"],
            fg=COLORS["text_main"],
            insertbackground=COLORS["accent_cyan"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            highlightcolor=COLORS["accent_cyan"]
        )
        entry_account.pack(fill="x", ipady=4, pady=(0, 6))

        self.lbl_device_name = tk.Label(card, text=self.t("device_name_label"), font=("Segoe UI", 8, "bold"), fg=COLORS["text_sub"], bg=COLORS["bg_card"])
        self.lbl_device_name.pack(anchor="w", pady=(2, 2))
        entry_name = tk.Entry(
            card,
            textvariable=self.name_var,
            font=("Consolas", 9),
            bg=COLORS["bg_card_inner"],
            fg=COLORS["text_main"],
            insertbackground=COLORS["accent_cyan"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            highlightcolor=COLORS["accent_cyan"]
        )
        entry_name.pack(fill="x", ipady=4, pady=(0, 6))

        self.lbl_perm_pin = tk.Label(card, text=self.t("perm_pin_label"), font=("Segoe UI", 8, "bold"), fg=COLORS["text_sub"], bg=COLORS["bg_card"])
        self.lbl_perm_pin.pack(anchor="w", pady=(2, 2))
        entry_pin = tk.Entry(
            card,
            textvariable=self.pin_var,
            font=("Consolas", 10, "bold"),
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

        # Checkboxes Card
        chk_card = tk.Frame(self.panel_chrome, bg=COLORS["bg_card"], padx=14, pady=10, highlightthickness=1, highlightbackground=COLORS["line"])
        chk_card.pack(fill="x", pady=(0, 8))

        self.autostart_var = tk.BooleanVar(value=False)
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
            font=("Segoe UI", 8)
        )
        self.chk_autostart.pack(anchor="w", pady=2)

        self.keepawake_var = tk.BooleanVar(value=self.config.get("keep_awake", True))
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
            font=("Segoe UI", 8)
        )
        self.chk_keepawake.pack(anchor="w", pady=2)

        # Minimize to tray button
        self.btn_minimize_tray = tk.Button(
            self.panel_chrome,
            text=self.t("btn_minimize_tray"),
            font=("Segoe UI", 8, "bold"),
            bg=COLORS["btn_surface"],
            fg=COLORS["text_sub"],
            activebackground=COLORS["btn_surface_hover"],
            activeforeground=COLORS["text_main"],
            relief="flat",
            bd=0,
            pady=8,
            cursor="hand2",
            command=self._minimize_to_tray
        )
        self.btn_minimize_tray.pack(fill="x", pady=(4, 0))

    # -------------------------------------------------------------
    # PANEL 3: SETTINGS & LIVE LOGS
    # -------------------------------------------------------------
    def _build_settings_panel(self):
        card = tk.Frame(self.panel_settings, bg=COLORS["bg_card"], padx=14, pady=12, highlightthickness=1, highlightbackground=COLORS["line"])
        card.pack(fill="x", pady=(0, 10))

        self.lbl_relay = tk.Label(card, text=self.t("relay_label"), font=("Segoe UI", 8, "bold"), fg=COLORS["text_sub"], bg=COLORS["bg_card"])
        self.lbl_relay.pack(anchor="w", pady=(0, 4))

        relay_row = tk.Frame(card, bg=COLORS["bg_card"])
        relay_row.pack(fill="x")

        self.relay_var = tk.StringVar(value=self.config.get("relay", "wss://titan-remote.onrender.com"))
        entry_relay = tk.Entry(
            relay_row,
            textvariable=self.relay_var,
            font=("Consolas", 9),
            bg=COLORS["bg_card_inner"],
            fg=COLORS["text_main"],
            insertbackground=COLORS["accent_cyan"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=COLORS["line"],
            highlightcolor=COLORS["accent_cyan"]
        )
        entry_relay.pack(side="left", fill="x", expand=True, ipady=4)

        self.btn_save_settings = tk.Button(
            relay_row,
            text=self.t("btn_save_settings"),
            font=("Segoe UI", 8, "bold"),
            bg=COLORS["btn_surface"],
            fg=COLORS["accent_cyan"],
            activebackground=COLORS["btn_surface_hover"],
            activeforeground=COLORS["accent_cyan"],
            relief="flat",
            bd=0,
            padx=12,
            pady=4,
            cursor="hand2",
            command=self._save_settings_click
        )
        self.btn_save_settings.pack(side="right", padx=(8, 0))

        # Activity Log Card
        log_card = tk.Frame(self.panel_settings, bg=COLORS["bg_card"], padx=14, pady=12, highlightthickness=1, highlightbackground=COLORS["line"])
        log_card.pack(fill="both", expand=True)

        self.lbl_log_title = tk.Label(log_card, text=self.t("log_title"), font=("Segoe UI", 8, "bold"), fg=COLORS["text_sub"], bg=COLORS["bg_card"])
        self.lbl_log_title.pack(anchor="w", pady=(0, 6))

        self.log_text = tk.Text(
            log_card,
            bg=COLORS["bg_card_inner"],
            fg=COLORS["text_sub"],
            insertbackground=COLORS["accent_green"],
            font=("Consolas", 8),
            relief="flat",
            height=10,
            wrap="word",
            state="disabled",
            highlightthickness=1,
            highlightbackground=COLORS["line"]
        )
        self.log_text.pack(fill="both", expand=True)

    # -------------------------------------------------------------
    # TAB SWITCHING
    # -------------------------------------------------------------
    def _switch_tab(self, tab: str):
        self.current_tab = tab
        self.panel_ultra.pack_forget()
        self.panel_chrome.pack_forget()
        self.panel_settings.pack_forget()

        # Update button styles
        for btn, name in [(self.btn_tab_ultra, "ultra"), (self.btn_tab_chrome, "chrome"), (self.btn_tab_cfg, "settings")]:
            if name == tab:
                btn.config(bg=COLORS["accent_green"], fg=COLORS["bg_main"], activebackground="#16A34A", activeforeground=COLORS["bg_main"])
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
        comp_name = os.environ.get("COMPUTERNAME", "Workstation")
        self.lbl_header_subtitle.config(text=self.t("workstation_fmt", name=comp_name))
        self.lbl_header_title.config(text=self.t("header_title"))

        # Language buttons
        if self.lang == "vi":
            self.btn_lang_vi.config(bg=COLORS["accent_cyan"], fg=COLORS["bg_main"])
            self.btn_lang_en.config(bg=COLORS["bg_card"], fg=COLORS["text_muted"])
        else:
            self.btn_lang_en.config(bg=COLORS["accent_cyan"], fg=COLORS["bg_main"])
            self.btn_lang_vi.config(bg=COLORS["bg_card"], fg=COLORS["text_muted"])

        # Tab buttons
        self.btn_tab_ultra.config(text=self.t("tab_ultra"))
        self.btn_tab_chrome.config(text=self.t("tab_chrome"))
        self.btn_tab_cfg.config(text=self.t("tab_settings"))

        # Master toggle
        if self.is_running:
            self.btn_master_toggle.config(text=self.t("btn_stop_service"))
        else:
            self.btn_master_toggle.config(text=self.t("btn_start_service"))

        # Status pill
        if self.is_running:
            if self.connected_client_info:
                self.status_pill.config(text=self.t("status_connected"), fg=COLORS["accent_cyan"], bg=COLORS["accent_cyan_bg"])
            else:
                self.status_pill.config(text=self.t("status_ready"), fg=COLORS["accent_green"], bg=COLORS["accent_green_bg"])
        else:
            self.status_pill.config(text=self.t("status_stopped"), fg=COLORS["accent_red"], bg=COLORS["accent_red_bg"])

        # Active session banner
        if self.connected_client_info:
            self.active_session_label.config(text=self.t("session_active", client=self.connected_client_info), fg=COLORS["accent_cyan"])
        elif self.is_running:
            self.active_session_label.config(text=self.t("session_waiting"), fg=COLORS["accent_green"])
        else:
            self.active_session_label.config(text=self.t("session_stopped"), fg=COLORS["text_muted"])

        # Panel Ultra
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

        # Panel Chrome
        self.lbl_chrome_title.config(text=self.t("chrome_title"))
        self.lbl_chrome_desc.config(text=self.t("chrome_desc"))
        self.lbl_account.config(text=self.t("account_label"))
        self.lbl_device_name.config(text=self.t("device_name_label"))
        self.lbl_perm_pin.config(text=self.t("perm_pin_label"))
        self.chk_autostart.config(text=self.t("autostart_label"))
        self.chk_keepawake.config(text=self.t("keepawake_label"))
        self.btn_minimize_tray.config(text=self.t("btn_minimize_tray"))

        # Panel Settings
        self.lbl_relay.config(text=self.t("relay_label"))
        self.btn_save_settings.config(text=self.t("btn_save_settings"))
        self.lbl_log_title.config(text=self.t("log_title"))

        # Update tray menu if active
        if HAS_TRAY and self.tray_icon:
            try:
                self.tray_icon.menu = pystray.Menu(
                    pystray.MenuItem(self.t("tray_open"), self._restore_from_tray, default=True),
                    pystray.MenuItem(self.t("tray_copy"), self._copy_share_info),
                    pystray.MenuItem(self.t("tray_exit"), self._exit_application)
                )
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

        self.host_service = HostService(
            relay_url=self.config["relay"],
            room_id=self.config["room_id"],
            pin=self.config["pin"],
            device_name=self.config["device_name"],
            account=self.config["account"]
        )

        # Wire live callbacks
        self.host_service.on_status_change = lambda st: self.root.after(0, lambda: self._on_service_status(st))
        self.host_service.on_client_connect = lambda ev: self.root.after(0, lambda: self._on_client_connected(ev))
        self.host_service.on_client_disconnect = lambda: self.root.after(0, self._on_client_disconnected)
        self.host_service.on_chat_message = lambda sender, text: self.root.after(0, lambda: self._log(f"[CHAT] [{sender}]: {text}"))

        def runner():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.host_service.start())
            except Exception as e:
                self.root.after(0, lambda: self._log(f"Service Error: {e}"))

        self.service_thread = threading.Thread(target=runner, daemon=True)
        self.service_thread.start()

        self.is_running = True
        self.status_pill.config(text=self.t("status_running"), fg=COLORS["accent_green"], bg=COLORS["accent_green_bg"])
        self.btn_master_toggle.config(text=self.t("btn_stop_service"), bg=COLORS["accent_red"], fg="#FFFFFF", activebackground="#DC2626")
        self.active_session_label.config(text=self.t("session_waiting"), fg=COLORS["accent_green"])
        self._log(self.t("log_service_started", room_id=self.config['room_id']))

    def _stop_service(self):
        if self.host_service:
            self.host_service.running = False
            if self.host_service.ws and self.host_service.loop:
                try:
                    asyncio.run_coroutine_threadsafe(self.host_service.ws.close(), self.host_service.loop)
                except Exception:
                    pass

        PowerManager.prevent_sleep(False)
        self.is_running = False
        self.connected_client_info = None
        self.status_pill.config(text=self.t("status_stopped"), fg=COLORS["accent_red"], bg=COLORS["accent_red_bg"])
        self.btn_master_toggle.config(text=self.t("btn_start_service"), bg=COLORS["accent_green"], fg=COLORS["bg_main"], activebackground="#16A34A")
        self.active_session_label.config(text=self.t("session_stopped"), fg=COLORS["text_muted"])
        self.btn_disconnect_client.pack_forget()
        self._log(self.t("log_service_stopped"))

    def _on_service_status(self, status: str):
        if status == "ready":
            self.status_pill.config(text=self.t("status_ready"), fg=COLORS["accent_green"], bg=COLORS["accent_green_bg"])
            self.active_session_label.config(text=self.t("session_waiting"), fg=COLORS["accent_green"])
            self._log(self.t("log_room_registered", room_id=self.config['room_id']))
        elif status == "reconnecting":
            self.status_pill.config(text=self.t("status_reconnecting"), fg=COLORS["accent_amber"], bg=COLORS["accent_amber_bg"])
            self._log(self.t("log_reconnecting"))

    def _on_client_connected(self, event: dict):
        client_user = event.get("clientUser") or event.get("username") or ("Người điều khiển từ xa" if self.lang == "vi" else "Remote Operator")
        client_ip = event.get("clientIp") or "N/A"
        self.connected_client_info = f"{client_user} ({client_ip})"
        self.status_pill.config(text=self.t("status_connected"), fg=COLORS["accent_cyan"], bg=COLORS["accent_cyan_bg"])
        self.active_session_label.config(text=self.t("session_active", client=self.connected_client_info), fg=COLORS["accent_cyan"])
        self.btn_disconnect_client.pack(side="right")
        self._log(self.t("log_new_connection", client=self.connected_client_info))

    def _on_client_disconnected(self):
        self.connected_client_info = None
        self.btn_disconnect_client.pack_forget()
        if self.is_running:
            self.status_pill.config(text=self.t("status_ready"), fg=COLORS["accent_green"], bg=COLORS["accent_green_bg"])
            self.active_session_label.config(text=self.t("session_waiting"), fg=COLORS["accent_green"])
            self._log(self.t("log_disconnected"))

    def _disconnect_active_client(self):
        if self.host_service and self.host_service.ws and self.host_service.loop:
            self._log(self.t("log_emergency_disconnect"))
            try:
                asyncio.run_coroutine_threadsafe(
                    self.host_service.ws.send(json.dumps({"type": "client_disconnected"})),
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
        rand_id = f"RD-{random.randint(1000, 9999)}"
        self.room_var.set(rand_id)
        self.config["room_id"] = rand_id
        self._save_config()
        self._log(self.t("log_new_room", room_id=rand_id))
        if self.is_running:
            self._log(self.t("log_restart_req"))

    def _generate_random_pin(self):
        rand_pin = f"{random.randint(100000, 999999)}"
        self.pin_var.set(rand_pin)
        self.config["pin"] = rand_pin
        self._save_config()
        self._log(self.t("log_new_pin", pin=rand_pin))

    def _copy_to_clip(self, text: str, name: str):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
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
        self.root.clipboard_clear()
        self.root.clipboard_append(info)
        self._log(self.t("log_copied_all"))

    def _save_settings_click(self):
        self.config["relay"] = self.relay_var.get().strip()
        self._save_config()
        self._log(self.t("log_saved_relay"))

    # -------------------------------------------------------------
    # AUTO-START & SYSTEM TRAY
    # -------------------------------------------------------------
    def _check_autostart_status(self):
        if not winreg:
            self.autostart_var.set(False)
            return
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_READ)
            val, _ = winreg.QueryValueEx(key, APP_REG_NAME)
            winreg.CloseKey(key)
            if val:
                self.autostart_var.set(True)
        except Exception:
            self.autostart_var.set(False)

    def _on_autostart_toggle(self):
        if not winreg:
            return
        enable = self.autostart_var.get()
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_SET_VALUE)
            if enable:
                if getattr(sys, "frozen", False):
                    exe_path = sys.executable
                    cmd = f'"{exe_path}" --autostart'
                else:
                    script_path = str(Path(__file__).resolve())
                    pythonw_exe = sys.executable.replace("python.exe", "pythonw.exe")
                    cmd = f'"{pythonw_exe}" "{script_path}" --autostart'
                winreg.SetValueEx(key, APP_REG_NAME, 0, winreg.REG_SZ, cmd)
                self._log(self.t("log_autostart_on"))
            else:
                try:
                    winreg.DeleteValue(key, APP_REG_NAME)
                    self._log(self.t("log_autostart_off"))
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            messagebox.showerror("Registry Error", f"Cannot update Registry: {e}")

    def _on_keepawake_toggle(self):
        enable = self.keepawake_var.get()
        self.config["keep_awake"] = enable
        self._save_config()
        PowerManager.prevent_sleep(enable)
        state_str = "ON" if (enable and self.lang == "en") else ("BẬT" if enable else ("OFF" if self.lang == "en" else "TẮT"))
        self._log(self.t("log_keepawake", state=state_str))

    def _init_system_tray(self):
        if not HAS_TRAY:
            return

        menu = pystray.Menu(
            pystray.MenuItem(self.t("tray_open"), self._restore_from_tray, default=True),
            pystray.MenuItem(self.t("tray_copy"), self._copy_share_info),
            pystray.MenuItem(self.t("tray_exit"), self._exit_application)
        )
        self.tray_icon = pystray.Icon("TitanRemoteHost", get_tray_icon_image(), "Titan Remote Host", menu)

        show_tray = self.config.get("show_tray_icon", True)
        if "--no-tray" in sys.argv:
            show_tray = False
        elif "--tray" in sys.argv:
            show_tray = True

        def setup_tray(icon):
            ensure_interactive_desktop()
            promote_tray_icon()
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
        self.root.after(0, self._show_window)

    def _show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _on_window_close(self):
        if HAS_TRAY:
            self._minimize_to_tray()
        else:
            self._exit_application()

    def _exit_application(self, icon=None, item=None):
        self._stop_service()
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        self.root.after(0, self.root.destroy)
        sys.exit(0)

    def _log(self, msg: str):
        if hasattr(self, "log_text"):
            self.log_text.config(state="normal")
            self.log_text.insert("end", f"[{time.strftime('%H:%M:%S')}] {msg}\n")
            self.log_text.see("end")
            self.log_text.config(state="disabled")

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
    if sys.platform == "win32":
        try:
            import ctypes
            u = ctypes.windll.user32
            k = ctypes.windll.kernel32
            k.GlobalAlloc.restype = ctypes.c_void_p
            k.GlobalLock.restype = ctypes.c_void_p
            k.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
            k.GlobalLock.argtypes = [ctypes.c_void_p]
            k.GlobalUnlock.argtypes = [ctypes.c_void_p]
            u.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
            if u.OpenClipboard(0):
                try:
                    u.EmptyClipboard()
                    b = text.encode("utf-16le") + b"\x00\x00"
                    h = k.GlobalAlloc(2, len(b))
                    if h:
                        p = k.GlobalLock(h)
                        if p:
                            ctypes.memmove(p, b, len(b))
                            k.GlobalUnlock(h)
                            u.SetClipboardData(13, h)
                            return True
                        k.GlobalFree(h)
                finally:
                    u.CloseClipboard()
        except Exception:
            pass
    try:
        r = tk.Tk()
        r.withdraw()
        r.clipboard_clear()
        r.clipboard_append(text)
        r.update()
        r.destroy()
        return True
    except Exception:
        pass
    return False

def is_autostart_enabled() -> bool:
    if not winreg:
        return False
    try:
        if is_task_scheduler_autostart_enabled():
            return True
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_READ)
        val, _ = winreg.QueryValueEx(key, APP_REG_NAME)
        winreg.CloseKey(key)
        return bool(val)
    except Exception:
        return False

def apply_dark_titlebar(hwnd):
    """Apply native dark theme to the Windows titlebar to match ambient dark style."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import byref, c_int
        dwmapi = ctypes.windll.dwmapi
        dark = c_int(1)
        dwmapi.DwmSetWindowAttribute(hwnd, 20, byref(dark), ctypes.sizeof(dark))
        caption_color = c_int(0x00170D07)
        dwmapi.DwmSetWindowAttribute(hwnd, 35, byref(caption_color), ctypes.sizeof(caption_color))
        text_color = c_int(0x00FCFAF8)
        dwmapi.DwmSetWindowAttribute(hwnd, 36, byref(text_color), ctypes.sizeof(text_color))
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
        "relay": "wss://titan-remote.onrender.com",
        "account": "",
        "device_name": default_comp,
        "room_id": f"RD-{random.randint(1000, 9999)}",
        "pin": f"{random.randint(100000, 999999)}",
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
        self._host_service: Optional[HostService] = None
        self._service_thread: Optional[threading.Thread] = None
        self._is_running = False
        self._connected_client_info: Optional[str] = None
        self._tray_icon = None
        self._is_quitting = False

    def set_window(self, window):
        self._window = window

    def t(self, key: str, **kwargs) -> str:
        lang_dict = TRANSLATIONS.get(self._lang, TRANSLATIONS["vi"])
        tmpl = lang_dict.get(key, TRANSLATIONS["vi"].get(key, key))
        if kwargs:
            return tmpl.format(**kwargs)
        return tmpl

    def _eval_js(self, js: str):
        if not self._window or self._is_quitting:
            return
        def _worker():
            try:
                self._window.evaluate_js(js)
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True).start()

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
        cfg_copy["relay_url"] = cfg_copy.get("relay") or "wss://titan-remote.onrender.com"
        return {
            "config": cfg_copy,
            "autostart": is_autostart_enabled(),
            "service_installed": is_windows_service_installed(),
            "deployment": get_deployment_status(),
            "is_running": self._is_running
        }

    def drag_window(self):
        if sys.platform == "win32" and self._window:
            try:
                import ctypes
                hwnd = None
                if hasattr(self._window, "native") and hasattr(self._window.native, "Handle"):
                    hwnd = int(self._window.native.Handle)
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
        if self._is_running:
            return

        relay_url = self._config.get("relay") or self._config.get("relay_url") or "wss://titan-remote.onrender.com"
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

        try:
            self._host_service = HostService(
                relay_url=relay_url,
                room_id=room_id,
                pin=pin,
                device_name=device_name,
                account=account
            )
            self._host_service.on_status_change = self._on_service_status
            self._host_service.on_client_connect = self._on_client_connected
            self._host_service.on_client_disconnect = self._on_client_disconnected
            self._host_service.on_chat_message = lambda sender, text: self._log(f"[CHAT] [{sender}]: {text}")
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
        if self._host_service:
            self._host_service.running = False
            if self._host_service.ws and self._host_service.loop:
                try:
                    asyncio.run_coroutine_threadsafe(self._host_service.ws.close(), self._host_service.loop)
                except Exception:
                    pass

        PowerManager.prevent_sleep(False)
        self._is_running = False
        self._connected_client_info = None
        self._eval_js("window.__onServiceStatus && window.__onServiceStatus('stopped');")
        self._log(self.t("log_service_stopped"))

    def _on_service_status(self, status: str):
        safe_st = json.dumps(status)
        self._eval_js(f"window.__onServiceStatus && window.__onServiceStatus({safe_st});")
        if status == "ready":
            self._log(self.t("log_room_registered", room_id=self._config.get("room_id", "")))
        elif status == "reconnecting":
            self._log(self.t("log_reconnecting"))

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
        rand_id = f"RD-{random.randint(1000, 9999)}"
        self._config["room_id"] = rand_id
        self._save_config()
        self._log(self.t("log_new_room", room_id=rand_id))
        if self._is_running:
            self._log(self.t("log_restart_req"))
        return rand_id

    def renew_pin(self) -> str:
        rand_pin = f"{random.randint(100000, 999999)}"
        self._config["pin"] = rand_pin
        self._save_config()
        self._log(self.t("log_new_pin", pin=rand_pin))
        return rand_pin

    def copy_text(self, text: str, name: str):
        set_clipboard_text(text)
        self._log(self.t("log_copied", name=name, text=text))

    def copy_share_info(self):
        room = self._config.get("room_id", "")
        pin = self._config.get("pin", "")
        relay = self._config.get("relay") or self._config.get("relay_url") or "wss://titan-remote.onrender.com"
        http_url = relay.replace("wss://", "https://").replace("ws://", "http://")
        info = (
            f"{self.t('share_header')}\n"
            f"{self.t('share_dashboard')} {http_url}/dashboard\n"
            f"{self.t('share_room')} {room}\n"
            f"{self.t('share_pin')} {pin}\n"
            "--------------------------------------------"
        )
        set_clipboard_text(info)
        self._log(self.t("log_copied_all"))

    def disconnect_client(self):
        if self._host_service and self._host_service.ws and self._host_service.loop:
            self._log(self.t("log_emergency_disconnect"))
            try:
                asyncio.run_coroutine_threadsafe(
                    self._host_service.ws.send(json.dumps({"type": "client_disconnected"})),
                    self._host_service.loop
                )
            except Exception:
                pass
            self._host_service.has_active_client = False
            self._on_client_disconnected()

    def toggle_autostart(self, is_on: bool):
        try:
            setup_task_scheduler_autostart(is_on)
            if winreg:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_SET_VALUE)
                if is_on:
                    perm_exe = ensure_permanent_deployment(self._config_path)
                    if getattr(sys, "frozen", False):
                        cmd = f'"{perm_exe}" --autostart'
                    else:
                        script_path = str(Path(__file__).resolve())
                        pythonw_exe = sys.executable.replace("python.exe", "pythonw.exe")
                        cmd = f'"{pythonw_exe}" "{script_path}" --autostart'
                    winreg.SetValueEx(key, APP_REG_NAME, 0, winreg.REG_SZ, cmd)
                    self._log(self.t("log_autostart_on") + " (Task Scheduler /rl highest + %LOCALAPPDATA%)")
                else:
                    try:
                        winreg.DeleteValue(key, APP_REG_NAME)
                        self._log(self.t("log_autostart_off"))
                    except FileNotFoundError:
                        pass
                winreg.CloseKey(key)
        except Exception as e:
            self._log(f"Autostart Error: {e}")

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
        """Brings the GUI window to the foreground."""
        if self._window:
            try:
                self._window.show()
                self._window.restore()
            except Exception:
                pass

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
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TitanRemote.WorkstationHost.2.0")
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
        title="Titan Remote Host",
        html=html_content,
        js_api=api,
        width=560,
        height=740,
        frameless=True,
        easy_drag=False,
        resizable=False,
        background_color="#070D17",
    )
    api.set_window(window)

    def on_shown():
        try:
            if hasattr(window, "native") and hasattr(window.native, "Handle"):
                hwnd = int(window.native.Handle)
                if ico_path and ico_path.is_file():
                    set_window_icon(hwnd, ico_path)
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
                try:
                    window.show()
                    window.restore()
                except Exception:
                    pass

        def tray_copy(icon=None, item=None):
            api.copy_share_info()

        def tray_exit(icon=None, item=None):
            api._is_quitting = True
            api.stop_service()
            if api._tray_icon:
                try:
                    api._tray_icon.stop()
                except Exception:
                    pass
            if window:
                try:
                    window.destroy()
                except Exception:
                    pass
            sys.exit(0)

        tray_menu = pystray.Menu(
            pystray.MenuItem(api.t("tray_open"), tray_restore, default=True),
            pystray.MenuItem(api.t("tray_copy"), tray_copy),
            pystray.MenuItem(api.t("tray_exit"), tray_exit),
        )
        api._tray_icon = pystray.Icon("TitanRemoteHost", get_tray_icon_image(), "Titan Remote Host", tray_menu)

        show_tray = config.get("show_tray_icon", True)
        if "--no-tray" in sys.argv:
            show_tray = False
        elif "--tray" in sys.argv:
            show_tray = True

        def setup_tray(icon):
            ensure_interactive_desktop()
            promote_tray_icon()
            icon.visible = bool(show_tray)

        def tray_worker():
            ensure_interactive_desktop()
            try:
                api._tray_icon.run(setup=setup_tray)
            except Exception as e:
                pass

        threading.Thread(target=tray_worker, daemon=True).start()

    def handle_ipc(cmd: str) -> str:
        c = cmd.strip().upper()
        if c == "SHOW":
            api.show_window()
            return "OK:SHOWN"
        elif c == "STOP":
            api._is_quitting = True
            api.stop_service()
            if api._tray_icon:
                try:
                    api._tray_icon.stop()
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
    relay_url = config.get("relay") or config.get("relay_url") or "wss://titan-remote.onrender.com"
    room_id = config.get("room_id") or f"RD-{random.randint(1000, 9999)}"
    pin = config.get("pin") or f"{random.randint(100000, 999999)}"
    account = config.get("account") or ""
    device_name = config.get("device_name") or os.environ.get("COMPUTERNAME", "Workstation")

    PowerManager.prevent_sleep(True)
    service = HostService(
        relay_url=relay_url,
        room_id=room_id,
        pin=pin,
        device_name=device_name,
        account=account
    )
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
    if sys.platform == "win32":
        try:
            import ctypes
            if ctypes.windll.kernel32.AttachConsole(-1):
                if sys.stdout is None or not hasattr(sys.stdout, "write"):
                    sys.stdout = open("CONOUT$", "w", encoding="utf-8")
                if sys.stderr is None or not hasattr(sys.stderr, "write"):
                    sys.stderr = open("CONOUT$", "w", encoding="utf-8")
        except Exception:
            pass

    if "--service" in sys.argv:
        run_service_headless()
        return

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

    # Single-instance check: if another instance is already running, activate its window
    resp = send_ipc_command("SHOW")
    if resp:
        print("[INFO] Titan Remote Host đã đang chạy. Đã kích hoạt mở cửa sổ quản lý.")
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
        app = TitanHostGUI(root)
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
        print(f"[WARN] WebView2 launch failed ({e}), falling back to Tkinter GUI.")
        root = tk.Tk()
        app = TitanHostGUI(root)
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
            crash_log = Path.home() / ".titan_remote_crash.log"
            with open(crash_log, "a", encoding="utf-8") as f:
                f.write(f"\n--- CRASH AT {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                traceback.print_exc(file=f)
        except Exception:
            pass
        raise


import os
import sys
import time
import json
import winreg
import threading
import asyncio
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

# Ensure package is resolvable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from host_agent.host_service import HostService

REG_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_REG_NAME = "TitanRemoteHost"

class TitanHostGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Titan Remote - Host Control Panel")
        self.root.geometry("480x560")
        self.root.resizable(False, False)
        self.root.configure(bg="#0B0F19")

        self.service_thread: Optional[threading.Thread] = None
        self.host_service: Optional[HostService] = None
        self.is_running = False

        self._load_config()
        self._build_ui()
        self._check_autostart_status()

    def _get_config_path(self):
        return Path.home() / ".titan_remote_config.json"

    def _load_config(self):
        self.config = {
            "relay": "wss://titan-remote.onrender.com",
            "device_name": "Workstation-Office",
            "room_id": "RD-8888",
            "pin": "123456"
        }
        cfg_file = self._get_config_path()
        if cfg_file.exists():
            try:
                with open(cfg_file, "r", encoding="utf-8") as f:
                    self.config.update(json.load(f))
            except Exception:
                pass

    def _save_config(self):
        cfg_file = self._get_config_path()
        try:
            with open(cfg_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
        except Exception:
            pass

    def _build_ui(self):
        # Header Brand
        header = tk.Frame(self.root, bg="#0B0F19", pady=16)
        header.pack(fill="x")

        title = tk.Label(
            header,
            text="TITAN REMOTE HOST",
            font=("Segoe UI", 15, "bold"),
            fg="#F8FAFC",
            bg="#0B0F19"
        )
        title.pack()

        subtitle = tk.Label(
            header,
            text="Hệ thống điều khiển máy trạm từ xa qua Outbound Relay",
            font=("Segoe UI", 8),
            fg="#94A3B8",
            bg="#0B0F19"
        )
        subtitle.pack(pady=(2, 0))

        # Main Card Form
        card = tk.Frame(self.root, bg="#111827", padx=20, pady=16, highlightthickness=1, highlightbackground="#273549")
        card.pack(fill="x", padx=20, pady=4)

        # Status Row
        status_row = tk.Frame(card, bg="#111827")
        status_row.pack(fill="x", pady=(0, 14))

        tk.Label(status_row, text="TRẠNG THÁI:", font=("Segoe UI", 9, "bold"), fg="#94A3B8", bg="#111827").pack(side="left")
        self.status_dot = tk.Label(status_row, text="●", font=("Segoe UI", 12), fg="#EF4444", bg="#111827")
        self.status_dot.pack(side="left", padx=(6, 4))
        self.status_label = tk.Label(status_row, text="ĐÃ DỪNG (STOPPED)", font=("Segoe UI", 9, "bold"), fg="#EF4444", bg="#111827")
        self.status_label.pack(side="left")

        # Inputs
        self.relay_var = tk.StringVar(value=self.config["relay"])
        self.name_var = tk.StringVar(value=self.config["device_name"])
        self.room_var = tk.StringVar(value=self.config["room_id"])
        self.pin_var = tk.StringVar(value=self.config["pin"])

        self._create_field(card, "Relay Server URL:", self.relay_var)
        self._create_field(card, "Tên máy hiển thị (Device Name):", self.name_var)

        row2 = tk.Frame(card, bg="#111827")
        row2.pack(fill="x", pady=4)

        col1 = tk.Frame(row2, bg="#111827")
        col1.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self._create_field(col1, "Mã phòng (Room ID):", self.room_var)

        col2 = tk.Frame(row2, bg="#111827")
        col2.pack(side="left", fill="x", expand=True, padx=(6, 0))
        self._create_field(col2, "Mã PIN bảo mật:", self.pin_var, show="*")

        # Autostart Checkbox
        self.autostart_var = tk.BooleanVar(value=False)
        chk = tk.Checkbutton(
            card,
            text="Tự động khởi động cùng Windows (Auto-start)",
            variable=self.autostart_var,
            command=self._on_autostart_toggle,
            bg="#111827",
            fg="#F8FAFC",
            selectcolor="#1F2937",
            activebackground="#111827",
            activeforeground="#22C55E",
            font=("Segoe UI", 8)
        )
        chk.pack(anchor="w", pady=(10, 4))

        # Control Buttons
        btn_frame = tk.Frame(self.root, bg="#0B0F19", pady=12)
        btn_frame.pack(fill="x", padx=20)

        self.btn_toggle = tk.Button(
            btn_frame,
            text="KHỞI ĐỘNG DỊCH VỤ",
            font=("Segoe UI", 10, "bold"),
            bg="#22C55E",
            fg="#0B0F19",
            activebackground="#16A34A",
            activeforeground="#0B0F19",
            relief="flat",
            pady=8,
            cursor="hand2",
            command=self._toggle_service
        )
        self.btn_toggle.pack(fill="x")

        btn_bg = tk.Button(
            btn_frame,
            text="Chạy Ngầm (Ẩn Cửa Sổ)",
            font=("Segoe UI", 8),
            bg="#1F2937",
            fg="#94A3B8",
            activebackground="#374151",
            activeforeground="#F8FAFC",
            relief="flat",
            pady=4,
            cursor="hand2",
            command=self._minimize_to_background
        )
        btn_bg.pack(fill="x", pady=(6, 0))

        # Mini Log Box
        log_frame = tk.Frame(self.root, bg="#0B0F19", padx=20)
        log_frame.pack(fill="both", expand=True, pady=(0, 12))

        self.log_text = tk.Text(
            log_frame,
            bg="#05070C",
            fg="#94A3B8",
            insertbackground="#22C55E",
            font=("Consolas", 8),
            relief="flat",
            height=6,
            wrap="word",
            state="disabled"
        )
        self.log_text.pack(fill="both", expand=True)

    def _create_field(self, parent, label_text, var, show=None):
        tk.Label(parent, text=label_text, font=("Segoe UI", 8), fg="#94A3B8", bg="#111827").pack(anchor="w", pady=(2, 2))
        entry = tk.Entry(
            parent,
            textvariable=var,
            font=("Consolas", 9),
            bg="#1E293B",
            fg="#F8FAFC",
            insertbackground="#22C55E",
            relief="flat",
            show=show,
            highlightthickness=1,
            highlightbackground="#334155",
            highlightcolor="#3B82F6"
        )
        entry.pack(fill="x", ipady=4, pady=(0, 4))

    def _log(self, msg: str):
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _check_autostart_status(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_READ)
            val, _ = winreg.QueryValueEx(key, APP_REG_NAME)
            winreg.CloseKey(key)
            if val:
                self.autostart_var.set(True)
        except Exception:
            self.autostart_var.set(False)

    def _on_autostart_toggle(self):
        enable = self.autostart_var.get()
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_SET_VALUE)
            if enable:
                script_path = str(Path(__file__).resolve())
                pythonw_exe = sys.executable.replace("python.exe", "pythonw.exe")
                cmd = f'"{pythonw_exe}" "{script_path}" --autostart'
                winreg.SetValueEx(key, APP_REG_NAME, 0, winreg.REG_SZ, cmd)
                self._log("Đã bật khởi động cùng Windows")
            else:
                try:
                    winreg.DeleteValue(key, APP_REG_NAME)
                    self._log("Đã tắt khởi động cùng Windows")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            messagebox.showerror("Lỗi Registry", f"Không thể cập nhật Registry: {e}")

    def _toggle_service(self):
        if self.is_running:
            self._stop_service()
        else:
            self._start_service()

    def _start_service(self):
        self.config["relay"] = self.relay_var.get().strip()
        self.config["device_name"] = self.name_var.get().strip()
        self.config["room_id"] = self.room_var.get().strip()
        self.config["pin"] = self.pin_var.get().strip()
        self._save_config()

        self.host_service = HostService(
            relay_url=self.config["relay"],
            room_id=self.config["room_id"],
            pin=self.config["pin"],
            device_name=self.config["device_name"]
        )

        def runner():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.host_service.start())
            except Exception as e:
                self._log(f"Lỗi service: {e}")

        self.service_thread = threading.Thread(target=runner, daemon=True)
        self.service_thread.start()

        self.is_running = True
        self.status_dot.config(fg="#22C55E")
        self.status_label.config(text="ĐANG HOẠT ĐỘNG (RUNNING)", fg="#22C55E")
        self.btn_toggle.config(text="DỪNG DỊCH VỤ", bg="#EF4444", fg="#FFFFFF")
        self._log(f"Khởi động thành công! Phòng: {self.config['room_id']}")

    def _stop_service(self):
        if self.host_service:
            self.host_service.running = False
            if self.host_service.ws:
                asyncio.run_coroutine_threadsafe(self.host_service.ws.close(), self.host_service.loop)

        self.is_running = False
        self.status_dot.config(fg="#EF4444")
        self.status_label.config(text="ĐÃ DỪNG (STOPPED)", fg="#EF4444")
        self.btn_toggle.config(text="KHỞI ĐỘNG DỊCH VỤ", bg="#22C55E", fg="#0B0F19")
        self._log("Đã dừng dịch vụ.")

    def _minimize_to_background(self):
        self.root.withdraw()
        # Create a small popup reminder in background
        threading.Thread(target=self._background_monitor, daemon=True).start()

    def _background_monitor(self):
        time.sleep(1)
        self._log("Ứng dụng đang chạy ngầm trong Windows.")

def main():
    root = tk.Tk()
    app = TitanHostGUI(root)
    # Check if started with --autostart
    if "--autostart" in sys.argv:
        app._start_service()
        app._minimize_to_background()
    root.mainloop()

if __name__ == "__main__":
    main()

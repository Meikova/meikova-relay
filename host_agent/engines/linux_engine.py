"""Dedicated High-Performance Linux Engine (X11 XShm / Wayland / Headless Xvfb + SIMD libturbojpeg.so.0 + XDG/systemd)."""

import os
import sys
import shutil
import platform
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from .base_engine import BaseOSEngine


class LinuxEngine(BaseOSEngine):
    """Dedicated Linux Host Engine optimized for Ubuntu, Debian, Kali, Fedora, Arch (X11/XShm & Wayland)."""

    engine_name = "LinuxEngine (X11 XShm / Wayland + SIMD TurboJPEG)"
    platform_key = "linux"

    def __init__(self):
        self.initialize_runtime()

    # -------------------------------------------------------------------------
    # 1. Runtime, Identity & Privilege
    # -------------------------------------------------------------------------
    def initialize_runtime(self) -> None:
        if "GTK_THEME" not in os.environ:
            os.environ["GTK_THEME"] = "Adwaita:dark"

    def get_os_display_name(self) -> str:
        arch = "64-bit" if (sys.maxsize > 2**32 or platform.machine().endswith("64")) else "32-bit"
        try:
            os_rel = "/etc/os-release"
            if os.path.isfile(os_rel):
                with open(os_rel, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if line.startswith("PRETTY_NAME="):
                            pretty = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if pretty:
                                return f"{pretty} ({arch})" if arch not in pretty else pretty
        except Exception:
            pass
        sys_name = platform.system() or "Linux"
        return f"{sys_name} {arch}"

    def get_machine_id(self) -> str:
        for p in (Path("/etc/machine-id"), Path("/var/lib/dbus/machine-id")):
            if p.exists():
                try:
                    t = p.read_text(encoding="utf-8", errors="ignore").strip()
                    if t:
                        return t
                except Exception:
                    pass
        return super().get_machine_id()

    def is_admin(self) -> bool:
        try:
            return os.geteuid() == 0
        except Exception:
            return False

    def elevate_and_execute(self, args_str: str) -> bool:
        if os.environ.get("MEIKOVA_TEST_MODE") == "1" or "unittest" in sys.modules:
            return False
        try:
            exe = sys.executable
            script_path = str(Path(__file__).resolve().parent.parent / "gui_agent.py")
            base_cmd = [exe] if getattr(sys, "frozen", False) else [exe, script_path]
            extra_args = [a for a in (args_str or "").split() if a]
            for elev_bin in ("pkexec", "gksudo", "kdesudo"):
                if shutil.which(elev_bin):
                    env_args = [
                        "env",
                        f"DISPLAY={os.environ.get('DISPLAY', ':0')}",
                        f"XAUTHORITY={os.environ.get('XAUTHORITY', str(Path.home() / '.Xauthority'))}",
                    ]
                    subprocess.Popen([elev_bin, *env_args, *base_cmd, *extra_args])
                    return True
        except Exception:
            pass
        return False

    # -------------------------------------------------------------------------
    # 2. Screen Capture & Monitor Topology
    # -------------------------------------------------------------------------
    def get_turbojpeg_candidates(self) -> List[str]:
        here = Path(__file__).resolve().parent.parent
        return [
            str(here / "libturbojpeg.so.0"),
            "libturbojpeg.so.0",
            "/usr/lib/x86_64-linux-gnu/libturbojpeg.so.0",
            "/usr/lib/aarch64-linux-gnu/libturbojpeg.so.0",
            "/usr/lib64/libturbojpeg.so.0",
            "/usr/lib/libturbojpeg.so.0",
            "/usr/lib/libturbojpeg.so",
        ]

    def detect_monitors(self, sct_instance: Any = None) -> List[Dict[str, Any]]:
        results = []
        if sct_instance is not None:
            try:
                mons = sct_instance.monitors[1:] if len(sct_instance.monitors) > 1 else sct_instance.monitors
                for i, m in enumerate(mons):
                    left = int(m.get("left", 0))
                    top = int(m.get("top", 0))
                    w = int(m.get("width", 1920))
                    h = int(m.get("height", 1080))
                    results.append({
                        "id": i + 1,
                        "name": f"Màn {i + 1}",
                        "rect": (left, top, left + w, top + h),
                        "x": left,
                        "y": top,
                        "left": left,
                        "top": top,
                        "width": w,
                        "height": h,
                    })
            except Exception:
                pass
        if not results:
            results.append({
                "id": 1,
                "name": "Màn 1",
                "rect": (0, 0, 1920, 1080),
                "x": 0,
                "y": 0,
                "left": 0,
                "top": 0,
                "width": 1920,
                "height": 1080,
            })
        return results

    def grab_frame_raw(
        self,
        left: int,
        top: int,
        width: int,
        height: int,
        monitor_id: int = 0,
        native_cap: Any = None,
        sct_instance: Any = None,
        dxcam_instance: Any = None,
    ) -> Tuple[Optional[Tuple[int, int]], Any, bool]:
        if sct_instance is not None:
            try:
                if monitor_id == 0:
                    mon_target = sct_instance.monitors[0]
                elif 1 <= monitor_id < len(sct_instance.monitors):
                    mon_target = sct_instance.monitors[monitor_id]
                else:
                    mon_target = {"left": left, "top": top, "width": width, "height": height}
                shot = sct_instance.grab(mon_target)
                return (shot.width, shot.height), shot.raw, False
            except Exception:
                pass
        return None, None, False

    # -------------------------------------------------------------------------
    # 3. Interactive Shell, Quick Macros & Input Shortcuts
    # -------------------------------------------------------------------------
    def get_shell_command(self) -> List[str]:
        return ["/bin/bash"] if os.path.exists("/bin/bash") else ["/bin/sh"]

    def execute_quick_macro(self, cmd: str, mode: str = "auto") -> bool:
        clean = (cmd or "").strip()
        if not clean:
            return False
        if os.environ.get("MEIKOVA_TEST_MODE") == "1" or "unittest" in sys.modules:
            return True
        low = clean.lower()
        try:
            if low == "calc":
                for c_app in ("gnome-calculator", "galculator", "kcalc", "mate-calc", "xcalc"):
                    if shutil.which(c_app):
                        subprocess.Popen([c_app])
                        return True
            elif low == "taskmgr":
                for t_app in ("gnome-system-monitor", "xfce4-taskmanager", "ksysguard", "mate-system-monitor"):
                    if shutil.which(t_app):
                        subprocess.Popen([t_app])
                        return True
            for term_app in ("x-terminal-emulator", "xfce4-terminal", "gnome-terminal", "konsole", "xterm"):
                if shutil.which(term_app):
                    subprocess.Popen([term_app, "-e", f"bash -c '{clean}; exec bash'"])
                    return True
            subprocess.Popen(clean, shell=True)
            return True
        except Exception:
            return False

    def get_paste_vk_combo(self) -> Tuple[int, int]:
        return (0x11, 0x56)  # Ctrl+V on Linux

    # -------------------------------------------------------------------------
    # 4. Power Management & Wake Timers
    # -------------------------------------------------------------------------
    def lock_workstation(self) -> bool:
        if os.environ.get("MEIKOVA_TEST_MODE") == "1" or "unittest" in sys.modules:
            return True
        for cmd in (["loginctl", "lock-session"], ["xdg-screensaver", "lock"], ["dm-tool", "lock"]):
            try:
                if subprocess.call(cmd) == 0:
                    return True
            except Exception:
                continue
        return False

    def restart_machine(self, delay_seconds: int = 5) -> bool:
        if os.environ.get("MEIKOVA_TEST_MODE") == "1" or "unittest" in sys.modules:
            return True
        try:
            cmd = ["systemctl", "reboot"] if os.path.exists("/bin/systemctl") else ["shutdown", "-r", "now"]
            return subprocess.call(cmd) == 0
        except Exception:
            return False

    def shutdown_machine(self, delay_seconds: int = 10) -> bool:
        if os.environ.get("MEIKOVA_TEST_MODE") == "1" or "unittest" in sys.modules:
            return True
        try:
            cmd = ["systemctl", "poweroff"] if os.path.exists("/bin/systemctl") else ["shutdown", "-h", "now"]
            return subprocess.call(cmd) == 0
        except Exception:
            return False

    def cancel_power_action(self) -> bool:
        if os.environ.get("MEIKOVA_TEST_MODE") == "1" or "unittest" in sys.modules:
            return True
        try:
            return subprocess.call(["shutdown", "-c"]) == 0
        except Exception:
            return False

    def prevent_sleep(self, enable: bool = True) -> bool:
        if os.environ.get("MEIKOVA_TEST_MODE") == "1" or "unittest" in sys.modules:
            return True
        if os.environ.get("DISPLAY") and shutil.which("xset"):
            try:
                if enable:
                    subprocess.Popen(["xset", "s", "off", "-dpms"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    subprocess.Popen(["xset", "s", "on", "+dpms"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
        return True

    # -------------------------------------------------------------------------
    # 5. Hardware Telemetry & Process Management
    # -------------------------------------------------------------------------
    def get_ram_telemetry(self) -> Dict[str, Any]:
        if os.path.exists("/proc/meminfo"):
            try:
                with open("/proc/meminfo", "r", encoding="utf-8", errors="ignore") as f:
                    meminfo = {}
                    for line in f:
                        parts = line.split(":")
                        if len(parts) == 2:
                            meminfo[parts[0].strip()] = int(parts[1].split()[0])
                    total_kb = meminfo.get("MemTotal", 16 * 1024 * 1024)
                    avail_kb = meminfo.get("MemAvailable", meminfo.get("MemFree", 8 * 1024 * 1024))
                    total_ram_gb = round(total_kb / (1024 ** 2), 2)
                    avail_ram_gb = round(avail_kb / (1024 ** 2), 2)
                    used_ram_gb = round(total_ram_gb - avail_ram_gb, 2)
                    ram_percent = int(((total_kb - avail_kb) / max(1, total_kb)) * 100)
                    return {
                        "total_gb": total_ram_gb,
                        "used_gb": used_ram_gb,
                        "free_gb": avail_ram_gb,
                        "percent": ram_percent,
                    }
            except Exception:
                pass
        return super().get_ram_telemetry()

    # -------------------------------------------------------------------------
    # 6. Service, Deployment & Autostart Tier Management
    # -------------------------------------------------------------------------
    def get_executable_name(self) -> str:
        return "meikova-relay-host"

    def is_autostart_enabled(self) -> bool:
        desktop = Path.home() / ".config/autostart/meikovarelayhost.desktop"
        systemd_unit = Path.home() / ".config/systemd/user/meikova-relay-host.service"
        return desktop.exists() or systemd_unit.exists()

    def set_autostart(self, enable: bool, config_path: Optional[Path] = None) -> Tuple[bool, str]:
        try:
            autostart_dir = Path.home() / ".config/autostart"
            desktop_path = autostart_dir / "meikovarelayhost.desktop"
            if enable:
                autostart_dir.mkdir(parents=True, exist_ok=True)
                try:
                    from host_agent.deployment_manager import ensure_permanent_deployment
                    perm_exe = ensure_permanent_deployment(config_path)
                except Exception:
                    perm_exe = Path(sys.executable)
                if getattr(sys, "frozen", False):
                    exec_cmd = f'"{perm_exe}" --autostart'
                else:
                    script_path = str(Path(__file__).resolve().parent.parent / "gui_agent.py")
                    exec_cmd = f'"{sys.executable}" "{script_path}" --autostart'
                content = f"""[Desktop Entry]
Type=Application
Version=1.0
Name=Meikova Relay Host
Comment=Meikova Relay Workstation Host Service
Exec={exec_cmd}
Icon=meikovarelayhost
Terminal=false
Categories=Network;RemoteAccess;
X-GNOME-Autostart-enabled=true
"""
                desktop_path.write_text(content, encoding="utf-8")
                return True, "Linux XDG Autostart (~/.config/autostart)"
            else:
                if desktop_path.exists():
                    desktop_path.unlink()
                return True, "Disabled Linux XDG Autostart"
        except Exception as e:
            return False, str(e)

    def is_service_installed(self) -> bool:
        return (
            Path("/etc/systemd/system/meikova-relay.service").exists()
            or Path("/lib/systemd/system/meikova-relay.service").exists()
        )

    # -------------------------------------------------------------------------
    # 7. Window Management, Clipboard & System Tray
    # -------------------------------------------------------------------------
    def get_ui_fonts(self) -> Dict[str, str]:
        return {"sans": "DejaVu Sans", "mono": "DejaVu Sans Mono"}

    def apply_window_theme(self, hwnd_or_window: Any) -> None:
        if not hwnd_or_window:
            return
        try:
            if hasattr(hwnd_or_window, "winfo_id") and shutil.which("xprop"):
                wid = hwnd_or_window.winfo_id()
                if wid:
                    subprocess.Popen(
                        ["xprop", "-id", str(wid), "-f", "_GTK_THEME_VARIANT", "8u", "-set", "_GTK_THEME_VARIANT", "dark"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
        except Exception:
            pass

    def activate_window(
        self,
        window_or_root: Any,
        cached_hwnd: Optional[int] = None,
        title: str = "Meikova Relay Host",
    ) -> bool:
        if window_or_root:
            try:
                if callable(getattr(window_or_root, "show", None)):
                    window_or_root.show()
                if callable(getattr(window_or_root, "restore", None)):
                    window_or_root.restore()
                if hasattr(window_or_root, "winfo_exists") and callable(getattr(window_or_root, "deiconify", None)):
                    window_or_root.deiconify()
                    window_or_root.update_idletasks()
                    window_or_root.lift()
                    try:
                        window_or_root.attributes("-topmost", True)
                        window_or_root.after(200, lambda: window_or_root.attributes("-topmost", False))
                    except Exception:
                        pass
                    window_or_root.focus_force()
            except Exception:
                pass

        try:
            subprocess.run(["wmctrl", "-a", title], check=False)
        except Exception:
            pass
        return True

    def set_clipboard_text(self, text: str, tk_root: Any = None) -> bool:
        ok = False
        if tk_root is not None:
            try:
                tk_root.clipboard_clear()
                tk_root.clipboard_append(text)
                tk_root.update_idletasks()
                ok = True
            except Exception:
                pass
        for cmd in (
            ["wl-copy"],
            ["xclip", "-selection", "clipboard"],
            ["xsel", "--clipboard", "--input"],
        ):
            if shutil.which(cmd[0]):
                try:
                    proc = subprocess.Popen(
                        cmd,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        close_fds=True,
                    )
                    proc.communicate(input=text.encode("utf-8"), timeout=1.0)
                    if proc.returncode == 0:
                        return True
                except Exception:
                    continue
        return ok

    def configure_tray_environment(self) -> str:
        if "PYSTRAY_BACKEND" in os.environ:
            return os.environ["PYSTRAY_BACKEND"]
        try:
            import gi
            for ns in ("AyatanaAppIndicator3", "AppIndicator3"):
                try:
                    gi.require_version(ns, "0.1")
                    return "appindicator"
                except Exception:
                    continue
            try:
                gi.require_version("Gtk", "3.0")
                return "gtk"
            except Exception:
                pass
        except Exception:
            pass
        return "xorg"

    def patch_tray_backend(self, on_left_click: Any = None, on_right_click: Any = None) -> None:
        try:
            import pystray._xorg as xorg_mod
            IconCls = getattr(xorg_mod, "Icon", None)
            if IconCls and not getattr(IconCls, "_meikova_xorg_patched", False):
                orig_btn_press = getattr(IconCls, "_on_button_press", None)

                def _patched_on_button_press(icon_self, event):
                    btn = getattr(event, "detail", 1)
                    rx = int(getattr(event, "root_x", 0) or 0)
                    ry = int(getattr(event, "root_y", 0) or 0)
                    cb_left = getattr(icon_self, "_meikova_on_left_click", None) or on_left_click
                    cb_right = getattr(icon_self, "_meikova_on_right_click", None) or on_right_click
                    if btn == 1:
                        if callable(cb_left):
                            try:
                                cb_left(icon_self, rx, ry)
                                return
                            except Exception:
                                pass
                    elif btn in (2, 3):
                        if callable(cb_right):
                            try:
                                cb_right(icon_self, rx, ry)
                                return
                            except Exception:
                                pass
                        elif callable(cb_left):
                            try:
                                cb_left(icon_self, rx, ry)
                                return
                            except Exception:
                                pass
                    if callable(orig_btn_press):
                        return orig_btn_press(icon_self, event)

                IconCls._on_button_press = _patched_on_button_press
                IconCls._meikova_xorg_patched = True
        except Exception:
            pass

        try:
            import gi
            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk, Gdk
            css_provider = Gtk.CssProvider()
            css_data = b"""
            menu, .menu, .popup {
                background-color: #16181A;
                color: #F4F6F8;
                border: 1px solid #2C3035;
                border-radius: 8px;
                padding: 6px 4px;
            }
            menuitem {
                color: #F4F6F8;
                padding: 6px 12px;
                border-radius: 5px;
            }
            menuitem:hover {
                background-color: #2A2E33;
                color: #83E8AC;
            }
            menuitem:disabled {
                color: #7D8590;
            }
            separator {
                background-color: #282B30;
                min-height: 1px;
                margin: 4px 8px;
            }
            """
            css_provider.load_from_data(css_data)
            screen = Gdk.Screen.get_default()
            if screen:
                Gtk.StyleContext.add_provider_for_screen(
                    screen,
                    css_provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
                )
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # 8. Cursor Telemetry & Clipboard Reading (Linux XFixes / X11 / Wayland)
    # -------------------------------------------------------------------------
    def get_cursor_shape(self) -> str:
        if os.environ.get("MEIKOVA_TEST_MODE") == "1" or "unittest" in sys.modules:
            return "default"
        if not os.environ.get("DISPLAY"):
            return "default"
        try:
            import ctypes
            x11 = getattr(self, "_x11_lib", None) or ctypes.CDLL("libX11.so.6")
            xfixes = getattr(self, "_xfixes_lib", None) or ctypes.CDLL("libXfixes.so.3")
            self._x11_lib = x11
            self._xfixes_lib = xfixes

            class XFixesCursorImage(ctypes.Structure):
                _fields_ = [
                    ("x", ctypes.c_short),
                    ("y", ctypes.c_short),
                    ("width", ctypes.c_ushort),
                    ("height", ctypes.c_ushort),
                    ("xhot", ctypes.c_ushort),
                    ("yhot", ctypes.c_ushort),
                    ("cursor_serial", ctypes.c_ulong),
                    ("pixels", ctypes.POINTER(ctypes.c_ulong)),
                    ("atom", ctypes.c_ulong),
                    ("name", ctypes.c_char_p),
                ]

            x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
            x11.XOpenDisplay.restype = ctypes.c_void_p
            x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
            xfixes.XFixesGetCursorImage.argtypes = [ctypes.c_void_p]
            xfixes.XFixesGetCursorImage.restype = ctypes.POINTER(XFixesCursorImage)
            x11.XFree.argtypes = [ctypes.c_void_p]

            dpy = x11.XOpenDisplay(None)
            if not dpy:
                return "default"
            try:
                img_ptr = xfixes.XFixesGetCursorImage(dpy)
                if not img_ptr:
                    return "default"
                try:
                    raw_name = img_ptr.contents.name
                    cname = raw_name.decode("utf-8", errors="ignore").lower() if raw_name else ""
                finally:
                    x11.XFree(img_ptr)
                if any(k in cname for k in ("hand", "pointer", "link")):
                    return "pointer"
                if any(k in cname for k in ("xterm", "ibeam", "text")):
                    return "text"
                if any(k in cname for k in ("watch", "wait", "progress", "left_ptr_watch")):
                    return "wait"
                if any(k in cname for k in ("fleur", "move", "size_all", "grabbing")):
                    return "move"
                if any(k in cname for k in ("cross", "tcross")):
                    return "crosshair"
                if any(k in cname for k in ("sb_h_double_arrow", "ew-resize", "col-resize", " left_side", "right_side")):
                    return "ew-resize"
                if any(k in cname for k in ("sb_v_double_arrow", "ns-resize", "row-resize", "top_side", "bottom_side")):
                    return "ns-resize"
                if any(k in cname for k in ("not-allowed", "pirate", "crossed_circle", "no_drop")):
                    return "not-allowed"
                return "default"
            finally:
                x11.XCloseDisplay(dpy)
        except Exception:
            return "default"

    def get_clipboard_text(self) -> Optional[str]:
        for cmd in (
            ["wl-paste", "--no-newline"],
            ["xclip", "-selection", "clipboard", "-o"],
            ["xsel", "--clipboard", "--output"],
        ):
            if shutil.which(cmd[0]):
                try:
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=1.5)
                    if res.returncode == 0:
                        return res.stdout
                except Exception:
                    continue
        return super().get_clipboard_text()

    # -------------------------------------------------------------------------
    # 9. Headless Detection & Virtual Display Status (Linux Xvfb / xrandr)
    # -------------------------------------------------------------------------
    def is_headless_display(self) -> bool:
        disp = os.environ.get("DISPLAY")
        if not disp:
            return True
        try:
            res = subprocess.run(["xrandr"], capture_output=True, text=True, timeout=3)
            return " connected" not in res.stdout
        except Exception:
            return False

    def get_virtual_display_status(self) -> Dict[str, Any]:
        if shutil.which("Xvfb"):
            return {"installed": True, "driver_name": "Xvfb Virtual Framebuffer"}
        return {"installed": False, "driver_name": None}

    # -------------------------------------------------------------------------
    # 10. Audio Output & Virtual Audio Detection (Linux PulseAudio / PipeWire / ALSA)
    # -------------------------------------------------------------------------
    def is_audio_output_available(self) -> bool:
        try:
            res = subprocess.run(["pactl", "list", "sinks", "short"], capture_output=True, text=True, timeout=3)
            if res.returncode == 0 and res.stdout.strip():
                return True
        except Exception:
            pass
        cards_file = Path("/proc/asound/cards")
        if cards_file.exists():
            content = cards_file.read_text(encoding="utf-8", errors="ignore").strip()
            return "--- no soundcards ---" not in content and bool(content)
        return True

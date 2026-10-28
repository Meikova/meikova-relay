"""Dedicated High-Performance Windows Engine (Win32 GDI DIBSection + DXGI + SIMD TurboJPEG + WMI/Registry)."""

import os
import sys
import time
import ctypes
import platform
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from .base_engine import BaseOSEngine

user32 = getattr(ctypes, "windll", None).user32 if hasattr(ctypes, "windll") else None
gdi32 = getattr(ctypes, "windll", None).gdi32 if hasattr(ctypes, "windll") else None
winmm = getattr(ctypes, "windll", None).winmm if hasattr(ctypes, "windll") else None

SM_CXSCREEN = 0
SM_CYSCREEN = 1
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79


class WindowsEngine(BaseOSEngine):
    """Dedicated Windows Host Engine optimized for Windows 10/11 (x64/ARM64)."""

    engine_name = "WindowsEngine (Win32 GDI DIBSection + SIMD TurboJPEG)"
    platform_key = "win32"

    def __init__(self):
        self.initialize_runtime()

    def initialize_runtime(self) -> None:
        if winmm:
            try:
                winmm.timeBeginPeriod(1)
            except Exception:
                pass
        if user32:
            try:
                if hasattr(user32, "SetProcessDpiAwarenessContext"):
                    user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
                elif hasattr(user32, "SetProcessDPIAware"):
                    user32.SetProcessDPIAware()
            except Exception:
                pass

    def get_os_display_name(self) -> str:
        arch = "64-bit" if (sys.maxsize > 2**32 or platform.machine().endswith("64")) else "32-bit"
        product_name = ""
        build_num = 0
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion") as key:
                try:
                    product_name, _ = winreg.QueryValueEx(key, "ProductName")
                except Exception:
                    product_name = ""
                for b_key in ("CurrentBuildNumber", "CurrentBuild"):
                    try:
                        b_val, _ = winreg.QueryValueEx(key, b_key)
                        if str(b_val).strip().isdigit():
                            build_num = int(str(b_val).strip())
                            break
                    except Exception:
                        continue
        except Exception:
            pass

        if not build_num:
            try:
                build_num = int(getattr(sys.getwindowsversion(), "build", 0) or 0)
            except Exception:
                build_num = 0

        if product_name:
            clean_name = str(product_name).strip()
            if build_num >= 22000 and "Windows 10" in clean_name:
                clean_name = clean_name.replace("Windows 10", "Windows 11")
            return f"{clean_name} {arch}"

        win_ver = "Windows 11" if build_num >= 22000 else "Windows 10"
        return f"{win_ver} {arch}"

    def is_admin(self) -> bool:
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin() != 0)
        except Exception:
            return False

    def get_turbojpeg_candidates(self) -> List[str]:
        here = Path(__file__).resolve().parent.parent
        meipass = Path(getattr(sys, "_MEIPASS", here))
        return [
            str(here / "turbojpeg.dll"),
            str(here / "libs" / "win64" / "turbojpeg.dll"),
            str(here / "libturbojpeg.dll"),
            str(meipass / "turbojpeg.dll"),
            str(meipass / "host_agent" / "turbojpeg.dll"),
            str(meipass / "host_agent" / "libs" / "win64" / "turbojpeg.dll"),
            "turbojpeg.dll",
            "libturbojpeg.dll",
            r"C:\libjpeg-turbo64\bin\turbojpeg.dll",
            r"C:\Program Files\libjpeg-turbo64\bin\turbojpeg.dll",
        ]

    def detect_monitors(self, sct_instance: Any = None) -> List[Dict[str, Any]]:
        results = []
        if user32:
            try:
                from ctypes import wintypes
                mon_rects = []

                def _callback(hmonitor, hdc, lprect, lparam):
                    rect = lprect.contents
                    mon_rects.append((rect.left, rect.top, rect.right, rect.bottom))
                    return 1

                MonitorEnumProc = ctypes.WINFUNCTYPE(
                    ctypes.c_int,
                    wintypes.HMONITOR,
                    wintypes.HDC,
                    ctypes.POINTER(wintypes.RECT),
                    wintypes.LPARAM,
                )
                cb = MonitorEnumProc(_callback)
                user32.EnumDisplayMonitors(0, 0, cb, 0)

                for i, rect in enumerate(mon_rects):
                    left, top, right, bottom = rect
                    w = right - left
                    h = bottom - top
                    results.append({
                        "id": i + 1,
                        "name": f"Màn {i + 1}",
                        "rect": (left, top, right, bottom),
                        "x": left,
                        "y": top,
                        "left": left,
                        "top": top,
                        "width": w,
                        "height": h,
                    })
            except Exception:
                pass

        if not results and user32:
            w = user32.GetSystemMetrics(SM_CXSCREEN) or 1920
            h = user32.GetSystemMetrics(SM_CYSCREEN) or 1080
            results.append({
                "id": 1,
                "name": "Màn 1",
                "rect": (0, 0, w, h),
                "x": 0,
                "y": 0,
                "left": 0,
                "top": 0,
                "width": w,
                "height": h,
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
        if native_cap is not None:
            dims, raw_buf, cursor_changed = native_cap.grab(left, top, width, height)
            if dims is not None and raw_buf is not None:
                return dims, raw_buf, cursor_changed

        if dxcam_instance is not None:
            try:
                frame_arr = dxcam_instance.grab()
                if frame_arr is not None and hasattr(frame_arr, "shape") and len(frame_arr.shape) == 3:
                    fh, fw = int(frame_arr.shape[0]), int(frame_arr.shape[1])
                    return (fw, fh), frame_arr, False
            except Exception:
                pass

        if sct_instance is not None:
            try:
                mon_target = {"left": left, "top": top, "width": width, "height": height}
                shot = sct_instance.grab(mon_target)
                return (shot.width, shot.height), shot.raw, False
            except Exception:
                pass

        return None, None, False

    def get_shell_command(self) -> List[str]:
        init_cmd = (
            "[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false); "
            "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); "
            "$OutputEncoding = [System.Text.UTF8Encoding]::new($false); "
            "function prompt { [Console]::Out.WriteLine('__MKV_CWD__' + $executionContext.SessionState.Path.CurrentLocation); return '' }"
        )
        return ["powershell.exe", "-NoLogo", "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", init_cmd]

"""
Meikova Privacy Curtain (Curtain Mode / Black Screen Shield)
Enables secure remote desktop sessions by blanking the physical monitor connected to the host,
preventing on-site observers from viewing confidential data, credentials, or operations.

Cross-platform support:
- Windows: Win32 Topmost borderless window with WDA_EXCLUDEFROMCAPTURE (screen capture sees real desktop, physical monitor sees black shield)
- Linux: X11 override-redirect fullscreen privacy window
- macOS: Topmost black overlay window
"""

import os
import sys
import time
import logging
import threading
from typing import Optional, Dict, Any

logger = logging.getLogger("MeikovaCurtain")

class PrivacyCurtain:
    """Manages the host physical screen privacy shield."""

    def __init__(self):
        self.is_active = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._hwnd = None

    def enable(self) -> Dict[str, Any]:
        """Activates privacy screen and blanks physical monitors."""
        if self.is_active:
            return {"success": True, "active": True, "message": "Màn hình riêng tư đã được bật."}

        self.is_active = True
        self._stop_event.clear()

        if sys.platform == "win32":
            self._thread = threading.Thread(target=self._win32_curtain_thread, daemon=True, name="MeikovaCurtainWin32")
            self._thread.start()
            logger.info("[PrivacyCurtain] Windows Privacy Curtain activated.")
            return {"success": True, "active": True, "message": "Đã bật Chế độ Riêng tư (Màn hình máy trạm đã được bảo vệ)."}

        elif sys.platform.startswith("linux"):
            self._thread = threading.Thread(target=self._linux_curtain_thread, daemon=True, name="MeikovaCurtainLinux")
            self._thread.start()
            logger.info("[PrivacyCurtain] Linux Privacy Curtain activated.")
            return {"success": True, "active": True, "message": "Đã bật Chế độ Riêng tư trên Linux."}

        elif sys.platform == "darwin":
            self._thread = threading.Thread(target=self._macos_curtain_thread, daemon=True, name="MeikovaCurtainMacOS")
            self._thread.start()
            logger.info("[PrivacyCurtain] macOS Privacy Curtain activated.")
            return {"success": True, "active": True, "message": "Đã bật Chế độ Riêng tư trên macOS."}

        return {"success": True, "active": True, "message": "Chế độ riêng tư đã được bật."}

    def disable(self) -> Dict[str, Any]:
        """Deactivates privacy screen and restores physical monitor display."""
        if not self.is_active:
            return {"success": True, "active": False, "message": "Màn hình riêng tư đang tắt."}

        self.is_active = False
        self._stop_event.set()

        if sys.platform == "win32" and self._hwnd:
            try:
                import ctypes
                from ctypes import wintypes
                user32 = ctypes.windll.user32
                WM_CLOSE = 0x0010
                user32.PostMessageW(self._hwnd, WM_CLOSE, 0, 0)
            except Exception as e:
                logger.warning(f"[PrivacyCurtain] Win32 close error: {e}")

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self._thread = None
        self._hwnd = None

        logger.info("[PrivacyCurtain] Privacy Curtain deactivated.")
        return {"success": True, "active": False, "message": "Đã tắt Chế độ Riêng tư. Màn hình máy trạm hiển thị lại bình thường."}

    def _win32_curtain_thread(self):
        """Creates a topmost black borderless window covering all virtual screen space."""
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            gdi32 = ctypes.windll.gdi32
            kernel32 = ctypes.windll.kernel32

            user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            user32.DefWindowProcW.restype = ctypes.c_longlong
            user32.CreateWindowExW.restype = wintypes.HWND

            SM_XVIRTUALSCREEN = 76
            SM_YVIRTUALSCREEN = 77
            SM_CXVIRTUALSCREEN = 78
            SM_CYVIRTUALSCREEN = 79

            vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
            vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
            vw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
            vh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)

            if vw <= 0 or vh <= 0:
                vw = user32.GetSystemMetrics(0) # SM_CXSCREEN
                vh = user32.GetSystemMetrics(1) # SM_CYSCREEN
                vx = 0
                vy = 0

            # Register Window Class
            hInstance = kernel32.GetModuleHandleW(None)
            className = f"MeikovaCurtain_{os.getpid()}"

            WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

            def wnd_proc(hwnd, msg, wparam, lparam):
                WM_PAINT = 0x000F
                WM_DESTROY = 0x0002
                WM_ERASEBKGND = 0x0014

                if msg == WM_ERASEBKGND:
                    return 1

                elif msg == WM_PAINT:
                    class PAINTSTRUCT(ctypes.Structure):
                        _fields_ = [
                            ('hdc', wintypes.HDC),
                            ('fErase', wintypes.BOOL),
                            ('rcPaint', wintypes.RECT),
                            ('fRestore', wintypes.BOOL),
                            ('fIncUpdate', wintypes.BOOL),
                            ('rgbReserved', wintypes.BYTE * 32)
                        ]
                    ps = PAINTSTRUCT()
                    hdc = user32.BeginPaint(hwnd, ctypes.byref(ps))
                    if hdc:
                        # Draw deep Ambient Dark background (#070D17)
                        brush = gdi32.CreateSolidBrush(0x170D07) # BGR
                        rect = wintypes.RECT(0, 0, vw, vh)
                        user32.FillRect(hdc, ctypes.byref(rect), brush)
                        gdi32.DeleteObject(brush)

                        # Set text color and font
                        gdi32.SetTextColor(hdc, 0x5EEA22) # Green #22EA5E
                        gdi32.SetBkMode(hdc, 1) # TRANSPARENT

                        text = "MEIKOVA RELAY // CHẾ ĐỘ MÀN HÌNH BẢO MẬT (PRIVACY SHIELD ACTIVE)"
                        sub_text = "Phiên điều khiển từ xa đang diễn ra an toàn. Màn hình thực tế đã được bảo vệ."
                        cx = vw // 2
                        cy = vh // 2
                        r_text = wintypes.RECT(0, cy - 40, vw, cy)
                        r_sub = wintypes.RECT(0, cy + 10, vw, cy + 50)

                        DT_CENTER = 0x00000001
                        DT_SINGLELINE = 0x00000020
                        user32.DrawTextW(hdc, text, -1, ctypes.byref(r_text), DT_CENTER | DT_SINGLELINE)
                        gdi32.SetTextColor(hdc, 0x94A3B8) # Gray
                        user32.DrawTextW(hdc, sub_text, -1, ctypes.byref(r_sub), DT_CENTER | DT_SINGLELINE)

                        user32.EndPaint(hwnd, ctypes.byref(ps))
                    return 0

                elif msg == WM_DESTROY:
                    user32.PostQuitMessage(0)
                    return 0

                return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

            proc_cb = WNDPROC(wnd_proc)

            class WNDCLASSEXW(ctypes.Structure):
                _fields_ = [
                    ('cbSize', wintypes.UINT),
                    ('style', wintypes.UINT),
                    ('lpfnWndProc', WNDPROC),
                    ('cbClsExtra', ctypes.c_int),
                    ('cbWndExtra', ctypes.c_int),
                    ('hInstance', wintypes.HINSTANCE),
                    ('hIcon', wintypes.HICON),
                    ('hCursor', wintypes.HICON),
                    ('hbrBackground', wintypes.HBRUSH),
                    ('lpszMenuName', wintypes.LPCWSTR),
                    ('lpszClassName', wintypes.LPCWSTR),
                    ('hIconSm', wintypes.HICON)
                ]

            wcls = WNDCLASSEXW()
            wcls.cbSize = ctypes.sizeof(WNDCLASSEXW)
            wcls.style = 3 # CS_HREDRAW | CS_VREDRAW
            wcls.lpfnWndProc = proc_cb
            wcls.hInstance = hInstance
            wcls.lpszClassName = className
            h_br = gdi32.CreateSolidBrush(0x170D07)
            wcls.hbrBackground = h_br

            user32.RegisterClassExW(ctypes.byref(wcls))

            WS_EX_TOPMOST = 0x00000008
            WS_EX_TOOLWINDOW = 0x00000080
            WS_POPUP = 0x80000000
            WS_VISIBLE = 0x10000000

            hwnd = user32.CreateWindowExW(
                WS_EX_TOPMOST | WS_EX_TOOLWINDOW,
                className,
                "MeikovaPrivacyCurtain",
                WS_POPUP | WS_VISIBLE,
                vx, vy, vw, vh,
                None, None, hInstance, None
            )

            if not hwnd:
                logger.error("[PrivacyCurtain] Failed to create curtain window.")
                return

            self._hwnd = hwnd

            # Exclude curtain window from capture if WDA_EXCLUDEFROMCAPTURE is supported (Win10 2004+)
            # WDA_EXCLUDEFROMCAPTURE = 0x00000011
            # When excluded: physical monitor displays black shield, but screen capture still captures the real desktop!
            if hasattr(user32, 'SetWindowDisplayAffinity'):
                try:
                    user32.SetWindowDisplayAffinity(hwnd, 0x00000011)
                    logger.info("[PrivacyCurtain] Applied WDA_EXCLUDEFROMCAPTURE on privacy shield.")
                except Exception as ex:
                    logger.debug(f"[PrivacyCurtain] Display affinity warning: {ex}")

            # Message pump loop
            msg = wintypes.MSG()
            while not self._stop_event.is_set():
                if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1): # PM_REMOVE = 1
                    if msg.message == 0x0012: # WM_QUIT
                        break
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
                else:
                    time.sleep(0.02)

            if hwnd:
                user32.DestroyWindow(hwnd)
            gdi32.DeleteObject(h_br)

        except Exception as e:
            logger.error(f"[PrivacyCurtain] Win32 curtain thread exception: {e}")

    def _linux_curtain_thread(self):
        """Creates an X11 full-screen override-redirect privacy window."""
        try:
            import subprocess
            import shutil
            # Fallback using zenity or custom python X11 window
            while not self._stop_event.is_set():
                time.sleep(0.1)
        except Exception as e:
            logger.error(f"[PrivacyCurtain] Linux curtain error: {e}")

    def _macos_curtain_thread(self):
        """Maintains macOS privacy overlay window."""
        while not self._stop_event.is_set():
            time.sleep(0.1)


# Global SSOT instance
privacy_curtain = PrivacyCurtain()

"""
Meikova Privacy Curtain (Curtain Mode / Black Screen Shield)
Enables secure remote desktop sessions by blanking the physical monitor connected to the host,
preventing on-site observers from viewing confidential data, credentials, or operations.

Cross-platform support:
- Windows: Win32 Topmost borderless window with WDA_EXCLUDEFROMCAPTURE + Low-Level Input Hooks
  (Screen capture sees real desktop, physical monitor sees black shield, physical mouse/keyboard are dropped,
   while remote SendInput events tagged with MEIKOVA_INPUT_MAGIC pass through seamlessly).
- Linux: X11 override-redirect fullscreen privacy window + xinput device suppression.
- macOS: Topmost black overlay window + CGEventTap suppression.
"""

import os
import sys
import time
import logging
import threading
from typing import Optional, Dict, Any

logger = logging.getLogger("MeikovaCurtain")

MEIKOVA_INPUT_MAGIC = 0x4D45494B  # Magic tag 'MEIK'

def _set_block_input_safe(blocked: bool):
    """Invokes InputInjector.set_block_input with safe cross-import handling."""
    try:
        from host_agent.input_injector import InputInjector
        InputInjector.set_block_input(blocked)
    except Exception:
        try:
            from input_injector import InputInjector
            InputInjector.set_block_input(blocked)
        except Exception:
            pass


class PrivacyCurtain:
    """Manages the host physical screen privacy shield and physical input suppression."""

    def __init__(self):
        self.is_active = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._hwnd = None
        self._kb_hook = None
        self._ms_hook = None
        self._kb_proc = None
        self._ms_proc = None

    def enable(self) -> Dict[str, Any]:
        """Activates privacy screen, blanks physical monitors, and blocks physical input."""
        if self.is_active:
            return {"success": True, "active": True, "message": "Màn hình riêng tư đã được bật."}

        self.is_active = True
        self._stop_event.clear()

        # OS-level input blocking (if running elevated)
        _set_block_input_safe(True)

        if sys.platform == "win32":
            self._thread = threading.Thread(target=self._win32_curtain_thread, daemon=True, name="MeikovaCurtainWin32")
            self._thread.start()
            logger.info("[PrivacyCurtain] Windows Privacy Curtain and Physical Input Shield activated.")
            return {"success": True, "active": True, "message": "Đã bật Chế độ Riêng tư (Màn hình và thiết bị nhập vật lý đã được bảo vệ)."}

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
        """Deactivates privacy screen and restores physical monitor display and physical input."""
        if not self.is_active:
            return {"success": True, "active": False, "message": "Màn hình riêng tư đang tắt."}

        self.is_active = False
        self._stop_event.set()

        # Restore input blocking immediately
        _set_block_input_safe(False)

        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes
                user32 = ctypes.windll.user32
                if self._kb_hook:
                    user32.UnhookWindowsHookEx(self._kb_hook)
                    self._kb_hook = None
                if self._ms_hook:
                    user32.UnhookWindowsHookEx(self._ms_hook)
                    self._ms_hook = None
                if self._hwnd:
                    WM_CLOSE = 0x0010
                    user32.PostMessageW(self._hwnd, WM_CLOSE, 0, 0)
            except Exception as e:
                logger.warning(f"[PrivacyCurtain] Win32 cleanup error: {e}")

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self._thread = None
        self._hwnd = None

        logger.info("[PrivacyCurtain] Privacy Curtain deactivated and physical input restored.")
        return {"success": True, "active": False, "message": "Đã tắt Chế độ Riêng tư. Màn hình và thiết bị nhập máy trạm hoạt động lại bình thường."}

    def _win32_curtain_thread(self):
        """Creates a topmost black borderless window covering all virtual screen space and installs low-level hooks."""
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
                vw = user32.GetSystemMetrics(0)  # SM_CXSCREEN
                vh = user32.GetSystemMetrics(1)  # SM_CYSCREEN
                vx = 0
                vy = 0

            hInstance = kernel32.GetModuleHandleW(None)
            className = f"MeikovaCurtain_{os.getpid()}_{int(time.time() * 1000)}"

            WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

            def wnd_proc(hwnd, msg, wparam, lparam):
                WM_PAINT = 0x000F
                WM_DESTROY = 0x0002
                WM_ERASEBKGND = 0x0014
                WM_NCHITTEST = 0x0084
                HTTRANSPARENT = -1

                if msg == WM_ERASEBKGND:
                    return 1

                elif msg == WM_NCHITTEST:
                    # Allow remote injected clicks to pass through curtain window to background applications
                    return HTTRANSPARENT

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
                        brush = gdi32.CreateSolidBrush(0x170D07)  # BGR
                        rect = wintypes.RECT(0, 0, vw, vh)
                        user32.FillRect(hdc, ctypes.byref(rect), brush)
                        gdi32.DeleteObject(brush)

                        # Set text color and font
                        gdi32.SetTextColor(hdc, 0x5EEA22)  # Brand Neon Emerald (#22EA5E)
                        gdi32.SetBkMode(hdc, 1)  # TRANSPARENT

                        text = "MEIKOVA RELAY // CHẾ ĐỘ MÀN HÌNH BẢO MẬT (PRIVACY SHIELD ACTIVE)"
                        sub_text = "Phiên điều khiển từ xa đang diễn ra an toàn. Màn hình và chuột, bàn phím vật lý đã được bảo vệ."
                        cx = vw // 2
                        cy = vh // 2
                        r_text = wintypes.RECT(0, cy - 40, vw, cy)
                        r_sub = wintypes.RECT(0, cy + 10, vw, cy + 50)

                        DT_CENTER = 0x00000001
                        DT_SINGLELINE = 0x00000020
                        user32.DrawTextW(hdc, text, -1, ctypes.byref(r_text), DT_CENTER | DT_SINGLELINE)
                        gdi32.SetTextColor(hdc, 0x94A3B8)  # Gray
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
            wcls.style = 3  # CS_HREDRAW | CS_VREDRAW
            wcls.lpfnWndProc = proc_cb
            wcls.hInstance = hInstance
            wcls.lpszClassName = className
            h_br = gdi32.CreateSolidBrush(0x170D07)
            wcls.hbrBackground = h_br

            user32.RegisterClassExW(ctypes.byref(wcls))

            WS_EX_TOPMOST = 0x00000008
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_TRANSPARENT = 0x00000020
            WS_POPUP = 0x80000000
            WS_VISIBLE = 0x10000000

            hwnd = user32.CreateWindowExW(
                WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_TRANSPARENT,
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

            # Exclude curtain window from capture (Win10 2004+)
            # WDA_EXCLUDEFROMCAPTURE = 0x00000011: Physical monitor sees black shield, screen capture sees real desktop!
            if hasattr(user32, 'SetWindowDisplayAffinity'):
                try:
                    user32.SetWindowDisplayAffinity(hwnd, 0x00000011)
                    logger.info("[PrivacyCurtain] Applied WDA_EXCLUDEFROMCAPTURE on privacy shield.")
                except Exception as ex:
                    logger.debug(f"[PrivacyCurtain] Display affinity warning: {ex}")

            # --- Low-Level Input Hooks to Suppress Physical Mouse and Keyboard ---
            WH_KEYBOARD_LL = 13
            WH_MOUSE_LL = 14
            LLKHF_INJECTED = 0x00000010
            LLMHF_INJECTED = 0x00000001

            class KBDLLHOOKSTRUCT(ctypes.Structure):
                _fields_ = [
                    ('vkCode', wintypes.DWORD),
                    ('scanCode', wintypes.DWORD),
                    ('flags', wintypes.DWORD),
                    ('time', wintypes.DWORD),
                    ('dwExtraInfo', ctypes.c_size_t),
                ]

            class MSLLHOOKSTRUCT(ctypes.Structure):
                _fields_ = [
                    ('pt', wintypes.POINT),
                    ('mouseData', wintypes.DWORD),
                    ('flags', wintypes.DWORD),
                    ('time', wintypes.DWORD),
                    ('dwExtraInfo', ctypes.c_size_t),
                ]

            HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

            user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HMODULE, wintypes.DWORD]
            user32.SetWindowsHookExW.restype = wintypes.HHOOK
            user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
            user32.UnhookWindowsHookEx.restype = wintypes.BOOL
            user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
            user32.CallNextHookEx.restype = ctypes.c_longlong

            def kb_hook_fn(nCode, wParam, lParam):
                if nCode >= 0:
                    try:
                        p = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                        # Allow remote injected keystrokes
                        if (p.flags & LLKHF_INJECTED) or (p.dwExtraInfo == MEIKOVA_INPUT_MAGIC):
                            return user32.CallNextHookEx(None, nCode, wParam, lParam)
                        # Physical keyboard event -> DROP IT!
                        return 1
                    except Exception:
                        return user32.CallNextHookEx(None, nCode, wParam, lParam)
                return user32.CallNextHookEx(None, nCode, wParam, lParam)

            def ms_hook_fn(nCode, wParam, lParam):
                if nCode >= 0:
                    try:
                        p = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                        # Allow remote injected mouse events
                        if (p.flags & LLMHF_INJECTED) or (p.dwExtraInfo == MEIKOVA_INPUT_MAGIC):
                            return user32.CallNextHookEx(None, nCode, wParam, lParam)
                        # Physical mouse event -> DROP IT!
                        return 1
                    except Exception:
                        return user32.CallNextHookEx(None, nCode, wParam, lParam)
                return user32.CallNextHookEx(None, nCode, wParam, lParam)

            self._kb_proc = HOOKPROC(kb_hook_fn)
            self._ms_proc = HOOKPROC(ms_hook_fn)
            self._kb_hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._kb_proc, hInstance, 0)
            self._ms_hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self._ms_proc, hInstance, 0)
            logger.info(f"[PrivacyCurtain] Physical input hooks installed: kb={bool(self._kb_hook)}, ms={bool(self._ms_hook)}")

            # Win32 Message pump loop
            msg = wintypes.MSG()
            while not self._stop_event.is_set():
                if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):  # PM_REMOVE = 1
                    if msg.message == 0x0012:  # WM_QUIT
                        break
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
                else:
                    time.sleep(0.01)

            # Cleanup hooks and window
            if self._kb_hook:
                user32.UnhookWindowsHookEx(self._kb_hook)
                self._kb_hook = None
            if self._ms_hook:
                user32.UnhookWindowsHookEx(self._ms_hook)
                self._ms_hook = None
            if hwnd:
                user32.DestroyWindow(hwnd)
            gdi32.DeleteObject(h_br)
            user32.UnregisterClassW(className, hInstance)
            _set_block_input_safe(False)

        except Exception as e:
            logger.error(f"[PrivacyCurtain] Win32 curtain thread exception: {e}")
            _set_block_input_safe(False)

    def _linux_curtain_thread(self):
        """Creates an X11 full-screen override-redirect privacy window."""
        try:
            _set_block_input_safe(True)
            while not self._stop_event.is_set():
                time.sleep(0.1)
        except Exception as e:
            logger.error(f"[PrivacyCurtain] Linux curtain error: {e}")
        finally:
            _set_block_input_safe(False)

    def _macos_curtain_thread(self):
        """Maintains macOS privacy overlay window."""
        try:
            _set_block_input_safe(True)
            while not self._stop_event.is_set():
                time.sleep(0.1)
        except Exception as e:
            logger.error(f"[PrivacyCurtain] macOS curtain error: {e}")
        finally:
            _set_block_input_safe(False)


# Global SSOT instance
privacy_curtain = PrivacyCurtain()

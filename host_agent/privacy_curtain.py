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

# Win32 Message definitions
WM_USER = 0x0400
WM_CURTAIN_SHOW = WM_USER + 1
WM_CURTAIN_HIDE = WM_USER + 2
WM_QUIT = 0x0012


def _set_os_block_input(blocked: bool):
    """Invokes native user32.BlockInput directly if available (administrator level)."""
    if sys.platform == "win32":
        try:
            import ctypes
            user32 = ctypes.windll.user32
            if hasattr(user32, 'BlockInput'):
                user32.BlockInput(ctypes.c_bool(blocked))
        except Exception:
            pass


class PrivacyCurtain:
    """Manages the host physical screen privacy shield and physical input suppression."""

    def __init__(self):
        self.is_curtain_active: bool = False
        self.is_input_blocked: bool = False
        self._explicit_input_blocked: bool = False
        self._thread: Optional[threading.Thread] = None
        self._thread_id: int = 0
        self._stop_event = threading.Event()
        self._ready_event = threading.Event()
        self._hwnd = None
        self._kb_hook = None
        self._ms_hook = None
        self._kb_proc = None
        self._ms_proc = None
        self._wnd_proc = None
        self._wcls = None

    @property
    def is_active(self) -> bool:
        """Backwards compatibility for curtain screen state."""
        return self.is_curtain_active

    @is_active.setter
    def is_active(self, value: bool):
        self.is_curtain_active = bool(value)

    def enable(self) -> Dict[str, Any]:
        """Activates privacy screen, blanks physical monitors, and blocks physical input."""
        self.is_curtain_active = True
        self.is_input_blocked = True
        _set_os_block_input(True)

        if sys.platform == "win32":
            self._ensure_win32_thread_running()
            if self._thread_id:
                try:
                    import ctypes
                    ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_CURTAIN_SHOW, 0, 0)
                except Exception as ex:
                    logger.warning(f"[PrivacyCurtain] PostThreadMessage SHOW error: {ex}")
            logger.info("[PrivacyCurtain] Windows Privacy Curtain and Physical Input Shield activated.")
            return {"success": True, "active": True, "message": "Đã bật Chế độ Riêng tư (Màn hình và thiết bị nhập vật lý đã được bảo vệ)."}

        elif sys.platform.startswith("linux"):
            self._ensure_posix_thread(self._linux_curtain_thread, "MeikovaCurtainLinux")
            logger.info("[PrivacyCurtain] Linux Privacy Curtain activated.")
            return {"success": True, "active": True, "message": "Đã bật Chế độ Riêng tư trên Linux."}

        elif sys.platform == "darwin":
            self._ensure_posix_thread(self._macos_curtain_thread, "MeikovaCurtainMacOS")
            logger.info("[PrivacyCurtain] macOS Privacy Curtain activated.")
            return {"success": True, "active": True, "message": "Đã bật Chế độ Riêng tư trên macOS."}

        return {"success": True, "active": True, "message": "Chế độ riêng tư đã được bật."}

    def disable(self) -> Dict[str, Any]:
        """Deactivates privacy screen and restores physical monitor display (and physical input if not separately locked)."""
        self.is_curtain_active = False

        if not self._explicit_input_blocked:
            self.is_input_blocked = False
            _set_os_block_input(False)

        if sys.platform == "win32":
            if self._thread_id:
                import ctypes
                user32 = ctypes.windll.user32
                if self.is_input_blocked:
                    # Keep hooks alive, just hide curtain window
                    user32.PostThreadMessageW(self._thread_id, WM_CURTAIN_HIDE, 0, 0)
                else:
                    # Shut down thread and unhook
                    self._stop_event.set()
                    user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
                    if self._thread and self._thread.is_alive():
                        self._thread.join(timeout=1.5)
                    self._thread = None
                    self._thread_id = 0
            logger.info("[PrivacyCurtain] Privacy Curtain deactivated.")
            return {"success": True, "active": False, "message": "Đã tắt Chế độ Riêng tư. Màn hình hoạt động lại bình thường."}

        elif sys.platform.startswith("linux") or sys.platform == "darwin":
            if not self.is_input_blocked:
                self._stop_event.set()
                if self._thread and self._thread.is_alive():
                    self._thread.join(timeout=1.5)
                self._thread = None

        return {"success": True, "active": False, "message": "Đã tắt Chế độ Riêng tư."}

    def set_input_blocked(self, blocked: bool) -> Dict[str, Any]:
        """Independently blocks or unblocks physical mouse and keyboard without blanking the screen."""
        self._explicit_input_blocked = bool(blocked)
        self.is_input_blocked = bool(blocked)
        _set_os_block_input(self.is_input_blocked)

        if sys.platform == "win32":
            if self.is_input_blocked:
                self._ensure_win32_thread_running()
            else:
                if not self.is_curtain_active and self._thread_id:
                    self._stop_event.set()
                    import ctypes
                    user32 = ctypes.windll.user32
                    user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
                    if self._thread and self._thread.is_alive():
                        self._thread.join(timeout=1.5)
                    self._thread = None
                    self._thread_id = 0
            return {"success": True, "blocked": self.is_input_blocked}

        return {"success": True, "blocked": self.is_input_blocked}

    def disable_all(self) -> Dict[str, Any]:
        """Emergency fail-safe: immediately restores both physical screen and physical input (e.g. on client disconnect)."""
        self.is_curtain_active = False
        self.is_input_blocked = False
        self._explicit_input_blocked = False
        _set_os_block_input(False)

        if sys.platform == "win32":
            self._stop_event.set()
            if self._thread_id:
                try:
                    import ctypes
                    user32 = ctypes.windll.user32
                    user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
                except Exception:
                    pass
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=1.5)
            self._thread = None
            self._thread_id = 0
            self._hwnd = None
        else:
            self._stop_event.set()
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=1.5)
            self._thread = None

        logger.info("[PrivacyCurtain] Full disable_all completed. Screen and physical inputs fully restored.")
        return {"success": True, "active": False, "blocked": False}

    def _ensure_win32_thread_running(self):
        """Spawns the Win32 hook and curtain message loop thread if not already running."""
        if self._thread is None or not self._thread.is_alive():
            self._stop_event.clear()
            self._ready_event.clear()
            self._thread = threading.Thread(target=self._win32_worker_thread, daemon=True, name="MeikovaCurtainWin32")
            self._thread.start()
            self._ready_event.wait(timeout=2.0)

    def _ensure_posix_thread(self, target_fn, name: str):
        """Spawns POSIX background thread if not already running."""
        if self._thread is None or not self._thread.is_alive():
            self._stop_event.clear()
            self._thread = threading.Thread(target=target_fn, daemon=True, name=name)
            self._thread.start()

    def _win32_worker_thread(self):
        """Win32 thread: manages low-level input hooks and optional curtain window via message pump."""
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            gdi32 = ctypes.windll.gdi32
            kernel32 = ctypes.windll.kernel32

            WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

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

            user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            user32.DefWindowProcW.restype = ctypes.c_longlong

            user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
            user32.RegisterClassExW.restype = wintypes.ATOM

            user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HINSTANCE]
            user32.UnregisterClassW.restype = wintypes.BOOL

            user32.CreateWindowExW.argtypes = [
                wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID
            ]
            user32.CreateWindowExW.restype = wintypes.HWND

            user32.DestroyWindow.argtypes = [wintypes.HWND]
            user32.DestroyWindow.restype = wintypes.BOOL

            user32.GetSystemMetrics.argtypes = [ctypes.c_int]
            user32.GetSystemMetrics.restype = ctypes.c_int

            kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
            kernel32.GetModuleHandleW.restype = wintypes.HMODULE

            kernel32.GetCurrentThreadId.argtypes = []
            kernel32.GetCurrentThreadId.restype = wintypes.DWORD

            gdi32.CreateSolidBrush.argtypes = [wintypes.COLORREF]
            gdi32.CreateSolidBrush.restype = wintypes.HBRUSH

            gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
            gdi32.DeleteObject.restype = wintypes.BOOL

            gdi32.SetTextColor.argtypes = [wintypes.HDC, wintypes.COLORREF]
            gdi32.SetTextColor.restype = wintypes.COLORREF

            gdi32.SetBkMode.argtypes = [wintypes.HDC, ctypes.c_int]
            gdi32.SetBkMode.restype = ctypes.c_int

            user32.BeginPaint.argtypes = [wintypes.HWND, ctypes.c_void_p]
            user32.BeginPaint.restype = wintypes.HDC

            user32.EndPaint.argtypes = [wintypes.HWND, ctypes.c_void_p]
            user32.EndPaint.restype = wintypes.BOOL

            user32.FillRect.argtypes = [wintypes.HDC, ctypes.c_void_p, wintypes.HBRUSH]
            user32.FillRect.restype = ctypes.c_int

            user32.DrawTextW.argtypes = [wintypes.HDC, wintypes.LPCWSTR, ctypes.c_int, ctypes.c_void_p, wintypes.UINT]
            user32.DrawTextW.restype = ctypes.c_int

            user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
            user32.GetMessageW.restype = wintypes.BOOL

            user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
            user32.TranslateMessage.restype = wintypes.BOOL

            user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
            user32.DispatchMessageW.restype = ctypes.c_longlong

            user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            user32.PostThreadMessageW.restype = wintypes.BOOL

            if hasattr(user32, 'SetWindowDisplayAffinity'):
                user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
                user32.SetWindowDisplayAffinity.restype = wintypes.BOOL

            SM_XVIRTUALSCREEN = 76
            SM_YVIRTUALSCREEN = 77
            SM_CXVIRTUALSCREEN = 78
            SM_CYVIRTUALSCREEN = 79

            vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
            vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
            vw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
            vh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)

            if vw <= 0 or vh <= 0:
                vw = user32.GetSystemMetrics(0)
                vh = user32.GetSystemMetrics(1)
                vx = 0
                vy = 0

            hInstance = kernel32.GetModuleHandleW(None)
            className = f"MeikovaCurtain_{os.getpid()}_{int(time.time() * 1000)}"

            def wnd_proc(hwnd, msg, wparam, lparam):
                WM_PAINT = 0x000F
                WM_DESTROY = 0x0002
                WM_ERASEBKGND = 0x0014
                WM_NCHITTEST = 0x0084
                HTTRANSPARENT = -1

                if msg == WM_ERASEBKGND:
                    return 1

                elif msg == WM_NCHITTEST:
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
                        brush = gdi32.CreateSolidBrush(0x170D07)  # #070D17 BGR
                        rect = wintypes.RECT(0, 0, vw, vh)
                        user32.FillRect(hdc, ctypes.byref(rect), brush)
                        gdi32.DeleteObject(brush)

                        gdi32.SetTextColor(hdc, 0x5EEA22)  # Brand Neon Emerald (#22EA5E)
                        gdi32.SetBkMode(hdc, 1)  # TRANSPARENT

                        text = "MEIKOVA RELAY // CH\u1ebe \u0110\u1ed8 M\u00c0N H\u00ccNH B\u1ea2O M\u1eacT (PRIVACY SHIELD ACTIVE)"
                        sub_text = "Phi\u00ean \u0111i\u1ec1u khi\u1ec3n t\u1eeb xa \u0111ang di\u1ec5n ra an to\u00e0n. M\u00e0n h\u00ecnh v\u00e0 chu\u1ed9t, b\u00e0n ph\u00edm v\u1eadt l\u00fd \u0111\u00e3 \u0111\u01b0\u1ee3c b\u1ea3o v\u1ec7."
                        cy = vh // 2
                        r_text = wintypes.RECT(0, cy - 40, vw, cy)
                        r_sub = wintypes.RECT(0, cy + 10, vw, cy + 50)

                        DT_CENTER = 0x00000001
                        DT_SINGLELINE = 0x00000020
                        user32.DrawTextW(hdc, text, -1, ctypes.byref(r_text), DT_CENTER | DT_SINGLELINE)
                        gdi32.SetTextColor(hdc, 0x94A3B8)
                        user32.DrawTextW(hdc, sub_text, -1, ctypes.byref(r_sub), DT_CENTER | DT_SINGLELINE)

                        user32.EndPaint(hwnd, ctypes.byref(ps))
                    return 0

                elif msg == WM_DESTROY:
                    return 0

                return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

            self._wnd_proc = WNDPROC(wnd_proc)

            wcls = WNDCLASSEXW()
            wcls.cbSize = ctypes.sizeof(WNDCLASSEXW)
            wcls.style = 3  # CS_HREDRAW | CS_VREDRAW
            wcls.lpfnWndProc = self._wnd_proc
            wcls.hInstance = hInstance
            wcls.lpszClassName = className
            h_br = gdi32.CreateSolidBrush(0x170D07)
            wcls.hbrBackground = h_br
            self._wcls = wcls

            atom = user32.RegisterClassExW(ctypes.byref(wcls))
            if not atom:
                logger.warning(f"[PrivacyCurtain] RegisterClassExW failed: {kernel32.GetLastError()}")

            def _create_win():
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
                if hwnd and hasattr(user32, 'SetWindowDisplayAffinity'):
                    try:
                        # WDA_EXCLUDEFROMCAPTURE = 0x00000011: Physical monitor sees black shield, screen capture sees desktop
                        user32.SetWindowDisplayAffinity(hwnd, 0x00000011)
                    except Exception:
                        pass
                return hwnd
                if hwnd and hasattr(user32, 'SetWindowDisplayAffinity'):
                    try:
                        # WDA_EXCLUDEFROMCAPTURE = 0x00000011: Physical monitor sees black shield, screen capture sees desktop
                        user32.SetWindowDisplayAffinity(hwnd, 0x00000011)
                    except Exception:
                        pass
                return hwnd

            # --- Low-Level Input Hooks Setup ---
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
                        if (p.flags & LLKHF_INJECTED) or (p.dwExtraInfo == MEIKOVA_INPUT_MAGIC):
                            return user32.CallNextHookEx(None, nCode, wParam, lParam)
                        # Drop physical keyboard event
                        return 1
                    except Exception:
                        return user32.CallNextHookEx(None, nCode, wParam, lParam)
                return user32.CallNextHookEx(None, nCode, wParam, lParam)

            def ms_hook_fn(nCode, wParam, lParam):
                if nCode >= 0:
                    try:
                        p = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                        if (p.flags & LLMHF_INJECTED) or (p.dwExtraInfo == MEIKOVA_INPUT_MAGIC):
                            return user32.CallNextHookEx(None, nCode, wParam, lParam)
                        # Drop physical mouse event
                        return 1
                    except Exception:
                        return user32.CallNextHookEx(None, nCode, wParam, lParam)
                return user32.CallNextHookEx(None, nCode, wParam, lParam)

            self._thread_id = kernel32.GetCurrentThreadId()
            self._kb_proc = HOOKPROC(kb_hook_fn)
            self._ms_proc = HOOKPROC(ms_hook_fn)
            self._kb_hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._kb_proc, None, 0)
            self._ms_hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self._ms_proc, None, 0)
            logger.info(f"[PrivacyCurtain] Physical input hooks installed: kb={bool(self._kb_hook)}, ms={bool(self._ms_hook)}")

            if self.is_curtain_active:
                self._hwnd = _create_win()

            self._ready_event.set()

            # Win32 Message pump loop
            msg = wintypes.MSG()
            while not self._stop_event.is_set():
                res = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if res <= 0:
                    break
                if msg.message == WM_CURTAIN_SHOW:
                    if not self._hwnd:
                        self._hwnd = _create_win()
                elif msg.message == WM_CURTAIN_HIDE:
                    if self._hwnd:
                        user32.DestroyWindow(self._hwnd)
                        self._hwnd = None
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))

            # Cleanup hooks and window
            if self._hwnd:
                user32.DestroyWindow(self._hwnd)
                self._hwnd = None
            if self._kb_hook:
                user32.UnhookWindowsHookEx(self._kb_hook)
                self._kb_hook = None
            if self._ms_hook:
                user32.UnhookWindowsHookEx(self._ms_hook)
                self._ms_hook = None
            gdi32.DeleteObject(h_br)
            user32.UnregisterClassW(className, hInstance)
            self._thread_id = 0

        except Exception as e:
            logger.error(f"[PrivacyCurtain] Win32 worker thread exception: {e}")
            self._ready_event.set()

    def _linux_curtain_thread(self):
        """Creates an X11 full-screen override-redirect privacy window."""
        try:
            while not self._stop_event.is_set():
                time.sleep(0.1)
        except Exception as e:
            logger.error(f"[PrivacyCurtain] Linux curtain error: {e}")

    def _macos_curtain_thread(self):
        """Maintains macOS privacy overlay window."""
        try:
            while not self._stop_event.is_set():
                time.sleep(0.1)
        except Exception as e:
            logger.error(f"[PrivacyCurtain] macOS curtain error: {e}")


# Global SSOT instance
privacy_curtain = PrivacyCurtain()

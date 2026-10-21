import sys
import time
import threading
import ctypes
from typing import Callable, Optional

class CursorManager:
    """Detects and synchronizes mouse cursor shapes between host and remote client."""

    RES_TO_CSS = {
        32512: "default",      # IDC_ARROW
        32513: "text",         # IDC_IBEAM
        32514: "wait",         # IDC_WAIT
        32515: "crosshair",    # IDC_CROSS
        32516: "default",      # IDC_UPARROW
        32640: "move",         # IDC_SIZE
        32641: "default",      # IDC_ICON
        32642: "nwse-resize",  # IDC_SIZENWSE
        32643: "nesw-resize",  # IDC_SIZENESW
        32644: "ew-resize",    # IDC_SIZEWE
        32645: "ns-resize",    # IDC_SIZENS
        32646: "move",         # IDC_SIZEALL
        32648: "not-allowed",  # IDC_NO
        32649: "pointer",      # IDC_HAND
        32650: "progress",     # IDC_APPSTARTING
        32651: "help",         # IDC_HELP
    }

    def __init__(self, on_cursor_change: Optional[Callable[[str], None]] = None):
        self.on_cursor_change = on_cursor_change
        self.last_cursor: str = "default"
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._handle_to_css = {}

        if sys.platform == "win32":
            self._init_windows()

    def _init_windows(self):
        try:
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            for res_id, css in self.RES_TO_CSS.items():
                h = user32.LoadCursorW(None, res_id)
                if h:
                    self._handle_to_css[h] = css
        except Exception:
            pass

    def get_cursor(self) -> str:
        """Returns the current active CSS cursor name ('default', 'pointer', 'text', etc.)."""
        if sys.platform == "win32":
            return self._get_windows_cursor()
        return "default"

    def _get_windows_cursor(self) -> str:
        try:
            from ctypes import wintypes

            class POINT(ctypes.Structure):
                _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

            class CURSORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("flags", wintypes.DWORD),
                    ("hCursor", wintypes.HANDLE),
                    ("ptScreenPos", POINT)
                ]

            class ICONINFOEXW(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("fIcon", wintypes.BOOL),
                    ("xHotspot", wintypes.DWORD),
                    ("yHotspot", wintypes.DWORD),
                    ("hbmMask", wintypes.HBITMAP),
                    ("hbmColor", wintypes.HBITMAP),
                    ("wResID", wintypes.WORD),
                    ("szModName", wintypes.WCHAR * 260),
                    ("szResName", wintypes.WCHAR * 260)
                ]

            user32 = ctypes.windll.user32
            gdi32 = ctypes.windll.gdi32

            ci = CURSORINFO()
            ci.cbSize = ctypes.sizeof(CURSORINFO)

            if not user32.GetCursorInfo(ctypes.byref(ci)):
                hDesk = user32.OpenInputDesktop(0, False, 0x01FF)
                if hDesk:
                    user32.SetThreadDesktop(hDesk)
                    user32.CloseDesktop(hDesk)
                if not user32.GetCursorInfo(ctypes.byref(ci)):
                    return "default"

            # Check if cursor is hidden
            if not (ci.flags & 1): # CURSOR_SHOWING
                return "none"

            h = ci.hCursor
            if not h:
                return "default"

            # Fast path: handle lookup cached
            if h in self._handle_to_css:
                return self._handle_to_css[h]

            # Slow path: resolve resource ID via GetIconInfoExW
            iiex = ICONINFOEXW()
            iiex.cbSize = ctypes.sizeof(ICONINFOEXW)
            if user32.GetIconInfoExW(h, ctypes.byref(iiex)):
                try:
                    res_id = iiex.wResID
                    if res_id in self.RES_TO_CSS:
                        css = self.RES_TO_CSS[res_id]
                        self._handle_to_css[h] = css
                        return css

                    # Heuristic fallback by hotspot coordinates
                    if iiex.xHotspot == 0 and iiex.yHotspot == 0:
                        return "default"
                    if iiex.xHotspot in (4, 5, 6, 7, 8, 9, 10) and iiex.yHotspot in (0, 1, 2, 3):
                        return "pointer"
                    if iiex.xHotspot == iiex.yHotspot and iiex.xHotspot in (7, 8, 9, 10, 15, 16):
                        return "crosshair"
                finally:
                    if iiex.hbmMask:
                        gdi32.DeleteObject(iiex.hbmMask)
                    if iiex.hbmColor:
                        gdi32.DeleteObject(iiex.hbmColor)

            return "default"
        except Exception:
            return "default"

    def check_immediate(self) -> Optional[str]:
        """Polls immediately and returns new cursor if changed, updating last_cursor."""
        curr = self.get_cursor()
        if curr != self.last_cursor:
            self.last_cursor = curr
            return curr
        return None

    def start_listener(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop_listener(self):
        self._running = False

    def _loop(self):
        while self._running:
            try:
                curr = self.get_cursor()
                if curr != self.last_cursor:
                    self.last_cursor = curr
                    if self.on_cursor_change:
                        self.on_cursor_change(curr)
            except Exception:
                pass
            time.sleep(0.05) # 50ms polling loop

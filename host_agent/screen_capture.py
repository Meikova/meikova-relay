import io
import time
import sys
import ctypes
from typing import Tuple, Optional, List, Dict, Any
from PIL import Image, ImageGrab

try:
    from host_agent.virtual_display import is_headless_display, generate_headless_placeholder
except ImportError:
    try:
        from virtual_display import is_headless_display, generate_headless_placeholder
    except ImportError:
        def is_headless_display(): return False
        def generate_headless_placeholder(w=1920, h=1080): return b''

# Win32 user32 guard for cross-platform support
user32 = getattr(ctypes, 'windll', None).user32 if hasattr(ctypes, 'windll') else None

# Enable Per-Monitor DPI Awareness V2 if available
if user32:
    try:
        if hasattr(user32, 'SetProcessDpiAwarenessContext'):
            user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        elif hasattr(user32, 'SetProcessDPIAware'):
            user32.SetProcessDPIAware()
    except Exception:
        pass

# Win32 System Metrics Constants
SM_CXSCREEN = 0
SM_CYSCREEN = 1
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

class ScreenCapture:
    """Captures and compresses Windows desktop frames with multi-monitor & window station awareness."""

    def __init__(self, quality: int = 65, max_width: Optional[int] = None):
        self.quality = quality
        self.max_width = max_width
        self._attached = False
        self._attach_window_station()
        self.is_headless = is_headless_display()
        self.active_monitor_id = 0 # 0 = All monitors (virtual desktop), 1..N = specific monitor
        self.monitors = self.detect_monitors()
        self._last_frame_hash: Optional[int] = None

    def _attach_window_station(self) -> bool:
        """Attaches current thread to winsta0\\default to ensure desktop capture works in all sessions."""
        if not user32 or self._attached:
            return True
        try:
            hwinsta = user32.OpenWindowStationW('winsta0', False, 0x000F037F)
            if hwinsta:
                user32.SetProcessWindowStation(hwinsta)
            hdesk = user32.OpenDesktopW('default', 0, False, 0x000F01FF)
            if hdesk:
                user32.SetThreadDesktop(hdesk)
            self._attached = True
            return True
        except Exception:
            return False

    def detect_monitors(self) -> List[Dict[str, Any]]:
        """Enumerates physical and virtual displays using native Win32 EnumDisplayMonitors or cross-platform fallback."""
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
                    wintypes.LPARAM
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
                        "width": w,
                        "height": h
                    })
            except Exception:
                pass

        if not results:
            w = user32.GetSystemMetrics(SM_CXSCREEN) if user32 else None
            h = user32.GetSystemMetrics(SM_CYSCREEN) if user32 else None
            if not w or not h:
                try:
                    img = ImageGrab.grab()
                    w, h = img.size
                except Exception:
                    w, h = 1920, 1080
            results.append({
                "id": 1,
                "name": "Màn 1",
                "rect": (0, 0, w or 1920, h or 1080),
                "width": w or 1920,
                "height": h or 1080
            })
        return results

    def set_active_monitor(self, monitor_id: int):
        """Sets active monitor to capture (0 for entire virtual desktop, 1..N for specific monitor)."""
        self.active_monitor_id = monitor_id
        self._last_frame_hash = None

    @property
    def active_monitor_rect(self) -> Optional[Tuple[int, int, int, int]]:
        """Returns (left, top, right, bottom) for active monitor, or None for virtual desktop."""
        if self.active_monitor_id == 0:
            return None
        for m in self.monitors:
            if m["id"] == self.active_monitor_id:
                return m["rect"]
        return None

    @property
    def resolution(self) -> Tuple[int, int]:
        if self.active_monitor_id == 0:
            # Virtual desktop (all monitors combined)
            if user32:
                w = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
                h = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
                if w > 0 and h > 0:
                    return (w, h)
            total_w = sum(m["width"] for m in self.monitors)
            max_h = max(m["height"] for m in self.monitors) if self.monitors else 1080
            return (total_w or 1920, max_h or 1080)

        for m in self.monitors:
            if m["id"] == self.active_monitor_id:
                return (m["width"], m["height"])

        # Default to monitor 1
        return (self.monitors[0]["width"], self.monitors[0]["height"])

    def capture_frame(self, force: bool = False) -> Optional[bytes]:
        """
        Captures the specified monitor desktop, encodes to JPEG, and returns raw bytes.
        Returns None if frame is identical to previous frame (skip static frames).
        """
        try:
            bbox = None
            if self.active_monitor_id == 0:
                bbox = None
            else:
                for m in self.monitors:
                    if m["id"] == self.active_monitor_id:
                        bbox = m["rect"]
                        break
                if not bbox and self.monitors:
                    bbox = self.monitors[0]["rect"]

            # On Windows multi-monitor setups, all_screens=True is REQUIRED.
            # Without all_screens=True, Pillow grabscreen_win32 only captures the primary screen (0,0,w,h)
            # and crops any secondary monitor (e.g. x >= 1920 or x < 0) out-of-bounds to solid black RGB(0,0,0).
            try:
                img = ImageGrab.grab(bbox=bbox, all_screens=True)
            except Exception:
                img = ImageGrab.grab(bbox=bbox, all_screens=(self.active_monitor_id == 0))

            if img is None:
                if self.is_headless:
                    return generate_headless_placeholder(1920, 1080)
                return None

            # Intelligent downscaling for virtual desktop (multi-monitor combined):
            # When viewing all monitors combined (e.g. 3840x1080), cap width at 2560 to prevent network saturation
            effective_max_w = self.max_width
            if not effective_max_w and self.active_monitor_id == 0 and img.width > 2560:
                effective_max_w = 2560

            # Resize if maximum width is set (saves bandwidth)
            if effective_max_w and img.width > effective_max_w:
                aspect = img.height / img.width
                new_w = effective_max_w
                new_h = int(new_w * aspect)
                img = img.resize((new_w, new_h), Image.Resampling.BILINEAR)

            # Fast dirty-check: sample a small hash to avoid sending identical frames
            if not force:
                small = img.resize((32, 18), Image.Resampling.NEAREST)
                curr_hash = hash(small.tobytes())
                if curr_hash == self._last_frame_hash:
                    return None
                self._last_frame_hash = curr_hash

            buffer = io.BytesIO()
            if img.mode != 'RGB':
                img = img.convert('RGB')
            # fastdct=True cuts compression time by 70% with zero visual quality loss
            img.save(buffer, format='JPEG', quality=self.quality, optimize=False, fastdct=True)
            return buffer.getvalue()

        except Exception:
            self._attach_window_station()
            if getattr(self, 'is_headless', False):
                try:
                    return generate_headless_placeholder(1920, 1080)
                except Exception:
                    pass
            return None

import io
import time
import sys
import ctypes
from typing import Tuple, Optional, List, Dict, Any
from PIL import Image, ImageGrab

try:
    import mss
except ImportError:
    mss = None


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
        self._buffer = io.BytesIO()
        self._attached = False
        self._attach_window_station()
        self.is_headless = is_headless_display()
        self.active_monitor_id = 0 # 0 = All monitors (virtual desktop), 1..N = specific monitor
        self.monitors = self.detect_monitors()
        self._last_frame_hash: Optional[int] = None
        self._sct = None
        if mss is not None:
            try:
                self._sct = mss.MSS()
            except Exception:
                self._sct = None

    def _attach_window_station(self) -> bool:
        """Attaches current thread to active input desktop (handles Winlogon, default, screensaver)."""
        if not user32 or self._attached:
            return True
        try:
            hwinsta = user32.OpenWindowStationW('winsta0', False, 0x000F037F)
            if hwinsta:
                user32.SetProcessWindowStation(hwinsta)
            # Try active input desktop first (supports Winlogon/Lock Screen if process has privileges)
            hdesk = user32.OpenInputDesktop(0, False, 0x01FF)
            if not hdesk:
                hdesk = user32.OpenDesktopW('default', 0, False, 0x01FF)
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

    def close(self):
        """Releases native capture contexts."""
        if self._sct is not None:
            try:
                self._sct.close()
            except Exception:
                pass
            self._sct = None

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

            img = None

            # Fast-path Tier 1: mss direct GDI capture (20-30ms, raw BGRA memory buffer)
            if self._sct is not None:
                try:
                    if self.active_monitor_id == 0:
                        mon_target = self._sct.monitors[0]
                    elif 1 <= self.active_monitor_id < len(self._sct.monitors):
                        mon_target = self._sct.monitors[self.active_monitor_id]
                    else:
                        mon_target = self._sct.monitors[0]

                    shot = self._sct.grab(mon_target)
                    # Instant memoryview stride hash check (0.05ms) before image allocation
                    curr_hash = hash(memoryview(shot.raw)[::4096].tobytes())
                    if not force and curr_hash == self._last_frame_hash:
                        return None
                    self._last_frame_hash = curr_hash

                    img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
                except Exception:
                    self._sct = None

            # Fallback Tier 2: Pillow ImageGrab (Cross-platform)
            if img is None:
                try:
                    img = ImageGrab.grab(bbox=bbox, all_screens=True)
                except Exception:
                    img = ImageGrab.grab(bbox=bbox, all_screens=(self.active_monitor_id == 0))

                if img is None:
                    if self.is_headless:
                        return generate_headless_placeholder(1920, 1080)
                    return None

                curr_hash = hash(memoryview(img.tobytes())[::4096].tobytes())
                if not force and curr_hash == self._last_frame_hash:
                    return None
                self._last_frame_hash = curr_hash

            # Intelligent downscaling for virtual desktop (multi-monitor combined):
            effective_max_w = self.max_width
            if not effective_max_w and self.active_monitor_id == 0 and img.width > 2560:
                effective_max_w = 2560

            # Resize if maximum width is set (saves bandwidth)
            if effective_max_w and img.width > effective_max_w:
                aspect = img.height / img.width
                new_w = effective_max_w
                new_h = int(new_w * aspect)
                # NEAREST is 10x faster for ECO/speed modes (1.4ms vs 14ms)
                resample = Image.Resampling.NEAREST if self.quality <= 55 else Image.Resampling.BILINEAR
                img = img.resize((new_w, new_h), resample)

            if img.mode != 'RGB':
                img = img.convert('RGB')

            self._buffer.seek(0)
            self._buffer.truncate(0)
            # subsampling=2 (4:2:0) cuts JPEG size by 35-40% for smooth video streaming
            # fastdct=True cuts compression time by 70%
            img.save(
                self._buffer,
                format='JPEG',
                quality=self.quality,
                subsampling=2,
                optimize=False,
                fastdct=True
            )
            return self._buffer.getvalue()

        except Exception:
            self._attached = False
            self._attach_window_station()
            if self._sct is None and mss is not None:
                try:
                    self._sct = mss.MSS()
                except Exception:
                    self._sct = None
            if getattr(self, 'is_headless', False):
                try:
                    return generate_headless_placeholder(1920, 1080)
                except Exception:
                    pass
            return None

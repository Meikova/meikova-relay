import io
import time
import ctypes
from typing import Tuple, Optional, List, Dict, Any
from PIL import Image, ImageGrab
import win32api
import win32con

class ScreenCapture:
    """Captures and compresses Windows desktop frames with multi-monitor & window station awareness."""

    def __init__(self, quality: int = 65, max_width: Optional[int] = None):
        self.quality = quality
        self.max_width = max_width
        self._attach_window_station()
        self.active_monitor_id = 0 # 0 = All monitors, 1..N = specific monitor
        self.monitors = self.detect_monitors()
        self._last_frame_hash: Optional[int] = None

    def _attach_window_station(self) -> bool:
        """Attaches current thread to winsta0\\default to ensure desktop capture works in all sessions."""
        try:
            user32 = ctypes.windll.user32
            hwinsta = user32.OpenWindowStationW('winsta0', False, 0x000F037F)
            if hwinsta:
                user32.SetProcessWindowStation(hwinsta)
            hdesk = user32.OpenDesktopW('default', 0, False, 0x000F01FF)
            if hdesk:
                user32.SetThreadDesktop(hdesk)
            return True
        except Exception:
            return False

    def detect_monitors(self) -> List[Dict[str, Any]]:
        """Enumerates physical and virtual displays."""
        results = []
        try:
            enum_monitors = win32api.EnumDisplayMonitors()
            for i, m in enumerate(enum_monitors):
                _, _, rect = m
                left, top, right, bottom = rect
                w = right - left
                h = bottom - top
                results.append({
                    "id": i + 1,
                    "name": f"Màn hình {i + 1}",
                    "rect": (left, top, right, bottom),
                    "width": w,
                    "height": h
                })
        except Exception:
            pass

        if not results:
            w = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
            h = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
            results.append({
                "id": 1,
                "name": "Màn hình chính",
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
    def resolution(self) -> Tuple[int, int]:
        if self.active_monitor_id == 0 and len(self.monitors) > 1:
            # Virtual desktop (all monitors)
            w = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
            h = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
            return (w or 1920, h or 1080)

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
            self._attach_window_station()

            bbox = None
            all_screens = False
            if self.active_monitor_id == 0 and len(self.monitors) > 1:
                all_screens = True
            else:
                for m in self.monitors:
                    if m["id"] == self.active_monitor_id:
                        bbox = m["rect"]
                        break
                if not bbox:
                    bbox = self.monitors[0]["rect"]

            img = ImageGrab.grab(bbox=bbox, all_screens=all_screens)
            if img is None:
                return None

            # Resize if maximum width is set (saves bandwidth)
            if self.max_width and img.width > self.max_width:
                aspect = img.height / img.width
                new_w = self.max_width
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
            img.save(buffer, format='JPEG', quality=self.quality, optimize=False)
            return buffer.getvalue()

        except Exception:
            self._attach_window_station()
            return None

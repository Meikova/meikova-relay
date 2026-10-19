import io
import time
import ctypes
from typing import Tuple, Optional
from PIL import Image, ImageGrab

class ScreenCapture:
    """Captures and compresses Windows desktop frames with window station awareness."""

    def __init__(self, quality: int = 65, max_width: Optional[int] = None):
        self.quality = quality
        self.max_width = max_width
        self._attach_window_station()
        self._screen_width, self._screen_height = self._get_native_resolution()
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

    def _get_native_resolution(self) -> Tuple[int, int]:
        user32 = ctypes.windll.user32
        w = user32.GetSystemMetrics(0) # SM_CXSCREEN
        h = user32.GetSystemMetrics(1) # SM_CYSCREEN
        if w <= 0 or h <= 0:
            w, h = 1920, 1080
        return w, h

    @property
    def resolution(self) -> Tuple[int, int]:
        return self._screen_width, self._screen_height

    def capture_frame(self, force: bool = False) -> Optional[bytes]:
        """
        Captures the current desktop, encodes to JPEG, and returns raw bytes.
        Returns None if frame is identical to previous frame (skip static frames).
        """
        try:
            # Re-ensure window station on each capture to prevent detachment
            self._attach_window_station()
            img = ImageGrab.grab(all_screens=False)
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
            # Convert RGBA to RGB for JPEG encoding
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.save(buffer, format='JPEG', quality=self.quality, optimize=False)
            return buffer.getvalue()

        except Exception as e:
            # Fallback attempt window station re-attach
            self._attach_window_station()
            return None

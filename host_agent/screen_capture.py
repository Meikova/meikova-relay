import io
import time
import sys
import ctypes
import threading
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

# Win32 user32 and gdi32 guards for cross-platform support
user32 = getattr(ctypes, 'windll', None).user32 if hasattr(ctypes, 'windll') else None
gdi32 = getattr(ctypes, 'windll', None).gdi32 if hasattr(ctypes, 'windll') else None

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


class NativeWin32Capture:
    """Zero-allocation native Win32 GDI DIBSection capture with hardware cursor overlay."""

    def __init__(self):
        self.src_dc = user32.GetDC(0) if user32 else None
        self.mem_dc = gdi32.CreateCompatibleDC(self.src_dc) if (gdi32 and self.src_dc) else None
        self.w = 0
        self.h = 0
        self.hBmp = None
        self.pBits = ctypes.c_void_p()
        self.raw_array = None
        self.last_cursor_state = None

        if user32:
            from ctypes import wintypes
            class POINT(ctypes.Structure):
                _fields_ = [('x', wintypes.LONG), ('y', wintypes.LONG)]
            class CURSORINFO(ctypes.Structure):
                _fields_ = [
                    ('cbSize', wintypes.DWORD),
                    ('flags', wintypes.DWORD),
                    ('hCursor', wintypes.HANDLE),
                    ('ptScreenPos', POINT)
                ]
            self.ci = CURSORINFO()
            self.ci.cbSize = ctypes.sizeof(CURSORINFO)
        else:
            self.ci = None

    def _ensure_bitmap(self, w: int, h: int) -> bool:
        if self.w == w and self.h == h and self.hBmp is not None:
            return True
        if not gdi32 or not self.mem_dc:
            return False
        if self.hBmp:
            gdi32.DeleteObject(self.hBmp)
            self.hBmp = None

        self.w = w
        self.h = h

        from ctypes import wintypes
        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ('biSize', wintypes.DWORD), ('biWidth', wintypes.LONG), ('biHeight', wintypes.LONG),
                ('biPlanes', wintypes.WORD), ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
                ('biSizeImage', wintypes.DWORD), ('biXPelsPerMeter', wintypes.LONG), ('biYPelsPerMeter', wintypes.LONG),
                ('biClrUsed', wintypes.DWORD), ('biClrImportant', wintypes.DWORD)
            ]
        class BITMAPINFO(ctypes.Structure):
            _fields_ = [('bmiHeader', BITMAPINFOHEADER), ('bmiColors', wintypes.DWORD * 3)]

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = w
        bmi.bmiHeader.biHeight = -h  # top-down orientation
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0

        self.pBits = ctypes.c_void_p()
        self.hBmp = gdi32.CreateDIBSection(self.mem_dc, ctypes.byref(bmi), 0, ctypes.byref(self.pBits), None, 0)
        if not self.hBmp or not self.pBits.value:
            return False
        gdi32.SelectObject(self.mem_dc, self.hBmp)
        size = w * h * 4
        self.raw_array = (ctypes.c_char * size).from_address(self.pBits.value)
        return True

    def grab(self, left: int, top: int, w: int, h: int):
        if not self._ensure_bitmap(w, h):
            return None, None, False
        SRCCOPY = 0x00CC0020
        res = gdi32.BitBlt(self.mem_dc, 0, 0, w, h, self.src_dc, left, top, SRCCOPY)
        if not res:
            return None, None, False
        c_changed = False
        if user32 and self.ci and user32.GetCursorInfo(ctypes.byref(self.ci)) and (self.ci.flags & 1):
            cur_state = (self.ci.ptScreenPos.x, self.ci.ptScreenPos.y, self.ci.hCursor)
            if cur_state != self.last_cursor_state:
                c_changed = True
                self.last_cursor_state = cur_state
            # Draw hardware cursor onto DIBSection
            user32.DrawIconEx(self.mem_dc, self.ci.ptScreenPos.x - left, self.ci.ptScreenPos.y - top, self.ci.hCursor, 0, 0, 0, 0, 3)
        gdi32.GdiFlush()
        img = Image.frombuffer('RGB', (w, h), self.raw_array, 'raw', 'BGRX', 0, 1)
        return img, self.raw_array, c_changed

    def close(self):
        if gdi32:
            if self.hBmp:
                gdi32.DeleteObject(self.hBmp)
                self.hBmp = None
            if self.mem_dc:
                gdi32.DeleteDC(self.mem_dc)
                self.mem_dc = None
        if user32 and self.src_dc:
            user32.ReleaseDC(0, self.src_dc)
            self.src_dc = None


class ScreenCapture:
    """Captures and compresses Windows desktop frames with multi-monitor & window station awareness."""

    def __init__(self, quality: int = 70, max_width: Optional[int] = None):
        self.quality = quality
        self.max_width = max_width
        self.resample_filter = "bilinear"
        self.subsampling = 2  # 0 for 4:4:4, 2 for 4:2:0
        self.grayscale = False
        self._buffer = io.BytesIO()
        self._tls = threading.local()
        self._attach_window_station()
        self.is_headless = is_headless_display()
        self.active_monitor_id = 0  # 0 = All monitors (virtual desktop), 1..N = specific monitor
        self.monitors = self.detect_monitors()
        self._last_frame_hash: Optional[int] = None
        self._last_frame_sent_time: float = 0.0
        self._native_cap: Optional[NativeWin32Capture] = None
        if user32 and gdi32:
            try:
                self._native_cap = NativeWin32Capture()
            except Exception:
                self._native_cap = None
        self._sct = None
        if mss is not None:
            try:
                self._sct = mss.MSS()
            except Exception:
                self._sct = None

    def _attach_window_station(self) -> bool:
        """Attaches current calling thread to active input desktop (handles Winlogon, default, screensaver)."""
        if not user32:
            return True
        if getattr(self._tls, "attached", False):
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
            self._tls.attached = True
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
        if self._native_cap is not None:
            try:
                self._native_cap.close()
            except Exception:
                pass
            self._native_cap = None
        if self._sct is not None:
            try:
                self._sct.close()
            except Exception:
                pass
            self._sct = None

    def capture_frame(self, force: bool = False) -> Optional[bytes]:
        """
        Captures the specified monitor desktop, encodes to JPEG, and returns raw bytes.
        Returns None if frame is identical to previous frame (skip static frames),
        except sending keepalive frames periodically (4 FPS) to prevent client stream starvation.
        """
        try:
            self._attach_window_station()

            left, top, w, h = 0, 0, 1920, 1080
            if self.active_monitor_id == 0:
                if user32:
                    left = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
                    top = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
                    w = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
                    h = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
                if w <= 0 or h <= 0:
                    left, top = 0, 0
                    w = user32.GetSystemMetrics(SM_CXSCREEN) if user32 else 1920
                    h = user32.GetSystemMetrics(SM_CYSCREEN) if user32 else 1080
            else:
                for m in self.monitors:
                    if m["id"] == self.active_monitor_id:
                        left, top, right, bottom = m["rect"]
                        w = right - left
                        h = bottom - top
                        break
                if (w <= 0 or h <= 0) and self.monitors:
                    left, top, right, bottom = self.monitors[0]["rect"]
                    w = right - left
                    h = bottom - top

            img = None
            now = time.perf_counter()

            # Fast-path Tier 1: Native Win32 GDI DIBSection with Hardware Cursor Overlay (0 allocs)
            if self._native_cap is not None:
                try:
                    native_img, raw_buf, cursor_changed = self._native_cap.grab(left, top, w, h)
                    if native_img is not None and raw_buf is not None:
                        # Granular grid sampling (stride 256 = sample every 64 pixels) catches any text/UI change
                        curr_hash = hash(memoryview(raw_buf)[::256].tobytes())
                        is_static = (not force and not cursor_changed and curr_hash == self._last_frame_hash)
                        if is_static:
                            # Keepalive idle frame: maintain minimum 4 FPS so video stream & HUD stay alive
                            if now - self._last_frame_sent_time > 0.25:
                                self._last_frame_sent_time = now
                            else:
                                return None
                        else:
                            self._last_frame_hash = curr_hash
                            self._last_frame_sent_time = now
                        img = native_img
                except Exception:
                    self._native_cap = None

            # Fallback Tier 2: mss direct grab
            if img is None and self._sct is not None:
                try:
                    if self.active_monitor_id == 0:
                        mon_target = self._sct.monitors[0]
                    elif 1 <= self.active_monitor_id < len(self._sct.monitors):
                        mon_target = self._sct.monitors[self.active_monitor_id]
                    else:
                        mon_target = self._sct.monitors[0]

                    shot = self._sct.grab(mon_target)
                    curr_hash = hash(memoryview(shot.raw)[::256].tobytes())
                    if not force and curr_hash == self._last_frame_hash:
                        if now - self._last_frame_sent_time > 0.25:
                            self._last_frame_sent_time = now
                        else:
                            return None
                    else:
                        self._last_frame_hash = curr_hash
                        self._last_frame_sent_time = now

                    img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
                except Exception:
                    self._sct = None

            # Fallback Tier 3: Pillow ImageGrab (Cross-platform)
            if img is None:
                bbox = (left, top, left + w, top + h) if self.active_monitor_id != 0 else None
                try:
                    img = ImageGrab.grab(bbox=bbox, all_screens=True)
                except Exception:
                    img = ImageGrab.grab(bbox=bbox, all_screens=(self.active_monitor_id == 0))

                if img is None:
                    if self.is_headless:
                        return generate_headless_placeholder(1920, 1080)
                    return None

                curr_hash = hash(memoryview(img.tobytes())[::256].tobytes())
                if not force and curr_hash == self._last_frame_hash:
                    if now - self._last_frame_sent_time > 0.25:
                        self._last_frame_sent_time = now
                    else:
                        return None
                else:
                    self._last_frame_hash = curr_hash
                    self._last_frame_sent_time = now

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
                use_nearest = getattr(self, "resample_filter", "bilinear") == "nearest" or self.quality <= 58
                resample = Image.Resampling.NEAREST if use_nearest else Image.Resampling.BILINEAR
                img = img.resize((new_w, new_h), resample)

            if getattr(self, "grayscale", False):
                if img.mode != 'L':
                    img = img.convert('L')
            else:
                if img.mode != 'RGB':
                    img = img.convert('RGB')

            self._buffer.seek(0)
            self._buffer.truncate(0)
            save_kwargs = {
                "format": "JPEG",
                "quality": self.quality,
                "optimize": False,
                "fastdct": True,
            }
            if not getattr(self, "grayscale", False):
                save_kwargs["subsampling"] = getattr(self, "subsampling", 2)

            img.save(self._buffer, **save_kwargs)
            return self._buffer.getvalue()

        except Exception:
            if getattr(self, 'is_headless', False):
                try:
                    w_res, h_res = getattr(self, 'resolution', (1920, 1080))
                    return generate_headless_placeholder(w_res, h_res)
                except Exception:
                    pass
            return None

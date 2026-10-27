import io
import time
import sys
import os
import ctypes
import threading
import logging
from typing import Tuple, Optional, List, Dict, Any
from PIL import Image, ImageGrab

try:
    import mss
except ImportError:
    mss = None

# High-performance JPEG encoder: turbojpeg (libjpeg-turbo) ~2-5ms vs PIL's ~35-55ms for 1080p
_tjpeg = None
_HAS_TURBOJPEG = False
try:
    import turbojpeg
    # Try default auto-detect first
    try:
        _tjpeg = turbojpeg.TurboJPEG()
        _HAS_TURBOJPEG = True
    except RuntimeError:
        # Auto-detect failed — try common install paths on Windows, Linux, macOS
        _lib_candidates = []
        if sys.platform == 'win32':
            meipass = getattr(sys, '_MEIPASS', None)
            exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else None
            _lib_candidates = [
                r"C:\libjpeg-turbo64\bin\turbojpeg.dll",
                r"C:\Program Files\libjpeg-turbo64\bin\turbojpeg.dll",
                r"C:\ProgramData\chocolatey\lib\libjpeg-turbo\tools\turbojpeg.dll",
                os.path.join(os.path.dirname(__file__), "turbojpeg.dll"),
            ]
            if meipass:
                _lib_candidates.insert(0, os.path.join(meipass, "turbojpeg.dll"))
                _lib_candidates.insert(1, os.path.join(meipass, "host_agent", "turbojpeg.dll"))
            if exe_dir:
                _lib_candidates.insert(0, os.path.join(exe_dir, "turbojpeg.dll"))
        elif sys.platform.startswith('linux'):
            _lib_candidates = [
                "/usr/lib/x86_64-linux-gnu/libturbojpeg.so.0",
                "/usr/lib/x86_64-linux-gnu/libturbojpeg.so",
                "/usr/lib/aarch64-linux-gnu/libturbojpeg.so.0",
                "/usr/lib/aarch64-linux-gnu/libturbojpeg.so",
                "/usr/lib64/libturbojpeg.so.0",
                "/usr/lib64/libturbojpeg.so",
                "/usr/lib/libturbojpeg.so.0",
                "/usr/lib/libturbojpeg.so",
                "/usr/local/lib/libturbojpeg.so.0",
                "/usr/local/lib/libturbojpeg.so",
            ]
        elif sys.platform == 'darwin':
            _lib_candidates = [
                "/opt/homebrew/lib/libturbojpeg.dylib",
                "/opt/homebrew/opt/jpeg-turbo/lib/libturbojpeg.dylib",
                "/usr/local/lib/libturbojpeg.dylib",
                "/usr/local/opt/jpeg-turbo/lib/libturbojpeg.dylib",
            ]
        for _lp in _lib_candidates:
            if os.path.isfile(_lp):
                try:
                    _tjpeg = turbojpeg.TurboJPEG(lib_path=_lp)
                    _HAS_TURBOJPEG = True
                    break
                except Exception:
                    continue
except ImportError:
    pass

# numpy for zero-copy BGRA→RGB conversion with turbojpeg
try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    np = None
    _HAS_NUMPY = False

# DXCam: GPU-accelerated DirectX Desktop Duplication capture (Windows only, ~1ms capture)
try:
    import dxcam
    _HAS_DXCAM = True
except ImportError:
    dxcam = None
    _HAS_DXCAM = False

_logger = logging.getLogger("meikova.screen_capture")

# Map subsampling int to turbojpeg constant (lazy — safe even if turbojpeg not available)
_TJPEG_SUBSAMP = {}
if _HAS_TURBOJPEG:
    _TJPEG_SUBSAMP = {
        0: turbojpeg.TJSAMP_444,
        1: turbojpeg.TJSAMP_422,
        2: turbojpeg.TJSAMP_420,
    }

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
        self.old_hBmp = None
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
            if self.old_hBmp and self.mem_dc:
                gdi32.SelectObject(self.mem_dc, self.old_hBmp)
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
        old = gdi32.SelectObject(self.mem_dc, self.hBmp)
        if not self.old_hBmp:
            self.old_hBmp = old
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
                if self.old_hBmp and self.mem_dc:
                    gdi32.SelectObject(self.mem_dc, self.old_hBmp)
                    self.old_hBmp = None
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
        self.custom_virtual_resolution: Optional[Tuple[int, int]] = None
        self.is_headless = is_headless_display()
        self.active_monitor_id = 0  # 0 = All monitors (virtual desktop), 1..N = specific monitor
        self.monitors = self.detect_monitors()
        self._last_frame_hash: Optional[int] = None
        self._last_frame_sent_time: float = 0.0
        self._native_cap: Optional[NativeWin32Capture] = None

        # DXCam: GPU-accelerated Desktop Duplication API (Windows only, ~1ms capture, auto-fallback)
        self._dxcam_cap = None
        if _HAS_DXCAM and sys.platform == 'win32':
            try:
                self._dxcam_cap = dxcam.create(output_color="BGR")
                _logger.info("DXCam GPU capture initialized (Desktop Duplication API)")
            except Exception as e:
                _logger.debug(f"DXCam init failed, using GDI fallback: {e}")
                self._dxcam_cap = None

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

        # Log encoder status at startup
        if _HAS_TURBOJPEG:
            _logger.info("TurboJPEG encoder active (libjpeg-turbo, ~2-5ms/frame 1080p)")
        else:
            _logger.warning("TurboJPEG unavailable, using PIL JPEG (~35-55ms/frame 1080p). Install libjpeg-turbo + PyTurboJPEG for 10x speedup.")

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
                user32.CloseWindowStation(hwinsta)
            hdesk = user32.OpenInputDesktop(0, False, 0x01FF)
            if not hdesk:
                hdesk = user32.OpenDesktopW('default', 0, False, 0x01FF)
            if hdesk:
                user32.SetThreadDesktop(hdesk)
                old_hdesk = getattr(self._tls, "hdesk", None)
                if old_hdesk and old_hdesk != hdesk:
                    try:
                        user32.CloseDesktop(old_hdesk)
                    except Exception:
                        pass
                self._tls.hdesk = hdesk
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

    def set_custom_resolution(self, width: int, height: int):
        """Sets dynamic virtual screen resolution for headless or multi-size streaming."""
        self.custom_virtual_resolution = (int(width), int(height))
        if self.max_width is not None:
            self.max_width = max(self.max_width, int(width))
        self._last_frame_hash = None
        if getattr(self, "is_headless", False) or not self.monitors:
            self.monitors = [{
                "id": 1,
                "name": f"Virtual Display ({width}x{height})",
                "width": int(width),
                "height": int(height),
                "left": 0,
                "top": 0
            }]
            self.active_monitor_id = 1
        elif self.monitors:
            for m in self.monitors:
                if m.get("id") == self.active_monitor_id or self.active_monitor_id == 0:
                    m["width"] = int(width)
                    m["height"] = int(height)

    @property
    def resolution(self) -> Tuple[int, int]:
        if self.custom_virtual_resolution:
            return self.custom_virtual_resolution
        if getattr(self, "is_headless", False) and not self.monitors:
            return (1920, 1080)
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
        if self._dxcam_cap is not None:
            try:
                self._dxcam_cap.stop()
            except Exception:
                pass
            self._dxcam_cap = None
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

    def _encode_jpeg_turbo(self, img_or_array, w: int, h: int, pixel_format: str = "RGB") -> Optional[bytes]:
        """Encode frame using turbojpeg (libjpeg-turbo). Returns JPEG bytes or None on failure.
        pixel_format: 'RGB', 'BGR', 'BGRA', 'BGRX' — determines turbojpeg pixel format constant.
        """
        if not _HAS_TURBOJPEG or _tjpeg is None:
            return None
        try:
            subsamp = _TJPEG_SUBSAMP.get(self.subsampling, turbojpeg.TJSAMP_420)
            if self.grayscale:
                subsamp = turbojpeg.TJSAMP_GRAY

            # If we have a numpy array, encode directly
            if _HAS_NUMPY and isinstance(img_or_array, np.ndarray):
                arr = img_or_array
                if pixel_format == "BGR":
                    pf = turbojpeg.TJPF_BGR
                elif pixel_format in ("BGRA", "BGRX"):
                    pf = turbojpeg.TJPF_BGRX
                elif pixel_format == "RGB":
                    pf = turbojpeg.TJPF_RGB
                else:
                    pf = turbojpeg.TJPF_RGB
                return _tjpeg.encode(arr, quality=self.quality, jpeg_subsample=subsamp, pixel_format=pf)

            # PIL Image path — convert to numpy then encode
            if _HAS_NUMPY:
                if self.grayscale:
                    if img_or_array.mode != 'L':
                        img_or_array = img_or_array.convert('L')
                    arr = np.array(img_or_array)
                    return _tjpeg.encode(arr, quality=self.quality, jpeg_subsample=turbojpeg.TJSAMP_GRAY, pixel_format=turbojpeg.TJPF_GRAY)
                if img_or_array.mode not in ('RGB', 'BGR'):
                    img_or_array = img_or_array.convert('RGB')
                arr = np.array(img_or_array)
                return _tjpeg.encode(arr, quality=self.quality, jpeg_subsample=subsamp, pixel_format=turbojpeg.TJPF_RGB)

            return None  # No numpy — fall through to PIL
        except Exception:
            return None

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
                        left, top, w, h = m["x"], m["y"], m["width"], m["height"]
                        break

            now = time.time()
            img = None
            raw_np_array = None  # numpy array for zero-copy turbojpeg path
            raw_pixel_format = None

            # Primary Tier 0: DXCam GPU Desktop Duplication capture (~1ms, numpy BGR output)
            if self._dxcam_cap is not None:
                try:
                    frame = self._dxcam_cap.grab()
                    if frame is not None and _HAS_NUMPY:
                        curr_hash = hash(frame.data.tobytes()[::1024])
                        is_static = (not force and curr_hash == self._last_frame_hash)
                        if is_static:
                            if now - self._last_frame_sent_time > 0.25:
                                self._last_frame_sent_time = now
                            else:
                                return None
                        else:
                            self._last_frame_hash = curr_hash
                            self._last_frame_sent_time = now
                        raw_np_array = frame
                        raw_pixel_format = "BGR"
                except Exception:
                    self._dxcam_cap = None

            # Primary Tier 1: Zero-allocation Win32 GDI DIBSection capture
            if raw_np_array is None and img is None and self._native_cap is not None:
                try:
                    native_img, raw_buf, cursor_changed = self._native_cap.grab(left, top, w, h)
                    if native_img is not None and raw_buf is not None:
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

                        # Zero-copy path: convert raw_buf BGRX to numpy for turbojpeg
                        if _HAS_NUMPY and _HAS_TURBOJPEG:
                            raw_np_array = np.frombuffer(raw_buf, dtype=np.uint8).reshape(h, w, 4)
                            raw_pixel_format = "BGRX"
                        else:
                            img = native_img
                except Exception:
                    self._native_cap = None

            # Fallback Tier 2: mss direct grab
            if raw_np_array is None and img is None and self._sct is not None:
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

                    # Zero-copy path for mss: BGRA numpy array
                    if _HAS_NUMPY and _HAS_TURBOJPEG:
                        raw_np_array = np.frombuffer(shot.raw, dtype=np.uint8).reshape(shot.height, shot.width, 4)
                        raw_pixel_format = "BGRA"
                    else:
                        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
                except Exception:
                    self._sct = None

            # Fallback Tier 3: Pillow ImageGrab (Cross-platform)
            if raw_np_array is None and img is None:
                bbox = (left, top, left + w, top + h) if self.active_monitor_id != 0 else None
                try:
                    img = ImageGrab.grab(bbox=bbox, all_screens=True)
                except Exception:
                    img = ImageGrab.grab(bbox=bbox, all_screens=(self.active_monitor_id == 0))

                if img is None:
                    if self.is_headless:
                        w_res, h_res = getattr(self, 'resolution', (1920, 1080))
                        return generate_headless_placeholder(w_res, h_res)
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

            # --- ENCODE PHASE ---

            # Fast path: turbojpeg with numpy array (zero PIL intermediate, ~2-5ms for 1080p)
            if raw_np_array is not None and _HAS_TURBOJPEG and _HAS_NUMPY:
                cap_h, cap_w = raw_np_array.shape[:2]

                # Downscale if needed (numpy resize via PIL, only when max_width set)
                effective_max_w = self.max_width
                if not effective_max_w and self.active_monitor_id == 0 and cap_w > 2560:
                    effective_max_w = 2560

                if effective_max_w and cap_w > effective_max_w:
                    aspect = cap_h / cap_w
                    new_w = effective_max_w
                    new_h = int(new_w * aspect)
                    # Convert to PIL for resize, then back to numpy
                    if raw_pixel_format in ("BGRX", "BGRA"):
                        pil_img = Image.frombuffer('RGB', (cap_w, cap_h), raw_np_array, 'raw', 'BGRX', 0, 1)
                    else:
                        pil_img = Image.fromarray(raw_np_array[:, :, ::-1] if raw_pixel_format == "BGR" else raw_np_array)
                    use_nearest = getattr(self, "resample_filter", "bilinear") == "nearest" or self.quality <= 58
                    resample = Image.Resampling.NEAREST if use_nearest else Image.Resampling.BILINEAR
                    pil_img = pil_img.resize((new_w, new_h), resample)
                    raw_np_array = np.array(pil_img)
                    raw_pixel_format = "RGB"

                jpeg_bytes = self._encode_jpeg_turbo(raw_np_array, cap_w, cap_h, raw_pixel_format)
                if jpeg_bytes:
                    return jpeg_bytes
                # Fall through to PIL path if turbojpeg fails
                if raw_pixel_format in ("BGRX", "BGRA"):
                    img = Image.frombuffer('RGB', (cap_w, cap_h), raw_np_array, 'raw', 'BGRX', 0, 1)
                else:
                    img = Image.fromarray(raw_np_array[:, :, ::-1] if raw_pixel_format == "BGR" else raw_np_array)

            # PIL encode path (fallback when turbojpeg unavailable)
            if img is not None:
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

                # Try turbojpeg with PIL Image
                turbo_result = self._encode_jpeg_turbo(img, img.width, img.height, "RGB")
                if turbo_result:
                    return turbo_result

                # Final fallback: PIL JPEG encode
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

            return None

        except Exception:
            if getattr(self, 'is_headless', False):
                try:
                    w_res, h_res = getattr(self, 'resolution', (1920, 1080))
                    return generate_headless_placeholder(w_res, h_res)
                except Exception:
                    pass
            return None

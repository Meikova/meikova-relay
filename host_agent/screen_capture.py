import io
import os
import time
import sys
import ctypes
import ctypes.util
import threading
from typing import Tuple, Optional, List, Dict, Any
from PIL import Image, ImageGrab

try:
    import numpy as np
except ImportError:
    np = None

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import mss
except ImportError:
    mss = None

try:
    import bettercam as dxcam_lib
except ImportError:
    try:
        import dxcam as dxcam_lib
    except ImportError:
        dxcam_lib = None

try:
    from turbojpeg import TurboJPEG as PyTurboJPEG, TJPF_BGRX, TJPF_BGR, TJPF_RGB, TJPF_GRAY, TJSAMP_444, TJSAMP_422, TJSAMP_420, TJSAMP_GRAY, TJFLAG_FASTDCT
except ImportError:
    PyTurboJPEG = None
    TJPF_RGB = 0
    TJPF_BGR = 1
    TJPF_BGRX = 3
    TJPF_GRAY = 6
    TJSAMP_444 = 0
    TJSAMP_422 = 1
    TJSAMP_420 = 2
    TJSAMP_GRAY = 3
    TJFLAG_FASTDCT = 2048

try:
    from host_agent.virtual_display import is_headless_display, generate_headless_placeholder
except ImportError:
    try:
        from virtual_display import is_headless_display, generate_headless_placeholder
    except ImportError:
        def is_headless_display(): return False
        def generate_headless_placeholder(w=1920, h=1080): return b''

# Win32 user32, gdi32, and winmm guards for cross-platform support
user32 = getattr(ctypes, 'windll', None).user32 if hasattr(ctypes, 'windll') else None
gdi32 = getattr(ctypes, 'windll', None).gdi32 if hasattr(ctypes, 'windll') else None
winmm = getattr(ctypes, 'windll', None).winmm if hasattr(ctypes, 'windll') else None

# Enable 1ms kernel timer resolution on Windows so asyncio.sleep / frame pacing achieves 120+ FPS
if winmm:
    try:
        winmm.timeBeginPeriod(1)
    except Exception:
        pass

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


class _CtypesTurboJPEG:
    """Zero-copy ctypes wrapper over native libturbojpeg (Windows/macOS/Linux) for SIMD BGRX->JPEG encoding."""

    def __init__(self):
        self._lib = None
        self._tls = threading.local()
        candidates = []
        if sys.platform == "win32":
            candidates.extend([
                "turbojpeg.dll",
                "libturbojpeg.dll",
                r"C:\libjpeg-turbo64\bin\turbojpeg.dll",
                r"C:\Program Files\libjpeg-turbo64\bin\turbojpeg.dll",
            ])
        elif sys.platform == "darwin":
            candidates.extend([
                "/opt/homebrew/opt/jpeg-turbo/lib/libturbojpeg.dylib",
                "/opt/homebrew/lib/libturbojpeg.dylib",
                "/usr/local/opt/jpeg-turbo/lib/libturbojpeg.dylib",
                "/usr/local/lib/libturbojpeg.dylib",
                "libturbojpeg.dylib",
            ])
        else:
            candidates.extend([
                "libturbojpeg.so.0",
                "/usr/lib/x86_64-linux-gnu/libturbojpeg.so.0",
                "/usr/lib/aarch64-linux-gnu/libturbojpeg.so.0",
                "/usr/lib64/libturbojpeg.so.0",
                "/usr/lib/libturbojpeg.so.0",
                "/usr/lib/libturbojpeg.so",
            ])
        found = ctypes.util.find_library("turbojpeg")
        if found:
            candidates.insert(0, found)

        for path in candidates:
            try:
                lib = ctypes.CDLL(path)
                lib.tjInitCompress.restype = ctypes.c_void_p
                lib.tjCompress2.argtypes = [
                    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                    ctypes.c_int, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_ulong),
                    ctypes.c_int, ctypes.c_int, ctypes.c_int
                ]
                lib.tjCompress2.restype = ctypes.c_int
                lib.tjFree.argtypes = [ctypes.c_void_p]
                lib.tjDestroy.argtypes = [ctypes.c_void_p]
                self._lib = lib
                break
            except Exception:
                continue

    @property
    def available(self) -> bool:
        return self._lib is not None

    def _get_handle(self):
        h = getattr(self._tls, "handle", None)
        if not h and self._lib is not None:
            h = self._lib.tjInitCompress()
            self._tls.handle = h
        return h

    def encode_raw(self, raw_buf, width: int, height: int, pitch: int, pixel_format: int, quality: int, subsampling: int, grayscale: bool = False) -> Optional[bytes]:
        if not self._lib:
            return None
        handle = self._get_handle()
        if not handle:
            return None

        if grayscale:
            subsamp = TJSAMP_GRAY
        elif subsampling == 0:
            subsamp = TJSAMP_444
        elif subsampling == 1:
            subsamp = TJSAMP_422
        else:
            subsamp = TJSAMP_420

        if isinstance(raw_buf, bytes):
            src_ptr = ctypes.cast(raw_buf, ctypes.c_void_p)
        elif hasattr(raw_buf, "ctypes"):
            src_ptr = ctypes.c_void_p(raw_buf.ctypes.data)
        else:
            try:
                src_ptr = ctypes.cast(ctypes.byref(raw_buf), ctypes.c_void_p)
            except Exception:
                return None

        jpeg_buf = ctypes.c_void_p()
        jpeg_size = ctypes.c_ulong(0)
        rc = self._lib.tjCompress2(
            handle,
            src_ptr,
            int(width),
            int(pitch),
            int(height),
            int(pixel_format),
            ctypes.byref(jpeg_buf),
            ctypes.byref(jpeg_size),
            int(subsamp),
            max(1, min(100, int(quality))),
            TJFLAG_FASTDCT
        )
        if rc != 0 or not jpeg_buf.value or jpeg_size.value == 0:
            if jpeg_buf.value:
                self._lib.tjFree(jpeg_buf)
            return None
        try:
            return ctypes.string_at(jpeg_buf.value, jpeg_size.value)
        finally:
            self._lib.tjFree(jpeg_buf)


_CTYPES_TJ = _CtypesTurboJPEG()
_PY_TJ = None
if PyTurboJPEG is not None:
    try:
        _PY_TJ = PyTurboJPEG()
    except Exception:
        _PY_TJ = None


class NativeWin32Capture:
    """Zero-allocation native Win32 GDI DIBSection capture with hardware cursor overlay.
    Uses pure SRCCOPY (without CAPTUREBLT) to avoid the 16-30ms Windows DWM composition stall.
    """

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
        # Pure SRCCOPY without CAPTUREBLT prevents Windows 10/11 DWM composition stall (~30ms lock)
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
        return (w, h), self.raw_array, c_changed

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
    """High-FPS cross-platform desktop capture & SIMD JPEG encoder (Windows, macOS, Linux).
    Decouples OS display capture + JPEG encoding into a continuous background producer thread
    during active streaming so 120-240 FPS frame pacing never blocks on DWM BitBlt locks.
    """

    def __init__(self, quality: int = 70, max_width: Optional[int] = None):
        self.quality = quality
        self.max_width = max_width
        self.resample_filter = "bilinear"
        self.subsampling = 2  # 0 for 4:4:4, 2 for 4:2:0
        self.grayscale = False
        self.encoder_mode = "auto"
        self.static_cache_enabled = True
        self.keepalive_interval = 0.0  # 0.0 = zero-CPU cached frame delivery at target FPS
        self._buffer = io.BytesIO()
        self._tls = threading.local()
        self._attach_window_station()
        self.custom_virtual_resolution: Optional[Tuple[int, int]] = None
        self.is_headless = is_headless_display()
        self.active_monitor_id = 0  # 0 = All monitors (virtual desktop), 1..N = specific monitor
        self._sct = None
        if mss is not None:
            try:
                _mss_factory = getattr(mss, "MSS", None) or mss.mss
                self._sct = _mss_factory()
            except Exception:
                self._sct = None
        self.monitors = self.detect_monitors()
        self._last_frame_hash: Optional[int] = None
        self._last_frame_sent_time: float = 0.0
        self._last_encoded_frame: Optional[bytes] = None
        self._last_encode_params: Optional[Tuple[Any, ...]] = None
        self._placeholder_cache: Dict[Tuple[int, int], bytes] = {}
        self._native_cap: Optional[NativeWin32Capture] = None
        if user32 and gdi32:
            try:
                self._native_cap = NativeWin32Capture()
            except Exception:
                self._native_cap = None

        # Background asynchronous capture & encode producer state
        self._bg_lock = threading.Lock()
        self._bg_thread: Optional[threading.Thread] = None
        self._bg_stop_event = threading.Event()
        self._bg_wake_event = threading.Event()
        self._last_poll_ts: float = 0.0

    def _get_thread_native_cap(self) -> Optional[NativeWin32Capture]:
        """Returns thread-local NativeWin32Capture so GDI DCs never suffer cross-thread contention."""
        if not (user32 and gdi32):
            return None
        cap = getattr(self._tls, "native_cap", None)
        if cap is None:
            try:
                cap = NativeWin32Capture()
                self._tls.native_cap = cap
            except Exception:
                cap = self._native_cap
        return cap

    def _get_thread_sct(self):
        """Returns thread-local mss instance so X11/XShm (Linux), Quartz (macOS), and GDI (Windows) are 100% thread-safe."""
        if mss is None:
            return None
        sct = getattr(self._tls, "sct", None)
        if sct is None:
            try:
                _mss_factory = getattr(mss, "MSS", None) or mss.mss
                sct = _mss_factory()
                self._tls.sct = sct
            except Exception:
                sct = self._sct
        return sct

    def _get_thread_dxcam(self, monitor_idx: int = 0):
        """Returns thread-local DXGI Desktop Duplication (bettercam/dxcam) instance on Windows when available."""
        if sys.platform != "win32" or dxcam_lib is None:
            return None
        cam_map = getattr(self._tls, "dxcam_map", None)
        if cam_map is None:
            cam_map = {}
            self._tls.dxcam_map = cam_map
        if monitor_idx not in cam_map:
            try:
                cam_map[monitor_idx] = dxcam_lib.create(output_idx=max(0, monitor_idx), output_color="BGRA")
            except Exception:
                cam_map[monitor_idx] = None
        return cam_map.get(monitor_idx)

    def _attach_window_station(self, force: bool = False) -> bool:
        """Attaches current calling thread to active input desktop (throttled to avoid per-frame kernel overhead)."""
        if not user32:
            return True
        now = time.perf_counter()
        if not force and getattr(self._tls, "attached", False):
            last_ts = getattr(self._tls, "last_attach_ts", 0.0)
            if now - last_ts < 1.0:
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
            self._tls.last_attach_ts = now
            return True
        except Exception:
            return False

    def detect_monitors(self) -> List[Dict[str, Any]]:
        """Enumerates physical and virtual displays across Windows (Win32), macOS (Quartz/mss), and Linux (XRandR/mss)."""
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
                        "x": left,
                        "y": top,
                        "left": left,
                        "top": top,
                        "width": w,
                        "height": h
                    })
            except Exception:
                pass

        # Cross-platform multi-monitor detection via mss (macOS Quartz & Linux X11/XShm)
        if not results:
            sct = self._get_thread_sct()
            if sct is not None:
                try:
                    mons = sct.monitors[1:] if len(sct.monitors) > 1 else sct.monitors
                    for i, m in enumerate(mons):
                        left = int(m.get("left", 0))
                        top = int(m.get("top", 0))
                        w = int(m.get("width", 1920))
                        h = int(m.get("height", 1080))
                        results.append({
                            "id": i + 1,
                            "name": f"Màn {i + 1}",
                            "rect": (left, top, left + w, top + h),
                            "x": left,
                            "y": top,
                            "left": left,
                            "top": top,
                            "width": w,
                            "height": h
                        })
                except Exception:
                    pass

        if not results:
            w = user32.GetSystemMetrics(SM_CXSCREEN) if user32 else None
            h = user32.GetSystemMetrics(SM_CYSCREEN) if user32 else None
            if not w or not h:
                if sys.platform.startswith("linux") and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
                    w, h = 1920, 1080
                else:
                    try:
                        img = ImageGrab.grab()
                        w, h = img.size
                    except Exception:
                        w, h = 1920, 1080
            w = w or 1920
            h = h or 1080
            results.append({
                "id": 1,
                "name": "Màn 1",
                "rect": (0, 0, w, h),
                "x": 0,
                "y": 0,
                "left": 0,
                "top": 0,
                "width": w,
                "height": h
            })
        return results

    def set_active_monitor(self, monitor_id: int):
        """Sets active monitor to capture (0 for entire virtual desktop, 1..N for specific monitor)."""
        self.active_monitor_id = monitor_id
        self._last_frame_hash = None
        self._last_encoded_frame = None
        self._bg_wake_event.set()

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
        w_int, h_int = int(width), int(height)
        self.custom_virtual_resolution = (w_int, h_int)
        if self.max_width is not None:
            self.max_width = max(self.max_width, w_int)
        self._last_frame_hash = None
        self._last_encoded_frame = None
        if getattr(self, "is_headless", False) or not self.monitors:
            self.monitors = [{
                "id": 1,
                "name": f"Virtual Display ({w_int}x{h_int})",
                "rect": (0, 0, w_int, h_int),
                "x": 0,
                "y": 0,
                "left": 0,
                "top": 0,
                "width": w_int,
                "height": h_int,
            }]
            self.active_monitor_id = 1
        elif self.monitors:
            for m in self.monitors:
                if m.get("id") == self.active_monitor_id or self.active_monitor_id == 0:
                    left = m.get("x", m.get("left", 0))
                    top = m.get("y", m.get("top", 0))
                    m["width"] = w_int
                    m["height"] = h_int
                    m["rect"] = (left, top, left + w_int, top + h_int)
        self._bg_wake_event.set()

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

    def _ensure_bg_producer(self):
        """Starts the asynchronous background capture & encode daemon thread if not already running."""
        if self._bg_thread is not None and self._bg_thread.is_alive():
            self._bg_wake_event.set()
            return
        with self._bg_lock:
            if self._bg_thread is not None and self._bg_thread.is_alive():
                self._bg_wake_event.set()
                return
            self._bg_stop_event.clear()
            self._bg_wake_event.set()
            self._bg_thread = threading.Thread(
                target=self._bg_capture_loop,
                daemon=True,
                name="MeikovaAsyncCaptureProducer"
            )
            self._bg_thread.start()

    def _bg_capture_loop(self):
        """Dedicated background loop that continuously grabs and encodes screen updates without blocking _stream_screen."""
        while not self._bg_stop_event.is_set():
            # Pause background grabbing when no stream consumer has polled within the last 1.5 seconds
            if time.perf_counter() - self._last_poll_ts > 1.5:
                self._bg_wake_event.clear()
                self._bg_wake_event.wait(timeout=0.5)
                continue

            t0 = time.perf_counter()
            try:
                self._capture_and_encode_sync(force=False)
            except Exception:
                pass
            elapsed = time.perf_counter() - t0
            # Pace background hardware polling to up to ~180Hz (5.5ms minimum cycle) so CPU stays cool
            if elapsed < 0.0055:
                time.sleep(0.0055 - elapsed)

    def close(self):
        """Releases native capture contexts and stops background producer thread."""
        self._bg_stop_event.set()
        self._bg_wake_event.set()
        if self._native_cap is not None:
            try:
                self._native_cap.close()
            except Exception:
                pass
            self._native_cap = None
        tls_cap = getattr(self._tls, "native_cap", None)
        if tls_cap is not None:
            try:
                tls_cap.close()
            except Exception:
                pass
            self._tls.native_cap = None
        if self._sct is not None:
            try:
                self._sct.close()
            except Exception:
                pass
            self._sct = None
        tls_sct = getattr(self._tls, "sct", None)
        if tls_sct is not None:
            try:
                tls_sct.close()
            except Exception:
                pass
            self._tls.sct = None

    def _encode_bgra_fast(self, raw_bgra, width: int, height: int, effective_max_w: Optional[int]) -> Optional[bytes]:
        """
        Compresses raw BGRA/BGRX buffer to JPEG using fastest available backend:
        1. libturbojpeg (zero-copy SIMD BGRX->JPEG when no resize needed)
        2. OpenCV + NumPy (SIMD C++ resize + libjpeg-turbo imencode, releases GIL)
        3. Pillow (zero-copy Image.frombuffer fallback)
        """
        needs_resize = bool(effective_max_w and width > effective_max_w)
        grayscale = bool(getattr(self, "grayscale", False))
        subsampling = getattr(self, "subsampling", 2)
        quality = max(10, min(100, int(self.quality)))
        mode = str(getattr(self, "encoder_mode", "auto") or "auto").lower()

        if mode == "pillow":
            img = Image.frombuffer("RGB", (width, height), raw_bgra, "raw", "BGRX", 0, 1)
            return self._encode_pil_image(img, effective_max_w)

        # Fast Path 1: Native 1:1 (no resize, color mode) -> Direct zero-copy libturbojpeg from BGRX buffer
        if mode in ("auto", "turbojpeg") and not needs_resize and not grayscale:
            if _CTYPES_TJ.available:
                encoded = _CTYPES_TJ.encode_raw(
                    raw_bgra, width, height, width * 4, TJPF_BGRX, quality, subsampling, False
                )
                if encoded:
                    return encoded
            if _PY_TJ is not None:
                try:
                    subsamp_map = {0: TJSAMP_444, 1: TJSAMP_422, 2: TJSAMP_420}
                    arr = np.frombuffer(raw_bgra, dtype=np.uint8).reshape((height, width, 4)) if np is not None else raw_bgra
                    return _PY_TJ.encode(
                        arr,
                        quality=quality,
                        pixel_format=TJPF_BGRX,
                        jpeg_subsample=subsamp_map.get(subsampling, TJSAMP_420),
                        flags=TJFLAG_FASTDCT
                    )
                except Exception:
                    pass

        # Fast Path 2: OpenCV + NumPy (handles both 1:1 and SIMD downscaling / grayscale in C++ outside GIL)
        if cv2 is not None and np is not None:
            try:
                arr = np.frombuffer(raw_bgra, dtype=np.uint8).reshape((height, width, 4))
                if needs_resize and effective_max_w:
                    new_w = int(effective_max_w)
                    new_h = max(1, int(round(height * (new_w / float(width)))))
                    use_nearest = getattr(self, "resample_filter", "bilinear") == "nearest" or quality <= 58
                    interp = cv2.INTER_NEAREST if use_nearest else cv2.INTER_LINEAR
                    arr = cv2.resize(arr, (new_w, new_h), interpolation=interp)
                else:
                    new_w, new_h = width, height

                if grayscale:
                    arr_gray = cv2.cvtColor(arr, cv2.COLOR_BGRA2GRAY)
                    if _CTYPES_TJ.available and arr_gray.flags['C_CONTIGUOUS']:
                        encoded = _CTYPES_TJ.encode_raw(
                            arr_gray, new_w, new_h, new_w, TJPF_GRAY, quality, subsampling, True
                        )
                        if encoded:
                            return encoded
                    ok, buf = cv2.imencode('.jpg', arr_gray, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
                    if ok:
                        return buf.tobytes()
                else:
                    if _CTYPES_TJ.available and arr.flags['C_CONTIGUOUS']:
                        encoded = _CTYPES_TJ.encode_raw(
                            arr, new_w, new_h, new_w * 4, TJPF_BGRX, quality, subsampling, False
                        )
                        if encoded:
                            return encoded
                    ok, buf = cv2.imencode('.jpg', arr, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
                    if ok:
                        return buf.tobytes()
            except Exception:
                pass

        # Fallback Path 3: Pillow with zero-copy Image.frombuffer
        img = Image.frombuffer("RGB", (width, height), raw_bgra, "raw", "BGRX", 0, 1)
        return self._encode_pil_image(img, effective_max_w)

    def _encode_pil_image(self, img: Image.Image, effective_max_w: Optional[int]) -> bytes:
        if effective_max_w and img.width > effective_max_w:
            aspect = img.height / img.width
            new_w = int(effective_max_w)
            new_h = max(1, int(new_w * aspect))
            use_nearest = getattr(self, "resample_filter", "bilinear") == "nearest" or self.quality <= 58
            resample = Image.Resampling.NEAREST if use_nearest else Image.Resampling.BILINEAR
            img = img.resize((new_w, new_h), resample)

        if getattr(self, "grayscale", False):
            if img.mode != 'L':
                img = img.convert('L')
        else:
            if img.mode != 'RGB':
                img = img.convert('RGB')

        buf = getattr(self._tls, "pil_buf", None)
        if buf is None:
            buf = io.BytesIO()
            self._tls.pil_buf = buf
        buf.seek(0)
        buf.truncate(0)
        save_kwargs = {
            "format": "JPEG",
            "quality": self.quality,
            "optimize": False,
            "fastdct": True,
        }
        if not getattr(self, "grayscale", False):
            save_kwargs["subsampling"] = getattr(self, "subsampling", 2)

        img.save(buf, **save_kwargs)
        return buf.getvalue()

    def _get_cached_headless_placeholder(self, w_res: int, h_res: int) -> bytes:
        key = (int(w_res), int(h_res))
        cached = self._placeholder_cache.get(key)
        if not cached:
            cached = generate_headless_placeholder(w_res, h_res)
            if cached:
                self._placeholder_cache[key] = cached
        return cached

    def _compute_current_params(self) -> Tuple[int, int, int, int, Optional[int], Tuple[Any, ...]]:
        left, top, w, h = 0, 0, 1920, 1080
        if self.active_monitor_id == 0:
            if user32:
                left = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
                top = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
                w = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
                h = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
            elif self.monitors:
                min_x = min(m.get("x", m.get("rect", (0, 0, 1920, 1080))[0]) for m in self.monitors)
                min_y = min(m.get("y", m.get("rect", (0, 0, 1920, 1080))[1]) for m in self.monitors)
                max_r = max(m.get("rect", (0, 0, m.get("width", 1920), m.get("height", 1080)))[2] for m in self.monitors)
                max_b = max(m.get("rect", (0, 0, m.get("width", 1920), m.get("height", 1080)))[3] for m in self.monitors)
                left, top, w, h = min_x, min_y, max(1, max_r - min_x), max(1, max_b - min_y)
            if w <= 0 or h <= 0:
                left, top = 0, 0
                w = user32.GetSystemMetrics(SM_CXSCREEN) if user32 else 1920
                h = user32.GetSystemMetrics(SM_CYSCREEN) if user32 else 1080
        else:
            for m in self.monitors:
                if m.get("id") == self.active_monitor_id:
                    rect = m.get("rect")
                    if rect and len(rect) == 4:
                        left, top = int(rect[0]), int(rect[1])
                        w = int(m.get("width", rect[2] - rect[0]))
                        h = int(m.get("height", rect[3] - rect[1]))
                    else:
                        left = int(m.get("x", m.get("left", 0)))
                        top = int(m.get("y", m.get("top", 0)))
                        w = int(m.get("width", 1920))
                        h = int(m.get("height", 1080))
                    break

        effective_max_w = self.max_width
        if not effective_max_w and self.active_monitor_id == 0 and w > 2560:
            effective_max_w = 2560

        current_params = (
            self.quality,
            effective_max_w,
            getattr(self, "resample_filter", "bilinear"),
            getattr(self, "subsampling", 2),
            getattr(self, "grayscale", False),
            self.active_monitor_id,
            w,
            h,
        )
        return left, top, w, h, effective_max_w, current_params

    def _capture_and_encode_sync(self, force: bool = False) -> Optional[bytes]:
        """Performs a single OS screen grab and SIMD JPEG encode, updating self._last_encoded_frame."""
        try:
            self._attach_window_station()
            left, top, w, h, effective_max_w, current_params = self._compute_current_params()
            params_changed = (current_params != self._last_encode_params)
            now = time.perf_counter()

            # Tier 0 (Windows DXGI Desktop Duplication via bettercam/dxcam when single monitor is selected)
            if sys.platform == "win32" and dxcam_lib is not None and self.active_monitor_id in (0, 1) and len(self.monitors) == 1:
                cam = self._get_thread_dxcam(0)
                if cam is not None:
                    try:
                        frame_arr = cam.grab()
                        if frame_arr is not None and hasattr(frame_arr, "shape") and len(frame_arr.shape) == 3:
                            fh, fw = int(frame_arr.shape[0]), int(frame_arr.shape[1])
                            raw_mv = memoryview(frame_arr).cast("B")
                            curr_hash = hash(raw_mv[::512].tobytes())
                            if not force and not params_changed and curr_hash == self._last_frame_hash and self._last_encoded_frame is not None:
                                self._last_frame_sent_time = now
                                return self._last_encoded_frame
                            encoded = self._encode_bgra_fast(frame_arr, fw, fh, effective_max_w)
                            if encoded:
                                self._last_frame_hash = curr_hash
                                self._last_frame_sent_time = now
                                self._last_encoded_frame = encoded
                                self._last_encode_params = current_params
                                return encoded
                    except Exception:
                        pass

            # Tier 1 (Windows): Zero-allocation Win32 GDI DIBSection capture with pure SRCCOPY
            native_cap = self._get_thread_native_cap()
            if native_cap is not None:
                try:
                    dims, raw_buf, cursor_changed = native_cap.grab(left, top, w, h)
                    if dims is not None and raw_buf is not None:
                        curr_hash = hash(memoryview(raw_buf)[::512].tobytes())
                        is_static = (
                            not force
                            and not params_changed
                            and not cursor_changed
                            and curr_hash == self._last_frame_hash
                            and self._last_encoded_frame is not None
                        )
                        if is_static:
                            self._last_frame_sent_time = now
                            return self._last_encoded_frame

                        encoded = self._encode_bgra_fast(raw_buf, dims[0], dims[1], effective_max_w)
                        if encoded:
                            self._last_frame_hash = curr_hash
                            self._last_frame_sent_time = now
                            self._last_encoded_frame = encoded
                            self._last_encode_params = current_params
                            return encoded
                except Exception:
                    self._attach_window_station(force=True)

            # Tier 2 (macOS Quartz / Linux X11 XShm / Windows Fallback): thread-safe mss direct grab
            sct = self._get_thread_sct()
            if sct is not None:
                try:
                    if self.active_monitor_id == 0:
                        mon_target = sct.monitors[0]
                    elif 1 <= self.active_monitor_id < len(sct.monitors):
                        mon_target = sct.monitors[self.active_monitor_id]
                    else:
                        mon_target = {"left": left, "top": top, "width": w, "height": h}

                    shot = sct.grab(mon_target)
                    raw_bgra = shot.raw
                    curr_hash = hash(memoryview(raw_bgra)[::512].tobytes())
                    is_static = (
                        not force
                        and not params_changed
                        and curr_hash == self._last_frame_hash
                        and self._last_encoded_frame is not None
                    )
                    if is_static:
                        self._last_frame_sent_time = now
                        return self._last_encoded_frame

                    encoded = self._encode_bgra_fast(raw_bgra, shot.width, shot.height, effective_max_w)
                    if encoded:
                        self._last_frame_hash = curr_hash
                        self._last_frame_sent_time = now
                        self._last_encoded_frame = encoded
                        self._last_encode_params = current_params
                        return encoded
                except Exception:
                    self._tls.sct = None

            # Fallback Tier 3: Pillow ImageGrab (Cross-platform)
            bbox = (left, top, left + w, top + h) if self.active_monitor_id != 0 else None
            img = None
            if not (sys.platform.startswith("linux") and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY")):
                try:
                    img = ImageGrab.grab(bbox=bbox, all_screens=True)
                except Exception:
                    try:
                        img = ImageGrab.grab(bbox=bbox, all_screens=(self.active_monitor_id == 0))
                    except Exception:
                        img = None

            if img is None:
                if self.is_headless:
                    w_res, h_res = getattr(self, 'resolution', (1920, 1080))
                    return self._get_cached_headless_placeholder(w_res, h_res)
                return None

            raw_img_bytes = img.tobytes()
            curr_hash = hash(memoryview(raw_img_bytes)[::512].tobytes())
            if not force and not params_changed and curr_hash == self._last_frame_hash and self._last_encoded_frame is not None:
                self._last_frame_sent_time = now
                return self._last_encoded_frame

            encoded = self._encode_pil_image(img, effective_max_w)
            self._last_frame_hash = curr_hash
            self._last_frame_sent_time = now
            self._last_encoded_frame = encoded
            self._last_encode_params = current_params
            return encoded

        except Exception:
            if getattr(self, 'is_headless', False):
                try:
                    w_res, h_res = getattr(self, 'resolution', (1920, 1080))
                    return self._get_cached_headless_placeholder(w_res, h_res)
                except Exception:
                    pass
            return None

    def capture_frame(self, force: bool = False) -> Optional[bytes]:
        """
        Returns the latest SIMD-encoded JPEG frame non-blockingly during streaming (120-240 FPS),
        while a background producer thread continuously captures & encodes display updates in parallel.
        When force=True, parameters changed, or no cached frame exists yet, performs an immediate synchronous capture.
        """
        now = time.perf_counter()
        self._last_poll_ts = now
        _, _, _, _, _, current_params = self._compute_current_params()
        params_changed = (current_params != self._last_encode_params)

        if not force and not params_changed and self._last_encoded_frame is not None:
            self._ensure_bg_producer()
            eff_interval = 0.0 if getattr(self, "static_cache_enabled", True) else max(0.0, self.keepalive_interval)
            if eff_interval <= 0.0 or (now - self._last_frame_sent_time) >= eff_interval:
                self._last_frame_sent_time = now
                return self._last_encoded_frame
            return None

        encoded = self._capture_and_encode_sync(force=True)
        if encoded is not None:
            self._ensure_bg_producer()
        return encoded

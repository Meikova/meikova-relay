"""Built-in pure-Python ctypes wrapper for libjpeg-turbo (compatible with PyTurboJPEG API).
Bundled directly in `vendor/packages/turbojpeg.py` so Meikova Relay can use SIMD TurboJPEG
out-of-the-box without requiring `pip install PyTurboJPEG`.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import sys
import threading
from pathlib import Path
from typing import Optional

TJPF_RGB = 0
TJPF_BGR = 1
TJPF_RGBX = 2
TJPF_BGRX = 3
TJPF_XBGR = 4
TJPF_XRGB = 5
TJPF_GRAY = 6
TJPF_RGBA = 7
TJPF_BGRA = 8

TJSAMP_444 = 0
TJSAMP_422 = 1
TJSAMP_420 = 2
TJSAMP_GRAY = 3

TJFLAG_FASTDCT = 2048


class TurboJPEG:
    """Drop-in compatible `TurboJPEG` wrapper over native `libturbojpeg`."""

    def __init__(self, lib_path: Optional[str] = None):
        self._lib = None
        self._tls = threading.local()
        here = Path(__file__).resolve().parents[2] / "host_agent"
        vendor_native = Path(__file__).resolve().parents[1] / "native"
        candidates = []
        if lib_path:
            candidates.append(str(lib_path))
        if sys.platform == "win32":
            candidates.extend([
                str(vendor_native / "turbojpeg.dll"),
                str(here / "turbojpeg.dll"),
                str(here / "libs" / "win64" / "turbojpeg.dll"),
                "turbojpeg.dll",
                "libturbojpeg.dll",
                r"C:\libjpeg-turbo64\bin\turbojpeg.dll",
                r"C:\Program Files\libjpeg-turbo64\bin\turbojpeg.dll",
            ])
        elif sys.platform == "darwin":
            candidates.extend([
                str(vendor_native / "libturbojpeg.dylib"),
                str(here / "libturbojpeg.dylib"),
                "/opt/homebrew/opt/jpeg-turbo/lib/libturbojpeg.dylib",
                "/opt/homebrew/lib/libturbojpeg.dylib",
                "/usr/local/opt/jpeg-turbo/lib/libturbojpeg.dylib",
                "/usr/local/lib/libturbojpeg.dylib",
                "libturbojpeg.dylib",
            ])
        else:
            candidates.extend([
                str(vendor_native / "libturbojpeg.so.0"),
                str(here / "libturbojpeg.so.0"),
                "libturbojpeg.so.0",
                "/usr/lib/x86_64-linux-gnu/libturbojpeg.so.0",
                "/usr/lib/aarch64-linux-gnu/libturbojpeg.so.0",
                "/usr/lib64/libturbojpeg.so.0",
                "/usr/lib/libturbojpeg.so.0",
                "/usr/lib/libturbojpeg.so",
            ])
        found = ctypes.util.find_library("turbojpeg")
        if found:
            candidates.append(found)

        for path in candidates:
            try:
                lib = ctypes.CDLL(path)
                lib.tjInitCompress.restype = ctypes.c_void_p
                lib.tjCompress2.argtypes = [
                    ctypes.c_void_p,
                    ctypes.c_void_p,
                    ctypes.c_int,
                    ctypes.c_int,
                    ctypes.c_int,
                    ctypes.c_int,
                    ctypes.POINTER(ctypes.c_void_p),
                    ctypes.POINTER(ctypes.c_ulong),
                    ctypes.c_int,
                    ctypes.c_int,
                    ctypes.c_int,
                ]
                lib.tjCompress2.restype = ctypes.c_int
                lib.tjFree.argtypes = [ctypes.c_void_p]
                lib.tjDestroy.argtypes = [ctypes.c_void_p]
                self._lib = lib
                break
            except Exception:
                continue

    def _get_handle(self):
        if self._lib is None:
            return None
        h = getattr(self._tls, "handle", None)
        if not h:
            h = self._lib.tjInitCompress()
            self._tls.handle = h
        return h

    def encode(
        self,
        img_array,
        quality: int = 85,
        pixel_format: int = TJPF_BGR,
        jpeg_subsample: int = TJSAMP_422,
        flags: int = TJFLAG_FASTDCT,
    ) -> bytes:
        h = self._get_handle()
        if not h:
            raise RuntimeError("Native libturbojpeg shared library not found on system")

        if hasattr(img_array, "shape") and hasattr(img_array, "__array_interface__"):
            height, width = int(img_array.shape[0]), int(img_array.shape[1])
            channels = int(img_array.shape[2]) if len(img_array.shape) > 2 else 1
            pitch = width * channels
            src_ptr = ctypes.c_void_p(img_array.__array_interface__["data"][0])
        else:
            raise TypeError("img_array must be a numpy ndarray")

        jpeg_buf = ctypes.c_void_p()
        jpeg_size = ctypes.c_ulong(0)
        rc = self._lib.tjCompress2(
            h,
            src_ptr,
            width,
            pitch,
            height,
            int(pixel_format),
            ctypes.byref(jpeg_buf),
            ctypes.byref(jpeg_size),
            int(jpeg_subsample),
            max(1, min(100, int(quality))),
            int(flags),
        )
        if rc != 0 or not jpeg_buf.value or jpeg_size.value == 0:
            if jpeg_buf.value:
                self._lib.tjFree(jpeg_buf)
            raise RuntimeError(f"tjCompress2 failed with code {rc}")
        try:
            return ctypes.string_at(jpeg_buf.value, jpeg_size.value)
        finally:
            self._lib.tjFree(jpeg_buf)

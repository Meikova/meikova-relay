import sys
import time
import threading
import ctypes
import io
import base64
import hashlib
import struct
from typing import Callable, Optional, Tuple, List

try:
    import win32clipboard
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

try:
    from PIL import Image, ImageGrab
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

if sys.platform == "win32":
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    # GlobalAlloc / Lock / Unlock / Free with exact 64-bit and 32-bit types
    kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p

    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p

    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.restype = ctypes.c_bool

    kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
    kernel32.GlobalFree.restype = ctypes.c_void_p

    # User32 Clipboard functions with exact 64-bit and 32-bit types
    user32.OpenClipboard.argtypes = [ctypes.c_void_p]
    user32.OpenClipboard.restype = ctypes.c_bool

    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = ctypes.c_bool

    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = ctypes.c_bool

    user32.IsClipboardFormatAvailable.argtypes = [ctypes.c_uint]
    user32.IsClipboardFormatAvailable.restype = ctypes.c_bool

    user32.GetClipboardData.argtypes = [ctypes.c_uint]
    user32.GetClipboardData.restype = ctypes.c_void_p

    user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p

    user32.GetClipboardSequenceNumber.argtypes = []
    user32.GetClipboardSequenceNumber.restype = ctypes.c_uint

    # Desktop security context
    user32.OpenInputDesktop.argtypes = [ctypes.c_uint, ctypes.c_bool, ctypes.c_uint]
    user32.OpenInputDesktop.restype = ctypes.c_void_p

    user32.SetThreadDesktop.argtypes = [ctypes.c_void_p]
    user32.SetThreadDesktop.restype = ctypes.c_bool

    user32.CloseDesktop.argtypes = [ctypes.c_void_p]
    user32.CloseDesktop.restype = ctypes.c_bool

    CF_TEXT = 1
    CF_BITMAP = 2
    CF_DIB = 8
    CF_UNICODETEXT = 13
    CF_HDROP = 15
    CF_DIBV5 = 17
    GMEM_MOVEABLE = 0x0002

class ClipboardManager:
    """Synchronizes Windows, Linux, and macOS clipboard (text, images, and files) with remote client with thread-safety and desktop awareness."""

    def __init__(
        self,
        on_clipboard_change: Optional[Callable[[str], None]] = None,
        on_clipboard_image: Optional[Callable[[str, str], None]] = None,
        on_clipboard_files: Optional[Callable[[List[str]], None]] = None,
    ):
        self.on_clipboard_change = on_clipboard_change
        self.on_clipboard_image = on_clipboard_image
        self.on_clipboard_files = on_clipboard_files
        self.last_text: Optional[str] = None
        self.last_image_hash: Optional[str] = None
        self.last_files: Optional[List[str]] = None
        self._last_seq: int = 0
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._attached = False

    def _attach_desktop(self):
        if sys.platform == "win32" and not self._attached:
            try:
                hDesk = user32.OpenInputDesktop(0, False, 0x01FF)
                if hDesk:
                    user32.SetThreadDesktop(hDesk)
                self._attached = True
            except Exception:
                pass

    def get_clipboard_text(self) -> Optional[str]:
        with self._lock:
            self._attach_desktop()
            if sys.platform == "win32":
                for _ in range(5):
                    if HAS_WIN32:
                        try:
                            win32clipboard.OpenClipboard()
                            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                                data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                                win32clipboard.CloseClipboard()
                                return data
                            win32clipboard.CloseClipboard()
                            return None
                        except Exception:
                            try: win32clipboard.CloseClipboard()
                            except Exception: pass

                    # Native Windows ctypes fallback (64-bit safe)
                    try:
                        if user32.OpenClipboard(None):
                            try:
                                if user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
                                    h_mem = user32.GetClipboardData(CF_UNICODETEXT)
                                    if h_mem:
                                        p_mem = kernel32.GlobalLock(h_mem)
                                        if p_mem:
                                            try:
                                                return ctypes.wstring_at(p_mem)
                                            finally:
                                                kernel32.GlobalUnlock(h_mem)
                                return None
                            finally:
                                user32.CloseClipboard()
                    except Exception:
                        pass
                    time.sleep(0.02)
                return None
            elif sys.platform == "darwin":
                try:
                    import subprocess
                    return subprocess.check_output(["pbpaste"], text=True)
                except Exception:
                    return None
            else:
                # Linux xclip / xsel
                import subprocess
                for cmd in [["xclip", "-selection", "clipboard", "-o"], ["xsel", "-b", "-o"]]:
                    try:
                        return subprocess.check_output(cmd, text=True)
                    except Exception:
                        continue
                return None

    def set_clipboard_text(self, text: str) -> bool:
        if text is None:
            return False
        with self._lock:
            self._attach_desktop()
            if sys.platform == "win32":
                for _ in range(10):
                    if HAS_WIN32:
                        try:
                            win32clipboard.OpenClipboard()
                            win32clipboard.EmptyClipboard()
                            win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, text)
                            win32clipboard.CloseClipboard()
                            self.last_text = text
                            return True
                        except Exception:
                            try: win32clipboard.CloseClipboard()
                            except Exception: pass

                    # Native Windows ctypes fallback (64-bit safe)
                    try:
                        data = text.encode('utf-16le') + b'\x00\x00'
                        h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
                        if h_mem:
                            p_mem = kernel32.GlobalLock(h_mem)
                            if p_mem:
                                ctypes.memmove(p_mem, data, len(data))
                                kernel32.GlobalUnlock(h_mem)
                                if user32.OpenClipboard(None):
                                    try:
                                        user32.EmptyClipboard()
                                        res = user32.SetClipboardData(CF_UNICODETEXT, h_mem)
                                        if res:
                                            self.last_text = text
                                            return True
                                    finally:
                                        user32.CloseClipboard()
                                else:
                                    kernel32.GlobalFree(h_mem)
                            else:
                                kernel32.GlobalFree(h_mem)
                    except Exception:
                        pass
                    time.sleep(0.02)
                return False
            elif sys.platform == "darwin":
                try:
                    import subprocess
                    p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
                    p.communicate(text.encode("utf-8"))
                    self.last_text = text
                    return p.returncode == 0
                except Exception:
                    return False
            else:
                # Linux xclip / xsel
                import subprocess
                for cmd in [["xclip", "-selection", "clipboard"], ["xsel", "-b", "-i"]]:
                    try:
                        p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
                        p.communicate(text.encode("utf-8"))
                        if p.returncode == 0:
                            self.last_text = text
                            return True
                    except Exception:
                        continue
                return False

    def get_clipboard_image(self) -> Optional[Tuple[str, str]]:
        """Extracts image from clipboard as base64 and mime type."""
        if not HAS_PIL:
            return None
        with self._lock:
            self._attach_desktop()
            try:
                clip = ImageGrab.grabclipboard()
                if isinstance(clip, Image.Image):
                    has_alpha = clip.mode in ("RGBA", "LA") or (clip.mode == "P" and "transparency" in clip.info)
                    fmt = "PNG" if has_alpha else "JPEG"
                    mime = "image/png" if has_alpha else "image/jpeg"
                    buf = io.BytesIO()
                    if fmt == "JPEG":
                        clip.convert("RGB").save(buf, "JPEG", quality=85, optimize=True)
                    else:
                        clip.save(buf, "PNG", optimize=True)
                    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
                    return b64, mime
            except Exception:
                pass
            return None

    def set_clipboard_image(self, b64_data: str, mime: str = "image/png") -> bool:
        """Sets base64 image data to Windows/system clipboard as CF_DIB."""
        if not b64_data or not HAS_PIL:
            return False
        with self._lock:
            self._attach_desktop()
            try:
                raw_bytes = base64.b64decode(b64_data)
                img = Image.open(io.BytesIO(raw_bytes))
                buf = io.BytesIO()
                img.convert("RGB").save(buf, "BMP")
                dib_data = buf.getvalue()[14:]  # Strip 14-byte BMP header for standard CF_DIB

                self.last_image_hash = hashlib.sha1(raw_bytes[:512]).hexdigest()

                if sys.platform == "win32":
                    for _ in range(5):
                        if HAS_WIN32:
                            try:
                                win32clipboard.OpenClipboard()
                                win32clipboard.EmptyClipboard()
                                win32clipboard.SetClipboardData(win32clipboard.CF_DIB, dib_data)
                                win32clipboard.CloseClipboard()
                                return True
                            except Exception:
                                try: win32clipboard.CloseClipboard()
                                except Exception: pass

                        try:
                            h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(dib_data))
                            if h_mem:
                                p_mem = kernel32.GlobalLock(h_mem)
                                if p_mem:
                                    ctypes.memmove(p_mem, dib_data, len(dib_data))
                                    kernel32.GlobalUnlock(h_mem)
                                    if user32.OpenClipboard(None):
                                        try:
                                            user32.EmptyClipboard()
                                            res = user32.SetClipboardData(CF_DIB, h_mem)
                                            if res:
                                                return True
                                        finally:
                                            user32.CloseClipboard()
                                    else:
                                        kernel32.GlobalFree(h_mem)
                                else:
                                    kernel32.GlobalFree(h_mem)
                        except Exception:
                            pass
                        time.sleep(0.02)
                    return False
            except Exception:
                return False
            return False

    def get_clipboard_files(self) -> Optional[List[str]]:
        """Extracts list of copied file paths from clipboard (CF_HDROP)."""
        if not HAS_PIL:
            return None
        with self._lock:
            self._attach_desktop()
            try:
                clip = ImageGrab.grabclipboard()
                if isinstance(clip, list) and len(clip) > 0 and isinstance(clip[0], str):
                    return clip
            except Exception:
                pass
            return None

    def set_clipboard_files(self, file_paths: List[str]) -> bool:
        """Sets list of file paths to Windows clipboard as CF_HDROP."""
        if not file_paths:
            return False
        with self._lock:
            self._attach_desktop()
            self.last_files = list(file_paths)
            if sys.platform == "win32":
                try:
                    header = struct.pack('IIIIi', 20, 0, 0, 0, 1)
                    file_bytes = ('\0'.join(file_paths) + '\0\0').encode('utf-16le')
                    payload = header + file_bytes
                    h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(payload))
                    if not h_mem:
                        return False
                    p_mem = kernel32.GlobalLock(h_mem)
                    if not p_mem:
                        kernel32.GlobalFree(h_mem)
                        return False
                    ctypes.memmove(p_mem, payload, len(payload))
                    kernel32.GlobalUnlock(h_mem)
                    for _ in range(5):
                        if user32.OpenClipboard(None):
                            try:
                                user32.EmptyClipboard()
                                res = user32.SetClipboardData(CF_HDROP, h_mem)
                                return bool(res)
                            finally:
                                user32.CloseClipboard()
                        time.sleep(0.02)
                    kernel32.GlobalFree(h_mem)
                except Exception:
                    return False
            return False

    def start_listener(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop_listener(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            try:
                self._thread.join(timeout=0.3)
            except Exception:
                pass

    def _loop(self):
        while self._running:
            try:
                if sys.platform == "win32":
                    seq = user32.GetClipboardSequenceNumber()
                    if seq == self._last_seq:
                        time.sleep(0.08)
                        continue
                    self._last_seq = seq

                self._attach_desktop()

                has_text = True
                has_files = False
                has_image = False
                if sys.platform == "win32":
                    try:
                        if user32.OpenClipboard(None):
                            try:
                                has_text = bool(user32.IsClipboardFormatAvailable(CF_UNICODETEXT) or user32.IsClipboardFormatAvailable(CF_TEXT))
                                has_files = bool(user32.IsClipboardFormatAvailable(CF_HDROP))
                                has_image = bool(user32.IsClipboardFormatAvailable(CF_DIB) or user32.IsClipboardFormatAvailable(CF_BITMAP) or user32.IsClipboardFormatAvailable(CF_DIBV5))
                            finally:
                                user32.CloseClipboard()
                    except Exception:
                        has_text, has_files, has_image = True, True, True

                # 1. Text
                if has_text:
                    curr_text = self.get_clipboard_text()
                    if curr_text and curr_text != self.last_text:
                        self.last_text = curr_text
                        if self.on_clipboard_change:
                            self.on_clipboard_change(curr_text)
                        time.sleep(0.08)
                        continue

                # 2. Image
                if has_image and self.on_clipboard_image:
                    img_data = self.get_clipboard_image()
                    if img_data:
                        b64, mime = img_data
                        h = hashlib.sha1(b64[:512].encode('ascii')).hexdigest()
                        if h != self.last_image_hash:
                            self.last_image_hash = h
                            self.on_clipboard_image(b64, mime)
                            time.sleep(0.08)
                            continue

                # 3. Files
                if has_files and self.on_clipboard_files:
                    files = self.get_clipboard_files()
                    if files and files != self.last_files:
                        self.last_files = files
                        self.on_clipboard_files(files)
                        time.sleep(0.08)
                        continue

            except Exception:
                pass
            time.sleep(0.08)

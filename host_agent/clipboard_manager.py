import sys
import time
import threading
import ctypes
from typing import Callable, Optional

try:
    import win32clipboard
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

class ClipboardManager:
    """Synchronizes Windows clipboard with remote client with thread-safety and desktop awareness."""

    def __init__(self, on_clipboard_change: Optional[Callable[[str], None]] = None):
        self.on_clipboard_change = on_clipboard_change
        self.last_text: Optional[str] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def _attach_desktop(self):
        if sys.platform == "win32":
            try:
                user32 = ctypes.windll.user32
                hDesk = user32.OpenInputDesktop(0, False, 0x01FF)
                if hDesk:
                    user32.SetThreadDesktop(hDesk)
                    user32.CloseDesktop(hDesk)
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

                    # Native Windows ctypes fallback
                    try:
                        user32 = ctypes.windll.user32
                        kernel32 = ctypes.windll.kernel32
                        CF_UNICODETEXT = 13
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

                    # Native Windows ctypes fallback
                    try:
                        user32 = ctypes.windll.user32
                        kernel32 = ctypes.windll.kernel32
                        CF_UNICODETEXT = 13
                        GMEM_MOVEABLE = 0x0002
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
                                        user32.SetClipboardData(CF_UNICODETEXT, h_mem)
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

    def start_listener(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop_listener(self):
        self._running = False

    def _loop(self):
        while self._running:
            try:
                curr = self.get_clipboard_text()
                if curr and curr != self.last_text:
                    self.last_text = curr
                    if self.on_clipboard_change:
                        self.on_clipboard_change(curr)
            except Exception:
                pass
            time.sleep(0.2) # Fast 200ms clipboard polling

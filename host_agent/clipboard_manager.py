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
    """Synchronizes Windows clipboard with remote client."""

    def __init__(self, on_clipboard_change: Optional[Callable[[str], None]] = None):
        self.on_clipboard_change = on_clipboard_change
        self.last_text: Optional[str] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def get_clipboard_text(self) -> Optional[str]:
        if sys.platform == "win32":
            if HAS_WIN32:
                try:
                    win32clipboard.OpenClipboard()
                    if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                        return win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                    return None
                except Exception:
                    return None
                finally:
                    try: win32clipboard.CloseClipboard()
                    except Exception: pass

            # Native Windows ctypes fallback (Zero external dependencies)
            try:
                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32
                CF_UNICODETEXT = 13
                if not user32.OpenClipboard(None):
                    return None
                try:
                    if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
                        return None
                    h_mem = user32.GetClipboardData(CF_UNICODETEXT)
                    if not h_mem:
                        return None
                    p_mem = kernel32.GlobalLock(h_mem)
                    if not p_mem:
                        return None
                    try:
                        return ctypes.wstring_at(p_mem)
                    finally:
                        kernel32.GlobalUnlock(h_mem)
                finally:
                    user32.CloseClipboard()
            except Exception:
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
        if sys.platform == "win32":
            if HAS_WIN32:
                try:
                    win32clipboard.OpenClipboard()
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, text)
                    self.last_text = text
                    return True
                except Exception:
                    return False
                finally:
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
                if not h_mem:
                    return False
                p_mem = kernel32.GlobalLock(h_mem)
                if not p_mem:
                    kernel32.GlobalFree(h_mem)
                    return False
                ctypes.memmove(p_mem, data, len(data))
                kernel32.GlobalUnlock(h_mem)

                if not user32.OpenClipboard(None):
                    kernel32.GlobalFree(h_mem)
                    return False
                try:
                    user32.EmptyClipboard()
                    user32.SetClipboardData(CF_UNICODETEXT, h_mem)
                    self.last_text = text
                    return True
                finally:
                    user32.CloseClipboard()
            except Exception:
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

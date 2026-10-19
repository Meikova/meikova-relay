import time
import threading
import win32clipboard
from typing import Callable, Optional

class ClipboardManager:
    """Synchronizes Windows clipboard with remote client."""

    def __init__(self, on_clipboard_change: Optional[Callable[[str], None]] = None):
        self.on_clipboard_change = on_clipboard_change
        self.last_text: Optional[str] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def get_clipboard_text(self) -> Optional[str]:
        try:
            win32clipboard.OpenClipboard()
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                return data
            return None
        except Exception:
            return None
        finally:
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass

    def set_clipboard_text(self, text: str) -> bool:
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, text)
            self.last_text = text # prevent loop echo
            return True
        except Exception:
            return False
        finally:
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass

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
            time.sleep(1.0) # Check every 1s

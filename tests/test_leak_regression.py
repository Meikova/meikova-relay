import os
import sys
import unittest
import ctypes
import time
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

user32 = ctypes.windll.user32 if hasattr(ctypes, "windll") else None
kernel32 = ctypes.windll.kernel32 if hasattr(ctypes, "windll") else None

def get_process_gdi_count() -> int:
    if not user32 or not kernel32:
        return 0
    h_proc = kernel32.GetCurrentProcess()
    return user32.GetGuiResources(h_proc, 0) # GR_GDIOBJECTS

def get_process_handle_count() -> int:
    if not kernel32:
        return 0
    h_proc = kernel32.GetCurrentProcess()
    count = ctypes.c_ulong()
    if hasattr(kernel32, "GetProcessHandleCount") and kernel32.GetProcessHandleCount(h_proc, ctypes.byref(count)):
        return count.value
    return 0


class TestLeakRegression(unittest.TestCase):
    """TDD Regression Tests verifying ZERO leaks in MeikovaRelayHost."""

    def test_cursor_manager_no_handle_leak(self):
        """Verifies get_cursor() does not leak Win32 desktop handles over hundreds of cycles."""
        if sys.platform != "win32":
            self.skipTest("Windows-only test")

        from host_agent.cursor_manager import CursorManager

        cm = CursorManager()
        # Warm-up
        for _ in range(10):
            cm.get_cursor()

        initial_handles = get_process_handle_count()

        # Run 300 cycles of get_cursor
        for _ in range(300):
            cm.get_cursor()

        final_handles = get_process_handle_count()
        handle_growth = final_handles - initial_handles

        cm.stop_listener()

        # Without the fix, 300 calls when GetCursorInfo fails leak 300 handles!
        self.assertLessEqual(
            handle_growth, 5,
            f"Handle leak detected! Handles grew by {handle_growth} over 300 get_cursor calls."
        )

    def test_screen_capture_no_gdi_leak_on_resize(self):
        """Verifies NativeWin32Capture does not leak GDI DIBSection objects when resizing/recreating bitmaps."""
        if sys.platform != "win32":
            self.skipTest("Windows-only test")

        from host_agent.screen_capture import NativeWin32Capture

        cap = NativeWin32Capture()
        if not cap.src_dc or not cap.mem_dc:
            self.skipTest("GDI DC not available")

        # Warm-up
        cap._ensure_bitmap(1920, 1080)
        initial_gdi = get_process_gdi_count()

        # Alternate sizes 100 times - without unselecting DIBSection, DeleteObject fails and GDI grows by 100!
        for i in range(100):
            w = 1920 if (i % 2 == 0) else 1280
            h = 1080 if (i % 2 == 0) else 720
            cap._ensure_bitmap(w, h)

        final_gdi = get_process_gdi_count()
        gdi_growth = final_gdi - initial_gdi

        cap.close()

        self.assertLessEqual(
            gdi_growth, 2,
            f"GDI Object leak detected! GDI objects grew by {gdi_growth} over 100 bitmap resizes."
        )

    def test_gui_agent_eval_js_bounded_threads(self):
        """Verifies HostApi._eval_js does not spawn unbounded OS threads on repeated log messages."""
        from host_agent.gui_agent import HostApi

        cfg = {"relay": "ws://localhost:8080", "room_id": "TEST", "pin": "1234"}
        api = HostApi(cfg, None)

        import threading
        initial_threads = threading.active_count()

        # Send 100 logs
        for i in range(100):
            api._log(f"Test log message #{i}")

        time.sleep(0.1)
        final_threads = threading.active_count()
        thread_growth = final_threads - initial_threads

        # Thread count should be bounded (at most 1 worker thread created)
        self.assertLessEqual(
            thread_growth, 2,
            f"Thread leak detected! Active threads grew by {thread_growth} over 100 logs."
        )

    def test_gui_view_html_log_ring_buffer(self):
        """Verifies gui_view.html contains ring-buffer pruning for log elements."""
        view_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "host_agent", "gui_view.html")
        self.assertTrue(os.path.exists(view_path), f"File missing: {view_path}")

        with open(view_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for ring buffer DOM pruning logic in addLog function
        self.assertIn("box.children.length", content, "addLog in gui_view.html must prune children to prevent DOM bloat")


if __name__ == "__main__":
    unittest.main()

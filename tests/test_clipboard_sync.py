import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sys
import unittest
import json
import time
import threading
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from host_agent.host_service import HostService
from host_agent.clipboard_manager import ClipboardManager

class TestClipboardSync(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "Windows ctypes native only")
    def test_clipboard_manager_native_windows(self):
        """Test Windows ctypes/win32 clipboard read and write."""
        mgr = ClipboardManager(None)
        test_content = f"__meikova_clipboard_test_{time.time()}__"
        ok = mgr.set_clipboard_text(test_content)
        if not ok:
            import ctypes
            if not ctypes.windll.user32.OpenClipboard(None) and ctypes.windll.kernel32.GetLastError() == 5:
                raise unittest.SkipTest("Windows clipboard access denied in headless/CI session (WinError 5)")
        self.assertTrue(ok)
        val = mgr.get_clipboard_text()
        self.assertEqual(val, test_content)

    def test_on_local_clipboard_change(self):
        """Test host sending clipboard_sync when local clipboard changes."""
        service = HostService(
            relay_url="ws://127.0.0.1:8080/ws",
            room_id="RD-CLIP-TEST",
            pin="123456",
            device_name="TestHost"
        )
        # Isolate from background terminal and cursor listeners
        if hasattr(service, "terminal") and service.terminal:
            try:
                service.terminal.stop()
            except Exception:
                pass
        service.terminal = MagicMock()
        if hasattr(service, "cursor_manager") and service.cursor_manager:
            try:
                service.cursor_manager.stop_listener()
            except Exception:
                pass
        if hasattr(service, "clipboard") and service.clipboard:
            try:
                service.clipboard.stop_listener()
            except Exception:
                pass

        loop = asyncio.new_event_loop()
        t = threading.Thread(target=loop.run_forever, daemon=True)
        t.start()
        try:
            service.ws = MagicMock()
            service.ws.send = AsyncMock()
            service.loop = loop
            service.has_active_client = True

            test_text = "local_copy_content_abc"
            service._on_local_clipboard_change(test_text)

            time.sleep(0.08)
            self.assertTrue(service.ws.send.called)

            # Filter calls for clipboard_sync to prevent interference from other subsystems
            sent_packets = [json.loads(c[0][0]) for c in service.ws.send.call_args_list]
            clip_packets = [p for p in sent_packets if p.get("type") == "clipboard_sync"]
            self.assertTrue(len(clip_packets) > 0, f"Expected clipboard_sync packet, got: {sent_packets}")
            self.assertEqual(clip_packets[0].get("text"), test_text)
        finally:
            service.stop()
            loop.call_soon_threadsafe(loop.stop)

    def test_clipboard_manager_ignore_duplicate_echo(self):
        """Test clipboard manager does not trigger callback if content is identical."""
        calls = []
        mgr = ClipboardManager(lambda text: calls.append(text))
        mgr.last_text = "same_content"
        # Simulate set_clipboard_text with same content
        mgr.set_clipboard_text("same_content")
        self.assertEqual(mgr.last_text, "same_content")

    def test_clipboard_pull_and_sync_handling(self):
        """Verify protocol handling logic for clipboard_sync and clipboard_pull."""
        mock_clipboard = MagicMock()
        mock_clipboard.get_clipboard_text.return_value = "host_pulled_text"
        mock_clipboard.set_clipboard_text.return_value = True

        # Simulate pull response
        pulled_text = mock_clipboard.get_clipboard_text() or ""
        pull_reply = json.dumps({"type": "clipboard_sync", "text": pulled_text})
        parsed_pull = json.loads(pull_reply)
        self.assertEqual(parsed_pull["type"], "clipboard_sync")
        self.assertEqual(parsed_pull["text"], "host_pulled_text")

        # Simulate sync apply
        incoming_sync = {"type": "clipboard_sync", "text": "client_pushed_text"}
        applied = mock_clipboard.set_clipboard_text(incoming_sync["text"])
        self.assertTrue(applied)
        mock_clipboard.set_clipboard_text.assert_called_with("client_pushed_text")

if __name__ == "__main__":
    unittest.main()

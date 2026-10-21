import unittest
import sys
import time
from host_agent.cursor_manager import CursorManager

class TestCursorManager(unittest.TestCase):

    def test_get_cursor_returns_valid_string(self):
        cm = CursorManager()
        c = cm.get_cursor()
        self.assertIsInstance(c, str)
        self.assertGreater(len(c), 0)
        valid_css_cursors = {
            "default", "pointer", "text", "wait", "crosshair",
            "nwse-resize", "nesw-resize", "ew-resize", "ns-resize",
            "move", "not-allowed", "progress", "help", "none"
        }
        self.assertIn(c, valid_css_cursors)

    def test_check_immediate(self):
        cm = CursorManager()
        # initial state
        cur = cm.get_cursor()
        cm.last_cursor = "non_existent_cursor_123"
        changed = cm.check_immediate()
        self.assertEqual(changed, cur)
        self.assertEqual(cm.last_cursor, cur)
        # Calling immediately again without change returns None
        self.assertIsNone(cm.check_immediate())

    def test_listener_start_stop(self):
        events = []
        cm = CursorManager(on_cursor_change=lambda c: events.append(c))
        cm.start_listener()
        time.sleep(0.12)
        cm.stop_listener()
        self.assertFalse(cm._running)

if __name__ == "__main__":
    unittest.main()

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from host_agent.virtual_display import (
    is_headless_display,
    get_virtual_display_driver_status,
    generate_headless_placeholder,
    IDDCX_DRIVER_URL
)
from host_agent.screen_capture import ScreenCapture

class TestVirtualDisplay(unittest.TestCase):
    def test_headless_check_non_crashing(self):
        """Tests that checking headless display state returns a bool and never crashes."""
        headless = is_headless_display()
        self.assertIsInstance(headless, bool)

    def test_driver_status_structure(self):
        """Tests driver status returns properly typed dict."""
        status = get_virtual_display_driver_status()
        self.assertIsInstance(status, dict)
        self.assertIn("installed", status)
        self.assertIn("driver_name", status)

    def test_headless_placeholder_frame_generation(self):
        """Tests generating high-resolution placeholder frame when headless."""
        frame_bytes = generate_headless_placeholder(1280, 720)
        self.assertIsInstance(frame_bytes, bytes)
        self.assertGreater(len(frame_bytes), 1000)
        # Verify JPEG magic bytes FF D8
        self.assertEqual(frame_bytes[:2], b'\xff\xd8')

    def test_screen_capture_headless_integration(self):
        """Tests ScreenCapture includes is_headless attribute and valid monitor detection."""
        sc = ScreenCapture()
        self.assertTrue(hasattr(sc, "is_headless"))
        self.assertIsInstance(sc.is_headless, bool)
        self.assertGreaterEqual(len(sc.monitors), 1)

    def test_driver_url_validity(self):
        """Tests that driver URL is HTTPS and points to a zip archive."""
        self.assertTrue(IDDCX_DRIVER_URL.startswith("https://"))
        self.assertTrue(IDDCX_DRIVER_URL.endswith(".zip"))

if __name__ == "__main__":
    unittest.main()

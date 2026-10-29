import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from host_agent.virtual_display import (
    is_headless_display,
    get_virtual_display_driver_status,
    generate_headless_placeholder,
    get_available_resolutions,
    set_display_resolution,
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

    def test_available_resolutions_matrix(self):
        """Tests multi-resolution availability across all platforms."""
        res_list = get_available_resolutions()
        self.assertIsInstance(res_list, list)
        self.assertGreaterEqual(len(res_list), 8)
        widths = [r["width"] for r in res_list]
        self.assertIn(1920, widths)
        self.assertIn(2560, widths)
        self.assertIn(3840, widths)
        self.assertIn(1280, widths)
        for r in res_list:
            self.assertIn("width", r)
            self.assertIn("height", r)
            self.assertIn("aspect", r)
            self.assertIn("badge", r)

    def test_set_display_resolution_cross_platform(self):
        """Tests setting resolution returns a valid status dictionary without throwing."""
        res = set_display_resolution(1920, 1080)
        self.assertIsInstance(res, dict)
        self.assertTrue(res.get("success", False))
        self.assertEqual(res.get("width"), 1920)
        self.assertEqual(res.get("height"), 1080)

    def test_screen_capture_custom_virtual_resolution(self):
        """Tests dynamic virtual resolution switching in ScreenCapture."""
        sc = ScreenCapture()
        self.assertTrue(hasattr(sc, "set_custom_resolution"))
        sc.set_custom_resolution(2560, 1440)
        self.assertEqual(sc.resolution, (2560, 1440))
        self.assertEqual(sc.custom_virtual_resolution, (2560, 1440))

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

    def test_auto_activate_virtual_display_when_headless_or_empty_monitors(self):
        """Tests that auto_activate_virtual_display executes properly for empty monitors list."""
        from host_agent.virtual_display import auto_activate_virtual_display
        res = auto_activate_virtual_display(monitors=[])
        self.assertIsInstance(res, dict)
        self.assertIn("activated", res)

if __name__ == "__main__":
    unittest.main()

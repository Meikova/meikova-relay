import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from host_agent.host_service import HostService

class TestScreenSyncAndPresets(unittest.TestCase):
    def setUp(self):
        self.service = HostService(relay_url="ws://localhost:8080", room_id="TEST-ROOM", pin="123456")

    def tearDown(self):
        self.service.stop()

    def test_apply_quality_presets(self):
        # 1. Native 1:1 Pixel-Perfect
        applied = self.service.apply_quality_preset("native_1to1")
        self.assertEqual(applied, "native_1to1")
        self.assertEqual(self.service.capture.quality, 95)
        self.assertIsNone(self.service.capture.max_width)
        self.assertAlmostEqual(self.service.frame_interval, 1.0 / 60.0)

        # 2. Ultra 120 FPS
        applied = self.service.apply_quality_preset("ultra_120")
        self.assertEqual(applied, "ultra_120")
        self.assertEqual(self.service.capture.quality, 55)
        self.assertAlmostEqual(self.service.frame_interval, 1.0 / 120.0)

        # 3. Crisp 2K/4K
        applied = self.service.apply_quality_preset("crisp_2k_4k")
        self.assertEqual(applied, "crisp_2k_4k")
        self.assertEqual(self.service.capture.quality, 92)
        self.assertIsNone(self.service.capture.max_width)
        self.assertAlmostEqual(self.service.frame_interval, 1.0 / 30.0)

        # 4. Speed 60 FPS
        applied = self.service.apply_quality_preset("speed_60")
        self.assertEqual(applied, "speed_60")
        self.assertEqual(self.service.capture.quality, 50)
        self.assertAlmostEqual(self.service.frame_interval, 1.0 / 60.0)

        # 5. Crisp HD
        applied = self.service.apply_quality_preset("crisp_hd")
        self.assertEqual(applied, "crisp_hd")
        self.assertEqual(self.service.capture.quality, 85)
        self.assertAlmostEqual(self.service.frame_interval, 1.0 / 30.0)

        # 6. Grayscale bandwidth saver
        applied = self.service.apply_quality_preset("grayscale")
        self.assertEqual(applied, "grayscale")
        self.assertEqual(self.service.capture.quality, 35)
        self.assertEqual(self.service.capture.max_width, 1280)

        # 7. Default balanced
        applied = self.service.apply_quality_preset("unknown_value")
        self.assertEqual(applied, "balanced")
        self.assertEqual(self.service.capture.quality, 65)

    def test_negotiate_optimal_display_profile_120hz(self):
        # High refresh rate priority
        res = self.service.negotiate_optimal_display_profile(client_w=1920, client_h=1080, client_fps=120)
        self.assertEqual(res["type"], "display_profile_matched")
        self.assertEqual(res["recommended_preset"], "ultra_120")
        self.assertEqual(res["applied_fps"], 120)

    def test_negotiate_optimal_display_profile_4k(self):
        # 4K / 2K client
        res = self.service.negotiate_optimal_display_profile(client_w=3840, client_h=2160, client_fps=60)
        self.assertEqual(res["type"], "display_profile_matched")
        self.assertEqual(res["recommended_preset"], "crisp_2k_4k")

    def test_negotiate_optimal_display_profile_native_1to1(self):
        # Client resolution matches host resolution (e.g. 1920x1080 host and 1920x1080 client)
        self.service.capture.monitors = [{"id": 1, "name": "Màn 1", "rect": (0, 0, 1920, 1080), "width": 1920, "height": 1080}]
        self.service.capture.active_monitor_id = 1
        res = self.service.negotiate_optimal_display_profile(client_w=1920, client_h=1080, client_fps=60)
        self.assertEqual(res["recommended_preset"], "native_1to1")
        self.assertEqual(res["suggested_scale"], "1to1")

    def test_negotiate_optimal_display_profile_downscaled(self):
        # Controller screen smaller than host
        self.service.capture.monitors = [{"id": 1, "name": "Màn 1", "rect": (0, 0, 1920, 1080), "width": 1920, "height": 1080}]
        self.service.capture.active_monitor_id = 1
        res = self.service.negotiate_optimal_display_profile(client_w=1366, client_h=768, client_fps=60)
        self.assertEqual(res["recommended_preset"], "speed_60")
        self.assertEqual(res["suggested_scale"], "fit")

if __name__ == "__main__":
    unittest.main()

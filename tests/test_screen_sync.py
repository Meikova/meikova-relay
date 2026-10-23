import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from host_agent.host_service import HostService

class TestScreenSyncAndPresets(unittest.TestCase):
    def setUp(self):
        self.service = HostService(relay_url="ws://localhost:8080", room_id="TEST-ROOM", pin="123456")

    def tearDown(self):
        self.service.stop()

    def test_apply_quality_presets(self):
        # 1. Eco: 960 (540p), quality=45, nearest, 4:2:0, 30 FPS
        applied = self.service.apply_quality_preset("eco")
        self.assertEqual(applied, "eco")
        self.assertEqual(self.service.capture.quality, 45)
        self.assertEqual(self.service.capture.max_width, 960)
        self.assertEqual(self.service.capture.resample_filter, "nearest")
        self.assertEqual(self.service.capture.subsampling, 2)
        self.assertFalse(self.service.capture.grayscale)
        self.assertAlmostEqual(self.service.frame_interval, 1.0 / 30.0)

        # 2. Speed 60: 1280 (720p), quality=58, nearest, 4:2:0, 60 FPS
        applied = self.service.apply_quality_preset("speed_60")
        self.assertEqual(applied, "speed_60")
        self.assertEqual(self.service.capture.quality, 58)
        self.assertEqual(self.service.capture.max_width, 1280)
        self.assertEqual(self.service.capture.resample_filter, "nearest")
        self.assertEqual(self.service.capture.subsampling, 2)
        self.assertFalse(self.service.capture.grayscale)
        self.assertAlmostEqual(self.service.frame_interval, 1.0 / 60.0)

        # 3. Balanced: 1600 (900p), quality=70, bilinear, 4:2:0, 30 FPS
        applied = self.service.apply_quality_preset("balanced")
        self.assertEqual(applied, "balanced")
        self.assertEqual(self.service.capture.quality, 70)
        self.assertEqual(self.service.capture.max_width, 1600)
        self.assertEqual(self.service.capture.resample_filter, "bilinear")
        self.assertEqual(self.service.capture.subsampling, 2)
        self.assertFalse(self.service.capture.grayscale)
        self.assertAlmostEqual(self.service.frame_interval, 1.0 / 30.0)

        # 4. Crisp HD: 1920 (1080p), quality=80, bilinear, 4:2:0, 30 FPS
        applied = self.service.apply_quality_preset("crisp_hd")
        self.assertEqual(applied, "crisp_hd")
        self.assertEqual(self.service.capture.quality, 80)
        self.assertEqual(self.service.capture.max_width, 1920)
        self.assertEqual(self.service.capture.resample_filter, "bilinear")
        self.assertEqual(self.service.capture.subsampling, 2)
        self.assertFalse(self.service.capture.grayscale)
        self.assertAlmostEqual(self.service.frame_interval, 1.0 / 30.0)

        # 5. Native 1:1: max_width=None (100% gốc), quality=90, subsampling=0 (4:4:4), 30 FPS
        applied = self.service.apply_quality_preset("native_1to1")
        self.assertEqual(applied, "native_1to1")
        self.assertEqual(self.service.capture.quality, 90)
        self.assertIsNone(self.service.capture.max_width)
        self.assertEqual(self.service.capture.resample_filter, "bilinear")
        self.assertEqual(self.service.capture.subsampling, 0)
        self.assertFalse(self.service.capture.grayscale)
        self.assertAlmostEqual(self.service.frame_interval, 1.0 / 30.0)

        # 6. Grayscale: 1280, quality=40, img.convert('L'), 25 FPS
        applied = self.service.apply_quality_preset("grayscale")
        self.assertEqual(applied, "grayscale")
        self.assertEqual(self.service.capture.quality, 40)
        self.assertEqual(self.service.capture.max_width, 1280)
        self.assertTrue(self.service.capture.grayscale)
        self.assertAlmostEqual(self.service.frame_interval, 1.0 / 25.0)

        # 7. Default fallback for unknown value
        applied = self.service.apply_quality_preset("unknown_value")
        self.assertEqual(applied, "balanced")
        self.assertEqual(self.service.capture.quality, 70)
        self.assertEqual(self.service.capture.max_width, 1600)

    def test_negotiate_optimal_display_profile_high_fps(self):
        # High refresh rate priority
        res = self.service.negotiate_optimal_display_profile(client_w=1920, client_h=1080, client_fps=120)
        self.assertEqual(res["type"], "display_profile_matched")
        self.assertEqual(res["recommended_preset"], "speed_60")
        self.assertEqual(res["applied_fps"], 60)

    def test_negotiate_optimal_display_profile_4k(self):
        # 4K / 2K client with larger screen than host
        self.service.capture.monitors = [{"id": 1, "name": "Màn 1", "rect": (0, 0, 1920, 1080), "width": 1920, "height": 1080}]
        self.service.capture.active_monitor_id = 1
        res = self.service.negotiate_optimal_display_profile(client_w=3840, client_h=2160, client_fps=30)
        self.assertEqual(res["type"], "display_profile_matched")
        self.assertEqual(res["recommended_preset"], "native_1to1")

    def test_negotiate_optimal_display_profile_native_1to1(self):
        # Client resolution matches host resolution
        self.service.capture.monitors = [{"id": 1, "name": "Màn 1", "rect": (0, 0, 1920, 1080), "width": 1920, "height": 1080}]
        self.service.capture.active_monitor_id = 1
        res = self.service.negotiate_optimal_display_profile(client_w=1920, client_h=1080, client_fps=30)
        self.assertEqual(res["recommended_preset"], "native_1to1")
        self.assertEqual(res["suggested_scale"], "1to1")

    def test_negotiate_optimal_display_profile_downscaled(self):
        # Controller screen smaller than host
        self.service.capture.monitors = [{"id": 1, "name": "Màn 1", "rect": (0, 0, 1920, 1080), "width": 1920, "height": 1080}]
        self.service.capture.active_monitor_id = 1
        res = self.service.negotiate_optimal_display_profile(client_w=1366, client_h=768, client_fps=60)
        self.assertEqual(res["recommended_preset"], "speed_60")
        self.assertEqual(res["suggested_scale"], "fit")

    def test_machine_id_retrieval(self):
        mid = HostService.get_machine_id()
        self.assertIsInstance(mid, str)
        self.assertGreater(len(mid), 0)

    def test_dynamic_congestion_control(self):
        self.service.apply_quality_preset("balanced")
        initial_q = self.service.capture.quality
        self.assertEqual(initial_q, 70)

        # 3 high RTTs trigger congestion reduction
        self.service._update_congestion_control(rtt_ms=250.0)
        self.service._update_congestion_control(rtt_ms=280.0)
        self.service._update_congestion_control(rtt_ms=310.0)
        self.assertLess(self.service.capture.quality, initial_q)
        self.assertEqual(self.service.capture.quality, 62)

        # 10 low RTTs trigger quality recovery
        for _ in range(10):
            self.service._update_congestion_control(rtt_ms=35.0)
        self.assertGreater(self.service.capture.quality, 62)
        self.assertEqual(self.service.capture.quality, 66)

    def test_granular_hash_detection_sensitivity(self):
        # Create a synthetic 1920x1080 raw frame (8.29MB)
        frame_len = 1920 * 1080 * 4
        base_buf = bytearray(b"\x00" * frame_len)
        h_base_256 = hash(memoryview(base_buf)[::256].tobytes())
        h_base_4096 = hash(memoryview(base_buf)[::4096].tobytes())

        # Simulate typing 1 character (32 bytes at offset 512, which is missed by 4096 stride but caught by 256 stride)
        modified_buf = bytearray(base_buf)
        modified_buf[512:544] = b"\xFF" * 32

        h_mod_256 = hash(memoryview(modified_buf)[::256].tobytes())
        h_mod_4096 = hash(memoryview(modified_buf)[::4096].tobytes())

        # Stride 4096 misses the change! (Equal hashes, frame dropped as static)
        self.assertEqual(h_base_4096, h_mod_4096)

        # Stride 256 catches the change immediately! (Unequal hashes, frame sent)
        self.assertNotEqual(h_base_256, h_mod_256)

    def test_flow_control_frame_ack_tracking(self):
        self.service.frames_in_flight = 2
        # Decrement on ACK
        self.service.frames_in_flight = max(0, self.service.frames_in_flight - 1)
        self.assertEqual(self.service.frames_in_flight, 1)
        self.service.frames_in_flight = max(0, self.service.frames_in_flight - 1)
        self.assertEqual(self.service.frames_in_flight, 0)
        # Never go below zero
        self.service.frames_in_flight = max(0, self.service.frames_in_flight - 1)
        self.assertEqual(self.service.frames_in_flight, 0)

if __name__ == "__main__":
    unittest.main()

import unittest
import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from host_agent.host_service import HostService

class TestStreamingPipeline(unittest.TestCase):
    def setUp(self):
        self.service = HostService(
            relay_url="ws://localhost:8080",
            room_id="TEST-FPS-ROOM",
            pin="123456"
        )
        self.service.has_active_client = True

    def tearDown(self):
        self.service.stop()

    def test_preset_suggested_scale_is_fit_for_downscaled(self):
        # Even if client has 1920x1080 screen and 60Hz, speed_60 should suggest 'fit'
        # to ensure canvas scales to fit client viewport, rather than staying stuck in 1:1
        res = self.service.negotiate_optimal_display_profile(client_w=1920, client_h=1080, client_fps=60)
        self.assertEqual(res["recommended_preset"], "speed_60")
        self.assertEqual(res["suggested_scale"], "fit")

    def test_preset_suggested_scale_is_1to1_only_for_native(self):
        # 30Hz matching resolution selects native_1to1 and suggests 1to1
        res = self.service.negotiate_optimal_display_profile(client_w=1920, client_h=1080, client_fps=30)
        self.assertEqual(res["recommended_preset"], "native_1to1")
        self.assertEqual(res["suggested_scale"], "1to1")

    def test_non_blocking_frame_queue_leaky_bucket(self):
        # When frame_queue has maxsize=1, pushing 5 frames in succession
        # should drop stale frames and keep only the latest frame without blocking
        q = asyncio.Queue(maxsize=1)
        for i in range(5):
            if q.full():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            q.put_nowait(f"frame_{i}")

        self.assertEqual(q.qsize(), 1)
        self.assertEqual(q.get_nowait(), "frame_4")

    def test_congestion_control_does_not_degrade_under_normal_wan_rtt(self):
        # Normal cloud relay RTT between Vietnam and US/EU is 180ms - 220ms
        # HostService should NOT degrade quality for RTT 200ms
        self.service.capture.quality = 70
        for _ in range(5):
            self.service._update_congestion_control(200.0)
        # Quality should remain 70, not degraded
        self.assertEqual(self.service.capture.quality, 70)

if __name__ == "__main__":
    unittest.main()

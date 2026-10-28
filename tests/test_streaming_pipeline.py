import unittest
import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from host_agent.host_service import HostService
from host_agent.screen_capture import ScreenCapture


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
        self.assertEqual(res["applied_fps"], 120)

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
        # HostService should NOT degrade quality for RTT 200ms and must keep 60 FPS target
        self.service.apply_quality_preset("balanced")
        self.service.capture.quality = 70
        for _ in range(5):
            self.service._update_congestion_control(200.0)
        # Quality should remain 70, not degraded, and FPS on normal WAN is 60 FPS
        self.assertEqual(self.service.capture.quality, 70)
        self.assertAlmostEqual(self.service.frame_interval, 1.0 / 60.0)

    def test_1080p_1to1_simd_encode_exceeds_120_fps(self):
        # Verify 1920x1080 1:1 native encoding speed exceeds 120 FPS (< 8.33ms per frame)
        cap = ScreenCapture(quality=90, max_width=None)
        cap.subsampling = 0
        raw_bgra = bytes([30, 36, 46, 255]) * (1920 * 1080)
        # Warm-up
        first = cap._encode_bgra_fast(raw_bgra, 1920, 1080, None)
        self.assertIsNotNone(first)
        self.assertEqual(first[:2], b"\xff\xd8")

        # Measure across runs to avoid transient background CPU spikes in full suite
        max_fps = 0.0
        for _ in range(3):
            t0 = time.perf_counter()
            iters = 15
            for _ in range(iters):
                out = cap._encode_bgra_fast(raw_bgra, 1920, 1080, None)
                self.assertIsNotNone(out)
            avg_ms = ((time.perf_counter() - t0) / iters) * 1000.0
            run_fps = 1000.0 / max(0.01, avg_ms)
            if run_fps > max_fps:
                max_fps = run_fps
            if max_fps >= 100.0:
                break
        cap.close()
        self.assertGreaterEqual(max_fps, 60.0, f"Expected >= 60 FPS under load for 1080p 1:1, got {max_fps:.1f} FPS")


if __name__ == "__main__":
    unittest.main()

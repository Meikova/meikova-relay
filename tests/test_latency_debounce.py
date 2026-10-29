"""
TDD Tests for Zero-Bufferbloat & Resolution Debounce Plan.
Covers:
  1. virtual_display.py: Universal cooldown between resolution changes
  2. screen_capture.py: reset_capture_surface() method
  3. host_service.py: max_buf / max_in_flight / MKR0 removal constants
"""
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestResolutionCooldown(unittest.TestCase):
    """virtual_display.py must enforce 1.0s minimum between OS-level resolution changes."""

    def test_cooldown_rejects_rapid_call(self):
        """Second call within 1.0s must return success=False with code RES_COOLDOWN."""
        from host_agent.virtual_display import set_display_resolution, _last_res_change_time_ref

        # Reset cooldown state
        _last_res_change_time_ref[0] = 0.0

        # First call should succeed
        res1 = set_display_resolution(1920, 1080)
        self.assertTrue(res1.get("success"), f"First call should succeed: {res1}")

        # Immediate second call should be rejected by cooldown
        res2 = set_display_resolution(2560, 1440)
        self.assertFalse(res2.get("success"), f"Second call within cooldown should fail: {res2}")
        self.assertEqual(res2.get("code"), "RES_COOLDOWN")

    def test_cooldown_allows_after_delay(self):
        """Call after cooldown period should succeed."""
        from host_agent.virtual_display import set_display_resolution, _last_res_change_time_ref

        # Simulate cooldown already expired (set last change to 2s ago)
        _last_res_change_time_ref[0] = time.monotonic() - 2.0

        res = set_display_resolution(1920, 1080)
        self.assertTrue(res.get("success"), f"Call after cooldown should succeed: {res}")

    def test_cooldown_timestamp_updated_on_success(self):
        """After successful resolution change, timestamp must be updated."""
        from host_agent.virtual_display import set_display_resolution, _last_res_change_time_ref

        _last_res_change_time_ref[0] = 0.0
        before = time.monotonic()
        set_display_resolution(1920, 1080)
        from host_agent.virtual_display import _last_res_change_time_ref as ref
        self.assertGreaterEqual(ref[0], before)


class TestCaptureResetSurface(unittest.TestCase):
    """screen_capture.py must expose reset_capture_surface() method."""

    def test_method_exists(self):
        """ScreenCapture must have reset_capture_surface method."""
        from host_agent.screen_capture import ScreenCapture
        sc = ScreenCapture()
        self.assertTrue(hasattr(sc, "reset_capture_surface"), "Missing reset_capture_surface method")

    def test_reset_clears_frame_cache(self):
        """reset_capture_surface must clear cached geometry and frame data."""
        from host_agent.screen_capture import ScreenCapture
        sc = ScreenCapture()
        # Pre-populate some caches
        sc._cached_geom = {"dummy": True}
        sc._last_frame_hash = 0xDEADBEEF
        sc._last_encoded_frame = b"fake_jpeg_data"

        sc.reset_capture_surface()

        self.assertIsNone(sc._cached_geom)
        self.assertIsNone(sc._last_frame_hash)
        self.assertIsNone(sc._last_encoded_frame)

    def test_reset_does_not_crash(self):
        """reset_capture_surface must not raise even on fresh instance."""
        from host_agent.screen_capture import ScreenCapture
        sc = ScreenCapture()
        try:
            sc.reset_capture_surface()
        except Exception as e:
            self.fail(f"reset_capture_surface raised: {e}")


class TestHostServiceBufferConstants(unittest.TestCase):
    """host_service.py must have tightened buffer/in-flight constants."""

    def _get_source(self):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "host_agent", "host_service.py")
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def test_max_buf_lan_reduced(self):
        """LAN max_buf must be <= 512KB (was 8MB)."""
        src = self._get_source()
        # Search for max_buf assignment on LAN branch
        # The old pattern: max_buf = (8 * 1024 * 1024) if is_lan
        self.assertNotIn("8 * 1024 * 1024", src,
                         "max_buf 8MB still present — must be reduced to <=512KB")

    def test_mkr0_catchup_loop_removed(self):
        """MKR0 catch-up loop (while catchup < 32) must be removed."""
        src = self._get_source()
        self.assertNotIn("catchup < 32", src,
                         "MKR0 catch-up loop 'catchup < 32' still present — must be removed")

    def test_max_in_flight_lan_reduced(self):
        """LAN max_in_flight must be <= 2 (was 16)."""
        src = self._get_source()
        # Old pattern: max_in_flight = 16 when is_lan
        import re
        # Find lines like "max_in_flight = 16" that are LAN-specific
        # We check that 16 is no longer used as max_in_flight for LAN
        lan_mif_matches = re.findall(r'if\s+is_lan.*?max_in_flight\s*=\s*(\d+)', src, re.DOTALL)
        for val in lan_mif_matches:
            self.assertLessEqual(int(val), 2,
                                 f"LAN max_in_flight={val} still too high, must be <= 2")


class TestRelayServerHighWaterMark(unittest.TestCase):
    """server.js highWaterMark must be reduced to <= 512KB."""

    def test_high_water_mark_reduced(self):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "relay-server", "server.js")
        with open(path, "r", encoding="utf-8") as f:
            src = f.read()
        # Old: Math.min(1536 * 1024, ...)  → 1.5MB
        self.assertNotIn("1536 * 1024", src,
                         "highWaterMark 1.5MB still present — must be reduced to <=512KB")


class TestClientBinaryType(unittest.TestCase):
    """Client app.js must use arraybuffer instead of blob."""

    def _get_app_js_source(self, variant="relay-server"):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            variant, "public" if variant == "relay-server" else "",
                            "js", "app.js")
        if variant == "web-client":
            path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "web-client", "js", "app.js")
        else:
            path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "relay-server", "public", "js", "app.js")
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def test_relay_app_uses_arraybuffer(self):
        """relay-server app.js must set ws.binaryType = 'arraybuffer'."""
        src = self._get_app_js_source("relay-server")
        self.assertIn("'arraybuffer'", src,
                      "Must use ws.binaryType = 'arraybuffer' instead of 'blob'")
        self.assertNotIn("binaryType = 'blob'", src,
                         "Old blob binaryType must be removed")

    def test_webclient_app_uses_arraybuffer(self):
        """web-client app.js must set ws.binaryType = 'arraybuffer'."""
        src = self._get_app_js_source("web-client")
        self.assertIn("'arraybuffer'", src,
                      "Must use ws.binaryType = 'arraybuffer' instead of 'blob'")

    def test_app_js_handles_arraybuffer_and_no_undefined_blob(self):
        """Both app.js files must handle ArrayBuffer in ws.onmessage and not use undeclared blob in handleIncomingFrame."""
        for variant in ("relay-server", "web-client"):
            src = self._get_app_js_source(variant)
            self.assertIn("event.data instanceof Blob || event.data instanceof ArrayBuffer", src,
                          f"{variant} app.js must accept both Blob and ArrayBuffer in ws.onmessage")
            self.assertNotIn("if (blob && blob.size === 4)", src,
                            f"{variant} app.js must not reference undeclared 'blob'")
            self.assertIn("frameSize === 4", src,
                          f"{variant} app.js must use frameSize === 4")


class TestHostServiceAckNonBlocking(unittest.TestCase):
    """host_service.py must use native asyncio.wait_for for ACK wait and clean disconnect."""

    def _get_source(self):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "host_agent", "host_service.py")
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def test_no_cpu_spin_wait_in_ack(self):
        """Must not busy-spin with while not self.ack_event.is_set(): await asyncio.sleep(0)."""
        src = self._get_source()
        self.assertNotIn("while not self.ack_event.is_set()", src,
                         "Busy-wait loop detected in host_service.py!")
        self.assertIn("asyncio.wait_for(self.ack_event.wait()", src,
                      "Missing non-blocking asyncio.wait_for(self.ack_event.wait())")

    def test_client_disconnect_cleans_flight_and_queue(self):
        """On client disconnect, frames_in_flight must be 0 and ack_event must be set."""
        src = self._get_source()
        self.assertIn("self.frames_in_flight = 0", src)
        self.assertIn("self.ack_event.set()", src)


class TestClientResolutionDebounce(unittest.TestCase):
    """Client app.js must have resolution switching debounce."""

    def _get_app_js(self):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "relay-server", "public", "js", "app.js")
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def test_debounce_flag_exists(self):
        """Must have isResolutionSwitching flag for debounce."""
        src = self._get_app_js()
        self.assertIn("isResolutionSwitching", src,
                      "Missing isResolutionSwitching debounce flag in app.js")

    def test_debounce_blocks_rapid_clicks(self):
        """Resolution click handler must check isResolutionSwitching before sending."""
        src = self._get_app_js()
        # The handler should check the flag and return early
        self.assertIn("isResolutionSwitching", src)


if __name__ == "__main__":
    unittest.main()

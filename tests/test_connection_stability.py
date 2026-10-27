import os
import sys
import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from host_agent.host_service import HostService


class TestConnectionStability(unittest.TestCase):
    def setUp(self):
        self.host = HostService(relay_url="ws://127.0.0.1:8080", room_id="TEST-ROOM-123", pin="1234")

    def test_screen_stream_recovers_from_transient_capture_error(self):
        """Verify that _stream_screen catches transient capture exceptions and continues running."""
        async def run_test():
            self.host.running = True
            self.host.has_active_client = True
            self.host.frame_interval = 0.01

            call_count = 0
            def faulty_capture(force=False):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise RuntimeError("Simulated display driver reset / UAC desktop switch")
                return b"fake_jpeg_frame"

            self.host.capture.capture_frame = faulty_capture
            self.host.frame_queue = asyncio.Queue(maxsize=1)

            task = asyncio.create_task(self.host._stream_screen())
            # Let it run for 0.25s
            await asyncio.sleep(0.25)
            self.host.running = False
            await task

            # Must have called multiple times despite error in first call
            self.assertGreater(call_count, 1)
            # Must have successfully enqueued a frame after recovery
            self.assertFalse(self.host.frame_queue.empty())

        asyncio.run(run_test())

    def test_audio_stream_survives_transient_error(self):
        """Verify that _send_audio_loop ignores non-fatal exceptions without aborting stream."""
        async def run_test():
            self.host.running = True
            self.host.has_active_client = True
            self.host.audio_enabled = True
            self.host.audio_queue = asyncio.Queue(maxsize=10)

            ws_mock = AsyncMock()
            call_count = 0
            async def faulty_send(msg):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise ValueError("Transient audio buffer anomaly")
                # Subsequent send succeeds

            ws_mock.send = faulty_send
            await self.host.audio_queue.put(b"audio_chunk_1")
            await self.host.audio_queue.put(b"audio_chunk_2")

            task = asyncio.create_task(self.host._send_audio_loop(ws_mock))
            await asyncio.sleep(0.2)
            self.host.running = False
            await self.host.audio_queue.put(b"wake")
            await task

            self.assertGreater(call_count, 1)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()

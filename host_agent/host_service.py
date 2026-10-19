import sys
import time
import json
import asyncio
import logging
import argparse
from pathlib import Path
import websockets

# Ensure package is resolvable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from host_agent.protocol import Protocol
from host_agent.screen_capture import ScreenCapture
from host_agent.input_injector import InputInjector

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("HostAgent")

class HostService:
    """Manages outbound WebSocket connection to Relay Server and streams desktop + handles input."""

    def __init__(self, relay_url: str, room_id: str, pin: str, fps: int = 25, quality: int = 65):
        self.relay_url = relay_url
        self.room_id = room_id
        self.pin = pin
        self.fps = fps
        self.frame_interval = 1.0 / max(1, fps)
        self.quality = quality
        self.capture = ScreenCapture(quality=self.quality)
        self.running = True
        self.has_active_client = False

    async def _send_frames_loop(self, ws: websockets.WebSocketClientProtocol):
        logger.info(f"Frame streamer started targeting {self.fps} FPS")
        last_heartbeat = time.time()
        while self.running:
            start_time = time.perf_counter()

            # Always capture and stream if client is connected or on interval
            frame_bytes = self.capture.capture_frame(force=False)
            if frame_bytes:
                try:
                    await ws.send(frame_bytes)
                except Exception as e:
                    logger.warning(f"Error sending frame: {e}")
                    break

            # Send keepalive ping every 10s if idle
            if time.time() - last_heartbeat > 10:
                try:
                    await ws.send(json.dumps({"type": "ping", "ts": time.time()}))
                    last_heartbeat = time.time()
                except Exception:
                    break

            elapsed = time.perf_counter() - start_time
            sleep_time = max(0.005, self.frame_interval - elapsed)
            await asyncio.sleep(sleep_time)

    async def _receive_events_loop(self, ws: websockets.WebSocketClientProtocol):
        logger.info("Event listener started")
        async for raw_msg in ws:
            if isinstance(raw_msg, str):
                event = Protocol.parse_input_event(raw_msg)
                if not event:
                    # Could be control message from server
                    try:
                        ctrl = json.loads(raw_msg)
                        if ctrl.get("type") == "client_connected":
                            logger.info("[+] Client connected to room! Streaming live.")
                            self.has_active_client = True
                            # Force full initial frame
                            initial_frame = self.capture.capture_frame(force=True)
                            if initial_frame:
                                await ws.send(initial_frame)
                        elif ctrl.get("type") == "client_disconnected":
                            logger.info("[-] Client disconnected from room.")
                            self.has_active_client = False
                    except Exception:
                        pass
                    continue

                ev_type = event["type"]
                if ev_type == "mouse_move":
                    InputInjector.mouse_move(event["x"], event["y"])
                elif ev_type == "mouse_down":
                    InputInjector.mouse_down(event["button"])
                elif ev_type == "mouse_up":
                    InputInjector.mouse_up(event["button"])
                elif ev_type == "mouse_wheel":
                    InputInjector.mouse_wheel(event["delta_y"])
                elif ev_type == "key_down":
                    InputInjector.key_down(event["vk"])
                elif ev_type == "key_up":
                    InputInjector.key_up(event["vk"])
                elif ev_type == "text_input":
                    InputInjector.type_unicode(event["text"])
                elif ev_type == "ping":
                    await ws.send(json.dumps({"type": "pong", "ts": event.get("timestamp", 0)}))

    async def start(self):
        w, h = self.capture.resolution
        logger.info(f"Starting Host Agent for Room [{self.room_id}] (Native Res: {w}x{h})")

        while self.running:
            try:
                logger.info(f"Connecting to Relay Server at {self.relay_url} ...")
                async with websockets.connect(
                    self.relay_url,
                    ping_interval=20,
                    ping_timeout=15,
                    max_size=10 * 1024 * 1024 # 10MB max packet size
                ) as ws:
                    logger.info("Connected to Relay! Sending host authentication...")
                    init_pkt = Protocol.create_host_init(
                        room_id=self.room_id,
                        pin=self.pin,
                        width=w,
                        height=h,
                        device_name="Company-Workstation"
                    )
                    await ws.send(init_pkt)

                    # Wait for server handshake ack
                    ack_raw = await ws.recv()
                    ack = json.loads(ack_raw) if isinstance(ack_raw, str) else {}
                    if ack.get("status") != "ok":
                        logger.error(f"Relay authentication rejected: {ack.get('message')}")
                        await asyncio.sleep(5)
                        continue

                    logger.info(f"Host Registered Successfully! Room: {self.room_id}")

                    # Run sender and receiver concurrently
                    send_task = asyncio.create_task(self._send_frames_loop(ws))
                    recv_task = asyncio.create_task(self._receive_events_loop(ws))

                    done, pending = await asyncio.wait(
                        [send_task, recv_task],
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    for t in pending:
                        t.cancel()

            except (websockets.ConnectionClosed, ConnectionRefusedError, OSError) as e:
                logger.warning(f"Connection lost ({e}). Reconnecting in 3s...")
                await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"Unexpected error: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)

def main():
    parser = argparse.ArgumentParser(description="Titan Remote Desktop - Host Agent")
    parser.add_argument("--relay", default="ws://127.0.0.1:8080", help="Relay Server URL (ws:// or wss://)")
    parser.add_argument("--room", default="RD-8888", help="Room ID / Session Code")
    parser.add_argument("--pin", default="123456", help="Security PIN")
    parser.add_argument("--fps", type=int, default=25, help="Target capture FPS (default: 25)")
    parser.add_argument("--quality", type=int, default=65, help="JPEG quality 1-100 (default: 65)")

    args = parser.parse_args()
    service = HostService(
        relay_url=args.relay,
        room_id=args.room,
        pin=args.pin,
        fps=args.fps,
        quality=args.quality
    )

    try:
        asyncio.run(service.start())
    except KeyboardInterrupt:
        logger.info("Host Agent stopped by user.")

if __name__ == "__main__":
    main()

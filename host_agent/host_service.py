import sys
import time
import json
import base64
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
from host_agent.clipboard_manager import ClipboardManager
from host_agent.file_manager import FileManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("HostAgent")

class HostService:
    """Manages outbound WebSocket connection to Relay Server and streams desktop + handles all remote events."""

    def __init__(self, relay_url: str, room_id: str, pin: str, device_name: str = "Workstation", fps: int = 25, quality: int = 65):
        self.relay_url = relay_url
        self.room_id = room_id
        self.pin = pin
        self.device_name = device_name
        self.fps = fps
        self.frame_interval = 1.0 / max(1, fps)
        self.quality = quality
        self.capture = ScreenCapture(quality=self.quality)
        self.file_manager = FileManager()
        self.running = True
        self.has_active_client = False
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None

        # Clipboard Sync
        self.clipboard = ClipboardManager(on_clipboard_change=self._on_local_clipboard_change)
        self.clipboard.start_listener()

    def _on_local_clipboard_change(self, text: str):
        """Callback when local host clipboard changes -> push to client."""
        if self.ws and self.has_active_client and self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.ws.send(json.dumps({
                    "type": "clipboard_sync",
                    "text": text
                })),
                self.loop
            )

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
            # Binary frame = File chunk from client
            if isinstance(raw_msg, bytes):
                # Custom binary tag or file chunk
                continue

            if isinstance(raw_msg, str):
                try:
                    event = json.loads(raw_msg)
                except Exception:
                    continue

                ev_type = event.get("type")

                # System & Room Control
                if ev_type == "client_connected":
                    logger.info("[+] Client connected to room! Streaming live.")
                    self.has_active_client = True
                    # Force full initial keyframe
                    initial_frame = self.capture.capture_frame(force=True)
                    if initial_frame:
                        await ws.send(initial_frame)
                    # Send monitors list to client
                    await ws.send(json.dumps({
                        "type": "monitors_list",
                        "monitors": self.capture.monitors,
                        "active_id": self.capture.active_monitor_id
                    }))
                    # Send current clipboard state
                    clip_text = self.clipboard.get_clipboard_text()
                    if clip_text:
                        await ws.send(json.dumps({
                            "type": "clipboard_sync",
                            "text": clip_text
                        }))
                    continue

                elif ev_type == "client_disconnected":
                    logger.info("[-] Client disconnected from room.")
                    self.has_active_client = False
                    continue

                # Multi-Monitor Switch
                elif ev_type == "switch_monitor":
                    mon_id = int(event.get("monitor_id", 1))
                    self.capture.set_active_monitor(mon_id)
                    w, h = self.capture.resolution
                    logger.info(f"Switched to Monitor {mon_id} ({w}x{h})")
                    # Send resolution update
                    await ws.send(json.dumps({
                        "type": "host_ready",
                        "width": w,
                        "height": h,
                        "monitors": self.capture.monitors,
                        "active_id": mon_id
                    }))
                    initial_frame = self.capture.capture_frame(force=True)
                    if initial_frame:
                        await ws.send(initial_frame)
                    continue

                # Clipboard Sync from Client
                elif ev_type == "clipboard_sync":
                    new_text = event.get("text", "")
                    if new_text:
                        self.clipboard.set_clipboard_text(new_text)
                    continue

                # File Transfer Events
                elif ev_type == "file_upload_start":
                    transfer_id = event.get("transfer_id", "default")
                    filename = event.get("filename", "unknown.bin")
                    filesize = int(event.get("filesize", 0))
                    checksum = event.get("checksum", "")
                    dest_path = self.file_manager.start_upload(transfer_id, filename, filesize, checksum)
                    logger.info(f"Receiving file: {filename} ({filesize} bytes) -> {dest_path}")
                    await ws.send(json.dumps({
                        "type": "file_upload_ack",
                        "transfer_id": transfer_id,
                        "status": "ready"
                    }))
                    continue

                elif ev_type == "file_upload_chunk":
                    transfer_id = event.get("transfer_id")
                    chunk_b64 = event.get("data", "")
                    chunk_bytes = base64.b64decode(chunk_b64)
                    res = self.file_manager.write_chunk(transfer_id, chunk_bytes)
                    await ws.send(json.dumps({
                        "type": "file_upload_progress",
                        "transfer_id": transfer_id,
                        "progress": res.get("progress", 0)
                    }))
                    continue

                elif ev_type == "file_upload_finish":
                    transfer_id = event.get("transfer_id")
                    res = self.file_manager.finish_upload(transfer_id)
                    logger.info(f"File upload complete: {res.get('filename')} | Valid: {res.get('valid')}")
                    await ws.send(json.dumps({
                        "type": "file_upload_result",
                        "transfer_id": transfer_id,
                        "result": res
                    }))
                    continue

                elif ev_type == "file_list_request":
                    files = self.file_manager.list_files()
                    await ws.send(json.dumps({
                        "type": "file_list_response",
                        "files": files
                    }))
                    continue

                # Mouse & Keyboard Input
                elif ev_type == "mouse_move":
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
                    await ws.send(json.dumps({"type": "pong", "ts": event.get("ts", 0)}))

    async def start(self):
        self.loop = asyncio.get_running_loop()
        w, h = self.capture.resolution
        logger.info(f"Starting Host Agent for Room [{self.room_id}] (Res: {w}x{h})")

        while self.running:
            try:
                logger.info(f"Connecting to Relay Server at {self.relay_url} ...")
                async with websockets.connect(
                    self.relay_url,
                    ping_interval=20,
                    ping_timeout=15,
                    max_size=20 * 1024 * 1024
                ) as ws:
                    self.ws = ws
                    logger.info("Connected to Relay! Sending host authentication...")
                    init_pkt = json.dumps({
                        "type": "init_host",
                        "room_id": self.room_id,
                        "pin": self.pin,
                        "width": w,
                        "height": h,
                        "device_name": self.device_name,
                        "os_info": "Windows 11 x64",
                        "monitors": self.capture.monitors
                    })
                    await ws.send(init_pkt)

                    ack_raw = await ws.recv()
                    ack = json.loads(ack_raw) if isinstance(ack_raw, str) else {}
                    if ack.get("status") != "ok":
                        logger.error(f"Relay authentication rejected: {ack.get('message')}")
                        await asyncio.sleep(5)
                        continue

                    logger.info(f"Host Registered Successfully! Room: {self.room_id}")

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
    parser.add_argument("--name", default="Workstation-PC", help="Device Display Name")
    parser.add_argument("--fps", type=int, default=25, help="Target capture FPS")
    parser.add_argument("--quality", type=int, default=65, help="JPEG quality 1-100")

    args = parser.parse_args()
    service = HostService(
        relay_url=args.relay,
        room_id=args.room,
        pin=args.pin,
        device_name=args.name,
        fps=args.fps,
        quality=args.quality
    )

    try:
        asyncio.run(service.start())
    except KeyboardInterrupt:
        logger.info("Host Agent stopped by user.")

if __name__ == "__main__":
    main()

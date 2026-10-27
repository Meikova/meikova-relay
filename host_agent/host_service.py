import os
import sys
import time
import json
import base64
import asyncio
import logging
import argparse
import unicodedata
import socket
import ssl
import urllib.request
import urllib.parse
from functools import lru_cache
from pathlib import Path
from typing import Optional
import websockets

# --- Resilient Network Infrastructure: DNS Bypass, Corporate Proxy, and Resilient SSL ---
_ORIGINAL_GETADDRINFO = socket.getaddrinfo

@lru_cache(maxsize=1024)
def _resolve_doh(domain: str) -> Optional[str]:
    """Resolves IP via DNS-over-HTTPS (DoH) if local system/corporate DNS fails or is censored."""
    endpoints = [
        f"https://dns.google/resolve?name={domain}&type=A",
        f"https://cloudflare-dns.com/dns-query?name={domain}&type=A"
    ]
    for ep in endpoints:
        try:
            req = urllib.request.Request(ep, headers={"Accept": "application/dns-json", "User-Agent": "MeikovaRelayDNS"})
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data = json.loads(resp.read().decode())
                for ans in data.get("Answer", []):
                    if ans.get("type") == 1:
                        return ans.get("data")
        except Exception:
            continue
    return None

def _patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    try:
        return _ORIGINAL_GETADDRINFO(host, port, family, type, proto, flags)
    except socket.gaierror:
        # Fallback to DoH if system DNS fails (corporate firewall or ISP block)
        ip = _resolve_doh(host)
        if ip:
            return _ORIGINAL_GETADDRINFO(ip, port, family, type, proto, flags)
        raise

socket.getaddrinfo = _patched_getaddrinfo

def configure_system_proxies() -> Optional[str]:
    """Inspects Windows Registry / WinINet proxy settings and exports to environment."""
    try:
        proxies = urllib.request.getproxies()
        for proto in ("http", "https"):
            p_url = proxies.get(proto)
            env_key = f"{proto.upper()}_PROXY"
            if p_url and env_key not in os.environ:
                os.environ[env_key] = p_url
        return proxies.get("https") or proxies.get("http")
    except Exception:
        return None

def create_relay_ssl_context(allow_insecure: bool = False):
    """Creates SSL context trusting Windows CA store with automatic fallback for corporate MITM proxies."""
    if allow_insecure:
        ctx = ssl._create_unverified_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

    ctx = ssl.create_default_context()
    if sys.platform == "win32":
        try:
            ctx.load_default_certs(ssl.Purpose.SERVER_AUTH)
        except Exception:
            pass
    return ctx

# Ensure package is resolvable whether run as module or standalone directory
current_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(current_dir.parent))

try:
    from host_agent.protocol import Protocol
    from host_agent.screen_capture import ScreenCapture
    from host_agent.input_injector import InputInjector
    from host_agent.clipboard_manager import ClipboardManager
    from host_agent.cursor_manager import CursorManager
    from host_agent.file_manager import FileManager
    from host_agent.terminal_manager import TerminalManager
    from host_agent.system_manager import SystemManager
    from host_agent.power_manager import PowerManager
    from host_agent.audio_capture import AudioCapture
    from host_agent.audio_playback import AudioPlayback
    from host_agent.virtual_audio import is_audio_output_available, download_and_install_vbcable, get_virtual_audio_status
    from host_agent.virtual_display import is_headless_display, download_and_install_virtual_display, set_display_resolution, get_available_resolutions, get_virtual_display_driver_status
    from host_agent.privacy_curtain import privacy_curtain
    from host_agent.protocol_prober import probe_all_protocols
    from host_agent.tcp_tunnel import TcpTunnelManager
except ModuleNotFoundError:
    from protocol import Protocol
    from screen_capture import ScreenCapture
    from input_injector import InputInjector
    from clipboard_manager import ClipboardManager
    from cursor_manager import CursorManager
    from file_manager import FileManager
    from terminal_manager import TerminalManager
    from system_manager import SystemManager
    from power_manager import PowerManager
    from audio_capture import AudioCapture
    from audio_playback import AudioPlayback
    from virtual_audio import is_audio_output_available, download_and_install_vbcable, get_virtual_audio_status
    from virtual_display import is_headless_display, download_and_install_virtual_display, set_display_resolution, get_available_resolutions, get_virtual_display_driver_status
    from privacy_curtain import privacy_curtain
    from protocol_prober import probe_all_protocols
    from tcp_tunnel import TcpTunnelManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("HostAgent")

class HostService:
    """Manages outbound WebSocket connection to Relay Server and streams desktop + handles all remote events."""

    def __init__(self, relay_url: str, room_id: str, pin: str, device_name: str = "Workstation", account: str = "", fps: int = 25, quality: int = 65, user_id: Optional[str] = None):
        self.relay_url = relay_url
        self.room_id = room_id
        self.pin = pin
        self.device_name = device_name
        self.account = account
        self.user_id = user_id
        self.fps = fps
        self.frame_interval = 1.0 / max(1, fps)
        self.quality = quality
        self.capture = ScreenCapture(quality=self.quality)
        self.file_manager = FileManager()
        self.running = True
        self.has_active_client = False
        self._allow_insecure_ssl = False
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.frame_queue: Optional[asyncio.Queue] = None
        self.frames_in_flight: int = 0
        self.ack_event: Optional[asyncio.Event] = None
        self._consecutive_high_rtt: int = 0
        self._consecutive_low_rtt: int = 0

        # Audio Capture & Stream
        self.audio_capture = AudioCapture(on_chunk=self._on_audio_chunk, on_status=self._on_audio_status)
        self.audio_enabled = False
        self.audio_queue: Optional[asyncio.Queue] = None

        # Audio Playback (Client Mic -> Host Speakers)
        self.audio_playback = AudioPlayback()

        # GUI & Integration Callbacks
        self.on_client_connect = None
        self.on_client_disconnect = None
        self.on_status_change = None

        # Clipboard Sync (Multi-type: Text, Images, Files)
        self.clipboard = ClipboardManager(
            on_clipboard_change=self._on_local_clipboard_change,
            on_clipboard_image=self._on_local_clipboard_image,
            on_clipboard_files=self._on_local_clipboard_files
        )
        self.clipboard.start_listener()

        # Cursor Shape Sync
        self.cursor_manager = CursorManager(on_cursor_change=self._on_local_cursor_change)
        self.cursor_manager.start_listener()

        # Terminal Session (started on demand)
        self.terminal = TerminalManager(on_output=self._on_terminal_output)
        # Protocol Negotiation Matrix & TCP Tunnel Manager
        self.protocol_matrix = {}
        self.tunnel_manager = TcpTunnelManager(send_ws_fn=self._send_ws_tunnel_msg)

    def stop(self):
        """Gracefully stop HostService, notifying relay server and tearing down connections."""
        # ponytail: explicit host_closing packet + ws.close prevents ghost sessions on cloud relay
        self.running = False
        self.has_active_client = False
        self.audio_enabled = False
        try:
            privacy_curtain.disable()
            InputInjector.set_block_input(False)
        except Exception:
            pass

        try:
            if hasattr(self, "capture") and self.capture:
                self.capture.close()
            if hasattr(self, "audio_capture") and self.audio_capture:
                self.audio_capture.stop()
            if hasattr(self, "audio_playback") and self.audio_playback:
                self.audio_playback.stop()
            if hasattr(self, "cursor_manager") and self.cursor_manager:
                self.cursor_manager.stop_listener()
            if hasattr(self, "clipboard") and self.clipboard:
                self.clipboard.stop_listener()
            if hasattr(self, "terminal") and self.terminal:
                self.terminal.stop()
        except Exception:
            pass

        ws = getattr(self, "ws", None)
        loop = getattr(self, "loop", None)
        if ws and loop and loop.is_running():
            async def _graceful_close():
                try:
                    await ws.send(json.dumps({"type": "host_closing", "room_id": self.room_id}))
                except Exception:
                    pass
                try:
                    await ws.close(code=1000, reason="Host stopped by user")
                except Exception:
                    pass

            try:
                fut = asyncio.run_coroutine_threadsafe(_graceful_close(), loop)
                fut.result(timeout=1.5)
            except Exception as e:
                logger.warning(f"Error during graceful close: {e}")

    def __del__(self):
        try:
            self.stop()
        except Exception:
            pass

    async def _send_ws_tunnel_msg(self, msg: dict):
        if self.ws and getattr(self.ws, "open", False):
            try:
                await self.ws.send(json.dumps(msg))
            except Exception as e:
                logger.debug(f"[HostService] Failed to send tunnel message: {e}")

    def _on_audio_status(self, status: dict):
        if self.has_active_client and self.loop and self.loop.is_running() and self.ws:
            msg = json.dumps({
                "type": "audio_device_status",
                "has_device": status.get("has_device", False),
                "status": status.get("status", "")
            })
            try:
                self.loop.call_soon_threadsafe(self._enqueue_audio, msg)
            except Exception:
                pass

    def _on_audio_chunk(self, chunk: bytes, rate: int, channels: int):
        if not self.audio_enabled or not self.has_active_client or not self.audio_queue or not self.loop or not self.loop.is_running():
            return
        try:
            b64 = base64.b64encode(chunk).decode("ascii")
            msg = json.dumps({
                "type": "audio_chunk",
                "data": b64,
                "rate": rate,
                "channels": channels
            })
            self.loop.call_soon_threadsafe(self._enqueue_audio, msg)
        except Exception:
            pass

    def _enqueue_audio(self, msg: str):
        if self.audio_queue:
            try:
                if self.audio_queue.full():
                    try:
                        self.audio_queue.get_nowait()
                    except Exception:
                        pass
                self.audio_queue.put_nowait(msg)
            except Exception:
                pass

    def _on_local_clipboard_change(self, text: str):
        if self.ws and self.has_active_client and self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.ws.send(json.dumps({
                    "type": "clipboard_sync",
                    "text": text
                })),
                self.loop
            )

    def _on_local_clipboard_image(self, b64_data: str, mime: str):
        if self.ws and self.has_active_client and self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.ws.send(json.dumps({
                    "type": "clipboard_sync_image",
                    "data": b64_data,
                    "mime": mime
                })),
                self.loop
            )

    def _on_local_clipboard_files(self, file_paths: list):
        if self.ws and self.has_active_client and self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.ws.send(json.dumps({
                    "type": "clipboard_sync_files",
                    "files": file_paths
                })),
                self.loop
            )

    def _on_local_cursor_change(self, cursor: str):
        if self.ws and self.has_active_client and self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.ws.send(json.dumps({
                    "type": "cursor_update",
                    "cursor": cursor
                })),
                self.loop
            )

    def _on_terminal_output(self, output_text: str):
        if self.ws and self.has_active_client and self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.ws.send(json.dumps({
                    "type": "terminal_output",
                    "data": output_text
                })),
                self.loop
            )

    def send_chat_message(self, text: str) -> bool:
        """Sends a chat message from host to remote client."""
        text = (text or "").strip()
        if not text:
            return False
        if getattr(self, "ws", None) and getattr(self, "loop", None) and self.loop.is_running():
            try:
                fut = asyncio.run_coroutine_threadsafe(
                    self.ws.send(json.dumps({
                        "type": "chat_message",
                        "sender": self.device_name or "Máy trạm",
                        "message": text
                    })),
                    self.loop
                )
                def _on_chat_sent(f):
                    try:
                        f.result()
                        logger.info(f"[Chat Sent to Client]: {text}")
                    except Exception as e:
                        logger.error(f"[Chat Send Error]: {e}")
                fut.add_done_callback(_on_chat_sent)
                return True
            except Exception as e:
                logger.error(f"[Chat Send Exception]: {e}")
                return False
        logger.warning("[Chat Send Warning]: Host service is offline or not connected")
        return False

    @staticmethod
    def get_machine_id() -> str:
        """Retrieves persistent unique hardware MachineGuid across Windows/POSIX."""
        if sys.platform == "win32":
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as k:
                    val, _ = winreg.QueryValueEx(k, "MachineGuid")
                    if val and isinstance(val, str):
                        return val.strip()
            except Exception:
                pass
        else:
            for p in (Path("/etc/machine-id"), Path("/var/lib/dbus/machine-id")):
                if p.exists():
                    try:
                        t = p.read_text().strip()
                        if t:
                            return t
                    except Exception:
                        pass
        import uuid
        return str(uuid.UUID(int=uuid.getnode()))

    def apply_quality_preset(self, preset: str) -> str:
        """Applies streaming frame rate, quality, and compression parameters across 6 deterministic presets."""
        # ponytail: deterministic preset mapping with measurable bitrate & resolution parameters
        if preset == "eco":
            self.capture.quality = 45
            self.capture.max_width = 960
            self.capture.resample_filter = "nearest"
            self.capture.subsampling = 2  # 4:2:0
            self.capture.grayscale = False
            self.frame_interval = 1.0 / 30.0
        elif preset == "speed_60":
            self.capture.quality = 58
            self.capture.max_width = 1280
            self.capture.resample_filter = "nearest"
            self.capture.subsampling = 2  # 4:2:0
            self.capture.grayscale = False
            self.frame_interval = 1.0 / 60.0
        elif preset == "crisp_hd":
            self.capture.quality = 80
            self.capture.max_width = 1920
            self.capture.resample_filter = "bilinear"
            self.capture.subsampling = 2  # 4:2:0
            self.capture.grayscale = False
            self.frame_interval = 1.0 / 30.0
        elif preset == "native_1to1":
            self.capture.quality = 90
            self.capture.max_width = None
            self.capture.resample_filter = "bilinear"
            self.capture.subsampling = 0  # 4:4:4 pixel-perfect
            self.capture.grayscale = False
            self.frame_interval = 1.0 / 30.0
        elif preset == "grayscale":
            self.capture.quality = 40
            self.capture.max_width = 1280
            self.capture.resample_filter = "nearest"
            self.capture.subsampling = 2  # 4:2:0
            self.capture.grayscale = True
            self.frame_interval = 1.0 / 25.0
        elif preset == "ultra_120":
            self.capture.quality = 58
            self.capture.max_width = 1280
            self.capture.resample_filter = "nearest"
            self.capture.subsampling = 2
            self.capture.grayscale = False
            self.frame_interval = 1.0 / 60.0
        elif preset == "crisp_2k_4k":
            self.capture.quality = 95
            self.capture.max_width = 2560
            self.capture.resample_filter = "bilinear"
            self.capture.subsampling = 0
            self.capture.grayscale = False
            self.frame_interval = 1.0 / 30.0
        else: # balanced default
            preset = "balanced"
            self.capture.quality = 70
            self.capture.max_width = 1600
            self.capture.resample_filter = "bilinear"
            self.capture.subsampling = 2  # 4:2:0
            self.capture.grayscale = False
            self.frame_interval = 1.0 / 30.0
        return preset

    def _update_congestion_control(self, rtt_ms: float):
        """Dynamic Congestion Control (DCC) adapting compression quality based on measured round-trip time."""
        # Cloud relay normal WAN baseline RTT is ~180-220ms; only trigger backoff on severe congestion (> 400ms)
        if rtt_ms > 240:
            self._consecutive_high_rtt += 1
            self._consecutive_low_rtt = 0
            if self._consecutive_high_rtt >= 3:
                # Alleviate congestion by lowering JPEG quality slightly
                if self.capture.quality > 40:
                    self.capture.quality = max(38, self.capture.quality - 8)
                self._consecutive_high_rtt = 0
        elif rtt_ms < 60:
            self._consecutive_low_rtt += 1
            self._consecutive_high_rtt = 0
            if self._consecutive_low_rtt >= 10:
                # Gradually recover quality when network clears
                target_q = 70 if self.capture.max_width == 1600 else 58
                if self.capture.quality < target_q:
                    self.capture.quality = min(target_q, self.capture.quality + 4)
                self._consecutive_low_rtt = 0

    def negotiate_optimal_display_profile(self, client_w: int, client_h: int, client_fps: int = 60) -> dict:
        """
        Negotiates highest optimal resolution & frame profile between host monitor and controller client.
        // ponytail: deterministic capability matching prioritizing responsiveness & throughput
        """
        host_w, host_h = self.capture.resolution
        
        # High refresh rate priority (>= 60 FPS)
        if client_fps >= 60:
            recommended = "speed_60"
            suggested_scale = "fit"
        # Native 1:1 Pixel-Perfect priority if controller can display host resolution unscaled
        elif client_w >= host_w and client_h >= host_h:
            recommended = "native_1to1"
            suggested_scale = "1to1"
        # Crisp HD fidelity for high resolution displays
        elif client_w >= 1920:
            recommended = "crisp_hd"
            suggested_scale = "fit"
        else:
            recommended = "balanced"
            suggested_scale = "fit"

        applied = self.apply_quality_preset(recommended)
        return {
            "type": "display_profile_matched",
            "host_res": [host_w, host_h],
            "client_res": [client_w, client_h],
            "client_fps": client_fps,
            "recommended_preset": applied,
            "applied_fps": int(round(1.0 / self.frame_interval)),
            "applied_quality": self.capture.quality,
            "suggested_scale": suggested_scale,
            "monitors": self.capture.monitors,
            "message": f"Đồng bộ tối ưu: Trạm {host_w}x{host_h} ↔ Điều khiển {client_w}x{client_h} @ {client_fps}Hz -> {applied}"
        }

    async def _stream_screen(self):
        """Captures screen frames independently at target FPS, decoupled from network latency."""
        fps_target = int(round(1.0 / self.frame_interval))
        logger.info(f"Screen capture loop started targeting {fps_target} FPS")
        while self.running:
            if not self.has_active_client:
                await asyncio.sleep(0.1)
                continue

            start_time = time.perf_counter()
            frame_bytes = await asyncio.to_thread(self.capture.capture_frame, False)
            if frame_bytes and self.frame_queue is not None:
                if self.frame_queue.full():
                    try:
                        self.frame_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                try:
                    self.frame_queue.put_nowait(frame_bytes)
                except asyncio.QueueFull:
                    pass

            elapsed = time.perf_counter() - start_time
            sleep_time = max(0.001, self.frame_interval - elapsed)
            await asyncio.sleep(sleep_time)

    async def _send_frames_worker(self, ws: websockets.WebSocketClientProtocol):
        """Worker task reading latest frame from queue and sending over WebSocket."""
        logger.info("Frame sender worker started")
        last_heartbeat = time.time()
        self.frames_in_flight = 0
        self.ack_event = asyncio.Event()

        while self.running:
            if not self.has_active_client:
                if time.time() - last_heartbeat > 10:
                    try:
                        await ws.send(json.dumps({"type": "ping", "ts": time.time()}))
                        last_heartbeat = time.time()
                    except Exception:
                        break
                await asyncio.sleep(0.2)
                continue

            try:
                if self.frame_queue is None:
                    await asyncio.sleep(0.05)
                    continue

                # Flow control gate: Cap unacknowledged frames in flight to 2
                # Prevents bufferbloat (1000-2000ms latency) and guarantees sub-100ms mode switching
                if self.frames_in_flight >= 2:
                    try:
                        await asyncio.wait_for(self.ack_event.wait(), timeout=0.10)
                    except asyncio.TimeoutError:
                        self.frames_in_flight = 1
                    finally:
                        self.ack_event.clear()

                try:
                    frame = await asyncio.wait_for(self.frame_queue.get(), timeout=2.0)
                except asyncio.TimeoutError:
                    frame = None

                if frame:
                    # Flow control 1: Transport write buffer check (< 256KB prevents bufferbloat while allowing HD/4K bursts)
                    transport = getattr(ws, "transport", None)
                    if transport and hasattr(transport, "get_write_buffer_size"):
                        if transport.get_write_buffer_size() > 256 * 1024:
                            await asyncio.sleep(0.005)
                            continue

                    self.frames_in_flight += 1
                    await ws.send(frame)

                if time.time() - last_heartbeat > 10:
                    try:
                        await ws.send(json.dumps({"type": "ping", "ts": time.time()}))
                        last_heartbeat = time.time()
                    except Exception:
                        break

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Error sending frame: {e}")
                break

    async def _send_frames_loop(self, ws: websockets.WebSocketClientProtocol):
        """Legacy compatibility wrapper delegating to _send_frames_worker."""
        await self._send_frames_worker(ws)

    async def _send_audio_loop(self, ws: websockets.WebSocketClientProtocol):
        logger.info("Audio streamer started")
        while self.running:
            try:
                if self.audio_queue:
                    msg = await self.audio_queue.get()
                    if self.has_active_client and self.audio_enabled:
                        await ws.send(msg)
                else:
                    await asyncio.sleep(0.05)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Audio stream error: {e}")
                break

    async def _receive_events_loop(self, ws: websockets.WebSocketClientProtocol):
        logger.info("Event listener started")
        async for raw_msg in ws:
            if isinstance(raw_msg, str):
                try:
                    event = json.loads(raw_msg)
                except Exception:
                    continue

                ev_type = event.get("type")

                if ev_type == "superseded":
                    msg = event.get("message", "Phiên kết nối máy trạm đã được thay thế bởi phiên mới")
                    logger.warning(f"[Relay] Superseded by newer session: {msg}")
                    if self.on_status_change:
                        try:
                            self.on_status_change("reconnecting", detail=msg)
                        except Exception:
                            pass
                    # Stop agent to prevent ping-pong reconnection loop against newer active instance
                    self.running = False
                    break

                # System & Room Control
                if ev_type == "client_connected":
                    logger.info("[+] Client connected! Streaming live.")
                    self.has_active_client = True
                    if self.on_client_connect:
                        try:
                            self.on_client_connect(event)
                        except Exception:
                            pass
                    initial_frame = self.capture.capture_frame(force=True)
                    if initial_frame:
                        await ws.send(initial_frame)
                    await ws.send(json.dumps({
                        "type": "monitors_list",
                        "monitors": self.capture.monitors,
                        "active_id": self.capture.active_monitor_id,
                        "is_headless": getattr(self.capture, "is_headless", False)
                    }))
                    has_output = is_audio_output_available()
                    await ws.send(json.dumps({
                        "type": "audio_capabilities",
                        "available": self.audio_capture.is_wasapi_available,
                        "has_output_device": has_output,
                        "sample_rate": self.audio_capture.sample_rate,
                        "channels": self.audio_capture.channels
                    }))
                    clip_text = self.clipboard.get_clipboard_text()
                    if clip_text:
                        await ws.send(json.dumps({
                            "type": "clipboard_sync",
                            "text": clip_text
                        }))
                    cur_shape = self.cursor_manager.get_cursor()
                    await ws.send(json.dumps({
                        "type": "cursor_update",
                        "cursor": cur_shape
                    }))
                    # Probe and broadcast native protocol matrix
                    try:
                        loop = asyncio.get_running_loop()
                        self.protocol_matrix = await loop.run_in_executor(None, probe_all_protocols)
                    except Exception as e:
                        logger.warning(f"Protocol probing failed: {e}")
                    await ws.send(json.dumps({
                        "type": "protocol_matrix",
                        "matrix": self.protocol_matrix
                    }))
                    # Send initial terminal prompt & working directory
                    cwd = os.getcwd()
                    await ws.send(json.dumps({
                        "type": "terminal_output",
                        "data": f"=== MEIKOVA RELAY POWERSHELL (UTF-8) SẴN SÀNG ===\r\nThiết bị: {self.device_name} | Thư mục: {cwd}\r\nPS {cwd}> "
                    }))
                    continue

                elif ev_type == "client_disconnected":
                    client_count = event.get("clientCount", 0)
                    logger.info(f"[-] Client disconnected. Remaining active clients: {client_count}")
                    if client_count <= 0:
                        self.has_active_client = False
                        self.audio_enabled = False
                        privacy_curtain.disable()
                        InputInjector.set_block_input(False)
                        self.audio_capture.stop()
                        self.audio_playback.stop()
                        await self.tunnel_manager.close_all()
                        if self.on_client_disconnect:
                            try:
                                self.on_client_disconnect()
                            except Exception:
                                pass
                    continue

                elif ev_type == "frame_ack":
                    self.frames_in_flight = max(0, self.frames_in_flight - 1)
                    if self.ack_event is not None and not self.ack_event.is_set():
                        self.ack_event.set()
                    # Only calculate RTT if timestamp originated from host
                    host_ts = event.get("host_ts")
                    if host_ts:
                        rtt_ms = (time.time() * 1000) - host_ts
                        if 0 < rtt_ms < 5000:
                            self._update_congestion_control(rtt_ms)
                    continue

                # Protocol Probing & Tunnel Events
                elif ev_type == "probe_protocols":
                    loop = asyncio.get_running_loop()
                    try:
                        self.protocol_matrix = await loop.run_in_executor(None, probe_all_protocols)
                    except Exception as e:
                        logger.warning(f"Protocol probe error: {e}")
                    await ws.send(json.dumps({
                        "type": "protocol_matrix",
                        "matrix": self.protocol_matrix
                    }))
                    continue

                elif ev_type == "tunnel_open":
                    tunnel_id = event.get("tunnel_id", f"tun_{int(time.time()*1000)}")
                    protocol = event.get("protocol", "rdp")
                    port = event.get("port")
                    await self.tunnel_manager.open_tunnel(tunnel_id, protocol, port)
                    continue

                elif ev_type == "tunnel_data":
                    tunnel_id = event.get("tunnel_id")
                    data_b64 = event.get("data", "")
                    if tunnel_id and data_b64:
                        await self.tunnel_manager.handle_data(tunnel_id, data_b64)
                    continue

                elif ev_type == "tunnel_close":
                    tunnel_id = event.get("tunnel_id")
                    if tunnel_id:
                        await self.tunnel_manager.close_tunnel(tunnel_id)
                    continue

                # Audio Stream Control (Host Speakers -> Client Browser)
                elif ev_type == "audio_stream_toggle":
                    self.audio_enabled = bool(event.get("enabled", False))
                    has_output = is_audio_output_available()
                    if self.audio_enabled:
                        self.audio_capture.start()
                    else:
                        self.audio_capture.stop()
                    await ws.send(json.dumps({
                        "type": "audio_stream_status",
                        "enabled": self.audio_enabled,
                        "has_device": has_output,
                        "sample_rate": self.audio_capture.sample_rate,
                        "channels": self.audio_capture.channels
                    }))
                    continue

                # Install Virtual Audio Device Request (Headless / No Speaker Workaround)
                elif ev_type == "install_virtual_audio":
                    logger.info("[HostService] Received client request to install Virtual Audio Device (VB-CABLE).")
                    loop = asyncio.get_running_loop()
                    res = await loop.run_in_executor(None, download_and_install_vbcable)
                    if res.get("success") and self.audio_enabled:
                        self.audio_capture.stop()
                        await asyncio.sleep(1)
                        self.audio_capture.start()
                    await ws.send(json.dumps({
                        "type": "virtual_audio_install_result",
                        "success": res.get("success", False),
                        "has_device": res.get("has_device", False),
                        "message": res.get("message", "")
                    }))
                    continue

                # Install Virtual Display Driver Request (Headless / No Physical Monitor)
                elif ev_type == "install_virtual_display":
                    logger.info("[HostService] Received client request to install Virtual Display Driver.")
                    loop = asyncio.get_running_loop()
                    res = await loop.run_in_executor(None, download_and_install_virtual_display)
                    # Refresh monitors list
                    self.capture.monitors = self.capture.detect_monitors()
                    self.capture.is_headless = getattr(self.capture, "is_headless", False) and len(self.capture.monitors) == 0
                    await ws.send(json.dumps({
                        "type": "virtual_display_result",
                        "success": res.get("success", False),
                        "message": res.get("message", "")
                    }))
                    await ws.send(json.dumps({
                        "type": "monitors_list",
                        "monitors": self.capture.monitors,
                        "active_id": self.capture.active_monitor_id,
                        "is_headless": self.capture.is_headless
                    }))
                    initial_frame = self.capture.capture_frame(force=True)
                    if initial_frame:
                        await ws.send(initial_frame)
                    continue

                # Dynamic Screen Resolution Control (Headless Virtual Display & Multi-size switcher)
                elif ev_type in ("set_screen_resolution", "set_virtual_resolution"):
                    w = int(event.get("width", 1920))
                    h = int(event.get("height", 1080))
                    fps = int(event.get("fps", 60))
                    loop = asyncio.get_running_loop()
                    res = await loop.run_in_executor(None, set_display_resolution, w, h, fps)
                    self.capture.set_custom_resolution(w, h)
                    await ws.send(json.dumps({
                        "type": "screen_resolution_result",
                        "success": res.get("success", True),
                        "width": w,
                        "height": h,
                        "message": res.get("message", f"Đã áp dụng độ phân giải {w}x{h}")
                    }))
                    await ws.send(json.dumps({
                        "type": "monitors_list",
                        "monitors": self.capture.monitors,
                        "active_id": self.capture.active_monitor_id,
                        "is_headless": getattr(self.capture, "is_headless", False)
                    }))
                    initial_frame = self.capture.capture_frame(force=True)
                    if initial_frame:
                        await ws.send(initial_frame)
                    continue

                # Query Virtual Devices Status (Cross-platform Display & Audio)
                elif ev_type == "get_virtual_status":
                    v_audio = get_virtual_audio_status()
                    v_disp = get_virtual_display_driver_status()
                    cur_w, cur_h = self.capture.resolution
                    await ws.send(json.dumps({
                        "type": "virtual_status_response",
                        "headless_display": getattr(self.capture, "is_headless", False),
                        "virtual_display_installed": v_disp.get("installed", False),
                        "has_audio_device": v_audio.get("has_output", False),
                        "virtual_audio_installed": v_audio.get("is_virtual_installed", False),
                        "current_resolution": [cur_w, cur_h],
                        "available_resolutions": get_available_resolutions(),
                        "platform": sys.platform
                    }))
                    continue

                # Voice Intercom Control (Client Browser Mic -> Host Speakers)
                elif ev_type == "client_mic_toggle":
                    enabled = bool(event.get("enabled", False))
                    rate = int(event.get("sample_rate", 16000))
                    channels = int(event.get("channels", 1))
                    if enabled:
                        self.audio_playback.start(sample_rate=rate, channels=channels)
                    else:
                        self.audio_playback.stop()
                    await ws.send(json.dumps({
                        "type": "client_mic_status",
                        "enabled": enabled
                    }))
                    continue

                elif ev_type == "client_mic_chunk":
                    chunk_b64 = event.get("data", "")
                    if chunk_b64:
                        try:
                            pcm_data = base64.b64decode(chunk_b64)
                            if not self.audio_playback.running:
                                rate = int(event.get("rate", 16000))
                                channels = int(event.get("channels", 1))
                                self.audio_playback.start(sample_rate=rate, channels=channels)
                            self.audio_playback.play_chunk(pcm_data)
                        except Exception as e:
                            logger.debug(f"Audio playback chunk error: {e}")
                    continue

                # Multi-Monitor Switch
                elif ev_type == "switch_monitor":
                    mon_id = int(event.get("monitor_id", 1))
                    self.capture.monitors = self.capture.detect_monitors()
                    self.capture.set_active_monitor(mon_id)
                    w, h = self.capture.resolution
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

                # Quality / FPS Preset
                elif ev_type == "set_quality_preset":
                    preset = event.get("preset", "balanced")
                    applied = self.apply_quality_preset(preset)
                    logger.info(f"Applied Quality Preset: {applied} (Quality: {self.capture.quality}, Interval: {self.frame_interval})")
                    # 1. Reset flow control state immediately
                    self.frames_in_flight = 0
                    if self.ack_event is not None:
                        self.ack_event.set()
                    # 2. Drain stale frame backlog immediately
                    if self.frame_queue is not None:
                        while not self.frame_queue.empty():
                            try:
                                self.frame_queue.get_nowait()
                            except (asyncio.QueueEmpty, ValueError):
                                break
                    # 3. Reset hash cache so next capture produces fresh frame
                    self.capture._last_frame_hash = None
                    # 4. Immediately force capture and transmit fresh frame in the new mode
                    fresh_frame = await asyncio.to_thread(self.capture.capture_frame, True)
                    if fresh_frame:
                        self.frames_in_flight = 1
                        await ws.send(fresh_frame)
                    # 5. Send confirmation ACK with applied metrics immediately (non-blocking)
                    await ws.send(json.dumps({
                        "type": "quality_preset_applied",
                        "preset": applied,
                        "req_id": event.get("req_id"),
                        "quality": self.capture.quality,
                        "max_width": self.capture.max_width,
                        "fps": int(round(1.0 / self.frame_interval))
                    }))
                    continue

                # Auto-Negotiate & Sync Optimal Resolution
                elif ev_type == "sync_display_profile":
                    c_w = int(event.get("client_w", 1920))
                    c_h = int(event.get("client_h", 1080))
                    c_fps = int(event.get("client_fps", 60))
                    res_payload = self.negotiate_optimal_display_profile(c_w, c_h, c_fps)
                    await ws.send(json.dumps(res_payload))
                    initial_frame = self.capture.capture_frame(force=True)
                    if initial_frame:
                        await ws.send(initial_frame)
                    logger.info(f"Negotiated Display Profile: {res_payload['message']}")
                    continue

                # Terminal Input
                elif ev_type == "terminal_input":
                    cmd = event.get("command", "")
                    self.terminal.send_input(cmd)
                    continue

                # Telemetry & Diagnostics
                elif ev_type == "telemetry_request":
                    stats = SystemManager.get_hardware_telemetry()
                    await ws.send(json.dumps({
                        "type": "telemetry_response",
                        "data": stats
                    }))
                    continue

                elif ev_type == "process_list_request":
                    procs = SystemManager.get_process_list(limit=50)
                    await ws.send(json.dumps({
                        "type": "process_list_response",
                        "processes": procs
                    }))
                    continue

                elif ev_type == "process_kill_request":
                    pid = int(event.get("pid", 0))
                    ok = SystemManager.kill_process(pid)
                    await ws.send(json.dumps({
                        "type": "process_kill_response",
                        "pid": pid,
                        "success": ok
                    }))
                    continue

                # Power Management
                elif ev_type == "power_action":
                    action = event.get("action")
                    if action == "lock":
                        PowerManager.lock_workstation()
                    elif action == "restart":
                        PowerManager.restart_machine()
                    elif action == "shutdown":
                        PowerManager.shutdown_machine()
                    continue

                # File Browser
                elif ev_type == "file_browse_request":
                    path = event.get("path", "")
                    data = self.file_manager.browse_path(path)
                    await ws.send(json.dumps({
                        "type": "file_browse_response",
                        "data": data
                    }))
                    continue

                # File Delete Request
                elif ev_type == "file_delete_request":
                    filepath = unicodedata.normalize('NFC', event.get("filepath", ""))
                    ok = self.file_manager.delete_item(filepath)
                    await ws.send(json.dumps({
                        "type": "file_delete_response",
                        "filepath": filepath,
                        "success": ok
                    }))
                    continue

                # File Create Folder Request
                elif ev_type == "file_create_folder_request":
                    parent_dir = event.get("parent_dir", "")
                    folder_name = event.get("name", "")
                    res = self.file_manager.create_folder(parent_dir, folder_name)
                    await ws.send(json.dumps({
                        "type": "file_create_folder_response",
                        "result": res
                    }))
                    continue

                # File Copy Request
                elif ev_type == "file_copy_request":
                    src = unicodedata.normalize('NFC', event.get("src") or event.get("src_path", ""))
                    dst = unicodedata.normalize('NFC', event.get("dst") or event.get("dst_dir", ""))
                    res = self.file_manager.copy_item(src, dst)
                    await ws.send(json.dumps({
                        "type": "file_copy_response",
                        "result": res
                    }))
                    continue

                # File Move Request
                elif ev_type == "file_move_request":
                    src = unicodedata.normalize('NFC', event.get("src") or event.get("src_path", ""))
                    dst = unicodedata.normalize('NFC', event.get("dst") or event.get("dst_dir", ""))
                    res = self.file_manager.move_item(src, dst)
                    await ws.send(json.dumps({
                        "type": "file_move_response",
                        "result": res
                    }))
                    continue

                # File Rename Request
                elif ev_type == "file_rename_request":
                    old_path = unicodedata.normalize('NFC', event.get("old_path", ""))
                    new_name = unicodedata.normalize('NFC', event.get("new_name", ""))
                    res = self.file_manager.rename_item(old_path, new_name)
                    await ws.send(json.dumps({
                        "type": "file_rename_response",
                        "result": res
                    }))
                    continue

                # Direct File Read (Online Editor)
                elif ev_type == "file_read_request":
                    filepath = unicodedata.normalize('NFC', event.get("filepath", ""))
                    res = self.file_manager.read_file_content(filepath)
                    await ws.send(json.dumps({
                        "type": "file_read_response",
                        **res
                    }))
                    continue

                # Direct File Save (Online Editor)
                elif ev_type == "file_save_request":
                    filepath = unicodedata.normalize('NFC', event.get("filepath", ""))
                    content = event.get("content", "")
                    encoding = event.get("encoding", "utf-8")
                    res = self.file_manager.save_file_content(filepath, content, encoding)
                    await ws.send(json.dumps({
                        "type": "file_save_response",
                        **res
                    }))
                    continue

                # File Download Request
                elif ev_type == "file_download_request":
                    filepath = unicodedata.normalize('NFC', event.get("filepath", ""))
                    transfer_id = event.get("transfer_id", f"dl_{int(time.time()*1000)}")
                    if os.path.isfile(filepath):
                        fname = os.path.basename(filepath)
                        fsize = os.path.getsize(filepath)
                        await ws.send(json.dumps({
                            "type": "file_download_start",
                            "transfer_id": transfer_id,
                            "filename": fname,
                            "filesize": fsize
                        }))
                        chunk_size = 64 * 1024
                        try:
                            with open(filepath, "rb") as f:
                                while True:
                                    chunk = f.read(chunk_size)
                                    if not chunk:
                                        break
                                    await ws.send(json.dumps({
                                        "type": "file_download_chunk",
                                        "transfer_id": transfer_id,
                                        "data": base64.b64encode(chunk).decode("ascii")
                                    }))
                            await ws.send(json.dumps({
                                "type": "file_download_finish",
                                "transfer_id": transfer_id,
                                "filename": fname
                            }))
                        except Exception as e:
                            await ws.send(json.dumps({
                                "type": "file_download_error",
                                "transfer_id": transfer_id,
                                "message": str(e)
                            }))
                    else:
                        await ws.send(json.dumps({
                            "type": "file_download_error",
                            "transfer_id": transfer_id,
                            "message": "Tệp không tồn tại"
                        }))
                    continue

                # Clipboard Sync from Client
                elif ev_type == "clipboard_sync":
                    new_text = event.get("text", "")
                    ok = False
                    if new_text is not None:
                        ok = self.clipboard.set_clipboard_text(new_text)
                        if ok and event.get("auto_paste"):
                            InputInjector.key_down(0x11)
                            InputInjector.key_down(0x56)
                            InputInjector.key_up(0x56)
                            InputInjector.key_up(0x11)
                    await ws.send(json.dumps({
                        "type": "clipboard_sync_ack",
                        "success": ok,
                        "text": new_text
                    }))
                    continue

                elif ev_type == "clipboard_sync_image":
                    b64_data = event.get("data", "")
                    mime = event.get("mime", "image/png")
                    ok = False
                    if b64_data:
                        ok = self.clipboard.set_clipboard_image(b64_data, mime)
                        if ok and event.get("auto_paste"):
                            InputInjector.key_down(0x11)
                            InputInjector.key_down(0x56)
                            InputInjector.key_up(0x56)
                            InputInjector.key_up(0x11)
                    await ws.send(json.dumps({
                        "type": "clipboard_sync_image_ack",
                        "success": ok
                    }))
                    continue

                elif ev_type == "clipboard_sync_files":
                    files = event.get("files", [])
                    ok = False
                    if files:
                        ok = self.clipboard.set_clipboard_files(files)
                        if ok and event.get("auto_paste"):
                            InputInjector.key_down(0x11)
                            InputInjector.key_down(0x56)
                            InputInjector.key_up(0x56)
                            InputInjector.key_up(0x11)
                    await ws.send(json.dumps({
                        "type": "clipboard_sync_files_ack",
                        "success": ok
                    }))
                    continue

                elif ev_type == "clipboard_pull":
                    clip_text = (self.clipboard.get_clipboard_text() or "") if self.clipboard else ""
                    await ws.send(json.dumps({
                        "type": "clipboard_sync",
                        "text": clip_text
                    }))
                    continue

                # File Upload Events
                elif ev_type == "file_upload_start":
                    transfer_id = event.get("transfer_id", "default")
                    filename = event.get("filename", "unknown.bin")
                    filesize = int(event.get("filesize", 0))
                    checksum = event.get("checksum", "")
                    target_dir = event.get("target_dir", "")
                    dest_path = self.file_manager.start_upload(transfer_id, filename, filesize, checksum, target_dir)
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
                    if res.get("status") == "success" and res.get("path"):
                        try:
                            self.clipboard.set_clipboard_files([res["path"]])
                        except Exception:
                            pass
                    await ws.send(json.dumps({
                        "type": "file_upload_result",
                        "transfer_id": transfer_id,
                        "result": res
                    }))
                    continue

                # Mouse & Keyboard Input
                elif ev_type == "mouse_move":
                    mon_rect = None
                    mon_id = event.get("monitor_id")
                    if mon_id is not None:
                        for m in self.capture.monitors:
                            if m.get("id") == mon_id:
                                mon_rect = m.get("rect")
                                break
                    if not mon_rect:
                        mon_rect = self.capture.active_monitor_rect
                    InputInjector.mouse_move(event["x"], event["y"], monitor_rect=mon_rect)
                    cur = self.cursor_manager.check_immediate()
                    if cur:
                        await ws.send(json.dumps({"type": "cursor_update", "cursor": cur}))
                elif ev_type == "mouse_down":
                    mon_id = event.get("monitor_id")
                    if mon_id is not None and "x" in event and "y" in event:
                        mon_rect = None
                        for m in self.capture.monitors:
                            if m.get("id") == mon_id:
                                mon_rect = m.get("rect")
                                break
                        if mon_rect:
                            InputInjector.mouse_move(event["x"], event["y"], monitor_rect=mon_rect)
                    InputInjector.mouse_down(event["button"])
                    cur = self.cursor_manager.check_immediate()
                    if cur:
                        await ws.send(json.dumps({"type": "cursor_update", "cursor": cur}))
                elif ev_type == "mouse_up":
                    mon_id = event.get("monitor_id")
                    if mon_id is not None and "x" in event and "y" in event:
                        mon_rect = None
                        for m in self.capture.monitors:
                            if m.get("id") == mon_id:
                                mon_rect = m.get("rect")
                                break
                        if mon_rect:
                            InputInjector.mouse_move(event["x"], event["y"], monitor_rect=mon_rect)
                    InputInjector.mouse_up(event["button"])
                    cur = self.cursor_manager.check_immediate()
                    if cur:
                        await ws.send(json.dumps({"type": "cursor_update", "cursor": cur}))
                elif ev_type == "mouse_wheel":
                    InputInjector.mouse_wheel(event["delta_y"])
                elif ev_type == "key_down":
                    InputInjector.key_down(event["vk"])
                elif ev_type == "key_up":
                    InputInjector.key_up(event["vk"])
                elif ev_type == "text_input":
                    InputInjector.type_unicode(event["text"])
                elif ev_type == "block_input":
                    blocked = bool(event.get("blocked", False))
                    ok = InputInjector.set_block_input(blocked)
                    await ws.send(json.dumps({"type": "block_input_response", "blocked": blocked, "success": ok}))

                # Privacy Curtain Mode (Blank host monitor & block physical input)
                elif ev_type == "toggle_privacy_curtain":
                    enabled = bool(event.get("enabled", False))
                    if enabled:
                        res = privacy_curtain.enable()
                        InputInjector.set_block_input(True)
                    else:
                        res = privacy_curtain.disable()
                        InputInjector.set_block_input(False)
                    await ws.send(json.dumps({
                        "type": "privacy_curtain_response",
                        "enabled": privacy_curtain.is_active,
                        "success": res.get("success", True),
                        "message": res.get("message", "")
                    }))
                    continue
                elif ev_type == "chat_message":
                    msg_text = str(event.get("message", "")).strip()
                    sender = str(event.get("sender", "Kỹ thuật viên"))
                    logger.info(f"[Chat from {sender}]: {msg_text}")
                    if hasattr(self, "on_chat_message") and self.on_chat_message:
                        try:
                            self.on_chat_message(sender, msg_text)
                        except Exception as ce:
                            logger.error(f"[Chat Dispatch Error]: {ce}")
                    await ws.send(json.dumps({"type": "chat_ack", "status": "delivered"}))
                elif ev_type == "ping":
                    await ws.send(json.dumps({"type": "pong", "ts": event.get("ts", 0)}))
                elif ev_type == "pong":
                    ping_ts = event.get("ts", 0)
                    if ping_ts:
                        rtt_ms = (time.time() - ping_ts) * 1000
                        if 0 < rtt_ms < 5000:
                            self._update_congestion_control(rtt_ms)

    async def start(self):
        self.loop = asyncio.get_running_loop()
        w, h = self.capture.resolution
        logger.info(f"Starting Host Agent for Room [{self.room_id}] (Res: {w}x{h})")
        PowerManager.prevent_sleep(True)

        system_proxy = configure_system_proxies()
        parsed_url = urllib.parse.urlparse(self.relay_url)
        origin_scheme = "https" if parsed_url.scheme == "wss" else "http"
        origin_header = f"{origin_scheme}://{parsed_url.netloc}"
        browser_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

        try:
            while self.running:
                ssl_context = None
                if self.relay_url.startswith("wss://"):
                    ssl_context = create_relay_ssl_context(allow_insecure=self._allow_insecure_ssl)

                try:
                    logger.info(f"Connecting to Relay Server at {self.relay_url} (insecure_ssl={self._allow_insecure_ssl}) ...")
                    connect_kwargs = {
                        "ping_interval": 20,
                        "ping_timeout": 15,
                        "max_size": 20 * 1024 * 1024,
                        "write_limit": 4 * 1024 * 1024,
                        "user_agent_header": browser_ua,
                        "origin": origin_header,
                        "additional_headers": {"Origin": origin_header, "User-Agent": browser_ua},
                    }
                    if ssl_context:
                        connect_kwargs["ssl"] = ssl_context
                    if system_proxy:
                        connect_kwargs["proxy"] = system_proxy

                    async with websockets.connect(self.relay_url, **connect_kwargs) as ws:
                        self.ws = ws
                        init_pkt = json.dumps({
                            "type": "init_host",
                            "room_id": self.room_id,
                            "pin": self.pin,
                            "width": w,
                            "height": h,
                            "device_name": self.device_name,
                            "account": self.account,
                            "user_id": self.user_id,
                            "machine_id": self.get_machine_id(),
                            "os_info": "Windows 11 x64",
                            "monitors": self.capture.monitors
                        })
                        await ws.send(init_pkt)

                        ack_raw = await ws.recv()
                        ack = json.loads(ack_raw) if isinstance(ack_raw, str) else {}
                        if ack.get("status") != "ok":
                            err_msg = ack.get("message") or ack.get("error") or ack.get("detail") or (str(ack_raw) if ack_raw else "Authentication rejected")
                            logger.error(f"Relay authentication rejected: {err_msg} (raw: {ack_raw})")
                            if self.on_status_change:
                                try:
                                    self.on_status_change("reconnecting", detail=err_msg)
                                except Exception:
                                    pass
                            await asyncio.sleep(5)
                            continue

                        logger.info(f"Host Registered Successfully! Room: {self.room_id}")
                        if self.on_status_change:
                            try:
                                self.on_status_change("ready")
                            except Exception:
                                pass

                        self.frame_queue = asyncio.Queue(maxsize=1)
                        self.audio_queue = asyncio.Queue(maxsize=50)
                        capture_task = asyncio.create_task(self._stream_screen())
                        send_task = asyncio.create_task(self._send_frames_worker(ws))
                        audio_task = asyncio.create_task(self._send_audio_loop(ws))
                        recv_task = asyncio.create_task(self._receive_events_loop(ws))

                        done, pending = await asyncio.wait(
                            [capture_task, send_task, audio_task, recv_task],
                            return_when=asyncio.FIRST_COMPLETED
                        )
                        for t in pending:
                            t.cancel()
                        self.audio_capture.stop()
                        self.audio_playback.stop()
                    await self.tunnel_manager.close_all()

                except (websockets.ConnectionClosed, ConnectionRefusedError, OSError, ssl.SSLError) as e:
                    if not self.running:
                        break
                    err_str = str(e) or type(e).__name__
                    # Detect corporate SSL Inspection and auto-switch to enterprise bypass
                    is_ssl_err = isinstance(e, ssl.SSLError) or "CERTIFICATE_VERIFY_FAILED" in err_str or "self-signed certificate" in err_str or "certificate verify failed" in err_str
                    if is_ssl_err and not self._allow_insecure_ssl:
                        logger.warning(f"Corporate SSL inspection detected ({err_str}). Switching to enterprise TLS bypass mode...")
                        self._allow_insecure_ssl = True
                        if self.on_status_change:
                            try:
                                self.on_status_change("reconnecting", detail="Phát hiện SSL Firewall công ty. Đang tự động chuyển sang chế độ vượt bảo mật...")
                            except Exception:
                                pass
                        await asyncio.sleep(1)
                        continue

                    logger.warning(f"Connection lost ({err_str}). Reconnecting in 3s...")
                    if self.on_status_change:
                        try:
                            self.on_status_change("reconnecting", detail=err_str)
                        except Exception:
                            pass
                    await asyncio.sleep(3)
                except Exception as e:
                    err_str = str(e) or type(e).__name__
                    logger.error(f"Unexpected error: {err_str}. Reconnecting in 5s...")
                    if self.on_status_change:
                        try:
                            self.on_status_change("reconnecting", detail=err_str)
                        except Exception:
                            pass
                    await asyncio.sleep(5)
        finally:
            PowerManager.prevent_sleep(False)

def resolve_config_path() -> Optional[Path]:
    candidates = []
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.append(exe_dir / "config.json")
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            candidates.append(Path(local_app_data) / "MeikovaRelayHost" / "config.json")
    else:
        candidates.append(Path.home() / ".meikova-relay" / "config.json")
    candidates.append(Path.cwd() / "config.json")
    candidates.append(Path(__file__).resolve().parent / "config.json")
    candidates.append(Path.home() / ".meikova_relay_config.json")
    for c in candidates:
        if c.exists() and c.is_file():
            return c
    return None

def main():
    parser = argparse.ArgumentParser(description="Meikova Relay Desktop - Host Agent")
    parser.add_argument("--config", default="", help="Path to config.json")
    parser.add_argument("--relay", default="", help="Relay Server URL")
    parser.add_argument("--room", default="", help="Room ID / Session Code")
    parser.add_argument("--pin", default="", help="Security PIN")
    parser.add_argument("--name", default="", help="Device Name")
    parser.add_argument("--account", default="", help="Linked user account (email or username)")
    parser.add_argument("--user-id", default="", help="Linked user ID")
    parser.add_argument("--fps", type=int, default=0, help="Target capture FPS")
    parser.add_argument("--quality", type=int, default=0, help="JPEG quality 1-100")
    parser.add_argument("--install-virtual-audio", action="store_true", help="Download and install VB-Audio Virtual Cable for headless audio")
    parser.add_argument("--install-virtual-display", action="store_true", help="Download and install Microsoft IddCx Virtual Display Driver for headless display")
    parser.add_argument("--probe-protocols", action="store_true", help="Probe and display native protocol negotiation matrix")

    args = parser.parse_args()
    if getattr(args, "probe_protocols", False):
        matrix = probe_all_protocols()
        print("=== MEIKOVA NATIVE PROTOCOL MATRIX ===")
        print(json.dumps(matrix, indent=2))
        sys.exit(0)
    if getattr(args, "install_virtual_display", False):
        print("[*] Installing Virtual Display Driver (IddCx)...")
        res = download_and_install_virtual_display()
        print("[+]" if res.get("success") else "[-]", res.get("message"))
        sys.exit(0 if res.get("success") else 1)
    if args.install_virtual_audio:
        print("[*] Installing Virtual Audio Device (VB-CABLE)...")
        res = download_and_install_vbcable()
        print("[+]" if res.get("success") else "[-]", res.get("message"))
        sys.exit(0 if res.get("success") else 1)

    cfg_data = {}
    cfg_file = Path(args.config) if args.config else resolve_config_path()
    if cfg_file and cfg_file.is_file():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                cfg_data = json.load(f)
            logger.info(f"Loaded host configuration from {cfg_file}")
        except Exception as e:
            logger.warning(f"Failed to read config from {cfg_file}: {e}")

    relay_url = args.relay or cfg_data.get("relay") or "ws://127.0.0.1:8080"
    room_id = args.room or cfg_data.get("room_id") or "RD-8888"
    pin = args.pin or cfg_data.get("pin") or "123456"
    device_name = args.name or cfg_data.get("device_name") or os.environ.get("COMPUTERNAME", socket.gethostname())
    account = args.account or cfg_data.get("account") or ""
    user_id = args.user_id or cfg_data.get("user_id") or None
    fps = args.fps if args.fps > 0 else int(cfg_data.get("fps", 25))
    quality = args.quality if args.quality > 0 else int(cfg_data.get("quality", 65))

    service = HostService(
        relay_url=relay_url,
        room_id=room_id,
        pin=pin,
        device_name=device_name,
        account=account,
        user_id=user_id,
        fps=fps,
        quality=quality
    )

    try:
        asyncio.run(service.start())
    except KeyboardInterrupt:
        logger.info("Host Agent stopped by user.")

if __name__ == "__main__":
    main()

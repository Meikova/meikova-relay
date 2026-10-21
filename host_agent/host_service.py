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
    from host_agent.file_manager import FileManager
    from host_agent.terminal_manager import TerminalManager
    from host_agent.system_manager import SystemManager
    from host_agent.power_manager import PowerManager
    from host_agent.audio_capture import AudioCapture
    from host_agent.audio_playback import AudioPlayback
except ModuleNotFoundError:
    from protocol import Protocol
    from screen_capture import ScreenCapture
    from input_injector import InputInjector
    from clipboard_manager import ClipboardManager
    from file_manager import FileManager
    from terminal_manager import TerminalManager
    from system_manager import SystemManager
    from power_manager import PowerManager
    from audio_capture import AudioCapture
    from audio_playback import AudioPlayback

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("HostAgent")

class HostService:
    """Manages outbound WebSocket connection to Relay Server and streams desktop + handles all remote events."""

    def __init__(self, relay_url: str, room_id: str, pin: str, device_name: str = "Workstation", account: str = "", fps: int = 25, quality: int = 65):
        self.relay_url = relay_url
        self.room_id = room_id
        self.pin = pin
        self.device_name = device_name
        self.account = account
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

        # Audio Capture & Stream
        self.audio_capture = AudioCapture(on_chunk=self._on_audio_chunk)
        self.audio_enabled = False
        self.audio_queue: Optional[asyncio.Queue] = None

        # Audio Playback (Client Mic -> Host Speakers)
        self.audio_playback = AudioPlayback()

        # GUI & Integration Callbacks
        self.on_client_connect = None
        self.on_client_disconnect = None
        self.on_status_change = None

        # Clipboard Sync
        self.clipboard = ClipboardManager(on_clipboard_change=self._on_local_clipboard_change)
        self.clipboard.start_listener()

        # Terminal Session
        self.terminal = TerminalManager(on_output=self._on_terminal_output)
        self.terminal.start()

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

    def _on_terminal_output(self, output_text: str):
        if self.ws and self.has_active_client and self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.ws.send(json.dumps({
                    "type": "terminal_output",
                    "data": output_text
                })),
                self.loop
            )

    def apply_quality_preset(self, preset: str) -> str:
        """Applies streaming frame rate, quality, and compression parameters."""
        # ponytail: deterministic preset mapping, single source of truth
        if preset == "native_1to1":
            self.capture.quality = 95
            self.capture.max_width = None
            self.frame_interval = 1.0 / 60.0
        elif preset == "ultra_120":
            self.capture.quality = 55
            self.capture.max_width = None
            self.frame_interval = 1.0 / 120.0
        elif preset == "crisp_2k_4k":
            self.capture.quality = 92
            self.capture.max_width = None
            self.frame_interval = 1.0 / 30.0
        elif preset == "speed_60":
            self.capture.quality = 50
            self.capture.max_width = None
            self.frame_interval = 1.0 / 60.0
        elif preset == "crisp_hd":
            self.capture.quality = 85
            self.capture.max_width = None
            self.frame_interval = 1.0 / 30.0
        elif preset == "grayscale":
            self.capture.quality = 35
            self.capture.max_width = 1280
            self.frame_interval = 1.0 / 25.0
        else: # balanced default
            preset = "balanced"
            self.capture.quality = 65
            self.capture.max_width = None
            self.frame_interval = 1.0 / 30.0
        return preset

    def negotiate_optimal_display_profile(self, client_w: int, client_h: int, client_fps: int = 60) -> dict:
        """
        Negotiates highest optimal resolution & frame profile between host monitor and controller client.
        // ponytail: deterministic capability matching without heuristic overhead
        """
        host_w, host_h = self.capture.resolution
        
        # High refresh rate priority (120 FPS)
        if client_fps >= 120:
            recommended = "ultra_120"
            suggested_scale = "fit" if (client_w < host_w or client_h < host_h) else "1to1"
        # Ultra HD (2K / 4K) fidelity priority
        elif host_w >= 2560 or host_h >= 1440 or client_w >= 2560:
            recommended = "crisp_2k_4k"
            suggested_scale = "1to1" if (client_w >= host_w and client_h >= host_h) else "fit"
        # Native 1:1 Pixel-Perfect priority if controller can display host resolution unscaled
        elif client_w >= host_w and client_h >= host_h:
            recommended = "native_1to1"
            suggested_scale = "1to1"
        # 60 FPS smooth default for standard displays
        elif client_fps >= 60:
            recommended = "speed_60"
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

    async def _send_frames_loop(self, ws: websockets.WebSocketClientProtocol):
        logger.info(f"Frame streamer started targeting {self.fps} FPS")
        last_heartbeat = time.time()
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

            start_time = time.perf_counter()

            frame_bytes = self.capture.capture_frame(force=False)
            if frame_bytes:
                try:
                    await ws.send(frame_bytes)
                except Exception as e:
                    logger.warning(f"Error sending frame: {e}")
                    break

            if time.time() - last_heartbeat > 10:
                try:
                    await ws.send(json.dumps({"type": "ping", "ts": time.time()}))
                    last_heartbeat = time.time()
                except Exception:
                    break

            elapsed = time.perf_counter() - start_time
            sleep_time = max(0.001, self.frame_interval - elapsed)
            await asyncio.sleep(sleep_time)

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
                        "active_id": self.capture.active_monitor_id
                    }))
                    await ws.send(json.dumps({
                        "type": "audio_capabilities",
                        "available": self.audio_capture.is_wasapi_available,
                        "sample_rate": self.audio_capture.sample_rate,
                        "channels": self.audio_capture.channels
                    }))
                    clip_text = self.clipboard.get_clipboard_text()
                    if clip_text:
                        await ws.send(json.dumps({
                            "type": "clipboard_sync",
                            "text": clip_text
                        }))
                    # Send initial terminal prompt & working directory
                    cwd = os.getcwd()
                    await ws.send(json.dumps({
                        "type": "terminal_output",
                        "data": f"=== MEIKOVA RELAY POWERSHELL (UTF-8) SẴN SÀNG ===\r\nThiết bị: {self.device_name} | Thư mục: {cwd}\r\nPS {cwd}> "
                    }))
                    continue

                elif ev_type == "client_disconnected":
                    logger.info("[-] Client disconnected.")
                    self.has_active_client = False
                    self.audio_enabled = False
                    self.audio_capture.stop()
                    self.audio_playback.stop()
                    if self.on_client_disconnect:
                        try:
                            self.on_client_disconnect()
                        except Exception:
                            pass
                    continue
                    continue

                # Audio Stream Control (Host Speakers -> Client Browser)
                elif ev_type == "audio_stream_toggle":
                    self.audio_enabled = bool(event.get("enabled", False))
                    if self.audio_enabled:
                        self.audio_capture.start()
                    else:
                        self.audio_capture.stop()
                    await ws.send(json.dumps({
                        "type": "audio_stream_status",
                        "enabled": self.audio_enabled,
                        "sample_rate": self.audio_capture.sample_rate,
                        "channels": self.audio_capture.channels
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
                    if new_text:
                        self.clipboard.set_clipboard_text(new_text)
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
                elif ev_type == "chat_message":
                    msg_text = str(event.get("message", "")).strip()
                    sender = str(event.get("sender", "Kỹ thuật viên"))
                    logger.info(f"[Chat from {sender}]: {msg_text}")
                    if hasattr(self, "on_chat_message") and self.on_chat_message:
                        self.on_chat_message(sender, msg_text)
                    await ws.send(json.dumps({"type": "chat_ack", "status": "delivered"}))
                elif ev_type == "ping":
                    await ws.send(json.dumps({"type": "pong", "ts": event.get("ts", 0)}))

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
                            "os_info": "Windows 11 x64",
                            "monitors": self.capture.monitors
                        })
                        await ws.send(init_pkt)

                        ack_raw = await ws.recv()
                        ack = json.loads(ack_raw) if isinstance(ack_raw, str) else {}
                        if ack.get("status") != "ok":
                            err_msg = ack.get("message", "Authentication rejected")
                            logger.error(f"Relay authentication rejected: {err_msg}")
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

                        self.audio_queue = asyncio.Queue(maxsize=50)
                        send_task = asyncio.create_task(self._send_frames_loop(ws))
                        audio_task = asyncio.create_task(self._send_audio_loop(ws))
                        recv_task = asyncio.create_task(self._receive_events_loop(ws))

                        done, pending = await asyncio.wait(
                            [send_task, audio_task, recv_task],
                            return_when=asyncio.FIRST_COMPLETED
                        )
                        for t in pending:
                            t.cancel()
                        self.audio_capture.stop()
                        self.audio_playback.stop()

                except (websockets.ConnectionClosed, ConnectionRefusedError, OSError, ssl.SSLError) as e:
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

def main():
    parser = argparse.ArgumentParser(description="Meikova Relay Desktop - Host Agent")
    parser.add_argument("--relay", default="ws://127.0.0.1:8080", help="Relay Server URL")
    parser.add_argument("--room", default="RD-8888", help="Room ID / Session Code")
    parser.add_argument("--pin", default="123456", help="Security PIN")
    parser.add_argument("--name", default="Workstation-PC", help="Device Name")
    parser.add_argument("--account", default="", help="Linked user account (email or username)")
    parser.add_argument("--fps", type=int, default=25, help="Target capture FPS")
    parser.add_argument("--quality", type=int, default=65, help="JPEG quality 1-100")

    args = parser.parse_args()
    service = HostService(
        relay_url=args.relay,
        room_id=args.room,
        pin=args.pin,
        device_name=args.name,
        account=args.account,
        fps=args.fps,
        quality=args.quality
    )

    try:
        asyncio.run(service.start())
    except KeyboardInterrupt:
        logger.info("Host Agent stopped by user.")

if __name__ == "__main__":
    main()

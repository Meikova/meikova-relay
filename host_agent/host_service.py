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
from typing import Optional, Tuple, Any, Dict
try:
    from .auto_bootstrap import (
        activate_vendor_paths,
        ensure_dependencies,
        inspect_dependencies,
        download_wheelhouse,
        install_into_vendor_packages,
    )
    activate_vendor_paths()
except Exception:
    try:
        from auto_bootstrap import (
            activate_vendor_paths,
            ensure_dependencies,
            inspect_dependencies,
            download_wheelhouse,
            install_into_vendor_packages,
        )
        activate_vendor_paths()
    except Exception:
        activate_vendor_paths = lambda: {}
        ensure_dependencies = lambda **kw: {}
        inspect_dependencies = lambda: {}
        download_wheelhouse = lambda **kw: {}
        install_into_vendor_packages = lambda **kw: {}
import concurrent.futures
try:
    import websockets
except ImportError:
    class _WebsocketsStub:
        WebSocketClientProtocol = object
        ConnectionClosed = ConnectionError
        @staticmethod
        def connect(*args, **kwargs):
            raise RuntimeError("websockets package is required for live relay connections")
    websockets = _WebsocketsStub()

APP_VERSION = "1.5.0"

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
    from host_agent.engines import get_active_os_engine, create_platform_engine
    from host_agent.power_manager import PowerManager
    from host_agent.audio_capture import AudioCapture
    from host_agent.audio_playback import AudioPlayback
    from host_agent.virtual_audio import is_audio_output_available, download_and_install_vbcable, get_virtual_audio_status
    from host_agent.virtual_display import is_headless_display, download_and_install_virtual_display, set_display_resolution, get_available_resolutions, get_virtual_display_driver_status
    from host_agent.privacy_curtain import privacy_curtain
    from host_agent.protocol_prober import probe_all_protocols
    from host_agent.tcp_tunnel import TcpTunnelManager
    from host_agent.deployment_manager import elevate_and_execute, get_deployment_status, manage_windows_service
except ModuleNotFoundError:
    from protocol import Protocol
    from screen_capture import ScreenCapture
    from input_injector import InputInjector
    from clipboard_manager import ClipboardManager
    from cursor_manager import CursorManager
    from file_manager import FileManager
    from terminal_manager import TerminalManager
    from system_manager import SystemManager
    try:
        from engines import get_active_os_engine, create_platform_engine
    except ImportError:
        def get_active_os_engine(): return None
        def create_platform_engine(plat=None): return None
    from power_manager import PowerManager
    from audio_capture import AudioCapture
    from audio_playback import AudioPlayback
    from virtual_audio import is_audio_output_available, download_and_install_vbcable, get_virtual_audio_status
    from virtual_display import is_headless_display, download_and_install_virtual_display, set_display_resolution, get_available_resolutions, get_virtual_display_driver_status
    from privacy_curtain import privacy_curtain
    from protocol_prober import probe_all_protocols
    from tcp_tunnel import TcpTunnelManager
    try:
        from deployment_manager import elevate_and_execute, get_deployment_status, manage_windows_service
    except ImportError:
        def elevate_and_execute(args_str: str) -> bool: return False
        def get_deployment_status() -> dict: return {}
        def manage_windows_service(action: str = "install"): return False, "Unsupported"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("HostAgent")

# 4-byte binary micro-frame representing a zero-bandwidth static cached frame repeat tick
MICRO_FRAME_REPEAT = b"MKR0"


def is_current_user_admin() -> bool:
    """Checks whether the current host agent process has Administrator/root privileges."""
    if sys.platform == "win32":
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False
    else:
        try:
            return os.geteuid() == 0
        except Exception:
            return False


class HostService:
    """Manages outbound WebSocket connection to Relay Server and streams desktop + handles all remote events."""

    def __init__(
        self,
        relay_url: str,
        room_id: str,
        pin: str = "123456",
        device_name: str = "Workstation",
        account: str = "",
        fps: int = 120,
        quality: int = 70,
        user_id: Optional[str] = None,
        host_config: Optional[Dict[str, Any]] = None,
        fps_limit: int = 0,
        uncapped_fps: bool = False,
        stream_mode: str = "adaptive_vfr",
        color_filter: str = "normal",
        auto_lock_on_disconnect: bool = False,
        idle_fps_saver: bool = False,
    ):
        self.relay_url = relay_url
        self.room_id = room_id
        self.pin = pin
        self.device_name = device_name
        self.account = account
        self.user_id = user_id
        self._client_is_lan: Optional[bool] = None
        self.last_rtt_ms: float = 0.0
        self.active_preset: str = "balanced"
        _sm_aliases = {"adaptive_hybrid": "adaptive_vfr", "youtube_smooth": "continuous_cfr", "zero_replay": "low_latency_drop"}
        raw_sm = str(stream_mode or "adaptive_vfr").strip().lower()
        self.stream_mode: str = _sm_aliases.get(raw_sm, raw_sm)
        if self.stream_mode not in ("adaptive_vfr", "continuous_cfr", "low_latency_drop"):
            self.stream_mode = "adaptive_vfr"
        raw_cf = str(color_filter or "normal").strip().lower()
        self.color_filter: str = raw_cf if raw_cf in ("normal", "crisp_text", "night_shield", "high_contrast") else "normal"
        self.auto_lock_on_disconnect: bool = bool(auto_lock_on_disconnect)
        self.idle_fps_saver: bool = bool(idle_fps_saver)
        self.custom_fps_limit: int = int(fps_limit or 0)
        self.fps_limit: int = self.custom_fps_limit
        self.uncapped_fps: bool = bool(uncapped_fps or fps == 0)
        self.custom_resolution_lock: Optional[Tuple[int, int]] = None
        self._resolution_lock = asyncio.Lock()
        self.fps = fps if fps != 25 else (120 if self._detect_url_is_lan(relay_url) else 60)
        if self.uncapped_fps:
            self.fps = max(self.fps, 240)
            self.frame_interval = 1.0 / 1000.0
        else:
            self.frame_interval = 1.0 / max(1, self.fps)
        self.quality = quality
        self.os_engine = get_active_os_engine()
        self.capture = ScreenCapture(quality=self.quality)
        if self.uncapped_fps:
            self.capture.bg_min_interval = 0.0002
        self._capture_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="MeikovaCapture")
        self.file_manager = FileManager()
        self.running = True
        self.has_active_client = False
        self._allow_insecure_ssl = False
        self.ws: Optional[Any] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.frame_queue: Optional[asyncio.Queue] = None
        self.frames_in_flight: int = 0
        self.ack_event: Optional[asyncio.Event] = None
        self._fps_wake_event: Optional[asyncio.Event] = None
        self._last_ack_rx_time: float = 0.0
        self._last_sent_frame_obj_id: Optional[int] = None
        self._last_mkr0_sent_time: float = 0.0
        self._force_full_frame: bool = True
        self._consecutive_high_rtt: int = 0
        self._consecutive_low_rtt: int = 0

        # Host Configuration Dictionary (Basic & Admin-Required settings)
        self.host_config: Dict[str, Any] = {
            "keep_awake": True,
            "auto_wakeup": False,
            "auto_wakeup_time": "08:00",
            "stealth_mode": False,
            "service_mode": False,
            "autostart": False,
            "open_on_boot": False,
            "close_to_tray": True,
            "show_tray_icon": True,
            "block_input": False,
            "privacy_curtain": False,
            "stream_mode": self.stream_mode,
            "color_filter": self.color_filter,
            "auto_lock_on_disconnect": self.auto_lock_on_disconnect,
            "idle_fps_saver": self.idle_fps_saver,
        }
        if isinstance(host_config, dict):
            self.host_config.update(host_config)
            if "stream_mode" in host_config and host_config["stream_mode"]:
                self.stream_mode = str(host_config["stream_mode"]).strip().lower()
            if "color_filter" in host_config and host_config["color_filter"]:
                cf_val = str(host_config["color_filter"]).strip().lower()
                if cf_val in ("normal", "crisp_text", "night_shield", "high_contrast"):
                    self.color_filter = cf_val
            if "auto_lock_on_disconnect" in host_config:
                self.auto_lock_on_disconnect = bool(host_config["auto_lock_on_disconnect"])
            if "idle_fps_saver" in host_config:
                self.idle_fps_saver = bool(host_config["idle_fps_saver"])

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
        self.on_config_updated = None

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
        self.curtain_active_sessions = set()

    @staticmethod
    def get_os_info() -> str:
        """Returns friendly OS display string (e.g. 'Windows 11 Pro 64-bit', 'macOS 14.5 (arm64)', 'Ubuntu 24.04 LTS')."""
        try:
            return SystemManager.get_os_display_name()
        except Exception:
            if sys.platform == "win32":
                return "Windows 64-bit"
            elif sys.platform == "darwin":
                return "macOS"
            return "Linux 64-bit"

    def get_host_config_snapshot(self) -> Dict[str, Any]:
        """Returns complete snapshot of Host capabilities, Admin status, and Basic/Admin configuration."""
        is_adm = is_current_user_admin()
        dep = {}
        try:
            dep = get_deployment_status()
        except Exception:
            pass
        return {
            "is_admin": is_adm,
            "os_platform": sys.platform,
            "os_engine": getattr(self.os_engine, "engine_name", sys.platform),
            "os_info": self.get_os_info(),
            "device_name": self.device_name,
            "room_id": self.room_id,
            "relay_url": self.relay_url,
            "account": self.account,
            "active_preset": getattr(self, "active_preset", "balanced"),
            "stream_mode": getattr(self, "stream_mode", "adaptive_vfr"),
            "fps_limit": self.custom_fps_limit,
            "uncapped_fps": self.uncapped_fps,
            "applied_fps": 0 if self.uncapped_fps else int(round(1.0 / max(0.0001, self.frame_interval))),
            "quality": self.capture.quality,
            "max_width": self.capture.max_width,
            "resolution": list(self.capture.resolution),
            "keep_awake": bool(self.host_config.get("keep_awake", True)),
            "auto_wakeup": bool(self.host_config.get("auto_wakeup", False)),
            "auto_wakeup_time": str(self.host_config.get("auto_wakeup_time", "08:00")),
            "stealth_mode": bool(self.host_config.get("stealth_mode", False)),
            "service_mode": bool(dep.get("service_installed", self.host_config.get("service_mode", False))),
            "autostart": bool(dep.get("user_installed", self.host_config.get("autostart", False))),
            "open_on_boot": bool(self.host_config.get("open_on_boot", False)),
            "close_to_tray": bool(self.host_config.get("close_to_tray", True)),
            "show_tray_icon": bool(self.host_config.get("show_tray_icon", True)),
            "block_input": bool(getattr(InputInjector, "is_input_blocked", False)),
            "privacy_curtain": bool(getattr(privacy_curtain, "is_active", False)),
            "color_filter": getattr(self, "color_filter", "normal"),
            "auto_lock_on_disconnect": bool(self.host_config.get("auto_lock_on_disconnect", getattr(self, "auto_lock_on_disconnect", False))),
            "idle_fps_saver": bool(self.host_config.get("idle_fps_saver", getattr(self, "idle_fps_saver", False))),
        }

    def get_host_config_dict(self) -> Dict[str, Any]:
        return self.get_host_config_snapshot()

    def stop(self):
        """Gracefully stop HostService, notifying relay server and tearing down connections."""
        self.running = False
        self.has_active_client = False
        self.audio_enabled = False
        had_curtain = bool(self.curtain_active_sessions) or getattr(privacy_curtain, "is_active", False)
        self.curtain_active_sessions.clear()
        try:
            privacy_curtain.disable()
            if had_curtain or getattr(InputInjector, "is_input_blocked", False):
                InputInjector.set_block_input(False)
        except Exception:
            pass

        try:
            if hasattr(self, "capture") and self.capture:
                self.capture.close()
            if hasattr(self, "_capture_executor") and self._capture_executor:
                self._capture_executor.shutdown(wait=False, cancel_futures=True)
                self._capture_executor = None
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

    async def _send_telemetry_loop(self, ws):
        """Broadcasts hardware telemetry pulse (CPU %, RAM %, Battery) every 2 seconds to active clients."""
        try:
            from host_agent.telemetry import get_system_telemetry
        except ImportError:
            try:
                from telemetry import get_system_telemetry
            except ImportError:
                return

        while self.is_running and not ws.closed:
            try:
                if self.has_active_client:
                    telemetry_data = get_system_telemetry()
                    await ws.send(json.dumps(telemetry_data))
                await asyncio.sleep(2.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"[Telemetry] Loop error: {e}")
                await asyncio.sleep(2.0)

    def save_host_config(self, updates: Dict[str, Any]):
        """Persists updated host configuration to active config.json on disk."""
        try:
            cfg_path = getattr(self, "config_path", None) or find_config_file()
            if not cfg_path:
                if sys.platform == "win32":
                    local_app_data = os.environ.get("LOCALAPPDATA")
                    cfg_dir = Path(local_app_data) / "MeikovaRelayHost" if local_app_data else Path.cwd()
                else:
                    cfg_dir = Path.home() / ".meikova-relay"
                cfg_dir.mkdir(parents=True, exist_ok=True)
                cfg_path = cfg_dir / "config.json"

            existing = {}
            if cfg_path.exists():
                try:
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                except Exception:
                    existing = {}
            existing.update(updates)
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2, ensure_ascii=False)
            if hasattr(self, "host_config") and isinstance(self.host_config, dict):
                self.host_config.update(updates)
        except Exception as e:
            logger.error(f"[HostService] Failed to persist config to disk: {e}")

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

    @staticmethod
    def _detect_url_is_lan(url: str) -> bool:
        raw = str(url or "").strip().lower()
        if not raw:
            return True
        if raw.startswith("::ffff:"):
            raw = raw[7:]
        if raw in ("localhost", "127.0.0.1", "::1", "[::1]", "0.0.0.0"):
            return True
        try:
            parsed_target = raw if "://" in raw else f"http://{raw}"
            host = (urllib.parse.urlparse(parsed_target).hostname or "").lower().strip()
        except Exception:
            host = raw.strip("[]")
        if host.startswith("::ffff:"):
            host = host[7:]
        if not host or host in ("localhost", "127.0.0.1", "::1", "0.0.0.0") or host.endswith(".local") or host.endswith(".lan"):
            return True
        if host.startswith("192.168.") or host.startswith("10.") or host.startswith("100."):
            return True
        if host.startswith("172."):
            parts = host.split(".")
            if len(parts) >= 2 and parts[1].isdigit() and 16 <= int(parts[1]) <= 31:
                return True
        return False

    def is_local_or_lan(self) -> bool:
        """Returns True when streaming over Localhost or LAN (targets 120+ FPS), False on WAN (targets 60-120 FPS)."""
        if self._client_is_lan is not None:
            return self._client_is_lan
        if 0.0 < self.last_rtt_ms < 20.0:
            return True
        if self.last_rtt_ms >= 25.0:
            return False
        return self._detect_url_is_lan(self.relay_url)

    def _apply_fps_target(self, fps_limit: int, uncapped: bool = False):
        """Applies target FPS limit (1..1000) or Uncapped (0 / True) mode and wakes pacing loops immediately."""
        try:
            fl = int(fps_limit or 0)
        except (ValueError, TypeError):
            fl = 0
        if uncapped or fl <= 0:
            self.custom_fps_limit = 0
            self.fps_limit = 0
            self.uncapped_fps = True
            self.frame_interval = 1.0 / 1000.0
            self.capture.bg_min_interval = 0.0002
        else:
            self.custom_fps_limit = max(1, min(1000, fl))
            self.fps_limit = self.custom_fps_limit
            self.uncapped_fps = False
            self.frame_interval = 1.0 / float(self.custom_fps_limit)
            self.capture.bg_min_interval = max(0.0002, min(0.002, self.frame_interval * 0.5))
        self.host_config["fps_limit"] = self.custom_fps_limit
        self.host_config["uncapped_fps"] = self.uncapped_fps
        if self._fps_wake_event is not None:
            try:
                self._fps_wake_event.set()
            except Exception:
                pass
        if self.ack_event is not None:
            try:
                self.ack_event.set()
            except Exception:
                pass

    def apply_quality_preset(self, preset: str) -> str:
        """Applies visual resolution and compression parameters while honoring any custom Resolution Lock or FPS Limit / Uncapped mode from the client session."""
        is_lan = self.is_local_or_lan()
        high_fps_interval = (1.0 / 120.0) if is_lan else (1.0 / 60.0)
        eco_fps_interval = (1.0 / 60.0) if is_lan else (1.0 / 30.0)

        if preset == "eco":
            self.capture.quality = 45
            self.capture.max_width = 960
            self.capture.resample_filter = "nearest"
            self.capture.subsampling = 2  # 4:2:0
            self.capture.grayscale = False
            self.frame_interval = eco_fps_interval
        elif preset == "speed_60":
            self.capture.quality = 58
            self.capture.max_width = 1280
            self.capture.resample_filter = "nearest"
            self.capture.subsampling = 2  # 4:2:0
            self.capture.grayscale = False
            self.frame_interval = high_fps_interval
        elif preset == "crisp_hd":
            self.capture.quality = 80
            self.capture.max_width = 1920
            self.capture.resample_filter = "bilinear"
            self.capture.subsampling = 2  # 4:2:0
            self.capture.grayscale = False
            self.frame_interval = high_fps_interval
        elif preset == "native_1to1":
            self.capture.quality = 90
            self.capture.max_width = None
            self.capture.resample_filter = "bilinear"
            self.capture.subsampling = 0  # 4:4:4 pixel-perfect
            self.capture.grayscale = False
            self.frame_interval = high_fps_interval
        elif preset == "grayscale":
            self.capture.quality = 40
            self.capture.max_width = 1280
            self.capture.resample_filter = "nearest"
            self.capture.subsampling = 2  # 4:2:0
            self.capture.grayscale = True
            self.frame_interval = eco_fps_interval
        elif preset == "ultra_120":
            self.capture.quality = 58
            self.capture.max_width = 1280
            self.capture.resample_filter = "nearest"
            self.capture.subsampling = 2
            self.capture.grayscale = False
            self.frame_interval = 1.0 / 120.0
        elif preset == "extreme_144":
            self.capture.quality = 62
            self.capture.max_width = 1280
            self.capture.resample_filter = "nearest"
            self.capture.subsampling = 2
            self.capture.grayscale = False
            self.frame_interval = 1.0 / 144.0
        elif preset == "native_120_1to1":
            self.capture.quality = 85
            self.capture.max_width = None
            self.capture.resample_filter = "bilinear"
            self.capture.subsampling = 2
            self.capture.grayscale = False
            self.frame_interval = 1.0 / 120.0
        elif preset == "wan_60_turbo":
            self.capture.quality = 52
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
            self.frame_interval = high_fps_interval
        else:  # balanced default
            preset = "balanced"
            self.capture.quality = 70
            self.capture.max_width = 1600
            self.capture.resample_filter = "bilinear"
            self.capture.subsampling = 2  # 4:2:0
            self.capture.grayscale = False
            self.frame_interval = high_fps_interval

        # If the user locked a target resolution (including Native/GỐC) in the Resolution Menu,
        # do not let Quality Presets downscale it to 1280/1600
        res_lock = getattr(self, "custom_resolution_lock", None)
        if res_lock and preset not in ("native_1to1", "native_120_1to1", "eco", "grayscale"):
            self.capture.max_width = int(res_lock[0])

        # Honor explicit FPS Limit or Uncapped (Unlimited) FPS mode from client session
        if getattr(self, "custom_fps_limit", 0) and self.custom_fps_limit > 0:
            self.frame_interval = 1.0 / float(max(1, min(1000, self.custom_fps_limit)))
            self.capture.bg_min_interval = max(0.0002, min(0.002, self.frame_interval * 0.5))
        elif getattr(self, "uncapped_fps", False):
            self.frame_interval = 1.0 / 1000.0
            self.capture.bg_min_interval = 0.0002

        self.active_preset = preset
        self.capture.keepalive_interval = 0.0
        self.capture._last_encoded_frame = None
        self._force_full_frame = True
        return preset

    def _update_congestion_control(self, rtt_ms: float):
        """Dynamic Congestion Control (DCC) adapting compression quality & FPS across Localhost/LAN and WAN/Cloudflare Tunnel."""
        self.last_rtt_ms = float(rtt_ms)
        has_custom_fps = bool((getattr(self, "custom_fps_limit", 0) and self.custom_fps_limit > 0) or getattr(self, "uncapped_fps", False))
        if rtt_ms > 240:
            self._client_is_lan = False
            self._consecutive_high_rtt += 1
            self._consecutive_low_rtt = 0
            if self._consecutive_high_rtt >= 3:
                if self.capture.quality > 40:
                    self.capture.quality = max(38, self.capture.quality - 8)
                if not has_custom_fps:
                    self.frame_interval = min(1.0 / 30.0, max(1.0 / 60.0, self.frame_interval * 1.25))
                self._consecutive_high_rtt = 0
        elif rtt_ms < 60:
            if rtt_ms < 20:
                self._client_is_lan = True
                if not has_custom_fps and self.active_preset not in ("eco", "grayscale", "extreme_144"):
                    self.frame_interval = 1.0 / 120.0
            else:
                self._client_is_lan = False
                if not has_custom_fps and self.active_preset not in ("ultra_120", "extreme_144", "native_120_1to1", "eco", "grayscale"):
                    self.frame_interval = 1.0 / 60.0
            self._consecutive_low_rtt += 1
            self._consecutive_high_rtt = 0
            if self._consecutive_low_rtt >= 10:
                target_q = 70 if self.capture.max_width == 1600 else (90 if self.capture.max_width is None else 58)
                if self.capture.quality < target_q:
                    self.capture.quality = min(target_q, self.capture.quality + 4)
                self._consecutive_low_rtt = 0
        else:
            self._client_is_lan = False
            if not has_custom_fps and self.active_preset not in ("ultra_120", "extreme_144", "native_120_1to1", "eco", "grayscale") and self.frame_interval < (1.0 / 60.0):
                self.frame_interval = 1.0 / 60.0

    def negotiate_optimal_display_profile(self, client_w: int, client_h: int, client_fps: int = 60) -> dict:
        """
        Negotiates highest optimal resolution & frame profile between host monitor and controller client.
        """
        host_w, host_h = self.capture.resolution

        if client_fps >= 60:
            recommended = "speed_60"
            suggested_scale = "fit"
        elif client_w >= host_w and client_h >= host_h:
            recommended = "native_1to1"
            suggested_scale = "1to1"
        elif client_w >= 1920:
            recommended = "crisp_hd"
            suggested_scale = "fit"
        else:
            recommended = "balanced"
            suggested_scale = "fit"

        applied = self.apply_quality_preset(recommended)
        if not ((getattr(self, "custom_fps_limit", 0) and self.custom_fps_limit > 0) or getattr(self, "uncapped_fps", False)):
            if client_fps >= 120 or (client_fps >= 60 and self.is_local_or_lan()):
                self.frame_interval = 1.0 / 120.0
            elif client_fps >= 60:
                self.frame_interval = 1.0 / 60.0

        return {
            "type": "display_profile_matched",
            "host_res": [host_w, host_h],
            "client_res": [client_w, client_h],
            "client_fps": client_fps,
            "recommended_preset": applied,
            "applied_fps": 0 if self.uncapped_fps else int(round(1.0 / self.frame_interval)),
            "applied_quality": self.capture.quality,
            "suggested_scale": suggested_scale,
            "monitors": self.capture.monitors,
            "message": f"Đồng bộ tối ưu: Trạm {host_w}x{host_h} ↔ Điều khiển {client_w}x{client_h} @ {client_fps}Hz -> {applied}"
        }

    async def _stream_screen(self):
        """Streams encoded frames with hardware QPC (time.perf_counter) + pure asyncio.sleep(0) pacing.
        Never calls asyncio.sleep(t>0), asyncio.wait_for(timeout>0), or time.sleep(t>0) during active pacing,
        completely bypassing Windows 11's 15.625ms (64Hz) timer quantization so 30, 60, 120, 144, 240, 360,
        and 1000+ FPS (MAX) all hit their exact target rates."""
        fps_target = "UNCAPPED" if self.uncapped_fps else int(round(1.0 / max(0.0001, self.frame_interval)))
        logger.info(f"Screen capture loop started targeting {fps_target} FPS")
        loop = asyncio.get_running_loop()
        if self._fps_wake_event is None:
            self._fps_wake_event = asyncio.Event()
        next_deadline = time.perf_counter()

        while self.running:
            if not self.has_active_client:
                await asyncio.sleep(0.05)
                next_deadline = time.perf_counter()
                continue

            try:
                if self.capture._last_encoded_frame is not None and callable(getattr(self.capture.capture_frame, "__self__", None)):
                    frame_bytes = self.capture.capture_frame(False)
                else:
                    executor = getattr(self, "_capture_executor", None)
                    frame_bytes = await loop.run_in_executor(executor, self.capture.capture_frame, False)
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
            except Exception as cap_err:
                logger.warning(f"Frame capture error (recovered): {cap_err}")
                await asyncio.sleep(0.05)
                next_deadline = time.perf_counter()
                continue

            if getattr(self, "uncapped_fps", False) or self.frame_interval <= 0.0008:
                next_deadline = time.perf_counter()
                await asyncio.sleep(0)
                continue

            next_deadline += self.frame_interval
            now = time.perf_counter()
            if now - next_deadline > max(0.05, self.frame_interval * 4.0):
                next_deadline = now

            if now >= next_deadline:
                await asyncio.sleep(0)
                continue

            # Hybrid Sleep: Sleep OS thread for bulk duration, then spin asyncio.sleep(0) for <1ms precision
            rem = next_deadline - time.perf_counter()
            if rem > 0.002:
                await asyncio.sleep(rem - 0.001)

            while self.running and self.has_active_client and not getattr(self, "uncapped_fps", False):
                if self._fps_wake_event is not None and self._fps_wake_event.is_set():
                    self._fps_wake_event.clear()
                    next_deadline = time.perf_counter()
                    break
                if time.perf_counter() >= next_deadline:
                    break
                await asyncio.sleep(0)

    async def _send_frames_worker(self, ws: Any):
        """High-throughput, zero-replay frame sender supporting 1000+ FPS Uncapped MKR0 micro-frames
        and exact QPC (time.perf_counter) FPS limit pacing (1..1000 FPS) with automatic catch-up
        whenever full-JPEG encoding or socket writes span multiple frame intervals."""
        logger.info("Frame sender worker started")
        last_heartbeat = time.time()
        self.frames_in_flight = 0
        self.ack_event = asyncio.Event()
        if self._fps_wake_event is None:
            self._fps_wake_event = asyncio.Event()
        self._last_sent_frame_obj_id = None
        self._last_mkr0_sent_time = 0.0
        self._force_full_frame = True
        next_send_qpc = time.perf_counter()
        last_known_interval = self.frame_interval
        last_known_uncapped = getattr(self, "uncapped_fps", False)

        while self.running:
            if not self.has_active_client:
                if time.time() - last_heartbeat > 10:
                    try:
                        await ws.send(json.dumps({"type": "ping", "ts": time.time()}))
                        last_heartbeat = time.time()
                    except Exception:
                        break
                await asyncio.sleep(0.1)
                next_send_qpc = time.perf_counter()
                continue

            try:
                if self.frame_queue is None:
                    await asyncio.sleep(0.02)
                    continue

                cur_uncapped = getattr(self, "uncapped_fps", False)
                cur_interval = self.frame_interval
                if cur_uncapped != last_known_uncapped or abs(cur_interval - last_known_interval) > 1e-7:
                    last_known_uncapped = cur_uncapped
                    last_known_interval = cur_interval
                    next_send_qpc = time.perf_counter()

                is_lan = self.is_local_or_lan()
                transport = getattr(ws, "transport", None)
                if transport and hasattr(transport, "get_write_buffer_size"):
                    # 1.5MB WAN buffer comfortably accommodates 2K (250-400KB) and 4K (450-850KB) frames without false stalls
                    max_buf = (384 * 1024) if is_lan else (384 * 1024)  # ponytail: 384KB cap — prevents 40-50 stale frames in TCP buffer
                    if transport.get_write_buffer_size() > max_buf:
                        await asyncio.sleep(0.005)
                        continue

                try:
                    frame = await asyncio.wait_for(self.frame_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    frame = None

                if frame:
                    while not self.frame_queue.empty():
                        try:
                            frame = self.frame_queue.get_nowait()
                        except asyncio.QueueEmpty:
                            break

                    s_mode = getattr(self, "stream_mode", "adaptive_vfr")
                    is_real_jpeg = len(frame) >= 512
                    now_pc = time.perf_counter()
                    cfr_need_keyframe = (
                        s_mode in ("continuous_cfr", "youtube_smooth")
                        and (now_pc - getattr(self, "_last_cfr_full_send_time", 0.0)) >= 0.25
                    )
                    is_same_cached_obj = (
                        is_real_jpeg
                        and not cfr_need_keyframe
                        and not getattr(self, "_force_full_frame", False)
                        and id(frame) == getattr(self, "_last_sent_frame_obj_id", None)
                    )

                    if is_same_cached_obj:
                        is_idle_eco = (
                            s_mode not in ("continuous_cfr", "youtube_smooth")
                            and bool(self.host_config.get("idle_fps_saver", getattr(self, "idle_fps_saver", False)))
                            and getattr(self.capture, "_input_dirty_until", 0.0) > 0.0
                            and (now_pc - getattr(self.capture, "_input_dirty_until", 0.0)) > 15.0
                        )
                        if is_idle_eco and (now_pc - getattr(self, "_last_mkr0_sent_time", 0.0)) < 0.10:
                            await asyncio.sleep(0.01)
                            continue
                        self._last_mkr0_sent_time = now_pc
                        await ws.send(MICRO_FRAME_REPEAT)
                    else:
                        is_input_burst = now_pc < getattr(self.capture, "_input_dirty_until", 0.0)
                        if is_lan:
                            max_in_flight = 2  # ponytail: was 16, reduced to prevent bufferbloat on LAN
                        elif s_mode in ("low_latency_drop", "zero_replay") or (s_mode in ("adaptive_vfr", "adaptive_hybrid") and is_input_burst):
                            max_in_flight = 2
                        elif s_mode in ("continuous_cfr", "youtube_smooth"):
                            max_in_flight = 12
                        else:
                            max_in_flight = 6

                        rtt_sec = max(0.03, float(getattr(self, "last_rtt_ms", 0.0) or 60.0) / 1000.0)
                        ack_expiry = max(0.35, min(1.2, rtt_sec * 2.5))

                        if is_real_jpeg and self.frames_in_flight >= max_in_flight:
                            if (now_pc - getattr(self, "_last_ack_rx_time", 0.0)) < ack_expiry and self.ack_event is not None:
                                self.ack_event.clear()
                                timeout = min(0.060, rtt_sec * 0.5)  # ponytail: non-blocking ACK wait, 0% idle CPU
                                try:
                                    await asyncio.wait_for(self.ack_event.wait(), timeout=timeout)
                                except asyncio.TimeoutError:
                                    pass
                                self.frames_in_flight = max(0, max_in_flight - 1)
                                while not self.frame_queue.empty():
                                    try:
                                        frame = self.frame_queue.get_nowait()
                                    except asyncio.QueueEmpty:
                                        break
                            else:
                                self.frames_in_flight = max(0, max_in_flight - 1)

                        self._last_sent_frame_obj_id = id(frame)
                        self._last_cfr_full_send_time = now_pc
                        self._force_full_frame = False
                        self.frames_in_flight = min(16, self.frames_in_flight + 1)
                        await ws.send(frame)

                    # Maintain exact QPC frame budget across all modes (including Continuous CFR):
                    # if a heavy 1080p/2K/4K JPEG capture/write took >1 frame_interval,
                    # immediately emit the elapsed MKR0 ticks so 30/60/120/144/240/360 FPS never drops below target!
                    if getattr(self, "uncapped_fps", False) or self.frame_interval <= 0.0008:
                        next_send_qpc = time.perf_counter()
                    else:
                        next_send_qpc += self.frame_interval
                        now_after = time.perf_counter()
                        # ponytail: removed MKR0 catch-up loop (was sending up to 32 stale micro-frames)
                        if now_after - next_send_qpc > max(0.08, self.frame_interval * 8.0):
                            next_send_qpc = now_after
                        else:
                            next_send_qpc = max(next_send_qpc, now_after)

                if time.time() - last_heartbeat > 10:
                    try:
                        await ws.send(json.dumps({"type": "ping", "ts": time.time()}))
                        last_heartbeat = time.time()
                    except Exception:
                        break

            except asyncio.CancelledError:
                break
            except (websockets.ConnectionClosed, ConnectionResetError):
                break
            except Exception as e:
                logger.warning(f"Error sending frame (transient): {e}")
                if getattr(ws, "closed", False):
                    break
                await asyncio.sleep(0.02)

    async def _send_frames_loop(self, ws: Any):
        """Legacy compatibility wrapper delegating to _send_frames_worker."""
        await self._send_frames_worker(ws)

    async def _send_audio_loop(self, ws: Any):
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
            except (websockets.ConnectionClosed, ConnectionResetError):
                break
            except Exception as e:
                logger.warning(f"Audio stream error (non-fatal): {e}")
                await asyncio.sleep(0.1)

    async def handle_control_event(self, raw_msg: str, ws):
        """Processes a single incoming control event message through the host event loop."""
        class _SingleMsgStream:
            def __init__(self, msg, ws_target):
                self._msg = msg
                self._sent = False
                self.ws = ws_target
            def __aiter__(self):
                return self
            async def __anext__(self):
                if not self._sent:
                    self._sent = True
                    return self._msg
                raise StopAsyncIteration
            async def send(self, data):
                return await self.ws.send(data)
            def __getattr__(self, name):
                return getattr(self.ws, name)

        await self._receive_events_loop(_SingleMsgStream(raw_msg, ws))

    async def _receive_events_loop(self, ws: Any):
        logger.info("Event listener started")
        async for raw_msg in ws:
            if isinstance(raw_msg, str):
                try:
                    event = json.loads(raw_msg)
                except Exception:
                    continue

                ev_type = event.get("type")

                if ev_type == "ping":
                    try:
                        await ws.send(json.dumps({"type": "pong", "ts": event.get("ts", time.time())}))
                    except Exception:
                        pass
                    continue

                if ev_type == "superseded":
                    msg = event.get("message", "Phiên kết nối máy trạm đã được thay thế bởi phiên mới")
                    logger.warning(f"[Relay] Superseded by newer session: {msg}")
                    if self.on_status_change:
                        try:
                            self.on_status_change("reconnecting", detail=msg)
                        except Exception:
                            pass
                    self.running = False
                    break

                # System & Room Control
                if ev_type == "client_connected":
                    client_ip = str(event.get("clientIp") or event.get("client_ip") or "").strip()
                    if client_ip:
                        self._client_is_lan = self._detect_url_is_lan(client_ip) and self._detect_url_is_lan(self.relay_url)
                    self._force_full_frame = True
                    self._last_sent_frame_obj_id = None
                    self.frames_in_flight = 0
                    # Default to preserving Native resolution (GỐC) on live client session connect unless locked otherwise
                    if self.custom_resolution_lock is None:
                        self.custom_resolution_lock = self.capture.resolution
                    self.apply_quality_preset(getattr(self, "active_preset", "balanced"))
                    logger.info(f"[+] Client connected (ip={client_ip}, lan={self.is_local_or_lan()}, target_fps={'UNCAPPED' if self.uncapped_fps else int(round(1.0 / self.frame_interval))})! Streaming live.")
                    self.has_active_client = True
                    try:
                        PowerManager.prevent_sleep(True)
                    except Exception:
                        pass
                    if self.on_client_connect:
                        try:
                            self.on_client_connect(event)
                        except Exception:
                            pass
                    initial_frame = self.capture.capture_frame(force=True)
                    if initial_frame:
                        self._last_sent_frame_obj_id = id(initial_frame)
                        await ws.send(initial_frame)
                    await ws.send(json.dumps({
                        "type": "monitors_list",
                        "monitors": self.capture.monitors,
                        "active_id": self.capture.active_monitor_id,
                        "is_headless": getattr(self.capture, "is_headless", False)
                    }))
                    # Broadcast Host Admin privileges & full configuration snapshot so Client Deck can enable/disable Admin-gated controls
                    await ws.send(json.dumps({
                        "type": "host_capabilities",
                        "is_admin": is_current_user_admin(),
                        "os_platform": sys.platform,
                        "os_info": self.get_os_info(),
                        "device_name": self.device_name,
                        "host_config": self.get_host_config_snapshot(),
                        "config": self.get_host_config_snapshot()
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
                    try:
                        loop = asyncio.get_running_loop()
                        self.protocol_matrix = await loop.run_in_executor(None, probe_all_protocols)
                    except Exception as e:
                        logger.warning(f"Protocol probing failed: {e}")
                    await ws.send(json.dumps({
                        "type": "protocol_matrix",
                        "matrix": self.protocol_matrix
                    }))
                    cwd = os.getcwd()
                    await ws.send(json.dumps({
                        "type": "terminal_output",
                        "data": f"=== MEIKOVA RELAY POWERSHELL (UTF-8) SẴN SÀNG ===\r\nThiết bị: {self.device_name} | Thư mục: {cwd}\r\n__MKV_CWD__{cwd}\n"
                    }))
                    if privacy_curtain.is_active:
                        await ws.send(json.dumps({
                            "type": "privacy_curtain_response",
                            "enabled": True,
                            "activeSessions": list(self.curtain_active_sessions),
                            "success": True,
                            "message": "Màn hình máy trạm đang trong Chế độ Riêng tư."
                        }))
                    continue

                elif ev_type == "client_disconnected":
                    client_count = event.get("clientCount", 0)
                    sess_id = event.get("sessionId") or event.get("session_id")
                    logger.info(f"[-] Client disconnected ({sess_id}). Remaining active clients: {client_count}")
                    if sess_id:
                        self.curtain_active_sessions.discard(sess_id)

                    if client_count <= 0 or not self.curtain_active_sessions:
                        if privacy_curtain.is_active:
                            logger.info("[PrivacyCurtain] Auto-disabling curtain mode: requesting client disconnected.")
                            privacy_curtain.disable()
                            InputInjector.set_block_input(False)
                            self.curtain_active_sessions.clear()
                            if ws and not getattr(ws, "closed", False):
                                try:
                                    await ws.send(json.dumps({
                                        "type": "privacy_curtain_response",
                                        "enabled": False,
                                        "activeSessions": [],
                                        "success": True,
                                        "message": "Đã tự động tắt Chế độ Riêng tư do người điều khiển ngắt kết nối."
                                    }))
                                except Exception:
                                    pass

                    if client_count <= 0:
                        self.has_active_client = False
                        try:
                            InputInjector.unstick_all_inputs()
                        except Exception:
                            pass
                        if not getattr(self, "keep_awake_permanent", False):
                            try:
                                PowerManager.prevent_sleep(False)
                            except Exception:
                                pass
                        self.frames_in_flight = 0
                        if self.ack_event is not None and not self.ack_event.is_set():
                            self.ack_event.set()
                        if self.frame_queue is not None:
                            while not self.frame_queue.empty():
                                try:
                                    self.frame_queue.get_nowait()
                                except Exception:
                                    break
                        self.audio_enabled = False
                        self.curtain_active_sessions.clear()
                        privacy_curtain.disable()
                        InputInjector.set_block_input(False)
                        self.has_active_client = False
                        self.frames_in_flight = 0
                        if self.ack_event is not None and not self.ack_event.is_set():
                            self.ack_event.set()
                        self.audio_capture.stop()
                        self.audio_playback.stop()
                        await self.tunnel_manager.close_all()
                        if bool(self.host_config.get("auto_lock_on_disconnect", getattr(self, "auto_lock_on_disconnect", False))):
                            logger.info("[AutoLock] Last remote client disconnected -> locking workstation OS session.")
                            try:
                                if os.environ.get("MEIKOVA_TEST_MODE") != "1":
                                    PowerManager.lock_workstation()
                            except Exception as lock_err:
                                logger.warning(f"[AutoLock] Failed to lock workstation: {lock_err}")
                        if self.on_client_disconnect:
                            try:
                                self.on_client_disconnect()
                            except Exception:
                                pass
                    continue

                elif ev_type == "frame_ack":
                    self.frames_in_flight = max(0, self.frames_in_flight - 1)
                    self._last_ack_rx_time = time.perf_counter()
                    if self.ack_event is not None and not self.ack_event.is_set():
                        self.ack_event.set()
                    host_ts = event.get("host_ts")
                    if host_ts:
                        rtt_ms = (time.time() * 1000) - float(host_ts)
                        if 0 < rtt_ms < 5000:
                            self._update_congestion_control(rtt_ms)
                    continue

                elif ev_type == "request_keyframe":
                    # Client requested an immediate fresh keyframe (e.g., after network lag/sync overlay):
                    # flush any queued stale frames and push the latest screen state immediately
                    self.frames_in_flight = 0
                    self._force_full_frame = True
                    self._last_sent_frame_obj_id = None
                    if self.ack_event is not None:
                        self.ack_event.set()
                    if self.frame_queue is not None:
                        while not self.frame_queue.empty():
                            try:
                                self.frame_queue.get_nowait()
                            except (asyncio.QueueEmpty, ValueError):
                                break
                    if hasattr(self.capture, "notify_input_activity"):
                        self.capture.notify_input_activity(0.5)
                    fresh_frame = await asyncio.to_thread(self.capture.capture_frame, True)
                    if fresh_frame:
                        self.frames_in_flight = 1
                        self._last_sent_frame_obj_id = id(fresh_frame)
                        await ws.send(fresh_frame)
                    continue

                elif ev_type == "set_stream_mode":
                    raw_sm = str(event.get("stream_mode", "adaptive_vfr")).strip().lower()
                    _sm_aliases = {"adaptive_hybrid": "adaptive_vfr", "youtube_smooth": "continuous_cfr", "zero_replay": "low_latency_drop"}
                    sm = _sm_aliases.get(raw_sm, raw_sm)
                    if sm not in ("adaptive_vfr", "continuous_cfr", "low_latency_drop"):
                        sm = "adaptive_vfr"
                    self.stream_mode = sm
                    self.host_config["stream_mode"] = sm
                    if "fps_limit" in event or "uncapped" in event:
                        req_fps = int(event.get("fps_limit") or 0)
                        is_unc = bool(event.get("uncapped", req_fps <= 0))
                        self._apply_fps_target(req_fps, uncapped=is_unc)
                    self.frames_in_flight = 0
                    self._last_cfr_full_send_time = 0.0
                    self._force_full_frame = True
                    if self.ack_event is not None:
                        self.ack_event.set()
                    await ws.send(json.dumps({
                        "type": "stream_mode_applied",
                        "stream_mode": self.stream_mode,
                        "quality": self.capture.quality,
                        "preset": getattr(self, "active_preset", "balanced")
                    }))
                    continue

                elif ev_type == "set_color_filter":
                    cf = str(event.get("color_filter", "normal")).strip().lower()
                    if cf not in ("normal", "crisp_text", "night_shield", "high_contrast"):
                        cf = "normal"
                    self.color_filter = cf
                    self.host_config["color_filter"] = cf
                    await ws.send(json.dumps({
                        "type": "color_filter_applied",
                        "color_filter": self.color_filter
                    }))
                    continue

                elif ev_type == "set_auto_lock_disconnect":
                    en_lock = bool(event.get("enabled", False))
                    self.auto_lock_on_disconnect = en_lock
                    self.host_config["auto_lock_on_disconnect"] = en_lock
                    await ws.send(json.dumps({
                        "type": "auto_lock_disconnect_response",
                        "enabled": en_lock,
                        "success": True
                    }))
                    continue

                elif ev_type == "set_idle_fps_saver":
                    en_idle = bool(event.get("enabled", False))
                    self.idle_fps_saver = en_idle
                    self.host_config["idle_fps_saver"] = en_idle
                    await ws.send(json.dumps({
                        "type": "idle_fps_saver_response",
                        "enabled": en_idle,
                        "success": True
                    }))
                    continue

                elif ev_type == "open_remote_url":
                    target_url = str(event.get("url") or "").strip()
                    ok_open = False
                    if target_url:
                        if target_url.lower().startswith(("http://", "https://", "mailto:")) or "." in target_url:
                            if "://" not in target_url and not target_url.lower().startswith("mailto:"):
                                target_url = "https://" + target_url
                            try:
                                if os.environ.get("MEIKOVA_TEST_MODE") != "1":
                                    import webbrowser
                                    webbrowser.open(target_url)
                                ok_open = True
                            except Exception as e:
                                logger.warning(f"[OpenRemoteURL] Failed to open {target_url}: {e}")
                    await ws.send(json.dumps({
                        "type": "open_remote_url_response",
                        "url": target_url,
                        "success": ok_open
                    }))
                    continue

                elif ev_type == "client_rtt":
                    rtt_val = float(event.get("rtt_ms", 0) or 0)
                    if 0 < rtt_val < 5000:
                        self._update_congestion_control(rtt_val)
                    continue

                # Host Configuration & Admin Privilege Control via Remote Client
                elif ev_type == "get_host_config":
                    await ws.send(json.dumps({
                        "type": "host_config_response",
                        "is_admin": is_current_user_admin(),
                        "host_config": self.get_host_config_snapshot(),
                        "config": self.get_host_config_snapshot()
                    }))
                    continue

                elif ev_type == "set_host_config":
                    updates = event.get("config") or event
                    is_adm = is_current_user_admin()
                    admin_only_keys = {"block_input", "privacy_curtain", "auto_wakeup", "service_mode"}
                    rejected_admin = [k for k in admin_only_keys if k in updates and bool(updates[k]) and not is_adm]
                    if rejected_admin:
                        await ws.send(json.dumps({
                            "type": "host_config_response",
                            "success": False,
                            "requires_admin": True,
                            "is_admin": is_adm,
                            "rejected_keys": rejected_admin,
                            "host_config": self.get_host_config_snapshot(),
                            "config": self.get_host_config_snapshot(),
                            "message": "Nhóm chức năng nâng cao yêu cầu quyền Quản trị viên (Admin) trên máy trạm."
                        }))
                        continue

                    if "keep_awake" in updates:
                        val = bool(updates["keep_awake"])
                        self.host_config["keep_awake"] = val
                        PowerManager.prevent_sleep(val)
                    if "auto_wakeup" in updates or "auto_wakeup_time" in updates:
                        aw_en = bool(updates.get("auto_wakeup", self.host_config.get("auto_wakeup", False)))
                        aw_tm = str(updates.get("auto_wakeup_time", self.host_config.get("auto_wakeup_time", "08:00")))
                        self.host_config["auto_wakeup"] = aw_en
                        self.host_config["auto_wakeup_time"] = aw_tm
                        PowerManager.configure_auto_wakeup(aw_en, aw_tm)
                    if "stealth_mode" in updates:
                        st_en = bool(updates["stealth_mode"])
                        self.host_config["stealth_mode"] = st_en
                        self.host_config["show_tray_icon"] = not st_en
                    if "show_tray_icon" in updates:
                        self.host_config["show_tray_icon"] = bool(updates["show_tray_icon"])
                    if "close_to_tray" in updates:
                        self.host_config["close_to_tray"] = bool(updates["close_to_tray"])
                    if "open_on_boot" in updates:
                        self.host_config["open_on_boot"] = bool(updates["open_on_boot"])
                    if "autostart" in updates:
                        self.host_config["autostart"] = bool(updates["autostart"])
                    if "service_mode" in updates and is_adm:
                        srv_en = bool(updates["service_mode"])
                        self.host_config["service_mode"] = srv_en
                        manage_windows_service("install" if srv_en else "uninstall")
                    if "block_input" in updates and is_adm:
                        blk = bool(updates["block_input"])
                        self.host_config["block_input"] = blk
                        InputInjector.set_block_input(blk)
                    if "privacy_curtain" in updates and is_adm:
                        curt = bool(updates["privacy_curtain"])
                        self.host_config["privacy_curtain"] = curt
                        if curt:
                            privacy_curtain.enable()
                            InputInjector.set_block_input(True)
                        else:
                            privacy_curtain.disable()
                            InputInjector.set_block_input(False)
                    if "stream_mode" in updates and updates["stream_mode"]:
                        sm = str(updates["stream_mode"]).strip().lower()
                        if sm in ("adaptive_vfr", "continuous_cfr", "low_latency_drop", "adaptive_hybrid", "youtube_smooth", "zero_replay"):
                            self.stream_mode = sm
                            self.host_config["stream_mode"] = sm
                    if "fps_limit" in updates or "uncapped_fps" in updates:
                        fl = int(updates.get("fps_limit") or 0)
                        is_unc = bool(updates.get("uncapped_fps", fl <= 0))
                        self._apply_fps_target(fl, uncapped=is_unc)
                    if "color_filter" in updates and updates["color_filter"]:
                        cf = str(updates["color_filter"]).strip().lower()
                        if cf in ("normal", "crisp_text", "night_shield", "high_contrast"):
                            self.color_filter = cf
                            self.host_config["color_filter"] = cf
                    if "auto_lock_on_disconnect" in updates:
                        al = bool(updates["auto_lock_on_disconnect"])
                        self.auto_lock_on_disconnect = al
                        self.host_config["auto_lock_on_disconnect"] = al
                    if "idle_fps_saver" in updates:
                        ifs = bool(updates["idle_fps_saver"])
                        self.idle_fps_saver = ifs
                        self.host_config["idle_fps_saver"] = ifs

                    if self.on_config_updated:
                        try:
                            self.on_config_updated(self.host_config)
                        except Exception:
                            pass

                    await ws.send(json.dumps({
                        "type": "host_config_response",
                        "success": True,
                        "requires_admin": False,
                        "is_admin": is_adm,
                        "host_config": self.get_host_config_snapshot(),
                        "config": self.get_host_config_snapshot(),
                        "message": "Đã cập nhật cấu hình máy trạm thành công."
                    }))
                    continue

                elif ev_type == "request_admin_elevation":
                    is_adm = is_current_user_admin()
                    if is_adm:
                        await ws.send(json.dumps({
                            "type": "admin_elevation_response",
                            "success": True,
                            "is_admin": True,
                            "message": "Máy trạm đã đang chạy với quyền Quản trị viên (Admin)."
                        }))
                    else:
                        elevated = elevate_and_execute("--admin --restart")
                        await ws.send(json.dumps({
                            "type": "admin_elevation_response",
                            "success": elevated,
                            "is_admin": is_current_user_admin(),
                            "message": "Đã gửi yêu cầu nâng quyền UAC trên màn hình máy trạm." if elevated else "Không thể kích hoạt UAC hoặc người dùng tại máy trạm đã từ chối."
                        }))
                    continue

                elif ev_type == "check_host_dependencies":
                    loop = asyncio.get_running_loop()
                    dep_report = await loop.run_in_executor(None, inspect_dependencies)
                    await ws.send(json.dumps({
                        "type": "host_dependencies_status",
                        "report": dep_report
                    }))
                    continue

                elif ev_type == "install_host_dependencies":
                    loop = asyncio.get_running_loop()
                    dep_report = await loop.run_in_executor(None, lambda: ensure_dependencies(auto_install=True))
                    await ws.send(json.dumps({
                        "type": "host_dependencies_status",
                        "report": dep_report
                    }))
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
                    has_output = is_audio_output_available()
                    if res.get("success") and self.audio_enabled:
                        self.audio_capture.stop()
                        await asyncio.sleep(1)
                        self.audio_capture.start()
                    await ws.send(json.dumps({
                        "type": "virtual_audio_install_result",
                        "success": res.get("success", False),
                        "has_device": has_output,
                        "message": res.get("message", "")
                    }))
                    await ws.send(json.dumps({
                        "type": "audio_capabilities",
                        "available": self.audio_capture.is_wasapi_available,
                        "has_output_device": has_output,
                        "sample_rate": self.audio_capture.sample_rate,
                        "channels": self.audio_capture.channels
                    }))
                    continue

                # Install Virtual Display Driver Request (Headless / No Physical Monitor)
                elif ev_type == "install_virtual_display":
                    logger.info("[HostService] Received client request to install Virtual Display Driver.")
                    loop = asyncio.get_running_loop()
                    res = await loop.run_in_executor(None, download_and_install_virtual_display)
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
                        self._last_sent_frame_obj_id = id(initial_frame)
                        await ws.send(initial_frame)
                    continue

                # Dynamic Screen Resolution Control (Headless Virtual Display & Multi-size switcher)
                elif ev_type in ("set_screen_resolution", "set_virtual_resolution"):
                    async with self._resolution_lock:
                        w = int(event.get("width", 0))
                        h = int(event.get("height", 0))
                        fps = int(event.get("fps", 120 if self.is_local_or_lan() else 60))
                        if w <= 0 or h <= 0:
                            self.capture.custom_virtual_resolution = None
                            self.capture.monitors = self.capture.detect_monitors()
                            self.capture.max_width = None
                            nw, nh = self.capture.resolution
                            # Lock to true physical native resolution so Quality Presets never downscale it to 1280x720
                            self.custom_resolution_lock = (nw, nh)
                            res = {"success": True, "message": f"Đã khôi phục độ phân giải gốc {nw}x{nh}"}
                            w, h = nw, nh
                        else:
                            loop = asyncio.get_running_loop()
                            res = await loop.run_in_executor(None, set_display_resolution, w, h, fps)
                            self.custom_resolution_lock = (w, h)
                            self.capture.set_custom_resolution(w, h, native_applied=bool(res.get("native", False)))
                            self.capture.reset_capture_surface()  # ponytail: safely destroy stale DXGI/GDI surfaces
                            self.capture.max_width = w
                        self._force_full_frame = True
                        self._last_sent_frame_obj_id = None
                        await ws.send(json.dumps({
                            "type": "screen_resolution_result",
                            "success": res.get("success", True),
                            "width": w,
                            "height": h,
                            "is_native": int(event.get("width", 0)) <= 0,
                            "message": res.get("message", f"Đã áp dụng độ phân giải {w}x{h}")
                        }))
                        await ws.send(json.dumps({
                            "type": "monitors_list",
                            "monitors": self.capture.monitors,
                            "active_id": self.capture.active_monitor_id,
                            "is_headless": getattr(self.capture, "is_headless", False)
                        }))
                        initial_frame = await asyncio.to_thread(self.capture.capture_frame, True)
                        if initial_frame:
                            self._last_sent_frame_obj_id = id(initial_frame)
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
                    self._force_full_frame = True
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
                        self._last_sent_frame_obj_id = id(initial_frame)
                        await ws.send(initial_frame)
                    continue

                # Session-Managed FPS Limit Control (Supports explicit FPS 1..1000 OR 0 = Unlimited / Uncapped)
                elif ev_type == "set_fps_limit":
                    raw_lim = event.get("fps_limit", 0)
                    try:
                        fps_lim = int(raw_lim or 0)
                    except (ValueError, TypeError):
                        fps_lim = 0
                    is_uncapped = bool(event.get("uncapped", False)) or (fps_lim <= 0 and event.get("mode") != "preset_auto")
                    self._apply_fps_target(fps_lim, uncapped=is_uncapped)
                    if "encoder_mode" in event and event["encoder_mode"]:
                        self.capture.encoder_mode = str(event["encoder_mode"])
                    if "stream_mode" in event and event["stream_mode"]:
                        sm = str(event["stream_mode"]).strip().lower()
                        if sm in ("adaptive_vfr", "continuous_cfr", "low_latency_drop", "adaptive_hybrid", "youtube_smooth", "zero_replay"):
                            self.stream_mode = sm
                            self.host_config["stream_mode"] = sm
                    if "static_cache" in event and event["static_cache"] is not None:
                        self.capture.static_cache_enabled = bool(event["static_cache"])
                    if self.frame_queue is not None:
                        while not self.frame_queue.empty():
                            try:
                                self.frame_queue.get_nowait()
                            except (asyncio.QueueEmpty, ValueError):
                                break
                    await ws.send(json.dumps({
                        "type": "fps_limit_applied",
                        "fps_limit": self.custom_fps_limit,
                        "uncapped": self.uncapped_fps,
                        "applied_fps": 0 if self.uncapped_fps else int(round(1.0 / self.frame_interval)),
                        "quality": self.capture.quality,
                        "stream_mode": self.stream_mode,
                        "preset": getattr(self, "active_preset", "balanced")
                    }))
                    continue

                # Quality / Resolution Preset (Managed 100% from Remote Client Session)
                elif ev_type == "set_quality_preset":
                    preset = event.get("preset", "balanced")
                    if "fps_limit" in event or "uncapped" in event:
                        fl = int(event.get("fps_limit") or 0)
                        is_unc = bool(event.get("uncapped", fl <= 0))
                        self._apply_fps_target(fl, uncapped=is_unc)
                    if "encoder_mode" in event and event["encoder_mode"]:
                        self.capture.encoder_mode = str(event["encoder_mode"])
                    if "stream_mode" in event and event["stream_mode"]:
                        sm = str(event["stream_mode"]).strip().lower()
                        if sm in ("adaptive_vfr", "continuous_cfr", "low_latency_drop", "adaptive_hybrid", "youtube_smooth", "zero_replay"):
                            self.stream_mode = sm
                            self.host_config["stream_mode"] = sm
                    if "static_cache" in event and event["static_cache"] is not None:
                        self.capture.static_cache_enabled = bool(event["static_cache"])
                    applied = self.apply_quality_preset(preset)
                    logger.info(f"Applied Quality Preset: {applied} (Quality: {self.capture.quality}, Interval: {self.frame_interval})")
                    self.frames_in_flight = 0
                    self._force_full_frame = True
                    if self.ack_event is not None:
                        self.ack_event.set()
                    if self.frame_queue is not None:
                        while not self.frame_queue.empty():
                            try:
                                self.frame_queue.get_nowait()
                            except (asyncio.QueueEmpty, ValueError):
                                break
                    self.capture._last_frame_hash = None
                    fresh_frame = await asyncio.to_thread(self.capture.capture_frame, True)
                    if fresh_frame:
                        self.frames_in_flight = 1
                        self._last_sent_frame_obj_id = id(fresh_frame)
                        await ws.send(fresh_frame)
                    await ws.send(json.dumps({
                        "type": "quality_preset_applied",
                        "preset": applied,
                        "req_id": event.get("req_id"),
                        "quality": self.capture.quality,
                        "max_width": self.capture.max_width,
                        "fps": 0 if self.uncapped_fps else int(round(1.0 / self.frame_interval)),
                        "fps_limit": self.custom_fps_limit,
                        "uncapped": self.uncapped_fps,
                        "stream_mode": self.stream_mode
                    }))
                    continue

                # Auto-Negotiate & Sync Optimal Resolution
                elif ev_type == "sync_display_profile":
                    c_w = int(event.get("client_w", 1920))
                    c_h = int(event.get("client_h", 1080))
                    c_fps = int(event.get("client_fps", 60))
                    if "fps_limit" in event or "uncapped" in event:
                        fl = int(event.get("fps_limit") or 0)
                        is_unc = bool(event.get("uncapped", fl <= 0))
                        self._apply_fps_target(fl, uncapped=is_unc)
                    if self.custom_resolution_lock is None:
                        self.custom_resolution_lock = self.capture.resolution
                    res_payload = self.negotiate_optimal_display_profile(c_w, c_h, c_fps)
                    await ws.send(json.dumps(res_payload))
                    initial_frame = self.capture.capture_frame(force=True)
                    if initial_frame:
                        self._last_sent_frame_obj_id = id(initial_frame)
                        await ws.send(initial_frame)
                    logger.info(f"Negotiated Display Profile: {res_payload['message']}")
                    continue

                # Terminal Input
                elif ev_type == "terminal_input":
                    cmd = event.get("command") or event.get("data", "")
                    self.terminal.send_input(cmd)
                    continue

                # Quick Macro Execution (GUI window on remote desktop + Terminal sync)
                elif ev_type == "quick_macro":
                    cmd = str(event.get("command") or event.get("macro", "")).strip()
                    mode = event.get("mode", "auto")
                    logger.info(f"[QuickMacro] Executing macro: {cmd} (mode={mode})")
                    if cmd:
                        try:
                            self.terminal.send_input(cmd + "\r\n")
                        except Exception:
                            pass

                        if mode in ("gui", "auto"):
                            try:
                                if self.os_engine and hasattr(self.os_engine, "execute_quick_macro"):
                                    self.os_engine.execute_quick_macro(cmd, mode=mode)
                                else:
                                    import subprocess
                                    if cmd.lower() in ("winver", "dxdiag", "taskmgr", "msconfig", "calc", "regedit"):
                                        subprocess.Popen(cmd, shell=True)
                                    else:
                                        subprocess.Popen(f'cmd.exe /k "{cmd}"', shell=True)
                            except Exception as ex:
                                logger.warning(f"[QuickMacro] Failed to spawn GUI process: {ex}")
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
                    limit = int(event.get("limit", 80) or 80)
                    procs = SystemManager.get_process_list(limit=limit)
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

                # Power Management & Wake-on-LAN / Auto-Wakeup
                elif ev_type == "power_action":
                    action = event.get("action")
                    is_admin = is_current_user_admin()
                    ok = True
                    if action == "lock":
                        PowerManager.lock_workstation()
                    elif action in ("restart", "shutdown"):
                        if not is_admin:
                            logger.warning(f"[HostService] power_action {action} rejected: Administrator privileges required")
                            ok = False
                            await ws.send(json.dumps({
                                "type": "power_action_response",
                                "action": action,
                                "success": False,
                                "requires_admin": True,
                                "error": "ADMIN_PRIVILEGES_REQUIRED",
                                "message": "Khởi động lại / tắt máy trạm yêu cầu quyền Quản trị viên (Admin)."
                            }))
                            continue
                        elif action == "restart":
                            PowerManager.restart_machine()
                        elif action == "shutdown":
                            PowerManager.shutdown_machine()
                    await ws.send(json.dumps({
                        "type": "power_action_response",
                        "action": action,
                        "success": ok,
                        "requires_admin": False
                    }))
                    continue

                elif ev_type == "auto_wakeup_request":
                    is_admin = is_current_user_admin()
                    enabled = bool(event.get("enabled", False))
                    wake_time = str(event.get("wake_time", "08:00"))
                    if enabled and not is_admin:
                        await ws.send(json.dumps({
                            "type": "auto_wakeup_response",
                            "success": False,
                            "requires_admin": True,
                            "message": "Hẹn giờ tự động bật/đánh thức máy (Auto-Wakeup) yêu cầu quyền Quản trị viên (Admin)."
                        }))
                        continue
                    res = PowerManager.configure_auto_wakeup(enabled, wake_time)
                    self.host_config["auto_wakeup"] = enabled
                    self.host_config["auto_wakeup_time"] = wake_time
                    await ws.send(json.dumps({
                        "type": "auto_wakeup_response",
                        "requires_admin": False,
                        **res
                    }))
                    continue

                elif ev_type == "wake_on_lan_request":
                    mac = str(event.get("mac", ""))
                    bcast = str(event.get("broadcast_ip", "255.255.255.255"))
                    port = int(event.get("port", 9) or 9)
                    res = PowerManager.send_wake_on_lan(mac, bcast, port)
                    await ws.send(json.dumps({
                        "type": "wake_on_lan_response",
                        **res
                    }))
                    continue

                elif ev_type == "unlock_workstation":
                    password = str(event.get("password") or event.get("pin") or "")
                    success = InputInjector.unlock_workstation(password)
                    await ws.send(json.dumps({
                        "type": "unlock_workstation_response",
                        "success": success
                    }))
                    continue

                elif ev_type in ("unstick_inputs", "emergency_unstick"):
                    released = InputInjector.unstick_all_inputs()
                    await ws.send(json.dumps({
                        "type": "unstick_inputs_response",
                        "released": released,
                        "success": True
                    }))
                    continue

                elif ev_type == "host_config_update":
                    cfg = event.get("config") or event.get("settings") or {}
                    if "quality" in cfg:
                        try:
                            self.quality = max(10, min(100, int(cfg["quality"])))
                        except Exception:
                            pass
                    if "fps" in cfg or "fps_limit" in cfg:
                        try:
                            fps_val = int(cfg.get("fps", cfg.get("fps_limit", 60)))
                            self.set_target_fps(fps_val)
                        except Exception:
                            pass
                    if "preset" in cfg:
                        self.apply_quality_preset(cfg["preset"])
                    if "stream_mode" in cfg:
                        self.stream_mode = cfg["stream_mode"]
                    if "keep_awake" in cfg:
                        PowerManager.prevent_sleep(bool(cfg["keep_awake"]))
                    if "block_input" in cfg:
                        InputInjector.set_block_input(bool(cfg["block_input"]))
                    if "privacy_curtain" in cfg:
                        if cfg["privacy_curtain"]:
                            privacy_curtain.enable()
                        else:
                            privacy_curtain.disable()
                    if "color_filter" in cfg:
                        self.color_filter = cfg["color_filter"]
                    try:
                        self.save_host_config(cfg)
                    except Exception:
                        pass
                    await ws.send(json.dumps({
                        "type": "host_config_response",
                        "success": True,
                        "config": self.get_host_config_snapshot()
                    }))
                    continue

                # File Browser & Rich File Operations
                elif ev_type == "file_browse_request":
                    path = event.get("path", "")
                    data = self.file_manager.browse_path(path)
                    await ws.send(json.dumps({
                        "type": "file_browse_response",
                        "data": data
                    }))
                    continue

                elif ev_type == "file_search_request":
                    root_dir = event.get("path", "")
                    query = event.get("query", "")
                    data = self.file_manager.search_files(root_dir, query)
                    await ws.send(json.dumps({
                        "type": "file_search_response",
                        "data": data
                    }))
                    continue

                elif ev_type == "file_create_request":
                    parent_dir = event.get("parent_dir", "")
                    filename = event.get("name", "")
                    content = event.get("content", "")
                    res = self.file_manager.create_file(parent_dir, filename, content)
                    await ws.send(json.dumps({
                        "type": "file_create_response",
                        "result": res
                    }))
                    continue

                elif ev_type == "file_delete_request":
                    filepath = unicodedata.normalize('NFC', event.get("filepath", ""))
                    ok = self.file_manager.delete_item(filepath)
                    await ws.send(json.dumps({
                        "type": "file_delete_response",
                        "filepath": filepath,
                        "success": ok
                    }))
                    continue

                elif ev_type == "file_create_folder_request":
                    parent_dir = event.get("parent_dir", "")
                    folder_name = event.get("name", "")
                    res = self.file_manager.create_folder(parent_dir, folder_name)
                    await ws.send(json.dumps({
                        "type": "file_create_folder_response",
                        "result": res
                    }))
                    continue

                elif ev_type == "file_copy_request":
                    src = unicodedata.normalize('NFC', event.get("src") or event.get("src_path", ""))
                    dst = unicodedata.normalize('NFC', event.get("dst") or event.get("dst_dir", ""))
                    res = self.file_manager.copy_item(src, dst)
                    await ws.send(json.dumps({
                        "type": "file_copy_response",
                        "result": res
                    }))
                    continue

                elif ev_type == "file_move_request":
                    src = unicodedata.normalize('NFC', event.get("src") or event.get("src_path", ""))
                    dst = unicodedata.normalize('NFC', event.get("dst") or event.get("dst_dir", ""))
                    res = self.file_manager.move_item(src, dst)
                    await ws.send(json.dumps({
                        "type": "file_move_response",
                        "result": res
                    }))
                    continue

                elif ev_type == "file_rename_request":
                    old_path = unicodedata.normalize('NFC', event.get("old_path", ""))
                    new_name = unicodedata.normalize('NFC', event.get("new_name", ""))
                    res = self.file_manager.rename_item(old_path, new_name)
                    await ws.send(json.dumps({
                        "type": "file_rename_response",
                        "result": res
                    }))
                    continue

                elif ev_type == "file_read_request":
                    filepath = unicodedata.normalize('NFC', event.get("filepath", ""))
                    res = self.file_manager.read_file_content(filepath)
                    await ws.send(json.dumps({
                        "type": "file_read_response",
                        **res
                    }))
                    continue

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
                            mod_vk, v_vk = self.os_engine.get_paste_vk_combo() if (self.os_engine and hasattr(self.os_engine, "get_paste_vk_combo")) else (0x11, 0x56)
                            InputInjector.key_down(mod_vk)
                            InputInjector.key_down(v_vk)
                            InputInjector.key_up(v_vk)
                            InputInjector.key_up(mod_vk)
                            if hasattr(self.capture, "notify_input_activity"):
                                self.capture.notify_input_activity(0.45)
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
                            mod_vk, v_vk = self.os_engine.get_paste_vk_combo() if (self.os_engine and hasattr(self.os_engine, "get_paste_vk_combo")) else (0x11, 0x56)
                            InputInjector.key_down(mod_vk)
                            InputInjector.key_down(v_vk)
                            InputInjector.key_up(v_vk)
                            InputInjector.key_up(mod_vk)
                            if hasattr(self.capture, "notify_input_activity"):
                                self.capture.notify_input_activity(0.45)
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
                            mod_vk, v_vk = self.os_engine.get_paste_vk_combo() if (self.os_engine and hasattr(self.os_engine, "get_paste_vk_combo")) else (0x11, 0x56)
                            InputInjector.key_down(mod_vk)
                            InputInjector.key_down(v_vk)
                            InputInjector.key_up(v_vk)
                            InputInjector.key_up(mod_vk)
                            if hasattr(self.capture, "notify_input_activity"):
                                self.capture.notify_input_activity(0.45)
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

                # File Upload & Direct Drag-and-Drop Events
                elif ev_type == "file_upload_start":
                    transfer_id = event.get("transfer_id", "default")
                    filename = event.get("filename", "unknown.bin")
                    filesize = int(event.get("filesize", 0))
                    checksum = event.get("checksum", "")
                    target_dir = event.get("target_dir", "")
                    dest_path = self.file_manager.start_upload(transfer_id, filename, filesize, checksum, target_dir)
                    if transfer_id in self.file_manager.active_transfers:
                        self.file_manager.active_transfers[transfer_id]["drop_x"] = event.get("drop_x")
                        self.file_manager.active_transfers[transfer_id]["drop_y"] = event.get("drop_y")
                        self.file_manager.active_transfers[transfer_id]["auto_paste_drop"] = bool(event.get("auto_paste_drop", False))
                    await ws.send(json.dumps({
                        "type": "file_upload_ack",
                        "transfer_id": transfer_id,
                        "status": "ready",
                        "dest_path": dest_path
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
                    transfer_meta = self.file_manager.active_transfers.get(transfer_id, {})
                    drop_x = event.get("drop_x", transfer_meta.get("drop_x"))
                    drop_y = event.get("drop_y", transfer_meta.get("drop_y"))
                    auto_paste_drop = bool(event.get("auto_paste_drop", transfer_meta.get("auto_paste_drop", False)))
                    res = self.file_manager.finish_upload(transfer_id)
                    if res.get("status") == "success" and res.get("path"):
                        try:
                            self.clipboard.set_clipboard_files([res["path"]])
                            if auto_paste_drop:
                                if drop_x is not None and drop_y is not None:
                                    mon_rect = self.capture.active_monitor_rect
                                    InputInjector.mouse_move(float(drop_x), float(drop_y), monitor_rect=mon_rect)
                                    InputInjector.mouse_down("left")
                                    InputInjector.mouse_up("left")
                                InputInjector.key_down(0x11)
                                InputInjector.key_down(0x56)
                                InputInjector.key_up(0x56)
                                InputInjector.key_up(0x11)
                        except Exception:
                            pass
                    await ws.send(json.dumps({
                        "type": "file_upload_result",
                        "transfer_id": transfer_id,
                        "result": res
                    }))
                    continue

                # Mouse & Keyboard Input (Triggers immediate capture wake-up so typing/clicking has zero visual lag)
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
                    if hasattr(self.capture, "notify_input_activity"):
                        self.capture.notify_input_activity(0.20)
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
                    if hasattr(self.capture, "notify_input_activity"):
                        self.capture.notify_input_activity(0.45)
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
                    if hasattr(self.capture, "notify_input_activity"):
                        self.capture.notify_input_activity(0.45)
                    cur = self.cursor_manager.check_immediate()
                    if cur:
                        await ws.send(json.dumps({"type": "cursor_update", "cursor": cur}))
                elif ev_type == "mouse_wheel":
                    InputInjector.mouse_wheel(event["delta_y"])
                    if hasattr(self.capture, "notify_input_activity"):
                        self.capture.notify_input_activity(0.35)
                elif ev_type == "key_down":
                    InputInjector.key_down(event["vk"])
                    self.frames_in_flight = 0  # ponytail: interactive fast-track unblocks frame queue on keypress
                    if hasattr(self.capture, "notify_input_activity"):
                        self.capture.notify_input_activity(0.50)
                elif ev_type == "key_up":
                    InputInjector.key_up(event["vk"])
                    self.frames_in_flight = 0
                    if hasattr(self.capture, "notify_input_activity"):
                        self.capture.notify_input_activity(0.50)
                elif ev_type == "text_input":
                    InputInjector.type_unicode(event["text"])
                    self.frames_in_flight = 0
                    if hasattr(self.capture, "notify_input_activity"):
                        self.capture.notify_input_activity(0.50)
                elif ev_type == "block_input":
                    blocked = bool(event.get("blocked", False))
                    is_admin = is_current_user_admin()
                    if not is_admin:
                        logger.warning("[HostService] block_input rejected: Administrator privileges required")
                        await ws.send(json.dumps({
                            "type": "block_input_response",
                            "blocked": False,
                            "success": False,
                            "requires_admin": True,
                            "error": "ADMIN_PRIVILEGES_REQUIRED",
                            "message": "Khóa chuột & bàn phím yêu cầu quyền Quản trị viên (Admin) trên máy trạm."
                        }))
                    else:
                        ok = InputInjector.set_block_input(blocked)
                        self.host_config["block_input"] = blocked if ok else False
                        await ws.send(json.dumps({
                            "type": "block_input_response",
                            "blocked": blocked if ok else False,
                            "success": ok,
                            "requires_admin": False
                        }))
                elif ev_type == "system_hotkey":
                    combo = str(event.get("combo", "")).strip().lower()
                    is_admin = is_current_user_admin()
                    if combo in ("cad", "ctrl_alt_del") and not is_admin:
                        logger.info(f"[HostService] CAD hotkey requested without admin rights, attempting fallback...")
                        ok = InputInjector.trigger_system_hotkey(combo)
                        await ws.send(json.dumps({
                            "type": "system_hotkey_response",
                            "combo": combo,
                            "success": ok,
                            "requires_admin": not is_admin,
                            "message": "Gửi tổ hợp phím SAS (Ctrl+Alt+Del) yêu cầu quyền Quản trị viên (Admin)." if not ok else ""
                        }))
                    else:
                        ok = InputInjector.trigger_system_hotkey(combo)
                        await ws.send(json.dumps({
                            "type": "system_hotkey_response",
                            "combo": combo,
                            "success": ok,
                            "requires_admin": False
                        }))

                # Privacy Curtain Mode (Blank host monitor & block physical input)
                elif ev_type == "toggle_privacy_curtain":
                    enabled = bool(event.get("enabled", False))
                    sess_id = event.get("sessionId") or event.get("session_id") or "default"
                    is_admin = is_current_user_admin()
                    if enabled and not is_admin:
                        logger.warning("[HostService] toggle_privacy_curtain rejected: Administrator privileges required")
                        await ws.send(json.dumps({
                            "type": "privacy_curtain_response",
                            "enabled": False,
                            "activeSessions": list(self.curtain_active_sessions),
                            "success": False,
                            "requires_admin": True,
                            "error": "ADMIN_PRIVILEGES_REQUIRED",
                            "message": "Chế độ màn hình riêng tư yêu cầu quyền Quản trị viên (Admin) trên máy trạm."
                        }))
                        continue

                    if enabled:
                        self.curtain_active_sessions.add(sess_id)
                        res = privacy_curtain.enable()
                        InputInjector.set_block_input(True)
                    else:
                        self.curtain_active_sessions.discard(sess_id)
                        if not self.curtain_active_sessions:
                            res = privacy_curtain.disable()
                            InputInjector.set_block_input(False)
                        else:
                            res = {"success": True, "active": True, "message": "Chế độ riêng tư vẫn duy trì do phiên khác đang yêu cầu."}
                    self.host_config["privacy_curtain"] = bool(privacy_curtain.is_active)
                    await ws.send(json.dumps({
                        "type": "privacy_curtain_response",
                        "enabled": privacy_curtain.is_active,
                        "activeSessions": list(self.curtain_active_sessions),
                        "success": res.get("success", True),
                        "requires_admin": False,
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
                    ping_ts = float(event.get("ts", 0) or 0)
                    if ping_ts > 0:
                        if ping_ts > 1e11:
                            rtt_ms = (time.time() * 1000.0) - ping_ts
                        else:
                            rtt_ms = (time.time() - ping_ts) * 1000.0
                        if 0 < rtt_ms < 5000:
                            self._update_congestion_control(rtt_ms)

    async def start(self):
        self.loop = asyncio.get_running_loop()
        w, h = self.capture.resolution
        os_display = self.get_os_info()
        logger.info(f"Starting Host Agent v{APP_VERSION} for Room [{self.room_id}] (OS: {os_display}, Res: {w}x{h}, Admin: {is_current_user_admin()})")
        if self.host_config.get("keep_awake", True):
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
                        "ping_interval": 25,
                        "ping_timeout": 30,
                        "max_size": 32 * 1024 * 1024,
                        "write_limit": 2 * 1024 * 1024,
                        "compression": None,
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
                        try:
                            tr = getattr(ws, "transport", None)
                            sock = tr.get_extra_info("socket") if tr else None
                            if sock is not None:
                                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                        except Exception:
                            pass
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
                            "os_info": os_display,
                            "is_admin": is_current_user_admin(),
                            "host_config": self.get_host_config_snapshot(),
                            "config": self.get_host_config_snapshot(),
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

                        logger.info(f"Host Registered Successfully! Room: {self.room_id} ({os_display})")
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
                        telemetry_task = asyncio.create_task(self._send_telemetry_loop(ws))

                        done, pending = await asyncio.wait(
                            [capture_task, send_task, audio_task, recv_task, telemetry_task],
                            return_when=asyncio.FIRST_COMPLETED
                        )
                        for t in pending:
                            t.cancel()
                        self.audio_capture.stop()
                        self.audio_playback.stop()
                        self.curtain_active_sessions.clear()
                        privacy_curtain.disable()
                        InputInjector.set_block_input(False)
                        self.has_active_client = False
                        self.frames_in_flight = 0
                        if self.ack_event is not None and not self.ack_event.is_set():
                            self.ack_event.set()
                    await self.tunnel_manager.close_all()

                except (websockets.ConnectionClosed, ConnectionRefusedError, OSError, ssl.SSLError) as e:
                    if not self.running:
                        break
                    err_str = str(e) or type(e).__name__
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
            self.curtain_active_sessions.clear()
            privacy_curtain.disable()
            InputInjector.set_block_input(False)
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


def build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="meikova-host",
        description="Meikova Relay Desktop - High-Performance Cross-Platform Workstation Host Agent (Windows, macOS, Linux)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python host_service.py --relay ws://localhost:8080 --room RD-8888 --pin 123456 --uncapped\n"
            "  python host_service.py --relay wss://meikova-relay.onrender.com --fps 144 --quality 80 --stream-mode adaptive_vfr\n"
            "  python host_service.py --admin --service --stealth --auto-wakeup 08:00\n"
        )
    )
    parser.add_argument("--config", default="", help="Path to custom config.json file")
    parser.add_argument("--relay", default="", help="Relay Server WebSocket URL (e.g., ws://localhost:8080 or wss://...)")
    parser.add_argument("--room", default="", help="Room ID / Session Code (e.g., RD-8888)")
    parser.add_argument("--pin", default="", help="Session or Permanent Access PIN (6 digits)")
    parser.add_argument("--perm-pin", default="", help="Permanent Unattended Access PIN")
    parser.add_argument("--name", default="", help="Workstation Fleet Display Name")
    parser.add_argument("--account", default="", help="Linked Owner Account (email or username)")
    parser.add_argument("--user-id", default="", help="Linked Owner User ID")
    parser.add_argument("--fps", type=int, default=-1, help="Target capture FPS limit (0 = Unlimited/Uncapped, or 30..1000)")
    parser.add_argument("--uncapped", action="store_true", help="Unlock Unlimited FPS (removes frame sleep ceiling)")
    parser.add_argument("--quality", type=int, default=0, help="JPEG compression quality (10-100)")
    parser.add_argument("--preset", default="", help="Initial quality preset (eco, speed_60, balanced, crisp_hd, native_1to1, ultra_120, extreme_144)")
    parser.add_argument("--stream-mode", default="", choices=["", "adaptive_vfr", "continuous_cfr", "low_latency_drop", "adaptive_hybrid", "youtube_smooth", "zero_replay"], help="Frame pacing mode: adaptive_vfr (default), continuous_cfr, or low_latency_drop")
    parser.add_argument("--resolution", default="", help="Target stream resolution lock (e.g., native, 1920x1080, 2560x1440, 1280x720)")
    parser.add_argument("--color-filter", default="", choices=["", "normal", "crisp_text", "night_shield", "high_contrast"], help="Visual display filter & sharpening mode (normal, crisp_text, night_shield, high_contrast)")
    parser.add_argument("--auto-lock-disconnect", action="store_true", help="Automatically lock OS workstation when all remote clients disconnect")
    parser.add_argument("--idle-fps-saver", action="store_true", help="Eco-pace static keepalive frames when session is idle for >15s")
    parser.add_argument("--admin", action="store_true", help="Request UAC Administrator elevation on startup")
    parser.add_argument("--stealth", action="store_true", help="Run in Stealth Mode (hide tray icon and main window)")
    parser.add_argument("--service", action="store_true", help="Install/run as 24/7 System Service (requires Admin)")
    parser.add_argument("--autostart", action="store_true", help="Enable automatic startup on OS login")
    parser.add_argument("--close-to-tray", action="store_true", help="Minimize to system tray when window is closed")
    parser.add_argument("--keep-awake", "--anti-sleep", dest="keep_awake", action="store_true", help="Prevent OS sleep and screen turn-off (Anti-Sleep)")
    parser.add_argument("--no-keep-awake", action="store_true", help="Allow normal OS sleep behavior")
    parser.add_argument("--auto-wakeup", default="", metavar="HH:MM", help="Schedule daily RTC hardware auto-wakeup time (e.g., 08:00, requires Admin)")
    parser.add_argument("--block-input", action="store_true", help="Block physical mouse & keyboard on workstation (requires Admin)")
    parser.add_argument("--curtain", action="store_true", help="Enable Privacy Curtain blank screen mode on startup (requires Admin)")
    parser.add_argument("--install-virtual-audio", action="store_true", help="Download and install VB-Audio Virtual Cable for headless audio")
    parser.add_argument("--install-virtual-display", action="store_true", help="Download and install Microsoft IddCx Virtual Display Driver for headless display")
    parser.add_argument("--probe-protocols", action="store_true", help="Probe and display native protocol negotiation matrix")
    parser.add_argument("--install-deps", action="store_true", help="Check and automatically install all required Python dependencies for the current OS")
    parser.add_argument("--embed-deps", action="store_true", help="Download and embed Python libraries directly into vendor/packages/ inside the source tree")
    parser.add_argument("--download-wheels", action="store_true", help="Download offline .whl installers into vendor/wheels/ inside the source tree")
    parser.add_argument("--no-auto-bootstrap", action="store_true", help="Disable automatic background dependency installation on startup")
    return parser


def main():
    parser = build_cli_parser()
    args = parser.parse_args()

    if getattr(args, "admin", False) and sys.platform == "win32" and not is_current_user_admin():
        forwarded = " ".join(f'"{a}"' if " " in a else a for a in sys.argv[1:] if a != "--admin")
        if elevate_and_execute(forwarded):
            sys.exit(0)

    if getattr(args, "install_deps", False):
        rep = ensure_dependencies(auto_install=True)
        print(json.dumps(rep, indent=2, ensure_ascii=False))
        sys.exit(0)
    if getattr(args, "embed_deps", False):
        rep = install_into_vendor_packages()
        print(json.dumps(rep, indent=2, ensure_ascii=False))
        sys.exit(0 if rep.get("success") else 1)
    if getattr(args, "download_wheels", False):
        rep = download_wheelhouse()
        print(json.dumps(rep, indent=2, ensure_ascii=False))
        sys.exit(0 if rep.get("success") else 1)
    if not getattr(args, "no_auto_bootstrap", False):
        ensure_dependencies(auto_install=True, quiet=True)
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
    pin = args.pin or args.perm_pin or cfg_data.get("pin") or "123456"
    device_name = args.name or cfg_data.get("device_name") or os.environ.get("COMPUTERNAME", socket.gethostname())
    account = args.account or cfg_data.get("account") or ""
    user_id = args.user_id or cfg_data.get("user_id") or None
    if args.uncapped or args.fps == 0:
        fps = 0
    elif args.fps > 0:
        fps = args.fps
    else:
        fps = int(cfg_data.get("fps", 120))
    quality = args.quality if args.quality > 0 else int(cfg_data.get("quality", 70))
    stream_mode = args.stream_mode or cfg_data.get("stream_mode") or "adaptive_vfr"
    color_filter = getattr(args, "color_filter", "") or cfg_data.get("color_filter") or "normal"
    auto_lock_disc = bool(getattr(args, "auto_lock_disconnect", False) or cfg_data.get("auto_lock_on_disconnect", False))
    idle_saver = bool(getattr(args, "idle_fps_saver", False) or cfg_data.get("idle_fps_saver", False))

    host_cfg = {
        "keep_awake": False if args.no_keep_awake else bool(args.keep_awake or cfg_data.get("keep_awake", True)),
        "auto_wakeup": bool(args.auto_wakeup or cfg_data.get("auto_wakeup", False)),
        "auto_wakeup_time": str(args.auto_wakeup or cfg_data.get("auto_wakeup_time", "08:00")),
        "stealth_mode": bool(args.stealth or cfg_data.get("stealth_mode", False)),
        "service_mode": bool(args.service or cfg_data.get("service_mode", False)),
        "autostart": bool(args.autostart or cfg_data.get("autostart", False)),
        "close_to_tray": bool(args.close_to_tray or cfg_data.get("close_to_tray", True)),
        "show_tray_icon": not bool(args.stealth or cfg_data.get("stealth_mode", False)),
        "block_input": bool(args.block_input or cfg_data.get("block_input", False)),
        "privacy_curtain": bool(args.curtain or cfg_data.get("privacy_curtain", False)),
        "stream_mode": stream_mode,
        "color_filter": color_filter,
        "auto_lock_on_disconnect": auto_lock_disc,
        "idle_fps_saver": idle_saver,
    }

    service = HostService(
        relay_url=relay_url,
        room_id=room_id,
        pin=pin,
        device_name=device_name,
        account=account,
        user_id=user_id,
        fps=fps,
        quality=quality,
        host_config=host_cfg,
        stream_mode=stream_mode,
        color_filter=color_filter,
        auto_lock_on_disconnect=auto_lock_disc,
        idle_fps_saver=idle_saver,
    )
    if getattr(args, "resolution", ""):
        res_str = str(args.resolution).strip().lower()
        if res_str == "native":
            service.custom_resolution_lock = service.capture.resolution
            service.capture.max_width = None
        elif "x" in res_str:
            try:
                rw, rh = [int(x) for x in res_str.split("x", 1)]
                if rw > 0 and rh > 0:
                    service.custom_resolution_lock = (rw, rh)
                    service.capture.set_custom_resolution(rw, rh)
                    service.capture.max_width = rw
            except Exception:
                pass
    if args.preset:
        service.apply_quality_preset(args.preset)
    if host_cfg["auto_wakeup"] and is_current_user_admin():
        PowerManager.configure_auto_wakeup(True, host_cfg["auto_wakeup_time"])
    if host_cfg["block_input"] and is_current_user_admin():
        InputInjector.set_block_input(True)
    if host_cfg["privacy_curtain"] and is_current_user_admin():
        privacy_curtain.enable()

    try:
        asyncio.run(service.start())
    except KeyboardInterrupt:
        logger.info("Host Agent stopped by user.")


if __name__ == "__main__":
    main()

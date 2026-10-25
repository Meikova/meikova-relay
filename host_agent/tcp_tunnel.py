"""
TCP Tunnel Manager for Meikova Relay.
Multiplexes local TCP services (RDP 3389, SSH 22, VNC 5900) over WebSocket.
Enables Zero-Port-Forwarding remote access across NAT / Firewalls.
// ponytail: stdlib asyncio streams + base64 chunking, zero external dependencies.
"""

import asyncio
import base64
import logging
from typing import Dict, Optional, Callable, Any

logger = logging.getLogger("TcpTunnel")

DEFAULT_PROTOCOL_PORTS = {
    "rdp": 3389,
    "ssh": 22,
    "vnc": 5900,
    "ftp": 21,
    "sftp": 22
}

class TunnelSession:
    """Represents an active TCP socket bridge to a local service."""

    def __init__(self, tunnel_id: str, protocol: str, target_port: int,
                 reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
                 on_data: Callable[[str, bytes], Any], on_close: Callable[[str], Any]):
        self.tunnel_id = tunnel_id
        self.protocol = protocol
        self.target_port = target_port
        self.reader = reader
        self.writer = writer
        self.on_data = on_data
        self.on_close = on_close
        self.is_active = True
        self._read_task: Optional[asyncio.Task] = None

    def start(self):
        """Starts background reader loop."""
        self._read_task = asyncio.create_task(self._reader_loop())

    async def _reader_loop(self):
        """Reads chunks from local TCP service and dispatches to WebSocket sender."""
        try:
            while self.is_active:
                chunk = await self.reader.read(32768)
                if not chunk:
                    # Remote service closed TCP connection
                    break
                await self.on_data(self.tunnel_id, chunk)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug(f"[Tunnel {self.tunnel_id}] Read error: {e}")
        finally:
            await self.close()

    async def write(self, data: bytes):
        """Writes data from WebSocket client into local TCP socket."""
        if not self.is_active or not self.writer:
            return
        try:
            self.writer.write(data)
            await self.writer.drain()
        except Exception as e:
            logger.debug(f"[Tunnel {self.tunnel_id}] Write error: {e}")
            await self.close()

    async def close(self):
        """Gracefully closes socket and cleans up task."""
        if not self.is_active:
            return
        self.is_active = False
        if self._read_task and not self._read_task.done():
            self._read_task.cancel()
        try:
            if self.writer:
                self.writer.close()
                await self.writer.wait_closed()
        except Exception:
            pass
        if self.on_close:
            try:
                res = self.on_close(self.tunnel_id)
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                pass


class TcpTunnelManager:
    """Manages active multiplexed TCP tunnel sessions over WebSocket."""

    def __init__(self, send_ws_fn: Callable[[dict], Any], host: str = "127.0.0.1"):
        self.send_ws = send_ws_fn
        self.host = host
        self.sessions: Dict[str, TunnelSession] = {}

    async def open_tunnel(self, tunnel_id: str, protocol: str, port: Optional[int] = None) -> bool:
        """Opens a local TCP connection to target protocol port."""
        if not port:
            port = DEFAULT_PROTOCOL_PORTS.get(protocol.lower(), 3389)

        # Close existing tunnel with same ID if any
        if tunnel_id in self.sessions:
            await self.sessions[tunnel_id].close()

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, port),
                timeout=3.0
            )
            session = TunnelSession(
                tunnel_id=tunnel_id,
                protocol=protocol,
                target_port=port,
                reader=reader,
                writer=writer,
                on_data=self._on_local_data,
                on_close=self._on_session_closed
            )
            self.sessions[tunnel_id] = session
            session.start()

            logger.info(f"[TcpTunnel] Opened tunnel {tunnel_id} -> {self.host}:{port} ({protocol.upper()})")
            await self.send_ws({
                "type": "tunnel_opened",
                "tunnel_id": tunnel_id,
                "protocol": protocol,
                "port": port,
                "status": "ready"
            })
            return True
        except Exception as e:
            logger.warning(f"[TcpTunnel] Failed to open tunnel {tunnel_id} -> {self.host}:{port}: {e}")
            await self.send_ws({
                "type": "tunnel_error",
                "tunnel_id": tunnel_id,
                "protocol": protocol,
                "error": str(e)
            })
            await self.send_ws({
                "type": "tunnel_closed",
                "tunnel_id": tunnel_id
            })
            return False

    async def handle_open(self, tunnel_id: str, port: int, protocol: str = "tcp") -> bool:
        """Alias for open_tunnel with (tunnel_id, port, protocol) signature."""
        return await self.open_tunnel(tunnel_id, protocol, port)

    async def handle_close(self, tunnel_id: str):
        """Alias for close_tunnel."""
        await self.close_tunnel(tunnel_id)

    @property
    def _tunnels(self):
        """Backward-compatible alias for self.sessions."""
        return self.sessions

    async def handle_data(self, tunnel_id: str, data_b64: str):
        """Dispatches data received from WebSocket into TCP socket."""
        session = self.sessions.get(tunnel_id)
        if not session or not session.is_active:
            return
        try:
            raw_bytes = base64.b64decode(data_b64)
            await session.write(raw_bytes)
        except Exception as e:
            logger.debug(f"[TcpTunnel] handle_data decode/write error: {e}")

    async def close_tunnel(self, tunnel_id: str):
        """Closes a specific tunnel."""
        session = self.sessions.pop(tunnel_id, None)
        if session:
            await session.close()
            await self.send_ws({
                "type": "tunnel_closed",
                "tunnel_id": tunnel_id
            })

    async def close_all(self):
        """Closes all active tunnels."""
        active = list(self.sessions.values())
        self.sessions.clear()
        for session in active:
            try:
                await session.close()
            except Exception:
                pass

    async def _on_local_data(self, tunnel_id: str, data: bytes):
        """Sends data chunk read from local TCP socket over WebSocket."""
        try:
            b64_str = base64.b64encode(data).decode("ascii")
            await self.send_ws({
                "type": "tunnel_data",
                "tunnel_id": tunnel_id,
                "data": b64_str
            })
        except Exception as e:
            logger.debug(f"[TcpTunnel] _on_local_data send error: {e}")

    def _on_session_closed(self, tunnel_id: str):
        """Handles local session closure callback."""
        self.sessions.pop(tunnel_id, None)

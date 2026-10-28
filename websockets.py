"""
Lightweight Pure-Python AsyncIO RFC 6455 WebSocket Client (`websockets` compatibility layer).
Used automatically when the third-party `websockets` package is not installed in the Python environment,
providing full compatibility for `websockets.connect()`, `ws.send()`, `ws.recv()`, `ws.close()`,
async context managers, async iteration, and `websockets.ConnectionClosed`.
"""

import asyncio
import base64
import os
import ssl
import struct
import urllib.parse


class ConnectionClosed(Exception):
    def __init__(self, code: int = 1000, reason: str = ""):
        self.code = code
        self.reason = reason
        super().__init__(f"WebSocket connection closed (code={code}, reason={reason})")


class ConnectionClosedOK(ConnectionClosed):
    pass


class ConnectionClosedError(ConnectionClosed):
    pass


class WebSocketClientProtocol:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self._reader = reader
        self._writer = writer
        self.closed = False
        self.close_code = None
        self.close_reason = ""
        self._recv_queue = asyncio.Queue()
        self._reader_task = asyncio.create_task(self._read_loop())

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return await self.recv()
        except ConnectionClosed:
            raise StopAsyncIteration

    async def _read_exact(self, n: int) -> bytes:
        return await self._reader.readexactly(n)

    async def _read_loop(self):
        fragments = []
        frag_opcode = None
        try:
            while not self.closed:
                hdr = await self._read_exact(2)
                b0, b1 = hdr[0], hdr[1]
                fin = bool(b0 & 0x80)
                opcode = b0 & 0x0F
                masked = bool(b1 & 0x80)
                length = b1 & 0x7F

                if length == 126:
                    ext = await self._read_exact(2)
                    length = struct.unpack("!H", ext)[0]
                elif length == 127:
                    ext = await self._read_exact(8)
                    length = struct.unpack("!Q", ext)[0]

                mask_key = await self._read_exact(4) if masked else None
                payload = await self._read_exact(length) if length > 0 else b""
                if masked and mask_key:
                    payload = bytes(b ^ mask_key[i & 3] for i, b in enumerate(payload))

                if opcode == 0x8:  # CLOSE
                    code = 1000
                    reason = ""
                    if len(payload) >= 2:
                        code = struct.unpack("!H", payload[:2])[0]
                        reason = payload[2:].decode("utf-8", errors="replace")
                    self.close_code = code
                    self.close_reason = reason
                    self.closed = True
                    try:
                        self._writer.close()
                    except Exception:
                        pass
                    await self._recv_queue.put(ConnectionClosed(code, reason))
                    break
                elif opcode == 0x9:  # PING
                    await self._send_frame(0xA, payload)
                elif opcode == 0xA:  # PONG
                    continue
                elif opcode in (0x1, 0x2):
                    if fin and not fragments:
                        item = payload.decode("utf-8", errors="replace") if opcode == 0x1 else payload
                        await self._recv_queue.put(item)
                    else:
                        frag_opcode = opcode
                        fragments.append(payload)
                        if fin:
                            full = b"".join(fragments)
                            fragments.clear()
                            item = full.decode("utf-8", errors="replace") if frag_opcode == 0x1 else full
                            await self._recv_queue.put(item)
                elif opcode == 0x0:
                    fragments.append(payload)
                    if fin and frag_opcode is not None:
                        full = b"".join(fragments)
                        fragments.clear()
                        item = full.decode("utf-8", errors="replace") if frag_opcode == 0x1 else full
                        frag_opcode = None
                        await self._recv_queue.put(item)
        except (asyncio.IncompleteReadError, ConnectionError, OSError) as e:
            self.closed = True
            if self.close_code is None:
                self.close_code = 1006
            try:
                self._writer.close()
            except Exception:
                pass
            await self._recv_queue.put(ConnectionClosed(self.close_code or 1006, str(e)))
        except asyncio.CancelledError:
            pass

    async def _send_frame(self, opcode: int, payload: bytes):
        if self.closed:
            raise ConnectionClosed(self.close_code or 1000, self.close_reason)
        mask_key = os.urandom(4)
        length = len(payload)
        header = bytearray([0x80 | (opcode & 0x0F)])
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        header.extend(mask_key)
        masked_payload = bytes(b ^ mask_key[i & 3] for i, b in enumerate(payload))
        self._writer.write(bytes(header) + masked_payload)
        await self._writer.drain()

    async def send(self, data):
        if isinstance(data, str):
            await self._send_frame(0x1, data.encode("utf-8"))
        elif isinstance(data, (bytes, bytearray, memoryview)):
            await self._send_frame(0x2, bytes(data))
        else:
            await self._send_frame(0x1, str(data).encode("utf-8"))

    async def recv(self):
        item = await self._recv_queue.get()
        if isinstance(item, ConnectionClosed):
            raise item
        return item

    async def close(self, code: int = 1000, reason: str = ""):
        if not self.closed:
            try:
                payload = struct.pack("!H", code) + reason.encode("utf-8")
                await self._send_frame(0x8, payload)
            except Exception:
                pass
            self.closed = True
        if self._reader_task and not self._reader_task.done():
            self._reader_task.cancel()
            try:
                await self._reader_task
            except BaseException:
                pass
        try:
            self._writer.close()
            await self._writer.wait_closed()
        except Exception:
            pass


class _ConnectContext:
    def __init__(self, uri: str, **kwargs):
        self.uri = uri
        self.kwargs = kwargs
        self.protocol = None

    async def _establish(self) -> WebSocketClientProtocol:
        parsed = urllib.parse.urlparse(self.uri)
        is_secure = parsed.scheme == "wss"
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or (443 if is_secure else 80)
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query

        ssl_ctx = self.kwargs.get("ssl")
        if is_secure and ssl_ctx is None:
            ssl_ctx = ssl.create_default_context()

        reader, writer = await asyncio.open_connection(host, port, ssl=ssl_ctx)
        ws_key = base64.b64encode(os.urandom(16)).decode("ascii")
        req_lines = [
            f"GET {path} HTTP/1.1",
            f"Host: {host}:{port}",
            "Upgrade: websocket",
            "Connection: Upgrade",
            f"Sec-WebSocket-Key: {ws_key}",
            "Sec-WebSocket-Version: 13",
            "\r\n",
        ]
        writer.write("\r\n".join(req_lines).encode("ascii"))
        await writer.drain()

        status_line = await reader.readline()
        if not status_line or b"101" not in status_line:
            writer.close()
            raise ConnectionError(f"WebSocket handshake failed: {status_line.decode('ascii', errors='replace').strip()}")

        while True:
            line = await reader.readline()
            if not line or line in (b"\r\n", b"\n"):
                break

        self.protocol = WebSocketClientProtocol(reader, writer)
        return self.protocol

    def __await__(self):
        return self._establish().__await__()

    async def __aenter__(self) -> WebSocketClientProtocol:
        return await self._establish()

    async def __aexit__(self, exc_type, exc, tb):
        if self.protocol:
            await self.protocol.close()


def connect(uri: str, **kwargs) -> _ConnectContext:
    return _ConnectContext(uri, **kwargs)

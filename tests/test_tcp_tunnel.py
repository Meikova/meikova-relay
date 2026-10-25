"""
Unit tests for host_agent/tcp_tunnel.py.
Tests async TCP socket tunneling over simulated WebSocket messages.
"""

import os
import sys
import asyncio
import base64
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from host_agent.tcp_tunnel import TcpTunnelManager

class TestTcpTunnel(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.sent_messages = []

        async def mock_send(msg: dict):
            self.sent_messages.append(msg)

        self.mock_send = mock_send
        self.manager = TcpTunnelManager(send_ws_fn=self.mock_send, host="127.0.0.1")

        # Start a local TCP echo server for testing
        async def echo_handler(reader, writer):
            try:
                while True:
                    data = await reader.read(1024)
                    if not data:
                        break
                    writer.write(data)
                    await writer.drain()
            except asyncio.CancelledError:
                pass
            finally:
                writer.close()
                await writer.wait_closed()

        self.server = await asyncio.start_server(echo_handler, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        await self.manager.close_all()
        self.server.close()
        await self.server.wait_closed()

    async def test_open_tunnel_success(self):
        """Tests that handle_open successfully connects to a local TCP port."""
        res = await self.manager.handle_open("tun-1", self.port)
        self.assertTrue(res)
        self.assertIn("tun-1", self.manager._tunnels)

        # Verify open confirmation sent via ws
        opened_msg = [m for m in self.sent_messages if m.get("type") == "tunnel_opened" and m.get("tunnel_id") == "tun-1"]
        self.assertEqual(len(opened_msg), 1)

    async def test_open_tunnel_unreachable_port(self):
        """Tests handle_open when target port is closed."""
        # Port 59997 likely closed
        res = await self.manager.handle_open("tun-fail", 59997)
        self.assertFalse(res)
        self.assertNotIn("tun-fail", self.manager._tunnels)

        # Verify close/error notification sent via ws
        closed_msg = [m for m in self.sent_messages if m.get("type") == "tunnel_closed" and m.get("tunnel_id") == "tun-fail"]
        self.assertEqual(len(closed_msg), 1)

    async def test_tunnel_data_echo_roundtrip(self):
        """Tests sending data into tunnel and receiving echo from TCP server."""
        await self.manager.handle_open("tun-echo", self.port)

        payload = b"Hello, Meikova TCP Tunnel!"
        b64_payload = base64.b64encode(payload).decode("ascii")

        await self.manager.handle_data("tun-echo", b64_payload)

        # Wait briefly for echo data callback
        for _ in range(50):
            echo_msgs = [m for m in self.sent_messages if m.get("type") == "tunnel_data" and m.get("tunnel_id") == "tun-echo"]
            if echo_msgs:
                received_b64 = echo_msgs[0]["data"]
                self.assertEqual(base64.b64decode(received_b64), payload)
                break
            await asyncio.sleep(0.02)
        else:
            self.fail("Timed out waiting for tunnel_data echo")

    async def test_close_tunnel(self):
        """Tests closing an active tunnel."""
        await self.manager.handle_open("tun-close", self.port)
        self.assertIn("tun-close", self.manager._tunnels)

        await self.manager.handle_close("tun-close")
        self.assertNotIn("tun-close", self.manager._tunnels)

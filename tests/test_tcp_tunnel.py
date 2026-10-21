"""
Unit tests for host_agent/tcp_tunnel.py.
Tests async TCP socket tunneling over simulated WebSocket messages.
"""

import asyncio
import base64
import unittest
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
            except Exception:
                pass
            finally:
                writer.close()
                await writer.wait_closed()

        self.server = await asyncio.start_server(echo_handler, "127.0.0.1", 0)
        self.echo_port = self.server.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        await self.manager.close_all()
        self.server.close()
        await self.server.wait_closed()

    async def test_open_tunnel_success(self):
        res = await self.manager.open_tunnel("tun-1", "rdp", port=self.echo_port)
        self.assertTrue(res)
        self.assertIn("tun-1", self.manager.sessions)

        opened_msgs = [m for m in self.sent_messages if m.get("type") == "tunnel_opened"]
        self.assertEqual(len(opened_msgs), 1)
        self.assertEqual(opened_msgs[0]["tunnel_id"], "tun-1")
        self.assertEqual(opened_msgs[0]["port"], self.echo_port)

    async def test_open_tunnel_unreachable_port(self):
        # Port 59997 should be closed
        res = await self.manager.open_tunnel("tun-fail", "ssh", port=59997)
        self.assertFalse(res)
        error_msgs = [m for m in self.sent_messages if m.get("type") == "tunnel_error"]
        self.assertEqual(len(error_msgs), 1)
        self.assertEqual(error_msgs[0]["tunnel_id"], "tun-fail")

    async def test_tunnel_data_echo_roundtrip(self):
        await self.manager.open_tunnel("tun-echo", "rdp", port=self.echo_port)
        test_payload = b"HELLO_MEIKOVA_RDP_TUNNEL_12345"
        b64_in = base64.b64encode(test_payload).decode("ascii")

        # Send data into tunnel
        await self.manager.handle_data("tun-echo", b64_in)

        # Wait briefly for echo server to respond and trigger _on_local_data
        for _ in range(20):
            await asyncio.sleep(0.05)
            echo_msgs = [m for m in self.sent_messages if m.get("type") == "tunnel_data"]
            if echo_msgs:
                break

        echo_msgs = [m for m in self.sent_messages if m.get("type") == "tunnel_data"]
        self.assertTrue(len(echo_msgs) >= 1)
        received_bytes = base64.b64decode(echo_msgs[0]["data"])
        self.assertEqual(received_bytes, test_payload)

    async def test_close_tunnel(self):
        await self.manager.open_tunnel("tun-close", "ssh", port=self.echo_port)
        self.assertIn("tun-close", self.manager.sessions)
        await self.manager.close_tunnel("tun-close")
        self.assertNotIn("tun-close", self.manager.sessions)

        close_msgs = [m for m in self.sent_messages if m.get("type") == "tunnel_closed"]
        self.assertEqual(len(close_msgs), 1)
        self.assertEqual(close_msgs[0]["tunnel_id"], "tun-close")

if __name__ == "__main__":
    unittest.main()

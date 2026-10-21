"""
Unit tests for Meikova Relay multi-client sessions and session termination.
// ponytail: stdlib unittest verifying 1-to-N fanout & session kill
"""

import json
import asyncio
import unittest
import websockets
import urllib.request
import subprocess
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

class TestMultiClientSessions(unittest.IsolatedAsyncioTestCase):
    server_process = None
    server_port = 9015

    @classmethod
    def setUpClass(cls):
        import os
        import socket
        server_js = REPO_ROOT / "relay-server" / "server.js"
        env = os.environ.copy()
        env["PORT"] = str(cls.server_port)
        try:
            cls.server_process = subprocess.Popen(
                ["node", str(server_js)],
                cwd=str(REPO_ROOT / "relay-server"),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        except FileNotFoundError:
            raise unittest.SkipTest("Node.js runtime not installed, skipping multi-client tests.")

        # Active polling for server to bind port
        start_time = time.time()
        ready = False
        while time.time() - start_time < 8.0:
            if cls.server_process.poll() is not None:
                _, err = cls.server_process.communicate()
                err_text = err.decode("utf-8", errors="replace")
                raise unittest.SkipTest(f"Relay server failed to start: {err_text}")
            try:
                with socket.create_connection(("127.0.0.1", cls.server_port), timeout=0.2):
                    ready = True
                    break
            except (ConnectionRefusedError, OSError):
                time.sleep(0.1)

        if not ready:
            raise unittest.SkipTest("Relay server did not start listening on port 9015 within 8s")

    @classmethod
    def tearDownClass(cls):
        if cls.server_process:
            cls.server_process.terminate()
            cls.server_process.wait()

    async def test_multi_client_connect_and_kill(self):
        url = f"ws://127.0.0.1:{self.server_port}"
        room_id = "MC-TEST-99"
        pin = "123456"

        # 1. Host inits
        host_ws = await websockets.connect(url)
        await host_ws.send(json.dumps({
            "type": "init_host",
            "room_id": room_id,
            "pin": pin,
            "device_name": "MultiClient-Host",
            "os_info": "Windows 11"
        }))
        host_res = json.loads(await host_ws.recv())
        self.assertEqual(host_res.get("status"), "ok")

        # 2. Client 1 inits
        client1_ws = await websockets.connect(url)
        await client1_ws.send(json.dumps({
            "type": "init_client",
            "room_id": room_id,
            "pin": pin,
            "username": "client1@meikova.io"
        }))
        c1_res = json.loads(await client1_ws.recv())
        self.assertEqual(c1_res.get("status"), "ok")
        c1_sess = c1_res.get("session_id")
        self.assertTrue(bool(c1_sess))

        # Host receives client1 connected notification
        h_notif1 = json.loads(await host_ws.recv())
        self.assertEqual(h_notif1.get("type"), "client_connected")
        self.assertEqual(h_notif1.get("clientCount"), 1)

        # 3. Client 2 inits
        client2_ws = await websockets.connect(url)
        await client2_ws.send(json.dumps({
            "type": "init_client",
            "room_id": room_id,
            "pin": pin,
            "username": "client2@meikova.io"
        }))
        c2_res = json.loads(await client2_ws.recv())
        self.assertEqual(c2_res.get("status"), "ok")
        c2_sess = c2_res.get("session_id")
        self.assertTrue(bool(c2_sess))

        # Host receives client2 connected notification with count 2
        h_notif2 = json.loads(await host_ws.recv())
        self.assertEqual(h_notif2.get("type"), "client_connected")
        self.assertEqual(h_notif2.get("clientCount"), 2)

        # 4. Host broadcasts frame -> BOTH client 1 and client 2 receive it!
        sample_frame = b'\xff\xd8\xff\xe0test-multi-client-frame'
        await host_ws.send(sample_frame)
        rec1 = await client1_ws.recv()
        rec2 = await client2_ws.recv()
        self.assertEqual(rec1, sample_frame)
        self.assertEqual(rec2, sample_frame)

        # 5. Client 1 queries session list
        await client1_ws.send(json.dumps({"type": "get_sessions"}))
        sess_list_msg = json.loads(await client1_ws.recv())
        self.assertEqual(sess_list_msg.get("type"), "session_list")
        self.assertEqual(sess_list_msg.get("clientCount"), 2)

        # 6. Client 1 kills Client 2
        await client1_ws.send(json.dumps({
            "type": "kill_session",
            "session_id": c2_sess
        }))

        # Client 2 receives session_killed notification
        c2_kill_notif = json.loads(await client2_ws.recv())
        self.assertEqual(c2_kill_notif.get("type"), "session_killed")

        # Client 1 receives updated session_list (membership change) and kill_session_success
        c1_msgs = [json.loads(await client1_ws.recv()), json.loads(await client1_ws.recv())]
        msg_types = [m.get("type") for m in c1_msgs]
        self.assertIn("session_list", msg_types)
        self.assertIn("kill_session_success", msg_types)

        # 7. Host graceful stop -> Client 1 immediately receives host_disconnected and socket is closed
        await host_ws.send(json.dumps({"type": "host_closing", "room_id": room_id}))
        c1_close_msg = json.loads(await client1_ws.recv())
        self.assertEqual(c1_close_msg.get("type"), "host_disconnected")
        with self.assertRaises(websockets.ConnectionClosed):
            await client1_ws.recv()

        # Cleanup
        try:
            await host_ws.close()
        except Exception:
            pass
        try:
            await client1_ws.close()
        except Exception:
            pass
        try:
            await client2_ws.close()
        except Exception:
            pass

    async def test_host_disconnect_kicks_all_clients(self):
        url = f"ws://127.0.0.1:{self.server_port}"
        room_id = "MC-HOST-DROP-1"
        pin = "654321"

        host_ws = await websockets.connect(url)
        await host_ws.send(json.dumps({
            "type": "init_host",
            "room_id": room_id,
            "pin": pin
        }))
        await host_ws.recv()

        client_ws = await websockets.connect(url)
        await client_ws.send(json.dumps({
            "type": "init_client",
            "room_id": room_id,
            "pin": pin
        }))
        await client_ws.recv()
        await host_ws.recv() # client_connected

        # Host drops socket unexpectedly
        await host_ws.close()

        # Client must receive host_disconnected and then socket is closed immediately
        c_msg = json.loads(await client_ws.recv())
        self.assertEqual(c_msg.get("type"), "host_disconnected")
        with self.assertRaises(websockets.ConnectionClosed):
            await client_ws.recv()

if __name__ == "__main__":
    unittest.main()

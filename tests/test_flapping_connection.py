"""
Unit tests for host connection stability, superseded host replacement, and SingleInstanceLock.
// ponytail: stdlib unittest verifying no flapping, ghost session prevention, and single-instance mutex
"""

import json
import asyncio
import unittest
import tempfile
import uuid
import websockets
import subprocess
import time
import sys
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

class TestFlappingAndSuperseded(unittest.IsolatedAsyncioTestCase):
    server_process = None
    temp_db_path = None
    server_port = 9022

    @classmethod
    def setUpClass(cls):
        import socket
        server_js = REPO_ROOT / "relay-server" / "server.js"
        env = os.environ.copy()
        cls.temp_db_path = str(Path(tempfile.gettempdir()) / f"test_relay_flap_{uuid.uuid4().hex[:8]}.db")
        env["PORT"] = str(cls.server_port)
        env["DB_PATH"] = cls.temp_db_path
        try:
            cls.server_process = subprocess.Popen(
                ["node", str(server_js)],
                cwd=str(REPO_ROOT / "relay-server"),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        except FileNotFoundError:
            raise unittest.SkipTest("Node.js runtime not installed, skipping test.")

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
            raise unittest.SkipTest(f"Relay server did not start on port {cls.server_port} within 8s")

    @classmethod
    def tearDownClass(cls):
        if cls.server_process:
            cls.server_process.terminate()
            try:
                cls.server_process.wait(timeout=2.0)
            except Exception:
                cls.server_process.kill()
        if cls.temp_db_path and os.path.exists(cls.temp_db_path):
            try:
                os.remove(cls.temp_db_path)
            except Exception:
                pass

    async def test_superseded_host_does_not_offline_room(self):
        """When host 1 is superseded by host 2, closing host 1 must NOT set room offline or kick client."""
        room_id = f"RD-{uuid.uuid4().hex[:4].upper()}"
        pin = "123456"
        uri = f"ws://127.0.0.1:{self.server_port}"

        # 1. Host 1 connects
        ws_host1 = await websockets.connect(uri)
        await ws_host1.send(json.dumps({
            "type": "init_host",
            "room_id": room_id,
            "pin": pin,
            "width": 1920,
            "height": 1080,
            "device_name": "Host-1"
        }))
        ack1 = json.loads(await ws_host1.recv())
        self.assertEqual(ack1.get("status"), "ok")

        # 2. Host 2 connects with the same room_id (reconnect or instance overlap)
        ws_host2 = await websockets.connect(uri)
        await ws_host2.send(json.dumps({
            "type": "init_host",
            "room_id": room_id,
            "pin": pin,
            "width": 1920,
            "height": 1080,
            "device_name": "Host-2"
        }))
        ack2 = json.loads(await ws_host2.recv())
        self.assertEqual(ack2.get("status"), "ok")

        # 3. Host 1 should receive superseded packet or socket close
        try:
            msg_host1 = await asyncio.wait_for(ws_host1.recv(), timeout=1.0)
            parsed_h1 = json.loads(msg_host1)
            self.assertEqual(parsed_h1.get("type"), "superseded")
        except (websockets.ConnectionClosed, asyncio.TimeoutError):
            pass
        finally:
            await ws_host1.close()

        # Brief pause to ensure host1 close event has fired on server
        await asyncio.sleep(0.2)

        # 4. Client connects - MUST succeed because Host 2 is active!
        ws_client = await websockets.connect(uri)
        await ws_client.send(json.dumps({
            "type": "init_client",
            "room_id": room_id,
            "pin": pin,
            "username": "Operator"
        }))
        client_ack = json.loads(await ws_client.recv())
        self.assertEqual(client_ack.get("status"), "ok", f"Client failed with {client_ack}")
        self.assertEqual(client_ack.get("role"), "client")

        await ws_client.close()
        await ws_host2.close()

    def test_single_instance_lock(self):
        """SingleInstanceLock must allow exactly one instance at a time."""
        from host_agent.gui_agent import SingleInstanceLock
        lock1 = SingleInstanceLock(f"Test_Mutex_{uuid.uuid4().hex[:6]}")
        self.assertTrue(lock1.acquire(), "First lock acquisition must succeed")

        lock2 = SingleInstanceLock(lock1.name)
        self.assertFalse(lock2.acquire(), "Second lock acquisition on same mutex must fail")

        lock1.release()
        self.assertTrue(lock2.acquire(), "Acquisition must succeed after first lock is released")
        lock2.release()

if __name__ == "__main__":
    unittest.main()

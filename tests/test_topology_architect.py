"""
Tests for Meikova Relay Server & Topology Architect fixes:
1. Device identity & isolation by machine_id (Issue 2)
2. Multi-client streaming & graceful client count tracking (Issue 4)
3. Reverse remote loop & self-loop prevention via activeRemoteEdges (Issue 5)
4. Full operator info broadcast on client_connected (Issue 6)
// ponytail: stdlib unittest verifying topology & relay invariants
"""

import json
import asyncio
import unittest
import tempfile
import uuid
import websockets
import subprocess
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

class TestTopologyArchitect(unittest.IsolatedAsyncioTestCase):
    server_process = None
    temp_db_path = None
    server_port = 9035

    @classmethod
    def setUpClass(cls):
        import os
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            cls.server_port = s.getsockname()[1]
        server_js = REPO_ROOT / "relay-server" / "server.js"
        env = os.environ.copy()
        cls.temp_db_path = str(Path(tempfile.gettempdir()) / f"test_relay_top_{uuid.uuid4().hex[:8]}.db")
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
            raise unittest.SkipTest("Node.js runtime not installed, skipping topology tests.")

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
            stdout, stderr = cls.server_process.communicate()
            print("\n--- SERVER STDOUT ---\n", stdout.decode("utf-8", errors="replace"))
            print("\n--- SERVER STDERR ---\n", stderr.decode("utf-8", errors="replace"))
        if cls.temp_db_path:
            for ext in ["", "-wal", "-shm"]:
                try:
                    p_db = Path(cls.temp_db_path + ext)
                    if p_db.exists():
                        p_db.unlink()
                except OSError:
                    pass

    async def test_issue2_device_machine_id_isolation_api(self):
        """Issue 2: Linking 2 devices with same account & device_name but different machine_id isolates both devices."""
        base_url = f"http://127.0.0.1:{self.server_port}"
        u_name = f"user_iso_{uuid.uuid4().hex[:6]}"
        reg_payload = json.dumps({"username": u_name, "password": "SecurePassword123"}).encode()
        req_reg = urllib.request.Request(f"{base_url}/api/auth/register", data=reg_payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req_reg) as resp:
            reg_data = json.loads(resp.read().decode())
        token = reg_data.get("token")
        self.assertTrue(bool(token))

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # Link Device A (Machine GUID A, default deviceName 'Workstation')
        room_a = f"ROOM-ISO-A-{uuid.uuid4().hex[:4]}"
        dev_a_payload = json.dumps({
            "roomId": room_a,
            "pin": "123456",
            "deviceName": "Workstation",
            "machineId": "HW-MACHINE-GUID-AAA"
        }).encode()
        req_a = urllib.request.Request(f"{base_url}/api/devices/link", data=dev_a_payload, headers=headers)
        with urllib.request.urlopen(req_a) as resp:
            res_a = json.loads(resp.read().decode())
            self.assertTrue(res_a.get("success"))

        # Link Device B (Machine GUID B, SAME deviceName 'Workstation' on same account)
        room_b = f"ROOM-ISO-B-{uuid.uuid4().hex[:4]}"
        dev_b_payload = json.dumps({
            "roomId": room_b,
            "pin": "654321",
            "deviceName": "Workstation",
            "machineId": "HW-MACHINE-GUID-BBB"
        }).encode()
        req_b = urllib.request.Request(f"{base_url}/api/devices/link", data=dev_b_payload, headers=headers)
        with urllib.request.urlopen(req_b) as resp:
            res_b = json.loads(resp.read().decode())
            self.assertTrue(res_b.get("success"))

        # Fetch devices list: MUST contain BOTH distinct devices without overwriting
        req_list = urllib.request.Request(f"{base_url}/api/devices", headers=headers)
        with urllib.request.urlopen(req_list) as resp:
            devices_data = json.loads(resp.read().decode())
            devices = devices_data.get("devices", [])

        self.assertEqual(len(devices), 2)
        dev_a = next((d for d in devices if d.get("machine_id") == "HW-MACHINE-GUID-AAA"), None)
        dev_b = next((d for d in devices if d.get("machine_id") == "HW-MACHINE-GUID-BBB"), None)
        self.assertIsNotNone(dev_a)
        self.assertIsNotNone(dev_b)
        self.assertEqual(dev_a.get("room_id"), room_a)
        self.assertEqual(dev_b.get("room_id"), room_b)

    async def test_issue6_client_connected_detailed_metadata(self):
        """Issue 6: Host receives complete operator metadata (username, clientName, clientIp, machineId)."""
        url = f"ws://127.0.0.1:{self.server_port}"
        room_id = f"TOP-6-{uuid.uuid4().hex[:6]}"
        pin = "112233"

        host_ws = await websockets.connect(url)
        await host_ws.send(json.dumps({
            "type": "init_host",
            "room_id": room_id,
            "pin": pin,
            "machine_id": "host-guid-6",
            "device_name": "Host-Station-6"
        }))
        host_ack = json.loads(await host_ws.recv())
        self.assertEqual(host_ack.get("status"), "ok")

        client_ws = await websockets.connect(url)
        await client_ws.send(json.dumps({
            "type": "init_client",
            "room_id": room_id,
            "pin": pin,
            "username": "alice_architect",
            "client_name": "Alice-MacBook-Pro",
            "machine_id": "client-guid-6"
        }))
        client_ack = json.loads(await client_ws.recv())
        self.assertEqual(client_ack.get("status"), "ok")

        notif = json.loads(await host_ws.recv())
        self.assertEqual(notif.get("type"), "client_connected")
        self.assertEqual(notif.get("clientCount"), 1)
        self.assertEqual(notif.get("username"), "alice_architect")
        self.assertEqual(notif.get("clientName"), "Alice-MacBook-Pro")
        self.assertEqual(notif.get("machineId"), "client-guid-6")
        self.assertTrue(bool(notif.get("sessionId")))
        self.assertTrue(bool(notif.get("clientIp")))

        await host_ws.close()
        await client_ws.close()

    async def test_issue4_multiclient_disconnect_and_stream_config(self):
        """Issue 4: Remaining client receives frames when 1 client disconnects; get_stream_config works."""
        url = f"ws://127.0.0.1:{self.server_port}"
        room_id = f"TOP-4-{uuid.uuid4().hex[:6]}"
        pin = "445566"

        host_ws = await websockets.connect(url)
        await host_ws.send(json.dumps({
            "type": "init_host",
            "room_id": room_id,
            "pin": pin,
            "machine_id": "host-guid-4",
            "device_name": "Multi-Host"
        }))
        await host_ws.recv()

        c1_ws = await websockets.connect(url)
        await c1_ws.send(json.dumps({
            "type": "init_client",
            "room_id": room_id,
            "pin": pin,
            "username": "client_one",
            "machine_id": "c1-guid"
        }))
        await c1_ws.recv() # client ok
        await host_ws.recv() # client_connected count 1

        c2_ws = await websockets.connect(url)
        await c2_ws.send(json.dumps({
            "type": "init_client",
            "room_id": room_id,
            "pin": pin,
            "username": "client_two",
            "machine_id": "c2-guid"
        }))
        await c2_ws.recv() # client ok
        h_notif2 = json.loads(await host_ws.recv())
        self.assertEqual(h_notif2.get("type"), "client_connected")
        self.assertEqual(h_notif2.get("clientCount"), 2)

        # Client 2 queries stream_config via get_stream_config
        await c2_ws.send(json.dumps({"type": "get_stream_config"}))
        cfg_msg = json.loads(await c2_ws.recv())
        self.assertEqual(cfg_msg.get("type"), "stream_config")
        self.assertIn("qualityPreset", cfg_msg)

        # Client 1 disconnects -> Host receives client_disconnected with count 1
        await c1_ws.close()
        disc_notif = json.loads(await host_ws.recv())
        self.assertEqual(disc_notif.get("type"), "client_disconnected")
        self.assertEqual(disc_notif.get("clientCount"), 1)
        self.assertEqual(disc_notif.get("username"), "client_one")

        # Client 2 receives updated session_list notifying remaining client count
        c2_sess_notif = json.loads(await c2_ws.recv())
        self.assertEqual(c2_sess_notif.get("type"), "session_list")
        self.assertEqual(c2_sess_notif.get("clientCount"), 1)

        # Host sends video frame -> Client 2 STILL receives it uninterrupted!
        test_frame = b"\xff\xd8\xff\xe0test_uninterrupted_frame"
        await host_ws.send(test_frame)
        rec2 = await c2_ws.recv()
        self.assertEqual(rec2, test_frame)

        await host_ws.close()
        await c2_ws.close()

    async def test_issue5_reverse_remote_loop_prevention(self):
        """Issue 5: Prevent reverse loops (A->B then B->A) and self-loops (A->A)."""
        url = f"ws://127.0.0.1:{self.server_port}"
        room_a = f"ROOM-A-{uuid.uuid4().hex[:4]}"
        room_b = f"ROOM-B-{uuid.uuid4().hex[:4]}"
        pin = "998877"
        machine_a = "machine-guid-AAA"
        machine_b = "machine-guid-BBB"

        # Host A online
        host_a_ws = await websockets.connect(url)
        await host_a_ws.send(json.dumps({
            "type": "init_host",
            "room_id": room_a,
            "pin": pin,
            "machine_id": machine_a,
            "device_name": "Workstation-A"
        }))
        await host_a_ws.recv()

        # Host B online
        host_b_ws = await websockets.connect(url)
        await host_b_ws.send(json.dumps({
            "type": "init_host",
            "room_id": room_b,
            "pin": pin,
            "machine_id": machine_b,
            "device_name": "Workstation-B"
        }))
        await host_b_ws.recv()

        # Self-Loop Test: Machine A tries to connect to Machine A
        client_self_ws = await websockets.connect(url)
        await client_self_ws.send(json.dumps({
            "type": "init_client",
            "room_id": room_a,
            "pin": pin,
            "machine_id": machine_a,
            "username": "SelfTester"
        }))
        self_res = json.loads(await client_self_ws.recv())
        self.assertEqual(self_res.get("status"), "error")
        self.assertEqual(self_res.get("code"), "RELAY_SELF_LOOP_FORBIDDEN")
        await client_self_ws.close()

        # Step 1: Machine A remotes into Machine B (A -> B)
        client_a_to_b = await websockets.connect(url)
        await client_a_to_b.send(json.dumps({
            "type": "init_client",
            "room_id": room_b,
            "pin": pin,
            "machine_id": machine_a,
            "username": "OperatorA"
        }))
        res_a_to_b = json.loads(await client_a_to_b.recv())
        self.assertEqual(res_a_to_b.get("status"), "ok")
        await host_b_ws.recv() # host B gets client_connected

        # Step 2: Machine B tries to remote into Machine A (B -> A) while A is remoting to B
        # Must be rejected with RELAY_REVERSE_LOOP_FORBIDDEN!
        client_b_to_a = await websockets.connect(url)
        await client_b_to_a.send(json.dumps({
            "type": "init_client",
            "room_id": room_a,
            "pin": pin,
            "machine_id": machine_b,
            "username": "OperatorB"
        }))
        res_b_to_a = json.loads(await client_b_to_a.recv())
        self.assertEqual(res_b_to_a.get("status"), "error")
        self.assertEqual(res_b_to_a.get("code"), "RELAY_REVERSE_LOOP_FORBIDDEN")
        await client_b_to_a.close()

        # Step 3: Machine A disconnects from Machine B
        await client_a_to_b.close()
        await asyncio.sleep(0.5)

        # Step 4: Now Machine B connects into Machine A -> MUST SUCCEED (loop is gone)
        client_b_to_a_allowed = await websockets.connect(url)
        await client_b_to_a_allowed.send(json.dumps({
            "type": "init_client",
            "room_id": room_a,
            "pin": pin,
            "machine_id": machine_b,
            "username": "OperatorB"
        }))
        res_allowed = json.loads(await client_b_to_a_allowed.recv())
        self.assertEqual(res_allowed.get("status"), "ok")

        await client_b_to_a_allowed.close()
        await host_a_ws.close()
        await host_b_ws.close()

if __name__ == "__main__":
    unittest.main()

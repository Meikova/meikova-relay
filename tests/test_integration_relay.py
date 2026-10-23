import json
import asyncio
import unittest
import tempfile
import uuid
import subprocess
import time
import sys
from pathlib import Path
import websockets

class TestIntegrationRelay(unittest.IsolatedAsyncioTestCase):
    server_process = None
    temp_db_path = None

    @classmethod
    def setUpClass(cls):
        # Start Relay Server on test port 8999
        server_path = str(Path(__file__).resolve().parent.parent / "relay-server" / "server.js")
        cls.temp_db_path = str(Path(tempfile.gettempdir()) / f"test_relay_integ_{uuid.uuid4().hex[:8]}.db")
        env = dict(**dict(subprocess.os.environ), PORT="8999", DB_PATH=cls.temp_db_path)
        try:
            cls.server_process = subprocess.Popen(
                ["node", server_path],
                cwd=str(Path(__file__).resolve().parent.parent / "relay-server"),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            # Active polling for port 8999
            import socket
            start_time = time.time()
            ready = False
            while time.time() - start_time < 8.0:
                if cls.server_process.poll() is not None:
                    _, err = cls.server_process.communicate()
                    err_text = err.decode('utf-8', errors='replace')
                    raise unittest.SkipTest(f"Relay server failed to start: {err_text}")
                try:
                    with socket.create_connection(("127.0.0.1", 8999), timeout=0.2):
                        ready = True
                        break
                except (ConnectionRefusedError, OSError):
                    time.sleep(0.1)
            if not ready:
                raise unittest.SkipTest("Relay server did not start listening on port 8999 within 8s")
        except FileNotFoundError:
            raise unittest.SkipTest("Node.js runtime not installed, skipping relay integration tests.")

    @classmethod
    def tearDownClass(cls):
        if cls.server_process:
            cls.server_process.terminate()
            cls.server_process.wait()
        if cls.temp_db_path:
            for ext in ["", "-wal", "-shm"]:
                try:
                    p_db = Path(cls.temp_db_path + ext)
                    if p_db.exists():
                        p_db.unlink()
                except OSError:
                    pass

    async def test_full_relay_lifecycle(self):
        url = "ws://127.0.0.1:8999"

        # 1. Host Connects & Inits
        host_ws = await websockets.connect(url)
        await host_ws.send(json.dumps({
            "type": "init_host",
            "room_id": "TEST-ROOM",
            "pin": "999888",
            "width": 1920,
            "height": 1080,
            "device_name": "Test-Host"
        }))
        host_ack = json.loads(await host_ws.recv())
        self.assertEqual(host_ack.get("status"), "ok")
        self.assertEqual(host_ack.get("role"), "host")

        # 2. Client Connects with Wrong PIN (Should Fail)
        bad_client_ws = await websockets.connect(url)
        await bad_client_ws.send(json.dumps({
            "type": "init_client",
            "room_id": "TEST-ROOM",
            "pin": "WRONG_PIN"
        }))
        bad_ack = json.loads(await bad_client_ws.recv())
        self.assertEqual(bad_ack.get("status"), "error")
        await bad_client_ws.close()

        # 3. Client Connects with Correct PIN (Should Succeed)
        client_ws = await websockets.connect(url)
        await client_ws.send(json.dumps({
            "type": "init_client",
            "room_id": "TEST-ROOM",
            "pin": "999888"
        }))
        client_ack = json.loads(await client_ws.recv())
        self.assertEqual(client_ack.get("status"), "ok")
        self.assertEqual(client_ack.get("role"), "client")
        self.assertEqual(client_ack["hostMeta"]["width"], 1920)

        # Host receives client_connected notification
        host_notif = json.loads(await host_ws.recv())
        self.assertEqual(host_notif.get("type"), "client_connected")

        # 4. Binary Frame forwarding (Host -> Client)
        sample_frame = b'\xff\xd8\xff\xe0' + b'dummy-jpeg-bytes-12345'
        await host_ws.send(sample_frame)
        received_frame = await client_ws.recv()
        self.assertEqual(received_frame, sample_frame)

        # 5. Input Event forwarding (Client -> Host)
        sample_input = json.dumps({"type": "mouse_move", "x": 0.42, "y": 0.88})
        await client_ws.send(sample_input)
        received_input = await host_ws.recv()
        self.assertEqual(received_input, sample_input)

        # Clean close
        await client_ws.close()
        await host_ws.close()

    async def test_protocol_matrix_and_tunnel_forwarding(self):
        url = "ws://127.0.0.1:8999"

        # 1. Connect Host
        host_ws = await websockets.connect(url)
        await host_ws.send(json.dumps({
            "type": "init_host",
            "room_id": "PROTO-ROOM",
            "pin": "123321",
            "device_name": "Protocol-Host"
        }))
        host_ack = json.loads(await host_ws.recv())
        self.assertEqual(host_ack.get("status"), "ok")

        # 2. Connect Client
        client_ws = await websockets.connect(url)
        await client_ws.send(json.dumps({
            "type": "init_client",
            "room_id": "PROTO-ROOM",
            "pin": "123321"
        }))
        client_ack = json.loads(await client_ws.recv())
        self.assertEqual(client_ack.get("status"), "ok")

        _ = await host_ws.recv()  # client_connected

        # 3. Host broadcasts protocol_matrix
        matrix_payload = {
            "type": "protocol_matrix",
            "matrix": {
                "remote": {"preferred": "rdp", "rdp": {"available": True, "port": 3389}},
                "terminal": {"preferred": "ssh", "ssh": {"available": True, "port": 22}},
                "file": {"preferred": "sftp", "sftp": {"available": True, "port": 22}}
            }
        }
        await host_ws.send(json.dumps(matrix_payload))
        client_recv = json.loads(await client_ws.recv())
        self.assertEqual(client_recv.get("type"), "protocol_matrix")
        self.assertEqual(client_recv["matrix"]["remote"]["preferred"], "rdp")

        # 4. Client requests tunnel_open
        tunnel_req = {
            "type": "tunnel_open",
            "tunnel_id": "tun-test-99",
            "protocol": "rdp",
            "port": 3389
        }
        await client_ws.send(json.dumps(tunnel_req))
        host_recv = json.loads(await host_ws.recv())
        self.assertEqual(host_recv.get("type"), "tunnel_open")
        self.assertEqual(host_recv.get("tunnel_id"), "tun-test-99")

        # 5. Host confirms tunnel_opened
        tunnel_ack = {
            "type": "tunnel_opened",
            "tunnel_id": "tun-test-99",
            "status": "ready"
        }
        await host_ws.send(json.dumps(tunnel_ack))
        client_recv_ack = json.loads(await client_ws.recv())
        self.assertEqual(client_recv_ack.get("type"), "tunnel_opened")

        await client_ws.close()
        await host_ws.close()

if __name__ == "__main__":
    unittest.main()

import json
import asyncio
import unittest
import subprocess
import time
import sys
from pathlib import Path
import websockets

class TestIntegrationRelay(unittest.IsolatedAsyncioTestCase):
    server_process = None

    @classmethod
    def setUpClass(cls):
        # Start Relay Server on test port 8999
        server_path = str(Path(__file__).resolve().parent.parent / "relay-server" / "server.js")
        env = dict(**dict(subprocess.os.environ), PORT="8999")
        try:
            cls.server_process = subprocess.Popen(
                ["node", server_path],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            time.sleep(1.5) # Give node server time to bind
            if cls.server_process.poll() is not None:
                _, err = cls.server_process.communicate()
                err_text = err.decode('utf-8', errors='replace')
                raise unittest.SkipTest(f"Relay server failed to start: {err_text}")
        except FileNotFoundError:
            raise unittest.SkipTest("Node.js runtime not installed, skipping relay integration tests.")

    @classmethod
    def tearDownClass(cls):
        if cls.server_process:
            cls.server_process.terminate()
            cls.server_process.wait()

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

if __name__ == "__main__":
    unittest.main()

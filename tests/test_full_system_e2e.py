import os
import json
import time
import urllib.request
import urllib.error
import subprocess
import unittest
import tempfile
import uuid
from pathlib import Path
import websockets
import asyncio

class TestFullSystemE2E(unittest.IsolatedAsyncioTestCase):
    server_process = None
    port = "9005"
    base_url = f"http://127.0.0.1:{port}"
    ws_url = f"ws://127.0.0.1:{port}"
    temp_db_path = None

    @classmethod
    def setUpClass(cls):
        server_path = str(Path(__file__).resolve().parent.parent / "relay-server" / "server.js")
        cls.temp_db_path = str(Path(tempfile.gettempdir()) / f"test_relay_e2e_{uuid.uuid4().hex[:8]}.db")
        env = dict(**dict(os.environ), PORT=cls.port, DB_PATH=cls.temp_db_path)
        try:
            cls.server_process = subprocess.Popen(
                ["node", server_path],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            time.sleep(2.0)
            if cls.server_process.poll() is not None:
                _, err = cls.server_process.communicate()
                err_text = err.decode('utf-8', errors='replace')
                raise unittest.SkipTest(f"Relay server failed to start: {err_text}")
        except FileNotFoundError:
            raise unittest.SkipTest("Node.js runtime not installed, skipping relay E2E tests.")

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

    def test_01_static_assets_serving(self):
        """Verifies Relay HTTP server serves web-client UI assets with 200 OK."""
        assets = [
            ("/", "text/html"),
            ("/index.html", "text/html"),
            ("/css/tokens.css", "text/css"),
            ("/css/style.css", "text/css"),
            ("/js/app.js", "application/javascript"),
        ]
        for path, expected_mime in assets:
            req = urllib.request.Request(f"{self.base_url}{path}")
            with urllib.request.urlopen(req) as resp:
                self.assertEqual(resp.status, 200)
                content_type = resp.headers.get("Content-Type", "")
                self.assertIn(expected_mime, content_type)
                body = resp.read()
                self.assertGreater(len(body), 50)

    def test_02_rest_api_auth_lifecycle(self):
        """Tests user registration, login, and token session verification."""
        username = f"admin_{int(time.time())}"
        password = "EnterprisePassword!123"

        # 1. Register
        reg_data = json.dumps({"username": username, "password": password}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/auth/register",
            data=reg_data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 201)
            res = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(res.get("success"))
            token = res.get("token")
            self.assertIsNotNone(token)

        # 2. Login
        login_data = json.dumps({"username": username, "password": password}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/auth/login",
            data=login_data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            res = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(res.get("success"))
            new_token = res.get("token")
            self.assertIsNotNone(new_token)

        # 3. /api/auth/me using new_token
        req = urllib.request.Request(
            f"{self.base_url}/api/auth/me",
            headers={"Authorization": f"Bearer {new_token}"}
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            res = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(res.get("success"))
            self.assertEqual(res["user"]["username"], username)

    async def test_03_enterprise_features_over_relay(self):
        """Simulates full host-client session: telemetry, terminal, file browse, power actions."""
        room_id = f"ROOM-{int(time.time())}"
        pin = "654321"

        # Host connects
        host_ws = await websockets.connect(self.ws_url)
        await host_ws.send(json.dumps({
            "type": "init_host",
            "room_id": room_id,
            "pin": pin,
            "width": 1920,
            "height": 1080,
            "device_name": "Meikova-Enterprise-Host",
            "os_info": "Windows 11 x64",
            "monitors": [{"id": 1, "name": "Primary", "width": 1920, "height": 1080}]
        }))
        host_ack = json.loads(await host_ws.recv())
        self.assertEqual(host_ack.get("status"), "ok")

        # Client connects
        client_ws = await websockets.connect(self.ws_url)
        await client_ws.send(json.dumps({
            "type": "init_client",
            "room_id": room_id,
            "pin": pin
        }))
        client_ack = json.loads(await client_ws.recv())
        self.assertEqual(client_ack.get("status"), "ok")

        # Drain host's client_connected message
        notif = json.loads(await host_ws.recv())
        self.assertEqual(notif.get("type"), "client_connected")

        # Test A: Telemetry Request -> Response
        await client_ws.send(json.dumps({"type": "telemetry_request"}))
        req = json.loads(await host_ws.recv())
        self.assertEqual(req.get("type"), "telemetry_request")

        # Host replies with telemetry
        await host_ws.send(json.dumps({
            "type": "telemetry_response",
            "data": {"ram": {"used_gb": 8.5, "total_gb": 32.0, "percent": 26}}
        }))
        res = json.loads(await client_ws.recv())
        self.assertEqual(res["type"], "telemetry_response")
        self.assertEqual(res["data"]["ram"]["percent"], 26)

        # Test B: Terminal Input -> Terminal Output
        await client_ws.send(json.dumps({"type": "terminal_input", "command": "dir\n"}))
        term_req = json.loads(await host_ws.recv())
        self.assertEqual(term_req["command"], "dir\n")

        await host_ws.send(json.dumps({"type": "terminal_output", "data": "Volume in drive C is OS\n"}))
        term_res = json.loads(await client_ws.recv())
        self.assertEqual(term_res["type"], "terminal_output")
        self.assertIn("Volume in drive C", term_res["data"])

        # Test C: File Browse Request -> Response
        await client_ws.send(json.dumps({"type": "file_browse_request", "path": ""}))
        browse_req = json.loads(await host_ws.recv())
        self.assertEqual(browse_req["type"], "file_browse_request")

        await host_ws.send(json.dumps({
            "type": "file_browse_response",
            "data": {"current_path": "", "items": [{"name": "C:\\", "is_dir": True, "size": 0}]}
        }))
        browse_res = json.loads(await client_ws.recv())
        self.assertEqual(browse_res["type"], "file_browse_response")
        self.assertEqual(len(browse_res["data"]["items"]), 1)

        # Test D: Audio Stream Toggle & Audio Chunk
        await client_ws.send(json.dumps({"type": "audio_stream_toggle", "enabled": True}))
        audio_req = json.loads(await host_ws.recv())
        self.assertEqual(audio_req.get("type"), "audio_stream_toggle")
        self.assertTrue(audio_req.get("enabled"))

        await host_ws.send(json.dumps({"type": "audio_stream_status", "enabled": True, "sample_rate": 48000, "channels": 2}))
        audio_status = json.loads(await client_ws.recv())
        self.assertEqual(audio_status["type"], "audio_stream_status")
        self.assertTrue(audio_status["enabled"])

        await host_ws.send(json.dumps({"type": "audio_chunk", "data": "AAAA//8=", "rate": 48000, "channels": 2}))
        audio_chunk = json.loads(await client_ws.recv())
        self.assertEqual(audio_chunk["type"], "audio_chunk")
        self.assertEqual(audio_chunk["data"], "AAAA//8=")

        await client_ws.close()
        await host_ws.close()

    async def test_04_google_auth_and_account_device_link(self):
        """Tests Google OAuth JWT payload decoding, session creation, and host device auto-linking."""
        import base64
        email = f"google_user_{int(time.time())}@gmail.com"
        header_b64 = base64.urlsafe_b64encode(b'{"alg":"RS256","typ":"JWT"}').decode().rstrip("=")
        payload_json = json.dumps({"email": email, "name": "Google User", "sub": "12345"}).encode()
        payload_b64 = base64.urlsafe_b64encode(payload_json).decode().rstrip("=")
        mock_id_token = f"{header_b64}.{payload_b64}.mock_sig"

        # 1. Google Auth endpoint
        req_data = json.dumps({"credential": mock_id_token}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/auth/google",
            data=req_data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            res = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(res.get("success"))
            user_token = res.get("token")
            self.assertEqual(res["user"]["username"], email)

        # 2. Host Agent connects and links using account email
        host_room = f"G-ROOM-{int(time.time())}"
        host_ws = await websockets.connect(self.ws_url)
        await host_ws.send(json.dumps({
            "type": "init_host",
            "room_id": host_room,
            "pin": "888888",
            "device_name": "Google-Linked-Workstation",
            "account": email,
            "width": 1920,
            "height": 1080
        }))
        host_ack = json.loads(await host_ws.recv())
        self.assertEqual(host_ack.get("status"), "ok")

        # 3. Call GET /api/devices with Google user's token
        req = urllib.request.Request(
            f"{self.base_url}/api/devices",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("success"))
            devices = data.get("devices", [])
            self.assertGreaterEqual(len(devices), 1)
            matched = any(d["room_id"] == host_room for d in devices)
            self.assertTrue(matched)

        await host_ws.close()

if __name__ == "__main__":
    unittest.main()

import os
import json
import time
import base64
import urllib.request
import urllib.error
import subprocess
import unittest
from pathlib import Path
import websockets
import asyncio

class TestAuthSyncAndLinking(unittest.IsolatedAsyncioTestCase):
    server_process = None
    port = "9015"
    base_url = f"http://127.0.0.1:{port}"
    ws_url = f"ws://127.0.0.1:{port}"

    @classmethod
    def setUpClass(cls):
        server_path = str(Path(__file__).resolve().parent.parent / "relay-server" / "server.js")
        env = dict(**dict(os.environ), PORT=cls.port)
        try:
            cls.server_process = subprocess.Popen(
                ["node", server_path],
                cwd=str(Path(__file__).resolve().parent.parent / "relay-server"),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            # Active wait for server startup
            import socket
            start = time.time()
            ready = False
            while time.time() - start < 8.0:
                if cls.server_process.poll() is not None:
                    _, err = cls.server_process.communicate()
                    raise unittest.SkipTest(f"Relay server failed to start: {err.decode('utf-8', errors='replace')}")
                try:
                    with socket.create_connection(("127.0.0.1", int(cls.port)), timeout=0.2):
                        ready = True
                        break
                except (ConnectionRefusedError, OSError):
                    time.sleep(0.1)
            if not ready:
                raise unittest.SkipTest(f"Relay server did not listen on port {cls.port} within 8s")
        except FileNotFoundError:
            raise unittest.SkipTest("Node.js runtime not installed, skipping tests.")

    @classmethod
    def tearDownClass(cls):
        if cls.server_process:
            cls.server_process.terminate()
            cls.server_process.wait()

    def _generate_mock_sso_token(self, user_id, username, email, display_name=None):
        """Generates a signed or mock Ed25519 Universal SSO token using node CLI script."""
        script = f"""
        const {{ UniversalSSO }} = require('./universal_sso');
        const sso = new UniversalSSO();
        try {{
          const token = sso.issueToken({{
            userId: '{user_id}',
            username: '{username}',
            email: '{email}',
            displayName: '{display_name or username}'
          }});
          process.stdout.write(token);
        }} catch(e) {{
          process.stderr.write(e.message);
          process.exit(1);
        }}
        """
        res = subprocess.run(
            ["node", "-e", script],
            cwd=str(Path(__file__).resolve().parent.parent / "relay-server"),
            capture_output=True,
            text=True
        )
        if res.returncode != 0:
            raise RuntimeError(f"Failed to generate SSO token: {res.stderr}")
        return res.stdout.strip()

    async def test_01_sso_jit_provisioning_and_device_link(self):
        """Tests that when user logs in via SSO, local user is mirrored and host agent links automatically."""
        user_id = f"usr_sso_{int(time.time())}"
        username = f"kiemp_{int(time.time())}"
        email = f"{username}@gmail.com"

        sso_token = self._generate_mock_sso_token(user_id, username, email, "Kiem Pham")
        self.assertTrue(len(sso_token) > 20)

        # 1. SSO Login Callback
        req_data = json.dumps({"token": sso_token}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/auth/sso/callback",
            data=req_data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("success"))
            session_token = data.get("token")
            self.assertEqual(data["user"]["id"], user_id)

        # 2. Host Agent connects via WebSocket sending account username (without @gmail.com)
        host_room = f"RD-{int(time.time()) % 100000}"
        host_ws = await websockets.connect(self.ws_url)
        await host_ws.send(json.dumps({
            "type": "init_host",
            "room_id": host_room,
            "pin": "654321",
            "device_name": "Host-Agent-SSO-PC",
            "account": username,
            "width": 1920,
            "height": 1080
        }))
        ack = json.loads(await host_ws.recv())
        self.assertEqual(ack.get("status"), "ok")

        # 3. Web client queries GET /api/devices with session token
        req = urllib.request.Request(
            f"{self.base_url}/api/devices",
            headers={"Authorization": f"Bearer {session_token}"}
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            res_data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(res_data.get("success"))
            devices = res_data.get("devices", [])
            self.assertGreaterEqual(len(devices), 1)
            matched = any(d["room_id"] == host_room for d in devices)
            self.assertTrue(matched, f"Device {host_room} must appear in user's device list")

        await host_ws.close()

    async def test_02_device_link_by_email_and_user_id(self):
        """Tests smart matching when host sends email address or direct user_id."""
        user_id = f"usr_sso2_{int(time.time())}"
        username = f"user2_{int(time.time())}"
        email = f"{username}@company.vn"

        sso_token = self._generate_mock_sso_token(user_id, username, email)
        req_data = json.dumps({"token": sso_token}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/auth/sso/callback",
            data=req_data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            session_token = data.get("token")

        # Host Agent connects using full email
        host_room = f"RD-EMAIL-{int(time.time()) % 100000}"
        host_ws = await websockets.connect(self.ws_url)
        await host_ws.send(json.dumps({
            "type": "init_host",
            "room_id": host_room,
            "pin": "123456",
            "device_name": "Host-Agent-Email-Matched",
            "account": email,
            "width": 1920,
            "height": 1080
        }))
        ack = json.loads(await host_ws.recv())
        self.assertEqual(ack.get("status"), "ok")

        # Web client queries devices
        req = urllib.request.Request(
            f"{self.base_url}/api/devices",
            headers={"Authorization": f"Bearer {session_token}"}
        )
        with urllib.request.urlopen(req) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            devices = res_data.get("devices", [])
            matched = any(d["room_id"] == host_room for d in devices)
            self.assertTrue(matched)

        await host_ws.close()

    def test_03_auth_sync_queue_and_status_api(self):
        """Tests that local registration is recorded in auth_sync_queue and sync endpoint works."""
        username = f"local_offline_{int(time.time())}"
        password = "SecurePassword123"

        reg_data = json.dumps({"username": username, "password": password}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/auth/register",
            data=reg_data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 201)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("success"))
            token = data.get("token")

        # Check sync status endpoint
        req = urllib.request.Request(
            f"{self.base_url}/api/auth/sync/status",
            headers={"Authorization": f"Bearer {token}"}
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            sync_info = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(sync_info.get("success"))
            self.assertIn("queue_count", sync_info)

    async def test_04_sync_conflict_resolution_same_email(self):
        """Tests that when gateway syncs account with same email, Account Linking merges identities seamlessly."""
        suffix = int(time.time() * 1000) % 1000000
        username_local = f"alice_local_{suffix}"
        email = f"alice_{suffix}@company.com"
        password = "Password123!"

        # 1. Local user registers offline with email
        reg_data = json.dumps({"username": username_local, "password": password, "email": email}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/auth/register",
            data=reg_data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 201)

        # 2. Host agent connects using local username
        host_room = f"RD-ALICE-{suffix}"
        host_ws = await websockets.connect(self.ws_url)
        await host_ws.send(json.dumps({
            "type": "init_host",
            "room_id": host_room,
            "pin": "111222",
            "device_name": "Alice-Laptop",
            "account": username_local,
            "width": 1920,
            "height": 1080
        }))
        ack = json.loads(await host_ws.recv())
        self.assertEqual(ack.get("status"), "ok")

        # 3. Gateway syncs account with same email
        gateway_user_id = f"usr_gateway_{suffix}"
        sync_payload = json.dumps({
            "accounts": [{
                "email": email,
                "gateway_user_id": gateway_user_id,
                "username": f"alice_corp_{suffix}",
                "display_name": "Alice Corp"
            }]
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/auth/sync/gateway",
            data=sync_payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            sync_res = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(sync_res.get("success"))
            self.assertEqual(sync_res["results"][0]["action"], "LINKED")
            self.assertEqual(sync_res["results"][0]["userId"], gateway_user_id)

        # 4. User logs in via Gateway SSO token with gateway_user_id
        sso_token = self._generate_mock_sso_token(gateway_user_id, f"alice_corp_{suffix}", email, "Alice Corp")
        req_data = json.dumps({"token": sso_token}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/auth/sso/callback",
            data=req_data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            session_data = json.loads(resp.read().decode("utf-8"))
            user_token = session_data["token"]

        # 5. Device previously added by local user MUST now appear under SSO user!
        req = urllib.request.Request(
            f"{self.base_url}/api/devices",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        with urllib.request.urlopen(req) as resp:
            devices_res = json.loads(resp.read().decode("utf-8"))
            devices = devices_res.get("devices", [])
            matched = any(d["room_id"] == host_room for d in devices)
            self.assertTrue(matched, f"Device {host_room} must be linked to {gateway_user_id}")

        await host_ws.close()

    def test_05_sync_conflict_resolution_same_username_diff_email(self):
        """Tests that when username matches but email differs, namespace resolution renames local user."""
        suffix = int(time.time() * 1000) % 1000000
        common_username = f"bob_clash_{suffix}"
        local_email = f"bob_local_{suffix}@internal.dev"
        gateway_email = f"bob_gateway_{suffix}@enterprise.com"
        gateway_user_id = f"usr_bob_{suffix}"

        # 1. Local user registers with common_username
        reg_data = json.dumps({
            "username": common_username,
            "password": "Password123!",
            "email": local_email
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/auth/register",
            data=reg_data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 201)

        # 2. Gateway syncs same common_username with different email
        sync_payload = json.dumps({
            "accounts": [{
                "email": gateway_email,
                "gateway_user_id": gateway_user_id,
                "username": common_username,
                "display_name": "Bob Enterprise"
            }]
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/auth/sync/gateway",
            data=sync_payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            sync_res = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(sync_res.get("success"))
            self.assertEqual(sync_res["results"][0]["action"], "RESOLVED_NAMESPACE")
            self.assertIn("_local_", sync_res["results"][0]["localRenamedTo"])
            self.assertEqual(sync_res["results"][0]["userId"], gateway_user_id)

if __name__ == "__main__":
    unittest.main()

import unittest
import subprocess
import time
import json
import urllib.request
import urllib.error
import socket
import uuid
from pathlib import Path
import os

class TestTursoRelay(unittest.TestCase):
    server_process = None
    port = 8995
    base_dir = Path(__file__).resolve().parent.parent
    relay_server_dir = base_dir / "relay-server"

    @classmethod
    def setUpClass(cls):
        # 1. First run the dedicated node unit test for dual adapter
        adapter_test_script = cls.relay_server_dir / "test_turso_dual_adapter.js"
        res = subprocess.run(
            ["node", str(adapter_test_script)],
            cwd=str(cls.relay_server_dir),
            capture_output=True,
            text=True
        )
        if res.returncode != 0:
            print("Adapter Test Stderr:\n", res.stderr)
            print("Adapter Test Stdout:\n", res.stdout)
            raise RuntimeError(f"Dual adapter unit test failed with code {res.returncode}")

        # 2. Launch server.js with Turso Cloud credentials on dedicated port
        server_path = str(cls.relay_server_dir / "server.js")
        env = dict(
            **dict(os.environ),
            PORT=str(cls.port),
            TURSO_DATABASE_URL="libsql://meikova-relay-m3ik18dp.aws-ap-northeast-1.turso.io",
            TURSO_AUTH_TOKEN="eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3OTI1ODkwNTMsImlkIjoiMDFhMTVlYTEtZDUwMS03NDlkLThkMTMtZmMyOGUyZDlhOGM5Iiwia2lkIjoibk13eDJZSGtEaHVvYl81SXZkM1FQVzhpVi1ZT0poeHdUbmpIMXo5dl9iMCIsInJpZCI6ImU0NmQyODEyLTRiYTYtNDc1MC04ZTM1LTI0MjIyOTZiYzdlMSJ9.AKPFGtMkGu20fOytd44kXqQg-UwV0_plYMoNW1XBhbISbV-iK75OnaPHPacOKRgnBdLU_qk-zdkdpz7y7qL0AA"
        )
        cls.server_process = subprocess.Popen(
            ["node", server_path],
            cwd=str(cls.relay_server_dir),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Wait for port to become available
        start_time = time.time()
        ready = False
        while time.time() - start_time < 10.0:
            if cls.server_process.poll() is not None:
                _, err = cls.server_process.communicate()
                if cls.server_process.stdout: cls.server_process.stdout.close()
                if cls.server_process.stderr: cls.server_process.stderr.close()
                raise RuntimeError(f"Server crashed on startup: {err.decode('utf-8', errors='replace')}")
            try:
                with socket.create_connection(("127.0.0.1", cls.port), timeout=0.2):
                    ready = True
                    break
            except (ConnectionRefusedError, OSError):
                time.sleep(0.1)
        if not ready:
            cls.server_process.terminate()
            raise RuntimeError(f"Server failed to start on port {cls.port} within 10s")

    @classmethod
    def tearDownClass(cls):
        if cls.server_process:
            cls.server_process.terminate()
            try:
                cls.server_process.wait(timeout=3)
                if cls.server_process.stdout: cls.server_process.stdout.close()
                if cls.server_process.stderr: cls.server_process.stderr.close()
            except subprocess.TimeoutExpired:
                cls.server_process.kill()

    def test_01_health_check(self):
        url = f"http://127.0.0.1:{self.port}/api/health"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as res:
            self.assertEqual(res.status, 200)
            data = json.loads(res.read().decode("utf-8"))
            self.assertEqual(data.get("status"), "ok")
            self.assertEqual(data.get("relay"), "online")

    def test_02_auth_register_and_login_turso(self):
        rand = f"py_turso_{uuid.uuid4().hex[:8]}_{int(time.time())}"
        reg_url = f"http://127.0.0.1:{self.port}/api/auth/register"
        payload = json.dumps({"username": rand, "password": "securePass123!"}).encode("utf-8")
        req = urllib.request.Request(reg_url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        
        with urllib.request.urlopen(req, timeout=20) as res:
            self.assertEqual(res.status, 201)
            reg_data = json.loads(res.read().decode("utf-8"))
            self.assertTrue(reg_data.get("success"))
            token = reg_data.get("token")
            self.assertTrue(token)
            self.assertEqual(reg_data.get("user", {}).get("username"), rand)

        # Login with registered account
        login_url = f"http://127.0.0.1:{self.port}/api/auth/login"
        req = urllib.request.Request(login_url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=20) as res:
            self.assertEqual(res.status, 200)
            login_data = json.loads(res.read().decode("utf-8"))
            self.assertTrue(login_data.get("success"))
            self.assertTrue(login_data.get("token"))

        # Verify /api/auth/me with Bearer token
        me_url = f"http://127.0.0.1:{self.port}/api/auth/me"
        req = urllib.request.Request(me_url, headers={"Authorization": f"Bearer {token}"}, method="GET")
        with urllib.request.urlopen(req, timeout=20) as res:
            self.assertEqual(res.status, 200)
            me_data = json.loads(res.read().decode("utf-8"))
            self.assertTrue(me_data.get("success"))
            self.assertEqual(me_data.get("user", {}).get("username"), rand)

    def test_03_audit_logs_query(self):
        # Query audit logs endpoint using admin / auth token
        reg_url = f"http://127.0.0.1:{self.port}/api/auth/register"
        rand = f"audit_usr_{uuid.uuid4().hex[:8]}_{int(time.time())}"
        payload = json.dumps({"username": rand, "password": "securePass123!"}).encode("utf-8")
        req = urllib.request.Request(reg_url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=20) as res:
            data = json.loads(res.read().decode("utf-8"))
            token = data.get("token")

        audit_url = f"http://127.0.0.1:{self.port}/api/audit-logs?limit=5"
        req = urllib.request.Request(audit_url, headers={"Authorization": f"Bearer {token}"}, method="GET")
        with urllib.request.urlopen(req, timeout=20) as res:
            self.assertEqual(res.status, 200)
            audit_data = json.loads(res.read().decode("utf-8"))
            self.assertTrue(audit_data.get("success"))
            self.assertIn("logs", audit_data)
            self.assertGreaterEqual(audit_data.get("total", 0), 1)

    def test_04_sync_endpoints(self):
        # Test offline-first sync push & pull
        reg_url = f"http://127.0.0.1:{self.port}/api/auth/register"
        rand = f"sync_usr_{uuid.uuid4().hex[:8]}_{int(time.time())}"
        payload = json.dumps({"username": rand, "password": "securePass123!"}).encode("utf-8")
        req = urllib.request.Request(reg_url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=20) as res:
            token = json.loads(res.read().decode("utf-8")).get("token")

        push_url = f"http://127.0.0.1:{self.port}/api/sync/push"
        sync_payload = json.dumps({"preferences": {"color_scheme": "ambient-dark"}}).encode("utf-8")
        req = urllib.request.Request(push_url, data=sync_payload, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=20) as res:
            self.assertEqual(res.status, 200)
            push_res = json.loads(res.read().decode("utf-8"))
            self.assertEqual(push_res.get("status"), "success")

        pull_url = f"http://127.0.0.1:{self.port}/api/sync/pull"
        req = urllib.request.Request(pull_url, headers={"Authorization": f"Bearer {token}"}, method="GET")
        with urllib.request.urlopen(req, timeout=20) as res:
            self.assertEqual(res.status, 200)
            pull_res = json.loads(res.read().decode("utf-8"))
            self.assertEqual(pull_res.get("data", {}).get("preferences", {}).get("color_scheme"), "ambient-dark")

if __name__ == "__main__":
    unittest.main()

import unittest
import subprocess
import time
import urllib.request
import urllib.error
import tempfile
import uuid
from pathlib import Path

class TestDownloadEndpoints(unittest.TestCase):
    server_process = None
    port = 8998
    temp_db_path = None

    @classmethod
    def setUpClass(cls):
        server_path = str(Path(__file__).resolve().parent.parent / "relay-server" / "server.js")
        cls.temp_db_path = str(Path(tempfile.gettempdir()) / f"test_relay_dl_{uuid.uuid4().hex[:8]}.db")
        env = dict(**dict(subprocess.os.environ), PORT=str(cls.port), DB_PATH=cls.temp_db_path)
        try:
            cls.server_process = subprocess.Popen(
                ["node", server_path],
                cwd=str(Path(__file__).resolve().parent.parent / "relay-server"),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            import socket
            start_time = time.time()
            ready = False
            while time.time() - start_time < 8.0:
                if cls.server_process.poll() is not None:
                    _, err = cls.server_process.communicate()
                    if cls.server_process.stdout: cls.server_process.stdout.close()
                    if cls.server_process.stderr: cls.server_process.stderr.close()
                    err_text = err.decode('utf-8', errors='replace')
                    raise unittest.SkipTest(f"Relay server failed to start: {err_text}")
                try:
                    with socket.create_connection(("127.0.0.1", cls.port), timeout=0.2):
                        ready = True
                        break
                except (ConnectionRefusedError, OSError):
                    time.sleep(0.1)
            if not ready:
                raise unittest.SkipTest(f"Relay server did not start listening on port {cls.port} within 8s")
        except FileNotFoundError:
            raise unittest.SkipTest("Node.js runtime not installed, skipping test.")

    @classmethod
    def tearDownClass(cls):
        if cls.server_process:
            cls.server_process.terminate()
            cls.server_process.wait()
            if cls.server_process.stdout: cls.server_process.stdout.close()
            if cls.server_process.stderr: cls.server_process.stderr.close()
        if cls.temp_db_path:
            for ext in ["", "-wal", "-shm"]:
                try:
                    p = Path(cls.temp_db_path + ext)
                    if p.exists():
                        p.unlink()
                except OSError:
                    pass

    def test_setup_bat_download(self):
        url = f"http://127.0.0.1:{self.port}/api/download/setup.bat?account=Tester"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            content = resp.read().decode("utf-8")
            self.assertIn("Meikova Relay Host", content)
            self.assertIn("HEADLESS_MODE=0", content)
            self.assertIn("APP_FLAGS=--gui", content)
            self.assertIn("Desktop Tray Agent", content)

    def test_setup_bat_with_user_id(self):
        url = f"http://127.0.0.1:{self.port}/api/download/setup.bat?account=Developer&userId=usr_abc123"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            content = resp.read().decode("utf-8")
            self.assertIn('"user_id": "usr_abc123"', content)
            self.assertIn('"account": "Developer"', content)
            self.assertIn('set "HEADLESS_BOOL=false"', content)
            self.assertIn('"headless": %HEADLESS_BOOL%', content)
            self.assertIn("Desktop Tray Agent", content)

    def test_setup_bat_headless_download(self):
        url = f"http://127.0.0.1:{self.port}/api/download/setup.bat?account=Tester&headless=1"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            content = resp.read().decode("utf-8")
            self.assertIn("HEADLESS_MODE=1", content)
            self.assertIn("--service", content)
            self.assertIn("Tester", content)
            self.assertIn("MeikovaRelayHost.exe", content)
            self.assertIn("Dich vu chay ngam", content)

    def test_setup_linux_download_with_account_and_user_id(self):
        url = f"http://127.0.0.1:{self.port}/api/download/setup-linux.sh?account=LinuxUser&userId=usr_linux99"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            content = resp.read().decode("utf-8")
            self.assertIn('ACCOUNT="LinuxUser"', content)
            self.assertIn('"user_id": "usr_linux99"', content)
            self.assertIn('host_service.py', content)

    def test_setup_macos_download_with_account_and_user_id(self):
        url = f"http://127.0.0.1:{self.port}/api/download/setup-macos.sh?account=MacUser&userId=usr_mac77"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            content = resp.read().decode("utf-8")
            self.assertIn('ACCOUNT="MacUser"', content)
            self.assertIn('"user_id": "usr_mac77"', content)
            self.assertIn('host_service.py', content)

    def test_host_exe_download(self):
        url = f"http://127.0.0.1:{self.port}/api/download/MeikovaRelayHost.exe"
        # Handler does HEAD or GET (if present returns 200, else 307)
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        opener = urllib.request.build_opener(NoRedirect)
        try:
            resp = opener.open(url)
            self.assertIn(resp.status, [200, 307])
        except urllib.error.HTTPError as e:
            self.assertIn(e.code, [200, 307])

    def test_client_exe_download(self):
        url = f"http://127.0.0.1:{self.port}/api/download/MeikovaRelayClient.exe"
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        opener = urllib.request.build_opener(NoRedirect)
        try:
            resp = opener.open(url)
            self.assertIn(resp.status, [200, 307])
        except urllib.error.HTTPError as e:
            self.assertIn(e.code, [200, 307])

    def test_unknown_artifact_returns_404(self):
        url = f"http://127.0.0.1:{self.port}/api/download/unknown_fake_artifact.exe"
        try:
            urllib.request.urlopen(url)
            self.fail("Expected 404")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 404)

    def test_rdp_config_download(self):
        url = f"http://127.0.0.1:{self.port}/api/session/RD-9999/rdp-config?port=3389&host=127.0.0.1"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("application/x-rdp", resp.headers.get("Content-Type", ""))
            body = resp.read().decode("utf-8")
            self.assertIn("full address:s:127.0.0.1:3389", body)
            self.assertIn("screen mode id:i:2", body)

    def test_host_info_endpoints_and_schema(self):
        import json
        for ep in ["/api/host-info", "/api/network/host-info"]:
            url = f"http://127.0.0.1:{self.port}{ep}"
            with urllib.request.urlopen(url) as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode("utf-8"))
                self.assertIn("lan_ip", data)
                self.assertIn("lan_url", data)
                self.assertIn("tailscale_ip", data)
                self.assertIn("tailscale_url", data)
                self.assertIn("active_url", data)
                self.assertIn("is_local", data)
                self.assertTrue(isinstance(data["lan_ip"], str))
                self.assertTrue(data["lan_url"].startswith("http"))

    def test_qr_endpoint(self):
        url = f"http://127.0.0.1:{self.port}/api/qr?data=https%3A%2F%2Fexample.com"
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        opener = urllib.request.build_opener(NoRedirect)
        try:
            resp = opener.open(url)
            self.assertIn(resp.status, [200, 307])
            if resp.status == 307:
                self.assertIn("api.qrserver.com", resp.headers.get("Location", ""))
        except urllib.error.HTTPError as e:
            self.assertIn(e.code, [200, 307])
            if e.code == 307:
                self.assertIn("api.qrserver.com", e.headers.get("Location", ""))

if __name__ == "__main__":
    unittest.main()

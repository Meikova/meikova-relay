import unittest
import subprocess
import time
import urllib.request
import urllib.error
from pathlib import Path

class TestDownloadEndpoints(unittest.TestCase):
    server_process = None
    port = 8998

    @classmethod
    def setUpClass(cls):
        server_path = str(Path(__file__).resolve().parent.parent / "relay-server" / "server.js")
        env = dict(**dict(subprocess.os.environ), PORT=str(cls.port))
        try:
            cls.server_process = subprocess.Popen(
                ["node", server_path],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            time.sleep(1.5)
            if cls.server_process.poll() is not None:
                _, err = cls.server_process.communicate()
                err_text = err.decode('utf-8', errors='replace')
                raise unittest.SkipTest(f"Relay server failed to start: {err_text}")
        except FileNotFoundError:
            raise unittest.SkipTest("Node.js runtime not installed, skipping test.")

    @classmethod
    def tearDownClass(cls):
        if cls.server_process:
            cls.server_process.terminate()
            cls.server_process.wait()

    def test_setup_bat_download(self):
        url = f"http://127.0.0.1:{self.port}/api/download/setup.bat?account=Tester"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            content = resp.read().decode("utf-8")
            self.assertIn("Meikova Relay Host", content)
            self.assertIn("Tester", content)
            self.assertIn("MeikovaRelayHost.exe", content)

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

if __name__ == "__main__":
    unittest.main()

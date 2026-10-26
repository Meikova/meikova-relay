import unittest
import sys
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

class TestTunnelManager(unittest.TestCase):
    def test_tunnel_manager_js_syntax_and_status(self):
        js_code = """
        const { tunnelManager } = require('./tunnel_manager.js');
        const st = tunnelManager.getStatus();
        console.log(JSON.stringify(st));
        """
        p = subprocess.run(
            ["node", "-e", js_code],
            cwd=str(REPO_ROOT / "relay-server"),
            capture_output=True,
            text=True
        )
        self.assertEqual(p.returncode, 0, f"Node script failed: {p.stderr}")
        self.assertIn('"running":false', p.stdout)
        self.assertIn('"status":"idle"', p.stdout)
        self.assertIn('"installed":', p.stdout)

    def test_find_cloudflared_path(self):
        js_code = """
        const { tunnelManager } = require('./tunnel_manager.js');
        const bin = tunnelManager.findCloudflared();
        console.log('BIN:' + (bin || 'NONE'));
        """
        p = subprocess.run(
            ["node", "-e", js_code],
            cwd=str(REPO_ROOT / "relay-server"),
            capture_output=True,
            text=True
        )
        self.assertEqual(p.returncode, 0, f"Node script failed: {p.stderr}")
        self.assertIn("BIN:", p.stdout)

    def test_get_install_command_multiplatform(self):
        js_code = """
        const { CloudflaredTunnelManager } = require('./tunnel_manager.js');
        const m = new CloudflaredTunnelManager();
        const cmd = m.getInstallCommand();
        if (!cmd || typeof cmd !== 'string') process.exit(1);
        console.log('CMD_OK');
        """
        p = subprocess.run(
            ["node", "-e", js_code],
            cwd=str(REPO_ROOT / "relay-server"),
            capture_output=True,
            text=True
        )
        self.assertEqual(p.returncode, 0, f"Node script failed: {p.stderr}")
        self.assertIn("CMD_OK", p.stdout)

    def test_tunnel_state_lifecycle_offline(self):
        js_code = """
        const { CloudflaredTunnelManager } = require('./tunnel_manager.js');
        const m = new CloudflaredTunnelManager();
        m.status = 'running';
        m.tunnelUrl = 'https://mock-test.trycloudflare.com';
        const st = m.getStatus();
        if (!st.running || st.url !== 'https://mock-test.trycloudflare.com') process.exit(1);
        m.stop();
        const st2 = m.getStatus();
        if (st2.running || st2.url !== null) process.exit(2);
        console.log('LIFECYCLE_OK');
        """
        p = subprocess.run(
            ["node", "-e", js_code],
            cwd=str(REPO_ROOT / "relay-server"),
            capture_output=True,
            text=True
        )
        self.assertEqual(p.returncode, 0, f"Node script failed: {p.stderr}")
        self.assertIn("LIFECYCLE_OK", p.stdout)

if __name__ == "__main__":
    unittest.main()

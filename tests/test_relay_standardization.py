import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

class TestRelayStandardization(unittest.TestCase):
    def test_01_zero_emojis_in_source(self):
        """Verifies zero emojis exist in client and server source files."""
        emoji_regex = re.compile(r"[\U00010000-\U0010ffff\u2600-\u26ff\u2700-\u27bf]")
        
        target_dirs = [
            ROOT / "web-client",
            ROOT / "relay-server" / "public",
            ROOT / "client_desktop",
            ROOT / "host_agent",
        ]
        
        found = []
        for d in target_dirs:
            if not d.exists():
                continue
            for p in d.rglob("*"):
                if not p.is_file():
                    continue
                if any(x in p.parts for x in ["node_modules", ".git", "dist", "build", "assets"]):
                    continue
                if p.suffix in [".html", ".js", ".css", ".py"]:
                    content = p.read_text(encoding="utf-8")
                    for i, line in enumerate(content.splitlines(), 1):
                        if emoji_regex.search(line):
                            found.append(f"{p.relative_to(ROOT)}:{i}: {line.strip()}")
        
        self.assertEqual(len(found), 0, f"Found emojis in source: {found}")

    def test_02_zero_native_dialogs_in_client(self):
        """Verifies zero alert(), window.confirm(), window.prompt() in client JS."""
        dialog_regex = re.compile(r"\b(window\.)?(alert|confirm|prompt)\s*\(")
        
        target_files = [
            ROOT / "web-client" / "js" / "app.js",
            ROOT / "relay-server" / "public" / "js" / "app.js",
        ]
        
        found = []
        for p in target_files:
            if not p.exists():
                continue
            content = p.read_text(encoding="utf-8")
            for i, line in enumerate(content.splitlines(), 1):
                # Ignore deferred PWA prompt method: relayPwaPrompt.prompt()
                if "relayPwaPrompt.prompt" in line:
                    continue
                if dialog_regex.search(line):
                    found.append(f"{p.relative_to(ROOT)}:{i}: {line.strip()}")
        
        self.assertEqual(len(found), 0, f"Found native dialogs in client: {found}")

    def test_03_server_google_auth_aliases(self):
        """Verifies server.js implements /api/auth/google/start alias for /api/auth/google/url."""
        server_js = ROOT / "relay-server" / "server.js"
        content = server_js.read_text(encoding="utf-8")
        self.assertIn("/api/auth/google/start", content)
        self.assertIn("/api/auth/google/url", content)

    def test_04_server_sync_endpoints(self):
        """Verifies server.js implements standard sync routes."""
        server_js = ROOT / "relay-server" / "server.js"
        content = server_js.read_text(encoding="utf-8")
        self.assertIn("/api/sync/status", content)
        self.assertIn("/api/sync/pull", content)
        self.assertIn("/api/sync/push", content)

    def test_05_dynamic_host_info_endpoints(self):
        """Verifies server.js implements dynamic host discovery and SVG QR code."""
        server_js = ROOT / "relay-server" / "server.js"
        content = server_js.read_text(encoding="utf-8")
        self.assertIn("/api/host-info", content)
        self.assertIn("/api/network/host-info", content)
        self.assertIn("/api/qr", content)

    def test_06_package_json_license(self):
        """Verifies package.json has MIT license."""
        pkg = ROOT / "relay-server" / "package.json"
        content = pkg.read_text(encoding="utf-8")
        self.assertIn('"license": "MIT"', content)


if __name__ == "__main__":
    unittest.main()

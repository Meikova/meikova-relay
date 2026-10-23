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


    def test_07_zero_double_border_in_chat_input(self):
        """Verifies chat input focus rules suppress concentric double borders."""
        for css_file in [ROOT / "web-client" / "css" / "style.css", ROOT / "relay-server" / "public" / "css" / "style.css"]:
            content = css_file.read_text(encoding="utf-8")
            self.assertIn(".chat-input-field:focus", content)
            self.assertIn("box-shadow: none !important", content)

    def test_08_harmonized_dialog_buttons(self):
        """Verifies confirm dialog uses balanced .dialog-btn instead of mismatched btn-pill vs btn-cta."""
        for html_file in [ROOT / "web-client" / "index.html", ROOT / "relay-server" / "public" / "index.html"]:
            content = html_file.read_text(encoding="utf-8")
            self.assertIn('id="confirmDialogBtnCancel" class="dialog-btn dialog-btn--secondary"', content)
            self.assertIn('id="confirmDialogBtnConfirm" class="dialog-btn dialog-btn--primary"', content)

    def test_09_svg_only_file_shelf_and_explorer(self):
        """Verifies shelf and explorer action buttons use standard SVG icons without raw unicode text."""
        for js_file in [ROOT / "web-client" / "js" / "app.js", ROOT / "relay-server" / "public" / "js" / "app.js"]:
            content = js_file.read_text(encoding="utf-8")
            self.assertIn("shelf-btn-action btn-shelf-download", content)
            self.assertIn("btn-action-icon btn-action-copy", content)
            self.assertIn("btn-action-icon btn-action-dl", content)
            self.assertNotIn("<span>${isDir ? '?' : '? T?i'}</span>", content)



    def test_10_frameless_titlebar_and_desktop_shell_isolation(self):
        """Verifies Law 5: Custom desktop titlebar exists and is strictly hidden on web/mobile."""
        for html_file in [ROOT / "web-client" / "index.html", ROOT / "relay-server" / "public" / "index.html"]:
            content = html_file.read_text(encoding="utf-8")
            self.assertIn('id="desktop-titlebar"', content)
            self.assertIn('id="dt-btn-min"', content)
            self.assertIn('id="dt-btn-max"', content)
            self.assertIn('id="dt-btn-close"', content)

        for css_file in [ROOT / "web-client" / "css" / "style.css", ROOT / "relay-server" / "public" / "css" / "style.css"]:
            content = css_file.read_text(encoding="utf-8")
            self.assertIn(".desktop-titlebar", content)
            self.assertIn("display: none !important", content)
            self.assertIn("body.is-desktop-shell .desktop-titlebar", content)

        for js_file in [ROOT / "web-client" / "js" / "app.js", ROOT / "relay-server" / "public" / "js" / "app.js"]:
            content = js_file.read_text(encoding="utf-8")
            self.assertIn("initDesktopTitlebar", content)

    def test_11_forbidden_make_icon_purged(self):
        """Verifies Law 8: make_icon.py is purged and never imported in codebase."""
        self.assertFalse((ROOT / "host_agent" / "make_icon.py").exists())
        py_files = list((ROOT / "host_agent").glob("*.py")) + list((ROOT / "client_desktop").glob("*.py"))
        for f in py_files:
            c = f.read_text(encoding="utf-8")
            self.assertNotIn("make_icon", c, f"Found forbidden make_icon import in {f}")

    def test_12_machine_readable_error_taxonomy(self):
        """Verifies Law 7: Machine-readable error codes are defined in i18n and server.js."""
        for i18n_file in [ROOT / "web-client" / "js" / "i18n.js", ROOT / "relay-server" / "public" / "js" / "i18n.js"]:
            content = i18n_file.read_text(encoding="utf-8")
            self.assertIn("'RELAY_ROOM_OFFLINE'", content)
            self.assertIn("'RELAY_INVALID_PIN'", content)
            self.assertIn("'AUTH_INVALID_CREDENTIALS'", content)

        server_js = ROOT / "relay-server" / "server.js"
        server_content = server_js.read_text(encoding="utf-8")
        self.assertIn("'RELAY_ROOM_OFFLINE'", server_content)
        self.assertIn("'RELAY_INVALID_PIN'", server_content)
        self.assertIn("'AUTH_INVALID_CREDENTIALS'", server_content)

if __name__ == "__main__":
    unittest.main()

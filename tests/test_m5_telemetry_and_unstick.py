import hashlib
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

class TestM5TelemetryAndUnstick(unittest.TestCase):
    def setUp(self):
        self.web_html = (ROOT / "web-client" / "index.html").read_text(encoding="utf-8")
        self.public_html = (ROOT / "relay-server" / "public" / "index.html").read_text(encoding="utf-8")
        self.web_app = (ROOT / "web-client" / "js" / "app.js").read_text(encoding="utf-8")
        self.public_app = (ROOT / "relay-server" / "public" / "js" / "app.js").read_text(encoding="utf-8")
        self.web_css = (ROOT / "web-client" / "css" / "style.css").read_text(encoding="utf-8")
        self.public_css = (ROOT / "relay-server" / "public" / "css" / "style.css").read_text(encoding="utf-8")
        self.i18n_text = (ROOT / "web-client" / "js" / "i18n.js").read_text(encoding="utf-8")

    def test_badge_telemetry_exists_on_floating_deck(self):
        for html, name in [(self.web_html, "web-client"), (self.public_html, "relay-server/public")]:
            deck_start = html.find('id="floatingDeck"')
            deck_end = html.find('</footer>', deck_start)
            deck_chunk = html[deck_start:deck_end]

            self.assertIn('id="badgeTelemetry"', deck_chunk, f"#badgeTelemetry missing on deck in {name}")
            self.assertIn('id="deckCpuLabel"', deck_chunk, f"#deckCpuLabel missing in {name}")
            self.assertIn('id="deckRamLabel"', deck_chunk, f"#deckRamLabel missing in {name}")
            self.assertIn('class="telemetry-dot', deck_chunk, f"telemetry-dot missing in {name}")

    def test_emergency_unstick_button_exists_on_floating_deck(self):
        for html, name in [(self.web_html, "web-client"), (self.public_html, "relay-server/public")]:
            deck_start = html.find('id="floatingDeck"')
            deck_end = html.find('</footer>', deck_start)
            deck_chunk = html[deck_start:deck_end]

            self.assertIn('id="btnEmergencyUnstick"', deck_chunk, f"#btnEmergencyUnstick missing on deck in {name}")
            self.assertIn('data-i18n="deck_emergency_unstick"', deck_chunk, f"data-i18n missing on unstick button in {name}")
            self.assertIn('<svg', deck_chunk, f"SVG icon missing on deck in {name}")

    def test_app_js_handles_telemetry_pulse(self):
        for app, name in [(self.web_app, "web-client"), (self.public_app, "relay-server/public")]:
            self.assertIn("function handleTelemetryPulse(msg)", app, f"handleTelemetryPulse function missing in {name}")
            self.assertIn("badgeTelemetry", app, f"badgeTelemetry missing in {name}")
            self.assertIn("msg.type === 'telemetry_pulse'", app, f"telemetry_pulse websocket router missing in {name}")

    def test_app_js_handles_emergency_unstick(self):
        for app, name in [(self.web_app, "web-client"), (self.public_app, "relay-server/public")]:
            self.assertIn("emergency_unstick", app, f"emergency_unstick trigger missing in {name}")
            self.assertIn("btnEmergencyUnstick", app, f"btnEmergencyUnstick listener missing in {name}")

    def test_i18n_keys_completeness_and_parity(self):
        def extract(lang):
            p = rf"{lang}\s*:\s*\{{(.*?)\n\s*\}}[,;]?"
            m = re.search(p, self.i18n_text, re.DOTALL)
            items = {}
            for match in re.finditer(r"['\"]([a-zA-Z0-9_.]+)['\"]\s*:\s*['\"](.*?)['\"]", m.group(1)):
                items[match.group(1)] = match.group(2)
            return items

        vi = extract("vi")
        en = extract("en")

        self.assertIn("deck_emergency_unstick", vi)
        self.assertIn("deck_emergency_unstick", en)
        self.assertIn("deck.emergency_unstick", vi)
        self.assertIn("deck.emergency_unstick", en)
        self.assertIn("deck.telemetry_host_title", vi)
        self.assertIn("deck.telemetry_host_title", en)
        self.assertEqual(set(vi.keys()), set(en.keys()), "Parity between VI and EN broken")

    def test_css_styling_for_badge_telemetry(self):
        for css, name in [(self.web_css, "web-client"), (self.public_css, "relay-server/public")]:
            self.assertIn("#badgeTelemetry", css, f"#badgeTelemetry missing in {name} CSS")
            self.assertIn(".deck__telemetry-badge", css, f".deck__telemetry-badge missing in {name} CSS")

    def test_ssot_sha256_match_all_files(self):
        src_dir = ROOT / "web-client"
        dst_dir = ROOT / "relay-server" / "public"
        src_files = [p.relative_to(src_dir) for p in src_dir.rglob("*") if p.is_file()]
        self.assertEqual(len(src_files), 24, "Must have exactly 24 files")
        for rel in src_files:
            sh = hashlib.sha256((src_dir / rel).read_bytes()).hexdigest()
            dh = hashlib.sha256((dst_dir / rel).read_bytes()).hexdigest()
            self.assertEqual(sh, dh, f"SHA256 mismatch for {rel}")

if __name__ == "__main__":
    unittest.main()

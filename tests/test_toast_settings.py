# -*- coding: utf-8 -*-
import unittest
import os
from pathlib import Path

class TestToastSettings(unittest.TestCase):
    def setUp(self):
        self.base_dir = str(Path(__file__).resolve().parent.parent / "relay-server" / "public")
        self.html_path = os.path.join(self.base_dir, "index.html")
        self.css_path = os.path.join(self.base_dir, "css", "style.css")
        self.app_js_path = os.path.join(self.base_dir, "js", "app.js")
        self.i18n_path = os.path.join(self.base_dir, "js", "i18n.js")

    def test_html_contains_toast_switch_and_deck_settings(self):
        with open(self.html_path, "r", encoding="utf-8") as f:
            html = f.read()

        self.assertIn('id="cfgEnableToasts"', html)
        self.assertIn('class="ambient-toggle"', html)
        self.assertIn('id="btnDeckOpenSettings"', html)
        self.assertIn('id="btnOpenSessionConfig"', html)

    def test_css_ambient_toggle(self):
        with open(self.css_path, "r", encoding="utf-8") as f:
            css = f.read()

        self.assertIn('.ambient-toggle', css)
        self.assertIn('.ambient-toggle__slider', css)

    def test_app_js_silenced_clipboard_toasts(self):
        with open(self.app_js_path, "r", encoding="utf-8") as f:
            js = f.read()

        # Check showToast respects meikova_toast_enabled
        self.assertIn("meikova_toast_enabled", js)
        self.assertIn("cfgEnableToasts", js)
        self.assertIn("openSettingsModal", js)

        # Check clipboard_sync_ack does NOT show toast on success
        ack_idx = js.find("msg.type === 'clipboard_sync_ack'")
        self.assertNotEqual(ack_idx, -1)
        ack_block = js[ack_idx:ack_idx+300]
        self.assertNotIn("showToast(t('toast.clip_sync_success')", ack_block)

    def test_i18n_keys(self):
        with open(self.i18n_path, "r", encoding="utf-8") as f:
            i18n = f.read()

        self.assertIn("settings.toasts_label", i18n)
        self.assertIn("deck.settings_title", i18n)

if __name__ == '__main__':
    unittest.main()

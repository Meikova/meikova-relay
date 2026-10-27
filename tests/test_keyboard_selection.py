# -*- coding: utf-8 -*-
import unittest
import os
import re
from pathlib import Path

class TestKeyboardSelection(unittest.TestCase):
    def setUp(self):
        self.base_dir = str(Path(__file__).resolve().parent.parent / "relay-server" / "public")
        self.html_path = os.path.join(self.base_dir, "index.html")
        self.css_path = os.path.join(self.base_dir, "css", "style.css")
        self.app_js_path = os.path.join(self.base_dir, "js", "app.js")
        self.i18n_path = os.path.join(self.base_dir, "js", "i18n.js")

    def test_html_contains_keyboard_selector_elements(self):
        with open(self.html_path, "r", encoding="utf-8") as f:
            html = f.read()

        # Keyboard popover menu
        self.assertIn('id="keyboardMenuDropdown"', html)
        self.assertIn('id="btnOptPhoneKeyboard"', html)
        self.assertIn('id="btnOptVirtualOSK"', html)
        self.assertIn('id="checkPhoneKeyboard"', html)
        self.assertIn('id="checkVirtualOSK"', html)
        # Mobile keyboard button with chevron and label
        self.assertIn('id="btnMobileKeyboard"', html)
        self.assertIn('id="keyboardCurrentLabel"', html)
        # OSK close button
        self.assertIn('id="btnCloseOSK"', html)

    def test_css_contains_keyboard_menu_styles(self):
        with open(self.css_path, "r", encoding="utf-8") as f:
            css = f.read()

        self.assertIn('.keyboard-menu', css)
        self.assertIn('.osk-header', css)
        self.assertIn('.osk-close-btn', css)

    def test_i18n_keys(self):
        with open(self.i18n_path, "r", encoding="utf-8") as f:
            i18n = f.read()

        self.assertIn('deck.keyboard_menu_title', i18n)
        self.assertIn('deck.keyboard_menu_header', i18n)
        self.assertIn('deck.kb_phone_title', i18n)
        self.assertIn('deck.kb_osk_title', i18n)
        self.assertIn('toast.osk_opened', i18n)
        self.assertIn('toast.osk_closed', i18n)

    def test_app_js_keyboard_logic(self):
        with open(self.app_js_path, "r", encoding="utf-8") as f:
            js = f.read()

        self.assertIn('updateKeyboardMenuUI', js)
        self.assertIn('meikova_keyboard_pref', js)
        self.assertIn('btnOptPhoneKeyboard', js)
        self.assertIn('btnOptVirtualOSK', js)
        self.assertIn('btnCloseOSK', js)

if __name__ == '__main__':
    unittest.main()

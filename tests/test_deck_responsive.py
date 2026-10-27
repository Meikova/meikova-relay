# -*- coding: utf-8 -*-
import unittest
import os
import re
from pathlib import Path

class TestDeckResponsive(unittest.TestCase):
    def setUp(self):
        self.base_dir = str(Path(__file__).resolve().parent.parent / "relay-server" / "public")
        self.css_path = os.path.join(self.base_dir, "css", "style.css")
        self.app_js_path = os.path.join(self.base_dir, "js", "app.js")

    def test_monitor_menu_not_self_hiding(self):
        with open(self.app_js_path, "r", encoding="utf-8") as f:
            js = f.read()

        # Extract btnMonitorMenu click listener block
        idx = js.find("btnMonitorMenu.addEventListener('click'")
        self.assertNotEqual(idx, -1, "btnMonitorMenu listener not found")
        block = js[idx:idx+1500]
        # In the isOpening branch, it should NOT hide itself
        is_opening_idx = block.find("if (isOpening)")
        self.assertNotEqual(is_opening_idx, -1)
        opening_block = block[is_opening_idx:is_opening_idx+500]
        self.assertNotIn("monitorMenuDropdown?.classList.add('hidden')", opening_block)
        self.assertNotIn("btnMonitorMenu?.classList.remove('btn-active')", opening_block)

    def test_css_deck_flex_shrink(self):
        with open(self.css_path, "r", encoding="utf-8") as f:
            css = f.read()

        self.assertIn("flex-shrink: 0;", css)
        self.assertIn("scroll-behavior: smooth;", css)
        self.assertIn(".deck::-webkit-scrollbar", css)
        self.assertIn("@media (max-width: 1280px)", css)
        self.assertIn("@media (max-width: 1120px)", css)
        self.assertIn("@media (max-width: 960px)", css)

    def test_deck_wheel_and_drag(self):
        with open(self.app_js_path, "r", encoding="utf-8") as f:
            js = f.read()

        self.assertIn("floatingDeck.addEventListener('wheel'", js)
        self.assertIn("floatingDeck.addEventListener('mousedown'", js)
        self.assertIn("floatingDeck.addEventListener('scroll'", js)

if __name__ == '__main__':
    unittest.main()

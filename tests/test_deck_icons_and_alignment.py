# -*- coding: utf-8 -*-
import unittest
import os
import re
from pathlib import Path
from bs4 import BeautifulSoup

class TestDeckIconsAndAlignment(unittest.TestCase):
    def setUp(self):
        self.base_dir = Path(__file__).resolve().parent.parent / "relay-server" / "public"
        self.html_path = self.base_dir / "index.html"
        self.css_path = self.base_dir / "css" / "style.css"

    def test_deck_buttons_have_distinct_svg_icons(self):
        with open(self.html_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "html.parser")

        # 1. OSK button vs Shortcuts button
        btn_osk = soup.find(id="btnToggleOSK")
        btn_shortcuts = soup.find(id="btnShortcutsMenu")
        self.assertIsNotNone(btn_osk, "btnToggleOSK must exist")
        self.assertIsNotNone(btn_shortcuts, "btnShortcutsMenu must exist")

        svg_osk = "".join(str(c) for c in btn_osk.find("svg").children if c.name)
        svg_shortcuts = "".join(str(c) for c in btn_shortcuts.find("svg").children if c.name)
        self.assertNotEqual(svg_osk, svg_shortcuts, "btnToggleOSK and btnShortcutsMenu must not have duplicate SVGs")

        # 2. Monitor menu vs Resolution menu
        btn_mon = soup.find(id="btnMonitorMenu")
        btn_res = soup.find(id="btnResolutionMenu")
        self.assertIsNotNone(btn_mon, "btnMonitorMenu must exist")
        self.assertIsNotNone(btn_res, "btnResolutionMenu must exist")

        svg_mon = "".join(str(c) for c in btn_mon.find("svg").children if c.name)
        svg_res = "".join(str(c) for c in btn_res.find("svg").children if c.name)
        self.assertNotEqual(svg_mon, svg_res, "btnMonitorMenu and btnResolutionMenu must not have duplicate SVGs")

    def test_menu_items_use_vibrant_vector_svg_icons(self):
        with open(self.html_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "html.parser")

        # Check Tools Menu items have SVG icons
        tools_dropdown = soup.find(id="moreToolsMenuDropdown")
        self.assertIsNotNone(tools_dropdown, "moreToolsMenuDropdown must exist")
        tool_icons = tools_dropdown.find_all("span", class_="quality-item-icon")
        self.assertGreaterEqual(len(tool_icons), 8, "All tools items must have quality-item-icon")
        for icon in tool_icons:
            self.assertIsNotNone(icon.find("svg"), "Every quality-item-icon must have an inline svg")

        # Check Shortcuts Menu items have SVG icons
        shortcuts_dropdown = soup.find(id="shortcutsMenuDropdown")
        self.assertIsNotNone(shortcuts_dropdown, "shortcutsMenuDropdown must exist")
        shortcut_icons = shortcuts_dropdown.find_all("span", class_="quality-item-icon")
        self.assertGreaterEqual(len(shortcut_icons), 20, "All shortcuts items must have quality-item-icon")
        for icon in shortcut_icons:
            self.assertIsNotNone(icon.find("svg"), "Every quality-item-icon must have an inline svg")

    def test_quality_item_icon_css(self):
        with open(self.css_path, "r", encoding="utf-8") as f:
            css = f.read()

        match = re.search(r"\.quality-item-icon\s*\{([^}]+)\}", css)
        self.assertIsNotNone(match, ".quality-item-icon rule must exist in style.css")
        body = match.group(1)

        self.assertIn("width: 28px;", body)
        self.assertIn("height: 28px;", body)
        self.assertIn("min-width: 28px;", body)
        self.assertIn("max-width: 28px;", body)

    def test_quality_group_headers_aligned(self):
        with open(self.css_path, "r", encoding="utf-8") as f:
            css = f.read()

        self.assertIn(".quality-group-header", css)
        self.assertIn(".shortcuts-menu", css)
        self.assertIn(".tools-menu", css)

if __name__ == '__main__':
    unittest.main()

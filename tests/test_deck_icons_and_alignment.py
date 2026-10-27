# -*- coding: utf-8 -*-
import unittest
import os
import re
from pathlib import Path

class TestDeckIconsAndAlignment(unittest.TestCase):
    def setUp(self):
        self.base_dir = Path(__file__).resolve().parent.parent / "relay-server" / "public"
        self.html_path = self.base_dir / "index.html"
        self.css_path = self.base_dir / "css" / "style.css"

    def _extract_element(self, html: str, element_id: str) -> str:
        pattern = rf'<button[^>]*id=["\']{element_id}["\'][^>]*>(.*?)</button>'
        m = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
        if not m:
            pattern = rf'<([a-zA-Z0-9]+)[^>]*id=["\']{element_id}["\'][^>]*>(.*?)</\1>'
            m = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
        return m.group(0) if m else None

    def _extract_svg(self, html_snippet: str) -> str:
        m = re.search(r'<svg[^>]*>(.*?)</svg>', html_snippet, re.DOTALL | re.IGNORECASE)
        return m.group(1).strip() if m else ""

    def test_deck_buttons_have_distinct_svg_icons(self):
        with open(self.html_path, "r", encoding="utf-8") as f:
            html = f.read()

        # 1. OSK button vs Shortcuts button
        btn_osk = self._extract_element(html, "btnToggleOSK")
        btn_shortcuts = self._extract_element(html, "btnShortcutsMenu")
        self.assertIsNotNone(btn_osk, "btnToggleOSK must exist")
        self.assertIsNotNone(btn_shortcuts, "btnShortcutsMenu must exist")

        svg_osk = self._extract_svg(btn_osk)
        svg_shortcuts = self._extract_svg(btn_shortcuts)
        self.assertTrue(len(svg_osk) > 0, "btnToggleOSK must contain svg")
        self.assertTrue(len(svg_shortcuts) > 0, "btnShortcutsMenu must contain svg")
        self.assertNotEqual(svg_osk, svg_shortcuts, "btnToggleOSK and btnShortcutsMenu must not have duplicate SVGs")

        # 2. Monitor menu vs Resolution menu
        btn_mon = self._extract_element(html, "btnMonitorMenu")
        btn_res = self._extract_element(html, "btnResolutionMenu")
        self.assertIsNotNone(btn_mon, "btnMonitorMenu must exist")
        self.assertIsNotNone(btn_res, "btnResolutionMenu must exist")

        svg_mon = self._extract_svg(btn_mon)
        svg_res = self._extract_svg(btn_res)
        self.assertTrue(len(svg_mon) > 0, "btnMonitorMenu must contain svg")
        self.assertTrue(len(svg_res) > 0, "btnResolutionMenu must contain svg")
        self.assertNotEqual(svg_mon, svg_res, "btnMonitorMenu and btnResolutionMenu must not have duplicate SVGs")

    def test_menu_items_use_vibrant_vector_svg_icons(self):
        with open(self.html_path, "r", encoding="utf-8") as f:
            html = f.read()

        tools_start = html.find('id="moreToolsMenuDropdown"')
        self.assertGreater(tools_start, 0, "moreToolsMenuDropdown must exist")
        shortcuts_start = html.find('id="shortcutsMenuDropdown"')
        self.assertGreater(shortcuts_start, 0, "shortcutsMenuDropdown must exist")
        shortcuts_end = html.find('</nav>', shortcuts_start)

        tools_chunk = html[tools_start:shortcuts_start]
        shortcuts_chunk = html[shortcuts_start:shortcuts_end]

        icon_pattern = r'<span[^>]*class=["\'][^"\']*quality-item-icon[^"\']*["\'][^>]*>(.*?)</span>'
        tool_icons = re.findall(icon_pattern, tools_chunk, re.DOTALL)
        self.assertGreaterEqual(len(tool_icons), 8, "All tools items must have quality-item-icon")
        for icon_html in tool_icons:
            self.assertIn("<svg", icon_html, "Every quality-item-icon must have an inline svg")

        shortcut_icons = re.findall(icon_pattern, shortcuts_chunk, re.DOTALL)
        self.assertGreaterEqual(len(shortcut_icons), 20, "All shortcuts items must have quality-item-icon")
        for icon_html in shortcut_icons:
            self.assertIn("<svg", icon_html, "Every quality-item-icon must have an inline svg")

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

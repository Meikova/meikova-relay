import os
import re
import unittest
from pathlib import Path

class TestI18nEngine(unittest.TestCase):
    def setUp(self):
        self.i18n_path = Path(__file__).resolve().parent.parent / "web-client" / "js" / "i18n.js"
        self.assertTrue(self.i18n_path.exists(), "i18n.js must exist")
        self.content = self.i18n_path.read_text(encoding="utf-8")

    def _extract_dict(self, lang_name):
        """Extract key-value pairs for a language section using regex."""
        # Find start of lang section, e.g. vi: { or en: {
        pattern = rf"{lang_name}\s*:\s*\{{(.*?)\n\s*\}}[,;]?"
        match = re.search(pattern, self.content, re.DOTALL)
        self.assertIsNotNone(match, f"Language '{lang_name}' section not found in i18n.js")
        section = match.group(1)

        # Extract 'key': 'value' or "key": "value"
        items = {}
        for m in re.finditer(r"['\"]([a-zA-Z0-9_.]+)['\"]\s*:\s*['\"](.*?)['\"]", section):
            items[m.group(1)] = m.group(2)
        return items

    def test_translation_dictionaries_loaded(self):
        vi = self._extract_dict("vi")
        en = self._extract_dict("en")

        self.assertGreater(len(vi), 70, "Vietnamese dictionary must have comprehensive keys")
        self.assertGreater(len(en), 70, "English dictionary must have comprehensive keys")

    def test_key_parity_between_vi_and_en(self):
        vi = self._extract_dict("vi")
        en = self._extract_dict("en")

        missing_in_en = set(vi.keys()) - set(en.keys())
        missing_in_vi = set(en.keys()) - set(vi.keys())

        self.assertEqual(missing_in_en, set(), f"Keys missing in EN: {missing_in_en}")
        self.assertEqual(missing_in_vi, set(), f"Keys missing in VI: {missing_in_vi}")

    def test_no_empty_translations(self):
        vi = self._extract_dict("vi")
        en = self._extract_dict("en")

        for k, v in vi.items():
            self.assertTrue(bool(v.strip()), f"Empty VI value for key: {k}")
        for k, v in en.items():
            self.assertTrue(bool(v.strip()), f"Empty EN value for key: {k}")

    def test_interpolation_placeholders_match(self):
        vi = self._extract_dict("vi")
        en = self._extract_dict("en")

        for key in vi:
            vi_placeholders = set(re.findall(r"\{(\w+)\}", vi[key]))
            en_placeholders = set(re.findall(r"\{(\w+)\}", en[key]))
            self.assertEqual(
                vi_placeholders,
                en_placeholders,
                f"Placeholder mismatch for '{key}': VI has {vi_placeholders}, EN has {en_placeholders}"
            )

    def test_extensibility_interface_present(self):
        self.assertIn("registerLang", self.content)
        self.assertIn("getSupportedLangs", self.content)
        self.assertIn("applyTranslations", self.content)
        self.assertIn("setLang", self.content)
        self.assertIn("meikova-lang-changed", self.content)

    def test_app_js_dashboard_instant_i18n_render(self):
        app_js_path = Path(__file__).resolve().parent.parent / "web-client" / "js" / "app.js"
        self.assertTrue(app_js_path.exists(), "app.js must exist")
        app_content = app_js_path.read_text(encoding="utf-8")

        # 1. Verify deviceGrid empty state contains data-i18n attributes
        self.assertIn('data-i18n="dashboard.empty"', app_content)
        self.assertIn('data-i18n="dashboard.empty_hint"', app_content)
        self.assertIn('data-i18n="dashboard.btn_download_host"', app_content)
        self.assertIn('data-i18n="dashboard.btn_quick_connect"', app_content)

        # 2. Verify deviceGrid device cards contain data-i18n attributes
        self.assertIn('data-i18n="dashboard.btn_connect"', app_content)

        # 3. Verify currentDeviceList caching
        self.assertIn('let currentDeviceList = [];', app_content)

        # 4. Verify meikova-lang-changed immediately re-renders dashboard
        pattern = r"window\.addEventListener\('meikova-lang-changed',.*?\n\s*if\s*\(\s*currentView\s*===\s*'dashboard'\s*\)\s*\{\s*renderDeviceGrid\(currentDeviceList\);\s*\}"
        self.assertIsNotNone(
            re.search(pattern, app_content, re.DOTALL),
            "meikova-lang-changed listener must immediately re-render deviceGrid on dashboard view"
        )

        # 5. Verify updateRoStatus is called in meikova-lang-changed
        self.assertIn("updateRoStatus();", app_content)


    def test_zero_missing_html_and_js_i18n_keys(self):
        """Ensure every single data-i18n* attribute in index.html and t(...) call in app.js exists in both VI and EN dictionaries."""
        root = Path(__file__).resolve().parents[1]
        html_text = (root / "relay-server" / "public" / "index.html").read_text(encoding="utf-8")
        app_text = (root / "relay-server" / "public" / "js" / "app.js").read_text(encoding="utf-8")

        vi_keys = set(self._extract_dict("vi").keys())
        en_keys = set(self._extract_dict("en").keys())

        used_html_keys = set(re.findall(r"data-i18n(?:-[a-z]+)?=[\x27\"]([^\x27\"]+)[\x27\"]", html_text))
        used_js_keys = set(re.findall(r"\bti?\(\s*[\x27\"]([a-zA-Z0-9_.-]+)[\x27\"]", app_text))

        missing_html_vi = used_html_keys - vi_keys
        missing_html_en = used_html_keys - en_keys
        missing_js_vi = used_js_keys - vi_keys
        missing_js_en = used_js_keys - en_keys

        self.assertEqual(missing_html_vi, set(), f"HTML data-i18n keys missing in VI: {missing_html_vi}")
        self.assertEqual(missing_html_en, set(), f"HTML data-i18n keys missing in EN: {missing_html_en}")
        self.assertEqual(missing_js_vi, set(), f"JS t() keys missing in VI: {missing_js_vi}")
        self.assertEqual(missing_js_en, set(), f"JS t() keys missing in EN: {missing_js_en}")


if __name__ == "__main__":
    unittest.main()

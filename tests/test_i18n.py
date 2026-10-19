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
        self.assertIn("titan-lang-changed", self.content)

if __name__ == "__main__":
    unittest.main()

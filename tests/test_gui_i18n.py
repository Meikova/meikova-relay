import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import unittest
import re
try:
    import tkinter as tk
except ImportError:
    class _TkStub:
        TclError = RuntimeError
        @staticmethod
        def Tk():
            raise RuntimeError("Tkinter unavailable")
    tk = _TkStub()
from host_agent.gui_agent import TRANSLATIONS, MeikovaRelayHostGUI

class TestGuiI18n(unittest.TestCase):
    def test_translation_dictionaries_parity(self):
        vi_keys = set(TRANSLATIONS["vi"].keys())
        en_keys = set(TRANSLATIONS["en"].keys())

        missing_in_en = vi_keys - en_keys
        missing_in_vi = en_keys - vi_keys

        self.assertEqual(missing_in_en, set(), f"Keys missing in EN: {missing_in_en}")
        self.assertEqual(missing_in_vi, set(), f"Keys missing in VI: {missing_in_vi}")
        self.assertGreater(len(vi_keys), 30, "Must have comprehensive translations")

    def test_no_empty_translations(self):
        for lang in ("vi", "en"):
            for k, v in TRANSLATIONS[lang].items():
                self.assertTrue(bool(v.strip()), f"Empty value in {lang} for key {k}")

    def test_placeholder_parity(self):
        for k in TRANSLATIONS["vi"]:
            vi_ph = set(re.findall(r"\{(\w+)\}", TRANSLATIONS["vi"][k]))
            en_ph = set(re.findall(r"\{(\w+)\}", TRANSLATIONS["en"][k]))
            self.assertEqual(vi_ph, en_ph, f"Placeholder mismatch for key: {k}")

    def test_zero_competitor_names(self):
        competitor_keywords = [
            "ultraviewer", "ultra viewer",
            "teamviewer", "team viewer",
            "chrome remote desktop", "chrome remote",
            "anydesk", "any desk"
        ]
        from pathlib import Path
        gui_file = Path(__file__).resolve().parent.parent / "host_agent" / "gui_agent.py"
        content_lower = gui_file.read_text(encoding="utf-8").lower()
        for kw in competitor_keywords:
            self.assertNotIn(kw, content_lower, f"Found competitor keyword '{kw}' in gui_agent.py")

    def test_gui_language_switching(self):
        try:
            root = tk.Tk()
            root.withdraw()
        except tk.TclError:
            self.skipTest("Tkinter display unavailable in test environment")

        try:
            app = MeikovaRelayHostGUI(root)
            self.assertEqual(app.lang, "vi")
            self.assertEqual(app.btn_tab_ultra.cget("text"), TRANSLATIONS["vi"]["tab_ultra"])

            # Switch to EN
            app._set_language("en")
            self.assertEqual(app.lang, "en")
            self.assertEqual(app.btn_tab_ultra.cget("text"), TRANSLATIONS["en"]["tab_ultra"])
            self.assertEqual(app.lbl_ultra_title.cget("text"), TRANSLATIONS["en"]["ultra_title"])

            # Switch back to VI
            app._set_language("vi")
            self.assertEqual(app.lang, "vi")
            self.assertEqual(app.btn_tab_ultra.cget("text"), TRANSLATIONS["vi"]["tab_ultra"])
        finally:
            try:
                root.destroy()
            except Exception:
                pass
            tk._default_root = None
            try:
                del app
            except Exception:
                pass
            try:
                del root
            except Exception:
                pass
            import gc
            gc.collect()

if __name__ == "__main__":
    unittest.main()

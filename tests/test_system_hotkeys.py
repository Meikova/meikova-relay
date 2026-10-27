import unittest
import sys
from pathlib import Path

# Add host_agent to sys.path
AGENT_DIR = Path(__file__).resolve().parent.parent / "host_agent"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from unittest.mock import patch
from input_injector import InputInjector

class TestSystemHotkeys(unittest.TestCase):
    @patch("ctypes.windll.user32.LockWorkStation", return_value=1, create=True)
    @patch("subprocess.Popen")
    def test_hotkey_combinations_supported(self, mock_popen, mock_lock):
        combos = [
            "cad", "lock", "taskmgr", "win_d", "win_e", "win_r",
            "win_x", "win_v", "win_shift_s", "win_i", "win_a",
            "win_tab", "win_ctrl_d", "ctrl_w", "ctrl_shift_t",
            "alttab", "altf4", "win", "esc", "ctrl_win_del"
        ]
        for combo in combos:
            res = InputInjector.trigger_system_hotkey(combo)
            self.assertTrue(res, f"Combo {combo} failed execution")

    def test_html_and_i18n_dropdown_structure(self):
        html_file = Path(__file__).resolve().parent.parent / "relay-server" / "public" / "index.html"
        i18n_file = Path(__file__).resolve().parent.parent / "relay-server" / "public" / "js" / "i18n.js"
        
        html_content = html_file.read_text(encoding="utf-8")
        i18n_content = i18n_file.read_text(encoding="utf-8")

        # Shortcuts dropdown check
        self.assertIn('id="btnShortcutsMenu"', html_content)
        self.assertIn('id="shortcutsMenuDropdown"', html_content)
        self.assertIn('data-system-combo="cad"', html_content)
        self.assertIn('data-system-combo="ctrl_win_del"', html_content)
        self.assertIn('data-system-combo="win_x"', html_content)
        self.assertIn('data-system-combo="win_v"', html_content)
        self.assertIn('data-system-combo="win_shift_s"', html_content)
        self.assertIn('data-system-combo="win_i"', html_content)
        self.assertIn('data-system-combo="win_a"', html_content)

        # More Tools dropdown check
        self.assertIn('id="btnMoreToolsMenu"', html_content)
        self.assertIn('id="moreToolsMenuDropdown"', html_content)
        self.assertIn('id="btnDropdownWhiteboard"', html_content)
        self.assertIn('id="btnDropdownLaser"', html_content)
        self.assertIn('id="btnDropdownScreenshot"', html_content)
        self.assertIn('id="btnDropdownRecord"', html_content)
        self.assertIn('id="btnDropdownCam"', html_content)
        self.assertIn('id="btnDropdownBlockInput"', html_content)
        self.assertIn('id="btnDropdownCurtain"', html_content)

        # Check i18n
        self.assertIn("'deck.shortcuts_title'", i18n_content)
        self.assertIn("'deck.tools_menu_title'", i18n_content)
        self.assertIn("'deck.combo_win_shift_s'", i18n_content)
        self.assertIn("'deck.tools_whiteboard'", i18n_content)
        self.assertIn("'deck.tools_curtain'", i18n_content)

if __name__ == "__main__":
    unittest.main()

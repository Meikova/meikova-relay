import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import json
import asyncio
import os
import sys
from pathlib import Path

# Enable Test Mode to completely protect physical host from reboot, lock or input interference
os.environ["MEIKOVA_TEST_MODE"] = "1"

# Add project root and host_agent to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
AGENT_DIR = BASE_DIR / "host_agent"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import host_service
from host_service import HostService

class MockCapture:
    def __init__(self):
        self.resolution = (1920, 1080)
        self.monitors = [{"id": 0, "name": "Display 1", "rect": (0, 0, 1920, 1080)}]

class TestDeckButtonsAndAdminPrivileges(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        os.environ["MEIKOVA_TEST_MODE"] = "1"
        self.html_path = BASE_DIR / "relay-server" / "public" / "index.html"
        self.app_js_path = BASE_DIR / "relay-server" / "public" / "js" / "app.js"
        self.i18n_path = BASE_DIR / "relay-server" / "public" / "js" / "i18n.js"

    # --- 1. TEST EVERY SINGLE BUTTON ON DECK AND SUBMENUS IN HTML ---
    def test_all_deck_buttons_exist_in_html(self):
        html = self.html_path.read_text(encoding="utf-8")

        # 11 Core Deck Buttons
        core_deck_buttons = [
            'id="btnDeckDisplayMode"',
            'id="btnDeckPinQuick"',
            'id="btnToggleAudio"',
            'id="btnToggleMic"',
            'id="btnToggleOSK"',
            'id="btnShortcutsMenu"',
            'id="btnMoreToolsMenu"',
            'id="btnPowerMenu"',
            'id="btnViewerChat"',
            'id="btnOpenShelf"',
            'id="btnDisconnect"'
        ]
        for btn in core_deck_buttons:
            self.assertIn(btn, html, f"Core deck button missing: {btn}")

        # Extra Tools in moreToolsMenuDropdown
        tools_buttons = [
            'id="btnDropdownWhiteboard"',
            'id="btnDropdownLaser"',
            'id="btnDropdownScreenshot"',
            'id="btnDropdownRecord"',
            'id="btnDropdownCam"',
            'id="btnDropdownBlockInput"',
            'id="btnDropdownCurtain"',
            'id="btnDropdownSnippets"'
        ]
        for btn in tools_buttons:
            self.assertIn(btn, html, f"Tools menu item missing: {btn}")

        # Shortcuts Menu Combos
        expected_combos = [
            "cad", "ctrl_win_del", "lock", "taskmgr", "win_x", "win_v",
            "win_shift_s", "win_i", "win_a", "win_tab", "win_ctrl_d",
            "ctrl_w", "ctrl_shift_t", "win_d", "win_e", "win_r",
            "alttab", "altf4", "win", "esc"
        ]
        for combo in expected_combos:
            self.assertIn(f'data-system-combo="{combo}"', html, f"Shortcut combo missing: {combo}")

        # Power Menu Items
        self.assertIn('data-power="lock"', html)
        self.assertIn('data-power="restart"', html)

    # --- 2. TEST I18N COMPLETENESS FOR ADMIN & TOOL TOASTS ---
    def test_i18n_admin_and_tool_keys(self):
        i18n = self.i18n_path.read_text(encoding="utf-8")
        admin_keys = [
            "'toast.requires_admin'",
            "'toast.requires_admin_block_input'",
            "'toast.requires_admin_curtain'",
            "'toast.requires_admin_hotkey'",
            "'toast.requires_admin_power'"
        ]
        for k in admin_keys:
            self.assertIn(k, i18n, f"i18n key missing: {k}")

    # --- 3. TEST ADMIN PRIVILEGE ELEVATION: HOST HAS ADMIN RIGHTS ---
    @patch("host_service.is_current_user_admin", return_value=True)
    @patch("host_service.InputInjector.set_block_input", return_value=True)
    @patch("host_service.privacy_curtain.enable", return_value={"success": True, "active": True})
    @patch("host_service.privacy_curtain.disable", return_value={"success": True, "active": False})
    @patch("host_service.PowerManager.restart_machine", return_value=True)
    @patch("host_service.PowerManager.lock_workstation", return_value=True)
    @patch("host_service.InputInjector.trigger_system_hotkey", return_value=True)
    async def test_admin_actions_when_host_has_admin(
        self, mock_hotkey, mock_lock, mock_restart, mock_curtain_disable,
        mock_curtain_enable, mock_block_input, mock_is_admin
    ):
        service = HostService(relay_url="ws://localhost:9999", room_id="TEST_ADMIN_ROOM", pin="123456")
        service.capture = MockCapture()
        mock_ws = AsyncMock()

        # A. Block Input (Should Succeed)
        await service.handle_control_event(json.dumps({"type": "block_input", "blocked": True}), mock_ws)
        sent = json.loads(mock_ws.send.call_args[0][0])
        self.assertEqual(sent["type"], "block_input_response")
        self.assertTrue(sent["success"])
        self.assertFalse(sent.get("requires_admin", False))

        # B. Toggle Privacy Curtain (Should Succeed)
        await service.handle_control_event(json.dumps({"type": "toggle_privacy_curtain", "enabled": True}), mock_ws)
        sent = json.loads(mock_ws.send.call_args[0][0])
        self.assertEqual(sent["type"], "privacy_curtain_response")
        self.assertTrue(sent["success"])
        self.assertFalse(sent.get("requires_admin", False))

        # C. System Hotkey: CAD (Ctrl+Alt+Del) (Should Succeed)
        await service.handle_control_event(json.dumps({"type": "system_hotkey", "combo": "cad"}), mock_ws)
        sent = json.loads(mock_ws.send.call_args[0][0])
        self.assertEqual(sent["type"], "system_hotkey_response")
        self.assertTrue(sent["success"])
        self.assertFalse(sent.get("requires_admin", False))

        # D. Power Action: Restart (Should Succeed)
        await service.handle_control_event(json.dumps({"type": "power_action", "action": "restart"}), mock_ws)
        sent = json.loads(mock_ws.send.call_args[0][0])
        self.assertEqual(sent["type"], "power_action_response")
        self.assertTrue(sent["success"])
        self.assertFalse(sent.get("requires_admin", False))
        mock_restart.assert_called_once()

    # --- 4. TEST ADMIN PRIVILEGE ENFORCEMENT: HOST DOES NOT HAVE ADMIN RIGHTS ---
    @patch("host_service.is_current_user_admin", return_value=False)
    @patch("sys.platform", "win32")
    @patch("host_service.InputInjector.set_block_input", return_value=False)
    @patch("host_service.privacy_curtain.enable")
    @patch("host_service.PowerManager.restart_machine")
    @patch("host_service.PowerManager.lock_workstation", return_value=True)
    @patch("host_service.InputInjector.trigger_system_hotkey", return_value=False)
    async def test_admin_actions_when_host_lacks_admin_rejects_with_error(
        self, mock_hotkey, mock_lock, mock_restart, mock_curtain_enable,
        mock_block_input, mock_is_admin
    ):
        service = HostService(relay_url="ws://localhost:9999", room_id="TEST_NO_ADMIN_ROOM", pin="123456")
        service.capture = MockCapture()
        mock_ws = AsyncMock()

        # A. Block Input: Rejected with ADMIN_PRIVILEGES_REQUIRED
        await service.handle_control_event(json.dumps({"type": "block_input", "blocked": True}), mock_ws)
        sent = json.loads(mock_ws.send.call_args[0][0])
        self.assertEqual(sent["type"], "block_input_response")
        self.assertFalse(sent["success"])
        self.assertTrue(sent["requires_admin"])
        self.assertEqual(sent["error"], "ADMIN_PRIVILEGES_REQUIRED")
        mock_block_input.assert_not_called()

        # B. Toggle Privacy Curtain: Rejected with ADMIN_PRIVILEGES_REQUIRED
        await service.handle_control_event(json.dumps({"type": "toggle_privacy_curtain", "enabled": True}), mock_ws)
        sent = json.loads(mock_ws.send.call_args[0][0])
        self.assertEqual(sent["type"], "privacy_curtain_response")
        self.assertFalse(sent["success"])
        self.assertTrue(sent["requires_admin"])
        self.assertEqual(sent["error"], "ADMIN_PRIVILEGES_REQUIRED")
        mock_curtain_enable.assert_not_called()

        # C. System Hotkey CAD: reports requires_admin
        await service.handle_control_event(json.dumps({"type": "system_hotkey", "combo": "cad"}), mock_ws)
        sent = json.loads(mock_ws.send.call_args[0][0])
        self.assertEqual(sent["type"], "system_hotkey_response")
        self.assertTrue(sent["requires_admin"])

        # D. Power Action: Restart rejected with ADMIN_PRIVILEGES_REQUIRED
        await service.handle_control_event(json.dumps({"type": "power_action", "action": "restart"}), mock_ws)
        sent = json.loads(mock_ws.send.call_args[0][0])
        self.assertEqual(sent["type"], "power_action_response")
        self.assertFalse(sent["success"])
        self.assertTrue(sent["requires_admin"])
        self.assertEqual(sent["error"], "ADMIN_PRIVILEGES_REQUIRED")
        mock_restart.assert_not_called()

        # E. Power Action: Lock Workstation should still succeed for standard user (non-destructive)
        await service.handle_control_event(json.dumps({"type": "power_action", "action": "lock"}), mock_ws)
        sent = json.loads(mock_ws.send.call_args[0][0])
        self.assertEqual(sent["type"], "power_action_response")
        self.assertTrue(sent["success"])
        self.assertFalse(sent["requires_admin"])
        mock_lock.assert_called_once()

    # --- 5. TEST NON-PRIVILEGED SHORTCUTS (NO INTERFERENCE WITH HOST) ---
    @patch("host_service.is_current_user_admin", return_value=False)
    @patch("host_service.InputInjector.trigger_system_hotkey", return_value=True)
    async def test_non_privileged_hotkeys_succeed_for_standard_user(self, mock_hotkey, mock_is_admin):
        service = HostService(relay_url="ws://localhost:9999", room_id="TEST_STD_ROOM", pin="123456")
        service.capture = MockCapture()
        mock_ws = AsyncMock()

        # Test safe non-intrusive combos
        combos = ["win_d", "win_e", "win_r", "win_v", "win_shift_s", "alttab", "altf4", "win", "esc"]
        for combo in combos:
            await service.handle_control_event(json.dumps({"type": "system_hotkey", "combo": combo}), mock_ws)
            sent = json.loads(mock_ws.send.call_args[0][0])
            self.assertEqual(sent["type"], "system_hotkey_response")
            self.assertTrue(sent["success"])
            self.assertFalse(sent["requires_admin"])

if __name__ == "__main__":
    unittest.main()

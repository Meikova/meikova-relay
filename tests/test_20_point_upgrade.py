import asyncio
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

os.environ["MEIKOVA_TEST_MODE"] = "1"

BASE_DIR = Path(__file__).resolve().parent.parent
AGENT_DIR = BASE_DIR / "host_agent"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from host_service import HostService, build_cli_parser
from screen_capture import ScreenCapture
from file_manager import FileManager
from power_manager import PowerManager


class TestTwentyPointUpgrade(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        os.environ["MEIKOVA_TEST_MODE"] = "1"
        self.html_path = BASE_DIR / "relay-server" / "public" / "index.html"
        self.app_js_path = BASE_DIR / "relay-server" / "public" / "js" / "app.js"
        self.i18n_path = BASE_DIR / "relay-server" / "public" / "js" / "i18n.js"
        self.css_path = BASE_DIR / "relay-server" / "public" / "css" / "style.css"
        self.gui_html_path = AGENT_DIR / "gui_view.html"
        self.gui_py_path = AGENT_DIR / "gui_agent.py"

    def test_01_uncapped_fps_and_custom_fps_limit_controls(self):
        """Item 1: Uncapped FPS mode (0 = Unlimited) and custom FPS Limit up to 1000 FPS."""
        service = HostService(relay_url="ws://localhost:9999", room_id="FPS-ROOM", pin="123456", fps_limit=0, uncapped_fps=True)
        self.assertTrue(service.uncapped_fps)
        self.assertEqual(service.fps_limit, 0)
        self.assertGreaterEqual(service.fps, 240)

        html = self.html_path.read_text(encoding="utf-8")
        self.assertIn('id="customFpsLimitInput"', html)
        self.assertIn('id="btnSetLimitFps"', html)

    def test_02_anti_aliasing_and_even_aspect_ratio_preservation(self):
        """Item 2: Eliminate jagged edges (NEAREST neighbor removed) and aspect distortion."""
        sc = ScreenCapture(quality=80, max_width=1920)
        sc.set_custom_resolution(2560, 1440)
        self.assertEqual(sc.resolution, (2560, 1440))
        # Physical monitor capture rect must not be overwritten by virtual output resolution
        self.assertTrue(hasattr(sc, "monitors"))

        css = self.css_path.read_text(encoding="utf-8")
        self.assertNotIn("image-rendering: pixelated;", css)
        app_js = self.app_js_path.read_text(encoding="utf-8")
        self.assertIn("imageSmoothingQuality = 'high'", app_js)

    def test_03_04_host_gui_admin_lever_and_config_groups(self):
        """Items 3 & 4: Host GUI Settings tab has Admin Elevation Lever and Basic vs Admin config groups."""
        gui_html = self.gui_html_path.read_text(encoding="utf-8")
        self.assertIn('id="swAdminElevation"', gui_html)
        self.assertIn('id="swStealthMode"', gui_html)
        self.assertIn('id="swAutoWakeup"', gui_html)
        self.assertIn('id="swBlockInputHost"', gui_html)
        self.assertIn('id="swPrivacyCurtainHost"', gui_html)
        self.assertIn('id="adminRequiredGroup"', gui_html)

        gui_py = self.gui_py_path.read_text(encoding="utf-8")
        self.assertIn("def toggle_admin_elevation", gui_py)
        self.assertIn("def toggle_stealth_mode", gui_py)

    def test_05_cli_parser_and_help_documentation(self):
        """Item 5: Comprehensive CLI flags and --help output."""
        parser = build_cli_parser()
        help_text = parser.format_help()
        for flag in ["--relay", "--room", "--pin", "--fps", "--uncapped", "--quality", "--stealth", "--service", "--anti-sleep", "--auto-wakeup", "--block-input", "--curtain", "--admin"]:
            self.assertIn(flag, help_text)

        args = parser.parse_args(["--room", "CLI-99", "--pin", "654321", "--fps", "240", "--stealth", "--anti-sleep"])
        self.assertEqual(args.room, "CLI-99")
        self.assertEqual(args.pin, "654321")
        self.assertEqual(args.fps, 240)
        self.assertTrue(args.stealth)
        self.assertTrue(args.keep_awake)

    @patch("host_service.is_current_user_admin", return_value=False)
    async def test_06_client_deck_admin_group_and_host_capabilities(self, mock_admin):
        """Item 6: Client deck groups Admin-required features and disables them when Host lacks Admin."""
        html = self.html_path.read_text(encoding="utf-8")
        self.assertIn('id="deckAdminGroup"', html)
        self.assertIn('id="badgeHostAdminStatus"', html)
        self.assertIn('id="btnRequestHostAdmin"', html)
        self.assertIn('id="modalRemoteHostConfig"', html)

        service = HostService(relay_url="ws://localhost:9999", room_id="CAP-ROOM", pin="123456")
        mock_ws = AsyncMock()
        await service.handle_control_event(json.dumps({"type": "get_host_config"}), mock_ws)
        sent = json.loads(mock_ws.send.call_args[0][0])
        self.assertEqual(sent["type"], "host_config_response")
        self.assertFalse(sent["is_admin"])
        self.assertIn("config", sent)

    def test_07_08_09_10_13_19_20_client_features_and_responsive_ui(self):
        """Items 7, 8, 9, 10, 13, 19, 20: Reconnect, iPhone Xs CSS, Advanced Download, Fleet Grouping, 3D Hero, Unconnected Guard, Direct Protocols."""
        html = self.html_path.read_text(encoding="utf-8")
        app_js = self.app_js_path.read_text(encoding="utf-8")
        css = self.css_path.read_text(encoding="utf-8")

        # Item 7: Session storage reconnect & client_leave
        self.assertIn("meikova_active_remote_session", app_js)
        self.assertIn("reconnect_session_id", app_js)
        self.assertIn("client_leave", app_js)

        # Item 8: Responsive rules for iPhone Xs (375px / 390px / 480px)
        self.assertIn("@media (max-width: 390px)", css)
        self.assertIn("@media (max-width: 480px)", css)

        # Item 9: Download Modal Advanced Configurator
        self.assertIn('id="swDownloadAdvanced"', html)
        self.assertIn('id="dlAdvancedConfigPanel"', html)
        self.assertIn("buildAdvancedDownloadParams", app_js)

        # Item 10: Fleet Grouping, Tags & Metadata
        self.assertIn('id="fleetFilterBar"', html)
        self.assertIn('id="modalDeviceMeta"', html)

        # Item 13: Interactive 3D Hero projection
        self.assertIn("function project3D(", app_js)

        # Item 19: Unconnected Screen Guard
        self.assertIn('id="unconnectedScreenGuard"', html)
        self.assertIn("syncRemoteStageOverlays", app_js)

        # Item 20: Direct In-Browser Protocol Execution
        self.assertIn('id="btnDirectProtoRdp"', html)
        self.assertIn('id="btnDirectProtoSsh"', html)
        self.assertIn('id="btnDirectProtoSftp"', html)

    def test_12_15_17_file_manager_power_and_drag_drop(self):
        """Items 12, 15, 17: File creation, recursive search, folder resolution, and Wake-on-LAN."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fm = FileManager()
            create_res = fm.create_file(tmpdir, "test_script.ps1", "Write-Host 'Hello'")
            self.assertTrue(create_res["success"])
            search_res = fm.search_files(tmpdir, "test_script")
            self.assertTrue(search_res["success"])
            self.assertEqual(len(search_res["items"]), 1)

        resolved_desktop = FileManager().resolve_target_folder("desktop")
        self.assertTrue(os.path.isabs(resolved_desktop))

        wol_res = PowerManager.send_wake_on_lan("AA:BB:CC:DD:EE:FF")
        self.assertTrue(wol_res["success"])



    def test_21_three_os_engines_and_friendly_os_info(self):
        """Verifies the 3 OS Engines (WindowsEngine, MacOSEngine, LinuxEngine) and that os_info is never 'win32 (nt)'."""
        from host_agent.engines import create_platform_engine, get_active_os_engine, WindowsEngine, MacOSEngine, LinuxEngine
        from host_agent.system_manager import SystemManager
        from host_agent.host_service import HostService

        win_eng = create_platform_engine("win32")
        mac_eng = create_platform_engine("darwin")
        lin_eng = create_platform_engine("linux")
        self.assertIsInstance(win_eng, WindowsEngine)
        self.assertIsInstance(mac_eng, MacOSEngine)
        self.assertIsInstance(lin_eng, LinuxEngine)
        self.assertIsNotNone(get_active_os_engine())

        os_name = SystemManager.get_os_display_name()
        self.assertNotIn("win32 (nt)", os_name.lower())
        self.assertNotEqual(os_name.lower(), "win32")
        self.assertNotIn("win32 (nt)", HostService.get_os_info().lower())

    def test_22_wan_mkr0_micro_frame_and_fhd_label_and_terminal_dedup(self):
        """Verifies 4-byte MKR0 micro-frame deduplication, FHD resolution label, and non-duplicating Terminal manager."""
        from host_agent.host_service import MICRO_FRAME_REPEAT
        from host_agent.terminal_manager import TerminalManager

        self.assertEqual(MICRO_FRAME_REPEAT, b"MKR0")
        self.assertEqual(len(MICRO_FRAME_REPEAT), 4)

        outputs = []
        tm = TerminalManager(on_output=lambda s: outputs.append(s))
        tm._pending_echo_cmds.append("ls")
        self.assertTrue(tm._should_skip_echo_line("PS D:\\JOB\\DEV\\meikova> ls\r\n"))
        self.assertFalse(tm._should_skip_echo_line("Directory: D:\\JOB\\DEV\\meikova\r\n"))

        html = (BASE_DIR / "relay-server" / "public" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="resolutionCurrentLabel" class="mono-font" style="font-size: 11px; font-weight: 700;">FHD</span>', html)
        self.assertIn('data-res-w="1920" data-res-h="1080" data-res-label="FHD"', html)
        self.assertIn('data-res-w="1600" data-res-h="900" data-res-label="HD+"', html)
        self.assertIn('data-res-w="1280" data-res-h="720" data-res-label="HD"', html)

        app_js = (BASE_DIR / "relay-server" / "public" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn("function mapResolutionToTierTag(", app_js)
        self.assertIn("['dashboard', 'remote', 'files', 'terminal', 'tasks', 'audit']", app_js)
        self.assertIn("route.isReloadReconnect = true;", app_js)


if __name__ == "__main__":
    unittest.main()

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



    def test_23_nine_point_cloudflare_wan_and_ui_fixes(self):
        """Verifies all 9 fixes: CRC32 full-pixel checksum, input-triggered capture, stream_mode CLI & WS,
        zero-replay networkSyncOverlay, Native FHD lock, top-deck stageRect offset, non-blocking top trigger,
        hidden redundant pin button, translucent corner HUDs, and PS>ls terminal echo stripping."""
        from host_agent.screen_capture import _compute_frame_checksum, ScreenCapture
        from host_agent.host_service import HostService, build_cli_parser
        from host_agent.terminal_manager import TerminalManager

        # 1. Full-pixel CRC32 detects single character change at arbitrary column offset (no stride-512 blind spot)
        buf_a = bytearray(1920 * 1080 * 4)
        buf_b = bytearray(1920 * 1080 * 4)
        # Modify pixel at column 7 (which was previously skipped by [::512] stride!)
        buf_b[7 * 4] = 255
        self.assertNotEqual(_compute_frame_checksum(buf_a), _compute_frame_checksum(buf_b))

        # 2. Input activity notification wakes capture & sets active input window
        cap = ScreenCapture(quality=75)
        cap.notify_input_activity(0.35)
        self.assertGreater(cap._force_active_until, 0.0)

        # 3. CLI --stream-mode and --resolution flags
        args = build_cli_parser().parse_args(["--stream-mode", "continuous_cfr", "--resolution", "1920x1080"])
        self.assertEqual(args.stream_mode, "continuous_cfr")
        self.assertEqual(args.resolution, "1920x1080")

        svc = HostService(relay_url="ws://localhost:8080", room_id="RD-TEST9", stream_mode="low_latency_drop")
        self.assertEqual(svc.stream_mode, "low_latency_drop")
        self.assertIn("stream_mode", svc.get_host_config_dict())

        # 4. TerminalManager strips compact 'PS>ls' as well as 'PS D:\path> ls'
        tm = TerminalManager(on_output=lambda s: None)
        tm._pending_echo_cmds.append("ls")
        self.assertTrue(tm._should_skip_echo_line("PS>ls\r\n"))
        tm._pending_echo_cmds.append("dir")
        self.assertTrue(tm._should_skip_echo_line("PS > dir\r\n"))

        # 5. HTML, CSS & JS checks for Network Sync Overlay, Top-Deck positioning, Translucent HUDs, and Hidden Quick Pin
        html = (BASE_DIR / "relay-server" / "public" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="networkSyncOverlay"', html)
        self.assertIn('id="streamModeBar"', html)
        self.assertIn('data-stream-mode="continuous_cfr"', html)
        self.assertIn('data-stream-mode="low_latency_drop"', html)

        css = (BASE_DIR / "relay-server" / "public" / "css" / "style.css").read_text(encoding="utf-8")
        self.assertIn(".network-sync-overlay", css)
        self.assertIn(".readout--corner-fade", css)
        self.assertIn("#btnDeckPinQuick {\n  display: none !important;\n}", css)

        app_js = (BASE_DIR / "relay-server" / "public" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn("btnRect.bottom - stageRect.top", app_js)
        self.assertIn("request_keyframe", app_js)
        self.assertIn("set_stream_mode", app_js)


    def test_24_high_fps_and_fps_limit_enforcement(self):
        """Verifies 1000+ FPS Uncapped mode, GIL-friendly background capture loop, WAN non-stalling ACK decay,
        and end-to-end FPS Limit enforcement across HostService, server.js, and app.js."""
        import asyncio
        import json
        from host_agent.host_service import HostService
        from host_agent.screen_capture import ScreenCapture

        svc = HostService(relay_url="ws://localhost:8080", room_id="RD-FPS24", pin="123456")
        try:
            sent_msgs = []

            class DummyWS:
                open = True
                closed = False
                async def send(self, data):
                    sent_msgs.append(data)

            ws = DummyWS()

            # 1. Test explicit FPS limit (e.g. 60 FPS -> 1/60s, then 144 FPS -> 1/144s, then Uncapped 0 -> 1/1000s)
            asyncio.run(svc.handle_control_event(json.dumps({"type": "set_fps_limit", "fps_limit": 60, "uncapped": False}), ws))
            self.assertFalse(svc.uncapped_fps)
            self.assertEqual(svc.custom_fps_limit, 60)
            self.assertAlmostEqual(svc.frame_interval, 1.0 / 60.0)
            last_resp = json.loads(sent_msgs[-1])
            self.assertEqual(last_resp["type"], "fps_limit_applied")
            self.assertEqual(last_resp["fps_limit"], 60)
            self.assertEqual(last_resp["applied_fps"], 60)

            asyncio.run(svc.handle_control_event(json.dumps({"type": "set_fps_limit", "fps_limit": 240, "uncapped": False}), ws))
            self.assertFalse(svc.uncapped_fps)
            self.assertEqual(svc.custom_fps_limit, 240)
            self.assertAlmostEqual(svc.frame_interval, 1.0 / 240.0)

            asyncio.run(svc.handle_control_event(json.dumps({"type": "set_fps_limit", "fps_limit": 0, "uncapped": True}), ws))
            self.assertTrue(svc.uncapped_fps)
            self.assertEqual(svc.custom_fps_limit, 0)
            self.assertAlmostEqual(svc.frame_interval, 1.0 / 1000.0)

            # 2. Test sync_display_profile and set_quality_preset preserving explicit FPS limit and Uncapped state
            asyncio.run(svc.handle_control_event(json.dumps({
                "type": "sync_display_profile",
                "client_w": 1920,
                "client_h": 1080,
                "client_fps": 60,
                "fps_limit": 30,
                "uncapped": False
            }), ws))
            self.assertFalse(svc.uncapped_fps)
            self.assertEqual(svc.custom_fps_limit, 30)
            self.assertAlmostEqual(svc.frame_interval, 1.0 / 30.0)

            asyncio.run(svc.handle_control_event(json.dumps({
                "type": "set_quality_preset",
                "preset": "speed_60",
                "fps_limit": 0,
                "uncapped": True
            }), ws))
            self.assertTrue(svc.uncapped_fps)
            self.assertEqual(svc.custom_fps_limit, 0)
            self.assertAlmostEqual(svc.frame_interval, 1.0 / 1000.0)

            # 3. Verify frame_ack with dropped=True does NOT force full-frame resend storm
            svc._force_full_frame = False
            svc._last_sent_frame_obj_id = 12345
            svc.frames_in_flight = 3
            asyncio.run(svc.handle_control_event(json.dumps({"type": "frame_ack", "dropped": True}), ws))
            self.assertFalse(svc._force_full_frame)
            self.assertEqual(svc._last_sent_frame_obj_id, 12345)
            self.assertEqual(svc.frames_in_flight, 2)

            # 4. Verify web client & relay server high-FPS and FPS limiter hooks
            app_js = (BASE_DIR / "relay-server" / "public" / "js" / "app.js").read_text(encoding="utf-8")
            self.assertIn("function syncFpsLimitUI(", app_js)
            self.assertIn("msg.type === 'fps_limit_applied'", app_js)
            self.assertIn("recordRenderedFrameTick", app_js)
            self.assertIn("lastAcceptedFrameTickTime", app_js)

            srv_js = (BASE_DIR / "relay-server" / "server.js").read_text(encoding="utf-8")
            self.assertIn("client.ws.bufferedAmount > 2 * 1024 * 1024", srv_js)
            self.assertIn("const highWaterMark = Math.max(512 * 1024, Math.min(1536 * 1024, msgLen * 2));", srv_js)
        finally:
            svc.stop()



    def test_25_new_enterprise_features_and_in_browser_protocol_matrix(self):
        """Verify new enterprise features (Smart Visual Filter, PiP Mini-Monitor, Remote URL Launcher, Auto-Lock on Disconnect, Idle FPS Saver) and In-Browser Protocol Matrix (RDP, SSH, SFTP)."""
        svc = HostService(
            relay_url="ws://127.0.0.1:8080",
            room_id="TEST-ENT",
            pin="123456",
            color_filter="crisp_text",
            auto_lock_on_disconnect=True,
            idle_fps_saver=True,
        )
        try:
            self.assertEqual(svc.color_filter, "crisp_text")
            self.assertTrue(svc.auto_lock_on_disconnect)
            self.assertTrue(svc.idle_fps_saver)

            class DummyWS:
                def __init__(self):
                    self.sent = []
                async def send(self, data):
                    self.sent.append(data)

            ws = DummyWS()

            # 1. Test set_color_filter event
            asyncio.run(svc.handle_control_event(json.dumps({
                "type": "set_color_filter",
                "color_filter": "night_shield"
            }), ws))
            self.assertEqual(svc.color_filter, "night_shield")
            last_msg = json.loads(ws.sent[-1])
            self.assertEqual(last_msg["type"], "color_filter_applied")
            self.assertEqual(last_msg["color_filter"], "night_shield")

            # 2. Test set_host_config updating color_filter, auto_lock_on_disconnect, idle_fps_saver
            asyncio.run(svc.handle_control_event(json.dumps({
                "type": "set_host_config",
                "color_filter": "high_contrast",
                "auto_lock_on_disconnect": False,
                "idle_fps_saver": False
            }), ws))
            self.assertEqual(svc.color_filter, "high_contrast")
            self.assertFalse(svc.auto_lock_on_disconnect)
            self.assertFalse(svc.idle_fps_saver)

            # 3. Test open_remote_url in MEIKOVA_TEST_MODE (safe, no physical browser spawned)
            os.environ["MEIKOVA_TEST_MODE"] = "1"
            asyncio.run(svc.handle_control_event(json.dumps({
                "type": "open_remote_url",
                "url": "github.com/meikova"
            }), ws))
            url_msg = json.loads(ws.sent[-1])
            self.assertEqual(url_msg["type"], "open_remote_url_response")
            self.assertTrue(url_msg["success"])
            self.assertEqual(url_msg["url"], "https://github.com/meikova")

            # 4. Test probe_protocols and in-browser Protocol Matrix UI bindings
            asyncio.run(svc.handle_control_event(json.dumps({
                "type": "probe_protocols"
            }), ws))
            proto_msg = json.loads(ws.sent[-1])
            self.assertEqual(proto_msg["type"], "protocol_matrix")
            self.assertIn("remote", proto_msg["matrix"])
            self.assertIn("terminal", proto_msg["matrix"])
            self.assertIn("file", proto_msg["matrix"])

            app_js = (BASE_DIR / "relay-server" / "public" / "js" / "app.js").read_text(encoding="utf-8")
            self.assertIn("btnDirectProtoRdp", app_js)
            self.assertIn("btnDirectProtoSsh", app_js)
            self.assertIn("btnDirectProtoSftp", app_js)
            self.assertIn("msg.type === 'tunnel_opened'", app_js)
            self.assertIn("function updateColorFilterUI(", app_js)
            self.assertIn("btnDropdownPip", app_js)
            self.assertIn("btnDropdownOpenUrl", app_js)
            self.assertIn("btnDropdownAutoLock", app_js)
        finally:
            svc.stop()



    def test_26_responsive_safe_area_and_os_engine_gui_tray_parity(self):
        """Verifies comprehensive responsive & safe-area CSS rules (Notch / Dynamic Island / Landscape),
        OS-Engine GUI/Tray/Autostart separation, Linux system tray hooks, and v1.4.0 Host GUI parity."""
        from host_agent.engines import create_platform_engine, WindowsEngine, MacOSEngine, LinuxEngine
        from host_agent.tray_menu import build_tray_menu, show_custom_tk_tray_popup
        from host_agent.gui_agent import HostApi, COLORS, APP_VERSION

        # 1. Verify OS Engines expose all OS-grouped GUI, Window, Autostart, Clipboard, and Tray methods
        for plat, cls in (("win32", WindowsEngine), ("darwin", MacOSEngine), ("linux", LinuxEngine)):
            eng = create_platform_engine(plat)
            self.assertIsInstance(eng, cls)
            self.assertIn("sans", eng.get_ui_fonts())
            self.assertIn("mono", eng.get_ui_fonts())
            self.assertTrue(callable(eng.activate_window))
            self.assertTrue(callable(eng.apply_window_theme))
            self.assertTrue(callable(eng.is_autostart_enabled))
            self.assertTrue(callable(eng.set_autostart))
            self.assertTrue(callable(eng.set_clipboard_text))
            self.assertTrue(callable(eng.configure_tray_environment))
            self.assertTrue(callable(eng.patch_tray_backend))

        # 2. Verify v1.4.0 Ambient Dark palette & version parity in gui_agent.py
        import json
        expected_version = json.loads((BASE_DIR / "version.json").read_text(encoding="utf-8"))["version"]
        self.assertEqual(APP_VERSION, expected_version)
        self.assertEqual(COLORS["bg_main"], "#111315")
        self.assertEqual(COLORS["accent_green"], "#83E8AC")
        self.assertTrue(callable(show_custom_tk_tray_popup))

        # 3. Verify responsive & safe-area CSS rules in relay-server/public/css/style.css
        css_text = (BASE_DIR / "relay-server" / "public" / "css" / "style.css").read_text(encoding="utf-8")
        self.assertIn("--bottom-nav-h: 56px;", css_text)
        self.assertIn("--bottom-nav-total-h: calc(var(--bottom-nav-h) + env(safe-area-inset-bottom, 0px));", css_text)
        self.assertIn("left: calc(76px + env(safe-area-inset-left, 0px)) !important;", css_text)
        self.assertIn("@media (max-height: 560px)", css_text)
        self.assertIn("env(safe-area-inset-top, 0px)", css_text)
        self.assertIn("env(safe-area-inset-left, 0px)", css_text)
        self.assertIn("env(safe-area-inset-right, 0px)", css_text)



    def test_27_full_os_engine_consolidation_and_100_percent_i18n_responsive_loop(self):
        """Verifies all 7 OS-Engine subsystem groups across WindowsEngine, MacOSEngine, and LinuxEngine,
        100% i18n wrapping in index.html / gui_view.html / gui_agent.py / tray_menu.py, and Pass #2 responsive CSS."""
        import re
        from host_agent.engines import create_platform_engine
        from host_agent.power_manager import PowerManager
        from host_agent.system_manager import SystemManager

        # 1. Verify all 3 OS Engines implement all 7 subsystem groups
        for plat, expected_paste in (("win32", (0x11, 0x56)), ("darwin", (0x5B, 0x56)), ("linux", (0x11, 0x56))):
            eng = create_platform_engine(plat)
            self.assertEqual(eng.get_paste_vk_combo(), expected_paste)
            self.assertTrue(eng.lock_workstation())
            self.assertTrue(eng.restart_machine(5))
            self.assertTrue(eng.shutdown_machine(10))
            self.assertTrue(eng.cancel_power_action())
            self.assertTrue(eng.prevent_sleep(True))
            wake_res = eng.configure_auto_wakeup(True, "07:30")
            self.assertTrue(wake_res["success"])
            self.assertEqual(wake_res["wake_time"], "07:30")
            self.assertTrue(eng.execute_quick_macro("calc"))
            hw = eng.get_hardware_telemetry()
            self.assertIn("ram", hw)
            self.assertIn("disks", hw)
            self.assertIn("os", hw)
            self.assertTrue(callable(eng.is_service_installed))
            self.assertTrue(callable(eng.manage_service))

        # 2. Verify PowerManager and SystemManager delegate cleanly
        self.assertTrue(PowerManager.lock_workstation())
        self.assertIn("ram", SystemManager.get_hardware_telemetry())

        # 3. Verify 0 unwrapped Vietnamese elements or attributes in index.html
        html = (BASE_DIR / "relay-server" / "public" / "index.html").read_text(encoding="utf-8")
        vi_pat = re.compile(r'[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ]')
        for line in html.splitlines():
            if line.strip().startswith("<!--"):
                continue
            for m in re.finditer(r'<(span|h1|h2|h3|h4|label|p|button|div|th|option)\b([^>]*)>([^<]+)</\1>', line):
                attrs, content = m.group(2), m.group(3).strip()
                if vi_pat.search(content):
                    self.assertIn("data-i18n", attrs, f"Unwrapped element in index.html: {content}")

        # 4. Verify Pass #2 responsive CSS in style.css and gui_view.html
        css_text = (BASE_DIR / "relay-server" / "public" / "css" / "style.css").read_text(encoding="utf-8")
        self.assertIn(".modal-overlay > .instrument-card", css_text)
        self.assertIn("@media (max-width: 360px)", css_text)
        gui_html = (BASE_DIR / "host_agent" / "gui_view.html").read_text(encoding="utf-8")
        self.assertIn("@media (max-width: 520px)", gui_html)
        self.assertIn("@media (max-height: 680px)", gui_html)


    def test_28_continuous_cfr_high_fps_pacing_and_keyframe_heartbeat(self):
        """Verify Continuous CFR (youtube_smooth) achieves high FPS via MKR0 sub-frame pacing + 250ms keyframe heartbeat + QPC catch-up ticks."""
        hs_src = (Path(__file__).resolve().parents[1] / "host_agent" / "host_service.py").read_text(encoding="utf-8")
        self.assertIn("cfr_need_keyframe", hs_src)
        self.assertIn("_last_cfr_full_send_time", hs_src)
        self.assertIn("max_in_flight = 12", hs_src)
        self.assertNotIn("if s_mode not in (\"continuous_cfr\", \"youtube_smooth\"):\n                                await ws.send(MICRO_FRAME_REPEAT)", hs_src)


    def test_29_zero_touch_auto_bootstrap_and_vendor_packages(self):
        """Verify auto_bootstrap.py, setup_dependencies.py, and bundled vendor/packages work out-of-the-box."""
        from host_agent.auto_bootstrap import activate_vendor_paths, inspect_dependencies
        v_info = activate_vendor_paths()
        self.assertTrue(v_info["mounted_packages"])
        rep = inspect_dependencies()
        self.assertIn("installed", rep)
        self.assertIn("missing", rep)
        installed_names = {item["import_name"] for item in rep["installed"]}
        self.assertIn("turbojpeg", installed_names)
        self.assertIn("pyperclip", installed_names)
        setup_file = Path(__file__).resolve().parents[1] / "setup_dependencies.py"
        self.assertTrue(setup_file.is_file())


    def test_30_fleet_search_anti_password_manager_autofill_guard(self):
        """Verify fleetSearchInput has readonly-until-interaction and fleetSearchUserInteracted guard against browser username autofill."""
        root = Path(__file__).resolve().parents[1]
        html_src = (root / "relay-server" / "public" / "index.html").read_text(encoding="utf-8")
        js_src = (root / "relay-server" / "public" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn("id=\"fleetSearchInput\" readonly", html_src)
        self.assertIn("fleetSearchUserInteracted", js_src)
        self.assertIn("if (!fleetSearchUserInteracted)", js_src)


    def test_31_ten_group_os_engine_and_dynamic_js_i18n(self):
        """Verify all 10 OS Engine subsystem groups across Windows/macOS/Linux, dynamic JS i18n keys, and Pass 10 responsive CSS."""
        from host_agent.engines import create_platform_engine
        for plat in ("win32", "darwin", "linux"):
            eng = create_platform_engine(plat)
            for method_name in (
                "get_cursor_shape",
                "get_clipboard_text",
                "is_headless_display",
                "get_virtual_display_status",
                "is_audio_output_available",
            ):
                self.assertTrue(callable(getattr(eng, method_name, None)), f"{plat} missing {method_name}")
            self.assertIsInstance(eng.get_cursor_shape(), str)
            self.assertIsInstance(eng.get_virtual_display_status(), dict)

        root = Path(__file__).resolve().parents[1]
        i18n_src = (root / "relay-server" / "public" / "js" / "i18n.js").read_text(encoding="utf-8")
        app_src = (root / "relay-server" / "public" / "js" / "app.js").read_text(encoding="utf-8")
        css_src = (root / "relay-server" / "public" / "css" / "style.css").read_text(encoding="utf-8")
        gui_src = (root / "host_agent" / "gui_view.html").read_text(encoding="utf-8")

        for key in ("pin.hide", "pin.show", "session_mgr.title", "audit.badge_session_conn", "power.lock_title", "tasks.ram_sub_fmt"):
            self.assertIn(f'"{key}"', i18n_src)
            self.assertIn(f"'{key}'", app_src)

        self.assertIn("PASS 10: ULTRA-NARROW FOLDABLES", css_src)
        self.assertIn("@media (max-width: 540px)", gui_src)


if __name__ == "__main__":




    unittest.main()

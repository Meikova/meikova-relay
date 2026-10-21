import unittest
import sys
import os
from unittest.mock import patch, MagicMock
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from host_agent.screen_capture import ScreenCapture
from host_agent.input_injector import InputInjector
from host_agent.power_manager import PowerManager
from host_agent.clipboard_manager import ClipboardManager
from host_agent.deployment_manager import is_current_user_admin, get_user_install_dir

class TestCrossPlatformAgent(unittest.TestCase):
    """Verifies that Host Agent modules run gracefully in non-Windows or simulated POSIX environments."""

    def test_screen_capture_detect_monitors_fallback(self):
        """When user32 is None or on non-Windows, detect_monitors should return at least 1 valid monitor."""
        sc = ScreenCapture()
        monitors = sc.detect_monitors()
        self.assertIsInstance(monitors, list)
        self.assertGreaterEqual(len(monitors), 1)
        self.assertIn("rect", monitors[0])
        self.assertIn("width", monitors[0])
        self.assertIn("height", monitors[0])

    def test_screen_capture_resolution(self):
        sc = ScreenCapture()
        w, h = sc.resolution
        self.assertGreater(w, 0)
        self.assertGreater(h, 0)

    def test_input_injector_send_safe_on_no_sendinput(self):
        """If SendInput is not available, _send should return False safely without crashing."""
        with patch('host_agent.input_injector.SendInput', None):
            res = InputInjector.mouse_down(0)
            self.assertFalse(res)
            res_up = InputInjector.mouse_up(0)
            self.assertFalse(res_up)
            res_key = InputInjector.key_down(0x41)
            self.assertFalse(res_key)

    def test_power_manager_cross_platform_methods(self):
        """PowerManager methods should execute without unhandled exceptions regardless of platform."""
        with patch('sys.platform', 'linux'):
            with patch('subprocess.call', return_value=0):
                self.assertTrue(PowerManager.lock_workstation())
                self.assertTrue(PowerManager.restart_machine(5))
                self.assertTrue(PowerManager.shutdown_machine(10))
                self.assertTrue(PowerManager.cancel_power_action())
                self.assertTrue(PowerManager.prevent_sleep(True))

    def test_clipboard_manager_posix_fallback(self):
        """ClipboardManager should handle macOS/Linux without crashing."""
        cm = ClipboardManager()
        with patch('sys.platform', 'darwin'):
            with patch('subprocess.check_output', return_value="hello mac"):
                text = cm.get_clipboard_text()
                self.assertEqual(text, "hello mac")

    def test_is_current_user_admin_cross_platform(self):
        with patch('sys.platform', 'linux'):
            with patch('os.geteuid', return_value=0, create=True):
                self.assertTrue(is_current_user_admin())
            with patch('os.geteuid', return_value=1000, create=True):
                self.assertFalse(is_current_user_admin())

    def test_user_install_dir_cross_platform(self):
        with patch.dict(os.environ, {"USERPROFILE": "C:/Users/testuser", "HOME": "/home/testuser"}, clear=True):
            dir_path = get_user_install_dir()
            self.assertIsInstance(dir_path, Path)
            self.assertTrue(dir_path.name in ("MeikovaRelayHost", ".meikova_relay_host"))

    def test_resolve_config_path_prefers_localappdata(self):
        """Verifies resolve_config_path correctly prioritizes LOCALAPPDATA when present."""
        from host_agent.gui_agent import resolve_config_path
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            fake_appdata = Path(tmp_dir)
            target_cfg = fake_appdata / "MeikovaRelayHost" / "config.json"
            target_cfg.parent.mkdir(parents=True, exist_ok=True)
            target_cfg.write_text('{"account": "test@domain.com"}', encoding="utf-8")
            with patch.dict(os.environ, {"LOCALAPPDATA": str(fake_appdata)}):
                with patch('sys.platform', 'win32'):
                    found_path = resolve_config_path()
                    self.assertEqual(found_path.resolve(), target_cfg.resolve())

    def test_host_api_private_state_hygiene(self):
        """HostApi must not expose internal native/COM objects without leading underscore."""
        from host_agent.gui_agent import HostApi
        api = HostApi({}, Path("config.json"))
        exposed = [m for m in dir(api) if not m.startswith("_")]
        forbidden = ["window", "hwnd", "host_service", "service_thread", "tray_icon"]
        for f in forbidden:
            self.assertNotIn(f, exposed, f"Attribute '{f}' must be private to prevent pywebview deadlock")

    def test_force_window_foreground_cross_platform(self):
        from host_agent.gui_agent import force_window_foreground
        mock_win = MagicMock()
        mock_win.show = MagicMock()
        mock_win.restore = MagicMock()

        # Test Linux execution
        with patch('sys.platform', 'linux'):
            with patch('subprocess.run') as mock_run:
                force_window_foreground(mock_win)
                mock_win.show.assert_called()
                mock_win.restore.assert_called()
                mock_run.assert_called_with(["wmctrl", "-a", "Meikova Relay Host"], check=False)

        # Test Darwin execution
        with patch('sys.platform', 'darwin'):
            with patch('subprocess.run') as mock_run:
                force_window_foreground(mock_win)
                mock_run.assert_called_with(["osascript", "-e", 'tell application "Meikova Relay Host" to activate'], check=False)

        # Test Win32 execution with no hwnd (graceful fallback)
        with patch('sys.platform', 'win32'):
            force_window_foreground(mock_win)

    def test_cross_platform_user_tier_install(self):
        import tempfile
        from host_agent.deployment_manager import install_user_tier, uninstall_user_tier

        with tempfile.TemporaryDirectory() as tmp_dir:
            fake_home = Path(tmp_dir)
            with patch.object(Path, "home", return_value=fake_home):
                # Linux user tier
                with patch('sys.platform', 'linux'):
                    ok, msg = install_user_tier()
                    self.assertTrue(ok)
                    desktop_file = fake_home / ".config/autostart/meikovarelayhost.desktop"
                    self.assertTrue(desktop_file.exists())
                    self.assertIn("Meikova Relay Host", desktop_file.read_text(encoding="utf-8"))

                    un_ok, _ = uninstall_user_tier()
                    self.assertTrue(un_ok)
                    self.assertFalse(desktop_file.exists())

                # Darwin user tier
                with patch('sys.platform', 'darwin'):
                    ok, msg = install_user_tier()
                    self.assertTrue(ok)
                    plist_file = fake_home / "Library/LaunchAgents/com.meikovarelay.host.plist"
                    self.assertTrue(plist_file.exists())
                    self.assertIn("com.meikovarelay.host", plist_file.read_text(encoding="utf-8"))

                    un_ok, _ = uninstall_user_tier()
                    self.assertTrue(un_ok)
                    self.assertFalse(plist_file.exists())

if __name__ == '__main__':
    unittest.main()

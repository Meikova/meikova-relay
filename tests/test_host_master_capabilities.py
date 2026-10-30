"""
Unit & Integration Test Suite for Host Master Capabilities
Validates:
1. Dynamic legacy file cleanup (zero-leftover in %LOCALAPPDATA%)
2. Atomic swap auto-update logic & semver parsing
3. Hardware telemetry collector (CPU/RAM Win32)
4. Screen capture Winlogon/UAC desktop attach
5. Input injector unstick & remote unlock
6. Server scripts (setup.bat, setup-linux.sh, setup-macos.sh, config.json)
7. Exact Web Client SHA256 Parity & i18n completeness
"""

import hashlib
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Paths
REPO_ROOT = Path(__file__).resolve().parent.parent
HOST_AGENT_DIR = REPO_ROOT / "host_agent"


class TestHostMasterCapabilities(unittest.TestCase):

    def test_deployment_manager_cleanup(self):
        """Verify dynamic cleanup purges .py and __pycache__ while preserving exe, config, icons."""
        from host_agent.deployment_manager import cleanup_legacy_source_files

        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_path = Path(tmp_dir) / "TestHostDir"
            temp_path.mkdir()

            # Create dummy preserved files
            (temp_path / "MeikovaRelayHost.exe").write_bytes(b"MZ" + b"\x00" * 100)
            (temp_path / "config.json").write_text('{"account": "test"}', encoding="utf-8")
            (temp_path / "icon.ico").write_bytes(b"\x00" * 20)
            (temp_path / "tray.log").write_text("running", encoding="utf-8")

            # Create dummy junk files from legacy zip
            (temp_path / "gui_agent.py").write_text("# old source", encoding="utf-8")
            (temp_path / "host_service.py").write_text("# old source", encoding="utf-8")
            (temp_path / "screen_capture.py").write_text("# old source", encoding="utf-8")
            (temp_path / "run_agent.bat").write_text("@echo off", encoding="utf-8")
            (temp_path / "requirements.txt").write_text("pillow", encoding="utf-8")
            pycache = temp_path / "__pycache__"
            pycache.mkdir()
            (pycache / "gui_agent.cpython-313.pyc").write_bytes(b"\x00" * 50)

            # Run cleanup
            cleaned = cleanup_legacy_source_files(temp_path)
            self.assertGreaterEqual(cleaned, 5)

            # Verify preserved files intact
            self.assertTrue((temp_path / "MeikovaRelayHost.exe").exists())
            self.assertTrue((temp_path / "config.json").exists())
            self.assertTrue((temp_path / "icon.ico").exists())
            self.assertTrue((temp_path / "tray.log").exists())

            # Verify junk files deleted
            self.assertFalse((temp_path / "gui_agent.py").exists())
            self.assertFalse((temp_path / "host_service.py").exists())
            self.assertFalse((temp_path / "screen_capture.py").exists())
            self.assertFalse((temp_path / "run_agent.bat").exists())
            self.assertFalse((temp_path / "__pycache__").exists())

    def test_auto_updater_semver(self):
        """Verify semver parsing and comparison."""
        from host_agent.auto_updater import parse_semver

        self.assertEqual(parse_semver("1.4.2"), (1, 4, 2))
        self.assertEqual(parse_semver("v1.4.3"), (1, 4, 3))
        self.assertEqual(parse_semver("2.0.0-beta"), (2, 0, 0))
        self.assertEqual(parse_semver("invalid"), (0, 0, 0))

        # Comparison
        self.assertGreater(parse_semver("v1.4.3"), parse_semver("1.4.2"))
        self.assertGreater(parse_semver("2.0.0"), parse_semver("1.9.9"))
        self.assertEqual(parse_semver("1.4.2"), parse_semver("v1.4.2"))

    def test_hardware_telemetry_metrics(self):
        """Verify hardware telemetry collector returns valid numeric metrics."""
        from host_agent.telemetry import get_system_telemetry

        metrics = get_system_telemetry()
        self.assertIsInstance(metrics, dict)
        self.assertIn("cpu_percent", metrics)
        self.assertIn("ram_percent", metrics)
        self.assertIn("ram_used_mb", metrics)
        self.assertIn("ram_total_mb", metrics)
        self.assertIn("power", metrics)
        self.assertIn("battery_percent", metrics["power"])

        # Values in logical ranges
        self.assertGreaterEqual(metrics["ram_percent"], 0)
        self.assertLessEqual(metrics["ram_percent"], 100)
        self.assertGreaterEqual(metrics["cpu_percent"], 0)
        self.assertLessEqual(metrics["cpu_percent"], 100)

    def test_input_injector_unstick_and_unlock(self):
        """Verify unstick_all_inputs and unlock_workstation methods exist and callable."""
        from host_agent.input_injector import InputInjector

        # Unstick all inputs
        res = InputInjector.unstick_all_inputs()
        self.assertIsInstance(res, int)
        if sys.platform == "win32":
            self.assertGreaterEqual(res, 258)
        else:
            self.assertGreaterEqual(res, 0)

        # Verify unlock_workstation is callable
        self.assertTrue(hasattr(InputInjector, "unlock_workstation"))
        self.assertTrue(callable(getattr(InputInjector, "unlock_workstation")))

    def test_screen_capture_desktop_attachment(self):
        """Verify _attach_window_station handles desktop switching logic."""
        from host_agent.screen_capture import ScreenCapture

        sc = ScreenCapture()
        self.assertTrue(hasattr(sc, "_attach_window_station"))
        # Should not raise exception
        try:
            res = sc._attach_window_station()
            self.assertIsInstance(res, bool)
        except Exception as e:
            self.fail(f"_attach_window_station raised an unexpected exception: {e}")

    def test_server_download_endpoints_coverage(self):
        """Verify server.js includes all 26 parameters across download scripts."""
        server_js = (REPO_ROOT / "relay-server" / "server.js").read_text(encoding="utf-8")

        # Verify extractHostConfigFromUrl function
        self.assertIn("function extractHostConfigFromUrl", server_js)

        # Verify parameter coverage
        required_params = [
            "relay", "account", "user_id", "device_name", "room_id", "pin",
            "fps", "quality", "preset", "stream_mode", "color_filter",
            "auto_lock_on_disconnect", "idle_fps_saver", "resolution",
            "stealth_mode", "service_mode", "admin_elevated", "keep_awake",
            "auto_wakeup", "auto_wakeup_time", "block_input", "privacy_curtain",
            "autostart", "close_to_tray", "audio_enabled", "headless"
        ]
        for param in required_params:
            self.assertIn(f'"{param}":', server_js, f"Missing parameter {param} in server.js")

        # Verify CLI loop %* in setup.bat
        self.assertIn('%*', server_js)
        # Verify CLI loop $@ in linux & macos scripts
        self.assertIn('"$@"', server_js)

    def test_web_client_parity(self):
        """Verify 100% SHA256 parity between relay-server/public and web-client."""
        sync_files = [
            ("relay-server/public/index.html", "web-client/index.html"),
            ("relay-server/public/css/style.css", "web-client/css/style.css"),
            ("relay-server/public/js/app.js", "web-client/js/app.js"),
            ("relay-server/public/js/i18n.js", "web-client/js/i18n.js"),
        ]
        for src_rel, dst_rel in sync_files:
            src = REPO_ROOT / src_rel
            dst = REPO_ROOT / dst_rel
            self.assertTrue(src.exists(), f"Source file missing: {src}")
            self.assertTrue(dst.exists(), f"Destination file missing: {dst}")

            h_src = hashlib.sha256(src.read_bytes()).hexdigest()
            h_dst = hashlib.sha256(dst.read_bytes()).hexdigest()
            self.assertEqual(h_src, h_dst, f"SHA256 mismatch for {src_rel} vs {dst_rel}")

    def test_i18n_keys_completeness(self):
        """Verify all new host management i18n keys are present in both vi and en."""
        import json
        import re

        i18n_file = (REPO_ROOT / "relay-server" / "public" / "js" / "i18n.js").read_text(encoding="utf-8")
        required_keys = [
            "deck.telemetry_host_title",
            "deck.btn_host_config",
            "deck.btn_unstick_inputs",
            "deck.btn_unlock_workstation",
            "modal.unlock_screen_btn",
            "toast.unstick_sent",
            "toast.unstick_success",
            "toast.unlock_sent",
            "toast.unlock_success",
            "toast.unlock_failed",
        ]
        for k in required_keys:
            count = i18n_file.count(f'"{k}":')
            self.assertGreaterEqual(count, 2, f"Key {k} must exist in both vi and en (found {count} times)")


if __name__ == "__main__":
    unittest.main()

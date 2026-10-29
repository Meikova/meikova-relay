import unittest
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from host_agent.deployment_manager import (
    get_permanent_dir,
    get_permanent_exe_path,
    get_user_install_dir,
    get_admin_install_dir,
    get_deployment_status,
    is_current_user_admin,
    cleanup_legacy_source_files,
    clean_legacy_registry_keys,
    register_protocol_handler,
    register_firewall_rule,
    self_deploy_if_needed,
    TASK_NAME,
    SERVICE_NAME
)
from host_agent.auto_updater import (
    parse_semver,
    cleanup_post_update,
)
import tempfile
import shutil

class TestDeploymentManager(unittest.TestCase):
    def test_user_install_dir(self):
        p = get_user_install_dir()
        self.assertIsInstance(p, Path)
        self.assertTrue(p.exists())
        self.assertTrue(
            "meikovarelayhost" in str(p).lower() or
            "meikova_relay_host" in str(p).lower() or
            "meikova-relay" in str(p).lower()
        )

    def test_admin_install_dir(self):
        p = get_admin_install_dir()
        self.assertIsInstance(p, Path)
        self.assertTrue("meikovarelayhost" in str(p).lower() or "meikova-relay-host" in str(p).lower())

    def test_permanent_exe_path(self):
        exe = get_permanent_exe_path()
        if sys.platform == "win32":
            self.assertEqual(exe.name, "MeikovaRelayHost.exe")
        elif sys.platform == "darwin":
            self.assertEqual(exe.name, "MeikovaRelayHost")
        else:
            self.assertEqual(exe.name, "meikova-relay-host")
        self.assertEqual(exe.parent, get_user_install_dir())

    def test_deployment_status_dictionary(self):
        status = get_deployment_status()
        self.assertIn("is_admin", status)
        self.assertIn("user_installed", status)
        self.assertIn("service_installed", status)
        self.assertIn("user_exe_path", status)
        self.assertIn("admin_exe_path", status)
        self.assertIsInstance(status["is_admin"], bool)

    def test_constants_naming(self):
        self.assertEqual(TASK_NAME, "MeikovaRelayHost")
        self.assertEqual(SERVICE_NAME, "MeikovaRelayService")

    def test_cleanup_legacy_source_files_comprehensive(self):
        """Verifies that all .py, scripts, and temp dirs are purged while config, exe, and icons are preserved."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_path = Path(tmp_dir)

            # Files that must be deleted
            junk_files = [
                "audio_capture.py",
                "gui_agent.py",
                "host_service.py",
                "__init__.py",
                "Install-MeikovaRelayHost.bat",
                "meikova-relay.service",
                "com.meikova.relay.plist",
                "requirements.txt",
                "gui_view.html",
                "old_script.sh",
            ]
            for jf in junk_files:
                (temp_path / jf).write_text("junk content", encoding="utf-8")

            # Junk directories that must be removed
            pycache_dir = temp_path / "__pycache__"
            pycache_dir.mkdir()
            (pycache_dir / "compiled.cpython-313.pyc").write_text("byte", encoding="utf-8")

            engines_dir = temp_path / "engines"
            engines_dir.mkdir()
            (engines_dir / "win.py").write_text("code", encoding="utf-8")

            # Assets that must be preserved
            (temp_path / "config.json").write_text('{"room": "RD-9999"}', encoding="utf-8")
            (temp_path / "MeikovaRelayHost.exe").write_bytes(b"MZfakebinary")
            (temp_path / "tray.log").write_text("logs", encoding="utf-8")
            (temp_path / "icon.ico").write_bytes(b"icodata")
            (temp_path / "icon.png").write_bytes(b"pngdata")
            (temp_path / "tray_icon.png").write_bytes(b"pngdata")

            tray_icons_dir = temp_path / "tray_icons"
            tray_icons_dir.mkdir()
            (tray_icons_dir / "active.png").write_bytes(b"pngdata")

            # Execute cleanup
            cleaned_count = cleanup_legacy_source_files(temp_path)
            self.assertGreater(cleaned_count, 0)

            # Verify junk files are gone
            for jf in junk_files:
                self.assertFalse((temp_path / jf).exists(), f"File {jf} should have been deleted!")
            self.assertFalse(pycache_dir.exists(), "__pycache__ should have been deleted!")
            self.assertFalse(engines_dir.exists(), "engines dir should have been deleted!")

            # Verify preserved assets remain intact
            self.assertTrue((temp_path / "config.json").exists())
            self.assertEqual((temp_path / "config.json").read_text(encoding="utf-8"), '{"room": "RD-9999"}')
            self.assertTrue((temp_path / "MeikovaRelayHost.exe").exists())
            self.assertTrue((temp_path / "tray.log").exists())
            self.assertTrue((temp_path / "icon.ico").exists())
            self.assertTrue((temp_path / "icon.png").exists())
            self.assertTrue((temp_path / "tray_icon.png").exists())
            self.assertTrue((tray_icons_dir / "active.png").exists())

    def test_clean_legacy_registry_keys(self):
        """Verifies clean_legacy_registry_keys runs cleanly."""
        res = clean_legacy_registry_keys()
        self.assertIsInstance(res, bool)

    def test_register_protocol_handler(self):
        """Verifies protocol registration in Windows registry."""
        if sys.platform == "win32":
            res = register_protocol_handler()
            self.assertTrue(res)

    def test_parse_semver(self):
        """Verifies SemVer comparisons for auto update."""
        self.assertEqual(parse_semver("1.4.2"), (1, 4, 2))
        self.assertEqual(parse_semver("v2.0.1"), (2, 0, 1))
        self.assertTrue(parse_semver("1.5.0") > parse_semver("1.4.9"))
        self.assertTrue(parse_semver("v1.4.3") > parse_semver("1.4.2"))
        self.assertFalse(parse_semver("1.4.2") > parse_semver("1.4.2"))

    def test_cleanup_post_update(self):
        """Verifies post-update cleanup of .old and .update artifacts."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_path = Path(tmp_dir)
            (temp_path / "MeikovaRelayHost.exe.old").write_bytes(b"old")
            (temp_path / "MeikovaRelayHost.exe.update").write_bytes(b"update")
            (temp_path / "MeikovaRelayHost.exe").write_bytes(b"new")

            cleaned = cleanup_post_update(temp_path)
            self.assertEqual(cleaned, 2)
            self.assertFalse((temp_path / "MeikovaRelayHost.exe.old").exists())
            self.assertFalse((temp_path / "MeikovaRelayHost.exe.update").exists())
            self.assertTrue((temp_path / "MeikovaRelayHost.exe").exists())

    def test_self_deploy_runs_without_error(self):
        """Verifies self_deploy_if_needed runs safely."""
        res = self_deploy_if_needed(relaunch=False)
        self.assertIsInstance(res, bool)

if __name__ == "__main__":
    unittest.main()

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
    TASK_NAME,
    SERVICE_NAME
)

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

if __name__ == "__main__":
    unittest.main()

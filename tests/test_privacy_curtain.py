import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from host_agent.privacy_curtain import PrivacyCurtain

class TestPrivacyCurtain(unittest.TestCase):
    def test_curtain_initial_state(self):
        """Tests that privacy curtain is initially inactive."""
        curtain = PrivacyCurtain()
        self.assertFalse(curtain.is_active)

    def test_curtain_enable_and_disable_lifecycle(self):
        """Tests enabling and immediately disabling privacy curtain lifecycle."""
        curtain = PrivacyCurtain()
        res_enable = curtain.enable()
        self.assertIsInstance(res_enable, dict)
        self.assertTrue(res_enable.get("success", False))
        self.assertTrue(curtain.is_active)

        res_disable = curtain.disable()
        self.assertIsInstance(res_disable, dict)
        self.assertTrue(res_disable.get("success", False))
        self.assertFalse(curtain.is_active)

if __name__ == "__main__":
    unittest.main()

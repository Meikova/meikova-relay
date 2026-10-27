import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from host_agent.privacy_curtain import PrivacyCurtain
from host_agent.input_injector import InputInjector


class TestBlockInputHooks(unittest.TestCase):
    def setUp(self):
        self.curtain = PrivacyCurtain()

    def tearDown(self):
        self.curtain.disable_all()

    def test_set_input_blocked_standalone(self):
        """Verify that physical input can be blocked without activating curtain window."""
        res = self.curtain.set_input_blocked(True)
        self.assertTrue(res.get("success", False))
        self.assertTrue(self.curtain.is_input_blocked)
        self.assertFalse(self.curtain.is_curtain_active)
        self.assertFalse(self.curtain.is_active)

        # Unblock
        res_off = self.curtain.set_input_blocked(False)
        self.assertTrue(res_off.get("success", False))
        self.assertFalse(self.curtain.is_input_blocked)

    def test_curtain_and_input_coordination(self):
        """Verify curtain enable turns on both, disable keeps input block if explicitly set."""
        self.curtain.set_input_blocked(True)
        self.curtain.enable()
        self.assertTrue(self.curtain.is_curtain_active)
        self.assertTrue(self.curtain.is_input_blocked)

        # Disabling curtain keeps input blocked because it was set
        self.curtain.disable()
        self.assertFalse(self.curtain.is_curtain_active)
        self.assertTrue(self.curtain.is_input_blocked)

        # disable_all resets everything
        self.curtain.disable_all()
        self.assertFalse(self.curtain.is_curtain_active)
        self.assertFalse(self.curtain.is_input_blocked)

    def test_input_injector_delegation(self):
        """Verify InputInjector.set_block_input operates cleanly."""
        res = InputInjector.set_block_input(True)
        self.assertIsInstance(res, bool)
        # Restore
        InputInjector.set_block_input(False)


if __name__ == "__main__":
    unittest.main()

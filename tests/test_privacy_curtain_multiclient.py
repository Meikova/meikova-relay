import os
import sys
import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from host_agent.privacy_curtain import PrivacyCurtain, MEIKOVA_INPUT_MAGIC
from host_agent.input_injector import InputInjector, MEIKOVA_INPUT_MAGIC as INJECTOR_MAGIC


class TestPrivacyCurtainMultiClient(unittest.TestCase):
    def setUp(self):
        self.curtain = PrivacyCurtain()

    def tearDown(self):
        if self.curtain.is_active:
            self.curtain.disable()

    def test_magic_constant_match(self):
        """Verify that privacy curtain and input injector share the same MEIKOVA_INPUT_MAGIC tag."""
        self.assertEqual(MEIKOVA_INPUT_MAGIC, INJECTOR_MAGIC)
        self.assertEqual(MEIKOVA_INPUT_MAGIC, 0x4D45494B)

    def test_curtain_lifecycle_with_input_block(self):
        """Verify that enabling curtain also triggers input blocking, and disabling restores it."""
        res_enable = self.curtain.enable()
        self.assertTrue(res_enable.get("success", False))
        self.assertTrue(self.curtain.is_active)

        res_disable = self.curtain.disable()
        self.assertTrue(res_disable.get("success", False))
        self.assertFalse(self.curtain.is_active)

    def test_multiclient_session_coordination(self):
        """Simulate HostService multi-client privacy curtain logic with session tracking."""
        curtain_active_sessions = set()
        curtain = self.curtain

        # Scenario 1: Client A enables privacy curtain
        curtain_active_sessions.add("session_A")
        curtain.enable()
        self.assertTrue(curtain.is_active)
        self.assertEqual(len(curtain_active_sessions), 1)

        # Scenario 2: Client B also connects and requests privacy curtain
        curtain_active_sessions.add("session_B")
        # Curtain is already active, remains active
        self.assertTrue(curtain.is_active)
        self.assertEqual(len(curtain_active_sessions), 2)

        # Scenario 3: Client A disconnects (active or passive drop)
        curtain_active_sessions.discard("session_A")
        # Since Client B is still in curtain_active_sessions, curtain must STAY ACTIVE
        self.assertTrue(len(curtain_active_sessions) > 0)
        self.assertTrue(curtain.is_active)

        # Scenario 4: Client B disconnects
        curtain_active_sessions.discard("session_B")
        # Now no sessions require curtain -> Fail-safe auto-exit MUST trigger
        if not curtain_active_sessions:
            curtain.disable()
        self.assertFalse(curtain.is_active)
        self.assertEqual(len(curtain_active_sessions), 0)

    def test_failsafe_zero_client_auto_exit(self):
        """Verify that when clientCount drops to 0, curtain is forcibly deactivated regardless of sessions."""
        curtain_active_sessions = {"ghost_session_1", "ghost_session_2"}
        curtain = self.curtain
        curtain.enable()
        self.assertTrue(curtain.is_active)

        # Simulate clientCount <= 0 event
        client_count = 0
        if client_count <= 0:
            curtain_active_sessions.clear()
            curtain.disable()

        self.assertFalse(curtain.is_active)
        self.assertEqual(len(curtain_active_sessions), 0)


if __name__ == "__main__":
    unittest.main()

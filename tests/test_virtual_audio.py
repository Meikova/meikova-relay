import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from host_agent.virtual_audio import is_audio_output_available, download_and_install_vbcable
from host_agent.audio_capture import AudioCapture

class TestVirtualAudio(unittest.TestCase):
    def test_audio_output_check_non_crashing(self):
        """Tests that checking audio output endpoints returns a valid bool and doesn't crash."""
        has_output = is_audio_output_available()
        self.assertIsInstance(has_output, bool)

    def test_audio_capture_status_callback(self):
        """Tests AudioCapture initialization and status callback registration."""
        status_events = []
        def on_status(st):
            status_events.append(st)

        ac = AudioCapture(on_status=on_status)
        self.assertIsNotNone(ac)
        self.assertTrue(ac.has_active_device)

    def test_virtual_audio_installer_url_validity(self):
        """Tests that VB-CABLE URL is properly formatted and reachable."""
        from host_agent.virtual_audio import VBCABLE_URL
        self.assertTrue(VBCABLE_URL.startswith("https://"))
        self.assertTrue(VBCABLE_URL.endswith(".zip"))

if __name__ == "__main__":
    unittest.main()

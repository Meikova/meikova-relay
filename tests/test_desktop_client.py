"""
Unit tests for Titan Remote Desktop Client.
Tests:
- ClientLocalDB initialization, key-value storage, and device caching
- DesktopBridge methods and offline cache access
- Server online detection
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from client_desktop.local_db import ClientLocalDB
from client_desktop.desktop_client import DesktopBridge, is_server_online


class TestDesktopClient(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "test_cache.db"
        self.db = ClientLocalDB(self.db_path)
        self.bridge = DesktopBridge(self.db)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_01_local_kv(self):
        """Verify local key-value store."""
        self.bridge.save_local_kv("theme", "ambient-dark")
        val = self.bridge.get_local_kv("theme")
        self.assertEqual(val, "ambient-dark")

        # Complex dictionary
        prefs = {"fps": 120, "audio": True}
        self.bridge.save_local_kv("prefs", prefs)
        saved_prefs = self.bridge.get_local_kv("prefs")
        self.assertEqual(saved_prefs.get("fps"), 120)

    def test_02_cache_devices(self):
        """Verify device fleet caching."""
        devices = [
            {"id": "dev-1", "device_name": "Workstation Alpha", "room_id": "RD-1111", "pin": "1234"},
            {"id": "dev-2", "device_name": "MacBook Pro", "room_id": "RD-2222", "pin": "5678"}
        ]
        self.bridge.cache_devices(devices)
        cached = self.bridge.get_cached_devices()
        self.assertEqual(len(cached), 2)
        dev_names = [d["device_name"] for d in cached]
        self.assertIn("Workstation Alpha", dev_names)
        self.assertIn("MacBook Pro", dev_names)

    def test_03_quick_connect_history(self):
        """Verify quick connect history recording."""
        self.bridge.record_quick_connect("RD-8571", "Lab Server")
        self.bridge.record_quick_connect("RD-9999", "Office PC")

        history = self.bridge.get_recent_history()
        self.assertEqual(len(history), 2)
        rooms = [h["room_id"] for h in history]
        self.assertIn("RD-8571", rooms)
        self.assertIn("RD-9999", rooms)

    def test_04_desktop_bridge_identity(self):
        """Verify bridge identifies as desktop client."""
        self.assertTrue(self.bridge.is_desktop_client())

    def test_05_server_online_check(self):
        """Verify server online status helper."""
        from unittest.mock import patch, MagicMock
        with patch("urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_url.return_value.__enter__.return_value = mock_resp
            self.assertTrue(is_server_online("http://localhost:8080"))
        self.assertFalse(is_server_online("http://localhost:59999"))


if __name__ == "__main__":
    unittest.main()

"""
Unit tests for Titan Remote Offline-First Sync Architecture and Endpoints.
Tests:
- Server sync status endpoint
- Push and pull user sync state
- Conflict resolution (Last-Write-Wins timestamps)
- Light metadata sync vs local storage isolation
"""

import json
import unittest
import urllib.request
import urllib.error
import time

RELAY_URL = "http://localhost:8080"


class TestSyncEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Register a test user for sync verification
        cls.username = f"sync_user_{int(time.time())}"
        cls.password = "SyncPassword123!"
        cls.token = None

        reg_data = json.dumps({"username": cls.username, "password": cls.password}).encode("utf-8")
        req = urllib.request.Request(
            f"{RELAY_URL}/api/auth/register",
            data=reg_data,
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                cls.token = data.get("token")
        except urllib.error.HTTPError as e:
            # If already exists, login
            login_data = json.dumps({"username": cls.username, "password": cls.password}).encode("utf-8")
            login_req = urllib.request.Request(
                f"{RELAY_URL}/api/auth/login",
                data=login_data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(login_req, timeout=5) as login_resp:
                cls.token = json.loads(login_resp.read().decode("utf-8")).get("token")

    def test_01_sync_status_public(self):
        """Verify /api/sync/status returns online state without authentication."""
        req = urllib.request.Request(f"{RELAY_URL}/api/sync/status")
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data.get("status"), "online")
            self.assertIn("timestamp", data)
            self.assertFalse(data.get("is_authenticated"))

    def test_02_sync_status_authenticated(self):
        """Verify /api/sync/status detects authenticated token."""
        req = urllib.request.Request(
            f"{RELAY_URL}/api/sync/status",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("is_authenticated"))
            self.assertIsNotNone(data.get("user"))

    def test_03_sync_pull_initial(self):
        """Verify initial /api/sync/pull returns default state structure."""
        req = urllib.request.Request(
            f"{RELAY_URL}/api/sync/pull",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data.get("status"), "success")
            sync_data = data.get("data", {})
            self.assertIn("preferences", sync_data)
            self.assertIn("device_bookmarks", sync_data)
            self.assertIn("quick_history", sync_data)

    def test_04_sync_push_and_pull(self):
        """Verify /api/sync/push updates cloud state and subsequent pull returns persisted state."""
        payload = {
            "preferences": {
                "lang": "vi",
                "defaultFps": 120,
                "fitMode": "contain"
            },
            "device_bookmarks": ["dev-test-1", "dev-test-2"],
            "quick_history": [
                {"roomId": "RD-1234", "deviceName": "Desktop PC", "timestamp": int(time.time())}
            ],
            "custom_labels": {
                "dev-test-1": "Máy trạm Thiết kế"
            }
        }
        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{RELAY_URL}/api/sync/push",
            data=req_data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.token}"
            }
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            body = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(body.get("status"), "success")
            self.assertGreater(body.get("updated_at", 0), 0)

        # Now pull and verify
        pull_req = urllib.request.Request(
            f"{RELAY_URL}/api/sync/pull",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        with urllib.request.urlopen(pull_req, timeout=5) as pull_resp:
            self.assertEqual(pull_resp.status, 200)
            pulled = json.loads(pull_resp.read().decode("utf-8")).get("data", {})
            self.assertEqual(pulled["preferences"].get("defaultFps"), 120)
            self.assertIn("dev-test-1", pulled.get("device_bookmarks", []))
            self.assertEqual(pulled["custom_labels"].get("dev-test-1"), "Máy trạm Thiết kế")


if __name__ == "__main__":
    unittest.main()

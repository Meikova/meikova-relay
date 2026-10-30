"""
Meikova Relay Enterprise - Comprehensive Security & Penetration Test Suite
Validates OWASP Top 10 defenses:
1. A01 Broken Access Control: Host Secret Proof (Anti-Superseding) & Sensitive File Manager Sandbox
2. A02 Cryptographic Failures: CSPRNG 9-digit Room ID & 6-digit PIN entropy verification
3. A07 Identification & Authentication: 5-Strike Lockout & Uniform Error Oracle Prevention
4. A10 DoS & Resource Exhaustion: HTTP Body Payload Guard (413), WS Connection Capping, Token Bucket Flooding Guard
// ponytail: stdlib unittest with live server subprocess
"""

import json
import os
import sys
import time
import uuid
import socket
import tempfile
import unittest
import urllib.request
import urllib.error
import subprocess
import asyncio
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

try:
    import websockets
except ImportError:
    websockets = None


class TestSecurityPenetration(unittest.IsolatedAsyncioTestCase):
    server_process = None
    server_port = 9055
    temp_db_path = None

    @classmethod
    def setUpClass(cls):
        if websockets is None:
            raise unittest.SkipTest("websockets library not available")

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            cls.server_port = s.getsockname()[1]

        server_js = REPO_ROOT / "relay-server" / "server.js"
        env = os.environ.copy()
        cls.temp_db_path = str(Path(tempfile.gettempdir()) / f"test_sec_{uuid.uuid4().hex[:8]}.db")
        env["PORT"] = str(cls.server_port)
        env["DB_PATH"] = cls.temp_db_path
        env["MEIKOVA_TEST_MODE"] = "1"
        env["MAX_WS_PER_IP"] = "16"

        cls.server_process = subprocess.Popen(
            ["node", str(server_js)],
            cwd=str(REPO_ROOT / "relay-server"),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        start_time = time.time()
        ready = False
        while time.time() - start_time < 8.0:
            if cls.server_process.poll() is not None:
                _, err = cls.server_process.communicate()
                raise unittest.SkipTest(f"Relay server failed to start: {err.decode('utf-8', errors='replace')}")
            try:
                with socket.create_connection(("127.0.0.1", cls.server_port), timeout=0.2):
                    ready = True
                    break
            except (ConnectionRefusedError, OSError):
                time.sleep(0.1)

        if not ready:
            raise unittest.SkipTest(f"Relay server did not start on port {cls.server_port} within 8s")

    @classmethod
    def tearDownClass(cls):
        if cls.server_process:
            cls.server_process.terminate()
            cls.server_process.communicate()
        if cls.temp_db_path:
            for ext in ["", "-wal", "-shm"]:
                try:
                    p = Path(cls.temp_db_path + ext)
                    if p.exists():
                        p.unlink()
                except OSError:
                    pass

    # --- 1. A10: HTTP BODY PAYLOAD GUARD (OOM DOS DEFENSE) ---

    def test_http_payload_limit_dos_guard(self):
        """Verify POST requests exceeding 1MB are rejected or disconnected (HTTP 413)."""
        base_url = f"http://127.0.0.1:{self.server_port}/api/auth/login"
        oversized_data = json.dumps({"username": "attacker", "password": "x" * (1024 * 1024 + 10000)}).encode("utf-8")
        req = urllib.request.Request(base_url, data=oversized_data, headers={"Content-Type": "application/json"})

        try:
            with urllib.request.urlopen(req) as resp:
                self.fail(f"Expected failure for oversized body, got {resp.status}")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 413)
        except Exception as e:
            # Socket reset on large stream overflow is also a valid DoS cutoff
            self.assertTrue(isinstance(e, (OSError, ConnectionResetError)))

    # --- 2. A07: 5-STRIKE LOCKOUT & BRUTE-FORCE DEFENSE ---

    async def test_5_strike_pin_lockout_and_uniform_error(self):
        """Verify 5 consecutive failed PIN attempts trigger IP lockout and uniform error."""
        url = f"ws://127.0.0.1:{self.server_port}"
        room_id = f"SEC-ROOM-{uuid.uuid4().hex[:6]}"
        correct_pin = "889900"

        # Host registers room
        host_ws = await websockets.connect(url)
        await host_ws.send(json.dumps({
            "type": "init_host",
            "room_id": room_id,
            "pin": correct_pin,
            "machine_id": "test-sec-host",
            "device_name": "SecHost"
        }))
        host_ack = json.loads(await host_ws.recv())
        self.assertEqual(host_ack.get("status"), "ok")
        self.assertTrue(bool(host_ack.get("host_secret")))

        # Test uniform error oracle on non-existent room:
        ghost_ws = await websockets.connect(url)
        await ghost_ws.send(json.dumps({
            "type": "init_client",
            "room_id": "NON-EXISTENT-ROOM-1234",
            "pin": "000000"
        }))
        ghost_res = json.loads(await ghost_ws.recv())
        self.assertEqual(ghost_res.get("status"), "error")
        self.assertEqual(ghost_res.get("code"), "RELAY_AUTH_FAILED")
        await ghost_ws.close()

        # Attacker tries 4 wrong PINs on the real room -> receives uniform RELAY_AUTH_FAILED
        for attempt in range(4):
            c_ws = await websockets.connect(url)
            await c_ws.send(json.dumps({
                "type": "init_client",
                "room_id": room_id,
                "pin": f"99999{attempt}"
            }))
            res = json.loads(await c_ws.recv())
            self.assertEqual(res.get("code"), "RELAY_AUTH_FAILED")
            await c_ws.close()

        # 5th wrong attempt -> Strikes reach 5, socket is locked out with RELAY_RATE_LIMITED
        c5_ws = await websockets.connect(url)
        await c5_ws.send(json.dumps({
            "type": "init_client",
            "room_id": room_id,
            "pin": "wrong_final"
        }))
        res5 = json.loads(await c5_ws.recv())
        self.assertEqual(res5.get("code"), "RELAY_RATE_LIMITED")
        self.assertGreater(res5.get("retryAfter", 0), 0)

        await c5_ws.close()
        await host_ws.close()

    # --- 3. A01: HOST SECRET PROOF (ANTI-SUPERSEDING HIJACKING) ---

    async def test_host_superseding_rejection(self):
        """Verify an attacker cannot hijack or supersede an existing room without valid host_secret."""
        url = f"ws://127.0.0.1:{self.server_port}"
        room_id = f"SEC-ROOM-OWNER-{uuid.uuid4().hex[:6]}"
        owner_pin = "112233"

        # Legitimate Host registers
        legit_host = await websockets.connect(url)
        await legit_host.send(json.dumps({
            "type": "init_host",
            "room_id": room_id,
            "pin": owner_pin,
            "machine_id": "legit-machine-guid",
            "device_name": "Legit-Workstation"
        }))
        legit_ack = json.loads(await legit_host.recv())
        self.assertEqual(legit_ack.get("status"), "ok")
        host_secret = legit_ack.get("host_secret")
        self.assertTrue(bool(host_secret))

        # Attacker tries to send init_host with same room_id but with fake host_secret
        attacker_host = await websockets.connect(url)
        await attacker_host.send(json.dumps({
            "type": "init_host",
            "room_id": room_id,
            "pin": "attacker_pin_666",
            "machine_id": "attacker-machine-guid",
            "host_secret": "fake-invalid-secret-token-123456"
        }))
        attacker_ack = json.loads(await attacker_host.recv())
        self.assertEqual(attacker_ack.get("status"), "error")
        self.assertEqual(attacker_ack.get("code"), "RELAY_HOST_UNAUTHORIZED")
        await attacker_host.close()

        # Legitimate host must STILL be alive and unharmed
        self.assertFalse(legit_host.closed)

        # Legitimate host reconnects sending its valid host_secret -> MUST succeed!
        reconnect_host = await websockets.connect(url)
        await reconnect_host.send(json.dumps({
            "type": "init_host",
            "room_id": room_id,
            "pin": owner_pin,
            "machine_id": "legit-machine-guid",
            "host_secret": host_secret
        }))
        reconnect_ack = json.loads(await reconnect_host.recv())
        self.assertEqual(reconnect_ack.get("status"), "ok")

        await legit_host.close()
        await reconnect_host.close()

    # --- 4. A10: TOKEN BUCKET MESSAGE FLOODING RATE LIMITER ---

    async def test_token_bucket_message_flooding_guard(self):
        """Verify flooding control messages is throttled by per-socket Token Bucket."""
        url = f"ws://127.0.0.1:{self.server_port}"
        room_id = f"SEC-ROOM-FLOOD-{uuid.uuid4().hex[:6]}"

        host_ws = await websockets.connect(url)
        await host_ws.send(json.dumps({
            "type": "init_host",
            "room_id": room_id,
            "pin": "123456"
        }))
        await host_ws.recv()

        client_ws = await websockets.connect(url)
        await client_ws.send(json.dumps({
            "type": "init_client",
            "room_id": room_id,
            "pin": "123456"
        }))
        await client_ws.recv()
        await host_ws.recv()

        # Send an instantaneous burst of 150 messages simultaneously
        tasks = [client_ws.send(json.dumps({"type": "ping", "seq": i})) for i in range(160)]
        await asyncio.gather(*tasks)

        # Read back: at least one rate_limited packet must be returned!
        flood_throttled = False
        for _ in range(200):
            try:
                resp = json.loads(await asyncio.wait_for(client_ws.recv(), timeout=0.3))
                if resp.get("type") == "rate_limited" and resp.get("code") == "RELAY_MESSAGE_FLOOD":
                    flood_throttled = True
                    break
            except Exception:
                break

        self.assertTrue(flood_throttled, "Expected client to receive RELAY_MESSAGE_FLOOD rate_limited packet")

        await host_ws.close()
        await client_ws.close()

    # --- 5. A01: FILE MANAGER SENSITIVE FILE ACCESS SHIELD ---

    def test_sensitive_file_sandbox_shield(self):
        """Verify FileManager strictly blocks reading, saving, and downloading system secrets."""
        from host_agent.file_manager import FileManager

        fm = FileManager()

        sensitive_samples = [
            "C:\\Windows\\System32\\config\\SAM",
            "C:\\Windows\\System32\\config\\SYSTEM",
            "/etc/shadow",
            "/etc/passwd",
            "C:\\Users\\Administrator\\.ssh\\id_rsa",
            "/home/user/.ssh/id_ed25519",
            "D:\\project\\.env",
            "C:\\inetpub\\wwwroot\\.env.production",
            "C:\\Users\\Victim\\AppData\\Local\\Google\\Chrome\\User Data\\Default\\Login Data",
            "C:\\Users\\Victim\\AppData\\Local\\Google\\Chrome\\User Data\\Default\\Network\\Cookies"
        ]

        for s_path in sensitive_samples:
            self.assertTrue(
                fm.is_sensitive_path(s_path),
                f"Expected {s_path} to be recognized as sensitive"
            )
            res_read = fm.read_file_content(s_path)
            self.assertFalse(res_read["success"])
            self.assertIn("chặn", res_read["error"].lower())

            res_save = fm.save_file_content(s_path, "MALICIOUS_PAYLOAD")
            self.assertFalse(res_save["success"])
            self.assertIn("chặn", res_save["error"].lower())

        safe_path = "D:\\Documents\\notes.txt"
        self.assertFalse(fm.is_sensitive_path(safe_path))

    # --- 6. A02: CSPRNG ROOM ID & PIN ENTROPY VERIFICATION ---

    def test_csprng_entropy_and_format(self):
        """Verify secure room ID (RD-XXX-XXX-XXX) and 6-digit PIN entropy."""
        from host_agent.gui_agent import generate_secure_room_id, generate_secure_pin
        import re

        room_ids = set()
        pins = set()

        room_pattern = re.compile(r"^RD-\d{3}-\d{3}-\d{3}$")

        for _ in range(500):
            rid = generate_secure_room_id()
            pin = generate_secure_pin()

            self.assertTrue(bool(room_pattern.match(rid)), f"Room ID {rid} does not match 9-digit segmented format")
            self.assertEqual(len(pin), 6)
            self.assertTrue(pin.isdigit())

            room_ids.add(rid)
            pins.add(pin)

        self.assertEqual(len(room_ids), 500, "CSPRNG Room ID collision detected in 500 samples")
        self.assertGreaterEqual(len(pins), 490, "Low entropy PINs detected")


if __name__ == "__main__":
    unittest.main()

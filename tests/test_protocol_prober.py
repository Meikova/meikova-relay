"""
Unit tests for host_agent/protocol_prober.py.
Tests port probing, protocol identification, banner parsing, and matrix aggregation.
"""

import socket
import threading
import time
import unittest
from host_agent.protocol_prober import (
    probe_tcp_port,
    probe_rdp,
    probe_ssh,
    probe_sftp,
    probe_ftp,
    probe_vnc,
    probe_all_protocols
)

class TestProtocolProber(unittest.TestCase):

    def _start_mock_server(self, response_bytes: bytes = b"", banner_first: bool = True):
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.bind(("127.0.0.1", 0))
        server_sock.listen(1)
        port = server_sock.getsockname()[1]

        def handler():
            try:
                server_sock.settimeout(2.0)
                conn, _ = server_sock.accept()
                with conn:
                    if banner_first and response_bytes:
                        conn.sendall(response_bytes)
                    elif not banner_first:
                        _ = conn.recv(128)
                        if response_bytes:
                            conn.sendall(response_bytes)
            except Exception:
                pass
            finally:
                server_sock.close()

        t = threading.Thread(target=handler, daemon=True)
        t.start()
        return port

    def test_probe_tcp_port(self):
        port = self._start_mock_server()
        time.sleep(0.05)
        self.assertTrue(probe_tcp_port("127.0.0.1", port))
        # Non-listening port
        self.assertFalse(probe_tcp_port("127.0.0.1", 59999))

    def test_probe_ssh_active(self):
        port = self._start_mock_server(b"SSH-2.0-OpenSSH_9.3\r\n", banner_first=True)
        time.sleep(0.05)
        res = probe_ssh("127.0.0.1", port)
        self.assertTrue(res["available"])
        self.assertTrue(res["banner"].startswith("SSH-2.0"))

    def test_probe_ssh_closed(self):
        res = probe_ssh("127.0.0.1", 59998)
        self.assertFalse(res["available"])

    def test_probe_rdp_active(self):
        # Mock X.224 Connection Confirm response
        x224_cc = b"\x03\x00\x00\x0b\x06\xd0\x00\x00\x12\x34\x00"
        port = self._start_mock_server(x224_cc, banner_first=False)
        time.sleep(0.05)
        res = probe_rdp("127.0.0.1", port)
        self.assertTrue(res["available"])
        self.assertTrue(res["handshake"])
        self.assertIn("RDP TermService active", res["details"])

    def test_probe_ftp(self):
        port = self._start_mock_server(b"220 ProFTPD 1.3 Ready.\r\n", banner_first=True)
        time.sleep(0.05)
        res = probe_ftp("127.0.0.1", port)
        self.assertTrue(res["available"])
        self.assertIn("220", res["banner"])

    def test_probe_vnc(self):
        port = self._start_mock_server(b"RFB 003.008\n", banner_first=True)
        time.sleep(0.05)
        res = probe_vnc("127.0.0.1", port)
        self.assertTrue(res["available"])
        self.assertTrue(res["banner"].startswith("RFB"))

    def test_probe_all_protocols_matrix(self):
        matrix = probe_all_protocols("127.0.0.1")
        self.assertIn("remote", matrix)
        self.assertIn("terminal", matrix)
        self.assertIn("file", matrix)
        self.assertIn("preferred", matrix["remote"])
        self.assertIn("preferred", matrix["terminal"])
        self.assertIn("preferred", matrix["file"])
        # Meikova bypass must always be guaranteed available
        self.assertTrue(matrix["remote"]["bypass"]["available"])
        self.assertTrue(matrix["terminal"]["bypass"]["available"])
        self.assertTrue(matrix["file"]["bypass"]["available"])

if __name__ == "__main__":
    unittest.main()

import os
import time
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from host_agent.system_manager import SystemManager
from host_agent.terminal_manager import TerminalManager
from host_agent.file_manager import FileManager
from host_agent.power_manager import PowerManager

class TestExtendedFeatures(unittest.TestCase):
    def test_hardware_telemetry(self):
        stats = SystemManager.get_hardware_telemetry()
        self.assertIn("ram", stats)
        self.assertIn("total_gb", stats["ram"])
        self.assertGreater(stats["ram"]["total_gb"], 0)
        self.assertIn("disks", stats)
        self.assertGreaterEqual(len(stats["disks"]), 1)

    def test_process_list(self):
        procs = SystemManager.get_process_list(limit=10)
        self.assertIsInstance(procs, list)
        self.assertGreater(len(procs), 0)
        first = procs[0]
        self.assertIn("pid", first)
        self.assertIn("name", first)
        self.assertIn("memory_mb", first)

    def test_file_manager_browse(self):
        fm = FileManager()
        # Browse drives
        drives = fm.browse_path("")
        self.assertIn("items", drives)
        self.assertIn("drives", drives)
        self.assertGreater(len(drives["items"]), 0)
        first_drive = drives["drives"][0]
        self.assertIn("total", first_drive)
        self.assertIn("free", first_drive)

        # Browse current folder
        curr = fm.browse_path(os.path.dirname(__file__))
        self.assertIn("items", curr)
        self.assertIn("drives", curr)
        self.assertIn("parent_path", curr)
        found_self = any(item["name"] == "test_extended_features.py" for item in curr["items"])
        self.assertTrue(found_self)

    def test_file_manager_folder_ops_and_target_upload(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            fm = FileManager(download_dir=tmpdir)
            # Create folder
            res = fm.create_folder(tmpdir, "test_subfolder")
            self.assertTrue(res["success"])
            subpath = res["path"]
            self.assertTrue(os.path.isdir(subpath))

            # Targeted upload into subfolder
            data = b"Enterprise Targeted File Data"
            dest = fm.start_upload("tx_target", "inner.txt", len(data), target_dir=subpath)
            self.assertTrue(dest.startswith(subpath))
            fm.write_chunk("tx_target", data)
            fin = fm.finish_upload("tx_target")
            self.assertTrue(fin["valid"])
            self.assertTrue(os.path.isfile(dest))

            # Delete folder
            ok = fm.delete_item(subpath)
            self.assertTrue(ok)
            self.assertFalse(os.path.exists(subpath))

    def test_terminal_interaction(self):
        output_received = []
        def on_out(data):
            output_received.append(data)

        term = TerminalManager(on_output=on_out)
        term.start()
        time.sleep(1.0)
        term.send_input("Write-Output 'TITAN_TEST_OK'")
        time.sleep(1.0)
        term.stop()

        full_output = "".join(output_received)
        self.assertIn("TITAN", full_output)

    def test_file_transfer_integrity(self):
        import tempfile
        import hashlib
        with tempfile.TemporaryDirectory() as tmpdir:
            fm = FileManager(download_dir=tmpdir)
            data = b"Hello Titan Remote Enterprise Stream" * 100
            expected_hash = hashlib.sha256(data).hexdigest()
            dest = fm.start_upload("tx1", "test.bin", len(data), expected_hash)
            # Write chunk
            res = fm.write_chunk("tx1", data)
            self.assertEqual(res["progress"], 100)
            fin = fm.finish_upload("tx1")
            self.assertTrue(fin["valid"])
            self.assertEqual(fin["sha256"], expected_hash)
            self.assertTrue(os.path.isfile(dest))

if __name__ == "__main__":
    unittest.main()

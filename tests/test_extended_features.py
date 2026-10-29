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
from host_agent.audio_capture import AudioCapture
from host_agent.audio_playback import AudioPlayback

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
        time.sleep(0.5)
        cmd = "Write-Output 'MEIKOVA_TEST_OK'" if sys.platform == "win32" else "echo 'MEIKOVA_TEST_OK'"
        for attempt in range(25):
            if any("MEIKOVA" in o for o in output_received):
                break
            if attempt % 3 == 0:
                term.send_input(cmd)
            time.sleep(0.2)
        term.stop()

        full_output = "".join(output_received)
        self.assertIn("MEIKOVA", full_output)

    def test_file_transfer_integrity(self):
        import tempfile
        import hashlib
        with tempfile.TemporaryDirectory() as tmpdir:
            fm = FileManager(download_dir=tmpdir)
            data = b"Hello Meikova Relay Enterprise Stream" * 100
            expected_hash = hashlib.sha256(data).hexdigest()
            dest = fm.start_upload("tx1", "test.bin", len(data), expected_hash)
            # Write chunk
            res = fm.write_chunk("tx1", data)
            self.assertEqual(res["progress"], 100)
            fin = fm.finish_upload("tx1")
            self.assertTrue(fin["valid"])
    def test_audio_capture_lifecycle(self):
        chunks = []
        def on_chunk(data, rate, channels):
            chunks.append((len(data), rate, channels))

        ac = AudioCapture(on_chunk=on_chunk)
        ac.start()
        for _ in range(40):
            if chunks:
                break
            time.sleep(0.04)
        ac.stop()
        self.assertGreaterEqual(len(chunks), 1)
        self.assertEqual(ac.channels, 2)
        self.assertGreaterEqual(ac.sample_rate, 44100)

    def test_vietnamese_unicode_file_and_folder_operations(self):
        import tempfile
        import unicodedata
        with tempfile.TemporaryDirectory() as tmpdir:
            fm = FileManager(download_dir=tmpdir)
            vn_folder_name = "Tài liệu thuyết trình Q4"
            res = fm.create_folder(tmpdir, vn_folder_name)
            self.assertTrue(res["success"])
            folder_path = res["path"]
            self.assertTrue(os.path.isdir(folder_path))

            # Upload PowerPoint file with Vietnamese diacritics
            vn_filename = "Báo cáo doanh thu & kế hoạch.pptx"
            content = b"PowerPoint Presentation Data Content"
            dest = fm.start_upload("tx_vn", vn_filename, len(content), target_dir=folder_path)
            self.assertTrue(os.path.basename(dest).endswith(".pptx"))
            fm.write_chunk("tx_vn", content)
            fin = fm.finish_upload("tx_vn")
            self.assertTrue(fin["valid"])

            # Browse folder and verify items
            browse_res = fm.browse_path(folder_path)
            items = browse_res["items"]
            self.assertEqual(len(items), 1)
            self.assertEqual(unicodedata.normalize('NFC', items[0]["name"]), unicodedata.normalize('NFC', vn_filename))
            self.assertEqual(items[0]["ext"], ".pptx")

            # Clean up
            ok = fm.delete_item(folder_path)
            self.assertTrue(ok)
            self.assertFalse(os.path.exists(folder_path))

    def test_vietnamese_terminal_utf8(self):
        output_received = []
        def on_out(data):
            output_received.append(data)

        term = TerminalManager(on_output=on_out)
        term.start()
        time.sleep(0.5)

        cmd = "Write-Output 'Tiếng Việt: Hà Nội - Đà Nẵng - Sài Gòn'" if sys.platform == "win32" else "echo 'Tiếng Việt: Hà Nội - Đà Nẵng - Sài Gòn'"
        for attempt in range(40):
            if any("Hà Nội" in o for o in output_received):
                break
            if attempt % 5 == 0:
                term.send_input(cmd)
            time.sleep(0.2)
        term.stop()

        full_output = "".join(output_received)
        self.assertIn("Hà Nội", full_output)
        self.assertIn("Đà Nẵng", full_output)
        self.assertIn("Sài Gòn", full_output)

    def test_audio_playback_lifecycle(self):
        ap = AudioPlayback(sample_rate=16000, channels=1)
        ap.start()
        self.assertTrue(ap.running)
        dummy = b"\x00\x00" * int(16000 * 0.05)
        ap.play_chunk(dummy)
        time.sleep(0.1)
        ap.stop()
        self.assertFalse(ap.running)

    def test_power_manager_prevent_sleep_and_wakeup(self):
        self.assertTrue(PowerManager.prevent_sleep(True))
        self.assertTrue(PowerManager.prevent_sleep(False))
        wake_res = PowerManager.configure_auto_wakeup(True, "07:30")
        self.assertIsInstance(wake_res, dict)
        self.assertTrue(wake_res.get("success", False))
        wol_res = PowerManager.send_wake_on_lan("11:22:33:44:55:66")
        self.assertIsInstance(wol_res, dict)
        self.assertTrue(wol_res.get("success", False))

    def test_input_injector_unstick_all_inputs(self):
        from host_agent.input_injector import InputInjector
        released = InputInjector.unstick_all_inputs()
        if sys.platform == "win32":
            self.assertGreaterEqual(released, 258)
        else:
            self.assertGreaterEqual(released, 0)

    def test_input_injector_unlock_workstation_logic(self):
        from host_agent.input_injector import InputInjector
        res = InputInjector.unlock_workstation("")
        if sys.platform == "win32":
            self.assertTrue(res)

if __name__ == "__main__":
    unittest.main()

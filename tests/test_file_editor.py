import os
import tempfile
import unittest
from host_agent.file_manager import FileManager

class TestFileEditor(unittest.TestCase):
    def setUp(self):
        self.fm = FileManager()
        self.test_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.test_dir.cleanup()

    def test_read_and_save_vietnamese_text_file(self):
        test_file = os.path.join(self.test_dir.name, "ghi_chu_tieng_viet.txt")
        initial_content = "Xin chào Titan Remote!\nThử nghiệm chỉnh sửa trực tiếp: Hà Nội, Đà Nẵng, TP. Hồ Chí Minh."

        # Save file directly
        save_res = self.fm.save_file_content(test_file, initial_content, encoding="utf-8")
        self.assertTrue(save_res["success"])
        self.assertEqual(save_res["filename"], "ghi_chu_tieng_viet.txt")
        self.assertTrue(os.path.exists(test_file))

        # Read file back directly
        read_res = self.fm.read_file_content(test_file)
        self.assertTrue(read_res["success"])
        self.assertEqual(read_res["content"], initial_content)
        self.assertIn("Hà Nội", read_res["content"])
        self.assertIn("Hồ Chí Minh", read_res["content"])

        # Edit and save again
        updated_content = initial_content + "\nĐã cập nhật dòng mới lúc 20:12:00!"
        save_res2 = self.fm.save_file_content(test_file, updated_content, encoding="utf-8")
        self.assertTrue(save_res2["success"])

        read_res2 = self.fm.read_file_content(test_file)
        self.assertTrue(read_res2["success"])
        self.assertEqual(read_res2["content"], updated_content)

    def test_binary_file_guard(self):
        bin_file = os.path.join(self.test_dir.name, "image.bin")
        with open(bin_file, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00")

        res = self.fm.read_file_content(bin_file)
        self.assertFalse(res["success"])
        self.assertIn("nhị phân", res["error"])

if __name__ == "__main__":
    unittest.main()

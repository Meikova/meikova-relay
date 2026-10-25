import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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
        initial_content = "Xin chào Meikova Relay!\nThử nghiệm chỉnh sửa trực tiếp: Hà Nội, Đà Nẵng, TP. Hồ Chí Minh."

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


    def test_copy_move_rename_file_and_folder(self):
        src_file = os.path.join(self.test_dir.name, "test_doc.txt")
        with open(src_file, "w", encoding="utf-8") as f:
            f.write("Meikova Relay File Operations")

        sub_dir = os.path.join(self.test_dir.name, "target_sub")
        os.makedirs(sub_dir, exist_ok=True)

        # 1. Test Copy
        copy_res = self.fm.copy_item(src_file, sub_dir)
        self.assertTrue(copy_res["success"])
        copied_file = os.path.join(sub_dir, "test_doc.txt")
        self.assertTrue(os.path.exists(copied_file))
        self.assertTrue(os.path.exists(src_file))

        # 2. Test Rename
        rename_res = self.fm.rename_item(copied_file, "renamed_doc.txt")
        self.assertTrue(rename_res["success"])
        renamed_file = os.path.join(sub_dir, "renamed_doc.txt")
        self.assertTrue(os.path.exists(renamed_file))
        self.assertFalse(os.path.exists(copied_file))

        # 3. Test Move
        sub_dir2 = os.path.join(self.test_dir.name, "target_sub2")
        os.makedirs(sub_dir2, exist_ok=True)
        move_res = self.fm.move_item(renamed_file, sub_dir2)
        self.assertTrue(move_res["success"])
        moved_file = os.path.join(sub_dir2, "renamed_doc.txt")
        self.assertTrue(os.path.exists(moved_file))
        self.assertFalse(os.path.exists(renamed_file))

    def test_nested_folder_upload_structure(self):
        dest = self.fm.start_upload("tx_test_nested", "deep/project/sub/code.js", 1024, target_dir=self.test_dir.name)
        self.fm.finish_upload("tx_test_nested")
        expected_dest = os.path.join(self.test_dir.name, "deep", "project", "sub", "code.js")
        self.assertEqual(os.path.abspath(dest), os.path.abspath(expected_dest))
        self.assertTrue(os.path.exists(expected_dest))

if __name__ == "__main__":
    unittest.main()

import unittest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from host_agent.input_injector import InputInjector
from host_agent.input_mapper import InputMapper

class TestVietnameseInput(unittest.TestCase):
    def test_unicode_normalization_and_characters(self):
        # Vietnamese text with combined accents and special characters
        sample_text = "Tiếng Việt có dấu: ă, â, đ, ê, ô, ơ, ư, ã, ả, ạ, á, à"
        
        sent_inputs = []
        def fake_send(inp):
            sent_inputs.append((inp.u.ki.wScan, inp.u.ki.dwFlags))

        with patch.object(InputInjector, '_send', side_effect=fake_send):
            InputInjector.type_unicode(sample_text)

        self.assertGreater(len(sent_inputs), 0)
        # Verify that ord of characters like 'đ' (0x0111 = 273), 'ă' (0x0103 = 259) are passed in wScan
        scans = [s[0] for s in sent_inputs]
        self.assertIn(ord('đ'), scans)
        self.assertIn(ord('ă'), scans)
        self.assertIn(ord('ê'), scans)

    def test_type_unicode_multiline_newlines(self):
        text = "Dong 1\nDong 2\r\nDong 3"
        down_vks = []
        up_vks = []

        def fake_down(vk):
            down_vks.append(vk)
        def fake_up(vk):
            up_vks.append(vk)

        with patch.object(InputInjector, 'key_down', side_effect=fake_down), \
             patch.object(InputInjector, 'key_up', side_effect=fake_up), \
             patch.object(InputInjector, '_send', return_value=None):
            InputInjector.type_unicode(text)

        # VK_RETURN is 0x0D (13)
        self.assertEqual(down_vks.count(0x0D), 2)
        self.assertEqual(up_vks.count(0x0D), 2)

    def test_input_mapper_does_not_break_on_unidentified_or_vietnamese(self):
        # Synthetic / IME key codes should safely map to 0 without exception
        self.assertEqual(InputMapper.js_code_to_vk(""), 0)
        self.assertEqual(InputMapper.js_code_to_vk("Unidentified"), 0)
        self.assertEqual(InputMapper.js_code_to_vk("Process"), 0)

if __name__ == "__main__":
    unittest.main()

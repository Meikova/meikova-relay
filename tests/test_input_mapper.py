import unittest

try:
    from host_agent.input_mapper import InputMapper
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from host_agent.input_mapper import InputMapper

class TestInputMapper(unittest.TestCase):
    def test_normalize_coordinates_to_windows_absolute(self):
        # Windows SendInput absolute mouse coordinates map 0.0 -> 0 and 1.0 -> 65535
        dx, dy = InputMapper.to_windows_coords(0.0, 0.0)
        self.assertEqual(dx, 0)
        self.assertEqual(dy, 0)

        dx, dy = InputMapper.to_windows_coords(1.0, 1.0)
        self.assertEqual(dx, 65535)
        self.assertEqual(dy, 65535)

        dx, dy = InputMapper.to_windows_coords(0.5, 0.5)
        self.assertTrue(32760 <= dx <= 32770)
        self.assertTrue(32760 <= dy <= 32770)

    def test_map_js_key_code_to_windows_vk(self):
        # Enter -> 0x0D (13)
        self.assertEqual(InputMapper.js_code_to_vk("Enter"), 0x0D)
        # Backspace -> 0x08 (8)
        self.assertEqual(InputMapper.js_code_to_vk("Backspace"), 0x08)
        # Tab -> 0x09 (9)
        self.assertEqual(InputMapper.js_code_to_vk("Tab"), 0x09)
        # Escape -> 0x1B (27)
        self.assertEqual(InputMapper.js_code_to_vk("Escape"), 0x1B)
        # ControlLeft -> 0x11 (17)
        self.assertEqual(InputMapper.js_code_to_vk("ControlLeft"), 0x11)
        # AltLeft -> 0x12 (18)
        self.assertEqual(InputMapper.js_code_to_vk("AltLeft"), 0x12)
        # ShiftLeft -> 0x10 (16)
        self.assertEqual(InputMapper.js_code_to_vk("ShiftLeft"), 0x10)
        # MetaLeft / Win -> 0x5B (91)
        self.assertEqual(InputMapper.js_code_to_vk("MetaLeft"), 0x5B)

    def test_map_letters(self):
        self.assertEqual(InputMapper.js_code_to_vk("KeyA"), 0x41)
        self.assertEqual(InputMapper.js_code_to_vk("KeyZ"), 0x5A)

    def test_map_numbers(self):
        self.assertEqual(InputMapper.js_code_to_vk("Digit0"), 0x30)
        self.assertEqual(InputMapper.js_code_to_vk("Digit9"), 0x39)

    def test_unknown_code_fallback(self):
        # Returns 0 or None if unknown
        self.assertEqual(InputMapper.js_code_to_vk("UnknownNonExistentKey"), 0)

if __name__ == "__main__":
    unittest.main()

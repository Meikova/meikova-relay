import unittest
import json

# Import the module to be implemented
try:
    from host_agent.protocol import Protocol
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from host_agent.protocol import Protocol

class TestProtocol(unittest.TestCase):
    def test_encode_decode_auth_packet(self):
        packet = Protocol.create_host_init(room_id="TEST-123", pin="123456", width=1920, height=1080)
        data = json.loads(packet)
        self.assertEqual(data["type"], "init_host")
        self.assertEqual(data["room_id"], "TEST-123")
        self.assertEqual(data["pin"], "123456")
        self.assertEqual(data["width"], 1920)
        self.assertEqual(data["height"], 1080)

    def test_parse_valid_mouse_move(self):
        msg = json.dumps({"type": "mouse_move", "x": 0.5, "y": 0.25})
        parsed = Protocol.parse_input_event(msg)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["type"], "mouse_move")
        self.assertAlmostEqual(parsed["x"], 0.5)
        self.assertAlmostEqual(parsed["y"], 0.25)

    def test_parse_invalid_mouse_coordinates(self):
        # Clamped or rejected if outside valid boundaries
        msg = json.dumps({"type": "mouse_move", "x": -0.2, "y": 1.5})
        parsed = Protocol.parse_input_event(msg)
        self.assertIsNotNone(parsed)
        # Should be clamped between 0.0 and 1.0
        self.assertEqual(parsed["x"], 0.0)
        self.assertEqual(parsed["y"], 1.0)

    def test_parse_mouse_click(self):
        msg = json.dumps({"type": "mouse_down", "button": 0})
        parsed = Protocol.parse_input_event(msg)
        self.assertEqual(parsed["type"], "mouse_down")
        self.assertEqual(parsed["button"], 0)

    def test_parse_key_event(self):
        msg = json.dumps({"type": "key_down", "code": "KeyA", "vk": 65})
        parsed = Protocol.parse_input_event(msg)
        self.assertEqual(parsed["type"], "key_down")
        self.assertEqual(parsed["vk"], 65)

    def test_parse_malformed_json(self):
        parsed = Protocol.parse_input_event("invalid-not-json")
        self.assertIsNone(parsed)

    def test_parse_missing_type(self):
        parsed = Protocol.parse_input_event(json.dumps({"some": "data"}))
        self.assertIsNone(parsed)

if __name__ == "__main__":
    unittest.main()

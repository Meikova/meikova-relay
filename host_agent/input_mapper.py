from typing import Tuple, Dict

class InputMapper:
    """Maps browser mouse coordinates and JS key codes to Windows Win32 inputs."""

    # Map of JavaScript KeyboardEvent.code to Windows Virtual-Key code
    JS_CODE_TO_VK: Dict[str, int] = {
        # Control & Special Keys
        "Backspace": 0x08,
        "Tab": 0x09,
        "Clear": 0x0C,
        "Enter": 0x0D,
        "NumpadEnter": 0x0D,
        "ShiftLeft": 0x10,
        "ShiftRight": 0x10,
        "ControlLeft": 0x11,
        "ControlRight": 0x11,
        "AltLeft": 0x12,
        "AltRight": 0x12,
        "Pause": 0x13,
        "CapsLock": 0x14,
        "Escape": 0x1B,
        "Space": 0x20,
        "PageUp": 0x21,
        "PageDown": 0x22,
        "End": 0x23,
        "Home": 0x24,
        "ArrowLeft": 0x25,
        "ArrowUp": 0x26,
        "ArrowRight": 0x27,
        "ArrowDown": 0x28,
        "PrintScreen": 0x2C,
        "Insert": 0x2D,
        "Delete": 0x2E,
        "MetaLeft": 0x5B,     # Left Windows Key
        "MetaRight": 0x5C,    # Right Windows Key
        "ContextMenu": 0x5D,  # Context Menu Key

        # Digits 0-9
        "Digit0": 0x30, "Digit1": 0x31, "Digit2": 0x32, "Digit3": 0x33, "Digit4": 0x34,
        "Digit5": 0x35, "Digit6": 0x36, "Digit7": 0x37, "Digit8": 0x38, "Digit9": 0x39,

        # Letters A-Z
        "KeyA": 0x41, "KeyB": 0x42, "KeyC": 0x43, "KeyD": 0x44, "KeyE": 0x45,
        "KeyF": 0x46, "KeyG": 0x47, "KeyH": 0x48, "KeyI": 0x49, "KeyJ": 0x4A,
        "KeyK": 0x4B, "KeyL": 0x4C, "KeyM": 0x4D, "KeyN": 0x4E, "KeyO": 0x4F,
        "KeyP": 0x50, "KeyQ": 0x51, "KeyR": 0x52, "KeyS": 0x53, "KeyT": 0x54,
        "KeyU": 0x55, "KeyV": 0x56, "KeyW": 0x57, "KeyX": 0x58, "KeyY": 0x59,
        "KeyZ": 0x5A,

        # Function Keys F1-F12
        "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73, "F5": 0x74, "F6": 0x75,
        "F7": 0x76, "F8": 0x77, "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,

        # Punctuation & Symbols
        "Semicolon": 0xBA,
        "Equal": 0xBB,
        "Comma": 0xBC,
        "Minus": 0xBD,
        "Period": 0xBE,
        "Slash": 0xBF,
        "Backquote": 0xC0,
        "BracketLeft": 0xDB,
        "Backslash": 0xDC,
        "BracketRight": 0xDD,
        "Quote": 0xDE,
    }

    @staticmethod
    def to_windows_coords(norm_x: float, norm_y: float) -> Tuple[int, int]:
        """Convert normalized [0.0, 1.0] coordinates to Windows SendInput [0, 65535] absolute space."""
        clamped_x = max(0.0, min(1.0, float(norm_x)))
        clamped_y = max(0.0, min(1.0, float(norm_y)))
        dx = int(clamped_x * 65535.0)
        dy = int(clamped_y * 65535.0)
        return dx, dy

    @classmethod
    def js_code_to_vk(cls, js_code: str) -> int:
        """Convert a JavaScript KeyboardEvent.code string to Windows Virtual Key integer."""
        return cls.JS_CODE_TO_VK.get(js_code, 0)

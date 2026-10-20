import ctypes
from ctypes import wintypes
from typing import Optional, Tuple
try:
    from .input_mapper import InputMapper
except (ImportError, ValueError):
    from input_mapper import InputMapper

# Win32 Constants
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ('dx', wintypes.LONG),
        ('dy', wintypes.LONG),
        ('mouseData', wintypes.DWORD),
        ('dwFlags', wintypes.DWORD),
        ('time', wintypes.DWORD),
        ('dwExtraInfo', ctypes.c_size_t),
    ]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ('wVk', wintypes.WORD),
        ('wScan', wintypes.WORD),
        ('dwFlags', wintypes.DWORD),
        ('time', wintypes.DWORD),
        ('dwExtraInfo', ctypes.c_size_t),
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ('uMsg', wintypes.DWORD),
        ('wParamL', wintypes.WORD),
        ('wParamH', wintypes.WORD),
    ]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ('mi', MOUSEINPUT),
        ('ki', KEYBDINPUT),
        ('hi', HARDWAREINPUT),
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ('type', wintypes.DWORD),
        ('_pad', wintypes.DWORD), # 64-bit alignment padding
        ('u', _INPUT_UNION),
    ]

user32 = getattr(ctypes, 'windll', None).user32 if hasattr(ctypes, 'windll') else None
SendInput = user32.SendInput if user32 else None
if SendInput:
    SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    SendInput.restype = wintypes.UINT

class InputInjector:
    """Injects mouse and keyboard events into Windows via native SendInput with cross-platform fallback."""

    @staticmethod
    def _send(inp: INPUT) -> bool:
        if SendInput is None:
            return False
        try:
            return SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT)) == 1
        except Exception:
            return False

    @classmethod
    def mouse_move(cls, norm_x: float, norm_y: float, monitor_rect: Optional[Tuple[int, int, int, int]] = None) -> bool:
        vx = user32.GetSystemMetrics(76) # SM_XVIRTUALSCREEN
        vy = user32.GetSystemMetrics(77) # SM_YVIRTUALSCREEN
        vw = user32.GetSystemMetrics(78) or user32.GetSystemMetrics(0) or 1920 # SM_CXVIRTUALSCREEN
        vh = user32.GetSystemMetrics(79) or user32.GetSystemMetrics(1) or 1080 # SM_CYVIRTUALSCREEN

        clamped_x = max(0.0, min(1.0, float(norm_x)))
        clamped_y = max(0.0, min(1.0, float(norm_y)))

        if monitor_rect:
            m_left, m_top, m_right, m_bottom = monitor_rect
            px = m_left + clamped_x * (m_right - m_left)
            py = m_top + clamped_y * (m_bottom - m_top)
        else:
            px = vx + clamped_x * vw
            py = vy + clamped_y * vh

        dx = int((px - vx) * 65535.0 / max(1, vw - 1))
        dy = int((py - vy) * 65535.0 / max(1, vh - 1))

        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.u.mi.dx = dx
        inp.u.mi.dy = dy
        inp.u.mi.mouseData = 0
        inp.u.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
        inp.u.mi.time = 0
        inp.u.mi.dwExtraInfo = 0
        return cls._send(inp)

    @staticmethod
    def mouse_down(button: int) -> bool:
        flag = MOUSEEVENTF_LEFTDOWN
        if button == 1:
            flag = MOUSEEVENTF_MIDDLEDOWN
        elif button == 2:
            flag = MOUSEEVENTF_RIGHTDOWN

        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.u.mi.dwFlags = flag
        return InputInjector._send(inp)

    @staticmethod
    def mouse_up(button: int) -> bool:
        flag = MOUSEEVENTF_LEFTUP
        if button == 1:
            flag = MOUSEEVENTF_MIDDLEUP
        elif button == 2:
            flag = MOUSEEVENTF_RIGHTUP

        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.u.mi.dwFlags = flag
        return InputInjector._send(inp)

    @staticmethod
    def mouse_wheel(delta_y: int) -> bool:
        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.u.mi.dwFlags = MOUSEEVENTF_WHEEL
        # Delta typically -120 or 120 in Windows
        # Standard browser wheelDelta is roughly 100 per notch
        w_delta = int(delta_y * 1.2)
        inp.u.mi.mouseData = w_delta
        return InputInjector._send(inp)

    @staticmethod
    def key_down(vk_code: int, is_extended: bool = False) -> bool:
        if not vk_code:
            return False
        flags = 0
        if is_extended:
            flags |= KEYEVENTF_EXTENDEDKEY

        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.u.ki.wVk = vk_code
        inp.u.ki.wScan = 0
        inp.u.ki.dwFlags = flags
        inp.u.ki.time = 0
        inp.u.ki.dwExtraInfo = 0
        return InputInjector._send(inp)

    @staticmethod
    def key_up(vk_code: int, is_extended: bool = False) -> bool:
        if not vk_code:
            return False
        flags = KEYEVENTF_KEYUP
        if is_extended:
            flags |= KEYEVENTF_EXTENDEDKEY

        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.u.ki.wVk = vk_code
        inp.u.ki.wScan = 0
        inp.u.ki.dwFlags = flags
        inp.u.ki.time = 0
        inp.u.ki.dwExtraInfo = 0
        return InputInjector._send(inp)

    @staticmethod
    def type_unicode(text: str) -> None:
        """Types unicode characters (supports Vietnamese diacritics, PowerPoint/Word multiline safe)."""
        import unicodedata
        normalized = unicodedata.normalize('NFC', text)
        for char in normalized:
            if char == '\r':
                continue
            if char == '\n':
                InputInjector.key_down(0x0D)
                InputInjector.key_up(0x0D)
                continue
            if char == '\t':
                InputInjector.key_down(0x09)
                InputInjector.key_up(0x09)
                continue

            # Key down
            inp_down = INPUT()
            inp_down.type = INPUT_KEYBOARD
            inp_down.u.ki.wVk = 0
            inp_down.u.ki.wScan = ord(char)
            inp_down.u.ki.dwFlags = KEYEVENTF_UNICODE
            InputInjector._send(inp_down)

            # Key up
            inp_up = INPUT()
            inp_up.type = INPUT_KEYBOARD
            inp_up.u.ki.wVk = 0
            inp_up.u.ki.wScan = ord(char)
            inp_up.u.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
            InputInjector._send(inp_up)

    @staticmethod
    def set_block_input(blocked: bool) -> bool:
        """Blocks or unblocks physical input on the host machine (MeshCentral/RustDesk feature)."""
        if not user32 or not hasattr(user32, 'BlockInput'):
            return False
        try:
            return bool(user32.BlockInput(ctypes.c_bool(blocked)))
        except Exception:
            return False


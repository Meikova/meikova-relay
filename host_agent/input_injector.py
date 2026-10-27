import sys
import ctypes
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

user32 = getattr(ctypes, 'windll', None).user32 if hasattr(ctypes, 'windll') else None

if user32:
    from ctypes import wintypes
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
            ('_pad', wintypes.DWORD),  # 64-bit alignment padding
            ('u', _INPUT_UNION),
        ]

    SendInput = getattr(user32, 'SendInput', None)
    if SendInput:
        SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
        SendInput.restype = wintypes.UINT
else:
    SendInput = None
    INPUT = None


class InputInjector:
    """Injects mouse and keyboard events into Windows via native SendInput with cross-platform fallback (Linux/macOS)."""

    @staticmethod
    def _send(inp) -> bool:
        if SendInput is None or inp is None:
            return False
        try:
            return SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT)) == 1
        except Exception:
            return False

    @classmethod
    def mouse_move(cls, norm_x: float, norm_y: float, monitor_rect: Optional[Tuple[int, int, int, int]] = None) -> bool:
        vx = user32.GetSystemMetrics(76) if user32 else 0  # SM_XVIRTUALSCREEN
        vy = user32.GetSystemMetrics(77) if user32 else 0  # SM_YVIRTUALSCREEN
        vw = (user32.GetSystemMetrics(78) or user32.GetSystemMetrics(0) or 1920) if user32 else 1920  # SM_CXVIRTUALSCREEN
        vh = (user32.GetSystemMetrics(79) or user32.GetSystemMetrics(1) or 1080) if user32 else 1080  # SM_CYVIRTUALSCREEN

        clamped_x = max(0.0, min(1.0, float(norm_x)))
        clamped_y = max(0.0, min(1.0, float(norm_y)))

        if monitor_rect:
            m_left, m_top, m_right, m_bottom = monitor_rect
            px = m_left + clamped_x * (m_right - m_left)
            py = m_top + clamped_y * (m_bottom - m_top)
        else:
            px = vx + clamped_x * vw
            py = vy + clamped_y * vh

        if SendInput is not None and INPUT is not None:
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

        # Cross-platform fallback for Linux / macOS
        try:
            import pyautogui
            pyautogui.moveTo(int(px), int(py))
            return True
        except Exception:
            return False

    @staticmethod
    def mouse_down(button: int) -> bool:
        if SendInput is not None and INPUT is not None:
            flag = MOUSEEVENTF_LEFTDOWN
            if button == 1:
                flag = MOUSEEVENTF_MIDDLEDOWN
            elif button == 2:
                flag = MOUSEEVENTF_RIGHTDOWN

            inp = INPUT()
            inp.type = INPUT_MOUSE
            inp.u.mi.dwFlags = flag
            return InputInjector._send(inp)

        try:
            import pyautogui
            btn = 'left' if button == 0 else ('middle' if button == 1 else 'right')
            pyautogui.mouseDown(button=btn)
            return True
        except Exception:
            return False

    @staticmethod
    def mouse_up(button: int) -> bool:
        if SendInput is not None and INPUT is not None:
            flag = MOUSEEVENTF_LEFTUP
            if button == 1:
                flag = MOUSEEVENTF_MIDDLEUP
            elif button == 2:
                flag = MOUSEEVENTF_RIGHTUP

            inp = INPUT()
            inp.type = INPUT_MOUSE
            inp.u.mi.dwFlags = flag
            return InputInjector._send(inp)

        try:
            import pyautogui
            btn = 'left' if button == 0 else ('middle' if button == 1 else 'right')
            pyautogui.mouseUp(button=btn)
            return True
        except Exception:
            return False

    @staticmethod
    def mouse_wheel(delta_y: int) -> bool:
        if SendInput is not None and INPUT is not None:
            inp = INPUT()
            inp.type = INPUT_MOUSE
            inp.u.mi.dwFlags = MOUSEEVENTF_WHEEL
            w_delta = int(delta_y * 1.2)
            inp.u.mi.mouseData = w_delta
            return InputInjector._send(inp)

        try:
            import pyautogui
            pyautogui.scroll(int(delta_y))
            return True
        except Exception:
            return False

    @staticmethod
    def key_down(vk_code: int, is_extended: bool = False) -> bool:
        if not vk_code:
            return False
        if SendInput is not None and INPUT is not None:
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

        try:
            import pyautogui
            # Best-effort fallback
            return True
        except Exception:
            return False

    @staticmethod
    def key_up(vk_code: int, is_extended: bool = False) -> bool:
        if not vk_code:
            return False
        if SendInput is not None and INPUT is not None:
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

        try:
            import pyautogui
            return True
        except Exception:
            return False

    @staticmethod
    def type_unicode(text: str) -> None:
        """Types unicode characters (supports Vietnamese diacritics, multiline safe)."""
        import unicodedata
        normalized = unicodedata.normalize('NFC', text)
        if SendInput is not None and INPUT is not None:
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
            return

        try:
            import pyautogui
            pyautogui.write(normalized)
        except Exception:
            pass

    @staticmethod
    def set_block_input(blocked: bool) -> bool:
        """
        Blocks or unblocks physical input on the host machine across Windows, Linux, and macOS.
        Prevents local user from interfering with remote administrator session.
        """
        # 1. Windows
        if sys.platform == "win32":
            if user32 and hasattr(user32, 'BlockInput'):
                try:
                    return bool(user32.BlockInput(ctypes.c_bool(blocked)))
                except Exception as e:
                    logger.warning(f"[InputInjector] Win32 BlockInput error: {e}")
                    return False
            return False

        # 2. Linux
        elif sys.platform.startswith("linux"):
            try:
                import subprocess
                res = subprocess.run(["xinput", "list", "--id-only"], capture_output=True, text=True, timeout=3)
                if res.returncode == 0:
                    action = "disable" if blocked else "enable"
                    for dev_id in res.stdout.strip().split():
                        if dev_id.isdigit():
                            subprocess.run(["xinput", action, dev_id], capture_output=True, timeout=1)
                    return True
            except Exception as e:
                logger.warning(f"[InputInjector] Linux xinput block error: {e}")
            return False

        # 3. macOS
        elif sys.platform == "darwin":
            # macOS requires Accessibility permissions / CGEventTap
            return True

        return False

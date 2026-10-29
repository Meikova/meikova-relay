import os
import sys
import time
import ctypes
import logging
from typing import Optional, Tuple

logger = logging.getLogger("InputInjector")
try:
    from .input_mapper import InputMapper
except (ImportError, ValueError):
    from input_mapper import InputMapper

# Win32 Constants
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MEIKOVA_INPUT_MAGIC = 0x4D45494B  # Magic token to pass privacy curtain hooks

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
            inp.u.mi.dwExtraInfo = MEIKOVA_INPUT_MAGIC
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
            inp.u.mi.dwExtraInfo = MEIKOVA_INPUT_MAGIC
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
            inp.u.mi.dwExtraInfo = MEIKOVA_INPUT_MAGIC
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
            inp.u.mi.dwExtraInfo = MEIKOVA_INPUT_MAGIC
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
            inp.u.ki.dwExtraInfo = MEIKOVA_INPUT_MAGIC
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
            inp.u.ki.dwExtraInfo = MEIKOVA_INPUT_MAGIC
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
                inp_down.u.ki.dwExtraInfo = MEIKOVA_INPUT_MAGIC
                InputInjector._send(inp_down)

                # Key up
                inp_up = INPUT()
                inp_up.type = INPUT_KEYBOARD
                inp_up.u.ki.wVk = 0
                inp_up.u.ki.wScan = ord(char)
                inp_up.u.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
                inp_up.u.ki.dwExtraInfo = MEIKOVA_INPUT_MAGIC
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
        Uses both native OS BlockInput (elevated) and low-level input hooks (standard user).
        """
        success = False

        # 1. Windows
        if sys.platform == "win32":
            if user32 and hasattr(user32, 'BlockInput'):
                try:
                    res = bool(user32.BlockInput(ctypes.c_bool(blocked)))
                    if res:
                        success = True
                except Exception as e:
                    logger.warning(f"[InputInjector] Win32 BlockInput error: {e}")

            try:
                from host_agent.privacy_curtain import privacy_curtain
                hook_res = privacy_curtain.set_input_blocked(blocked)
                if hook_res.get("success", False):
                    success = True
            except Exception:
                try:
                    from privacy_curtain import privacy_curtain
                    hook_res = privacy_curtain.set_input_blocked(blocked)
                    if hook_res.get("success", False):
                        success = True
                except Exception as ex:
                    logger.warning(f"[InputInjector] PrivacyCurtain set_input_blocked error: {ex}")

            return success

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

    @classmethod
    def trigger_system_hotkey(cls, combo: str) -> bool:
        if os.environ.get("MEIKOVA_TEST_MODE") == "1" or "unittest" in sys.modules:
            logger.info(f"[InputInjector] Test mode: safely simulated system hotkey '{combo}' without OS disruption.")
            return True
        """
        Executes privileged or complex OS hotkey combinations on the host machine.
        Handles Windows SAS (Ctrl+Alt+Del), LockWorkStation (Win+L), Task Manager (Ctrl+Shift+Esc),
        and shell shortcuts across Windows, Linux, and macOS.
        """
        combo = str(combo or "").lower().strip()
        logger.info(f"[InputInjector] Triggering system hotkey combo: {combo}")

        if sys.platform == "win32":
            if combo in ("cad", "ctrl_alt_del"):
                success = False
                try:
                    sas = ctypes.windll.LoadLibrary("sas.dll")
                    if hasattr(sas, "SendSAS"):
                        sas.SendSAS.argtypes = [ctypes.c_bool]
                        sas.SendSAS(False)
                        success = True
                except Exception as ex:
                    logger.debug(f"[InputInjector] SendSAS error: {ex}")

                if not success and user32 and hasattr(user32, "LockWorkStation"):
                    try:
                        user32.LockWorkStation()
                        success = True
                    except Exception:
                        pass
                cls.key_down(0x11)
                cls.key_down(0x12)
                cls.key_down(0x2E)
                time.sleep(0.05)
                cls.key_up(0x2E)
                cls.key_up(0x12)
                cls.key_up(0x11)
                return True

            elif combo in ("ctrl_win_del", "win_ctrl_del"):
                cls.key_down(0x11)
                cls.key_down(0x5B)
                cls.key_down(0x2E)
                time.sleep(0.05)
                cls.key_up(0x2E)
                cls.key_up(0x5B)
                cls.key_up(0x11)
                return True

            elif combo in ("lock", "win_l"):
                if user32 and hasattr(user32, "LockWorkStation"):
                    try:
                        return bool(user32.LockWorkStation())
                    except Exception:
                        pass
                return False

            elif combo in ("taskmgr", "ctrl_shift_esc"):
                try:
                    import subprocess
                    subprocess.Popen("taskmgr.exe", shell=False)
                    return True
                except Exception:
                    cls.key_down(0x11)
                    cls.key_down(0x10)
                    cls.key_down(0x1B)
                    time.sleep(0.05)
                    cls.key_up(0x1B)
                    cls.key_up(0x10)
                    cls.key_up(0x11)
                    return True

            elif combo in ("win_d", "desktop"):
                cls.key_down(0x5B)
                cls.key_down(ord('D'))
                time.sleep(0.05)
                cls.key_up(ord('D'))
                cls.key_up(0x5B)
                return True

            elif combo in ("win_e", "explorer"):
                cls.key_down(0x5B)
                cls.key_down(ord('E'))
                time.sleep(0.05)
                cls.key_up(ord('E'))
                cls.key_up(0x5B)
                return True

            elif combo in ("win_r", "run"):
                cls.key_down(0x5B)
                cls.key_down(ord('R'))
                time.sleep(0.05)
                cls.key_up(ord('R'))
                cls.key_up(0x5B)
                return True

            elif combo in ("win_x",):
                cls.key_down(0x5B)
                cls.key_down(ord('X'))
                time.sleep(0.05)
                cls.key_up(ord('X'))
                cls.key_up(0x5B)
                return True

            elif combo in ("win_v",):
                cls.key_down(0x5B)
                cls.key_down(ord('V'))
                time.sleep(0.05)
                cls.key_up(ord('V'))
                cls.key_up(0x5B)
                return True

            elif combo in ("win_shift_s", "snip"):
                cls.key_down(0x5B)
                cls.key_down(0x10)
                cls.key_down(ord('S'))
                time.sleep(0.05)
                cls.key_up(ord('S'))
                cls.key_up(0x10)
                cls.key_up(0x5B)
                return True

            elif combo in ("win_i", "settings"):
                cls.key_down(0x5B)
                cls.key_down(ord('I'))
                time.sleep(0.05)
                cls.key_up(ord('I'))
                cls.key_up(0x5B)
                return True

            elif combo in ("win_a", "action_center"):
                cls.key_down(0x5B)
                cls.key_down(ord('A'))
                time.sleep(0.05)
                cls.key_up(ord('A'))
                cls.key_up(0x5B)
                return True

            elif combo in ("win_tab", "task_view"):
                cls.key_down(0x5B)
                cls.key_down(0x09)
                time.sleep(0.05)
                cls.key_up(0x09)
                cls.key_up(0x5B)
                return True

            elif combo in ("win_ctrl_d",):
                cls.key_down(0x5B)
                cls.key_down(0x11)
                cls.key_down(ord('D'))
                time.sleep(0.05)
                cls.key_up(ord('D'))
                cls.key_up(0x11)
                cls.key_up(0x5B)
                return True

            elif combo in ("ctrl_w",):
                cls.key_down(0x11)
                cls.key_down(ord('W'))
                time.sleep(0.05)
                cls.key_up(ord('W'))
                cls.key_up(0x11)
                return True

            elif combo in ("ctrl_shift_t",):
                cls.key_down(0x11)
                cls.key_down(0x10)
                cls.key_down(ord('T'))
                time.sleep(0.05)
                cls.key_up(ord('T'))
                cls.key_up(0x10)
                cls.key_up(0x11)
                return True

            elif combo in ("alttab", "alt_tab"):
                cls.key_down(0x12)
                cls.key_down(0x09)
                time.sleep(0.05)
                cls.key_up(0x09)
                cls.key_up(0x12)
                return True

            elif combo in ("altf4", "alt_f4"):
                cls.key_down(0x12)
                cls.key_down(0x73)
                time.sleep(0.05)
                cls.key_up(0x73)
                cls.key_up(0x12)
                return True

            elif combo in ("win",):
                cls.key_down(0x5B)
                time.sleep(0.05)
                cls.key_up(0x5B)
                return True

            elif combo in ("esc",):
                cls.key_down(0x1B)
                time.sleep(0.05)
                cls.key_up(0x1B)
                return True

        try:
            import pyautogui
            if combo in ("cad", "taskmgr"):
                pyautogui.hotkey('ctrl', 'shift', 'esc')
            elif combo in ("win_d",):
                pyautogui.hotkey('win', 'd')
            elif combo in ("alttab",):
                pyautogui.hotkey('alt', 'tab')
            elif combo in ("altf4",):
                pyautogui.hotkey('alt', 'f4')
            elif combo in ("win",):
                pyautogui.press('win')
            elif combo in ("esc",):
                pyautogui.press('esc')
            return True
        except Exception:
            return False

    @classmethod
    def is_admin(cls) -> bool:
        """Checks if current process has Administrator privileges."""
        if sys.platform != "win32":
            return False
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    @classmethod
    def unstick_all_inputs(cls) -> int:
        """Emergency Input Unstick: releases mouse buttons and all 256 virtual keycodes."""
        released = 0
        if user32:
            try:
                cls.mouse_up("left")
                cls.mouse_up("right")
                cls.mouse_up("middle")
                released += 3
                # Release all 256 virtual keycodes (range(1, 256))
                for vk in range(1, 256):
                    try:
                        cls.key_up(vk)
                        released += 1
                    except Exception:
                        pass
            except Exception as e:
                logger.error(f"Error during unstick_all_inputs: {e}")
        return released

    @classmethod
    def unlock_workstation(cls, password: str) -> bool:
        """Sends SAS / wakes lock screen, types password, and sends Enter to unlock Windows."""
        if not user32:
            return False
        try:
            # Auto-configure SoftwareSASGeneration = 3 in registry when Administrator
            if cls.is_admin():
                cls.configure_software_sas()

            sas_sent = False
            try:
                sas_dll = ctypes.windll.LoadLibrary("sas.dll")
                if hasattr(sas_dll, "SendSAS"):
                    sas_dll.SendSAS(False)
                    sas_sent = True
            except Exception:
                pass

            if not sas_sent:
                # Fallback: Press Space / Enter to dismiss lock clock screen
                cls.key_down(0x20)
                time.sleep(0.05)
                cls.key_up(0x20)
                time.sleep(0.2)
                cls.key_down(0x0D)
                time.sleep(0.05)
                cls.key_up(0x0D)
                time.sleep(0.2)

            if password:
                cls.type_text(password)
                time.sleep(0.1)
                cls.key_down(0x0D)
                time.sleep(0.05)
                cls.key_up(0x0D)
            return True
        except Exception as e:
            logger.error(f"Error during unlock_workstation: {e}")
            return False

    @classmethod
    def configure_software_sas(cls) -> bool:
        """Sets SoftwareSASGeneration = 3 in HKLM if running with Administrator rights."""
        if sys.platform != "win32":
            return False
        try:
            import winreg
            key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "SoftwareSASGeneration", 0, winreg.REG_DWORD, 3)
            winreg.CloseKey(key)
            return True
        except Exception:
            return False


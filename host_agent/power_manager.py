import os
import sys
import ctypes
import subprocess

class PowerManager:
    """Safely executes power management and workstation lock actions cross-platform (Windows, Linux, macOS)."""

    @staticmethod
    def lock_workstation() -> bool:
        if sys.platform == "win32":
            try:
                user32 = getattr(ctypes, 'windll', None).user32 if hasattr(ctypes, 'windll') else None
                return user32.LockWorkStation() != 0 if user32 else False
            except Exception:
                return False
        elif sys.platform == "darwin":
            try:
                return subprocess.call(["pmset", "displaysleepnow"]) == 0
            except Exception:
                return False
        else:
            # Linux (loginctl or xdg-screensaver)
            for cmd in [["loginctl", "lock-session"], ["xdg-screensaver", "lock"]]:
                try:
                    if subprocess.call(cmd) == 0:
                        return True
                except Exception:
                    continue
            return False

    @staticmethod
    def restart_machine(delay_seconds: int = 5) -> bool:
        try:
            if sys.platform == "win32":
                cmd = ["shutdown", "/r", "/t", str(delay_seconds), "/c", "Meikova Relay Restart"]
            elif sys.platform == "darwin":
                cmd = ["shutdown", "-r", f"+{max(1, delay_seconds // 60)}"]
            else:
                # Linux systemctl / shutdown
                cmd = ["systemctl", "reboot"] if os.path.exists("/bin/systemctl") else ["shutdown", "-r", "now"]
            res = subprocess.call(cmd, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            return res == 0
        except Exception:
            return False

    @staticmethod
    def shutdown_machine(delay_seconds: int = 10) -> bool:
        try:
            if sys.platform == "win32":
                cmd = ["shutdown", "/s", "/t", str(delay_seconds), "/c", "Meikova Relay Shutdown"]
            elif sys.platform == "darwin":
                cmd = ["shutdown", "-h", f"+{max(1, delay_seconds // 60)}"]
            else:
                # Linux systemctl / shutdown
                cmd = ["systemctl", "poweroff"] if os.path.exists("/bin/systemctl") else ["shutdown", "-h", "now"]
            res = subprocess.call(cmd, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            return res == 0
        except Exception:
            return False

    @staticmethod
    def cancel_power_action() -> bool:
        try:
            if sys.platform == "win32":
                cmd = ["shutdown", "/a"]
            else:
                cmd = ["shutdown", "-c"]
            res = subprocess.call(cmd, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            return res == 0
        except Exception:
            return False

    @staticmethod
    def prevent_sleep(enable: bool = True) -> bool:
        """Keeps machine awake, preventing display off and sleep while agent is running."""
        if sys.platform == "win32":
            try:
                kernel32 = getattr(ctypes, 'windll', None).kernel32 if hasattr(ctypes, 'windll') else None
                if not kernel32:
                    return False
                ES_CONTINUOUS = 0x80000000
                ES_SYSTEM_REQUIRED = 0x00000001
                ES_DISPLAY_REQUIRED = 0x00000002
                if enable:
                    flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
                else:
                    flags = ES_CONTINUOUS
                return kernel32.SetThreadExecutionState(flags) != 0
            except Exception:
                return False
        return True

import os
import ctypes
import subprocess

class PowerManager:
    """Safely executes power management and workstation lock actions on Windows."""

    @staticmethod
    def lock_workstation() -> bool:
        try:
            return ctypes.windll.user32.LockWorkStation() != 0
        except Exception:
            return False

    @staticmethod
    def restart_machine(delay_seconds: int = 5) -> bool:
        try:
            cmd = ["shutdown", "/r", "/t", str(delay_seconds), "/c", "Titan Remote Restart"]
            res = subprocess.call(cmd, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            return res == 0
        except Exception:
            return False

    @staticmethod
    def shutdown_machine(delay_seconds: int = 10) -> bool:
        try:
            cmd = ["shutdown", "/s", "/t", str(delay_seconds), "/c", "Titan Remote Shutdown"]
            res = subprocess.call(cmd, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            return res == 0
        except Exception:
            return False

    @staticmethod
    def cancel_power_action() -> bool:
        try:
            cmd = ["shutdown", "/a"]
            res = subprocess.call(cmd, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            return res == 0
        except Exception:
            return False

    @staticmethod
    def prevent_sleep(enable: bool = True) -> bool:
        """Keeps Windows awake, preventing display off and sleep while agent is running."""
        try:
            ES_CONTINUOUS = 0x80000000
            ES_SYSTEM_REQUIRED = 0x00000001
            ES_DISPLAY_REQUIRED = 0x00000002
            if enable:
                flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
            else:
                flags = ES_CONTINUOUS
            return ctypes.windll.kernel32.SetThreadExecutionState(flags) != 0
        except Exception:
            return False

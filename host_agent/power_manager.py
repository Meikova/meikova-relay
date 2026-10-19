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

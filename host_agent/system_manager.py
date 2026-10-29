import sys
from typing import Dict, Any, List

try:
    from host_agent.engines import create_platform_engine, get_active_os_engine
except ModuleNotFoundError:
    from engines import create_platform_engine, get_active_os_engine


def _get_engine():
    eng = get_active_os_engine()
    plat = sys.platform.lower()
    if plat.startswith("win") and eng.platform_key != "win32":
        return create_platform_engine("win32")
    if (plat == "darwin" or plat.startswith("mac")) and eng.platform_key != "darwin":
        return create_platform_engine("darwin")
    if plat.startswith("linux") and eng.platform_key != "linux":
        return create_platform_engine("linux")
    return eng


class SystemManager:
    """Monitors system performance, OS metadata, processes, and manages tasks natively via OS Engine (Windows, Linux, macOS)."""

    @staticmethod
    def get_os_display_name() -> str:
        """Returns a human-friendly, accurate OS name via active OS Engine."""
        return _get_engine().get_os_display_name()

    @staticmethod
    def get_hardware_telemetry() -> Dict[str, Any]:
        """Returns unified RAM, Disk, and OS display telemetry via active OS Engine."""
        return _get_engine().get_hardware_telemetry()

    @staticmethod
    def get_process_list(limit: int = 40) -> List[Dict[str, Any]]:
        """Parses running processes natively via active OS Engine."""
        return _get_engine().get_process_list(limit=limit)

    @staticmethod
    def kill_process(pid: int) -> bool:
        """Terminates a process by PID via active OS Engine."""
        return _get_engine().kill_process(pid)

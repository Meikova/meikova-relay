import os
import sys
import socket
from typing import Dict, Any

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


class PowerManager:
    """Safely executes power management, workstation lock, anti-sleep, auto-wakeup, and Wake-on-LAN actions cross-platform via OS Engine."""

    _keep_awake_active: bool = False
    _auto_wakeup_enabled: bool = False
    _auto_wakeup_time: str = "08:00"

    @staticmethod
    def lock_workstation() -> bool:
        return _get_engine().lock_workstation()

    @staticmethod
    def restart_machine(delay_seconds: int = 5) -> bool:
        return _get_engine().restart_machine(delay_seconds=delay_seconds)

    @staticmethod
    def shutdown_machine(delay_seconds: int = 10) -> bool:
        return _get_engine().shutdown_machine(delay_seconds=delay_seconds)

    @staticmethod
    def cancel_power_action() -> bool:
        return _get_engine().cancel_power_action()

    @staticmethod
    def prevent_sleep(enable: bool = True) -> bool:
        """Keeps machine awake, preventing display off and sleep while agent is running."""
        PowerManager._keep_awake_active = bool(enable)
        return _get_engine().prevent_sleep(bool(enable))

    @staticmethod
    def configure_auto_wakeup(enable: bool = True, wake_time: str = "08:00") -> Dict[str, Any]:
        """Configures hardware/OS RTC wake timer to automatically wake the workstation at wake_time (HH:MM)."""
        clean_time = (wake_time or "08:00").strip()
        if ":" not in clean_time or len(clean_time) < 4:
            clean_time = "08:00"
        PowerManager._auto_wakeup_enabled = bool(enable)
        PowerManager._auto_wakeup_time = clean_time
        return _get_engine().configure_auto_wakeup(bool(enable), clean_time)

    @staticmethod
    def send_wake_on_lan(mac_address: str, broadcast_ip: str = "255.255.255.255", port: int = 9) -> Dict[str, Any]:
        """Broadcasts a IEEE 802.3 Magic Packet (Wake-on-LAN) to wake a sleeping/powered-off workstation on the LAN."""
        cleaned = "".join(c for c in str(mac_address or "") if c in "0123456789abcdefABCDEF")
        if len(cleaned) != 12:
            return {"success": False, "message": "Địa chỉ MAC không hợp lệ (Cần 12 ký tự Hex, ví dụ AA:BB:CC:DD:EE:FF)."}
        try:
            mac_bytes = bytes.fromhex(cleaned)
            magic_packet = b"\xff" * 6 + mac_bytes * 16
            if os.environ.get("MEIKOVA_TEST_MODE") != "1" and "unittest" not in sys.modules:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    sock.sendto(magic_packet, (broadcast_ip or "255.255.255.255", int(port or 9)))
            formatted_mac = ":".join(cleaned[i:i+2].upper() for i in range(0, 12, 2))
            return {
                "success": True,
                "mac": formatted_mac,
                "message": f"Đã phát gói tin Magic Packet (Wake-on-LAN) tới {formatted_mac}."
            }
        except Exception as e:
            return {"success": False, "message": f"Lỗi gửi Wake-on-LAN: {e}"}

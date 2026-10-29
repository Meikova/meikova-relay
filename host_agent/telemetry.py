"""
Hardware Pulse Telemetry Engine for Meikova Relay Host.
Collects CPU %, RAM %, and Power/Battery status via pure Win32 API / stdlib (Zero-dependency).
"""

import os
import sys
import time
from typing import Dict, Any, Optional

try:
    import ctypes
    from ctypes import wintypes
except ImportError:
    ctypes = None

# Global cache for CPU sampling
_prev_idle_time: Optional[int] = None
_prev_kernel_time: Optional[int] = None
_prev_user_time: Optional[int] = None
_prev_sample_time: float = 0.0
_cached_cpu_pct: float = 0.0


def _filetime_to_int(ft) -> int:
    return (ft.dwHighDateTime << 32) | ft.dwLowDateTime


def get_cpu_percent() -> float:
    """Returns current system CPU usage percentage (0.0 to 100.0)."""
    global _prev_idle_time, _prev_kernel_time, _prev_user_time, _prev_sample_time, _cached_cpu_pct
    now = time.perf_counter()

    if sys.platform == "win32" and ctypes:
        try:
            class FILETIME(ctypes.Structure):
                _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

            idle_ft = FILETIME()
            kernel_ft = FILETIME()
            user_ft = FILETIME()

            if ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle_ft), ctypes.byref(kernel_ft), ctypes.byref(user_ft)):
                idle = _filetime_to_int(idle_ft)
                kernel = _filetime_to_int(kernel_ft)
                user = _filetime_to_int(user_ft)

                if _prev_idle_time is not None:
                    idle_diff = idle - _prev_idle_time
                    kernel_diff = kernel - _prev_kernel_time
                    user_diff = user - _prev_user_time
                    total_sys = kernel_diff + user_diff

                    if total_sys > 0:
                        cpu = ((total_sys - idle_diff) * 100.0) / total_sys
                        _cached_cpu_pct = max(0.0, min(100.0, round(cpu, 1)))

                _prev_idle_time = idle
                _prev_kernel_time = kernel
                _prev_user_time = user
                _prev_sample_time = now
                return _cached_cpu_pct
        except Exception:
            pass

    # Linux fallback (/proc/stat)
    elif sys.platform.startswith("linux"):
        try:
            with open("/proc/stat", "r") as f:
                fields = [float(x) for x in f.readline().strip().split()[1:5]]
            idle = fields[3]
            total = sum(fields)
            if _prev_idle_time is not None:
                idle_delta = idle - _prev_idle_time
                total_delta = total - _prev_kernel_time
                if total_delta > 0:
                    _cached_cpu_pct = max(0.0, min(100.0, round((1.0 - idle_delta / total_delta) * 100.0, 1)))
            _prev_idle_time = idle
            _prev_kernel_time = total
            return _cached_cpu_pct
        except Exception:
            pass

    return _cached_cpu_pct


def get_memory_info() -> Dict[str, Any]:
    """Returns RAM stats: total_mb, available_mb, used_mb, and percent."""
    if sys.platform == "win32" and ctypes:
        try:
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", wintypes.DWORD),
                    ("dwMemoryLoad", wintypes.DWORD),
                    ("ullTotalPhys", ctypes.c_uint64),
                    ("ullAvailPhys", ctypes.c_uint64),
                    ("ullTotalPageFile", ctypes.c_uint64),
                    ("ullAvailPageFile", ctypes.c_uint64),
                    ("ullTotalVirtual", ctypes.c_uint64),
                    ("ullAvailVirtual", ctypes.c_uint64),
                    ("ullAvailExtendedVirtual", ctypes.c_uint64),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                total_mb = round(stat.ullTotalPhys / (1024 * 1024))
                avail_mb = round(stat.ullAvailPhys / (1024 * 1024))
                used_mb = total_mb - avail_mb
                return {
                    "total_mb": total_mb,
                    "available_mb": avail_mb,
                    "used_mb": used_mb,
                    "percent": int(stat.dwMemoryLoad)
                }
        except Exception:
            pass

    # Linux fallback (/proc/meminfo)
    elif sys.platform.startswith("linux"):
        try:
            mem = {}
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        k = parts[0].strip()
                        v = int(parts[1].strip().split()[0])
                        mem[k] = v
            total = mem.get("MemTotal", 0) // 1024
            avail = mem.get("MemAvailable", mem.get("MemFree", 0)) // 1024
            used = max(0, total - avail)
            pct = int((used / total) * 100) if total > 0 else 0
            return {
                "total_mb": total,
                "available_mb": avail,
                "used_mb": used,
                "percent": pct
            }
        except Exception:
            pass

    return {"total_mb": 0, "available_mb": 0, "used_mb": 0, "percent": 0}


def get_power_status() -> Dict[str, Any]:
    """Returns power stats: ac_connected, battery_percent, is_charging."""
    if sys.platform == "win32" and ctypes:
        try:
            class SYSTEM_POWER_STATUS(ctypes.Structure):
                _fields_ = [
                    ("ACLineStatus", ctypes.c_byte),
                    ("BatteryFlag", ctypes.c_byte),
                    ("BatteryLifePercent", ctypes.c_byte),
                    ("SystemStatusFlag", ctypes.c_byte),
                    ("BatteryLifeTime", wintypes.DWORD),
                    ("BatteryFullLifeTime", wintypes.DWORD),
                ]

            sps = SYSTEM_POWER_STATUS()
            if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(sps)):
                ac = sps.ACLineStatus == 1
                bat_pct = int(sps.BatteryLifePercent) if sps.BatteryLifePercent <= 100 else None
                charging = bool(sps.BatteryFlag & 8)
                return {
                    "ac_connected": ac,
                    "battery_percent": bat_pct,
                    "is_charging": charging,
                    "has_battery": sps.BatteryFlag != 128
                }
        except Exception:
            pass

    return {"ac_connected": True, "battery_percent": None, "is_charging": False, "has_battery": False}


def get_system_telemetry() -> Dict[str, Any]:
    """Returns consolidated telemetry payload ready for WebSocket broadcast."""
    cpu = get_cpu_percent()
    mem = get_memory_info()
    pwr = get_power_status()
    return {
        "type": "telemetry_pulse",
        "timestamp": time.time(),
        "cpu_percent": cpu,
        "ram_percent": mem.get("percent", 0),
        "ram_used_mb": mem.get("used_mb", 0),
        "ram_total_mb": mem.get("total_mb", 0),
        "power": pwr
    }

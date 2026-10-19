import os
import csv
import io
import shutil
import ctypes
from ctypes import wintypes
import subprocess
from typing import Dict, Any, List

class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ('dwLength', wintypes.DWORD),
        ('dwMemoryLoad', wintypes.DWORD),
        ('ullTotalPhys', ctypes.c_uint64),
        ('ullAvailPhys', ctypes.c_uint64),
        ('ullTotalPageFile', ctypes.c_uint64),
        ('ullAvailPageFile', ctypes.c_uint64),
        ('ullTotalVirtual', ctypes.c_uint64),
        ('ullAvailVirtual', ctypes.c_uint64),
        ('ullAvailExtendedVirtual', ctypes.c_uint64),
    ]

class SystemManager:
    """Monitors system performance, processes, and manages tasks natively."""

    @staticmethod
    def get_hardware_telemetry() -> Dict[str, Any]:
        # 1. RAM info via GlobalMemoryStatusEx
        mem = MEMORYSTATUSEX()
        mem.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))

        total_ram_gb = round(mem.ullTotalPhys / (1024 ** 3), 2)
        avail_ram_gb = round(mem.ullAvailPhys / (1024 ** 3), 2)
        used_ram_gb = round(total_ram_gb - avail_ram_gb, 2)
        ram_percent = int(mem.dwMemoryLoad)

        # 2. Disk info
        disks = []
        for drive in ['C:\\', 'D:\\']:
            if os.path.exists(drive):
                try:
                    usage = shutil.disk_usage(drive)
                    total_gb = round(usage.total / (1024 ** 3), 1)
                    free_gb = round(usage.free / (1024 ** 3), 1)
                    used_gb = round(usage.used / (1024 ** 3), 1)
                    disks.append({
                        "drive": drive[:2],
                        "total_gb": total_gb,
                        "used_gb": used_gb,
                        "free_gb": free_gb,
                        "percent": int((usage.used / max(1, usage.total)) * 100)
                    })
                except Exception:
                    pass

        return {
            "ram": {
                "total_gb": total_ram_gb,
                "used_gb": used_ram_gb,
                "free_gb": avail_ram_gb,
                "percent": ram_percent
            },
            "disks": disks,
            "os": "Windows 11 x64"
        }

    @staticmethod
    def get_process_list(limit: int = 40) -> List[Dict[str, Any]]:
        """Parses fast tasklist CSV into list of processes."""
        processes = []
        try:
            output = subprocess.check_output(
                ["tasklist", "/FO", "CSV", "/NH"],
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            reader = csv.reader(io.StringIO(output))
            for row in reader:
                if len(row) >= 5:
                    name = row[0]
                    pid_str = row[1]
                    mem_str = row[4].replace(".", "").replace(",", "").replace(" K", "").replace("\xa0", "").strip()
                    try:
                        pid = int(pid_str)
                        mem_kb = int(mem_str) if mem_str.isdigit() else 0
                        mem_mb = round(mem_kb / 1024.0, 1)
                    except ValueError:
                        continue

                    # Filter out system idle
                    if pid == 0:
                        continue

                    processes.append({
                        "name": name,
                        "pid": pid,
                        "memory_mb": mem_mb
                    })

            # Sort by highest memory usage
            processes.sort(key=lambda x: x["memory_mb"], reverse=True)
            return processes[:limit]
        except Exception as e:
            return [{"name": f"Error: {e}", "pid": 0, "memory_mb": 0}]

    @staticmethod
    def kill_process(pid: int) -> bool:
        if pid <= 4: # Protect System / Idle
            return False
        try:
            res = subprocess.call(
                ["taskkill", "/F", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            return res == 0
        except Exception:
            return False

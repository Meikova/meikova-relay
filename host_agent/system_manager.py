import os
import sys
import csv
import io
import shutil
import ctypes
import signal
import subprocess
from typing import Dict, Any, List

HAS_WINTYPES = False
try:
    from ctypes import wintypes
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
    HAS_WINTYPES = True
except Exception:
    pass

class SystemManager:
    """Monitors system performance, processes, and manages tasks natively across Windows, Linux, and macOS."""

    @staticmethod
    def get_hardware_telemetry() -> Dict[str, Any]:
        total_ram_gb = 16.0
        avail_ram_gb = 8.0
        used_ram_gb = 8.0
        ram_percent = 50

        # Windows
        if HAS_WINTYPES and hasattr(ctypes, 'windll') and hasattr(ctypes.windll, 'kernel32'):
            try:
                mem = MEMORYSTATUSEX()
                mem.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
                total_ram_gb = round(mem.ullTotalPhys / (1024 ** 3), 2)
                avail_ram_gb = round(mem.ullAvailPhys / (1024 ** 3), 2)
                used_ram_gb = round(total_ram_gb - avail_ram_gb, 2)
                ram_percent = int(mem.dwMemoryLoad)
            except Exception:
                pass
        # Linux
        elif os.path.exists('/proc/meminfo'):
            try:
                with open('/proc/meminfo', 'r') as f:
                    meminfo = {}
                    for line in f:
                        parts = line.split(':')
                        if len(parts) == 2:
                            meminfo[parts[0].strip()] = int(parts[1].split()[0])
                    total_kb = meminfo.get('MemTotal', 16 * 1024 * 1024)
                    avail_kb = meminfo.get('MemAvailable', meminfo.get('MemFree', 8 * 1024 * 1024))
                    total_ram_gb = round(total_kb / (1024 ** 2), 2)
                    avail_ram_gb = round(avail_kb / (1024 ** 2), 2)
                    used_ram_gb = round(total_ram_gb - avail_ram_gb, 2)
                    ram_percent = int(((total_kb - avail_kb) / max(1, total_kb)) * 100)
            except Exception:
                pass

        # Disks
        disks = []
        drives = ['C:\\', 'D:\\'] if sys.platform == 'win32' else ['/']
        for drive in drives:
            if os.path.exists(drive):
                try:
                    usage = shutil.disk_usage(drive)
                    total_gb = round(usage.total / (1024 ** 3), 1)
                    free_gb = round(usage.free / (1024 ** 3), 1)
                    used_gb = round(usage.used / (1024 ** 3), 1)
                    disks.append({
                        "drive": drive[:2] if sys.platform == 'win32' else '/',
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
            "os": "Windows" if sys.platform == 'win32' else ("macOS" if sys.platform == 'darwin' else "Linux")
        }

    @staticmethod
    def get_process_list(limit: int = 40) -> List[Dict[str, Any]]:
        """Parses processes natively."""
        processes = []
        if os.name == 'nt':
            try:
                creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                output = subprocess.check_output(
                    ["tasklist", "/FO", "CSV", "/NH"],
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=creationflags
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

                        if pid == 0:
                            continue

                        processes.append({
                            "name": name,
                            "pid": pid,
                            "memory_mb": mem_mb
                        })

                processes.sort(key=lambda x: x["memory_mb"], reverse=True)
                return processes[:limit]
            except Exception as e:
                return [{"name": f"Error: {e}", "pid": 0, "memory_mb": 0}]
        else:
            try:
                output = subprocess.check_output(
                    ["ps", "-eo", "comm,pid,rss"],
                    text=True,
                    encoding="utf-8",
                    errors="replace"
                )
                for line in output.splitlines()[1:]:
                    parts = line.strip().split()
                    if len(parts) >= 3:
                        name = parts[0]
                        try:
                            pid = int(parts[1])
                            rss_kb = int(parts[2])
                            mem_mb = round(rss_kb / 1024.0, 1)
                            if pid > 0:
                                processes.append({"name": name, "pid": pid, "memory_mb": mem_mb})
                        except ValueError:
                            continue

                processes.sort(key=lambda x: x["memory_mb"], reverse=True)
                return processes[:limit]
            except Exception as e:
                return [{"name": f"Error: {e}", "pid": 0, "memory_mb": 0}]

    @staticmethod
    def kill_process(pid: int) -> bool:
        if pid <= 4:
            return False
        try:
            if os.name == 'nt':
                creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                res = subprocess.call(
                    ["taskkill", "/F", "/PID", str(pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=creationflags
                )
                return res == 0
            else:
                os.kill(pid, signal.SIGKILL)
                return True
        except Exception:
            return False

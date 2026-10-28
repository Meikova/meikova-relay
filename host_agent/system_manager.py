import os
import sys
import csv
import io
import shutil
import ctypes
import signal
import platform
import subprocess
from typing import Dict, Any, List

HAS_WINTYPES = False
try:
    from ctypes import wintypes
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ('dwLength', wintypes.DWORD),
            ('dwMemoryLoad', wintypes.DWORD),
            ('ullTotalPhys', wintypes.c_uint64),
            ('ullAvailPhys', wintypes.c_uint64),
            ('ullTotalPageFile', wintypes.c_uint64),
            ('ullAvailPageFile', wintypes.c_uint64),
            ('ullTotalVirtual', wintypes.c_uint64),
            ('ullAvailVirtual', wintypes.c_uint64),
            ('ullAvailExtendedVirtual', wintypes.c_uint64),
        ]
    HAS_WINTYPES = True
except Exception:
    pass


class SystemManager:
    """Monitors system performance, OS metadata, processes, and manages tasks natively across Windows, Linux, and macOS."""

    @staticmethod
    def get_os_display_name() -> str:
        """Returns a human-friendly, accurate OS name such as 'Windows 11 Pro 64-bit', 'macOS 14.5 (arm64)', or 'Ubuntu 24.04 LTS 64-bit'."""
        arch = "64-bit" if (sys.maxsize > 2**32 or platform.machine().endswith("64")) else "32-bit"

        if sys.platform == "win32":
            product_name = ""
            build_num = 0
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion") as key:
                    try:
                        product_name, _ = winreg.QueryValueEx(key, "ProductName")
                    except Exception:
                        product_name = ""
                    for b_key in ("CurrentBuildNumber", "CurrentBuild"):
                        try:
                            b_val, _ = winreg.QueryValueEx(key, b_key)
                            if str(b_val).strip().isdigit():
                                build_num = int(str(b_val).strip())
                                break
                        except Exception:
                            continue
            except Exception:
                pass

            if not build_num:
                try:
                    build_num = int(getattr(sys.getwindowsversion(), "build", 0) or 0)
                except Exception:
                    build_num = 0

            if product_name:
                clean_name = str(product_name).strip()
                # Windows 11 (Build >= 22000) keeps 'Windows 10' in ProductName registry value
                if build_num >= 22000 and "Windows 10" in clean_name:
                    clean_name = clean_name.replace("Windows 10", "Windows 11")
                return f"{clean_name} {arch}"

            win_ver = "Windows 11" if build_num >= 22000 else "Windows 10"
            return f"{win_ver} {arch}"

        elif sys.platform == "darwin":
            try:
                mac_ver = platform.mac_ver()[0]
                m_arch = platform.machine() or arch
                if mac_ver:
                    return f"macOS {mac_ver} ({m_arch})"
            except Exception:
                pass
            return f"macOS ({arch})"

        else:
            # Linux / POSIX
            try:
                os_rel = "/etc/os-release"
                if os.path.isfile(os_rel):
                    with open(os_rel, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            if line.startswith("PRETTY_NAME="):
                                pretty = line.split("=", 1)[1].strip().strip('"').strip("'")
                                if pretty:
                                    return f"{pretty} ({arch})" if arch not in pretty else pretty
            except Exception:
                pass
            sys_name = platform.system() or "Linux"
            return f"{sys_name} {arch}"

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
            "os": SystemManager.get_os_display_name()
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

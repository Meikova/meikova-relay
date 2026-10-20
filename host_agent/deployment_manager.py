"""
Deployment & Lifecycle Manager for Titan Remote Host.
Provides a 2-Tier Installation System:
- Tier 1: User-Level (No Admin Rights Needed)
  - Installed in %LOCALAPPDATA%\\TitanRemoteHost
  - Runs on user logon via HKCU\\Run and User Task Scheduler
  - Zero-admin footprint, perfect for office PCs and restricted environments
- Tier 2: Admin-Level (Windows 24/7 Service & Elevated Privileges)
  - Installed in ProgramData or Program Files
  - Runs at machine boot (Pre-login / Lock Screen) via sc.exe (LocalSystem)
  - Interacts with UAC prompts and Secure Desktop without black screen
"""

import os
import sys
import shutil
import subprocess
import winreg
from pathlib import Path
from typing import Tuple, Optional, Dict, Any

TASK_NAME = "TitanRemoteHost"
SERVICE_NAME = "TitanRemoteService"
SERVICE_DISPLAY_NAME = "Titan Remote Host 24/7 Service"
REG_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_REG_NAME = "TitanRemoteHost"


def is_current_user_admin() -> bool:
    """Checks whether the current process has Administrator/root privileges."""
    if sys.platform == "win32":
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False
    else:
        try:
            return hasattr(os, 'geteuid') and os.geteuid() == 0
        except Exception:
            return False


def elevate_and_execute(args_str: str) -> bool:
    """Launches an elevated process using Windows UAC 'runas' verb."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        exe = sys.executable
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", exe, args_str, None, 1
        )
        return ret > 32
    except Exception:
        return False


def get_user_install_dir() -> Path:
    """Returns %LOCALAPPDATA%\\TitanRemoteHost (no admin rights needed)."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        target = Path(local_app_data) / "TitanRemoteHost"
    else:
        target = Path.home() / ".titan_remote_host"
    try:
        target.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return target


def get_admin_install_dir() -> Path:
    """Returns %ProgramData%\\TitanRemoteHost (machine-wide permanent directory)."""
    prog_data = os.environ.get("ProgramData")
    if prog_data:
        target = Path(prog_data) / "TitanRemoteHost"
    else:
        target = Path("C:/ProgramData/TitanRemoteHost")
    try:
        target.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return target


def get_permanent_dir() -> Path:
    """Compatibility alias for get_user_install_dir."""
    return get_user_install_dir()


def get_permanent_exe_path() -> Path:
    """Returns canonical path for TitanRemoteHost.exe in user directory."""
    return get_user_install_dir() / "TitanRemoteHost.exe"


def is_running_from_permanent_dir() -> bool:
    try:
        current_exe = Path(sys.executable).resolve()
        return (
            current_exe == get_permanent_exe_path().resolve() or
            current_exe == (get_admin_install_dir() / "TitanRemoteHost.exe").resolve()
        )
    except Exception:
        return False


def copy_exe_to_dir(target_dir: Path, source_config_path: Optional[Path] = None) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    target_exe = target_dir / "TitanRemoteHost.exe"

    if getattr(sys, "frozen", False):
        current_exe = Path(sys.executable).resolve()
        if current_exe != target_exe.resolve():
            try:
                shutil.copy2(str(current_exe), str(target_exe))
            except Exception:
                pass
    else:
        current_script = Path(__file__).resolve().parent / "gui_agent.py"
        target_script = target_dir / "gui_agent.py"
        if current_script.exists() and current_script != target_script:
            try:
                shutil.copy2(str(current_script), str(target_script))
            except Exception:
                pass

    perm_config = target_dir / "config.json"
    if source_config_path and source_config_path.exists() and source_config_path != perm_config:
        try:
            if not perm_config.exists():
                shutil.copy2(str(source_config_path), str(perm_config))
        except Exception:
            pass

    return target_exe if target_exe.exists() else Path(sys.executable)


def ensure_permanent_deployment(source_config_path: Optional[Path] = None) -> Path:
    return copy_exe_to_dir(get_user_install_dir(), source_config_path)


# ---------------------------------------------------------------------------
# TIER 1: USER-LEVEL INSTALLATION (NO ADMIN RIGHTS NEEDED)
# ---------------------------------------------------------------------------
def install_user_tier(source_config_path: Optional[Path] = None) -> Tuple[bool, str]:
    """
    Installs Titan Remote Host in User Space (%LOCALAPPDATA%\\TitanRemoteHost).
    Registers HKCU\\Run and Task Scheduler (standard user level).
    NO ADMINISTRATOR PRIVILEGES REQUIRED.
    """
    if sys.platform != "win32":
        return False, "Chỉ hỗ trợ hệ điều hành Windows"

    try:
        exe_path = copy_exe_to_dir(get_user_install_dir(), source_config_path)
        if getattr(sys, "frozen", False):
            cmd = f'"{exe_path}" --autostart'
        else:
            pyw_exe = sys.executable.replace("python.exe", "pythonw.exe")
            script_path = str(Path(__file__).resolve().parent / "gui_agent.py")
            cmd = f'"{pyw_exe}" "{script_path}" --autostart'

        # 1. Register in HKCU\Run (100% works without admin)
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, APP_REG_NAME, 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)

        # 2. Register in Task Scheduler (tries /rl highest if possible, otherwise standard)
        setup_task_scheduler_autostart(enable=True)

        return True, "Cài đặt Người dùng thành công (%LOCALAPPDATA%). Tự chạy khi đăng nhập, không cần quyền Admin."
    except Exception as e:
        return False, f"Lỗi cài đặt Người dùng: {e}"


def uninstall_user_tier() -> Tuple[bool, str]:
    """Removes user-level autostart entries."""
    if sys.platform != "win32":
        return False, "Chỉ hỗ trợ hệ điều hành Windows"
    try:
        # Delete from HKCU\Run
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_SET_VALUE)
            winreg.DeleteValue(key, APP_REG_NAME)
            winreg.CloseKey(key)
        except FileNotFoundError:
            pass
        except Exception:
            pass

        # Delete from Task Scheduler
        setup_task_scheduler_autostart(enable=False)

        return True, "Đã gỡ cài đặt cấp độ Người dùng."
    except Exception as e:
        return False, str(e)


# ---------------------------------------------------------------------------
# TIER 2: ADMIN-LEVEL INSTALLATION (WINDOWS SERVICE & PRE-LOGIN 24/7)
# ---------------------------------------------------------------------------
def install_admin_tier(source_config_path: Optional[Path] = None) -> Tuple[bool, str]:
    """
    Installs Titan Remote Host as a full Windows Service running under LocalSystem.
    Requires Administrator privileges (automatically triggers UAC elevation if needed).
    """
    if sys.platform != "win32":
        return False, "Chỉ hỗ trợ hệ điều hành Windows"

    if not is_current_user_admin():
        elevated = elevate_and_execute("--install-admin")
        if elevated:
            return True, "Đang mở cửa sổ UAC yêu cầu quyền Quản trị viên..."
        return False, "Người dùng đã từ chối cấp quyền Administrator (UAC)"

    try:
        admin_dir = get_admin_install_dir()
        exe_path = copy_exe_to_dir(admin_dir, source_config_path)

        # Install and start Windows Service
        ok, msg = manage_windows_service("install")
        if ok:
            manage_windows_service("start")
            # Also register machine-wide highest task
            setup_task_scheduler_autostart(enable=True)
            return True, "Cài đặt Quản trị viên thành công! Windows Service 24/7 đang hoạt động."
        return False, msg
    except Exception as e:
        return False, f"Lỗi cài đặt Quản trị viên: {e}"


def uninstall_admin_tier() -> Tuple[bool, str]:
    """Uninstalls the machine-wide Windows Service and admin autostart."""
    if sys.platform != "win32":
        return False, "Chỉ hỗ trợ hệ điều hành Windows"

    if not is_current_user_admin():
        elevated = elevate_and_execute("--uninstall-admin")
        if elevated:
            return True, "Đang mở cửa sổ UAC yêu cầu quyền Quản trị viên để gỡ bỏ..."
        return False, "Người dùng đã từ chối cấp quyền Administrator (UAC)"

    try:
        ok, msg = manage_windows_service("uninstall")
        setup_task_scheduler_autostart(enable=False)
        return True, "Đã gỡ bỏ hoàn toàn Dịch vụ Windows Service 24/7."
    except Exception as e:
        return False, str(e)


# ---------------------------------------------------------------------------
# HELPERS & SYSTEM CALLS
# ---------------------------------------------------------------------------
def setup_task_scheduler_autostart(enable: bool = True) -> Tuple[bool, str]:
    if sys.platform != "win32":
        return False, "Only supported on Windows"

    if enable:
        exe_path = ensure_permanent_deployment()
        if getattr(sys, "frozen", False):
            cmd = f'"{exe_path}" --autostart'
        else:
            pyw_exe = sys.executable.replace("python.exe", "pythonw.exe")
            script_path = str(Path(__file__).resolve().parent / "gui_agent.py")
            cmd = f'"{pyw_exe}" "{script_path}" --autostart'

        # Try with highest privileges first
        args_highest = [
            "schtasks.exe", "/create",
            "/tn", TASK_NAME,
            "/tr", cmd,
            "/sc", "onlogon",
            "/rl", "highest",
            "/f"
        ]
        try:
            res = subprocess.run(args_highest, capture_output=True, text=True, check=False)
            if res.returncode == 0:
                return True, "Task Scheduler autostart enabled with Highest Privileges"
            else:
                # Fallback to standard user task
                args_standard = [
                    "schtasks.exe", "/create",
                    "/tn", TASK_NAME,
                    "/tr", cmd,
                    "/sc", "onlogon",
                    "/f"
                ]
                res_std = subprocess.run(args_standard, capture_output=True, text=True, check=False)
                if res_std.returncode == 0:
                    return True, "Task Scheduler autostart enabled (Standard User)"
                return False, res.stderr.strip() or res.stdout.strip()
        except Exception as e:
            return False, str(e)
    else:
        args = ["schtasks.exe", "/delete", "/tn", TASK_NAME, "/f"]
        try:
            res = subprocess.run(args, capture_output=True, text=True, check=False)
            return True, "Task Scheduler autostart disabled"
        except Exception as e:
            return False, str(e)


def is_task_scheduler_autostart_enabled() -> bool:
    if sys.platform != "win32":
        return False
    try:
        res = subprocess.run(
            ["schtasks.exe", "/query", "/tn", TASK_NAME],
            capture_output=True,
            text=True,
            check=False
        )
        return res.returncode == 0
    except Exception:
        return False


def is_hkcu_run_enabled() -> bool:
    if sys.platform != "win32":
        return False
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_READ)
        val, _ = winreg.QueryValueEx(key, APP_REG_NAME)
        winreg.CloseKey(key)
        return bool(val)
    except Exception:
        return False


def is_windows_service_installed() -> bool:
    if sys.platform != "win32":
        return False
    try:
        res = subprocess.run(
            ["sc.exe", "query", SERVICE_NAME],
            capture_output=True,
            text=True,
            check=False
        )
        return res.returncode == 0
    except Exception:
        return False


def manage_windows_service(action: str = "install") -> Tuple[bool, str]:
    if sys.platform != "win32":
        return False, "Only supported on Windows"

    admin_dir = get_admin_install_dir()
    exe_path = admin_dir / "TitanRemoteHost.exe"
    if not exe_path.exists():
        exe_path = ensure_permanent_deployment()
    bin_cmd = f'"{exe_path}" --service'

    if action == "install":
        args = [
            "sc.exe", "create", SERVICE_NAME,
            f"binPath= {bin_cmd}",
            f"DisplayName= {SERVICE_DISPLAY_NAME}",
            "start= auto"
        ]
        try:
            res = subprocess.run(args, capture_output=True, text=True, check=False)
            if res.returncode == 0:
                subprocess.run(
                    ["sc.exe", "description", SERVICE_NAME, "Titan Remote Unattended Access Service"],
                    capture_output=True,
                    check=False
                )
                return True, "Windows Service installed successfully (start=auto)"
            return False, res.stderr.strip() or res.stdout.strip()
        except Exception as e:
            return False, str(e)

    elif action == "uninstall":
        try:
            subprocess.run(["sc.exe", "stop", SERVICE_NAME], capture_output=True, check=False)
            res = subprocess.run(["sc.exe", "delete", SERVICE_NAME], capture_output=True, text=True, check=False)
            if res.returncode == 0:
                return True, "Windows Service uninstalled"
            return False, res.stderr.strip() or res.stdout.strip()
        except Exception as e:
            return False, str(e)

    elif action == "start":
        res = subprocess.run(["sc.exe", "start", SERVICE_NAME], capture_output=True, text=True, check=False)
        return res.returncode == 0, res.stdout.strip()

    elif action == "stop":
        res = subprocess.run(["sc.exe", "stop", SERVICE_NAME], capture_output=True, text=True, check=False)
        return res.returncode == 0, res.stdout.strip()

    return False, f"Unknown action: {action}"


def get_deployment_status() -> Dict[str, Any]:
    """Returns a full summary of installation states for the GUI."""
    user_installed = is_task_scheduler_autostart_enabled() or is_hkcu_run_enabled()
    service_installed = is_windows_service_installed()
    return {
        "is_admin": is_current_user_admin(),
        "user_installed": user_installed,
        "service_installed": service_installed,
        "user_exe_path": str(get_user_install_dir() / "TitanRemoteHost.exe"),
        "admin_exe_path": str(get_admin_install_dir() / "TitanRemoteHost.exe")
    }

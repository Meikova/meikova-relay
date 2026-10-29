"""
Deployment & Lifecycle Manager for Meikova Relay Host.
Provides a 2-Tier Installation System:
- Tier 1: User-Level (No Admin Rights Needed)
  - Installed in %LOCALAPPDATA%\\MeikovaRelayHost
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
try:
    import winreg
except ImportError:
    winreg = None
from pathlib import Path
from typing import Tuple, Optional, Dict, Any

TASK_NAME = "MeikovaRelayHost"
SERVICE_NAME = "MeikovaRelayService"
SERVICE_DISPLAY_NAME = "Meikova Relay Host 24/7 Service"
REG_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_REG_NAME = "MeikovaRelayHost"
WIN_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0


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
    """Launches an elevated process via OS Engine (Windows UAC 'runas', macOS osascript, Linux pkexec)."""
    if sys.platform == "win32":
        try:
            import ctypes
            exe = sys.executable
            ret = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", exe, args_str, None, 1
            )
            return ret > 32
        except Exception:
            return False
    try:
        from host_agent.engines import create_platform_engine
        return create_platform_engine(sys.platform).elevate_and_execute(args_str)
    except Exception:
        return False


def get_user_install_dir() -> Path:
    """Returns %LOCALAPPDATA%\\MeikovaRelayHost (no admin rights needed)."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        target = Path(local_app_data) / "MeikovaRelayHost"
    else:
        target = Path.home() / ".meikova-relay"
    try:
        target.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return target


def get_admin_install_dir() -> Path:
    """Returns /opt/meikova-relay-host or %ProgramData%\\MeikovaRelayHost."""
    if sys.platform != "win32":
        target = Path("/opt/meikova-relay-host")
    else:
        prog_data = os.environ.get("ProgramData")
        if prog_data:
            target = Path(prog_data) / "MeikovaRelayHost"
        else:
            target = Path("C:/ProgramData/MeikovaRelayHost")
    try:
        target.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return target


def get_permanent_dir() -> Path:
    """Compatibility alias for get_user_install_dir."""
    return get_user_install_dir()


def get_permanent_exe_path() -> Path:
    """Returns canonical path for executable in user directory."""
    if sys.platform == "win32":
        name = "MeikovaRelayHost.exe"
    elif sys.platform == "darwin":
        name = "MeikovaRelayHost"
    else:
        name = "meikova-relay-host"
    return get_user_install_dir() / name


def is_running_from_permanent_dir() -> bool:
    try:
        current_exe = Path(sys.executable).resolve()
        return (
            current_exe == get_permanent_exe_path().resolve() or
            current_exe == (get_admin_install_dir() / "MeikovaRelayHost.exe").resolve()
        )
    except Exception:
        return False


def copy_exe_to_dir(target_dir: Path, source_config_path: Optional[Path] = None) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    target_exe = target_dir / get_permanent_exe_path().name

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

    if sys.platform != "win32" and target_exe.exists():
        try:
            target_exe.chmod(target_exe.stat().st_mode | 0o755)
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
# TIER 1: USER-LEVEL INSTALLATION (NO ADMIN RIGHTS NEEDED, CROSS-PLATFORM)
# ---------------------------------------------------------------------------
def install_user_tier(source_config_path: Optional[Path] = None) -> Tuple[bool, str]:
    """
    Installs Meikova Relay Host in User Space cross-platform.
    Windows: %LOCALAPPDATA%\\MeikovaRelayHost, Task Scheduler / HKCU\\Run.
    macOS: ~/Library/Application Support/MeikovaRelayHost, ~/Library/LaunchAgents.
    Linux: ~/.meikova_relay_host, ~/.config/autostart.
    NO ADMINISTRATOR PRIVILEGES REQUIRED.
    """
    try:
        user_dir = get_user_install_dir()
        exe_path = copy_exe_to_dir(user_dir, source_config_path)

        if sys.platform == "win32":
            if getattr(sys, "frozen", False):
                cmd = f'"{exe_path}" --autostart'
            else:
                pyw_exe = sys.executable.replace("python.exe", "pythonw.exe")
                script_path = str(Path(__file__).resolve().parent / "gui_agent.py")
                cmd = f'"{pyw_exe}" "{script_path}" --autostart'

            # 1. Register in HKCU\\Run (100% works without admin)
            if winreg:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_SET_VALUE)
                winreg.SetValueEx(key, APP_REG_NAME, 0, winreg.REG_SZ, cmd)
                winreg.CloseKey(key)

            # 2. Register in Task Scheduler (tries /rl highest if possible, otherwise standard)
            setup_task_scheduler_autostart(enable=True)
            return True, f"Cài đặt Người dùng thành công ({user_dir}). Tự chạy khi đăng nhập Windows."

        elif sys.platform == "darwin":
            plist_dir = Path.home() / "Library/LaunchAgents"
            plist_path = plist_dir / "com.meikovarelay.host.plist"
            plist_dir.mkdir(parents=True, exist_ok=True)
            content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.meikovarelay.host</string>
    <key>ProgramArguments</key>
    <array>
        <string>{exe_path}</string>
        <string>--autostart</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>"""
            plist_path.write_text(content, encoding="utf-8")
            return True, f"Cài đặt Người dùng thành công ({user_dir}). Tự khởi động cùng macOS."

        else:
            # Linux
            autostart_dir = Path.home() / ".config/autostart"
            desktop_path = autostart_dir / "meikovarelayhost.desktop"
            autostart_dir.mkdir(parents=True, exist_ok=True)
            content = f"""[Desktop Entry]
Type=Application
Version=1.0
Name=Meikova Relay Host
Comment=Meikova Relay Workstation Host Service
Exec="{exe_path}" --autostart
Icon=meikovarelayhost
Terminal=false
Categories=Network;RemoteAccess;
"""
            desktop_path.write_text(content, encoding="utf-8")
            return True, f"Cài đặt Người dùng thành công ({user_dir}). Tự khởi động cùng Linux."
    except Exception as e:
        return False, f"Lỗi cài đặt Người dùng: {e}"


def uninstall_user_tier() -> Tuple[bool, str]:
    """Removes user-level autostart entries cross-platform."""
    try:
        if sys.platform == "win32":
            if winreg:
                try:
                    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_SET_VALUE)
                    winreg.DeleteValue(key, APP_REG_NAME)
                    winreg.CloseKey(key)
                except Exception:
                    pass
            setup_task_scheduler_autostart(enable=False)
        elif sys.platform == "darwin":
            plist_path = Path.home() / "Library/LaunchAgents/com.meikovarelay.host.plist"
            if plist_path.exists():
                plist_path.unlink()
        else:
            desktop_path = Path.home() / ".config/autostart/meikovarelayhost.desktop"
            if desktop_path.exists():
                desktop_path.unlink()

        return True, "Đã gỡ cài đặt cấp độ Người dùng."
    except Exception as e:
        return False, str(e)


# ---------------------------------------------------------------------------
# TIER 2: ADMIN-LEVEL INSTALLATION (WINDOWS SERVICE & PRE-LOGIN 24/7)
# ---------------------------------------------------------------------------
def install_admin_tier(source_config_path: Optional[Path] = None) -> Tuple[bool, str]:
    """
    Installs Meikova Relay Host as a full Windows Service running under LocalSystem.
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
            res = subprocess.run(args_highest, capture_output=True, text=True, check=False, creationflags=WIN_NO_WINDOW)
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
                res_std = subprocess.run(args_standard, capture_output=True, text=True, check=False, creationflags=WIN_NO_WINDOW)
                if res_std.returncode == 0:
                    return True, "Task Scheduler autostart enabled (Standard User)"
                return False, res.stderr.strip() or res.stdout.strip()
        except Exception as e:
            return False, str(e)
    else:
        args = ["schtasks.exe", "/delete", "/tn", TASK_NAME, "/f"]
        try:
            res = subprocess.run(args, capture_output=True, text=True, check=False, creationflags=WIN_NO_WINDOW)
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
            check=False,
            creationflags=WIN_NO_WINDOW
        )
        return res.returncode == 0
    except Exception:
        return False


def is_hkcu_run_enabled() -> bool:
    if sys.platform != "win32" or not winreg:
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
            check=False,
            creationflags=WIN_NO_WINDOW
        )
        return res.returncode == 0
    except Exception:
        return False


def manage_windows_service(action: str = "install") -> Tuple[bool, str]:
    if sys.platform != "win32":
        return False, "Only supported on Windows"

    admin_dir = get_admin_install_dir()
    exe_path = admin_dir / "MeikovaRelayHost.exe"
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
            res = subprocess.run(args, capture_output=True, text=True, check=False, creationflags=WIN_NO_WINDOW)
            if res.returncode == 0:
                subprocess.run(
                    ["sc.exe", "description", SERVICE_NAME, "Meikova Relay Unattended Access Service"],
                    capture_output=True,
                    check=False,
                    creationflags=WIN_NO_WINDOW
                )
                return True, "Windows Service installed successfully (start=auto)"
            return False, res.stderr.strip() or res.stdout.strip()
        except Exception as e:
            return False, str(e)

    elif action == "uninstall":
        try:
            subprocess.run(["sc.exe", "stop", SERVICE_NAME], capture_output=True, check=False, creationflags=WIN_NO_WINDOW)
            res = subprocess.run(["sc.exe", "delete", SERVICE_NAME], capture_output=True, text=True, check=False, creationflags=WIN_NO_WINDOW)
            if res.returncode == 0:
                return True, "Windows Service uninstalled"
            return False, res.stderr.strip() or res.stdout.strip()
        except Exception as e:
            return False, str(e)

    elif action == "start":
        res = subprocess.run(["sc.exe", "start", SERVICE_NAME], capture_output=True, text=True, check=False, creationflags=WIN_NO_WINDOW)
        return res.returncode == 0, res.stdout.strip()

    elif action == "stop":
        res = subprocess.run(["sc.exe", "stop", SERVICE_NAME], capture_output=True, text=True, check=False, creationflags=WIN_NO_WINDOW)
        return res.returncode == 0, res.stdout.strip()

    return False, f"Unknown action: {action}"


def get_deployment_status() -> Dict[str, Any]:
    """Returns a full summary of installation states for the GUI across Windows, macOS, and Linux."""
    try:
        from host_agent.engines import create_platform_engine
        eng = create_platform_engine(sys.platform)
        user_installed = is_task_scheduler_autostart_enabled() or is_hkcu_run_enabled() or eng.is_autostart_enabled()
        service_installed = is_windows_service_installed() or eng.is_service_installed()
        exe_name = eng.get_executable_name()
    except Exception:
        user_installed = is_task_scheduler_autostart_enabled() or is_hkcu_run_enabled()
        service_installed = is_windows_service_installed()
        exe_name = "MeikovaRelayHost.exe"
    return {
        "is_admin": is_current_user_admin(),
        "user_installed": bool(user_installed),
        "service_installed": bool(service_installed),
        "user_exe_path": str(get_user_install_dir() / exe_name),
        "admin_exe_path": str(get_admin_install_dir() / exe_name)
    }

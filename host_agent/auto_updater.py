"""
Live Auto-Update Engine for Meikova Relay Host.
Handles version polling, atomic binary swap (NTFS rename), and zero-downtime relaunch.
"""

import sys
import os
import time
import json
import shutil
import urllib.request
import subprocess
import threading
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, Callable

WIN_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0


def parse_semver(ver_str: str) -> Tuple[int, ...]:
    """Parses a SemVer string into a comparable tuple of integers."""
    clean = ver_str.strip().lstrip("vV")
    parts = []
    for part in clean.split("."):
        try:
            parts.append(int(part.split("-")[0]))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def check_for_updates(relay_url: str, current_version: str, timeout: float = 5.0) -> Optional[Dict[str, Any]]:
    """Polls the relay server's /api/version endpoint to check for newer releases."""
    if not relay_url:
        return None
    try:
        http_base = relay_url.replace("ws://", "http://").replace("wss://", "https://").rstrip("/")
        api_url = f"{http_base}/api/version"
        req = urllib.request.Request(api_url, headers={"User-Agent": f"MeikovaRelayHost/{current_version}"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                remote_version = data.get("version", "")
                if remote_version and parse_semver(remote_version) > parse_semver(current_version):
                    dl_url = data.get("download_url") or f"/api/download/app/{'MeikovaRelayHost.exe' if sys.platform == 'win32' else 'meikova-relay-host'}"
                    if not dl_url.startswith("http"):
                        dl_url = f"{http_base}{dl_url if dl_url.startswith('/') else '/' + dl_url}"
                    return {
                        "available": True,
                        "current_version": current_version,
                        "latest_version": remote_version,
                        "download_url": dl_url,
                        "name": data.get("name", "Meikova Relay")
                    }
    except Exception:
        pass
    return None


def apply_update(download_url: str, target_exe: Optional[Path] = None, restart_args: Optional[list] = None) -> bool:
    """Downloads updated binary, performs atomic swap via NTFS rename, and relaunches."""
    is_frozen = getattr(sys, "frozen", False)
    if sys.platform == "win32" and not is_frozen:
        return False

    target = (target_exe or Path(sys.executable)).resolve()
    temp_update = target.with_suffix(".exe.update" if sys.platform == "win32" else ".update")
    old_backup = target.with_suffix(".exe.old" if sys.platform == "win32" else ".old")

    try:
        # Download update with chunked stream
        req = urllib.request.Request(download_url, headers={"User-Agent": "MeikovaRelayAutoUpdater"})
        with urllib.request.urlopen(req, timeout=60.0) as resp, open(str(temp_update), "wb") as out:
            shutil.copyfileobj(resp, out, length=64 * 1024)

        # Validate downloaded binary integrity
        if not temp_update.exists():
            return False
        file_size = temp_update.stat().st_size
        # Minimum threshold: 3MB
        if file_size < 3_000_000:
            temp_update.unlink(missing_ok=True)
            return False

        if sys.platform == "win32":
            with open(str(temp_update), "rb") as f:
                header = f.read(2)
                if header != b"MZ":
                    temp_update.unlink(missing_ok=True)
                    return False
        else:
            temp_update.chmod(temp_update.stat().st_mode | 0o755)

        # Remove previous .old backup if present
        if old_backup.exists():
            try:
                old_backup.unlink(missing_ok=True)
            except Exception:
                pass

        # Atomic Swap:
        # On Windows: NTFS Rename allows renaming running exe -> .old, then .update -> .exe
        # On POSIX: atomic replace
        if sys.platform == "win32":
            target.rename(old_backup)
            temp_update.rename(target)
        else:
            temp_update.replace(target)

        # Filter out existing --updated from argv to avoid duplication
        raw_args = restart_args if restart_args is not None else sys.argv[1:]
        clean_args = [a for a in raw_args if a != "--updated"]
        args = [str(target), "--updated"] + clean_args

        # Spawn new binary
        subprocess.Popen(args, cwd=str(target.parent), close_fds=True)
        sys.exit(0)
    except Exception:
        # Rollback atomic swap if failure occurred
        try:
            if not target.exists() and old_backup.exists():
                old_backup.rename(target)
        except Exception:
            pass
        if temp_update.exists():
            try:
                temp_update.unlink(missing_ok=True)
            except Exception:
                pass
        return False


def cleanup_post_update(target_dir: Optional[Path] = None, retries: int = 5, delay: float = 0.4) -> int:
    """Removes temporary *.old or *.update binaries after a successful relaunch.
    Retries up to retries times to handle brief file locks from terminating parent process."""
    base = target_dir or (Path(sys.executable).parent if getattr(sys, "frozen", False) else Path.cwd())
    if not base.exists():
        return 0

    cleaned = 0
    patterns = ("*.exe.old", "*.exe.update", "*.old", "*.update")
    for attempt in range(max(1, retries)):
        all_done = True
        for pattern in patterns:
            for item in list(base.glob(pattern)):
                try:
                    item.unlink(missing_ok=True)
                    cleaned += 1
                except (PermissionError, OSError):
                    all_done = False
                except Exception:
                    pass
        if all_done:
            break
        time.sleep(delay)
    return cleaned


def check_and_apply_update(
    relay_url: str,
    current_version: str,
    target_exe: Optional[Path] = None,
    restart_args: Optional[list] = None
) -> bool:
    """Checks relay server for newer version and applies atomic swap if available."""
    info = check_for_updates(relay_url, current_version)
    if info and info.get("available") and info.get("download_url"):
        return apply_update(info["download_url"], target_exe=target_exe, restart_args=restart_args)
    return False


def start_auto_update_loop(
    relay_url: str,
    current_version: str,
    interval_seconds: float = 1800.0,
    target_exe: Optional[Path] = None,
    on_update_found: Optional[Callable[[Dict[str, Any]], None]] = None
) -> threading.Thread:
    """Spawns background daemon thread to periodically poll for updates and apply atomic swap."""
    def _loop():
        # Delay initial check by 20 seconds so application boots smoothly
        time.sleep(20.0)
        while True:
            try:
                info = check_for_updates(relay_url, current_version)
                if info and info.get("available") and info.get("download_url"):
                    if on_update_found:
                        try:
                            on_update_found(info)
                        except Exception:
                            pass
                    apply_update(info["download_url"], target_exe=target_exe)
                    break
            except Exception:
                pass
            time.sleep(interval_seconds)

    thread = threading.Thread(target=_loop, daemon=True, name="AutoUpdateWorker")
    thread.start()
    return thread

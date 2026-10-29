"""Zero-Touch Dependency Bootstrap & Local Vendor Wheelhouse Manager for Meikova Relay Host.

Supports 3 modes of operation so users never need to run manual pip commands:
1. Local Vendor Source Directory (`vendor/packages/` or `vendor/wheels/`):
   - Automatically prepends `vendor/packages` to `sys.path` if pre-extracted packages exist in source.
   - Automatically installs from `vendor/wheels/` offline if `.whl` files are bundled in source.
2. Automatic Runtime Pip Bootstrap (`ensure_dependencies()`):
   - Checks required & optional high-FPS packages per OS (`Windows`, `macOS`, `Linux`) on startup.
   - Automatically installs any missing packages via `sys.executable -m pip install` with safe fallbacks
     (`--user`, `--break-system-packages` on PEP 668 Linux distros).
3. Offline Wheelhouse Downloader (`download_wheelhouse()`):
   - Downloads all required `.whl` files into `vendor/wheels/` so the entire source folder can be
     copied and deployed offline with all libraries bundled inside the repository.
"""

from __future__ import annotations

import importlib.util
import logging
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("MeikovaBootstrap")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_DIR = PROJECT_ROOT / "vendor"
VENDOR_PACKAGES_DIR = VENDOR_DIR / "packages"
VENDOR_WHEELS_DIR = VENDOR_DIR / "wheels"
VENDOR_NATIVE_DIR = VENDOR_DIR / "native"

# Core cross-platform dependencies: (import_name, pip_spec, category, description)
COMMON_DEPENDENCIES: List[Tuple[str, str, str, str]] = [
    ("websockets", "websockets>=12.0", "core", "WebSocket transport"),
    ("PIL", "Pillow>=10.0.0", "core", "Image processing & fallback JPEG/WebP encoder"),
    ("mss", "mss>=9.0.0", "core", "Cross-platform ultra-fast screen capture"),
    ("numpy", "numpy>=1.26.0", "high_fps", "SIMD array buffer manipulation for 2K/4K capture"),
    ("cv2", "opencv-python-headless>=4.9.0", "high_fps", "Hardware-accelerated SIMD image resize & JPEG/WebP encode"),
    ("turbojpeg", "PyTurboJPEG>=1.7.0", "high_fps", "libjpeg-turbo SIMD encoder for 240-1000+ FPS"),
    ("psutil", "psutil>=5.9.0", "core", "System telemetry, CPU/RAM & process manager"),
    ("pystray", "pystray>=0.19.0", "gui", "Cross-platform system tray icon & menu"),
    ("pyperclip", "pyperclip>=1.8.2", "core", "Clipboard synchronization"),
    ("pyautogui", "pyautogui>=0.9.54", "input", "Cross-platform mouse & keyboard injection fallback"),
    ("sounddevice", "sounddevice>=0.4.6", "audio", "Low-latency audio loopback & voice intercom"),
]

OS_SPECIFIC_DEPENDENCIES: Dict[str, List[Tuple[str, str, str, str]]] = {
    "windows": [
        ("win32api", "pywin32>=306", "os_native", "Windows Win32 API, Service & UAC integration"),
        ("dxcam", "dxcam>=0.0.5", "high_fps", "Windows Desktop Duplication API (DXGI) GPU capture"),
        ("pyaudiowpatch", "PyAudioWPatch>=0.2.12.6", "audio", "Windows WASAPI loopback audio capture"),
    ],
    "darwin": [
        ("Quartz", "pyobjc-framework-Quartz>=10.0", "os_native", "macOS CoreGraphics & CGEvent native engine"),
        ("ApplicationServices", "pyobjc-framework-ApplicationServices>=10.0", "os_native", "macOS Accessibility & input control"),
    ],
    "linux": [
        ("Xlib", "python-xlib>=0.33", "os_native", "Linux X11 display, window & input integration"),
    ],
}


def get_os_key() -> str:
    sys_plat = sys.platform.lower()
    if sys_plat.startswith("win"):
        return "windows"
    if sys_plat == "darwin":
        return "darwin"
    return "linux"


def activate_vendor_paths() -> Dict[str, Any]:
    """Mount `vendor/packages` into `sys.path` and `vendor/native` into shared library env vars."""
    mounted_packages = False
    mounted_native = False

    if VENDOR_PACKAGES_DIR.is_dir():
        pkg_path = str(VENDOR_PACKAGES_DIR)
        if pkg_path not in sys.path:
            sys.path.insert(0, pkg_path)
        mounted_packages = True

    if VENDOR_NATIVE_DIR.is_dir():
        native_path = str(VENDOR_NATIVE_DIR)
        os_key = get_os_key()
        if os_key == "windows":
            os.environ["PATH"] = native_path + os.pathsep + os.environ.get("PATH", "")
            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(native_path)
                except Exception:
                    pass
        elif os_key == "darwin":
            os.environ["DYLD_LIBRARY_PATH"] = native_path + os.pathsep + os.environ.get("DYLD_LIBRARY_PATH", "")
        else:
            os.environ["LD_LIBRARY_PATH"] = native_path + os.pathsep + os.environ.get("LD_LIBRARY_PATH", "")
        mounted_native = True

    return {
        "vendor_packages_dir": str(VENDOR_PACKAGES_DIR),
        "vendor_wheels_dir": str(VENDOR_WHEELS_DIR),
        "vendor_native_dir": str(VENDOR_NATIVE_DIR),
        "mounted_packages": mounted_packages,
        "mounted_native": mounted_native,
    }


def is_module_installed(import_name: str) -> bool:
    """Fast, side-effect-free check if a Python module is importable."""
    try:
        spec = importlib.util.find_spec(import_name)
        if spec is not None:
            return True
    except (ImportError, ValueError, AttributeError):
        pass
    try:
        __import__(import_name)
        return True
    except Exception:
        return False


def get_target_dependencies(include_os_specific: bool = True) -> List[Tuple[str, str, str, str]]:
    deps = list(COMMON_DEPENDENCIES)
    if include_os_specific:
        os_key = get_os_key()
        deps.extend(OS_SPECIFIC_DEPENDENCIES.get(os_key, []))
    return deps


def inspect_dependencies() -> Dict[str, Any]:
    """Return a structured report of all installed and missing dependencies for the current OS."""
    activate_vendor_paths()
    os_key = get_os_key()
    deps = get_target_dependencies(include_os_specific=True)
    installed: List[Dict[str, str]] = []
    missing: List[Dict[str, str]] = []

    for import_name, pip_spec, category, desc in deps:
        entry = {
            "import_name": import_name,
            "pip_spec": pip_spec,
            "category": category,
            "description": desc,
        }
        if is_module_installed(import_name):
            installed.append(entry)
        else:
            missing.append(entry)

    has_local_wheels = VENDOR_WHEELS_DIR.is_dir() and any(VENDOR_WHEELS_DIR.glob("*.whl"))
    return {
        "os": os_key,
        "python_version": platform.python_version(),
        "is_frozen_binary": bool(getattr(sys, "frozen", False)),
        "installed_count": len(installed),
        "missing_count": len(missing),
        "all_satisfied": len(missing) == 0,
        "has_local_wheels": has_local_wheels,
        "vendor_wheels_dir": str(VENDOR_WHEELS_DIR),
        "vendor_packages_dir": str(VENDOR_PACKAGES_DIR),
        "installed": installed,
        "missing": missing,
    }


def _run_pip_install(pip_specs: List[str], timeout: int = 180) -> Tuple[bool, str]:
    """Install a list of pip specs using offline wheelhouse first, then online PyPI with PEP-668 fallback."""
    if not pip_specs:
        return True, "All packages already satisfied."

    base_cmd = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--no-warn-script-location"]

    # 1. Try offline local wheelhouse first if available (`vendor/wheels/*.whl`)
    if VENDOR_WHEELS_DIR.is_dir() and any(VENDOR_WHEELS_DIR.glob("*.whl")):
        offline_cmd = base_cmd + ["--no-index", "--find-links", str(VENDOR_WHEELS_DIR)] + pip_specs
        try:
            res = subprocess.run(offline_cmd, capture_output=True, text=True, timeout=timeout)
            if res.returncode == 0:
                return True, f"Installed offline from {VENDOR_WHEELS_DIR}"
        except Exception as e:
            logger.debug(f"Offline wheelhouse install fallback to online: {e}")

    # 2. Try standard pip install
    attempts = [
        base_cmd + pip_specs,
        base_cmd + ["--user"] + pip_specs,
        base_cmd + ["--break-system-packages"] + pip_specs,
        base_cmd + ["--user", "--break-system-packages"] + pip_specs,
    ]
    last_err = ""
    for cmd in attempts:
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if res.returncode == 0:
                return True, (res.stdout or "Installed successfully.").strip()
            last_err = (res.stderr or res.stdout or "").strip()
            if "no such option: --break-system-packages" in last_err.lower():
                continue
        except Exception as e:
            last_err = str(e)

    return False, last_err


def ensure_dependencies(
    auto_install: bool = True,
    categories: Optional[List[str]] = None,
    quiet: bool = False,
) -> Dict[str, Any]:
    """Check and optionally auto-install missing dependencies at startup."""
    activate_vendor_paths()

    # Never run pip inside a PyInstaller frozen executable or inside unit tests unless explicitly requested
    if getattr(sys, "frozen", False):
        return inspect_dependencies()

    status = inspect_dependencies()
    missing = status["missing"]
    if categories:
        missing = [m for m in missing if m["category"] in categories]

    if not missing or not auto_install:
        return status

    if not quiet:
        logger.info(
            f"[AutoBootstrap] Phát hiện {len(missing)} thư viện chưa cài đặt ({', '.join(m['import_name'] for m in missing)}). Đang tự động cài đặt..."
        )

    installed_now: List[str] = []
    failed_now: List[Dict[str, str]] = []

    # Install each package individually so an optional OS-specific package failure never blocks core packages
    for item in missing:
        spec = item["pip_spec"]
        ok, msg = _run_pip_install([spec], timeout=120)
        if ok and is_module_installed(item["import_name"]):
            installed_now.append(item["import_name"])
            if not quiet:
                logger.info(f"[AutoBootstrap] + Đã cài đặt tự động: {spec}")
        else:
            failed_now.append({"pip_spec": spec, "reason": msg[:300]})
            if not quiet:
                logger.warning(f"[AutoBootstrap] ! Không thể tự động cài {spec}: {msg[:160]}")

    updated = inspect_dependencies()
    updated["installed_now"] = installed_now
    updated["failed_now"] = failed_now
    return updated


def download_wheelhouse(target_dir: Optional[Path] = None, include_os_specific: bool = True) -> Dict[str, Any]:
    """Download `.whl` packages into `vendor/wheels/` so the source tree is 100% self-contained offline."""
    dest = Path(target_dir) if target_dir else VENDOR_WHEELS_DIR
    dest.mkdir(parents=True, exist_ok=True)
    deps = get_target_dependencies(include_os_specific=include_os_specific)
    specs = [d[1] for d in deps]
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "download",
        "--dest",
        str(dest),
        "--disable-pip-version-check",
    ] + specs
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        wheels = [p.name for p in sorted(dest.glob("*.whl"))]
        return {
            "success": res.returncode == 0,
            "wheel_count": len(wheels),
            "wheels": wheels,
            "target_dir": str(dest),
            "message": (res.stdout or res.stderr or "").strip()[:500],
        }
    except Exception as e:
        return {
            "success": False,
            "wheel_count": 0,
            "wheels": [],
            "target_dir": str(dest),
            "message": str(e),
        }


def install_into_vendor_packages(target_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Install dependencies directly into `vendor/packages/` inside the source tree (`--target`)."""
    dest = Path(target_dir) if target_dir else VENDOR_PACKAGES_DIR
    dest.mkdir(parents=True, exist_ok=True)
    deps = get_target_dependencies(include_os_specific=True)
    specs = [d[1] for d in deps]
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--target",
        str(dest),
        "--upgrade",
        "--disable-pip-version-check",
        "--no-warn-script-location",
    ]
    if VENDOR_WHEELS_DIR.is_dir() and any(VENDOR_WHEELS_DIR.glob("*.whl")):
        cmd.extend(["--no-index", "--find-links", str(VENDOR_WHEELS_DIR)])
    cmd.extend(specs)
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        activate_vendor_paths()
        return {
            "success": res.returncode == 0,
            "target_dir": str(dest),
            "message": (res.stdout or res.stderr or "").strip()[:500],
        }
    except Exception as e:
        return {
            "success": False,
            "target_dir": str(dest),
            "message": str(e),
        }

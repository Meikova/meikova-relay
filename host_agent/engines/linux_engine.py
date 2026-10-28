"""Dedicated High-Performance Linux Engine (X11 XShm / Wayland / Headless Xvfb + SIMD libturbojpeg.so.0)."""

import os
import sys
import platform
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from .base_engine import BaseOSEngine


class LinuxEngine(BaseOSEngine):
    """Dedicated Linux Host Engine optimized for Ubuntu, Debian, Fedora, Arch (X11/XShm & Wayland)."""

    engine_name = "LinuxEngine (X11 XShm / Wayland + SIMD TurboJPEG)"
    platform_key = "linux"

    def __init__(self):
        self.initialize_runtime()

    def initialize_runtime(self) -> None:
        pass

    def get_os_display_name(self) -> str:
        arch = "64-bit" if (sys.maxsize > 2**32 or platform.machine().endswith("64")) else "32-bit"
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

    def is_admin(self) -> bool:
        try:
            return os.geteuid() == 0
        except Exception:
            return False

    def get_turbojpeg_candidates(self) -> List[str]:
        here = Path(__file__).resolve().parent.parent
        return [
            str(here / "libturbojpeg.so.0"),
            "libturbojpeg.so.0",
            "/usr/lib/x86_64-linux-gnu/libturbojpeg.so.0",
            "/usr/lib/aarch64-linux-gnu/libturbojpeg.so.0",
            "/usr/lib64/libturbojpeg.so.0",
            "/usr/lib/libturbojpeg.so.0",
            "/usr/lib/libturbojpeg.so",
        ]

    def detect_monitors(self, sct_instance: Any = None) -> List[Dict[str, Any]]:
        results = []
        if sct_instance is not None:
            try:
                mons = sct_instance.monitors[1:] if len(sct_instance.monitors) > 1 else sct_instance.monitors
                for i, m in enumerate(mons):
                    left = int(m.get("left", 0))
                    top = int(m.get("top", 0))
                    w = int(m.get("width", 1920))
                    h = int(m.get("height", 1080))
                    results.append({
                        "id": i + 1,
                        "name": f"Màn {i + 1}",
                        "rect": (left, top, left + w, top + h),
                        "x": left,
                        "y": top,
                        "left": left,
                        "top": top,
                        "width": w,
                        "height": h,
                    })
            except Exception:
                pass
        if not results:
            results.append({
                "id": 1,
                "name": "Màn 1",
                "rect": (0, 0, 1920, 1080),
                "x": 0,
                "y": 0,
                "left": 0,
                "top": 0,
                "width": 1920,
                "height": 1080,
            })
        return results

    def grab_frame_raw(
        self,
        left: int,
        top: int,
        width: int,
        height: int,
        monitor_id: int = 0,
        native_cap: Any = None,
        sct_instance: Any = None,
        dxcam_instance: Any = None,
    ) -> Tuple[Optional[Tuple[int, int]], Any, bool]:
        if sct_instance is not None:
            try:
                if monitor_id == 0:
                    mon_target = sct_instance.monitors[0]
                elif 1 <= monitor_id < len(sct_instance.monitors):
                    mon_target = sct_instance.monitors[monitor_id]
                else:
                    mon_target = {"left": left, "top": top, "width": width, "height": height}
                shot = sct_instance.grab(mon_target)
                return (shot.width, shot.height), shot.raw, False
            except Exception:
                pass
        return None, None, False

    def get_shell_command(self) -> List[str]:
        return ["/bin/bash"] if os.path.exists("/bin/bash") else ["/bin/sh"]

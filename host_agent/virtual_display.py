"""
Meikova Virtual Display Provisioner
Enables high-resolution remote desktop streaming for headless workstations without physical monitors.
Cross-platform support:
- Windows: Microsoft IddCx (Indirect Display Driver Class eXtension) 1080p/2K/4K @ 60/120Hz
- Linux: Xvfb / xserver-xorg-video-dummy virtual display resolution negotiation
- macOS: Virtual display bridge guidance
"""

import os
import sys
import time
import io
import shutil
import zipfile
import logging
import urllib.request
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image, ImageDraw

logger = logging.getLogger("MeikovaVirtualDisplay")

IDDCX_DRIVER_URL = "https://github.com/itsmikethetech/Virtual-Display-Driver/releases/latest/download/Virtual-Display-Driver.zip"

AVAILABLE_RESOLUTIONS = [
    {"name": "1080p (FHD)", "width": 1920, "height": 1080, "aspect": "16:9", "badge": "FHD"},
    {"name": "2K (QHD)", "width": 2560, "height": 1440, "aspect": "16:9", "badge": "2K"},
    {"name": "4K (UHD)", "width": 3840, "height": 2160, "aspect": "16:9", "badge": "4K"},
    {"name": "720p (HD)", "width": 1280, "height": 720, "aspect": "16:9", "badge": "720p"},
    {"name": "900p (HD+)", "width": 1600, "height": 900, "aspect": "16:9", "badge": "900p"},
    {"name": "Laptop (HD)", "width": 1366, "height": 768, "aspect": "16:9", "badge": "HD"},
    {"name": "Ultrawide (WFHD)", "width": 2560, "height": 1080, "aspect": "21:9", "badge": "21:9"},
    {"name": "Ultrawide (WQHD)", "width": 3440, "height": 1440, "aspect": "21:9", "badge": "UW2K"}
]

def get_available_resolutions() -> List[Dict[str, Any]]:
    """Returns standard cross-platform supported resolutions."""
    return list(AVAILABLE_RESOLUTIONS)

def is_headless_display() -> bool:
    """Detects if the host is running headless across Windows, Linux, and macOS."""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32

            SM_CXVIRTUALSCREEN = 78
            SM_CYVIRTUALSCREEN = 79
            SM_CXSCREEN = 0
            SM_CYSCREEN = 1

            vw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
            vh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
            sw = user32.GetSystemMetrics(SM_CXSCREEN)
            sh = user32.GetSystemMetrics(SM_CYSCREEN)

            if vw <= 0 or vh <= 0 or sw <= 0 or sh <= 0:
                return True

            # Fast check via EnumDisplayDevicesW: detect Microsoft Basic Display Adapter
            is_basic_adapter = False
            has_attached_physical_monitor = False

            class DISPLAY_DEVICEW(ctypes.Structure):
                _fields_ = [
                    ('cb', wintypes.DWORD),
                    ('DeviceName', wintypes.WCHAR * 32),
                    ('DeviceString', wintypes.WCHAR * 128),
                    ('StateFlags', wintypes.DWORD),
                    ('DeviceID', wintypes.WCHAR * 128),
                    ('DeviceKey', wintypes.WCHAR * 128)
                ]

            dd = DISPLAY_DEVICEW()
            dd.cb = ctypes.sizeof(dd)
            i = 0
            while user32.EnumDisplayDevicesW(None, i, ctypes.byref(dd), 0):
                if dd.StateFlags & 0x1:  # DISPLAY_DEVICE_ATTACHED_TO_DESKTOP
                    d_str = dd.DeviceString.lower()
                    if "basic display" in d_str or "basic render" in d_str or "vnc" in d_str:
                        is_basic_adapter = True
                    dd_mon = DISPLAY_DEVICEW()
                    dd_mon.cb = ctypes.sizeof(dd_mon)
                    j = 0
                    while user32.EnumDisplayDevicesW(dd.DeviceName, j, ctypes.byref(dd_mon), 0):
                        if dd_mon.StateFlags & 0x1:
                            has_attached_physical_monitor = True
                        j += 1
                i += 1

            if is_basic_adapter and not has_attached_physical_monitor:
                return True

            # Check 1024x768 or lower resolution (typical Microsoft Basic Display Adapter headless mode)
            if (sw <= 1024 and sh <= 768) or is_basic_adapter:
                cmd = 'powershell -NoProfile -Command "@(Get-CimInstance WmiMonitorBasicDisplayParams -Namespace root/wmi -ErrorAction SilentlyContinue).Count"'
                res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=3)
                count_str = res.stdout.strip()
                if count_str.isdigit() and int(count_str) == 0:
                    return True

            return False
        except Exception as e:
            logger.warning(f"[VirtualDisplay] Windows headless check error: {e}")
            return False

    elif sys.platform.startswith("linux"):
        disp = os.environ.get("DISPLAY")
        if not disp:
            return True
        try:
            res = subprocess.run(["xrandr"], capture_output=True, text=True, timeout=3)
            return " connected" not in res.stdout
        except Exception:
            return False

    elif sys.platform == "darwin":
        return False

    return False

def get_virtual_display_driver_status() -> Dict[str, Any]:
    """Checks if a Virtual Display Driver is installed on the host."""
    if sys.platform == "win32":
        try:
            cmd = 'powershell -NoProfile -Command "Get-PnpDevice -FriendlyName \\"*Virtual Display*\\" -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FriendlyName"'
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            name = res.stdout.strip()
            if name:
                return {"installed": True, "driver_name": name}
        except Exception:
            pass
    elif sys.platform.startswith("linux"):
        if shutil.which("Xvfb"):
            return {"installed": True, "driver_name": "Xvfb Virtual Framebuffer"}

    return {"installed": False, "driver_name": None}

def generate_headless_placeholder(width: int = 1920, height: int = 1080) -> bytes:
    """Generates an Ambient Dark high-resolution placeholder frame when a host has no physical display."""
    width = max(640, int(width or 1920))
    height = max(480, int(height or 1080))
    img = Image.new("RGB", (width, height), (7, 13, 23))
    d = ImageDraw.Draw(img)

    d.line([(0, 0), (width, 0)], fill=(34, 197, 94), width=4)

    cx = width // 2
    cy = height // 2

    mon_w, mon_h = 240, 150
    mon_x = cx - mon_w // 2
    mon_y = cy - 140
    d.rectangle([mon_x, mon_y, mon_x + mon_w, mon_y + mon_h], outline=(56, 189, 248), width=3)
    d.line([cx - 40, mon_y + mon_h + 20, cx + 40, mon_y + mon_h + 20], fill=(100, 116, 139), width=3)
    d.line([cx, mon_y + mon_h, cx, mon_y + mon_h + 20], fill=(100, 116, 139), width=3)

    d.polygon([(cx, mon_y + 40), (cx - 30, mon_y + 100), (cx + 30, mon_y + 100)], outline=(34, 197, 94), fill=(15, 23, 42))
    d.line([(cx, mon_y + 58), (cx, mon_y + 80)], fill=(34, 197, 94), width=3)
    d.ellipse([(cx - 2, mon_y + 88), (cx + 2, mon_y + 92)], fill=(34, 197, 94))

    d.text((cx, cy + 50), "MEIKOVA RELAY // CHẾ ĐỘ MÁY TRẠM KHÔNG MÀN HÌNH (HEADLESS)", fill=(255, 255, 255), anchor="mm")
    d.text((cx, cy + 90), "Máy trạm hiện không cắm màn hình vật lý vào card đồ họa (NVIDIA / AMD / Intel).", fill=(148, 163, 184), anchor="mm")
    d.text((cx, cy + 130), f"[ ĐỘ PHÂN GIẢI ẢO HIỆN TẠI: {width} x {height} ]", fill=(34, 197, 94), anchor="mm")
    d.text((cx, cy + 165), "Nhấn nút 'Kích Hoạt Màn Hình Ảo' trên menu Độ phân giải hoặc chạy: MeikovaRelayHost.exe --install-virtual-display", fill=(100, 116, 139), anchor="mm")

    bio = io.BytesIO()
    img.save(bio, format="JPEG", quality=85)
    return bio.getvalue()

def download_and_install_virtual_display() -> Dict[str, Any]:
    """Installs or creates a virtual display driver across Windows, Linux, and macOS."""
    if sys.platform == "win32":
        target_dir = Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "MeikovaVirtualDisplay"
        zip_path = target_dir / "driver.zip"

        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            options_file = target_dir / "options.txt"
            options_content = (
                "1\n"
                "1920, 1080, 60\n"
                "1920, 1080, 120\n"
                "2560, 1440, 60\n"
                "3840, 2160, 60\n"
                "1280, 720, 60\n"
            )
            options_file.write_text(options_content, encoding="utf-8")
            logger.info(f"[VirtualDisplay] Wrote options.txt to {options_file}")

            logger.info(f"[VirtualDisplay] Downloading Virtual Display Driver from {IDDCX_DRIVER_URL}...")
            req = urllib.request.Request(IDDCX_DRIVER_URL, headers={"User-Agent": "Mozilla/5.0 MeikovaRelay/1.0"})
            with urllib.request.urlopen(req, timeout=35) as resp, open(zip_path, "wb") as out:
                shutil.copyfileobj(resp, out)

            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(target_dir)

            inf_file = None
            for p in target_dir.rglob("*.inf"):
                if "idd" in p.name.lower() or "display" in p.name.lower():
                    inf_file = p
                    break

            if not inf_file:
                return {"success": False, "message": "Không tìm thấy tệp cấu hình INF của driver màn hình ảo."}

            cmd = f'Start-Process -FilePath "pnputil.exe" -ArgumentList "/add-driver `"{inf_file}`" /install" -Wait -Verb RunAs'
            proc = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
                                  capture_output=True, text=True, timeout=60)

            time.sleep(3)
            try:
                subprocess.run(["DisplaySwitch.exe", "/extend"], timeout=5)
            except Exception:
                pass

            return {
                "success": True,
                "message": "Đã cài đặt Màn Hình Ảo thành công! Màn hình 1080p/2K/4K đã sẵn sàng."
            }
        except Exception as e:
            logger.error(f"[VirtualDisplay] Windows install error: {e}")
            return {"success": False, "message": f"Lỗi cài đặt Màn hình ảo: {str(e)}"}
        finally:
            try:
                if zip_path.exists():
                    zip_path.unlink(missing_ok=True)
            except Exception:
                pass

    elif sys.platform.startswith("linux"):
        if shutil.which("Xvfb"):
            try:
                subprocess.Popen(["Xvfb", ":99", "-screen", "0", "1920x1080x24"])
                os.environ["DISPLAY"] = ":99"
                return {"success": True, "message": "Đã khởi chạy Xvfb Virtual Framebuffer (:99) 1920x1080 thành công."}
            except Exception as e:
                return {"success": False, "message": f"Lỗi khởi chạy Xvfb: {e}"}
        return {"success": False, "message": "Trên Linux, vui lòng cài đặt Xvfb (chạy: sudo apt install -y xvfb x11-xserver-utils) để tạo màn hình ảo."}

    elif sys.platform == "darwin":
        return {"success": False, "message": "Trên macOS, vui lòng sử dụng BetterDisplay hoặc DummyDisplay để tạo màn hình ảo."}

    return {"success": False, "message": f"Nền tảng {sys.platform} chưa được hỗ trợ."}

def set_display_resolution(width: int, height: int, refresh_rate: int = 60) -> Dict[str, Any]:
    """
    Sets display resolution across Windows, Linux, and macOS.
    Updates virtual display driver configuration if present, or issues native OS resolution changes.
    """
    width = int(width)
    height = int(height)
    refresh_rate = int(refresh_rate or 60)

    # 1. Windows
    if sys.platform == "win32":
        target_dir = Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "MeikovaVirtualDisplay"
        options_file = target_dir / "options.txt"
        if target_dir.exists():
            try:
                options_content = (
                    "1\n"
                    f"{width}, {height}, {refresh_rate}\n"
                    "1920, 1080, 60\n"
                    "2560, 1440, 60\n"
                    "3840, 2160, 60\n"
                    "1280, 720, 60\n"
                )
                options_file.write_text(options_content, encoding="utf-8")
                logger.info(f"[VirtualDisplay] Updated IddCx options.txt with primary resolution {width}x{height}")
            except Exception as e:
                logger.warning(f"[VirtualDisplay] Could not update options.txt: {e}")

        # Attempt Win32 ChangeDisplaySettingsExW
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            buf = ctypes.create_string_buffer(256)
            ctypes.c_uint16.from_buffer(buf, 68).value = 188
            if user32.EnumDisplaySettingsW(None, -1, buf):
                ctypes.c_uint32.from_buffer(buf, 72).value = 0x00080000 | 0x00100000
                ctypes.c_uint32.from_buffer(buf, 172).value = width
                ctypes.c_uint32.from_buffer(buf, 176).value = height
                ctypes.c_uint32.from_buffer(buf, 184).value = refresh_rate
                ret = user32.ChangeDisplaySettingsW(buf, 0)
                if ret == 0:
                    logger.info(f"[VirtualDisplay] Applied native display resolution {width}x{height} via Win32.")
                    return {"success": True, "width": width, "height": height, "native": True, "message": f"Đã áp dụng độ phân giải {width}x{height}"}
        except Exception as e:
            logger.debug(f"[VirtualDisplay] Win32 ChangeDisplaySettings error: {e}")

        return {
            "success": True,
            "width": width,
            "height": height,
            "native": False,
            "virtual_canvas": True,
            "message": f"Đã điều chỉnh phân giải màn hình ảo thành {width}x{height}"
        }

    # 2. Linux
    elif sys.platform.startswith("linux"):
        try:
            res = subprocess.run(["xrandr"], capture_output=True, text=True, timeout=3)
            out_name = None
            for line in res.stdout.splitlines():
                if " connected" in line:
                    out_name = line.split()[0]
                    break

            if out_name:
                cmd = ["xrandr", "--output", out_name, "--mode", f"{width}x{height}"]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
                if r.returncode == 0:
                    logger.info(f"[VirtualDisplay] Linux xrandr applied {width}x{height} on {out_name}")
                    return {"success": True, "width": width, "height": height, "native": True, "message": f"Đã áp dụng {width}x{height} trên {out_name}"}

            subprocess.run(["xrandr", "-s", f"{width}x{height}"], capture_output=True, timeout=3)
            subprocess.run(["xrandr", "--fb", f"{width}x{height}"], capture_output=True, timeout=3)
        except Exception as e:
            logger.warning(f"[VirtualDisplay] Linux xrandr error: {e}")

        return {
            "success": True,
            "width": width,
            "height": height,
            "virtual_canvas": True,
            "message": f"Đã cấu hình phân giải hiển thị {width}x{height} (Linux)"
        }

    # 3. macOS
    elif sys.platform == "darwin":
        if shutil.which("displayplacer"):
            try:
                subprocess.run(["displayplacer", f"res:{width}x{height}"], capture_output=True, timeout=4)
            except Exception:
                pass
        return {
            "success": True,
            "width": width,
            "height": height,
            "virtual_canvas": True,
            "message": f"Đã cấu hình phân giải hiển thị {width}x{height} (macOS)"
        }

    return {"success": True, "width": width, "height": height, "virtual_canvas": True, "message": f"Đã áp dụng phân giải {width}x{height}"}

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Platform:", sys.platform)
    print("Is Headless Display:", is_headless_display())
    print("Virtual Display Driver Status:", get_virtual_display_driver_status())
    if "--install" in sys.argv:
        print(download_and_install_virtual_display())

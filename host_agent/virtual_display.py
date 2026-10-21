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

def is_headless_display() -> bool:
    """Detects if the host is running headless across Windows, Linux, and macOS."""
    if sys.platform == "win32":
        try:
            import ctypes
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

            if sw <= 800 and sh <= 600:
                cmd = 'powershell -NoProfile -Command "(Get-CimInstance WmiMonitorBasicDisplayParams -Namespace root\\wmi -ErrorAction SilentlyContinue | Where-Object { $_.Active }).Count"'
                res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
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
            cmd = 'powershell -NoProfile -Command "Get-PnpDevice -FriendlyName \"*Virtual Display*\" -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FriendlyName"'
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
    d.text((cx, cy + 130), "[ KÍCH HOẠT MÀN HÌNH ẢO ĐỂ MỞ ĐẦY ĐỦ ĐỘ PHÂN GIẢI 1080P / 2K / 4K ]", fill=(34, 197, 94), anchor="mm")
    d.text((cx, cy + 165), "Nhấn nút 'Kích Hoạt Màn Hình Ảo' trên thông báo hoặc chạy: MeikovaRelayHost.exe --install-virtual-display", fill=(100, 116, 139), anchor="mm")

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
        return {"success": False, "message": "Trên Linux, vui lòng cài đặt Xvfb (chạy: sudo apt install xvfb) để tạo màn hình ảo."}

    elif sys.platform == "darwin":
        return {"success": False, "message": "Trên macOS, vui lòng sử dụng BetterDisplay hoặc DummyDisplay để tạo màn hình ảo."}

    return {"success": False, "message": f"Nền tảng {sys.platform} chưa được hỗ trợ."}

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Platform:", sys.platform)
    print("Is Headless Display:", is_headless_display())
    print("Virtual Display Driver Status:", get_virtual_display_driver_status())
    if "--install" in sys.argv:
        print(download_and_install_virtual_display())

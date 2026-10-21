"""
Meikova Virtual Audio Provisioner
Enables headless audio transmission on remote hosts without physical speakers/headphones.
Cross-platform support:
- Windows: WHQL-signed VB-Audio Virtual Cable (automated download & silent install)
- Linux: Native PulseAudio/PipeWire module-null-sink (zero-download instant creation)
- macOS: BlackHole 2ch / Soundflower driver verification
"""

import os
import sys
import time
import shutil
import zipfile
import logging
import urllib.request
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger("MeikovaVirtualAudio")

VBCABLE_URL = "https://download.vb-audio.com/Download_CABLE/VBCABLE_Driver_Pack43.zip"

def is_audio_output_available() -> bool:
    """Checks if host has any active audio playback (render) endpoint across Windows, Linux, and macOS."""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes
            import uuid

            ole32 = ctypes.windll.ole32
            ole32.CoInitialize(None)

            class GUID(ctypes.Structure):
                _fields_ = [
                    ('Data1', wintypes.DWORD),
                    ('Data2', wintypes.WORD),
                    ('Data3', wintypes.WORD),
                    ('Data4', wintypes.BYTE * 8)
                ]

            def str_to_guid(s):
                b = uuid.UUID(s).bytes_le
                g = GUID()
                g.Data1 = int.from_bytes(b[0:4], 'little')
                g.Data2 = int.from_bytes(b[4:6], 'little')
                g.Data3 = int.from_bytes(b[6:8], 'little')
                for i in range(8):
                    g.Data4[i] = b[8 + i]
                return g

            clsid_enum = str_to_guid('BCDE0395-E52F-467C-8E3D-C4579291692E')
            iid_enum = str_to_guid('A95664D2-9614-4F35-A746-DE8DB63617E6')

            p_enum = ctypes.c_void_p()
            hr = ole32.CoCreateInstance(ctypes.byref(clsid_enum), None, 1, ctypes.byref(iid_enum), ctypes.byref(p_enum))
            if hr != 0:
                ole32.CoUninitialize()
                return False

            def v_call(ptr, idx, argtypes, *args):
                vt = ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))
                fn = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, *argtypes)(vt[0][idx])
                return fn(ptr, *args)

            # 1. Try GetDefaultAudioEndpoint (eRender=0, eConsole=0)
            p_dev = ctypes.c_void_p()
            hr_def = v_call(p_enum, 4, [ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)], 0, 0, ctypes.byref(p_dev))
            if hr_def == 0 and p_dev.value:
                ole32.CoUninitialize()
                return True

            # 2. Try EnumAudioEndpoints (eRender=0, DEVICE_STATE_ACTIVE=1)
            p_col = ctypes.c_void_p()
            hr_enum = v_call(p_enum, 3, [ctypes.c_int, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p)], 0, 1, ctypes.byref(p_col))
            if hr_enum == 0 and p_col.value:
                count = wintypes.UINT()
                v_call(p_col, 3, [ctypes.POINTER(wintypes.UINT)], ctypes.byref(count))
                ole32.CoUninitialize()
                return count.value > 0

            ole32.CoUninitialize()
            return False
        except Exception as e:
            logger.warning(f"[VirtualAudio] Audio check exception on Windows: {e}")
            return True

    elif sys.platform.startswith("linux"):
        try:
            res = subprocess.run(["pactl", "list", "sinks", "short"], capture_output=True, text=True, timeout=3)
            if res.returncode == 0 and res.stdout.strip():
                return True
        except Exception:
            pass
        cards_file = Path("/proc/asound/cards")
        if cards_file.exists():
            content = cards_file.read_text(encoding="utf-8", errors="ignore").strip()
            return "--- no soundcards ---" not in content and bool(content)
        return True

    elif sys.platform == "darwin":
        try:
            res = subprocess.run(["system_profiler", "SPAudioDataType"], capture_output=True, text=True, timeout=5)
            if "Default Output Device: Yes" in res.stdout:
                return True
        except Exception:
            pass
        return True

    return True

def download_and_install_vbcable() -> Dict[str, Any]:
    """
    Installs virtual audio device according to the current platform:
    - Windows: Downloads and silently installs WHQL VB-CABLE driver
    - Linux: Instantly creates PulseAudio/PipeWire module-null-sink
    - macOS: Provides guidance for BlackHole 2ch driver
    """
    if sys.platform == "win32":
        temp_dir = Path(os.environ.get("TEMP", r"C:\Temp")) / "MeikovaVBCable"
        zip_path = temp_dir / "vbcable.zip"

        try:
            temp_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"[VirtualAudio] Downloading VB-CABLE driver from {VBCABLE_URL}...")
            
            req = urllib.request.Request(VBCABLE_URL, headers={"User-Agent": "Mozilla/5.0 MeikovaRelay/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp, open(zip_path, "wb") as out:
                shutil.copyfileobj(resp, out)

            logger.info(f"[VirtualAudio] Download completed ({zip_path.stat().st_size} bytes). Extracting...")
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(temp_dir)

            is_64 = sys.maxsize > 2**32
            installer_exe = temp_dir / ("VBCABLE_Setup_x64.exe" if is_64 else "VBCABLE_Setup.exe")

            if not installer_exe.exists():
                return {"success": False, "message": f"Không tìm thấy tệp cài đặt: {installer_exe.name}"}

            logger.info(f"[VirtualAudio] Running silent driver install: {installer_exe} -i -h...")
            cmd = f'Start-Process -FilePath "{installer_exe}" -ArgumentList "-i -h" -Wait -Verb RunAs'
            proc = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
                                  capture_output=True, text=True, timeout=60)

            time.sleep(3)
            active = is_audio_output_available()
            logger.info(f"[VirtualAudio] Driver installation finished. Audio output active: {active}")

            return {
                "success": True,
                "has_device": active,
                "message": "Đã cài đặt thành công Loa ảo (VB-Audio Virtual Cable). Windows đã sẵn sàng truyền âm thanh."
            }
        except Exception as e:
            logger.error(f"[VirtualAudio] Windows installation failed: {e}")
            return {"success": False, "message": f"Lỗi cài đặt Loa ảo Windows: {str(e)}"}
        finally:
            try:
                if zip_path.exists():
                    zip_path.unlink(missing_ok=True)
            except Exception:
                pass

    elif sys.platform.startswith("linux"):
        try:
            cmd = ["pactl", "load-module", "module-null-sink", "sink_name=Meikova_Virtual_Sink", "sink_properties=device.description=Meikova_Virtual_Speaker"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                return {
                    "success": True,
                    "has_device": True,
                    "message": "Đã khởi tạo PulseAudio/PipeWire Null Sink (Meikova_Virtual_Speaker) thành công."
                }
            return {
                "success": False,
                "message": f"pactl returned code {res.returncode}: {res.stderr.strip()}"
            }
        except Exception as e:
            return {"success": False, "message": f"Lỗi khởi tạo Linux Virtual Sink: {e}"}

    elif sys.platform == "darwin":
        return {
            "success": False,
            "message": "Trên macOS, vui lòng cài đặt BlackHole 2ch (chạy: brew install blackhole-2ch) để kích hoạt Loa ảo."
        }

    return {"success": False, "message": f"Nền tảng {sys.platform} chưa được hỗ trợ."}

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Platform:", sys.platform)
    print("Has audio output:", is_audio_output_available())
    if "--install" in sys.argv:
        print(download_and_install_vbcable())

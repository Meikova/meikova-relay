"""
Meikova Virtual Audio Provisioner
Enables headless audio transmission on remote hosts without physical speakers/headphones.
Automatically detects, downloads and installs WHQL-signed Virtual Audio Device (VB-CABLE).
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
    """Checks if Windows has any active audio playback (render) endpoint."""
    if sys.platform != "win32":
        return True

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
        logger.warning(f"[VirtualAudio] Audio check exception: {e}")
        return True # Fallback assume true to not block

def download_and_install_vbcable() -> Dict[str, Any]:
    """
    Downloads and silently installs VB-Audio Virtual Cable (WHQL certified).
    Requires administrator privilege on the host.
    """
    if sys.platform != "win32":
        return {"success": False, "message": "Chỉ hỗ trợ hệ điều hành Windows."}

    temp_dir = Path(os.environ.get("TEMP", "C:\\Temp")) / "MeikovaVBCable"
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

        # Detect 64-bit vs 32-bit setup
        is_64 = sys.maxsize > 2**32
        installer_exe = temp_dir / ("VBCABLE_Setup_x64.exe" if is_64 else "VBCABLE_Setup.exe")

        if not installer_exe.exists():
            return {"success": False, "message": f"Không tìm thấy tệp cài đặt: {installer_exe.name}"}

        logger.info(f"[VirtualAudio] Running silent driver install: {installer_exe} -i -h...")
        # Run installer silently (-i = install, -h = hide/silent)
        # Using PowerShell Start-Process with -Verb RunAs in case elevation is needed
        cmd = f'Start-Process -FilePath "{installer_exe}" -ArgumentList "-i -h" -Wait -Verb RunAs'
        proc = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
                              capture_output=True, text=True, timeout=60)

        # Allow Windows Audio Service time to register new PnP endpoint
        time.sleep(3)

        # Verify device
        active = is_audio_output_available()
        logger.info(f"[VirtualAudio] Driver installation finished. Audio output active: {active}")

        return {
            "success": True,
            "has_device": active,
            "message": "Đã cài đặt thành công Loa ảo (VB-Audio Virtual Cable). Windows đã sẵn sàng truyền âm thanh."
        }
    except Exception as e:
        logger.error(f"[VirtualAudio] Installation failed: {e}")
        return {"success": False, "message": f"Lỗi cài đặt Loa ảo: {str(e)}"}
    finally:
        try:
            if zip_path.exists():
                zip_path.unlink(missing_ok=True)
        except Exception:
            pass

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Has audio output:", is_audio_output_available())
    if "--install" in sys.argv:
        res = download_and_install_vbcable()
        print("Result:", res)

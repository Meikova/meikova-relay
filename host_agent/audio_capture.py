import sys
import time
import array
import struct
import logging
import threading
from typing import Callable, Optional

logger = logging.getLogger("TitanAudio")

class AudioCapture:
    """Captures system audio playback loopback via native Windows WASAPI."""

    def __init__(self, on_chunk: Optional[Callable[[bytes, int, int], None]] = None, sample_rate: int = 48000, channels: int = 2):
        self.on_chunk = on_chunk
        self.sample_rate = sample_rate
        self.channels = channels
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.is_wasapi_available = (sys.platform == "win32")

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._capture_thread_main, daemon=True, name="TitanAudioCapture")
        self.thread.start()
        logger.info("[AudioCapture] Started loopback capture thread.")

    def stop(self):
        if not self.running:
            return
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        self.thread = None
        logger.info("[AudioCapture] Stopped loopback capture.")

    def _capture_thread_main(self):
        if not self.is_wasapi_available:
            self._mock_loop()
            return

        try:
            self._wasapi_loop()
        except Exception as e:
            logger.warning(f"[AudioCapture] WASAPI loopback unavailable or failed: {e}. Falling back to mock/silent capture.")
            self._mock_loop()

    def _wasapi_loop(self):
        import ctypes
        from ctypes import wintypes

        ole32 = ctypes.windll.ole32
        ole32.CoInitialize(None)

        class GUID(ctypes.Structure):
            _fields_ = [
                ('Data1', wintypes.DWORD),
                ('Data2', wintypes.WORD),
                ('Data3', wintypes.WORD),
                ('Data4', wintypes.BYTE * 8)
            ]

        def str_to_guid(s: str) -> GUID:
            import uuid
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
        iid_client = str_to_guid('1CB9AD4C-DBFA-4C32-B178-C2F568A703B2')
        iid_capture = str_to_guid('C8ADBD64-E71E-48A0-A4DE-185C395CD317')

        p_enum = ctypes.c_void_p()
        hr = ole32.CoCreateInstance(ctypes.byref(clsid_enum), None, 1, ctypes.byref(iid_enum), ctypes.byref(p_enum))
        if hr != 0:
            ole32.CoUninitialize()
            raise RuntimeError(f"CoCreateInstance failed with hr={hex(hr & 0xffffffff)}")

        def v_call(ptr, idx, argtypes, *args):
            vt = ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))
            fn = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, *argtypes)(vt[0][idx])
            return fn(ptr, *args)

        p_device = ctypes.c_void_p()
        # eRender=0, eConsole=0
        hr = v_call(p_enum, 4, [ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)], 0, 0, ctypes.byref(p_device))
        if hr != 0:
            ole32.CoUninitialize()
            raise RuntimeError(f"GetDefaultAudioEndpoint failed: {hex(hr & 0xffffffff)}")

        p_client = ctypes.c_void_p()
        hr = v_call(p_device, 3, [ctypes.POINTER(GUID), ctypes.c_uint, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)], ctypes.byref(iid_client), 23, None, ctypes.byref(p_client))
        if hr != 0:
            ole32.CoUninitialize()
            raise RuntimeError(f"Activate IAudioClient failed: {hex(hr & 0xffffffff)}")

        pwfx = ctypes.c_void_p()
        v_call(p_client, 8, [ctypes.POINTER(ctypes.c_void_p)], ctypes.byref(pwfx))

        wfx_bytes = ctypes.string_at(pwfx, 18)
        wFormatTag, nChannels, nSamplesPerSec, nAvgBytesPerSec, nBlockAlign, wBitsPerSample = struct.unpack('<HHIIHH', wfx_bytes[:16])
        self.sample_rate = nSamplesPerSec
        self.channels = nChannels
        bytes_per_sample = wBitsPerSample // 8

        # AUDCLNT_SHAREMODE_SHARED=0, AUDCLNT_STREAMFLAGS_LOOPBACK=0x00020000
        # Buffer duration 100ms (1,000,000 in 100ns units)
        hr = v_call(p_client, 3, [ctypes.c_int, ctypes.c_uint, ctypes.c_int64, ctypes.c_int64, ctypes.c_void_p, ctypes.c_void_p], 0, 0x00020000, 1000000, 0, pwfx, None)
        if hr != 0:
            ole32.CoUninitialize()
            raise RuntimeError(f"IAudioClient::Initialize loopback failed: {hex(hr & 0xffffffff)}")

        p_capture = ctypes.c_void_p()
        hr = v_call(p_client, 14, [ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)], ctypes.byref(iid_capture), ctypes.byref(p_capture))
        if hr != 0:
            ole32.CoUninitialize()
            raise RuntimeError(f"IAudioClient::GetService capture failed: {hex(hr & 0xffffffff)}")

        # Start capture
        v_call(p_client, 10, [])
        logger.info(f"[AudioCapture] WASAPI loopback active: {self.channels} channels @ {self.sample_rate}Hz ({wBitsPerSample}-bit)")

        p_data = ctypes.c_void_p()
        num_frames = wintypes.UINT()
        flags = wintypes.DWORD()
        pos = ctypes.c_uint64()
        qpc = ctypes.c_uint64()

        try:
            while self.running:
                packet_size = wintypes.UINT()
                hr = v_call(p_capture, 5, [ctypes.POINTER(wintypes.UINT)], ctypes.byref(packet_size))
                if hr == 0 and packet_size.value > 0:
                    hr = v_call(
                        p_capture, 3,
                        [ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.UINT), ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint64)],
                        ctypes.byref(p_data), ctypes.byref(num_frames), ctypes.byref(flags), ctypes.byref(pos), ctypes.byref(qpc)
                    )
                    if hr == 0 and num_frames.value > 0:
                        is_silent = bool(flags.value & 2) or (not p_data.value)
                        if is_silent:
                            out_bytes = b'\x00' * (num_frames.value * self.channels * 2)
                        else:
                            raw_floats = ctypes.string_at(p_data.value, num_frames.value * nBlockAlign)
                            if wBitsPerSample == 32:
                                in_array = array.array('f')
                                in_array.frombytes(raw_floats)
                                # Convert float32 [-1.0, 1.0] to 16-bit PCM
                                pcm16 = array.array('h', (int(max(-1.0, min(1.0, x)) * 32767) for x in in_array))
                                out_bytes = pcm16.tobytes()
                            else:
                                out_bytes = raw_floats

                        if self.on_chunk and out_bytes:
                            self.on_chunk(out_bytes, self.sample_rate, self.channels)

                        v_call(p_capture, 4, [wintypes.UINT], num_frames.value)
                else:
                    time.sleep(0.015)
        finally:
            v_call(p_client, 11, []) # Stop
            ole32.CoUninitialize()

    def _mock_loop(self):
        """Generates silent PCM chunks for automated test suites or unsupported platforms."""
        logger.info("[AudioCapture] Running in mock/fallback mode.")
        chunk_frames = int(self.sample_rate * 0.04) # 40ms
        silent_chunk = b'\x00' * (chunk_frames * self.channels * 2)
        while self.running:
            if self.on_chunk:
                self.on_chunk(silent_chunk, self.sample_rate, self.channels)
            time.sleep(0.04)

import os
import sys
import time
import queue
import threading
from typing import Optional

# WinMM ctypes structures
if os.name == 'nt':
    import ctypes
    from ctypes import wintypes

    winmm = ctypes.windll.winmm

    class WAVEFORMATEX(ctypes.Structure):
        _fields_ = [
            ("wFormatTag", wintypes.WORD),
            ("nChannels", wintypes.WORD),
            ("nSamplesPerSec", wintypes.DWORD),
            ("nAvgBytesPerSec", wintypes.DWORD),
            ("nBlockAlign", wintypes.WORD),
            ("wBitsPerSample", wintypes.WORD),
            ("cbSize", wintypes.WORD),
        ]

    class WAVEHDR(ctypes.Structure):
        pass

    WAVEHDR._fields_ = [
        ("lpData", ctypes.POINTER(ctypes.c_char)),
        ("dwBufferLength", wintypes.DWORD),
        ("dwBytesRecorded", wintypes.DWORD),
        ("dwUser", ctypes.c_size_t),
        ("dwFlags", wintypes.DWORD),
        ("dwLoops", wintypes.DWORD),
        ("lpNext", ctypes.POINTER(WAVEHDR)),
        ("reserved", ctypes.c_size_t),
    ]

    WHDR_DONE = 1
    MMSYSERR_NOERROR = 0


class AudioPlayback:
    """Plays client voice PCM audio stream to host speakers via native Windows waveOut."""

    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels
        self.queue: queue.Queue[bytes] = queue.Queue(maxsize=100)
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.is_available = (os.name == 'nt')
        self._hWaveOut = None

    def start(self, sample_rate: Optional[int] = None, channels: Optional[int] = None):
        if self.running:
            return
        if sample_rate:
            self.sample_rate = sample_rate
        if channels:
            self.channels = channels

        self.running = True
        self.thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.thread.start()

    def play_chunk(self, pcm_bytes: bytes):
        if not self.running or not pcm_bytes:
            return
        try:
            self.queue.put_nowait(pcm_bytes)
        except queue.Full:
            try:
                self.queue.get_nowait()
                self.queue.put_nowait(pcm_bytes)
            except Exception:
                pass

    def _worker_loop(self):
        if not self.is_available:
            while self.running:
                try:
                    self.queue.get(timeout=0.05)
                except queue.Empty:
                    pass
            return

        wfx = WAVEFORMATEX(
            1, # WAVE_FORMAT_PCM
            self.channels,
            self.sample_rate,
            self.sample_rate * self.channels * 2,
            self.channels * 2,
            16,
            0
        )
        hWaveOut = wintypes.HANDLE()
        res = winmm.waveOutOpen(ctypes.byref(hWaveOut), -1, ctypes.byref(wfx), 0, 0, 0)
        if res != MMSYSERR_NOERROR:
            self.running = False
            return

        self._hWaveOut = hWaveOut
        active_headers = []

        try:
            while self.running:
                # 1. Reclaim finished wave headers
                still_active = []
                for buf, hdr in active_headers:
                    if hdr.dwFlags & WHDR_DONE:
                        winmm.waveOutUnprepareHeader(hWaveOut, ctypes.byref(hdr), ctypes.sizeof(WAVEHDR))
                    else:
                        still_active.append((buf, hdr))
                active_headers = still_active

                # 2. Get next PCM chunk
                try:
                    chunk = self.queue.get(timeout=0.02)
                except queue.Empty:
                    continue

                if not chunk:
                    continue

                buf = ctypes.create_string_buffer(chunk)
                hdr = WAVEHDR()
                hdr.lpData = ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))
                hdr.dwBufferLength = len(chunk)
                hdr.dwFlags = 0

                prep_res = winmm.waveOutPrepareHeader(hWaveOut, ctypes.byref(hdr), ctypes.sizeof(WAVEHDR))
                if prep_res == MMSYSERR_NOERROR:
                    write_res = winmm.waveOutWrite(hWaveOut, ctypes.byref(hdr), ctypes.sizeof(WAVEHDR))
                    if write_res == MMSYSERR_NOERROR:
                        active_headers.append((buf, hdr))
                    else:
                        winmm.waveOutUnprepareHeader(hWaveOut, ctypes.byref(hdr), ctypes.sizeof(WAVEHDR))
        finally:
            try:
                winmm.waveOutReset(hWaveOut)
                for buf, hdr in active_headers:
                    winmm.waveOutUnprepareHeader(hWaveOut, ctypes.byref(hdr), ctypes.sizeof(WAVEHDR))
                winmm.waveOutClose(hWaveOut)
            except Exception:
                pass
            self._hWaveOut = None

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=0.5)
        self.thread = None
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except Exception:
                break

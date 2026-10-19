import sys
import time
from pathlib import Path

# Ensure host_agent is in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from host_agent.screen_capture import ScreenCapture
from host_agent.input_injector import InputInjector

def main():
    print("--- Starting Remote Desktop Self-Test ---")
    cap = ScreenCapture(quality=60)
    w, h = cap.resolution
    print(f"[OK] Detected Screen Resolution: {w}x{h}")
    assert w > 0 and h > 0, "Resolution must be greater than 0"

    print("Testing Screen Capture...")
    times = []
    total_bytes = 0
    for i in range(5):
        t0 = time.perf_counter()
        frame = cap.capture_frame(force=True)
        dt = (time.perf_counter() - t0) * 1000.0
        times.append(dt)
        if frame:
            total_bytes += len(frame)
            # Check JPEG magic bytes: 0xFF, 0xD8
            assert frame[:2] == b'\xff\xd8', "Frame is not a valid JPEG"
        else:
            print(f"Warning: Frame {i} was None")

    avg_dt = sum(times) / len(times)
    avg_size_kb = (total_bytes / len(times)) / 1024.0
    print(f"[OK] Average Capture Time: {avg_dt:.2f} ms")
    print(f"[OK] Average JPEG Frame Size: {avg_size_kb:.1f} KB")

    print("Testing Input Injector (Mouse Move & Query)...")
    # Move mouse slightly to center-screen
    res = InputInjector.mouse_move(0.5, 0.5)
    print(f"[OK] Mouse Move API return code: {res}")
    assert res, "mouse_move should return True on Windows"

    print("--- ALL SELF-TESTS PASSED SUCCESSFULLY ---")

if __name__ == "__main__":
    main()

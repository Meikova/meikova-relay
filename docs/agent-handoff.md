# Meikova Relay - Session Handoff (v1.0.70)

## Mục tiêu hoàn thành
1. **Khắc phục triệt để rò rỉ bộ nhớ & GDI handle gây đơ lag máy tính (MeikovaRelayHost.exe)**:
   - **Hiện tượng**: `MeikovaRelayHost.exe` ngốn tới **27.58 GB RAM ảo (Commit)**, **37,586 handles**, chạm kịch trần **10,000 GDI objects** (`GDIProcessHandleQuota`). Hệ thống Windows bị dồn sang SSD đẩy `pagefile.sys` lên 50 GB gây nghẽn bộ nhớ ảo (Paging Thrashing), làm tụt FPS từ 60 FPS xuống 1 FPS và RTT tăng vọt lên 508ms.
   - **4 Nguyên nhân gốc rễ và giải pháp triệt để**:
     1. `host_agent/cursor_manager.py`: Vòng lặp 50ms (20 Hz) gọi `user32.OpenInputDesktop(0, False, 0x01FF)` khi màn hình khóa hoặc truy vấn con trỏ lỗi mà không hề gọi `user32.CloseDesktop(old_h)` (rò rỉ 72,000 handles/giờ). Khắc phục: Quản lý vòng đời handle desktop, đóng handle cũ bằng `CloseDesktop` khi chuyển desktop, đồng thời backoff 500ms khi truy vấn con trỏ liên tục thất bại.
     2. `host_agent/screen_capture.py`: Trong `NativeWin32Capture`, `CreateDIBSection` tạo bitmap được chọn vào DC bằng `SelectObject(mem_dc, hBmp)`. Khi đổi kích thước hoặc đóng, gọi `DeleteObject(hBmp)`. Theo Win32 GDI spec, `DeleteObject` trả về `FALSE` nếu bitmap đang được chọn trong DC! DIBSection 8.3 MB bị kẹt vĩnh viễn trong kernel GDI table, tích lũy tới kịch trần 10,000 objects. Khắc phục: Lưu `self.old_hBmp`, gọi `SelectObject(mem_dc, old_hBmp)` unselect trước khi `DeleteObject(hBmp)`, giải phóng sạch `ReleaseDC(0, src_dc)`.
     3. `host_agent/gui_agent.py`: `_eval_js()` tạo một `threading.Thread` mới cho từng log và sự kiện (hàng vạn thread qua 24h). Khắc phục: Dùng 1 daemon worker thread duy nhất với `queue.Queue(maxsize=100)` chặn tràn bộ đệm. Thêm cờ `_interactive_desktop_attached` chỉ chạy 1 lần trong `ensure_interactive_desktop()`.
     4. `host_agent/gui_view.html`: Hàm `addLog()` chèn vô hạn `div.log-line` làm WebView2 phình to DOM tree. Khắc phục: Bổ sung ring-buffer giới hạn tối đa 100 dòng log (`while (box.children.length > 100) box.removeChild(box.firstChild)`).
   - **Biên dịch & Triển khai thực tế**:
     * Biên dịch sạch lại `MeikovaRelayHost.exe` bằng PyInstaller (Python 3.12).
     * Triển khai tệp thực thi mới (31.4 MB) vào `%LOCALAPPDATA%\MeikovaRelayHost\MeikovaRelayHost.exe`.
     * **Kết quả đo lường thực tế sau khi sửa**:
       - RAM Commit: **88.6 MB** (giảm từ **26,299 MB** -> giảm **99.6%**).
       - Handles: **106 / 825** (giảm từ **37,586**).
       - GDI Objects: **0 / 102** (giảm từ **10,000** - không còn chạm quota).
       - Khung hình capture: Trở lại mượt mà 30 - 60 FPS, RTT dưới 30ms.

2. **Triệt tiêu hoàn toàn khoảng trống đáy trang trên iPhone PWA (v1.0.70)**:
   - **Hiện tượng**: Trên mobile web (Safari browser tab) hiển thị 48px sát chân rất đẹp, nhưng khi thêm vào màn hình chính dạng PWA Standalone (`display-mode: standalone`), chân trang bị thừa một khoảng đen trống hoác lớn phía dưới các nút điều hướng.
   - **Nguyên nhân gốc rễ**:
     1. Trên Safari Mobile Web, `env(safe-area-inset-bottom)` bằng 0px nên thanh nav bar cao đúng 48px, các nút phủ kín thanh, không có khoảng trống.
     2. Khi cài vào màn hình chính dạng PWA Standalone, `env(safe-area-inset-bottom)` trên iPhone tự động kích hoạt 34px. CSS cũ đưa trực tiếp `34px` này vào `padding-bottom` và cộng vào `height: calc(48px + 34px) = 82px`, đồng thời đẩy `.stage` lên cao thêm 34px. Hậu quả là gần một nửa thanh điều hướng (34px / 82px) trở thành một dải đen chết vô dụng dưới đáy.
     3. Kèm theo lỗi `position: fixed` cũ trên `html, body` làm WebKit co ngắn viewport khiến khoảng hở bị nhân đôi lên tới 74pt.
   - **Giải pháp triệt để**:
     1. Khóa chuẩn chiều cao bottom nav mobile: `--bottom-nav-h: 48px; --bottom-nav-total-h: var(--bottom-nav-h);`.
     2. `#mainNav`: `height: 48px !important; padding: 2px !important; align-items: center !important; bottom: 0 !important;`. Toàn bộ 7 nút tab cao 44px nằm căn giữa đều đặn, phủ kín thanh nav bar, sát mép kính dưới cùng. Không có bất kỳ khoảng đệm đen dư thừa nào.
     3. `.stage`: Khóa tiếp giáp liền khối tại `bottom: 48px !important; width: 100% !important;`, triệt tiêu hoàn toàn khe hở giữa màn hình nội dung và thanh điều hướng.
     4. Thêm logic tự động xóa CacheStorage cũ (`meikova_pwa_ver !== '1.0.70'`) ngay khi app khởi chạy để loại bỏ nguy cơ kẹt cache PWA trên iOS.
     5. Cập nhật `sw.js` và query string toàn bộ asset lên `v1.0.70`.

## Trạng thái kiểm chứng (Verification)
- **Selenium Headless Mobile Emulation (iPhone 14 - 390x844)**:
  * `mainNav` bounding rect: `x=0, y=796, w=390, h=48` (Gap below nav: **0px**).
  * Standalone Mode: `Gap below nav: 0px`.
  * Đủ 7 tab buttons: `landing`, `dashboard`, `remote`, `files`, `terminal`, `tasks`, `audit` (`displayed=True`, `w=55, h=44`).
- **Python Unit Test Suite**:
  * `tests/test_leak_regression.py`: **4/4 tests PASS (OK, Exit Code 0)**.
  * `tests/test_tcp_tunnel.py`: **4/4 tests PASS (OK, Exit Code 0)**.
  * `tests/test_screen_sync.py`: **9/9 tests PASS (OK, Exit Code 0)**.
  * `tests/test_pwa_manifest.py`: **1/1 test PASS (OK, Exit Code 0)**.
  * `tests/test_i18n.py`: **6/6 tests PASS (OK, Exit Code 0)**.
  * Tổng cộng: **24/24 tests PASS (100% Exit Code 0)**.

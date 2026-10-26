# Meikova Relay - Session Handoff (v1.0.72)

## Mục tiêu hoàn thành
1. **Khắc phục lỗi chạy ra phiên bản/phòng cũ khi chạy lệnh cài đặt `setup.bat` (v1.0.72)**:
   - **Hiện tượng**:
     * Người dùng chạy lệnh tải và cài đặt qua `setup.bat` nhưng giao diện máy trạm vẫn hiển thị phiên bản/phiên làm việc cũ (Room ID `RD-1815`).
   - **Phân tích nguyên nhân gốc rễ**:
     1. **Xung đột Mutex & `setup.bat` không dọn dẹp tiến trình Python nền**:
        * Khi tiến trình cũ được chạy dưới dạng `python -m host_agent.gui_agent --gui` hoặc `pythonw.exe`, lệnh `taskkill /f /im MeikovaRelayHost.exe` trong `setup.bat` cũ **không thể tắt được `python.exe`/`pythonw.exe`**.
        * Tiến trình cũ tiếp tục giữ Win32 Named Mutex `MeikovaRelayHost_AppMutex`.
        * Khi `setup.bat` tạo cấu hình mới và khởi chạy `MeikovaRelayHost.exe`, cơ chế `SingleInstanceLock` phát hiện Mutex đang bị chiếm dụng nên gửi lệnh IPC `SHOW` đến tiến trình cũ và tự thoát ngay lập tức.
        * Tiến trình cũ (Room `RD-1815`) được đẩy lên màn hình trước mặt người dùng, khiến người dùng thấy cấu hình cũ không hề thay đổi.
     2. **Thiếu cờ `--collect-all webview` trong PyInstaller packaging**:
        * `scripts/build.py` trước đây chưa khai báo `--collect-all webview` và các module nền tảng `webview.platforms.winforms`, `clr`, `pythonnet`.
        * Bổ sung bắt lỗi và ghi nhật ký chi tiết vào `%LOCALAPPDATA%\MeikovaRelayHost\gui.log` thay vì fallback âm thầm.
     3. **Thiếu hiển thị nhãn Version trên thanh tiêu đề Host**:
        * Giao diện `gui_view.html` trước đây không có nhãn phiên bản trực quan khiến người dùng không phân biệt được bản đang chạy.
   - **Giải pháp kỹ thuật triệt để**:
     1. **Nâng cấp kịch bản cài đặt `setup.bat`**:
        * Dùng PowerShell để quét và dừng cưỡng bức cả `MeikovaRelayHost.exe` lẫn mọi tiến trình Python đang thực thi `gui_agent.py`.
        * Dùng `Move-Item -Force` để ghi đè tệp nhị phân an toàn.
        * Bổ sung cờ `--restart` khi khởi động để tự động đóng phiên cũ nếu còn sót lại.
     2. **Đóng gói PyInstaller hoàn chỉnh**:
        * Thêm `--collect-all webview`, `--hidden-import webview.platforms.winforms`, `clr`, `pythonnet` vào `scripts/build.py`.
        * Biên dịch lại `MeikovaRelayHost.exe` (31.8 MB), kiểm chứng tải thành công giao diện Ambient Dark PyWebView.
     3. **Hiển thị huy hiệu phiên bản trên Host Titlebar**:
        * Thêm thẻ `.host-version-pill` (`v1.0.72`) phát quang Cyan ngay cạnh tiêu đề ứng dụng.
        * Truyền `version` qua `api.get_initial_data()` để tự động đồng bộ.
     4. **Nâng cấp phiên bản toàn hệ thống**:
        * Bump phiên bản `1.0.72` across `package.json`, `sw.js`, `index.html`, `gui_agent.py`, `gui_view.html`.
        * Đóng gói lại `MeikovaRelayHost.exe` và `agent-package.zip`.

## Trạng thái kiểm chứng (Verification)
- **Kiểm chứng thực thi Native Standalone (`scratch/find_win.ps1`)**:
  * Chạy `MeikovaRelayHost.exe --gui --restart`: Cửa sổ `Meikova Relay Host` (PyWebView Ambient Dark) xuất hiện `Visible: True`. Không bị rơi vào Tkinter fallback.
- **Toàn bộ Test Suite Cốt lõi**:
  * 100% test cases trong `tests/` vượt qua (**PASS, Exit Code 0**).

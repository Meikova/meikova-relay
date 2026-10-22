# Session Handoff: Meikova Relay - Chuẩn Hóa Vị Trí Log/Config, Xóa Sạch Vết Titan & Đồng Bộ Tray Icon Brand Squircle Nền Đen Phát Quang

## 1. Mục tiêu hoàn thành
- [x] **Gom toàn bộ file Log & Config vào thư mục riêng của dự án, chống xả rác ra Profile người dùng:**
  - Tạo hàm SSOT `get_app_data_dir()` trong `host_agent/gui_agent.py`: Trả về `%LOCALAPPDATA%\MeikovaRelayHost` trên Windows và `~/.meikova-relay` trên Linux/macOS.
  - Chuyển `tray.log` và `crash.log` vào `get_app_data_dir()`.
  - Cập nhật `resolve_config_path()` để ưu tiên ghi và đọc tại `get_app_data_dir() / "config.json"`. Giữ cơ chế fallback tương thích ngược chỉ đọc.
  - Trong `relay-server/server.js`: Xóa bỏ dòng lệnh `setup.bat` copy file ra `%USERPROFILE%\.meikova_relay_config.json`.
  - Dọn dẹp sạch toàn bộ file rác khỏi thư mục người dùng `C:\Users\kiemp\`: `.titan_tray.log`, `.meikova_relay_tray.log`, `.meikova_relay_config.json`.
- [x] **Rà soát và xóa sạch 100% tàn dư định danh cũ `"titan"`:**
  - Xóa bỏ database cũ `relay-server/titan_remote.db` và `titan_remote.db-journal`.
  - Xóa bỏ các artifact cũ `dist/TitanRemote*` và `build/TitanRemote*`.
  - Cập nhật `host_agent/deployment_manager.py` chuẩn hóa thư mục `.meikova-relay`.
- [x] **Sửa triệt để lỗi System Tray Icon bị trắng/mờ trên Windows Light Taskbar:**
  - **Nguyên nhân gốc rễ:** File `tray_icon.png` cũ chứa biểu tượng trắng thuần `(255, 255, 255, 255)` trên nền trong suốt. Khi Windows chạy chế độ Light Mode (thanh tác vụ và popup thông báo màu trắng/xám sáng), icon bị chìm màu trắng-trên-trắng hoàn toàn. Đồng thời bản `MeikovaRelayHost.exe` trên máy trạm là bản cũ đóng gói trước khi đổi asset.
  - **Khắc phục:**
    1. Cập nhật `get_tray_icon_image()` trong `host_agent/gui_agent.py`: Luôn luôn sinh và nạp chuẩn **Brand Squircle** nền tối `#11151B` kết hợp biểu tượng Duplex Bridge phát quang xanh ngọc `#83E8AC`.
    2. Bổ sung vector renderer nội tại (self-contained PIL procedural) trực tiếp trong `gui_agent.py` để bảo đảm ngay cả khi thiếu file ảnh bên ngoài hoặc lỗi import, icon khay hệ thống vẫn luôn render đúng chuẩn Brand Squircle, không bao giờ rơi vào fallback trắng/trống.
    3. Cập nhật `scripts/build.py`: Cho phép `build_agent_package_zip` đóng gói đệ quy toàn bộ thư mục `tray_icons` chứa đầy đủ asset.
    4. Sao chép trực tiếp bộ icon chuẩn (`tray_icon.png`, `icon.png`, `icon.ico`, `tray_icons`) vào thư mục máy trạm `%LOCALAPPDATA%\MeikovaRelayHost\`.
    5. Build lại file thực thi độc lập `MeikovaRelayHost.exe` mới nhất bằng PyInstaller và cập nhật vào `dist/` lẫn `%LOCALAPPDATA%\MeikovaRelayHost\`.
- [x] **Rà soát 3 dự án còn lại (`meikova-loop`, `meikova-harvest`, `meikova-auth`):**
  - `meikova-loop`: Sử dụng chuẩn `%LOCALAPPDATA%\MeikovaLoop\data`, khay hệ thống nạp chuẩn Brand Squircle cam hổ phách `#FFB38A` trên nền `#11151B`. Không xả rác ra Profile root.
  - `meikova-harvest`: Sử dụng chuẩn `%LOCALAPPDATA%`, khay hệ thống nạp chuẩn Brand Squircle cyan `#83C4FF` trên nền `#11151B`. Không xả rác ra Profile root.
  - `meikova-auth`: Gateway xác thực chạy độc lập, 22/22 bài test Ed25519 SSO vượt qua với Exit Code 0.

- [x] **Nâng cấp Cửa Sổ Chat Host Đạt Chuẩn Frameless Ambient Dark & Khắc Phục Lỗi Nhắn Tin 1 Chiều:**
  - **Khắc phục lỗi thanh trắng OS & icon lông vũ Tkinter default:**
    1. Thiết lập `self.root.overrideredirect(True)` loại bỏ hoàn toàn viền và thanh tiêu đề trắng nguyên mẫu của hệ điều hành.
    2. Bao bọc toàn bộ cửa sổ bằng khung đơn viền hairline 1px `#1E293B`, màu nền tối `#070D17`.
    3. Tự dựng custom titlebar 36px Ambient Dark `#0D1524`: Logo Brand Squircle `black-16.png`, LED xanh ngọc `●`, nhãn tiêu đề `TRÒ CHUYỆN TRỰC TIẾP` (Segoe UI 9 bold `#F8FAFC`), phụ đề `// KỸ THUẬT VIÊN` (`#64748B`), bộ nút điều khiển `—` (thu nhỏ vào tray) và `✕` (đóng vào tray, hover nền đỏ `#EF4444`).
    4. Tích hợp cơ chế kéo thả mượt mà qua toạ độ màn hình (`x_root`, `y_root`) không bị giật lag.
  - **Khắc phục lỗi nhắn tin 1 chiều (thiếu khung input gõ chữ):**
    1. Đảo thứ tự layout packing: Đóng gói khung input xuống đáy cửa sổ trước (`side=tk.BOTTOM, fill=tk.X`) trước khi pack `history_frame`, đảm bảo khung nhập tin nhắn luôn luôn hiển thị 100% ở đáy màn hình, không bao giờ bị khung lịch sử đè mất.
    2. Thiết kế thanh input chuẩn Meikova: Khung `tk.Entry` bo viền `#1E293B`, focus glow `#22C55E`, hỗ trợ placeholder "Nhập tin nhắn gửi kỹ thuật viên...", nút `GỬI` (accent `#22C55E`, active `#16A34A`, hover `#4ADE80`), bắt sự kiện phím `Enter` và click chuột.
    3. Đảm bảo luồng gửi hai chiều: Lưu tin nhắn gửi đi vào `self.history`, đẩy qua WebSocket tới kỹ thuật viên, đồng thời đồng bộ hai chiều trực tiếp với ngăn kéo chat trên giao diện chính (WebView drawer).
  - **Đóng gói và đồng bộ:** Rebuild `MeikovaRelayHost.exe` mới (23.98 MB) và cập nhật trực tiếp vào `%LOCALAPPDATA%\MeikovaRelayHost\MeikovaRelayHost.exe`.

## 2. Lệnh kiểm tra đã chạy & Exit Code
- `python -m unittest tests/test_host_chat.py`: **Exit Code 0** (5/5 tests pass)
- `python -m unittest discover tests`: **Exit Code 0** (131/131 tests pass trong 60.0s, 1 skipped)
- `python scripts/build.py --target windows`: **Exit Code 0** (Tạo mới `dist/MeikovaRelayHost.exe` 23.98 MB)

## 3. Các phần còn tồn đọng và cảnh báo kỹ thuật
- Không còn bất kỳ file rác nào xả ra `C:\Users\kiemp\` (User Profile Root).
- Khay hệ thống của toàn bộ 3 desktop client (Relay, Loop, Harvest) đã đồng nhất 100% theo chuẩn Brand Squircle nền tối `#11151B`, hiển thị tương phản hoàn hảo trên cả Dark/Light OS taskbars.

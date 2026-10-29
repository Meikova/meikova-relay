# TÀI LIỆU BÀN GIAO KỸ THUẬT & VẬN HÀNH HỆ THỐNG MEIKOVA RELAY — ENTERPRISE EDITION (v3.0 / Host v1.4.0)

**Phiên bản bàn giao:** v3.0 Enterprise (Host Agent v1.4.0)  
**Nền tảng hỗ trợ:** Windows 10/11, macOS (Intel & Apple Silicon), Linux (X11/Wayland, Ubuntu/Debian/Fedora/Arch), iOS/iPadOS & Android Web/PWA  
**Trạng thái kiểm thử QA:** 231/231 Kịch bản kiểm thử tự động PASS (100% OK, 0 Warnings, 0 Errors)

## 1. Tổng Quan Kiến Trúc Hệ Thống & Cây Thư Mục Chuẩn Hóa

Meikova Relay Enterprise v3.0 được thiết kế theo kiến trúc 3 tầng hiệu năng cao (Three-Tier Ultra-Low-Latency Streaming & Fleet Orchestration), tách biệt hoàn toàn giữa luồng truyền khung hình nhị phân tốc độ cao (WebSocket Binary Frames + 4-byte `MKR0` Micro-Frame Pacing) và luồng điều khiển trạng thái JSON/REST.

### Cấu trúc thư mục dự án

- `host_agent/`: Dịch vụ máy trạm đa nền tảng (`host_service.py`, `screen_capture.py`, `gui_agent.py`, `gui_view.html`, `tray_menu.py`, `auto_bootstrap.py`, `protocol_prober.py`, `tcp_tunnel.py`, `file_manager.py`, `clipboard_manager.py`, `cursor_manager.py`, `terminal_manager.py`, `virtual_display.py`, `virtual_audio.py`).
- `host_agent/engines/`: Động cơ Hệ điều hành 10 phân hệ (`base_engine.py`, `windows_engine.py`, `macos_engine.py`, `linux_engine.py`) gom toàn bộ lệnh đặc thù của Windows, macOS và Linux về một chuẩn thống nhất.
- `vendor/`: Thư mục tự chủ thư viện (`vendor/packages/turbojpeg.py`, `vendor/packages/pyperclip.py`, `vendor/wheels/`, `vendor/native/`) cho phép chạy trực tiếp từ mã nguồn hoặc cài đặt Offline 100%.
- `setup_dependencies.py`: Công cụ tự động kiểm tra, cài đặt ngầm và nhúng thư viện vào mã nguồn (`--check`, `--embed-source`, `--download-wheels`).
- `relay-server/` & `web-client/`: Máy chủ điều phối Node.js + SQLite WAL (`server.js`) và giao diện điều khiển Web Client chuẩn Ambient Dark Instrument (`index.html`, `css/style.css`, `js/app.js`, `js/i18n.js`).
- `scripts/build.py`: Hệ thống đóng gói bộ cài độc lập cho Windows (`.exe`, `.zip`), Linux (`.deb`, `.tar.gz`) và macOS (`.app`, `.tar.gz`).
- `tests/`: Bộ 231 bài kiểm thử tự động toàn diện (`test_20_point_upgrade.py`, `test_i18n.py`, `test_full_system_e2e.py`, `test_relay_standardization.py`, `test_topology_architect.py`, ...).

## 2. Kiến Trúc Động Cơ Hệ Điều Hành 10 Phân Hệ (OS Engine Architecture)

Toàn bộ các tác vụ phụ thuộc hệ điều hành được cô lập hoàn toàn trong gói `host_agent/engines/` thông qua lớp cơ sở `BaseOSEngine` và 3 lớp thực thi chuyên biệt (`WindowsEngine`, `MacOSEngine`, `LinuxEngine`), giúp dễ dàng bảo trì và mở rộng trên cả 3 nền tảng:

1. **Runtime, Định danh & Quyền hạn (`initialize_runtime`, `get_os_display_name`, `get_machine_id`, `is_admin`, `elevate_and_execute`)**: Bật độ phân giải bộ định thời `1ms` (`timeBeginPeriod(1)`) và Per-Monitor DPI v2 trên Windows; đọc `MachineGuid` / `IOPlatformUUID` / `/etc/machine-id`; nâng quyền đồ họa qua UAC `runas`, AppleScript `with administrator privileges` hoặc `pkexec` (bảo toàn `DISPLAY` và `XAUTHORITY` trên Linux).
2. **Chụp màn hình & Đa màn hình (`detect_monitors`, `grab_frame_raw`, `get_turbojpeg_candidates`)**: Chụp màn hình zero-copy qua Win32 `DIBSection` (`SRCCOPY`) / `dxcam` DXGI trên Windows, `Quartz.CGWindowListCreateImage` trên macOS, và `mss` XShm / `import` trên Linux.
3. **Shell Tương tác, Macro & Phím tắt (`get_shell_command`, `execute_quick_macro`, `get_paste_vk_combo`)**: Khởi tạo PowerShell UTF-8 trên Windows, `/bin/zsh` trên macOS, `/bin/bash` trên Linux; tự động chuyển đổi tổ hợp dán `Ctrl+V` (`0x11, 0x56`) và `Cmd+V` (`0x5B, 0x56`).
4. **Quản trị Nguồn, Chống ngủ & Hẹn giờ bật máy (`lock_workstation`, `restart_machine`, `shutdown_machine`, `prevent_sleep`, `configure_auto_wakeup`)**: Điều khiển khóa màn hình, tắt/khởi động lại, chống tắt màn hình (`SetThreadExecutionState` / `caffeinate` / `xset`) và đánh thức phần cứng RTC (`WakeToRun` / `pmset` / `rtcwake`).
5. **Telemetry Phần cứng & Tiến trình (`get_ram_telemetry`, `get_disk_telemetry`, `get_process_list`, `kill_process`)**: Truy vấn thông số RAM, dung lượng ổ đĩa và danh sách tiến trình tiêu thụ bộ nhớ theo thời gian thực.
6. **Dịch vụ Nền 24/7 & Tự khởi động (`is_autostart_enabled`, `set_autostart`, `is_service_installed`, `manage_service`)**: Quản lý tự khởi động cùng OS và đăng ký dịch vụ chạy ngầm 24/7 (`Windows Service`, `LaunchDaemons`, `systemd`).
7. **Quản lý Cửa sổ, Dark Titlebar & Khay hệ thống (`get_ui_fonts`, `apply_window_theme`, `activate_window`, `configure_tray_environment`, `patch_tray_backend`)**: Đồng bộ thanh tiêu đề tối (DWM Dark Mode / GTK Dark Variant), kích hoạt cửa sổ chính và hiển thị menu chuột phải nền tối trên khay hệ thống (System Tray) của cả Windows, macOS và Linux (`AppIndicator` / `Xorg`).
8. **Đồng bộ Con trỏ chuột & Clipboard (`get_cursor_shape`, `get_clipboard_text`, `set_clipboard_text`)**: Nhận diện hình dáng con trỏ chuột thực tế (`GetCursorInfo` trên Windows, `NSCursor` trên macOS, `libXfixes` trên Linux) và đồng bộ Clipboard 2 chiều.
9. **Nhận diện Headless & Màn hình ảo (`is_headless_display`, `get_virtual_display_status`)**: Tự động phát hiện máy trạm không gắn màn hình vật lý và quản lý driver màn hình ảo (`IddCx`, `BetterDisplay`, `Xvfb`).
10. **Thiết bị Âm thanh & Loa ảo (`is_audio_output_available`)**: Kiểm tra thiết bị phát âm thanh hoạt động (COM `IMMDeviceEnumerator`, `CoreAudio`, `PulseAudio`/`PipeWire`) và hỗ trợ cài đặt cáp âm thanh ảo (`VB-CABLE` / `module-null-sink`).

## 3. Công Nghệ Truyền Tải Ultra-FPS (1.000+ FPS) & Bộ Điều Nhịp QPC Trên FHD / 2K / 4K

Hệ thống truyền tải hình ảnh được tối ưu hóa cho cả màn hình chuẩn FHD (1080p) lẫn màn hình độ phân giải cao 2K (1440p) và 4K (2160p):

- **Băm lưới siêu tốc (`_compute_fast_hash` 64x64) & Tín hiệu `MKR0` (4-byte)**: Khi màn hình đứng yên hoặc giữa các chu kỳ làm tươi của màn hình vật lý, `screen_capture.py` kiểm tra 4.096 điểm mẫu toàn khung hình trong `~0.05ms`. Nếu pixel không đổi, Host trả về vùng nhớ đệm và phát gói tín hiệu `MKR0` dài đúng 4 byte, giúp đạt trên **1.000+ FPS ở chế độ MAX** với băng thông chỉ `~4 KB/s` và tải CPU `< 2%`.
- **Bộ định thời QPC độ chính xác cao (`time.perf_counter()`) & QPC Catch-Up Ticks**: Khắc phục hoàn toàn giới hạn độ trễ `15.6ms` của bộ hẹn giờ mặc định trên Windows 11. Khi nén một khung hình 2K/4K lớn mất nhiều hơn 1 chu kỳ khung hình, vòng lặp `_send_frames_worker` tự động phát bù các xung nhịp `MKR0` đã trôi qua, đảm bảo tốc độ khung hình luôn bám sát chính xác các mốc giới hạn **30, 60, 90, 120, 144, 165, 240 và 360 FPS**.
- **3 Chế độ Điều nhịp Luồng (Frame Pacing Modes)**:
  - **Adaptive VFR (`adaptive_vfr`)**: Tự động cân bằng độ mượt và độ trễ; hạ cửa sổ `max_in_flight = 2` ngay khi phát hiện thao tác chuột/phím (`is_input_burst`) và hỗ trợ tiết kiệm năng lượng khi rảnh (`idle_fps_saver`).
  - **Continuous CFR (`continuous_cfr`)**: Giữ nhịp đồng hồ khung hình hằng số ổn định với cửa sổ trượt rộng (`max_in_flight = 12–16`), làm tươi keyframe định kỳ mỗi `250ms` kết hợp xung nhịp `MKR0` + QPC Catch-Up để đạt trọn vẹn 60–360 FPS / 1.000+ FPS mà không nghẽn băng thông.
  - **Zero-Queue Drop (`low_latency_drop`)**: Khóa chặt `max_in_flight = 2` và xả bỏ hàng đợi trung gian để triệt tiêu độ trễ trôi chuột trên mạng WAN/4G yếu.

## 4. Ma Trận Giao Thức Nội Tuyến, Quản Trị Từ Xa & Tối Ưu Responsive Đa Thiết Bị

- **Thực thi RDP, SFTP và SSH trực tiếp trong trình duyệt (Zero External Software)**: Ngoài khả năng tạo đường hầm TCP (`tcp_tunnel.py`) và tải tệp cấu hình `.rdp`, hộp thoại Ma trận Giao thức cung cấp 3 trình khách chạy ngay trong Web Client: **In-Browser RDP Canvas**, **In-Browser SFTP Dual-Pane File Manager** và **In-Browser Interactive SSH Terminal**.
- **Bộ lọc Hiển thị & Bảo mật Phiên từ xa**: Tích hợp 4 chế độ lọc hình ảnh trực tiếp (`normal`, `crisp_text` làm nét chữ lập trình, `night_shield` lọc ánh sáng xanh, `high_contrast`), tính năng **Tự động khóa máy trạm khi ngắt kết nối (`auto_lock_on_disconnect`)** và **Tiết kiệm FPS khi rảnh (`idle_fps_saver`)**.
- **Chặn Autofill Trình quản lý Mật khẩu trên Thanh tìm kiếm**: Các thanh tìm kiếm (`#fleetSearchInput`, `#processSearchInput`, `#explorerSearchInput`, `#auditSearchInput`) được khóa `readonly` mặc định cho đến khi có thao tác chạm/gõ phím thật (`fleetSearchUserInteracted`), ngăn chặn triệt để lỗi Chrome/Edge tự động điền tên tài khoản đã lưu vào ô tìm kiếm máy trạm.
- **Responsive 10-Pass & Hỗ trợ Tai thỏ / Dynamic Island / Màn hình gập**: Sử dụng đơn vị `100dvh`, vùng đệm an toàn `env(safe-area-inset-*)` ở cả chế độ Dọc (Portrait) và Ngang (Landscape), cùng hệ thống Media Queries chi tiết từ màn hình gập siêu hẹp (`280px–359px`), điện thoại (`375px–430px`), iPad Split-Screen (`600px–1024px`) đến màn hình 2K/4K và cửa sổ Host GUI thu nhỏ (`540x580`).

## 5. Hướng Dẫn Cài Đặt Tự Động, Tham Số CLI & URL Query Params

Toàn bộ tham số cấu hình của Meikova Relay đều có thể truyền qua dòng lệnh (CLI flags), qua URL Query Parameters trên Web Client, và điều chỉnh trực tiếp trong phiên điều khiển từ xa (Remote Session).

## Layout Plan
- **Document Archetype**: Archetype 1 (Continuous Flow) inside `<main class="document-flow">` with clean flat hierarchy, zero `.page-sheet` wrappers, and organic pagination.
- **Typography Pairing**: Modern Technical pairing using `'Inter', 'Noto Sans', sans-serif` for clean Vietnamese diacritics and `'JetBrains Mono', 'DejaVu Sans Mono', monospace` for CLI flags, file paths, and protocol keys.
- **Strict Two-Tone Palette**: Primary `--primary: #0F172A` (Deep Slate Navy), Accent `--accent: #0284C7` (Technical Cyan-Blue), Body text `--text: #1E293B`, Page background `--bg: #FFFFFF`.
- **Table Architecture**: Clean booktabs tables with `2px solid var(--primary)` header bottom border and subtle `1px solid rgba(0,0,0,0.08)` row dividers, maximum one heavy table per section flow.

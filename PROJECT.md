# Project: Meikova Relay Host Master System

## Architecture
Hệ thống Remote Desktop Meikova Relay gồm 3 thành phần cốt lõi:
1. **Host Agent (`host_agent/`)**: Ứng dụng desktop Windows chạy ngầm khay hệ thống (System Tray) / Service, chịu trách nhiệm bắt hình màn hình (Native Win32, Desktop Duplication, Winlogon/UAC), bơm phím chuột (Win32 SendInput), đồng bộ clipboard text/image (`CF_DIB`), đo đạc telemetry 2s, quản trị nguồn (Keep-Awake), tự động triển khai (%LOCALAPPDATA%) và Live Auto-Update (NTFS Atomic Swap).
2. **Relay Server (`relay-server/`)**: Máy chủ WebSocket & HTTP Node.js chịu trách nhiệm điều phối phòng kết nối (room/signalling), quản lý tài khoản JWT, cung cấp API thông tin (`/api/version`, `/api/host-info`), và sinh động các script cài đặt đa nền tảng (`setup.bat`, `setup-linux.sh`, `setup-macos.sh`, `custom-config.json`).
3. **Web Client (`web-client/` & `relay-server/public/`)**: Giao diện người dùng Web SPA Ambient Dark kết nối điều khiển máy trạm thời gian thực, chứa Client Dock (`#floatingDeck`), Telemetry Badge, nút Emergency Unstick, Host Settings Modal (`#modalRemoteHostConfig`), đa ngôn ngữ i18n VI/EN và đồng bộ SHA-256 SSOT 100%.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | %LOCALAPPDATA% Self-Deploy | Tự kiểm tra và copy vào `%LOCALAPPDATA%\MeikovaRelayHost\MeikovaRelayHost.exe`, đăng ký HKCU\Run | M1 | ORIGINAL_REQUEST R1 |
| 2 | Junk Source Cleanup | Quét và xóa sạch các file `.py`, `.pyc`, batch/service rác trong `%LOCALAPPDATA%\MeikovaRelayHost`, xóa khóa `TitanRemoteHost` | M1 | ORIGINAL_REQUEST R1 |
| 3 | NTFS Atomic Swap Auto-Update | Thăm dò `GET /api/version`, tải `.update`, rename `.exe` -> `.old`, nạp bản mới, spawn `--updated`, xóa `.old` | M1 | ORIGINAL_REQUEST R1 |
| 4 | URL Protocol & Firewall | Đăng ký URL protocol `meikova-relay://` và mở Windows Firewall Rule chống chặn ngầm | M1 | ORIGINAL_REQUEST R1 |
| 5 | Winlogon / UAC Screen Capture | Xử lý chuyển đổi desktop bảo mật Winlogon / UAC Secure Desktop, refresh DC, chống màn hình đen | M2 | ORIGINAL_REQUEST R2 |
| 6 | Remote Workstation Unlock | Hàm `unlock_workstation(password)` bơm phím ảo mở khóa; tự cấu hình `SoftwareSASGeneration = 3` khi Admin | M2 | ORIGINAL_REQUEST R2 |
| 7 | Smart Keep-Awake | Tự kích hoạt `SetThreadExecutionState` chống ngủ khi có client kết nối, hoàn trả khi ngắt kết nối | M2 | ORIGINAL_REQUEST R2 |
| 8 | Power RTC & WoL | Hỗ trợ BIOS RTC Wake Timer và Wake-on-LAN UDP | M2 | ORIGINAL_REQUEST R2 |
| 9 | Headless Virtual Display | Tự kích hoạt driver màn hình ảo khi máy trạm không cắm dây màn hình (`len(monitors) == 0`) | M2 | ORIGINAL_REQUEST R2 |
| 10 | Emergency Input Unstick | Nhả toàn bộ 256 virtual keycodes và 3 nút chuột khi disconnect hoặc qua WebSocket event | M3 | ORIGINAL_REQUEST R3 |
| 11 | Hardware Pulse Telemetry | Thu thập CPU %, RAM %, Nguồn/Pin thời gian thực qua Win32 API thuần gửi mỗi 2s qua WebSocket | M3 | ORIGINAL_REQUEST R3 |
| 12 | Bi-directional Image Clipboard | Đồng bộ ảnh Clipboard hai chiều (`CF_DIB` / PNG Base64) qua WebSocket | M3 | ORIGINAL_REQUEST R3 |
| 13 | High-DPI Manifest & Context | Nhúng manifest XML `uiAccess=true` và Win32 `SetProcessDpiAwarenessContext(Per-Monitor Aware V2)` | M3 | ORIGINAL_REQUEST R3 |
| 14 | 25+ Parameter Normalization | Chuẩn hóa ánh xạ 28 tham số SSOT trong `server.js` và `app.js` (`room`/`roomId`, `fps`/`fpsLimit`, etc.) | M4 | ORIGINAL_REQUEST R4 |
| 15 | CLI Parameter Parsing Scripts | `setup.bat` bóc tách `%*`, `setup-linux.sh` và `setup-macos.sh` bóc tách `$@`, sinh đầy đủ `config.json` | M4 | ORIGINAL_REQUEST R4 |
| 16 | SSOT `buildHostDownloadUrl` | Triển khai hàm `buildHostDownloadUrl()` chuẩn hóa vào toàn bộ nút tải và lệnh copy PowerShell | M4 | ORIGINAL_REQUEST R4 |
| 17 | Real-time Session Settings Modal | Bổ sung các trường còn thiếu vào `#modalRemoteHostConfig`, đọc/ghi qua WebSocket hai chiều | M4 | ORIGINAL_REQUEST R4 |
| 18 | Client Dock Telemetry Badge & Unstick | Thêm Telemetry Badge (CPU/RAM nhảy số 2s) và nút Emergency Input Unstick lên `#floatingDeck` | M5 | ORIGINAL_REQUEST R3, R5 |
| 19 | Ambient Dark Standards | Tuân thủ Ambient Dark, hairline border liền khối, zero double-border, zero native dialogs, zero emoji | M5 | ORIGINAL_REQUEST R5 |
| 20 | Complete Bilingual i18n | Đảm bảo 100% nhãn và chuỗi giao diện mới có mặt trong từ điển song ngữ VI/EN `i18n.js` | M5 | ORIGINAL_REQUEST R5 |
| 21 | SHA-256 SSOT Sync | Đồng bộ 100% tất cả 24 tệp giữa `web-client/` và `relay-server/public/` | M5 | ORIGINAL_REQUEST R5 |
| 22 | Comprehensive Test Suite | Viết `tests/test_host_master_capabilities.py` và chạy toàn bộ test suites đạt 100% PASS (Exit 0) | M6 | ORIGINAL_REQUEST Acceptance Criteria |
| 23 | Security Review & Forensic Audit | Độc lập kiểm toán an ninh, xác thực quyền hạn, bảo vệ chống rò rỉ credential, không backdoor | M6 | ORIGINAL_REQUEST Acceptance Criteria |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | %LOCALAPPDATA% Deployment, NTFS Atomic Swap & Cleanup | Features 1, 2, 3, 4 (`host_agent/deployment_manager.py`, `gui_agent.py`, `auto_updater.py`) | None | IN_PROGRESS |
| M2 | Winlogon/UAC Capture, Remote Unlock, Power & Virtual Display | Features 5, 6, 7, 8, 9 (`host_agent/screen_capture.py`, `input_injector.py`, `virtual_display.py`, `power_manager.py`) | None | PLANNED |
| M3 | Emergency Input Unstick, 2s Telemetry, Image Clipboard & High-DPI | Features 10, 11, 12, 13 (`host_agent/input_injector.py`, `telemetry.py`, `clipboard_manager.py`, `MeikovaRelayHost.manifest`, `scripts/build.py`) | None | PLANNED |
| M4 | SSOT 25+ Parameter Matrix & Remote Session Settings | Features 14, 15, 16, 17 (`relay-server/server.js`, `setup.bat`, `setup-linux.sh`, `setup-macos.sh`, `web-client/js/app.js`) | None | PLANNED |
| M5 | Ambient Dark UI Controls, i18n & SHA-256 SSOT Sync | Features 18, 19, 20, 21 (`web-client/index.html`, `js/app.js`, `js/i18n.js`, `relay-server/public/`) | M3, M4 | PLANNED |
| M6 | Test Suite Verification & Forensic Security Audit | Features 22, 23 (`tests/test_host_master_capabilities.py`, full pytest suite, security audit) | M1, M2, M3, M4, M5 | PLANNED |

## Interface Contracts
### Host Agent ↔ Relay Server (WebSocket Signalling)
- `telemetry_pulse`: `{ "type": "telemetry_pulse", "cpu_percent": 12.5, "ram_percent": 45.2, "battery_percent": 98, "power_plugged": true, "timestamp": 1729876543 }`
- `get_host_config`: Client gửi `{ "type": "get_host_config" }`, Server chuyển tiếp cho Host, Host trả `{ "type": "host_config_response", "config": { ... 28 fields } }`.
- `set_host_config`: Client gửi `{ "type": "set_host_config", "config": { ... modified fields } }`, Host lưu `config.json`, cập nhật runtime params, phản hồi `{ "type": "host_config_response", "success": true, "config": { ... } }`.
- `unstick_inputs` / `emergency_unstick`: Client gửi `{ "type": "emergency_unstick" }` hoặc `{ "type": "unstick_inputs" }`, Host gọi `unstick_all_inputs()` nhả 256 virtual keycodes và 3 nút chuột.
- `unlock_workstation`: Client gửi `{ "type": "unlock_workstation", "password": "..." }`, Host gọi `unlock_workstation(password)`.

### Client Dock ↔ Web UI State
- `#badgeTelemetry`: Gắn trên `#floatingDeck`, hiển thị CPU% / RAM% nhảy số real-time mỗi khi nhận `telemetry_pulse`.
- `#btnEmergencyUnstick`: Gắn trên `#floatingDeck`, bấm gửi ngay WebSocket event `emergency_unstick` và hiển thị ambient toast.

## Code Layout
- `host_agent/deployment_manager.py`: Quản lý vị trí cài đặt, copy vào `%LOCALAPPDATA%`, dọn rác, registry autostart, protocol URL, firewall rule.
- `host_agent/gui_agent.py`: Entry point GUI, kiểm tra self deploy, gọi auto-update, xử lý cờ CLI `--updated`.
- `host_agent/auto_updater.py`: Live update, tải `.update`, NTFS atomic swap.
- `host_agent/screen_capture.py`: Chụp màn hình, quản lý DC Win32, phát hiện switch desktop Winlogon/UAC và tái tạo DC.
- `host_agent/input_injector.py`: Bơm phím chuột, unstick 256 keycodes, unlock workstation.
- `host_agent/telemetry.py`: Thu thập CPU/RAM/Battery qua Win32 API thuần.
- `host_agent/clipboard_manager.py`: Đồng bộ text và ảnh `CF_DIB`.
- `host_agent/virtual_display.py`: Quản lý và tự động cài đặt driver màn hình ảo khi headless.
- `host_agent/MeikovaRelayHost.manifest`: Manifest Windows nhúng `uiAccess=true` và Per-Monitor Aware V2.
- `relay-server/server.js`: REST API, sinh script cài đặt, chuẩn hóa ma trận 28 tham số, WebSocket relaying.
- `web-client/index.html` & `relay-server/public/index.html`: Giao diện Web SPA, Client Dock controls, Host Settings modal.
- `web-client/js/app.js` & `relay-server/public/js/app.js`: Logic frontend, `buildHostDownloadUrl()`, telemetry badge, unstick trigger.
- `web-client/js/i18n.js` & `relay-server/public/js/i18n.js`: Từ điển song ngữ VI/EN.
- `tests/test_host_master_capabilities.py`: Test suite toàn diện kiểm thử tất cả các năng lực mới của Host Master System.

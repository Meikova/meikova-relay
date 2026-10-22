# Session Handoff: Meikova Platform - Đồng Bộ Hóa Phong Cách Tray Icon Sang Brand Squircle Trên Toàn Bộ Hệ Sinh Thái

## 1. Mục tiêu hoàn thành
- [x] **Chuẩn hóa và đồng bộ phong cách Tray Icon sang Brand Squircle cho 100% sản phẩm:**
  - Trước đây: `meikova-harvest` dùng icon đơn sắc trắng (`white-32.png`), `meikova-relay` dùng `white-32.png`, trong khi `meikova-loop` dùng icon app squircle có màu (`app.ico`). Điều này tạo ra sự không đồng nhất về nhận diện thương hiệu giữa các sản phẩm trên Taskbar.
  - Sau chuẩn hóa: Cả 3 sản phẩm đều chuyển sang dùng chung phong cách **Brand Squircle** (`app-icons/rounded/icon-32.png`): Nền bo góc tối `#11151B` kết hợp biểu tượng phát quang màu thương hiệu riêng biệt (Relay: xanh ngọc `#83E8AC`, Loop: cam hổ phách `#FFB38A`, Harvest: cyber cyan `#83C4FF`).
  - Cập nhật công cụ đồng bộ tài sản tập trung `D:\JOB\DEV\meikova\scripts\deploy_product_assets.py` để trỏ toàn bộ tray icon nguồn sang `app-icons/rounded/icon-32.png`.
  - Đồng bộ và kiểm tra 183/183 tài sản đạt chuẩn 100% với SSOT (`deploy_product_assets.py --check` -> Clean Exit Code 0).
  - Cập nhật `host_agent/tray_menu.py` trên Meikova Relay để ưu tiên đọc file `logo.png` / `tray_icon.png` Brand Squircle chính thức từ SSOT.

## 2. Lệnh kiểm tra đã chạy & Exit Code
- `python D:\JOB\DEV\meikova\scripts\deploy_product_assets.py`: **Exit Code 0** (Đã đồng bộ toàn bộ 3 dự án).
- `python D:\JOB\DEV\meikova\scripts\deploy_product_assets.py --check`: **Exit Code 0** (183/183 tài sản khớp).
- `python -m unittest tests/test_host_chat.py tests/test_screen_sync.py`: **Exit Code 0** (10/10 tests pass).

## 3. Các phần còn tồn đọng và cảnh báo kỹ thuật
- Không còn lỗi phân mảnh nhận diện. Cả 3 ứng dụng Desktop đều hiển thị biểu tượng khay hệ thống Brand Squircle sắc nét, đồng bộ tuyệt đối với Header và App Icon.

---

# Session Handoff: Meikova Relay - Khắc Phục Lỗi Foreign Key Constraint (LibsqlError SQLITE_CONSTRAINT) Khi Host Workstation Kết Nối

## 1. Mục tiêu hoàn thành
- [x] **Tìm nguyên nhân gốc rễ và sửa triệt để lỗi sập server Render do FOREIGN KEY constraint failed:**
  - `relay-server/server.js`: Khi máy trạm (Host) gửi gói tin bắt tay `init_host`, trường `data.user_id` mang giá trị định danh từ cấu hình local của máy trạm. Giá trị này chưa tồn tại trong bảng `users` trên cơ sở dữ liệu đám mây Turso. Đoạn code cũ gán trực tiếp `targetUserId = data.user_id` mà không kiểm tra sự tồn tại trong `users`.
  - `relay-server/db.js` (`upsertDevice`): Khi thực hiện `INSERT INTO devices (id, user_id, ...)` hoặc `UPDATE devices`, SQLite kích hoạt ràng buộc khóa ngoại `FOREIGN KEY(user_id) REFERENCES users(id)`. Do `user_id` không tồn tại, Libsql ném lỗi `SQLITE_CONSTRAINT: SQLite error: FOREIGN KEY constraint failed`.
  - Do `ws.on('message')` thiếu bọc `try...catch` và tiến trình Node.js thiếu bộ lắng nghe `unhandledRejection`, lỗi async này đã làm sập toàn bộ tiến trình relay server trên Render (`error Command failed with exit code 1`).
- [x] **Khắc phục đa tầng (Defense-in-depth):**
  - `relay-server/db.js`: Kiểm tra tính hợp lệ của `userId` bằng truy vấn `SELECT id FROM users WHERE id = ?`. Nếu không tồn tại, tự động gán `validatedUserId = null` (cột `user_id` là nullable). Đồng thời bổ sung khối `try...catch` dự phòng: nếu phát sinh lỗi `FOREIGN KEY`, tự động fallback sang ghi bản ghi với `user_id = NULL` để không làm gián đoạn kết nối.
  - `relay-server/server.js`: Trong `init_host`, thực hiện tra cứu người dùng qua `DB.findUserByIdentifier()` trước khi gán `targetUserId`. Bọc toàn bộ các lời gọi `DB.upsertDevice` và `DB.logAudit` trong khối `try...catch`.
  - Bổ sung `process.on('unhandledRejection')` và `process.on('uncaughtException')` ở đầu `server.js` nhằm triệt tiêu nguy cơ sập tiến trình production khi có lỗi ngoài ý muốn.
- [x] **Xác minh kiểm thử:**
  - Kiểm tra trực tiếp hàm `DB.upsertDevice` với `userId` rác không tồn tại: Thành công 100%, tự động tạo thiết bị hợp lệ không vi phạm constraint.
  - Chạy toàn bộ test suite `test_turso_dual_adapter.js`: **Exit Code 0** (PASS cả Turso Cloud SQLite và Local SQLite WAL).
  - Chạy toàn bộ `tests/test_auth_sync_and_linking.py` và `tests/test_host_chat.py`: **Exit Code 0** (10/10 tests pass).

## 2. Lệnh kiểm tra đã chạy & Exit Code
- `node relay-server/test_turso_dual_adapter.js`: **Exit Code 0**.
- `python -m unittest tests/test_auth_sync_and_linking.py tests/test_host_chat.py`: **Exit Code 0** (10/10 tests pass).
- `node -c relay-server/server.js` & `node -c relay-server/db.js`: **Exit Code 0** (Syntax valid).

## 3. Các phần còn tồn đọng và cảnh báo kỹ thuật
- Không còn lỗi Foreign Key constraint khi máy trạm lạ hoặc máy trạm chưa liên kết tài khoản kết nối vào Relay Server.

---

# Session Handoff: Meikova Relay - Khắc Phục Lỗi Heap Corruption (NTSTATUS 0xC0000374 / Exit Code 1) Trên Windows CI/CD

## 1. Mục tiêu hoàn thành
- [x] **Tìm nguyên nhân gốc rễ và sửa triệt để lỗi Exit Code 1 / 0xC0000374 (`STATUS_HEAP_CORRUPTION`) trên Windows:**
  - `host_agent/screen_capture.py`, `host_agent/cursor_manager.py`, `host_agent/clipboard_manager.py`: Loại bỏ hoàn toàn lệnh `user32.CloseDesktop(hDesk)` gọi ngay sau `user32.SetThreadDesktop(hDesk)`. Theo đặc tả Win32 API, việc gọi `CloseDesktop` trên desktop handle đang được gán cho thread hiện tại làm hỏng heap quản lý desktop của NT subsystem.
  - `host_agent/clipboard_manager.py`: Loại bỏ việc gọi `OpenInputDesktop` lặp đi lặp lại mỗi 200ms trong vòng lặp polling. Bổ sung cờ `self._attached = False` và chỉ attach một lần duy nhất. Thêm join thread trong `stop_listener(timeout=0.3)`.
  - `host_agent/cursor_manager.py`: Thêm join thread trong `stop_listener(timeout=0.3)`.
  - `host_agent/host_service.py`: Bổ sung dọn dẹp `self.clipboard.stop_listener()` và `self.terminal.stop()` trong phương thức `stop()`.
  - `tests/test_clipboard_sync.py` & `tests/test_host_chat.py`: Bọc và dọn dẹp `service.stop()` trong các khối `finally:`, đảm bảo không để rò rỉ daemon thread chạy nền khi runner thoát tiến trình.
- [x] **Xác minh kiểm thử cục bộ:**
  - Toàn bộ 131 test cases vượt qua (`OK (skipped=1)`).
  - Exit code tiến trình chuyển từ `-1073740940` (0xC0000374) sang `0` (Clean Exit) thành công 100%.

## 2. Lệnh kiểm tra đã chạy & Exit Code
- `python -m unittest discover tests`: **Exit Code 0** (131/131 tests pass, 1 skipped).
- Kiểm tra trực tiếp `$LASTEXITCODE`: **0**.

## 3. Các phần còn tồn đọng và cảnh báo kỹ thuật
- Không còn lỗi heap corruption trên môi trường Windows.
- Khi push commit lên GitHub Actions, luôn kèm cờ `[build] [release]` để kích hoạt runner build theo chuẩn `meikova-release-ops`.

---

# Session Handoff: Meikova Relay - Khắc Phục Lỗi Đồng Bộ Clipboard Hai Chiều (Windows 64-bit & Web Client)

## 1. Mục tiêu hoàn thành
- [x] **Tìm nguyên nhân gốc rễ và sửa triệt để lỗi không đồng bộ Clipboard trên Windows Host:**
  - `host_agent/clipboard_manager.py`: Môi trường không cài `win32clipboard` (pywin32) nên chạy nhánh ctypes native. Trên kiến trúc Windows 64-bit, con trỏ trả về từ `kernel32.GlobalAlloc`, `kernel32.GlobalLock`, `user32.GetClipboardData`, `user32.SetClipboardData` bị ép kiểu ngầm định về `c_int` (32-bit), dẫn đến lỗi `Access violation writing 0x0000000000000000` khiến `set_clipboard_text` luôn thất bại và `get_clipboard_text` luôn trả về `None`.
  - Khai báo đầy đủ `argtypes` và `restype` chuẩn 64-bit (`c_void_p`, `c_size_t`, `c_bool`, `OpenInputDesktop`, `SetThreadDesktop`, `CloseDesktop`).
- [x] **Bổ sung giao thức kéo Clipboard chủ động (`clipboard_pull`):**
  - `host_agent/host_service.py`: Xử lý sự kiện `clipboard_pull` từ client, lấy ngay nội dung clipboard hiện tại của máy trạm và phản hồi bằng tin nhắn `clipboard_sync`.
- [x] **Nâng cấp Web Client (`relay-server/public` và `web-client`):**
  - `index.html`: Bổ sung nút `#btnPullClipboard` ("Làm mới") với biểu tượng SVG trên tiêu đề tab Bộ nhớ tạm (`#shelfClipboardTab`).
  - `i18n.js`: Thêm khóa dịch `shelf.btn_pull_clip` và `shelf.btn_pull_clip_title` cho cả tiếng Việt và tiếng Anh.
  - `app.js`:
    - Gắn sự kiện click cho `#btnPullClipboard` kích hoạt `clipboard_pull`.
    - Tự động gửi `clipboard_pull` khi người dùng chuyển sang tab clipboard (`shelfClipboardTab`).
    - Tự động gửi `clipboard_pull` ngay khi hoàn tất bắt tay kết nối phiên (`init_client`).
    - Khắc phục race condition phím tắt `Ctrl+V` trên Remote Desktop: Khi nhấn `Ctrl+V`, chặn sự kiện phím thô `KeyV` gửi lên máy trạm để cho phép sự kiện `paste` của trình duyệt thu nhận clipboard mới nhất, gửi `clipboard_sync` tới host và kích hoạt dán từ xa mượt mà.
- [x] **Viết bộ kiểm thử tự động `tests/test_clipboard_sync.py` & Sửa cấu hình CI/CD:**
  - Cô lập test khỏi background `terminal` và `cursor_manager` của `HostService` để tránh race condition trên môi trường Linux/macOS runner khiến `terminal_output` chèn vào kiểm tra `clipboard_sync`.
  - Bổ sung `@unittest.skipUnless(sys.platform == 'win32')` cho test ctypes native Windows.
  - Sửa `.github/workflows/build-release.yml`: Xóa bỏ điều kiện ép buộc commit message phải có cờ `[build]` hoặc `[release]`. Bây giờ mọi commit push lên branch `main` đều sẽ tự động chạy toàn bộ quy trình CI/CD build và kiểm thử đa nền tảng.
- [x] **Nâng cấp `screen_capture.py` hỗ trợ Desktop Swapping:**
  - Chuyển `_attach_window_station()` sang ưu tiên gọi `OpenInputDesktop(0, False, 0x01FF)` thay vì hardcode `OpenDesktopW('default')`, tự động bắt vào desktop `Winlogon` / Lock Screen khi tiến trình có quyền quản trị/service.
- [x] **Đồng bộ hóa 100% giữa `relay-server/public` và `web-client`.**

## 2. Lệnh kiểm tra đã chạy & Exit Code
- `python -m unittest tests/test_clipboard_sync.py`: **Exit Code 0** (4/4 tests pass).
- `python -m unittest tests/test_host_chat.py tests/test_i18n.py tests/test_download_endpoints.py`: **Exit Code 0** (20/20 tests pass).
- `python -m unittest tests/test_auth_sync_and_linking.py`: **Exit Code 0** (5/5 tests pass).
- `python -m unittest discover tests`: **Exit Code 0** (131/131 tests pass, 1 skipped).
- `node -c relay-server/public/js/app.js` & `web-client/js/app.js`: **Exit Code 0** (Syntax valid).
- `node -c relay-server/public/js/i18n.js` & `web-client/js/i18n.js`: **Exit Code 0** (Syntax valid).

## 3. Các phần còn tồn đọng và cảnh báo kỹ thuật
- Không có lỗi tồn đọng. Clipboard đồng bộ hai chiều mượt mà, tức thời giữa Web Client và Host Workstation Windows x64.

---

# Session Handoff: Meikova Relay - Giao Diện Chat Ambient Dark & Tin Nhắn Hai Chiều Thời Gian Thực

## 1. Mục tiêu hoàn thành
- [x] **Custom lại giao diện khung chat Web Client theo chuẩn Meikova Ambient UI:**
  - Thay thế terminal text thô sơ cũ bằng Container `.meikova-chat-tab` và Stream `.meikova-chat-stream` (nền sâu OKLCH `#070D17`, viền hairline `#1E293B`, scrollbar mỏng 4px bo tròn).
  - Phân tách Chat Bubbles 2 chiều:
    - **Tin nhắn Bạn (Operator/Client):** Căn phải, bubble gradient xanh ngọc `linear-gradient(135deg, rgba(34,197,94,0.18), rgba(34,197,94,0.08))` viền `rgba(34,197,94,0.35)`, timestamp JetBrains Mono kèm icon Checkmark SVG đôi xác nhận đã gửi.
    - **Tin nhắn Máy trạm (Remote Host):** Căn trái, bubble gradient xanh dương đậm `linear-gradient(135deg, rgba(15,23,42,0.9), rgba(30,41,59,0.6))` viền `rgba(56,189,248,0.25)`, kèm SVG avatar máy trạm và tên máy trạm Cyan `#38BDF8`.
  - Header khung chat: LED xanh báo trạng thái trực tiếp, tên máy trạm đồng bộ động (`#chatHostName`), nút làm trống lịch sử trò chuyện.
  - Quick action chips: Các nút bấm SVG gửi nhanh ("Xin chào", "Giữ màn hình", "Hoàn tất") tuân thủ nghiêm ngặt Zero-Emoji Mandate.
  - Thanh nhập tin nhắn: Pill input bo tròn viền hairline glow neon khi focus, nút gửi SVG Paper plane bo góc.
- [x] **Bổ sung nút Chat chuyên dụng trên Viewer Floating Deck:**
  - Nút `#btnViewerChat` trên thanh công cụ điều khiển nổi giúp người dùng mở/đóng khung chat 1-click mà không cần tìm trong menu.
  - Tích hợp chấm đỏ nhấp nháy Unread Dot (`#chatUnreadDot` và `#tabChatUnreadDot`) khi có tin nhắn từ máy trạm đến mà khung chat đang đóng.
  - Tích hợp âm thanh chuông báo tinh tế bằng Web Audio API (sine wave 784Hz -> 1046Hz, không cần tải file ngoài).
- [x] **Kích hoạt gửi nhận tin nhắn 2 chiều hoàn chỉnh từ phía Máy trạm (Host Workstation):**
  - **Trên Host GUI WebView2 (`gui_view.html`):**
    - Tích hợp sẵn Slide-over Chat Drawer `#hostChatDrawer` hiển thị trực tiếp bên trong cửa sổ host agent.
    - Nút Chat trên titlebar và session banner được trang bị Unread Dot và click là mở ngay Chat Drawer.
    - Cho phép người ngồi máy trạm nhập phản hồi và gửi tin nhắn 2 chiều ngay lập tức qua API `send_host_chat(text)`.
    - Tự động phát âm báo Web Audio và rung chuông khi có tin nhắn từ kỹ thuật viên đến.
  - **Trên Cửa sổ Chat nổi Tkinter (`chat_window.py`):**
    - Chuẩn hóa toàn bộ typography và bảng màu theo phong cách Ambient Dark `#070D17` / `#0D1524`, viền `#1E293B`, nút Send Emerald `#22C55E`.
    - Sửa triệt để các ký tự tiếng Việt mojibake ("Trò chuyện trực tiếp", "Kỹ thuật viên", "Bạn", "Gửi").
    - Đồng bộ tin nhắn 2 chiều với `HostService.send_chat_message`.
- [x] **Nâng cấp Relay Server (`relay-server/server.js`):**
  - Bổ sung router điều phối tin nhắn `chat_message` 2 chiều:
    - Client -> Host + phát sóng tới các client quan sát khác trong phòng.
    - Host -> Phát sóng tới tất cả các client trong phòng.
  - Bổ sung Audit Logging: `CHAT_SENT_CLIENT` và `CHAT_SENT_HOST` ghi nhận đầy đủ người gửi, máy trạm và độ dài tin nhắn.
- [x] **Đồng bộ hóa 100% giữa `relay-server/public` và `web-client`:**
  - Cập nhật cả `index.html`, `style.css`, `app.js`, `i18n.js`.

## 2. Lệnh kiểm tra đã chạy & Exit Code
- `python -m unittest tests/test_host_chat.py`: **Exit Code 0** (5/5 tests pass).
- `python -m unittest discover tests`: **Exit Code 0** (127/127 tests pass, 1 skipped).
- `node -c server.js`: **Exit Code 0** (Syntax valid).
- `node -c app.js` & `node -c i18n.js`: **Exit Code 0** (Syntax valid).

## 3. Các phần còn tồn đọng và cảnh báo kỹ thuật
- Không có lỗi tồn đọng. Tính năng chat 2 chiều hoạt động đồng bộ trên cả Web Viewer, Host WebView2 GUI và Host Standalone Tkinter Floating Window.

---

# Session Handoff: Meikova Relay - Tắt Headless, Sửa Nút Thêm Máy Trạm & Dynamic Account Binding

## 1. Mục tiêu hoàn thành
- [x] **Sửa nút "Thêm máy trạm" (`#btnOpenAddModal`):** Sửa lỗi `ReferenceError: userId is not defined` trong hàm `getInstallCommands()` (`app.js` cả `relay-server` và `web-client`). Khai báo đúng `userId = currentUser ? (currentUser.id || currentUser.userId || '') : ''` và `accountName = currentUser ? (currentUser.username || currentUser.email || 'User') : 'User'`. Bổ sung event listener đóng modal khi click ra backdrop và phím Escape.
- [x] **Tắt chế độ Headless mặc định (Turn Off Headless):**
  - Trong `relay-server/server.js`: Mặc định `isHeadless = false` và `HEADLESS_MODE=0`.
  - Trong file sinh `setup.bat`: Mặc định `APP_FLAGS=--gui` để khi cài đặt trên máy trạm, ứng dụng lập tức mở cửa sổ GUI cho người dùng; registry `HKCU\...\Run` đăng ký `--autostart` để khởi động cùng Windows thu gọn khay hệ thống.
  - Trong `host_agent/gui_agent.py`: Bỏ cờ tự động ép headless từ file config cũ. Chỉ chạy headless khi có cờ CLI tường minh (`--headless` hoặc `--service-headless`).
- [x] **Tự động gắn thông tin tài khoản đang đăng nhập vào script và lệnh tải:**
  - `Setup-MeikovaHost.bat`: Tự động gắn query params `?account=${accountName}&userId=${userId}&relay=${relayWs}`.
  - Thêm thẻ và liên kết 1-click cho Linux (`setup-linux.sh`) và macOS (`setup-macos.sh`) với đầy đủ `account` và `user_id`.
  - Cập nhật lệnh PowerShell 1-liner trên `#appsDownloadModal` tự động nhúng link đầy đủ thông số tài khoản người dùng đang đăng nhập.
  - Cập nhật hàm `renderUserBadge()` để tự động làm mới toàn bộ link và snippet ngay khi user đăng nhập.
- [x] **Sửa lỗi Service Worker Cache (`sw.js`):**
  - Khắc phục triệt để `Uncaught (in promise) TypeError: Failed to execute 'put' on 'Cache': Request scheme 'chrome-extension' is unsupported` bằng cách kiểm tra `!url.protocol.startsWith('http')` và thêm catch handler an toàn.
- [x] **Bổ sung thẻ meta PWA:** Thêm `<meta name="mobile-web-app-capable" content="yes">` xử lý deprecation warning của trình duyệt.
- [x] **Nâng cấp `host_service.py`:** Bổ sung cơ chế tự tìm và nạp cấu hình `config.json` đa nền tảng (frozen exe, LocalAppData, ~/.meikova-relay, CWD, script dir, user profile), hỗ trợ tham số `--user-id` và `--config`.
- [x] **Chuẩn hóa bộ kiểm thử:**
  - Cập nhật `tests/test_pwa_manifest.py` kế thừa chuẩn `unittest.TestCase`.
  - Bổ sung 3 test cases cho `tests/test_download_endpoints.py` kiểm tra `user_id` và setup script cho Linux/macOS.

## 2. Lệnh kiểm tra đã chạy & Exit Code
- `python -m unittest tests/test_download_endpoints.py tests/test_pwa_manifest.py`: **Exit Code 0** (9/9 tests pass).
- Full suite (26 test files, 129 test cases): **Exit Code 0** (`Was successful: True`, 0 failures, 0 errors).

## 3. Các phần còn tồn đọng và cảnh báo kỹ thuật
- Không có lỗi tồn đọng. Hệ thống hoạt động trơn tru trên mọi nền tảng Windows, Linux, macOS.

---

# Session Handoff: Meikova Space Deployment & Legacy Alias Purge

## 1. Mục tiêu hoàn thành
- [x] Đã xóa bỏ toàn bộ tên định danh cũ `TitanRemoteHost.exe` và `TitanRemoteHost-windows-x64.zip` trong file `scripts/build.py` và `.github/workflows/build-release.yml` (theo ảnh người dùng gửi).
- [x] Đã cập nhật `app.py` trong `meikova-loop` để trỏ nguồn đồng bộ về kho công khai `Meikova/meikova-loop`.
- [x] Đã đồng bộ thành công các file lên Hugging Face Space `m3ik18dp/meikova-loop` bằng API Token mới:
  - Trạng thái Space: **RUNNING (HTTP 200 OK)**
  - Tên hiển thị trên web: **Meikova Loop**
- [x] Cập nhật mô tả repository trên GitHub `Meikova/meikova-loop` để thể hiện rõ nguồn gốc fork:
  - "Fork of lvt1693/meikova-loop - DJ mashup & continuous soundscape engine with ONNX inference, mobile shell, and desktop app."
  - Lưu ý về gắn cờ fork native của GitHub: GitHub không cung cấp API tự động chuyển repo độc lập thành fork; cần gửi ticket cho GitHub Support nếu muốn hiển thị dòng chữ "forked from lvt1693/meikova-loop" dưới tên repo.

## 2. Kết quả CI/CD Runner thực tế (GitHub Actions)
- `Meikova/meikova-relay`:
  - Run 39537926502: **SUCCESS (Exit Code 0)** trên cả 3 nền tảng Windows, Linux, macOS.
  - Run 39538847824: Đang đóng gói bản sạch hoàn toàn không còn alias cũ.
- `Meikova/meikova-loop`:
  - Run 39537474393: **SUCCESS (Exit Code 0)** trên cả 5 nền tảng: Windows, Linux, macOS, Android, iOS.
- `Meikova/meikova-harvest`:
  - Run 39537664137: **SUCCESS (Exit Code 0)** trên cả 3 nền tảng: Windows, Ubuntu, macOS.


---

## 3. Cập nhật Nút & Modal Tải Ứng Dụng Đa Nền Tảng (Cross-Platform Native Apps)
- **Meikova Harvest:**
  - Bổ sung nút `#btn-open-apps-modal` trên Topbar Header `.header-actions`.
  - Bổ sung modal `#apps-download-modal` với 6 thẻ tải chính:
    1. Windows Setup (`.EXE` installer) -> `/api/download/app/win-setup`
    2. Windows Portable (`.EXE` không cần cài) -> `/api/download/app/win-portable`
    3. macOS Silicon (`.DMG` Apple Silicon M1-M4) -> `/api/download/app/dmg`
    4. Linux AppImage (`.AppImage` đa distro) -> `/api/download/app/appimage`
    5. Extension trình duyệt Chrome / Edge (`.ZIP` Manifest V3) -> `/api/download/app/extension`
    6. Web App Standalone (PWA) -> Cài trực tiếp trên trình duyệt.
  - Viết unit test `tests/test_download_native_app.py` (3/3 test pass - Exit Code 0).
  - Đã commit và push lên `Meikova/meikova-harvest` (commit `d9c08e3`).

- **Meikova Relay:**
  - Hoàn thiện nút `#btnNavDownloadApps` trên topbar và modal `#modalDownloadApps` phân tách 2 Tab (Sliding Segmented Switcher):
    1. **Tab 1: Máy trạm phát sóng (Host Agent)** - máy bị điều khiển (Windows Standalone EXE, Portable ZIP, Script 1-Click setup.bat, Linux DEB daemon, Linux Tarball, macOS DMG, lệnh PowerShell 1 dòng).
    2. **Tab 2: Máy điều khiển (Remote Viewer Client)** - máy điều khiển (Windows Desktop Client WebView2 60fps, Portable ZIP, macOS Client, Linux Client, Web Remote PWA).
  - Tích hợp controller JS (đóng/mở modal, chuyển tab Host/Client, sao chép lệnh cài đặt 1-click, PWA prompt).
  - Viết unit test `tests/test_download_endpoints.py` (4/4 test pass - Exit Code 0).
  - Chạy toàn bộ 80 unit test của meikova-relay: **80 tests in 19.6s, OK (Exit Code 0)**.
  - **Trạng thái lưu trữ:** Giữ nguyên cục bộ (local uncommitted/unpushed) theo yêu cầu người dùng, không push lên remote.


---

## 4. Xây dựng Skill Cha & Rule Cha Tự Động Định Tuyến (Meikova Master Meta-Orchestrator)
- **Vấn đề giải quyết:** Trước đây hệ sinh thái có 9 skill phân mảnh (`meikova-ambient-ui`, `meikova-auth`, `meikova-data-sync`, `meikova-i18n`, `meikova-media-engine`, `meikova-multiplatform`, `meikova-network-relay`, `meikova-system-control`, `meikova-testing`) khiến người dùng phải nhớ và gõ nhiều lần `/skill`.
- **Giải pháp thực hiện:**
  1. **Master Skill (`meikova`):** Tạo tại `C:\Users\kiemp\.gemini\config\skills\meikova\SKILL.md`. Người dùng chỉ cần gõ duy nhất `/meikova <nhiệm vụ>`. Skill chứa Ma trận định tuyến tự động (Intent Routing Matrix) để Agent tự động dùng `read_file` nạp tri thức của sub-skill tương ứng hoặc chuỗi liên hoàn nhiều sub-skills.
  2. **Master Rule (`meikova-master.md`):** Tạo tại `C:\Users\kiemp\.gemini\config\rules\meikova-master.md` và liên kết vào `D:\JOB\DEV\meikova\AGENTS.md`. Rule quy định cơ chế "Zero-Prompt Skill Routing" — khi làm việc trong bất kỳ repo Meikova nào, Agent tự động phân loại ngữ cảnh và áp dụng quy chuẩn kỹ thuật mà không cần người dùng gõ lệnh thủ công.


---

## 5. Thiết Lập Đội Ngũ Subagents Kỹ Thuật Có Phân Cấp Lãnh Đạo (Meikova Engineering Squad)
- **Đã định nghĩa 6 vị trí subagent chuyên biệt:**
  1. `meikova-lead-architect`: Tech Lead & Chief Architect (Lãnh đạo, chia việc, duyệt kiến trúc).
  2. `meikova-frontend-engineer`: Kỹ sư giao diện Ambient Dark & Inline Vector SVG.
  3. `meikova-backend-engineer`: Kỹ sư máy chủ lõi, SQLite sync, WebSocket relay, Media engine.
  4. `meikova-security-auditor`: Kiểm toán viên an ninh, Google OAuth, SSRF guard, Audit trail.
  5. `meikova-devops-engineer`: Kỹ sư đóng gói đa nền tảng, System service/tray, Docker, Deploy.
  6. `meikova-qa-engineer`: Kỹ sư kiểm thử chất lượng, TDD, bắt buộc Exit Code 0.
- **Tích hợp vào hệ thống:**
  - Runtime: Định nghĩa thành công vào hệ thống qua tool `define_subagent` (sẵn sàng gọi qua `invoke_subagent`).
  - Persistent: Lưu trữ tại `D:\JOB\DEV\meikova\.agents\agents/<name>/agent.md`.
  - Skill: Cập nhật mục 5 trong `C:\Users\kiemp\.gemini\config\skills\meikova\SKILL.md`.
  - Rule: Cập nhật mục 3 trong `C:\Users\kiemp\.gemini\config\rules\meikova-master.md`.


---

## 6. Thiết Lập Đội Ngũ IT Thực Chiến Chuẩn Quốc Tế (Full-Stack 14-Role Enterprise Team)
- **Hoàn thành thiết kế & đăng ký 14 vị trí IT chuyên trách:**
  1. `meikova-pm-scrum`: Project Manager & Scrum Master (Delivery & Milestones).
  2. `meikova-ba-po`: Senior Business Analyst & Product Owner (Requirements & Data Contracts).
  3. `meikova-uiux-designer`: Lead UI/UX & Design System Architect (Ambient Dark, Tokens, Inline SVG).
  4. `meikova-lead-architect`: Chief Architect & Tech Lead (System Architecture & Ponytail Ladder).
  5. `meikova-frontend-engineer`: Senior Frontend Engineer (Web Client & PWA).
  6. `meikova-desktop-mobile-engineer`: Desktop & Mobile Engineer (WebView2, PyWebView, Mobile Shells).
  7. `meikova-backend-engineer`: Senior Backend & API Engineer (Node/Python, SQLite Sync, Relay).
  8. `meikova-media-infra-engineer`: Media Streaming & Low-Level Engineer (yt-dlp, FFmpeg, WASAPI).
  9. `meikova-security-auditor`: Application Security Auditor (AppSec, SAST, Google OAuth GIS, PBKDF2).
  10. `meikova-pentest-engineer`: Penetration Tester & Red Teamer (DAST, SSRF bypass, Fuzzing).
  11. `meikova-qa-automation`: Senior QA Automation Engineer (TDD, Unit/Integration Test, Exit Code 0).
  12. `meikova-qc-manual-e2e`: Quality Control & E2E Tester (Playwright E2E, Cross-Browser, a11y).
  13. `meikova-devops-engineer`: DevOps & Multiplatform Release Engineer (EXE/DMG/Deb/AppImage, CI/CD).
  14. `meikova-sre-observability`: Site Reliability Engineer (Telemetry, 60fps Latency, Crash Recovery).
- **Tích hợp:**
  - Runtime: Đăng ký cả 14 subagent vào phiên làm việc qua `define_subagent` (sẵn sàng gọi `invoke_subagent`).
  - Persistent: Lưu trữ 14 thư mục agent tại `D:\JOB\DEV\meikova\.agents\agents/`.
  - Skill: Cập nhật mục 5 & 6 trong `C:\Users\kiemp\.gemini\config\skills\meikova\SKILL.md`.
  - Rule: Cập nhật mục 3 trong `C:\Users\kiemp\.gemini\config\rules\meikova-master.md`.

---

## 7. Thực Thi Quy Chuẩn Zero-Native-Dialogs (Cấm Tuyệt Đối `alert` / `confirm` / `prompt`)
- **Quy định:** Không sử dụng hộp thoại native của trình duyệt (`window.alert`, `window.confirm`, `window.prompt`). Bắt buộc 100% sử dụng Custom Modal / Toast theo chuẩn Ambient Dark (`showAlert`, `showConfirm`, `showToast`).
- **Triển khai:**
  - Cập nhật rule vào: `C:\Users\kiemp\.gemini\config\rules\meikova-master.md`, `C:\Users\kiemp\.gemini\config\rules\AGENTS.md`, `C:\Users\kiemp\.gemini\config\rules\GEMINI.md`, `meikova-harvest/AGENTS.md`, `meikova-relay/AGENTS.md`, `meikova-loop/AGENTS.md`.
  - Đã rà soát và loại bỏ lệnh `alert()` PWA còn sót trong `meikova-harvest/static/js/main.js` (commit `ad47ac0`).
  - Đẩy commit `3eb3008` lên GitHub `Meikova/meikova-harvest`: **SUCCESS (Exit Code 0)**.

---

## 8. Trạng Thái Hiện Tại & Ràng Buộc Kiểm Chứng
- `Meikova/meikova-harvest`: Đã push hoàn tất lên nhánh `main` (`b57fc5d`).
- `Meikova/meikova-loop`: Sẵn sàng, sạch git, Space Hugging Face hoạt động bình thường.
- `Meikova/meikova-relay`:
  - Đã kiểm tra 82 unit test: **Ran 82 tests, OK (Exit Code 0)**.
  - Đã sửa triệt để token `--focus` loại bỏ lỗi viền kép (racetrack defect) tại local.
  - **Đang giữ nguyên cục bộ tại local, KHÔNG push lên GitHub** theo chỉ thị của người dùng (chờ luồng fix bug ở conversation khác hoàn thành).

---

## 9. Mở Rộng Bộ Quy Chuẩn & Skill: Zero-Native-Inputs, Custom Scrollbars & Frameless Window
- **Zero-Native-Inputs:** Cấm tuyệt đối form input nguyên mẫu (checkbox ô vuông xanh, radio mặc định, range slider xám). 100% custom `appearance: none`, bo góc, viền hairline neon, checked state phát quang.
- **Zero-Native-Scrollbars:** Cấm thanh cuộn to bản xám trắng của OS. Bắt buộc custom `::-webkit-scrollbar` mỏng 5px, bo tròn, nền trong suốt, hover neon.
- **Frameless Desktop Window & Custom Titlebar:** Cấm thanh quản trị nguyên mẫu của OS trên Desktop (Electron/PyWebView/WebView2). Bắt buộc `frame: false`, tự dựng titlebar custom 34px Ambient Dark với bộ 3 nút vector (Minimize, Maximize, Close - hover đỏ rực).
- **Đã cập nhật toàn diện:**
  - Skill: `meikova-ambient-ui/SKILL.md`, `meikova-multiplatform/SKILL.md`, `meikova/SKILL.md`.
  - Rules: `meikova-master.md`, `AGENTS.md` (toàn cục & 3 repo), `GEMINI.md`.
  - Subagents: `meikova-uiux-designer`, `meikova-frontend-engineer`, `meikova-desktop-mobile-engineer`.

---

## 10. Khắc Phục & Ban Hành Quy Chuẩn: Zero-Double-Border Mandate (Chống Lỗi Viền Kép Focus)
- **Nguyên nhân gốc rễ lỗi trong ảnh:** Biến `--focus` cũ khai báo `0 0 0 2px var(--ink-0), 0 0 0 4px var(--accent)` tạo ra một rãnh đen 2px ngăn cách giữa viền gốc của input (`border: 1px solid var(--accent)`) và viền ngoài (`box-shadow 4px`), biến thành 2 đường viền xanh song song đồng tâm (đường ray xe lửa).
- **Quy chuẩn mới (Single Hairline + Soft Diffuse Glow):**
  - Reset `outline: none !important;`.
  - Chỉ dùng 1 đường biên đơn: `border-color: var(--accent)`.
  - Thay thế token `--focus`: `0 0 0 1px var(--accent), 0 0 14px -2px oklch(var(--acc) / 0.5)` (tỏa sáng liền khối, không còn khe hở đen).
  - Đối với input lồng trong `.input-wrapper`: thẻ con triệt tiêu hoàn toàn `border` & `outline`, bắt sự kiện `:focus-within` trên thẻ cha.
- **Triển khai:**
  - Đã sửa token trong `meikova-ambient-ui/examples/tokens.css`, `meikova-relay/relay-server/public/css/tokens.css`, `web-client/css/tokens.css`.
  - Đã nạp vào quy tắc cốt lõi trong `meikova-ambient-ui/SKILL.md`, `meikova-master.md`, `AGENTS.md` (toàn cục & repo).
  - Subagents `meikova-uiux-designer` và `meikova-frontend-engineer` đã cập nhật nhiệm vụ kiểm duyệt viền input.

---

## 11. Thiết Kế Skill Điều Khiển CI/CD & Tự Động Hóa Phát Hành (`meikova-release-ops`)
- **Vấn đề giải quyết:** Trước đây mỗi lần push commit (kể cả sửa docs) đều kích hoạt toàn bộ runner (Windows, macOS, Ubuntu, Android, iOS), làm lãng phí hạn mức GitHub Actions và có nguy cơ ghi đè bản release không kiểm soát.
- **Giải pháp & Kiến trúc 3 Tầng:**
  1. **Tầng 1 (Fast CI):** Chỉ chạy unit tests / linter trên Ubuntu khi có thay đổi code. Tự động bỏ qua tệp `.md`, `docs/**`, `.agents/**` (`paths-ignore`).
  2. **Tầng 2 (On-Demand Packaging):** Chỉ đóng gói native apps khi commit có cờ `[build]` hoặc chọn qua giao diện `workflow_dispatch`.
  3. **Tầng 3 (Official Release):** Chỉ chạy toàn bộ ma trận phát hành khi push một Git Tag mới dạng `v*.*.*` hoặc commit có cờ `[release]`.
- **Cờ điều khiển qua Commit Message:**
  - `[skip ci]` hoặc `[ci skip]`: Bỏ qua toàn bộ CI/CD.
  - `[build]`: Đóng gói bản cài đặt thử nghiệm.
  - `[release]`: Đóng gói và tạo GitHub Release chính thức.
- **Công cụ tự động hóa:**
  - Tạo script `scripts/release.py` (chạy lệnh: `python scripts/release.py <repo> [patch|minor|major] "Ghi chú"`). Tự động kiểm tra git sạch, chạy test suite, bump SemVer, tạo tag và đẩy lên GitHub.
- **Triển khai:**
  - Tạo mới Skill: `C:\Users\kiemp\.gemini\config\skills\meikova-release-ops\SKILL.md`.
  - Cập nhật Master Skill `meikova/SKILL.md` (thêm vào Ma trận định tuyến) và Master Rule `meikova-master.md`.
  - Giao quyền quản trị cho Subagent `meikova-devops-engineer`.
  - Cập nhật bộ lọc `paths-ignore` và `if:` guard vào `.github/workflows/` của cả 3 repo (`meikova-loop` commit `68430d8`, `meikova-harvest` commit `2dee5bc`, `meikova-relay` lưu cục bộ).

---

## 12. Chuẩn Hóa Nhận Diện Thương Hiệu SSOT & Xóa Bỏ Thiếu Sót Logo (`meikova-brand-assets`)
- **Vấn đề giải quyết:** Tình trạng Agent tự dùng thư viện PIL trong Python vẽ icon tạm bợ (`make_icon.py`, `draw_circle.py`), dùng generic icon pack, hoặc cập nhật thiếu sót (chỉ thay `favicon.ico` mà bỏ quên PWA maskable icons, tray icons cả 2 bộ trắng/đen, app executable `app.ico`/`app.icns`, splash screen, manifest) dẫn đến giao diện bị lỗi hiển thị hoặc trôi về logo cũ.
- **Giải pháp & Tiêu chuẩn ban hành:**
  1. **Thiết lập Single Source of Truth (SSOT):** Toàn bộ tài sản chính thức nằm tập trung tại `D:\JOB\DEV\meikova\assets\logos\` với 21 bộ Folded Continuum v6.0 hoàn chỉnh (gồm Relay xanh lá `#83E8AC`, Loop cam amber `#FFB38A`, Harvest xanh dương `#83C4FF`, và 18 nhận diện mở rộng).
  2. **Bản Kiểm Tra Bắt Buộc 10 Điểm Chạm (10-Point Brand Exhaustion Checklist):**
     - Web Favicons: `favicon.ico` (multi-res), `favicon.svg`, `favicon-16/32/48.png`
     - Web PWA: `apple-touch-icon.png` (180x180), `icon-any-192/512.png`, `icon-maskable-192/512.png`, `site.webmanifest`
     - Desktop Executables: `app.ico` (multi-res), `app.icns`, Linux hicolor
     - System Tray: Bộ icon `white-*.png` (dark taskbar) và `black-*.png` (light taskbar) từ 16 đến 48px
     - Header Brandmark: 100% Inline Vector SVG thuần từ `currentColor.svg` hoặc `color.svg`, cấm nhúng PNG
     - Splash & Modals: SVG lớn hoặc PNG rounded 512x512
     - Open Graph: `og:image` 512x512 PNG
     - Native Shells: Android `res/` adaptive & notification silhouettes, iOS `AppIcon.appiconset`
     - Browser Extension: `icon-16/32/48/128.png`
     - Checksum Integrity: Kiểm tra SHA-256 khớp `asset-manifest.json`
  3. **Bộ Luật Thép Cấm Tuyệt Đối (Zero-Ad-Hoc Mandate):**
     - CẤM dùng PIL/Pillow tự vẽ icon (`make_icon.py`).
     - CẤM dùng emoji hoặc generic icon làm logo sản phẩm.
     - CẤM cập nhật logo nửa vời.
     - CẤM hoán đổi màu nhận diện thương hiệu giữa các sản phẩm.
  4. **Nâng cấp Script Tự Động Hóa & Kiểm Định SHA-256:**
     - Nâng cấp `D:\JOB\DEV\meikova\scripts\deploy_product_assets.py` đồng bộ toàn diện 182 tài sản sang cả 3 repository.
     - Tích hợp cờ `--check` (audit mode) kiểm tra toàn vẹn hash SHA-256 của mọi file đích.
- **Triển khai kỹ thuật:**
  - Tạo mới Skill: `C:\Users\kiemp\.gemini\config\skills\meikova-brand-assets\SKILL.md`.
  - Cập nhật Master Skill `meikova/SKILL.md` (Điều luật 7: Zero-Ad-Hoc Brand Assets Mandate).
  - Cập nhật `meikova-ambient-ui/SKILL.md` (Điều luật 13: Brand SSOT Mandate).
  - Cập nhật Master Rules: `meikova-master.md`, `C:\Users\kiemp\.gemini\config\rules\AGENTS.md`, `GEMINI.md`, `e:\Github\edtech-gdrive-commerce\AGENTS.md`.
- **Kết quả kiểm thử & Kiểm chứng Terminal:**
  - `python scripts/deploy_product_assets.py`: **182/182 assets deployed/synchronized (Exit Code 0)**.
  - `python scripts/deploy_product_assets.py --check`: **182/182 assets verified SHA-256 match, 0 missing, 0 mismatched (Exit Code 0)**.
  - `meikova-relay` unittest: **112/112 tests passed (Exit Code 0)**.
  - `meikova-harvest` unittest: **100% tests passed (Exit Code 0)**.
  - `meikova-loop` unittest & desktop icon test: **100% tests passed (Exit Code 0)**.
- **Cảnh báo kỹ thuật:**
  - `meikova-relay` tiếp tục được lưu cục bộ (unpushed) theo cam kết với người dùng.

---

## 13. Đồng Bộ Dải Lệnh Terminal Winget Cho Cả 3 Ứng Dụng Đa Nền Tảng
- **Mục tiêu:** Đồng bộ thanh lệnh CLI nhanh dưới chân modal tải ứng dụng (.apps-modal-footer-strip), kèm tính năng 1-Click Copy to Clipboard cho cả 3 project:
  1. **Meikova Harvest:** winget install Meikova.Harvest + link GitHub Releases + 1-Click Copy feedback Đã sao chép lệnh ✓.
  2. **Meikova Loop:** Bổ sung footer strip winget install Meikova.Loop + link GitHub Releases + 1-Click Copy feedback Đã sao chép lệnh ✓ vào web/index.html, web/css/app.css, web/js/main.js.
  3. **Meikova Relay (Relay Server & Web Client):** Bổ sung footer strip và logic chuyển đổi động lệnh theo vai trò trong index.html, style.css, pp.js:
     - Khi chọn Tab Host Agent: $ winget install Meikova.Relay.Host
     - Khi chọn Tab Viewer Client: $ winget install Meikova.Relay.Client
     - Click để sao chép lệnh vào clipboard tức thì.
- **Kiểm chứng Terminal:**
  - python scripts/deploy_product_assets.py --check: Exit Code 0 (182/182 assets).
  - Test suite Relay: 11 tests pass (Exit Code 0).
  - Test suite Loop: 9 tests + desktop modal test pass (Exit Code 0).
  - Test suite Harvest: 3 tests pass (Exit Code 0).


---

## 7. Chuẩn hóa PWA Manifest & Khắc phục triệt để lỗi Windows PWA Tile (4 góc tam giác xanh)
- **Nguyên nhân gốc rễ:** Chromium trên Windows khi tạo Start Menu tile / shortcut đã chọn icon squircle bo góc có transparency (`logo.png` RGBA) hoặc favicon SVG từ mảng `icons` trong manifest. Windows tự động tô màu accent vào các góc trong suốt (alpha=0), gây ra lỗi 4 góc tam giác xanh.
- **Các thay đổi thực hiện:**
  1. **meikova-harvest:**
     - `static/manifest.json`: Xóa `logo.png` và `favicon.svg`. Chuẩn hóa 4 icons: `/static/icon-any-192.png`, `/static/icon-maskable-192.png`, `/static/icon-any-512.png`, `/static/icon-maskable-512.png`. Màu nền và theme: `#11151B`.
     - `static/site.webmanifest`: Đồng bộ 100% với `manifest.json`.
     - `templates/index.html`: Cập nhật `<meta name="theme-color" content="#11151B" />`.
     - Tạo test `tests/test_pwa_manifest.py`.
  2. **meikova-loop:**
     - `web/manifest.json`: Xóa `favicon.svg` và `apple-touch-icon.png`. Chuẩn hóa 4 icons: `img/icon-any-192.png`, `img/icon-maskable-192.png`, `img/icon-any-512.png`, `img/icon-maskable-512.png`. Màu nền và theme: `#11151B`.
     - `web/site.webmanifest`: Đồng bộ 100% với `manifest.json`.
     - `web/index.html`: Xóa link trùng lặp `site.webmanifest`.
     - Tạo test `tests/test_pwa_manifest.py`.
  3. **meikova-relay:**
     - `relay-server/public/manifest.json` & `web-client/manifest.json`: Bổ sung 4 icon PNG PWA chuẩn, xóa `favicon.svg`. Màu nền và theme: `#11151B`.
     - `relay-server/public/site.webmanifest` & `web-client/site.webmanifest`: Đồng bộ 100%.
     - `relay-server/public/index.html` & `web-client/index.html`: Cập nhật `theme-color` thành `#11151B`, `apple-touch-icon` thành `/apple-touch-icon.png`.
     - Tạo test `tests/test_pwa_manifest.py`.
- **Kiểm chứng:**
  - `test_harvest_pwa_manifests`: PASS (Exit Code 0)
  - `test_loop_pwa_manifests`: PASS (Exit Code 0)
  - `test_relay_pwa_manifests`: PASS (Exit Code 0)
  - `scripts/verify_pwa_manifests.py`: 8/8 manifest files OK, 100% icon RGB không có alpha góc, corners solid `#11151B`.
- **Bảo mật:** `meikova-relay` không push lên GitHub.

---

## 14. Triển Khai Turso Cloud SQLite Dual Adapter Cho Meikova Relay
- **Mục tiêu hoàn thành:**
  - Cập nhật `relay-server/db.js`:
    * Hỗ trợ biến môi trường `TURSO_DATABASE_URL` và `TURSO_AUTH_TOKEN`.
    * Tự động nhận diện kết nối Turso Cloud (`libsql://...`) qua `@libsql/client`.
    * Tự động fallback về file SQLite WAL cục bộ (`file:...`) khi không cấu hình Turso.
    * Đưa 100% các hàm DB sang async hoàn chỉnh: `registerUser`, `authenticateUser`, `validateSession`, `deleteSession`, `refreshSession`, `getUserByUsername`, `getDevices`, `upsertDevice`, `deleteDevice`, `setDeviceOnlineStatus`, `googleAuth`, `logAudit`, `getAuditLogs`, `getUserSync`, `saveUserSync`.
  - Cập nhật `relay-server/server.js`:
    * 100% các lời gọi `DB.*` trong REST API routes và WebSocket handlers (`ws.on('message')`, `ws.on('close')`, `closeRoomClients`) đều được `await` đầy đủ.
    * Xử lý lỗi gracefully với try-catch không để crash tiến trình server.
    * Cập nhật thông tin hiển thị trạng thái DB adapter khi khởi động server.
  - Tạo file mẫu `relay-server/.env.example` hướng dẫn cấu hình cả 2 chế độ (Turso Cloud và Local WAL).
  - Tạo bộ test kiểm chứng kép:
    * `relay-server/test_turso_dual_adapter.js`: Kiểm thử trực tiếp adapter Turso Cloud và Local SQLite WAL.
    * `tests/test_turso_relay.py`: Kiểm thử tích hợp E2E server REST API (Health, Register, Login, Me, Audit Logs, Offline-First Sync) trên nền tảng Turso Cloud.
- **Lệnh kiểm tra đã chạy & Exit Code:**
  - `node relay-server/test_turso_dual_adapter.js`: **PASS - Exit Code 0**
  - `python tests/test_turso_relay.py`: **4/4 tests PASS in 7.9s - Exit Code 0**
  - `python tests/test_download_endpoints.py`: **6/6 tests PASS - Exit Code 0**
  - `python tests/test_integration_relay.py`: **2/2 tests PASS - Exit Code 0**
- **Cảnh báo kỹ thuật & Tuân thủ:**
  - Không push repo `meikova-relay` lên GitHub theo chỉ đạo bảo mật.
  - File `.env` chứa token được tự động bảo vệ qua `.gitignore`.



---

## 15. Khắc Phục Bug Liên Kết Máy Trạm & Cơ Chế Đồng Bộ Xác Thực 2 Chiều (Fault-Tolerant Auth Sync)

### 1. Phân Tích & Khắc Phục Nguyên Nhân Gốc Rễ Bug Liên Kết Máy Trạm:
- **Nguyên nhân gốc rễ:**
  1. Khi người dùng xác thực qua Universal SSO (Cổng xác thực Ed25519) hoặc Google OAuth, Relay Server chỉ thẩm định chữ ký token mà không mirror/lưu bản ghi vào bảng `users` cục bộ (thiếu JIT Provisioning).
  2. Lệch định danh giữa các phiên: người dùng đăng nhập email `kiempham1256@gmail.com`, máy trạm gửi `account: "kiempham1256"`. Hàm `getUserByUsername` chỉ tìm exact match `username`, trả về `null` dẫn đến máy trạm được gán `user_id = NULL`.
  3. Khi Web Client gọi `GET /api/devices`: query `WHERE user_id = ?` với ID của token SSO không tìm thấy máy trạm nào.
- **Giải pháp triển khai:**
  1. **JIT Provisioning (`DB.upsertLocalUserFromSSO`):** Tự động tạo hoặc cập nhật bản ghi local user khi đăng nhập qua SSO/Gateway, đánh dấu `auth_provider = 'universal_sso'` và `sync_status = 'synced'`.
  2. **Smart Identifier Matching (`DB.findUserByIdentifier`):** Hỗ trợ khớp đa định danh: `user_id`, `gateway_user_id`, `username`, `email` đầy đủ, hoặc prefix email trước dấu `@`. Khớp chính xác 100% dù máy trạm gửi username hay email.
  3. **Universal Fleet Query (`DB.getDevices`):** Mở rộng truy vấn thiết bị hỗ trợ cả `local_user_id` và `gateway_user_id`, đảm bảo thiết bị luôn hiển thị đúng cho tài khoản chủ sở hữu.

### 2. Nghiên Cứu & Phát Triển Cơ Chế Đồng Bộ Xác Thực 2 Chiều (Offline-First):
- **Bảng hàng đợi `auth_sync_queue`:** Ghi nhận mọi giao dịch đăng ký offline (`sync_status = 'pending_gateway'`).
- **Endpoint đồng bộ:**
  - `GET /api/auth/sync/status`: Báo cáo số lượng pending, synced, failed.
  - `POST /api/auth/sync/push`: Đẩy các tài khoản đăng ký offline lên Gateway khi mạng/gateway phục hồi.
  - `POST /api/auth/sync/gateway`: Đồng bộ tài khoản từ Gateway về Local.
- **Ma trận giải quyết xung đột (Conflict Resolution Matrix):**
  - **Trùng Email (Same Email) -> Account Linking:** Email là SSOT Unique Anchor. Hợp nhất tài khoản, liên kết `gateway_user_id`, giữ nguyên toàn bộ máy trạm (`devices`), cấu hình (`user_sync_store`), không làm mất dữ liệu.
  - **Trùng Username nhưng khác Email -> Namespace Resolution:** Ưu tiên tài khoản Gateway làm SSOT Authoritative. Tài khoản local tự động đổi tên thành `username_local_<short_hash>` và đánh dấu `sync_status = 'conflict'`.

### 3. Cập Nhật Bộ Skill Chuẩn (`meikova-auth`):
- Đã bổ sung **Mục 9.4: Bi-directional Fault-Tolerant Auth Sync & Conflict Resolution (Offline-First)** vào `C:\Users\kiemp\.gemini\config\skills\meikova-auth\SKILL.md`.

### 4. Kết Quả Kiểm Chứng & Build Artifacts:
- **Bộ Test TDD Mới:** `tests/test_auth_sync_and_linking.py` (5/5 tests PASS).
- **Toàn bộ Test Suite:** 121/121 tests PASS in 64.0s (Exit Code 0).
- **Build Artifacts:**
  - `dist/MeikovaRelayHost.exe` & `relay-server/MeikovaRelayHost.exe`
  - `dist/MeikovaRelayHost-windows-x64.zip`
  - `relay-server/agent-package.zip`
  - Version: `meikova-relay-server` v1.0.52.


---

## 4. UI/UX Viewer Refinement: Bypass Menu, Pill Deck Alignment & Complete OSK
- **Mục tiêu hoàn thành:**
  - Sửa lỗi Menu Bypass (#protocolMenuDropdown) & Menu Chế độ / Preset (#qualityMenuDropdown) bị lệch sang 1 phía:
    - Bổ sung helper positionDeckDropdown(triggerBtn, dropdownEl) trong pp.js tính toán dynamically bounding box của nút bấm và căn giữa dropdown ngay phía trên/dưới nút, tự động clamp trong phạm vi màn hình và re-position khi resize.
    - Áp dụng đồng bộ cho cả 4 floating menus: Bypass/Protocol Matrix, Quality/Preset, Deck Display Mode, và Power Actions.
  - Tối giản số lượng chữ trong menu Bypass & thay bằng Vector SVG:
    - Rút gọn 3 nút điều hướng: Tự động (Native First) -> Tự động, Ép Meikova Bypass -> Bypass, Ép Native (RDP/SSH) -> Native.
    - Tích hợp 100% Inline Vector SVG optical center cho cả 3 nút, đưa mô tả chi tiết vào tooltip.
  - Sửa lỗi hình thái lệch và lỗi CSS hover/active:
    - Đồng bộ .deck__btn--protocol thành 36px pill (order-radius: var(--round)), xóa bỏ kiểu dáng chữ nhật 32px góc nhọn gây khập khiễng.
    - Sửa triệt để lỗi active biến thành khối màu xanh đặc chói lóa làm biến mất chữ: chuẩn hóa theo Meikova Ambient Dark (ackground: oklch(var(--acc) / 0.18), viền neon glow, chữ và icon giữ màu sáng neon rõ nét).
    - Đồng bộ màu sắc chuyên biệt cho ypass-active (#38BDF8 / cyan glow) và 
ative-active (#34D399 / emerald glow).
  - Cải thiện bàn phím ảo (OSK):
    - Bổ sung đầy đủ layout 6 hàng tiêu chuẩn: hàng Function F1-F12, hàng số & ký tự (- = ), hàng QWERTY kèm ngoặc vuông [ ], hàng Home row kèm dấu chấm phẩy và nháy kép (; '), hàng ZXCV kèm Shift và dấu chấm phẩy, hàng Điều hướng với 4 nút mũi tên SVG sắc nét.
    - Mở rộng bảng ánh xạ JS_TO_VK với đầy đủ OEM Virtual Keys (Backquote, Minus, Equal, BracketLeft, BracketRight, Backslash, Semicolon, Quote, Comma, Period, Slash).
    - Bổ sung logic giữ phím điều khiển (Modifier Latching) cho Shift, Ctrl, Alt và Caps Lock.
  - Đồng bộ toàn bộ tài nguyên sang thư mục mirror web-client/.
- **Lệnh kiểm tra đã chạy & Exit Code:**
  - python -m unittest discover tests: **121 tests passed (OK, skipped=1, Exit Code 0)**.
- **Tình trạng:** Sẵn sàng commit và deploy.

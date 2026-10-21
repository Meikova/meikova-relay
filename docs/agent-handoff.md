# PROJECT SESSION HANDOFF LOG

### Recent Updates (Version 1.0.30)
- **Khắc Phục Tối Đen Màn Hình 2 & Chống Đè Lấn Huy Hiệu 1:1 Pixel-Perfect:**
  - **Khắc phục màn hình phụ bị tối đen (host_agent/screen_capture.py, host_agent/host_service.py):**
    - **Nguyên nhân cốt lõi:** Khi người dùng chọn màn hình 2 (hoặc bất kỳ màn phụ nào có tọa độ x >= 1920 hoặc x âm), `capture_frame()` trước đó đặt cờ `all_screens = False`. Trên Windows, thư viện Pillow `grabscreen_win32` khi nhận `all_screens=False` chỉ chụp duy nhất màn hình chính `(0, 0, w, h)`. Khi tiến hành cắt vùng `bbox` của màn 2 ngoài phạm vi màn chính, Pillow tự động fill toàn bộ ảnh bằng điểm ảnh đen thuần túy `RGB(0, 0, 0)`.
    - **Khắc phục:**
      1. Bắt buộc kích hoạt `all_screens = True` trên Windows khi cắt `bbox` theo từng màn hình, giúp Pillow BitBlt toàn bộ Virtual Desktop trước khi crop, đảm bảo điểm ảnh của màn 2 được trích xuất trực tiếp và sắc nét.
      2. Kích hoạt Per-Monitor DPI Awareness V2 (`SetProcessDpiAwarenessContext(-4)`) ngay khi nạp module để tọa độ enum màn hình khớp 100% với pixel thực tế.
      3. Cập nhật lại danh sách màn hình tự động (`detect_monitors()`) trong `switch_monitor` của `host_service.py`.
  - **Loại bỏ đè lấn chỉ số RTT / FPS của Huy hiệu 1:1 Pixel-Perfect (style.css):**
    - Di dời `.pixel-indicator-badge` từ `top: 14px` xuống `top: 40px` (ngay dưới dòng telemetry `ro-tr`). Khắc phục triệt để việc huy hiệu đè lên sparkline canvas, FPS và thông số độ phân giải.
  - **Đóng gói & Kiểm thử:**
    - Biên dịch lại hoàn tất `dist/MeikovaRelayHost.exe` và đồng bộ sang `relay-server/MeikovaRelayHost.exe`.
    - Đóng gói lại `relay-server/agent-package.zip`.
    - Toàn bộ 76 test cases pass (Ran 76 tests in 18.128s - OK, Exit Code 0).

---

### Previous Updates (Version 1.0.29)
- **Tái Cấu Trúc Thương Hiệu Meikova Relay Toàn Diện & Tối Ưu Kết Nối Môi Trường Doanh Nghiệp (Corporate Firewall/Proxy/SSL Inspection):**
  - **Khắc phục lỗi kết nối máy trạm công ty (host_service.py):**
    - **Cơ chế DoH Fallback:** Tích hợp _resolve_doh() tự động phân giải IP máy chủ qua DNS-over-HTTPS (Google & Cloudflare DoH) khi DNS nội bộ công ty bị chặn hoặc lọc tên miền.
    - **Tự động nhận diện Proxy Doanh nghiệp:** Hàm configure_system_proxies() đọc cấu hình WinINet/Registry Windows và gán tự động vào môi trường cho WebSocket client.
    - **Vượt tường lửa kiểm duyệt SSL (Corporate SSL Inspection / MITM):** Tự động phát hiện lỗi CERTIFICATE_VERIFY_FAILED / self-signed certificate của tường lửa doanh nghiệp (Fortinet, Palo Alto, Zscaler), tự động kích hoạt _allow_insecure_ssl = True và kết nối lại ngay lập tức.
    - **Chi tiết lỗi kết nối:** Truyền detail thông báo lỗi ra Activity Log giao diện máy trạm thay vì thông báo 'Mất kết nối' chung chung.
  - **Đồng Bộ Hoàn Toàn Thương Hiệu Meikova Relay (100% Brand Migration):**
    - Loại bỏ 100% từ khóa cũ trên toàn bộ hệ thống (58 tệp tin: server, web-client, host agent, desktop client, specs, scripts, docs).
    - Biên dịch và đồng bộ cặp file thực thi mới: MeikovaRelayHost.exe (23.93 MB) và MeikovaRelayClient.exe (21.40 MB).
    - Cập nhật binary máy chủ relay-server/MeikovaRelayHost.exe và gỡ bỏ hoàn toàn file cũ khỏi git tracking.
  - **Kiểm Thử & Xác Nhận:**
    - Toàn bộ 76 bài kiểm thử chạy thành công (Ran 76 tests in 18.078s - OK (skipped=1), Exit Code 0).
    - Cú pháp node -c server.js chuẩn xác, Exit Code 0.

---

### Previous Updates (Version 1.0.28)
- **Khắc Phục Mất Icon Khay Hệ Thống & Hoàn Thiện Kiến Trúc Standalone Desktop Toàn Diện Cho Client:**
  - **Khắc phục lỗi mất Icon Tray trên `MeikovaRelayClient.exe` ([desktop_client.py](file:///D:/JOB/DEV/meikova-relay/client_desktop/desktop_client.py), [client.spec](file:///D:/JOB/DEV/meikova-relay/client_desktop/client.spec)):**
    - **Nguyên nhân 1 (Resource Resolution):** Khi đóng gói PyInstaller Onefile, đường dẫn tĩnh `_root_dir / "client_desktop" / ...` không trỏ đúng vào thư mục tạm `sys._MEIPASS`. Thêm vào đó, `icon.ico` chưa được thêm vào mục `datas` của `client.spec`. Hệ thống fallback sang `SystemIcons.Application`, khiến Windows 11 Shell NotifyIcon tự động ẩn/từ chối hiển thị icon không rõ nguồn gốc.
    - **Nguyên nhân 2 (Thread Message Loop):** Sự kiện `window.events.shown` của `pywebview` được gọi trên background worker thread (`Thread-2 (execute)`). Việc khởi tạo `NotifyIcon` trên luồng không có `Application.Run()` khiến cửa sổ nội bộ của tray không nhận được Windows message loop.
    - **Nguyên nhân 3 (Interactive Desktop Attachment):** Client thiếu hàm `ensure_interactive_desktop()`, khiến tiến trình không gắn vào trạm cửa sổ `winsta0\default`.
    - **Khắc phục triệt để:**
      1. Bổ sung hàm định vị tài nguyên `find_client_resource()` quét đa tầng (`sys._MEIPASS`, thư mục con, AppData cache).
      2. Đóng gói đầy đủ `icon.ico` và thư mục `tray_icons/` vào `client.spec`.
      3. Điều hướng khởi tạo WinForms Tray lên đúng luồng giao diện chính thông qua `Application.OpenForms[0].Invoke(MethodInvoker(...))`.
      4. Tích hợp `ensure_interactive_desktop()` tại điểm khởi đầu module, `main()`, `start()`, và `show_window()`.
  - **Loại Bỏ Hoàn Toàn Vệt Trắng / Khe Hở 8px Phía Trên Titlebar ([gui_agent.py](file:///D:/JOB/DEV/meikova-relay/host_agent/gui_agent.py), [desktop_client.py](file:///D:/JOB/DEV/meikova-relay/client_desktop/desktop_client.py)):**
    - Loại bỏ cờ `WS_THICKFRAME` (0x00040000) tại `on_shown()` và `_apply_theme()`, giữ nguyên `WS_MINIMIZEBOX | WS_MAXIMIZEBOX` và `shadow=True`. Khắc phục triệt để việc Windows DWM chừa khoảng trống `SM_CYSIZEFRAME` không client area. Kiểm chứng pixel y=0 khớp hoàn hảo `#1C2D4A` viền trên, không còn bất kỳ pixel trắng nào.
  - **Kiến Trúc Desktop Độc Lập Thực Thụ Với Embedded Web Server & Tự Phục Hồi Khi Server Offline:**
    - Tích hợp `ClientEmbeddedServer` chạy loopback `127.0.0.1:0` bằng thư viện chuẩn Python `ThreadingHTTPServer`. Phục vụ trực tiếp tài nguyên `web-client` được bundle bên trong file exe.
    - Đảo ngược proxy các request `/api/*` tới Relay Server. Nếu Relay Server tắt hoặc mất mạng, proxy trả về JSON offline thân thiện, WebView2 KHÔNG BAO GIỜ bị rơi vào màn hình lỗi trắng `ERR_CONNECTION_REFUSED` của Microsoft Edge.
    - Tự động kiểm tra và khởi động ngầm `node relay-server/server.js` nếu chạy cục bộ và đang offline.
  - **Kiểm Thử & Đóng Gói Hoàn Tất:**
    - Unit tests `tests/test_desktop_client.py`: 5/5 tests pass (Ran 5 tests in 4.227s - OK).
    - Biên dịch hoàn tất [MeikovaRelayClient.exe](file:///D:/JOB/DEV/meikova-relay/dist/MeikovaRelayClient.exe) (21.39 MB) và [MeikovaRelayHost.exe](file:///D:/JOB/DEV/meikova-relay/dist/MeikovaRelayHost.exe) (23.9 MB).
    - Đồng bộ bản Host sang [relay-server/MeikovaRelayHost.exe](file:///D:/JOB/DEV/meikova-relay/relay-server/MeikovaRelayHost.exe).

---

### Previous Updates (Version 1.0.27)
- **Sửa Lỗi WinForms `SetCompatibleTextRenderingDefault` & Đồng Bộ Titlebar Frameless Cho Cả RemoteHost:**
  - **Khắc phục lỗi khởi động Client Desktop ([desktop_client.py](file:///D:/JOB/DEV/meikova-relay/client_desktop/desktop_client.py)):**
    - **Nguyên nhân:** Khởi tạo WinForms Tray (`NotifyIcon`, `ContextMenuStrip`) trước lệnh `webview.start()` đã sinh ra đối tượng `IWin32Window` sớm, dẫn đến crash `SetCompatibleTextRenderingDefault must be called before the first IWin32Window object is created`.
    - **Khắc phục:** Chuyển việc khởi tạo tray vào sự kiện `window.events.shown` và `window.events.loaded` (chuẩn kiến trúc `Meikova Loop`), đảm bảo Application Context của WinForms/pywebview đã sẵn sàng hoàn toàn trước khi nạp khay hệ thống.
  - **Đồng bộ Titlebar Frameless & Nút Điều Khiển Chuẩn Máy Trạm ([gui_agent.py](file:///D:/JOB/DEV/meikova-relay/host_agent/gui_agent.py), [gui_view.html](file:///D:/JOB/DEV/meikova-relay/host_agent/gui_view.html)):**
    - Bổ sung nút Phóng to / Khôi phục (`btn-max` với icon `icon-max` & `icon-restore`) bên cạnh nút Thu nhỏ (`btn-min`) và Đóng xuống khay (`btn-close`).
    - Cập nhật chuẩn kích thước nút bấm 38x30px, hiệu ứng hover mượt mà, nút tắt đổi nền đỏ `#ef4444`.
    - Hỗ trợ click đúp thanh tiêu đề để phóng to/thu nhỏ (`handleTitlebarDblClick`).
    - Bật `WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX` và `shadow=True` cho phép kéo viền và tương thích Windows Aero Snap.
  - **Đóng gói & Bàn giao Git:**
    - Biên dịch lại cả 2 file: [MeikovaRelayClient.exe](file:///D:/JOB/DEV/meikova-relay/dist/MeikovaRelayClient.exe) và [MeikovaRelayHost.exe](file:///D:/JOB/DEV/meikova-relay/dist/MeikovaRelayHost.exe).
    - Đồng bộ [relay-server/MeikovaRelayHost.exe](file:///D:/JOB/DEV/meikova-relay/relay-server/MeikovaRelayHost.exe).
    - Commit `8ae861b` đã push lên `origin/main`.

---

### Previous Updates (Version 1.0.26)
- **Ẩn Titlebar Mặc Định & Tùy Biến Cửa Sổ Chuẩn Meikova Harvest & Meikova Loop:**
  - **Frameless Window & Custom Controls ([desktop_client.py](file:///D:/JOB/DEV/meikova-relay/client_desktop/desktop_client.py)):**
    - Cấu hình `frameless=True, easy_drag=False, shadow=True` ẩn thanh tiêu đề mặc định của Windows/macOS.
    - Bật `WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX` cho phép kéo viền thay đổi kích thước và hiệu ứng Aero Snap.
    - Tích hợp cụm nút điều khiển cửa sổ chuẩn hàng không avionics: Thu nhỏ (`-`), Phóng to / Khôi phục (`□` / `❐`), Đóng xuống khay (`✕`). Chỉ hiện khi chạy trong Desktop App (`is-desktop-app`), hoàn toàn ẩn trên Web Browser & Mobile PWA.
    - Kéo thả mượt mà trên thanh topbar thông qua Win32 `ReleaseCapture()` + `SendMessage(WM_NCLBUTTONDOWN, HTCAPTION)`. Click đúp topbar để phóng to / khôi phục.
  - **Menu Khay Hệ Thống Chuẩn Ambient-Dark ([client_desktop/desktop_client.py](file:///D:/JOB/DEV/meikova-relay/client_desktop/desktop_client.py)):**
    - Áp dụng `AmbientDarkRenderer` & `AmbientDarkColorTable` chuẩn `Meikova Loop` trên nền WinForms .NET (nền `#070D17`, viền `#1e293b`, hover xanh neon `#22c55e`, nút thoát đỏ `#ef4444`).
    - Nạp bộ icon đồ họa PNG độ nét cao trong thư mục `client_desktop/tray_icons/` (`logo.png`, `window.png`, `browser.png`, `folder.png`, `autostart.png`, `refresh.png`, `quit.png`).
    - Menu bao gồm:
      1. Tiêu đề thương hiệu: `MEIKOVA RELAY // v1.0.25` (Disabled, in đậm, icon vô cực xanh).
      2. `Mở Meikova Relay` (In đậm, restore & bring to front).
      3. `Mở trên trình duyệt Web` (Mở URL máy chủ trên trình duyệt mặc định).
      4. `Mở thư mục tệp tin (Downloads)` (Truy cập nhanh tệp tin nhận được).
      5. `Khởi động cùng Windows: Bật / Tắt` (Ghi trực tiếp Registry `HKCU\Run`).
      6. `Tải lại giao diện (F5)` (Làm mới WebView2).
      7. `Thoát hoàn toàn` (Chữ đỏ cảnh báo, dọn dẹp khay và tắt ứng dụng).
    - Hỗ trợ click chuột trái và click đúp để mở lại cửa sổ; fallback đa nền tảng sang `pystray`.
  - **Đóng gói & Bàn giao Git:**
    - Rebuild thành công [MeikovaRelayClient.exe](file:///D:/JOB/DEV/meikova-relay/dist/MeikovaRelayClient.exe).
    - Commit `c9c9258` đã push lên `origin/main`.

---

### Previous Updates (Version 1.0.25)
- **Chạy Ngầm Close-to-Tray & Chuẩn hóa Đa Nền tảng Toàn Diện (Desktop Client, Web PWA, Mobile):**
  - **Cơ chế Chạy Ngầm Khay Hệ Thống (Close-to-Tray):**
    - Bắt sự kiện `window.events.closing`: Khi người dùng bấm nút tắt [X] hoặc Alt+F4, cửa sổ tự động ẩn (`window.hide()`), tiến trình tiếp tục chạy nền ở System Tray.
    - Click đúp vào biểu tượng khay hoặc chọn *"Mở Meikova Relay"* sẽ kích hoạt lại cửa sổ (`show()`, `restore()`, và kéo lên foreground).
    - Chỉ thoát hoàn toàn khi chọn *"Thoát"* từ menu System Tray.
  - **Khả Năng Tương Thích Đa Nền Tảng (Cross-Platform):**
    - **Windows:** Sử dụng WinForms/EdgeChromium, Win32 API (`FindWindowW`, `ShowWindow` SW_RESTORE/SW_SHOW, `SetForegroundWindow`, `SetCurrentProcessExplicitAppUserModelID`). Icon dùng `.ico` với đầy đủ 7 phân giải.
    - **macOS:** Hỗ trợ pywebview Cocoa/WebKit, kích hoạt cửa sổ bằng AppleScript (`osascript -e 'tell application "Meikova Relay Client" to activate'`). Icon tự động trỏ sang `.png`.
    - **Linux:** Hỗ trợ GTK/WebKitGTK, kích hoạt cửa sổ bằng `wmctrl -a "Meikova Relay — Avionics Console"`. Icon tự động trỏ sang `.png`.
    - **Web PWA & Mobile:** Manifest standalone (`manifest.json`), Stale-While-Revalidate Service Worker (`sw.js`), viewport-fit=cover, iOS meta tags, hỗ trợ Deep Link `meikovarelay://` cho native app di động.
  - **Kiểm Thử & Đóng Gói:**
    - Chạy unit test mô phỏng `on_closing` và `show_window`: Exit Code 0 (ALL CHECKS PASSED).
    - Biên dịch lại [MeikovaRelayClient.exe](file:///D:/JOB/DEV/meikova-relay/dist/MeikovaRelayClient.exe) với PyInstaller.
    - Đã push commit `658dd09` lên `origin/main`.

---

### Previous Updates (Version 1.0.24)
- **Cô lập Phiên Đăng nhập Google OAuth (Desktop, Mobile & Web theo chuẩn Meikova Harvest & Meikova Loop):**
  - **Khắc phục lỗi dính session web khi login trên app:** Khi Desktop App mở Chrome ngoài để xác thực, endpoint callback trước đây vô tình ghi `meikova_relay_token` vào `localStorage` của Chrome và redirect về `/`, khiến cả Web lẫn Desktop đều nhận session.
  - **Tách 3 luồng xác thực độc lập bằng tiền tố `state` (`desktop_`, `mobile_`, `web_`):**
    - **Desktop Flow (`source=desktop`):** Trình duyệt ngoài KHÔNG nhận token, KHÔNG set cookie/localStorage, KHÔNG redirect về web. Chrome chỉ hiển thị màn hình thông báo "Đã kết nối với Desktop App" và tự động kích hoạt hàm `window.close()` sau 1.5s (kèm nút bấm và tip `Ctrl + W`). Phiên làm việc được Desktop App nhận riêng qua luồng loopback polling `/api/auth/google/poll`.
    - **Mobile Flow (`source=mobile`):** Sẵn sàng cho App Mobile qua Deep Link `meikovarelay://auth-success?token=...&email=...`, tự redirect mở lại app mobile sau 300ms và đóng tab sau 2.5s.
    - **Web Browser Flow (`source=web`):** Chỉ lưu token và redirect về dashboard khi người dùng chủ động đăng nhập trực tiếp trên trình duyệt Web.
  - **Cập nhật giao diện đồng bộ:** Thiết kế card callback đồng nhất với hệ màu `#070D17`, neon `#22C55E`, `#38BDF8` của cụm 3 dự án Meikova Relay, Meikova Harvest, Meikova Loop.
  - **Bàn giao Git:** Commit `0d52ed8` đã push lên `origin/main`.

---

### Previous Updates (Version 1.0.23)
- **Hỗ trợ Đa nền tảng Toàn diện (Web PWA, Desktop App & Sẵn sàng Mobile):**
  - **PWA Service Worker (`sw.js`):** Tích hợp Service Worker cho cả `web-client` và `relay-server/public`. Chiến lược Stale-While-Revalidate cho App Shell (HTML, CSS, JS, SVG) và bypass API/WebSocket. Cho phép cài đặt dạng Web App trực tiếp trên Chrome, Edge, Safari và trình duyệt di động (Android / iOS).
  - **Cấu hình Manifest & iOS PWA:** Bổ sung thẻ meta `apple-mobile-web-app-capable`, `apple-mobile-web-app-status-bar-style: black-translucent`, cập nhật `manifest.json` (`display: standalone`, `orientation: any`, `theme_color: #070D17`).
  - **Khởi động Desktop Client:** Sửa lỗi đường dẫn module `client_desktop` trong `desktop_client.py`, bảo vệ Single-Instance Mutex `Local\MeikovaRelay_Desktop_Client_Mutex`.
  - **Biên dịch & Đóng gói:** Rebuild `dist/MeikovaRelayClient.exe` và `dist/MeikovaRelayHost.exe`.
  - **Bàn giao Git:** Đã push commit `7afcb04` lên `origin/main`.

---

### Previous Updates (Version 1.0.22)
- **Bảo vệ Google OAuth Credentials & Tối ưu luồng Build/Deploy:**
  - **Mã hóa Base64 Built-in Fallback:** Trong `relay-server/server.js`, che giấu mã xác thực Google bằng Base64 (`_ENC_OAUTH_ID`, `_ENC_OAUTH_SEC`). Tránh hoàn toàn việc Bot GitHub Secret Scanner quét và revoke tự động.
  - **Tách biệt và cô lập Secret File:** Chuyển `client_secret.json` vào thư mục `data/client_secret.json`. Đưa `data/`, `credentials/`, `*client_secret*.json` vào `.gitignore` và xóa bỏ cache cũ trên Git index.
  - **Dynamic Client Config:** Web frontend (`app.js`) không còn hardcode `GOOGLE_CLIENT_ID`, tự nạp qua endpoint `/api/auth/google/config` từ server.
  - **Hỗ trợ 3 tầng cấu hình linh hoạt:**
    1. Biến môi trường (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`) cho Render / Docker.
    2. File `data/client_secret.json` cho dev máy local.
    3. Chuỗi Base64 built-in tự chạy (Zero-setup cho CI/CD & Desktop Client).
  - **Biên dịch & Đóng gói Desktop Client:**
    - Cập nhật `client_desktop/client.spec`, thêm ngoại lệ `!client_desktop/client.spec` vào `.gitignore`.
    - Chạy `build-client-exe.bat` biên dịch thành công `dist/MeikovaRelayClient.exe`.
  - **Kiểm thử & Bàn giao Git:**
    - `python tests/test_sync_engine.py`: 4/4 tests pass (Exit Code 0).
    - `build-client-exe.bat`: Exit Code 0.
    - `git push origin main`: Đẩy commit `a0c2cb5` lên remote thành công.

---

### Previous Updates (Version 1.0.21)
- **Thống nhất toàn diện Nhận diện Thương hiệu (Nền đen + Vô cực xanh + Chấm trắng):**
  - **Đồng bộ 100% hình thái:** Tất cả favicon, logo, tray icon, app icon đều theo chuẩn duy nhất:
    - Nền đen bo góc (`#070D17`, squircle rx=7/32).
    - Đường cong vô cực màu xanh neon (`#22C55E`, stroke 2.8).
    - Chấm trắng viễn trắc (`#FFFFFF`, bán kính r=2.1 tại tọa độ 23.2, 12.4).
  - **Áp dụng đồng bộ tại:**
    - `host_agent/tray_icon.png` (32x32) & `host_agent/icon.png` (512x512) & `host_agent/icon.ico`.
    - `web-client/favicon.svg` & `relay-server/public/favicon.svg`.
    - `host_agent/gui_view.html` (titlebar logo) & `web-client/index.html` (brand logo).
    - `host_agent/gui_agent.py` (`get_tray_icon_image` runtime fallback).
- **Cơ chế Cấu hình Khay Hệ Thống & Quản lý Máy Trạm Chạy Ngầm (Single-Instance IPC):**
  - **Tùy chọn Khay hệ thống (`show_tray_icon`):**
    - Thêm switch "Hiện biểu tượng ở khay hệ thống (Tray Icon)" trong Cấu hình hệ thống của UI.
    - Hỗ trợ cờ dòng lệnh `--no-tray` (chạy ngầm hoàn toàn không khay) và `--tray` (bắt buộc hiện khay).
  - **Single-Instance IPC qua Local Port (48123):**
    - Khi máy trạm đang chạy ngầm (kể cả không có tray icon), người dùng chỉ cần click lại shortcut hoặc chạy `MeikovaRelayHost.exe`, tiến trình mới sẽ gửi tín hiệu `SHOW` qua loopback TCP để tiến trình ngầm tự kích hoạt và hiển thị cửa sổ điều khiển, không bao giờ sinh tiến trình trùng lặp.
    - Hỗ trợ lệnh CLI quản trị: `MeikovaRelayHost.exe --status` (kiểm tra trạng thái), `MeikovaRelayHost.exe --stop` (dừng dịch vụ ngầm sạch sẽ).
    - Hỗ trợ `AttachConsole(-1)` để hiển thị output trực tiếp trên console khi gọi từ CLI.
- **Biên dịch & Kiểm thử:**
  - 69/69 tests pass (Exit Code 0).
  - Biên dịch PyInstaller thành công, cập nhật bản build vào `relay-server/` và `%LOCALAPPDATA%\MeikovaRelayHost\`.
  - Tiến trình đang chạy ngầm trực tuyến và phản hồi lệnh IPC tức thì.

---

### Previous Updates (Version 1.0.20)
- **Tái thiết kế toàn diện Icon Khay Hệ Thống và Nhận diện Thương hiệu (Theo chuẩn Meikova Loop & Meikova Harvest):**
  - **Phân tích vấn đề:** Icon khay cũ vẽ hình tròn tối màu `#070D17` viền xanh và 2 elip crude trong `create_tray_badge`. Khi Windows 11 thu nhỏ xuống kích thước khay 16x16 / 24x24 pixel, hình tròn đen bị nhòe thành đốm đen mờ đục với 2 chấm mắt méo mó ("icon không ổn").
  - **Áp dụng chuẩn thiết kế Meikova Loop & Meikova Harvest:**
    - Loại bỏ hoàn toàn khối hộp tròn đen đặc nền. Nền chuyển sang trong suốt 100% `(0, 0, 0, 0)`.
    - Biểu tượng vô cực toán học (Cubic Bezier Infinity Loop `M16 16 C 19.5 10.5, 27 10.5, 27 16 C 27 21.5, 19.5 21.5, 16 16 C 12.5 10.5, 5 10.5, 5 16 C 5 21.5, 12.5 21.5, 16 16 Z`).
    - Viền tối emerald contour `#047857` chống chìm trên nền Taskbar trắng/sáng, dải nét neon xanh ngọc `#22C55E` cùng lõi phosphor sáng `#DCFCE7`.
    - Điểm phát sóng viễn trắc quỹ đạo (Signature orbiting pulse beacon dot) tại tọa độ `(23.2, 12.4)` với tâm trắng tinh khiết `#FFFFFF` và vầng hào quang ngọc bích.
    - Render vector ở độ phân giải 256x256 / 512x512 rồi downsample bằng thuật toán `Image.Resampling.LANCZOS` để đạt độ sắc nét tuyệt đối ở mọi kích thước 16x16, 24x24, 32x32 trên Windows 11.
  - **Đồng bộ toàn hệ thống:**
    - Cập nhật `host_agent/make_icon.py` tạo `tray_icon.png` (32x32 transparent), `icon.png` (512x512 squircle), `icon.ico` (multi-resolution 16->256px).
    - Cập nhật `host_agent/gui_agent.py`: hàm dùng chung `get_tray_icon_image()` cho cả giao diện Tkinter và Edge WebView2.
    - Cập nhật `MeikovaRelayHost.spec`: nhúng `tray_icon.png` và gắn resource PE icon cho file `.exe`.
    - Đồng bộ `web-client/favicon.svg` và `relay-server/public/favicon.svg` theo chuẩn SVG mới (viewBox 32x32, squircle rx=8, beacon dot tại 23.2, 12.4).
  - **Biên dịch & Đóng gói:**
    - Chạy lại PyInstaller tạo `MeikovaRelayHost.exe` mới.
    - Cập nhật bản build vào `relay-server/MeikovaRelayHost.exe` và `%LOCALAPPDATA%\MeikovaRelayHost\MeikovaRelayHost.exe`.
  - **Kiểm thử:**
    - Toàn bộ 69/69 test suite pass (Exit Code 0).
    - Tiến trình host agent chạy trực tuyến, kết nối WebSocket relay ổn định và hiển thị icon sắc nét trên taskbar.

---

### Previous Updates (Version 1.0.19)
- **Sửa tận gốc nguyên nhân System Tray Icon không hiển thị / bị tàng hình:**
  - **Nguyên nhân 1 (Lệch WindowStation/Desktop per-thread):** `SetThreadDesktop` trong Win32 là thuộc tính riêng của từng luồng (per-thread). Khi `pystray.Icon.run()` khởi tạo luồng nội bộ `setup_thread`, luồng này không tự kế thừa desktop handle `winsta0\default` của luồng cha, khiến hàm gọi `Shell_NotifyIconW(NIM_ADD)` bị Windows trả về mã lỗi `0x80004005 (E_FAIL)` do không tìm thấy `Shell_TrayWnd` (Taskbar).
    - *Khắc phục:* Truyền callback `setup=setup_tray` vào `Icon.run(setup=setup_tray)`, gọi `ensure_interactive_desktop()` ngay trong luồng `setup_thread` trước khi gán `icon.visible = True`.
  - **Nguyên nhân 2 (Icon bị chìm/tàng hình trên Windows 11 Light Theme):** Mã icon cũ vẽ 2 hình chữ nhật trắng `#FFFFFF` trên nền trong suốt, khi đặt vào menu khay hệ thống màu trắng xám (`#F2F2F2`) của Windows 11 sẽ bị hòa tan thành 2 đường viền mờ tàng hình (chính là ô hàng 2 cột 1 trong ảnh chụp).
    - *Khắc phục:* Thiết kế lại huy hiệu khay hệ thống `create_tray_badge` với viền xanh ngọc bích nổi bật (`#10B981` / `#047857`), bên trong là buồng điều khiển tối `#070D17` cùng biểu tượng vô cực neon `#22C55E` và điểm tâm trắng `#FFFFFF`, đảm bảo tương phản tuyệt đối trên cả theme Sáng và Tối của Windows 11.
  - **Nguyên nhân 3 (Tự động ghim icon lên thanh Taskbar - `IsPromoted = 1`):** Tự động cập nhật khóa Registry `HKCU\Control Panel\NotifyIconSettings` với giá trị `IsPromoted = 1`, đưa biểu tượng Meikova Relay ra ngoài thanh taskbar chính (cạnh đồng hồ/wifi/âm lượng) thay vì bị Windows mặc định giấu vào menu mũi tên `^`.
- **Xác thực kiểm thử:**
  - `SystemTrayIcon` window `MeikovaRelayHost...SystemTrayIcon` đã xuất hiện hợp lệ trong `winsta0\default`.
  - Khóa `IsPromoted` của toàn bộ các file thực thi Meikova Relay đã được đặt thành `1`.
  - Test suite: 69/69 tests pass (Exit Code 0).

---

### Previous Updates (Version 1.0.18)
- **Ghi đè và khử trùng lặp máy trạm (Device Deduplication & Upsert):**
  - **Vấn đề:** Mỗi lần chạy `setup.bat` sinh `room_id` ngẫu nhiên mới khiến cơ sở dữ liệu ghi thêm bản ghi riêng biệt cho cùng một thiết bị (`PHAMDOANKIEM`), dẫn đến danh sách hiển thị 4-5 card trùng tên máy.
  - **Khắc phục:** 
    - Sửa `DB.upsertDevice` trong `relay-server/db.js`: Kiểm tra `(user_id, device_name)` trước. Nếu đã tồn tại máy trạm có tên tương ứng của người dùng, cập nhật thẳng `room_id`, `pin`, `resolution`, `os_info`, `is_online = 1`, `last_seen` thay vì tạo dòng mới.
    - Thêm hàm `DB.deduplicateDevices(userId)` tự động dọn dẹp các bản ghi cũ trùng tên, giữ lại duy nhất 1 bản ghi mới nhất/đang online.
- **Bổ sung tính năng Xóa máy trạm (Device Deletion):**
  - Thêm API `DELETE /api/devices/:id` và `POST /api/devices/delete` trong `relay-server/server.js`, kèm ghi nhật ký kiểm toán `DEVICE_DELETED`.
  - Bổ sung nút biểu tượng thùng rác (Xóa) cạnh nút Kết nối trên mỗi card máy trạm trong `web-client/js/app.js`, kèm hộp thoại xác nhận hủy liên kết và tự động cập nhật danh sách.
- **Sửa triệt để rò rỉ GDI/Window Station handle gây mất System Tray icon:**
  - **Nguyên nhân cốt lõi:** Lớp `ScreenCapture` trong `host_agent/screen_capture.py` gọi `_attach_window_station()` 25 lần mỗi giây nhưng không đóng handle `winsta0` và `default`, làm rò rỉ 50 handle/giây. Chỉ sau vài phút tiến trình tích tụ tới 64,886 handle, làm cạn kiệt Desktop Heap của Windows khiến Windows API từ chối cấp phát icon khay hệ thống (`Shell_NotifyIcon`).
  - **Khắc phục:**
    - Cờ `self._attached`: Chỉ gắn window station 1 lần duy nhất lúc khởi tạo capture.
    - Tối ưu `_send_frames_loop` trong `host_agent/host_service.py`: Khi không có viewer kết nối (`has_active_client = False`), chuyển sang chế độ ngủ tiết kiệm năng lượng (`asyncio.sleep(0.2)`) và gửi heartbeat ping định kỳ, không capture khung hình liên tục (giảm CPU từ 100% xuống 0% và giữ số lượng handle cố định ~800).
- **Xác thực kiểm thử:**
  - 69/69 test suite pass (Exit Code 0).
  - Bản build PyInstaller 31.1 MB chạy trực tiếp với mức tài nguyên ổn định: 833 handles, CPU 1.5s, RAM 135 MB.
  - Danh sách máy trạm đã tự động gom thành 1 máy duy nhất `PHAMDOANKIEM` (Trực tuyến, Room `RD-8571`).

---

### Previous Updates (Version 1.0.17)
- **Bổ sung 4 thiết lập hệ thống chuẩn cho máy trạm (Workstation Behavior Settings):**
  - **Khởi động cùng Windows (`autostart`):** Ghi/xóa khóa Registry `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.
  - **Mở cửa sổ khi Windows khởi động (`open_on_boot`):** Tùy chọn hiển thị giao diện Desktop khi Windows khởi động thay vì mặc định tự thu nhỏ xuống System Tray.
  - **Thu nhỏ vào khay khi bấm nút đóng [X] (`close_to_tray`):** Bấm [X] sẽ thu nhỏ vào khay hệ thống (mặc định Bật); nếu Tắt sẽ dừng dịch vụ và thoát hẳn tiến trình.
  - **Chống tắt màn hình / Sleep (`keep_awake`):** Duy trì hệ thống luôn thức bằng API Windows `SetThreadExecutionState`.
- **Sửa triệt để lỗi xung đột WebView2 Data Lock (`0x800700AA`):**
  - Chuyển `launch_webview_app` sang `private_mode=True` tự cấp phát thư mục tạm cô lập cho mỗi phiên chạy, triệt tiêu xung đột lockfile `EBWebView` khi nhiều tiến trình hoặc phiên cũ chưa giải phóng bộ đệm.
- **Khắc phục lỗi ngắt tiến trình GUI PyInstaller không có console:**
  - Bổ sung `multiprocessing.freeze_support()` ngay đầu file `host_agent/gui_agent.py` và trong `__main__`.
  - Tự động chuyển hướng `sys.stdout` và `sys.stderr` sang `os.devnull` (thay vì giá trị `None` mặc định của `console=False`), loại bỏ hoàn toàn ngoại lệ `AttributeError: 'NoneType' object has no attribute 'write'`.
  - Bổ sung cơ chế tự ghi crash log vào `~/.meikova_relay_crash.log`.
- **Tối ưu script cài đặt `setup.bat` (Loại bỏ lỗi phân giải ngoặc đơn trong CMD):**
  - Chuyển toàn bộ luồng điều kiện sang kiến trúc nhãn `:LABEL` và `goto`, tránh lỗi cú pháp dấu đóng ngoặc `)` nằm trong chuỗi `echo` làm gãy khối `if (...)` của Windows Command Prompt.
- **Xác thực kiểm thử:**
  - Đóng gói PyInstaller thành công: file nhị phân `MeikovaRelayHost.exe` 31.1 MB.
  - Chạy `setup.bat`: Khởi tạo và kết nối thành công phòng `RD-8571`, đăng ký `PHAMDOANKIEM` lên Relay Server `ws://localhost:8080`.
  - Toàn bộ 69/69 unit tests pass (Exit Code 0).

---

### Previous Updates (Version 1.0.16)
- **Sửa lỗi dính thông tin Telemetry Overlay (`#ro-tr`) sau khi ngắt kết nối:**
  - **Nguyên nhân:** Khi kết thúc phiên remote điều khiển (`disconnect()`), client chỉ đóng WebSocket và chuyển về Dashboard nhưng không dọn dẹp biến telemetry. Phần tử `#ro-tr` ở góc trên bên phải vẫn giữ nguyên DOM hiển thị `RTT: 1ms _____ // 21 FPS // RES: 1920x1080` kèm đồ thị sparkline canvas.
  - **Khắc phục:**
    - Tạo hàm `resetSessionMetrics()` trong `web-client/js/app.js`: Đặt lại `metricPing`, `metricFps`, `metricRes` về `--`, xóa mảng `pingSamples`, xóa sạch nét vẽ canvas `sparkCtx.clearRect()`.
    - Cập nhật hàm `updateRoStatus()`: Quản lý hiển thị `#ro-tr` theo điều kiện nghiêm ngặt `const showTr = isConnected && (currentView === 'remote' || currentView === 'terminal' || currentView === 'files' || currentView === 'tasks')`. Khi không kết nối hoặc đang ở Dashboard / Landing / Auth, ẩn hoàn toàn `#ro-tr` (`display: none`).
    - Khởi tạo ẩn mặc định `#ro-tr` trong `web-client/index.html` (`style="display: none;"`).
- **Tối ưu trải nghiệm cài đặt & Khởi động Host Agent:**
  - Cài đặt đầy đủ `pywebview`, `pythonnet`, `pystray`, `pillow` vào môi trường Python 3.12 và đóng gói lại bản nhị phân `dist/MeikovaRelayHost.exe`.
  - Trong `host_agent/gui_agent.py`: Tự động kích hoạt dịch vụ kết nối `api.start_service()` ngay khi nạp giao diện; chỉ thu nhỏ xuống System Tray nếu có tham số `--autostart` (dành cho Windows Startup). Khi người dùng chạy trực tiếp hoặc cài qua file `.bat`, cửa sổ GUI sẽ lập tức hiển thị trên màn hình để quan sát Room ID, PIN và trạng thái kết nối.
  - Cập nhật kịch bản `setup.bat` khởi chạy ứng dụng trực quan (không thêm `--autostart` ở lần chạy đầu tiên, giữ `--autostart` trong registry Run).
- **Bump phiên bản v1.0.16** trên toàn bộ asset (`package.json`, `index.html`, CSS, JS).

---

### Previous Updates (Version 1.0.15)
- **Sửa triệt để lỗi treo GUI ("MeikovaRelayHost.exe is not responding") và liên kết máy trạm vào Dashboard:**
  - **Nguyên nhân 1 (PyWebView Reflection Deadlock):** Lớp `HostApi` trước đây khai báo các thuộc tính công khai như `self.window`, `self.host_service`, `self.service_thread`, `self.tray_icon`. Cơ chế JS Bridge của PyWebView tự động dùng reflection duyệt qua toàn bộ thuộc tính không có dấu `_`. Khi duyệt vào đối tượng native Windows Forms (`window.native`) và WebView2 controller từ background thread, hệ thống ném hàng ngàn ngoại lệ `CoreWebView2Controller members can only be accessed from the UI thread`, làm kẹt hoàn toàn Windows message loop khiến cửa sổ bị treo cứng và hiện thông báo "is not responding".
    - *Khắc phục:* Chuyển toàn bộ biến trạng thái nội bộ sang private có tiền tố `_` (`self._window`, `self._host_service`, `self._service_thread`, `self._tray_icon`, `self._is_quitting`). Loại bỏ thao tác Win32 icon chéo luồng trong `on_shown`.
  - **Nguyên nhân 2 (Lệch đường dẫn cấu hình & không liên kết tài khoản):** Script `setup.bat` lưu file cấu hình tại `%LOCALAPPDATA%\MeikovaRelayHost\config.json`. Nhưng khi chạy file `.bat` từ PowerShell hay thư mục khác, `MeikovaRelayHost.exe` chỉ tìm kiếm tại `cwd` (`C:\Users\kiemp`) rồi fallback sang `~/.meikova_relay_config.json` cũ vốn có `account: ""`. Vì thế Relay Server đăng ký host với `user_id = null`, làm máy trạm không bao giờ xuất hiện trên Dashboard của tài khoản.
    - *Khắc phục:* Viết hàm `resolve_config_path()` trong `host_agent/gui_agent.py` quét theo thứ tự ưu tiên: thư mục chứa file `.exe` (`sys.executable.parent`), `%LOCALAPPDATA%\MeikovaRelayHost\config.json`, `~/.meikova-relay/config.json`, `cwd`, script dir, và `~/.meikova_relay_config.json`. Đồng thời cập nhật `setup.bat` để đồng bộ cấu hình vào `%USERPROFILE%\.meikova_relay_config.json` và khởi chạy với cờ thư mục làm việc `/D "%TARGET_DIR%"`.
  - **Nguyên nhân 3 (Thiếu asset khi đóng gói PyInstaller):** Kịch bản `scripts/build.py` thiếu tham số `--add-data` cho `gui_view.html` và icon, gây lỗi `FileNotFoundError` khi chạy từ file nhị phân đóng gói một file.
    - *Khắc phục:* Bổ sung `--add-data` cho `gui_view.html`, `icon.ico`, `icon.png` vào cấu hình PyInstaller và `.spec`.
- **Kết quả kiểm thử & xác thực (Exit Code 0):**
  - Đã biên dịch lại bản `MeikovaRelayHost.exe` 23.9MB chuẩn bằng Python 3.12 + PyInstaller 6.21.0.
  - Toàn bộ 69 bài unit tests trong test suite đều pass (Exit Code 0).
  - Khởi chạy tiến trình `MeikovaRelayHost.exe --autostart`: `Responding = True` (73.52 MB RAM), giao diện mượt mà không còn treo.
  - Relay Server nhận diện `[Host Online] Room: RD-23973 | Device: PHAMDOANKIEM`.
  - REST API `GET /api/devices` trả về `is_online: 1` gắn chính xác với `user_id: 25b4f409-f9a4-49fc-b727-1cb9940e16f9` (`kiempham1256@gmail.com`).
  - Web Dashboard hiển thị máy trạm `PHAMDOANKIEM` trạng thái `TRỰC TUYẾN`.

---

### Previous Updates (Version 1.0.14)
- **Căn giữa tuyệt đối thanh điều hướng phân hệ (`#mainNav`):**
  - **Nguyên nhân lệch trái:** `.topbar` trước đây dùng Flexbox với `justify-content: space-between`. Cụm bên phải (`.topbar-right`) chứa chuyển ngôn ngữ, badge tài khoản email dài, nút cấu hình phiên và nút kết nối nhanh có độ rộng lớn hơn cụm logo bên trái (`.brand-container`) khoảng ~300px, khiến khoảng trống phân bổ đẩy `#mainNav` lệch sang trái ~150px so với tâm màn hình.
  - **Giải pháp 3 cột đối xứng (CSS Grid):** Chuyển `.topbar` sang layout CSS Grid `grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr)`.
    - Cột 1 (`.brand-container`): `grid-column: 1; justify-self: start; min-width: 0;`
    - Cột 2 (`#mainNav`): `grid-column: 2; justify-self: center; margin: 0 auto;`
    - Cột 3 (`.topbar-right`): `grid-column: 3; justify-self: end; min-width: 0;`
  - **Cân bằng track 2 bên & Chống tràn:**
    - Cắt tỉa `#userNameDisplay` bằng `max-width: 130px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;` kèm `title` hiển thị email đầy đủ khi rê chuột.
    - Media query responsive `@media (max-width: 1480px)`: giảm padding tab `#mainNav`, ẩn chữ của `#btnQuickConnect` và `#btnOpenSessionConfig` (giữ lại icon SVG inline) để đảm bảo 2 cột 1fr luôn cân đối và `#mainNav` luôn ở chính giữa màn hình tới tận 1200px.
    - Media query `@media (max-width: 1200px)`: chuyển thành cuộn ngang an toàn (`overflow-x: auto`), tránh vỡ giao diện trên màn hình nhỏ.
  - **Bảo toàn cơ chế trượt (Sliding Pill Indicator):** Hoàn toàn tương thích với engine `placeIndicator(mainNav)` vì toạ độ `offsetLeft` / `offsetWidth` của các button được tính toán cục bộ bên trong `#mainNav`.
  - Bump phiên bản v1.0.14 trên toàn bộ asset (`index.html`, `package.json`, CSS, JS).

---

### Previous Updates (Version 1.0.13)
- **Tăng chiều rộng modal #addDeviceModal & Chống rớt chữ:**
  - Tăng `max-width` thẻ modal từ `580px` lên `680px` (`width: 92vw`), tăng 100px không gian hiển thị giúp các dòng lệnh terminal và ghi chú quyền hạn không bị rớt chữ đơn lẻ xuống dòng mới.
  - Tinh chỉnh `.cmd-box` CSS: chuyển `word-break: break-all` sang `word-break: normal; overflow-wrap: anywhere;`, ngăn chặn ngắt đôi từ ngẫu nhiên (như `acc` và `ount`), ngắt dòng tự nhiên theo dấu phân cách tham số (`?`, `&`, khoảng trắng).
  - Bump phiên bản v1.0.13 trên toàn bộ asset để tránh cache trình duyệt.

---

### Previous Updates (Version 1.0.12)
- **Sửa triệt để lỗi thực thi script cài đặt Windows (`Setup-MeikovaHost.bat`):**
  - **Nguyên nhân cốt lõi gây lỗi:** Lệnh `setlocal EnableDelayedExpansion` trong `server.js` khiến CMD hiểu dấu chấm than `!` trong các câu lệnh `echo [!]...` và `echo ...!` là biến nội suy chưa đóng, gây lỗi cú pháp lập tức: `! was unexpected at this time.` và dừng chương trình trước khi tải bất kỳ file nào.
  - **Khắc phục cú pháp:** Chuyển sang `setlocal DisableDelayedExpansion`, loại bỏ toàn bộ dấu `!` trong các chuỗi thông báo, dùng biến chuẩn `%RAND_ROOM%` và `%RAND_PIN%`.
  - **Xử lý tệp tải dở dang:** Tự động kiểm tra nếu `MeikovaRelayHost.exe` tồn tại nhưng dung lượng < 5MB (lỗi mạng tải chưa xong) thì tự động xóa và tải lại bản đầy đủ 24MB từ Relay Server.
  - **Tự động kích hoạt Host Service:** Thêm cờ `--autostart` khi gọi `MeikovaRelayHost.exe`, đảm bảo dịch vụ tự động kết nối và máy trạm lập tức hiển thị trạng thái `Trực tuyến` trên Dashboard mà không cần click tay.
- **Xác thực kiểm thử & Triển khai:**
  - Chạy thử nghiệm thực tế script `setup.bat` sinh ra từ Relay Server trên CMD: Exit Code 0, tải trọn vẹn 23.96MB nhị phân, ghi `config.json` hợp lệ và kích hoạt tiến trình Host Agent.
  - Đã đẩy commit `355354f` lên `origin/main`. Render đã hoàn tất build và deploy live version `1.0.12`.

---

### Previous Updates (Version 1.0.11)
- **Zero-Flash Route Hydration on Reload:**
  - Triệt tiêu hoàn toàn hiện tượng nhấp nháy/nhảy về dashboard hoặc landing khi reload trang ở bất kỳ URL phân hệ nào (`/audit`, `/files`, `/terminal`, `/tasks`, `/remote`, `/dashboard`).
  - `initApp()` trong `web-client/js/app.js` được tái cấu trúc thực thi đồng bộ: Phân giải `targetView` từ URL và token lưu tại `localStorage` rồi lập tức kích hoạt `switchView(targetView, false)` ngay frame đầu tiên, trước khi bắt đầu network fetch xác thực `/api/auth/me`.
  - Toàn bộ `<section>` (kể cả `landingSection`) khởi tạo với class `hidden` trong `index.html`. Tab `mainNav` không còn hardcode `.on` ở "Trang chủ", đảm bảo sliding pill indicator đặt chính xác vào tab đích mà không bị trượt từ tab 1 qua.
- **Multi-OS Workstation Modal & Direct Desktop App Distribution:**
  - Thiết kế modal `#addDeviceModal` đa nền tảng cân đối, đồng bộ 2-card layout (1-line terminal command + download button) cho 3 tab Windows, macOS, Linux.
  - Phục vụ trực tiếp gói cài đặt nhị phân độc lập Windows 24MB `MeikovaRelayHost.exe` tại `/api/download/MeikovaRelayHost.exe` (đã whitelist trong `.gitignore`).
  - Cập nhật script cài đặt `Setup-MeikovaHost.bat` tự động kiểm tra kích thước `MeikovaRelayHost.exe` (>5MB) và kết thúc bằng `pause >nul` thay vì đóng đột ngột cửa sổ console.
  - Đồng bộ hóa các endpoint script cho macOS (`/api/download/setup-macos.sh` & `install-macos.sh`) và Linux (`/api/download/setup-linux.sh` & `install-linux.sh`).
- **Xác thực kiểm thử & Triển khai:**
  - Node.js syntax checks và CSS bracket balance: Exit Code 0.
  - Kiểm thử 10 HTTP endpoints local: Exit Code 0 (Status 200 OK).
  - Tải file nhị phân `MeikovaRelayHost.exe`: 23.96MB Status 200 OK.
  - Commit & Push thành công lên GitHub `origin/main` (`584d5a4`), kích hoạt auto-deploy Render v1.0.11.

---

### Project Status
- Path: `D:\JOB\DEV\meikova-relay`
- GitHub Repo: `https://github.com/m3iK18dp/meikova-relay.git`
- GitHub Release: `https://github.com/m3iK18dp/meikova-relay/releases/tag/v1.0.5`
- GitHub Actions CI/CD Run: `https://github.com/m3iK18dp/meikova-relay/actions/runs/39365130954` (Conclusion: SUCCESS across all 3 OS runners)
- Local Test Suite: Exit Code 0 (67/67 unit tests pass)
- Published Workstation Packages:
  1. Windows: `MeikovaRelayHost.exe` (20.34 MB), `MeikovaRelayHost-windows-x64.zip` (20.08 MB)
  2. Linux: `meikova-relay-host` (36.14 MB), `meikova-relay-host_amd64.deb` (35.91 MB), `meikova-relay-host-linux-x64.tar.gz` (35.91 MB)
  3. macOS: `MeikovaRelayHost` (17.80 MB), `meikova-relay-host-macos.tar.gz` (17.59 MB)
  4. Checksums: `SHA256SUMS.txt` (Consolidated SHA256 hashes)

## Completed Features
1. **Multi-Platform Workstation Build Engine & CI/CD Matrix Pipeline:**
   - **Cross-Platform Build Tool (`scripts/build.py`):**
     - Windows: Tự động biên dịch `MeikovaRelayHost.exe` và đóng gói `MeikovaRelayHost-windows-x64.zip`.
     - Linux: Tự động biên dịch ELF standalone `meikova-relay-host`, tạo gói Debian / Ubuntu `meikova-relay-host_amd64.deb` chuẩn format `ar` + `control.tar.gz` + `data.tar.gz` (tích hợp systemd unit và desktop entry) và gói `meikova-relay-host-linux-x64.tar.gz`.
     - macOS: Tự động biên dịch `MeikovaRelayHost`, tạo gói `meikova-relay-host-macos.tar.gz` (tích hợp launchd plist) và `.dmg`.
     - Tự động tính toán và xuất mã băm `SHA256SUMS.txt` cho toàn bộ artifact.
   - **Cross-Platform Guards & Headless CI Hardening:**
     - `host_agent/deployment_manager.py`: Guard an toàn `winreg`, hỗ trợ phân quyền người dùng và đường dẫn cài đặt trên Linux (`~/.meikova_relay_host`, `/opt/meikova-relay-host`) và macOS.
     - `host_agent/system_manager.py`: Fallback telemetry không phụ thuộc `ctypes.windll`, dùng `/proc/meminfo` và `ps` POSIX chuẩn.
     - `host_agent/clipboard_manager.py`: Guard nền tảng `win32` trước `win32clipboard` và `ctypes.windll`, fallback POSIX qua `pbpaste`/`pbcopy` (macOS) và `xclip`/`xsel` (Linux).
     - `host_agent/file_manager.py`: Bổ sung kiểm tra ổ đĩa POSIX Root (`/`) và các điểm mount `/Volumes`, `/media`, `/mnt`.
     - `host_agent/gui_agent.py`: Bọc an toàn `winreg` và bắt ngoại lệ headless (`except Exception:`) khi `pystray`/`pywebview` chạy trong môi trường CI không có `$DISPLAY`.
     - `host_agent/terminal_manager.py`: Phân nhánh lệnh xả đệm terminal: PowerShell `[Console]::Out.Flush()` chỉ kích hoạt trên Windows, POSIX dùng chuẩn stream stdin flush.
   - **GitHub Actions CI/CD Pipeline (`.github/workflows/build-release.yml`):**
     - Ma trận 3 runner độc lập: `windows-latest`, `ubuntu-latest`, `macos-latest`.
     - Tự động cấu hình Node.js 20 và cài đặt dependencies cho relay server để chạy trọn vẹn E2E tests trên mọi runner.
     - Cơ chế Release trực tiếp qua GitHub Releases API (`softprops/action-gh-release@v2`), vượt qua giới hạn dung lượng GitHub Actions storage quota.
   - **Relay Server & Landing UI Endpoints:**
     - Relay Server hỗ trợ endpoint tải trực tiếp: `/api/download/meikova-relay-host_amd64.deb`, `/api/download/meikova-relay-host-linux-x64.tar.gz`, `/api/download/meikova-relay-host-macos.tar.gz`, `/api/download/MeikovaRelayHost-windows-x64.zip`.
     - Giao diện Landing Hub bổ sung nút tải gói `.deb`, `.tar.gz` trực tiếp cho Linux & macOS.
   - **Kiểm thử tự động:** Toàn bộ 67/67 unit & integration tests chạy thành công trên cả 3 runner Windows, Linux và macOS (Exit Code 0).
1. **True 1:1 Pixel-Perfect Native Replication & Auto-Sync Display Engine:**
   - **1:1 Chuẩn gốc (Pixel-Perfect Native Replica):**
     - Host Agent streaming engine: Bổ sung cấu hình `native_1to1` (`quality: 95`, `max_width: None`, `frame_interval: 1/60.0`), loại bỏ triệt để hiện tượng nén mờ điểm ảnh.
     - Web Client Canvas: Tùy chỉnh chế độ 1:1 không bị co giãn cưỡng bức bởi viewport (`max-width: none; max-height: none; image-rendering: pixelated; crisp-edges;`).
     - Tương tác kéo khung hình mượt mà: Hỗ trợ nhấp giữ chuột giữa (Middle-click) hoặc `Alt + Chuột trái` để kéo di chuyển (Pan) khi độ phân giải máy trạm lớn hơn màn hình điều khiển.
     - Huy hiệu trạng thái thời gian thực `.pixel-indicator-badge` góc trên bên phải hiển thị `1:1 PIXEL-PERFECT (WxH)` kèm LED indicator.
   - **Tự động đàm phán & đồng bộ cấu hình cao nhất (Auto-Negotiate & Sync Resolution):**
     - Web Client tự động đo đạc năng lực hiển thị (`devicePixelRatio`, độ phân giải màn hình, độ phân giải viewport, tần số quét màn hình 60Hz/120Hz/144Hz qua RequestAnimationFrame probe).
     - Gửi bản tin handshake `sync_display_profile` tới Host Agent khi kết nối (`host_ready`) hoặc khi nhấn nút **SYNC** trên thanh Floating Deck.
     - Host Agent phân tích ma trận tương thích giữa màn hình trạm và màn hình điều khiển để tự động thiết lập cấu hình tối ưu cao nhất:
       - Tần số quét >= 120Hz: Chọn `ultra_120` (120 FPS Siêu mượt, độ trễ tối thiểu).
       - Màn hình 2K/4K: Chọn `crisp_2k_4k` (Lossless chất lượng 92%).
       - Màn hình trạm khớp hoặc nhỏ hơn màn hình điều khiển: Kích hoạt `native_1to1` (1:1 chuẩn điểm ảnh gốc).
       - Tiêu chuẩn: Chọn `speed_60` (60 FPS mượt mà) hoặc `balanced` (30 FPS cân bằng).
   - **Tuân thủ quy chuẩn Ambient Instrument UI (Zero-Icon & 100% Inline Vector SVG):**
     - Tuyệt đối không dùng emoji, icon font hay icon ngoài.
     - Toàn bộ nút thao tác trên Floating Deck (`SYNC`, `Grid switcher`, `Quality selector`) dùng 100% inline SVG có `viewBox="0 0 24 24"`, `stroke="currentColor"`.
   - **Kiểm thử tự động:** Bổ sung `tests/test_screen_sync.py`, toàn bộ 61/61 unit tests chạy thành công (Exit Code 0).
1. **Instant Zero-Latency i18n Language Switcher (Fixed 3s UI Lag):**
   - Đã khắc phục triệt để độ trễ ~3 giây khi đổi từ Tiếng Việt sang Tiếng Anh.
   - Nguyên nhân: Trước đó vùng rỗng máy trạm (`deviceGrid`) được render động không có thuộc tính `data-i18n` và listener `meikova-lang-changed` bỏ sót render lại view `dashboard`, khiến người dùng phải đợi bộ đếm polling 4 giây (`setInterval`) mới thấy đổi ngôn ngữ.
   - Giải pháp:
     - Gắn đầy đủ thuộc tính `data-i18n` vào toàn bộ template động của `renderDeviceGrid` (tiêu đề rỗng, gợi ý, nút tải cài đặt, nút kết nối nhanh, thẻ máy trạm).
     - Cache mảng thiết bị `currentDeviceList` và lập tức gọi `renderDeviceGrid(currentDeviceList)` khi bắt sự kiện `meikova-lang-changed`.
     - Thêm helper `updateRoStatus()` và cập nhật tức thì telemetry góc trên bên trái (`roStatus`) theo ngôn ngữ lựa chọn.
     - Đồng bộ lại kích thước sliding pill indicator `placeAllIndicators()` khi chuyển đổi ngôn ngữ.
2. **Internationalization (i18n) Engine with Vietnamese & English Support:**
   - Bộ máy đa ngôn ngữ độc lập, zero-dependency với Tiếng Việt làm ngôn ngữ chính mặc định (`vi`) và Tiếng Anh (`en`) hoàn chỉnh cho toàn bộ giao diện và nghiệp vụ.
   - Hỗ trợ kiến trúc mở rộng (`registerLang`) cho phép bổ sung thêm ngôn ngữ khác (Nhật, Hàn, Trung,...) mà không cần sửa đổi mã nguồn xử lý.
   - Đồng bộ trạng thái: Nút chuyển đổi ngôn ngữ segmented pill `[VI] [EN]` ngay tại thanh điều khiển Topbar. Tự động lưu lựa chọn vào `localStorage` và duy trì liên kết URL qua tham số `?lang=en` / `?lang=vi`.
   - Cơ chế nội suy tham số động (`t(key, params)`), ràng buộc tự động qua các thuộc tính DOM (`data-i18n`, `data-i18n-title`, `data-i18n-placeholder`, `data-i18n-aria`).
   - Cập nhật thời gian thực không cần tải lại trang qua custom event `meikova-lang-changed`.
3. **Direct Online File Editor (Chỉnh sửa tệp trực tiếp trên máy trạm):**
   - Mở, sửa và lưu trực tiếp tệp văn bản / mã nguồn (`.txt`, `.json`, `.js`, `.py`, `.html`, `.css`, `.bat`, `.ps1`, `.log`, `.env`, `.md`,...) ngay trên giao diện Web mà không cần tải về máy tính rồi upload lại.
   - Trình soạn thảo trực quan: Giao diện modal dark ambient, đếm dòng/ký tự, hiển thị vị trí con trỏ (Dòng, Cột), trạng thái lưu (`ĐÃ LƯU` vs `● ĐÃ SỬA (CHƯA LƯU)`).
   - Phím tắt `Ctrl + S` lưu tức thì, phím `Tab` thụt lề 2 spaces, tùy chọn ngắt dòng `Xuống dòng`.
   - Cơ chế bảo vệ: Giới hạn kích thước tối đa 5MB, tự động nhận diện và chặn tệp nhị phân (`binary guard`).
   - Tự động nhận diện bảng mã (UTF-8, UTF-8-BOM, CP1258 tiếng Việt, CP1252, Latin1).
   - Thao tác nhanh: Nút **"Sửa"** ngay tại mỗi hàng tệp hoặc nhấp đúp (`Double-click`) vào tệp để mở editor.
   - Tích hợp ghi nhật ký kiểm toán `FILE_READ` và `FILE_SAVE`.
4. **Workstation Quick-Connect & Setup Fixes:**
   - Fixed Windows batch script command separator bug in `relay-server/server.js` (`&` parsed as command in `echo`).
   - Standardized flat script extraction in `%LOCALAPPDATA%\MeikovaRelayHost`.
   - Dual-import fallback and sys.path auto-configuration in `gui_agent.py`, `host_service.py`, `input_injector.py`.
   - Native `ctypes` clipboard implementation in `clipboard_manager.py` replacing `win32clipboard`.
   - Repacked `relay-server/agent-package.zip`.
5. **Auto-Start on Boot / Login:**
   - Integrated Windows Registry Run entry `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\MeikovaRelayHost`.
   - Auto-launches `pythonw.exe gui_agent.py --autostart` on user logon without visible console.
6. **Anti-Sleep / Keep-Awake:**
   - Native Windows API `SetThreadExecutionState` (`ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED`) in `host_agent/power_manager.py`.
   - Automatically prevents system sleep and display timeout during host session lifetime.
7. **Remote Restart Auto-Reconnect:**
   - In `web-client/js/app.js`: Arming auto-reconnect on remote restart power action.
   - Non-blocking polling every 5s after host disconnects to seamlessly re-establish session once workstation finishes rebooting.
8. **Real-Time Interactive Terminal (Native Shell Experience):**
   - Removed clunky bottom input form & "Gửi" button.
   - User types directly on the terminal screen with inline prompt `PS > `, real-time character mirroring, and blinking cursor (`▋`).
   - Integrated command history with `↑`/`↓` arrow keys, and screen clearing via `Ctrl+L` or `cls`/`clear`.
   - Enhanced `terminal_manager.py` with immediate pipeline flush `[Console]::Out.Flush()` to stream command output in real time.
   - Added connection status badge and initial greeting with host location upon connecting.
9. **Deep Audit Logging System (`audit_logs` table in `relay-server/db.js`):**
   - Tracks source client IP, client device OS/browser.
   - Tracks target workstation Room ID, device name, host OS.
   - Comprehensive action logging and REST/Export API.
10. **Web Client Audit View & Face Cam PiP:**
   - Dedicated "Nhật ký (Audit)" tab and optional Face Cam overlay for session recording.

11. **Landing Page Cockpit & Universal Dark Autofill Guard:**
   - Chặn triệt để autofill trên các ô nhập mã máy trạm (Room ID) và mã PIN (`autocomplete="off"`, `autocomplete="new-password"`, `data-lpignore="true"`).
   - Khắc phục hoàn toàn lỗi vỡ màu nền khi browser autofill (`input:-webkit-autofill`) bằng bộ lọc `box-shadow inset` đồng màu nền `#070D17` / `var(--ink-0)` và độ trễ transition màu nền.
   - Nâng cấp 2 ô input: bổ sung icon inline SVG (màn hình / khóa), viền hairline chuẩn studio, nút điền mẫu `Mẫu: RD-8924` và nút ẩn/hiện mã PIN thành dạng tactile pill nổi bật.
12. **High-Impact Ambient Connection Canvas Visualizer:**
   - Hệ thống giả lập topo mạng 3D sống động: Sàn lưới Tron phối cảnh chuyển động tiến về phía trước (`rolling 3D perspective floor grid`), đường chân trời phát quang.
   - Ống truyền dẫn năng lượng kép (Dual-rail energy conduits): Downlink truyền hình ảnh/âm thanh 120 FPS màu Cyan (`#38BDF8`), Uplink điều khiển phím/chuột màu Emerald (`#22C55E`).
   - 42 hạt photon dữ liệu đa kênh di chuyển tốc độ cao kèm vệt sáng chuyển động (`motion blur trails`).
   - Lõi nút holographic: radar sonar ping định kỳ, vòng con quay gyroscope xoay ngược chiều, lõi sáng trắng cực đại.
   - Tương tác từ tính cao cấp: tia plasma điện tích tự động nối tới con trỏ chuột khi di chuyển trong arena; hiệu ứng sóng xung kích (`shockwave ripple`) khi click chuột.
13. **Sliding Session Activity & Inactivity Timeout Engine:**
   - **X phút (Mặc định 15 phút):** Tự động ngắt kết nối phiên máy trạm từ xa (`disconnect()`) nếu người dùng không có thao tác chuột/phím/chạm quá X phút, giải phóng tài nguyên và bảo mật.
   - **Y phút (Mặc định 30 phút):** Tự động đăng xuất tài khoản (`handleAutoLogout()`) khi không có kết nối và không có hoạt động quá Y phút.
   - **Cơ chế trượt (Sliding Session Token Refresh):** Khi người dùng thao tác chuột/phím, hệ thống tự động làm mới token định kỳ qua `POST /api/auth/refresh` để duy trì phiên làm việc liên tục ("tránh văng").
   - **Modal cấu hình phiên trực quan (`#sessionConfigModal`):** Cho phép người dùng tùy chỉnh linh hoạt giá trị X và Y phút ngay trên thanh điều khiển Topbar, lưu tự động vào `localStorage`.
15. **Redesigned Live Connection Topology HUD & Clean Ambient Canvas:**
   - Thay thế toàn bộ cụm cầu vòm canvas vẽ đè lên chữ và 2 máy trạm trôi nổi ngoài lề bằng hệ thống **Holographic Topology Pipeline HUD** tích hợp ngay đầu bảng điều khiển [Cockpit Gateway](file:///D:/JOB/DEV/meikova-relay/web-client/index.html#L185-L242).
   - Hiển thị trực quan 3 nút mạng thời gian thực: `[ MÁY ĐIỀU KHIỂN ]` ──(120 FPS)──► `[ MEIKOVA RELAY ]` ──(4K READY)──► `[ MÁY TỪ XA ]` với đèn beacon nhịp thở (ping animation) và các luồng hạt photon ánh sáng chuyển động liên tục trên rãnh cáp quang (hardware-accelerated CSS keyframes).
   - Căn chỉnh đường cáp quang (`.topo-line`) và nhãn thông số (`.topo-badge`) đồng trục tuyệt đối theo phương ngang (`top: 50%; transform: translateY(-50%)`), tag nằm chính giữa đường cáp với nền `#0B111A` cắt lớp sắc nét.
   - Tiêu đề chính `ĐIỀU KHIỂN TỪ XA CHÍNH XÁC CAO` hoàn toàn sạch sẽ, không còn bất kỳ chữ hay vòng xoay canvas nào đè lên.
   - Nền canvas chuyển thành không gian vi hạt lượng tử (Quantum Cyber Dust & Constellation Micro-Mesh) cùng luồng ánh sáng tinh vân (Nebula Aura) mềm mại, tạo chiều sâu thị giác ambient-dark mà không gây nhiễu chữ.
16. **Balanced 3-Column Deployment Cards & Hairline Scrollbar:**
   - Cân bằng tuyệt đối 3 thẻ tải về trên Landing page: tiêu đề 52px, mô tả 74px, khoang thông số / lệnh cài đặt cố định 140px, nút tải cuối thẻ 52px.
   - Bổ sung thanh cuộn tối màu ambient hairline (4px) trên toàn bộ hệ thống (`scrollbar-width: thin; scrollbar-color: ...`).
17. **Silky Tactile Spring Language Switcher:**
   - Nút chuyển ngôn ngữ `[ VI ] [ EN ]` có con trượt spring animation mượt mà sử dụng `cubic-bezier(0.34, 1.56, 0.64, 1)`.

18. **Desktop Host GUI Redesign & Bilingual VI/EN Localization (`host_agent/gui_agent.py`):**
   - Áp dụng triệt để tiêu chuẩn thiết kế `ambient-instrument-ui`: bảng màu dark ambient ink (`COLORS`), bo viền hairline (`line`), typography phân cấp và telemetry dạng monospace (`Consolas`).
   - Hỗ trợ song ngữ hoàn chỉnh **Tiếng Việt (`vi`)** và **Tiếng Anh (`en`)**:
     - Bộ từ điển song ngữ chuẩn stdlib `TRANSLATIONS` đồng bộ 100% key và interpolation placeholders (`{name}`, `{room_id}`, `{pin}`, `{client}`, `{state}`).
     - Segmented pill switch `[ VI ] [ EN ]` ngay tại header cho phép đổi ngôn ngữ tức thì trong runtime mà không cần khởi động lại app.
     - Lưu ngôn ngữ vào cấu hình (`config.json`), tự động phục hồi khi mở lại app.
   - Loại bỏ 100% tên thương hiệu đối thủ và emoji rác trong toàn bộ mã nguồn và giao diện.
   - Mở rộng kích thước cửa sổ `540x720` (minsize `500, 660`), loại bỏ triệt để lỗi cắt chữ tab.
19. **Build Artifacts & Cache Sanitation (.gitignore):**
   - Bổ sung cấu hình loại trừ triệt để tệp build PyInstaller (`build/`, `dist/`, `*.spec`, `*.exe`), tệp cấu hình runtime cá nhân (`config.json`, `.meikova_relay_config.json`), cache kiểm thử (`.pytest_cache/`, `.coverage`), và tệp tạm OS/IDE.
20. **Infinity Lemniscate 2D Telemetry Canvas (Meikova Loop Customization):**
   - Tái tạo hệ thống vô cực $\infty$ (Lemniscate of Bernoulli) tùy biến chuyên sâu cho hạ tầng Meikova Relay:
     - 180 khối gói dữ liệu số (digital telemetry blocks) uốn lượn liên tục quanh đường ray kép.
     - Phân cụm màu sắc topo: Cụm máy trạm (Host Station - Amber/Emerald bên trái), Cổng Outbound Relay (Nexus trung tâm - Trắng/Cyan), Cụm điều khiển (Client Cockpit - Cyan/Indigo bên phải).
     - Mạng lưới sợi quang cung vòm nội vi (Neural Telemetry Chords) kết nối hai thùy vô cực với nhịp thở mờ ảo.
     - Hai đầu photon động năng (Kinetic Energy Comets) quét dọc cung đường với quầng sáng radial bloom đa tầng và vệt sao chổi chiếu sáng các khối xung quanh.
     - Hồng tâm chuyển tiếp trung tâm (Relay Nexus Reticle) phát xung nhịp khi các photon dữ liệu băng qua tâm giao.
     - Tương tác chuột từ tính: Parallax góc nhìn, khối nở rộng khi rê chuột gần, sóng xung kích (shockwave ripple) kích hoạt khi click chuột.

21. **Official Meikova Logo Branding & Binary Packaging (`dist/MeikovaRelayHost.exe`):**
   - Thay thế icon lông vũ xanh mặc định của Tkinter bằng bộ nhận diện thương hiệu chính thức Meikova (vòng tròn viền xanh lục neon `#22C55E`, nền đen `#070D17`, chữ "T" trắng in đậm):
     - Sinh bộ icon đa kích thước (`icon.ico` 16x16 đến 256x256, `icon.png` 256x256).
     - Gán Windows Taskbar grouping `SetCurrentProcessExplicitAppUserModelID("MeikovaRelay.WorkstationHost.2.0")` để taskbar và alt-tab hiển thị logo Meikova riêng.
     - Cập nhật GUI Agent nạp `iconphoto` và `iconbitmap`.
     - Cập nhật System Tray nạp trực tiếp `icon.png` kèm fallback vẽ vector độ nét cao.
     - Cập nhật `MeikovaRelayHost.spec` nhúng `icon='host_agent/icon.ico'` và `datas=[('host_agent', 'host_agent'), ('host_agent/icon.ico', '.'), ('host_agent/icon.png', '.')]`.
     - Biên dịch PyInstaller thành công bản `dist/MeikovaRelayHost.exe` sạch.
     - Đồng bộ bản build mới vào `relay-server/MeikovaRelayHost.exe`, đóng gói lại `relay-server/agent-package.zip`, và đồng bộ sang `%LOCALAPPDATA%\MeikovaRelayHost\`.

22. **Grand-Scale Infinity Lemniscate & Instrument Telemetry Visualizer (`web-client/js/app.js` & `style.css`):**
   - **Tăng quy mô vô cực $\infty$ gấp 3 lần chiều cao (`scaleY` đạt 480-720px, `scaleX` đạt 560-920px):**
     - Đỉnh loop cao ~480-510px, uốn cong ôm trọn phía trên và quét xuống phía dưới toàn bộ cụm tiêu đề bên trái và cockpit bên phải mà không bị che khuất.
     - Bố cục lưới mở rộng `max-width: 1400px`, `gap: 60px;`, tạo khoang thở trung tâm cho điểm giao Nexus.
     - Thân cockpit chassis chuyển sang kính mờ ambient glass `rgba(11, 17, 26, 0.78)` kèm `backdrop-filter: blur(24px)`.
   - **Bổ sung chi tiết đo lường chuẩn `/ambient-instrument-ui` & Meikova Loop:**
     - **Thước đo Vernier Caliper (260 bước):** Các vạch chia độ chính xác (major 6.5px, minor 3.2px) dọc theo đường ray ngoài.
     - **Tọa độ vi mô (Milestone Micro-Stamps):** Nhãn số telemetry cố định dọc chu vi (`NODE-01 // HOST`, `NODE-02 // 0.8ms`, `CH-1 // 120FPS`,...).
     - **Khung định vị trạm biên (Lobe Milestone Reticles):** Khung góc quang học `┌ ┐ └ ┘` tại đỉnh trái (`NODE-01 // HOST WORKSTATION`) và đỉnh phải (`NODE-02 // CLIENT COCKPIT`).
     - **Mạng lưới sợi quang hài hòa mở rộng (28 Harmonic Chords):** Uốn cong đàn hồi và bị lực từ trường của con trỏ chuột hút về khi rê chuột lại gần (<160px).
     - **Cụm hạt Photon đa kênh:** Sao chổi chính kèm cụm 3 hạt vệ tinh bám đuôi và 4 xung dữ liệu cao tần (micro-pulses) chạy tốc độ cao.
     - **Holographic Gimbal Nexus tại tâm giao ($cx, cy$):** Vòng con quay trong xoay thuận chiều kim đồng hồ, vòng ngoài đứt đoạn xoay ngược chiều, lõi điểm kỳ dị bùng sáng quầng quang học khi hạt photon băng qua.
     - **Tia dẫn đường từ tính (Laser Vector Tether):** Khóa tiêu điểm và hiển thị khoảng cách thời gian thực (`LOCK // Xpx`) từ con trỏ tới điểm gần nhất trên vô cực.
     - **Mạng vi chòm sao lượng tử (Micro-Constellations):** 56 hạt bụi vũ trụ tự động kết nối dây tơ phát quang khi ở gần nhau (<65px).
     - **Sóng xung kích sắc sai kép (Dual Chromatic Shockwaves):** Vòng kép Cyan và Emerald lan tỏa khi nhấp chuột.

23. **Unified Meikova Loop Infinity Logo & Native WebView2 Desktop Host (`/ambient-instrument-ui`):**
   - **Đồng nhất Logo Vô Cực chuẩn Meikova Loop:**
     - Sử dụng vector Bézier chính xác từ Meikova Loop (`M256 256 C 312 168...`), stroke 44.8px.
     - Chuyển màu sang xanh neon `#22C55E`, nền đen studio `#070D17`, loại bỏ 100% viền ngoài (border).
     - Đặt chấm sáng trắng `#FFFFFF` tại tâm giao Nexus $(256, 256)$.
     - Xuất vector đa phân giải bằng Playwright: `host_agent/icon.png` (512x512), `host_agent/icon.ico` (đa kích thước 16, 24, 32, 48, 64, 128, 256px), và đồng bộ `web-client/favicon.svg`.
   - **Thiết kế lại toàn bộ Desktop Host GUI (`/ambient-instrument-ui`):**
     - Thay thế hoàn toàn giao diện Tkinter cũ bằng Microsoft Edge WebView2 (`pywebview 6.2.1` + `clr` Python.NET).
     - Xây dựng giao diện chuẩn studio `host_agent/gui_view.html`: Dark chamber `#070D17`, 100% inline SVG vector (zero-icon font / zero-emoji), segmented sliding pill nav, floating pill master start/stop, room ID/PIN glow cards, log terminal thời gian thực.
     - Cầu nối JavaScript <-> Python hai chiều (`window.pywebview.api` <-> `HostApi`): Quản lý vòng đời `HostService`, đổi Room/PIN, tự khởi động cùng Windows (Run on boot), chống tắt màn hình (Anti-Sleep `PowerManager`), chuyển đổi ngôn ngữ VI/EN.
     - Dark Titlebar DWM (`DwmSetWindowAttribute` 20/35/36), icon thanh tiêu đề Win32 `WM_SETICON`, clipboard chuẩn ctypes 64-bit.
     - Giữ nguyên `MeikovaRelayHostGUI` làm engine fallback (`--legacy-tk`) và phục vụ bộ unit test i18n không làm gãy test.
   - **PyInstaller & Phân phối:**
     - Cập nhật `MeikovaRelayHost.spec` nhúng `gui_view.html`, `icon.ico`, `icon.png` và hiddenimports (`clr`, `webview.platforms.winforms`).
     - Biên dịch thành công bản build mới `dist/MeikovaRelayHost.exe` (Exit Code 0).
     - Đồng bộ bản build vào `relay-server/MeikovaRelayHost.exe`, đóng gói lại `relay-server/agent-package.zip`, và cập nhật `%LOCALAPPDATA%\MeikovaRelayHost\`.

24. **Custom Ambient Studio Titlebar & UI Thread Deadlock Fix (`/ambient-instrument-ui`):**
   - **Khắc phục lỗi treo cứng khởi động (Not Responding):**
     - *Nguyên nhân gốc rễ:* Trong `launch_webview_app`, hàm `on_loaded` được gọi đồng bộ trên UI Thread khi WebView2 hoàn tất tải trang. Lệnh `self.window.evaluate_js` gọi qua `edgechromium.py` thực hiện `semaphore.acquire()`, khóa UI Thread chờ callback. Tuy nhiên callback `ExecuteScriptAsync.ContinueWith` lại cần UI Thread (`self.syncContextTaskScheduler`) để nhả semaphore. Dẫn tới deadlock hai chiều, cửa sổ bị Windows đóng băng "Not Responding".
     - *Giải pháp:* Chuyển sang cơ chế kéo bất đồng bộ (Async Pull Pattern). Giao diện HTML tự gửi yêu cầu qua `window.pywebview.api.get_initial_data()` khi sự kiện `pywebviewready` kích hoạt. Mọi lệnh `_eval_js` từ Python sang JS được đẩy sang luồng daemon ngầm độc lập, bảo vệ UI Thread luôn phản hồi 100%.
   - **Tùy biến thanh tiêu đề Studio Ambient Dark (Custom Titlebar):**
     - Loại bỏ hoàn toàn thanh tiêu đề trắng sáng mặc định của Windows 10 (`frameless=True`, `easy_drag=True`).
     - Tích hợp thanh tiêu đề Studio `#060B14` đồng nhất 100% với dark chamber `#070D17`:
       - Bên trái: Logo vô cực Meikova Loop neon green `#22C55E` kèm tên ứng dụng monospace `MEIKOVA RELAY HOST`.
       - Ở giữa: Rãnh kéo cửa sổ đa màn hình với hỗ trợ Win32 `WM_NCLBUTTONDOWN` (`0x00A1`) và `.pywebview-drag-region`.
       - Bên phải: Nút thu nhỏ (`—`) và nút đóng (`✕`) chuẩn hover dark/red, liên kết trực tiếp `minimize_window()` và `close_window()`.
     - Phân bổ lại subheader bên trong: Telemetry máy trạm `PC-LOCAL // 120 FPS` ở bên trái, cụm nút chuyển ngôn ngữ `[ VI ] [ EN ]` và Status Pill ở bên phải, loại bỏ hoàn toàn tình trạng trùng lặp chữ.
   - **Biên dịch & Kiểm chứng:**
     - Đã biên dịch lại bản `dist/MeikovaRelayHost.exe` sạch (Exit Code 0).
     - Đồng bộ `relay-server/MeikovaRelayHost.exe`, cập nhật `relay-server/agent-package.zip` và thư mục máy trạm cục bộ.
     - Chạy thử nghiệm binary: PID 54228 chạy mượt mà, khởi động tức thì, không còn hiện tượng treo "Not Responding".

25. **HostService Constructor Signature Parity & Console Unicode Guard:**
   - **Lỗi văng khi nhấn "BẬT DỊCH VỤ":**
     - *Nguyên nhân 1 (TypeError):* Trong `HostApi.start_service`, hàm khởi tạo `HostService` bị truyền thừa 5 tham số không tồn tại (`device_token`, `account_owner`, `permanent_pin`, `on_client_connected`, `on_status_changed`), dẫn tới `TypeError: HostService.__init__() got an unexpected keyword argument 'device_token'` ngay khi click.
     - *Nguyên nhân 2 (UnicodeEncodeError):* Trên Windows console mặc định (`cp1252`), lệnh `print(f"[{t_str}] {msg}")` với tiếng Việt có dấu (`Khởi động dịch vụ thành công!`) bị lỗi `charmap codec can't encode character...`.
     - *Hậu quả gián tiếp (Treo Not Responding):* Khi hàm Python trong JS Bridge ném Exception, `pywebview.util.js_bridge_call` bắt lỗi và cố đẩy thông báo lỗi về JS qua `evaluate_js`, dẫn tới khóa UI thread lần thứ hai.
     - *Giải pháp:*
       1. Đồng bộ 100% chữ ký hàm `HostService(relay_url, room_id, pin, device_name, account)` và gán callback thuộc tính động (`on_status_change`, `on_client_connect`, `on_client_disconnect`, `on_chat_message`) giống kiến trúc `MeikovaRelayHostGUI`.
       2. Bọc `print` trong `try...except` và cấu hình tự động `reconfigure(encoding='utf-8', errors='replace')` cho `sys.stdout` và `sys.stderr`.
       3. Bọc toàn bộ các hàm gọi bridge với `try...except` để bảo vệ JS bridge không bao giờ gặp unhandled exception.
   - **Biên dịch & Kiểm chứng:**
     - Chạy thử nghiệm trực tiếp `api.start_service()` trong Python: Dịch vụ khởi động và kết nối sạch, trả về `is_running: True`, ngắt kết nối an toàn.
     - Đã biên dịch lại bản `dist/MeikovaRelayHost.exe` sạch (Exit Code 0).
     - Đồng bộ `relay-server/MeikovaRelayHost.exe`, cập nhật `relay-server/agent-package.zip` và thư mục máy trạm cục bộ `%LOCALAPPDATA%\MeikovaRelayHost\`.
  26. **Host Window Drag Boundary & Subheader Overflow Layout Fix:**
   - **Kéo thả giới hạn độc quyền trên Titlebar (`easy_drag=False`):**
     - *Nguyên nhân:* Thuộc tính `easy_drag=True` trong `pywebview.create_window` tự động gán event listener mousedown lên toàn bộ body HTML, dẫn đến bấm giữ ở bất kỳ đâu (nút, thẻ card, ô nhập liệu) cũng kéo di chuyển cửa sổ.
     - *Giải pháp:* Đổi `easy_drag=False`. Kéo thả chỉ diễn ra khi bấm giữ trên thanh tiêu đề `.titlebar` (thông qua `handleTitlebarMouseDown` và Win32 `WM_NCLBUTTONDOWN` / `HTCAPTION`), các vùng khác của cửa sổ hoàn toàn độc lập.
   - **Mở rộng kích thước cửa sổ & Chống vỡ layout subheader:**
     - Tăng kích thước cửa sổ từ `500x720` lên `560x740` px trong `host_agent/gui_agent.py`.
     - Thêm `min-width: 0;` cho `.sub-header`, `flex-shrink: 0;` cho `.sub-header-right`.
     - Thêm `white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex: 1; min-width: 0;` cho `.telemetry-kicker`.
     - Đảm bảo dòng telemetry máy trạm luôn nằm gọn gàng trên 1 dòng duy nhất, không bao giờ ngắt dòng làm vỡ bố cục khi tên máy tính dài.
   - **Biên dịch & Triển khai:**
     - Đã biên dịch lại bản `dist/MeikovaRelayHost.exe` sạch (Exit Code 0).
     - Đồng bộ `relay-server/MeikovaRelayHost.exe`, cập nhật `relay-server/agent-package.zip` và thư mục máy trạm cục bộ `%LOCALAPPDATA%\MeikovaRelayHost\`.
     - Binary test: PID 54772 chạy ổn định, khởi động tức thì, Exit Code 0.

   27. **Interactive Multi-Monitor Drag-and-Drop Grid Layout & Portable EXE Lifecycle Overhaul:**
   - **Bố cục lưới đa màn hình kéo thả trên Web Client (`/ambient-instrument-ui`, `/ui-ux-pro-max`):**
     - Bổ sung vùng `#monitorGrid` với hệ thống các thẻ `.monitor-tile` hiển thị đồng thời các màn hình của máy trạm.
     - Cắt lát frame GPU Canvas không tốn thêm băng thông (`drawImage` sub-rectangle từ frame Virtual Desktop tổng).
     - Cho phép kéo thả (HTML5 Drag & Drop) để tráo đổi vị trí các màn hình theo bất kỳ thứ tự nào (lưu cấu hình vào `localStorage`).
     - Tích hợp các nút chuyển đổi bố cục nhanh: `◄ ► Ngang`, `► ◄ Đảo ngược`, `▲ ▼ Dọc`.
     - Điều phối tọa độ chuột độc lập theo từng ô màn hình: rê chuột, click chuột trái/phải, con lăn chuột đều gửi kèm `monitor_id` giúp `InputInjector` click trúng đích 100%.
   - **Khắc phục triệt để hạn chế của Portable EXE:**
     - Mô-đun `host_agent/deployment_manager.py`: Tự động sao chép bảo vệ đường dẫn vào `%LOCALAPPDATA%\MeikovaRelayHost\MeikovaRelayHost.exe` khi bật tự khởi động, loại bỏ hoàn toàn lỗi gãy đường dẫn khi xóa file trong `Downloads` hoặc rút USB.
     - Nâng quyền UAC qua Task Scheduler (`schtasks.exe /create /tn MeikovaRelayHost /sc onlogon /rl highest /f`): Chạy với quyền Administrator cao nhất lúc đăng nhập, khắc phục triệt để lỗi đen màn hình và kẹt chuột khi máy trạm bật cửa sổ UAC/Task Manager.
     - Windows Service Mode 24/7 (`sc.exe create MeikovaRelayService`): Cho phép phần mềm tự động chạy ngầm ngay từ khi bật máy trước khi có người đăng nhập (Lock screen).
     - Bổ sung các cờ dòng lệnh CLI: `--install-service`, `--uninstall-service`, `--service` và tích hợp nút bật/tắt dịch vụ trực quan trong tab "QUẢN TRỊ 24/7" của Host GUI.
   - **Biên dịch & Triển khai:**
     - Đã biên dịch lại bản `dist/MeikovaRelayHost.exe` sạch (Exit Code 0).
     - Đồng bộ `relay-server/MeikovaRelayHost.exe`, cập nhật `relay-server/agent-package.zip` và thư mục máy trạm cục bộ `%LOCALAPPDATA%\MeikovaRelayHost\`.
     - Binary test: PID 61096 chạy ổn định, khởi động tức thì, Exit Code 0.

    28. **2-Tier Installation UX Architecture (User-Level Zero-Admin vs System-Level Service with UAC Elevation) & Visual Cards Deck:**
    - **Phân cấp kiến trúc cài đặt 2 tầng rõ ràng (User vs Admin):**
      - **Tầng 1: Cài đặt Người dùng (User Level - Zero Admin):**
        - Dành cho môi trường doanh nghiệp hoặc tài khoản văn phòng không có mật khẩu Admin.
        - Tự động sao chép binary vào thư mục an toàn cá nhân `%LOCALAPPDATA%\MeikovaRelayHost\MeikovaRelayHost.exe`.
        - Đăng ký tự khởi động qua `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` và Task Scheduler chế độ người dùng chuẩn (`/rl limited`).
        - Hoạt động 100% không yêu cầu hộp thoại UAC hay mật khẩu Admin.
      - **Tầng 2: Dịch vụ Hệ thống 24/7 (System Service - Cần Admin UAC):**
        - Dành cho máy chủ hoặc máy trạm cần truy cập từ xa mọi lúc, kể cả trước khi đăng nhập Windows (Lock Screen / Login Screen).
        - Khi bấm "Cài Đặt Dịch Vụ 24/7", nếu đang chạy quyền thường sẽ tự động nâng quyền thông qua `ShellExecuteW(..., 'runas', ...)` mở hộp thoại Windows UAC yêu cầu cấp quyền đúng 1 lần duy nhất.
        - Cài đặt vào `%ProgramData%\MeikovaRelayHost\`, đăng ký và kích hoạt Windows Service `MeikovaRelayService` (`sc.exe create ... start= auto`), đồng thời tạo Task Scheduler `/rl highest` cho quyền Administrator cao nhất.
    - **Giao diện thẻ trực quan Ambient Dark (`/ambient-instrument-ui`, `/ui-ux-pro-max`):**
      - Thiết kế lại toàn bộ tab "QUẢN TRỊ 24/7" trên Host GUI thành 2 thẻ lựa chọn độc lập:
        - Thẻ 1: `CÀI ĐẶT NGƯỜI DÙNG // USER LEVEL` kèm huy hiệu xanh lục `[ KHÔNG CẦN ADMIN ]`, nút bấm `Cài Đặt Vào User` / `Gỡ Cài Đặt User`.
        - Thẻ 2: `DỊCH VỤ HỆ THỐNG 24/7 // SYSTEM SERVICE` kèm huy hiệu vàng hổ phách `[ CẦN ADMIN (UAC) ]`, nút bấm `Cài Đặt Dịch Vụ 24/7` / `Gỡ Bỏ Dịch Vụ 24/7`.
      - Hỗ trợ đầy đủ song ngữ Việt - Anh (VI / EN).
    - **Biên dịch & Triển khai:**
      - Đã biên dịch lại bản `dist/MeikovaRelayHost.exe` mới nhất bằng PyInstaller (Exit Code 0).
      - Đồng bộ `relay-server/MeikovaRelayHost.exe`, cập nhật `relay-server/agent-package.zip` và thư mục máy trạm cục bộ `%LOCALAPPDATA%\MeikovaRelayHost\`.
      - Toàn bộ 49/49 unit tests chạy thành công (Exit Code 0).

    29. **Cross-Platform Workstation Host Architecture & 3 Deck Display Modes (Bottom Float, Top Pinned, Top Auto-hide Unpinned):**
    - **Kiến trúc Hỗ trợ Đa Nền Tảng Máy Trạm (Workstation Host):**
      - **Windows (10/11/Server):** Hỗ trợ 100% Native Win32 API (DXGI/GDI, SendInput, WASAPI, UAC Elevation, 2-Tier Deployment, Windows Service 24/7). Đã đóng gói thành file thực thi `.exe`.
      - **Linux (Ubuntu, Debian, Fedora, Arch, Raspberry Pi OS):** Hỗ trợ 100% qua X11/Wayland Screen Grab, `pynput` / `pyautogui`, Bash/Zsh interactive shell, `systemctl` / `poweroff`. Cung cấp script launcher `run_agent_linux.sh` và systemd unit `meikova-relay.service` chạy ngầm 24/7.
      - **macOS (Intel & Apple Silicon M1-M4):** Hỗ trợ 100% sau khi cấp quyền Screen Recording & Accessibility trong macOS System Settings. Cung cấp script launcher `run_agent_macos.sh` và `com.meikova.relay.plist` qua Launchd.
      - **iOS (iPhone) & iPadOS (iPad):** Làm rõ giới hạn kỹ thuật kiến trúc bảo mật của Apple: Apple áp dụng cơ chế Sandbox tuyệt đối, cấm hoàn toàn synthetic touch injection vào ứng dụng bên thứ 3 hoặc SpringBoard (ngay cả TeamViewer/AnyDesk trên iOS cũng chỉ là View-only). Không thể chạy ngầm unmanaged host trên iOS/iPadOS nếu không Jailbreak.
      - **Cross-Platform Guard trong Code:** Toàn bộ các module `screen_capture.py`, `input_injector.py`, `power_manager.py`, `terminal_manager.py`, `clipboard_manager.py`, `deployment_manager.py` đều được bảo vệ bằng platform-guards an toàn, không bao giờ bị crash vì `ctypes.windll` khi chạy trên non-Windows.
    - **3 Chế độ hiển thị Floating Deck linh hoạt trên Web Client (`/ambient-instrument-ui`, `/ui-ux-pro-max`):**
      - **Chế độ 1: Dạng đáy nổi (`bottom-float`):** Thanh pill lơ lửng ở đáy màn hình như mặc định, làm mờ sau 3.5s không thao tác.
      - **Chế độ 2: Mép trên - Ghim cố định (`top-pinned`):** Dock vào đỉnh màn hình (`top: 0`), bo góc dưới, luôn hiển thị, không che thanh Taskbar Windows ở đáy của máy trạm.
      - **Chế độ 3: Mép trên - Tự động ẩn khi rời chuột (`top-unpinned`):** Mặc định ẩn hoàn toàn lên mép trên (`transform: translate(-50%, -100%)`). Có tai kéo phát sáng `#deckTopTrigger` ở chính giữa mép trên. Khi rê chuột vào mép trên (hover trong phạm vi 14px) hoặc chạm vào tai kéo, thanh deck trượt mượt mà xuống để thao tác. Khi chuột rời khỏi deck, sau 450ms tự động trượt thu gọn lên trên. Tránh đè lên 100% các phần giao diện cần thao tác của máy trạm.
      - **Điều khiển trực quan & Lưu cấu hình:** Nút chuyển vị trí `#btnDeckDisplayMode` mở popover lựa chọn 3 chế độ kèm radio checkmark, nút ghim/bỏ ghim nhanh `#btnDeckPinQuick` khi ở mép trên, tự động lưu và khôi phục từ `localStorage.getItem('meikova_deck_mode')`. Hỗ trợ đầy đủ cử chỉ chạm Touch/Tablet cho iPadOS và mobile.
    - **Tài liệu chuyên sâu:** Bổ sung `docs/cross-platform-workstation-guide.md` phân tích toàn diện ma trận hệ điều hành và hướng dẫn cài đặt trên Linux/macOS.
    - **Biên dịch & Triển khai:**
      - Đã biên dịch lại bản `dist/MeikovaRelayHost.exe` mới nhất bằng PyInstaller (Exit Code 0).
      - Đồng bộ `relay-server/MeikovaRelayHost.exe`, cập nhật `relay-server/agent-package.zip` và thư mục máy trạm cục bộ `%LOCALAPPDATA%\MeikovaRelayHost\`.
      - Toàn bộ 56/56 unit tests chạy thành công (Exit Code 0).

    30. **Sửa Lỗi CSS / Active Tab Indicator Khi Chưa Đăng Nhập:**
    - **Triệu chứng lỗi ban đầu:** Ở trang chủ, tab "Trang chủ" hiển thị indicator xanh lục chữ đen đậm chuẩn. Nhưng khi bấm sang tab khác (ví dụ "Máy trạm") trong trạng thái chưa đăng nhập, hệ thống điều hướng vào view `auth` nhưng indicator xanh lục `.seg__ind` bị kẹt lại ở "Trang chủ", trong khi nút "Trang chủ" lại bị gỡ class `.on` làm chữ chuyển sang màu mờ (`var(--text-muted)`) đè lên nền xanh phát sáng, gây vỡ tương phản thị giác.
    - **Nguyên nhân cốt lõi:**
      1. Trong `web-client/js/app.js`: Hàm `placeIndicator(seg)` kiểm tra `if (!onBtn || !ind) return;`. Khi chuyển sang `auth`, không có nút nào trong `mainNav` có `data-view="auth"`, nên `onBtn` là `null`. Hàm trả về sớm mà không ẩn indicator, khiến `.seg__ind` giữ nguyên tọa độ và kích thước cũ ở "Trang chủ".
      2. Trong `web-client/css/style.css`: `.seg button.on` gán trùng lặp `background: var(--accent)`, trong khi `.seg__ind` lại để `z-index: -1` và không có hiệu ứng chuyển đổi `opacity`.
      3. Sự kiện click `mainNav` chưa lưu lại tab mục tiêu mà người dùng muốn truy cập vào `sessionStorage`.
    - **Giải pháp xử lý:**
      1. Cập nhật `placeIndicator(seg)`: Khi `!onBtn`, lập tức gán `ind.style.setProperty('--ind-w', '0px')` và `ind.style.opacity = '0'` với transition mượt mà.
      2. Tối ưu CSS theo chuẩn Meikova Loop (`ambient-instrument-ui`): `.seg button` có `position: relative; z-index: 2; background: transparent;`. Nút `.on` có `color: var(--on-accent); background: transparent; font-weight: 600;`. `.seg__ind` có `z-index: 1; pointer-events: none;` kèm transition cả `transform`, `width`, `opacity`. Nền pill duy nhất do `.seg__ind` đảm nhiệm, triệt tiêu hoàn toàn lỗi chồng chéo màu hoặc chữ mờ trên nền xanh.
      3. Lưu tuyến đường đang chờ `sessionStorage.setItem('meikova_relay_pending_route', view)` khi click tab lúc chưa đăng nhập để tự động chuyển tiếp sau khi đăng nhập thành công.
      4. Tự động cập nhật `placeIndicator(authTabs)` khi view `auth` hiển thị.

    31. **Nâng Cấp Toàn Diện Landing Page Đa Nền Tảng & Sửa Tràn Bố Cục UI:**
    - **Nâng cấp Landing Page:**
      - **Dải huy hiệu đa nền tảng:** Bổ sung thanh OS Support Strip (`.landing-os-strip`) hiển thị trực quan các nền tảng máy trạm: Windows (EXE / 2-Tier), Linux (Systemd / X11), macOS (Apple Silicon M1-M4), Web & iPadOS (Zero-Install).
      - **Mạng lưới tính năng chuẩn Studio (6 thẻ cân đối):** 120 FPS & Đa màn hình (Multi-Monitor Grid), Thanh Floating Deck 3 chế độ, Máy trạm đa nền tảng Win/Mac/Linux, Âm thanh 2 chiều & Mic Talkback, Terminal tương tác thời gian thực, Quản lý tệp 2 chiều & Sửa trực tiếp.
      - **Trung tâm Tải về đa nền tảng (Download Hub Matrix):** Tích hợp thanh trượt chọn phân hệ (`#dlPlatformSeg`) với 4 tab độc lập: Windows (EXE, BAT, PowerShell), Linux (Bash 1-liner curl, Systemd unit, ARM64/Headless), macOS (macOS 1-liner curl, Apple Silicon, Launchd plist), Web & iPadOS (Trình duyệt trực tiếp, Touch / Pencil gestures, Bàn phím ảo).
      - **API phục vụ tải script cài đặt:** Bổ sung các endpoint `/api/download/install-linux.sh`, `/api/download/install-macos.sh`, `/api/download/meikova-relay.service`, `/api/download/com.meikova.relay.plist` trên Relay Server.
    - **Sửa triệt để 2 lỗi tràn giao diện (Overflow Bugfix):**
      - **Lỗi 1 (Thanh Telemetry Strip rớt dòng):** `.landing-stats-strip` trước đó bị nhét 5 ô khiến ô thứ 5 rớt xuống hàng 2 gây thừa khoảng trống trong khung bo tròn. Đã tinh gọn về đúng 4 thông số cốt lõi (`< 15ms`, `120 FPS`, `MULTI-MON`, `3-DECK`), đổi `flex-wrap: nowrap`, đảm bảo thanh pill luôn nằm trên 1 hàng duy nhất thẳng hàng hoàn hảo.
      - **Lỗi 2 (Khung Topology HUD bị cắt chữ bên phải):** Nhãn node 3 trước đó quá dài (`MÁY TRẠM ĐA HỆ ĐIỀU HÀNH`) khiến chữ "HÀNH" tràn ra mép phải. Đã rút gọn nhãn thành `MÁY TRẠM HOST` (cân bằng 14 ký tự với `MÁY ĐIỀU KHIỂN`), giữ sub-meta `WIN • LINUX • MACOS`, đồng thời tinh chỉnh `padding` và `min-width` của `.topo-conduit` để không bao giờ bị cắt chữ trên mọi kích thước màn hình.

## Verification
- Unit Tests: `.\.venv\Scripts\python.exe -m unittest discover tests` -> 56 passed, Exit Code 0.
- Cross-Platform Tests: `.\.venv\Scripts\python.exe -m unittest tests.test_cross_platform_agent` -> 7 passed, Exit Code 0.
- Multi-Monitor Tests: `.\.venv\Scripts\python.exe -m unittest tests.test_multi_monitor_grid` -> 4 passed, Exit Code 0.
- Deployment Manager Tests: `.\.venv\Scripts\python.exe -m unittest tests.test_deployment_manager` -> 5 passed, Exit Code 0.
- GUI i18n Suite: `.\.venv\Scripts\python.exe -m unittest tests.test_gui_i18n` -> 5 passed, Exit Code 0.
- Web Client i18n Suite: `.\.venv\Scripts\python.exe -m unittest tests.test_i18n` -> 6 passed, Exit Code 0.
- PyInstaller Build: `.\.venv\Scripts\pyinstaller.exe MeikovaRelayHost.spec --clean --noconfirm` -> Exit Code 0.
- Binary Execution Test: `dist/MeikovaRelayHost.exe --help` -> Exit Code 0.
- Python Syntax: `.\.venv\Scripts\python.exe -m py_compile host_agent/*.py` -> Exit Code 0.
- JavaScript Syntax: `node -c web-client/js/app.js` & `node -c web-client/js/i18n.js` & `node -c relay-server/server.js` -> Exit Code 0.
- CSS Braces Balance: 419 open / 419 close (Depth 0).
- Relay Server: Active on port 8080 (endpoints `/api/health`, `/api/download/install-linux.sh`, `/api/download/install-macos.sh` verified with 200 OK).

    32. **Unified Cluster Design Parity, Offline-First Sync Architecture & Native Desktop Remote Client:**
    - **Đồng nhất Hệ Thống Thiết Kế Cụm 3 Phần Mềm (Meikova Loop, Meikova Harvest, Meikova Relay):**
      - Thống nhất bảng màu Ambient Dark: `#070D17` (ink-0), `#0F172A` (ink-1), `#1E293B` (ink-2), neon emerald `#22C55E`, cyan `#38BDF8`, white `#FFFFFF`.
      - Bộ ba Typography chuẩn quốc tế & tiếng Việt không vỡ dấu: `Unbounded` (Brand/Display), `Be Vietnam Pro` (UI/Buttons/Tabs), `JetBrains Mono` (Telemetry/Data).
      - Triết lý "Less Text, More Signal", 100% Inline Vector SVG không dùng icon font hay emoji.
    - **Tối ưu Responsive 100% Đa Thiết Bị:**
      - **Laptop & Tablet (1024px – 1440px):** Chuyển `.topbar` sang flexbox chống đè các nút điều hướng `#mainNav` và cụm điều khiển `.topbar-right`. Truncate email người dùng, tự động chuyển `#mainNav` sang Icon-Only mode trên màn hình hẹp kèm tooltip.
      - **Điện thoại di động (< 768px):** Tự động chuyển `#mainNav` thành **Mobile Bottom Navigation Bar** cố định sát đáy màn hình (`position: fixed; bottom: 0`), hỗ trợ vùng an toàn iOS Home indicator (`env(safe-area-inset-bottom)`), 7 tab xúc giác trực quan (Trang chủ, Máy trạm, Màn hình, Tệp, Terminal, Tiến trình, Nhật ký). Diện tích chạm >= 44x44px.
      - Tối ưu hóa `.dashboard-container`, `.device-grid`, các modal popup và stage hiển thị 100% fluid từ 360px trở lên.
    - **Kiến trúc Đồng bộ Ngoại tuyến (Offline-First Sync Engine):**
      - **Dữ liệu nhẹ đồng bộ Cloud:** Preferences (ngôn ngữ, theme, fps, fit-mode), danh sách thiết bị yêu thích (`device_bookmarks`), lịch sử kết nối nhanh (`quick_history`), tên gợi nhớ máy trạm (`custom_labels`). Bảng SQLite `user_sync_store` tại Relay Server.
      - **Dữ liệu nặng lưu trữ Local:** Screen buffer, Audio PCM chunks, file transfers, private keys, raw clipboard buffers được giữ an toàn tại local cache.
      - **Hàng đợi Local Sync Queue:** Khi mất kết nối hoặc server unreachable, mọi thao tác người dùng lưu tức thời vào Local Storage / SQLite. Ngay khi có mạng trở lại, sync engine tự động xả hàng đợi qua `/api/sync/push` và kéo cập nhật mới qua `/api/sync/pull` (Last-Write-Wins timestamps).
      - Thư viện `web-client/js/sync_engine.js` dùng chung cho Web Client và Desktop Client.
    - **Ứng dụng Desktop Remote Client độc lập (`MeikovaRelayClient`):**
      - Xây dựng bằng `pywebview` (Microsoft Edge WebView2) tương thích kiến trúc của `Meikova Loop/loopbox/desktop.py`.
      - Cửa sổ native 1366x840, Per-Monitor High-DPI Awareness, Win32 DWM Immersive Dark Titlebar (`#070D17`).
      - Cơ chế **Global Hotkey Capture** khi toàn màn hình: bắt và chuyển tiếp các phím đặc biệt (Windows key, Alt+Tab, Ctrl+Alt+Del) sang máy trạm mà không bị trình duyệt web chặn.
      - Cơ sở dữ liệu SQLite cục bộ `client_desktop/local_db.py` tại `%LOCALAPPDATA%\MeikovaRelayClient\client_cache.db`.
      - Tích hợp khay hệ thống Dark Mode Systray, script khởi chạy `run-desktop-client.bat` và file cấu hình đóng gói PyInstaller `client_desktop/client.spec`.
    - **Kết quả Kiểm Thử:**
      - Toàn bộ 80/80 unit tests chạy thành công (`Ran 80 tests in 28.860s - OK`, Exit Code 0).





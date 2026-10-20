# PROJECT SESSION HANDOFF LOG

### Recent Updates (Version 1.0.12)
- **Sửa triệt để lỗi thực thi script cài đặt Windows (`Setup-TitanHost.bat`):**
  - **Nguyên nhân cốt lõi gây lỗi:** Lệnh `setlocal EnableDelayedExpansion` trong `server.js` khiến CMD hiểu dấu chấm than `!` trong các câu lệnh `echo [!]...` và `echo ...!` là biến nội suy chưa đóng, gây lỗi cú pháp lập tức: `! was unexpected at this time.` và dừng chương trình trước khi tải bất kỳ file nào.
  - **Khắc phục cú pháp:** Chuyển sang `setlocal DisableDelayedExpansion`, loại bỏ toàn bộ dấu `!` trong các chuỗi thông báo, dùng biến chuẩn `%RAND_ROOM%` và `%RAND_PIN%`.
  - **Xử lý tệp tải dở dang:** Tự động kiểm tra nếu `TitanRemoteHost.exe` tồn tại nhưng dung lượng < 5MB (lỗi mạng tải chưa xong) thì tự động xóa và tải lại bản đầy đủ 24MB từ Relay Server.
  - **Tự động kích hoạt Host Service:** Thêm cờ `--autostart` khi gọi `TitanRemoteHost.exe`, đảm bảo dịch vụ tự động kết nối và máy trạm lập tức hiển thị trạng thái `Trực tuyến` trên Dashboard mà không cần click tay.
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
  - Phục vụ trực tiếp gói cài đặt nhị phân độc lập Windows 24MB `TitanRemoteHost.exe` tại `/api/download/TitanRemoteHost.exe` (đã whitelist trong `.gitignore`).
  - Cập nhật script cài đặt `Setup-TitanHost.bat` tự động kiểm tra kích thước `TitanRemoteHost.exe` (>5MB) và kết thúc bằng `pause >nul` thay vì đóng đột ngột cửa sổ console.
  - Đồng bộ hóa các endpoint script cho macOS (`/api/download/setup-macos.sh` & `install-macos.sh`) và Linux (`/api/download/setup-linux.sh` & `install-linux.sh`).
- **Xác thực kiểm thử & Triển khai:**
  - Node.js syntax checks và CSS bracket balance: Exit Code 0.
  - Kiểm thử 10 HTTP endpoints local: Exit Code 0 (Status 200 OK).
  - Tải file nhị phân `TitanRemoteHost.exe`: 23.96MB Status 200 OK.
  - Commit & Push thành công lên GitHub `origin/main` (`584d5a4`), kích hoạt auto-deploy Render v1.0.11.

---

### Project Status
- Path: `D:\JOB\DEV\titan-remote`
- GitHub Repo: `https://github.com/m3iK18dp/titan-remote.git`
- GitHub Release: `https://github.com/m3iK18dp/titan-remote/releases/tag/v1.0.5`
- GitHub Actions CI/CD Run: `https://github.com/m3iK18dp/titan-remote/actions/runs/39365130954` (Conclusion: SUCCESS across all 3 OS runners)
- Local Test Suite: Exit Code 0 (67/67 unit tests pass)
- Published Workstation Packages:
  1. Windows: `TitanRemoteHost.exe` (20.34 MB), `TitanRemoteHost-windows-x64.zip` (20.08 MB)
  2. Linux: `titan-remote-host` (36.14 MB), `titan-remote-host_amd64.deb` (35.91 MB), `titan-remote-host-linux-x64.tar.gz` (35.91 MB)
  3. macOS: `TitanRemoteHost` (17.80 MB), `titan-remote-host-macos.tar.gz` (17.59 MB)
  4. Checksums: `SHA256SUMS.txt` (Consolidated SHA256 hashes)

## Completed Features
1. **Multi-Platform Workstation Build Engine & CI/CD Matrix Pipeline:**
   - **Cross-Platform Build Tool (`scripts/build.py`):**
     - Windows: Tự động biên dịch `TitanRemoteHost.exe` và đóng gói `TitanRemoteHost-windows-x64.zip`.
     - Linux: Tự động biên dịch ELF standalone `titan-remote-host`, tạo gói Debian / Ubuntu `titan-remote-host_amd64.deb` chuẩn format `ar` + `control.tar.gz` + `data.tar.gz` (tích hợp systemd unit và desktop entry) và gói `titan-remote-host-linux-x64.tar.gz`.
     - macOS: Tự động biên dịch `TitanRemoteHost`, tạo gói `titan-remote-host-macos.tar.gz` (tích hợp launchd plist) và `.dmg`.
     - Tự động tính toán và xuất mã băm `SHA256SUMS.txt` cho toàn bộ artifact.
   - **Cross-Platform Guards & Headless CI Hardening:**
     - `host_agent/deployment_manager.py`: Guard an toàn `winreg`, hỗ trợ phân quyền người dùng và đường dẫn cài đặt trên Linux (`~/.titan_remote_host`, `/opt/titan-remote-host`) và macOS.
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
     - Relay Server hỗ trợ endpoint tải trực tiếp: `/api/download/titan-remote-host_amd64.deb`, `/api/download/titan-remote-host-linux-x64.tar.gz`, `/api/download/titan-remote-host-macos.tar.gz`, `/api/download/TitanRemoteHost-windows-x64.zip`.
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
   - Nguyên nhân: Trước đó vùng rỗng máy trạm (`deviceGrid`) được render động không có thuộc tính `data-i18n` và listener `titan-lang-changed` bỏ sót render lại view `dashboard`, khiến người dùng phải đợi bộ đếm polling 4 giây (`setInterval`) mới thấy đổi ngôn ngữ.
   - Giải pháp:
     - Gắn đầy đủ thuộc tính `data-i18n` vào toàn bộ template động của `renderDeviceGrid` (tiêu đề rỗng, gợi ý, nút tải cài đặt, nút kết nối nhanh, thẻ máy trạm).
     - Cache mảng thiết bị `currentDeviceList` và lập tức gọi `renderDeviceGrid(currentDeviceList)` khi bắt sự kiện `titan-lang-changed`.
     - Thêm helper `updateRoStatus()` và cập nhật tức thì telemetry góc trên bên trái (`roStatus`) theo ngôn ngữ lựa chọn.
     - Đồng bộ lại kích thước sliding pill indicator `placeAllIndicators()` khi chuyển đổi ngôn ngữ.
2. **Internationalization (i18n) Engine with Vietnamese & English Support:**
   - Bộ máy đa ngôn ngữ độc lập, zero-dependency với Tiếng Việt làm ngôn ngữ chính mặc định (`vi`) và Tiếng Anh (`en`) hoàn chỉnh cho toàn bộ giao diện và nghiệp vụ.
   - Hỗ trợ kiến trúc mở rộng (`registerLang`) cho phép bổ sung thêm ngôn ngữ khác (Nhật, Hàn, Trung,...) mà không cần sửa đổi mã nguồn xử lý.
   - Đồng bộ trạng thái: Nút chuyển đổi ngôn ngữ segmented pill `[VI] [EN]` ngay tại thanh điều khiển Topbar. Tự động lưu lựa chọn vào `localStorage` và duy trì liên kết URL qua tham số `?lang=en` / `?lang=vi`.
   - Cơ chế nội suy tham số động (`t(key, params)`), ràng buộc tự động qua các thuộc tính DOM (`data-i18n`, `data-i18n-title`, `data-i18n-placeholder`, `data-i18n-aria`).
   - Cập nhật thời gian thực không cần tải lại trang qua custom event `titan-lang-changed`.
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
   - Standardized flat script extraction in `%LOCALAPPDATA%\TitanRemoteHost`.
   - Dual-import fallback and sys.path auto-configuration in `gui_agent.py`, `host_service.py`, `input_injector.py`.
   - Native `ctypes` clipboard implementation in `clipboard_manager.py` replacing `win32clipboard`.
   - Repacked `relay-server/agent-package.zip`.
5. **Auto-Start on Boot / Login:**
   - Integrated Windows Registry Run entry `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\TitanRemoteHost`.
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
   - Thay thế toàn bộ cụm cầu vòm canvas vẽ đè lên chữ và 2 máy trạm trôi nổi ngoài lề bằng hệ thống **Holographic Topology Pipeline HUD** tích hợp ngay đầu bảng điều khiển [Cockpit Gateway](file:///D:/JOB/DEV/titan-remote/web-client/index.html#L185-L242).
   - Hiển thị trực quan 3 nút mạng thời gian thực: `[ MÁY ĐIỀU KHIỂN ]` ──(120 FPS)──► `[ TITAN RELAY ]` ──(4K READY)──► `[ MÁY TỪ XA ]` với đèn beacon nhịp thở (ping animation) và các luồng hạt photon ánh sáng chuyển động liên tục trên rãnh cáp quang (hardware-accelerated CSS keyframes).
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
   - Bổ sung cấu hình loại trừ triệt để tệp build PyInstaller (`build/`, `dist/`, `*.spec`, `*.exe`), tệp cấu hình runtime cá nhân (`config.json`, `.titan_remote_config.json`), cache kiểm thử (`.pytest_cache/`, `.coverage`), và tệp tạm OS/IDE.
20. **Infinity Lemniscate 2D Telemetry Canvas (MashLoop Customization):**
   - Tái tạo hệ thống vô cực $\infty$ (Lemniscate of Bernoulli) tùy biến chuyên sâu cho hạ tầng Titan Remote:
     - 180 khối gói dữ liệu số (digital telemetry blocks) uốn lượn liên tục quanh đường ray kép.
     - Phân cụm màu sắc topo: Cụm máy trạm (Host Station - Amber/Emerald bên trái), Cổng Outbound Relay (Nexus trung tâm - Trắng/Cyan), Cụm điều khiển (Client Cockpit - Cyan/Indigo bên phải).
     - Mạng lưới sợi quang cung vòm nội vi (Neural Telemetry Chords) kết nối hai thùy vô cực với nhịp thở mờ ảo.
     - Hai đầu photon động năng (Kinetic Energy Comets) quét dọc cung đường với quầng sáng radial bloom đa tầng và vệt sao chổi chiếu sáng các khối xung quanh.
     - Hồng tâm chuyển tiếp trung tâm (Relay Nexus Reticle) phát xung nhịp khi các photon dữ liệu băng qua tâm giao.
     - Tương tác chuột từ tính: Parallax góc nhìn, khối nở rộng khi rê chuột gần, sóng xung kích (shockwave ripple) kích hoạt khi click chuột.

21. **Official Titan Logo Branding & Binary Packaging (`dist/TitanRemoteHost.exe`):**
   - Thay thế icon lông vũ xanh mặc định của Tkinter bằng bộ nhận diện thương hiệu chính thức Titan (vòng tròn viền xanh lục neon `#22C55E`, nền đen `#070D17`, chữ "T" trắng in đậm):
     - Sinh bộ icon đa kích thước (`icon.ico` 16x16 đến 256x256, `icon.png` 256x256).
     - Gán Windows Taskbar grouping `SetCurrentProcessExplicitAppUserModelID("TitanRemote.WorkstationHost.2.0")` để taskbar và alt-tab hiển thị logo Titan riêng.
     - Cập nhật GUI Agent nạp `iconphoto` và `iconbitmap`.
     - Cập nhật System Tray nạp trực tiếp `icon.png` kèm fallback vẽ vector độ nét cao.
     - Cập nhật `TitanRemoteHost.spec` nhúng `icon='host_agent/icon.ico'` và `datas=[('host_agent', 'host_agent'), ('host_agent/icon.ico', '.'), ('host_agent/icon.png', '.')]`.
     - Biên dịch PyInstaller thành công bản `dist/TitanRemoteHost.exe` sạch.
     - Đồng bộ bản build mới vào `relay-server/TitanRemoteHost.exe`, đóng gói lại `relay-server/agent-package.zip`, và đồng bộ sang `%LOCALAPPDATA%\TitanRemoteHost\`.

22. **Grand-Scale Infinity Lemniscate & Instrument Telemetry Visualizer (`web-client/js/app.js` & `style.css`):**
   - **Tăng quy mô vô cực $\infty$ gấp 3 lần chiều cao (`scaleY` đạt 480-720px, `scaleX` đạt 560-920px):**
     - Đỉnh loop cao ~480-510px, uốn cong ôm trọn phía trên và quét xuống phía dưới toàn bộ cụm tiêu đề bên trái và cockpit bên phải mà không bị che khuất.
     - Bố cục lưới mở rộng `max-width: 1400px`, `gap: 60px;`, tạo khoang thở trung tâm cho điểm giao Nexus.
     - Thân cockpit chassis chuyển sang kính mờ ambient glass `rgba(11, 17, 26, 0.78)` kèm `backdrop-filter: blur(24px)`.
   - **Bổ sung chi tiết đo lường chuẩn `/ambient-instrument-ui` & MashLoop:**
     - **Thước đo Vernier Caliper (260 bước):** Các vạch chia độ chính xác (major 6.5px, minor 3.2px) dọc theo đường ray ngoài.
     - **Tọa độ vi mô (Milestone Micro-Stamps):** Nhãn số telemetry cố định dọc chu vi (`NODE-01 // HOST`, `NODE-02 // 0.8ms`, `CH-1 // 120FPS`,...).
     - **Khung định vị trạm biên (Lobe Milestone Reticles):** Khung góc quang học `┌ ┐ └ ┘` tại đỉnh trái (`NODE-01 // HOST WORKSTATION`) và đỉnh phải (`NODE-02 // CLIENT COCKPIT`).
     - **Mạng lưới sợi quang hài hòa mở rộng (28 Harmonic Chords):** Uốn cong đàn hồi và bị lực từ trường của con trỏ chuột hút về khi rê chuột lại gần (<160px).
     - **Cụm hạt Photon đa kênh:** Sao chổi chính kèm cụm 3 hạt vệ tinh bám đuôi và 4 xung dữ liệu cao tần (micro-pulses) chạy tốc độ cao.
     - **Holographic Gimbal Nexus tại tâm giao ($cx, cy$):** Vòng con quay trong xoay thuận chiều kim đồng hồ, vòng ngoài đứt đoạn xoay ngược chiều, lõi điểm kỳ dị bùng sáng quầng quang học khi hạt photon băng qua.
     - **Tia dẫn đường từ tính (Laser Vector Tether):** Khóa tiêu điểm và hiển thị khoảng cách thời gian thực (`LOCK // Xpx`) từ con trỏ tới điểm gần nhất trên vô cực.
     - **Mạng vi chòm sao lượng tử (Micro-Constellations):** 56 hạt bụi vũ trụ tự động kết nối dây tơ phát quang khi ở gần nhau (<65px).
     - **Sóng xung kích sắc sai kép (Dual Chromatic Shockwaves):** Vòng kép Cyan và Emerald lan tỏa khi nhấp chuột.

23. **Unified MashLoop Infinity Logo & Native WebView2 Desktop Host (`/ambient-instrument-ui`):**
   - **Đồng nhất Logo Vô Cực chuẩn MashLoop:**
     - Sử dụng vector Bézier chính xác từ MashLoop (`M256 256 C 312 168...`), stroke 44.8px.
     - Chuyển màu sang xanh neon `#22C55E`, nền đen studio `#070D17`, loại bỏ 100% viền ngoài (border).
     - Đặt chấm sáng trắng `#FFFFFF` tại tâm giao Nexus $(256, 256)$.
     - Xuất vector đa phân giải bằng Playwright: `host_agent/icon.png` (512x512), `host_agent/icon.ico` (đa kích thước 16, 24, 32, 48, 64, 128, 256px), và đồng bộ `web-client/favicon.svg`.
   - **Thiết kế lại toàn bộ Desktop Host GUI (`/ambient-instrument-ui`):**
     - Thay thế hoàn toàn giao diện Tkinter cũ bằng Microsoft Edge WebView2 (`pywebview 6.2.1` + `clr` Python.NET).
     - Xây dựng giao diện chuẩn studio `host_agent/gui_view.html`: Dark chamber `#070D17`, 100% inline SVG vector (zero-icon font / zero-emoji), segmented sliding pill nav, floating pill master start/stop, room ID/PIN glow cards, log terminal thời gian thực.
     - Cầu nối JavaScript <-> Python hai chiều (`window.pywebview.api` <-> `HostApi`): Quản lý vòng đời `HostService`, đổi Room/PIN, tự khởi động cùng Windows (Run on boot), chống tắt màn hình (Anti-Sleep `PowerManager`), chuyển đổi ngôn ngữ VI/EN.
     - Dark Titlebar DWM (`DwmSetWindowAttribute` 20/35/36), icon thanh tiêu đề Win32 `WM_SETICON`, clipboard chuẩn ctypes 64-bit.
     - Giữ nguyên `TitanHostGUI` làm engine fallback (`--legacy-tk`) và phục vụ bộ unit test i18n không làm gãy test.
   - **PyInstaller & Phân phối:**
     - Cập nhật `TitanRemoteHost.spec` nhúng `gui_view.html`, `icon.ico`, `icon.png` và hiddenimports (`clr`, `webview.platforms.winforms`).
     - Biên dịch thành công bản build mới `dist/TitanRemoteHost.exe` (Exit Code 0).
     - Đồng bộ bản build vào `relay-server/TitanRemoteHost.exe`, đóng gói lại `relay-server/agent-package.zip`, và cập nhật `%LOCALAPPDATA%\TitanRemoteHost\`.

24. **Custom Ambient Studio Titlebar & UI Thread Deadlock Fix (`/ambient-instrument-ui`):**
   - **Khắc phục lỗi treo cứng khởi động (Not Responding):**
     - *Nguyên nhân gốc rễ:* Trong `launch_webview_app`, hàm `on_loaded` được gọi đồng bộ trên UI Thread khi WebView2 hoàn tất tải trang. Lệnh `self.window.evaluate_js` gọi qua `edgechromium.py` thực hiện `semaphore.acquire()`, khóa UI Thread chờ callback. Tuy nhiên callback `ExecuteScriptAsync.ContinueWith` lại cần UI Thread (`self.syncContextTaskScheduler`) để nhả semaphore. Dẫn tới deadlock hai chiều, cửa sổ bị Windows đóng băng "Not Responding".
     - *Giải pháp:* Chuyển sang cơ chế kéo bất đồng bộ (Async Pull Pattern). Giao diện HTML tự gửi yêu cầu qua `window.pywebview.api.get_initial_data()` khi sự kiện `pywebviewready` kích hoạt. Mọi lệnh `_eval_js` từ Python sang JS được đẩy sang luồng daemon ngầm độc lập, bảo vệ UI Thread luôn phản hồi 100%.
   - **Tùy biến thanh tiêu đề Studio Ambient Dark (Custom Titlebar):**
     - Loại bỏ hoàn toàn thanh tiêu đề trắng sáng mặc định của Windows 10 (`frameless=True`, `easy_drag=True`).
     - Tích hợp thanh tiêu đề Studio `#060B14` đồng nhất 100% với dark chamber `#070D17`:
       - Bên trái: Logo vô cực MashLoop neon green `#22C55E` kèm tên ứng dụng monospace `TITAN REMOTE HOST`.
       - Ở giữa: Rãnh kéo cửa sổ đa màn hình với hỗ trợ Win32 `WM_NCLBUTTONDOWN` (`0x00A1`) và `.pywebview-drag-region`.
       - Bên phải: Nút thu nhỏ (`—`) và nút đóng (`✕`) chuẩn hover dark/red, liên kết trực tiếp `minimize_window()` và `close_window()`.
     - Phân bổ lại subheader bên trong: Telemetry máy trạm `PC-LOCAL // 120 FPS` ở bên trái, cụm nút chuyển ngôn ngữ `[ VI ] [ EN ]` và Status Pill ở bên phải, loại bỏ hoàn toàn tình trạng trùng lặp chữ.
   - **Biên dịch & Kiểm chứng:**
     - Đã biên dịch lại bản `dist/TitanRemoteHost.exe` sạch (Exit Code 0).
     - Đồng bộ `relay-server/TitanRemoteHost.exe`, cập nhật `relay-server/agent-package.zip` và thư mục máy trạm cục bộ.
     - Chạy thử nghiệm binary: PID 54228 chạy mượt mà, khởi động tức thì, không còn hiện tượng treo "Not Responding".

25. **HostService Constructor Signature Parity & Console Unicode Guard:**
   - **Lỗi văng khi nhấn "BẬT DỊCH VỤ":**
     - *Nguyên nhân 1 (TypeError):* Trong `HostApi.start_service`, hàm khởi tạo `HostService` bị truyền thừa 5 tham số không tồn tại (`device_token`, `account_owner`, `permanent_pin`, `on_client_connected`, `on_status_changed`), dẫn tới `TypeError: HostService.__init__() got an unexpected keyword argument 'device_token'` ngay khi click.
     - *Nguyên nhân 2 (UnicodeEncodeError):* Trên Windows console mặc định (`cp1252`), lệnh `print(f"[{t_str}] {msg}")` với tiếng Việt có dấu (`Khởi động dịch vụ thành công!`) bị lỗi `charmap codec can't encode character...`.
     - *Hậu quả gián tiếp (Treo Not Responding):* Khi hàm Python trong JS Bridge ném Exception, `pywebview.util.js_bridge_call` bắt lỗi và cố đẩy thông báo lỗi về JS qua `evaluate_js`, dẫn tới khóa UI thread lần thứ hai.
     - *Giải pháp:*
       1. Đồng bộ 100% chữ ký hàm `HostService(relay_url, room_id, pin, device_name, account)` và gán callback thuộc tính động (`on_status_change`, `on_client_connect`, `on_client_disconnect`, `on_chat_message`) giống kiến trúc `TitanHostGUI`.
       2. Bọc `print` trong `try...except` và cấu hình tự động `reconfigure(encoding='utf-8', errors='replace')` cho `sys.stdout` và `sys.stderr`.
       3. Bọc toàn bộ các hàm gọi bridge với `try...except` để bảo vệ JS bridge không bao giờ gặp unhandled exception.
   - **Biên dịch & Kiểm chứng:**
     - Chạy thử nghiệm trực tiếp `api.start_service()` trong Python: Dịch vụ khởi động và kết nối sạch, trả về `is_running: True`, ngắt kết nối an toàn.
     - Đã biên dịch lại bản `dist/TitanRemoteHost.exe` sạch (Exit Code 0).
     - Đồng bộ `relay-server/TitanRemoteHost.exe`, cập nhật `relay-server/agent-package.zip` và thư mục máy trạm cục bộ `%LOCALAPPDATA%\TitanRemoteHost\`.
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
     - Đã biên dịch lại bản `dist/TitanRemoteHost.exe` sạch (Exit Code 0).
     - Đồng bộ `relay-server/TitanRemoteHost.exe`, cập nhật `relay-server/agent-package.zip` và thư mục máy trạm cục bộ `%LOCALAPPDATA%\TitanRemoteHost\`.
     - Binary test: PID 54772 chạy ổn định, khởi động tức thì, Exit Code 0.

   27. **Interactive Multi-Monitor Drag-and-Drop Grid Layout & Portable EXE Lifecycle Overhaul:**
   - **Bố cục lưới đa màn hình kéo thả trên Web Client (`/ambient-instrument-ui`, `/ui-ux-pro-max`):**
     - Bổ sung vùng `#monitorGrid` với hệ thống các thẻ `.monitor-tile` hiển thị đồng thời các màn hình của máy trạm.
     - Cắt lát frame GPU Canvas không tốn thêm băng thông (`drawImage` sub-rectangle từ frame Virtual Desktop tổng).
     - Cho phép kéo thả (HTML5 Drag & Drop) để tráo đổi vị trí các màn hình theo bất kỳ thứ tự nào (lưu cấu hình vào `localStorage`).
     - Tích hợp các nút chuyển đổi bố cục nhanh: `◄ ► Ngang`, `► ◄ Đảo ngược`, `▲ ▼ Dọc`.
     - Điều phối tọa độ chuột độc lập theo từng ô màn hình: rê chuột, click chuột trái/phải, con lăn chuột đều gửi kèm `monitor_id` giúp `InputInjector` click trúng đích 100%.
   - **Khắc phục triệt để hạn chế của Portable EXE:**
     - Mô-đun `host_agent/deployment_manager.py`: Tự động sao chép bảo vệ đường dẫn vào `%LOCALAPPDATA%\TitanRemoteHost\TitanRemoteHost.exe` khi bật tự khởi động, loại bỏ hoàn toàn lỗi gãy đường dẫn khi xóa file trong `Downloads` hoặc rút USB.
     - Nâng quyền UAC qua Task Scheduler (`schtasks.exe /create /tn TitanRemoteHost /sc onlogon /rl highest /f`): Chạy với quyền Administrator cao nhất lúc đăng nhập, khắc phục triệt để lỗi đen màn hình và kẹt chuột khi máy trạm bật cửa sổ UAC/Task Manager.
     - Windows Service Mode 24/7 (`sc.exe create TitanRemoteService`): Cho phép phần mềm tự động chạy ngầm ngay từ khi bật máy trước khi có người đăng nhập (Lock screen).
     - Bổ sung các cờ dòng lệnh CLI: `--install-service`, `--uninstall-service`, `--service` và tích hợp nút bật/tắt dịch vụ trực quan trong tab "QUẢN TRỊ 24/7" của Host GUI.
   - **Biên dịch & Triển khai:**
     - Đã biên dịch lại bản `dist/TitanRemoteHost.exe` sạch (Exit Code 0).
     - Đồng bộ `relay-server/TitanRemoteHost.exe`, cập nhật `relay-server/agent-package.zip` và thư mục máy trạm cục bộ `%LOCALAPPDATA%\TitanRemoteHost\`.
     - Binary test: PID 61096 chạy ổn định, khởi động tức thì, Exit Code 0.

    28. **2-Tier Installation UX Architecture (User-Level Zero-Admin vs System-Level Service with UAC Elevation) & Visual Cards Deck:**
    - **Phân cấp kiến trúc cài đặt 2 tầng rõ ràng (User vs Admin):**
      - **Tầng 1: Cài đặt Người dùng (User Level - Zero Admin):**
        - Dành cho môi trường doanh nghiệp hoặc tài khoản văn phòng không có mật khẩu Admin.
        - Tự động sao chép binary vào thư mục an toàn cá nhân `%LOCALAPPDATA%\TitanRemoteHost\TitanRemoteHost.exe`.
        - Đăng ký tự khởi động qua `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` và Task Scheduler chế độ người dùng chuẩn (`/rl limited`).
        - Hoạt động 100% không yêu cầu hộp thoại UAC hay mật khẩu Admin.
      - **Tầng 2: Dịch vụ Hệ thống 24/7 (System Service - Cần Admin UAC):**
        - Dành cho máy chủ hoặc máy trạm cần truy cập từ xa mọi lúc, kể cả trước khi đăng nhập Windows (Lock Screen / Login Screen).
        - Khi bấm "Cài Đặt Dịch Vụ 24/7", nếu đang chạy quyền thường sẽ tự động nâng quyền thông qua `ShellExecuteW(..., 'runas', ...)` mở hộp thoại Windows UAC yêu cầu cấp quyền đúng 1 lần duy nhất.
        - Cài đặt vào `%ProgramData%\TitanRemoteHost\`, đăng ký và kích hoạt Windows Service `TitanRemoteService` (`sc.exe create ... start= auto`), đồng thời tạo Task Scheduler `/rl highest` cho quyền Administrator cao nhất.
    - **Giao diện thẻ trực quan Ambient Dark (`/ambient-instrument-ui`, `/ui-ux-pro-max`):**
      - Thiết kế lại toàn bộ tab "QUẢN TRỊ 24/7" trên Host GUI thành 2 thẻ lựa chọn độc lập:
        - Thẻ 1: `CÀI ĐẶT NGƯỜI DÙNG // USER LEVEL` kèm huy hiệu xanh lục `[ KHÔNG CẦN ADMIN ]`, nút bấm `Cài Đặt Vào User` / `Gỡ Cài Đặt User`.
        - Thẻ 2: `DỊCH VỤ HỆ THỐNG 24/7 // SYSTEM SERVICE` kèm huy hiệu vàng hổ phách `[ CẦN ADMIN (UAC) ]`, nút bấm `Cài Đặt Dịch Vụ 24/7` / `Gỡ Bỏ Dịch Vụ 24/7`.
      - Hỗ trợ đầy đủ song ngữ Việt - Anh (VI / EN).
    - **Biên dịch & Triển khai:**
      - Đã biên dịch lại bản `dist/TitanRemoteHost.exe` mới nhất bằng PyInstaller (Exit Code 0).
      - Đồng bộ `relay-server/TitanRemoteHost.exe`, cập nhật `relay-server/agent-package.zip` và thư mục máy trạm cục bộ `%LOCALAPPDATA%\TitanRemoteHost\`.
      - Toàn bộ 49/49 unit tests chạy thành công (Exit Code 0).

    29. **Cross-Platform Workstation Host Architecture & 3 Deck Display Modes (Bottom Float, Top Pinned, Top Auto-hide Unpinned):**
    - **Kiến trúc Hỗ trợ Đa Nền Tảng Máy Trạm (Workstation Host):**
      - **Windows (10/11/Server):** Hỗ trợ 100% Native Win32 API (DXGI/GDI, SendInput, WASAPI, UAC Elevation, 2-Tier Deployment, Windows Service 24/7). Đã đóng gói thành file thực thi `.exe`.
      - **Linux (Ubuntu, Debian, Fedora, Arch, Raspberry Pi OS):** Hỗ trợ 100% qua X11/Wayland Screen Grab, `pynput` / `pyautogui`, Bash/Zsh interactive shell, `systemctl` / `poweroff`. Cung cấp script launcher `run_agent_linux.sh` và systemd unit `titan-remote.service` chạy ngầm 24/7.
      - **macOS (Intel & Apple Silicon M1-M4):** Hỗ trợ 100% sau khi cấp quyền Screen Recording & Accessibility trong macOS System Settings. Cung cấp script launcher `run_agent_macos.sh` và `com.titan.remote.plist` qua Launchd.
      - **iOS (iPhone) & iPadOS (iPad):** Làm rõ giới hạn kỹ thuật kiến trúc bảo mật của Apple: Apple áp dụng cơ chế Sandbox tuyệt đối, cấm hoàn toàn synthetic touch injection vào ứng dụng bên thứ 3 hoặc SpringBoard (ngay cả TeamViewer/AnyDesk trên iOS cũng chỉ là View-only). Không thể chạy ngầm unmanaged host trên iOS/iPadOS nếu không Jailbreak.
      - **Cross-Platform Guard trong Code:** Toàn bộ các module `screen_capture.py`, `input_injector.py`, `power_manager.py`, `terminal_manager.py`, `clipboard_manager.py`, `deployment_manager.py` đều được bảo vệ bằng platform-guards an toàn, không bao giờ bị crash vì `ctypes.windll` khi chạy trên non-Windows.
    - **3 Chế độ hiển thị Floating Deck linh hoạt trên Web Client (`/ambient-instrument-ui`, `/ui-ux-pro-max`):**
      - **Chế độ 1: Dạng đáy nổi (`bottom-float`):** Thanh pill lơ lửng ở đáy màn hình như mặc định, làm mờ sau 3.5s không thao tác.
      - **Chế độ 2: Mép trên - Ghim cố định (`top-pinned`):** Dock vào đỉnh màn hình (`top: 0`), bo góc dưới, luôn hiển thị, không che thanh Taskbar Windows ở đáy của máy trạm.
      - **Chế độ 3: Mép trên - Tự động ẩn khi rời chuột (`top-unpinned`):** Mặc định ẩn hoàn toàn lên mép trên (`transform: translate(-50%, -100%)`). Có tai kéo phát sáng `#deckTopTrigger` ở chính giữa mép trên. Khi rê chuột vào mép trên (hover trong phạm vi 14px) hoặc chạm vào tai kéo, thanh deck trượt mượt mà xuống để thao tác. Khi chuột rời khỏi deck, sau 450ms tự động trượt thu gọn lên trên. Tránh đè lên 100% các phần giao diện cần thao tác của máy trạm.
      - **Điều khiển trực quan & Lưu cấu hình:** Nút chuyển vị trí `#btnDeckDisplayMode` mở popover lựa chọn 3 chế độ kèm radio checkmark, nút ghim/bỏ ghim nhanh `#btnDeckPinQuick` khi ở mép trên, tự động lưu và khôi phục từ `localStorage.getItem('titan_deck_mode')`. Hỗ trợ đầy đủ cử chỉ chạm Touch/Tablet cho iPadOS và mobile.
    - **Tài liệu chuyên sâu:** Bổ sung `docs/cross-platform-workstation-guide.md` phân tích toàn diện ma trận hệ điều hành và hướng dẫn cài đặt trên Linux/macOS.
    - **Biên dịch & Triển khai:**
      - Đã biên dịch lại bản `dist/TitanRemoteHost.exe` mới nhất bằng PyInstaller (Exit Code 0).
      - Đồng bộ `relay-server/TitanRemoteHost.exe`, cập nhật `relay-server/agent-package.zip` và thư mục máy trạm cục bộ `%LOCALAPPDATA%\TitanRemoteHost\`.
      - Toàn bộ 56/56 unit tests chạy thành công (Exit Code 0).

    30. **Sửa Lỗi CSS / Active Tab Indicator Khi Chưa Đăng Nhập:**
    - **Triệu chứng lỗi ban đầu:** Ở trang chủ, tab "Trang chủ" hiển thị indicator xanh lục chữ đen đậm chuẩn. Nhưng khi bấm sang tab khác (ví dụ "Máy trạm") trong trạng thái chưa đăng nhập, hệ thống điều hướng vào view `auth` nhưng indicator xanh lục `.seg__ind` bị kẹt lại ở "Trang chủ", trong khi nút "Trang chủ" lại bị gỡ class `.on` làm chữ chuyển sang màu mờ (`var(--text-muted)`) đè lên nền xanh phát sáng, gây vỡ tương phản thị giác.
    - **Nguyên nhân cốt lõi:**
      1. Trong `web-client/js/app.js`: Hàm `placeIndicator(seg)` kiểm tra `if (!onBtn || !ind) return;`. Khi chuyển sang `auth`, không có nút nào trong `mainNav` có `data-view="auth"`, nên `onBtn` là `null`. Hàm trả về sớm mà không ẩn indicator, khiến `.seg__ind` giữ nguyên tọa độ và kích thước cũ ở "Trang chủ".
      2. Trong `web-client/css/style.css`: `.seg button.on` gán trùng lặp `background: var(--accent)`, trong khi `.seg__ind` lại để `z-index: -1` và không có hiệu ứng chuyển đổi `opacity`.
      3. Sự kiện click `mainNav` chưa lưu lại tab mục tiêu mà người dùng muốn truy cập vào `sessionStorage`.
    - **Giải pháp xử lý:**
      1. Cập nhật `placeIndicator(seg)`: Khi `!onBtn`, lập tức gán `ind.style.setProperty('--ind-w', '0px')` và `ind.style.opacity = '0'` với transition mượt mà.
      2. Tối ưu CSS theo chuẩn MashLoop (`ambient-instrument-ui`): `.seg button` có `position: relative; z-index: 2; background: transparent;`. Nút `.on` có `color: var(--on-accent); background: transparent; font-weight: 600;`. `.seg__ind` có `z-index: 1; pointer-events: none;` kèm transition cả `transform`, `width`, `opacity`. Nền pill duy nhất do `.seg__ind` đảm nhiệm, triệt tiêu hoàn toàn lỗi chồng chéo màu hoặc chữ mờ trên nền xanh.
      3. Lưu tuyến đường đang chờ `sessionStorage.setItem('titan_pending_route', view)` khi click tab lúc chưa đăng nhập để tự động chuyển tiếp sau khi đăng nhập thành công.
      4. Tự động cập nhật `placeIndicator(authTabs)` khi view `auth` hiển thị.

    31. **Nâng Cấp Toàn Diện Landing Page Đa Nền Tảng & Sửa Tràn Bố Cục UI:**
    - **Nâng cấp Landing Page:**
      - **Dải huy hiệu đa nền tảng:** Bổ sung thanh OS Support Strip (`.landing-os-strip`) hiển thị trực quan các nền tảng máy trạm: Windows (EXE / 2-Tier), Linux (Systemd / X11), macOS (Apple Silicon M1-M4), Web & iPadOS (Zero-Install).
      - **Mạng lưới tính năng chuẩn Studio (6 thẻ cân đối):** 120 FPS & Đa màn hình (Multi-Monitor Grid), Thanh Floating Deck 3 chế độ, Máy trạm đa nền tảng Win/Mac/Linux, Âm thanh 2 chiều & Mic Talkback, Terminal tương tác thời gian thực, Quản lý tệp 2 chiều & Sửa trực tiếp.
      - **Trung tâm Tải về đa nền tảng (Download Hub Matrix):** Tích hợp thanh trượt chọn phân hệ (`#dlPlatformSeg`) với 4 tab độc lập: Windows (EXE, BAT, PowerShell), Linux (Bash 1-liner curl, Systemd unit, ARM64/Headless), macOS (macOS 1-liner curl, Apple Silicon, Launchd plist), Web & iPadOS (Trình duyệt trực tiếp, Touch / Pencil gestures, Bàn phím ảo).
      - **API phục vụ tải script cài đặt:** Bổ sung các endpoint `/api/download/install-linux.sh`, `/api/download/install-macos.sh`, `/api/download/titan-remote.service`, `/api/download/com.titan.remote.plist` trên Relay Server.
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
- PyInstaller Build: `.\.venv\Scripts\pyinstaller.exe TitanRemoteHost.spec --clean --noconfirm` -> Exit Code 0.
- Binary Execution Test: `dist/TitanRemoteHost.exe --help` -> Exit Code 0.
- Python Syntax: `.\.venv\Scripts\python.exe -m py_compile host_agent/*.py` -> Exit Code 0.
- JavaScript Syntax: `node -c web-client/js/app.js` & `node -c web-client/js/i18n.js` & `node -c relay-server/server.js` -> Exit Code 0.
- CSS Braces Balance: 419 open / 419 close (Depth 0).
- Relay Server: Active on port 8080 (endpoints `/api/health`, `/api/download/install-linux.sh`, `/api/download/install-macos.sh` verified with 200 OK).




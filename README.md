# Meikova Relay

<div align="center">

<img src="docs/assets/logo.png" alt="Meikova Relay Logo" width="160px">

[![CI/CD Pipeline](https://img.shields.io/github/actions/workflow/status/Meikova/meikova-relay/build-release.yml?branch=main&style=flat-square)](https://github.com/Meikova/meikova-relay/actions/workflows/build-release.yml)
[![Latest Release](https://img.shields.io/github/v/release/Meikova/meikova-relay?color=059669&style=flat-square)](https://github.com/Meikova/meikova-relay/releases)
[![Platforms](https://img.shields.io/badge/Platforms-Windows%20%7C%20Linux%20%7C%20macOS%20%7C%20Web-2563eb?style=flat-square)](https://github.com/Meikova/meikova-relay)
[![Security Shield](https://img.shields.io/badge/Security-OWASP%20Top%2010%20Hardened-83E8AC?style=flat-square)](https://github.com/Meikova/meikova-relay)
[![Architecture](https://img.shields.io/badge/Architecture-Outbound--Only%20WSS-7c3aed?style=flat-square)](https://github.com/Meikova/meikova-relay)
[![License](https://img.shields.io/badge/License-MIT-16a34a?style=flat-square)](LICENSE)

**Hệ thống điều khiển máy tính từ xa thế hệ mới: Độ trễ siêu thấp, chuẩn màu 1:1 Pixel-Perfect, truyền tải âm thanh trực tiếp, lá chắn bảo mật OWASP Top 10 và vượt qua 100% tường lửa doanh nghiệp.**

[Dùng Thử Web Client](https://meikova-relay.onrender.com) | [Tải Gói Máy Trạm](https://github.com/Meikova/meikova-relay/releases) | [Tài Liệu Triển Khai](docs/DEPLOYMENT_GUIDE.md)

</div>

---

## 1. Tổng quan hệ thống

Meikova Relay là giải pháp Remote Desktop toàn diện, độc lập, được thiết kế tối ưu cho:

- **Môi trường mạng doanh nghiệp khắt khe**: Hoạt động ổn định trong mạng chặn toàn bộ giao thức UDP, không có IPv6 công cộng và không thể mở cổng (Port Forwarding).
- **Bảo mật Outbound-Only**: Máy trạm (Host Agent) chỉ mở kết nối một chiều từ trong ra ngoài tới Relay Server qua cổng tiêu chuẩn **443 (HTTPS/WSS)**.
- **Client Zero-Install**: Người điều khiển sử dụng trình duyệt web hiện đại (Chrome, Edge, Safari, Firefox trên PC, Mac, iPad, iPhone, Android) mà không cần cài thêm plugin.
- **Tự trị không cấu hình (Zero-Config Engine)**: Tự động dự phòng cơ sở dữ liệu nội bộ SQLite WAL khi không có biến môi trường hoặc cơ sở dữ liệu đám mây, khởi động 1-chạm không lỗi.

```
+-----------------------------------------------------------------------------------------+
|                                LUỒNG TRUYỀN DẪN DỮ LIỆU                                 |
+-----------------------------------------------------------------------------------------+

 [MÁY TRẠM (HOST AGENT)]                                   [NGƯỜI ĐIỀU KHIỂN (WEB CLIENT)]
 - Windows (Win32 GDI / DXGI)                              - HTML5 Canvas 2D / Offscreen
 - Linux (X11 / Scrot)                                     - Bàn phím / Chuột / Cảm ứng
 - macOS (CoreGraphics / ScreenCapture)                    - Web Audio 48kHz Stereo Loopback
         \                                                         /
          \---- [ Outbound WSS:443 ]                     [ HTTPS / WSS:443 ] ----/
                                    \                   /
                                     v                 v
                    +----------------------------------------------------+
                    |         MEIKOVA RELAY SERVER (Node.js Engine)      |
                    |  - Lá chắn OWASP Top 10 & Chống DDoS Payload trần 1MB|
                    |  - Khóa IP 5-Strike Lockout & Uniform Timing Delay |
                    |  - Khóa định danh Host Secret chống chiếm quyền    |
                    |  - Bộ định tuyến WebSocket Room ID / PIN CSPRNG   |
                    |  - Google OAuth 2.0 (GIS) & JWT Session Manager    |
                    |  - SQLite WAL Database (Zero-Config Tự trị)        |
                    +----------------------------------------------------+
```

---

## 2. Lá chắn Bảo mật Đa Tầng OWASP Top 10 (v1.5.2)

Bản phát hành **v1.5.2** nâng cấp toàn diện cơ chế phòng thủ an ninh theo chuẩn OWASP Top 10 (2021/2025), triệt tiêu các nguy cơ tấn công chiếm quyền, bắt tay 3 bước giả mạo và từ chối dịch vụ:

### A01: Broken Access Control & Anti-Hijacking
- **Cryptographic Host Secret**: Máy trạm đầu tiên đăng ký Room ID nhận một bí mật ngẫu nhiên 24-byte (`host_secret`). Mọi yêu cầu tái kết nối hoặc mạo danh phòng bắt buộc phải xuất trình đúng bí mật này; kẻ tấn công gửi gói tin giả mạo lập tức bị máy chủ từ chối với mã `RELAY_HOST_UNAUTHORIZED`.
- **Sensitive File Access Sandbox**: Module Quản lý Tệp (FileManager) áp dụng bộ lọc đường dẫn nghiêm ngặt trên cả Windows và POSIX. Chặn hoàn toàn việc duyệt, đọc và ghi đè các tệp nhạy cảm của hệ thống: SAM, SYSTEM, SECURITY, `/etc/shadow`, `/etc/passwd`, `/etc/sudoers`, `.ssh/id_rsa`, `.env*`, cũng như cookie và dữ liệu đăng nhập của trình duyệt Chrome/Edge.

### A02: Cryptographic Failures & CSPRNG Entropy
- **CSPRNG Room ID & PIN**: Thay thế toàn bộ hàm sinh số ngẫu nhiên dự đoán được (Mersenne Twister) bằng CSPRNG chuẩn hệ điều hành (`secrets.SystemRandom()` trong Python, `crypto.randomBytes` trong Node.js).
- **Định dạng Room ID 9 chữ số**: Nâng cấp định dạng phòng thành 9 chữ số phân đoạn `RD-XXX-XXX-XXX`, nâng không gian khóa lên $10^9$ kết hợp cùng mã PIN 6 chữ số ($10^6$), triệt tiêu nguy cơ đoán mò ID phòng.

### A04: Insecure Design & Privacy Curtain Physical Fail-Safe
- **Lối thoát Khẩn cấp Bàn phím Vật lý (Emergency Escape)**: Trong chế độ Rèm Che (Privacy Curtain - màn hình đen và khóa bàn phím chuột tại chỗ), nếu người dùng ngồi trước máy trạm nhấn phím vật lý `Esc` 3 lần liên tiếp trong vòng 1.5 giây, hook bàn phím mức thấp sẽ kích hoạt cơ chế an toàn khẩn cấp, lập tức hủy rèm che và hoàn trả toàn bộ quyền điều khiển chuột phím.

### A07: Identification & Auth Failures (5-Strike Lockout & Uniform Timing)
- **5-Strike Lockout**: Mọi địa chỉ IP nhập sai mã PIN hoặc thông tin xác thực 5 lần liên tiếp sẽ bị khóa lập tức trong vòng 15 phút (`429 Too Many Requests` trên REST hoặc ngắt kết nối WebSocket với mã lỗi 4003 `RELAY_RATE_LIMITED`).
- **Uniform Timing Equalizer**: Khi kiểm tra kết nối tới phòng không tồn tại hoặc sai mã PIN, hệ thống áp dụng cùng một mã lỗi `RELAY_AUTH_FAILED` đi kèm độ trễ ngẫu nhiên có kiểm soát (300ms + 50ms jitter), ngăn chặn kỹ thuật timing attack và room enumeration oracle.

### A10: DoS, DDoS & Resource Exhaustion Defense
- **HTTP Body Payload Guard**: Trần dung lượng request JSON tối đa **1MB**. Mọi payload vượt quá giới hạn lập tức bị từ chối với HTTP 413 `PAYLOAD_TOO_LARGE` kèm kỹ thuật drain stream chuẩn, bảo vệ máy chủ khỏi nguy cơ cạn kiệt bộ nhớ (OOM).
- **Slowloris Timeout Guard**: Áp dụng `headersTimeout = 10s` và `requestTimeout = 30s` trên máy chủ HTTP, triệt tiêu tấn công treo kết nối truyền dữ liệu chậm.
- **WebSocket IP Connection Cap**: Giới hạn tối đa 32 kết nối WebSocket đồng thời trên mỗi địa chỉ IP (cấu hình linh hoạt qua biến `MAX_WS_PER_IP`).
- **Token Bucket Flooding Guard**: Áp dụng thuật toán Token Bucket trên từng kết nối WebSocket (sức chứa 120 tokens, nạp lại 60 tokens/giây). Các gói tin điều khiển gửi ồ ạt vượt ngưỡng sẽ bị chặn với mã `RELAY_MESSAGE_FLOOD`.

---

## 3. Tính năng nổi bật

### Cơ sở dữ liệu Tự trị Không cấu hình (Zero-Config Database Engine)
- Khi khởi chạy máy chủ mà không có tệp cấu hình `.env` hoặc cơ sở dữ liệu đám mây Turso, máy chủ tự động khởi tạo cơ sở dữ liệu SQLite cục bộ ở chế độ Write-Ahead Logging (WAL) tại `%LOCALAPPDATA%\MeikovaRelay\meikova_relay.db` (trên Windows) hoặc `~/.meikova-relay/meikova_relay.db` (trên Linux/macOS).
- Đảm bảo tính sẵn sàng 100%, cắm là chạy ngay (Out-of-the-box) mà không phát sinh lỗi khởi động.

### Hiệu ứng Trượt Thích ứng (Tactile Sliding Tab Indicators)
- Thanh điều hướng và các bộ chuyển đổi phân đoạn (Segmented Controls) sử dụng chỉ báo trượt CSS linh hoạt (`.seg__ind`) kết hợp biến CSS `@property` mượt mà, phản hồi tức thì theo kích thước phím bấm trên mọi độ phân giải màn hình từ Desktop tới Mobile.

### Quản trị máy trạm toàn diện (Host Master Architecture)
- **Mở khóa màn hình Winlogon & Xử lý UAC Desktop**: Triệt tiêu hoàn toàn hiện tượng màn hình đen khi máy trạm bị khóa (`Win + L`) hoặc khi xuất hiện cửa sổ xác nhận quyền quản trị UAC (Secure Desktop). Hỗ trợ lệnh và modal mở khóa từ xa 1 chạm an toàn.
- **Quản trị nguồn thông minh (Smart Keep-Awake & RTC Wakeup)**: Tự động kích hoạt cờ Win32 `SetThreadExecutionState` ngăn máy trạm tắt màn hình/ngủ khi có client kết nối và hoàn trả chế độ tiết kiệm điện khi ngắt kết nối. Hỗ trợ đặt lịch hẹn giờ thức dậy BIOS RTC Wake Timer và phát gói Wake-on-LAN UDP.
- **Xung nhịp phần cứng thời gian thực (Hardware Pulse Telemetry 2s)**: Thu thập thông số CPU %, RAM %, Pin/Nguồn qua Win32 API thuần, gửi định kỳ 2 giây hiển thị badge trực quan trên thanh điều khiển Client Dock.
- **Live Auto-Update nền (NTFS Rename Atomic Swap)**: Máy trạm tự động thăm dò phiên bản mới từ Relay Server, tải bản vá và hoán đổi tệp thực thi nguyên tử không gián đoạn dịch vụ.
- **Giải phóng phím kẹt khẩn cấp (Emergency Input Unstick)**: Quét và nhả toàn bộ 256 phím ảo (`Ctrl`, `Alt`, `Shift`, `Win`) cùng các nút chuột khi ngắt kết nối hoặc qua nút bấm trong danh mục công cụ.
- **Đồng bộ ảnh Clipboard hai chiều**: Hỗ trợ copy-paste hình ảnh chụp màn hình trực tiếp giữa máy trạm và trình duyệt qua định dạng `CF_DIB` / Base64 PNG.
- **Ma trận 25+ tham số SSOT**: Hỗ trợ đầy đủ trên 10 kênh cài đặt (Windows EXE, `.bat`, PowerShell, Linux Bash, `.deb`, `.tar.gz`, macOS Bash, `.dmg`, `Portable ZIP`, `config.json`), đồng bộ 2 chiều thời gian thực trong phiên remote qua modal cấu hình chuyên dụng.

### Sao chép màn hình 1:1 Pixel-Perfect và tự động đàm phán ma trận
- **1:1 Native Replica**: Hiển thị chính xác từng điểm ảnh gốc không nén vỡ hình (`image-rendering: pixelated; crisp-edges`). Hỗ trợ kéo di chuyển khung hình (Pan) bằng chuột giữa hoặc `Alt + Chuột trái` khi máy trạm có độ phân giải lớn hơn thiết bị điều khiển.
- **Tự động đo đạc và cấu hình thích ứng**:
  - Tần số quét >= 120Hz: Tự động kích hoạt Ultra 120 FPS.
  - Màn hình độ phân giải cao: Kích hoạt Crisp 2K / 4K với thuật toán xử lý độ nét cao.
  - Chế độ điều chỉnh linh hoạt: 1:1 Chuẩn Gốc, Cân bằng (30 FPS), Siêu mượt (60 FPS), Tiết kiệm băng thông.
- **Hỗ trợ đa màn hình (Multi-Monitor Grid)**: Nhận diện danh sách màn hình gắn trên máy trạm, chuyển đổi giữa Màn 1, Màn 2 hoặc kéo thả sắp xếp trên lưới Grid theo thực tế vật lý.

### Trải nghiệm điều khiển di động toàn diện (Mobile Touch & Responsive)
- **Động cơ cử chỉ cảm ứng (Touch-First Controller)**:
  - Chạm 1 ngón (Single Tap): Gửi chuỗi sự kiện Click hoàn chỉnh kèm hiệu ứng sóng phản hồi Cyan trực quan.
  - Nhấp đúp (Double Tap): Gửi Double Click nguyên bản.
  - Nhấn giữ 450ms (Long Press): Kích hoạt Chuột phải (Right Click) kèm rung phản hồi xúc giác (`45ms`).
  - Nút chuột phải chuyên dụng: Tích hợp trực tiếp trên Floating Deck cho thao tác chính xác tức thì.
  - Cử chỉ 2 ngón: Vuốt cuộn trang (Mouse Wheel) và Chụm thu phóng (Pinch Zoom).
- **Cầu nối bàn phím ảo (Native Soft Keyboard Bridge)**: Mở bàn phím ảo gốc của điện thoại/máy tính bảng, nhập liệu ký tự Unicode tiếng Việt và phím chức năng (`Backspace`, `Enter`, `Tab`, `Esc`).
- **Thanh phím tắt nhanh (Mobile Quick Keys Bar)**: Thao tác 1-chạm với các phím thông dụng (`Ctrl+Alt+Del`, `Esc`, `Tab`, `Win`, `Space`, `Enter`, `Back`, `Alt+Tab`).
- **Tối ưu hiển thị Stage & Safe Area**: Tự động mở rộng Canvas stage toàn màn hình (`100vw x 100dvh`), triệt tiêu thanh cuộn trang thừa và bảo vệ vùng an toàn (`env(safe-area-inset-*)`).

---

## 4. Danh mục gói cài đặt máy trạm (Downloads)

Gói cài đặt được biên dịch và đóng gói tự động qua GitHub Actions CI/CD:

| Hệ điều hành | Tệp phát hành | Định dạng | Mô tả |
| :--- | :--- | :--- | :--- |
| Windows | [`MeikovaRelayHost.exe`](https://github.com/Meikova/meikova-relay/releases/latest) | Standalone Exe | Chạy trực tiếp không cần cài đặt hoặc cài dịch vụ 24/7 |
| Windows | [`MeikovaRelayHost-Setup.exe`](https://github.com/Meikova/meikova-relay/releases/latest) | Inno Setup | Trình cài đặt chuẩn với Wizard tiếng Việt & tiếng Anh |
| Windows | [`MeikovaRelayHost-windows-x64.zip`](https://github.com/Meikova/meikova-relay/releases/latest) | Zip Archive | Bộ cài đặt đầy đủ kèm tệp cấu hình và tài nguyên |
| Linux | [`meikova-relay-host_amd64.deb`](https://github.com/Meikova/meikova-relay/releases/latest) | Debian / Ubuntu | Gói cài đặt tích hợp App Icon và Systemd service |
| Linux | [`meikova-relay-host-linux-x64.tar.gz`](https://github.com/Meikova/meikova-relay/releases/latest) | Tarball | Dành cho các bản phân phối Linux khác (Fedora, Arch, RHEL) |
| Linux | [`meikova-relay-host`](https://github.com/Meikova/meikova-relay/releases/latest) | Standalone ELF | Tệp thực thi nhị phân cho Server / CLI |
| macOS | [`meikova-relay-host-macos.tar.gz`](https://github.com/Meikova/meikova-relay/releases/latest) | Tarball | Gói cài đặt macOS kèm cấu hình LaunchAgent |
| macOS | [`MeikovaRelayHost`](https://github.com/Meikova/meikova-relay/releases/latest) | Mach-O Binary | Tệp thực thi chạy trực tiếp từ Terminal macOS |
| Đối soát | [`SHA256SUMS.txt`](https://github.com/Meikova/meikova-relay/releases/latest) | Text | Bảng mã băm SHA-256 đối chiếu tính toàn vẹn |

---

## 5. Hướng dẫn bắt đầu nhanh (Quick Start)

### Bước 1: Khởi động máy trạm (Host Agent)

1. Tải bản phù hợp từ [GitHub Releases](https://github.com/Meikova/meikova-relay/releases/latest).
2. Chạy ứng dụng `MeikovaRelayHost`:
   - Giao diện hiển thị **Mã Máy Trạm** (Room ID dạng `RD-XXX-XXX-XXX`) và **Mã PIN Kết Nối** (6 chữ số ngẫu nhiên).
   - Tùy chọn chạy cấp Người dùng (User) tự khởi động cùng máy, hoặc Dịch vụ Hệ thống (Admin Service) chạy nền 24/7.

### Bước 2: Điều khiển từ xa (Web Client)

1. Truy cập cổng Web Hub: [https://meikova-relay.onrender.com](https://meikova-relay.onrender.com).
2. Đăng nhập tài khoản hoặc chọn Đăng nhập bằng Google.
3. Chọn thiết bị trong danh bạ hoặc bấm **Kết nối nhanh**, nhập Room ID và PIN.
4. Màn hình máy tính hiển thị ngay lập tức với đầy đủ thao tác chuột, phím và âm thanh.

---

## 6. Hướng dẫn triển khai máy chủ riêng (Self-Hosted)

Chi tiết xem tại: [Tài liệu Triển Khai Hệ Thống (DEPLOYMENT_GUIDE.md)](docs/DEPLOYMENT_GUIDE.md)

Lệnh khởi chạy máy chủ Node.js:

```bash
git clone https://github.com/Meikova/meikova-relay.git
cd meikova-relay/relay-server
npm install
npm start
```

*Máy chủ mặc định lắng nghe tại cổng `8080` (HTTP + WebSocket). Tự động dùng SQLite WAL nội bộ nếu không cấu hình `.env`.*

---

## 7. Triển khai Docker (Container-Native)

Dự án hỗ trợ triển khai máy chủ độc lập 100% thông qua Docker và Docker Compose, tích hợp sẵn Node.js 22-slim và công cụ đường hầm `cloudflared`:

```bash
# Khởi chạy máy chủ relay
docker compose up -d

# Xem logs trực tiếp
docker compose logs -f

# Tự động mở Cloudflare Quick Tunnel xuyên tường lửa/NAT
AUTO_TUNNEL=1 docker compose up -d
```

Máy chủ lắng nghe tại cổng `8080` (HTTP + WebSocket). Dữ liệu được lưu trữ bền vững tại `./data/meikova_relay.db`.

---

## 8. Đường hầm Cloudflare Quick Tunnel (Universal Tunnel Bridge)

Tích hợp sẵn Cloudflare Quick Tunnel (`trycloudflare.com`) cho phép truy cập Web UI và kết nối máy trạm từ Internet không cần cấu hình port forwarding:

- **Khởi động kèm Tunnel:** `node server.js --tunnel` (hoặc `AUTO_TUNNEL=1` trong Docker)
- **Quản trị API:**
  - `GET /api/tunnel/status` - Trạng thái hoạt động và URL công khai (`https://*.trycloudflare.com`)
  - `POST /api/tunnel/start` - Bật đường hầm
  - `POST /api/tunnel/stop` - Tắt đường hầm
  - `POST /api/tunnel/restart` - Khởi động lại đường hầm

---

## 9. Kiểm thử và xác minh chất lượng (Testing)

Hệ thống tuân thủ quy chuẩn kiểm thử nghiêm ngặt bao gồm kiểm thử an ninh chuyên sâu và mô phỏng xâm nhập:

```bash
python -m unittest discover tests
```

Kết quả kiểm thử tự động:
- Test Suite: **286/286 tests PASS** (Exit Code 0).
- Chuyên biệt an ninh: Bộ kiểm thử xâm nhập tự động (`test_security_penetration.py`) xác thực toàn diện 6 lớp phòng thủ OWASP Top 10.
- CI/CD Matrix: Biên dịch và kiểm thử tự động trên Windows, Ubuntu và macOS.

---

## 10. Giấy phép bản quyền (License)

Dự án được phát hành theo giấy phép mã nguồn mở **MIT License**.
Bản quyền thuộc về **Meikova Relay Team © 2026**.

---

## 11. Hệ sinh thái Meikova

- [Meikova Harvest](https://github.com/Meikova/meikova-harvest) - Hệ sinh thái trích xuất và tải đa phương tiện đa nền tảng.
- [Meikova Loop](https://github.com/Meikova/meikova-loop) - DJ mashup và infinite soundscape engine chạy trên web, desktop và mobile.
- [Meikova Relay](https://github.com/Meikova/meikova-relay) - Điều khiển máy tính từ xa độ trễ thấp, outbound-only.
- [Meikova Auth](https://github.com/Meikova/meikova-auth) - Cổng xác thực tập trung, Universal SSO Ed25519 và quản lý danh tính đa nền tảng.
- [Meikova Balance](https://github.com/Meikova/meikova-balance) - Quản lý tài chính cá nhân, chia hóa đơn nhóm và trợ lý AI đa tầng.
- [Meikova Campus](https://github.com/Meikova/meikova-campus) - Nền tảng thương mại khóa học, phân quyền Google Drive tự động và LMS trực tuyến.
- [Meikova Exchange](https://github.com/Meikova/meikova-exchange) - Sàn giao dịch B2B cho dự án phần mềm, mã nguồn và tài sản số.
- [Meikova Traverse](https://github.com/Meikova/meikova-traverse) - Trình duyệt tệp tin cục bộ, SFTP, WebDAV và quản lý lưu trữ đa nền tảng.
- [Meikova Shield](https://github.com/Meikova/meikova-shield) - Hệ thống phòng thủ an ninh mạng và phát hiện web defacement bằng học máy lai ghép.
- [Meikova Vision](https://github.com/Meikova/meikova-vision) - Bộ công cụ xử lý ảnh RAW, ghép đa phơi sáng HDR và tone mapping chuyên nghiệp.
- [Meikova Flow](https://github.com/Meikova/meikova-flow) - Động cơ trích xuất, biến đổi, nạp dữ liệu (ETL) và tự động hóa luồng báo cáo.

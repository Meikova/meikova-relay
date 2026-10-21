# MEIKOVA RELAY

<div align="center">

![CI/CD Pipeline](https://github.com/m3iK18dp/meikova-relay/actions/workflows/build-release.yml/badge.svg)
![Latest Release](https://img.shields.io/github/v/release/m3iK18dp/meikova-relay?color=emerald)
![Platforms](https://img.shields.io/badge/Platforms-Windows%20%7C%20Linux%20%7C%20macOS%20%7C%20Web-blue)
![Architecture](https://img.shields.io/badge/Architecture-Outbound--Only%20WSS-purple)
![License](https://img.shields.io/badge/License-MIT-green)

**Hệ thống điều khiển máy tính từ xa thế hệ mới: Độ trễ siêu thấp, chuẩn màu 1:1 Pixel-Perfect, truyền tải âm thanh trực tiếp và vượt qua 100% Tường lửa Doanh nghiệp.**

[Dùng Thử Web Client](https://meikova-relay.onrender.com) • [Tải Gói Máy Trạm](https://github.com/m3iK18dp/meikova-relay/releases) • [Tài Liệu Triển Khai](docs/DEPLOYMENT_GUIDE.md)

</div>

---

## 1. TỔNG QUAN HỆ THỐNG (OVERVIEW)

**Meikova Relay** là giải pháp Remote Desktop toàn diện, độc lập, được nghiên cứu và thiết kế tối ưu cho:
- **Môi trường mạng công ty khắt khe**: Chặn toàn bộ giao thức UDP (khiến WebRTC/TeamViewer/AnyDesk mất kết nối hoặc lag giật), không có địa chỉ IPv6 công cộng và không có quyền can thiệp mở cổng (Port Forwarding) trên Router.
- **Bảo mật Outbound-Only**: Máy trạm (Host Agent) chỉ mở kết nối một chiều từ trong ra ngoài (Outbound) tới Relay Server qua cổng tiêu chuẩn **443 (HTTPS/WSS)**.
- **Client Zero-Install**: Người điều khiển chỉ cần mở trình duyệt web hiện đại (Chrome, Edge, Safari, Firefox trên PC, Mac, iPad, iPhone, Android) để điều khiển máy trạm mà không cần cài thêm bất kỳ tiện ích hay plugin nào.

```
+-----------------------------------------------------------------------------------------+
|                                    LUỒNG TRUYỀN DẪN DỮ LIỆU                             |
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
                    |         MEIKOVA RELAY SERVER (Node.js Engine)        |
                    |  - Bộ định tuyến WebSocket Room ID / PIN an toàn   |
                    |  - Google OAuth 2.0 (GIS) & JWT Session Manager    |
                    |  - Nhật ký kiểm toán bảo mật (Audit Log Trail)     |
                    +----------------------------------------------------+
```

---

## 2. TÍNH NĂNG NỔI BẬT (CORE CAPABILITIES)

### 🖥️ Sao Chép Màn Hình 1:1 Pixel-Perfect & Tự Động Đồng Bộ (Auto-Negotiation)
- **1:1 Native Replica**: Hiển thị chính xác từng điểm ảnh gốc không bị nén vỡ hay méo hình (`image-rendering: pixelated; crisp-edges`). Hỗ trợ kéo di chuyển khung hình (Pan) bằng chuột giữa hoặc `Alt + Chuột trái` khi máy trạm có độ phân giải lớn hơn thiết bị điều khiển.
- **Tự động đo đạc & đàm phán ma trận cấu hình cao nhất**:
  - Tần số quét >= 120Hz: Tự động kích hoạt **Ultra 120 FPS** cho trải nghiệm cuộn lướt siêu mượt.
  - Màn hình độ phân giải cao: Kích hoạt **Crisp 2K / 4K** với thuật toán xử lý độ nét cao.
  - Đầy đủ chế độ điều chỉnh linh hoạt: *1:1 Chuẩn Gốc*, *Cân bằng (30 FPS)*, *Siêu mượt (60 FPS)*, *Tiết kiệm băng thông*.
- **Hỗ trợ Đa Màn Hình (Multi-Monitor)**: Nhận diện tức thời danh sách màn hình gắn trên máy trạm, chuyển đổi mượt mà giữa Màn 1, Màn 2 hoặc xem gộp toàn cảnh.

### 🎨 Giao Diện Ambient Instrument UI Chuẩn Studio
- Thiết kế theo triết lý tối giản, tập trung vào tín hiệu (**Less Text, More Signal**) với bảng màu tối chuyên sâu OKLCH.
- **100% Inline Vector SVG**: Tuyệt đối không dùng icon font hay ảnh emoji ngoài; toàn bộ biểu tượng được vẽ bằng SVG inline chuẩn pixel, tối ưu kích thước và tốc độ render.
- **Thanh Công Cụ Floating Deck Đa Chế Độ**:
  1. *Dạng Deck nổi (Pill Deck)*: Nằm gọn gàng góc dưới màn hình.
  2. *Dạng Ghim mép trên (Top Pin)*: Tiết kiệm không gian quan sát.
  3. *Dạng Ẩn mép trên (Top Unpin)*: Tự động trượt gọn lên mép trên, chỉ hiện ra khi rê chuột lại gần để không che khuất các nút thanh tiêu đề của máy trạm.

### 🔊 Truyền Tải Âm Thanh Thời Gian Thực (Audio Streaming)
- Tự động bắt âm thanh hệ thống (WASAPI Loopback Capture) với định dạng chuẩn studio PCM 16-bit / 48kHz Stereo.
- Phát lại độ trễ cực thấp trên Web Client qua API HTML5 Web Audio AudioContext.

### 🛠️ Bộ Công Cụ Quản Trị Hệ Thống Từ Xa Toàn Diện
- **Quản lý Tệp Tin Hai Chiều (File Manager)**: Duyệt cây thư mục máy trạm, tải lên/tải xuống tệp tin, xem nội dung tệp văn bản từ xa, kiểm tra mã băm toàn vẹn SHA-256 chống lỗi truyền dữ liệu.
- **Terminal Dòng Lệnh Trực Tiếp (Remote CLI)**: Tích hợp PowerShell (Windows) và Bash (Linux/macOS), hỗ trợ đầy đủ tiếng Việt có dấu (UTF-8).
- **Giám Sát Tiến Trình (Process Manager)**: Theo dõi danh sách phần mềm đang chiếm dụng CPU / RAM cao nhất và cho phép đóng tiến trình từ xa.
- **Điều Khiển Nguồn Điện (Power Control)**: Khóa màn hình (Lock), Khởi động lại (Restart), Tắt máy (Shutdown) có hẹn giờ đếm ngược và hủy lệnh khẩn cấp.
- **Đồng Bộ Bộ Nhớ Tạm (Clipboard Sync)**: Tự động đồng bộ nội dung văn bản sao chép giữa máy trạm và trình duyệt.

### 🔐 Bảo Mật Đa Tầng Cấp Doanh Nghiệp
- Mã hóa toàn bộ luồng truyền dẫn bằng TLS 1.3 (HTTPS / WSS).
- Xác thực hai lớp: Tài khoản người dùng + Mã PIN phòng ngẫu nhiên 6 chữ số.
- Cơ chế chống tấn công Brute-Force: Tự động khóa phòng tạm thời khi nhập sai mã PIN liên tiếp.
- Xác thực đăng nhập hiện đại: Hỗ trợ Google Identity Services (GIS) 1-click và JWT Bearer Tokens.
- Nhật ký kiểm toán bảo mật (Audit Logging): Ghi lại toàn bộ lịch sử kết nối, địa chỉ IP và thiết bị truy cập.

---

## 3. DANH MỤC GÓI CÀI ĐẶT MÁY TRẠM (DOWNLOADS)

Toàn bộ gói cài đặt được biên dịch và đóng gói tự động qua GitHub Actions CI/CD:

| Hệ Điều Hành | Tệp Cài Đặt Phát Hành | Định Dạng | Mô Tả |
| :--- | :--- | :--- | :--- |
| **Windows** | [`MeikovaRelayHost.exe`](https://github.com/m3iK18dp/meikova-relay/releases/latest) | Portable Exe | Chạy trực tiếp ngay lập tức không cần quyền Admin |
| **Windows** | [`MeikovaRelayHost-windows-x64.zip`](https://github.com/m3iK18dp/meikova-relay/releases/latest) | Zip Archive | Bộ cài đặt đầy đủ kèm hướng dẫn chạy dịch vụ nền |
| **Linux** | [`meikova-relay-host_amd64.deb`](https://github.com/m3iK18dp/meikova-relay/releases/latest) | Debian / Ubuntu | Gói cài đặt 1-click có App Icon & Systemd service |
| **Linux** | [`meikova-relay-host-linux-x64.tar.gz`](https://github.com/m3iK18dp/meikova-relay/releases/latest) | Tarball | Dành cho các bản phân phối Linux khác (Fedora, Arch, RHEL) |
| **Linux** | [`meikova-relay-host`](https://github.com/m3iK18dp/meikova-relay/releases/latest) | Standalone ELF | Tệp thực thi nhị phân cho Server / CLI |
| **macOS** | [`meikova-relay-host-macos.tar.gz`](https://github.com/m3iK18dp/meikova-relay/releases/latest) | Tarball | Gói cài đặt macOS kèm LaunchAgent khởi động cùng máy |
| **macOS** | [`MeikovaRelayHost`](https://github.com/m3iK18dp/meikova-relay/releases/latest) | Mach-O Binary | Tệp thực thi chạy trực tiếp từ Terminal trên Mac |
| **Đối Soát** | [`SHA256SUMS.txt`](https://github.com/m3iK18dp/meikova-relay/releases/latest) | Text | Bảng mã băm SHA-256 đối chiếu tính toàn vẹn của tệp |

---

## 4. HƯỚNG DẪN BẮT ĐẦU NHANH (QUICK START)

### Bước 1: Khởi động Máy Trạm (Host Agent)
1. Tải bản phù hợp từ [GitHub Releases](https://github.com/m3iK18dp/meikova-relay/releases/latest).
2. Mở ứng dụng `MeikovaRelayHost`:
   - Giao diện sẽ hiển thị **ID Máy Trạm** (Room ID) và **Mã PIN Kết Nối**.
   - Tùy chọn: Chọn **Cài đặt cấp Người dùng (User)** để tự động chạy khi khởi động mà không cần quyền Admin, hoặc **Cài đặt Dịch vụ Hệ thống (Admin Service)** để chạy ngầm 24/7.

### Bước 2: Điều Khiển Từ Xa (Web Client)
1. Truy cập vào cổng Web Hub: **[https://meikova-relay.onrender.com](https://meikova-relay.onrender.com)**.
2. Đăng nhập bằng tài khoản hoặc nhấn **Đăng nhập bằng Google**.
3. Chọn thiết bị trong danh bạ máy trạm hoặc bấm **Kết nối nhanh**, nhập Room ID và PIN.
4. Màn hình máy tính hiển thị ngay lập tức với đầy đủ thao tác chuột và phím.

---

## 5. HƯỚNG DẪN TRIỂN KHAI MÁY CHỦ RIÊNG (SELF-HOSTED RELAY SERVER)

Xem hướng dẫn chi tiết tại: **[Tài liệu Triển Khai Hệ Thống (DEPLOYMENT_GUIDE.md)](docs/DEPLOYMENT_GUIDE.md)**

Tóm tắt lệnh chạy máy chủ với Node.js:
```bash
git clone https://github.com/m3iK18dp/meikova-relay.git
cd meikova-relay/relay-server
npm install
npm start
```
*Máy chủ mặc định lắng nghe tại cổng `8080` (HTTP + WebSocket).*

---

## 6. KIỂM THỬ VÀ XÁC MINH CHẤT LƯỢNG (TESTING & CI/CD)

Hệ thống tuân thủ quy chuẩn kỹ thuật nghiêm ngặt (Test-Driven Development):
```bash
# Chạy toàn bộ 67 kiểm thử tự động (Unit & Integration tests)
python -m unittest discover tests
```

### Kết quả kiểm định tự động:
- **Test Suite**: 67/67 tests đạt trạng thái **PASS (Exit Code 0)**.
- **CI/CD Pipeline**: Kiểm thử và đóng gói tự động trên toàn bộ 3 hệ điều hành:
  - `windows-latest`
  - `ubuntu-latest`
  - `macos-latest`

---

## 7. BẢN QUYỀN (LICENSE)

Dự án được phát hành theo giấy phép mã nguồn mở **MIT License**.

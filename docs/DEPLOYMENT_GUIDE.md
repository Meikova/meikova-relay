# HƯỚNG DẪN TRIỂN KHAI HỆ THỐNG MEIKOVA RELAY (DEPLOYMENT GUIDE)

Tài liệu hướng dẫn triển khai toàn diện hệ thống **Meikova Relay Desktop**, bao gồm:
1. Triển khai Relay Server (Cloud Render.com, VPS Linux, Docker, Systemd).
2. Cấu hình xác thực Google OAuth 2.0 (Google Identity Services - GIS).
3. Triển khai máy trạm (Host Agent) trên Windows, Linux và macOS.
4. Cấu hình bảo mật, tường lửa và tối ưu hóa độ trễ mạng.

---

## MỤC LỤC
1. [Kiến trúc kết nối & Yêu cầu hệ thống](#1-kiến-trúc-kết-nối--yêu-cầu-hệ-thống)
2. [Triển khai Relay Server](#2-triển-khai-relay-server)
   - [Cách 1: Triển khai nhanh trên Cloud Render.com (Miễn phí / Khuyên dùng)](#cách-1-triển-khai-nhanh-trên-cloud-rendercom-miễn-phí--khuyên-dùng)
   - [Cách 2: Triển khai trên VPS Linux (Ubuntu / Debian / CentOS)](#cách-2-triển-khai-trên-vps-linux-ubuntu--debian--centos)
   - [Cách 3: Triển khai qua Docker & Docker Compose](#cách-3-triển-khai-qua-docker--docker-compose)
3. [Cấu hình Google OAuth 2.0](#3-cấu-hình-google-oauth-20)
4. [Cài đặt & Vận hành Máy Trạm (Host Agent)](#4-cài-đặt--vận-hành-máy-trạm-host-agent)
   - [Trên Windows (Cài đặt User vs Admin Service)](#trên-windows)
   - [Trên Linux (Ubuntu, Debian, Fedora)](#trên-linux)
   - [Trên macOS (Apple Silicon M1/M2/M3 & Intel)](#trên-macos)
5. [Cấu hình Tường lửa & Khắc phục sự cố](#5-cấu-hình-tường-lửa--khắc-phục-sự-cố)

---

## 1. Kiến trúc kết nối & Yêu cầu hệ thống

```
+-----------------------------------------------------------------------------------+
|                                  KIẾN TRÚC TỔNG THỂ                               |
+-----------------------------------------------------------------------------------+

 [MÁY TRẠM - HOST AGENT]                               [TRÌNH DUYỆT - WEB CLIENT]
 (Windows / Linux / macOS)                             (Chrome, Edge, Safari, iPad)
        |                                                           |
        | Outbound WSS:443                                          | HTTPS / WSS:443
        v                                                           v
+-----------------------------------------------------------------------------------+
|                        RELAY SERVER (Node.js WebSocket Hub)                       |
|  - Định tuyến WebSocket theo Room ID & PIN       - Static Web Server              |
|  - Cung cấp API Auth, JWT, Google GIS, Audit Log - Quản lý File Transfer & Audio   |
+-----------------------------------------------------------------------------------+
```

### Ưu điểm vượt trội:
- **100% Outbound Connection**: Máy trạm chỉ chủ động kết nối ra ngoài cổng tiêu chuẩn `443` (HTTPS/WSS).
- **Vượt mọi Firewall/NAT công ty**: Không cần mở cổng (Port Forwarding), không cần IP tĩnh, không cần tạo mạng riêng ảo VPN phức tạp.
- **Client Zero-Install**: Người điều khiển chỉ cần mở trình duyệt web trên điện thoại, máy tính bảng hoặc laptop.

---

## 2. Triển khai Relay Server

### Cách 1: Triển khai nhanh trên Cloud Render.com (Miễn phí / Khuyên dùng)
Render.com cung cấp môi trường Web Service miễn phí có sẵn SSL (HTTPS và WSS) tự động.

1. Đăng ký/Đăng nhập tại [https://render.com](https://render.com).
2. Chọn **New +** -> **Web Service** -> Kết nối với repository GitHub của bạn (`meikova-relay`).
3. Điền cấu hình triển khai:
   - **Name**: `meikova-relay`
   - **Region**: Singapore (khuyên dùng để có độ trễ Ping thấp nhất về Việt Nam) hoặc Oregon.
   - **Root Directory**: `relay-server`
   - **Runtime**: `Node`
   - **Build Command**: `npm install`
   - **Start Command**: `npm start` (hoặc `node server.js`)
   - **Instance Type**: `Free`
4. Bấm **Create Web Service**.
5. Sau 1-2 phút, Render sẽ cấp tên miền an toàn:
   - Web URL: `https://meikova-relay.onrender.com`
   - WebSocket URL: `wss://meikova-relay.onrender.com`

---

### Cách 2: Triển khai trên VPS Linux (Ubuntu / Debian / CentOS)
Phù hợp cho doanh nghiệp cần tự lưu trữ (Self-hosted) hoặc tối ưu tốc độ mạng nội bộ.

#### Bước 1: Cài đặt Node.js
```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs git
```

#### Bước 2: Tải mã nguồn & Cài đặt thư viện
```bash
git clone https://github.com/m3iK18dp/meikova-relay.git /opt/meikova-relay
cd /opt/meikova-relay/relay-server
npm install
```

#### Bước 3: Cấu hình Systemd Service chạy nền vĩnh viễn
Tạo file dịch vụ `/etc/systemd/system/meikova-relay.service`:
```ini
[Unit]
Description=Meikova Relay Relay Server Hub
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/meikova-relay/relay-server
ExecStart=/usr/bin/node server.js
Restart=always
RestartSec=5
Environment=PORT=8080
Environment=NODE_ENV=production

[Install]
WantedBy=multi-user.target
```

Kích hoạt và chạy dịch vụ:
```bash
sudo systemctl daemon-reload
sudo systemctl enable meikova-relay
sudo systemctl start meikova-relay
sudo systemctl status meikova-relay
```

#### Bước 4: Cấu hình Nginx Reverse Proxy & SSL (Cổng 443 WSS)
Cài đặt Nginx và Certbot:
```bash
sudo apt-get install -y nginx certbot python3-certbot-nginx
```

Tạo file cấu hình `/etc/nginx/sites-available/meikova-relay`:
```nginx
server {
    server_name remote.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }
}
```

Bật site và cấp chứng chỉ SSL Let's Encrypt:
```bash
sudo ln -s /etc/nginx/sites-available/meikova-relay /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
sudo certbot --nginx -d remote.yourdomain.com
```

---

### Cách 3: Triển khai qua Docker & Docker Compose
Tạo file `docker-compose.yml` tại thư mục gốc:
```yaml
version: '3.8'

services:
  meikova-relay:
    build:
      context: ./relay-server
      dockerfile: Dockerfile
    container_name: meikova-relay
    restart: always
    ports:
      - "8080:8080"
    environment:
      - PORT=8080
      - NODE_ENV=production
    volumes:
      - ./relay-data:/app/data
```

Chạy container:
```bash
docker compose up -d
```

---

## 3. Cấu hình Google OAuth 2.0

Để sử dụng tính năng **Đăng nhập 1-click bằng tài khoản Google (GIS)**:

1. Truy cập [Google Cloud Console](https://console.cloud.google.com/apis/credentials).
2. Tạo mới hoặc chọn dự án hiện tại của bạn.
3. Vào **APIs & Services** -> **OAuth consent screen**:
   - Chọn loại người dùng: **External**.
   - Nhập tên ứng dụng: `Meikova Relay`.
   - Nhập email liên hệ hỗ trợ.
   - Tại mục **Test users**: Bấm **+ ADD USERS** và thêm các email Google được phép đăng nhập thử nghiệm.
4. Vào **Credentials** -> Bấm **+ CREATE CREDENTIALS** -> Chọn **OAuth client ID**:
   - Application type: **Web application**.
   - Name: `Meikova Relay Web Hub`.
   - **Authorized JavaScript origins** (Nguồn gốc JavaScript được phép):
     ```
     https://meikova-relay.onrender.com
     http://localhost:8080
     ```
   - **Authorized redirect URIs** (URI chuyển hướng được phép):
     ```
     https://meikova-relay.onrender.com/auth
     https://meikova-relay.onrender.com
     http://localhost:8080/auth
     ```
5. Bấm **CREATE**. Google sẽ cấp:
   - `Client ID`: Dạng `xxxxxxxxxxxx-xxxxxxxx.apps.googleusercontent.com`
   - `Client Secret`: Dạng `GOCSPX-xxxxxxxxxxxxxxxx`
6. Điền Client ID này vào file `web-client/js/app.js`:
   ```javascript
   const GOOGLE_CLIENT_ID = 'xxxxxxxxxxxx-xxxxxxxx.apps.googleusercontent.com';
   ```

---

## 4. Cài đặt & Vận hành Máy Trạm (Host Agent)

Tất cả các bản phát hành nhị phân đã được đóng gói sẵn trên [GitHub Releases](https://github.com/m3iK18dp/meikova-relay/releases).

### Trên Windows

#### Lựa chọn A: Chạy tức thì không cần cài đặt (Portable)
1. Tải file `MeikovaRelayHost.exe` từ GitHub Release.
2. Click đúp chuột để chạy.
3. Giao diện điều khiển mở ra, hiển thị mã PIN kết nối và trạng thái trực tuyến.

#### Lựa chọn B: Cài đặt User Tier (Không cần quyền Quản trị viên Admin)
- Dành cho máy công ty bị IT khóa quyền UAC / Administrator.
- Trên giao diện `MeikovaRelayHost`, bấm **Cài đặt cấp Người dùng (User)**:
  - Ứng dụng tự động sao chép vào `%LOCALAPPDATA%\MeikovaRelayHost\`.
  - Đăng ký khởi động tự động qua HKCU Run Registry và Task Scheduler của user.

#### Lựa chọn C: Cài đặt Admin Tier (Dịch vụ Chạy Ngầm 24/7)
- Dành cho máy chủ hoặc máy cá nhân có quyền Admin:
  - Bấm **Cài đặt Dịch vụ Hệ thống (Admin Service)**.
  - Đăng ký Windows Service `MeikovaRelayHost` với tài khoản `LocalSystem`, tự động khởi động ngay khi bật máy trước khi đăng nhập Windows (hỗ trợ màn hình khóa Lock Screen / Login Screen).

---

### Trên Linux (Ubuntu, Debian, Fedora, Arch)

#### Cách 1: Gói cài đặt Debian / Ubuntu (Khuyên dùng)
1. Tải file `meikova-relay-host_amd64.deb`.
2. Mở Terminal và cài đặt:
   ```bash
   sudo dpkg -i meikova-relay-host_amd64.deb
   sudo apt-get install -f # Tự động sửa dependency nếu thiếu
   ```
3. Khởi chạy:
   - Bấm vào icon **Meikova Relay Host** trong App Menu hoặc chạy:
     ```bash
     meikova-relay-host
     ```
   - Quản lý dịch vụ chạy ngầm systemd:
     ```bash
     sudo systemctl enable meikova-relay
     sudo systemctl start meikova-relay
     ```

#### Cách 2: Gói nén Portable `.tar.gz`
1. Tải `meikova-relay-host-linux-x64.tar.gz` và giải nén:
   ```bash
   tar -xzf meikova-relay-host-linux-x64.tar.gz
   cd meikova-relay-host-linux-x64
   chmod +x install.sh
   sudo ./install.sh
   ```

---

### Trên macOS (Apple Silicon M1/M2/M3 & Intel)

1. Tải file `meikova-relay-host-macos.tar.gz` từ GitHub Release.
2. Click đúp chuột vào file để Finder giải nén tự động.
3. Mở Terminal tại thư mục vừa bung và chạy:
   ```bash
   chmod +x install.sh
   ./install.sh
   ```
   Script tự động sao chép nhị phân vào `~/.meikova-relay/bin/` và đăng ký LaunchAgent `com.meikova.relay.plist` để chạy tự động cùng hệ thống.
4. **Cấp quyền bảo mật hệ thống macOS (Bắt buộc):**
   - Vào **System Settings** -> **Privacy & Security**:
     - **Screen Recording** (Ghi màn hình): Bật cho phép `MeikovaRelayHost`.
     - **Accessibility** (Trợ năng): Bật cho phép `MeikovaRelayHost` (để nhận lệnh chuột và phím).

---

## 5. Cấu hình Tường lửa & Khắc phục sự cố

| Hiện tượng | Nguyên nhân | Cách khắc phục |
| :--- | :--- | :--- |
| **Lỗi 400: origin_mismatch khi đăng nhập Google** | Domain triển khai chưa được khai báo trong Google Cloud Console | Vào Credentials của Google Cloud, thêm domain `https://meikova-relay.onrender.com` vào mục **Authorized JavaScript origins** và **Authorized redirect URIs**. |
| **Web Client báo "Mất kết nối tới Relay Server"** | Server Render miễn phí đang ở trạng thái ngủ đông (Spin-down) | Chờ khoảng 30 - 45 giây để instance khởi động lại hoặc nâng cấp lên gói Starter có tính năng Always-On. |
| **Không click được chuột trên macOS** | Thiếu quyền Trợ năng (Accessibility) của macOS | Vào `System Settings` -> `Privacy & Security` -> `Accessibility`, bật công tắc cho phép ứng dụng `MeikovaRelayHost`. |
| **Màn hình máy trạm bị đen khi truyền** | Máy trạm tắt màn hình hoặc bị vô hiệu hóa driver ảo | Đảm bảo tính năng **Ngăn máy trạm ngủ (Keep Awake)** đang bật trên Host Agent. |

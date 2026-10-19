# TITAN REMOTE DESKTOP (RD)

Hệ thống Remote Desktop độc lập, tự viết hoàn toàn từ đầu, tối ưu hóa đặc biệt cho môi trường **Firewall công ty chặn toàn bộ UDP**, không có IPv6 và không thể mở cổng Router.

---

## 1. Kiến trúc hệ thống (Architecture)

```
[Máy Công Ty (Host)]                 [Internet]                 [Máy Ở Nhà (Client)]
+--------------------+         +--------------------+         +--------------------+
|  ScreenCapture     |         |                    |         |  HTML5 Canvas      |
|  (Win32 GDI +      | --WSS-> | WebSocket Relay    | --WSS-> |  (OLED Dark UI)    |
|   WindowStation)   | (Frames)| Server (Port 443)  | (Frames)|  Mouse & Keyboard  |
|                    |         |                    |         |  Listener          |
|  InputInjector     | <-WSS-- | Room / PIN Router  | <-WSS-- |  Virtual Hotkeys   |
|  (Win32 SendInput) | (Inputs)|                    | (Inputs)|  (Win, TaskMgr,..) |
+--------------------+         +--------------------+         +--------------------+
```

- **Host Agent (Python)**: Kết nối **Outbound** (chiều từ trong mạng công ty đi ra) qua cổng 443 (HTTPS/WSS) -> Vượt qua 100% Firewall, NAT công ty mà không cần mở cổng hay cài VPN ảo.
- **Relay Server (Node.js)**: Định tuyến luồng ảnh và lệnh chuột/phím giữa Host và Client theo Room ID và mã PIN bảo mật. Tích hợp sẵn Web Server phục vụ giao diện Web Client.
- **Web Client (HTML5 / JS / Canvas)**: Mở trực tiếp bằng trình duyệt trên bất kỳ thiết bị nào (Chrome, Edge, Safari, Firefox). Không cần cài đặt phần mềm.

---

## 2. Hướng dẫn chạy thử nghiệm tại chỗ (Local Test)

### Bước 1: Khởi động Relay Server & Web UI
Mở Terminal tại thư mục `relay-server`:
```powershell
cd D:\JOB\DEV\RD\relay-server
npm start
```
*Server sẽ lắng nghe tại `http://localhost:8080` (vừa làm Web Client vừa làm WebSocket Relay).*

### Bước 2: Khởi động Host Agent (Mô phỏng máy bị điều khiển)
Mở một Terminal khác:
```powershell
cd D:\JOB\DEV\RD\host-agent
python host_service.py --relay ws://127.0.0.1:8080 --room RD-8888 --pin 123456
```
*(Hoặc click đúp chuột vào file `run_agent.bat`)*

### Bước 3: Mở Web Client điều khiển
- Mở trình duyệt truy cập: `http://localhost:8080`
- Nhập thông tin:
  - **Relay URL**: `ws://localhost:8080`
  - **Room ID**: `RD-8888`
  - **PIN**: `123456`
- Bấm **Kết Nối Ngay**. Màn hình máy tính sẽ hiển thị ngay lập tức với đầy đủ thao tác chuột và phím.

---

## 3. Triển khai thực tế giữa Công Ty và Nhà

### Cách A: Deploy Relay Server lên Cloud miễn phí (Khuyên dùng)
1. Đẩy thư mục `relay-server/` lên GitHub cá nhân.
2. Vào [Render.com](https://render.com) (hoặc Railway / Fly.io), tạo **Web Service** mới từ repo đó:
   - Build Command: `npm install`
   - Start Command: `npm start`
3. Render sẽ cấp một đường link miễn phí chuẩn HTTPS/WSS:
   `https://my-rd-relay.onrender.com` (tương ứng `wss://my-rd-relay.onrender.com`).

### Cách B: Vận hành kết nối
- **Trên máy công ty**: Chạy lệnh:
  ```powershell
  python host_service.py --relay wss://my-rd-relay.onrender.com --room RD-MYPC --pin 654321
  ```
- **Trên máy nhà**: Mở trình duyệt vào link `https://my-rd-relay.onrender.com`, nhập Room `RD-MYPC` và PIN `654321` để điều khiển.

---

## 4. Danh mục tính năng & Phím tắt hỗ trợ

- **Chuột mượt mà**: Click chuột trái, click phải, click giữa, double click, kéo thả (drag & drop), cuộn con lăn mượt mà.
- **Bàn phím toàn diện**: Hỗ trợ toàn bộ phím gõ, phím mũi tên, phím chức năng (F1-F12), tổ hợp phím tắt Ctrl, Alt, Shift, Win.
- **Hộp phím ảo (Floating Pill Deck)**:
  - `Win Key`: Mở Start menu từ xa.
  - `Task Manager`: Kích hoạt nhanh `Ctrl + Shift + Esc`.
  - `Alt + Tab`: Chuyển đổi cửa sổ.
  - `Dán Văn Bản Từ Xa`: Gửi chuỗi ký tự unicode (tiếng Việt có dấu) sang máy Host an toàn.
- **Chế độ hiển thị**:
  - `Fit Screen`: Tự động co giãn theo kích thước cửa sổ trình duyệt.
  - `100% Scale`: Hiển thị đúng kích thước pixel gốc 1:1.
  - `Fullscreen`: Toàn màn hình như đang ngồi trực tiếp trước máy công ty.
- **HUD thông số trực tiếp**: Đo đạc độ trễ mạng (Ping RTT ms), tốc độ khung hình (FPS), và độ phân giải màn hình máy Host.

---

## 5. Chạy kiểm thử tự động (Automated Verification)

Chạy toàn bộ 13 bài test (Protocol, Input Mapping, và E2E Relay Lifecycle):
```powershell
python -m unittest discover -s D:\JOB\DEV\RD\tests -p "test_*.py"
```

Chạy bài kiểm thử hiệu năng Screen Capture & Windows SendInput:
```powershell
python D:\JOB\DEV\RD\tests\self_test_capture.py
```

# Hướng dẫn Kỹ thuật & Kiến trúc Đa nền tảng Máy Trạm (Workstation Host OS Guide)

Tài liệu này cung cấp chi tiết kỹ thuật về khả năng hỗ trợ hệ điều hành của **Titan Remote**: Phân định rõ ràng giữa **Máy Trạm (Host Agent - Thiết bị bị điều khiển)** và **Máy Điều Khiển (Client / Controller - Thiết bị truy cập)**.

---

## 1. Bảng ma trận hỗ trợ Đa nền tảng (OS Support Matrix)

| Hệ điều hành | Vai trò Máy Trạm (Host Agent - Bị điều khiển) | Vai trò Máy Điều Khiển (Client Viewer) | Cơ chế kỹ thuật cốt lõi |
|--------------|---------------------------------------------|----------------------------------------|-------------------------|
| **Windows 10/11/Server** | **HỖ TRỢ 100% NATIVE** | **HỖ TRỢ 100% (Web Client)** | DXGI / GDI Capture, Win32 SendInput, WASAPI Audio, UAC Elevation, Windows Service 24/7 |
| **Linux (Ubuntu, Debian, Fedora, Arch...)** | **HỖ TRỢ 100% (Desktop & Server)** | **HỖ TRỢ 100% (Web Client)** | X11/Wayland Grab, `pynput` / `pyautogui`, Bash/Zsh Terminal, Systemd Service 24/7 |
| **macOS (Intel & M1/M2/M3/M4)** | **HỖ TRỢ 100% (Cần cấp quyền OS)** | **HỖ TRỢ 100% (Safari/Chrome)** | CoreGraphics / PIL Grab, Quartz `CGEvent`, Launchd Daemon 24/7 |
| **iOS (iPhone) / iPadOS (iPad)** | **KHÔNG KHẢ THI (Giới hạn bảo mật Apple)** | **HỖ TRỢ 100% CẢM ỨNG (Safari PWA)** | Client: Touch Gestures, 2-finger scroll, Pinch zoom, Virtual OSK, 3 chế độ Deck |
| **Android (Điện thoại & Tablet)** | **KHẢ THI QUA ACCESSIBILITY** | **HỖ TRỢ 100% (Chrome / Edge Mobile)** | Client: Web Client mượt mà. Host: MediaProjection + AccessibilityService |

---

## 2. Phân tích Chuyên sâu Kiến trúc: Tại sao iOS / iPadOS không thể làm Máy Trạm bị điều khiển?

Nhiều người dùng đặt câu hỏi: *"Tại sao không thể cài Agent lên iPhone hoặc iPad để ngồi từ xa điều khiển bấm chạm màn hình iPhone?"*

Về mặt an ninh hệ điều hành của Apple (Apple Sandbox Security Architecture):
1. **Không có API Chạm ảo (No Synthetic Touch Injection):**
   - Trên Windows: Có `SendInput()`.
   - Trên Linux: Có `/dev/uinput` hoặc XTest extension.
   - Trên macOS: Có Quartz `CGEventPost()`.
   - Trên Android: Có `AccessibilityService.dispatchGesture()`.
   - **Trên iOS / iPadOS:** Apple **nghiêm cấm tuyệt đối** bất kỳ ứng dụng của bên thứ 3 nào inject cử chỉ chạm (synthetic touch) vào các ứng dụng khác hoặc màn hình chính (SpringBoard). Không có bất kỳ Public API nào tồn tại cho mục đích này.
2. **Cơ chế ghi hình màn hình ngặt nghèo (ReplayKit Limitations):**
   - iOS chỉ cho phép quay màn hình thông qua `ReplayKit Broadcast Upload Extension`.
   - Cơ chế này luôn bật một popup hệ thống bắt buộc người dùng thật phải bấm *"Start Broadcast"*.
   - Tiến trình bị giới hạn RAM tối đa 50MB (vượt quá 50MB hệ thống sẽ tự động Terminate ngay lập tức).
   - Tự động ngắt truyền phát ngay khi người dùng khóa màn hình.
3. **Thực tế ngành (Industry Reality):**
   - Ngay cả các giải pháp thương mại hàng đầu như **TeamViewer QuickSupport** hay **AnyDesk** trên iOS/iPadOS cũng **chỉ là chế độ Xem màn hình (View-Only Screen Sharing)** kèm con trỏ ảo hướng dẫn bằng tay, hoàn toàn KHÔNG THỂ bấm thay người dùng.
   - Việc can thiệp điều khiển cảm ứng từ xa trên iOS chỉ thực hiện được nếu:
     - Thiết bị đã Jailbreak (vượt rào sandbox bảo mật).
     - Thiết bị cắm cáp USB vào máy Mac chạy Xcode WebDriverAgent (chế độ Test Automation của lập trình viên).

---

## 3. Hướng dẫn triển khai Máy Trạm trên Linux

### 3.1. Chạy thủ công hoặc môi trường phát triển
```bash
cd host_agent
chmod +x run_agent_linux.sh
./run_agent_linux.sh
```

### 3.2. Cài đặt Dịch vụ Hệ thống 24/7 (Systemd Service)
Để máy trạm Linux tự khởi động ngầm ngay từ khi bật nguồn (kể cả chưa đăng nhập màn hình):
```bash
# 1. Copy thư mục mã nguồn vào /opt
sudo mkdir -p /opt/titan-remote
sudo cp -r host_agent /opt/titan-remote/

# 2. Cài đặt file systemd service
sudo cp host_agent/titan-remote.service /etc/systemd/system/

# 3. Kích hoạt và bật tự khởi động
sudo systemctl daemon-reload
sudo systemctl enable titan-remote.service
sudo systemctl start titan-remote.service

# Kiểm tra trạng thái
sudo systemctl status titan-remote.service
```

---

## 4. Hướng dẫn triển khai Máy Trạm trên macOS

### 4.1. Cấp quyền Hệ thống trên macOS
Do cơ chế bảo mật TCC (Transparency, Consent, and Control) của macOS, cần cấp 2 quyền:
1. Mở **System Settings -> Privacy & Security -> Screen Recording**: Bật quyền cho Terminal hoặc Python.
2. Mở **System Settings -> Privacy & Security -> Accessibility**: Bật quyền cho Terminal hoặc Python để gửi sự kiện chuột/phím.

### 4.2. Khởi chạy
```bash
cd host_agent
chmod +x run_agent_macos.sh
./run_agent_macos.sh
```

### 4.3. Cài đặt Chạy ngầm 24/7 qua Launchd
```bash
cp host_agent/com.titan.remote.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.titan.remote.plist
```

---

## 5. Trải nghiệm Máy Điều Khiển trên iPadOS, iOS và Mobile

Mặc dù iOS/iPadOS không thể làm máy bị điều khiển, nhưng **iPad và iPhone lại là các thiết bị điều khiển từ xa (Controller) xuất sắc nhất** khi kết hợp với Web Client của Titan Remote:
- Mở Safari trên iPad/iPhone, truy cập URL Web Client (hoặc chọn "Add to Home Screen" để chạy toàn màn hình không có thanh địa chỉ Safari).
- **Hệ thống điều khiển cảm ứng tối ưu:**
  - Chạm 1 ngón: Click chuột trái.
  - Chạm giữ 0.5s: Click chuột phải.
  - Vuốt 2 ngón: Cuộn trang (Scroll Wheel).
  - Kéo 2 ngón (Pinch-to-zoom): Phóng to / Thu nhỏ mượt mà từ 50% đến 400%.
  - Bàn phím ảo OSK đầy đủ phím chuyên dụng: Ctrl, Alt, Win, Tab, Esc, F1-F12.
- **3 Chế độ hiển thị Deck:**
  - Tự động điều chỉnh theo tai thỏ / Dynamic Island qua CSS `safe-area-inset-top`.
  - Chế độ Mép trên Tự động ẩn (`top-unpinned`) giải phóng 100% diện tích màn hình iPad để làm việc với máy tính từ xa.

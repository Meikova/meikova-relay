# Meikova Relay - Session Handoff (v1.0.74)

## Mục tiêu hoàn thành
1. **Khắc phục triệt để lỗi gõ tiếng Việt bị tự xóa chữ ("gõ xong tự xóa hết")**:
   - **Nguyên nhân**:
     * Khi người dùng gõ tiếng Việt có dấu (Unikey / EVKey / Windows IME / MacOS Telex):
       - Bộ gõ phía máy khách chặn phím, phát chuỗi `Backspace` để xóa ký tự thô cũ, rồi chèn ký tự Unicode tổng hợp (`â`, `đ`, `ô`, `ơ`, `ư`, etc.).
       - Ký tự tổng hợp do Unikey sinh ra có `e.code = ""` hoặc `"Unidentified"` hoặc `"Process"`.
       - Trong `app.js`, `JS_TO_VK[e.code]` trả về `0`, dẫn tới điều kiện `if (vk > 0)` bỏ qua hoàn toàn ký tự có dấu!
       - Kết quả: Máy trạm nhận `Backspace` xóa chữ cũ nhưng không nhận được ký tự thay thế mới, khiến chữ bị xóa trắng.
     * Khi cả 2 máy đều bật Unikey (Double-Hook Collision):
       - Máy khách gửi phím, Unikey máy khách sinh Backspace; máy trạm nhận được phím lại qua Unikey máy trạm sinh thêm Backspace lần 2, xóa gấp đôi và triệt tiêu chữ.
   - **Giải pháp**:
     * Trong `relay-server/public/js/app.js`:
       - Lắng nghe sự kiện `keydown`: Bắt mọi ký tự Unicode diacritic (`charCode > 127`) hoặc ký tự IME tổng hợp (`isSyntheticIME = (!e.code || e.code === 'Unidentified' || e.code === 'Process')`) khi `e.key.length === 1`.
       - Phát trực tiếp sang máy trạm dưới dạng gói tin `{ type: 'text_input', text: e.key }`.
       - Bổ sung `compositionend` trên toàn trang để chuyển giao văn bản tổng hợp của IME di động và Safari/WebKit.
       - Sửa `mobileVirtualInput` để không xóa `value = ''` khi đang trong phiên gõ tổ hợp (`isVirtualComposing`).
     * Phía Máy trạm (`host_agent/input_injector.py`):
       - Xử lý `text_input` thông qua `InputInjector.type_unicode(text)` sử dụng Windows API chuẩn `SendInput` với cờ `KEYEVENTF_UNICODE` (`wScan = ord(char)`).
       - Các sự kiện `KEYEVENTF_UNICODE` có `wVk = 0` (hoặc `VK_PACKET = 0xE7`), bộ gõ Unikey/EVKey trên máy trạm tự động bỏ qua không can thiệp, triệt tiêu 100% hiện tượng xung đột kép.

2. **Đột phá tốc độ luồng hình ảnh: Đưa trần FPS từ 15-20 FPS lên 30-60 FPS (Non-Blocking Leaky-Bucket Pipeline)**:
   - **Nguyên nhân nghẽn 15-20 FPS**:
     * Luồng `_send_frames_worker` trước đây bị chặn bởi `if self.frames_in_flight >= 4: await asyncio.wait_for(self.ack_event.wait(), timeout=0.20)`.
     * Với độ trễ WAN thực tế giữa Việt Nam và Cloud Relay (Mỹ/Châu Âu) từ 180ms - 220ms, máy trạm phát 4 khung hình rồi phải dừng chờ 180ms cho gói ACK từ Client bay về.
     * Trần FPS toán học: $\text{FPS}_{\text{max}} = 4 / 0.200\text{s} = 20\text{ FPS}$ bất kể máy trạm mạnh hay mạng nhanh đến đâu.
   - **Giải pháp chuẩn Open-Source (Moonlight / RustDesk / Sunshine)**:
     * Loại bỏ hoàn toàn lệnh chặn chờ ACK `wait_for(ack_event)` khỏi `_send_frames_worker`.
     * Áp dụng hàng đợi trượt dung lượng 1 (`frame_queue = asyncio.Queue(maxsize=1)`): Khung hình mới nhất chụp được luôn đè lên khung hình cũ. Khung hình trễ tự động hủy trên RAM, triệt tiêu tích lũy độ trễ.
     * Kiểm soát tắc nghẽn thông qua bộ đệm tầng Socket `transport.get_write_buffer_size() > 1MB`, không khóa luồng phát hình.
     * Điều chỉnh ngưỡng DCC RTT từ 140ms lên 240ms để không suy giảm nhầm chất lượng trước độ trễ WAN địa lý bình thường (180-220ms).

3. **Khắc phục lỗi hiển thị "1:1 PIXEL-PERFECT (1600x900)" và chức năng Co giãn màn hình (Fit to Viewport)**:
   - **Nguyên nhân**:
     * `negotiate_optimal_display_profile` trả về `suggested_scale = "1to1"` cho `speed_60` và `balanced` khi màn hình điều khiển có độ phân giải bằng hoặc lớn hơn máy trạm.
     * Client UI nhận `suggested_scale = "1to1"` nên tự chuyển sang chế độ 1:1 và bật huy hiệu `1:1 PIXEL-PERFECT`.
     * Khi người dùng chọn preset "30 FPS Cân bằng" (được thiết kế nén 1600x900 để tối ưu băng thông), Client UI vẫn giữ nguyên huy hiệu và báo "1:1 PIXEL-PERFECT (1600x900)".
     * Trong CSS, `max-width: 100%; width: auto;` chỉ co nhỏ khi khung hình tràn ra ngoài, không thể phóng to (upscale) để lấp đầy màn hình trình duyệt khi khung hình nhỏ hơn cửa sổ.
   - **Giải pháp**:
     * `suggested_scale` trên Host chỉ trả về `"1to1"` khi cấu hình thực sự là `native_1to1`. Tất cả cấu hình nén/hạ độ phân giải (`speed_60`, `balanced`, `crisp_hd`, `eco`) luôn trả về `"fit"`.
     * Huy hiệu `pixelIndicatorBadge` chỉ hiển thị khi đồng thời: `!isFitMode` VÀ `qualitySelector.value === 'native_1to1'`. Ẩn hoàn toàn trong tất cả các chế độ còn lại.
     * Bổ sung hàm định cỡ động `fitCanvasToViewport()`: Tự động tính toán tỷ lệ `scaleFactor = Math.min(containerW / hostW, containerH / hostH)` và gán kích thước hiển thị chính xác theo pixel cho `#remoteCanvas` và `#laserCanvas`, bảo đảm hình ảnh luôn lấp đầy tối đa khung trình duyệt mà không bị méo tỷ lệ và không để lộ viền đen thừa thãi.
     * Thêm mã định danh yêu cầu `req_id` cho `set_quality_preset` để loại bỏ xung đột phản hồi bất đồng bộ khi chuyển đổi nhanh giữa các cấu hình A -> B -> C.


4. **Tích hợp Cloudflare Quick Tunnel (Multiplatform One-Click WAN) & Phân giải nguồn động (Dynamic Origin)**:
   - **Mục tiêu**: Kích hoạt Cloudflare Quick Tunnel trực tiếp trên Web UI không cần mở port modem hay cấu hình DNS; phân giải động origin cho file .bat, QR code và installer.
   - **Thực thi**:
     * Backend (`relay-server/tunnel_manager.js`): Quản lý vòng đời tiến trình `cloudflared`, tự động phát hiện binary đa nền tảng (Windows/Linux/macOS), cung cấp REST API (`/api/tunnel/status`, `/api/tunnel/start`, `/api/tunnel/stop`, `/api/tunnel/toggle`).
     * Tích hợp `active_url`: Tự động ghi đè URL tunnel công khai vào `/api/host-info` khi tunnel kích hoạt.
     * Tối giản giao diện & Căn trái (Less Text, More Signal): Modal Cloudflare Tunnel căn trái, gọn gàng (460px), loại bỏ chữ rườm rà. Nút bấm tinh gọn 'Bật' / 'Tắt', nhãn 'PUBLIC URL', QR code di động.
     * Xóa khoảng trống thừa trong `i18n.js`: Rút gọn từ 2893 dòng xuống 1667 dòng, bổ sung từ điển i18n đầy đủ cho cả `vi` và `en`.
     * Chuẩn responsive: Co giãn mượt mà trên di động và tablet (`max-width: 1320px`, `max-width: 767px`, `min-width: 0` trên input, touch target >= 44x44px).

## Trạng thái kiểm chứng (Verification)
- **Kiểm thử tự động toàn diện**: 175 bài kiểm thử unit tests vượt qua 100% (**Exit Code 0**, 1 skipped).
- **Kiểm thử chuyên biệt mới**:
  * `tests/test_tunnel_manager.py`: Passed (4/4).
  * `tests/test_vietnamese_input.py`: Passed (3/3).
  * `tests/test_streaming_pipeline.py`: Passed (4/4).
  * `tests/test_screen_sync.py`: Passed (9/9).
- **GitHub Actions CI/CD**: Hoàn thành vượt qua 100% cả 3 nền tảng (Windows, Linux, macOS).
- **Bản dựng Native Windows**:
  * Đóng gói thành công `MeikovaRelayHost.exe` (v1.0.74, 31.8 MB).
  * Đã đồng bộ sang `relay-server/MeikovaRelayHost.exe` và `dist/MeikovaRelayHost-windows-x64.zip`.

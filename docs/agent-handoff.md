# Meikova Relay - Session Handoff (v1.0.73)

## Mục tiêu hoàn thành
1. **Khắc phục lỗi co giãn màn hình (Fit-to-Screen) không hoạt động trên Web Desktop**:
   - **Hiện tượng**:
     * Khi người dùng nhấp nút chuyển chế độ co giãn màn hình (`btnScaleToggle`), Canvas màn hình từ xa không co giãn vừa vặn với kích thước trình duyệt máy tính, vẫn giữ nguyên kích thước 1920x1080 gây tràn khung và không phản hồi.
   - **Nguyên nhân gốc rễ**:
     * `.viewport-box` trên giao diện desktop thiếu ràng buộc kích thước (`min-width: 0; min-height: 0; max-width: 100%; max-height: 100%`).
     * Trong CSS Flexbox, phần tử thay thế `<canvas>` có kích thước nội tại (1920x1080) khiến flex container không thể co lại nhỏ hơn kích thước nội tại nếu thiếu `min-width: 0; min-height: 0;`.
   - **Giải pháp**:
     * Áp dụng quy chuẩn CSS rõ ràng giữa 2 chế độ:
       - `.remote-stage.fit-mode .viewport-box`: `width: 100%; height: 100%; max-width: 100%; max-height: 100%; min-width: 0; min-height: 0; display: flex; align-items: center; justify-content: center; overflow: hidden;`.
       - `.remote-stage.fit-mode #remoteCanvas`: `max-width: 100%; max-height: 100%; width: auto; height: auto; object-fit: contain; flex-shrink: 1;`.
       - `.remote-stage.fit-mode #laserCanvas`: Định vị tuyệt đối căn giữa `top: 50%; left: 50%; transform: translate(-50%, -50%); max-width: 100%; max-height: 100%; object-fit: contain;` khớp chính xác từng điểm ảnh với canvas điều khiển.
       - `.remote-stage:not(.fit-mode)`: Trả về chế độ 1:1 Pixel-Perfect cho phép cuộn/kéo tự do (`panX`, `panY`).

2. **Khắc phục độ trễ và kẹt khi chuyển đổi chế độ chất lượng (A -> B -> C)**:
   - **Hiện tượng**:
     * Người dùng chuyển từ preset chất lượng A sang B rồi C, hệ thống phản hồi rất chậm, thường kẹt lại ở A, sau đó chậm rãi sang B và không cập nhật C.
   - **Nguyên nhân gốc rễ**:
     1. Host nhận `set_quality_preset` nhưng không xóa hàng đợi khung hình cũ `self.frame_queue`, khiến client phải nhận hết các khung hình tồn đọng của preset cũ.
     2. Bộ lọc khung hình tĩnh (`screen_capture.py`) giữ `self._last_frame_hash` khiến khung hình mới bị bỏ qua (trả về `None`) nếu màn hình tĩnh.
     3. Sự kiện nền `display_profile_matched` tự động ghi đè lại giá trị `qualitySelector.value` về chế độ mặc định của hệ thống (`speed_60`).
     4. `apply_quality_preset` trước đây ánh xạ ghi đè biến `preset = "native_1to1"` khi người dùng chọn `crisp_2k_4k`.
   - **Giải pháp**:
     * Khi Host nhận `set_quality_preset`:
       1. Ngay lập tức xả sạch toàn bộ backlog khung hình trong `self.frame_queue`.
       2. Đặt `self.capture._last_frame_hash = None` để vô hiệu hóa cache khung hình cũ.
       3. Chụp cưỡng bức ngay 1 khung hình tươi mới với cấu hình mới (`force=True`).
       4. Gửi gói tin ACK xác nhận `{"type": "quality_preset_applied", "preset": applied, ...}` về Client.
     * Trên Client UI:
       - Đánh dấu cờ `hasUserManuallySelectedQuality = true` khi người dùng tự chọn chế độ; ngăn không cho `display_profile_matched` tự ý ghi đè lựa chọn của người dùng.
       - Cập nhật UI ngay lập tức khi nhận gói tin `quality_preset_applied`.
       - Tách bạch cấu hình `crisp_2k_4k` (chất lượng 95%, max_width 2560px) độc lập, không bị ghi đè nhầm sang `native_1to1`.

3. **Khắc phục hiện tượng trập chờn và treo kết nối**:
   - **Hiện tượng**:
     * Kết nối WebSocket trập chờn, luồng màn hình thỉnh thoảng bị khựng hoặc đóng băng hoàn toàn.
   - **Nguyên nhân gốc rễ**:
     1. Cơ chế Zero-lag backpressure tại `relay-server/server.js` kiểm tra `client.ws.bufferedAmount > 64 * 1024` (64KB). Trong khi một khung hình JPEG HD/4K có dung lượng từ 120KB - 300KB, khiến máy chủ hủy bỏ (drop) gần như 100% khung hình tiếp theo khi có độ trễ mạng thông thường.
     2. Giới hạn `frames_in_flight >= 2` và timeout chờ ACK 40ms trên Host quá nhỏ so với thời gian truyền gói tin mạng (RTT 100ms - 220ms), gây nghẽn luồng gửi khung hình.
     3. Tính toán RTT trong cơ chế chống nghẽn (DCC) lấy đồng hồ Host trừ đi đồng hồ Client (`(time.time() * 1000) - client_ts`), gây sai lệch thời gian hệ thống và liên tục giảm tụt chất lượng hình ảnh về mức thấp nhất (38).
     4. Khi bị đóng kết nối bởi `superseded`, Host cũ lập tức thử kết nối lại trong vòng lặp vô hạn, gây ra xung đột đá phiên qua lại.
   - **Giải pháp**:
     * Nâng ngưỡng backpressure tại `server.js` từ 64KB lên 1.5MB (`1536 * 1024`), cho phép đệm khung hình an toàn mà không làm gián đoạn luồng stream.
     * Nâng ngưỡng write buffer trên Host lên 1MB, tăng số khung hình in-flight tối đa lên 4, và tăng timeout chờ ACK lên 200ms.
     * Tính toán RTT thuần túy dựa trên mốc thời gian của Host thông qua cơ chế Ping/Pong đồng bộ.
     * Khi nhận tín hiệu `superseded`, Host cũ dừng hẳn (`self.running = False`), chấm dứt triệt để vòng lặp kết nối tranh chấp.

## Trạng thái kiểm chứng (Verification)
- **Kiểm thử đơn vị (Unit Tests)**:
  * Chạy `python -m unittest discover -s tests -p "test_*.py"`: **100% tests PASS (Exit Code 0)**.
  * Bổ sung test case `test_instant_quality_preset_switch_and_ack`: **PASS**.
- **Đóng gói Native Binary**:
  * Đã build thành công `MeikovaRelayHost.exe` (31.8 MB) phiên bản `v1.0.73`.
  * Đồng bộ vào `relay-server/MeikovaRelayHost.exe` và `agent-package.zip`.

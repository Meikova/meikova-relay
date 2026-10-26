# Meikova Relay - Session Handoff (v1.0.71)

## Mục tiêu hoàn thành
1. **Khắc phục triệt để lỗi kết nối chập chờn, máy trạm Offline & Authentication rejected (v1.0.71)**:
   - **Hiện tượng**:
     * Log máy trạm (Host Agent): Liên tục lặp lại `[09:05:24] Đã đăng ký phòng RD-1815 trên Relay Server`, `[09:05:25] Đã đăng ký phòng RD-1815 trên Relay Server`, sau đó `[09:05:26] Mất kết nối với Relay Server... (Chi tiết: Authentication rejected)`.
     * Người xem (Viewer/Client): Mắc kẹt tại `XÁC THỰC...`, thông báo `Lỗi: Máy trạm đang Offline hoặc không tồn tại`.
   - **Phân tích nguyên nhân gốc rễ**:
     1. **Xung đột 2 tiến trình chạy song song (Process Collision & No OS Mutex)**:
        * Khi khởi động Windows hoặc nhấp đúp nhanh, 2 tiến trình `MeikovaRelayHost.exe --gui` (PID 37180 và PID 35420) được bật cách nhau chỉ 2 giây.
        * Cơ chế IPC cũ dùng TCP loopback port `48123` tốn 2-3 giây để khởi tạo WebView2 rồi mới lắng nghe socket. Cả 2 tiến trình đều vượt qua vòng kiểm tra trước khi kịp bind cổng.
        * Khi tiến trình thứ 2 bind lỗi (Address already in use), code cũ bọc `except Exception: pass` nuốt lỗi ngầm làm **cả 2 tiến trình cùng chạy song song**.
        * Cả 2 tiến trình đều giữ chung cấu hình `room_id = RD-1815` và liên tục gửi `init_host` lên máy chủ Cloud Relay (`meikova-relay.onrender.com`), tranh giành phòng và đá kết nối của nhau.
     2. **Lỗi Race Condition & Ghost Session Invalidation trên Relay Server (`server.js`)**:
        * Trong `relay-server/server.js`, khi nhận `init_host` trùng `roomId`, máy chủ gán đè `room.hostWs = ws2` mà không ngắt socket cũ `ws1`.
        * Khi socket cũ `ws1` bị timeout hoặc ngắt kết nối, sự kiện `ws1.on('close')` kích hoạt hàm `closeRoomClients(currentRoomId)`.
        * Hàm `closeRoomClients` **không kiểm tra danh tính socket** (`room.hostWs === ws`), dẫn đến việc sự kiện đóng của `ws1` **xóa sạch `room.hostWs = null`** và đá văng toàn bộ Client khỏi phòng, mặc dù `ws2` đang hoạt động hoàn hảo.
        * Khách hàng kết nối vào phòng nhận ngay mã lỗi `RELAY_ROOM_OFFLINE` ("Máy trạm đang Offline hoặc không tồn tại").
     3. **Rò rỉ socket và thread khi tắt/khởi động lại dịch vụ (`host_service.py` & `gui_agent.py`)**:
        * Trong `host_service.py`, hàm `stop()` không thực sự đóng `self.ws` do logic `_graceful_close()` bị thụt nhầm vào `__del__()` (nơi không bao giờ được GC gọi kịp do circular references).
        * Trong `gui_agent.py`, `start_service()` thiếu re-entrancy lock, dẫn đến việc kích hoạt nhiều `_service_thread` cùng lúc.

   - **Giải pháp kỹ thuật triệt để**:
     1. **Khóa đơn phiên toàn hệ điều hành bằng Win32 Named Mutex (`SingleInstanceLock`)**:
        * Xây dựng `SingleInstanceLock` sử dụng `kernel32.CreateMutexW` kèm kiểm tra lỗi `ERROR_ALREADY_EXISTS (183)`.
        * Nếu phát hiện phiên bản khác đang chạy, gửi lệnh `SHOW` qua loopback IPC (thử lại 15 lần trong 3s phòng trường hợp tiến trình chính đang khởi tạo) và thoát ngay lập tức (`sys.exit(0)`).
        * Xử lý đóng handle an toàn ngay khi phát hiện `ERROR_ALREADY_EXISTS` để không rò rỉ mutex handle trong Windows kernel. Hỗ trợ fallback `msvcrt.locking` và POSIX `fcntl.flock`.
     2. **Đồng bộ vòng đời Host Socket trên Relay Server (`relay-server/server.js`)**:
        * Khi nhận `init_host` mới cho phòng đang mở, máy chủ gửi gói tin `{ type: 'superseded', message: '...' }` và đóng socket cũ một cách minh bạch.
        * Cập nhật `closeRoomClients(roomId, reason, expectedHostWs)`: Chỉ gán `room.hostWs = null` và đá Client nếu socket đang đóng thực sự là socket đại diện hợp lệ (`room.hostWs === expectedHostWs`). Nếu là socket cũ bị thay thế, bỏ qua không phá vỡ phòng của host mới.
     3. **Bảo toàn vòng đời HostService & Bắt lỗi minh bạch**:
        * Chuyển logic đóng socket `_graceful_close()` vào trực tiếp `HostService.stop()`.
        * Thêm `_service_lock = threading.Lock()` trong `HostApi` chặn tuyệt đối race condition đa luồng khi bật/tắt dịch vụ.
        * Bóc tách chi tiết thông điệp từ `ack` (`ack.get("message") or ack.get("error") or ack.get("detail") or str(ack_raw)`) để ghi log tường minh, không bao giờ rơi vào fallback mù mờ.
        * Bổ sung xử lý sự kiện `type == 'superseded'` trong `_receive_events_loop()` để host cũ dừng truyền dữ liệu ngay lập tức.
     4. **Nâng cấp phiên bản toàn hệ thống**:
        * Bump phiên bản đồng bộ `1.0.71` across `package.json`, `sw.js`, `index.html`.
        * Đóng gói lại `agent-package.zip`.

2. **Duy trì toàn vẹn các tối ưu từ phiên v1.0.70**:
   - Zero-gap navigation bar 48px cho iPhone PWA.
   - Zero GDI/RAM leak (RAM Commit < 100MB, GDI < 110).

## Trạng thái kiểm chứng (Verification)
- **Unit Test Mới (`tests/test_flapping_connection.py`)**:
  * `test_superseded_host_does_not_offline_room`: **PASS (Exit Code 0)**. Host 1 kết nối, Host 2 kết nối, Host 1 nhận `superseded` và đóng. Client kết nối thành công, không gặp lỗi `RELAY_ROOM_OFFLINE`.
  * `test_single_instance_lock`: **PASS (Exit Code 0)**. Khóa thứ hai bị từ chối; sau khi khóa thứ nhất giải phóng, khóa thứ hai chiếm giữ thành công.
- **Toàn bộ Test Suite Cốt lõi**:
  * `tests.test_flapping_connection`: 2/2 PASS.
  * `tests.test_multi_client_sessions`: 2/2 PASS.
  * `tests.test_tcp_tunnel`: 4/4 PASS.
  * `tests.test_leak_regression`: 4/4 PASS.
  * Tổng cộng: **12/12 core tests PASS (100% Exit Code 0)**.

/**
 * MEIKOVA RELAY — INTERNATIONALIZATION (i18n) ENGINE
 * Default / Primary: Vietnamese ('vi')
 * Secondary: English ('en')
 * Architecture: Zero-dependency, extensible dictionary with dynamic interpolation,
 * DOM translation binding, URL query sync, and localStorage persistence.
 */

(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.MeikovaI18n = factory();
    root.t = root.MeikovaI18n.t;
  }
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const DEFAULT_LANG = 'vi';
  const STORAGE_KEY = 'meikova_relay_lang';

  // Master Translation Dictionary
  // ponytail: Minimal flat-key dictionary; registerLang() allows arbitrary expansion (ja, zh, ko)
  const MESSAGES = {
    vi: {
      // Top Navigation
      'nav.workstations': 'Máy trạm',
      'nav.screen': 'Màn hình',
      'nav.files': 'Tệp & Thư mục',
      'nav.terminal': 'Terminal',
      'nav.tasks': 'Tiến trình',
      'nav.audit': 'Nhật ký (Audit)',
      'nav.aria_label': 'Phân hệ điều khiển',

      // Topbar
      'topbar.brand': 'MEIKOVA RELAY',
      'topbar.logout': 'Thoát',
      'topbar.logout_title': 'Đăng xuất khỏi phiên làm việc',
      'topbar.quick_connect': 'Kết nối nhanh',
      'topbar.quick_connect_title': 'Kết nối trực tiếp bằng Room ID',
      'topbar.download_apps': 'Tải App',
      'topbar.download_apps_title': 'Tải ứng dụng Meikova Relay (Host & Viewer)',
      'dl_modal.title': 'Cài đặt & Tải ứng dụng',
      'dl_modal.subtitle': 'HỆ SINH THÁI ĐA NỀN TẢNG // HOST AGENT & VIEWER',
      'dl_modal.close_title': 'Đóng',
      'dl_modal.tab_host': 'Máy trạm (Host Agent)',
      'dl_modal.tab_client': 'Máy điều khiển (Viewer Client)',
      'dl_modal.host_role_hint': 'MÁY BỊ ĐIỀU KHIỂN: Cài đặt trên máy tính cần truy cập hoặc hỗ trợ từ xa.',
      'dl_modal.client_role_hint': 'MÁY ĐIỀU KHIỂN: Cài đặt trên máy của bạn để kết nối, xem và điều khiển các máy trạm khác.',

      // Telemetry Readouts
      'ro.disconnected': 'CHƯA KẾT NỐI',
      'ro.connecting': 'ĐANG KẾT NỐI...',
      'ro.connected': 'ĐÃ KẾT NỐI',
      'ro.reconnecting': 'TỰ ĐỘNG KẾT NỐI LẠI...',
      'ro.auth': 'ĐĂNG NHẬP',
      'ro.dashboard': 'DANH SÁCH MÁY TRẠM',
      'ro.authenticating': 'XÁC THỰC...',
      'ro.rebooting': 'MÁY TRẠM ĐANG KHỞI ĐỘNG LẠI...',

      // View 1: Auth
      'auth.title': 'Đăng nhập quản trị',
      'auth.subtitle': 'Nền tảng điều khiển máy trạm toàn diện qua Outbound Relay',
      'auth.tab_login': 'Đăng nhập',
      'auth.tab_register': 'Đăng ký',
      'auth.username_label': 'Tên tài khoản',
      'auth.username_placeholder': 'Nhập username',
      'auth.password_label': 'Mật khẩu',
      'auth.password_placeholder': '••••••••',
      'auth.or': 'hoặc',
      'auth.or_local': 'hoặc tài khoản nội bộ',
      'auth.google_signin': 'Tiếp tục với Google',
      'auth.btn_login': 'Vào bảng điều khiển',
      'auth.btn_register': 'Đăng ký tài khoản',
      'auth.err_missing': 'Vui lòng điền đầy đủ tên đăng nhập và mật khẩu',
      'auth.err_generic': 'Đã có lỗi xảy ra khi xác thực',

      // View 2: Dashboard
      'dashboard.title': 'Danh sách máy trạm',
      'dashboard.subtitle': 'Các thiết bị đã liên kết với tài khoản của bạn',
      'dashboard.btn_add_device': 'Thêm máy trạm',
      'dashboard.btn_add_device_title': 'Thêm máy trạm Windows, macOS hoặc Linux',
      'dashboard.btn_download_exe': 'Tải Desktop App (.exe)',
      'dashboard.btn_download_exe_title': 'Tải phần mềm Desktop độc lập (.exe) - Không cần cài Python',
      'dashboard.btn_download_host': 'Tải bộ cài (.bat)',
      'dashboard.btn_download_host_title': 'Tải file cài đặt máy trạm tự động (.bat)',
      'dashboard.btn_mac_title': 'Cài đặt máy trạm macOS',
      'dashboard.btn_linux_title': 'Cài đặt máy trạm Linux',
      'dashboard.btn_quick_connect': 'Kết nối Room ID',
      'dashboard.empty': 'Chưa có máy trạm nào được liên kết',
      'dashboard.empty_hint': 'Tải phần mềm hoặc chạy lệnh tự động để kết nối máy trạm Windows, macOS hoặc Linux.',
      'dashboard.loading': 'Đang tải danh sách máy trạm...',
      'dashboard.load_error': 'Không thể tải danh sách thiết bị.',
      'add_device.title': 'Thêm máy trạm mới',
      'add_device.subtitle': 'Chọn hệ điều hành để cài đặt máy trạm hoặc kết nối tự động',
      'dashboard.status_online': 'Trực tuyến',
      'dashboard.status_offline': 'Ngoại tuyến',
      'dashboard.btn_connect': 'Kết nối',
      'dashboard.btn_delete': 'Xóa',
      'dashboard.delete_confirm': 'Bạn có chắc chắn muốn hủy liên kết máy trạm này?',
      'dashboard.unlink_success': 'Đã hủy liên kết máy trạm thành công',

      // View 3: Remote Desktop & Floating Deck
      'deck.monitor_title': 'Chọn màn hình truyền phát',
      'deck.monitor_all': 'Tất cả màn hình',
      'deck.monitor_single': 'Màn {num}',
      'deck.quality_title': 'Cấu hình phân giải, FPS & chất lượng',
      'deck.quality_native_1to1': '1:1 Chuẩn gốc (Pixel-Perfect)',
      'deck.quality_auto_sync': 'Tự động tối ưu (Auto-Sync)',
      'deck.quality_ultra_120': '120 FPS Siêu mượt',
      'deck.quality_speed': '60 FPS Mượt mà',
      'deck.quality_crisp_2k_4k': '2K / 4K Cực nét (95%)',
      'deck.quality_hd': 'HD Nét (85%)',
      'deck.quality_balanced': '30 FPS Cân bằng',
      'deck.quality_grayscale': 'Tiết kiệm băng thông',
      'deck.sync_display_btn': 'SYNC',
      'deck.sync_display_title': 'Đồng bộ tối ưu cấu hình 2 màn hình (Trạm ↔ Điều khiển)',
      'deck.scale_title': 'Co giãn theo cửa sổ / 100% tỷ lệ gốc',
      'deck.grid_btn': 'LƯỚI',
      'deck.grid_toggle_title': 'Chuyển chế độ Lưới kéo thả đa màn hình',
      'deck.grid_side_by_side': 'Bố cục ngang [Màn 1 | Màn 2]',
      'deck.grid_invert': 'Đảo ngược vị trí [Màn 2 | Màn 1]',
      'deck.grid_stacked': 'Bố cục dọc [Màn 1 / Màn 2]',
      'deck.fullscreen_title': 'Toàn màn hình',
      'deck.laser_title': 'Bật/Tắt Laser Pointer',
      'deck.record_title': 'Ghi hình phiên làm việc',
      'deck.cam_title': 'Bật/Tắt Face Cam (Webcam PiP khi ghi hình)',
      'deck.screenshot_title': 'Chụp ảnh màn hình máy trạm',
      'deck.audio_title': 'Bật/Tắt truyền âm thanh máy trạm (Live Audio Stream)',
      'deck.mic_title': 'Bật/Tắt micro nói sang máy trạm (Live Voice Intercom)',
      'deck.osk_title': 'Mở bàn phím ảo',
      'deck.block_input_title': 'Khóa chuột & phím máy đích (Block Host Input)',
      'deck.power_title': 'Tác vụ nguồn',
      'deck.power_lock': 'Khóa màn hình',
      'deck.power_restart': 'Khởi động lại',
      'deck.power_restart_confirm': 'Bạn có chắc chắn muốn khởi động lại máy trạm từ xa? Phiên làm việc sẽ tạm ngắt quãng và tự động kết nối lại khi máy hoàn tất khởi động.',
      'deck.shelf_title': 'Truyền tệp & Clipboard',
      'deck.disconnect_title': 'Ngắt kết nối',
      'deck.face_cam_badge': 'FACE CAM',
      'deck.drop_title': 'Thả tệp để truyền sang máy trạm',
      'deck.drop_hint': 'Tệp sẽ được lưu trực tiếp vào thư mục tải về của máy trạm',
      'deck.display_mode_title': 'Chế độ hiển thị thanh điều khiển (Đáy / Mép trên Ghim / Mép trên Tự ẩn)',
      'deck.pin_quick_title': 'Ghim / Bỏ ghim thanh điều khiển mép trên',
      'deck.top_trigger_title': 'Rê chuột hoặc chạm vào đây để mở thanh điều khiển',
      'deck.mode_menu_title': 'VỊ TRÍ & HIỂN THỊ DECK',
      'deck.mode_bottom': 'Dạng đáy nổi (Mặc định)',
      'deck.mode_bottom_desc': 'Thanh pill lơ lửng ở đáy màn hình',
      'deck.mode_top_pinned': 'Mép trên (Ghim cố định)',
      'deck.mode_top_pinned_desc': 'Cố định ở đỉnh, không che Taskbar máy trạm',
      'deck.mode_top_unpinned': 'Mép trên (Tự động ẩn)',
      'deck.mode_top_unpinned_desc': 'Hover mép trên mới trượt ra, tránh đè giao diện',

      // View 4: Terminal
      'terminal.title': 'PS REMOTE // HOST SHELL',
      'terminal.badge_disconnected': 'CHƯA KẾT NỐI',
      'terminal.badge_connected': 'ĐÃ KẾT NỐI (POWERSHELL UTF-8)',
      'terminal.hint': 'Enter: Thực thi | ↑/↓: Lịch sử | Ctrl+L: Xóa',
      'terminal.btn_clear': 'Xóa màn hình',
      'terminal.screen_title': 'Nhấn vào màn hình để gõ lệnh trực tiếp',
      'terminal.welcome': 'Meikova Relay PowerShell Console sẵn sàng. Đang chạy trong môi trường UTF-8.',

      // View 5: Tasks & Diagnostics
      'tasks.title': 'Giám sát & Quản lý tiến trình',
      'tasks.subtitle': 'Thông số phần cứng và ứng dụng đang chạy trên máy trạm',
      'tasks.refresh_title': 'Làm mới',
      'tasks.ram_title': 'Bộ nhớ RAM',
      'tasks.disk_c_title': 'Ổ đĩa C:',
      'tasks.os_title': 'Hệ điều hành',
      'tasks.measuring': 'Đang đo...',
      'tasks.table_title': 'Danh sách tiến trình (Sắp xếp theo RAM)',
      'tasks.search_placeholder': 'Lọc tiến trình...',
      'tasks.th_pid': 'PID',
      'tasks.th_name': 'Tên tiến trình',
      'tasks.th_ram': 'RAM (MB)',
      'tasks.th_actions': 'Thao tác',
      'tasks.no_conn': 'Chưa kết nối máy trạm',
      'tasks.btn_kill': 'Dừng',
      'tasks.kill_confirm': 'Bạn có chắc chắn muốn dừng tiến trình {name} (PID: {pid})?',
      'tasks.search_no_results': 'Không tìm thấy tiến trình phù hợp',

      // View 6: Remote File Explorer
      'files.title': 'Trình quản lý tệp tin máy trạm',
      'files.subtitle': 'Truyền tải tệp tin và duyệt cây thư mục đa luồng qua WebSocket 443 (Bypass Firewall/NAT)',
      'files.path_placeholder': 'Nhập đường dẫn đầy đủ (vd: C:\\Windows)...',
      'files.btn_go': 'Đến',
      'files.btn_cancel': 'Hủy',
      'files.edit_path_title': 'Chỉnh sửa đường dẫn trực tiếp',
      'files.btn_up': 'Lên',
      'files.btn_up_title': 'Thư mục cha',
      'files.btn_refresh': 'Làm mới',
      'files.btn_refresh_title': 'Làm mới danh sách tệp',
      'files.btn_new_folder': 'Thư mục mới',
      'files.btn_new_folder_title': 'Tạo thư mục mới',
      'files.btn_upload': 'Tải tệp lên',
      'files.btn_upload_title': 'Tải tệp tin lên thư mục này',
      'files.search_placeholder': 'Lọc tệp trong thư mục...',
      'files.mode_list_title': 'Xem danh sách',
      'files.mode_grid_title': 'Xem dạng lưới',
      'files.transfer_label': 'Đang truyền tải...',
      'files.th_name': 'Tên tệp / Thư mục',
      'files.th_size': 'Kích thước',
      'files.th_modified': 'Ngày sửa đổi',
      'files.th_actions': 'Thao tác',
      'files.no_conn': 'Chưa kết nối máy trạm',
      'files.action_edit': 'Sửa',
      'files.action_edit_title': 'Mở và sửa trực tiếp trên máy trạm',
      'files.action_download': 'Tải',
      'files.action_download_title': 'Tải tệp về máy cục bộ',
      'files.action_delete': 'Xóa',
      'files.action_delete_title': 'Xóa tệp/thư mục này',
      'files.action_copy': 'Sao chép',
      'files.action_copy_title': 'Sao chép tệp/thư mục này',
      'files.action_cut': 'Cắt',
      'files.action_cut_title': 'Cắt / Di chuyển tệp/thư mục này',
      'files.action_rename': 'Đổi tên',
      'files.action_rename_title': 'Đổi tên tệp/thư mục',
      'files.rename_title': 'Đổi tên tệp / thư mục',
      'files.rename_prompt': 'Nhập tên mới cho tệp hoặc thư mục:',
      'files.new_folder_title': 'Tạo thư mục mới',
      'files.btn_paste': 'Dán',
      'files.btn_paste_title': 'Dán tệp/thư mục vào đây',
      'files.status_count': '{count} mục',
      'files.status_selected': '{count} đã chọn',
      'files.status_summary': '{count} mục ({dirs} thư mục, {files} tệp)',
      'files.total_size': 'Tổng kích thước: {size}',
      'files.empty_folder': 'Thư mục trống',
      'files.not_found': 'Không tìm thấy tệp phù hợp',
      'files.new_folder_prompt': 'Nhập tên thư mục mới:',
      'files.delete_confirm': 'Bạn có chắc chắn muốn xóa {name}?',
      'files.folder_type': 'Thư mục tệp',
      'files.file_type': 'Tệp {ext}',
      'files.drives_list': 'Danh sách ổ đĩa',
      'files.drives_root': 'Ổ đĩa',

      // View 7: Deep Audit Logs
      'audit.title': 'Nhật ký truy vết & Kiểm toán (Deep Audit Logs)',
      'audit.subtitle': 'Ghi nhận chi tiết IP, loại thiết bị nguồn, tài khoản truy cập, máy đích và lịch sử thao tác',
      'audit.btn_refresh': 'Làm mới',
      'audit.btn_refresh_title': 'Làm mới dữ liệu nhật ký',
      'audit.btn_export_csv': 'Xuất CSV',
      'audit.btn_export_csv_title': 'Xuất toàn bộ nhật ký sang CSV',
      'audit.search_placeholder': 'Tìm theo IP, tài khoản, thiết bị, Room ID, lệnh...',
      'audit.action_all': 'Tất cả hành động',
      'audit.action_session_conn': 'Kết nối máy trạm (SESSION_CONNECTED)',
      'audit.action_session_disc': 'Ngắt kết nối (SESSION_DISCONNECTED)',
      'audit.action_pin_failed': 'Sai mã PIN (CONNECT_PIN_FAILED)',
      'audit.action_cmd': 'Lệnh Terminal (CMD_EXEC)',
      'audit.action_file_browse': 'Duyệt thư mục (FILE_BROWSE)',
      'audit.action_file_read': 'Đọc/Mở file trực tiếp (FILE_READ)',
      'audit.action_file_save': 'Lưu file trực tiếp (FILE_SAVE)',
      'audit.action_file_dl': 'Tải file về (FILE_DOWNLOAD)',
      'audit.action_file_ul': 'Tải file lên (FILE_UPLOAD)',
      'audit.action_file_del': 'Xóa file (FILE_DELETE)',
      'audit.action_file_mkdir': 'Tạo thư mục (FILE_MKDIR)',
      'audit.action_proc_kill': 'Dừng tiến trình (PROCESS_KILL)',
      'audit.action_power': 'Nguồn/Khóa máy (POWER_ACTION)',
      'audit.action_block_input': 'Khóa chuột/phím (BLOCK_INPUT)',
      'audit.action_clip_sync': 'Đồng bộ Clipboard (CLIPBOARD_SYNC)',
      'audit.action_auth_login': 'Đăng nhập tài khoản',
      'audit.action_auth_reg': 'Đăng ký tài khoản',
      'audit.action_dev_linked': 'Liên kết máy trạm',
      'audit.th_time': 'Thời gian',
      'audit.th_action': 'Hành động',
      'audit.th_source': 'Người dùng & IP Nguồn',
      'audit.th_target': 'Máy đích (Host)',
      'audit.th_details': 'Chi tiết nghiệp vụ',
      'audit.loading': 'Đang tải nhật ký kiểm toán...',
      'audit.empty': 'Không có bản ghi nhật ký phù hợp',
      'audit.anonymous': 'Ẩn danh',
      'audit.refreshed': 'Đã làm mới nhật ký kiểm toán',
      'audit.exporting': 'Đang tải tệp CSV nhật ký...',
      'audit.summary': 'Hiển thị {showing} / {total} bản ghi',
      'audit.prev': 'Trang trước',
      'audit.next': 'Trang sau',

      // Side Drawer (Shelf)
      'shelf.title': 'Tệp tin & Bộ nhớ tạm',
      'shelf.close_title': 'Đóng',
      'shelf.tab_files': 'Tệp',
      'shelf.tab_clipboard': 'Clip',
      'shelf.tab_chat': 'Chat',
      'shelf.btn_expand': 'Mở File Explorer toàn màn hình',
      'shelf.drop_text': 'Kéo thả tệp tin để gửi',
      'shelf.drop_sub': 'hoặc bấm để chọn tệp',
      'shelf.browse_title': 'Duyệt thư mục máy trạm:',
      'shelf.btn_up': 'Thư mục cha ⇡',
      'shelf.drives_root': 'Ổ đĩa',
      'shelf.no_conn': 'Kết nối máy trạm để duyệt tệp',
      'shelf.clip_title': 'Nội dung bộ nhớ tạm (Tự động đồng bộ 2 chiều):',
      'shelf.clip_placeholder': 'Chưa có dữ liệu clipboard...',
      'shelf.btn_push_clip': 'Đẩy clipboard',
      'shelf.btn_type_direct': 'Gõ trực tiếp',
      'shelf.type_direct_title': 'Gõ trực tiếp ký tự Unicode vào ứng dụng đang mở (PowerPoint, Word, Notepad...)',
      'shelf.chat_title': 'Tin nhắn trực tiếp tới người ngồi máy trạm:',
      'shelf.chat_welcome': 'Phiên chat trực tiếp với máy trạm',
      'shelf.chat_placeholder': 'Nhập tin nhắn...',
      'shelf.chat_send': 'Gửi',

      // Quick Connect Modal
      'qc.title': 'Kết nối bằng Room ID',
      'qc.subtitle': 'Nhập mã phòng và PIN để kết nối trực tiếp',
      'qc.relay_url': 'Relay Server URL',
      'qc.room_id': 'Room ID / Mã phiên',
      'qc.pin': 'Mã PIN bảo mật',
      'qc.btn_cancel': 'Hủy',
      'qc.btn_connect': 'Kết nối ngay',

      // Online File Editor Modal
      'editor.saved': 'ĐÃ LƯU',
      'editor.dirty': '● ĐÃ SỬA (CHƯA LƯU)',
      'editor.wrap': 'Xuống dòng',
      'editor.wrap_title': 'Tự động xuống dòng',
      'editor.btn_save': 'Lưu (Ctrl+S)',
      'editor.btn_save_title': 'Lưu trực tiếp lên máy trạm (Ctrl + S)',
      'editor.btn_close_title': 'Đóng trình soạn thảo',
      'editor.path_title': 'Đường dẫn tệp trên máy trạm',
      'editor.cursor': 'Dòng {line}, Cột {col}',
      'editor.cursor_default': 'Dòng 1, Cột 1',
      'editor.stats': '{lines} dòng, {chars} ký tự',
      'editor.stats_default': '0 dòng, 0 ký tự',
      'editor.unmodified': 'Chưa sửa đổi',
      'editor.saved_at': 'Đã lưu lúc {time}',
      'editor.saving': 'Đang lưu...',
      'editor.read_error': 'Không thể mở tệp: {error}',
      'editor.save_error': 'Lỗi khi lưu tệp: {error}',
      'editor.save_success': 'Đã lưu tệp thành công lên máy trạm',
      'editor.discard_confirm': 'Tệp đã được chỉnh sửa nhưng chưa lưu. Bạn có chắc chắn muốn đóng mà không lưu?',

      // Ambient Confirmation & Alert Dialog
      'dialog.confirm_title': 'Xác nhận',
      'dialog.alert_title': 'Thông báo',
      'dialog.btn_confirm': 'Đồng ý',
      'dialog.btn_cancel': 'Hủy',
      'dialog.btn_ok': 'Đã hiểu',
      'dialog.btn_delete': 'Xóa',
      'dialog.btn_kill': 'Ngắt phiên',
      'dialog.btn_discard': 'Đóng & Hủy',
      'dialog.btn_keep_editing': 'Tiếp tục sửa',

      // Toasts & Alerts
      'toast.ws_error': 'Không thể kết nối WebSocket: {error}',
      'toast.connected': 'Đã kết nối thành công tới máy trạm {room}!',
      'toast.disconnected': 'Đã ngắt kết nối với máy trạm',
      'toast.restart_success': 'Máy trạm đã khởi động lại và kết nối thành công!',
      'toast.generic_error': 'Lỗi: {message}',
      'toast.kill_success': 'Đã dừng tiến trình PID {pid}',
      'toast.kill_failed': 'Không thể dừng tiến trình PID {pid}',
      'toast.file_delete_success': 'Đã xóa tệp/thư mục thành công',
      'toast.file_delete_failed': 'Không thể xóa (tệp đang được dùng hoặc bị khóa quyền)',
      'toast.mkdir_success': 'Đã tạo thư mục mới thành công',
      'toast.mkdir_failed': 'Lỗi tạo thư mục: {error}',
      'toast.upload_success': 'Đã truyền tệp thành công: {filename}',
      'toast.upload_failed': 'Lỗi tải tệp: {error}',
      'toast.download_success': 'Đã tải xuống thành công: {filename}',
      'toast.clip_pushed': 'Đã đẩy nội dung clipboard sang máy trạm',
      'toast.clip_empty': 'Bộ nhớ tạm trống, vui lòng nhập nội dung',
      'toast.type_direct_done': 'Đã gửi lệnh gõ trực tiếp sang máy trạm',
      'toast.audio_started': 'Đã kích hoạt truyền âm thanh máy trạm',
      'toast.audio_stopped': 'Đã tắt truyền âm thanh máy trạm',
      'toast.mic_started': 'Đã bật micro nói sang máy trạm',
      'toast.mic_stopped': 'Đã tắt micro nói sang máy trạm',
      'toast.laser_on': 'Đã bật Laser Pointer (Chuột sẽ tạo vệt laser trên máy đích)',
      'toast.laser_off': 'Đã tắt Laser Pointer',
      'toast.cam_on': 'Đã bật Face Cam (Webcam PiP)',
      'toast.cam_off': 'Đã tắt Face Cam',
      'toast.cam_error': 'Không thể kích hoạt webcam: {error}',
      'toast.record_started': 'Bắt đầu ghi hình phiên làm việc',
      'toast.record_stopped': 'Đã kết thúc ghi hình. Tệp video đang được tải về...',
      'toast.screenshot_saved': 'Đã chụp và lưu ảnh màn hình máy trạm',
      'toast.block_input_on': 'Đã khóa chuột & bàn phím tại máy đích',
      'toast.block_input_off': 'Đã mở khóa chuột & bàn phím tại máy đích',

      // Landing Page
      'nav.home': 'Trang chủ',
      'ro.landing': 'TRANG CHỦ // GIỚI THIỆU',
      'landing.badge': 'v2.5.0 // ĐA NỀN TẢNG // WINDOWS • LINUX • MACOS • IPADOS // MULTI-MONITOR',
      'landing.hero_title': 'ĐIỀU KHIỂN TỪ XA ĐA NỀN TẢNG CHÍNH XÁC CAO',
      'landing.hero_subtitle': 'Màn hình 120 FPS, âm thanh 2 chiều, kéo thả bố cục đa màn hình, thanh Deck 3 chế độ thông minh và quản trị máy trạm Windows, macOS, Linux an toàn qua Outbound Relay.',
      'landing.os_support_lbl': 'MÁY TRẠM HỖ TRỢ:',
      'landing.btn_start': 'Bắt đầu ngay',
      'landing.btn_dashboard': 'Vào bảng điều khiển',
      'landing.btn_quick': 'Kết nối nhanh',
      'landing.btn_download': 'Tải bộ cài',
      'landing.stat_latency': '< 15ms Độ trễ',
      'landing.stat_fps': '60-120 FPS Stream',
      'landing.stat_monitors': 'Đa màn hình Grid',
      'landing.stat_deck': 'Deck 3 Chế độ',
      'landing.stat_cross': 'Win • Linux • macOS',
      'landing.stat_audio': 'Âm thanh 2 chiều',
      'landing.stat_engine': 'Desktop Standalone',
      'landing.topo_client': 'MÁY ĐIỀU KHIỂN',
      'landing.topo_client_meta': '0.8ms ĐỘ TRỄ',
      'landing.topo_relay': 'MEIKOVA RELAY',
      'landing.topo_relay_meta': 'E2E TLS 1.3',
      'landing.topo_host': 'MÁY TRẠM HOST',
      'landing.topo_host_meta': 'WIN • LINUX • MACOS',

      // Landing Quick Connect Bar
      'landing.qc_title': 'Kết nối tức thì không cần cài đặt',
      'landing.qc_room_placeholder': 'Nhập Room ID (VD: RD-4821)',
      'landing.qc_pin_placeholder': 'PIN (nếu có)',
      'landing.qc_btn_connect': 'Kết nối ngay',

      // Landing Dual Architecture Modes
      'landing.modes_title': 'Kiến trúc truy cập kép linh hoạt',
      'landing.modes_subtitle': 'Đáp ứng hoàn hảo cả nhu cầu hỗ trợ khách hàng tức thì và quản trị máy cá nhân 24/7',
      
      'landing.mode1_tag': 'ON-DEMAND REMOTE ASSIST',
      'landing.mode1_title': 'Chế độ Hỗ trợ Tức thì (On-Demand)',
      'landing.mode1_desc': 'Hỗ trợ khách hàng và xử lý sự cố từ xa nhanh chóng mà không cần đăng nhập hay liên kết tài khoản.',
      'landing.mode1_feat1': 'Mã Room ID & PIN 6 số tạo ngẫu nhiên bảo mật',
      'landing.mode1_feat2': '1-click sao chép văn bản mời kèm thông tin phòng',
      'landing.mode1_feat3': 'Người dùng máy trạm có thể ngắt kết nối khẩn cấp bất kỳ lúc nào',
      'landing.mode1_feat4': 'Bật phần mềm lên là có phòng, không cấu hình rườm rà',

      'landing.mode2_tag': 'UNATTENDED 24/7 ACCESS',
      'landing.mode2_title': 'Chế độ Quản trị Thường trực (Unattended 24/7)',
      'landing.mode2_desc': 'Truy cập máy tính làm việc và văn phòng từ xa liên tục, ổn định và an toàn tuyệt đối.',
      'landing.mode2_feat1': 'Gắn kết vĩnh viễn với tài khoản chủ máy',
      'landing.mode2_feat2': 'Tự khởi động cùng Windows / macOS / Linux',
      'landing.mode2_feat3': 'Chống ngủ máy (Power Manager Awake API)',
      'landing.mode2_feat4': 'Thu nhỏ khay hệ thống (System Tray), kết nối 1 chạm',

      // Landing Studio Features
      'landing.features_title': 'Khả năng điều khiển chuẩn Studio & Đa Nền tảng',
      'landing.features_subtitle': 'Được tối ưu hoá từng mili-giây để đem lại cảm giác như đang thao tác trực tiếp trước màn hình máy trạm',
      'landing.feat_stream_title': 'Màn hình 120 FPS & Đa Màn hình (Multi-Monitor Grid)',
      'landing.feat_stream_desc': 'Tự động nhận diện mọi màn hình máy trạm. Trực tiếp kéo thả sắp xếp vị trí hiển thị trên lưới Grid theo thực tế vật lý, chuyển đổi 1-click hoặc xem toàn cảnh.',
      'landing.feat_deck_title': 'Thanh Điều khiển Floating Deck 3 Chế độ',
      'landing.feat_deck_desc': 'Linh hoạt lựa chọn: Đáy nổi, Mép trên ghim cố định hoặc Mép trên tự động ẩn (rê chuột/chạm để trượt ra), hoàn toàn không che thanh Taskbar hay vùng làm việc.',
      'landing.feat_cross_title': 'Máy trạm Đa Nền tảng (Windows, macOS, Linux)',
      'landing.feat_cross_desc': 'Host Agent tối ưu hóa cho Windows (Win32 API/Service 24/7), Linux (systemd daemon), macOS (Launchd/Apple Silicon M1-M4) kết nối xuyên suốt qua Outbound Relay.',
      'landing.feat_audio_title': 'Âm thanh 2 chiều & Mic Talkback',
      'landing.feat_audio_desc': 'Truyền âm thanh hệ thống cực nét qua WebAudio PCM, bật mic từ xa nói sang máy trạm không giật lag.',
      'landing.feat_term_title': 'Terminal tương tác thời gian thực',
      'landing.feat_term_desc': 'Gõ lệnh trực tiếp như native shell (PowerShell / Bash / Zsh), pipeline realtime, nhận phản hồi ngay trên giao diện web không cần mở màn hình.',
      'landing.feat_files_title': 'Quản lý tệp 2 chiều & Sửa trực tiếp',
      'landing.feat_files_desc': 'Duyệt toàn bộ ổ đĩa, kéo thả upload/download và mở sửa trực tiếp file text/code ngay trên trình duyệt mà không cần tải file về.',

      // Landing Download Hub
      'landing.dl_title': 'Trung tâm Tải về & Cài đặt Đa Nền Tảng',
      'landing.dl_subtitle': 'Lựa chọn phương thức triển khai phù hợp nhất với hệ điều hành máy trạm của bạn',
      'landing.dl_tab_win': 'Windows',
      'landing.dl_tab_linux': 'Linux',
      'landing.dl_tab_macos': 'macOS',
      'landing.dl_tab_web': 'Web & iPadOS',

      'landing.dl_exe_title': 'Phần mềm Desktop Standalone (.exe)',
      'landing.dl_exe_desc': 'Đóng gói sẵn trọn gói Python Runtime, Tkinter, Pillow, Websockets. Hỗ trợ 2 tùy chọn: Chạy ngay không cần quyền Admin hoặc Cài đặt dịch vụ hệ thống 24/7.',
      'landing.dl_exe_btn': 'Tải MeikovaRelayHost.exe (19.8 MB)',
      'landing.dl_exe_btn_title': 'Tải MeikovaRelayHost.exe',
      'landing.dl_exe_btn_size': '(19.8 MB)',
      'landing.dl_exe_f1': '2 Tùy chọn: User Portable & Dịch vụ 24/7',
      'landing.dl_exe_f2': 'Khởi động cùng Win & Chống tắt máy',
      'landing.dl_exe_f3': 'Tương thích Windows 10/11/Server (64-bit)',
      'landing.dl_bat_title': 'Bộ cài đặt tự động (.bat)',
      'landing.dl_bat_desc': 'Script cài đặt thông minh, tự động liên kết với tài khoản chủ máy và tự động fallback tải .exe nếu máy trạm chưa có Python.',
      'landing.dl_bat_btn': 'Tải Setup-MeikovaHost.bat',
      'landing.dl_bat_size': '(Tự động nhận diện)',
      'landing.dl_bat_f1': 'Tự động liên kết tài khoản chủ',
      'landing.dl_bat_f2': 'Tự tạo Service chạy nền 24/7',
      'landing.dl_bat_f3': 'Tự tải EXE nếu máy thiếu Python',
      'landing.dl_ps1_title': 'Cài đặt 1 dòng lệnh (PowerShell)',
      'landing.dl_ps1_desc': 'Dành cho IT Admin / DevOps triển khai hàng loạt máy trạm chỉ với một câu lệnh PowerShell duy nhất.',
      'landing.dl_ps1_copy': 'Sao chép lệnh PowerShell',
      'landing.dl_ps1_copy_btn': 'Sao chép lệnh PowerShell',
      'landing.dl_ps1_size': '(1-Click Copy)',
      'landing.dl_ps1_copied': 'Đã chép!',
      'landing.toast_copied': 'Đã sao chép lệnh cài đặt vào clipboard!',

      'landing.dl_linux_sh_title': 'Cài đặt 1 dòng lệnh (Bash)',
      'landing.dl_linux_sh_desc': 'Tự động tải gói Agent, tạo môi trường ảo Python venv độc lập, ghi file cấu hình và kích hoạt chạy ngầm.',
      'landing.dl_linux_sh_copy': 'Sao chép lệnh Linux',
      'landing.dl_linux_sh_copy_btn': 'Sao chép lệnh Linux',
      'landing.dl_linux_sh_size': '(1-Click Copy)',
      'landing.dl_linux_deb_title': 'Gói cài đặt Debian / Ubuntu (.deb)',
      'landing.dl_linux_deb_desc': 'File cài đặt chuẩn Debian / Ubuntu (.deb), tích hợp sẵn binary biên dịch, systemd daemon tự chạy ngầm và desktop launcher.',
      'landing.dl_linux_deb_f1': 'Cài 1-click qua: sudo dpkg -i',
      'landing.dl_linux_deb_f2': 'Tự tạo systemd service 24/7',
      'landing.dl_linux_deb_f3': 'Hỗ trợ Ubuntu 20.04+, Debian 11+',
      'landing.dl_linux_deb_btn': 'Tải meikova-relay.deb',
      'landing.dl_linux_tar_title': 'Gói Linux Độc lập (.tar.gz)',
      'landing.dl_linux_tar_desc': 'Gói nén chứa file thực thi ELF độc lập, unit file systemd và script install.sh tương thích mọi bản phân phối Linux.',
      'landing.dl_linux_tar_f1': 'Chạy trực tiếp không cần cài đặt',
      'landing.dl_linux_tar_f2': 'Tương thích Fedora, Arch, RHEL, Mint',
      'landing.dl_linux_tar_f3': 'Kèm mã nguồn Python universal',
      'landing.dl_linux_tar_btn': 'Tải meikova-relay-linux.tar.gz',
      'landing.dl_linux_systemd_title': 'Dịch vụ Hệ thống (Systemd 24/7)',
      'landing.dl_linux_systemd_desc': 'Chạy ngầm ổn định như một Linux daemon qua meikova-relay.service, tự động bật cùng OS và tự khôi phục khi restart.',
      'landing.dl_linux_systemd_f1': 'Tự khởi động cùng Linux (systemctl)',
      'landing.dl_linux_systemd_f2': 'Hỗ trợ X11 & Wayland Screen Grab',
      'landing.dl_linux_systemd_f3': 'Phù hợp Ubuntu, Debian, Arch, Fedora',
      'landing.dl_linux_headless_title': 'Máy chủ Headless & Raspberry Pi',
      'landing.dl_linux_headless_desc': 'Hoạt động nhẹ nhàng trên các máy chủ không màn hình, máy tính nhúng ARM64, Raspberry Pi OS và container.',
      'landing.dl_linux_headless_f1': 'Tối ưu kiến trúc ARM64 & x86_64',
      'landing.dl_linux_headless_f2': 'Quản lý từ xa qua Web Terminal & Files',
      'landing.dl_linux_headless_f3': 'Mức chiếm dụng RAM cực thấp (< 50MB)',

      'landing.dl_macos_sh_title': 'Cài đặt 1 dòng lệnh (macOS)',
      'landing.dl_macos_sh_desc': 'Script cài đặt tự động tương thích 100% với macOS Monterey, Ventura, Sonoma, Sequoia (Intel & Apple Silicon M1-M4).',
      'landing.dl_macos_sh_copy': 'Sao chép lệnh macOS',
      'landing.dl_macos_sh_copy_btn': 'Sao chép lệnh macOS',
      'landing.dl_macos_sh_size': '(1-Click Copy)',
      'landing.dl_macos_apple_silicon_title': 'Tối ưu Apple Silicon & Intel',
      'landing.dl_macos_apple_silicon_desc': 'Tận dụng trực tiếp Quartz Screen Capture và Accessibility framework để điều khiển mượt mà, chuẩn xác từng pixel.',
      'landing.dl_macos_apple_silicon_f1': 'Hỗ trợ Chip M1, M2, M3, M4 & Intel',
      'landing.dl_macos_apple_silicon_f2': 'Ghi hình màn hình độ trễ tối thiểu',
      'landing.dl_macos_apple_silicon_f3': 'Cần cấp quyền Screen & Accessibility',
      'landing.dl_macos_tar_btn': 'Tải meikova-relay-macos.tar.gz',
      'landing.dl_macos_guide_link': 'Xem hướng dẫn cấp quyền Security & Accessibility',
      'landing.dl_macos_launchd_title': 'Dịch vụ Khởi động (Launchd 24/7)',
      'landing.dl_macos_launchd_desc': 'Đăng ký LaunchAgent com.meikova.relay.plist để tự động chạy ngầm mỗi khi người dùng đăng nhập vào macOS.',
      'landing.dl_macos_launchd_f1': 'Tự động chạy qua launchctl',
      'landing.dl_macos_launchd_f2': 'Hoạt động ngầm không hiện cửa sổ',
      'landing.dl_macos_launchd_f3': 'Không kẹt tường lửa qua Outbound Tunnel',

      'landing.dl_web_title': 'Trình điều khiển Web Không cần Cài đặt',
      'landing.dl_web_desc': 'Không cần cài bất kỳ phần mềm nào lên máy điều khiển. Mở trình duyệt Web trên PC, laptop hoặc tablet và truy cập ngay lập tức.',
      'landing.dl_web_f1': 'Hỗ trợ Chrome, Safari, Edge, Firefox',
      'landing.dl_web_f2': 'Mã hóa E2E qua giao thức TLS 1.3',
      'landing.dl_web_f3': 'Mượt mà trên cả mạng 4G/5G và Wi-Fi yếu',
      'landing.dl_web_ipad_title': 'Tối ưu Cảm ứng iPadOS & Tablet',
      'landing.dl_web_ipad_desc': 'Giao diện cảm ứng toàn diện: Hỗ trợ Touch Gestures, Laser Pointer khi dùng bút Apple Pencil, giả lập chuột phải và vuốt cuộn trang.',
      'landing.dl_web_ipad_f1': 'Hỗ trợ cử chỉ vuốt, chạm, chụm phóng to',
      'landing.dl_web_ipad_f2': 'Con trỏ Laser Pointer hỗ trợ hội thảo',
      'landing.dl_web_ipad_f3': 'Tự động xoay ngang dọc linh hoạt',
      'landing.dl_web_shortcuts_title': 'Bàn phím Ảo & Phím tắt Hệ thống',
      'landing.dl_web_shortcuts_desc': 'Thanh công cụ tích hợp sẵn các phím chức năng đặc thù của máy trạm: Windows Key, Ctrl+Alt+Del, Alt+Tab, Esc và chuyển đổi đa màn hình.',
      'landing.dl_web_shortcuts_f1': 'Phím gửi Ctrl+Alt+Del khẩn cấp',
      'landing.dl_web_shortcuts_f2': 'Tổ hợp phím Windows / Command đầy đủ',
      'landing.dl_web_shortcuts_f3': 'Khóa / Chống vô tình gửi phím tắt trình duyệt',

      // Landing CI/CD & Footer
      'landing.cicd_title': 'Biên dịch tự động qua GitHub Actions CI/CD',
      'landing.cicd_desc': 'Mọi phiên bản phát hành đều được tự động biên dịch, kiểm thử và đóng gói trên hạ tầng GitHub Actions độc lập (Windows, Ubuntu Linux, macOS), xuất bản đầy đủ gói cài đặt (.exe, .deb, .tar.gz, .dmg) kèm mã băm SHA256 kiểm chứng.',
      'landing.footer_brand': 'MEIKOVA RELAY // AMBIENT INSTRUMENT SPECIFICATION',
      'landing.footer_status': 'HỆ THỐNG: HOẠT ĐỘNG // RELAY: CLOUD-EDGE // E2E ENCRYPTED',

      // Session Activity & Inactivity Timeout
      'session.modal_title': 'Cấu hình phiên hoạt động',
      'session.modal_subtitle': 'Tự động ngắt kết nối và đăng xuất an toàn khi không hoạt động',
      'session.remote_idle_label': 'Thời gian chờ ngắt kết nối (X phút)',
      'session.remote_idle_hint': 'Tự động ngắt phiên điều khiển máy trạm khi không có thao tác chuột/phím',
      'session.global_idle_label': 'Thời gian chờ tự động đăng xuất (Y phút)',
      'session.global_idle_hint': 'Tự động đăng xuất tài khoản khi không có kết nối hay thao tác gì',
      'session.sliding_hint': 'Cơ chế trượt: Mọi thao tác chuột/phím sẽ tự làm mới token và gia hạn phiên để tránh văng.',
      'session.btn_cancel': 'Hủy',
      'session.btn_save': 'Lưu cấu hình',
      'session.toast_saved': 'Đã lưu cấu hình phiên: X={x} phút, Y={y} phút',
      'session.toast_remote_disconnected': 'Đã tự động ngắt kết nối máy trạm do không có thao tác trong {min} phút',
      'session.toast_global_logout': 'Đã tự động đăng xuất tài khoản do không hoạt động trong {min} phút',
      'topbar.session_cfg': 'Phiên',
      'topbar.session_cfg_title': 'Cấu hình thời gian chờ phiên (X/Y phút)'
    },

    en: {
      // Top Navigation
      'nav.workstations': 'Workstations',
      'nav.screen': 'Screen',
      'nav.files': 'Files & Folders',
      'nav.terminal': 'Terminal',
      'nav.tasks': 'Processes',
      'nav.audit': 'Audit Logs',
      'nav.aria_label': 'System Control Navigation',

      // Topbar
      'topbar.brand': 'MEIKOVA RELAY',
      'topbar.logout': 'Logout',
      'topbar.logout_title': 'Logout from current session',
      'topbar.quick_connect': 'Quick Connect',
      'topbar.quick_connect_title': 'Direct connect via Room ID',
      'topbar.download_apps': 'Download App',
      'topbar.download_apps_title': 'Download Meikova Relay Apps (Host & Viewer)',
      'dl_modal.title': 'Install & Download Apps',
      'dl_modal.subtitle': 'CROSS-PLATFORM ECOSYSTEM // HOST AGENT & VIEWER',
      'dl_modal.close_title': 'Close',
      'dl_modal.tab_host': 'Host Agent (Station)',
      'dl_modal.tab_client': 'Viewer Client (Controller)',
      'dl_modal.host_role_hint': 'CONTROLLED MACHINE: Install on computers that need remote access or support.',
      'dl_modal.client_role_hint': 'CONTROLLER DEVICE: Install on your device to connect, monitor, and control hosts.',

      // Telemetry Readouts
      'ro.disconnected': 'DISCONNECTED',
      'ro.connecting': 'CONNECTING...',
      'ro.connected': 'CONNECTED',
      'ro.reconnecting': 'AUTO RECONNECTING...',
      'ro.auth': 'AUTHENTICATION',
      'ro.dashboard': 'WORKSTATION FLEET',
      'ro.authenticating': 'AUTHENTICATING...',
      'ro.rebooting': 'REBOOTING WORKSTATION...',

      // View 1: Auth
      'auth.title': 'Admin Login',
      'auth.subtitle': 'Comprehensive workstation remote control via Outbound Relay',
      'auth.tab_login': 'Sign In',
      'auth.tab_register': 'Register',
      'auth.username_label': 'Username',
      'auth.username_placeholder': 'Enter username',
      'auth.password_label': 'Password',
      'auth.password_placeholder': '••••••••',
      'auth.or': 'or',
      'auth.or_local': 'or internal account',
      'auth.google_signin': 'Continue with Google',
      'auth.btn_login': 'Enter Dashboard',
      'auth.btn_register': 'Create Account',
      'auth.err_missing': 'Please fill in both username and password',
      'auth.err_generic': 'Authentication error occurred',

      // View 2: Dashboard
      'dashboard.title': 'Workstation Fleet',
      'dashboard.subtitle': 'Devices linked to your account',
      'dashboard.btn_add_device': 'Add Workstation',
      'dashboard.btn_add_device_title': 'Add Windows, macOS, or Linux workstation',
      'dashboard.btn_download_exe': 'Download Desktop App (.exe)',
      'dashboard.btn_download_exe_title': 'Download standalone desktop app (.exe) - No Python needed',
      'dashboard.btn_download_host': 'Download Installer (.bat)',
      'dashboard.btn_download_host_title': 'Download automated host installer (.bat)',
      'dashboard.btn_mac_title': 'Install macOS Workstation Agent',
      'dashboard.btn_linux_title': 'Install Linux Workstation Agent',
      'dashboard.btn_quick_connect': 'Connect Room ID',
      'dashboard.empty': 'No workstations linked yet',
      'dashboard.empty_hint': 'Download the software or run the automated command to link your Windows, macOS, or Linux workstation.',
      'dashboard.loading': 'Loading workstation fleet...',
      'dashboard.load_error': 'Failed to load device list.',
      'add_device.title': 'Add New Workstation',
      'add_device.subtitle': 'Select operating system to install or connect automatically',
      'dashboard.status_online': 'Online',
      'dashboard.status_offline': 'Offline',
      'dashboard.btn_connect': 'Connect',
      'dashboard.btn_delete': 'Delete',
      'dashboard.delete_confirm': 'Are you sure you want to unlink this workstation?',
      'dashboard.unlink_success': 'Workstation unlinked successfully',

      // View 3: Remote Desktop & Floating Deck
      'deck.monitor_title': 'Select display monitor',
      'deck.monitor_all': 'All Displays',
      'deck.monitor_single': 'Display {num}',
      'deck.quality_title': 'Resolution, FPS & quality profile',
      'deck.quality_native_1to1': '1:1 Native (Pixel-Perfect)',
      'deck.quality_auto_sync': 'Auto-Negotiate (Auto-Sync)',
      'deck.quality_ultra_120': '120 FPS Ultra Smooth',
      'deck.quality_speed': '60 FPS Smooth',
      'deck.quality_crisp_2k_4k': '2K / 4K Crisp (95%)',
      'deck.quality_hd': 'Crisp HD (85%)',
      'deck.quality_balanced': '30 FPS Balanced',
      'deck.quality_grayscale': 'Low Bandwidth',
      'deck.sync_display_btn': 'SYNC',
      'deck.sync_display_title': 'Auto-negotiate optimal display configuration (Host ↔ Controller)',
      'deck.scale_title': 'Fit window / 1:1 Pixel scale',
      'deck.grid_btn': 'GRID',
      'deck.grid_toggle_title': 'Toggle Multi-Monitor Drag-and-Drop Grid',
      'deck.grid_side_by_side': 'Side-by-side [Mon 1 | Mon 2]',
      'deck.grid_invert': 'Inverted [Mon 2 | Mon 1]',
      'deck.grid_stacked': 'Stacked [Mon 1 / Mon 2]',
      'deck.fullscreen_title': 'Fullscreen',
      'deck.laser_title': 'Toggle Laser Pointer',
      'deck.record_title': 'Record Session',
      'deck.cam_title': 'Toggle Face Cam (Webcam PiP during recording)',
      'deck.screenshot_title': 'Take Host Screenshot',
      'deck.audio_title': 'Toggle Host Audio Stream (Live Audio)',
      'deck.mic_title': 'Toggle Remote Voice Intercom (Mic)',
      'deck.osk_title': 'Virtual On-Screen Keyboard',
      'deck.block_input_title': 'Block Host Input (Mouse & Keyboard)',
      'deck.power_title': 'Power Actions',
      'deck.power_lock': 'Lock Screen',
      'deck.power_restart': 'Restart Host',
      'deck.power_restart_confirm': 'Are you sure you want to restart the remote host? The session will pause and automatically reconnect once reboot completes.',
      'deck.shelf_title': 'File Shelf & Clipboard',
      'deck.disconnect_title': 'Disconnect',
      'deck.face_cam_badge': 'FACE CAM',
      'deck.drop_title': 'Drop files to transfer to host',
      'deck.drop_hint': 'Files will be saved directly to the remote host Downloads folder',
      'deck.display_mode_title': 'Deck display mode (Bottom / Top Pinned / Top Auto-hide)',
      'deck.pin_quick_title': 'Pin / Unpin top bar deck',
      'deck.top_trigger_title': 'Hover or tap here to reveal remote deck controller',
      'deck.mode_menu_title': 'DECK POSITION & DISPLAY MODE',
      'deck.mode_bottom': 'Bottom Floating Deck (Default)',
      'deck.mode_bottom_desc': 'Floating pill deck docked at bottom',
      'deck.mode_top_pinned': 'Top Bar (Pinned)',
      'deck.mode_top_pinned_desc': 'Fixed at top edge, avoids host taskbar',
      'deck.mode_top_unpinned': 'Top Bar (Auto-hide)',
      'deck.mode_top_unpinned_desc': 'Slides down on top hover, prevents overlay',

      // View 4: Terminal
      'terminal.title': 'PS REMOTE // HOST SHELL',
      'terminal.badge_disconnected': 'DISCONNECTED',
      'terminal.badge_connected': 'CONNECTED (POWERSHELL UTF-8)',
      'terminal.hint': 'Enter: Execute | ↑/↓: History | Ctrl+L: Clear',
      'terminal.btn_clear': 'Clear Screen',
      'terminal.screen_title': 'Click screen to type commands directly',
      'terminal.welcome': 'Meikova Relay PowerShell Console ready. Running in UTF-8 environment.',

      // View 5: Tasks & Diagnostics
      'tasks.title': 'Process Monitor & Hardware Diagnostics',
      'tasks.subtitle': 'Hardware telemetry and running processes on remote host',
      'tasks.refresh_title': 'Refresh',
      'tasks.ram_title': 'RAM Memory',
      'tasks.disk_c_title': 'Drive C:',
      'tasks.os_title': 'Operating System',
      'tasks.measuring': 'Measuring...',
      'tasks.table_title': 'Process List (Sorted by RAM)',
      'tasks.search_placeholder': 'Filter processes...',
      'tasks.th_pid': 'PID',
      'tasks.th_name': 'Process Name',
      'tasks.th_ram': 'RAM (MB)',
      'tasks.th_actions': 'Actions',
      'tasks.no_conn': 'Not connected to host',
      'tasks.btn_kill': 'End Task',
      'tasks.kill_confirm': 'Are you sure you want to end process {name} (PID: {pid})?',
      'tasks.search_no_results': 'No matching processes found',

      // View 6: Remote File Explorer
      'files.title': 'Remote File Explorer',
      'files.subtitle': 'Multi-threaded file transfer and directory traversal over WebSocket 443 (Bypass Firewall/NAT)',
      'files.path_placeholder': 'Enter full path (e.g. C:\\Windows)...',
      'files.btn_go': 'Go',
      'files.btn_cancel': 'Cancel',
      'files.edit_path_title': 'Edit path directly',
      'files.btn_up': 'Up',
      'files.btn_up_title': 'Parent directory',
      'files.btn_refresh': 'Refresh',
      'files.btn_refresh_title': 'Refresh file list',
      'files.btn_new_folder': 'New Folder',
      'files.btn_new_folder_title': 'Create new folder',
      'files.btn_upload': 'Upload File',
      'files.btn_upload_title': 'Upload files to this directory',
      'files.search_placeholder': 'Filter files in directory...',
      'files.mode_list_title': 'List View',
      'files.mode_grid_title': 'Grid View',
      'files.transfer_label': 'Transferring...',
      'files.th_name': 'File / Folder Name',
      'files.th_size': 'Size',
      'files.th_modified': 'Date Modified',
      'files.th_actions': 'Actions',
      'files.no_conn': 'Not connected to host',
      'files.action_edit': 'Edit',
      'files.action_edit_title': 'Open and edit directly on host',
      'files.action_download': 'Download',
      'files.action_download_title': 'Download file to client',
      'files.action_delete': 'Delete',
      'files.action_delete_title': 'Delete this file/folder',
      'files.action_copy': 'Copy',
      'files.action_copy_title': 'Copy this item',
      'files.action_cut': 'Cut',
      'files.action_cut_title': 'Cut / Move this item',
      'files.action_rename': 'Rename',
      'files.action_rename_title': 'Rename this item',
      'files.rename_title': 'Rename Item',
      'files.rename_prompt': 'Enter new name for file or folder:',
      'files.new_folder_title': 'New Folder',
      'files.btn_paste': 'Paste',
      'files.btn_paste_title': 'Paste copied/cut item here',
      'files.status_count': '{count} items',
      'files.status_selected': '{count} selected',
      'files.status_summary': '{count} items ({dirs} folders, {files} files)',
      'files.total_size': 'Total size: {size}',
      'files.empty_folder': 'Folder is empty',
      'files.not_found': 'No matching files found',
      'files.new_folder_prompt': 'Enter new folder name:',
      'files.delete_confirm': 'Are you sure you want to delete {name}?',
      'files.folder_type': 'File folder',
      'files.file_type': '{ext} File',
      'files.drives_list': 'Drive List',
      'files.drives_root': 'Drives',

      // View 7: Deep Audit Logs
      'audit.title': 'Deep Audit Logs & Traceability',
      'audit.subtitle': 'Comprehensive recording of source IP, client device, user account, target host and audit trail',
      'audit.btn_refresh': 'Refresh',
      'audit.btn_refresh_title': 'Refresh audit logs',
      'audit.btn_export_csv': 'Export CSV',
      'audit.btn_export_csv_title': 'Export entire audit log to CSV',
      'audit.search_placeholder': 'Search by IP, account, device, Room ID, command...',
      'audit.action_all': 'All Actions',
      'audit.action_session_conn': 'Connect Host (SESSION_CONNECTED)',
      'audit.action_session_disc': 'Disconnect (SESSION_DISCONNECTED)',
      'audit.action_pin_failed': 'Wrong PIN (CONNECT_PIN_FAILED)',
      'audit.action_cmd': 'Terminal Command (CMD_EXEC)',
      'audit.action_file_browse': 'Browse Directory (FILE_BROWSE)',
      'audit.action_file_read': 'Open File Editor (FILE_READ)',
      'audit.action_file_save': 'Save File Directly (FILE_SAVE)',
      'audit.action_file_dl': 'Download File (FILE_DOWNLOAD)',
      'audit.action_file_ul': 'Upload File (FILE_UPLOAD)',
      'audit.action_file_del': 'Delete File (FILE_DELETE)',
      'audit.action_file_mkdir': 'Create Directory (FILE_MKDIR)',
      'audit.action_proc_kill': 'End Process (PROCESS_KILL)',
      'audit.action_power': 'Power/Lock Action (POWER_ACTION)',
      'audit.action_block_input': 'Block Host Input (BLOCK_INPUT)',
      'audit.action_clip_sync': 'Sync Clipboard (CLIPBOARD_SYNC)',
      'audit.action_auth_login': 'User Sign In',
      'audit.action_auth_reg': 'User Registration',
      'audit.action_dev_linked': 'Workstation Linked',
      'audit.th_time': 'Timestamp',
      'audit.th_action': 'Action',
      'audit.th_source': 'User & Source IP',
      'audit.th_target': 'Target Host',
      'audit.th_details': 'Business Details',
      'audit.loading': 'Loading audit logs...',
      'audit.empty': 'No matching audit logs found',
      'audit.anonymous': 'Anonymous',
      'audit.refreshed': 'Audit logs refreshed',
      'audit.exporting': 'Downloading audit log CSV file...',
      'audit.summary': 'Showing {showing} / {total} records',
      'audit.prev': 'Previous',
      'audit.next': 'Next',

      // Side Drawer (Shelf)
      'shelf.title': 'Files & Clipboard',
      'shelf.close_title': 'Close',
      'shelf.tab_files': 'Files',
      'shelf.tab_clipboard': 'Clip',
      'shelf.tab_chat': 'Chat',
      'shelf.btn_expand': 'Open Fullscreen File Explorer',
      'shelf.drop_text': 'Drag & drop files to send',
      'shelf.drop_sub': 'or click to browse files',
      'shelf.browse_title': 'Browse remote directories:',
      'shelf.btn_up': 'Parent folder ⇡',
      'shelf.drives_root': 'Drives',
      'shelf.no_conn': 'Connect to host to browse files',
      'shelf.clip_title': 'Clipboard content (Auto 2-way sync):',
      'shelf.clip_placeholder': 'No clipboard content yet...',
      'shelf.btn_push_clip': 'Push Clipboard',
      'shelf.btn_type_direct': 'Type Directly',
      'shelf.type_direct_title': 'Type Unicode text directly into active application (PowerPoint, Word, Notepad...)',
      'shelf.chat_title': 'Direct message to remote host user:',
      'shelf.chat_welcome': 'Live chat session with remote host',
      'shelf.chat_placeholder': 'Type a message...',
      'shelf.chat_send': 'Send',

      // Quick Connect Modal
      'qc.title': 'Connect via Room ID',
      'qc.subtitle': 'Enter Room ID and PIN to connect directly',
      'qc.relay_url': 'Relay Server URL',
      'qc.room_id': 'Room ID / Session Code',
      'qc.pin': 'Security PIN',
      'qc.btn_cancel': 'Cancel',
      'qc.btn_connect': 'Connect Now',

      // Online File Editor Modal
      'editor.saved': 'SAVED',
      'editor.dirty': '● MODIFIED (UNSAVED)',
      'editor.wrap': 'Word wrap',
      'editor.wrap_title': 'Toggle word wrap',
      'editor.btn_save': 'Save (Ctrl+S)',
      'editor.btn_save_title': 'Save directly to host disk (Ctrl + S)',
      'editor.btn_close_title': 'Close editor',
      'editor.path_title': 'File path on remote host',
      'editor.cursor': 'Line {line}, Col {col}',
      'editor.cursor_default': 'Line 1, Col 1',
      'editor.stats': '{lines} lines, {chars} characters',
      'editor.stats_default': '0 lines, 0 characters',
      'editor.unmodified': 'Unmodified',
      'editor.saved_at': 'Saved at {time}',
      'editor.saving': 'Saving...',
      'editor.read_error': 'Cannot open file: {error}',
      'editor.save_error': 'Error saving file: {error}',
      'editor.save_success': 'File saved successfully to host disk',
      'editor.discard_confirm': 'File has unsaved changes. Are you sure you want to discard them?',

      // Ambient Confirmation & Alert Dialog
      'dialog.confirm_title': 'Confirmation',
      'dialog.alert_title': 'Notice',
      'dialog.btn_confirm': 'Confirm',
      'dialog.btn_cancel': 'Cancel',
      'dialog.btn_ok': 'OK',
      'dialog.btn_delete': 'Delete',
      'dialog.btn_kill': 'Disconnect',
      'dialog.btn_discard': 'Discard changes',
      'dialog.btn_keep_editing': 'Keep editing',

      // Toasts & Alerts
      'toast.ws_error': 'Cannot connect WebSocket: {error}',
      'toast.connected': 'Connected successfully to host {room}!',
      'toast.disconnected': 'Disconnected from remote host',
      'toast.restart_success': 'Remote host rebooted and reconnected successfully!',
      'toast.generic_error': 'Error: {message}',
      'toast.kill_success': 'Terminated process PID {pid}',
      'toast.kill_failed': 'Failed to terminate process PID {pid}',
      'toast.file_delete_success': 'Deleted file/folder successfully',
      'toast.file_delete_failed': 'Could not delete (file is locked or permission denied)',
      'toast.mkdir_success': 'Created new folder successfully',
      'toast.mkdir_failed': 'Failed to create folder: {error}',
      'toast.upload_success': 'Uploaded file successfully: {filename}',
      'toast.upload_failed': 'File upload error: {error}',
      'toast.download_success': 'Downloaded file successfully: {filename}',
      'toast.clip_pushed': 'Pushed clipboard content to remote host',
      'toast.clip_empty': 'Clipboard is empty, please enter text',
      'toast.type_direct_done': 'Direct typing keystrokes dispatched to remote host',
      'toast.audio_started': 'Host audio streaming enabled',
      'toast.audio_stopped': 'Host audio streaming disabled',
      'toast.mic_started': 'Remote microphone intercom enabled',
      'toast.mic_stopped': 'Remote microphone intercom disabled',
      'toast.laser_on': 'Laser Pointer enabled (Mouse creates laser trail on host)',
      'toast.laser_off': 'Laser Pointer disabled',
      'toast.cam_on': 'Face Cam enabled (Webcam PiP)',
      'toast.cam_off': 'Face Cam disabled',
      'toast.cam_error': 'Failed to activate webcam: {error}',
      'toast.record_started': 'Session recording started',
      'toast.record_stopped': 'Session recording stopped. Video file is downloading...',
      'toast.screenshot_saved': 'Remote screenshot captured and downloaded',
      'toast.block_input_on': 'Blocked remote host keyboard and mouse input',
      'toast.block_input_off': 'Unblocked remote host keyboard and mouse input',

      // Landing Page
      'nav.home': 'Home',
      'ro.landing': 'HOME // OVERVIEW',
      'landing.badge': 'v2.5.0 // CROSS-PLATFORM // WINDOWS • LINUX • MACOS • IPADOS // MULTI-MONITOR',
      'landing.hero_title': 'PRECISION CROSS-PLATFORM REMOTE CONTROL',
      'landing.hero_subtitle': '120 FPS display, 2-way audio, multi-monitor grid layout, 3-mode smart deck, and secure remote control for Windows, macOS, and Linux workstations via Outbound Relay.',
      'landing.os_support_lbl': 'SUPPORTED WORKSTATIONS:',
      'landing.btn_start': 'Get Started',
      'landing.btn_dashboard': 'Go to Dashboard',
      'landing.btn_quick': 'Quick Connect',
      'landing.btn_download': 'Downloads',
      'landing.stat_latency': '< 15ms Latency',
      'landing.stat_fps': '60-120 FPS Stream',
      'landing.stat_monitors': 'Multi-Monitor Grid',
      'landing.stat_deck': '3-Mode Deck',
      'landing.stat_cross': 'Win • Linux • macOS',
      'landing.stat_audio': '2-Way Audio',
      'landing.stat_engine': 'Desktop Standalone',
      'landing.topo_client': 'LOCAL CLIENT',
      'landing.topo_client_meta': '0.8ms JITTER',
      'landing.topo_relay': 'MEIKOVA RELAY',
      'landing.topo_relay_meta': 'E2E TLS 1.3',
      'landing.topo_host': 'CROSS-PLATFORM WORKSTATIONS',
      'landing.topo_host_meta': 'WIN • LINUX • MACOS',

      // Landing Quick Connect Bar
      'landing.qc_title': 'Instant connection without installation',
      'landing.qc_room_placeholder': 'Enter Room ID (e.g. RD-4821)',
      'landing.qc_pin_placeholder': 'PIN (optional)',
      'landing.qc_btn_connect': 'Connect Now',

      // Landing Dual Architecture Modes
      'landing.modes_title': 'Flexible Dual Access Architecture',
      'landing.modes_subtitle': 'Perfect for both instant customer support and 24/7 personal workstation management',
      
      'landing.mode1_tag': 'ON-DEMAND REMOTE ASSIST',
      'landing.mode1_title': 'On-Demand Remote Assist Mode',
      'landing.mode1_desc': 'Fast on-demand remote support and troubleshooting without requiring any account login.',
      'landing.mode1_feat1': 'Random secure Room ID & 6-digit PIN generation',
      'landing.mode1_feat2': '1-click shareable invitation text with room details',
      'landing.mode1_feat3': 'Workstation user can emergency disconnect at any time',
      'landing.mode1_feat4': 'Run and connect immediately without tedious setup',

      'landing.mode2_tag': 'UNATTENDED 24/7 ACCESS',
      'landing.mode2_title': 'Unattended 24/7 Access Mode',
      'landing.mode2_desc': 'Continuous, stable, and secure remote access to your office or personal workstation.',
      'landing.mode2_feat1': 'Permanently linked to owner account',
      'landing.mode2_feat2': 'Auto-start on Windows / macOS / Linux boot',
      'landing.mode2_feat3': 'Anti-sleep keep-awake (Power Manager Awake API)',
      'landing.mode2_feat4': 'Minimizes to System Tray for 1-click background access',

      // Landing Studio Features
      'landing.features_title': 'Studio-Grade Control & Cross-Platform Capabilities',
      'landing.features_subtitle': 'Millisecond-optimized precision providing the sensation of sitting right at the workstation',
      'landing.feat_stream_title': '120 FPS & Multi-Monitor Grid Layout',
      'landing.feat_stream_desc': 'Instantly detects all connected displays. Drag-and-drop to arrange spatial positions matching physical setup, switch displays with 1 click, or view all screens at once.',
      'landing.feat_deck_title': '3-Mode Smart Floating Deck',
      'landing.feat_deck_desc': 'Choose your ideal layout: Bottom float, Top pinned, or Top unpinned with hover peek, completely freeing up the workstation taskbar and workspace.',
      'landing.feat_cross_title': 'Cross-Platform Host Agent (Win, Mac, Linux)',
      'landing.feat_cross_desc': 'Optimized host agents for Windows (Win32 API/Service 24/7), Linux (systemd daemon), and macOS (Launchd/Apple Silicon M1-M4) connecting seamlessly through Outbound Relay.',
      'landing.feat_audio_title': '2-Way Audio & Mic Talkback',
      'landing.feat_audio_desc': 'Crystal clear system audio via WebAudio PCM, with remote mic talkback directly to the workstation.',
      'landing.feat_term_title': 'Live Interactive Terminal',
      'landing.feat_term_desc': 'Direct real-time shell input (PowerShell / Bash / Zsh) and instant streaming output without needing remote desktop video.',
      'landing.feat_files_title': '2-Way File Manager & Live Editor',
      'landing.feat_files_desc': 'Browse all drives, drag-and-drop upload/download, and view/edit code files directly in the browser.',

      // Landing Download Hub
      'landing.dl_title': 'Cross-Platform Download & Deployment Hub',
      'landing.dl_subtitle': 'Choose the ideal deployment method for your remote workstation OS',
      'landing.dl_tab_win': 'Windows',
      'landing.dl_tab_linux': 'Linux',
      'landing.dl_tab_macos': 'macOS',
      'landing.dl_tab_web': 'Web & iPadOS',

      'landing.dl_exe_title': 'Standalone Desktop App (.exe)',
      'landing.dl_exe_desc': 'Fully bundled with Python Runtime, Tkinter, Pillow, and Websockets. Supports 2 options: Portable without Admin or 24/7 System Service with Admin.',
      'landing.dl_exe_btn': 'Download MeikovaRelayHost.exe (19.8 MB)',
      'landing.dl_exe_btn_title': 'Download MeikovaRelayHost.exe',
      'landing.dl_exe_btn_size': '(19.8 MB)',
      'landing.dl_exe_f1': '2 Options: User Portable & 24/7 Service',
      'landing.dl_exe_f2': 'Auto-run on boot & Anti-sleep',
      'landing.dl_exe_f3': 'Windows 10/11/Server (64-bit)',
      'landing.dl_bat_title': 'Automated Installer (.bat)',
      'landing.dl_bat_desc': 'Smart setup script linking to your account with auto-fallback to download the standalone .exe if Python is absent.',
      'landing.dl_bat_btn': 'Download Setup-MeikovaHost.bat',
      'landing.dl_bat_size': '(Auto-Config)',
      'landing.dl_bat_f1': 'Auto-links owner account',
      'landing.dl_bat_f2': 'Background 24/7 host service',
      'landing.dl_bat_f3': 'Auto-fallback EXE if Python missing',
      'landing.dl_ps1_title': 'One-Line Command (PowerShell)',
      'landing.dl_ps1_desc': 'Ideal for IT Admins and DevOps deploying across fleets with a single PowerShell command.',
      'landing.dl_ps1_copy': 'Copy PowerShell Command',
      'landing.dl_ps1_copy_btn': 'Copy PowerShell Command',
      'landing.dl_ps1_size': '(1-Click Copy)',
      'landing.dl_ps1_copied': 'Copied!',
      'landing.toast_copied': 'Install command copied to clipboard!',

      'landing.dl_linux_sh_title': '1-Line Command (Bash Script)',
      'landing.dl_linux_sh_desc': 'Automatically downloads agent package, sets up isolated Python venv, writes config, and starts daemon.',
      'landing.dl_linux_sh_copy': 'Copy Linux Command',
      'landing.dl_linux_sh_copy_btn': 'Copy Linux Command',
      'landing.dl_linux_sh_size': '(1-Click Copy)',
      'landing.dl_linux_deb_title': 'Debian / Ubuntu Package (.deb)',
      'landing.dl_linux_deb_desc': 'Native Debian/Ubuntu package with compiled binary, systemd daemon, and desktop entry.',
      'landing.dl_linux_deb_f1': '1-click install via: sudo dpkg -i',
      'landing.dl_linux_deb_f2': 'Auto-installs 24/7 systemd service',
      'landing.dl_linux_deb_f3': 'Ubuntu 20.04+, Debian 11+ 64-bit',
      'landing.dl_linux_deb_btn': 'Download meikova-relay.deb',
      'landing.dl_linux_tar_title': 'Standalone Linux Archive (.tar.gz)',
      'landing.dl_linux_tar_desc': 'Self-contained archive with ELF binary, systemd unit, and install.sh script.',
      'landing.dl_linux_tar_f1': 'Run directly without installation',
      'landing.dl_linux_tar_f2': 'Compatible with Fedora, Arch, RHEL',
      'landing.dl_linux_tar_f3': 'Includes universal source fallback',
      'landing.dl_linux_tar_btn': 'Download meikova-relay-linux.tar.gz',
      'landing.dl_linux_systemd_title': 'System Daemon (Systemd 24/7)',
      'landing.dl_linux_systemd_desc': 'Runs reliably as a background service via meikova-relay.service, auto-starting on OS boot and auto-restarting on failure.',
      'landing.dl_linux_systemd_f1': 'Auto-start on Linux boot (systemctl)',
      'landing.dl_linux_systemd_f2': 'Supports X11 & Wayland Screen Grab',
      'landing.dl_linux_systemd_f3': 'For Ubuntu, Debian, Arch, Fedora',
      'landing.dl_linux_headless_title': 'Headless Servers & Raspberry Pi',
      'landing.dl_linux_headless_desc': 'Runs smoothly on headless servers, ARM64 single-board computers, Raspberry Pi OS, and containers.',
      'landing.dl_linux_headless_f1': 'Optimized for ARM64 & x86_64',
      'landing.dl_linux_headless_f2': 'Remote management via Web Terminal & Files',
      'landing.dl_linux_headless_f3': 'Ultra-low memory footprint (< 50MB)',

      'landing.dl_macos_sh_title': '1-Line Command (macOS)',
      'landing.dl_macos_sh_desc': 'Automated setup script supporting macOS Monterey, Ventura, Sonoma, Sequoia (Intel & Apple Silicon M1-M4).',
      'landing.dl_macos_sh_copy': 'Copy macOS Command',
      'landing.dl_macos_sh_copy_btn': 'Copy macOS Command',
      'landing.dl_macos_sh_size': '(1-Click Copy)',
      'landing.dl_macos_apple_silicon_title': 'Apple Silicon & Intel Optimized',
      'landing.dl_macos_apple_silicon_desc': 'Leverages Quartz Screen Capture and Accessibility framework for smooth, pixel-accurate remote control.',
      'landing.dl_macos_apple_silicon_f1': 'Apple Silicon M1/M2/M3/M4 & Intel',
      'landing.dl_macos_apple_silicon_f2': 'Ultra-low capture latency',
      'landing.dl_macos_apple_silicon_f3': 'Requires Screen & Accessibility rights',
      'landing.dl_macos_tar_btn': 'Download meikova-relay-macos.tar.gz',
      'landing.dl_macos_guide_link': 'Security & Accessibility permission guide',
      'landing.dl_macos_launchd_title': 'Auto-Start Daemon (Launchd 24/7)',
      'landing.dl_macos_launchd_desc': 'Registers com.meikova.relay.plist in ~/Library/LaunchAgents to run automatically on macOS login.',
      'landing.dl_macos_launchd_f1': 'Auto-start via launchctl',
      'landing.dl_macos_launchd_f2': 'Silent background execution',
      'landing.dl_macos_launchd_f3': 'Firewall-friendly Outbound Relay',

      'landing.dl_web_title': 'Zero-Install Web Controller',
      'landing.dl_web_desc': 'No client app installation required. Open any web browser on desktop or tablet and access your workstations immediately.',
      'landing.dl_web_f1': 'Works on Chrome, Safari, Edge, Firefox',
      'landing.dl_web_f2': 'E2E encrypted via TLS 1.3 protocol',
      'landing.dl_web_f3': 'Responsive on 4G/5G and high-latency networks',
      'landing.dl_web_ipad_title': 'iPadOS & Tablet Touch Optimized',
      'landing.dl_web_ipad_desc': 'Full touch experience: Touch gestures, Apple Pencil Laser Pointer, virtual mousepad, and smooth pinch-to-zoom.',
      'landing.dl_web_ipad_f1': 'Supports tap, swipe, and pinch zoom',
      'landing.dl_web_ipad_f2': 'Laser Pointer for collaborative meetings',
      'landing.dl_web_ipad_f3': 'Dynamic portrait/landscape adaptation',
      'landing.dl_web_shortcuts_title': 'Virtual Keyboard & System Hotkeys',
      'landing.dl_web_shortcuts_desc': 'Built-in toolbar with essential workstation keys: Windows Key, Ctrl+Alt+Del, Alt+Tab, Esc, and multi-display toggles.',
      'landing.dl_web_shortcuts_f1': 'Emergency Ctrl+Alt+Del signal',
      'landing.dl_web_shortcuts_f2': 'Complete Windows / Command key set',
      'landing.dl_web_shortcuts_f3': 'Safety hotkey interception guard',

      // Landing CI/CD & Footer
      'landing.cicd_title': 'Automated GitHub Actions CI/CD Pipeline',
      'landing.cicd_desc': 'Every release is automatically compiled, tested, and packaged across isolated GitHub Actions runners (Windows, Ubuntu Linux, macOS), producing multi-platform packages (.exe, .deb, .tar.gz, .dmg) with verifiable SHA256 checksums.',
      'landing.footer_brand': 'MEIKOVA RELAY // AMBIENT INSTRUMENT SPECIFICATION',
      'landing.footer_status': 'SYSTEM: OPERATIONAL // RELAY: CLOUD-EDGE // E2E ENCRYPTED',

      // Session Activity & Inactivity Timeout
      'session.modal_title': 'Session Activity Settings',
      'session.modal_subtitle': 'Auto-disconnect and secure logout when idle or inactive',
      'session.remote_idle_label': 'Inactivity Disconnect Timeout (X min)',
      'session.remote_idle_hint': 'Auto-disconnects workstation remote session when mouse/keys are idle',
      'session.global_idle_label': 'Auto-Logout Timeout (Y min)',
      'session.global_idle_hint': 'Auto-logouts account when there is no active connection or user activity',
      'session.sliding_hint': 'Sliding session: Any user activity auto-refreshes token to prevent unexpected session drop.',
      'session.btn_cancel': 'Cancel',
      'session.btn_save': 'Save Settings',
      'session.toast_saved': 'Saved session settings: X={x} min, Y={y} min',
      'session.toast_remote_disconnected': 'Workstation session disconnected due to {min} min inactivity',
      'session.toast_global_logout': 'Account logged out due to {min} min inactivity',
      'topbar.session_cfg': 'Session',
      'topbar.session_cfg_title': 'Configure session timeouts (X/Y min)'
    }
  };

  let currentLang = DEFAULT_LANG;

  function getSupportedLangs() {
    return Object.keys(MESSAGES);
  }

  function getLang() {
    return currentLang;
  }

  function registerLang(code, messages) {
    if (!code || typeof code !== 'string') return;
    const cleanCode = code.toLowerCase().trim();
    MESSAGES[cleanCode] = Object.assign({}, MESSAGES[DEFAULT_LANG], messages);
  }

  function t(key, params = {}) {
    if (!key) return '';
    const langDict = MESSAGES[currentLang] || MESSAGES[DEFAULT_LANG];
    let template = langDict[key];
    if (template === undefined) {
      template = MESSAGES[DEFAULT_LANG][key];
    }
    if (template === undefined) {
      return key;
    }
    if (params && typeof params === 'object') {
      return template.replace(/\{(\w+)\}/g, function (match, p1) {
        return params[p1] !== undefined ? params[p1] : match;
      });
    }
    return template;
  }

  function applyTranslations(root = document) {
    if (!root) return;

    // 1. Text Content
    const textEls = root.querySelectorAll('[data-i18n]');
    for (let i = 0; i < textEls.length; i++) {
      const el = textEls[i];
      const key = el.getAttribute('data-i18n');
      if (key) {
        el.textContent = t(key);
      }
    }

    // 2. HTML Content (safe simple formatting)
    const htmlEls = root.querySelectorAll('[data-i18n-html]');
    for (let i = 0; i < htmlEls.length; i++) {
      const el = htmlEls[i];
      const key = el.getAttribute('data-i18n-html');
      if (key) {
        el.innerHTML = t(key);
      }
    }

    // 3. Title / Tooltips
    const titleEls = root.querySelectorAll('[data-i18n-title]');
    for (let i = 0; i < titleEls.length; i++) {
      const el = titleEls[i];
      const key = el.getAttribute('data-i18n-title');
      if (key) {
        el.title = t(key);
      }
    }

    // 4. Placeholders
    const phEls = root.querySelectorAll('[data-i18n-placeholder]');
    for (let i = 0; i < phEls.length; i++) {
      const el = phEls[i];
      const key = el.getAttribute('data-i18n-placeholder');
      if (key) {
        el.placeholder = t(key);
      }
    }

    // 5. Aria Labels
    const ariaEls = root.querySelectorAll('[data-i18n-aria]');
    for (let i = 0; i < ariaEls.length; i++) {
      const el = ariaEls[i];
      const key = el.getAttribute('data-i18n-aria');
      if (key) {
        el.setAttribute('aria-label', t(key));
      }
    }

    // 6. Update document lang attribute
    if (document.documentElement) {
      document.documentElement.lang = currentLang;
    }

    // 7. Synchronize Language Switcher UI buttons
    const langBtns = document.querySelectorAll('[data-lang-code]');
    for (let i = 0; i < langBtns.length; i++) {
      const btn = langBtns[i];
      btn.classList.toggle('on', btn.getAttribute('data-lang-code') === currentLang);
    }
    const langSwitch = document.getElementById('langSwitch');
    if (langSwitch && typeof window !== 'undefined' && typeof window.placeIndicator === 'function') {
      window.placeIndicator(langSwitch);
    }
  }

  function setLang(code, updateStorage = true) {
    if (!code) return currentLang;
    const cleanCode = code.toLowerCase().trim();
    if (MESSAGES[cleanCode]) {
      currentLang = cleanCode;
    } else {
      currentLang = DEFAULT_LANG;
    }

    if (updateStorage) {
      try {
        localStorage.setItem(STORAGE_KEY, currentLang);
      } catch (e) {
        // Ignore quota/private mode errors
      }
    }

    applyTranslations();

    // Dispatch global event for application listeners (dynamic re-renders)
    if (typeof window !== 'undefined' && window.dispatchEvent) {
      window.dispatchEvent(new CustomEvent('meikova-lang-changed', {
        detail: { lang: currentLang }
      }));
    }

    return currentLang;
  }

  function init() {
    // 1. Check URL query ?lang=...
    let initialLang = null;
    if (typeof window !== 'undefined' && window.location) {
      const params = new URLSearchParams(window.location.search);
      const urlLang = params.get('lang');
      if (urlLang && MESSAGES[urlLang.toLowerCase().trim()]) {
        initialLang = urlLang.toLowerCase().trim();
      }
    }

    // 2. Check LocalStorage if URL didn't specify
    if (!initialLang) {
      try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored && MESSAGES[stored.toLowerCase().trim()]) {
          initialLang = stored.toLowerCase().trim();
        }
      } catch (e) {}
    }

    // 3. Fallback to default ('vi')
    if (!initialLang) {
      initialLang = DEFAULT_LANG;
    }

    setLang(initialLang, false);

    // Bind click events on any language switcher buttons
    if (typeof document !== 'undefined') {
      document.addEventListener('click', function (e) {
        const btn = e.target.closest('[data-lang-code]');
        if (btn) {
          e.preventDefault();
          const targetCode = btn.getAttribute('data-lang-code');
          if (targetCode && targetCode !== currentLang) {
            setLang(targetCode, true);
          }
        }
      });
    }
  }

  // Auto-initialize when DOM is ready
  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', init);
    } else {
      init();
    }
  }

  return {
    DEFAULT_LANG,
    MESSAGES,
    getSupportedLangs,
    getLang,
    setLang,
    registerLang,
    t,
    applyTranslations,
    init
  };
});

# Hướng dẫn Thiết lập và Lấy Google OAuth Credentials

Tài liệu hướng dẫn chi tiết cách tạo và cấu hình `Client ID` & `Client Secret` từ **Google Cloud Console** để kích hoạt tính năng đăng nhập Google trên Meikova Relay (hỗ trợ Web, App Desktop Windows/macOS/Linux, và Cloud Relay Server).

---

## 📌 Tổng quan các thông số cấu hình cần thiết

Trước khi bắt đầu, hãy lưu lại các thông số Redirect URI và Origin mà Meikova Relay yêu cầu:

| Thông số | Giá trị Local (Chạy thử / Desktop) | Giá trị Production (Deploy Render) |
| :--- | :--- | :--- |
| **Loại ứng dụng (Application Type)** | `Web application` | `Web application` |
| **Authorized JavaScript origins** | `http://localhost:8080` | `https://<ten-app-cua-ban>.onrender.com` |
| **Authorized redirect URIs** | `http://localhost:8080/api/auth/google/callback` | `https://<ten-app-cua-ban>.onrender.com/api/auth/google/callback` |

> [!NOTE]
> Meikova Relay sử dụng kiến trúc **RFC 8252 (Loopback Browser Flow)** cho App Desktop, nên cả phiên bản Web lẫn Desktop đều dùng chung cấu hình **Web application** với redirect URI trỏ về server relay (`/api/auth/google/callback`).

---

## 🚀 HƯỚNG 1: Tạo mới trên Google Cloud Project chưa có sẵn (Bắt đầu từ số 0)

### Bước 1: Đăng nhập Google Cloud Console
1. Truy cập [Google Cloud Console](https://console.cloud.google.com/).
2. Đăng nhập bằng tài khoản Google của bạn.

### Bước 2: Tạo Project mới
1. Nhấp vào thanh chọn dự án ở góc trên bên trái (bên cạnh logo Google Cloud) → Chọn **New Project** (Dự án mới).
2. **Project name**: Đặt tên dự án (ví dụ: `Meikova Relay` hoặc `Meikova-Cluster`).
3. **Organization**: Để mặc định (hoặc chọn tổ chức của bạn nếu dùng Google Workspace).
4. Nhấn **Create** và chờ 5-10 giây để Google khởi tạo dự án.
5. Khi có thông báo hoàn tất, click chọn project vừa tạo để vào trang Dashboard của project đó.

### Bước 3: Cấu hình Màn hình đồng thuận (OAuth consent screen)
*(Google bắt buộc cấu hình bước này trước khi cho phép tạo Credentials)*

1. Trên menu bên trái (Icon ☰), chọn **APIs & Services** → **OAuth consent screen** (hoặc truy cập nhanh qua ô tìm kiếm).
2. **User Type**:
   - Chọn **External** (Khuyên dùng: Cho phép mọi tài khoản cá nhân Gmail hoặc bất kỳ ai đều đăng nhập được).
   - *(Chọn Internal nếu bạn dùng Google Workspace và chỉ muốn nhân viên trong công ty đăng nhập).*
3. Nhấn **Create**.
4. **Điền thông tin ứng dụng (App information)**:
   - **App name**: `Meikova Relay`
   - **User support email**: Chọn email của bạn.
   - **Developer contact information**: Điền email nhận thông báo của bạn.
   - Nhấn **Save and Continue**.
5. **Cấu hình Phạm vi quyền (Scopes)**:
   - Nhấn **Add or Remove Scopes**.
   - Tích chọn 3 quyền cơ bản:
     - `.../auth/userinfo.email`
     - `.../auth/userinfo.profile`
     - `openid`
   - Nhấn **Update** → Nhấn **Save and Continue**.
6. **Thêm tài khoản thử nghiệm (Test users)** *(Nếu App ở trạng thái Testing)*:
   - Nhấn **Add Users** → Điền địa chỉ Gmail của bạn và các tài khoản bạn sẽ dùng để đăng nhập test.
   - Nhấn **Add** → Nhấn **Save and Continue**.
7. Xem lại tóm tắt và nhấn **Back to Dashboard**.

### Bước 4: Tạo OAuth 2.0 Client ID
1. Trên menu bên trái, vào **APIs & Services** → **Credentials**.
2. Nhấp vào nút **+ CREATE CREDENTIALS** ở trên cùng → Chọn **OAuth client ID**.
3. **Application type**: Chọn **Web application**.
4. **Name**: Đặt tên nhận diện (ví dụ: `Meikova Relay Relay Client`).
5. **Authorized JavaScript origins**:
   - Nhấn **+ ADD URI** và thêm:
     - `http://localhost:8080`
     - `https://<ten-app-cua-ban>.onrender.com` *(nếu đã có domain Render)*
6. **Authorized redirect URIs**:
   - Nhấn **+ ADD URI** và thêm:
     - `http://localhost:8080/api/auth/google/callback`
     - `https://<ten-app-cua-ban>.onrender.com/api/auth/google/callback`
7. Nhấn **Create**.

### Bước 5: Tải file Credentials về máy
1. Một cửa sổ popup hiện ra hiển thị `Client ID` và `Client Secret`.
2. Nhấn nút **DOWNLOAD JSON** để tải file cấu hình về máy tính.
3. Đổi tên file vừa tải thành `client_secret.json`.

---

## ⚡ HƯỚNG 2: Tạo trên Google Cloud Project đã có sẵn

Nếu bạn đã có sẵn một Google Cloud Project từ trước:

### Bước 1: Chọn Project hiện có
1. Truy cập [Google Cloud Console](https://console.cloud.google.com/).
2. Nhấp vào danh sách chọn dự án ở thanh tiêu đề trên cùng → Chọn Project bạn muốn tích hợp.

### Bước 2: Kiểm tra OAuth Consent Screen
1. Vào menu **APIs & Services** → **OAuth consent screen**.
2. Kiểm tra trạng thái:
   - Nếu màn hình đồng thuận đã được tạo trước đó: Kiểm tra mục **Scopes** đã có `email`, `profile`, `openid` chưa. Nếu chưa có, chọn **Edit App** để bổ sung.
   - Nếu trạng thái là **Testing**: Đảm bảo email của bạn đã nằm trong danh sách **Test users**.

### Bước 3: Thêm Client ID mới
1. Vào mục **APIs & Services** → **Credentials**.
2. Nhấn **+ CREATE CREDENTIALS** → Chọn **OAuth client ID**.
3. **Application type**: Chọn **Web application**.
4. **Name**: Đặt tên (ví dụ: `Meikova Relay Client`).
5. Thêm các URL:
   - **Authorized JavaScript origins**:
     - `http://localhost:8080`
     - `https://<ten-app-cua-ban>.onrender.com`
   - **Authorized redirect URIs**:
     - `http://localhost:8080/api/auth/google/callback`
     - `https://<ten-app-cua-ban>.onrender.com/api/auth/google/callback`
6. Nhấn **Create**.
7. Nhấn **DOWNLOAD JSON** để tải file về, đổi tên thành `client_secret.json`.

---

## 📂 Cách đưa Credentials vào Meikova Relay

Sau khi đã có file hoặc thông tin `Client ID` / `Client Secret`, bạn áp dụng vào dự án theo 1 trong các cách sau:

### Cách 1: Bỏ file vào thư mục `data/` (Dành cho Dev Local & Desktop)
- Di chuyển file `client_secret.json` vào thư mục:
  ```
  meikova-relay/
  ├── data/
  │   └── client_secret.json   <-- Đặt ở đây
  ```
- *Thư mục `data/` đã được cấu hình trong `.gitignore`, bạn hoàn toàn yên tâm push git mà không lo bị lộ mã bí mật.*

### Cách 2: Cấu hình trên Render (Production Cloud)
- Truy cập vào **Render Dashboard** → Chọn Web Service `meikova-relay`.
- Mở tab **Environment** → Chọn **Add Environment Variable**:
  - `GOOGLE_CLIENT_ID` = `...apps.googleusercontent.com`
  - `GOOGLE_CLIENT_SECRET` = `GOCSPX-...`
- Nhấn **Save Changes**. Server sẽ tự khởi động lại và nhận diện ngay.

---

## 🛠️ Các lỗi phổ biến & Cách khắc phục (Troubleshooting)

### 1. Lỗi `redirect_uri_mismatch` (Lỗi 400)
- **Nguyên nhân**: URI gọi đến Google không khớp 100% với URI đã khai báo trên Google Cloud Console.
- **Khắc phục**: 
  - Kiểm tra từng ký tự, cổng mạng (port 8080) và giao thức (`http` cho local, `https` cho render).
  - Đảm bảo có đường dẫn `/api/auth/google/callback` ở cuối.

### 2. Lỗi `Access blocked: This app's request is invalid` hoặc `403: access_denied`
- **Nguyên nhân**: App đang ở chế độ **Testing** và tài khoản Google bạn dùng để đăng nhập chưa được cấp quyền thử nghiệm.
- **Khắc phục**: Vào Google Cloud Console → **OAuth consent screen** → Kéo xuống mục **Test users** → Nhấn **+ ADD USERS** → Thêm địa chỉ Gmail của bạn vào.

### 3. Vừa thêm URI nhưng đăng nhập vẫn báo lỗi URI mismatch
- **Nguyên nhân**: Google Cloud cần thời gian phân bổ cấu hình mới đến các máy chủ DNS/OAuth toàn cầu.
- **Khắc phục**: Chờ từ **2 đến 5 phút** sau khi nhấn Save trên Google Cloud Console rồi thử lại.

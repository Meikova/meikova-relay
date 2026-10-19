const http = require('http');
const fs = require('fs');
const path = require('path');
const { WebSocketServer, WebSocket } = require('ws');
const DB = require('./db');

const PORT = process.env.PORT || 8080;
const WEB_CLIENT_DIR = path.join(__dirname, '..', 'web-client');

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon'
};

function getClientIp(req) {
  if (!req) return '127.0.0.1';
  const fwd = req.headers['x-forwarded-for'];
  if (fwd) {
    const parts = fwd.split(',').map(s => s.trim());
    if (parts.length > 0 && parts[0]) return parts[0].replace(/^::ffff:/, '');
  }
  const realIp = req.headers['x-real-ip'];
  if (realIp) return realIp.replace(/^::ffff:/, '');
  const addr = req.socket?.remoteAddress || req.connection?.remoteAddress || '127.0.0.1';
  return addr.replace(/^::ffff:/, '');
}

function parseClientDevice(ua) {
  if (!ua) return 'Không xác định';
  let os = 'Khác';
  if (/windows nt 10/i.test(ua)) os = 'Windows 10/11';
  else if (/windows nt 6\.3/i.test(ua)) os = 'Windows 8.1';
  else if (/windows nt 6\.1/i.test(ua)) os = 'Windows 7';
  else if (/windows/i.test(ua)) os = 'Windows';
  else if (/iphone/i.test(ua)) os = 'iPhone iOS';
  else if (/ipad/i.test(ua)) os = 'iPadOS';
  else if (/macintosh|mac os x/i.test(ua)) os = 'macOS';
  else if (/android/i.test(ua)) os = 'Android';
  else if (/linux/i.test(ua)) os = 'Linux';

  let browser = 'Browser';
  if (/edg/i.test(ua)) browser = 'Edge';
  else if (/opr|opera/i.test(ua)) browser = 'Opera';
  else if (/chrome|crios/i.test(ua)) browser = 'Chrome';
  else if (/firefox|fxios/i.test(ua)) browser = 'Firefox';
  else if (/safari/i.test(ua)) browser = 'Safari';

  return `${os} // ${browser}`;
}

function parseBody(req) {
  return new Promise((resolve) => {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => {
      try {
        resolve(JSON.parse(body || '{}'));
      } catch {
        resolve({});
      }
    });
  });
}

function jsonResponse(res, status, data) {
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization'
  });
  res.end(JSON.stringify(data));
}

// HTTP Server: Serves REST API and Web Client files
const server = http.createServer(async (req, res) => {
  // CORS Preflight
  if (req.method === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization'
    });
    res.end();
    return;
  }

  const url = new URL(req.url, `http://${req.headers.host}`);
  const pathname = url.pathname;

  // --- REST API ROUTES ---
  if (pathname.startsWith('/api/')) {
    // 1. Auth: Register
    if (pathname === '/api/auth/register' && req.method === 'POST') {
      const { username, password } = await parseBody(req);
      const clientIp = getClientIp(req);
      const clientDevice = parseClientDevice(req.headers['user-agent']);
      try {
        const user = DB.registerUser(username, password);
        const auth = DB.authenticateUser(username, password);
        DB.logAudit({
          action: 'AUTH_REGISTER',
          userId: user.id,
          username: user.username,
          clientIp,
          clientDevice,
          details: { status: 'success' }
        });
        return jsonResponse(res, 201, { success: true, token: auth.token, user: auth.user });
      } catch (err) {
        DB.logAudit({
          action: 'AUTH_REGISTER_FAILED',
          username: username || 'Unknown',
          clientIp,
          clientDevice,
          details: { status: 'failed', reason: err.message }
        });
        return jsonResponse(res, 400, { success: false, message: err.message });
      }
    }

    // 2. Auth: Login
    if (pathname === '/api/auth/login' && req.method === 'POST') {
      const { username, password } = await parseBody(req);
      const clientIp = getClientIp(req);
      const clientDevice = parseClientDevice(req.headers['user-agent']);
      const auth = DB.authenticateUser(username, password);
      if (!auth) {
        DB.logAudit({
          action: 'AUTH_LOGIN_FAILED',
          username: username || 'Unknown',
          clientIp,
          clientDevice,
          details: { status: 'failed', reason: 'Sai tên đăng nhập hoặc mật khẩu' }
        });
        return jsonResponse(res, 401, { success: false, message: 'Sai tên đăng nhập hoặc mật khẩu' });
      }
      DB.logAudit({
        action: 'AUTH_LOGIN',
        userId: auth.user.id,
        username: auth.user.username,
        clientIp,
        clientDevice,
        details: { status: 'success', method: 'password' }
      });
      return jsonResponse(res, 200, { success: true, token: auth.token, user: auth.user });
    }

    // 2.5 Auth: Google Sign-In
    if (pathname === '/api/auth/google' && req.method === 'POST') {
      const { credential } = await parseBody(req);
      const clientIp = getClientIp(req);
      const clientDevice = parseClientDevice(req.headers['user-agent']);
      if (!credential) {
        return jsonResponse(res, 400, { success: false, message: 'Missing Google credential' });
      }
      try {
        // Decode JWT payload (Google ID token is a standard JWT)
        const parts = credential.split('.');
        const payload = JSON.parse(Buffer.from(parts[1], 'base64url').toString());
        const email = payload.email;
        const name = payload.name || email.split('@')[0];
        
        if (!email) {
          return jsonResponse(res, 400, { success: false, message: 'Token không hợp lệ' });
        }
        
        // Auto-register or login by email
        const auth = DB.googleAuth(email, name);
        DB.logAudit({
          action: 'AUTH_GOOGLE',
          userId: auth.user.id,
          username: auth.user.username,
          clientIp,
          clientDevice,
          details: { status: 'success', email }
        });
        return jsonResponse(res, 200, { success: true, token: auth.token, user: auth.user });
      } catch (err) {
        return jsonResponse(res, 400, { success: false, message: 'Google token không hợp lệ: ' + err.message });
      }
    }

    // Auth Middleware for protected endpoints
    const authHeader = req.headers['authorization'] || '';
    const token = authHeader.replace(/^Bearer\s+/i, '').trim();
    const session = DB.validateSession(token);

    // 3. Auth: Current User
    if (pathname === '/api/auth/me' && req.method === 'GET') {
      if (!session) {
        return jsonResponse(res, 401, { success: false, message: 'Chưa đăng nhập' });
      }
      return jsonResponse(res, 200, { success: true, user: session });
    }

    // 4. Devices: List for logged-in user
    if (pathname === '/api/devices' && req.method === 'GET') {
      if (!session) {
        return jsonResponse(res, 401, { success: false, message: 'Yêu cầu đăng nhập' });
      }
      const devices = DB.getDevices(session.id);
      return jsonResponse(res, 200, { success: true, devices });
    }

    // 5. Devices: Link a device to account
    if (pathname === '/api/devices/link' && req.method === 'POST') {
      if (!session) {
        return jsonResponse(res, 401, { success: false, message: 'Yêu cầu đăng nhập' });
      }
      const { roomId, pin, deviceName } = await parseBody(req);
      if (!roomId || !pin) {
        return jsonResponse(res, 400, { success: false, message: 'Thiếu Room ID hoặc PIN' });
      }
      DB.upsertDevice({
        userId: session.id,
        roomId,
        pin,
        deviceName: deviceName || 'Workstation'
      });
      DB.logAudit({
        action: 'DEVICE_LINKED',
        userId: session.id,
        username: session.username,
        clientIp: getClientIp(req),
        clientDevice: parseClientDevice(req.headers['user-agent']),
        roomId,
        targetDevice: deviceName,
        details: { roomId, deviceName }
      });
      return jsonResponse(res, 200, { success: true, message: 'Đã liên kết thiết bị thành công' });
    }

    // 5.5 Audit Logs: Query
    if (pathname === '/api/audit-logs' && req.method === 'GET') {
      if (!session) {
        return jsonResponse(res, 401, { success: false, message: 'Yêu cầu đăng nhập' });
      }
      const limit = parseInt(url.searchParams.get('limit') || '50', 10);
      const offset = parseInt(url.searchParams.get('offset') || '0', 10);
      const action = url.searchParams.get('action') || null;
      const roomId = url.searchParams.get('roomId') || null;
      const search = url.searchParams.get('search') || null;

      const result = DB.getAuditLogs({ limit, offset, action, roomId, search });
      return jsonResponse(res, 200, { success: true, ...result });
    }

    // 5.6 Audit Logs: Export
    if (pathname === '/api/audit-logs/export' && req.method === 'GET') {
      if (!session) {
        return jsonResponse(res, 401, { success: false, message: 'Yêu cầu đăng nhập' });
      }
      const format = url.searchParams.get('format') || 'csv';
      const action = url.searchParams.get('action') || null;
      const roomId = url.searchParams.get('roomId') || null;
      const search = url.searchParams.get('search') || null;
      const { logs } = DB.getAuditLogs({ limit: 5000, offset: 0, action, roomId, search });

      if (format === 'json') {
        res.writeHead(200, {
          'Content-Type': 'application/json; charset=utf-8',
          'Content-Disposition': 'attachment; filename="titan-audit-logs.json"'
        });
        return res.end(JSON.stringify(logs, null, 2));
      }

      const headers = ['ID', 'Thời gian', 'Hành động', 'Người dùng', 'IP Nguồn', 'Thiết bị Nguồn', 'Room ID', 'Máy đích', 'HĐH Đích', 'Chi tiết'];
      const rows = logs.map(l => [
        l.id,
        new Date(l.timestamp).toLocaleString('vi-VN'),
        `"${(l.action || '').replace(/"/g, '""')}"`,
        `"${(l.username || '').replace(/"/g, '""')}"`,
        l.client_ip,
        `"${(l.client_device || '').replace(/"/g, '""')}"`,
        l.room_id || '',
        `"${(l.target_device || '').replace(/"/g, '""')}"`,
        `"${(l.target_os || '').replace(/"/g, '""')}"`,
        `"${(l.details || '').replace(/"/g, '""')}"`
      ].join(','));
      const csvContent = '\uFEFF' + [headers.join(','), ...rows].join('\r\n');
      res.writeHead(200, {
        'Content-Type': 'text/csv; charset=utf-8',
        'Content-Disposition': 'attachment; filename="titan-audit-logs.csv"'
      });
      return res.end(csvContent);
    }

    // 6. Download: Pre-configured Setup Batch Script
    if (pathname === '/api/download/setup.bat' && req.method === 'GET') {
      const account = url.searchParams.get('account') || (session ? session.username : 'User');
      const origin = `${req.headers['x-forwarded-proto'] || 'http'}://${req.headers.host}`;
      const relayWs = (url.searchParams.get('relay') || origin.replace(/^http/, 'ws'));

      const batContent = `@echo off
setlocal EnableDelayedExpansion
title Titan Remote Host - Cai dat may tram tu dong
echo ==============================================================
echo        TITAN REMOTE ENTERPRISE - TU DONG LIEN KET MAY TRAM
echo ==============================================================
echo Tai khoan lien ket: ${account}
echo Relay Server:       ${relayWs}
echo.

set "TARGET_DIR=%LOCALAPPDATA%\\TitanRemoteHost"
if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%"
cd /d "%TARGET_DIR%"

echo [1/5] Kiem tra moi truong Python...
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Python chua duoc cai dat. Dang thu cai dat Python qua winget...
    winget install Python.Python.3.13 --silent --accept-source-agreements --accept-package-agreements >nul 2>&1
)

echo [2/5] Dang tai ma nguon Host Agent tu Relay Server...
powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile('${origin}/api/download/agent-package.zip', 'agent-package.zip')"
if exist "agent-package.zip" (
    powershell -Command "Expand-Archive -Path 'agent-package.zip' -DestinationPath '.' -Force"
    del agent-package.zip >nul 2>&1
    if exist "host_agent\\gui_agent.py" copy /y host_agent\\*.py . >nul 2>&1
) else (
    echo [!] Khong the tai goi agent-package.zip. Kiem tra ket noi mang.
    pause
    exit /b 1
)

echo [3/5] Khoi tao Virtual Environment (.venv) va cai dat thu vien...
if not exist ".venv\\Scripts\\python.exe" (
    python -m venv .venv
)
if exist "requirements.txt" (
    ".venv\\Scripts\\python.exe" -m pip install -r requirements.txt --quiet
) else if exist "host_agent\\requirements.txt" (
    ".venv\\Scripts\\python.exe" -m pip install -r host_agent\\requirements.txt --quiet
)

echo [4/5] Ghi cau hinh lien ket voi tai khoan ${account}...
set "RAND_ROOM=RD-%RANDOM%"
set "RAND_PIN=%RANDOM%%RANDOM%"
(
echo {
echo   "relay": "${relayWs}",
echo   "account": "${account}",
echo   "device_name": "%COMPUTERNAME%",
echo   "room_id": "!RAND_ROOM!",
echo   "pin": "!RAND_PIN!"
echo }
) > config.json

echo [5/5] Dang ky tu dong khoi dong cung Windows (Auto-start on Boot / Restart)...
reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" /v "TitanRemoteHost" /t REG_SZ /d "\"%TARGET_DIR%\\.venv\\Scripts\\pythonw.exe\" \"%TARGET_DIR%\\gui_agent.py\" --autostart" /f >nul 2>&1

echo.
echo ==============================================================
echo   DA KET NOI VA LIEN KET VOI TAI KHOAN ${account}!
echo   Room ID: !RAND_ROOM!  ^|  PIN: !RAND_PIN!
echo   Dang khoi chay Host Agent trong che do ngam...
echo ==============================================================
start "" ".venv\\Scripts\\pythonw.exe" "gui_agent.py" --autostart
echo May tram dang hoat dong ngam. Vao Dashboard tren Web de ket noi 1-click!
timeout /t 5
`;

      res.writeHead(200, {
        'Content-Type': 'application/x-bat; charset=utf-8',
        'Content-Disposition': 'attachment; filename="Setup-TitanHost.bat"',
        'Cache-Control': 'no-cache'
      });
      res.end(batContent);
      return;
    }

    // 7. Download: Agent Package Zip
    if (pathname === '/api/download/agent-package.zip' && req.method === 'GET') {
      const zipPath = path.join(__dirname, 'agent-package.zip');
      if (fs.existsSync(zipPath)) {
        res.writeHead(200, {
          'Content-Type': 'application/zip',
          'Content-Disposition': 'attachment; filename="agent-package.zip"',
          'Cache-Control': 'no-cache'
        });
        fs.createReadStream(zipPath).pipe(res);
        return;
      }
      return jsonResponse(res, 404, { error: 'Agent package zip not found' });
    }

    return jsonResponse(res, 404, { error: 'API endpoint not found' });
  }

  // --- STATIC FILE SERVER (Web Client) ---
  let reqPath = pathname;
  if (reqPath === '/' || reqPath === '') {
    reqPath = '/index.html';
  }

  const safePath = path.normalize(reqPath).replace(/^(\.\.[\/\\])+/, '');
  const filePath = path.join(WEB_CLIENT_DIR, safePath);

  fs.stat(filePath, (err, stats) => {
    if (err || !stats.isFile()) {
      // SPA Fallback: Serve index.html for application routes without file extensions
      if (!pathname.startsWith('/api/') && !path.extname(pathname)) {
        const indexPath = path.join(WEB_CLIENT_DIR, 'index.html');
        res.writeHead(200, {
          'Content-Type': 'text/html; charset=utf-8',
          'Cache-Control': 'no-cache, no-store, must-revalidate'
        });
        fs.createReadStream(indexPath).pipe(res);
        return;
      }

      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end('404 Not Found - Titan Remote Client');
      return;
    }

    const ext = path.extname(filePath).toLowerCase();
    const contentType = MIME_TYPES[ext] || 'application/octet-stream';

    res.writeHead(200, {
      'Content-Type': contentType,
      'Cache-Control': 'no-cache, no-store, must-revalidate'
    });
    fs.createReadStream(filePath).pipe(res);
  });
});

// WebSocket Relay Server
const wss = new WebSocketServer({ server });
const rooms = new Map();

function getOrCreateRoom(roomId) {
  if (!rooms.has(roomId)) {
    rooms.set(roomId, {
      pin: null,
      hostWs: null,
      clientWs: null,
      hostMeta: null
    });
  }
  return rooms.get(roomId);
}

wss.on('connection', (ws, req) => {
  let role = null;
  let currentRoomId = null;

  ws.isAlive = true;
  ws.clientIp = getClientIp(req);
  ws.clientDevice = parseClientDevice(req.headers['user-agent']);
  ws.connectTime = Date.now();
  ws.username = 'Khách (Ẩn danh)';
  ws.userId = null;

  ws.on('pong', () => { ws.isAlive = true; });

  ws.on('message', (message, isBinary) => {
    // 1. Forward raw binary frames (Screen frames or file chunks)
    if (isBinary) {
      if (role === 'host' && currentRoomId) {
        const room = rooms.get(currentRoomId);
        if (room && room.clientWs && room.clientWs.readyState === WebSocket.OPEN) {
          room.clientWs.send(message, { binary: true });
        }
      } else if (role === 'client' && currentRoomId) {
        const room = rooms.get(currentRoomId);
        if (room && room.hostWs && room.hostWs.readyState === WebSocket.OPEN) {
          room.hostWs.send(message, { binary: true });
        }
      }
      return;
    }

    // 2. Control & Input Messages (JSON)
    let data;
    try {
      data = JSON.parse(message.toString());
    } catch {
      return;
    }

    const type = data.type;

    // --- Host Handshake ---
    if (type === 'init_host') {
      const roomId = String(data.room_id || '').trim();
      const pin = String(data.pin || '').trim();
      if (!roomId || !pin) {
        ws.send(JSON.stringify({ status: 'error', message: 'Missing room_id or pin' }));
        ws.close();
        return;
      }

      role = 'host';
      currentRoomId = roomId;
      const room = getOrCreateRoom(roomId);
      room.pin = pin;
      room.hostWs = ws;
      room.hostMeta = {
        width: data.width || 1920,
        height: data.height || 1080,
        deviceName: data.device_name || 'Host-PC',
        osInfo: data.os_info || 'Windows',
        monitors: data.monitors || []
      };

      // Register device in DB
      let targetUserId = data.user_id || null;
      if (!targetUserId && (data.account || data.user_email)) {
        const matchedUser = DB.getUserByUsername(data.account || data.user_email);
        if (matchedUser) {
          targetUserId = matchedUser.id;
        }
      }

      DB.upsertDevice({
        userId: targetUserId,
        deviceName: room.hostMeta.deviceName,
        roomId: roomId,
        pin: pin,
        resolution: `${room.hostMeta.width}x${room.hostMeta.height}`,
        osInfo: room.hostMeta.osInfo
      });

      DB.logAudit({
        action: 'HOST_ONLINE',
        roomId,
        clientIp: ws.clientIp,
        clientDevice: ws.clientDevice,
        targetDevice: room.hostMeta.deviceName,
        targetOs: room.hostMeta.osInfo,
        details: { width: data.width, height: data.height, monitors: (data.monitors || []).length }
      });

      console.log(`[Host Online] Room: ${roomId} | Device: ${room.hostMeta.deviceName} | IP: ${ws.clientIp}`);
      ws.send(JSON.stringify({ status: 'ok', role: 'host', room_id: roomId }));

      if (room.clientWs && room.clientWs.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'client_connected' }));
        room.clientWs.send(JSON.stringify({
          type: 'host_ready',
          width: room.hostMeta.width,
          height: room.hostMeta.height,
          deviceName: room.hostMeta.deviceName,
          monitors: room.hostMeta.monitors
        }));
      }
      return;
    }

    // --- Client Handshake ---
    if (type === 'init_client') {
      const roomId = String(data.room_id || '').trim();
      const pin = String(data.pin || '').trim();
      const room = rooms.get(roomId);

      if (data.token) {
        const sess = DB.validateSession(data.token);
        if (sess) {
          ws.username = sess.username;
          ws.userId = sess.id;
        }
      } else if (data.username) {
        ws.username = data.username;
      }

      if (!room || !room.hostWs || room.hostWs.readyState !== WebSocket.OPEN) {
        DB.logAudit({
          action: 'CONNECT_FAILED_OFFLINE',
          userId: ws.userId,
          username: ws.username,
          clientIp: ws.clientIp,
          clientDevice: ws.clientDevice,
          roomId,
          details: { status: 'failed', reason: 'Máy trạm đang Offline' }
        });
        ws.send(JSON.stringify({ status: 'error', message: 'Máy trạm đang Offline hoặc không tồn tại' }));
        return;
      }

      if (room.pin && room.pin !== pin) {
        DB.logAudit({
          action: 'CONNECT_PIN_FAILED',
          userId: ws.userId,
          username: ws.username,
          clientIp: ws.clientIp,
          clientDevice: ws.clientDevice,
          roomId,
          targetDevice: room.hostMeta?.deviceName,
          targetOs: room.hostMeta?.osInfo,
          details: { status: 'failed', reason: 'Sai mã PIN bảo mật' }
        });
        ws.send(JSON.stringify({ status: 'error', message: 'Mã PIN bảo mật không chính xác' }));
        return;
      }

      role = 'client';
      currentRoomId = roomId;
      room.clientWs = ws;

      DB.logAudit({
        action: 'SESSION_CONNECTED',
        userId: ws.userId,
        username: ws.username,
        clientIp: ws.clientIp,
        clientDevice: ws.clientDevice,
        roomId,
        targetDevice: room.hostMeta?.deviceName,
        targetOs: room.hostMeta?.osInfo,
        details: { status: 'connected', resolution: `${room.hostMeta?.width}x${room.hostMeta?.height}` }
      });

      console.log(`[Client Connected] Room: ${roomId} | User: ${ws.username} | IP: ${ws.clientIp} | Device: ${ws.clientDevice}`);
      ws.send(JSON.stringify({
        status: 'ok',
        role: 'client',
        room_id: roomId,
        hostMeta: room.hostMeta
      }));

      room.hostWs.send(JSON.stringify({ type: 'client_connected' }));
      return;
    }

    // --- Ping / Pong ---
    if (type === 'ping') {
      ws.send(JSON.stringify({ type: 'pong', ts: data.ts }));
      return;
    }

    // --- Deep Operation Audit Logging (From Client to Host) ---
    if (role === 'client' && currentRoomId) {
      const room = rooms.get(currentRoomId);
      const targetDevice = room?.hostMeta?.deviceName || 'Host-PC';
      const targetOs = room?.hostMeta?.osInfo || 'Windows';

      if (type === 'terminal_input') {
        DB.logAudit({
          action: 'CMD_EXEC',
          userId: ws.userId,
          username: ws.username,
          clientIp: ws.clientIp,
          clientDevice: ws.clientDevice,
          roomId: currentRoomId,
          targetDevice,
          targetOs,
          details: { command: (data.input || data.cmd || '').trim() }
        });
      } else if (type === 'file_browse_request') {
        DB.logAudit({
          action: 'FILE_BROWSE',
          userId: ws.userId,
          username: ws.username,
          clientIp: ws.clientIp,
          clientDevice: ws.clientDevice,
          roomId: currentRoomId,
          targetDevice,
          targetOs,
          details: { path: data.path || '' }
        });
      } else if (type === 'file_download_request') {
        DB.logAudit({
          action: 'FILE_DOWNLOAD',
          userId: ws.userId,
          username: ws.username,
          clientIp: ws.clientIp,
          clientDevice: ws.clientDevice,
          roomId: currentRoomId,
          targetDevice,
          targetOs,
          details: { path: data.path || '', filename: data.filename || '' }
        });
      } else if (type === 'file_upload_start') {
        DB.logAudit({
          action: 'FILE_UPLOAD',
          userId: ws.userId,
          username: ws.username,
          clientIp: ws.clientIp,
          clientDevice: ws.clientDevice,
          roomId: currentRoomId,
          targetDevice,
          targetOs,
          details: { filename: data.filename, size: data.total_size, path: data.dest_path }
        });
      } else if (type === 'file_delete_request') {
        DB.logAudit({
          action: 'FILE_DELETE',
          userId: ws.userId,
          username: ws.username,
          clientIp: ws.clientIp,
          clientDevice: ws.clientDevice,
          roomId: currentRoomId,
          targetDevice,
          targetOs,
          details: { path: data.path || '' }
        });
      } else if (type === 'file_create_folder_request') {
        DB.logAudit({
          action: 'FILE_MKDIR',
          userId: ws.userId,
          username: ws.username,
          clientIp: ws.clientIp,
          clientDevice: ws.clientDevice,
          roomId: currentRoomId,
          targetDevice,
          targetOs,
          details: { path: data.path || '', folderName: data.name || '' }
        });
      } else if (type === 'process_kill_request') {
        DB.logAudit({
          action: 'PROCESS_KILL',
          userId: ws.userId,
          username: ws.username,
          clientIp: ws.clientIp,
          clientDevice: ws.clientDevice,
          roomId: currentRoomId,
          targetDevice,
          targetOs,
          details: { pid: data.pid, name: data.name || '' }
        });
      } else if (type === 'power_action') {
        DB.logAudit({
          action: 'POWER_ACTION',
          userId: ws.userId,
          username: ws.username,
          clientIp: ws.clientIp,
          clientDevice: ws.clientDevice,
          roomId: currentRoomId,
          targetDevice,
          targetOs,
          details: { action: data.action }
        });
      } else if (type === 'block_input') {
        DB.logAudit({
          action: 'BLOCK_INPUT',
          userId: ws.userId,
          username: ws.username,
          clientIp: ws.clientIp,
          clientDevice: ws.clientDevice,
          roomId: currentRoomId,
          targetDevice,
          targetOs,
          details: { blocked: !!data.blocked }
        });
      } else if (type === 'clipboard_sync') {
        DB.logAudit({
          action: 'CLIPBOARD_SYNC',
          userId: ws.userId,
          username: ws.username,
          clientIp: ws.clientIp,
          clientDevice: ws.clientDevice,
          roomId: currentRoomId,
          targetDevice,
          targetOs,
          details: { length: (data.text || '').length }
        });
      }
    }

    // --- Forward Bidirectional Control / Inputs / Files / Clipboard ---
    if (role === 'client' && currentRoomId) {
      const room = rooms.get(currentRoomId);
      if (room && room.hostWs && room.hostWs.readyState === WebSocket.OPEN) {
        room.hostWs.send(message.toString());
      }
    } else if (role === 'host' && currentRoomId) {
      const room = rooms.get(currentRoomId);
      if (room && room.clientWs && room.clientWs.readyState === WebSocket.OPEN) {
        room.clientWs.send(message.toString());
      }
    }
  });

  ws.on('close', () => {
    if (currentRoomId && rooms.has(currentRoomId)) {
      const room = rooms.get(currentRoomId);
      if (role === 'host') {
        console.log(`[Host Offline] Room: ${currentRoomId}`);
        DB.logAudit({
          action: 'HOST_OFFLINE',
          roomId: currentRoomId,
          clientIp: ws.clientIp,
          clientDevice: ws.clientDevice,
          targetDevice: room?.hostMeta?.deviceName,
          targetOs: room?.hostMeta?.osInfo,
          details: { status: 'offline' }
        });
        room.hostWs = null;
        DB.setDeviceOnlineStatus(currentRoomId, false);
        if (room.clientWs && room.clientWs.readyState === WebSocket.OPEN) {
          room.clientWs.send(JSON.stringify({ type: 'host_disconnected', message: 'Máy trạm đã ngắt kết nối' }));
        }
      } else if (role === 'client') {
        console.log(`[Client Disconnected] Room: ${currentRoomId}`);
        const durationSec = Math.round((Date.now() - (ws.connectTime || Date.now())) / 1000);
        DB.logAudit({
          action: 'SESSION_DISCONNECTED',
          userId: ws.userId,
          username: ws.username,
          clientIp: ws.clientIp,
          clientDevice: ws.clientDevice,
          roomId: currentRoomId,
          targetDevice: room?.hostMeta?.deviceName,
          targetOs: room?.hostMeta?.osInfo,
          details: { durationSec, durationText: `${durationSec}s` }
        });
        room.clientWs = null;
        if (room.hostWs && room.hostWs.readyState === WebSocket.OPEN) {
          room.hostWs.send(JSON.stringify({ type: 'client_disconnected' }));
        }
      }

      if (!room.hostWs && !room.clientWs) {
        rooms.delete(currentRoomId);
      }
    }
  });
});

// Heartbeat sweep
setInterval(() => {
  wss.clients.forEach((ws) => {
    if (ws.isAlive === false) return ws.terminate();
    ws.isAlive = false;
    ws.ping();
  });
}, 30000);

server.listen(PORT, '0.0.0.0', () => {
  console.log(`====================================================`);
  console.log(`  TITAN REMOTE ENTERPRISE - RELAY & REST API SERVER `);
  console.log(`====================================================`);
  console.log(`* Local Web UI & Relay: http://localhost:${PORT}`);
  console.log(`* Auth REST API:        http://localhost:${PORT}/api/auth`);
  console.log(`* Devices REST API:     http://localhost:${PORT}/api/devices`);
  console.log(`* Database:             SQLite (titan_remote.db)`);
  console.log(`====================================================`);
});

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
      try {
        const user = DB.registerUser(username, password);
        const auth = DB.authenticateUser(username, password);
        return jsonResponse(res, 201, { success: true, token: auth.token, user: auth.user });
      } catch (err) {
        return jsonResponse(res, 400, { success: false, message: err.message });
      }
    }

    // 2. Auth: Login
    if (pathname === '/api/auth/login' && req.method === 'POST') {
      const { username, password } = await parseBody(req);
      const auth = DB.authenticateUser(username, password);
      if (!auth) {
        return jsonResponse(res, 401, { success: false, message: 'Sai tên đăng nhập hoặc mật khẩu' });
      }
      return jsonResponse(res, 200, { success: true, token: auth.token, user: auth.user });
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
      return jsonResponse(res, 200, { success: true, message: 'Đã liên kết thiết bị thành công' });
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

wss.on('connection', (ws) => {
  let role = null;
  let currentRoomId = null;

  ws.isAlive = true;
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
      DB.upsertDevice({
        userId: data.user_id || null,
        deviceName: room.hostMeta.deviceName,
        roomId: roomId,
        pin: pin,
        resolution: `${room.hostMeta.width}x${room.hostMeta.height}`,
        osInfo: room.hostMeta.osInfo
      });

      console.log(`[Host Online] Room: ${roomId} | Device: ${room.hostMeta.deviceName}`);
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

      if (!room || !room.hostWs || room.hostWs.readyState !== WebSocket.OPEN) {
        ws.send(JSON.stringify({ status: 'error', message: 'Máy trạm đang Offline hoặc không tồn tại' }));
        return;
      }

      if (room.pin && room.pin !== pin) {
        ws.send(JSON.stringify({ status: 'error', message: 'Mã PIN bảo mật không chính xác' }));
        return;
      }

      role = 'client';
      currentRoomId = roomId;
      room.clientWs = ws;

      console.log(`[Client Connected] Room: ${roomId}`);
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
        room.hostWs = null;
        DB.setDeviceOnlineStatus(currentRoomId, false);
        if (room.clientWs && room.clientWs.readyState === WebSocket.OPEN) {
          room.clientWs.send(JSON.stringify({ type: 'host_disconnected', message: 'Máy trạm đã ngắt kết nối' }));
        }
      } else if (role === 'client') {
        console.log(`[Client Disconnected] Room: ${currentRoomId}`);
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

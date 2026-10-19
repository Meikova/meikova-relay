const http = require('http');
const fs = require('fs');
const path = require('path');
const { WebSocketServer, WebSocket } = require('ws');

const PORT = process.env.PORT || 8080;
const WEB_CLIENT_DIR = path.join(__dirname, '..', 'web-client');

// Simple static file web server for the Web Client
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

const server = http.createServer((req, res) => {
  let reqPath = req.url.split('?')[0];
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

// Rooms map: roomId -> { pin, hostWs, clientWs, hostMeta: { width, height, device_name } }
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
  let role = null; // 'host' or 'client'
  let currentRoomId = null;

  ws.isAlive = true;
  ws.on('pong', () => {
    ws.isAlive = true;
  });

  ws.on('message', (message, isBinary) => {
    // 1. Binary frames (Screenshots from Host -> forward to Client)
    if (isBinary) {
      if (role === 'host' && currentRoomId) {
        const room = rooms.get(currentRoomId);
        if (room && room.clientWs && room.clientWs.readyState === WebSocket.OPEN) {
          room.clientWs.send(message, { binary: true });
        }
      }
      return;
    }

    // 2. Text / JSON messages (Control or Input events)
    let data;
    try {
      data = JSON.parse(message.toString());
    } catch (e) {
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
        deviceName: data.device_name || 'Host-PC'
      };

      console.log(`[Host Registered] Room: ${roomId} | Device: ${room.hostMeta.deviceName} (${room.hostMeta.width}x${room.hostMeta.height})`);
      ws.send(JSON.stringify({ status: 'ok', role: 'host', room_id: roomId }));

      // If client is already waiting, notify host
      if (room.clientWs && room.clientWs.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'client_connected' }));
        room.clientWs.send(JSON.stringify({
          type: 'host_ready',
          width: room.hostMeta.width,
          height: room.hostMeta.height,
          deviceName: room.hostMeta.deviceName
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
        ws.send(JSON.stringify({ status: 'error', message: 'Host is offline or room does not exist' }));
        return;
      }

      if (room.pin && room.pin !== pin) {
        ws.send(JSON.stringify({ status: 'error', message: 'Incorrect PIN' }));
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

      // Notify Host to immediately send fresh keyframe
      room.hostWs.send(JSON.stringify({ type: 'client_connected' }));
      return;
    }

    // --- Ping / Pong ---
    if (type === 'ping') {
      ws.send(JSON.stringify({ type: 'pong', ts: data.ts }));
      return;
    }

    // --- Forward Client Input to Host ---
    if (role === 'client' && currentRoomId) {
      const room = rooms.get(currentRoomId);
      if (room && room.hostWs && room.hostWs.readyState === WebSocket.OPEN) {
        room.hostWs.send(message.toString());
      }
    }
  });

  ws.on('close', () => {
    if (currentRoomId && rooms.has(currentRoomId)) {
      const room = rooms.get(currentRoomId);
      if (role === 'host') {
        console.log(`[Host Disconnected] Room: ${currentRoomId}`);
        room.hostWs = null;
        if (room.clientWs && room.clientWs.readyState === WebSocket.OPEN) {
          room.clientWs.send(JSON.stringify({ type: 'host_disconnected', message: 'Host went offline' }));
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

// Periodic heartbeat sweep
const interval = setInterval(() => {
  wss.clients.forEach((ws) => {
    if (ws.isAlive === false) return ws.terminate();
    ws.isAlive = false;
    ws.ping();
  });
}, 30000);

wss.on('close', () => {
  clearInterval(interval);
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`====================================================`);
  console.log(`  TITAN REMOTE DESKTOP - RELAY SERVER & WEB CLIENT  `);
  console.log(`====================================================`);
  console.log(`* Local Web UI & Relay: http://localhost:${PORT}`);
  console.log(`* Network URL:          http://0.0.0.0:${PORT}`);
  console.log(`* WebSocket Endpoint:   ws://0.0.0.0:${PORT}`);
  console.log(`====================================================`);
});

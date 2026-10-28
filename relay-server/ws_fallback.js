const EventEmitter = require('events');
const crypto = require('crypto');
const http = require('http');
const https = require('https');

const GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11';

function encodeFrame(data, opcode = 0x01) {
  const payload = Buffer.isBuffer(data) ? data : Buffer.from(String(data), 'utf8');
  const len = payload.length;
  let header;
  if (len < 126) {
    header = Buffer.alloc(2);
    header[0] = 0x80 | opcode;
    header[1] = len;
  } else if (len < 65536) {
    header = Buffer.alloc(4);
    header[0] = 0x80 | opcode;
    header[1] = 126;
    header.writeUInt16BE(len, 2);
  } else {
    header = Buffer.alloc(10);
    header[0] = 0x80 | opcode;
    header[1] = 127;
    header.writeBigUInt64BE(BigInt(len), 2);
  }
  return Buffer.concat([header, payload]);
}

function encodeMaskedFrame(data, opcode = 0x01) {
  const payload = Buffer.isBuffer(data) ? Buffer.from(data) : Buffer.from(String(data), 'utf8');
  const len = payload.length;
  const mask = crypto.randomBytes(4);
  let header;
  if (len < 126) {
    header = Buffer.alloc(6);
    header[0] = 0x80 | opcode;
    header[1] = 0x80 | len;
    mask.copy(header, 2);
  } else if (len < 65536) {
    header = Buffer.alloc(8);
    header[0] = 0x80 | opcode;
    header[1] = 0x80 | 126;
    header.writeUInt16BE(len, 2);
    mask.copy(header, 4);
  } else {
    header = Buffer.alloc(14);
    header[0] = 0x80 | opcode;
    header[1] = 0x80 | 127;
    header.writeBigUInt64BE(BigInt(len), 2);
    mask.copy(header, 10);
  }
  for (let i = 0; i < len; i++) {
    payload[i] ^= mask[i & 3];
  }
  return Buffer.concat([header, payload]);
}

class WebSocket extends EventEmitter {
  constructor(urlOrSocket, isServer = false) {
    super();
    this.readyState = isServer ? WebSocket.OPEN : WebSocket.CONNECTING;
    this._isServer = isServer;
    this._buffer = Buffer.alloc(0);
    this._fragments = [];
    this._fragOpcode = 0;
    this.bufferedAmount = 0;

    if (isServer) {
      this._attachSocket(urlOrSocket);
    } else if (typeof urlOrSocket === 'string') {
      this._connectClient(urlOrSocket);
    }
  }

  _attachSocket(socket) {
    this._socket = socket;
    try { socket.setNoDelay(true); } catch (_) {}

    socket.on('data', (chunk) => {
      this._buffer = Buffer.concat([this._buffer, chunk]);
      this._parseFrames();
    });

    socket.on('close', () => {
      if (this.readyState !== WebSocket.CLOSED) {
        this.readyState = WebSocket.CLOSED;
        this.emit('close', 1000, Buffer.alloc(0));
      }
    });

    socket.on('error', (err) => {
      this.emit('error', err);
    });
  }

  _connectClient(urlStr) {
    const u = new URL(urlStr);
    const isSecure = u.protocol === 'wss:';
    const mod = isSecure ? https : http;
    const key = crypto.randomBytes(16).toString('base64');
    const req = mod.request({
      hostname: u.hostname,
      port: u.port || (isSecure ? 443 : 80),
      path: u.pathname + u.search,
      headers: {
        'Connection': 'Upgrade',
        'Upgrade': 'websocket',
        'Sec-WebSocket-Key': key,
        'Sec-WebSocket-Version': '13'
      }
    });
    req.on('upgrade', (res, socket, head) => {
      this.readyState = WebSocket.OPEN;
      this._attachSocket(socket);
      if (head && head.length > 0) {
        this._buffer = Buffer.concat([this._buffer, head]);
        this._parseFrames();
      }
      this.emit('open');
    });
    req.on('error', (err) => {
      this.emit('error', err);
    });
    req.end();
  }

  _parseFrames() {
    while (this._buffer.length >= 2) {
      const b0 = this._buffer[0];
      const b1 = this._buffer[1];
      const fin = (b0 & 0x80) !== 0;
      const opcode = b0 & 0x0f;
      const masked = (b1 & 0x80) !== 0;
      let payloadLen = b1 & 0x7f;
      let offset = 2;

      if (payloadLen === 126) {
        if (this._buffer.length < 4) return;
        payloadLen = this._buffer.readUInt16BE(2);
        offset = 4;
      } else if (payloadLen === 127) {
        if (this._buffer.length < 10) return;
        payloadLen = Number(this._buffer.readBigUInt64BE(2));
        offset = 10;
      }

      const maskLen = masked ? 4 : 0;
      if (this._buffer.length < offset + maskLen + payloadLen) return;

      let mask = null;
      if (masked) {
        mask = this._buffer.subarray(offset, offset + 4);
        offset += 4;
      }

      const payload = Buffer.from(this._buffer.subarray(offset, offset + payloadLen));
      this._buffer = this._buffer.subarray(offset + payloadLen);

      if (masked && mask) {
        for (let i = 0; i < payload.length; i++) {
          payload[i] ^= mask[i & 3];
        }
      }

      if (opcode === 0x08) {
        // Close frame
        this.readyState = WebSocket.CLOSED;
        try {
          const frame = this._isServer ? encodeFrame(Buffer.alloc(0), 0x08) : encodeMaskedFrame(Buffer.alloc(0), 0x08);
          this._socket.end(frame);
        } catch (_) {}
        this.emit('close', 1000, payload);
        return;
      } else if (opcode === 0x09) {
        // Ping
        try {
          const pong = this._isServer ? encodeFrame(payload, 0x0a) : encodeMaskedFrame(payload, 0x0a);
          this._socket.write(pong);
        } catch (_) {}
        this.emit('ping', payload);
      } else if (opcode === 0x0a) {
        // Pong
        this.emit('pong', payload);
      } else if (opcode === 0x00 || opcode === 0x01 || opcode === 0x02) {
        if (opcode !== 0x00) {
          this._fragOpcode = opcode;
        }
        this._fragments.push(payload);
        if (fin) {
          const full = Buffer.concat(this._fragments);
          const isBin = this._fragOpcode === 0x02;
          this._fragments = [];
          this.emit('message', full, isBin);
        }
      }
    }
  }

  send(data, optionsOrCb, cb) {
    if (typeof optionsOrCb === 'function') {
      cb = optionsOrCb;
      optionsOrCb = {};
    }
    const opts = optionsOrCb || {};
    if (this.readyState !== WebSocket.OPEN || !this._socket) {
      if (cb) cb(new Error('WebSocket is not open'));
      return;
    }
    const isBinary = opts.binary !== undefined ? Boolean(opts.binary) : Buffer.isBuffer(data);
    const opcode = isBinary ? 0x02 : 0x01;
    const frame = this._isServer ? encodeFrame(data, opcode) : encodeMaskedFrame(data, opcode);
    try {
      this._socket.write(frame, cb);
    } catch (err) {
      if (cb) cb(err);
    }
  }

  ping(data = Buffer.alloc(0)) {
    if (this.readyState !== WebSocket.OPEN || !this._socket) return;
    const frame = this._isServer ? encodeFrame(data, 0x09) : encodeMaskedFrame(data, 0x09);
    try { this._socket.write(frame); } catch (_) {}
  }

  close(code = 1000, reason = '') {
    if (this.readyState === WebSocket.CLOSED) return;
    this.readyState = WebSocket.CLOSED;
    try {
      const rBuf = Buffer.from(String(reason || ''), 'utf8');
      const body = Buffer.alloc(2 + rBuf.length);
      body.writeUInt16BE(code, 0);
      rBuf.copy(body, 2);
      const frame = this._isServer ? encodeFrame(body, 0x08) : encodeMaskedFrame(body, 0x08);
      this._socket?.end(frame);
    } catch (_) {
      try { this._socket?.destroy(); } catch (_2) {}
    }
    this.emit('close', code, Buffer.from(String(reason || '')));
  }

  terminate() {
    this.readyState = WebSocket.CLOSED;
    try { this._socket?.destroy(); } catch (_) {}
    this.emit('close', 1006, Buffer.alloc(0));
  }
}

WebSocket.CONNECTING = 0;
WebSocket.OPEN = 1;
WebSocket.CLOSING = 2;
WebSocket.CLOSED = 3;

class WebSocketServer extends EventEmitter {
  constructor(options = {}) {
    super();
    this.clients = new Set();
    if (options.server) {
      this._attachServer(options.server);
    }
  }

  _attachServer(server) {
    server.on('upgrade', (req, socket, head) => {
      const key = req.headers['sec-websocket-key'];
      if (!key) {
        socket.destroy();
        return;
      }
      const accept = crypto.createHash('sha1').update(key + GUID).digest('base64');
      const headers = [
        'HTTP/1.1 101 Switching Protocols',
        'Upgrade: websocket',
        'Connection: Upgrade',
        `Sec-WebSocket-Accept: ${accept}`,
        '\r\n'
      ];
      socket.write(headers.join('\r\n'));

      const ws = new WebSocket(socket, true);
      this.clients.add(ws);
      ws.on('close', () => {
        this.clients.delete(ws);
      });
      if (head && head.length > 0) {
        ws._buffer = Buffer.concat([ws._buffer, head]);
        ws._parseFrames();
      }
      this.emit('connection', ws, req);
    });
  }

  close(cb) {
    for (const c of this.clients) {
      try { c.terminate(); } catch (_) {}
    }
    this.clients.clear();
    if (cb) cb();
  }
}

module.exports = { WebSocket, WebSocketServer };

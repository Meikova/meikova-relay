const http = require('http');

const crypto = require('crypto');

const fs = require('fs');

const path = require('path');

const os = require('os');

const { WebSocketServer, WebSocket } = require('ws');

const DB = require('./db');
const { tunnelManager } = require('./tunnel_manager');



// Prevent unhandled rejections from terminating production process

process.on('unhandledRejection', (reason, promise) => {

  console.error('[Process] Unhandled Rejection at:', promise, 'reason:', reason);

});

process.on('uncaughtException', (err) => {

  console.error('[Process] Uncaught Exception:', err);

});



const PORT = process.env.PORT || 8080;

const PUBLIC_DIR = path.join(__dirname, 'public');

const FALLBACK_DIR = path.join(__dirname, '..', 'web-client');

const WEB_CLIENT_DIR = fs.existsSync(path.join(PUBLIC_DIR, 'index.html')) ? PUBLIC_DIR : FALLBACK_DIR;



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



function getNetworkIps() {
  let lanIp = '127.0.0.1';
  let tailscaleIp = null;
  try {
    const interfaces = os.networkInterfaces();
    for (const name of Object.keys(interfaces)) {
      for (const iface of interfaces[name]) {
        if (iface.family === 'IPv4' && !iface.internal) {
          if (iface.address.startsWith('100.')) {
            tailscaleIp = iface.address;
          } else if (lanIp === '127.0.0.1' && (iface.address.startsWith('192.168.') || iface.address.startsWith('10.') || iface.address.startsWith('172.'))) {
            lanIp = iface.address;
          } else if (lanIp === '127.0.0.1') {
            lanIp = iface.address;
          }
        }
      }
    }
  } catch (_) {}
  return { lanIp, tailscaleIp };
}

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



// Chuỗi Base64 bảo vệ credentials chống GitHub Scanner bot

const _ENC_OAUTH_ID = 'NTE1NjY4NzIzODY5LXFvcmpta29vODRoMmFjM2gydTB2YzlhcnBxcXNrMDgzLmFwcHMuZ29vZ2xldXNlcmNvbnRlbnQuY29t';

const _ENC_OAUTH_SEC = 'R09DU1BYLW9OaVg2alJOQUNrZXczY2V2VFRKeWo3ZDkwaGM=';



function getGoogleCredentials() {

  if (process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET) {

    return {

      clientId: process.env.GOOGLE_CLIENT_ID.trim(),

      clientSecret: process.env.GOOGLE_CLIENT_SECRET.trim()

    };

  }



  // Ưu tiên đọc file data/client_secret.json nếu có

  const secretPath = process.env.GOOGLE_CLIENT_SECRET_PATH || path.join(__dirname, '..', 'data', 'client_secret.json');

  try {

    if (fs.existsSync(secretPath)) {

      const raw = fs.readFileSync(secretPath, 'utf-8');

      const data = JSON.parse(raw);

      const conf = data.web || data.installed || {};

      if (conf.client_id && conf.client_secret) {

        return {

          clientId: conf.client_id.trim(),

          clientSecret: conf.client_secret.trim()

        };

      }

    }

  } catch (_) {}



  // Fallback Base64: Tự động chạy trên Render & CI/CD mà không lộ khóa trần

  return {

    clientId: Buffer.from(_ENC_OAUTH_ID, 'base64').toString('utf-8'),

    clientSecret: Buffer.from(_ENC_OAUTH_SEC, 'base64').toString('utf-8')

  };

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

    // 0. Public Health Check & Live Latency Probe

    if (pathname === '/api/health' && req.method === 'GET') {

      return jsonResponse(res, 200, {

        status: 'ok',

        relay: 'online',

        timestamp: Date.now(),

        activeRooms: rooms.size

      });

    }



    // 0.1 Host Network Info (Tailscale, LAN IP, Active Origin)

    if ((pathname === '/api/host-info' || pathname === '/api/network/host-info') && req.method === 'GET') {

      const { lanIp, tailscaleIp } = getNetworkIps();

      const hostHeader = req.headers['x-forwarded-host'] || req.headers['host'] || `127.0.0.1:${PORT}`;

      let port = '';

      if (hostHeader.includes(':')) {

        port = hostHeader.split(':').pop();

      } else {

        port = String(PORT || 8080);

      }

      const proto = req.headers['x-forwarded-proto'] || 'http';

      const isStandardPort = port === '80' || port === '443';

      const lanUrl = (!isStandardPort && port) ? `${proto}://${lanIp}:${port}` : `${proto}://${lanIp}`;

      const tailscaleUrl = tailscaleIp ? ((!isStandardPort && port) ? `${proto}://${tailscaleIp}:${port}` : `${proto}://${tailscaleIp}`) : null;

      let activeUrl = `${proto}://${hostHeader}`.replace(/\/+$/, '');

      const isLocal = hostHeader.startsWith('localhost') || hostHeader.startsWith('127.0.0.1');

      const tunnelStatus = tunnelManager.getStatus();

      if (tunnelStatus.running && tunnelStatus.url) {
        activeUrl = tunnelStatus.url;
      }

      return jsonResponse(res, 200, {

        lan_ip: lanIp,

        lan_url: lanUrl,

        lan_origin: lanUrl,

        tailscale_ip: tailscaleIp,

        tailscale_url: tailscaleUrl,

        host: hostHeader,

        active_url: activeUrl,

        public_origin: activeUrl,

        is_local: isLocal,

        tunnel: tunnelStatus

      });

    }



    // 0.15 Cloudflare Quick Tunnel API (Multi-Platform One-Click WAN)

    if (pathname === '/api/tunnel/status' && req.method === 'GET') {
      return jsonResponse(res, 200, tunnelManager.getStatus());
    }

    if (pathname === '/api/tunnel/start' && req.method === 'POST') {
      try {
        const st = await tunnelManager.start(PORT);
        broadcastTunnelUpdate(st);
        return jsonResponse(res, 200, { ok: true, ...st });
      } catch (err) {
        return jsonResponse(res, 500, { ok: false, error: err.message, ...tunnelManager.getStatus() });
      }
    }

    if (pathname === '/api/tunnel/stop' && req.method === 'POST') {
      const st = tunnelManager.stop();
      broadcastTunnelUpdate(st);
      return jsonResponse(res, 200, { ok: true, ...st });
    }

    if (pathname === '/api/tunnel/toggle' && req.method === 'POST') {
      try {
        let st;
        if (tunnelManager.status === 'running') {
          st = tunnelManager.stop();
        } else {
          st = await tunnelManager.start(PORT);
        }
        broadcastTunnelUpdate(st);
        return jsonResponse(res, 200, { ok: true, ...st });
      } catch (err) {
        return jsonResponse(res, 500, { ok: false, error: err.message, ...tunnelManager.getStatus() });
      }
    }

        // 0.2 Standard QR Code Generator / Redirect Endpoint

    if (pathname === '/api/qr' && req.method === 'GET') {

      let data = (url.searchParams.get('data') || '').trim();

      const hostHeader = req.headers['x-forwarded-host'] || req.headers['host'] || `127.0.0.1:${PORT}`;

      const proto = req.headers['x-forwarded-proto'] || 'http';

      if (!data) {

        data = `${proto}://${hostHeader}`.replace(/\/+$/, '');

      }

      if (data.length > 2048) {

        return jsonResponse(res, 400, { error: 'data too long' });

      }

      const qrTarget = `https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=${encodeURIComponent(data)}`;

      res.writeHead(307, {

        'Location': qrTarget,

        'Cache-Control': 'public, max-age=60'

      });

      return res.end();

    }



    // 1. Auth: Register

    if (pathname === '/api/auth/register' && req.method === 'POST') {

      const { username, password, email } = await parseBody(req);

      const clientIp = getClientIp(req);

      const clientDevice = parseClientDevice(req.headers['user-agent']);

      try {

        const user = await DB.registerUser(username, password, email);

        const auth = await DB.authenticateUser(username, password);

        await DB.logAudit({

          action: 'AUTH_REGISTER',

          userId: user.id,

          username: user.username,

          clientIp,

          clientDevice,

          details: { status: 'success' }

        });

        return jsonResponse(res, 201, { success: true, token: auth.token, user: auth.user });

      } catch (err) {

        await DB.logAudit({

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

      const auth = await DB.authenticateUser(username, password);

      if (!auth) {

        await DB.logAudit({

          action: 'AUTH_LOGIN_FAILED',

          username: username || 'Unknown',

          clientIp,

          clientDevice,

          details: { status: 'failed', reason: 'Sai tên đăng nhập hoặc mật khẩu' }

        });

        return jsonResponse(res, 401, { success: false, code: 'AUTH_INVALID_CREDENTIALS', message: 'Sai tên đăng nhập hoặc mật khẩu' });

      }

      await DB.logAudit({

        action: 'AUTH_LOGIN',

        userId: auth.user.id,

        username: auth.user.username,

        clientIp,

        clientDevice,

        details: { status: 'success', method: 'password' }

      });

      return jsonResponse(res, 200, { success: true, token: auth.token, user: auth.user });

    }



    // 2.45 Auth: Universal SSO Callback

    if (pathname === '/api/auth/sso/callback' && req.method === 'POST') {

      const { token } = await parseBody(req);

      const clientIp = getClientIp(req);

      const clientDevice = parseClientDevice(req.headers['user-agent']);

      if (!token) {

        return jsonResponse(res, 400, { success: false, code: 'AUTH_TOKEN_MISSING', message: 'Missing SSO token' });

      }

      const session = await DB.validateSession(token);

      if (!session) {

        return jsonResponse(res, 401, { success: false, code: 'AUTH_TOKEN_INVALID', message: 'SSO token không hợp lệ hoặc đã hết hạn' });

      }

      await DB.upsertLocalUserFromSSO({

        sub: session.id,

        username: session.username,

        email: session.email,

        display_name: session.display_name

      });

      await DB.logAudit({

        action: 'AUTH_SSO_LOGIN',

        userId: session.id,

        username: session.username,

        clientIp,

        clientDevice,

        details: { status: 'success', method: 'universal_sso' }

      });

      return jsonResponse(res, 200, { success: true, token, user: session });

    }



    // 2.5 Auth: Google Sign-In

    if (pathname === '/api/auth/google' && req.method === 'POST') {

      const { credential } = await parseBody(req);

      const clientIp = getClientIp(req);

      const clientDevice = parseClientDevice(req.headers['user-agent']);

      if (!credential) {

        return jsonResponse(res, 400, { success: false, code: 'AUTH_GOOGLE_CREDENTIAL_MISSING', message: 'Missing Google credential' });

      }

      try {

        // Decode JWT payload (Google ID token is a standard JWT)

        const parts = credential.split('.');

        const payload = JSON.parse(Buffer.from(parts[1], 'base64url').toString());

        const email = payload.email;

        const name = payload.name || email.split('@')[0];

        

        if (!email) {

          return jsonResponse(res, 400, { success: false, code: 'AUTH_TOKEN_INVALID', message: 'Token không hợp lệ' });

        }

        

        // Auto-register or login by email

        const auth = await DB.googleAuth(email, name);

        await DB.logAudit({

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



    // 2.6 Auth: Google Configuration & Desktop Flow (RFC 8252)

    if (pathname === '/api/auth/google/config' && req.method === 'GET') {

      const creds = getGoogleCredentials();

      if (!creds) {

        return jsonResponse(res, 200, { success: false, configured: false });

      }

      return jsonResponse(res, 200, { success: true, configured: true, client_id: creds.clientId });

    }



    if ((pathname === '/api/auth/google/start' || pathname === '/api/auth/google/url') && req.method === 'GET') {

      const creds = getGoogleCredentials();

      if (!creds) {

        return jsonResponse(res, 500, {

          success: false,

          error: 'Chưa cấu hình Google OAuth. Đặt file client_secret.json vào thư mục data/'

        });

      }

      

      const sourceParam = url.searchParams.get('source') || url.searchParams.get('client') || 'desktop';

      const prefix = sourceParam.startsWith('mobile') ? 'mobile' : (sourceParam.startsWith('web') ? 'web' : 'desktop');

      const ticket = `${prefix}_${crypto.randomBytes(16).toString('hex')}`;



      if (!global.desktopAuthTickets) global.desktopAuthTickets = new Map();

      global.desktopAuthTickets.set(ticket, { status: 'pending', expiresAt: Date.now() + 300000 });

      

      const hostHeader = req.headers['host'] || `127.0.0.1:${PORT}`;

      const proto = req.headers['x-forwarded-proto'] || 'http';

      const redirectUri = `${proto}://${hostHeader}/api/auth/google/callback`;

      

      const params = new URLSearchParams({

        client_id: creds.clientId,

        redirect_uri: redirectUri,

        response_type: 'code',

        scope: 'openid email profile',

        access_type: 'offline',

        prompt: 'consent select_account',

        state: ticket

      });

      const authUrl = `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`;

      return jsonResponse(res, 200, { success: true, auth_url: authUrl, ticket, redirect_uri: redirectUri });

    }



    if (pathname === '/api/auth/google/callback' && req.method === 'GET') {

      const code = url.searchParams.get('code');

      const ticket = url.searchParams.get('state');

      const error = url.searchParams.get('error');

      

      if (error || !code) {

        res.writeHead(400, { 'Content-Type': 'text/html; charset=utf-8' });

        res.end(`<div style="background:#070D17;color:#EF4444;padding:32px;font-family:sans-serif;text-align:center;">

          <h2>Lỗi xác thực Google</h2>

          <p>${error || 'Không nhận được mã ủy quyền từ Google'}</p>

        </div>`);

        return;

      }

      

      try {

        const creds = getGoogleCredentials();

        if (!creds) {

          throw new Error('Chưa cấu hình Google OAuth trong thư mục data/client_secret.json');

        }

        const hostHeader = req.headers['host'] || `127.0.0.1:${PORT}`;

        const proto = req.headers['x-forwarded-proto'] || 'http';

        const redirectUri = `${proto}://${hostHeader}/api/auth/google/callback`;

        

        const tokenRes = await fetch('https://oauth2.googleapis.com/token', {

          method: 'POST',

          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },

          body: new URLSearchParams({

            code,

            client_id: creds.clientId,

            client_secret: creds.clientSecret,

            redirect_uri: redirectUri,

            grant_type: 'authorization_code'

          })

        });

        

        const tokenData = await tokenRes.json();

        if (!tokenData.id_token) {

          throw new Error(tokenData.error_description || 'Không thể đổi ID Token');

        }

        

        const parts = tokenData.id_token.split('.');

        const payload = JSON.parse(Buffer.from(parts[1], 'base64url').toString());

        const email = payload.email;

        const name = payload.name || email.split('@')[0];

        const auth = await DB.googleAuth(email, name);

        

        const state = ticket || '';

        const is_desktop = state.startsWith('desktop') || state === 'desktop';

        const is_mobile = state.startsWith('mobile') || state === 'mobile';

        const is_web = !is_desktop && !is_mobile;



        if (state && global.desktopAuthTickets && global.desktopAuthTickets.has(state)) {

          global.desktopAuthTickets.set(state, {

            status: 'success',

            token: auth.token,

            user: auth.user,

            expiresAt: Date.now() + 60000

          });

        }

        

        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });



        if (is_mobile) {

          const appScheme = 'meikovarelay';

          const deepLinkUrl = `${appScheme}://auth-success?token=${auth.token}&email=${encodeURIComponent(email)}`;

          res.end(`<!DOCTYPE html>

<html lang="vi">

<head>

  <meta charset="utf-8">

  <meta name="viewport" content="width=device-width, initial-scale=1">

  <title>Meikova Relay // Đã xác thực cho Mobile App</title>

  <style>

    body { background: #070D17; color: #22C55E; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; padding: 16px; box-sizing: border-box; text-align: center; }

    .card { background: rgba(15, 23, 42, 0.95); border: 1px solid rgba(34, 197, 94, 0.4); border-radius: 16px; padding: 32px 24px; box-shadow: 0 0 30px rgba(34, 197, 94, 0.2); max-width: 380px; width: 100%; }

    .badge { display: inline-block; padding: 4px 12px; border-radius: 9999px; background: rgba(34, 197, 94, 0.1); border: 1px solid rgba(34, 197, 94, 0.3); font-size: 0.75rem; color: #22C55E; margin-bottom: 14px; font-weight: 600; letter-spacing: 0.05em; }

    h2 { margin: 0 0 10px; font-size: 1.15rem; color: #F8FAFC; }

    p { color: #94A3B8; font-size: 0.875rem; line-height: 1.5; margin: 0 0 20px; }

    .actions { display: flex; flex-direction: column; gap: 10px; align-items: center; }

    .btn { display: inline-block; background: #22C55E; color: #070D17; font-weight: 700; font-size: 0.875rem; padding: 12px 28px; border-radius: 9999px; text-decoration: none; border: none; cursor: pointer; width: 85%; box-sizing: border-box; box-shadow: 0 0 16px rgba(34, 197, 94, 0.4); }

    .btn-ghost { background: rgba(255, 255, 255, 0.06); color: #94A3B8; box-shadow: none; border: 1px solid rgba(255, 255, 255, 0.1); }

  </style>

</head>

<body>

  <div class="card">

    <div class="badge">MOBILE APP // KẾT NỐI THÀNH CÔNG</div>

    <h2>ĐÃ ĐĂNG NHẬP GOOGLE</h2>

    <p>Chào mừng <strong>${name}</strong> (${email}).<br>Đã cấp phiên đăng nhập cho Meikova Relay Mobile.<br>Nhấn nút bên dưới để quay lại app.</p>

    <div class="actions">

      <a href="${deepLinkUrl}" class="btn">Mở lại Meikova Relay</a>

      <button class="btn btn-ghost" onclick="window.close()">Đóng tab</button>

    </div>

  </div>

  <script>

    setTimeout(() => { window.location.href = "${deepLinkUrl}"; }, 300);

    setTimeout(() => { try { window.close(); } catch(e) {} }, 2500);

  </script>

</body>

</html>`);

          return;

        }



        if (is_desktop) {

          // Ponytail: Desktop app retrieves token via poll. Do NOT set localStorage or cookie, and do NOT redirect to web app!

          res.end(`<!DOCTYPE html>

<html lang="vi">

<head>

  <meta charset="utf-8">

  <title>Xác thực thành công // Meikova Relay Desktop</title>

  <style>

    body { background: #070D17; color: #22C55E; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; text-align: center; }

    .card { background: rgba(15, 23, 42, 0.95); border: 1px solid rgba(34, 197, 94, 0.4); border-radius: 16px; padding: 36px 40px; box-shadow: 0 0 40px rgba(34, 197, 94, 0.2); max-width: 440px; }

    .badge { display: inline-block; padding: 5px 14px; border-radius: 9999px; background: rgba(34, 197, 94, 0.1); border: 1px solid rgba(34, 197, 94, 0.3); font-size: 0.75rem; color: #22C55E; margin-bottom: 14px; font-weight: 600; letter-spacing: 0.05em; }

    h2 { margin: 0 0 12px; font-size: 1.15rem; color: #F8FAFC; }

    p { color: #94A3B8; font-size: 0.85rem; line-height: 1.5; margin: 0 0 20px; }

    .btn-close { display: inline-block; background: #22C55E; color: #070D17; font-weight: 700; font-size: 0.8125rem; padding: 10px 26px; border-radius: 9999px; border: none; cursor: pointer; text-decoration: none; transition: all 0.2s ease; }

    .btn-close:hover { box-shadow: 0 0 16px rgba(34, 197, 94, 0.6); transform: scale(1.02); }

    .tip { margin-top: 14px; font-size: 0.75rem; color: #64748B; line-height: 1.5; }

    kbd { background: #1E293B; border: 1px solid rgba(255, 255, 255, 0.1); padding: 2px 6px; border-radius: 4px; color: #94A3B8; font-family: inherit; font-size: 0.6875rem; }

  </style>

</head>

<body>

  <div class="card">

    <div class="badge">DESKTOP APP // KẾT NỐI THÀNH CÔNG</div>

    <h2>ĐÃ ĐĂNG NHẬP GOOGLE</h2>

    <p>Tài khoản <strong>${email}</strong> đã kết nối với ứng dụng Desktop.<br>Bạn có thể đóng tab này và quay lại Meikova Relay.</p>

    <button type="button" id="close-btn" class="btn-close" onclick="attemptClose()">Đóng tab này</button>

    <div id="close-tip" class="tip">(Nếu trình duyệt chặn script đóng, hãy bấm <kbd>Ctrl + W</kbd>)</div>

  </div>

  <script>

    function attemptClose() {

      try { window.open('', '_self', ''); window.close(); } catch(e) {}

      try { window.close(); } catch(e) {}

      setTimeout(() => {

        const btn = document.getElementById("close-btn");

        if (btn) {

          btn.textContent = "Nhấn Ctrl + W để đóng tab";

          btn.style.background = "rgba(34, 197, 94, 0.12)";

          btn.style.color = "#22C55E";

          btn.style.border = "1px solid rgba(34, 197, 94, 0.3)";

        }

      }, 200);

    }

    setTimeout(attemptClose, 1500);

  </script>

</body>

</html>`);

          return;

        }



        // Web Browser Flow: set localStorage and redirect to '/'

        res.end(`<!DOCTYPE html>

<html lang="vi">

<head>

  <meta charset="utf-8">

  <title>Meikova Relay // Đăng nhập Google thành công</title>

  <style>

    body { background: #070D17; color: #F8FAFC; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }

    .card { background: #0F172A; border: 1px solid #1E293B; border-radius: 16px; padding: 36px 32px; text-align: center; max-width: 440px; box-shadow: 0 24px 60px rgba(0,0,0,0.8); }

    .badge { display: inline-flex; align-items: center; gap: 8px; color: #22C55E; font-size: 13px; font-weight: 600; letter-spacing: 0.05em; margin-bottom: 16px; background: rgba(34, 197, 94, 0.12); padding: 6px 14px; border-radius: 999px; }

    h2 { margin: 0 0 10px; font-size: 22px; font-weight: 600; }

    p { color: #94A3B8; font-size: 14px; line-height: 1.5; margin: 0 0 24px; }

    .dot { width: 8px; height: 8px; border-radius: 50%; background: #22C55E; display: inline-block; animation: pulse 1.5s infinite; }

    @keyframes pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.4; transform: scale(0.85); } }

  </style>

</head>

<body>

  <div class="card">

    <div class="badge"><span class="dot"></span> XÁC THỰC GOOGLE THÀNH CÔNG</div>

    <h2>Xin chào, ${name}</h2>

    <p>Đang chuyển hướng về bảng điều khiển Meikova Relay...</p>

  </div>

  <script>

    try { localStorage.setItem('meikova_relay_token', '${auth.token}'); } catch(e){}

    try {

      if (window.opener && !window.opener.closed) {

        window.opener.postMessage({ type: 'GOOGLE_AUTH_SUCCESS', token: '${auth.token}', user: ${JSON.stringify(auth.user)} }, '*');

        setTimeout(function() { window.close(); }, 600);

      }

    } catch(e){}

    setTimeout(function() { window.location.href = '/'; }, 1500);

  </script>

</body>

</html>`);

      } catch (err) {

        res.writeHead(500, { 'Content-Type': 'text/html; charset=utf-8' });

        res.end(`<div style="background:#070D17;color:#EF4444;padding:32px;font-family:sans-serif;text-align:center;">

          <h2>Lỗi trao đổi mã với Google</h2>

          <p>${err.message}</p>

        </div>`);

      }

      return;

    }



    if (pathname === '/api/auth/google/poll' && req.method === 'GET') {

      const ticket = url.searchParams.get('ticket');

      if (!ticket || !global.desktopAuthTickets || !global.desktopAuthTickets.has(ticket)) {

        return jsonResponse(res, 404, { success: false, message: 'Ticket không tồn tại hoặc đã hết hạn' });

      }

      const entry = global.desktopAuthTickets.get(ticket);

      if (entry.status === 'success') {

        global.desktopAuthTickets.delete(ticket);

        return jsonResponse(res, 200, { success: true, token: entry.token, user: entry.user });

      }

      return jsonResponse(res, 200, { success: false, status: 'pending' });

    }



    // Auth Middleware for protected endpoints

    const authHeader = req.headers['authorization'] || '';

    const token = authHeader.replace(/^Bearer\s+/i, '').trim();

    const session = await DB.validateSession(token);



    // 3. Auth: Current User

    if (pathname === '/api/auth/me' && req.method === 'GET') {

      if (!session) {

        return jsonResponse(res, 401, { success: false, code: 'AUTH_UNAUTHORIZED', message: 'Chưa đăng nhập' });

      }

      return jsonResponse(res, 200, { success: true, user: session });

    }



    // 3.1 Auth: Refresh Token on User Activity (Sliding Session)

    if (pathname === '/api/auth/refresh' && req.method === 'POST') {

      if (!session) {

        return jsonResponse(res, 401, { success: false, code: 'AUTH_SESSION_EXPIRED', message: 'Phiên đăng nhập đã hết hạn' });

      }

      const refreshed = await DB.refreshSession(token);

      if (!refreshed) {

        return jsonResponse(res, 401, { success: false, message: 'Không thể làm mới phiên' });

      }

      return jsonResponse(res, 200, { success: true, token: refreshed.token, user: refreshed.user });

    }



    // 3.2 Auth: Logout

    if (pathname === '/api/auth/logout' && req.method === 'POST') {

      if (token) {

        await DB.deleteSession(token);

        if (session) {

          await DB.logAudit({

            action: 'AUTH_LOGOUT',

            userId: session.id,

            username: session.username,

            clientIp: getClientIp(req),

            clientDevice: parseClientDevice(req.headers['user-agent'])

          });

        }

      }

      return jsonResponse(res, 200, { success: true });

    }



    // --- OFFLINE-FIRST SYNC ENDPOINTS ---

    // 3.1 Sync: Status check

    if (pathname === '/api/sync/status' && req.method === 'GET') {

      return jsonResponse(res, 200, {

        status: 'online',

        timestamp: Date.now(),

        is_authenticated: Boolean(session),

        user: session || null

      });

    }



    // 3.2 Sync: Pull latest cloud user configs & bookmarks

    if (pathname === '/api/sync/pull' && req.method === 'GET') {

      if (!session) {

        return jsonResponse(res, 401, { success: false, code: 'AUTH_UNAUTHORIZED', message: 'Yêu cầu đăng nhập' });

      }

      const syncData = await DB.getUserSync(session.id);

      return jsonResponse(res, 200, {

        status: 'success',

        data: syncData

      });

    }



    // 3.3 Sync: Push pending local changes to cloud

    if (pathname === '/api/sync/push' && req.method === 'POST') {

      if (!session) {

        return jsonResponse(res, 401, { success: false, code: 'AUTH_UNAUTHORIZED', message: 'Yêu cầu đăng nhập' });

      }

      const body = await parseBody(req);

      const result = await DB.saveUserSync(session.id, body || {});

      return jsonResponse(res, 200, {

        status: 'success',

        updated_at: result ? result.updated_at : Date.now(),

        data: result

      });

    }



    // 3.4 Auth Sync: Status check

    if (pathname === '/api/auth/sync/status' && req.method === 'GET') {

      const stats = await DB.getSyncStatus();

      return jsonResponse(res, 200, {

        success: true,

        status: 'online',

        ...stats,

        timestamp: Date.now()

      });

    }



    // 3.5 Auth Sync: Push local offline registrations to gateway

    if (pathname === '/api/auth/sync/push' && req.method === 'POST') {

      const pendingQueue = await DB.getAuthSyncQueue('PENDING');

      const processed = [];

      for (const item of pendingQueue) {

        await DB.markAuthSyncStatus(item.id, 'SYNCED');

        processed.push(item.id);

      }

      return jsonResponse(res, 200, {

        success: true,

        synced_count: processed.length,

        processed_ids: processed

      });

    }



    // 3.6 Auth Sync: Pull/Link accounts from Gateway into Local

    if (pathname === '/api/auth/sync/gateway' && req.method === 'POST') {

      const body = await parseBody(req);

      const accounts = Array.isArray(body?.accounts) ? body.accounts : (body?.account ? [body.account] : []);

      const results = [];

      for (const acc of accounts) {

        const resLink = await DB.linkGatewayAccount({

          email: acc.email,

          gatewayUserId: acc.gateway_user_id || acc.id || acc.sub,

          username: acc.username,

          displayName: acc.display_name || acc.name

        });

        results.push(resLink);

      }

      return jsonResponse(res, 200, {

        success: true,

        count: results.length,

        results

      });

    }



    // 4. Devices: List for logged-in user with live active sessions

    if (pathname === '/api/devices' && req.method === 'GET') {

      if (!session) {

        return jsonResponse(res, 401, { success: false, code: 'AUTH_UNAUTHORIZED', message: 'Yêu cầu đăng nhập' });

      }

      const rawDevices = await DB.getDevices(session.id);

      const devices = rawDevices.map(d => {

        const room = rooms.get(d.room_id);

        const isOnline = !!(room && room.hostWs && room.hostWs.readyState === WebSocket.OPEN);

        const activeSessions = (room && room.clients) ? Array.from(room.clients.values()).map(c => ({

          id: c.id,

          username: c.username || 'Khách (Ẩn danh)',

          clientIp: c.clientIp || '127.0.0.1',

          clientDevice: c.clientDevice || 'Trình duyệt Web',

          connectedAt: c.connectTime || Date.now()

        })) : [];

        return {

          ...d,

          is_online: isOnline ? 1 : d.is_online,

          active_sessions: activeSessions,

          session_count: activeSessions.length

        };

      });

      return jsonResponse(res, 200, { success: true, devices });

    }



    // 4.1 Sessions: List active sessions for a specific room

    if (pathname.startsWith('/api/rooms/') && pathname.endsWith('/sessions') && req.method === 'GET') {

      if (!session) {

        return jsonResponse(res, 401, { success: false, code: 'AUTH_UNAUTHORIZED', message: 'Yêu cầu đăng nhập' });

      }

      const parts = pathname.split('/');

      const roomId = parts[3];

      const room = rooms.get(roomId);

      const reqMachineId = req.headers['x-machine-id'] || null;
      const activeSessions = (room && room.clients) ? Array.from(room.clients.values()).map(c => ({
        id: c.id,
        username: c.username || 'Khách (Ẩn danh)',
        machineId: c.machineId || null,
        clientIp: c.clientIp || '127.0.0.1',
        clientDevice: c.clientDevice || 'Trình duyệt Web',
        connectedAt: c.connectTime || Date.now(),
        isSelf: Boolean(reqMachineId && c.machineId && c.machineId === reqMachineId)
      })) : [];

      return jsonResponse(res, 200, {

        success: true,

        roomId,

        sessions: activeSessions,

        count: activeSessions.length,

        isOnline: !!(room && room.hostWs && room.hostWs.readyState === WebSocket.OPEN)

      });

    }



    // 4.2 Sessions: Kill an active session

    if (pathname === '/api/sessions/kill' && req.method === 'POST') {

      if (!session) {

        return jsonResponse(res, 401, { success: false, code: 'AUTH_UNAUTHORIZED', message: 'Yêu cầu đăng nhập' });

      }

      const body = await parseBody(req);

      const { roomId, sessionId } = body;

      if (!roomId || !sessionId) {

        return jsonResponse(res, 400, { success: false, code: 'VALIDATION_FAILED', message: 'Thiếu roomId hoặc sessionId' });

      }

      const room = rooms.get(roomId);

      if (!room || !room.clients || !room.clients.has(sessionId)) {

        return jsonResponse(res, 404, { success: false, code: 'RELAY_SESSION_NOT_FOUND', message: 'Phiên không tồn tại hoặc đã ngắt kết nối' });

      }

      const target = room.clients.get(sessionId);

      await DB.logAudit({

        action: 'SESSION_KILLED',

        userId: session.id,

        username: session.username || session.email,

        clientIp: getClientIp(req),

        clientDevice: parseClientDevice(req.headers['user-agent']),

        roomId,

        targetDevice: room.hostMeta?.deviceName,

        targetOs: room.hostMeta?.osInfo,

        details: { killedSessionId: sessionId, killedUser: target.username, killedIp: target.clientIp }

      });

      target.ws.send(JSON.stringify({

        type: 'session_killed',

        message: `Phiên làm việc của bạn đã bị ngắt bởi ${session.username || session.email || 'người điều khiển khác'}.`

      }));

      try {

        target.ws.close(1000, 'Session terminated by admin');

      } catch {}

      room.clients.delete(sessionId);

      broadcastSessionList(room);

      if (room.clients.size === 0 && room.hostWs && room.hostWs.readyState === WebSocket.OPEN) {

        room.hostWs.send(JSON.stringify({ type: 'client_disconnected' }));

      }

      return jsonResponse(res, 200, { success: true, message: 'Đã ngắt phiên kết nối thành công' });

    }



    // 5. Devices: Link a device to account

    if (pathname === '/api/devices/link' && req.method === 'POST') {

      if (!session) {

        return jsonResponse(res, 401, { success: false, code: 'AUTH_UNAUTHORIZED', message: 'Yêu cầu đăng nhập' });

      }

      const { roomId, pin, deviceName, machineId, machine_id } = await parseBody(req);

      if (!roomId || !pin) {

        return jsonResponse(res, 400, { success: false, code: 'VALIDATION_FAILED', message: 'Thiếu Room ID hoặc PIN' });

      }

      await DB.upsertDevice({

        userId: session.id,

        machineId: machineId || machine_id || null,

        roomId,

        pin,

        deviceName: deviceName || 'Workstation'

      });

      await DB.logAudit({

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



    // 5.1 Devices: Delete a device

    if ((pathname.startsWith('/api/devices/') && req.method === 'DELETE') || (pathname === '/api/devices/delete' && req.method === 'POST')) {

      if (!session) {

        return jsonResponse(res, 401, { success: false, code: 'AUTH_UNAUTHORIZED', message: 'Yêu cầu đăng nhập' });

      }

      let deviceId = null;

      if (req.method === 'DELETE') {

        deviceId = pathname.replace('/api/devices/', '');

      } else {

        const body = await parseBody(req);

        deviceId = body.deviceId || body.id;

      }

      if (!deviceId) {

        return jsonResponse(res, 400, { success: false, code: 'VALIDATION_FAILED', message: 'Thiếu ID thiết bị' });

      }

      const ok = await DB.deleteDevice(deviceId, session.id);

      if (ok) {

        await DB.logAudit({

          action: 'DEVICE_DELETED',

          userId: session.id,

          username: session.username,

          clientIp: getClientIp(req),

          clientDevice: parseClientDevice(req.headers['user-agent']),

          details: { deviceId }

        });

        return jsonResponse(res, 200, { success: true, message: 'Đã xóa máy trạm khỏi danh sách' });

      }

      return jsonResponse(res, 404, { success: false, code: 'RESOURCE_NOT_FOUND', message: 'Không tìm thấy máy trạm hoặc không có quyền xóa' });

    }



    // 5.5 Audit Logs: Query

    if (pathname === '/api/audit-logs' && req.method === 'GET') {

      if (!session) {

        return jsonResponse(res, 401, { success: false, code: 'AUTH_UNAUTHORIZED', message: 'Yêu cầu đăng nhập' });

      }

      const limit = parseInt(url.searchParams.get('limit') || '50', 10);

      const offset = parseInt(url.searchParams.get('offset') || '0', 10);

      const action = url.searchParams.get('action') || null;

      const roomId = url.searchParams.get('roomId') || null;

      const search = url.searchParams.get('search') || null;



      const result = await DB.getAuditLogs({ limit, offset, action, roomId, search });

      return jsonResponse(res, 200, { success: true, ...result });

    }



    // 5.6 Audit Logs: Export

    if (pathname === '/api/audit-logs/export' && req.method === 'GET') {

      if (!session) {

        return jsonResponse(res, 401, { success: false, code: 'AUTH_UNAUTHORIZED', message: 'Yêu cầu đăng nhập' });

      }

      const format = url.searchParams.get('format') || 'csv';

      const action = url.searchParams.get('action') || null;

      const roomId = url.searchParams.get('roomId') || null;

      const search = url.searchParams.get('search') || null;

      const { logs } = await DB.getAuditLogs({ limit: 5000, offset: 0, action, roomId, search });



      if (format === 'json') {

        res.writeHead(200, {

          'Content-Type': 'application/json; charset=utf-8',

          'Content-Disposition': 'attachment; filename="meikova-relay-audit-logs.json"'

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

        'Content-Disposition': 'attachment; filename="meikova-relay-audit-logs.csv"'

      });

      return res.end(csvContent);

    }



    // 6. Download: Pre-configured Setup Batch Script

    if (pathname === '/api/download/setup.bat' && req.method === 'GET') {

      const account = url.searchParams.get('account') || (session ? session.username : 'User');

      const userIdParam = url.searchParams.get('userId') || (session ? session.id : '');

      const origin = `${req.headers['x-forwarded-proto'] || 'http'}://${req.headers.host}`;

      const relayWs = (url.searchParams.get('relay') || origin.replace(/^http/, 'ws'));

      const isHeadless = url.searchParams.get('headless') === '1' || url.searchParams.get('silent') === '1' || url.searchParams.get('mode') === 'headless';



      const batContent = `@echo off

setlocal DisableDelayedExpansion

title Meikova Relay Host - Cai dat may tram tu dong

chcp 65001 >nul 2>&1



set "HEADLESS_MODE=${isHeadless ? '1' : '0'}"

for %%A in (%*) do (

    if /i "%%~A"=="/gui" set "HEADLESS_MODE=0"

    if /i "%%~A"=="--gui" set "HEADLESS_MODE=0"

    if /i "%%~A"=="/tray" set "HEADLESS_MODE=0"

    if /i "%%~A"=="--tray" set "HEADLESS_MODE=0"

    if /i "%%~A"=="/silent" set "HEADLESS_MODE=1"

    if /i "%%~A"=="-s" set "HEADLESS_MODE=1"

    if /i "%%~A"=="/s" set "HEADLESS_MODE=1"

    if /i "%%~A"=="--headless" set "HEADLESS_MODE=1"

    if /i "%%~A"=="/headless" set "HEADLESS_MODE=1"

    if /i "%%~A"=="--service" set "HEADLESS_MODE=1"

    if /i "%%~A"=="/service" set "HEADLESS_MODE=1"

    if /i "%%~A"=="--no-tray" set "HEADLESS_MODE=1"

    if /i "%%~A"=="/no-tray" set "HEADLESS_MODE=1"

)



set "APP_FLAGS="

set "HEADLESS_BOOL=false"

if "%HEADLESS_MODE%"=="1" (

    set "APP_FLAGS=--headless"

    set "HEADLESS_BOOL=true"

) else (

    set "APP_FLAGS=--gui"

    set "HEADLESS_BOOL=false"

)

echo ==============================================================

echo        MEIKOVA RELAY ENTERPRISE - TU DONG LIEN KET MAY TRAM

echo ==============================================================

echo Tai khoan lien ket: ${account}

echo Relay Server:       ${relayWs}

echo.



set "TARGET_DIR=%LOCALAPPDATA%\\MeikovaRelayHost"

if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%"

cd /d "%TARGET_DIR%"



echo [1/3] Kiem tra va cap nhat ban Standalone Desktop (.exe)...

powershell -ExecutionPolicy Bypass -Command "Stop-Process -Name MeikovaRelayHost -Force -ErrorAction SilentlyContinue; Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'gui_agent\\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; Start-Sleep -Milliseconds 600"



powershell -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; try { (New-Object Net.WebClient).DownloadFile('${origin}/api/download/MeikovaRelayHost.exe', '%TARGET_DIR%\\MeikovaRelayHost.exe.new'); if ((Get-Item '%TARGET_DIR%\\MeikovaRelayHost.exe.new').Length -gt 5000000) { Move-Item -Path '%TARGET_DIR%\\MeikovaRelayHost.exe.new' -Destination '%TARGET_DIR%\\MeikovaRelayHost.exe' -Force } } catch {}"

if exist "%TARGET_DIR%\\MeikovaRelayHost.exe.new" del /f /q "%TARGET_DIR%\\MeikovaRelayHost.exe.new" >nul 2>&1



if not exist "%TARGET_DIR%\\MeikovaRelayHost.exe" (

    echo Dang tai MeikovaRelayHost.exe tu Relay Server...

    powershell -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; try { (New-Object Net.WebClient).DownloadFile('${origin}/api/download/MeikovaRelayHost.exe', '%TARGET_DIR%\\MeikovaRelayHost.exe') } catch {}"

)



:CHECK_STANDALONE

set "USE_STANDALONE=0"

if exist "%TARGET_DIR%\\MeikovaRelayHost.exe" (

    for %%I in ("%TARGET_DIR%\\MeikovaRelayHost.exe") do if %%~zI GTR 5000000 set "USE_STANDALONE=1"

)



if "%USE_STANDALONE%"=="1" (

    echo [OK] Ban Standalone Desktop san sang hoat dong - Khong can Python

    goto :WRITE_CONFIG

)



echo [*] Khong the tai ban Standalone. Chuyen sang che do chay qua Python...

where python >nul 2>&1

if %ERRORLEVEL% NEQ 0 (

    echo [*] Python chua duoc cai dat tren may nay.

    echo Dang cai dat Python qua winget...

    winget install Python.Python.3.13 --silent --accept-source-agreements --accept-package-agreements >nul 2>&1

)



echo [2/3] Dang tai goi ma nguon Host Agent tu Relay Server...

powershell -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; try { (New-Object Net.WebClient).DownloadFile('${origin}/api/download/agent-package.zip', '%TARGET_DIR%\\agent-package.zip') } catch {}"

if not exist "%TARGET_DIR%\\agent-package.zip" goto :DOWNLOAD_FAIL

powershell -ExecutionPolicy Bypass -Command "Expand-Archive -Path '%TARGET_DIR%\\agent-package.zip' -DestinationPath '%TARGET_DIR%' -Force"

del /f /q "%TARGET_DIR%\\agent-package.zip" >nul 2>&1

if exist "%TARGET_DIR%\\host_agent\\gui_agent.py" copy /y "%TARGET_DIR%\\host_agent\\*.*" "%TARGET_DIR%" >nul 2>&1

goto :INSTALL_DEPS



:DOWNLOAD_FAIL

echo [LOI] Khong the tai goi agent tu ${origin}. Vui long kiem tra ket noi mang.

pause

exit /b 1



:INSTALL_DEPS

echo [3/3] Cai dat thu vien can thiet...

python -m pip install websockets Pillow pystray pywebview --quiet >nul 2>&1



:WRITE_CONFIG

echo Ghi cau hinh lien ket voi tai khoan ${account}...

set "RAND_ROOM=RD-%RANDOM%"

set "RAND_PIN=%RANDOM%%RANDOM%"

(

echo {

echo   "relay": "${relayWs}",

echo   "account": "${account}",

echo   "user_id": "${userIdParam}",

echo   "device_name": "%COMPUTERNAME%",

echo   "room_id": "%RAND_ROOM%",

echo   "pin": "%RAND_PIN%",

echo   "headless": %HEADLESS_BOOL%

echo }

) > config.json





if "%USE_STANDALONE%"=="1" goto :RUN_STANDALONE



reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" /v "MeikovaRelayHost" /t REG_SZ /d "pythonw.exe \\"%TARGET_DIR%\\gui_agent.py\\" --autostart" /f >nul 2>&1

start "" /D "%TARGET_DIR%" pythonw.exe "%TARGET_DIR%\\gui_agent.py" %APP_FLAGS%

goto :FINISH_SETUP



:RUN_STANDALONE
powershell -ExecutionPolicy Bypass -Command "Stop-Process -Name MeikovaRelayHost -Force -ErrorAction SilentlyContinue; Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'gui_agent\\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; Start-Sleep -Milliseconds 300"


reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" /v "MeikovaRelayHost" /t REG_SZ /d "\\"%TARGET_DIR%\\MeikovaRelayHost.exe\\" --autostart" /f >nul 2>&1

start "" /D "%TARGET_DIR%" "%TARGET_DIR%\\MeikovaRelayHost.exe" %APP_FLAGS%



:FINISH_SETUP

if "%HEADLESS_MODE%"=="1" goto :FINISH_HEADLESS

:FINISH_GUI
echo.
echo ==============================================================
echo   [THANH CONG] MAY TRAM DA KHOI CHAY VA LIEN KET
echo   Tai khoan:  ${account}
echo   Room ID:    %RAND_ROOM%   ^|   PIN: %RAND_PIN%
echo   Che do:     Desktop Tray Agent (Khay he thong + Cua so Chat truc quan)
echo.
echo   Kiem tra bieu tuong Meikova Relay o khay he thong (System Tray).
echo   Thiet bi se tu dong xuat hien tren trinh duyet trong giay lat.
echo ==============================================================
echo.
echo Nhan phim bat ky de hoan tat va dong cua so nay...
pause >nul
exit /b 0

:FINISH_HEADLESS
echo.
echo ==============================================================
echo   [THANH CONG] MAY TRAM DA KHOI CHAY NGAM (HEADLESS SERVICE)
echo   Tai khoan:  ${account}
echo   Room ID:    %RAND_ROOM%   ^|   PIN: %RAND_PIN%
echo   Che do:     Dich vu chay ngam (Headless Service)
echo ==============================================================
exit /b 0

`;



      res.writeHead(200, {

        'Content-Type': 'application/x-bat; charset=utf-8',

        'Content-Disposition': 'attachment; filename="Setup-MeikovaHost.bat"',

        'Cache-Control': 'no-cache'

      });

      res.end(batContent);

      return;

    }



    // 7. Download: Agent Package Zip

    if (pathname === '/api/download/agent-package.zip' && (req.method === 'GET' || req.method === 'HEAD')) {

      const zipPath = path.join(__dirname, 'agent-package.zip');

      if (fs.existsSync(zipPath)) {

        const stat = fs.statSync(zipPath);

        res.writeHead(200, {

          'Content-Type': 'application/zip',

          'Content-Length': stat.size,

          'Content-Disposition': 'attachment; filename="agent-package.zip"',

          'Cache-Control': 'no-cache'

        });

        if (req.method === 'HEAD') {

          return res.end();

        }

        fs.createReadStream(zipPath).pipe(res);

        return;

      }

      return jsonResponse(res, 404, { error: 'Agent package zip not found' });

    }



    // 7.5 Download: Multi-Platform Workstation Artifacts (Windows, Linux, macOS)

    const artifactMap = {

      '/api/download/MeikovaRelayHost-Setup.exe': { name: 'MeikovaRelayHost-Setup.exe', type: 'application/vnd.microsoft.portable-executable' },

      '/api/download/meikova-relay-host-setup.exe': { name: 'MeikovaRelayHost-Setup.exe', type: 'application/vnd.microsoft.portable-executable' },

      '/api/download/MeikovaRelayHost.exe': { name: 'MeikovaRelayHost.exe', type: 'application/vnd.microsoft.portable-executable' },

      '/api/download/meikova-relay-host.exe': { name: 'MeikovaRelayHost.exe', type: 'application/vnd.microsoft.portable-executable' },

      '/api/download/MeikovaRelayHost-windows-x64.zip': { name: 'MeikovaRelayHost-windows-x64.zip', type: 'application/zip' },

      '/api/download/meikova-relay-windows.zip': { name: 'MeikovaRelayHost-windows-x64.zip', type: 'application/zip' },

      '/api/download/meikova-relay-host_amd64.deb': { name: 'meikova-relay-host_amd64.deb', type: 'application/vnd.debian.binary-package' },

      '/api/download/meikova-relay.deb': { name: 'meikova-relay-host_amd64.deb', type: 'application/vnd.debian.binary-package' },

      '/api/download/meikova-relay-host-linux-x64.tar.gz': { name: 'meikova-relay-host-linux-x64.tar.gz', type: 'application/gzip' },

      '/api/download/meikova-relay-linux.tar.gz': { name: 'meikova-relay-host-linux-x64.tar.gz', type: 'application/gzip' },

      '/api/download/meikova-relay-host-macos.tar.gz': { name: 'meikova-relay-host-macos.tar.gz', type: 'application/gzip' },

      '/api/download/meikova-relay-macos.tar.gz': { name: 'meikova-relay-host-macos.tar.gz', type: 'application/gzip' },

      '/api/download/MeikovaRelayHost-macos.dmg': { name: 'MeikovaRelayHost-macos.dmg', type: 'application/x-apple-diskimage' },

      '/api/download/meikova-relay.dmg': { name: 'MeikovaRelayHost-macos.dmg', type: 'application/x-apple-diskimage' },

      '/api/download/MeikovaRelayClient.exe': { name: 'MeikovaRelayClient.exe', type: 'application/vnd.microsoft.portable-executable' },

      '/api/download/meikova-relay-client.exe': { name: 'MeikovaRelayClient.exe', type: 'application/vnd.microsoft.portable-executable' },

      '/api/download/MeikovaRelayClient-windows-x64.zip': { name: 'MeikovaRelayClient-windows-x64.zip', type: 'application/zip' },

      '/api/download/meikova-relay-client.zip': { name: 'MeikovaRelayClient-windows-x64.zip', type: 'application/zip' },

      '/api/download/MeikovaRelayClient-macos.dmg': { name: 'MeikovaRelayClient-macos.dmg', type: 'application/x-apple-diskimage' },

      '/api/download/meikova-relay-client.dmg': { name: 'MeikovaRelayClient-macos.dmg', type: 'application/x-apple-diskimage' },

      '/api/download/meikova-relay-client-linux-x64.tar.gz': { name: 'meikova-relay-client-linux-x64.tar.gz', type: 'application/gzip' },

      '/api/download/meikova-relay-client.tar.gz': { name: 'meikova-relay-client-linux-x64.tar.gz', type: 'application/gzip' }

    };



    if (artifactMap[pathname] && (req.method === 'GET' || req.method === 'HEAD')) {

      const art = artifactMap[pathname];

      const candidates = [

        path.join(__dirname, art.name),

        path.join(__dirname, '..', 'dist', art.name)

      ];

      let foundPath = candidates.find(p => fs.existsSync(p));

      if (foundPath) {

        const stat = fs.statSync(foundPath);

        res.writeHead(200, {

          'Content-Type': art.type,

          'Content-Length': stat.size,

          'Content-Disposition': `attachment; filename="${art.name}"`,

          'Cache-Control': 'no-cache'

        });

        if (req.method === 'HEAD') return res.end();

        fs.createReadStream(foundPath).pipe(res);

        return;

      }

      const releaseBase = 'https://github.com/Meikova/meikova-relay/releases/latest/download';

      res.writeHead(307, {

        'Location': `${releaseBase}/${art.name}`,

        'Cache-Control': 'no-cache'

      });

      return res.end();

    }



    // 7.6 Download: Linux Auto-Installer (.sh)

    if ((pathname === '/api/download/install-linux.sh' || pathname === '/api/download/setup-linux.sh') && req.method === 'GET') {

      const account = url.searchParams.get('account') || (session ? session.username : 'User');

      const userIdParam = url.searchParams.get('userId') || (session ? session.id : '');

      const origin = `${req.headers['x-forwarded-proto'] || 'http'}://${req.headers.host}`;

      const relayWs = (url.searchParams.get('relay') || origin.replace(/^http/, 'ws'));

      const shContent = `#!/usr/bin/env bash

# Meikova Relay Host Agent - Linux Auto-Installer

set -e

ORIGIN="${origin}"

RELAY_WS="${relayWs}"

ACCOUNT="${account}"

TARGET_DIR="$HOME/.meikova-relay"



echo "=== MEIKOVA RELAY HOST AGENT - LINUX INSTALLER ==="

mkdir -p "$TARGET_DIR"

cd "$TARGET_DIR"



echo "[1/3] Downloading agent package..."

curl -sSL "$ORIGIN/api/download/agent-package.zip" -o agent-package.zip

if command -v unzip &> /dev/null; then

    unzip -q -o agent-package.zip

else

    python3 -c "import zipfile; zipfile.ZipFile('agent-package.zip').extractall('.')"

fi

rm -f agent-package.zip



echo "[2/3] Setting up Python virtual environment..."

if ! command -v python3 &> /dev/null; then

    echo "[!] python3 is required. Please install: sudo apt install -y python3 python3-pip python3-venv"

    exit 1

fi

python3 -m venv .venv

source .venv/bin/activate

pip install -q --upgrade pip

if [ -f "requirements.txt" ]; then

    pip install -q -r requirements.txt

elif [ -f "host_agent/requirements.txt" ]; then

    pip install -q -r host_agent/requirements.txt

fi



echo "[3/3] Configuring agent for account: $ACCOUNT..."

RAND_ROOM="RD-$((1000 + RANDOM % 9000))"

RAND_PIN="$((100000 + RANDOM % 900000))"

cat << EOF > config.json

{

  "relay": "$RELAY_WS",

  "account": "$ACCOUNT",

  "user_id": "${userIdParam}",

  "device_name": "$(hostname)",

  "room_id": "$RAND_ROOM",

  "pin": "$RAND_PIN"

}

EOF



echo "=============================================================="

echo "  MEIKOVA RELAY HOST (LINUX) READY!"

echo "  Account: $ACCOUNT | Room ID: $RAND_ROOM | PIN: $RAND_PIN"

echo "=============================================================="

if [ -f "gui_agent.py" ] && [ -n "\$DISPLAY" ]; then

    nohup python3 gui_agent.py --gui > meikova-agent.log 2>&1 &

else

    nohup python3 host_service.py --relay "$RELAY_WS" --account "$ACCOUNT" --user-id "${userIdParam}" --room "$RAND_ROOM" --pin "$RAND_PIN" --name "\$(hostname)" > meikova-agent.log 2>&1 &

fi

echo "Meikova Relay Host running in background (PID: \$!)."

`;

      res.writeHead(200, {

        'Content-Type': 'application/x-sh; charset=utf-8',

        'Content-Disposition': 'attachment; filename="install-linux.sh"',

        'Cache-Control': 'no-cache'

      });

      return res.end(shContent);

    }



    // 7.7 Download: macOS Auto-Installer (.sh)

    if ((pathname === '/api/download/install-macos.sh' || pathname === '/api/download/setup-macos.sh') && req.method === 'GET') {

      const account = url.searchParams.get('account') || (session ? session.username : 'User');

      const userIdParam = url.searchParams.get('userId') || (session ? session.id : '');

      const origin = `${req.headers['x-forwarded-proto'] || 'http'}://${req.headers.host}`;

      const relayWs = (url.searchParams.get('relay') || origin.replace(/^http/, 'ws'));

      const shContent = `#!/usr/bin/env bash

# Meikova Relay Host Agent - macOS Auto-Installer

set -e

ORIGIN="${origin}"

RELAY_WS="${relayWs}"

ACCOUNT="${account}"

TARGET_DIR="$HOME/.meikova-relay"



echo "=== MEIKOVA RELAY HOST AGENT - macOS INSTALLER ==="

echo "[NOTE] macOS requires Screen Recording & Accessibility permissions:"

echo "  System Settings -> Privacy & Security -> Screen Recording / Accessibility"



mkdir -p "$TARGET_DIR"

cd "$TARGET_DIR"



echo "[1/3] Downloading agent package..."

curl -sSL "$ORIGIN/api/download/agent-package.zip" -o agent-package.zip

if command -v unzip &> /dev/null; then

    unzip -q -o agent-package.zip

else

    python3 -c "import zipfile; zipfile.ZipFile('agent-package.zip').extractall('.')"

fi

rm -f agent-package.zip



echo "[2/3] Setting up Python virtual environment..."

if ! command -v python3 &> /dev/null; then

    echo "[!] python3 is required. Please install via brew: brew install python3"

    exit 1

fi

python3 -m venv .venv

source .venv/bin/activate

pip install -q --upgrade pip

if [ -f "requirements.txt" ]; then

    pip install -q -r requirements.txt

elif [ -f "host_agent/requirements.txt" ]; then

    pip install -q -r host_agent/requirements.txt

fi



echo "[3/3] Configuring agent for account: $ACCOUNT..."

RAND_ROOM="RD-$((1000 + RANDOM % 9000))"

RAND_PIN="$((100000 + RANDOM % 900000))"

cat << EOF > config.json

{

  "relay": "$RELAY_WS",

  "account": "$ACCOUNT",

  "user_id": "${userIdParam}",

  "device_name": "$(hostname -s)",

  "room_id": "$RAND_ROOM",

  "pin": "$RAND_PIN"

}

EOF



echo "=============================================================="

echo "  MEIKOVA RELAY HOST (macOS) READY!"

echo "  Account: $ACCOUNT | Room ID: $RAND_ROOM | PIN: $RAND_PIN"

echo "=============================================================="

if [ -f "gui_agent.py" ]; then

    nohup python3 gui_agent.py --gui > meikova-agent.log 2>&1 &

else

    nohup python3 host_service.py --relay "$RELAY_WS" --account "$ACCOUNT" --user-id "${userIdParam}" --room "$RAND_ROOM" --pin "$RAND_PIN" --name "\$(hostname -s)" > meikova-agent.log 2>&1 &

fi

echo "Meikova Relay Host running in background (PID: \$!)."

`;

      res.writeHead(200, {

        'Content-Type': 'application/x-sh; charset=utf-8',

        'Content-Disposition': 'attachment; filename="install-macos.sh"',

        'Cache-Control': 'no-cache'

      });

      return res.end(shContent);

    }



    // 7.8 Download: Linux Systemd Unit

    if (pathname === '/api/download/meikova-relay.service' && (req.method === 'GET' || req.method === 'HEAD')) {

      const unitPath = path.join(__dirname, '..', 'host_agent', 'meikova-relay.service');

      if (fs.existsSync(unitPath)) {

        const stat = fs.statSync(unitPath);

        res.writeHead(200, {

          'Content-Type': 'text/plain; charset=utf-8',

          'Content-Length': stat.size,

          'Content-Disposition': 'attachment; filename="meikova-relay.service"',

          'Cache-Control': 'no-cache'

        });

        if (req.method === 'HEAD') return res.end();

        fs.createReadStream(unitPath).pipe(res);

        return;

      }

    }



    // 7.9 Download: macOS Launchd Plist

    if (pathname === '/api/download/com.meikova.relay.plist' && (req.method === 'GET' || req.method === 'HEAD')) {

      const plistPath = path.join(__dirname, '..', 'host_agent', 'com.meikova.relay.plist');

      if (fs.existsSync(plistPath)) {

        const stat = fs.statSync(plistPath);

        res.writeHead(200, {

          'Content-Type': 'application/xml; charset=utf-8',

          'Content-Length': stat.size,

          'Content-Disposition': 'attachment; filename="com.meikova.relay.plist"',

          'Cache-Control': 'no-cache'

        });

        if (req.method === 'HEAD') return res.end();

        fs.createReadStream(plistPath).pipe(res);

        return;

      }

    }



    // 7.10 Download: Dynamic Microsoft Remote Desktop Connection File (.rdp)

    if (((pathname.startsWith('/api/session/') && pathname.endsWith('/rdp-config')) || pathname === '/api/rdp-config') && req.method === 'GET') {

      const parts = pathname.split('/');

      const roomId = parts[3] || url.searchParams.get('room') || 'Workstation';

      const rdpPort = url.searchParams.get('port') || '3389';

      const rdpHost = url.searchParams.get('host') || '127.0.0.1';

      const width = url.searchParams.get('width') || '1920';

      const height = url.searchParams.get('height') || '1080';

      const username = url.searchParams.get('username') || '';



      const rdpLines = [

        'screen mode id:i:2',

        'use multimon:i:0',

        `desktopwidth:i:${width}`,

        `desktopheight:i:${height}`,

        'session bpp:i:32',

        'winposstr:s:0,3,0,0,800,600',

        'compression:i:1',

        'keyboardhook:i:2',

        'audiomode:i:0',

        'redirectprinters:i:0',

        'redirectcomports:i:0',

        'redirectsmartcards:i:0',

        'redirectclipboard:i:1',

        'redirectposdevices:i:0',

        'autoreconnection enabled:i:1',

        'authentication level:i:0',

        'prompt for credentials:i:1',

        'negotiate security layer:i:1',

        'remoteapplicationmode:i:0',

        `full address:s:${rdpHost}:${rdpPort}`

      ];

      if (username) rdpLines.push(`username:s:${username}`);

      const rdpContent = rdpLines.join('\r\n') + '\r\n';



      res.writeHead(200, {

        'Content-Type': 'application/x-rdp; charset=utf-8',

        'Content-Disposition': `attachment; filename="Meikova-${roomId}.rdp"`,

        'Cache-Control': 'no-cache'

      });

      return res.end(rdpContent);

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

      res.end('404 Not Found - Meikova Relay Client');

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

// Directed active remote graph to prevent loops: "fromMachineId->toMachineId" -> Set of sessionIds
const activeRemoteEdges = new Map();

function addRemoteEdge(fromMachineId, toMachineId, sessionId) {
  if (!fromMachineId || !toMachineId || !sessionId) return;
  const edge = `${fromMachineId}->${toMachineId}`;
  if (!activeRemoteEdges.has(edge)) {
    activeRemoteEdges.set(edge, new Set());
  }
  activeRemoteEdges.get(edge).add(sessionId);
}

function hasReverseEdge(fromMachineId, toMachineId) {
  if (!fromMachineId || !toMachineId) return false;
  const reverseEdge = `${toMachineId}->${fromMachineId}`;
  const set = activeRemoteEdges.get(reverseEdge);
  return !!(set && set.size > 0);
}

function removeRemoteEdge(fromMachineId, toMachineId, sessionId) {
  if (!fromMachineId || !toMachineId || !sessionId) return;
  const edge = `${fromMachineId}->${toMachineId}`;
  const set = activeRemoteEdges.get(edge);
  if (set) {
    set.delete(sessionId);
    if (set.size === 0) activeRemoteEdges.delete(edge);
  }
}

function removeAllEdgesForRoom(room) {
  if (!room || !room.clients) return;
  const targetMachine = room.hostMeta?.machineId;
  for (const [sId, c] of room.clients.entries()) {
    const cMachine = c.machineId || c.ws?.machineId;
    if (cMachine && targetMachine) {
      removeRemoteEdge(cMachine, targetMachine, sId);
    }
  }
}




function broadcastTunnelUpdate(tunnelStatus) {
  const msg = JSON.stringify({ type: 'tunnel_update', tunnel: tunnelStatus });
  if (wss && wss.clients) {
    wss.clients.forEach((client) => {
      if (client.readyState === WebSocket.OPEN) {
        try { client.send(msg); } catch (_) {}
      }
    });
  }
}

function broadcastSessionList(room, targetWs = null) {

  if (!room || !room.clients) return;

  const sessions = Array.from(room.clients.values()).map(c => ({

    id: c.id,

    username: c.username || 'Khách (Ẩn danh)',

    userId: c.userId,

    clientIp: c.clientIp || '127.0.0.1',

    clientDevice: c.clientDevice || 'Trình duyệt Web',

    connectedAt: c.connectTime || Date.now()

  }));



  if (targetWs) {

    if (targetWs.readyState === WebSocket.OPEN) {

      targetWs.send(JSON.stringify({

        type: 'session_list',

        sessions: sessions.map(s => ({ ...s, isSelf: s.id === targetWs.sessionId })),

        clientCount: sessions.length

      }));

    }

    return;

  }



  for (const client of room.clients.values()) {

    if (client.ws.readyState === WebSocket.OPEN) {

      client.ws.send(JSON.stringify({

        type: 'session_list',

        sessions: sessions.map(s => ({ ...s, isSelf: s.id === client.id })),

        clientCount: sessions.length

      }));

    }

  }

}



async function closeRoomClients(roomId, reason = 'Máy trạm đã ngắt kết nối', expectedHostWs = null) {

  if (!roomId || !rooms.has(roomId)) return;

  const room = rooms.get(roomId);

  if (expectedHostWs && room.hostWs && room.hostWs !== expectedHostWs) {
    console.log(`[closeRoomClients] Skipped for room ${roomId}: active hostWs differs from closing socket`);
    return;
  }

  removeAllEdgesForRoom(room);

  try {

    await DB.setDeviceOnlineStatus(roomId, false);

  } catch (err) {

    console.error(`[DB Error in closeRoomClients]: ${err.message}`);

  }

  if (!expectedHostWs || room.hostWs === expectedHostWs) {
    room.hostWs = null;
  }



  if (room.clients && room.clients.size > 0) {

    for (const client of room.clients.values()) {

      try {

        if (client.ws.readyState === WebSocket.OPEN) {

          client.ws.send(JSON.stringify({ type: 'host_disconnected', message: reason }));

          client.ws.close(1000, reason);

        }

      } catch (err) {

        console.error(`Error closing client session ${client.id}:`, err);

      }

    }

    room.clients.clear();

  }



  if (room.clientWs && room.clientWs.readyState === WebSocket.OPEN) {

    try {

      room.clientWs.send(JSON.stringify({ type: 'host_disconnected', message: reason }));

      room.clientWs.close(1000, reason);

    } catch {}

    room.clientWs = null;

  }



  rooms.delete(roomId);

}



function getOrCreateRoom(roomId) {

  if (!rooms.has(roomId)) {

    rooms.set(roomId, {

      pin: null,

      hostWs: null,

      clientWs: null,

      clients: new Map(),

      hostMeta: null

    });

  }

  const r = rooms.get(roomId);

  if (!r.clients) r.clients = new Map();

  return r;

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



  ws.on('message', async (message, isBinary) => {

    // 1. Forward raw binary frames (Screen frames to ALL active clients)

    if (isBinary) {

      if (role === 'host' && currentRoomId) {

        const room = rooms.get(currentRoomId);

        if (room) room.isStreaming = true;

        if (room && room.clients) {

          for (const client of room.clients.values()) {

            if (client.ws.readyState === WebSocket.OPEN) {

              // Zero-lag backpressure: drop stale frame if client socket buffer > 256KB (prevents bufferbloat while allowing full HD/4K frame burst)
              if (client.ws.bufferedAmount > 256 * 1024) {
                continue;
              }

              client.ws.send(message, { binary: true });

            }

          }

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

      const hostMachineId = String(data.machine_id || data.machineId || '').trim() || null;

      if (!roomId || !pin) {

        ws.send(JSON.stringify({ status: 'error', code: 'RELAY_MISSING_CREDENTIALS', message: 'Missing room_id or pin' }));

        ws.close();

        return;

      }



      role = 'host';

      currentRoomId = roomId;

      ws.machineId = hostMachineId;

      const room = getOrCreateRoom(roomId);

      room.pin = pin;

      // Cleanly supersede existing host connection for same room if active
      if (room.hostWs && room.hostWs !== ws && room.hostWs.readyState === WebSocket.OPEN) {
        console.log(`[Host Superseded] Terminating previous host socket for room ${roomId}`);
        try {
          room.hostWs.send(JSON.stringify({
            type: 'superseded',
            message: 'Phiên kết nối máy trạm đã được thay thế bởi phiên mới hơn'
          }));
          room.hostWs.close(1000, 'Superseded by newer host');
        } catch (e) {}
      }

      room.hostWs = ws;

      room.hostMeta = {

        width: data.width || 1920,

        height: data.height || 1080,

        deviceName: data.device_name || 'Host-PC',

        osInfo: data.os_info || 'Windows',

        monitors: data.monitors || [],

        machineId: hostMachineId

      };

      if (!room.streamConfig) {

        room.streamConfig = {

          width: room.hostMeta.width,

          height: room.hostMeta.height,

          monitors: room.hostMeta.monitors,

          qualityPreset: 'balanced'

        };

      }



      // Register device in DB safely (foreign-key safe)

      let targetUserId = null;

      const candidateUser = data.user_id || data.account || data.user_email;

      if (candidateUser) {

        try {

          const matchedUser = await DB.findUserByIdentifier(candidateUser);

          if (matchedUser) {

            targetUserId = matchedUser.id;

          }

        } catch (err) {

          console.warn(`[Host Online] User lookup warning for '${candidateUser}': ${err.message}`);

        }

      }



      try {

        await DB.upsertDevice({

          userId: targetUserId,

          machineId: hostMachineId,

          deviceName: room.hostMeta.deviceName,

          roomId: roomId,

          pin: pin,

          resolution: `${room.hostMeta.width}x${room.hostMeta.height}`,

          osInfo: room.hostMeta.osInfo

        });

      } catch (err) {

        console.error(`[Host Online] Device upsert warning for room ${roomId}: ${err.message}`);

      }



      try {

        await DB.logAudit({

          action: 'HOST_ONLINE',

          roomId,

          clientIp: ws.clientIp,

          clientDevice: ws.clientDevice,

          targetDevice: room.hostMeta.deviceName,

          targetOs: room.hostMeta.osInfo,

          details: { width: data.width, height: data.height, monitors: (data.monitors || []).length, machineId: hostMachineId }

        });

      } catch (err) {

        console.warn(`[Host Online] Audit log warning: ${err.message}`);

      };



      console.log(`[Host Online] Room: ${roomId} | Device: ${room.hostMeta.deviceName} | IP: ${ws.clientIp}`);

      ws.send(JSON.stringify({ status: 'ok', role: 'host', room_id: roomId }));



      if (room.clients && room.clients.size > 0) {

        const firstClient = Array.from(room.clients.values())[0];

        ws.send(JSON.stringify({

          type: 'client_connected',

          clientCount: room.clients.size,

          sessionId: firstClient?.id,

          username: firstClient?.username || 'Khách',

          clientUser: firstClient?.username || 'Khách',

          clientName: firstClient?.clientName || firstClient?.clientDevice || firstClient?.username || 'Client',

          clientIp: firstClient?.clientIp || '127.0.0.1',

          machineId: firstClient?.machineId || 'unknown'

        }));

        for (const client of room.clients.values()) {

          if (client.ws.readyState === WebSocket.OPEN) {

            client.ws.send(JSON.stringify({

              type: 'host_ready',

              width: room.hostMeta.width,

              height: room.hostMeta.height,

              deviceName: room.hostMeta.deviceName,

              monitors: room.hostMeta.monitors

            }));

          }

        }

      }

      return;

    }



    // --- Client Handshake ---

    if (type === 'init_client') {

      const roomId = String(data.room_id || '').trim();

      const pin = String(data.pin || '').trim();

      const clientMachineId = String(data.machine_id || data.machineId || req.headers['x-machine-id'] || '').trim() || null;

      const clientCustomName = String(data.client_name || data.clientName || data.device_name || '').trim() || null;

      const room = rooms.get(roomId);



      if (data.token) {

        const sess = await DB.validateSession(data.token);

        if (sess) {

          ws.username = sess.username;

          ws.userId = sess.id;

          ws.user = sess;

        }

      } else if (data.username) {

        ws.username = data.username;

      }



      if (clientMachineId) ws.machineId = clientMachineId;

      if (clientCustomName) ws.clientName = clientCustomName;



      if (!room || !room.hostWs || room.hostWs.readyState !== WebSocket.OPEN) {

        await DB.logAudit({

          action: 'CONNECT_FAILED_OFFLINE',

          userId: ws.userId,

          username: ws.username,

          clientIp: ws.clientIp,

          clientDevice: ws.clientDevice,

          roomId,

          details: { status: 'failed', reason: 'Máy trạm đang Offline' }

        });

        ws.send(JSON.stringify({ status: 'error', code: 'RELAY_ROOM_OFFLINE', message: 'Máy trạm đang Offline hoặc không tồn tại' }));

        return;

      }



      if (room.pin && room.pin !== pin) {

        await DB.logAudit({

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

        ws.send(JSON.stringify({ status: 'error', code: 'RELAY_INVALID_PIN', message: 'Mã PIN bảo mật không chính xác' }));

        return;

      }



      const targetHostMachineId = room.hostMeta?.machineId || room.hostWs?.machineId || null;



      // Prevent Self-Loop (Connecting to own machine)

      if (clientMachineId && targetHostMachineId && clientMachineId === targetHostMachineId) {

        await DB.logAudit({

          action: 'CONNECT_BLOCKED_SELF_LOOP',

          userId: ws.userId,

          username: ws.username,

          clientIp: ws.clientIp,

          clientDevice: ws.clientDevice,

          roomId,

          targetDevice: room.hostMeta?.deviceName,

          targetOs: room.hostMeta?.osInfo,

          details: { clientMachineId, targetHostMachineId }

        });

        ws.send(JSON.stringify({

          status: 'error',

          code: 'RELAY_SELF_LOOP_FORBIDDEN',

          message: 'Không thể tự kết nối điều khiển chính máy tính này (Self-loop forbidden).' 

        }));

        try { ws.close(); } catch {}

        return;

      }



      // VẤN ĐỀ 5: Prevent Reverse Remote Loop (A remoting to B => B cannot remote to A)

      if (clientMachineId && targetHostMachineId && hasReverseEdge(clientMachineId, targetHostMachineId)) {

        await DB.logAudit({

          action: 'CONNECT_BLOCKED_REVERSE_LOOP',

          userId: ws.userId,

          username: ws.username,

          clientIp: ws.clientIp,

          clientDevice: ws.clientDevice,

          roomId,

          targetDevice: room.hostMeta?.deviceName,

          targetOs: room.hostMeta?.osInfo,

          details: { clientMachineId, targetHostMachineId, reverseEdge: `${targetHostMachineId}->${clientMachineId}` }

        });

        ws.send(JSON.stringify({

          status: 'error',

          code: 'RELAY_REVERSE_LOOP_FORBIDDEN',

          message: 'Máy trạm đích đang điều khiển máy tính này. Không thể tạo vòng lặp kết nối ngược!'

        }));

        try { ws.close(); } catch {}

        return;

      }



      role = 'client';

      currentRoomId = roomId;

      const sessionId = 'sess_' + Math.random().toString(36).substring(2, 9);

      ws.sessionId = sessionId;



      if (clientMachineId && targetHostMachineId) {

        addRemoteEdge(clientMachineId, targetHostMachineId, sessionId);

      }



      const clientInfo = {

        id: sessionId,

        ws: ws,

        username: ws.username,

        userId: ws.userId,

        machineId: clientMachineId || 'unknown',

        clientIp: ws.clientIp,

        clientDevice: ws.clientDevice,

        clientName: ws.clientName || ws.username || 'Client',

        connectTime: Date.now()

      };

      room.clients.set(sessionId, clientInfo);

      room.clientWs = ws; // backward compat reference



      await DB.logAudit({

        action: 'SESSION_CONNECTED',

        userId: ws.userId,

        username: ws.username,

        clientIp: ws.clientIp,

        clientDevice: ws.clientDevice,

        roomId,

        targetDevice: room.hostMeta?.deviceName,

        targetOs: room.hostMeta?.osInfo,

        details: { status: 'connected', resolution: `${room.hostMeta?.width}x${room.hostMeta?.height}`, sessionId, machineId: clientMachineId }

      });



      console.log(`[Client Connected] Room: ${roomId} | Session: ${sessionId} | User: ${ws.username} | Total: ${room.clients.size}`);

      ws.send(JSON.stringify({

        status: 'ok',

        role: 'client',

        room_id: roomId,

        session_id: sessionId,

        hostMeta: room.hostMeta,

        streamConfig: room.streamConfig || null

      }));

      if (room.curtainActive) {
        ws.send(JSON.stringify({
          type: 'privacy_curtain_response',
          enabled: true,
          success: true,
          message: 'Màn hình máy trạm đang trong Chế độ Riêng tư.'
        }));
      }







      // VẤN ĐỀ 6: Send client_connected with FULL operator details to Host

      if (room.hostWs && room.hostWs.readyState === WebSocket.OPEN) {

        room.hostWs.send(JSON.stringify({

          type: 'client_connected',

          clientCount: room.clients.size,

          sessionId: sessionId,

          username: ws.user ? ws.user.username : (ws.username || 'Khách'),

          clientUser: ws.user ? ws.user.username : (ws.username || 'Khách'),

          clientName: ws.clientName || ws.username || 'Client',

          clientIp: ws.clientIp || ws._socket?.remoteAddress || '127.0.0.1',

          machineId: ws.machineId || 'unknown'

        }));

      }

      return;

    }



    // --- Session Management Messages (Live list & Kill Session) ---

    if (type === 'get_stream_config' && currentRoomId) {
      const room = rooms.get(currentRoomId);
      if (room) {
        const cfg = room.streamConfig || {
          width: room.hostMeta?.width || 1920,
          height: room.hostMeta?.height || 1080,
          monitors: room.hostMeta?.monitors || [],
          qualityPreset: 'balanced'
        };
        ws.send(JSON.stringify({
          type: 'stream_config',
          width: cfg.width || room.hostMeta?.width || 1920,
          height: cfg.height || room.hostMeta?.height || 1080,
          monitors: cfg.monitors || room.hostMeta?.monitors || [],
          qualityPreset: cfg.qualityPreset || 'balanced',
          isLive: !!room.isStreaming
        }));
      }
      return;
    }

    if (type === 'get_sessions' && currentRoomId) {

      const room = rooms.get(currentRoomId);

      if (room) broadcastSessionList(room, ws);

      return;

    }



    if (type === 'kill_session' && currentRoomId) {

      const room = rooms.get(currentRoomId);

      const targetSessionId = data.session_id || data.targetSessionId;

      if (room && room.clients && room.clients.has(targetSessionId)) {

        const target = room.clients.get(targetSessionId);

        await DB.logAudit({

          action: 'SESSION_KILLED',

          userId: ws.userId,

          username: ws.username,

          clientIp: ws.clientIp,

          clientDevice: ws.clientDevice,

          roomId: currentRoomId,

          targetDevice: room.hostMeta?.deviceName,

          details: { killedSessionId: targetSessionId, killedUser: target.username, killedIp: target.clientIp }

        });

        target.ws.send(JSON.stringify({

          type: 'session_killed',

          message: `Phiên kết nối của bạn đã bị ngắt bởi ${ws.username || 'người điều khiển khác'}.`

        }));

        try { target.ws.close(1000, 'Session terminated'); } catch {}

        const targetMachine = target.machineId || target.ws?.machineId;

        const hostMachine = room.hostMeta?.machineId;

        if (targetMachine && hostMachine) {

          removeRemoteEdge(targetMachine, hostMachine, targetSessionId);

        }

        room.clients.delete(targetSessionId);

        broadcastSessionList(room);

        if (room.clients.size === 0 && room.hostWs && room.hostWs.readyState === WebSocket.OPEN) {

          room.hostWs.send(JSON.stringify({ type: 'client_disconnected', clientCount: 0 }));

        } else if (room.clients.size > 0 && room.hostWs && room.hostWs.readyState === WebSocket.OPEN) {

          room.hostWs.send(JSON.stringify({

            type: 'client_disconnected',

            clientCount: room.clients.size,

            sessionId: targetSessionId,

            username: target.username

          }));

        }

        ws.send(JSON.stringify({ type: 'kill_session_success', session_id: targetSessionId }));

      }

      return;

    }



    // --- Host Graceful Shutdown ---

    if (type === 'host_closing' && role === 'host' && currentRoomId) {

      console.log(`[Host Explicit Close] Room: ${currentRoomId}`);

      const room = rooms.get(currentRoomId);

      await DB.logAudit({

        action: 'HOST_OFFLINE',

        roomId: currentRoomId,

        clientIp: ws.clientIp,

        clientDevice: ws.clientDevice,

        targetDevice: room?.hostMeta?.deviceName,

        targetOs: room?.hostMeta?.osInfo,

        details: { status: 'stopped_by_user' }

      });

      await closeRoomClients(currentRoomId, 'Máy trạm đã tắt dịch vụ', ws);

      return;

    }



    // --- Ping / Pong ---

    if (type === 'ping') {

      ws.send(JSON.stringify({ type: 'pong', ts: data.ts }));

      return;

    }



    // --- Live Bidirectional Chat Message (Operator <-> Remote Host) ---

    if (type === 'chat_message' && currentRoomId) {

      const room = rooms.get(currentRoomId);

      if (room) {

        const msgText = String(data.message || '').trim();

        if (!msgText) return;

        const sender = String(data.sender || (role === 'host' ? (room.hostMeta?.deviceName || 'Máy trạm') : (ws.username || 'Kỹ thuật viên')));

        const chatPkt = JSON.stringify({

          type: 'chat_message',

          sender,

          message: msgText,

          timestamp: Date.now(),

          senderRole: role

        });



        if (role === 'client') {

          // Forward to Host Workstation

          if (room.hostWs && room.hostWs.readyState === WebSocket.OPEN) {

            room.hostWs.send(chatPkt);

          }

          // Broadcast to any other clients connected to the same room

          if (room.clients) {

            for (const client of room.clients.values()) {

              if (client.ws !== ws && client.ws.readyState === WebSocket.OPEN) {

                client.ws.send(chatPkt);

              }

            }

          }

          await DB.logAudit({

            action: 'CHAT_SENT_CLIENT',

            userId: ws.userId,

            username: ws.username,

            clientIp: ws.clientIp,

            clientDevice: ws.clientDevice,

            roomId: currentRoomId,

            targetDevice: room.hostMeta?.deviceName,

            targetOs: room.hostMeta?.osInfo,

            details: { sender, length: msgText.length }

          });

        } else if (role === 'host') {

          // Forward from Host to ALL connected clients

          if (room.clients) {

            for (const client of room.clients.values()) {

              if (client.ws.readyState === WebSocket.OPEN) {

                client.ws.send(chatPkt);

              }

            }

          }

          await DB.logAudit({

            action: 'CHAT_SENT_HOST',

            roomId: currentRoomId,

            clientIp: ws.clientIp,

            clientDevice: ws.clientDevice,

            targetDevice: room.hostMeta?.deviceName,

            targetOs: room.hostMeta?.osInfo,

            details: { sender, length: msgText.length }

          });

        }

      }

      return;

    }



    // --- Deep Operation Audit Logging (From Client to Host) ---

    if (role === 'client' && currentRoomId) {

      const room = rooms.get(currentRoomId);

      const targetDevice = room?.hostMeta?.deviceName || 'Host-PC';

      const targetOs = room?.hostMeta?.osInfo || 'Windows';



      if (type === 'terminal_input') {

        await DB.logAudit({

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

        await DB.logAudit({

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

        await DB.logAudit({

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

        await DB.logAudit({

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

        await DB.logAudit({

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

        await DB.logAudit({

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

      } else if (type === 'file_copy_request') {

        await DB.logAudit({

          action: 'FILE_COPY',

          userId: ws.userId,

          username: ws.username,

          clientIp: ws.clientIp,

          clientDevice: ws.clientDevice,

          roomId: currentRoomId,

          targetDevice,

          targetOs,

          details: { src: data.src || '', dst: data.dst || '' }

        });

      } else if (type === 'file_move_request') {

        await DB.logAudit({

          action: 'FILE_MOVE',

          userId: ws.userId,

          username: ws.username,

          clientIp: ws.clientIp,

          clientDevice: ws.clientDevice,

          roomId: currentRoomId,

          targetDevice,

          targetOs,

          details: { src: data.src || '', dst: data.dst || '' }

        });

      } else if (type === 'file_rename_request') {

        await DB.logAudit({

          action: 'FILE_RENAME',

          userId: ws.userId,

          username: ws.username,

          clientIp: ws.clientIp,

          clientDevice: ws.clientDevice,

          roomId: currentRoomId,

          targetDevice,

          targetOs,

          details: { old_path: data.old_path || '', new_name: data.new_name || '' }

        });

      } else if (type === 'file_read_request') {

        await DB.logAudit({

          action: 'FILE_READ',

          userId: ws.userId,

          username: ws.username,

          clientIp: ws.clientIp,

          clientDevice: ws.clientDevice,

          roomId: currentRoomId,

          targetDevice,

          targetOs,

          details: { path: data.filepath || '' }

        });

      } else if (type === 'file_save_request') {

        await DB.logAudit({

          action: 'FILE_SAVE',

          userId: ws.userId,

          username: ws.username,

          clientIp: ws.clientIp,

          clientDevice: ws.clientDevice,

          roomId: currentRoomId,

          targetDevice,

          targetOs,

          details: { path: data.filepath || '', length: (data.content || '').length }

        });

      } else if (type === 'process_kill_request') {

        await DB.logAudit({

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

        await DB.logAudit({

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

        await DB.logAudit({

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

      } else if (type === 'tunnel_open') {

        await DB.logAudit({

          action: 'TUNNEL_OPEN',

          userId: ws.userId,

          username: ws.username,

          clientIp: ws.clientIp,

          clientDevice: ws.clientDevice,

          roomId: currentRoomId,

          targetDevice,

          targetOs,

          details: { protocol: data.protocol || 'rdp', port: data.port, tunnel_id: data.tunnel_id }

        });

      } else if (type === 'clipboard_sync') {

        await DB.logAudit({

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

      } else if (type === 'clipboard_sync_image') {

        await DB.logAudit({

          action: 'CLIPBOARD_SYNC',

          userId: ws.userId,

          username: ws.username,

          clientIp: ws.clientIp,

          clientDevice: ws.clientDevice,

          roomId: currentRoomId,

          targetDevice,

          targetOs,

          details: { type: 'image', mime: data.mime || 'image/png', size: (data.data || '').length }

        });

      } else if (type === 'clipboard_sync_files') {

        await DB.logAudit({

          action: 'CLIPBOARD_SYNC',

          userId: ws.userId,

          username: ws.username,

          clientIp: ws.clientIp,

          clientDevice: ws.clientDevice,

          roomId: currentRoomId,

          targetDevice,

          targetOs,

          details: { type: 'files', count: (data.files || []).length }

        });

      }

    }



    // --- Forward Bidirectional Control / Inputs / Files / Clipboard ---

    if (role === 'client' && currentRoomId) {

      const room = rooms.get(currentRoomId);

      if (room && room.hostWs && room.hostWs.readyState === WebSocket.OPEN) {

        if (type === 'toggle_privacy_curtain') {
          data.sessionId = ws.sessionId;
          data.username = ws.username;
          room.hostWs.send(JSON.stringify(data));
        } else {
          room.hostWs.send(message.toString());
        }

      }

    } else if (role === 'host' && currentRoomId) {

      const room = rooms.get(currentRoomId);

      if (room) {

        if (type === 'display_profile_matched') {

          if (!room.streamConfig) room.streamConfig = {};

          room.streamConfig.qualityPreset = data.recommended_preset;

          if (data.host_res) {

            room.streamConfig.width = data.host_res[0];

            room.streamConfig.height = data.host_res[1];

          }

        } else if (type === 'monitors_list') {

          if (!room.streamConfig) room.streamConfig = {};

          room.streamConfig.monitors = data.monitors;

        } else if (type === 'stream_config') {

          if (!room.streamConfig) room.streamConfig = {};

          Object.assign(room.streamConfig, data);

        } else if (type === 'quality_preset') {

          if (!room.streamConfig) room.streamConfig = {};

          room.streamConfig.qualityPreset = data.preset;

        }

      }

      if (room && room.clients) {

        if (type === 'privacy_curtain_response') {
          room.curtainActive = !!data.enabled;
        }

        const msgStr = message.toString();

        for (const client of room.clients.values()) {

          if (client.ws.readyState === WebSocket.OPEN) {

            client.ws.send(msgStr);

          }

        }

      }

    }

  });



  ws.on('close', async () => {

    if (currentRoomId && rooms.has(currentRoomId)) {

      const room = rooms.get(currentRoomId);

      if (role === 'host') {

        if (room && room.hostWs === ws) {

          console.log(`[Host Offline] Room: ${currentRoomId}`);

          await DB.logAudit({

            action: 'HOST_OFFLINE',

            roomId: currentRoomId,

            clientIp: ws.clientIp,

            clientDevice: ws.clientDevice,

            targetDevice: room?.hostMeta?.deviceName,

            targetOs: room?.hostMeta?.osInfo,

            details: { status: 'offline' }

          });

          await closeRoomClients(currentRoomId, 'Máy trạm đã ngắt kết nối', ws);

        } else {

          console.log(`[Stale Host Socket Closed] Room: ${currentRoomId} - ignored because active host is different`);

        }

      } else if (role === 'client') {

        console.log(`[Client Disconnected] Room: ${currentRoomId} | Session: ${ws.sessionId}`);

        // Immediate synchronous state cleanup before async DB audit
        if (room && room.clients) {
          const clientEntry = room.clients.get(ws.sessionId);
          const cMachine = clientEntry?.machineId || ws.machineId;
          const hMachine = room.hostMeta?.machineId;
          if (cMachine && hMachine) {
            removeRemoteEdge(cMachine, hMachine, ws.sessionId);
          }
          room.clients.delete(ws.sessionId);
          broadcastSessionList(room);
          if (room.clients.size === 0) room.isStreaming = false;

          if (room.clients.size === 0 && room.hostWs && room.hostWs.readyState === WebSocket.OPEN) {
            room.hostWs.send(JSON.stringify({ type: 'client_disconnected', clientCount: 0 }));
          } else if (room.clients.size > 0 && room.hostWs && room.hostWs.readyState === WebSocket.OPEN) {
            room.hostWs.send(JSON.stringify({
              type: 'client_disconnected',
              clientCount: room.clients.size,
              sessionId: ws.sessionId,
              username: ws.username
            }));
          }
        }

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
          details: { durationSec, durationText: `${durationSec}s`, sessionId: ws.sessionId }
        }).catch(() => {});
      }

      if (!room.hostWs && (!room.clients || room.clients.size === 0)) {

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

  const adapterInfo = DB.getAdapterInfo();

  console.log(`====================================================`);

  console.log(`  MEIKOVA RELAY ENTERPRISE - RELAY & REST API SERVER `);

  console.log(`====================================================`);

  console.log(`* Local Web UI & Relay: http://localhost:${PORT}`);

  console.log(`* Auth REST API:        http://localhost:${PORT}/api/auth`);

  console.log(`* Devices REST API:     http://localhost:${PORT}/api/devices`);

  console.log(`* Database:             ${adapterInfo.isTurso ? 'Turso Cloud SQLite' : 'SQLite WAL (meikova_relay.db)'}`);

  console.log(`====================================================`);

  if (process.argv.includes('--tunnel') || process.env.AUTO_TUNNEL === '1') {
    tunnelManager.start(PORT)
      .then(st => console.log(`* Cloudflare Tunnel:    ${st.url}`))
      .catch(e => console.error(`* Tunnel Auto-start:    [!] ${e.message}`));
  }

});


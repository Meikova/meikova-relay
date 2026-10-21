const { createClient } = require('@libsql/client');
const crypto = require('crypto');
const path = require('path');
const fs = require('fs');

// Lightweight zero-dependency .env loader for Node.js
function loadEnv() {
  const envCandidates = [
    path.join(__dirname, '.env'),
    path.join(process.cwd(), '.env'),
    path.join(__dirname, '..', '.env')
  ];
  for (const envFile of envCandidates) {
    if (fs.existsSync(envFile)) {
      try {
        const content = fs.readFileSync(envFile, 'utf8');
        for (const line of content.split(/\r?\n/)) {
          const trimmed = line.trim();
          if (!trimmed || trimmed.startsWith('#')) continue;
          const eqIdx = trimmed.indexOf('=');
          if (eqIdx !== -1) {
            const key = trimmed.slice(0, eqIdx).trim();
            let val = trimmed.slice(eqIdx + 1).trim();
            if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
              val = val.slice(1, -1);
            }
            if (!(key in process.env)) {
              process.env[key] = val;
            }
          }
        }
      } catch (_) {}
      break;
    }
  }
}
loadEnv();

const SCHEMA_SQL = `
  CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    created_at INTEGER NOT NULL
  );

  CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    device_name TEXT NOT NULL,
    room_id TEXT UNIQUE NOT NULL,
    pin TEXT NOT NULL,
    is_online INTEGER DEFAULT 0,
    last_seen INTEGER NOT NULL,
    os_info TEXT DEFAULT 'Windows',
    resolution TEXT DEFAULT '1920x1080',
    FOREIGN KEY(user_id) REFERENCES users(id)
  );

  CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
  );

  CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    timestamp INTEGER NOT NULL,
    action TEXT NOT NULL,
    user_id TEXT,
    username TEXT,
    client_ip TEXT NOT NULL,
    client_device TEXT,
    room_id TEXT,
    target_device TEXT,
    target_os TEXT,
    details TEXT
  );

  CREATE TABLE IF NOT EXISTS user_sync_store (
    user_id TEXT PRIMARY KEY,
    preferences TEXT DEFAULT '{}',
    device_bookmarks TEXT DEFAULT '[]',
    quick_history TEXT DEFAULT '[]',
    custom_labels TEXT DEFAULT '{}',
    updated_at INTEGER NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
  );

  CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_logs(timestamp DESC);
  CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action);
  CREATE INDEX IF NOT EXISTS idx_audit_room ON audit_logs(room_id);
  CREATE INDEX IF NOT EXISTS idx_sync_user ON user_sync_store(user_id);
`;

let client = null;
let isTurso = false;
let adapterUrl = '';
let initPromise = null;

function setupClient(override = {}) {
  const tursoUrl = (override.url || process.env.TURSO_DATABASE_URL || '').trim();
  const tursoToken = (override.authToken || process.env.TURSO_AUTH_TOKEN || '').trim();

  if (tursoUrl && (tursoToken || tursoUrl.startsWith('libsql:') || tursoUrl.startsWith('https:'))) {
    isTurso = true;
    adapterUrl = tursoUrl;
    client = createClient({
      url: tursoUrl,
      authToken: tursoToken
    });
    console.log(`[DB] Connected to Turso Cloud SQLite (${tursoUrl})`);
  } else {
    isTurso = false;
    const DB_DIR = override.dataDir || process.env.DATA_DIR || __dirname;
    const DB_PATH = override.dbPath || process.env.DB_PATH || path.join(DB_DIR, 'meikova_relay.db');
    const dbFolder = path.dirname(DB_PATH);
    if (!fs.existsSync(dbFolder)) {
      try {
        fs.mkdirSync(dbFolder, { recursive: true });
      } catch (err) {
        console.error('[DB] Failed to create database directory:', err.message);
      }
    }
    const normalized = path.resolve(DB_PATH).replace(/\\/g, '/');
    adapterUrl = `file:${normalized}`;
    client = createClient({
      url: adapterUrl
    });
    console.log(`[DB] Fallback to local SQLite WAL database (${adapterUrl})`);
  }
  initPromise = null;
}

// Initial client setup
setupClient();

async function ensureInit() {
  if (initPromise) return initPromise;

  initPromise = (async () => {
    try {
      await client.execute('PRAGMA foreign_keys = ON;');
      if (!isTurso) {
        await client.execute('PRAGMA journal_mode = WAL;');
        await client.execute('PRAGMA synchronous = NORMAL;');
      }
    } catch (err) {
      console.warn('[DB] Pragma configuration notice:', err.message);
    }

    try {
      await client.executeMultiple(SCHEMA_SQL);
    } catch (err) {
      console.error('[DB] Schema initialization error:', err.message);
      throw err;
    }
  })().catch(err => {
    initPromise = null;
    throw err;
  });

  return initPromise;
}

// Start async initialization in background
ensureInit().catch(err => {
  console.error('[DB] Async initialization failed:', err.message);
});

function hashPassword(password, salt) {
  return crypto.scryptSync(password, salt, 64).toString('hex');
}

const DB = {
  // --- Adapter Lifecycle & Inspection ---
  init(config) {
    if (config) {
      setupClient(config);
    }
    return ensureInit();
  },

  async close() {
    if (client && typeof client.close === 'function') {
      await client.close();
    }
  },

  getClient() {
    return client;
  },

  getAdapterInfo() {
    return {
      type: isTurso ? 'turso' : 'local',
      url: adapterUrl,
      isTurso
    };
  },

  // --- User Auth ---
  async registerUser(username, password) {
    await ensureInit();
    const trimmedUser = String(username || '').trim().toLowerCase();
    if (!trimmedUser || !password || password.length < 6) {
      throw new Error('Username must not be empty and password must be at least 6 characters');
    }

    const salt = crypto.randomBytes(16).toString('hex');
    const hash = hashPassword(password, salt);
    const userId = crypto.randomUUID();
    const now = Date.now();

    try {
      await client.execute({
        sql: 'INSERT INTO users (id, username, password_hash, salt, created_at) VALUES (?, ?, ?, ?, ?)',
        args: [userId, trimmedUser, hash, salt, now]
      });
      return { id: userId, username: trimmedUser };
    } catch (err) {
      const msg = err.message || '';
      if (msg.includes('UNIQUE constraint failed') || msg.includes('constraint failed') || msg.includes('SQLITE_CONSTRAINT')) {
        throw new Error('Tài khoản đã tồn tại');
      }
      throw err;
    }
  },

  async authenticateUser(username, password) {
    await ensureInit();
    const trimmedUser = String(username || '').trim().toLowerCase();
    const res = await client.execute({
      sql: 'SELECT id, username, password_hash, salt FROM users WHERE username = ?',
      args: [trimmedUser]
    });
    const user = res.rows[0];
    if (!user) {
      return null;
    }

    const hash = hashPassword(password, user.salt);
    if (hash !== user.password_hash) {
      return null;
    }

    // Create session token
    const token = crypto.randomBytes(32).toString('hex');
    const now = Date.now();
    await client.execute({
      sql: 'INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)',
      args: [token, user.id, now]
    });

    return { token, user: { id: user.id, username: user.username } };
  },

  async validateSession(token) {
    if (!token) return null;

    // Fast-path: Check if token is a Universal SSO Ed25519 Token (offline 0.1ms verification)
    if (typeof token === 'string' && token.split('.').length === 3) {
      try {
        let verifyUniversalToken;
        try {
          verifyUniversalToken = require('./universal_sso').verifyUniversalToken;
        } catch (_) {
          try {
            verifyUniversalToken = require('../../shared/universal_sso').verifyUniversalToken;
          } catch (_2) {}
        }
        if (verifyUniversalToken) {
          const ssoUser = verifyUniversalToken(token);
          if (ssoUser) {
            return {
              id: ssoUser.sub,
              username: ssoUser.username,
              email: ssoUser.email || null,
              display_name: ssoUser.display_name || ssoUser.username,
              role: ssoUser.role || 'user',
              provider: 'universal_sso'
            };
          }
        }
      } catch (_) {}
    }

    await ensureInit();
    const res = await client.execute({
      sql: `
        SELECT u.id, u.username 
        FROM sessions s 
        JOIN users u ON s.user_id = u.id 
        WHERE s.token = ?
      `,
      args: [token]
    });
    return res.rows[0] || null;
  },

  async deleteSession(token) {
    if (!token) return false;
    await ensureInit();
    const res = await client.execute({
      sql: 'DELETE FROM sessions WHERE token = ?',
      args: [token]
    });
    return (res.rowsAffected || 0) > 0;
  },

  async refreshSession(oldToken) {
    if (!oldToken) return null;
    await ensureInit();
    const user = await this.validateSession(oldToken);
    if (!user) return null;
    const newToken = crypto.randomBytes(32).toString('hex');
    const now = Date.now();
    await client.execute({
      sql: 'UPDATE sessions SET token = ?, created_at = ? WHERE token = ?',
      args: [newToken, now, oldToken]
    });
    return { token: newToken, user };
  },

  async getUserByUsername(username) {
    if (!username) return null;
    await ensureInit();
    const trimmedUser = String(username).trim().toLowerCase();
    const res = await client.execute({
      sql: 'SELECT id, username FROM users WHERE username = ?',
      args: [trimmedUser]
    });
    return res.rows[0] || null;
  },

  // --- Device Management ---
  async getDevices(userId) {
    await ensureInit();
    await this.deduplicateDevices(userId);
    const res = await client.execute({
      sql: `
        SELECT id, device_name, room_id, pin, is_online, last_seen, os_info, resolution 
        FROM devices 
        WHERE user_id = ? 
        ORDER BY is_online DESC, last_seen DESC
      `,
      args: [userId]
    });
    return res.rows;
  },

  async deduplicateDevices(userId) {
    if (!userId) return;
    await ensureInit();
    try {
      await client.execute({
        sql: `
          DELETE FROM devices 
          WHERE user_id = ? AND id NOT IN (
            SELECT id FROM (
              SELECT id, ROW_NUMBER() OVER (
                PARTITION BY user_id, device_name 
                ORDER BY is_online DESC, last_seen DESC
              ) as rn 
              FROM devices
              WHERE user_id = ?
            ) WHERE rn = 1
          )
        `,
        args: [userId, userId]
      });
    } catch (err) {
      console.error('[DB] Error deduplicating devices:', err.message);
    }
  },

  async deleteDevice(deviceId, userId) {
    if (!deviceId || !userId) return false;
    await ensureInit();
    const res = await client.execute({
      sql: 'DELETE FROM devices WHERE id = ? AND user_id = ?',
      args: [deviceId, userId]
    });
    return (res.rowsAffected || 0) > 0;
  },

  async upsertDevice({ userId, deviceName, roomId, pin, resolution, osInfo }) {
    await ensureInit();
    const now = Date.now();
    let existing = null;
    if (userId && deviceName) {
      const res = await client.execute({
        sql: 'SELECT id, user_id, room_id FROM devices WHERE user_id = ? AND device_name = ?',
        args: [userId, deviceName]
      });
      existing = res.rows[0] || null;
    }
    if (!existing && roomId) {
      const res = await client.execute({
        sql: 'SELECT id, user_id, room_id FROM devices WHERE room_id = ?',
        args: [roomId]
      });
      existing = res.rows[0] || null;
    }

    if (existing) {
      // Update existing
      await client.execute({
        sql: `
          UPDATE devices 
          SET room_id = ?, device_name = ?, pin = ?, resolution = ?, os_info = ?, is_online = 1, last_seen = ?, user_id = COALESCE(?, user_id)
          WHERE id = ?
        `,
        args: [roomId, deviceName, pin, resolution || '1920x1080', osInfo || 'Windows', now, userId || null, existing.id]
      });
      return existing.id;
    } else {
      // Insert new device
      const id = crypto.randomUUID();
      await client.execute({
        sql: `
          INSERT INTO devices (id, user_id, device_name, room_id, pin, is_online, last_seen, os_info, resolution)
          VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
        `,
        args: [id, userId || null, deviceName, roomId, pin, now, osInfo || 'Windows', resolution || '1920x1080']
      });
      return id;
    }
  },

  async setDeviceOnlineStatus(roomId, isOnline) {
    await ensureInit();
    const now = Date.now();
    await client.execute({
      sql: 'UPDATE devices SET is_online = ?, last_seen = ? WHERE room_id = ?',
      args: [isOnline ? 1 : 0, now, roomId]
    });
  },

  async googleAuth(email, displayName) {
    await ensureInit();
    const trimmedEmail = String(email || '').trim().toLowerCase();
    const res = await client.execute({
      sql: 'SELECT id, username FROM users WHERE username = ?',
      args: [trimmedEmail]
    });
    let user = res.rows[0] || null;

    if (!user) {
      // Auto-register Google user with random password
      const salt = crypto.randomBytes(16).toString('hex');
      const hash = hashPassword(crypto.randomBytes(32).toString('hex'), salt);
      const userId = crypto.randomUUID();
      const now = Date.now();
      await client.execute({
        sql: 'INSERT INTO users (id, username, password_hash, salt, created_at) VALUES (?, ?, ?, ?, ?)',
        args: [userId, trimmedEmail, hash, salt, now]
      });
      user = { id: userId, username: trimmedEmail };
    }

    // Create session
    const token = crypto.randomBytes(32).toString('hex');
    const now = Date.now();
    await client.execute({
      sql: 'INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)',
      args: [token, user.id, now]
    });

    return { token, user: { id: user.id, username: user.username, displayName: displayName || user.username } };
  },

  // --- Audit Logging ---
  async logAudit({ action, userId, username, clientIp, clientDevice, roomId, targetDevice, targetOs, details }) {
    try {
      await ensureInit();
      const id = crypto.randomUUID();
      const now = Date.now();
      const detailsStr = typeof details === 'object' ? JSON.stringify(details) : (details ? String(details) : '{}');
      await client.execute({
        sql: `
          INSERT INTO audit_logs (id, timestamp, action, user_id, username, client_ip, client_device, room_id, target_device, target_os, details)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        `,
        args: [
          id,
          now,
          String(action || 'UNKNOWN'),
          userId || null,
          username || 'Khách (Ẩn danh)',
          String(clientIp || '127.0.0.1'),
          String(clientDevice || 'Unknown'),
          roomId || null,
          targetDevice || null,
          targetOs || null,
          detailsStr
        ]
      });
      return id;
    } catch (err) {
      console.error('[DB Audit Error]:', err.message);
      return null;
    }
  },

  async getAuditLogs({ limit = 50, offset = 0, action = null, roomId = null, search = null } = {}) {
    await ensureInit();
    let whereClauses = [];
    let params = [];

    if (action && action !== 'all') {
      whereClauses.push('action = ?');
      params.push(action);
    }
    if (roomId) {
      whereClauses.push('room_id = ?');
      params.push(roomId);
    }
    if (search && search.trim()) {
      whereClauses.push('(username LIKE ? OR client_ip LIKE ? OR client_device LIKE ? OR target_device LIKE ? OR room_id LIKE ? OR details LIKE ?)');
      const s = `%${search.trim()}%`;
      params.push(s, s, s, s, s, s);
    }

    const whereSql = whereClauses.length > 0 ? `WHERE ${whereClauses.join(' AND ')}` : '';

    const countRes = await client.execute({
      sql: `SELECT COUNT(*) as count FROM audit_logs ${whereSql}`,
      args: params
    });
    const countRow = countRes.rows[0];
    const total = countRow ? Number(countRow.count) : 0;

    const queryRes = await client.execute({
      sql: `
        SELECT id, timestamp, action, user_id, username, client_ip, client_device, room_id, target_device, target_os, details
        FROM audit_logs
        ${whereSql}
        ORDER BY timestamp DESC
        LIMIT ? OFFSET ?
      `,
      args: [...params, Math.min(Number(limit) || 50, 500), Math.max(Number(offset) || 0, 0)]
    });

    return { logs: queryRes.rows, total };
  },

  // --- Offline-First User Config & Bookmark Sync ---
  async getUserSync(userId) {
    if (!userId) return null;
    await ensureInit();
    const res = await client.execute({
      sql: 'SELECT preferences, device_bookmarks, quick_history, custom_labels, updated_at FROM user_sync_store WHERE user_id = ?',
      args: [userId]
    });
    const row = res.rows[0];
    if (!row) {
      return {
        preferences: {},
        device_bookmarks: [],
        quick_history: [],
        custom_labels: {},
        updated_at: 0
      };
    }
    try {
      return {
        preferences: JSON.parse(row.preferences || '{}'),
        device_bookmarks: JSON.parse(row.device_bookmarks || '[]'),
        quick_history: JSON.parse(row.quick_history || '[]'),
        custom_labels: JSON.parse(row.custom_labels || '{}'),
        updated_at: Number(row.updated_at) || 0
      };
    } catch (err) {
      return {
        preferences: {},
        device_bookmarks: [],
        quick_history: [],
        custom_labels: {},
        updated_at: Number(row.updated_at) || 0
      };
    }
  },

  async saveUserSync(userId, data = {}) {
    if (!userId) return null;
    await ensureInit();
    const current = await this.getUserSync(userId);
    const now = Date.now();

    const mergedPrefs = data.preferences !== undefined ? { ...current.preferences, ...data.preferences } : current.preferences;
    const mergedBookmarks = data.device_bookmarks !== undefined ? data.device_bookmarks : current.device_bookmarks;
    const mergedHistory = data.quick_history !== undefined ? data.quick_history : current.quick_history;
    const mergedLabels = data.custom_labels !== undefined ? { ...current.custom_labels, ...data.custom_labels } : current.custom_labels;

    await client.execute({
      sql: `
        INSERT INTO user_sync_store (user_id, preferences, device_bookmarks, quick_history, custom_labels, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
          preferences = excluded.preferences,
          device_bookmarks = excluded.device_bookmarks,
          quick_history = excluded.quick_history,
          custom_labels = excluded.custom_labels,
          updated_at = excluded.updated_at
      `,
      args: [
        userId,
        JSON.stringify(mergedPrefs),
        JSON.stringify(mergedBookmarks),
        JSON.stringify(mergedHistory),
        JSON.stringify(mergedLabels),
        now
      ]
    });

    return {
      preferences: mergedPrefs,
      device_bookmarks: mergedBookmarks,
      quick_history: mergedHistory,
      custom_labels: mergedLabels,
      updated_at: now
    };
  }
};

module.exports = DB;

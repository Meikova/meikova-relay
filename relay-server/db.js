const { DatabaseSync } = require('node:sqlite');
const crypto = require('crypto');
const path = require('path');

const DB_PATH = path.join(__dirname, 'titan_remote.db');
const db = new DatabaseSync(DB_PATH);

// Initialize schema
db.exec(`
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

  CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_logs(timestamp DESC);
  CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action);
  CREATE INDEX IF NOT EXISTS idx_audit_room ON audit_logs(room_id);
`);

function hashPassword(password, salt) {
  return crypto.scryptSync(password, salt, 64).toString('hex');
}

const DB = {
  // --- User Auth ---
  registerUser(username, password) {
    const trimmedUser = String(username).trim().toLowerCase();
    if (!trimmedUser || !password || password.length < 6) {
      throw new Error('Username must not be empty and password must be at least 6 characters');
    }

    const salt = crypto.randomBytes(16).toString('hex');
    const hash = hashPassword(password, salt);
    const userId = crypto.randomUUID();
    const now = Date.now();

    try {
      const stmt = db.prepare('INSERT INTO users (id, username, password_hash, salt, created_at) VALUES (?, ?, ?, ?, ?)');
      stmt.run(userId, trimmedUser, hash, salt, now);
      return { id: userId, username: trimmedUser };
    } catch (err) {
      if (err.message && err.message.includes('UNIQUE constraint failed')) {
        throw new Error('Tài khoản đã tồn tại');
      }
      throw err;
    }
  },

  authenticateUser(username, password) {
    const trimmedUser = String(username).trim().toLowerCase();
    const stmt = db.prepare('SELECT id, username, password_hash, salt FROM users WHERE username = ?');
    const user = stmt.get(trimmedUser);
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
    const sessStmt = db.prepare('INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)');
    sessStmt.run(token, user.id, now);

    return { token, user: { id: user.id, username: user.username } };
  },

  validateSession(token) {
    if (!token) return null;
    const stmt = db.prepare(`
      SELECT u.id, u.username 
      FROM sessions s 
      JOIN users u ON s.user_id = u.id 
      WHERE s.token = ?
    `);
    return stmt.get(token) || null;
  },

  deleteSession(token) {
    if (!token) return false;
    const stmt = db.prepare('DELETE FROM sessions WHERE token = ?');
    stmt.run(token);
    return true;
  },

  refreshSession(oldToken) {
    if (!oldToken) return null;
    const user = this.validateSession(oldToken);
    if (!user) return null;
    const newToken = crypto.randomBytes(32).toString('hex');
    const now = Date.now();
    const updateStmt = db.prepare('UPDATE sessions SET token = ?, created_at = ? WHERE token = ?');
    updateStmt.run(newToken, now, oldToken);
    return { token: newToken, user };
  },

  getUserByUsername(username) {
    if (!username) return null;
    const trimmedUser = String(username).trim().toLowerCase();
    const stmt = db.prepare('SELECT id, username FROM users WHERE username = ?');
    return stmt.get(trimmedUser) || null;
  },

  // --- Device Management ---
  getDevices(userId) {
    this.deduplicateDevices(userId);
    const stmt = db.prepare(`
      SELECT id, device_name, room_id, pin, is_online, last_seen, os_info, resolution 
      FROM devices 
      WHERE user_id = ? 
      ORDER BY is_online DESC, last_seen DESC
    `);
    return stmt.all(userId);
  },

  deduplicateDevices(userId) {
    if (!userId) return;
    try {
      db.prepare(`
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
      `).run(userId, userId);
    } catch (err) {
      console.error('[DB] Error deduplicating devices:', err);
    }
  },

  deleteDevice(deviceId, userId) {
    if (!deviceId || !userId) return false;
    const stmt = db.prepare('DELETE FROM devices WHERE id = ? AND user_id = ?');
    const result = stmt.run(deviceId, userId);
    return result.changes > 0;
  },

  upsertDevice({ userId, deviceName, roomId, pin, resolution, osInfo }) {
    const now = Date.now();
    let existing = null;
    if (userId && deviceName) {
      existing = db.prepare('SELECT id, user_id, room_id FROM devices WHERE user_id = ? AND device_name = ?').get(userId, deviceName);
    }
    if (!existing && roomId) {
      existing = db.prepare('SELECT id, user_id, room_id FROM devices WHERE room_id = ?').get(roomId);
    }

    if (existing) {
      // Update existing
      const updateStmt = db.prepare(`
        UPDATE devices 
        SET room_id = ?, device_name = ?, pin = ?, resolution = ?, os_info = ?, is_online = 1, last_seen = ?, user_id = COALESCE(?, user_id)
        WHERE id = ?
      `);
      updateStmt.run(roomId, deviceName, pin, resolution || '1920x1080', osInfo || 'Windows', now, userId || null, existing.id);
      return existing.id;
    } else {
      // Insert new device
      const id = crypto.randomUUID();
      const insertStmt = db.prepare(`
        INSERT INTO devices (id, user_id, device_name, room_id, pin, is_online, last_seen, os_info, resolution)
        VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
      `);
      insertStmt.run(id, userId || null, deviceName, roomId, pin, now, osInfo || 'Windows', resolution || '1920x1080');
      return id;
    }
  },

  setDeviceOnlineStatus(roomId, isOnline) {
    const now = Date.now();
    const stmt = db.prepare('UPDATE devices SET is_online = ?, last_seen = ? WHERE room_id = ?');
    stmt.run(isOnline ? 1 : 0, now, roomId);
  },

  googleAuth(email, displayName) {
    const trimmedEmail = String(email).trim().toLowerCase();
    const stmt = db.prepare('SELECT id, username FROM users WHERE username = ?');
    let user = stmt.get(trimmedEmail);
    
    if (!user) {
      // Auto-register Google user with random password
      const salt = crypto.randomBytes(16).toString('hex');
      const hash = hashPassword(crypto.randomBytes(32).toString('hex'), salt);
      const userId = crypto.randomUUID();
      const now = Date.now();
      const insertStmt = db.prepare('INSERT INTO users (id, username, password_hash, salt, created_at) VALUES (?, ?, ?, ?, ?)');
      insertStmt.run(userId, trimmedEmail, hash, salt, now);
      user = { id: userId, username: trimmedEmail };
    }
    
    // Create session
    const token = crypto.randomBytes(32).toString('hex');
    const now = Date.now();
    const sessStmt = db.prepare('INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)');
    sessStmt.run(token, user.id, now);
    
    return { token, user: { id: user.id, username: user.username, displayName: displayName || user.username } };
  },

  // --- Audit Logging ---
  logAudit({ action, userId, username, clientIp, clientDevice, roomId, targetDevice, targetOs, details }) {
    const id = crypto.randomUUID();
    const now = Date.now();
    const detailsStr = typeof details === 'object' ? JSON.stringify(details) : (details ? String(details) : '{}');
    try {
      const stmt = db.prepare(`
        INSERT INTO audit_logs (id, timestamp, action, user_id, username, client_ip, client_device, room_id, target_device, target_os, details)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      `);
      stmt.run(
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
      );
      return id;
    } catch (err) {
      console.error('[DB Audit Error]:', err.message);
      return null;
    }
  },

  getAuditLogs({ limit = 50, offset = 0, action = null, roomId = null, search = null } = {}) {
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

    const countStmt = db.prepare(`SELECT COUNT(*) as count FROM audit_logs ${whereSql}`);
    const countRow = countStmt.get(...params);
    const total = countRow ? countRow.count : 0;

    const queryStmt = db.prepare(`
      SELECT id, timestamp, action, user_id, username, client_ip, client_device, room_id, target_device, target_os, details
      FROM audit_logs
      ${whereSql}
      ORDER BY timestamp DESC
      LIMIT ? OFFSET ?
    `);
    const logs = queryStmt.all(...params, Math.min(Number(limit) || 50, 500), Math.max(Number(offset) || 0, 0));

    return { logs, total };
  }
};

module.exports = DB;

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

  // --- Device Management ---
  getDevices(userId) {
    const stmt = db.prepare(`
      SELECT id, device_name, room_id, pin, is_online, last_seen, os_info, resolution 
      FROM devices 
      WHERE user_id = ? 
      ORDER BY is_online DESC, last_seen DESC
    `);
    return stmt.all(userId);
  },

  upsertDevice({ userId, deviceName, roomId, pin, resolution, osInfo }) {
    const now = Date.now();
    const existingStmt = db.prepare('SELECT id, user_id FROM devices WHERE room_id = ?');
    const existing = existingStmt.get(roomId);

    if (existing) {
      // Update existing
      const updateStmt = db.prepare(`
        UPDATE devices 
        SET device_name = ?, pin = ?, resolution = ?, os_info = ?, is_online = 1, last_seen = ?, user_id = COALESCE(?, user_id)
        WHERE room_id = ?
      `);
      updateStmt.run(deviceName, pin, resolution || '1920x1080', osInfo || 'Windows', now, userId || null, roomId);
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
  }
};

module.exports = DB;

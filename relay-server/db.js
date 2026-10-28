
function normalizeOsInfoString(rawOs) {
  const s = String(rawOs || "").trim();
  if (!s) return "Windows 64-bit";
  const low = s.toLowerCase();
  if (low === "win32 (nt)" || low === "win32" || low === "nt" || low === "windows_nt") {
    return "Windows 64-bit";
  }
  if (low === "darwin (posix)" || low === "darwin") {
    return "macOS (64-bit)";
  }
  if (low === "linux (posix)" || low === "linux" || low === "posix") {
    return "Linux 64-bit";
  }
  return s;
}

let createClient;
try {
  ({ createClient } = require('@libsql/client'));
} catch (_) {
  ({ createClient } = require('./libsql_fallback'));
}
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
    email TEXT,
    display_name TEXT,
    gateway_user_id TEXT,
    auth_provider TEXT DEFAULT 'local',
    sync_status TEXT DEFAULT 'synced',
    created_at INTEGER NOT NULL,
    updated_at INTEGER
  );

  CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    machine_id TEXT,
    device_name TEXT NOT NULL,
    room_id TEXT UNIQUE NOT NULL,
    pin TEXT NOT NULL,
    is_online INTEGER DEFAULT 0,
    last_seen INTEGER NOT NULL,
    last_accessed INTEGER DEFAULT 0,
    os_info TEXT DEFAULT 'Windows',
    resolution TEXT DEFAULT '1920x1080',
    group_name TEXT DEFAULT 'Mặc định',
    tags TEXT DEFAULT '[]',
    is_admin INTEGER DEFAULT 0,
    host_config TEXT DEFAULT '{}',
    notes TEXT DEFAULT '',
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

  CREATE TABLE IF NOT EXISTS auth_sync_queue (
    id TEXT PRIMARY KEY,
    action TEXT NOT NULL,
    user_id TEXT,
    payload TEXT NOT NULL,
    status TEXT DEFAULT 'PENDING',
    retry_count INTEGER DEFAULT 0,
    error_message TEXT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
  );

  CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_logs(timestamp DESC);
  CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action);
  CREATE INDEX IF NOT EXISTS idx_audit_room ON audit_logs(room_id);
  CREATE INDEX IF NOT EXISTS idx_sync_user ON user_sync_store(user_id);
  CREATE INDEX IF NOT EXISTS idx_sync_queue_status ON auth_sync_queue(status);
`;

let client = null;
let isTurso = false;
let adapterUrl = '';
let initPromise = null;

function setupClient(override = {}) {
  const tursoUrl = (override.url || process.env.TURSO_DATABASE_URL || '').trim();
  const tursoToken = (override.authToken || process.env.TURSO_AUTH_TOKEN || '').trim();
  const hasLocalOverride = Boolean(override.dbPath || process.env.DB_PATH || process.env.NODE_ENV === 'test');

  if (!hasLocalOverride && tursoUrl && (tursoToken || tursoUrl.startsWith('libsql:') || tursoUrl.startsWith('https:'))) {
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

    // Safe incremental migrations for existing DBs
    const migrations = [
      'ALTER TABLE users ADD COLUMN email TEXT;',
      'ALTER TABLE users ADD COLUMN display_name TEXT;',
      'ALTER TABLE users ADD COLUMN gateway_user_id TEXT;',
      'ALTER TABLE users ADD COLUMN auth_provider TEXT DEFAULT "local";',
      'ALTER TABLE users ADD COLUMN sync_status TEXT DEFAULT "synced";',
      'ALTER TABLE users ADD COLUMN updated_at INTEGER;',
      'CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);',
      'CREATE INDEX IF NOT EXISTS idx_users_gateway ON users(gateway_user_id);',
      'CREATE INDEX IF NOT EXISTS idx_sync_queue_status ON auth_sync_queue(status);',
      'ALTER TABLE devices ADD COLUMN machine_id TEXT;',
      'ALTER TABLE devices ADD COLUMN last_accessed INTEGER DEFAULT 0;',
      'ALTER TABLE devices ADD COLUMN group_name TEXT DEFAULT "Mặc định";',
      'ALTER TABLE devices ADD COLUMN tags TEXT DEFAULT "[]";',
      'ALTER TABLE devices ADD COLUMN is_admin INTEGER DEFAULT 0;',
      'ALTER TABLE devices ADD COLUMN host_config TEXT DEFAULT "{}";',
      'ALTER TABLE devices ADD COLUMN notes TEXT DEFAULT "";',
      'CREATE INDEX IF NOT EXISTS idx_devices_machine ON devices(machine_id);',
      'CREATE INDEX IF NOT EXISTS idx_devices_user_machine ON devices(user_id, machine_id);'
    ];
    for (const sql of migrations) {
      try {
        await client.execute(sql);
      } catch (_) {}
    }

    // Reset stale online flags on server startup
    try {
      await client.execute('UPDATE devices SET is_online = 0;');
    } catch (_) {}
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
  async registerUser(username, password, email = null) {
    await ensureInit();
    const trimmedUser = String(username || '').trim().toLowerCase();
    const trimmedEmail = email ? String(email).trim().toLowerCase() : null;
    if (!trimmedUser || !password || password.length < 6) {
      throw new Error('Username must not be empty and password must be at least 6 characters');
    }

    const salt = crypto.randomBytes(16).toString('hex');
    const hash = hashPassword(password, salt);
    const userId = crypto.randomUUID();
    const now = Date.now();

    try {
      await client.execute({
        sql: `INSERT INTO users (id, username, password_hash, salt, email, display_name, auth_provider, sync_status, created_at, updated_at)
              VALUES (?, ?, ?, ?, ?, ?, 'local', 'pending_gateway', ?, ?)`,
        args: [userId, trimmedUser, hash, salt, trimmedEmail, trimmedUser, now, now]
      });

      // Enqueue for gateway synchronization
      await this.queueAuthSync('REGISTER', userId, {
        id: userId,
        username: trimmedUser,
        email: trimmedEmail,
        created_at: now
      });

      return { id: userId, username: trimmedUser, email: trimmedEmail };
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

  async createSession(userId) {
    await ensureInit();
    const token = crypto.randomBytes(32).toString('hex');
    const now = Date.now();
    await client.execute({
      sql: 'INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)',
      args: [token, userId, now]
    });
    return { token, userId, createdAt: now };
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
            // JIT Provisioning / Mirror into local users table
            try {
              await this.upsertLocalUserFromSSO(ssoUser);
            } catch (err) {
              console.warn('[DB] SSO JIT provisioning notice:', err.message);
            }
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
        SELECT u.id, u.username, u.email, u.display_name
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
    return this.findUserByIdentifier(username);
  },

  async findUserByIdentifier(identifier) {
    if (!identifier) return null;
    await ensureInit();
    const raw = String(identifier).trim();
    const lower = raw.toLowerCase();
    const prefix = lower.includes('@') ? lower.split('@')[0] : lower;

    // 1. Direct ID / gateway_user_id match
    let res = await client.execute({
      sql: 'SELECT id, username, email, display_name, gateway_user_id, auth_provider, sync_status FROM users WHERE id = ? OR gateway_user_id = ?',
      args: [raw, raw]
    });
    if (res.rows[0]) return res.rows[0];

    // 2. Exact username or exact email match
    res = await client.execute({
      sql: 'SELECT id, username, email, display_name, gateway_user_id, auth_provider, sync_status FROM users WHERE lower(username) = ? OR lower(email) = ?',
      args: [lower, lower]
    });
    if (res.rows[0]) return res.rows[0];

    // 3. Smart prefix matching (e.g. host sends 'kiempham1256', email is 'kiempham1256@gmail.com')
    res = await client.execute({
      sql: `SELECT id, username, email, display_name, gateway_user_id, auth_provider, sync_status FROM users 
            WHERE lower(username) = ? OR lower(email) LIKE ?`,
      args: [prefix, `${prefix}@%`]
    });
    if (res.rows[0]) return res.rows[0];

    return null;
  },

  async upsertLocalUserFromSSO(ssoUser) {
    if (!ssoUser || !ssoUser.sub) return null;
    await ensureInit();
    const sub = String(ssoUser.sub).trim();
    const username = String(ssoUser.username || ssoUser.sub).trim().toLowerCase();
    const email = ssoUser.email ? String(ssoUser.email).trim().toLowerCase() : null;
    const displayName = ssoUser.display_name || ssoUser.displayName || ssoUser.username || username;
    const now = Date.now();

    // 1. Search existing user by sub / gateway_user_id
    let existing = null;
    let res = await client.execute({
      sql: 'SELECT id, username, email, gateway_user_id FROM users WHERE id = ? OR gateway_user_id = ?',
      args: [sub, sub]
    });
    existing = res.rows[0];

    // 2. Search by email if not found
    if (!existing && email) {
      res = await client.execute({
        sql: 'SELECT id, username, email, gateway_user_id FROM users WHERE lower(email) = ?',
        args: [email]
      });
      existing = res.rows[0];
    }

    // 3. Search by username if not found
    if (!existing) {
      res = await client.execute({
        sql: 'SELECT id, username, email, gateway_user_id FROM users WHERE lower(username) = ?',
        args: [username]
      });
      existing = res.rows[0];
    }

    if (existing) {
      // Conflict / Account Linking: Match found
      await client.execute({
        sql: `UPDATE users 
              SET gateway_user_id = ?, email = COALESCE(?, email), display_name = ?, 
                  auth_provider = 'universal_sso', sync_status = 'synced', updated_at = ?
              WHERE id = ?`,
        args: [sub, email, displayName, now, existing.id]
      });

      return { id: existing.id, gateway_user_id: sub, username, email, display_name: displayName };
    }

    // Insert new mirrored user
    const dummySalt = crypto.randomBytes(16).toString('hex');
    const dummyHash = hashPassword(crypto.randomBytes(32).toString('hex'), dummySalt);
    await client.execute({
      sql: `INSERT INTO users (id, username, password_hash, salt, email, display_name, gateway_user_id, auth_provider, sync_status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'universal_sso', 'synced', ?, ?)`,
      args: [sub, username, dummyHash, dummySalt, email, displayName, sub, now, now]
    });

    return { id: sub, username, email, display_name: displayName };
  },

  // --- Auth Sync Queue & Conflict Resolution ---
  async queueAuthSync(action, userId, payload) {
    await ensureInit();
    const id = crypto.randomUUID();
    const now = Date.now();
    const payloadStr = typeof payload === 'object' ? JSON.stringify(payload) : String(payload);
    await client.execute({
      sql: `INSERT INTO auth_sync_queue (id, action, user_id, payload, status, retry_count, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'PENDING', 0, ?, ?)`,
      args: [id, action, userId || null, payloadStr, now, now]
    });
    return id;
  },

  async getAuthSyncQueue(status = 'PENDING') {
    await ensureInit();
    const res = await client.execute({
      sql: 'SELECT id, action, user_id, payload, status, retry_count, created_at FROM auth_sync_queue WHERE status = ? ORDER BY created_at ASC',
      args: [status]
    });
    return res.rows.map(row => ({
      ...row,
      payload: typeof row.payload === 'string' ? JSON.parse(row.payload) : row.payload
    }));
  },

  async markAuthSyncStatus(id, status, errorMsg = null) {
    await ensureInit();
    const now = Date.now();
    await client.execute({
      sql: 'UPDATE auth_sync_queue SET status = ?, error_message = ?, updated_at = ? WHERE id = ?',
      args: [status, errorMsg, now, id]
    });
  },

  async getSyncStatus() {
    await ensureInit();
    const pendingRes = await client.execute({
      sql: "SELECT COUNT(*) as count FROM auth_sync_queue WHERE status = 'PENDING'"
    });
    const syncedRes = await client.execute({
      sql: "SELECT COUNT(*) as count FROM auth_sync_queue WHERE status = 'SYNCED'"
    });
    const failedRes = await client.execute({
      sql: "SELECT COUNT(*) as count FROM auth_sync_queue WHERE status = 'FAILED'"
    });
    const usersRes = await client.execute({
      sql: "SELECT COUNT(*) as count FROM users WHERE sync_status = 'pending_gateway'"
    });
    return {
      queue_count: Number(pendingRes.rows[0]?.count || 0),
      synced_count: Number(syncedRes.rows[0]?.count || 0),
      failed_count: Number(failedRes.rows[0]?.count || 0),
      pending_users: Number(usersRes.rows[0]?.count || 0)
    };
  },

  async linkGatewayAccount({ email, gatewayUserId, username, displayName }) {
    await ensureInit();
    const now = Date.now();
    const cleanEmail = email ? String(email).trim().toLowerCase() : null;
    const cleanUser = String(username || '').trim().toLowerCase();
    const sub = String(gatewayUserId).trim();

    // Check Case 1: Same Email -> Account Linking (Merge into Gateway identity)
    if (cleanEmail) {
      const emailRes = await client.execute({
        sql: 'SELECT id, username, email FROM users WHERE lower(email) = ?',
        args: [cleanEmail]
      });
      const localWithEmail = emailRes.rows[0];
      if (localWithEmail) {
        await client.execute({
          sql: `UPDATE users 
                SET gateway_user_id = ?, auth_provider = 'universal_sso', sync_status = 'synced', updated_at = ?
                WHERE id = ?`,
          args: [sub, now, localWithEmail.id]
        });
        return { action: 'LINKED', userId: sub, localId: localWithEmail.id };
      }
    }

    // Check Case 2: Same Username, different Email -> Namespace Resolution (Rename local to username_local_<hash>)
    const userRes = await client.execute({
      sql: 'SELECT id, username, email FROM users WHERE lower(username) = ?',
      args: [cleanUser]
    });
    const localWithUser = userRes.rows[0];
    if (localWithUser && (!cleanEmail || localWithUser.email !== cleanEmail)) {
      const suffix = crypto.randomBytes(3).toString('hex');
      const renamedUsername = `${localWithUser.username}_local_${suffix}`;
      await client.execute({
        sql: `UPDATE users 
              SET username = ?, sync_status = 'conflict', updated_at = ?
              WHERE id = ?`,
        args: [renamedUsername, now, localWithUser.id]
      });

      const dummySalt = crypto.randomBytes(16).toString('hex');
      const dummyHash = hashPassword(crypto.randomBytes(32).toString('hex'), dummySalt);
      await client.execute({
        sql: `INSERT INTO users (id, username, password_hash, salt, email, display_name, gateway_user_id, auth_provider, sync_status, created_at, updated_at)
              VALUES (?, ?, ?, ?, ?, ?, ?, 'universal_sso', 'synced', ?, ?)`,
        args: [sub, cleanUser, dummyHash, dummySalt, cleanEmail, displayName || cleanUser, sub, now, now]
      });
      return { action: 'RESOLVED_NAMESPACE', localRenamedTo: renamedUsername, userId: sub };
    }

    // Case 3: Fresh insert
    return this.upsertLocalUserFromSSO({
      sub,
      username: cleanUser,
      email: cleanEmail,
      display_name: displayName
    });
  },

  // --- Device Management ---
  async getDevices(userId) {
    if (!userId) return [];
    await ensureInit();
    await this.deduplicateDevices(userId);
    const res = await client.execute({
      sql: `
        SELECT id, machine_id, device_name, room_id, pin, is_online, last_seen, last_accessed,
               os_info, resolution, group_name, tags, is_admin, host_config, notes
        FROM devices 
        WHERE user_id = ? 
           OR user_id IN (SELECT id FROM users WHERE gateway_user_id = ? OR id = ?)
           OR user_id IN (SELECT gateway_user_id FROM users WHERE id = ?)
        ORDER BY is_online DESC, last_seen DESC
      `,
      args: [userId, userId, userId, userId]
    });
    return (res.rows || []).map(r => {
      let parsedTags = [];
      let parsedCfg = {};
      try { parsedTags = typeof r.tags === 'string' ? JSON.parse(r.tags || '[]') : (r.tags || []); } catch (_) {}
      try { parsedCfg = typeof r.host_config === 'string' ? JSON.parse(r.host_config || '{}') : (r.host_config || {}); } catch (_) {}
      return {
        ...r,
        group_name: r.group_name || 'Mặc định',
        tags: Array.isArray(parsedTags) ? parsedTags : [],
        host_config: parsedCfg,
        is_admin: Number(r.is_admin || 0) === 1,
        last_accessed: Number(r.last_accessed || 0)
      };
    });
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
                PARTITION BY user_id, COALESCE(machine_id, device_name) 
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

  async upsertDevice({ userId, machineId, deviceName, roomId, pin, resolution, osInfo }) {
    await ensureInit();
    const now = Date.now();
    const cleanMachineId = machineId ? String(machineId).trim() : null;

    // Verify foreign key integrity: ensure userId actually exists in users table
    let validatedUserId = null;
    if (userId) {
      try {
        const uRes = await client.execute({
          sql: 'SELECT id FROM users WHERE id = ?',
          args: [userId]
        });
        if (uRes.rows && uRes.rows.length > 0) {
          validatedUserId = String(uRes.rows[0].id || userId);
        }
      } catch {
        validatedUserId = null;
      }
    }

    let existing = null;
    // 1. Primary identification: Hardware Machine ID (unique GUID per physical computer)
    if (cleanMachineId) {
      const res = await client.execute({
        sql: 'SELECT id, user_id, room_id, machine_id FROM devices WHERE machine_id = ?',
        args: [cleanMachineId]
      });
      existing = res.rows[0] || null;
    }
    // 2. Secondary identification: Unique Room ID
    if (!existing && roomId) {
      const res = await client.execute({
        sql: 'SELECT id, user_id, room_id, machine_id FROM devices WHERE room_id = ?',
        args: [roomId]
      });
      existing = res.rows[0] || null;
    }
    // 3. Fallback: By user_id and device_name ONLY if machine_id is not specified
    if (!existing && validatedUserId && deviceName && !cleanMachineId) {
      const res = await client.execute({
        sql: 'SELECT id, user_id, room_id, machine_id FROM devices WHERE user_id = ? AND device_name = ?',
        args: [validatedUserId, deviceName]
      });
      existing = res.rows[0] || null;
    }

    try {
      if (existing) {
        // Update existing device
        await client.execute({
          sql: `
            UPDATE devices 
            SET room_id = ?, device_name = ?, pin = ?, resolution = ?, os_info = ?, is_online = 1, last_seen = ?,
                user_id = COALESCE(?, user_id),
                machine_id = COALESCE(?, machine_id)
            WHERE id = ?
          `,
          args: [roomId, deviceName, pin, resolution || '1920x1080', normalizeOsInfoString(osInfo), now, validatedUserId, cleanMachineId, existing.id]
        });
        return existing.id;
      } else {
        // Insert new device
        const id = crypto.randomUUID();
        await client.execute({
          sql: `
            INSERT INTO devices (id, user_id, machine_id, device_name, room_id, pin, is_online, last_seen, os_info, resolution)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
          `,
          args: [id, validatedUserId, cleanMachineId, deviceName, roomId, pin, now, normalizeOsInfoString(osInfo), resolution || '1920x1080']
        });
        return id;
      }
    } catch (err) {
      // In case of foreign key error or constraint mismatch, fallback gracefully to unlinked device
      if (String(err).includes('FOREIGN KEY')) {
        if (existing) {
          await client.execute({
            sql: `
              UPDATE devices 
              SET room_id = ?, device_name = ?, pin = ?, resolution = ?, os_info = ?, is_online = 1, last_seen = ?,
                  machine_id = COALESCE(?, machine_id)
              WHERE id = ?
            `,
            args: [roomId, deviceName, pin, resolution || '1920x1080', normalizeOsInfoString(osInfo), now, cleanMachineId, existing.id]
          });
          return existing.id;
        } else {
          const id = crypto.randomUUID();
          await client.execute({
            sql: `
              INSERT INTO devices (id, user_id, machine_id, device_name, room_id, pin, is_online, last_seen, os_info, resolution)
              VALUES (?, NULL, ?, ?, ?, ?, 1, ?, ?, ?)
            `,
            args: [id, cleanMachineId, deviceName, roomId, pin, now, normalizeOsInfoString(osInfo), resolution || '1920x1080']
          });
          return id;
        }
      }
      throw err;
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

  async touchDeviceAccess(roomId, hostMeta = null) {
    if (!roomId) return;
    await ensureInit();
    const now = Date.now();
    try {
      if (hostMeta && (hostMeta.isAdmin !== undefined || hostMeta.hostConfig)) {
        await client.execute({
          sql: 'UPDATE devices SET last_accessed = ?, is_admin = ?, host_config = ? WHERE room_id = ?',
          args: [now, hostMeta.isAdmin ? 1 : 0, JSON.stringify(hostMeta.hostConfig || {}), roomId]
        });
      } else {
        await client.execute({
          sql: 'UPDATE devices SET last_accessed = ? WHERE room_id = ?',
          args: [now, roomId]
        });
      }
    } catch (_) {}
  },

  async updateDeviceMeta(deviceIdOrRoom, userId, { deviceName, groupName, tags, notes, hostConfig, isAdmin } = {}) {
    if (!deviceIdOrRoom || !userId) return false;
    await ensureInit();
    const existingRes = await client.execute({
      sql: 'SELECT id, device_name, group_name, tags, notes, host_config, is_admin FROM devices WHERE (id = ? OR room_id = ?) AND user_id = ?',
      args: [deviceIdOrRoom, deviceIdOrRoom, userId]
    });
    const row = existingRes.rows[0];
    if (!row) return false;

    const nextName = deviceName !== undefined ? String(deviceName).trim() : row.device_name;
    const nextGroup = groupName !== undefined ? String(groupName).trim() || 'Mặc định' : (row.group_name || 'Mặc định');
    const nextTags = tags !== undefined ? (Array.isArray(tags) ? JSON.stringify(tags) : String(tags)) : (row.tags || '[]');
    const nextNotes = notes !== undefined ? String(notes) : (row.notes || '');
    const nextCfg = hostConfig !== undefined ? (typeof hostConfig === 'object' ? JSON.stringify(hostConfig) : String(hostConfig)) : (row.host_config || '{}');
    const nextAdmin = isAdmin !== undefined ? (isAdmin ? 1 : 0) : Number(row.is_admin || 0);

    await client.execute({
      sql: `UPDATE devices
            SET device_name = ?, group_name = ?, tags = ?, notes = ?, host_config = ?, is_admin = ?
            WHERE id = ?`,
      args: [nextName, nextGroup, nextTags, nextNotes, nextCfg, nextAdmin, row.id]
    });
    return true;
  },

  async googleAuth(email, displayName) {
    await ensureInit();
    const trimmedEmail = String(email || '').trim().toLowerCase();
    let user = await this.findUserByIdentifier(trimmedEmail);

    if (!user) {
      // Auto-register Google user with random password
      const salt = crypto.randomBytes(16).toString('hex');
      const hash = hashPassword(crypto.randomBytes(32).toString('hex'), salt);
      const userId = crypto.randomUUID();
      const now = Date.now();
      await client.execute({
        sql: `INSERT INTO users (id, username, password_hash, salt, email, display_name, auth_provider, sync_status, created_at, updated_at) 
              VALUES (?, ?, ?, ?, ?, ?, 'google', 'synced', ?, ?)`,
        args: [userId, trimmedEmail, hash, salt, trimmedEmail, displayName || trimmedEmail, now, now]
      });
      user = { id: userId, username: trimmedEmail, email: trimmedEmail, display_name: displayName || trimmedEmail };
    } else {
      // Update display name / provider if needed
      await client.execute({
        sql: `UPDATE users SET display_name = COALESCE(?, display_name), email = COALESCE(?, email), updated_at = ? WHERE id = ?`,
        args: [displayName || user.username, trimmedEmail, Date.now(), user.id]
      });
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

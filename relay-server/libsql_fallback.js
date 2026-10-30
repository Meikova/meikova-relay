const { spawnSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');

let nodeSqlite = null;
try {
  const { DatabaseSync } = require('node:sqlite');
  nodeSqlite = DatabaseSync;
} catch (_) {}

const PY_SQLITE_RUNNER = `
import sys, json, sqlite3

req = json.loads(sys.stdin.read())
db_path = req["db_path"]
mode = req["mode"]
conn = sqlite3.connect(db_path, timeout=15.0)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

try:
    if mode == "multiple":
        cur.executescript(req["sql"])
        conn.commit()
        print(json.dumps({"ok": True, "rows": [], "rowsAffected": 0}))
    else:
        sql = req["sql"]
        args = req.get("args") or []
        cur.execute(sql, args)
        if cur.description:
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        else:
            rows = []
        affected = cur.rowcount if cur.rowcount is not None and cur.rowcount >= 0 else 0
        conn.commit()
        print(json.dumps({"ok": True, "rows": rows, "rowsAffected": affected}))
except Exception as e:
    print(json.dumps({"ok": False, "error": str(e)}))
finally:
    conn.close()
`;

function createClient(config = {}) {
  let rawUrl = String(config.url || '').trim();
  let dbPath;
  if (!rawUrl || rawUrl.startsWith('libsql://') || rawUrl.startsWith('https://')) {
    dbPath = path.join(os.tmpdir(), 'meikova_turso_local_sim.db');
  } else if (rawUrl.startsWith('file:')) {
    dbPath = rawUrl.replace(/^file:\/\//, '').replace(/^file:/, '');
  } else {
    dbPath = rawUrl;
  }

  // 1. Prefer Node.js native DatabaseSync (node:sqlite) - zero dependency, native speed
  if (nodeSqlite) {
    const dbDir = path.dirname(dbPath);
    if (!fs.existsSync(dbDir)) {
      try { fs.mkdirSync(dbDir, { recursive: true }); } catch (_) {}
    }
    const db = new nodeSqlite(dbPath);
    return {
      async execute(stmt) {
        const sql = typeof stmt === 'string' ? stmt : stmt.sql;
        const args = typeof stmt === 'string' ? [] : (stmt.args || []);
        const isSelect = /^\s*(SELECT|PRAGMA)\b/i.test(sql);
        const prepared = db.prepare(sql);
        if (isSelect) {
          const rows = prepared.all(...args);
          return { rows, rowsAffected: 0 };
        } else {
          const res = prepared.run(...args);
          return { rows: [], rowsAffected: res.changes || 0, lastInsertRowid: res.lastInsertRowid };
        }
      },
      async executeMultiple(sql) {
        db.exec(sql);
        return { rows: [], rowsAffected: 0 };
      },
      async close() {
        try { db.close(); } catch (_) {}
      }
    };
  }

  // 2. Fallback to python runner if nodeSqlite is unavailable
  const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';

  function runPy(payload) {
    let res = spawnSync(pythonCmd, ['-c', PY_SQLITE_RUNNER], {
      input: JSON.stringify({ ...payload, db_path: dbPath }),
      encoding: 'utf8',
      maxBuffer: 32 * 1024 * 1024
    });
    if (res.error && pythonCmd !== 'python') {
      res = spawnSync('python', ['-c', PY_SQLITE_RUNNER], {
        input: JSON.stringify({ ...payload, db_path: dbPath }),
        encoding: 'utf8',
        maxBuffer: 32 * 1024 * 1024
      });
    }
    if (res.error) throw res.error;
    const out = (res.stdout || '').trim();
    if (!out) {
      throw new Error(res.stderr || 'Empty sqlite runner output');
    }
    const parsed = JSON.parse(out);
    if (!parsed.ok) {
      throw new Error(parsed.error || 'SQLite error');
    }
    return {
      rows: parsed.rows || [],
      rowsAffected: parsed.rowsAffected || 0
    };
  }

  return {
    async execute(stmt) {
      if (typeof stmt === 'string') {
        return runPy({ mode: 'single', sql: stmt, args: [] });
      }
      return runPy({ mode: 'single', sql: stmt.sql, args: stmt.args || [] });
    },
    async executeMultiple(sql) {
      return runPy({ mode: 'multiple', sql });
    },
    async close() {}
  };
}

module.exports = { createClient };

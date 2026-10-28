const { spawnSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');

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

  function runPy(payload) {
    const res = spawnSync('python3', ['-c', PY_SQLITE_RUNNER], {
      input: JSON.stringify({ ...payload, db_path: dbPath }),
      encoding: 'utf8',
      maxBuffer: 32 * 1024 * 1024
    });
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

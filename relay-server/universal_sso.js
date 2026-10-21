/**
 * Meikova Platform — Universal SSO & Auth Gateway Module (Node.js)
 * Zero external dependencies (uses native Node.js crypto stdlib).
 * High-performance offline token verification in ~0.1ms using Ed25519.
 */

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const SHARED_DIR = __dirname;
const KEYS_DIR = path.join(SHARED_DIR, 'keys');
const DEFAULT_PUB_KEY = path.join(KEYS_DIR, 'ed25519_public.pem');
const DEFAULT_PRIV_KEY = path.join(KEYS_DIR, 'ed25519_private.pem');

function b64urlEncode(buf) {
  return buf.toString('base64url');
}

function b64urlDecode(str) {
  return Buffer.from(str, 'base64url');
}

function resolveKey(filePath, envVarPem, envVarB64, fallbackPaths = []) {
  if (process.env[envVarPem]) {
    return process.env[envVarPem];
  }
  if (process.env[envVarB64]) {
    try {
      return Buffer.from(process.env[envVarB64], 'base64').toString('utf8');
    } catch (_) {}
  }
  const candidatePaths = [filePath, ...fallbackPaths];
  for (const p of candidatePaths) {
    if (p && fs.existsSync(p)) {
      try {
        return fs.readFileSync(p, 'utf8');
      } catch (_) {}
    }
  }
  return null;
}

class UniversalSSO {
  constructor(publicKeyPath, privateKeyPath) {
    const pubFallback = [
      path.join(__dirname, 'keys', 'ed25519_public.pem'),
      path.join(__dirname, '..', 'shared', 'keys', 'ed25519_public.pem'),
      path.join(__dirname, '..', '..', 'shared', 'keys', 'ed25519_public.pem')
    ];
    const privFallback = [
      path.join(__dirname, 'keys', 'ed25519_private.pem'),
      path.join(__dirname, '..', 'shared', 'keys', 'ed25519_private.pem'),
      path.join(__dirname, '..', '..', 'shared', 'keys', 'ed25519_private.pem')
    ];

    this.publicKeyPem = resolveKey(publicKeyPath || DEFAULT_PUB_KEY, 'AUTH_PUBLIC_KEY_PEM', 'AUTH_PUBLIC_KEY_B64', pubFallback);
    this.privateKeyPem = resolveKey(privateKeyPath || DEFAULT_PRIV_KEY, 'AUTH_PRIVATE_KEY_PEM', 'AUTH_PRIVATE_KEY_B64', privFallback);
  }

  issueToken({
    userId,
    username,
    email = null,
    displayName = null,
    role = 'user',
    expiresInSec = 30 * 86400
  }) {
    if (!this.privateKeyPem) {
      throw new Error('Private key not configured for issuing SSO tokens.');
    }

    const now = Math.floor(Date.now() / 1000);
    const header = { alg: 'EdDSA', typ: 'JWT' };
    const payload = {
      iss: 'meikova.auth',
      sub: String(userId),
      username: String(username),
      email: email ? String(email) : null,
      display_name: String(displayName || username),
      role: String(role),
      iat: now,
      exp: now + expiresInSec
    };

    const hB64 = b64urlEncode(Buffer.from(JSON.stringify(header)));
    const pB64 = b64urlEncode(Buffer.from(JSON.stringify(payload)));
    const signingInput = Buffer.from(`${hB64}.${pB64}`);

    const sig = crypto.sign(null, signingInput, this.privateKeyPem);
    const sigB64 = b64urlEncode(sig);

    return `${hB64}.${pB64}.${sigB64}`;
  }

  verifyToken(token) {
    if (!token || !this.publicKeyPem) return null;

    const parts = String(token).trim().split('.');
    if (parts.length !== 3) return null;

    const [hB64, pB64, sigB64] = parts;

    try {
      const signingInput = Buffer.from(`${hB64}.${pB64}`);
      const sig = b64urlDecode(sigB64);

      const isValid = crypto.verify(null, signingInput, this.publicKeyPem, sig);
      if (!isValid) return null;

      const payload = JSON.parse(b64urlDecode(pB64).toString('utf8'));
      const now = Math.floor(Date.now() / 1000);
      if (payload.exp && payload.exp < now) {
        return null; // Expired
      }

      return payload;
    } catch {
      return null;
    }
  }
}

const defaultSSO = new UniversalSSO();

module.exports = {
  UniversalSSO,
  issueUniversalToken: (args) => defaultSSO.issueToken(args),
  verifyUniversalToken: (token) => defaultSSO.verifyToken(token)
};

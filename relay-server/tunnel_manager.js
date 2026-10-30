/**
 * Meikova Platform - Universal Tunnel Manager
 * Integrates Cloudflare Quick Tunnel (trycloudflare.com) for One-Click WAN exposure
 * Zero-config, NAT/Firewall traversal, HTTPS encryption, Edge PoP & Latency Detection
 */

const { spawn, execSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const https = require('https');
const net = require('net');

// Cloudflare Edge Colocation (IATA Airport Codes) SSOT Map
const COLO_LOCATIONS = {
  HAN: 'Hà Nội (Việt Nam)',
  SGN: 'TP. Hồ Chí Minh (Việt Nam)',
  HKG: 'Hong Kong',
  SIN: 'Singapore',
  BKK: 'Bangkok (Thái Lan)',
  KUL: 'Kuala Lumpur (Malaysia)',
  TPE: 'Đài Bắc (Taiwan)',
  NRT: 'Tokyo Narita (Nhật Bản)',
  HND: 'Tokyo Haneda (Nhật Bản)',
  KIX: 'Osaka (Nhật Bản)',
  ICN: 'Seoul (Hàn Quốc)',
  MNL: 'Manila (Philippines)',
  CGK: 'Jakarta (Indonesia)',
  SYD: 'Sydney (Úc)',
  MEL: 'Melbourne (Úc)',
  LAX: 'Los Angeles (Mỹ)',
  SFO: 'San Francisco (Mỹ)',
  SJC: 'San Jose (Mỹ)',
  SEA: 'Seattle (Mỹ)',
  ORD: 'Chicago (Mỹ)',
  IAD: 'Washington DC (Mỹ)',
  EWR: 'Newark / New York (Mỹ)',
  JFK: 'New York (Mỹ)',
  LHR: 'London (Anh)',
  FRA: 'Frankfurt (Đức)',
  AMS: 'Amsterdam (Hà Lan)',
  CDG: 'Paris (Pháp)'
};

class CloudflaredTunnelManager {
  constructor() {
    this.process = null;
    this.tunnelUrl = null;
    this.status = 'idle'; // 'idle' | 'starting' | 'running' | 'failed'
    this.error = null;
    this.startedAt = null;
    this.activePort = 8080;
    this.edgeIpVersion = 'auto'; // 'auto' | '4' | '6'
    this.edgeColo = null; // 'HKG', 'SIN', 'HAN', etc.
    this.edgeLocation = null; // 'Hong Kong', 'Singapore', etc.
    this.latencyMs = null; // Measured round-trip latency in ms
    this._startPromise = null;
    this.onStateChange = null;
  }

  findCloudflared() {
    // 1. Check PATH
    try {
      const cmd = process.platform === 'win32' ? 'where cloudflared' : 'which cloudflared';
      const out = execSync(cmd, { stdio: ['ignore', 'pipe', 'ignore'], encoding: 'utf-8' }).trim();
      if (out) {
        const firstLine = out.split(/\r?\n/)[0].trim();
        if (fs.existsSync(firstLine)) return firstLine;
      }
    } catch (_) {}

    // 2. Standard filesystem paths
    const candidates = [];
    if (process.platform === 'win32') {
      const progFilesX86 = process.env['ProgramFiles(x86)'];
      const progFiles = process.env['ProgramFiles'];
      const localAppData = process.env['LOCALAPPDATA'];

      if (progFilesX86) candidates.push(path.join(progFilesX86, 'cloudflared', 'cloudflared.exe'));
      if (progFiles) candidates.push(path.join(progFiles, 'cloudflared', 'cloudflared.exe'));
      if (localAppData) {
        candidates.push(path.join(localAppData, 'Programs', 'cloudflared', 'cloudflared.exe'));
        candidates.push(path.join(localAppData, 'Microsoft', 'WinGet', 'Packages', 'cloudflared.exe'));
      }
    } else {
      candidates.push('/usr/local/bin/cloudflared');
      candidates.push('/usr/bin/cloudflared');
      candidates.push('/opt/homebrew/bin/cloudflared');
    }

    for (const cand of candidates) {
      if (cand && fs.existsSync(cand)) {
        return cand;
      }
    }

    return null;
  }

  getInstallCommand() {
    if (process.platform === 'win32') {
      return 'winget install --id Cloudflare.cloudflared --exact --silent';
    } else if (process.platform === 'darwin') {
      return 'brew install cloudflared';
    } else {
      return 'curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb && sudo dpkg -i cloudflared.deb';
    }
  }

  getStatus() {
    const bin = this.findCloudflared();
    return {
      running: this.status === 'running',
      status: this.status,
      url: this.tunnelUrl,
      error: this.error,
      startedAt: this.startedAt,
      port: this.activePort,
      installed: !!bin,
      binaryPath: bin,
      platform: process.platform,
      installCommand: this.getInstallCommand(),
      edgeIpVersion: this.edgeIpVersion,
      edgeColo: this.edgeColo,
      edgeLocation: this.edgeLocation,
      latencyMs: this.latencyMs
    };
  }

  async start(port = 8080, ipVersion = 'auto') {
    if (this.status === 'running' && this.tunnelUrl) {
      return this.getStatus();
    }
    if (this._startPromise) {
      return this._startPromise;
    }

    const bin = this.findCloudflared();
    if (!bin) {
      this.status = 'failed';
      this.error = 'CLOUDFLARED_NOT_INSTALLED';
      throw new Error(this.error);
    }

    this.activePort = port;
    this.edgeIpVersion = ipVersion || 'auto';
    this.edgeColo = null;
    this.edgeLocation = null;
    this.latencyMs = null;
    this.status = 'starting';
    this.error = null;
    this._notifyState();

    this._startPromise = new Promise((resolve, reject) => {
      let resolved = false;

      try {
        const args = [
          'tunnel',
          '--protocol', 'http2',
          '--edge-ip-version', this.edgeIpVersion,
          '--no-autoupdate',
          '--url', `http://127.0.0.1:${port}`
        ];
        this.process = spawn(bin, args, {
          windowsHide: true,
          stdio: ['ignore', 'pipe', 'pipe']
        });
      } catch (err) {
        this.status = 'failed';
        this.error = err.message;
        this._startPromise = null;
        this._notifyState();
        return reject(err);
      }

      const timeout = setTimeout(() => {
        if (!resolved) {
          resolved = true;
          this.stop();
          this.status = 'failed';
          this.error = 'TUNNEL_CONNECTION_TIMEOUT';
          this._startPromise = null;
          this._notifyState();
          reject(new Error(this.error));
        }
      }, 35000);

      const handleData = (data) => {
        const text = data.toString('utf-8');

        // Detect Edge PoP Colocation (e.g., location=hkg09, location=sin02)
        const locMatch = text.match(/location=([a-zA-Z]{3})[0-9]*/i);
        if (locMatch && !this.edgeColo) {
          const code = locMatch[1].toUpperCase();
          this.edgeColo = code;
          this.edgeLocation = COLO_LOCATIONS[code] || code;
          if (resolved) {
            this._notifyState();
          }
        }

        const match = text.match(/https:\/\/[a-zA-Z0-9-]+\.trycloudflare\.com/);
        if (match && !resolved) {
          resolved = true;
          clearTimeout(timeout);
          this.tunnelUrl = match[0];
          this.status = 'running';
          this.startedAt = Date.now();
          this._startPromise = null;
          this._notifyState();
          this._measureLatency();
          resolve(this.getStatus());
        }
      };

      if (this.process.stdout) this.process.stdout.on('data', handleData);
      if (this.process.stderr) this.process.stderr.on('data', handleData);

      this.process.on('error', (err) => {
        if (!resolved) {
          resolved = true;
          clearTimeout(timeout);
          this.status = 'failed';
          this.error = err.message;
          this._startPromise = null;
          this._notifyState();
          reject(err);
        }
      });

      this.process.on('close', (code) => {
        if (!resolved) {
          resolved = true;
          clearTimeout(timeout);
          this.status = 'failed';
          this.error = `Process exited prematurely with code ${code}`;
          this._startPromise = null;
          this._notifyState();
          reject(new Error(this.error));
        } else {
          this.status = 'idle';
          this.tunnelUrl = null;
          this.process = null;
          this.edgeColo = null;
          this.edgeLocation = null;
          this.latencyMs = null;
          this._startPromise = null;
          this._notifyState();
        }
      });
    });

    return this._startPromise;
  }

  _measureLatency(retries = 2) {
    if (this.status !== 'running') return;
    try {
      // 1. Measure pure 1-RTT TCP Handshake Latency directly to Cloudflare Anycast IP
      const pingStart = Date.now();
      const socket = net.connect({ host: '1.1.1.1', port: 443, timeout: 3000 }, () => {
        this.latencyMs = Date.now() - pingStart;
        socket.destroy();
        this._notifyState();
      });
      socket.on('error', () => { socket.destroy(); });
      socket.on('timeout', () => { socket.destroy(); });

      // 2. Fetch Colo identity from Cloudflare trace
      const req = https.get({
        hostname: '1.1.1.1',
        port: 443,
        path: '/cdn-cgi/trace',
        timeout: 4000,
        headers: { 'User-Agent': 'MeikovaRelay-ColoCheck' }
      }, (res) => {
        let body = '';
        res.on('data', chunk => { body += chunk; });
        res.on('end', () => {
          const match = body.match(/^colo=([A-Z]{3})/m);
          if (match && !this.edgeColo) {
            const code = match[1].toUpperCase();
            this.edgeColo = code;
            this.edgeLocation = COLO_LOCATIONS[code] || code;
            this._notifyState();
          }
        });
      });
      req.on('error', () => {
        if (retries > 0 && this.status === 'running') {
          setTimeout(() => this._measureLatency(retries - 1), 1500);
        }
      });
      req.on('timeout', () => { req.destroy(); });
    } catch (_) {}
  }

  stop() {
    if (this.process) {
      try {
        if (process.platform === 'win32' && this.process.pid) {
          execSync(`taskkill /pid ${this.process.pid} /t /f`, { stdio: 'ignore' });
        } else {
          this.process.kill('SIGTERM');
        }
      } catch (_) {
        try { this.process.kill('SIGKILL'); } catch (__) {}
      }
      this.process = null;
    }
    this.status = 'idle';
    this.tunnelUrl = null;
    this.startedAt = null;
    this.edgeColo = null;
    this.edgeLocation = null;
    this.latencyMs = null;
    this._startPromise = null;
    this._notifyState();
    return this.getStatus();
  }

  toggle(port = 8080, ipVersion = 'auto') {
    if (this.status === 'running') {
      return this.stop();
    } else {
      return this.start(port, ipVersion);
    }
  }

  _notifyState() {
    if (typeof this.onStateChange === 'function') {
      try {
        this.onStateChange(this.getStatus());
      } catch (_) {}
    }
  }
}

const tunnelManager = new CloudflaredTunnelManager();

// Clean up child process on exit
process.on('exit', () => {
  tunnelManager.stop();
});

module.exports = {
  CloudflaredTunnelManager,
  tunnelManager,
  COLO_LOCATIONS
};

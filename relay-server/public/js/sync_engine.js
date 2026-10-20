/**
 * Titan Remote — Ambient Instrument Offline-First Sync Engine
 * 
 * Philosophy:
 * - Lightweight sync: User preferences, device bookmarks, quick connect history, custom labels.
 * - Heavy data stays strictly local: Screen capture ring buffers, audio PCM chunks, transfer binaries.
 * - Offline Queue: When offline or server unreachable, mutations are persisted locally.
 *   Immediately flushes pending queue upon reconnection (Last-Write-Wins based on timestamps).
 */

class TitanSyncEngine {
  constructor(options = {}) {
    this.apiUrl = options.apiUrl || '';
    this.storageKey = 'titan:sync:state';
    this.queueKey = 'titan:sync:queue';
    this.authToken = null;
    this.isOnline = typeof navigator !== 'undefined' ? navigator.onLine : true;
    this.statusListeners = [];
    this.isFlushing = false;
    this.pollInterval = null;

    // Load initial cached state from localStorage
    this.state = this._loadLocalState();
    this.queue = this._loadQueue();

    this._setupNetworkListeners();
    this.startAutoSync(30000); // Periodic 30s auto-sync
  }

  setAuthToken(token) {
    this.authToken = token;
    if (token) {
      this.syncNow();
    }
  }

  onStatusChange(fn) {
    if (typeof fn === 'function') {
      this.statusListeners.push(fn);
      // Immediately notify current status
      fn(this.getStatusSummary());
    }
  }

  _notifyStatus() {
    const summary = this.getStatusSummary();
    for (const fn of this.statusListeners) {
      try {
        fn(summary);
      } catch (e) {
        console.error('[SyncEngine] Listener error:', e);
      }
    }
  }

  getStatusSummary() {
    return {
      isOnline: this.isOnline,
      pendingCount: this.queue.length,
      lastSyncTime: this.state.updated_at || 0,
      label: !this.isOnline || this.queue.length > 0
        ? (this.queue.length > 0 ? `NGOẠI TUYẾN // CHỜ ĐỒNG BỘ (${this.queue.length})` : 'NGOẠI TUYẾN // CỤC BỘ')
        : 'ĐỒNG BỘ // CLOUD'
    };
  }

  _loadLocalState() {
    try {
      const raw = localStorage.getItem(this.storageKey);
      if (raw) return JSON.parse(raw);
    } catch (_) {}
    return {
      preferences: {
        lang: 'vi',
        theme: 'dark',
        defaultFps: 60,
        fitMode: 'contain',
        audioStream: true
      },
      device_bookmarks: [],
      quick_history: [],
      custom_labels: {},
      updated_at: 0
    };
  }

  _saveLocalState(newState) {
    this.state = { ...this.state, ...newState, updated_at: Date.now() };
    try {
      localStorage.setItem(this.storageKey, JSON.stringify(this.state));
    } catch (e) {
      console.warn('[SyncEngine] Failed to save local state:', e);
    }
    this._notifyStatus();
  }

  _loadQueue() {
    try {
      const raw = localStorage.getItem(this.queueKey);
      if (raw) return JSON.parse(raw);
    } catch (_) {}
    return [];
  }

  _saveQueue() {
    try {
      localStorage.setItem(this.queueKey, JSON.stringify(this.queue));
    } catch (e) {
      console.warn('[SyncEngine] Failed to save queue:', e);
    }
    this._notifyStatus();
  }

  _setupNetworkListeners() {
    if (typeof window === 'undefined') return;

    window.addEventListener('online', () => {
      this.isOnline = true;
      this._notifyStatus();
      this.flushQueue();
    });

    window.addEventListener('offline', () => {
      this.isOnline = false;
      this._notifyStatus();
    });
  }

  startAutoSync(ms = 30000) {
    if (this.pollInterval) clearInterval(this.pollInterval);
    this.pollInterval = setInterval(() => {
      if (this.isOnline && this.authToken) {
        this.flushQueue();
      }
    }, ms);
  }

  stopAutoSync() {
    if (this.pollInterval) clearInterval(this.pollInterval);
  }

  // --- API Mutators ---
  updatePreferences(prefs) {
    const updated = { ...this.state.preferences, ...prefs };
    this._saveLocalState({ preferences: updated });
    this._enqueueMutation('preferences', updated);
  }

  addBookmark(deviceId) {
    if (!deviceId) return;
    const set = new Set(this.state.device_bookmarks || []);
    set.add(deviceId);
    const list = Array.from(set);
    this._saveLocalState({ device_bookmarks: list });
    this._enqueueMutation('device_bookmarks', list);
  }

  removeBookmark(deviceId) {
    const list = (this.state.device_bookmarks || []).filter(id => id !== deviceId);
    this._saveLocalState({ device_bookmarks: list });
    this._enqueueMutation('device_bookmarks', list);
  }

  addQuickConnectHistory(roomInfo) {
    if (!roomInfo || !roomInfo.roomId) return;
    const history = (this.state.quick_history || []).filter(h => h.roomId !== roomInfo.roomId);
    history.unshift({
      roomId: roomInfo.roomId,
      deviceName: roomInfo.deviceName || roomInfo.roomId,
      timestamp: Date.now()
    });
    const trimmed = history.slice(0, 15); // keep last 15 recent
    this._saveLocalState({ quick_history: trimmed });
    this._enqueueMutation('quick_history', trimmed);
  }

  setDeviceAlias(deviceId, alias) {
    if (!deviceId) return;
    const labels = { ...(this.state.custom_labels || {}), [deviceId]: String(alias).trim() };
    this._saveLocalState({ custom_labels: labels });
    this._enqueueMutation('custom_labels', labels);
  }

  _enqueueMutation(field, data) {
    const item = {
      id: `${Date.now()}_${Math.random().toString(36).substr(2, 6)}`,
      field,
      data,
      timestamp: Date.now()
    };
    this.queue.push(item);
    this._saveQueue();

    // Trigger immediate flush if online
    if (this.isOnline && this.authToken) {
      this.flushQueue();
    }
  }

  async syncNow() {
    await this.flushQueue();
    await this.pullRemoteState();
  }

  async flushQueue() {
    if (this.isFlushing || this.queue.length === 0 || !this.authToken) return;
    this.isFlushing = true;

    try {
      // Build composite payload from queue items
      const payload = {};
      for (const q of this.queue) {
        payload[q.field] = q.data;
      }

      const res = await fetch(`${this.apiUrl}/api/sync/push`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.authToken}`
        },
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        const body = await res.json();
        this.queue = [];
        this._saveQueue();
        if (body.updated_at) {
          this.state.updated_at = body.updated_at;
          localStorage.setItem(this.storageKey, JSON.stringify(this.state));
        }
        this.isOnline = true;
      } else if (res.status === 401) {
        // Auth expired, keep queue intact
        console.warn('[SyncEngine] Auth session invalid, keeping offline queue');
      } else {
        this.isOnline = false;
      }
    } catch (err) {
      // Network failure: retain queue in local storage, sync on reconnect
      this.isOnline = false;
    } finally {
      this.isFlushing = false;
      this._notifyStatus();
    }
  }

  async pullRemoteState() {
    if (!this.authToken || !this.isOnline) return;

    try {
      const res = await fetch(`${this.apiUrl}/api/sync/pull`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${this.authToken}`
        }
      });

      if (res.ok) {
        const result = await res.json();
        const remote = result.data;
        if (remote && remote.updated_at > (this.state.updated_at || 0)) {
          // Last-Write-Wins: Remote is fresher
          this.state = {
            preferences: { ...this.state.preferences, ...remote.preferences },
            device_bookmarks: remote.device_bookmarks || this.state.device_bookmarks,
            quick_history: remote.quick_history || this.state.quick_history,
            custom_labels: { ...this.state.custom_labels, ...remote.custom_labels },
            updated_at: remote.updated_at
          };
          localStorage.setItem(this.storageKey, JSON.stringify(this.state));
        }
        this.isOnline = true;
      }
    } catch (err) {
      this.isOnline = false;
    } finally {
      this._notifyStatus();
    }
  }
}

// Attach globally for browser / webview usage
if (typeof window !== 'undefined') {
  window.TitanSyncEngine = TitanSyncEngine;
  window.titanSync = new TitanSyncEngine();
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = TitanSyncEngine;
}

// Titan Remote Enterprise - Ambient Instrument Web Application
(function () {
  'use strict';

  // DOM Navigation & Views
  const mainNav = document.getElementById('mainNav');
  const authSection = document.getElementById('authSection');
  const dashboardSection = document.getElementById('dashboardSection');
  const remoteSection = document.getElementById('remoteSection');
  const shelfDrawer = document.getElementById('shelfDrawer');

  // Auth DOM
  const authTabs = document.getElementById('authTabs');
  const authForm = document.getElementById('authForm');
  const authUsername = document.getElementById('authUsername');
  const authPassword = document.getElementById('authPassword');
  const btnSubmitAuth = document.getElementById('btnSubmitAuth');
  const authError = document.getElementById('authError');
  const userBadge = document.getElementById('userBadge');
  const userNameDisplay = document.getElementById('userNameDisplay');
  const btnLogout = document.getElementById('btnLogout');

  // Dashboard DOM
  const deviceGrid = document.getElementById('deviceGrid');
  const btnOpenLinkModal = document.getElementById('btnOpenLinkModal');
  const btnQuickConnect = document.getElementById('btnQuickConnect');
  const quickConnectModal = document.getElementById('quickConnectModal');
  const quickConnectForm = document.getElementById('quickConnectForm');
  const btnCancelQC = document.getElementById('btnCancelQC');
  const qcRelayUrl = document.getElementById('qcRelayUrl');
  const qcRoomId = document.getElementById('qcRoomId');
  const qcPin = document.getElementById('qcPin');

  // Remote Canvas & HUD DOM
  const remoteCanvas = document.getElementById('remoteCanvas');
  const ctx = remoteCanvas.getContext('2d');
  const roStatus = document.getElementById('roStatus');
  const metricPing = document.getElementById('metricPing');
  const metricFps = document.getElementById('metricFps');
  const metricRes = document.getElementById('metricRes');

  // Bottom Deck Controls DOM
  const monitorSelector = document.getElementById('monitorSelector');
  const btnScaleToggle = document.getElementById('btnScaleToggle');
  const scaleLabel = document.getElementById('scaleLabel');
  const btnFullscreen = document.getElementById('btnFullscreen');
  const btnToggleOSK = document.getElementById('btnToggleOSK');
  const oskOverlay = document.getElementById('oskOverlay');
  const btnOpenShelf = document.getElementById('btnOpenShelf');
  const btnCloseShelf = document.getElementById('btnCloseShelf');
  const btnDisconnect = document.getElementById('btnDisconnect');

  // Shelf Drawer DOM
  const shelfTabs = document.querySelectorAll('.shelf-tabs button');
  const shelfFilesTab = document.getElementById('shelfFilesTab');
  const shelfClipboardTab = document.getElementById('shelfClipboardTab');
  const fileDropzone = document.getElementById('fileDropzone');
  const fileInput = document.getElementById('fileInput');
  const uploadProgressContainer = document.getElementById('uploadProgressContainer');
  const uploadFileName = document.getElementById('uploadFileName');
  const uploadPercent = document.getElementById('uploadPercent');
  const uploadProgressBar = document.getElementById('uploadProgressBar');
  const clipboardViewer = document.getElementById('clipboardViewer');
  const btnPushClipboard = document.getElementById('btnPushClipboard');

  // Application State
  let authToken = localStorage.getItem('titan_token') || null;
  let currentUser = null;
  let authMode = 'login'; // 'login' | 'register'
  let currentView = 'dashboard';

  let ws = null;
  let isConnected = false;
  let currentRoom = null;
  let hostResolution = { width: 1920, height: 1080 };
  let isFitMode = true;

  // Zoom & Pan for Touch/Canvas
  let scale = 1.0;
  let panX = 0;
  let panY = 0;
  let touchStartDist = 0;
  let touchStartScale = 1.0;

  // Telemetry Metrics
  let frameCount = 0;
  let lastFpsUpdate = performance.now();
  let lastPingSend = 0;
  let pingIntervalId = null;

  // Key code mapping
  const JS_TO_VK = {
    Backspace: 0x08, Tab: 0x09, Clear: 0x0C, Enter: 0x0D, NumpadEnter: 0x0D,
    ShiftLeft: 0x10, ShiftRight: 0x10, ControlLeft: 0x11, ControlRight: 0x11,
    AltLeft: 0x12, AltRight: 0x12, Pause: 0x13, CapsLock: 0x14, Escape: 0x1B,
    Space: 0x20, PageUp: 0x21, PageDown: 0x22, End: 0x23, Home: 0x24,
    ArrowLeft: 0x25, ArrowUp: 0x26, ArrowRight: 0x27, ArrowDown: 0x28,
    PrintScreen: 0x2C, Insert: 0x2D, Delete: 0x2E,
    MetaLeft: 0x5B, MetaRight: 0x5C, ContextMenu: 0x5D,
    Digit0: 0x30, Digit1: 0x31, Digit2: 0x32, Digit3: 0x33, Digit4: 0x34,
    Digit5: 0x35, Digit6: 0x36, Digit7: 0x37, Digit8: 0x38, Digit9: 0x39,
    KeyA: 0x41, KeyB: 0x42, KeyC: 0x43, KeyD: 0x44, KeyE: 0x45, KeyF: 0x46,
    KeyG: 0x47, KeyH: 0x48, KeyI: 0x49, KeyJ: 0x4A, KeyK: 0x4B, KeyL: 0x4C,
    KeyM: 0x4D, KeyN: 0x4E, KeyO: 0x4F, KeyP: 0x50, KeyQ: 0x51, KeyR: 0x52,
    KeyS: 0x53, KeyT: 0x54, KeyU: 0x55, KeyV: 0x56, KeyW: 0x57, KeyX: 0x58,
    KeyY: 0x59, KeyZ: 0x5A,
    F1: 0x70, F2: 0x71, F3: 0x72, F4: 0x73, F5: 0x74, F6: 0x75,
    F7: 0x76, F8: 0x77, F9: 0x78, F10: 0x79, F11: 0x7A, F12: 0x7B
  };

  // Default server URLs
  const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const defaultWsUrl = `${wsProto}//${window.location.host}`;
  qcRelayUrl.value = defaultWsUrl;

  // --- REST API CALLS ---
  async function apiFetch(endpoint, method = 'GET', body = null) {
    const headers = { 'Content-Type': 'application/json' };
    if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
    const opts = { method, headers };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(endpoint, opts);
    return res.json();
  }

  // --- INITIALIZATION ---
  async function initApp() {
    if (authToken) {
      const data = await apiFetch('/api/auth/me');
      if (data.success && data.user) {
        currentUser = data.user;
        renderUserBadge();
        switchView('dashboard');
        loadDeviceFleet();
        return;
      }
    }
    switchView('auth');
  }

  function renderUserBadge() {
    if (currentUser) {
      userNameDisplay.textContent = currentUser.username;
      userBadge.classList.remove('hidden');
    } else {
      userBadge.classList.add('hidden');
    }
  }

  function switchView(view) {
    currentView = view;
    authSection.classList.add('hidden');
    dashboardSection.classList.add('hidden');
    remoteSection.classList.add('hidden');

    document.querySelectorAll('.segmented-nav .seg-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.view === view);
    });

    if (view === 'auth') {
      authSection.classList.remove('hidden');
      roStatus.textContent = 'ĐĂNG NHẬP';
    } else if (view === 'dashboard') {
      dashboardSection.classList.remove('hidden');
      roStatus.textContent = 'DANH SÁCH MÁY TRẠM';
      loadDeviceFleet();
    } else if (view === 'remote') {
      remoteSection.classList.remove('hidden');
      roStatus.textContent = isConnected ? `${currentRoom} // TRỰC TUYẾN` : 'CHƯA KẾT NỐI';
    }
  }

  // Navigation handlers
  mainNav.addEventListener('click', (e) => {
    const btn = e.target.closest('.seg-btn');
    if (!btn) return;
    const view = btn.dataset.view;
    if (view === 'shelf') {
      shelfDrawer.classList.toggle('open');
      return;
    }
    switchView(view);
  });

  // --- AUTHENTICATION ---
  authTabs.addEventListener('click', (e) => {
    const btn = e.target.closest('.seg-btn');
    if (!btn) return;
    authTabs.querySelectorAll('.seg-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    authMode = btn.dataset.authMode;
    btnSubmitAuth.textContent = authMode === 'login' ? 'Vào Bảng Điều Khiển' : 'Đăng Ký Tài Khoản';
    authError.classList.add('hidden');
  });

  authForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    authError.classList.add('hidden');
    const username = authUsername.value.trim();
    const password = authPassword.value;

    const endpoint = authMode === 'login' ? '/api/auth/login' : '/api/auth/register';
    try {
      const res = await apiFetch(endpoint, 'POST', { username, password });
      if (res.success && res.token) {
        authToken = res.token;
        localStorage.setItem('titan_token', authToken);
        currentUser = res.user;
        renderUserBadge();
        switchView('dashboard');
        loadDeviceFleet();
      } else {
        authError.textContent = res.message || 'Thao tác không thành công';
        authError.classList.remove('hidden');
      }
    } catch (err) {
      authError.textContent = `Lỗi mạng: ${err.message}`;
      authError.classList.remove('hidden');
    }
  });

  btnLogout.addEventListener('click', () => {
    authToken = null;
    currentUser = null;
    localStorage.removeItem('titan_token');
    renderUserBadge();
    switchView('auth');
  });

  // --- DASHBOARD FLEET ---
  async function loadDeviceFleet() {
    deviceGrid.innerHTML = '<p class="mono-font" style="color: #64748B;">Đang tải danh sách máy trạm...</p>';
    try {
      const data = await apiFetch('/api/devices');
      if (data.success && data.devices) {
        renderDeviceGrid(data.devices);
      }
    } catch {
      deviceGrid.innerHTML = '<p class="mono-font" style="color: #EF4444;">Không thể tải danh sách thiết bị.</p>';
    }
  }

  function renderDeviceGrid(devices) {
    if (!devices || devices.length === 0) {
      deviceGrid.innerHTML = `
        <div class="empty-fleet">
          <p class="brand-font" style="font-size: 1.1rem; color: #F8FAFC; margin-bottom: 8px;">Chưa có máy trạm nào được liên kết</p>
          <p style="font-size: 0.85rem; margin-bottom: 16px;">Khởi chạy Host Agent trên máy công ty để kết nối vào hệ thống</p>
          <button id="btnEmptyAdd" class="btn-pill" style="border-color: var(--accent); color: var(--accent);">+ Thêm Máy Đầu Tiên</button>
        </div>
      `;
      document.getElementById('btnEmptyAdd')?.addEventListener('click', () => quickConnectModal.classList.remove('hidden'));
      return;
    }

    deviceGrid.innerHTML = devices.map(d => {
      const isOnline = d.is_online === 1;
      return `
        <div class="device-card">
          <div class="device-card-header">
            <span class="device-name brand-font">${escapeHtml(d.device_name)}</span>
            <span class="status-badge ${isOnline ? 'online' : 'offline'}">
              <span class="status-dot"></span> ${isOnline ? 'ONLINE' : 'OFFLINE'}
            </span>
          </div>
          <div class="device-specs">
            <span>OS: ${escapeHtml(d.os_info || 'Windows')}</span>
            <span>RES: ${escapeHtml(d.resolution || '1920x1080')}</span>
            <span>ROOM: ${escapeHtml(d.room_id)}</span>
          </div>
          <button class="btn-connect-device" data-room="${d.room_id}" data-pin="${d.pin}">
            <span>${isOnline ? 'Kết Nối Máy Này' : 'Thử Kết Nối'}</span> →
          </button>
        </div>
      `;
    }).join('');

    // Attach click events
    deviceGrid.querySelectorAll('.btn-connect-device').forEach(btn => {
      btn.addEventListener('click', () => {
        const room = btn.dataset.room;
        const pin = btn.dataset.pin;
        startRemoteSession(defaultWsUrl, room, pin);
      });
    });
  }

  function escapeHtml(str) {
    return String(str || '').replace(/[&<>"']/g, m => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[m]));
  }

  // --- QUICK CONNECT MODAL ---
  btnQuickConnect.addEventListener('click', () => quickConnectModal.classList.remove('hidden'));
  btnOpenLinkModal.addEventListener('click', () => quickConnectModal.classList.remove('hidden'));
  btnCancelQC.addEventListener('click', () => quickConnectModal.classList.add('hidden'));

  quickConnectForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const url = qcRelayUrl.value.trim();
    const room = qcRoomId.value.trim();
    const pin = qcPin.value.trim();
    quickConnectModal.classList.add('hidden');
    startRemoteSession(url, room, pin);
  });

  // --- REMOTE DESKTOP SESSION ---
  function startRemoteSession(relayUrl, roomId, pin) {
    switchView('remote');
    roStatus.textContent = `${roomId} // ĐANG KẾT NỐI...`;
    currentRoom = roomId;

    if (ws) {
      ws.close();
      ws = null;
    }

    try {
      ws = new WebSocket(relayUrl);
      ws.binaryType = 'blob';
    } catch (err) {
      alert(`Không thể kết nối WebSocket: ${err.message}`);
      return;
    }

    ws.onopen = () => {
      roStatus.textContent = `${roomId} // XÁC THỰC...`;
      ws.send(JSON.stringify({
        type: 'init_client',
        room_id: roomId,
        pin: pin
      }));
    };

    ws.onmessage = async (event) => {
      // 1. Binary = Video frame
      if (event.data instanceof Blob) {
        handleIncomingFrame(event.data);
        return;
      }

      // 2. Control Messages
      try {
        const msg = JSON.parse(event.data);
        if (msg.status === 'ok' && msg.role === 'client') {
          isConnected = true;
          roStatus.textContent = `${roomId} // TRỰC TUYẾN`;
          if (msg.hostMeta) {
            updateHostResolution(msg.hostMeta.width, msg.hostMeta.height);
            if (msg.hostMeta.monitors) populateMonitors(msg.hostMeta.monitors);
          }
          startPingLoop();
        } else if (msg.status === 'error') {
          alert(`Lỗi: ${msg.message}`);
          disconnect();
        } else if (msg.type === 'host_ready') {
          updateHostResolution(msg.width, msg.height);
          if (msg.monitors) populateMonitors(msg.monitors, msg.active_id);
        } else if (msg.type === 'monitors_list') {
          populateMonitors(msg.monitors, msg.active_id);
        } else if (msg.type === 'clipboard_sync') {
          clipboardViewer.value = msg.text || '';
        } else if (msg.type === 'file_upload_progress') {
          uploadPercent.textContent = `${msg.progress}%`;
          uploadProgressBar.style.width = `${msg.progress}%`;
        } else if (msg.type === 'file_upload_result') {
          uploadProgressContainer.classList.add('hidden');
          alert(`Đã truyền tệp thành công: ${msg.result.filename}`);
        } else if (msg.type === 'pong') {
          const rtt = Math.round(performance.now() - lastPingSend);
          metricPing.textContent = rtt;
        } else if (msg.type === 'host_disconnected') {
          alert('Máy trạm đã ngắt kết nối!');
          disconnect();
        }
      } catch (err) {
        console.error('WS parse error:', err);
      }
    };

    ws.onclose = () => {
      if (isConnected) alert('Mất kết nối với máy trạm');
      disconnect();
    };
  }

  function disconnect() {
    isConnected = false;
    if (pingIntervalId) clearInterval(pingIntervalId);
    if (ws) {
      ws.close();
      ws = null;
    }
    switchView('dashboard');
  }

  btnDisconnect.addEventListener('click', disconnect);

  function startPingLoop() {
    if (pingIntervalId) clearInterval(pingIntervalId);
    pingIntervalId = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        lastPingSend = performance.now();
        ws.send(JSON.stringify({ type: 'ping', ts: Date.now() }));
      }
    }, 3000);
  }

  function updateHostResolution(w, h) {
    hostResolution.width = w;
    hostResolution.height = h;
    remoteCanvas.width = w;
    remoteCanvas.height = h;
    metricRes.textContent = `${w}x${h}`;
  }

  async function handleIncomingFrame(blob) {
    frameCount++;
    const now = performance.now();
    if (now - lastFpsUpdate >= 1000) {
      metricFps.textContent = frameCount;
      frameCount = 0;
      lastFpsUpdate = now;
    }

    try {
      const bitmap = await createImageBitmap(blob);
      if (remoteCanvas.width !== bitmap.width || remoteCanvas.height !== bitmap.height) {
        updateHostResolution(bitmap.width, bitmap.height);
      }
      ctx.drawImage(bitmap, 0, 0);
      bitmap.close();
    } catch {}
  }

  // --- MULTI-MONITOR SELECTION ---
  function populateMonitors(monitors, activeId = 1) {
    if (!monitors || monitors.length === 0) return;
    monitorSelector.innerHTML = monitors.map(m => `
      <option value="${m.id}" ${m.id == activeId ? 'selected' : ''}>${escapeHtml(m.name)} (${m.width}x${m.height})</option>
    `).join('');

    if (monitors.length > 1) {
      monitorSelector.innerHTML += `<option value="0" ${activeId === 0 ? 'selected' : ''}>Toàn Bộ Màn Hình</option>`;
    }
  }

  monitorSelector.addEventListener('change', () => {
    if (!isConnected) return;
    const monId = parseInt(monitorSelector.value, 10);
    ws.send(JSON.stringify({
      type: 'switch_monitor',
      monitor_id: monId
    }));
  });

  // --- SCALE & FULLSCREEN ---
  btnScaleToggle.addEventListener('click', () => {
    isFitMode = !isFitMode;
    remoteSection.classList.toggle('fit-mode', isFitMode);
    scaleLabel.textContent = isFitMode ? 'Fit' : '1:1';
    scale = 1.0;
    panX = 0;
    panY = 0;
    applyCanvasTransform();
  });

  btnFullscreen.addEventListener('click', () => {
    if (!document.fullscreenElement) {
      remoteSection.requestFullscreen().then(() => {
        // Request pointer lock for gaming / native precision
        if (remoteCanvas.requestPointerLock) {
          remoteCanvas.requestPointerLock().catch(() => {});
        }
      }).catch(() => {});
    } else {
      document.exitFullscreen().catch(() => {});
    }
  });

  function applyCanvasTransform() {
    remoteCanvas.style.transform = `translate(${panX}px, ${panY}px) scale(${scale})`;
  }

  // --- TOUCH PINCH-TO-ZOOM & PAN ---
  remoteCanvas.addEventListener('touchstart', (e) => {
    if (e.touches.length === 2) {
      e.preventDefault();
      const p1 = e.touches[0];
      const p2 = e.touches[1];
      touchStartDist = Math.hypot(p2.clientX - p1.clientX, p2.clientY - p1.clientY);
      touchStartScale = scale;
    }
  }, { passive: false });

  remoteCanvas.addEventListener('touchmove', (e) => {
    if (e.touches.length === 2) {
      e.preventDefault();
      const p1 = e.touches[0];
      const p2 = e.touches[1];
      const dist = Math.hypot(p2.clientX - p1.clientX, p2.clientY - p1.clientY);
      if (touchStartDist > 0) {
        scale = Math.max(0.5, Math.min(4.0, touchStartScale * (dist / touchStartDist)));
        applyCanvasTransform();
      }
    }
  }, { passive: false });

  // --- MOUSE TRACKING ---
  function getNormalizedCoords(e) {
    const rect = remoteCanvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;
    return {
      x: Math.max(0.0, Math.min(1.0, x)),
      y: Math.max(0.0, Math.min(1.0, y))
    };
  }

  let lastMove = 0;
  remoteCanvas.addEventListener('mousemove', (e) => {
    if (!isConnected) return;
    const now = performance.now();
    if (now - lastMove < 25) return;
    lastMove = now;

    const coords = getNormalizedCoords(e);
    ws.send(JSON.stringify({
      type: 'mouse_move',
      x: coords.x,
      y: coords.y
    }));
  });

  remoteCanvas.addEventListener('mousedown', (e) => {
    if (!isConnected) return;
    e.preventDefault();
    remoteCanvas.focus();
    ws.send(JSON.stringify({
      type: 'mouse_down',
      button: e.button
    }));
  });

  remoteCanvas.addEventListener('mouseup', (e) => {
    if (!isConnected) return;
    e.preventDefault();
    ws.send(JSON.stringify({
      type: 'mouse_up',
      button: e.button
    }));
  });

  remoteCanvas.addEventListener('contextmenu', e => e.preventDefault());

  remoteCanvas.addEventListener('wheel', (e) => {
    if (!isConnected) return;
    e.preventDefault();
    ws.send(JSON.stringify({
      type: 'mouse_wheel',
      delta_y: -e.deltaY
    }));
  }, { passive: false });

  // --- KEYBOARD CAPTURE ---
  window.addEventListener('keydown', (e) => {
    if (!isConnected || currentView !== 'remote') return;
    const vk = JS_TO_VK[e.code] || 0;
    if (vk > 0) {
      if (['Tab', 'AltLeft', 'AltRight', 'Backspace', 'F5', 'F11'].includes(e.code)) {
        e.preventDefault();
      }
      ws.send(JSON.stringify({
        type: 'key_down',
        code: e.code,
        vk: vk
      }));
    }
  });

  window.addEventListener('keyup', (e) => {
    if (!isConnected || currentView !== 'remote') return;
    const vk = JS_TO_VK[e.code] || 0;
    if (vk > 0) {
      if (['Tab', 'AltLeft', 'AltRight', 'Backspace'].includes(e.code)) {
        e.preventDefault();
      }
      ws.send(JSON.stringify({
        type: 'key_up',
        code: e.code,
        vk: vk
      }));
    }
  });

  // Hotkey Buttons on Deck
  document.querySelectorAll('[data-hotkey]').forEach(btn => {
    btn.addEventListener('click', () => {
      if (!isConnected) return;
      const key = btn.dataset.hotkey;
      if (key === 'win') {
        sendKeySequence([0x5B]);
      } else if (key === 'taskmgr') {
        sendHotKeyCombo([0x11, 0x10, 0x1B]); // Ctrl+Shift+Esc
      } else if (key === 'alttab') {
        sendHotKeyCombo([0x12, 0x09]); // Alt+Tab
      } else if (key === 'esc') {
        sendKeySequence([0x1B]);
      }
    });
  });

  function sendKeySequence(vks) {
    vks.forEach(vk => {
      ws.send(JSON.stringify({ type: 'key_down', vk }));
      setTimeout(() => ws.send(JSON.stringify({ type: 'key_up', vk })), 50);
    });
  }

  function sendHotKeyCombo(vks) {
    vks.forEach(vk => ws.send(JSON.stringify({ type: 'key_down', vk })));
    setTimeout(() => {
      [...vks].reverse().forEach(vk => ws.send(JSON.stringify({ type: 'key_up', vk })));
    }, 100);
  }

  // --- ON-SCREEN KEYBOARD (OSK) ---
  btnToggleOSK.addEventListener('click', () => {
    oskOverlay.classList.toggle('hidden');
    btnToggleOSK.classList.toggle('btn-active', !oskOverlay.classList.contains('hidden'));
  });

  oskOverlay.addEventListener('click', (e) => {
    const keyBtn = e.target.closest('.osk-key');
    if (!keyBtn || !isConnected) return;
    const key = keyBtn.dataset.key;
    const vk = JS_TO_VK[key] || 0;
    if (vk > 0) {
      sendKeySequence([vk]);
    }
  });

  // --- SIDE SHELF: FILE TRANSFER & CLIPBOARD ---
  btnOpenShelf.addEventListener('click', () => shelfDrawer.classList.add('open'));
  btnCloseShelf.addEventListener('click', () => shelfDrawer.classList.remove('open'));

  shelfTabs.forEach(btn => {
    btn.addEventListener('click', () => {
      shelfTabs.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const tab = btn.dataset.shelfTab;
      shelfFilesTab.classList.toggle('hidden', tab !== 'files');
      shelfClipboardTab.classList.toggle('hidden', tab !== 'clipboard');
    });
  });

  // Clipboard Push
  btnPushClipboard.addEventListener('click', () => {
    if (!isConnected) return;
    const text = clipboardViewer.value;
    ws.send(JSON.stringify({
      type: 'clipboard_sync',
      text: text
    }));
    alert('Đã đồng bộ sang bộ nhớ tạm của máy trạm!');
  });

  // File Upload via Drag-and-Drop & File Picker
  fileDropzone.addEventListener('click', () => fileInput.click());
  fileDropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    fileDropzone.classList.add('dragover');
  });
  fileDropzone.addEventListener('dragleave', () => fileDropzone.classList.remove('dragover'));
  fileDropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    fileDropzone.classList.remove('dragover');
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      uploadFileToHost(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files && fileInput.files[0]) {
      uploadFileToHost(fileInput.files[0]);
    }
  });

  async function uploadFileToHost(file) {
    if (!isConnected) {
      alert('Vui lòng kết nối vào máy trạm trước khi gửi tệp tin!');
      return;
    }

    uploadFileName.textContent = file.name;
    uploadPercent.textContent = '0%';
    uploadProgressBar.style.width = '0%';
    uploadProgressContainer.classList.remove('hidden');

    const transferId = 'transfer_' + Date.now();
    const chunkSize = 64 * 1024; // 64KB chunks
    const totalChunks = Math.ceil(file.size / chunkSize);

    ws.send(JSON.stringify({
      type: 'file_upload_start',
      transfer_id: transferId,
      filename: file.name,
      filesize: file.size
    }));

    for (let i = 0; i < totalChunks; i++) {
      const start = i * chunkSize;
      const end = Math.min(file.size, start + chunkSize);
      const slice = file.slice(start, end);
      const buffer = await slice.arrayBuffer();
      const b64 = arrayBufferToBase64(buffer);

      ws.send(JSON.stringify({
        type: 'file_upload_chunk',
        transfer_id: transferId,
        data: b64
      }));

      const progress = Math.round(((i + 1) / totalChunks) * 100);
      uploadPercent.textContent = `${progress}%`;
      uploadProgressBar.style.width = `${progress}%`;
    }

    ws.send(JSON.stringify({
      type: 'file_upload_finish',
      transfer_id: transferId
    }));
  }

  function arrayBufferToBase64(buffer) {
    let binary = '';
    const bytes = new Uint8Array(buffer);
    const len = bytes.byteLength;
    for (let i = 0; i < len; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return window.btoa(binary);
  }

  // Start app
  initApp();
})();

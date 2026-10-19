// Titan Remote Enterprise — Ambient Instrument Web Application
(function () {
  'use strict';

  // --- DOM Navigation & Views ---
  const mainNav = document.getElementById('mainNav');
  const authSection = document.getElementById('authSection');
  const dashboardSection = document.getElementById('dashboardSection');
  const remoteSection = document.getElementById('remoteSection');
  const terminalSection = document.getElementById('terminalSection');
  const tasksSection = document.getElementById('tasksSection');
  const shelfDrawer = document.getElementById('shelfDrawer');

  // --- Auth DOM ---
  const authTabs = document.getElementById('authTabs');
  const authForm = document.getElementById('authForm');
  const authUsername = document.getElementById('authUsername');
  const authPassword = document.getElementById('authPassword');
  const btnSubmitAuth = document.getElementById('btnSubmitAuth');
  const authError = document.getElementById('authError');
  const userBadge = document.getElementById('userBadge');
  const userNameDisplay = document.getElementById('userNameDisplay');
  const btnLogout = document.getElementById('btnLogout');

  // --- Dashboard DOM ---
  const deviceGrid = document.getElementById('deviceGrid');
  const btnOpenLinkModal = document.getElementById('btnOpenLinkModal');
  const btnQuickConnect = document.getElementById('btnQuickConnect');
  const quickConnectModal = document.getElementById('quickConnectModal');
  const quickConnectForm = document.getElementById('quickConnectForm');
  const btnCancelQC = document.getElementById('btnCancelQC');
  const qcRelayUrl = document.getElementById('qcRelayUrl');
  const qcRoomId = document.getElementById('qcRoomId');
  const qcPin = document.getElementById('qcPin');

  // --- Remote Canvas & Viewport DOM ---
  const viewportBox = document.getElementById('viewportBox');
  const remoteCanvas = document.getElementById('remoteCanvas');
  const ctx = remoteCanvas.getContext('2d');
  const laserCanvas = document.getElementById('laserCanvas');
  const laserCtx = laserCanvas.getContext('2d');
  const roStatus = document.getElementById('roStatus');
  const metricPing = document.getElementById('metricPing');
  const metricFps = document.getElementById('metricFps');
  const metricRes = document.getElementById('metricRes');

  // --- Floating Deck Controls DOM ---
  const floatingDeck = document.getElementById('floatingDeck');
  const monitorSelector = document.getElementById('monitorSelector');
  const qualitySelector = document.getElementById('qualitySelector');
  const btnScaleToggle = document.getElementById('btnScaleToggle');
  const scaleLabel = document.getElementById('scaleLabel');
  const btnFullscreen = document.getElementById('btnFullscreen');
  const btnToggleLaser = document.getElementById('btnToggleLaser');
  const btnRecord = document.getElementById('btnRecord');
  const recordLabel = document.getElementById('recordLabel');
  const btnScreenshot = document.getElementById('btnScreenshot');
  const btnToggleOSK = document.getElementById('btnToggleOSK');
  const oskOverlay = document.getElementById('oskOverlay');
  const btnPowerMenu = document.getElementById('btnPowerMenu');
  const powerMenuDropdown = document.getElementById('powerMenuDropdown');
  const btnOpenShelf = document.getElementById('btnOpenShelf');
  const btnCloseShelf = document.getElementById('btnCloseShelf');
  const btnDisconnect = document.getElementById('btnDisconnect');

  // --- Terminal View DOM ---
  const terminalOutput = document.getElementById('terminalOutput');
  const terminalInputForm = document.getElementById('terminalInputForm');
  const terminalCmdInput = document.getElementById('terminalCmdInput');
  const btnClearTerminal = document.getElementById('btnClearTerminal');

  // --- Task Manager DOM ---
  const btnRefreshTasks = document.getElementById('btnRefreshTasks');
  const ramValue = document.getElementById('ramValue');
  const ramGaugeBar = document.getElementById('ramGaugeBar');
  const ramSub = document.getElementById('ramSub');
  const diskCValue = document.getElementById('diskCValue');
  const diskCGaugeBar = document.getElementById('diskCGaugeBar');
  const diskCSub = document.getElementById('diskCSub');
  const processSearchInput = document.getElementById('processSearchInput');
  const processTableBody = document.getElementById('processTableBody');

  // --- Shelf Drawer DOM ---
  const shelfTabs = document.getElementById('shelfTabs');
  const shelfFilesTab = document.getElementById('shelfFilesTab');
  const shelfClipboardTab = document.getElementById('shelfClipboardTab');
  const fileDropzone = document.getElementById('fileDropzone');
  const fileInput = document.getElementById('fileInput');
  const uploadProgressContainer = document.getElementById('uploadProgressContainer');
  const uploadFileName = document.getElementById('uploadFileName');
  const uploadPercent = document.getElementById('uploadPercent');
  const uploadProgressBar = document.getElementById('uploadProgressBar');
  const btnBrowseUp = document.getElementById('btnBrowseUp');
  const currentFolderPath = document.getElementById('currentFolderPath');
  const remoteFolderList = document.getElementById('remoteFolderList');
  const clipboardViewer = document.getElementById('clipboardViewer');
  const btnPushClipboard = document.getElementById('btnPushClipboard');

  // --- Application State ---
  let authToken = localStorage.getItem('titan_token') || null;
  let currentUser = null;
  let authMode = 'login';
  let currentView = 'dashboard';

  let ws = null;
  let isConnected = false;
  let currentRoom = null;
  let hostResolution = { width: 1920, height: 1080 };
  let isFitMode = true;

  // Zoom & Pan
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

  // Inactivity Dimming
  let idleTimer = null;

  // Laser Pointer State
  let isLaserActive = false;
  let laserPos = { x: -100, y: -100 };
  let laserAnimId = null;

  // Recording State
  let mediaRecorder = null;
  let recordedChunks = [];
  let isRecording = false;

  // Process Manager State
  let currentProcessList = [];

  // File Manager State
  let remoteCurrentPath = '';
  let activeDownloads = {};

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

  // --- SLIDING SEGMENTED INDICATOR ENGINE (MASHLOOP PATTERN) ---
  function placeIndicator(seg) {
    if (!seg) return;
    const onBtn = seg.querySelector('button.on');
    const ind = seg.querySelector('.seg__ind');
    if (!onBtn || !ind) return;
    ind.style.setProperty('--ind-x', `${onBtn.offsetLeft}px`);
    ind.style.setProperty('--ind-w', `${onBtn.offsetWidth}px`);
  }

  function placeAllIndicators() {
    document.querySelectorAll('.seg').forEach(placeIndicator);
  }

  window.addEventListener('resize', placeAllIndicators);
  if (document.fonts) document.fonts.ready.then(placeAllIndicators);
  setTimeout(placeAllIndicators, 60);

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
      try {
        const data = await apiFetch('/api/auth/me');
        if (data.success && data.user) {
          currentUser = data.user;
          renderUserBadge();
          switchView('dashboard');
          loadDeviceFleet();
          return;
        }
      } catch {}
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
    terminalSection.classList.add('hidden');
    tasksSection.classList.add('hidden');

    mainNav.querySelectorAll('button').forEach(btn => {
      const isTarget = btn.dataset.view === view;
      btn.classList.toggle('on', isTarget);
      btn.setAttribute('aria-selected', isTarget ? 'true' : 'false');
    });
    placeIndicator(mainNav);

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
      resetDeckIdle();
    } else if (view === 'terminal') {
      terminalSection.classList.remove('hidden');
      roStatus.textContent = isConnected ? `${currentRoom} // TERMINAL` : 'CHƯA KẾT NỐI';
      terminalCmdInput.focus();
    } else if (view === 'tasks') {
      tasksSection.classList.remove('hidden');
      roStatus.textContent = isConnected ? `${currentRoom} // TIẾN TRÌNH` : 'CHƯA KẾT NỐI';
      if (isConnected) requestTelemetryAndTasks();
    }
  }

  // Navigation Click Handler
  mainNav.addEventListener('click', (e) => {
    const btn = e.target.closest('button');
    if (!btn) return;
    const view = btn.dataset.view;
    if (view === 'shelf') {
      shelfDrawer.classList.toggle('open');
      if (shelfDrawer.classList.contains('open') && isConnected) {
        requestBrowsePath(remoteCurrentPath);
      }
      return;
    }
    switchView(view);
  });

  // --- AUTHENTICATION ---
  authTabs.addEventListener('click', (e) => {
    const btn = e.target.closest('button');
    if (!btn) return;
    authTabs.querySelectorAll('button').forEach(b => b.classList.remove('on'));
    btn.classList.add('on');
    placeIndicator(authTabs);

    authMode = btn.dataset.authMode;
    btnSubmitAuth.textContent = authMode === 'login' ? 'Vào bảng điều khiển' : 'Đăng ký tài khoản';
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
      authError.textContent = `Lỗi kết nối: ${err.message}`;
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
    deviceGrid.innerHTML = '<p class="mono-font" style="color: var(--text-faint); padding: 20px;">Đang tải danh sách máy trạm...</p>';
    try {
      const data = await apiFetch('/api/devices');
      if (data.success && data.devices) {
        renderDeviceGrid(data.devices);
      }
    } catch {
      deviceGrid.innerHTML = '<p class="mono-font" style="color: #EF4444; padding: 20px;">Không thể tải danh sách thiết bị.</p>';
    }
  }

  function renderDeviceGrid(devices) {
    if (!devices || devices.length === 0) {
      deviceGrid.innerHTML = `
        <div class="empty-fleet" style="grid-column: 1 / -1; text-align: center; padding: 48px; background: var(--ink-1); border: 1px dashed var(--line); border-radius: var(--radius);">
          <p class="brand-font" style="font-size: 1.15rem; color: var(--text); margin-bottom: 8px;">Chưa có máy trạm nào được liên kết</p>
          <p style="font-size: var(--step--1); color: var(--text-muted); margin-bottom: 20px;">Khởi chạy Host Agent trên máy tính để liên kết tự động</p>
          <button id="btnEmptyAdd" class="btn-pill" style="border-color: var(--accent); color: var(--accent);">+ Kết nối nhanh bằng Room ID</button>
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
            <span>${isOnline ? 'Kết nối máy này' : 'Thử kết nối'}</span> →
          </button>
        </div>
      `;
    }).join('');

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
        } else if (msg.type === 'terminal_output') {
          handleTerminalOutput(msg.data || '');
        } else if (msg.type === 'telemetry_response') {
          handleTelemetryData(msg.data);
        } else if (msg.type === 'process_list_response') {
          handleProcessList(msg.processes || []);
        } else if (msg.type === 'process_kill_response') {
          alert(msg.success ? `Đã dừng tiến trình PID ${msg.pid}` : `Không thể dừng tiến trình PID ${msg.pid}`);
          if (currentView === 'tasks') requestTelemetryAndTasks();
        } else if (msg.type === 'file_browse_response') {
          renderFolderBrowser(msg.data);
        } else if (msg.type === 'file_upload_progress') {
          uploadPercent.textContent = `${msg.progress}%`;
          uploadProgressBar.style.width = `${msg.progress}%`;
        } else if (msg.type === 'file_upload_result') {
          uploadProgressContainer.classList.add('hidden');
          alert(`Đã truyền tệp thành công: ${msg.result.filename}`);
          requestBrowsePath(remoteCurrentPath);
        } else if (msg.type === 'file_download_start') {
          activeDownloads[msg.transfer_id] = {
            filename: msg.filename,
            totalBytes: msg.filesize,
            chunks: []
          };
        } else if (msg.type === 'file_download_chunk') {
          const dl = activeDownloads[msg.transfer_id];
          if (dl) {
            dl.chunks.push(base64ToArrayBuffer(msg.data));
          }
        } else if (msg.type === 'file_download_finish') {
          const dl = activeDownloads[msg.transfer_id];
          if (dl) {
            const blob = new Blob(dl.chunks, { type: 'application/octet-stream' });
            downloadBlob(blob, dl.filename);
            delete activeDownloads[msg.transfer_id];
          }
        } else if (msg.type === 'file_download_error') {
          alert(`Lỗi tải tệp: ${msg.message}`);
          delete activeDownloads[msg.transfer_id];
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
    stopRecording();
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
    laserCanvas.width = w;
    laserCanvas.height = h;
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

  // --- QUALITY PRESET ---
  qualitySelector.addEventListener('change', () => {
    if (!isConnected) return;
    ws.send(JSON.stringify({
      type: 'set_quality_preset',
      preset: qualitySelector.value
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
      remoteSection.requestFullscreen().catch(() => {});
    } else {
      document.exitFullscreen().catch(() => {});
    }
  });

  function applyCanvasTransform() {
    viewportBox.style.transform = `translate(${panX}px, ${panY}px) scale(${scale})`;
  }

  // --- INACTIVITY DIMMING FOR THE FLOATING DECK ---
  function resetDeckIdle() {
    floatingDeck.classList.remove('dimmed');
    clearTimeout(idleTimer);
    if (currentView === 'remote' && isConnected) {
      idleTimer = setTimeout(() => {
        if (!floatingDeck.matches(':hover') && !powerMenuDropdown.matches(':hover')) {
          floatingDeck.classList.add('dimmed');
        }
      }, 3500);
    }
  }

  remoteSection.addEventListener('mousemove', resetDeckIdle);
  remoteSection.addEventListener('mousedown', resetDeckIdle);

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

  // --- MOUSE TRACKING & COORDINATE CONVERSION ---
  function getNormalizedCoords(e) {
    const rect = remoteCanvas.getBoundingClientRect();
    const normX = Math.max(0.0, Math.min(1.0, (e.clientX - rect.left) / rect.width));
    const normY = Math.max(0.0, Math.min(1.0, (e.clientY - rect.top) / rect.height));
    return {
      x: normX,
      y: normY,
      pixelX: normX * remoteCanvas.width,
      pixelY: normY * remoteCanvas.height
    };
  }

  let lastMove = 0;
  remoteCanvas.addEventListener('mousemove', (e) => {
    if (!isConnected) return;
    const coords = getNormalizedCoords(e);

    if (isLaserActive) {
      laserPos.x = coords.pixelX;
      laserPos.y = coords.pixelY;
    }

    const now = performance.now();
    if (now - lastMove < 25) return;
    lastMove = now;

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

  // --- LASER POINTER OVERLAY RENDERING ---
  btnToggleLaser.addEventListener('click', () => {
    isLaserActive = !isLaserActive;
    btnToggleLaser.classList.toggle('btn-active', isLaserActive);
    if (isLaserActive) {
      startLaserLoop();
    } else {
      cancelAnimationFrame(laserAnimId);
      laserCtx.clearRect(0, 0, laserCanvas.width, laserCanvas.height);
    }
  });

  function startLaserLoop() {
    function drawLaser() {
      if (!isLaserActive) return;
      laserCtx.clearRect(0, 0, laserCanvas.width, laserCanvas.height);

      if (laserPos.x >= 0 && laserPos.y >= 0) {
        laserCtx.save();
        const rad = 20;
        const grad = laserCtx.createRadialGradient(laserPos.x, laserPos.y, 2, laserPos.x, laserPos.y, rad);
        grad.addColorStop(0, 'rgba(239, 68, 68, 1)');
        grad.addColorStop(0.4, 'rgba(239, 68, 68, 0.7)');
        grad.addColorStop(1, 'rgba(239, 68, 68, 0)');
        laserCtx.fillStyle = grad;
        laserCtx.beginPath();
        laserCtx.arc(laserPos.x, laserPos.y, rad, 0, Math.PI * 2);
        laserCtx.fill();

        laserCtx.fillStyle = '#FFFFFF';
        laserCtx.beginPath();
        laserCtx.arc(laserPos.x, laserPos.y, 3, 0, Math.PI * 2);
        laserCtx.fill();
        laserCtx.restore();
      }
      laserAnimId = requestAnimationFrame(drawLaser);
    }
    laserAnimId = requestAnimationFrame(drawLaser);
  }

  // --- SESSION RECORDING (WEBM) ---
  btnRecord.addEventListener('click', () => {
    if (!isConnected) {
      alert('Vui lòng kết nối vào máy trạm trước khi ghi hình!');
      return;
    }
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  });

  function startRecording() {
    try {
      const stream = remoteCanvas.captureStream(30);
      recordedChunks = [];
      mediaRecorder = new MediaRecorder(stream, { mimeType: 'video/webm' });
      mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) recordedChunks.push(e.data);
      };
      mediaRecorder.onstop = () => {
        const blob = new Blob(recordedChunks, { type: 'video/webm' });
        downloadBlob(blob, `titan-session-${Date.now()}.webm`);
        recordedChunks = [];
      };
      mediaRecorder.start();
      isRecording = true;
      btnRecord.classList.add('btn-active');
      recordLabel.textContent = 'Đang ghi...';
    } catch (err) {
      alert(`Không thể bắt đầu ghi hình: ${err.message}`);
    }
  }

  function stopRecording() {
    if (isRecording && mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
      isRecording = false;
      btnRecord.classList.remove('btn-active');
      recordLabel.textContent = 'Ghi';
    }
  }

  // --- CANVAS SCREENSHOT (PNG) ---
  btnScreenshot.addEventListener('click', () => {
    if (!isConnected) {
      alert('Chưa kết nối máy trạm');
      return;
    }
    remoteCanvas.toBlob((blob) => {
      if (blob) {
        downloadBlob(blob, `titan-screen-${Date.now()}.png`);
      }
    }, 'image/png');
  });

  function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  // --- KEYBOARD CAPTURE (PREVENT LEAKS INTO TEXT INPUTS) ---
  window.addEventListener('keydown', (e) => {
    if (!isConnected || currentView !== 'remote') return;

    // Do NOT capture keys when user is typing into an input field or textarea
    const activeEl = document.activeElement;
    const tag = activeEl ? activeEl.tagName.toLowerCase() : '';
    if (tag === 'input' || tag === 'textarea' || tag === 'select' || (activeEl && activeEl.isContentEditable)) {
      return;
    }

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

    const activeEl = document.activeElement;
    const tag = activeEl ? activeEl.tagName.toLowerCase() : '';
    if (tag === 'input' || tag === 'textarea' || tag === 'select' || (activeEl && activeEl.isContentEditable)) {
      return;
    }

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

  // --- POWER ACTIONS MENU ---
  btnPowerMenu.addEventListener('click', (e) => {
    e.stopPropagation();
    powerMenuDropdown.classList.toggle('hidden');
  });

  document.addEventListener('click', (e) => {
    if (!powerMenuDropdown.contains(e.target) && e.target !== btnPowerMenu) {
      powerMenuDropdown.classList.add('hidden');
    }
  });

  document.querySelectorAll('[data-power]').forEach(btn => {
    btn.addEventListener('click', () => {
      const act = btn.dataset.power;
      powerMenuDropdown.classList.add('hidden');
      if (!isConnected) {
        alert('Chưa kết nối máy trạm');
        return;
      }
      if (act === 'lock') {
        if (confirm('Khóa màn hình máy trạm (Lock Workstation)?')) {
          ws.send(JSON.stringify({ type: 'power_action', action: 'lock' }));
        }
      } else if (act === 'restart') {
        if (confirm('Khởi động lại máy trạm sẽ ngắt phiên làm việc. Bạn có chắc chắn?')) {
          ws.send(JSON.stringify({ type: 'power_action', action: 'restart' }));
        }
      }
    });
  });

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

  // --- VIEW 4: REMOTE TERMINAL (POWERSHELL) ---
  terminalInputForm.addEventListener('submit', (e) => {
    e.preventDefault();
    if (!isConnected) {
      alert('Vui lòng kết nối vào máy trạm để sử dụng Terminal');
      return;
    }
    const cmd = terminalCmdInput.value;
    if (!cmd.trim()) return;

    // Immediate local echo with prompt
    handleTerminalOutput(`PS > ${cmd}\n`);
    ws.send(JSON.stringify({
      type: 'terminal_input',
      command: cmd.trim() + '\n'
    }));
    terminalCmdInput.value = '';
  });

  btnClearTerminal.addEventListener('click', () => {
    terminalOutput.textContent = '';
  });

  function handleTerminalOutput(text) {
    terminalOutput.textContent += text;
    terminalOutput.scrollTop = terminalOutput.scrollHeight;
  }

  // --- VIEW 5: TASK MANAGER & DIAGNOSTICS ---
  btnRefreshTasks.addEventListener('click', () => {
    if (!isConnected) {
      alert('Chưa kết nối máy trạm');
      return;
    }
    requestTelemetryAndTasks();
  });

  function requestTelemetryAndTasks() {
    if (!isConnected || !ws) return;
    ws.send(JSON.stringify({ type: 'telemetry_request' }));
    ws.send(JSON.stringify({ type: 'process_list_request' }));
  }

  function handleTelemetryData(stats) {
    if (!stats) return;
    // RAM
    if (stats.ram) {
      ramValue.textContent = `${stats.ram.used_gb} / ${stats.ram.total_gb} GB`;
      ramGaugeBar.style.width = `${stats.ram.percent}%`;
      ramSub.textContent = `${stats.ram.percent}% Đang sử dụng (${stats.ram.free_gb} GB còn trống)`;
    }
    // Disk C:
    if (stats.disks && stats.disks.length > 0) {
      const diskC = stats.disks[0];
      diskCValue.textContent = `${diskC.used_gb} / ${diskC.total_gb} GB`;
      diskCGaugeBar.style.width = `${diskC.percent}%`;
      diskCSub.textContent = `${diskC.percent}% Đã dùng (${diskC.free_gb} GB trống)`;
    }
  }

  function handleProcessList(processes) {
    currentProcessList = processes;
    renderProcessTable();
  }

  processSearchInput.addEventListener('input', () => {
    renderProcessTable();
  });

  function renderProcessTable() {
    const term = processSearchInput.value.toLowerCase().trim();
    const filtered = currentProcessList.filter(p => {
      return p.name.toLowerCase().includes(term) || String(p.pid).includes(term);
    });

    if (filtered.length === 0) {
      processTableBody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-faint); padding: 20px;">Không tìm thấy tiến trình phù hợp</td></tr>`;
      return;
    }

    processTableBody.innerHTML = filtered.map(p => `
      <tr>
        <td style="color: var(--accent);">${p.pid}</td>
        <td><strong>${escapeHtml(p.name)}</strong></td>
        <td>${p.memory_mb} MB</td>
        <td>
          <button class="btn-kill-proc" data-pid="${p.pid}">Diệt (Kill)</button>
        </td>
      </tr>
    `).join('');

    processTableBody.querySelectorAll('.btn-kill-proc').forEach(btn => {
      btn.addEventListener('click', () => {
        const pid = parseInt(btn.dataset.pid, 10);
        if (confirm(`Bạn có chắc chắn muốn dừng tiến trình PID ${pid}?`)) {
          ws.send(JSON.stringify({
            type: 'process_kill_request',
            pid: pid
          }));
        }
      });
    });
  }

  // --- SIDE SHELF: FILE EXPLORER & CLIPBOARD ---
  btnOpenShelf.addEventListener('click', () => {
    shelfDrawer.classList.add('open');
    if (isConnected) requestBrowsePath(remoteCurrentPath);
  });
  btnCloseShelf.addEventListener('click', () => shelfDrawer.classList.remove('open'));

  shelfTabs.addEventListener('click', (e) => {
    const btn = e.target.closest('button');
    if (!btn) return;
    shelfTabs.querySelectorAll('button').forEach(b => b.classList.remove('on'));
    btn.classList.add('on');
    placeIndicator(shelfTabs);

    const tab = btn.dataset.shelfTab;
    shelfFilesTab.classList.toggle('hidden', tab !== 'files');
    shelfClipboardTab.classList.toggle('hidden', tab !== 'clipboard');
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
    const chunkSize = 64 * 1024;
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

  // Remote Directory Browser
  function requestBrowsePath(p) {
    if (!isConnected || !ws) return;
    ws.send(JSON.stringify({
      type: 'file_browse_request',
      path: p || ''
    }));
  }

  btnBrowseUp.addEventListener('click', () => {
    if (!remoteCurrentPath) return;
    const parts = remoteCurrentPath.replace(/\\$/, '').split('\\');
    if (parts.length <= 1) {
      remoteCurrentPath = '';
    } else {
      parts.pop();
      remoteCurrentPath = parts.join('\\') + (parts.length === 1 ? '\\' : '');
    }
    requestBrowsePath(remoteCurrentPath);
  });

  function renderFolderBrowser(data) {
    if (!data) return;
    remoteCurrentPath = data.current_path || '';
    currentFolderPath.textContent = remoteCurrentPath || 'Danh sách ổ đĩa';

    if (data.error) {
      remoteFolderList.innerHTML = `<div style="color: #EF4444; font-size: 0.75rem; padding: 10px;">${escapeHtml(data.error)}</div>`;
      return;
    }

    if (!data.items || data.items.length === 0) {
      remoteFolderList.innerHTML = `<div style="color: var(--text-faint); font-size: 0.75rem; padding: 10px;">Thư mục trống</div>`;
      return;
    }

    remoteFolderList.innerHTML = data.items.map(item => {
      const isDir = item.is_dir;
      const icon = isDir ? '📁' : '📄';
      const sizeStr = isDir ? '' : ` (${formatBytes(item.size)})`;
      return `
        <div class="folder-item" data-path="${escapeHtml(item.path || item.name)}" data-isdir="${isDir}">
          <span>${icon} ${escapeHtml(item.name)}${sizeStr}</span>
          <span>${isDir ? '→' : '⇣ Tải'}</span>
        </div>
      `;
    }).join('');

    remoteFolderList.querySelectorAll('.folder-item').forEach(el => {
      el.addEventListener('click', () => {
        const itemPath = el.dataset.path;
        const isDir = el.dataset.isdir === 'true';
        if (isDir) {
          requestBrowsePath(itemPath);
        } else {
          ws.send(JSON.stringify({
            type: 'file_download_request',
            filepath: itemPath
          }));
        }
      });
    });
  }

  function formatBytes(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
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

  function base64ToArrayBuffer(base64) {
    const binary = window.atob(base64);
    const len = binary.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
      bytes[i] = binary.charCodeAt(i);
    }
    return bytes.buffer;
  }

  // Start app
  initApp();
})();

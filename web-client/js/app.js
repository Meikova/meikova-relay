// Titan Remote Desktop - Web Client Application
(function () {
  'use strict';

  // DOM Elements
  const connectModal = document.getElementById('connectModal');
  const connectForm = document.getElementById('connectForm');
  const relayUrlInput = document.getElementById('relayUrl');
  const roomIdInput = document.getElementById('roomId');
  const roomPinInput = document.getElementById('roomPin');
  const statusMessage = document.getElementById('statusMessage');
  const btnConnect = document.getElementById('btnConnect');

  const remoteViewport = document.getElementById('remoteViewport');
  const canvasContainer = document.getElementById('canvasContainer');
  const remoteCanvas = document.getElementById('remoteCanvas');
  const ctx = remoteCanvas.getContext('2d');

  const remoteDeviceName = document.getElementById('remoteDeviceName');
  const metricPing = document.getElementById('metricPing');
  const metricFps = document.getElementById('metricFps');
  const metricRes = document.getElementById('metricRes');

  const btnScaleToggle = document.getElementById('btnScaleToggle');
  const scaleLabel = document.getElementById('scaleLabel');
  const btnFullscreen = document.getElementById('btnFullscreen');
  const btnDisconnect = document.getElementById('btnDisconnect');

  const pasteModal = document.getElementById('pasteModal');
  const pasteTextInput = document.getElementById('pasteTextInput');
  const btnCancelPaste = document.getElementById('btnCancelPaste');
  const btnConfirmPaste = document.getElementById('btnConfirmPaste');

  // State
  let ws = null;
  let isConnected = false;
  let hostResolution = { width: 1920, height: 1080 };
  let isFitMode = true;

  // Metrics
  let frameCount = 0;
  let lastFpsUpdate = performance.now();
  let lastPingSend = 0;
  let pingIntervalId = null;

  // Default Relay URL to current host if served via http
  if (window.location.protocol.startsWith('http')) {
    const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    relayUrlInput.value = `${wsProto}//${window.location.host}`;
  } else {
    relayUrlInput.value = 'ws://localhost:8080';
  }

  // JS Key Code to Win32 Virtual-Key Map
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
    F7: 0x76, F8: 0x77, F9: 0x78, F10: 0x79, F11: 0x7A, F12: 0x7B,
    Semicolon: 0xBA, Equal: 0xBB, Comma: 0xBC, Minus: 0xBD, Period: 0xBE,
    Slash: 0xBF, Backquote: 0xC0, BracketLeft: 0xDB, Backslash: 0xDC,
    BracketRight: 0xDD, Quote: 0xDE
  };

  function showStatus(text, isError = false) {
    statusMessage.textContent = text;
    statusMessage.className = `status-box ${isError ? 'error' : 'info'}`;
    statusMessage.classList.remove('hidden');
  }

  function hideStatus() {
    statusMessage.classList.add('hidden');
  }

  // Connect Handler
  connectForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const relayUrl = relayUrlInput.value.trim();
    const roomId = roomIdInput.value.trim();
    const pin = roomPinInput.value.trim();

    if (!relayUrl || !roomId || !pin) {
      showStatus('Vui lòng điền đầy đủ thông tin kết nối', true);
      return;
    }

    startConnection(relayUrl, roomId, pin);
  });

  function startConnection(relayUrl, roomId, pin) {
    showStatus('Đang kết nối tới Relay Server...');
    btnConnect.disabled = true;

    try {
      ws = new WebSocket(relayUrl);
      ws.binaryType = 'blob';
    } catch (err) {
      showStatus(`Không thể mở WebSocket: ${err.message}`, true);
      btnConnect.disabled = false;
      return;
    }

    ws.onopen = () => {
      showStatus('Đã kết nối Relay! Đang xác thực phòng...');
      ws.send(JSON.stringify({
        type: 'init_client',
        room_id: roomId,
        pin: pin
      }));
    };

    ws.onmessage = async (event) => {
      // 1. Binary message = Screen frame from Host
      if (event.data instanceof Blob) {
        handleIncomingFrame(event.data);
        return;
      }

      // 2. Text / JSON message
      try {
        const msg = JSON.parse(event.data);
        if (msg.status === 'ok' && msg.role === 'client') {
          handleConnectSuccess(msg);
        } else if (msg.status === 'error') {
          showStatus(`Lỗi: ${msg.message}`, true);
          disconnect();
        } else if (msg.type === 'host_ready') {
          if (msg.width && msg.height) {
            updateHostResolution(msg.width, msg.height);
          }
          if (msg.deviceName) {
            remoteDeviceName.textContent = msg.deviceName;
          }
        } else if (msg.type === 'host_disconnected') {
          alert('Host đã ngắt kết nối hoặc offline!');
          disconnect();
        } else if (msg.type === 'pong') {
          const rtt = Math.round(performance.now() - lastPingSend);
          metricPing.textContent = rtt;
        }
      } catch (err) {
        console.error('Parse error:', err);
      }
    };

    ws.onerror = (err) => {
      console.error('WS Error:', err);
      showStatus('Lỗi kết nối WebSocket tới Relay Server', true);
    };

    ws.onclose = () => {
      if (isConnected) {
        alert('Mất kết nối với Relay Server');
      }
      disconnect();
    };
  }

  function handleConnectSuccess(msg) {
    isConnected = true;
    btnConnect.disabled = false;
    hideStatus();

    connectModal.classList.add('hidden');
    remoteViewport.classList.remove('hidden');

    if (msg.hostMeta) {
      updateHostResolution(msg.hostMeta.width, msg.hostMeta.height);
      remoteDeviceName.textContent = msg.hostMeta.deviceName || 'Host-PC';
    }

    applyScaleMode();

    // Start FPS counter and Ping loop
    lastFpsUpdate = performance.now();
    frameCount = 0;
    pingIntervalId = setInterval(measurePing, 3000);
    remoteCanvas.focus();
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
    } catch (err) {
      console.warn('Frame render error:', err);
    }
  }

  function measurePing() {
    if (ws && ws.readyState === WebSocket.OPEN) {
      lastPingSend = performance.now();
      ws.send(JSON.stringify({ type: 'ping', ts: Date.now() }));
    }
  }

  function disconnect() {
    isConnected = false;
    if (pingIntervalId) clearInterval(pingIntervalId);

    if (ws) {
      ws.close();
      ws = null;
    }

    connectModal.classList.remove('hidden');
    remoteViewport.classList.add('hidden');
    btnConnect.disabled = false;
  }

  btnDisconnect.addEventListener('click', disconnect);

  // Scaling mode toggle
  btnScaleToggle.addEventListener('click', () => {
    isFitMode = !isFitMode;
    applyScaleMode();
  });

  function applyScaleMode() {
    if (isFitMode) {
      canvasContainer.classList.add('fit-mode');
      scaleLabel.textContent = 'Fit Screen';
    } else {
      canvasContainer.classList.remove('fit-mode');
      scaleLabel.textContent = '100% Scale';
    }
  }

  // Fullscreen toggle
  btnFullscreen.addEventListener('click', () => {
    if (!document.fullscreenElement) {
      remoteViewport.requestFullscreen().catch((err) => console.warn(err));
    } else {
      document.exitFullscreen().catch((err) => console.warn(err));
    }
  });

  // Mouse Input Handling
  function getCanvasNormalizedCoords(e) {
    const rect = remoteCanvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;
    return {
      x: Math.max(0.0, Math.min(1.0, x)),
      y: Math.max(0.0, Math.min(1.0, y))
    };
  }

  let lastMoveSent = 0;
  remoteCanvas.addEventListener('mousemove', (e) => {
    if (!isConnected) return;
    const now = performance.now();
    // Throttle mouse moves to ~40fps (25ms) to prevent network congestion
    if (now - lastMoveSent < 25) return;
    lastMoveSent = now;

    const coords = getCanvasNormalizedCoords(e);
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
      button: e.button // 0: Left, 1: Middle, 2: Right
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

  remoteCanvas.addEventListener('contextmenu', (e) => {
    e.preventDefault(); // Prevent browser context menu
  });

  remoteCanvas.addEventListener('wheel', (e) => {
    if (!isConnected) return;
    e.preventDefault();
    ws.send(JSON.stringify({
      type: 'mouse_wheel',
      delta_y: -e.deltaY
    }));
  }, { passive: false });

  // Keyboard Input Handling
  window.addEventListener('keydown', (e) => {
    if (!isConnected || !connectModal.classList.contains('hidden') || !pasteModal.classList.contains('hidden')) {
      return;
    }

    // Intercept keys when remote viewport is active
    const vk = JS_TO_VK[e.code] || 0;
    if (vk > 0) {
      // Prevent browser default actions for keys like Tab, Alt, Backspace, F-keys
      if (['Tab', 'AltLeft', 'AltRight', 'Backspace', 'F5', 'F11', 'F12'].includes(e.code)) {
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
    if (!isConnected || !connectModal.classList.contains('hidden') || !pasteModal.classList.contains('hidden')) {
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

  // Bottom Pill Deck Shortcuts
  document.querySelectorAll('.pill-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      if (!isConnected) return;
      const action = btn.dataset.keyAction;

      if (action === 'win') {
        // Tap Windows Key (0x5B)
        sendKeySequence([0x5B]);
      } else if (action === 'taskmgr') {
        // Ctrl + Shift + Esc (0x11, 0x10, 0x1B)
        sendHotKeyCombo([0x11, 0x10, 0x1B]);
      } else if (action === 'alttab') {
        // Alt + Tab (0x12, 0x09)
        sendHotKeyCombo([0x12, 0x09]);
      } else if (action === 'esc') {
        sendKeySequence([0x1B]);
      } else if (action === 'paste') {
        pasteModal.classList.remove('hidden');
        pasteTextInput.value = '';
        pasteTextInput.focus();
      }
    });
  });

  function sendKeySequence(vkList) {
    vkList.forEach((vk) => {
      ws.send(JSON.stringify({ type: 'key_down', vk: vk }));
      setTimeout(() => {
        ws.send(JSON.stringify({ type: 'key_up', vk: vk }));
      }, 50);
    });
  }

  function sendHotKeyCombo(vkList) {
    // Press all down in order
    vkList.forEach((vk) => {
      ws.send(JSON.stringify({ type: 'key_down', vk: vk }));
    });
    // Release in reverse order
    setTimeout(() => {
      [...vkList].reverse().forEach((vk) => {
        ws.send(JSON.stringify({ type: 'key_up', vk: vk }));
      });
    }, 100);
  }

  // Paste Text Modal
  btnCancelPaste.addEventListener('click', () => {
    pasteModal.classList.add('hidden');
    remoteCanvas.focus();
  });

  btnConfirmPaste.addEventListener('click', () => {
    const text = pasteTextInput.value;
    if (text && isConnected) {
      ws.send(JSON.stringify({
        type: 'text_input',
        text: text
      }));
    }
    pasteModal.classList.add('hidden');
    remoteCanvas.focus();
  });
})();

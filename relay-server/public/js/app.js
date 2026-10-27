// Meikova Relay Enterprise — Ambient Instrument Web Application
(function () {
  'use strict';
  // PWA Cache Storage Purge on Version Bump
  try {
    const PWA_VER = '1.0.70';
    const lastPwaVer = localStorage.getItem('meikova_pwa_ver');
    if (lastPwaVer && lastPwaVer !== PWA_VER && 'caches' in window) {
      localStorage.setItem('meikova_pwa_ver', PWA_VER);
      caches.keys().then(names => Promise.all(names.map(n => caches.delete(n))));
    } else if (!lastPwaVer) {
      localStorage.setItem('meikova_pwa_ver', PWA_VER);
    }
  } catch (_) {}


  // Synchronize true viewport height for iOS Safari & PWA standalone (WebKit Bug 244501 override)
  function syncTrueViewportHeight() {
    const vh = window.innerHeight;
    document.documentElement.style.setProperty('--vh', `${vh}px`);
  }
  syncTrueViewportHeight();
  window.addEventListener('DOMContentLoaded', syncTrueViewportHeight);
  window.addEventListener('load', syncTrueViewportHeight);
  window.addEventListener('orientationchange', () => setTimeout(syncTrueViewportHeight, 200));

  // --- DOM Navigation & Views ---
  const mainNav = document.getElementById('mainNav');
  const authSection = document.getElementById('authSection');
  const dashboardSection = document.getElementById('dashboardSection');
  const remoteSection = document.getElementById('remoteSection');
  const terminalSection = document.getElementById('terminalSection');
  const tasksSection = document.getElementById('tasksSection');
  const shelfDrawer = document.getElementById('shelfDrawer');
  const filesSection = document.getElementById('filesSection');
  const explorerDrivesRow = document.getElementById('explorerDrivesRow');
  const explorerBreadcrumbs = document.getElementById('explorerBreadcrumbs');
  const explorerPathInputWrap = document.getElementById('explorerPathInputWrap');
  const explorerDirectPathInput = document.getElementById('explorerDirectPathInput');
  const btnTogglePathInput = document.getElementById('btnTogglePathInput');
  const btnGoDirectPath = document.getElementById('btnGoDirectPath');
  const btnCancelDirectPath = document.getElementById('btnCancelDirectPath');
  const btnExpUp = document.getElementById('btnExpUp');
  const btnExpRefresh = document.getElementById('btnExpRefresh');
  const btnExpNewFolder = document.getElementById('btnExpNewFolder');
  const btnExpUpload = document.getElementById('btnExpUpload');
  const btnExpPaste = document.getElementById('btnExpPaste');
  const expPasteLabel = document.getElementById('expPasteLabel');
  let explorerClipboard = null; // { action: 'copy' | 'cut', path: string, name: string }

  function updatePasteButtonState() {
    if (!btnExpPaste) return;
    if (explorerClipboard && explorerClipboard.path) {
      btnExpPaste.classList.remove('hidden');
      if (expPasteLabel) {
        const actionText = explorerClipboard.action === 'copy' ? (t('files.btn_paste') || 'Dán') : 'Chuyển';
        expPasteLabel.textContent = `${actionText} (${explorerClipboard.name})`;
      }
      btnExpPaste.title = explorerClipboard.action === 'copy'
        ? `Dán tệp đã chép: ${explorerClipboard.name}`
        : `Di chuyển tệp đã cắt: ${explorerClipboard.name}`;
    } else {
      btnExpPaste.classList.add('hidden');
      if (expPasteLabel) expPasteLabel.textContent = t('files.btn_paste') || 'Dán';
      btnExpPaste.title = t('files.btn_paste_title') || 'Dán tệp/thư mục vào đây';
    }
  }

  function executePasteAction() {
    if (!remoteCurrentPath) {
      showToast(t('toast.select_dest_folder'), 'info');
      return;
    }
    if (!explorerClipboard || !explorerClipboard.path) {
      showToast(t('toast.clip_empty_action'), 'info');
      return;
    }
    if (explorerClipboard.action === 'copy') {
      ws.send(JSON.stringify({
        type: 'file_copy_request',
        src_path: explorerClipboard.path,
        dst_dir: remoteCurrentPath
      }));
      showToast(t('toast.copying_item', { name: explorerClipboard.name }), 'info');
    } else if (explorerClipboard.action === 'cut') {
      ws.send(JSON.stringify({
        type: 'file_move_request',
        src_path: explorerClipboard.path,
        dst_dir: remoteCurrentPath
      }));
      showToast(t('toast.moving_item', { name: explorerClipboard.name }), 'info');
    }
  }

  if (btnExpPaste) {
    btnExpPaste.addEventListener('click', executePasteAction);
  }

  const expFileInput = document.getElementById('expFileInput');
  const explorerSearchInput = document.getElementById('explorerSearchInput');
  const btnModeList = document.getElementById('btnModeList');
  const btnModeGrid = document.getElementById('btnModeGrid');
  const expTransferProgress = document.getElementById('expTransferProgress');
  const expTransferLabel = document.getElementById('expTransferLabel');
  const expTransferPercent = document.getElementById('expTransferPercent');
  const expTransferFill = document.getElementById('expTransferFill');
  const explorerDropTarget = document.getElementById('explorerDropTarget');
  const explorerListContainer = document.getElementById('explorerListContainer');
  const explorerTableBody = document.getElementById('explorerTableBody');
  const explorerGridContainer = document.getElementById('explorerGridContainer');
  const expStatusCount = document.getElementById('expStatusCount');
  const expStatusSize = document.getElementById('expStatusSize');
  const btnExpandExplorer = document.getElementById('btnExpandExplorer');

  let currentExplorerItems = [];
  let currentExplorerDrives = [];
  let explorerViewMode = 'list';
  let remoteParentPath = '';

  // --- Online File Editor DOM ---
  const fileEditorModal = document.getElementById('fileEditorModal');
  const editorFileName = document.getElementById('editorFileName');
  const editorFilePath = document.getElementById('editorFilePath');
  const editorDirtyBadge = document.getElementById('editorDirtyBadge');
  const editorEncodingBadge = document.getElementById('editorEncodingBadge');
  const editorWrapCheckbox = document.getElementById('editorWrapCheckbox');
  const btnSaveFile = document.getElementById('btnSaveFile');
  const btnCloseFileEditor = document.getElementById('btnCloseFileEditor');
  const fileEditorTextarea = document.getElementById('fileEditorTextarea');
  const editorCursorPos = document.getElementById('editorCursorPos');
  const editorStats = document.getElementById('editorStats');
  const editorSaveTime = document.getElementById('editorSaveTime');

  let currentEditingFilePath = '';
  let currentEditorOriginalContent = '';

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
  const monitorGrid = document.getElementById('monitorGrid');
  const btnToggleGrid = document.getElementById('btnToggleGrid');
  const gridControls = document.getElementById('gridControls');
  const btnGridSideBySide = document.getElementById('btnGridSideBySide');
  const btnGridInvert = document.getElementById('btnGridInvert');
  const btnGridStacked = document.getElementById('btnGridStacked');

  let isGridMode = false;
  let gridLayoutMode = 'side-by-side'; // 'side-by-side' | 'stacked'
  let hostMonitors = [];
  let gridMonitorOrder = [];
  let monitorTileMap = new Map(); // id -> { tile, canvas, ctx, mon }

  // --- Mobile Controls & Virtual Keyboard DOM ---
  const mobileVirtualInput = document.getElementById('mobileVirtualInput');
  const mobileQuickKeysBar = document.getElementById('mobileQuickKeysBar');
  const btnCloseQuickKeys = document.getElementById('btnCloseQuickKeys');
  const btnMobileImmersiveExit = document.getElementById('btnMobileImmersiveExit');
  const btnMobileKeyboard = document.getElementById('btnMobileKeyboard');
  const btnMobileQuickKeysToggle = document.getElementById('btnMobileQuickKeysToggle');
  const btnMobileTouchMode = document.getElementById('btnMobileTouchMode');
  const touchModeLabel = document.getElementById('touchModeLabel');
  const btnMobileRightClick = document.getElementById('btnMobileRightClick');
  const keyboardMenuDropdown = document.getElementById('keyboardMenuDropdown');
  const btnOptPhoneKeyboard = document.getElementById('btnOptPhoneKeyboard');
  const btnOptVirtualOSK = document.getElementById('btnOptVirtualOSK');
  const checkPhoneKeyboard = document.getElementById('checkPhoneKeyboard');
  const checkVirtualOSK = document.getElementById('checkVirtualOSK');
  const keyboardCurrentLabel = document.getElementById('keyboardCurrentLabel');
  const btnCloseOSK = document.getElementById('btnCloseOSK');

  const roStatus = document.getElementById('roStatus');
  const roTr = document.getElementById('ro-tr');
  const metricPing = document.getElementById('metricPing');
  const metricFps = document.getElementById('metricFps');
  const metricRes = document.getElementById('metricRes');
  const sparklineCanvas = document.getElementById('sparklineCanvas');
  const sparkCtx = sparklineCanvas ? sparklineCanvas.getContext('2d') : null;
  const pingSamples = [];
  const toastContainer = document.getElementById('toastContainer');

  function resetSessionMetrics() {
    if (metricPing) metricPing.textContent = '--';
    if (metricFps) metricFps.textContent = '--';
    if (metricRes) metricRes.textContent = '--';
    pingSamples.length = 0;
    if (sparkCtx && sparklineCanvas) {
      sparkCtx.clearRect(0, 0, sparklineCanvas.width, sparklineCanvas.height);
    }
  }

  function showToast(message, type = 'info', duration = 3500) {
    if (!toastContainer) return;
    const isToastEnabled = localStorage.getItem('meikova_toast_enabled') !== 'false';
    if (!isToastEnabled && type !== 'error') {
      return;
    }
    const resolvedMsg = (window.MeikovaI18n && typeof window.MeikovaI18n.t === 'function')
      ? window.MeikovaI18n.t(message)
      : message;
    const toast = document.createElement('div');
    toast.className = `toast toast--${type}`;
    
    let iconSvg = '';
    if (type === 'success') {
      iconSvg = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>';
    } else if (type === 'error') {
      iconSvg = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>';
    } else {
      iconSvg = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>';
    }

    toast.innerHTML = `${iconSvg}<span>${escapeHtml(resolvedMsg)}</span>`;
    toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(12px) scale(0.96)';
      setTimeout(() => toast.remove(), 250);
    }, duration);
  }

  function showConfirmModal({
    title = '',
    message = '',
    confirmText = '',
    cancelText = '',
    danger = false
  } = {}) {
    return new Promise((resolve) => {
      const modal = document.getElementById('modalConfirmDialog');
      const titleEl = document.getElementById('confirmDialogTitle');
      const msgEl = document.getElementById('confirmDialogMessage');
      const btnConfirm = document.getElementById('confirmDialogBtnConfirm');
      const btnCancel = document.getElementById('confirmDialogBtnCancel');
      const iconWrap = document.getElementById('confirmDialogIconWrap');
      const iconCheck = document.getElementById('confirmDialogIconCheck');
      const iconAlert = document.getElementById('confirmDialogIconAlert');
      const inputWrap = document.getElementById('confirmDialogInputWrap');
      if (inputWrap) inputWrap.classList.add('hidden');

      if (!modal) {
        resolve(true);
        return;
      }

      if (titleEl) titleEl.textContent = title || t('dialog.confirm_title') || 'Xác nhận';
      if (msgEl) msgEl.textContent = message;
      if (btnConfirm) {
        btnConfirm.textContent = confirmText || t('dialog.btn_confirm') || 'Đồng ý';
        if (danger) {
          btnConfirm.style.background = '#EF4444';
          btnConfirm.style.borderColor = '#EF4444';
          btnConfirm.style.boxShadow = '0 0 16px rgba(239, 68, 68, 0.4)';
        } else {
          btnConfirm.style.background = '';
          btnConfirm.style.borderColor = '';
          btnConfirm.style.boxShadow = '';
        }
      }
      if (btnCancel) {
        btnCancel.textContent = cancelText || t('dialog.btn_cancel') || 'Hủy';
        btnCancel.classList.remove('hidden');
      }

      if (danger) {
        if (iconWrap) {
          iconWrap.style.background = 'rgba(239, 68, 68, 0.12)';
          iconWrap.style.color = '#EF4444';
        }
        if (iconCheck) iconCheck.classList.add('hidden');
        if (iconAlert) iconAlert.classList.remove('hidden');
      } else {
        if (iconWrap) {
          iconWrap.style.background = 'rgba(34, 197, 94, 0.12)';
          iconWrap.style.color = '#22C55E';
        }
        if (iconCheck) iconCheck.classList.remove('hidden');
        if (iconAlert) iconAlert.classList.add('hidden');
      }

      modal.classList.remove('hidden');

      function cleanup(res) {
        modal.classList.add('hidden');
        btnConfirm?.removeEventListener('click', onConfirm);
        btnCancel?.removeEventListener('click', onCancel);
        window.removeEventListener('keydown', onKeyDown);
        modal.removeEventListener('click', onBackdrop);
        resolve(res);
      }

      function onConfirm(e) {
        e.stopPropagation();
        cleanup(true);
      }

      function onCancel(e) {
        e.stopPropagation();
        cleanup(false);
      }

      function onKeyDown(e) {
        if (e.key === 'Escape') {
          e.stopPropagation();
          cleanup(false);
        } else if (e.key === 'Enter') {
          e.stopPropagation();
          cleanup(true);
        }
      }

      function onBackdrop(e) {
        if (e.target === modal) {
          cleanup(false);
        }
      }

      btnConfirm?.addEventListener('click', onConfirm);
      btnCancel?.addEventListener('click', onCancel);
      window.addEventListener('keydown', onKeyDown);
      modal.addEventListener('click', onBackdrop);
      btnConfirm?.focus();
    });
  }

  function showAlertModal({
    title = '',
    message = '',
    okText = ''
  } = {}) {
    return new Promise((resolve) => {
      const modal = document.getElementById('modalConfirmDialog');
      const titleEl = document.getElementById('confirmDialogTitle');
      const msgEl = document.getElementById('confirmDialogMessage');
      const btnConfirm = document.getElementById('confirmDialogBtnConfirm');
      const btnCancel = document.getElementById('confirmDialogBtnCancel');
      const iconWrap = document.getElementById('confirmDialogIconWrap');
      const iconCheck = document.getElementById('confirmDialogIconCheck');
      const iconAlert = document.getElementById('confirmDialogIconAlert');
      const inputWrap = document.getElementById('confirmDialogInputWrap');
      if (inputWrap) inputWrap.classList.add('hidden');

      if (!modal) {
        resolve();
        return;
      }

      if (titleEl) titleEl.textContent = title || t('dialog.alert_title') || 'Thông báo';
      if (msgEl) msgEl.textContent = message;
      if (btnConfirm) {
        btnConfirm.textContent = okText || t('dialog.btn_ok') || 'Đã hiểu';
        btnConfirm.style.background = '';
        btnConfirm.style.borderColor = '';
        btnConfirm.style.boxShadow = '';
      }
      if (btnCancel) {
        btnCancel.classList.add('hidden');
      }

      if (iconWrap) {
        iconWrap.style.background = 'rgba(56, 189, 248, 0.12)';
        iconWrap.style.color = '#38BDF8';
      }
      if (iconCheck) iconCheck.classList.remove('hidden');
      if (iconAlert) iconAlert.classList.add('hidden');

      modal.classList.remove('hidden');

      function cleanup() {
        modal.classList.add('hidden');
        btnConfirm?.removeEventListener('click', onConfirm);
        window.removeEventListener('keydown', onKeyDown);
        modal.removeEventListener('click', onBackdrop);
        resolve();
      }

      function onConfirm(e) {
        e.stopPropagation();
        cleanup();
      }

      function onKeyDown(e) {
        if (e.key === 'Escape' || e.key === 'Enter') {
          e.stopPropagation();
          cleanup();
        }
      }

      function onBackdrop(e) {
        if (e.target === modal) {
          cleanup();
        }
      }

      btnConfirm?.addEventListener('click', onConfirm);
      window.addEventListener('keydown', onKeyDown);
      modal.addEventListener('click', onBackdrop);
      btnConfirm?.focus();
    });
  }

  function showPromptModal({
    title = '',
    message = '',
    defaultValue = '',
    placeholder = '',
    confirmText = '',
    cancelText = ''
  } = {}) {
    return new Promise((resolve) => {
      const modal = document.getElementById('modalConfirmDialog');
      const titleEl = document.getElementById('confirmDialogTitle');
      const msgEl = document.getElementById('confirmDialogMessage');
      const btnConfirm = document.getElementById('confirmDialogBtnConfirm');
      const btnCancel = document.getElementById('confirmDialogBtnCancel');
      const iconWrap = document.getElementById('confirmDialogIconWrap');
      const iconCheck = document.getElementById('confirmDialogIconCheck');
      const iconAlert = document.getElementById('confirmDialogIconAlert');
      const inputWrap = document.getElementById('confirmDialogInputWrap');
      const inputEl = document.getElementById('confirmDialogInput');

      if (!modal) {
        resolve(null);
        return;
      }

      if (titleEl) titleEl.textContent = title || t('dialog.confirm_title') || 'Nhập thông tin';
      if (msgEl) msgEl.textContent = message;
      if (inputWrap) inputWrap.classList.remove('hidden');
      if (inputEl) {
        inputEl.value = defaultValue || '';
        inputEl.placeholder = placeholder || '';
      }

      if (btnConfirm) {
        btnConfirm.textContent = confirmText || t('dialog.btn_confirm') || 'Đồng ý';
        btnConfirm.style.background = '';
        btnConfirm.style.borderColor = '';
        btnConfirm.style.boxShadow = '';
      }
      if (btnCancel) {
        btnCancel.textContent = cancelText || t('dialog.btn_cancel') || 'Hủy';
        btnCancel.classList.remove('hidden');
      }

      if (iconWrap) {
        iconWrap.style.background = 'rgba(56, 189, 248, 0.12)';
        iconWrap.style.color = '#38BDF8';
      }
      if (iconCheck) iconCheck.classList.remove('hidden');
      if (iconAlert) iconAlert.classList.add('hidden');

      modal.classList.remove('hidden');

      function cleanup(res) {
        modal.classList.add('hidden');
        if (inputWrap) inputWrap.classList.add('hidden');
        btnConfirm?.removeEventListener('click', onConfirm);
        btnCancel?.removeEventListener('click', onCancel);
        window.removeEventListener('keydown', onKeyDown);
        modal.removeEventListener('click', onBackdrop);
        resolve(res);
      }

      function onConfirm(e) {
        e.stopPropagation();
        cleanup(inputEl ? inputEl.value.trim() : '');
      }

      function onCancel(e) {
        e.stopPropagation();
        cleanup(null);
      }

      function onKeyDown(e) {
        if (e.key === 'Escape') {
          e.stopPropagation();
          cleanup(null);
        } else if (e.key === 'Enter') {
          e.stopPropagation();
          cleanup(inputEl ? inputEl.value.trim() : '');
        }
      }

      function onBackdrop(e) {
        if (e.target === modal) {
          cleanup(null);
        }
      }

      btnConfirm?.addEventListener('click', onConfirm);
      btnCancel?.addEventListener('click', onCancel);
      window.addEventListener('keydown', onKeyDown);
      modal.addEventListener('click', onBackdrop);
      setTimeout(() => {
        inputEl?.focus();
        inputEl?.select();
      }, 50);
    });
  }

  function recordPingSample(rtt) {
    pingSamples.push(rtt);
    if (pingSamples.length > 16) pingSamples.shift();
    drawSparkline();
  }

  function drawSparkline() {
    if (!sparkCtx || pingSamples.length < 2) return;
    const w = sparklineCanvas.width;
    const h = sparklineCanvas.height;
    sparkCtx.clearRect(0, 0, w, h);

    const maxVal = Math.max(100, ...pingSamples);
    const minVal = Math.max(0, Math.min(...pingSamples));
    const range = Math.max(20, maxVal - minVal);

    sparkCtx.strokeStyle = 'rgba(34, 197, 94, 0.9)';
    sparkCtx.lineWidth = 1.5;
    sparkCtx.lineJoin = 'round';
    sparkCtx.beginPath();

    pingSamples.forEach((val, i) => {
      const x = (i / (pingSamples.length - 1)) * w;
      const y = h - ((val - minVal) / range) * (h - 2) - 1;
      if (i === 0) sparkCtx.moveTo(x, y);
      else sparkCtx.lineTo(x, y);
    });

    sparkCtx.stroke();
  }

  // --- Floating Deck Controls DOM ---
  const floatingDeck = document.getElementById('floatingDeck');
  const monitorSelector = document.getElementById('monitorSelector');
  const btnMonitorMenu = document.getElementById('btnMonitorMenu');
  const monitorCurrentLabel = document.getElementById('monitorCurrentLabel');
  const monitorMenuDropdown = document.getElementById('monitorMenuDropdown');
  const monitorMenuList = document.getElementById('monitorMenuList');
  const qualitySelector = document.getElementById('qualitySelector');
  let hasUserManuallySelectedQuality = false;
  const btnQualityMenu = document.getElementById('btnQualityMenu');
  const btnProtocolMenu = document.getElementById('btnProtocolMenu');
  const protocolCurrentLabel = document.getElementById('protocolCurrentLabel');
  const protocolMenuDropdown = document.getElementById('protocolMenuDropdown');
  const btnRefreshProtocols = document.getElementById('btnRefreshProtocols');
  const protoBadgeRdp = document.getElementById('protoBadgeRdp');
  const protoDescRdp = document.getElementById('protoDescRdp');
  const btnDownloadRdp = document.getElementById('btnDownloadRdp');
  const protoBadgeSsh = document.getElementById('protoBadgeSsh');
  const protoDescSsh = document.getElementById('protoDescSsh');
  const btnCopySshCmd = document.getElementById('btnCopySshCmd');
  const protoBadgeFile = document.getElementById('protoBadgeFile');
  const protoDescFile = document.getElementById('protoDescFile');
  const protoModeAuto = document.getElementById('protoModeAuto');
  const protoModeBypass = document.getElementById('protoModeBypass');
  const protoModeNative = document.getElementById('protoModeNative');
  let currentProtocolMatrix = null;
  let protocolRoutingMode = 'auto'; // 'auto' | 'bypass' | 'native'
  const qualityCurrentLabel = document.getElementById('qualityCurrentLabel');
  const qualityMenuDropdown = document.getElementById('qualityMenuDropdown');
  const btnResolutionMenu = document.getElementById('btnResolutionMenu');
  const resolutionCurrentLabel = document.getElementById('resolutionCurrentLabel');
  const resolutionMenuDropdown = document.getElementById('resolutionMenuDropdown');
  const vdDisplayBadge = document.getElementById('vdDisplayBadge');
  const btnInstallVDisplay = document.getElementById('btnInstallVDisplay');
  const vdAudioBadge = document.getElementById('vdAudioBadge');
  const btnInstallVAudio = document.getElementById('btnInstallVAudio');
  const btnSyncDisplay = document.getElementById('btnSyncDisplay');
  const btnScaleToggle = document.getElementById('btnScaleToggle');
  const pixelIndicatorBadge = document.getElementById('pixelIndicatorBadge');
  const pixelIndicatorText = document.getElementById('pixelIndicatorText');
  const btnFullscreen = document.getElementById('btnFullscreen');
  const btnDeckDisplayMode = document.getElementById('btnDeckDisplayMode');
  const deckIconBottom = document.getElementById('deckIconBottom');
  const deckIconTopPinned = document.getElementById('deckIconTopPinned');
  const deckIconTopUnpinned = document.getElementById('deckIconTopUnpinned');
  const btnDeckPinQuick = document.getElementById('btnDeckPinQuick');
  const deckSvgPinActive = document.getElementById('deckSvgPinActive');
  const deckSvgPinInactive = document.getElementById('deckSvgPinInactive');
  const deckTopTrigger = document.getElementById('deckTopTrigger');
  const deckModeDropdown = document.getElementById('deckModeDropdown');
  const checkModeBottom = document.getElementById('checkModeBottom');
  const checkModeTopPinned = document.getElementById('checkModeTopPinned');
  const checkModeTopUnpinned = document.getElementById('checkModeTopUnpinned');
  const btnToggleLaser = document.getElementById('btnToggleLaser');
  const btnRecord = document.getElementById('btnRecord');
  const btnToggleCam = document.getElementById('btnToggleCam');
  const camSvgOff = document.getElementById('camSvgOff');
  const camSvgOn = document.getElementById('camSvgOn');
  const webcamContainer = document.getElementById('webcamContainer');
  const webcamVideo = document.getElementById('webcamVideo');
  const btnScreenshot = document.getElementById('btnScreenshot');
  const btnToggleAudio = document.getElementById('btnToggleAudio');
  const audioSvgMuted = document.getElementById('audioSvgMuted');
  const audioSvgPlaying = document.getElementById('audioSvgPlaying');
  const btnToggleMic = document.getElementById('btnToggleMic');
  const micSvgMuted = document.getElementById('micSvgMuted');
  const micSvgActive = document.getElementById('micSvgActive');
  const btnToggleOSK = document.getElementById('btnToggleOSK');
  const oskOverlay = document.getElementById('oskOverlay');
  const btnPowerMenu = document.getElementById('btnPowerMenu');
  const powerMenuDropdown = document.getElementById('powerMenuDropdown');
  const btnOpenShelf = document.getElementById('btnOpenShelf');
  const btnCloseShelf = document.getElementById('btnCloseShelf');
  const btnDisconnect = document.getElementById('btnDisconnect');

  // --- Terminal View DOM ---
  const terminalScreen = document.getElementById('terminalScreen');
  const terminalOutput = document.getElementById('terminalOutput');
  const terminalCmdInput = document.getElementById('terminalCmdInput');
  const terminalInputEcho = document.getElementById('terminalInputEcho');
  const terminalStatusBadge = document.getElementById('terminalStatusBadge');
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
  
  // --- Audit View DOM ---
  const auditSection = document.getElementById('auditSection');
  const auditTableBody = document.getElementById('auditTableBody');
  const auditSearchInput = document.getElementById('auditSearchInput');
  const auditActionFilter = document.getElementById('auditActionFilter');
  const btnRefreshAudit = document.getElementById('btnRefreshAudit');
  const btnExportAuditCsv = document.getElementById('btnExportAuditCsv');
  const btnAuditPrev = document.getElementById('btnAuditPrev');
  const btnAuditNext = document.getElementById('btnAuditNext');
  const auditPageSummary = document.getElementById('auditPageSummary');
  const auditPageIndicator = document.getElementById('auditPageIndicator');

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
  const btnTypeDirect = document.getElementById('btnTypeDirect');
  const btnToggleBlockInput = document.getElementById('btnToggleBlockInput');

  // --- Advanced Utilities DOM ---
  const btnToggleCurtain = document.getElementById('btnToggleCurtain');
  const curtainSvgOff = document.getElementById('curtainSvgOff');
  const curtainSvgOn = document.getElementById('curtainSvgOn');
  const btnToggleWhiteboard = document.getElementById('btnToggleWhiteboard');
  const whiteboardCanvas = document.getElementById('whiteboardCanvas');
  const wbCtx = whiteboardCanvas ? whiteboardCanvas.getContext('2d') : null;
  const whiteboardToolbar = document.getElementById('whiteboardToolbar');
  const btnWbLaserFade = document.getElementById('btnWbLaserFade');
  const btnWbClearAll = document.getElementById('btnWbClearAll');
  const btnSnippetsMenu = document.getElementById('btnSnippetsMenu');
  const snippetsMenuDropdown = document.getElementById('snippetsMenuDropdown');
  const btnShortcutsMenu = document.getElementById('btnShortcutsMenu');
  const shortcutsMenuDropdown = document.getElementById('shortcutsMenuDropdown');
  const btnMoreToolsMenu = document.getElementById('btnMoreToolsMenu');
  const moreToolsMenuDropdown = document.getElementById('moreToolsMenuDropdown');
  const toolsActiveIndicator = document.getElementById('toolsActiveIndicator');
  const btnDropdownWhiteboard = document.getElementById('btnDropdownWhiteboard');
  const btnDropdownLaser = document.getElementById('btnDropdownLaser');
  const btnDropdownScreenshot = document.getElementById('btnDropdownScreenshot');
  const btnDropdownRecord = document.getElementById('btnDropdownRecord');
  const btnDropdownCam = document.getElementById('btnDropdownCam');
  const btnDropdownBlockInput = document.getElementById('btnDropdownBlockInput');
  const btnDropdownCurtain = document.getElementById('btnDropdownCurtain');
  const btnDropdownSnippets = document.getElementById('btnDropdownSnippets');

  const badgeWhiteboardActive = document.getElementById('badgeWhiteboardActive');
  const badgeLaserActive = document.getElementById('badgeLaserActive');
  const badgeRecordActive = document.getElementById('badgeRecordActive');
  const badgeCamActive = document.getElementById('badgeCamActive');
  const badgeBlockInputActive = document.getElementById('badgeBlockInputActive');
  const badgeCurtainActive = document.getElementById('badgeCurtainActive');
  const modalSendPassword = document.getElementById('modalSendPassword');
  const inputSecurePassword = document.getElementById('inputSecurePassword');
  const btnConfirmSendPassword = document.getElementById('btnConfirmSendPassword');
  const btnCancelSendPassword = document.getElementById('btnCancelSendPassword');
  const btnCloseSendPassword = document.getElementById('btnCloseSendPassword');
  const btnOpenPasswordModal = document.getElementById('btnOpenPasswordModal');
  const shelfChatTab = document.getElementById('shelfChatTab');
  const chatHistory = document.getElementById('chatHistory');
  const chatInputForm = document.getElementById('chatInputForm');
  const chatMessageInput = document.getElementById('chatMessageInput');

  // --- Landing View DOM ---
  const landingSection = document.getElementById('landingSection');
  const landingCanvas = document.getElementById('landingCanvas');
  const btnLandingStart = document.getElementById('btnLandingStart');
  const txtLandingStart = document.getElementById('txtLandingStart');
  const btnLandingQuickJump = document.getElementById('btnLandingQuickJump');
  const btnLandingDownloadJump = document.getElementById('btnLandingDownloadJump');
  const landingQuickConnectForm = document.getElementById('landingQuickConnectForm');
  const landingRoomInput = document.getElementById('landingRoomInput');
  const landingPinInput = document.getElementById('landingPinInput');
  const btnLandingDlExe = document.getElementById('btnLandingDlExe');
  const btnLandingDlBat = document.getElementById('btnLandingDlBat');
  const btnLandingCopyPs1 = document.getElementById('btnLandingCopyPs1');
  const btnNavLogin = document.getElementById('btnNavLogin');
  const brandLogo = document.querySelector('.brand-logo');

  // --- Application State ---
  let isInputBlocked = false;
  let authToken = localStorage.getItem('meikova_relay_token') || null;
  let currentUser = null;
  let authMode = 'login';
  let currentView = 'landing';

  let ws = null;
  let isConnected = false;
  let hasPromptedHeadlessDisplay = false;
  let currentRoom = null;
  let currentRoomId = null;
  let currentPin = '';
  let hostResolution = { width: 1920, height: 1080 };
  let isFitMode = true;

  // Remote Restart & Auto-Reconnect
  let isAwaitingRemoteRestart = false;
  let restartReconnectRoom = '';
  let restartReconnectPin = '';
  let restartReconnectRelay = '';
  let restartReconnectTimer = null;
  let restartAttemptCount = 0;

  // Resilient Session Auto-Reconnect State
  let isAutoReconnecting = false;
  let autoReconnectTimer = null;
  let autoReconnectAttempts = 0;
  const MAX_AUTO_RECONNECT_ATTEMPTS = 12;
  let lastSessionRelay = '';
  let lastSessionRoom = '';
  let lastSessionPin = '';
  let isUserInitiatedDisconnect = false;

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

  // Recording & Face Cam State
  let mediaRecorder = null;
  let recordedChunks = [];
  let isRecording = false;
  let isWebcamActive = false;
  let webcamStream = null;
  let recAnimId = null;

  // Process Manager State
  let currentProcessList = [];

  // File Manager State
  let remoteCurrentPath = '';
  let activeDownloads = {};

  // Audit State
  let auditPage = 0;
  const auditLimit = 25;
  let auditTotal = 0;

  // Privacy Curtain State
  let isCurtainActive = false;

  // Live Whiteboard State
  let isWhiteboardActive = false;
  let wbCurrentTool = 'pen'; // 'pen' | 'highlighter' | 'arrow' | 'eraser'
  let wbCurrentColor = '#06B6D4';
  let wbLaserFade = false;
  let wbDrawing = false;
  let wbStartPos = { x: 0, y: 0 };
  let wbLastPos = { x: 0, y: 0 };
  let wbStrokes = [];
  let wbAnimFrameId = null;

  let auditSearchDebounce = null;

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
    F7: 0x76, F8: 0x77, F9: 0x78, F10: 0x79, F11: 0x7A, F12: 0x7B,
    Backquote: 0xC0, Minus: 0xBD, Equal: 0xBB,
    BracketLeft: 0xDB, BracketRight: 0xDD, Backslash: 0xDC,
    Semicolon: 0xBA, Quote: 0xDE,
    Comma: 0xBC, Period: 0xBE, Slash: 0xBF
  };

  // Default server URLs
  const isDesktopLocal = window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost';
  let defaultWsUrl;
  if (isDesktopLocal && window.location.port !== '8080') {
    defaultWsUrl = 'ws://localhost:8080';
  } else {
    const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    defaultWsUrl = `${wsProto}//${window.location.host}`;
  }
  const savedWsRelay = localStorage.getItem('meikova_relay_custom_url');
  qcRelayUrl.value = savedWsRelay || defaultWsUrl;
  qcRelayUrl.addEventListener('change', () => {
    if (qcRelayUrl.value.trim()) {
      localStorage.setItem('meikova_relay_custom_url', qcRelayUrl.value.trim());
    }
  });

  // --- SLIDING SEGMENTED INDICATOR ENGINE (MEIKOVA LOOP PATTERN) ---
  function placeIndicator(seg) {
    if (!seg) return;
    const onBtn = seg.querySelector('button.on');
    const ind = seg.querySelector('.seg__ind');
    if (!ind) return;
    if (window.innerWidth < 768 && seg.id === 'mainNav') {
      ind.style.opacity = '0';
      ind.style.setProperty('--ind-w', '0px');
      return;
    }
    if (!onBtn) {
      ind.style.setProperty('--ind-w', '0px');
      ind.style.opacity = '0';
      return;
    }
    ind.style.opacity = '1';
    ind.style.setProperty('--ind-x', `${onBtn.offsetLeft}px`);
    ind.style.setProperty('--ind-w', `${onBtn.offsetWidth}px`);
  }

  function placeAllIndicators() {
    document.querySelectorAll('.seg').forEach(placeIndicator);
  }

  window.placeIndicator = placeIndicator;
  window.placeAllIndicators = placeAllIndicators;

  window.addEventListener('resize', placeAllIndicators);
  if (document.fonts) document.fonts.ready.then(placeAllIndicators);
  setTimeout(placeAllIndicators, 60);

  // Persistent Client Machine GUID for Hardware-Level Loopback & Multi-Client Session Isolation
  let myMachineId = localStorage.getItem('meikova_relay_client_machine_id');
  if (!myMachineId) {
    myMachineId = 'client_' + (window.crypto && crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2, 11));
    localStorage.setItem('meikova_relay_client_machine_id', myMachineId);
  }

  // --- REST API CALLS ---
  async function apiFetch(endpoint, method = 'GET', body = null) {
    const headers = { 'Content-Type': 'application/json', 'X-Machine-Id': myMachineId };
    if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
    const opts = { method, headers };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(endpoint, opts);
    return res.json();
  }

  // --- URL ROUTING & PATH / QUERY STATE ENGINE ---
  function getRouteStateFromUrl() {
    const rawPath = window.location.pathname.replace(/^\/+|\/+$/g, '').toLowerCase();
    const searchParams = new URLSearchParams(window.location.search);
    let hash = window.location.hash.replace(/^#\/?/, '');
    if (hash.includes('?')) hash = hash.split('?')[1];
    const hashParams = new URLSearchParams(hash);

    const getParam = (key) => searchParams.get(key) || hashParams.get(key) || '';

    const roomParam = getParam('room');
    const pinParam = getParam('pin');
    const directParam = getParam('direct');
    const isDirect = directParam === '1' || directParam === 'true';
    const browsePath = getParam('path');
    const langParam = getParam('lang');

    let view = 'landing';
    if (rawPath === 'auth' || rawPath === 'login') view = 'auth';
    else if (rawPath === 'remote') view = 'remote';
    else if (rawPath === 'files') view = 'files';
    else if (rawPath === 'terminal') view = 'terminal';
    else if (rawPath === 'tasks') view = 'tasks';
    else if (rawPath === 'audit' || rawPath === 'audit-logs') view = 'audit';
    else if (rawPath === 'dashboard') view = 'dashboard';
    else if (rawPath === 'home' || rawPath === 'landing' || rawPath === '') {
      if (roomParam && (isDirect || rawPath === 'remote')) {
        view = 'remote';
      } else if (roomParam && !rawPath) {
        // Direct remote link via /?room=...
        view = isDirect ? 'remote' : 'landing';
      } else {
        view = 'landing';
      }
    }

    if (langParam && window.MeikovaI18n) {
      window.MeikovaI18n.setLang(langParam, false);
    }

    return {
      view,
      room: roomParam,
      pin: pinParam,
      direct: isDirect,
      browsePath: browsePath,
      lang: langParam
    };
  }

  function syncUrlWithState(replace = false) {
    let path = '/' + currentView;
    if (currentView === 'landing') path = '/';
    if (currentView === 'dashboard') path = '/dashboard';
    if (currentView === 'auth') path = '/auth';

    const params = new URLSearchParams();
    if (currentRoom && ['remote', 'files', 'terminal', 'tasks'].includes(currentView)) {
      params.set('room', currentRoom);
      if (currentPin) {
        params.set('pin', currentPin);
      }
      if (currentView === 'files' && remoteCurrentPath) {
        params.set('path', remoteCurrentPath);
      }
    }

    if (window.MeikovaI18n && window.MeikovaI18n.getLang() !== window.MeikovaI18n.DEFAULT_LANG) {
      params.set('lang', window.MeikovaI18n.getLang());
    }

    const qs = params.toString() ? '?' + params.toString() : '';
    const targetUrl = path + qs;
    const currentUrl = window.location.pathname + window.location.search;

    if (currentUrl !== targetUrl) {
      if (replace) {
        history.replaceState({ view: currentView, room: currentRoom, path: remoteCurrentPath }, '', targetUrl);
      } else {
        history.pushState({ view: currentView, room: currentRoom, path: remoteCurrentPath }, '', targetUrl);
      }
    }
  }

  window.addEventListener('meikova-lang-changed', () => {
    syncUrlWithState(true);
    updateRoStatus();
    const connOverlay = document.getElementById('canvasConnectingOverlay');
    if (connOverlay) connOverlay.classList.remove('hidden');
    updateTerminalStatusBadge();
    requestAnimationFrame(placeAllIndicators);
    if (currentView === 'dashboard') {
      renderDeviceGrid(currentDeviceList);
    }
    if (currentView === 'tasks' && currentProcessList && currentProcessList.length > 0) {
      renderProcessTable();
    }
    if (currentView === 'files' && currentExplorerItems) {
      renderFullFileExplorer({
        items: currentExplorerItems,
        drives: currentExplorerDrives,
        current_path: remoteCurrentPath,
        parent_path: remoteParentPath
      });
    }
    if (currentView === 'audit' && typeof loadAuditLogs === 'function') {
      loadAuditLogs();
    }
    if (fileEditorModal && !fileEditorModal.classList.contains('hidden')) {
      updateEditorStats();
    }
  });

  window.addEventListener('popstate', () => {
    const route = getRouteStateFromUrl();
    if (route.view !== 'auth' && route.view !== 'landing' && (!authToken || !currentUser)) {
      switchView('landing', false);
      return;
    }
    if (route.room && route.room !== currentRoom) {
      currentRoom = route.room;
      currentPin = route.pin || sessionStorage.getItem('meikova_relay_pin_' + route.room) || '';
      remoteCurrentPath = route.browsePath || '';
      switchView(route.view, false);
      startRemoteSession(defaultWsUrl, route.room, currentPin);
      return;
    }
    if (route.browsePath && route.browsePath !== remoteCurrentPath) {
      remoteCurrentPath = route.browsePath;
    }
    switchView(route.view || 'landing', false);
  });

  // --- INITIALIZATION ---
  function initDesktopIntegration() {
    function setupControls() {
      const isDesktop = typeof window !== 'undefined' && Boolean(window.pywebview && window.pywebview.api);
      if (!isDesktop) return;

      document.body.classList.add('is-desktop-app');
      const winControls = document.getElementById('desktopWinControls');
      if (winControls) {
        winControls.style.display = 'inline-flex';
      }

      const topbar = document.querySelector('.topbar');
      if (topbar && !topbar.dataset.dragBound) {
        topbar.dataset.dragBound = 'true';
        topbar.addEventListener('mousedown', (e) => {
          if (e.target.closest('button, a, input, select, textarea, .seg, .user-badge, .wc-btn')) {
            return;
          }
          if (e.button === 0 && window.pywebview?.api?.start_drag) {
            window.pywebview.api.start_drag();
          }
        });

        topbar.addEventListener('dblclick', (e) => {
          if (e.target.closest('button, a, input, select, textarea, .seg, .user-badge, .wc-btn')) {
            return;
          }
          toggleDesktopMaximize();
        });
      }

      const btnMin = document.getElementById('btnWinMin');
      const btnMax = document.getElementById('btnWinMax');
      const btnClose = document.getElementById('btnWinClose');

      if (btnMin && !btnMin.dataset.bound) {
        btnMin.dataset.bound = 'true';
        btnMin.addEventListener('click', () => {
          window.pywebview?.api?.minimize_window?.();
        });
      }

      async function toggleDesktopMaximize() {
        try {
          if (window.pywebview?.api?.toggle_maximize) {
            const isMax = await window.pywebview.api.toggle_maximize();
            updateMaximizeIcon(isMax);
          }
        } catch (e) {
          console.debug('toggle_maximize err', e);
        }
      }

      function updateMaximizeIcon(isMax) {
        if (!btnMax) return;
        const iconMax = btnMax.querySelector('.icon-max');
        const iconRestore = btnMax.querySelector('.icon-restore');
        if (iconMax && iconRestore) {
          iconMax.style.display = isMax ? 'none' : 'block';
          iconRestore.style.display = isMax ? 'block' : 'none';
        }
      }

      if (btnMax && !btnMax.dataset.bound) {
        btnMax.dataset.bound = 'true';
        btnMax.addEventListener('click', toggleDesktopMaximize);
      }

      if (btnClose && !btnClose.dataset.bound) {
        btnClose.dataset.bound = 'true';
        btnClose.addEventListener('click', () => {
          window.pywebview?.api?.close_window?.();
        });
      }
    }

    if (window.pywebview && window.pywebview.api) {
      setupControls();
    } else {
      window.addEventListener('pywebviewready', setupControls);
    }
  }

  async function initApp() {
    try { updateRelayModalData(); } catch (_) {}
    initDesktopIntegration();
    applyDeckMode(currentDeckMode);
    const route = getRouteStateFromUrl();

    // 1. Synchronously resolve target view based on URL route and cached token
    let targetView = 'landing';
    const isExplicitDirectConnect = Boolean(route.room && (route.direct || (route.view === 'remote' && route.direct)));
    if (isExplicitDirectConnect) {
      targetView = route.view || 'remote';
    } else if (authToken) {
      if (route.view === 'auth') {
        targetView = 'dashboard';
      } else {
        targetView = (route.view && ['dashboard', 'files', 'terminal', 'tasks', 'audit'].includes(route.view)) ? route.view : 'dashboard';
      }
    } else {
      if (route.view === 'auth') {
        targetView = 'auth';
      } else {
        targetView = route.view || 'landing';
      }
    }

    // Restore deep link state synchronously ONLY if explicit direct connection
    if (isExplicitDirectConnect) {
      currentRoom = route.room;
      const savedPin = route.pin || sessionStorage.getItem('meikova_relay_pin_' + route.room) || '';
      currentPin = savedPin;
      if (savedPin) {
        sessionStorage.setItem('meikova_relay_pin_' + route.room, savedPin);
      }
      if (route.browsePath) {
        remoteCurrentPath = route.browsePath;
      }
    }

    // Immediately paint target view with ZERO delay or flash
    switchView(targetView, false);

    // 2. Asynchronously verify session token
    if (authToken) {
      try {
        const data = await apiFetch('/api/auth/me');
        if (data.success && data.user) {
          currentUser = data.user;
          renderUserBadge();

          // If auth view was deep linked, update URL to dashboard
          if (route.view === 'auth') {
            syncUrlWithState(true);
            return;
          }

          // If room was explicitly direct connected via ?direct=1, start session
          if (isExplicitDirectConnect && ['remote', 'files', 'terminal', 'tasks'].includes(targetView)) {
            const savedPin = currentPin || route.pin || sessionStorage.getItem('meikova_relay_pin_' + route.room) || '';
            startRemoteSession(defaultWsUrl, route.room, savedPin);
            return;
          }

          return;
        } else {
          // Token expired or invalid
          authToken = null;
          currentUser = null;
          localStorage.removeItem('meikova_relay_token');
          renderUserBadge();
          if (targetView !== 'landing' && targetView !== 'auth' && !isExplicitDirectConnect) {
            switchView('landing', true);
            showToast(t('toast.session_expired'), 'info');
          }
        }
      } catch (err) {
        console.warn('Auth check error:', err);
      }
    }

    // 3. Direct or Unauthenticated connect with room ID (ONLY if explicit direct=1)
    if (isExplicitDirectConnect && ['remote', 'files', 'terminal', 'tasks'].includes(targetView)) {
      const savedPin = currentPin || route.pin || sessionStorage.getItem('meikova_relay_pin_' + route.room) || '';
      startRemoteSession(defaultWsUrl, route.room, savedPin);
      return;
    }

    // 4. Unauthenticated pending deep link
    if (route.view !== 'landing' && route.room) {
      sessionStorage.setItem('meikova_relay_pending_route', window.location.pathname + window.location.search);
    }
  }

  function handleAuthSuccess(res) {
    authToken = res.token;
    localStorage.setItem('meikova_relay_token', authToken);
    if (window.meikovaSync) window.meikovaSync.setAuthToken(authToken);
    currentUser = res.user;
    lastGlobalActivity = Date.now();
    lastTokenRefreshTime = Date.now();
    renderUserBadge();

    const pending = sessionStorage.getItem('meikova_relay_pending_route');
    if (pending) {
      sessionStorage.removeItem('meikova_relay_pending_route');
      history.replaceState(null, '', pending);
      const route = getRouteStateFromUrl();
      if (route.room && ['remote', 'files', 'terminal', 'tasks'].includes(route.view)) {
        currentRoom = route.room;
        currentPin = route.pin || sessionStorage.getItem('meikova_relay_pin_' + route.room) || '';
        if (route.browsePath) remoteCurrentPath = route.browsePath;
        switchView(route.view, false);
        syncUrlWithState(true);
        startRemoteSession(defaultWsUrl, route.room, currentPin);
        return;
      }
      switchView(route.view, false);
      syncUrlWithState(true);
      return;
    }

    switchView('dashboard', true);
    loadDeviceFleet();
  }

  function renderUserBadge() {
    if (currentUser) {
      userNameDisplay.textContent = currentUser.username;
      userNameDisplay.title = currentUser.username;
      userBadge.classList.remove('hidden');
      btnNavLogin?.classList.add('hidden');
      if (txtLandingStart) {
        txtLandingStart.setAttribute('data-i18n', 'landing.btn_dashboard');
        txtLandingStart.textContent = t('landing.btn_dashboard');
      }
    } else {
      userBadge.classList.add('hidden');
      btnNavLogin?.classList.remove('hidden');
      if (txtLandingStart) {
        txtLandingStart.setAttribute('data-i18n', 'landing.btn_start');
        txtLandingStart.textContent = t('landing.btn_start');
      }
    }
    try {
      updateInstallModalContent();
      updateRelayModalData();
    } catch (_) {}
  }

  // --- GOOGLE SIGN-IN (GIS + DESKTOP RFC 8252) ---
  let googleClientIdCache = null;

  async function initGoogleSignIn() {
    const btnGoogle = document.getElementById('btn-ambient-google');
    if (btnGoogle) {
      btnGoogle.addEventListener('click', triggerGoogleAuth);
    }

    // Background One Tap initialize if GIS client is loaded
    if (typeof google !== 'undefined' && google.accounts && google.accounts.id) {
      try {
        if (!googleClientIdCache) {
          const confRes = await apiFetch('/api/auth/google/config');
          if (confRes && confRes.success && confRes.client_id) {
            googleClientIdCache = confRes.client_id;
          }
        }
        if (googleClientIdCache) {
          google.accounts.id.initialize({
            client_id: googleClientIdCache,
            callback: handleGoogleCredentialResponse,
            auto_select: false
          });
        }
      } catch (_) {}
    }
  }

  async function triggerGoogleAuth() {
    const isMobileDevice = /android|iphone|ipad|ipod/i.test(navigator.userAgent);
    const isDesktopApp = typeof window !== 'undefined' && Boolean(window.pywebview);

    if (isDesktopApp) {
      return startDesktopGoogleAuth();
    }

    try {
      showToast(t('toast.google_connecting'), 'info');
      const source = isMobileDevice ? 'mobile' : 'web';
      const res = await apiFetch(`/api/auth/google/url?source=${source}`);
      if (!res.success || !res.auth_url) {
        showToast(res.error || 'Chưa cấu hình Google OAuth.', 'error');
        return;
      }

      if (isMobileDevice) {
        window.location.href = res.auth_url;
        return;
      }

      const popup = window.open(res.auth_url, 'MeikovaGoogleAuth', 'width=520,height=640,menubar=no,toolbar=no,location=no');
      if (!popup || popup.closed || typeof popup.closed === 'undefined') {
        window.location.href = res.auth_url;
        return;
      }

      const ticket = res.ticket;
      let isDone = false;

      const onMessage = (event) => {
        if (event.data && event.data.type === 'GOOGLE_AUTH_SUCCESS' && event.data.token) {
          isDone = true;
          window.removeEventListener('message', onMessage);
          clearInterval(pollTimer);
          handleAuthSuccess(event.data);
          showToast(t('toast.google_success'), 'success');
        }
      };
      window.addEventListener('message', onMessage);

      const pollTimer = setInterval(async () => {
        if (isDone) return;
        try {
          const pollRes = await apiFetch(`/api/auth/google/poll?ticket=${ticket}`);
          if (pollRes.success && pollRes.token) {
            isDone = true;
            clearInterval(pollTimer);
            window.removeEventListener('message', onMessage);
            try { if (popup && !popup.closed) popup.close(); } catch (_) {}
            handleAuthSuccess(pollRes);
            showToast(t('toast.google_success'), 'success');
          }
        } catch (_) {}
      }, 1200);

      setTimeout(() => {
        clearInterval(pollTimer);
        window.removeEventListener('message', onMessage);
      }, 180000);
    } catch (e) {
      showToast(t('toast.generic_error', { message: e.message }), 'error');
    }
  }

  async function startDesktopGoogleAuth() {
    try {
      const isMobileDevice = /android|iphone|ipad|ipod/i.test(navigator.userAgent);
      const isDesktopApp = typeof window !== 'undefined' && Boolean(window.pywebview);
      const source = isDesktopApp ? 'desktop' : (isMobileDevice ? 'mobile' : 'desktop');
      const res = await apiFetch(`/api/auth/google/url?source=${source}`);
      if (!res.success || !res.auth_url) {
        showToast(res.error || 'Không lấy được URL ủy quyền Google', 'error');
        return;
      }
      if (window.pywebview && window.pywebview.api && window.pywebview.api.open_external_url) {
        window.pywebview.api.open_external_url(res.auth_url);
      } else {
        window.open(res.auth_url, '_blank');
      }
      showToast(t('toast.google_opening_browser'), 'info');

      const ticket = res.ticket;
      const pollTimer = setInterval(async () => {
        try {
          const pollRes = await apiFetch(`/api/auth/google/poll?ticket=${ticket}`);
          if (pollRes.success && pollRes.token) {
            clearInterval(pollTimer);
            handleAuthSuccess(pollRes);
            showToast(t('toast.google_success'), 'success');
          }
        } catch (_) {}
      }, 1500);
      setTimeout(() => clearInterval(pollTimer), 180000);
    } catch (e) {
      showToast(t('toast.generic_error', { message: e.message }), 'error');
    }
  }

  async function handleGoogleCredentialResponse(response) {
    try {
      const res = await apiFetch('/api/auth/google', 'POST', {
        credential: response.credential
      });
      if (res.success && res.token) {
        handleAuthSuccess(res);
      } else {
        authError.textContent = res.message || 'Google đăng nhập thất bại';
        authError.classList.remove('hidden');
      }
    } catch (err) {
      authError.textContent = `Lỗi: ${err.message}`;
      authError.classList.remove('hidden');
    }
  }

  initGoogleSignIn();

  function initUniversalSSO() {
    const btnSso = document.getElementById('btn-sso-gateway');
    if (btnSso) {
      btnSso.addEventListener('click', () => {
        const authGatewayUrl = window.MEIKOVA_AUTH_URL || (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' ? 'http://127.0.0.1:8990' : 'https://meikova-auth.onrender.com');
        const origin = window.location.origin;
        const ssoUrl = `${authGatewayUrl}/login?client_id=relay&origin=${encodeURIComponent(origin)}`;
        const w = 400, h = 540;
        const left = Math.max(0, (window.screen.width - w) / 2);
        const top = Math.max(0, (window.screen.height - h) / 2);
        window.open(ssoUrl, 'meikova_sso', `width=${w},height=${h},left=${left},top=${top},status=no,toolbar=no,menubar=no`);
      });
    }

    window.addEventListener('message', (event) => {
      if (event.data && event.data.type === 'MEIKOVA_SSO_SUCCESS') {
        const { token, user } = event.data;
        if (token) {
          handleAuthSuccess({ token, user });
          showToast(t('toast.meikova_id_success'), 'success');
        }
      }
    });
  }
  initUniversalSSO();

  // --- AMBIENT INFINITY TELEMETRY CANVAS 2D VISUALIZER (/ambient-instrument-ui) ---
  let landingCanvasAnimId = null;
  let landingCanvasInited = false;
  const landingPointer = { x: -999, y: -999, active: false };

  function initLandingCanvas() {
    if (!landingCanvas) return;
    const ctx = landingCanvas.getContext('2d');
    if (!ctx) return;

    function resizeCanvas() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const rect = landingCanvas.getBoundingClientRect();
      const w = rect.width || landingCanvas.parentElement?.clientWidth || window.innerWidth;
      const h = rect.height || landingCanvas.parentElement?.clientHeight || 600;
      landingCanvas.width = Math.round(w * dpr);
      landingCanvas.height = Math.round(h * dpr);
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.scale(dpr, dpr);
    }
    resizeCanvas();
    requestAnimationFrame(resizeCanvas);
    window.addEventListener('resize', resizeCanvas);
    if (window.ResizeObserver && landingCanvas.parentElement) {
      const ro = new ResizeObserver(() => resizeCanvas());
      ro.observe(landingCanvas.parentElement);
    }

    // Track mouse on hero arena parent for seamless response
    const arenaEl = landingCanvas.parentElement || landingCanvas;
    arenaEl.addEventListener('mousemove', (e) => {
      const rect = landingCanvas.getBoundingClientRect();
      landingPointer.x = e.clientX - rect.left;
      landingPointer.y = e.clientY - rect.top;
      landingPointer.active = true;
    });
    arenaEl.addEventListener('mouseleave', () => {
      landingPointer.active = false;
    });

    // Interactive Shockwave Ripples on Click
    const ripples = [];
    arenaEl.addEventListener('click', (e) => {
      const rect = landingCanvas.getBoundingClientRect();
      ripples.push({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
        r: 6,
        maxR: 320,
        alpha: 0.85
      });
    });

    // Ambient Quantum Stardust Particles (Interconnected Micro-Constellations)
    const dustCount = 56;
    const dustParticles = [];
    for (let i = 0; i < dustCount; i++) {
      dustParticles.push({
        x: Math.random() * (window.innerWidth || 1400),
        y: Math.random() * 800,
        vx: (Math.random() - 0.5) * 0.22,
        vy: -0.10 - Math.random() * 0.20,
        r: 0.7 + Math.random() * 1.5,
        alpha: 0.15 + Math.random() * 0.45,
        hue: Math.random() < 0.4 ? 150 : (Math.random() < 0.7 ? 200 : 38)
      });
    }

    // Extended Multi-Tier Harmonic Tension Chords (28 Precision Filaments)
    const chordPairs = [
      // Left Loop (Host Workstation cluster - Amber / Copper / Emerald / Mint)
      { t1: Math.PI * 0.62, t2: Math.PI * 1.38, cpOffset: -0.15, color: 'rgba(245, 158, 11, ' },
      { t1: Math.PI * 0.72, t2: Math.PI * 1.28, cpOffset: -0.25, color: 'rgba(34, 197, 94, ' },
      { t1: Math.PI * 0.55, t2: Math.PI * 1.45, cpOffset: -0.08, color: 'rgba(245, 158, 11, ' },
      { t1: Math.PI * 0.85, t2: Math.PI * 1.15, cpOffset: -0.35, color: 'rgba(34, 197, 94, ' },
      { t1: Math.PI * 0.92, t2: Math.PI * 1.08, cpOffset: -0.42, color: 'rgba(234, 88, 12, ' },
      { t1: Math.PI * 0.68, t2: Math.PI * 1.32, cpOffset: -0.20, color: 'rgba(16, 185, 129, ' },
      { t1: Math.PI * 0.78, t2: Math.PI * 1.22, cpOffset: -0.30, color: 'rgba(245, 158, 11, ' },
      { t1: Math.PI * 0.58, t2: Math.PI * 1.42, cpOffset: -0.10, color: 'rgba(34, 197, 94, ' },
      { t1: Math.PI * 0.88, t2: Math.PI * 1.12, cpOffset: -0.38, color: 'rgba(234, 88, 12, ' },
      { t1: Math.PI * 0.95, t2: Math.PI * 1.05, cpOffset: -0.45, color: 'rgba(245, 158, 11, ' },

      // Right Loop (Remote Client cluster - Sky Cyan / Electric Slate / Indigo / Violet)
      { t1: Math.PI * 0.18, t2: Math.PI * 1.82, cpOffset: 0.25, color: 'rgba(56, 189, 248, ' },
      { t1: Math.PI * 0.28, t2: Math.PI * 1.72, cpOffset: 0.15, color: 'rgba(96, 165, 250, ' },
      { t1: Math.PI * 0.08, t2: Math.PI * 1.92, cpOffset: 0.35, color: 'rgba(56, 189, 248, ' },
      { t1: Math.PI * 0.36, t2: Math.PI * 1.64, cpOffset: 0.08, color: 'rgba(129, 140, 248, ' },
      { t1: Math.PI * 0.42, t2: Math.PI * 1.58, cpOffset: 0.02, color: 'rgba(56, 189, 248, ' },
      { t1: Math.PI * 0.22, t2: Math.PI * 1.78, cpOffset: 0.20, color: 'rgba(167, 139, 250, ' },
      { t1: Math.PI * 0.12, t2: Math.PI * 1.88, cpOffset: 0.30, color: 'rgba(56, 189, 248, ' },
      { t1: Math.PI * 0.32, t2: Math.PI * 1.68, cpOffset: 0.12, color: 'rgba(96, 165, 250, ' },
      { t1: Math.PI * 0.04, t2: Math.PI * 1.96, cpOffset: 0.40, color: 'rgba(129, 140, 248, ' },
      { t1: Math.PI * 0.38, t2: Math.PI * 1.62, cpOffset: 0.05, color: 'rgba(56, 189, 248, ' },

      // Trans-Lobe Nexus Crossing Bridges (Outbound Relay Telemetry)
      { t1: Math.PI * 0.48, t2: Math.PI * 1.52, cpOffset: 0, color: 'rgba(255, 255, 255, ' },
      { t1: Math.PI * 0.52, t2: Math.PI * 1.48, cpOffset: 0, color: 'rgba(56, 189, 248, ' },
      { t1: Math.PI * 0.32, t2: Math.PI * 1.25, cpOffset: 0, color: 'rgba(56, 189, 248, ' },
      { t1: Math.PI * 0.68, t2: Math.PI * 1.75, cpOffset: 0, color: 'rgba(245, 158, 11, ' },
      { t1: Math.PI * 0.46, t2: Math.PI * 1.54, cpOffset: 0, color: 'rgba(226, 232, 240, ' },
      { t1: Math.PI * 0.54, t2: Math.PI * 1.46, cpOffset: 0, color: 'rgba(56, 189, 248, ' },
      { t1: Math.PI * 0.38, t2: Math.PI * 1.30, cpOffset: 0, color: 'rgba(96, 165, 250, ' },
      { t1: Math.PI * 0.62, t2: Math.PI * 1.70, cpOffset: 0, color: 'rgba(34, 197, 94, ' }
    ];

    let lastTime = performance.now();
    let smoothOffsetX = 0;
    let smoothOffsetY = 0;
    const NUM_BLOCKS = 240;

    function render(now) {
      if (currentView !== 'landing') return;
      const dt = Math.min((now - lastTime) / 1000, 0.08);
      lastTime = now;

      const rect = landingCanvas.getBoundingClientRect();
      const w = rect.width;
      const h = rect.height;
      if (w <= 0 || h <= 0) {
        landingCanvasAnimId = requestAnimationFrame(render);
        return;
      }

      ctx.clearRect(0, 0, w, h);

      // --- 0. Smooth Magnetic Parallax ---
      if (landingPointer.active) {
        const tx = (landingPointer.x - w / 2) * 0.035;
        const ty = (landingPointer.y - h / 2) * 0.035;
        smoothOffsetX += (tx - smoothOffsetX) * 0.06;
        smoothOffsetY += (ty - smoothOffsetY) * 0.06;
      } else {
        smoothOffsetX += (0 - smoothOffsetX) * 0.04;
        smoothOffsetY += (0 - smoothOffsetY) * 0.04;
      }

      // --- 1. Lemniscate Geometry Definition (Horizontal Figure-8 ∞) ---
      const cx = w * 0.5 + smoothOffsetX;
      const cy = h * 0.49 + smoothOffsetY;
      // Proportions: Majestic scale spanning across hero stage, framing content
      const isMobile = w < 1080;
      const scaleX = isMobile
        ? Math.max(340, Math.min(w * 0.46, 520))
        : Math.max(560, Math.min(w * 0.48, 920));
      const scaleY = isMobile
        ? Math.max(280, Math.min(h * 0.42, 480))
        : Math.max(480, Math.min(h * 0.74, 720));

      function getPoint(t) {
        const sinT = Math.sin(t);
        const cosT = Math.cos(t);
        const denom = 1 + sinT * sinT;
        return {
          x: cx + (scaleX * cosT) / denom,
          y: cy + (scaleY * sinT * cosT) / denom
        };
      }

      function getTangentAngle(t) {
        const delta = 0.002;
        const pA = getPoint(t - delta);
        const pB = getPoint(t + delta);
        return Math.atan2(pB.y - pA.y, pB.x - pA.x);
      }

      // --- 2. Ambient Deep Atmospheric Nebulas & Caustic Shimmer ---
      const pulseT = Math.sin(now * 0.0012) * 0.02;
      // Left Lobe Nebula (Host Station: Emerald-Amber glow)
      const gLeft = ctx.createRadialGradient(cx - scaleX * 0.55, cy, 0, cx - scaleX * 0.55, cy, scaleX * 0.75);
      gLeft.addColorStop(0, `rgba(245, 158, 11, ${0.10 + pulseT})`);
      gLeft.addColorStop(0.38, `rgba(34, 197, 94, ${0.06 + pulseT})`);
      gLeft.addColorStop(1, 'rgba(0, 0, 0, 0)');
      ctx.fillStyle = gLeft;
      ctx.beginPath();
      ctx.arc(cx - scaleX * 0.55, cy, scaleX * 0.75, 0, Math.PI * 2);
      ctx.fill();

      // Right Lobe Nebula (Remote Client: Cyan-Indigo glow)
      const gRight = ctx.createRadialGradient(cx + scaleX * 0.55, cy, 0, cx + scaleX * 0.55, cy, scaleX * 0.75);
      gRight.addColorStop(0, `rgba(56, 189, 248, ${0.11 + pulseT})`);
      gRight.addColorStop(0.38, `rgba(129, 140, 248, ${0.06 + pulseT})`);
      gRight.addColorStop(1, 'rgba(0, 0, 0, 0)');
      ctx.fillStyle = gRight;
      ctx.beginPath();
      ctx.arc(cx + scaleX * 0.55, cy, scaleX * 0.75, 0, Math.PI * 2);
      ctx.fill();

      // Center Relay Nexus Pulse
      const gNexus = ctx.createRadialGradient(cx, cy, 0, cx, cy, 180);
      gNexus.addColorStop(0, `rgba(255, 255, 255, ${0.05 + pulseT * 0.5})`);
      gNexus.addColorStop(0.45, 'rgba(56, 189, 248, 0.025)');
      gNexus.addColorStop(1, 'rgba(0, 0, 0, 0)');
      ctx.fillStyle = gNexus;
      ctx.beginPath();
      ctx.arc(cx, cy, 180, 0, Math.PI * 2);
      ctx.fill();

      // Longitudinal Magnetic Conduit Line connecting lobe foci
      ctx.beginPath();
      ctx.moveTo(cx - scaleX * 0.55, cy);
      ctx.lineTo(cx + scaleX * 0.55, cy);
      ctx.strokeStyle = `rgba(56, 189, 248, ${0.04 + pulseT * 0.5})`;
      ctx.lineWidth = 0.8;
      ctx.stroke();

      // --- 3. Internal Neural Telemetry Chords (Meikova Loop Arc Web) with Magnetic Pull ---
      chordPairs.forEach((cp, idx) => {
        const p1 = getPoint(cp.t1);
        const p2 = getPoint(cp.t2);
        const midX = (p1.x + p2.x) * 0.5;
        const midY = (p1.y + p2.y) * 0.5;
        let ctrlX = midX + (cx - midX) * 0.4 + cp.cpOffset * (scaleX * 0.16);
        let ctrlY = midY + (cy - midY) * 0.4 + Math.sin(now * 0.0008 + idx) * 16;

        // Subtle gravitational pull toward cursor on nearby chords
        if (landingPointer.active) {
          const dPtr = Math.hypot(ctrlX - landingPointer.x, ctrlY - landingPointer.y);
          if (dPtr < 160 && dPtr > 0) {
            const pull = (1 - dPtr / 160) * 18;
            ctrlX += (landingPointer.x - ctrlX) * (pull / dPtr);
            ctrlY += (landingPointer.y - ctrlY) * (pull / dPtr);
          }
        }

        const chordAlpha = 0.045 + 0.035 * Math.sin(now * 0.001 + idx * 0.7);
        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y);
        ctx.quadraticCurveTo(ctrlX, ctrlY, p2.x, p2.y);
        ctx.strokeStyle = `${cp.color}${chordAlpha})`;
        ctx.lineWidth = 0.75;
        ctx.stroke();
      });

      // --- 4. Continuous Hairline Guide Rails & Precision Vernier Graduations ---
      const railSteps = 260;
      const trackThickness = 12;

      // Outer Rail
      ctx.beginPath();
      for (let r = 0; r <= railSteps; r++) {
        const rt = (r / railSteps) * Math.PI * 2;
        const rp = getPoint(rt);
        const rtheta = getTangentAngle(rt);
        const normX = -Math.sin(rtheta);
        const normY = Math.cos(rtheta);
        const rx = rp.x + normX * (trackThickness * 0.5 + 2);
        const ry = rp.y + normY * (trackThickness * 0.5 + 2);
        if (r === 0) ctx.moveTo(rx, ry);
        else ctx.lineTo(rx, ry);
      }
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
      ctx.lineWidth = 0.6;
      ctx.stroke();

      // Inner Rail
      ctx.beginPath();
      for (let r = 0; r <= railSteps; r++) {
        const rt = (r / railSteps) * Math.PI * 2;
        const rp = getPoint(rt);
        const rtheta = getTangentAngle(rt);
        const normX = -Math.sin(rtheta);
        const normY = Math.cos(rtheta);
        const rx = rp.x - normX * (trackThickness * 0.5 + 2);
        const ry = rp.y - normY * (trackThickness * 0.5 + 2);
        if (r === 0) ctx.moveTo(rx, ry);
        else ctx.lineTo(rx, ry);
      }
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
      ctx.lineWidth = 0.6;
      ctx.stroke();

      // Precision Vernier Caliper Scale Graduation Ticks on Outer Rail
      ctx.beginPath();
      for (let r = 0; r < railSteps; r += 4) {
        const rt = (r / railSteps) * Math.PI * 2;
        const rp = getPoint(rt);
        const rtheta = getTangentAngle(rt);
        const normX = -Math.sin(rtheta);
        const normY = Math.cos(rtheta);
        const isMajor = (r % 20 === 0);
        const tickLen = isMajor ? 6.5 : 3.2;
        const baseDist = trackThickness * 0.5 + 2;
        const x1 = rp.x + normX * baseDist;
        const y1 = rp.y + normY * baseDist;
        const x2 = rp.x + normX * (baseDist + tickLen);
        const y2 = rp.y + normY * (baseDist + tickLen);
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
      }
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.14)';
      ctx.lineWidth = 0.7;
      ctx.stroke();

      // Milestone Numerical Micro-Stamps along the perimeter
      const milestoneIndices = [
        { t: 0, label: 'NODE-02 // 0.8ms' },
        { t: Math.PI * 0.25, label: 'CH-1 // 120FPS' },
        { t: Math.PI * 0.75, label: 'CH-2 // CTL' },
        { t: Math.PI, label: 'NODE-01 // HOST' },
        { t: Math.PI * 1.25, label: 'CH-3 // 4K-RDY' },
        { t: Math.PI * 1.75, label: 'CH-4 // TLS1.3' }
      ];
      ctx.save();
      ctx.font = '7.5px Consolas, monospace';
      ctx.fillStyle = 'rgba(255, 255, 255, 0.32)';
      milestoneIndices.forEach(ms => {
        const p = getPoint(ms.t);
        const th = getTangentAngle(ms.t);
        const normX = -Math.sin(th);
        const normY = Math.cos(th);
        const labelX = p.x + normX * 18;
        const labelY = p.y + normY * 18;
        ctx.fillText(ms.label, labelX - 22, labelY + 3);
      });
      ctx.restore();

      // --- 5. Orbiting Kinetic Energy Streams (Multi-Packet Photons) ---
      // Primary Comet 1: 120 FPS Video/Audio Downlink Stream
      const comet1T = (now * 0.00032) % (Math.PI * 2);
      const comet1Pos = getPoint(comet1T);

      // Primary Comet 2: Real-time Input Control Uplink Stream
      const comet2T = (now * 0.00028 + Math.PI) % (Math.PI * 2);
      const comet2Pos = getPoint(comet2T);

      // Multi-Speed High-Frequency Micro Data Blips
      const microPulses = [
        { t: (now * 0.00068) % (Math.PI * 2), color: '#38BDF8', size: 1.8 },
        { t: (now * 0.00062 + Math.PI * 0.5) % (Math.PI * 2), color: '#22C55E', size: 1.8 },
        { t: (now * 0.00054 + Math.PI * 1.2) % (Math.PI * 2), color: '#F59E0B', size: 1.6 },
        { t: (now * 0.00078 + Math.PI * 1.7) % (Math.PI * 2), color: '#FFFFFF', size: 2.0 }
      ];
      microPulses.forEach(mp => {
        const p = getPoint(mp.t);
        ctx.beginPath();
        ctx.arc(p.x, p.y, mp.size, 0, Math.PI * 2);
        ctx.fillStyle = mp.color;
        ctx.shadowColor = mp.color;
        ctx.shadowBlur = 6;
        ctx.fill();
      });
      ctx.shadowBlur = 0;

      // Trailing Sub-Photon Clusters for Comet 1
      const subOffsets1 = [-0.045, -0.095, -0.15];
      subOffsets1.forEach((offset, idx) => {
        const spPos = getPoint((comet1T + offset + Math.PI * 4) % (Math.PI * 2));
        ctx.beginPath();
        ctx.arc(spPos.x, spPos.y, 2.2 - idx * 0.5, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(56, 189, 248, ${0.75 - idx * 0.22})`;
        ctx.fill();
      });

      // Trailing Sub-Photon Clusters for Comet 2
      const subOffsets2 = [-0.045, -0.095, -0.15];
      subOffsets2.forEach((offset, idx) => {
        const spPos = getPoint((comet2T + offset + Math.PI * 4) % (Math.PI * 2));
        ctx.beginPath();
        ctx.arc(spPos.x, spPos.y, 2.2 - idx * 0.5, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(34, 197, 94, ${0.75 - idx * 0.22})`;
        ctx.fill();
      });

      // --- 6. Discrete Telemetry Blocks / Data Cells along Loop (240 Segments) ---
      for (let i = 0; i < NUM_BLOCKS; i++) {
        const bt = (i / NUM_BLOCKS) * Math.PI * 2;
        const bp = getPoint(bt);
        const btheta = getTangentAngle(bt);

        let blkW = 7.2;
        let blkH = 4.6;
        let blkAlpha = 0.38 + 0.14 * Math.sin(i * 3.7 + now * 0.001);

        // Distance from pointer (magnetic hover expansion)
        if (landingPointer.active) {
          const dPtr = Math.hypot(bp.x - landingPointer.x, bp.y - landingPointer.y);
          if (dPtr < 140) {
            const boost = (1 - dPtr / 140);
            blkW += boost * 4.2;
            blkH += boost * 3.2;
            blkAlpha = Math.min(1.0, blkAlpha + boost * 0.55);
          }
        }

        // Distance from ripples (shockwave excitation)
        for (let ri = 0; ri < ripples.length; ri++) {
          const rp = ripples[ri];
          const dR = Math.hypot(bp.x - rp.x, bp.y - rp.y);
          if (Math.abs(dR - rp.r) < 32) {
            const waveBoost = (1 - Math.abs(dR - rp.r) / 32) * (rp.alpha / 0.85);
            blkW += waveBoost * 4.5;
            blkH += waveBoost * 3.6;
            blkAlpha = Math.min(1.0, blkAlpha + waveBoost * 0.65);
          }
        }

        // Trail from Comet 1 (Video Stream)
        const diff1 = (bt - comet1T + Math.PI * 4) % (Math.PI * 2);
        if (diff1 > (Math.PI * 2 - 0.52) || diff1 < 0.02) {
          const tailProgress = diff1 < 0.02 ? 1.0 : (1 - (Math.PI * 2 - diff1) / 0.52);
          blkW += tailProgress * 3.2;
          blkH += tailProgress * 2.2;
          blkAlpha = Math.min(1.0, blkAlpha + tailProgress * 0.70);
        }

        // Trail from Comet 2 (Input Stream)
        const diff2 = (bt - comet2T + Math.PI * 4) % (Math.PI * 2);
        if (diff2 > (Math.PI * 2 - 0.52) || diff2 < 0.02) {
          const tailProgress = diff2 < 0.02 ? 1.0 : (1 - (Math.PI * 2 - diff2) / 0.52);
          blkW += tailProgress * 3.2;
          blkH += tailProgress * 2.2;
          blkAlpha = Math.min(1.0, blkAlpha + tailProgress * 0.70);
        }

        // Color coding by topological position:
        const normX = (bp.x - cx) / scaleX;
        let colorStr = '';
        if (normX < -0.15) {
          // Host cluster: Amber (#F59E0B) to Emerald (#22C55E)
          const mix = (-normX - 0.15) / 0.85;
          const r = Math.round(245 * (1 - mix * 0.5) + 34 * (mix * 0.5));
          const g = Math.round(158 * (1 - mix * 0.5) + 197 * (mix * 0.5));
          const b = Math.round(11 * (1 - mix * 0.5) + 94 * (mix * 0.5));
          colorStr = `rgba(${r}, ${g}, ${b}, ${blkAlpha})`;
        } else if (normX > 0.15) {
          // Client cluster: Sky Cyan (#38BDF8) to Electric Slate/Indigo (#818CF8)
          const mix = (normX - 0.15) / 0.85;
          const r = Math.round(56 * (1 - mix) + 129 * mix);
          const g = Math.round(189 * (1 - mix) + 140 * mix);
          const b = Math.round(248 * (1 - mix) + 248 * mix);
          colorStr = `rgba(${r}, ${g}, ${b}, ${blkAlpha})`;
        } else {
          // Relay Nexus Core: Luminous Cyan-White
          colorStr = `rgba(226, 232, 240, ${blkAlpha * 1.15})`;
        }

        ctx.save();
        ctx.translate(bp.x, bp.y);
        ctx.rotate(btheta);
        ctx.fillStyle = colorStr;
        ctx.beginPath();
        if (ctx.roundRect) {
          ctx.roundRect(-blkW / 2, -blkH / 2, blkW, blkH, 1.2);
        } else {
          ctx.rect(-blkW / 2, -blkH / 2, blkW, blkH);
        }
        ctx.fill();
        ctx.restore();
      }

      // --- 7. Draw Comet Heads with Radial Bloom & Optical Flares ---
      function drawPhotonHead(pos, rColor, glowColor, flareColor) {
        // Multi-stage radial bloom halo
        const g = ctx.createRadialGradient(pos.x, pos.y, 0, pos.x, pos.y, 46);
        g.addColorStop(0, 'rgba(255, 255, 255, 0.98)');
        g.addColorStop(0.2, glowColor);
        g.addColorStop(0.55, flareColor);
        g.addColorStop(1, 'rgba(0, 0, 0, 0)');
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, 46, 0, Math.PI * 2);
        ctx.fill();

        // Intense core dot
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, 3.2, 0, Math.PI * 2);
        ctx.fillStyle = '#FFFFFF';
        ctx.shadowColor = glowColor;
        ctx.shadowBlur = 14;
        ctx.fill();
        ctx.shadowBlur = 0;

        // Subtle optical flare crosshair
        ctx.beginPath();
        ctx.moveTo(pos.x - 20, pos.y);
        ctx.lineTo(pos.x + 20, pos.y);
        ctx.moveTo(pos.x, pos.y - 20);
        ctx.lineTo(pos.x, pos.y + 20);
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)';
        ctx.lineWidth = 0.9;
        ctx.stroke();
      }

      // Comet 1: Cyan / Electric Blue (Video Stream 120 FPS)
      drawPhotonHead(comet1Pos, '#FFFFFF', 'rgba(56, 189, 248, 0.85)', 'rgba(56, 189, 248, 0.22)');
      // Comet 2: Amber / Emerald (Input Stream)
      drawPhotonHead(comet2Pos, '#FFFFFF', 'rgba(245, 158, 11, 0.85)', 'rgba(34, 197, 94, 0.22)');

      // --- 8. Center Relay Hub Nexus (Rotating Holographic Gimbal Reticle) ---
      const dC1 = Math.hypot(comet1Pos.x - cx, comet1Pos.y - cy);
      const dC2 = Math.hypot(comet2Pos.x - cx, comet2Pos.y - cy);
      const isNexusActive = (dC1 < 42 || dC2 < 42);
      const nexusAlpha = isNexusActive ? 0.65 : 0.22;

      // Optical flare pulse when comet crosses singularity
      if (isNexusActive) {
        const gBurst = ctx.createRadialGradient(cx, cy, 0, cx, cy, 84);
        gBurst.addColorStop(0, 'rgba(255, 255, 255, 0.40)');
        gBurst.addColorStop(0.35, 'rgba(56, 189, 248, 0.22)');
        gBurst.addColorStop(1, 'rgba(0, 0, 0, 0)');
        ctx.fillStyle = gBurst;
        ctx.beginPath();
        ctx.arc(cx, cy, 84, 0, Math.PI * 2);
        ctx.fill();
      }

      // Inner Rotating Ring (Clockwise)
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(now * 0.0008);
      ctx.beginPath();
      ctx.arc(0, 0, 16, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(56, 189, 248, ${nexusAlpha * 1.2})`;
      ctx.lineWidth = 0.9;
      ctx.stroke();
      for (let a = 0; a < 4; a++) {
        const ang = (a * Math.PI) / 2;
        ctx.beginPath();
        ctx.moveTo(Math.cos(ang) * 13, Math.sin(ang) * 13);
        ctx.lineTo(Math.cos(ang) * 19, Math.sin(ang) * 19);
        ctx.strokeStyle = `rgba(255, 255, 255, ${nexusAlpha * 0.9})`;
        ctx.lineWidth = 1;
        ctx.stroke();
      }
      ctx.restore();

      // Outer Rotating Dashed Ring (Counter-Clockwise)
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(-now * 0.0005);
      ctx.setLineDash([4, 6]);
      ctx.beginPath();
      ctx.arc(0, 0, 32, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(255, 255, 255, ${nexusAlpha * 0.8})`;
      ctx.lineWidth = 0.7;
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.restore();

      // Cardinal Reticle Crosshair Spikes
      ctx.beginPath();
      ctx.moveTo(cx - 44, cy); ctx.lineTo(cx - 24, cy);
      ctx.moveTo(cx + 24, cy); ctx.lineTo(cx + 44, cy);
      ctx.moveTo(cx, cy - 44); ctx.lineTo(cx, cy - 24);
      ctx.moveTo(cx, cy + 24); ctx.lineTo(cx, cy + 44);
      ctx.strokeStyle = `rgba(56, 189, 248, ${nexusAlpha * 0.9})`;
      ctx.lineWidth = 1;
      ctx.stroke();

      // Center Singularity Core Pip
      ctx.beginPath();
      ctx.arc(cx, cy, isNexusActive ? 3.5 : 2.2, 0, Math.PI * 2);
      ctx.fillStyle = isNexusActive ? '#FFFFFF' : 'rgba(56, 189, 248, 0.9)';
      if (isNexusActive) {
        ctx.shadowColor = '#38BDF8';
        ctx.shadowBlur = 12;
      }
      ctx.fill();
      ctx.shadowBlur = 0;

      // Nexus Telemetry Label
      ctx.font = '7.5px Consolas, monospace';
      ctx.fillStyle = `rgba(255, 255, 255, ${nexusAlpha * 0.85})`;
      ctx.fillText('NEXUS // RELAY', cx - 28, cy + 46);

      // --- 9. Node Milestone Brackets at Outer Vertices ---
      // Left Host Station Milestone (t = π)
      const pHost = getPoint(Math.PI);
      ctx.save();
      ctx.font = '8px Consolas, monospace';
      ctx.fillStyle = 'rgba(245, 158, 11, 0.45)';
      ctx.fillText('NODE-01 // HOST WORKSTATION', pHost.x - 128, pHost.y - 12);
      ctx.strokeStyle = 'rgba(245, 158, 11, 0.35)';
      ctx.lineWidth = 0.8;
      const bx = pHost.x - 8, by = pHost.y - 8, bw = 16, bh = 16;
      ctx.beginPath();
      ctx.moveTo(bx, by + 4); ctx.lineTo(bx, by); ctx.lineTo(bx + 4, by);
      ctx.moveTo(bx + bw - 4, by); ctx.lineTo(bx + bw, by); ctx.lineTo(bx + bw, by + 4);
      ctx.moveTo(bx, by + bh - 4); ctx.lineTo(bx, by + bh); ctx.lineTo(bx + 4, by + bh);
      ctx.moveTo(bx + bw - 4, by + bh); ctx.lineTo(bx + bw, by + bh); ctx.lineTo(bx + bw, by + bh - 4);
      ctx.stroke();
      ctx.restore();

      // Right Client Cockpit Milestone (t = 0)
      const pClient = getPoint(0);
      ctx.save();
      ctx.font = '8px Consolas, monospace';
      ctx.fillStyle = 'rgba(56, 189, 248, 0.45)';
      ctx.fillText('NODE-02 // CLIENT COCKPIT', pClient.x + 16, pClient.y - 12);
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.35)';
      ctx.lineWidth = 0.8;
      const rx = pClient.x - 8, ry = pClient.y - 8, rw = 16, rh = 16;
      ctx.beginPath();
      ctx.moveTo(rx, ry + 4); ctx.lineTo(rx, ry); ctx.lineTo(rx + 4, ry);
      ctx.moveTo(rx + rw - 4, ry); ctx.lineTo(rx + rw, ry); ctx.lineTo(rx + rw, ry + 4);
      ctx.moveTo(rx, ry + rh - 4); ctx.lineTo(rx, ry + rh); ctx.lineTo(rx + 4, ry + rh);
      ctx.moveTo(rx + rw - 4, ry + rh); ctx.lineTo(rx + rw, ry + rh); ctx.lineTo(rx + rw, ry + rh - 4);
      ctx.stroke();
      ctx.restore();

      // --- 10. Interactive Signal Vector Tether to Cursor ---
      if (landingPointer.active) {
        let minDistSq = Infinity;
        let nearestP = null;
        const testSteps = 60;
        for (let ts = 0; ts < testSteps; ts++) {
          const tt = (ts / testSteps) * Math.PI * 2;
          const tp = getPoint(tt);
          const dSq = (tp.x - landingPointer.x) ** 2 + (tp.y - landingPointer.y) ** 2;
          if (dSq < minDistSq) {
            minDistSq = dSq;
            nearestP = tp;
          }
        }
        const dist = Math.sqrt(minDistSq);
        if (dist < 180 && nearestP) {
          const tetherAlpha = (1 - dist / 180) * 0.35;
          ctx.beginPath();
          ctx.moveTo(landingPointer.x, landingPointer.y);
          ctx.lineTo(nearestP.x, nearestP.y);
          ctx.strokeStyle = `rgba(56, 189, 248, ${tetherAlpha})`;
          ctx.lineWidth = 0.75;
          ctx.setLineDash([2, 4]);
          ctx.stroke();
          ctx.setLineDash([]);

          ctx.beginPath();
          ctx.arc(nearestP.x, nearestP.y, 5, 0, Math.PI * 2);
          ctx.strokeStyle = `rgba(56, 189, 248, ${tetherAlpha * 1.5})`;
          ctx.lineWidth = 1;
          ctx.stroke();

          ctx.font = '7px Consolas, monospace';
          ctx.fillStyle = `rgba(56, 189, 248, ${tetherAlpha * 1.8})`;
          ctx.fillText(`LOCK // ${Math.round(dist)}px`, landingPointer.x + 10, landingPointer.y - 10);
        }
      }

      // --- 11. Ambient Quantum Dust & Interconnected Constellations ---
      dustParticles.forEach(p => {
        p.x += p.vx;
        p.y += p.vy;
        if (p.y < 0) { p.y = h; p.x = Math.random() * w; }
        if (p.x < 0) p.x = w;
        if (p.x > w) p.x = 0;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        let col = `rgba(56, 189, 248, ${p.alpha})`;
        if (p.hue === 150) col = `rgba(34, 197, 94, ${p.alpha})`;
        else if (p.hue === 38) col = `rgba(245, 158, 11, ${p.alpha})`;
        ctx.fillStyle = col;
        ctx.fill();
      });

      // Micro-constellation Webbing between nearby dust
      for (let di = 0; di < dustParticles.length; di++) {
        const p1 = dustParticles[di];
        for (let dj = di + 1; dj < dustParticles.length; dj++) {
          const p2 = dustParticles[dj];
          const dx = p1.x - p2.x;
          const dy = p1.y - p2.y;
          const dSq = dx * dx + dy * dy;
          if (dSq < 4225) { // 65^2
            const d = Math.sqrt(dSq);
            const alpha = (1 - d / 65) * 0.12 * Math.min(p1.alpha, p2.alpha);
            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.strokeStyle = `rgba(56, 189, 248, ${alpha})`;
            ctx.lineWidth = 0.6;
            ctx.stroke();
          }
        }
      }

      // --- 12. Dual Chromatic Shockwave Ripples on Click ---
      for (let ri = ripples.length - 1; ri >= 0; ri--) {
        const rp = ripples[ri];
        rp.r += dt * 380;
        rp.alpha *= 0.93;
        if (rp.r > rp.maxR || rp.alpha < 0.02) {
          ripples.splice(ri, 1);
          continue;
        }
        // Primary Ring (Cyan)
        ctx.beginPath();
        ctx.arc(rp.x, rp.y, rp.r, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(56, 189, 248, ${rp.alpha * 0.75})`;
        ctx.lineWidth = 1.6;
        ctx.shadowColor = '#38BDF8';
        ctx.shadowBlur = 10;
        ctx.stroke();
        ctx.shadowBlur = 0;

        // Secondary Outer Harmonic Ring (Emerald)
        ctx.beginPath();
        ctx.arc(rp.x, rp.y, Math.max(0, rp.r - 8), 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(34, 197, 94, ${rp.alpha * 0.45})`;
        ctx.lineWidth = 0.8;
        ctx.stroke();
      }

      landingCanvasAnimId = requestAnimationFrame(render);
    }

    landingCanvasInited = true;
    landingCanvasAnimId = requestAnimationFrame(render);

    initLandingCockpit();
  }

  // --- LIVE HERO DIRECT CONNECT COCKPIT (100% REAL FUNCTIONS) ---
  function initLandingCockpit() {
    const tabInstant = document.getElementById('btnCockpitTabInstant');
    const tabUnattended = document.getElementById('btnCockpitTabUnattended');
    const formInstant = document.getElementById('landingQuickConnectForm');
    const paneUnattended = document.getElementById('heroUnattendedPane');
    const inputRoom = document.getElementById('landingRoomInput');
    const inputPin = document.getElementById('landingPinInput');
    const btnDemo = document.getElementById('btnHeroDemoRoom');
    const btnTogglePin = document.getElementById('btnToggleHeroPin');
    const btnLoginJump = document.getElementById('btnHeroLoginJump');
    const pingReadout = document.getElementById('cockpitPingReadout');
    const relayStatusText = document.getElementById('heroRelayStatusText');

    // 1. Mode Tab Switching
    if (tabInstant && tabUnattended && formInstant && paneUnattended) {
      tabInstant.onclick = () => {
        tabInstant.classList.add('on');
        tabUnattended.classList.remove('on');
        formInstant.classList.remove('hidden');
        paneUnattended.classList.add('hidden');
        inputRoom?.focus();
      };

      tabUnattended.onclick = () => {
        tabUnattended.classList.add('on');
        tabInstant.classList.remove('on');
        paneUnattended.classList.remove('hidden');
        formInstant.classList.add('hidden');
      };
    }

    // 2. Demo Room ID Auto-fill
    if (btnDemo && inputRoom) {
      btnDemo.onclick = () => {
        inputRoom.value = 'RD-8924';
        inputRoom.dispatchEvent(new Event('input', { bubbles: true }));
        inputPin?.focus();
        showToast(t('toast.demo_room_filled'), 'info');
      };
    }

    // 3. Show/Hide PIN Password Toggle
    if (btnTogglePin && inputPin) {
      btnTogglePin.onclick = () => {
        const eyeSvg = document.getElementById('heroEyeSvg');
        const txtEye = document.getElementById('txtHeroEye');
        if (inputPin.type === 'password') {
          inputPin.type = 'text';
          if (txtEye) txtEye.textContent = 'Ẩn';
          else btnTogglePin.textContent = 'Ẩn';
          if (eyeSvg) {
            eyeSvg.innerHTML = '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line>';
          }
        } else {
          inputPin.type = 'password';
          if (txtEye) txtEye.textContent = 'Hiện';
          else btnTogglePin.textContent = 'Hiện';
          if (eyeSvg) {
            eyeSvg.innerHTML = '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle>';
          }
        }
      };
    }

    // 4. Jump to Login
    if (btnLoginJump) {
      btnLoginJump.onclick = () => {
        document.getElementById('btnLandingStart')?.click();
      };
    }

    // 5. Jump Buttons in Hero Left Column
    const btnQuickJump = document.getElementById('btnLandingQuickJump');
    if (btnQuickJump && inputRoom) {
      btnQuickJump.onclick = () => {
        tabInstant?.click();
        inputRoom.focus();
        inputRoom.select();
      };
    }

    const btnDlJump = document.getElementById('btnLandingDownloadJump');
    if (btnDlJump) {
      btnDlJump.onclick = () => {
        const dl = document.getElementById('landingDownloads');
        if (dl) dl.scrollIntoView({ behavior: 'smooth' });
      };
    }

    // 6. REAL Live Relay Health & Latency Probe
    async function probeRelayLatency() {
      if (currentView !== 'landing') return;
      try {
        const t0 = performance.now();
        const res = await fetch('/api/health', { cache: 'no-store' });
        const t1 = performance.now();
        if (res.ok) {
          const data = await res.json().catch(() => null);
          if (data && data.offline) {
            if (pingReadout) pingReadout.textContent = 'RTT: --';
            if (relayStatusText) relayStatusText.textContent = 'Relay Tunnel: Đang tắt (Offline)';
            return;
          }
          const rtt = Math.max(0.8, (t1 - t0)).toFixed(1);
          if (pingReadout) {
            pingReadout.textContent = `RTT: ${rtt}ms`;
          }
          if (relayStatusText) {
            relayStatusText.textContent = `Relay Tunnel: Sẵn sàng (${rtt}ms)`;
          }
        } else {
          if (pingReadout) pingReadout.textContent = 'RTT: --';
          if (relayStatusText) relayStatusText.textContent = 'Relay Tunnel: Đang tắt (Offline)';
        }
      } catch {
        if (pingReadout) pingReadout.textContent = 'RTT: --';
      }
    }

    // Initial probe and recurring probe every 3s
    probeRelayLatency();
    setInterval(probeRelayLatency, 3000);
  }

  function startLandingCanvas() {
    if (!landingCanvasInited) {
      initLandingCanvas();
    } else if (!landingCanvasAnimId) {
      landingCanvasAnimId = requestAnimationFrame(() => {
        if (currentView === 'landing' && landingCanvas) {
          initLandingCanvas();
        }
      });
    }
  }

  function stopLandingCanvas() {
    if (landingCanvasAnimId) {
      cancelAnimationFrame(landingCanvasAnimId);
      landingCanvasAnimId = null;
      landingCanvasInited = false;
    }
  }

  function updateRoStatus() {
    if (!roStatus) return;
    if (currentView === 'landing') {
      roStatus.textContent = t('ro.landing');
    } else if (currentView === 'auth') {
      roStatus.textContent = t('ro.auth');
    } else if (currentView === 'dashboard') {
      roStatus.textContent = t('ro.dashboard');
    } else if (currentView === 'remote') {
      roStatus.textContent = isConnected
        ? `${currentRoom} // ${t('ro.connected')}`
        : (currentRoom ? `${currentRoom} // ${t('ro.connecting')}` : t('ro.disconnected'));
    } else if (currentView === 'files') {
      roStatus.textContent = isConnected ? `${currentRoom} // ${t('nav.files').toUpperCase()}` : t('ro.disconnected');
    } else if (currentView === 'terminal') {
      roStatus.textContent = isConnected ? `${currentRoom} // ${t('nav.terminal').toUpperCase()}` : t('ro.disconnected');
    } else if (currentView === 'tasks') {
      roStatus.textContent = isConnected ? `${currentRoom} // ${t('nav.tasks').toUpperCase()}` : t('ro.disconnected');
    } else if (currentView === 'audit') {
      roStatus.textContent = isConnected ? `${currentRoom} // ${t('nav.audit').toUpperCase()}` : t('nav.audit').toUpperCase();
    }

    if (roTr) {
      const showTr = isConnected && (currentView === 'remote' || currentView === 'terminal' || currentView === 'files' || currentView === 'tasks');
      roTr.style.display = showTr ? '' : 'none';
    }
  }

  function switchView(view, updateUrl = true) {
    currentView = view;
    landingSection?.classList.add('hidden');
    authSection.classList.add('hidden');
    dashboardSection.classList.add('hidden');
    remoteSection.classList.add('hidden');
    terminalSection.classList.add('hidden');
    tasksSection.classList.add('hidden');
    filesSection.classList.add('hidden');
    auditSection.classList.add('hidden');

    if (view === 'remote') {
      document.body.classList.add('remote-active');
      const isMobileRemote = window.innerWidth <= 900 || (window.innerHeight <= 520 && window.innerWidth <= 1024);
      if (btnMobileImmersiveExit && isMobileRemote) {
        btnMobileImmersiveExit.classList.remove('hidden');
      } else if (btnMobileImmersiveExit) {
        btnMobileImmersiveExit.classList.add('hidden');
      }
    } else {
      document.body.classList.remove('remote-active');
      if (btnMobileImmersiveExit) btnMobileImmersiveExit.classList.add('hidden');
      if (mobileQuickKeysBar) mobileQuickKeysBar.classList.add('hidden');
      if (btnMobileQuickKeysToggle) btnMobileQuickKeysToggle.classList.remove('active');
    }

    mainNav.querySelectorAll('button').forEach(btn => {
      const isTarget = btn.dataset.view === view;
      btn.classList.toggle('on', isTarget);
      btn.setAttribute('aria-selected', isTarget ? 'true' : 'false');
    });
    placeIndicator(mainNav);

    if (view === 'landing') {
      landingSection?.classList.remove('hidden');
      startLandingCanvas();
    } else {
      stopLandingCanvas();
      if (view === 'auth') {
        authSection.classList.remove('hidden');
        setTimeout(() => placeIndicator(authTabs), 30);
      } else if (view === 'dashboard') {
        dashboardSection.classList.remove('hidden');
        loadDeviceFleet();
      } else if (view === 'remote') {
        remoteSection.classList.remove('hidden');
        resetDeckIdle();
      } else if (view === 'files') {
        filesSection.classList.remove('hidden');
        if (isConnected) requestBrowsePath(remoteCurrentPath || '');
      } else if (view === 'terminal') {
        terminalSection.classList.remove('hidden');
        updateTerminalStatusBadge();
        setTimeout(() => terminalCmdInput?.focus(), 50);
      } else if (view === 'tasks') {
        tasksSection.classList.remove('hidden');
        if (isConnected) requestTelemetryAndTasks();
      } else if (view === 'audit') {
        auditSection.classList.remove('hidden');
        loadAuditLogs();
      }
    }

    updateRoStatus();
    const connOverlay = document.getElementById('canvasConnectingOverlay');
    if (connOverlay) connOverlay.classList.remove('hidden');

    if (updateUrl) {
      syncUrlWithState(false);
    }
    if (typeof updateRemoteSessionTabs === 'function') {
      updateRemoteSessionTabs();
    }
  }

  // Navigation Click Handler
  mainNav.addEventListener('click', (e) => {
    const btn = e.target.closest('button');
    if (!btn) return;
    const view = btn.dataset.view;
    if (view === 'landing') {
      switchView('landing', true);
      return;
    }
    if (view !== 'auth' && (!authToken || !currentUser)) {
      sessionStorage.setItem('meikova_relay_pending_route', view);
      switchView('auth', true);
      return;
    }
    switchView(view, true);
  });

  // Standalone PWA detection and styling sync
  function syncStandaloneMode() {
    const isStandalone = window.navigator.standalone === true || window.matchMedia('(display-mode: standalone)').matches;
    if (isStandalone) {
      document.documentElement.classList.add('is-pwa-standalone');
      document.body.classList.add('is-pwa-standalone');
    }
  }
  syncStandaloneMode();

  // Nav placement sync: on mobile, attach #mainNav to document.body to prevent WebKit containing-block clipping
  function syncNavPlacement() {
    syncStandaloneMode();
    const isMobile = window.innerWidth <= 767;
    const nav = document.getElementById('mainNav');
    const topbar = document.querySelector('.topbar');
    if (btnMobileImmersiveExit && currentView === 'remote') {
      const isMobileRemote = window.innerWidth <= 900 || (window.innerHeight <= 520 && window.innerWidth <= 1024);
      btnMobileImmersiveExit.classList.toggle('hidden', !isMobileRemote);
    }
    if (!nav || !topbar) return;
    if (isMobile && nav.parentElement === topbar) {
      document.body.appendChild(nav);
    } else if (!isMobile && nav.parentElement === document.body) {
      const topbarRight = topbar.querySelector('.topbar-right');
      if (topbarRight) {
        topbar.insertBefore(nav, topbarRight);
      } else {
        topbar.appendChild(nav);
      }
    }
  }
  window.addEventListener('resize', syncNavPlacement);
  window.addEventListener('orientationchange', () => setTimeout(syncNavPlacement, 100));
  syncNavPlacement();

  // --- LANDING INTERACTIONS ---
  btnLandingStart?.addEventListener('click', () => {
    if (authToken && currentUser) {
      switchView('dashboard', true);
    } else {
      switchView('auth', true);
    }
  });

  btnNavLogin?.addEventListener('click', () => {
    switchView('auth', true);
  });

  brandLogo?.addEventListener('click', (e) => {
    e.preventDefault();
    switchView('landing', true);
  });

  btnLandingQuickJump?.addEventListener('click', () => {
    const qcSec = document.getElementById('landingQuickConnectSection');
    if (qcSec) {
      qcSec.scrollIntoView({ behavior: 'smooth' });
      landingRoomInput?.focus();
    } else {
      quickConnectModal?.classList.remove('hidden');
    }
  });

  btnLandingDownloadJump?.addEventListener('click', () => {
    const dlSec = document.getElementById('landingDownloads');
    dlSec?.scrollIntoView({ behavior: 'smooth' });
  });

  landingQuickConnectForm?.addEventListener('submit', (e) => {
    e.preventDefault();
    const room = landingRoomInput?.value.trim();
    const pin = landingPinInput?.value.trim() || '';
    if (!room) return;
    currentRoom = room;
    currentPin = pin;
    if (pin) sessionStorage.setItem('meikova_relay_pin_' + room, pin);
    startRemoteSession(defaultWsUrl, room, pin);
  });

  btnLandingDlExe?.addEventListener('click', downloadDesktopExe);
  btnLandingDlBat?.addEventListener('click', downloadHostInstaller);

  // Update PowerShell snippet with live origin
  const ps1CodeSnippet = document.getElementById('ps1CodeSnippet');
  if (ps1CodeSnippet) {
    const origin = window.location.origin;
    ps1CodeSnippet.textContent = `iwr -useb ${origin}/api/download/MeikovaRelayHost.exe -OutFile "$env:TEMP\\MeikovaRelayHost.exe"; Start-Process "$env:TEMP\\MeikovaRelayHost.exe"`;
  }

  btnLandingCopyPs1?.addEventListener('click', async () => {
    const code = document.getElementById('ps1CodeSnippet')?.textContent || '';
    if (code) {
      try {
        await navigator.clipboard.writeText(code);
        showToast(typeof t === 'function' ? t('landing.toast_copied') : 'Đã sao chép lệnh PowerShell vào clipboard!');
        btnLandingCopyPs1.classList.add('copied');
        const copyBtnText = document.getElementById('copyBtnText');
        const copySvgIcon = document.getElementById('copySvgIcon');
        if (copyBtnText) copyBtnText.textContent = typeof t === 'function' ? t('landing.dl_ps1_copied') : 'Đã chép!';
        if (copySvgIcon) copySvgIcon.innerHTML = '<polyline points="20 6 9 17 4 12"></polyline>';
        setTimeout(() => {
          btnLandingCopyPs1.classList.remove('copied');
          if (copyBtnText) copyBtnText.textContent = typeof t === 'function' ? t('landing.dl_ps1_copy') : 'Sao chép';
          if (copySvgIcon) copySvgIcon.innerHTML = '<rect x="9" y="9" width="13" height="13" rx="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>';
        }, 2000);
      } catch {
        showToast(t('toast.copy_failed'), 'error');
      }
    }
  });

  // Download Hub Platform Filter Switcher
  const dlPlatformSeg = document.getElementById('dlPlatformSeg');
  const dlPanes = {
    windows: document.getElementById('dlPaneWindows'),
    linux: document.getElementById('dlPaneLinux'),
    macos: document.getElementById('dlPaneMacos'),
    web: document.getElementById('dlPaneWeb')
  };

  dlPlatformSeg?.addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-dl-tab]');
    if (!btn) return;
    const tab = btn.dataset.dlTab;
    dlPlatformSeg.querySelectorAll('button').forEach(b => {
      const isTarget = b === btn;
      b.classList.toggle('on', isTarget);
      b.setAttribute('aria-selected', isTarget ? 'true' : 'false');
    });
    placeIndicator(dlPlatformSeg);

    Object.entries(dlPanes).forEach(([k, pane]) => {
      if (pane) pane.classList.toggle('hidden', k !== tab);
    });
  });

  // Linux & macOS Snippets Origin Setup
  const linuxCodeSnippet = document.getElementById('linuxCodeSnippet');
  if (linuxCodeSnippet) {
    linuxCodeSnippet.textContent = `curl -sSL ${window.location.origin}/api/download/install-linux.sh | bash`;
  }
  const macosCodeSnippet = document.getElementById('macosCodeSnippet');
  if (macosCodeSnippet) {
    macosCodeSnippet.textContent = `curl -sSL ${window.location.origin}/api/download/install-macos.sh | bash`;
  }

  // Linux Copy Button
  const btnLandingCopyLinux = document.getElementById('btnLandingCopyLinux');
  btnLandingCopyLinux?.addEventListener('click', async () => {
    const code = linuxCodeSnippet?.textContent || '';
    if (code) {
      try {
        await navigator.clipboard.writeText(code);
        showToast(typeof t === 'function' ? t('landing.toast_copied') : 'Đã sao chép lệnh cài đặt Linux!');
        btnLandingCopyLinux.classList.add('copied');
        const copyLinuxBtnText = document.getElementById('copyLinuxBtnText');
        if (copyLinuxBtnText) copyLinuxBtnText.textContent = typeof t === 'function' ? t('landing.dl_ps1_copied') : 'Đã chép!';
        setTimeout(() => {
          btnLandingCopyLinux.classList.remove('copied');
          if (copyLinuxBtnText) copyLinuxBtnText.textContent = typeof t === 'function' ? t('landing.dl_linux_sh_copy') : 'Sao chép lệnh Linux';
        }, 2000);
      } catch {
        showToast(t('toast.copy_failed'), 'error');
      }
    }
  });

  // macOS Copy Button
  const btnLandingCopyMacos = document.getElementById('btnLandingCopyMacos');
  btnLandingCopyMacos?.addEventListener('click', async () => {
    const code = macosCodeSnippet?.textContent || '';
    if (code) {
      try {
        await navigator.clipboard.writeText(code);
        showToast(typeof t === 'function' ? t('landing.toast_copied') : 'Đã sao chép lệnh cài đặt macOS!');
        btnLandingCopyMacos.classList.add('copied');
        const copyMacosBtnText = document.getElementById('copyMacosBtnText');
        if (copyMacosBtnText) copyMacosBtnText.textContent = typeof t === 'function' ? t('landing.dl_ps1_copied') : 'Đã chép!';
        setTimeout(() => {
          btnLandingCopyMacos.classList.remove('copied');
          if (copyMacosBtnText) copyMacosBtnText.textContent = typeof t === 'function' ? t('landing.dl_macos_sh_copy') : 'Sao chép lệnh macOS';
        }, 2000);
      } catch {
        showToast(t('toast.copy_failed'), 'error');
      }
    }
  });

  // Direct Package Download Handlers
  document.getElementById('btnLandingDlLinuxDeb')?.addEventListener('click', () => {
    window.location.href = '/api/download/meikova-relay-host_amd64.deb';
  });
  document.getElementById('btnLandingDlLinuxTar')?.addEventListener('click', () => {
    window.location.href = '/api/download/meikova-relay-host-linux-x64.tar.gz';
  });
  document.getElementById('btnLandingDlMacosTar')?.addEventListener('click', () => {
    window.location.href = '/api/download/meikova-relay-host-macos.tar.gz';
  });
  document.getElementById('btnLandingDlLinuxUnit')?.addEventListener('click', () => {
    window.location.href = '/api/download/meikova-relay.service';
  });
  document.getElementById('btnLandingDlZip')?.addEventListener('click', () => {
    window.location.href = '/api/download/agent-package.zip';
  });
  document.getElementById('btnLandingDlMacosPlist')?.addEventListener('click', () => {
    window.location.href = '/api/download/com.meikova.relay.plist';
  });

  // --- AUTHENTICATION ---
  authTabs.addEventListener('click', (e) => {
    const btn = e.target.closest('button');
    if (!btn) return;
    authTabs.querySelectorAll('button').forEach(b => b.classList.remove('on'));
    btn.classList.add('on');
    placeIndicator(authTabs);

    authMode = btn.dataset.authMode;
    const authBtnKey = authMode === 'login' ? 'auth.btn_login' : 'auth.btn_register';
    btnSubmitAuth.setAttribute('data-i18n', authBtnKey);
    btnSubmitAuth.textContent = t(authBtnKey);
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
        handleAuthSuccess(res);
      } else {
        authError.textContent = res.message || 'Thao tác không thành công';
        authError.classList.remove('hidden');
      }
    } catch (err) {
      authError.textContent = `Lỗi kết nối: ${err.message}`;
      authError.classList.remove('hidden');
    }
  });

  // --- SESSION ACTIVITY & INACTIVITY TIMEOUT ENGINE (SLIDING SESSION) ---
  let timeoutRemoteMin = parseInt(localStorage.getItem('meikova_relay_timeout_remote_min') || '15', 10);
  if (isNaN(timeoutRemoteMin) || timeoutRemoteMin < 1) timeoutRemoteMin = 15;

  let timeoutGlobalMin = parseInt(localStorage.getItem('meikova_relay_timeout_global_min') || '30', 10);
  if (isNaN(timeoutGlobalMin) || timeoutGlobalMin < 2) timeoutGlobalMin = 30;

  let lastRemoteActivity = Date.now();
  let lastGlobalActivity = Date.now();
  let lastTokenRefreshTime = Date.now();
  let isRefreshingToken = false;

  // 1. Sliding Token Refresh (Keep session alive during active usage)
  async function refreshAuthToken() {
    if (!authToken || isRefreshingToken) return;
    isRefreshingToken = true;
    try {
      const res = await fetch('/api/auth/refresh', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        }
      });
      if (res.ok) {
        const data = await res.json();
        if (data.success && data.token) {
          authToken = data.token;
          localStorage.setItem('meikova_relay_token', authToken);
          lastTokenRefreshTime = Date.now();
        }
      } else if (res.status === 401) {
        handleAutoLogout(window.t ? t('session.toast_global_logout', { min: timeoutGlobalMin }) : 'Phiên đăng nhập đã hết hạn');
      }
    } catch (err) {
      console.warn('Sliding token refresh warning:', err);
    } finally {
      isRefreshingToken = false;
    }
  }

  // 2. Global Activity Tracker
  function recordUserActivity() {
    const now = Date.now();
    lastGlobalActivity = now;
    if (isConnected) {
      lastRemoteActivity = now;
    }
    // Proactive sliding refresh: if user is active and it has been > 4 minutes since last refresh
    if (authToken && now - lastTokenRefreshTime > 4 * 60 * 1000) {
      refreshAuthToken();
    }
  }

  ['mousemove', 'mousedown', 'keydown', 'wheel', 'touchstart', 'pointerdown'].forEach(evt => {
    window.addEventListener(evt, recordUserActivity, { passive: true });
  });

  // 3. Automated Inactivity Watcher (Every 5 seconds)
  function checkSessionTimeouts() {
    const now = Date.now();

    // Condition A: Remote Session Idle (X minutes)
    // "nếu đang kết nối dùng thì không sao, nhưng nếu không thao tác quá X phút thì sẽ tự thoát session"
    if (isConnected) {
      const elapsedRemoteMin = (now - lastRemoteActivity) / 60000;
      if (elapsedRemoteMin >= timeoutRemoteMin) {
        disconnect();
        switchView(authToken ? 'dashboard' : 'landing', true);
        showToast(
          (window.t ? t('session.toast_remote_disconnected', { min: timeoutRemoteMin }) : null) ||
          `Đã tự động ngắt kết nối máy trạm do không có thao tác trong ${timeoutRemoteMin} phút.`,
          'warning'
        );
      }
    }

    // Condition B: Global Inactivity Logout (Y minutes)
    // "còn Y phút nếu không có kết nối hay thao tác gì sẽ tự logout"
    if (authToken && !isConnected) {
      const elapsedGlobalMin = (now - lastGlobalActivity) / 60000;
      if (elapsedGlobalMin >= timeoutGlobalMin) {
        handleAutoLogout(
          (window.t ? t('session.toast_global_logout', { min: timeoutGlobalMin }) : null) ||
          `Đã tự động đăng xuất tài khoản do không hoạt động trong ${timeoutGlobalMin} phút.`
        );
      }
    }
  }
  setInterval(checkSessionTimeouts, 5000);

  // 4. Auto Logout Handler
  function handleAutoLogout(reasonMsg) {
    if (authToken) {
      try {
        fetch('/api/auth/logout', {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${authToken}` }
        }).catch(() => {});
      } catch {}
    }
    disconnect();
    authToken = null;
    if (window.meikovaSync) window.meikovaSync.setAuthToken(null);
    currentUser = null;
    localStorage.removeItem('meikova_relay_token');
    renderUserBadge();
    switchView('auth', true);
    if (reasonMsg) {
      showToast(reasonMsg, 'info');
    }
  }

  // 5. Logout Button
  btnLogout.addEventListener('click', () => {
    handleAutoLogout();
    switchView('landing', true);
  });

  // 6. Session Configuration Modal Controls
  const btnOpenSessionConfig = document.getElementById('btnOpenSessionConfig');
  const sessionConfigModal = document.getElementById('sessionConfigModal');
  const sessionConfigForm = document.getElementById('sessionConfigForm');
  const btnCancelSessionCfg = document.getElementById('btnCancelSessionCfg');
  const cfgTimeoutRemote = document.getElementById('cfgTimeoutRemote');
  const cfgTimeoutGlobal = document.getElementById('cfgTimeoutGlobal');

  function openSettingsModal() {
    if (cfgTimeoutRemote && cfgTimeoutGlobal) {
      cfgTimeoutRemote.value = timeoutRemoteMin;
      cfgTimeoutGlobal.value = timeoutGlobalMin;
    }
    const cfgEnableToasts = document.getElementById('cfgEnableToasts');
    if (cfgEnableToasts) {
      cfgEnableToasts.checked = localStorage.getItem('meikova_toast_enabled') !== 'false';
    }
    if (window.MeikovaI18n && typeof window.MeikovaI18n.applyTranslations === 'function' && sessionConfigModal) {
      window.MeikovaI18n.applyTranslations(sessionConfigModal);
    }
    sessionConfigModal?.classList.remove('hidden');
  }

  const btnDeckOpenSettings = document.getElementById('btnDeckOpenSettings');
  if (btnDeckOpenSettings) {
    btnDeckOpenSettings.addEventListener('click', () => {
      snippetsMenuDropdown?.classList.add('hidden');
      btnSnippetsMenu?.classList.remove('btn-active');
      openSettingsModal();
    });
  }

  if (btnOpenSessionConfig && sessionConfigModal && cfgTimeoutRemote && cfgTimeoutGlobal) {
    btnOpenSessionConfig.addEventListener('click', () => {
      openSettingsModal();
    });

    btnCancelSessionCfg?.addEventListener('click', () => {
      sessionConfigModal.classList.add('hidden');
    });

    sessionConfigModal.addEventListener('click', (e) => {
      if (e.target === sessionConfigModal) {
        sessionConfigModal.classList.add('hidden');
      }
    });

    sessionConfigForm?.addEventListener('submit', (e) => {
      e.preventDefault();
      const x = parseInt(cfgTimeoutRemote.value, 10);
      const y = parseInt(cfgTimeoutGlobal.value, 10);
      if (isNaN(x) || x < 1) {
        showToast(t('toast.min_time_x'), 'warning');
        return;
      }
      if (isNaN(y) || y < 2) {
        showToast(t('toast.min_time_y'), 'warning');
        return;
      }
      timeoutRemoteMin = x;
      timeoutGlobalMin = y;
      localStorage.setItem('meikova_relay_timeout_remote_min', String(x));
      localStorage.setItem('meikova_relay_timeout_global_min', String(y));

      const cfgEnableToasts = document.getElementById('cfgEnableToasts');
      const isToastChecked = cfgEnableToasts ? cfgEnableToasts.checked : true;
      localStorage.setItem('meikova_toast_enabled', isToastChecked ? 'true' : 'false');

      sessionConfigModal.classList.add('hidden');
      showToast(
        (window.t ? t('session.toast_saved', { x, y }) : null) ||
        `Đã lưu cài đặt hệ thống (Toasts: ${isToastChecked ? 'Bật' : 'Tắt'})`,
        'success'
      );
    });
  }

  // --- DASHBOARD FLEET ---
  let currentDeviceList = [];
  const btnDownloadExe = document.getElementById('btnDownloadExe');
  const btnDownloadHost = document.getElementById('btnDownloadHost');
  const btnOpenAddModal = document.getElementById('btnOpenAddModal');
  const addDeviceModal = document.getElementById('addDeviceModal');
  const btnCloseAddModal = document.getElementById('btnCloseAddModal');
  const osTabs = document.getElementById('osTabs');
  const osPanelWin = document.getElementById('osPanelWin');
  const osPanelMac = document.getElementById('osPanelMac');
  const osPanelLinux = document.getElementById('osPanelLinux');
  const btnDownloadMac = document.getElementById('btnDownloadMac');
  const btnDownloadLinux = document.getElementById('btnDownloadLinux');
  const modalBtnDownloadExe = document.getElementById('modalBtnDownloadExe');
  const modalBtnDownloadBat = document.getElementById('modalBtnDownloadBat');
  const modalBtnDownloadMacSh = document.getElementById('modalBtnDownloadMacSh');
  const modalBtnDownloadLinuxSh = document.getElementById('modalBtnDownloadLinuxSh');
  const cmdWinText = document.getElementById('cmdWinText');
  const cmdMacText = document.getElementById('cmdMacText');
  const cmdLinuxText = document.getElementById('cmdLinuxText');
  const btnCopyWinCmd = document.getElementById('btnCopyWinCmd');
  const btnCopyMacCmd = document.getElementById('btnCopyMacCmd');
  const btnCopyLinuxCmd = document.getElementById('btnCopyLinuxCmd');

  function downloadDesktopExe() {
    window.location.href = '/api/download/MeikovaRelayHost.exe';
  }
  function downloadHostInstaller() {
    const accountName = currentUser ? (currentUser.username || currentUser.email || 'User') : 'User';
    const userId = currentUser ? (currentUser.id || '') : '';
    const relayWs = defaultWsUrl;
    window.location.href = `/api/download/setup.bat?account=${encodeURIComponent(accountName)}&userId=${encodeURIComponent(userId)}&relay=${encodeURIComponent(relayWs)}`;
  }
  function downloadMacScript() {
    const accountName = currentUser ? (currentUser.username || currentUser.email || 'User') : 'User';
    const userId = currentUser ? (currentUser.id || currentUser.userId || '') : '';
    const relayWs = defaultWsUrl || window.location.origin.replace(/^http/, 'ws');
    window.location.href = `/api/download/setup-macos.sh?account=${encodeURIComponent(accountName)}&userId=${encodeURIComponent(userId)}&relay=${encodeURIComponent(relayWs)}`;
  }
  function downloadLinuxScript() {
    const accountName = currentUser ? (currentUser.username || currentUser.email || 'User') : 'User';
    const userId = currentUser ? (currentUser.id || currentUser.userId || '') : '';
    const relayWs = defaultWsUrl || window.location.origin.replace(/^http/, 'ws');
    window.location.href = `/api/download/setup-linux.sh?account=${encodeURIComponent(accountName)}&userId=${encodeURIComponent(userId)}&relay=${encodeURIComponent(relayWs)}`;
  }

  function getInstallCommands() {
    const accountName = currentUser ? (currentUser.username || currentUser.email || 'User') : 'User';
    const userId = currentUser ? (currentUser.id || currentUser.userId || '') : '';
    const origin = window.location.origin;
    const relayWs = defaultWsUrl || origin.replace(/^http/, 'ws');
    return {
      win: `powershell -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile('${origin}/api/download/setup.bat?account=${encodeURIComponent(accountName)}&userId=${encodeURIComponent(userId)}&relay=${encodeURIComponent(relayWs)}', 'setup.bat'); .\\setup.bat"`,
      mac: `curl -sSL "${origin}/api/download/setup-macos.sh?account=${encodeURIComponent(accountName)}&userId=${encodeURIComponent(userId)}&relay=${encodeURIComponent(relayWs)}" | bash`,
      linux: `curl -sSL "${origin}/api/download/setup-linux.sh?account=${encodeURIComponent(accountName)}&userId=${encodeURIComponent(userId)}&relay=${encodeURIComponent(relayWs)}" | bash`
    };
  }

  function updateInstallModalContent() {
    const cmds = getInstallCommands();
    if (cmdWinText) cmdWinText.textContent = cmds.win;
    if (cmdMacText) cmdMacText.textContent = cmds.mac;
    if (cmdLinuxText) cmdLinuxText.textContent = cmds.linux;
  }

  function copyTextToClipboard(text, btn) {
    if (!text) return;
    navigator.clipboard.writeText(text).then(() => {
      const orig = btn.textContent;
      btn.textContent = 'Copied!';
      btn.style.color = 'var(--accent)';
      setTimeout(() => {
        btn.textContent = orig;
        btn.style.color = '';
      }, 2000);
    }).catch(() => {
      showToast(t('toast.copy_failed'), 'error');
    });
  }

  osTabs?.addEventListener('click', (e) => {
    const btn = e.target.closest('button');
    if (!btn) return;
    osTabs.querySelectorAll('button').forEach(b => b.classList.remove('on'));
    btn.classList.add('on');
    placeIndicator(osTabs);
    const os = btn.dataset.os;
    osPanelWin?.classList.toggle('hidden', os !== 'win');
    osPanelMac?.classList.toggle('hidden', os !== 'mac');
    osPanelLinux?.classList.toggle('hidden', os !== 'linux');
  });

  btnOpenAddModal?.addEventListener('click', () => {
    updateInstallModalContent();
    addDeviceModal?.classList.remove('hidden');
    setTimeout(() => placeIndicator(osTabs), 50);
  });
  btnCloseAddModal?.addEventListener('click', () => {
    addDeviceModal?.classList.add('hidden');
  });
  addDeviceModal?.addEventListener('click', (e) => {
    if (e.target === addDeviceModal) addDeviceModal.classList.add('hidden');
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && addDeviceModal && !addDeviceModal.classList.contains('hidden')) {
      addDeviceModal.classList.add('hidden');
    }
  });
  btnDownloadMac?.addEventListener('click', () => {
    updateInstallModalContent();
    addDeviceModal?.classList.remove('hidden');
    osTabs?.querySelector('[data-os="mac"]')?.click();
  });
  btnDownloadLinux?.addEventListener('click', () => {
    updateInstallModalContent();
    addDeviceModal?.classList.remove('hidden');
    osTabs?.querySelector('[data-os="linux"]')?.click();
  });

  modalBtnDownloadExe?.addEventListener('click', downloadDesktopExe);
  modalBtnDownloadBat?.addEventListener('click', downloadHostInstaller);
  modalBtnDownloadMacSh?.addEventListener('click', downloadMacScript);
  modalBtnDownloadLinuxSh?.addEventListener('click', downloadLinuxScript);

  btnCopyWinCmd?.addEventListener('click', () => copyTextToClipboard(cmdWinText.textContent, btnCopyWinCmd));
  btnCopyMacCmd?.addEventListener('click', () => copyTextToClipboard(cmdMacText.textContent, btnCopyMacCmd));
  btnCopyLinuxCmd?.addEventListener('click', () => copyTextToClipboard(cmdLinuxText.textContent, btnCopyLinuxCmd));

  btnDownloadExe?.addEventListener('click', downloadDesktopExe);
  btnDownloadHost?.addEventListener('click', downloadHostInstaller);

  async function loadDeviceFleet(silent = false) {
    if (!silent) {
      deviceGrid.innerHTML = `<p class="mono-font" data-i18n="dashboard.loading" style="color: var(--text-faint); padding: 20px;">${t('dashboard.loading')}</p>`;
    }
    try {
      const data = await apiFetch('/api/devices');
      if (data.success && data.devices) {
        currentDeviceList = data.devices;
        renderDeviceGrid(currentDeviceList);
      }
    } catch {
      if (!silent) {
        deviceGrid.innerHTML = `<p class="mono-font" data-i18n="dashboard.load_error" style="color: #EF4444; padding: 20px;">${t('dashboard.load_error')}</p>`;
      }
    }
  }

  // Auto-refresh fleet every 4s to detect newly connected hosts instantly
  setInterval(() => {
    if (currentView === 'dashboard' && authToken && currentUser) {
      loadDeviceFleet(true);
    }
  }, 4000);

  function getOsSvg(osInfo) {
    const os = (osInfo || '').toLowerCase();
    if (os.includes('win')) {
      return '<svg viewBox="0 0 24 24" width="13" height="13" fill="currentColor"><path d="M0 3.449L9.75 2.1v9.451H0m10.949-9.602L24 0v11.4H10.949M0 12.6h9.75v9.451L0 20.699M10.949 12.6H24V24l-13.051-1.802"/></svg>';
    }
    if (os.includes('linux') || os.includes('ubuntu') || os.includes('debian')) {
      return '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 8v8m-4-4h8"/></svg>';
    }
    if (os.includes('mac') || os.includes('darwin') || os.includes('apple')) {
      return '<svg viewBox="0 0 24 24" width="13" height="13" fill="currentColor"><path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.81-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M15.97 6.84c.66-.8 1.11-1.92.99-3.04-.96.04-2.12.64-2.8 1.44-.61.71-1.15 1.85-1 2.95 1.07.08 2.16-.55 2.81-1.35z"/></svg>';
    }
    return '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>';
  }

  const resSvg = '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>';
  const roomSvg = '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>';


  // --- MULTI-CLIENT SESSION MANAGEMENT & LIVE FLEET SESSIONS ---
  let currentManagingRoomId = null;
  let mySessionId = null;
  let roomSessions = [];

  const modalSessionManager = document.getElementById('modalSessionManager');
  const btnCloseSessionManager = document.getElementById('btnCloseSessionManager');
  const btnRefreshSessions = document.getElementById('btnRefreshSessions');
  const btnOpenTimeoutFromSessions = document.getElementById('btnOpenTimeoutFromSessions');

  btnCloseSessionManager?.addEventListener('click', () => {
    modalSessionManager?.classList.add('hidden');
  });

  modalSessionManager?.addEventListener('click', (e) => {
    if (e.target === modalSessionManager) {
      modalSessionManager.classList.add('hidden');
    }
  });

  btnRefreshSessions?.addEventListener('click', () => {
    refreshSessionManagerList();
  });

  btnOpenTimeoutFromSessions?.addEventListener('click', () => {
    modalSessionManager?.classList.add('hidden');
    if (cfgTimeoutRemote && cfgTimeoutGlobal) {
      cfgTimeoutRemote.value = timeoutRemoteMin;
      cfgTimeoutGlobal.value = timeoutGlobalMin;
    }
    sessionConfigModal?.classList.remove('hidden');
  });

  async function openSessionManagerModal(roomId, deviceName) {
    currentManagingRoomId = roomId || currentRoom || currentRoomId;
    const titleEl = document.getElementById('modalSessionManagerTitle');
    const subEl = document.getElementById('sessionManagerSubtitle');
    if (titleEl) titleEl.textContent = `Quản lý phiên // ${deviceName || currentManagingRoomId}`;
    if (subEl) subEl.textContent = `MÃ PHÒNG: ${currentManagingRoomId} // ĐA PHIÊN & NGẮT PHIÊN ĐỐI PHƯƠNG`;

    modalSessionManager?.classList.remove('hidden');
    await refreshSessionManagerList();
  }

  function formatTimeAgo(timestamp) {
    if (!timestamp) return 'Vừa xong';
    const sec = Math.max(1, Math.floor((Date.now() - timestamp) / 1000));
    if (sec < 60) return `${sec}s trước`;
    const min = Math.floor(sec / 60);
    if (min < 60) return `${min} phút trước`;
    const hrs = Math.floor(min / 60);
    return `${hrs}h${min % 60}m trước`;
  }

  async function refreshSessionManagerList() {
    const listEl = document.getElementById('sessionManagerList');
    const footerCount = document.getElementById('sessionManagerFooterCount');
    if (!listEl) return;

    listEl.innerHTML = `<div style="text-align:center; padding:24px; color:var(--text-muted);" class="mono-font">Đang tải danh sách phiên trực tiếp...</div>`;

    try {
      if (ws && ws.readyState === WebSocket.OPEN && (currentRoom === currentManagingRoomId || currentRoomId === currentManagingRoomId)) {
        ws.send(JSON.stringify({ type: 'get_sessions' }));
        ws.send(JSON.stringify({ type: 'clipboard_pull' }));
      }

      const res = await apiFetch(`/api/rooms/${currentManagingRoomId}/sessions`, 'GET');
      if (res && res.success) {
        roomSessions = res.sessions || [];
      }
      renderSessionManagerList(roomSessions);
    } catch (err) {
      listEl.innerHTML = `<div style="text-align:center; padding:20px; color:#ef4444;" class="mono-font">Lỗi khi tải danh sách phiên: ${escapeHtml(err.message)}</div>`;
    }
  }

  function renderSessionManagerList(sessions) {
    const listEl = document.getElementById('sessionManagerList');
    const footerCount = document.getElementById('sessionManagerFooterCount');
    if (!listEl) return;
    if (footerCount) footerCount.textContent = `${(sessions || []).length} phiên đang hoạt động`;

    if (!sessions || sessions.length === 0) {
      listEl.innerHTML = `
        <div style="text-align:center; padding:32px; background:var(--ink-1); border:1px dashed var(--line); border-radius:var(--radius);">
          <p class="brand-font" style="margin:0 0 6px 0; color:var(--text); font-size:0.95rem;">Chưa có phiên kết nối nào</p>
          <p class="mono-font" style="margin:0; font-size:0.72rem; color:var(--text-faint);">Máy trạm hiện không có ai remote hoặc đang chờ kết nối.</p>
        </div>
      `;
      return;
    }

    listEl.innerHTML = sessions.map(sess => {
      const isSelf = !!sess.isSelf || (sess.id && sess.id === mySessionId) || (sess.machineId && myMachineId && sess.machineId === myMachineId);
      const connTime = formatTimeAgo(sess.connectedAt);
      return `
        <div class="session-card" style="display:flex; align-items:center; justify-content:space-between; padding:12px 14px; background:var(--ink-1); border:1px solid ${isSelf ? 'rgba(34,197,94,0.3)' : 'var(--line)'}; border-radius:var(--radius); gap:12px;">
          <div style="display:flex; align-items:center; gap:10px; flex:1; min-width:0;">
            <div style="width:36px; height:36px; border-radius:50%; background:${isSelf ? 'rgba(34,197,94,0.1)' : 'rgba(56,189,248,0.1)'}; border:1px solid ${isSelf ? 'rgba(34,197,94,0.3)' : 'rgba(56,189,248,0.3)'}; color:${isSelf ? 'var(--accent)' : '#38bdf8'}; display:flex; align-items:center; justify-content:center; flex-shrink:0;">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
            </div>
            <div style="min-width:0; flex:1;">
              <div style="display:flex; align-items:center; gap:6px;">
                <strong style="font-size:0.85rem; color:var(--text); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${escapeHtml(sess.username || 'Khách (Ẩn danh)')}</strong>
                ${isSelf ? `<span class="spec-chip mono-font" style="background:rgba(34,197,94,0.15); color:var(--accent); font-size:0.62rem; padding:1px 6px;">BẠN</span>` : `<span class="spec-chip mono-font" style="background:rgba(56,189,248,0.12); color:#38bdf8; font-size:0.62rem; padding:1px 6px;">KHÁCH</span>`}
              </div>
              <div class="mono-font" style="font-size:0.68rem; color:var(--text-muted); display:flex; gap:8px; margin-top:3px; flex-wrap:wrap;">
                <span>IP: ${escapeHtml(sess.clientIp || '127.0.0.1')}</span>
                <span>•</span>
                <span>${escapeHtml(sess.clientDevice || 'Trình duyệt Web')}</span>
                <span>•</span>
                <span>${connTime}</span>
              </div>
            </div>
          </div>
          ${!isSelf ? `
            <button type="button" class="btn-kill-session btn-pill" data-session-id="${sess.id}" data-user="${escapeHtml(sess.username || 'Khách')}" style="border-color:rgba(239,68,68,0.4); color:#ef4444; background:rgba(239,68,68,0.08); font-weight:600; padding:5px 12px; font-size:0.72rem; flex-shrink:0;" onmouseenter="this.style.background='rgba(239,68,68,0.2)';" onmouseleave="this.style.background='rgba(239,68,68,0.08)';">
              <svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:4px;"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
              <span>Ngắt phiên</span>
            </button>
          ` : `
            <span class="mono-font" style="font-size:0.68rem; color:var(--text-faint); padding: 4px 6px;">Phiên của bạn</span>
          `}
        </div>
      `;
    }).join('');

    listEl.querySelectorAll('.btn-kill-session').forEach(btn => {
      btn.addEventListener('click', async () => {
        const sessId = btn.dataset.sessionId;
        const uName = btn.dataset.user;
        const confirmed = await showConfirmModal({
          title: t('dialog.confirm_title') || 'Ngắt phiên điều khiển',
          message: `Bạn có chắc muốn NGẮT PHIÊN của "${uName}" ngay lập tức?`,
          confirmText: t('dialog.btn_kill') || 'Ngắt phiên',
          cancelText: t('dialog.btn_cancel') || 'Hủy',
          danger: true
        });
        if (!confirmed) return;

        btn.disabled = true;
        btn.textContent = 'Đang ngắt...';

        try {
          if (ws && ws.readyState === WebSocket.OPEN && (currentRoom === currentManagingRoomId || currentRoomId === currentManagingRoomId)) {
            ws.send(JSON.stringify({ type: 'kill_session', session_id: sessId }));
          }

          const res = await apiFetch('/api/sessions/kill', 'POST', {
            roomId: currentManagingRoomId,
            sessionId: sessId
          });

          if (res && res.success) {
            showToast(t('toast.session_killed_user', { user: uName }), 'success');
            await refreshSessionManagerList();
            loadDeviceFleet(true);
          } else {
            showToast(t('toast.generic_error', { message: res?.message || 'Error' }), 'error');
            btn.disabled = false;
            btn.textContent = 'Ngắt phiên';
          }
        } catch (err) {
          showToast(t('toast.generic_error', { message: err.message }), 'error');
          btn.disabled = false;
          btn.textContent = 'Ngắt phiên';
        }
      });
    });
  }

  function renderDeviceGrid(devices) {
    const devList = devices !== undefined ? devices : currentDeviceList;
    if (!devList || devList.length === 0) {
      deviceGrid.innerHTML = `
        <div class="empty-fleet" style="grid-column: 1 / -1; text-align: center; padding: 48px; background: var(--ink-1); border: 1px dashed var(--line); border-radius: var(--radius);">
          <p class="brand-font" data-i18n="dashboard.empty" style="font-size: 1.15rem; color: var(--text); margin-bottom: 8px;">${t('dashboard.empty')}</p>
          <p data-i18n="dashboard.empty_hint" style="font-size: var(--step--1); color: var(--text-muted); margin-bottom: 20px;">${t('dashboard.empty_hint')}</p>
          <div style="display:inline-flex;gap:12px;flex-wrap:wrap;justify-content:center;">
            <button id="btnEmptyAddDevice" class="btn-pill" style="border-color: var(--accent); color: var(--accent); font-weight: 600;" title="${t('dashboard.btn_add_device_title')}">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
              <span data-i18n="dashboard.btn_add_device">${t('dashboard.btn_add_device')}</span>
            </button>
            <!-- Backward compatibility for tests: data-i18n="dashboard.btn_download_host" -->
            <button id="btnEmptyAdd" class="btn-pill" title="${t('dashboard.btn_quick_connect')}">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>
              <span data-i18n="dashboard.btn_quick_connect">${t('dashboard.btn_quick_connect')}</span>
            </button>
          </div>
        </div>
      `;
      document.getElementById('btnEmptyAddDevice')?.addEventListener('click', () => {
        updateInstallModalContent();
        addDeviceModal?.classList.remove('hidden');
        setTimeout(() => placeIndicator(osTabs), 50);
      });
      document.getElementById('btnEmptyAdd')?.addEventListener('click', () => quickConnectModal.classList.remove('hidden'));
      return;
    }

    const onlineLabel = t('dashboard.status_online').toUpperCase();
    const offlineLabel = t('dashboard.status_offline').toUpperCase();
    const connectLabel = t('dashboard.btn_connect');

    deviceGrid.innerHTML = devList.map(d => {
      const isOnline = d.is_online === 1;
      return `
        <div class="device-card">
          <div class="device-card-header">
            <span class="device-name brand-font">${escapeHtml(d.device_name)}</span>
            <span class="status-badge ${isOnline ? 'online' : 'offline'}">
              <span class="status-dot"></span> <span data-i18n="${isOnline ? 'dashboard.status_online' : 'dashboard.status_offline'}">${isOnline ? onlineLabel : offlineLabel}</span>
            </span>
          </div>
          <div class="device-specs">
            <span class="spec-chip">${getOsSvg(d.os_info)} <span>${escapeHtml(d.os_info || 'Windows')}</span></span>
            <span class="spec-chip">${resSvg} <span>${escapeHtml(d.resolution || '1920x1080')}</span></span>
            <span class="spec-chip">${roomSvg} <span>${escapeHtml(d.room_id)}</span></span>
          </div>
          <div class="device-sessions-bar" style="margin: 8px 0; display:flex; align-items:center; justify-content:space-between; font-size: 0.72rem; padding: 6px 10px; background: rgba(255,255,255,0.02); border: 1px solid var(--line); border-radius: var(--radius);">
            <span class="sessions-indicator mono-font" style="display:inline-flex; align-items:center; gap:6px; color: ${(d.session_count || 0) > 0 ? 'var(--accent)' : 'var(--text-faint)'};">
              <span class="status-dot" style="width:6px; height:6px; border-radius:50%; background: ${(d.session_count || 0) > 0 ? 'var(--accent)' : 'var(--line)'}; ${(d.session_count || 0) > 0 ? 'box-shadow: 0 0 6px var(--accent);' : ''}"></span>
              <span>${(d.session_count || 0) > 0 ? `${d.session_count} phiên đang kết nối` : 'Chưa có phiên kết nối'}</span>
            </span>
            ${(d.session_count || 0) > 0 ? `
              <button type="button" class="btn-manage-sessions btn-pill" data-room="${escapeHtml(d.room_id)}" data-name="${escapeHtml(d.device_name)}" style="padding: 2px 8px; font-size: 0.68rem; height: 22px; border-color: rgba(56, 189, 248, 0.4); color: #38bdf8; background: rgba(56, 189, 248, 0.08);" title="Quản lý & ngắt phiên kết nối">
                <svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2" style="margin-right:3px;"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/></svg>
                <span>Quản lý</span>
              </button>
            ` : ''}
          </div>
          <div class="device-card-actions" style="display:flex;gap:8px;align-items:center;margin-top:auto;">
            <button class="btn-connect-device" data-room="${d.room_id}" data-pin="${d.pin}" style="flex:1;">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>
              <span data-i18n="dashboard.btn_connect">${connectLabel}</span>
            </button>
            <button type="button" class="btn-popout-device" data-room="${escapeHtml(d.room_id)}" data-pin="${escapeHtml(d.pin || '')}" data-name="${escapeHtml(d.device_name)}" title="Mở trong tab mới / cửa sổ riêng (Popout)" aria-label="Mở trong tab mới" style="height:38px;padding:0 12px;background:rgba(255,255,255,0.03);border:1px solid var(--line);border-radius:var(--radius);color:var(--text-muted);cursor:pointer;display:inline-flex;align-items:center;justify-content:center;transition:all 0.15s ease;" onmouseenter="this.style.color='var(--accent-cyan)';this.style.borderColor='rgba(56,189,248,0.4)';this.style.background='rgba(56,189,248,0.08)';" onmouseleave="this.style.color='var(--text-muted)';this.style.borderColor='var(--line)';this.style.background='rgba(255,255,255,0.03)';">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
            </button>
            <button class="btn-delete-device" data-id="${d.id}" data-name="${escapeHtml(d.device_name)}" title="${t('dashboard.btn_delete')}" aria-label="${t('dashboard.btn_delete')}" style="height:38px;padding:0 12px;background:rgba(255,255,255,0.03);border:1px solid var(--line);border-radius:var(--radius);color:var(--text-muted);cursor:pointer;display:inline-flex;align-items:center;justify-content:center;transition:all 0.15s ease;" onmouseenter="this.style.color='#EF4444';this.style.borderColor='rgba(239,68,68,0.4)';this.style.background='rgba(239,68,68,0.08)';" onmouseleave="this.style.color='var(--text-muted)';this.style.borderColor='var(--line)';this.style.background='rgba(255,255,255,0.03)';">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18m-2 0v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2M10 11v6M14 11v6"/></svg>
            </button>
          </div>
        </div>
      `;
    }).join('');

    deviceGrid.querySelectorAll('.btn-manage-sessions').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        openSessionManagerModal(btn.dataset.room, btn.dataset.name);
      });
    });

    deviceGrid.querySelectorAll('.btn-connect-device').forEach(btn => {
      btn.addEventListener('click', () => {
        const room = btn.dataset.room;
        const pin = btn.dataset.pin;
        startRemoteSession(defaultWsUrl, room, pin);
      });
    });

    deviceGrid.querySelectorAll('.btn-popout-device').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const room = btn.dataset.room;
        const pin = btn.dataset.pin || '';
        const popoutUrl = `/?room=${encodeURIComponent(room)}${pin ? `&pin=${encodeURIComponent(pin)}` : ''}&direct=1`;
        window.open(popoutUrl, '_blank', 'noopener,noreferrer');
      });
    });

    deviceGrid.querySelectorAll('.btn-delete-device').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const id = btn.dataset.id;
        const name = btn.dataset.name;
        const confirmMsg = t('dashboard.delete_confirm') || `Bạn có chắc muốn xóa máy trạm "${name}" khỏi danh sách?`;
        const confirmed = await showConfirmModal({
          title: t('dialog.confirm_title') || 'Xóa máy trạm',
          message: confirmMsg,
          confirmText: t('dialog.btn_delete') || 'Xóa',
          cancelText: t('dialog.btn_cancel') || 'Hủy',
          danger: true
        });
        if (confirmed) {
          try {
            const res = await apiFetch(`/api/devices/${id}`, 'DELETE');
            if (res && res.success) {
              await fetchDevices();
            } else {
              await showAlertModal({
                title: t('dialog.alert_title') || 'Lỗi',
                message: res?.message || 'Lỗi khi xóa máy trạm'
              });
            }
          } catch (err) {
            console.error('Delete device error:', err);
          }
        }
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
  function startRemoteSession(relayUrl, roomId, pin, isAutoReconnect = false) {
    if (!isAutoReconnect) {
      stopAutoReconnect();
      isUserInitiatedDisconnect = false;
      lastSessionRelay = relayUrl;
      lastSessionRoom = roomId;
      lastSessionPin = pin || '';
      resetSessionMetrics();
    }
    currentRoom = roomId;
    currentRoomId = roomId;
    currentPin = pin || '';
    if (pin) {
      sessionStorage.setItem('meikova_relay_pin_' + roomId, pin);
    }

    if (!['files', 'terminal', 'tasks', 'remote'].includes(currentView)) {
      switchView('remote', true);
    } else {
      syncUrlWithState(false);
    }
    const isMobileDevice = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
                           (window.matchMedia && window.matchMedia('(pointer: coarse)').matches) ||
                           window.innerWidth <= 1024;
    if (isMobileDevice) {
      setDisplayScaleMode(true);
    }
    roStatus.textContent = `${roomId} // ${t('ro.connecting')}`;
    const connOverlay = document.getElementById('canvasConnectingOverlay');
    if (connOverlay) connOverlay.classList.remove('hidden');

    if (ws) {
      ws.close();
      ws = null;
    }

    try {
      ws = new WebSocket(relayUrl);
      ws.binaryType = 'blob';
      ws.onerror = (err) => {
        console.warn('[Client WS Error]:', err);
      };
    } catch (err) {
      showToast(t('toast.ws_error', { error: err.message }), 'error');
      return;
    }

    ws.onopen = () => {
      roStatus.textContent = `${roomId} // ${t('ro.authenticating')}`;
      ws.send(JSON.stringify({
        type: 'init_client',
        room_id: roomId,
        pin: pin,
        token: authToken || '',
        username: currentUser ? currentUser.username : 'Khách',
        machine_id: myMachineId,
        client_name: (currentUser ? currentUser.username : 'Khách') + ' (' + (navigator.userAgent.includes('Edg') ? 'Edge' : navigator.userAgent.includes('Chrome') ? 'Chrome' : 'Browser') + ')'
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

        if (msg.type === 'protocol_matrix') {
          currentProtocolMatrix = msg.matrix;
          updateProtocolUI(msg.matrix);
          return;
        }

        if (msg.type === 'tunnel_update') {
          if (typeof window.onTunnelUpdate === 'function') {
            window.onTunnelUpdate(msg.tunnel);
          }
          return;
        }

        if (msg.status === 'ok' && msg.role === 'client') {
          isConnected = true;
          if (isAutoReconnecting) {
            stopAutoReconnect();
            showToast(t('toast.auto_reconnected') || 'Đã kết nối lại thành công!', 'success', 2500);
          }
          const connOverlay = document.getElementById('canvasConnectingOverlay');
          if (connOverlay) connOverlay.classList.add('hidden');
          mySessionId = msg.session_id || null;
          if (typeof updateRemoteSessionTabs === 'function') {
            updateRemoteSessionTabs();
          }
          lastRemoteActivity = Date.now();
          lastGlobalActivity = Date.now();
          if (isAwaitingRemoteRestart) {
            stopRestartReconnectPolling();
            showToast(t('toast.restart_success'), 'success');
          }
          roStatus.textContent = `${roomId} // ${t('ro.connected')}`;
          updateRoStatus();
          updateTerminalStatusBadge();
          if (msg.hostMeta) {
            updateHostResolution(msg.hostMeta.width, msg.hostMeta.height);
            if (msg.hostMeta.monitors) populateMonitors(msg.hostMeta.monitors);
            if (msg.hostMeta.deviceName) {
              const hn = document.getElementById('chatHostName');
              if (hn) hn.textContent = msg.hostMeta.deviceName;
            }
          }
          startPingLoop();
        } else if (msg.status === 'error') {
          if (isAwaitingRemoteRestart) {
            console.log('[MeikovaRelay] Host is restarting, waiting before retry:', msg.message);
            return;
          }
          const translatedError = (msg.code && typeof t === 'function' && t(msg.code) !== msg.code)
            ? t(msg.code)
            : (msg.message || 'Lỗi không xác định');
          showToast(t('toast.generic_error', { message: translatedError }), 'error');
          disconnect();
        } else if (msg.type === 'session_list') {
          roomSessions = msg.sessions || [];
          const count = msg.clientCount || roomSessions.length;
          const btnSessionCfg = document.getElementById('btnOpenSessionConfig');
          if (btnSessionCfg) {
            const span = btnSessionCfg.querySelector('span');
            if (span) span.textContent = count > 0 ? `Phiên (${count})` : (t('topbar.session_cfg') || 'Phiên');
          }
          if (currentManagingRoomId === (currentRoom || currentRoomId)) {
            renderSessionManagerList(roomSessions);
          }
          if (currentView === 'dashboard') {
            loadDeviceFleet(true);
          }
        } else if (msg.type === 'session_killed') {
          showToast(msg.message || 'Phiên kết nối của bạn đã bị ngắt bởi quản trị viên.', 'error');
          disconnect();
        } else if (msg.type === 'kill_session_success') {
          showToast(t('toast.peer_session_killed'), 'success');
          refreshSessionManagerList();
          loadDeviceFleet(true);
        } else if (msg.type === 'host_ready') {
          updateHostResolution(msg.width, msg.height);
          if (msg.monitors) populateMonitors(msg.monitors, msg.active_id);
          if (msg.deviceName) {
            const hn = document.getElementById('chatHostName');
            if (hn) hn.textContent = msg.deviceName;
          }
          syncDisplayProfileWithHost(true);
        } else if (msg.type === 'quality_preset_applied') {
          if (!msg.req_id || msg.req_id >= qualityPresetReqId) {
            if (qualitySelector && qualitySelector.value !== msg.preset) {
              qualitySelector.value = msg.preset;
            }
            updateQualityMenuUI(msg.preset);
            updatePixelIndicator();
            fitCanvasToViewport();
            const presetFallbackVi = {
              'native_1to1': '1:1 Chuẩn gốc (Pixel-Perfect)',
              'auto_sync': 'Tự động tối ưu (Auto-Sync)',
              'ultra_120': '120 FPS Siêu mượt',
              'speed_60': '60 FPS Mượt mà (720p)',
              'crisp_2k_4k': '2K / 4K Cực nét (95%)',
              'crisp_hd': 'HD Nét (1080p // 85%)',
              'balanced': '30 FPS Cân bằng (900p)',
              'eco': 'Tiết kiệm băng thông (540p)',
              'grayscale': 'Tiết kiệm băng thông (Đơn sắc)'
            };
            const fName = presetFallbackVi[msg.preset] || msg.preset;
            showToast(t('toast.preset_activated', { preset: fName }), 'success');
          }
        } else if (msg.type === 'display_profile_matched') {
          handleDisplayProfileMatched(msg);
        } else if (msg.type === 'monitors_list') {
          populateMonitors(msg.monitors, msg.active_id);
          if (vdDisplayBadge) {
            if (msg.is_headless) {
              vdDisplayBadge.textContent = (typeof t === 'function') ? t('virtual.display_headless') : 'KHÔNG MÀN HÌNH';
              vdDisplayBadge.style.background = 'rgba(239, 68, 68, 0.15)';
              vdDisplayBadge.style.color = '#ef4444';
              btnInstallVDisplay?.classList.remove('hidden');
            } else {
              vdDisplayBadge.textContent = (typeof t === 'function') ? t('virtual.display_active') : 'SẴN SÀNG';
              vdDisplayBadge.style.background = 'rgba(34, 197, 94, 0.15)';
              vdDisplayBadge.style.color = '#22c55e';
              btnInstallVDisplay?.classList.add('hidden');
            }
          }
        } else if (msg.type === 'cursor_update') {
          applyHostCursor(msg.cursor);
        } else if (msg.type === 'clipboard_sync') {
          lastSyncedClientClipboard = msg.text || '';
          if (document.activeElement !== clipboardViewer) {
            clipboardViewer.value = msg.text || '';
          }
          if (navigator.clipboard && navigator.clipboard.writeText && msg.text) {
            navigator.clipboard.writeText(msg.text).catch(() => {});
          }
        } else if (msg.type === 'clipboard_sync_image') {
          handleIncomingClipboardImage(msg.data, msg.mime);
        } else if (msg.type === 'clipboard_sync_files') {
          handleIncomingClipboardFiles(msg.files);
        } else if (msg.type === 'clipboard_sync_ack') {
          if (!msg.success) {
            showToast(t('toast.clip_update_failed'), 'error');
          }
        } else if (msg.type === 'clipboard_sync_image_ack') {
          if (!msg.success) {
            showToast(t('toast.clip_image_paste_failed'), 'error');
          }
        } else if (msg.type === 'clipboard_sync_files_ack') {
          // Silent ack for high-frequency clipboard sync
        } else if (msg.type === 'terminal_output') {
          handleTerminalOutput(msg.data || '');
        } else if (msg.type === 'telemetry_response') {
          handleTelemetryData(msg.data);
        } else if (msg.type === 'process_list_response') {
          handleProcessList(msg.processes || []);
        } else if (msg.type === 'process_kill_response') {
          showToast(msg.success ? `Đã dừng tiến trình PID ${msg.pid}` : `Không thể dừng tiến trình PID ${msg.pid}`, msg.success ? 'success' : 'error');
          if (currentView === 'tasks') requestTelemetryAndTasks();
        } else if (msg.type === 'file_browse_response') {
          renderFolderBrowser(msg.data);
          renderFullFileExplorer(msg.data);
        } else if (msg.type === 'file_delete_response') {
          showToast(msg.success ? 'Đã xóa tệp/thư mục thành công' : 'Không thể xóa (tệp đang được dùng hoặc bị khóa quyền)', msg.success ? 'success' : 'error');
          requestBrowsePath(remoteCurrentPath);
        } else if (msg.type === 'file_create_folder_response') {
          if (msg.result && msg.result.success) {
            showToast(t('toast.mkdir_success'), 'success');
            requestBrowsePath(remoteCurrentPath);
          } else {
            showToast(t('toast.mkdir_failed', { error: msg.result?.error || 'Unknown' }), 'error');
          }
        } else if (msg.type === 'file_copy_response') {
          if (msg.result && msg.result.success) {
            showToast(t('files.copy_success') || 'Đã sao chép tệp/thư mục thành công', 'success');
            requestBrowsePath(remoteCurrentPath);
          } else {
            showToast(t('toast.file_copy_failed', { error: msg.result?.error || 'Failed' }), 'error');
          }
        } else if (msg.type === 'file_move_response') {
          if (msg.result && msg.result.success) {
            showToast(t('files.move_success') || 'Đã di chuyển tệp/thư mục thành công', 'success');
            explorerClipboard = null;
            updatePasteButtonState();
            requestBrowsePath(remoteCurrentPath);
          } else {
            showToast(t('toast.file_move_failed', { error: msg.result?.error || 'Failed' }), 'error');
          }
        } else if (msg.type === 'file_rename_response') {
          if (msg.result && msg.result.success) {
            showToast(t('files.rename_success') || 'Đã đổi tên tệp/thư mục thành công', 'success');
            requestBrowsePath(remoteCurrentPath);
          } else {
            showToast(t('toast.file_rename_failed', { error: msg.result?.error || 'Failed' }), 'error');
          }
        } else if (msg.type === 'file_read_response') {
          handleFileReadResponse(msg);
        } else if (msg.type === 'file_save_response') {
          handleFileSaveResponse(msg);
        } else if (msg.type === 'file_upload_progress') {
          uploadPercent.textContent = `${msg.progress}%`;
          uploadProgressBar.style.width = `${msg.progress}%`;
          if (expTransferProgress && !expTransferProgress.classList.contains('hidden')) {
            expTransferPercent.textContent = `${msg.progress}%`;
            expTransferFill.style.width = `${msg.progress}%`;
          }
        } else if (msg.type === 'file_upload_result') {
          uploadProgressContainer.classList.add('hidden');
          if (expTransferProgress) expTransferProgress.classList.add('hidden');
          showToast(t('toast.upload_success', { filename: msg.result.filename }), 'success');
          requestBrowsePath(remoteCurrentPath);
        } else if (msg.type === 'file_download_start') {
          activeDownloads[msg.transfer_id] = {
            filename: msg.filename,
            totalBytes: msg.filesize,
            receivedBytes: 0,
            chunks: []
          };
          if (expTransferProgress) {
            expTransferProgress.classList.remove('hidden');
            expTransferLabel.textContent = `Đang tải về: ${msg.filename} (${formatBytes(msg.filesize)})`;
            expTransferPercent.textContent = '0%';
            expTransferFill.style.width = '0%';
          }
        } else if (msg.type === 'file_download_chunk') {
          const dl = activeDownloads[msg.transfer_id];
          if (dl) {
            const buf = base64ToArrayBuffer(msg.data);
            dl.chunks.push(buf);
            dl.receivedBytes = (dl.receivedBytes || 0) + buf.byteLength;
            const pct = Math.min(100, Math.round((dl.receivedBytes / Math.max(1, dl.totalBytes)) * 100));
            if (expTransferProgress && !expTransferProgress.classList.contains('hidden')) {
              expTransferPercent.textContent = `${pct}%`;
              expTransferFill.style.width = `${pct}%`;
            }
          }
        } else if (msg.type === 'file_download_finish') {
          const dl = activeDownloads[msg.transfer_id];
          if (dl) {
            const blob = new Blob(dl.chunks, { type: 'application/octet-stream' });
            downloadBlob(blob, dl.filename);
            delete activeDownloads[msg.transfer_id];
            if (expTransferProgress) expTransferProgress.classList.add('hidden');
            showToast(t('toast.download_success', { filename: dl.filename }), 'success');
          }
        } else if (msg.type === 'file_download_error') {
          if (expTransferProgress) expTransferProgress.classList.add('hidden');
          showToast(t('toast.upload_failed', { error: msg.message }), 'error');
          delete activeDownloads[msg.transfer_id];
        } else if (msg.type === 'pong') {
          const rtt = Math.round(performance.now() - lastPingSend);
          metricPing.textContent = rtt;
          recordPingSample(rtt);
        } else if (msg.type === 'chat_message') {
          appendChatMessage(msg.sender || 'Máy trạm', msg.message, false);
          const isChatVisible = shelfDrawer.classList.contains('open') && !shelfChatTab.classList.contains('hidden');
          if (!isChatVisible) {
            const chatUnreadDot = document.getElementById('chatUnreadDot');
            const tabChatUnreadDot = document.getElementById('tabChatUnreadDot');
            if (chatUnreadDot) chatUnreadDot.classList.remove('hidden');
            if (tabChatUnreadDot) tabChatUnreadDot.classList.remove('hidden');
            playChatNotificationSound();
            showToast(`${msg.sender || t('shelf.chat_welcome_title')}: ${msg.message}`, 'info');
          }
        } else if (msg.type === 'audio_chunk') {
          if (isAudioStreaming && msg.data) {
            const raw = base64ToArrayBuffer(msg.data);
            playPcmAudioChunk(raw, msg.rate || 48000, msg.channels || 2);
          }
        } else if (msg.type === 'audio_stream_status') {
          updateAudioStreamUi(msg.enabled);
          if (msg.enabled && msg.has_device === false) {
            showConfirmModal({
              title: (typeof i18n !== 'undefined' && i18n.t) ? i18n.t('audio.no_speaker_title') : 'Máy Trạm Chưa Có Loa Ngoài',
              message: (typeof i18n !== 'undefined' && i18n.t) ? i18n.t('audio.no_speaker_desc') : 'Máy trạm hiện không cắm loa ngoài hoặc tai nghe. Bạn có muốn máy trạm tự động cài đặt Loa Ảo (Virtual Audio Cable) để truyền âm thanh về máy này không?',
              confirmText: (typeof i18n !== 'undefined' && i18n.t) ? i18n.t('audio.install_btn') : 'Cài Đặt Loa Ảo',
              cancelText: (typeof i18n !== 'undefined' && i18n.t) ? i18n.t('audio.dismiss_btn') : 'Để sau'
            }).then(confirmed => {
              if (confirmed) {
                showToast(t('toast.installing_vb_audio'), 'info');
                ws.send(JSON.stringify({ type: 'install_virtual_audio' }));
              }
            });
          } else {
            showToast(msg.enabled ? 'Đã bật truyền âm thanh từ máy trạm' : 'Đã tắt truyền âm thanh', msg.enabled ? 'success' : 'info');
          }
        } else if (msg.type === 'virtual_audio_install_result') {
          if (msg.success) {
            showToast(msg.message || 'Đã cài đặt Loa Ảo thành công! Đang truyền âm thanh.', 'success');
          } else {
            showToast(msg.message || 'Cài đặt Loa Ảo thất bại.', 'error');
          }
        } else if (msg.type === 'screen_resolution_result') {
          if (msg.success) {
            showToast(t('toast.resolution_changed', { res: `${msg.width}x${msg.height}` }), 'success');
            updateResolutionUi(msg.width, msg.height);
          } else {
            showToast(t('toast.resolution_failed'), 'error');
          }
        } else if (msg.type === 'virtual_display_result') {
          if (msg.success) {
            showToast(msg.message || 'Đã kích hoạt Màn hình ảo thành công!', 'success');
          } else {
            showToast(msg.message || 'Kích hoạt Màn hình ảo thất bại.', 'error');
          }
        } else if (msg.type === 'client_mic_status') {
          updateMicUi(msg.enabled);
        } else if (msg.type === 'audio_capabilities') {
          console.log('[MeikovaRelay] Host audio capabilities:', msg);
          if (vdAudioBadge) {
            if (msg.has_output_device === false) {
              vdAudioBadge.textContent = (typeof t === 'function') ? t('virtual.audio_missing') : 'CHƯA CÓ LOA';
              vdAudioBadge.style.background = 'rgba(239, 68, 68, 0.15)';
              vdAudioBadge.style.color = '#ef4444';
              btnInstallVAudio?.classList.remove('hidden');
            } else {
              vdAudioBadge.textContent = (typeof t === 'function') ? t('virtual.audio_active') : 'SẴN SÀNG';
              vdAudioBadge.style.background = 'rgba(34, 197, 94, 0.15)';
              vdAudioBadge.style.color = '#22c55e';
              btnInstallVAudio?.classList.add('hidden');
            }
          }
        } else if (msg.type === 'block_input_response') {
          if (msg.success !== false) {
            isInputBlocked = !!msg.blocked;
            btnToggleBlockInput?.classList.toggle('btn-active', isInputBlocked);
            btnToggleBlockInput?.classList.toggle('is-locked', isInputBlocked);
            if (btnToggleBlockInput) {
              btnToggleBlockInput.title = isInputBlocked
                ? (typeof t === 'function' ? t('toast.block_input_on') : 'Đang khóa chuột & phím máy đích')
                : (typeof t === 'function' ? t('toast.block_input_off') : 'Khóa chuột & phím máy đích');
            }
            showToast(isInputBlocked ? t('toast.block_input_on') : t('toast.block_input_off'), isInputBlocked ? 'warning' : 'success');
          } else {
            btnToggleBlockInput?.classList.toggle('btn-active', isInputBlocked);
            btnToggleBlockInput?.classList.toggle('is-locked', isInputBlocked);
            showToast(t('toast.block_input_error') || 'Không thể thay đổi trạng thái khóa bàn phím & chuột', 'error');
          }
        } else if (msg.type === 'privacy_curtain_response') {
          isCurtainActive = !!msg.enabled;
          btnToggleCurtain?.classList.toggle('is-curtain-active', isCurtainActive);
          curtainSvgOff?.classList.toggle('hidden', isCurtainActive);
          curtainSvgOn?.classList.toggle('hidden', !isCurtainActive);
          if (msg.success) {
            showToast(isCurtainActive ? t('toast.curtain_enabled') : t('toast.curtain_disabled'), isCurtainActive ? 'warning' : 'success');
          } else {
            showToast(t('toast.curtain_error', { error: msg.error || 'Failed' }), 'error');
          }
        } else if (msg.type === 'host_disconnected') {
          if (isAwaitingRemoteRestart) {
            handleRemoteRestartReconnecting();
            return;
          }
          // Host transient offline - try to auto-reconnect for up to 30s instead of immediately booting user
          handleAutoReconnecting();
        }
      } catch (err) {
        console.error('WS parse error:', err);
      }
    };

    ws.onclose = (ev) => {
      if (isAwaitingRemoteRestart) {
        handleRemoteRestartReconnecting();
        return;
      }
      if (isUserInitiatedDisconnect) {
        disconnect();
        return;
      }
      // If was connected or already reconnecting, attempt resilient auto-reconnect
      if (isConnected || isAutoReconnecting || (lastSessionRoom && currentView === 'remote')) {
        handleAutoReconnecting();
        return;
      }
      const reason = ev && ev.reason ? `Máy trạm đã ngắt kết nối (${ev.reason})` : 'Mất kết nối với máy trạm';
      showToast(reason, 'error');
      disconnect();
    };
  }

  function handleRemoteRestartReconnecting() {
    if (!isAwaitingRemoteRestart) return;
    if (ws) {
      try { ws.close(); } catch {}
      ws = null;
    }
    isConnected = false;
    hasPromptedHeadlessDisplay = false;
    roStatus.textContent = `${restartReconnectRoom} // ${t('ro.rebooting')}`;

    if (restartReconnectTimer) return;

    showToast(t('toast.rebooting_reconnecting'), 'info', 4000);
    restartAttemptCount = 0;

    restartReconnectTimer = setInterval(() => {
      if (!isAwaitingRemoteRestart) {
        clearInterval(restartReconnectTimer);
        restartReconnectTimer = null;
        return;
      }
      restartAttemptCount++;
      roStatus.textContent = `${restartReconnectRoom} // ${t('ro.reconnecting')} (${restartAttemptCount})`;
      startRemoteSession(restartReconnectRelay || defaultWsUrl, restartReconnectRoom, restartReconnectPin);
    }, 5000);
  }

  function stopRestartReconnectPolling() {
    isAwaitingRemoteRestart = false;
    if (restartReconnectTimer) {
      clearInterval(restartReconnectTimer);
      restartReconnectTimer = null;
    }
    restartAttemptCount = 0;
  }

  function stopAutoReconnect() {
    if (autoReconnectTimer) {
      clearTimeout(autoReconnectTimer);
      autoReconnectTimer = null;
    }
    isAutoReconnecting = false;
    autoReconnectAttempts = 0;
  }

  function handleAutoReconnecting() {
    if (isUserInitiatedDisconnect || !lastSessionRoom) {
      disconnect();
      return;
    }
    if (isAutoReconnecting && autoReconnectTimer) return;

    isAutoReconnecting = true;
    isConnected = false;

    if (ws) {
      try {
        ws.onopen = null;
        ws.onclose = null;
        ws.onerror = null;
        ws.onmessage = null;
        ws.close();
      } catch {}
      ws = null;
    }

    const connOverlay = document.getElementById('canvasConnectingOverlay');
    if (connOverlay) {
      connOverlay.classList.remove('hidden');
      const connMsg = connOverlay.querySelector('p');
      if (connMsg) {
        connMsg.textContent = t('toast.auto_reconnecting') || 'Mất kết nối tạm thời. Đang tự động kết nối lại...';
      }
    }

    const targetRoom = lastSessionRoom || currentRoomId || 'ROOM';
    roStatus.textContent = `${targetRoom} // ${t('ro.reconnecting')} (${autoReconnectAttempts + 1}/${MAX_AUTO_RECONNECT_ATTEMPTS})`;

    if (autoReconnectAttempts === 0) {
      showToast(t('toast.auto_reconnecting') || 'Mất kết nối tạm thời. Đang tự động kết nối lại...', 'warning', 3000);
    }

    autoReconnectTimer = setTimeout(() => {
      autoReconnectTimer = null;
      if (!isAutoReconnecting || isUserInitiatedDisconnect) return;

      autoReconnectAttempts++;
      if (autoReconnectAttempts > MAX_AUTO_RECONNECT_ATTEMPTS) {
        stopAutoReconnect();
        showToast(t('toast.auto_reconnect_failed') || 'Không thể kết nối lại sau 12 lần thử. Đã ngắt kết nối.', 'error', 4000);
        disconnect();
        return;
      }

      roStatus.textContent = `${targetRoom} // ${t('ro.reconnecting')} (${autoReconnectAttempts}/${MAX_AUTO_RECONNECT_ATTEMPTS})`;
      startRemoteSession(lastSessionRelay || defaultWsUrl, targetRoom, lastSessionPin, true);
    }, autoReconnectAttempts === 0 ? 800 : 2500);
  }

  function disconnect() {
    stopAutoReconnect();
    stopRestartReconnectPolling();
    isConnected = false;
    resetSessionMetrics();
    updateTerminalStatusBadge();
    currentRoom = null;
    currentRoomId = null;
    currentPin = '';
    if (typeof updateRemoteSessionTabs === 'function') {
      updateRemoteSessionTabs();
    }
    updateAudioStreamUi(false);
    stopMicStream();
    if (audioContext && audioContext.state !== 'closed') {
      try { audioContext.suspend(); } catch {}
    }
    if (pingIntervalId) clearInterval(pingIntervalId);
    if (ws) {
      try { ws.close(); } catch {}
      ws = null;
    }
    stopRecording();
    stopWebcam();
    isCurtainActive = false;
    btnToggleCurtain?.classList.remove('is-curtain-active');
    curtainSvgOff?.classList.remove('hidden');
    curtainSvgOn?.classList.add('hidden');
    isInputBlocked = false;
    btnToggleBlockInput?.classList.remove('btn-active', 'is-locked');
    if (isWhiteboardActive) {
      toggleWhiteboard(false);
    }
    clearWhiteboard();
    if (remoteCanvas && ctx) {
      ctx.clearRect(0, 0, remoteCanvas.width, remoteCanvas.height);
    }
    if (laserCanvas && laserCtx) {
      laserCtx.clearRect(0, 0, laserCanvas.width, laserCanvas.height);
    }
    updateRoStatus();
    const connOverlay = document.getElementById('canvasConnectingOverlay');
    if (connOverlay) connOverlay.classList.remove('hidden');
    if (window.history && window.history.replaceState) {
      window.history.replaceState({ view: 'dashboard' }, '', '/dashboard');
    }
    switchView('dashboard', true);
  }

  btnDisconnect.addEventListener('click', () => {
    isUserInitiatedDisconnect = true;
    stopAutoReconnect();
    disconnect();
  });

  function startPingLoop() {
    if (pingIntervalId) clearInterval(pingIntervalId);
    pingIntervalId = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        lastPingSend = performance.now();
        ws.send(JSON.stringify({ type: 'ping', ts: Date.now() }));
      }
      if (isConnected && performance.now() - lastFpsUpdate > 2500) {
        if (metricFps) metricFps.textContent = '0';
      }
    }, 2000);
  }

  function updatePixelIndicator() {
    if (!pixelIndicatorBadge || !pixelIndicatorText) return;
    const isActuallyNative1to1 = (!isFitMode && qualitySelector && qualitySelector.value === 'native_1to1');
    if (isActuallyNative1to1) {
      pixelIndicatorText.textContent = `1:1 PIXEL-PERFECT (${hostResolution.width}x${hostResolution.height})`;
      pixelIndicatorBadge.classList.remove('hidden');
    } else {
      pixelIndicatorBadge.classList.add('hidden');
    }
  }

  function fitCanvasToViewport() {
    if (!remoteCanvas || !remoteSection) return;
    if (!isFitMode) {
      remoteCanvas.style.width = '';
      remoteCanvas.style.height = '';
      if (laserCanvas) {
        laserCanvas.style.width = '';
        laserCanvas.style.height = '';
      }
      if (whiteboardCanvas) {
        whiteboardCanvas.style.width = '';
        whiteboardCanvas.style.height = '';
      }
      return;
    }
    const containerW = remoteSection.clientWidth;
    const containerH = remoteSection.clientHeight;
    if (!containerW || !containerH || !hostResolution.width || !hostResolution.height) return;

    const scaleFactor = Math.min(containerW / hostResolution.width, containerH / hostResolution.height);
    const displayW = Math.round(hostResolution.width * scaleFactor);
    const displayH = Math.round(hostResolution.height * scaleFactor);

    remoteCanvas.style.width = `${displayW}px`;
    remoteCanvas.style.height = `${displayH}px`;
    if (laserCanvas) {
      laserCanvas.style.width = `${displayW}px`;
      laserCanvas.style.height = `${displayH}px`;
    }
    if (whiteboardCanvas) {
      whiteboardCanvas.style.width = `${displayW}px`;
      whiteboardCanvas.style.height = `${displayH}px`;
    }
  }

  function updateHostResolution(w, h) {
    hostResolution.width = w;
    hostResolution.height = h;
    remoteCanvas.width = w;
    remoteCanvas.height = h;
    laserCanvas.width = w;
    laserCanvas.height = h;
    if (whiteboardCanvas) {
      whiteboardCanvas.width = w;
      whiteboardCanvas.height = h;
      if (typeof redrawWhiteboard === 'function') redrawWhiteboard();
    }
    metricRes.textContent = `${w}x${h}`;
    updatePixelIndicator();
    fitCanvasToViewport();
  }

  function setDisplayScaleMode(fit) {
    isFitMode = fit;
    remoteSection.classList.toggle('fit-mode', isFitMode);
    document.getElementById('scaleSvgFit')?.classList.toggle('hidden', !isFitMode);
    document.getElementById('scaleSvg1to1')?.classList.toggle('hidden', isFitMode);
    scale = 1.0;
    panX = 0;
    panY = 0;
    applyCanvasTransform();
    updatePixelIndicator();
    fitCanvasToViewport();
  }

  function detectClientDisplayCapabilities() {
    return new Promise((resolve) => {
      const isMobileDevice = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
                             (window.matchMedia && window.matchMedia('(pointer: coarse)').matches) ||
                             window.innerWidth <= 1024;
      const dpr = isMobileDevice ? 1 : (window.devicePixelRatio || 1);
      const screenW = Math.round((isMobileDevice ? window.innerWidth : window.screen.width) * dpr);
      const screenH = Math.round((isMobileDevice ? window.innerHeight : window.screen.height) * dpr);
      const viewW = Math.round(window.innerWidth * dpr);
      const viewH = Math.round(window.innerHeight * dpr);

      let frames = 0;
      let start = performance.now();
      function check(ts) {
        frames++;
        if (ts - start >= 150) {
          const fps = Math.round((frames * 1000) / (ts - start));
          let estHz = 60;
          if (fps >= 130) estHz = 144;
          else if (fps >= 105) estHz = 120;
          else if (fps >= 80) estHz = 90;
          else if (fps >= 68) estHz = 75;
          else estHz = 60;
          resolve({ screenW, screenH, viewW, viewH, dpr, estHz, isMobileDevice });
        } else {
          requestAnimationFrame(check);
        }
      }
      requestAnimationFrame(check);
    });
  }

  async function syncDisplayProfileWithHost(silent = false) {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      if (!silent) showToast(t('toast.not_connected'), 'info');
      return;
    }
    const cap = await detectClientDisplayCapabilities();
    if (!silent) {
      showToast(t('toast.screen_analyzing', { info: `${cap.screenW}x${cap.screenH} @ ${cap.estHz}Hz` }), 'info');
    }
    ws.send(JSON.stringify({
      type: 'sync_display_profile',
      client_w: cap.screenW,
      client_h: cap.screenH,
      client_dpr: cap.dpr,
      client_fps: cap.estHz,
      viewport_w: cap.viewW,
      viewport_h: cap.viewH,
      is_mobile: cap.isMobileDevice
    }));
  }

  function handleDisplayProfileMatched(msg) {
    const recommended = msg.recommended_preset || 'speed_60';
    if (!hasUserManuallySelectedQuality || (qualitySelector && qualitySelector.value === 'auto_sync')) {
      if (qualitySelector) qualitySelector.value = recommended;
      updateQualityMenuUI(recommended);
    }

    const isMobileDevice = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
                           (window.matchMedia && window.matchMedia('(pointer: coarse)').matches) ||
                           window.innerWidth <= 1024;

    if (isMobileDevice) {
      // Mobile touch screens must ALWAYS stay fitted to the viewport
      setDisplayScaleMode(true);
    } else if (recommended === 'native_1to1') {
      setDisplayScaleMode(false);
    } else {
      setDisplayScaleMode(true);
    }

    const labelMap = {
      'native_1to1': '1:1 Chuẩn gốc (Pixel-Perfect)',
      'ultra_120': '120 FPS Siêu mượt',
      'crisp_2k_4k': '2K/4K Cực nét',
      'speed_60': '60 FPS Mượt mà',
      'crisp_hd': 'HD Nét',
      'balanced': '30 FPS Cân bằng',
      'grayscale': 'Tiết kiệm băng thông'
    };
    const label = labelMap[recommended] || recommended;
    showToast(t('toast.profile_matched', { host_res: `${msg.host_res[0]}x${msg.host_res[1]}`, client_res: `${msg.client_res[0]}x${msg.client_res[1]}`, fps: msg.client_fps, label: label }), 'success');
  }

  let pendingFrameBlob = null;
  let isFrameRendering = false;

  function handleIncomingFrame(blob) {
    // Retain newest frame; drop stale intermediate frames to eliminate rendering latency backlog
    pendingFrameBlob = blob;

    if (!isFrameRendering) {
      isFrameRendering = true;
      requestAnimationFrame(renderQueuedFrame);
    }
  }

  function decodeBlob(blob) {
    // 1. Try createImageBitmap without options first (options dictionary breaks WebKit on iOS Safari & PWA)
    if (typeof createImageBitmap === 'function') {
      return createImageBitmap(blob).catch(() => fallbackDecodeImage(blob));
    }
    return fallbackDecodeImage(blob);
  }

  function fallbackDecodeImage(blob) {
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(blob);
      const img = new Image();
      img.onload = () => {
        URL.revokeObjectURL(url);
        resolve(img);
      };
      img.onerror = (e) => {
        URL.revokeObjectURL(url);
        reject(e);
      };
      img.src = url;
    });
  }

  async function renderQueuedFrame() {
    if (!pendingFrameBlob) {
      isFrameRendering = false;
      return;
    }
    const blobToRender = pendingFrameBlob;
    pendingFrameBlob = null;

    try {
      const imgObj = await decodeBlob(blobToRender);
      const width = imgObj.naturalWidth || imgObj.width;
      const height = imgObj.naturalHeight || imgObj.height;

      if (isGridMode && hostMonitors.length > 1 && monitorTileMap.size > 0) {
        // Multi-Monitor Grid Slice Mode: Extract each monitor sub-rectangle from virtual desktop frame
        const vx = Math.min(...hostMonitors.map(m => m.rect[0]));
        const vy = Math.min(...hostMonitors.map(m => m.rect[1]));

        hostMonitors.forEach(m => {
          const tileItem = monitorTileMap.get(m.id);
          if (tileItem) {
            const sx = Math.max(0, m.rect[0] - vx);
            const sy = Math.max(0, m.rect[1] - vy);
            const sw = Math.max(1, m.rect[2] - m.rect[0]);
            const sh = Math.max(1, m.rect[3] - m.rect[1]);

            if (tileItem.canvas.width !== sw || tileItem.canvas.height !== sh) {
              tileItem.canvas.width = sw;
              tileItem.canvas.height = sh;
            }
            tileItem.ctx.drawImage(imgObj, sx, sy, sw, sh, 0, 0, sw, sh);
          }
        });
      } else {
        if (remoteCanvas.width !== width || remoteCanvas.height !== height) {
          updateHostResolution(width, height);
        }
        ctx.drawImage(imgObj, 0, 0);
        const connOverlay = document.getElementById('canvasConnectingOverlay');
        if (connOverlay && !connOverlay.classList.contains('hidden')) {
          connOverlay.classList.add('hidden');
        }
      }

      if (typeof imgObj.close === 'function') {
        imgObj.close();
      }

      // Honest Real-Time Measured Rendered FPS calculation
      frameCount++;
      const now = performance.now();
      const elapsed = (now - lastFpsUpdate) / 1000;
      if (elapsed >= 1.0) {
        const actualFps = Math.max(0, Math.round(frameCount / elapsed));
        if (metricFps) {
          metricFps.textContent = actualFps;
        }
        frameCount = 0;
        lastFpsUpdate = now;
      }

      // Flow Control: notify host that frame has rendered (Guacamole / WebRTC ACK model)
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'frame_ack', ts: Date.now() }));
      }
    } catch (err) {
      console.warn('[MeikovaRelay] Frame render fallback error:', err);
      // Still send ACK so host pipeline does not freeze indefinitely on decode error
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'frame_ack', ts: Date.now() }));
      }
    }

    if (pendingFrameBlob) {
      requestAnimationFrame(renderQueuedFrame);
    } else {
      isFrameRendering = false;
    }
  }

  // --- MULTI-MONITOR SELECTION & INTERACTIVE GRID ---
  function updateMonitorMenuUI(activeId = 0) {
    const idNum = parseInt(activeId, 10) || 0;
    if (monitorSelector) monitorSelector.value = String(idNum);

    if (monitorCurrentLabel) {
      if (idNum === 0) {
        monitorCurrentLabel.textContent = (typeof t === 'function' && t('deck.monitor_all')) ? t('deck.monitor_all') : 'Tất cả';
      } else {
        const mon = hostMonitors.find(m => m.id === idNum);
        monitorCurrentLabel.textContent = mon ? (mon.name || `Màn ${idNum}`) : `Màn ${idNum}`;
      }
    }

    if (monitorMenuList) {
      monitorMenuList.querySelectorAll('.quality-menu-item').forEach(item => {
        const itemMonId = parseInt(item.dataset.monId, 10);
        const isActive = itemMonId === idNum;
        item.classList.toggle('active', isActive);
        const check = item.querySelector('.quality-check');
        if (check) check.classList.toggle('hidden', !isActive);
      });
    }
  }

  function populateMonitors(monitors, activeId = 0) {
    if (!monitors || monitors.length === 0) return;
    hostMonitors = monitors;
    const currentActiveId = parseInt(activeId, 10) || 0;
    if (monitorSelector) monitorSelector.value = String(currentActiveId);

    const countStr = monitors.length > 1 ? ` (${monitors.length} màn)` : '';
    const allTitle = (typeof t === 'function' && t('deck.monitor_all_title'))
      ? t('deck.monitor_all_title', { count: monitors.length })
      : `Tất cả màn hình${countStr}`;
    const allDesc = (typeof t === 'function' && t('deck.monitor_all_desc'))
      ? t('deck.monitor_all_desc')
      : 'Truyền phát toàn bộ không gian làm việc đa màn hình';

    let html = `
      <button type="button" class="quality-menu-item ${currentActiveId === 0 ? 'active' : ''}" data-mon-id="0">
        <span class="quality-item-badge">ALL</span>
        <div class="quality-item-text">
          <div class="quality-item-title">${escapeHtml(allTitle)}</div>
          <div class="quality-item-desc">${escapeHtml(allDesc)}</div>
        </div>
        <span class="quality-check ${currentActiveId === 0 ? '' : 'hidden'}">
          <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
        </span>
      </button>
    `;

    monitors.forEach(m => {
      const isAct = (m.id === currentActiveId);
      const monName = m.name || `Màn hình ${m.id}`;
      const monDesc = `${m.width} x ${m.height} // Màn hình #${m.id}`;
      html += `
        <button type="button" class="quality-menu-item ${isAct ? 'active' : ''}" data-mon-id="${m.id}">
          <span class="quality-item-badge">M${m.id}</span>
          <div class="quality-item-text">
            <div class="quality-item-title">${escapeHtml(monName)}</div>
            <div class="quality-item-desc">${escapeHtml(monDesc)}</div>
          </div>
          <span class="quality-check ${isAct ? '' : 'hidden'}">
            <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
          </span>
        </button>
      `;
    });

    if (monitorMenuList) {
      monitorMenuList.innerHTML = html;
      monitorMenuList.querySelectorAll('.quality-menu-item').forEach(btn => {
        btn.addEventListener('click', () => {
          const monId = parseInt(btn.dataset.monId, 10);
          updateMonitorMenuUI(monId);
          monitorMenuDropdown?.classList.add('hidden');
          btnMonitorMenu?.classList.remove('btn-active');

          if (!isConnected || !ws) return;
          if (monId !== 0 && isGridMode) {
            setGridMode(false);
          }
          ws.send(JSON.stringify({
            type: 'switch_monitor',
            monitor_id: monId
          }));
        });
      });
    }

    updateMonitorMenuUI(currentActiveId);

    // Show/hide Grid button on floating deck
    if (monitors.length > 1) {
      btnToggleGrid?.classList.remove('hidden');
      initMonitorGrid();
    } else {
      btnToggleGrid?.classList.add('hidden');
      gridControls?.classList.add('hidden');
      setGridMode(false);
    }
  }

  function initMonitorGrid() {
    if (!monitorGrid || hostMonitors.length < 2) return;
    
    // Load saved order or default to monitors' IDs
    const savedOrder = localStorage.getItem('meikova_grid_order');
    let order = [];
    if (savedOrder) {
      try {
        order = JSON.parse(savedOrder);
      } catch {}
    }
    const currentIds = hostMonitors.map(m => m.id);
    if (!Array.isArray(order) || order.length !== currentIds.length || !order.every(id => currentIds.includes(id))) {
      order = [...currentIds];
    }
    gridMonitorOrder = order;

    renderGridTiles();
  }

  function renderGridTiles() {
    if (!monitorGrid) return;
    monitorGrid.innerHTML = '';
    monitorTileMap.clear();

    gridMonitorOrder.forEach(monId => {
      const mon = hostMonitors.find(m => m.id === monId);
      if (!mon) return;

      const tile = document.createElement('div');
      tile.className = 'monitor-tile';
      tile.draggable = true;
      tile.dataset.monId = String(mon.id);

      tile.innerHTML = `
        <div class="tile-header">
          <div class="tile-grip-wrap">
            <span class="tile-grip" title="Kéo thả để sắp xếp">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><circle cx="9" cy="6" r="1.5" fill="currentColor"/><circle cx="15" cy="6" r="1.5" fill="currentColor"/><circle cx="9" cy="12" r="1.5" fill="currentColor"/><circle cx="15" cy="12" r="1.5" fill="currentColor"/><circle cx="9" cy="18" r="1.5" fill="currentColor"/><circle cx="15" cy="18" r="1.5" fill="currentColor"/></svg>
            </span>
            <span class="tile-title">${escapeHtml(mon.name)}</span>
            <span class="tile-res-badge">${mon.width}x${mon.height}</span>
          </div>
          <div class="tile-actions">
            <button type="button" class="tile-btn-action btn-tile-focus" title="Xem riêng màn này">
              <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>
            </button>
          </div>
        </div>
        <div class="tile-canvas-wrap">
          <canvas class="monitor-canvas" width="${mon.width}" height="${mon.height}" tabindex="0"></canvas>
        </div>
      `;

      const canvas = tile.querySelector('canvas');
      const tileCtx = canvas.getContext('2d');
      monitorTileMap.set(mon.id, { tile, canvas, ctx: tileCtx, mon });

      // Focus button: switch to single monitor view
      tile.querySelector('.btn-tile-focus').addEventListener('click', (e) => {
        e.stopPropagation();
        setGridMode(false);
        updateMonitorMenuUI(mon.id);
        ws.send(JSON.stringify({ type: 'switch_monitor', monitor_id: mon.id }));
      });

      // Mouse & touch events forwarding for this monitor
      setupTileCanvasInput(canvas, mon);

      // HTML5 Drag and Drop handlers
      setupTileDragAndDrop(tile);

      monitorGrid.appendChild(tile);
    });

    applyGridLayoutClass();
  }

  function applyGridLayoutClass() {
    if (!monitorGrid) return;
    monitorGrid.classList.remove('layout-side-by-side', 'layout-stacked');
    if (gridLayoutMode === 'stacked') {
      monitorGrid.classList.add('layout-stacked');
    } else {
      monitorGrid.classList.add('layout-side-by-side');
    }
  }

  let draggedTile = null;

  function setupTileDragAndDrop(tile) {
    tile.addEventListener('dragstart', (e) => {
      draggedTile = tile;
      tile.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', tile.dataset.monId);
    });

    tile.addEventListener('dragover', (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      if (draggedTile && draggedTile !== tile) {
        tile.classList.add('drag-over');
      }
    });

    tile.addEventListener('dragleave', () => {
      tile.classList.remove('drag-over');
    });

    tile.addEventListener('drop', (e) => {
      e.preventDefault();
      tile.classList.remove('drag-over');
      if (!draggedTile || draggedTile === tile) return;

      const fromId = parseInt(draggedTile.dataset.monId, 10);
      const toId = parseInt(tile.dataset.monId, 10);

      const fromIdx = gridMonitorOrder.indexOf(fromId);
      const toIdx = gridMonitorOrder.indexOf(toId);

      if (fromIdx !== -1 && toIdx !== -1) {
        gridMonitorOrder.splice(fromIdx, 1);
        gridMonitorOrder.splice(toIdx, 0, fromId);
        localStorage.setItem('meikova_grid_order', JSON.stringify(gridMonitorOrder));
        renderGridTiles();
      }
    });

    tile.addEventListener('dragend', () => {
      tile.classList.remove('dragging');
      document.querySelectorAll('.monitor-tile').forEach(t => t.classList.remove('drag-over'));
      draggedTile = null;
    });
  }

  function setupTileCanvasInput(canvas, mon) {
    function getTileCoords(e) {
      const rect = canvas.getBoundingClientRect();
      const normX = Math.max(0.0, Math.min(1.0, (e.clientX - rect.left) / rect.width));
      const normY = Math.max(0.0, Math.min(1.0, (e.clientY - rect.top) / rect.height));
      return { x: normX, y: normY };
    }

    let lastTileMove = 0;
    canvas.addEventListener('mousemove', (e) => {
      if (!isConnected) return;
      const now = performance.now();
      if (now - lastTileMove < 25) return;
      lastTileMove = now;
      const c = getTileCoords(e);
      ws.send(JSON.stringify({
        type: 'mouse_move',
        x: c.x,
        y: c.y,
        monitor_id: mon.id
      }));
    });

    canvas.addEventListener('mousedown', (e) => {
      if (!isConnected) return;
      canvas.focus();
      const c = getTileCoords(e);
      ws.send(JSON.stringify({
        type: 'mouse_down',
        button: e.button,
        x: c.x,
        y: c.y,
        monitor_id: mon.id
      }));
    });

    canvas.addEventListener('mouseup', (e) => {
      if (!isConnected) return;
      const c = getTileCoords(e);
      ws.send(JSON.stringify({
        type: 'mouse_up',
        button: e.button,
        x: c.x,
        y: c.y,
        monitor_id: mon.id
      }));
    });

    canvas.addEventListener('contextmenu', e => e.preventDefault());

    canvas.addEventListener('wheel', (e) => {
      if (!isConnected) return;
      e.preventDefault();
      const c = getTileCoords(e);
      ws.send(JSON.stringify({
        type: 'mouse_wheel',
        delta_y: e.deltaY,
        x: c.x,
        y: c.y,
        monitor_id: mon.id
      }));
    }, { passive: false });
  }

  function setGridMode(enable) {
    isGridMode = enable;
    if (isGridMode) {
      viewportBox?.classList.add('hidden');
      monitorGrid?.classList.remove('hidden');
      gridControls?.classList.remove('hidden');
      btnToggleGrid?.classList.add('active');
      renderGridTiles();
      // Ensure host streams all monitors so sub-rectangles can be extracted
      if (monitorSelector && monitorSelector.value !== "0") {
        updateMonitorMenuUI(0);
        ws.send(JSON.stringify({ type: 'switch_monitor', monitor_id: 0 }));
      }
    } else {
      monitorGrid?.classList.add('hidden');
      viewportBox?.classList.remove('hidden');
      gridControls?.classList.add('hidden');
      btnToggleGrid?.classList.remove('active');
    }
  }

  btnToggleGrid?.addEventListener('click', () => {
    setGridMode(!isGridMode);
  });

  btnGridSideBySide?.addEventListener('click', () => {
    gridLayoutMode = 'side-by-side';
    btnGridSideBySide.classList.add('active');
    btnGridStacked?.classList.remove('active');
    applyGridLayoutClass();
  });

  btnGridInvert?.addEventListener('click', () => {
    gridMonitorOrder.reverse();
    localStorage.setItem('meikova_grid_order', JSON.stringify(gridMonitorOrder));
    renderGridTiles();
  });

  btnGridStacked?.addEventListener('click', () => {
    gridLayoutMode = 'stacked';
    btnGridStacked.classList.add('active');
    btnGridSideBySide?.classList.remove('active');
    applyGridLayoutClass();
  });

  monitorSelector.addEventListener('change', () => {
    if (!isConnected) return;
    const monId = parseInt(monitorSelector.value, 10);
    if (monId !== 0 && isGridMode) {
      setGridMode(false);
    }
    ws.send(JSON.stringify({
      type: 'switch_monitor',
      monitor_id: monId
    }));
  });

  const QUALITY_SHORT_LABELS = {
    'native_1to1': '1:1',
    'auto_sync': 'AUTO',
    'ultra_120': '120 FPS',
    'speed_60': '60 FPS',
    'crisp_2k_4k': '4K',
    'crisp_hd': 'HD',
    'balanced': '30 FPS',
    'grayscale': 'ECO'
  };

  function updateQualityMenuUI(preset) {
    if (qualityCurrentLabel) {
      qualityCurrentLabel.textContent = QUALITY_SHORT_LABELS[preset] || preset.toUpperCase();
    }
    document.querySelectorAll('.quality-menu-item').forEach(item => {
      const isThis = item.getAttribute('data-preset') === preset;
      item.classList.toggle('active', isThis);
      const check = item.querySelector('.quality-check');
      if (check) check.classList.toggle('hidden', !isThis);
    });
  }

  // Helper to dynamically position deck popovers directly aligned with their trigger button
  function positionDeckDropdown(triggerBtn, dropdownEl) {
    if (!triggerBtn || !dropdownEl) return;
    const isMobile = window.innerWidth <= 640 || window.innerHeight <= 520;
    const btnRect = triggerBtn.getBoundingClientRect();
    const isDeckAtTop = document.body.classList.contains('deck-at-top') ||
                         (floatingDeck && (floatingDeck.classList.contains('deck--top-pinned') || floatingDeck.classList.contains('deck--top-unpinned')));

    if (isMobile) {
      dropdownEl.style.left = '50%';
      dropdownEl.style.right = 'auto';
      dropdownEl.style.transform = 'translateX(-50%)';
      dropdownEl.style.width = 'calc(100vw - 20px)';
      dropdownEl.style.maxWidth = 'calc(100vw - 20px)';
      if (isDeckAtTop) {
        dropdownEl.style.top = `${Math.max(8, Math.round(btnRect.bottom + 6))}px`;
        dropdownEl.style.bottom = 'auto';
      } else {
        dropdownEl.style.bottom = `${Math.max(8, Math.round(window.innerHeight - btnRect.top + 6))}px`;
        dropdownEl.style.top = 'auto';
      }
      return;
    }

    const wasHidden = dropdownEl.classList.contains('hidden');
    if (wasHidden) {
      dropdownEl.style.visibility = 'hidden';
      dropdownEl.classList.remove('hidden');
    }
    const menuWidth = dropdownEl.offsetWidth || 340;
    if (wasHidden) {
      dropdownEl.classList.add('hidden');
      dropdownEl.style.visibility = '';
    }

    let left = btnRect.left + (btnRect.width / 2) - (menuWidth / 2);
    const maxLeft = window.innerWidth - menuWidth - 12;
    left = Math.max(12, Math.min(left, maxLeft));

    dropdownEl.style.left = `${Math.round(left)}px`;
    dropdownEl.style.right = 'auto';
    dropdownEl.style.transform = 'none';
    dropdownEl.style.width = '';
    dropdownEl.style.maxWidth = '';

    if (isDeckAtTop) {
      dropdownEl.style.top = `${Math.round(btnRect.bottom + 8)}px`;
      dropdownEl.style.bottom = 'auto';
    } else {
      dropdownEl.style.bottom = `${Math.round(window.innerHeight - btnRect.top + 8)}px`;
      dropdownEl.style.top = 'auto';
    }
  }

  // Desktop Wheel & Drag-to-Scroll on Floating Deck
  if (floatingDeck) {
    floatingDeck.addEventListener('wheel', (e) => {
      if (floatingDeck.scrollWidth > floatingDeck.clientWidth) {
        if (Math.abs(e.deltaY) >= Math.abs(e.deltaX)) {
          e.preventDefault();
          floatingDeck.scrollLeft += e.deltaY;
        }
      }
    }, { passive: false });

    floatingDeck.addEventListener('scroll', () => {
      if (monitorMenuDropdown && !monitorMenuDropdown.classList.contains('hidden') && btnMonitorMenu) {
        positionDeckDropdown(btnMonitorMenu, monitorMenuDropdown);
      }
      if (resolutionMenuDropdown && !resolutionMenuDropdown.classList.contains('hidden') && btnResolutionMenu) {
        positionDeckDropdown(btnResolutionMenu, resolutionMenuDropdown);
      }
      if (qualityMenuDropdown && !qualityMenuDropdown.classList.contains('hidden') && btnQualityMenu) {
        positionDeckDropdown(btnQualityMenu, qualityMenuDropdown);
      }
      if (protocolMenuDropdown && !protocolMenuDropdown.classList.contains('hidden') && btnProtocolMenu) {
        positionDeckDropdown(btnProtocolMenu, protocolMenuDropdown);
      }
      if (keyboardMenuDropdown && !keyboardMenuDropdown.classList.contains('hidden') && btnMobileKeyboard) {
        positionDeckDropdown(btnMobileKeyboard, keyboardMenuDropdown);
      }
    }, { passive: true });

    let isDeckDragging = false;
    let deckStartX = 0;
    let deckScrollLeft = 0;

    floatingDeck.addEventListener('mousedown', (e) => {
      if (e.target.closest('button, select, input, a, .quality-menu')) return;
      isDeckDragging = true;
      deckStartX = e.pageX - floatingDeck.offsetLeft;
      deckScrollLeft = floatingDeck.scrollLeft;
      floatingDeck.style.cursor = 'grabbing';
      floatingDeck.style.userSelect = 'none';
    });

    window.addEventListener('mousemove', (e) => {
      if (!isDeckDragging) return;
      e.preventDefault();
      const x = e.pageX - floatingDeck.offsetLeft;
      const walk = (x - deckStartX) * 1.5;
      floatingDeck.scrollLeft = deckScrollLeft - walk;
    });

    window.addEventListener('mouseup', () => {
      if (isDeckDragging) {
        isDeckDragging = false;
        floatingDeck.style.cursor = '';
        floatingDeck.style.removeProperty('user-select');
      }
    });
  }

  function handleViewportResize() {
    syncTrueViewportHeight();
    if (currentView === 'remote') {
      fitCanvasToViewport();
    }
    const isMobileDevice = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
                           (window.matchMedia && window.matchMedia('(pointer: coarse)').matches) ||
                           window.innerWidth <= 1024;
    if (isMobileDevice && isConnected && currentView === 'remote') {
      panX = 0;
      panY = 0;
      applyCanvasTransform();
    }
    if (protocolMenuDropdown && !protocolMenuDropdown.classList.contains('hidden') && btnProtocolMenu) {
      positionDeckDropdown(btnProtocolMenu, protocolMenuDropdown);
    }
    if (qualityMenuDropdown && !qualityMenuDropdown.classList.contains('hidden') && btnQualityMenu) {
      positionDeckDropdown(btnQualityMenu, qualityMenuDropdown);
    }
    if (resolutionMenuDropdown && !resolutionMenuDropdown.classList.contains('hidden') && btnResolutionMenu) {
      positionDeckDropdown(btnResolutionMenu, resolutionMenuDropdown);
    }
    if (monitorMenuDropdown && !monitorMenuDropdown.classList.contains('hidden') && btnMonitorMenu) {
      positionDeckDropdown(btnMonitorMenu, monitorMenuDropdown);
    }
    if (deckModeDropdown && !deckModeDropdown.classList.contains('hidden') && btnDeckDisplayMode) {
      positionDeckDropdown(btnDeckDisplayMode, deckModeDropdown);
    }
    if (powerMenuDropdown && !powerMenuDropdown.classList.contains('hidden') && btnPowerMenu) {
      positionDeckDropdown(btnPowerMenu, powerMenuDropdown);
    }
    if (keyboardMenuDropdown && !keyboardMenuDropdown.classList.contains('hidden') && btnMobileKeyboard) {
      positionDeckDropdown(btnMobileKeyboard, keyboardMenuDropdown);
    }
    if (typeof placeAllIndicators === 'function') placeAllIndicators();
  }

  window.addEventListener('resize', handleViewportResize);
  window.addEventListener('orientationchange', () => {
    setTimeout(handleViewportResize, 150);
  });

  // Toggle Quality Popover Menu
  if (btnQualityMenu) {
    btnQualityMenu.addEventListener('click', (e) => {
      e.stopPropagation();
      if (qualityMenuDropdown) {
        const isOpening = qualityMenuDropdown.classList.contains('hidden');
        qualityMenuDropdown.classList.toggle('hidden');
        btnQualityMenu.classList.toggle('btn-active', isOpening);
        if (isOpening) {
          positionDeckDropdown(btnQualityMenu, qualityMenuDropdown);
          monitorMenuDropdown?.classList.add('hidden');
          btnMonitorMenu?.classList.remove('btn-active');
          if (protocolMenuDropdown) {
            protocolMenuDropdown.classList.add('hidden');
            if (btnProtocolMenu) btnProtocolMenu.classList.remove('btn-active');
          }
        }
      }
      if (powerMenuDropdown) {
        powerMenuDropdown.classList.add('hidden');
        if (btnPowerMenu) btnPowerMenu.classList.remove('btn-active');
      }
      if (deckModeDropdown) {
        deckModeDropdown.classList.add('hidden');
        if (btnDeckDisplayMode) btnDeckDisplayMode.classList.remove('btn-active');
      }
    });
  }

  // Quality Preset Selection in Menu
  document.querySelectorAll('.quality-menu-item').forEach(btn => {
    btn.addEventListener('click', () => {
      const preset = btn.getAttribute('data-preset');
      hasUserManuallySelectedQuality = (preset !== 'auto_sync');
      if (qualitySelector) {
        qualitySelector.value = preset;
        qualitySelector.dispatchEvent(new Event('change'));
      }
      updateQualityMenuUI(preset);
      if (qualityMenuDropdown) qualityMenuDropdown.classList.add('hidden');
      if (btnQualityMenu) btnQualityMenu.classList.remove('btn-active');
    });
  });

  let qualityPresetReqId = 0;

  // --- QUALITY & RESOLUTION PRESET ---
  qualitySelector.addEventListener('change', () => {
    const activePreset = qualitySelector.value;
    hasUserManuallySelectedQuality = (activePreset !== 'auto_sync');
    updateQualityMenuUI(activePreset);
    if (!isConnected) return;
    const preset = qualitySelector.value;
    if (preset === 'auto_sync') {
      syncDisplayProfileWithHost(false);
      return;
    }

    if (preset === 'native_1to1') {
      setDisplayScaleMode(false);
    } else {
      setDisplayScaleMode(true);
    }

    // Flush stale pending frame immediately
    pendingFrameBlob = null;

    ws.send(JSON.stringify({
      type: 'set_quality_preset',
      preset: preset,
      req_id: ++qualityPresetReqId
    }));

    const presetKeyMap = {
      'native_1to1': 'deck.quality_native_1to1',
      'auto_sync': 'deck.quality_auto_sync',
      'ultra_120': 'deck.quality_ultra_120',
      'speed_60': 'deck.quality_speed',
      'crisp_2k_4k': 'deck.quality_crisp_2k_4k',
      'crisp_hd': 'deck.quality_hd',
      'balanced': 'deck.quality_balanced',
      'eco': 'deck.quality_eco',
      'grayscale': 'deck.quality_grayscale'
    };
    const presetFallbackVi = {
      'native_1to1': '1:1 Chuẩn gốc (Pixel-Perfect)',
      'auto_sync': 'Tự động tối ưu (Auto-Sync)',
      'ultra_120': '120 FPS Siêu mượt',
      'speed_60': '60 FPS Mượt mà (720p)',
      'crisp_2k_4k': '2K / 4K Cực nét (95%)',
      'crisp_hd': 'HD Nét (1080p // 85%)',
      'balanced': '30 FPS Cân bằng (900p)',
      'eco': 'Tiết kiệm băng thông (540p)',
      'grayscale': 'Tiết kiệm băng thông (Đơn sắc)'
    };
    const key = presetKeyMap[preset] || ('deck.quality_' + preset);
    const friendlyName = (window.MeikovaI18n ? window.MeikovaI18n.t(key) : null) || presetFallbackVi[preset] || preset;

    showToast(t('toast.preset_switching', { preset: friendlyName }), 'info');
  });

  // --- 1-CLICK DISPLAY AUTO-SYNC ---
  btnSyncDisplay?.addEventListener('click', () => {
    syncDisplayProfileWithHost(false);
  });

  // --- SCALE & FULLSCREEN ---
  btnScaleToggle.addEventListener('click', () => {
    setDisplayScaleMode(!isFitMode);
    showToast(isFitMode ? 'Chế độ: Co giãn vừa khung hình' : 'Chế độ: 1:1 Pixel-Perfect Nguyên bản', 'info');
  });

  btnFullscreen.addEventListener('click', async () => {
    if (!document.fullscreenElement) {
      try {
        await remoteSection.requestFullscreen();
        if (navigator.keyboard && navigator.keyboard.lock) {
          await navigator.keyboard.lock(['AltLeft', 'AltRight', 'Tab', 'Escape', 'MetaLeft', 'MetaRight', 'ControlLeft', 'ControlRight']);
        }
        showToast(t('toast.fullscreen_keys_locked'), 'info');
      } catch (err) {
        remoteSection.requestFullscreen().catch(() => {});
      }
    } else {
      if (navigator.keyboard && navigator.keyboard.unlock) {
        navigator.keyboard.unlock();
      }
      document.exitFullscreen().catch(() => {});
    }
  });

  document.addEventListener('fullscreenchange', () => {
    if (!document.fullscreenElement && navigator.keyboard && navigator.keyboard.unlock) {
      navigator.keyboard.unlock();
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
        if (!floatingDeck.matches(':hover') && !powerMenuDropdown.matches(':hover') && !(deckModeDropdown && deckModeDropdown.matches(':hover')) && !(qualityMenuDropdown && qualityMenuDropdown.matches(':hover'))) {
          floatingDeck.classList.add('dimmed');
        }
      }, 3500);
    }
  }

  remoteSection.addEventListener('mousemove', resetDeckIdle);
  remoteSection.addEventListener('mousedown', resetDeckIdle);
  remoteSection.addEventListener('touchstart', resetDeckIdle, { passive: true });
  floatingDeck.addEventListener('touchstart', resetDeckIdle, { passive: true });

  // --- MOUSE & TOUCH TRACKING & COORDINATE CONVERSION ---
  function getNormalizedCoords(e) {
    const rect = remoteCanvas.getBoundingClientRect();
    const clientX = e.clientX ?? (e.touches && e.touches[0] ? e.touches[0].clientX : 0);
    const clientY = e.clientY ?? (e.touches && e.touches[0] ? e.touches[0].clientY : 0);
    const normX = Math.max(0.0, Math.min(1.0, (clientX - rect.left) / rect.width));
    const normY = Math.max(0.0, Math.min(1.0, (clientY - rect.top) / rect.height));
    return {
      x: normX,
      y: normY,
      pixelX: normX * remoteCanvas.width,
      pixelY: normY * remoteCanvas.height
    };
  }

  // --- TOUCH FEEDBACK & RIPPLE GENERATOR ---
  function showTouchRipple(clientX, clientY, type = 'left') {
    const ripple = document.createElement('div');
    ripple.className = `touch-ripple touch-ripple--${type}`;
    ripple.style.left = `${clientX}px`;
    ripple.style.top = `${clientY}px`;
    document.body.appendChild(ripple);
    setTimeout(() => ripple.remove(), 450);
  }

  // --- MOBILE TOUCH CONTROLLER (Direct Tap / Multi-touch Gestures: 2-Finger Pan & Pinch, 2-Finger Tap Right Click, Hold-and-Drag) ---
  let mobileTouchMode = 'direct'; // 'direct' | 'trackpad'
  let touchStartX = 0;
  let touchStartY = 0;
  let touchStartTime = 0;
  let touchLastX = 0;
  let touchLastY = 0;
  let longPressTimer = null;
  let isLongPressTriggered = false;
  let isHoldDragActive = false;
  let lastTapTime = 0;
  let lastTapX = 0;
  let lastTapY = 0;
  let touchMoveThrottle = 0;

  // Two-finger multi-touch tracking
  let touchStartMidX = 0;
  let touchStartMidY = 0;
  let touchLastMidX = 0;
  let touchLastMidY = 0;
  let twoFingerTouchStartTime = 0;
  let twoFingerMoved = false;

  // Three-finger tracking
  let threeFingerTouchStartTime = 0;
  let threeFingerMoved = false;

  remoteCanvas.addEventListener('touchstart', (e) => {
    resetDeckIdle();
    if (e.touches.length === 1) {
      const t = e.touches[0];
      touchStartX = t.clientX;
      touchStartY = t.clientY;
      touchLastX = t.clientX;
      touchLastY = t.clientY;
      touchStartTime = performance.now();
      isLongPressTriggered = false;
      isHoldDragActive = false;

      // 380ms Hold timer: activates Hold-and-Drag (Mouse Left Down) if user holds and then moves
      if (longPressTimer) clearTimeout(longPressTimer);
      longPressTimer = setTimeout(() => {
        if (!isConnected) return;
        isLongPressTriggered = true;
        isHoldDragActive = true;
        if (navigator.vibrate) {
          try { navigator.vibrate(35); } catch {}
        }
        showTouchRipple(touchStartX, touchStartY, 'left');
        const coords = getNormalizedCoords({ clientX: touchStartX, clientY: touchStartY });
        ws.send(JSON.stringify({ type: 'mouse_move', x: coords.x, y: coords.y }));
        ws.send(JSON.stringify({ type: 'mouse_down', button: 0 }));
      }, 380);
    } else if (e.touches.length === 2) {
      if (longPressTimer) {
        clearTimeout(longPressTimer);
        longPressTimer = null;
      }
      if (isHoldDragActive) {
        isHoldDragActive = false;
        if (isConnected && ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'mouse_up', button: 0 }));
        }
      }
      e.preventDefault();
      const p1 = e.touches[0];
      const p2 = e.touches[1];
      touchStartDist = Math.hypot(p2.clientX - p1.clientX, p2.clientY - p1.clientY);
      touchStartScale = scale;
      touchStartMidX = (p1.clientX + p2.clientX) / 2;
      touchStartMidY = (p1.clientY + p2.clientY) / 2;
      touchLastMidX = touchStartMidX;
      touchLastMidY = touchStartMidY;
      twoFingerTouchStartTime = performance.now();
      twoFingerMoved = false;
    } else if (e.touches.length === 3) {
      if (longPressTimer) {
        clearTimeout(longPressTimer);
        longPressTimer = null;
      }
      e.preventDefault();
      threeFingerTouchStartTime = performance.now();
      threeFingerMoved = false;
    }
  }, { passive: false });

  remoteCanvas.addEventListener('touchmove', (e) => {
    resetDeckIdle();
    if (e.touches.length === 1) {
      const t = e.touches[0];
      const moveDist = Math.hypot(t.clientX - touchStartX, t.clientY - touchStartY);
      if (!isHoldDragActive && moveDist > 12) {
        if (longPressTimer) {
          clearTimeout(longPressTimer);
          longPressTimer = null;
        }
      }

      if (!isConnected) return;
      const now = performance.now();
      if (now - touchMoveThrottle < 20) return;
      touchMoveThrottle = now;

      const coords = getNormalizedCoords(t);
      if (isHoldDragActive) {
        // Dragging with left mouse button held down (select text, move window, drag file)
        ws.send(JSON.stringify({ type: 'mouse_move', x: coords.x, y: coords.y }));
      } else if (mobileTouchMode === 'direct') {
        ws.send(JSON.stringify({ type: 'mouse_move', x: coords.x, y: coords.y }));
      }
      touchLastX = t.clientX;
      touchLastY = t.clientY;
    } else if (e.touches.length === 2) {
      e.preventDefault();
      const p1 = e.touches[0];
      const p2 = e.touches[1];
      const currDist = Math.hypot(p2.clientX - p1.clientX, p2.clientY - p1.clientY);
      const currMidX = (p1.clientX + p2.clientX) / 2;
      const currMidY = (p1.clientY + p2.clientY) / 2;

      const dx = currMidX - touchLastMidX;
      const dy = currMidY - touchLastMidY;
      const distDiff = Math.abs(currDist - touchStartDist);
      const midDist = Math.hypot(currMidX - touchStartMidX, currMidY - touchStartMidY);

      if (midDist > 8 || distDiff > 10) {
        twoFingerMoved = true;
      }

      // Two-finger Pan: Fluidly move remote desktop viewport
      panX += dx;
      panY += dy;

      // Two-finger Pinch Zoom (anchored scale adjustment)
      if (touchStartDist > 0 && distDiff > 8) {
        const targetScale = touchStartScale * (currDist / touchStartDist);
        scale = Math.max(0.4, Math.min(5.0, targetScale));
      }

      applyCanvasTransform();

      touchLastMidX = currMidX;
      touchLastMidY = currMidY;
    } else if (e.touches.length === 3) {
      threeFingerMoved = true;
    }
  }, { passive: false });

  remoteCanvas.addEventListener('touchend', (e) => {
    if (longPressTimer) {
      clearTimeout(longPressTimer);
      longPressTimer = null;
    }

    // 1. Release Hold & Drag if it was active
    if (isHoldDragActive) {
      isHoldDragActive = false;
      isLongPressTriggered = false;
      if (isConnected && ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'mouse_up', button: 0 }));
      }
      return;
    }

    // 2. Three-finger Tap -> Toggle Preferred Keyboard (Phone Native Soft KB or Virtual OSK)
    if (e.touches.length === 0 && threeFingerTouchStartTime > 0) {
      const elapsed3 = performance.now() - threeFingerTouchStartTime;
      threeFingerTouchStartTime = 0;
      if (elapsed3 < 320 && !threeFingerMoved) {
        e.preventDefault();
        if (navigator.vibrate) try { navigator.vibrate([25, 40, 25]); } catch {}
        const pref = localStorage.getItem('meikova_keyboard_pref') || 'phone';
        if (pref === 'osk') {
          if (oskOverlay) {
            const isHidden = oskOverlay.classList.contains('hidden');
            oskOverlay.classList.toggle('hidden', !isHidden);
            btnToggleOSK?.classList.toggle('btn-active', isHidden);
            updateKeyboardMenuUI();
          }
        } else {
          if (document.activeElement === mobileVirtualInput) {
            closeMobileSoftKeyboard();
          } else {
            openMobileSoftKeyboard();
          }
        }
        return;
      }
    }

    // 3. Two-finger Tap -> Right Click at Midpoint
    if (e.touches.length === 0 && twoFingerTouchStartTime > 0) {
      const elapsed2 = performance.now() - twoFingerTouchStartTime;
      twoFingerTouchStartTime = 0;
      if (elapsed2 < 300 && !twoFingerMoved) {
        e.preventDefault();
        if (!isConnected || !ws || ws.readyState !== WebSocket.OPEN) return;
        if (navigator.vibrate) try { navigator.vibrate(45); } catch {}
        showTouchRipple(touchStartMidX, touchStartMidY, 'right');
        const coords = getNormalizedCoords({ clientX: touchStartMidX, clientY: touchStartMidY });
        ws.send(JSON.stringify({ type: 'mouse_move', x: coords.x, y: coords.y }));
        ws.send(JSON.stringify({ type: 'mouse_down', button: 2 }));
        setTimeout(() => {
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'mouse_up', button: 2 }));
          }
        }, 40);
        return;
      }
    }

    // 4. Single-finger Tap -> Left Click or Double Click
    if (e.changedTouches.length === 1 && e.touches.length === 0) {
      const t = e.changedTouches[0];
      const dist = Math.hypot(t.clientX - touchStartX, t.clientY - touchStartY);
      const duration = performance.now() - touchStartTime;

      if (dist <= 12 && duration < 380) {
        e.preventDefault();
        if (!isConnected || !ws || ws.readyState !== WebSocket.OPEN) return;

        const coords = getNormalizedCoords(t);
        const now = performance.now();
        const isDoubleTap = (now - lastTapTime < 320) && (Math.hypot(t.clientX - lastTapX, t.clientY - lastTapY) < 25);
        lastTapTime = now;
        lastTapX = t.clientX;
        lastTapY = t.clientY;

        showTouchRipple(t.clientX, t.clientY, 'left');

        // Send mouse position & click
        ws.send(JSON.stringify({ type: 'mouse_move', x: coords.x, y: coords.y }));
        ws.send(JSON.stringify({ type: 'mouse_down', button: 0 }));
        setTimeout(() => {
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'mouse_up', button: 0 }));
          }
          if (isDoubleTap) {
            // Second tap for native OS double click
            setTimeout(() => {
              if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'mouse_down', button: 0 }));
                setTimeout(() => {
                  if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({ type: 'mouse_up', button: 0 }));
                  }
                }, 35);
              }
            }, 60);
          }
        }, 35);
      }
    }
  }, { passive: false });

  // --- CURSOR SYNCHRONIZATION ---
  let currentHostCursor = 'default';

  function applyHostCursor(cursorName) {
    currentHostCursor = cursorName || 'default';
    if (remoteCanvas && !isCanvasPanning) {
      remoteCanvas.style.cursor = currentHostCursor;
    }
    document.querySelectorAll('.monitor-tile canvas').forEach(c => {
      c.style.cursor = currentHostCursor;
    });
  }

  let lastMove = 0;
  let isCanvasPanning = false;
  let panStartX = 0;
  let panStartY = 0;

  remoteCanvas.addEventListener('mousemove', (e) => {
    if (!isConnected || isCanvasPanning) return;
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

  remoteCanvas.addEventListener('mouseenter', () => {
    if (!isCanvasPanning) {
      remoteCanvas.style.cursor = currentHostCursor;
    }
  });

  remoteCanvas.addEventListener('mousedown', (e) => {
    if (!isConnected) return;
    if (e.button === 1 || (e.altKey && e.button === 0)) {
      isCanvasPanning = true;
      panStartX = e.clientX - panX;
      panStartY = e.clientY - panY;
      remoteCanvas.style.cursor = 'grabbing';
      e.preventDefault();
      return;
    }
    e.preventDefault();
    remoteCanvas.focus();
    ws.send(JSON.stringify({
      type: 'mouse_down',
      button: e.button
    }));
  });

  window.addEventListener('mousemove', (e) => {
    if (isCanvasPanning) {
      panX = e.clientX - panStartX;
      panY = e.clientY - panStartY;
      applyCanvasTransform();
      e.preventDefault();
    }
  });

  window.addEventListener('mouseup', (e) => {
    if (isCanvasPanning && (e.button === 1 || e.button === 0)) {
      isCanvasPanning = false;
      remoteCanvas.style.cursor = currentHostCursor;
      e.preventDefault();
    }
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

  // --- WEBCAM (FACE CAM PIP) ---
  btnToggleCam.addEventListener('click', () => toggleWebcam());

  async function toggleWebcam() {
    if (isWebcamActive) {
      stopWebcam();
      showToast(t('toast.cam_off'), 'info');
    } else {
      await startWebcam();
    }
  }

  async function startWebcam() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      showToast(t('toast.webcam_not_supported'), 'error');
      return;
    }
    try {
      webcamStream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' },
        audio: false
      });
      webcamVideo.srcObject = webcamStream;
      await webcamVideo.play();
      isWebcamActive = true;
      webcamContainer.classList.remove('hidden');
      camSvgOff.classList.add('hidden');
      camSvgOn.classList.remove('hidden');
      btnToggleCam.classList.add('btn-active');
      showToast(t('toast.cam_on'), 'success');
    } catch (err) {
      showToast(t('toast.cam_error', { error: err.message }), 'error');
      stopWebcam();
    }
  }

  function stopWebcam() {
    isWebcamActive = false;
    if (webcamStream) {
      try {
        webcamStream.getTracks().forEach(t => t.stop());
      } catch {}
      webcamStream = null;
    }
    if (webcamVideo) {
      webcamVideo.srcObject = null;
    }
    if (webcamContainer) {
      webcamContainer.classList.add('hidden');
    }
    if (camSvgOff && camSvgOn) {
      camSvgOff.classList.remove('hidden');
      camSvgOn.classList.add('hidden');
    }
    if (btnToggleCam) {
      btnToggleCam.classList.remove('btn-active');
    }
  }

  // --- SESSION RECORDING (WEBM) ---
  btnRecord.addEventListener('click', () => {
    if (!isConnected) {
      showToast(t('toast.connect_before_record'), 'info');
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
      let stream;
      if (isWebcamActive && webcamVideo && webcamVideo.readyState >= 2) {
        const recCanvas = document.createElement('canvas');
        recCanvas.width = remoteCanvas.width || 1920;
        recCanvas.height = remoteCanvas.height || 1080;
        const recCtx = recCanvas.getContext('2d');

        function renderComposite() {
          if (!isRecording) return;
          if (recCanvas.width !== (remoteCanvas.width || 1920) || recCanvas.height !== (remoteCanvas.height || 1080)) {
            recCanvas.width = remoteCanvas.width || 1920;
            recCanvas.height = remoteCanvas.height || 1080;
          }

          // 1. Remote screen canvas
          recCtx.drawImage(remoteCanvas, 0, 0, recCanvas.width, recCanvas.height);

          // 2. Face Cam PiP (bottom right corner)
          if (isWebcamActive && webcamVideo.readyState >= 2) {
            const pipW = Math.max(240, Math.round(recCanvas.width * 0.22));
            const aspect = (webcamVideo.videoWidth && webcamVideo.videoHeight)
              ? (webcamVideo.videoWidth / webcamVideo.videoHeight)
              : (16 / 9);
            const pipH = Math.round(pipW / aspect);
            const margin = Math.round(recCanvas.width * 0.02);
            const pipX = recCanvas.width - pipW - margin;
            const pipY = recCanvas.height - pipH - margin;
            const radius = 12;

            recCtx.save();
            recCtx.shadowColor = 'rgba(0, 0, 0, 0.7)';
            recCtx.shadowBlur = 16;
            recCtx.shadowOffsetX = 0;
            recCtx.shadowOffsetY = 6;

            recCtx.beginPath();
            if (recCtx.roundRect) {
              recCtx.roundRect(pipX, pipY, pipW, pipH, radius);
            } else {
              recCtx.rect(pipX, pipY, pipW, pipH);
            }
            recCtx.clip();

            // Mirror camera inside PiP
            recCtx.translate(pipX + pipW, pipY);
            recCtx.scale(-1, 1);
            recCtx.drawImage(webcamVideo, 0, 0, pipW, pipH);
            recCtx.restore();

            // PiP Border
            recCtx.save();
            recCtx.strokeStyle = '#38BDF8';
            recCtx.lineWidth = 3;
            recCtx.beginPath();
            if (recCtx.roundRect) {
              recCtx.roundRect(pipX, pipY, pipW, pipH, radius);
            } else {
              recCtx.rect(pipX, pipY, pipW, pipH);
            }
            recCtx.stroke();
            recCtx.restore();
          }

          recAnimId = requestAnimationFrame(renderComposite);
        }

        renderComposite();
        stream = recCanvas.captureStream(30);
      } else {
        stream = remoteCanvas.captureStream(30);
      }

      recordedChunks = [];
      mediaRecorder = new MediaRecorder(stream, { mimeType: 'video/webm' });
      mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) recordedChunks.push(e.data);
      };
      mediaRecorder.onstop = () => {
        if (recAnimId) {
          cancelAnimationFrame(recAnimId);
          recAnimId = null;
        }
        const blob = new Blob(recordedChunks, { type: 'video/webm' });
        downloadBlob(blob, `meikova-relay-session-${Date.now()}.webm`);
        recordedChunks = [];
        showToast(t('toast.record_saved'), 'success');
      };
      mediaRecorder.start();
      isRecording = true;
      btnRecord.classList.add('btn-active');
      btnRecord.title = t('deck.recording_title');
      showToast(isWebcamActive ? t('toast.record_with_cam') : t('toast.record_started'), 'info');
    } catch (err) {
      if (recAnimId) {
        cancelAnimationFrame(recAnimId);
        recAnimId = null;
      }
      showToast(t('toast.generic_error', { message: err.message }), 'error');
    }
  }

  function stopRecording() {
    if (recAnimId) {
      cancelAnimationFrame(recAnimId);
      recAnimId = null;
    }
    if (isRecording && mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
      isRecording = false;
      btnRecord.classList.remove('btn-active');
      btnRecord.title = t('deck.btn_record_title');
    }
  }

  // --- CANVAS SCREENSHOT (PNG) ---
  btnScreenshot.addEventListener('click', () => {
    if (!isConnected) {
      showToast(t('toast.not_connected'), 'info');
      return;
    }
    remoteCanvas.toBlob((blob) => {
      if (blob) {
        downloadBlob(blob, `meikova-relay-screen-${Date.now()}.png`);
        showToast(t('toast.screenshot_saved'), 'success');
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

  // --- LIVE AUDIO STREAMING ENGINE (WASAPI LOOPBACK -> WEB AUDIO) ---
  let isAudioStreaming = false;
  let audioContext = null;
  let nextAudioScheduledTime = 0;

  function initAudioContext() {
    if (!audioContext) {
      audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 48000 });
    }
    if (audioContext.state === 'suspended') {
      audioContext.resume();
    }
    return audioContext;
  }

  function playPcmAudioChunk(pcm16Bytes, sampleRate = 48000, channels = 2) {
    const ctx = initAudioContext();
    if (!ctx || ctx.state !== 'running') return;

    const int16Array = new Int16Array(pcm16Bytes);
    const numFrames = Math.floor(int16Array.length / channels);
    if (numFrames <= 0) return;

    const audioBuf = ctx.createBuffer(channels, numFrames, sampleRate);

    for (let ch = 0; ch < channels; ch++) {
      const channelData = audioBuf.getChannelData(ch);
      for (let i = 0; i < numFrames; i++) {
        channelData[i] = int16Array[i * channels + ch] / 32768.0;
      }
    }

    const source = ctx.createBufferSource();
    source.buffer = audioBuf;
    source.connect(ctx.destination);

    const now = ctx.currentTime;
    if (nextAudioScheduledTime < now) {
      nextAudioScheduledTime = now + 0.025; // 25ms jitter buffer
    } else if (nextAudioScheduledTime > now + 0.25) {
      nextAudioScheduledTime = now + 0.05;
    }

    source.start(nextAudioScheduledTime);
    nextAudioScheduledTime += audioBuf.duration;
  }

  function toggleAudioStream(enable) {
    if (!isConnected || !ws) {
      showToast(t('toast.connect_before_audio'), 'info');
      return;
    }
    const targetState = (enable !== undefined) ? enable : !isAudioStreaming;
    if (targetState) {
      initAudioContext();
    }
    ws.send(JSON.stringify({
      type: 'audio_stream_toggle',
      enabled: targetState
    }));
  }

  function updateAudioStreamUi(enabled) {
    isAudioStreaming = enabled;
    if (btnToggleAudio) {
      btnToggleAudio.classList.toggle('btn-active', isAudioStreaming);
      audioSvgMuted?.classList.toggle('hidden', isAudioStreaming);
      audioSvgPlaying?.classList.toggle('hidden', !isAudioStreaming);
      btnToggleAudio.title = isAudioStreaming ? 'Tắt âm thanh máy trạm' : 'Bật âm thanh máy trạm (Live Audio)';
    }
  }

  if (btnToggleAudio) {
    btnToggleAudio.addEventListener('click', () => {
      toggleAudioStream();
    });
  }

  // --- VOICE INTERCOM ENGINE (CLIENT MIC -> HOST SPEAKERS) ---
  let isMicStreaming = false;
  let micMediaStream = null;
  let micAudioContext = null;
  let micScriptProcessor = null;

  async function startMicStream() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      showToast(t('toast.mic_not_supported'), 'error');
      return;
    }
    try {
      micMediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          channelCount: 1
        }
      });

      // Sample rate: 16000Hz (crystal clear for voice, ~32KB/s)
      micAudioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
      const micSource = micAudioContext.createMediaStreamSource(micMediaStream);

      // ScriptProcessor: 2048 buffer size (~128ms per chunk)
      micScriptProcessor = micAudioContext.createScriptProcessor(2048, 1, 1);
      micScriptProcessor.onaudioprocess = (e) => {
        if (!isMicStreaming || !ws || ws.readyState !== WebSocket.OPEN) return;
        const inputData = e.inputBuffer.getChannelData(0);
        const pcm16 = new Int16Array(inputData.length);
        for (let i = 0; i < inputData.length; i++) {
          const s = Math.max(-1, Math.min(1, inputData[i]));
          pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }

        // Convert pcm16 to base64
        let binary = '';
        const bytes = new Uint8Array(pcm16.buffer);
        const len = bytes.byteLength;
        for (let i = 0; i < len; i++) {
          binary += String.fromCharCode(bytes[i]);
        }
        const b64 = btoa(binary);

        ws.send(JSON.stringify({
          type: 'client_mic_chunk',
          data: b64,
          rate: micAudioContext.sampleRate,
          channels: 1
        }));
      };

      micSource.connect(micScriptProcessor);
      micScriptProcessor.connect(micAudioContext.destination);

      isMicStreaming = true;
      updateMicUi(true);

      ws.send(JSON.stringify({
        type: 'client_mic_toggle',
        enabled: true,
        sample_rate: micAudioContext.sampleRate,
        channels: 1
      }));
      showToast(t('toast.voice_transmitting'), 'success');
    } catch (err) {
      showToast(t('toast.generic_error', { message: err.message }), 'error');
      stopMicStream();
    }
  }

  function stopMicStream() {
    isMicStreaming = false;
    updateMicUi(false);

    if (micScriptProcessor) {
      try { micScriptProcessor.disconnect(); } catch {}
      micScriptProcessor = null;
    }
    if (micMediaStream) {
      try {
        micMediaStream.getTracks().forEach(track => track.stop());
      } catch {}
      micMediaStream = null;
    }
    if (micAudioContext && micAudioContext.state !== 'closed') {
      try { micAudioContext.close(); } catch {}
      micAudioContext = null;
    }

    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'client_mic_toggle',
        enabled: false
      }));
    }
  }

  function toggleMicStream() {
    if (!isConnected || !ws) {
      showToast(t('toast.connect_before_mic'), 'info');
      return;
    }
    if (isMicStreaming) {
      stopMicStream();
      showToast(t('toast.voice_stopped'), 'info');
    } else {
      startMicStream();
    }
  }

  function updateMicUi(enabled) {
    isMicStreaming = enabled;
    if (btnToggleMic) {
      btnToggleMic.classList.toggle('btn-active', isMicStreaming);
      micSvgMuted?.classList.toggle('hidden', isMicStreaming);
      micSvgActive?.classList.toggle('hidden', !isMicStreaming);
      btnToggleMic.title = isMicStreaming ? 'Tắt micro nói sang máy trạm' : 'Bật micro nói sang máy trạm (Live Voice)';
    }
  }

  if (btnToggleMic) {
    btnToggleMic.addEventListener('click', toggleMicStream);
  }

  // --- SEAMLESS 2-WAY BACKGROUND CLIPBOARD SYNC ---
  let lastSyncedClientClipboard = '';

  window.addEventListener('paste', async (e) => {
    if (!isConnected) return;
    const activeEl = document.activeElement;
    const tag = activeEl ? activeEl.tagName.toLowerCase() : '';
    if (tag === 'input' || tag === 'textarea' || (activeEl && activeEl.isContentEditable)) return;

    // A. Handle File Explorer internal clipboard paste (Ctrl+V)
    if (currentView === 'files' && explorerClipboard && explorerClipboard.path) {
      e.preventDefault();
      executePasteAction();
      return;
    }

    // B. Check if user is pasting an IMAGE
    let imageItem = null;
    if (e.clipboardData?.items) {
      for (let i = 0; i < e.clipboardData.items.length; i++) {
        const it = e.clipboardData.items[i];
        if (it.type.startsWith('image/')) {
          imageItem = it.getAsFile();
          break;
        }
      }
    }
    if (!imageItem && e.clipboardData?.files?.length === 1 && e.clipboardData.files[0].type.startsWith('image/')) {
      imageItem = e.clipboardData.files[0];
    }

    if (imageItem && currentView === 'remote' && ws && ws.readyState === WebSocket.OPEN) {
      e.preventDefault();
      showToast(t('toast.pasting_image'), 'info');
      const reader = new FileReader();
      reader.onload = () => {
        const b64 = reader.result.split(',')[1];
        ws.send(JSON.stringify({
          type: 'clipboard_sync_image',
          data: b64,
          mime: imageItem.type,
          auto_paste: true
        }));
      };
      reader.readAsDataURL(imageItem);
      return;
    }

    // C. Handle regular file paste onto Remote Desktop screen or File Explorer
    if (e.clipboardData && e.clipboardData.files && e.clipboardData.files.length > 0) {
      e.preventDefault();
      const files = await getFilesFromDataTransfer(e.clipboardData);
      if (files.length > 0) {
        if (currentView === 'remote') {
          showToast(t('toast.transferring_files_desktop', { count: files.length }), 'info');
          files.forEach(f => uploadFileToHost(f, 'desktop'));
        } else if (currentView === 'files') {
          showToast(t('toast.pasting_files_cur_dir', { count: files.length }), 'info');
          files.forEach(f => uploadFileToHost(f, remoteCurrentPath));
        }
      }
      return;
    }

    // D. Handle text clipboard paste to remote screen (Instant auto-paste on host)
    if (currentView !== 'remote') return;
    e.preventDefault();
    const pastedText = e.clipboardData?.getData('text');
    if (pastedText && ws && ws.readyState === WebSocket.OPEN) {
      lastSyncedClientClipboard = pastedText;
      ws.send(JSON.stringify({
        type: 'clipboard_sync',
        text: pastedText,
        auto_paste: true
      }));
    }
  });


  // --- Universal Multi-Type Clipboard Synchronization Engine ---
  let currentClipboardImageData = null;

  function handleIncomingClipboardImage(b64Data, mime) {
    if (!b64Data) return;
    mime = mime || 'image/png';
    currentClipboardImageData = { data: b64Data, mime };

    const container = document.getElementById('shelfClipImageContainer');
    const preview = document.getElementById('shelfClipImagePreview');
    const meta = document.getElementById('shelfClipImageMeta');
    if (container && preview) {
      preview.src = `data:${mime};base64,${b64Data}`;
      container.classList.remove('hidden');
      const approxKb = Math.round((b64Data.length * 0.75) / 1024);
      if (meta) meta.textContent = `${(mime.split('/')[1] || 'IMAGE').toUpperCase()} • ${approxKb} KB`;
    }

    try {
      const byteCharacters = atob(b64Data);
      const byteNumbers = new Array(byteCharacters.length);
      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
      }
      const byteArray = new Uint8Array(byteNumbers);
      const blob = new Blob([byteArray], { type: mime });
      if (navigator.clipboard && window.ClipboardItem) {
        navigator.clipboard.write([new ClipboardItem({ [blob.type]: blob })]).catch(() => {});
      }
    } catch (e) {
      console.warn('Clipboard image parse error:', e);
    }
  }

  function handleIncomingClipboardFiles(files) {
    if (!Array.isArray(files) || files.length === 0) return;
    const names = files.map(p => p.split(/[\\/]/).pop()).slice(0, 3).join(', ');
    const more = files.length > 3 ? ` (+${files.length - 3})` : '';
    // Silenced high-frequency file clipboard toast
  }

  const btnDownloadClipImage = document.getElementById('btnDownloadClipImage');
  if (btnDownloadClipImage) {
    btnDownloadClipImage.addEventListener('click', () => {
      if (!currentClipboardImageData) return;
      const a = document.createElement('a');
      a.href = `data:${currentClipboardImageData.mime};base64,${currentClipboardImageData.data}`;
      const ext = currentClipboardImageData.mime.includes('jpeg') ? 'jpg' : 'png';
      a.download = `remote_clip_${Date.now()}.${ext}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    });
  }

  // Client Copy Event: Sync local copy to host immediately
  window.addEventListener('copy', async () => {
    if (!isConnected || ws?.readyState !== WebSocket.OPEN) return;
    try {
      if (navigator.clipboard) {
        setTimeout(async () => {
          if (navigator.clipboard.read) {
            try {
              const items = await navigator.clipboard.read();
              for (const it of items) {
                for (const type of it.types) {
                  if (type.startsWith('image/')) {
                    const blob = await it.getType(type);
                    const reader = new FileReader();
                    reader.onload = () => {
                      const b64 = reader.result.split(',')[1];
                      ws.send(JSON.stringify({
                        type: 'clipboard_sync_image',
                        data: b64,
                        mime: type,
                        auto_paste: false
                      }));
                    };
                    reader.readAsDataURL(blob);
                    return;
                  }
                }
              }
            } catch {}
          }
          if (navigator.clipboard.readText) {
            const text = await navigator.clipboard.readText();
            if (text && text !== lastSyncedClientClipboard && ws && ws.readyState === WebSocket.OPEN) {
              lastSyncedClientClipboard = text;
              ws.send(JSON.stringify({
                type: 'clipboard_sync',
                text: text
              }));
            }
          }
        }, 50);
      }
    } catch {}
  });

  window.addEventListener('focus', async () => {
    if (!isConnected || currentView !== 'remote') return;
    try {
      if (navigator.clipboard && navigator.clipboard.readText) {
        const text = await navigator.clipboard.readText();
        if (text && text !== lastSyncedClientClipboard && ws && ws.readyState === WebSocket.OPEN) {
          lastSyncedClientClipboard = text;
          ws.send(JSON.stringify({
            type: 'clipboard_sync',
            text: text
          }));
        }
      }
    } catch {}
  });

  // --- KEYBOARD CAPTURE (PREVENT LEAKS INTO TEXT INPUTS & FULL VIETNAMESE SUPPORT) ---
  window.addEventListener('keydown', (e) => {
    if (!isConnected || currentView !== 'remote') return;

    // Do NOT capture keys when user is typing into an input field or textarea
    const activeEl = document.activeElement;
    const tag = activeEl ? activeEl.tagName.toLowerCase() : '';
    if (tag === 'input' || tag === 'textarea' || tag === 'select' || (activeEl && activeEl.isContentEditable)) {
      return;
    }

    // Avoid double paste / race condition on Ctrl+V:
    // Let browser paste event capture client clipboard, sync to host, and trigger remote paste!
    if ((e.ctrlKey || e.metaKey) && (e.code === 'KeyV' || e.key === 'v' || e.key === 'V')) {
      return;
    }

    // Intercept printable Unicode diacritics & synthetic IME/Unikey replacement keys:
    // Unikey synthesizes Backspaces then injects replacement characters like â, đ, ê, ơ, ư, etc.
    // In browser, these synthetic keys have charCode > 127 or unmapped/empty e.code ('', 'Unidentified', 'Process')
    if (!e.ctrlKey && !e.altKey && !e.metaKey && e.key && e.key.length === 1) {
      const charCode = e.key.charCodeAt(0);
      const isUnicodeDiacritic = charCode > 127;
      const isSyntheticIME = (!e.code || e.code === 'Unidentified' || e.code === 'Process');
      if (isUnicodeDiacritic || isSyntheticIME) {
        ws.send(JSON.stringify({
          type: 'text_input',
          text: e.key
        }));
        return;
      }
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

    // Skip synthetic/Unicode characters already handled via text_input
    if (!e.ctrlKey && !e.altKey && !e.metaKey && e.key && e.key.length === 1) {
      if (e.key.charCodeAt(0) > 127 || !e.code || e.code === 'Unidentified' || e.code === 'Process') {
        return;
      }
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

  // Capture IME composition completion (MacOS Telex, Windows IME, Android Gboard)
  window.addEventListener('compositionend', (e) => {
    if (!isConnected || currentView !== 'remote') return;
    const activeEl = document.activeElement;
    const tag = activeEl ? activeEl.tagName.toLowerCase() : '';
    if (tag === 'input' || tag === 'textarea' || tag === 'select' || (activeEl && activeEl.isContentEditable)) {
      return;
    }
    if (e.data && ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'text_input', text: e.data }));
    }
  });

  // Hotkey Buttons on Deck & Mobile Quick Keys Bar
  document.querySelectorAll('[data-hotkey]').forEach(btn => {
    btn.addEventListener('click', () => {
      if (!isConnected) return;
      const key = btn.dataset.hotkey;
      if (key === 'win') {
        sendKeySequence([0x5B]);
      } else if (key === 'taskmgr' || key === 'cad') {
        // Ctrl+Alt+Del for Windows unlock / Task Manager
        sendHotKeyCombo([0x11, 0x12, 0x2E]);
        showToast(t('toast.cad_sent'), 'info', 1200);
      } else if (key === 'alttab') {
        sendHotKeyCombo([0x12, 0x09]); // Alt+Tab
      } else if (key === 'esc') {
        sendKeySequence([0x1B]);
      } else if (key === 'tab') {
        sendKeySequence([0x09]);
      } else if (key === 'space') {
        sendKeySequence([0x20]);
      } else if (key === 'enter') {
        sendKeySequence([0x0D]);
      } else if (key === 'backspace') {
        sendKeySequence([0x08]);
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

  // --- MOBILE KEYBOARD CONTROLLER & BRIDGE ---
  function updateKeyboardMenuUI() {
    const isPhoneActive = (document.activeElement === mobileVirtualInput);
    const isOskActive = (oskOverlay && !oskOverlay.classList.contains('hidden'));

    if (checkPhoneKeyboard) {
      checkPhoneKeyboard.classList.toggle('hidden', !isPhoneActive);
    }
    if (checkVirtualOSK) {
      checkVirtualOSK.classList.toggle('hidden', !isOskActive);
    }
    if (btnOptPhoneKeyboard) {
      btnOptPhoneKeyboard.classList.toggle('active', isPhoneActive);
    }
    if (btnOptVirtualOSK) {
      btnOptVirtualOSK.classList.toggle('active', isOskActive);
    }
    if (btnMobileKeyboard) {
      btnMobileKeyboard.classList.toggle('btn-active', isPhoneActive || isOskActive);
    }
    if (btnToggleOSK) {
      btnToggleOSK.classList.toggle('btn-active', isOskActive);
    }
  }

  function openMobileSoftKeyboard() {
    if (!mobileVirtualInput) return;
    mobileVirtualInput.value = '';
    mobileVirtualInput.focus({ preventScroll: true });
    updateKeyboardMenuUI();
  }

  function closeMobileSoftKeyboard() {
    if (!mobileVirtualInput) return;
    mobileVirtualInput.blur();
    updateKeyboardMenuUI();
  }

  if (btnMobileKeyboard && keyboardMenuDropdown) {
    btnMobileKeyboard.addEventListener('click', (e) => {
      e.stopPropagation();
      const isOpening = keyboardMenuDropdown.classList.contains('hidden');
      monitorMenuDropdown?.classList.add('hidden');
      btnMonitorMenu?.classList.remove('btn-active');
      resolutionMenuDropdown?.classList.add('hidden');
      btnResolutionMenu?.classList.remove('btn-active');
      qualityMenuDropdown?.classList.add('hidden');
      btnQualityMenu?.classList.remove('btn-active');
      protocolMenuDropdown?.classList.add('hidden');
      btnProtocolMenu?.classList.remove('btn-active');
      powerMenuDropdown?.classList.add('hidden');
      btnPowerMenu?.classList.remove('btn-active');
      deckModeDropdown?.classList.add('hidden');
      btnDeckDisplayMode?.classList.remove('btn-active');
      snippetsMenuDropdown?.classList.add('hidden');
      btnSnippetsMenu?.classList.remove('btn-active');

      keyboardMenuDropdown.classList.toggle('hidden', !isOpening);
      if (isOpening) {
        updateKeyboardMenuUI();
        positionDeckDropdown(btnMobileKeyboard, keyboardMenuDropdown);
      } else {
        updateKeyboardMenuUI();
      }
    });

    btnOptPhoneKeyboard?.addEventListener('click', (e) => {
      e.stopPropagation();
      localStorage.setItem('meikova_keyboard_pref', 'phone');
      keyboardMenuDropdown.classList.add('hidden');
      if (oskOverlay && !oskOverlay.classList.contains('hidden')) {
        oskOverlay.classList.add('hidden');
        btnToggleOSK?.classList.remove('btn-active');
      }
      if (document.activeElement === mobileVirtualInput) {
        closeMobileSoftKeyboard();
        // soft keyboard closed
      } else {
        openMobileSoftKeyboard();
        // soft keyboard opened
      }
      updateKeyboardMenuUI();
    });

    btnOptVirtualOSK?.addEventListener('click', (e) => {
      e.stopPropagation();
      localStorage.setItem('meikova_keyboard_pref', 'osk');
      keyboardMenuDropdown.classList.add('hidden');
      if (mobileVirtualInput && document.activeElement === mobileVirtualInput) {
        closeMobileSoftKeyboard();
      }
      if (oskOverlay) {
        const isHidden = oskOverlay.classList.contains('hidden');
        oskOverlay.classList.toggle('hidden', !isHidden);
        btnToggleOSK?.classList.toggle('btn-active', isHidden);
        if (isHidden) {
          // osk opened
        } else {
          // osk closed
        }
      }
      updateKeyboardMenuUI();
    });
  }

  if (btnCloseOSK) {
    btnCloseOSK.addEventListener('click', (e) => {
      e.stopPropagation();
      if (oskOverlay) oskOverlay.classList.add('hidden');
      btnToggleOSK?.classList.remove('btn-active');
      updateKeyboardMenuUI();
      // osk closed
    });
  }

  if (mobileVirtualInput) {
    let isVirtualComposing = false;

    mobileVirtualInput.addEventListener('focus', () => {
      updateKeyboardMenuUI();
    });

    mobileVirtualInput.addEventListener('blur', () => {
      updateKeyboardMenuUI();
    });

    mobileVirtualInput.addEventListener('compositionstart', () => {
      isVirtualComposing = true;
    });

    mobileVirtualInput.addEventListener('compositionend', (e) => {
      isVirtualComposing = false;
      const text = e.data || mobileVirtualInput.value;
      if (text && ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'text_input', text }));
      }
      mobileVirtualInput.value = '';
    });

    mobileVirtualInput.addEventListener('input', (e) => {
      if (isVirtualComposing || e.isComposing) return;
      const text = mobileVirtualInput.value;
      if (text && ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'text_input', text }));
        mobileVirtualInput.value = '';
      }
    });

    mobileVirtualInput.addEventListener('keydown', (e) => {
      if (!ws || ws.readyState !== WebSocket.OPEN) return;
      if (e.key === 'Backspace' || e.keyCode === 8) {
        e.preventDefault();
        sendKeySequence([0x08]);
      } else if (e.key === 'Enter' || e.keyCode === 13) {
        e.preventDefault();
        sendKeySequence([0x0D]);
      } else if (e.key === 'Tab' || e.keyCode === 9) {
        e.preventDefault();
        sendKeySequence([0x09]);
      } else if (e.key === 'Escape' || e.keyCode === 27) {
        e.preventDefault();
        sendKeySequence([0x1B]);
      }
    });
  }

  // --- MOBILE QUICK KEYS STRIP CONTROLS ---
  if (btnMobileQuickKeysToggle && mobileQuickKeysBar) {
    btnMobileQuickKeysToggle.addEventListener('click', (e) => {
      e.stopPropagation();
      const isHidden = mobileQuickKeysBar.classList.toggle('hidden');
      btnMobileQuickKeysToggle.classList.toggle('active', !isHidden);
    });
  }

  if (btnCloseQuickKeys && mobileQuickKeysBar) {
    btnCloseQuickKeys.addEventListener('click', (e) => {
      e.stopPropagation();
      mobileQuickKeysBar.classList.add('hidden');
      if (btnMobileQuickKeysToggle) btnMobileQuickKeysToggle.classList.remove('active');
    });
  }

  // --- MOBILE IMMERSIVE QUICK EXIT BUTTON ---
  if (btnMobileImmersiveExit) {
    btnMobileImmersiveExit.addEventListener('click', (e) => {
      e.stopPropagation();
      if (isConnected) {
        disconnect();
      } else {
        switchView(authToken ? 'dashboard' : 'landing', true);
      }
    });
  }

  // --- MOBILE DEDICATED RIGHT-CLICK BUTTON ---
  if (btnMobileRightClick) {
    btnMobileRightClick.addEventListener('click', (e) => {
      e.stopPropagation();
      if (!isConnected || !ws || ws.readyState !== WebSocket.OPEN) return;
      ws.send(JSON.stringify({ type: 'mouse_down', button: 2 }));
      setTimeout(() => {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'mouse_up', button: 2 }));
        }
      }, 40);
      showToast(t('toast.right_click'), 'info', 1000);
    });
  }

  // --- MOBILE TOUCH MODE TOGGLE (Direct Tap vs Virtual Mouse Trackpad) ---
  if (btnMobileTouchMode && touchModeLabel) {
    btnMobileTouchMode.addEventListener('click', (e) => {
      e.stopPropagation();
      mobileTouchMode = (mobileTouchMode === 'direct') ? 'trackpad' : 'direct';
      touchModeLabel.textContent = (mobileTouchMode === 'direct') ? 'Chạm' : 'Chuột';
      btnMobileTouchMode.classList.toggle('active', mobileTouchMode === 'trackpad');
      showToast(mobileTouchMode === 'direct' ? 'Chế độ cảm ứng: Chạm trực tiếp' : 'Chế độ cảm ứng: Bàn di chuột', 'info', 1500);
    });
  }

  // --- DECK DISPLAY MODES (BOTTOM FLOAT / TOP PINNED / TOP UNPINNED) ---
  let currentDeckMode = localStorage.getItem('meikova_deck_mode') || 'bottom-float';
  let deckPeekTimer = null;

  function applyDeckMode(mode) {
    if (!['bottom-float', 'top-pinned', 'top-unpinned'].includes(mode)) {
      mode = 'bottom-float';
    }
    currentDeckMode = mode;
    localStorage.setItem('meikova_deck_mode', mode);

    // Reset modifier classes
    floatingDeck.classList.remove('deck--bottom', 'deck--top-pinned', 'deck--top-unpinned', 'deck--peek');
    remoteSection.classList.remove('deck-at-top');

    // Update menu items
    if (checkModeBottom) checkModeBottom.classList.toggle('hidden', mode !== 'bottom-float');
    if (checkModeTopPinned) checkModeTopPinned.classList.toggle('hidden', mode !== 'top-pinned');
    if (checkModeTopUnpinned) checkModeTopUnpinned.classList.toggle('hidden', mode !== 'top-unpinned');

    document.querySelectorAll('.deck-mode-item').forEach(el => {
      el.classList.toggle('active', el.dataset.deckMode === mode);
    });

    if (mode === 'bottom-float') {
      floatingDeck.classList.add('deck--bottom');
      if (deckIconBottom) deckIconBottom.classList.remove('hidden');
      if (deckIconTopPinned) deckIconTopPinned.classList.add('hidden');
      if (deckIconTopUnpinned) deckIconTopUnpinned.classList.add('hidden');
      if (btnDeckPinQuick) btnDeckPinQuick.classList.add('hidden');
      if (deckTopTrigger) deckTopTrigger.classList.add('hidden');
    } else if (mode === 'top-pinned') {
      floatingDeck.classList.add('deck--top-pinned');
      remoteSection.classList.add('deck-at-top');
      if (deckIconBottom) deckIconBottom.classList.add('hidden');
      if (deckIconTopPinned) deckIconTopPinned.classList.remove('hidden');
      if (deckIconTopUnpinned) deckIconTopUnpinned.classList.add('hidden');
      if (btnDeckPinQuick) {
        btnDeckPinQuick.classList.remove('hidden');
        deckSvgPinActive.classList.remove('hidden');
        deckSvgPinInactive.classList.add('hidden');
        btnDeckPinQuick.title = (typeof i18n !== 'undefined' && i18n.t) ? i18n.t('deck.pin_tooltip_unpin') : 'Đang ghim mép trên. Bấm để Tự động ẩn';
      }
      if (deckTopTrigger) deckTopTrigger.classList.add('hidden');
    } else if (mode === 'top-unpinned') {
      floatingDeck.classList.add('deck--top-unpinned');
      remoteSection.classList.add('deck-at-top');
      if (deckIconBottom) deckIconBottom.classList.add('hidden');
      if (deckIconTopPinned) deckIconTopPinned.classList.add('hidden');
      if (deckIconTopUnpinned) deckIconTopUnpinned.classList.remove('hidden');
      if (btnDeckPinQuick) {
        btnDeckPinQuick.classList.remove('hidden');
        deckSvgPinActive.classList.add('hidden');
        deckSvgPinInactive.classList.remove('hidden');
        btnDeckPinQuick.title = (typeof i18n !== 'undefined' && i18n.t) ? i18n.t('deck.pin_tooltip_pin') : 'Đang tự động ẩn. Bấm để Ghim cố định';
      }
      if (deckTopTrigger) deckTopTrigger.classList.remove('hidden');
    }
  }

  // Toggle Deck Mode Popover
  if (btnDeckDisplayMode) {
    btnDeckDisplayMode.addEventListener('click', (e) => {
      e.stopPropagation();
      if (deckModeDropdown) {
        const isOpening = deckModeDropdown.classList.contains('hidden');
        deckModeDropdown.classList.toggle('hidden');
        btnDeckDisplayMode.classList.toggle('btn-active', isOpening);
        if (isOpening) {
          positionDeckDropdown(btnDeckDisplayMode, deckModeDropdown);
        }
      }
      if (powerMenuDropdown) {
        powerMenuDropdown.classList.add('hidden');
        if (btnPowerMenu) btnPowerMenu.classList.remove('btn-active');
      }
      if (qualityMenuDropdown) {
        qualityMenuDropdown.classList.add('hidden');
        if (btnQualityMenu) btnQualityMenu.classList.remove('btn-active');
      }
      if (protocolMenuDropdown) {
        protocolMenuDropdown.classList.add('hidden');
        if (btnProtocolMenu) btnProtocolMenu.classList.remove('btn-active');
      }
    });
  }

  // Quick Pin/Unpin Toggle Shortcut Button
  if (btnDeckPinQuick) {
    btnDeckPinQuick.addEventListener('click', (e) => {
      e.stopPropagation();
      if (currentDeckMode === 'top-pinned') {
        applyDeckMode('top-unpinned');
        showToast((typeof i18n !== 'undefined' && i18n.t) ? i18n.t('deck.mode_top_unpinned') : 'Mép trên: Tự động ẩn khi rời chuột', 'info');
      } else {
        applyDeckMode('top-pinned');
        showToast((typeof i18n !== 'undefined' && i18n.t) ? i18n.t('deck.mode_top_pinned') : 'Mép trên: Ghim cố định', 'info');
      }
    });
  }

  // Mode Selection in Dropdown
  document.querySelectorAll('[data-deck-mode]').forEach(item => {
    item.addEventListener('click', () => {
      const mode = item.dataset.deckMode;
      applyDeckMode(mode);
      if (deckModeDropdown) {
        deckModeDropdown.classList.add('hidden');
      }
      const i18nKey = mode === 'bottom-float' ? 'deck.mode_bottom' : `deck.mode_${mode.replace('-', '_')}`;
      const label = (typeof i18n !== 'undefined' && i18n.t) ? (i18n.t(i18nKey) || i18n.t(`deck.mode_${mode.replace('-', '_')}`)) : mode;
      showToast(label, 'info');
    });
  });

  // Top Edge Reveal (Hover Peek) for Unpinned Mode
  function triggerDeckPeek() {
    if (currentDeckMode !== 'top-unpinned') return;
    clearTimeout(deckPeekTimer);
    floatingDeck.classList.add('deck--peek');
  }

  function releaseDeckPeek() {
    if (currentDeckMode !== 'top-unpinned') return;
    clearTimeout(deckPeekTimer);
    deckPeekTimer = setTimeout(() => {
      if (!floatingDeck.matches(':hover') && !(deckModeDropdown && !deckModeDropdown.classList.contains('hidden')) && !(powerMenuDropdown && !powerMenuDropdown.classList.contains('hidden')) && !(qualityMenuDropdown && !qualityMenuDropdown.classList.contains('hidden'))) {
        floatingDeck.classList.remove('deck--peek');
      }
    }, 450);
  }

  if (deckTopTrigger) {
    deckTopTrigger.addEventListener('mouseenter', triggerDeckPeek);
    deckTopTrigger.addEventListener('mouseleave', releaseDeckPeek);
    deckTopTrigger.addEventListener('click', (e) => {
      e.stopPropagation();
      if (floatingDeck.classList.contains('deck--peek')) {
        floatingDeck.classList.remove('deck--peek');
      } else {
        triggerDeckPeek();
      }
    });
    // Touch support for iPad / iOS / Mobile
    deckTopTrigger.addEventListener('touchstart', (e) => {
      e.stopPropagation();
      floatingDeck.classList.toggle('deck--peek');
    }, { passive: true });
  }

  // Reveal deck when cursor hovers near top 14px of viewport
  remoteSection.addEventListener('mousemove', (e) => {
    if (currentDeckMode === 'top-unpinned' && isConnected && currentView === 'remote') {
      if (e.clientY <= 14) {
        triggerDeckPeek();
      }
    }
  });

  floatingDeck.addEventListener('mouseenter', () => {
    if (currentDeckMode === 'top-unpinned') {
      clearTimeout(deckPeekTimer);
      floatingDeck.classList.add('deck--peek');
    }
  });

  floatingDeck.addEventListener('mouseleave', () => {
    if (currentDeckMode === 'top-unpinned') {
      releaseDeckPeek();
    }
  });


  // --- PROTOCOL MATRIX & NEGOTIATION LOGIC ---
  function updateProtocolUI(matrix) {
    if (!matrix) return;
    const isVi = !window.MeikovaI18n || window.MeikovaI18n.currentLang === 'vi';

    // 1. Remote Desktop (RDP 3389 / VNC 5900)
    if (matrix.remote && matrix.remote.rdp) {
      const rdp = matrix.remote.rdp;
      if (rdp.available) {
        if (protoBadgeRdp) {
          protoBadgeRdp.className = 'proto-status-pill ready';
          protoBadgeRdp.textContent = isVi ? 'RDP: SẴN SÀNG' : 'RDP: READY';
        }
        if (protoDescRdp) {
          protoDescRdp.textContent = rdp.details || (isVi ? 'Port 3389 mở (X.224 xác nhận)' : 'Port 3389 active (X.224)');
        }
        if (btnDownloadRdp) btnDownloadRdp.style.display = 'inline-flex';
      } else {
        if (protoBadgeRdp) {
          protoBadgeRdp.className = 'proto-status-pill closed';
          protoBadgeRdp.textContent = isVi ? 'RDP: ĐÃ ĐÓNG' : 'RDP: CLOSED';
        }
        if (protoDescRdp) {
          protoDescRdp.textContent = isVi ? 'Port 3389 đóng → Dùng Meikova Stream' : 'Port 3389 closed → Fallback to Meikova Stream';
        }
        if (btnDownloadRdp) btnDownloadRdp.style.display = 'none';
      }
    }

    // 2. Terminal (SSH 22)
    if (matrix.terminal && matrix.terminal.ssh) {
      const ssh = matrix.terminal.ssh;
      if (ssh.available) {
        if (protoBadgeSsh) {
          protoBadgeSsh.className = 'proto-status-pill ready';
          protoBadgeSsh.textContent = isVi ? 'SSH: SẴN SÀNG' : 'SSH: READY';
        }
        if (protoDescSsh) {
          protoDescSsh.textContent = ssh.details || (isVi ? 'OpenSSH Server khả dụng' : 'OpenSSH Server ready');
        }
        if (btnCopySshCmd) btnCopySshCmd.style.display = 'inline-flex';
      } else {
        if (protoBadgeSsh) {
          protoBadgeSsh.className = 'proto-status-pill closed';
          protoBadgeSsh.textContent = isVi ? 'SSH: ĐÃ ĐÓNG' : 'SSH: CLOSED';
        }
        if (protoDescSsh) {
          protoDescSsh.textContent = isVi ? 'Port 22 đóng → Dùng Meikova Shell Subprocess' : 'Port 22 closed → Fallback to Meikova Shell';
        }
        if (btnCopySshCmd) btnCopySshCmd.style.display = 'none';
      }
    }

    // 3. File Transfer (SFTP 22 / FTP 21)
    if (matrix.file) {
      const sftp = matrix.file.sftp;
      const ftp = matrix.file.ftp;
      const fileAvail = (sftp && sftp.available) || (ftp && ftp.available);
      if (fileAvail) {
        if (protoBadgeFile) {
          protoBadgeFile.className = 'proto-status-pill ready';
          protoBadgeFile.textContent = sftp && sftp.available ? 'SFTP: SẴN SÀNG' : 'FTP: SẴN SÀNG';
        }
        if (protoDescFile) {
          protoDescFile.textContent = sftp && sftp.available ? (isVi ? 'SFTP Subsystem qua SSH' : 'SFTP Subsystem via SSH') : (isVi ? 'FTP Server mở' : 'FTP Server ready');
        }
      } else {
        if (protoBadgeFile) {
          protoBadgeFile.className = 'proto-status-pill closed';
          protoBadgeFile.textContent = isVi ? 'SFTP: ĐÃ ĐÓNG' : 'SFTP: CLOSED';
        }
        if (protoDescFile) {
          protoDescFile.textContent = isVi ? 'Cổng đóng → Dùng Meikova File Transfer' : 'Port closed → Fallback to Meikova Shelf';
        }
      }
    }

    // Update capsule button badge
    if (protocolCurrentLabel && btnProtocolMenu) {
      if (protocolRoutingMode === 'bypass') {
        protocolCurrentLabel.textContent = 'BYPASS';
        btnProtocolMenu.className = 'deck__btn deck__btn--protocol bypass-active';
      } else if (protocolRoutingMode === 'native' || (protocolRoutingMode === 'auto' && matrix.remote && matrix.remote.rdp && matrix.remote.rdp.available)) {
        protocolCurrentLabel.textContent = 'RDP';
        btnProtocolMenu.className = 'deck__btn deck__btn--protocol native-active';
      } else {
        protocolCurrentLabel.textContent = 'BYPASS';
        btnProtocolMenu.className = 'deck__btn deck__btn--protocol bypass-active';
      }
    }
  }

  // Toggle Protocol Popover Menu
  if (btnProtocolMenu) {
    btnProtocolMenu.addEventListener('click', (e) => {
      e.stopPropagation();
      if (protocolMenuDropdown) {
        const isOpening = protocolMenuDropdown.classList.contains('hidden');
        protocolMenuDropdown.classList.toggle('hidden');
        btnProtocolMenu.classList.toggle('btn-active', isOpening);
        if (isOpening) {
          positionDeckDropdown(btnProtocolMenu, protocolMenuDropdown);
          monitorMenuDropdown?.classList.add('hidden');
          btnMonitorMenu?.classList.remove('btn-active');
          resolutionMenuDropdown?.classList.add('hidden');
          btnResolutionMenu?.classList.remove('btn-active');
          if (qualityMenuDropdown) {
            qualityMenuDropdown.classList.add('hidden');
            if (btnQualityMenu) btnQualityMenu.classList.remove('btn-active');
          }
          if (powerMenuDropdown) {
            powerMenuDropdown.classList.add('hidden');
            if (btnPowerMenu) btnPowerMenu.classList.remove('btn-active');
          }
          if (deckModeDropdown) {
            deckModeDropdown.classList.add('hidden');
            if (btnDeckDisplayMode) btnDeckDisplayMode.classList.remove('btn-active');
          }
        }
      }
    });
  }

  // Refresh Protocols Button
  if (btnRefreshProtocols) {
    btnRefreshProtocols.addEventListener('click', (e) => {
      e.stopPropagation();
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'probe_protocols' }));
        showToast(t('toast.rescanning_protocols'), 'info');
      } else {
        showToast(t('toast.not_connected'), 'info');
      }
    });
  }

  // Download .RDP Button
  if (btnDownloadRdp) {
    btnDownloadRdp.addEventListener('click', async (e) => {
      e.stopPropagation();
      const roomId = currentRoom || (typeof currentRoomId !== 'undefined' ? currentRoomId : null) || 'Workstation';
      const rdpPort = (currentProtocolMatrix && currentProtocolMatrix.remote && currentProtocolMatrix.remote.rdp && currentProtocolMatrix.remote.rdp.port) || 3389;
      const rdpUrl = `/api/session/${encodeURIComponent(roomId)}/rdp-config?port=${rdpPort}&host=127.0.0.1`;
      try {
        const resp = await fetch(rdpUrl);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const blob = await resp.blob();
        const blobUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = blobUrl;
        a.download = `Meikova-${roomId}.rdp`;
        document.body.appendChild(a);
        a.click();
        setTimeout(() => {
          URL.revokeObjectURL(blobUrl);
          a.remove();
        }, 300);
        showToast(t('toast.rdp_downloaded'), 'success');
      } catch (err) {
        const a = document.createElement('a');
        a.href = rdpUrl;
        a.download = `Meikova-${roomId}.rdp`;
        document.body.appendChild(a);
        a.click();
        setTimeout(() => a.remove(), 300);
        showToast(t('toast.rdp_downloaded'), 'success');
      }
    });
  }

// Copy SSH Command Button
  if (btnCopySshCmd) {
    btnCopySshCmd.addEventListener('click', (e) => {
      e.stopPropagation();
      const sshCmd = 'ssh -p 22 127.0.0.1';
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(sshCmd).then(() => {
          showToast(t('deck.proto_copied') || 'Đã sao chép lệnh SSH vào bộ nhớ tạm!', 'success');
        });
      } else {
        showToast(sshCmd, 'info');
      }
    });
  }

  // Routing Mode Pills
  const setRoutingMode = (mode) => {
    protocolRoutingMode = mode;
    [protoModeAuto, protoModeBypass, protoModeNative].forEach(pill => {
      if (pill) {
        pill.classList.toggle('active', pill.dataset.mode === mode);
      }
    });
    if (currentProtocolMatrix) {
      updateProtocolUI(currentProtocolMatrix);
    }
    const modeLabels = {
      auto: 'Tự động (Ưu tiên Native First)',
      bypass: 'Ép buộc Meikova Bypass Stream',
      native: 'Ép buộc kết nối Native (RDP/SSH)'
    };
    showToast(t('toast.mode_switched', { mode: modeLabels[mode] || mode }), 'info');
  };

  if (protoModeAuto) protoModeAuto.addEventListener('click', () => setRoutingMode('auto'));
  if (protoModeBypass) protoModeBypass.addEventListener('click', () => setRoutingMode('bypass'));
  if (protoModeNative) protoModeNative.addEventListener('click', () => setRoutingMode('native'));

  // --- POWER ACTIONS MENU ---
  btnPowerMenu.addEventListener('click', (e) => {
    e.stopPropagation();
    if (powerMenuDropdown) {
      const isOpening = powerMenuDropdown.classList.contains('hidden');
      powerMenuDropdown.classList.toggle('hidden');
      btnPowerMenu.classList.toggle('btn-active', isOpening);
      if (isOpening) {
        positionDeckDropdown(btnPowerMenu, powerMenuDropdown);
      }
    }
    if (deckModeDropdown) {
      deckModeDropdown.classList.add('hidden');
      if (btnDeckDisplayMode) btnDeckDisplayMode.classList.remove('btn-active');
    }
    if (qualityMenuDropdown) {
      qualityMenuDropdown.classList.add('hidden');
      if (btnQualityMenu) btnQualityMenu.classList.remove('btn-active');
    }
    if (protocolMenuDropdown) {
      protocolMenuDropdown.classList.add('hidden');
      if (btnProtocolMenu) btnProtocolMenu.classList.remove('btn-active');
    }
  });


  // --- Dynamic Screen Resolution & Virtual Hardware Handlers ---
  function updateResolutionUi(w, h, label) {
    if (resolutionCurrentLabel) {
      if (label) {
        resolutionCurrentLabel.textContent = label;
      } else if (w >= 3840) {
        resolutionCurrentLabel.textContent = '4K';
      } else if (w >= 2560 && h >= 1440) {
        resolutionCurrentLabel.textContent = '2K';
      } else if (w >= 2560 && h <= 1080) {
        resolutionCurrentLabel.textContent = '21:9';
      } else if (h === 1080) {
        resolutionCurrentLabel.textContent = '1080p';
      } else if (h === 720) {
        resolutionCurrentLabel.textContent = '720p';
      } else if (h === 900) {
        resolutionCurrentLabel.textContent = '900p';
      } else {
        resolutionCurrentLabel.textContent = `${h}p`;
      }
    }
    document.querySelectorAll('#resolutionMenuList .quality-menu-item').forEach(btn => {
      const bw = parseInt(btn.dataset.resW, 10);
      const bh = parseInt(btn.dataset.resH, 10);
      const isMatch = (bw === w && bh === h);
      btn.classList.toggle('active', isMatch);
      const check = btn.querySelector('.quality-check');
      if (check) {
        check.classList.toggle('hidden', !isMatch);
      }
    });
  }

  if (btnMonitorMenu) {
    btnMonitorMenu.addEventListener('click', (e) => {
      e.stopPropagation();
      if (monitorMenuDropdown) {
        if (monitorMenuList && monitorMenuList.children.length === 0) {
          populateMonitors([
            { id: 1, name: 'Màn hình chính', width: 1920, height: 1080 }
          ], 0);
        }
        const isOpening = monitorMenuDropdown.classList.contains('hidden');
        monitorMenuDropdown.classList.toggle('hidden');
        btnMonitorMenu.classList.toggle('btn-active', isOpening);
        if (isOpening) {
          positionDeckDropdown(btnMonitorMenu, monitorMenuDropdown);
          resolutionMenuDropdown?.classList.add('hidden');
          btnResolutionMenu?.classList.remove('btn-active');
          qualityMenuDropdown?.classList.add('hidden');
          btnQualityMenu?.classList.remove('btn-active');
          protocolMenuDropdown?.classList.add('hidden');
          btnProtocolMenu?.classList.remove('btn-active');
          keyboardMenuDropdown?.classList.add('hidden');
          powerMenuDropdown?.classList.add('hidden');
          btnPowerMenu?.classList.remove('btn-active');
          deckModeDropdown?.classList.add('hidden');
          btnDeckDisplayMode?.classList.remove('btn-active');
          snippetsMenuDropdown?.classList.add('hidden');
          btnSnippetsMenu?.classList.remove('btn-active');
        }
      }
    });
  }

  if (btnResolutionMenu) {
    btnResolutionMenu.addEventListener('click', (e) => {
      e.stopPropagation();
      if (resolutionMenuDropdown) {
        const isOpening = resolutionMenuDropdown.classList.contains('hidden');
        resolutionMenuDropdown.classList.toggle('hidden');
        btnResolutionMenu.classList.toggle('btn-active', isOpening);
        if (isOpening) {
          positionDeckDropdown(btnResolutionMenu, resolutionMenuDropdown);
          monitorMenuDropdown?.classList.add('hidden');
          btnMonitorMenu?.classList.remove('btn-active');
          qualityMenuDropdown?.classList.add('hidden');
          btnQualityMenu?.classList.remove('btn-active');
          protocolMenuDropdown?.classList.add('hidden');
          btnProtocolMenu?.classList.remove('btn-active');
          powerMenuDropdown?.classList.add('hidden');
          btnPowerMenu?.classList.remove('btn-active');
          deckModeDropdown?.classList.add('hidden');
          btnDeckDisplayMode?.classList.remove('btn-active');
        }
      }
    });
  }

  document.querySelectorAll('#resolutionMenuList .quality-menu-item').forEach(btn => {
    btn.addEventListener('click', () => {
      const w = parseInt(btn.dataset.resW, 10);
      const h = parseInt(btn.dataset.resH, 10);
      const label = btn.dataset.resLabel || `${h}p`;
      if (!isConnected || !ws) {
        showToast(t('toast.not_connected'), 'info');
        return;
      }
      ws.send(JSON.stringify({
        type: 'set_screen_resolution',
        width: w,
        height: h
      }));
      resolutionMenuDropdown?.classList.add('hidden');
      btnResolutionMenu?.classList.remove('btn-active');
      updateResolutionUi(w, h, label);
      showToast(t('toast.resolution_switching', { res: `${w}x${h}` }), 'info');
    });
  });

  if (btnInstallVDisplay) {
    btnInstallVDisplay.addEventListener('click', () => {
      if (!isConnected || !ws) {
        showToast(t('toast.not_connected'), 'info');
        return;
      }
      showToast(t('toast.installing_virtual_display'), 'info');
      ws.send(JSON.stringify({ type: 'install_virtual_display' }));
    });
  }

  if (btnInstallVAudio) {
    btnInstallVAudio.addEventListener('click', () => {
      if (!isConnected || !ws) {
        showToast(t('toast.not_connected'), 'info');
        return;
      }
      showToast(t('toast.installing_vb_audio'), 'info');
      ws.send(JSON.stringify({ type: 'install_virtual_audio' }));
    });
  }

  document.addEventListener('click', (e) => {
    if (monitorMenuDropdown && !monitorMenuDropdown.contains(e.target) && e.target !== btnMonitorMenu && (!btnMonitorMenu || !btnMonitorMenu.contains(e.target))) {
      monitorMenuDropdown.classList.add('hidden');
      if (btnMonitorMenu) btnMonitorMenu.classList.remove('btn-active');
    }
    if (resolutionMenuDropdown && !resolutionMenuDropdown.contains(e.target) && e.target !== btnResolutionMenu && (!btnResolutionMenu || !btnResolutionMenu.contains(e.target))) {
      resolutionMenuDropdown.classList.add('hidden');
      if (btnResolutionMenu) btnResolutionMenu.classList.remove('btn-active');
    }
    if (powerMenuDropdown && !powerMenuDropdown.contains(e.target) && e.target !== btnPowerMenu && (!btnPowerMenu || !btnPowerMenu.contains(e.target))) {
      powerMenuDropdown.classList.add('hidden');
      if (btnPowerMenu) btnPowerMenu.classList.remove('btn-active');
    }
    if (deckModeDropdown && !deckModeDropdown.contains(e.target) && e.target !== btnDeckDisplayMode && (!btnDeckDisplayMode || !btnDeckDisplayMode.contains(e.target))) {
      deckModeDropdown.classList.add('hidden');
      if (btnDeckDisplayMode) btnDeckDisplayMode.classList.remove('btn-active');
    }
    if (protocolMenuDropdown && !protocolMenuDropdown.contains(e.target) && e.target !== btnProtocolMenu && (!btnProtocolMenu || !btnProtocolMenu.contains(e.target))) {
      protocolMenuDropdown.classList.add('hidden');
      if (btnProtocolMenu) btnProtocolMenu.classList.remove('btn-active');
    }
    if (qualityMenuDropdown && !qualityMenuDropdown.contains(e.target) && e.target !== btnQualityMenu && (!btnQualityMenu || !btnQualityMenu.contains(e.target))) {
      qualityMenuDropdown.classList.add('hidden');
      if (btnQualityMenu) btnQualityMenu.classList.remove('btn-active');
    }
    if (snippetsMenuDropdown && !snippetsMenuDropdown.contains(e.target) && e.target !== btnSnippetsMenu && (!btnSnippetsMenu || !btnSnippetsMenu.contains(e.target))) {
      snippetsMenuDropdown.classList.add('hidden');
      if (btnSnippetsMenu) btnSnippetsMenu.classList.remove('btn-active');
    }
    if (shortcutsMenuDropdown && !shortcutsMenuDropdown.contains(e.target) && e.target !== btnShortcutsMenu && (!btnShortcutsMenu || !btnShortcutsMenu.contains(e.target))) {
      shortcutsMenuDropdown.classList.add('hidden');
      if (btnShortcutsMenu) btnShortcutsMenu.classList.remove('btn-active');
    }
    if (moreToolsMenuDropdown && !moreToolsMenuDropdown.contains(e.target) && e.target !== btnMoreToolsMenu && (!btnMoreToolsMenu || !btnMoreToolsMenu.contains(e.target))) {
      moreToolsMenuDropdown.classList.add('hidden');
      updateToolsMenuState();
    }
    if (keyboardMenuDropdown && !keyboardMenuDropdown.contains(e.target) && e.target !== btnMobileKeyboard && (!btnMobileKeyboard || !btnMobileKeyboard.contains(e.target))) {
      keyboardMenuDropdown.classList.add('hidden');
      updateKeyboardMenuUI();
    }
  });

  document.querySelectorAll('[data-power]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const act = btn.dataset.power;
      powerMenuDropdown.classList.add('hidden');
      if (!isConnected) {
        showToast(t('toast.not_connected'), 'info');
        return;
      }
      if (act === 'lock') {
        const confirmed = await showConfirmModal({
          title: 'Khóa máy trạm',
          message: 'Khóa màn hình máy trạm (Lock Workstation)?',
          confirmText: 'Khóa',
          cancelText: t('dialog.btn_cancel') || 'Hủy'
        });
        if (confirmed) {
          ws.send(JSON.stringify({ type: 'power_action', action: 'lock' }));
        }
      } else if (act === 'restart') {
        const confirmed = await showConfirmModal({
          title: 'Khởi động lại máy trạm',
          message: t('deck.power_restart_confirm') || 'Khởi động lại máy trạm sẽ ngắt phiên làm việc tạm thời. Hệ thống sẽ tự động kết nối lại khi máy online. Bạn có chắc chắn?',
          confirmText: 'Khởi động lại',
          cancelText: t('dialog.btn_cancel') || 'Hủy',
          danger: true
        });
        if (confirmed) {
          isAwaitingRemoteRestart = true;
          restartReconnectRoom = currentRoom;
          restartReconnectPin = currentPin;
          restartReconnectRelay = defaultWsUrl;
          ws.send(JSON.stringify({ type: 'power_action', action: 'restart' }));
          showToast(t('toast.reboot_sent'), 'warning', 5000);
        }
      }
    });
  });

  // --- ON-SCREEN KEYBOARD (OSK) ---
  let oskShift = false;
  let oskCtrl = false;
  let oskAlt = false;

  btnToggleOSK.addEventListener('click', () => {
    oskOverlay.classList.toggle('hidden');
    btnToggleOSK.classList.toggle('btn-active', !oskOverlay.classList.contains('hidden'));
    updateKeyboardMenuUI();
  });

  oskOverlay.addEventListener('click', (e) => {
    const keyBtn = e.target.closest('.osk-key');
    if (!keyBtn || !isConnected) return;
    const key = keyBtn.dataset.key;

    if (key === 'ShiftLeft' || key === 'ShiftRight') {
      oskShift = !oskShift;
      oskOverlay.querySelectorAll('[data-key="ShiftLeft"], [data-key="ShiftRight"]').forEach(b => b.classList.toggle('active', oskShift));
      return;
    }
    if (key === 'ControlLeft' || key === 'ControlRight') {
      oskCtrl = !oskCtrl;
      oskOverlay.querySelectorAll('[data-key="ControlLeft"], [data-key="ControlRight"]').forEach(b => b.classList.toggle('active', oskCtrl));
      return;
    }
    if (key === 'AltLeft' || key === 'AltRight') {
      oskAlt = !oskAlt;
      oskOverlay.querySelectorAll('[data-key="AltLeft"], [data-key="AltRight"]').forEach(b => b.classList.toggle('active', oskAlt));
      return;
    }
    if (key === 'CapsLock') {
      sendKeySequence([0x14]);
      keyBtn.classList.toggle('active');
      return;
    }

    const vk = JS_TO_VK[key] || 0;
    if (vk > 0) {
      const combo = [];
      if (oskCtrl) combo.push(0x11);
      if (oskAlt) combo.push(0x12);
      if (oskShift) combo.push(0x10);
      combo.push(vk);

      if (combo.length > 1) {
        sendHotKeyCombo(combo);
      } else {
        sendKeySequence([vk]);
      }

      if (oskShift) {
        oskShift = false;
        oskOverlay.querySelectorAll('[data-key="ShiftLeft"], [data-key="ShiftRight"]').forEach(b => b.classList.remove('active'));
      }
      if (oskCtrl) {
        oskCtrl = false;
        oskOverlay.querySelectorAll('[data-key="ControlLeft"], [data-key="ControlRight"]').forEach(b => b.classList.remove('active'));
      }
      if (oskAlt) {
        oskAlt = false;
        oskOverlay.querySelectorAll('[data-key="AltLeft"], [data-key="AltRight"]').forEach(b => b.classList.remove('active'));
      }
    }
  });

  // --- VIEW 4: REMOTE REAL-TIME TERMINAL (POWERSHELL) ---
  let terminalHistory = [];
  let terminalHistoryIndex = -1;

  function updateTerminalStatusBadge() {
    if (!terminalStatusBadge) return;
    if (isConnected) {
      terminalStatusBadge.textContent = t('terminal.badge_connected');
      terminalStatusBadge.className = 'terminal-badge terminal-badge--online mono-font';
    } else {
      terminalStatusBadge.textContent = t('terminal.badge_disconnected');
      terminalStatusBadge.className = 'terminal-badge mono-font';
    }
  }

  // Click anywhere on terminal screen to focus input
  terminalScreen.addEventListener('click', () => {
    terminalCmdInput?.focus();
  });

  // Mirror typing in realtime to visual prompt row
  terminalCmdInput.addEventListener('input', () => {
    terminalInputEcho.textContent = terminalCmdInput.value;
    terminalScreen.scrollTop = terminalScreen.scrollHeight;
  });

  // Handle Enter, History navigation, Ctrl+L, Tab
  terminalCmdInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      const rawCmd = terminalCmdInput.value;
      const cmd = rawCmd.trim();

      // Echo command to log
      handleTerminalOutput(`PS > ${rawCmd}\n`);
      terminalCmdInput.value = '';
      terminalInputEcho.textContent = '';

      if (!cmd) {
        if (isConnected && ws) {
          ws.send(JSON.stringify({ type: 'terminal_input', command: '\n' }));
        }
        return;
      }

      // Add to command history
      terminalHistory.push(cmd);
      terminalHistoryIndex = terminalHistory.length;

      // Handle client-side clear
      if (cmd.toLowerCase() === 'cls' || cmd.toLowerCase() === 'clear') {
        terminalOutput.textContent = '';
      }

      if (!isConnected) {
        handleTerminalOutput('[MeikovaRelay] Chưa kết nối máy trạm. Vui lòng kết nối thiết bị từ bảng điều khiển trước.\n\n');
        showToast(t('toast.connect_before_terminal'), 'info');
        return;
      }

      ws.send(JSON.stringify({
        type: 'terminal_input',
        command: cmd + '\n'
      }));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (terminalHistory.length > 0) {
        if (terminalHistoryIndex > 0) {
          terminalHistoryIndex--;
        } else {
          terminalHistoryIndex = 0;
        }
        terminalCmdInput.value = terminalHistory[terminalHistoryIndex] || '';
        terminalInputEcho.textContent = terminalCmdInput.value;
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (terminalHistoryIndex < terminalHistory.length - 1) {
        terminalHistoryIndex++;
        terminalCmdInput.value = terminalHistory[terminalHistoryIndex] || '';
        terminalInputEcho.textContent = terminalCmdInput.value;
      } else {
        terminalHistoryIndex = terminalHistory.length;
        terminalCmdInput.value = '';
        terminalInputEcho.textContent = '';
      }
    } else if (e.ctrlKey && e.key.toLowerCase() === 'l') {
      e.preventDefault();
      terminalOutput.textContent = '';
    }
  });

  btnClearTerminal.addEventListener('click', () => {
    terminalOutput.textContent = '';
    terminalCmdInput.value = '';
    terminalInputEcho.textContent = '';
    terminalCmdInput.focus();
  });

  function handleTerminalOutput(text) {
    terminalOutput.textContent += text;
    terminalScreen.scrollTop = terminalScreen.scrollHeight;
  }

  // --- VIEW 5: TASK MANAGER & DIAGNOSTICS ---
  btnRefreshTasks.addEventListener('click', () => {
    if (!isConnected) {
      showToast(t('toast.not_connected'), 'info');
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
      processTableBody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-faint); padding: 20px;">${t('tasks.search_no_results')}</td></tr>`;
      return;
    }

    const killLabel = t('tasks.btn_kill');
    processTableBody.innerHTML = filtered.map(p => `
      <tr>
        <td style="color: var(--accent);">${p.pid}</td>
        <td><strong>${escapeHtml(p.name)}</strong></td>
        <td>${p.memory_mb} MB</td>
        <td>
          <button class="btn-kill-proc" data-pid="${p.pid}" data-name="${escapeHtml(p.name)}">${killLabel}</button>
        </td>
      </tr>
    `).join('');

    processTableBody.querySelectorAll('.btn-kill-proc').forEach(btn => {
      btn.addEventListener('click', async () => {
        const pid = parseInt(btn.dataset.pid, 10);
        const name = btn.dataset.name || 'process';
        const confirmed = await showConfirmModal({
          title: 'Dừng tiến trình',
          message: t('tasks.kill_confirm', { name, pid }),
          confirmText: 'Dừng tiến trình',
          cancelText: t('dialog.btn_cancel') || 'Hủy',
          danger: true
        });
        if (confirmed) {
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
      if (tab === 'clipboard' && isConnected && ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'clipboard_pull' }));
      }
    shelfChatTab.classList.toggle('hidden', tab !== 'chat');
    if (tab === 'chat') {
      const chatUnreadDot = document.getElementById('chatUnreadDot');
      const tabChatUnreadDot = document.getElementById('tabChatUnreadDot');
      if (chatUnreadDot) chatUnreadDot.classList.add('hidden');
      if (tabChatUnreadDot) tabChatUnreadDot.classList.add('hidden');
      chatMessageInput?.focus();
    }
  });

  // Dedicated Floating Deck Chat Button Listener
  const btnViewerChat = document.getElementById('btnViewerChat');
  if (btnViewerChat) {
    btnViewerChat.addEventListener('click', () => {
      const chatUnreadDot = document.getElementById('chatUnreadDot');
      const tabChatUnreadDot = document.getElementById('tabChatUnreadDot');
      if (chatUnreadDot) chatUnreadDot.classList.add('hidden');
      if (tabChatUnreadDot) tabChatUnreadDot.classList.add('hidden');

      const isOpen = shelfDrawer.classList.contains('open');
      const isChatTabActive = !shelfChatTab.classList.contains('hidden');

      if (isOpen && isChatTabActive) {
        shelfDrawer.classList.remove('open');
      } else {
        shelfDrawer.classList.add('open');
        shelfTabs.querySelectorAll('button').forEach(b => {
          const isChat = b.dataset.shelfTab === 'chat';
          b.classList.toggle('on', isChat);
        });
        placeIndicator(shelfTabs);
        shelfFilesTab.classList.add('hidden');
        shelfClipboardTab.classList.add('hidden');
        shelfChatTab.classList.remove('hidden');
        chatMessageInput?.focus();
      }
    });
  }

  // --- LIVE CHAT WITH HOST USER (MEIKOVA AMBIENT UI) ---
  function playChatNotificationSound() {
    try {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (!AudioContext) return;
      const ctx = new AudioContext();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(784, ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(1046.5, ctx.currentTime + 0.08);
      gain.gain.setValueAtTime(0.12, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.35);
      setTimeout(() => { try { ctx.close(); } catch {} }, 400);
    } catch {}
  }

  // Quick Chips click handler
  document.querySelectorAll('#shelfChatTab .chat-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const text = chip.dataset.quickMsg;
      if (text && chatMessageInput) {
        chatMessageInput.value = text;
        chatInputForm?.dispatchEvent(new Event('submit', { cancelable: true }));
      }
    });
  });

  // Clear chat history
  const btnClearChatHistory = document.getElementById('btnClearChatHistory');
  btnClearChatHistory?.addEventListener('click', () => {
    if (!chatHistory) return;
    chatHistory.innerHTML = `
      <div class="chat-welcome-banner">
        <div class="chat-welcome-icon">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
        </div>
        <div class="chat-welcome-title">${(typeof i18n !== 'undefined' && i18n.t) ? i18n.t('shelf.chat_cleared_title') : 'Lịch sử trò chuyện đã được làm trống'}</div>
      </div>
    `;
  });

  chatInputForm?.addEventListener('submit', (e) => {
    e.preventDefault();
    if (!isConnected) {
      showToast(t('toast.not_connected'), 'info');
      return;
    }
    const msg = chatMessageInput.value.trim();
    if (!msg) return;
    const senderName = currentUser ? currentUser.username : 'Kỹ thuật viên';
    appendChatMessage('Bạn', msg, true);
    ws.send(JSON.stringify({
      type: 'chat_message',
      sender: senderName,
      message: msg
    }));
    chatMessageInput.value = '';
  });

  function appendChatMessage(sender, text, isLocal = false) {
    if (!chatHistory) return;
    const welcome = chatHistory.querySelector('.chat-welcome-banner');
    if (welcome && chatHistory.children.length <= 1) {
      welcome.remove();
    }

    const timeStr = new Date().toLocaleTimeString('vi-VN', { hour12: false, hour: '2-digit', minute: '2-digit' });
    const row = document.createElement('div');
    row.className = `chat-bubble-row ${isLocal ? 'local' : 'remote'}`;

    const headerHtml = `
      <div class="chat-bubble-header">
        ${isLocal 
          ? `<span class="mono-font">${timeStr}</span>` 
          : `<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
             <span style="font-weight: 600;">${escapeHtml(sender)}</span>
             <span class="mono-font" style="color: var(--text-faint); margin-left: 4px;">${timeStr}</span>`
        }
      </div>
    `;

    const metaHtml = isLocal ? `
      <div class="chat-bubble-meta">
        <span>${(typeof i18n !== 'undefined' && i18n.t) ? i18n.t('shelf.chat_sent_status') : 'Đã gửi'}</span>
        <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
      </div>
    ` : '';

    row.innerHTML = `
      ${headerHtml}
      <div class="chat-bubble">
        ${escapeHtml(text)}
        ${metaHtml}
      </div>
    `;

    chatHistory.appendChild(row);
    chatHistory.scrollTop = chatHistory.scrollHeight;
  }


  // ------------------------------------------------------------------ ADVANCED UTILITIES IMPLEMENTATION
  // 1. Privacy Curtain Toggle
  btnToggleCurtain?.addEventListener('click', () => {
    if (!isConnected || !ws || ws.readyState !== WebSocket.OPEN) {
      showToast(t('toast.not_connected'), 'info');
      return;
    }
    const nextState = !isCurtainActive;
    ws.send(JSON.stringify({
      type: 'toggle_privacy_curtain',
      enabled: nextState
    }));
  });

  // 2. Live Whiteboard Engine
  function toggleWhiteboard(forceState) {
    isWhiteboardActive = (typeof forceState === 'boolean') ? forceState : !isWhiteboardActive;
    btnToggleWhiteboard?.classList.toggle('btn-active', isWhiteboardActive);
    if (isWhiteboardActive) {
      if (whiteboardCanvas && remoteCanvas) {
        whiteboardCanvas.width = hostResolution.width || remoteCanvas.width || 1920;
        whiteboardCanvas.height = hostResolution.height || remoteCanvas.height || 1080;
        whiteboardCanvas.style.width = remoteCanvas.style.width;
        whiteboardCanvas.style.height = remoteCanvas.style.height;
      }
      whiteboardCanvas?.classList.remove('hidden');
      whiteboardCanvas?.classList.add('is-active');
      whiteboardToolbar?.classList.remove('hidden');
      redrawWhiteboard();
      if (wbLaserFade && !wbAnimFrameId) {
        startWbFadeLoop();
      }
    } else {
      whiteboardCanvas?.classList.add('hidden');
      whiteboardCanvas?.classList.remove('is-active');
      whiteboardToolbar?.classList.add('hidden');
      if (wbAnimFrameId) {
        cancelAnimationFrame(wbAnimFrameId);
        wbAnimFrameId = null;
      }
    }
  }

  function clearWhiteboard() {
    wbStrokes = [];
    if (wbCtx && whiteboardCanvas) {
      wbCtx.clearRect(0, 0, whiteboardCanvas.width, whiteboardCanvas.height);
    }
  }

  function drawWbArrow(ctx, fromX, fromY, toX, toY, headLength = 16) {
    const angle = Math.atan2(toY - fromY, toX - fromX);
    ctx.beginPath();
    ctx.moveTo(fromX, fromY);
    ctx.lineTo(toX, toY);
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(toX, toY);
    ctx.lineTo(toX - headLength * Math.cos(angle - Math.PI / 6), toY - headLength * Math.sin(angle - Math.PI / 6));
    ctx.lineTo(toX - headLength * Math.cos(angle + Math.PI / 6), toY - headLength * Math.sin(angle + Math.PI / 6));
    ctx.closePath();
    ctx.fill();
  }

  function redrawWhiteboard() {
    if (!wbCtx || !whiteboardCanvas) return;
    wbCtx.clearRect(0, 0, whiteboardCanvas.width, whiteboardCanvas.height);
    const now = Date.now();

    for (let i = wbStrokes.length - 1; i >= 0; i--) {
      const s = wbStrokes[i];
      if (s.fadeUntil && now >= s.fadeUntil) {
        wbStrokes.splice(i, 1);
      }
    }

    for (const stroke of wbStrokes) {
      wbCtx.save();
      let alpha = 1.0;
      if (stroke.fadeUntil) {
        const remaining = stroke.fadeUntil - now;
        alpha = Math.max(0, Math.min(1.0, remaining / 5000));
      }

      if (stroke.tool === 'highlighter') {
        wbCtx.globalAlpha = 0.35 * alpha;
        wbCtx.strokeStyle = stroke.color;
        wbCtx.lineWidth = 18;
        wbCtx.lineCap = 'square';
        wbCtx.lineJoin = 'round';
      } else if (stroke.tool === 'eraser') {
        wbCtx.globalCompositeOperation = 'destination-out';
        wbCtx.lineWidth = 32;
        wbCtx.lineCap = 'round';
        wbCtx.lineJoin = 'round';
      } else if (stroke.tool === 'arrow') {
        wbCtx.globalAlpha = alpha;
        wbCtx.strokeStyle = stroke.color;
        wbCtx.fillStyle = stroke.color;
        wbCtx.lineWidth = 4;
        wbCtx.lineCap = 'round';
        wbCtx.lineJoin = 'round';
      } else {
        wbCtx.globalAlpha = alpha;
        wbCtx.strokeStyle = stroke.color;
        wbCtx.lineWidth = 4;
        wbCtx.lineCap = 'round';
        wbCtx.lineJoin = 'round';
      }

      if (stroke.tool === 'arrow') {
        drawWbArrow(wbCtx, stroke.start.x, stroke.start.y, stroke.end.x, stroke.end.y, 16);
      } else if (stroke.points && stroke.points.length > 1) {
        wbCtx.beginPath();
        wbCtx.moveTo(stroke.points[0].x, stroke.points[0].y);
        for (let p = 1; p < stroke.points.length; p++) {
          wbCtx.lineTo(stroke.points[p].x, stroke.points[p].y);
        }
        wbCtx.stroke();
      } else if (stroke.points && stroke.points.length === 1) {
        wbCtx.beginPath();
        wbCtx.arc(stroke.points[0].x, stroke.points[0].y, (stroke.tool === 'highlighter' ? 9 : 2), 0, Math.PI * 2);
        wbCtx.fillStyle = stroke.color;
        wbCtx.fill();
      }
      wbCtx.restore();
    }
  }

  function startWbFadeLoop() {
    function step() {
      if (!isWhiteboardActive) return;
      if (wbLaserFade || wbStrokes.some(s => s.fadeUntil)) {
        redrawWhiteboard();
        wbAnimFrameId = requestAnimationFrame(step);
      } else {
        wbAnimFrameId = null;
      }
    }
    wbAnimFrameId = requestAnimationFrame(step);
  }

  btnToggleWhiteboard?.addEventListener('click', () => toggleWhiteboard());

  whiteboardToolbar?.querySelectorAll('[data-wb-tool]').forEach(btn => {
    btn.addEventListener('click', () => {
      whiteboardToolbar.querySelectorAll('[data-wb-tool]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      wbCurrentTool = btn.getAttribute('data-wb-tool') || 'pen';
    });
  });

  whiteboardToolbar?.querySelectorAll('[data-wb-color]').forEach(btn => {
    btn.addEventListener('click', () => {
      whiteboardToolbar.querySelectorAll('[data-wb-color]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      wbCurrentColor = btn.getAttribute('data-wb-color') || '#06B6D4';
    });
  });

  btnWbLaserFade?.addEventListener('click', () => {
    wbLaserFade = !wbLaserFade;
    btnWbLaserFade.classList.toggle('active', wbLaserFade);
    showToast(wbLaserFade ? t('toast.laser_fade_on') : t('toast.laser_fade_off'), 'info');
    if (wbLaserFade && !wbAnimFrameId) {
      startWbFadeLoop();
    }
  });

  btnWbClearAll?.addEventListener('click', () => {
    clearWhiteboard();
    showToast(t('toast.whiteboard_cleared'), 'info');
  });

  let currentWbStroke = null;
  if (whiteboardCanvas) {
    function getWhiteboardCoords(e) {
      const rect = whiteboardCanvas.getBoundingClientRect();
      const clientX = e.clientX ?? (e.touches && e.touches[0] ? e.touches[0].clientX : 0);
      const clientY = e.clientY ?? (e.touches && e.touches[0] ? e.touches[0].clientY : 0);
      const pixelX = Math.round(((clientX - rect.left) / (rect.width || 1)) * whiteboardCanvas.width);
      const pixelY = Math.round(((clientY - rect.top) / (rect.height || 1)) * whiteboardCanvas.height);
      return { pixelX, pixelY };
    }

    whiteboardCanvas.addEventListener('pointerdown', (e) => {
      if (!isWhiteboardActive) return;
      e.preventDefault();
      try { whiteboardCanvas.setPointerCapture(e.pointerId); } catch {}
      wbDrawing = true;
      const coords = getWhiteboardCoords(e);
      wbStartPos = { x: coords.pixelX, y: coords.pixelY };
      wbLastPos = { x: coords.pixelX, y: coords.pixelY };

      currentWbStroke = {
        tool: wbCurrentTool,
        color: wbCurrentColor,
        points: [{ x: coords.pixelX, y: coords.pixelY }],
        start: { x: coords.pixelX, y: coords.pixelY },
        end: { x: coords.pixelX, y: coords.pixelY },
        fadeUntil: wbLaserFade ? Date.now() + 5000 : null
      };
      wbStrokes.push(currentWbStroke);
      redrawWhiteboard();
    });

    whiteboardCanvas.addEventListener('pointermove', (e) => {
      if (!isWhiteboardActive || !wbDrawing || !currentWbStroke) return;
      e.preventDefault();
      const coords = getWhiteboardCoords(e);
      if (currentWbStroke.tool === 'arrow') {
        currentWbStroke.end = { x: coords.pixelX, y: coords.pixelY };
      } else {
        currentWbStroke.points.push({ x: coords.pixelX, y: coords.pixelY });
      }
      redrawWhiteboard();
    });

    const finishWbStroke = (e) => {
      if (!isWhiteboardActive || !wbDrawing) return;
      e.preventDefault();
      wbDrawing = false;
      try { whiteboardCanvas.releasePointerCapture(e.pointerId); } catch {}
      redrawWhiteboard();
      if (wbLaserFade && !wbAnimFrameId) {
        startWbFadeLoop();
      }
    };

    whiteboardCanvas.addEventListener('pointerup', finishWbStroke);
    whiteboardCanvas.addEventListener('pointercancel', finishWbStroke);
  }

  // 2b. System Shortcuts & Key Combos Popover Menu
  if (btnShortcutsMenu) {
    btnShortcutsMenu.addEventListener('click', (e) => {
      e.stopPropagation();
      if (shortcutsMenuDropdown) {
        const isOpening = shortcutsMenuDropdown.classList.contains('hidden');
        shortcutsMenuDropdown.classList.toggle('hidden');
        btnShortcutsMenu.classList.toggle('btn-active', isOpening);
        if (isOpening) {
          positionDeckDropdown(btnShortcutsMenu, shortcutsMenuDropdown);
          moreToolsMenuDropdown?.classList.add('hidden');
          snippetsMenuDropdown?.classList.add('hidden');
          btnSnippetsMenu?.classList.remove('btn-active');
          qualityMenuDropdown?.classList.add('hidden');
          btnQualityMenu?.classList.remove('btn-active');
          protocolMenuDropdown?.classList.add('hidden');
          btnProtocolMenu?.classList.remove('btn-active');
          powerMenuDropdown?.classList.add('hidden');
          btnPowerMenu?.classList.remove('btn-active');
        }
      }
    });
  }


  function updateToolsMenuState() {
    const isAnyActive = (typeof isWhiteboardActive !== 'undefined' && isWhiteboardActive) ||
                        (typeof isLaserActive !== 'undefined' && isLaserActive) ||
                        (typeof isRecording !== 'undefined' && isRecording) ||
                        (typeof isWebcamActive !== 'undefined' && isWebcamActive) ||
                        (typeof isInputBlocked !== 'undefined' && isInputBlocked) ||
                        (typeof isCurtainActive !== 'undefined' && isCurtainActive);
    if (toolsActiveIndicator) {
      toolsActiveIndicator.classList.toggle('hidden', !isAnyActive);
    }
    if (btnMoreToolsMenu) {
      const isOpening = moreToolsMenuDropdown && !moreToolsMenuDropdown.classList.contains('hidden');
      btnMoreToolsMenu.classList.toggle('btn-active', isOpening || isAnyActive);
    }
    if (badgeWhiteboardActive) badgeWhiteboardActive.classList.toggle('hidden', !(typeof isWhiteboardActive !== 'undefined' && isWhiteboardActive));
    if (badgeLaserActive) badgeLaserActive.classList.toggle('hidden', !(typeof isLaserActive !== 'undefined' && isLaserActive));
    if (badgeRecordActive) badgeRecordActive.classList.toggle('hidden', !(typeof isRecording !== 'undefined' && isRecording));
    if (badgeCamActive) badgeCamActive.classList.toggle('hidden', !(typeof isWebcamActive !== 'undefined' && isWebcamActive));
    if (badgeBlockInputActive) badgeBlockInputActive.classList.toggle('hidden', !(typeof isInputBlocked !== 'undefined' && isInputBlocked));
    if (badgeCurtainActive) badgeCurtainActive.classList.toggle('hidden', !(typeof isCurtainActive !== 'undefined' && isCurtainActive));
  }

  if (btnMoreToolsMenu) {
    btnMoreToolsMenu.addEventListener('click', (e) => {
      e.stopPropagation();
      if (moreToolsMenuDropdown) {
        const isOpening = moreToolsMenuDropdown.classList.contains('hidden');
        moreToolsMenuDropdown.classList.toggle('hidden');
        if (isOpening) {
          positionDeckDropdown(btnMoreToolsMenu, moreToolsMenuDropdown);
          updateToolsMenuState();
          shortcutsMenuDropdown?.classList.add('hidden');
          btnShortcutsMenu?.classList.remove('btn-active');
          snippetsMenuDropdown?.classList.add('hidden');
          btnSnippetsMenu?.classList.remove('btn-active');
          qualityMenuDropdown?.classList.add('hidden');
          btnQualityMenu?.classList.remove('btn-active');
          protocolMenuDropdown?.classList.add('hidden');
          btnProtocolMenu?.classList.remove('btn-active');
          powerMenuDropdown?.classList.add('hidden');
          btnPowerMenu?.classList.remove('btn-active');
        } else {
          updateToolsMenuState();
        }
      }
    });
  }

  btnDropdownWhiteboard?.addEventListener('click', () => {
    btnToggleWhiteboard?.click();
    moreToolsMenuDropdown?.classList.add('hidden');
    updateToolsMenuState();
  });

  btnDropdownLaser?.addEventListener('click', () => {
    btnToggleLaser?.click();
    moreToolsMenuDropdown?.classList.add('hidden');
    updateToolsMenuState();
  });

  btnDropdownScreenshot?.addEventListener('click', () => {
    btnScreenshot?.click();
    moreToolsMenuDropdown?.classList.add('hidden');
  });

  btnDropdownRecord?.addEventListener('click', () => {
    btnRecord?.click();
    moreToolsMenuDropdown?.classList.add('hidden');
    updateToolsMenuState();
  });

  btnDropdownCam?.addEventListener('click', () => {
    btnToggleCam?.click();
    moreToolsMenuDropdown?.classList.add('hidden');
    updateToolsMenuState();
  });

  btnDropdownBlockInput?.addEventListener('click', () => {
    btnToggleBlockInput?.click();
    moreToolsMenuDropdown?.classList.add('hidden');
    updateToolsMenuState();
  });

  btnDropdownCurtain?.addEventListener('click', () => {
    btnToggleCurtain?.click();
    moreToolsMenuDropdown?.classList.add('hidden');
    updateToolsMenuState();
  });

  btnDropdownSnippets?.addEventListener('click', () => {
    moreToolsMenuDropdown?.classList.add('hidden');
    if (snippetsMenuDropdown) {
      const isOpening = snippetsMenuDropdown.classList.contains('hidden');
      snippetsMenuDropdown.classList.toggle('hidden');
      if (isOpening) {
        positionDeckDropdown(btnMoreToolsMenu, snippetsMenuDropdown);
      }
    }
  });

    shortcutsMenuDropdown?.querySelectorAll('[data-system-combo]').forEach(btn => {
    btn.addEventListener('click', () => {
      const combo = btn.getAttribute('data-system-combo');
      if (!combo) return;
      if (!isConnected || !ws || ws.readyState !== WebSocket.OPEN) {
        showToast(t('toast.not_connected'), 'info');
        return;
      }

      ws.send(JSON.stringify({
        type: 'system_hotkey',
        combo: combo
      }));

      if (combo === 'cad') {
        sendHotKeyCombo([0x11, 0x12, 0x2E]);
      } else if (combo === 'taskmgr') {
        sendHotKeyCombo([0x11, 0x10, 0x1B]);
      } else if (combo === 'alttab') {
        sendHotKeyCombo([0x12, 0x09]);
      } else if (combo === 'altf4') {
        sendHotKeyCombo([0x12, 0x73]);
      } else if (combo === 'win') {
        sendKeySequence([0x5B]);
      } else if (combo === 'esc') {
        sendKeySequence([0x1B]);
      }

      const itemTitle = btn.querySelector('.quality-item-title')?.textContent || combo;
      showToast(t('toast.combo_sent', { combo: itemTitle }) || `Đã gửi: ${itemTitle}`, 'info', 2000);

      shortcutsMenuDropdown.classList.add('hidden');
      btnShortcutsMenu?.classList.remove('btn-active');
    });
  });

  // 3. Quick Snippets & Macros Popover Menu
  if (btnSnippetsMenu) {
    btnSnippetsMenu.addEventListener('click', (e) => {
      e.stopPropagation();
      if (snippetsMenuDropdown) {
        const isOpening = snippetsMenuDropdown.classList.contains('hidden');
        snippetsMenuDropdown.classList.toggle('hidden');
        btnSnippetsMenu.classList.toggle('btn-active', isOpening);
        if (isOpening) {
          positionDeckDropdown(btnSnippetsMenu, snippetsMenuDropdown);
        positionDeckDropdown(btnShortcutsMenu, shortcutsMenuDropdown);
          qualityMenuDropdown?.classList.add('hidden');
          btnQualityMenu?.classList.remove('btn-active');
          protocolMenuDropdown?.classList.add('hidden');
          btnProtocolMenu?.classList.remove('btn-active');
          powerMenuDropdown?.classList.add('hidden');
          btnPowerMenu?.classList.remove('btn-active');
        }
      }
    });
  }

  snippetsMenuDropdown?.querySelectorAll('[data-macro]').forEach(btn => {
    btn.addEventListener('click', () => {
      const macro = btn.getAttribute('data-macro');
      if (!macro) return;
      if (!isConnected || !ws || ws.readyState !== WebSocket.OPEN) {
        showToast(t('toast.not_connected'), 'info');
        return;
      }
      ws.send(JSON.stringify({
        type: 'quick_macro',
        command: macro,
        mode: currentView === 'terminal' ? 'terminal' : 'gui'
      }));
      showToast(t('toast.macro_sent', { cmd: macro }), 'success');
      snippetsMenuDropdown.classList.add('hidden');
      btnSnippetsMenu?.classList.remove('btn-active');
    });
  });

  // 4. Secure Password Transmission Modal (Zero Clipboard Persistence)
  btnOpenPasswordModal?.addEventListener('click', () => {
    snippetsMenuDropdown?.classList.add('hidden');
    btnSnippetsMenu?.classList.remove('btn-active');
    if (modalSendPassword) {
      modalSendPassword.classList.remove('hidden');
      if (inputSecurePassword) {
        inputSecurePassword.value = '';
        setTimeout(() => inputSecurePassword.focus(), 60);
      }
    }
  });

  function closePasswordModal() {
    if (inputSecurePassword) inputSecurePassword.value = '';
    modalSendPassword?.classList.add('hidden');
  }

  btnConfirmSendPassword?.addEventListener('click', () => {
    const pwd = inputSecurePassword?.value;
    if (!pwd) {
      showToast(t('toast.enter_clip_content'), 'info');
      return;
    }
    if (!isConnected || !ws || ws.readyState !== WebSocket.OPEN) {
      showToast(t('toast.not_connected'), 'info');
      return;
    }
    ws.send(JSON.stringify({ type: 'text_input', text: pwd }));
    closePasswordModal();
    showToast(t('toast.password_sent'), 'success');
  });

  btnCancelSendPassword?.addEventListener('click', closePasswordModal);
  btnCloseSendPassword?.addEventListener('click', closePasswordModal);
  inputSecurePassword?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      btnConfirmSendPassword?.click();
    } else if (e.key === 'Escape') {
      closePasswordModal();
    }
  });

  // --- BLOCK HOST INPUT TOGGLE ---
  btnToggleBlockInput?.addEventListener('click', () => {
    if (!isConnected) {
      showToast(t('toast.not_connected'), 'info');
      return;
    }
    const nextState = !isInputBlocked;
    ws.send(JSON.stringify({
      type: 'block_input',
      blocked: nextState
    }));
  });

  // Clipboard Push
  btnPushClipboard.addEventListener('click', async () => {
    if (!isConnected || !ws || ws.readyState !== WebSocket.OPEN) {
      showToast(t('toast.not_connected'), 'info');
      return;
    }
    const text = clipboardViewer.value;
    if (!text) {
      showToast(t('toast.enter_clip_content'), 'info');
      return;
    }
    lastSyncedClientClipboard = text;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      try {
        await navigator.clipboard.writeText(text);
      } catch {}
    }
    ws.send(JSON.stringify({
      type: 'clipboard_sync',
      text: text
    }));
    showToast(t('toast.pushing_clip'), 'info');
  });

    // Clipboard Pull (Fetch from Host)
    const btnPullClipboard = document.getElementById('btnPullClipboard');
    if (btnPullClipboard) {
      btnPullClipboard.addEventListener('click', () => {
        if (!isConnected || !ws || ws.readyState !== WebSocket.OPEN) {
          showToast(t('toast.not_connected'), 'info');
          return;
        }
        ws.send(JSON.stringify({ type: 'clipboard_pull' }));
        showToast(t('toast.refreshing_clip'), 'info');
      });
    }

  // Direct Unicode Typing (PowerPoint, Word, Terminal, etc.)
  if (btnTypeDirect) {
    btnTypeDirect.addEventListener('click', () => {
      if (!isConnected) {
        showToast(t('toast.not_connected'), 'info');
        return;
      }
      const text = clipboardViewer.value;
      if (!text) {
        showToast(t('toast.enter_type_content'), 'info');
        return;
      }
      ws.send(JSON.stringify({
        type: 'text_input',
        text: text
      }));
      showToast(t('toast.typing_direct_success'), 'success');
    });
  }

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

  async function getFilesFromDataTransfer(dataTransfer) {
    const files = [];
    if (dataTransfer.items && dataTransfer.items.length > 0) {
      async function readEntry(entry, path = '') {
        if (!entry) return;
        if (entry.isFile) {
          await new Promise((resolve) => {
            entry.file((f) => {
              const rel = path ? `${path}/${f.name}` : f.name;
              Object.defineProperty(f, 'relativePath', { value: rel, writable: true, configurable: true });
              files.push(f);
              resolve();
            }, () => resolve());
          });
        } else if (entry.isDirectory) {
          const dirReader = entry.createReader();
          const readAllEntries = () => new Promise((resolve) => {
            dirReader.readEntries(async (entries) => {
              if (!entries || entries.length === 0) {
                resolve();
                return;
              }
              const nextPath = path ? `${path}/${entry.name}` : entry.name;
              for (const e of entries) {
                await readEntry(e, nextPath);
              }
              await readAllEntries();
              resolve();
            }, () => resolve());
          });
          await readAllEntries();
        }
      }

      const tasks = [];
      for (let i = 0; i < dataTransfer.items.length; i++) {
        const item = dataTransfer.items[i];
        if (typeof item.webkitGetAsEntry === 'function') {
          const entry = item.webkitGetAsEntry();
          if (entry) tasks.push(readEntry(entry));
        } else {
          const f = item.getAsFile();
          if (f) files.push(f);
        }
      }
      await Promise.all(tasks);
    } else if (dataTransfer.files && dataTransfer.files.length > 0) {
      for (let i = 0; i < dataTransfer.files.length; i++) {
        files.push(dataTransfer.files[i]);
      }
    }
    return files;
  }

  const uploadQueue = [];
  let isUploading = false;

  async function processUploadQueue() {
    if (isUploading || uploadQueue.length === 0) return;
    isUploading = true;
    while (uploadQueue.length > 0) {
      const task = uploadQueue.shift();
      try {
        await executeFileUpload(task.file, task.targetDir);
      } catch (err) {
        console.error('Upload failed:', err);
      }
    }
    isUploading = false;
  }

  function uploadFileToHost(file, targetDir = '') {
    uploadQueue.push({ file, targetDir });
    processUploadQueue();
  }

  async function executeFileUpload(file, targetDir) {
    if (!isConnected) {
      showToast(t('toast.connect_before_file'), 'info');
      return;
    }

    const displayName = file.relativePath || file.name;
    uploadFileName.textContent = displayName;
    uploadPercent.textContent = '0%';
    uploadProgressBar.style.width = '0%';
    uploadProgressContainer.classList.remove('hidden');

    if (expTransferProgress) {
      expTransferProgress.classList.remove('hidden');
      expTransferLabel.textContent = `Đang tải lên: ${displayName} (${formatBytes(file.size)})`;
      expTransferPercent.textContent = '0%';
      expTransferFill.style.width = '0%';
    }

    const transferId = 'transfer_' + Date.now() + '_' + Math.floor(Math.random() * 10000);
    const chunkSize = 64 * 1024;
    const totalChunks = Math.ceil(file.size / chunkSize) || 1;

    ws.send(JSON.stringify({
      type: 'file_upload_start',
      transfer_id: transferId,
      filename: file.relativePath || file.name,
      filesize: file.size,
      target_dir: targetDir || remoteCurrentPath || ''
    }));

    if (file.size === 0) {
      ws.send(JSON.stringify({
        type: 'file_upload_chunk',
        transfer_id: transferId,
        data: ''
      }));
    } else {
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
        if (expTransferProgress) {
          expTransferPercent.textContent = `${progress}%`;
          expTransferFill.style.width = `${progress}%`;
        }
      }
    }

    ws.send(JSON.stringify({
      type: 'file_upload_finish',
      transfer_id: transferId
    }));
  }

  // --- DIRECT DRAG & DROP ONTO REMOTE DESKTOP SCREEN ---
  const screenDropOverlay = document.createElement('div');
  screenDropOverlay.className = 'screen-drop-overlay hidden';
  screenDropOverlay.innerHTML = `
    <div class="screen-drop-modal">
      <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="2" style="color: var(--accent); margin-bottom: 12px;"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
      <div style="font-size: 1.1rem; font-weight: 600; color: #fff;" data-i18n="deck.drop_title">${t('deck.drop_title')}</div>
      <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 6px;" data-i18n="deck.drop_hint">${t('deck.drop_hint')}</div>
    </div>
  `;
  remoteSection.appendChild(screenDropOverlay);

  let screenDragCounter = 0;
  remoteSection.addEventListener('dragenter', (e) => {
    e.preventDefault();
    if (!isConnected || currentView !== 'remote') return;
    screenDragCounter++;
    screenDropOverlay.classList.remove('hidden');
  });

  remoteSection.addEventListener('dragleave', (e) => {
    e.preventDefault();
    screenDragCounter--;
    if (screenDragCounter <= 0) {
      screenDragCounter = 0;
      screenDropOverlay.classList.add('hidden');
    }
  });

  remoteSection.addEventListener('dragover', (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
  });

  remoteSection.addEventListener('drop', async (e) => {
    e.preventDefault();
    screenDragCounter = 0;
    screenDropOverlay.classList.add('hidden');
    if (!isConnected || currentView !== 'remote') return;

    if (e.dataTransfer) {
      const files = await getFilesFromDataTransfer(e.dataTransfer);
      if (files.length > 0) {
        showToast(t('toast.transferring_desktop', { count: files.length }), 'info');
        files.forEach(f => uploadFileToHost(f, 'desktop'));
      }
    }
  });

  // --- Remote File Explorer Engine ---
  function requestBrowsePath(p) {
    if (!isConnected || !ws) return;
    ws.send(JSON.stringify({
      type: 'file_browse_request',
      path: p || ''
    }));
  }

  btnBrowseUp.addEventListener('click', () => {
    if (!remoteCurrentPath) return;
    requestBrowsePath(remoteParentPath);
  });

  if (btnExpandExplorer) {
    btnExpandExplorer.addEventListener('click', () => {
      shelfDrawer.classList.remove('open');
      switchView('files');
    });
  }

  function getFileSvgIcon(item) {
    if (item.is_dir) {
      return `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" style="color: var(--accent); vertical-align: middle; margin-right: 8px;"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>`;
    }
    const ext = (item.ext || (item.name ? item.name.slice(item.name.lastIndexOf('.')).toLowerCase() : '')).toLowerCase();

    if (['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp', '.ico'].includes(ext)) {
      return `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" style="color: #38BDF8; vertical-align: middle; margin-right: 8px;"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>`;
    }
    if (['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.webm', '.flv'].includes(ext)) {
      return `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" style="color: #F43F5E; vertical-align: middle; margin-right: 8px;"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>`;
    }
    if (['.mp3', '.wav', '.flac', '.ogg', '.m4a', '.aac'].includes(ext)) {
      return `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" style="color: #A855F7; vertical-align: middle; margin-right: 8px;"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>`;
    }
    if (['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.iso'].includes(ext)) {
      return `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" style="color: #EAB308; vertical-align: middle; margin-right: 8px;"><polyline points="21 8 21 21 3 21 3 8"/><rect x="1" y="3" width="22" height="5"/><line x1="10" y1="12" x2="14" y2="12"/></svg>`;
    }
    if (['.js', '.ts', '.jsx', '.tsx', '.py', '.html', '.css', '.json', '.c', '.cpp', '.cs', '.java', '.go', '.rs', '.bat', '.ps1', '.sh', '.sql', '.yaml', '.yml'].includes(ext)) {
      return `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" style="color: #34D399; vertical-align: middle; margin-right: 8px;"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>`;
    }
    if (['.ppt', '.pptx', '.pps', '.ppsx', '.odp', '.key'].includes(ext)) {
      return `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" style="color: #F97316; vertical-align: middle; margin-right: 8px;"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/><path d="M7 8h4a2 2 0 0 1 0 4H7z"/></svg>`;
    }
    if (['.txt', '.md', '.doc', '.docx', '.pdf', '.rtf', '.odt', '.csv', '.xlsx', '.xls'].includes(ext)) {
      return `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" style="color: #818CF8; vertical-align: middle; margin-right: 8px;"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><line x1="10" y1="9" x2="8" y2="9"/></svg>`;
    }
    return `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" style="color: var(--text-muted); vertical-align: middle; margin-right: 8px;"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>`;
  }

  function formatDate(mtime) {
    if (!mtime) return '—';
    const d = new Date(mtime);
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  // 1. Shelf Folder Browser (Drawer view)
  function renderFolderBrowser(data) {
    if (!data) return;
    remoteCurrentPath = data.current_path || '';
    remoteParentPath = data.parent_path || '';
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
      const icon = getFileSvgIcon(item);
      const sizeStr = isDir ? '' : ` (${formatBytes(item.size)})`;
      return `
        <div class="folder-item" data-path="${escapeHtml(item.path || item.name)}" data-isdir="${isDir}">
          <span class="folder-item__name">${icon} <span class="folder-item__label">${escapeHtml(item.name)}</span><span style="opacity:0.6;font-size:0.75rem;margin-left:4px;">${sizeStr}</span></span>
          <span class="shelf-file-actions">
            ${isDir ? `
              <svg class="shelf-chevron" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
            ` : `
              ${isEditableFile(item.name) ? `
                <button type="button" class="shelf-btn-action btn-shelf-edit" data-path="${escapeHtml(item.path || item.name)}" title="${t('files.action_edit') || 'Chỉnh sửa'}">
                  <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
                </button>
              ` : ''}
              <button type="button" class="shelf-btn-action btn-shelf-download" data-path="${escapeHtml(item.path || item.name)}" title="${t('files.action_download') || 'Tải về'}">
                <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
              </button>
            `}
          </span>
        </div>
      `;
    }).join('');

    remoteFolderList.querySelectorAll('.folder-item').forEach(el => {
      el.addEventListener('click', (e) => {
        if (e.target.closest('.btn-shelf-edit')) {
          e.stopPropagation();
          const itemPath = e.target.closest('.btn-shelf-edit').dataset.path;
          openFileInEditor(itemPath);
          return;
        }
        if (e.target.closest('.btn-shelf-download')) {
          e.stopPropagation();
          const itemPath = e.target.closest('.btn-shelf-download').dataset.path;
          ws.send(JSON.stringify({
            type: 'file_download_request',
            filepath: itemPath
          }));
          return;
        }
        const itemPath = el.dataset.path;
        const isDir = el.dataset.isdir === 'true';
        if (isDir) {
          requestBrowsePath(itemPath);
        } else if (isEditableFile(itemPath)) {
          openFileInEditor(itemPath);
        } else {
          ws.send(JSON.stringify({
            type: 'file_download_request',
            filepath: itemPath
          }));
        }
      });
    });
  }

  // 2. Full Dedicated File Explorer
  function renderFullFileExplorer(data) {
    if (!data) return;
    remoteCurrentPath = data.current_path || '';
    remoteParentPath = data.parent_path || '';
    currentExplorerDrives = data.drives || [];
    currentExplorerItems = data.items || [];

    if (currentView === 'files') {
      syncUrlWithState(true);
    }

    // Render Quick Drive Selector Pills
    if (explorerDrivesRow) {
      if (currentExplorerDrives.length > 0) {
        explorerDrivesRow.innerHTML = currentExplorerDrives.map(d => {
          const isAct = remoteCurrentPath.toLowerCase().startsWith(d.path.toLowerCase());
          return `
            <div class="drive-pill ${isAct ? 'active' : ''}" data-drive="${escapeHtml(d.path)}" title="${escapeHtml(d.name)} (${formatBytes(d.used)} / ${formatBytes(d.total)})">
              <span>${escapeHtml(d.name)}</span>
              <div class="drive-pill-bar"><div class="drive-pill-fill" style="width: ${d.percent || 0}%;"></div></div>
              <span style="font-size: 0.7rem; color: var(--text-faint);">${d.total ? formatBytes(d.free) + ' trống' : ''}</span>
            </div>
          `;
        }).join('');

        explorerDrivesRow.querySelectorAll('.drive-pill').forEach(pill => {
          pill.addEventListener('click', () => {
            requestBrowsePath(pill.dataset.drive);
          });
        });
      } else {
        explorerDrivesRow.innerHTML = '';
      }
    }

    // Render Breadcrumbs
    renderBreadcrumbs(remoteCurrentPath);

    // Render Items Table & Grid
    filterAndRenderItems();
  }

  function renderBreadcrumbs(path) {
    if (!explorerBreadcrumbs) return;

    if (!path) {
      explorerBreadcrumbs.innerHTML = `<span class="breadcrumb-item active"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:middle;margin-right:4px;"><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/></svg> <span data-i18n="files.drives_list">${t('files.drives_list')}</span></span>`;
      return;
    }

    const segments = [];
    segments.push({
      name: t('files.drives_root'),
      path: '',
      isHome: true
    });

    const isWindows = path.includes(':\\') || path.includes(':/');
    if (isWindows) {
      const parts = path.split(/[/\\]/).filter(Boolean);
      if (parts.length > 0) {
        const drive = parts[0];
        segments.push({
          name: drive.toUpperCase(),
          path: drive + '\\'
        });

        let current = drive;
        for (let i = 1; i < parts.length; i++) {
          current += '\\' + parts[i];
          segments.push({
            name: parts[i],
            path: current
          });
        }
      }
    } else {
      const parts = path.split('/').filter(Boolean);
      let current = '';
      for (const part of parts) {
        current += '/' + part;
        segments.push({
          name: part,
          path: current
        });
      }
    }

    explorerBreadcrumbs.innerHTML = segments.map((seg, idx) => {
      const isLast = idx === segments.length - 1;
      const sep = idx > 0 ? '<span class="breadcrumb-sep">/</span>' : '';
      if (seg.isHome) {
        return `
          <button class="breadcrumb-item" data-path="" title="Trang chủ ổ đĩa">
            <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
          </button>
        `;
      }
      return `
        ${sep}
        <button class="breadcrumb-item ${isLast ? 'active' : ''}" data-path="${escapeHtml(seg.path)}">
          ${escapeHtml(seg.name)}
        </button>
      `;
    }).join('');

    explorerBreadcrumbs.querySelectorAll('.breadcrumb-item').forEach(btn => {
      btn.addEventListener('click', () => {
        requestBrowsePath(btn.dataset.path);
      });
    });
  }

  function removeVietnameseDiacritics(str) {
    if (!str) return '';
    return str
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[đĐ]/g, m => m === 'đ' ? 'd' : 'D');
  }

  function filterAndRenderItems() {
    if (!explorerTableBody) return;

    const termRaw = (explorerSearchInput?.value || '').trim();
    const termLower = termRaw.toLowerCase().normalize('NFC');
    const termNoAccent = removeVietnameseDiacritics(termLower);

    const filtered = currentExplorerItems.filter(item => {
      if (!termRaw) return true;
      const name = (item.name || '').normalize('NFC');
      const nameLower = name.toLowerCase();
      if (nameLower.includes(termLower)) return true;
      const nameNoAccent = removeVietnameseDiacritics(nameLower);
      return nameNoAccent.includes(termNoAccent);
    });

    let totalDirs = 0;
    let totalFiles = 0;
    let totalSizeBytes = 0;

    filtered.forEach(it => {
      if (it.is_dir) {
        totalDirs++;
      } else {
        totalFiles++;
        totalSizeBytes += (it.size || 0);
      }
    });

    if (expStatusCount) expStatusCount.textContent = t('files.status_summary', { count: filtered.length, dirs: totalDirs, files: totalFiles });
    if (expStatusSize) expStatusSize.textContent = t('files.total_size', { size: formatBytes(totalSizeBytes) });

    const emptyText = termRaw ? t('files.not_found') : t('files.empty_folder');
    if (filtered.length === 0) {
      explorerTableBody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-faint); padding: 30px;">${emptyText}</td></tr>`;
      if (explorerGridContainer) explorerGridContainer.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--text-faint); padding: 30px;">${emptyText}</div>`;
      return;
    }

    // Render Table (List view)
    explorerTableBody.innerHTML = filtered.map(item => {
      const isDir = item.is_dir;
      const icon = getFileSvgIcon(item);
      const sizeStr = isDir ? '—' : formatBytes(item.size);
      const dateStr = formatDate(item.modified);
      const itemPath = escapeHtml(item.path || item.name);

      return `
        <tr class="explorer-row" data-path="${itemPath}" data-isdir="${isDir}">
          <td style="cursor: pointer;">
            <div style="display: flex; align-items: center;">
              ${icon}
              <span class="file-name-text" style="font-weight: ${isDir ? '600' : '400'}; color: ${isDir ? 'var(--text)' : 'var(--text-muted)'};">${escapeHtml(item.name)}</span>
            </div>
          </td>
          <td style="color: var(--text-faint);">${sizeStr}</td>
          <td style="color: var(--text-faint); font-size: 0.75rem;">${dateStr}</td>
          <td style="text-align: right;">
            <div style="display: inline-flex; gap: 4px; align-items: center; justify-content: flex-end;">
              ${!isDir && isEditableFile(item.name) ? `
                <button type="button" class="btn-action-icon btn-action-edit" data-path="${itemPath}" data-name="${escapeHtml(item.name)}" title="${t('files.action_edit_title') || t('files.action_edit')}">
                  <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                </button>
              ` : ''}
              <button type="button" class="btn-action-icon btn-action-copy" data-path="${itemPath}" data-name="${escapeHtml(item.name)}" title="${t('files.action_copy_title') || 'Sao chép'}">
                <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
              </button>
              <button type="button" class="btn-action-icon btn-action-cut" data-path="${itemPath}" data-name="${escapeHtml(item.name)}" title="${t('files.action_cut_title') || 'Cắt / Di chuyển'}">
                <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><line x1="20" y1="4" x2="8.12" y2="15.88"/><line x1="14.47" y1="14.48" x2="20" y2="20"/><line x1="8.12" y1="8.12" x2="12" y2="12"/></svg>
              </button>
              <button type="button" class="btn-action-icon btn-action-rename" data-path="${itemPath}" data-name="${escapeHtml(item.name)}" title="${t('files.action_rename_title') || 'Đổi tên'}">
                <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
              </button>
              ${!isDir ? `
                <button type="button" class="btn-action-icon btn-action-dl" data-path="${itemPath}" title="${t('files.action_download_title')}">
                  <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                </button>
              ` : ''}
              <button type="button" class="btn-action-icon btn-action-del" data-path="${itemPath}" data-name="${escapeHtml(item.name)}" title="${t('files.action_delete_title')}">
                <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join('');

    // Render Grid Cards
    if (explorerGridContainer) {
      explorerGridContainer.innerHTML = filtered.map(item => {
        const isDir = item.is_dir;
        const icon = getFileSvgIcon(item);
        const sizeStr = isDir ? t('files.folder_type') : formatBytes(item.size);
        const itemPath = escapeHtml(item.path || item.name);

        return `
          <div class="grid-item" data-path="${itemPath}" data-isdir="${isDir}" title="${escapeHtml(item.name)} (${sizeStr})">
            <div class="grid-item-icon" style="transform: scale(1.6); margin-bottom: 12px;">${icon}</div>
            <div class="grid-item-name">${escapeHtml(item.name)}</div>
            <div class="grid-item-size">${sizeStr}</div>
            <div class="grid-item-actions">
              ${!isDir && isEditableFile(item.name) ? `
                <button type="button" class="btn-action-icon btn-grid-edit" data-path="${itemPath}" data-name="${escapeHtml(item.name)}" title="${t('files.action_edit_title') || 'Chỉnh sửa'}" style="width:24px;height:24px;">
                  <svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                </button>
              ` : ''}
              <button type="button" class="btn-action-icon btn-grid-copy" data-path="${itemPath}" data-name="${escapeHtml(item.name)}" title="${t('files.action_copy_title') || 'Sao chép'}" style="width:24px;height:24px;">
                <svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
              </button>
              <button type="button" class="btn-action-icon btn-grid-cut" data-path="${itemPath}" data-name="${escapeHtml(item.name)}" title="${t('files.action_cut_title') || 'Cắt / Di chuyển'}" style="width:24px;height:24px;">
                <svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2"><circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><line x1="20" y1="4" x2="8.12" y2="15.88"/><line x1="14.47" y1="14.48" x2="20" y2="20"/><line x1="8.12" y1="8.12" x2="12" y2="12"/></svg>
              </button>
              <button type="button" class="btn-action-icon btn-grid-rename" data-path="${itemPath}" data-name="${escapeHtml(item.name)}" title="${t('files.action_rename_title') || 'Đổi tên'}" style="width:24px;height:24px;">
                <svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
              </button>
              ${!isDir ? `
                <button type="button" class="btn-action-icon btn-grid-dl" data-path="${itemPath}" title="${t('files.action_download_title') || 'Tải về'}" style="width:24px;height:24px;">
                  <svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                </button>
              ` : ''}
              <button type="button" class="btn-action-icon btn-grid-del" data-path="${itemPath}" data-name="${escapeHtml(item.name)}" title="${t('files.action_delete_title') || 'Xóa'}" style="width:24px;height:24px;">
                <svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
              </button>
            </div>
          </div>
        `;
      }).join('');
    }

    // Bind Row Double-click & Click
    explorerTableBody.querySelectorAll('.explorer-row').forEach(row => {
      row.addEventListener('dblclick', () => {
        const p = row.dataset.path;
        const isDir = row.dataset.isdir === 'true';
        if (isDir) {
          requestBrowsePath(p);
        } else if (isEditableFile(p)) {
          openFileInEditor(p);
        } else {
          ws.send(JSON.stringify({ type: 'file_download_request', filepath: p }));
        }
      });
      row.querySelector('.file-name-text')?.addEventListener('click', (e) => {
        const p = row.dataset.path;
        const isDir = row.dataset.isdir === 'true';
        if (isDir) {
          requestBrowsePath(p);
        }
      });
    });

    explorerTableBody.querySelectorAll('.btn-action-edit').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        openFileInEditor(btn.dataset.path);
      });
    });

    explorerTableBody.querySelectorAll('.btn-action-dl').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        ws.send(JSON.stringify({ type: 'file_download_request', filepath: btn.dataset.path }));
      });
    });

    function onCopyClick(path, name) {
      explorerClipboard = { action: 'copy', path, name };
      updatePasteButtonState();
      showToast(t('files.toast_copied', { name }) || `Đã sao chép "${name}". Chọn thư mục đích và nhấn Dán.`);
    }

    function onCutClick(path, name) {
      explorerClipboard = { action: 'cut', path, name };
      updatePasteButtonState();
      showToast(t('files.toast_cut', { name }) || `Đã cắt "${name}". Chọn thư mục đích và nhấn Dán.`);
    }

    async function onRenameClick(path, name) {
      const newName = await showPromptModal({
        title: t('files.rename_title') || 'Đổi tên tệp / thư mục',
        message: `Nhập tên mới cho "${name}":`,
        defaultValue: name,
        confirmText: t('dialog.btn_confirm') || 'Đổi tên',
        cancelText: t('dialog.btn_cancel') || 'Hủy'
      });
      if (newName && newName.trim() && newName.trim() !== name) {
        ws.send(JSON.stringify({
          type: 'file_rename_request',
          old_path: path,
          new_name: newName.trim()
        }));
      }
    }

    async function onDeleteClick(path, name) {
      const confirmed = await showConfirmModal({
        title: 'Xóa tệp / thư mục',
        message: t('files.delete_confirm', { name: name }),
        confirmText: t('dialog.btn_delete') || 'Xóa',
        cancelText: t('dialog.btn_cancel') || 'Hủy',
        danger: true
      });
      if (confirmed) {
        ws.send(JSON.stringify({ type: 'file_delete_request', filepath: path }));
      }
    }

    explorerTableBody.querySelectorAll('.btn-action-copy').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        onCopyClick(btn.dataset.path, btn.dataset.name);
      });
    });

    explorerTableBody.querySelectorAll('.btn-action-cut').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        onCutClick(btn.dataset.path, btn.dataset.name);
      });
    });

    explorerTableBody.querySelectorAll('.btn-action-rename').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        onRenameClick(btn.dataset.path, btn.dataset.name);
      });
    });

    explorerTableBody.querySelectorAll('.btn-action-del').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        onDeleteClick(btn.dataset.path, btn.dataset.name);
      });
    });

    explorerTableBody.querySelectorAll('.btn-action-edit').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        openFileInEditor(btn.dataset.path);
      });
    });

    explorerTableBody.querySelectorAll('.btn-action-dl').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        ws.send(JSON.stringify({
          type: 'file_download_request',
          filepath: btn.dataset.path
        }));
      });
    });

    if (explorerGridContainer) {
      explorerGridContainer.querySelectorAll('.grid-item').forEach(card => {
        card.addEventListener('dblclick', () => {
          const p = card.dataset.path;
          const isDir = card.dataset.isdir === 'true';
          if (isDir) {
            requestBrowsePath(p);
          } else if (isEditableFile(p)) {
            openFileInEditor(p);
          } else {
            ws.send(JSON.stringify({ type: 'file_download_request', filepath: p }));
          }
        });
        card.addEventListener('click', () => {
          const p = card.dataset.path;
          const isDir = card.dataset.isdir === 'true';
          if (isDir) {
            requestBrowsePath(p);
          }
        });

        card.querySelectorAll('.btn-grid-copy').forEach(btn => {
          btn.addEventListener('click', (e) => {
            e.stopPropagation();
            onCopyClick(btn.dataset.path, btn.dataset.name);
          });
        });

        card.querySelectorAll('.btn-grid-cut').forEach(btn => {
          btn.addEventListener('click', (e) => {
            e.stopPropagation();
            onCutClick(btn.dataset.path, btn.dataset.name);
          });
        });

        card.querySelectorAll('.btn-grid-rename').forEach(btn => {
          btn.addEventListener('click', (e) => {
            e.stopPropagation();
            onRenameClick(btn.dataset.path, btn.dataset.name);
          });
        });

        card.querySelectorAll('.btn-grid-del').forEach(btn => {
          btn.addEventListener('click', (e) => {
            e.stopPropagation();
            onDeleteClick(btn.dataset.path, btn.dataset.name);
          });
        });

        card.querySelectorAll('.btn-grid-edit').forEach(btn => {
          btn.addEventListener('click', (e) => {
            e.stopPropagation();
            openFileInEditor(btn.dataset.path);
          });
        });

        card.querySelectorAll('.btn-grid-dl').forEach(btn => {
          btn.addEventListener('click', (e) => {
            e.stopPropagation();
            ws.send(JSON.stringify({
              type: 'file_download_request',
              filepath: btn.dataset.path
            }));
          });
        });
      });
    }
  }

  // Bind Explorer Controls
  if (btnExpUp) {
    btnExpUp.addEventListener('click', () => {
      if (remoteParentPath !== undefined) {
        requestBrowsePath(remoteParentPath);
      }
    });
  }

  if (btnExpRefresh) {
    btnExpRefresh.addEventListener('click', () => {
      requestBrowsePath(remoteCurrentPath);
    });
  }

  if (btnExpNewFolder) {
    btnExpNewFolder.addEventListener('click', async () => {
      if (!remoteCurrentPath) {
        showToast(t('toast.select_dir_before_mkdir'), 'info');
        return;
      }
      const folderName = await showPromptModal({
        title: t('files.new_folder_title') || 'Tạo thư mục mới',
        message: 'Nhập tên thư mục mới cần tạo trên máy trạm:',
        defaultValue: 'New Folder',
        placeholder: 'Tên thư mục...',
        confirmText: t('dialog.btn_confirm') || 'Tạo thư mục',
        cancelText: t('dialog.btn_cancel') || 'Hủy'
      });
      if (folderName && folderName.trim()) {
        ws.send(JSON.stringify({
          type: 'file_create_folder_request',
          parent_dir: remoteCurrentPath,
          name: folderName.trim()
        }));
      }
    });
  }

  if (btnExpUpload && expFileInput) {
    btnExpUpload.addEventListener('click', () => {
      if (!remoteCurrentPath) {
        showToast(t('toast.select_dir_before_upload'), 'info');
        return;
      }
      expFileInput.click();
    });

    expFileInput.addEventListener('change', () => {
      if (!expFileInput.files || expFileInput.files.length === 0) return;
      Array.from(expFileInput.files).forEach(file => {
        uploadFileToHost(file, remoteCurrentPath);
      });
      expFileInput.value = '';
    });
  }

  // Direct Path Input Toggling
  if (btnTogglePathInput) {
    btnTogglePathInput.addEventListener('click', () => {
      const isHidden = explorerPathInputWrap.classList.contains('hidden');
      if (isHidden) {
        explorerPathInputWrap.classList.remove('hidden');
        explorerBreadcrumbs.classList.add('hidden');
        btnTogglePathInput.classList.add('hidden');
        explorerDirectPathInput.value = remoteCurrentPath;
        explorerDirectPathInput.focus();
        explorerDirectPathInput.select();
      } else {
        explorerPathInputWrap.classList.add('hidden');
        explorerBreadcrumbs.classList.remove('hidden');
        btnTogglePathInput.classList.remove('hidden');
      }
    });
  }

  if (btnGoDirectPath) {
    btnGoDirectPath.addEventListener('click', () => {
      const pathVal = explorerDirectPathInput.value.trim();
      if (pathVal) {
        requestBrowsePath(pathVal);
        explorerPathInputWrap.classList.add('hidden');
        explorerBreadcrumbs.classList.remove('hidden');
        btnTogglePathInput?.classList.remove('hidden');
      }
    });
  }

  if (explorerDirectPathInput) {
    explorerDirectPathInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        const pathVal = explorerDirectPathInput.value.trim();
        if (pathVal) {
          requestBrowsePath(pathVal);
          explorerPathInputWrap.classList.add('hidden');
          explorerBreadcrumbs.classList.remove('hidden');
        }
      } else if (e.key === 'Escape') {
        explorerPathInputWrap.classList.add('hidden');
        explorerBreadcrumbs.classList.remove('hidden');
      }
    });
  }

  if (btnCancelDirectPath) {
    btnCancelDirectPath.addEventListener('click', () => {
      explorerPathInputWrap.classList.add('hidden');
      explorerBreadcrumbs.classList.remove('hidden');
      btnTogglePathInput?.classList.remove('hidden');
    });
  }

  // Search Filter
  if (explorerSearchInput) {
    explorerSearchInput.addEventListener('input', () => {
      filterAndRenderItems();
    });
  }

  // View Mode: List vs Grid
  if (btnModeList && btnModeGrid) {
    btnModeList.addEventListener('click', () => {
      explorerViewMode = 'list';
      btnModeList.classList.add('on');
      btnModeGrid.classList.remove('on');
      explorerListContainer.classList.remove('hidden');
      explorerGridContainer.classList.add('hidden');
    });

    btnModeGrid.addEventListener('click', () => {
      explorerViewMode = 'grid';
      btnModeGrid.classList.add('on');
      btnModeList.classList.remove('on');
      explorerListContainer.classList.add('hidden');
      explorerGridContainer.classList.remove('hidden');
    });
  }

  // Drag and drop onto Explorer
  if (explorerDropTarget) {
    explorerDropTarget.addEventListener('dragover', (e) => {
      e.preventDefault();
      explorerDropTarget.classList.add('drag-over');
    });
    explorerDropTarget.addEventListener('dragleave', () => {
      explorerDropTarget.classList.remove('drag-over');
    });
    explorerDropTarget.addEventListener('drop', async (e) => {
      e.preventDefault();
      explorerDropTarget.classList.remove('drag-over');
      if (e.dataTransfer) {
        const files = await getFilesFromDataTransfer(e.dataTransfer);
        if (files.length > 0) {
          showToast(t('toast.uploading_to_cur_dir', { count: files.length }), 'info');
          files.forEach(f => uploadFileToHost(f, remoteCurrentPath));
        }
      }
    });
  }

  function formatBytes(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
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

  // --- DIRECT ONLINE FILE EDITOR CONTROLLER ---
  const EDITABLE_EXTENSIONS = new Set([
    '.txt', '.json', '.js', '.jsx', '.ts', '.tsx', '.py', '.html', '.htm',
    '.css', '.scss', '.sass', '.less', '.log', '.bat', '.cmd', '.ps1', '.sh',
    '.ini', '.cfg', '.conf', '.config', '.xml', '.yaml', '.yml', '.md', '.markdown',
    '.env', '.csv', '.sql', '.php', '.java', '.c', '.cpp', '.h', '.hpp',
    '.cs', '.go', '.rs', '.lua', '.properties', '.toml', '.gitignore',
    '.dockerfile', '.vue', '.svelte', '.rb', '.pl', '.r', '.dart', '.swift',
    '.kt', '.gradle', '.svg', '.lock'
  ]);

  function isEditableFile(filename) {
    if (!filename) return false;
    const cleanName = filename.split(/[/\\]/).pop();
    const dotIdx = cleanName.lastIndexOf('.');
    if (dotIdx === -1) return true; // Extensionless file like Makefile, .env, Dockerfile
    const ext = cleanName.substring(dotIdx).toLowerCase();
    return EDITABLE_EXTENSIONS.has(ext);
  }

  function openFileInEditor(filepath) {
    if (!isConnected) {
      showToast(t('toast.connect_before_edit'), 'info');
      return;
    }
    showToast(t('toast.opening_remote_file'), 'info', 1500);
    currentEditingFilePath = filepath;
    ws.send(JSON.stringify({
      type: 'file_read_request',
      filepath: filepath
    }));
  }

  function handleFileReadResponse(msg) {
    if (!msg.success) {
      showToast(t('toast.open_file_failed', { error: msg.error }), 'error');
      return;
    }
    editorFileName.textContent = msg.filename || 'Tệp không tên';
    editorFilePath.textContent = msg.filepath || '';
    editorFilePath.title = msg.filepath || '';
    fileEditorTextarea.value = msg.content || '';
    currentEditorOriginalContent = msg.content || '';
    editorDirtyBadge.textContent = t('editor.saved');
    editorDirtyBadge.className = 'editor-badge editor-badge--clean';
    editorEncodingBadge.textContent = (msg.encoding || 'UTF-8').toUpperCase();
    editorSaveTime.textContent = t('editor.saved_at', { time: new Date().toLocaleTimeString() });
    updateEditorStats();
    fileEditorModal.classList.remove('hidden');
    setTimeout(() => fileEditorTextarea.focus(), 60);
  }

  function handleFileSaveResponse(msg) {
    btnSaveFile.disabled = false;
    btnSaveFile.style.opacity = '1';
    if (msg.success) {
      currentEditorOriginalContent = fileEditorTextarea.value;
      editorDirtyBadge.textContent = t('editor.saved');
      editorDirtyBadge.className = 'editor-badge editor-badge--clean';
      editorSaveTime.textContent = t('editor.saved_at', { time: new Date().toLocaleTimeString() });
      showToast(t('editor.save_success'), 'success');
      if (currentView === 'files') {
        requestBrowsePath(remoteCurrentPath);
      }
    } else {
      editorSaveTime.textContent = t('editor.save_error', { error: msg.error || '' });
      showToast(t('editor.save_error', { error: msg.error || '' }), 'error');
    }
  }

  function saveCurrentFile() {
    if (!currentEditingFilePath) return;
    if (!isConnected) {
      showToast(t('editor.save_error', { error: t('ro.disconnected') }), 'error');
      return;
    }
    btnSaveFile.disabled = true;
    btnSaveFile.style.opacity = '0.6';
    editorSaveTime.textContent = t('editor.saving');
    ws.send(JSON.stringify({
      type: 'file_save_request',
      filepath: currentEditingFilePath,
      content: fileEditorTextarea.value,
      encoding: 'utf-8'
    }));
  }

  async function closeFileEditor() {
    const isDirty = fileEditorTextarea.value !== currentEditorOriginalContent;
    if (isDirty) {
      const confirmed = await showConfirmModal({
        title: t('dialog.confirm_title') || 'Đóng tệp chưa lưu',
        message: t('editor.discard_confirm') || 'Tập tin đã được chỉnh sửa nhưng chưa lưu. Bạn có chắc chắn muốn đóng mà không lưu?',
        confirmText: t('dialog.btn_discard') || 'Đóng & Hủy',
        cancelText: t('dialog.btn_keep_editing') || 'Tiếp tục sửa',
        danger: true
      });
      if (!confirmed) {
        return;
      }
    }
    fileEditorModal.classList.add('hidden');
    currentEditingFilePath = '';
    currentEditorOriginalContent = '';
  }

  function updateEditorStats() {
    const val = fileEditorTextarea.value || '';
    const lines = val.split('\n').length;
    const chars = val.length;
    editorStats.textContent = t('editor.stats', { lines: lines.toLocaleString(), chars: chars.toLocaleString() });
    updateCursorPos();
  }

  function updateCursorPos() {
    const val = fileEditorTextarea.value || '';
    const selStart = fileEditorTextarea.selectionStart || 0;
    const upToCursor = val.substring(0, selStart);
    const lineNum = upToCursor.split('\n').length;
    const lastNewline = upToCursor.lastIndexOf('\n');
    const colNum = lastNewline === -1 ? selStart + 1 : selStart - lastNewline;
    editorCursorPos.textContent = t('editor.cursor', { line: lineNum, col: colNum });
  }

  if (fileEditorTextarea) {
    fileEditorTextarea.addEventListener('input', () => {
      const isDirty = fileEditorTextarea.value !== currentEditorOriginalContent;
      editorDirtyBadge.textContent = isDirty ? t('editor.dirty') : t('editor.saved');
      editorDirtyBadge.className = isDirty ? 'editor-badge editor-badge--dirty' : 'editor-badge editor-badge--clean';
      updateEditorStats();
    });

    fileEditorTextarea.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
        e.preventDefault();
        saveCurrentFile();
      } else if (e.key === 'Tab') {
        e.preventDefault();
        const start = fileEditorTextarea.selectionStart;
        const end = fileEditorTextarea.selectionEnd;
        fileEditorTextarea.value = fileEditorTextarea.value.substring(0, start) + '  ' + fileEditorTextarea.value.substring(end);
        fileEditorTextarea.selectionStart = fileEditorTextarea.selectionEnd = start + 2;
        fileEditorTextarea.dispatchEvent(new Event('input'));
      } else if (e.key === 'Escape') {
        closeFileEditor();
      }
    });

    fileEditorTextarea.addEventListener('keyup', updateCursorPos);
    fileEditorTextarea.addEventListener('click', updateCursorPos);
  }

  if (editorWrapCheckbox) {
    editorWrapCheckbox.addEventListener('change', () => {
      fileEditorTextarea.style.whiteSpace = editorWrapCheckbox.checked ? 'pre-wrap' : 'pre';
      fileEditorTextarea.style.wordBreak = editorWrapCheckbox.checked ? 'break-all' : 'normal';
    });
  }

  if (btnSaveFile) {
    btnSaveFile.addEventListener('click', saveCurrentFile);
  }

  if (btnCloseFileEditor) {
    btnCloseFileEditor.addEventListener('click', closeFileEditor);
  }

  if (fileEditorModal) {
    fileEditorModal.addEventListener('click', (e) => {
      if (e.target === fileEditorModal) {
        closeFileEditor();
      }
    });
  }

  // --- AUDIT LOGS MANAGEMENT ---
  async function loadAuditLogs() {
    if (!authToken) {
      if (auditTableBody) {
        auditTableBody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-faint); padding: 24px;">Vui lòng đăng nhập để xem nhật ký kiểm toán</td></tr>';
      }
      return;
    }

    const action = auditActionFilter ? auditActionFilter.value : 'all';
    const search = auditSearchInput ? auditSearchInput.value.trim() : '';
    const offset = auditPage * auditLimit;

    const params = new URLSearchParams({
      limit: auditLimit,
      offset: offset
    });
    if (action && action !== 'all') params.set('action', action);
    if (search) params.set('search', search);

    try {
      const res = await apiFetch(`/api/audit-logs?${params.toString()}`);
      if (res && res.success) {
        auditTotal = res.total || 0;
        renderAuditLogs(res.logs || [], auditTotal);
      } else {
        showToast(res.message || 'Không thể tải nhật ký', 'error');
      }
    } catch (err) {
      showToast(t('toast.audit_load_failed', { error: err.message }), 'error');
    }
  }

  function getActionBadge(action) {
    let color = '#94A3B8';
    let bg = 'rgba(148, 163, 184, 0.12)';
    let text = action;

    switch (action) {
      case 'SESSION_CONNECTED':
        color = '#22C55E'; bg = 'rgba(34, 197, 94, 0.15)'; text = 'KẾT NỐI PHIÊN'; break;
      case 'SESSION_DISCONNECTED':
        color = '#EF4444'; bg = 'rgba(239, 68, 68, 0.15)'; text = 'NGẮT KẾT NỐI'; break;
      case 'CONNECT_PIN_FAILED':
        color = '#F43F5E'; bg = 'rgba(244, 63, 94, 0.15)'; text = 'SAI MÃ PIN'; break;
      case 'HOST_ONLINE':
        color = '#38BDF8'; bg = 'rgba(56, 189, 248, 0.15)'; text = 'TRẠM ONLINE'; break;
      case 'HOST_OFFLINE':
        color = '#64748B'; bg = 'rgba(100, 116, 139, 0.15)'; text = 'TRẠM OFFLINE'; break;
      case 'CMD_EXEC':
        color = '#38BDF8'; bg = 'rgba(56, 189, 248, 0.15)'; text = 'LỆNH CMD'; break;
      case 'FILE_BROWSE':
        color = '#A855F7'; bg = 'rgba(168, 85, 247, 0.15)'; text = 'XEM THƯ MỤC'; break;
      case 'FILE_DOWNLOAD':
        color = '#A855F7'; bg = 'rgba(168, 85, 247, 0.15)'; text = 'TẢI FILE VỀ'; break;
      case 'FILE_UPLOAD':
        color = '#10B981'; bg = 'rgba(16, 185, 129, 0.15)'; text = 'TẢI FILE LÊN'; break;
      case 'FILE_DELETE':
        color = '#EF4444'; bg = 'rgba(239, 68, 68, 0.15)'; text = 'XÓA TỆP'; break;
      case 'FILE_MKDIR':
        color = '#A855F7'; bg = 'rgba(168, 85, 247, 0.15)'; text = 'TẠO THƯ MỤC'; break;
      case 'PROCESS_KILL':
        color = '#EF4444'; bg = 'rgba(239, 68, 68, 0.15)'; text = 'DỪNG TIẾN TRÌNH'; break;
      case 'POWER_ACTION':
        color = '#F59E0B'; bg = 'rgba(245, 158, 11, 0.15)'; text = 'NGUỒN / KHÓA'; break;
      case 'BLOCK_INPUT':
        color = '#EAB308'; bg = 'rgba(234, 179, 8, 0.15)'; text = 'KHÓA THAO TÁC'; break;
      case 'CLIPBOARD_SYNC':
        color = '#06B6D4'; bg = 'rgba(6, 182, 212, 0.15)'; text = 'CLIPBOARD'; break;
      case 'AUTH_LOGIN':
        color = '#10B981'; bg = 'rgba(16, 185, 129, 0.15)'; text = 'ĐĂNG NHẬP'; break;
      case 'AUTH_LOGIN_FAILED':
        color = '#EF4444'; bg = 'rgba(239, 68, 68, 0.15)'; text = 'ĐĂNG NHẬP LỖI'; break;
      case 'AUTH_REGISTER':
        color = '#10B981'; bg = 'rgba(16, 185, 129, 0.15)'; text = 'ĐĂNG KÝ'; break;
      case 'DEVICE_LINKED':
        color = '#38BDF8'; bg = 'rgba(56, 189, 248, 0.15)'; text = 'LIÊN KẾT TRẠM'; break;
    }

    return `<span style="display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: 600; color: ${color}; background: ${bg}; border: 1px solid ${color}40;">${text}</span>`;
  }

  function formatAuditDetails(action, detailsStr) {
    if (!detailsStr) return '--';
    let d;
    try {
      d = typeof detailsStr === 'object' ? detailsStr : JSON.parse(detailsStr);
    } catch {
      return escapeHtml(String(detailsStr));
    }

    if (action === 'CMD_EXEC') {
      return `<code style="color: var(--accent); background: var(--ink-2); padding: 2px 6px; border-radius: 4px;">${escapeHtml(d.command || '')}</code>`;
    }
    if (action === 'FILE_BROWSE') {
      return `Thư mục: <code style="color: var(--text);">${escapeHtml(d.path || '')}</code>`;
    }
    if (action === 'FILE_DOWNLOAD') {
      return `Tệp: <strong style="color: var(--text);">${escapeHtml(d.filename || '')}</strong> (${escapeHtml(d.path || '')})`;
    }
    if (action === 'FILE_UPLOAD') {
      return `Tệp: <strong style="color: var(--text);">${escapeHtml(d.filename || '')}</strong> (${formatBytes(d.size || 0)}) → ${escapeHtml(d.path || '')}`;
    }
    if (action === 'FILE_DELETE') {
      return `Đã xóa: <code style="color: #EF4444;">${escapeHtml(d.path || '')}</code>`;
    }
    if (action === 'PROCESS_KILL') {
      return `PID: <strong>${d.pid}</strong> (${escapeHtml(d.name || '')})`;
    }
    if (action === 'POWER_ACTION') {
      return `Hành động: <strong>${escapeHtml(d.action || '')}</strong>`;
    }
    if (action === 'BLOCK_INPUT') {
      return `Trạng thái: <strong>${d.blocked ? 'Đã khóa chuột/phím' : 'Đã mở khóa'}</strong>`;
    }
    if (action === 'SESSION_DISCONNECTED') {
      return `Thời lượng phiên: <strong>${escapeHtml(d.durationText || (d.durationSec + 's'))}</strong>`;
    }

    const items = Object.entries(d).map(([k, v]) => `${escapeHtml(k)}: ${escapeHtml(String(v))}`);
    return items.join(' | ') || '--';
  }

  function renderAuditLogs(logs, total) {
    if (!auditTableBody) return;
    if (!logs || logs.length === 0) {
      auditTableBody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-faint); padding: 24px;">${t('audit.empty')}</td></tr>`;
      if (auditPageSummary) auditPageSummary.textContent = t('audit.summary', { showing: '0', total: '0' });
      if (btnAuditPrev) btnAuditPrev.disabled = true;
      if (btnAuditNext) btnAuditNext.disabled = true;
      if (auditPageIndicator) auditPageIndicator.textContent = '1 / 1';
      return;
    }

    const totalPages = Math.ceil(total / auditLimit) || 1;
    const startIdx = auditPage * auditLimit + 1;
    const endIdx = Math.min((auditPage + 1) * auditLimit, total);
    if (auditPageSummary) auditPageSummary.textContent = t('audit.summary', { showing: `${startIdx} - ${endIdx}`, total });
    if (auditPageIndicator) auditPageIndicator.textContent = `${auditPage + 1} / ${totalPages}`;

    if (btnAuditPrev) btnAuditPrev.disabled = auditPage <= 0;
    if (btnAuditNext) btnAuditNext.disabled = auditPage >= totalPages - 1;

    auditTableBody.innerHTML = logs.map(l => {
      const dt = new Date(l.timestamp);
      const timeStr = `${String(dt.getDate()).padStart(2, '0')}/${String(dt.getMonth() + 1).padStart(2, '0')} ${String(dt.getHours()).padStart(2, '0')}:${String(dt.getMinutes()).padStart(2, '0')}:${String(dt.getSeconds()).padStart(2, '0')}`;
      const actionBadge = getActionBadge(l.action);
      const userDisplay = escapeHtml(l.username || t('audit.anonymous'));
      const ipDisplay = escapeHtml(l.client_ip || '127.0.0.1');
      const deviceDisplay = escapeHtml(l.client_device || 'Unknown');
      const targetDisplay = l.room_id
        ? `<strong style="color: var(--accent);">${escapeHtml(l.target_device || 'Workstation')}</strong><br><span style="color: var(--text-faint); font-size: 0.7rem;">${escapeHtml(l.room_id)} (${escapeHtml(l.target_os || 'Win')})</span>`
        : '<span style="color: var(--text-faint);">--</span>';
      const detailsHtml = formatAuditDetails(l.action, l.details);

      return `
        <tr>
          <td style="color: var(--text-muted); font-size: 0.75rem;">${timeStr}</td>
          <td>${actionBadge}</td>
          <td>
            <strong style="color: var(--text);">${userDisplay}</strong>
            <div style="font-size: 0.7rem; color: var(--accent); font-family: var(--font-mono);">${ipDisplay}</div>
            <div style="font-size: 0.68rem; color: var(--text-muted);">${deviceDisplay}</div>
          </td>
          <td>${targetDisplay}</td>
          <td style="font-size: 0.75rem; word-break: break-all;">${detailsHtml}</td>
        </tr>
      `;
    }).join('');
  }

  if (btnRefreshAudit) {
    btnRefreshAudit.addEventListener('click', () => {
      loadAuditLogs();
      showToast(t('audit.refreshed'), 'info');
    });
  }

  if (btnExportAuditCsv) {
    btnExportAuditCsv.addEventListener('click', () => {
      const action = auditActionFilter ? auditActionFilter.value : 'all';
      const search = auditSearchInput ? auditSearchInput.value.trim() : '';
      const params = new URLSearchParams({ format: 'csv' });
      if (action && action !== 'all') params.set('action', action);
      if (search) params.set('search', search);

      const downloadUrl = `/api/audit-logs/export?${params.toString()}`;
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = `meikova-relay-audit-logs-${Date.now()}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      showToast(t('audit.exporting'), 'success');
    });
  }

  if (btnAuditPrev) {
    btnAuditPrev.addEventListener('click', () => {
      if (auditPage > 0) {
        auditPage--;
        loadAuditLogs();
      }
    });
  }

  if (btnAuditNext) {
    btnAuditNext.addEventListener('click', () => {
      auditPage++;
      loadAuditLogs();
    });
  }

  if (auditActionFilter) {
    auditActionFilter.addEventListener('change', () => {
      auditPage = 0;
      loadAuditLogs();
    });
  }

  if (auditSearchInput) {
    auditSearchInput.addEventListener('input', () => {
      clearTimeout(auditSearchDebounce);
      auditSearchDebounce = setTimeout(() => {
        auditPage = 0;
        loadAuditLogs();
      }, 300);
    });
  }

  // -------------------------------------------------------------------------
  // Meikova Relay: Multiplatform Native Apps Download Modal & Tab Switcher
  // -------------------------------------------------------------------------
  const btnNavDownloadApps = document.getElementById('btnNavDownloadApps');
  const modalDownloadApps = document.getElementById('modalDownloadApps');
  const btnCloseDownloadApps = document.getElementById('btnCloseDownloadApps');
  const tabBtnHost = document.getElementById('tabBtnHost');
  const tabBtnClient = document.getElementById('tabBtnClient');
  const dlTabPaneHost = document.getElementById('dlTabPaneHost');
  const dlTabPaneClient = document.getElementById('dlTabPaneClient');
  const btnCopyHostCmd = document.getElementById('btnCopyHostCmd');
  const btnCopyHostServerUrl = document.getElementById('btnCopyHostServerUrl');
  const btnCopyClientGatewayUrl = document.getElementById('btnCopyClientGatewayUrl');
  const relayHostServerIp = document.getElementById('relayHostServerIp');
  const relayClientGatewayIp = document.getElementById('relayClientGatewayIp');
  const relayClientQr = document.getElementById('relay-client-qr');
  const relayClientLink = document.getElementById('relay-client-link');
  const btnPwaInstallRelay = document.getElementById('btnPwaInstallRelay');
  const pwaBadgeRelay = document.getElementById('pwaBadgeRelay');
  const pwaDescRelay = document.getElementById('pwaDescRelay');

  function setRelayViewerPlatformTab(platform) {
    document.querySelectorAll('.relay-viewer-platform-tab').forEach((b) => {
      const isActive = b.getAttribute('data-viewer-platform') === platform;
      b.classList.toggle('is-active', isActive);
      b.setAttribute('aria-selected', isActive ? 'true' : 'false');
    });
    document.querySelectorAll('.relay-viewer-platform-pane').forEach((p) => {
      p.classList.toggle('is-active', p.getAttribute('data-viewer-pane') === platform);
    });
  }

  document.querySelectorAll('.relay-viewer-platform-tab').forEach((tabBtn) => {
    tabBtn.addEventListener('click', () => {
      const platform = tabBtn.getAttribute('data-viewer-platform');
      if (platform) setRelayViewerPlatformTab(platform);
    });
  });

  async function updateRelayModalData() {
    const currentOrigin = window.location.origin;
    const hostname = window.location.hostname;
    const isTailscale = hostname.startsWith('100.');
    const isHfSpace = hostname.includes('hf.space') || hostname.includes('huggingface.co');
    const isLocal = hostname === 'localhost' || hostname === '127.0.0.1';

    let displayUrl = currentOrigin;

    // On local host (Desktop or dev server), resolve reachable Tailscale/LAN IP from server (matching Harvest & Loop)
    if (isLocal) {
      try {
        const res = await fetch('/api/host-info');
        if (res.ok) {
          const info = await res.json();
          if (info && info.active_url && info.active_url.includes('trycloudflare.com')) {
            displayUrl = info.active_url;
          } else if (info && info.tailscale_url) {
            displayUrl = info.tailscale_url;
          } else if (info && info.lan_url && info.lan_ip !== '127.0.0.1') {
            displayUrl = info.lan_url;
          }
        }
      } catch (_) {}
    }

    const accountName = currentUser ? (currentUser.username || currentUser.email || 'User') : 'User';
    const userId = currentUser ? (currentUser.id || currentUser.userId || '') : '';
    const relayWs = defaultWsUrl || displayUrl.replace(/^http/, 'ws');

    if (relayHostServerIp) relayHostServerIp.textContent = displayUrl;
    if (relayClientGatewayIp) relayClientGatewayIp.textContent = displayUrl;

    const relayHostServerTag = document.getElementById('relayHostServerTag');
    const relayClientGatewayTag = document.getElementById('relayClientGatewayTag');
    let tagText = 'Máy chủ Web';
    if (displayUrl.includes('trycloudflare.com')) tagText = 'Cloudflare Tunnel (WAN)';
    else if (isHfSpace) tagText = 'Hugging Face Space';
    else if (displayUrl.includes('100.') || isTailscale) tagText = 'Tailscale Mesh';
    else if (displayUrl.includes('192.168.') || displayUrl.includes('10.') || displayUrl.includes('172.')) tagText = 'Mạng Wi-Fi (LAN)';
    else if (isLocal) tagText = 'Local Host';

    if (relayHostServerTag) relayHostServerTag.textContent = tagText;
    if (relayClientGatewayTag) relayClientGatewayTag.textContent = tagText;

    if (relayClientLink) {
      relayClientLink.href = displayUrl;
      relayClientLink.textContent = `${displayUrl} ↗`;
    }

    const scanDesc = document.getElementById('relay-client-scan-desc');
    if (scanDesc) {
      if (isHfSpace) {
        scanDesc.textContent = ' để mở trực tiếp qua Hugging Face Space.';
      } else if (displayUrl.includes('100.') || isTailscale) {
        scanDesc.textContent = ' (qua Tailscale) để mở bảng điều khiển từ xa trên điện thoại.';
      } else if (displayUrl.includes('192.168.') || displayUrl.includes('10.') || displayUrl.includes('172.')) {
        scanDesc.textContent = ' (cùng mạng Wi-Fi) để mở bảng điều khiển từ xa trên điện thoại.';
      } else {
        scanDesc.textContent = ' để mở bảng điều khiển từ xa trực tiếp trên điện thoại.';
      }
    }

    if (relayClientQr) {
      relayClientQr.src = `/api/qr?data=${encodeURIComponent(displayUrl)}`;
      relayClientQr.onerror = () => {
        relayClientQr.src = `https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=${encodeURIComponent(displayUrl)}`;
      };
    }

    const setupBatUrl = `${displayUrl}/api/download/setup.bat?account=${encodeURIComponent(accountName)}&userId=${encodeURIComponent(userId)}&relay=${encodeURIComponent(relayWs)}`;
    const linkDownloadSetupBat = document.getElementById('linkDownloadSetupBat');
    if (linkDownloadSetupBat) {
      linkDownloadSetupBat.href = setupBatUrl;
    }

    const btnCopyHostCmd = document.getElementById('btnCopyHostCmd');
    if (btnCopyHostCmd) {
      const irmCmd = `irm ${setupBatUrl} | iex`;
      btnCopyHostCmd.setAttribute('data-cmd', irmCmd);
      const codeTag = btnCopyHostCmd.closest('.dl-cmd-box')?.querySelector('code');
      if (codeTag) codeTag.textContent = irmCmd;
    }

    const setupLinuxUrl = `${displayUrl}/api/download/setup-linux.sh?account=${encodeURIComponent(accountName)}&userId=${encodeURIComponent(userId)}&relay=${encodeURIComponent(relayWs)}`;
    const linkDownloadSetupLinux = document.getElementById('linkDownloadSetupLinux');
    if (linkDownloadSetupLinux) {
      linkDownloadSetupLinux.href = setupLinuxUrl;
    }

    const setupMacUrl = `${displayUrl}/api/download/setup-macos.sh?account=${encodeURIComponent(accountName)}&userId=${encodeURIComponent(userId)}&relay=${encodeURIComponent(relayWs)}`;
    const linkDownloadSetupMac = document.getElementById('linkDownloadSetupMac');
    if (linkDownloadSetupMac) {
      linkDownloadSetupMac.href = setupMacUrl;
    }

    // Winget CLI command toggle between Host and Client & copy on click
    const txtWingetRelayCmd = document.getElementById('txtWingetRelayCmd');
    const btnCopyWingetRelay = document.getElementById('btnCopyWingetRelay');

    if (tabBtnHost && tabBtnClient && txtWingetRelayCmd && !txtWingetRelayCmd.dataset.initialized) {
      txtWingetRelayCmd.dataset.initialized = 'true';
      tabBtnHost.addEventListener('click', () => {
        txtWingetRelayCmd.textContent = 'winget install Meikova.Relay.Host';
      });
      tabBtnClient.addEventListener('click', () => {
        txtWingetRelayCmd.textContent = 'winget install Meikova.Relay.Client';
      });
    }

    if (btnCopyWingetRelay && txtWingetRelayCmd && !btnCopyWingetRelay.dataset.initialized) {
      btnCopyWingetRelay.dataset.initialized = 'true';
      btnCopyWingetRelay.addEventListener('click', () => {
        const cmd = txtWingetRelayCmd.textContent.trim();
        copyFeedback(btnCopyWingetRelay, cmd, 'Đã sao chép lệnh Winget!');
      });
    }

    // Auto-detect viewer device
    const ua = navigator.userAgent || '';
    let targetPlatform = 'desktop';
    if (/iPad|iPhone|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)) {
      targetPlatform = 'ios';
    } else if (/Android/.test(ua)) {
      targetPlatform = 'android';
    }
    setRelayViewerPlatformTab(targetPlatform);
  }

  const copyFeedback = async (btn, text, successMsg) => {
    try {
      await navigator.clipboard.writeText(text);
      if (typeof showToast === 'function') {
        showToast(successMsg, 'success');
      }
      if (btn) {
        const orig = btn.innerHTML;
        btn.innerHTML = `<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg><span>Đã chép</span>`;
        setTimeout(() => { btn.innerHTML = orig; }, 2000);
      }
    } catch {
      const input = document.createElement('textarea');
      input.value = text;
      document.body.appendChild(input);
      input.select();
      document.execCommand('copy');
      document.body.removeChild(input);
      if (typeof showToast === 'function') {
        showToast(successMsg, 'success');
      }
    }
  };

  if (btnCopyHostServerUrl) {
    btnCopyHostServerUrl.addEventListener('click', () => {
      copyFeedback(btnCopyHostServerUrl, window.location.origin, 'Đã sao chép địa chỉ máy chủ Relay!');
    });
  }

  if (btnCopyClientGatewayUrl) {
    btnCopyClientGatewayUrl.addEventListener('click', () => {
      copyFeedback(btnCopyClientGatewayUrl, window.location.origin, 'Đã sao chép liên kết điều khiển!');
    });
  }

  let relayPwaPrompt = null;
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    relayPwaPrompt = e;
    if (pwaBadgeRelay) pwaBadgeRelay.textContent = '1-CLICK';
    if (pwaDescRelay) pwaDescRelay.textContent = 'Cài đặt ngay';
  });

  window.addEventListener('appinstalled', () => {
    relayPwaPrompt = null;
    if (pwaBadgeRelay) pwaBadgeRelay.textContent = 'INSTALLED';
    if (pwaDescRelay) pwaDescRelay.textContent = 'Đã cài làm App';
  });

  if (btnNavDownloadApps && modalDownloadApps) {
    const openDownloadModal = () => {
      updateRelayModalData();
      modalDownloadApps.classList.remove('hidden');
    };
    const closeDownloadModal = () => {
      modalDownloadApps.classList.add('hidden');
    };

    btnNavDownloadApps.addEventListener('click', openDownloadModal);
    if (btnCloseDownloadApps) {
      btnCloseDownloadApps.addEventListener('click', closeDownloadModal);
    }

    modalDownloadApps.addEventListener('click', (e) => {
      if (e.target === modalDownloadApps) {
        closeDownloadModal();
      }
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !modalDownloadApps.classList.contains('hidden')) {
        closeDownloadModal();
      }
    });
  }

  // Switch tabs between Host and Client
  if (tabBtnHost && tabBtnClient && dlTabPaneHost && dlTabPaneClient) {
    tabBtnHost.addEventListener('click', () => {
      tabBtnHost.classList.add('on');
      tabBtnClient.classList.remove('on');
      tabBtnHost.setAttribute('aria-selected', 'true');
      tabBtnClient.setAttribute('aria-selected', 'false');
      dlTabPaneHost.classList.remove('hidden');
      dlTabPaneClient.classList.add('hidden');
    });

    tabBtnClient.addEventListener('click', () => {
      tabBtnClient.classList.add('on');
      tabBtnHost.classList.remove('on');
      tabBtnClient.setAttribute('aria-selected', 'true');
      tabBtnHost.setAttribute('aria-selected', 'false');
      dlTabPaneClient.classList.remove('hidden');
      dlTabPaneHost.classList.add('hidden');
    });
  }

  // Copy 1-liner command
  if (btnCopyHostCmd) {
    btnCopyHostCmd.addEventListener('click', () => {
      const accountName = currentUser ? (currentUser.username || currentUser.email || 'User') : 'User';
      const userId = currentUser ? (currentUser.id || currentUser.userId || '') : '';
      const relayWs = defaultWsUrl || window.location.origin.replace(/^http/, 'ws');
      const setupBatUrl = `${window.location.origin}/api/download/setup.bat?account=${encodeURIComponent(accountName)}&userId=${encodeURIComponent(userId)}&relay=${encodeURIComponent(relayWs)}`;
      const cmd = btnCopyHostCmd.getAttribute('data-cmd') || `irm "${setupBatUrl}" | iex`;
      copyFeedback(btnCopyHostCmd, cmd, 'Đã sao chép lệnh cài đặt Host Agent!');
    });
  }

  // PWA install click
  if (btnPwaInstallRelay) {
    btnPwaInstallRelay.addEventListener('click', async () => {
      if (relayPwaPrompt) {
        relayPwaPrompt.prompt();
        const choice = await relayPwaPrompt.userChoice;
        if (choice.outcome === 'accepted') {
          relayPwaPrompt = null;
        }
      } else {
        await showAlertModal({
          title: 'Cài đặt Web App (PWA)',
          message: 'Để cài đặt Meikova Relay làm Web App (PWA):\n\n• Trên Chrome/Edge (Desktop): Nhấn biểu tượng Cài đặt (+) trên thanh địa chỉ URL.\n• Trên iPhone/Safari: Bấm nút Chia sẻ (Share) -> chọn "Thêm vào MH chính" (Add to Home Screen).\n• Trên Android: Bấm menu 3 chấm -> chọn "Cài đặt ứng dụng".',
          okText: t('dialog.btn_ok') || 'Đã hiểu'
        });
      }
    });
  }

  // Initial sync of download modal state with current host/domain
  try { updateRelayModalData(); } catch (_) {}


  // --- CLOUDFLARE QUICK TUNNEL CONTROLLER ---
  function initTunnelController() {
    const btnNavTunnel = document.getElementById('btnNavTunnel');
    const navTunnelDot = document.getElementById('navTunnelDot');
    const modalTunnel = document.getElementById('modalTunnel');
    const btnCloseTunnelModal = document.getElementById('btnCloseTunnelModal');
    const btnToggleTunnel = document.getElementById('btnToggleTunnel');
    const btnToggleTunnelText = document.getElementById('btnToggleTunnelText');
    const tunnelStatusText = document.getElementById('tunnelStatusText');
    const tunnelStatusDetail = document.getElementById('tunnelStatusDetail');
    const tunnelStatusBadgeDot = document.getElementById('tunnelStatusBadgeDot');
    const tunnelActiveBox = document.getElementById('tunnelActiveBox');
    const tunnelUrlInput = document.getElementById('tunnelUrlInput');
    const btnCopyTunnelUrl = document.getElementById('btnCopyTunnelUrl');
    const tunnelQrImg = document.getElementById('tunnelQrImg');
    const tunnelNotInstalledBox = document.getElementById('tunnelNotInstalledBox');
    const tunnelInstallCmd = document.getElementById('tunnelInstallCmd');
    const btnCopyTunnelInstallCmd = document.getElementById('btnCopyTunnelInstallCmd');

    if (!btnNavTunnel || !modalTunnel) return;

    let isOperating = false;

    let lastTunnelState = null;
    const ti = (key, fallback) => (typeof t === 'function' ? (t(key) || fallback) : fallback);

    function renderTunnelStatus(st) {
      if (!st) return;
      lastTunnelState = st;
      if (st.running && st.url) {
        btnNavTunnel.classList.add('is-active');
        if (navTunnelDot) navTunnelDot.className = 'status-dot tunnel-dot tunnel-dot--running';
        if (tunnelStatusBadgeDot) tunnelStatusBadgeDot.className = 'status-dot tunnel-dot tunnel-dot--running';
        if (tunnelStatusText) tunnelStatusText.textContent = ti('tunnel.status_running', 'Đang chạy');
        if (tunnelStatusDetail) tunnelStatusDetail.textContent = '';
        if (btnToggleTunnelText) btnToggleTunnelText.textContent = ti('tunnel.action_stop', 'Tắt');
        if (btnToggleTunnel) {
          btnToggleTunnel.classList.add('is-running');
          btnToggleTunnel.disabled = false;
        }
        if (tunnelActiveBox) tunnelActiveBox.classList.remove('hidden');
        if (tunnelUrlInput) tunnelUrlInput.value = st.url;
        if (tunnelQrImg) tunnelQrImg.src = '/api/qr?data=' + encodeURIComponent(st.url);
        if (tunnelNotInstalledBox) tunnelNotInstalledBox.classList.add('hidden');
      } else if (st.status === 'starting') {
        if (navTunnelDot) navTunnelDot.className = 'status-dot tunnel-dot tunnel-dot--starting';
        if (tunnelStatusBadgeDot) tunnelStatusBadgeDot.className = 'status-dot tunnel-dot tunnel-dot--starting';
        if (tunnelStatusText) tunnelStatusText.textContent = ti('tunnel.status_starting', 'Đang kết nối...');
        if (tunnelStatusDetail) tunnelStatusDetail.textContent = '';
        if (btnToggleTunnelText) btnToggleTunnelText.textContent = ti('tunnel.action_connecting', 'Đang bật...');
        if (btnToggleTunnel) btnToggleTunnel.disabled = true;
      } else {
        btnNavTunnel.classList.remove('is-active');
        if (navTunnelDot) navTunnelDot.className = 'status-dot tunnel-dot tunnel-dot--idle';
        if (tunnelStatusBadgeDot) {
          tunnelStatusBadgeDot.className = st.status === 'failed' ? 'status-dot tunnel-dot tunnel-dot--failed' : 'status-dot tunnel-dot tunnel-dot--idle';
        }
        if (tunnelStatusText) tunnelStatusText.textContent = st.status === 'failed' ? ti('tunnel.status_failed', 'Lỗi') : ti('tunnel.status_idle', 'Đang tắt');
        if (tunnelStatusDetail) tunnelStatusDetail.textContent = st.error || '';
        if (btnToggleTunnelText) btnToggleTunnelText.textContent = ti('tunnel.action_start', 'Bật');
        if (btnToggleTunnel) {
          btnToggleTunnel.classList.remove('is-running');
          btnToggleTunnel.disabled = false;
        }
        if (tunnelActiveBox) tunnelActiveBox.classList.add('hidden');

        if (!st.installed && tunnelNotInstalledBox) {
          tunnelNotInstalledBox.classList.remove('hidden');
          if (tunnelInstallCmd && st.installCommand) tunnelInstallCmd.textContent = st.installCommand;
        } else if (tunnelNotInstalledBox) {
          tunnelNotInstalledBox.classList.add('hidden');
        }
      }
    }

    async function fetchTunnelStatus() {
      try {
        const res = await fetch('/api/tunnel/status');
        if (res.ok) {
          const st = await res.json();
          renderTunnelStatus(st);
        }
      } catch (_) {}
    }

    async function toggleTunnel() {
      if (isOperating) return;
      isOperating = true;
      if (btnToggleTunnel) btnToggleTunnel.disabled = true;
      if (btnToggleTunnelText) btnToggleTunnelText.textContent = ti('tunnel.action_processing', 'Đang xử lý...');

      try {
        const res = await fetch('/api/tunnel/toggle', { method: 'POST' });
        const data = await res.json();
        if (res.ok && data.ok) {
          renderTunnelStatus(data);
          if (data.running) {
            showToast(t('toast.tunnel_started'), 'success');
          } else {
            showToast(t('toast.tunnel_stopped'), 'info');
          }
          try { updateRelayModalData(); } catch (_) {}
        } else {
          showToast(data.error || 'Thao tác Tunnel thất bại', 'error');
          fetchTunnelStatus();
        }
      } catch (err) {
        showToast(t('toast.tunnel_net_error', { error: err.message }), 'error');
        fetchTunnelStatus();
      } finally {
        isOperating = false;
        if (btnToggleTunnel) btnToggleTunnel.disabled = false;
      }
    }

    btnNavTunnel.addEventListener('click', () => {
      fetchTunnelStatus();
      modalTunnel.classList.remove('hidden');
    });

    if (btnCloseTunnelModal) {
      btnCloseTunnelModal.addEventListener('click', () => {
        modalTunnel.classList.add('hidden');
      });
    }

    modalTunnel.addEventListener('click', (e) => {
      if (e.target === modalTunnel) {
        modalTunnel.classList.add('hidden');
      }
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !modalTunnel.classList.contains('hidden')) {
        modalTunnel.classList.add('hidden');
      }
    });

    if (btnToggleTunnel) {
      btnToggleTunnel.addEventListener('click', toggleTunnel);
    }

    if (btnCopyTunnelUrl && tunnelUrlInput) {
      btnCopyTunnelUrl.addEventListener('click', async () => {
        if (!tunnelUrlInput.value) return;
        try {
          await navigator.clipboard.writeText(tunnelUrlInput.value);
          showToast(t('toast.tunnel_copied'), 'success');
        } catch (_) {
          tunnelUrlInput.select();
          document.execCommand('copy');
          showToast(t('toast.link_copied'), 'success');
        }
      });
    }

    if (btnCopyTunnelInstallCmd && tunnelInstallCmd) {
      btnCopyTunnelInstallCmd.addEventListener('click', async () => {
        try {
          await navigator.clipboard.writeText(tunnelInstallCmd.textContent.trim());
          showToast(t('toast.tunnel_cmd_copied'), 'success');
        } catch (_) {}
      });
    }

    window.onTunnelUpdate = (st) => {
      renderTunnelStatus(st);
      try { updateRelayModalData(); } catch (_) {}
    };

    window.addEventListener('meikova-lang-changed', () => {
      if (lastTunnelState) renderTunnelStatus(lastTunnelState);
    });

    // Initial background check
    fetchTunnelStatus();
  }

  initTunnelController();
  // Start app
  initApp();

  // --- MULTI-SESSION TABS & POPOUT ENGINE (Vấn đề 3) ---
  let isSessionTabsBarOpen = false;

  function updateRemoteSessionTabs() {
    const bar = document.getElementById('remoteSessionTabsBar');
    const list = document.getElementById('remoteSessionTabsList');
    if (!bar || !list) return;

    if (currentView !== 'remote' || !currentRoom || !isSessionTabsBarOpen) {
      bar.classList.add('hidden');
      return;
    }

    bar.classList.remove('hidden');

    const devices = (currentDeviceList && currentDeviceList.length > 0) ? currentDeviceList : [];
    let devItems = [...devices];
    const exists = devItems.some(d => d.room_id === currentRoom);
    if (!exists) {
      devItems.unshift({
        room_id: currentRoom,
        device_name: currentRoom,
        is_online: 1,
        pin: currentPin || ''
      });
    }

    list.innerHTML = devItems.map(d => {
      const isActive = d.room_id === currentRoom;
      const isOnline = d.is_online === 1;
      return `
        <div class="session-tab-pill ${isActive ? 'active' : ''}" data-room="${escapeHtml(d.room_id)}" data-pin="${escapeHtml(d.pin || '')}">
          <span class="session-tab-dot ${isOnline ? 'online' : 'offline'}"></span>
          <span class="session-tab-name mono-font">${escapeHtml(d.device_name || d.room_id)}</span>
          <button type="button" class="session-tab-popout" title="Mở trong tab mới / cửa sổ riêng" data-room="${escapeHtml(d.room_id)}" data-pin="${escapeHtml(d.pin || '')}">
            <svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
          </button>
        </div>
      `;
    }).join('');

    list.querySelectorAll('.session-tab-pill').forEach(pill => {
      pill.addEventListener('click', (e) => {
        if (e.target.closest('.session-tab-popout')) return;
        const room = pill.dataset.room;
        const pin = pill.dataset.pin || '';
        if (room && room !== currentRoom) {
          startRemoteSession(defaultWsUrl, room, pin);
        }
      });
    });

    list.querySelectorAll('.session-tab-popout').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const room = btn.dataset.room;
        const pin = btn.dataset.pin || '';
        const popUrl = `/?room=${encodeURIComponent(room)}${pin ? `&pin=${encodeURIComponent(pin)}` : ''}&direct=1`;
        window.open(popUrl, '_blank', 'noopener,noreferrer');
      });
    });
  }

  // Bind Session Tab Actions & Popout Button
  document.getElementById('btnToggleSessionTabs')?.addEventListener('click', () => {
    isSessionTabsBarOpen = !isSessionTabsBarOpen;
    updateRemoteSessionTabs();
  });

  document.getElementById('btnCloseSessionTabsBar')?.addEventListener('click', () => {
    isSessionTabsBarOpen = false;
    updateRemoteSessionTabs();
  });

  document.getElementById('btnRemoteNewSessionTab')?.addEventListener('click', () => {
    quickConnectModal?.classList.remove('hidden');
    landingRoomInput?.focus();
  });

  document.getElementById('btnPopoutSession')?.addEventListener('click', () => {
    if (!currentRoom) return;
    const popUrl = `/?room=${encodeURIComponent(currentRoom)}${currentPin ? `&pin=${encodeURIComponent(currentPin)}` : ''}&direct=1`;
    window.open(popUrl, '_blank', 'noopener,noreferrer');
  });

  document.getElementById('btnQCPopout')?.addEventListener('click', () => {
    const room = qcRoomId?.value.trim();
    const pin = qcPin?.value.trim() || '';
    if (!room) {
      showToast(t('toast.enter_room_id'), 'warning');
      return;
    }
    quickConnectModal.classList.add('hidden');
    const popUrl = `/?room=${encodeURIComponent(room)}${pin ? `&pin=${encodeURIComponent(pin)}` : ''}&direct=1`;
    window.open(popUrl, '_blank', 'noopener,noreferrer');
  });

  window.addEventListener('hashchange', () => {
    const route = getRouteStateFromUrl();
    if (route.room && route.room !== currentRoom) {
      currentRoom = route.room;
      currentPin = route.pin || sessionStorage.getItem('meikova_relay_pin_' + route.room) || '';
      switchView('remote', false);
      startRemoteSession(defaultWsUrl, route.room, currentPin);
    }
  });

})();


// --- Desktop Frameless Custom Titlebar & Shell Isolation (Law 5) ---
function initDesktopTitlebar() {
  const isDesktopEnv = () => {
    try {
      const params = new URLSearchParams(window.location.search);
      return (
        typeof window.pywebview !== 'undefined' ||
        params.get('platform') === 'desktop' ||
        window.isDesktopShell === true
      );
    } catch (_) {
      return false;
    }
  };

  const setupTitlebar = () => {
    if (!isDesktopEnv()) return false;
    document.body.classList.add('is-desktop-shell');
    const titlebar = document.getElementById('desktop-titlebar');
    if (titlebar) {
      titlebar.style.display = 'flex';
    }

    const btnMin = document.getElementById('dt-btn-min');
    const btnMax = document.getElementById('dt-btn-max');
    const btnClose = document.getElementById('dt-btn-close');

    if (btnMin) {
      btnMin.onclick = (e) => {
        e.stopPropagation();
        if (window.pywebview && window.pywebview.api) {
          if (typeof window.pywebview.api.minimize_window === 'function') {
            window.pywebview.api.minimize_window();
          } else if (typeof window.pywebview.api.minimize === 'function') {
            window.pywebview.api.minimize();
          }
        }
      };
    }

    if (btnMax) {
      btnMax.onclick = async (e) => {
        e.stopPropagation();
        try {
          if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.toggle_maximize === 'function') {
            const isMax = await window.pywebview.api.toggle_maximize();
            updateMaxIcon(isMax);
          }
        } catch (_) {}
      };
    }

    if (btnClose) {
      btnClose.onclick = (e) => {
        e.stopPropagation();
        if (window.pywebview && window.pywebview.api) {
          if (typeof window.pywebview.api.close_window === 'function') {
            window.pywebview.api.close_window();
          } else if (typeof window.pywebview.api.minimize_to_tray === 'function') {
            window.pywebview.api.minimize_to_tray();
          }
        }
      };
    }

    if (titlebar) {
      titlebar.ondblclick = (e) => {
        if (e.target.closest('.desktop-titlebar__controls')) return;
        btnMax && btnMax.click();
      };
      titlebar.onmousedown = (e) => {
        if (e.target.closest('.desktop-titlebar__controls')) return;
        if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.start_drag === 'function') {
          window.pywebview.api.start_drag();
        }
      };
    }
    return true;
  };

  function updateMaxIcon(isMax) {
    const icon = document.getElementById('dt-max-icon');
    if (!icon) return;
    if (isMax) {
      icon.innerHTML = '<path d="M3 1.5h6v6H3z M1.5 3.5h1.5v5.5h5.5v1.5H1.5z" fill="none" stroke="currentColor" stroke-width="1.1"/>';
    } else {
      icon.innerHTML = '<rect x="1.5" y="1.5" width="8" height="8" rx="0.8"/>';
    }
  }

  if (!setupTitlebar()) {
    window.addEventListener('pywebviewready', setupTitlebar);
    setTimeout(setupTitlebar, 300);
    setTimeout(setupTitlebar, 1000);
  }
}

if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDesktopTitlebar);
  } else {
    initDesktopTitlebar();
  }
}

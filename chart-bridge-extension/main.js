(() => {
  'use strict';
  if (window.__JEET_DELTA_BRIDGE_MAIN__) return;
  window.__JEET_DELTA_BRIDGE_MAIN__ = true;

  const DEFAULT_BRIDGE = 'https://jeet-delta-mcp.onrender.com/chart-bridge';
  let socket = null;
  let reconnectTimer = null;
  let bridgeUrl = DEFAULT_BRIDGE;
  let bridgeToken = '';
  let connected = false;
  let configReady = false;

  function postMessage(type, payload = {}) {
    window.postMessage({ source: 'JEET_DELTA_BRIDGE_MAIN', type, ...payload }, '*');
  }

  function requestConfig() {
    postMessage('request_config');
  }

  function connect() {
    if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) return;
    const base = bridgeUrl.replace(/\/$/, '');
    const wsUrl = base.replace(/^http/, 'ws') + '/ws' + (bridgeToken ? `?token=${encodeURIComponent(bridgeToken)}` : '');
    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      connected = true;
      postMessage('status', { connected, config_ready: configReady });
    };

    socket.onmessage = (event) => {
      let msg;
      try { msg = JSON.parse(event.data); } catch (_) { return; }
      if (msg.action !== 'draw_horizontal_line') return;
      // Native chart access is deliberately isolated in MAIN-world page-bridge.js.
      // The content script receives the command and forwards it into that bridge.
      postMessage('draw_horizontal_line', { command: msg });
    };

    socket.onclose = () => {
      connected = false;
      postMessage('status', { connected, config_ready: configReady });
      clearTimeout(reconnectTimer);
      reconnectTimer = setTimeout(connect, 2000);
    };

    socket.onerror = () => {
      connected = false;
      postMessage('status', { connected, config_ready: configReady });
    };
  }

  window.addEventListener('message', (event) => {
    if (event.source !== window || !event.data) return;
    const msg = event.data;

    if (msg.source === 'JEET_DELTA_BRIDGE_EXTENSION' && msg.type === 'config') {
      bridgeUrl = String(msg.bridgeUrl || DEFAULT_BRIDGE).trim().replace(/\/$/, '');
      bridgeToken = String(msg.bridgeToken || '');
      configReady = true;
      connect();
      return;
    }

    if (msg.source === 'JEET_DELTA_BRIDGE_CONTENT' && msg.type === 'request_config') {
      requestConfig();
      return;
    }

    if (msg.source === 'JEET_DELTA_BRIDGE_CONTENT' && msg.type === 'draw_result') {
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({
          action: 'draw_result',
          ok: !!msg.ok,
          request_id: msg.request_id,
          result: msg.result,
          error: msg.error,
        }));
      }
      return;
    }
  });

  connect();
})();

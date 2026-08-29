(() => {
  'use strict';
  if (window.__JEET_DELTA_BRIDGE_MAIN__) return;
  window.__JEET_DELTA_BRIDGE_MAIN__ = true;

  const DEFAULT_BRIDGE = 'https://jeet-delta-mcp.onrender.com/chart-bridge';
  const COMMAND_EVENT = 'JEET_DELTA_NATIVE_CHART_COMMAND';
  const RESULT_EVENT = 'JEET_DELTA_NATIVE_CHART_RESULT';
  let socket = null;
  let reconnectTimer = null;
  let bridgeUrl = DEFAULT_BRIDGE;
  let bridgeToken = '';
  let connected = false;
  let configReady = false;

  function post(type, payload = {}) {
    window.postMessage({ source: 'JEET_DELTA_BRIDGE_MAIN', type, ...payload }, '*');
  }

  function connect() {
    if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) return;
    const base = bridgeUrl.replace(/\/$/, '');
    const wsUrl = base.replace(/^http/, 'ws') + '/ws' + (bridgeToken ? `?token=${encodeURIComponent(bridgeToken)}` : '');
    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      connected = true;
      post('status', { connected, config_ready: configReady });
    };

    socket.onmessage = (event) => {
      let msg;
      try { msg = JSON.parse(event.data); } catch (_) { return; }
      if (msg.action !== 'draw_horizontal_line') return;
      window.postMessage({ source: COMMAND_EVENT, type: 'draw_horizontal_line', ...msg }, '*');
    };

    socket.onclose = () => {
      connected = false;
      post('status', { connected, config_ready: configReady });
      clearTimeout(reconnectTimer);
      reconnectTimer = setTimeout(connect, 2000);
    };

    socket.onerror = () => {
      connected = false;
      post('status', { connected, config_ready: configReady });
    };
  }

  function sendResult(msg) {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({
        action: 'draw_result',
        ok: !!msg.ok,
        request_id: msg.request_id,
        result: msg.result,
        error: msg.error,
      }));
    }
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
      post('request_config');
      return;
    }

    if (msg.source === RESULT_EVENT && msg.type === 'draw_result') {
      sendResult(msg);
    }
  });

  connect();
})();

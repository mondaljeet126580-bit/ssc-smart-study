(() => {
  'use strict';
  if (window.__JEET_DELTA_BRIDGE_MAIN__) return;
  window.__JEET_DELTA_BRIDGE_MAIN__ = true;

  const DEFAULT_BRIDGE = 'https://jeet-delta-mcp.onrender.com/chart-bridge';
  const COMMAND_EVENT = 'JEET_DELTA_NATIVE_DRAW_COMMAND';
  const RESULT_EVENT = 'JEET_DELTA_NATIVE_DRAW_RESULT';
  let socket = null;
  let reconnectTimer = null;
  let bridgeUrl = DEFAULT_BRIDGE;
  let bridgeToken = '';

  function post(type, payload = {}) {
    window.postMessage({ source: 'JEET_DELTA_BRIDGE_MAIN', type, ...payload }, '*');
  }

  function connect() {
    if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) return;
    const base = bridgeUrl.replace(/\/$/, '');
    const wsUrl = base.replace(/^http/, 'ws') + '/ws' + (bridgeToken ? `?token=${encodeURIComponent(bridgeToken)}` : '');
    socket = new WebSocket(wsUrl);
    socket.onopen = () => post('status', { connected: true });
    socket.onmessage = (event) => {
      let msg;
      try { msg = JSON.parse(event.data); } catch (_) { return; }
      if (msg.action === 'draw_horizontal_line') {
        window.postMessage({ source: COMMAND_EVENT, type: 'draw_horizontal_line', ...msg }, '*');
      }
    };
    socket.onclose = () => {
      post('status', { connected: false });
      clearTimeout(reconnectTimer);
      reconnectTimer = setTimeout(connect, 2000);
    };
    socket.onerror = () => post('status', { connected: false });
  }

  function sendResult(msg) {
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    socket.send(JSON.stringify({ action: 'draw_result', ok: !!msg.ok, request_id: msg.request_id, result: msg.result, error: msg.error }));
  }

  window.addEventListener('message', (event) => {
    if (event.source !== window || !event.data) return;
    const msg = event.data;
    if (msg.source === 'JEET_DELTA_BRIDGE_EXTENSION' && msg.type === 'config') {
      bridgeUrl = String(msg.bridgeUrl || DEFAULT_BRIDGE).trim().replace(/\/$/, '');
      bridgeToken = String(msg.bridgeToken || '');
      connect();
      return;
    }
    if (msg.source === 'JEET_DELTA_BRIDGE_CONTENT' && msg.type === 'request_config') {
      post('request_config');
      return;
    }
    if (msg.source === RESULT_EVENT && msg.type === 'draw_result') sendResult(msg);
  });

  connect();
})();

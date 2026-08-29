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

  function getCandidates() {
    const values = [];
    const add = (v) => { if (v && !values.includes(v)) values.push(v); };
    try {
      add(window.tvWidget);
      add(window.TradingView?.widget);
      add(window.chartWidget);
      add(window.widget);
      add(window.tv?.widget);
    } catch (_) {}
    return values;
  }

  function findChartApi() {
    for (const widget of getCandidates()) {
      try {
        if (typeof widget.activeChart === 'function') {
          const chart = widget.activeChart();
          if (chart && typeof chart.createShape === 'function') return chart;
        }
        if (typeof widget.chart === 'function') {
          const chart = widget.chart();
          if (chart && typeof chart.createShape === 'function') return chart;
        }
      } catch (_) {}
    }
    return null;
  }

  async function drawHorizontalLine(msg) {
    const symbol = String(msg.symbol || '').trim().toUpperCase();
    const price = Number(msg.price);
    if (!symbol || !Number.isFinite(price) || price <= 0) throw new Error('Invalid symbol or price');

    const chart = findChartApi();
    if (!chart) throw new Error('Native chart createShape API is unavailable on this Delta chart');

    const shapeId = await chart.createShape(
      { time: Math.floor(Date.now() / 1000), price },
      {
        shape: 'horizontal_line',
        text: msg.label || `Horizontal ${price}`,
        disableSave: false,
        disableUndo: false,
      }
    );

    return { native: true, symbol, price, shape_id: shapeId ?? null };
  }

  function postStatus() {
    window.postMessage({
      source: 'JEET_DELTA_BRIDGE_MAIN',
      type: 'status',
      connected,
      native_chart_api: !!findChartApi(),
    }, '*');
  }

  function sendResult(payload) {
    if (socket && socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify(payload));
    window.postMessage({ source: 'JEET_DELTA_BRIDGE_MAIN', type: 'draw_result', ...payload }, '*');
  }

  function connect() {
    if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) return;
    const base = bridgeUrl.replace(/\/$/, '');
    const wsUrl = base.replace(/^http/, 'ws') + '/ws' + (bridgeToken ? `?token=${encodeURIComponent(bridgeToken)}` : '');
    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      connected = true;
      postStatus();
      // Ask the isolated content script to resend configuration in case MAIN loaded first.
      window.postMessage({ source: 'JEET_DELTA_BRIDGE_MAIN', type: 'request_config' }, '*');
    };

    socket.onmessage = async (event) => {
      let msg;
      try { msg = JSON.parse(event.data); } catch (_) { return; }
      if (msg.action !== 'draw_horizontal_line') return;
      try {
        const result = await drawHorizontalLine(msg);
        sendResult({ action: 'draw_result', ok: true, request_id: msg.request_id, result });
      } catch (error) {
        sendResult({ action: 'draw_result', ok: false, request_id: msg.request_id, error: String(error) });
      }
    };

    socket.onclose = () => {
      connected = false;
      postStatus();
      clearTimeout(reconnectTimer);
      reconnectTimer = setTimeout(connect, 2000);
    };
  }

  window.addEventListener('message', (event) => {
    if (event.source !== window || !event.data) return;
    const msg = event.data;
    if (msg.source === 'JEET_DELTA_BRIDGE_EXTENSION' && msg.type === 'config') {
      bridgeUrl = String(msg.bridgeUrl || DEFAULT_BRIDGE).trim().replace(/\/$/, '');
      bridgeToken = String(msg.bridgeToken || '');
      connect();
    }
  });

  connect();
  postStatus();
})();

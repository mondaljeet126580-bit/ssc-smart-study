(() => {
  if (window.__JEET_DELTA_CHART_BRIDGE__) return;
  window.__JEET_DELTA_CHART_BRIDGE__ = true;

  const DEFAULT_BRIDGE = 'https://jeet-delta-mcp.onrender.com/chart-bridge';
  let bridgeUrl = DEFAULT_BRIDGE;
  let socket = null;
  let reconnectTimer = null;

  const log = (...args) => console.debug('[Jeet Chart Bridge]', ...args);

  function findTradingViewApi() {
    const candidates = [
      window.tvWidget,
      window.TradingView?.widget,
      window.chartWidget,
      window.widget,
      window.tv?.widget,
    ].filter(Boolean);
    return candidates[0] || null;
  }

  async function drawHorizontalLine(msg) {
    const price = Number(msg.price);
    if (!Number.isFinite(price) || price <= 0) throw new Error('Invalid price');

    const widget = findTradingViewApi();
    if (!widget) {
      throw new Error('Native TradingView chart API was not exposed by this chart frame');
    }

    const chart = typeof widget.activeChart === 'function' ? widget.activeChart() : widget.chart?.();
    if (!chart || typeof chart.createShape !== 'function') {
      throw new Error('TradingView chart drawing API is unavailable');
    }

    const shape = await chart.createShape(
      { time: Math.floor(Date.now() / 1000), price },
      {
        shape: 'horizontal_line',
        text: msg.label || `Horizontal ${price}`,
        disableSave: false,
        disableUndo: false,
      }
    );

    return { shape, symbol: msg.symbol, price, native: true };
  }

  function connect() {
    if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) return;
    const base = bridgeUrl.replace(/\/$/, '');
    const token = localStorage.getItem('JEET_CHART_BRIDGE_TOKEN') || '';
    const wsUrl = base.replace(/^http/, 'ws') + '/ws' + (token ? `?token=${encodeURIComponent(token)}` : '');
    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      log('connected to', wsUrl);
      window.postMessage({ source: 'JEET_DELTA_BRIDGE', type: 'status', connected: true }, '*');
    };

    socket.onmessage = async (event) => {
      let msg;
      try { msg = JSON.parse(event.data); } catch { return; }
      if (msg.action !== 'draw_horizontal_line') return;
      try {
        const result = await drawHorizontalLine(msg);
        socket.send(JSON.stringify({ action: 'draw_result', ok: true, request_id: msg.request_id, result }));
      } catch (error) {
        socket.send(JSON.stringify({ action: 'draw_result', ok: false, request_id: msg.request_id, error: String(error) }));
      }
    };

    socket.onclose = () => {
      window.postMessage({ source: 'JEET_DELTA_BRIDGE', type: 'status', connected: false }, '*');
      clearTimeout(reconnectTimer);
      reconnectTimer = setTimeout(connect, 2000);
    };
  }

  chrome.storage.local.get(['bridgeUrl', 'bridgeToken'], (cfg) => {
    bridgeUrl = cfg.bridgeUrl || DEFAULT_BRIDGE;
    if (cfg.bridgeToken) localStorage.setItem('JEET_CHART_BRIDGE_TOKEN', cfg.bridgeToken);
    connect();
  });
})();

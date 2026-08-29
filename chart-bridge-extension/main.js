(() => {
  if (window.__JEET_DELTA_BRIDGE_MAIN__) return;
  window.__JEET_DELTA_BRIDGE_MAIN__ = true;

  const DEFAULT_BRIDGE = 'https://jeet-delta-mcp.onrender.com/chart-bridge';
  let socket = null;
  let reconnectTimer = null;
  let bridgeUrl = DEFAULT_BRIDGE;
  let bridgeToken = '';

  function findTradingViewApi() {
    return [window.tvWidget, window.TradingView?.widget, window.chartWidget, window.widget, window.tv?.widget].find(Boolean) || null;
  }

  async function drawHorizontalLine(msg) {
    const price = Number(msg.price);
    if (!Number.isFinite(price) || price <= 0) throw new Error('Invalid price');
    const widget = findTradingViewApi();
    if (!widget) throw new Error('Native TradingView widget is unavailable');
    const chart = typeof widget.activeChart === 'function' ? widget.activeChart() : typeof widget.chart === 'function' ? widget.chart() : null;
    if (!chart || typeof chart.createShape !== 'function') throw new Error('Native chart createShape API is unavailable');
    const shapeId = await chart.createShape(
      { time: Math.floor(Date.now() / 1000), price },
      { shape: 'horizontal_line', text: msg.label || `Horizontal ${price}`, disableSave: false, disableUndo: false }
    );
    return { native: true, symbol: msg.symbol, price, shape_id: shapeId };
  }

  function connect() {
    if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) return;
    const base = bridgeUrl.replace(/\/$/, '');
    const wsUrl = base.replace(/^http/, 'ws') + '/ws' + (bridgeToken ? `?token=${encodeURIComponent(bridgeToken)}` : '');
    socket = new WebSocket(wsUrl);
    socket.onopen = () => window.postMessage({ source: 'JEET_DELTA_BRIDGE_MAIN', type: 'status', connected: true }, '*');
    socket.onmessage = async (event) => {
      let msg; try { msg = JSON.parse(event.data); } catch { return; }
      if (msg.action !== 'draw_horizontal_line') return;
      try {
        const result = await drawHorizontalLine(msg);
        const payload = { action: 'draw_result', ok: true, request_id: msg.request_id, result };
        socket.send(JSON.stringify(payload));
        window.postMessage({ source: 'JEET_DELTA_BRIDGE_MAIN', type: 'draw_result', ...payload }, '*');
      } catch (error) {
        const payload = { action: 'draw_result', ok: false, request_id: msg.request_id, error: String(error) };
        socket.send(JSON.stringify(payload));
        window.postMessage({ source: 'JEET_DELTA_BRIDGE_MAIN', type: 'draw_result', ...payload }, '*');
      }
    };
    socket.onclose = () => {
      window.postMessage({ source: 'JEET_DELTA_BRIDGE_MAIN', type: 'status', connected: false }, '*');
      clearTimeout(reconnectTimer); reconnectTimer = setTimeout(connect, 2000);
    };
  }

  window.addEventListener('message', (event) => {
    if (event.source !== window || !event.data) return;
    const msg = event.data;
    if (msg.source === 'JEET_DELTA_BRIDGE_EXTENSION' && msg.type === 'config') {
      bridgeUrl = String(msg.bridgeUrl || DEFAULT_BRIDGE);
      bridgeToken = String(msg.bridgeToken || '');
      connect();
    }
    if (msg.source === 'JEET_DELTA_BRIDGE_CONTENT' && msg.type === 'draw_horizontal_line') {
      drawHorizontalLine(msg).then(result => {
        window.postMessage({ source: 'JEET_DELTA_BRIDGE_MAIN', type: 'draw_result', action: 'draw_result', ok: true, request_id: msg.request_id, result }, '*');
      }).catch(error => {
        window.postMessage({ source: 'JEET_DELTA_BRIDGE_MAIN', type: 'draw_result', action: 'draw_result', ok: false, request_id: msg.request_id, error: String(error) }, '*');
      });
    }
  });
})();

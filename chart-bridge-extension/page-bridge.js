(() => {
  if (window.__JEET_DELTA_NATIVE_PAGE_BRIDGE__) return;
  window.__JEET_DELTA_NATIVE_PAGE_BRIDGE__ = true;

  const BRIDGE_EVENT = 'JEET_DELTA_NATIVE_CHART_COMMAND';
  const RESULT_EVENT = 'JEET_DELTA_NATIVE_CHART_RESULT';

  function findWidget() {
    return [
      window.tvWidget,
      window.TradingView?.widget,
      window.chartWidget,
      window.widget,
      window.tv?.widget,
    ].find(Boolean) || null;
  }

  async function draw(msg) {
    const widget = findWidget();
    if (!widget) throw new Error('TradingView widget not found');

    const chart = typeof widget.activeChart === 'function'
      ? widget.activeChart()
      : typeof widget.chart === 'function'
        ? widget.chart()
        : null;

    if (!chart || typeof chart.createShape !== 'function') {
      throw new Error('TradingView chart createShape API is unavailable');
    }

    const symbol = String(msg.symbol || '').toUpperCase();
    const price = Number(msg.price);
    if (!symbol || !Number.isFinite(price) || price <= 0) {
      throw new Error('Invalid symbol or price');
    }

    const shapeId = await chart.createShape(
      { time: Math.floor(Date.now() / 1000), price },
      {
        shape: 'horizontal_line',
        text: msg.label || `Horizontal ${price}`,
        disableSave: false,
        disableUndo: false,
      }
    );

    return { native: true, symbol, price, shape_id: shapeId };
  }

  window.addEventListener('message', async (event) => {
    const msg = event.data;
    if (!msg || msg.source !== 'JEET_DELTA_BRIDGE_CONTENT' || msg.type !== 'draw_horizontal_line') return;
    const requestId = msg.request_id || '';
    try {
      const result = await draw(msg);
      window.postMessage({ source: BRIDGE_EVENT, type: RESULT_EVENT, ok: true, request_id: requestId, result }, '*');
    } catch (error) {
      window.postMessage({ source: BRIDGE_EVENT, type: RESULT_EVENT, ok: false, request_id: requestId, error: String(error) }, '*');
    }
  });
})();

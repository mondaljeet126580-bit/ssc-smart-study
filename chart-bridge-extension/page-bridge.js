(() => {
  'use strict';
  if (window.__JEET_DELTA_NATIVE_PAGE_BRIDGE__) return;
  window.__JEET_DELTA_NATIVE_PAGE_BRIDGE__ = true;

  const EVENT_IN = 'JEET_DELTA_NATIVE_DRAW_COMMAND';
  const EVENT_OUT = 'JEET_DELTA_NATIVE_DRAW_RESULT';

  function findWidget() {
    const candidates = [window.tvWidget, window.TradingView?.widget, window.chartWidget, window.widget, window.tv?.widget];
    for (const widget of candidates) if (widget) return widget;
    return null;
  }

  function findChart() {
    const widget = findWidget();
    if (!widget) return null;
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
    return null;
  }

  async function execute(msg) {
    const symbol = String(msg.symbol || '').trim().toUpperCase();
    const resolution = String(msg.resolution || '').trim();
    const price = Number(msg.price);
    if (!symbol || !resolution || !Number.isFinite(price) || price <= 0) throw new Error('Invalid symbol, resolution, or price');

    const chart = findChart();
    if (!chart) throw new Error('Native chart drawing API is unavailable on the active Delta chart');

    const shapeId = await chart.createShape(
      { time: Math.floor(Date.now() / 1000), price },
      {
        shape: 'horizontal_line',
        text: msg.label || `Horizontal ${price}`,
        disableSave: false,
        disableUndo: false,
      }
    );

    return { native: true, symbol, resolution, price, shape_id: shapeId ?? null };
  }

  window.addEventListener('message', async (event) => {
    if (event.source !== window || !event.data || event.data.source !== EVENT_IN) return;
    const msg = event.data;
    const requestId = String(msg.request_id || '');
    try {
      const result = await execute(msg);
      window.postMessage({ source: EVENT_OUT, ok: true, request_id: requestId, result }, '*');
    } catch (error) {
      window.postMessage({ source: EVENT_OUT, ok: false, request_id: requestId, error: String(error) }, '*');
    }
  });

  window.dispatchEvent(new CustomEvent('JEET_DELTA_NATIVE_BRIDGE_READY'));
})();

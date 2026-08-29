(() => {
  'use strict';
  if (window.__JEET_DELTA_NATIVE_PAGE_BRIDGE__) return;
  window.__JEET_DELTA_NATIVE_PAGE_BRIDGE__ = true;

  const COMMAND_EVENT = 'JEET_DELTA_NATIVE_CHART_COMMAND';
  const RESULT_EVENT = 'JEET_DELTA_NATIVE_CHART_RESULT';

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

  async function draw(msg) {
    const symbol = String(msg.symbol || '').trim().toUpperCase();
    const price = Number(msg.price);
    if (!symbol || !Number.isFinite(price) || price <= 0) throw new Error('Invalid symbol or price');

    const chart = findChart();
    if (!chart) throw new Error('Native chart drawing API is unavailable on this Delta chart');

    const shapeId = await chart.createShape(
      { time: Math.floor(Date.now() / 1000), price },
      { shape: 'horizontal_line', text: msg.label || `Horizontal ${price}`, disableSave: false, disableUndo: false }
    );

    return { native: true, symbol, price, shape_id: shapeId ?? null };
  }

  window.addEventListener('message', async (event) => {
    if (event.source !== window || !event.data) return;
    const msg = event.data;
    if (msg.source !== COMMAND_EVENT || msg.type !== 'draw_horizontal_line') return;

    const requestId = String(msg.request_id || '');
    try {
      const result = await draw(msg);
      window.postMessage({ source: RESULT_EVENT, type: 'draw_result', ok: true, request_id: requestId, result }, '*');
    } catch (error) {
      window.postMessage({ source: RESULT_EVENT, type: 'draw_result', ok: false, request_id: requestId, error: String(error) }, '*');
    }
  });

  window.dispatchEvent(new CustomEvent('JEET_DELTA_BRIDGE_READY'));
})();

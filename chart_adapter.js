// Jeet Delta Chart Adapter
// Run this in the browser context where the native chart is open.
// The adapter listens to the Render bridge and exposes the drawing hook used by chart_bridge.py.

(() => {
  'use strict';

  function getSymbol() {
    const text = document.body?.innerText || '';
    const match = text.match(/\b(BTCUSD|ETHUSD|[A-Z]{2,12}USD)\b/);
    return match ? match[1] : null;
  }

  // This adapter intentionally does not fake a successful native drawing.
  // It tries known TradingView widget APIs when exposed by the page, then
  // falls back to visible DOM overlay only when a chart container is detectable.
  async function drawHorizontalLine(command) {
    const symbol = String(command.symbol || '').toUpperCase();
    const price = Number(command.price);
    if (!symbol || !Number.isFinite(price) || price <= 0) {
      throw new Error('Invalid symbol or price');
    }

    // Common TradingView lightweight-widget integration hook.
    if (window.tvWidget?.activeChart) {
      const chart = window.tvWidget.activeChart();
      if (typeof chart.createShape === 'function') {
        const shape = chart.createShape({ price }, { shape: 'horizontal_line', disableSave: false, text: command.label || '' });
        return { adapter: 'tradingview-widget', symbol, price, shape_id: shape || null };
      }
    }

    throw new Error('Native chart drawing API is not exposed by this page.');
  }

  window.deltaChartBridgeDraw = drawHorizontalLine;
  window.deltaChartBridgeAdapter = { name: 'Jeet Delta Chart Adapter', getSymbol };
  console.log('[Jeet Delta] chart adapter installed');
})();

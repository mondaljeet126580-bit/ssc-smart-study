(() => {
  'use strict';
  if (window.__JEET_DELTA_BRIDGE_CONTENT__) return;
  window.__JEET_DELTA_BRIDGE_CONTENT__ = true;

  const DEFAULT_BRIDGE = 'https://jeet-delta-mcp.onrender.com/chart-bridge';

  function sendConfig() {
    chrome.storage.local.get(['bridgeUrl', 'bridgeToken'], (cfg) => {
      window.postMessage({
        source: 'JEET_DELTA_BRIDGE_EXTENSION',
        type: 'config',
        bridgeUrl: String(cfg.bridgeUrl || DEFAULT_BRIDGE),
        bridgeToken: String(cfg.bridgeToken || '')
      }, '*');
    });
  }

  window.addEventListener('message', (event) => {
    if (event.source !== window || !event.data) return;
    if (event.data.source !== 'JEET_DELTA_BRIDGE_MAIN' || event.data.type !== 'request_config') return;
    sendConfig();
  });

  sendConfig();
  setTimeout(sendConfig, 500);
  setTimeout(sendConfig, 2000);
})();

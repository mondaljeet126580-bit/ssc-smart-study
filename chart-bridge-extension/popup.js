const url = document.getElementById('url');
const token = document.getElementById('token');
const status = document.getElementById('status');
chrome.storage.local.get(['bridgeUrl','bridgeToken'], (v) => { if (v.bridgeUrl) url.value=v.bridgeUrl; if (v.bridgeToken) token.value=v.bridgeToken; });
document.getElementById('save').onclick = () => chrome.storage.local.set({bridgeUrl:url.value.trim(), bridgeToken:token.value.trim()}, () => { status.textContent=' Saved'; setTimeout(()=>status.textContent='',1500); });

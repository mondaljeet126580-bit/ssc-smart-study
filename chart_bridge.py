from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI(title="Jeet Delta Chart Bridge", version="1.0.0")
ACCESS_TOKEN = os.getenv("CHART_BRIDGE_TOKEN", "").strip()
_clients: set[WebSocket] = set()

HTML = """<!doctype html><html><body style='font-family:system-ui;background:#111;color:#eee;padding:20px'>
<h2>Jeet Delta Chart Bridge</h2><p id='s'>Connecting…</p>
<script>
const token=new URLSearchParams(location.search).get('token')||'';
let ws;
function connect(){
 const p=location.protocol==='https:'?'wss':'ws';
 ws=new WebSocket(`${p}://${location.host}/ws?token=${encodeURIComponent(token)}`);
 ws.onopen=()=>document.getElementById('s').textContent='Bridge connected';
 ws.onclose=()=>setTimeout(connect,1000);
 ws.onmessage=e=>{
  const m=JSON.parse(e.data);
  if(m.action==='draw_horizontal_line' && typeof window.deltaChartBridgeDraw==='function') window.deltaChartBridgeDraw(m);
 };
}
connect();
</script></body></html>"""

def _auth(request: Request) -> None:
    if ACCESS_TOKEN and request.headers.get("authorization", "") != f"Bearer {ACCESS_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"ok": True, "service": "Jeet Delta Chart Bridge", "token_configured": bool(ACCESS_TOKEN), "connected_clients": len(_clients)})

@app.get("/bridge", response_class=HTMLResponse)
async def bridge(request: Request) -> HTMLResponse:
    _auth(request)
    return HTMLResponse(HTML)

@app.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token", "")
    if ACCESS_TOKEN and token != ACCESS_TOKEN:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    _clients.add(websocket)
    try:
        while True:
            msg: dict[str, Any] = await websocket.receive_json()
            if msg.get("action") != "draw_horizontal_line":
                continue
            symbol = str(msg.get("symbol", "")).strip().upper()
            try:
                price = float(msg.get("price"))
            except (TypeError, ValueError):
                await websocket.send_json({"ok": False, "error": "price must be numeric"})
                continue
            if not symbol or price <= 0:
                await websocket.send_json({"ok": False, "error": "symbol and positive price are required"})
                continue
            command = {"action": "draw_horizontal_line", "symbol": symbol, "price": price, "label": str(msg.get("label") or "Horizontal level")}
            for client in list(_clients):
                try:
                    await client.send_json(command)
                except Exception:
                    _clients.discard(client)
            await websocket.send_json({"ok": True, "queued": True, "command": command})
    finally:
        _clients.discard(websocket)

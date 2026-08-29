from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI(title="Jeet Delta Chart Bridge", version="1.0.0")
ACCESS_TOKEN = os.getenv("CHART_BRIDGE_TOKEN", "").strip()
_clients: set[WebSocket] = set()

HTML = """<!doctype html><html><body style='font-family:system-ui;background:#111;color:#eee;padding:20px'>
<h2>Jeet Delta Chart Bridge</h2><p id='s'>Bridge ready. Keep this tab open.</p>
<script>
const token=new URLSearchParams(location.search).get('token')||'';
let ws;
function connect(){
 const p=location.protocol==='https:'?'wss':'ws';
 ws=new WebSocket(`${p}://${location.host}/ws?token=${encodeURIComponent(token)}`);
 ws.onopen=()=>document.getElementById('s').textContent='Bridge connected and listening';
 ws.onclose=()=>{document.getElementById('s').textContent='Disconnected; retrying…';setTimeout(connect,1000)};
 ws.onmessage=e=>{
  const m=JSON.parse(e.data);
  if(m.action==='draw_horizontal_line'){
   if(typeof window.deltaChartBridgeDraw==='function'){
    Promise.resolve(window.deltaChartBridgeDraw(m)).then(()=>ws.send(JSON.stringify({action:'draw_result',ok:true,request_id:m.request_id}))).catch(err=>ws.send(JSON.stringify({action:'draw_result',ok:false,request_id:m.request_id,error:String(err)})));
   } else {
    ws.send(JSON.stringify({action:'draw_result',ok:false,request_id:m.request_id,error:'No native chart adapter installed'}));
   }
  }
 };
}
connect();
</script></body></html>"""

def _check_auth(request: Request) -> None:
    if ACCESS_TOKEN and request.headers.get("authorization", "") != f"Bearer {ACCESS_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")

def _validate(symbol: Any, price: Any) -> tuple[str, float]:
    s=str(symbol or "").strip().upper()
    try: p=float(price)
    except (TypeError, ValueError) as exc: raise HTTPException(status_code=400, detail="price must be numeric") from exc
    if not s or p <= 0: raise HTTPException(status_code=400, detail="symbol and positive price are required")
    return s,p

@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"ok": True, "service": "Jeet Delta Chart Bridge", "token_configured": bool(ACCESS_TOKEN), "connected_clients": len(_clients)})

@app.get("/bridge", response_class=HTMLResponse)
async def bridge(request: Request) -> HTMLResponse:
    _check_auth(request)
    return HTMLResponse(HTML)

@app.post("/draw")
async def draw(request: Request) -> JSONResponse:
    _check_auth(request)
    body=await request.json()
    symbol,price=_validate(body.get("symbol"),body.get("price"))
    request_id=str(body.get("request_id") or "bridge")
    command={"action":"draw_horizontal_line","symbol":symbol,"price":price,"label":str(body.get("label") or "Horizontal level"),"request_id":request_id}
    sent=0
    for client in list(_clients):
        try:
            await client.send_json(command); sent += 1
        except Exception:
            _clients.discard(client)
    return JSONResponse({"ok": True, "dispatched_to_clients": sent, "command": command})

@app.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    token=websocket.query_params.get("token", "")
    if ACCESS_TOKEN and token != ACCESS_TOKEN:
        await websocket.close(code=1008); return
    await websocket.accept(); _clients.add(websocket)
    try:
        while True:
            msg:dict[str,Any]=await websocket.receive_json()
            if msg.get("action") == "draw_horizontal_line":
                symbol,price=_validate(msg.get("symbol"),msg.get("price"))
                command={"action":"draw_horizontal_line","symbol":symbol,"price":price,"label":str(msg.get("label") or "Horizontal level"),"request_id":str(msg.get("request_id") or "local")}
                for client in list(_clients):
                    try: await client.send_json(command)
                    except Exception: _clients.discard(client)
                await websocket.send_json({"ok":True,"queued":True,"command":command})
            elif msg.get("action") == "draw_result":
                await websocket.send_json(msg)
    finally:
        _clients.discard(websocket)

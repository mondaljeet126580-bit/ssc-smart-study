from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI(title="Jeet Delta Chart Bridge", version="1.2.0")
ACCESS_TOKEN = os.getenv("CHART_BRIDGE_TOKEN", "").strip()
_clients: set[WebSocket] = set()
_pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
_last_result: dict[str, Any] = {}

HTML = """<!doctype html><html><body style='font-family:system-ui;background:#111;color:#eee;padding:20px'>
<h2>Jeet Delta Chart Bridge</h2><p id='s'>Bridge ready. Keep this page open on the Delta chart tab/device.</p>
<script>
const token=new URLSearchParams(location.search).get('token')||'';
let ws;
function connect(){
 const p=location.protocol==='https:'?'wss':'ws';
 ws=new WebSocket(`${p}://${location.host}/ws?token=${encodeURIComponent(token)}`);
 ws.onopen=()=>document.getElementById('s').textContent='Bridge connected and listening';
 ws.onclose=()=>{document.getElementById('s').textContent='Disconnected; retrying…';setTimeout(connect,1500)};
 ws.onmessage=e=>{
  let m; try{m=JSON.parse(e.data)}catch{return}
  if(m.action==='draw_horizontal_line'){
   if(typeof window.deltaChartBridgeDraw!=='function'){
    ws.send(JSON.stringify({action:'draw_result',ok:false,request_id:m.request_id,error:'Native chart adapter is not installed'}));
    return;
   }
   Promise.resolve(window.deltaChartBridgeDraw(m))
    .then(result=>ws.send(JSON.stringify({action:'draw_result',ok:true,request_id:m.request_id,result:result||{}})))
    .catch(err=>ws.send(JSON.stringify({action:'draw_result',ok:false,request_id:m.request_id,error:String(err)})));
  }
 };
}
connect();
</script></body></html>"""


def _check_auth(request: Request) -> None:
    if ACCESS_TOKEN and request.headers.get("authorization", "") != f"Bearer {ACCESS_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")


def _validate(symbol: Any, price: Any) -> tuple[str, float]:
    s = str(symbol or "").strip().upper()
    try:
        p = float(price)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="price must be numeric") from exc
    if not s or p <= 0:
        raise HTTPException(status_code=400, detail="symbol and positive price are required")
    return s, p


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({
        "ok": True,
        "service": "Jeet Delta Chart Bridge",
        "token_configured": bool(ACCESS_TOKEN),
        "connected_clients": len(_clients),
        "pending_commands": len(_pending),
        "last_result": _last_result,
    })


@app.get("/bridge", response_class=HTMLResponse)
async def bridge(request: Request) -> HTMLResponse:
    _check_auth(request)
    return HTMLResponse(HTML)


@app.get("/status")
async def status(request: Request) -> JSONResponse:
    _check_auth(request)
    return JSONResponse({
        "ok": True,
        "connected_clients": len(_clients),
        "pending_commands": len(_pending),
        "last_result": _last_result,
    })


@app.post("/draw")
async def draw(request: Request) -> JSONResponse:
    _check_auth(request)
    body = await request.json()
    symbol, price = _validate(body.get("symbol"), body.get("price"))
    if not _clients:
        raise HTTPException(status_code=503, detail="No browser chart client is connected. Open the bridge page in the chart browser context first.")

    request_id = str(body.get("request_id") or uuid.uuid4().hex)
    command = {
        "action": "draw_horizontal_line",
        "symbol": symbol,
        "price": price,
        "label": str(body.get("label") or "Horizontal level"),
        "request_id": request_id,
    }
    loop = asyncio.get_running_loop()
    future: asyncio.Future[dict[str, Any]] = loop.create_future()
    _pending[request_id] = future
    sent = 0
    for client in list(_clients):
        try:
            await client.send_json(command)
            sent += 1
        except Exception:
            _clients.discard(client)

    if sent == 0:
        _pending.pop(request_id, None)
        raise HTTPException(status_code=503, detail="No live browser chart client could receive the command")

    try:
        result = await asyncio.wait_for(future, timeout=15.0)
    except asyncio.TimeoutError as exc:
        _pending.pop(request_id, None)
        raise HTTPException(status_code=504, detail="Browser chart client did not confirm native drawing within 15 seconds") from exc

    _pending.pop(request_id, None)
    _last_result.clear()
    _last_result.update({"request_id": request_id, "result": result})
    if not result.get("ok"):
        raise HTTPException(status_code=422, detail=str(result.get("error") or "Native chart drawing failed"))
    return JSONResponse({"ok": True, "executed": True, "native_chart_modified": True, "dispatched_to_clients": sent, "request_id": request_id, "result": result.get("result", {})})


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
            action = msg.get("action")
            if action == "draw_result":
                request_id = str(msg.get("request_id") or "")
                future = _pending.get(request_id)
                if future and not future.done():
                    future.set_result(msg)
            elif action == "draw_horizontal_line":
                symbol, price = _validate(msg.get("symbol"), msg.get("price"))
                command = {
                    "action": "draw_horizontal_line",
                    "symbol": symbol,
                    "price": price,
                    "label": str(msg.get("label") or "Horizontal level"),
                    "request_id": str(msg.get("request_id") or uuid.uuid4().hex),
                }
                for client in list(_clients):
                    try:
                        await client.send_json(command)
                    except Exception:
                        _clients.discard(client)
    finally:
        _clients.discard(websocket)

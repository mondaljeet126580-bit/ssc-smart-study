from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI(title="Jeet Delta Chart Bridge", version="1.3.0")
ACCESS_TOKEN = os.getenv("CHART_BRIDGE_TOKEN", "").strip()
_clients: set[WebSocket] = set()
_pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
_last_result: dict[str, Any] = {}

HTML = """<!doctype html>
<html><body style='font-family:system-ui;background:#111;color:#eee;padding:20px'>
<h2>Jeet Delta Chart Bridge</h2>
<p id='s'>Bridge ready. Keep this page open on the Delta chart tab.</p>
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
   window.postMessage({source:'JEET_DELTA_BRIDGE_PAGE',type:'draw_horizontal_line',command:m},'*');
  }
 };
}
connect();
</script></body></html>"""


def _check_auth(request: Request) -> None:
    if ACCESS_TOKEN and request.headers.get("authorization", "") != f"Bearer {ACCESS_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")


def _validate(symbol: Any, price: Any, resolution: Any = "15m") -> tuple[str, float, str]:
    symbol_value = str(symbol or "").strip().upper()
    try:
        price_value = float(price)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="price must be numeric") from exc
    resolution_value = str(resolution or "15m").strip()
    allowed = {"1m","3m","5m","15m","30m","1h","2h","4h","6h","12h","1d","1w"}
    if not symbol_value or price_value <= 0:
        raise HTTPException(status_code=400, detail="symbol and positive price are required")
    if resolution_value not in allowed:
        raise HTTPException(status_code=400, detail=f"unsupported resolution: {resolution_value}")
    return symbol_value, price_value, resolution_value


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
    symbol, price, resolution = _validate(body.get("symbol"), body.get("price"), body.get("resolution", "15m"))
    if not _clients:
        raise HTTPException(status_code=503, detail="No browser chart client is connected")

    request_id = str(body.get("request_id") or uuid.uuid4().hex)
    command = {
        "action": "draw_horizontal_line",
        "symbol": symbol,
        "price": price,
        "resolution": resolution,
        "label": str(body.get("label") or "Horizontal level"),
        "request_id": request_id,
    }
    loop = asyncio.get_running_loop()
    future: asyncio.Future[dict[str, Any]] = loop.create_future()
    _pending[request_id] = future
    delivered = 0
    for client in list(_clients):
        try:
            await client.send_json(command)
            delivered += 1
        except Exception:
            _clients.discard(client)
    if delivered == 0:
        _pending.pop(request_id, None)
        raise HTTPException(status_code=503, detail="No live browser chart client could receive the command")

    try:
        result = await asyncio.wait_for(future, timeout=20.0)
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Native chart client did not confirm drawing within 20 seconds") from exc
    finally:
        _pending.pop(request_id, None)

    _last_result.clear()
    _last_result.update({"request_id": request_id, "result": result})
    if not result.get("ok"):
        raise HTTPException(status_code=422, detail=str(result.get("error") or "Native chart drawing failed"))
    return JSONResponse({
        "ok": True,
        "executed": True,
        "native_chart_modified": True,
        "symbol": symbol,
        "resolution": resolution,
        "price": price,
        "dispatched_to_clients": delivered,
        "request_id": request_id,
        "result": result.get("result", {}),
    })


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
                symbol, price, resolution = _validate(msg.get("symbol"), msg.get("price"), msg.get("resolution", "15m"))
                command = {
                    "action": "draw_horizontal_line",
                    "symbol": symbol,
                    "price": price,
                    "resolution": resolution,
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

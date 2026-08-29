from __future__ import annotations

import os
import uuid
from typing import Any

import httpx


async def dispatch_horizontal_line(
    symbol: str,
    price: float,
    resolution: str = "15m",
    label: str = "Horizontal level",
) -> dict[str, Any]:
    """Dispatch an exact horizontal-line command and require native execution confirmation."""
    bridge_url = os.getenv("CHART_BRIDGE_URL", "").strip().rstrip("/")
    token = os.getenv("CHART_BRIDGE_TOKEN", "").strip()
    if not bridge_url:
        return {"ok": False, "executed": False, "error": "CHART_BRIDGE_URL is not configured"}

    request_id = uuid.uuid4().hex
    headers = {"Authorization": f"Bearer {token}"} if token else None
    payload = {
        "symbol": str(symbol).strip().upper(),
        "price": float(price),
        "resolution": str(resolution).strip(),
        "label": str(label or "Horizontal level"),
        "request_id": request_id,
    }
    try:
        async with httpx.AsyncClient(timeout=30) as http:
            response = await http.post(f"{bridge_url}/draw", json=payload, headers=headers)
            try:
                data = response.json()
            except Exception:
                data = {"executed": False, "native_chart_modified": False, "error": response.text[:1000]}
    except Exception as exc:
        return {
            "ok": False,
            "executed": False,
            "request_id": request_id,
            "error": f"{type(exc).__name__}: {exc}",
        }

    executed = bool(data.get("executed")) and bool(data.get("native_chart_modified"))
    return {
        "ok": response.is_success and executed,
        "executed": executed,
        "request_id": request_id,
        "status_code": response.status_code,
        "response": data,
    }

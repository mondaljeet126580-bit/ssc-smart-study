from __future__ import annotations

import os
import uuid
from typing import Any

import httpx


async def dispatch_horizontal_line(symbol: str, price: float, label: str = "Horizontal level") -> dict[str, Any]:
    """Dispatch an exact horizontal-line command to the connected chart bridge."""
    bridge_url = os.getenv("CHART_BRIDGE_URL", "").strip().rstrip("/")
    token = os.getenv("CHART_BRIDGE_TOKEN", "").strip()
    if not bridge_url:
        return {"ok": False, "executed": False, "error": "CHART_BRIDGE_URL is not configured"}

    request_id = uuid.uuid4().hex
    headers = {"Authorization": f"Bearer {token}"} if token else None
    payload = {
        "symbol": str(symbol).strip().upper(),
        "price": float(price),
        "label": str(label or "Horizontal level"),
        "request_id": request_id,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(f"{bridge_url}/draw", json=payload, headers=headers)
        try:
            data = response.json()
        except Exception:
            data = {"ok": False, "executed": False, "error": response.text[:1000]}
        return {
            "ok": response.is_success and bool(data.get("ok")) and bool(data.get("executed")),
            "executed": bool(data.get("executed")),
            "request_id": request_id,
            "status_code": response.status_code,
            "response": data,
        }

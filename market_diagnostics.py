from __future__ import annotations

import time
from typing import Any

from delta_client import DeltaAPIError


def register_market_diagnostics(mcp, client) -> None:
    @mcp.tool()
    async def diagnose_market_data(
        symbol: str = "BTCUSD",
        resolution: str = "15m",
        candles: int = 120,
    ) -> Any:
        """Diagnose Delta public OHLC candle access and return the exact API result/error."""
        symbol = symbol.strip().upper()
        resolution = resolution.strip()
        candles = max(5, min(int(candles), 2000))
        supported = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d", "1w"}
        if resolution not in supported:
            return {
                "ok": False,
                "stage": "validation",
                "message": f"Unsupported resolution: {resolution}",
                "supported_resolutions": sorted(supported),
            }

        seconds = {
            "1m": 60, "3m": 180, "5m": 300, "15m": 900,
            "30m": 1800, "1h": 3600, "2h": 7200,
            "4h": 14400, "6h": 21600, "12h": 43200,
            "1d": 86400, "1w": 604800,
        }[resolution]
        end = int(time.time())
        start = end - seconds * candles
        params = {
            "resolution": resolution,
            "symbol": symbol,
            "start": start,
            "end": end,
        }
        try:
            data = await client.public("GET", "/v2/history/candles", params)
            result = data.get("result") if isinstance(data, dict) else data
            return {
                "ok": True,
                "stage": "delta_candles",
                "endpoint": "/v2/history/candles",
                "params": params,
                "rows": len(result) if isinstance(result, list) else None,
                "sample": result[:2] if isinstance(result, list) else result,
            }
        except DeltaAPIError as exc:
            return {
                "ok": False,
                "stage": "delta_candles",
                "endpoint": "/v2/history/candles",
                "params": params,
                "message": str(exc),
                "hint": "Check symbol, resolution, start/end timestamps, Delta public API availability, and rate limits.",
            }
        except Exception as exc:
            return {
                "ok": False,
                "stage": "server_runtime",
                "endpoint": "/v2/history/candles",
                "params": params,
                "message": f"{type(exc).__name__}: {exc}",
            }

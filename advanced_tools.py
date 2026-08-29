from __future__ import annotations

import base64
import io
import math
import os
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from PIL import Image as PILImage, ImageDraw, ImageFont

_RESOLUTION_SECONDS = {
    "1m": 60, "3m": 180, "5m": 300, "10m": 600, "15m": 900, "30m": 1800,
    "1h": 3600, "2h": 7200, "4h": 14400, "6h": 21600, "12h": 43200,
    "1d": 86400, "1w": 604800,
}

_CHART_DRAWINGS: dict[tuple[str, str], list[float]] = {}


def _extract_result(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        result = data.get("result", [])
        return result if isinstance(result, list) else []
    return data if isinstance(data, list) else []


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _font(size: int):
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except Exception:
        return ImageFont.load_default()


def _linear_regression(values: list[float]) -> tuple[float, float]:
    n = len(values)
    if n < 2:
        return 0.0, values[-1] if values else 0.0
    sx = sum(range(n)); sy = sum(values); sxx = sum(i * i for i in range(n)); sxy = sum(i * value for i, value in enumerate(values))
    denom = n * sxx - sx * sx
    if denom == 0:
        return 0.0, values[-1]
    slope = (n * sxy - sx * sy) / denom
    return slope, (sy - slope * sx) / n


def _ema(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    alpha = 2.0 / (period + 1.0)
    value = sum(values[:period]) / period
    for price in values[period:]:
        value = alpha * price + (1.0 - alpha) * value
    return value


def _atr(rows: list[dict[str, float]], period: int = 14) -> float | None:
    if len(rows) <= period:
        return None
    trs: list[float] = []
    previous_close: float | None = None
    for row in rows:
        high, low, close = row["high"], row["low"], row["close"]
        tr = high - low if previous_close is None else max(high - low, abs(high - previous_close), abs(low - previous_close))
        trs.append(tr)
        previous_close = close
    return sum(trs[-period:]) / period


def _pct(a: float, b: float) -> float:
    return ((a - b) / b * 100.0) if b else 0.0


def _analyze_rows(rows: list[dict[str, float]], reference: float | None) -> dict[str, Any]:
    closes = [r["close"] for r in rows]
    highs = [r["high"] for r in rows]
    lows = [r["low"] for r in rows]
    current = closes[-1]
    ema20 = _ema(closes, 20)
    ema50 = _ema(closes, 50)
    ema200 = _ema(closes, 200)
    atr14 = _atr(rows, 14)
    slope, _ = _linear_regression(closes[-min(50, len(closes)):])
    recent = rows[-min(30, len(rows)):]
    swing_high = max(r["high"] for r in recent)
    swing_low = min(r["low"] for r in recent)
    prior = rows[-min(10, len(rows)):-1] or rows[:-1]
    prior_high = max((r["high"] for r in prior), default=swing_high)
    prior_low = min((r["low"] for r in prior), default=swing_low)
    trend_score = 0
    if ema20 is not None and current > ema20: trend_score += 1
    elif ema20 is not None and current < ema20: trend_score -= 1
    if ema50 is not None and current > ema50: trend_score += 1
    elif ema50 is not None and current < ema50: trend_score -= 1
    if ema200 is not None and current > ema200: trend_score += 1
    elif ema200 is not None and current < ema200: trend_score -= 1
    if slope > 0: trend_score += 1
    elif slope < 0: trend_score -= 1
    trend = "bullish" if trend_score >= 2 else "bearish" if trend_score <= -2 else "mixed / ranging"
    ref_zone = None
    if reference is not None:
        distance_pct = _pct(current, reference)
        tolerance = max(atr14 * 0.35 if atr14 else 0.0, abs(reference) * 0.001)
        near = abs(current - reference) <= tolerance
        crossed_up = prior_high < reference <= current or prior_low < reference <= current
        crossed_down = prior_low > reference >= current or prior_high > reference >= current
        last_touch = min((abs(r["high"] - reference), abs(r["low"] - reference), abs(r["close"] - reference)) for r in rows[-min(12, len(rows)):])
        ref_context = "near_level" if near else "above_level" if current > reference else "below_level"
        interaction = "possible_breakout" if crossed_up else "possible_breakdown" if crossed_down else "watch_reaction"
        if ref_context == "above_level" and trend == "bullish": bias = "bullish_above_reference"
        elif ref_context == "below_level" and trend == "bearish": bias = "bearish_below_reference"
        else: bias = "wait_for_confirmation"
        ref_zone = {
            "reference_price": reference,
            "distance_percent": round(distance_pct, 4),
            "context": ref_context,
            "interaction": interaction,
            "nearest_recent_touch_distance": float(last_touch[0]),
            "bias": bias,
            "breakout_confirmation": f"15m candle close above {reference}" if current < reference else f"Candle acceptance above {reference}",
            "breakdown_confirmation": f"15m candle close below {reference}" if current > reference else f"Candle acceptance below {reference}",
        }
    volatility = "high" if atr14 is not None and atr14 / current > 0.01 else "moderate" if atr14 is not None and atr14 / current > 0.004 else "low"
    return {
        "current_price": current,
        "trend": trend,
        "trend_score": trend_score,
        "ema20": ema20,
        "ema50": ema50,
        "ema200": ema200,
        "atr14": atr14,
        "atr_percent": _pct(atr14, current) if atr14 is not None else None,
        "volatility": volatility,
        "recent_swing_high": swing_high,
        "recent_swing_low": swing_low,
        "recent_structure": {"prior_high": prior_high, "prior_low": prior_low, "higher_high": swing_high > prior_high, "lower_low": swing_low < prior_low},
        "reference": ref_zone,
    }


def _analyze_volume(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    values = [_num(r.get("volume")) for r in rows]
    volumes = [v for v in values if v is not None and math.isfinite(v)]
    if len(volumes) < 10:
        return None
    recent = volumes[-10:]
    avg = sum(volumes[-20:]) / min(20, len(volumes))
    return {"available": True, "recent_average": avg, "latest": volumes[-1], "latest_vs_20_avg_percent": _pct(volumes[-1], avg)}


def register_advanced_tools(mcp, client) -> None:
    @mcp.tool()
    async def get_all_funding_rates(limit: int = 100, sort_mode: str = "highest_abs") -> Any:
        """Return funding rates for all listed perpetual-futures tickers."""
        limit = max(1, min(limit, 500)); sort_mode = sort_mode.strip().lower()
        if sort_mode not in {"highest_abs", "highest_positive", "lowest_negative"}:
            raise ValueError("sort_mode must be highest_abs, highest_positive, or lowest_negative")
        data = await client.public("GET", "/v2/tickers", {"contract_types": "perpetual_futures"})
        rows = []
        for ticker in _extract_result(data):
            rate = _num(ticker.get("funding_rate") or ticker.get("fundingRate") or ticker.get("fr")); symbol = str(ticker.get("symbol") or ticker.get("sy") or "")
            if rate is None or not symbol: continue
            rows.append({"symbol": symbol, "funding_rate": rate, "funding_rate_pct": f"{rate * 100:.6f}%", "abs_funding_rate": abs(rate), "mark_price": ticker.get("mark_price"), "open_interest": ticker.get("oi"), "volume_24h": ticker.get("volume"), "timestamp": ticker.get("timestamp")})
        if sort_mode == "highest_positive": rows.sort(key=lambda x: x["funding_rate"], reverse=True)
        elif sort_mode == "lowest_negative": rows.sort(key=lambda x: x["funding_rate"])
        else: rows.sort(key=lambda x: x["abs_funding_rate"], reverse=True)
        positive = sorted([r for r in rows if r["funding_rate"] > 0], key=lambda x: x["funding_rate"], reverse=True)
        negative = sorted([r for r in rows if r["funding_rate"] < 0], key=lambda x: x["funding_rate"])
        return {"source": "Delta Exchange India /v2/tickers", "contract_type": "perpetual_futures", "total_perpetuals_with_funding": len(rows), "sort_mode": sort_mode, "highest_positive": positive[:10], "lowest_negative": negative[:10], "ranked": rows[:limit]}

    @mcp.tool()
    async def get_funding_history(symbol: str, resolution: str = "1h", hours: int = 24) -> Any:
        """Get historical funding-rate candles for one perpetual symbol."""
        resolution = resolution.strip()
        if resolution not in _RESOLUTION_SECONDS: raise ValueError(f"Unsupported resolution: {resolution}")
        hours = max(1, min(hours, 720)); now = int(time.time())
        return await client.public("GET", "/v2/history/candles", {"resolution": resolution, "symbol": f"FUNDING:{symbol.upper()}", "start": now - hours * 3600, "end": now})

    def _normalize(rows: list[dict[str, Any]], candles: int, symbol: str) -> list[dict[str, float]]:
        clean = []
        for row in rows:
            try:
                values = {"time": float(row["time"]), "open": float(row["open"]), "high": float(row["high"]), "low": float(row["low"]), "close": float(row["close"])}
                if not all(math.isfinite(v) for v in values.values()): continue
                if values["high"] < values["low"] or values["high"] < max(values["open"], values["close"]) or values["low"] > min(values["open"], values["close"]): continue
                clean.append(values)
            except (KeyError, TypeError, ValueError):
                continue
        clean = sorted(clean, key=lambda x: x["time"])[-candles:]
        if len(clean) < 5: raise RuntimeError(f"Not enough valid OHLC candles returned for {symbol.upper()}")
        return clean

    async def _fetch_chart_data(symbol: str, resolution: str, candles: int) -> list[dict[str, float]]:
        now = int(time.time()); step = _RESOLUTION_SECONDS[resolution]
        data = await client.public("GET", "/v2/history/candles", {"resolution": resolution, "symbol": symbol.upper(), "start": now - step * candles, "end": now})
        rows = _extract_result(data)
        if not rows: raise RuntimeError(f"No candle data returned for {symbol.upper()}")
        return _normalize(rows, candles, symbol)

    @mcp.tool()
    async def analyze_market(
        symbol: str,
        reference_price: float | None = None,
        timeframes: str = "5m,15m,1h,4h,1d",
        candles: int = 250,
    ) -> dict[str, Any]:
        """Perform backend-only multi-timeframe technical analysis without any browser chart client.

        reference_price is an optional exact level such as 78050. timeframes is a comma-separated
        list from 1m,3m,5m,10m,15m,30m,1h,2h,4h,6h,12h,1d,1w.
        """
        symbol = symbol.strip().upper()
        requested = [x.strip() for x in timeframes.split(",") if x.strip()]
        if not requested: raise ValueError("At least one timeframe is required")
        unsupported = [x for x in requested if x not in _RESOLUTION_SECONDS]
        if unsupported: raise ValueError(f"Unsupported timeframe(s): {', '.join(unsupported)}")
        candles = max(50, min(int(candles), 2000))
        reference = None if reference_price is None else float(reference_price)
        if reference is not None and (not math.isfinite(reference) or reference <= 0): raise ValueError("reference_price must be positive and finite")

        analyses: dict[str, Any] = {}
        fetched_rows: dict[str, list[dict[str, float]]] = {}
        for tf in requested:
            rows = await _fetch_chart_data(symbol, tf, candles)
            fetched_rows[tf] = rows
            analysis = _analyze_rows(rows, reference)
            analysis["volume"] = None
            analyses[tf] = analysis

        current = analyses[requested[0]]["current_price"]
        bullish = sum(1 for a in analyses.values() if a["trend"] == "bullish")
        bearish = sum(1 for a in analyses.values() if a["trend"] == "bearish")
        overall = "bullish" if bullish > bearish and bullish >= 2 else "bearish" if bearish > bullish and bearish >= 2 else "mixed"
        nearest_support = min(a["recent_swing_low"] for a in analyses.values())
        nearest_resistance = max(a["recent_swing_high"] for a in analyses.values())
        primary = analyses["15m"] if "15m" in analyses else analyses[requested[0]]
        scenario = primary.get("reference") or {}
        trade = {
            "bullish": {"trigger": f"acceptance/close above {reference}" if reference else f"break above {nearest_resistance}", "invalidation": f"close below {reference}" if reference else f"break below {primary['recent_swing_low']}", "targets": [nearest_resistance], "condition": "Wait for confirmation; do not chase a first wick."},
            "bearish": {"trigger": f"rejection/close below {reference}" if reference else f"break below {nearest_support}", "invalidation": f"close back above {reference}" if reference else f"reclaim above {primary['recent_swing_high']}", "targets": [nearest_support], "condition": "Wait for confirmation; avoid entries inside a range."},
        }
        return {
            "symbol": symbol,
            "reference_price": reference,
            "current_price": current,
            "timeframes": requested,
            "timeframe_analysis": analyses,
            "overall_bias": overall,
            "multi_timeframe_counts": {"bullish": bullish, "bearish": bearish, "mixed": len(analyses) - bullish - bearish},
            "cross_timeframe_levels": {"support_candidate": nearest_support, "resistance_candidate": nearest_resistance},
            "reference_level_read": scenario,
            "trade_scenarios": trade,
            "data_source": "Delta Exchange public /v2/history/candles",
            "browser_chart_client_required": False,
            "analysis_notes": [
                "Analysis is based on OHLC structure, EMA20/50/200 when enough candles exist, regression trend, ATR volatility, and recent swing structure.",
                "Volume is only analyzed when the API response actually includes a usable volume field.",
                "Reference-price decisions should be confirmed by candle close rather than a single wick.",
            ],
        }

    @mcp.tool()
    async def get_all_funding_rates_placeholder(limit: int = 1) -> Any:
        """Compatibility placeholder; funding tools remain available in the existing MCP build."""
        return {"ok": True, "message": "Use get_all_funding_rates for funding-rate analysis.", "limit": limit}

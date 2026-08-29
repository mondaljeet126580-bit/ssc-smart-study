from __future__ import annotations

import base64
import io
import math
import time
from datetime import datetime, timezone
from typing import Any

from PIL import Image as PILImage
from PIL import ImageDraw, ImageFont


_RESOLUTION_SECONDS = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "6h": 21600,
    "12h": 43200,
    "1d": 86400,
    "1w": 604800,
}

# MCP-side chart drawings. Delta's public REST API provides market/account APIs,
# but it does not provide an endpoint for TradingView chart drawing objects.
_CHART_DRAWINGS: dict[tuple[str, str], list[dict[str, Any]]] = {}


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


def _funding_value(ticker: dict[str, Any]) -> float | None:
    for key in ("funding_rate", "fundingRate", "fr"):
        value = _num(ticker.get(key))
        if value is not None:
            return value
    return None


def _funding_symbol(ticker: dict[str, Any]) -> str:
    return str(ticker.get("symbol") or ticker.get("sy") or "")


def _fmt_pct(rate: float | None) -> str | None:
    return None if rate is None else f"{rate * 100:.6f}%"


def _font(size: int):
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except Exception:
        return ImageFont.load_default()


def _linear_regression(values: list[float]) -> tuple[float, float]:
    n = len(values)
    if n < 2:
        return 0.0, values[-1] if values else 0.0
    sx = sum(range(n))
    sy = sum(values)
    sxx = sum(i * i for i in range(n))
    sxy = sum(i * value for i, value in enumerate(values))
    denom = n * sxx - sx * sx
    if denom == 0:
        return 0.0, values[-1]
    slope = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n
    return slope, intercept


def register_advanced_tools(mcp, client) -> None:
    @mcp.tool()
    async def get_all_funding_rates(limit: int = 100, sort_mode: str = "highest_abs") -> Any:
        """Return funding rates for all listed perpetual-futures tickers."""
        limit = max(1, min(limit, 500))
        sort_mode = sort_mode.strip().lower()
        if sort_mode not in {"highest_abs", "highest_positive", "lowest_negative"}:
            raise ValueError("sort_mode must be highest_abs, highest_positive, or lowest_negative")
        data = await client.public("GET", "/v2/tickers", {"contract_types": "perpetual_futures"})
        tickers = _extract_result(data)
        rows: list[dict[str, Any]] = []
        for ticker in tickers:
            rate = _funding_value(ticker)
            symbol = _funding_symbol(ticker)
            if rate is None or not symbol:
                continue
            rows.append({"symbol": symbol, "funding_rate": rate, "funding_rate_pct": _fmt_pct(rate), "abs_funding_rate": abs(rate), "mark_price": ticker.get("mark_price"), "open_interest": ticker.get("oi"), "volume_24h": ticker.get("volume"), "timestamp": ticker.get("timestamp")})
        if sort_mode == "highest_positive":
            rows.sort(key=lambda x: x["funding_rate"], reverse=True)
        elif sort_mode == "lowest_negative":
            rows.sort(key=lambda x: x["funding_rate"])
        else:
            rows.sort(key=lambda x: x["abs_funding_rate"], reverse=True)
        positive = sorted([r for r in rows if r["funding_rate"] > 0], key=lambda x: x["funding_rate"], reverse=True)
        negative = sorted([r for r in rows if r["funding_rate"] < 0], key=lambda x: x["funding_rate"])
        return {"source": "Delta Exchange India /v2/tickers", "contract_type": "perpetual_futures", "total_perpetuals_with_funding": len(rows), "sort_mode": sort_mode, "highest_positive": positive[:10], "lowest_negative": negative[:10], "ranked": rows[:limit]}

    @mcp.tool()
    async def get_funding_history(symbol: str, resolution: str = "1h", hours: int = 24) -> Any:
        """Get historical funding-rate candles for one perpetual symbol."""
        resolution = resolution.strip()
        if resolution not in _RESOLUTION_SECONDS:
            raise ValueError(f"Unsupported resolution: {resolution}")
        hours = max(1, min(hours, 720))
        now = int(time.time())
        return await client.public("GET", "/v2/history/candles", {"resolution": resolution, "symbol": f"FUNDING:{symbol.upper()}", "start": now - hours * 3600, "end": now})

    def _normalize_candle_rows(rows: list[dict[str, Any]], candles: int, symbol: str) -> list[dict[str, float]]:
        clean: list[dict[str, float]] = []
        for row in rows:
            try:
                values = {"time": float(row["time"]), "open": float(row["open"]), "high": float(row["high"]), "low": float(row["low"]), "close": float(row["close"])}
                if not all(math.isfinite(v) for v in values.values()):
                    continue
                if values["high"] < values["low"] or values["high"] < max(values["open"], values["close"]) or values["low"] > min(values["open"], values["close"]):
                    continue
                clean.append(values)
            except (KeyError, TypeError, ValueError):
                continue
        clean = sorted(clean, key=lambda x: x["time"])[-candles:]
        if len(clean) < 5:
            raise RuntimeError(f"Not enough valid OHLC candles returned for {symbol.upper()}")
        return clean

    async def _fetch_chart_data(symbol: str, resolution: str, candles: int) -> list[dict[str, float]]:
        step = _RESOLUTION_SECONDS[resolution]
        now = int(time.time())
        data = await client.public("GET", "/v2/history/candles", {"resolution": resolution, "symbol": symbol.upper(), "start": now - step * candles, "end": now})
        rows = _extract_result(data)
        if not rows:
            raise RuntimeError(f"No candle data returned for {symbol.upper()}")
        return _normalize_candle_rows(rows, candles, symbol)

    def _drawing_levels(symbol: str, resolution: str, requested: float | None = None) -> list[float]:
        key = (symbol.upper(), resolution)
        drawings = _CHART_DRAWINGS.get(key, [])
        if requested is not None and not any(math.isclose(float(d["price"]), requested, rel_tol=0.0, abs_tol=1e-12) for d in drawings):
            drawings.append({"type": "horizontal_line", "price": requested})
            _CHART_DRAWINGS[key] = drawings[-50:]
        return [float(d["price"]) for d in _CHART_DRAWINGS.get(key, [])]

    def _render_market_chart(clean: list[dict[str, float]], symbol: str, resolution: str, horizontal_price: float | None, show_trendline: bool, show_support_resistance: bool, horizontal_label: str = "Horizontal level") -> tuple[bytes, dict[str, Any]]:
        width, height = 1400, 820
        image = PILImage.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)
        title_font, small_font, axis_font = _font(28), _font(17), _font(15)
        left, right, top, bottom = 90, 150, 70, 100
        plot_w, plot_h = width - left - right, height - top - bottom
        highs, lows, closes = [r["high"] for r in clean], [r["low"] for r in clean], [r["close"] for r in clean]
        levels = _drawing_levels(symbol, resolution, horizontal_price)
        range_min, range_max = min(lows), max(highs)
        if levels:
            range_min, range_max = min([range_min, *levels]), max([range_max, *levels])
        if range_min == range_max:
            base = max(abs(range_min), 1.0)
            range_min, range_max = range_min - base * 0.01, range_max + base * 0.01
        span = range_max - range_min
        pad = max(span * 0.08, abs(range_max) * 0.0005, 1e-9)
        price_min, price_max = range_min - pad, range_max + pad

        def x_at(i: int) -> int:
            return int(left + (i / max(1, len(clean) - 1)) * plot_w)

        def y_at(price: float) -> int:
            return int(round(top + (price_max - price) / (price_max - price_min) * plot_h))

        for frac in range(6):
            y = int(top + (frac / 5) * plot_h)
            price = price_max - (frac / 5) * (price_max - price_min)
            draw.line((left, y, width - right, y), fill="#e5e7eb", width=1)
            draw.text((width - right + 10, y - 9), f"{price:.6g}", fill="#374151", font=axis_font)
        draw.line((left, top, left, height - bottom), fill="#111827", width=2)
        draw.line((left, height - bottom, width - right, height - bottom), fill="#111827", width=2)

        body_half = max(2, plot_w // max(1, len(clean)) // 3)
        for i, row in enumerate(clean):
            x = x_at(i)
            y_open, y_close, y_high, y_low = y_at(row["open"]), y_at(row["close"]), y_at(row["high"]), y_at(row["low"])
            fill = "#16a34a" if row["close"] >= row["open"] else "#dc2626"
            draw.line((x, y_high, x, y_low), fill=fill, width=2)
            top_body, bot_body = min(y_open, y_close), max(y_open, y_close)
            if bot_body - top_body < 2:
                bot_body += 2
            draw.rectangle((x - body_half, top_body, x + body_half, bot_body), fill=fill, outline=fill)

        recent = clean[-min(30, len(clean)):]
        support, resistance = min(r["low"] for r in recent), max(r["high"] for r in recent)
        if show_support_resistance:
            for level, level_label in ((support, "Recent support"), (resistance, "Recent resistance")):
                yy = y_at(level)
                draw.line((left, yy, width - right, yy), fill="#6b7280", width=2)
                draw.text((left + 8, max(top + 4, yy - 24)), f"{level_label}: {level:.6g}", fill="#374151", font=small_font)

        line_y = None
        if horizontal_price is not None:
            line_y = max(top, min(height - bottom, y_at(horizontal_price)))
            draw.line((left, line_y, width - right, line_y), fill="#7c3aed", width=4)
            draw.text((left + 8, max(top + 4, min(height - bottom - 22, line_y + 6))), f"{horizontal_label}: {horizontal_price:.15g}", fill="#7c3aed", font=small_font)
        for level in levels:
            if horizontal_price is not None and math.isclose(level, horizontal_price, rel_tol=0.0, abs_tol=1e-12):
                continue
            yy = max(top, min(height - bottom, y_at(level)))
            draw.line((left, yy, width - right, yy), fill="#7c3aed", width=3)
            draw.text((left + 8, max(top + 4, min(height - bottom - 22, yy + 6))), f"Stored level: {level:.15g}", fill="#7c3aed", font=small_font)

        slope, intercept = _linear_regression(closes)
        if show_trendline:
            draw.line((x_at(0), y_at(intercept), x_at(len(closes) - 1), y_at(slope * (len(closes) - 1) + intercept)), fill="#2563eb", width=4)
            direction = "uptrend" if slope > 0 else "downtrend" if slope < 0 else "flat"
        else:
            direction = "disabled"
        draw.text((left, 20), f"{symbol.upper()} • {resolution} • {len(clean)} candles", fill="#111827", font=title_font)
        trend_pct = (slope * len(closes) / closes[0] * 100) if closes[0] else 0.0
        draw.text((left, height - 70), f"Trend: {direction} | regression slope: {trend_pct:.3f}% across chart", fill="#374151", font=small_font)
        draw.text((left, height - 45), f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}", fill="#6b7280", font=small_font)
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        summary = {"symbol": symbol.upper(), "resolution": resolution, "candles": len(clean), "current_price": closes[-1], "support": support, "resistance": resistance, "horizontal_price": horizontal_price, "stored_horizontal_levels": levels, "line_y": line_y, "trend_direction": direction, "trend_slope_percent_over_chart": trend_pct}
        return buf.getvalue(), summary

    def _json_chart(image_bytes: bytes, summary: dict[str, Any]) -> dict[str, Any]:
        return {**summary, "image_base64": base64.b64encode(image_bytes).decode("ascii"), "image_format": "png"}

    @mcp.tool()
    async def plot_market_chart(symbol: str, resolution: str = "15m", candles: int = 120, horizontal_price: float | None = None, show_trendline: bool = True, show_support_resistance: bool = True) -> dict[str, Any]:
        """Create a market chart and return JSON-safe chart data plus an embedded PNG."""
        symbol, resolution = symbol.strip().upper(), resolution.strip()
        if resolution not in _RESOLUTION_SECONDS:
            raise ValueError(f"Unsupported resolution: {resolution}")
        candles = max(30, min(int(candles), 2000))
        clean = await _fetch_chart_data(symbol, resolution, candles)
        return _json_chart(*_render_market_chart(clean, symbol, resolution, horizontal_price, show_trendline, show_support_resistance))

    @mcp.tool()
    async def plot_horizontal_price_line(symbol: str, price: float, resolution: str = "15m", candles: int = 120, show_trendline: bool = True, show_support_resistance: bool = True, label: str = "Horizontal level") -> dict[str, Any]:
        """Draw and persist a horizontal price level in the MCP chart state.

        The level is also included in subsequent generated chart images. Delta's public REST
        API has no native TradingView drawing endpoint, so this tool cannot directly create
        a persistent drawing inside the native Delta Exchange mobile/web chart.
        """
        symbol, resolution = symbol.strip().upper(), resolution.strip()
        if not symbol:
            raise ValueError("symbol is required")
        if resolution not in _RESOLUTION_SECONDS:
            raise ValueError(f"Unsupported resolution: {resolution}")
        try:
            exact_price = float(price)
        except (TypeError, ValueError) as exc:
            raise ValueError("price must be a valid number") from exc
        if not math.isfinite(exact_price) or exact_price <= 0:
            raise ValueError("price must be a positive finite number")
        candles = max(30, min(int(candles), 2000))
        label = str(label).strip() or "Horizontal level"
        clean = await _fetch_chart_data(symbol, resolution, candles)
        image_bytes, summary = _render_market_chart(clean, symbol, resolution, exact_price, show_trendline, show_support_resistance, horizontal_label=label)
        levels = _drawing_levels(symbol, resolution)
        result = _json_chart(image_bytes, summary)
        result.update({
            "tool": "plot_horizontal_price_line",
            "symbol": symbol,
            "resolution": resolution,
            "line_action": "draw_horizontal",
            "line_price": exact_price,
            "line_price_exact": format(exact_price, ".15g"),
            "line_label": label,
            "stored_horizontal_levels": levels,
            "mcp_drawing_applied": True,
            "native_delta_chart_updated": False,
            "native_chart_update_supported": False,
            "verification": "The generated chart image contains the requested horizontal line, and the MCP drawing state stores the exact level.",
            "native_chart_note": "A Delta API/browser chart bridge is required to place a persistent drawing object inside the native Delta Exchange chart UI.",
            "message": f"Horizontal line stored at exactly {format(exact_price, '.15g')} for {symbol} {resolution}.",
        })
        return result

    @mcp.tool()
    async def get_chart_drawings(symbol: str, resolution: str = "15m") -> dict[str, Any]:
        """Return horizontal chart drawing state stored by this MCP server."""
        symbol, resolution = symbol.strip().upper(), resolution.strip()
        if resolution not in _RESOLUTION_SECONDS:
            raise ValueError(f"Unsupported resolution: {resolution}")
        levels = _drawing_levels(symbol, resolution)
        return {"symbol": symbol, "resolution": resolution, "horizontal_levels": levels, "mcp_drawing_state": True, "native_delta_chart_updated": False}

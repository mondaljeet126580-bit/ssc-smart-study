from __future__ import annotations

import io
import math
import time
from datetime import datetime, timezone
from typing import Any

from PIL import Image as PILImage
from PIL import ImageDraw, ImageFont
from mcp.server.mcpserver import Image


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
    async def get_all_funding_rates(
        limit: int = 100,
        sort_mode: str = "highest_abs",
    ) -> Any:
        """Return funding rates for ALL listed perpetual-futures tickers, ranked so smaller coins are not omitted.

        sort_mode: highest_abs, highest_positive, or lowest_negative.
        Includes positive and negative leaders and the complete ranked list up to limit.
        """
        limit = max(1, min(limit, 500))
        sort_mode = sort_mode.strip().lower()
        if sort_mode not in {"highest_abs", "highest_positive", "lowest_negative"}:
            raise ValueError("sort_mode must be highest_abs, highest_positive, or lowest_negative")

        data = await client.public(
            "GET",
            "/v2/tickers",
            {"contract_types": "perpetual_futures"},
        )
        tickers = _extract_result(data)
        rows: list[dict[str, Any]] = []
        for ticker in tickers:
            rate = _funding_value(ticker)
            symbol = _funding_symbol(ticker)
            if rate is None or not symbol:
                continue
            rows.append(
                {
                    "symbol": symbol,
                    "funding_rate": rate,
                    "funding_rate_pct": _fmt_pct(rate),
                    "abs_funding_rate": abs(rate),
                    "mark_price": ticker.get("mark_price"),
                    "open_interest": ticker.get("oi"),
                    "volume_24h": ticker.get("volume"),
                    "timestamp": ticker.get("timestamp"),
                }
            )

        if sort_mode == "highest_positive":
            rows.sort(key=lambda x: x["funding_rate"], reverse=True)
        elif sort_mode == "lowest_negative":
            rows.sort(key=lambda x: x["funding_rate"])
        else:
            rows.sort(key=lambda x: x["abs_funding_rate"], reverse=True)

        positive = sorted([r for r in rows if r["funding_rate"] > 0], key=lambda x: x["funding_rate"], reverse=True)
        negative = sorted([r for r in rows if r["funding_rate"] < 0], key=lambda x: x["funding_rate"])

        return {
            "source": "Delta Exchange India /v2/tickers",
            "contract_type": "perpetual_futures",
            "total_perpetuals_with_funding": len(rows),
            "sort_mode": sort_mode,
            "highest_positive": positive[:10],
            "lowest_negative": negative[:10],
            "ranked": rows[:limit],
            "note": "Funding rates are included for all returned perpetual tickers; do not restrict the answer to large-cap coins.",
        }

    @mcp.tool()
    async def get_funding_history(
        symbol: str,
        resolution: str = "1h",
        hours: int = 24,
    ) -> Any:
        """Get historical funding-rate candles for one perpetual symbol."""
        resolution = resolution.strip()
        if resolution not in _RESOLUTION_SECONDS:
            raise ValueError(f"Unsupported resolution: {resolution}")
        hours = max(1, min(hours, 720))
        now = int(time.time())
        start = now - hours * 3600
        return await client.public(
            "GET",
            "/v2/history/candles",
            {
                "resolution": resolution,
                "symbol": f"FUNDING:{symbol.upper()}",
                "start": start,
                "end": now,
            },
        )

    @mcp.tool()
    async def plot_market_chart(
        symbol: str,
        resolution: str = "15m",
        candles: int = 120,
        horizontal_price: float | None = None,
        show_trendline: bool = True,
        show_support_resistance: bool = True,
    ) -> list[Any]:
        """Create a real chart image from Delta candles with optional horizontal level and automatic trendline.

        The returned MCP image can be rendered by clients that support image tool results.
        """
        resolution = resolution.strip()
        if resolution not in _RESOLUTION_SECONDS:
            raise ValueError(f"Unsupported resolution: {resolution}")
        candles = max(30, min(candles, 2000))
        step = _RESOLUTION_SECONDS[resolution]
        now = int(time.time())
        start = now - step * candles
        data = await client.public(
            "GET",
            "/v2/history/candles",
            {
                "resolution": resolution,
                "symbol": symbol.upper(),
                "start": start,
                "end": now,
            },
        )
        rows = _extract_result(data)
        if not rows:
            raise RuntimeError(f"No candle data returned for {symbol.upper()}")

        clean: list[dict[str, float]] = []
        for row in rows:
            try:
                clean.append(
                    {
                        "time": float(row["time"]),
                        "open": float(row["open"]),
                        "high": float(row["high"]),
                        "low": float(row["low"]),
                        "close": float(row["close"]),
                    }
                )
            except (KeyError, TypeError, ValueError):
                continue
        clean = sorted(clean, key=lambda x: x["time"])[-candles:]
        if len(clean) < 5:
            raise RuntimeError(f"Not enough valid OHLC candles returned for {symbol.upper()}")

        width, height = 1400, 820
        image = PILImage.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)
        title_font = _font(28)
        small_font = _font(17)
        axis_font = _font(15)

        left, right, top, bottom = 90, 150, 70, 100
        plot_w = width - left - right
        plot_h = height - top - bottom
        highs = [r["high"] for r in clean]
        lows = [r["low"] for r in clean]
        closes = [r["close"] for r in clean]
        price_min = min(lows)
        price_max = max(highs)
        pad = max((price_max - price_min) * 0.08, price_max * 0.0005, 1e-9)
        price_min -= pad
        price_max += pad

        def x_at(i: int) -> int:
            return int(left + (i / max(1, len(clean) - 1)) * plot_w)

        def y_at(price: float) -> int:
            return int(top + (price_max - price) / (price_max - price_min) * plot_h)

        # Grid and labels.
        for frac in range(0, 6):
            y = int(top + (frac / 5) * plot_h)
            price = price_max - (frac / 5) * (price_max - price_min)
            draw.line((left, y, width - right, y), fill="#e5e7eb", width=1)
            draw.text((width - right + 10, y - 9), f"{price:.6g}", fill="#374151", font=axis_font)
        draw.line((left, top, left, height - bottom), fill="#111827", width=2)
        draw.line((left, height - bottom, width - right, height - bottom), fill="#111827", width=2)

        candle_gap = max(1, plot_w // max(1, len(clean)) // 5)
        body_half = max(2, plot_w // max(1, len(clean)) // 3)
        for i, row in enumerate(clean):
            x = x_at(i)
            y_open = y_at(row["open"])
            y_close = y_at(row["close"])
            y_high = y_at(row["high"])
            y_low = y_at(row["low"])
            up = row["close"] >= row["open"]
            fill = "#16a34a" if up else "#dc2626"
            draw.line((x, y_high, x, y_low), fill=fill, width=2)
            top_body = min(y_open, y_close)
            bot_body = max(y_open, y_close)
            if bot_body - top_body < 2:
                bot_body = top_body + 2
            draw.rectangle((x - body_half, top_body, x + body_half, bot_body), fill=fill, outline=fill)

        # Automatic support/resistance from the recent range.
        recent = clean[-min(30, len(clean)):]
        support = min(r["low"] for r in recent)
        resistance = max(r["high"] for r in recent)
        if show_support_resistance:
            for level, label in ((support, "Recent support"), (resistance, "Recent resistance")):
                yy = y_at(level)
                draw.line((left, yy, width - right, yy), fill="#6b7280", width=2)
                draw.text((left + 8, yy - 24), f"{label}: {level:.6g}", fill="#374151", font=small_font)

        # User-requested horizontal level.
        if horizontal_price is not None:
            yy = y_at(horizontal_price)
            draw.line((left, yy, width - right, yy), fill="#7c3aed", width=4)
            draw.text((left + 8, yy + 6), f"Horizontal level: {horizontal_price:.6g}", fill="#7c3aed", font=small_font)

        # Linear trendline over closes.
        slope, intercept = _linear_regression(closes)
        if show_trendline:
            y1 = y_at(intercept)
            y2 = y_at(slope * (len(closes) - 1) + intercept)
            draw.line((x_at(0), y1, x_at(len(closes) - 1), y2), fill="#2563eb", width=4)
            direction = "uptrend" if slope > 0 else "downtrend" if slope < 0 else "flat"
        else:
            direction = "disabled"

        title = f"{symbol.upper()} • {resolution} • {len(clean)} candles"
        draw.text((left, 20), title, fill="#111827", font=title_font)
        trend_pct = (slope * len(closes) / closes[0] * 100) if closes[0] else 0.0
        draw.text((left, height - 70), f"Trend: {direction} | regression slope: {trend_pct:.3f}% across chart", fill="#374151", font=small_font)
        draw.text((left, height - 45), f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}", fill="#6b7280", font=small_font)

        buf = io.BytesIO()
        image.save(buf, format="PNG")
        summary = {
            "symbol": symbol.upper(),
            "resolution": resolution,
            "candles": len(clean),
            "current_price": closes[-1],
            "support": support,
            "resistance": resistance,
            "horizontal_price": horizontal_price,
            "trend_direction": direction,
            "trend_slope_percent_over_chart": trend_pct,
        }
        return [Image(data=buf.getvalue(), format="png"), summary]

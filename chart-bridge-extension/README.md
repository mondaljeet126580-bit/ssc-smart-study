# Jeet Delta Chart Bridge

This extension connects the Delta Exchange web chart to the Render MCP chart bridge.

## Install

1. Open Chrome on a desktop computer and open `chrome://extensions`.
2. Enable **Developer mode**.
3. Choose **Load unpacked** and select this `chart-bridge-extension` folder.
4. Open the Delta Exchange web chart and keep the chart tab open.
5. Open the extension popup and keep the default bridge URL:
   `https://jeet-delta-mcp.onrender.com/chart-bridge`
6. If `CHART_BRIDGE_TOKEN` is enabled on Render, enter the same token in the popup and save it.
7. Refresh the Delta chart after installing or updating the extension.

## Native drawing confirmation

The extension uses a MAIN-world script to call the native TradingView widget's `activeChart().createShape()` when the page exposes that API. The bridge waits for a `draw_result` before reporting success. If the native chart API is unavailable, the request fails rather than claiming that a line was drawn.

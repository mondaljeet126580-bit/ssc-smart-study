# Jeet Delta Chart Bridge

This browser bridge connects the Delta Exchange web chart to the Render MCP server so a horizontal-line command can be executed on the currently open chart.

## Install

1. Use a Chromium browser that supports Manifest V3 extensions.
2. Open the extensions manager and enable Developer mode.
3. Load this `chart-bridge-extension` folder as an unpacked extension.
4. Open the Delta Exchange web chart and keep that tab open.
5. Open the extension popup and keep the default bridge URL:
   `https://jeet-delta-mcp.onrender.com/chart-bridge`
6. If Render has `CHART_BRIDGE_TOKEN` configured, enter the same token in the popup and save it.
7. Refresh the Delta chart tab after installing or updating the extension.

## Execution behavior

The bridge does not claim success from server-side storage. The Render bridge sends a command to the connected browser client and waits for a native chart drawing result. The page-side script then calls the exposed TradingView chart API `createShape()` with `shape: "horizontal_line"` and the exact requested price. Only a positive native result is reported as executed.

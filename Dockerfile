FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CHART_BRIDGE_URL=https://jeet-delta-mcp.onrender.com/chart-bridge

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py delta_client.py advanced_tools.py market_diagnostics.py bootstrap.py chart_bridge.py chart_command.py ./

ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn bootstrap:app --host 0.0.0.0 --port ${PORT:-8000}"]

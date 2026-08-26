from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from typing import Any
from urllib.parse import urlencode

import httpx


class DeltaAPIError(RuntimeError):
    pass


class DeltaClient:
    """Small, dependency-light Delta Exchange India REST client."""

    def __init__(self) -> None:
        self.base_url = os.getenv("DELTA_BASE_URL", "https://api.india.delta.exchange").rstrip("/")
        self.api_key = os.getenv("DELTA_API_KEY", "").strip()
        self.api_secret = os.getenv("DELTA_API_SECRET", "").strip()
        self.user_agent = os.getenv("DELTA_USER_AGENT", "jeet-delta-mcp/1.0")
        self.timeout = float(os.getenv("DELTA_HTTP_TIMEOUT", "30"))

    @property
    def has_credentials(self) -> bool:
        return bool(self.api_key and self.api_secret)

    def _auth_headers(self, method: str, path: str, query_string: str, body: str) -> dict[str, str]:
        if not self.has_credentials:
            raise DeltaAPIError("Delta API credentials are not configured on the server.")
        timestamp = str(int(time.time()))
        prehash = method.upper() + timestamp + path + query_string + body
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            prehash.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return {
            "api-key": self.api_key,
            "timestamp": timestamp,
            "signature": signature,
            "User-Agent": self.user_agent,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        authenticated: bool = False,
    ) -> dict[str, Any] | list[Any] | Any:
        params = {k: v for k, v in (params or {}).items() if v is not None and v != ""}
        query_string = urlencode(params, doseq=True)
        query_part = f"?{query_string}" if query_string else ""
        payload = json.dumps(body, separators=(",", ":"), ensure_ascii=False) if body is not None else ""
        headers = {"Accept": "application/json", "User-Agent": self.user_agent}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if authenticated:
            headers.update(self._auth_headers(method, path, query_part, payload))

        url = f"{self.base_url}{path}{query_part}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(method.upper(), url, content=payload, headers=headers)

        try:
            data = response.json()
        except Exception:
            data = {"status_code": response.status_code, "text": response.text[:2000]}

        if response.is_error:
            raise DeltaAPIError(f"Delta API HTTP {response.status_code}: {json.dumps(data, ensure_ascii=False)}")
        if isinstance(data, dict) and data.get("success") is False:
            raise DeltaAPIError(json.dumps(data, ensure_ascii=False))
        return data

    async def public(self, method: str, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self.request(method, path, params=params, authenticated=False)

    async def private(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> Any:
        return await self.request(method, path, params=params, body=body, authenticated=True)


client = DeltaClient()

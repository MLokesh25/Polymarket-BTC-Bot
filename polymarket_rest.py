from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import httpx

from config import APIConfig


class PolymarketRestError(RuntimeError):
    pass


@dataclass(slots=True)
class PolymarketRESTClient:
    config: APIConfig
    timeout_s: float = 15.0

    def __post_init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=self.timeout_s)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_active_btc_5m_markets(self) -> list[dict[str, Any]]:
        url = f"{self.config.gamma_base_url}/markets"
        params = {
            "active": "true",
            "limit": 200,
        }
        data = await self._get_json(url, params=params)
        items = data if isinstance(data, list) else data.get("data", [])
        out: list[dict[str, Any]] = []
        for item in items:
            question = str(item.get("question", ""))
            if "Bitcoin" in question and "5 Minutes" in question:
                out.append(item)
        return out

    async def get_market_by_slug(self, slug: str) -> dict[str, Any] | None:
        url = f"{self.config.gamma_base_url}/markets"
        data = await self._get_json(url, params={"slug": slug})
        items = data if isinstance(data, list) else data.get("data", [])
        return items[0] if items else None

    async def get_midpoint_price(self, token_id: str) -> Decimal | None:
        url = f"{self.config.clob_rest_base_url}/book"
        payload = await self._get_json(url, params={"token_id": token_id})
        bids = payload.get("bids", [])
        asks = payload.get("asks", [])
        if not bids or not asks:
            return None
        best_bid = Decimal(str(bids[0]["price"] if isinstance(bids[0], dict) else bids[0][0]))
        best_ask = Decimal(str(asks[0]["price"] if isinstance(asks[0], dict) else asks[0][0]))
        return (best_bid + best_ask) / Decimal("2")

    async def get_prices_history(
        self,
        token_id: str,
        interval: str = "1m",
        start_ts: int | None = None,
        end_ts: int | None = None,
    ) -> list[dict[str, Any]]:
        url = f"{self.config.prices_history_base_url}/prices-history"
        params: dict[str, Any] = {"token_id": token_id, "interval": interval}
        if start_ts is not None:
            params["startTs"] = start_ts
        if end_ts is not None:
            params["endTs"] = end_ts
        payload = await self._get_json(url, params=params)
        if isinstance(payload, list):
            return payload
        return payload.get("history", payload.get("data", []))

    async def _get_json(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any] | list[Any]:
        try:
            resp = await self._client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001 - normalized in one place
            raise PolymarketRestError(f"GET {url} failed: {exc}") from exc


def parse_time(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)

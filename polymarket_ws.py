from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass

import websockets
from websockets.client import WebSocketClientProtocol


@dataclass(slots=True)
class MarketWebSocket:
    url: str
    reconnect_initial_s: float = 1.0
    reconnect_max_s: float = 30.0

    async def stream_market(self, asset_ids: list[str]) -> AsyncIterator[dict]:
        backoff = self.reconnect_initial_s
        while True:
            try:
                async with websockets.connect(self.url, ping_interval=20, ping_timeout=20) as ws:
                    await self._subscribe(ws, asset_ids)
                    backoff = self.reconnect_initial_s
                    async for message in ws:
                        try:
                            payload = json.loads(message)
                        except json.JSONDecodeError:
                            continue
                        if isinstance(payload, dict):
                            yield payload
                        elif isinstance(payload, list):
                            for item in payload:
                                if isinstance(item, dict):
                                    yield item
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(backoff)
                backoff = min(self.reconnect_max_s, backoff * 2)

    async def _subscribe(self, ws: WebSocketClientProtocol, asset_ids: list[str]) -> None:
        msg = {
            "type": "subscribe",
            "channel": "market",
            "assets_ids": asset_ids,
            "asset_ids": asset_ids,
        }
        await ws.send(json.dumps(msg))

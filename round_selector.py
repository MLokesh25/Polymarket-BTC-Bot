from __future__ import annotations

from datetime import datetime, timezone

from models import MarketRound
from polymarket_rest import PolymarketRESTClient, parse_time


def _extract_asset_ids(market: dict) -> tuple[str | None, str | None]:
    outcomes = market.get("outcomes") or market.get("tokens") or []
    if isinstance(outcomes, str):
        return None, None

    up_asset: str | None = None
    down_asset: str | None = None

    for out in outcomes:
        if not isinstance(out, dict):
            continue
        name = str(out.get("outcome") or out.get("name") or "").upper()
        token_id = out.get("token_id") or out.get("asset_id") or out.get("id")
        if not token_id:
            continue
        token_str = str(token_id)
        if name == "YES" or "UP" in name:
            up_asset = token_str
        elif name == "NO" or "DOWN" in name:
            down_asset = token_str

    # Fallback for markets that encode tokens in "clobTokenIds" in the order [UP, DOWN]
    if (not up_asset or not down_asset) and market.get("clobTokenIds"):
        token_ids = market["clobTokenIds"]
        if isinstance(token_ids, list) and len(token_ids) >= 2:
            up_asset = up_asset or str(token_ids[0])
            down_asset = down_asset or str(token_ids[1])

    return up_asset, down_asset


async def detect_current_round(rest: PolymarketRESTClient) -> MarketRound:
    markets = await rest.get_active_btc_5m_markets()
    now = datetime.now(timezone.utc)

    candidates: list[MarketRound] = []
    for m in markets:
        up_asset_id, down_asset_id = _extract_asset_ids(m)
        if not up_asset_id or not down_asset_id:
            continue
        end_time = parse_time(m.get("endDate") or m.get("endTime") or m.get("closedTime"))
        if end_time <= now:
            continue

        candidates.append(
            MarketRound(
                market_id=str(m.get("id") or m.get("conditionId") or m.get("questionID") or ""),
                question=str(m.get("question") or ""),
                slug=str(m.get("slug") or ""),
                up_asset_id=up_asset_id,
                down_asset_id=down_asset_id,
                end_time=end_time,
                start_time=parse_time(m.get("startDate") or m.get("createdAt")),
            )
        )

    if not candidates:
        raise RuntimeError("No active Bitcoin 5 Minutes round with UP/DOWN asset IDs found")

    candidates.sort(key=lambda r: r.end_time)
    return candidates[0]

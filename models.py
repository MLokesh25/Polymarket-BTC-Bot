from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any


class Side(str, Enum):
    UP = "UP"
    DOWN = "DOWN"


@dataclass(slots=True)
class MarketRound:
    market_id: str
    question: str
    slug: str
    up_asset_id: str
    down_asset_id: str
    end_time: datetime
    start_time: datetime | None = None


@dataclass(slots=True)
class BookLevel:
    price: Decimal
    size: Decimal


@dataclass(slots=True)
class TopOfBook:
    best_bid: BookLevel | None = None
    best_ask: BookLevel | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def spread(self) -> Decimal | None:
        if not self.best_bid or not self.best_ask:
            return None
        return self.best_ask.price - self.best_bid.price


@dataclass(slots=True)
class AssetState:
    asset_id: str
    side: Side
    top_of_book: TopOfBook = field(default_factory=TopOfBook)
    last_trade_price: Decimal | None = None


@dataclass(slots=True)
class RoundState:
    round_meta: MarketRound
    up: AssetState
    down: AssetState
    chosen_side: Side
    stake_usd: Decimal
    opened_price: Decimal | None = None
    opened_at: datetime | None = None
    cashout_price: Decimal | None = None
    cashout_at: datetime | None = None
    settled_at: datetime | None = None
    winner: Side | None = None
    pnl: Decimal = Decimal("0")
    skipped_reason: str | None = None
    raw_events: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class StrategyStats:
    rounds: int = 0
    wins: int = 0
    losses: int = 0
    cashouts: int = 0
    cashouts_in_row: int = 0
    skipped: int = 0
    daily_pnl: Decimal = Decimal("0")


@dataclass(slots=True)
class PersistedRound:
    timestamp: str
    market_id: str
    question: str
    chosen_side: str
    winner: str | None
    opened_price: str | None
    cashout_price: str | None
    pnl: str
    skipped_reason: str | None

    @classmethod
    def from_round(cls, round_state: RoundState) -> "PersistedRound":
        return cls(
            timestamp=datetime.now(timezone.utc).isoformat(),
            market_id=round_state.round_meta.market_id,
            question=round_state.round_meta.question,
            chosen_side=round_state.chosen_side.value,
            winner=round_state.winner.value if round_state.winner else None,
            opened_price=str(round_state.opened_price) if round_state.opened_price is not None else None,
            cashout_price=str(round_state.cashout_price) if round_state.cashout_price is not None else None,
            pnl=str(round_state.pnl),
            skipped_reason=round_state.skipped_reason,
        )

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


@dataclass(frozen=True, slots=True)
class APIConfig:
    gamma_base_url: str = "https://gamma-api.polymarket.com"
    clob_rest_base_url: str = "https://clob.polymarket.com"
    prices_history_base_url: str = "https://clob.polymarket.com"
    ws_market_url: str = "wss://ws-subscriptions-clob.polymarket.com/ws/market"


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    start_side: str = "UP"
    stake_usd: Decimal = Decimal("2")
    block_size: int = 3
    cashout_threshold: Decimal = Decimal("0.20")
    daily_loss_limit: Decimal = Decimal("-10")
    max_losing_blocks_in_row: int = 2
    max_spread: Decimal = Decimal("0.04")
    min_top_book_size: Decimal = Decimal("50")
    min_seconds_to_expiry: int = 45


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    quote_poll_interval_s: float = 1.0
    summary_print_interval_s: float = 5.0
    ws_reconnect_initial_s: float = 1.0
    ws_reconnect_max_s: float = 30.0
    http_timeout_s: float = 15.0
    output_path: Path = Path("rounds.jsonl")
    warmup_history: bool = False
    mock_mode: bool = False


@dataclass(frozen=True, slots=True)
class AppConfig:
    api: APIConfig = APIConfig()
    strategy: StrategyConfig = StrategyConfig()
    runtime: RuntimeConfig = RuntimeConfig()


DEFAULT_CONFIG = AppConfig()

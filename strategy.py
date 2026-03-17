from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from config import StrategyConfig
from models import AssetState, RoundState, Side, StrategyStats


@dataclass(slots=True)
class StrategyDecision:
    open_position: bool
    skip_reason: str | None = None


@dataclass(slots=True)
class PaperStrategy:
    config: StrategyConfig
    next_side: Side = Side.UP

    def __post_init__(self) -> None:
        self.next_side = Side(self.config.start_side.upper())

    def decide_entry(self, up: AssetState, down: AssetState, expiry: datetime, stats: StrategyStats) -> StrategyDecision:
        now = datetime.now(timezone.utc)
        if stats.daily_pnl <= self.config.daily_loss_limit:
            return StrategyDecision(False, "daily_loss_limit_reached")
        if (expiry - now).total_seconds() < self.config.min_seconds_to_expiry:
            return StrategyDecision(False, "too_close_to_expiry")

        target = up if self.next_side is Side.UP else down
        book = target.top_of_book
        if not book.best_bid or not book.best_ask:
            return StrategyDecision(False, "no_top_of_book")

        spread = book.spread
        if spread is None or spread > self.config.max_spread:
            return StrategyDecision(False, "spread_too_wide")

        if book.best_bid.size < self.config.min_top_book_size and book.best_ask.size < self.config.min_top_book_size:
            return StrategyDecision(False, "insufficient_top_book_size")

        return StrategyDecision(True)

    def mark_entry(self, state: RoundState, chosen_asset: AssetState) -> None:
        ask = chosen_asset.top_of_book.best_ask
        state.opened_at = datetime.now(timezone.utc)
        state.opened_price = ask.price if ask else chosen_asset.last_trade_price

    def check_cashout(self, state: RoundState, chosen_asset: AssetState) -> bool:
        if state.opened_price is None:
            return False
        ref_price = chosen_asset.last_trade_price
        if ref_price is None and chosen_asset.top_of_book.best_bid:
            ref_price = chosen_asset.top_of_book.best_bid.price
        if ref_price is None:
            return False
        if ref_price < self.config.cashout_threshold:
            state.cashout_at = datetime.now(timezone.utc)
            state.cashout_price = ref_price
            state.pnl = (ref_price - state.opened_price) * (state.stake_usd / state.opened_price)
            return True
        return False

    def settle(self, state: RoundState, winner: Side) -> None:
        state.settled_at = datetime.now(timezone.utc)
        state.winner = winner
        if state.opened_price is None:
            state.pnl = Decimal("0")
            return

        qty = state.stake_usd / state.opened_price
        if state.cashout_price is None:
            state.pnl = qty * ((Decimal("1") if state.chosen_side == winner else Decimal("0")) - state.opened_price)

    def update_block_state(self, stats: StrategyStats) -> None:
        if stats.current_block_rounds < self.config.block_size:
            return

        stats.blocks_completed += 1
        if stats.current_block_wins >= 2:
            stats.losing_blocks_in_row = 0
        else:
            stats.losing_blocks_in_row += 1
            self.next_side = Side.DOWN if self.next_side is Side.UP else Side.UP

        stats.current_block_rounds = 0
        stats.current_block_wins = 0

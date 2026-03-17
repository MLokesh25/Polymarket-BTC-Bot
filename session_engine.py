from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from config import AppConfig
from metrics import render_summary, update_stats
from models import AssetState, BookLevel, MarketRound, PersistedRound, RoundState, Side, StrategyStats
from strategy import PaperStrategy


@dataclass(slots=True)
class SessionEngine:
    config: AppConfig

    async def run(self, max_rounds: int | None = None) -> None:
        strategy = PaperStrategy(self.config.strategy)
        stats = StrategyStats()

        rest: Any = None
        ws: Any = None
        if not self.config.runtime.mock_mode:
            try:
                from polymarket_rest import PolymarketRESTClient
                from polymarket_ws import MarketWebSocket
            except ModuleNotFoundError as exc:
                missing = exc.name or "dependency"
                raise SystemExit(
                    f"Missing required dependency '{missing}'. Install project requirements first: pip install -r requirements.txt"
                ) from exc

            rest = PolymarketRESTClient(self.config.api, timeout_s=self.config.runtime.http_timeout_s)
            ws = MarketWebSocket(
                self.config.api.ws_market_url,
                reconnect_initial_s=self.config.runtime.ws_reconnect_initial_s,
                reconnect_max_s=self.config.runtime.ws_reconnect_max_s,
            )

        try:
            rounds_completed = 0
            while True:
                if self.config.runtime.mock_mode:
                    state = await self._run_mock_one_round(strategy, stats)
                else:
                    state = await self._run_one_round(rest, ws, strategy, stats)
                update_stats(stats, state)
                strategy.update_block_state(stats)
                rounds_completed += 1
                self._append_round(state, self.config.runtime.output_path)
                print(render_summary(stats), flush=True)

                if max_rounds is not None and rounds_completed >= max_rounds:
                    print(f"Stopping session: max rounds ({max_rounds}) reached.")
                    break
                if stats.daily_pnl <= self.config.strategy.daily_loss_limit:
                    print("Stopping session: daily P&L loss limit reached.")
                    break
                if stats.losing_blocks_in_row >= self.config.strategy.max_losing_blocks_in_row:
                    print("Stopping session: 2 losing blocks in a row reached.")
                    break
        finally:
            if rest is not None:
                await rest.aclose()

    async def _run_one_round(self, rest: Any, ws: Any, strategy: PaperStrategy, stats: StrategyStats) -> RoundState:
        from round_selector import detect_current_round

        round_meta = await detect_current_round(rest)

        up_state = AssetState(asset_id=round_meta.up_asset_id, side=Side.UP)
        down_state = AssetState(asset_id=round_meta.down_asset_id, side=Side.DOWN)
        chosen_side = strategy.next_side
        state = RoundState(
            round_meta=round_meta,
            up=up_state,
            down=down_state,
            chosen_side=chosen_side,
            stake_usd=self.config.strategy.stake_usd,
        )

        if self.config.runtime.warmup_history:
            await self._warmup(rest, state)

        expiry = round_meta.end_time
        entry_done = False

        async for event in ws.stream_market([round_meta.up_asset_id, round_meta.down_asset_id]):
            state.raw_events.append(event)
            self._apply_event(up_state, down_state, event)

            if not entry_done:
                decision = strategy.decide_entry(up_state, down_state, expiry, stats)
                if decision.open_position:
                    chosen_asset = up_state if chosen_side is Side.UP else down_state
                    strategy.mark_entry(state, chosen_asset)
                    entry_done = True
                elif decision.skip_reason is not None:
                    state.skipped_reason = decision.skip_reason
                    if decision.skip_reason in {
                        "daily_loss_limit_reached",
                        "too_close_to_expiry",
                    }:
                        strategy.settle(state, winner=strategy.next_side)
                        return state

            if entry_done:
                chosen_asset = up_state if chosen_side is Side.UP else down_state
                if strategy.check_cashout(state, chosen_asset):
                    break

            if datetime.now(timezone.utc) >= expiry:
                break

        winner = self._infer_winner(up_state, down_state)
        strategy.settle(state, winner)
        return state

    async def _run_mock_one_round(self, strategy: PaperStrategy, stats: StrategyStats) -> RoundState:
        now = datetime.now(timezone.utc)
        round_meta = MarketRound(
            market_id=f"mock-{int(now.timestamp())}",
            question="Bitcoin Up or Down - 5 Minutes (MOCK)",
            slug="mock-btc-5m",
            up_asset_id="mock-up",
            down_asset_id="mock-down",
            start_time=now,
            end_time=now + timedelta(seconds=90),
        )
        up_state = AssetState(asset_id=round_meta.up_asset_id, side=Side.UP)
        down_state = AssetState(asset_id=round_meta.down_asset_id, side=Side.DOWN)

        up_state.top_of_book.best_bid = BookLevel(price=Decimal("0.50"), size=Decimal("120"))
        up_state.top_of_book.best_ask = BookLevel(price=Decimal("0.52"), size=Decimal("120"))
        down_state.top_of_book.best_bid = BookLevel(price=Decimal("0.48"), size=Decimal("120"))
        down_state.top_of_book.best_ask = BookLevel(price=Decimal("0.50"), size=Decimal("120"))

        state = RoundState(
            round_meta=round_meta,
            up=up_state,
            down=down_state,
            chosen_side=strategy.next_side,
            stake_usd=self.config.strategy.stake_usd,
        )

        decision = strategy.decide_entry(up_state, down_state, round_meta.end_time, stats)
        if not decision.open_position:
            state.skipped_reason = decision.skip_reason
            strategy.settle(state, winner=Side.UP)
            return state

        chosen_asset = up_state if state.chosen_side is Side.UP else down_state
        strategy.mark_entry(state, chosen_asset)

        await asyncio.sleep(0.01)
        chosen_asset.last_trade_price = Decimal("0.15")
        if not strategy.check_cashout(state, chosen_asset):
            up_state.last_trade_price = Decimal("0.78")
            down_state.last_trade_price = Decimal("0.22")

        winner = self._infer_winner(up_state, down_state)
        strategy.settle(state, winner)
        state.raw_events.append({"mode": "mock", "winner": winner.value})
        return state

    async def _warmup(self, rest: Any, state: RoundState) -> None:
        end_ts = int(datetime.now(timezone.utc).timestamp())
        start_ts = end_ts - 300
        for asset in (state.up, state.down):
            try:
                history = await rest.get_prices_history(asset.asset_id, interval="1m", start_ts=start_ts, end_ts=end_ts)
            except Exception:
                continue
            if history:
                price = history[-1].get("p") or history[-1].get("price")
                if price is not None:
                    asset.last_trade_price = Decimal(str(price))

    def _apply_event(self, up: AssetState, down: AssetState, event: dict[str, Any]) -> None:
        asset_id = str(event.get("asset_id") or event.get("assetId") or event.get("token_id") or event.get("market") or "")
        if asset_id not in {up.asset_id, down.asset_id}:
            return
        target = up if asset_id == up.asset_id else down

        bids = event.get("bids")
        asks = event.get("asks")
        if isinstance(bids, list) and bids:
            top_bid = bids[0]
            target.top_of_book.best_bid = BookLevel(
                price=Decimal(str(top_bid.get("price") if isinstance(top_bid, dict) else top_bid[0])),
                size=Decimal(str(top_bid.get("size") if isinstance(top_bid, dict) else top_bid[1])),
            )
            target.top_of_book.updated_at = datetime.now(timezone.utc)
        if isinstance(asks, list) and asks:
            top_ask = asks[0]
            target.top_of_book.best_ask = BookLevel(
                price=Decimal(str(top_ask.get("price") if isinstance(top_ask, dict) else top_ask[0])),
                size=Decimal(str(top_ask.get("size") if isinstance(top_ask, dict) else top_ask[1])),
            )
            target.top_of_book.updated_at = datetime.now(timezone.utc)

        price = event.get("price") or event.get("last_price")
        if price is not None:
            target.last_trade_price = Decimal(str(price))

    def _infer_winner(self, up: AssetState, down: AssetState) -> Side:
        up_ref = up.last_trade_price or (up.top_of_book.best_bid.price if up.top_of_book.best_bid else Decimal("0"))
        down_ref = down.last_trade_price or (down.top_of_book.best_bid.price if down.top_of_book.best_bid else Decimal("0"))
        return Side.UP if up_ref >= down_ref else Side.DOWN

    def _append_round(self, round_state: RoundState, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = PersistedRound.from_round(round_state)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(payload)) + "\n")

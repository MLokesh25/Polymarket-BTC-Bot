from __future__ import annotations

from decimal import Decimal

from models import RoundState, StrategyStats


def update_stats(stats: StrategyStats, round_state: RoundState) -> StrategyStats:
    stats.rounds += 1
    stats.daily_pnl += round_state.pnl

    if round_state.skipped_reason:
        stats.skipped += 1
        return stats

    if round_state.cashout_price is not None:
        stats.cashouts += 1

    if round_state.winner and round_state.chosen_side == round_state.winner and round_state.pnl > Decimal("0"):
        stats.wins += 1
        stats.current_block_wins += 1
    elif round_state.winner:
        stats.losses += 1

    stats.current_block_rounds += 1
    return stats


def render_summary(stats: StrategyStats) -> str:
    return (
        "\n=== Paper Session Summary ===\n"
        f"Rounds         : {stats.rounds}\n"
        f"Wins/Losses    : {stats.wins}/{stats.losses}\n"
        f"Cashouts       : {stats.cashouts}\n"
        f"Skipped        : {stats.skipped}\n"
        f"Blocks         : {stats.blocks_completed} (current {stats.current_block_rounds}/3, wins {stats.current_block_wins})\n"
        f"Losing blocks  : {stats.losing_blocks_in_row} in a row\n"
        f"Daily P&L ($)  : {stats.daily_pnl.quantize(Decimal('0.0001'))}\n"
    )

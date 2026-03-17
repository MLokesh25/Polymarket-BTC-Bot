from __future__ import annotations

import argparse
import asyncio
from dataclasses import replace
from pathlib import Path

from config import DEFAULT_CONFIG
from session_engine import SessionEngine


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Polymarket BTC 5-minute paper strategy")
    parser.add_argument("--warmup-history", action="store_true", help="Pull recent price history before streaming")
    parser.add_argument("--output", default=None, help="JSONL output path")
    parser.add_argument("--max-rounds", type=int, default=None, help="Optional max number of rounds to simulate")
    parser.add_argument("--mock", action="store_true", help="Run an offline mock stream (no network dependencies)")
    return parser.parse_args()


async def amain() -> None:
    args = parse_args()
    runtime_cfg = DEFAULT_CONFIG.runtime
    if args.warmup_history:
        runtime_cfg = replace(runtime_cfg, warmup_history=True)
    if args.output:
        runtime_cfg = replace(runtime_cfg, output_path=Path(args.output))
    if args.mock:
        runtime_cfg = replace(runtime_cfg, mock_mode=True)

    cfg = replace(DEFAULT_CONFIG, runtime=runtime_cfg)
    engine = SessionEngine(cfg)
    await engine.run(max_rounds=args.max_rounds)


if __name__ == "__main__":
    asyncio.run(amain())

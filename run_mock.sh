#!/usr/bin/env bash
set -euo pipefail

# Optional first arg: number of rounds (default 5)
ROUNDS="${1:-5}"

python main.py --mock --max-rounds "${ROUNDS}" --output rounds.mock.jsonl

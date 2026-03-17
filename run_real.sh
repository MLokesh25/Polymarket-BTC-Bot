#!/usr/bin/env bash
set -euo pipefail

# Optional first arg: number of rounds (default 3)
ROUNDS="${1:-3}"

python -m pip install -r requirements.txt
python main.py --max-rounds "${ROUNDS}" --output rounds.jsonl

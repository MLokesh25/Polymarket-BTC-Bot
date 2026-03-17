# Polymarket BTC 5-Minute Paper Bot

Async Python paper-testing bot for Polymarket BTC 5-minute rounds.

## Quick start

### 1) Offline mock run (works without network dependencies)
```bash
./run_mock.sh
```

Or directly:
```bash
python main.py --mock --max-rounds 5 --output rounds.mock.jsonl
```

### 2) Real mode
```bash
./run_real.sh
```

Or directly:
```bash
python -m pip install -r requirements.txt
python main.py --max-rounds 3 --output rounds.jsonl
```

## CLI options
- `--warmup-history`: fetch short price history warmup.
- `--output <path>`: JSONL persistence path.
- `--max-rounds <n>`: bounded run count.
- `--mock`: run deterministic offline simulation.

## Notes
- Uses `Decimal` for price math.
- Streams from Polymarket market WS in real mode.
- Persists each simulated round as JSONL and prints running summary.

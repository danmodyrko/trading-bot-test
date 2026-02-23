# Verification Checklist

## Commands
- Unit tests:
  - `cd trading_bot_dan_v1 && pytest -q`
- Headless smoke test:
  - `cd trading_bot_dan_v1 && python -m danbot.main --headless`
- Run desktop app (manual verification):
  - `cd trading_bot_dan_v1 && python -m danbot.main`

## Runtime validations
1. **Kill switch:** engage from UI, verify new entries blocked and kill event logged.
2. **Risk limits:** lower `max_positions`/`max_daily_loss_pct` and confirm `BLOCKED` reason in event timeline + JSONL.
3. **Reconnect:** simulate ws interruption, verify reconnect/stale events (`WS_RECONNECT`, `WS_RESTART`).
4. **Snapshot persistence:** confirm `data/runtime_snapshot.json` updates periodically.
5. **Trade journal:** confirm `data/trade_journal.csv` appends completed-trade rows.

## Config defaults changed
- Added risk keys:
  - `max_positions_per_symbol`
  - `max_exposure_per_symbol`
  - `max_account_exposure`
  - `max_consecutive_losses`
  - `loss_cooldown_seconds`
  - `include_unrealized_pnl`
- Added execution keys:
  - `max_retry_attempts`
  - `retry_base_delay_s`
- Added storage keys:
  - `snapshots_path`
  - `trade_journal_path`

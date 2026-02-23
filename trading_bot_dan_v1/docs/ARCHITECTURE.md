# Current Architecture

## Stack and entrypoints
- **Desktop GUI framework:** PySide6 (Qt Widgets), defined in `danbot/ui/app.py` and widget modules.
- **Entrypoint:** `danbot/main.py` (`main()` launches UI by default, `--headless` runs simulated loop).

## Main modules
- `danbot/ui/*`: dashboard, settings, timeline/log widgets, engine worker thread.
- `danbot/strategy/*`: signal strategy, risk rules, execution/slippage logic.
- `danbot/exchange/*`: Binance REST + websocket clients, adapters, paper simulator.
- `danbot/storage/*`: sqlite lifecycle/event storage, exports, runtime snapshots/journal.
- `danbot/core/*`: config loading, structured event bus, logging utilities.

## Data flow
1. **Market data** is received from exchange feed/simulated ticks (`TickFeatureEngine`).
2. **Signal generation** via `ReversalStrategy.evaluate(...)` and spike classifier.
3. **Decision + filters** run through `ExecutionEngine` (spread/slippage + Binance filters + risk guardrails).
4. **Order execution** via one gateway (`ExecutionEngine.place_order`) and submit function (paper/real).
5. **Position/risk updates** are applied in `RiskManager` and reflected in snapshots.
6. **UI + logs** update through `EventBus` JSONL and the timeline panel (`LiveLogPanel`).

## State storage
- **In-memory:** runtime risk state, idempotency cache, live event buffer.
- **On disk:**
  - sqlite db (`storage.sqlite_path`)
  - structured event JSONL (`logs/events.jsonl`)
  - runtime snapshot JSON (`storage.snapshots_path`, atomic write)
  - trade journal CSV (`storage.trade_journal_path`)
  - UI app state JSON (`storage.app_state_path`)

# Implementation Roadmap

1. **Recon and baseline docs**
   - map framework, entrypoints, exchange, ws, logging paths
   - write `docs/ARCHITECTURE.md`
2. **Risk guardrails**
   - extend `RiskManager` for position/exposure/loss/cooldown/kill switch controls
   - enforce all orders through one execution gateway
   - wire new risk defaults into config
3. **Execution quality/idempotency**
   - implement `ExecutionEngine.place_order(...)` with:
     - binance-style qty/price normalization
     - spread/slippage checks
     - retry/backoff+jitter
     - idempotency dedupe cache
     - timestamp tracing (`signal/decision/send/ack/fill`)
4. **Reliability and persistence**
   - websocket supervisor with stale detection/restart hooks
   - periodic atomic state snapshots
5. **Observability**
   - structured JSONL event schema with category/correlation ID/payload
   - completed-trade journal CSV output
   - live event timeline UX improvements (copy selected/all)
6. **UI restyle**
   - central modern light theme (white cards, subtle dividers, clear hierarchy)
   - apply styling across widgets/dialogs without changing desktop stack
7. **Verification and docs**
   - add `docs/VERIFICATION.md`
   - run tests + headless smoke + app launch validation steps

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Literal

import tomli as tomllib
from pydantic import BaseModel, Field, ValidationError


class Mode(str, Enum):
    DEMO = "DEMO"
    REAL = "REAL"


class RiskConfig(BaseModel):
    max_daily_loss_pct: float = 3.0
    max_trade_risk_pct: float = 0.5
    max_positions: int = 3
    max_leverage: int = 5
    max_notional_per_trade: float = 250.0
    cooldown_seconds: int = 45


class StrategyConfig(BaseModel):
    impulse_threshold_pct: float = 3.0
    impulse_window_seconds: int = 60
    volume_zscore_threshold: float = 2.0
    trade_rate_burst_threshold: float = 8.0
    exhaustion_ratio_threshold: float = 0.4
    exhaustion_confidence_threshold: float = 0.55
    vol_kill_threshold: float = 0.02
    vol_cooldown_seconds: int = 30
    regime_filter_enabled: bool = True
    trend_strength_threshold: float = 1.4
    retrace_target_pct: tuple[float, float, float] = (0.3, 0.5, 0.6)
    stop_loss_model: Literal["ATR", "fixed"] = "ATR"
    take_profit_model: Literal["dynamic_retrace", "fixed"] = "dynamic_retrace"
    hard_time_stop_seconds: int = 120


class ExecutionConfig(BaseModel):
    order_type: Literal["MARKET", "LIMIT"] = "MARKET"
    max_slippage_bps: float = 8.0
    edge_safety_factor: float = 0.7
    min_orderbook_depth: float = 50000
    spread_guard_bps: float = 15.0
    dry_run: bool = True
    enable_real_orders: bool = False


class UiConfig(BaseModel):
    dark_mode: bool = True
    refresh_ms: int = 200
    sound_notifications: bool = True


class StorageConfig(BaseModel):
    sqlite_path: Path = Path("data/danbot.sqlite3")
    csv_dir: Path = Path("data/exports")
    app_state_path: Path = Path("data/app_state.json")


class Endpoints(BaseModel):
    ws_demo: str
    ws_real: str
    rest_demo: str
    rest_real: str


class APIConfig(BaseModel):
    demo_key_env: str = "BINANCE_TESTNET_API_KEY"
    demo_secret_env: str = "BINANCE_TESTNET_API_SECRET"
    real_key_env: str = "BINANCE_API_KEY"
    real_secret_env: str = "BINANCE_API_SECRET"


class AppConfig(BaseModel):
    mode: Mode = Mode.DEMO
    exchange: str = "binance-futures-usdtm"
    symbols: list[str] = Field(default_factory=lambda: ["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    auto_discover_symbols: bool = True
    min_quote_volume_24h: float = 5_000_000
    min_trade_rate_baseline: float = 1.0
    max_symbols_active: int = 100
    endpoints: Endpoints
    risk: RiskConfig = Field(default_factory=RiskConfig)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    ui: UiConfig = Field(default_factory=UiConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    api: APIConfig = Field(default_factory=APIConfig)


class AppState(BaseModel):
    mode: Mode = Mode.DEMO
    dry_run: bool = True
    real_confirm_required: bool = True
    kill_switch_engaged: bool = False
    order_value_usdt: float = 250.0
    max_leverage: int = 5
    max_positions_open: int = 3
    max_daily_loss_pct: float = 3.0
    cooldown_seconds_per_symbol: int = 45
    spread_guard_bps: float = 15.0
    max_slippage_bps: float = 8.0
    volatility_kill_switch_threshold: float = 0.02
    regime_filter_enabled: bool = True
    regime_threshold: float = 1.4
    max_trades_per_hour: int = 20
    impulse_threshold_pct: float = 3.0
    impulse_window_seconds: int = 60
    exhaustion_ratio_threshold: float = 0.4
    tp1_pct: float = 0.3
    tp2_pct: float = 0.5
    tp3_pct: float = 0.6
    time_stop_seconds: int = 120
    stop_model: Literal["ATR", "fixed"] = "ATR"
    spike_classifier_enabled: bool = True
    ml_gate_enabled: bool = False
    ml_threshold: float = 0.6
    ml_model_path: str = ""


def _load_env_file(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        entry = line.strip()
        if not entry or entry.startswith("#") or "=" not in entry:
            continue
        key, value = entry.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def load_config(path: Path | str = "config.toml") -> AppConfig:
    _load_env_file()
    config_path = Path(path)
    with config_path.open("rb") as f:
        data = tomllib.load(f)
    try:
        return AppConfig.model_validate(data)
    except ValidationError as exc:
        raise RuntimeError(f"Invalid config at {config_path}: {exc}") from exc


def load_app_state(path: Path) -> AppState:
    if not path.exists():
        return AppState()
    import json

    return AppState.model_validate(json.loads(path.read_text(encoding="utf-8")))


def save_app_state(path: Path, state: AppState) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state.model_dump(mode="json"), indent=2), encoding="utf-8")

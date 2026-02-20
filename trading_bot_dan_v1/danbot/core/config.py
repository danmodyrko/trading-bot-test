from __future__ import annotations

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
    exhaustion_ratio_threshold: float = 0.4
    retrace_target_pct: tuple[float, float] = (0.3, 0.6)
    stop_loss_model: Literal["ATR", "fixed"] = "ATR"
    take_profit_model: Literal["dynamic_retrace", "fixed"] = "dynamic_retrace"
    hard_time_stop_seconds: int = 120


class ExecutionConfig(BaseModel):
    order_type: Literal["MARKET", "LIMIT"] = "MARKET"
    max_slippage_bps: float = 8.0
    min_orderbook_depth: float = 50000
    spread_guard_bps: float = 15.0
    dry_run: bool = True


class UiConfig(BaseModel):
    dark_mode: bool = True
    refresh_ms: int = 200
    sound_notifications: bool = True


class StorageConfig(BaseModel):
    sqlite_path: Path = Path("data/danbot.sqlite3")
    csv_dir: Path = Path("data/exports")


class Endpoints(BaseModel):
    ws_demo: str
    ws_real: str
    rest_demo: str
    rest_real: str


class AppConfig(BaseModel):
    mode: Mode = Mode.DEMO
    exchange: str = "binance-futures-usdtm"
    symbols: list[str] = Field(default_factory=lambda: ["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    endpoints: Endpoints
    risk: RiskConfig = Field(default_factory=RiskConfig)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    ui: UiConfig = Field(default_factory=UiConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)


def load_config(path: Path | str = "config.toml") -> AppConfig:
    config_path = Path(path)
    with config_path.open("rb") as f:
        data = tomllib.load(f)
    try:
        return AppConfig.model_validate(data)
    except ValidationError as exc:
        raise RuntimeError(f"Invalid config at {config_path}: {exc}") from exc

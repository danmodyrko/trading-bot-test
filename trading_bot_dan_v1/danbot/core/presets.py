from __future__ import annotations

from typing import Any

PRESET_ORDER = ["SAFE", "MEDIUM", "AGGRESSIVE", "INSANE"]

PRESETS: dict[str, dict[str, Any]] = {
    "SAFE": {
        "dry_run": True,
        "order_value_pct_balance": 0.005,
        "max_leverage": 3,
        "max_positions": 1,
        "max_daily_loss_pct": 0.01,
        "cooldown_seconds": 180,
        "max_trades_per_hour": 6,
        "spread_guard_bps": 2.0,
        "max_slippage_bps": 8.0,
        "edge_gate_factor": 0.55,
        "vol_10s_threshold": 0.004,
        "regime_filter_enabled": True,
        "trend_strength_threshold": 0.18,
        "time_stop_seconds": 90,
        "tp_profile": [0.30, 0.50],
        "impulse_threshold_pct": 3.5,
        "impulse_window_seconds": 60,
        "exhaustion_ratio_threshold": 0.35,
        "ml_gate_enabled": False,
    },
    "MEDIUM": {
        "dry_run": True,
        "order_value_pct_balance": 0.01,
        "max_leverage": 5,
        "max_positions": 2,
        "max_daily_loss_pct": 0.02,
        "cooldown_seconds": 120,
        "max_trades_per_hour": 10,
        "spread_guard_bps": 3.0,
        "max_slippage_bps": 12.0,
        "edge_gate_factor": 0.65,
        "vol_10s_threshold": 0.006,
        "regime_filter_enabled": True,
        "trend_strength_threshold": 0.25,
        "time_stop_seconds": 120,
        "tp_profile": [0.30, 0.50, 0.60],
        "impulse_threshold_pct": 3.0,
        "impulse_window_seconds": 60,
        "exhaustion_ratio_threshold": 0.40,
        "ml_gate_enabled": False,
    },
    "AGGRESSIVE": {
        "dry_run": True,
        "order_value_pct_balance": 0.02,
        "max_leverage": 8,
        "max_positions": 3,
        "max_daily_loss_pct": 0.035,
        "cooldown_seconds": 60,
        "max_trades_per_hour": 16,
        "spread_guard_bps": 4.5,
        "max_slippage_bps": 18.0,
        "edge_gate_factor": 0.75,
        "vol_10s_threshold": 0.009,
        "regime_filter_enabled": True,
        "trend_strength_threshold": 0.35,
        "time_stop_seconds": 150,
        "tp_profile": [0.25, 0.40, 0.55, 0.65],
        "impulse_threshold_pct": 2.5,
        "impulse_window_seconds": 60,
        "exhaustion_ratio_threshold": 0.45,
        "ml_gate_enabled": False,
    },
    "INSANE": {
        "dry_run": True,
        "order_value_pct_balance": 0.04,
        "max_leverage": 15,
        "max_positions": 5,
        "max_daily_loss_pct": 0.06,
        "cooldown_seconds": 20,
        "max_trades_per_hour": 30,
        "spread_guard_bps": 8.0,
        "max_slippage_bps": 35.0,
        "edge_gate_factor": 0.90,
        "vol_10s_threshold": 0.015,
        "regime_filter_enabled": True,
        "trend_strength_threshold": 0.50,
        "time_stop_seconds": 180,
        "tp_profile": [0.20, 0.35, 0.50, 0.65],
        "impulse_threshold_pct": 2.0,
        "impulse_window_seconds": 60,
        "exhaustion_ratio_threshold": 0.50,
        "ml_gate_enabled": False,
    },
}

PRESET_FIELDS = tuple(PRESETS["SAFE"].keys())


def apply_preset(settings_obj, preset_name: str):
    updates = PRESETS[preset_name]
    for field, value in updates.items():
        setattr(settings_obj, field, value)
    return settings_obj


def detect_profile(settings_obj) -> str:
    current = {field: getattr(settings_obj, field) for field in PRESET_FIELDS}
    for preset_name in PRESET_ORDER:
        if current == PRESETS[preset_name]:
            return preset_name
    return "CUSTOM"

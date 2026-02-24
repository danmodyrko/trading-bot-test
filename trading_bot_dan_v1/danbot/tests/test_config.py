from danbot.core.config import AppConfig


def test_strategy_retrace_target_pct_accepts_four_levels():
    cfg = AppConfig.model_validate(
        {
            "endpoints": {
                "ws_demo": "wss://demo.example/ws",
                "ws_real": "wss://real.example/ws",
                "rest_demo": "https://demo.example/api",
                "rest_real": "https://real.example/api",
            },
            "strategy": {"retrace_target_pct": [0.2, 0.35, 0.5, 0.65]},
        }
    )

    assert cfg.strategy.retrace_target_pct == (0.2, 0.35, 0.5, 0.65)

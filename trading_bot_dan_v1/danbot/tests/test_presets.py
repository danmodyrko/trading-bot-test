from danbot.core.config import AppState
from danbot.core.presets import PRESETS, PRESET_ORDER, apply_preset, detect_profile


def test_detect_profile_returns_expected_presets():
    state = AppState()
    for preset in PRESET_ORDER:
        apply_preset(state, preset)
        assert detect_profile(state) == preset
        assert state.max_leverage == PRESETS[preset]["max_leverage"]


def test_detect_profile_switches_to_custom_after_single_change():
    state = AppState()
    apply_preset(state, "MEDIUM")
    assert detect_profile(state) == "MEDIUM"
    state.max_positions += 1
    assert detect_profile(state) == "CUSTOM"

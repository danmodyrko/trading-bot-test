from danbot.strategy.state_machine import MarketState, ProbabilisticStateMachine


def test_probabilistic_state_machine_reaches_exhaustion():
    sm = ProbabilisticStateMachine()
    conf = sm.update(impulse_score=0.8, impulse_detected=True, exhaustion_detected=False, exhaustion_ratio=0.9, wick_proxy=0.0005, structure_confirmed=False)
    assert conf[MarketState.IMPULSE] > 0
    conf = sm.update(impulse_score=0.2, impulse_detected=False, exhaustion_detected=True, exhaustion_ratio=0.2, wick_proxy=0.002, structure_confirmed=True)
    assert conf[MarketState.EXHAUSTION] > 0

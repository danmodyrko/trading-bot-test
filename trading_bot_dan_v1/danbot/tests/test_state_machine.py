from danbot.strategy.state_machine import ImpulseLifecycleMachine, MarketState


def test_state_machine_lifecycle():
    sm = ImpulseLifecycleMachine()
    assert sm.state == MarketState.BUILDUP
    sm.transition(impulse=True, climax=False, exhaustion=False, rebalance=False)
    assert sm.state == MarketState.IMPULSE
    sm.transition(impulse=True, climax=True, exhaustion=False, rebalance=False)
    assert sm.state == MarketState.CLIMAX
    sm.transition(impulse=False, climax=False, exhaustion=True, rebalance=False)
    assert sm.state == MarketState.EXHAUSTION

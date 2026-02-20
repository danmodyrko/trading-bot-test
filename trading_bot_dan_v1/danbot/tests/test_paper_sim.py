from danbot.exchange.models import OrderRequest, Side
from danbot.exchange.paper_sim import PaperSimulator


def test_paper_sim_updates_position():
    sim = PaperSimulator()
    fill = sim.place_order(OrderRequest("BTCUSDT", Side.BUY, 0.1), mark_price=100)
    assert fill.price > 100
    assert sim.positions["BTCUSDT"].qty == 0.1

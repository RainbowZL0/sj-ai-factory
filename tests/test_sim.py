import pytest

from sjfactory import STOP, FactorySim, load_scenario
from sjfactory.spec import scenario_from_dict


# One machine that turns A into B; B can be sold
TINY = {
    "horizon": 20,
    "initial_cash": 100,
    "energy_price": 2.0,
    "rent_per_second": 1.0,
    "materials": {
        "A": {"initial_stock": 3},
        "B": {"sell_price": 10, "storage_cost": 0.5, "shortfall_penalty": 4},
    },
    "recipes": {
        "Make": {"category": "M", "cycle_time": 2, "power_kw": 3600, "inputs": {"A": 1}, "outputs": {"B": 1}},
        "Idle": {"category": "M", "cycle_time": 1, "power_kw": 0, "outputs": {}},
    },
    "machines": [{"category": "M", "recipe": "Make"}],
    "orders": {"fixed": [{"product": "B", "quantity": 3, "due_time": 5}]},
}


def tiny_sim():
    sim = FactorySim(scenario_from_dict(TINY))
    sim.reset(seed=0)
    return sim


def test_batch_takes_cycle_time_and_uses_energy():
    sim = tiny_sim()
    r1 = sim.step()
    assert sim.state.remaining[0] == 1
    assert sim.state.stock.tolist() == [2, 0]  # inputs are taken at the start
    assert r1.energy_kwh == pytest.approx(1.0)  # 3600 kW × 1 s
    assert r1.energy_cost == pytest.approx(2.0)
    sim.step()
    assert sim.state.stock.tolist() == [2, 1]  # output reaches stock at the end of second 2
    assert sim.state.remaining[0] == 0


def test_order_partial_delivery_and_penalty():
    sim = tiny_sim()
    reports = [sim.step() for _ in range(5)]
    # by the end of second 5 there are 2 B; the order wants 3
    d = reports[-1].deliveries[0]
    assert d.shipped == 2
    assert d.revenue == 20
    assert d.penalty == 4
    assert sim.state.stock[1] == 0


def test_cash_is_sum_of_step_changes():
    sim = tiny_sim()
    total = sum(sim.step().cash_change for _ in range(20))
    assert sim.state.cash == pytest.approx(100 + total)
    assert sim.done


def test_cannot_change_recipe_while_running():
    sim = tiny_sim()
    sim.step()
    with pytest.raises(ValueError, match="is busy"):
        sim.step({0: 1})


def test_stop_halts_production():
    sim = tiny_sim()
    sim.step({0: STOP})
    assert sim.state.remaining[0] == 0
    assert sim.state.stock.tolist() == [3, 0]


def test_unknown_material_rejected():
    bad = {**TINY, "recipes": {"X": {"category": "M", "cycle_time": 1, "inputs": {"Nope": 1}}}}
    with pytest.raises(ValueError, match="unknown material"):
        scenario_from_dict(bad)


def test_default_scenario_loads_with_old_machine_ids():
    sc = load_scenario()
    ids = [m.id for m in sc.machines]
    assert len(ids) == 25
    assert ids[0] == "CASTER-01" and ids[-1] == "ASSEMBLER-05"
    assert sc.machines[ids.index("CONSTRUCTOR-07")].initial_recipe == "Bar_2_Screw"


def test_same_seed_same_orders():
    a, b = FactorySim(load_scenario()), FactorySim(load_scenario())
    assert a.reset(seed=7).orders == b.reset(seed=7).orders
    assert a.reset(seed=7).orders != a.reset(seed=8).orders

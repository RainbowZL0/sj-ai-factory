import json

import numpy as np
import pytest
from gymnasium.utils.env_checker import check_env

from sjfactory import STOP, FactoryEnv, FactorySim, load_scenario
from sjfactory.env import NO_CHANGE, allocate
from sjfactory.policies import KeepPolicy, RandomPolicy
from sjfactory.recorder import Recorder
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


def test_env_passes_gymnasium_checks():
    check_env(FactoryEnv(horizon=50), skip_render_check=True)


def test_allocate_splits_machines_in_proportion():
    assert allocate(np.array([1, 1, 0]), 5).tolist() == [3, 2, 0]
    assert allocate(np.array([6, 4, 2, 2, 0]), 14).tolist() == [6, 4, 2, 2, 0]
    assert allocate(np.array([0, 0, 7]), 3).tolist() == [0, 0, 3]


def test_recipes_that_can_never_run_get_no_slot():
    env = FactoryEnv(horizon=50)
    sc = env.sim.scenario
    assert "IronOre" not in sc.obtainable and "Motor" in sc.obtainable
    assert [k.category for k in env.kinds] == ["Constructor", "Assembler"]  # every caster recipe needs ore
    assert env.action_space.nvec.tolist() == [15] * 5 + [6] * 5


def test_plan_switches_idle_machines_only_and_keeps_the_rest():
    env = FactoryEnv(horizon=400, ticks_per_action=1)
    env.reset(seed=0)
    start = env.start_action()
    assert env.switches() == {}  # no plan yet
    env.step(start)  # planning the starting allocation changes nothing
    assert env.switches() == {}
    assert env.start_action().tolist() == start.tolist()  # from the scenario, not from the current state

    sc = env.sim.scenario
    constructors = env.kinds[0]
    plate = constructors.recipes.index(sc.recipe_index["Ingot_2_Plate"])
    bar = constructors.recipes.index(sc.recipe_index["Ingot_2_Bar"])
    action = start.copy()
    action[constructors.slots.start + plate] = 2
    action[constructors.slots.start + bar] = 4
    for _ in range(60):
        env.step(action)
        for m in env.switches():
            assert env.sim.idle[m]
    assert env._current_counts(constructors).tolist() == env.plan[0].tolist()
    assert env.plan[0][plate] == 2 and env.plan[0][bar] == 4

    env.step(np.zeros_like(action))  # all zeros: keep the plan
    assert env.plan[0][plate] == 2


def test_changeover_delays_the_new_recipe():
    sim = FactorySim(scenario_from_dict({**TINY, "changeover_time": 3}))
    sim.reset(seed=0)
    idle = sim.scenario.recipe_index["Idle"]
    sim.step({0: idle})
    assert sim.state.setup[0] == 2 and not sim.idle[0]
    with pytest.raises(ValueError, match="is busy"):
        sim.step({0: 0})
    reports = [sim.step() for _ in range(2)]
    assert sim.idle[0]  # 3 seconds of changeover have passed, making nothing
    assert all(r.running[0] == STOP for r in reports)
    assert sim.step().running[0] == idle  # starts on the next second
    while not sim.idle[0]:
        sim.step()
    # Stopping needs no changeover; switching back to the same recipe after a stop does
    sim.step({0: STOP})
    assert sim.state.setup[0] == 0
    sim.step({0: idle})
    assert sim.state.setup[0] == 2


def test_reward_matches_cash_change():
    env = FactoryEnv(horizon=200, ticks_per_action=7, reward_scale=1.0)
    _, info = env.reset(seed=1)
    cash0, total, done = info["cash"], 0.0, False
    policy = RandomPolicy(env.action_space, change_prob=0.3, seed=0)
    obs = None
    while not done:
        obs, r, done, _, info = env.step(policy.act(obs, env.action_masks()))
        total += r
    assert info["clock"] == 200
    assert info["cash"] == pytest.approx(cash0 + total)


def test_recorder_and_save(tmp_path):
    env = FactoryEnv(horizon=300)
    with Recorder(env.sim) as rec:
        env.reset(seed=0)
        policy = KeepPolicy(env.action_space)
        done = False
        while not done:
            _, _, done, _, _ = env.step(policy.act(None, None))
    assert len(rec.reports) == 300
    assert env.sim.listeners == []
    rec.save(tmp_path)
    assert {p.name for p in tmp_path.iterdir()} >= {
        "history.xlsx", "dashboard.png", "gantt.png", "material_flow.png"
    }

def test_web_pages(tmp_path):
    from sjfactory import web
    from sjfactory.evaluate import baseline_policy, run_episode

    env = FactoryEnv(horizon=200, ticks_per_action=5)
    run = tmp_path / "0101_000000-keep"
    run.mkdir()
    rec = run_episode(env, baseline_policy("keep", env), seed=0)
    ref = run_episode(env, baseline_policy("random", env), seed=0)
    (run / "summary.json").write_text(json.dumps(rec.summary()), encoding="utf-8")
    assert "Cash over time" in web.write_report(run, rec, "keep", {"random": ref}).read_text(encoding="utf-8")

    # A training page from the files the training monitor writes, before any statistics exist
    web.write_config(run, steps=1000, initial_cash=1000)
    (run / "eval.csv").write_text(
        "step,mode,seed,profit,fill_rate,busy,revenue,penalty\n0,fixed,1,5,0.1,0.5,10,0\n0,sampled,1,7,0.2,0.5,12,0\n",
        encoding="utf-8",
    )
    page = web.write_training_page(run).read_text(encoding="utf-8")
    assert 'http-equiv="refresh"' in page  # still running, so it reloads itself

    index = web.write_index(tmp_path).read_text(encoding="utf-8")
    assert run.name in index
    assert (tmp_path / "plotly.min.js").exists()

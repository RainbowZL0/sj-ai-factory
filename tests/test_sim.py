import json

import numpy as np
import pytest
from gymnasium.utils.env_checker import check_env

from sjfactory import STOP, FactoryEnv, FactorySim, load_scenario
from sjfactory.env import NO_CHANGE
from sjfactory.policies import KeepPolicy, RandomPolicy
from sjfactory.recorder import Recorder
from sjfactory.spec import PROJECT_ROOT, scenario_from_dict

FACTORY = PROJECT_ROOT / "scenarios" / "large" / "default.yaml"  # the large factory most tests were written for

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
    sc = load_scenario(FACTORY)
    ids = [m.id for m in sc.machines]
    assert len(ids) == 25
    assert ids[0] == "CASTER-01" and ids[-1] == "ASSEMBLER-05"
    assert sc.machines[ids.index("CONSTRUCTOR-07")].initial_recipe == "Bar_2_Screw"


def test_same_seed_same_orders():
    a, b = FactorySim(load_scenario(FACTORY)), FactorySim(load_scenario(FACTORY))
    assert a.reset(seed=7).orders == b.reset(seed=7).orders
    assert a.reset(seed=7).orders != a.reset(seed=8).orders


def test_varied_orders_follow_their_ranges():
    sim = FactorySim(load_scenario(PROJECT_ROOT / "scenarios" / "large" / "varied.yaml"))
    counts, single = set(), 0
    for seed in range(40):
        orders = sim.reset(seed=seed).orders
        counts.add(len(orders))
        single += len({o.product for o in orders}) == 1
        for o in orders:
            assert 1 <= o.quantity <= 15
            assert 900 <= o.due_time < 5000
            assert 900 <= o.due_time - o.known_time <= 2400 or o.known_time == 0
    assert min(counts) >= 20 and max(counts) <= 100 and len(counts) > 10
    assert 3 <= single <= 20  # about a quarter of episodes order one product only


def test_orders_are_hidden_until_known():
    env = FactoryEnv(PROJECT_ROOT / "scenarios" / "large" / "varied.yaml", ticks_per_action=60)
    obs, _ = env.reset(seed=0)
    s = env.sim.state
    assert any(o.known_time > 0 for o in s.orders)
    known = [o for o in s.orders if o.known_time == 0]
    n_prod = len(env.sim.scenario.products)
    orders = obs[-env.visible_orders * (n_prod + 2):].reshape(env.visible_orders, n_prod + 2)
    shown = int((orders[:, :n_prod].sum(axis=1) > 0).sum())
    assert shown == min(len(known), env.visible_orders)


def test_move_cost_only_lowers_the_reward():
    env = FactoryEnv(FACTORY, horizon=120, ticks_per_action=60, reward_scale=1.0, move_cost=100)
    _, info = env.reset(seed=0)
    constructors = env.kinds[0]
    action = env.start_action()
    action[0] = move(constructors, 0, 1)
    _, reward, _, _, after = env.step(action)
    assert reward == pytest.approx(after["cash"] - info["cash"] - 100)


def test_env_passes_gymnasium_checks():
    check_env(FactoryEnv(FACTORY, horizon=50), skip_render_check=True)


def test_recipes_that_can_never_run_get_no_slot():
    env = FactoryEnv(FACTORY, horizon=50)
    sc = env.sim.scenario
    assert "IronOre" not in sc.obtainable and "Motor" in sc.obtainable
    assert [k.category for k in env.kinds] == ["Constructor", "Assembler"]  # every caster recipe needs ore
    assert env.action_space.nvec.tolist() == [1 + 5 * 4, 1 + 5 * 4]  # no change, or a move between 2 of 5 recipes


def test_casters_scenario_plans_casters_too():
    env = FactoryEnv(PROJECT_ROOT / "scenarios" / "large" / "casters.yaml", horizon=50)
    assert [k.category for k in env.kinds] == ["Caster", "Constructor", "Assembler"]
    assert env.action_space.nvec.tolist() == [1 + 3 * 2, 1 + 5 * 4, 1 + 5 * 4]


def move(kind, a, b):
    """The choice that moves one planned machine of kind from recipe a to recipe b (positions in kind.recipes)"""
    return 1 + kind.moves.index((a, b))


def test_moves_are_unique_and_masked():
    env = FactoryEnv(FACTORY, horizon=50)
    env.reset(seed=0)
    for k in env.kinds:
        assert len(set(k.moves)) == len(k.moves)
    assemblers = env.kinds[1]
    assert env.plan[1].tolist() == [2, 2, 0, 1, 0]  # the starting plan: what the machines start on
    mask = env.action_masks()[env.action_space.nvec[0]:]
    assert mask[0]  # no change is always allowed
    assert not mask[move(assemblers, 2, 0)]  # nothing planned on PlateAssemble to move away
    assert mask[move(assemblers, 0, 2)]


def test_plan_switches_idle_machines_only_and_keeps_the_rest():
    env = FactoryEnv(FACTORY, horizon=400, ticks_per_action=1)
    env.reset(seed=0)
    start = env.start_action()
    env.step(start)  # no change: nothing switches
    assert env.switches() == {}

    sc = env.sim.scenario
    constructors = env.kinds[0]
    plate = constructors.recipes.index(sc.recipe_index["Ingot_2_Plate"])
    bar = constructors.recipes.index(sc.recipe_index["Ingot_2_Bar"])
    action = start.copy()
    action[0] = move(constructors, bar, plate)
    env.step(action)
    env.step(action)  # two moves: 2 bar machines planned onto plates
    assert env.plan[0][plate] == 2 and env.plan[0][bar] == 4
    for _ in range(60):
        env.step(start)
        for m in env.switches():
            assert env.sim.idle[m]
    assert env._current_counts(constructors).tolist() == env.plan[0].tolist()
    assert env.plan[0].sum() == len(constructors.machines)  # moves keep the total


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
    env = FactoryEnv(FACTORY, horizon=200, ticks_per_action=7, reward_scale=1.0)
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
    env = FactoryEnv(FACTORY, horizon=300)
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

    env = FactoryEnv(FACTORY, horizon=200, ticks_per_action=5)
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


def test_variant_file_changes_only_what_it_lists(tmp_path):
    (tmp_path / "variant.yaml").write_text(
        f"base: {(PROJECT_ROOT / 'scenarios' / 'lab.yaml').as_posix()}\n"
        "recipes: {Make_Plate: {cycle_time: 5}}\n"
        "orders: {random: {count: [50, 50]}}\n",
        encoding="utf-8",
    )
    lab, variant = load_scenario(PROJECT_ROOT / "scenarios" / "lab.yaml"), load_scenario(tmp_path / "variant.yaml")
    plate = lab.recipe_index["Make_Plate"]
    assert variant.recipes[plate].cycle_time == 5
    assert variant.recipes[plate].inputs == lab.recipes[plate].inputs  # merged, not replaced
    assert variant.random_orders.count_range == (50, 50)
    assert variant.random_orders.notice_range == lab.random_orders.notice_range
    assert variant.machines == lab.machines


def test_lab_is_balanced_and_the_default():
    from sjfactory.check import unit_load

    sc = load_scenario()
    assert sc == load_scenario(PROJECT_ROOT / "scenarios" / "lab.yaml")
    # every product needs 30 s from each kind, as the scenario file says
    assert unit_load(sc) == {p: {"Smelter": 30.0, "Constructor": 30.0, "Assembler": 30.0} for p in ("Motor", "Frame")}
    env = FactoryEnv(horizon=700)
    assert env.action_space.nvec.tolist() == [3, 3, 3]
    check_env(env, skip_render_check=True)


def test_upper_bound_is_above_keep():
    from sjfactory.check import bound
    from sjfactory.evaluate import run_episode

    env = FactoryEnv(ticks_per_action=60)
    env.reset(seed=2000)
    b = bound(env)
    keep = run_episode(env, KeepPolicy(env.action_space), seed=2000).summary()["profit"]
    assert keep < b


def test_downstream_priority_serves_deeper_recipes_first():
    two = {
        "horizon": 10,
        "materials": {"A": {"initial_stock": 1}, "B": {"initial_stock": 1}, "C": {}},
        "recipes": {
            "Split": {"category": "M", "cycle_time": 2, "inputs": {"A": 1}, "outputs": {"B": 1}},
            "Join": {"category": "M", "cycle_time": 2, "inputs": {"A": 1, "B": 1}, "outputs": {"C": 1}},
        },
        "machines": [{"category": "M", "recipe": "Split"}, {"category": "M", "recipe": "Join"}],
    }
    for priority, started in [("machine_order", [1, 0]), ("downstream", [0, 1])]:
        sim = FactorySim(scenario_from_dict({**two, "input_priority": priority}))
        sim.reset(seed=0)
        sim.step()
        assert (sim.state.remaining > 0).astype(int).tolist() == started, priority


def test_three_product_lab_loads_with_its_variant_chain():
    from sjfactory.check import unit_load

    sc = load_scenario(PROJECT_ROOT / "scenarios" / "lab-three-downstream.yaml")
    assert sc.input_priority == "downstream" and sc.products == ("Motor", "Frame", "Pump")
    assert unit_load(sc)["Pump"] == {"Assembler": 30.0, "Constructor": 50.0, "Smelter": 40.0}
    assert sc.random_orders.notice_range == (600, 1800)  # from lab.yaml, two files up


def test_lookahead_tries_do_not_change_the_episode():
    from sjfactory.evaluate import run_episode
    from sjfactory.lookahead import LookaheadPolicy

    env = FactoryEnv(horizon=1200, ticks_per_action=60)
    first = run_episode(env, LookaheadPolicy(env, 5), seed=3)
    again = run_episode(env, LookaheadPolicy(env, 5), seed=3)
    assert len(first.reports) == 1200  # the recording holds the real seconds only, not the tries
    assert first.summary() == again.summary()


def test_order_fine_applies_once_per_short_order():
    sim = FactorySim(scenario_from_dict({**TINY, "materials": {**TINY["materials"], "B": {**TINY["materials"]["B"], "order_fine": 50}}}))
    sim.reset(seed=0)
    reports = [sim.step() for _ in range(5)]
    assert reports[-1].deliveries[0].penalty == 4 + 50  # 1 unit short × 4, plus the fine for the order


def test_without_partial_delivery_a_short_order_ships_nothing():
    sim = FactorySim(scenario_from_dict({**TINY, "partial_delivery": False}))
    sim.reset(seed=0)
    reports = [sim.step() for _ in range(5)]
    d = reports[-1].deliveries[0]  # 2 of 3 B in stock when due
    assert d.shipped == 0 and d.revenue == 0
    assert d.penalty == 3 * 4  # every unit of the order is fined
    assert sim.state.stock[1] == 2  # the units stay in stock

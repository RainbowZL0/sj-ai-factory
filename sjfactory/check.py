"""Quick check of a scenario, with no training: how loaded each machine kind is, and how much profit is possible.

uv run python -m sjfactory --scenario scenarios/lab.yaml check [runs/<folder>/best_model.zip ...]

- Load: machine seconds each product needs from each machine kind, following the recipes back to raw materials.
- Upper bound (linear program, a standard method for finding the best split of limited resources): time in
  10 s periods; each machine kind's time in a period can be split freely over its recipes; a batch's inputs are
  taken in the period it runs and its outputs count floor(cycle / 10) periods later (a real batch never finishes
  sooner); no changeovers; every order known from the start. Every real schedule fits these rules, so no policy
  can beat it. Storage is charged on the stock at the end of each period, so with storage costs the bound is close
  but no longer strict.
- Oracle (integer program): the model's own kind of decision, whole machines per recipe each minute, with a
  changeover per machine added, but knowing every order in advance. Its plan is played in the simulator.
  Not a strict bound: flow within a minute is treated as smooth, so the plan loses some profit when played.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from scipy.optimize import Bounds, LinearConstraint, linprog, milp

from sjfactory.env import FactoryEnv
from sjfactory.evaluate import baseline_policy, model_episodes, run_episode
from sjfactory.policies import KeepPolicy
from sjfactory.recorder import Recorder
from sjfactory.spec import Scenario

L = 10  # seconds per period in the upper bound
P = 60  # seconds per period in the oracle, the same as one decision


def unit_load(sc: Scenario) -> dict[str, dict[str, float]]:
    """{product: {machine kind: machine seconds per unit}}, following the first runnable recipe that makes each
    material back to materials no runnable recipe makes (those count as raw)"""
    maker = {}
    for i, r in enumerate(sc.recipes):
        if sc.can_ever_run(i):
            for name in r.outputs:
                maker.setdefault(name, r)
    load = {}
    for product in sc.products:
        seconds: dict[str, float] = {}

        def add(name: str, qty: float, depth=0):
            r = maker.get(name)
            if r is None:
                return
            if depth > len(sc.recipes):
                raise ValueError(f"recipes for {name} go round in a circle")
            batches = qty / r.outputs[name]
            seconds[r.category] = seconds.get(r.category, 0.0) + batches * r.cycle_time
            for inp, q in r.inputs.items():
                add(inp, batches * q, depth + 1)

        add(product, 1.0)
        load[product] = seconds
    return load


def bound(env: FactoryEnv) -> float:
    """Upper bound on the profit of the episode just reset in env"""
    sim, sc = env.sim, env.sim.scenario
    orders = sim.state.orders
    R, M = len(sc.recipes), len(sc.materials)
    T = -(-sc.horizon // L)
    period_len = np.full(T, L)
    period_len[-1] = sc.horizon - L * (T - 1)
    cats = sorted({m.category for m in sc.machines})
    n_cat = {c: sum(m.category == c for m in sc.machines) for c in cats}
    lag = sim.cycle_time // L
    nx, no = T * R, len(orders)
    xi = lambda t, r: t * R + r  # machine-seconds on recipe r in period t

    rows, cols, vals, rhs = [], [], [], []
    row = 0
    for t in range(T):  # machine time
        for c in cats:
            for r in range(R):
                if sc.recipes[r].category == c:
                    rows.append(row); cols.append(xi(t, r)); vals.append(1.0)
            rhs.append(n_cat[c] * period_len[t]); row += 1
    init = np.array([m.initial_stock for m in sc.materials])
    o_period = [min(T - 1, (o.due_time - 1) // L) for o in orders]  # ships at the end of its due second
    o_mat = [sc.material_index[o.product] for o in orders]
    # Stock variables: I[t, m] = stock at the end of period t, never negative
    ni = T * M
    ii = lambda t, m: nx + t * M + m
    si = lambda i: nx + ni + i
    erows, ecols, evals, erhs = [], [], [], []
    erow = 0
    for t in range(T):
        for m in range(M):
            # I[t] - I[t-1] - made (finished now) + used + shipped = 0
            erows.append(erow); ecols.append(ii(t, m)); evals.append(1.0)
            if t > 0:
                erows.append(erow); ecols.append(ii(t - 1, m)); evals.append(-1.0)
            for r in range(R):
                if sim.recipe_out[r, m] > 0 and t - lag[r] >= 0:
                    erows.append(erow); ecols.append(xi(t - lag[r], r)); evals.append(-sim.recipe_out[r, m] / sim.cycle_time[r])
                if sim.recipe_in[r, m] > 0:
                    erows.append(erow); ecols.append(xi(t, r)); evals.append(sim.recipe_in[r, m] / sim.cycle_time[r])
            erhs.append(init[m] if t == 0 else 0.0); erow += 1
    for i in range(no):
        erows.append(o_period[i] * M + o_mat[i]); ecols.append(si(i)); evals.append(1.0)
    n = nx + ni + no
    A = sp.csr_matrix((vals, (rows, cols)), shape=(row, n))
    E = sp.csr_matrix((evals, (erows, ecols)), shape=(erow, n))
    price = np.array([sim.sell_price[m] + sim.shortfall_penalty[m] for m in o_mat])
    c = np.concatenate([_energy_cost(sim, T), _storage_cost(sim, period_len), -price])
    bounds = [(0, None)] * (nx + ni) + [(0, o.quantity) for o in orders]
    res = linprog(c, A_ub=A, b_ub=rhs, A_eq=E, b_eq=erhs, bounds=bounds, method="highs")
    assert res.status == 0, res.message
    return -res.fun - _all_penalties(env) - sc.rent_per_second * sc.horizon


def _energy_cost(sim, T: int) -> np.ndarray:
    """Cost per machine-second on each recipe, repeated for T periods"""
    return np.tile(sim.power_kw / 3600 * sim.scenario.energy_price, T)


def _storage_cost(sim, period_len: np.ndarray) -> np.ndarray:
    """Cost of one unit of each material held at the end of each period, for the whole period"""
    return np.outer(period_len, sim.storage_cost).ravel()


def _all_penalties(env: FactoryEnv) -> float:
    sim, sc = env.sim, env.sim.scenario
    return sum(o.quantity * sim.shortfall_penalty[sc.material_index[o.product]] for o in sim.state.orders)


def oracle(env: FactoryEnv, time_limit=60):
    """Best minute-by-minute plan knowing every order: (planned profit, plan[minute, recipe], solver result)"""
    sim, sc = env.sim, env.sim.scenario
    orders = sim.state.orders
    R, M = len(sc.recipes), len(sc.materials)
    T = -(-sc.horizon // P)
    plen = np.full(T, P)
    plen[-1] = sc.horizon - P * (T - 1)
    cats = sorted({m.category for m in sc.machines})
    n_cat = {c: sum(m.category == c for m in sc.machines) for c in cats}
    lag = sim.cycle_time // P
    co = sc.changeover_time
    start = np.zeros(R)
    for m in sc.machines:
        if m.initial_recipe:
            start[sc.recipe_index[m.initial_recipe]] += 1
    no = len(orders)
    # variable blocks: n[t,r] whole machines, u[t,r] busy machine-seconds, add[t,r] machines added, I[t,m] stock, s[o]
    N, U, AD, I, S = 0, T * R, 2 * T * R, 3 * T * R, 3 * T * R + T * M
    nv = S + no
    rows, cols, vals, lo, hi = [], [], [], [], []
    k = 0

    def row(entries, l, h):
        nonlocal k
        for c, v in entries:
            rows.append(k); cols.append(c); vals.append(v)
        lo.append(l); hi.append(h); k += 1

    for t in range(T):
        for c in cats:
            row([(N + t * R + r, 1.0) for r in range(R) if sc.recipes[r].category == c], 0, n_cat[c])
        for r in range(R):
            # busy time <= machine time minus changeovers of machines added this minute
            row([(U + t * R + r, 1.0), (N + t * R + r, -float(plen[t])), (AD + t * R + r, float(min(co, plen[t])))], -np.inf, 0)
            prev = [(N + (t - 1) * R + r, 1.0)] if t else []
            row([(AD + t * R + r, 1.0), (N + t * R + r, -1.0), *prev], 0 if t else -start[r], np.inf)
        for m in range(M):
            e = [(I + t * M + m, 1.0)]
            if t:
                e.append((I + (t - 1) * M + m, -1.0))
            for r in range(R):
                if sim.recipe_out[r, m] > 0 and t - lag[r] >= 0:
                    e.append((U + (t - lag[r]) * R + r, -sim.recipe_out[r, m] / sim.cycle_time[r]))
                if sim.recipe_in[r, m] > 0:
                    e.append((U + t * R + r, sim.recipe_in[r, m] / sim.cycle_time[r]))
            for i, o in enumerate(orders):
                if sc.material_index[o.product] == m and min(T - 1, (o.due_time - 1) // P) == t:
                    e.append((S + i, 1.0))
            b = sc.materials[m].initial_stock if t == 0 else 0.0
            row(e, b, b)
    A = sp.csr_matrix((vals, (rows, cols)), shape=(k, nv))
    c = np.zeros(nv)
    c[U:AD] = _energy_cost(sim, T)
    c[I:S] = _storage_cost(sim, plen)
    for i, o in enumerate(orders):
        j = sc.material_index[o.product]
        c[S + i] = -(sim.sell_price[j] + sim.shortfall_penalty[j])
    ub = np.full(nv, np.inf)
    ub[S:] = [o.quantity for o in orders]
    integrality = np.zeros(nv)
    integrality[N:U] = 1
    res = milp(c, constraints=LinearConstraint(A, lo, hi), bounds=Bounds(0, ub), integrality=integrality,
               options={"time_limit": time_limit, "mip_rel_gap": 0.01})
    value = -res.fun - _all_penalties(env) - sc.rent_per_second * sc.horizon
    plan = np.rint(res.x[N:U].reshape(T, R)).astype(int)
    return value, plan, res


def play_plan(env: FactoryEnv, seed, plan) -> Recorder:
    """Play the oracle's minute-by-minute plan in the real simulator (the env carries out each plan as usual)"""
    with Recorder(env.sim) as rec:
        env.reset(seed=seed)
        keep = KeepPolicy(env.action_space)
        t, done = 0, False
        while not done:
            for i, k in enumerate(env.kinds):
                target = plan[min(t, len(plan) - 1), list(k.recipes)].copy()
                # machines the oracle leaves unused stay where they are (no needless changeover)
                for j in np.argsort(-(env.plan[i] - target)):
                    target[j] += max(0, min(env.plan[i][j] - target[j], len(k.machines) - target.sum()))
                if (target != env.plan[i]).any():
                    env.plan[i] = target.copy()
                    env._unreached.add(i)
            _, _, done, _, _ = env.step(keep.act(None, None))
            t += 1
    return rec


def _check_seed(job) -> dict:
    scenario, horizon, models, seed, oracle_seconds = job
    import torch

    torch.set_num_threads(1)
    env = FactoryEnv(scenario, horizon=horizon, ticks_per_action=P)
    env.reset(seed=seed)
    sc = env.sim.scenario
    out = {"demand": {p: sum(o.quantity for o in env.sim.state.orders if o.product == p) for p in sc.products}}
    out["bound"] = bound(env)
    if oracle_seconds > 0:
        out["oracle planned"], plan, _ = oracle(env, time_limit=oracle_seconds)
        out["oracle"] = play_plan(env, seed, plan).summary()
    out["keep"] = run_episode(env, baseline_policy("keep", env), seed=seed).summary()
    if models:
        from sb3_contrib import MaskablePPO

        for path in models:
            model = MaskablePPO.load(path, device="cpu")
            out[path] = model_episodes(env, model, [seed], "fixed")[0].summary()
    return out


def run_check(scenario: str | Path, models: Sequence[str] = (), seeds: Sequence[int] = range(2000, 2010),
              horizon: int | None = None, oracle_seconds: int = 30, workers: int | None = None) -> dict:
    """Print the load table and the profit of keep, the oracle, models and the upper bound; returns the numbers"""
    env = FactoryEnv(scenario, horizon=horizon)
    sc = env.sim.scenario
    kinds = list(dict.fromkeys(m.category for m in sc.machines))
    n_kind = {k: sum(m.category == k for m in sc.machines) for k in kinds}
    load = unit_load(sc)

    print(f"{scenario}: {len(sc.machines)} machines, {sc.horizon} s per episode, changeover {sc.changeover_time} s")
    print("\nMachine seconds per unit, divided by the machines of that kind:")
    print(f"  {'':10s}" + "".join(f"{f'{k} ({n_kind[k]})':>18s}" for k in kinds) + f"{'most per episode':>18s}")
    for p, sec in load.items():
        per = [sec.get(k, 0.0) / n_kind[k] for k in kinds]
        most = sc.horizon / max(per) if max(per) > 0 else float("inf")
        print(f"  {p:10s}" + "".join(f"{x:18.1f}" for x in per) + f"{most:18.0f}")

    seeds = list(seeds)
    jobs = [(str(scenario), horizon, list(models), s, oracle_seconds) for s in seeds]
    with ProcessPoolExecutor(workers or min(len(jobs), os.cpu_count() or 1)) as pool:
        res = list(pool.map(_check_seed, jobs))

    demand = {p: float(np.mean([r["demand"][p] for r in res])) for p in sc.products}
    # Share of each kind's time the orders need, if no machine ever waited or switched
    need = {k: np.mean([sum(r["demand"][p] * load[p].get(k, 0) for p in sc.products) for r in res])
            / (n_kind[k] * sc.horizon) for k in kinds}
    print(f"\nOrders, mean over seeds {seeds[0]}-{seeds[-1]}: "
          + ", ".join(f"{p} {d:.0f}" for p, d in demand.items()) + f", total {sum(demand.values()):.0f} units")
    print("Share of each kind's time these orders need: " + ", ".join(f"{k} {v:.0%}" for k, v in need.items()))

    rows = ["keep", *models] + (["oracle"] if oracle_seconds > 0 else [])
    b = float(np.mean([r["bound"] for r in res]))
    summary = {"seeds": seeds, "demand": demand, "need": need, "bound": b}
    print(f"\nMean over {len(seeds)} episodes{'':30s}{'profit':>10s}{'of bound':>10s}{'shipped':>10s}{'busy':>8s}")
    for key in rows:
        s = [r[key] for r in res]
        profit = float(np.mean([x["profit"] for x in s]))
        fill = float(np.mean([x["fill_rate"] for x in s]))
        busy = float(np.mean([x["machine_busy_ratio"] for x in s]))
        summary[key] = {"profit": profit, "fill_rate": fill, "busy": busy}
        label = key if len(key) <= 50 else "..." + key[-47:]
        print(f"  {label:50s}{profit:10,.0f}{profit / b if b > 0 else float('nan'):10.0%}{fill:10.0%}{busy:8.0%}")
    if oracle_seconds > 0:
        # What the oracle expected: the gap to "oracle" is lost to flow within a minute (batches, waiting for inputs)
        planned = float(np.mean([r["oracle planned"] for r in res]))
        summary["oracle planned"] = planned
        print(f"  {'oracle, as planned':50s}{planned:10,.0f}{planned / b if b > 0 else float('nan'):10.0%}")
    print(f"  {'upper bound':50s}{b:10,.0f}")
    return summary

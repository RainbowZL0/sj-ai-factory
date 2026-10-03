"""Quick check of a scenario, with no training: how loaded each machine kind is, and how much profit is possible.

uv run python -m sjfactory --scenario scenarios/lab.yaml check [runs/<folder>/best_model.zip ...]

- Load: machine seconds each product needs from each machine kind, following the recipes back to raw materials.
- Upper bound (linear program, a standard method for finding the best split of limited resources): time in
  10 s periods; each machine kind's time in a period can be split freely over its recipes; a batch's inputs are
  taken in the period it runs and its outputs count floor(cycle / 10) periods later (a real batch never finishes
  sooner); no changeovers; every order known from the start. Every real schedule fits these rules, so no policy
  can beat it. Without partial delivery each order is a yes/no choice (an integer program, still well under a
  second), and fines per order not filled in full are counted; with partial delivery they are left out, which
  only makes the bound higher. Storage is charged on the stock at the end of each period, so with storage costs the bound is close
  but no longer strict.
- Look-ahead (sjfactory/lookahead.py): tries moves in a copy of the simulator each minute, so it sees
  batches and input order too. Knows every order in advance.
- Oracle (integer program): the model's own kind of decision, whole machines per recipe each minute, with a
  changeover per machine added, but knowing every order in advance. Its plan is played in the simulator.
  Not a strict bound: flow within a minute is treated as smooth, so the plan loses some profit when played.
- Re-planned (--replan-minutes): the oracle solved again from the real state every few minutes, aiming to have
  each order ready a minute early, so slips in the simulator get corrected. "All orders" knows every order in
  advance; "known orders" only those announced so far, the same knowledge the model has: a fair yardstick.
- Machine time: where each policy's machine time went (work in shipped units, in products left unsold, in
  other parts, changeovers, waiting). Only the first earns money.
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
from sjfactory.evaluate import baseline_policy, model_env_options, model_episodes, run_episode
from sjfactory.policies import KeepPolicy
from sjfactory.recorder import Recorder
from sjfactory.sim import STOP
from sjfactory.spec import PROJECT_ROOT, Scenario, unit_load  # noqa: F401  (unit_load is used here and by tests)

L = 10  # seconds per period in the upper bound
P = 60  # seconds per period in the oracle, the same as one decision
MARGIN = 60  # seconds early the re-planning oracle aims to have each order ready (experiment 17)
REPLAN_ROWS = ["re-planned, all orders", "re-planned, known orders"]


def bound(env: FactoryEnv, whole_orders: bool | None = None) -> float:
    """Upper bound on the profit of the episode just reset in env. With whole_orders (the default when the
    scenario has no partial delivery) each order is a yes/no choice, which makes the bound tighter"""
    sim, sc = env.sim, env.sim.scenario
    whole = not sc.partial_delivery if whole_orders is None else whole_orders
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

    lost = _breakdown_seconds(sim, cats, T)
    rows, cols, vals, rhs = [], [], [], []
    row = 0
    for t in range(T):  # machine time, less the time machines are broken down
        for ci, c in enumerate(cats):
            for r in range(R):
                if sc.recipes[r].category == c:
                    rows.append(row); cols.append(xi(t, r)); vals.append(1.0)
            rhs.append(n_cat[c] * period_len[t] - lost[t, ci]); row += 1
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
    # Order variables: units shipped, or with whole orders 1 if the order is filled in full (it ships its quantity)
    qty = np.array([o.quantity for o in orders], dtype=float)
    for i in range(no):
        erows.append(o_period[i] * M + o_mat[i]); ecols.append(si(i)); evals.append(qty[i] if whole else 1.0)
    n = nx + ni + no
    A = sp.csr_matrix((vals, (rows, cols)), shape=(row, n))
    E = sp.csr_matrix((evals, (erows, ecols)), shape=(erow, n))
    price = np.array([sim.sell_price[m] + sim.shortfall_penalty[m] for m in o_mat])
    if whole:
        # an order filled in full earns its price, gets back its fine per unit and avoids its order fine
        price = price * qty + np.array([sim.order_fine[m] for m in o_mat])
    c = np.concatenate([_energy_cost(sim, T), _storage_cost(sim, period_len), -price])
    if not whole:
        bounds = [(0, None)] * (nx + ni) + [(0, o.quantity) for o in orders]
        res = linprog(c, A_ub=A, b_ub=rhs, A_eq=E, b_eq=erhs, bounds=bounds, method="highs")
        assert res.status == 0, res.message
        return -res.fun - _all_penalties(env) - sc.rent_per_second * sc.horizon
    ub = np.concatenate([np.full(nx + ni, np.inf), np.ones(no)])
    integrality = np.concatenate([np.zeros(nx + ni), np.ones(no)])
    cons = [LinearConstraint(A, -np.inf, rhs), LinearConstraint(E, erhs, erhs)]
    res = milp(c, constraints=cons, bounds=Bounds(0, ub), integrality=integrality,
               options={"time_limit": 60, "mip_rel_gap": 1e-4})
    assert res.x is not None, res.message
    # If the solver stops early, its own bound is the safe number: never below the best possible
    best = -res.mip_dual_bound if np.isfinite(getattr(res, "mip_dual_bound", np.nan)) else -res.fun
    fines = sum(sim.order_fine[m] for m in o_mat)
    return best - _all_penalties(env) - fines - sc.rent_per_second * sc.horizon


def _breakdown_seconds(sim, cats: list[str], T: int) -> np.ndarray:
    """[period, kind]: machine seconds lost to the breakdowns still to come, from the state just reset"""
    sc = sim.scenario
    down = np.zeros((len(sc.machines), sc.horizon), dtype=bool)
    end = np.zeros(len(sc.machines), dtype=int)
    for at, m, seconds in sim.state.failures:  # sorted by time; a breakdown while broken makes it last longer
        end[m] = max(end[m], at + seconds)
        down[m, at:min(end[m], sc.horizon)] = True
    lost = np.zeros((T, len(cats)))
    for m, machine in enumerate(sc.machines):
        per = np.add.reduceat(down[m], np.arange(0, sc.horizon, L))[:T] if down[m].any() else 0
        lost[:, cats.index(machine.category)] += per
    return lost


def _energy_cost(sim, T: int) -> np.ndarray:
    """Cost per machine-second on each recipe, repeated for T periods"""
    return np.tile(sim.power_kw / 3600 * sim.scenario.energy_price, T)


def _storage_cost(sim, period_len: np.ndarray) -> np.ndarray:
    """Cost of one unit of each material held at the end of each period, for the whole period"""
    return np.outer(period_len, sim.storage_cost).ravel()


def _all_penalties(env: FactoryEnv) -> float:
    sim, sc = env.sim, env.sim.scenario
    return sum(o.quantity * sim.shortfall_penalty[sc.material_index[o.product]] for o in sim.state.orders)


def oracle(env: FactoryEnv, time_limit=60, margin: int = 0, known_only: bool = False):
    """Best minute-by-minute plan from the current state to the end of the episode, knowing every order still
    to come: (planned profit from now on, plan[minute from now, recipe], solver result).
    With a margin (seconds), each order must be in stock that much before it is due, which leaves room for the
    delays a played plan meets. With known_only, only orders already announced count, as for the model."""
    sim, sc, s = env.sim, env.sim.scenario, env.sim.state
    orders = [o for o in s.orders if not o.declined and (not known_only or o.known_time <= s.clock)]
    R, M = len(sc.recipes), len(sc.materials)
    left = sc.horizon - s.clock
    T = -(-left // P)
    plen = np.full(T, P)
    plen[-1] = left - P * (T - 1)
    cats = sorted({m.category for m in sc.machines})
    n_cat = {c: sum(m.category == c for m in sc.machines) for c in cats}
    lag = sim.cycle_time // P
    co = sc.changeover_time
    start = np.bincount(s.recipe[s.recipe != STOP], minlength=R).astype(float)
    # batches already running: their inputs are taken, their outputs arrive in the minute they finish
    arriving = np.zeros((T, M))
    for m in np.flatnonzero(s.remaining > 0):
        arriving[min(T - 1, (s.remaining[m] - 1) // P)] += sim.recipe_out[s.recipe[m]]
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
                if sc.material_index[o.product] == m and min(T - 1, max(0, o.due_time - 1 - margin - s.clock) // P) == t:
                    e.append((S + i, 1.0))
            b = arriving[t, m] + (s.stock[m] if t == 0 else 0.0)
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
    if not sc.partial_delivery:
        # all or nothing: units shipped = quantity x (0 or 1), so each order is a yes/no choice
        y = nv
        nv += no
        for i, o in enumerate(orders):
            row([(S + i, 1.0), (y + i, -float(o.quantity))], 0, 0)
        A = sp.csr_matrix((vals, (rows, cols)), shape=(k, nv))
        c = np.concatenate([c, np.zeros(no)])
        ub = np.concatenate([ub, np.ones(no)])
        integrality = np.concatenate([integrality, np.ones(no)])
    res = milp(c, constraints=LinearConstraint(A, lo, hi), bounds=Bounds(0, ub), integrality=integrality,
               options={"time_limit": time_limit, "mip_rel_gap": 0.01})
    fines = sum(o.quantity * sim.shortfall_penalty[sc.material_index[o.product]] for o in orders)
    value = -res.fun - fines - sc.rent_per_second * left
    plan = np.rint(res.x[N:U].reshape(T, R)).astype(int)
    return value, plan, res


def chosen_orders(env: FactoryEnv, res) -> np.ndarray | None:
    """From the oracle's solver result for the episode just reset in env: True for each order it fills in full.
    None when the scenario allows partial delivery (then there is no yes/no choice per order)."""
    if env.sim.scenario.partial_delivery or res.x is None:
        return None
    return res.x[-len(env.sim.state.orders):] > 0.5  # right after reset no order is declined or unknown to it


def play_plan(env: FactoryEnv, seed, plan, keep_orders: np.ndarray | None = None) -> Recorder:
    """Play the oracle's minute-by-minute plan in the real simulator (the env carries out each plan as usual).
    With keep_orders, the orders marked False are declined at the start, so their stock stays for the others."""
    with Recorder(env.sim) as rec:
        env.reset(seed=seed)
        if keep_orders is not None:
            for i in np.flatnonzero(~keep_orders):
                env.sim.decline(int(i))
        keep = KeepPolicy(env.action_space)
        t, done = 0, False
        while not done:
            _set_plan(env, plan[min(t, len(plan) - 1)])
            _, _, done, _, _ = env.step(keep.act(None, None))
            t += 1
    return rec


def play_replanned(env: FactoryEnv, seed, every: int = 5, time_limit=10, margin: int = 0,
                   known_only: bool = False) -> Recorder:
    """Play the oracle, solving again from the real state every `every` minutes, so a plan that slipped in
    the simulator (an order a few units short, a machine waiting for inputs) is corrected. With known_only it
    only plans for orders already announced, the same knowledge the model has: a fair yardstick for short notice."""
    with Recorder(env.sim) as rec:
        env.reset(seed=seed)
        keep = KeepPolicy(env.action_space)
        t, done, plan, since = 0, False, None, 0
        while not done:
            if t % every == 0:
                _, plan, _ = oracle(env, time_limit, margin, known_only)
                since = t
            _set_plan(env, plan[min(t - since, len(plan) - 1)])
            _, _, done, _, _ = env.step(keep.act(None, None))
            t += 1
    return rec


def _set_plan(env: FactoryEnv, row: np.ndarray):
    """Make env's plan follow one minute of an oracle plan (machines per recipe)"""
    for i, k in enumerate(env.kinds):
        target = row[list(k.recipes)].copy()
        # machines the oracle leaves unused stay where they are (no needless changeover)
        for j in np.argsort(-(env.plan[i] - target)):
            target[j] += max(0, min(env.plan[i][j] - target[j], len(k.machines) - target.sum()))
        if (target != env.plan[i]).any():
            env.plan[i] = target.copy()
            env._unreached.add(i)


def time_split(rec: Recorder) -> dict[str, float]:
    """Where the machine time of an episode went, as shares of all machine time:
    shipped: work in units that shipped; unsold: work in finished products still in stock at the end;
    parts: other work (parts left over or still being made); switching: changeovers;
    waiting: stopped or short of inputs."""
    sc = rec.scenario
    run = rec.running_matrix()
    total = run.size
    busy = int((run != STOP).sum())
    switches = 0
    for m, col in zip(sc.machines, run.T):
        seq = col[col != STOP]
        if m.initial_recipe:
            seq = np.concatenate([[sc.recipe_index[m.initial_recipe]], seq])
        switches += int((seq[1:] != seq[:-1]).sum())
    switching = min(switches * sc.changeover_time, total - busy)
    load = unit_load(sc)
    d = rec.deliveries_frame()
    shipped = sum(row.shipped * sum(load[row.product].values()) for row in d.itertuples())
    left = rec.stock[-1] if rec.stock else np.zeros(len(sc.materials))
    unsold = sum(max(0.0, left[sc.material_index[p]] - sc.materials[sc.material_index[p]].initial_stock)
                 * sum(load[p].values()) for p in sc.products)
    return {"shipped": shipped / total, "unsold": unsold / total, "parts": (busy - shipped - unsold) / total,
            "switching": switching / total, "waiting": (total - busy - switching) / total}


def _summary(rec: Recorder) -> dict:
    """The episode summary plus units shipped per product and where the machine time went"""
    d = rec.deliveries_frame()
    by_product = d.groupby("product")["shipped"].sum().to_dict() if not d.empty else {}
    return {**rec.summary(), "by_product": {p: float(by_product.get(p, 0.0)) for p in rec.scenario.products},
            "time": time_split(rec)}


def _check_seed(job) -> dict:
    scenario, horizon, models, seed, oracle_seconds, lookahead_minutes, replan_minutes = job
    import torch

    torch.set_num_threads(1)
    env = FactoryEnv(scenario, horizon=horizon, ticks_per_action=P)
    env.reset(seed=seed)
    sc = env.sim.scenario
    out = {"demand": {p: sum(o.quantity for o in env.sim.state.orders if o.product == p) for p in sc.products}}
    out["bound"] = bound(env)
    if oracle_seconds > 0:
        out["oracle planned"], plan, _ = oracle(env, time_limit=oracle_seconds)
        out["oracle"] = _summary(play_plan(env, seed, plan))
    out["keep"] = _summary(run_episode(env, baseline_policy("keep", env), seed=seed))
    if replan_minutes > 0:
        for key, known in zip(REPLAN_ROWS, (False, True)):
            out[key] = _summary(play_replanned(env, seed, replan_minutes, max(oracle_seconds, 30), MARGIN, known))
    if lookahead_minutes > 0:
        from sjfactory.lookahead import LookaheadPolicy

        out["look-ahead"] = _summary(run_episode(env, LookaheadPolicy(env, lookahead_minutes), seed=seed))
    if models:
        from sb3_contrib import MaskablePPO

        for path in models:
            model = MaskablePPO.load(path, device="cpu")
            menv = FactoryEnv(scenario, horizon=horizon, ticks_per_action=P, **model_env_options(path))
            out[path] = _summary(model_episodes(menv, model, [seed], "fixed")[0])
    return out


def run_check(scenario: str | Path, models: Sequence[str] = (), seeds: Sequence[int] = range(2000, 2010),
              horizon: int | None = None, oracle_seconds: int = 30, lookahead_minutes: int = 30, replan_minutes: int = 0,
              workers: int | None = None, verbose: bool = True) -> dict:
    """Print the load table and the profit of keep, the oracle, models and the upper bound; returns the numbers"""
    say = print if verbose else (lambda *a, **k: None)
    env = FactoryEnv(scenario, horizon=horizon)
    sc = env.sim.scenario
    kinds = list(dict.fromkeys(m.category for m in sc.machines))
    n_kind = {k: sum(m.category == k for m in sc.machines) for k in kinds}
    load = unit_load(sc)

    say(f"{scenario}: {len(sc.machines)} machines, {sc.horizon} s per episode, changeover {sc.changeover_time} s")
    say("\nMachine seconds per unit, divided by the machines of that kind:")
    say(f"  {'':10s}" + "".join(f"{f'{k} ({n_kind[k]})':>18s}" for k in kinds) + f"{'most per episode':>18s}")
    for p, sec in load.items():
        per = [sec.get(k, 0.0) / n_kind[k] for k in kinds]
        most = sc.horizon / max(per) if max(per) > 0 else float("inf")
        say(f"  {p:10s}" + "".join(f"{x:18.1f}" for x in per) + f"{most:18.0f}")

    seeds = list(seeds)
    jobs = [(str(scenario), horizon, list(models), s, oracle_seconds, lookahead_minutes, replan_minutes) for s in seeds]
    with ProcessPoolExecutor(workers or min(len(jobs), os.cpu_count() or 1)) as pool:
        res = list(pool.map(_check_seed, jobs))

    demand = {p: float(np.mean([r["demand"][p] for r in res])) for p in sc.products}
    # Share of each kind's time the orders need, if no machine ever waited or switched
    need = {k: np.mean([sum(r["demand"][p] * load[p].get(k, 0) for p in sc.products) for r in res])
            / (n_kind[k] * sc.horizon) for k in kinds}
    say(f"\nOrders, mean over seeds {seeds[0]}-{seeds[-1]}: "
          + ", ".join(f"{p} {d:.0f}" for p, d in demand.items()) + f", total {sum(demand.values()):.0f} units")
    say("Share of each kind's time these orders need: " + ", ".join(f"{k} {v:.0%}" for k, v in need.items()))

    rows = ["keep", *models] + (["look-ahead"] if lookahead_minutes > 0 else []) + (["oracle"] if oracle_seconds > 0 else []) + (REPLAN_ROWS if replan_minutes > 0 else [])
    b = float(np.mean([r["bound"] for r in res]))
    summary = {"seeds": seeds, "demand": demand, "need": need, "bound": b}
    say(f"\nMean over {len(seeds)} episodes{'':30s}{'profit':>10s}{'of bound':>10s}{'shipped':>10s}{'busy':>8s}   units shipped")
    for key in rows:
        s = [r[key] for r in res]
        profit = float(np.mean([x["profit"] for x in s]))
        fill = float(np.mean([x["fill_rate"] for x in s]))
        busy = float(np.mean([x["machine_busy_ratio"] for x in s]))
        units = {p: float(np.mean([x["by_product"][p] for x in s])) for p in sc.products}
        summary[key] = {"profit": profit, "fill_rate": fill, "busy": busy, "units": units}
        label = key if len(key) <= 50 else "..." + key[-47:]
        say(f"  {label:50s}{profit:10,.0f}{profit / b if b > 0 else float('nan'):10.0%}{fill:10.0%}{busy:8.0%}"
              + "   " + ", ".join(f"{p} {u:.0f}" for p, u in units.items()))
    if oracle_seconds > 0:
        # What the oracle expected: the gap to "oracle" is lost to flow within a minute (batches, waiting for inputs)
        planned = float(np.mean([r["oracle planned"] for r in res]))
        summary["oracle planned"] = planned
        say(f"  {'oracle, as planned':50s}{planned:10,.0f}{planned / b if b > 0 else float('nan'):10.0%}")
    say(f"  {'upper bound':50s}{b:10,.0f}")

    # Where the machine time went: only work in shipped units earns money
    parts = ["shipped", "unsold", "parts", "switching", "waiting"]
    say(f"\nShare of all machine time{'':25s}" + "".join(f"{p:>11s}" for p in parts))
    for key in rows:
        split = {p: float(np.mean([r[key]["time"][p] for r in res])) for p in parts}
        summary[key]["time"] = split
        label = key if len(key) <= 50 else "..." + key[-47:]
        say(f"  {label:48s}" + "".join(f"{split[p]:11.0%}" for p in parts))
    return summary


# The fixed set of days a change is judged on (roadmap milestone 4): (scenario, what kind of day, seeds).
# 30 days each: on 10 busy days the share of the bound moved by up to 6 points with the days drawn (experiment 16).
BENCH = (
    ("scenarios/lab-mixed.yaml", "light to busy", range(2000, 2030)),
    ("scenarios/lab-busy.yaml", "busy", range(2000, 2030)),
    ("scenarios/lab-three-downstream.yaml", "third product", range(2000, 2030)),
    ("scenarios/lab-short.yaml", "short notice", range(2000, 2030)),
    ("scenarios/lab-breakdowns.yaml", "breakdowns", range(2000, 2030)),
)


def model_fits(path: str, scenario: str | Path) -> bool:
    """True if the model can play this scenario: same observation and action sizes"""
    from sb3_contrib import MaskablePPO

    model = MaskablePPO.load(path, device="cpu")
    env = FactoryEnv(scenario, ticks_per_action=P, **model_env_options(path))
    return (model.observation_space.shape == env.observation_space.shape
            and list(model.action_space.nvec) == list(env.action_space.nvec))


def run_bench(models: Sequence[str] = (), oracle_seconds: int = 30, lookahead_minutes: int = 0, replan_minutes: int = 5,
              workers: int | None = None) -> dict:
    """Run check on every scenario in BENCH and print each policy's share of the upper bound per kind of day.
    A model is only played on scenarios it fits (a model for two products can't play three)."""
    results = {}
    for scenario, label, seeds in BENCH:
        fit = [m for m in models if model_fits(m, PROJECT_ROOT / scenario)]
        print(f"{scenario} ({label}, {len(seeds)} days)...", flush=True)
        results[scenario] = run_check(PROJECT_ROOT / scenario, fit, seeds, oracle_seconds=oracle_seconds,
                                      lookahead_minutes=lookahead_minutes, replan_minutes=replan_minutes,
                                      workers=workers, verbose=False)
    rows = ["keep", *models] + (["look-ahead"] if lookahead_minutes > 0 else []) + (["oracle"] if oracle_seconds > 0 else []) + (REPLAN_ROWS if replan_minutes > 0 else [])
    print(f"\nShare of the upper bound{'':26s}" + "".join(f"{label:>16s}" for _, label, _ in BENCH))
    for key in rows:
        cells = [results[s][key]["profit"] / results[s]["bound"] if key in results[s] else None for s, _, _ in BENCH]
        label = key if len(key) <= 50 else "..." + key[-47:]
        print(f"  {label:48s}" + "".join(f"{c:16.0%}" if c is not None else f"{'-':>16s}" for c in cells))
    return results

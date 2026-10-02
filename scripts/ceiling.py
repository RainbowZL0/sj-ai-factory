"""How close is a policy to the best possible? Two yardsticks per episode, next to keep and trained models.

uv run python scripts/ceiling.py runs/<a>/best_model.zip [runs/<b>/best_model.zip ...] --scenario scenarios/varied.yaml

- Upper bound (linear program): time in 10 s periods; each machine kind's time in a period can be split freely
  over its recipes; a batch's inputs are taken in the period it runs and its outputs count floor(cycle / 10)
  periods later (a real batch never finishes sooner); no changeovers; every order known from the start.
  Every real schedule fits these rules, so no policy can beat it.
- Oracle (integer program): the model's own kind of decision, whole machines per recipe each minute with a
  30 s changeover per machine added, but knowing every order in advance. Its plan is played in the simulator.
  Not a strict bound: flow within a minute is treated as smooth, and the plan loses 10-30% when played.

See docs/experiments/09-bottleneck-analysis.md. Needs scipy (a dev dependency).
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from scipy.optimize import Bounds, LinearConstraint, linprog, milp

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sjfactory.env import FactoryEnv  # noqa: E402
from sjfactory.evaluate import baseline_policy, model_episodes, run_episode  # noqa: E402
from sjfactory.policies import KeepPolicy  # noqa: E402
from sjfactory.recorder import Recorder  # noqa: E402
from sjfactory.spec import load_scenario  # noqa: E402

L = 10  # seconds per period in the upper bound
P = 60  # seconds per period in the oracle, the same as one decision


def bound(env: FactoryEnv) -> dict:
    """Upper bound on the profit of the episode just reset in env, plus units ordered and shipped"""
    sim, sc = env.sim, env.sim.scenario
    orders = sim.state.orders
    R, M = len(sc.recipes), len(sc.materials)
    T = -(-sc.horizon // L)
    period_len = np.full(T, L); period_len[-1] = sc.horizon - L * (T - 1)
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
    c = np.concatenate([np.zeros(nx + ni), -price])
    bounds = [(0, None)] * (nx + ni) + [(0, o.quantity) for o in orders]
    res = linprog(c, A_ub=A, b_ub=rhs, A_eq=E, b_eq=erhs, bounds=bounds, method="highs")
    assert res.status == 0, res.message
    penalty_all = sum(o.quantity * sim.shortfall_penalty[sc.material_index[o.product]] for o in orders)
    profit = -res.fun - penalty_all - sc.rent_per_second * sc.horizon
    demand = {p: sum(o.quantity for o in orders if o.product == p) for p in ("Motor", "Frame")}
    s = res.x[nx + ni:]
    split = {"bound " + p: sum(s[i] for i in range(no) if orders[i].product == p) for p in ("Motor", "Frame")}
    return {"bound": profit, "units": sum(o.quantity for o in orders), "shipped": s.sum(), **demand, **split}


def oracle(env: FactoryEnv, time_limit=120):
    """Best minute-by-minute plan knowing every order: (planned profit, plan[minute, recipe], solver result)"""
    sim, sc = env.sim, env.sim.scenario
    orders = sim.state.orders
    R, M = len(sc.recipes), len(sc.materials)
    T = -(-sc.horizon // P)
    plen = np.full(T, P); plen[-1] = sc.horizon - P * (T - 1)
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
    for i, o in enumerate(orders):
        j = sc.material_index[o.product]
        c[S + i] = -(sim.sell_price[j] + sim.shortfall_penalty[j])
    ub = np.full(nv, np.inf)
    ub[S:] = [o.quantity for o in orders]
    integrality = np.zeros(nv); integrality[N:U] = 1
    res = milp(c, constraints=LinearConstraint(A, lo, hi), bounds=Bounds(0, ub), integrality=integrality,
               options={"time_limit": time_limit, "mip_rel_gap": 0.01})
    penalty_all = sum(o.quantity * sim.shortfall_penalty[sc.material_index[o.product]] for o in orders)
    value = -res.fun - penalty_all - sc.rent_per_second * sc.horizon
    plan = np.rint(res.x[N:U].reshape(T, R)).astype(int)
    return value, plan, res


def play_plan(env: FactoryEnv, seed, plan):
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


def play(job):
    scenario, models, seed, oracle_seconds = job
    import torch
    from sb3_contrib import MaskablePPO

    torch.set_num_threads(1)
    env = FactoryEnv(load_scenario(scenario), ticks_per_action=60)
    env.reset(seed=seed)
    out = {"bound": bound(env)["bound"]}
    _, plan, _ = oracle(env, time_limit=oracle_seconds)
    out["oracle"] = play_plan(env, seed, plan).summary()["profit"]
    out["keep"] = run_episode(env, baseline_policy("keep", env), seed=seed).summary()["profit"]
    for path in models:
        out[path] = model_episodes(env, MaskablePPO.load(path, device="cpu"), [seed], "fixed")[0].summary()["profit"]
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("models", nargs="*", help="trained models, played with their most likely choice")
    p.add_argument("--scenario", default="scenarios/casters.yaml")
    p.add_argument("--seed", type=int, default=2000, help="first seed")
    p.add_argument("--episodes", type=int, default=30)
    p.add_argument("--oracle-seconds", type=int, default=60, help="time limit per oracle solve")
    p.add_argument("--workers", type=int, default=24)
    args = p.parse_args()

    seeds = range(args.seed, args.seed + args.episodes)
    with ProcessPoolExecutor(args.workers) as pool:
        res = list(pool.map(play, [(args.scenario, args.models, s, args.oracle_seconds) for s in seeds]))
    print(f"{args.scenario}, seeds {seeds.start}-{seeds.stop - 1}, mean profit:")
    for key in ["keep", *args.models, "oracle", "bound"]:
        print(f"  {key:60s} {np.mean([r[key] for r in res]):10,.0f}")


if __name__ == "__main__":
    main()

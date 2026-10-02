"""Look-ahead planner: a yardstick that plays in the real simulator, so it sees everything the simulator does
(batches, changeovers, which machine gets inputs first), unlike the oracle's integer program.

Every decision it tries moves in a copy of the factory and keeps the best: starting from "no change", it goes
through the machine kinds one at a time and tries each allowed move for that kind, with the other kinds at their
best choice so far. Each try plays the move, then "no change" for the rest of the look-ahead window, and scores
    cash change in the window + finished products in stock that later orders still want × (price + penalty).
Like the oracle, it knows every order in advance, including those the model can't see yet. Parts not yet
finished are worth nothing to it, so a window shorter than the time to make a product makes it short-sighted:
on the lab factory 10 minutes reaches about 120k, 30 minutes about 138k (experiment 13). It is a planner that
sees the real flow, not a strong one; trained models beat it.
"""

from __future__ import annotations

import dataclasses

import numpy as np

from sjfactory.env import NO_CHANGE, FactoryEnv


class LookaheadPolicy:
    def __init__(self, env: FactoryEnv, minutes: int = 30):
        self.env = env
        self.decisions = max(1, minutes * 60 // env.ticks_per_action)  # decisions per look-ahead window

    def act(self, obs, mask) -> np.ndarray:
        env = self.env
        saved = self._save()
        listeners, env.sim.listeners = env.sim.listeners, []  # tries must not show up in recordings
        try:
            per_kind = np.split(np.asarray(mask), np.cumsum(env.action_space.nvec)[:-1])
            best = env.start_action()
            best_score = self._score(best, saved)
            for k, allowed in enumerate(per_kind):
                for choice in np.flatnonzero(allowed):
                    if choice == NO_CHANGE or choice == best[k]:
                        continue
                    action = best.copy()
                    action[k] = choice
                    score = self._score(action, saved)
                    if score > best_score:
                        best_score, best = score, action
        finally:
            self._restore(saved)
            env.sim.listeners = listeners
        return best

    def _score(self, action, saved) -> float:
        env, sim = self.env, self.env.sim
        self._restore(saved)
        cash = sim.state.cash
        env.step(action)
        for _ in range(self.decisions - 1):
            if sim.done:
                break
            env.step(env.start_action())
        s, sc = sim.state, sim.scenario
        value = s.cash - cash
        for p in sc.products:
            i = sc.material_index[p]
            wanted = sum(o.quantity for o in s.orders if o.product == p)
            value += min(s.stock[i], wanted) * (sim.sell_price[i] + sim.shortfall_penalty[i])
        return value

    def _save(self):
        env, s = self.env, self.env.sim.state
        state = dataclasses.replace(
            s, stock=s.stock.copy(), recipe=s.recipe.copy(), remaining=s.remaining.copy(), setup=s.setup.copy(),
            orders=list(s.orders), down=s.down.copy(), failures=list(s.failures),
        )
        return state, [p.copy() for p in env.plan], set(env._unreached)

    def _restore(self, saved):
        state, plan, unreached = saved
        self.env.sim.state = dataclasses.replace(
            state, stock=state.stock.copy(), recipe=state.recipe.copy(), remaining=state.remaining.copy(),
            setup=state.setup.copy(), orders=list(state.orders), down=state.down.copy(), failures=list(state.failures),
        )
        self.env.plan = [p.copy() for p in plan]
        self.env._unreached = set(unreached)

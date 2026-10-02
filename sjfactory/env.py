"""Wraps FactorySim as a Gymnasium environment for reinforcement learning.

Plan: how many machines of each kind should run each recipe. A "slot" is a machine kind + a recipe it can run.
    An episode starts with the plan the machines start in, so doing nothing plays like the keep rule.
    Recipes that can never run (an input can never be obtained) get no slot; kinds with no slot are left alone.

Action: one choice per machine kind, each either "no change" (0) or "move one machine of the plan from
    recipe A to recipe B". Every choice gives a different plan, so the model never has to learn that two
    actions mean the same thing. Moves away from a recipe with no planned machine are masked out.

Carrying out the plan, every second: an idle machine whose recipe has more machines than planned (or that is
stopped) switches to the recipe furthest below its planned number. Busy machines switch after their batch,
so the plan is reached with as few switches, and changeovers, as possible.

Reward: (cash change during the action - move_cost × machines moved) × reward_scale.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from sjfactory.sim import STOP, FactorySim
from sjfactory.spec import DEFAULT_SCENARIO, Scenario, load_scenario, unit_load

NO_CHANGE = 0  # a kind's choice that keeps its plan as it is


def _squash(x):
    """Pull numbers that span many orders of magnitude close to 0, so a neural network can handle them"""
    return np.sign(x) * np.log1p(np.abs(x)) / 10


@dataclasses.dataclass(frozen=True)
class Kind:
    """Machines of one category that have at least one recipe that can run"""

    category: str
    machines: tuple[int, ...]  # machine indexes
    recipes: tuple[int, ...]  # recipe indexes that can ever run
    slots: slice  # where this kind's recipes sit in the observation's per-slot numbers

    @property
    def moves(self) -> tuple[tuple[int, int], ...]:
        """(from, to) positions in recipes; choice i (from 1) is moves[i - 1]"""
        n = len(self.recipes)
        return tuple((a, b) for a in range(n) for b in range(n) if a != b)


class FactoryEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(
        self,
        scenario: Scenario | str | Path = DEFAULT_SCENARIO,
        *,
        horizon: int | None = None,
        ticks_per_action: int = 1,
        visible_orders: int = 20,
        reward_scale: float = 0.01,
        move_cost: float = 0.0,
        order_slack: bool = False,
    ):
        """
        :param horizon: overrides the scenario's seconds per episode
        :param ticks_per_action: seconds simulated after each action. Fewer decisions make learning easier
        :param visible_orders: how many of the earliest-due known orders go into the observation
        :param move_cost: taken off the reward (in cash units) for every machine moved in the plan, to discourage
            needless changeovers. Only the reward pays it; cash and profit don't change.
        :param order_slack: also show, for each visible order, the time to spare once it and the earlier orders
            that still fit are made (see order_slack()). Changes the observation, so models trained with and
            without it can't be swapped.
        """
        if not isinstance(scenario, Scenario):
            scenario = load_scenario(scenario)
        if horizon is not None:
            scenario = dataclasses.replace(scenario, horizon=horizon)

        self.sim = FactorySim(scenario)
        self.ticks_per_action = ticks_per_action
        self.visible_orders = visible_orders
        self.reward_scale = reward_scale
        self.move_cost = move_cost
        self.order_slack = order_slack

        sc = scenario
        kinds, start = [], 0
        for cat in dict.fromkeys(m.category for m in sc.machines):
            recipes = tuple(r for r in sc.recipes_for(cat) if sc.can_ever_run(r))
            if recipes:
                machines = tuple(i for i, m in enumerate(sc.machines) if m.category == cat)
                kinds.append(Kind(cat, machines, recipes, slice(start, start + len(recipes))))
                start += len(recipes)
        self.kinds = tuple(kinds)
        self.slot_recipe = np.array([r for k in self.kinds for r in k.recipes])
        self.slot_size = np.array([len(k.machines) for k in self.kinds for _ in k.recipes])
        self.action_space = spaces.MultiDiscrete([1 + len(k.moves) for k in self.kinds])

        # Stock is also shown in "batches": stock / the most any recipe uses per batch (for products: the largest
        # order). Log scale alone hides the difference between 3 and 5 screws, which decides whether a machine starts.
        unit = self.sim.recipe_in.max(axis=0)
        biggest_order = max([o.quantity for o in sc.orders] + list(sc.random_orders.quantity_range if sc.random_orders else [1]))
        self.stock_unit = np.where(unit > 0, unit, biggest_order)

        self._product_index = {p: i for i, p in enumerate(sc.products)}
        # [product, kind]: seconds of the whole kind's time one unit needs (machine seconds / machines of that kind)
        load = unit_load(sc)
        cats = list(dict.fromkeys(m.category for m in sc.machines))
        n_cat = [sum(m.category == c for m in sc.machines) for c in cats]
        self._unit_seconds = np.array([[load[p].get(c, 0.0) / n for c, n in zip(cats, n_cat)] for p in sc.products])
        n_rcp = len(sc.recipes)
        obs_dim = (
            1  # time progress
            + 2 * len(sc.materials)  # stock: log scale, and in batches
            + 2 * len(self.slot_recipe)  # per slot: machines on that recipe now, and planned
            + self.sim.n_machines * (n_rcp + 4)  # recipe (including stop), batch left, changeover left, waiting for inputs
            + len(sc.products)  # units still ordered per product, over all known orders
            + visible_orders * (len(sc.products) + 2 + order_slack)  # product, quantity, time until due, [slack]
        )
        # Every value is already squashed close to 0; even _squash(1e40) is only about 9
        self.observation_space = spaces.Box(-10, 10, (obs_dim,), np.float32)
        self.plan: list[np.ndarray] = []
        self._unreached: set[int] = set()  # kinds whose machines don't match their plan yet

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.sim.reset(seed=int(self.np_random.integers(2**31)))
        # Machines that start stopped are left out of the plan, and moves keep its total, so they stay stopped
        self.plan = [self._current_counts(k) for k in self.kinds]
        self._unreached.clear()
        return self._obs(), self._info()

    def step(self, action):
        moves = self.set_plan(action)
        cash_change = 0.0
        for _ in range(self.ticks_per_action):
            cash_change += self.sim.step(self.switches()).cash_change
            if self.sim.done:
                break
        reward = (cash_change - moves * self.move_cost) * self.reward_scale
        return self._obs(), reward, self.sim.done, False, self._info()

    def set_plan(self, action) -> int:
        """Apply each kind's move to the plan; returns how many machines were moved"""
        moves = 0
        for i, (k, choice) in enumerate(zip(self.kinds, np.asarray(action, dtype=int))):
            if choice == NO_CHANGE:
                continue
            a, b = k.moves[choice - 1]
            if self.plan[i][a] == 0:  # masked out; ignored if it comes anyway
                continue
            self.plan[i][a] -= 1
            self.plan[i][b] += 1
            self._unreached.add(i)
            moves += 1
        return moves

    def start_action(self) -> np.ndarray:
        """The action that keeps the starting plan, i.e. plays like the keep rule"""
        return np.full(len(self.kinds), NO_CHANGE)

    def _current_counts(self, k: Kind) -> np.ndarray:
        on = self.sim.state.recipe[list(k.machines)]
        return np.array([np.count_nonzero(on == r) for r in k.recipes])

    def switches(self) -> dict[int, int]:
        """{machine: new recipe} for idle machines that move toward the plan this second"""
        if not self._unreached:  # recipes only change here, so a reached plan stays reached until the next one
            return {}
        s, idle = self.sim.state, self.sim.idle
        changes = {}
        for i in list(self._unreached):
            k = self.kinds[i]
            missing = self.plan[i] - self._current_counts(k)
            if not (missing > 0).any():
                self._unreached.discard(i)
                continue
            for m in k.machines:
                r = s.recipe[m]
                pos = k.recipes.index(r) if r in k.recipes else None
                surplus = pos is None or missing[pos] < 0  # stopped, unplanned recipe, or too many on it
                if idle[m] and surplus:
                    target = int(np.argmax(missing))
                    if missing[target] <= 0:
                        break
                    changes[m] = k.recipes[target]
                    missing[target] -= 1
                    if pos is not None:
                        missing[pos] += 1
        return changes

    def action_masks(self) -> np.ndarray:
        """Per kind: "no change" is always allowed; a move only from a recipe that has a planned machine"""
        if not self.kinds:
            return np.zeros(0, dtype=bool)
        return np.concatenate([[True, *(p[a] > 0 for a, _ in k.moves)] for k, p in zip(self.kinds, self.plan)])

    def _obs(self) -> np.ndarray:
        s, sc, sim = self.sim.state, self.sim.scenario, self.sim
        n_rcp = len(sc.recipes)

        # STOP = -1 picks the last row of the identity matrix
        recipe_onehot = np.eye(n_rcp + 1)[s.recipe]
        progress = s.remaining / sim.cycle_time[s.recipe]
        setup = s.setup / max(sc.changeover_time, 1)
        has_inputs = np.all(s.stock >= sim.recipe_in[s.recipe], axis=1)
        waiting = sim.idle & (s.recipe != STOP) & ~has_inputs

        now = np.concatenate([self._current_counts(k) for k in self.kinds]) if self.kinds else np.zeros(0)
        planned = np.concatenate(self.plan) if self.kinds else now

        known = [o for o in s.orders if o.known_time <= s.clock]
        demand = np.zeros(len(sc.products))
        for o in known:
            demand[self._product_index[o.product]] += o.quantity
        n_p = len(sc.products)
        orders = np.zeros((self.visible_orders, n_p + 2 + self.order_slack))
        for row, o in zip(orders, known[: self.visible_orders]):
            row[self._product_index[o.product]] = 1
            row[n_p] = _squash(o.quantity)
            row[n_p + 1] = (o.due_time - s.clock) / sc.horizon
        if self.order_slack:
            orders[: len(known), -1] = self.order_slack_seconds(known[: self.visible_orders]) / sc.horizon

        return np.concatenate(
            [
                [s.clock / sc.horizon],
                _squash(s.stock),
                np.minimum(s.stock / self.stock_unit, 10) / 10,
                now / self.slot_size,
                planned / self.slot_size,
                np.column_stack([recipe_onehot, progress, setup, waiting]).ravel(),
                _squash(demand),
                orders.ravel(),
            ]
        ).clip(-10, 10).astype(np.float32)

    def order_slack_seconds(self, orders) -> np.ndarray:
        """For orders sorted by due time: seconds to spare at each order's due time if the factory makes that order
        and the earlier ones that fit, from the finished products in stock, at full speed on every machine kind.
        Negative means the order doesn't fit; it is then left out for the orders after it, as the factory will
        miss it anyway. A rough guide (it ignores parts in stock, waiting and changeovers), not a plan."""
        s, sc = self.sim.state, self.sim.scenario
        stock = np.array([s.stock[sc.material_index[p]] for p in sc.products])
        taken = np.zeros(len(sc.products))  # units of the orders that fit so far
        slack = np.zeros(len(orders))
        for i, o in enumerate(orders):
            p = self._product_index[o.product]
            taken[p] += o.quantity
            busy = (np.maximum(taken - stock, 0) @ self._unit_seconds).max(initial=0.0)
            slack[i] = o.due_time - s.clock - busy
            if slack[i] < 0:
                taken[p] -= o.quantity
        return slack

    def _info(self) -> dict:
        return {"clock": self.sim.state.clock, "cash": self.sim.state.cash}

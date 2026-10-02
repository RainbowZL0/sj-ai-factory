"""Wraps FactorySim as a Gymnasium environment for reinforcement learning.

Action: a plan for how many machines of each kind run each recipe.
    One integer per "slot" (a machine kind + a recipe it can run), from 0 to the number of machines of that kind.
    The numbers of one kind are scaled to the machines available (largest remainder), so any action is valid.
    If every number of a kind is 0, that kind keeps its previous plan; a fresh episode starts with no plan,
    meaning no machine switches (the keep rule).
    Recipes that can never run (an input can never be obtained) get no slot; kinds with no slot are left alone.

Carrying out the plan, every second: an idle machine whose recipe has more machines than planned (or that is
stopped) switches to the recipe furthest below its planned number. Busy machines switch after their batch,
so the plan is reached with as few switches, and changeovers, as possible.

Reward: cash change during the action × reward_scale.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from sjfactory.sim import STOP, FactorySim
from sjfactory.spec import DEFAULT_SCENARIO, Scenario, load_scenario

NO_CHANGE = 0  # an all-zero action keeps the previous plan


def _squash(x):
    """Pull numbers that span many orders of magnitude close to 0, so a neural network can handle them"""
    return np.sign(x) * np.log1p(np.abs(x)) / 10


def allocate(weights: np.ndarray, n: int) -> np.ndarray:
    """Split n machines over recipes in proportion to weights; leftovers go to the largest fractions, then by order"""
    quota = weights / weights.sum() * n
    counts = np.floor(quota).astype(int)
    order = np.argsort(-(quota - counts), kind="stable")
    counts[order[: n - counts.sum()]] += 1
    return counts


@dataclasses.dataclass(frozen=True)
class Kind:
    """Machines of one category that have at least one recipe that can run"""

    category: str
    machines: tuple[int, ...]  # machine indexes
    recipes: tuple[int, ...]  # recipe indexes that can ever run
    slots: slice  # where this kind's numbers sit in the action


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
    ):
        """
        :param horizon: overrides the scenario's seconds per episode
        :param ticks_per_action: seconds simulated after each action. Fewer decisions make learning easier
        :param visible_orders: how many of the earliest-due orders go into the observation
        """
        if not isinstance(scenario, Scenario):
            scenario = load_scenario(scenario)
        if horizon is not None:
            scenario = dataclasses.replace(scenario, horizon=horizon)

        self.sim = FactorySim(scenario)
        self.ticks_per_action = ticks_per_action
        self.visible_orders = visible_orders
        self.reward_scale = reward_scale

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
        self.action_space = spaces.MultiDiscrete(self.slot_size + 1)

        # Stock is also shown in "batches": stock / the most any recipe uses per batch (for products: the largest
        # order). Log scale alone hides the difference between 3 and 5 screws, which decides whether a machine starts.
        unit = self.sim.recipe_in.max(axis=0)
        biggest_order = max([o.quantity for o in sc.orders] + list(sc.random_orders.quantity_range if sc.random_orders else [1]))
        self.stock_unit = np.where(unit > 0, unit, biggest_order)

        self._product_index = {p: i for i, p in enumerate(sc.products)}
        n_rcp = len(sc.recipes)
        obs_dim = (
            1  # time progress
            + 2 * len(sc.materials)  # stock: log scale, and in batches
            + 2 * len(self.slot_recipe)  # per slot: machines on that recipe now, and planned
            + self.sim.n_machines * (n_rcp + 4)  # recipe (including stop), batch left, changeover left, waiting for inputs
            + visible_orders * (len(sc.products) + 2)  # product, quantity, time until due
        )
        # Every value is already squashed close to 0; even _squash(1e40) is only about 9
        self.observation_space = spaces.Box(-10, 10, (obs_dim,), np.float32)
        self.plan: list[np.ndarray | None] = [None] * len(self.kinds)
        self._unreached: set[int] = set()  # kinds whose machines don't match their plan yet

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.sim.reset(seed=int(self.np_random.integers(2**31)))
        self.plan = [None] * len(self.kinds)
        self._unreached.clear()
        return self._obs(), self._info()

    def step(self, action):
        self.set_plan(action)
        cash_change = 0.0
        for _ in range(self.ticks_per_action):
            cash_change += self.sim.step(self.switches()).cash_change
            if self.sim.done:
                break
        reward = cash_change * self.reward_scale
        return self._obs(), reward, self.sim.done, False, self._info()

    def set_plan(self, action):
        action = np.asarray(action, dtype=int)
        for i, k in enumerate(self.kinds):
            weights = action[k.slots]
            if weights.sum() > 0:
                self.plan[i] = allocate(weights, len(k.machines))
                self._unreached.add(i)

    def start_action(self) -> np.ndarray:
        """The action that plans the machines' starting recipes, i.e. plays like the keep rule"""
        sc = self.sim.scenario
        recipe = np.array([sc.recipe_index.get(m.initial_recipe, STOP) for m in sc.machines])
        return np.concatenate([self._counts(k, recipe) for k in self.kinds]) if self.kinds else np.zeros(0, int)

    def _current_counts(self, k: Kind) -> np.ndarray:
        return self._counts(k, self.sim.state.recipe)

    @staticmethod
    def _counts(k: Kind, recipe: np.ndarray) -> np.ndarray:
        on = recipe[list(k.machines)]
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
        """Every action is valid; kept so MaskablePPO and the shared policy interface work unchanged"""
        return np.ones(int(self.action_space.nvec.sum()), dtype=bool)

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
        planned = np.concatenate([now[k.slots] if p is None else p for k, p in zip(self.kinds, self.plan)]) if self.kinds else now

        orders = np.zeros((self.visible_orders, len(sc.products) + 2))
        for row, o in zip(orders, s.orders[: self.visible_orders]):
            row[self._product_index[o.product]] = 1
            row[-2] = _squash(o.quantity)
            row[-1] = (o.due_time - s.clock) / sc.horizon

        return np.concatenate(
            [
                [s.clock / sc.horizon],
                _squash(s.stock),
                np.minimum(s.stock / self.stock_unit, 10) / 10,
                now / self.slot_size,
                planned / self.slot_size,
                np.column_stack([recipe_onehot, progress, setup, waiting]).ravel(),
                orders.ravel(),
            ]
        ).clip(-10, 10).astype(np.float32)

    def _info(self) -> dict:
        return {"clock": self.sim.state.clock, "cash": self.sim.state.cash}

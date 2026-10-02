"""Wraps FactorySim as a Gymnasium environment for reinforcement learning.

Action: one integer per machine
    0    = keep. A running machine carries on; an idle one starts its current recipe once inputs are in stock
    1    = stop
    2+k  = switch to the k-th recipe this machine can run
Only idle machines may choose 1 or 2+k. action_masks() hides the rest; if one arrives anyway it is treated as 0.

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

KEEP = 0
STOP_CHOICE = 1
FIRST_RECIPE_CHOICE = 2


def _squash(x):
    """Pull numbers that span many orders of magnitude close to 0, so a neural network can handle them"""
    return np.sign(x) * np.log1p(np.abs(x)) / 10


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
        self.n_choices = FIRST_RECIPE_CHOICE + max(len(a) for a in self.sim.allowed)
        self.action_space = spaces.MultiDiscrete([self.n_choices] * self.sim.n_machines)

        self._product_index = {p: i for i, p in enumerate(sc.products)}
        n_rcp = len(sc.recipes)
        obs_dim = (
            2  # time progress, cash
            + len(sc.materials)  # stock
            + self.sim.n_machines * (n_rcp + 2)  # assigned recipe (including stop) + fraction of batch left
            + visible_orders * (len(sc.products) + 2)  # product, quantity, time until due
        )
        # Every value is already squashed close to 0; even _squash(1e40) is only about 9
        self.observation_space = spaces.Box(-10, 10, (obs_dim,), np.float32)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.sim.reset(seed=int(self.np_random.integers(2**31)))
        return self._obs(), self._info()

    def step(self, action):
        changes = self.decode(action)
        cash_change = 0.0
        for _ in range(self.ticks_per_action):
            cash_change += self.sim.step(changes).cash_change
            changes = None  # the action applies only in the first second; after that it is "keep"
            if self.sim.done:
                break
        reward = cash_change * self.reward_scale
        return self._obs(), reward, self.sim.done, False, self._info()

    def decode(self, action) -> dict[int, int]:
        """Action array -> {machine index: recipe index or STOP}.

        Choices the mask hides (machine busy, or no such recipe) are treated as "keep",
        so algorithms that ignore the mask can still use this environment.
        """
        changes = {}
        idle = self.sim.state.remaining == 0
        for m, a in enumerate(np.asarray(action, dtype=int)):
            if a == KEEP or not idle[m]:
                continue
            if a == STOP_CHOICE:
                changes[m] = STOP
            elif a - FIRST_RECIPE_CHOICE < len(self.sim.allowed[m]):
                changes[m] = self.sim.allowed[m][a - FIRST_RECIPE_CHOICE]
        return changes

    def action_masks(self) -> np.ndarray:
        """The format MaskablePPO expects: every machine's allowed choices joined into one boolean array"""
        mask = np.zeros((self.sim.n_machines, self.n_choices), dtype=bool)
        mask[:, KEEP] = True
        for m in np.flatnonzero(self.sim.state.remaining == 0):
            mask[m, STOP_CHOICE] = True
            mask[m, FIRST_RECIPE_CHOICE : FIRST_RECIPE_CHOICE + len(self.sim.allowed[m])] = True
        return mask.ravel()

    def _obs(self) -> np.ndarray:
        s, sc, sim = self.sim.state, self.sim.scenario, self.sim
        n_rcp = len(sc.recipes)

        # STOP = -1 picks the last row of the identity matrix
        recipe_onehot = np.eye(n_rcp + 1)[s.recipe]
        progress = s.remaining / sim.cycle_time[s.recipe]

        orders = np.zeros((self.visible_orders, len(sc.products) + 2))
        for row, o in zip(orders, s.orders[: self.visible_orders]):
            row[self._product_index[o.product]] = 1
            row[-2] = _squash(o.quantity)
            row[-1] = (o.due_time - s.clock) / sc.horizon

        return np.concatenate(
            [
                [s.clock / sc.horizon, _squash(s.cash)],
                _squash(s.stock),
                np.column_stack([recipe_onehot, progress]).ravel(),
                orders.ravel(),
            ]
        ).clip(-10, 10).astype(np.float32)

    def _info(self) -> dict:
        return {"clock": self.sim.state.clock, "cash": self.sim.state.cash}

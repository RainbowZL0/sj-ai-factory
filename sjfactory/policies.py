"""Decision rules. All share one interface: look at the observation and the allowed-action mask, return an action."""

from __future__ import annotations

from typing import Protocol

import numpy as np
from gymnasium import spaces

from sjfactory.env import KEEP


class Policy(Protocol):
    def act(self, obs: np.ndarray, mask: np.ndarray) -> np.ndarray: ...


class KeepPolicy:
    """Never switches recipes: each machine keeps its starting recipe and starts whenever inputs are in stock
    (the old code's "greedy" mode)"""

    def __init__(self, action_space: spaces.MultiDiscrete):
        self.n_machines = len(action_space.nvec)

    def act(self, obs, mask):
        return np.full(self.n_machines, KEEP)


class RandomPolicy:
    """With probability change_prob, an idle machine picks a random allowed action; otherwise it keeps"""

    def __init__(self, action_space: spaces.MultiDiscrete, change_prob=0.02, seed=None):
        self.nvec = action_space.nvec
        self.change_prob = change_prob
        self.rng = np.random.default_rng(seed)

    def act(self, obs, mask):
        mask = mask.reshape(len(self.nvec), -1)
        action = np.full(len(self.nvec), KEEP)
        for m, row in enumerate(mask):
            choices = np.flatnonzero(row)
            if len(choices) > 1 and self.rng.random() < self.change_prob:
                action[m] = self.rng.choice(choices)
        return action


class ModelPolicy:
    """Wraps a trained MaskablePPO model"""

    def __init__(self, model, deterministic=True):
        self.model = model
        self.deterministic = deterministic

    def act(self, obs, mask):
        action, _ = self.model.predict(
            obs, action_masks=mask, deterministic=self.deterministic
        )
        return action

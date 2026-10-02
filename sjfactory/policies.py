"""Decision rules. All share one interface: look at the observation and the allowed-action mask, return an action."""

from __future__ import annotations

from typing import Protocol

import numpy as np
from gymnasium import spaces

from sjfactory.env import NO_CHANGE


class Policy(Protocol):
    def act(self, obs: np.ndarray, mask: np.ndarray) -> np.ndarray: ...


class KeepPolicy:
    """Never makes a plan, so no machine switches: each keeps its starting recipe and starts whenever inputs are
    in stock (the old code's "greedy" mode)"""

    def __init__(self, action_space: spaces.MultiDiscrete):
        self.n_slots = len(action_space.nvec)

    def act(self, obs, mask):
        return np.full(self.n_slots, NO_CHANGE)


class RandomPolicy:
    """With probability change_prob per decision, makes a random plan; otherwise keeps the previous one"""

    def __init__(self, action_space: spaces.MultiDiscrete, change_prob=0.1, seed=None):
        self.nvec = action_space.nvec
        self.change_prob = change_prob
        self.rng = np.random.default_rng(seed)

    def act(self, obs, mask):
        if self.rng.random() < self.change_prob:
            return self.rng.integers(0, self.nvec)
        return np.full(len(self.nvec), NO_CHANGE)


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

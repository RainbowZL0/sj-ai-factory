"""Run whole episodes with a policy and collect their results. Used by the command line and the training monitor."""

from __future__ import annotations

from collections.abc import Callable, Iterable

import numpy as np

from sjfactory.env import FactoryEnv
from sjfactory.policies import KeepPolicy, ModelPolicy, RandomPolicy
from sjfactory.recorder import Recorder

BASELINES = ("keep", "random")

# Two ways to play a trained model. "fixed": every machine takes its most likely choice.
# "sampled": choices are drawn from the model's probabilities, as during training, with the draws seeded.
MODEL_MODES = ("fixed", "sampled")


def run_episode(env: FactoryEnv, policy, seed=None) -> Recorder:
    with Recorder(env.sim) as rec:
        obs, _ = env.reset(seed=seed)
        done = False
        while not done:
            obs, _, terminated, truncated, _ = env.step(policy.act(obs, env.action_masks()))
            done = terminated or truncated
    return rec


def baseline_policy(name: str, env: FactoryEnv, seed=0):
    if name == "keep":
        return KeepPolicy(env.action_space)
    if name == "random":
        return RandomPolicy(env.action_space, seed=seed)
    raise ValueError(f"unknown baseline policy: {name}")


def evaluate(env: FactoryEnv, make_policy: Callable[[], object], seeds: Iterable[int]) -> list[Recorder]:
    """One episode per seed. A fresh policy per episode, so random policies repeat exactly."""
    return [run_episode(env, make_policy(), seed=s) for s in seeds]


def model_episodes(env: FactoryEnv, model, seeds: Iterable[int], mode: str) -> list[Recorder]:
    """One episode per seed with a trained model. In "sampled" mode the random draws are seeded too, so a
    test repeats exactly, and the training's own random state is left untouched."""
    import torch

    recs = []
    for s in seeds:
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(s)
            recs.append(run_episode(env, ModelPolicy(model, deterministic=mode == "fixed"), seed=s))
    return recs


def cash_curve(rec: Recorder, max_points=1000) -> dict:
    """Cash over time, thinned to at most max_points so pages stay small"""
    t, cash = rec.time, np.asarray(rec.cash)
    step = max(1, len(t) // max_points)
    idx = np.r_[np.arange(0, len(t), step), len(t) - 1] if len(t) else np.array([], dtype=int)
    idx = np.unique(idx)
    return {"time": t[idx].tolist(), "cash": cash[idx].tolist()}

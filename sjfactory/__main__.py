"""Command-line entry point.

uv run python -m sjfactory run --policy keep
uv run python -m sjfactory train --steps 200000
uv run python -m sjfactory eval runs/<time>-train/model.zip
"""

from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path

from sjfactory.env import FactoryEnv
from sjfactory.policies import KeepPolicy, ModelPolicy, RandomPolicy
from sjfactory.recorder import Recorder
from sjfactory.spec import DEFAULT_SCENARIO, PROJECT_ROOT

RUNS_DIR = PROJECT_ROOT / "runs"


def new_run_dir(tag: str) -> Path:
    path = RUNS_DIR / f"{datetime.datetime.now():%m%d_%H%M%S}-{tag}"
    path.mkdir(parents=True)
    return path


def run_episode(env: FactoryEnv, policy, seed=None) -> Recorder:
    with Recorder(env.sim) as rec:
        obs, _ = env.reset(seed=seed)
        done = False
        while not done:
            obs, _, terminated, truncated, _ = env.step(policy.act(obs, env.action_masks()))
            done = terminated or truncated
    return rec


def finish(rec: Recorder, out: Path):
    rec.save(out)
    summary = rec.summary()
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Results saved to {out}")


def make_env(args) -> FactoryEnv:
    return FactoryEnv(args.scenario, horizon=args.horizon, ticks_per_action=args.ticks)


def cmd_run(args):
    env = make_env(args)
    if args.policy == "keep":
        policy = KeepPolicy(env.action_space)
    else:
        policy = RandomPolicy(env.action_space, seed=args.seed)
    finish(run_episode(env, policy, seed=args.seed), new_run_dir(args.policy))


def cmd_train(args):
    from sb3_contrib import MaskablePPO
    from stable_baselines3.common.env_util import make_vec_env

    out = new_run_dir("train")
    vec_env = make_vec_env(lambda: make_env(args), n_envs=args.envs, seed=args.seed)
    model = MaskablePPO(
        "MlpPolicy",
        vec_env,
        learning_rate=3e-4,
        n_steps=1024,
        batch_size=256,
        gamma=args.gamma,
        verbose=1,
        seed=args.seed,
        tensorboard_log=str(out / "tb"),
    )
    model.learn(total_timesteps=args.steps)
    model.save(out / "model")
    finish(run_episode(make_env(args), ModelPolicy(model), seed=args.seed), out)


def cmd_eval(args):
    from sb3_contrib import MaskablePPO

    model = MaskablePPO.load(args.model)
    finish(run_episode(make_env(args), ModelPolicy(model), seed=args.seed), new_run_dir("eval"))


def main():
    p = argparse.ArgumentParser(prog="sjfactory")
    p.add_argument("--scenario", default=str(DEFAULT_SCENARIO))
    p.add_argument("--horizon", type=int, default=None, help="override the scenario's seconds per episode")
    p.add_argument("--seed", type=int, default=0)
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run one episode with a fixed rule")
    r.add_argument("--policy", choices=["keep", "random"], default="keep")
    r.add_argument("--ticks", type=int, default=1, help="seconds simulated after each decision")
    r.set_defaults(func=cmd_run)

    t = sub.add_parser("train", help="train with MaskablePPO")
    t.add_argument("--steps", type=int, default=200_000)
    t.add_argument("--envs", type=int, default=4)
    t.add_argument("--ticks", type=int, default=10, help="seconds simulated after each decision")
    t.add_argument("--gamma", type=float, default=0.995)
    t.set_defaults(func=cmd_train)

    e = sub.add_parser("eval", help="run one episode with a trained model")
    e.add_argument("model")
    e.add_argument("--ticks", type=int, default=10)
    e.set_defaults(func=cmd_eval)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

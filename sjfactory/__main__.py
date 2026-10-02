"""Command-line entry point.

uv run python -m sjfactory run --policy keep
uv run python -m sjfactory train --steps 1000000 --note "what I changed"
uv run python -m sjfactory eval runs/<time>-train/best_model.zip --mode sampled
uv run python -m sjfactory view                 # open the page listing all runs
uv run python -m sjfactory check [models ...]   # machine load, keep, oracle and upper bound, no training
uv run python -m sjfactory bench [models ...]   # check on the fixed set of test days, one line per policy
"""

from __future__ import annotations

import argparse
import datetime
import json
import webbrowser
from pathlib import Path

from sjfactory import web
from sjfactory.env import FactoryEnv
from sjfactory.evaluate import (
    BASELINES, MODEL_MODES, baseline_policy, cash_curve, evaluate, model_env_options, model_episodes, run_episode,
)
from sjfactory.recorder import Recorder
from sjfactory.spec import DEFAULT_SCENARIO, PROJECT_ROOT

RUNS_DIR = PROJECT_ROOT / "runs"


def new_run_dir(tag: str) -> Path:
    path = RUNS_DIR / f"{datetime.datetime.now():%m%d_%H%M%S}-{tag}"
    path.mkdir(parents=True)
    return path


def open_page(path: Path, args):
    print(f"Page: {path}")
    if not args.no_open:
        webbrowser.open(path.resolve().as_uri())


def finish(rec: Recorder, out: Path, policy: str, args) -> Path:
    """Save files, run the fixed rules on the same orders for comparison, and write the report page"""
    rec.save(out)
    summary = rec.summary()
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))

    refs = {}
    for name in BASELINES:
        if name != policy:
            env = make_env(args)
            refs[name] = run_episode(env, baseline_policy(name, env, args.seed), seed=args.seed)
    report = web.write_report(out, rec, policy, refs, note=getattr(args, "note", ""), seed=args.seed)
    web.write_index(RUNS_DIR)
    print(f"Results saved to {out}")
    return report


def make_env(args) -> FactoryEnv:
    return FactoryEnv(
        args.scenario, horizon=args.horizon, ticks_per_action=args.ticks, move_cost=getattr(args, "move_cost", 0.0),
        order_slack=getattr(args, "order_slack", False),
    )


def base_config(args, kind: str, env: FactoryEnv) -> dict:
    return {
        "kind": kind,
        "created": datetime.datetime.now().isoformat(timespec="seconds"),
        "note": args.note,
        "scenario": args.scenario,
        "horizon": env.sim.scenario.horizon,
        "seed": args.seed,
        "ticks": args.ticks,
        "initial_cash": env.sim.scenario.initial_cash,
        "reward_scale": env.reward_scale,
    }


def cmd_run(args):
    env = make_env(args)
    out = new_run_dir(args.policy)
    web.write_config(out, **base_config(args, args.policy, env))
    rec = run_episode(env, baseline_policy(args.policy, env, args.seed), seed=args.seed)
    open_page(finish(rec, out, args.policy, args), args)


def cmd_train(args):
    import torch
    from sb3_contrib import MaskablePPO
    from stable_baselines3.common.env_util import make_vec_env
    from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv
    from stable_baselines3.common.logger import configure
    from stable_baselines3.common.vec_env import VecNormalize

    from sjfactory.training import TrainingMonitor

    out = new_run_dir("train")
    eval_env = make_env(args)
    seeds = list(range(args.test_seed, args.test_seed + args.tests))
    web.write_config(
        out,
        **base_config(args, "train", eval_env),
        steps=args.steps,
        envs=args.envs,
        rollout=args.rollout,
        torch_threads=args.torch_threads,
        gamma=args.gamma,
        keep_bias=args.keep_bias,
        move_cost=args.move_cost,
        order_slack=args.order_slack,
        test_seeds=seeds,
    )

    # Fixed rules on the test orders: the lines the model has to beat
    baselines = {}
    for name in BASELINES:
        recs = evaluate(eval_env, lambda: baseline_policy(name, eval_env, args.seed), seeds)
        sums = [r.summary() for r in recs]
        baselines[name] = {
            key: sum(s[key] for s in sums) / len(sums) for key in ("profit", "fill_rate", "machine_busy_ratio")
        }
        baselines[name]["curve"] = cash_curve(recs[0])
    (out / "baselines.json").write_text(json.dumps(baselines), encoding="utf-8")
    print("Baselines on the test orders: " + ", ".join(f"{k} profit {v['profit']:,.0f}" for k, v in baselines.items()))

    web.write_training_page(out)
    web.write_index(RUNS_DIR)
    open_page(out / "training.html", args)

    # The model is small, so extra PyTorch threads mostly wait on each other; the cores are better spent simulating
    torch.set_num_threads(args.torch_threads)
    # Each environment runs in its own process, so the simulations run at the same time on separate cores
    vec_env = make_vec_env(
        lambda: make_env(args), n_envs=args.envs, seed=args.seed,
        vec_env_cls=SubprocVecEnv if args.envs > 1 else DummyVecEnv,
    )
    # Rewards are rescaled by a running estimate of their spread, so the reward predictions stay in a steady range.
    # Observations are already scaled by the environment and are left alone, so a saved model needs no extra files.
    vec_env = VecNormalize(vec_env, norm_obs=False, norm_reward=True, gamma=args.gamma)
    model = MaskablePPO(
        "MlpPolicy",
        vec_env,
        learning_rate=3e-4,
        n_steps=max(64, args.rollout // args.envs),  # steps per environment between updates
        batch_size=256,
        gamma=args.gamma,
        verbose=0,
        seed=args.seed,
    )
    # Optionally start close to the keep rule. A fresh model picks every choice almost evenly, so it moves
    # machines often, paying a changeover each time. With the bias, "no change" is e^keep_bias times as likely
    # as any single move, so a fresh model's most likely action is to keep the plan.
    with torch.no_grad():
        bias, start = model.policy.action_net.bias, 0
        for size, choice in zip(eval_env.action_space.nvec, eval_env.start_action()):
            bias[start + choice] += args.keep_bias
            start += size
    # progress.csv feeds the "learning health" charts; TensorBoard still works on the same folder
    model.set_logger(configure(str(out / "logs"), ["csv", "tensorboard"]))
    every = args.test_every or max(args.steps // 20, args.rollout)
    monitor = TrainingMonitor(out, eval_env, seeds, every)
    try:
        model.learn(total_timesteps=args.steps, callback=monitor)
    except KeyboardInterrupt:
        print("Stopped early; keeping what was learned so far.")
        monitor._write_status(done=True)
    model.save(out / "model")
    web.write_training_page(out)

    # The report shows the best model found, on the first test seed, played in the mode that scored best
    best = MaskablePPO.load(out / "best_model") if (out / "best_model.zip").exists() else model
    args.seed = seeds[0]
    args.note = f"{args.note} (best model, played {monitor.best_mode}, first of test seeds {seeds[0]}-{seeds[-1]})".strip()
    finish(model_episodes(make_env(args), best, [seeds[0]], monitor.best_mode)[0], out, "model", args)
    web.write_training_page(out)


def cmd_eval(args):
    from sb3_contrib import MaskablePPO

    model = MaskablePPO.load(args.model)
    args.order_slack = model_env_options(args.model).get("order_slack", False)
    env = make_env(args)
    out = new_run_dir("eval")
    web.write_config(out, **base_config(args, "eval", env), model=str(args.model), mode=args.mode)
    rec = model_episodes(env, model, [args.seed], args.mode)[0]
    open_page(finish(rec, out, "model", args), args)


def cmd_view(args):
    if args.run:
        run = Path(args.run)
        if (run / "eval.csv").exists():
            web.write_training_page(run)
        page = run / ("training.html" if (run / "training.html").exists() else "report.html")
    else:
        page = web.write_index(RUNS_DIR)
    open_page(page, args)


def cmd_check(args):
    from sjfactory.check import run_check

    run_check(
        args.scenario, args.models, range(args.first_seed, args.first_seed + args.episodes), horizon=args.horizon,
        oracle_seconds=args.oracle_seconds, lookahead_minutes=args.lookahead_minutes, workers=args.workers,
    )


def cmd_bench(args):
    from sjfactory.check import run_bench

    run_bench(args.models, oracle_seconds=args.oracle_seconds, lookahead_minutes=args.lookahead_minutes,
              workers=args.workers)


def main():
    p = argparse.ArgumentParser(prog="sjfactory")
    p.add_argument("--scenario", default=str(DEFAULT_SCENARIO))
    p.add_argument("--horizon", type=int, default=None, help="override the scenario's seconds per episode")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--note", default="", help="short text shown on the pages, e.g. what you changed")
    p.add_argument("--no-open", action="store_true", help="don't open the result page in a browser")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run one episode with a fixed rule")
    r.add_argument("--policy", choices=list(BASELINES), default="keep")
    r.add_argument("--ticks", type=int, default=60, help="seconds simulated after each decision")
    r.set_defaults(func=cmd_run)

    t = sub.add_parser("train", help="train with MaskablePPO, with a live progress page")
    t.add_argument("--steps", type=int, default=1_000_000, help="decisions to train on")
    t.add_argument("--envs", type=int, default=20, help="environments simulated in parallel, one process each")
    t.add_argument("--rollout", type=int, default=4096, help="steps collected (over all environments) per update")
    t.add_argument("--torch-threads", type=int, default=1, help="PyTorch threads for the model update")
    t.add_argument("--ticks", type=int, default=60, help="seconds simulated after each decision")
    t.add_argument("--gamma", type=float, default=0.97, help="0.97 looks about 33 decisions (33 minutes) ahead")
    t.add_argument(
        "--move-cost", type=float, default=50.0,
        help="taken off the reward for each machine moved in the plan; profit is not affected",
    )
    t.add_argument("--keep-bias", type=float, default=0.0, help="how strongly a fresh model prefers the starting plan (0: no preference)")
    t.add_argument(
        "--order-slack", action="store_true",
        help="also show the model, per order, the time to spare once it and the earlier orders that fit are made",
    )
    t.add_argument("--tests", type=int, default=3, help="test episodes (seeds) per check")
    t.add_argument("--test-seed", type=int, default=1000, help="first test seed; tests use fixed orders")
    t.add_argument("--test-every", type=int, default=0, help="steps between checks (default: 20 checks per run)")
    t.set_defaults(func=cmd_train)

    e = sub.add_parser("eval", help="run one episode with a trained model")
    e.add_argument("model")
    e.add_argument("--ticks", type=int, default=60)
    e.add_argument(
        "--mode", choices=MODEL_MODES, default="fixed",
        help="fixed: always the most likely choice; sampled: random draws from the model's probabilities",
    )
    e.set_defaults(func=cmd_eval)

    v = sub.add_parser("view", help="rebuild and open the page of one run, or of all runs")
    v.add_argument("run", nargs="?", help="run folder; leave out to open the list of all runs")
    v.set_defaults(func=cmd_view)

    c = sub.add_parser("check", help="machine load, keep, oracle and upper bound in seconds; no training")
    c.add_argument("models", nargs="*", help="trained models to compare, played with their most likely choice")
    c.add_argument("--episodes", type=int, default=10, help="seeds checked, starting at --seed")
    c.add_argument("--oracle-seconds", type=int, default=30, help="time limit per oracle solve; 0 skips the oracle")
    c.add_argument("--lookahead-minutes", type=int, default=30, help="look-ahead planner's window; 0 skips it")
    c.add_argument("--workers", type=int, default=None, help="processes (default: one per episode, up to the cores)")
    c.add_argument("--first-seed", type=int, default=2000, help="first seed; no training run tests on 2000 and up")
    c.set_defaults(func=cmd_check)

    b = sub.add_parser("bench", help="check on the fixed set of test days; one share of the bound per kind of day")
    b.add_argument("models", nargs="*", help="trained models; each plays the scenarios it fits")
    b.add_argument("--oracle-seconds", type=int, default=30, help="time limit per oracle solve; 0 skips the oracle")
    b.add_argument("--lookahead-minutes", type=int, default=0, help="look-ahead planner's window; 0 (default) skips it")
    b.add_argument("--workers", type=int, default=None, help="processes (default: one per episode, up to the cores)")
    b.set_defaults(func=cmd_bench)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

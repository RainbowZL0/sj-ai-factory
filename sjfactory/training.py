"""Watches a training run: every few thousand steps it tests the model on fixed orders and redraws training.html.

Files written to the run folder:
    baselines.json      keep and random policies on the test seeds (written before training, by the caller)
    eval.csv            one row per test episode: step, mode, seed, profit, fill_rate, busy, revenue, penalty
    latest_curve.json   cash over time of the latest test episodes on the first seed, one curve per mode
    status.json         current step, whether training has finished, and the best model's mode
    best_model.zip      the model with the best mean test profit so far, in either mode

Every check plays the model twice per seed: "fixed" (most likely choice) and "sampled" (random draws,
as in training). A big gap between the two means the model relies on chance to spread its choices.
"""

from __future__ import annotations

import csv
import json
import time
from collections.abc import Sequence
from pathlib import Path

import numpy as np
from stable_baselines3.common.callbacks import BaseCallback

from sjfactory import web
from sjfactory.env import FactoryEnv
from sjfactory.evaluate import MODEL_MODES, cash_curve, model_episodes

EVAL_FIELDS = ["step", "mode", "seed", "profit", "fill_rate", "busy", "revenue", "penalty"]


def eval_row(step: int, mode: str, seed: int, summary: dict) -> dict:
    return {
        "step": step,
        "mode": mode,
        "seed": seed,
        "profit": summary["profit"],
        "fill_rate": summary["fill_rate"],
        "busy": summary["machine_busy_ratio"],
        "revenue": summary["revenue"],
        "penalty": summary["penalty"],
    }


class TrainingMonitor(BaseCallback):
    def __init__(self, out: Path, eval_env: FactoryEnv, seeds: Sequence[int], every: int):
        super().__init__()
        self.out = Path(out)
        self.eval_env = eval_env
        self.seeds = list(seeds)
        self.every = every
        self.last_eval = -every
        self.best = -np.inf
        self.best_mode = MODEL_MODES[0]
        self.started = time.time()
        with open(self.out / "eval.csv", "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, EVAL_FIELDS).writeheader()

    def _on_training_start(self):
        self._evaluate()

    def _on_step(self) -> bool:
        if self.num_timesteps - self.last_eval >= self.every:
            self._evaluate()
        return True

    def _on_training_end(self):
        if self.num_timesteps != self.last_eval:
            self._evaluate()
        self._write_status(done=True)
        web.write_training_page(self.out)

    def _evaluate(self):
        self.last_eval = self.num_timesteps
        rows, curves, means = [], {}, {}
        for mode in MODEL_MODES:
            recs = model_episodes(self.eval_env, self.model, self.seeds, mode)
            mode_rows = [eval_row(self.num_timesteps, mode, s, r.summary()) for s, r in zip(self.seeds, recs)]
            rows += mode_rows
            curves[mode] = cash_curve(recs[0])
            means[mode] = {k: float(np.mean([r[k] for r in mode_rows])) for k in ("profit", "fill_rate", "busy")}
            for key, value in means[mode].items():
                self.logger.record(f"eval_{mode}/{key}", value)
        with open(self.out / "eval.csv", "a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, EVAL_FIELDS).writerows(rows)
        (self.out / "latest_curve.json").write_text(json.dumps(curves), encoding="utf-8")

        mode = max(MODEL_MODES, key=lambda m: means[m]["profit"])
        mark = ""
        if means[mode]["profit"] > self.best:
            self.best, self.best_mode = means[mode]["profit"], mode
            self.model.save(self.out / "best_model")
            mark = f"  (new best, {mode}; saved best_model.zip)"
        minutes = (time.time() - self.started) / 60
        scores = "  ".join(f"{m} {means[m]['profit']:>10,.0f} ({means[m]['fill_rate']:4.0%} shipped)" for m in MODEL_MODES)
        print(f"[test] step {self.num_timesteps:>9,}  profit: {scores}  {minutes:5.1f} min{mark}")

        self._write_status(done=False)
        web.write_training_page(self.out)

    def _write_status(self, done: bool):
        (self.out / "status.json").write_text(
            json.dumps({"step": self.num_timesteps, "done": done, "best_mode": self.best_mode}), encoding="utf-8"
        )

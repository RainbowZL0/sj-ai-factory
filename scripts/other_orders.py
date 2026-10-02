"""Check whether a trained model still beats keep on new seeds and on orders of a different shape.

uv run python scripts/other_orders.py runs/<folder>/best_model.zip [--scenario scenarios/casters.yaml]

Each row plays keep and the model (most likely choice, and sampled) on the same seeds and prints mean profits.
The rows change only the orders of the given scenario, so a model trained on varied.yaml is tested with
--scenario scenarios/casters.yaml (the same factory). See docs/experiments/06-other-orders.md.
"""

from __future__ import annotations

import argparse
import copy
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from ruamel.yaml import YAML

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sjfactory.env import FactoryEnv  # noqa: E402
from sjfactory.evaluate import baseline_policy, model_episodes, run_episode  # noqa: E402
from sjfactory.spec import DEFAULT_SCENARIO, scenario_from_dict  # noqa: E402

NEW_SEEDS = range(2000, 2030)


def variants(base: dict) -> dict[str, tuple[dict, range]]:
    """Order shapes to test. Products must still include both Motor and Frame so the observation keeps its
    size; listing a product several times makes it more likely to be drawn."""

    def variant(**random_orders):
        d = copy.deepcopy(base)
        d["orders"]["random"].update(random_orders)
        return d

    return {
        "training shape, test seeds 1000-1002": (variant(), range(1000, 1003)),
        "training shape, new seeds": (variant(), NEW_SEEDS),
        "fewer orders (25)": (variant(count=25), NEW_SEEDS),
        "more orders (100)": (variant(count=100), NEW_SEEDS),
        "bigger orders (5-20 units)": (variant(quantity=[5, 20]), NEW_SEEDS),
        "mostly Motor (80%)": (variant(products=["Motor"] * 4 + ["Frame"]), NEW_SEEDS),
        "mostly Frame (80%)": (variant(products=["Frame"] * 4 + ["Motor"]), NEW_SEEDS),
        "almost only Motor (99%)": (variant(products=["Motor"] * 99 + ["Frame"]), NEW_SEEDS),
        "almost only Frame (99%)": (variant(products=["Frame"] * 99 + ["Motor"]), NEW_SEEDS),
        "known 900-2400 s before due": (variant(notice=[900, 2400]), NEW_SEEDS),
        "tough: 100 orders of 5-20, 900-2400 s": (variant(count=100, quantity=[5, 20], notice=[900, 2400]), NEW_SEEDS),
    }


def play(job):
    """Keep, model most likely, model sampled on one seed: profits and shipped shares"""
    model_path, scenario, seed = job
    import torch
    from sb3_contrib import MaskablePPO

    torch.set_num_threads(1)
    env = FactoryEnv(scenario_from_dict(scenario), ticks_per_action=60)
    model = MaskablePPO.load(model_path, device="cpu")
    keep = run_episode(env, baseline_policy("keep", env), seed=seed).summary()
    fixed = model_episodes(env, model, [seed], "fixed")[0].summary()
    sampled = model_episodes(env, model, [seed], "sampled")[0].summary()
    return keep["profit"], fixed["profit"], sampled["profit"], keep["fill_rate"], fixed["fill_rate"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("model")
    p.add_argument("--scenario", default=str(DEFAULT_SCENARIO))
    p.add_argument("--workers", type=int, default=24, help="episodes played at the same time, one process each")
    args = p.parse_args()

    base = YAML(typ="safe").load(Path(args.scenario).read_text(encoding="utf-8"))
    print(f"model: {args.model}\nscenario: {args.scenario}")
    print(f"{'orders':38s} {'seeds':>5s} {'keep':>9s} {'model':>9s} {'sampled':>9s} {'model-keep':>10s} {'model<keep':>10s} {'shipped keep/model':>19s}")
    with ProcessPoolExecutor(args.workers) as pool:
        for name, (scenario, seeds) in variants(base).items():
            res = np.array(list(pool.map(play, [(args.model, scenario, s) for s in seeds])))
            keep, fixed, sampled, keep_fill, fixed_fill = res.T
            print(
                f"{name:38s} {len(seeds):5d} {keep.mean():9,.0f} {fixed.mean():9,.0f} {sampled.mean():9,.0f} "
                f"{fixed.mean() - keep.mean():10,.0f} {int((fixed < keep).sum()):10d} {keep_fill.mean():13.0%} / {fixed_fill.mean():.0%}",
                flush=True,
            )


if __name__ == "__main__":
    main()

"""Draw the pictures used on the project README from one finished training run.

uv run python scripts/readme_images.py runs/<folder>

Writes docs/images/profit.png (cash over time), docs/images/learning.png (test profit while training)
and docs/images/schedule.png (copy of the run's machine schedule). Run again after a better run.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "docs" / "images"
BLUE, ORANGE, GRAY = "#2563eb", "#f59e0b", "#9ca3af"


def style(ax, title: str):
    ax.set_title(title, loc="left", fontsize=14, fontweight="bold", pad=12)
    ax.grid(axis="y", alpha=0.25)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def draw_profit(run: Path):
    base = json.loads((run / "baselines.json").read_text())
    model = json.loads((run / "latest_curve.json").read_text())["fixed"]
    fig, ax = plt.subplots(figsize=(10, 4.5), dpi=160)
    for name, curve, color, label in (
        ("random", base["random"]["curve"], GRAY, "Random plans"),
        ("keep", base["keep"]["curve"], ORANGE, "Keep (no changes)"),
        ("model", model, BLUE, "Trained model"),
    ):
        ax.plot(curve["time"], curve["cash"], color=color, lw=2.5 if name == "model" else 2, label=label)
        ax.annotate(f"{curve['cash'][-1]:,.0f}", (curve["time"][-1], curve["cash"][-1]), xytext=(6, 0),
                    textcoords="offset points", color=color, va="center", fontweight="bold")
    ax.set_xlabel("Time in the episode (s)")
    ax.set_ylabel("Cash")
    ax.set_xlim(right=5000 * 1.07)
    ax.legend(frameon=False, loc="upper left")
    style(ax, "Money over one 5000 s episode, same orders")
    fig.tight_layout()
    fig.savefig(OUT / "profit.png")


def draw_learning(run: Path):
    df = pd.read_csv(run / "eval.csv")
    mean = df.groupby(["step", "mode"]).profit.mean().unstack()
    base = json.loads((run / "baselines.json").read_text())
    fig, ax = plt.subplots(figsize=(10, 4.5), dpi=160)
    ax.plot(mean.index, mean["fixed"], color=BLUE, lw=2.5, label="Model, most likely choices")
    ax.plot(mean.index, mean["sampled"], color=BLUE, lw=2, ls="--", alpha=0.7, label="Model, random draws")
    ax.axhline(base["keep"]["profit"], color=ORANGE, lw=2, label="Keep")
    ax.axhline(base["random"]["profit"], color=GRAY, lw=2, label="Random plans")
    ax.set_xlabel("Training decisions")
    ax.set_ylabel("Test profit")
    ax.xaxis.set_major_formatter(lambda x, _: f"{x / 1e3:,.0f}k")
    ax.legend(frameon=False, loc="center right")
    style(ax, "Test profit while training")
    fig.tight_layout()
    fig.savefig(OUT / "learning.png")


if __name__ == "__main__":
    run = Path(sys.argv[1])
    OUT.mkdir(parents=True, exist_ok=True)
    draw_profit(run)
    draw_learning(run)
    shutil.copy(run / "gantt.png", OUT / "schedule.png")
    print(f"Wrote pictures to {OUT}")

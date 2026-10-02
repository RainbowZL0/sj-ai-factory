<h1 align="center">sj-rl-factory-schedule</h1>

<p align="center">
  A factory simulator where a reinforcement learning model decides which machine makes what.<br>
  Work in progress: it already earns more than the "change nothing" rule.
</p>

<p align="center">
  <img alt="Python 3.12+" src="https://img.shields.io/badge/python-3.12%2B-3776ab?logo=python&logoColor=white">
  <img alt="Built with uv" src="https://img.shields.io/badge/built%20with-uv-de5fe9">
  <img alt="MaskablePPO" src="https://img.shields.io/badge/RL-MaskablePPO-2563eb">
  <img alt="Gymnasium" src="https://img.shields.io/badge/env-Gymnasium-0081a5">
</p>

<p align="center">
  <img src="docs/images/profit.png" alt="Cash over time: trained model 118k, keep 56k, random plans -68k" width="860">
</p>

Reinforcement learning (RL) means a program learns by trial and error, guided by a reward score. Here the reward is money earned. Every minute the model may move one machine of each kind to another recipe, and the simulator plays out the next minute.

This project is still in development. These are the results so far, and they will change.

| Policy | Test profit | Ordered units shipped |
|---|---|---|
| **Trained model** (1M decisions, about 13 minutes) | **about 120k** | **about 88%** |
| Keep (every machine stays on its starting recipe) | 58.9k | 39% |
| Random plans (before the move action) | -68.3k | about 2% |

Profit is the mean over three test episodes with fixed orders, on the larger factory of experiments 1 to 9 (`scenarios/casters.yaml`). The default is now the small lab factory (`scenarios/lab.yaml`).

## How it works

```mermaid
flowchart LR
    A["scenario YAML<br>materials, recipes,<br>machines, orders"] --> B["FactorySim<br>second-by-second rules"]
    B --> C["FactoryEnv<br>Gymnasium wrapper"]
    C -- "what the factory looks like" --> D["MaskablePPO model"]
    D -- "move one machine per kind,<br>every 60 s" --> C
    C -- "reward: cash earned" --> D
    B --> E["HTML pages and charts"]
```

The model starts out knowing nothing. After about 120k decisions it beats keep, and it levels off near 120k profit:

<p align="center">
  <img src="docs/images/learning.png" alt="Test profit while training: the model passes keep after about 120k decisions and settles near 120k profit" width="860">
</p>

The solid line is the model taking its most likely choices. The dashed line is it drawing choices at random, as it does in training. Both end in the same place, so the model really has a plan and is not relying on luck.

This is what the plan looks like on the factory floor: 14 constructors on top, 5 assemblers at the bottom, one colour per recipe.

<p align="center">
  <img src="docs/images/schedule.png" alt="Machine schedule of the trained model" width="860">
</p>

The pictures come from one training run; `uv run python scripts/readme_images.py runs/<folder>` redraws them.

All docs start at [docs/README.md](docs/README.md): [design](docs/design/README.md) (simulation rules, what the model decides and sees, training) and [experiments](docs/experiments/README.md) (results so far, lessons, next steps).

## Run

```bash
uv run python -m sjfactory run --policy keep         # every machine keeps its starting recipe
uv run python -m sjfactory run --policy random
uv run python -m sjfactory --note "what I changed" train --steps 1000000   # MaskablePPO; steps = decisions, one per 60 s
uv run python -m sjfactory eval runs/<folder>/best_model.zip --mode sampled   # or --mode fixed
uv run python -m sjfactory view                      # list of all runs in the browser
uv run python -m sjfactory check                     # machine load, keep, oracle and upper bound in under a minute, no training
uv run pytest
```

Global options go before the command, for example `--horizon 1000`, `--seed 3`, `--note "..."`, `--scenario path.yaml` or `--no-open`.

## Looking at results

Every command opens a web page in your browser. The pages are plain files, no server needed, and the charts are interactive: hover for values, drag to zoom, double-click to reset.

- `runs/index.html`: every run, newest first, with the notes you gave. The top chart lays all training runs over each other, so you can see whether a code change helped.
- `runs/<folder>/training.html`: opens as soon as training starts and reloads itself every 15 seconds. The main chart shows the model's profit on fixed test orders against the two fixed rules (keep and random): solid blue takes the model's most likely choices, dashed blue draws them at random as in training. Blue above orange means the model beats the fixed rule. Below it are "learning health" charts, each with a one-line note on what healthy looks like.
- `runs/<folder>/report.html`: one episode in detail: cash over time compared with the fixed rules on the same orders, where the money came from, every order (filled, partly filled, missed), the machine schedule and stock.

`uv run python -m sjfactory view runs/<folder>` rebuilds a run's page, for example after you change the page code.

Each run folder also holds `summary.json`, `history.xlsx`, `dashboard.png`, `gantt.png` and `material_flow.png`. Training runs also save `model.zip` (the last model), `best_model.zip` (best test profit, in either mode), `eval.csv` (every test episode) and `logs/` (`progress.csv` and TensorBoard files).

## Layout

- `scenarios/lab.yaml`: the default factory, small and balanced for quick experiments. A variant file names it as `base:` and lists only what changes (see `lab-busy.yaml`)
- `scenarios/default.yaml`, `casters.yaml`, `varied.yaml`: the larger factory used in experiments 1 to 9
- `sjfactory/`: the code (`spec` → `sim` → `env` → `policies`, plus `evaluate`, `training`, `recorder`, `plots` and `web` for running and watching)
- `tests/`: tests

Generated files (`runs/`, `*.png`, `*.xlsx`, `*.zip`) are ignored by git. Don't commit them. The pictures in `docs/images/` are the one exception.

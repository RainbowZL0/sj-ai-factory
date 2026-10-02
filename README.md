# sj-ai-factory

A factory production simulator, plus reinforcement learning (RL) that learns how many machines should run each recipe. RL means a program learns by trial and error, guided by a reward score. Here the reward is money earned.

All docs start at [docs/README.md](docs/README.md): [design](docs/design/README.md) (simulation rules, what the model decides and sees, training) and [experiments](docs/experiments/README.md) (results so far, lessons, next steps).

## Run

```bash
uv run python -m sjfactory run --policy keep         # every machine keeps its starting recipe
uv run python -m sjfactory run --policy random
uv run python -m sjfactory --note "what I changed" train --steps 1000000   # MaskablePPO; steps = decisions, one per 60 s
uv run python -m sjfactory eval runs/<folder>/best_model.zip --mode sampled   # or --mode fixed
uv run python -m sjfactory view                      # list of all runs in the browser
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

- `scenarios/default.yaml`: the whole factory in one file (materials, recipes, machines, money, orders)
- `sjfactory/`: the code (`spec` → `sim` → `env` → `policies`, plus `evaluate`, `training`, `recorder`, `plots` and `web` for running and watching)
- `tests/`: tests

Generated files (`runs/`, `*.png`, `*.xlsx`, `*.zip`) are ignored by git. Don't commit them.

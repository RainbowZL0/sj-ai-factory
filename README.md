# sj-ai-factory

A factory production simulator, plus reinforcement learning (RL) that learns which recipe each machine should run. RL means a program learns by trial and error, guided by a reward score. Here the reward is money earned.

See [docs/architecture.md](docs/architecture.md) for the design.

## Run

```bash
uv run python -m sjfactory run --policy keep         # every machine keeps its starting recipe
uv run python -m sjfactory run --policy random
uv run python -m sjfactory train --steps 200000      # MaskablePPO
uv run python -m sjfactory eval runs/<folder>/model.zip
uv run pytest
```

Global options go before the command, for example `--horizon 1000`, `--seed 3` or `--scenario path.yaml`.

Each run writes a folder under `runs/`. It holds `summary.json`, `history.xlsx`, `dashboard.png`, `gantt.png` and `material_flow.png`. Training runs also save `model.zip` and TensorBoard logs.

## Layout

- `scenarios/default.yaml`: the whole factory in one file (materials, recipes, machines, money, orders)
- `sjfactory/`: the code (`spec` → `sim` → `env` → `policies`, plus `recorder` and `plots`)
- `tests/`: tests

Generated files (`runs/`, `*.png`, `*.xlsx`, `*.zip`) are ignored by git. Don't commit them.

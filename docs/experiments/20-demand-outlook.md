# 20. Showing the model how much demand is still to come

2026-10-03. Roadmap milestone 6, step 2. Run: `runs/1003_043348-train` (4M steps, same mix and settings as `runs/1003_024435-train` in [experiment 19](19-one-model-for-all-days.md), plus `--demand-outlook`). All numbers from `bench`: 30 days per kind of day (seeds 2000 to 2029), share of the upper bound.

## What changed and why

On long-notice days the model is about 3 points below a planner that knows every order in advance (experiment 17), so what is left lies in guessing orders not yet announced. The model sees the orders announced so far and the time, but on a mix of kinds of day it has to work out by itself how much more usually comes.

- **`train --demand-outlook`** adds one number to the observation: how many units a usual day has not announced yet at this second, on average over days. It is worked out from the scenario's order settings only (number and size of orders, notice, when they fall due), which a factory would know from experience. It never looks at the orders of the day being played. A test checks it against 300 simulated days.
- Saved in the run's `config.json`, so `check`, `bench` and `eval` set it up again.

## Results

| Policy | Light to busy | Busy | Short notice | Breakdowns |
|---|---|---|---|---|
| One model, no outlook, final (experiment 19) | 86% | 83% | 82% | 69% |
| One model, no outlook, best on its test days | 86% | 84% | 82% | 76% |
| **One model with outlook, final** | **88%** | 85% | **83%** | 73% |
| One model with outlook, best on its test days | 87% | 82% | 83% | **77%** |
| Models trained on one kind of day (best of each) | 88% | 86% | 83% | 74% |
| Re-planned every 5 minutes, known orders (fair planner) | 86% | 82% | 61% | 71% |

## What it taught

- **A small gain, maybe noise.** With the outlook the final model gains 1 to 4 points on every kind of day; the "best" versions move by -2 to +1. Averaged over the four kinds of day, final 82.3% against 80.0%, best 82.3% against 82.0%. One training run each, so this is not settled.
- **The final model with the outlook is level with the specialists** (within 1 point on every kind of day) while being a single model, so it is the one to use for now: `runs/1003_043348-train/model.zip`.
- Most of what a usual day still brings can already be read from the time and the orders seen so far; one average number adds little. The points left to the planner that knows the future probably depend on what this particular day brings, which no average can tell.

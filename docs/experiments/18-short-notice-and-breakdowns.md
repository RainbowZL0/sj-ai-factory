# 18. Reacting to the unexpected: short notice and breakdowns

2026-10-03. Roadmap milestone 5. Runs: `runs/1003_013405-train` (`lab-short.yaml`, 2M steps) and `runs/1003_015135-train` (`lab-breakdowns.yaml`, 2M steps). Other models from experiments 16 and 17. All numbers from `bench` or `check`: 30 days (seeds 2000 to 2029), share of the upper bound.

## What changed and why

Experiment 17 showed that on today's lab days the model is close to the best a planner can do with the same knowledge, and that knowing orders early is worth 5 to 8 points. A real factory also gets surprises: orders at short notice, and machines that break. These are the days where reacting should matter more than planning ahead, so a trained model should pull ahead of planners there.

- **`lab-short.yaml`**: `lab-mixed.yaml` with orders announced only 120 to 600 s before they are due (was 600 to 1800 s).
- **Breakdowns**, a new scenario setting (`breakdowns: {per_hour, duration}`, default none, so old scenarios repeat exactly). Each machine fails at random times; a broken machine does nothing until repaired. The breakdown times come from their own random stream, so a seed's orders don't change. `lab-breakdowns.yaml` is `lab-mixed.yaml` with about 2 failures per machine per hour, 1 to 5 minutes each (about 10% of machine time). Models see each machine's repair time left, but only in scenarios with breakdowns, so models for other scenarios can't play these days.
- **The upper bound counts breakdowns.** It takes off the machine time each kind loses to that day's breakdowns. Without this the bound was 27% too high on breakdown days (121,567 against 95,927 on average) and every policy looked 15 points worse than it was.
- Both kinds of day were added to `bench`.

## Results

Short notice (`lab-short.yaml`):

| Policy | Share of the bound |
|---|---|
| Keep | -26% |
| Model trained on short notice | **83%** |
| Model trained on busy days | 82% |
| Model trained on busy days, order slack | 80% |
| Oracle, planned once (knows every order) | 85% |
| Re-planned every 5 minutes, all orders | 87% |
| Re-planned every 5 minutes, known orders | 61% |

The model trained on short notice does worse on the other days: 82% on light-to-busy (busy-day models 88%) and 77% on busy days (87%).

Breakdown days (`lab-breakdowns.yaml`), bound with breakdowns taken off:

| Policy | Profit | Share of the bound |
|---|---|---|
| Keep | -40,820 | -43% |
| Model trained on breakdown days | **71,313** | **74%** |
| Oracle, planned once (knows every order) | 67,233 | 70% |
| Re-planned every 5 minutes, all orders | 67,567 | 70% |
| Re-planned every 5 minutes, known orders | 68,513 | 71% |

On seeds 2000 to 2009 the look-ahead planner, which plays in a copy of the simulator, got 78% against the model's 79%.

## What it taught

- **With short notice, a planner that only knows announced orders collapses** (61%, against 82-86% with long notice), while the model loses only a few points (83%). Planning from the visible orders is not enough when orders keep arriving; the model has learned what usually comes. This is the biggest gap between the model and a fair planner so far: 22 points.
- **The busy-day model already handles short notice** (82% without seeing it in training). Training on short notice adds 1 point there and costs 5 to 10 points on the other days, so it is not worth a separate model.
- **Breakdowns hurt every policy, and planners most.** The model beats all three planners by 3 to 4 points. Knowing every order no longer helps (70% either way): a plan made in advance is broken by the next failure, and re-planning every 5 minutes reacts too late.
- **A yardstick must know what no schedule can avoid.** Before the bound counted breakdowns, the model looked at 59%; the gap was the bound, not the model.
- The bound now is loose on breakdown days in a different way: it knows when every machine will fail. A model can't, so 74% may be closer to the best possible than the number suggests.

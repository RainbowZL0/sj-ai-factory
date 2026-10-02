# 17. Re-planning yardsticks: how much is left, and what knowing the future is worth

2026-10-03. No training. Models: `runs/1003_003814-train` and `runs/1003_004241-train` (busy days, 2M steps, experiment 16), `runs/1003_005606-train` (`lab-three-downstream.yaml`, 2M steps, new) and `runs/1002_233856-train` (the same, 500k steps, experiment 14). All numbers from `bench`: 30 days per kind of day (seeds 2000 to 2029), share of the upper bound.

## What changed and why

After experiment 16 the model is level with the oracle on busy days. But the oracle is not the best possible: its plan reaches 99% of the bound on paper and loses 14 points when played. Two questions were open: is there a better schedule in the real simulator, and how much does knowing every order in advance help?

- **The oracle can plan from any moment** (`oracle(env, ...)` now starts from the current state: stock, machines, batches running, orders not yet due).
- **Safety margin** (`margin`): each order must be ready that many seconds before it is due.
- **Re-planned oracle** (`play_replanned`): the oracle solves again from the real state every 5 minutes, so slips in the simulator (an order a few units short, machines waiting for inputs) are corrected. Two versions: knowing **all orders** in advance, and knowing only **orders already announced**, the same knowledge the model has.
- `check --replan-minutes 5` and `bench` (on by default) print both.

## Results

Busy days (`lab-busy.yaml`), oracle planned once, by safety margin (30 days):

| Margin | 0 s | 60 s | 120 s | 240 s |
|---|---|---|---|---|
| Share of the bound | 85.4% | 87.4% | 86.1% | 84.8% |

Busy days, by how often the oracle re-plans and how long the solver may take (10 days, 2000-2009, while a training run used the other cores):

| Re-plan every | Solver limit | Margin | Share |
|---|---|---|---|
| never (planned once) | 30 s | 0 s | 87.0% |
| never | 10 s | 0 s | 81.8% |
| 5 minutes | 10 s | 0 s | 82.8% |
| 15 minutes | 10 s | 0 s | 78.3% |
| 15 minutes | 10 s | 60 s | 81.1% |
| 5 minutes | 10 s | 60 s | 86.0% |
| 15 minutes | 30 s | 60 s | 88.1% |
| 5 minutes | 30 s | 60 s | **91.4%** |

`bench`, 30 days per kind of day:

| Policy | Light to busy (`lab-mixed`) | Busy (`lab-busy`) | Third product (`lab-three-downstream`) |
|---|---|---|---|
| Keep | -22% | -31% | 1% |
| Model, busy days 2M steps | 88% | 86% | |
| Model, busy days 2M steps, order slack | 88% | **87%** | |
| Model, three products 2M steps | | | **86%** |
| Model, three products 500k steps | | | 85% |
| Oracle, planned once | 87% | 85% | 69% |
| Re-planned every 5 minutes, all orders | **91%** | **90%** | 63% |
| Re-planned every 5 minutes, known orders | 86% | 82% | 59% |

## What it taught

- **There is a better schedule than the model's, but only for someone who knows the future.** Re-planning with every order known reaches 90-91%, 3 points above the model. With only the orders announced so far, the same planner gets 82-86%, below the model on every kind of day.
- **Knowing the orders in advance is worth about 5 to 8 points on busy days.** Experiment 13 called notice "generous" because each order is known 10 to 30 times longer than it takes to make. But a planner that sees only today's orders leaves machines on the wrong product for orders it can't see yet. The model has learned what usually comes, so it beats a planner with the same knowledge by 2 to 5 points.
- **So the model is near the ceiling for what it can know.** The fair target, the best plan knowing only announced orders, lies between 82% and 90% on busy days, and the model is at 87%. Further gains there must come from guessing the future better, not from scheduling better.
- **The solver needs time.** Cut off at 10 s, the oracle's plan plays 5 points worse; re-planning often with a short limit is worse than planning once. Some busy days need more than 10 s.
- **A margin of one minute helps a little** (2 points): an order finished a minute early survives the small delays of the real line.
- **On three products, planners fail and the model doesn't.** All the planners treat flow within a minute as smooth and can't see which machine gets plates first, so they starve the line (59-69%). Training 2M steps instead of 500k changes the model by 1 point (85% to 86%).

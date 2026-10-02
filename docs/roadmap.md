# Roadmap

Where the project is going, why, and in what order. Started 2026-10-03, after experiment 14. Each milestone
says what "done" means; when one is done, mark it here and record the work as an experiment page.

## The target

The project builds a program that runs a factory for as much money as possible. So the measure that counts is
the money it leaves on the table on a day $d$:

$$\text{regret}(d) = \text{best possible profit}(d) - \text{model's profit}(d)$$

averaged over the kinds of days a real factory sees. "Best possible" has several levels, and each one is at
least as high as the one before:

$$\text{best plan knowing only today's orders} \le \text{best plan knowing every order} \le \text{whole-order bound} \le \text{upper bound}$$

The first can't be computed, so we measure against the tightest one we can compute and say which one it is.

We now have computable stand-ins for the first two levels (experiment 17): the oracle re-planned every 5
minutes from the real state, once knowing only the orders announced so far (a fair planner: the model's own
knowledge) and once knowing every order. The best plan knowing only today's orders lies between them.

**Goal:** on every kind of test day in `bench`, the model is at least as good as the fair planner and the
oracle, and as close as possible to the planner that knows every order.

## Where things stand (2026-10-03)

`bench`, share of the upper bound, 30 days per kind of day:

| Policy | Light to busy | Busy | Third product | Short notice | Breakdowns |
|---|---|---|---|---|---|
| Best model | 88% | 87% | 86% | 83% | 74% |
| Re-planned, every order known | 91% | 90% | 63% | 87% | 70% |
| Re-planned, announced orders only (fair) | 86% | 82% | 59% | 61% | 71% |
| Oracle, planned once | 87% | 85% | 69% | 85% | 70% |

The goal is met on every kind of day. The model beats the fair planner on all of them, by 22 points with short
notice, and beats even the planner that sees the future when machines break down. The best model differs by kind
of day; since experiment 19 one model covers all two-product days within 1 to 2 points of them. Next: guess
future orders better (milestone 6).

## Why busy days came first

- On normal days almost every order can be made, so the job is only to divide machine time, and the model
  already matched the oracle there.
- On busy days there are more orders than the factory can make, and an order is paid only if it ships in
  full, so a plan must give up whole orders on purpose. After experiment 14 this looked like the weak spot
  (79% against the oracle's 87%); experiments 15 to 17 showed most of that gap was the choice of test days
  and too little training.

## Milestones

### 1. An honest yardstick (done, [experiment 15](experiments/15-whole-order-bound-and-machine-time.md))

The upper bound in `check.py` let an order ship in part even when the scenario ships whole orders only, so it
might have been too high exactly where the model looks weakest. Now, with `partial_delivery: false`, each order
is a yes/no choice in the bound.

Result: the bound moves by 0.2% at most, because a fine for a short order is as big as its price, so filling
part of an order almost never pays even on paper. The busy-day gap is real: model 79%, oracle 88%, and the
oracle's own plan reaches 101% before it is played.

### 2. Where the busy-day money goes (done, [experiment 15](experiments/15-whole-order-bound-and-machine-time.md))

`check` now shows where each policy's machine time went: work in units that shipped, in products left
unsold, in other parts, changeovers, and waiting.

Result: the loss is **waste**, not choice of product or flow. The model keeps its machines as busy as the oracle,
but 10% of all machine time ends in finished products nobody buys (oracle 6%): units for orders that then
came up short. Declining orders on purpose does not help the oracle, so stock going to the wrong order is not
the cause either. The model needs to see which orders still fit.

### 3. Close the busy-day gap (done, [experiment 16](experiments/16-busy-days-longer-training.md))

1. Longer training on `lab-busy` (2M steps instead of 500k): closes the gap. On 30 busy days the model gets
   86-87%, the oracle 85%. On only 10 days the share moves by up to 6 points with the days drawn, which made
   the gap look bigger than it was.
2. Showing the model which orders still fit (`train --order-slack`): no measurable gain (+740 per day, margin
   ±2,100). Kept as an option.
3. and 4. (letting the model drop orders, a solver picking orders) were not needed.

Also learned: the "best" model, picked on 3 test seeds, is often worse on new days than the final model.

### 4. One score for all kinds of days (done, experiments [16](experiments/16-busy-days-longer-training.md) and [17](experiments/17-replanning-yardsticks.md))

`uv run python -m sjfactory bench [models ...]` runs `check` on 30 days each of light-to-busy (`lab-mixed`),
busy (`lab-busy`) and three-product (`lab-three-downstream`) days, with keep, the oracle and both re-planned
oracles, and prints each policy's share of the bound per kind of day. It takes about 15 minutes.

### 5. Reacting to the unexpected (done, [experiment 18](experiments/18-short-notice-and-breakdowns.md))

- Short notice (`lab-short.yaml`, orders known 120 to 600 s ahead): the fair planner drops to 61%, the
  busy-day model keeps 82%, a model trained on short notice 83%.
- Machine breakdowns (`breakdowns` setting, `lab-breakdowns.yaml`): a model trained on them gets 74%, every
  planner 70-71%. The upper bound now takes off the machine time lost to breakdowns.
- Showing 30 orders instead of 20 was not needed: with short notice fewer orders are visible, not more.

### 6. Guess the future better, with one model (next)

On long-notice days the model is 3 points below the planner that knows every order; what is left there is in
predicting orders not yet announced. And today each kind of day has its own best model. Steps:
1. One model for all two-product days (done, [experiment 19](experiments/19-one-model-for-all-days.md)):
   `train --mix` over light-to-busy, busy, short-notice and breakdown days, 4M steps. It is 1 to 2 points
   behind the models trained on one kind of day, 2 ahead on breakdown days, and matches or beats the fair
   planner everywhere. Training it twice as long (8M steps) gave the same scores.
2. Show the model how much of the day's usual demand is still to come (done, [experiment 20](experiments/20-demand-outlook.md)):
   `train --demand-outlook`. The final model gains 1 to 4 points and is level with the specialists, but the
   "best" versions barely move, so it may be noise.
3. Next ideas: repeat the comparisons with a second training seed to tell real gains from noise; look at the
   days where the planner that knows every order beats the model most, to see what the model failed to guess.

## Parked

Not on the path to the target; pick up only if a milestone needs them.

- Ties in input priority: machines that make a product first, then those that make parts (under keep,
  `lab-three-downstream.yaml` ships no Frames). Matters for keep, not for trained models.
- The large factory of experiments 1 to 9 (`scenarios/large/`): where batch flow loses 10 to 15%; longer
  training of the varied model; move cost. Its files and best models stay usable, and the tests still use it.
- Buying raw materials.

## Done

- Experiments 1 to 14 ([experiments](experiments/README.md)): a model that matches or beats the oracle on
  normal days in a 4-minute training run.
- Milestones 1 to 4 (experiments 15 to 17): an honest yardstick, the busy-day gap closed, `bench`, and fair
  re-planning yardsticks.
- Milestone 5 (experiment 18): short notice and machine breakdowns, both in `bench`.

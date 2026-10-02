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

**Goal:** on a fixed set of test days, from light to busy, the model is at least as good as the oracle (the
planner that knows every order in advance) on every kind of day, and leaves less than 10% of the tightest
bound on the table on average.

## Why busy days come first

- On normal days almost every order can be made, so the job is only to divide machine time. The model already
  matches the oracle there (89-91% of the upper bound). Little money is left to win.
- On busy days there are more orders than the factory can make, and since experiment 14 an order is paid only
  if it ships in full. A plan must give up whole orders on purpose, and choosing badly is expensive: work spent
  on an order that is dropped later is lost, and the order is fined its full price. This is where the model is
  furthest behind (79% against the oracle's 87%).
- Busy days hide two different problems. **Which orders to take** is a choice among about 30 to 50 orders that
  a solver can make exactly in well under a second, but a trained model must learn it from fines that arrive
  up to 30 minutes after the decision. **How to run the line minute by minute** is where the trained model is
  already strong; it beats the oracle when the line can starve (`lab-three`: 93% against 53%).

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

### 3. Close the busy-day gap

Try, cheapest first, and stop when the model reaches the oracle on `lab-busy`:
1. Longer training on `lab-busy` (gamma stays 0.97).
2. Show the model, for the known orders, how much machine time they need compared with the time left before
   each is due, so it can see which orders still fit.
3. Let the model drop an order on purpose, so nothing more is spent on it.
4. If the model still can't learn the choice: a small solver picks the orders each minute and the model runs
   the line for them. Kept as its own policy, so pure model and solver-plus-model can be compared.

### 4. One score for all kinds of days (first version done)

`uv run python -m sjfactory bench [models ...]` runs `check` on a fixed set of days (`BENCH` in `check.py`):
20 light-to-busy days (`lab-mixed`), 10 busy days (`lab-busy`) and 10 days of the three-product lab
(`lab-three-downstream`). It prints each policy's share of the bound per kind of day, so no kind of day gets
worse unnoticed. Short-notice days join it with milestone 5.

### 5. Reacting to the unexpected

Today orders are known 10 to 30 times the time it takes to make them, so knowing every order in advance is
worth almost nothing, and the oracle is a fair yardstick. Real factories get rush orders and breakdowns, and
that is where a trained model should beat any planner that plans once.
- Shorter notice: `lab-short.yaml` (`lab-mixed` with notice 120 to 600 s). Without training: keep -17%,
  oracle 84% of the bound, which it reaches only because it knows the orders before they are announced.
  Also try showing 30 orders instead of 20.
- Machine breakdowns (a new scenario setting whose default is none).
- A fair yardstick for this: the look-ahead planner or the oracle re-planned each minute from the orders known
  so far.

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

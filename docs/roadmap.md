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

### 1. An honest yardstick (next)

The upper bound in `check.py` lets an order ship in part even when the scenario ships whole orders only. On a
busy day it then fills spare machine time with pieces of orders that in reality earn nothing, so the bound is
too high exactly where the model looks weakest. We don't yet know how big the busy-day gap really is.

- Make the bound treat each order as yes or no when `partial_delivery: false` (an integer program with one
  yes/no choice per order; machine time stays divisible, so it stays fast and stays a true bound).
- Re-measure keep, the oracle and the best models on `lab`, `lab-busy`, `lab-mixed` and
  `lab-three-downstream`.

Done when `check` prints the whole-order bound and the numbers above are redone with it.

### 2. Where the busy-day money goes

Split each policy's loss on busy days into parts that point to different fixes:
- **choice:** the orders it filled are worth less than the oracle's set;
- **waste:** machine time spent on units that were never shipped (orders started and then missed);
- **flow:** time lost to waiting, switching and batches, on the orders it did ship.

Done when `check` prints this split and we know which part is largest.

### 3. Close the busy-day gap

Try, cheapest first, and stop when the model reaches the oracle on `lab-busy`:
1. Longer training on `lab-busy` (gamma stays 0.97).
2. Show the model, for the known orders, how much machine time they need compared with the time left before
   each is due, so it can see which orders still fit.
3. Let the model drop an order on purpose, so nothing more is spent on it.
4. If the model still can't learn the choice: a small solver picks the orders each minute and the model runs
   the line for them. Kept as its own policy, so pure model and solver-plus-model can be compared.

### 4. One score for all kinds of days

A single `check` run over a fixed set of days: light to busy (`lab-mixed`), shared materials
(`lab-three-downstream`), and later short notice. It prints the share of the tightest bound per kind of day
and on average, so one number says whether a change helped, and no kind of day gets worse unnoticed.

### 5. Reacting to the unexpected

Today orders are known 10 to 30 times the time it takes to make them, so knowing every order in advance is
worth almost nothing, and the oracle is a fair yardstick. Real factories get rush orders and breakdowns, and
that is where a trained model should beat any planner that plans once.
- Shorter notice (120 to 600 s), and show 30 orders instead of 20.
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

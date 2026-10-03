# 15. Whole-order bound, and where busy-day machine time goes

2026-10-03. Roadmap milestones 1 and 2. No training; models from experiment 14: `runs/1002_233508-train` (`lab-busy.yaml`) and `runs/1002_233133-train` (`lab.yaml`). All numbers are means over seeds 2000 to 2009.

## What changed and why

- **Whole-order bound.** Since experiment 14 the lab ships whole orders only, but the upper bound still let an order ship in part. On a busy day that could fill spare machine time with pieces of orders that really earn nothing, so the bound could be too high exactly where the model looked weakest. With `partial_delivery: false`, `check` now treats each order as a yes/no choice (an integer program; machine time stays divisible, so it is still a true bound and still takes under a second).
- **Where machine time goes.** `check` prints a second table: the share of all machine time that went into units that shipped, into finished products still unsold at the end, into other parts, into changeovers, and waiting. Only the first earns money.
- **Declining orders.** `FactorySim.decline` gives up an order on purpose: it ships nothing when due, even if the stock would cover it, so the stock stays for other orders. Nothing uses it by default. It tests one idea: the simulator ships any due order it can fill, so stock built for one order may be taken by another that the plan meant to give up.

## Results

The bound with and without whole orders:

| Scenario | Orders in part | Whole orders | Largest difference on one seed |
|---|---|---|---|
| `lab.yaml` | 123,240 | 123,240 | 0 |
| `lab-busy.yaml` | 129,040 | 128,840 | 800 |
| `lab-mixed.yaml` | 111,160 | 111,160 | 0 |
| `lab-three-downstream.yaml` | 136,104 | 136,080 | 240 |

Busy days (`lab-busy.yaml`), share of the whole-order bound:

| Policy | Profit | Share | Units shipped (Motor, Frame) |
|---|---|---|---|
| Keep | -31,840 | -25% | 34, 160 |
| Model trained on busy days | 101,480 | 79% | 136, 174 |
| Model trained on normal days | 100,080 | 78% | 136, 173 |
| Look-ahead | 96,560 | 75% | 124, 187 |
| Oracle, played | 112,760 | 88% | 142, 179 |
| Oracle, as planned | 130,160 | 101% | |

Where the machine time went on busy days:

| Policy | Shipped | Unsold products | Parts | Switching | Waiting |
|---|---|---|---|---|---|
| Keep | 54% | 28% | 12% | 0% | 6% |
| Model trained on busy days | 86% | 10% | 1% | 1% | 1% |
| Look-ahead | 86% | 5% | 6% | 0% | 3% |
| Oracle, played | 89% | 6% | 2% | 2% | 1% |

Per busy day, model against oracle: 7.4 against 6.5 orders missed, of which 3.9 against 3.7 had at least half their units in stock when due; 36 against 22 finished products unsold at the end, of which only about 4 were made after the last order was due.

Declining the orders the oracle's plan leaves out, then playing the plan: 110,240 on busy days (without declines 112,760) and 107,800 on normal days (109,000).

## What it taught

- **The bound was not the problem.** Without partial orders it moves by 0.2% at most. Filling orders in part almost never pays even in the linear program, because a fine for a short order is as big as its price. So the busy-day gap is real: the model gets 79% where the oracle gets 88%, and the best possible lies somewhere between 88% and 100%.
- **The model loses by making products that never ship.** It keeps its machines as busy as the oracle (98%), but 10% of all machine time ends in finished products nobody buys, against 6% for the oracle. That is about 14 more units per day; the oracle ships 11 more units than the model, and that is its whole lead of about 11,000. Nearly all of them were made before the last due time: units for orders that then came up short.
- **Declining orders does not help the oracle.** The oracle's plan loses 13 points when played (101% planned, 88% played) on normal and busy days alike, so that loss is flow within a minute, not stock going to the wrong order. The decline tool stays, for a model that may learn to use it.
- **So the model needs to see which orders still fit.** It sees each order's product, size and due time, but has to add up the work of all earlier orders itself to know whether one more fits. Next: show it that sum (milestone 3, step 2), next to plain longer training (step 1).

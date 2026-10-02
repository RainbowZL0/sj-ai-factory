# 7. Move action, and the casters back

Runs, 1M steps each, 2026-10-02 (run at the same time, so slower than usual):
- `1002_190200-train`: old plan action, casters scenario (the comparison point)
- `1002_190427-train`: move action, casters scenario
- `1002_190535-train`: move action, default scenario

Settings as in [experiment 5](05-keep-bias-sweep.md) (keep bias 0); the two move-action runs used 10 environments instead of 20.

## Changes

**Move action.** The plan action gave each recipe a number from 0 to 14, then scaled the numbers to the machines there are. Many different actions gave the same plan (1, 1, 1, 1, 1 and 2, 2, 2, 2, 2 both mean "spread evenly"): about 760,000 actions for 3,060 constructor plans. The new action is one choice per machine kind: no change, or move one planned machine from recipe A to recipe B. Every choice gives a different plan, "no change" is a single choice, and an episode starts from the starting plan. See [rl-interface.md](../design/rl-interface.md).

**Casters back.** [scenarios/casters.yaml](../../scenarios/casters.yaml): ore and coal in stock, ingots start at 0, so the 6 casters must make every ingot (see [simulation.md](../design/simulation.md#the-casters-scenario-scenarioscastersyaml)).

## Results

Mean test profit (seeds 1000 to 1002), model taking its most likely choice, then drawing at random:

| Steps | Plan action, casters | Move action, casters | Plan action, default ([exp. 5](05-keep-bias-sweep.md)) | Move action, default |
|---|---|---|---|---|
| 0 | -64,000 / -15,800 | -66,500 / -36,800 | | -53,500 / 14,700 |
| 100k | -18,700 / 72,450 | 58,100 / 68,950 | | 87,300 / 85,150 |
| 200k | 27,550 / 97,750 | 89,650 / 92,500 | 81,400 | 116,800 / 99,050 |
| 300k | 72,850 / 99,600 | 113,850 / 90,800 | | 116,600 / 109,700 |
| 500k | 94,700 / 106,400 | 115,200 / 109,800 | | 116,050 / 114,500 |
| 1M | 116,550 / 115,250 | 117,900 / 114,000 (at 900k) | 120,950 / 117,450 | 118,600 / 116,150 |
| Keep | 58,100 | 58,100 | 58,900 | 58,900 |

Recipe switches in the best model's report episode (seed 1000), each costing a 30 s changeover:

| | Plan action | Move action |
|---|---|---|
| Default scenario | 315 | 144 |
| Casters scenario | 427 | 203 |

Other orders ([experiment 6](06-other-orders.md), 30 new seeds per row), model profit / keep profit, and the seeds where the model lost:

| Orders | Plan action, default | Move action, default | Move action, casters |
|---|---|---|---|
| Training shape | 1.55, 0 lost | 1.59, 0 lost | 1.57, 0 lost |
| More orders (100) | 0.96, 21 lost | 1.06, 11 lost | 1.02, 16 lost |
| Bigger orders (5 to 20) | 0.89, 24 lost | 1.00, 16 lost | 0.92, 21 lost |
| Mostly Motor | 0.93, 21 lost | 1.10, 0 lost | 1.08, 2 lost |
| Mostly Frame | 11.5, 0 lost | 12.7, 0 lost | 13.1, 0 lost |

The random baseline now drifts by single moves, so it scores much closer to keep: 14,400 (default) and -15,200 (casters), against -68,300 for random plans.

## What it taught

- **The extra layer is not what blocked learning.** With the plan action, the casters scenario also reaches about 117k. The old failure came from the action design.
- **Unique actions learn much faster, not higher.** The move action reaches about 115k by 200k to 300k steps, where the plan action needed 500k or more; both end near 117k to 120k. The ceiling now seems set by something else, most likely that the model plays one plan for the usual order mix (experiment 6).
- **Half the changeovers,** but still about 2 switches per minute. A small cost per move, or deciding less often, could cut more.
- **A little better on other orders,** for example it now beats keep when most orders are Motors, but it still loses on many seeds when demand is more than the factory can make.
- A fresh model with the move action moves a machine almost every minute (step 0 is worse than keep). That costs little here, since it learns fast.

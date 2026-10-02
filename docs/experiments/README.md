# Experiments

What was tried in training, what happened, and what it taught us. Run folders live in `runs/` on the machine that made them (not in git); `runs/index.html` compares them.

Profits in experiments 1 to 9 are the mean over test seeds 1000, 1001 and 1002 per 5000 s episode, on the large factory. From experiment 10 on, results come from `check` on the lab factory: the mean over new seeds 2000 to 2009 per one-hour episode, often as a share of the upper bound.

The plan for what comes next is in the [roadmap](../roadmap.md).

## Where things stand (2026-10-03)

**The lab factory** (`scenarios/lab.yaml`, [experiment 10](10-lab-factory.md)) is where all work happens: 9 machines, round numbers, a training run levels off in a few minutes, and `check` compares keep, models, the look-ahead planner, the oracle and the upper bound in under a minute.

**Since experiment 14 the lab ships whole orders only**: a short order earns nothing and is fined its full quantity at the full price.

**Since experiment 17** (`bench`, 30 days per kind of day, share of the upper bound): the best models get 88% on light-to-busy days, 87% on busy days and 86% on three-product days. That beats the oracle (87%, 85%, 69%) and a planner that re-plans every 5 minutes from the orders announced so far (86%, 82%, 59%). Only a planner that also knows the orders still to come does better on two products (91%, 90%). The busy-day gap of experiment 14 came mostly from testing on too few days and training too briefly ([16](16-busy-days-longer-training.md)). Judge models on 30 days or more, and look at the final model as well as the "best" one.

What earlier lab experiments settled (numbers under the old rules, where part of an order was paid):
- Serving machines further down the line first only matters when a material feeds recipes at different depths ([11](11-lab-variants.md), [12](12-mixed-demand-and-three-products.md)). There, machine order starves the line and the oracle fails (53%), while the model works around it (93%).
- Spare time before the bottleneck lifts the oracle to 100% of the bound; storage costs hurt keep but not a model ([11](11-lab-variants.md)).
- Training on busy days gives a model that is best on every lab scenario ([11](11-lab-variants.md), [12](12-mixed-demand-and-three-products.md)).
- Stricter penalties don't change which product gets the machines, because on a busy machine the gain is only the difference in product value ([13](13-yardsticks-and-penalties.md)). Order notice is generous, 10 to 30 times the time to make a product.
- Gamma stays at 0.97: 0.98 and 0.99 did worse in 500k steps ([14](14-whole-orders-and-gamma.md)).

The scenario files used only by experiments 11 and 13 (`lab-storage`, `lab-bottleneck`, `lab-three-strict`, `lab-three-orderfine`) were removed on 2026-10-03; get them back from git history if needed (`git log --all -- scenarios/lab-storage.yaml`).

### The large factory (experiments 1 to 9, finished)

The files are now in `scenarios/large/`. Two trained models, both with the move action and a move cost of 50, on the casters factory:

| Orders (30 new seeds each) | Keep | Trained on the usual orders | Trained on varied orders |
|---|---|---|---|
| Usual shape | 82,560 | 126,590 | 116,680 |
| More orders (100) | 117,360 | 115,110 | 140,290 |
| Almost only Motor | 164,590 | 161,190 | 175,910 |
| Tough: 100 large orders, known 900 to 2400 s ahead | -51,520 | -65,330 | -33,150 |

- The action is one move per machine kind per minute ([experiment 7](07-move-action-and-casters.md)).
- A model trained on one order shape plays one plan; trained on varied orders it beats keep on every shape tested ([6](06-other-orders.md), [8](08-varied-orders.md)).
- On every order type the models match or beat the oracle ([9](09-bottleneck-analysis.md)). The open questions there are parked in the roadmap.

## Next steps

See the [roadmap](../roadmap.md). The first step is a whole-order upper bound, so the busy-day gap is measured against an honest ceiling.
## Experiments

| # | Page | Change | Result |
|---|---|---|---|
| 1 | [01-one-choice-per-machine.md](01-one-choice-per-machine.md) | One choice per machine every 10 s, no costs | Fails: 80k at best, then collapses to about 0 without randomness |
| 2 | [02-changeover-and-penalties.md](02-changeover-and-penalties.md) | 30 s changeover, penalties, hide impossible recipes, keep bias 5 | With randomness 72k; without, stuck at keep |
| 3 | [03-plan-action.md](03-plan-action.md) | Action becomes a plan every 60 s | With randomness 74k and rising; without, still keep |
| 4 | [04-speed-up.md](04-speed-up.md) | Parallel environments, 1 PyTorch thread, faster simulator | 132 to about 1,300 steps per second, same learning |
| 5 | [05-keep-bias-sweep.md](05-keep-bias-sweep.md) | Keep bias 0 to 3, 1M steps | About 120k both ways; bias 0 fastest, now the default |
| 6 | [06-other-orders.md](06-other-orders.md) | Best model on new seeds and differently shaped orders | Wins on all new seeds; loses to keep when demand exceeds capacity or most orders are Motors |
| 7 | [07-move-action-and-casters.md](07-move-action-and-casters.md) | Action becomes one move per kind; casters back | Same 118k, reached in less than half the steps, half the changeovers; casters learned fine |
| 8 | [08-varied-orders.md](08-varied-orders.md) | Notice times, varied orders per episode, move cost | Beats keep on every order shape; 10k less on the usual one; move cost cuts switches 4 times |
| 9 | [09-bottleneck-analysis.md](09-bottleneck-analysis.md) | Analysis: upper bound and oracle planner | Models match the oracle; limits are demand, then constructor time and batch flow |
| 10 | [10-lab-factory.md](10-lab-factory.md) | Small balanced lab factory, variant files, `check` command | 4-minute training reaches 96% of the upper bound, level with the oracle |
| 11 | [11-lab-variants.md](11-lab-variants.md) | Input priority, storage costs, one tight kind, more orders than capacity | Priority changes nothing; spare time upstream helps; training on busy orders gives the best model |
| 12 | [12-mixed-demand-and-three-products.md](12-mixed-demand-and-three-products.md) | Mixed demand; third product sharing plates across depths | Busy-day training is enough; machine order starves the line, the model works around it (93%), the oracle can't (53%) |
| 13 | [13-yardsticks-and-penalties.md](13-yardsticks-and-penalties.md) | Look-ahead planner; strict penalties and order fines; order notice | Stricter penalties don't change priorities; the missed Motors cost only 1 to 2.5%; notice is generous |
| 14 | [14-whole-orders-and-gamma.md](14-whole-orders-and-gamma.md) | Whole orders only, fine = full price; gamma 0.98 and 0.99 | Same behaviour; busy days are the weak spot (79% against the oracle's 87%); higher gamma worse at 500k |
| 15 | [15-whole-order-bound-and-machine-time.md](15-whole-order-bound-and-machine-time.md) | Whole-order bound; where machine time goes; declining orders | Bound moves 0.2% at most, so the gap is real; the model loses by making products that never ship (10% of machine time, oracle 6%) |
| 16 | [16-busy-days-longer-training.md](16-busy-days-longer-training.md) | 2M steps on busy days; order slack; 30 test days | Longer training closes the gap (87% against the oracle's 85% on 30 days); 10 days are too few; order slack adds nothing |
| 17 | [17-replanning-yardsticks.md](17-replanning-yardsticks.md) | Oracle re-planned every 5 minutes, with all orders or only announced ones | Model beats the fair planner by 2-5 points and is 3 below the one that sees the future; knowing orders ahead is worth 5-8 points |

A new experiment page says: what changed and why, the run folder, the settings, a results table, and what it taught.

## Lessons

- **Test the model both with and without randomness.** A model can do well when its choices are drawn at random and badly when it always takes its most likely choice. (1)
- **Decide a plan for the whole factory, not one choice per machine.** Independent choices per machine made the most likely choice useless. (1, 3)
- **Free actions get abused.** With no changeover time and no penalty for missed orders, the model switched recipes thousands of times per episode at no cost. (1, 2)
- **Don't leave impossible choices in.** Casters can never run, yet they kept choosing recipes. (2)
- **A strong starting preference for keep freezes learning.** Keep bias 5 held the model exactly at keep for 200k steps; 0 learns fastest. (2, 3, 5)
- **Training time is simulation time.** Parallel processes and 1 PyTorch thread gave about 9 times the speed. (4)
- **Give each different decision exactly one action.** When many actions meant the same plan, learning took twice as long. (7)
- **Test on orders of other shapes, not only other seeds.** A model can win on every new seed and still only know one plan. (6)
- **Train on the variety you want handled.** Varied orders per episode taught the model to read the orders. (8)
- **Check what is possible before blaming the model.** All the missed units were in orders no plan could fill in time. (8) An upper bound and an oracle show how much is left to gain. (9)

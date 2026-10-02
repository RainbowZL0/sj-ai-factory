# Experiments

What was tried in training, what happened, and what it taught us. Run folders live in `runs/` on the machine that made them (not in git); `runs/index.html` compares them.

All profits are the mean over test seeds 1000, 1001 and 1002 (the same orders every time), per 5000 s episode.

## Where things stand (2026-10-02)

**New default: the small lab factory** ([experiment 10](10-lab-factory.md)). It has 9 machines, round numbers and a load that can be checked by hand. A training run reaches its plateau in about 2 minutes. `python -m sjfactory check` shows keep, the oracle and the upper bound in under a minute. On new seeds the model reaches 96% of the upper bound (oracle 97%, keep 32%). Test ideas for the factory here first, as variant files (`base: lab.yaml`).

The rest of this section is about the larger factory of experiments 1 to 9 (`casters.yaml`, `varied.yaml`).


Two trained models, both with the move action and a move cost of 50, on the casters factory:

| Orders (30 new seeds each) | Keep | Trained on the usual orders | Trained on varied orders |
|---|---|---|---|
| Usual shape | 82,560 | 126,590 | 116,680 |
| More orders (100) | 117,360 | 115,110 | 140,290 |
| Almost only Motor | 164,590 | 161,190 | 175,910 |
| Tough: 100 large orders, known 900 to 2400 s ahead | -51,520 | -65,330 | -33,150 |

- The action is one move per machine kind per minute ([experiment 7](07-move-action-and-casters.md)): the same level as the old plan action in less than half the steps. The casters are back and learned just as well.
- A model trained on the usual orders plays one plan for that mix and loses to keep when the orders take another shape ([experiment 6](06-other-orders.md)). Trained on varied orders ([experiment 8](08-varied-orders.md)), it beats keep on every order shape tested, at a cost of about 10k on the usual shape.
- Early orders used to be impossible (the first Frame takes about 550 s). Orders can now have a notice time, and nothing is due before it.
- A move cost of 50 in the reward cut changeovers from 203 to 46 per episode on varied orders, without losing profit.

The model is no longer the main limit: on every order type it matches or beats an oracle planner that knows all orders in advance ([experiment 9](09-bottleneck-analysis.md)). With the usual orders, demand is the limit; with heavy orders, the constructors' iron bar and screw time. Use `python -m sjfactory --scenario <file> check <model>` to see how close a model gets to the upper bound.

## Next steps

1. Try factory ideas on the lab factory as variant files, comparing the share of the upper bound before and after with `check`: input priority for machines further down the line, storage costs, a slower or extra machine kind (a real bottleneck), more product types.
2. Train on `lab-busy.yaml` or a mix of demand levels: the model leaves 4 points to the oracle when there are more orders than capacity.
3. Larger factory: train the varied model longer (for example 3M steps; it was still improving at 1M). It is 10k behind the usual model on the usual orders.
4. Keep the move cost at 50 or lower: useful plans switch 60 to 110 times per episode.
5. Scenario ideas from [Not modelled yet](../design/simulation.md#not-modelled-yet).

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

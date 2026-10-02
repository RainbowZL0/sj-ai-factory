# Experiments

What was tried in training, what happened, and what it taught us. Run folders live in `runs/` on the machine that made them (not in git); `runs/index.html` compares them.

All profits are the mean over test seeds 1000, 1001 and 1002 (the same orders every time), per 5000 s episode.

## Where things stand (2026-10-02)

| Policy | Test profit | Ordered units shipped |
|---|---|---|
| Trained model, plan action, 1M steps | about 116k to 121k | about 88% |
| Keep (every machine stays on its starting recipe) | 58,900 | 39% |
| Random plans | -68,300 | about 2% |

The model does just as well taking its most likely choice as when drawing at random. What the best model does (run `1002_163351-train`, seed 1000):
- Assemblers: from the first minute, one machine on each of the 5 assembler recipes. Keep never makes reinforced plates or frames, so this is where most of the extra profit comes from: Frame orders get filled.
- Constructors: roughly 6 to 7 on iron bars, 3 to 5 on screws, 1 to 2 on plates, the rest on tubes and wire. But it changes this plan almost every minute, and each change costs a 30 s changeover.

## Next steps

1. Cut needless changeovers: decide less often (`--ticks 120` or `180`), or charge a small cost whenever the plan changes.
2. Test on seeds never used for picking the best model, to check the profit holds on other orders.
3. Scenario ideas from [Not modelled yet](../design/simulation.md#not-modelled-yet).

## Experiments

| # | Page | Change | Result |
|---|---|---|---|
| 1 | [01-one-choice-per-machine.md](01-one-choice-per-machine.md) | One choice per machine every 10 s, no costs | Fails: 80k at best, then collapses to about 0 without randomness |
| 2 | [02-changeover-and-penalties.md](02-changeover-and-penalties.md) | 30 s changeover, penalties, hide impossible recipes, keep bias 5 | With randomness 72k; without, stuck at keep |
| 3 | [03-plan-action.md](03-plan-action.md) | Action becomes a plan every 60 s | With randomness 74k and rising; without, still keep |
| 4 | [04-speed-up.md](04-speed-up.md) | Parallel environments, 1 PyTorch thread, faster simulator | 132 to about 1,300 steps per second, same learning |
| 5 | [05-keep-bias-sweep.md](05-keep-bias-sweep.md) | Keep bias 0 to 3, 1M steps | About 120k both ways; bias 0 fastest, now the default |

A new experiment page says: what changed and why, the run folder, the settings, a results table, and what it taught.

## Lessons

- **Test the model both with and without randomness.** A model can do well when its choices are drawn at random and badly when it always takes its most likely choice. (1)
- **Decide a plan for the whole factory, not one choice per machine.** Independent choices per machine made the most likely choice useless. (1, 3)
- **Free actions get abused.** With no changeover time and no penalty for missed orders, the model switched recipes thousands of times per episode at no cost. (1, 2)
- **Don't leave impossible choices in.** Casters can never run, yet they kept choosing recipes. (2)
- **A strong starting preference for keep freezes learning.** Keep bias 5 held the model exactly at keep for 200k steps; 0 learns fastest. (2, 3, 5)
- **Training time is simulation time.** Parallel processes and 1 PyTorch thread gave about 9 times the speed. (4)

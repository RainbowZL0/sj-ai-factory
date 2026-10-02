# RL interface (`env.py`)

## The plan

For each machine kind (category), how many machines should run each of its recipes. An episode starts with the plan the machines start in, so a model that never changes it plays exactly like the keep rule.

Recipes that can never run, because an input can never be obtained (`Scenario.obtainable`: starting stock plus anything made from it), are left out. In `large/default.yaml` there is no ore, so the casters are left out and never run; in `large/casters.yaml` they are planned like any other kind.

## Action: one move per kind

One choice per machine kind, every decision:
- 0: no change, or
- move one machine of the plan from recipe A to recipe B (every ordered pair of two different recipes of that kind).

So constructors (5 recipes) have 1 + 5 × 4 = 21 choices, assemblers 21, casters (3 recipes) 7.

- Every choice gives a different plan. The earlier action (a number from 0 to 14 per recipe, scaled to the machines there are) gave the same plan for many different numbers, for example 1, 1, 1, 1, 1 and 2, 2, 2, 2, 2, so the model had to learn that those mean the same thing.
- "No change" is a single choice, so keeping a good plan is easy to learn, and plans change by one machine at a time, so needless changeovers are less likely.
- `action_masks()` blocks moves away from a recipe that has no planned machine.
- `start_action()` is "no change" for every kind. Training can give a fresh model a preference for it (`--keep-bias`).
- Machines that start stopped are not in the plan and stay stopped. No scenario has any.

Why a plan and not one choice per machine: with one choice per machine, the model's most likely choice was either a bad plan (all constructors on the same recipe) or no change at all, and the useful behaviour lived only in random draws. See [experiment 1](../experiments/01-one-choice-per-machine.md) and [experiment 3](../experiments/03-plan-action.md). Why moves and not a full plan per decision: see [experiment 7](../experiments/07-move-action-and-casters.md).

## Carrying out the plan

Every second, an idle machine whose recipe has more machines than planned (or that is stopped) switches to the recipe furthest below its planned number. Busy machines switch after their batch. That reaches the plan with as few switches, and so as few changeovers, as possible. Recipes only change here, so once a plan is reached nothing is checked until the next plan.

## Observation

One flat vector, all squeezed to small values:
- time progress
- stock, twice: on a log scale, and in "batches" (stock divided by the most any recipe uses per batch, capped at 10). The log scale alone hides the difference between 3 and 5 screws, which decides whether a machine can start.
- per kind and recipe: machines on it now, and machines planned
- per machine: its recipe (one‑hot, meaning a row of zeros with a single 1), the fraction of its batch left, the fraction of its changeover left, and whether it is waiting for inputs
- units still ordered per product, over all known orders
- the 20 known orders due soonest: product, quantity and time until due. Orders not yet known (see `notice` in [simulation.md](simulation.md)) are hidden.
- only in scenarios with breakdowns, or with `show_breakdowns` (set by `train --mix` when any scenario in the mix has breakdowns, and saved in the run's `config.json`): per machine, the repair time left (divided by the longest possible; always 0 on days without breakdowns). So one model can play days with and without breakdowns.
- optional (`train --order-slack`, saved in the run's `config.json`, so `check` and `eval` set it up again for that model): for each of those orders, the time to spare at its due time if the factory makes it and the earlier orders that fit, from the finished products in stock, with every machine kind at full speed. Negative means the order doesn't fit; it is then left out for the later orders, since the factory will miss it anyway. It is a rough guide (it ignores parts in stock, waiting and changeovers) that saves the model from adding up orders itself (roadmap milestone 3).

Prices and other constants are left out because they never change within a scenario; cash is left out because it does not change what the best decision is.

Changing the observation or the action means models saved before the change can't be loaded any more.

## Reward and time

- **Reward.** The cash change during the action, minus `move_cost` for each machine moved in the plan, times `reward_scale` (0.01). The move cost (`--move-cost`, 50 in training) discourages needless changeovers; it only lowers the reward, never cash or profit.
- **Time.** `ticks_per_action` seconds pass per decision; the command line uses 60. A changeover alone takes 30 seconds, so plans don't need to change faster.
- **Repeatable runs.** `reset(seed=...)` seeds the random orders, so the same seed gives the same episode.

## Fixed rules (`policies.py`)

- `KeepPolicy`: never plans, so no machine ever switches.
- `RandomPolicy`: with probability 0.1 per decision, a random allowed choice for each kind (a move, or sometimes no change); otherwise no change. Since the move action it drifts slowly away from keep instead of jumping to random plans, so its score is much closer to keep than before.
- `ModelPolicy`: a trained model, either taking its most likely plan ("fixed") or drawing one from its probabilities ("sampled").

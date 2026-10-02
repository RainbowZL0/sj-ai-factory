# RL interface (`env.py`)

## Action: a plan

One number per pair of machine kind (category) and recipe: how many machines of that kind should run that recipe, from 0 to the number of machines of that kind.

- The numbers of one kind are scaled to the machines there are, with leftovers going to the largest fractions (`allocate`), so every action is valid.
- If all numbers of a kind are 0, that kind keeps its previous plan. A new episode starts with no plan, which means no machine switches: the keep rule.
- Recipes that can never run, because an input can never be obtained (`Scenario.obtainable`: starting stock plus anything made from it), get no number. The casters (ore only) get none and are left alone.
- `action_masks()` allows everything; it exists so MaskablePPO and the shared policy interface work.
- `start_action()` is the plan that matches the starting recipes. Training can give a fresh model a preference for it (`--keep-bias`).

Why a plan and not one choice per machine: with one choice per machine, the model's most likely choice was either a bad plan (all constructors on the same recipe) or no change at all, and the useful behaviour lived only in random draws. See [experiment 1](../experiments/01-one-choice-per-machine.md) and [experiment 3](../experiments/03-plan-action.md).

## Carrying out the plan

Every second, an idle machine whose recipe has more machines than planned (or that is stopped) switches to the recipe furthest below its planned number. Busy machines switch after their batch. That reaches the plan with as few switches, and so as few changeovers, as possible. Recipes only change here, so once a plan is reached nothing is checked until the next plan.

## Observation

One flat vector, all squeezed to small values:
- time progress
- stock, twice: on a log scale, and in "batches" (stock divided by the most any recipe uses per batch, capped at 10). The log scale alone hides the difference between 3 and 5 screws, which decides whether a machine can start.
- per kind and recipe: machines on it now, and machines planned
- per machine: its recipe (one‑hot, meaning a row of zeros with a single 1), the fraction of its batch left, the fraction of its changeover left, and whether it is waiting for inputs
- the 20 nearest orders: product, quantity and time until due

Prices and other constants are left out because they never change within a scenario; cash is left out because it does not change what the best decision is.

Changing the observation or the action means models saved before the change can't be loaded any more.

## Reward and time

- **Reward.** The cash change during the action, times `reward_scale` (0.01).
- **Time.** `ticks_per_action` seconds pass per decision; the command line uses 60. A changeover alone takes 30 seconds, so plans don't need to change faster.
- **Repeatable runs.** `reset(seed=...)` seeds the random orders, so the same seed gives the same episode.

## Fixed rules (`policies.py`)

- `KeepPolicy`: never plans, so no machine ever switches.
- `RandomPolicy`: with probability 0.1 per decision, a random plan; otherwise keeps the previous one.
- `ModelPolicy`: a trained model, either taking its most likely plan ("fixed") or drawing one from its probabilities ("sampled").

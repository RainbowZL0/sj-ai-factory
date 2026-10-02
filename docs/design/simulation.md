# Simulation

## Rules of one simulated second

`FactorySim.step(changes)` does these steps in this order:

1. **Switch recipes.** Only idle machines (no batch running, no changeover going on) can switch. Asking a busy machine to switch is an error, because it would mean the caller has a bug. Switching to a different recipe starts a changeover of `changeover_time` seconds, during which the machine makes nothing and uses no power. Stopping needs no changeover; starting again after a stop does.
2. **Start batches.** Every idle machine that has a recipe starts if the stock covers the inputs. Inputs are taken now. Machines are served in list order, or with `input_priority: downstream` the machines whose recipe is furthest from the raw materials first (`Scenario.recipe_depth`), then in list order.
3. **Use power.** Running machines use `power_kw × 1 s` of energy.
4. **Advance one second.** Changeovers count down. Batches that reach zero put their outputs into stock.
5. **Settle due orders.** Orders whose due time has arrived ship whatever stock exists. Missing units cost `shortfall_penalty` each, plus `order_fine` once per order not filled in full. With `partial_delivery: false` an order ships only if the full quantity is in stock; otherwise nothing ships, nothing is paid, every unit of the order is fined, and the stock stays for later orders. An order given up on purpose (`FactorySim.decline`) is settled the same way even if the stock would cover it; nothing declines orders unless a caller asks.
6. **Settle cash.** Cash changes by revenue − penalty − energy − storage − rent.

All machines share one warehouse, so the scenario needs no links between machines. The real connections are the material flow chart (`material_flow.png`), drawn from the recipes.

A change meant only to make this faster must give identical results: compare it second by second with the old code on several seeds, with random plans, and check that keep still makes 52,050 on seed 0 of `scenarios/large/default.yaml`.

## Variant files

A scenario file that starts with `base: other.yaml` begins from that file (the path is relative to the variant) and changes only what it lists. Mappings are merged key by key, so `recipes: {Make_Plate: {cycle_time: 5}}` changes one number and keeps the rest of the recipe. Anything else, such as the `machines` list, is replaced whole. An experiment on the factory is then a file of a few lines, and the difference between two scenarios is plain to see.

## The lab scenario (`scenarios/lab.yaml`, the default)

A small factory built for quick experiments: round numbers, every load easy to check by hand.

| Kind (machines) | Recipes | Time |
|---|---|---|
| Smelter (3) | IronOre → Iron, CopperOre → Copper | 10 s per unit |
| Constructor (3) | Iron → Plate, Copper → Wire | 10 s per unit |
| Assembler (3) | 1 Plate + 2 Wire → Motor (sells 600, penalty 600 per unit); 2 Plate + 1 Wire → Frame (400, penalty 400) | 30 s per unit |

- Every product needs exactly 30 s from each kind, so the factory makes at most 360 products per hour, whatever the mix, if no machine ever waits or switches.
- One hour per episode. 20 to 40 orders of 1 to 19 units (about 300 units, so about 86% of the factory's time), with the Motor/Frame mix drawn per episode and each order known 600 to 1800 s before it is due.
- The machines start leaning to Frames (2 iron smelters, 2 plate constructors, 2 Frame assemblers), so keep is short of wire whenever Motors are ordered.
- Each kind has 2 recipes, so the action is 3 choices per kind.
- Orders are all or nothing (`partial_delivery: false`), as with a real customer: a short order earns nothing and is fined its full quantity times the product's price, so bigger orders are fined more. Experiments 10 to 13 ran before this (partial orders paid per unit, penalty half the price); their numbers come from the lab of that time.
- Machines further down the line get inputs first (`input_priority: downstream`).

On seeds 2000 to 2009, keep makes -2.9k and the oracle 109k (88% of the upper bound, 123k).

Variants (each a few lines on top of `lab.yaml`), each with a role in the [roadmap](../roadmap.md):
- `lab-busy.yaml`: 30 to 50 orders, about 410 units against a capacity of 360, so the plan also has to choose which orders to leave short.
- `lab-mixed.yaml`: 15 to 50 orders, from light days to more than the factory can make.
- `lab-three.yaml`: a third product, Pump (1 Gear + 1 Plate + 1 Wire; a constructor makes a Gear from 2 Plates), on 4 smelters, 4 constructors and 3 assemblers. Plates go both to assemblers and to gear making, and in machine order the gear maker takes every plate, so keep ships nothing. `lab-three-downstream.yaml` is the same with `input_priority: downstream`.

Variants used only by experiments 11 and 13 (storage costs, a single tight kind, stricter penalties, order fines) were removed on 2026-10-03 and are in git history. The settings they used (`storage_cost`, `order_fine`) still work.
## Checking a scenario without training

`uv run python -m sjfactory --scenario <file> check [models ...]` prints, in under a minute:
- the machine seconds each product needs from each kind, and the most of each product per episode;
- the orders, and the share of each kind's time they need;
- the profit of keep, any models given, the look-ahead planner (`lookahead.py`: tries each move in a copy of the simulator, 30 minutes ahead, so it sees batches and input order; slower and weaker than a trained model), the oracle and the upper bound (see [experiment 9](../experiments/09-bottleneck-analysis.md)), on seeds 2000 to 2009, each as a share of the upper bound. When the scenario ships whole orders only, the bound treats each order as a yes/no choice (experiment 15: on the lab scenarios this changes it by 0.2% at most). The bound and the oracle count energy and storage costs; storage is charged on the stock at the end of each period, so with storage costs the bound is close but not strict.
- where each policy's machine time went: work in units that shipped, in finished products left unsold at the end, in other parts, changeovers, and waiting. Only the first earns money, so this shows where a policy loses against the oracle.

Use it to see whether a change to the factory changes anything before spending a training run on it.

`uv run python -m sjfactory bench [models ...]` runs `check` on a fixed set of test days (`BENCH` in `check.py`: 20 light-to-busy days from `lab-mixed.yaml`, 10 busy days, 10 days of the three-product lab) and prints one line per policy: its share of the upper bound on each kind of day. A model only plays the scenarios it fits (a model for two products can't play three). It takes a few minutes; this is the score the [roadmap](../roadmap.md) aims at.

## The large factory (`scenarios/large/`)

The factory of experiments 1 to 9, now parked. `casters-downstream.yaml` is the casters factory with `input_priority: downstream`.

### `default.yaml`

- 5000 s per episode, 50 random orders for Motors and Frames, seeded at `reset()`.
- 25 machines: 6 casters, 14 constructors, 5 assemblers.
- Changeover 30 s. Motor sells for 800 (penalty 400 per missing unit), Frame for 300 (penalty 150). Rent 0.5 per second; energy is free.
- Ore stock is 0, so the casters never run. Ingots start at 99,999, so they never run out.
- Keep (every machine stays on its starting recipe) never runs PlateAssemble or FrameFinal, so it fills no Frame orders.

The large factory from the earlier experiments (1 to 9). Despite the file name, it is no longer the default; tests still use it.

### `casters.yaml`

The same factory with the smelting layer switched on: ore and coal start at 99,999 and ingots at 0, so the casters must make every ingot. With the starting recipes, casters and constructors are roughly in balance (3 iron casters make 1.5 iron ingots per second, which is what 6 bar constructors use), so moving constructors onto plates needs iron casters taken from steel. Keep makes 58,100 on the test seeds, about the same as in the default scenario.

### `varied.yaml` (varied orders)

The casters factory, with orders whose shape changes every episode, so a model has to read the orders instead of learning one plan:
- `count: [20, 100]` orders, `quantity: [1, 15]` units each.
- `mix: random`: each episode draws its own Motor/Frame mix; a quarter of episodes order one product only.
- `notice: [900, 2400]`: each order becomes known 900 to 2400 s before it is due, and nothing is due before 900 s. In the other scenarios orders are due from second 0, but the first Frame takes about 550 s to make, so early orders could never be filled ([experiment 7](../experiments/07-move-action-and-casters.md)).

These settings are optional in any scenario; without them orders are drawn exactly as before. Keep's profit swings widely from episode to episode here (-61k to 134k on the 3 test seeds), so training on it uses 10 test seeds.

## Not modelled yet

- Buying raw materials.
- Machine breakdowns.

Each would be a field in `spec.py` plus a few lines in `FactorySim.step`.

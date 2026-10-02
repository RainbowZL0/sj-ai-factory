# Architecture

## Starting from first principles

Strip the project down and it is one question: **given a factory and a list of orders, which recipe should each machine run, and when, to end with the most money?**

Answering that needs exactly five things, and each one gets its own module:

| What it is | Changes over time? | Module |
|---|---|---|
| The factory and its rules: materials, recipes, machines, prices, orders | No | `spec.py` |
| Where things stand right now: clock, stock, each machine's recipe and time left, cash, open orders | Yes | `sim.State` |
| The rule that moves the state forward one second, given decisions | No (pure rule) | `sim.FactorySim.step` |
| Whoever makes the decisions: a fixed rule, random, or a trained model | n/a | `policies.py` |
| Whoever watches: history, charts, Excel | n/a | `recorder.py`, `plots.py` |

The RL interface (`env.py`) is a thin translation layer. It turns the state into numbers for a neural network, turns the network's numbers back into decisions, and reports the cash change as the reward.

```
scenarios/*.yaml ──load──▶ Scenario (frozen)
                              │
                              ▼
   Policy ──action──▶ FactoryEnv ──changes──▶ FactorySim.step() ──▶ State
     ▲                   │                         │
     └──obs, mask────────┘                         └──StepReport──▶ Recorder ──▶ Excel, charts
```

Dependencies point one way only: `spec` ← `sim` ← `env` ← `policies`. `recorder` and `plots` only read.

## Rules of one simulated second

`FactorySim.step(changes)` does these steps in this order:

1. **Switch recipes.** Only idle machines can switch. Asking a busy machine to switch is an error, because it would mean the caller has a bug.
2. **Start batches.** Every idle machine that has a recipe starts if the stock covers the inputs. Inputs are taken now. Machines are served in list order.
3. **Use power.** Running machines use `power_kw × 1 s` of energy.
4. **Advance one second.** Batches that reach zero put their outputs into stock.
5. **Settle due orders.** Orders whose due time has arrived ship whatever stock exists. Missing units cost `shortfall_penalty` each.
6. **Settle cash.** Cash changes by revenue − penalty − energy − storage − rent.

All machines share one warehouse. That is why the scenario has no upstream/downstream links. The real connections between machines are the material flow chart (`material_flow.png`), drawn from the recipes.

Before the old `pycode` simulator was deleted, these rules were checked to reproduce it exactly. With the same orders, the old greedy run and the new keep-policy run match second by second over 5000 seconds in stock, cash, machine activity and energy.

## RL interface

- **Action.** One integer per machine: `0` keep, `1` stop, `2+k` switch to that machine's k‑th recipe. Busy machines can only keep. `action_masks()` tells MaskablePPO which choices are allowed. Any disallowed choice that does arrive is treated as keep, so algorithms that ignore masks still work.
- **Observation.** One flat vector, all squeezed to small values:
  - time progress
  - cash
  - stock (log scale)
  - per machine: its recipe (one‑hot, meaning a row of zeros with a single 1) and the fraction of its batch left
  - the 20 nearest orders: product, quantity and time until due

  Prices and other constants are left out because they never change within a scenario.
- **Reward.** The cash change during the action, times `reward_scale` (0.01 by default).
- **Time scale.** `ticks_per_action` lets the simulation run several seconds per decision. Training defaults to 10 seconds per decision and `gamma=0.995`. That makes the agent weigh about the next 200 decisions, or roughly 2000 seconds. That is the scale on which orders pay out. The old setup (1 s per decision, `gamma=0.95`) looked only about 20 seconds ahead.
- **Repeatable runs.** `reset(seed=...)` seeds the random orders, so the same seed gives the same episode.

## What changed from the old `pycode/` version, and why

The old version has been deleted.

| Old | New | Why |
|---|---|---|
| 7 YAML files, each material listed in 3 of them | One scenario file, each material listed once | Nothing to keep in sync |
| Machine list with unused upstream/downstream links | Machine groups: category + starting recipe + count | The simulation never used the links. IDs stay the same (`CASTER-01`…) |
| Order due times count down in place; recipes divided in place | Scenario is frozen; orders keep an absolute due time | Fixed data can't be corrupted by a run |
| Selling done inside the price manager | Selling is a step of the simulation | One place for each rule |
| Scheduler holds its own copy of the bindings, with a mode string | No scheduler object; decisions are an argument to `step()` | The state has one owner |
| "Keep" (index 0) meant *don't start this second* | "Keep" means *carry on*; an explicit "stop" exists | The default action does the sensible thing |
| Busy machine could switch recipe (check commented out) | Not allowed; the simulator raises an error | Was a real bug |
| `price_sell=sold_quantity` in sale records | Fixed | Bug |
| Unseeded random orders, created in a constructor | Seeded at `reset()` | Repeatable experiments |
| `reset()` drew charts and wrote Excel | The env has no side effects; `Recorder` is opt‑in | Training runs thousands of resets |
| `../` paths that depend on the start folder; config loaded at import | Paths from the project root; scenarios loaded on request | Runs from anywhere; several scenarios at once |
| Raw values (99999, cash) in the observation | Log‑scaled, bounded | Neural networks train poorly on huge raw numbers |
| Topology chart | Material flow chart | Shows the factory as it really works |

## Not modelled yet

The old code didn't model these either:
- Buying raw materials. Ore stock is 0, so the casters never run in the default scenario.
- Orders appearing during the episode. All orders are known at the start.
- Machine breakdowns.
- Recipe changeover time.

Each would be a field in `spec.py` plus a few lines in `FactorySim.step`.

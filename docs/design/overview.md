# Overview

## The question

Strip the project down and it is one question: **given a factory and a list of orders, how many machines should run each recipe, and when, to end with the most money?**

## The modules

Answering that needs five things, and each one gets its own module:

| What it is | Changes over time? | Module |
|---|---|---|
| The factory and its rules: materials, recipes, machines, prices, orders | No | `spec.py` |
| Where things stand right now: clock, stock, each machine's recipe, batch time left and changeover time left, cash, open orders | Yes | `sim.State` |
| The rule that moves the state forward one second, given recipe switches | No (pure rule) | `sim.FactorySim.step` |
| Whoever decides: a fixed rule, random, or a trained model | n/a | `policies.py` |
| Whoever watches: history, charts, Excel, web pages | n/a | `recorder.py`, `plots.py`, `web.py`, `training.py` |

The RL interface (`env.py`; RL means reinforcement learning, where a program learns by trial and error, guided by a reward) is a translation layer. It turns the state into numbers for a neural network, turns the network's plan into recipe switches, and reports the cash change as the reward.

## How data flows

```
scenarios/*.yaml ──load──▶ Scenario (frozen)
                              │
                              ▼
   Policy ──plan──▶ FactoryEnv ──switches──▶ FactorySim.step() ──▶ State
     ▲                 │                          │
     └──observation────┘                          └──StepReport──▶ Recorder ──▶ Excel, charts, pages
```

Dependencies point one way only: `spec` ← `sim` ← `env` ← `policies`. `evaluate` runs whole episodes; `recorder`, `plots` and `web` only read.

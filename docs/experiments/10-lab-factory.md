# 10. A small lab factory for quick experiments

2026-10-02. Run folder: `runs/1002_220856-train`.

## What changed and why

The old factory's numbers were inherited from an early prototype. A Motor needs about 29 iron bars, so the constructors were a hidden bottleneck, and it took a linear program ([experiment 9](09-bottleneck-analysis.md)) to find out what limits profit. On the usual orders, demand was the limit (about 280 units ordered against about 440 possible), so comparisons said little about planning. A training run took 13 minutes, and every scenario variant copied the whole 80-line file.

Three changes:
- **`scenarios/lab.yaml`, now the default:** 9 machines (3 smelters, 3 constructors, 3 assemblers) with 2 recipes each. Every product needs exactly 30 s from each kind, so the factory makes at most 360 products per hour, whatever the mix. Orders ask for about 300 units per hour-long episode, with the mix drawn per episode and each order known 600 to 1800 s ahead. Details are in [simulation.md](../design/simulation.md#the-lab-scenario-scenarioslabyaml-the-default).
- **Variant files:** `base: lab.yaml` plus only the fields that change. `lab-busy.yaml` is an example: 30 to 50 orders, more than the factory can make.
- **`python -m sjfactory check`:** shows how loaded each machine kind is, plus keep, the oracle, any models and the upper bound on seeds 2000 to 2009. It takes under a minute and needs no training. It replaces `scripts/ceiling.py`.

## Settings

Training defaults (move cost 50, 20 processes, test seeds 1000 to 1002), 500k steps, `scenarios/lab.yaml`.

## Results

Training took 3.9 minutes. The model passed keep within the first 25k steps, reached about 145k on the test seeds by 150k steps, and ended at about 149k (keep: 17k on these 3 seeds).

`check` on new seeds 2000 to 2009, mean profit, with the share of the upper bound:

| Scenario | Keep | Model | Oracle, played | Upper bound |
|---|---|---|---|---|
| `lab.yaml` (86% of machine time needed) | 41,290 (32%) | **124,210 (96%)** | 125,650 (97%) | 130,000 |
| `lab-busy.yaml` (114% needed; not trained on) | 31,940 (22%) | 132,440 (91%) | **139,430 (95%)** | 146,210 |

## What it taught

- **A full experiment now takes about 5 minutes:** under a minute for `check`, about 2 minutes of training to reach the plateau.
- **The lab factory is solved at its base settings.** The model is within 1% of the oracle, so this is the reference to compare changes against. An idea shows up as a change in the share of the upper bound that keep, the model and the oracle reach.
- **With more orders than capacity, the model trained on normal demand leaves 4 points to the oracle.** Choosing which orders to leave short is a skill it hasn't trained on.

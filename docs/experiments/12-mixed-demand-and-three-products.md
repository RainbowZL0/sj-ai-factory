# 12. Mixed demand, and a third product that starves the line

2026-10-02. Run folders: `runs/1002_224202-train` (`lab-mixed.yaml`), `runs/1002_224900-train` (`lab-three.yaml`), `runs/1002_225242-train` (`lab-three-downstream.yaml`). All 500k steps with the training defaults, 3.5 to 4 minutes each.

## What changed and why

- **Mixed demand** (`lab-mixed.yaml`: 15 to 50 orders per episode). [Experiment 11](11-lab-variants.md) found that training on more orders than capacity gave the best model; would a range of demand levels do better still?
- **`check` shows the oracle's plan as planned,** next to its result when played. The gap is what the plan loses to flow within a minute: batches, and machines waiting for inputs.
- **A third product** (`lab-three.yaml`): Pump = 1 Gear + 1 Plate + 1 Wire, where a constructor makes a Gear from 2 Plates. Plates now go to two depths: gear making, and the assemblers. It runs on 4 smelters, 4 constructors and 3 assemblers, and the orders need 60 to 73% of each kind's time. `lab-three-downstream.yaml` is the same with `input_priority: downstream`.

## Results

Mean profit on seeds 2000 to 2009, share of the upper bound in brackets.

Demand levels:

| Model trained on | `lab.yaml` | `lab-busy.yaml` | `lab-mixed.yaml` |
|---|---|---|---|
| Keep (no model) | 41,290 (32%) | 31,940 (22%) | 33,430 (27%) |
| `lab.yaml` | 124,210 (96%) | 132,440 (91%) | 116,680 (94%) |
| `lab-busy.yaml` | **125,590 (97%)** | **135,440 (93%)** | **118,990 (96%)** |
| `lab-mixed.yaml` | 124,810 (96%) | 132,320 (90%) | 118,180 (96%) |
| Oracle, played | 125,650 (97%) | 139,430 (95%) | 120,010 (97%) |
| Oracle, as planned | 130,830 (101%) | 147,080 (101%) | 124,660 (101%) |
| Upper bound | 130,000 | 146,210 | 123,550 |

The oracle's plan can be above the bound because it treats flow within a minute as smooth.

Three products:

| | `lab-three.yaml` (machine order) | `lab-three-downstream.yaml` |
|---|---|---|
| Keep | -77,240 (-55%), ships nothing | 39,580 (28%) |
| Model trained on `lab-three.yaml` | **130,180 (93%)** | 128,440 (92%) |
| Model trained on `lab-three-downstream.yaml` | 122,830 (88%) | **132,280 (95%)** |
| Oracle, played | 73,450 (53%) | 109,960 (79%) |
| Oracle, as planned | 139,750 (100%) | 139,750 (100%) |
| Upper bound | 139,348 | 139,348 |

In machine order, keep ends with 358 gears, 359 wires and 2 plates. The gear constructor is listed before the assemblers, so it takes every plate as soon as two exist, and no assembler ever gets one.

## What it taught

- **Training on busy days is enough.** A range of demand levels did not beat training on more orders than capacity, even on the mixed orders themselves.
- **Who gets inputs first matters when a material feeds two depths.** It changed nothing in the larger factory or the plain lab, but here it turns keep from -77k into 40k and lifts the oracle from 53% to 79% of the bound.
- **The model works around starvation that the oracle can't see.** The oracle plans whole minutes and doesn't model which machine gets inputs first. Its plan loses half its value when played, while the models reach 93 to 95% of the bound. The oracle is a good yardstick only when flow within a minute is smooth.
- **The upper bound is the reliable yardstick.** In both lab-three versions the best model is within 5 to 7 points of it.

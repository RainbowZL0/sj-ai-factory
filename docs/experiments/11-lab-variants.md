# 11. Factory ideas tried on the lab factory and its variants

2026-10-02. Run folders: `runs/1002_220856-train` (trained on `lab.yaml`, from [experiment 10](10-lab-factory.md)), `runs/1002_222259-train` (`lab-busy.yaml`), `runs/1002_222657-train` (`lab-storage.yaml`). All 500k steps with the training defaults, each under 4 minutes.

## What changed and why

The ideas for more profit from [experiment 9](09-bottleneck-analysis.md), each tried with `check` first, then with training where it could matter:
- **Input priority.** New scenario setting `input_priority: downstream`: when stock is short, machines whose recipe is furthest from the raw materials get inputs first. The default (`machine_order`) is unchanged, and keep still makes 52,050 on seed 0 of `default.yaml`.
- **Storage costs** (`lab-storage.yaml`). The upper bound and the oracle now count storage and energy costs too.
- **One tight machine kind** (`lab-bottleneck.yaml`: 4 smelters and 4 constructors, so only the assemblers are tight).
- **More orders than capacity** (`lab-busy.yaml`), trained on.

## Results

Mean profit on seeds 2000 to 2009, share of the upper bound in brackets.

Input priority, on the larger casters factory (in the lab factory no material is shared between recipes at different depths, so it changes nothing there):

| Scenario | Keep | Usual model | Varied model | Oracle, played | Upper bound |
|---|---|---|---|---|---|
| `casters.yaml` | 80,615 (56%) | 126,980 (89%) | 117,275 (82%) | 123,095 (86%) | 142,823 |
| `casters-downstream.yaml` | 80,855 (57%) | 126,905 (89%) | 117,830 (83%) | 124,250 (87%) | 142,823 |

One tight machine kind, no training:

| Scenario | Keep | Oracle, played | Upper bound |
|---|---|---|---|
| `lab.yaml` | 41,290 (32%) | 125,650 (97%) | 130,000 |
| `lab-bottleneck.yaml` | 69,460 (53%) | 129,370 (100%) | 130,000 |

Three lab models, each tested on every scenario:

| Model trained on | `lab.yaml` | `lab-busy.yaml` | `lab-storage.yaml` |
|---|---|---|---|
| Keep (no model) | 41,290 (32%) | 31,940 (22%) | 23,009 (18%) |
| `lab.yaml` | 124,210 (96%) | 132,440 (91%) | 114,262 (90%) |
| `lab-busy.yaml` | **125,590 (97%)** | **135,440 (93%)** | **115,712 (91%)** |
| `lab-storage.yaml` | 124,540 (96%) | 130,970 (90%) | 114,792 (91%) |
| Oracle, played | 125,650 (97%) | 139,430 (95%) | 118,237 (93%) |
| Upper bound | 130,000 | 146,210 | 126,705 |

## What it taught

- **Input priority is not where the batch-flow loss comes from.** Serving machines further down the line first moves every result by 1 point of the bound or less. The 10 to 15% the larger factory loses to batch flow must come from elsewhere, for example machines waiting for a full batch of inputs.
- **Spare time before the bottleneck absorbs switching losses.** With extra smelters and constructors the upper bound stays the same (the assemblers set it), but the oracle reaches 100% of it and keep goes from 41k to 69k.
- **Storage costs hurt keep, not a model.** Keep piles up parts and loses 18k to storage. A model that plans for the orders pays little, even if it never saw storage costs in training. Training with them did not help.
- **Training on more orders than capacity gave the best model on every scenario,** up to 2 points behind the oracle. The differences between models are 1 to 3k on 10 seeds, so they are small; a mix of demand levels might help more.

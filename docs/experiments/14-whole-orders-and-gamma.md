# 14. Whole orders only, and looking further ahead (gamma)

2026-10-02. Run folders, all 500k steps under the new rules: `runs/1002_233133-train` (`lab.yaml`), `runs/1002_233508-train` (`lab-busy.yaml`), `runs/1002_233856-train` (`lab-three-downstream.yaml`, gamma 0.97), `runs/1002_234310-train` (the same, gamma 0.98), `runs/1002_234706-train` (gamma 0.99). Older models, trained under the old rules, for comparison: `1002_222259` (`lab-busy.yaml`) and `1002_225242` (`lab-three-downstream.yaml`).

## What changed and why

- **Whole orders only** (new scenario setting `partial_delivery: false`, now in `lab.yaml`). A real customer doesn't pay for part of an order and fines a late one, and a big order from a big customer is fined more. So an order ships only if the full quantity is in stock; otherwise nothing is paid and every unit of the order is fined. The fine per unit is now the full price (Motor 600, Frame 400, Pump 800), where it was half before. Under the old rules a partly filled order still paid per unit, so spreading units thinly was almost as good as finishing orders.
- **The oracle chooses whole orders.** Each order is either filled or not. The upper bound still allows filling part of an order, which can only make it higher, so it stays a true bound.
- **Gamma 0.98 and 0.99** (was 0.97): how much a reward one minute later counts. Under whole orders the money arrives in lumps at due times, up to 30 minutes after the decisions that earned it. At 0.97, a payment 30 minutes away counts for 40%; at 0.98 for 55%; at 0.99 for 74%.
- **Pages:** the report now names its seed, and the training chart of units shipped says it is a mean over the test seeds. The report shows only the first test seed, which can be far from the mean: in `1002_225242` it shipped 77% on seed 1000, while the chart showed 91% (seeds 1000 to 1002: 77%, 94%, 100%).

## Results

Mean profit on seeds 2000 to 2009 under the new rules, share of the upper bound in brackets:

| Scenario | Keep | Model, old rules | Model, new rules | Oracle, played | Upper bound |
|---|---|---|---|---|---|
| `lab.yaml` | -2,880 | 112,400 (91%) | 109,760 (89%) | 109,000 (88%) | 123,240 |
| `lab-busy.yaml` | -31,840 | 101,480 (79%) | 101,480 (79%) | **112,120 (87%)** | 129,040 |
| `lab-three-downstream.yaml` | -4,120 | 120,520 (89%) | 121,480 (89%) | 97,600 (72%) | 136,104 |

"Model, old rules" is the model trained on `lab-busy.yaml` for the first two rows, and on `lab-three-downstream.yaml` for the third.

Gamma, on `lab-three-downstream.yaml` under the new rules:

| Gamma | Profit | Share of bound | Units shipped (Motor, Frame, Pump) |
|---|---|---|---|
| 0.97 | **121,480** | **89%** | 78, 96, 65 |
| 0.98 | 111,280 | 82% | 74, 90, 64 |
| 0.99 | 116,400 | 86% | 73, 95, 66 |

The 0.99 run was still setting new bests at the end; the other two had levelled off.

## What it taught

- **Whole orders change the scores, not the models' behaviour.** Models trained under the old rules do as well under the new ones as models trained under them. They already filled most orders in full, since partial fills only happen when stock runs out.
- **The weak spot is busy days: choosing which orders to drop.** With more orders than capacity, the model is 8 points behind the oracle (79% against 87%), and training under the new rules didn't close it. Here the new rules matter most: an order 1 unit short earns nothing, so a plan has to give up whole orders on purpose.
- **Looking further ahead didn't help in 500k steps.** Gamma 0.98 and 0.99 both did worse than 0.97. A longer look-ahead makes the reward estimates noisier and learning slower, and 0.99 was still improving, so it may need more steps.
- **Decision: gamma stays at 0.97.**

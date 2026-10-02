# 19. One model for every two-product day

2026-10-03. Roadmap milestone 6, step 1. Run: `runs/1003_024435-train` (4M steps, about 29 minutes). Compared with the models trained on one kind of day: `runs/1003_003814-train` (busy days, 2M steps, experiment 16), `runs/1003_013405-train` (short notice) and `runs/1003_015135-train` (breakdowns, both experiment 18). All numbers from `bench`: 30 days per kind of day (seeds 2000 to 2029), share of the upper bound.

## What changed and why

After experiment 18 each kind of day had its own best model, and the breakdown model could not even play days without breakdowns, because it sees one more number per machine. A real factory doesn't know in the morning what kind of day it will be, so it needs one model for all of them.

- **`train --mix a.yaml b.yaml ...`**: the 20 training processes take turns over the scenarios given (`--scenario` plus the mix), so each update learns from all kinds of day at once. The test episodes during training still use `--scenario`. The mix is saved in the run's `config.json`.
- **`show_breakdowns`**: an environment setting that always shows each machine's repair time left (0 on days without breakdowns). `train --mix` turns it on when any scenario in the mix has breakdowns, and saves it with the model, so `check`, `bench` and `eval` set it up again.
- The run: `--scenario lab-busy.yaml --mix lab-mixed.yaml lab-short.yaml lab-breakdowns.yaml`, 4M steps, so about 1M steps per kind of day.

## Results

| Policy | Light to busy | Busy | Short notice | Breakdowns |
|---|---|---|---|---|
| Keep | -22% | -31% | -26% | -43% |
| One model, final | 86% | 83% | 82% | 69% |
| One model, best on its test days | 86% | 84% | 82% | **76%** |
| Busy-day model | **88%** | **86%** | 82% | can't play |
| Short-notice model | 82% | 77% | **83%** | can't play |
| Breakdown model | can't play | can't play | can't play | 74% |
| Oracle, planned once | 87% | 86% | 85% | 70% |
| Re-planned every 5 minutes, all orders | 91% | 90% | 87% | 71% |
| Re-planned every 5 minutes, known orders | 86% | 82% | 61% | 71% |

## What it taught

- **One model nearly matches the specialists**: 1 to 2 points behind on light-to-busy, busy and short-notice days, and 2 points ahead on breakdown days, where it also beats every planner. On 30 days a difference of 2 points is about the size of the noise between days (experiment 16), so the losses may be partly chance.
- **It still matches or beats the fair planner on every kind of day** (by 0 to 21 points), so the roadmap goal holds for a single model.
- **Final and "best" models differ by 7 points on breakdown days.** Breakdown days vary a lot, so the final model's last update may just have moved it; this is why `bench` looks at both.
- Each kind of day got about 1M steps here against 2M for the specialists. Longer training of the mix is the obvious next try.

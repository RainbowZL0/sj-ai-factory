# 16. Busy days: longer training, order slack, and how many days to test on

2026-10-03. Roadmap milestone 3, steps 1 and 2. Run folders, both on `lab-busy.yaml`, 2M steps, gamma 0.97: `runs/1003_003814-train` (as before, only longer) and `runs/1003_004241-train` (with `--order-slack`). For comparison, the 500k-step model of experiment 14: `runs/1002_233508-train`.

## What changed and why

- **Longer training** (step 1): 2M steps instead of 500k, the cheapest thing to try.
- **Order slack** (step 2, `train --order-slack`): experiment 15 showed the model loses by making products for orders that then come up short. So for each of the 20 visible orders the model also sees the time to spare at its due time, if the factory makes it and the earlier orders that fit, at full speed. A negative number says the order no longer fits. It saves the model from adding up the work of all earlier orders itself.
- **More test days.** The first checks below disagreed with each other by several points, so the models were also played on 30 and 60 busy days.

## Results

Share of the upper bound on busy days (`lab-busy.yaml`). "Final" is the model at the end of training (`model.zip`); "best" is the one that scored best on the 3 test seeds during training (`best_model.zip`).

| Policy | Days 2000-2009 | Days 2010-2029 | Days 2000-2029 |
|---|---|---|---|
| 500k steps (experiment 14), best | 79% | 83% | |
| 500k steps, final | | 83% | 83% |
| 2M steps, best | 83% | 84% | |
| 2M steps, final | **87%** | **85%** | 86% |
| 2M steps with order slack, best | | | 84% |
| 2M steps with order slack, final | | | **87%** |
| Oracle, played | 88% | 85% | 85% |
| Oracle, as planned | 101% | 99% | 99% |

Day by day on 60 days (2000-2059), the order-slack model against the plain 2M model: busy days +740 per day (95% margin ±2,100), better on 16 days; light-to-busy days (`lab-mixed.yaml`) +390 (±1,650), better on 12 days. On the other days they tie or the plain model wins.

The learning curve on the 3 test seeds stops rising after about 400k steps and then wanders between 123k and 135k.

On 30 busy days, the machine time of the order-slack model: 86% in shipped units, 9% in unsold products, the same as the oracle.

## What it taught

- **The busy-day gap is closed.** After 2M steps the model is level with the oracle on busy days (86-87% against 85% over 30 days), and wastes no more machine time than the oracle does.
- **Ten days are too few on busy days.** The same 500k model scored 79% on days 2000-2009 and 83% on days 2010-2029; the oracle 88% and 85%. Much of the "8-point gap" of experiment 14 came from which 10 days were drawn. `bench` now uses 30 days per kind of day; comparing two models day by day on the same days is better still.
- **Use the final model, not only the "best" one.** The best model is picked on just 3 test seeds, so it is the luckiest on those 3 days, not the best on new ones. The final model did better on new days in every run here.
- **Order slack doesn't help measurably.** The model seems to work out which orders fit by itself, given enough training. The option stays (`--order-slack`) but is not the default.
- **What is left is shared with the oracle.** Both lose about 14% of the bound; the oracle's plan reaches 99% on paper and loses it when played, in flow within a minute (batches, waiting for inputs) and in orders that come up a few units short. Whether a better schedule exists in the real simulator is unknown: the bound can't say, because it ignores batches and changeovers.

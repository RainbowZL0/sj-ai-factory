# 6. Does the model only fit the test orders?

Model `1002_163351-train/best_model.zip` (experiment 5, keep bias 0), 2026-10-02. No training; `scripts/other_orders.py` played it on new orders.

## Question

The best model is picked by its score on test seeds 1000 to 1002. Training itself draws new random orders every episode, so the model never sees the same orders twice, but the pick could still favour a model that suits those 3 seeds. And all training orders have the same shape: 50 orders, Motor or Frame with equal chance, 1 to 10 units each. Does the model still win on new seeds, and on orders of a different shape?

## Results

Mean profit over 30 seeds (2000 to 2029) per row, except the first row. "Model < keep" counts the seeds where the model (most likely choice) earned less than keep.

| Orders | Keep | Model, most likely | Model, sampled | Model / keep | Model < keep | Shipped, keep / model |
|---|---|---|---|---|---|---|
| Training shape, test seeds 1000 to 1002 | 58,900 | 120,950 | 117,450 | 2.05 | 0 of 3 | 39% / 90% |
| Training shape, new seeds | 83,200 | 128,550 | 127,980 | 1.55 | 0 of 30 | 49% / 90% |
| Fewer orders (25) | 36,960 | 65,890 | 65,620 | 1.78 | 0 of 30 | 46% / 94% |
| More orders (100) | 117,480 | 113,300 | 109,700 | 0.96 | 21 of 30 | 41% / 58% |
| Bigger orders (5 to 20 units) | 94,260 | 83,990 | 83,110 | 0.89 | 24 of 30 | 36% / 50% |
| Mostly Motor (80%) | 145,170 | 135,490 | 137,400 | 0.93 | 21 of 30 | 73% / 83% |
| Mostly Frame (80%) | 7,620 | 87,590 | 86,000 | 11.5 | 0 of 30 | 20% / 85% |

## What it taught

- **Not tied to the 3 test seeds.** On 30 new seeds of the training shape it beats keep every time. The test seeds are just harder than average (keep makes 58,900 there and 83,200 on new seeds).
- **Tied to the shape of the training orders.** When demand is higher than the factory can make (100 orders, or bigger ones) or mostly Motors, it loses to keep. In those cases the best answer is to put everything into Motors (800 each, against 300 for a Frame), but the model keeps its usual Motor and Frame split. It has learned one good plan for the usual mix of orders, not how to read the orders it is shown.
- **Fix to try:** train on orders of varied shape, drawing the number of orders, their size and the Motor/Frame mix at random per episode, so that reading the orders pays off.

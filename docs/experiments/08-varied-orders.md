# 8. Orders that can be filled, varied orders, and a move cost

Runs, 1M steps each, 10 environments each (3 run at the same time), 2026-10-02:
- `1002_194645-train`: casters scenario, move cost 50
- `1002_194725-train`: varied-orders scenario, move cost 50 (10 test seeds)
- `1002_194816-train`: varied-orders scenario, no move cost (10 test seeds)

## Why

- **Impossible orders.** In experiment 7 every unit the model missed belonged to an order due in the first 600 s. The first Frame can't exist before about 550 s, so those orders can't be filled by any plan: the model was already at the ceiling for that order mix (all later orders were filled in full).
- **One plan for one order mix.** [Experiment 6](06-other-orders.md) showed the model loses to keep when the orders take another shape.
- **Changeovers.** The move action still switched about 2 machines a minute.

## Changes

- Orders can have a **notice** time: an order becomes known that many seconds before it is due, and the model can't see it before then. Nothing is due before the shortest notice. This also adds orders arriving during the episode.
- **Varied orders** per episode: number of orders, units per order, and the Motor/Frame mix, with a quarter of episodes ordering one product only. Both are optional scenario settings; [scenarios/varied.yaml](../../scenarios/varied.yaml) uses them on the casters factory (see [simulation.md](../design/simulation.md#the-varied-orders-scenario-scenariosvariedyaml)).
- The observation gains the units still ordered per product, over all known orders.
- **Move cost** (`--move-cost`): taken off the reward for every machine moved in the plan. Profit is not affected.

## Results

Test profit, model taking its most likely choice, at the end of training:

| Run | Test profit | Keep | Switches in report episode |
|---|---|---|---|
| Casters, no move cost ([exp. 7](07-move-action-and-casters.md)) | 117,900 | 58,100 | 203 |
| Casters, move cost 50 | 116,300 | 58,100 | 174 |
| Varied, no move cost | 132,300 | 79,400 | 203 |
| Varied, move cost 50 | 135,650 (still rising) | 79,400 | 46 |

All on the casters factory, 30 new seeds per row (`scripts/other_orders.py --scenario scenarios/casters.yaml`). Model profit minus keep profit, and in brackets the seeds where the model earned less than keep:

| Orders | Keep | Trained on usual orders (move cost 50) | Trained on varied orders, move cost 50 | Varied, no move cost |
|---|---|---|---|---|
| Usual shape (50 orders, even mix, 1 to 10 units) | 82,560 | **+44,030** (0) | +34,120 (0) | +32,350 (0) |
| Fewer orders (25) | 36,440 | +27,810 (0) | +27,130 (0) | +24,340 (0) |
| More orders (100) | 117,360 | -2,250 (19) | **+22,930** (0) | +20,670 (1) |
| Bigger orders (5 to 20 units) | 94,100 | -17,270 (24) | **+20,280** (0) | +16,470 (4) |
| Mostly Motor (80%) | 144,650 | +6,050 (5) | +4,310 (8) | +3,000 (12) |
| Mostly Frame (80%) | 7,140 | +86,730 (0) | +85,810 (0) | +86,100 (0) |
| Almost only Motor (99%) | 164,590 | -3,400 (17) | **+11,320** (4) | +11,920 (4) |
| Almost only Frame (99%) | -42,880 | +114,850 (0) | +116,300 (0) | +114,420 (0) |
| Known 900 to 2400 s before due | 87,310 | **+56,840** (0) | +46,750 (0) | +47,130 (0) |
| Tough: 100 orders of 5 to 20 units, known 900 to 2400 s ahead | -51,520 | -13,810 (27) | **+18,370** (0) | +14,140 (0) |

## What it taught

- **Varied training makes a model that reads the orders.** It beats keep on all 30 seeds when demand is more than the factory can make, where the model trained on the usual orders loses on most seeds, and it wins on Motor-only orders. On the tough case everyone loses money (penalties can't be avoided), but it loses 18k less than keep.
- **The price is about 10k on the usual order shape** (+34k against +44k over keep). The varied model was still improving at 1M steps, so longer training may close part of this.
- **The move cost cuts changeovers without hurting profit.** On varied orders: 46 switches instead of 203, and slightly higher profit everywhere. On the usual orders the cut was smaller (203 to 174). It is now the default (50).
- **Notice times remove the impossible orders.** With orders known 900 to 2400 s ahead, the usual model ships 96% of units.

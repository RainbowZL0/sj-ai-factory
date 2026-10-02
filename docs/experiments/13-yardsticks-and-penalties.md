# 13. A look-ahead yardstick, and do stricter penalties teach better priorities?

2026-10-02. Run folders: `runs/1002_225242-train` (`lab-three-downstream.yaml`, from [experiment 12](12-mixed-demand-and-three-products.md)), `runs/1002_231115-train` (`lab-three-strict.yaml`), `runs/1002_231458-train` (`lab-three-orderfine.yaml`). All 500k steps with the training defaults.

## What changed and why

- **Downstream input priority is now set in `lab.yaml`,** so every lab variant has it. The plain lab gives identical results. `lab-three.yaml` sets machine order explicitly, so experiment 12 still repeats.
- **Look-ahead planner** (`sjfactory/lookahead.py`, a row in `check`). The oracle can't see which machine gets inputs first, so on `lab-three` its plan lost half its value when played. The look-ahead planner plays in the real simulator instead. Each minute, for one machine kind at a time, it tries every move, plays it 30 minutes ahead in a copy of the factory, and keeps the best.
- **The question:** in a test episode the model made 1 of 15 ordered Motors and spent the assemblers on Frames, although a Motor is worth more for the same assembler time. Would stricter penalties teach it which product deserves the machines? Two variants of `lab-three-downstream.yaml`:
  - `lab-three-strict.yaml`: a missing unit costs twice its price instead of half;
  - `lab-three-orderfine.yaml`: an extra fine of 3,000 for each order not filled in full (new material field `order_fine`).

  Each model was scored under all three sets of rules. Under the normal rules, a better model is one that really learned better priorities.

## Results

### Look-ahead window

Mean over seeds 2000 to 2005:

| Window | `lab.yaml` | `lab-three-downstream.yaml` |
|---|---|---|
| 10 minutes | 120,767 | 95,450 |
| 20 minutes | 129,367 | 113,850 |
| 30 minutes | 137,617 | 114,550 |

Over 10 seeds with a 10-minute window it reached 89% of the bound on `lab.yaml` (model 97%) and 73% on `lab-three-downstream.yaml` (model 95%). Unfinished parts are worth nothing to it, which makes it short-sighted. It sees the real flow, but it is weaker than a trained model, so the upper bound stays the main yardstick.

### The missed Motors (test seed 1000)

The orders needed 111% of the assemblers' time. The upper bound ships 15 Motors, 212 Frames and 113 Pumps; the model shipped 1, 205 and 103. Plates and wire were in stock the whole time. Replaying the episode with one assembler kept on Motors from 1,380 s:

| Assembler on Motors | Profit | Motors | Frames | Pumps |
|---|---|---|---|---|
| As the model played (1 minute) | 141,800 | 1 | 205 | 103 |
| 1,380 to 1,860 s | 143,000 | 15 | 190 | 101 |
| 1,380 to 1,920 s | 145,400 | 15 | 188 | 104 |
| 1,380 to 2,040 s | 141,200 | 15 | 185 | 102 |

### Stricter penalties

Mean profit on seeds 2000 to 2009, share of the upper bound in brackets. Units shipped per episode in the last column (Motor, Frame, Pump).

| Model trained on | Normal rules | Strict penalties | Order fine | Units shipped |
|---|---|---|---|---|
| Normal rules | 132,280 (95%) | 115,480 (89%) | 123,880 (89%) | 80, 98, 66 |
| Strict penalties | **132,760 (95%)** | **116,440 (90%)** | **124,960 (90%)** | 80, 98, 66 |
| Order fine | 131,170 (94%) | 113,260 (87%) | 122,170 (88%) | 78, 98, 66 |
| Keep | 39,580 (28%) | -69,920 | -9,020 | 65, 0, 48 |
| Oracle, played | 109,960 (79%) | 81,880 (63%) | 88,660 (64%) | 74, 67, 67 |
| Upper bound | 139,348 | 129,616 | 139,348 | |

### Order notice

Orders become known 600 to 1,800 s ahead (mean about 1,130 s, 19 decisions). Making one product from ore takes 50 to 60 s, or about 150 s with a changeover at every stage. The upper bound assumes every order is known from the start, and the model still reaches 95 to 97% of it. The model is shown only the 20 earliest-due known orders. Sometimes more are known: in 2% of minutes on `lab.yaml` and 9% on `lab-busy.yaml` (up to 27 at once).

## What it taught

- **Stricter penalties don't change priorities.** All three models ship the same units under every set of rules, within 1.6k of each other. Doubling every penalty keeps the products' values in the same ratio, and training rescales rewards anyway, so the signal for which product deserves machines stays just as weak. A fine per order didn't change the mix either.
- **The missed Motors were a small mistake, not a blind spot.** Every Motor made displaces about a Frame on the busy assemblers, so the most to gain was 15 × (900 − 600) = 4,500, less two changeovers: 1 to 2.5% of the profit. That is too small to stand out from the usual differences between episodes. The model did try Motors for one minute.
- **Notice is generous.** It is 10 to 30 times the time to make a product, and the model gets 95 to 97% of a bound that knows every order from the start. The lab tests dividing machine time, not quick reactions.
- **Ties in input priority still starve.** Under keep, `lab-three-downstream.yaml` ships no Frames: the gear maker and the Frame assembler are at the same depth, and the gear maker is listed first, so it still gets the plates.
- **The look-ahead planner sees the flow but is weak.** It is useful for showing what starvation costs, not as a target to beat.

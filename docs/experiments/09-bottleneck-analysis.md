# 9. What limits profit now? (analysis, no training)

2026-10-02. Models from [experiment 8](08-varied-orders.md): `1002_194645-train` (trained on the usual orders, casters factory, move cost 50) and `1002_194725-train` (trained on varied orders, move cost 50). Tool: `scripts/ceiling.py`.

## Two yardsticks

- **Upper bound** (linear program, a standard method for finding the best split of limited resources): machines may be split into fractions, no changeovers, every order known in advance, batch outputs never later than possible. No policy can beat it.
- **Oracle** (integer program): whole machines per recipe each minute, 30 s changeover per machine added, every order known in advance; its plan is then played in the simulator. It loses 10 to 30% of its planned profit when played, so it is a reference point, not a bound.

## Results

Mean profit over 30 new seeds (2000 to 2029), casters factory:

| Orders | Keep | Usual model | Varied model | Oracle, played | Upper bound |
|---|---|---|---|---|---|
| Usual | 82,560 | **126,590** | 116,680 | 124,990 | 143,310 |
| Usual, known 900 to 2400 s ahead | 87,310 | **144,150** | 134,060 | 138,180 | 151,150 |
| Varied (`varied.yaml`) | 47,640 | 91,620 | **110,410** | 99,070 | 131,090 |
| Tough: 100 orders of 5 to 20, known late | -51,520 | -65,330 | -33,150 | **-30,820** | 3,570 |

Capacity at steady state, if machines could be split into fractions: at most 210 Motors per hour, or 375 Frames, or a mix worth about 255k per hour (sell price plus penalty avoided). With whole machines, and machines allowed to wait for inputs, the best is all Motors: 192 per hour, about 230k per hour.

Seconds of machine time per Motor, divided by the number of machines of that kind:

| Kind | Per Motor | Machines | Per Motor per machine |
|---|---|---|---|
| Constructors (about 29 iron bars at 4 s each, plus screws, tubes, wire) | 240 s | 14 | 17 s |
| Casters | 86 s | 6 | 14 s |
| Assemblers | 66 s | 5 | 13 s |

For Frames the assemblers are the tightest (PlateAssemble and FrameFinal, about 10 s per Frame per machine).

In the varied model's episodes (10 seeds), the bar, screw and iron-caster machines are busy 96 to 98% of the time in the tough case; MotorFinal waits for rotors and stators about 30% of the time, plate machines up to 38%. Hundreds of ingots, bars, screws and plates are left over at the end.

The oracle needs more than one move per kind in only 0 to 6 of 84 minutes, but switches 60 to 110 times per episode on purpose, sharing machines between recipes.

## What it taught

- **The model is no longer the main limit.** On every order type it matches or beats the oracle, which knows all orders in advance.
- **With the usual orders, demand is the limit:** about 280 units are ordered against roughly 440 the factory could make; the usual model gets 95% of the upper bound when orders are known in advance.
- **With heavy orders, the factory is the limit:** constructor time for iron bars and screws (a Motor needs about 29 bars).
- **The rest of the gap to the upper bound is batch flow,** not decisions: machines waiting for a full batch of inputs and parts left over. Even the oracle's plan loses 10 to 30% when played.
- **The one model weakness:** the varied model is 10k behind the usual model on the usual orders and was still improving at 1M steps.
- **One move per kind per minute is fast enough,** and some switching is useful, so the move cost should not go above 50.

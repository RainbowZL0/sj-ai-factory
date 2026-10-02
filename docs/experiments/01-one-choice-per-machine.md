# 1. One choice per machine, no costs

Run `1002_145729-train`, 200k steps, 2026-10-02.

## Setup

Every 10 s, each idle machine picked keep, stop, or one of its recipes. No changeover time, no penalties for missed orders, energy free. `gamma` 0.995, 4 environments. Tested without randomness only.

## Results

| Check | Test profit, no randomness | Score while training (with randomness) | Keep |
|---|---|---|---|
| 20k steps (best) | 80k | about 19k | 86.3k |
| 80k to 200k steps | about 0 to 3.6k | rising to 54.5k | 86.3k |

On seed 1000 the final model made 75.6k with randomness but 23.7k without. Without randomness, 9 of 14 constructors ended on iron bars and none on wire, so no stators and no motors. After 200k steps the model's choices were still almost evenly spread (entropy 26 down to only 24.8), and it changed a recipe about every second.

## What it taught

- Drawn at random, the even spread of choices happened to balance the factory; taking each machine's most likely choice sent them all to the same recipe. Test both ways.
- One choice per machine, all sharing one reward, makes it very hard to learn which choice earned the money.
- Free switching and free missed orders were exploited.
- Casters kept choosing between recipes that can never run.

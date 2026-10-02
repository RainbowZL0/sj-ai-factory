# 2. Changeover time, penalties, keep bias 5

Run `1002_152729-train`, 200k steps, 2026-10-02. Still one choice per machine every 10 s.

## Changes

- 30 s changeover after switching to a different recipe.
- Shortfall penalties: Motor 400, Frame 150 per missing unit. Keep's test profit fell from 86.3k to 58.9k.
- Recipes that can never run, the current recipe, and stop for a stopped machine are hidden from the choices.
- Stock also shown in batches; per machine, changeover left and waiting for inputs; cash removed from the observation.
- Rewards normalized during training (`VecNormalize`).
- Tests both without randomness ("fixed") and with it ("sampled").
- A fresh model prefers keep (`--keep-bias 5`).

## Results

Without the keep bias, the fresh model switched constantly: about -55k, machines busy 10% of the time (keep: 70%).

| Steps | Fixed | Sampled | Keep |
|---|---|---|---|
| 0 | 58,900 | -50,100 | 58,900 |
| 100k | 58,900 | 54,250 | 58,900 |
| 190k (best) | 58,900 | 71,950 | 58,900 |

## What it taught

- The changeover made random switching costly, as intended, but a fresh model then starts deep in a hole.
- With the bias, the useful switches stayed low-probability choices, so the most likely choice was always keep.

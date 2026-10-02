# 5. Keep bias 0, 1, 2, 3 at 1M steps

Runs `1002_163351-train` (0), `1002_164644-train` (1), `1002_170001-train` (2), `1002_171308-train` (3); 2026-10-02. About 13 minutes each.

## Results

| Keep bias | Fixed at 200k | Fixed at end | Sampled at end | Shipped |
|---|---|---|---|---|
| 0 | 81,400 | 120,950 | 117,450 | 90% |
| 1 | 54,300 | 120,400 | 116,100 | 89% |
| 2 | 59,400 | 115,600 | 116,900 | 86% |
| 3 | 58,900 | 119,900 | 120,450 | 88% |
| Keep | 58,900 | 58,900 | 58,900 | 39% |

Learning health at the end: reward prediction quality about 0.97 to 0.98 (1 is perfect).

## What it taught

- With enough training every bias reaches the same level, about twice keep, with or without randomness.
- Bias 0 gets there fastest, so it became the default, along with 1M steps.
- The best model runs each assembler recipe on one machine, so Frames get made, but changes the constructor plan almost every minute (see [Next steps](README.md#next-steps)).

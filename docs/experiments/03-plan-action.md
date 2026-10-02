# 3. Plan action

Run `1002_155320-train`, 200k steps, 2026-10-02.

## Changes

The action became a plan: how many machines of each kind run each recipe, decided every 60 s (see [rl-interface.md](../design/rl-interface.md)). `gamma` 0.97. Keep bias 5, now applied to the starting plan.

## Results

| Steps | Fixed | Sampled | Keep |
|---|---|---|---|
| 0 | 58,900 | 56,600 | 58,900 |
| 100k | 58,900 | 64,250 | 58,900 |
| 200k | 58,900 | 74,450 (52% shipped) | 58,900 (39% shipped) |

Training speed: 132 steps per second, about 25 minutes.

## What it taught

- Random draws from a plan no longer wreck the factory: sampled started at 56,600, against -50,100 with one choice per machine.
- Fixed still never left keep: keep bias 5 was too strong (confirmed in [experiment 5](05-keep-bias-sweep.md)).
- Training was too slow to try many settings, which led to [experiment 4](04-speed-up.md).

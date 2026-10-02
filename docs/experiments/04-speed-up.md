# 4. Training speed-up

Run `1002_162844-train`, 200k steps, 2026-10-02. Same settings as [experiment 3](03-plan-action.md).

## Where the time went

Training ran at 132 steps per second, the same as the simulator alone on one core (7 ms per decision): updating the model took almost no time. The 4 environments ran one after another in one process, while PyTorch held 16 threads that mostly waited.

## Changes

- Simulator about 3 times faster (5.6 to 1.9 ms per decision), with identical results checked second by second on 5 seeds:
  - the env only recounts machines per recipe while a plan is not yet reached;
  - batch starts first rule out, in one step, machines short of inputs.
- Environments run in parallel, one process each (`--envs`, default 20).
- 4096 decisions per update across all environments (`--rollout`), the same as before.
- PyTorch limited to 1 thread (`--torch-threads`).

## Results

| Environments | Steps per second |
|---|---|
| 4, one process (before) | 132 |
| 12 processes | 948 |
| 16 | 1,174 |
| 20 (default) | 1,402 |
| 24 | 1,458 |
| 32 | 1,454 |

1 and 4 PyTorch threads were equally fast. 200k steps took 3.3 minutes instead of about 25. The learning curve matched experiment 3 (sampled: 73,350 at the end, against 74,450).

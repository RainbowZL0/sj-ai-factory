# Training

## Settings

MaskablePPO from sb3-contrib (PPO is a standard RL training method) with the default small network, learning rate 3e-4 and minibatches of 256. All of these are command-line options of `train`:

| Option | Default | Meaning |
|---|---|---|
| `--steps` | 1,000,000 | decisions to train on (about 8 minutes on the lab factory, 13 on the larger one) |
| `--ticks` | 60 | seconds per decision |
| `--gamma` | 0.97 | how far ahead rewards count: about 33 decisions, or 2000 s, the scale on which orders pay out |
| `--envs` | 20 | environments simulated at once, one process each |
| `--rollout` | 4096 | decisions collected across all environments per update |
| `--torch-threads` | 1 | PyTorch threads; the model is small, so more threads only wait on each other |
| `--move-cost` | 50 | taken off the reward for each machine moved in the plan; profit is not affected. Cut switches by 4 times on varied orders at no cost to profit ([experiment 8](../experiments/08-varied-orders.md)) |
| `--keep-bias` | 0 | preference a fresh model gets for the starting plan; 0 learned fastest ([experiment 5](../experiments/05-keep-bias-sweep.md)) |
| `--tests`, `--test-seed`, `--test-every` | 3, 1000, steps/20 | test episodes per check, first test seed, steps between checks |

Rewards are also divided by a running estimate of their spread (`VecNormalize`, rewards only), so the reward predictions stay in a steady range. Observations are untouched, so a saved model needs no extra files.

## Speed

Training time is almost all simulation. 20 processes give about 1,100 to 1,400 decisions per second on a 16-core machine; more than about 24 gives nothing more. Measurements: [experiment 4](../experiments/04-speed-up.md).

## Watching and testing

`training.TrainingMonitor` is a Stable-Baselines3 callback. Every `--test-every` steps it plays the current model on the fixed test seeds, twice per seed:
- "fixed": the model's most likely choice;
- "sampled": choices drawn at random from the model's probabilities, as in training. The draws are seeded, so tests repeat.

A large gap between the two means the model relies on chance.

Before training, the keep and random policies play the same seeds; their scores are the lines the model has to beat. Each check:
- appends to `eval.csv`;
- saves `best_model.zip` when the mean profit of either mode improves (the final report plays it in that mode);
- rebuilds `training.html` from the files on disk. The page holds no state of its own, so `view` can rebuild it at any time.

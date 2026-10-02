# Design

| Page | What it covers | Code |
|---|---|---|
| [overview.md](overview.md) | The question the project answers, the modules, how data flows | all of `sjfactory/` |
| [simulation.md](simulation.md) | The rules of one simulated second, the three scenarios, what is not modelled yet | `spec.py`, `sim.py`, `scenarios/` |
| [rl-interface.md](rl-interface.md) | What the model decides (moves in a plan), how a plan is carried out, what it sees, its reward | `env.py`, `policies.py` |
| [training.md](training.md) | Training settings and their defaults, speed, how training is watched and tested | `__main__.py`, `training.py`, `evaluate.py`, `web.py` |

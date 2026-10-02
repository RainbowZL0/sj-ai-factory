# Docs

Start here. Each folder has its own index (`README.md`) listing its pages.

| Area | What it answers |
|---|---|
| [design/](design/README.md) | How the factory is simulated, what the model sees and decides, and how it is trained |
| [experiments/](experiments/README.md) | What was tried in training, the results, the lessons, and what to try next |

How to use and add to these docs:
- Commands and result pages are in the [project README](../README.md).
- A page covers one topic. When adding a page, add a line for it to its folder's index.
- When the rules in `FactorySim.step` or the RL interface in `env.py` change, update the matching page in `design/`.
- Every training experiment gets a page in `experiments/` and a row in its index.

# Project notes

## Rules

- Commit messages and PR descriptions must not contain "Co-Authored-By: Claude" or any other AI attribution line.
- Never commit generated files (`runs/`, charts, Excel, models); `.gitignore` covers them. The one exception is the README pictures in `docs/images/`; redraw them with `scripts/readme_images.py` after a better run.
- English for everything in the repo: code comments, docstrings, error messages, CLI output, docs, YAML comments and commit messages.
- Docs are a tree of indexes starting at `docs/README.md`; every folder's `README.md` lists its pages. When adding a page, add it to its folder's index.
- Keep `docs/design/` in sync when the rules in `FactorySim.step` or the RL interface in `env.py` change.
- Record each training experiment as a page in `docs/experiments/` plus a row in its index; update "Where things stand" and "Next steps" there.
- A change meant only to make the simulator faster must give identical results. Check it second by second against the old code on several seeds, with random plans, and check that keep still makes 52,050 on seed 0.

## Where to look

- All docs: `docs/README.md` (design, experiments).
- Current results and next steps: `docs/experiments/README.md`.
- Commands and result pages: `README.md`. VS Code run configurations: `.vscode/launch.json`.
- Test: `uv run pytest`. Train: `uv run python -m sjfactory --note "what changed" train` (1M steps, about 13 minutes, 20 processes).

## Facts worth knowing

- Code is `sjfactory/`. The old prototype (`pycode/`, `spec_yaml/`) only exists in git history. On 2026-10-02 the history was rewritten with git filter-repo to strip charts and Excel files; commit IDs from before that date no longer exist.
- Ore stock is 0, so casters never run; their recipes are left out of the action. Keep never runs PlateAssemble or FrameFinal, so it fills no Frame orders.
- Models saved before a change to the observation or the action can't be loaded by `eval` afterwards.
- As of 2026-10-02 the trained model makes about 120k test profit against keep's 58.9k. Next steps are listed in `docs/experiments/README.md`.

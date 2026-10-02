# Project notes

- Code is `sjfactory/`. The old version (`pycode/`, `spec_yaml/`) was deleted; it only exists in git history.
- On 2026-10-02 the history was rewritten with git filter-repo to strip charts and Excel files (70 MB to 104 KB), with both owners' agreement. Commit IDs from before that date no longer exist.
- Commit messages and PR descriptions must not contain "Co-Authored-By: Claude" or any other AI attribution line.
- Never commit generated files (charts, Excel, models); `.gitignore` covers them.
- Design and simulation rules: `docs/architecture.md`. Keep it in sync when the rules in `FactorySim.step` change.
- Default language is English for everything in the repo: code comments, docstrings, error messages, CLI output, docs, YAML comments and commit messages.
- Test: `uv run pytest`. Quick run: `uv run python -m sjfactory run --policy keep`.
- Outputs go to `runs/`.
- Before deletion, the new simulator was checked to match the old `pycode` greedy run exactly (stock, cash, machine activity, energy over 5000 s, same fixed orders).
- Known scenario facts: ore stock is 0, so casters never run; no machine starts on PlateAssemble/FrameFinal, so Frame orders go unfilled under the keep policy.

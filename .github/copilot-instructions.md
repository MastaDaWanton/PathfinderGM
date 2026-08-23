# Copilot instructions for Pathfinder GM

## Project shape

This is a Django app for running a Pathfinder 1e campaign inside a World Bible-generated world.

Primary references:
- [README.md](../README.md)
- [CLAUDE.md](../CLAUDE.md)
- [docs/architecture.md](../docs/architecture.md)
- [docs/intent-protocol.md](../docs/intent-protocol.md)
- [docs/campaign-format.md](../docs/campaign-format.md)
- [docs/from-world-bible.md](../docs/from-world-bible.md)

## Guardrails

- The GM agent should propose structured intent; the rules engine owns state, dice, and resolution.
- World Bible export files are read-only input; play changes belong in the campaign overlay.
- Preserve the single-PC, 1e rules-first model.
- Keep packaged desktop behavior in mind; code that only works under `runserver` is not complete.
- Favor a targeted fix with tests that capture the actual failure mode.

## Validation

- Run the full suite before finalizing: `python -m pytest`
- For UI path verification, use the real app and the real generated content where practical.

# AGENTS.md

This repo is a Pathfinder 1e GM app that reads a World Bible export and overlays a campaign save. The authoritative project guidance lives in the docs below; keep the implementation aligned with them instead of inventing a separate pattern.

- [README.md](README.md)
- [CLAUDE.md](CLAUDE.md)
- [docs/architecture.md](docs/architecture.md)
- [docs/intent-protocol.md](docs/intent-protocol.md)
- [docs/campaign-format.md](docs/campaign-format.md)
- [docs/from-world-bible.md](docs/from-world-bible.md)

## Working expectations

- Treat the rules engine as the source of truth; the GM agent proposes structured intent and the engine resolves outcomes.
- Keep the World Bible export read-only; store play-state mutations in the campaign overlay.
- Default to local models and Ollama. Hosted providers are optional and must not be required for the app to work.
- Match the existing 1e semantics and avoid ad hoc "chat-like" resolution that bypasses the rules engine.

## Verification

- Run the full project test suite before claiming a fix: `python -m pytest`
- For a local app run: `python manage.py runserver 8000`
- Prefer real app validation for GM flow changes; synthetic fixtures are useful but not enough on their own.

## Critical repo constraints

- Do not assume packaged-app paths are relative to `__file__`; use the executable's actual install location.
- Keep user-data caches versioned and scoped to the user data directory rather than the install directory.
- Do not duplicate the architecture or protocol documentation here; use the linked docs as the source of truth.

"""A catalogue with no homebrew beside it is the same catalogue every time it is built.

Measured 2026-09-25: rebuilding the bestiary took 325 ms (16 MB of JSON) and the spells
526 ms, and the test suite rebuilt them each time a test moved CAMPAIGN_DIR — 82
bestiary rebuilds in an 11-file sample of 271 tests, 57% of that sample's run — though
almost none of those tests had a homebrew file at all, so every rebuild produced exactly
the catalogue before it. The same holds in the app: a player with no homebrew never needs
a second build.

So a loader asks `memo(name, folders, build)`: when none of its homebrew folders holds a
file, the catalogue built from the shipped content alone is kept for the life of the
process and handed back; when any does, it builds as before, every time its caller asks.
The fingerprint is a directory listing, 0.58 ms for seven absent folders.

Deliberately NOT keyed on the homebrew files' mtimes to cache the homebrew case too:
two same-size writes inside one clock tick share an mtime (git's "racy git"; measured in
this project's race cache the same day), and the app's own writes already clear the
caches they touch. Only the no-homebrew case is memoised, because only there is the
answer certain.

`_MEMO` is annotated without `None` on purpose: tests/conftest.py clears every
module-level `_NAME: ... | None` cache when a test moves CAMPAIGN_DIR, and this one is
the thing that makes that clear cheap. `tests/conftest.py` rebuilds each memoised
catalogue at the end of a run and fails if a test mutated the shared copy.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

_MEMO: dict[str, object] = {}
_BUILDERS: dict[str, Callable[[], object]] = {}


def has_homebrew(*folders) -> bool:
    """Whether any of these folders holds a .json file."""
    for folder in folders:
        p = Path(folder)
        if p.is_dir() and next(p.glob("*.json"), None) is not None:
            return True
    return False


def memo(name: str, folders, build: Callable[[], object]):
    """`build()`, kept for the process when `folders` hold no homebrew."""
    if has_homebrew(*folders):
        return build()
    if name not in _MEMO:
        _MEMO[name] = build()
        _BUILDERS[name] = build
    return _MEMO[name]

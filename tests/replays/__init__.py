"""Replay corpora extracted from real playtests, and the loader the tests read them with.

Each corpus is a folder `tests/replays/<player>-<date>/` of three JSON files, extracted
read-only from a save and its backups:

  * `turns.json` — one record per player line: the text, the GM beats that followed it
    (with their `said` records and any spliced `added` lines), and the turn log for that
    turn: the plan's intents, outcomes, rejections and reading; the prose call's repairs;
    the mention and speech-tag counts (`hails_tagged`, `hails_guessed`).
  * `saves.json` — the scene's people (ref, name, place, zone, square, face, pronouns) and
    the PC's prepared spells and spellbook, at the save and at each backup.
  * `cases.json` — the named defects, each pointing at the turn that carries its evidence.

Distinct from `tests/replay/`, which holds `narrator_audit.py --record` sessions against
the fixture worlds with every raw model reply. These hold what a player saw, not what the
model wrote, so they replay a beat's text and outcomes, not a plan.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent

BOBBY = "bobby-2026-09-28"


def available(corpus: str = BOBBY) -> bool:
    """Whether the corpus is on this disk. The player's own corpora are kept out of the
    repository (it is public, and they are extracts of a person's saves — owner's ruling,
    2026-09-28), so a fresh clone or a worktree has only this loader, and every test that
    reads a corpus skips rather than fails."""
    return all((HERE / corpus / name).is_file()
               for name in ("turns.json", "saves.json", "cases.json"))


@lru_cache(maxsize=None)
def _read(corpus: str, name: str) -> dict:
    return json.loads((HERE / corpus / name).read_text(encoding="utf-8"))


def turns(corpus: str = BOBBY) -> list[dict]:
    return _read(corpus, "turns.json")["turns"]


def opening(corpus: str = BOBBY) -> dict:
    return _read(corpus, "turns.json")["opening"]


def turn(n: int, corpus: str = BOBBY) -> dict:
    """The player's n-th line (1-based) and everything the turn wrote."""
    found = [t for t in turns(corpus) if t["n"] == n]
    if not found:
        raise KeyError(f"{corpus} has no turn {n}")
    return found[0]


def saves(corpus: str = BOBBY) -> list[dict]:
    """The save first, then its backups, newest first (`.1` is the one before)."""
    return _read(corpus, "saves.json")["saves"]


def save(file: str, corpus: str = BOBBY) -> dict:
    return next(s for s in saves(corpus) if s["file"] == file)


def cases(corpus: str = BOBBY) -> list[dict]:
    return _read(corpus, "cases.json")["cases"]


def case(case_id: str, corpus: str = BOBBY) -> dict:
    """A named case, with its turn record attached as `record`."""
    found = next((c for c in cases(corpus) if c["id"] == case_id), None)
    if found is None:
        raise KeyError(f"{corpus} has no case {case_id!r}")
    return dict(found, record=turn(found["turn"], corpus))


def beat_text(record: dict) -> str:
    """Everything the page showed for a turn, in order."""
    return "\n\n".join(b.get("text", "") for b in record["beats"])


def said(record: dict) -> list[dict]:
    return [s for b in record["beats"] for s in (b.get("said") or [])]


def outcomes(record: dict) -> list[dict]:
    """The engine's outcomes for the turn: the plan's, or the direct cast's."""
    if record.get("plan"):
        return record["plan"]["outcomes"]
    if record.get("resolution"):
        return record["resolution"]["outcomes"]
    return []

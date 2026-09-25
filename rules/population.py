"""Everybody the campaign has seen, kept where they were seen.

The user's ruling of 2026-09-25: "I dont care if a database grows of random people as long
as we can search the data base quickly and precisely"; the woman watching from a doorway
"should stay there until i leave or something moves them in prose. and once I leave that
woman remains a resident of the city/town/village unless she is a merchant or traveller".
Design record: docs/the-population.md.

A person here is a RECORD, not a character sheet: a sheet is 1.4 KB bare and several KB
with gear (measured), too heavy for a town's worth of passers-by. The record carries the
phrase the prose first used (what the player will paraphrase), where and when, and a life
rolled by `rules.lives` — work, face, temperament, wants, goal, hobby, quirk. A person
becomes an `Actor` in `Scene.people` only when they enter play (the existing promotion,
and later the player engaging them), and the record keeps the ref.

Tiers, after RimWorld's "who is kept" and Dwarf Fortress's "anybody named you meet":
  glimpse       the prose described them; nothing more has happened
  acquaintance  the player spoke to them, or they were named, or acted in a scene
  figure        tied to a quest, a debt, a fight or a relative of a figure
Only the first exists before the engagement work of phase 2's later steps.

Nothing here writes a number the narrator hears, and nothing here is a second store of a
fact the engine holds elsewhere: a person with an `Actor` is that actor for everything
mechanical; the record holds only what no sheet has — the phrase, the place first seen,
the life, and when the player last met them.
"""
from __future__ import annotations

import re

from . import lives


def _norm(phrase: str) -> str:
    return " ".join(re.findall(r"[a-z']+", str(phrase or "").lower()))


def _next_id(scene) -> str:
    taken = [int(k[1:]) for k in (getattr(scene, "population", {}) or {})
             if re.fullmatch(r"p\d+", k)]
    return f"p{max(taken, default=0) + 1}"


def at_spot(scene, phrase: str, spot: str | None = None) -> dict | None:
    """The person already recorded under this phrase at this place, if any."""
    want = _norm(phrase)
    where = spot if spot is not None else getattr(scene, "at", None)
    for rec in (getattr(scene, "population", {}) or {}).values():
        if rec.get("spot") == where and _norm(rec.get("phrase", "")) == want:
            return rec
    return None


def used_frames(scene, home) -> set[str]:
    """The quirk frames people of this settlement already carry, so the next is new."""
    return {rec["life"]["quirk_frame"]
            for rec in (getattr(scene, "population", {}) or {}).values()
            if rec.get("home") == home and rec.get("life")}


def note(scene, phrase: str, *, turn: int = 0, body: str = "") -> dict:
    """Record the person this phrase describes, where the party stands; return the record.

    The same phrase at the same place is the same person seen again — their `last_seen`
    moves and nothing is rolled twice. A new one is rolled once, seeded by their id, and
    never re-rolled: the roll is stored, not the seed.
    """
    if not hasattr(scene, "population") or scene.population is None:
        scene.population = {}
    clock = int(getattr(scene, "clock_minutes", 0) or 0)
    have = at_spot(scene, phrase)
    if have is not None:
        have["last_seen"] = clock
        return have
    pid = _next_id(scene)
    home = getattr(scene, "location_id", None)
    life = lives.roll(f"{home}|{pid}", phrase=phrase, body=body,
                      used_frames=used_frames(scene, home))
    rec = {
        "id": pid, "phrase": " ".join(str(phrase).split()), "home": home,
        "spot": getattr(scene, "at", None), "first_seen": clock, "last_seen": clock,
        "last_met": None, "turn": int(turn), "ref": "", "tier": "glimpse",
        "life": life.as_dict(),
    }
    scene.population[pid] = rec
    return rec


def of_ref(scene, ref: str) -> dict | None:
    """The record behind an actor, if the actor came from one."""
    for rec in (getattr(scene, "population", {}) or {}).values():
        if rec.get("ref") == ref:
            return rec
    return None

"""Shared set-up for Lane A's tests (tests/test_a_*.py): the Bobby corpus's scene rebuilt
on the Aurvantis fixture, and a narrator-check context over a recorded beat.

Not a test module (no `test_` prefix). The corpus is the owner's own playtest and is kept
out of the repository; every test that reads it skips when `replays.available()` says it
is not on this disk.
"""
from __future__ import annotations

from dataclasses import replace

import replays
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Outcome, Scene
from rules.sheet import load_pc
from world.loader import load_cached

WORLD = load_cached("fixtures/aurvantis-campaign.json")
VORMOOR = WORLD.by_name("Vormoor", kind="CITY")

WAY_IN = f"{VORMOOR.id}~urban:the-way-in"
MARKET = f"{VORMOOR.id}~urban:the-market"
APPROACH = f"{VORMOOR.id}~forest:the-approach"


def outcome(d: dict) -> Outcome:
    """A recorded outcome dict as the engine's `Outcome`."""
    keep = {k: d.get(k) for k in ("intent_id", "op", "status", "effects", "tell",
                                  "because", "rolls") if k in d}
    keep["effects"] = list(keep.get("effects") or [])
    keep["rolls"] = []
    out = Outcome(**{k: v for k, v in keep.items() if v is not None})
    # The recorded rolls stay dicts: the checks read their labels only.
    out.rolls = list(d.get("rolls") or [])
    return out


def scene_at(place: str, people=(), *, world=WORLD, location=None):
    """(agent, engine) with Bobby — a wizard, he/him — standing at `place`, and the
    named people from the Bobby save standing with him. `people` is a list of the save's
    person dicts (`replays.save(...)["people"]`) or (name, template) pairs."""
    from gm.agent import GMAgent

    location = location or VORMOOR
    s = Scene(location_id=location.id)
    pc = load_pc("fixtures/pc-kesst.json")
    pc.name, pc.pronouns = "Bobby", "he/him"
    s.add(pc)
    e = Engine(s, Dice(seed=3), world=world)
    e.place_party(place)
    refs = {}
    for p in people:
        if isinstance(p, dict):
            name, template = p["name"], p.get("from_template") or "guildhand"
        else:
            name, template = p
        a = instantiate(template if _known(template) else "guildhand", scene=s, name=name)
        s.add(a)
        if isinstance(p, dict):
            a.pronouns = p.get("pronouns") or a.pronouns
            a.appearance = p.get("appearance") or ""
            a.described = bool(p.get("described"))
            a.true_name = p.get("true_name") or ""
            refs[p["ref"]] = a.ref
    return GMAgent(world, e), refs


def _known(template: str) -> bool:
    from rules import bestiary

    return bestiary.lookup(str(template or "").strip().lower()) is not None


def people_named(*names, save="bobby.json"):
    """The save's people by name, in the order asked."""
    rows = {p["name"]: p for p in replays.save(save)["people"]}
    return [rows[n] for n in names]


def context(agent, text: str, *, door="turn", outcomes=(), player="", reading=None,
            was_at=None, said=()):
    """A narrator-check context over one recorded beat, as `_groom` builds it."""
    agent.reading = reading
    ctx = agent._beat_context(door, player_input=player, brief="",
                              outcomes=[outcome(o) if isinstance(o, dict) else o
                                        for o in outcomes])
    return replace(ctx, text=text, said=tuple(said),
                   was_at=was_at if was_at is not None else ctx.was_at)

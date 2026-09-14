"""Natural attacks, and the two gates that made every one of them undeclarable.

Measured 2026-09-14, chasing why fifteen attack evolutions carried a `not_yet`. The
answer was worse than the fifteen: **not one natural attack could be declared at all.**

  rules.weapons.has("bite")   False        and the same for claws, gore, slam,
  rules.weapons.has("claws")  False        pincers, sting, tail slap, tentacle
                                           and wing buffet

`intents._known_weapon` asked only that table, so a bite was refused at validation with
"no such weapon 'bite'. Did you mean 'bardiche'?" before the engine was ever asked. Past
that, `Engine._check_legality` asked the same table again. `Actor.weapon` has resolved
naturals off the race document the whole time; nothing could reach it.

So a race could take Bite for 1 RP, the forge would price it, the sheet would show it,
and the player could never bite anything. That is the whole attack group of the evolution
pool — twenty-six entries — not the fifteen that admit to a problem.
"""
from __future__ import annotations

import copy

import pytest
from unittest import mock

from rules import races
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

BITE = {"key": "bite", "name": "bite", "type": "piercing", "count": 1,
        "damage": {"tiny": "1d3", "small": "1d4", "medium": "1d6", "large": "1d8"}}


def _body(monkeypatch, *tags):
    """A PC whose own race grants a bite and the riders named."""
    pc = load_pc("fixtures/pc-kesst.json")
    real = races.all_races()
    doc = copy.deepcopy(real[pc.race])
    doc.setdefault("weapons", []).append(dict(BITE))
    doc.setdefault("tags", []).extend(["natural.bite", *tags])
    monkeypatch.setattr(races, "all_races", lambda: {**real, pc.race: doc})

    s = Scene(location_id="t")
    s.add(pc)
    foe = instantiate("guildhand", scene=s, name="the thug")
    foe.hp = foe.hp_base = 40          # survives long enough to be bitten repeatedly
    s.add(foe)
    e = Engine(s, Dice(seed=4), world=None)
    pc.apply_effect(ActiveEffect(name="body", kind="racial", key="race:body",
                                 source="race:test", origin="race:test",
                                 duration="until-dismissed",
                                 tags=("natural.bite", *tags)))
    return s, e, pc, foe


def _run(e, op, params, actor="pc", target=None):
    raw = {"op": op, "actor": actor, "because": "t", "params": params}
    if target:
        raw["target"] = target
    return e.run(e.validate([raw], origin="author:test"))


def _best(notation: str) -> int:
    """The highest total the named die can produce."""
    count, _, faces = str(notation).partition("d")
    faces, _, _ = faces.partition("+")
    return int(count or 1) * int(faces or 20)


def _bite_until_it_lands(e, s, foe, tries=25):
    """Swing, answering the PC's own to-hit and damage, until one connects.

    The suspension is read off the *result*, not the scene: the PC rolls their own
    to-hit and their own damage, so one attack suspends twice and `run` hands the
    pending roll back on the outcome.
    """
    _run(e, "begin_encounter", {"sides": {"us": ["pc"], "them": [foe.ref]}})
    for _ in range(tries):
        res = _run(e, "attack", {"weapon": "bite"}, target=foe.ref)
        for _ in range(6):
            if res.awaiting is None:
                break
            # Each prompt names its own die, and the engine refuses a total that die
            # cannot make: answering 20 to a 2d6 damage roll raises BadDice. Take the
            # best legal result for whatever is being asked, so the swing connects.
            res = e.resume(face=_best(res.awaiting.get("die", "1d20")))
        if any(x.get("kind") == "damage" for o in res.outcomes for x in (o.effects or [])):
            return res
    return None


def test_a_bite_can_be_declared_at_all(monkeypatch):
    """The gate that refused it: validation asked a 456-weapon table that holds no
    natural attacks, and suggested a bardiche."""
    from rules.intents import _known_weapon

    assert _known_weapon("bite"), "a bite cannot even be named"
    assert _known_weapon("claws") and _known_weapon("gore")
    assert not _known_weapon("nonsense-stick"), "the gate stopped refusing anything"


def test_the_names_come_from_the_pool_and_not_a_list(monkeypatch):
    """A list in `intents.py` would go stale in the direction that hides the bug: a new
    evolution's weapon would be refused and nobody would look there for why."""
    aliases = races.natural_weapon_aliases()
    for ev in races.evolutions().values():
        for w in ev.get("weapons") or []:
            assert str(w["key"]).lower() in aliases, f"{w['key']} is not accepted"


def test_the_engine_still_refuses_a_bite_to_somebody_with_no_jaws():
    """Let through by validation and refused here, the way the blood armament is —
    because "you have no bite" is the sentence, not "did you mean bardiche"."""
    from rules.intents import IntentError

    s = Scene(location_id="t")
    s.add(load_pc("fixtures/pc-kesst.json"))
    foe = instantiate("guildhand", scene=s, name="the thug")
    s.add(foe)
    e = Engine(s, Dice(seed=1), world=None)
    with pytest.raises(IntentError) as caught:
        e.validate([{"op": "attack", "actor": "pc", "target": foe.ref, "because": "t",
                     "params": {"weapon": "bite"}}], origin="author:test")
    assert "has no weapon" in str(caught.value)


def test_a_bite_lands_and_does_damage(monkeypatch):
    s, e, pc, foe = _body(monkeypatch)
    before = foe.hp
    res = _bite_until_it_lands(e, s, foe)
    assert res is not None, "twenty-five bites and none of them landed"
    assert foe.hp < before, "the bite landed and took nothing off"


def test_the_trip_rider_puts_them_down(monkeypatch):
    """`natural.trip` — one of the fifteen that carried a `not_yet`. The rider is a
    save the defender may make, so this asserts the fork happened, not that it failed."""
    s, e, pc, foe = _body(monkeypatch, "natural.trip")
    res = _bite_until_it_lands(e, s, foe)
    assert res is not None
    kinds = [x.get("kind") for o in res.outcomes for x in (o.effects or [])]
    assert "condition" in kinds or "rider_resisted" in kinds, (
        f"the bite landed and the trip never fired: {kinds}")


def test_no_rider_fires_without_the_tag(monkeypatch):
    """The other half: a plain bite trips nobody."""
    s, e, pc, foe = _body(monkeypatch)
    res = _bite_until_it_lands(e, s, foe)
    assert res is not None
    kinds = [x.get("kind") for o in res.outcomes for x in (o.effects or [])]
    assert "rider_resisted" not in kinds
    assert not foe.has_state("state.position.prone")


def test_a_rider_never_fires_on_a_corpse(monkeypatch):
    """`grappled` on the dead is the shape that once made 759 undead unkillable."""
    s, e, pc, foe = _body(monkeypatch, "natural.grab")
    foe.hp = 0
    assert e._natural_riders(pc, foe, "bite") == []

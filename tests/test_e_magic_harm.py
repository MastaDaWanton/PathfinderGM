"""Lane E: harm opens the fight and moves attitude — when the source is perceived.

Measured 2026-09-28 (docs/playtest-2026-09-28.md item 22): Bobby's Burning Hands went
through the man in a stained leather jerkin and nothing followed. `_op_cast` never called
`_ensure_encounter`, so harmful magic was the one violence that never started a fight
(22.2); and no rule anywhere turned harm into feeling, for a spell or a sword (22.3).

The owner's rulings: a first harmful cast defers through the battle gate like a first
swing (Q31); a companion caught loses 10 regard (Q35); the grudge does not fade (Q36);
the sword door obeys the same rule (Q37); and harm counts only when the victim perceives
who did it — "if i shoot a blowdart from concealment or [pass] a stealth check then nobody
saw that I did it so no one dislikes me for it or tries to fight me" (Q34).
"""
from __future__ import annotations

import pytest

from rules import attitude, casting, grid as gridmod, states
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc, to_dict
from tests._places import stand_on


def caster():
    d = to_dict(load_pc("fixtures/pc-caster.json"))
    d["abilities"]["int"] = 18
    d["prepared"] = {"burning-hands": 2}
    return from_dict(d, ref="pc")


def board(fight=False, seed=4):
    s = Scene(location_id="5bbd0c40345f")
    s.add(caster())
    man = s.add(instantiate("guildhand", scene=s, name="the man in a stained jerkin"))
    stand_on(s, "forest")
    s.grid = gridmod.Grid(20, 20)
    s.positions["pc"], s.positions[man.ref] = (4, 7), (1, 8)
    if fight:
        s.initiative = [("pc", 20), (man.ref, 10)]
        s.sides = {"pc": ["pc"], "them": [man.ref]}
        s.round, s.turn = 1, 0
    return s, Engine(s, Dice(seed=seed)), man.ref


def burn(engine, ref):
    return engine.run(engine.validate([{"op": "cast", "actor": "pc", "because": "t",
                                        "params": {"spell": "burning-hands",
                                                   "aim": f"ref:{ref}"}}])).outcomes


def hide(actor, how="invisible"):
    """Hidden through the one applicator, as a condition — invisibility, or a scheme's
    `state.hidden` grant (the Stealth case)."""
    if how == "invisible":
        actor.add_condition("invisible", None, source="test")
    else:
        from rules.activeeffect import ActiveEffect

        actor.apply_effect(ActiveEffect(name="hidden", kind="condition", key="hidden",
                                        source="test", duration="until-dismissed",
                                        tags=("state.hidden",)))


# --- the battle gate (22.2) ---------------------------------------------------------------------

def test_e_first_harmful_cast_opens_the_fight_and_defers():
    """The shipped law — first violence opens the fight and never resolves it — now for a
    spell too (owner, Q31: the gate, not a surprise round). The encounter forms with the
    man on the other side, nothing is spent or rolled, and the caster holds the turn to
    cast it as declared, the aim riding in the params."""
    s, e, man = board()
    pc = s.actors["pc"]
    slots, hp = casting.slots_left(pc, 1), s.actors[man].hp
    outs = burn(e, man)
    joined = [x for o in outs for x in o.effects if x.get("kind") == "battle_joined"]
    assert joined == [{"ref": "pc", "kind": "battle_joined", "op": "cast", "target": man,
                       "params": {"spell": "burning-hands", "aim": f"ref:{man}"}}]
    assert s.in_encounter and man in s.sides["them"]
    assert casting.slots_left(pc, 1) == slots and casting.prepared_count(pc, "burning-hands") == 2
    assert s.actors[man].hp == hp
    assert s.current_ref() == "pc"
    assert "Nothing has been cast yet" in outs[0].tell


def test_e_a_harmless_cast_opens_nothing():
    """Invisibility's line: an attack is a spell whose area includes a foe AND harms — a
    spell that harms nobody (mage armor on yourself) is not violence."""
    s, e, man = board()
    s.actors["pc"].prepared = {"mage-armor": 1}
    e.run(e.validate([{"op": "cast", "actor": "pc", "because": "t",
                       "params": {"spell": "mage-armor", "at": "pc"}}]))
    assert not s.in_encounter


# --- attitude, as an ActiveEffect (22.3) --------------------------------------------------------

def test_e_harm_makes_a_stranger_hostile_as_an_effect():
    """The man was harmed and moved not at all. Now: hostile, through the one applicator
    (`Engine._set_attitude`), an ActiveEffect whose source names the spell; regard drops
    with it and does not recover on a clock — only talk mends it (owner, Q36)."""
    s, e, man = board(fight=True)
    victim = s.actors[man]
    outs = burn(e, man)
    moved = [x for o in outs for x in o.effects if x.get("kind") == "attitude"]
    assert moved == [{"kind": "attitude", "ref": man, "from": "indifferent",
                      "to": "hostile", "why": "harmed", "source": "spell:burning-hands"}]
    assert attitude.of(victim) == attitude.HOSTILE
    held = [x for x in victim.effects if "attitude.hostile" in (x.tags or ())]
    assert held and held[0].source == "spell:burning-hands"
    assert held[0].duration == "until-dismissed"
    assert "wants you gone" in outs[0].tell
    victim.remove_effects(source="spell:burning-hands")
    assert attitude.of(victim) == attitude.HOSTILE, \
        "the grudge lives in regard too, and nothing but talk raises it"


def test_e_a_companion_caught_loses_regard_and_keeps_their_step():
    """Owner, Q35: somebody travelling with you who is caught loses 10 regard (RimWorld's
    "Harmed me" at the weight of its "Insulted", the mapping provocation.py made), and is
    not made hostile."""
    s, e, man = board(fight=True)
    friend = s.actors[man]
    from rules.activeeffect import ActiveEffect

    friend.apply_effect(ActiveEffect(name="company", kind="bond", key="company",
                                     source="company", duration="until-dismissed",
                                     tags=(states.TRAVELS_WITH_YOU,)))
    attitude.set_regard(friend, 60, "test")
    s.sides = {"pc": ["pc", man], "them": []}
    outs = burn(e, man)
    rec = [x for o in outs for x in o.effects if x.get("kind") == "attitude"]
    assert rec and rec[0]["regard"] == [60, 50]
    assert attitude.regard_of(friend) == 60 - attitude.HARMED
    assert attitude.of(friend) != attitude.HOSTILE


def test_e_already_hostile_loses_nothing_more():
    s, e, man = board(fight=True)
    e._set_attitude(s.actors[man], attitude.HOSTILE, None, "earlier")
    outs = burn(e, man)
    assert not [x for o in outs for x in o.effects if x.get("kind") == "attitude"]


# --- only when the source is perceived (Q34) ----------------------------------------------------

def test_e_a_hidden_casters_harm_changes_no_attitude_and_opens_no_fight():
    """The owner's blowdart, for a spell: an invisible caster fifteen feet off is not
    identified (Invisibility, ID=431, pinpoints only a creature that STRUCK the victim;
    Stealth's sniping rule needs 10 ft or more). The man knows he was hurt, not by whom:
    no fight opens, no attitude moves, and the crowd's heat is not the player's."""
    from gm import judgement

    s, e, man = board()
    hide(s.actors["pc"])
    outs = burn(e, man)
    assert not s.in_encounter
    assert not [x for o in outs for x in o.effects if x.get("kind") == "battle_joined"]
    assert not [x for o in outs for x in o.effects if x.get("kind") == "attitude"]
    unseen = [x for o in outs for x in o.effects if x.get("kind") == "harm_unseen"]
    assert unseen and unseen[0]["ref"] == man
    assert attitude.of(s.actors[man]) == attitude.DEFAULT
    assert "cannot tell who did it" in outs[0].tell
    s.heat = {}
    judgement.note_heat(s, outs, "")
    assert s.heat.get("kind") != "violence"


def test_e_a_seen_casters_harm_does():
    """The same cast, the caster in plain sight: the fight opens (and defers)."""
    s, e, man = board()
    outs = burn(e, man)
    assert s.in_encounter
    assert [x for o in outs for x in o.effects if x.get("kind") == "battle_joined"]


def test_e_the_sniping_rule_as_sourced():
    """`attitude.perceived`, the one reader: not hidden → seen; hidden but within 5 ft (a
    blow in reach — Stealth ends on an attack roll, and the struck know where an invisible
    attacker is) → seen; invisible at 10 ft or more → unseen; hidden by Stealth at 10 ft
    or more → Stealth at −20 against the victim's Perception, the contest rolled hidden."""
    s, e, man = board()
    pc, victim = s.actors["pc"], s.actors[man]
    assert attitude.perceived(e, pc, victim) is True
    hide(pc)
    assert attitude.perceived(e, pc, victim) is False
    s.positions[man] = (5, 7)
    assert attitude.perceived(e, pc, victim) is True, "a blow in reach is seen"
    pc.remove_condition("invisible")
    hide(pc, "stealth")
    s.positions[man] = (1, 8)
    rolls: list = []
    attitude.perceived(e, pc, victim, rolls=rolls)
    assert len(rolls) == 2 and all(r["visibility"] == "hidden" for r in rolls)
    assert any(m["value"] == -20 for m in rolls[0]["modifiers"]), "the sniping penalty"


def test_e_the_sword_door_obeys_the_same_rule():
    """Owner, Q37: a rapier moved nobody's attitude either. The one `attitude.harmed` call
    in `_op_attack` makes a stranger struck in a fight hostile, source the weapon."""
    s, e, man = board(fight=True)
    s.positions[man] = (5, 7)
    victim = s.actors[man]
    for _ in range(6):
        res = e.run(e.validate([{"op": "attack", "actor": "pc", "target": man,
                                 "because": "t", "visibility": "hidden"}]))
        if any(x.get("kind") == "damage" for o in res.outcomes for x in o.effects):
            break
        s.turn, s.acted = 0, set()
    else:
        pytest.skip("six misses in a row on this seed")
    assert attitude.of(victim) == attitude.HOSTILE
    assert any(x.get("kind") == "attitude" and x.get("source", "").startswith("attack:")
               for o in res.outcomes for x in o.effects)


def test_e_a_hidden_sword_in_reach_is_still_seen():
    """Sniping is a RANGED attack from 10 ft or more; a blow in reach gives the attacker
    away, so an invisible swing at an unaware stranger still opens the fight."""
    s, e, man = board()
    s.positions[man] = (5, 7)
    hide(s.actors["pc"])
    res = e.run(e.validate([{"op": "attack", "actor": "pc", "target": man,
                             "because": "t", "visibility": "hidden"}]))
    assert s.in_encounter
    assert [x for o in res.outcomes for x in o.effects if x.get("kind") == "battle_joined"]


def test_e_a_crowd_sees_a_spell_wound_as_violence():
    """`note_heat` read damage only from `attack` and `damage` ops, so a spell burning a man
    in front of onlookers was no heat at all (item 22.3)."""
    from gm import judgement

    s, e, man = board(fight=True)
    outs = burn(e, man)
    if not any(x.get("kind") == "damage" for o in outs for x in o.effects):
        pytest.skip("saved to nothing on this seed")
    s.heat = {}
    judgement.note_heat(s, outs, "")
    assert s.heat.get("kind") == "violence"

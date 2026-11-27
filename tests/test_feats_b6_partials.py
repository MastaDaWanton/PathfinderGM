"""Feat loop batch 6, lane b6-partials (2026-11-27): the feats that carried a `not_yet`
line, finished where the book defines the rule and the machinery is small. The ledger of
every line, grouped by what each is missing, is docs/feats-partial-ledger.md.

Measured on integrate/feats-b5 3520f6a8 before this lane: 256 `not_yet` lines on 216
feats. Twelve of them named a blocker ("lane b2-actions' charge_ac", "until that lane
merges") that had merged weeks before, so the feat sat PARTIAL with its machinery built.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rules import classbuilder, reactions
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.engine import Engine
from tests.test_feats_b4_moves import _attack, _board, _pc, _run, _tells

MECH = Path("content/feats/mechanics")


@pytest.mark.parametrize("name", sorted(p.name for p in MECH.glob("*.json")))
def test_every_feat_file_still_validates(name):
    doc = json.loads((MECH / name).read_text("utf-8"))
    assert classbuilder.validate_feat_documents(
        {k: v for k, v in doc.items() if not k.startswith("_")}) == []


def _held_by(actor, key, tags, rounds=5):
    actor.apply_effect(ActiveEffect(name=key, kind="buff", key=key, source="test",
                                    origin="author:test", duration="rounds",
                                    rounds_left=rounds, tags=tuple(tags)))


# --- the stale lines: machinery merged, the feat left PARTIAL ------------------------------

def test_improved_snap_shot_threatens_fifteen_feet_with_a_bow():
    """UC: "You threaten an additional 10 feet with Snap Shot." The line said the reader
    was another lane's and unmerged; `reactions.ranged_threat` has read the tag since b2."""
    pc = _pc("fighter", feats=["Snap Shot", "Weapon Focus (longbow)"], equipped="longbow")
    assert reactions.ranged_threat(pc) == 5
    pc.feats.append("Improved Snap Shot")
    assert reactions.ranged_threat(pc) == 15


def test_janni_style_charges_at_only_minus_one_ac():
    """UC, Janni Style: "you take only a -1 penalty to AC for charging." The charge's
    `charge_ac` offset has existed since b2; the style never wrote a term for it."""
    pc = _pc("monk", feats=["Janni Style"])
    assert Engine._stance_terms(pc, "charge")[0]["amount"] == -2
    _held_by(pc, "janni style", ["style.janni-style"])
    assert Engine._stance_terms(pc, "charge")[0]["amount"] == -1


def test_two_weapon_defense_gives_two_when_fighting_defensively():
    """CRB: "When you are fighting defensively ... this shield bonus increases to +2."
    Before: +1 whatever the stance."""
    pc = _pc("fighter", feats=["Two-Weapon Fighting", "Two-Weapon Defense"])
    plain = pc.ac()
    Engine._lay_attack_stances(pc, ("two_weapon",))
    assert pc.ac() == plain + 1
    Engine._lay_attack_stances(pc, ("two_weapon", "fighting_defensively"))
    from rules.sheet import defensive_dodge

    assert pc.ac() == plain + 2 + defensive_dodge(pc)


def test_monkey_lunge_waives_the_lunge_s_ac_only_on_a_standard_action():
    """Monkey Lunge: "As a standard action, you can use the Lunge feat ... without
    suffering a penalty to your AC." Before: the waiver held after a full attack's lunge
    too. A single lunging blow keeps the AC; a full attack's lunge pays the -2."""
    pc = _pc("fighter", feats=["Lunge", "Monkey Lunge"])
    s, e = _board(pc, ("thug", (7, 5)))
    ac = pc.ac()
    _attack(e, lunge=True)
    assert pc.has_state("buff.stance.lunging") and pc.ac() == ac
    pc2 = _pc("fighter", feats=["Lunge", "Monkey Lunge"])
    s2, e2 = _board(pc2, ("thug", (7, 5)))
    ac2 = pc2.ac()
    _attack(e2, lunge=True, full_attack=True)
    assert pc2.has_state("buff.stance.lunging") and pc2.ac() == ac2 - 2


def _cleaver(*feats):
    pc = _pc("fighter", feats=["Power Attack", "Cleave", "Goblin Cleaver", *feats])
    s, e = _board(pc, ("thug", (6, 5)), ("orc", (4, 5)))
    return s, e, pc


def _next_blow(e, s, pc):
    from rules.intents import Intent

    intent = Intent(op="attack", actor="pc", target="c1", params={"cleave": True})
    return e._cleave_next(pc, s.actors["c1"], pc.wielded_key(), intent, True)


def test_orc_hewer_cleaves_on_into_a_foe_its_own_size():
    """ARG: "your additional attacks can be made against creatures your size or smaller"
    and "+2 circumstance ... against humanoids (orc)". Goblin Cleaver alone passes over
    the Medium orc behind the bearer (not beside the first foe); Orc Hewer takes it."""
    s, e, pc = _cleaver()
    nxt, _ = _next_blow(e, s, pc)
    assert nxt is None
    s, e, pc = _cleaver("Orc Hewer")
    nxt, _ = _next_blow(e, s, pc)
    assert nxt and nxt["target"] == "c2"
    orc = s.actors["c2"]
    on = sum(m.value for m in pc.attack_modifiers(defender=orc, choices=("cleave", "cleaving_on")))
    off = sum(m.value for m in pc.attack_modifiers(defender=orc, choices=("cleave",)))
    assert on - off == 2


def test_giant_killer_reaches_one_size_larger():
    """ARG: "one size category larger than you or smaller". The ogre (Large) beside the
    bearer, not beside the first foe: Orc Hewer passes it, Giant Killer takes it."""
    pc = _pc("fighter", feats=["Power Attack", "Cleave", "Goblin Cleaver", "Orc Hewer"])
    s, e = _board(pc, ("thug", (6, 5)), ("ogre", (3, 5)))
    assert _next_blow(e, s, pc)[0] is None
    pc.feats.append("Giant Killer")
    nxt, _ = _next_blow(e, s, pc)
    assert nxt and nxt["target"] == "c2"


def _pounce(feats, acted=False):
    from tests.test_feats_b4_moves import _rolls

    pc = _pc("fighter", feats=feats)
    s, e = _board(pc, ("thug", (11, 5)), faces={"Attack with": 17, "Confirm": 2})
    if not acted:
        s.acted.discard("c1")
    res = _attack(e, charge=True)
    assert any(o.op == "move" for o in res.outcomes), _tells(res)
    return _rolls(res, "Confirm")


def test_jaguar_pounce_threatens_as_improved_critical_on_a_charge_at_the_flat_footed():
    """Sargava: "When making a charge ... against an opponent who is flat-footed or
    helpless, you treat your first melee attack ... as if you had the Improved Critical
    feat." Before: the line waited on a charge that had merged. A natural 17 with a
    19-20 blade is no threat without it; with it the blade threatens 17-20 and the
    confirmation is rolled — only while the thug has not acted."""
    assert _pounce([]) == []
    assert len(_pounce(["Jaguar Pounce"])) == 1
    assert _pounce(["Jaguar Pounce"], acted=True) == []


def _grappled_at(feats, foe="thug", acted=True):
    pc = _pc("fighter", feats=feats)
    pc.race, pc.size = "halfling", "small"
    s, e = _board(pc, (foe, (6, 5)), faces={"Grapple": 1, "Trip": 15})
    if not acted:
        s.acted.discard("pc")
    s.turn = 1                                            # the foe's turn
    return s, e, pc, _run(e, {"op": "attack", "actor": "c1", "target": "pc",
                              "visibility": "hidden", "params": {"manoeuvre": "grapple"}})


def test_under_and_over_trips_the_larger_grappler_who_failed():
    """APG: "If an opponent larger than you attempts to grapple you and fails, you may
    make a trip attack as an immediate action against that opponent with a +2 bonus."
    Before: the line waited on an immediate-action budget that had merged. The thug's
    grapple fails (a natural 1): the halfling's trip follows, its +2 named, and it
    spends her next swift."""
    from tests.test_feats_b4_moves import _rolls

    s, e, pc, res = _grappled_at(["Agile Maneuvers", "Under and Over"])
    trips = _rolls(res, "Trip (CMB)")
    assert trips and any(m.get("source") == "Under and Over" and m.get("value") == 2
                         for m in trips[0].get("modifiers") or ()), _tells(res)
    assert "Under and Over" in _tells(res)
    assert s.swift_spent.get("pc") is not None


def test_under_and_over_is_not_offered_flat_footed_or_without_the_feat():
    from tests.test_feats_b4_moves import _rolls

    s, e, pc, res = _grappled_at(["Agile Maneuvers"])
    assert _rolls(res, "Grapple (CMB)") and not _rolls(res, "Trip (CMB)")
    s, e, pc, res = _grappled_at(["Agile Maneuvers", "Under and Over"], acted=False)
    assert not _rolls(res, "Trip (CMB)") and "flat-footed" in _tells(res)

"""Held, questioned, judged, sentenced — and the ways out (owner ruling 2026-11-01).

The ruling: "you are held questioned and if found guilty charged appropriately, with murder
being a death sentence. you should always have to ability to talk your way out of things.
but if you cant then either you pay your fine and have stolen goods confiscated or worst
case are executed. or you can escape from your cell or during the walk to your execution."

Measured before it: going quietly was one night held and release at morning "for want of
proof" whatever the character had done — a thief seen by the guard with the apple still in
the pack walked out at eight with the apple, and a theft nobody but the victim saw was
never reported to anybody. Each test below names the half of the ruling it holds.
"""
from __future__ import annotations

import pytest

from rules import arrest, attitude, deeds, goods, states, trial
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.sheet import from_dict
from tests.test_wanted import MARKET, TOWN, _table, _want

GAOL = f"{TOWN}~urban:the-gaol"


def _guard(s, name="the guardsman", tag=states.GUARD):
    g = s.add(instantiate("watchman", scene=s, name=name), zone="near")
    if tag != states.GUARD:
        g.apply_effect(ActiveEffect(name="an officer of the watch", kind="situation",
                                    key="role:officer", source="rule:test",
                                    duration="until-dismissed", tags=(tag,)))
    return g


def _seller(s, ref="c90", name="the fruit seller"):
    d = {"name": name, "kind": "npc", "hp": 20, "hp_max": 20,
         "abilities": {k: 10 for k in ("str", "dex", "con", "int", "wis", "cha")},
         "goods": {"apple": 20}}
    return s.add(from_dict(d, ref=ref))


def _run(e, raw, face=10):
    res = e.run(e.validate(raw if isinstance(raw, list) else [raw], origin="author:test"))
    done = []
    while res.awaiting:
        done.extend(res.outcomes)
        res = e.resume(face)
    res.outcomes[:0] = [o for o in done if o not in res.outcomes]
    return res


def _wait(e, face=10):
    return _run(e, {"op": "narrate_only", "because": "t"}, face)


def _check(e, skill, target=None, face=10, **params):
    raw = {"op": "check", "actor": "pc", "because": "t", "params": {"skill": skill, **params}}
    if target:
        raw["target"] = target
    return _run(e, raw, face)


def _law(res):
    return [o for o in res.outcomes if o.op in ("arrest", "trial", "report")]


def _tells(res) -> str:
    return " | ".join(o.tell for o in res.outcomes)


def _steal_an_apple(e, s, face=10):
    """A theft the real way: the player takes an apple off a seller who is standing there."""
    return _run(e, {"op": "give", "actor": "pc", "because": "pockets one",
                    "params": {"item": "apple", "to": "pc"}}, face)


def _taken_for_theft(seed=3):
    """Theft seen by a guard: a warrant, the arrest, the player goes quietly — held."""
    s, e, pc = _table(seed)
    _seller(s)
    g = _guard(s)
    res = _steal_an_apple(e, s)
    assert states.standing_with_the_law(pc, TOWN) == "wanted", _tells(res)
    assert pc.has_state(states.ARRESTING), _tells(res)
    res = _wait(e)                                  # going quietly
    return s, e, pc, g, res


# --- ruling 1: the crime reaches the watch ----------------------------------------------

def test_ruling_theft_seen_by_a_guard_is_a_warrant_with_its_charge():
    """Before: a theft under a guard's nose wrote a deed and nothing else; the watch had no
    door from a crime to a warrant except a break-in. Now the guard who saw it is a warrant,
    and the warrant says what it is for."""
    s, e, pc = _table()
    _seller(s)
    _guard(s)
    res = _steal_an_apple(e, s)
    told = [o for o in res.outcomes if o.op == "give"]
    assert told and "Seen by" in told[0].tell and "warrant for theft" in told[0].tell, \
        _tells(res)
    assert any(x.get("kind") == "wanted" for x in told[0].effects)
    w = [x for x in pc.effects if states.wanted_tag(TOWN) in x.tags]
    assert w and w[0].payload["crime"] == "theft"


def test_ruling_theft_only_the_victim_saw_is_suspicion_first_then_a_warrant():
    """The break-in's ladder for everything else: seen by a civilian, a name on the watch's
    lips; again (another day, another theft), a warrant."""
    s, e, pc = _table()
    _seller(s)
    _steal_an_apple(e, s)
    assert states.standing_with_the_law(pc, TOWN) == "suspected"
    s.clock_minutes += 24 * 60                      # the deeds' day gate: a new theft
    _steal_an_apple(e, s)
    assert states.standing_with_the_law(pc, TOWN) == "wanted"


def test_ruling_a_sleight_of_hand_past_every_eye_is_no_crime_the_watch_can_charge():
    """Measured live 2026-11-01: a "flawless" Sleight of Hand at the stall was still "seen
    by" both guardsmen — every conscious person present counted as a witness, whatever the
    hands did. CRB p.104: the opponent's Perception opposes the Sleight of Hand result."""
    s, e, pc = _table()
    _seller(s)
    g = _guard(s)
    pc.ranks["sleight of hand"] = 8                 # trained, and good at it
    total = 20 + sum(m.value for m in pc.skill_modifiers("sleight of hand"))
    best = 20 + max(sum(m.value for m in a.skill_modifiers("perception"))
                    for a in (g, s.people["c90"]))
    assert total > best, (total, best)        # nobody present can match it
    raw = [{"op": "check", "actor": "pc", "because": "palms it",
            "params": {"skill": "sleight of hand", "dc": {"band": "average"}}},
           {"op": "give", "actor": "pc", "because": "pockets one",
            "params": {"item": "apple", "to": "pc"}}]
    res = _run(e, raw, face=20)
    assert "Nobody saw it done" in _tells(res), _tells(res)
    assert states.standing_with_the_law(pc, TOWN) == ""
    assert trial.charges(e, pc, TOWN) == [] or all(c.goods for c in trial.charges(e, pc, TOWN))


def test_ruling_nobody_saw_it_nothing_is_reported():
    s, e, pc = _table()
    seller = _seller(s)
    deeds.record(pc, "deed.theft", scene=s, subject=seller.ref, subject_name=seller.name,
                 what="an apple", witnesses=[])
    assert trial.charges(e, pc, TOWN) == []


# --- ruling 1: held and questioned --------------------------------------------------------

def test_ruling_going_quietly_is_held_at_the_gaol_and_questioned_on_the_charge():
    s, e, pc, g, res = _taken_for_theft()
    held = trial.custody(pc)
    assert held is not None and held.payload["stage"] == "questioning"
    assert s.at == GAOL and g.at == GAOL, "the guard walks them in"
    t = _tells(res)
    assert "questions" in t and "theft" in t and "caught" in t, t
    assert "Diplomacy, Bluff or Intimidate" in t


def test_ruling_walking_to_the_gaol_with_the_guards_is_going_quietly_not_running():
    """Measured live 2026-11-01 on the owner's save: "I raise my hands and go quietly with
    the guards" was planned as a travel to the guardhouse, and the arrest told it "You are
    away before the guardsmen can lay hands on you". Arriving at the watch's own hold is
    the surrender; the guards are there when the questions start."""
    s, e, pc = _table()
    _seller(s)
    g = _guard(s)
    _steal_an_apple(e, s)
    res = _run(e, {"op": "travel", "actor": "pc", "because": "t",
                   "params": {"place": "the gaol"}})
    assert "away before" not in _tells(res), _tells(res)
    held = trial.custody(pc)
    assert held is not None and held.payload["stage"] == "questioning", _tells(res)
    assert g.at == GAOL and g.ref in s.actors


def test_ruling_the_talk_at_questioning_is_the_books_dc_never_the_plans():
    """The plan wrote a trivial band; the questioner's attitude DC plus Make Request's
    "aid that could result in punishment" (+15, CRB p.93) is the number, for a thief caught
    with the goods."""
    s, e, pc, g, _ = _taken_for_theft()
    res = _check(e, "diplomacy", face=1, dc={"band": "very_easy"})   # said to the room
    check = next(o for o in res.outcomes if o.op == "check")
    assert check.dc["value"] == attitude.influence_dc(g) + 15, check.dc
    assert "aid that could result in punishment" in check.dc.get("basis", "")


def test_ruling_a_made_diplomacy_at_questioning_drops_the_charge_and_the_rule_warrant():
    s, e, pc, g, _ = _taken_for_theft()
    attitude.set_regard(g, 95, "test")              # helpful: DC 0 + Cha + 15
    res = _check(e, "diplomacy", g.ref, face=20)
    assert "drops the charges" in _tells(res), _tells(res)
    assert trial.custody(pc) is None
    assert states.standing_with_the_law(pc, TOWN) == "", "the law's own warrant lifted"
    assert trial.charges(e, pc, TOWN) == [] or all(c.proof == "caught" and c.goods
                                                   for c in trial.charges(e, pc, TOWN))


def test_ruling_bluff_at_questioning_is_against_sense_motive_at_the_proofs_believability():
    """Caught with the goods, a denial is far-fetched: -10 on the liar's roll (CRB p.90)."""
    s, e, pc, g, _ = _taken_for_theft()
    res = _check(e, "bluff", g.ref, face=10, opposed_by={"ref": g.ref, "skill": "perception"})
    check = next(o for o in res.outcomes if o.op == "check")
    roll = check.rolls[0]
    assert any(m.value == -10 for m in roll.modifiers), roll.modifiers
    assert "sense motive" in check.tell.lower()


def test_ruling_intimidate_lets_them_go_with_the_warrant_standing():
    s, e, pc, g, _ = _taken_for_theft()
    res = _check(e, "intimidate", g.ref, face=20)
    check = next(o for o in res.outcomes if o.op == "check")
    assert check.verdict == "success", check.tell   # the watchman's 10 + 1 HD + Wis 0
    assert check.dc["value"] == attitude.intimidate_dc(g)
    assert "Cowed" in _tells(res)
    assert trial.custody(pc) is None
    assert states.standing_with_the_law(pc, TOWN) == "wanted"


def test_ruling_a_second_talk_at_the_same_stage_is_refused_and_rolls_nothing():
    """Measured live 2026-11-01 on the owner's save: the plan wrote two Diplomacy checks for
    "I try to persuade the guardsman", the first at the law's DC 29, the second falling
    through to the plan's DC 10. A refused request stands (CRB p.93): the second is refused."""
    s, e, pc, g, _ = _taken_for_theft()
    raw = [{"op": "check", "actor": "pc", "target": g.ref, "because": "t",
            "params": {"skill": "diplomacy"}},
           {"op": "check", "actor": "pc", "target": g.ref, "because": "t again",
            "params": {"skill": "diplomacy"}}]
    res = _run(e, raw, face=1)
    checks = [o for o in res.outcomes if o.op == "check"]
    assert checks[0].dc["value"] == attitude.influence_dc(g) + 15
    assert checks[1].effects == [] and "heard" in checks[1].tell and not checks[1].rolls


def test_ruling_a_failed_talk_is_guilty_and_a_second_chance_before_sentence():
    s, e, pc, g, _ = _taken_for_theft()
    res = _check(e, "diplomacy", g.ref, face=1)
    t = _tells(res)
    assert "guilty of" in t and "speak once more" in t, t
    assert trial.custody(pc).payload["stage"] == "plea"


# --- ruling 1: the fine and the stolen goods ---------------------------------------------

def test_ruling_the_fine_is_paid_and_the_stolen_goods_go_back_to_their_owner():
    """Gaius, Institutes III.190: caught with it, fourfold — at least the gold piece."""
    s, e, pc, g, _ = _taken_for_theft()
    pc.purse = {"gp": 30}
    _check(e, "diplomacy", g.ref, face=1)           # guilty
    before = goods.in_copper(pc.purse)
    res = _wait(e)                                  # silent at the plea: sentence
    t = _tells(res)
    assert "fine is" in t and "Taken back to their owners: apple to the fruit seller" in t, t
    assert before - goods.in_copper(pc.purse) >= 100
    rec = next(r for r in s.props if r["name"] == "apple")
    assert rec["held_by"] == "c90" and not rec.get("stolen")
    assert trial.custody(pc) is None
    assert states.standing_with_the_law(pc, TOWN) == "", "the debt is paid"
    assert trial.charges(e, pc, TOWN) == [], "a deed judged is never charged again"


def test_ruling_an_unpaid_fine_is_worked_off_at_a_labourers_wage_at_most_thirty_days():
    s, e, pc, g, _ = _taken_for_theft()
    pc.purse = {}
    _check(e, "diplomacy", g.ref, face=1)
    clock = s.clock_minutes
    res = _wait(e)
    t = _tells(res)
    assert "no coin to pay it" in t and "worked off" in t, t
    days = (s.clock_minutes - clock) // (24 * 60)
    assert 1 <= days <= 30


def test_ruling_a_plea_made_waives_the_fine_and_the_goods_still_go_back():
    s, e, pc, g, _ = _taken_for_theft()
    pc.purse = {"gp": 30}
    _check(e, "diplomacy", g.ref, face=1)
    attitude.set_regard(g, 95, "test")
    res = _check(e, "diplomacy", g.ref, face=20)
    res = res if trial.custody(pc) is None else _wait(e)
    t = _tells(res)
    assert "fine is waived" in t and "apple to the fruit seller" in t, t
    assert goods.in_copper(pc.purse) == 3000


# --- ruling 1: murder -------------------------------------------------------------------

def _murderer(seed=3):
    """A killing of somebody who had not raised a hand, seen by a guard: murder."""
    s, e, pc = _table(seed)
    victim = _seller(s, name="the cooper")
    g = _guard(s)
    deeds.record(pc, "deed.kill.unprovoked", scene=s, subject=victim.ref,
                 subject_name=victim.name, witnesses=[g.ref])
    _want(pc)
    return s, e, pc, g


def _condemned(seed=3):
    s, e, pc, g = _murderer(seed)
    _wait(e)                                        # the arrest begins
    _wait(e)                                        # taken
    _check(e, "diplomacy", g.ref, face=1)           # guilty
    res = _wait(e)                                  # sentence
    return s, e, pc, g, res


def test_ruling_murder_is_a_death_sentence():
    s, e, pc, g, res = _condemned()
    t = _tells(res)
    assert "hang at first light tomorrow for murder" in t, t
    assert trial.custody(pc).payload["stage"] == "condemned"
    assert "pick the lock" in t and "Escape Artist" in t and "Strength" in t


def test_ruling_killing_a_beaten_foe_after_the_fight_is_murder():
    """The owner's answer of 2026-11-01: a foe who was down, held or helpless and no longer
    a threat, killed after the fight (deed.kill.captive), is murder. Until then it was left
    uncharged, the question open."""
    s, e, pc = _table()
    v = _seller(s)
    g = _guard(s)
    deeds.record(pc, "deed.kill.captive", scene=s, subject=v.ref, subject_name=v.name,
                 witnesses=[g.ref])
    chs = trial.charges(e, pc, TOWN)
    assert [c.kind for c in chs] == ["murder"] and chs[0].proof == "caught"


def test_ruling_finishing_a_helpless_foe_after_the_fight_reaches_the_watch_as_murder():
    """The real path: a hostile, sapient, helpless foe struck dead out of a fight is the
    deeds' captive row, and a guard watching lays a warrant for murder at once."""
    s, e, pc = _table()
    v = _seller(s)
    g = _guard(s)
    attitude.set_regard(v, 0, "test")                  # hostile: they came at the player
    v.add_condition("unconscious", source="test")     # beaten, helpless
    v.hp = 1
    res = _run(e, {"op": "damage", "actor": "pc", "target": v.ref, "because": "t",
                   "params": {"amount": 30, "type": "slashing"}}, face=19)
    assert v.is_dead, _tells(res)
    assert deeds.of(pc, "deed.kill.captive"), pc.deeds
    w = [x for x in pc.effects if states.wanted_tag(TOWN) in x.tags]
    assert w and w[0].payload["crime"] == "murder", _tells(res)


def test_ruling_an_unprovoked_victim_killed_outright_is_murder():
    """Struck dead by the player's own blow, having raised no hand: murder."""
    s, e, pc = _table()
    v = _seller(s)
    g = _guard(s)
    v.hp = 1
    res = _run(e, {"op": "damage", "actor": "pc", "target": v.ref, "because": "t",
                   "params": {"amount": 30, "type": "slashing"}}, face=19)
    assert v.is_dead, _tells(res)
    row = deeds.of(pc, "deed.kill.unprovoked")[0]
    assert row["manner"] == "blow"
    assert "murder" in [c.kind for c in trial.charges(e, pc, TOWN)]


def test_ruling_an_unprovoked_victim_left_to_bleed_out_is_manslaughter_not_murder():
    """The owner: "be sure that letting someone bleedout ... are not murder and instead
    manslaughter". Before it, a victim struck down and dead an hour later was murder, the
    same as one struck dead: the deeds record could not tell a blow from a bleeding."""
    s, e, pc = _table()
    v = _seller(s)
    g = _guard(s)
    deeds.record(pc, "deed.violence.unprovoked", scene=s, subject=v.ref,
                 subject_name=v.name, witnesses=[g.ref])
    v.die("bled out")                                  # the bleeding did it, not a blow
    res = _wait(e)
    row = deeds.of(pc, "deed.kill.unprovoked")[0]
    assert row["manner"] == "after", row
    kinds = [c.kind for c in trial.charges(e, pc, TOWN)]
    assert "manslaughter" in kinds and "murder" not in kinds, kinds
    assert "warrant for a killing" in _tells(res), _tells(res)


def test_ruling_walking_away_from_a_dying_victim_is_manslaughter_seen_by_who_saw_the_blow():
    """Left to bleed out the real way: struck down before the guard, left dying, the player
    walks off and the travel door resolves the dying (`_resolve_dying`). Before the fix the
    kill row took its witnesses from the room the player had walked INTO (the tavern), so
    the guard who saw the blow was no witness to the death it caused."""
    s, e, pc = _table()
    v = _seller(s)
    g = _guard(s)
    deeds.record(pc, "deed.violence.unprovoked", scene=s, subject=v.ref,
                 subject_name=v.name, witnesses=[g.ref])
    v.hp = v.death_floor() + 1
    v.apply_hp_state()
    assert v.has_state("state.down.dying")
    _run(e, {"op": "travel", "actor": "pc", "because": "t", "params": {"place": "the tavern"}})
    assert v.is_dead, "the seed's stabilise roll came up (10%): pick another seed"
    row = deeds.of(pc, "deed.kill.unprovoked")[0]
    assert row["manner"] == "after" and g.ref in row["witnesses"], row
    kinds = [c.kind for c in trial.charges(e, pc, TOWN)]
    assert kinds == ["manslaughter"], kinds


def test_ruling_the_blow_that_killed_is_part_of_the_killing_not_a_second_fine():
    """Measured live 2026-11-01: a victim struck down and left to bleed out was charged
    "assault (Denna Krell); a killing (Denna Krell)" — fined twice for one harm. The
    assault merges into the killing, and is judged with it so it is never charged later."""
    s, e, pc = _table()
    v = _seller(s)
    g = _guard(s)
    deeds.record(pc, "deed.violence.unprovoked", scene=s, subject=v.ref,
                 subject_name=v.name, witnesses=[g.ref])
    v.die("bled out")
    _wait(e)
    chs = trial.charges(e, pc, TOWN)
    assert [c.kind for c in chs] == ["manslaughter"] and chs[0].merged, chs
    trial._judge_all(pc, TOWN, [k for c in chs for k in [c.deed, *c.merged]])
    assert trial.charges(e, pc, TOWN) == []


def _attacker(s, hp=1):
    v = _seller(s, ref="c91", name="the cutpurse")
    attitude.set_regard(v, 0, "test")                  # hostile: came at the player
    v.hp = hp
    return v


def test_ruling_killing_someone_who_attacked_you_is_manslaughter_not_murder():
    """The owner: "killing someone who attacked you durring combat are not murder and
    instead manslaughter". Before it, the deeds record kept no row for fighting back and a
    guard could watch the player kill an attacker with the law silent. A guard-witnessed
    self-defence kill is now a warrant for manslaughter: a fine of 10 gp (law.json)."""
    s, e, pc = _table()
    g = _guard(s)
    v = _attacker(s)
    res = _run(e, {"op": "damage", "actor": "pc", "target": v.ref, "because": "t",
                   "params": {"amount": 30, "type": "slashing"}}, face=19)
    assert v.is_dead, _tells(res)
    assert not deeds.of(pc, "deed.kill"), "fighting back is still no deed"
    chs = trial.charges(e, pc, TOWN)
    assert [c.kind for c in chs] == ["manslaughter"] and chs[0].proof == "caught", chs
    assert "Seen by the guardsman: there will be a warrant for a killing" in _tells(res)
    assert trial.fine_cp(chs[0]) == 1000


def test_ruling_a_downed_attacker_left_to_bleed_out_is_manslaughter():
    """The other half: an attacker the player dropped dying, dead since by bleeding, is
    manslaughter — remembered from the moment they went down, witnesses and all."""
    from types import SimpleNamespace

    s, e, pc = _table()
    g = _guard(s)
    v = _attacker(s, hp=5)
    from rules import deeds as deeds_mod

    snap = deeds_mod.before(e)
    v.hp = -2
    v.apply_hp_state()
    blow = SimpleNamespace(actor=pc.ref, status="resolved",
                           effects=[{"kind": "condition", "ref": v.ref, "condition": "dying"}])
    assert trial.watch(e, blow, blow, snap, []) == []
    v.die("bled out")
    later = SimpleNamespace(actor=pc.ref, status="resolved", effects=[])
    got = trial.watch(e, later, later, deeds_mod.before(e), [])
    assert got and got[0]["crime"] == "manslaughter" and got[0]["how"] == "bled-out"
    assert [c.kind for c in trial.charges(e, pc, TOWN)] == ["manslaughter"]


def test_ruling_fighting_off_an_attacker_without_a_death_is_uncharged():
    """Careless or defensive harm short of a death is left uncharged (the owner's question
    unanswered): only the player striking first is assault."""
    s, e, pc = _table()
    g = _guard(s)
    v = _attacker(s, hp=200)
    v.hp_max = 200
    _run(e, {"op": "damage", "actor": "pc", "target": v.ref, "because": "t",
             "params": {"amount": 6, "type": "slashing"}}, face=19)
    assert not v.is_dead
    assert trial.charges(e, pc, TOWN) == []


def test_ruling_no_proof_released_the_frame_up_cannot_convict_the_innocent():
    """The owner's answer of 2026-11-01: "No proof, released". A Small Favour names the
    player for a killing they did not do; its warrant carries the charge and nothing else —
    no witnessed deed, no stolen goods. Before the answer that accusation alone convicted a
    silent player, and an innocent character hanged. Now it falls at questioning, the
    warrant is lifted, and the tell says why."""
    from rules import schemes

    s, e, pc = _table()
    g = _guard(s)
    schemes._grant(s, {}, {"to": "pc", "tags": ["state.wanted.$town"], "charge": "murder"},
                   "scheme:wanted/open", {"town": TOWN})
    assert states.standing_with_the_law(pc, TOWN) == "wanted"
    c = trial.charges(e, pc, TOWN)
    assert [(x.kind, x.proof) for x in c] == [("murder", "accused")]
    _wait(e)                                           # the watch comes
    res = _wait(e)                                     # going quietly
    t = _tells(res)
    assert "accusation of murder falls for want of proof" in t, t
    assert "let go for want of proof" in t
    assert trial.custody(pc) is None and not pc.is_dead
    assert states.standing_with_the_law(pc, TOWN) == "", "the warrant is lifted"


def test_a_bluff_against_somebody_left_behind_is_refused_not_a_crash():
    """Measured live 2026-11-01 on the frame-up: "I hold out my wrists and go quietly" was
    planned as a walk to the guardhouse and a Bluff against the stallholder left at the
    market; `scene.actors[ref]` raised KeyError and the turn was a 502, twice running."""
    s, e, pc = _table()
    v = _seller(s)
    raw = [{"op": "travel", "actor": "pc", "because": "t", "params": {"place": "the gaol"}},
           {"op": "check", "actor": "pc", "because": "t",
            "params": {"skill": "bluff", "opposed_by": {"ref": v.ref, "skill": "sense motive"}}}]
    res = _run(e, raw)
    check = next(o for o in res.outcomes if o.op == "check")
    assert check.effects == [] and "not here" in check.tell, check.tell


def test_ruling_an_accusation_falls_but_a_witnessed_charge_beside_it_stands():
    s, e, pc = _table()
    g = _guard(s)
    v = _seller(s)
    from rules import schemes

    schemes._grant(s, {}, {"to": "pc", "tags": ["state.wanted.$town"], "charge": "murder"},
                   "scheme:wanted/open", {"town": TOWN})
    deeds.record(pc, "deed.theft", scene=s, subject=v.ref, subject_name=v.name,
                 what="apple", witnesses=[g.ref])
    _wait(e)
    res = _wait(e)
    t = _tells(res)
    assert "accusation of murder falls" in t and "charged with theft" in t, t
    held = trial.custody(pc)
    assert [c["kind"] for c in held.payload["charges"]] == ["theft"]


def test_ruling_a_plea_made_commutes_death_to_the_blood_price():
    s, e, pc, g = _murderer()
    pc.purse = {"gp": 50}
    _wait(e)
    _wait(e)
    _check(e, "diplomacy", g.ref, face=1)
    attitude.set_regard(g, 95, "test")
    res = _check(e, "diplomacy", g.ref, face=20)
    res = res if trial.custody(pc) is None else _wait(e)
    t = _tells(res)
    assert "commuted to the blood price" in t, t
    assert not pc.is_dead and trial.custody(pc) is None


# --- ruling 1: escape -------------------------------------------------------------------

def test_ruling_the_cell_lock_is_disable_device_at_the_books_dc_plus_ten_without_tools():
    s, e, pc, g, _ = _condemned()
    res = _check(e, "disable device", face=1, dc={"band": "very_easy"})
    check = next(o for o in res.outcomes if o.op == "check")
    assert check.dc["value"] == 30, check.dc          # simple lock 20, no thieves tools


def test_ruling_escaping_the_cell_leaves_them_free_and_still_wanted():
    s, e, pc, g, _ = _condemned()
    pc.abilities["str"] = 28                        # +9: a natural 20 makes the door
    # Forcing the door: the cell's Strength DC, through the break-in door (CRB doors).
    res = _run(e, {"op": "break_in", "actor": "pc", "because": "t",
                   "params": {"how": "force"}}, face=20)
    out = next(o for o in res.outcomes if o.op == "break_in")
    assert out.dc["value"] == 18, out.dc
    assert out.verdict == "success", out.tell
    assert "slips away" in _tells(res) or "Out of the cell" in _tells(res), _tells(res)
    assert trial.custody(pc) is None and not pc.is_dead
    assert s.at != GAOL
    assert states.standing_with_the_law(pc, TOWN) == "wanted"


def test_ruling_no_escape_is_the_walk_and_then_the_execution():
    s, e, pc, g, _ = _condemned()
    res = _wait(e)                                  # the night passes
    assert "first light" in _tells(res) and trial.custody(pc).payload["stage"] == "walk"
    res = _wait(e)                                  # goes to it
    t = _tells(res)
    assert "is hanged for murder" in t, t
    # "with the town looking on", never "before the town": read as time by the death slot
    # 5 of 21 re-asks ("before the crowd can gather"), 0 of 21 so (round 3, 2026-11-05).
    assert "with the town looking on" in t and "before the town" not in t, t
    assert pc.is_dead
    assert any(x.get("origin") == trial.EXECUTION for o in res.outcomes for x in o.effects)


def test_ruling_breaking_away_on_the_walk_is_a_roll_against_the_escorts_cmd():
    s, e, pc, g, _ = _condemned()
    _wait(e)                                        # the walk
    res = _run(e, {"op": "escape", "actor": "pc", "because": "t", "params": {}}, face=20)
    out = next(o for o in res.outcomes if o.op == "escape")
    assert "CMD" in out.tell, out.tell
    if out.verdict == "success":
        assert trial.custody(pc) is None and not pc.is_dead
        assert "runs" in _tells(res)


def test_ruling_a_walk_while_held_on_the_gallows_road_is_refused_and_rolls_nothing():
    """Measured live 2026-11-01, twice: a walk on the gallows road was rolled as the
    break-away, and "I go to the gallows with my head held high" — planned as a travel to
    the gate — was made, and the condemned man walked free by going quietly. Held is held
    (CRB p.200): the hold is broken first, by an escape, or not at all."""
    s, e, pc, g, _ = _condemned()
    _wait(e)
    res = _run(e, {"op": "travel", "actor": "pc", "because": "t",
                   "params": {"place": "the tavern"}}, face=20)
    out = next(o for o in res.outcomes if o.op == "travel")
    assert out.effects == [] and not out.rolls and "held by the escort" in out.tell
    assert pc.is_dead, "held, and the sentence carried out at the batch's end"


def test_ruling_broken_free_on_the_walk_the_run_goes_where_the_player_said():
    s, e, pc, g, _ = _condemned()
    _wait(e)
    pc.ranks["escape artist"] = 10                  # a natural 20 beats any escort's CMD
    raw = [{"op": "escape", "actor": "pc", "because": "t", "params": {"how": "escape artist"}},
           {"op": "travel", "actor": "pc", "because": "t", "params": {"place": "the tavern"}}]
    res = _run(e, raw, face=20)
    assert "tears free" in _tells(res), _tells(res)
    assert trial.custody(pc) is None and not pc.is_dead
    assert s.at.endswith("the-tavern"), s.at


def test_ruling_walking_to_the_gallows_on_the_walk_is_going_to_it_with_no_roll():
    """A walk to the gallows place itself is going along, not a dash for freedom: no
    break-away is rolled for it (a made roll would have freed a player who meant to go).

    And told as going along since 2026-11-04: refused as a walk "anywhere else", with the
    ways out listed, it was told as a struggle on 3 of 3 runs of the narration diagnosis
    bench ("The escort staggers back, caught off guard by your sudden resistance")."""
    s, e, pc, g, _ = _condemned()
    _wait(e)
    gallows = trial.custody(pc).payload["gallows_name"]
    for params in ({"place": gallows}, {}):
        s, e, pc, g, _ = _condemned()
        _wait(e)
        res = _run(e, {"op": "travel", "actor": "pc", "because": "t",
                       "params": params}, face=20)
        out = next(o for o in res.outcomes if o.op == "travel")
        assert not out.rolls and out.status == "resolved", out
        assert "goes along with the escort" in out.tell and "choose" not in out.tell, out.tell
        assert pc.is_dead


def test_ruling_walking_out_of_the_cell_is_refused_with_the_ways_out_named():
    s, e, pc, g, _ = _condemned()
    res = _run(e, {"op": "travel", "actor": "pc", "because": "t",
                   "params": {"place": "the tavern"}})
    out = next(o for o in res.outcomes if o.op == "travel")
    assert out.effects == [] and "Disable Device" in out.tell
    assert s.at == GAOL


def test_ruling_a_bribe_big_enough_opens_the_door_and_too_little_comes_back():
    """Ultimate Intrigue p.124: a quarter of the guard's Table 14-9 gear to look away. Both
    offers in the one night: a single gold piece pushed back, then the price, taken."""
    s, e, pc, g, _ = _condemned()
    price = trial.bribe_price_cp(g)
    pc.purse = {"gp": 2 * price // 100}
    raw = [{"op": "give", "actor": "pc", "target": g.ref, "because": "t",
            "params": {"item": "gp", "count": 1, "to": g.ref}},
           {"op": "give", "actor": "pc", "target": g.ref, "because": "t",
            "params": {"item": "gp", "count": price // 100, "to": g.ref}}]
    res = _run(e, raw)
    t = _tells(res)
    assert "pushes it back" in t and "looks the other way" in t, t
    assert goods.in_copper(pc.purse) == price, "the small coin came back, the price went"
    assert trial.custody(pc) is None and not pc.is_dead


def test_ruling_beaten_by_the_law_is_taken_in_and_on_the_walk_it_is_the_end():
    s, e, pc, g = _murderer()
    got = trial.beaten(e, pc, [g])
    assert got is not None and "questions" in " ".join(got[1])
    assert trial.custody(pc).payload["stage"] == "questioning"
    s2, e2, pc2, g2, _ = _condemned()
    _wait(e2)
    trial.beaten(e2, pc2, [g2])
    assert pc2.is_dead


def test_ruling_custody_is_one_effect_and_removing_it_ends_it():
    """Law 2: one record; removed, nothing is owed and the next batch is free."""
    s, e, pc, g, _ = _taken_for_theft()
    pc.remove_effects(source=trial.SOURCE)
    pc.apply_effect(ActiveEffect(name="t", kind="situation", key="x", source="rule:test",
                                 duration="rounds", rounds_left=24 * 600,
                                 tags=(states.stood_down_tag(TOWN),)))
    assert not [o for o in _wait(e).outcomes if o.op == "trial"]


def test_ruling_the_law_document_is_validated_on_load():
    doc = trial.document()
    assert trial.validate(doc) == []
    bad = {**doc, "charges": {**doc["charges"], "murder": {**doc["charges"]["murder"],
                                                          "plea": "nothing"}}}
    assert any("plea" in p for p in trial.validate(bad))


def test_ruling_a_scheme_warrant_says_what_it_is_for():
    """A Small Favour names the player for a killing: its warrant carries `murder`, the
    accusation the trial reads. A charge on anything but a warrant is refused."""
    from rules import schemes

    doc = schemes.all_schemes()["wanted"]
    assert schemes.validate(doc) == []
    g = next(x for x in doc["grants_on_open"] if "state.wanted.$town" in x["tags"])
    assert g["charge"] == "murder"
    bad = dict(doc, grants_on_open=[{"to": "pc", "tags": ["knows.x"], "say": "x",
                                     "charge": "murder"}])
    assert any("charge goes on a warrant" in p for p in schemes.validate(bad))


# --- ruling 2: officers arrest too --------------------------------------------------------

def test_ruling_a_watch_captain_with_the_officer_tag_comes_to_arrest():
    """Corvin's turns 56-61: the scheme's captain stood there with no guard tag and never
    came. `role.guard.officer` answers `has_state("role.guard")` by the prefix (law 1)."""
    s, e, pc = _table()
    _want(pc)
    cap = s.add(instantiate("guildhand", scene=s, name="the captain"), zone="near")
    cap.apply_effect(ActiveEffect(name="officer", kind="situation", key="role:officer",
                                  source="rule:test", duration="until-dismissed",
                                  tags=(states.GUARD_OFFICER,)))
    res = _wait(e)
    got = [o for o in res.outcomes if o.op == "arrest"]
    assert got and "the captain" in got[0].tell.lower(), _tells(res)


def test_ruling_the_officer_questions_when_one_is_there():
    s, e, pc = _table()
    v = _seller(s)
    g = _guard(s)
    cap = _guard(s, "the sergeant", tag=states.GUARD_OFFICER)
    deeds.record(pc, "deed.theft", scene=s, subject=v.ref, subject_name=v.name,
                 what="apple", witnesses=[g.ref])
    _want(pc)
    _wait(e)
    res = _wait(e)
    assert trial.custody(pc).payload["questioner"] == cap.ref
    assert "The sergeant questions" in _tells(res) or "the sergeant questions" in _tells(res)


def test_ruling_a_small_favours_captain_is_granted_the_officer_tag_and_old_saves_heal():
    from rules import schemes

    doc = schemes.all_schemes()["a-small-favour"]
    assert any(g.get("to") == "$captain" and states.GUARD_OFFICER in g["tags"]
               for g in doc["grants_on_open"])
    s, e, pc = _table()
    cap = s.add(instantiate("guildhand", scene=s, name="the captain"))
    s.schemes.append({"scheme": "a-small-favour", "slots": {
        "captain": {"kind": "actor", "ref": cap.ref, "name": cap.name}}, "fired": {},
        "town": TOWN})
    assert not cap.has_state(states.GUARD)
    schemes._heal_cast_grants(s, schemes.all_schemes())
    assert cap.has_state(states.GUARD)

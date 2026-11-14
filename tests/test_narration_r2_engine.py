"""Round 2 of the narration fixes: what the engine says, and what the slots carry (2026-11-05).

The owner, 2026-11-04: "I want to have better narration. so lets make it work." The rerun of
the 44-line bench (docs/narration-diagnosis.md, "The rerun") halved the errors, 0.19 to 0.09
a beat, and named what was left. This file holds the patterns that came from engine facts,
tell wording or slot content; each was re-asked with its recorded slot call before any code
moved, and the counts are in the docstrings. Names and prose are synthetic; the bench's
lines and saves stay in scratch.
"""
from __future__ import annotations

import pytest
from django.test import override_settings

from gm import narration, planned
from gm.agent import TurnPlan, _owned_by
from rules import arrest, commission, harvest, states
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Outcome, Scene
from rules.intents import IntentError
from rules.sheet import load_pc
from tests import test_casting_executes as tc
from tests._places import stand_on
from tests.test_arrest import _batch, _guard
from tests.test_wanted import _run, _table, _want


# --- 1. who comes for the player on an arrest -----------------------------------------------

def test_the_arrest_counts_the_watch_and_people_here_says_who_is_of_it():
    """"Pallo Farrow, the guardsman and the second guardsman come for Corvin T." came back
    "Pallo Farrow, Vessa Duskwatch, and the two Grippli guardsmen" — the shopkeeper, next
    on PEOPLE HERE, counted among the watch — on 3 of 7 rerun runs, and on 3 of 6 re-asks
    of the recorded slot. The engine's arresters were right (`has_state(GUARD)`); counted
    and named as the watch, with PEOPLE HERE marking it: 0 of 6."""
    s, e, pc = _table()
    _want(pc)
    _guard(s, "the captain")
    _guard(s, "the guardsman")
    keeper = s.add(instantiate("guildhand", scene=s, name="the stallholder"), zone="near")
    got = [o for o in _batch(e).outcomes if o.op == "arrest"]
    assert got, "the watch comes"
    tell = got[0].tell
    assert tell.startswith("Two of the watch come for Kesst Vayr, and only they: the captain "
                           "and the guardsman."), tell
    assert "stallholder" not in tell
    what = {p["name"]: p["what"] for p in planned.present(e)}
    assert "of the watch" in what["the captain"] and "of the watch" in what["the guardsman"]
    assert "of the watch" not in what[keeper.name]


def test_one_guard_alone_is_said_as_one_of_the_watch():
    s, e, pc = _table()
    _want(pc)
    _guard(s)
    got = [o for o in _batch(e).outcomes if o.op == "arrest"]
    assert got[0].tell.startswith("One of the watch comes for Kesst Vayr: the guardsman."), \
        got[0].tell


# --- 2. walking to the gate is not going through it -----------------------------------------

def test_a_walk_to_the_gate_says_the_player_is_still_inside():
    """"I walk to the gate" was told as entering the town ("as you enter Reedsink", "allow
    you passage into Reedsink") on 5 rerun beats: the tell's "the guards at the gate look
    twice, and let you through" on a walk that stopped inside. 6 of 6 re-asks of the
    recorded slot passed through; with the inner side said and nothing that says "let",
    8 of 8 kept the player inside."""
    s, e, pc = _table()
    _want(pc, how="suspected")
    out = _run(e, "travel", {"place": "the gate"})
    assert s.at.endswith(":the-gate")
    assert "look twice" in out.tell, "the suspected are still looked at"
    assert "let you through" not in out.tell, out.tell
    assert "You stand on the inner side of the gate: still in" in out.tell, out.tell


def test_the_inner_side_is_said_to_anybody_who_walks_to_the_gate():
    s, e, pc = _table()
    out = _run(e, "travel", {"place": "the gate"})
    assert "You stand on the inner side of the gate: still in" in out.tell, out.tell
    assert "watch" not in out.tell


def test_going_out_through_the_gate_still_lets_the_suspected_through():
    """The look-twice line keeps "let you through" where the walk does cross the walls."""
    s, e, pc = _table()
    _want(pc, how="suspected")
    gate = next(p for p in e.places() if p.name == "the gate")
    refused, line = e.watch_at_the_way_out(pc, s.at, gate, e.places(), through=True,
                                           crossing=True)
    assert not refused and "let you through" in line
    refused, line = e.watch_at_the_way_out(pc, s.at, gate, e.places(), crossing=False)
    assert not refused and "let you" not in line and "look twice" in line


# --- 3. a harvest says each part's fate -----------------------------------------------------

def _dead_wolf(s):
    wolf = s.add(instantiate("wolf", scene=s))
    wolf.hp = -20
    wolf.die("test")
    harvest.mark_the_dead(s)
    return wolf


def _skin(faces):
    s = Scene(location_id="5bbd0c40345f")
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    stand_on(s, "forest")
    wolf = _dead_wolf(s)
    e = Engine(s, Dice(seed=3))
    seq = iter(faces)
    real = e.dice.d20

    def d20(*a, **k):
        r = real(*a, **k)
        if str(k.get("label", "")).startswith("Harvest: "):
            r.faces = [next(seq)]
        return r

    e.dice.d20 = d20
    out = e.run(e.validate([{"op": "harvest", "actor": pc.ref, "target": wolf.ref,
                             "because": "t", "params": {"parts": []}}],
                           origin="author:test")).outcomes[-1]
    return out, pc, wolf


def test_a_part_ruined_beside_a_part_kept_says_whose_ruin_it_is():
    """"peels the wolf pelt off the wolf, 1 unit … works at the wolf, and the sinew thread
    is ruined in the taking … Missed by 6: the sinew thread is ruined" came back "ruining
    the integrity of the hide" (4 errors on the rerun). Each part's fate in its own
    sentence, opening on the part, and the ruin said as the ruined part's alone: re-asked,
    the pelt kept 8 of 8."""
    out, _pc, _wolf = _skin([20, 1, 1, 1, 1])
    parts = [e["name"].lower() for e in out.effects if e.get("kind") == "harvest"]
    if len(parts) < 2:
        pytest.skip("this sheet's wolf has one part for Kesst")
    tell = out.tell
    kept = [e["name"].lower() for e in out.effects if e.get("kind") == "harvest"
            and (e["stock"] or e["carried"])]
    lost = [p for p in parts if p not in kept]
    assert kept and lost, out.tell
    for p in kept:
        assert f"The {p}: " in tell and "kept" in tell.split(f"The {p}: ", 1)[1][:60], tell
    for p in lost:
        assert f"The {p}: ruined in the taking, and none of it is kept" in tell, tell
    assert f"The ruin is the {lost[0]}" in tell and "alone" in tell, tell
    assert " it comes " not in tell and "went through it" not in tell


def test_every_part_kept_is_said_kept_and_none_is_the_knife_work():
    """A sinew cut cleanly beside the pelt was written as the knife work that freed the
    hide ("cut through the sinew threads to free the hide", 6 of 6 re-asks) and scored
    as left out (2). Said as a part kept: 8 of 8."""
    out, _pc, _wolf = _skin([20, 20, 20, 20, 20])
    parts = [e["name"].lower() for e in out.effects if e.get("kind") == "harvest"]
    for p in parts:
        assert f"The {p}: " in out.tell and "kept" in out.tell, out.tell
    if len(parts) > 1:
        assert out.tell.startswith(f"Kesst Vayr cuts {['', '', 'two', 'three'][len(parts)]}"
                                   f" parts from the wolf"), out.tell
    assert "ruin" not in out.tell


def test_a_harvest_that_kept_parts_backs_the_page_that_packs_them():
    """Found on the round-2 bench: "peeling away the wolf's pelt and cutting out the sinew
    threads to stow them safely in your pack" — true — was cut by the claims scrubber as
    an invented haul ("the satchel is the engine's to fill"): `harvest` was not among the
    doors that bring things home, and the beat shipped with no harvest on it."""
    from rules.intents import claims_the_engine_backs, find_outcome_claims

    out, _pc, _wolf = _skin([20, 20, 20, 20, 20])
    page = "You cut out the sinew threads and stow them safely in your pack."
    assert not find_outcome_claims(page, claims_the_engine_backs([out]))
    ruined = Outcome("i1", "harvest", tell="x", effects=[
        {"kind": "harvest", "stock": [], "carried": []}])
    assert find_outcome_claims(page, claims_the_engine_backs([ruined])), \
        "a harvest that kept nothing backs no haul"


def test_the_harvest_fate_reads_the_structured_answer():
    got = {"fate": "rough", "ok": False, "stock": [], "carried": [{"id": "x"}],
           "salt_spent": 0}
    from rules.engine import _harvest_fate

    assert _harvest_fate("Sinew Thread", got, "Survival 15 vs DC 16, missed by 1") == \
        "The sinew thread: cut out roughly, but kept, in the pack (Survival 15 vs DC 16, " \
        "missed by 1)."
    got = {"fate": "ruined", "ok": False, "stock": [], "carried": [], "salt_spent": 0}
    assert "ruined in the taking, and none of it is kept" in _harvest_fate("Pelt", got, "x")


# --- 4. magic missile: how many, and each one's harm ----------------------------------------

def test_one_missile_at_caster_level_one_is_said_as_one_and_is_a_blow():
    """The cast's tell gave "1d4+1 — 3. the robber takes 3 untyped." and the act slot wrote
    "Two darts" and "three glowing bolts" for one missile (3 of 7 rerun runs; 7 of 8
    re-asks), and once left the wound out. Said as one missile, and carried as a blow:
    12 of 12 one bolt, the wound told."""
    w = tc.wizard(level=1, prepared={"magic-missile": 2})
    _s, e = tc.table(w)
    out = tc.cast(e, "magic-missile").outcomes[0]
    assert "One missile of force flies, the only one a caster of level 1 makes: it strikes " \
           "the thug for " in out.tell, out.tell
    assert [b["weapon"] for b in out.blows] == ["Magic Missile, its one missile"]
    facts = planned.blow_facts([out], e, said={})
    assert facts and facts[0].startswith("HIT — you at the thug — weapon: Magic Missile, "
                                         "its one missile (force)"), facts


def test_a_caster_of_level_three_looses_two_missiles_each_its_own_share():
    """CRB p.310: one missile, plus one for every two caster levels beyond 1st, to five at
    9th. The engine rolled one 1d4+1 at every level."""
    w = tc.wizard(level=3, prepared={"magic-missile": 2})
    _s, e = tc.table(w)
    out = tc.cast(e, "magic-missile").outcomes[0]
    assert out.effects[0]["dice"] == "2d4+2"
    assert "Two missiles of force fly, as many as a caster of level 3 makes: the first " \
           "strikes the thug for " in out.tell, out.tell
    assert [b["weapon"] for b in out.blows] == ["Magic Missile, missile 1 of 2",
                                                "Magic Missile, missile 2 of 2"]
    dealt = sum(x["amount"] for x in out.effects if x.get("kind") == "damage")
    roll = next(r for r in out.rolls if r.die == "2d4+2")
    assert dealt == roll.total


def test_more_targets_than_missiles_leaves_the_rest_unreached():
    from rules import spells as spells_mod

    assert [spells_mod.missiles_at("magic-missile", cl) for cl in (1, 2, 3, 5, 9, 15)] == \
        [1, 1, 2, 3, 5, 5]
    assert spells_mod.missiles_at("fireball", 5) == 0
    from rules.engine import _missiles_split

    split = _missiles_split(Dice(seed=1), "1d4+1", [4, 2, 3], 3, ["c1", "c2"])
    assert [(m["ref"], m["amount"]) for m in split] == [("c1", 5), ("c2", 3), ("c1", 4)]


# --- 5. a price agreed for work already paid ------------------------------------------------

def test_a_price_already_paid_is_said_as_paid_before_and_no_coin_now():
    """"pays nothing more: the smith took the fee with the job" was still told as the
    smith accepting the coin now (rerun: 1 of 7; re-asked: 5 of 6). Said as a payment in
    the past, and none now: 0 of 8."""
    said = commission.paid_before("Kesst Vayr", "the smith")
    assert "earlier, when the job was taken" in said and "no coin changes hands" in said
    assert "took the fee" not in said


def test_the_players_line_never_rides_somebody_elses_act():
    """"I agree to his price and pay" rode the smith's own `say` ("A fair trade …") and
    came back "eyes narrowing as they inspect the payment" (2 of 7 runs; 4 of 6 re-asks of
    the recorded call, 0 of 8 with the line off it), beside the engine's refused payment."""
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    smith = s.add(instantiate("guildhand", scene=s, name="the smith"))
    engine = Engine(s, Dice(seed=3))
    smith_says = Outcome("i1", "say", actor=smith.ref,
                         tell="the smith speaks, to the effect that \"A fair trade.\"")
    refused = Outcome("i2", "commission", status="refused", actor="pc",
                      tell=commission.paid_before("Kesst Vayr", "the smith"))
    slots = planned.build_plan(engine, "I agree to his price and pay", [smith_says, refused])
    assert all("and pay" not in x["say"] for x in slots), [x["say"] for x in slots]
    # And the line still rides the player's own act when there is one.
    took = Outcome("i3", "quest", actor="pc", tell="Kesst Vayr takes it on: Courier.")
    slots = planned.build_plan(engine, "I take the job", [smith_says, took])
    assert '"I take the job"' in next(x["say"] for x in slots if x["key"] == "fact2")


def test_an_act_naming_the_player_says_who_the_player_is():
    """The gallows walk (handed over by the pipeline lane): "snaps Corvin T. into the air, and
    he dies instantly" — the name became "you" downstream, the "he" stayed. Re-asked with
    its recorded call: third person 8 of 8; with the sentence, 0 of 8 (and the arrest,
    price and harvest asks re-asked with it held their own counts: 0 of 6, 0 of 6, 6 of 6
    pelts kept)."""
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    engine = Engine(s, Dice(seed=3))
    hanged = Outcome("", "trial", tell="At the market, Kesst Vayr is hanged for murder. "
                                       "Kesst Vayr is dead.")
    say = next(x["say"] for x in planned.build_plan(engine, "I walk with them", [hanged])
               if x["key"] == "fact1")
    assert say.endswith('Kesst Vayr is the player\'s character: "you" in every sentence, '
                        'never "he", "she" or "they".'), say
    other = Outcome("", "say", actor="c1", tell="the smith speaks, to the effect that hm.")
    say = next(x["say"] for x in planned.build_plan(engine, "hello", [other])
               if x["key"] == "fact1")
    assert "player's character" not in say


# --- 6. a fight the player's side lost is not "over" ----------------------------------------

@pytest.fixture
def robbed(tmp_path):
    """The player and two robbers, one side each: the player falling leaves only the
    robbers' side standing."""
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        for ref in [r for r in c.scene.actors if r != "pc"]:
            c.scene.depart(ref)
        for ref, name in (("c1", "the robber"), ("c2", "the second robber")):
            foe = instantiate("thug", scene=c.scene, name=name)
            foe.ref = ref
            c.scene.add(foe)
        e = c.engine()
        e.run(e.validate([{"op": "begin_encounter", "params": {
            "sides": {"party": ["pc"], "robbers": ["c1", "c2"]}}}], origin="author:test"))
        yield c
        cm._LIVE.clear()


class _Idle:
    engine = None

    def npc_turn(self, ref, **_k):
        return TurnPlan(narration="", intents=[])

    def narrate_outcome(self, *a, **k):
        return "", None


def test_the_player_down_with_the_robbers_standing_is_a_fight_lost_not_over(
        robbed, monkeypatch):
    """"The fight is over." was printed under a wizard lying dying with both robbers on
    their feet (2 errors scored on the rerun, 3 of 14 spell turns). `sides_standing() <= 1`
    ended the fight whichever side had fallen. Said as lost, with who stands over them,
    and the fight left for the downed door, which bleeds them round by round and ends it
    when they are stable."""
    from play import views

    c = robbed
    monkeypatch.setattr(views, "_log_mentions", lambda c, agent: None)
    pc = c.scene.pc()
    pc.hp = -2
    pc.apply_hp_state()
    views._run_npc_turns(c, _Idle())
    said = [b.get("text", "") for b in c.transcript]
    assert not any(t.startswith("The fight is over") for t in said), said[-3:]
    assert ("Nobody on your side is left standing, and the fight is lost: the robber and "
            "the second robber stand over you.") in said, said[-3:]
    assert c.scene.in_encounter, "the downed door ends it, by the rules"


def test_the_other_side_down_is_still_the_fight_over(robbed, monkeypatch):
    from play import views

    c = robbed
    monkeypatch.setattr(views, "_log_mentions", lambda c, agent: None)
    for ref in ("c1", "c2"):
        foe = c.scene.actors[ref]
        foe.hp = -20
        foe.apply_hp_state()
    views._run_npc_turns(c, _Idle())
    assert any(b.get("text", "").startswith("The fight is over") for b in c.transcript)
    assert not c.scene.in_encounter


def test_a_caster_struck_down_by_the_provoked_blow_loses_the_spell():
    """The same rerun: the robber's attack of opportunity left the wizard "unconscious and
    dying", and the cast's tell went on "holds Burning Hands together (struck for 13 while
    casting): concentration 24 against DC 24 … the robber takes 2 fire"."""
    w = tc.wizard(level=1, prepared={"burning-hands": 2}, book=("burning-hands",))
    _s, e = tc.table(w)
    w.hp = -2
    w.apply_hp_state()
    intent = e.validate([{"op": "cast", "actor": "pc", "because": "t",
                          "params": {"spell": "burning-hands", "at": "c1"}}])[0]
    intent.params["struck_from"] = 9
    from rules import spells as spells_mod

    spell = spells_mod.get("burning-hands")
    lost = e._concentrate(intent, w, spell, 1, {"rolls": [], "tells": []}, "1")
    assert lost is not None and "is struck down before it is cast" in lost.tell, lost
    assert not lost.rolls, "no concentration check is rolled for a caster who cannot act"


# --- 7. a manoeuvre that rides a hit is on the blow -----------------------------------------

def test_a_trip_that_rides_the_bite_is_a_fact_of_the_blow():
    """"Borin Achereth is knocked prone" was never told on 2 of 7 rerun runs: the wolf's
    trip was in the act's tells, which the enemy turn's second blow slot never sees
    (`turn_plan`), and the bite's facts said nothing of it."""
    from tests.test_attack_riders import _fight, _full_attack

    for seed in range(1, 40):
        engine, pc, wolf = _fight("wolf", seed)
        outs = _full_attack(engine, wolf)
        if pc.has_state("state.position.prone"):
            break
    else:
        pytest.fail("no seed tripped the player")
    blow = next(b for o in outs for b in (o.blows or []) if b.get("then"))
    assert any("trip takes" in t for t in blow["then"]), blow
    facts = planned.blow_facts(outs, engine, said={})
    hit = next(f for f in facts if "then " in f)
    assert "then the wolf's trip takes: you are knocked prone" in hit, hit


def test_a_bloodied_band_is_never_slowing():
    """"hurt and slowing" came back "leaving you reeling and slowed" (rerun, shoot): slowed
    is a condition the engine did not apply."""
    assert not any("slow" in w for pool in planned._LEFT.values() for w in pool)


# --- 8. a creature's turn is its own; a beast dies as a beast -------------------------------

def test_an_actorless_intent_on_a_creatures_turn_is_the_creatures():
    """A creature's `use_ability` came with `actor: null` and was resolved as the PLAYER's
    ("<the player> has no ability called Booming Voice")."""
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    raw = [{"op": "use_ability", "params": {"ability": "booming voice"}},
           {"op": "use_ability", "params": {"ability": "x", "actor": ""}},
           {"op": "attack", "actor": "c3", "target": "pc"}]
    out = _owned_by(raw, "c3", s)
    assert [r["actor"] for r in out] == ["c3", "c3", "c3"]
    assert out[1]["params"]["actor"] == "c3"
    with pytest.raises(IntentError, match="names the player"):
        _owned_by([{"op": "attack", "actor": "pc", "target": "c1"}], "c3", s)


def test_a_beast_dies_in_a_beasts_words_chosen_by_its_type():
    """"The wolf staggers two steps, hands full of it, and sit down against nothing and
    are dead": a humanoid line for a wolf, its second verb agreeing with the pronoun."""
    s = Scene(location_id="5bbd0c40345f")
    wolf = s.add(instantiate("wolf", scene=s))
    thug = s.add(instantiate("thug", scene=s, name="the thug"))
    assert states.is_beast(wolf) and not states.is_beast(thug)
    for margin in (0, 6, 30):
        line = narration.death_line({"name": "wolf", "margin": margin, "hp_max": 13,
                                     "family": "slashing", "body": "beast",
                                     "subj": "they", "obj": "them", "poss": "their"}, {})
        assert "hand" not in line and "throat" not in line and "knees" not in line, line
        assert narration.death_on_the_page(line, "wolf"), line
    fixed = narration._fill(narration._DEATHS["slashing"]["barely"][0], "the bandit",
                            "they", "them", "their")
    assert "staggers two steps, hands full of it, and sits down against nothing and is " \
           "dead" in fixed, fixed
    inverted = narration._fill(narration._DEATHS["piercing"]["overkill"][2], "the bandit",
                               "they", "them", "their")
    assert "so do they" in inverted, inverted


# --- 9. a declared shot rolled in the same batch is a blow, not a declaration ---------------

def test_a_shot_joined_and_struck_in_one_batch_is_told_as_struck():
    """"I shoot the wolf" joined the fight and hit in the same batch; the slot was told
    "nobody moves, no blow lands and nobody is hurt yet" and the joined tell "Nothing has
    landed yet — the first blow is still to be struck", and the page read "You hit the wolf
    with the shortbow … before the first strike" (3 errors, unchanged by round 1)."""
    from tests.test_the_opening_throw import THROW

    s = Scene(location_id="5bbd0c40345f")
    pc = load_pc("fixtures/pc-kesst.json")
    s.add(pc)
    s.add(instantiate("thug", scene=s, name="woman"))
    pc.goods["hairball"] = 1
    e = Engine(s, Dice(seed=5))
    first = e.run(e.validate([THROW]))
    joined = first.outcomes[0]
    # With its article, as every tell leaves the engine (`Engine._articled`): the bench's
    # first run of this read "squares off against wolf".
    assert joined.tell.startswith("Battle is joined: Kesst Vayr squares off against the "
                                  "woman."), joined.tell
    assert "Nothing has landed yet" not in joined.tell, joined.tell
    assert "The first blow is Kesst Vayr's, and it comes at once." in joined.tell
    res = e.resume(12)
    outs = res.outcomes
    blow = next(o for o in outs if o.op == "attack" and o.blows)
    slots = planned.build_plan(e, "I hurl the hairball at her", [joined, blow])
    say = next(x["say"] for x in slots if x["key"] == "fact1")
    assert "THE BLOW" in say and "no blow lands" not in say, say


def test_a_fight_only_declared_is_still_the_squaring_up():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    foe = s.add(instantiate("thug", scene=s, name="the bandit"))
    e = Engine(s, Dice(seed=3))
    joined = Outcome("i1", "attack", actor="pc",
                     tell="Battle is joined: Kesst Vayr squares off against the bandit. "
                          "Nothing has landed yet — the first blow is still to be struck.",
                     effects=[{"kind": "battle_joined", "ref": "pc", "target": foe.ref}])
    say = next(x["say"] for x in planned.build_plan(e, "I punch the bandit", [joined])
               if x["key"] == "fact1")
    assert "no blow lands" in say and "THE BLOW" not in say

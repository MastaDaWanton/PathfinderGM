"""The robbers in the warrens: what winning a fight does, and one answer for "hostile".

The owner's report, 2026-10-04: "the robber beat me up time passed and an hour later they
are still in the scene in the same place labeled as not hostile on the map but the scene
says the second robber is hostile. its all over the place."

Measured on the save (13 turns, the "Trouble in the lane" opening): the player struck the
second robber once; the second robber's natural 20 was confirmed at 17 against AC 17 only
by a +2 "flanking with the basket carrier" — the robbers' own victim, on no side — and the
player went to -2. "The fight is over." Continue: the bleeding stopped, an hour passed, and
the engine printed "Whoever was standing over you has gone." Nobody had gone. One hour
after the fight:

  * the panel read "the robber c2 16/16" with no attitude, and "the second robber c3 16/16
    · Hostile" — only the robber the player had HIT was on the attitude track;
  * the map painted no token red: it read `Scene.sides`, which the fight's end empties;
  * the suggestions still offered "I focus on the first robber";
  * the player's 30 gp were still in the player's purse, both robbers on the squares they
    had fought from, and the turn log held not one entry for the bleeding or the hour.

These rebuild that scene from the measured shape — the same templates, names, sides and
purse; none of the owner's save is in the repository (tests/replays is gitignored).
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from play import downed
from rules import attitude, defeat, grid as gridmod, position, residency
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

WARRENS = "5bbd0c40345f~urban:the-warrens"


def _lane(seed=3):
    """The opening's people: the player, the basket carrier who knows them, two robbers,
    and the fight the opening declares between "party" and "robbers"."""
    s = Scene(location_id="5bbd0c40345f")
    s.stand(WARRENS)
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    pc.purse = {"gp": 30}
    carrier = s.add(instantiate("commoner-outlaw", scene=s, name="the basket carrier"))
    robber = s.add(instantiate("street-thug", scene=s, name="the robber"))
    second = s.add(instantiate("street-thug", scene=s, name="the second robber"))
    e = Engine(s, Dice(seed=seed))
    # Friendly through the one applicator, as the background's "knows you" lands it.
    e.settle_attitude(carrier, "friendly", None, "background:forager")
    e.run(e.validate([{"op": "begin_encounter", "because": "the start: trouble-in-the-lane",
                       "params": {"sides": {"party": [pc.ref],
                                            "robbers": [robber.ref, second.ref]}}}]))
    return s, e, pc, carrier, robber, second


def _beaten(s, pc):
    """The player at -2 and stabilised, the fight over — where the Continue found them."""
    pc.hp = -2
    pc.apply_hp_state()
    pc.remove_condition("dying")
    pc.add_condition("stable")
    s.end_encounter()


class _Campaign:
    def __init__(self, scene, engine):
        self.scene, self._engine = scene, engine

    def engine(self):
        return self._engine


def test_both_robbers_are_hostile_from_the_batch_that_drew_the_fight():
    """Measured: "the robber c2 16/16" with no attitude beside it while "the second robber
    c3 16/16 · Hostile" — the track was only ever written by HARM, and the player had hit
    only the second robber. The first, cudgel up and coming on, was indifferent to the
    brief, the panel and every rule that asks it. Both are on the side against the
    player, so both are hostile, from the batch that declared the fight."""
    s, e, pc, carrier, robber, second = _lane()
    assert attitude.of(robber) == attitude.HOSTILE
    assert attitude.of(second) == attitude.HOSTILE
    # The basket carrier is on no side and stays where her history put her.
    assert attitude.of(carrier) == "friendly"


def test_the_map_the_panel_and_the_track_agree_during_and_after_the_fight():
    """Measured one hour after the fight: the map painted no token red (it read the
    fight's sides, which `end_encounter` empties), the panel called one robber Hostile and
    said nothing of the other, the brief told the narrator the second robber was hostile.
    Three surfaces, three sources. Now one: `attitude.of`, read by `attitude.stance` for
    the map and `attitude.word_for_panel` for the panel."""
    from play.views import _shown_conditions

    s, e, pc, carrier, robber, second = _lane()
    for when in ("in the fight", "after it"):
        for r in (robber, second):
            assert attitude.stance(s, r) == "foe", f"{r.name}, {when}"
            assert "Hostile" in _shown_conditions(r), f"{r.name}, {when}"
        assert attitude.stance(s, carrier) == "", when
        assert _shown_conditions(carrier).count("Friendly") == 1, when
        assert attitude.stance(s, pc) == "pc"
        s.end_encounter()
    assert not s.sides, "the fight is over and its sides with it — the track is not"


def test_a_companion_on_a_side_named_party_is_an_ally_not_a_foe():
    """The browser decided "ally" by the side's NAME being "pc" or "you"; the opening's
    fights call the player's side "party", so anybody beside the player there was painted
    red. Asked of the side the player is on, whatever it is called."""
    s, e, pc, carrier, robber, second = _lane()
    s.sides["party"].append(carrier.ref)
    assert attitude.stance(s, carrier) == "ally"


def test_a_bystander_does_not_flank():
    """Measured: the second robber's natural 20 was confirmed at 17 against AC 17 because
    of +2 "flanking with the basket carrier" — the robbers' victim, pressed to the wall and
    on no side — and the confirmed critical put the player at -2. A creature in none of a
    fight's declared sides is helping nobody; one on the attacker's side still flanks."""
    s, e, pc, carrier, robber, second = _lane()
    s.grid = gridmod.Grid(12, 12)
    s.positions.update({pc.ref: (5, 5), second.ref: (5, 4), carrier.ref: (5, 6),
                        robber.ref: (0, 0)})
    assert position.flanking_with(s, second, pc) == ""
    s.positions.update({carrier.ref: (0, 0), robber.ref: (5, 6)})
    assert position.flanking_with(s, second, pc) == "the robber"


def test_the_winners_rob_the_player_and_go_before_they_come_round():
    """Measured: "You come round about an hour later ... Whoever was standing over you has
    gone." — and both robbers stood on their squares, the 30 gp in the player's purse. The
    winners now act on it while the player lies there (rules/defeat.py): one robber takes
    a share of the coin into his own purse — three quarters for two robbers since the
    owner's ruling of 2026-10-05, the whole purse before it, and the rest of that ruling is
    tests/test_robbed_retrieval_quest.py — both leave through `Scene.move` to somewhere
    off stage in the same town, and the sentence about them is built from what they did."""
    s, e, pc, carrier, robber, second = _lane()
    _beaten(s, pc)
    out = downed.resolve(_Campaign(s, e))
    text = " ".join(out.lines)
    assert out.playable and pc.hp == 1
    assert "Whoever was standing over you" not in text
    assert "The robber took 22 of your 30 gold pieces, and your rapier." in out.lines
    assert "The robber and the second robber have gone." in out.lines
    assert pc.purse == {"gp": 8}
    assert robber.purse.get("gp", 0) >= 22, "the coin is in his purse, not out of existence"
    # Gone from the room, still in the campaign: the people who did it.
    assert robber.ref not in s.actors and second.ref not in s.actors
    assert residency.is_offstage(robber.at) and residency.is_offstage(second.at)
    assert robber.ref in s.people and second.ref in s.people
    # The basket carrier was nobody's winner; she is still here.
    assert carrier.ref in s.actors
    assert {x["kind"] for x in out.effects} == {"took", "left", "quest"}


def test_nobody_standing_over_the_player_means_no_sentence_about_them():
    """The old line claimed somebody had gone whether or not anybody had been there."""
    s, e, pc, carrier, robber, second = _lane()
    s.remove(robber.ref)
    s.remove(second.ref)
    _beaten(s, pc)
    out = downed.resolve(_Campaign(s, e))
    assert not any("gone" in line for line in out.lines), out.lines
    assert pc.purse == {"gp": 30}


def test_the_law_does_not_pocket_the_coin():
    """A robber robs; the watch arrests rather than pockets, and a wolf has no purse. Only
    a person who is not the law takes the coin; everyone standing over the player goes."""
    s, e, pc, carrier, robber, second = _lane()
    s.remove(robber.ref)
    s.remove(second.ref)
    watch = s.add(instantiate("watchman", scene=s, name="the watchman"))
    from rules import states
    from rules.activeeffect import ActiveEffect

    if not watch.has_state(states.GUARD):
        watch.apply_effect(ActiveEffect(name="guard", kind="role", key="role-guard",
                                        source="test", duration="until-dismissed",
                                        tags=(states.GUARD,)))
    e.settle_attitude(watch, attitude.HOSTILE, None, "test")
    _beaten(s, pc)
    out = downed.resolve(_Campaign(s, e))
    assert pc.purse == {"gp": 30}
    assert "The watchman has gone." in out.lines


def test_a_blow_makes_the_fights_hostility_a_grudge():
    """The fight's hostility is for a while (eight hours, `Engine.FIGHT_HOSTILE_MINUTES`),
    because a step with no end floors the standing regard and wiped provocation's
    bookkeeping off a baited brawler. Harm is still a grudge for good, as it always was:
    a blow on a robber already hostile from the fight makes it permanent."""
    s, e, pc, carrier, robber, second = _lane()
    assert not attitude._hostile_for_good(second)
    attitude.harmed(e, second, pc, "attack:club", seen=True)
    assert attitude._hostile_for_good(second)
    assert not attitude._hostile_for_good(robber)
    s.advance(Engine.FIGHT_HOSTILE_MINUTES + 10)
    assert attitude.of(second) == attitude.HOSTILE, "struck: a grudge"
    assert attitude.of(robber) != attitude.HOSTILE, "only fought: it cooled"


def test_the_aftermath_is_on_the_turn_log_and_the_stale_offers_go(tmp_path):
    """Measured on the save: the bleeding, the hour and the wake-up are in the transcript
    and in not one turn-log entry, and an hour after the robbers won the offers still read
    "I focus on the first robber". The Continue that carries a downed player forward now
    logs what it did and clears the offers written for the fight."""
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        from play import campaign as cm
        from play import concurrency

        cm._LIVE.clear()
        concurrency.reset_for_tests()
        # The campaign the table plays, the one `/api/say` reads.
        c = cm.current()
        s = c.scene
        for r in [r for r, a in list(s.actors.items()) if not a.is_pc]:
            s.remove(r)
        pc = s.pc()
        pc.purse = {"gp": 30}
        robber = s.add(instantiate("street-thug", scene=s, name="the robber"))
        second = s.add(instantiate("street-thug", scene=s, name="the second robber"))
        e = c.engine()
        e.run(e.validate([{"op": "begin_encounter", "because": "test",
                           "params": {"sides": {"party": [pc.ref],
                                                "robbers": [robber.ref, second.ref]}}}]))
        _beaten(s, pc)
        c.suggestions = ["I focus on the first robber", "I move to help the basket carrier"]
        c.save()
        r = Client().post("/api/say", data=json.dumps({"text": "…", "carry_on": True}),
                          content_type="application/json")
        assert r.status_code == 200, r.content[:300]
        body = r.json()
        assert body["suggestions"] == []
        said = " ".join(b["text"] for b in body["transcript"][-4:])
        assert "The robber took" in said and "have gone" in said
        assert "Get back what the robber and the second robber took" in said
        names = {a["name"]: a for a in body["scene"]["actors"]}
        assert "the robber" not in names and "the second robber" not in names
        row = next(x for x in reversed(c.turn_log) if x.get("kind") == "downed")
        assert {x["kind"] for x in row["effects"]} == {"took", "left", "quest"}
        cm._LIVE.clear()

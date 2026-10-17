"""A creature's blow at the player, shown on the player's own beat, before its turn.

Measured live 2026-10-17 (integration branch, free narrator, gemma-4-12B, the inn fight,
round 4): the player's beat — "You strike the one behind the bar with the dagger for 2
piercing" — went on "He lunges forward, swinging the heavy sap in a desperate, wide arc. The
weight of the club whistles through the air, and the sheer desperation in his swing sends it
toward your shoulder", and shipped. The barkeep's own turn, rolled after it, swung the sap
again. No reader asked: the struck-with question reads a creature's blows only on its own
turn, and the plan door's regex (`judgement.attacked_by`) did not read "swinging the heavy
sap" as a blow.

Now, on the player's beat in a fight, a call of its own asks who the page shows striking or
swinging at the player (people codes); code compares each named person with the engine's
own attacks this beat (`Facts.struck_by`), and a mismatch is `beat-struck-at-early` — cut,
never rewritten, after a second read of WHO the sentence shows swinging at the player.

Measured on 59 player-turn fight beats (41 shipped from the scratch saves, 18 drafts in
tests/replay; none with a creature attack resolved on the beat), gemma-4-12B x2: the same 7
beats alarmed both runs, 9 sentences asked per run, 8 kept, 1 refuted (a shopkeeper
"clawing at your sleeve"). Every kept sentence is a blow thrown at the player — both live
round-4 sentences, a raider's blade "aimed at your chest", a blade "missing your shoulder by
a hair's breadth", a fist "trailing a blur of motion toward your jaw", two grabs to pin or
seize. The wind-ups on the same beats were spared: "the heavy weight of his club is poised
for a swing", "closing the distance behind you, the steel of his blade held in a steady
grip", "moving toward you", "stumbling toward you". 0 false cuts.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from gm import agent as agent_mod
from gm import beat_verify as bv
from gm.checks import BeatContext, beat_verified

LUNGE = "He lunges forward, swinging the heavy sap in a desperate, wide arc."
WHISTLES = ("The weight of the club whistles through the air, and the sheer desperation in "
            "his swing sends it toward your shoulder, a frantic arc of wood and motion.")
BEAT = ("You strike the one behind the bar with the dagger for 2 piercing. He is reeling, "
        "his movements sluggish from the shock of the steel. " + LUNGE + " " + WHISTLES
        + " What do you do?")
DAGGER = {"intent_id": "i1", "op": "attack", "status": "resolved", "actor": "pc",
          "rolls": [{"label": "Attack with dagger", "visibility": "player"}],
          "blows": [{"result": "hit", "weapon": "dagger"}],
          "effects": [{"ref": "c8", "kind": "damage", "amount": 2}],
          "tell": "Kesst Vayr hits the one behind the bar with the dagger for 2 piercing."}


class _Reply:
    def __init__(self, obj):
        self.text = json.dumps(obj)
        self.seconds, self.model = 0.0, "stub"

    def json(self):
        return json.loads(self.text)


def _ctx(door="turn", acting="", fight=True, intimate=False):
    return SimpleNamespace(door=door, acting=acting, intimate=intimate,
                           scene=SimpleNamespace(in_encounter=fight))


PEOPLE = (bv.Person(ref="pc", name="Kesst Vayr", pc=True),
          bv.Person(ref="c8", name="the one behind the bar", what="barkeep"),
          bv.Person(ref="c6", name="the guard", here=False))


def _facts(outcomes=(DAGGER,), door="turn"):
    got = bv._struck_by_of(_ctx(door), outcomes, SimpleNamespace(ref="pc"),
                           _ctx(door).scene)
    return bv.Facts(start="the inn", end="the inn", places=("the inn",), people=PEOPLE,
                    in_fight=True, outcomes=tuple(outcomes), **got)


def test_asked_only_on_the_players_own_beat_in_a_fight():
    pc = SimpleNamespace(ref="pc")
    assert bv._struck_by_of(_ctx(), (DAGGER,), pc, _ctx().scene) == {
        "at_you": True, "struck_by": ()}
    assert bv._struck_by_of(_ctx("outcome"), (DAGGER,), pc, _ctx().scene)["at_you"]
    # A creature's own turn, the plan door (nothing resolved yet), out of a fight, and an
    # intimate scene are not asked.
    for ctx in (_ctx(acting="c8"), _ctx("plan"), _ctx(fight=False), _ctx(intimate=True)):
        assert bv._struck_by_of(ctx, (DAGGER,), pc, ctx.scene) == {}


def test_a_blow_the_engine_resolved_this_beat_is_somebodys_own():
    """An attack of opportunity on the player's move is a creature's blow on the player's
    beat that the dice threw: its maker is in `struck_by`, and never judged."""
    aoo = {"op": "attack", "status": "resolved", "actor": "c8",
           "rolls": [{"label": "Attack with sap", "visibility": "hidden"}]}
    facts = _facts((DAGGER, aoo))
    assert facts.struck_by == ("c8",)
    c = bv.Claim("at_you", {"who": "c8"}, "swinging the heavy sap", LUNGE, True)
    assert bv.diff([c], facts) == []
    # A harm outcome nobody stamped and the player did not roll: whose blow it was is
    # unknown, so nothing is asked rather than judged wrongly.
    anon = {"op": "attack", "status": "resolved", "rolls": [{"visibility": "hidden"}]}
    assert bv._struck_by_of(_ctx(), (DAGGER, anon), SimpleNamespace(ref="pc"),
                            _ctx().scene) == {}


def test_the_live_round_four_swing_is_a_contradiction():
    facts = _facts()
    asked = []

    def chat(messages, *a, schema=None, **k):
        props = (schema or {}).get("properties", {})
        asked.append(next(iter(props), ""))
        if "at_you" in props:
            assert props["at_you"]["items"]["properties"]["who"]["enum"] == [
                "c8", bv.NEW_PERSON]
            return _Reply({"at_you": [
                {"who": "c8", "quote": "He lunges forward, swinging the heavy sap"},
                {"who": "c8", "quote": "sends it toward your shoulder"}]})
        if "struck_with" in props:
            return _Reply({"struck_with": []})
        return _Reply({"player_ends_at": {"place": "the inn", "quote": ""},
                       "changed_hands": [], "trades": [], "harmed": [], "arrived": [],
                       "left": [], "time_of_day": [], "conditions": [], "setting": []})

    reading = bv.read(BEAT, facts, model="stub", chat=chat)
    assert "at_you" in asked
    found = bv.diff(reading.claims, facts, BEAT)
    assert [(d.category, d.sentence) for d in found] == [("at_you", LUNGE),
                                                         ("at_you", WHISTLES)]
    assert "has not struck at you" in found[0].fact and found[0].ref == "c8"


def test_nobody_listed_the_player_and_the_away_are_not_judged_here():
    facts = _facts()
    for who in (bv.NEW_PERSON, "pc", "c6"):
        c = bv.Claim("at_you", {"who": who}, "x y z", LUNGE, True)
        assert bv.diff([c], facts) == [], who


def test_the_second_read_asks_who_swings_and_spares_a_wind_up():
    facts = _facts()
    d = bv.diff([bv.Claim("at_you", {"who": "c8"}, "x y z", LUNGE, True)], facts)[0]
    seen = []

    def chat(messages, *a, answer=None, **k):
        seen.append(messages[-1]["content"])
        return _Reply({"who": answer})

    for answer, kept in ((["c8"], True), (["nobody"], False), ([bv.NEW_PERSON], False)):
        held, _r, _s = bv.confirm([d], BEAT, facts, model="stub",
                                  chat=lambda *a, answer=answer, **k: chat(*a, answer=answer,
                                                                           **k))
        assert (d in held) is kept, answer
    # The passage before it, for who "he" is, and the wind-up named as what it is not.
    assert "He is reeling" in seen[0] and "not only raising or drawing a weapon" in seen[0]


def test_the_kind_is_cut_only_and_the_backstop_cuts_it(monkeypatch):
    """No one-sentence rewrite: re-read alone, "He lunges forward, swinging the heavy sap"
    is nobody's swing (the hole measured on the joined turn), and no engine line can stand
    in for a blow nothing threw."""
    from gm import checks
    from gm.narration import Finding

    assert beat_verified._KIND["at_you"] == ("beat-struck-at-early", 3)
    assert "beat-struck-at-early" in beat_verified.CUT_ONLY
    facts = _facts()
    d = bv.diff([bv.Claim("at_you", {"who": "c8"}, "x y z", LUNGE, True)], facts)[0]
    monkeypatch.setattr(beat_verified, "discrepancies", lambda ctx: [d])
    ctx = BeatContext(door="turn", text=BEAT, player_text="", engine=None, scene=None,
                      world=None, location=None, reading=None, outcomes=(), tells=(),
                      said=(), attribution=None, brief="", brief_facts={}, pull=None,
                      was_at="", acting="", turn=0)
    out, notes = beat_verified.backstop(ctx, BEAT, [])
    assert LUNGE not in out and "You strike the one behind the bar" in out and notes

    def no_model(*a, **k):
        raise AssertionError("a cut-only kind was sent to the model")

    monkeypatch.setattr(agent_mod.client, "chat", no_model)
    f = Finding("beat-struck-at-early", "x", "y", weight=3, sentences=(LUNGE,))
    monkeypatch.setattr(beat_verified, "find", lambda c: [f] if LUNGE in c.text else [])
    monkeypatch.setattr(beat_verified, "backstop",
                        lambda c, text, found: (text.replace(LUNGE, "").strip(), ["cut"]))
    monkeypatch.setattr(checks, "owner_of", lambda kind: beat_verified)
    agent = SimpleNamespace(engine=SimpleNamespace(scene=SimpleNamespace(
        pc=lambda: None, actors={})), _TRUTH_CALLS=3)
    out, _notes, attempts = agent_mod.GMAgent._repair_sentences(agent, BEAT, [f], ctx)
    assert LUNGE not in out and attempts == []

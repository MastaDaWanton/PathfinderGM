"""A blow of the player's landed on the turn the fight was only joined.

Measured live 2026-10-17 on the integration branch (free narrator, gemma-4-12B): "draw my
dagger and stab the one behind the bar" joined battle and rolled nothing ("Nothing has
landed yet — the first blow is still to be struck"). The page shipped "He bellows, a raw
sound of defiance, and recoils from your strike": the claims scrubber had cut the stab
sentence before it, the harm repair turned "pain" into "defiance", and the re-read of that
one sentence named "someone not listed", which is never judged. Nothing asked whether a
blow of the player's had landed at all. The struck-with question is now asked on a joined
turn too, and any blow of the player's it finds is judged against the joined tell.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from gm import beat_verify as bv
from gm.checks import beat_verified

class _Reply:
    def __init__(self, text):
        self.text, self.seconds, self.model = text, 0.0, "stub"

    def json(self):
        return json.loads(self.text)


# --- 3. a blow landed before any blow was rolled ----------------------------------------------

JOINED = {"intent_id": "i1", "op": "attack", "status": "resolved", "rolls": [],
          "effects": [{"ref": "pc", "kind": "battle_joined", "target": "c8"}],
          "tell": "Battle is joined: Kesst Vayr squares off against the one behind the bar. "
                  "Nothing has landed yet — the first blow is still to be struck.",
          "actor": "pc"}
SHIPPED_150 = ("He bellows, a raw sound of defiance, and recoils from your strike, the smell of "
               "iron and old wood filling the space between you.")


class _PC:
    ref = "pc"
    weapons = {"rapier": {}, "dagger": {}}

    def weapon(self, k):
        return {"name": k}


def _joined_facts():
    got = bv._blows_of(SimpleNamespace(acting=""), (JOINED,), _PC())
    return bv.Facts(start="the inn", end="the inn", places=("the inn",), in_fight=True,
                    outcomes=(JOINED,), **got)


def test_a_joined_attack_asks_the_swing_question():
    facts = _joined_facts()
    assert facts.joined.startswith("Battle is joined") and facts.blows == ()
    assert facts.swings and "dagger" in facts.arms
    asked = []

    def chat(messages, *a, schema=None, **k):
        props = (schema or {}).get("properties", {})
        asked.append(next(iter(props), ""))
        if "struck_with" in props:
            return _Reply(json.dumps({"struck_with": [
                {"weapon": "not shown", "quote": "recoils from your strike"}]}))
        return _Reply(json.dumps({"player_ends_at": {"place": "the inn", "quote": ""},
                                  "changed_hands": [], "trades": [], "harmed": [],
                                  "arrived": [], "left": [], "time_of_day": [],
                                  "conditions": [], "setting": []}))

    reading = bv.read(SHIPPED_150, facts, model="stub", chat=chat)
    assert "struck_with" in asked
    found = bv.diff(reading.claims, facts, SHIPPED_150)
    assert [d.category for d in found] == ["early"]
    assert found[0].sentence == SHIPPED_150
    assert "first blow is still to come" in found[0].fact
    assert found[0].line == JOINED["tell"]


def test_the_early_blow_is_asked_of_its_arrival_and_kept_only_on_a_yes():
    """Measured on 37 joined-turn beats (19 shipped from scratch saves, 18 recorded
    drafts), gemma-4-12B x2: the first read alarmed on 7 clean beats' wind-ups ("You
    lunge forward, your fist aimed directly at the guard's face", "You draw your rapier
    and strike at the cutpurse"); the second read refuted all 14 asks, and kept 9 of the
    10 beats that landed a blow."""
    facts = _joined_facts()
    c = bv.Claim("weapon", {"weapon": "not shown"}, "recoils from your strike",
                 SHIPPED_150, True)
    d = bv.diff([c], facts)[0]
    q = bv.question(d, facts)
    assert "already struck" in q and "not only drawn, raised, aimed" in q
    for answer, kept in (("yes", True), ("no", False)):
        held, _r, _s = bv.confirm([d], SHIPPED_150, facts, model="stub",
                                  chat=lambda *a, **k: _Reply(json.dumps({"answer": answer})))
        assert (d in held) is kept


def test_a_rolled_blow_is_never_early_and_the_backstop_puts_the_declaration_back():
    rolled = dict(JOINED, effects=[{"ref": "c8", "kind": "damage", "amount": 6}],
                  rolls=[{"label": "Attack with dagger", "visibility": "player"}],
                  blows=[{"result": "hit", "weapon": "dagger"}])
    got = bv._blows_of(SimpleNamespace(acting=""), (rolled,), _PC())
    assert got["joined"] == "" and got["blows"] == ("dagger",)
    facts = bv.Facts(start="", end="", places=(), **got)
    c = bv.Claim("weapon", {"weapon": "dagger"}, "x", "Your dagger bites.", True)
    assert bv.diff([c], facts) == []
    assert beat_verified._KIND["early"] == ("beat-swing-early", 3)
    assert "beat-swing-early" in beat_verified.KINDS

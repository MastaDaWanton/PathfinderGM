"""Somebody on their feet written down, whom the first read could not name.

Measured live 2026-10-17 on the integration branch (free narrator, gemma-4-12B): the dagger
left the one behind the bar at 12 of 23, and the beat said "He lets out a choked, wet grunt
… and he collapses into the counter". Nothing caught it. The truth pass read the beat before
the blow pass wrote the engine's line naming him, so it opened "The blade finds the gap in
his leather jerkin…", and the read back answered the collapse as `down` of "someone not
listed" — never judged. `contradicts-the-engine`'s regex links a sentence to a NAME, and the
name was not on the page either. The body-conditions call claimed no `prone`.

Replayed offline on that draft (gemma-4-12B x3): the first read still answers "someone not
listed", and the who-read (`beat_verify._felled_who`, the passage before and the turn's tells
for "he") named him 3 of 3 and the collapse was kept. Read with the blow line in front, the
first read names him itself (4 of 4).
"""
from __future__ import annotations

import json

from gm import beat_verify as bv
from gm.checks import beat_verified

COLLAPSE = ("He lets out a choked, wet grunt as the steel carves through muscle and hits bone, "
            "and he collapses into the counter, his weight shattering the wood.")
TEXT = "The blade finds the gap in his leather jerkin. " + COLLAPSE


class _Reply:
    def __init__(self, obj):
        self.text = json.dumps(obj)
        self.seconds, self.model = 0.0, "stub"

    def json(self):
        return json.loads(self.text)


def _facts(down=False):
    return bv.Facts(
        start="the inn", end="the inn", places=("the inn",), in_fight=True,
        people=(bv.Person("pc", "Kesst Vayr", pc=True),
                bv.Person("c8", "the one behind the bar", "barkeep", down=down)),
        outcomes=({"op": "attack", "status": "resolved",
                   "tell": "Kesst Vayr hits the one behind the bar with the dagger for 5 "
                           "piercing.",
                   "effects": [{"ref": "c8", "kind": "damage", "amount": 5}]},))


def _claim():
    return bv.Claim("harm", {"who": bv.NEW_PERSON, "how": "down"},
                    "he collapses into the counter", COLLAPSE, True)


def test_an_unnamed_felling_is_asked_who_and_kept_on_somebody_standing():
    bv.clear_cache()
    facts = _facts()
    found = bv.diff([_claim()], facts, TEXT)
    assert [d.category for d in found] == ["felled"] and found[0].fact == ""
    asked = []

    def chat(messages, *a, schema=None, **k):
        asked.append(messages[-1]["content"])
        return _Reply({"who": ["c8"]})

    held, refuted, _s = bv.confirm(found, TEXT, facts, model="stub", chat=chat)
    assert held == found and refuted == []
    assert held[0].ref == "c8"
    assert held[0].fact.startswith("the one behind the bar is not down: still on their feet")
    # The who-read is given the turn's tells, numbers off, and the passage before.
    assert "What the rules resolved this turn: Kesst Vayr hits the one behind the bar with " \
           "the dagger." in asked[0]
    assert "The blade finds the gap in his leather jerkin." in asked[0]
    assert "Not only staggers, stumbles, reels or steps back." in asked[0]
    # And a later diff of the same beat (the repair asks the member again) names him.
    again = bv.diff([_claim()], facts, TEXT)
    assert again[0].ref == "c8" and again[0].fact == held[0].fact
    assert beat_verified._KIND["felled"] == ("beat-harms", 3)


def test_nobody_named_or_somebody_already_down_is_no_contradiction():
    bv.clear_cache()
    facts = _facts()
    for who in ([bv.NEW_PERSON], [bv.NOBODY]):
        found = bv.diff([_claim()], facts, TEXT)
        held, refuted, _s = bv.confirm(found, TEXT, facts, model="stub",
                                       chat=lambda *a, who=who, **k: _Reply({"who": who}))
        assert held == [] and len(refuted) == 1
    # Named, but the engine holds him down already: the page is true.
    down = _facts(down=True)
    found = bv.diff([_claim()], down, TEXT)
    held, refuted, _s = bv.confirm(found, TEXT, down, model="stub",
                                   chat=lambda *a, **k: _Reply({"who": ["c8"]}))
    assert held == [] and len(refuted) == 1
    # A hurt "someone not listed" is not asked at all.
    hurt = bv.Claim("harm", {"who": bv.NEW_PERSON, "how": "hurt"}, "x", COLLAPSE, True)
    assert bv.diff([hurt], facts, TEXT) == []

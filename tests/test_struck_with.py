"""What the player's blows were struck with, read back and judged against `Outcome.blows`.

Measured live 2026-10-16 (scratch copy of the owner's data, Khalmorin market, gemma-4-12B):
"I grab a shard of the broken pot and stab him" — the engine refused the shard (nothing had
put one there) and rolled an unarmed strike, 5 non-lethal, the man unconscious; the page
wrote "The shard bites deep into the soft tissue of his shoulder, and the man's body
buckles." Nothing read what a blow was struck with. And the dice popup over that roll was
titled "Attack with unarmed strike" and subtitled "you use the shard to strike a desperate
blow" — the plan's reason, for a weapon never in hand.

Now, on a beat where the player struck (and only then), a model answers which weapon each
of the player's blows is shown struck with, from the weapons they carry, unarmed, what the
engine swung, "something else" and "not shown"; code compares that with the engine's own
`blows[...]["weapon"]`, and a mismatch is a `beat-struck-with` contradiction repaired
through the existing repair. The popup's subtitle on a blow is the engine's words.
"""
from __future__ import annotations

import json

from gm import beat_verify as bv
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from tests.beat_verify import gold as G


class _Reply:
    def __init__(self, obj):
        self.text = json.dumps(obj)
        self.seconds, self.model = 0.0, "stub"

    def json(self):
        return json.loads(self.text)


def _chat(answers):
    """Answers by what each call asks for (its schema's one property)."""
    asked = []

    def chat(messages, *a, schema=None, **k):
        props = (schema or {}).get("properties", {})
        asked.append(next(iter(props), ""))
        for key, value in answers.items():
            if key in props:
                return _Reply(value)
        return _Reply({"player_ends_at": {"place": "the market", "quote": ""},
                       "changed_hands": [], "trades": [], "harmed": [], "arrived": [],
                       "left": [], "time_of_day": [], "conditions": [], "setting": []})

    chat.asked = asked
    return chat


SHARD = G.by_id("sw-shard-on-a-punch")


def test_the_shard_on_an_unarmed_strike_is_a_contradiction_with_the_fix_named():
    facts = G.facts(SHARD)
    reading = bv.read(SHARD["text"], facts, model="stub", chat=_chat({"struck_with": {
        "struck_with": [{"weapon": "something else",
                         "quote": "The shard bites deep into the soft tissue of his shoulder"}]}}))
    found = [d for d in bv.diff(reading.claims, facts, SHARD["text"])
             if d.category == "weapon"]
    assert len(found) == 1
    assert "bare hands" in found[0].fact and "not with anything else" in found[0].fact
    assert found[0].sentence.startswith("The shard bites deep")


def test_the_right_weapon_and_not_shown_are_never_judged():
    facts = G.facts(G.by_id("sw-rapier-true"))
    for said in ("rapier", "not shown"):
        c = bv.Claim("weapon", {"weapon": said}, "x", "Your rapier darts in.", True)
        assert bv.diff([c], facts) == []
    c = bv.Claim("weapon", {"weapon": "dagger"}, "x", "You stab with the dagger.", True)
    assert [d.category for d in bv.diff([c], facts)] == ["weapon"]


def test_asked_only_on_a_beat_where_the_player_struck():
    """No blow of the player's: no struck-with call at all, and the first read is asked
    exactly what it was."""
    calm = G.by_id("sw-her-blow-only")
    facts = G.facts(dict(calm, blows=[], arms=[]))
    chat = _chat({})
    bv.read(calm["text"], facts, model="stub", chat=chat)
    assert "struck_with" not in chat.asked
    facts = G.facts(SHARD)
    chat = _chat({})
    bv.read(SHARD["text"], facts, model="stub", chat=chat)
    assert "struck_with" in chat.asked
    assert "struck_with" not in bv.schema(facts)["properties"], "a call of its own"


def test_the_second_read_keeps_only_a_weapon_that_is_not_the_engines():
    facts = G.facts(SHARD)
    c = bv.Claim("weapon", {"weapon": "something else"}, "The shard bites deep",
                 "The shard bites deep into the soft tissue of his shoulder.", True)
    d = bv.diff([c], facts)[0]
    for answer, kept in (("something else", True), ("unarmed strike", False),
                         ("not shown", False), ("rapier", True)):
        held, refuted, _ = bv.confirm([d], SHARD["text"], facts, model="stub",
                                      chat=_chat({"weapon": {"weapon": answer}}))
        assert (d in held) is kept, answer


def test_the_engines_blows_are_read_off_the_players_own_rolls():
    """An outcome carries no actor; the player's roll is the one made `visibility:
    player` (every non-PC roll is forced hidden), and an NPC's turn is its own door."""
    from types import SimpleNamespace

    pc = load_pc("fixtures/pc-kesst.json")
    mine = {"op": "attack", "status": "resolved", "blows": [
        {"result": "hit", "weapon": "unarmed strike"}],
        "rolls": [{"label": "Attack with unarmed strike", "visibility": "player"}]}
    theirs = {"op": "attack", "status": "resolved", "blows": [
        {"result": "miss", "weapon": "shortspear"}],
        "rolls": [{"label": "Attack with shortspear", "visibility": "hidden"}]}
    got = bv._blows_of(SimpleNamespace(acting=""), (mine, theirs), pc)
    assert got["blows"] == ("unarmed strike",)
    assert got["arms"] == ("rapier", "dagger", "unarmed strike")
    assert bv._blows_of(SimpleNamespace(acting="c4"), (mine,), pc) == {}


def test_the_finding_is_a_member_kind():
    from gm.checks import beat_verified

    assert beat_verified._KIND["weapon"] == ("beat-struck-with", 3)
    assert "beat-struck-with" in beat_verified.KINDS


# --- the popup's subtitle -------------------------------------------------------------------

def test_the_dice_popup_over_a_blow_says_what_is_rolled_not_the_plans_reason():
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    man = scene.add(instantiate("thug", scene=scene, name="the man"))
    engine = Engine(scene, Dice(seed=4))
    engine.run(engine.validate([{"op": "begin_encounter", "params": {
        "sides": {"pc": ["pc"], "them": [man.ref]}}}]))
    scene.turn = [r for r, _ in scene.initiative].index("pc")
    res = engine.run(engine.validate([{
        "op": "attack", "actor": "pc", "target": man.ref,
        "because": "you use the shard to strike a desperate blow",
        "params": {"weapon": "unarmed"}}]))
    asked = res.awaiting
    assert asked and asked["label"] == "Attack with unarmed strike"
    assert asked["because"] == "Kesst Vayr against the man"

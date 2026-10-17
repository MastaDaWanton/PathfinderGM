"""What a creature's blows were struck with, on its own turn, read back and judged.

Measured live 2026-10-17 (integration branch, free narrator, gemma-4-12B, the inn fight):
the barkeep's tell was "the one behind the bar's attack with the sap misses Kesst Vayr (7
against AC 15)", and the beat wrote "The tavern keeper swings the heavy crossbow with a
desperate, wide arc, but the heavy bolt whistles past your ear" — a crossbow his stat block
prints and the engine never fired. The next round's beat had him "fumbling with the
crossbow". The struck-with question read the player's blows only.

Now, on a creature's turn (the `outcome` door with `ctx.acting`), a call of its own asks
which weapon each of THAT creature's blows is shown struck with, from what it carries and
what its stat block prints; code compares the answer with `Outcome.blows[...]["weapon"]`,
and a mismatch is `beat-foe-struck-with` — cut, never rewritten (a rewritten sentence is
re-read alone and loses whose blow it is), with the engine's own line in its place.

Measured on 74 creature-turn beats (37 shipped from scratch saves, 37 recorded consequence
drafts in tests/replay), gemma-4-12B x2: 10 beats alarmed, the same 10 both runs, every one
kept by the second read; 9 true (the crossbow twice, a club told as a blade, a fist and a
bare arm, an unarmed commoner swinging a stool twice, a fist on a sap turn, a club told as
a shove), 1 false (a tentacle told as a vine, now spared for natural attacks). Missed: "The
blade strikes your temple" on a sap turn, read as "not shown".
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from gm import agent as agent_mod
from gm import beat_verify as bv
from gm.checks import beat_verified
from rules.bestiary import instantiate
from rules.engine import Scene
from rules.sheet import load_pc

TELL = "the one behind the bar's attack with the sap misses Kesst Vayr (7 against AC 15)."
CROSSBOW = ("The tavern keeper swings the heavy crossbow with a desperate, wide arc, but the "
            "heavy bolt whistles past your ear and thuds into the timber of a nearby stool.")
BEAT = CROSSBOW + " They scramble back, eyes wide with alarm."


class _Reply:
    def __init__(self, obj):
        self.text = json.dumps(obj)
        self.seconds, self.model = 0.0, "stub"

    def json(self):
        return json.loads(self.text)


def _scene():
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    bar = scene.add(instantiate("barkeep", scene=scene, name="the one behind the bar"))
    return scene, bar


def _outcome(ref):
    return {"intent_id": "i1", "op": "attack", "status": "resolved", "actor": ref,
            "rolls": [{"label": "Attack with sap", "visibility": "hidden"}],
            "blows": [{"result": "miss", "weapon": "sap", "how": "plain"}], "tell": TELL}


def _facts():
    scene, bar = _scene()
    got = bv._foe_blows_of(SimpleNamespace(acting=bar.ref), (_outcome(bar.ref),), scene)
    return bv.Facts(start="the inn", end="the inn", places=("the inn",), in_fight=True,
                    outcomes=(_outcome(bar.ref),), **got), bar


def test_the_creatures_blows_and_arms_come_off_the_engine():
    facts, bar = _facts()
    assert facts.foe == bar.ref and facts.foe_blows == ("sap",)
    # What the barkeep carries and prints: the crossbow is a code the reader can answer
    # with, so it can be judged.
    assert "sap" in facts.foe_arms and "dagger" in facts.foe_arms
    assert any("crossbow" in w for w in facts.foe_arms)
    assert bv.UNARMED in facts.foe_arms
    # The player's question is not asked on the creature's turn.
    assert facts.blows == () and not facts.swings


def test_the_crossbow_on_a_sap_turn_is_a_contradiction_the_sap_is_not():
    facts, bar = _facts()
    bow = next(w for w in facts.foe_arms if "crossbow" in w)
    asked = []

    def chat(messages, *a, schema=None, **k):
        props = (schema or {}).get("properties", {})
        asked.append(next(iter(props), ""))
        if "foe_struck_with" in props:
            return _Reply({"foe_struck_with": [
                {"weapon": bow, "quote": "The tavern keeper swings the heavy crossbow"}]})
        return _Reply({"player_ends_at": {"place": "the inn", "quote": ""},
                       "changed_hands": [], "trades": [], "harmed": [], "arrived": [],
                       "left": [], "time_of_day": [], "conditions": [], "setting": []})

    reading = bv.read(BEAT, facts, model="stub", chat=chat)
    assert "foe_struck_with" in asked and "struck_with" not in asked
    found = bv.diff(reading.claims, facts, BEAT)
    assert [d.category for d in found] == ["foe_weapon"]
    assert found[0].sentence == CROSSBOW and found[0].line == TELL
    assert "struck with the sap, not with the" in found[0].fact
    for said in ("sap", bv.NOT_SHOWN):
        c = bv.Claim("foe_weapon", {"weapon": said}, "x", CROSSBOW, True)
        assert bv.diff([c], facts) == []


def test_a_natural_attack_told_in_other_words_is_not_judged():
    """The one false alarm of ten on the recorded fight beats (gemma-4-12B x2): Zygomind's
    tentacle written as "the heavy vine strikes your ribs", read as "something else" both
    runs. A bite or a tentacle has no name the page must use; a listed weapon it did not
    swing is still judged."""
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(load_pc("fixtures/pc-kesst.json"))
    wolf = scene.add(instantiate("wolf", scene=scene, name="the wolf"))
    bite = dict(_outcome(wolf.ref), blows=[{"result": "hit", "weapon": "bite"}])
    got = bv._foe_blows_of(SimpleNamespace(acting=wolf.ref), (bite,), scene)
    assert got["foe_natural"] is True
    facts = bv.Facts(start="", end="", places=(), outcomes=(bite,), **got)
    vine = bv.Claim("foe_weapon", {"weapon": bv.OTHER_WEAPON}, "x",
                    "The wolf's jaws close on your calf.", True)
    assert bv.diff([vine], facts) == []
    facts, _bar = _facts()
    assert facts.foe_natural is False
    vine = bv.Claim("foe_weapon", {"weapon": bv.OTHER_WEAPON}, "x", CROSSBOW, True)
    assert [d.category for d in bv.diff([vine], facts)] == ["foe_weapon"]


def test_the_second_read_keeps_only_a_weapon_that_is_not_the_engines():
    facts, _bar = _facts()
    bow = next(w for w in facts.foe_arms if "crossbow" in w)
    d = bv.diff([bv.Claim("foe_weapon", {"weapon": bow}, "x", CROSSBOW, True)], facts)[0]
    for answer, kept in ((bow, True), ("sap", False), (bv.NOT_SHOWN, False),
                         (bv.OTHER_WEAPON, True)):
        held, _r, _s = bv.confirm([d], BEAT, facts, model="stub",
                                  chat=lambda *a, answer=answer, **k: _Reply({"weapon": answer}))
        assert (d in held) is kept, answer


def test_the_backstop_puts_the_engines_line_where_the_crossbow_was(monkeypatch):
    facts, _bar = _facts()
    d = bv.diff([bv.Claim("foe_weapon", {"weapon": "dagger"}, "x", CROSSBOW, True)], facts)[0]
    monkeypatch.setattr(beat_verified, "discrepancies", lambda ctx: [d])
    from gm.checks import BeatContext

    ctx = BeatContext(door="outcome", text=BEAT, player_text="", engine=None, scene=None,
                      world=None, location=None, reading=None, outcomes=(), tells=(),
                      said=(), attribution=None, brief="", brief_facts={}, pull=None,
                      was_at="", acting="", turn=0)
    out, notes = beat_verified.backstop(ctx, BEAT, [])
    assert out.startswith("The one behind the bar's attack with the sap misses Kesst Vayr.")
    assert "crossbow" not in out and "(7 against" not in out
    assert "They scramble back" in out and notes


def test_the_kind_is_cut_only(monkeypatch):
    """No one-sentence rewrite is asked for it: the rewritten sentence would be re-read
    alone, and alone "the heavy bolt whistles past your ear" is nobody's blow."""
    from gm import checks
    from gm.narration import Finding

    assert "beat-foe-struck-with" in beat_verified.CUT_ONLY
    assert beat_verified._KIND["foe_weapon"] == ("beat-foe-struck-with", 3)

    def no_model(*a, **k):
        raise AssertionError("a cut-only kind was sent to the model")

    monkeypatch.setattr(agent_mod.client, "chat", no_model)
    monkeypatch.setattr(beat_verified, "find",
                        lambda ctx: [f] if CROSSBOW in ctx.text else [])
    monkeypatch.setattr(beat_verified, "backstop",
                        lambda ctx, text, found: (text.replace(CROSSBOW, "").strip(), ["cut"]))
    monkeypatch.setattr(checks, "owner_of", lambda kind: beat_verified)
    agent = SimpleNamespace(engine=SimpleNamespace(scene=SimpleNamespace(
        pc=lambda: None, actors={})), _TRUTH_CALLS=3)
    f = Finding("beat-foe-struck-with", "x", "y", weight=3, sentences=(CROSSBOW,))
    from gm.checks import BeatContext

    ctx = BeatContext(door="outcome", text=BEAT, player_text="", engine=None, scene=None,
                      world=None, location=None, reading=None, outcomes=(), tells=(),
                      said=(), attribution=None, brief="", brief_facts={}, pull=None,
                      was_at="", acting="", turn=0)
    out, notes, attempts = agent_mod.GMAgent._repair_sentences(agent, BEAT, [f], ctx)
    assert "crossbow" not in out and attempts == []

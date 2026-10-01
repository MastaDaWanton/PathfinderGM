"""Taking a thing is not a boast about having it, and a lie is Bluff against a listener.

Item 5 of the 2026-09-30 playtest (docs/playtest-2026-09-30-findings.md). The owner played
Sam, a bonesetter wizard, and the room rolled a Bluff against him **four times** — turns 4,
5, 12 and 23 — at a flat DC 30 ("heroic"): 10, 18 and 7 against 30, the fourth unseen.
His note: "random Bluff check that seemed to do nothing and worse i didnt lie about
anything." Every one came from `judgement.inject_false_claim`, not the model:

    turn  4  "I take the herbs and use them on him"        -> "produce a herbs you do not have"
    turn  5  "... I'll take my payment for a job done ..."  -> "produce a payment ..."
    turn 12  "I'm a bit of a free spirit"                    -> an identity claim (spirit)
    turn 23  "I take the key and walk toward the curtain."  -> the same plan GAVE him the key

`_PRODUCE` read bare "take" as producing, its verbs had no subject anchor ("my hand on the
hilt" and "Lay on Hands on the fighter" both misfired when replayed), `_IDENTITY_HEAD`
matched any word of the predicate, and nothing passed the interpreter's reading — which
had already read `act: take` — into the check. `note_heat` then told the crowd it had
heard a delusion, and the prose mocked Sam for boasts he never made (beats 18, 25, 47).

And the DC: owner ruling B1, 2026-09-30, a spoken lie is opposed by the listener's Sense
Motive with the Core Rulebook's believability modifiers (CRB p.90; `rules/bluff.py`).
"""
from __future__ import annotations

import pytest

from gm import judgement
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Outcome, Scene
from rules.sheet import from_dict

# Sam's sheet as the save had it on 2026-09-30, the fields these detectors read: a level 1
# wizard with the bonesetter background, a shortbow in hand, a bo staff and arrows, and
# nothing in his goods but his clothes — the herbs (turn 4) and the key (turn 23) are taken
# out, because the replay asks what the sheet said BEFORE those turns gave them to him.
SAM = {
    "ref": "pc", "name": "Sam", "kind": "pc", "level": 1, "class": "wizard",
    "abilities": {"str": 10, "dex": 14, "con": 10, "int": 16, "wis": 12, "cha": 11},
    "ranks": {"bluff": 1, "sense motive": 1, "spellcraft": 1},
    "weapons": ["unarmed", "bo-staff", "shortbow", "arrows-20"],
    "equipped": "shortbow", "armour": "none", "race": "human",
    "background": "bonesetter",
    "background_ties": ["You learned it from Chitter Ashbourne, and were better at it "
                        "than expected."],
    "spellbook": ["burning-hands", "magic-missile", "shocking-grasp", "acid-splash",
                  "arcane-mark", "bleed"],
    "prepared": {"burning-hands": 1, "magic-missile": 1, "acid-splash": 1, "bleed": 1},
    "goods": {"scholar's outfit": 1}, "purse": {"gp": 37}, "gender": "man",
}

MEASURED = {
    4: "I take the herbs and use them on him",
    5: "\"he's all yours, I am done here, I'll take my payment for a job done. This man is "
       "yours to do with as you please.\"",
    12: "\"Thank you friend but I'm a bit of a free spirit, I plan to go outs ide the city "
        "and harvest herbs to sell tinctures to those who will buy them and to make some "
        "for my work as a bonesetter.\"",
    23: "I take the key and walk toward the curtain.",
}


def _sam(*others: str) -> Scene:
    s = Scene(location_id="5bbd0c40345f")
    s.add(from_dict(dict(SAM), ref="pc"))
    for name in others:
        s.add(instantiate("thug", scene=s, name=name))
    return s


# --- the four measured lines --------------------------------------------------------------


@pytest.mark.parametrize("turn", sorted(MEASURED))
def test_the_four_measured_lines_are_not_claims(turn):
    """Four of four were rolled as a Bluff at DC 30 on 2026-09-30; none was a lie."""
    scene = _sam("the cage owner")
    line = MEASURED[turn]
    assert judgement.false_claim(line, scene) == "", (turn, line)
    out = judgement.inject_false_claim([{"op": "narrate_only", "because": "t"}], line, scene)
    assert all(r.get("op") != "check" for r in out), (turn, out)


def test_bare_take_is_acquisition_and_take_out_is_still_producing():
    """"take" went; "take out" stays — pulling a crown out of a coat is still a claim."""
    scene = _sam()
    assert judgement.false_claim("I take the crown", scene) == ""
    assert judgement.false_claim("I take out my crown", scene) == \
        "produce a crown you do not have"


# --- the anchor ---------------------------------------------------------------------------


@pytest.mark.parametrize("line", [
    "I keep my hand on the hilt of my blade as I navigate the crowd.",
    "I use Lay on Hands on the fighter",
    "I lay my hands on the wound and press down",
])
def test_a_noun_after_my_or_on_is_never_the_verb(line):
    """Replayed 2026-09-30: `hand`/`Hands` matched with no subject — "my hand on the
    hilt" and "Lay on Hands on the fighter" both read as handing something over."""
    scene = _sam("the fighter")
    assert not judgement._PRODUCE.search(line), line
    assert judgement.false_claim(line, scene) == "", line


@pytest.mark.parametrize("line", [
    "I hand him the deed to the mill",
    "I kneel and pull out my crown",
    "I reach into my coat to pull out my crown",
    "I slowly pull out my crown",
    "\"Look.\" I show them my royal seal",
    "I'll show you my royal seal",
])
def test_the_anchored_verb_still_finds_the_real_shapes(line):
    """The narrowing loses nothing item 37 caught: a subject, a coordinated verb, an
    infinitive, an adverb, a clause start."""
    assert judgement._PRODUCE.search(line), line
    assert judgement.false_claim(line, _sam()), line


# --- the reading and the plan --------------------------------------------------------------


def test_turn_23_a_plan_that_gives_the_key_is_acquisition():
    """Turn 23: the plan carried `give key -> pc` and the room still rolled against him
    for producing a key. Asked with a produce-shaped line, so it is the plan doing it."""
    scene = _sam("Gorm Vesper")
    line = "I take out the key and walk toward the curtain."
    assert judgement.false_claim(line, scene) == "produce a key you do not have"
    plan = [{"op": "give", "params": {"item": "key", "to": "pc"},
             "because": "the player said they took it"}]
    assert judgement.false_claim(line, scene, plan=plan) == ""
    out = judgement.inject_false_claim(list(plan), line, scene)
    assert [r["op"] for r in out] == ["give"], out


def test_a_take_the_interpreter_read_is_acquisition():
    """The interpreter had already read `act: take` on turn 4 and nothing passed it in;
    `gm/agent.py` hands `self.reading` to the check now."""
    scene = _sam("the cage owner")
    line = "I pull out the herbs and press them to the wound"
    assert judgement.false_claim(line, scene)
    reading = {"actions": [{"act": "take", "object": "the herbs"},
                           {"act": "use", "object": "the herbs", "target": "him"}]}
    assert judgement.false_claim(line, scene, reading=reading) == ""
    assert all(r.get("op") != "check" for r in judgement.inject_false_claim(
        [{"op": "narrate_only"}], line, scene, reading=reading))


def test_the_agent_passes_the_reading_and_withdraws_the_prose_claim():
    import inspect

    from gm import agent

    src = inspect.getsource(agent.GMAgent.plan_turn)
    at = src.index("inject_false_claim(")
    assert "reading=reading" in src[at:at + 200]
    assert "self.false_claim = \"\"" in src[at:at + 600]


def test_the_crowd_hears_no_delusion_on_the_turn_the_key_was_given():
    """`note_heat` reads the same `false_claim`: a give that landed is acquisition."""
    scene = _sam("Gorm Vesper")
    given = Outcome(intent_id="i1", op="give", tell="the key changes hands.",
                    effects=[{"ref": "pc", "kind": "give", "item": "key", "count": 1}])
    judgement.note_heat(scene, [given], "I take out the key and walk toward the curtain.")
    assert (scene.heat or {}).get("kind") != "delusion"
    judgement.note_heat(scene, [], "I take out my crown")
    assert scene.heat["kind"] == "delusion"


# --- hedges and the head noun -----------------------------------------------------------------


@pytest.mark.parametrize("line", [
    "I'm a bit of a free spirit",
    "I'm a little bit of a rogue, honestly",
    "I am a kind of wizard of the kitchen",
    "I am the last in the queue",
    "I'm the one who set his leg",
])
def test_a_hedge_or_a_head_that_is_no_identity_is_character(line):
    """Turn 12: "a bit of a free spirit" was a claim to BE a spirit, because any word of
    the predicate counted. Only the head noun is judged now, and a hedge is temper."""
    assert judgement.false_claim(line, _sam()) == "", line


@pytest.mark.parametrize("pred,head", [
    ("the lost heir of the old kings", "heir"),
    ("the greatest swordsman alive", "swordsman"),
    ("the chosen one of the old prophecy", "chosen"),
    ("my true form as a divine being", "form"),
    ("the ancient power within me", "power"),
    ("what I truly am: a master assassin of the eastern guilds", "assassin"),
    # The hedge's own head: "a BIT (of a free spirit)". Not an identity either way, and
    # `_HEDGE` says so before the head is asked.
    ("a bit of a free spirit", "bit"),
])
def test_the_head_noun_is_read_from_the_noun_phrase(pred, head):
    assert judgement._predicate_head(pred) == head


@pytest.mark.parametrize("line", [
    "I am the lost heir of the old kings",
    "I am actually the greatest swordsman alive",
    "I am the chosen one of the old prophecy",
    "I'm a free spirit",
])
def test_an_unhedged_identity_is_still_a_claim(line):
    """The owner's recommendation: fix hedges and the head noun now, idioms only if an
    unhedged "I'm a free spirit" recurs. It is still read as a claim today."""
    assert judgement.false_claim(line, _sam()), line


# --- B1: Bluff against Sense Motive, at the book's believability ------------------------------


@pytest.mark.parametrize("claim,lie", [
    ("reveal their true form as a divine being", "impossible"),
    ("produce a crown you do not have", "impossible"),
    ("are the king's lost heir", "far_fetched"),
    ("have always been a wizard", "unlikely"),
    ("are a merchant of the eastern guilds", "believable"),
])
def test_believability_is_read_from_the_claim_in_code(claim, lie):
    assert judgement.lie_of(claim) == lie


def test_the_lie_is_opposed_by_the_listeners_sense_motive():
    """Was {"dc": {"band": "heroic"}}: DC 30 against Sam's Bluff +6, three failures in
    three. Now the listener is named and the check is opposed."""
    scene = _sam("the foreman")
    out = judgement.inject_false_claim([{"op": "narrate_only"}],
                                       "I am the king's lost heir", scene)
    assert out == [{"op": "check", "actor": "pc", "visibility": "player",
                    "because": "claiming to be what the sheet says they are not",
                    "params": {"skill": "bluff",
                               "opposed_by": {"ref": "c1", "skill": "sense motive",
                                              "lie": "far_fetched"}}}]


def test_the_person_spoken_to_is_the_one_who_judges_it():
    scene = _sam("the foreman", "the clerk")
    said = [{"op": "say", "params": {"to": "c2", "words": "I am the king's lost heir"}}]
    out = judgement.inject_false_claim(said, "I tell the clerk I am the king's lost heir",
                                       scene)
    check = next(r for r in out if r["op"] == "check")
    assert check["params"]["opposed_by"]["ref"] == "c2"


def test_nobody_listening_is_no_roll():
    """An opposed check needs an opponent (CRB p.90: "against your opponent's Sense
    Motive"). Alone, the claim is still false — the prose is told so — and nothing rolls."""
    scene = _sam()
    raw = [{"op": "narrate_only"}]
    assert judgement.false_claim("I am the king's lost heir", scene)
    assert judgement.inject_false_claim(raw, "I am the king's lost heir", scene) == raw


def test_a_lie_the_model_wrote_is_not_a_number_it_chose():
    """The believability is code's: a `lie` on a model's check is taken off."""
    scene = _sam("the foreman")
    raw = [{"op": "check", "actor": "pc", "params": {
        "skill": "stealth", "opposed_by": {"ref": "c1", "skill": "perception",
                                           "lie": "believable"}}}]
    out = judgement.inject_false_claim(raw, "I creep past him", scene)
    assert "lie" not in out[0]["params"]["opposed_by"]


def test_the_engine_rolls_it_opposed_with_the_books_modifier():
    """End to end through the engine's own check machinery: the opposing Sense Motive is
    rolled, the believability is a named term on the Bluff, and the tell names both."""
    scene = _sam("the foreman")
    raw = judgement.inject_false_claim([{"op": "narrate_only"}],
                                       "I reveal my true form as a divine being", scene)
    engine = Engine(scene, Dice(seed=3))
    res = engine.run(engine.validate(raw))
    if res.awaiting:
        res = engine.resume(10)
    o = next(o for o in res.outcomes if o.op == "check")
    bluff, motive = o.rolls[0], o.rolls[1]
    assert {"value": -20, "source": "the lie is impossible"} in \
        [m.as_dict() for m in bluff.modifiers]
    assert "Sense Motive" in motive.label
    assert "Bluff" in o.tell and "sense motive" in o.tell
    assert o.dc["value"] == motive.total

"""`"manoeuvre": "none"` is no manoeuvre, never a weapon called "none".

Measured on two live fight audits running (`narrator_audit.py --script fight`,
gemma-4-12B; 2026-09-27 on twin-names, 2026-09-28 on pick-a-fight-is-not-a-thing):
turn 1, "I pick a fight with the biggest man in the room", was lost the same way both
times. The plan's `declared` block held `"attack": {"params": {"manoeuvre": "none"}}`;
`judgement.normalize_attacks` moved every word that is not a manoeuvre into `weapon`,
and the parser refused "attack: no such weapon 'none'" on all five attempts. The turn
went to the fallback model, which did not answer in 600 s, and degraded to narration.

"none" is the commonest manoeuvre the model writes: 53 of 157 values across the 32
recordings on this machine (2026-09-28). The same unasked move lost "punch" (6), "strike"
(4, a word the parser itself drops as part of attacking), "throw" (3), "bull_rush" and
"dirty_trick" (1 each), and would have lost "intimidate", which the parser turns into a
check but only ever saw as a weapon. Both turns are kept in tests/replay/plans/ and
replayed through the real `plan_turn` below.
"""
from __future__ import annotations

import pytest

from gm import judgement
from rules.intents import attack_slots, parse
from tests._replay import recorded, replay_plan

RECORDED = "2026-09-28-fight-manoeuvre-none-gemma4-12b.jsonl.gz"


def _through(params):
    """An attack with these params, through the pre-validation repair and the parser."""
    raw = [{"op": "attack", "actor": "pc", "target": "c1", "params": params}]
    raw = judgement.normalize_attacks(raw, None) or raw
    return parse(raw[0])


@pytest.mark.parametrize("word", ["none", "None", "null", "n/a", "no", "", "nothing"])
def test_a_null_word_is_no_manoeuvre(word):
    intent = _through({"manoeuvre": word})
    assert intent.op == "attack"
    assert "manoeuvre" not in intent.params and "weapon" not in intent.params


@pytest.mark.parametrize("word", ["none", "null", "n/a"])
def test_a_null_word_is_no_weapon_either(word):
    intent = _through({"weapon": word})
    assert "weapon" not in intent.params


@pytest.mark.parametrize("word,expect", [
    # Recorded in the manoeuvre slot, each refused as a weapon before.
    ("punch", {"weapon": "unarmed"}),
    ("strike", {}),
    ("throw", {}),
    ("bull_rush", {"manoeuvre": "bull rush"}),
    ("dirty_trick", {"manoeuvre": "dirty trick"}),
    # The controls: a manoeuvre stays one, and a weapon filed as a manoeuvre — the case
    # the move into `weapon` was written for — still becomes the weapon.
    ("trip", {"manoeuvre": "trip"}),
    ("grab", {"manoeuvre": "grapple"}),
    ("armed punch", {"weapon": "armed punch"}),
    ("unarmed", {"weapon": "unarmed"}),
])
def test_each_recorded_word_lands_in_its_own_slot(word, expect):
    got = {k: v for k, v in _through({"manoeuvre": word}).params.items()
           if k in ("manoeuvre", "weapon")}
    assert got == expect, word


def test_a_skill_in_the_manoeuvre_slot_still_reaches_the_parser_as_a_skill():
    """The parser rewrites `"manoeuvre": "intimidate"` into an Intimidate check; the
    repair that runs before it used to file the skill as a weapon first."""
    intent = _through({"manoeuvre": "intimidate"})
    assert intent.op == "check" and intent.params["skill"] == "intimidate"


@pytest.mark.parametrize("word", ["false", "no", "none", "0"])
def test_a_flag_written_as_a_word_is_read_as_one(word):
    """`bool("false")` is True, the engine reads every flag with `bool()`, and the
    declared block typed them all as strings. Not seen in a recording yet; a wrong power
    attack changes the numbers, and a wrong `drain` makes ability damage permanent."""
    intent = parse({"op": "attack", "actor": "pc", "target": "c1",
                    "params": {"full_attack": word, "power_attack": word}})
    assert intent.params["full_attack"] is False
    assert intent.params["power_attack"] is False
    drained = parse({"op": "ability_damage", "target": "pc",
                     "params": {"ability": "str", "amount": 1, "drain": word}})
    assert drained.params["drain"] is False
    assert parse({"op": "attack", "actor": "pc", "target": "c1",
                  "params": {"full_attack": "true"}}).params["full_attack"] is True


def test_the_declared_schema_samples_a_flag_as_a_boolean():
    """At the sampler, so no word should be writable there: Ollama compiles `format` to
    a grammar, which held required properties and enums 6 of 6 where it ignored
    `contains` (docs/the-interpreter.md). Types ride the same grammar and were not
    probed separately; the parser's `_flag` is the net either way."""
    from gm import prompts

    props = prompts._declared_op("attack", (), ())["properties"]["params"]["properties"]
    assert props["full_attack"] == {"type": "boolean"}
    assert props["power_attack"] == {"type": "boolean"}
    assert props["manoeuvre"] == {"type": "string"}


def test_the_slots_are_read_once():
    """The repair before validation and the parser read the two slots the same way
    (`attack_slots`); a second copy of the rule is how "strike" was dropped by one and
    refused by the other. Where they still differ is on purpose: a word neither table
    knows is refused by the parser, which teaches the model, and moved or dropped only by
    the repair before it ("armed punch" to `weapon`, above)."""
    for word in ("none", "null", "punch", "strike", "bull_rush", "trip", "grab"):
        man, weapon = attack_slots(word, None)
        parsed = parse({"op": "attack", "actor": "pc", "target": "c1",
                        "params": {"manoeuvre": word}})
        assert (parsed.params.get("manoeuvre"), parsed.params.get("weapon")) \
            == (man, weapon), word


@pytest.mark.parametrize("n", [0, 1])
def test_the_recorded_turn_stands_on_the_first_reply(n, tmp_path, monkeypatch):
    """Turn 1 of each audit, the model's first plan reply as it was written: refused on
    "no such weapon 'none'" before, five times, then narration. Now the first reply
    stands: a plain attack on Borin (the plan's `new1`/`new2`, bound by
    `bind_placeholders`) and the provocation."""
    rec = recorded(RECORDED)[n]
    assert rec["player"] == "I pick a fight with the biggest man in the room."
    assert '"manoeuvre": "none"' in rec["calls"][1]["raw"]
    plan, scene = replay_plan(rec, tmp_path, monkeypatch)

    assert plan.rejections == [], plan.rejections
    # The plan's `say` ("I've had enough of this.") was the MODEL's words in the player's
    # mouth — the player wrote no speech — and since item 6 (2026-09-28,
    # `judgement.own_words_only`) such a say is dropped, not booked as the player's.
    assert [i.op for i in plan.intents] == ["attack", "provoke"]
    attack, _ = plan.intents
    # The barkeep, by the name the world holds for him; the panel shows "the one behind
    # the bar" until he gives it (owner ruling F1, 2026-09-30).
    assert scene.actors["c2"].true_name == "Borin Lyraxys"
    assert attack.target == "c2"
    assert "weapon" not in attack.params and "manoeuvre" not in attack.params

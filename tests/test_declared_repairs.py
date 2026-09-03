"""Two repairs the 2026-09-02 probes measured, each twice, in code rather than in prompt.

Playtest method, as the memory records it: declaration-detection in code is the only
GM fix that has ever held here. Both of these are that.
"""
from __future__ import annotations

import pytest

from gm import judgement
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError
from rules.sheet import load_pc
from tests._places import stand_on


def _yard():
    s = Scene(location_id="5bbd0c40345f")
    stand_on(s, "urban")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("guildhand", scene=s, name="the merchant"))
    return s, Engine(s, Dice(seed=3))


# --- a power nobody has is not an assault ----------------------------------------------

def test_an_unknown_ability_used_on_somebody_does_not_start_a_fight():
    """"I use Blood Nova on the merchant" came back from the model as `attack`, opened a
    fight with the merchant and every promoted bystander in the market, and the second
    time put Kesst on the floor. Nothing in the sentence is a fight cue; the model
    guessed what a thing it had never heard of does, and guessed violence."""
    s, engine = _yard()
    proposed = [{"op": "attack", "actor": "pc", "target": "c1", "because": "a burst"},
                {"op": "narrate_only"}]
    raw = judgement.refuse_unknown_ability(proposed, "I use Blood Nova on the merchant", s)
    ops = [r["op"] for r in raw]
    assert "attack" not in ops and "use_ability" in ops
    assert next(r for r in raw if r["op"] == "use_ability")["params"]["ability"] == "Blood Nova"

    # And the engine prints the refusal with the real names, starting nothing.
    res = engine.run(engine.validate(raw))
    assert not s.in_encounter
    out = next(o for o in res.outcomes if o.op == "use_ability")
    assert out.effects == [] and "no ability called Blood Nova" in out.tell


def test_a_real_ability_and_a_carried_jar_are_left_to_their_own_injectors():
    from rules.crafting import Stock

    s, engine = _yard()
    s.pc().stock["tea#1"] = Stock(base="Woundwart Tea", count=1,
                                  specs=[{"type": "heal", "dice": "1d8"}])
    proposed = [{"op": "attack", "actor": "pc", "target": "c1"}]
    # A jar by its base name: the jar door opens it. Before stage 8 this returned the
    # list untouched, which let a model-written `heal` through beside the real potion
    # and landed the number twice; now the attack (no number in it) stays and the
    # `use_item` is added, so the tea's own document supplies what it does.
    assert judgement.refuse_unknown_ability(proposed, "I use Woundwart Tea on the merchant", s) \
        == proposed + [{"op": "use_item", "actor": "pc",
                        "because": "the player reached for Woundwart Tea",
                        "params": {"item": "tea#1", "how": "drink"}}]
    # Lowercase after the verb is an object, not a named power: "the rope" is not an
    # ability called "the rope".
    assert judgement.refuse_unknown_ability(proposed, "I use the rope on the door", s) \
        == proposed
    # A question is not a use.
    assert judgement.refuse_unknown_ability(proposed, "Can I use Blood Nova on him?", s) \
        == proposed


# --- told to leave, the model may not name the room it is in ----------------------------

def test_leaving_to_the_room_you_are_in_is_asked_again_with_the_others():
    """Twice in one probe: "I leave the merchant and head out", the schema demanding a
    travel and the brief listing three places, came back as `travel place=the market`
    — the place the party was standing in. Raised into the planner's correction path,
    so the model is asked again with the places that would have worked."""
    s, engine = _yard()
    here = engine.here()
    with pytest.raises(IntentError) as e:
        judgement.refuse_leaving_in_place(
            [{"op": "travel", "params": {"place": here.name}}],
            "I leave the merchant and head out", s)
    said = str(e.value)
    assert f"already at {here.name}" in said
    for p in engine.places():
        if p.id != here.id:
            assert p.name in said, "the correction must name what would have worked"
    assert here.name not in said.split("name where to:")[1]


def test_leaving_to_another_room_or_staying_on_purpose_passes():
    s, engine = _yard()
    here = engine.here()
    other = next(p for p in engine.places() if p.id != here.id)
    ok = [{"op": "travel", "params": {"place": other.name}}]
    assert judgement.refuse_leaving_in_place(ok, "I leave and head out", s) == ok
    # Not a departure: a travel to here on a sentence that did not say "leave" is the
    # engine's no-op, not this repair's business.
    stay = [{"op": "travel", "params": {"place": here.name}}]
    assert judgement.refuse_leaving_in_place(stay, "I look around the market", s) == stay
    # The ground already underfoot, by biome, IS staying.
    with pytest.raises(IntentError):
        judgement.refuse_leaving_in_place(
            [{"op": "travel", "params": {"biome": "urban"}}], "I head out", s)


def test_a_one_place_location_has_nowhere_to_send_them():
    s = Scene(location_id=None)
    s.add(load_pc("fixtures/pc-kesst.json"))
    stay = [{"op": "travel", "params": {"place": "here"}}]
    assert judgement.refuse_leaving_in_place(stay, "I leave", s) == stay

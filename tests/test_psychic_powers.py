"""A mind is not changed by saying so.

Reported from the table 2026-09-09: "I was able to break the game and use psychic
powers to manipulate the people and story in ways that should not be possible."

Reproduced in a single intent, with no ability, no spell and no document of any kind:

    {"op": "condition", "actor": "pc", "because": "I bend his mind to my will",
     "params": {"condition": "helpful", "to": "c1"}}

    merchant attitude before: indifferent
    ACCEPTED — tell: "the merchant is helpful."
    merchant attitude after:  helpful

Two holes, one either side of the model, and both are pinned here.

  * **The engine had no gate on a mind.** The seven amount-ops have been refused
    without provenance since stage 8a — a number needs a document behind it — and an
    attitude is a bigger lever than a number, because the brief reads it and the
    narrator then writes that creature as an ally for the rest of the campaign. It had
    no gate at all, and `condition` is not an amount-op, so the sampler offers it.
  * **The declaration had no door.** `refuse_unknown_ability` catches "I use Blood Nova
    on the merchant" because Blood Nova is a NAME it can look up. "I read his mind" has
    no name in it, so nothing looked anything up and the sentence reached the narrator
    as ordinary prose, which wrote it as working. That shape needs no intent at all to
    do damage: the story simply bends.

The rule both halves enforce is the one the table asked for in GAS's words — an ability
that was never granted cannot be activated. Here the grant is a document (a spell in the
book, a power on the sheet, an item in the satchel) and `origin` is the engine's record
that one was actually read.
"""
from __future__ import annotations

import pytest

from gm import judgement
from rules import states
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError
from rules.sheet import load_pc
from tests._places import stand_on


def _market():
    s = Scene(location_id="5bbd0c40345f")
    stand_on(s, "urban")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("guildhand", scene=s, name="the merchant"))
    return s, Engine(s, Dice(seed=3))


def _condition(key, **params):
    return {"op": "condition", "actor": "pc", "because": "I will it",
            "params": dict({"condition": key, "to": "c1"}, **params)}


# --- the engine gate ------------------------------------------------------------------

def test_the_reported_exploit_in_the_intent_that_did_it():
    """The measurement at the top of this file, exactly as it was made."""
    s, engine = _market()
    merchant = s.actors["c1"]
    with pytest.raises(IntentError) as e:
        engine.run(engine.validate([_condition("helpful")]))
    assert "an attitude is not something anyone can simply decide on" in str(e.value)
    assert states.attitude_of(merchant) != "helpful"


@pytest.mark.parametrize("key,family", [
    ("helpful", "an attitude"), ("friendly", "an attitude"),
    ("hostile", "an attitude"), ("unfriendly", "an attitude"),
    ("charmed", "a mind-affecting effect"),
    ("dominated", "a mind-affecting effect"),
    ("confused", "a mind-affecting effect"),
    ("fascinated", "a mind-affecting effect"),
    ("frightened", "a fear effect"), ("shaken", "a fear effect"),
    ("panicked", "a fear effect"), ("cowering", "a fear effect"),
    ("sleeping", "a sleep effect"), ("asleep", "a sleep effect"),
])
def test_every_family_of_mind_needs_a_document(key, family):
    s, engine = _market()
    with pytest.raises(IntentError) as e:
        engine.validate([_condition(key)])
    assert family in str(e.value)


def test_the_refusal_names_doors_that_exist():
    """Validators name the fix, not the fault. Every door listed here is real, and the
    ordinary social route is named too so the answer is not "you may never persuade
    anybody" — Diplomacy, Intimidate and Bluff are checks the engine already rolls."""
    s, engine = _market()
    with pytest.raises(IntentError) as e:
        engine.validate([_condition("charmed")])
    said = str(e.value)
    for door in ("cast spell=<id>", "use_ability ability=<name>", "use_item item=<id>",
                 "check skill=diplomacy", "check skill=intimidate"):
        assert door in said, door


@pytest.mark.parametrize("key", [
    "prone", "grappled", "stunned", "dazed", "blinded", "deafened", "nauseated",
    "sickened", "staggered", "entangled", "pinned", "fatigued", "exhausted",
    "petrified", "paralyzed", "flat-footed", "dazzled", "invisible",
])
def test_a_body_is_left_alone(key):
    """The gate is about minds. Shoving somebody prone, grappling them or blinding them
    with a lantern needs no document, and a gate that asked for one would refuse
    ordinary violence for having a mental cousin. Measured when this was written: 25 of
    25 body conditions pass, 21 of 21 mind conditions are caught."""
    s, engine = _market()
    engine.validate([_condition(key)])          # raises if the gate over-reached


def test_lifting_a_mind_effect_is_never_gated():
    """The inversion `_op_condition` already carries a scar from: gate a removal and a
    charm can never be broken, exactly as gating the applicator once made 759 undead
    unkillable by blocking the very condition that records their death."""
    s, engine = _market()
    engine.validate([_condition("charmed", ends=True)])
    engine.validate([_condition("helpful", ends=True)])


@pytest.mark.parametrize("origin", [
    "spell:charm-person", "ability:blood-bending/dread-presence",
    "item:philtre-of-love#1", "rule:fear", "creature:guildhand",
])
def test_a_real_document_still_changes_a_mind(origin):
    """The gate asks for provenance, not for permission. Every door that reads a real
    document stamps one, so charm person still charms — and this is the half that would
    make the fix a worse bug than the exploit if it were wrong."""
    s, engine = _market()
    engine.run(engine.validate([_condition("charmed")], origin=origin))
    assert s.actors["c1"].has_state("condition.charmed")


# --- the immunity table the gate was asked of -----------------------------------------

def test_undead_are_immune_to_domination_and_always_should_have_been():
    """Found while writing the gate, not looked for. `IMMUNITY_COVERS` spelled the
    mind-affecting family out four separate times — under "mind-affecting", "mind
    affecting", "undead traits" and "construct traits" — and the word "dominate"
    appeared in none of the four. Dominate person is a mind-affecting compulsion in the
    Core Rulebook, so 759 shipped creatures with undead traits were immune to charm and
    wide open to domination. The list is written once now and spliced into all four."""
    for bundle in ("mind-affecting", "undead traits", "construct traits"):
        assert states.immunity_blocks([bundle], "dominated"), bundle
        assert states.immunity_blocks([bundle], "charmed"), bundle
    assert not states.immunity_blocks(["undead traits"], "prone"), \
        "the bundle grew a condition it should never have covered"


# --- the declaration door -------------------------------------------------------------

REACHES_A_MIND = [
    "I read his mind", "I read the merchant's thoughts", "I probe her mind for the truth",
    "I search his memories for the name", "I peer into their mind",
    "I mind control the guard", "I mind-control him into opening the gate",
    "I dominate the merchant", "I charm the guard",
    "I charm the merchant into a better price", "I hypnotize her",
    "I mesmerise the crowd", "I brainwash him", "I bewitch the clerk",
    "I bend his will to mine", "I take over her mind", "I seize control of his mind",
    "I erase his memory of the theft", "I plant a suggestion in his head",
    "I implant the idea that I am a guard",
    "I use my psychic powers to make him hand it over",
    "I focus my mental energy on the lock", "I telepathically tell her to run",
    "I psychically push him back", "I speak to him with my mind",
    "I command him inside his head", "I try to read his mind",
    "I quietly probe the merchant's thoughts",
    # The instrument named outright, with no verb the pattern could have listed. The
    # first is the sentence that failed this file's own guesses test.
    "I crush his will with my mind", "I open the door with my mind",
    "I lift the key using my mind", "I strike him through my thoughts",
]

ORDINARY = [
    # Social play. Every one of these is a skill check and none of them is refused —
    # the fix must not turn "I persuade the merchant" into "you have no such power".
    "I persuade the merchant to lower the price", "I convince him I am a guard",
    "I intimidate the thug into backing off", "I threaten him with the guard",
    "I lie about where I came from", "I bluff my way past the clerk",
    "I haggle with the stallholder", "I plead with her to let me through",
    "I bribe the guard", "I flirt with the barkeep", "I appeal to his greed",
    "I ask the merchant about the road",
    # Speech. A character may BOAST about powers they do not have; the file already
    # knows the difference between saying a thing and doing it.
    "I tell him I can read minds", 'I say "I will dominate you all"',
    # The same words, meaning something physical or idiomatic.
    "I read the letter", "I read the sign over the door", "I search his pockets",
    "I search the room for the key", "I make up my mind to go north",
    "I control my breathing", "I bend the bars", "I break the lock",
    "I push the door open", "I plant my feet", "I focus my attention on the tracks",
    "I command my dog to sit", "I remember the road to the coast", "I keep it in mind",
    "I take control of the cart", "I seize the reins",
    # "Charm" is two words in English and only one of them is the spell. A charm done
    # WITH something is a performance; the spell never names an instrument.
    "I charm the snake with my flute", "I charm the room with my manner",
    "I charm her with a story",
    # "With" is the commonest preposition in English and the instrument arm above had
    # to be narrow enough not to eat these.
    "I go with my gut", "I fight with my sword", "I open the door with my shoulder",
    "I deal with my debts", "I catch up with my brother", "I part with my coin",
    "I speak with the merchant",
]


@pytest.mark.parametrize("line", REACHES_A_MIND)
def test_reaching_into_a_mind_becomes_the_ability_door(line):
    """32 of 32 when this was written."""
    s, _ = _market()
    out = judgement.refuse_unnamed_power([{"op": "narrate_only", "because": "x"}],
                                         line, s)
    assert any(r["op"] == "use_ability" for r in out), line


@pytest.mark.parametrize("line", ORDINARY)
def test_ordinary_play_is_untouched(line):
    """40 of 40 when this was written. This half matters more than the other: a false
    refusal lands on a player who did nothing wrong, in the middle of their turn."""
    s, _ = _market()
    raw = [{"op": "narrate_only", "because": "x"}]
    assert judgement.refuse_unnamed_power(list(raw), line, s) == raw, line


def test_the_engine_answers_the_declaration_with_what_they_can_actually_use():
    """The whole point of routing it to `use_ability` rather than inventing a refusal
    here: the engine's own door already prints the list, in the same words a made-up
    named power gets."""
    s, engine = _market()
    out = judgement.refuse_unnamed_power(
        [{"op": "narrate_only", "because": "x"}],
        "I read the merchant's mind to find where he keeps the key", s)
    result = engine.run(engine.validate(out))
    tells = " ".join(o.tell for o in result.outcomes)
    assert "no ability called" in tells and "They can use:" in tells


def test_the_models_guesses_do_not_survive_the_refusal():
    """`refuse_unknown_ability` learned this the expensive way — told to drop only the
    fight-makers, the next probe came back with `ability_damage con 1d4` instead and it
    landed, three Constitution damage from a power nobody has. A guess about a power
    that was never granted is worth nothing, whatever op it is wearing."""
    s, _ = _market()
    guesses = [
        {"op": "ability_damage", "actor": "pc", "target": "c1",
         "because": "psychic", "params": {"ability": "wis", "amount": "1d4"}},
        {"op": "condition", "actor": "pc",
         "because": "dominated", "params": {"condition": "helpful", "to": "c1"}},
        {"op": "attack", "actor": "pc", "target": "c1", "because": "psychic assault"},
        {"op": "damage", "actor": "pc", "target": "c1", "params": {"amount": "2d6"}},
    ]
    out = judgement.refuse_unnamed_power(guesses, "I crush his will with my mind", s)
    assert [r["op"] for r in out] == ["use_ability"]


def test_a_power_they_really_have_is_never_second_guessed():
    """This door is the complement of `inject_ability`, not a second opinion on it. A
    granted power that reaches a mind is exactly what the GAS rule permits, and the
    refusal must stand down the moment the sheet actually carries one."""
    from rules import creation, classbuilder as cb
    from rules.sheet import from_dict

    cb.save_class(cb.scaffold("paths"))
    built, _ = creation.build({
        "name": "Gale Test", "race": "human", "bonus_ability": "wis",
        "class": "storm caller", "pronouns": "she/her",
        "abilities": {"str": 10, "dex": 14, "con": 12, "int": 10, "wis": 14, "cha": 10},
        "skills": [], "feats": [], "paths": ["gale"],
    })
    s = Scene(location_id="5bbd0c40345f")
    stand_on(s, "urban")
    pc = from_dict(built["sheet"])
    pc.ref = "pc"
    s.add(pc)
    s.add(instantiate("guildhand", scene=s, name="the merchant"))

    real = [{"op": "use_ability", "actor": "pc", "because": "she reaches for it",
             "params": {"ability": "Cutting Gust"}}]
    assert judgement.refuse_unnamed_power(list(real),
                                          "I bend his will with Cutting Gust", s) == real

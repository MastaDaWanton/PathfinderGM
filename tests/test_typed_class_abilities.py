"""A class ability TYPED at the table reaches the engine (fix/typed-class-abilities).

The defect, measured 2026-10-05 by two lanes: the core classes' abilities existed as
documents (rules/class_abilities.py) and worked from the combat bar, but the GM's doors in
gm/judgement.py asked only `leveling.find_ability` / `usable_names` — Blood Bending's path
abilities. Live: "use my Fire Bolt" produced narration describing a hit while no ability
was used and the pool stayed 6/6 — the narrator authored a mechanical result. "I use
Smite Evil" resolved only by accident: refused as unknown, then rescued by the
`use_ability` put in the refusal's place.

Measured on 41 typed lines across eight classes, through the ability doors of the live
chain with the model's reply standing at `narrate_only`: **4 of 41** reached the right
ability before (each by that accident), 0 of 3 named-but-not-yet abilities reached the
engine's level refusal, 0 of 20 must-not-fire lines fired. After: 41/41, 3/3, 0/20. Then
18 more lines and 13 more must-not-fire lines were written to test the change rather than
confirm it; on its first run they scored 17/18 and **3 false alarms of 13** ("I lay hands on
the altar and pray", "I rage against the dying of the light", "I want to use my fire bolt
later"), which the pointing-preposition and intention rules now answer: 59/59, 3/3, 0/33.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from gm import beat_verify, judgement
from rules import class_abilities as ca
from rules import leveling
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc, to_dict


def _bare(cls, level, **extra):
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"class": cls, "level": level, "ranks": {}, "armour": "none"})
    d.pop("paths", None)
    d.update(extra)
    return from_dict(d, ref="pc")


def _picks(choice, pick, **more):
    return {choice: {"option": "class option",
                     "picks": [{"pick": pick, "level": 1, **more}]}}


def _who(who, level):
    if who == "cleric":
        return _bare("cleric", level, domains=["Fire", "War"])
    if who == "sorc_draconic":
        return _bare("sorcerer", level, class_choices=_picks("bloodline", "draconic",
                                                             variant="red"))
    if who == "sorc_elemental":
        return _bare("sorcerer", level, class_choices=_picks("bloodline", "elemental",
                                                             variant="fire"))
    if who == "wiz_evocation":
        return _bare("wizard", level, class_choices=_picks("arcane school", "evocation"))
    return _bare(who, level)


def _scene(pc):
    s = Scene()
    s.add(pc)
    s.add(instantiate("thug", scene=s, name="the cutpurse"))
    ally = instantiate("thug", scene=s, name="Brannoc")
    s.add(ally)
    s.sides = {"pc": ["pc", ally.ref], "them": ["c1"]}
    return s


def _doors(raw, text, scene):
    """The ability doors of the live chain, in gm/agent.py's order."""
    raw = judgement.inject_ability(raw, text, scene)
    raw = judgement.refuse_unknown_ability(raw, text, scene)
    raw = judgement.refuse_unnamed_power(raw, text, scene)
    return judgement.refuse_declared_creation(raw, text, scene)


def _resolved(pc, raw):
    """What the engine's own lookups make of the turn's `use_ability`: "Name (choice)",
    "?Name [arrives N]" for one not yet theirs, or None when no ability is used."""
    for r in raw:
        if r.get("op") != "use_ability":
            continue
        name = str((r.get("params") or {}).get("ability", ""))
        doc, choice = ca.find(pc, name)
        if doc is None:
            return f"?{name} [arrives {ca.arrives_at(pc, name)}]"
        doc2, wrong = ca.with_choice(pc, doc, choice)
        assert not wrong, wrong
        pick = doc2.get("picked") or (doc2.get("form") or {}).get("key") or doc2.get("skill")
        return f"{doc['name']} ({pick})" if pick else doc["name"]
    return None


HITS = [
    ("cleric", 3, "I channel energy", "Channel Energy (heal)", ""),
    ("cleric", 3, "I channel positive energy to heal everyone", "Channel Energy (heal)", ""),
    ("cleric", 3, "I channel negative energy to harm them",
     "Channel Energy (harm the living)", ""),
    ("cleric", 3, "channel to heal", "Channel Energy (heal)", ""),
    ("cleric", 3, "I channel to harm the undead", "Channel Energy (harm)", ""),
    ("cleric", 3, "I use Channel Energy (harm the living)",
     "Channel Energy (harm the living)", ""),
    ("cleric", 3, "I channel negative energy to heal the undead",
     "Channel Energy (heal undead)", ""),
    ("cleric", 3, "I use my channel to heal the party", "Channel Energy (heal)", ""),
    ("cleric", 3, "use my Fire Bolt on the cutpurse", "Fire Bolt", "c1"),
    ("cleric", 3, "I hurl a fire bolt at the cutpurse", "Fire Bolt", "c1"),
    ("cleric", 3, "i use my fire bolt on the cutpurse", "Fire Bolt", "c1"),
    ("cleric", 3, "I use Battle Rage on myself", "Battle Rage", "pc"),
    ("barbarian", 3, "I rage", "Rage", ""),
    ("barbarian", 3, "I rage and attack the cutpurse", "Rage", ""),
    ("barbarian", 3, "I fly into a rage and charge the cutpurse", "Rage", ""),
    ("barbarian", 3, "I enter a rage", "Rage", ""),
    ("barbarian", 3, "I use rage", "Rage", ""),
    ("barbarian", 3, "Rage, then I swing at the cutpurse", "Rage", ""),
    ("barbarian", 3, "I activate my rage", "Rage", ""),
    ("paladin", 4, "I smite evil on the cutpurse", "Smite Evil", "c1"),
    ("paladin", 4, "I use Smite Evil against the cutpurse", "Smite Evil", "c1"),
    ("paladin", 4, "I lay on hands on myself", "Lay on Hands", "pc"),
    ("paladin", 4, "I lay hands on Brannoc", "Lay on Hands", "c2"),
    ("paladin", 4, "I use my lay on hands on Brannoc", "Lay on Hands", "c2"),
    ("paladin", 4, "I channel positive energy to heal us", "Channel Positive Energy (heal)",
     ""),
    ("sorc_draconic", 3, "I use my claws", "Claws", ""),
    ("sorc_draconic", 3, "I attack the cutpurse with my claws", "Claws", ""),
    ("sorc_elemental", 3, "I fire an elemental ray at the cutpurse", "Elemental Ray", "c1"),
    ("sorc_elemental", 3, "I use Elemental Ray on the cutpurse", "Elemental Ray", "c1"),
    ("wiz_evocation", 3, "I use Force Missile on the cutpurse", "Force Missile", "c1"),
    ("wiz_evocation", 3, "I cast force missile at the cutpurse", "Force Missile", "c1"),
    ("bard", 3, "I inspire courage", "Inspire Courage", ""),
    ("bard", 3, "I perform Inspire Courage for my allies", "Inspire Courage", ""),
    ("bard", 3, "I use Inspire Competence (diplomacy) on Brannoc",
     "Inspire Competence (diplomacy)", "c2"),
    ("monk", 4, "I use stunning fist on the cutpurse", "Stunning Fist (stunned)", ""),
    ("monk", 4, "I punch the cutpurse with a stunning fist", "Stunning Fist (stunned)", ""),
    ("monk", 4, "I use ki dodge", "Ki Dodge", ""),
    ("monk", 4, "I spend ki for speed", "Ki Speed", ""),
    ("druid", 4, "I wild shape into a wolf", "Wild Shape (wolf)", ""),
    ("druid", 4, "I wildshape into a wolf", "Wild Shape (wolf)", ""),
    ("druid", 4, "I use Wild Shape (wolf)", "Wild Shape (wolf)", ""),
    # Written after the first 41 passed, to test the change rather than confirm it.
    ("cleric", 3, "I call upon my god and channel positive energy", "Channel Energy (heal)",
     ""),
    ("cleric", 3, "Channel Energy (heal)", "Channel Energy (heal)", ""),
    ("cleric", 3, "I quickly channel to heal Brannoc", "Channel Energy (heal)", ""),
    ("cleric", 3, "I channel divine energy", "Channel Energy (heal)", ""),
    ("cleric", 3, "I use battle rage on Brannoc", "Battle Rage", "c2"),
    ("barbarian", 3, "I start raging", "Rage", ""),
    ("barbarian", 3, "I draw my axe and rage", "Rage", ""),
    ("barbarian", 3, "I go into a rage and smash the door", "Rage", ""),
    ("paladin", 4, "I smite the cutpurse", "Smite Evil", "c1"),
    ("paladin", 4, "I use smite on the cutpurse", "Smite Evil", "c1"),
    ("paladin", 4, "I lay hands on myself", "Lay on Hands", "pc"),
    ("monk", 12, "I use Stunning Fist (staggered) on him", "Stunning Fist (staggered)", ""),
    ("monk", 4, "I use stunning fist to fatigue the cutpurse", "Stunning Fist (fatigued)",
     ""),
    ("druid", 4, "I shapeshift into a wolf", "Wild Shape (wolf)", ""),
    ("bard", 3, "I begin to inspire courage", "Inspire Courage", ""),
    ("bard", 3, "I strike up Inspire Courage", "Inspire Courage", ""),
    ("sorc_draconic", 3, "I grow my claws and slash the cutpurse", "Claws", ""),
    ("wiz_evocation", 3, "I hurl a force missile at the cutpurse", "Force Missile", "c1"),
]

NOT_YET = [
    ("bard", 3, "I start a dirge of doom", "Dirge of Doom", 8),
    ("druid", 2, "I wild shape into a wolf", "Wild Shape", 4),
    ("paladin", 1, "I lay on hands on myself", "Lay on Hands", 2),
]

# Decided, and why, where it was borderline:
#   "I rage at the merchant's prices" — "rage at" is the English for anger; rage reaches
#     nobody, so "at"/"against" after a self-only ability is never the ability.
#   "I smite the table with my fist" — a punch. But "I smite the cutpurse" (in HITS) IS
#     Smite Evil: the paladin document lists "smite" as its alias, and the object is a
#     creature here. A thing as the object is not.
#   "I want to use my fire bolt later" — wanting is not doing ("I'll ..." still is).
MISSES = [
    ("barbarian", 3, "I rage at the merchant's prices"),
    ("barbarian", 3, "I ask Brannoc about the barbarian rage"),
    ("barbarian", 3, "My rage is spent, so I sit down by the fire"),
    ("barbarian", 3, "I remember my father's rage"),
    ("barbarian", 3, "Should I rage now?"),
    ("barbarian", 3, 'I shout "I rage at the gods!"'),
    ("barbarian", 3, "I don't rage, I just talk to him"),
    ("paladin", 4, "I smite the table with my fist"),
    ("paladin", 4, "I lay my hands on the table"),
    ("paladin", 4, "I lay the sword on the table"),
    ("cleric", 3, "I channel my anger into my swing"),
    ("cleric", 3, "I wade across the channel"),
    ("cleric", 3, "I ask the priest how to channel energy"),
    ("cleric", 3, "I warm my hands at the fire"),
    ("bard", 3, "I tell Brannoc a story to inspire him"),
    ("bard", 3, "I play a quiet tune for the room"),
    ("monk", 4, "I punch the cutpurse"),
    ("druid", 4, "I watch the wolf"),
    ("sorc_draconic", 3, "I look at the dragon's claws carved on the door"),
    ("wiz_evocation", 3, "I attack the cutpurse with my quarterstaff"),
    ("barbarian", 3, "I'm in a rage about the stolen horse"),
    ("barbarian", 3, "The barbarian's rage frightens the crowd"),
    ("barbarian", 3, "I rage against the dying of the light"),
    ("barbarian", 3, "If I rage, will it help?"),
    ("barbarian", 3, "I should rage soon"),
    ("paladin", 4, "I lay hands on the altar and pray"),
    ("cleric", 3, "I channel the river into the ditch"),
    ("cleric", 3, "I pray to heal Brannoc"),
    ("bard", 3, "I inspire the crowd with a speech"),
    ("monk", 4, "I ask the old monk about stunning fist"),
    ("druid", 4, "I change shape of the clay pot"),
    ("wiz_evocation", 3, "I read about force missile in my book"),
    ("cleric", 3, "I want to use my fire bolt later"),
]


@pytest.mark.parametrize("who,level,text,want,to", HITS)
def test_a_typed_class_ability_reaches_the_engine_by_its_own_name(who, level, text, want,
                                                                  to):
    """4 of 41 typed lines reached the right ability before (module docstring). Each
    line, with the model's reply standing at narrate_only, comes out of the ability doors
    as the `use_ability` the engine resolves to the right document and mode — and aimed
    at the person named, where the ability reaches somebody."""
    pc = _who(who, level)
    scene = _scene(pc)
    raw = _doors([{"op": "narrate_only", "because": "model"}], text, scene)
    assert _resolved(pc, raw) == want, raw
    op = next(r for r in raw if r.get("op") == "use_ability")
    assert (op["params"].get("to") or "") == to, op


@pytest.mark.parametrize("who,level,text,name,arrives", NOT_YET)
def test_an_ability_not_yet_theirs_reaches_the_refusal_that_says_when(who, level, text,
                                                                     name, arrives):
    """0 of 3 before: a 2nd-level druid's "I wild shape into a wolf" declared nothing, so
    the narrator was free to write the wolf. It reaches the engine now, whose refusal
    names the level it arrives at."""
    pc = _who(who, level)
    scene = _scene(pc)
    raw = _doors([{"op": "narrate_only", "because": "model"}], text, scene)
    op = next(r for r in raw if r.get("op") == "use_ability")
    assert op["params"]["ability"].startswith(name)
    e = Engine(scene, dice=Dice(seed=3))
    out = e.run(e.validate([op])).outcomes[-1]
    assert out.status == "refused" and f"level {arrives}" in out.tell, out.tell


@pytest.mark.parametrize("who,level,text", MISSES)
def test_a_sentence_that_only_mentions_an_ability_uses_nothing(who, level, text):
    """The held-out lines fired 3 times of 13 on the first run (module docstring). None of
    these is a use, and none may spend a daily use the player did not choose to spend."""
    pc = _who(who, level)
    raw = _doors([{"op": "narrate_only", "because": "model"}], text, _scene(pc))
    assert _resolved(pc, raw) is None, raw


# --- one lookup, both kinds ---------------------------------------------------------------

def test_find_ability_answers_for_the_class_documents_too():
    """gm/judgement.py's three callers asked `find_ability` and it searched only paths:
    a Fire-domain cleric's "Fire Bolt" was not theirs, so `refuse_unnamed_power` and
    `refuse_declared_creation` would refuse a power the sheet grants. A fighter still has
    no rage."""
    assert leveling.find_ability(_who("cleric", 3), "fire bolt") == ("", "Fire Bolt", [])
    assert leveling.find_ability(_who("barbarian", 1), "Rage")[1] == "Rage"
    assert leveling.find_ability(_bare("fighter", 3), "rage") == ("", "", [])


def test_a_mode_is_named_in_the_players_words_from_the_document():
    """The rest after the name went to `with_choice` as the mode itself: "channel energy
    to harm them" was refused as "no mode called 'harm them'" — only the bracketed key
    worked. Read through the option's own aliases, longest phrase first."""
    pc = _who("cleric", 3)
    for said, mode in (("channel energy to harm them", "harm"),
                       ("channel negative energy to harm them", "harm the living"),
                       ("channel negative energy to heal the undead", "heal undead"),
                       ("channel to heal", "heal")):
        doc, choice = ca.find(pc, said)
        assert doc is not None and choice == mode, (said, choice)
    # A rest that names no option stays as said, so the engine's refusal quotes it.
    _doc, choice = ca.find(pc, "channel energy to juggle")
    assert choice == "juggle"


def test_the_words_for_a_mode_live_in_the_documents_and_nowhere_in_code():
    """The owner's rule for this lane: the mode mapping is data, and the reader names no
    ability. Every name, alias and option alias the documents print is looked for in the
    STRING LITERALS of the routing code (comments may give examples); none may appear."""
    phrases: set[str] = set()
    for file in ca.documents().values():
        for doc in file.get("abilities") or ():
            phrases.update(ca._names_of(doc))
            for key, opt in ((doc.get("choice") or {}).get("options") or {}).items():
                phrases.add(ca._norm(key))
                phrases.update(ca._norm(a) for a in (opt or {}).get("aliases") or ())
    phrases.discard("")
    # Walked as an AST (tests/test_suite_isolation.py caps source-text pins): the string
    # constants inside the routing functions, docstrings excluded.
    wanted = {"gm/judgement.py": {"_typed_class_ability", "_with_class_ability",
                                  "_follows_as_a_use", "_choice_said", "inject_ability"},
              "rules/class_abilities.py": {"find", "option_for", "vocabulary", "words_of"}}
    literals = []
    for path, names in wanted.items():
        tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        found = [n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name in names]
        assert {n.name for n in found} == names, (path, names - {n.name for n in found})
        for fn in found:
            doc = ast.get_docstring(fn, clean=False)
            for node in ast.walk(fn):
                if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                        and node.value != doc):
                    literals.append(node.value.lower())
    for name in ("_ABILITY_VERBS", "_THEN_ON", "_PREPOSITIONS", "_POINTING",
                 "_DETERMINERS", "_PRONOUNS"):
        value = getattr(judgement, name)
        literals.append(" ".join(sorted(value)) if isinstance(value, frozenset) else value)
    for lit in literals:
        for p in phrases:
            assert not re.search(r"(?<![a-z])" + re.escape(p) + r"(?![a-z])", lit), (
                f"{p!r} is written in the routing code ({lit[:60]!r}); it belongs in the "
                f"document's `aliases`.")


def test_an_alias_naming_two_options_is_refused_with_the_fix_named():
    """An alias two options both answer to is decided by dict order — invisible from
    the table. The validator names it."""
    doc = json.loads(json.dumps(ca.documents()["cleric"]))
    opts = doc["abilities"][0]["choice"]["options"]
    opts["heal undead"]["aliases"].append("heal")
    problems = ca.validate_documents({"cleric": doc})
    assert any("'heal' names both option" in p for p in problems), problems
    assert ca.validate_documents() == []


# --- the model's guesses, and the order of the deeds ----------------------------------------

def test_the_models_guess_at_what_the_ability_does_is_dropped():
    """With no `use_ability` the model's own ops were the only mechanics: a `damage` it
    authored, or an `attack` standing in for a ray. The ability is the one source of its
    numbers now."""
    pc = _who("cleric", 3)
    scene = _scene(pc)
    raw = [{"op": "attack", "actor": "pc", "target": "c1", "because": "m"},
           {"op": "damage", "actor": "pc", "target": "c1", "because": "m",
            "params": {"amount": "2d6"}},
           {"op": "narrate_only", "because": "m"}]
    out = judgement.inject_ability(raw, "use my Fire Bolt on the cutpurse", scene)
    assert sorted(r["op"] for r in out) == ["narrate_only", "use_ability"], out
    used = next(r for r in out if r["op"] == "use_ability")
    assert used["params"] == {"ability": "Fire Bolt", "to": "c1"}


def test_rage_goes_in_front_of_the_blow_it_is_for():
    """"I rage and attack the cutpurse": the attack is a deed of its own and stays, and
    the rage is put before it so the swing feels the Strength."""
    pc = _who("barbarian", 3)
    scene = _scene(pc)
    raw = [{"op": "attack", "actor": "pc", "target": "c1", "because": "m"}]
    out = judgement.inject_ability(raw, "I rage and attack the cutpurse", scene)
    assert [r["op"] for r in out] == ["use_ability", "attack"]


def test_the_schema_asks_for_the_ability_the_player_declared():
    """`declared_ops` runs the same door, so the model is required to emit the op."""
    pc = _who("barbarian", 3)
    assert "use_ability" in judgement.declared_ops("I rage", _scene(pc))
    assert "use_ability" not in judgement.declared_ops("I rage at the merchant's prices",
                                                       _scene(pc))


# --- through the engine: the pool moves and the tell says the roll ------------------------

def _run(scene, raw):
    """Run the turn inside a fight already joined: outside one, a harmful ability's first
    use opens the battle and spends nothing (`Engine._ability_gate`, the battle gate)."""
    e = Engine(scene, dice=Dice(seed=7))
    e.run(e.validate([{"op": "begin_encounter", "params": {
        "sides": {"pc": ["pc", "c2"], "them": ["c1"]}}}]))
    res = e.run(e.validate(raw))
    while res.awaiting:
        res = e.resume(int(res.awaiting["max"]))
    return res


def test_a_typed_fire_bolt_spends_its_use_and_rolls():
    """The live defect itself: "use my Fire Bolt" left the pool 6/6. Typed, it spends a
    use and the tell carries the roll."""
    from rules import classes as classes_mod

    pc = _who("cleric", 3)
    classes_mod.apply(pc)
    scene = _scene(pc)
    raw = _doors([{"op": "narrate_only", "because": "m"}],
                 "use my Fire Bolt on the cutpurse", scene)
    before = pc.pool("fire bolt").current
    res = _run(scene, raw)
    out = next(o for o in res.outcomes if o.op == "use_ability")
    assert out.status != "refused", out.tell
    assert pc.pool("fire bolt").current == before - 1
    # The roll is in the record and the tell: "ranged touch attack misses the cutpurse
    # (7 against touch AC 13)" on this seed.
    assert out.rolls and re.search(r"\d+ against touch AC \d+", out.tell), out.tell


def test_a_typed_channel_to_harm_the_living_rolls_damage_with_a_save():
    pc = _who("cleric", 3)
    scene = _scene(pc)
    raw = _doors([{"op": "narrate_only", "because": "m"}],
                 "I channel negative energy to harm them", scene)
    res = _run(scene, raw)
    out = next(o for o in res.outcomes if o.op == "use_ability")
    assert out.status != "refused", out.tell
    assert pc.pool("channel energy").current == pc.pool("channel energy").maximum - 1
    assert any(e.get("kind") == "damage" for e in out.effects), out.effects


def test_a_typed_bolt_with_no_uses_left_is_the_engines_refusal_and_the_guard_sees_it():
    """Unusable, typed: the refusal reaches the page as the engine's tell — and because a
    `use_ability` now sits in the turn's outcomes, the beat verifier judges a page that
    says the cutpurse was hurt anyway. Before the fix there was no ability op at all, the
    verifier's harm row only judges a turn where something rolled harm, and the invented
    bolt went unjudged."""
    from rules import classes as classes_mod

    pc = _who("cleric", 3)
    classes_mod.apply(pc)
    pc.pool("fire bolt").current = 0
    scene = _scene(pc)
    raw = _doors([{"op": "narrate_only", "because": "m"}],
                 "use my Fire Bolt on the cutpurse", scene)
    res = _run(scene, raw)
    out = next(o for o in res.outcomes if o.op == "use_ability")
    assert out.status == "refused" and out.tell, out.tell

    facts = beat_verify.Facts(
        start="the market", end="the market", places=("the market",),
        people=(beat_verify.Person(ref="c1", name="the cutpurse"),),
        outcomes=tuple({"op": o.op, "status": o.status, "effects": o.effects,
                        "tell": o.tell} for o in res.outcomes))
    claim = beat_verify.Claim(category="harm", slots={"who": "c1", "how": "hurt"},
                              quote="slams into the cutpurse", valid=True)
    found = beat_verify.diff([claim], facts)
    assert any(d.category == "harm" for d in found), found
    # The gap it closes: the same page on a turn with no ability op is not judged.
    bare_facts = beat_verify.Facts(
        start="the market", end="the market", places=("the market",),
        people=facts.people, outcomes=())
    assert beat_verify.diff([claim], bare_facts) == []

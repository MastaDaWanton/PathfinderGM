"""Animals and Handle Animal (rules/animals.py, round 3, 2026-11-22).

The owner's ruling that day: "Companions can still obey in character but companions that
are animals/beasts are unable to communicate without the use of magic. So handle animal
functions almost as diplomacy in many ways." What it replaced, measured on the round-3
base (integrate/0.5.1-impl 0eee57ff):

  * a `say` to a horse opened a conversation with it ("You are in conversation with the
    bay") and counted towards its regard, like talk with a person;
  * Diplomacy at a dog rolled against the dog's attitude DC and moved it — the CRB says
    "You cannot use Diplomacy against a creature that does not understand you or has an
    Intelligence of 3 or less";
  * Handle Animal had no resolved use at all (its card: "teaching new tricks, rearing or
    pushing an animal are not in play yet"); wild empathy was a bare class-table string;
  * combat training was not recorded: `goods.deliver` dropped "(combat-trained)" from the
    name and nothing else, so a 300 gp warhorse and a 200 gp plough horse were the same
    animal, and nobody had to control either in a fight.

Every behaviour test goes through `Engine.run` and reads the sheet and the tells.
"""
from __future__ import annotations

import pytest

from rules import animals, bodyskills, inprogress, states
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc


class _Faces(Dice):
    """Every d20 whose label holds a key lands on that key's face; the rest on `rest`."""

    def __init__(self, faces: dict | None = None, rest: int = 10):
        super().__init__(seed=20261122)
        self.faces, self.rest = dict(faces or {}), rest
        self.labels: list[str] = []

    def roll(self, notation, modifiers=None, label="", visibility="hidden"):
        if str(notation).lstrip("1").startswith("d20"):
            self.labels.append(label or "")
            face = next((f for k, f in self.faces.items() if k in (label or "")), self.rest)
            return self.given(face, modifiers, label)
        return super().roll(notation, modifiers, label, visibility)


def _travels(animal):
    animal.apply_effect(ActiveEffect(name="travels with you", kind="bond",
                                     key=f"company:{animal.ref}:travels",
                                     source=f"company:{animal.ref}", origin="bought:pc",
                                     tags=(states.TRAVELS_WITH_YOU,)))
    return animal


def _scene(*beasts, faces=None, rest=10, ranks=0, druid=False):
    scene = Scene(location_id="5bbd0c40345f")
    pc = scene.add(load_pc("fixtures/pc-kesst.json"))
    if ranks:
        pc.ranks["handle animal"] = ranks
    if druid:
        pc.char_class, pc.level = "druid", 5
    made = [scene.add(instantiate(t, scene=scene, name=n)) for t, n in beasts]
    engine = Engine(scene, _Faces(faces, rest))
    return scene, engine, pc, made


def _run(engine, *raws):
    res = engine.run(engine.validate([dict(r, visibility="hidden") for r in raws]))
    assert not res.awaiting
    return res.outcomes


def _check(**params):
    target = params.pop("target", None)
    out = {"op": "check", "actor": "pc", "params": params}
    if target:
        out["target"] = target
    return out


# --- words do not reach them ----------------------------------------------------------------

def test_words_said_to_a_horse_reach_nothing_and_open_no_conversation():
    """Measured on the base: "You are in conversation with the bay", and the regard rose."""
    scene, engine, pc, (horse,) = _scene(("horse", "the bay"))
    out = _run(engine, {"op": "say", "actor": "pc",
                        "params": {"words": "Easy now, girl", "to": horse.ref}})[0]
    assert "does not understand words" in out.tell
    assert "conversation" not in out.tell
    assert not horse.has_state(states.TALKING)
    assert not any(e.get("kind") == "regard" for e in out.effects)


def test_a_greeting_to_a_dog_is_refused_and_a_person_still_talks():
    scene, engine, pc, (dog, thug) = _scene(("dog", "the dog"), ("thug", "the drover"))
    out = _run(engine, {"op": "greet", "actor": "pc", "params": {"who": dog.ref}})[0]
    assert "does not understand words" in out.tell and not dog.has_state(states.TALKING)
    out = _run(engine, {"op": "greet", "actor": "pc", "params": {"who": thug.ref}})[0]
    assert thug.has_state(states.TALKING)


def test_the_book_records_who_understands_speech():
    """A beast with no language understands none: every bestiary animal prints `[]`; a
    griffon prints "Common (cannot speak)" and is understood."""
    scene, engine, pc, (horse, griffon) = _scene(("horse", "the bay"),
                                                 ("griffon", "the griffon"))
    assert animals.wordless(horse) and not animals.understands(horse, pc)
    assert not animals.wordless(griffon) and animals.understands(griffon, pc)


def test_speak_with_animals_lets_words_reach_an_animal():
    """The magic the ruling names: the spell's permission, held through the applicator."""
    scene, engine, pc, (horse,) = _scene(("horse", "the bay"))
    pc.apply_effect(ActiveEffect(name="speak with animals", kind="buff", key="swa",
                                 source="spell:speak-with-animals",
                                 origin="spell:speak-with-animals", duration="rounds",
                                 rounds_left=50, tags=("permission.speak_with_animals",)))
    out = _run(engine, {"op": "say", "actor": "pc",
                        "params": {"words": "Which way did the riders go?",
                                   "to": horse.ref}})[0]
    assert "does not understand" not in out.tell
    assert horse.has_state(states.TALKING)


def test_the_spell_grants_its_permission_on_a_cast():
    """speak-with-animals' permission spec names its tag, so the cast door runs it; one
    that names none (295 of 296 permission specs) stays told."""
    scene, engine, pc, _ = _scene()
    assert engine._executes({"type": "permission", "tag": "speak_with_animals"})
    assert not engine._executes({"type": "permission", "target": "May walk on walls."})


# --- Diplomacy cannot reach them; wild empathy can --------------------------------------------

def test_diplomacy_at_a_dog_is_refused_with_the_fix_named():
    scene, engine, pc, (dog,) = _scene(("dog", "the dog"))
    out = _run(engine, _check(skill="diplomacy", target=dog.ref))[0]
    assert "Diplomacy cannot move the dog" in out.tell and "Handle Animal" in out.tell
    assert not out.rolls and dog.ref not in scene.swayed


def test_wild_empathy_calms_a_hostile_wolf_through_diplomacys_own_machinery():
    """CRB, Druid: 1d20 + druid level + Cha, against the Diplomacy DC for its attitude
    (hostile 25 + Cha), steps as Diplomacy's, and once a day. Kesst made a 5th-level druid:
    d20 18 + 5 + Cha 2 = 25 against hostile 25 + Cha -2 = 23, made by 2: one step."""
    scene, engine, pc, (wolf,) = _scene(("wolf", "the wolf"), faces={"Wild empathy": 18},
                                        druid=True)
    engine._set_attitude(wolf, "hostile", None, "test")
    out = _run(engine, _check(skill="diplomacy", target=wolf.ref))[0]
    assert out.dc["value"] == 25 + wolf.ability_mod("cha")
    assert out.rolls[0].total == 18 + 5 + pc.ability_mod("cha")
    assert "wild empathy" in out.tell
    from rules import attitude

    assert attitude.of(wolf) == "unfriendly"
    again = _run(engine, _check(skill="diplomacy", target=wolf.ref))[0]
    assert "once today" in again.tell and not again.rolls


def test_wild_empathy_is_a_minute_of_calm_not_a_fights_round():
    scene, engine, pc, (wolf,) = _scene(("wolf", "the wolf"), druid=True)
    engine._ensure_encounter("pc")
    out = _run(engine, _check(skill="diplomacy", target=wolf.ref))[0]
    assert "not a fight's round" in out.tell and not out.rolls


# --- handle and push ---------------------------------------------------------------------------

def _fight_with_dog(faces=None, ranks=4):
    scene, engine, pc, (dog, foe) = _scene(("dog", "Brindle"), ("thug", "the foe"),
                                           faces=faces, ranks=ranks)
    _travels(dog)
    animals.train_purpose(dog, "fighting", by="test")
    engine._ensure_encounter("pc", target=foe.ref)
    scene.acted.update(scene.actors)
    return scene, engine, pc, dog, foe


def test_handling_a_trained_dog_to_attack_is_dc_ten_a_move_action_and_its_command():
    scene, engine, pc, dog, foe = _fight_with_dog(faces={"Handle Animal": 8})
    out = _run(engine, _check(skill="handle animal", use="handle", trick="attack",
                              at=foe.ref, target=dog.ref))[0]
    assert out.dc["value"] == 10 and out.verdict == "success"
    assert animals.command(dog) == ("attack", foe.ref, False)
    assert dog.has_state("handled.attack")
    assert scene.move_spent.get("pc") == scene.round
    assert "will attack the foe on its turn" in out.tell


def test_the_dogs_own_turn_is_held_to_the_attack_it_was_handled_to_make():
    from gm import companions

    scene, engine, pc, dog, foe = _fight_with_dog(faces={"Handle Animal": 8})
    _run(engine, _check(skill="handle animal", use="handle", trick="attack", at=foe.ref,
                        target=dog.ref))
    idle = [{"op": "move", "actor": dog.ref, "params": {"square": [1, 1]}}]
    assert "handled to attack the foe" in companions.handled_unheeded(scene, dog.ref, idle)
    bite = [{"op": "attack", "actor": dog.ref, "target": foe.ref}]
    assert companions.handled_unheeded(scene, dog.ref, bite) == ""
    # And its words-free character: tricks and command, never the player's sentences.
    assert companions.orders_for(scene, dog.ref, [{"who": "player", "text":
                                                   "Brindle, get him!"}]) == []
    assert "attack the foe" in companions.turn_facts(scene, dog, [])


def test_a_trick_it_does_not_know_is_a_push_at_dc_25_and_a_full_round():
    scene, engine, pc, dog, foe = _fight_with_dog(faces={"Handle Animal": 20})
    out = _run(engine, _check(skill="handle animal", use="handle", trick="fetch",
                              target=dog.ref))[0]
    assert out.dc["value"] == 25 and "does not know fetch, so it is pushed" in out.tell
    assert animals.command(dog) == ("fetch", "", True)
    assert scene.standard_spent.get("pc") == scene.round


def test_a_hurt_animal_is_two_harder_to_handle():
    scene, engine, pc, dog, foe = _fight_with_dog(faces={"Handle Animal": 15})
    dog.hp -= 1
    out = _run(engine, _check(skill="handle animal", trick="attack", at=foe.ref,
                              target=dog.ref))[0]
    assert out.dc["value"] == 12


def test_untrained_hands_get_a_charisma_check_on_a_domestic_animal_only():
    scene, engine, pc, (dog, wolf) = _scene(("dog", "the dog"), ("wolf", "the wolf"))
    animals.train_purpose(dog, "riding", by="test")
    out = _run(engine, _check(skill="handle animal", trick="come", target=dog.ref))[0]
    assert out.rolls and "Charisma check" in out.rolls[0].label
    out = _run(engine, _check(skill="handle animal", trick="come", target=wolf.ref))[0]
    assert "no training in Handle Animal" in out.tell and not out.rolls


def test_a_hostile_animal_takes_no_command():
    scene, engine, pc, (wolf,) = _scene(("wolf", "the wolf"), ranks=4)
    engine._set_attitude(wolf, "hostile", None, "test")
    out = _run(engine, _check(skill="handle animal", use="push", trick="stay",
                              target=wolf.ref))[0]
    assert "hostile and takes no command" in out.tell and not out.rolls


# --- teaching and training: In progress --------------------------------------------------------

def test_teaching_a_trick_takes_a_week_in_progress_and_collecting_lays_the_trick():
    scene, engine, pc, (dog,) = _scene(("dog", "Brindle"), faces={"Handle Animal": 15},
                                       ranks=4)
    _travels(dog)
    out = _run(engine, _check(skill="handle animal", use="teach", trick="attack",
                              target=dog.ref))[0]
    assert out.dc["value"] == 20 and out.verdict == "success"
    assert not animals.knows(dog, "attack")
    rows = inprogress.entries(pc, scene.clock_minutes)
    assert len(rows) == 1 and rows[0]["ready_in"] == 7 * 24 * 60
    animals.lend_scene(scene)
    early = inprogress.collect(pc, rows[0]["key"], now=scene.clock_minutes, here=None)
    assert early["ok"] is False
    got = inprogress.collect(pc, rows[0]["key"], now=scene.clock_minutes + 7 * 1440,
                             here=None)
    assert got["ok"] and "learned the trick: attack" in got["said"]
    assert animals.knows(dog, "attack") and not inprogress.entries(pc, 10 ** 9)


def test_a_failed_lesson_holds_the_animal_half_the_week_and_teaches_nothing():
    scene, engine, pc, (dog,) = _scene(("dog", "Brindle"), faces={"Handle Animal": 1},
                                       ranks=1)
    _travels(dog)
    out = _run(engine, _check(skill="handle animal", use="teach", trick="seek",
                              target=dog.ref))[0]
    assert out.verdict == "failure"
    row = inprogress.entries(pc, scene.clock_minutes)[0]
    assert row["ready_in"] == 7 * 24 * 60 // 2
    animals.lend_scene(scene)
    got = inprogress.collect(pc, row["key"], now=scene.clock_minutes + 7 * 1440, here=None)
    assert got["ok"] and "learned nothing" in got["said"] and not animals.knows(dog, "seek")


def test_an_animal_of_int_one_or_two_holds_only_so_many_tricks():
    scene, engine, pc, (dog,) = _scene(("dog", "Brindle"), ranks=4)
    _travels(dog)
    for t in ("attack", "come", "down", "fetch", "heel", "seek"):
        animals.teach_trick(dog, t, "test")
    out = _run(engine, _check(skill="handle animal", use="teach", trick="stay",
                              target=dog.ref))[0]
    assert "all the tricks" in out.tell and not out.rolls


# --- bought mounts and combat training ---------------------------------------------------------

def _bought(name):
    from rules import goods

    scene = Scene(location_id="5bbd0c40345f")
    pc = scene.add(load_pc("fixtures/pc-kesst.json"))
    found = next(g for g in goods.stables_goods() if g.name == name)
    goods.deliver(scene, pc, found, 1)
    return scene, pc, next(a for a in scene.people.values() if a is not pc)


def test_a_bought_warhorse_is_combat_trained_and_a_plain_one_is_trained_to_ride():
    """Before: "(combat-trained)" was cut from the name and nothing recorded it."""
    _, _, war = _bought("heavy horse (combat-trained)")
    _, _, plain = _bought("heavy horse")
    assert animals.combat_trained(war) and war.has_state("trained.combat-riding")
    assert not animals.combat_trained(plain) and plain.has_state("trained.riding")
    assert animals.known(plain) == ["come", "heel", "stay"]


def _mounted(trained: bool, faces):
    scene, engine, pc, (horse, foe) = _scene(("heavy-horse", "the bay"), ("thug", "the foe"),
                                             faces=faces)
    _travels(horse)
    if trained:
        animals.train_purpose(horse, "combat riding", by="test")
    engine._ensure_encounter("pc", target=foe.ref)
    scene.acted.update(scene.actors)
    scene.positions["pc"], scene.positions[horse.ref], scene.positions[foe.ref] = \
        (5, 5), (5, 5), (6, 5)
    horse.apply_effect(ActiveEffect(name="ridden", kind="situation", key="ridden",
                                    source="rule:ride", origin="rule:ride",
                                    tags=(bodyskills.RIDDEN,), payload={"by": "pc"}))
    pc.apply_effect(ActiveEffect(name="riding", kind="situation", key="mounted",
                                 source="rule:ride", origin="rule:ride",
                                 tags=(bodyskills.MOUNTED,), payload={"mount": horse.ref}))
    scene.resync_zones()
    return scene, engine, pc, horse, foe


def test_an_untrained_mount_must_be_controlled_before_the_rider_strikes():
    """CRB, Ride: DC 20, a move action; "If you fail the Ride check, you can do nothing
    else in that round." A Ride roll of 1 + Kesst's Ride: missed, and no blow."""
    scene, engine, pc, horse, foe = _mounted(False, {"Ride check (control": 1})
    out = _run(engine, {"op": "attack", "actor": "pc", "target": foe.ref})
    assert out[0].status == "prevented" and "cannot control it" in out[0].tell
    assert scene.standard_spent.get("pc") == scene.round


def test_a_controlled_untrained_mount_costs_the_move_and_the_blow_lands():
    scene, engine, pc, horse, foe = _mounted(False, {"Ride check (control": 20})
    out = _run(engine, {"op": "attack", "actor": "pc", "target": foe.ref})
    said = " ".join(o.tell for o in out)
    assert "keeps it in hand" in said
    assert any(o.op == "attack" and o.status == "resolved" for o in out)
    assert scene.move_spent.get("pc") == scene.round


def test_a_combat_trained_mount_needs_no_roll():
    scene, engine, pc, horse, foe = _mounted(True, {})
    engine.dice.labels.clear()
    out = _run(engine, {"op": "attack", "actor": "pc", "target": foe.ref})
    assert not any("control" in label for label in engine.dice.labels)
    assert any(o.op == "attack" and o.status == "resolved" for o in out)


# --- the druid's companion: the link, its bonus tricks ------------------------------------------

def test_a_companions_bonus_tricks_are_its_trick_tags_and_the_link_makes_handling_free():
    from rules import animal_companion as ac

    scene, engine, pc, _ = _scene(druid=True, faces={"Handle Animal": 6})
    wolf = ac.make(scene, pc, "wolf", tricks=["attack", "come"])
    for t in ac.bond_of(wolf).payload["tricks"]:
        assert animals.knows(wolf, t)
    foe = scene.add(instantiate("thug", scene=scene, name="the foe"))
    engine._ensure_encounter("pc", target=foe.ref)
    scene.acted.update(scene.actors)
    trick = ac.bond_of(wolf).payload["tricks"][0]
    out = _run(engine, _check(skill="handle animal", trick=trick, target=wolf.ref,
                              **({"at": foe.ref} if trick == "attack" else {})))[0]
    assert out.verdict == "success"
    assert any(m.type == "circumstance" and m.value == 4 for m in out.rolls[0].modifiers)
    assert scene.move_spent.get("pc") != scene.round        # free, through the link


# --- the reader: words to an animal are its handling ---------------------------------------------

def test_words_to_an_animal_declare_a_handle_animal_check_not_a_say():
    from gm import acts_to_ops

    scene, engine, pc, (dog,) = _scene(("dog", "Brindle"))
    frame = {"actions": [{"span": "Brindle, sit", "act": "talk", "target": "Brindle",
                          "says": "sit"}]}
    row = acts_to_ops.table(frame, scene)[0]
    assert row.ops == ["check"] and row.skill == "handle animal"


def test_the_declared_check_offers_the_tricks_as_a_closed_list():
    from gm import prompts

    shape = prompts._declared_op("check", ("pc", "c1"), (), skill="handle animal")
    props = shape["properties"]["params"]["properties"]
    assert set(animals.tricks()) <= set(props["trick"]["enum"])
    assert "trick" in shape["properties"]["params"]["required"]
    plain = prompts._declared_op("check", ("pc",), (), skill="perception")
    assert "trick" not in plain["properties"]["params"]["properties"]

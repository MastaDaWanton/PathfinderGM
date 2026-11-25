"""Feat loop batch 2, the styles lane: combat styles as a stance, and luck on the d20.

Batch 1 found the machinery missing. A style feat's follow-ups ("while using Crane
Style") had no stance to ask, so Snake Style's immediate Sense Motive and every follow-up
of the 50 in this list was a name on the sheet; and no feat could reroll a die or add to
one after it landed, so Dauntless Destiny, Close Call, Inexplicable Luck, Lucky Halfling,
Strong Comeback and Surge of Success changed nothing (worklist 2026-11-22). Each test
below rolls the real op, or reads the sheet the roll reads, and names the number it pins.
"""
from __future__ import annotations

import pytest

from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc, situated

THUG = "the thug"


class Faces(Dice):
    """d20s land on the faces given, in order, for rolls whose label holds `match` (or
    every d20 when no match is given); everything else rolls as usual."""

    def __init__(self, faces=(), match=""):
        super().__init__(seed=20261122)
        self.faces, self.match = list(faces), match

    def roll(self, notation, modifiers=None, label="", visibility="hidden"):
        if notation.strip() == "1d20" and self.faces and self.match in (label or ""):
            return self.given(self.faces.pop(0), modifiers, label)
        return super().roll(notation, modifiers, label, visibility)


def _monk(*feats, level=1, wis=14, ranks=None):
    """Borin's sheet as an unarmed monk: no shield, no armour, both hands free. Int 30 so
    the ranks the styles ask for fit a 1st-level sheet (a copy of it is validated)."""
    pc = load_pc("fixtures/pc-borin.json")
    pc.char_class, pc.level = "monk", level
    pc.shield, pc.armour, pc.equipped = "none", "none", "unarmed"
    pc.abilities["wis"], pc.abilities["int"] = wis, 30
    pc.ranks = dict(ranks or {})
    pc.feats = ["improved unarmed strike", "dodge", "combat expertise", *feats]
    return pc


def _fight(pc, dice=None, thug_feats=()):
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(pc)
    thug = instantiate("thug", scene=scene, name=THUG)
    thug.feats = list(thug.feats) + list(thug_feats)
    scene.add(thug)
    engine = Engine(scene, dice or Dice(seed=7))
    engine._ensure_encounter("pc")
    scene.positions["pc"], scene.positions[thug.ref] = (6, 10), (7, 10)
    scene.resync_zones()
    return scene, engine, pc, thug


def _run(engine, raw, faces=()):
    res = engine.run(engine.validate(raw))
    faces = list(faces)
    while res.awaiting:
        res = engine.resume(faces.pop(0) if faces else min(10, res.awaiting["max"]))
    return res


def _enter(engine, style, who="pc"):
    return _run(engine, [{"op": "style", "actor": who, "params": {"style": style}}])


def _named(mods, name: str) -> int:
    return sum(m.value for m in mods if str(m.source).startswith(name))


# --- the stance ------------------------------------------------------------------------

def test_a_first_level_monk_qualifies_by_the_printed_monk_level():
    """"base attack bonus +2 or monk level 1st" (Crane Style): the extractor kept only the
    BAB half, so a 1st-level monk (BAB +0) was refused; a 1st-level fighter still is."""
    from rules import feats

    assert feats.meets(_monk(), "crane-style")["ok"]
    fighter = load_pc("fixtures/pc-borin.json")
    fighter.feats += ["improved unarmed strike", "dodge"]
    unmet = feats.meets(fighter, "crane-style")["unmet"]
    assert unmet == ["base attack bonus +2 or monk level 1"]


def test_a_style_is_one_stance_entered_in_a_fight_and_left_with_it():
    """Out of a fight: refused ("cannot use a style feat before combat begins"). In one:
    the stance is `style.crane-style`; a second style takes the first off; the fight's end
    takes the last off, each said."""
    pc = _monk("crane style", "snake style", level=3,
               ranks={"acrobatics": 1, "sense motive": 3})
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(pc)
    scene.add(instantiate("thug", scene=scene, name=THUG))
    engine = Engine(scene, Dice(seed=1))
    out = _enter(engine, "crane-style").outcomes[0]
    assert out.status == "refused" and "never before it begins" in out.tell
    engine._ensure_encounter("pc")
    assert _enter(engine, "crane-style").outcomes[0].tell == \
        "Borin Achereth settles into Crane Style."
    assert pc.has_state("style.crane-style")
    said = _enter(engine, "snake-style").outcomes[0].tell
    assert said == "Borin Achereth settles into Snake Style, leaving Crane Style."
    assert pc.has_state("style.snake-style") and not pc.has_state("style.crane-style")
    scene.end_encounter()
    assert not pc.has_state("style")
    assert scene.log[-1]["tell"] == "Borin Achereth lets Snake Style go with the fight over."


def test_the_declare_section_offers_each_known_style_as_a_swift_action():
    """The bar reads the engine's list (rules/styles.py, the index's `style` tag): Crane
    and Snake Style are offered, swift, posting the `style` op; the one stood in says so;
    a feat that is no style (Dodge) is not offered."""
    from play.views import _attack_options

    pc = _monk("crane style", "snake style", level=3,
               ranks={"acrobatics": 1, "sense motive": 3})
    scene, engine, pc, thug = _fight(pc)
    _enter(engine, "snake-style")
    styles = {o["id"]: o for o in _attack_options(pc)["options"]
              if o["id"].startswith("style:")}
    assert set(styles) == {"style:crane-style", "style:snake-style"}
    crane = styles["style:crane-style"]
    assert (crane["shape"], crane["action"], crane["why"]) == ("act", "swift", "")
    assert crane["op"] == {"op": "style", "params": {"style": "crane-style"}}
    assert styles["style:snake-style"]["why"] == "You are in this style."


def test_a_creature_that_knows_a_style_takes_it_on_its_first_turn():
    """`styles.npc_stance`: the thug with Crane Style puts the stance in front of its plan
    once, and never again while it stands in it."""
    from rules import styles

    scene, engine, pc, thug = _fight(_monk())
    thug.feats += ["improved unarmed strike", "dodge", "crane style"]
    thug.char_class = "monk"
    plan = [{"op": "attack", "actor": thug.ref, "target": "pc"}]
    got = styles.npc_stance(scene, thug.ref, plan)
    assert got[0] == {"op": "style", "actor": thug.ref, "params": {"style": "crane-style"},
                      "because": "its fighting stance"}
    _run(engine, got[:1])
    assert styles.npc_stance(scene, thug.ref, plan) == plan


# --- Crane ------------------------------------------------------------------------------

def _defensive(engine, pc):
    engine._lay_attack_stances(pc, ("fighting_defensively",))


def test_crane_style_halves_the_defensive_penalty_and_adds_a_dodge_in_the_style():
    """Fighting defensively: -4 to hit, +2 dodge. Crane Style: "only a -2 penalty" (any
    time), and "+1 dodge" more only while in the style."""
    pc = _monk("crane style")
    scene, engine, pc, thug = _fight(pc)
    plain_hit, plain_ac = sum(m.value for m in pc.attack_modifiers("unarmed")), pc.ac()
    _defensive(engine, pc)
    assert sum(m.value for m in pc.attack_modifiers("unarmed")) - plain_hit == -2
    assert pc.ac() - plain_ac == 2
    _enter(engine, "crane-style")
    assert pc.ac() - plain_ac == 3


def test_crane_riposte_takes_the_penalty_to_minus_one_in_the_style():
    pc = _monk("crane style", "crane wing", "crane riposte", level=7)
    scene, engine, pc, thug = _fight(pc)
    plain = sum(m.value for m in pc.attack_modifiers("unarmed"))
    _enter(engine, "crane-style")
    _defensive(engine, pc)
    assert sum(m.value for m in pc.attack_modifiers("unarmed")) - plain == -1


def _thug_swings(engine, thug, face):
    engine.dice = Faces([face], match="Attack")
    return _run(engine, [{"op": "attack", "actor": thug.ref, "target": "pc",
                          "visibility": "hidden"}])


def test_crane_wing_meets_the_first_blow_with_four_dodge_and_only_the_first():
    """Fighting defensively in Crane Style with a hand free: the round's first melee blow
    is rolled against AC +4; the second against the plain AC."""
    pc = _monk("crane style", "crane wing", level=5)
    scene, engine, pc, thug = _fight(pc)
    _enter(engine, "crane-style")
    _defensive(engine, pc)
    first = _thug_swings(engine, thug, 2).outcomes[0]
    assert "Crane Wing, +4 dodge" in first.tell
    assert "+4 dodge (Crane Wing)" in first.tell
    second = _thug_swings(engine, thug, 2).outcomes[0]
    assert "Crane Wing" not in second.tell


def test_crane_wing_under_total_defense_deflects_a_hit_and_riposte_answers_it():
    """Total defense: a blow that would hit does nothing; with Crane Riposte the crane
    gets its attack of opportunity at the attacker, spliced behind the blow."""
    pc = _monk("crane style", "crane wing", "crane riposte", level=7)
    scene, engine, pc, thug = _fight(pc)
    _enter(engine, "crane-style")
    _run(engine, [{"op": "total_defense", "actor": "pc"}])
    hp = pc.hp
    res = _thug_swings(engine, thug, 19)
    blow = next(o for o in res.outcomes if o.actor == thug.ref and o.op == "attack")
    assert "deflects" in blow.tell and pc.hp == hp
    back = [o for o in res.outcomes if o.op == "attack" and o.actor == "pc"]
    assert back, "Crane Riposte's attack of opportunity was not made"


# --- Scorpion, Second Chance -------------------------------------------------------------

def test_scorpion_style_hobbles_a_foe_that_fails_its_fortitude():
    """One unarmed strike as the attack action; a hit and a failed Fortitude save leave the
    thug's speed at 5 feet for Wisdom-modifier rounds (Wis 14: 2)."""
    pc = _monk("scorpion style", wis=14)
    scene, engine, pc, thug = _fight(pc)
    engine.dice = Faces([1], match="save against")
    res = _run(engine, [{"op": "attack", "actor": "pc", "target": thug.ref,
                         "visibility": "hidden",
                         "params": {"scorpion_style": True, "weapon": "unarmed"}}], [18, 3])
    assert thug.has_state("state.hampered.speed-5")
    assert thug.speed_feet == 5
    hob = next(e for e in thug.effects if e.key == "hobbled")
    assert hob.rounds_left == 2
    from rules.intents import IntentError

    with pytest.raises(IntentError, match="cannot ride a full attack"):
        engine.validate([{"op": "attack", "actor": "pc", "target": thug.ref,
                          "params": {"scorpion_style": True, "full_attack": True}}])
    del res


def test_second_chance_rerolls_the_first_miss_and_forgoes_the_rest():
    """BAB +6: a full attack is two blows. The first misses on a 2 and is rolled again;
    without Improved Second Chance the second blow is never rolled. (Natural 1s: the
    second chance is a miss's, the wild one's too.)"""
    pc = load_pc("fixtures/pc-borin.json")
    pc.level, pc.abilities["int"] = 6, 13
    pc.feats += ["combat expertise", "second chance"]
    scene, engine, pc, thug = _fight(pc)
    engine.dice = Faces([1, 1, 1], match="Attack")
    res = _run(engine, [{"op": "attack", "actor": "pc", "target": thug.ref,
                         "visibility": "hidden",
                         "params": {"full_attack": True, "second_chance": True}}])
    out = next(o for o in res.outcomes if o.op == "attack")
    attacks = [r for r in out.rolls if "Attack" in (r.label or "")]
    assert len(attacks) == 2 and "giving up the rest of the attack" in out.tell


def test_improved_second_chance_keeps_the_rest_of_the_attack_at_minus_five():
    pc = load_pc("fixtures/pc-borin.json")
    pc.level, pc.abilities["int"] = 11, 13
    pc.feats += ["combat expertise", "second chance", "improved second chance"]
    scene, engine, pc, thug = _fight(pc)
    thug.hp = thug.hp_max = 500
    engine.dice = Faces([1, 1, 1, 1, 1], match="Attack")
    res = _run(engine, [{"op": "attack", "actor": "pc", "target": thug.ref,
                         "visibility": "hidden",
                         "params": {"full_attack": True, "second_chance": True}}])
    out = next(o for o in res.outcomes if o.op == "attack")
    attacks = [r for r in out.rolls if "Attack" in (r.label or "")]
    assert len(attacks) == 4                     # BAB +11: three blows, the first twice
    assert _named(attacks[-1].modifiers, "Improved Second Chance") == -5
    assert _named(attacks[1].modifiers, "Improved Second Chance") == 0


# --- the plain stance terms --------------------------------------------------------------

def test_snapping_turtle_shell_and_clutch_on_ac_cmd_touch_and_the_confirm():
    """Style: +1 shield to AC with a hand free. Clutch: the same on CMD and touch AC. Shell:
    +2 instead (shield bonuses take the best), and -4 on a confirmation against you."""
    pc = _monk("snapping turtle style", "improved grapple", "snapping turtle clutch",
               "snapping turtle shell", level=5)
    scene, engine, pc, thug = _fight(pc)
    ac, cmd, touch = pc.ac(), pc.cmd(), pc.touch_ac()
    _enter(engine, "snapping-turtle-style")
    assert (pc.ac() - ac, pc.cmd() - cmd, pc.touch_ac() - touch) == (2, 2, 2)
    assert _named(pc._buff_mods("combat_mod", "crit_confirm_against"),
                  "Snapping Turtle Shell") == -4
    pc.equipped, pc.shield = "longsword", "heavy shield"
    assert _named(pc.ac_modifiers(), "Snapping Turtle") == 0


def test_tiger_style_guards_against_three_manoeuvres_in_the_style():
    pc = _monk("tiger style", level=3)
    scene, engine, pc, thug = _fight(pc)
    _enter(engine, "tiger-style")
    for m in ("bull rush", "overrun", "trip"):
        assert _named(pc.cmd_modifiers(maneuver=m), "Tiger Style") == 2
    assert _named(pc.cmd_modifiers(maneuver="disarm"), "Tiger Style") == 0


def test_monkey_style_wisdom_on_acrobatics_and_no_prone_penalty_in_the_style():
    pc = _monk("monkey style", wis=16, level=5, ranks={"acrobatics": 5, "climb": 5})
    scene, engine, pc, thug = _fight(pc)
    assert _named(pc.skill_modifiers("acrobatics"), "Monkey Style") == 3
    pc.add_condition("prone", 5, source="test")
    down = sum(m.value for m in pc.attack_modifiers("unarmed"))
    _enter(engine, "monkey-style")
    assert sum(m.value for m in pc.attack_modifiers("unarmed")) - down == 4
    assert _named(pc.ac_modifiers("melee"), "Monkey Style") == 4
    assert _named(pc.ac_modifiers("ranged"), "Monkey Style") == 0


def test_mantis_style_adds_a_stunning_fist_and_two_to_its_dc_in_the_style():
    """A 6th-level monk has 6 Stunning Fists, DC 10 + 3 + Wis 2 = 15: Mantis Style makes 7,
    and 17 while in the style."""
    pc = _monk("stunning fist", "mantis style", level=6, ranks={"heal": 3})
    scene, engine, pc, thug = _fight(pc)
    from rules import class_abilities as ca

    doc, _ = ca.find(pc, "stunning fist")
    ca.ensure_pool(pc, doc)
    assert pc.pool("stunning fist").maximum == 7
    charge = doc["charge"]
    assert engine._resolve_charge(pc, doc, charge)["dc"] == 15
    _enter(engine, "mantis-style")
    assert engine._resolve_charge(pc, doc, charge)["dc"] == 17


def test_djinni_spirit_resists_electricity_in_the_style_unless_denied_dexterity():
    """A 9th-level monk (BAB +6): resistance 9, the monk level being higher, in the style
    only, and none while flat-footed."""
    pc = _monk("elemental fist", "djinni style", "djinni spirit", level=9, wis=15)
    pc.abilities["con"] = 15
    scene, engine, pc, thug = _fight(pc)
    assert pc.resistance("electricity") == 0
    _enter(engine, "djinni-style")
    assert pc.resistance("electricity") == 9
    pc.add_condition("flat-footed", 1, source="test")
    assert pc.resistance("electricity") == 0


def test_dragon_style_and_ferocity_in_the_style_only():
    """+2 on saves against sleep; Dragon Ferocity half Strength again (Str 17: +1) on an
    unarmed strike."""
    pc = _monk("dragon style", "stunning fist", "dragon ferocity", level=5,
               ranks={"acrobatics": 5})
    pc.abilities["str"] = 17
    scene, engine, pc, thug = _fight(pc)
    sleep = {"against": ("spell", "sleep")}
    assert _named(pc.save_modifiers("will", sleep), "Dragon Style") == 0
    _enter(engine, "dragon-style")
    assert _named(pc.save_modifiers("will", sleep), "Dragon Style") == 2
    assert _named(pc.save_modifiers("will", {"against": ("spell",)}), "Dragon Style") == 0
    assert _named(pc.damage_modifiers("unarmed"), "Dragon Ferocity") == 1


def test_snake_style_reads_the_blow_and_stands_its_sense_motive_for_the_ac():
    """In Snake Style the thug's first blow is met by a Sense Motive check that beats the
    AC (a 19 on the die): the blow is rolled against it; the second blow is not."""
    pc = _monk("snake style", level=3, ranks={"acrobatics": 1, "sense motive": 3})
    scene, engine, pc, thug = _fight(pc)
    _enter(engine, "snake-style")
    engine.dice = Faces([19], match="Sense Motive")
    first = _run(engine, [{"op": "attack", "actor": thug.ref, "target": "pc",
                           "visibility": "hidden"}]).outcomes[0]
    assert "(Snake Style)" in first.tell
    assert any("Sense Motive (Snake Style)" in (r.label or "") for r in first.rolls)
    second = _run(engine, [{"op": "attack", "actor": thug.ref, "target": "pc",
                            "visibility": "hidden"}]).outcomes[0]
    assert "Snake Style" not in second.tell


def test_boar_style_tears_flesh_on_the_second_unarmed_hit_of_the_round():
    pc = _monk("boar style", level=8, ranks={"intimidate": 3})
    scene, engine, pc, thug = _fight(pc)
    thug.hp = thug.hp_max = 400
    _enter(engine, "boar-style")
    engine.dice = Faces([18, 18], match="Attack")
    res = _run(engine, [{"op": "attack", "actor": "pc", "target": thug.ref,
                         "visibility": "hidden",
                         "params": {"full_attack": True, "weapon": "unarmed"}}])
    assert thug.has_state("state.bleeding") or any(e.key == "bleed" for e in thug.effects)
    assert "rule:feat-boar-style" in {e.origin for e in thug.effects}
    del res


def test_panther_style_strikes_back_at_an_attack_of_opportunity_for_moving():
    """The swing a move drew (`provoked_by: movement`) owes the panther one unarmed strike
    back; with Panther Claw as many as its Wisdom modifier, then no more."""
    from rules.intents import Intent

    pc = _monk("combat reflexes", "panther style", "panther claw", wis=15)
    scene, engine, pc, thug = _fight(pc)
    _enter(engine, "panther-style")
    aoo = Intent(op="attack", actor=thug.ref, target="pc",
                 params={"reaction": "attack_of_opportunity", "provoked_by": "movement"})
    got = [engine._panther_retort(aoo) for _ in range(3)]
    assert [len(g) for g in got] == [1, 1, 0]       # Wis 15: +2
    assert got[0][0]["params"]["weapon"] == "unarmed" and got[0][0]["target"] == thug.ref
    still = Intent(op="attack", actor=thug.ref, target="pc", params={})
    assert engine._panther_retort(still) == []


# --- luck --------------------------------------------------------------------------------

def _save(engine, who, save="will", dc=15, vis="player"):
    return engine.run(engine.validate([{"op": "save", "actor": who, "visibility": vis,
                                        "params": {"save": save, "dc": dc}}]))


def _luck_pc(*feats):
    pc = load_pc("fixtures/pc-borin.json")
    pc.feats = list(pc.feats) + list(feats)
    scene = Scene(location_id="5bbd0c40345f")
    scene.add(pc)
    return scene, Engine(scene, Dice(seed=3)), pc


def test_dauntless_destiny_offers_the_player_a_reroll_of_a_natural_one_once_a_day():
    """The popup's die shows 1: the engine asks again with the offer; the reroll (14) is
    taken, said, and Strong Comeback's +2 circumstance rides it. The next natural 1 that
    day is offered nothing."""
    scene, engine, pc = _luck_pc("dauntless destiny", "strong comeback")
    assert _save(engine, "pc").awaiting
    again = engine.resume(1)
    assert again.awaiting["luck"][0]["id"] == "dauntless-destiny"
    assert again.awaiting["luck_face"] == 1
    done = engine.resume(14, luck="dauntless-destiny")
    roll = next(o for o in done.outcomes if o.op == "save").rolls[0]
    assert roll.natural == 14 and _named(roll.modifiers, "Strong Comeback") == 2
    assert "rolls again (Dauntless Destiny): 1, then 14" in \
        next(o for o in done.outcomes if o.op == "luck").tell
    _save(engine, "pc")
    assert not engine.resume(1).awaiting


def test_keeping_the_die_spends_nothing():
    scene, engine, pc = _luck_pc("dauntless destiny")
    _save(engine, "pc")
    engine.resume(1)
    done = engine.resume(1, luck="keep")
    assert next(o for o in done.outcomes if o.op == "save").verdict == "failure"
    assert pc.pool("dauntless-destiny").current == 1


def test_a_foe_takes_its_dauntless_destiny_by_the_book():
    scene, engine, pc = _luck_pc()
    thug = instantiate("thug", scene=scene, name=THUG)
    thug.feats += ["dauntless destiny"]
    scene.add(thug)
    engine.dice = Faces([1, 15])
    res = _save(engine, thug.ref, save="fort", dc=12, vis="hidden")
    assert next(o for o in res.outcomes if o.op == "save").verdict == "success"


def test_inexplicable_luck_is_plus_eight_before_the_die_and_four_after():
    scene, engine, pc = _luck_pc("inexplicable luck")
    first = _save(engine, "pc").awaiting
    assert first["luck"] == [{"id": "inexplicable-luck", "name": "Inexplicable Luck",
                              "when": "before", "amount": 8,
                              "text": "+8 on this roll (Inexplicable Luck)"}]
    done = engine.resume(5, luck="inexplicable-luck")
    roll = next(o for o in done.outcomes if o.op == "save").rolls[0]
    assert _named(roll.modifiers, "Inexplicable Luck") == 8
    scene, engine, pc = _luck_pc("inexplicable luck")
    _save(engine, "pc", dc=15)
    after = engine.resume(12)                      # Will +1: 13 against 15, short
    assert [o["kind"] for o in after.awaiting["luck"]] == ["bonus"]
    done = engine.resume(12, luck="inexplicable-luck")
    assert next(o for o in done.outcomes if o.op == "save").verdict == "success"


def test_close_call_rerolls_a_sleight_of_hand_and_the_second_die_stands():
    scene, engine, pc = _luck_pc("deft hands", "close call")
    pc.ranks = {"sleight of hand": 1}
    res = engine.run(engine.validate([{"op": "check", "actor": "pc", "visibility": "player",
                                       "params": {"skill": "sleight of hand", "dc": 20}}]))
    assert res.awaiting
    offer = engine.resume(3).awaiting
    assert offer["luck"][0]["id"] == "close-call"
    done = engine.resume(2, luck="close-call")
    roll = next(o for o in done.outcomes if o.op == "check").rolls[0]
    assert roll.natural == 2                       # "even if it's worse"


def test_surge_of_success_after_a_natural_twenty_rides_the_next_roll_once():
    scene, engine, pc = _luck_pc("surge of success")
    engine.dice = Faces([20, 5, 5])
    _save(engine, pc.ref, vis="hidden")
    assert pc.has_state("luck.surge")
    nxt = next(o for o in _save(engine, pc.ref, vis="hidden").outcomes if o.op == "save")
    assert _named(nxt.rolls[0].modifiers, "Surge of Success") == 2
    assert not pc.has_state("luck.surge")


def test_lucky_halfling_lends_an_ally_their_own_save():
    """The thug's ally — a halfling with the feat, 5 ft away — rolls the save the thug
    failed (a 2), makes it (an 18), and the thug takes it; once a day."""
    scene, engine, pc = _luck_pc()
    thug = instantiate("thug", scene=scene, name=THUG)
    scene.add(thug)
    friend = instantiate("thug", scene=scene, name="the halfling")
    friend.feats += ["lucky halfling"]
    scene.add(friend)
    scene.sides = {"them": [thug.ref, friend.ref], "pc": ["pc"]}
    engine.dice = Faces([2, 18, 2])
    res = _save(engine, thug.ref, save="ref", dc=14, vis="hidden")
    assert next(o for o in res.outcomes if o.op == "save").verdict == "success"
    assert "the halfling rolls the save for the thug" in \
        next(o for o in res.outcomes if o.op == "luck").tell
    res = _save(engine, thug.ref, save="ref", dc=14, vis="hidden")
    assert next(o for o in res.outcomes if o.op == "save").verdict == "failure"


def test_every_style_document_validates_and_every_follow_up_asks_its_style():
    """A follow-up feat (one with a style feat as a prerequisite) is usable "only while in
    the stance of the associated style" (Ultimate Combat): every term it carries asks for
    a `style.` state. Measured while writing them: none may slip through always-on."""
    import json

    from rules import feats, styles

    docs = json.load(open("content/feats/mechanics/batch2-styles.json", encoding="utf-8"))
    for fid, doc in docs.items():
        if fid.startswith("_"):
            continue
        feat = feats.get(fid)
        follows = [p["feat"] for p in feat.prerequisites if p.get("kind") == "feat"
                   and styles.is_style(feats.get(p["feat"]))]
        if not follows or styles.is_style(feat):
            continue
        for m in doc.get("modifiers") or ():
            if str(m["target"]).startswith("pool."):
                continue                          # "You gain one additional ... per day"
            state = (m.get("when") or {}).get("bearer", {}).get("state", "")
            state = state if isinstance(state, list) else [state]
            assert any(str(s).startswith("style.") for s in state), (fid, m)

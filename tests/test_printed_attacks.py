"""A monster fights with the attacks its stat block prints.

Measured 2026-09-27, read-only, through `Engine.run` against the Kesst fixture: an ogre's
50 hits came to a mean of 7.1 — 6, 7 and 8, one critical 15 — every one an "unarmed
strike". Its line is "greatclub +7 (2d8+7)": a minimum of 9 and a mean of 16. The line was
stripped with the rest of `_NOT_ON_THE_SHEET`, `flat_damage` was read by one method the
engine never called, the ogre arrived with no weapon, and the engine swung its fists,
1d3 plus Strength. A full attack gave an owlbear one swing where its line gives three.

Every fight in the game had been played against monsters doing about half their damage —
see docs/printed-attacks.md for what that did to the XP a fight paid.
"""
from __future__ import annotations

import pytest

from rules import bestiary
from rules import statblock_attacks as sa
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError
from rules.sheet import load_pc


def _fight(template: str, seed: int = 7):
    scene = Scene(location_id="5bbd0c40345f")
    pc = load_pc("fixtures/pc-kesst.json")
    scene.add(pc)
    foe = scene.add(bestiary.instantiate(template, scene=scene))
    engine = Engine(scene, Dice(seed=seed))
    engine._ensure_encounter(foe.ref)      # the gate defers a swing that opens a fight
    return engine, pc, foe


def _swing(engine, foe, pc, **params):
    # A body that cannot fall, so a full attack is never cut short by the first blow:
    # what is measured is what the monster throws, not how long Kesst lasts.
    pc.hp = pc.hp_max = 500
    res = engine.run(engine.validate([
        {"op": "attack", "actor": foe.ref, "target": "pc", "params": params,
         "because": "the test swings it"}]))
    return res.outcomes[0]


# --- the measurement ------------------------------------------------------------------

def test_an_ogre_hits_with_its_greatclub_not_its_fists():
    """The defect as it was measured: ogre hits of 6 and 7 against 2d8+7's minimum of 9,
    50 hits at a mean of 7.1, every one an "unarmed strike". Fifty hits again, now: every
    one the greatclub, stamped with the stat block it came from, and none below 9 unless
    it was a critical (which only raises it)."""
    engine, pc, ogre = _fight("ogre")
    hits = []
    for _ in range(400):
        out = _swing(engine, ogre, pc)
        crit = any("CRITICAL" in str(r.label) for r in out.rolls)
        for e in out.effects:
            if e.get("kind") == "damage" and e.get("ref") == pc.ref:
                hits.append((e["amount"], e.get("weapon"), e.get("origin"), crit))
        if len(hits) >= 50:
            break
    assert len(hits) >= 50
    assert {w for _, w, _, _ in hits} == {"greatclub"}
    assert {o for _, _, o, _ in hits} == {"creature:ogre"}
    plain = [a for a, _, _, crit in hits if not crit]
    assert min(plain) >= 9, sorted(plain)
    assert max(plain) <= 23, sorted(plain)
    # 2d8+7 averages 16. The fists averaged 7.1; anything under 12 is the old bug back.
    assert sum(plain) / len(plain) > 12, sorted(plain)


def test_the_printed_numbers_are_the_whole_bonus_and_nothing_is_added_twice():
    """A printed +7 already holds base attack, Strength and size; a printed +7 damage
    already holds 1.5x Strength on a two-hander. The sheet names the stat block's term and
    no BAB, Str or size beside it — the double count every importer that re-derives from
    ability scores has had to patch with a fudge field."""
    _, _, ogre = _fight("ogre")
    atk = ogre.attack_modifiers()
    assert [(m.value, m.source) for m in atk] == [(7, "greatclub (stat block)")]
    dmg = ogre.damage_modifiers()
    assert [(m.value, m.source) for m in dmg] == [(7, "greatclub (stat block)")]
    club = ogre.weapon()
    assert club["damage"] == "2d8"             # the Large die the book prints, not 1d10
    assert club["type"] == "bludgeoning" and club["crit_mult"] == 2


def test_what_the_print_cannot_know_still_arrives_through_the_funnel():
    """Printed numbers are the base, not the whole answer: a shaken ogre still takes its
    -2, because a condition is exactly what a stat block cannot have counted."""
    _, _, ogre = _fight("ogre")
    ogre.add_condition("shaken", source="test")
    assert sum(m.value for m in ogre.attack_modifiers()) == 5


# --- a monster's full attack -----------------------------------------------------------

def test_a_full_attack_throws_the_whole_printed_line():
    """Measured: `full_attack` gave every stat-block creature exactly one swing
    (`attack_sequence` returned [0] for any `flat_attack`). An owlbear's line is "2 claws
    +8 (1d6+4 plus grab), bite +8 (1d6+4)" — claw, claw, bite — and a troll's is bite,
    claw, claw."""
    _, _, owlbear = _fight("owlbear")
    assert owlbear.attack_plan(full_attack=True) == [("claws", 0), ("claws", 0),
                                                     ("bite", 0)]
    assert owlbear.attack_plan() == [("claws", 0)]
    _, _, troll = _fight("troll")
    assert troll.attack_plan(full_attack=True) == [("bite", 0), ("claws", 0),
                                                   ("claws", 0)]

    engine, pc, owlbear = _fight("owlbear")
    out = _swing(engine, owlbear, pc, full_attack=True)
    swung = [r for r in out.rolls if str(r.label).startswith("Attack with")]
    assert [r.label for r in swung] == ["Attack with claws", "Attack with claws",
                                        "Attack with bite"]


def test_a_bite_is_a_bite_and_a_claw_a_claw():
    """Each swing of a mixed full attack is its own weapon: the bite of claw-claw-bite
    pierces and the claws slash, where every blow used to be the fist's bludgeoning."""
    _, _, owlbear = _fight("owlbear")
    assert owlbear.weapon("claws")["type"] == "slashing"
    assert owlbear.weapon("bite")["type"] == "piercing"
    assert owlbear.weapon("talons")["name"] == "claws"      # a model's word for them


def test_printed_iteratives_are_the_books_not_minus_five_steps():
    """Two-weapon fighting printed out: "2 +1 short swords +19/+17/+12/+12/+9". Five
    swings, each at its printed bonus — the second is +17, not the +14 a -5 step would
    make, and the count of two does not double them to ten."""
    _, _, rogue = _fight("zelfane-vexidyre")
    plan = rogue.attack_plan(full_attack=True)
    assert [i for _, i in plan] == [0, 1, 2, 3, 4]
    totals = [sum(m.value for m in rogue.attack_modifiers(k, i)) for k, i in plan]
    assert totals == [19, 17, 12, 12, 9]


# --- what rides the blow ---------------------------------------------------------------

def test_a_typed_extra_die_lands_as_its_own_type():
    """"+1 frost katana (1d8+10/18-20 plus 2d6 cold)": 551 printed attacks carry an extra
    typed die. It lands as its own packet, so cold resistance meets only the cold."""
    engine, pc, samurai = _fight("michiko-subtier-6-7")
    for _ in range(40):
        out = _swing(engine, samurai, pc)
        cold = [e for e in out.effects if e.get("type") == "cold"]
        if cold:
            assert cold[0]["origin"] == "creature:michiko-subtier-6-7"
            assert "adds" in out.tell
            return
    pytest.fail("forty swings and the frost never landed")


def test_a_shadows_touch_drains_strength_not_hit_points():
    """"incorporeal touch +4 (1d6 Str)". Read naively as hit points, the new reader would
    have had a shadow club the player for 1d6 bludgeoning; 35 printed attacks deal a
    score. It lands through the `ability_damage` op, against touch AC."""
    engine, pc, shadow = _fight("shadow", seed=3)
    assert shadow.weapon()["stat_block"]["touch"]
    for _ in range(30):
        out = _swing(engine, shadow, pc)                # sets the body to 500 first
        if out.verdict == "hit":
            assert "Strength damage" in out.tell
            assert pc.hp == 500                         # no hit points taken
            assert any(e.get("origin") == "creature:shadow" for e in out.effects)
            return
    pytest.fail("thirty touches and none landed")


def test_the_hand_written_dog_bites():
    """The guard dog said `equipped: unarmed` beside `flat_damage: 1d4` and nothing read
    the second: it punched, 1d3+1. The Bestiary dog bites for 1d4+1."""
    _, _, dog = _fight("guard dog")
    assert dog.wielded_key() == "bite"
    assert dog.weapon()["damage"] == "1d4"
    assert sum(m.value for m in dog.damage_modifiers()) == 1


# --- the gates -------------------------------------------------------------------------

def test_a_weapon_the_block_does_not_print_is_refused_with_the_ones_it_does():
    """An ogre asked to swing a longsword used to be let through (a stat-block creature
    carries no `weapons` list, so the carried check never fired) and rolled at its
    printed +7 with a longsword's dice and its Strength on top — neither the book's
    number nor a derivation. Refused now, naming what it has."""
    engine, _, ogre = _fight("ogre")
    with pytest.raises(IntentError) as e:
        engine.validate([{"op": "attack", "actor": ogre.ref, "target": "pc",
                          "params": {"weapon": "longsword"}, "because": "x"}])
    assert "greatclub" in str(e.value) and "javelin" in str(e.value)


def test_a_printed_name_outside_both_tables_passes_the_parse_gate():
    """"tendrils" is in no weapons table and no race's evolution pool, so the parse gate
    refused it before the engine could ask the creature — the hole the natural attacks
    were let through in 2026-09-14."""
    from rules.intents import _known_weapon

    assert _known_weapon("tendrils")
    assert _known_weapon("tail slap")
    assert not _known_weapon("zzkrath blade")


# --- the reader ------------------------------------------------------------------------

@pytest.mark.parametrize("line, want", [
    # The PDF's typography: an en dash for minus and for a crit range, x for times.
    ("short sword +1 (1d4/19–20)", {"bonuses": [1], "crit_range": 19,
                                         "base": "short-sword"}),
    ("short bow +3 (1d4/×3)", {"crit_mult": 3, "base": "shortbow"}),
    ("claw –3 (1d4+1)", {"bonuses": [-3], "dice": "1d4", "bonus": 1}),
    # A size word in front of an enhancement once read as an attack called "Large" at +1.
    ("Large +1 giant-bane greatsword +21/+16/+11 (3d6+16/19-20)",
     {"bonuses": [21, 16, 11], "dice": "3d6", "bonus": 16, "base": "greatsword"}),
    ("longbow +11/+6 (1d8/3)", {"crit_mult": 3}),
    ("2 claws +8 (1d6+4 plus gra b)", {"count": 2, "riders": ["grab"], "kind": "claw"}),
    ("troop (4d6+8)", {"automatic": True, "dice": "4d6", "bonus": 8}),
    ("flurry of blows +1/+1 (1d6+2)", {"base": "unarmed", "bonuses": [1, 1]}),
    ("sap +3 (1d6+1 nonlethal)", {"nonlethal": True}),
    ("incorporeal touch +4 (1d6 Str)", {"touch": True, "ability": "str"}),
])
def test_the_reader_reads_the_book_as_printed(line, want):
    got = sa.parse(line)[0][0]
    for k, v in want.items():
        assert got[k] == v, (k, got)


def test_the_or_separates_what_a_full_attack_may_combine():
    """"broken scimitar +0 (1d6), claw -3 (1d4+1) or 2 claws +2 (1d4+2)" is two full
    attacks, not one of three weapons; asked for "claws", the skeleton gets the option
    whose entry is printed "claws", not the lone "claw" before it."""
    _, _, skeleton = _fight("skeleton")
    assert skeleton.attack_plan("claws", True) == [("claws", 0), ("claws", 0)]
    assert skeleton.attack_plan(full_attack=True) == [("broken scimitar", 0),
                                                      ("claw", 0)]


def test_every_printed_die_is_one_the_roller_will_roll_even_on_a_critical():
    """Measured 2026-09-27: five blocks print "1d1", which `Dice.parse` refuses as
    implausible — and `_multiply_dice` turned any constant into "0d1+N", refused too, so
    the first critical from one of them would have raised in the middle of a fight."""
    from rules.dice import Dice
    from rules.engine import _multiply_dice

    dice = Dice()
    for doc in bestiary.imported().values():
        for options in sa.of_block(doc).values():
            for option in options:
                for a in option:
                    for notation in [a["dice"]] + [x["dice"] for x in a["extra"]]:
                        for mult in (1, 2, 3, 4):
                            dice.parse(_multiply_dice(notation, mult))
    assert _multiply_dice("1", 3) == "3"
    assert sa.parse("claw +4 (1d1)")[0][0]["dice"] == "1"


def test_nearly_every_printed_melee_line_reads():
    """Measured 2026-09-27: 7,053 of the 7,090 blocks with a melee line read into at least
    one attack. The 37 that do not are prose, "none", a truncated parenthesis or an attack
    printed with no bonus — and they keep the old behaviour rather than a guess."""
    blocks = [c for c in bestiary.imported().values() if (c.get("melee") or "").strip()]
    read = sum(1 for c in blocks if sa.parse(c["melee"]))
    assert read / len(blocks) > 0.99, (read, len(blocks))

"""The metal tag's readers (leatherworking plan §18.5, contracts §11 lane M).

The owner's answer to Q7.3: "armor and weapons both need a metal tag because there are
spells that affect metal". The tag existed (`rules/item_tags.py`, enchanting plan §16) and
was read by one thing, inubrix's house clause. Read off the code and the documents on
build/leatherworking before this lane, 2026-10-08:

- the druid's "no metal armour" was a proficiency token read by the armour-proficiency
  parser and nothing else: a druid in steel-studded leather cast as freely as in a robe;
- heat metal and chill metal were a save gate with a paragraph inside — a slot spent and
  nothing on anybody's sheet, a knight in chainmail and a monk in a robe alike;
- rusting grasp was a plain 3d6 untyped to whatever it touched, flesh or iron, and took no
  armour class from anything;
- shocking grasp rolled no attack at all, so its +3 against metal had nothing to land on.
"""
from __future__ import annotations

import pytest

from rules import casting, classbuilder, classes, class_abilities, classfeatures
from rules import effectspec, forge_items, item_tags, states
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc, to_dict


def druid(level=1, **extra):
    """Kesst's sheet as a druid of `level` with a Wisdom to cast from, in nothing."""
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"class": "druid", "level": level, "ranks": {}, "armour": "none",
              "shield": "none",
              "abilities": {**d["abilities"], "wis": 18},
              "class_choices": {"nature bond": {"option": "animal companion",
                                                "pick": "wolf"}}})
    d.pop("paths", None)
    d.update(extra)
    pc = from_dict(d, ref="pc")
    pc.weapons, pc.equipped = ["quarterstaff"], "quarterstaff"
    return pc


def scene_with(pc, *others):
    s = Scene(location_id="5bbd0c40345f")
    s.add(pc)
    for o in others:
        s.add(o)
    return s, Engine(s, Dice(seed=5))


def fight(s):
    """A fight already running, so a harmful cast resolves rather than opening one (the
    battle gate defers the first violence: tests/test_battle_gate.py)."""
    foes = [r for r in s.actors if r != "pc"]
    s.initiative = [("pc", 20)] + [(r, 10) for r in foes]
    s.sides = {"pc": ["pc"], "them": foes}
    s.round, s.turn = 1, 0


def refill(pc, spell, level):
    """A slot and a prepared copy back for the next cast: each test casts one spell at
    several targets, and the slots are not what is measured."""
    pool = pc.pool(casting.slot_pool(level))
    if pool is not None:
        pool.current = max(pool.current, 1)
    if casting.prepared_count(pc, spell) < 1:
        casting.prepare(pc, spell, 1)


def run(engine, op, **params):
    res = engine.run(engine.validate([{"op": op, "actor": "pc", "because": "test",
                                       "params": params}]))
    while res.awaiting:
        res = engine.resume(int(res.awaiting["max"]))
    return res


def said(res) -> str:
    return " ".join(o.tell for o in res.outcomes if o.tell)


def thug(scene, name, armour="none", weapons=(), equipped="unarmed"):
    t = instantiate("thug", scene=scene, name=name)
    t.flat_ac = None
    t.armour, t.shield = armour, "none"
    t.weapons, t.equipped = list(weapons), equipped
    # Every save fails, through the one funnel, so the curve itself is what is measured.
    t.add_buff("save_mod", "will", -40, source="test: no save")
    scene.add(t)
    return t


# --- the tag ---------------------------------------------------------------------------------

def test_iron_and_steel_are_ferrous_and_mithral_is_not():
    """Rusting grasp's target is "iron or an iron alloy" (CRB). Lane D set `ferrous: true`
    on the eleven iron and steel metal documents and nothing read it: the material tags of
    a steel-studded suit and a mithral shirt said the same thing about iron (nothing)."""
    assert item_tags.has_material("studded leather", states.METAL_FERROUS)
    assert item_tags.has_material("chainmail", states.METAL_FERROUS)
    mithral = {"id": "m", "name": "Mithral shirt", "gear": "armour", "base": "chain shirt",
               "pieces": {"body": {"material": "mithral"}}}
    assert item_tags.has_material(mithral, states.METAL)
    assert not item_tags.has_material(mithral, states.METAL_FERROUS)
    assert not item_tags.has_material("leather", states.METAL)


def test_what_is_metal_on_a_creature_is_a_standing_tag_asked_by_prefix():
    """Law 1: the readers ask `has_state("wears.armour.metal")`, never a suit's name. The
    tags are live-read off what is worn, wielded and packed, so off comes the suit and gone
    is the tag."""
    pc = druid()
    assert not pc.has_state("wears.armour.metal")
    pc.armour = "chain shirt"
    assert pc.has_state("wears.armour.metal") and pc.has_state("wears.armour.metal.ferrous")
    assert pc.has_state("carries.metal")
    pc.armour = "hide armour"
    assert not pc.has_state("wears.armour.metal")
    pc.weapons, pc.equipped = ["dagger"], "unarmed"
    assert pc.has_state("carries.metal") and not pc.has_state("wields.metal")
    pc.equipped = "dagger"
    assert pc.has_state("wields.metal")


# --- the druid ---------------------------------------------------------------------------------

def test_a_druid_in_steel_studded_leather_cannot_cast_and_can_24_hours_after_not_23():
    """CRB Druid: "unable to cast druid spells ... while doing so and for 24 hours
    thereafter". Before, nothing read the druid's "no metal armour" token but the
    proficiency parser, so the cast door had no question to ask. Now the wear op lays one effect (origin `rule:prohibited-metal`), the
    cast is refused with nothing spent, taking the suit off starts the 24 hours on the one
    ticker, and at 23 hours the cast is still refused; at 24 it lands."""
    pc = druid()
    s, e = scene_with(pc)
    casting.prepare(pc, "guidance", 1)
    pc.goods["studded leather"] = 1
    worn = run(e, "wear", item="studded leather")
    assert "stands between them and the green" in said(worn), said(worn)
    held = [x for x in pc.effects if x.origin == classfeatures.PROHIBITION_ORIGIN]
    assert len(held) == 1 and held[0].rounds_left is None
    assert pc.has_state("suspended.casting.class")

    refused = run(e, "cast", spell="guidance")
    assert "nothing answers" in said(refused) and "metal armour" in said(refused)
    assert not any(x.op == "cast" and x.effects for x in refused.outcomes)

    off = run(e, "take_off", item="armour")
    assert "land's voice will return" in said(off), said(off)
    s.advance(minutes=23 * 60)
    still = run(e, "cast", spell="guidance")
    assert "nothing answers yet" in said(still), said(still)
    s.advance(minutes=60)
    assert not pc.has_state("suspended.casting.class")
    cast = run(e, "cast", spell="guidance")
    assert "casts Guidance" in said(cast), said(cast)


def test_putting_it_back_on_during_the_lapse_starts_the_day_again():
    """The lapse is "thereafter": metal back on stops the clock, metal off starts a fresh
    24 hours. One effect throughout, never a second (refresh through the applicator)."""
    pc = druid()
    s, e = scene_with(pc)
    pc.goods["studded leather"] = 1
    run(e, "wear", item="studded leather")
    run(e, "take_off", item="armour")
    s.advance(minutes=20 * 60)
    run(e, "wear", item="studded leather")
    held = [x for x in pc.effects if x.origin == classfeatures.PROHIBITION_ORIGIN]
    assert len(held) == 1 and held[0].rounds_left is None
    run(e, "take_off", item="armour")
    s.advance(minutes=20 * 60)
    assert pc.has_state("suspended.casting.class"), "20 hours into a fresh day"


def _wear_record(e, pc, rec):
    pc.add_stock(forge_items.stock_item(rec))
    return run(e, "wear", item=rec["id"])


@pytest.mark.parametrize("rec", [
    # Dragonhide (CRB Special Materials: "druids can wear dragonhide armor"), even with an
    # iron buckle on it: the exemption is the main material's.
    {"id": "dh", "name": "Red Dragonhide Breastplate", "kind": "crafted", "count": 1,
     "craft": "leatherworker", "gear": "armour", "base": "breastplate", "slot": "armor",
     "quality_index": 3, "masterwork": True, "schema": 3,
     "pieces": {"body": {"material": "red-dragonhide", "passes": 0},
                "fastenings": {"material": "iron", "passes": 0}},
     "smith": {"level": 5, "perks": {}}},
    # Bone-studded leather: the studs are bone (`base-pieces.json` substances), so the
    # studded leather carries no metal at all.
    {"id": "bs", "name": "Bone-studded Leather", "kind": "crafted", "count": 1,
     "craft": "leatherworker", "gear": "armour", "base": "studded leather", "slot": "armor",
     "quality_index": 1, "masterwork": False, "schema": 3,
     "pieces": {"body": {"material": "leather", "passes": 0},
                "fastenings": {"material": "bone-studs", "passes": 0}},
     "smith": {"level": 1, "perks": {}}},
], ids=["dragonhide", "bone-studs"])
def test_a_druid_in_dragonhide_or_bone_studded_leather_casts(rec):
    """The book's druid suits. The dragonhide breastplate here has iron fastenings, and its
    wearer truly has metal on (`wears.armour.metal` holds, so heat metal still finds the
    buckles): what lets the druid cast is the main material's `druid_permitted`, asked by
    the prohibition alone. Bone studs carry no metal at all."""
    pc = druid()
    s, e = scene_with(pc)
    casting.prepare(pc, "guidance", 1)
    worn = _wear_record(e, pc, rec)
    assert pc.armour in ("breastplate", "studded leather"), said(worn)
    assert pc.has_state("wears.armour.metal") is (rec["id"] == "dh")
    assert not pc.has_state("suspended.casting.class")
    assert "casts Guidance" in said(run(e, "cast", spell="guidance"))


def test_a_druid_in_metal_cannot_wild_shape_and_an_item_is_not_her_spell():
    """Supernatural class abilities go with the spells (CRB), read off the ability
    document's `ability_type` ("su"), never off its name."""
    pc = druid(level=4)
    s, e = scene_with(pc)
    pc.armour = "chain shirt"
    res = run(e, "use_ability", ability="wild shape (wolf)")
    assert "nothing answers" in said(res), said(res)
    pc.armour = "none"
    classfeatures.settle(pc)
    pc.remove_effects(match=lambda x: x.origin == classfeatures.PROHIBITION_ORIGIN)
    res = run(e, "use_ability", ability="wild shape (wolf)")
    assert "nothing answers" not in said(res), said(res)
    assert pc.has_state("buff.form.wild-shape"), said(res)


def test_the_druids_rule_is_a_document_and_a_bad_one_is_refused_with_the_fix():
    """Stage 9's direction: no class name in the engine. The rule is the class document's
    `prohibits` block, validated with the fix named."""
    block = classes.get("druid").get("prohibits")
    assert block and block["lapse_hours"] == 24 and block["exempt"] == "druid_permitted"
    assert classfeatures.validate_prohibits(block) == []
    assert not any("prohibits" in p
                   for p in classbuilder.validate_class(classes.get("druid")))
    bad = classfeatures.validate_prohibits({"tags": ["wears.hat"], "suspends": ["all"]})
    assert any("wears.hat" in p for p in bad) and any("'all'" in p for p in bad)
    assert classbuilder.validate_class({**classes.get("druid"), "prohibits": {"tags": []}})
    assert not any("ability_type" in p for p in class_abilities.validate_documents())
    wrong = {"druid": {"abilities": [{"key": "x", "name": "X", "source": "test",
                                      "ability_type": "magic"}]}}
    assert any("ability_type 'magic'" in p for p in class_abilities.validate_documents(wrong))


# --- heat metal and chill metal ------------------------------------------------------------

def _cast_at(e, spell, *refs):
    return run(e, "cast", spell=spell, at=refs[0], targets=list(refs)) if len(refs) > 1 \
        else run(e, "cast", spell=spell, at=refs[0])


@pytest.mark.parametrize("spell,dtype", [("heat-metal", "fire"), ("chill-metal", "cold")])
def test_heat_metal_burns_a_chainmail_wearer_fully_and_a_dagger_carrier_at_the_minimum(
        spell, dtype, monkeypatch):
    """CRB: full damage "if its armor, shield, or weapon is affected", minimum damage
    "(1 point or 2 points, depending on the round)" if it is only carrying metal. Round 1
    is warm (no damage) and lands on the cast; rounds 2-7 ride one effect the periodic
    executor spends: 1d4, 2d4, 2d4, 2d4, 1d4, 0 for the knight; 1, 2, 2, 2, 1, 0 for the
    man with a dagger in his belt. Before, the document was a save gate around a
    paragraph, and nothing landed on either.

    Every gear save fails here (a natural 20 still saves, and seed 5 rolled one for the
    knight on the first run), so the curve is what is measured."""
    from rules import dice as dice_mod

    monkeypatch.setattr(dice_mod, "d20_succeeds", lambda roll, dc: False)
    pc = druid(level=3)
    s, e = scene_with(pc)
    knight = thug(s, "the knight", armour="chainmail")
    carrier = thug(s, "the carrier", weapons=["dagger"])
    robe = thug(s, "the robe")
    casting.prepare(pc, spell, 3)
    fight(s)
    told = {}
    for who in (knight, carrier, robe):
        before = who.hp
        refill(pc, spell, 2)
        told[who.ref] = said(run(e, "cast", spell=spell, at=who.ref))
        assert who.hp == before, "round 1 is warm: no damage on the cast"
    assert "no metal on them" in told[robe.ref], told
    assert "worn or wielded: full damage" in told[knight.ref], told
    assert "only carried" in told[carrier.ref], told
    k = next(x for x in knight.effects if x.key == "metal-temperature")
    c = next(x for x in carrier.effects if x.key == "metal-temperature")
    assert not any(x.key == "metal-temperature" for x in robe.effects)
    assert k.payload["contact"] == "full" and c.payload["contact"] == "minimum"
    assert k.periodic[0]["schedule"] == ["1d4", "2d4", "2d4", "2d4", "1d4", "0"]
    took_k, took_c = [], []
    for _ in range(6):
        for who, took in ((knight, took_k), (carrier, took_c)):
            got = [r for r in s._drain_periodic(who) if r.get("kind") == "damage"]
            assert all(r["type"] == dtype for r in got)
            took.append(sum(r["amount"] for r in got))
    assert took_c == [1, 2, 2, 2, 1, 0]
    assert 1 <= took_k[0] <= 4 and all(2 <= n <= 8 for n in took_k[1:4]) and took_k[5] == 0
    assert not any(x.key == "metal-temperature" for x in knight.effects + carrier.effects)


def test_a_metal_temperature_curve_is_validated_with_the_fix_named():
    spec = {"type": "metal_temperature", "damage_type": "fire",
            "schedule": "0, 1d4, 2d4", "minimum": "0, 1"}
    assert any("same rounds" in p for p in effectspec.validate(spec))
    spec["minimum"] = "0, 1, two"
    assert any("whole numbers" in p for p in effectspec.validate(spec))


# --- rusting grasp -------------------------------------------------------------------------

def cast_rust(e, pc, **params):
    refill(pc, "rusting-grasp", 4)
    return run(e, "cast", **params)


def test_rusting_grasp_takes_at_most_one_ac_from_studded_leather_and_more_from_chainmail():
    """The owner's answer 7 (2026-10-08): a mixed suit loses only its metal pieces' share —
    studded leather's book 3 less leather's 2 — so the leather survives the rust; a suit
    whose body is steel can lose up to the 1d6. Before, the document was 3d6 untyped
    damage to the wearer, and the suit's armour class was untouched. The touch is rolled at the player's best
    face (the helper resumes every popup at its maximum), so it lands."""
    pc = druid(level=7)
    s, e = scene_with(pc)
    studded = thug(s, "the studded", armour="studded leather")
    mailed = thug(s, "the mailed", armour="chainmail")
    hide = thug(s, "the hide", armour="hide armour")
    casting.prepare(pc, "rusting-grasp", 4)
    fight(s)
    hp = studded.hp
    ac = studded.ac()
    first = cast_rust(e, pc, spell="rusting-grasp", at=studded.ref)
    assert studded.ac() == ac - 1 and studded.hp == hp, said(first)
    again = cast_rust(e, pc, spell="rusting-grasp", at=studded.ref)
    assert studded.ac() == ac - 1, "never past the metal's share"
    assert "lost all the rust can take" in said(again)
    ac_m, touch_m = mailed.ac(), mailed.touch_ac()
    cast_rust(e, pc, spell="rusting-grasp", at=mailed.ref)
    assert ac_m - 6 <= mailed.ac() <= ac_m - 1
    assert mailed.touch_ac() == touch_m, "rust is the armour's, never touch AC"
    ac_h = hide.ac()
    res = cast_rust(e, pc, spell="rusting-grasp", at=hide.ref)
    assert hide.ac() == ac_h and "nothing to rust" in said(res)
    mailed.armour = "none"
    casting.settle_rust(mailed)
    assert not any(x.key == "rust" for x in mailed.effects), "taken off, its rust goes"


def test_rusting_grasps_share_is_the_metal_pieces_own():
    """The reader behind the cap, on the table: studded leather 1, armoured coat 2,
    chainmail its whole bonus."""
    pc = druid()
    for key, share in (("studded leather", 1), ("armored coat", 2), ("chainmail", 6)):
        pc.armour = key
        assert casting.rust_reach(pc)["share"] == share, key


# --- shocking grasp ------------------------------------------------------------------------

@pytest.mark.parametrize("armour,metal", [("chain shirt", True), ("hide armour", False)])
def test_shocking_grasp_gets_three_against_a_chain_shirt_and_not_against_hide(armour, metal):
    """CRB: "+3 bonus on the attack roll if the opponent is wearing metal armor". Read
    before: `Engine._op_cast` rolled no attack for any spell, so the +3 had nothing to land
    on."""
    pc = druid()
    pc.char_class = "wizard"
    pc.abilities["int"] = 18
    s, e = scene_with(pc)
    target = thug(s, "the guard", armour=armour)
    pc.spellbook = list(pc.spellbook or []) + ["shocking-grasp"]
    casting.prepare(pc, "shocking-grasp", 1)
    fight(s)
    res = run(e, "cast", spell="shocking-grasp", at=target.ref)
    text = said(res)
    assert "melee touch reaches" in text, text
    assert ("+3 against metal" in text) is metal, text
    touch = [r for o in res.outcomes for r in o.rolls if "touch attack" in r.label]
    assert touch and any(m.source == "against metal" for m in touch[0].modifiers) is metal

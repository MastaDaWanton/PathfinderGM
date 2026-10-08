"""Every weapon and every armour usable: the owner's "lets make all weapons and armor
useable" (playtest 2026-09-30, item 2; docs/playtest-2026-09-30-findings.md, parts E1-E5, D
and U; the owner's rulings E1-E6 in docs/fix-plan-2026-09-30.md).

What was measured before, and what each test below pins:

* **Two weapon tables.** `goods.kind_of` asked the curated twelve-row `tables.WEAPONS`;
  the attack op and the shops asked the 456 in `content/weapons/weapons.json`. Of the 356
  weapons the weaponsmith sold, `wear` refused 348 ("bo-staff is not something that can be
  worn or wielded") and the Equipment tab hid Wield behind "The rules cannot put this in
  hand by name yet". Only 8 could be drawn.
* **Double weapons.** 16 rows printed "1d6/1d6", and rolling one raised `BadDice`.
* **Ammunition.** Arrows were a weapon with no damage and a "+20" attack row; a bow fired
  forever; three bundles of arrows were three of a thing.
* **Armour.** Worn only by its exact key: "leather armour" (its display name) and
  "chain-shirt" (the loot op's spelling) were gear. Nothing took armour off. The table had
  7 of the CRB's 12 armours and 3 of its 6 shields, with no weight and no spell failure.
* **Loot and the outfit.** The watchman's chain shirt went into the ingredient satchel as
  "chain-shirt"; the outfit stored a replaced suit under its display name.
* **Mage Armor.** Cast through the real model, it spent its slot, was narrated, and AC
  stayed 13 -> 13: a cast's AC bonus was rendered for the GM and never applied.
"""
from __future__ import annotations

import collections
import re

import pytest

from rules import armour as armour_mod
from rules import goods, market, spells as spells_mod
from rules import weapons as W
from rules.bestiary import instantiate
from rules.dice import BadDice, Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, full_sheet, load_pc, to_dict


def fighter(**over):
    pc = load_pc("fixtures/pc-borin.json")
    pc.weapons, pc.equipped, pc.goods, pc.armour, pc.shield = (
        ["unarmed"], "unarmed", {}, "none", "none")
    for k, v in over.items():
        setattr(pc, k, v)
    s = Scene(location_id=None)
    s.add(pc)
    return pc, s, Engine(s, Dice(seed=3))


def wizard(level=3, armour="none", shield="none", book=("mage-armor",), **extra):
    d = to_dict(load_pc("fixtures/pc-caster.json"))
    d.update({"level": level, "armour": armour, "shield": shield})
    d["spellbook"] = sorted(set(list(d.get("spellbook") or []) + list(book)))
    d["prepared"] = {k: 4 for k in book}
    d.update(extra)
    pc = from_dict(d, ref="pc")
    s = Scene(location_id=None)
    s.add(pc)
    return pc, s, Engine(s, Dice(seed=11))


def run(e, raw, origin="author:test"):
    return e.run(e.validate(raw, origin=origin)).outcomes


def wear(e, item):
    return run(e, [{"op": "wear", "params": {"item": item, "actor": "pc"}}])[0]


def take_off(e, item="armour"):
    return run(e, [{"op": "take_off", "actor": "pc", "params": {"item": item}}])[0]


def fight(s, pc):
    thug = instantiate("thug", scene=s, name="the thug")
    s.add(thug)
    s.initiative = [("pc", 20), (thug.ref, 10)]
    s.sides = {"pc": ["pc"], "them": [thug.ref]}
    s.round, s.turn = 1, 0
    return thug


# --- E1: one name, one row --------------------------------------------------------------------

@pytest.mark.parametrize("said, key", [
    ("bo-staff", "bo-staff"), ("Bo staff", "bo-staff"), ("bo staff", "bo-staff"),
    ("Short sword", "short-sword"), ("shortsword", "short-sword"),
    ("light crossbow", "light-crossbow"), ("Light-Crossbow", "light-crossbow"),
    ("Arrows (20)", "arrows-20"), ("arrows", "arrows-20"), ("my longbow", "longbow"),
    ("heavy crossbow", "heavy-crossbow"), ("brass knuckles", "brass-knuckles"),
    ("shuriken", "shuriken-5"),
])
def test_every_spelling_of_a_weapon_is_one_key(said, key):
    """"bo-staff" was a weapon to the attack op and gear to `wear`; "Bo staff", its display
    name, was neither (measured 2026-09-30)."""
    assert W.key_for(said) == key


def test_an_unknown_word_is_never_the_nearest_weapon():
    assert W.key_for("plasma rifle") == "" and goods.kind_of("plasma rifle") == "gear"
    # A general-store item sharing a name with a weapon row is the store's gear.
    assert goods.kind_of("grappling hook") == "gear"


@pytest.mark.parametrize("said, kind, key", [
    ("leather armour", "armour", "leather"), ("Leather Armor", "armour", "leather"),
    ("chain-shirt", "armour", "chain shirt"), ("Chain Shirt", "armour", "chain shirt"),
    ("full-plate", "armour", "full plate"), ("a suit of half-plate", "armour", "half-plate"),
    ("light steel shield", "shield", "light shield"), ("tower shield", "shield", "tower shield"),
])
def test_every_spelling_of_an_armour_is_one_key(said, kind, key):
    """"leather armour" and "chain-shirt" were filed as gear: every armour could be worn
    only by its exact key (all 10 sold, none by name)."""
    assert armour_mod.key_for(said) == (kind, key)
    assert goods.kind_of(said) == kind


def test_a_bare_material_word_is_not_armour():
    """A tanner's raw hide, a length of chain, "my shield?" — none is a suit to wear."""
    for word in ("hide", "chain", "plate", "shield"):
        assert armour_mod.key_for(word) == ("", ""), word


def test_the_curated_short_sword_and_light_crossbow_are_one_row_each():
    """The curated "shortsword" and "light crossbow" sat beside the file's "short-sword"
    and "light-crossbow" — the same sword at two keys, one priced and one not."""
    table = W.all_weapons()
    assert "shortsword" not in table and "light crossbow" not in table
    assert W.get("shortsword") is table["short-sword"]
    assert W.get("shortsword")["finessable"] is True          # the curated field won
    assert W.get("shortsword")["cost_gp"] == 10.0             # the file's price kept
    sold = goods.outfit_weapons()
    assert sum(1 for k in sold if W.key_for(k) == "short-sword") == 1


def test_348_of_356_sold_weapons_were_refused_now_every_one_is_drawn_or_filed():
    """The whole-catalogue measurement, through the real doors: bought (`deliver`),
    offered by the Equipment tab (`_carried`), put in hand by the `wear` op. Before: 348 of
    356 refused, 8 drawn. Now every row the smith sells is drawn, worn, or carried with its
    reason in words; a button appears exactly where the op accepts, and the op refuses
    exactly where there is none."""
    from play.views import _carried

    sold = goods.outfit_weapons()
    smith = {g.key for g in market.staples_of("market:weaponsmith")
             if g.id.startswith("weapon:")}
    assert smith == set(sold)
    pc, s, e = fighter()
    seen = collections.Counter()
    for key in sorted(sold):
        pc.weapons, pc.equipped, pc.goods, pc.stock = ["unarmed"], "unarmed", {}, {}
        pc.armour = pc.shield = "none"
        g = goods.weapon_good(key)
        goods.deliver(s, pc, g)
        rows = _carried(pc)
        kind = goods.kind_of(key)
        if kind == "gear":
            assert any(r["id"].startswith("stock:") for r in rows), key
            seen["carried as gear"] += 1
            continue
        row = next(r for r in rows if r["key"] in (key, goods.canonical(key)))
        out = wear(e, row["acts"][0]["body"]["item"] if row["acts"] else key)
        if row["acts"]:
            assert out.effects, f"{key}: a button, and the op refused: {out.tell}"
            if kind == "weapon":
                Dice(seed=1).roll(pc.damage_dice(key), pc.damage_modifiers(key))
            seen["drawn" if kind == "weapon" else "worn"] += 1
        else:
            assert row["note"], f"{key}: no button and no reason"
            assert not out.effects, f"{key}: no button, and the op took it"
            seen[f"filed: {row['kind']}"] += 1
    # 2026-09-30, after: 340 sold (the siege and "(Modern)" rows are off the shelf).
    assert sum(seen.values()) == len(sold)
    assert seen["drawn"] >= 260, seen


def test_the_weaponsmith_sells_no_siege_engine_and_nothing_modern():
    """Owner's ruling E5. The shelf sold rams, ladders, siege ammunition and grenades."""
    for key, row in goods.outfit_weapons().items():
        assert not re.search(r"siege|\(modern\)", str(row.get("section")), re.I), key


def test_wear_stores_the_canonical_key():
    pc, s, e = fighter(goods={"Leather Armour": 1})
    pc.weapons.append("bo staff")
    assert wear(e, "leather armour").effects
    assert pc.armour == "leather"
    assert wear(e, "Bo staff").effects
    assert pc.equipped == "bo-staff" and "bo-staff" in pc.weapons


def test_a_sheet_holding_a_drawn_bo_staff_still_loads():
    """`validate` asked the curated twelve, so drawing any of the other 444 would have made
    the character's own save refuse to load."""
    pc, s, e = fighter()
    pc.weapons.append("bo-staff")
    wear(e, "bo-staff")
    again = from_dict(to_dict(pc), ref="pc")
    assert again.equipped == "bo-staff"


def test_a_non_key_armour_is_refused_by_validation():
    d = to_dict(load_pc("fixtures/pc-borin.json"))
    d["armour"] = "chain-shirt"
    with pytest.raises(Exception):
        from_dict(d, ref="pc")


@pytest.mark.parametrize("cls, weapon", [
    ("wizard", "heavy crossbow"), ("wizard", "heavy-crossbow"), ("rogue", "short sword"),
    ("rogue", "hand crossbow"), ("monk", "brass knuckles"), ("monk", "shuriken"),
    ("monk", "light crossbow"), ("monk", "heavy crossbow"),
])
def test_class_proficiency_tokens_name_real_rows(cls, weapon):
    """Six class tokens matched no row (wizard "heavy crossbow", rogue "hand crossbow" and
    "short sword", monk "brass knuckles", "crossbow", "shuriken"), so each was -4."""
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"class": cls, "ranks": {}})
    pc = from_dict(d, ref="pc")
    assert pc.is_proficient(weapon), (cls, weapon)


# --- E2: double weapons ------------------------------------------------------------------------

def test_16_double_weapons_raised_baddice_and_now_roll_the_first_end():
    """16 rows the smith sold printed "1d6/1d6" and raised `BadDice` when rolled."""
    pc, s, e = fighter()
    doubles = [k for k, w in goods.outfit_weapons().items() if "/" in str(w.get("damage"))]
    assert len(doubles) == 16
    for k in doubles:
        with pytest.raises(BadDice):
            Dice(seed=1).roll(str(W.get(k)["damage"]))
        Dice(seed=1).roll(pc.damage_dice(k), pc.damage_modifiers(k))
    pc.weapons.append("bo-staff")
    row = next(a for a in full_sheet(pc)["offense"]["attacks"] if a["key"] == "bo-staff")
    assert row["damage_dice"] == "1d6/1d6" and pc.damage_dice("bo-staff") == "1d6"


# --- E3: ammunition ----------------------------------------------------------------------------

_LAUNCHER = re.compile(r"\bbow\b|bow$|crossbow|\bsling\b|blowgun|pelletbow|launcher|"
                       r"kestros|atlatl|stonebow|arrow (?:cord|shooter)|repeater", re.I)


def test_every_launcher_names_its_ammunition():
    """A bow that names no arrows cannot spend any, and fires forever. Launchers are found
    by what they are called and by the firearm sections, not by the field under test."""
    missing = []
    for key, row in W.all_weapons().items():
        name, sec = str(row.get("name")), str(row.get("section") or "")
        firearm = "Firearms" in sec and "Siege" not in sec
        if W.is_ammunition(key) or row.get("not_ammo"):
            continue                       # "Atlatl dart", "Sling bullets": the rounds
        if (row.get("category") == "ranged" and _LAUNCHER.search(name)
                and "stitched" not in name.lower() or firearm):
            if not W.ammo_families(key):
                missing.append(key)
    assert missing == []


def test_ammunition_is_never_wieldable_and_has_no_attack_row():
    """Arrows had an attack row at "+20" with no damage, from the import's prof: exotic."""
    pc, s, e = fighter()
    pc.weapons = ["shortbow", "arrows-20"]
    keys = [a["key"] for a in full_sheet(pc)["offense"]["attacks"]]
    assert "arrows-20" not in keys and "shortbow" in keys
    for key in W.all_weapons():
        if W.is_ammunition(key):
            assert W.wieldable(key)[0] is False, key


def test_three_bundles_of_twenty_arrows_are_sixty_arrows():
    pc, s, e = fighter()
    goods.deliver(s, pc, goods.weapon_good("arrows-20"), 3)
    assert pc.goods == {"arrows-20": 60}
    assert "arrows-20" not in pc.weapons


def test_an_old_save_with_arrows_on_the_weapons_list_is_migrated_to_rounds():
    """Sam's save, 2026-09-30: `weapons: [..., "arrows-20", "arrows-20", "arrows-20"]`."""
    d = to_dict(load_pc("fixtures/pc-borin.json"))
    d["weapons"] = ["shortbow", "arrows-20", "arrows-20", "arrows-20"]
    pc = from_dict(d, ref="pc")
    assert pc.weapons == ["shortbow"] and pc.goods.get("arrows-20") == 60


def test_a_bow_with_no_arrows_is_refused_and_starts_no_fight():
    pc, s, e = fighter()
    pc.weapons.append("shortbow")
    wear(e, "shortbow")
    thug = instantiate("thug", scene=s, name="the thug")
    s.add(thug)
    out = run(e, [{"op": "attack", "actor": "pc", "target": thug.ref,
                   "visibility": "hidden", "params": {"weapon": "shortbow"}}], origin="")
    said = " ".join(o.tell for o in out)
    assert "Borin Achereth has no arrows" in said
    assert not s.in_encounter


def test_every_shot_spends_one_arrow_iteratives_included_and_says_what_is_left():
    pc, s, e = fighter(level=6)
    pc.weapons.append("shortbow")
    pc.goods["arrows-20"] = 5
    wear(e, "shortbow")
    thug = fight(s, pc)
    thug.hp = 500
    swings = len(pc.attack_sequence("shortbow", full_attack=True))
    assert swings >= 2
    out = run(e, [{"op": "attack", "actor": "pc", "target": thug.ref, "visibility": "hidden",
                   "params": {"weapon": "shortbow", "full_attack": True}}], origin="")
    spent = [x for o in out for x in o.effects if x.get("kind") == "ammunition"]
    assert spent and spent[0]["spent"] == swings and spent[0]["left"] == 5 - swings
    assert pc.goods["arrows-20"] == 5 - swings
    assert f"has {5 - swings} arrow" in " ".join(o.tell for o in out)


def test_half_the_misses_come_back_when_the_fight_ends():
    """Owner's ruling E1: 50% of misses recovered automatically at a fight's end, with a
    tell. Hits are spent ("destroyed or rendered useless", CRB Equipment, Ammunition)."""
    pc, s, e = fighter()
    pc.weapons.append("shortbow")
    pc.goods["arrows-20"] = 20
    wear(e, "shortbow")
    thug = fight(s, pc)
    thug.hp = 9999
    for _ in range(20):
        run(e, [{"op": "attack", "actor": "pc", "target": thug.ref, "visibility": "hidden",
                 "params": {"weapon": "shortbow"}}], origin="")
    lying = [p for p in s.props if p.get("loosed")]
    assert lying, "no shot missed in 20; the seed changed"
    missed = lying[0]["count"]
    assert "arrows-20" not in pc.goods
    out = run(e, [{"op": "end_encounter", "because": "they stop"}])[0]
    assert pc.goods.get("arrows-20", 0) == missed // 2
    assert f"gathers up {missed // 2} of the {missed}" in out.tell
    assert not [p for p in s.props if p.get("loosed")]


# --- E4: take off, put away, and two hands -----------------------------------------------------

def test_take_off_returns_the_suit_and_carries_the_armour_class_and_the_minutes():
    """Nothing set armour back to none: "armour and a shield come off only by putting
    another on" was the Equipment tab's own note."""
    pc, s, e = fighter(armour="chain shirt")          # worn off the outfit, not in goods
    clock = s.clock_minutes
    out = take_off(e, "armour")
    assert pc.armour == "none" and pc.goods.get("chain shirt") == 1
    assert re.search(r"Armour class \d+ to \d+", out.tell), out.tell
    assert s.clock_minutes == clock + 1                  # Table 6-8: 1 minute


def test_putting_on_armour_costs_its_donning_time():
    pc, s, e = fighter(goods={"breastplate": 1})
    clock = s.clock_minutes
    out = wear(e, "breastplate")
    assert pc.armour == "breastplate" and s.clock_minutes == clock + 4
    assert "4 minutes" in out.tell


def test_plate_alone_goes_on_hastily_one_worse_and_comes_off_with_it():
    """CRB Table 6-8's footnote: without help, plate "can be donned only hastily", and
    hastily donned armour is 1 worse on its bonus and its check penalty."""
    pc, s, e = fighter(goods={"full plate": 1})
    base = pc.ac()
    wear(e, "full plate")
    assert pc.ac() == base + 9 - 1 - (pc.ability_mod("dex") - min(pc.ability_mod("dex"), 1))
    assert pc.armour_check_penalty == -7
    take_off(e, "full plate")
    assert pc.ac() == base and pc.armour_check_penalty == 0


def test_in_a_fight_a_suit_is_refused_with_its_time_and_a_shield_is_a_move_action():
    """Owner's ruling E2."""
    pc, s, e = fighter(armour="chain shirt", shield="heavy shield")
    fight(s, pc)
    no = take_off(e, "armour")
    assert pc.armour == "chain shirt" and "takes 1 minute" in no.tell
    yes = take_off(e, "shield")
    assert pc.shield == "none" and "a move action" in yes.tell


def test_put_away_is_wielding_the_fists():
    pc, s, e = fighter()
    pc.weapons.append("longsword")
    wear(e, "longsword")
    out = take_off(e, "longsword")
    assert pc.equipped == "unarmed" and "away" in out.tell


def test_a_two_handed_weapon_with_a_shield_on_says_take_the_shield_off_first():
    """Owner's ruling E4; the buckler is exempt for a bow or a crossbow (CRB "Buckler":
    "You can use a bow or crossbow without penalty while carrying it")."""
    pc, s, e = fighter(shield="heavy shield")
    pc.weapons += ["greatsword", "shortbow"]
    out = wear(e, "greatsword")
    assert pc.equipped == "unarmed" and "take the shield off first" in out.tell
    pc.shield = "buckler"
    assert wear(e, "shortbow").effects and pc.equipped == "shortbow"
    assert not wear(e, "greatsword").effects


# --- E5: loot and the outfit -------------------------------------------------------------------

def test_the_watchmans_chain_shirt_went_to_the_satchel_and_now_goes_to_goods():
    """Measured 2026-09-30: looted armour went into the INGREDIENT satchel as
    "chain-shirt", where it could be neither seen as armour nor worn."""
    pc, s, e = fighter()
    body = instantiate("watchman", scene=s)
    body.armour = "chain shirt"
    s.add(body)
    body.hp = -20
    body.die("a test")
    run(e, [{"op": "loot", "actor": "pc", "params": {"from_": body.ref}}])
    assert "chain-shirt" not in pc.inventory
    assert pc.goods.get("chain shirt") == 1
    assert wear(e, "chain shirt").effects and pc.armour == "chain shirt"


def test_the_outfit_files_a_replaced_suit_by_its_key():
    """The outfit page stored the suit it replaced in `stock` under its display name."""
    from play import outfit_views

    class Entry:
        sheet = to_dict(load_pc("fixtures/pc-borin.json"))

    entry = Entry()
    entry.sheet["purse"] = {"gp": 500}
    entry.sheet["armour"] = "leather"
    import play.roster as roster
    saved = []
    orig = roster.save
    roster.save = lambda e: saved.append(e)
    try:
        got, problems = outfit_views.apply(entry, [{"kind": "armour", "key": "breastplate"}])
    finally:
        roster.save = orig
    assert not problems
    pc = from_dict(entry.sheet, ref="pc")
    assert pc.armour == "breastplate" and pc.goods.get("leather") == 1


# --- D: the tables -----------------------------------------------------------------------------

def test_the_armour_table_has_all_12_crb_armours_and_6_shields_with_weight_and_asf():
    """It had 7 of 12 and 3 of 6, with no weights and no arcane spell failure. Re-pinned by
    leather lane B (2026-10-08): the leatherworker's five suits and the madu beyond Table
    6-6 (APG, UE; tests/test_leather_items.py pins their numbers) make 17 and 7."""
    from rules.tables import ARMOUR, SHIELDS

    crb = {"padded", "leather", "studded leather", "chain shirt", "hide armour", "scale mail",
           "breastplate", "chainmail", "splint mail", "banded mail", "half-plate",
           "full plate"}
    assert crb <= set(ARMOUR) and len([k for k in ARMOUR if k != "none"]) == 12 + 5
    assert len([k for k in SHIELDS if k != "none"]) == 6 + 1
    for table in (ARMOUR, SHIELDS):
        for k, row in table.items():
            if k != "none":
                assert row["lb"] > 0 and row["asf"] > 0, k
    assert ARMOUR["full plate"]["asf"] == 35 and SHIELDS["tower shield"]["asf"] == 50


# --- E3/AC: spell failure and non-proficiency, through the funnel ------------------------------

def test_a_wizard_in_a_chain_shirt_takes_its_check_penalty_on_attacks():
    """CRB "Armor Proficiency": a non-proficient wearer "takes the armor's ... armor check
    penalty on attack rolls"; the shield's stacks with it."""
    pc, s, e = wizard(armour="chain shirt", shield="tower shield")
    terms = {m.source: m.value for m in pc.attack_modifiers("dagger")}
    assert terms["not proficient with chain shirt"] == -2
    assert terms["not proficient with tower shield"] == -10
    assert terms["tower shield (encumbering)"] == -2


def test_a_fighter_in_a_chain_shirt_takes_no_attack_penalty():
    pc, s, e = fighter(armour="chain shirt", shield="heavy shield")
    assert not [m for m in pc.attack_modifiers("dagger") if "proficient with" in m.source
                and m.source != "not proficient with dagger"]


def test_a_wizard_in_armour_rolls_spell_failure_and_a_failure_loses_the_slot():
    """Owner's ruling E3; CRB "Arcane Spell Failure". Full plate's 35% over 30 casts."""
    pc, s, e = wizard(armour="full plate", level=5, book=("magic-missile",))
    fight(s, pc)
    failed = cast = 0
    for _ in range(30):
        pc.pool("spell slot 1").current = 3
        pc.prepared["magic-missile"] = 2
        out = run(e, [{"op": "cast", "actor": "pc", "visibility": "hidden",
                       "params": {"spell": "magic-missile", "at": s.initiative[1][0]}}],
                  origin="")[0]
        cast += 1
        if any(x.get("kind") == "spell_failure" for x in out.effects):
            failed += 1
            assert "arcane spell failure" in out.tell and "slot" in out.tell
        else:
            assert "does not foul the casting" in out.tell
    assert 0 < failed < cast


def test_a_spell_with_no_somatic_component_never_fails():
    spell = next(sp for sp in spells_mod.all_spells().values()
                 if sp.components and "S" not in [c.upper() for c in sp.components])
    pc, s, e = wizard(armour="full plate")
    assert armour_mod.spell_failure(pc, spell) == (0, "")


# --- Mage Armor, at the cause ------------------------------------------------------------------

def test_mage_armor_was_ac_13_to_13_and_now_lands_its_plus_4():
    """Measured 2026-09-30 through the real model: the slot spent, the spell narrated, and
    AC 13 -> 13. A cast's AC `combat_mod` was rendered for the GM and never applied."""
    pc, s, e = wizard()
    before = pc.ac()
    out = run(e, [{"op": "cast", "actor": "pc", "visibility": "hidden",
                   "params": {"spell": "mage-armor"}}], origin="")[0]
    assert pc.ac() == before + 4
    assert f"armour class {before} to {before + 4}" in out.tell
    effect = next(x for x in pc.effects if x.source == "Mage Armor")
    assert effect.origin == "spell:mage-armor" and effect.rounds_left


def test_mage_armor_does_not_stack_with_a_chain_shirt():
    """Both armour bonuses: the better one, by 1e's types in `dice.stack`."""
    pc, s, e = wizard(armour="chain shirt")
    before = pc.ac()
    run(e, [{"op": "cast", "actor": "pc", "visibility": "hidden",
             "params": {"spell": "mage-armor", "at": "pc"}}], origin="")
    assert pc.ac() == before


def test_barkskin_scales_with_caster_level():
    """"+1 more per three caster levels above 3rd, maximum +5": +3 at 6th."""
    from rules.engine import _ac_grant

    grant = _ac_grant(spells_mod.get("barkskin").effects[0])
    assert (grant(3, {}), grant(6, {}), grant(12, {}), grant(20, {})) == (2, 3, 5, 5)


def test_every_ac_spell_is_applied_or_told_and_the_counts_are_recorded():
    """2026-09-30 survey of the 3,040 spells: 101 carry an AC `combat_mod`. Applied on
    casting: the top-level bonuses with no condition (mage armor, shield, shield of faith,
    barkskin, haste's dodge ...). Told, not applied: a penalty, a conditional ("against
    attacks of opportunity only"), or one behind a save gate."""
    from rules.engine import _ac_grant

    applied, told = [], []
    for sid, sp in spells_mod.all_spells().items():
        for spec in sp.effects or ():
            if spec.get("type") == "combat_mod" and spec.get("target") == "ac":
                (applied if _ac_grant(spec) else told).append(sid)
    for must in ("mage-armor", "shield", "shield-of-faith", "barkskin", "haste"):
        assert must in applied, must
    for never in ("aspect-of-the-stag", "rage", "protection-from-technology"):
        assert never not in applied, never
    assert len(applied) >= 50, len(applied)


# --- U: the Equipment tab ----------------------------------------------------------------------

def test_the_equipment_tab_offers_take_off_put_away_and_counts_the_arrows():
    from play.views import _carried

    pc, s, e = fighter(armour="chain shirt")
    pc.weapons.append("shortbow")
    pc.goods["arrows-20"] = 37
    wear(e, "shortbow")
    rows = {r["id"]: r for r in _carried(pc)}
    assert [a["label"] for a in rows["armour:chain shirt"]["acts"]] == ["Take off"]
    assert [a["label"] for a in rows["weapon:shortbow"]["acts"]] == ["Put away"]
    assert "37 carried" in rows["weapon:shortbow"]["line"]
    ammo = rows["ammo:arrows-20"]
    assert ammo["count"] == 37 and not ammo["acts"] and ammo["note"]


def test_every_row_with_no_act_says_why():
    from play.views import _carried

    pc, s, e = fighter(shield="heavy shield")
    pc.weapons += ["greatsword", "net", "bo-staff"]
    pc.goods["arrows-20"] = 3
    for r in _carried(pc):
        if r["kind"] in ("weapon", "ammunition", "armour", "shield") and not r["acts"]:
            assert r["note"], r["id"]


# --- the declarer, the op table and the prompt -------------------------------------------------

def test_take_off_my_armour_is_declared_and_take_off_down_the_street_is_not():
    from gm import judgement

    pc, s, e = fighter(armour="chain shirt", shield="buckler")
    got = judgement.declare_take_off([], "I take off my armour and sit down", s)
    assert got and got[0]["op"] == "take_off" and got[0]["params"]["item"] == "chain shirt"
    assert judgement.declare_take_off([], "I unstrap the buckler", s)[0]["params"]["item"] \
        == "buckler"
    assert judgement.declare_take_off([], "I take off down the street", s) == []
    assert judgement.declare_take_off([], "Should I take my shield off?", s) == []
    assert judgement.declare_take_off([], "I get my shield", s) == []
    assert "take_off" in judgement.declared_ops("I take my armour off", s)


def test_take_off_is_an_op_the_model_is_taught():
    from gm import prompts
    from rules.intents import OPS

    assert "take_off" in OPS
    assert '{"op": "take_off"' in prompts.BRIEFING

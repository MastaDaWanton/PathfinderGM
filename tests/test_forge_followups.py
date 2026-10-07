"""The forge revamp's engine follow-ups (blacksmithing contracts §12, §13; lane H, wave 2).

Wave 1 made a forged item wieldable and wearable and computed its numbers; each wave-1
report then named a reader that still asked the base table, a gate that still refused the
new thing, or a clause in lane C's data that nothing evaluated. Every test here names the
measurement that found its defect. They run on the REAL material documents (lane C's
`content/materials`), not stand-ins: the clauses tested are the ones the shipped data uses.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from django.conf import settings

from rules import armour as armour_mod
from rules import forge_items, gear, intents, keepers, knowledge, places
from rules import spells as spells_mod
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError
from rules.sheet import (_when_holds, attacker_traits, from_dict, load_pc, to_dict)
from tests._board import face_to_face


# --- builders ----------------------------------------------------------------------------------

def suit(rid: str, body: str, base: str = "chain shirt", **over) -> dict:
    rec = {"id": rid, "name": rid.replace("-", " ").title(), "kind": "crafted",
           "craft": "blacksmith", "count": 1, "gear": "armour", "base": base,
           "slot": "armor", "quality_index": 1, "masterwork": False,
           "pieces": {"body": {"material": body, "passes": 0}},
           "quench": None, "finish": [], "flaws": [],
           "smith": {"level": 1, "perks": {}}, "schema": 3}
    rec.update(over)
    return rec


def blade(rid: str, head: str, base: str = "longsword", finish=(), **over) -> dict:
    rec = {"id": rid, "name": rid.replace("-", " ").title(), "kind": "crafted",
           "craft": "blacksmith", "count": 1, "gear": "weapon", "base": base,
           "slot": "hands", "quality_index": 1, "masterwork": False,
           "pieces": {"head": {"material": head, "passes": 0}},
           "quench": None, "finish": list(finish), "flaws": [],
           "smith": {"level": 1, "perks": {}}, "schema": 3}
    rec.update(over)
    return rec


def wizard(book=("magic-missile", "mage-armor")):
    d = to_dict(load_pc("fixtures/pc-caster.json"))
    d.update({"level": 5, "armour": "none", "shield": "none"})
    d["spellbook"] = sorted(set(list(d.get("spellbook") or []) + list(book)))
    d["prepared"] = {k: 4 for k in book}
    pc = from_dict(d, ref="pc")
    s = Scene(location_id=None)
    s.add(pc)
    return pc, s, Engine(s, Dice(seed=11))


def kesst(seed: int = 5):
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    return s.pc(), s, Engine(s, Dice(seed=seed))


def run(e, raw, origin="author:test"):
    return e.run(e.validate(raw, origin=origin)).outcomes


def wear(e, item, actor="pc"):
    return run(e, [{"op": "wear", "actor": actor, "because": "test",
                    "params": {"item": item}}])[0]


def total(mods) -> int:
    return sum(m.value for m in mods)


def tagged(actor, *tags):
    actor.apply_effect(ActiveEffect(name="test body", kind="trait", source="test",
                                    tags=tuple(tags)))
    return actor


# --- 1. what is worn is what the readers read -------------------------------------------------

def test_a_mithral_shirts_minus_ten_percent_reaches_a_cast():
    """Contracts §12 item 1. Measured 2026-10-04 before the fix: a wizard in a forged
    mithral chain shirt rolled arcane spell failure at 20% — the base chain shirt's row —
    because `armour.spell_failure` read `row("armour", actor.armour)` while the sheet's AC
    line already read the build. The book's mithral is 10% less: 10%."""
    pc, s, e = wizard()
    pc.add_stock(forge_items.stock_item(suit("mithral-shirt", "mithral")))
    assert wear(e, "mithral-shirt").effects and pc.armour == "chain shirt"
    spell = spells_mod.get("magic-missile")
    assert armour_mod.spell_failure(pc, spell) == (10, "Mithral Shirt")
    thug = instantiate("thug", scene=s, name="the thug")
    s.add(thug)
    s.initiative = [("pc", 20), (thug.ref, 10)]
    s.sides = {"pc": ["pc"], "them": [thug.ref]}
    s.round, s.turn = 1, 0
    out = run(e, [{"op": "cast", "actor": "pc", "visibility": "hidden",
                   "params": {"spell": "magic-missile", "at": thug.ref}}], origin="")[0]
    assert "(arcane spell failure 10%" in out.tell or "against 10%" in out.tell, out.tell


def test_an_unproficient_wearer_pays_the_forged_suits_check_penalty_not_the_tables():
    """Contracts §12 item 1, the attack half. CRB "Armor Proficiency": the unproficient
    wearer takes the armour's check penalty on attacks. A mithral chain shirt's penalty is
    0 (−2, three lighter, minimum 0), and the wizard took the table's −2 on every swing."""
    pc, s, e = wizard()
    pc.add_stock(forge_items.stock_item(suit("mithral-shirt", "mithral")))
    wear(e, "mithral-shirt")
    assert pc.armour_stats()["acp"] == 0
    assert armour_mod.attack_penalties(pc) == []
    pc.add_stock(forge_items.stock_item(suit("iron-shirt", "iron")))
    wear(e, "iron-shirt")
    assert armour_mod.attack_penalties(pc) == [(-4, "not proficient with Iron Shirt")]


def test_the_pack_weighs_what_the_forge_made():
    """Contracts §12 item 1, the weight half. Measured before the fix: the worn mithral
    shirt weighed the table's 25 lb in `gear.load`, and a forged longsword on the shelf
    was listed `unknown` and weighed nothing (its shelf name is no goods row)."""
    pc, s, e = kesst()
    pc.stock.clear()
    pc.goods.clear()
    pc.weapons, pc.equipped, pc.armour, pc.shield = [], "unarmed", "none", "none"
    bare = gear.load(pc)["lb"]
    pc.add_stock(forge_items.stock_item(suit("mithral-shirt", "mithral")))
    assert gear.load(pc)["lb"] == pytest.approx(bare + 12.5)
    wear(e, "mithral-shirt")
    assert gear.load(pc)["lb"] == pytest.approx(bare + 12.5), "counted once, worn"
    pc.add_stock(forge_items.stock_item(blade("iron-longsword", "iron")))
    got = gear.load(pc)
    assert "Iron Longsword" not in got["unknown"]
    assert got["lb"] == pytest.approx(bare + 12.5 + 4)


# --- 2. a forged blade can be named in an attack -------------------------------------------------

def test_an_attack_naming_a_forged_blade_passes_the_parse():
    """Contracts §12 item 2. Measured before the fix: "attack with the Fine Iron Longsword"
    was refused at parse — "attack: no such weapon 'fine iron longsword'" — because
    `_known_weapon` knew the weapon tables and natural weapons only, while the engine's
    legality step already resolved crafted records. The forged blade could be drawn and
    never named."""
    pc, s, e = kesst()
    thug = instantiate("thug", scene=s, name="the thug")
    s.add(thug)
    pc.add_stock(forge_items.stock_item(blade("fine-iron-longsword", "iron",
                                              name="Fine Iron Longsword")))
    for said in ("Fine Iron Longsword", "fine-iron-longsword"):
        got = e.validate([{"op": "attack", "actor": "pc", "target": thug.ref,
                           "params": {"weapon": said}, "because": "test"}])
        assert got[0].params["weapon"] == said.lower()
    # The gate is opened for the call only: parse alone, with nobody to ask, still refuses.
    with pytest.raises(IntentError, match="no such weapon"):
        intents.parse({"op": "attack", "actor": "pc", "target": thug.ref,
                       "params": {"weapon": "Fine Iron Longsword"}, "because": "t"})
    # And somebody who does not carry it is refused by the legality step, by name.
    with pytest.raises(IntentError, match="has no weapon"):
        e.validate([{"op": "attack", "actor": thug.ref, "target": "pc",
                     "params": {"weapon": "Fine Iron Longsword"}, "because": "test"}])


# --- 3. nobody is hired into the PC's own smithy -------------------------------------------------

def test_no_hired_smith_stands_in_the_players_own_smithy():
    """Contracts §12 item 3. Measured before the fix: found "my own forge" (kind forge,
    owner pc), walk in, and `keepers.staff` stood a smith up behind the PC's anvil — and
    `places.smithy_here` then named that stranger as its keeper. A held place is kept by
    its holder."""
    from tests.test_forge_places import PANGRELLA, VYRAKON, _run, _table

    scene, engine = _table(PANGRELLA, VYRAKON)
    made = _run(engine, "found", {"name": "my own forge", "kind": "forge", "owner": "pc"})
    _run(engine, "travel", {"place": "my own forge"})
    pid = made.effects[0]["id"]
    assert scene.at == pid
    assert keepers.keeper_in(scene, pid) is None
    assert keepers.staff(engine) is None
    here = places.smithy_here(scene, engine.places())
    assert here["kind"] == "owned" and here["keeper"] is None
    # A smithy founded with no holder is the town's and is still staffed.
    town = _run(engine, "found", {"name": "the smithy"})
    _run(engine, "travel", {"place": "the smithy"})
    assert keepers.keeper_in(scene, town.effects[0]["id"]) is not None


# --- 4. every `when` clause lane C's data uses is asked ------------------------------------------

def test_target_subtype_and_a_list_of_types_mean_any_of():
    """Silver and electrum's +2 against shapechangers is `{"target": {"subtype": ...}}`;
    elysian bronze's `{"target": {"type": ["magical beast", "monstrous humanoid"]}}` is a
    LIST, meaning any of them. Asked of the defender by tag prefix (law 1)."""
    s = Scene(location_id=None)
    were = tagged(instantiate("thug", scene=s, name="were"), "subtype.shapechanger")
    beast = tagged(instantiate("thug", scene=s, name="beast"), "type.monstrous-humanoid")
    man = instantiate("thug", scene=s, name="man")
    assert _when_holds({"target": {"subtype": "shapechanger"}}, {"target_actor": were})
    assert not _when_holds({"target": {"subtype": "shapechanger"}}, {"target_actor": man})
    either = {"target": {"type": ["magical beast", "monstrous humanoid"]}}
    assert _when_holds(either, {"target_actor": beast})
    assert not _when_holds(either, {"target_actor": man})


def test_an_adamantine_suits_dr_is_its_weight_classes_not_the_best_of_three():
    """`{"armour": {"weight": ...}}`, answered at build. Measured 2026-10-04 before the
    fix: no reader asked it, so a forged adamantine chain shirt (light) met all three book
    rows and took the best — DR 3/— where the book says 1/—."""
    pc, s, e = kesst()
    for rid, base, want in (("adamant-shirt", "chain shirt", "DR 1/—"),
                            ("adamant-breastplate", "breastplate", "DR 2/—"),
                            ("adamant-plate", "full plate", "DR 3/—")):
        pc.add_stock(forge_items.stock_item(suit(rid, "adamantine", base=base)))
        assert wear(e, rid).effects, rid
        assert pc.damage_reduction("slashing").label == want, rid
    # The clause is gone from what readers see; a shield (no weight class) has none.
    b = forge_items.build(suit("x", "adamantine", base="breastplate"))
    assert not any("when" in sp for sp in b["specs"] + b["book"])
    assert forge_items.at_build({"type": "damage_reduction", "amount": 1,
                                 "when": {"armour": {"weight": "light"}}},
                                "shield", "heavy shield") is None


def test_elysian_bronze_dr_asks_who_struck():
    """`{"attacker": {"type": [...]}}`: elysian bronze armour's DR holds against magical
    beasts and monstrous humanoids, and against nobody else. The blow carries its maker's
    type as `attacker:` traits from the weapon hit. Measured before lane H: the suit
    reader asked no `when` at all, so an elysian bronze breastplate held DR 3/— (the best
    of its three weight rows) against every blow from anybody."""
    pc, s, e = kesst()
    pc.add_stock(forge_items.stock_item(suit("bronze-plate", "elysian-bronze",
                                             base="breastplate")))
    wear(e, "bronze-plate")
    beast = tagged(instantiate("thug", scene=s, name="beast"), "type.magical-beast")
    man = instantiate("thug", scene=s, name="man")
    assert any(t == "attacker:type.magical-beast" for t in attacker_traits(beast))
    assert pc.damage_reduction("slashing", attacker_traits(beast)).label == "DR 2/—"
    assert pc.damage_reduction("slashing", attacker_traits(man)) is None
    assert pc.damage_reduction("slashing", ()) is None


def test_noqual_armour_guards_saves_against_spells_only():
    """`{"against": "spell"}`: noqual armour's +2 resistance on saves against spells. The
    cast's save and a spell-stamped save op pass it; a plain save does not."""
    pc, s, e = kesst()
    pc.add_stock(forge_items.stock_item(suit("noqual-shirt", "noqual")))
    wear(e, "noqual-shirt")
    plain = total(pc.save_modifiers("will"))
    assert total(pc.save_modifiers("will", {"against": "spell"})) == plain + 2
    def save_terms(origin):
        out = run(e, [{"op": "save", "actor": "pc", "visibility": "hidden",
                       "params": {"save": "will", "dc": 15}, "because": "test"}],
                  origin=origin)[0]
        return [m.source for m in out.rolls[0].modifiers]

    assert "Noqual Shirt" in save_terms("spell:hold-person")
    assert "Noqual Shirt" not in save_terms("author:test")


def test_alchemical_silvers_minus_one_is_slashing_and_piercing_only():
    """`{"weapon": {"slashing_or_piercing": true}}`: the book's −1 damage for alchemical
    silver (and singing steel, which counts as silver) on a slashing or piercing weapon.
    Nothing set the field, so the −1 was dropped on every weapon, a mace included."""
    pc, s, e = kesst()
    plain_sword = total(pc.damage_modifiers("longsword"))
    plain_mace = total(pc.damage_modifiers("light-mace"))
    pc.add_stock(forge_items.stock_item(blade("silvered-sword", "iron",
                                              finish=["alchemical-silver-plating"])))
    pc.add_stock(forge_items.stock_item(blade("silvered-mace", "iron", base="light-mace",
                                              finish=["alchemical-silver-plating"])))
    iron = forge_items.build(blade("x", "iron"))
    iron_dmg = next((r["final"] for r in iron["sum"] if r["target"] == "damage"), 0)
    assert total(pc.damage_modifiers("silvered-sword")) == plain_sword + iron_dmg - 1
    assert total(pc.damage_modifiers("silvered-mace")) == plain_mace + iron_dmg


def test_inubrix_swings_truer_at_a_metal_armoured_defender():
    """`{"target": {"armour_metal": true}}`: inubrix's house +3 attack against a defender
    in iron or steel (the book's "ignores armour bonuses from iron or steel"). Evaluated
    off what the defender wears (`armour.wears_metal`), never off a name."""
    pc, s, e = kesst()
    pc.add_stock(forge_items.stock_item(blade("inubrix-rapier", "inubrix", base="rapier")))
    wear(e, "inubrix-rapier")
    mailed = instantiate("thug", scene=s, name="mailed")
    mailed.flat_ac = None
    mailed.armour = "chainmail"
    hide = instantiate("thug", scene=s, name="hide")
    hide.flat_ac = None
    hide.armour = "hide armour"
    assert armour_mod.wears_metal(mailed) and not armour_mod.wears_metal(hide)
    assert total(pc.attack_modifiers(defender=mailed)) == \
        total(pc.attack_modifiers(defender=hide)) + 3


def test_a_clause_nothing_can_evaluate_is_still_dropped_never_applied():
    """The plan's rule for every clause, kept: an unknown key, an unknown field, or a
    context that cannot answer means the term does not apply. Making six clauses fire must
    not make a seventh fire unconditionally."""
    s = Scene(location_id=None)
    who = instantiate("thug", scene=s, name="who")
    ctx = {"target_actor": who, "weapon": {"key": "longsword"}}
    # `target.alignment` is READ since enchanting lane C (2026-10-05), and answers yes for
    # every target by the owner's ruling (round 6: no alignment is tracked yet, holy's 2d6
    # lands on any foe, as smite does). It left this list of unevaluable clauses then;
    # the rest stay dropped.
    assert _when_holds({"target": {"alignment": "evil"}}, ctx)
    assert not _when_holds({"phase_of_the_moon": "full"}, ctx)
    assert not _when_holds({"weapon": {"glows": True}}, ctx)
    assert not _when_holds({"attacker": {"type": "dragon"}}, ctx)
    assert not _when_holds({"against": "spell"}, ctx)
    assert not _when_holds({"target": {"type": "fey"}}, None)
    assert forge_items.at_build({"type": "combat_mod", "target": "ac", "amount": 1,
                                 "when": {"armour": {"colour": "red"}}},
                                "armour", "chain shirt") is None


# --- 5. ghost touch ---------------------------------------------------------------------------------

def _hit(e, s, target_ref, weapon_key, tries=25):
    for _ in range(tries):
        s.turn = [r for r, _ in s.initiative].index("pc")
        out = e.run(e.validate([{"op": "attack", "actor": "pc", "target": target_ref,
                                 "visibility": "hidden", "params": {"weapon": weapon_key},
                                 "because": "test"}])).outcomes[-1]
        hit = next((x for x in out.effects if x.get("kind") == "damage"), None)
        if hit:
            return out, hit
    pytest.fail("never hit")


def test_ghost_salt_strikes_as_ghost_touch_and_an_incorporeal_foe_halves_the_rest():
    """Contracts §12 item 5, and the rule under it. Bestiary, Incorporeal: "it takes only
    half damage from a corporeal source"; CRB, ghost touch: that 50% "does not apply to
    attacks made against it with ghost touch weapons". Before lane H neither existed — a
    ghost took a sword's full damage — so lane C's data stood a +2 against undead in for
    ghost salt. Now ghost salt is `strikes_as: ghost_touch` and the halving is real."""
    pc, s, e = kesst(seed=9)
    ghost = s.add(instantiate("thug", scene=s, name="the ghost"))
    tagged(ghost, "subtype.incorporeal")
    ghost.hp = ghost.hp_max = 500
    pc.add_stock(forge_items.stock_item(blade("salted-rapier", "iron", base="rapier",
                                              finish=["ghost-salt-blanching"])))
    pc.add_stock(forge_items.stock_item(blade("plain-rapier", "iron", base="rapier")))
    assert "ghost_touch" in forge_items.build(blade("x", "iron", finish=[
        "ghost-salt-blanching"]))["strikes_as"]
    run(e, [{"op": "begin_encounter",
             "params": {"sides": {"you": ["pc"], "them": [ghost.ref]}}}])
    face_to_face(s, b=ghost.ref)

    # A plain iron blade is a nonmagical attack form, and since enchanting lane C
    # (2026-10-05) the incorporeal are "immune to all nonmagical attack forms" (Bestiary):
    # it passes through and does nothing. The half is for a magic one (a +1 rapier).
    wear(e, "plain-rapier")
    for _ in range(25):
        s.turn = [r for r, _ in s.initiative].index("pc")
        out = run(e, [{"op": "attack", "actor": "pc", "target": ghost.ref,
                       "visibility": "hidden", "params": {"weapon": "plain-rapier"},
                       "because": "test"}])[-1]
        if any(x.get("kind") == "blow_harmless" for x in out.effects):
            break
    else:
        pytest.fail("never landed")
    assert not any(x.get("kind") == "damage" for x in out.effects), out.effects
    assert "passes clean through the ghost: it is not magic" in out.tell
    assert ghost.hp == 500

    magic = blade("magic-rapier", "iron", base="rapier")
    magic["magic"] = {"schema": 1, "enhancement": 1, "properties": [], "flat": [],
                      "powers": []}
    magic["quality_index"] = 3
    pc.add_stock(forge_items.stock_item(magic))
    wear(e, "magic-rapier")
    out, hit = _hit(e, s, ghost.ref, "magic-rapier")
    rolled = next(r for r in out.rolls if str(r.label).startswith("Damage")).total
    assert hit["amount"] == max(1, max(1, rolled) // 2), (rolled, hit)
    assert "passes through the ghost's insubstantial form" in out.tell

    wear(e, "salted-rapier")
    out, hit = _hit(e, s, ghost.ref, "salted-rapier")
    rolled = next(r for r in out.rolls if str(r.label).startswith("Damage")).total
    assert hit["amount"] == max(1, rolled), (rolled, hit)
    assert "bites the ghost as if it were flesh" in out.tell


# --- 6. forged shields --------------------------------------------------------------------------------

def test_a_forged_shield_is_strapped_on_and_folds_into_the_shield_bonus():
    """Contracts §12 item 6. Wave 1 refused it: "forged shields cannot be carried into a
    fight yet", while the bench made bucklers and steel shields. The shield slot holds the
    record, `shield` the base key, and an iron body's +2 AC folds into the SHIELD bonus
    (one term, as a suit's folds into the armour bonus); it is a move action, in a fight
    too, and it comes off again and round-trips through the save."""
    pc, s, e = kesst()
    pc.shield = "none"
    before = pc.ac()
    rec = suit("iron-shield", "iron", base="heavy shield", gear="shield", slot="shield")
    pc.add_stock(forge_items.stock_item(rec))
    assert pc.stock["iron-shield"].slot == "shield"
    out = wear(e, "iron-shield")
    assert pc.shield == "heavy shield", out.tell
    assert "a move action" in out.tell
    shield_terms = [m for m in pc.ac_modifiers() if m.type == "shield"]
    assert [(m.source, m.value) for m in shield_terms] == [("Iron Shield", 4)]
    assert pc.ac() == before + 4
    assert pc.shield_stats()["acp"] == -2 - 2
    back = from_dict(to_dict(pc), ref="pc")
    assert back.ac() == pc.ac() and back.shield_record()["id"] == "iron-shield"
    off = run(e, [{"op": "take_off", "actor": "pc", "params": {"item": "Iron Shield"}}])[0]
    assert pc.shield == "none" and pc.ac() == before, off.tell
    assert "iron-shield" in pc.stock


# --- 9. noqual's recoil (the owner's house rule, contracts §13.2) --------------------------------

def test_assaying_noqual_suppresses_the_assayers_magic_for_1d4_rounds():
    """The owner, 2026-10-04: "magic recoils" — a HOUSE RULE. Before it, an assay of noqual
    was safe (`danger_of` found no carrier effect on it). Now the assay's danger is
    `suppress_magic`, applied through the one applicator with `origin: item:noqual`: a
    cast mage armor's +4 AC goes quiet while it holds and comes back when it ends — the
    spell suppressed, not dispelled (its clock still runs) — and a tea's buff, which is
    chemistry, is untouched."""
    pc, s, e = wizard()
    run(e, [{"op": "cast", "actor": "pc", "visibility": "hidden",
             "params": {"spell": "mage-armor"}}], origin="")
    armoured = pc.ac()
    pc.add_buff("save_mod", "will", 1, source="a calming tea", rounds=100,
                origin="item:chamomile")
    will = total(pc.save_modifiers("will"))
    got = knowledge.assay(pc, "noqual", 0, clock=0)
    assert got["danger"]["type"] == "suppress_magic" and got["danger"].get("house")
    outcomes = knowledge.apply_danger(e, pc, "noqual", got["danger"])
    assert outcomes and "recoils" in outcomes[0].tell
    held = next(x for x in pc.effects if x.key == "magic-recoils")
    assert held.origin == "item:noqual" and 1 <= held.rounds_left <= 4
    assert pc.has_state("suppressed.magic")
    assert pc.ac() == armoured - 4
    assert total(pc.save_modifiers("will")) == will, "the tea is not magic"
    mage_armor = next(x for x in pc.effects if x.origin == "spell:mage-armor")
    left = mage_armor.rounds_left
    pc.tick_effects(held.rounds_left)
    assert not pc.has_state("suppressed.magic")
    assert pc.ac() == armoured and mage_armor.rounds_left < left


def test_noquals_danger_is_written_as_a_house_rule_in_the_data():
    """The assay danger is data, validated: a type the assay can apply, a duration, the
    `reactive` trait, and whose rule it is. Noqual's says house."""
    from rules import materials

    doc = materials.get("noqual")
    assert doc["assay_danger"]["type"] == "suppress_magic"
    assert doc["assay_danger"]["house"] is True
    assert doc["assay_danger"]["duration"] == {"amount": "1d4", "unit": "round"}
    assert materials.validate(doc) == []
    bad = dict(doc, assay_danger={"type": "explode"})
    assert any("assay danger" in p for p in materials.validate(bad))


# --- 10. every city has a smithy (the owner's ruling, contracts §13.3) ---------------------------

@pytest.mark.parametrize("export, cities, before", [
    ("fixtures/aurvantis-campaign.json", 16, 4),
    ("fixtures/pangrella-campaign.json", 6, 0),
])
def test_every_authored_city_has_a_smithy(export, cities, before):
    """The owner, 2026-10-04: "every city gets a smithy, even when the world's author did
    not list one". Measured the same day on the shipped exports: a smithy in 5 of
    Aurvantis's 64 authored settlements (4 of 16 cities, 1 of 32 towns) and in 0 of
    Pangrella's 12 (0 of 6 cities), so the forge's furnace work could not be rented in 18
    of 22 cities. Appended, reachable from the first place, and never a second one."""
    from world import loader

    world = loader.load_cached(export)
    ents = list(world.entities.values()) if isinstance(world.entities, dict) \
        else list(world.entities)
    authored = [x for x in ents if getattr(x, "places", None)
                and places.scale_of(x) == "city"]
    assert len(authored) == cities
    assert sum(any(places.has_place_tag(p, places.SMITHY) for p in places._authored(x))
               for x in authored) == before
    for city in authored:
        home = places.home_set(city)
        smithies = [p for p in home if places.has_place_tag(p, places.SMITHY)]
        assert len(smithies) == 1, city.name
        one = smithies[0]
        assert any(one.id in (p.exits or ()) for p in home if p.id != one.id), city.name
    # Towns are the author's (and their own words'): nothing is appended to one.
    towns = [x for x in ents if getattr(x, "places", None) and places.scale_of(x) == "town"]
    for town in towns:
        assert sum(places.has_place_tag(p, places.SMITHY) for p in places.home_set(town)) \
            == sum(places.has_place_tag(p, places.SMITHY) for p in places._authored(town))


def test_the_appended_smithy_is_published_for_world_bible():
    vocab = json.loads(Path(settings.BASE_DIR, "docs", "place-vocabulary.json")
                       .read_text(encoding="utf-8"))
    # The laboratory joined 2026-10-06 (alchemy lane G: "every city has a laboratory").
    assert vocab["appended_to_authored"]["city"][0] == "the smithy"
    assert vocab["appended_to_authored"] == {"city": list(places.APPENDED_TO_AUTHORED["city"])}


# --- 8. the World Bible contract names the material fields ----------------------------------------

MATERIAL_FIELDS = ("pieces", "weapon", "armour", "working", "quench_mark", "forms",
                   "material", "book", "feeds", "finishes", "not_on", "assay_danger")


def test_the_campaign_format_documents_every_material_field():
    """Plan §15.1 (fixes are world-agnostic): a world's own metals need the same fields as
    the shipped ones, documented as optional with their defaults, and the next export asked
    for them. Before lane H neither document named one of them."""
    fmt = Path(settings.BASE_DIR, "docs", "campaign-format.md").read_text(encoding="utf-8")
    handoff = Path(settings.BASE_DIR, "docs", "from-world-bible.md").read_text(
        encoding="utf-8")
    section = fmt[fmt.index("## Materials"):]
    for name in MATERIAL_FIELDS:
        assert f"`{name}`" in section, name
    assert "materials" in handoff.lower() and "quench_mark" in handoff


def test_noqual_assay_warns_in_words_not_an_id():
    """Merged 2026-10-04: noqual's recoil reached the card as the bare id `suppress_magic`
    (`effectspec.render` had no line for it and `knowledge.danger_of` drops the note), so
    the forge's `_danger_words` sent nothing and the confirm fell back on a general warning.
    The owner's ruling is that the warning says what happens: your magic is suppressed."""
    from play import forge_views
    from rules import knowledge, materials

    found = knowledge.danger_of(materials.get("noqual"))
    words = forge_views._danger_words(found[1])
    assert "magic" in words.lower() and "1d4 rounds" in words, words

"""Feat loop batch 1, lane b1-spellhooks (2026-11-22): the feats that change how a spell
works, proved through the engine's own cast.

Before this lane, measured on integrate/0.5.1-impl: of the 83 feats on the lane's list
none had a document, so every one of them was a line on the sheet that changed nothing —
a Dazing Spell fireball dazed nobody, an Elemental Focus (fire) caster's fireball had the
same DC as anyone's, and Spell Specialization (fireball) cast at the plain caster level.
The roll context of a spell carried only its school, so a feat about an energy, one spell
or a list of spells had no word to bind to (`casting.spell_context`).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rules import areas, casting, classbuilder, metamagic, spells
from rules.bestiary import instantiate
from rules.dice import Dice, stack
from rules.engine import Engine, Scene
from rules.grid import Grid
from rules.intents import IntentError
from rules.sheet import _when_holds, from_dict, load_pc, to_dict

BOOK = ("magic-missile", "mage-armor", "fireball", "burning-hands", "shocking-grasp",
        "cone-of-cold", "lightning-bolt", "shout", "dimension-door", "hold-person")
META = ("Heighten Spell", "Widen Spell", "Reach Spell", "Merciful Spell",
        "Intensified Spell", "Elemental Spell (cold)", "Piercing Spell",
        "Persistent Spell", "Focused Spell", "Selective Spell", "Disruptive Spell",
        "Dazing Spell", "Sickening Spell", "Thundering Spell", "Rime Spell",
        "Flaring Spell", "Concussive Spell", "Burning Spell", "Toppling Spell",
        "Ectoplasmic Spell")


def caster(cls="sorcerer", level=15, book=BOOK, feats=META, ref="pc"):
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"class": cls, "level": level, "ranks": {}, "armour": "none"})
    for ab in ("int", "wis", "cha"):
        d["abilities"][ab] = 18
    d["spellbook"] = list(book)
    d["prepared"] = {k: 2 for k in book}
    d["feats"] = list(feats)
    return from_dict(d, ref=ref)


def table(pc, seed=5, sturdy=True, foes=1, grid=False):
    s = Scene(location_id="5bbd0c40345f")
    s.add(pc, at=(5, 5) if grid else None)
    for i in range(foes):
        foe = instantiate("thug", scene=s, name=f"the thug {i + 1}")
        s.add(foe, at=(9 + i, 5) if grid else None)
        if sturdy:
            foe.hp_max = foe.hp = 500
    if grid:
        s.grid = Grid(width=20, height=20)
    refs = [r for r in s.actors if r != "pc"]
    s.initiative = [("pc", 20)] + [(r, 10 - i) for i, r in enumerate(refs)]
    s.sides = {"pc": ["pc"], "them": refs}
    s.round, s.turn = 1, 0
    return s, Engine(s, Dice(seed=seed))


def cast(engine, actor="pc", **params):
    return engine.run(engine.validate([{"op": "cast", "actor": actor,
                                        "because": "the words are said",
                                        "params": params}])).outcomes[0]


def conditions(actor):
    return {e.key: e.rounds_left for e in actor.effects if e.kind == "condition"}


# --- metamagic: the transform's new shapes ---------------------------------------------

def test_heighten_raises_the_dc_and_the_slot_by_the_levels_named():
    """CRB Heighten Spell: "All effects dependent on spell level (such as saving throw
    DCs ...) are calculated according to the heightened level." Fireball at Cha 18 is
    DC 17; heightened by two it is DC 19 and paid from a 5th-level slot."""
    pc = caster()
    s, e = table(pc)
    fifth = casting.pool_left(pc, casting.slot_pool(5))
    out = cast(e, spell="fireball", at="c1", metamagic="heighten 2")
    assert "heightened, in a level 5 slot" in out.tell and "DC 19" in out.tell
    assert casting.pool_left(pc, casting.slot_pool(5)) == fifth - 1
    assert metamagic.chosen({"metamagic": "heighten-spell-2"}) == ["heighten-spell-2"]


def test_heighten_past_ninth_and_a_number_on_an_unstepped_feat_are_refused():
    s, e = table(caster(level=20))
    for meta, said in (("heighten-7", "past 9th"), ("dazing-2", "without a number")):
        with pytest.raises(IntentError) as err:
            e.validate([{"op": "cast", "actor": "pc", "params": {
                "spell": "fireball", "at": "c1", "metamagic": meta}}])
        assert said in str(err.value)


def test_widen_doubles_a_spread_and_refuses_a_line():
    """APG Widen Spell: "Any numeric measurements of the spell's area increase by 100%"
    for a burst, emanation or spread. Fireball's 20-foot spread is 40; a line is not one
    of the four sorts."""
    pc = caster()
    plain = spells.get("fireball")
    wide = metamagic.apply(plain, pc, ["widen-spell"])
    assert areas.shape_of(plain, 15)["length_ft"] == 20
    assert areas.shape_of(wide, 15)["length_ft"] == 40
    assert "burst, emanation or spread" in metamagic.refusal(
        pc, spells.get("lightning-bolt"), ["widen-spell"], spontaneous=True)


def test_reach_turns_a_melee_touch_into_a_ranged_touch_at_close_range():
    """APG Reach Spell: touch to close is one step, and "Spells modified by this feat that
    require melee touch attacks instead require ranged touch attacks." Two steps cost
    two slot levels."""
    pc = caster()
    s, e = table(pc)
    out = cast(e, spell="shocking-grasp", at="c1", metamagic="reach")
    assert "ranged touch reaches" in out.tell or "ranged touch misses" in out.tell
    far = metamagic.apply(spells.get("shocking-grasp"), pc, ["reach-spell-2"])
    assert far.range_value["kind"] == "medium"
    assert metamagic.levels(pc, ["reach-spell-2"]) == 2
    assert "long range" in metamagic.refusal(pc, spells.get("shocking-grasp"),
                                             ["reach-spell-4"], spontaneous=True)


def test_merciful_spell_deals_its_damage_as_nonlethal():
    """APG Merciful Spell: "inflict nonlethal damage instead"; at +0 levels."""
    pc = caster()
    s, e = table(pc)
    out = cast(e, spell="fireball", at="c1", metamagic="merciful")
    c1 = s.actors["c1"]
    assert c1.hp == 500 and c1.nonlethal > 0, out.tell
    assert "in a level 3 slot" in out.tell


def test_intensified_raises_the_dice_cap_by_five():
    """APG Intensified Spell: shocking grasp's 5d6 cap is 10d6 at caster level 15."""
    pc = caster()
    s, e = table(pc)
    out = cast(e, spell="shocking-grasp", at="c1", metamagic="intensified")
    assert out.effects[0]["dice"] == "10d6"
    assert "maximum number of dice" in metamagic.refusal(
        pc, spells.get("magic-missile"), ["intensified-spell"], spontaneous=True)


def test_elemental_spell_makes_the_damage_the_feats_energy_and_its_descriptor_too():
    """APG Elemental Spell (cold): a fireball's damage is cold, and the copy is a [cold]
    spell — so Rime Spell, which only affects cold spells, rides on it (owner call)."""
    pc = caster()
    s, e = table(pc)
    out = cast(e, spell="fireball", at="c1", metamagic=["elemental", "rime"])
    assert any(x.get("kind") == "damage" and x.get("type") == "cold" for x in out.effects)
    assert "entangled" in conditions(s.actors["c1"])


def test_piercing_spell_treats_spell_resistance_as_five_lower():
    pc = caster(level=7)
    s, e = table(pc)
    c1 = s.actors["c1"]
    c1.add_defence("spell_resistance", 60) if hasattr(c1, "add_defence") else None
    from rules.activeeffect import ActiveEffect
    c1.apply_effect(ActiveEffect(name="spell resistance 15", kind="spell_resistance",
                                 key="sr", amount=15, source="test"))
    out = cast(e, spell="magic-missile", at="c1", metamagic="piercing")
    assert "SR 10" in out.tell and "5 lower against a piercing spell" in out.tell


def test_persistent_spell_makes_a_saver_save_again():
    """APG Persistent Spell: "Whenever a creature ... succeeds on its saving throw against
    the spell, it must make another saving throw". A thug with +60 Reflex saves twice."""
    pc = caster()
    s, e = table(pc)
    s.actors["c1"].add_buff("save_mod", "ref", 60, source="test")
    out = cast(e, spell="fireball", at="c1", metamagic="persistent")
    labels = [r.label for r in out.rolls]
    assert any("again (persistent)" in lab for lab in labels), labels
    plain_pc = caster()
    s2, e2 = table(plain_pc)
    s2.actors["c1"].add_buff("save_mod", "ref", 60, source="test")
    plain = cast(e2, spell="fireball", at="c1")
    assert not any("persistent" in r.label for r in plain.rolls)


def test_focused_spell_adds_two_to_the_aimed_creatures_dc_only():
    pc = caster()
    s, e = table(pc, foes=2)
    out = cast(e, spell="fireball", at="c1", metamagic="focused")
    assert "against DC 19" in out.tell, out.tell
    state = {"aim": {"kind": "ref", "value": "c1"}, "caught": ["c1", "c2"], "caster": "pc"}
    spell = metamagic.apply(spells.get("fireball"), pc, ["focused-spell"])
    assert e._focused_dc(spell, 17, s.actors["c1"], state) == 19
    assert e._focused_dc(spell, 17, s.actors["c2"], state) == 17


def test_selective_spell_spares_the_casters_side_up_to_the_casting_modifier():
    """APG Selective Spell: "a number of targets in the area equal to the ability score
    modifier used to determine bonus spells" are excluded — Cha 18 is four."""
    pc = caster()
    s, e = table(pc, foes=1)
    friends = []
    for i in range(5):
        f = instantiate("thug", scene=s, name=f"friend {i}")
        s.add(f)
        s.sides["pc"].append(f.ref)
        friends.append(f.ref)
    left = e._selective_spell_spares(pc, ["pc", "c1", *friends], {"tells": []})
    # The caster is one of the four, then three friends; the foe and two friends remain.
    assert left == ["c1", friends[3], friends[4]]


def test_the_damage_riders_lay_their_condition_for_the_spells_level_in_rounds():
    """APG Dazing Spell: dazed "for a number of rounds equal to the original level of the
    spell" (fireball: 3). UM Rime: a cold spell's victims entangled (cone of cold: 5).
    UM Flaring: lightning bolt dazzles (3). UM Concussive: a sonic spell, -2 on attacks,
    saves, skills and ability checks (shout: 4)."""
    for meta, spell, key, rounds in (("dazing", "fireball", "dazed", 3),
                                     ("rime", "cone-of-cold", "entangled", 5),
                                     ("flaring", "lightning-bolt", "dazzled", 3),
                                     ("concussive", "shout", "concussed", 4),
                                     ("sickening", "fireball", "sickened", 3),
                                     ("thundering", "fireball", "deafened", 3)):
        pc = caster()
        s, e = table(pc, seed=2)
        out = cast(e, spell=spell, at="c1", metamagic=meta)
        assert conditions(s.actors["c1"]).get(key) == rounds, (meta, out.tell)
    c1 = s.actors["c1"]
    assert c1.has_state("state.senses.deafened")


def test_a_concussed_creature_takes_two_off_attacks_and_saves():
    pc = caster()
    s, e = table(pc)
    c1 = s.actors["c1"]
    will = sum(m.value for m in c1.save_modifiers("will"))
    cast(e, spell="shout", at="c1", metamagic="concussive")
    assert sum(m.value for m in c1.save_modifiers("will")) == will - 2


def test_a_dazing_spell_is_negated_by_the_spells_own_save():
    """"If the spell allows a saving throw, a successful save negates the daze effect."
    The thug with +60 Reflex halves the fireball and is not dazed."""
    pc = caster()
    s, e = table(pc)
    s.actors["c1"].add_buff("save_mod", "ref", 60, source="test")
    out = cast(e, spell="fireball", at="c1", metamagic="dazing")
    assert "dazed" not in conditions(s.actors["c1"]), out.tell
    assert s.actors["c1"].hp < 500


def test_a_rider_needs_its_descriptor():
    pc = caster()
    assert "cold" in metamagic.refusal(pc, spells.get("fireball"), ["rime-spell"],
                                       spontaneous=True)
    assert "sonic" in metamagic.refusal(pc, spells.get("fireball"), ["concussive-spell"],
                                        spontaneous=True)


def test_burning_spell_burns_again_at_the_start_of_the_next_turn():
    """UM Burning Spell: "damage equal to 2 x the spell's actual level at the start of its
    next turn" — burning hands, 2."""
    pc = caster()
    s, e = table(pc)
    out = cast(e, spell="burning-hands", at="c1", metamagic="burning")
    c1 = s.actors["c1"]
    assert "burning-spell" in conditions(c1), out.tell
    hp = c1.hp
    said = s._drain_periodic(c1)
    assert c1.hp == hp - 2, said


def test_toppling_spell_trips_with_caster_level_and_the_casting_bonus():
    """UM Toppling Spell: a trip at caster level 15 + Cha 4 against the thug's CMD."""
    pc = caster()
    s, e = table(pc)
    out = cast(e, spell="magic-missile", at="c1", metamagic="toppling")
    assert "toppling Magic Missile knocks" in out.tell
    assert s.actors["c1"].has_state("state.prone") or "prone" in conditions(s.actors["c1"])


def test_disruptive_spell_makes_its_victim_concentrate_to_cast():
    """APG Disruptive Spell: those affected "must make concentration checks when using
    spells ... (DC equals the save DC of the disruptive spell plus the level of the spell
    being cast) for 1 round". Laid on a caster at DC 40, their magic missile is lost."""
    pc = caster()
    s, e = table(pc)
    out = cast(e, spell="fireball", at="c1", metamagic="disruptive")
    assert conditions(s.actors["c1"]).get("disrupted") == 1, out.tell
    pc2 = caster(feats=())
    s2, e2 = table(pc2)
    pc2.add_condition("disrupted", rounds=1, source="a disruptive fireball",
                      payload={"dc": 40})
    lost = cast(e2, spell="magic-missile", at="c1")
    assert "concentration" in lost.tell and "loses it" in lost.tell


def test_an_incorporeal_creature_takes_half_and_ectoplasmic_spell_full():
    """Bestiary, Incorporeal: half damage from a corporeal source; force (magic missile)
    affects it normally. APG Ectoplasmic Spell: "full effect against incorporeal"."""
    from rules.activeeffect import ActiveEffect

    def ghostly(meta=None):
        pc = caster()
        s, e = table(pc, seed=9)
        c1 = s.actors["c1"]
        c1.apply_effect(ActiveEffect(name="incorporeal", kind="condition",
                                     key="incorporeal-test", source="test",
                                     tags=("subtype.incorporeal",)))
        out = cast(e, spell="fireball", at="c1", **({"metamagic": meta} if meta else {}))
        return 500 - c1.hp, out

    half, out = ghostly()
    full, out2 = ghostly("ectoplasmic")
    assert "incorporeal and takes half" in out.tell
    assert full == 2 * half or full == 2 * half + 1


# --- the spell's roll context: the funnel feats ----------------------------------------

def test_elemental_focus_raises_only_its_energys_dc_and_the_greater_stacks():
    pc = caster(feats=("Elemental Focus (fire)", "Greater Elemental Focus (fire)"))
    lvl = 3
    fire = casting.save_dc(pc, lvl, spells.get("fireball"))
    cold = casting.save_dc(pc, lvl, spells.get("lightning-bolt"))
    assert fire == 10 + 3 + 4 + 2 and cold == 10 + 3 + 4


def test_spell_specialization_casts_its_one_spell_two_levels_higher():
    pc = caster(level=6, feats=("Spell Focus (evocation)", "Spell Specialization (fireball)"))
    s, e = table(pc)
    out = cast(e, spell="fireball", at="c1")
    assert out.effects[0]["caster_level"] == 8 and out.effects[0]["dice"] == "8d6"
    assert casting.spell_caster_level(pc, spells.get("lightning-bolt")) == 6


def test_bloatmage_and_mystic_tattoo_raise_their_schools_caster_level():
    pc = caster(level=5, feats=("Bloatmage Initiate (evocation)",
                                "Mystic Tattoo (evocation)"))
    assert casting.spell_caster_level(pc, spells.get("fireball")) == 7
    assert casting.spell_caster_level(pc, spells.get("mage-armor")) == 5


def test_peacemaker_raises_the_books_calming_spells():
    pc = caster(cls="cleric", feats=("Peacemaker",))
    assert casting.save_dc(pc, 1, spells.get("command")) == \
        casting.save_dc(caster(cls="cleric", feats=()), 1, spells.get("command")) + 2
    assert casting.save_dc(pc, 2, spells.get("hold-person")) == \
        casting.save_dc(caster(cls="cleric", feats=()), 2, spells.get("hold-person"))


def test_divine_defiance_saves_against_a_clerics_spell_and_not_a_wizards():
    """Faiths & Philosophies: "+2 bonus on saving throws against divine spells". The cast
    save is against the caster's tradition (`Engine._spell_source_words`)."""
    from rules.engine import Engine as E

    holder = caster(feats=("Divine Defiance",), ref="c9")
    spell = spells.get("hold-person")
    cleric, wizard = caster(cls="cleric", feats=()), caster(cls="wizard", feats=())
    vs = lambda who: sum(m.value for m in holder.save_modifiers("will", {
        "against": ("spell",) + E._spell_source_words(who, spell)}))
    assert vs(cleric) == vs(wizard) + 2
    pc = caster(cls="cleric", book=("hold-person",), feats=())
    s, e = table(pc)
    s.actors["c1"].feats = ["Divine Defiance"]
    out = cast(e, spell="hold-person", at="c1")
    save = next(r for r in out.rolls if "Will save" in r.label)
    assert any(m.source == "Divine Defiance" for m in save.modifiers), save.modifiers


def test_necromantic_affinity_saves_against_an_inflict():
    from rules.engine import Engine as E

    holder = caster(feats=("Necromantic Affinity",), ref="c9")
    words = ("spell",) + E._spell_source_words(caster(cls="cleric", feats=()),
                                               spells.get("inflict-light-wounds"))
    assert "negative_energy" in words
    plain = sum(m.value for m in holder.save_modifiers("will", {"against": ("spell",)}))
    assert sum(m.value for m in holder.save_modifiers("will", {"against": words})) == plain + 2


def test_concentration_feats_through_the_spells_context():
    """UM Uncanny Concentration +2 on every concentration check; UC Dimensional Agility
    +4 "when casting teleportation spells"."""
    pc = caster(feats=("Uncanny Concentration", "Dimensional Agility"))
    base = sum(m.value for m in caster(feats=()).concentration_modifiers({}))
    tele = casting.spell_context(spells.get("dimension-door"), casting="defensively")
    fire = casting.spell_context(spells.get("fireball"), casting="defensively")
    assert sum(m.value for m in pc.concentration_modifiers(fire)) == base + 2
    assert sum(m.value for m in pc.concentration_modifiers(tele)) == base + 6


def test_shielded_caster_counts_an_adjacent_allys_shield():
    """APG Shielded Caster: +4 competence beside an ally with the feat, +5 if the ally
    has a buckler or light shield, +6 a heavy or tower shield. Competence takes the best."""
    pc = caster(feats=("Shielded Caster",))
    base = sum(m.value for m in pc.concentration_modifiers({}))
    ally = caster(feats=("Shielded Caster",), ref="a1")
    for shield, more in (("none", 4), ("buckler", 5), ("heavy shield", 6)):
        ally.shield = shield
        got = sum(m.value for m in pc.concentration_modifiers({"adjacent_allies": [ally]}))
        assert got == base + more, shield
    ally.feats = []
    assert sum(m.value for m in pc.concentration_modifiers({"adjacent_allies": [ally]})) \
        == base


def test_adjacency_is_read_off_the_board():
    pc = caster(feats=("Shielded Caster",))
    s, e = table(pc, grid=True)
    ally = caster(feats=("Shielded Caster",), ref="a1")
    s.add(ally, at=(6, 5))
    s.sides["pc"].append("a1")
    assert [a.ref for a in e._adjacent_allies(pc)] == ["a1"]
    s.positions["a1"] = (12, 12, 0)
    assert e._adjacent_allies(pc) == []


def test_allied_spellcaster_adds_to_spell_resistance_and_more_with_the_same_spell():
    pc = caster(feats=("Allied Spellcaster",))
    ally = caster(feats=("Allied Spellcaster",), ref="a1", book=("fireball",))
    spell = spells.get("fireball")
    ctx = casting.spell_context(spell, against="spell_resistance", adjacent_allies=[ally])
    assert sum(m.value for m in stack(pc._buff_mods("combat_mod", "spell_resistance",
                                                     ctx))) == 4
    assert casting.spell_caster_level(pc, spell, adjacent_allies=[ally]) == 16
    other = casting.spell_context(spells.get("magic-missile"), against="spell_resistance",
                                  adjacent_allies=[ally])
    assert sum(m.value for m in stack(pc._buff_mods("combat_mod", "spell_resistance",
                                                     other))) == 2


def test_diviner_and_demon_hunter_on_the_spell_resistance_check():
    demon = instantiate("thug", name="a demon")
    from rules.activeeffect import ActiveEffect
    demon.apply_effect(ActiveEffect(name="demon", kind="condition", key="demon-test",
                                    source="test", tags=("subtype.demon",)))
    pc = caster(feats=("Demon Hunter", "Diviner's Delving", "Elven Spirit"))
    ctx = lambda sp, who: casting.spell_context(spells.get(sp), against="spell_resistance",
                                                target_actor=who)
    sr = lambda sp, who: sum(m.value for m in stack(pc._buff_mods(
        "combat_mod", "spell_resistance", ctx(sp, who))))
    plain = instantiate("thug", name="a thug")
    assert sr("fireball", plain) == 2                       # elven spirit, racial
    assert sr("fireball", demon) == 4                       # + demon hunter, morale
    assert sr("detect-magic", plain) == 4                   # + diviner's delving
    assert sum(m.value for m in pc._buff_mods("combat_mod", "attack",
                                              {"target_actor": demon})) == 2


def test_deflect_arrows_turns_one_shot_a_round_with_a_free_hand():
    """CRB Deflect Arrows: once per round a ranged hit is turned, with a hand free and
    not flat-footed; a two-handed weapon in hand leaves none."""
    from rules.engine import _hand_free

    pc = caster(feats=("Deflect Arrows",))
    s, e = table(pc)
    pc.equipped, pc.shield = "unarmed", "none"
    assert _hand_free(pc)
    first = e._deflect(s.actors["c1"], pc, {"category": "ranged"}, {"rolls": [],
                                                                    "tells": []}, False)
    second = e._deflect(s.actors["c1"], pc, {"category": "ranged"}, {"rolls": [],
                                                                     "tells": []}, False)
    assert "Deflect Arrows" in first and second == ""
    assert e._deflect(s.actors["c1"], pc, {"category": "ranged"}, {}, True) == ""


def test_missile_shield_needs_a_real_shield():
    pc = caster(feats=("Missile Shield",))
    s, e = table(pc)
    pc.shield = "buckler"
    assert e._deflect_by_feat(pc, {}, "ranged") == ""
    pc.shield = "heavy shield"
    assert "Missile Shield" in e._deflect_by_feat(pc, {}, "ranged")


def test_the_lanes_documents_validate_and_name_no_other_files_ids():
    folder = Path("content/feats/mechanics")
    mine = {k for k in json.loads((folder / "batch1-spells.json").read_text(
        encoding="utf-8")) if not k.startswith("_")}
    for name in ("core.json", "combat.json", "skills.json", "pools.json",
                 "summoning.json", "metamagic.json", "spell-items.json", "riding.json"):
        theirs = {k for k in json.loads((folder / name).read_text(encoding="utf-8"))}
        assert not mine & theirs, (name, mine & theirs)
    assert classbuilder.validate_feat_document("dazing-spell", {
        "metamagic": {"does": "rider", "levels": 3, "rider": {"condition": "dazd"}}})
    assert classbuilder.validate_feat_document("x", {"modifiers": [
        {"type": "combat_mod", "target": "spell_dc", "amount": 1,
         "scope": {"element": "fire"}}]})


def test_a_scope_matches_one_word_of_several():
    from rules.sheet import _scope_holds

    assert _scope_holds({"energy": "$target"}, {"target": "fire"}, {"energy": ("fire",)})
    assert not _scope_holds({"energy": "$target"}, {"target": "cold"},
                            {"energy": ("fire",)})
    assert _scope_holds({"spell": "$target"}, {"target": "magic missile"},
                        {"spell": "magic-missile"})
    assert _when_holds({"ally_adjacent": {"feat": "x"}}, {"adjacent_allies": []}) is False


def test_preferred_spell_casts_by_giving_up_a_prepared_spell_and_takes_metamagic():
    """APG Preferred Spell: "You can cast that spell spontaneously by sacrificing a
    prepared spell or spell slot of equal or higher level ... You can apply any metamagic
    feats you possess to this spell when you cast it. This increases the minimum level of
    the prepared spell ... you must sacrifice". A wizard 9 with fireball unprepared gives
    up lightning bolt; empowered, the 5th-level cone of cold."""
    pc = caster(cls="wizard", level=9,
                book=("fireball", "lightning-bolt", "cone-of-cold", "magic-missile"),
                feats=("Preferred Spell (fireball)", "Empower Spell"))
    pc.prepared = {"lightning-bolt": 1, "cone-of-cold": 1, "magic-missile": 1}
    s, e = table(pc)
    out = cast(e, spell="fireball", at="c1")
    assert "gives up Lightning Bolt" in out.tell
    out = cast(e, spell="fireball", at="c1", metamagic="empower")
    assert "gives up Cone of Cold" in out.tell and "empowered, in a level 5 slot" in out.tell
    assert pc.prepared == {"magic-missile": 1}
    plain = caster(cls="wizard", level=9, book=("fireball", "lightning-bolt"), feats=())
    plain.prepared = {"lightning-bolt": 1}
    s2, e2 = table(plain)
    with pytest.raises(IntentError):
        e2.validate([{"op": "cast", "actor": "pc", "params": {"spell": "fireball",
                                                               "at": "c1"}}])


def test_cypher_magic_reads_scrolls_a_level_higher_and_checks_at_plus_two():
    pc = caster(feats=("Cypher Magic",))
    plain = caster(feats=())
    assert sum(m.value for m in pc.caster_level_check_modifiers({"against": "scroll"})) \
        == sum(m.value for m in plain.caster_level_check_modifiers({"against": "scroll"})) + 2
    assert sum(m.value for m in stack(pc._buff_mods("combat_mod", "spell_cl",
                                                    {"against": "scroll"}))) == 1


def test_a_giants_rock_is_not_deflected():
    pc = caster(feats=("Deflect Arrows",))
    s, e = table(pc)
    pc.equipped, pc.shield = "unarmed", "none"
    assert e._deflect_by_feat(pc, {"key": "rock", "category": "ranged"}, "ranged") == ""
    assert "Deflect Arrows" in e._deflect_by_feat(pc, {"key": "longbow"}, "ranged")

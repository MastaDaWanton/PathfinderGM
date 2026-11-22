"""Cast-time choices: summons from their tables, a chosen energy, metamagic (lane C).

Audit 2026-11-22 (docs/implementation-audit-2026-11-22.md, lane C): summon monster I-IX
and summon nature's ally I-IX were narrative on every level — "Summon one creature of your
choice" was a sentence for the GM and nothing arrived; protection from energy granted an
immunity to the words "one energy type chosen when you cast"; and no metamagic feat had a
reader at all (Foundry PF1 never built one either: issues #17, #1069).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rules import bestiary, casting, classbuilder, metamagic, summons
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError
from rules.sheet import from_dict, load_pc, to_dict


def caster(cls="wizard", level=5, book=("summon-monster-1", "summon-monster-3"),
           feats=(), prepared=None):
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"class": cls, "level": level, "ranks": {}, "armour": "none"})
    for ab in ("int", "wis", "cha"):
        d["abilities"][ab] = 18
    d["spellbook"] = list(book)
    d["prepared"] = dict({k: 2 for k in book} if prepared is None else prepared)
    d["feats"] = list(feats)
    return from_dict(d, ref="pc")


def table(pc, fight=True, seed=3):
    s = Scene(location_id="5bbd0c40345f")
    s.add(pc)
    s.add(instantiate("thug", scene=s, name="the thug"))
    if fight:
        s.initiative = [("pc", 20), ("c1", 10)]
        s.sides = {"pc": ["pc"], "them": ["c1"]}
        s.round, s.turn = 1, 0
    return s, Engine(s, Dice(seed=seed))


def cast(engine, **params):
    return engine.run(engine.validate([{"op": "cast", "actor": "pc",
                                        "because": "the words are said",
                                        "params": params}]))


def summoned(s):
    return [a for r, a in s.actors.items() if r not in ("pc", "c1")]


# --- summons -------------------------------------------------------------------------------

def test_every_creature_on_the_summon_tables_is_a_shipped_stat_block():
    """The tables are CRB Tables 10-1 and 10-2 as bestiary ids; a starred entry must have
    both its celestial and fiendish blocks (content/bestiary/derived.json). Measured when
    the tables were written: the monitor lizard (SM III*) had no templated block, and was
    added to tools/build_derived.py."""
    store = bestiary.imported()
    for table_id in ("summon-monster", "summon-nature-s-ally"):
        for level in range(1, 10):
            opts = summons.options(table_id, level)
            assert opts, (table_id, level)
            missing = [o["creature"] for o in opts if o["creature"] not in store]
            assert not missing, (table_id, level, missing)


def test_a_summons_without_a_creature_is_refused_before_the_slot_is_spent():
    """Audit 2026-11-22: summon monster III was a narrative sentence, so the slot went and
    nothing came. Now the caster names the creature, and a cast that names none is
    refused with the list, the slot still there — the player's choice, never the plan's."""
    pc = caster()
    s, e = table(pc)
    before = casting.pool_left(pc, casting.slot_pool(3))
    with pytest.raises(IntentError) as err:
        e.validate([{"op": "cast", "actor": "pc", "params": {"spell": "summon-monster-3"}}])
    assert err.value.code == "choose_creature" and err.value.fixable_by == "player"
    assert "celestial-gorilla" in err.value.fix["options"]
    assert casting.pool_left(pc, casting.slot_pool(3)) == before


def test_a_creature_off_the_spells_list_is_refused_by_name():
    """A tiger is on summon nature's ally IV and not on summon monster III."""
    s, e = table(caster())
    with pytest.raises(IntentError) as err:
        e.validate([{"op": "cast", "actor": "pc",
                     "params": {"spell": "summon-monster-3", "creature": "tiger"}}])
    assert "'tiger' is not on the list" in str(err.value)


def test_summon_monster_one_calls_one_celestial_dog_that_fights_for_the_caster():
    """The real actor, from the bestiary's templated block, on the caster's side, held by
    a manifestation with the spell's own clock (1 round/level: 5 at caster level 5)."""
    s, e = table(caster())
    out = cast(e, spell="summon-monster-1", creature="dog").outcomes[0]
    dogs = summoned(s)
    assert len(dogs) == 1 and dogs[0].from_template == "celestial-dog"
    assert dogs[0].ref in s.sides["pc"]
    held = [m for m in s.manifests if m.creature == dogs[0].ref]
    assert held and held[0].rounds_left == 5
    assert "Answering the call" in out.tell


def test_a_bare_starred_base_is_celestial_and_the_fiendish_one_is_asked_for():
    """No alignment is tracked yet, so every caster chooses as a neutral one may (CRB:
    "If you are neutral, you may choose which template to apply")."""
    s, e = table(caster())
    cast(e, spell="summon-monster-1", creature="fiendish dog")
    assert summoned(s)[0].from_template == "fiendish-dog"


def test_a_lower_list_brings_several_of_one_kind_each_its_own_creature():
    """Summon monster III's "1d4+1 creatures of the same kind from the 1st-level list".
    Five through `_bring_in`'s count would have been ONE troop actor with pooled hit
    points (troops.UNIT_FROM is 5); the book's five dogs are five dogs."""
    for seed in range(1, 30):
        s, e = table(caster(), seed=seed)
        out = cast(e, spell="summon-monster-3", creature="dog").outcomes[0]
        dogs = summoned(s)
        assert 2 <= len(dogs) <= 5, len(dogs)
        assert all(d.troop is None for d in dogs)
        assert f"1d4+1 answer: {len(dogs)}." in out.tell
        if len(dogs) == 5:
            break
    else:
        pytest.fail("no seed in 1-29 rolled five")


def test_the_summoned_act_on_the_casters_count():
    """"It appears where you designate and acts immediately, on your turn" (CRB). Measured
    before: each arrival rolled its own d20, and one dog came in at 6, after the thug."""
    s, e = table(caster())
    cast(e, spell="summon-monster-3", creature="dog")
    order = [r for r, _ in s.initiative]
    assert order.index("c1") == len(order) - 1
    assert all(n == 20 for r, n in s.initiative if r != "c1")


def test_summon_natures_ally_calls_the_plain_animal():
    """Table 10-2 carries no template: a dog is a dog."""
    s, e = table(caster(cls="druid", book=("summon-nature-s-ally-1",)))
    cast(e, spell="summon-nature-s-ally-1", creature="dog")
    assert summoned(s)[0].from_template == "dog"


def test_augment_summoning_adds_four_strength_and_constitution_for_the_spell():
    """Augment Summoning's +4 enhancement to Strength and Constitution, from its feat
    document (content/feats/mechanics/summoning.json), on the creature, with the spell's
    clock — and Constitution's hit points with it. A celestial dog: Str 13 → 17, Con 15 →
    19, 1 Hit Die, 6 → 8 hit points, full on arrival."""
    plain_s, plain_e = table(caster())
    cast(plain_e, spell="summon-monster-1", creature="dog")
    plain = summoned(plain_s)[0]
    s, e = table(caster(feats=("Spell Focus (conjuration)", "Augment Summoning")))
    out = cast(e, spell="summon-monster-1", creature="dog").outcomes[0]
    dog = summoned(s)[0]
    assert dog.ability_score("str") == plain.ability_score("str") + 4
    assert dog.ability_score("con") == plain.ability_score("con") + 4
    assert dog.hp_max == plain.hp_max + 2 * max(1, dog.hit_dice) and dog.hp == dog.hp_max
    buffs = [b for b in dog.effects if b.kind == "buff"]
    assert {b.rounds_left for b in buffs} == {5}
    assert {b.origin for b in buffs} == {"feat:augment-summoning"}
    assert "Augment Summoning" in out.tell
    assert not [b for b in s.actors["pc"].effects if b.kind == "buff"]


def test_superior_summoning_adds_one_to_a_summons_of_several():
    for seed in (1, 2, 3):
        a_s, a_e = table(caster(), seed=seed)
        cast(a_e, spell="summon-monster-3", creature="dog")
        b_s, b_e = table(caster(feats=("Spell Focus (conjuration)", "Augment Summoning",
                                       "Superior Summoning")), seed=seed)
        cast(b_e, spell="summon-monster-3", creature="dog")
        assert len(summoned(b_s)) == len(summoned(a_s)) + 1


def test_a_table_summon_document_names_a_table_or_a_creature_never_both():
    from rules import effectspec

    assert effectspec.validate({"type": "summon", "table": "summon-monster", "level": 3})\
        == []
    assert effectspec.validate({"type": "summon", "creature": "dog"}) == []
    assert effectspec.validate({"type": "summon"})
    assert effectspec.validate({"type": "summon", "table": "summon-monster", "level": 12})


# --- a chosen energy -----------------------------------------------------------------------

def test_protection_from_energy_asks_which_energy_and_absorbs_twelve_a_level():
    """Audit 2026-11-22: protection from energy granted an immunity to the words "one
    energy type chosen when you cast", which matched no damage at all. Now the cast names
    the energy, and the ward absorbs 12 points per caster level (84 at 7) and then is
    gone; what gets past an exhausted ward lands as usual."""
    pc = caster(cls="sorcerer", level=7, book=("protection-from-energy",))
    s, e = table(pc, fight=False)
    with pytest.raises(IntentError) as err:
        e.validate([{"op": "cast", "actor": "pc",
                     "params": {"spell": "protection-from-energy", "aim": "self"}}])
    assert err.value.code == "choose_energy"
    out = cast(e, spell="protection-from-energy", aim="self", energy="fire").outcomes[0]
    assert "absorbed 84 points" in out.tell
    assert not pc.immune_to("fire")
    first = pc.take_damage(30, "fire")
    assert first["warded"] == 30 and first["taken"] == 0 and first["rolled"] == 30
    hp = pc.hp
    second = pc.take_damage(60, "fire")
    assert second["warded"] == 54 and second["taken"] == 6 and pc.hp == hp - 6
    assert not [x for x in pc.effects if x.kind == "immunity"]
    assert pc.take_damage(5, "cold")["taken"] == 5


def test_an_energy_that_is_not_one_of_the_five_is_refused():
    pc = caster(cls="sorcerer", level=7, book=("protection-from-energy",))
    s, e = table(pc, fight=False)
    with pytest.raises(IntentError) as err:
        e.validate([{"op": "cast", "actor": "pc", "params": {
            "spell": "protection-from-energy", "aim": "self", "energy": "force"}}])
    assert "'force' is not one of them" in str(err.value)


def test_the_book_spell_is_untouched_by_the_cast_that_bound_it():
    """The choice is written on a COPY: the next caster must be asked again."""
    from rules import spells as spells_mod

    pc = caster(cls="sorcerer", level=7, book=("protection-from-energy",))
    s, e = table(pc, fight=False)
    cast(e, spell="protection-from-energy", aim="self", energy="acid")
    doc = spells_mod.get("protection-from-energy").effects[0]
    assert doc.get("choice_key") == "energy" and not doc.get("target")


# --- metamagic -----------------------------------------------------------------------------

SORC = ("magic-missile", "mage-armor", "fireball", "burning-hands")
META = ("Extend Spell", "Empower Spell", "Maximize Spell", "Still Spell", "Silent Spell")


def test_extend_doubles_the_clock_and_costs_a_slot_one_level_higher():
    """Mage armor at caster level 7 is 7 hours (4,200 rounds); extended, 8,400, paid from
    a 2nd-level slot and none of the 1st."""
    pc = caster(cls="sorcerer", level=7, book=SORC, feats=META)
    s, e = table(pc, fight=False)
    first, second = (casting.pool_left(pc, casting.slot_pool(n)) for n in (1, 2))
    out = cast(e, spell="mage-armor", aim="self", metamagic="extend").outcomes[0]
    assert [x.rounds_left for x in pc.effects if x.source == "Mage Armor"] == [8400]
    assert casting.pool_left(pc, casting.slot_pool(1)) == first
    assert casting.pool_left(pc, casting.slot_pool(2)) == second - 1
    assert "extended, in a level 2 slot" in out.tell


def test_extend_refuses_an_instantaneous_spell():
    s, e = table(caster(cls="sorcerer", level=7, book=SORC, feats=META))
    with pytest.raises(IntentError) as err:
        e.validate([{"op": "cast", "actor": "pc", "params": {
            "spell": "fireball", "at": "c1", "metamagic": ["extend-spell"]}}])
    assert err.value.code == "metamagic" and "instantaneous" in str(err.value)


def test_a_metamagic_feat_not_held_is_refused():
    s, e = table(caster(cls="sorcerer", level=7, book=SORC, feats=("Extend Spell",)))
    with pytest.raises(IntentError) as err:
        e.validate([{"op": "cast", "actor": "pc", "params": {
            "spell": "magic-missile", "at": "c1", "metamagic": "maximize"}}])
    assert "does not have the maximize spell feat" in str(err.value)


@pytest.mark.parametrize("seed", [1, 2, 3, 4])
def test_empower_is_half_again_and_maximize_is_the_top_of_the_dice(seed):
    """Burning hands caps at 5d4. Empowered, the same roll counts half again
    ("including bonuses to those dice rolls"); maximized it is 20 whatever the dice say;
    both, 20 plus half the roll (CRB, Maximize Spell)."""
    def hit(meta):
        # Level 12: empowered and maximized is a 6th-level slot.
        pc = caster(cls="sorcerer", level=12, book=SORC, feats=META)
        s, e = table(pc, seed=seed)
        return cast(e, spell="burning-hands", at="c1",
                    **({"metamagic": meta} if meta else {})).outcomes[0]

    rolled = hit(None).rolls[0].total
    emp, mx, both = hit("empower"), hit("maximize"), hit(["empower", "maximize"])
    assert f"the {rolled} rolled counts as {rolled + rolled // 2}." in emp.tell
    assert f"the {rolled} rolled counts as 20." in mx.tell
    assert f"the {rolled} rolled counts as {20 + rolled // 2}." in both.tell


def test_a_spontaneous_metamagic_cast_takes_the_whole_round_in_a_fight():
    """CRB: a sorcerer's metamagic spell is a full-round action. After a move it is
    refused with nothing spent; cast, it spends the move."""
    pc = caster(cls="sorcerer", level=7, book=SORC, feats=META)
    s, e = table(pc)
    s.move_spent["pc"] = s.round
    left = casting.pool_left(pc, casting.slot_pool(3))
    out = cast(e, spell="magic-missile", at="c1", metamagic="empower").outcomes[0]
    assert out.status != "resolved" and "whole round" in out.tell
    assert casting.pool_left(pc, casting.slot_pool(3)) == left
    s2, e2 = table(caster(cls="sorcerer", level=7, book=SORC, feats=META))
    cast(e2, spell="magic-missile", at="c1", metamagic="empower")
    assert s2.move_spent.get("pc") == s2.round


def test_still_spell_casts_in_armour_without_spell_failure():
    """Still Spell's copy has no somatic component, which is the one thing arcane spell
    failure reads ("If the spell lacks a somatic component, however, it can be cast with
    no chance of arcane spell failure")."""
    pc = caster(cls="sorcerer", level=7, book=SORC, feats=META)
    pc.armour = "full-plate"
    s, e = table(pc, seed=1)
    out = cast(e, spell="magic-missile", at="c1", metamagic="still").outcomes[0]
    assert not [x for x in out.effects if x.get("kind") == "spell_failure"]
    assert "arcane spell failure" not in out.tell


def test_a_deafened_caster_risks_the_words_and_silent_spell_does_not():
    """Deafened (CRB, Conditions): "a 20% chance of spell failure when casting spells with
    verbal components". The engine rolled no such chance before lane C; a Silent spell's
    copy has no V and rolls none."""
    pc = caster(cls="sorcerer", level=7, book=SORC, feats=META)
    pc.add_condition("deafened", 10)
    s, e = table(pc, seed=1)
    loud = cast(e, spell="magic-missile", at="c1").outcomes[0]
    assert "Deafened" in loud.tell or "deafened" in loud.tell
    pc2 = caster(cls="sorcerer", level=7, book=SORC, feats=META)
    pc2.add_condition("deafened", 10)
    s2, e2 = table(pc2, seed=1)
    quiet = cast(e2, spell="magic-missile", at="c1", metamagic="silent").outcomes[0]
    assert "eafened" not in quiet.tell


def test_a_prepared_caster_casts_the_copy_prepared_with_the_feat():
    """CRB: a wizard "must prepare the spell with the feat applied", in the higher slot.
    The copy is its own prepared key; a wizard who prepared plain mage armor cannot
    extend it at the cast, and one who prepared it extended spends that copy."""
    key = casting.metamagic_key("mage-armor", ["extend-spell"])
    pc = caster(level=7, book=("mage-armor",), feats=META,
                prepared={"mage-armor": 1})
    s, e = table(pc, fight=False)
    with pytest.raises(IntentError) as err:
        e.validate([{"op": "cast", "actor": "pc", "params": {
            "spell": "mage-armor", "aim": "self", "metamagic": "extend"}}])
    assert "fixes metamagic when preparing" in str(err.value)
    pc = caster(level=7, book=("mage-armor",), feats=META, prepared={key: 1})
    s, e = table(pc, fight=False)
    assert casting._level(pc, key) == 2 and casting.held_at(pc, 2) == 1
    cast(e, spell=key, aim="self")
    assert casting.prepared_count(pc, key) == 0
    assert [x.rounds_left for x in pc.effects if x.source == "Mage Armor"] == [8400]


def test_a_metamagic_copy_survives_a_save():
    key = casting.metamagic_key("mage-armor", ["extend-spell"])
    pc = caster(level=7, book=("mage-armor",), feats=META, prepared={key: 1})
    again = from_dict(to_dict(pc), ref="pc")
    assert casting.prepared_count(again, key) == 1


def test_metamagic_documents_are_validated_with_the_fix_named():
    assert classbuilder.validate_feat_document("extend-spell", {
        "metamagic": {"does": "extend", "levels": 1}}) == []
    bad = classbuilder.validate_feat_document("extend-spell", {
        "metamagic": {"does": "lengthen", "levels": 1}})
    assert bad and "one of extend" in bad[0]
    assert classbuilder.validate_feat_document("augment-summoning", {
        "summoned": [{"type": "ability_mod", "target": "strength", "amount": 4}]})


def test_the_feat_files_carry_only_their_own_lanes_ids():
    """The later feat file silently wins (lane brief): summoning.json and metamagic.json
    must never name an id core.json already documents."""
    folder = Path("content/feats/mechanics")
    core = set(json.loads((folder / "core.json").read_text(encoding="utf-8")))
    for name in ("summoning.json", "metamagic.json"):
        mine = {k for k in json.loads((folder / name).read_text(encoding="utf-8"))
                if not k.startswith("_")}
        assert not mine & core, (name, mine & core)
    assert metamagic.DOES


def test_enlarge_doubles_a_medium_range_on_the_copy_only():
    """Enlarge Spell: "medium-range spells have a range of 200 ft. + 20 ft./level". Magic
    missile at caster level 7: 170 ft plain, 340 ft enlarged; the book's spell is
    unchanged."""
    from rules import spells as spells_mod

    pc = caster(cls="sorcerer", level=7, book=SORC, feats=("Enlarge Spell",))
    plain = spells_mod.get("magic-missile")
    big = metamagic.apply(plain, pc, ["enlarge-spell"])
    assert spells_mod.range_feet(plain, 7) == 170
    assert spells_mod.range_feet(big, 7) == 340
    assert spells_mod.range_feet(spells_mod.get("magic-missile"), 7) == 170


def test_resist_energy_as_lane_b_wrote_it_is_answered_by_the_energy_param(monkeypatch):
    """Lane B wrote resist energy (part-21.json) as a `choose_one` of five `resistance`
    options. The `energy` param answers it as it answers a `choice_key` spec: refused
    before the slot without one, and naming the option `choose` would have counted to.
    Rated 10 below caster level 7 and 20 from it (CRB), worked out for the caster."""
    import dataclasses

    from rules import spells as spells_mod

    amount = "min(30, max(10, 10 * ((caster_level + 1) / 4)))"
    real = spells_mod.get("resist-energy")
    b = dataclasses.replace(real, effects=[{"type": "choose_one", "options": [
        {"type": "resistance", "target": e, "amount": amount}
        for e in ("acid", "cold", "electricity", "fire", "sonic")]}])
    monkeypatch.setitem(spells_mod.all_spells(), "resist-energy", b)
    pc = caster(cls="sorcerer", level=7, book=("resist-energy",))
    s, e = table(pc, fight=False)
    with pytest.raises(IntentError) as err:
        e.validate([{"op": "cast", "actor": "pc",
                     "params": {"spell": "resist-energy", "aim": "self"}}])
    assert err.value.code == "choose_energy" and err.value.fix["options"][3] == "fire"
    [intent] = e.validate([{"op": "cast", "actor": "pc", "params": {
        "spell": "resist-energy", "aim": "self", "energy": "fire"}}])
    assert intent.params["choose"] == 4
    copy = e._cast_copy(intent, pc, b, [])
    assert copy.effects[0]["options"][3]["amount"] == 20

"""What has to happen to an ingredient before it is any use.

The bench could brew but treated everything as equally ready: a shelled nut, a volatile
resin and a handful of leaves all went into the pot the same way. These are the author's
rules, each test naming the sentence it protects.
"""
from __future__ import annotations

import pytest

from rules import herbprep as H


def prep(**over):
    return H.Prep(**over)


# --- the order the steps come in ---------------------------------------------------------

def test_nothing_can_be_done_to_a_thing_still_in_its_shell():
    """"What herbs need extracting (pulling it out of a shell etc..) before they can be
    ground or mixed or brewed"."""
    nut = prep(needs_extraction=True)
    for step in ("grind", "mix", "brew", "neutralise"):
        ok, why = H.can(step, nut, "raw")
        assert not ok and "extracted" in why, step
    assert H.can("extract", nut, "raw")[0]


def test_extracting_something_that_has_no_shell_is_refused():
    ok, why = H.can("extract", prep(), "raw")
    assert not ok and "nothing to extract" in why


def test_a_volatile_herb_must_be_neutralised_before_grinding():
    """"what herb are volatile and need neutralized before they can be ground"."""
    resin = prep(volatile=True)
    ok, why = H.can("grind", resin, "raw")
    assert not ok and "neutralise it before grinding" in why
    assert H.can("neutralise", resin, "raw")[0]
    assert H.can("grind", resin, "neutralised")[0]


def test_neutralising_something_stable_is_refused():
    ok, why = H.can("neutralise", prep(), "raw")
    assert not ok and "not volatile" in why


def test_the_whole_chain_for_the_worst_case():
    """A shelled, volatile herb that cannot be brewed raw: extract, neutralise, grind,
    and only then does the pot accept it."""
    worst = prep(needs_extraction=True, volatile=True, brew_raw=False)
    for step, state in (("extract", "raw"), ("neutralise", "extracted"),
                        ("grind", "neutralised")):
        assert H.can(step, worst, state)[0], (step, state)
    assert H.can("brew", worst, "ground")[0]


# --- what can be mixed and brewed raw ----------------------------------------------------

def test_an_ordinary_herb_mixes_and_brews_raw():
    assert H.can("mix", prep(), "raw")[0]
    assert H.can("brew", prep(), "raw")[0]


def test_one_that_cannot_says_to_grind_it_first():
    """"what herbs can be mixed raw vs only when ground", and the same for brewing.
    The refusal is the rule: a player who reads it once knows it thereafter."""
    ok, why = H.can("mix", prep(mix_raw=False), "raw")
    assert not ok and "once it has been ground" in why
    assert H.can("mix", prep(mix_raw=False), "ground")[0]

    ok, why = H.can("brew", prep(brew_raw=False), "raw")
    assert not ok and "once it has been ground" in why
    assert H.can("brew", prep(brew_raw=False), "ground")[0]


def test_a_herb_that_cannot_be_ground_at_all():
    ok, why = H.can("grind", prep(can_grind=False), "raw")
    assert not ok and "cannot be ground" in why


# --- the clock ---------------------------------------------------------------------------

def test_animal_parts_have_two_days_and_plants_a_week():
    """"all animal parts need preserved within 48 hours for they become garbage and
    fresh herbs last a week"."""
    assert H.spoils_after(prep(animal=True)) == 48
    assert H.spoils_after(prep()) == 24 * 7


def test_a_gland_left_two_days_is_refuse():
    gland = prep(animal=True)
    assert not H.is_spoiled(gland, 47)
    assert H.is_spoiled(gland, 48)


def test_a_leaf_keeps_a_week_and_not_a_day_longer():
    leaf = prep()
    assert not H.is_spoiled(leaf, 167)
    assert H.is_spoiled(leaf, 168)


def test_preserved_material_does_not_spoil_at_all():
    assert not H.is_spoiled(prep(animal=True), 10_000, preserved=True)


def test_a_monster_part_is_an_animal_part_without_being_told():
    """The 161 already authored say nothing about any of this. A monster part is on
    the shorter clock because of what it is, not because somebody remembered to tick a
    box that did not exist when it was written."""
    assert H.Prep.of({"kind": "monster part"}).animal
    assert not H.Prep.of({"kind": "herb"}).animal


def test_everything_already_authored_behaves_exactly_as_it_did():
    """Every default is the old behaviour: grind it, mix it, brew it, keep it a week."""
    plain = H.Prep.of({"kind": "herb", "name": "Leechwort"})
    assert plain == H.Prep()
    for step in ("grind", "mix", "brew"):
        assert H.can(step, plain, "raw")[0], step


def test_flags_read_from_yes_and_no_as_well_as_booleans():
    """The editor stores choices as strings, and the loader must not care."""
    got = H.Prep.of({"kind": "herb", "volatile": "yes", "brew_raw": "no"})
    assert got.volatile and not got.brew_raw


# --- and it reaches the ingredient editor ------------------------------------------------

def test_the_ingredient_form_offers_every_preparation_rule():
    """Modular was the ask: the bench draws every editor from the registry, so a new
    rule is one Field and appears in the UI without a line of template changing."""
    from rules import registry

    fields = {f.name for f in registry.KINDS["ingredients"].fields}
    assert {"needs_extraction", "volatile", "can_grind", "mix_raw", "brew_raw",
            "animal"} <= fields


def test_every_new_field_explains_itself_or_is_obvious():
    from rules import registry

    for f in registry.KINDS["ingredients"].fields:
        if f.name in ("volatile", "mix_raw", "brew_raw", "needs_extraction", "animal"):
            assert f.help, f.name


# --- salt (asked for 2026-08-23) ---------------------------------------------------------

class Carrier:
    """Carried goods by name, and the satchel by material id (where a counter's curing salt
    lands, `goods.deliver`)."""
    def __init__(self, inventory=None, **goods):
        self.goods = goods
        self.inventory = dict(inventory or {})

    def spend(self, key, n):
        took = min(int(self.inventory.get(key, 0)), int(n))
        self.inventory[key] = self.inventory.get(key, 0) - took
        if self.inventory[key] <= 0:
            self.inventory.pop(key)
        return took


def test_carrying_salt_preserves_it_without_being_asked():
    """"preservation can be automatic if i have salt" — so it does not depend on the
    player remembering on the turn they pick a gland up, which is the turn they are
    least likely to be thinking about the 48 hours that start now."""
    gland = H.Prep(animal=True)
    ok, cost, why = H.preserve_automatically(Carrier({"curing-salt": 2}), gland)
    assert ok and cost < 0 and "salt" in why


def test_without_salt_it_says_how_long_there_is():
    ok, cost, why = H.preserve_automatically(Carrier(rope=50), H.Prep(animal=True))
    assert not ok and cost == 0
    assert "48 hours" in why


def test_salt_is_curing_salt_by_id_never_a_word_in_a_name():
    """Re-pinned 2026-10-08 (leatherworking lane C; plan §6 and the owner's answer 8, "salt
    costs salt"): this matched name fragments ("salt", "Sea Salt", "saltpetre") over
    everything carried, the shape law 1 refuses, and preserved for nothing. The one reader
    counts curing salt by material id (`materials.is_salt`) in measures, and spends them."""
    for name in ("salt", "Sea Salt", "a pouch of curing salt"):
        assert not H.has_salt(Carrier(**{name: 1})), name
    assert not H.has_salt(Carrier(lantern=1))
    pack = Carrier({"curing-salt": 3})
    assert H.has_salt(pack) and H.salt_measures(pack) == 3
    assert H.spend_salt(pack, 2) == 2 and H.salt_measures(pack) == 1


# --- the tags actually survive the trip in (found by applying them, 2026-08-23) ------

def test_the_ingredient_dataclass_has_somewhere_to_put_them():
    """55 ingredients were tagged, the file merged correctly, and every one still read
    as an ordinary leaf: `from_dict` builds a dataclass and quietly drops anything it
    has no field for. The flags were nowhere on `Ingredient`, so they vanished on the
    way in with nothing raised and nothing logged."""
    from rules.ingredients import Ingredient

    fields = set(Ingredient.__dataclass_fields__)
    assert {"needs_extraction", "volatile", "can_grind", "mix_raw", "brew_raw",
            "animal"} <= fields


def test_a_flag_stored_as_the_word_no_is_not_true():
    """The editor stores choices as "yes"/"no" and the importer writes the same. A
    plain `bool("no")` is True, which would turn "cannot be ground" into its
    opposite — the worst direction for a rule about volatile things to fail in."""
    from rules.ingredients import from_dict

    got = from_dict({"id": "x", "name": "X", "can_grind": "no", "volatile": "yes"})
    assert got.can_grind is False and got.volatile is True


def test_a_monster_part_is_animal_unless_the_entry_says_otherwise():
    from rules.ingredients import from_dict

    assert from_dict({"id": "a", "name": "A", "kind": "monster part"}).animal
    assert not from_dict({"id": "b", "name": "B", "kind": "herb"}).animal
    # And an explicit answer wins, which is how a plant growing on a creature is told
    # apart from the creature.
    assert from_dict({"id": "c", "name": "C", "kind": "monster part",
                      "animal": "no"}).animal is False


def test_the_shipped_corpus_is_untouched_by_tagging():
    """The tags land in the homebrew overlay. Deleting one file undoes all of it, and
    a corrected corpus in a later build is not shadowed by a stale copy."""
    import json
    from pathlib import Path

    corpus = json.loads(
        Path("content/ingredients/herbs-and-parts.json").read_text(encoding="utf-8"))
    entries = corpus.get("ingredients", corpus)
    assert not any("volatile" in e for e in entries), \
        "preparation flags belong in the overlay, not in the shipped file"


def test_a_plant_keeps_a_week_where_a_gland_keeps_two_days():
    from rules.sheet import load_pc

    pc = load_pc("fixtures/pc-kesst.json")
    pc.carry("acacia", 1, at_minute=0)
    pc.carry("wyrmfang-venom", 1, at_minute=0)
    from rules import ingredients as ing

    e = ing.all_ingredients()
    at_three_days = 72 * 60
    assert pc.freshness("acacia", at_three_days, H.Prep.of(e["acacia"]))[0] is False
    assert pc.freshness("wyrmfang-venom", at_three_days,
                        H.Prep.of(e["wyrmfang-venom"]))[0] is True


def test_material_carried_before_the_clock_existed_is_treated_as_fresh():
    """A save that retroactively spoiled somebody's satchel would be a worse answer
    than a lenient one."""
    from rules.sheet import load_pc

    pc = load_pc("fixtures/pc-kesst.json")
    pc.inventory["wyrmfang-venom"] = 2          # no timestamp, as an old save has none
    spoiled, _ = pc.freshness("wyrmfang-venom", 9999 * 60, H.Prep(animal=True))
    assert spoiled is False


# --- a herb the GM hands over gets the same clock (2026-08-23) ------------------------

def _scene_at(minute=0):
    from rules.dice import Dice
    from rules.engine import Engine, Scene
    from rules.sheet import load_pc

    scene = Scene(location_id=None)
    scene.add(load_pc("fixtures/pc-kesst.json"))
    scene.clock_minutes = minute
    return Engine(scene, Dice(seed=3))


def _give(engine, item, count=1):
    raw = {"op": "give", "actor": "pc",
           "params": {"item": item, "count": count, "to": "pc"}}
    # The test's own word that the thing exists: since 2026-10-16 a pick-up from nowhere
    # is refused (`Engine._picked_from_nowhere`, tests/test_scenery.py), and what these
    # pin is where a herb lands once it is in hand, not where it came from.
    return engine.run(engine.validate([raw], origin="author:test")).outcomes[0]


def test_a_handed_over_herb_reaches_the_satchel():
    """It used to land in `goods` as a generic carried thing, so the crafting bench
    could not see it at all — the shelf reads the satchel."""
    eng = _scene_at()
    _give(eng, "woundwort", 3)
    pc = eng.scene.pc()
    assert pc.inventory.get("woundwort") == 3
    assert "woundwort" not in {k.lower() for k in pc.goods}, \
        "one herb in two lists is two counts that drift"


def test_it_is_named_from_the_prose_the_gm_actually_writes():
    """"three sprigs of woundwort" is how a handover is written, not `woundwort`."""
    eng = _scene_at()
    _give(eng, "a salamander ember gland")
    assert eng.scene.pc().inventory.get("salamander-ember-gland") == 1


def test_the_clock_starts_when_it_changes_hands():
    """The 48 hours were only counted from foraging, so a gland handed across a table
    kept forever — which made the spoilage rule avoidable by never picking anything up
    yourself."""
    eng = _scene_at(minute=600)
    _give(eng, "wyrmfang venom")
    pc = eng.scene.pc()
    assert pc.picked_at.get("wyrmfang-venom") == 600

    prep = H.Prep(animal=True)
    assert pc.freshness("wyrmfang-venom", 600 + 47 * 60, prep)[0] is False
    assert pc.freshness("wyrmfang-venom", 600 + 49 * 60, prep)[0] is True


def test_salt_in_the_pack_preserves_what_is_handed_over_too():
    eng = _scene_at()
    eng.scene.pc().inventory["curing-salt"] = 1      # by id, and it is spent
    _give(eng, "wyrmfang venom")
    assert "curing-salt" not in eng.scene.pc().inventory
    assert eng.scene.pc().preserved.get("wyrmfang-venom") is True


def test_something_that_is_not_an_ingredient_still_goes_to_the_pack():
    eng = _scene_at()
    _give(eng, "brass key")
    pc = eng.scene.pc()
    assert pc.goods.get("brass key") == 1 and not pc.inventory


def test_a_near_miss_is_not_a_match():
    """Deliberately not fuzzy: the wrong herb in the satchel is one the player crafts
    with for a week before noticing."""
    from rules import ingredients as ing

    assert ing.by_name("a brass lantern") is None
    assert ing.by_name("Juniper Berry").name == "Juniper Berry"   # not "Juniper"


def test_the_matcher_has_no_stray_control_characters():
    """`\b` written through a shell heredoc arrives as a literal backspace byte, which
    silently breaks the pattern while every test still passes. It happened here: the
    word-boundary match became a search for a control character and no phrase longer
    than the bare name resolved. CLAUDE.md opens its everyday section with this."""
    from pathlib import Path

    source = Path("rules/ingredients.py").read_text(encoding="utf-8")
    assert not any(chr(c) in source for c in range(1, 9)), \
        "a control character is in the source"


# --- the step bench's states (herbalism revamp, 2026-10-02) ------------------------------

def test_the_states_are_the_contracts_five():
    """docs/herbalism-contracts.md §2 fixes the vocabulary the page and the bench share:
    raw, extracted, neutralised, ground, dried. "preserved" left with the Preserve method;
    salting is a satchel flag, not a state a thing is worked into."""
    assert H.STATES == ("raw", "extracted", "neutralised", "ground", "dried")


def test_drying_is_a_step_and_leaves_it_dried():
    """Dry is the step bench's solid concentration (plan §5.3). Something still in its
    shell is opened first, as for every other step."""
    assert H.can("dry", prep()) == (True, "")
    ok, why = H.can("dry", prep(needs_extraction=True))
    assert not ok and "extracted" in why


def test_preserving_is_not_a_bench_step_any_more_and_says_what_replaced_it():
    """The owner retired Preserve (plan §2). A refusal that named no way through would
    read like a bug; this one names the salt that still does the job on pick-up."""
    ok, why = H.can("preserve", prep())
    assert not ok and "salt" in why


def test_the_reasons_the_bench_prints_carry_no_em_dash():
    """UI plan §8: no em-dashes in new player-facing bench strings. These reasons are
    printed on the step bench's tiles verbatim."""
    reasons = [H.can("grind", prep(volatile=True))[1],
               H.can("preserve", prep())[1],
               H.preserve_automatically(type("Bare", (), {"goods": {}, "inventory": {}})(),
                                        prep(animal=True))[2]]
    assert all(r and "—" not in r for r in reasons), reasons


def test_a_herb_handed_over_keeps_its_age():
    """Ponytail audit 2026-11-07 (smaller findings): the handover carried a herb with the
    clock reset to the minute it changed hands, so a gland picked 40 hours before was
    fresh for another 48 in the next pair of hands — the spoilage rule dodged by passing
    it to a friend. The giver's pick-time travels with it (`Actor.carry_from`)."""
    from rules.bestiary import instantiate

    eng = _scene_at(minute=600)
    friend = instantiate("guildhand", scene=eng.scene, name="Drenn")
    eng.scene.add(friend)
    friend.carry("wyrmfang-venom", 1, at_minute=600)
    eng.scene.clock_minutes = 600 + 40 * 60
    eng.run(eng.validate([{"op": "give", "actor": friend.ref, "because": "t",
                           "params": {"item": "wyrmfang venom", "to": "pc"}}]))
    pc = eng.scene.pc()
    assert pc.inventory.get("wyrmfang-venom") == 1
    assert pc.picked_at.get("wyrmfang-venom") == 600
    assert pc.freshness("wyrmfang-venom", 600 + 49 * 60, H.Prep(animal=True))[0] is True


def test_a_looted_herb_starts_its_clock_at_the_loot():
    """Ponytail audit 2026-11-07: a body's satchel went into the looter's with no clock at
    all, which `freshness` reads as never spoiling — looted animal parts kept forever.
    Taken with the body's own pick-time, or from the minute of the loot when it has none."""
    from rules.bestiary import instantiate

    eng = _scene_at(minute=600)
    body = instantiate("thug", scene=eng.scene, name="the poacher")
    eng.scene.add(body)
    body.inventory["wyrmfang-venom"] = 1
    body.hp = -13
    eng.run(eng.validate([{"op": "loot", "actor": "pc", "because": "t",
                           "params": {"from": body.ref}}]))
    pc = eng.scene.pc()
    assert pc.inventory.get("wyrmfang-venom") == 1
    assert pc.picked_at.get("wyrmfang-venom") == 600
    assert pc.freshness("wyrmfang-venom", 600 + 49 * 60, H.Prep(animal=True))[0] is True

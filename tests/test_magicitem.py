"""The second enchanting mode: Pathfinder's own magic item creation.

Everything here pins a rule from the book or a house rule taken deliberately against
it. The two house rules are the whole reason this mode is playable solo — a potion
stands in for the prerequisite spell, and permanency is not required — and both are
tested as decisions rather than as behaviour, so nobody "fixes" them back into the book
without reading why they went.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rules import effectspec
from rules import magicitem as mi

SHIPPED = Path("content/materials/magic-items.json")

MW_SWORD = {"masterwork": True, "kind": "weapon", "weapon": "longsword"}
PLAIN_SWORD = {"masterwork": False, "kind": "weapon"}
MW_ARMOUR = {"masterwork": True, "kind": "armour", "armour": "breastplate"}


@pytest.fixture
def corpus():
    return json.loads(SHIPPED.read_text(encoding="utf-8"))["materials"]


def chain(materials=(), *, plus=0, item="longsword", name="", stock=None):
    return mi.Chain(material_ids=list(materials), enhancement=plus, item=item,
                    name=name, stock_used=dict(stock or {}))


# A potion in the shape the alchemist track ships: the contract is `holds_spell` plus a
# caster level on the stock entry, and this mode reads only those two fields.
def potion(spell_id, count=1, caster_level=5):
    return {"name": f"Potion of {spell_id}", "holds_spell": spell_id,
            "caster_level": caster_level, "count": count}


# --- the catalogue ------------------------------------------------------------------------

def test_the_catalogue_loads_and_ids_are_unique(corpus):
    """Duplicate ids merge silently on read — one entry shadowing another with no error
    anywhere, which is how a priced property quietly becomes a different one."""
    ids = [m["id"] for m in corpus]
    assert not {i for i in ids if ids.count(i) > 1}
    assert len(mi.catalogue()) == len(corpus)


def test_the_catalogue_is_only_its_own_file():
    """This mode reads `magic-items.json` alone, where the essence mode reads the whole
    shared materials folder. A blacksmith's quenching brine appearing as a weapon
    property would be nonsense rather than generosity."""
    assert "quartz-focus" not in mi.catalogue()
    assert "mi-flaming" in mi.catalogue()


def test_every_authored_effect_validates(corpus):
    """Zero invalid specs, offenders printed. A spec that fails validation renders on a
    card and does nothing when the engine is asked — the silent failure the effect
    vocabulary exists to prevent."""
    bad = []
    for m in corpus:
        for where in ("effects", "drawbacks"):
            for i, spec in enumerate(m.get(where) or []):
                bad.extend(effectspec.validate(spec, f"{m['id']}.{where}[{i}]"))
    for line in bad:
        print(line)
    assert not bad, f"{len(bad)} invalid specs (printed above)"


def test_every_prerequisite_spell_is_a_real_spell(corpus):
    """The prerequisite is the whole point of the potion rule, so a misspelled spell id
    would refuse a working for a spell no potion could ever hold. Grounded against the
    corpus rather than trusted — "ground every name", measured."""
    from rules import spells

    known = spells.all_spells()
    missing = sorted({m["spell"] for m in corpus
                      if m.get("spell") and m["spell"] not in known})
    assert not missing, f"prerequisite spells not in the corpus: {missing}"


def test_all_three_kinds_are_stocked(corpus):
    """Weapons, armour and jewelry each need enough to choose between, or a mode tab
    opens on a list of four things."""
    by_kind = {}
    for m in corpus:
        by_kind.setdefault(m["kind"], []).append(m)
    assert len(by_kind["weapon_property"]) >= 15
    assert len(by_kind["armour_property"]) >= 15
    assert len(by_kind["wondrous"]) >= 40


# --- the +1 ladder and its caps -----------------------------------------------------------

def test_a_plain_plus_one_longsword():
    """The simplest working in the book, end to end: masterwork sword, +1, no property,
    2,000 gp market price, 1,000 to make, DC 5 + caster level."""
    result = mi.preview(3, chain(plus=1), item=MW_SWORD)
    assert result.problems == []
    assert result.name == "Longsword +1"
    assert result.price_gp == 2000 and result.cost_gp == 1000
    assert result.total_bonus == 1
    attack = [s for s in result.specs if s.get("target") == "attack"]
    assert attack and attack[0]["amount"] == 1
    assert attack[0]["bonus_type"] == "enhancement"


def test_enhancement_stops_at_plus_five():
    """The book's ceiling on the enhancement bonus itself, separate from the +10 total.
    A +6 sword is not a thing; the budget past +5 goes on properties."""
    result = mi.preview(5, chain(plus=6), item=MW_SWORD)
    assert any("stops at +5" in p for p in result.problems)


def test_a_property_needs_an_enhancement_bonus_under_it():
    """The ordering rule people forget: named properties are priced as bonus
    equivalents *on top of* an enhancement bonus, so there has to be one. A flaming
    sword that is not at least +1 cannot be priced at all."""
    result = mi.preview(5, chain(["mi-flaming"], plus=0), item=MW_SWORD)
    assert any("at least +1" in p for p in result.problems)
    allowed = mi.preview(5, chain(["mi-flaming"], plus=1),
                         stock={"p": potion("flame-blade")}, item=MW_SWORD)
    assert allowed.problems == []


def test_enhancement_and_properties_may_not_pass_plus_ten():
    """The book's total cap. Vorpal alone is +5, so a +5 vorpal sword is exactly the
    whole budget — and adding anything else to it is refused with the arithmetic
    spelled out."""
    exactly = mi.preview(5, chain(["mi-vorpal"], plus=5),
                         stock={"p": potion("circle-of-death")}, item=MW_SWORD)
    assert exactly.problems == [] and exactly.total_bonus == 10
    over = mi.preview(5, chain(["mi-vorpal", "mi-flaming"], plus=5), item=MW_SWORD)
    assert any("may not pass +10" in p for p in over.problems)


def test_pricing_squares_the_total_bonus():
    """N² × 2,000 for weapons and N² × 1,000 for armour. The squaring is the whole
    reason a high-end item is a campaign goal rather than a shopping trip: a +1 flaming
    sword is a +2 item at 8,000 gp, not 4,000."""
    flaming = mi.preview(5, chain(["mi-flaming"], plus=1), item=MW_SWORD)
    assert flaming.total_bonus == 2 and flaming.price_gp == 8000
    assert flaming.cost_gp == 4000
    armour = mi.preview(5, chain(["mi-shadow"], plus=1, item="breastplate"),
                        item=MW_ARMOUR)
    assert armour.total_bonus == 2 and armour.price_gp == 4000


def test_time_is_eight_hours_per_thousand_gp():
    """The book's clock, in the bench's unit. Rounded up to whole thousands because a
    day of crafting is not divisible and time is a cost — costs never round in the
    crafter's favour."""
    assert mi.craft_hours(2000) == 16
    assert mi.craft_hours(1) == 8, "a trinket still takes a working day"
    assert mi.craft_hours(0) == 0


def test_the_dc_is_five_plus_caster_level():
    """Craft Magic Arms and Armor's one number, and the highest caster level in the
    working sets it — a chain is as hard as its hardest piece."""
    result = mi.preview(5, chain(["mi-flaming"], plus=1), item=MW_SWORD)
    assert result.caster_level == 10 and result.dc == 15


# --- the vessel ---------------------------------------------------------------------------

def test_arms_and_armour_need_a_masterwork_vessel():
    """The book's gate, kept for weapons and armour."""
    assert any("not masterwork" in p
               for p in mi.preview(5, chain(plus=1), item=PLAIN_SWORD).problems)
    assert any("not masterwork" in p
               for p in mi.preview(5, chain(plus=1), item=None).problems)


def test_jewelry_needs_no_masterwork_vessel():
    """The book asks for masterwork on arms and armour and *not* on rings, amulets or
    wondrous items — a ring blank is a ring blank. Pinned so the asymmetry reads as the
    rule rather than as a check somebody forgot to write."""
    result = mi.preview(5, chain(["mi-ring-protection-1"], item="ring"),
                        stock={"p": potion("shield-of-faith")},
                        item={"masterwork": False, "kind": "jewelry"})
    assert result.problems == []
    assert result.name == "Ring of Protection +1"
    assert result.output["slot"] == "ring"


def test_a_wondrous_item_is_made_whole():
    """A wondrous item is not a property laid over an enhancement bonus, and mixing the
    two would price one item on two different tables at once."""
    result = mi.preview(5, chain(["mi-ring-protection-1"], plus=2, item="ring"),
                        item={"kind": "jewelry"})
    assert any("made whole" in p for p in result.problems)


def test_weapon_and_armour_properties_do_not_share_a_working():
    result = mi.preview(5, chain(["mi-flaming", "mi-shadow"], plus=1), item=MW_SWORD)
    assert any("different items" in p for p in result.problems)


# --- the two house rules ------------------------------------------------------------------

def test_a_potion_stands_in_for_the_prerequisite_spell():
    """The house rule that makes the mode playable solo. The book requires the creator
    to know the spell; in a one-person party a fighter could never qualify, so the
    requirement would not gate power — it would delete the feature. A potion holding
    the spell is consumed instead, and the alchemist's `holds_spell` field is the
    contract this reads."""
    held = {"potion-flame-blade": potion("flame-blade")}
    result = mi.preview(5, chain(["mi-flaming"], plus=1), stock=held, item=MW_SWORD)
    assert result.problems == []
    assert result.consumes == {"potion-flame-blade": 1}
    assert any("is consumed in the making" in n for n in result.notes)


def test_the_refusal_names_the_spell_and_both_ways_to_satisfy_it():
    """A refusal that only says "you cannot" sends the player to the rulebook. This one
    names the spell and both routes: know it, or carry a potion of it."""
    result = mi.preview(5, chain(["mi-keen"], plus=1), item=MW_SWORD)
    said = " ".join(result.problems)
    assert "Keen Edge" in said
    assert "neither know it nor carry a potion" in said
    assert "Brew or buy a potion" in said
    assert result.chance == 0, "a refused working must not offer odds"


def test_knowing_the_spell_also_satisfies_it():
    """The book's own route still works and costs nothing — the potion is an addition,
    not a replacement. Read through `rules/casting.knows`, read-only, and driven with a
    real wizard sheet rather than a stub: `knows` reads `class_data` and the spellbook,
    and a hand-made object that answers the wrong shape would prove nothing about
    whether a live character satisfies the prerequisite."""
    from rules.sheet import load_pc

    wizard = load_pc("fixtures/pc-thessaly.json")
    wizard.spellbook = ["keen-edge"]

    result = mi.preview(5, chain(["mi-keen"], plus=1), actor=wizard, item=MW_SWORD)
    assert result.problems == [], result.problems
    assert result.consumes == {}, "knowing the spell must not eat a potion"
    assert any("is known" in n for n in result.notes)

    # And the same wizard without the spell in the book is refused, so the pass above
    # is the spellbook doing the work rather than the caster class alone.
    wizard.spellbook = []
    refused = mi.preview(5, chain(["mi-keen"], plus=1), actor=wizard, item=MW_SWORD)
    assert any("Keen Edge" in p for p in refused.problems)


def test_a_potion_of_the_wrong_spell_does_not_satisfy_it():
    """The stand-in is per spell, not per potion. A shelf of cure light wounds does not
    make a keen blade."""
    held = {"potion-clw": potion("cure-light-wounds", count=9)}
    result = mi.preview(5, chain(["mi-keen"], plus=1), stock=held, item=MW_SWORD)
    assert any("Keen Edge" in p for p in result.problems)
    assert result.consumes == {}


def test_permanency_is_never_required():
    """The book's "…and permanency" prerequisites are dropped: a solo game cannot farm
    a 5th-level caster to cast it. Stated on the working itself, not only in the docs,
    so the house rule is visible at the bench."""
    result = mi.preview(5, chain(["mi-flaming"], plus=1),
                        stock={"p": potion("flame-blade")}, item=MW_SWORD)
    assert any("permanency" in n.lower() for n in result.notes)
    assert not any("permanency" in p.lower() for p in result.problems)


# --- dispatch and output ------------------------------------------------------------------

def test_chain_from_body_is_tolerant_about_shape():
    """The spine posts one body to whichever mode is active. A comma-joined string, a
    "+3", a list of stock ids instead of a dict — all survive, because the validation
    that matters happens in `preview` where a problem can be shown."""
    parsed = mi.chain_from_body({
        "materials": "mi-flaming, mi-keen", "enhancement": "+3",
        "vessel": "longsword", "stock": ["potion-a"],
        "methods": "attune"})
    assert parsed.material_ids == ["mi-flaming", "mi-keen"]
    assert parsed.enhancement == 3 and parsed.item == "longsword"
    assert parsed.stock_used == {"potion-a": 1}
    # A body meant for the other mode must not blow this one up.
    assert mi.chain_from_body({"materials": ["fire-mote"]}).enhancement == 0
    assert mi.chain_from_body({}).material_ids == []


def test_the_result_carries_everything_the_spine_reads():
    result = mi.preview(3, chain(plus=1), item=MW_SWORD)
    d = result.as_dict()
    for key in ("name", "tier", "rank", "stages", "dc", "risky", "problems",
                "effects", "specs", "consumes", "output", "bonus", "terms", "chance"):
        assert key in d, f"as_dict is missing {key}"
    assert all(isinstance(line, str) for line in d["effects"])
    assert all(isinstance(spec, dict) for spec in d["specs"])


def test_the_output_is_an_inventory_item():
    """What the player receives: masterwork, with its slot, its enhancement and its
    properties, so the sheet can show what it is without re-deriving any of it."""
    sword = mi.preview(5, chain(["mi-flaming"], plus=2),
                       stock={"p": potion("flame-blade")}, item=MW_SWORD).output
    assert sword["kind"] == "crafted" and sword["craft"] == "enchanter"
    assert sword["masterwork"] is True and sword["weapon"] == "longsword"
    assert sword["enhancement"] == 2 and sword["properties"] == ["Flaming"]
    assert sword["slot"] is None and sword["usable"]

    ring = mi.preview(5, chain(["mi-ring-protection-2"], item="ring"),
                      item={"kind": "jewelry"}).output
    assert ring["slot"] == "ring" and ring["wearable"]
    assert all(not effectspec.validate(s) for s in ring["specs"])


def test_check_terms_match_the_other_mode():
    """Same enchanter, same head, same three terms — so a player switching tabs does
    not find their bonus quietly changing."""
    from rules import enchanter as en

    class Stub:
        level = 8

        def ability_mod(self, which):
            return 2 if which == "int" else 0

    assert mi.check_terms(Stub(), 3) == en.check_terms(Stub(), 3)
    assert mi.check_bonus(Stub(), 3) == 9


def test_glyphs_are_distinct_and_not_herbalisms():
    glyphs = mi.KIND_GLYPH
    kinds = {i.kind for i in mi.catalogue().values()}
    assert kinds <= set(glyphs)
    assert len(set(glyphs.values())) == len(glyphs)
    assert not (set(glyphs.values()) & {"🌿", "🍄", "🦴", "☠️"})


def test_homebrew_layers_over_shipped(tmp_path, monkeypatch):
    """A homebrew property just works, and a partial override of a shipped one merges
    rather than replacing — the `worldclass.tracks()` rule, whose failure (a stale user
    copy shadowing a corrected shipped entry) is invisible until it is not."""
    from django.conf import settings

    hb = tmp_path / "homebrew" / "magic-items"
    hb.mkdir(parents=True)
    (hb / "mi-singing.json").write_text(json.dumps({
        "id": "mi-singing", "name": "Singing", "kind": "weapon_property",
        "tier": "rare", "plus": 1, "spell": "haste", "caster_level": 9,
        "effects": [{"type": "narrative", "target": "The blade hums in battle"}],
    }), encoding="utf-8")
    (hb / "mi-flaming.json").write_text(json.dumps({
        "id": "mi-flaming", "name": "Balefire"}), encoding="utf-8")

    monkeypatch.setattr(settings, "CAMPAIGN_DIR", str(tmp_path / "campaigns"))
    monkeypatch.setattr(mi, "_CATALOGUE", None)

    loaded = mi.catalogue()
    assert loaded["mi-singing"].plus == 1
    assert loaded["mi-flaming"].name == "Balefire"
    assert loaded["mi-flaming"].effects, "the override replaced instead of merging"

    result = mi.preview(5, chain(["mi-singing"], plus=1),
                        stock={"p": potion("haste")}, item=MW_SWORD)
    assert result.problems == []
    assert result.total_bonus == 2 and result.price_gp == 8000

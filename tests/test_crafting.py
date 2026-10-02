"""The ingredient shelf, the card arithmetic, and the old chain reader behind them.

Herbalism's live bench is the step model (rules/crafting.py "THE STEP BENCH", driven
through its API in tests/test_bench_api.py). What stays here is what the step bench is
built on and still reads: the corpus, the benefit/harm sort, the check's terms, Stock and
the sheet's use of it, and the retired chain reader `crafting.preview`, kept as a library.

Tests that pinned rules the owner retired on 2026-10-02 (distill, purify, refine,
preserve, the x2 concentrate, tincture infusions, the old bench's per-dose batch rolls and
its natural 20 and 1) were deleted with the rules; the defects they recorded that still
apply are re-pinned against the step bench in tests/test_bench_api.py.
"""
from __future__ import annotations

import json
import re

import pytest
from django.test import Client, override_settings

from play import craft_views
from rules import crafting, herbprep, ingredients
from rules.crafting import Chain
from rules.sheet import load_pc


@pytest.fixture
def shelf():
    return ingredients.all_ingredients()


# Fixture herbs, added 2026-10-02 when the relevance pass rewrote the corpus and four
# tests here that pinned Woundwort, Comfrey and Dragon Flower failed with every rule still
# working. Each is the real herb's specs as they were, under its own name, so the chain
# reader and the benefit/harm sort are pinned to data no later edit can move.
TESTWORT = {  # Woundwort as it was: a narrated bleed reduction and a heal
    "id": "testwort", "name": "Testwort", "kind": "herb", "tier": "common",
    "text": "A styptic for deep cuts.",
    "effects": [{"type": "narrative", "target": "Bleeding damage 20% less", "route": "wound"},
                {"type": "heal", "dice": "1d4",
                 "note": "applied within two rounds; stops bleeding", "route": "wound"}]}
TESTFREY = {  # Comfrey as it was: one heal, in the corpus's own range form
    "id": "testfrey", "name": "Testfrey", "kind": "herb", "tier": "common",
    "text": "Wonder weed.",
    "effects": [{"type": "heal", "dice": "1-4", "route": "wound"}]}
# Dragon Flower as it was: a penalty, a narrated bonus, and a gated poison of two bodies.
OLD_FLOWER_SPECS = [
    {"type": "situational_mod", "amount": -2, "target": "actions while in the area",
     "bonus_type": "untyped", "duration": {"amount": "1d4", "unit": "week"},
     "route": "external"},
    {"type": "situational_mod", "amount": 5, "target": "save vs poison for 10 rounds",
     "bonus_type": "untyped", "route": "ingest"},
    {"type": "ability_damage", "target": "con", "dice": "1d6", "route": "ingest"},
    {"type": "save_gate", "target": "fort", "dc": 25, "route": "ingest"},
    {"type": "apply_condition", "target": "nauseated", "route": "inhale"},
]
TESTFLOWER = {"id": "testflower", "name": "Testflower", "kind": "herb", "tier": "common",
              "text": "A flower with a stench.", "effects": OLD_FLOWER_SPECS}


@pytest.fixture
def fixture_herbs(monkeypatch):
    """The fixture herbs on the shelf beside the corpus, for one test."""
    shelf = dict(ingredients.all_ingredients())
    for raw in (TESTWORT, TESTFREY, TESTFLOWER):
        shelf[raw["id"]] = ingredients.from_dict(
            {**raw, "effects": [dict(s) for s in raw["effects"]]})
    monkeypatch.setattr(ingredients, "_ALL", shelf)
    return shelf


# --- the shelf ----------------------------------------------------------------------------

def test_the_document_loaded(shelf):
    """160 entries out of the herbs document, read from its own bold runs rather than
    guessed from punctuation — the entries use " ", ": ", "- " and "-" as separators and
    the first twenty use nothing at all."""
    assert len(shelf) > 150
    assert "woundwort" in shelf and "phoenix-feather" in shelf


def test_monster_parts_carry_their_harvesting(shelf):
    hydra = shelf["hydra-gall"]
    assert hydra.kind == "monster part"
    assert "silver scalpel" in hydra.harvesting
    assert hydra.risky


def test_tier_is_marked_inferred(shelf):
    """The document never states a tier. It states a crafting DC on 31 entries, which is
    the only quantity in it that tracks difficulty, so tier is derived from that and
    flagged — a guessed number that looks authored is worse than no number."""
    assert shelf["tahtoalehti"].tier == "legendary"
    assert shelf["tahtoalehti"].tier_inferred
    assert all(i.tier_inferred for i in shelf.values())


def test_world_flora_is_marked_rather_than_assumed_present(shelf):
    """Whether Nura Stalk grows in this world is a World Bible question. Until the export
    carries flora, they load and say so instead of being silently assumed."""
    assert shelf["nura-stalk"].world_gated
    assert not shelf["woundwort"].world_gated


def test_a_crafter_sees_only_their_own_tier_and_below(shelf):
    low = ingredients.usable_at(1)
    assert any(i.id == "woundwort" for i in low)
    assert not any(i.id == "phoenix-feather" for i in low)


# --- chains -------------------------------------------------------------------------------

def test_a_simple_chain_previews(fixture_herbs):
    """Re-pinned 2026-10-02 because the herb data changed: Woundwort's bleed reduction
    became a typed Heal bonus that potency scales, and Comfrey gained two more heals.
    Testwort and Testfrey, fixtures of the two herbs as they were, keep the chain's card
    pinned line for line."""
    r = crafting.preview("herbalist", 1,
                         Chain("herbalist", ["grind", "brew"], ["testwort", "testfrey"]))
    assert not r.problems
    assert r.stages == 2 and r.tier == "common"
    # The mechanic, not the paragraph: Woundwort's bleed reduction and now its authored
    # heal — "way too many useless herbs" gave every benefit-less herb a runnable one —
    # and Comfrey's healing.
    assert r.effects == ["Testwort: Bleeding damage 20% less",
                         "Testwort: Heals 1d4 hit points",
                         "Testfrey: Heals 1-4 hit points"]
    assert len(r.described) == 2


# --- benefit, harm, and the line between them ------------------------------------------------

def test_harm_is_a_drawback_rather_than_an_effect(fixture_herbs):
    """From the bench, before: Dragon Flower's Effects panel listed "-2 actions while in
    the area", "+5 save vs poison", "1d6 Constitution damage", "Fortitude DC 25" and
    "Causes nauseated" as five undifferentiated bullets, and Drawbacks said one boilerplate
    sentence that named nothing. 99 of the corpus's 178 effects were filed that way.

    Re-pinned 2026-10-02 because the herb data changed: the real flower's bonuses are
    typed and potency-scaled now and its nausea states its rounds. Testflower, a fixture
    of its old five specs, keeps the sort pinned line for line."""
    r = crafting.preview("herbalist", 3,
                         Chain("herbalist", ["grind"], ["testflower"]))
    assert r.effects == ["Testflower: +5 save vs poison for 10 rounds"]
    assert r.drawbacks == [
        "Testflower: Fortitude DC 25 or 1d6 Constitution damage, causes nauseated",
        "Testflower: -2 actions while in the area for 1d4 weeks",
    ]


def test_the_save_reads_as_the_gate_for_the_harm_it_governs(fixture_herbs):
    """"Fortitude DC 25" was its own bullet, so nothing on the card said which of the four
    other lines it applied to. Grouped by the ingredient the effects were read out of,
    which is the only thing that ties them together.

    Re-pinned 2026-10-02 because the herb data changed: the real flower's nausea now
    states its rounds. Testflower, a fixture of its old specs, keeps the lines exact."""
    r = crafting.preview("herbalist", 3,
                         Chain("herbalist", ["grind"], ["testflower"]))
    assert len(r.poisons) == 1
    assert r.poisons[0]["source"] == "Testflower"
    assert r.poisons[0]["save_line"] == "Fortitude DC 25"
    assert r.poisons[0]["lines"] == ["1d6 Constitution damage", "Causes nauseated"]


def test_two_poisonous_ingredients_stay_two_poisons():
    """A pot holding Dragon Flower and Skull Orchid is two poisons with two different
    saves, not one heap of damage under whichever DC came first."""
    r = crafting.preview("herbalist", 3,
                         Chain("herbalist", ["grind"], ["dragon-flower", "skull-orchid"]))
    assert [(p["source"], p["save_line"]) for p in r.poisons] == \
        [("Dragon Flower", "Fortitude DC 25"), ("Skull Orchid", "DC 17")]


def test_an_ingredient_that_is_only_dangerous_to_handle_is_named():
    """30 of the corpus's ingredients are marked risky and extract no harmful mechanic at
    all, because the danger is in the harvesting. The warning stays — but it says which
    ingredient it is about, instead of the one sentence that used to be the whole panel
    however many poisons were in the pot."""
    r = crafting.preview("herbalist", 3,
                         Chain("herbalist", ["grind"], ["basilisk-eye"]))
    assert any("Untreated hazardous components: Basilisk Eye." in d for d in r.drawbacks)


def test_a_crafting_dc_restated_in_the_prose_does_not_become_a_poison():
    """41 of the corpus's 59 save gates gate nothing: they are the entry's own crafting DC,
    written at the end of its description ("Cave Star ... DC: 10.") and picked up by the
    extractor's bare-DC fallback. Filing every gate under Drawbacks would have put 41
    poisons on the shelf that poison nobody."""
    r = crafting.preview("herbalist", 3, Chain("herbalist", ["grind"], ["cave-star"]))
    assert r.poisons == []
    assert r.drawbacks == []


def test_a_card_line_and_its_mechanic_come_from_one_walk(shelf):
    """`lines` and `specs` were two separate walks over the same effects with nothing
    tying entry n of one to entry n of the other. Harmless while every line was printed
    the same way; not harmless once the spec's type decides which panel its line lands in.
    All 161 entries line up, and this is what keeps them lined up."""
    for ing in shelf.values():
        assert [line for line, _ in ing.pairs] == ing.lines
        assert [spec for _, spec in ing.pairs if spec] == ing.specs


def test_a_method_you_have_not_learned_is_named_with_the_level_that_grants_it():
    """Re-pinned 2026-10-02 on Neutralize: the test used Distill, which the owner retired.
    The defect is the same: a locked method must say which level opens it."""
    r = crafting.preview("herbalist", 1,
                         Chain("herbalist", ["neutralize"], ["woundwort"]))
    assert any(re.search(r"Neutralize is learned at Herbalist \d", p) for p in r.problems)


def test_material_above_your_tier_is_refused_by_name():
    r = crafting.preview("herbalist", 1,
                         Chain("herbalist", ["grind"], ["phoenix-feather"]))
    assert any("Phoenix Feather" in p and "legendary" in p for p in r.problems)


def test_the_result_is_as_rare_as_its_rarest_component():
    """A common chain with one legendary petal in it is a legendary brew, which is also
    what gates who can make it."""
    r = crafting.preview("herbalist", 5,
                         Chain("herbalist", ["grind"], ["woundwort", "phoenix-feather"]))
    assert r.tier == "legendary"


def test_a_finishing_method_has_to_come_last():
    """You brew the mixture; you do not grind the tea."""
    r = crafting.preview("herbalist", 1,
                         Chain("herbalist", ["brew", "grind"], ["woundwort"]))
    assert any("finishes a chain" in p for p in r.problems)


def test_an_empty_pot_says_so_rather_than_erroring():
    """Preview never raises for a chain that is merely bad — the page has to be able to
    grey the button and say why."""
    r = crafting.preview("herbalist", 1, Chain("herbalist", ["grind"], []))
    assert "Nothing in the pot." in r.problems
    assert r.chance == 0


def test_an_authored_dc_beats_a_derived_one():
    """31 ingredients carry their own crafting DC. An authored number beats a tier
    lookup every time."""
    r = crafting.preview("herbalist", 5, Chain("herbalist", ["grind"], ["cotsbalm"]))
    assert ingredients.get("cotsbalm").craft_dc == 35
    assert r.dc == 35


def test_no_craft_is_ever_certain():
    """Clamped to 5-95 rather than allowed to reach 100: a natural 1 fails, so the number
    on the button must never claim otherwise."""
    r = crafting.preview("herbalist", 5, Chain("herbalist", ["grind"], ["barley"]))
    assert 5 <= r.chance <= 95


# --- through the page ---------------------------------------------------------------------

@pytest.fixture
def client(tmp_path):
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        yield Client()
        cm._LIVE.clear()


def test_the_bench_opens(client):
    assert client.get("/craft/").status_code == 200


def test_the_shelf_shows_what_is_out_of_reach_rather_than_hiding_it(client):
    """A shelf that silently hides the interesting half gives a player no reason to
    level. One showing a Phoenix Feather greyed out gives them a goal."""
    d = client.get("/api/craft/ingredients?craft=herbalism").json()
    by_id = {i["id"]: i for i in d["ingredients"]}
    assert by_id["woundwort"]["usable"]
    assert not by_id["phoenix-feather"]["usable"]
    assert by_id["phoenix-feather"]["tier"] == "legendary"


def test_each_bench_serves_its_own_shelf(client):
    """Enchanting was once the example of a discipline with no rules at all. Now every
    discipline has a track, and the thing worth pinning is that the shelves do not
    bleed: a binding circle offers essences, never the herb corpus, because all five
    crafts read materials through one dispatcher and one shared folder."""
    d = client.get("/api/craft/ingredients?craft=enchanting").json()
    assert d["track"]["available"] is True
    ids = {m["id"] for m in d["ingredients"]}
    assert "woundwort" not in ids            # the herb shelf stays at the herb bench
    assert any(m.get("kind") == "essence" for m in d["ingredients"])

    herbs = client.get("/api/craft/ingredients?craft=herbalism").json()
    assert "woundwort" in {m["id"] for m in herbs["ingredients"]}


def test_the_shelf_marks_a_jar_that_will_poison_whoever_drinks_it(client):
    """A made poison and a made tea were the same green flask on the Made shelf, and the
    only way to find out which was which was to drink one.

    Re-pinned 2026-10-02 because the herb data changed: the real flower's nausea now
    states its rounds, which lengthened the body line. The jar is filled with the
    fixture of the flower's old specs, so the shelf's marking is what is pinned."""
    from play import campaign as cm

    c = cm.current()
    c.scene.pc().add_stock(crafting.Stock(
        base="Dragon Flower Tincture", craft="herbalist",
        specs=[dict(s) for s in OLD_FLOWER_SPECS]), count=1)
    c.save()

    d = client.get("/api/craft/ingredients?craft=herbalism").json()
    jar = next(s for s in d["stock"] if s["base"] == "Dragon Flower Tincture")
    assert jar["poisons"][0]["body"] == \
        "Fortitude DC 25 or 1d6 Constitution damage, causes nauseated"


# --- crafted output as an ingredient -------------------------------------------------------

def _tea(concentration=1, tier="common", potency=1.0, count=1):
    return crafting.Stock(base="Woundwort Tea", concentration=concentration, tier=tier,
                          potency=potency, count=count, craft="herbalist",
                          effects=["stops bleeding"])


def test_a_crafted_input_brings_its_potency_into_a_new_compound():
    """A compound made from a doubled tea is stronger than one made from a plain one."""
    stock = {"woundwort-tea#2": _tea(concentration=2, tier="uncommon", potency=2.0)}
    r = crafting.preview("herbalist", 3,
                         Chain("herbalist", ["mix"], ["comfrey"],
                               stock_used={"woundwort-tea#2": 1}),
                         stock=stock)
    assert not r.problems
    assert r.potency == pytest.approx(0.80 * 2.0)
    assert r.tier == "uncommon"          # as rare as its rarest component


def test_stock_survives_a_save():
    from rules.sheet import from_dict, load_pc, to_dict

    pc = load_pc("fixtures/pc-kesst.json")
    pc.add_stock(_tea(concentration=2, tier="uncommon", potency=2.0), count=3)
    back = from_dict(to_dict(pc))
    got = back.stock["woundwort-tea#2"]
    assert got.count == 3 and got.potency == 2.0
    assert got.name == "Woundwort Tea (Tier 2)"


def test_an_emptied_jar_leaves_the_shelf():
    """A count of zero left behind is a jar the page offers and the next preview refuses."""
    from rules.sheet import load_pc

    pc = load_pc("fixtures/pc-kesst.json")
    pc.add_stock(_tea(), count=2)
    assert pc.take_stock("woundwort-tea#1", 2) == 2
    assert "woundwort-tea#1" not in pc.stock


# --- the shelf says which jars the chain will take -----------------------------------
#
# The preparation rules were enforced correctly and said nothing until a chain was built
# and Craft was pressed, which reads exactly like the rules not working at all. Reported
# from play: "I don't think the restrictions on material processing are holding up."
# They were: on the reporter's own corpus, choosing `brew` refuses 24 of 162 ingredients
# and greyed none of them.
#
# The flags are asserted against herbs the test makes up, never against the corpus. The
# tags live in the homebrew overlay in the player's data directory, so "Chimera Horn
# cannot be brewed raw" is a fact about whoever ran the suite — green on this machine and
# red on a fresh clone, which is the worst kind of green.

def _herb(source_id, **flags):
    """A real ingredient with exactly the preparation flags this test names.

    Built by replacing fields on a corpus entry rather than by faking one: `preview` and
    the view walk the full `Ingredient` interface — `craft_dc`, `as_dict`, `pairs` — and
    a stub grew three more attributes every time it was run against another code path.
    """
    import dataclasses

    return dataclasses.replace(ingredients.all_ingredients()[source_id], **flags)


def test_choosing_brew_marks_what_has_to_be_ground_first():
    """The exact case the report names, at the point the page asks the question: a method
    picked, nothing in the pot yet."""
    horn = _herb("chimera-horn", brew_raw=False)
    assert "ground" in crafting.prep_problem(horn, ["brew"])


def test_adding_the_grind_clears_the_mark():
    """A refusal has to be a statement about the chain, not about the ingredient. If
    grinding first did not clear it, the mark would be telling the player to give up on a
    herb that is perfectly usable."""
    horn = _herb("chimera-horn", brew_raw=False)
    assert crafting.prep_problem(horn, ["grind", "brew"]) == ""


def test_a_step_an_ingredient_has_no_use_for_is_not_a_refusal():
    """Neutralising a pot of eight herbs when one is volatile is the whole point; the
    other seven must not come back marked for having sat through it."""
    plain = _herb("woundwort", volatile=False)
    assert crafting.prep_problem(plain, ["neutralize", "brew"]) == ""


def test_a_volatile_herb_is_marked_until_it_is_neutralised():
    volatile = _herb("dragon-flower", volatile=True, needs_extraction=False)
    assert "volatile" in crafting.prep_problem(volatile, ["grind"])
    assert crafting.prep_problem(volatile, ["neutralize", "grind"]) == ""


def test_the_reason_carries_no_name_prefix():
    """It is drawn on the jar, which is already wearing the name. `_preparation_problems`
    adds the name back for the problems panel, where eight herbs are listed together."""
    horn = _herb("chimera-horn", brew_raw=False)
    assert not crafting.prep_problem(horn, ["brew"]).startswith(horn.name)


# --- the craft is a check, rolled where you can see it ---------------------------------
#
# "instead of a percentage chance and a blind roll just roll a d100 on screen or even
# better convert it all to a skill DC and have it be a herbalist check (d20 + Herbalist
# lvl + 1/2 Character Lvl + WIS Mod)."
#
# The DC was already computed from the chain and then thrown away: `_chance` turned it
# into a percentage using `3 * level + 2 * (level - rank)` — a bonus invented here with no
# counterpart anywhere in 1e — and the roll was a d20 against `21 - chance/5`, made on the
# server and reported as a verdict. Every term now comes from the character sheet.

def _crafter(level=8, wis=16, ranks=None):
    pc = load_pc("fixtures/pc-kesst.json")
    pc.level = level
    pc.abilities["wis"] = wis
    return pc


def test_the_bonus_is_the_authors_formula():
    """Track level, half character level rounded down, Wisdom. Nothing else."""
    pc = _crafter(level=8, wis=16)                     # half of 8 is 4, Wis 16 is +3
    assert crafting.check_bonus(pc, 4) == 4 + 4 + 3


def test_half_character_level_rounds_down():
    """As every half-level term in 1e rounds. A 7th-level crafter adds 3, not 3.5."""
    assert crafting.check_bonus(_crafter(level=7, wis=10), 0) == 3


def test_a_negative_wisdom_modifier_counts_against_you():
    """It is a modifier, not a bonus. Wisdom 8 is -1 and the check is worse for it."""
    assert crafting.check_bonus(_crafter(level=2, wis=8), 3) == 3 + 1 - 1


def test_the_terms_are_itemised_not_just_summed():
    """"+9" says nothing; "Herbalist 4, half level +4, Wis +3" says which of the three to
    go and improve. The bench draws these rows under the die."""
    labels = [t["label"] for t in crafting.check_terms(_crafter(), 4)]
    assert any("Herbalist 4" in x for x in labels)
    assert any("half character level" in x for x in labels)
    assert any("Wisdom" in x for x in labels)


def test_the_preview_carries_the_check_to_the_bench():
    """The page draws `d20+11 vs DC 20` on the button from these, so they have to survive
    the trip rather than only the percentage they imply."""
    r = crafting.preview("herbalist", 4,
                         Chain(track="herbalist", methods=["brew"],
                               ingredient_ids=["woundwort"]),
                         satchel={"woundwort": 5}, carrier=_crafter())
    assert r.bonus == 11 and r.dc > 0
    assert r.as_dict()["bonus"] == 11 and r.as_dict()["terms"]


def test_the_chance_is_derived_from_the_check_rather_than_being_the_mechanic():
    """It is a label now. d20+11 against DC 20 needs a 9: twelve faces of twenty, 60%."""
    assert crafting._chance(20, 11) == 60


# --- what you made is in your inventory, and you can use it ----------------------------
#
# "my crafted tinctures don't appear in my inventory I want to be able to use my
# consumables." Reported against a live save holding thirty crafted jars: the Inventory tab
# listed three things — "offer", "scene on" and a traveller's outfit — because `carrying`
# was `actor.goods`, and jars live in `actor.stock`. The most usable thing the character
# owned was the one thing the sheet did not show, and there was no route to use it: the
# `use_item` op existed and had no door from the sheet.

def _made(pc, base="Woundwort Tea", count=2, heal=True):
    item = crafting.Stock(
        base=base, tier="common", count=count, potency=1.0, craft="herbalist",
        effects=["Heals 1d8 hit points"] if heal else ["Deals 1d6 damage"],
        specs=[{"type": "heal", "dice": "1d8"}] if heal
        else [{"type": "damage", "dice": "1d6", "target": "enemy"}])
    pc.add_stock(item, count)
    return item


def test_a_crafted_jar_reaches_the_character_sheet(client):
    """It was on the crafting bench and nowhere else."""
    from play import campaign as cm
    from rules.sheet import full_sheet

    item = _made(cm.current().scene.pc())
    names = [j["name"] for j in full_sheet(cm.current().scene.pc())["defense"]["stock"]]
    assert item.name in names


def test_the_sheet_says_which_ways_a_jar_can_be_used(client):
    """Asked of `rules.consumables` rather than guessed from the name, so the button on
    the sheet and the refusal from the engine cannot disagree."""
    from play import campaign as cm
    from rules.sheet import full_sheet

    _made(cm.current().scene.pc(), base="Kind Tea", heal=True)
    row = next(j for j in full_sheet(cm.current().scene.pc())["defense"]["stock"]
               if j["name"] == "Kind Tea")
    assert row["drinkable"]
    # Nothing harmful in it, so there is nothing to throw at anybody and the sheet must
    # not offer a button the engine would refuse.
    assert not row["throwable"]


def test_the_satchel_is_on_the_sheet_too(client):
    """Raw material is carried and does spoil, so it belongs on the Inventory tab even
    though it is not usable."""
    from play import campaign as cm
    from rules.sheet import full_sheet

    cm.current().scene.pc().inventory["woundwort"] = 4
    satchel = full_sheet(cm.current().scene.pc())["defense"]["satchel"]
    assert {"id": "woundwort", "name": "Woundwort", "count": 4} in satchel


def test_drinking_a_jar_spends_the_dose(client):
    """The route the sheet's button uses. Straight to the engine, no GM turn."""
    from play import campaign as cm

    item = _made(cm.current().scene.pc(), count=2)
    r = client.post("/api/use", data=json.dumps({"item": item.id, "how": "drink"}),
                    content_type="application/json")
    assert r.status_code == 200, r.json()
    assert cm.current().scene.pc().stock[item.id].count == 1


def test_the_last_dose_leaves_the_shelf(client):
    from play import campaign as cm

    item = _made(cm.current().scene.pc(), count=1)
    client.post("/api/use", data=json.dumps({"item": item.id, "how": "drink"}),
                content_type="application/json")
    assert item.id not in cm.current().scene.pc().stock


def test_using_something_you_do_not_have_is_refused_with_what_you_do(client):
    r = client.post("/api/use", data=json.dumps({"item": "nonesuch#1", "how": "drink"}),
                    content_type="application/json")
    assert r.status_code == 400
    assert "not carrying" in r.json()["error"]


def test_throwing_something_harmless_is_refused(client):
    """The engine's own rule, reached through the same door: a tea that only heals has
    nothing to throw at anybody."""
    from play import campaign as cm

    item = _made(cm.current().scene.pc(), heal=True)
    r = client.post("/api/use", data=json.dumps({"item": item.id, "how": "throw"}),
                    content_type="application/json")
    assert r.status_code == 400


def test_using_a_jar_hands_back_the_fresh_sheet(client):
    """So the tab redraws with the dose gone rather than showing the count it had before
    the drink — the same trap as any page that acts and does not re-read."""
    from play import campaign as cm

    item = _made(cm.current().scene.pc(), count=3)
    d = client.post("/api/use", data=json.dumps({"item": item.id, "how": "drink"}),
                    content_type="application/json").json()
    row = next(j for j in d["sheet"]["defense"]["stock"] if j["id"] == item.id)
    assert row["count"] == 2


# --- the step bench's arithmetic -----------------------------------------------------------
#
# The rules the API tests drive end to end (tests/test_bench_api.py), pinned here where a
# failure names the function rather than an endpoint.

def test_benefits_round_up_and_harm_rounds_down():
    """The module's own rounding rule, now applied to harm as well as help: a Fine
    remedy's heal rounds in the drinker's favour, and so does its poison. 1d6 harm at
    x0.75 is 1d6-1 (0.875 down), never 1d6 (up); 1d4 help at x1.1 is 1d4+1 (0.25 up)."""
    help_, harm = crafting.bake(
        [{"type": "heal", "dice": "1d4"},
         {"type": "damage", "dice": "1d6", "duration": {"amount": 1, "unit": "round"}}],
        1.1, 1.0, 0.75)
    assert help_["dice"] == "1d4+1"
    assert harm["dice"] == "1d6-1"
    # Never shortened to 0: a duration of 0 reads as no duration at all.
    assert harm["duration"]["amount"] == 1


def test_a_flat_bonus_and_its_duration_scale_with_the_strength():
    """"Stronger and longer" (plan §2): +2 for 1 hour at x1.5 is +3 for 2 hours, rounded
    up as benefits are, and a string amount from the corpus scales the same as a number."""
    got, = crafting.bake([{"type": "save_mod", "amount": "2",
                           "duration": {"amount": "1", "unit": "hour"}}], 1.5, 1.5, 1.0)
    assert got["amount"] == 3 and got["duration"]["amount"] == 2


def test_the_ladder_runs_on_past_flawless():
    """Plan §2: Crude, Sound, Fine, Superior, Flawless, then Flawless +1 and on, with
    potency +0.1 a step, price +0.5 a step and the drawback held at 0.25."""
    assert [crafting.quality_name(i) for i in range(7)] == [
        "Crude", "Sound", "Fine", "Superior", "Flawless", "Flawless +1", "Flawless +2"]
    assert crafting.quality_mult("potency", 6) == pytest.approx(1.7)
    assert crafting.quality_mult("price", 5) == pytest.approx(3.5)
    assert crafting.quality_mult("drawback", 9) == pytest.approx(0.25)


@pytest.mark.parametrize("score,ceiling,tier", [
    (0.0, 2, 0), (0.33, 2, 0), (0.34, 2, 1), (0.71, 3, 2), (1.0, 2, 2), (1.0, 4, 4),
    (5, 2, 2), (-1, 4, 0), ("x", 4, 0), (None, 4, 0), (float("nan"), 4, 0),
    (float("inf"), 3, 3)])
def test_the_score_is_spread_evenly_under_the_ceiling_and_clamped(score, ceiling, tier):
    """Plan §4.3: a perfect run lands exactly on the ceiling and the bands below share
    the range. The page's number is never trusted past that: anything outside 0..1, or
    not a number, is clamped before it is read."""
    assert crafting.tier_from_score(score, ceiling)[0] == tier


def test_the_failure_rule_ruins_exactly_half_rounded_up():
    """Miss by 5 or more: half the stack, rounded up, shared across its materials by
    their share. 7 and 2 is 9 units, so 5 ruined: never 4 (half rounded down) and never
    4 + 1 + 1 (each share rounded up on its own)."""
    a = crafting.Material(key="ing:a", name="A", ingredient_id="a", kind="herb",
                          part="leaf", tier="common", count=7)
    b = crafting.Material(key="ing:b", name="B", ingredient_id="b", kind="reagent",
                          part="oil", tier="common", count=2)
    plan = crafting.StepPlan(method="steep", consumes=[(a, 7), (b, 2)])
    assert crafting.failure_losses(plan, 4) == []
    lost = dict((m.key, n) for m, n in crafting.failure_losses(plan, 5))
    assert sum(lost.values()) == 5
    assert lost["ing:a"] <= 7 and lost.get("ing:b", 0) <= 2


def test_the_check_has_no_natural_twenty():
    """CRB p.180: a skill check has no automatic success. Beyond 20 the bench says how
    far, instead of offering a 5% roll that the old bench honoured on a 20."""
    assert crafting.check_odds(32, 10) == (None, "needs +2 more to the check")
    assert crafting.check_odds(30, 10) == (20, "")
    assert crafting.check_odds(5, 10) == (1, "")


def test_an_old_jar_saves_back_exactly_as_it_was():
    """Every new Stock field is written only when set: a pre-revamp jar's dict comes back
    with no new key at all, so an old save is not rewritten into a different file the
    first time it saves. The retired method is detected on read and not written."""
    old = {"base": "Woundwort Purified Draught", "concentration": 1, "tier": "common",
           "potency": 1.25, "count": 2, "craft": "herbalist", "specs": []}
    jar = crafting.from_stock_dict(old)
    assert jar.old_method == "purify" and jar.id == "woundwort-purified-draught#1"
    d = jar.as_dict()
    for key in ("form", "state", "quality", "ready_minute", "spoils_minute",
                "old_method", "base_specs", "mults", "worked"):
        assert key not in d, key


def test_a_forge_blades_quality_word_is_not_a_quality_index():
    """Measured while building the step bench: the forge's output says
    `"quality": "plain"`, and reading every `quality` as a ladder index turned every forge
    craft into a 500. The step fields are herbalism's alone."""
    blade = crafting.from_stock_dict({"base": "Longsword", "craft": "blacksmith",
                                      "quality": "plain", "form": "blade"})
    assert blade.quality is None and blade.form is None and not blade.stepped
    assert blade.id == "longsword#1"

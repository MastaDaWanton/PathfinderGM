"""Crafting chains, and the ingredient shelf behind them.

A craft is an ordered list of methods applied to a set of ingredients, per the Herbalist
document's own framing: "crafting is no longer limited to single-step recipes. Complex
items require Crafting Chains—combining multiple methods across different tools."

The workbench is assumed to fold out wherever the character is standing, per the design
call, so nothing here gates on location.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from rules import crafting, ingredients
from rules.crafting import Chain
from rules.sheet import load_pc


@pytest.fixture
def shelf():
    return ingredients.all_ingredients()


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

def test_a_simple_chain_previews(shelf):
    r = crafting.preview("herbalist", 1,
                         Chain("herbalist", ["grind", "brew"], ["woundwort", "comfrey"]))
    assert not r.problems
    assert r.stages == 2 and r.tier == "common"
    # The mechanic, not the paragraph: Woundwort's bleed reduction and Comfrey's healing.
    assert r.effects == ["Woundwort: Bleeding damage 20% less",
                         "Comfrey: Heals 1-4 hit points"]
    assert len(r.described) == 2


def test_mix_costs_potency_and_distil_returns_it():
    """The author's percentages: mix keeps 80%, distil adds 25%, refine reaches 125%."""
    mixed = crafting.preview("herbalist", 3,
                             Chain("herbalist", ["mix"], ["woundwort"]))
    assert mixed.potency == pytest.approx(0.80)

    both = crafting.preview("herbalist", 3,
                            Chain("herbalist", ["mix", "distill"], ["woundwort"]))
    assert both.potency == pytest.approx(1.00)


def test_purifying_removes_the_drawback():
    """"Passing a dangerous ingredient through Purify or Neutralize completely removes
    its negative side effects.\""""
    raw = crafting.preview("herbalist", 3,
                           Chain("herbalist", ["grind"], ["nightshade"]))
    assert raw.risky and raw.drawbacks

    clean = crafting.preview("herbalist", 3,
                             Chain("herbalist", ["grind", "purify"], ["nightshade"]))
    assert not clean.risky and not clean.drawbacks


# --- benefit, harm, and the line between them ------------------------------------------------

def test_harm_is_a_drawback_rather_than_an_effect():
    """From the bench, before: Dragon Flower's Effects panel listed "-2 actions while in
    the area", "+5 save vs poison", "1d6 Constitution damage", "Fortitude DC 25" and
    "Causes nauseated" as five undifferentiated bullets, and Drawbacks said one boilerplate
    sentence that named nothing. 99 of the corpus's 178 effects were filed that way."""
    r = crafting.preview("herbalist", 3,
                         Chain("herbalist", ["grind"], ["dragon-flower"]))
    assert r.effects == ["Dragon Flower: +5 save vs poison for 10 rounds"]
    assert r.drawbacks == [
        "Dragon Flower: Fortitude DC 25 or 1d6 Constitution damage, causes nauseated",
        "Dragon Flower: -2 actions while in the area for 1d4 weeks",
    ]


def test_the_save_reads_as_the_gate_for_the_harm_it_governs():
    """"Fortitude DC 25" was its own bullet, so nothing on the card said which of the four
    other lines it applied to. Grouped by the ingredient the effects were read out of,
    which is the only thing that ties them together."""
    r = crafting.preview("herbalist", 3,
                         Chain("herbalist", ["grind"], ["dragon-flower"]))
    assert len(r.poisons) == 1
    assert r.poisons[0]["source"] == "Dragon Flower"
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


def test_purify_says_which_poison_it_took_out():
    """It used to append "Side effects and secondary toxicities removed by the chain." — a
    sentence that named nothing, whether the chain had cleansed one poison or three."""
    r = crafting.preview("herbalist", 3,
                         Chain("herbalist", ["grind", "purify"],
                               ["dragon-flower", "mad-cap"]))
    assert r.removed[:2] == [
        "Purify removed Dragon Flower's poison: Fortitude DC 25 or 1d6 Constitution "
        "damage, causes nauseated.",
        "Purify removed Mad Cap's poison: DC 18 or causes exhausted, causes unconscious, "
        "causes confused.",
    ]


def test_purify_takes_the_poison_out_of_the_item_and_not_only_off_the_card():
    """Measured: purifying set a `cleansed` flag and appended a sentence, and left every
    harmful spec on the Stock. A "Purified Draught of Skull Orchid" still did all three of
    its ability damages when somebody drank it, and could still be thrown at people — the
    method the author says "completely removes its negative side effects" removed nothing
    whatsoever."""
    from rules import consumables as con

    raw = crafting.preview("herbalist", 3,
                           Chain("herbalist", ["grind"], ["skull-orchid"]))
    assert con.is_harmful(crafting.from_stock_dict(raw.output))

    clean = crafting.preview("herbalist", 3,
                             Chain("herbalist", ["grind", "purify"], ["skull-orchid"]))
    made = crafting.from_stock_dict(clean.output)
    assert not con.is_harmful(made)
    assert not any(s["type"] == "ability_damage" for s in made.specs)


def test_a_purified_poison_survives_into_inventory_still_purified():
    """The removal has to be a property of the jar, not of the preview that made it —
    otherwise the card is honest and the thing in the satchel is not."""
    clean = crafting.preview("herbalist", 3,
                             Chain("herbalist", ["grind", "purify"], ["skull-orchid"]))
    back = crafting.from_stock_dict(crafting.from_stock_dict(clean.output).as_dict())
    assert not back.drawbacks
    assert any("Purify removed Skull Orchid's poison" in e for e in back.effects)


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
    r = crafting.preview("herbalist", 1,
                         Chain("herbalist", ["distill"], ["woundwort"]))
    assert any("Herbalist 3" in p for p in r.problems)


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


def test_a_longer_chain_is_harder():
    short = crafting.preview("herbalist", 3, Chain("herbalist", ["grind"], ["woundwort"]))
    long = crafting.preview("herbalist", 3,
                            Chain("herbalist", ["grind", "mix", "purify", "brew"],
                                  ["woundwort"]))
    assert long.dc > short.dc


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


def _carry(ids):
    """Put raw material in the satchel. Crafting spends what the character is carrying,
    so a bench test has to forage — or be handed the herbs — before it can brew."""
    from play import campaign as cm

    c = cm.current()
    for i in ids:
        c.scene.pc().carry(i, 1)
    c.save()


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


def test_a_discipline_with_no_rules_says_so(client):
    d = client.get("/api/craft/ingredients?craft=enchanting").json()
    assert d["track"]["available"] is False

    r = client.post("/api/craft/preview",
                    data=json.dumps({"craft": "enchanting", "ingredients": ["woundwort"]}),
                    content_type="application/json")
    assert r.status_code == 400
    assert "no rules yet" in r.json()["error"]


def test_crafting_advances_the_track(client):
    _carry(["woundwort", "comfrey"])
    r = client.post("/api/craft/do", data=json.dumps({
        "craft": "herbalism", "ingredients": ["woundwort", "comfrey"],
        "methods": ["grind", "brew"]}), content_type="application/json")
    assert r.status_code == 200
    d = r.json()
    assert d["track"]["mp"] > 0
    assert 1 <= d["roll"] <= 20


def test_a_chain_that_cannot_be_made_is_refused_before_it_is_scored(client):
    """Scoring it would let a track level itself on work the character has neither the
    tools nor the methods to attempt."""
    r = client.post("/api/craft/do", data=json.dumps({
        "craft": "herbalism", "ingredients": ["phoenix-feather"],
        "methods": ["grind"]}), content_type="application/json")
    assert r.status_code == 400

    after = client.get("/api/craft/ingredients?craft=herbalism").json()
    assert after["track"]["mp"] == 0


def test_a_recipe_can_be_kept_and_corrected(client):
    body = {"craft": "herbalism", "name": "Wound Wash",
            "ingredients": ["woundwort"], "methods": ["grind"]}
    d = client.post("/api/craft/recipes", data=json.dumps(body),
                    content_type="application/json").json()
    assert len(d["recipes"]) == 1

    body["ingredients"] = ["woundwort", "comfrey"]
    d = client.post("/api/craft/recipes", data=json.dumps(body),
                    content_type="application/json").json()
    # Saved under a name that exists replaces it. A bench where the second save silently
    # makes a duplicate is a bench nobody can correct a recipe at.
    assert len(d["recipes"]) == 1
    assert d["recipes"][0]["ingredients"] == ["woundwort", "comfrey"]


def test_the_bench_is_sent_the_poisons_grouped(client):
    """The page cannot group them itself: it receives lines, and the type that says
    whether a line is a benefit is only on the server. Sending the grouping is what lets
    the Drawbacks panel print the save in front of the harm it gates."""
    d = client.post("/api/craft/preview", data=json.dumps({
        "craft": "herbalism", "ingredients": ["dragon-flower"],
        "methods": ["grind"]}), content_type="application/json").json()
    assert d["effects"] == ["Dragon Flower: +5 save vs poison for 10 rounds"]
    assert d["poisons"][0]["save_line"] == "Fortitude DC 25"
    assert d["poisons"][0]["harm"] == "1d6 Constitution damage, causes nauseated"


def test_the_shelf_marks_a_jar_that_will_poison_whoever_drinks_it(client):
    """A made poison and a made tea were the same green flask on the Made shelf, and the
    only way to find out which was which was to drink one."""
    from play import campaign as cm

    c = cm.current()
    c.scene.pc().add_stock(crafting.Stock(
        base="Dragon Flower Tincture", craft="herbalist",
        specs=[dict(s) for s in ingredients.get("dragon-flower").specs]), count=1)
    c.save()

    d = client.get("/api/craft/ingredients?craft=herbalism").json()
    jar = next(s for s in d["stock"] if s["base"] == "Dragon Flower Tincture")
    assert jar["poisons"][0]["body"] == \
        "Fortitude DC 25 or 1d6 Constitution damage, causes nauseated"


def test_a_nameless_recipe_is_refused(client):
    r = client.post("/api/craft/recipes",
                    data=json.dumps({"ingredients": ["woundwort"]}),
                    content_type="application/json")
    assert r.status_code == 400


# --- crafted output as an ingredient -------------------------------------------------------

def _tea(concentration=1, tier="common", potency=1.0, count=1):
    return crafting.Stock(base="Woundwort Tea", concentration=concentration, tier=tier,
                          potency=potency, count=count, craft="herbalist",
                          effects=["stops bleeding"])


def test_two_doses_make_one_of_twice_the_strength():
    """The trade is quantity for density, not a gain: nothing is created, and the pair is
    spent."""
    made = crafting.concentrate(_tea())
    assert made.concentration == 2
    assert made.potency == 2.0
    assert made.count == 1
    assert made.name == "Woundwort Tea (Tier 2)"


def test_concentrating_again_compounds():
    once = crafting.concentrate(_tea())
    twice = crafting.concentrate(once)
    assert twice.name == "Woundwort Tea (Tier 3)"
    assert twice.potency == 4.0


def test_each_step_is_a_band_rarer():
    """What makes it a ladder rather than a loop: Tier 3 is rare material, and working
    rare material is Herbalist 3."""
    assert crafting.concentrate(_tea()).tier == "uncommon"
    assert crafting.concentrate(crafting.concentrate(_tea())).tier == "rare"


def test_concentration_spends_the_pair():
    stock = {"woundwort-tea#1": _tea(count=4)}
    r = crafting.preview("herbalist", 3,
                         Chain("herbalist", ["distill"], [], stock_used={"woundwort-tea#1": 2}),
                         stock=stock)
    assert r.concentrating and not r.problems
    assert r.consumes == {"woundwort-tea#1": 2}
    assert r.output["name"] == "Woundwort Tea (Tier 2)"


def test_concentrating_needs_the_still():
    """Concentrating is distilling. Requiring the method keeps the ladder behind the
    track rather than available to anyone holding two jars."""
    stock = {"woundwort-tea#1": _tea(count=2)}
    r = crafting.preview("herbalist", 3,
                         Chain("herbalist", [], [], stock_used={"woundwort-tea#1": 2}),
                         stock=stock)
    assert any("still" in p for p in r.problems)


def test_a_first_level_herbalist_cannot_concentrate():
    stock = {"woundwort-tea#1": _tea(count=2)}
    r = crafting.preview("herbalist", 1,
                         Chain("herbalist", ["distill"], [], stock_used={"woundwort-tea#1": 2}),
                         stock=stock)
    assert any("Herbalist 3" in p for p in r.problems)


def test_one_dose_is_not_a_concentration():
    """A single jar with the still in the chain is an ordinary distillation, not a step
    up the ladder."""
    stock = {"woundwort-tea#1": _tea(count=3)}
    r = crafting.preview("herbalist", 3,
                         Chain("herbalist", ["distill"], [], stock_used={"woundwort-tea#1": 1}),
                         stock=stock)
    assert not r.concentrating


def test_you_cannot_spend_what_you_do_not_have():
    stock = {"woundwort-tea#1": _tea(count=1)}
    r = crafting.preview("herbalist", 3,
                         Chain("herbalist", ["distill"], [], stock_used={"woundwort-tea#1": 2}),
                         stock=stock)
    assert any("you have 1" in p for p in r.problems)


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


# --- the ladder, through the page ----------------------------------------------------------

def test_a_craft_lands_on_the_shelf(client):
    _carry(["woundwort"])
    d = client.post("/api/craft/do", data=json.dumps({
        "craft": "herbalism", "ingredients": ["woundwort"], "methods": ["brew"],
        "name": "Woundwort Tea"}), content_type="application/json").json()
    if not d["succeeded"]:
        return                                  # the dice decide; the path is the point
    shelf = client.get("/api/craft/ingredients?craft=herbalism").json()
    assert any(s["base"] == "Woundwort Tea" for s in shelf["stock"])


def test_the_shelf_says_what_concentrating_would_make(client, tmp_path):
    from play import campaign as cm

    c = cm.current()
    c.scene.pc().add_stock(_tea(), count=2)
    c.save()

    d = client.get("/api/craft/ingredients?craft=herbalism").json()
    tea = next(s for s in d["stock"] if s["base"] == "Woundwort Tea")
    assert tea["count"] == 2
    assert tea["can_concentrate"]
    assert tea["concentrates_to"]["name"] == "Woundwort Tea (Tier 2)"


def test_a_spoiled_batch_still_spends_the_doses(client):
    """"Rare ingredients spoil" is the author's own note, and a failure that hands them
    back would make failing free."""
    from play import campaign as cm

    c = cm.current()
    pc = c.scene.pc()
    pc.track("herbalist").level = 3
    pc.add_stock(_tea(), count=2)
    c.save()

    d = client.post("/api/craft/do", data=json.dumps({
        "craft": "herbalism", "methods": ["distill"], "ingredients": [],
        "stock": {"woundwort-tea#1": 2}}), content_type="application/json").json()
    assert d["spent"] == {"woundwort-tea#1": 2}
    assert "woundwort-tea#1" not in cm.current().scene.pc().stock
    if d["succeeded"]:
        assert cm.current().scene.pc().stock["woundwort-tea#2"].count == 1


def test_one_dose_is_not_a_free_concentration():
    """Found by driving the bench: `spend` rounds down, so a single dose gave
    `(1 // 2) * 2 = 0`. The pair was never taken, the output was still made, and a lone
    jar became a rarer jar at no cost — the opposite of the two-for-one trade."""
    from rules import crafting, worldclass

    track = worldclass.tracks()["herbalist"]
    held = crafting.Stock(base="Ice Lotus", concentration=1, tier="uncommon", count=1)
    chain = crafting.Chain(track="herbalist", methods=["distill"])
    got = crafting._concentration(track, 5, chain, (held, 1), ceiling=99)
    assert any("takes 2 doses" in p for p in got.problems)


# --- infusions carry into the tincture ------------------------------------------------
#
# "Infusions should be the only way to combine tinctures with other things" — and the
# thing that comes out is the tincture, enriched. Before this, infusing a Tier 3 Mad Cap
# Tincture with woundwort produced "Woundwort Infusion" at concentration 1: the tincture's
# identity gone, and the two doses that bought the concentration silently thrown away.

def _tincture(base="Mad Cap Tincture", concentration=1, count=3):
    return crafting.Stock(
        base=base, concentration=concentration, tier="uncommon", count=count,
        potency=1.25, craft="herbalist", effects=["Heals 2d8 hit points"],
        specs=[{"type": "heal", "dice": "2d8", "from": "Mad Cap"}])


def _infuse(jar, ingredient_id, level=5):
    chain = Chain(track="herbalist", methods=["infuse"], ingredient_ids=[ingredient_id],
                  stock_used={jar.id: 1})
    return crafting.preview("herbalist", level, chain, stock={jar.id: jar},
                            satchel={ingredient_id: 5})


def test_an_infusion_keeps_the_tinctures_own_effects():
    """The base jar's `heal 2d8` has to survive the pour.

    Both sides end up on the result: the tincture's heal and the herb's line, rather than
    the herb's line alone.
    """
    result = _infuse(_tincture(), "woundwort")
    joined = " | ".join(result.effects)
    assert "Heals 2d8" in joined, result.effects
    assert "Woundwort" in joined, result.effects
    assert [s for s in result.as_dict()["output"]["specs"] if s.get("type") == "heal"]


def test_an_infusion_is_still_the_tincture_it_was_poured_into():
    """It came out named "Woundwort Infusion" — named after the herb, not the jar."""
    result = _infuse(_tincture(), "woundwort")
    assert result.as_dict()["output"]["base"].startswith("Mad Cap Tincture"), result.name


def test_an_infusion_does_not_throw_away_the_concentration():
    """A Tier 3 tincture infused came back at concentration 1.

    Four doses bought that Tier 3 (two per step); infusing a herb into it is not a reason
    to hand back one dose of the base strength.
    """
    result = _infuse(_tincture(concentration=3), "woundwort")
    assert result.as_dict()["output"]["concentration"] == 3


def test_two_differently_infused_jars_of_one_tincture_do_not_stack():
    """Stock is held per base name, so identical names merge into one count.

    A Mad Cap Tincture infused with woundwort and one infused with dragon flower are not
    interchangeable, and would have become a count of two of whichever was crafted first.
    """
    first = _infuse(_tincture(), "woundwort").as_dict()["output"]
    second = _infuse(_tincture(), "mad-cap").as_dict()["output"]
    assert first["id"] != second["id"], first["id"]


def test_infusing_twice_keeps_the_first_infusion_on_the_label():
    """Stripping the parenthetical to avoid "Tincture Tincture Tincture" compounding
    would otherwise erase woundwort from a jar that still contains it."""
    once = _infuse(_tincture(), "woundwort").as_dict()["output"]
    twice = _infuse(_tincture(base=once["base"]), "mad-cap").as_dict()["output"]
    assert "Woundwort" in twice["base"] and "Mad Cap" in twice["base"], twice["base"]


def test_a_chain_with_no_infuse_is_still_named_for_its_ingredients():
    """The tincture-keeping rule is scoped to infusions. A plain brew of woundwort is a
    new thing and should not inherit a name from whatever jar was in the pot."""
    jar = _tincture()
    chain = Chain(track="herbalist", methods=["brew"], ingredient_ids=["woundwort"],
                  stock_used={jar.id: 1})
    result = crafting.preview("herbalist", 5, chain, stock={jar.id: jar},
                              satchel={"woundwort": 5})
    assert "Mad Cap Tincture" not in result.name, result.name

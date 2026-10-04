"""The forged item's maths (docs/blacksmithing-revamp-plan.md §6, contracts §4).

The record stores ids and passes; every number here is computed on read from material
documents. Those documents are lane C's (`rules/materials.py`), built in parallel, so these
tests supply their own through `forge_items.material` — the one door the build reads — and
pin the arithmetic, not the data.
"""
from __future__ import annotations

import pytest

from rules import forge_items

# The plan's own worked example (§6.4), at the owner's base of ±2.
DOCS = {
    "iron": {
        "id": "iron", "name": "Iron", "kind": "metal", "material": "iron",
        "weapon": [
            {"type": "combat_mod", "target": "damage", "amount": 2, "bonus_type": "material"},
            {"type": "combat_mod", "target": "attack", "amount": -2, "bonus_type": "material"},
            {"type": "gear_mod", "target": "hardness", "amount": 2},
        ],
        "armour": [
            {"type": "combat_mod", "target": "ac", "amount": 2, "bonus_type": "material"},
            {"type": "gear_mod", "target": "acp", "amount": -2},
            {"type": "gear_mod", "target": "hardness", "amount": 2},
        ],
    },
    "ash-haft": {"id": "ash-haft", "name": "Ash haft", "kind": "fitting",
                 "weapon": [{"type": "combat_mod", "target": "attack", "amount": 2,
                             "bonus_type": "material"}]},
    "brass-guard": {"id": "brass-guard", "name": "Brass guard", "kind": "fitting",
                    "weapon": [{"type": "gear_mod", "target": "hardness", "amount": 2}]},
    "mithral": {
        "id": "mithral", "name": "Mithral", "kind": "metal", "material": "mithral",
        "book": True,
        "weapon": [
            {"type": "strikes_as", "target": "silver", "book": True},
            {"type": "gear_mod", "target": "weight_pct", "amount": -50, "book": True},
            {"type": "combat_mod", "target": "attack", "amount": 2, "bonus_type": "material"},
            {"type": "combat_mod", "target": "damage", "amount": -2, "bonus_type": "material"},
        ],
        "armour": [
            {"type": "gear_mod", "target": "acp", "amount": 3, "book": True},
            {"type": "gear_mod", "target": "max_dex", "amount": 2, "book": True},
            {"type": "gear_mod", "target": "asf", "amount": -10, "book": True},
            {"type": "gear_mod", "target": "weight_pct", "amount": -50, "book": True},
            {"type": "gear_mod", "target": "category", "amount": -1, "book": True},
            {"type": "gear_mod", "target": "hardness", "amount": -2},
        ],
    },
    "leaden-lining": {"id": "leaden-lining", "name": "Lead lining", "kind": "fitting",
                      "armour": [{"type": "gear_mod", "target": "asf", "amount": 10},
                                 {"type": "save_mod", "target": "fort", "amount": 2,
                                  "bonus_type": "material"}]},
    "wyvern-blood": {"id": "wyvern-blood", "name": "Wyvern blood", "kind": "quenchant",
                     "quench_mark": {"type": "save_gate", "target": "fort", "dc": 17,
                                     "trigger": "first_wound_daily",
                                     "on_failure": [{"type": "ability_damage",
                                                     "target": "con", "dice": "1d4"}]}},
    "mercury-bath": {"id": "mercury-bath", "name": "Mercury bath", "kind": "quenchant",
                     "quench_mark": {"type": "gear_mod", "target": "hardness", "amount": 1}},
    "alchemical-silver": {"id": "alchemical-silver", "name": "Alchemical silver",
                          "kind": "treatment",
                          "weapon": [{"type": "strikes_as", "target": "silver"},
                                     {"type": "combat_mod", "target": "damage", "amount": -1}]},
}


@pytest.fixture(autouse=True)
def documents(monkeypatch):
    monkeypatch.setattr(forge_items, "material", lambda mid: DOCS.get(str(mid)))


def longsword(**over) -> dict:
    rec = {
        "id": "fine-iron-longsword", "name": "Fine Iron Longsword",
        "kind": "crafted", "craft": "blacksmith", "count": 1,
        "gear": "weapon", "base": "longsword", "slot": "hands",
        "quality": "fine", "quality_index": 2, "masterwork": False,
        "pieces": {"head": {"material": "iron", "passes": 1},
                   "haft": {"material": "ash-haft", "passes": 0},
                   "fittings": {"material": "brass-guard", "passes": 0}},
        "quench": "", "finish": [], "flaws": [],
        "smith": {"level": 2, "perks": {"potency": 0, "hardening": 0}},
        "schema": 3,
    }
    rec.update(over)
    return rec


def row(build: dict, target: str, kind: str | None = None) -> dict:
    return next(r for r in build["sum"] if r["target"] == target
                and (kind is None or r["type"] == kind))


def test_the_worked_example_lands_on_the_plans_integers():
    """Plan §6.4, to the integer: a Fine longsword, iron head Strengthened once, ash haft,
    brass fittings, smith level 2 — +3 damage, −1 attack, +5 hardness. The table in the
    plan is the card the player will read; if the code and the table disagree, one of
    them is lying to the player."""
    b = forge_items.build(longsword())
    damage, attack, hardness = row(b, "damage"), row(b, "attack"), row(b, "hardness")
    assert damage["final"] == 3 and damage["bonus"] == 3.75
    assert attack["pieces"] == {"head": -3.0, "haft": 1.0, "fittings": 0.0}
    assert attack["bonus"] == 1.25 and attack["negative"] == -2.7
    assert attack["final"] == -1
    assert hardness["pieces"] == {"head": 3.0, "haft": 0.0, "fittings": 1.0}
    assert hardness["final"] == 5 and b["gear"]["hardness"] == 5
    specs = {(s["type"], s["target"]): s for s in b["specs"]}
    assert specs[("combat_mod", "damage")]["amount"] == 3
    assert specs[("combat_mod", "attack")]["amount"] == -1
    # Every number says which item put it there (the provenance vocabulary of stage 8).
    assert all(s["origin"] == "item:fine-iron-longsword" for s in b["specs"])
    assert specs[("combat_mod", "attack")]["source"] == "iron+ash-haft"
    assert specs[("combat_mod", "attack")]["bonus_type"] == "material"


def test_negatives_round_toward_zero_not_down():
    """The owner's ruling (2026-10-03): "rounded down" means toward zero, so −1.45 is −1
    and −1.5 is −1. `math.floor` would make both −2 — doubling a small penalty — and
    `round` would make −1.5 into −2 by banker's rounding on the next even number."""
    b = forge_items.build(longsword())
    assert row(b, "attack")["final"] == -1           # −1.45
    # A lone −2 haft-weight negative at level 1: −2 × 0.5 = −1; a level-1 iron head
    # unstrengthened: −2 × 1 = −2 exactly; two passes at level 4: −2 × 2.25 × 0.729.
    b = forge_items.build(longsword(
        pieces={"head": {"material": "iron", "passes": 2}},
        smith={"level": 4, "perks": {}}))
    assert row(b, "attack")["negative"] == pytest.approx(-3.2805)
    assert row(b, "attack")["final"] == -3


def test_floating_point_never_moves_an_integer():
    """1.25 − 2.7 is −1.4500000000000002 in floating point. The sum is rounded to six
    places before it is truncated, so a stray epsilon can never turn +5.0 into 4."""
    assert forge_items._toward_zero(4.999999999999) == 5
    assert forge_items._toward_zero(-1.4500000000000002) == -1
    assert forge_items._toward_zero(-0.9999999999) == -1


def test_book_effects_are_never_weighted_strengthened_or_scaled():
    """Plan §6.3: the printed number is the number. A Flawless mithral head Strengthened
    three times still makes the blade count as silver and weigh half — never 1.75 × 3.375
    × −50% (a weightless sword), which is what scaling book effects would do."""
    b = forge_items.build(longsword(
        quality_index=4,
        pieces={"head": {"material": "mithral", "passes": 3},
                "haft": {"material": "ash-haft"}}))
    assert b["strikes_as"] == ["silver"]
    assert b["gear"]["weight_pct"] == -50
    assert {e["target"] for e in b["book"]} == {"silver", "weight_pct"}
    # The house modifiers on the same head ARE scaled: +2 × 3.375 × 1.75 (+ ash 1 × 1.75).
    assert row(b, "attack")["final"] == int(2 * 3.375 * 1.75 + 1 * 1.75)


def test_book_effects_come_from_the_main_piece_only():
    """A mithral FITTING is not a mithral blade: it does not make the sword strike as
    silver or halve its weight (plan §6.3, "from the main piece only")."""
    b = forge_items.build(longsword(
        pieces={"head": {"material": "iron"}, "fittings": {"material": "mithral"}}))
    assert b["strikes_as"] == []
    assert b["gear"]["weight_pct"] == 0
    # Its house modifiers still count, at half weight.
    assert row(b, "attack")["pieces"]["fittings"] == 1.0


def test_quality_never_worsens_a_negative_and_the_cut_never_shrinks_a_bonus():
    """Bonuses and negatives are scaled apart (§6.2). Summing first and multiplying the
    net by quality would make a Flawless blade's net penalty WORSE than a Crude one's."""
    crude = forge_items.build(longsword(quality_index=0))
    flawless = forge_items.build(longsword(quality_index=4))
    assert row(crude, "attack")["negative"] == row(flawless, "attack")["negative"]
    assert row(flawless, "attack")["bonus"] > row(crude, "attack")["bonus"]
    low = forge_items.build(longsword(smith={"level": 1, "perks": {}}))
    high = forge_items.build(longsword(smith={"level": 9, "perks": {"hardening": 4}}))
    assert row(low, "damage")["bonus"] == row(high, "damage")["bonus"]
    assert row(high, "attack")["negative"] > row(low, "attack")["negative"]


def test_the_negative_cut_is_floored_at_half():
    """§4.3: 0.9 per level after the first and 0.95 per Hardening pick, never below 0.5,
    so a negative never vanishes. Level 6 with two picks is the plan's ≈0.53."""
    assert forge_items.negative_cut(1) == 1.0
    assert forge_items.negative_cut(6, 2) == pytest.approx(0.9 ** 5 * 0.95 ** 2)
    assert forge_items.negative_cut(30, 10) == 0.5


def test_gear_numbers_are_judged_by_direction_not_sign():
    """A lead lining's +10 spell failure is a NEGATIVE (spell failure is worse as it rises,
    effectspec.GEAR_TARGETS), so the level cut shrinks it and quality does not grow it.
    Judging by sign alone, a Flawless lining would have multiplied its own spell failure."""
    shirt = {"id": "lined-shirt", "name": "Lined Shirt", "gear": "armour",
             "base": "chain shirt", "quality_index": 4,
             "pieces": {"body": {"material": "iron"},
                        "lining": {"material": "leaden-lining"}},
             "smith": {"level": 3, "perks": {}}}
    b = forge_items.build(shirt)
    asf = row(b, "asf")
    assert asf["bonus"] == 0 and asf["negative"] == pytest.approx(10 * 0.5 * 0.81)
    assert b["gear"]["asf"] == 4
    # The iron body's −2 check penalty (the table stores penalties negative) is a negative.
    assert row(b, "acp")["negative"] == pytest.approx(-2 * 0.81)


def test_masterwork_is_its_own_effect_from_the_quality_tier():
    """§4.4: Superior or better is masterwork — +1 enhancement on attack for a weapon,
    1 less armour check penalty for armour — with `origin: rule:masterwork`, outside the
    sum and never scaled by Strengthen."""
    b = forge_items.build(longsword(quality_index=3))
    mw = [s for s in b["specs"] if s["origin"] == "rule:masterwork"]
    assert b["masterwork"] and mw == [{
        "type": "combat_mod", "target": "attack", "amount": 1, "bonus_type": "enhancement",
        "origin": "rule:masterwork", "source": "masterwork", "item": "fine-iron-longsword"}]
    assert all(r["target"] != "attack" or r["final"] != 0 for r in b["sum"])
    shirt = forge_items.build({"id": "s", "gear": "armour", "base": "chain shirt",
                               "quality_index": 3, "pieces": {"body": {"material": "iron"}},
                               "smith": {"level": 1}})
    assert shirt["masterwork"] and shirt["gear"]["acp"] == -2 + 1


def test_quench_mark_finish_and_flaws_are_applied_once_unscaled():
    """§6.3: the quench mark once, finishes as their own effects, flaws as fixed numbers —
    none of them through the sum. A mercury bath's +1 hardness stays +1 on a Flawless
    blade; skipping Temper leaves `brittle`, −1 hardness (plan §7)."""
    b = forge_items.build(longsword(quality_index=4, quench="mercury-bath",
                                    finish=["alchemical-silver"], flaws=["brittle"]))
    plain = forge_items.build(longsword(quality_index=4))
    assert b["gear"]["hardness"] == plain["gear"]["hardness"] + 1 - 1
    assert b["strikes_as"] == ["silver"]
    finish = [s for s in b["specs"] if s.get("source") == "alchemical-silver"]
    assert finish and finish[0]["amount"] == -1


def test_riders_keep_their_trigger_and_say_which_item_they_came_from():
    """A trigger-bearing effect is a rider (plan §12.4), never a modifier: wyvern blood's
    first-wound venom lands as its own document stamped `item:<id>` for the engine's
    rider door, and it is not summed into anything."""
    b = forge_items.build(longsword(quench="wyvern-blood"))
    assert len(b["riders"]) == 1
    r = b["riders"][0]
    assert r["trigger"] == "first_wound_daily" and r["origin"] == "item:fine-iron-longsword"
    assert r["source"] == "wyvern-blood" and r["dc"] == 17


def test_preview_is_the_same_build_without_a_record():
    """Contract §4: `preview` answers what Assemble would give, in the same shape, so the
    bench's info line and the finished item can never disagree."""
    made = forge_items.build(longsword())
    seen = forge_items.preview(longsword()["pieces"], gear="weapon", base="longsword",
                               quality_index=2, level=2, perks={},
                               item_id="fine-iron-longsword", name="Fine Iron Longsword")
    assert seen["sum"] == made["sum"] and seen["specs"] == made["specs"]
    assert seen["gear"] == made["gear"]


def test_an_unknown_material_is_a_problem_in_words_not_a_crash():
    """A record naming a material that is not (or no longer) in the documents builds what
    it can and says what is missing — a crash here would take the sheet down on load."""
    b = forge_items.build(longsword(pieces={"head": {"material": "unobtainium"},
                                            "haft": {"material": "ash-haft"}}))
    assert b["problems"] == ["head: no material called 'unobtainium'."]
    assert row(b, "attack")["final"] == 1


def test_the_material_door_survives_without_lane_cs_module(monkeypatch):
    """`rules/materials.py` is built in parallel by lane C. Until it lands, the door
    answers None rather than raising ImportError on every sheet read."""
    monkeypatch.undo()
    import importlib.util

    if importlib.util.find_spec("rules.materials") is None:
        assert forge_items.material("iron") is None
    assert forge_items.material("") is None


def test_a_forged_record_survives_the_save(tmp_path):
    """`Actor.stock` holds `crafting.Stock`, which has no field for pieces, passes or a
    quality index: put in as a plain Stock, the record would come back from the next save
    as a name with nothing to compute from. `ForgedStock` keeps it whole."""
    from rules import sheet

    pc = sheet.load_pc("fixtures/pc-kesst.json")
    pc.add_stock(forge_items.stock_item(longsword()))
    assert "fine-iron-longsword" in pc.stock
    back = sheet.from_dict(sheet.to_dict(pc))
    rec = forge_items.record_of(back.stock["fine-iron-longsword"])
    assert rec is not None and rec["pieces"]["head"] == {"material": "iron", "passes": 1}
    assert back.stock["fine-iron-longsword"].craft == "blacksmith"
    # The read-live rule: the save holds ids and passes, never a computed number.
    saved = sheet.to_dict(pc)["stock"]["fine-iron-longsword"]
    assert "specs" not in saved or not saved.get("specs")
    assert forge_items.build(rec)["sum"] == forge_items.build(longsword())["sum"]

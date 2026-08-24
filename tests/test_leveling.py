"""Paths, levelling, and the class table a player plans against.

Blood Bending declares four paths — battle blood, blood spike, coagulator, blood
commander — and the abilities behind them are not in the class file. That absence is
the file's own note and it is deliberate: they are not written down anywhere in this
repository, and inventing eighty abilities and calling them somebody's homebrew is
worse than an empty branch. What is built here is the structure around the choice, so
the moment the abilities are written they grant like any other class feature.
"""
from __future__ import annotations

import pytest

from rules import creation, leveling
from rules.dice import Dice
from rules.sheet import from_dict, load_pc, to_dict


def bender(**over):
    base = {
        "name": "Path Test", "race": "half-orc", "bonus_ability": "con",
        "class": "blood bending",
        "abilities": {"str": 12, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 10},
        "skills": [], "feats": [], "paths": ["battle blood"],
    }
    base.update(over)
    return base


# --- the four paths ------------------------------------------------------------------

def test_the_class_declares_its_own_paths():
    assert set(leveling.paths_for("blood bending")) == {
        "battle blood", "blood spike", "coagulator", "blood commander"}
    assert leveling.paths_for("fighter") == []
    assert leveling.needs_path("blood bending")
    assert not leveling.needs_path("fighter")


def test_a_bender_must_take_a_path():
    """"if you choose blood bender you have to choose a path or both paths"."""
    _, problems = creation.build(bender(paths=[]))
    assert any("follows a path" in p and "Path A" in p for p in problems)


def test_a_bender_may_take_more_than_one():
    built, problems = creation.build(bender(paths=["coagulator", "blood commander"]))
    assert problems == []
    assert built["sheet"]["paths"] == ["coagulator", "blood commander"]


def test_a_path_the_class_does_not_offer_is_refused():
    _, problems = creation.build(bender(paths=["blood accountant"]))
    assert any("not a path of this class" in p for p in problems)


def test_a_class_with_no_paths_may_not_carry_one():
    """A rogue with a Coagulator branch is a save that confuses everything downstream
    that reads it."""
    _, problems = creation.build(bender(**{"class": "fighter"}, paths=["coagulator"]))
    assert any("it has none" in p for p in problems)


def test_the_choice_survives_a_save():
    built, _ = creation.build(bender(paths=["blood spike"]))
    assert from_dict(to_dict(from_dict(built["sheet"]))).paths == ["blood spike"]


def test_the_forge_is_told_which_paths_a_class_offers():
    classes = {c["id"]: c for c in creation.options()["classes"]}
    assert len(classes["blood bending"]["paths"]) == 4
    assert classes["fighter"]["paths"] == []


# --- levelling -------------------------------------------------------------------------

def test_a_level_rolls_its_hit_points_rather_than_maximising_them():
    """First level takes the whole die; every level after it rolls. That is the rule
    the user's own sentence draws the contrast against — "2d8 is a roll that should be
    made to get my actual health... however lvl 1 should get Max HP"."""
    pc = load_pc("fixtures/pc-kesst.json")
    _earned(pc)
    before, was = pc.hp_max, pc.level
    got = leveling.level_up(pc, dice=Dice(seed=5))
    assert got["ok"] and pc.level == was + 1
    assert 1 <= got["rolled"] <= 8              # a rogue's d8, rolled not assumed
    assert pc.hp_max == before + got["hp"]
    assert got["hp"] == max(1, got["rolled"] + got["con"])


def test_a_level_never_costs_hit_points():
    """A wretched Constitution and a low roll must not take hit points away."""
    pc = load_pc("fixtures/pc-kesst.json")
    _earned(pc)
    pc.abilities["con"] = 3
    before = pc.hp_max
    got = leveling.level_up(pc, dice=Dice(seed=1))
    assert got["hp"] >= 1 and pc.hp_max > before


def test_the_twentieth_level_is_the_last():
    pc = load_pc("fixtures/pc-kesst.json")
    pc.level = leveling.MAX_LEVEL
    assert leveling.level_up(pc)["ok"] is False


def test_what_a_level_is_worth_is_read_from_the_class_not_invented():
    """A Blood Bender's second level: the class file says bonus feat, evasion and
    blood sense, and nothing here says otherwise."""
    gains = leveling.gains_at("blood bending", 2)
    assert gains["grants"] == ["bonus feat", "evasion", "blood sense 60ft"]
    assert gains["bab"] >= 0


def test_a_class_the_app_has_never_seen_is_refused_rather_than_guessed():
    pc = load_pc("fixtures/pc-kesst.json")
    pc.char_class = "chronomancer"
    assert leveling.level_up(pc)["ok"] is False


# --- the table a player plans against --------------------------------------------------

def test_the_whole_twenty_level_table_is_offered_reached_or_not():
    """"add the class tab to the full character sheet page so the player can see the
    full class and plan ahead." Planning means seeing the rows you have not reached."""
    rows = leveling.preview("blood bending", 3)
    assert len(rows) == leveling.MAX_LEVEL
    assert [r["reached"] for r in rows[:4]] == [True, True, True, False]
    assert rows[0]["grants"]


def test_columns_the_app_has_never_heard_of_still_show():
    """Blood Bending prints `fist` and `blood` on its table. Reading the row rather
    than naming the columns is what lets a class ship with its own."""
    row = leveling.preview("blood bending", 1)[2]
    assert row["columns"] == {"fist": "1d6", "blood": "1d8"}


def test_the_sheet_carries_the_progression_and_the_paths():
    from rules.sheet import full_sheet

    built, _ = creation.build(bender(paths=["coagulator"]))
    p = full_sheet(from_dict(built["sheet"]))["progression"]
    assert len(p["rows"]) == 20
    assert p["paths_taken"] == ["coagulator"]
    assert len(p["paths_offered"]) == 4
    assert p["next"]["level"] == 2


def test_the_class_tab_exists_and_draws_the_table():
    from pathlib import Path

    page = Path("play/templates/play/table.html").read_text(encoding="utf-8")
    assert '["class",     "Class",     s => tabClass(s)]' in page
    assert "function tabClass(s)" in page
    assert "The whole table" in page
    assert 'id="levelup"' in page


def test_the_paths_carry_the_authors_own_abilities():
    """They were in the author's document all along, tiered by Control Blood level —
    which is exactly what `control blood 1a` through `5b` on the class table means.
    `tools/import_blood_paths.py` lifted them in without paraphrase."""
    for name in ("blood spike", "coagulator", "blood commander", "battle blood"):
        det = leveling.path_detail("blood bending", name)
        assert det, name
        assert det["role"], name
        # Not every path carries a blurb: Blood Commander's heading is followed
        # straight by its table in the document, and inventing one line of flavour is
        # the same mistake as inventing eighty abilities.
        assert "summary" in det
        assert sorted(det["tiers"]) == ["1", "2", "3", "4", "5"], name
        assert det["abilities"], name


def test_a_scaled_ability_finds_the_text_written_under_its_bare_name():
    """A tier row names "Blood Burst 40ft"; the description is written once under
    "Blood Burst". Without resolving that, four ranks in five rendered blank."""
    bb = leveling.path_detail("blood bending", "battle blood")
    assert bb["resolves"]["Blood Burst 40ft"] == "Blood Burst"
    assert bb["abilities"]["Blood Burst"]


def test_a_rank_described_inside_its_parents_sentence_is_found():
    """I reported four Battle Blood abilities as undescribed and the author corrected
    me on every one. Two are ranks defined inside Blood Rage's own sentence —
    "Upgrades to Greater Blood Rage (+3 attack/damage, +3 Temp HP/HD) and Mighty Blood
    Rage (+4 ...)" — which reading only headings could never see."""
    bb = leveling.path_detail("blood bending", "battle blood")
    assert bb["resolves"]["Mighty Blood Rage"] == "Blood Rage"
    assert bb["upgrades"]["Mighty Blood Rage"] == "+4 attack/damage, +4 Temp HP/HD"
    assert bb["upgrades"]["Greater Blood Rage"] == "+3 attack/damage, +3 Temp HP/HD"


def test_an_ability_whose_name_starts_with_a_digit_is_read():
    """"1-2-Punch" was skipped because the definition pattern insisted on a capital
    letter, so a fully-written ability was reported as missing."""
    bb = leveling.path_detail("blood bending", "battle blood")
    assert bb["abilities"]["1-2-Punch"].startswith("Subsequent attacks")


def test_a_core_rulebook_ability_is_a_reference_not_an_omission():
    """Uncanny Dodge is 1e's, and naming it on a homebrew table is a citation. Calling
    it undescribed said the document was missing something it had no reason to write."""
    bb = leveling.path_detail("blood bending", "battle blood")
    assert bb["core"] == ["Uncanny Dodge"]


def test_every_listed_ability_now_resolves_to_something():
    """62 of 62 — nothing on any path's table is left unexplained."""
    for name in leveling.paths_for("blood bending"):
        det = leveling.path_detail("blood bending", name)
        assert det["undescribed"] == [], (name, det["undescribed"])


def test_the_page_shows_the_tiers_and_is_honest_about_the_engine():
    from pathlib import Path

    page = Path("play/templates/play/table.html").read_text(encoding="utf-8")
    assert "Control Blood ${esc(tier)}" in page
    assert "the source does not describe it" in page
    assert "the engine does not" in page and "execute these yet" in page


# --- over the wire ---------------------------------------------------------------------

def test_the_level_up_endpoint_actually_works(tmp_path, settings):
    """Every test above passed while the endpoint 500'd on `c.engine.dice` — `engine`
    is a method on Campaign, not a property. Unit tests on `leveling` could not see
    that, because the mistake was in the wiring rather than in the rules."""
    import json as _json

    from django.test import Client

    from play import campaign as cm

    settings.CAMPAIGN_DIR = str(tmp_path / "campaigns")
    cm._LIVE.clear()
    client = Client()

    built, problems = creation.build(bender(name="Wire Test"))
    assert problems == []
    r = client.post("/api/character/create",
                    data=_json.dumps(bender(name="Wire Test", begin=True)),
                    content_type="application/json")
    assert r.status_code == 200

    # The gate refuses an unearned level with the ledger's own numbers...
    r = client.post("/api/level-up")
    assert r.status_code == 409
    assert b"needs 2,000" in r.content

    # ...and opens once the XP is real.
    pc = cm.current().scene.pc()
    was = pc.level
    from rules import xp

    pc.xp = xp.total_for(was + 1)
    r = client.post("/api/level-up")
    assert r.status_code == 200, r.content[:200]
    got = r.json()["levelled"]
    assert got["level"] == was + 1
    assert got["rolled"] >= 1
    assert cm.current().scene.pc().level == was + 1


def test_levelling_is_refused_at_twenty_over_the_wire(tmp_path, settings):
    import json as _json

    from django.test import Client

    from play import campaign as cm

    settings.CAMPAIGN_DIR = str(tmp_path / "campaigns")
    cm._LIVE.clear()
    client = Client()
    client.post("/api/character/create",
                data=_json.dumps(bender(name="Capped", begin=True)),
                content_type="application/json")
    c = cm.current()
    c.scene.pc().level = leveling.MAX_LEVEL
    c.save()

    r = client.post("/api/level-up")
    assert r.status_code == 409
    assert "20th level" in r.json()["error"]


# --- abilities the engine can actually run ---------------------------------------------

def test_path_abilities_carry_converted_effects():
    """The same treatment consumables and creatures had: prose anchored on a number, a
    save or a named mechanic becomes an effect spec; anything a pattern cannot claim is
    left as prose rather than guessed at."""
    for name in leveling.paths_for("blood bending"):
        det = leveling.path_detail("blood bending", name)
        assert det["effects_converted"] is True
        assert isinstance(det["effects"], dict)
        assert isinstance(det["needs"], dict)


def test_a_ladder_of_damage_reduction_is_not_four_reductions():
    """Iron Clot writes its whole ladder in one sentence — DR 2/-, 5/-, 8/-, 12/- —
    and emitting each as its own effect gave a first-level character DR 27.

    It first converted to nothing, honestly, because several values is a rank that
    scales and the engine could not express one. Now it converts to a single reduction
    whose rung is chosen by the track, which is what the sentence always meant.
    """
    coag = leveling.path_detail("blood bending", "coagulator")
    spec = coag["effects"]["Iron Clot"]
    assert len(spec) == 1, "one reduction, not four"
    assert spec[0]["scales_by"] == "control_blood"
    assert "Iron Clot" not in coag["needs"]


def test_taking_stacks_away_is_not_applying_one():
    """"Pull back blood stacks from all surrounding enemies" was converted as applying
    a stack — the opposite of what it does. A confidently wrong conversion is worse
    than no conversion."""
    coag = leveling.path_detail("blood bending", "coagulator")
    assert "Sanguine Siphon" not in coag["effects"]


def test_what_the_engine_still_lacks_is_named_per_ability():
    """Two shapes recur and neither is forced: Control Blood scaling and multiples of
    the class table's Blood die. "Blood Pools as scene objects" used to be the third
    and is now built, which is why this test no longer looks for it."""
    spike = leveling.path_detail("blood bending", "blood spike")
    every = {n for names in spike["needs"].values() for n in names}
    assert any("Blood die" in n or "Control Blood level" in n for n in every)
    assert not any("Pools as objects" in n for n in every)


def test_making_and_spending_pools_are_ops_now():
    """The capability that unlocked the largest block of unconverted abilities."""
    spike = leveling.path_detail("blood bending", "blood spike")
    made = spike["effects"]["Blood Pool Manifestation"]
    assert made[0]["op"] == "blood_pool"
    burst = spike["effects"]["Hemorrhagic Eruption"]
    spend = next(e for e in burst if e.get("op") == "spend_pools")
    # "Detonate any number of Blood Pools" is genuinely unbounded; a cap here would be
    # a rule nobody wrote.
    assert spend["count"] == "all"


def test_a_self_cost_in_non_lethal_damage_converts():
    """The class's whole economy is paying in non-lethal damage, and it is the one
    cost the engine already models exactly."""
    coag = leveling.path_detail("blood bending", "coagulator")
    aura = coag["effects"]["Blood Spatter Aura"]
    cost = next(e for e in aura if e["type"] == "damage")
    assert cost["lethality"] == "nonlethal" and cost["dice"] == "1d4"


def test_the_map_has_a_tab_of_its_own():
    """"the mapping is under the hood lets have a tab on the left that can pop out the
    map for the user to see." The side panel drew it at 18px to the square, legible as
    a shape and not as a grid anybody could plan a move on."""
    from pathlib import Path

    page = Path("play/templates/play/table.html").read_text(encoding="utf-8")
    assert 'id="maptab"' in page and 'id="maptray"' in page
    assert "function showMap(" in page
    # It refills while open, so a token that moves during a turn moves here too.
    assert '$("#maptray").classList.contains("on")' in page


# --- blood on the ground ---------------------------------------------------------------

def _fight():
    from rules.engine import Engine, Scene
    from rules.grid import Grid

    scene = Scene(location_id=None, grid=Grid(width=8, height=8))
    scene.add(load_pc("fixtures/pc-kesst.json"))
    scene.positions["pc"] = (2, 2)
    return Engine(scene, Dice(seed=9))


def _run(engine, raw):
    return engine.run(engine.validate([raw])).outcomes


def test_a_pool_lands_where_the_bender_is_standing():
    """Blood Pool Manifestation puts one "in the target's square (or your square if
    self)", so the square is read from the scene rather than asked for."""
    eng = _fight()
    _run(eng, {"op": "blood_pool", "actor": "pc"})
    assert len(eng.scene.pools) == 1
    assert eng.scene.pools[0].at == (2, 2)
    assert eng.scene.pools[0].owner == "pc"


def test_a_pool_can_be_put_on_a_named_square():
    eng = _fight()
    _run(eng, {"op": "blood_pool", "actor": "pc", "params": {"at": [5, 6]}})
    assert eng.scene.pools[0].at == (5, 6)


def test_pools_work_without_a_map_at_all():
    """The scene's positions are optional and so are theirs — a pool in a
    theatre-of-the-mind fight is still a pool that can be spent."""
    from rules.engine import Engine, Scene

    scene = Scene(location_id=None)
    scene.add(load_pc("fixtures/pc-kesst.json"))
    eng = Engine(scene, Dice(seed=2))
    _run(eng, {"op": "blood_pool", "actor": "pc"})
    assert len(eng.scene.pools) == 1 and eng.scene.pools[0].at is None


def test_spending_takes_them_back_off_the_ground():
    eng = _fight()
    for _ in range(3):
        _run(eng, {"op": "blood_pool", "actor": "pc"})
    out = _run(eng, {"op": "spend_pools", "actor": "pc", "params": {"count": 2}})
    assert len(eng.scene.pools) == 1
    assert "2 pools" in out[0].tell


def test_any_number_means_all_of_them():
    """"Detonate any number of Blood Pools within Blood Sense range" is genuinely
    unbounded, and a cap the engine invented would be a rule nobody wrote."""
    eng = _fight()
    for _ in range(4):
        _run(eng, {"op": "blood_pool", "actor": "pc"})
    _run(eng, {"op": "spend_pools", "actor": "pc", "params": {"count": "all"}})
    assert eng.scene.pools == []


def test_spending_blood_that_is_not_there_says_so():
    eng = _fight()
    out = _run(eng, {"op": "spend_pools", "actor": "pc"})
    assert "no blood on the ground" in out[0].tell


def test_pools_survive_a_save(tmp_path, settings):
    from play import campaign as cm

    settings.CAMPAIGN_DIR = str(tmp_path / "campaigns")
    cm._LIVE.clear()
    c = cm.new_campaign("pools", character=load_pc("fixtures/pc-kesst.json"))
    eng = c.engine()
    _run(eng, {"op": "blood_pool", "actor": "pc", "params": {"amount": 2,
                                                            "source": "a spike"}})
    c.save()

    again = cm.Campaign.load(c.path())
    assert len(again.scene.pools) == 1
    assert again.scene.pools[0].amount == 2
    assert again.scene.pools[0].source == "a spike"


def test_the_map_draws_them():
    from pathlib import Path

    page = Path("play/templates/play/table.html").read_text(encoding="utf-8")
    assert "bloodpool" in page
    assert "pools of blood on the ground" in page or "pool${" in page


# --- Control Blood scaling ---------------------------------------------------------------

def _coagulator(level=1):
    built, problems = creation.build(bender(name="Clot", paths=["coagulator"]))
    assert problems == []
    pc = from_dict(built["sheet"])
    pc.level = level
    return pc


def test_control_blood_is_read_off_the_class_table_not_written_out_again():
    """The grants say "control blood 1a" at 1st, "2a" at 3rd, "5a" at 10th, "1b" at
    11th. A second copy of that progression here would be a second thing to keep level
    with the first."""
    assert leveling.control_blood(_coagulator(1)) == {"a": 1, "b": 0}
    assert leveling.control_blood(_coagulator(5)) == {"a": 3, "b": 0}
    assert leveling.control_blood(_coagulator(11)) == {"a": 5, "b": 1}


def test_the_two_tracks_are_the_two_paths():
    """"you have to choose a path or both paths" — the a-track is the first path
    followed and the b-track the second, which is what the halves of the table are
    for. A path never taken has no tier."""
    built, _ = creation.build(bender(paths=["coagulator", "blood spike"]))
    pc = from_dict(built["sheet"])
    pc.level = 11
    assert leveling.control_blood_for(pc, "coagulator") == 5
    assert leveling.control_blood_for(pc, "blood spike") == 1
    assert leveling.control_blood_for(pc, "battle blood") == 0


def test_a_ladder_picks_the_rung_the_character_has_reached():
    """Iron Clot's four values are one DR chosen by the track, not four DRs summing to
    27 — the false conversion this replaces."""
    spec = leveling.path_detail("blood bending", "coagulator")["effects"]["Iron Clot"][0]
    assert spec["scales_by"] == "control_blood"
    got = [leveling.resolve_effect(spec, _coagulator(n), "coagulator")["amount"]
           for n in (1, 3, 5, 10)]
    assert got == [2, 5, 8, 12]


def test_a_tier_that_grants_no_new_rung_keeps_the_one_below():
    """The ladder skips tier 4. At Control Blood 4 the character still has DR 8,
    because nothing took it away."""
    spec = leveling.path_detail("blood bending", "coagulator")["effects"]["Iron Clot"][0]
    got = leveling.resolve_effect(spec, _coagulator(7), "coagulator")
    assert got["control_blood"] == 4 and got["at_tier"] == 3 and got["amount"] == 8


def test_a_formula_over_the_track_is_evaluated_like_any_pool_formula():
    """"Armor Bonus to AC equal to 3+ControlBloodLevel". The pools have evaluated
    formulas since they were written; this points one at the track."""
    spec = leveling.path_detail(
        "blood bending", "coagulator")["effects"]["Coagulated Plate"][0]
    assert spec["formula"] == "3 + control_blood"
    assert leveling.resolve_effect(spec, _coagulator(5), "coagulator")["amount"] == 6


def test_a_branch_the_character_never_took_grants_nothing():
    spec = leveling.path_detail("blood bending", "coagulator")["effects"]["Iron Clot"][0]
    built, _ = creation.build(bender(paths=["blood spike"]))
    got = leveling.resolve_effect(spec, from_dict(built["sheet"]), "coagulator")
    assert got.get("inactive") is True


def test_formulas_can_name_the_track():
    """`resources.variables` exposes it, so a class file can write a pool or a
    modifier against Control Blood rather than against character level."""
    from rules import resources

    assert resources.evaluate("control_blood", _coagulator(5)) == 3
    assert resources.evaluate("control_blood_b", _coagulator(11)) == 1


def test_a_class_that_does_not_branch_reads_zero_rather_than_failing():
    """Every formula on every sheet runs through this, including classes and stand-in
    actors that have never heard of a track."""
    from rules import resources

    assert resources.evaluate("control_blood", load_pc("fixtures/pc-kesst.json")) == 0


# --- multiples of the class table's own die -----------------------------------------------

def _spiker(level=1):
    built, problems = creation.build(bender(name="Spike", paths=["blood spike"]))
    assert problems == []
    pc = from_dict(built["sheet"])
    pc.level = level
    return pc


def test_the_die_is_read_off_the_row_not_written_into_the_effect():
    """"Blood DMG ×2" names a column and a multiplier. The number cannot be baked in:
    a Blood Bender's blood die is 1d8 at first level and 5d12 at twentieth."""
    spec = next(e for e in leveling.path_detail(
        "blood bending", "blood spike")["effects"]["Blood Mine"] if e.get("dice_from"))
    assert spec["dice_from"] == "blood" and spec["times"] == 2
    assert "dice" not in spec


def test_a_multiplier_multiplies_the_count_and_not_the_face():
    """Three times a d8 is three d8s, not one d24 — what a damage multiplier means in
    1e. A flat bonus is part of the thing being tripled, so it rides along."""
    assert leveling.multiply_dice("1d8", 3) == "3d8"
    assert leveling.multiply_dice("2d8", 2) == "4d8"
    assert leveling.multiply_dice("1d6+2", 3) == "3d6+6"
    assert leveling.multiply_dice("5d12", 1) == "5d12"


def test_the_same_ability_grows_with_the_class_table():
    spec = next(e for e in leveling.path_detail(
        "blood bending", "blood spike")["effects"]["Blood Mine"] if e.get("dice_from"))
    got = [leveling.resolve_effect(spec, _spiker(n), "blood spike")["dice"]
           for n in (1, 4, 10, 20)]
    assert got == ["2d8", "4d8", "8d8", "10d12"]


def test_the_resolved_effect_says_where_the_die_came_from():
    """The sheet's whole proposition: not "8d8" but "8d8, from blood 4d8"."""
    spec = next(e for e in leveling.path_detail(
        "blood bending", "blood spike")["effects"]["Blood Mine"] if e.get("dice_from"))
    got = leveling.resolve_effect(spec, _spiker(10), "blood spike")
    assert got["from_column"] == "blood 4d8"


def test_a_class_printing_no_such_column_is_inactive_rather_than_wrong():
    """Read by column name so a class with a die nobody here has heard of works. The
    other half of that is a class that has none: better silent than invented."""
    got = leveling.resolve_effect({"type": "damage", "dice_from": "blood", "times": 2},
                                  load_pc("fixtures/pc-kesst.json"))
    assert got.get("inactive") is True


def test_nothing_is_left_needing_the_blood_die():
    """It was the last of the three shapes the conversion could not express."""
    for name in leveling.paths_for("blood bending"):
        every = " ".join(n for names in leveling.path_detail(
            "blood bending", name)["needs"].values() for n in names)
        assert "Blood die" not in every, name


# --- using one in play -------------------------------------------------------------------

def _table(level=5, paths=("blood spike", "coagulator")):
    from rules.bestiary import instantiate
    from rules.engine import Engine, Scene
    from rules.grid import Grid

    built, problems = creation.build(bender(name="Vashka", paths=list(paths)))
    assert problems == []
    pc = from_dict(built["sheet"], ref="pc")
    pc.level = level
    scene = Scene(location_id=None, grid=Grid(width=8, height=8))
    scene.add(pc)
    scene.positions["pc"] = (2, 2)
    scene.add(instantiate("thug", scene=scene, name="the bravo"))
    scene.positions["c1"] = (4, 2)
    return Engine(scene, Dice(seed=6)), pc


def _use(engine, **params):
    raw = {"op": "use_ability", "actor": "pc", "params": params}
    return engine.run(engine.validate([raw])).outcomes[0]


def test_an_ability_can_be_used_by_name():
    eng, pc = _table()
    out = _use(eng, ability="Blood Pool Manifestation")
    assert "Blood Pool Manifestation" in out.tell
    assert len(eng.scene.pools) == 1


def test_the_tell_counts_what_was_resolved_and_what_was_not():
    """An ability that says it did nine things and silently did two is worse than one
    that did nothing, so both halves are reported."""
    eng, _ = _table()
    out = _use(eng, ability="Blood Mine", to="c1")
    assert "The engine resolves:" in out.tell
    assert "yours to narrate" in out.tell


def test_lethal_damage_never_falls_back_to_the_person_using_it():
    """Half of these are areas. Defaulting the target to the actor had Hemorrhagic
    Eruption detonating pools on its own caster for 21 and ending them at -1."""
    eng, pc = _table()
    _use(eng, ability="Blood Pool Manifestation")
    before = pc.hp
    out = _use(eng, ability="Hemorrhagic Eruption")
    assert pc.hp == before, out.tell
    assert "pool spent" in out.tell


def test_the_self_cost_is_still_paid_by_the_user():
    """The one damage that *is* the user's: this class buys everything with its own
    non-lethal, and that must not be lost with the fix above."""
    eng, pc = _table()
    out = _use(eng, ability="Crimson Torrent", to="c1")
    assert "pays" in out.tell and "non-lethal" in out.tell


def test_an_ability_above_the_characters_tier_is_refused_with_the_number():
    eng, _ = _table(level=5)
    out = _use(eng, ability="Heart-Seeker Spike")
    assert "Control Blood 5" in out.tell and "has reached 3" in out.tell


def test_an_ability_from_a_path_never_taken_is_not_theirs():
    from rules.intents import IntentError

    eng, _ = _table(paths=("coagulator",))
    with pytest.raises(IntentError):
        _use(eng, ability="Blood Mine")


def test_an_ability_nobody_wrote_is_refused_and_says_which_paths_they_have():
    from rules.intents import IntentError

    eng, _ = _table()
    with pytest.raises(IntentError) as e:
        _use(eng, ability="Blood Accountancy")
    assert "blood spike" in str(e.value)


def test_a_trigger_clause_is_not_damage_dealt():
    """"Whenever you deal Blood DMG ... a Blood Pool appears" is a condition, not an
    attack. Reading it as one made Blood Pool Manifestation — whose whole content is
    leaving a pool behind — take ten hit points off the bender who used it."""
    spike = leveling.path_detail("blood bending", "blood spike")
    made = spike["effects"]["Blood Pool Manifestation"]
    assert all(e.get("type") != "damage" for e in made)


# --- the GM knowing, and a way to press it -----------------------------------------------

def test_the_brief_tells_the_gm_what_this_character_can_do():
    """Fifty-four turns produced one mechanical intent between them, partly because
    the GM was never told the class had abilities at all. It cannot reach for a name
    it has not been given."""
    from gm import prompts

    eng, pc = _table()

    class W:
        name, secret, premise = "Testholme", "", {}
        entities, unwritten, chronology, factions = {}, [], [], []

        def ancestors(self, _):
            return []

    brief = prompts.scene_brief(W(), eng.scene, None, None)
    assert "WHAT VASHKA CAN DO" in brief
    assert "Blood Mine" in brief and "use_ability" in brief
    # And nothing above their tier, which would be a name they cannot use.
    assert "Heart-Seeker Spike" not in brief


def test_a_named_ability_reaches_the_engine_whatever_the_gm_proposed():
    """The brief lists them and the model still narrates the spike and emits
    narrate_only. Same shape and same reason as the survival and goods injections."""
    from gm import judgement

    eng, _ = _table()
    out = judgement.inject_ability([{"op": "narrate_only"}],
                                   "I lay a Blood Mine in the doorway", eng.scene)
    used = next(i for i in out if i["op"] == "use_ability")
    assert used["params"]["ability"] == "Blood Mine"
    assert used["params"]["to"] == "c1"          # one hostile is not a guess


def test_the_longest_name_wins():
    """"Blood Pool Manifestation" must not be read as "Blood Pool"."""
    from gm import judgement

    eng, _ = _table()
    out = judgement.inject_ability([{"op": "narrate_only"}],
                                   "I use Blood Pool Manifestation", eng.scene)
    assert next(i for i in out if i["op"] == "use_ability"
                )["params"]["ability"] == "Blood Pool Manifestation"


def test_asking_about_an_ability_is_not_using_it():
    from gm import judgement

    eng, _ = _table()
    raw = [{"op": "narrate_only"}]
    assert judgement.inject_ability(raw, "What does Blood Mine do?", eng.scene) == raw


def test_an_ability_above_their_tier_is_not_injected():
    from gm import judgement

    eng, _ = _table(level=5)
    raw = [{"op": "narrate_only"}]
    assert judgement.inject_ability(raw, "I fire a Heart-Seeker Spike", eng.scene) == raw


def test_the_state_carries_only_the_abilities_they_can_use():
    from play.views import _usable_abilities

    _, pc = _table(level=5)
    names = {a["name"] for a in _usable_abilities(pc)}
    assert "Blood Mine" in names and "Heart-Seeker Spike" not in names
    assert all(a["path"] and a["tier"] for a in _usable_abilities(pc))


def test_a_character_with_no_paths_gets_no_buttons():
    from play.views import _usable_abilities

    assert _usable_abilities(load_pc("fixtures/pc-kesst.json")) == []


def test_the_page_draws_them_as_buttons():
    from pathlib import Path

    page = Path("play/templates/play/table.html").read_text(encoding="utf-8")
    assert 'id="abilities"' in page and "renderAbilities" in page
    assert "data-ability" in page


# --- two paths, in order (clarified 2026-08-23) ------------------------------------------

def test_a_bender_follows_two_paths_at_most():
    """"you should only be able to chose two paths, Path A and Path B." Two is not a
    house rule: the progression has an a-track and a b-track and no third, so it is
    what the table can actually carry."""
    assert leveling.max_paths("blood bending") == 2
    _, problems = creation.build(bender(
        paths=["coagulator", "blood spike", "battle blood"]))
    assert any("2 paths at most" in p and "Path A" in p for p in problems)


def test_the_first_chosen_is_path_a_and_the_second_path_b():
    """"the fist path you choose should be path A and the second path b" — order is
    the whole meaning of the choice, so it is preserved rather than sorted."""
    built, problems = creation.build(bender(paths=["blood spike", "coagulator"]))
    assert problems == []
    assert built["sheet"]["paths"] == ["blood spike", "coagulator"]


def test_path_a_runs_from_first_level_and_path_b_waits():
    """"you begin with path A available getting 1a abilities at lvl 1 ... you
    eventually unlock 1b at which point you gain access to the next path.\""""
    assert leveling.unlocks_at("blood bending", 0) == 1
    assert leveling.unlocks_at("blood bending", 1) == 11

    built, _ = creation.build(bender(paths=["coagulator", "blood spike"]))
    pc = from_dict(built["sheet"])
    pc.level = 1
    assert leveling.control_blood_for(pc, "coagulator") == 1
    assert leveling.control_blood_for(pc, "blood spike") == 0
    pc.level = 11
    assert leveling.control_blood_for(pc, "blood spike") == 1


def test_nothing_from_path_b_is_usable_before_it_opens():
    from play.views import _usable_abilities

    built, _ = creation.build(bender(paths=["coagulator", "blood spike"]))
    pc = from_dict(built["sheet"])
    pc.level = 5
    paths = {a["path"] for a in _usable_abilities(pc)}
    assert paths == {"coagulator"}
    pc.level = 11
    assert "blood spike" in {a["path"] for a in _usable_abilities(pc)}


def test_the_forge_says_which_slot_is_which():
    from pathlib import Path

    page = Path("play/templates/play/home.html").read_text(encoding="utf-8")
    assert "Path A" in page and "Path B" in page


# --- Blood Bond, whole -------------------------------------------------------------------
#
# "where is this data?" — the user quoting the class document's full Blood Bond paragraph.
# The honest answer was "mostly nowhere": of its six clauses, two had become overrides,
# one was baked into each ability's own wording, and three did not exist — including two
# that are mechanics, not flavour. The text is stored in the class file now and these pin
# the two mechanics that were missing.

def _earned(pc):
    """XP enough for the next level: these tests are about what a level *does*, and the
    gate — the feature that levels are earned, not chosen — has its own tests below."""
    from rules import xp

    pc.xp = xp.total_for(int(pc.level) + 1)
    return pc


def _bender(level=4):
    from rules.sheet import from_dict, load_pc, to_dict

    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d["class"] = "blood bending"
    d["level"] = level
    d["ranks"] = {}
    return _earned(from_dict(d, ref="pc"))


def test_blood_bond_grants_con_every_five_levels():
    """'Permanently increase your Constitution by +2 for every 5 levels.' Applied to the
    base score so every recompute keeps it, and named in the level's own grants."""
    from rules.dice import Dice

    pc = _bender(level=4)
    before = pc.abilities["con"]
    r = leveling.level_up(pc, dice=Dice(seed=1))
    assert pc.abilities["con"] == before + 2
    assert "Con +2 (permanent)" in r["grants"]


def test_the_growth_only_fires_on_the_multiples():
    from rules.dice import Dice

    pc = _bender(level=5)
    before = pc.abilities["con"]
    leveling.level_up(pc, dice=Dice(seed=1))  # 6th: not a multiple of five
    assert pc.abilities["con"] == before


def test_healing_at_full_banks_as_temporary_hit_points():
    """'Any healing you receive while your health is at max becomes Temporary HP.' Gated
    on the class's own override, applied automatically at load — no other class banks."""
    pc = _bender()
    assert pc.allows("heal.overflow_temp_hp")
    pc.hp = pc.hp_max
    restored = pc.heal(5)
    assert restored == 0
    assert sum(p.amount for p in pc.temp_pools) == 5


def test_partial_overflow_banks_only_the_spare():
    pc = _bender()
    pc.hp = pc.hp_max - 2
    pc.heal(5)
    assert pc.hp == pc.hp_max
    assert sum(p.amount for p in pc.temp_pools) == 3


def test_other_classes_still_waste_nothing_into_temp_hp():
    """The control: a cure at full on anybody else is still just a cure at full."""
    from rules.sheet import load_pc

    pc = load_pc("fixtures/pc-kesst.json")
    pc.hp = pc.hp_max
    pc.heal(5)
    assert sum(p.amount for p in pc.temp_pools) == 0


def test_the_full_blood_bond_text_is_data_and_the_glossary_serves_it():
    from rules import glossary

    pc = _bender()
    entry = glossary.lookup(glossary.build(pc), "blood bond")
    assert entry["text"].startswith("Your blood is bonded to you")
    assert "Constitution check (DC 10+LVL+CONmod)" in entry["text"]


def test_blood_bending_bab_matches_the_supplied_chart():
    """The user's chart is the standard full progression — +1 per level, iterative
    attacks at 6/11/16 — and the class had been shipped as three_quarter, which the
    document itself never stated. Every one of the twenty rows is checked, because a
    progression is exactly the kind of table that is wrong at one level and looks right
    at the other nineteen."""
    from rules.sheet import from_dict, load_pc, to_dict
    from rules.tables import iterative_attacks

    chart = {1: [1], 2: [2], 3: [3], 4: [4], 5: [5],
             6: [6, 1], 7: [7, 2], 8: [8, 3], 9: [9, 4], 10: [10, 5],
             11: [11, 6, 1], 12: [12, 7, 2], 13: [13, 8, 3], 14: [14, 9, 4],
             15: [15, 10, 5], 16: [16, 11, 6, 1], 17: [17, 12, 7, 2],
             18: [18, 13, 8, 3], 19: [19, 14, 9, 4], 20: [20, 15, 10, 5]}
    for level, want in chart.items():
        d = to_dict(load_pc("fixtures/pc-kesst.json"))
        d["class"] = "blood bending"
        d["level"] = level
        d["ranks"] = {}
        pc = from_dict(d, ref="pc")
        assert iterative_attacks(pc.bab) == want, (level, pc.bab)

"""Authoring a class: the classification, the validator, the scaffolds and the page.

The user's ask was two halves. "Everything about a class needs labeled and classified" is
pinned mechanically here rather than by reading: `test_every_key_blood_bending_uses_is_classified`
walks the real 1,091-line class file and fails on any key `CLASS_SCHEMA` does not name, so
the classification cannot quietly fall behind the data. "A class creation tool" is pinned by
building classes through it and playing them.

The defects these were written against, each of which is a real shape the app has already
been bitten by:

- A class file that loads *partly*. `rules.classes.all_classes` swallows an unreadable file
  and merges a valid-looking one field by field, so a wrong `bab` or a mistyped override is
  a class that quietly stops doing something, with no error anywhere. Every validator test
  below is one of those silences turned into a sentence.
- A path whose abilities never unlock. Tiers gate on the level table granting the literal
  phrase `control blood N<track>`; a class that declares four beautiful paths and never
  grants a track has zero usable abilities and looks fine on the page.
- A level table with a hole in it. `table_at` returns `{}` for the missing level, so every
  effect reading a die column goes inactive at exactly that level and nowhere else.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rules import classbuilder as cb
from rules import classes as classes_mod, creation, leveling
from rules.sheet import ACTOR_RULES, from_dict

BLOOD_BENDING = Path("content/classes/blood-bending.json")


@pytest.fixture(autouse=True)
def _fresh_classes():
    """The class table is cached for the life of the process. A test that writes a class
    and leaves the cache warm hands the next test file a class that does not exist."""
    classes_mod._ALL = None
    yield
    classes_mod._ALL = None


@pytest.fixture
def mine(tmp_path, settings):
    """A homebrew directory belonging to nobody but this test."""
    settings.CAMPAIGN_DIR = str(tmp_path / "campaigns")
    classes_mod._ALL = None
    return tmp_path / "homebrew" / "classes"


def blood_bending() -> dict:
    return json.loads(BLOOD_BENDING.read_text(encoding="utf-8"))


# --- the classification --------------------------------------------------------------

def test_every_key_blood_bending_uses_is_classified():
    """"Everything about a class needs labeled and classified", made mechanical.

    Walks the shipped reference class — 26 top-level keys, 20 level rows, 5 pools, 3
    overrides and 4 paths of 14 keys each — and fails on any key the schema does not name.
    Reading the file and believing it was covered is exactly the check that has been wrong
    before; this one cannot be.
    """
    assert cb.unclassified(blood_bending()) == []


def test_a_key_the_schema_does_not_name_is_reported_with_its_path():
    d = blood_bending()
    d["swagger"] = 3
    d["paths"]["coagulator"]["vibes"] = "moody"
    d["levels"][4]["_a_note"] = "notes are not fields and are never reported"
    assert cb.unclassified(d) == ["swagger", "paths.coagulator.vibes"]


def test_the_schema_names_every_rule_the_engine_can_actually_be_told_to_break():
    """Six rules exist in `sheet.ACTOR_RULES` and a class may claim any of them. A seventh
    added to the engine and not offered here would be a feature no authored class could
    reach, and the failure would be invisible — `overrides_for` would simply never grant
    it."""
    field = next(f for f in cb.registry_fields() if f.name == "overrides")
    rule = next(f for f in field.of if f.name == "rule")
    assert set(rule.choices) == set(ACTOR_RULES)


def test_the_schema_offers_exactly_the_progressions_the_loader_accepts():
    fields = {f.name: f for f in cb.registry_fields()}
    assert set(fields["bab"].choices) == set(classes_mod.BAB)
    saves_help = fields["saves"].help
    for track in classes_mod.SAVE_TRACKS:
        assert track in saves_help, f"{track} is a track the loader accepts and the form " \
                                    f"never mentions"


def test_a_simple_class_touches_nothing_marked_advanced():
    """The other half of the ask: "a simpler class must not have to fill in machinery it
    does not want". The martial scaffold is the proof — it uses no field from an advanced
    section and no field marked advanced."""
    advanced = {f.name for s in cb.CLASS_SCHEMA for f in s.fields
                if s.advanced or f.advanced}
    used = set(cb.scaffold("martial"))
    assert used & advanced == set()
    assert cb.validate_class(cb.scaffold("martial")) == []


def test_a_field_nothing_reads_says_so_rather_than_implying_otherwise():
    """Three class keys are carried by the shipped data and read by nothing at all. Naming
    them with an empty consumer is the honest answer; leaving them out would make an
    authored class lose them on a round trip, and describing them as read would be a lie
    the author only discovers in play."""
    unread = {f.name for f in cb.registry_fields() if not f.consumer}
    assert unread == {"source", "alignment", "starting_wealth"}
    for f in cb.registry_fields():
        assert f.help or f.type in ("table", "paths"), f"{f.name} tells the author nothing"


def test_the_fields_are_registry_fields_so_the_bench_needs_no_special_case():
    from rules.registry import Field

    for f in cb.registry_fields():
        assert isinstance(f, Field)
        assert set(f.as_dict()) >= {"name", "label", "type", "choices", "help", "required"}


# --- the scaffolds ---------------------------------------------------------------------

@pytest.mark.parametrize("kind", sorted(cb.SCAFFOLDS))
def test_every_scaffold_validates_clean(kind):
    """A template that does not validate is a template that teaches the user their first
    edit broke something."""
    assert cb.validate_class(cb.scaffold(kind)) == []


@pytest.mark.parametrize("kind", sorted(cb.SCAFFOLDS))
def test_every_scaffold_has_a_row_for_all_twenty_levels(kind):
    levels = [r["level"] for r in cb.scaffold(kind)["levels"]]
    assert levels == list(range(1, 21))


@pytest.mark.parametrize("kind", sorted(cb.SCAFFOLDS))
def test_every_scaffold_saves_loads_and_makes_a_character(kind, mine):
    """The whole point of a scaffold: it is playable the moment it is saved, without an
    edit, a restart or a second file."""
    entry = cb.scaffold(kind)
    path = cb.save_class(entry)
    assert path.parent == mine

    loaded = classes_mod.get(entry["id"])
    assert loaded["name"] == entry["name"]

    built, problems = creation.build({
        "name": "Scaffold Test", "race": "human", "bonus_ability": "con",
        "class": entry["id"],
        "pronouns": "she/her",
        "abilities": {"str": 12, "dex": 12, "con": 14, "int": 10, "wis": 12, "cha": 10},
        "skills": [], "feats": [],
        "paths": list(entry.get("paths") or {})[:1],
    })
    assert problems == [], problems
    actor = from_dict(built["sheet"])
    assert actor.level == 1
    assert actor.hp_max > 0


def test_a_scaffolded_class_levels_up_and_its_pool_formula_follows(mine):
    """A pool maximum is a formula so that it resizes itself rather than freezing at the
    value it had when the character was 1st level.

    Measured 2026-08-24, and worth writing down because it is not what `level_up` implies:
    it ends with `actor.rebuild_pools() if hasattr(actor, "rebuild_pools")`, and **no such
    method exists on `Actor`** — so the pool does not resize on the level-up itself. It
    resizes on the next `classes.apply`, which runs on every load, so the number is right by
    the time anybody sees the sheet. The two assertions below pin both halves rather than
    the half that reads better.
    """
    entry = cb.scaffold("paths")
    cb.save_class(entry)
    built, problems = creation.build({
        "name": "Storm Test", "race": "human", "bonus_ability": "wis",
        "class": "storm caller",
        "pronouns": "she/her",
        "abilities": {"str": 10, "dex": 14, "con": 12, "int": 10, "wis": 14, "cha": 10},
        "skills": [], "feats": [], "paths": ["gale"],
    })
    assert problems == []
    actor = from_dict(built["sheet"])
    actor.xp = 1_000_000                    # the level gate is XP, and it is not the point
    classes_mod.apply(actor)
    wis = actor.ability_mod("wis")
    assert actor.pool("squall").maximum == 3 + wis          # 3 + wis_mod + floor(1/2)

    for _ in range(4):
        result = leveling.level_up(actor)
        assert result["ok"], result
    assert actor.level == 5
    assert actor.pool("squall").maximum == 3 + wis, \
        "level_up does not resize pools — there is no Actor.rebuild_pools"
    classes_mod.apply(actor)
    assert actor.pool("squall").maximum == 3 + wis + 2      # 3 + wis_mod + floor(5/2)


def test_the_path_scaffold_gates_its_abilities_by_tier(mine):
    """The mechanism the whole exercise turns on: an ability is not yours because the class
    prints it somewhere. Tier 3 is refused at 1st level and granted at 5th, because that is
    where the level table opens the track."""
    cb.save_class(cb.scaffold("paths"))
    built, _ = creation.build({
        "name": "Gale Test", "race": "human", "bonus_ability": "wis",
        "class": "storm caller",
        "pronouns": "she/her",
        "abilities": {"str": 10, "dex": 14, "con": 12, "int": 10, "wis": 14, "cha": 10},
        "skills": [], "feats": [], "paths": ["gale"],
    })
    actor = from_dict(built["sheet"])
    actor.xp = 1_000_000

    path, found, effects = leveling.find_ability(actor, "Cutting Gust")
    assert (path, found) == ("gale", "cutting gust")
    assert effects, "a tier 1 ability is usable at 1st level"
    assert effects[1]["dice"] == "1d6", "its damage came off the class table's own column"

    _, thunder, locked = leveling.find_ability(actor, "Thunderclap")
    assert thunder and locked == [], "tier 3 is not reachable at Control Blood 1"
    assert leveling.tier_needed(actor, "Thunderclap") == 3

    assert leveling.is_passive(actor, "Windstep")
    assert leveling.toggle_key(actor, "Riding the Squall") == "riding the squall"

    for _ in range(4):
        leveling.level_up(actor)
    _, _, unlocked = leveling.find_ability(actor, "Thunderclap")
    assert unlocked, "the track opened at 5th and the ability came with it"
    # 5th level prints 2d6 in the Squall column, and Thunderclap doubles it.
    assert [e.get("dice") for e in unlocked if e.get("from_column")] == ["4d6"]


# --- the validator: one test per class of error ----------------------------------------

def _one(problems, needle):
    found = [p for p in problems if needle in p]
    assert found, f"nothing said {needle!r}; got {problems}"
    return found[0]


def test_an_unknown_bab_progression_is_named_with_the_three_that_exist():
    problems = cb.validate_class({**cb.scaffold("martial"), "bab": "medium"})
    message = _one(problems, "'medium' is not a progression")
    assert "three_quarter" in message and "full is +1 a level" in message


def test_a_path_tier_above_five_says_why_five_is_the_ceiling():
    d = cb.scaffold("paths")
    d["paths"]["gale"]["tiers"]["6"] = ["Hurricane"]
    message = _one(cb.validate_class(d), "tier 6 is outside 1-5")
    assert "could ever be reached" in message
    assert "move these abilities to a tier from 1 to 5" in message


def test_an_ability_in_resolves_that_no_tier_lists_is_refused():
    """It would show on no tier, so no character could ever have it — and nothing anywhere
    would say so."""
    d = cb.scaffold("paths")
    d["paths"]["gale"]["resolves"]["Hurricane"] = "Hurricane"
    message = _one(cb.validate_class(d), "'Hurricane' is resolved but no tier lists it")
    assert "Add it to a tier, or remove the entry" in message


def test_a_tier_ability_with_nothing_to_resolve_to_is_refused():
    d = cb.scaffold("paths")
    del d["paths"]["gale"]["resolves"]["Cutting Gust"]
    message = _one(cb.validate_class(d), "nothing says what 'Cutting Gust' resolves to")
    assert "shows no text and runs no effects" in message
    assert "list it under Core" in message


def test_a_toggle_naming_an_ability_that_does_not_exist_is_refused():
    d = cb.scaffold("paths")
    d["paths"]["gale"]["toggles"]["Riding the Hurricane"] = "hurricane"
    message = _one(cb.validate_class(d), "'Riding the Hurricane' is not an ability")
    assert "Add it to a tier, or remove the toggle" in message


def test_a_toggle_with_no_condition_name_is_refused():
    d = cb.scaffold("paths")
    d["paths"]["gale"]["toggles"]["Riding the Squall"] = ""
    assert _one(cb.validate_class(d), "a toggle needs a condition name")


def test_a_passive_that_is_on_no_tier_is_refused():
    d = cb.scaffold("paths")
    d["paths"]["gale"]["passive"] = ["Windstep", "Standing Still"]
    assert _one(cb.validate_class(d), "'Standing Still' is not listed on any tier")


def test_an_effect_that_fails_the_effect_vocabulary_says_which_field_is_missing():
    d = cb.scaffold("paths")
    d["paths"]["gale"]["effects"]["Cutting Gust"] = [
        {"type": "damage", "damage_type": "untyped", "lethality": "lethal"}]
    assert _one(cb.validate_class(d), "Damage needs how much")


def test_an_effect_problem_carries_the_fix_where_the_field_states_one():
    """`effectspec` names the fault and stops, which is right for a form that shows the
    hint beside the input and wrong for a validator whose whole output is sentences. The
    hint is appended from the field itself rather than restated, so the two cannot drift."""
    d = cb.scaffold("paths")
    d["paths"]["gale"]["effects"]["Cutting Gust"] = [{"type": "heal"}]
    message = _one(cb.validate_class(d), "Heal needs how much")
    assert "1d4, 2d6+2, 10." in message


def test_an_unknown_effect_type_lists_the_ones_that_exist():
    d = cb.scaffold("paths")
    d["paths"]["gale"]["effects"]["Cutting Gust"] = [{"type": "vibes", "target": "x"}]
    assert _one(cb.validate_class(d), "no effect type 'vibes'")


def test_an_unknown_engine_op_lists_the_two_that_exist():
    """`engine_op` is not an effectspec type at all — it is the two scene operations
    `_op_use_ability` executes by name. A third invented in a class file would be silently
    narrated instead of run."""
    d = cb.scaffold("paths")
    d["paths"]["bulwark"]["effects"]["Rolling Thunder"] = [
        {"type": "engine_op", "op": "summon_storm"}]
    message = _one(cb.validate_class(d), "no engine op")
    assert "blood_pool" in message and "spend_pools" in message


def test_an_effect_reading_a_column_the_table_does_not_print_is_refused():
    """`dice_from` reads a die off the class's own level table. Naming a column that is not
    there does not fail — `resolve_effect` marks the effect inactive, and the ability
    silently does nothing for the rest of the campaign."""
    d = cb.scaffold("paths")
    d["paths"]["gale"]["effects"]["Cutting Gust"][1]["dice_from"] = "thunder"
    message = _one(cb.validate_class(d), "no column called 'thunder'")
    assert "squall" in message


def test_a_pool_formula_that_will_not_parse_is_refused_with_what_it_may_say():
    d = cb.scaffold("paths")
    d["pools"][0]["max"] = "3 + charisma_modifier"
    message = _one(cb.validate_class(d), "nothing called 'charisma_modifier'")
    assert "control_blood" in message and "floor/ceil/min/max" in message


def test_a_pool_refresh_the_engine_does_not_have_is_refused():
    d = cb.scaffold("paths")
    d["pools"][0]["refresh"] = "dawn"
    assert _one(cb.validate_class(d), "'dawn' is not a refresh")


def test_a_level_table_with_a_gap_names_the_missing_levels():
    """A missing row is the least visible error a class table can have: `table_at` answers
    `{}`, so the class grants nothing and prints no dice at that level and nowhere says
    why."""
    d = cb.scaffold("martial")
    d["levels"] = [r for r in d["levels"] if r["level"] not in (4, 7)]
    message = _one(cb.validate_class(d), "no row for levels 4, 7")
    assert "empty grants list" in message


def test_a_die_column_missing_at_some_levels_is_reported():
    d = cb.scaffold("paths")
    del d["levels"][2]["squall"]
    message = _one(cb.validate_class(d), "the 'squall' column is empty at level 3")
    assert "goes inactive" in message


def test_two_rows_for_one_level_are_refused():
    d = cb.scaffold("martial")
    d["levels"].append({"level": 3, "grants": ["something else"]})
    assert _one(cb.validate_class(d), "level 3 has two rows")


def test_an_override_naming_a_rule_the_engine_never_asks_about_is_refused():
    """`classes.apply` collects an unknown rule instead of setting it, so the only symptom
    is a class feature that never happens. The validator is where that becomes visible."""
    d = cb.scaffold("paths")
    d["overrides"][0]["rule"] = "temp_hp_stacks"
    message = _one(cb.validate_class(d), "'temp_hp_stacks' is not a rule")
    assert "temp_hp.stacks" in message


def test_a_path_id_with_a_capital_in_it_is_refused():
    """`path_detail` looks a path up lower-cased, so a key with a capital is a path the
    engine can never find and a character can never take."""
    d = cb.scaffold("paths")
    d["paths"]["Gale"] = d["paths"].pop("gale")
    message = _one(cb.validate_class(d), "a path id must be lower case")
    assert "'gale'" in message


def test_paths_with_no_track_on_the_level_table_are_refused():
    """The one class-specific string left in a class-agnostic engine: tiers are counted off
    grants matching `control blood N<track>`. Without them every ability stays locked at
    tier 0 forever, and the class tab looks perfectly healthy."""
    d = cb.scaffold("paths")
    for row in d["levels"]:
        row["grants"] = [g for g in row["grants"] if "control blood" not in g]
    message = _one(cb.validate_class(d), "nothing on the level table opens a path")
    assert "control blood 1a" in message
    assert "matched literally" in message


def test_a_tier_higher_than_the_table_grants_is_reported():
    """Both tracks count: the a-track opens the first path and the b-track the second, so
    a tier is unreachable only when *neither* ever grants it."""
    d = cb.scaffold("paths")
    for row in d["levels"]:
        row["grants"] = [g for g in row["grants"] if "control blood 3" not in g]
    assert _one(cb.validate_class(d), "tier 3 is higher than any 'control blood N'")


def test_a_class_skill_the_sheet_never_heard_of_is_reported():
    d = {**cb.scaffold("martial"), "class_skills": ["climb", "haggling"]}
    message = _one(cb.validate_class(d), "'haggling' is not a skill")
    assert "knowledge (religion)" in message


def test_a_casting_block_with_an_unknown_progression_is_refused():
    from rules import casting

    d = cb.scaffold("spellcaster")
    d["casting"]["progression"] = "half_caster"
    message = _one(cb.validate_class(d), "'half_caster' is not a slot table")
    for known in casting.PROGRESSIONS:
        assert known in message


def test_an_empty_class_asks_for_the_five_things_a_class_cannot_do_without():
    problems = cb.validate_class({})
    for needle in ("id:", "name:", "bab:", "hit_die:", "skill_ranks:", "levels:"):
        assert any(p.startswith(needle) for p in problems), needle


# --- the reference class, measured -------------------------------------------------------

def test_blood_bending_reports_exactly_its_nine_known_gaps():
    """Measured 2026-08-24 against the shipped file: nine problems, and every one of them
    is real rather than a false positive from the class layer's own extensions.

    Eight are `save_gate` effects converted from the author's sentences that carry a note
    reading "DC 10+12LVL+CONmod" and no `dc` field — the DC is in prose the engine cannot
    read. The ninth is Coagulated Plate's `bonus_type: "armor"`, which is not in
    `effectspec.VOCAB` at all (it lists "natural armour" and "shield", and no plain armour
    bonus). Both are recorded in docs/class-creation.md; neither is invented by this test.

    The ninth was Coagulated Plate's `bonus_type: "armor"`, which failed because the
    effect vocabulary had no plain armour bonus at all — only `natural armour`, which
    is a different bonus that stacks with it. Adding `armour` fixed the class and
    mage armor's +4 in the same stroke; both had been written as something else.

    The other fifteen problems a naive run of `effectspec.validate` reports on this file
    are *not* errors — nine `dice_from`, two tiered or formula amounts and four
    `engine_op`s — which is the reason `validate_effect` exists.
    """
    problems = cb.validate_class(blood_bending())
    assert len(problems) == 8, problems
    # All eight are the same defect: a save whose DC is written in a note rather than
    # in the field the engine reads, so nothing rolls against it.
    assert sum("Saving throw needs dc" in p for p in problems) == 8


def test_the_class_layer_extensions_are_not_reported_as_missing_fields():
    """The nine `dice_from` damage effects, the tiered DR and the formula-driven AC bonus
    all leave a field empty that `effectspec` requires — because `resolve_effect` fills it
    in from the class table, the tier or the sheet. Reported as errors, they would bury the
    real problems in fifteen false ones."""
    from rules import effectspec

    naive = [p for path in blood_bending()["paths"].values()
             for ability, specs in (path.get("effects") or {}).items()
             for spec in specs
             for p in effectspec.validate(spec, ability)]
    assert len(naive) == 23
    assert len(cb.validate_class(blood_bending())) == 8


# --- the page ------------------------------------------------------------------------------

def test_the_builder_page_loads_and_carries_the_whole_schema(client):
    res = client.get("/homebrew/classes/")
    assert res.status_code == 200
    body = res.content.decode("utf-8")
    for section in cb.CLASS_SCHEMA:
        assert section.title in body
    assert "control blood" in body


def test_the_page_offers_every_scaffold(client):
    res = client.get("/api/classes/catalogue")
    assert {s["id"] for s in res.json()["scaffolds"]} == set(cb.SCAFFOLDS)


def test_a_scaffold_can_be_fetched_and_a_bad_one_404s(client):
    assert client.get("/api/classes/scaffold/paths").json()["class"]["id"] == "storm caller"
    assert client.get("/api/classes/scaffold/nonsense").status_code == 404


def test_a_shipped_class_opens_for_editing(client):
    """A shipped entry that cannot be opened is a table nobody can correct — the failure
    `registry.find` was written to end, and the same rule applies to classes."""
    data = client.get("/api/classes/open/blood bending").json()
    assert data["class"]["name"] == "Blood Bending"
    assert len(data["class"]["paths"]) == 4
    assert len(data["problems"]) == 8


def test_saving_an_invalid_class_writes_nothing_and_says_why(client, mine):
    res = client.post("/api/classes/save",
                      data=json.dumps({"class": {"id": "broken", "name": "Broken"}}),
                      content_type="application/json")
    assert res.status_code == 400
    assert any("bab:" in p for p in res.json()["problems"])
    assert not (mine / "broken.json").exists()


def test_saving_a_valid_class_makes_it_playable_at_once(client, mine):
    """The cache is the trap: `all_classes` holds for the life of the process, so a class
    saved through the page was invisible until the app was restarted — which reads exactly
    like a save that did not work."""
    entry = cb.scaffold("martial")
    res = client.post("/api/classes/save", data=json.dumps({"class": entry}),
                      content_type="application/json")
    assert res.status_code == 200, res.content
    assert (mine / "bulwark.json").exists()
    assert classes_mod.get("bulwark")["name"] == "Bulwark"
    assert "bulwark" in {c["id"] for c in creation.options()["classes"]}


def test_the_saved_file_is_the_file_the_loader_reads(mine):
    """One file per class in the user's own folder, layered over what ships — the registry's
    rule, so a corrected table in a later build is never shadowed by a stale copy."""
    cb.save_class(cb.scaffold("spellcaster"))
    written = json.loads((mine / "hedge mage.json").read_text(encoding="utf-8"))
    assert written["casting"]["ability"] == "int"
    assert classes_mod.get("hedge mage")["casting"]["progression"] == "full"


def test_live_validation_answers_two_hundred_even_when_the_class_is_wrong(client):
    """A form being wrong is not a request being wrong. A 400 here would show in the
    browser console on every keystroke of a half-typed class."""
    res = client.post("/api/classes/validate",
                      data=json.dumps({"class": {"id": "half typed"}}),
                      content_type="application/json")
    assert res.status_code == 200
    assert res.json()["problems"]


# --- the page wears the app's own clothes ---------------------------------------------

TEMPLATE = Path("play/templates/play/classbuilder.html")
CRAFT = Path("play/templates/play/craft.html")


def _root_block(path: Path) -> dict[str, str]:
    """The `:root` custom properties a template declares, as a dict."""
    import re

    text = path.read_text(encoding="utf-8")
    block = re.search(r":root\s*\{(.*?)\}", text, re.S).group(1)
    return {m.group(1): m.group(2).strip()
            for m in re.finditer(r"(--[a-z-]+)\s*:\s*([^;]+);", block)}


def test_the_builder_declares_the_same_palette_as_the_craft_bench():
    """The user's words: "its UI need to be the same style as everything else". Pinned as a
    value comparison rather than a screenshot, because the failure this prevents is drift —
    a palette corrected on one page and left stale on another, which is the shape CLAUDE.md
    names as the reason a fix ships from the copy nobody looked at.
    """
    mine, craft = _root_block(TEMPLATE), _root_block(CRAFT)
    shared = set(mine) & set(craft)
    assert len(shared) >= 12, f"only {len(shared)} tokens in common with the craft bench"
    for token in sorted(shared):
        assert mine[token] == craft[token], \
            f"{token} is {mine[token]} here and {craft[token]} on the craft bench"


def test_the_builder_uses_the_shipped_leather_and_the_shipped_face():
    """Reuse of the app's vocabulary, not a parallel one: the same two background images,
    the same display face, loaded through `{% static %}` so the packaged build finds them.
    """
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "{% load static %}" in text
    for asset in ("img/grimoire-leather.jpg", "img/card-leather.jpg",
                  "fonts/Cinzel-Regular.woff2"):
        assert asset in text, f"{asset} is what the rest of the app is made of"
    assert 'font-variant: small-caps' in text


def test_the_validation_banner_uses_the_benchs_alarm_and_confirm_colours():
    """A refusal has to read the same wherever it comes from. The banner is the alarm
    colour the forge's `.problems` box uses, and the confirm state is the brew green the
    shelf uses for a thing that worked."""
    text = TEMPLATE.read_text(encoding="utf-8")
    import re

    banner = re.search(r"#problems \{(.*?)\}", text, re.S).group(1)
    clean = re.search(r"#problems\.clean \{(.*?)\}", text, re.S).group(1)
    assert "var(--alarm)" in banner and "110,31,31" in banner
    assert "var(--brew)" in clean


def test_the_restyle_did_not_drop_the_two_things_that_are_the_feature(client):
    """Both halves of "everything labeled" are rendered by the page itself, so a restyle is
    exactly where they would be lost without a test noticing: the line naming which engine
    mechanism reads a field, and the admission where none does.

    The live validation is pinned by its two halves as well — the per-section badge count
    and the click-to-jump handler that reads the section off the message's dotted path.
    """
    body = client.get("/homebrew/classes/").content.decode("utf-8")
    assert '"read by " + f.consumer' in body
    assert "recorded only — no engine mechanism reads this" in body
    assert 'class="badge"' in body
    assert "SECTION_OF[rootOf(" in body

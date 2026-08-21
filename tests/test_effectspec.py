"""The authored-effect schema, and the catalogue the editor builds its forms from.

One idea holds it together: effects are grouped by **the fields needed to build them**,
not by what they are about. +2 Climb and +2 Strength are the same form with a different
dropdown behind `target`; a poison and a fireball are the same form because both need a
save, a DC and dice. That is what makes one generic builder possible instead of twenty
hand-written ones.

The catalogue is the single definition both sides read, so a form cannot drift from what
the engine expects — and these tests assert that property directly.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from rules import effectspec as es
from rules.sheet import load_pc


# --- the catalogue ------------------------------------------------------------------------

def test_the_catalogue_covers_what_the_corpus_needs():
    """Measured across the 161 shipped ingredients: saves, conditions, modifiers, healing,
    ability damage, resistance, immunity, temporary hit points and fast healing."""
    ids = {t.id for c in es.CATEGORIES for t in c.types}
    for needed in ("save_gate", "apply_condition", "remove_condition", "skill_mod",
                   "ability_mod", "heal", "damage", "ability_damage", "resistance",
                   "immunity", "temp_hp", "fast_healing"):
        assert needed in ids


def test_every_type_declares_its_own_fields():
    """The form generator reads these. A type with no fields would render an empty form
    and save an empty effect."""
    for c in es.CATEGORIES:
        for t in c.types:
            assert t.fields, t.id
            assert t.example


def test_every_dropdown_points_at_a_real_vocabulary():
    """A `choice` field naming a list that does not exist renders an empty dropdown, which
    looks like a bug in the data rather than in the schema."""
    for c in es.CATEGORIES:
        for t in c.types:
            for f in t.fields + es.COMMON:
                if f.kind == "choice":
                    assert f.vocab in es.VOCAB, (t.id, f.id)


def test_modifiers_share_one_form_and_differ_only_in_the_target():
    """The whole reason the taxonomy is grouped this way."""
    shapes = {}
    for t in next(c for c in es.CATEGORIES if c.id == "modifier").types:
        shapes[t.id] = [f.id for f in t.fields]
    assert len(set(map(tuple, shapes.values()))) == 1
    assert all(s == ["amount", "bonus_type", "target"] for s in shapes.values())


def test_the_catalogue_serialises_for_the_editor():
    d = es.catalogue()
    assert d["categories"] and d["vocab"]
    json.dumps(d)                       # the page embeds it; it has to be JSON


def test_a_type_the_engine_cannot_run_says_why():
    """Authoring one is allowed and marked, never silently accepted: an effect that looks
    authored and does nothing is what docs/homebrew-rules.md §1 exists to prevent."""
    for c in es.CATEGORIES:
        for t in c.types:
            if not t.engine:
                assert t.blocked, t.id
    assert not es.find("spell_effect")[1].engine
    assert not es.find("permission")[1].engine


# --- validation ------------------------------------------------------------------------------

def test_a_complete_effect_validates():
    assert es.validate({"type": "skill_mod", "amount": 2, "bonus_type": "alchemical",
                        "target": "climb"}) == []


def test_every_problem_is_reported_at_once():
    """A builder that reports them one at a time is one nobody finishes a complex effect
    in."""
    problems = es.validate({"type": "skill_mod", "amount": "two", "target": "flying"})
    assert len(problems) == 3
    assert any("must be a number" in p for p in problems)
    assert any("needs bonus type" in p for p in problems)
    assert any("not a skill" in p for p in problems)


def test_a_rejected_choice_lists_the_ones_that_exist():
    problems = es.validate({"type": "ability_mod", "amount": 2,
                            "bonus_type": "alchemical", "target": "luck"})
    assert any("str" in p and "cha" in p for p in problems)


def test_an_unknown_type_names_the_ones_that_exist():
    problems = es.validate({"type": "teleport"})
    assert len(problems) == 1 and "save_gate" in problems[0]


@pytest.mark.parametrize("dice,ok", [
    ("1d4", True), ("2d6+2", True), ("10", True), ("d20", True),
    ("a bit", False), ("1d", False), ("", False),
])
def test_dice_are_dice(dice, ok):
    problems = es.validate({"type": "heal", "dice": dice})
    assert (problems == []) is ok


def test_a_use_limit_needs_a_count():
    assert es.validate({"type": "heal", "dice": "1d4", "uses": "per_day"})
    assert es.validate({"type": "heal", "dice": "1d4", "uses": "per_day",
                        "uses_count": 3}) == []


def test_nested_branches_are_validated_and_named():
    """A malformed effect three levels down has to be findable."""
    problems = es.validate({
        "type": "save_gate", "target": "fort", "dc": 18,
        "on_failure": [{"type": "ability_damage", "target": "con"}]})
    assert len(problems) == 1
    assert "if they fail 1" in problems[0]


# --- rendering ---------------------------------------------------------------------------------

@pytest.mark.parametrize("spec,line", [
    ({"type": "skill_mod", "amount": 2, "bonus_type": "alchemical", "target": "climb"},
     "+2 Climb"),
    ({"type": "ability_mod", "amount": -2, "bonus_type": "untyped", "target": "con"},
     "-2 Constitution"),
    ({"type": "heal", "dice": "1d4"}, "Heals 1d4 hit points"),
    ({"type": "damage", "dice": "1d6", "damage_type": "fire", "lethality": "lethal"},
     "1d6 fire damage"),
    ({"type": "temp_hp", "dice": "10", "duration": {"amount": 8, "unit": "hour"}},
     "10 temporary hit points for 8 hours"),
    ({"type": "fast_healing", "amount": 2}, "Fast healing 2"),
    ({"type": "remove_condition", "target": "fatigued"}, "Ends fatigued"),
    ({"type": "resistance", "target": "fire", "amount": 10}, "Resist fire 10"),
    ({"type": "damage_reduction", "amount": 3}, "DR 3/—"),
    ({"type": "speed", "target": "land", "amount": 20}, "+20 ft land speed"),
])
def test_an_authored_effect_reads_like_a_card_line(spec, line):
    """The same voice `rules/effects.py` produces from prose, so a player cannot tell
    which items were authored and which were read out of a description."""
    assert es.render(spec) == line


def test_a_duration_of_one_is_not_pluralised():
    assert es.render({"type": "heal", "dice": "1d4",
                      "duration": {"amount": 1, "unit": "hour"}}).endswith("for 1 hour")


def test_a_use_limit_shows_on_the_line():
    assert es.render({"type": "heal", "dice": "1d10", "uses": "per_day",
                      "uses_count": 1}).endswith("(1× per day)")


def test_a_save_gate_reads_as_a_fork():
    """The Skull Orchid poison: the shape the whole schema exists for."""
    line = es.render({
        "type": "save_gate", "target": "fort", "dc": "10 + level/2 + con_mod",
        "on_failure": [{"type": "ability_damage", "target": "con", "dice": "2d6"},
                       {"type": "apply_condition", "target": "nauseated",
                        "duration": {"amount": "1d4", "unit": "round"}}],
        "on_success": [{"type": "ability_damage", "target": "con", "dice": "1"}]})
    assert line == ("Fortitude DC 10 + level/2 + con_mod · "
                    "fail: 2d6 Constitution damage, Causes nauseated for 1d4 rounds · "
                    "save: 1 Constitution damage")


# --- through the app ---------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path):
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        yield Client()
        cm._LIVE.clear()


def test_the_editor_fetches_one_catalogue(client):
    """Served rather than duplicated in the page: a new effect type is one entry in
    rules/effectspec.py and its form appears without a line of template changing."""
    d = client.get("/api/effects/catalogue").json()
    assert len(d["categories"]) == len(es.CATEGORIES)
    assert d["vocab"]["ability"] and d["vocab"]["condition"]


def test_preview_validates_and_renders_together(client):
    d = client.post("/api/effects/preview", data=json.dumps({"effects": [
        {"type": "skill_mod", "amount": 2, "bonus_type": "alchemical", "target": "climb"},
        {"type": "heal", "dice": "nope"},
    ]}), content_type="application/json").json()
    assert d["effects"][0]["line"] == "+2 Climb" and not d["effects"][0]["problems"]
    assert d["effects"][1]["problems"]


def test_saving_a_consumable_writes_structured_data(client):
    from play import homebrew

    r = client.post("/api/consumables", data=json.dumps({
        "name": "Heart Fire", "kind": "poison",
        "description": "Distilled from skull orchid seeds.",
        "effects": [{"type": "save_gate", "target": "fort", "dc": 20,
                     "on_failure": [{"type": "ability_damage", "target": "con",
                                     "dice": "2d6"}]}],
    }), content_type="application/json")
    assert r.status_code == 200

    saved = json.loads((homebrew.folder("consumables") / "heart-fire.json")
                       .read_text(encoding="utf-8"))
    assert saved["effects"][0]["on_failure"][0]["dice"] == "2d6"
    assert homebrew.get("consumables").yours == 1


def test_a_malformed_effect_is_refused_rather_than_written(client):
    """A file that cannot be read back is worse than a form the user has to finish."""
    from play import homebrew

    r = client.post("/api/consumables", data=json.dumps({
        "name": "Broken", "effects": [{"type": "heal", "dice": "some"}]}),
        content_type="application/json")
    assert r.status_code == 400
    assert not list(homebrew.folder("consumables").glob("*.json"))


def test_a_nameless_thing_is_refused(client):
    r = client.post("/api/consumables", data=json.dumps({"effects": []}),
                    content_type="application/json")
    assert r.status_code == 400


def test_the_bench_offers_the_builder(client):
    d = client.get("/api/bench/consumables").json()
    assert d["bench"]["builder"] == "effects"
    assert d["bench"]["shipped"] == 0

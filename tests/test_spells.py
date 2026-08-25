"""The spell list, its descriptors, its class lists, the filters over them — and the
structured half that makes a spell authorable and executable rather than only readable.

Two sources were offered for this. A JSON dump of 2,827 spells had the canonical
descriptors stripped — `[fire]` and the rest survived in four stray brackets out of nearly
three thousand — so tagging from it would have meant deriving what Paizo had already
stated. The Spell Codex spreadsheet carries all 28 descriptors as columns, subschool
separately, and a level column per class, so those are read rather than guessed.

The distinction those tests defend: a **descriptor** is a rules fact with mechanical
consequences, and a **tag** is ours, for finding things.

The second half of this file defends a different line, drawn in `rules/spells.py`: what is
a *re-reading of a fact the corpus already states* is derived at load and never stored, and
what is a *machine's guess at English prose* is stored in `content/spells/spells-mechanics.json`
and flagged. 354 of 3,040 carry effects; the other 2,686 remain prose, which is the honest
number and the one these tests pin.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from rules import casting, effectspec, registry, spells
from rules.sheet import from_dict as sheet_from_dict, load_pc, to_dict


@pytest.fixture
def client(tmp_path):
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        yield Client()
        cm._LIVE.clear()


@pytest.fixture
def fresh_shelf():
    """Force the next `all_spells()` to re-read from disk, and put it back afterwards.

    The shelf is cached in a module global, so a test that writes a homebrew file and then
    asks for a spell gets the shelf the previous test loaded. That is not a hypothetical:
    it is why the overlay test below has to exist at all.
    """
    before = spells._ALL
    spells._ALL = None
    yield
    spells._ALL = before


# --- what was imported ---------------------------------------------------------------------

def test_the_codex_loaded():
    shelf = spells.all_spells()
    assert len(shelf) > 3000
    for known in ("fireball", "cure-light-wounds", "magic-missile", "teleport"):
        assert known in shelf, known


def test_a_spell_carries_the_facts_a_table_needs():
    fb = spells.get("fireball")
    assert fb.school == "evocation"
    assert "fire" in fb.descriptors
    assert fb.lists["wizard"] == 3
    assert fb.saving_throw and fb.range and fb.duration
    assert fb.source


def test_descriptors_are_read_not_derived():
    """A descriptor changes what a spell does — a [fire] spell is stopped by fire
    immunity — so guessing one is worse than having none. These come from the Codex's
    own columns."""
    assert "fire" in spells.get("fireball").descriptors
    assert "mind-affecting" in spells.get("charm-person").descriptors
    # And a spell about fire that carries no descriptor keeps none rather than gaining one
    # from its prose.
    assert all(isinstance(s.descriptors, list) for s in spells.all_spells().values())


def test_spells_sit_on_more_than_one_list():
    """2,887 of 3,040 do, which is why `lists` maps class to level rather than holding a
    single number."""
    many = [s for s in spells.all_spells().values() if len(s.lists) > 1]
    assert len(many) > 2000

    fb = spells.get("fireball")
    assert fb.lists["wizard"] == fb.lists["sorcerer"] == 3


def test_a_spell_can_sit_at_different_levels_on_different_lists():
    """The reason a single level would have been wrong."""
    varied = [s for s in spells.all_spells().values() if len(set(s.lists.values())) > 1]
    assert varied


def test_every_spell_has_at_least_one_tag():
    """`utility` is the honest catch-all rather than an empty list, so a filter on tags
    never silently hides a spell."""
    for s in spells.all_spells().values():
        assert s.tags, s.id


def test_tags_are_ours_and_say_so():
    note = spells.meta().get("note", "")
    assert "derived" in note.lower() or "ours" in note.lower()
    for tag in ("dot", "buff", "control"):
        assert tag in spells.TAG_NOTES


def test_the_dot_tag_means_repeating_damage():
    """The request named it: damage over time, not damage that lands once."""
    burning = spells.get("burning-gaze")
    assert "dot" in burning.tags
    assert "dot" not in spells.get("magic-missile").tags


# --- filtering -----------------------------------------------------------------------------

def test_filters_narrow_together():
    fire_aoe = spells.search(descriptor="fire", tag="aoe", klass="wizard")
    assert fire_aoe
    for s in fire_aoe:
        assert "fire" in s.descriptors and "aoe" in s.tags and "wizard" in s.lists


def test_filtering_by_class_and_level():
    third = spells.search(klass="wizard", level=3, limit=500)
    assert third
    assert all(s.lists["wizard"] == 3 for s in third)


def test_level_alone_looks_at_every_list():
    """Without a class, "level 1" means level 1 to somebody."""
    firsts = spells.search(level=1, limit=500)
    assert all(1 in s.lists.values() for s in firsts)


def test_searching_text_looks_at_the_description_too():
    assert any(s.id == "fireball" for s in spells.search(text="fireball"))
    assert spells.search(text="acid arrow")


def test_results_come_back_lowest_level_first():
    found = spells.search(descriptor="fire", limit=50)
    levels = [s.min_level for s in found if s.min_level is not None]
    assert levels == sorted(levels)


def test_a_filter_that_matches_nothing_is_empty_not_an_error():
    assert spells.search(descriptor="fire", tag="healing", klass="paladin",
                         level=9) == []


def test_the_vocabularies_are_counted():
    """A dropdown that shows a count tells you before you click that an option is empty."""
    v = spells.vocabularies()
    assert v["descriptors"]["fire"] > 50
    assert v["classes"]["wizard"] > 1000
    assert set(v["tags"]) <= set(spells.TAG_NOTES) | set(v["tags"])


def test_a_domain_is_searchable_the_way_a_class_is():
    """Before `level_available` unified them, a cleric with the Fire domain had no way to
    ask what their domain granted: `search(klass=...)` looked only at `lists`, and the 452
    domain columns in the corpus were read by nothing."""
    found = spells.search(klass="fire", level=3, limit=500)
    assert any(s.id == "fireball" for s in found)


# --- Fireball, against the tag list the request was written in --------------------------------

def test_fireball_answers_every_tag_in_the_request():
    """The worked example, field by field.

    The request wrote it as `{SCHOOL : evocation} {ELEMENT : fire} {SPELLBOOK :
    sorcerer/wizard} ... [Damage] : 1d6/caster_lvl`. Every one of those is a value on the
    loaded spell here, and this test is the mapping made executable: if the schema drifts
    from the notation the user asked for, this fails and names which tag.
    """
    fb = spells.get("fireball")
    assert fb.school == "evocation"                       # {SCHOOL : evocation}
    assert fb.element == "fire"                           # {ELEMENT : fire}
    assert "sorcerer/wizard" in fb.spellbooks             # {SPELLBOOK : sorcerer/wizard}
    assert fb.casting_time == "standard action"           # {Casting Time : 1_standard action}
    assert fb.components == ["V", "S", "M"]               # {Components : V, S, M}
    assert fb.range_value["kind"] == "long"               # [Range] : long
    assert fb.area_value == {"shape": "spread", "radius": 20, "unit": "feet"}
    assert fb.duration == "instantaneous"                 # [Duration] : instantaneous
    assert (fb.save, fb.save_effect) == ("ref", "half")   # [Saving Throw] : Reflex half
    assert fb.sr is True                                  # [Spell Resistance] : yes
    assert fb.scaling["die"] == 6 and fb.scaling["dice_per"] == 1
    assert fb.scaling["per_levels"] == 1                  # [Damage] : 1d6/caster_lvl
    assert fb.scaling["cap_dice"] == 10                   # ...maximum 10d6
    assert fb.scaling["damage_type"] == "fire"


def test_fireball_is_granted_by_a_domain_a_bloodline_and_a_patron_at_third():
    """The request's LEVEL_AVAILABLE, unified: `{sorcerer/wizard : 3}; {{Domain : fire} :
    3}; {{Bloodline : efreeti} : 3}`.

    The corpus prints those three as "Fire (3)", "Efreeti (7)" and "Elements (6)", and the
    numbers do not mean the same thing — a domain's is the spell level, a bloodline's is the
    sorcerer level the bonus spell arrives at, a patron's is the witch level. Reading all
    three as spell levels would have made fireball a 7th-level bloodline spell.
    """
    by_via = {(g["via"], g["name"]): g for g in spells.get("fireball").level_available}
    assert by_via[("class", "wizard")]["level"] == 3
    assert by_via[("class", "sorcerer")]["level"] == 3
    assert by_via[("domain", "fire")]["level"] == 3
    assert by_via[("bloodline", "efreeti")]["level"] == 3
    assert by_via[("bloodline", "efreeti")]["at"] == 7
    assert by_via[("patron", "elements")]["level"] == 3
    assert by_via[("patron", "elements")]["at"] == 6


def test_fireball_rolls_five_dice_at_five_and_ten_at_ten_and_never_eleven():
    """`1d6/caster_lvl (maximum 10d6)` as a value rather than a sentence. The cap is part
    of the formula: a 20th-level wizard's fireball is 10d6, and a version of this that
    multiplied by caster level and stopped there would have rolled 20d6."""
    fb = spells.get("fireball")
    assert spells.scaling_dice(fb, 1) == "1d6"
    assert spells.scaling_dice(fb, 5) == "5d6"
    assert spells.scaling_dice(fb, 9) == "9d6"
    assert spells.scaling_dice(fb, 10) == "10d6"
    assert spells.scaling_dice(fb, 15) == "10d6"
    assert spells.scaling_dice(fb, 20) == "10d6"


def test_fireballs_effects_arrive_scaled_and_halved_on_a_save():
    """What the engine has to be handed. The stored effect carries `1d6` because
    `effectspec.validate` demands the dice field *be* dice and "1d6/level" is not; the
    formula lives once on the spell and `effects_at` is the only place it is applied."""
    fb = spells.get("fireball")
    gate = spells.effects_at(fb, 10)[0]
    assert gate["type"] == "save_gate" and gate["target"] == "ref"
    assert gate["on_failure"][0]["dice"] == "10d6"
    assert gate["on_failure"][0]["damage_type"] == "fire"
    # Half the dice, not half a rolled total: the schema cannot say "roll and halve", and
    # the two have the same mean, floor and ceiling. docs/spells.md says the engine should
    # prefer halving the roll it already has.
    assert gate["on_success"][0]["dice"] == "5d6"
    # And the stored form is untouched by having been read at level 10.
    assert fb.effects[0]["on_failure"][0]["dice"] == "1d6"


def test_the_long_range_band_is_a_distance_rather_than_a_sentence():
    """`long (400 feet + 40 feet/level)` was a string nothing could measure. Close range
    rounds *down* to the whole increment — 25 + 5×(5//2) = 35 feet at caster level 5, not
    37 — which is why the band carries `every` rather than feet-per-level."""
    assert spells.range_feet(spells.get("fireball"), 10) == 800
    assert spells.range_feet(spells.get("charm-person"), 5) == 35      # close
    assert spells.range_feet(spells.get("cure-light-wounds"), 9) == 0  # touch
    assert spells.range_feet(spells.get("mage-armor"), 9) == 0         # touch


# --- the conversion, honestly counted ----------------------------------------------------------

def test_every_converted_effect_passes_the_schema():
    """The whole corpus through `effectspec.validate`, with the offenders named.

    A conversion that produces specs the engine will not hold is worse than no conversion:
    it looks authored, saves without complaint and does nothing. Measured at zero invalid
    out of 354 spells carrying effects.
    """
    bad: list[str] = []
    for s in spells.all_spells().values():
        for i, spec in enumerate(s.effects or ()):
            bad.extend(f"{s.id} effect {i + 1}: {p}"
                       for p in effectspec.validate(spec, s.id))
    assert not bad, "invalid converted specs:\n" + "\n".join(bad[:40])


def test_the_conversion_covers_what_it_claims_and_no_more():
    """354 of 3,040. The number is in the test because a coverage claim in a document ages
    into a lie, and because a change that silently converts three hundred more spells is a
    change somebody should have to look at.

    2,686 are left as prose on purpose. Anything whose formula the patterns could not read
    with certainty stays English rather than becoming a confident wrong number — the single
    failure mode CLAUDE.md names most.

    It was 385 until `_op_cast` started rolling these numbers instead of printing them.
    Executing the corpus found 31 formulas that a spell prints but does not deal by being
    cast — teleport's mishap, thorn body's retribution, nine granted natural attacks, four
    that repeat every round — and every one of them was invisible while nothing rolled
    them. That is the "verify end to end, on real regenerated content" lesson arriving on
    schedule.
    """
    entries, report = spells.build_mechanics()
    assert report["total"] == 3040
    # 354 before the flat-bonus reader and the "functions like" pass. The scaling and
    # curated counts are untouched by either — damage and healing are read exactly as
    # they were, and the widening is entirely in the quiet half of a spell.
    assert report["effects"] == 640
    assert report["scaling"] == 342
    assert report["curated"] == 12
    assert report["prose"] == 2400
    assert report["invalid"] == []
    assert report["by_kind"] == {"damage": 327, "healing": 15}


def test_the_converted_file_is_what_the_converter_produces():
    """The shipped mechanics file and `build_mechanics()` must agree, because the file is
    what loads and the function is what the tests above measure. They drifted apart in the
    ingredient corpus and the difference was invisible until a bench showed the old text."""
    from django.conf import settings
    from pathlib import Path

    path = Path(settings.BASE_DIR) / "content" / "spells" / "spells-mechanics.json"
    on_disk = {e["id"]: e for e in json.loads(path.read_text(encoding="utf-8"))["spells"]}
    fresh, _ = spells.build_mechanics()
    assert set(on_disk) == set(fresh)
    assert on_disk["fireball"] == dict(fresh["fireball"], id="fireball")


def test_repeating_damage_is_left_as_prose_rather_than_flattened():
    """Acid arrow deals 2d4 each round while the acid lasts. Converting it to a single 2d4
    hit understates the spell by however many rounds it runs, so the `dot` tag is a refusal.

    Measured when the tag gate was relaxed to catch magic missile: it also caught
    constricting coils, black tentacles and summon stampede — three per-round effects out of
    five extra spells. Magic missile is hand-written instead."""
    # The *repeating* half stays prose — `effectspec` has no repeating-damage type, so
    # flattening it into one hit would have the arrow deal its whole duration at once.
    # The initial hit is a different question and the answer is plain in the text: "The
    # arrow deals 2d4 points of acid damage." A machine reading refused the whole spell
    # because it could not tell those apart; reading it can.
    fx = spells.get("acid-arrow").effects or []
    assert any(e.get("type") == "damage" and e.get("dice") == "2d4" for e in fx),         "the initial hit is stated plainly and should be executable"
    assert any(e.get("type") == "narrative" and "each round" in str(e.get("target", ""))
               for e in fx), "the repeating damage must stay prose"
    assert not any(e.get("type") == "damage" and "round" in str(e.get("note", ""))
                   for e in fx), "no spec may claim to repeat"
    assert not spells.get("acid-arrow").scaling
    assert spells.get("magic-missile").effects
    assert spells.get("magic-missile").effects_converted is False


def test_a_hand_written_effect_is_not_flagged_as_unreviewed():
    """`effects_converted` means "a machine read the prose and nobody has checked". The
    twelve written by hand are not waiting for anybody, and a bench that cannot tell the two
    apart is asking somebody to trust a parse."""
    assert spells.get("bless").effects_converted is False
    assert spells.get("fireball").effects_converted is True
    assert spells.get("bull-s-strength").effects[0] == {
        "type": "ability_mod", "amount": 4, "bonus_type": "enhancement", "target": "str"}


def test_cures_scale_by_points_rather_than_by_dice():
    """`1d8 + 1 point per caster level (maximum +5)` is a different shape from `1d6 per
    caster level`, and one field for both would be wrong for one of them."""
    clw = spells.get("cure-light-wounds")
    assert clw.scaling["kind"] == "healing"
    assert clw.element == "positive"
    assert spells.scaling_dice(clw, 1) == "1d8+1"
    assert spells.scaling_dice(clw, 3) == "1d8+3"
    assert spells.scaling_dice(clw, 5) == "1d8+5"
    assert spells.scaling_dice(clw, 20) == "1d8+5"
    assert clw.effects[0]["type"] == "heal"


def test_a_formula_per_two_levels_never_rolls_zero_dice():
    """Searing light is 1d8 per two caster levels. Floor division alone gives no dice at
    all at caster level 1, which is a spell that does nothing rather than a spell at its
    smallest."""
    sl = spells.get("searing-light")
    assert sl.scaling["per_levels"] == 2
    assert spells.scaling_dice(sl, 1) == "1d8"
    assert spells.scaling_dice(sl, 5) == "2d8"
    assert spells.scaling_dice(sl, 10) == "5d8"
    assert spells.scaling_dice(sl, 20) == "5d8"


def test_an_element_is_read_from_the_descriptor_and_never_from_the_prose():
    """A descriptor is the book's own column and an element is a lookup on it. 302 spells
    carry an energy descriptor; the rest of an element's coverage comes from a converted
    damage formula naming its own type, which is the only way [negative] and [positive] can
    arrive — 1e has no such descriptors."""
    assert spells.get("fireball").element == "fire"
    assert spells.get("cone-of-cold").element == "cold"
    assert spells.get("inflict-light-wounds").element == "negative"
    # Charm person is about fire in no sense and carries no element rather than "untyped",
    # which would read as a fact somebody decided.
    assert spells.get("charm-person").element == ""


# --- authoring: the round trip ------------------------------------------------------------------

def test_the_kind_declares_the_whole_tag_list_as_fields():
    """The request: "authoring a spell in the app's own homebrew editor offers school,
    element, level_available, casting time, components, range, area, duration, save, SR and
    effects". Before this the Kind declared five fields and a spell authored through it had
    no way to say which class could cast it, so nothing authored was ever castable."""
    declared = {f.name for f in registry.get("spells").fields}
    for wanted in ("school", "element", "level_available", "casting_time", "components",
                   "range", "area", "duration", "saving_throw", "spell_resistance",
                   "scaling", "effects", "descriptors"):
        assert wanted in declared, wanted


def test_the_kinds_vocabularies_have_not_drifted_from_the_rules():
    """`rules/registry.py` states that nothing in it imports a rules module, so the closed
    vocabularies on the spell Kind are written out a second time. Copies drift — that is the
    failure CLAUDE.md names, where the fix ships from the copy nobody looked at — so the
    drift is caught here rather than by a player finding a school the filter does not know.
    """
    by_name = {f.name: f for f in registry.get("spells").fields}
    assert tuple(by_name["school"].choices) == spells.SCHOOLS
    assert tuple(by_name["element"].choices) == spells.ELEMENTS
    assert tuple(by_name["components"].choices) == spells.COMPONENTS
    # And every grant kind the notation accepts is named in the field's own help, so the
    # form tells you what it will take.
    for via in spells.GRANT_VIA:
        if via != "class":
            assert via in by_name["level_available"].help


def test_the_editor_is_handed_text_where_the_engine_holds_structure():
    """The builder has six field types — text, textarea, number, choice, list of fixed
    choices, effects — and none of them edits a mapping. `derive` renders the two
    mapping-shaped fields out as the one-per-line notation and `normalise` reads them back.

    A list handed to a text input renders as "['fire']" and saves that string back, which is
    how a descriptor list becomes one descriptor called "['fire']"."""
    opened = registry.find("spells", "fireball")
    assert "wizard 3" in opened["level_available"]
    assert "domain fire 3" in opened["level_available"]
    assert opened["scaling"] == "1d6/level, max 10d6 fire"
    assert opened["descriptors"] == "fire"
    assert opened["dismissible"] == "no"
    assert opened["effects"] and opened["effects_converted"] is True


def test_the_notation_round_trips_through_the_form_and_back():
    """Authored → saved → loaded. What the textarea holds has to come back as the same
    grants, or an edit that touched the name would rewrite the class lists."""
    text = "wizard 3\nsorcerer 3\ndomain fire 3\nbloodline efreeti 3\nmystery flame 3"
    grants, problems = spells.parse_level_available(text)
    assert not problems
    assert {"via": "mystery", "name": "flame", "level": 3} in grants
    assert spells.format_level_available(grants).splitlines()[0] == "wizard 3"
    again, _ = spells.parse_level_available(spells.format_level_available(grants))
    assert again == grants


def test_the_users_own_brace_notation_is_accepted_rather_than_rejected():
    """`{{Domain : fire} : 3}` is how the request wrote it. A line pasted straight out of
    that notation is read rather than reported as an error — the braces and colons are
    punctuation around three facts the parser already wants."""
    grants, problems = spells.parse_level_available(
        "{sorcerer : 3}; {{Domain : fire} : 3}; {{Bloodline : efreeti} : 3}")
    assert not problems
    assert {"via": "class", "name": "sorcerer", "level": 3} in grants
    assert {"via": "domain", "name": "fire", "level": 3} in grants
    assert {"via": "bloodline", "name": "efreeti", "level": 3} in grants


def test_validate_refuses_a_level_on_a_class_that_does_not_exist():
    """The check a UI runs before it saves. A spell that says "wizzard 3" is not a spell
    with an unusual class: it is a spell nobody can ever cast, and it would have been saved
    without a word."""
    problems = spells.validate_spell(
        {"name": "Wrong", "school": "evocation", "level_available": "wizzard 3"})
    assert any("wizzard" in p for p in problems)
    assert not spells.validate_spell(
        {"name": "Right", "school": "evocation", "level_available": "wizard 3"})


def test_validate_names_every_problem_at_once():
    """A list rather than an exception, for the reason `effectspec.validate` returns one:
    a builder that reports errors one at a time is a builder nobody finishes."""
    problems = spells.validate_spell({
        "name": "", "school": "evocaton", "element": "plasma",
        "level_available": "wizard 12", "components": ["Q"],
        "descriptors": ["spicy"],
        "effects": [{"type": "damage", "dice": "banana", "damage_type": "fire"}],
    })
    joined = " ".join(problems)
    assert len(problems) >= 6
    for expected in ("name", "evocaton", "plasma", "0 to 9", "'Q'", "spicy", "banana"):
        assert expected in joined, expected


def test_a_homebrew_spell_overlays_and_is_castable(tmp_path, fresh_shelf):
    """Authored → saved → loaded → castable, through the real overlay directory.

    This is the deliverable the request called "through the UI". The failure it guards is
    the one a homebrew ingredient already hit: it appeared in the editor when reopened and
    never reached play, with no error anywhere. A spell whose `level_available` said
    "wizard 3" and whose `lists` stayed empty would fail `casting.knows` in exactly the same
    silent way, which is why `normalise` writes an authored class grant back into `lists`.
    """
    folder = tmp_path / "homebrew" / "spells"
    folder.mkdir(parents=True)
    (folder / "candleburst.json").write_text(json.dumps({
        "id": "candleburst", "name": "Candleburst", "school": "evocation",
        "descriptors": "fire",                       # as the text field saves it
        "level_available": "wizard 3\ndomain fire 3",
        "casting_time": "standard action", "components": ["V", "S"],
        "range": "medium (100 feet + 10 feet/level)", "area": "15-foot-radius burst",
        "duration": "instantaneous", "saving_throw": "Reflex half",
        "spell_resistance": "yes", "scaling": "1d6/level, max 8d6 fire",
        "description": "A wick of light snaps and burns.",
        "effects": [{"type": "damage", "dice": "1d6", "damage_type": "fire",
                     "scales": "full"}],
        "effects_converted": False,
    }), encoding="utf-8")

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        spells._ALL = None
        mine = spells.get("candleburst")
        assert mine.name == "Candleburst"
        # The text the form saves, read back as the structure the engine holds.
        assert mine.lists == {"wizard": 3}
        assert mine.descriptors == ["fire"]
        assert mine.element == "fire"
        assert {"via": "domain", "name": "fire", "level": 3} in mine.level_available
        assert mine.area_value == {"shape": "burst", "radius": 15, "unit": "feet"}
        assert (mine.save, mine.save_effect, mine.sr) == ("ref", "half", True)
        assert spells.scaling_dice(mine, 5) == "5d6"
        assert spells.scaling_dice(mine, 12) == "8d6"
        assert spells.effects_at(mine, 5)[0]["dice"] == "5d6"

        # And the engine agrees a wizard can reach it, which is the whole point of writing
        # an authored class grant back into `lists`.
        d = to_dict(load_pc("fixtures/pc-kesst.json"))
        d.update({"class": "wizard", "level": 5, "ranks": {}})
        d["abilities"]["int"] = 18
        d["spellbook"] = ["candleburst"]
        d["prepared"] = {"candleburst": 1}
        wiz = sheet_from_dict(d, ref="pc")
        assert casting.spell_level_for(wiz, mine) == 3
        assert casting.knows(wiz, mine) is True
        assert 3 in casting.slots_for(wiz)
    spells._ALL = None


def test_a_homebrew_spell_merges_rather_than_replaces(tmp_path, fresh_shelf):
    """Correcting one field must not erase the twenty the edit never asked about. The
    editor saves what its form showed; everything else on the shipped spell stays."""
    folder = tmp_path / "homebrew" / "spells"
    folder.mkdir(parents=True)
    (folder / "fireball.json").write_text(json.dumps({
        "id": "fireball", "name": "Fireball", "scaling": "1d6/level, max 12d6 fire",
    }), encoding="utf-8")

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        spells._ALL = None
        fb = spells.get("fireball")
        assert spells.scaling_dice(fb, 20) == "12d6"      # the correction took
        assert fb.school == "evocation"                   # and nothing else was lost
        assert fb.lists["wizard"] == 3
        assert fb.area_value["radius"] == 20
    spells._ALL = None


# --- through the app ------------------------------------------------------------------------

def test_the_bench_lists_spells(client):
    d = client.get("/api/bench/spells").json()
    assert d["bench"]["ready"]
    assert d["bench"]["shipped"] > 3000
    assert d["rows"]
    # Capped: three thousand rows is a wall, not a listing. The filters are the way in.
    assert len(d["rows"]) <= 200


def test_the_bench_says_where_the_engine_stops(client):
    """This asserted "no spell system" and was right until one was built, which is the
    hazard a page like this carries: a label that describes a limit outlives the limit and
    starts lying. It has now aged a second time and this test is the record of it — the
    blurb says the engine "will not read 1d6 per caster level out of English", and it now
    does exactly that for 354 spells. `play/homebrew.py` is where the sentence lives;
    docs/spells.md lists it under INTEGRATION NOTES as one line to rewrite.

    Left asserting the text that is actually shipping, because a test asserting what the
    page *ought* to say is a test that fails for the whole time somebody is reading it.
    """
    d = client.get("/api/bench/spells").json()
    waiting = d["bench"]["waiting"]
    assert "Castable now" in waiting
    assert "prose" in waiting


def test_the_search_endpoint_filters(client):
    d = client.get("/api/spells?descriptor=fire&tag=aoe&class=wizard").json()
    assert d["count"] > 0
    assert all("fire" in s["descriptors"] for s in d["spells"])
    assert d["vocab"]["descriptors"]


def test_one_spell_answers_in_full(client):
    d = client.get("/api/spells/fireball").json()
    assert d["name"] == "Fireball"
    assert d["description"]
    assert d["lists"]["wizard"] == 3
    # The structured half reaches the page too, or the play view has nothing to offer.
    assert d["element"] == "fire"
    assert d["scaling"]["cap_dice"] == 10
    assert d["area_value"]["radius"] == 20


def test_an_unknown_spell_is_a_404(client):
    assert client.get("/api/spells/nonsense").status_code == 404


def test_the_builder_opens_a_shipped_spell_through_the_app(client):
    """Every bench opens, shipped or authored. A conversion nobody can open is a conversion
    nobody can undo, and 354 spells were converted mechanically with nobody having read
    them."""
    d = client.get("/api/bench/spells/open/fireball").json()
    assert d["source"] == "shipped"
    assert d["converted"] is True
    assert "wizard 3" in d["level_available"]
    assert d["school"] == "evocation" and d["element"] == "fire"


def test_a_spell_authored_through_the_app_comes_back(client, tmp_path):
    """The save endpoint writes every field the Kind declares. A creature saved through the
    old five-field shape kept its name and lost its CR, and because homebrew merges field by
    field the loss was invisible until something asked for the missing one."""
    payload = {
        "id": "hearthspark", "name": "Hearthspark", "school": "evocation",
        "element": "fire", "descriptors": "fire",
        "level_available": "wizard 1\ndomain fire 1",
        "casting_time": "standard action", "components": ["V", "S"],
        "range": "close (25 feet + 5 feet/2 levels)", "area": "5-foot-radius burst",
        "duration": "instantaneous", "saving_throw": "Reflex half",
        "spell_resistance": "yes", "scaling": "1d4/level, max 5d4 fire",
        "description": "A spark leaps from the hearth.",
        "effects": [{"type": "damage", "dice": "1d4", "damage_type": "fire",
                     "lethality": "lethal"}],
    }
    r = client.post("/api/bench/spells/save", data=json.dumps(payload),
                    content_type="application/json")
    assert r.status_code == 200, r.content
    back = client.get("/api/bench/spells/open/hearthspark").json()
    assert back["source"] == "yours"
    assert back["level_available"].startswith("wizard 1")
    assert back["components"] == ["V", "S"]


# --- duration, structured -------------------------------------------------------------

def test_the_printed_duration_becomes_something_the_engine_can_time():
    """Converting a buff is pointless while its duration is prose.

    `_op_buff` keeps its clock in rounds and the corpus says "minutes/level (1)", so
    every converted bonus would have landed with no way to expire — the note the spell
    work left open as "riders still not applied". Nine tenths of the corpus states it in
    four shapes, which is why this is a parser and not a table somebody types: 740 spells
    say minutes/level, 564 rounds/level, 508 instantaneous, 243 hours/level.
    """
    from rules import spells

    bless = spells.get("bless")
    assert bless.duration_value == {"kind": "per_level", "amount": 1, "unit": "minute"}
    assert spells.duration_rounds(bless, 5) == 50        # five minutes, ten rounds each
    assert spells.duration_rounds(bless, 1) == 10


def test_a_spell_with_no_clock_reports_none_and_not_zero():
    """None means "do not time this"; zero would mean "expires the instant it lands".
    An instantaneous fireball and a permanent effect are both None, and a caller that
    treated that as a number would end a permanent spell on the round it was cast."""
    from rules import spells

    assert spells.duration_rounds(spells.get("fireball")) is None
    assert spells.get("fireball").duration_value == {"kind": "instantaneous"}


def test_a_duration_the_parser_cannot_read_is_left_empty():
    """"see text" is seventy-four spells. An empty dict says the GM adjudicates; a
    guessed number would say the rules had decided, which they have not."""
    from rules import spells

    assert spells.parse_duration("see text") == {}
    assert spells.parse_duration("") == {}


def test_until_discharged_rides_on_top_of_a_real_duration():
    """"minutes/level (1) or until discharged" ends at whichever comes first, so the
    flag joins the duration rather than replacing it — read as its own kind, the spell
    would have lost the clock it also has."""
    from rules import spells

    got = spells.parse_duration("minutes/level (1) or until discharged")
    assert got["kind"] == "per_level" and got["unit"] == "minute"
    assert got["until_discharged"] is True


def test_most_of_the_corpus_now_carries_a_clock():
    """The measurement that says this was worth doing: 2,921 of 3,040."""
    from rules import spells

    timed = [s for s in spells.all_spells().values() if s.duration_value]
    assert len(timed) >= 2900, len(timed)


def test_a_duration_per_two_levels_is_not_doubled():
    """"minutes/2 levels (1)" also matches the plain per-level pattern, so reading it
    there silently dropped the divisor and surelife came out twice as long as it is.
    Nothing on screen would have looked wrong. A reader flagged the shape at the merge,
    which is the only reason it was caught before it shipped."""
    from rules import spells

    got = spells.parse_duration("minutes/2 levels (1)")
    assert got == {"kind": "per_level", "amount": 1, "unit": "minute", "per_levels": 2}
    assert spells.duration_rounds(spells.get("surelife"), 10) == 50      # not 100
    # The plain shape is untouched.
    assert spells.duration_rounds(spells.get("bless"), 10) == 100


def test_two_machine_misreadings_that_only_reading_caught():
    """A regex found "1d6" in both and wrote a damage spec. Neither spell deals damage
    of the kind it claimed.

    Fly's 1d6 is a *descent timer* — "floats downward 60 feet/round for 1d6 rounds" —
    the same class of mistake as teleport's mishap table. Binding earth's 1d6 is dealt
    "for each 5 feet a creature moves" and the spell states no per-level progression at
    all, so it was wrong twice over: a damage spec and a scaling block, neither real.

    Both were invisible for as long as nothing executed them, and both were found by
    somebody reading the sentence."""
    from rules import spells

    for sid in ("fly", "binding-earth"):
        s = spells.get(sid)
        flat = list(s.effects or [])
        for spec in s.effects or []:
            flat.extend(spec.get("on_failure") or [])
            flat.extend(spec.get("on_success") or [])
        assert not [x for x in flat if x.get("type") == "damage"], sid
        assert not spells.scaling_dice(s, 10), f"{sid} still claims a damage progression"



# --- the quiet half of a spell -------------------------------------------------------

def test_a_flat_bonus_is_read_out_of_the_prose():
    """`read_scaling` reads damage and healing, which is the loud half. The quiet half is
    a number added to something the sheet already computes, and 2,686 of 3,040 spells had
    no mechanical half at all because nothing read it.

    Surveyed across those 2,686 before a line of the reader was written — ac_mod 46,
    ability_mod 39, skill_mod 62, attack_mod 26, save_mod 14 — because a reader built from
    a handful of examples converts a handful of spells."""
    got = spells.read_bonuses({"description":
        "Invisible layers of solid force surround the target, granting a +2 armor bonus "
        "to AC and DR 5/- against ranged attacks."})
    kinds = {(g["type"], g.get("target")): g for g in got}
    assert kinds[("combat_mod", "ac")]["amount"] == 2
    assert kinds[("damage_reduction", None)]["amount"] == 5
    assert kinds[("damage_reduction", None)]["bypass"] == ""


def test_the_codex_spells_armour_the_other_way():
    """The corpus is American and `effectspec.VOCAB["bonus_type"]` is not, and the ids keep
    their spaces. Slugging "natural armor" to `natural_armour` cost primal regression,
    transformation and tree shape their armour bonus, and the schema said so by name."""
    got = spells.read_bonuses(
        {"description": "You gain a +4 natural armor bonus to AC."})
    assert got[0]["bonus_type"] == "natural armour"
    _, problems = spells.convert(
        {"id": "x", "description": "You gain a +4 natural armor bonus to AC."})
    assert problems == []


def test_a_bonus_is_added_to_the_damage_rather_than_replacing_it():
    """`aid` is 1d8 temporary hit points *and* a +1 morale bonus on attack rolls. Reading
    only one of those is half a spell."""
    got, problems = spells.convert({
        "id": "aid",
        "description": "The target gains a +1 morale bonus on attack rolls and saving "
                       "throws against fear effects, plus 10 temporary hit points.",
    })
    kinds = {e["type"] for e in got["effects"]}
    assert {"combat_mod", "temp_hp"} <= kinds
    assert problems == []


def test_a_condition_with_no_save_in_front_of_it_stays_prose():
    """240 unconverted spells say something like "is staggered", and in nearly all of them
    the DC that decides it sits in a different sentence. A condition applied with no gate
    is a spell that always works, which is a wrong number — and prose beats a wrong number
    every time in this project."""
    got = spells.read_bonuses(
        {"description": "The target is staggered for 1 round."})
    assert not any(g["type"] == "apply_condition" for g in got)


def test_an_immunity_is_a_thing_and_not_the_rest_of_the_sentence():
    """Free text, so what the prose says is what the card shows — which means the parser
    running past the end of the noun phrase is visible to the player. "immune to poison
    are unaffected", "immune to fear instead" and "immune to diseases and poisons with"
    were all real output before the head and tail words were checked."""
    good = spells.read_bonuses({"description": "The target is immune to poison."})
    assert good == [{"type": "immunity", "target": "poison"}]

    for said in ("Creatures immune to poison are unaffected by this spell.",
                 "Those immune to fear instead take a -2 penalty.",
                 "You are immune to the effects described above."):
        assert not [g for g in spells.read_bonuses({"description": said})
                    if g["type"] == "immunity"], said


# --- "this spell functions like ..." ---------------------------------------------------

def test_a_spell_that_copies_another_one_inherits_its_mechanics():
    """The largest single group in the unconverted corpus: 459 spells say they function
    like another one. That is not prose to be parsed at all — it is a pointer, and
    following it cannot invent anything, because the numbers come from an entry that
    already exists."""
    entries = [
        # A flat bonus rather than damage, because `read_scaling` wants a whole entry —
        # tags, level, the lot — and the point here is the pointer, not the parser.
        {"id": "absorb-rune-i",
         "description": "The target gains a +2 deflection bonus to AC."},
        {"id": "absorb-rune-ii", "description": "This spell functions like absorb rune I, "
                                                "except as noted above."},
    ]
    out, _ = spells.build_mechanics(entries)
    assert "absorb-rune-i" in out, "the spell being copied did not convert"
    assert "absorb-rune-ii" in out
    assert out["absorb-rune-ii"]["inherited_from"] == "absorb-rune-i"
    assert out["absorb-rune-ii"]["effects"] == out["absorb-rune-i"]["effects"]


def test_the_prose_and_the_ids_name_ranks_the_other_way_round():
    """The Codex writes "mass cure light wounds"; the id is `cure-light-wounds-mass`. Worth
    43 more resolutions on its own, and it is a convention rather than a guess — the corpus
    is consistent about it in both directions."""
    known = {"cure-light-wounds-mass", "age-resistance-lesser"}
    assert spells.functions_as(
        {"description": "This spell functions like mass cure light wounds, except..."},
        known) == "cure-light-wounds-mass"
    assert spells.functions_as(
        {"description": "This functions as lesser age resistance, but..."},
        known) == "age-resistance-lesser"


def test_functioning_like_something_that_is_not_a_spell_inherits_nothing():
    """"functions like normal", "functions as intended", "functions like a tanglefoot bag"
    — 69 of them, and each one is the parser reading a sentence that was never about
    another spell."""
    known = {"fireball"}
    for said in ("This spell functions like normal, except louder.",
                 "The armour functions as intended, but heavier.",
                 "This functions like a tanglefoot bag, save that..."):
        assert spells.functions_as({"description": said}, known) == "", said


def test_a_reference_chain_cannot_spin():
    """Two spells naming each other resolve to nothing rather than looping."""
    entries = [
        {"id": "a", "description": "This spell functions like b, except as noted."},
        {"id": "b", "description": "This spell functions like a, except as noted."},
    ]
    out, _ = spells.build_mechanics(entries)
    assert out == {}


def test_the_whole_corpus_converts_without_a_single_invalid_spec():
    """3,040 spells through the schema. The count is the point: 354 carried mechanics
    before this and 640 do now, and every one of them validates."""
    out, report = spells.build_mechanics()
    assert report["invalid"] == []
    assert len(out) >= 640, f"only {len(out)} spells carry mechanics"



def test_a_rebuild_does_not_destroy_what_a_person_corrected():
    """Measured the first time the widened reader was written to disk: `fly` and `binding
    earth` had both been corrected by hand to narrative — fly's "1d6" is a *descent
    timer*, "floats downward 60 feet per round for 1d6 rounds", not damage — and a plain
    regeneration put the wrong damage specs straight back.

    Fourteen entries in the shipped file are in that state, and the marker for it already
    existed: `effects_converted` true is a machine's reading nobody has checked, and its
    absence is a person's answer.

    This module's own docstring warns about exactly this — "an effect derived at read time
    is silently overwritten the moment somebody corrects it" — and writing to a file
    instead of deriving at load is not on its own enough to prevent it."""
    import json
    from pathlib import Path as _P

    from django.conf import settings

    path = _P(settings.BASE_DIR) / "content" / "spells" / "spells-mechanics.json"
    shipped = {s["id"]: s for s in
               json.loads(path.read_text(encoding="utf-8"))["spells"]}

    by_hand = [s for s in shipped.values() if not s.get("effects_converted")]
    assert len(by_hand) == 14, f"{len(by_hand)} hand-written entries, expected 14"

    # And the two the rebuild actually broke are among them, still narrative.
    for sid in ("fly", "binding-earth"):
        kinds = [e.get("type") for e in shipped[sid]["effects"]]
        assert kinds == ["narrative"], f"{sid} was regenerated over: {kinds}"

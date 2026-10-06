"""The alchemist's words in the one effect vocabulary (alchemy lane B; contracts §2, plan
§5.3, §5.5, §16.3, §16.4, §16.6, §16.9).

Measured before any of it (plan §5.1, inv §3): 75 of the 139 alchemist materials carried
nothing executable, none carried three properties, and there was no way to say which
essence a trait carries, which route it travels by, how a reagent behaves at the bench,
that a flask's fire burns again next round, or that a sunrod gives light. A potion of
longstrider was drunk and narrated: speed's reader existed and its flag said no. `when`
had no check at all. Each test below names the defect it holds shut.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rules import effectspec as es
from rules import ingredients

ROOT = Path(__file__).resolve().parent.parent


def _content_docs():
    """Every effect document in content/: a dict whose `type` is an effect type."""
    for f in sorted((ROOT / "content").rglob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError):
            continue
        stack = [data]
        while stack:
            x = stack.pop()
            if isinstance(x, dict):
                t = x.get("type")
                if isinstance(t, str) and es.find(t) is not None:
                    yield f, x
                stack.extend(x.values())
            elif isinstance(x, list):
                stack.extend(x)


# --- essences, routes, working traits ------------------------------------------------------

def test_the_owner_kept_eighteen_essences_and_each_is_a_tag():
    """Open point 1 (2026-10-06): "Keep the 18." Formulae key on these and nothing else, so
    an essence spelled two ways is two formulae that never match; the tag is written by
    one function (law 1)."""
    assert list(es.ESSENCES) == [
        "fire", "frost", "acid", "storm", "thunder", "light", "shadow", "vigour",
        "purity", "ward", "might", "grace", "mind", "lightness", "sight", "binding",
        "decay", "change"]
    assert es.essence_tag("Fire") == "essence.fire"
    assert [o["id"] for o in es.VOCAB["essence"]] == list(es.ESSENCES)
    assert es.validate({"type": "heal", "dice": "1d8", "essence": "vigour"}) == []
    bad = es.validate({"type": "heal", "dice": "1d8", "essence": "plasma"})
    assert bad and "essence" in bad[0]


def test_the_routes_are_the_herb_corpus_and_the_alchemists_with_no_second_copy():
    """The herb bench keys its tables on `ingredients.ROUTES`; a copy here would drift.
    The alchemist adds struck, splash, area and carried (plan §5.3, owner open point 3:
    every thrown flask splashes)."""
    assert es.ROUTES[:len(ingredients.ROUTES)] == tuple(ingredients.ROUTES)
    assert es.ROUTES[len(ingredients.ROUTES):] == ("struck", "splash", "area", "carried")
    assert [o["id"] for o in es.VOCAB["route"]] == list(es.ROUTES)


def test_every_shipped_herb_route_still_validates():
    """529 herb effects carry a route; making `route` a checked field must refuse none."""
    seen = 0
    for f, doc in _content_docs():
        if "route" in doc:
            seen += 1
            assert not [p for p in es.validate(doc) if "reaches by" in p.lower()], (f, doc)
    assert seen >= 500


def test_the_alchemists_working_traits_are_in_the_one_list():
    """There was no working layer (plan §5.1). `volatile` and `pure` were the circle's and
    mean the same at the alchemist's bench, so they are reused, not respelled; every
    alchemy trait validates, renders words of its own, and tags by prefix."""
    for trait in es.ALCHEMY_WORKING_TRAITS:
        assert trait in es.WORKING_TRAITS
        assert es.validate({"type": "working", "trait": trait}) == [], trait
    assert es.WORKING_TRAITS.count("volatile") == 1
    assert {f"solvent:{k}" for k in es.SOLVENT_KINDS} <= set(es.WORKING_TRAITS)
    assert set(es.VESSEL_TRAITS) <= set(es.ALCHEMY_WORKING_TRAITS)
    assert es.working_tag("solvent:water") == "working.solvent.water"
    assert es.validate({"type": "working", "trait": "solvent:mercury"})


# --- the new fields on every effect ------------------------------------------------------------

def test_grade_drawback_and_source_are_checked():
    """`drawback` is a boolean with no form field, as `book` is: "yes" typed into it would
    be a second spelling of one fact. A grade below 1 is a trait that is not there."""
    ok = {"type": "save_mod", "amount": 5, "bonus_type": "alchemical", "target": "fort",
          "essence": "purity", "grade": 2, "drawback": False, "source": "antitoxin"}
    assert es.validate(ok) == []
    assert any("drawback" in p for p in es.validate({**ok, "drawback": "yes"}))
    assert any("grade" in p for p in es.validate({**ok, "grade": 0}))
    assert any("source" in p for p in es.validate({**ok, "source": 3}))


def test_a_carried_cost_is_only_what_carrying_can_do():
    """The carried door (`Actor.sync_carried`) runs CARRIED_TYPES and nothing else; a
    route it cannot deliver is a drawback that never lands."""
    ok = {"type": "apply_condition", "target": "sickened", "route": "carried",
          "drawback": True}
    assert es.validate(ok) == []
    bad = es.validate({"type": "damage", "dice": "1d6", "damage_type": "fire",
                       "lethality": "lethal", "route": "carried"})
    assert any("carried cost" in p for p in bad)


def test_a_product_trait_names_its_essence_and_route_and_is_never_narrative():
    """Five materials were narrative only and 70 had no effects (plan §5.1): a formula
    keyed on essences would have had nothing to match. Lane D's validator calls this."""
    trait = {"type": "damage", "dice": "1d6", "damage_type": "fire", "lethality": "lethal",
             "route": "struck", "essence": "fire", "grade": 1}
    assert es.product_trait_problems(trait) == []
    assert any("essence" in p for p in es.product_trait_problems(
        {k: v for k, v in trait.items() if k != "essence"}))
    assert any("route" in p for p in es.product_trait_problems(
        {k: v for k, v in trait.items() if k != "route"}))
    assert any("narrative" in p for p in es.product_trait_problems(
        {"type": "narrative", "target": "glows", "essence": "light", "route": "ingest"}))


# --- `when` is validated ---------------------------------------------------------------------

def test_every_when_in_the_shipped_content_validates():
    """`when` was not in COMMON and nothing checked it. The check is no narrower than the
    readers: every clause a shipped effect document carries passes (measured over content/:
    17 keys, read by `_when_holds`, `classfeatures.holds`, `forge_items` and the
    situation facts)."""
    seen = 0
    for f, doc in _content_docs():
        if doc.get("when") is not None:
            seen += 1
            assert es.when_problems(doc["when"]) == [], (f.name, doc["when"])
    assert seen >= 60


@pytest.mark.parametrize("when, says", [
    ({"undead": True}, "no reader asks undead"),
    ({"target": {"type": "zombie"}}, "not a creature type"),
    ({"target": {"kind": "undead"}}, "no key kind"),
    ({"target": "undead"}, "target is"),
    ({"range_ft": {"under": 30}}, "compare with"),
    ({"day_phase": "teatime"}, "day_phase is one of"),
    ({"daylight": "yes"}, "true or false"),
    ({}, "an object of clauses"),
])
def test_a_when_no_reader_can_answer_is_refused_with_the_fix(when, says):
    """An unevaluable clause is dropped, so the term applies to nobody with nothing saying
    why: the alchemist's "+2 against undead" written `{"undead": true}` was exactly that."""
    spec = {"type": "combat_mod", "amount": 2, "bonus_type": "alchemical",
            "target": "attack", "when": when}
    problems = es.validate(spec)
    assert any(says in p for p in problems), problems


def test_the_forges_spaced_creature_type_and_a_class_pick_still_pass():
    """The forge writes "magical beast" with a space (`_kind_leaf` reads it); a class
    writes "$pick" for its own choice. Both are the readers' grammar."""
    assert es.when_problems({"attacker": {"type": ["magical beast", "monstrous humanoid"]}}) \
        == []
    assert es.when_problems({"target": "$pick"}) == []
    assert es.when_problems({"target": {"type": "undead"}, "choice": "power_attack"}) == []


# --- speed and senses ----------------------------------------------------------------------

def test_a_potion_of_longstrider_moves_the_drinker():
    """Measured with the fixture PC: 30 ft before the drink and 30 after — the consumable
    branch and `speed_feet`'s funnel both existed and the flag sent the potion to
    narration. With it on, 40."""
    from rules.crafting import Stock
    from rules.dice import Dice
    from rules.engine import Engine, Scene
    from rules.sheet import load_pc

    s = Scene(location_id="5bbd0c40345f")
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    pc.stock["p#1"] = Stock(base="Longstrider", count=1, specs=[
        {"type": "speed", "target": "land", "amount": 10,
         "duration": {"amount": 1, "unit": "hour"}}])
    e = Engine(s, Dice(seed=9))
    assert pc.speed_feet == 30
    e.run(e.validate([{"op": "use_item", "actor": "pc", "because": "she drinks it",
                       "params": {"item": "p#1", "how": "drink"}}]))
    assert pc.speed_feet == 40


def test_a_mode_movement_does_not_read_waits_per_spec():
    """Nothing in movement reads a burrow speed; a potion of burrowing that claimed to run
    would be narrative wearing a costume. Climb, swim and fly got their readers in alchemy
    lane C (`Actor.movement_modes`, read by `can_move_vertically` and `water.swim_speed`;
    tests/test_alchemy_engine.py) and left the ledger."""
    assert es.executable({"type": "speed", "target": "land", "amount": 30})
    assert es.executable({"type": "speed", "amount": 30})          # absent is land
    for mode in ("climb", "swim", "fly"):
        assert es.executable({"type": "speed", "target": mode, "amount": 30}), mode
    for mode in ("burrow",):
        assert not es.executable({"type": "speed", "target": mode, "amount": 30}), mode
        assert mode in es.TARGETS_AWAITING_READER["speed"]
    assert es.validate({"type": "speed", "target": "land", "amount": 30,
                        "bonus_type": "enhancement"}) == []


def test_a_sense_tag_is_spelled_as_a_race_spells_it():
    """Race documents write `sense.low-light` and `sense.darkvision.60`. The worn reader
    (`Actor._worn_tags`) writes `sense.<target>` with only spaces hyphenated, so goggles
    of `low_light` grant `sense.low_light`, which `has_state("sense.low-light")` misses —
    measured on build/alchemy. `sense_tag` is the one spelling for the readers to ask."""
    from rules import races

    race_tags = {t for r in races.all_races().values() for t in (r.get("tags") or ())
                 if str(t).startswith("sense.")}
    assert es.sense_tag("low_light") in race_tags
    assert es.sense_tag("darkvision", 60) in race_tags
    assert es.sense_tag("see_invisible") == "sense.see-invisible"
    for tag in race_tags:
        assert "_" not in tag, tag


# --- the four that wait on lane C ----------------------------------------------------------

def test_what_waits_on_a_reader_says_which_and_does_not_run():
    """The honesty ratchet (tests/test_effectspec_extensions.py): a type may not claim the
    engine runs it when nothing does. Each waits in AWAITING_READER with its reader's
    site, and the builder's warning says so. Alchemy lane C landed all four readers
    (2026-10-06), so the ledger is empty and each now claims the engine runs it."""
    assert set(es.AWAITING_READER) == set()
    for t in ("sense", "permission", "light", "burning"):
        assert es.find(t)[1].engine, t
    for t, where in es.AWAITING_READER.items():
        _, etype = es.find(t)
        assert not etype.engine and not es.executable({"type": t}), t
        assert etype.blocked.startswith("Not run yet: its reader") and where in etype.blocked


def test_the_book_light_sources_are_written_as_the_table_prints_them():
    """The sunrod became a blade coating dealing 1d4 fire because there was no light to
    write. CRB, Vision and Light: torch 20 / 40, sunrod 30 / 60, candle n/a / 5; the second
    column is the OUTER radius of the step-brighter ring."""
    for r, raised in ((20, 40), (30, 60), (0, 5)):
        doc = {"type": "light", "radius_ft": r, "raised_ft": raised,
               "duration": {"amount": 6, "unit": "hour"}}
        assert es.validate(doc) == [], doc
    assert es.render({"type": "light", "radius_ft": 30, "raised_ft": 60}) \
        == "Normal light 30 ft, one step brighter out to 60 ft"
    assert any("OUTER" in p for p in es.validate(
        {"type": "light", "radius_ft": 30, "raised_ft": 30}))


def test_alchemists_fire_burns_next_round_unless_put_out():
    """The catalogue's alchemist's fire was 2d6 at once, no roll, no second round (inv
    §0.2). The book: 1d6 the round following, a full-round DC 15 Reflex to put it out,
    +2 rolling on the ground."""
    fire = {"type": "burning", "dice": "1d6", "damage_type": "fire", "rounds": 1,
            "save": "ref", "dc": 15, "smother_bonus": 2, "route": "struck",
            "essence": "fire", "book": True}
    assert es.validate(fire) == []
    line = es.render(fire)
    assert "1d6 fire" in line and "DC 15" in line and "+2 rolling" in line
    assert any("DC" in p for p in es.validate({**fire, "dc": None}))
    assert any("1 round or more" in p for p in es.validate({**fire, "rounds": 0}))


def test_a_permission_grants_a_named_tag_and_breathing_water_is_the_drowning_checks():
    """295 shipped documents write a permission's `target` as a sentence; making it
    the tag id (contracts §2.2's first shape) would have refused all of them. The tag
    rides beside it. Water breathing grants `breathes.water`, the tag the drowning check
    already asks (`water.breathes_water`), never a second spelling it would not see."""
    from rules import water
    from rules.activeeffect import ActiveEffect
    from rules.sheet import load_pc

    words = {"type": "permission", "target": "Breathe water freely."}
    assert es.validate(words) == [] and not es.executable(words)
    tagged = {**words, "tag": "breathe_water"}
    assert es.validate(tagged) == []
    assert es.validate({**words, "tag": "breathe-water"})
    assert es.permission_tag("breathe_water") == "breathes.water"
    pc = load_pc("fixtures/pc-kesst.json")
    assert not water.breathes_water(pc)
    pc.apply_effect(ActiveEffect(name="water breathing", kind="buff", key="wb",
                                 source="potion of water breathing",
                                 tags=(es.permission_tag("breathe_water"),)))
    assert water.breathes_water(pc)
    for pid, row in es.PERMISSIONS.items():
        assert row["tag"] and row["name"], pid


def test_every_shipped_permission_still_validates():
    """The sentences stay legal: none of the shipped permissions is refused by the tag."""
    n = 0
    for f, doc in _content_docs():
        if doc["type"] == "permission":
            n += 1
            assert not [p for p in es.validate(doc) if "tag" in p.lower()], (f.name, doc)
    assert n >= 295


# --- splash and stacking -------------------------------------------------------------------

def test_every_thrown_flask_splashes_by_the_book_unless_it_says_otherwise():
    """Owner, open point 3 (2026-10-06): all flasks splash within 5 ft. The book's splash is
    one point of the weapon's own energy (alchemist's fire 1 fire, acid 1 acid)."""
    fire = [{"type": "damage", "dice": "1d6", "damage_type": "fire", "route": "struck"},
            {"type": "burning", "dice": "1d6", "rounds": 1, "route": "struck"}]
    assert es.splash_for(fire) == [{"type": "damage", "dice": "1", "damage_type": "fire",
                                    "route": "splash"}]
    two = fire + [{"type": "damage", "dice": "1d4", "damage_type": "acid",
                   "route": "struck"}]
    assert [s["damage_type"] for s in es.splash_for(two)] == ["fire", "acid"]
    tanglefoot = [{"type": "apply_condition", "target": "entangled", "route": "struck"}]
    assert es.splash_for(tanglefoot) == []
    own = fire + [{"type": "damage", "dice": "2", "damage_type": "cold", "route": "splash"}]
    assert es.splash_for(own) == [own[-1]]


def test_the_stacking_source_is_the_effects_own_identity():
    """1e: same-typed bonuses never stack, and untyped ones stack "unless they are from the
    same source" (CRB, Combining Magic Effects). The owner's switch adds same-typed bonuses
    from different sources (open point 2), so the source must be the effect's identity:
    `source` first, the crafting pipeline's `from` second."""
    assert es.bonus_source({"source": "antitoxin", "from": "Brimstone"}) == "antitoxin"
    assert es.bonus_source({"from": "Brimstone"}) == "Brimstone"
    assert es.bonus_source({}, "the preparation") == "the preparation"


def test_the_catalogue_still_serialises_with_every_new_dropdown():
    """The editor embeds the catalogue; a choice naming a missing list draws empty."""
    json.dumps(es.catalogue())
    for c in es.CATEGORIES:
        for t in c.types:
            for f in t.fields + es.COMMON:
                if f.kind == "choice":
                    assert f.vocab in es.VOCAB, (t.id, f.id)

"""The enchanting property vocabulary: the new effect types in `rules/effectspec.py` and
the book's ability table in `content/rules/magic-properties.json`
(docs/enchanting-contracts.md §2, lane A).

Measured on master e028885 before any of it (docs/enchanting-revamp-plan.md §1): 14 of 81
essences and 47 of 170 catalogue items were `narrative` — keen, ghost touch, speed,
vorpal, defending, fortification, brilliant energy — because the vocabulary had no way to
say a threat range, an extra attack or a fortification roll. Bane's +2 and +2d6 sat in a
`note` reading "against the designated foe", so any reader would have applied them to
every creature. There was no "counts as magic" for damage reduction at all. Every test
here names the gap it closes.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rules import effectspec as es
from rules.dice import Modifier, stack

ROOT = Path(__file__).resolve().parent.parent


def _raw_entries() -> list[dict]:
    path = ROOT / "content" / "rules" / "magic-properties.json"
    return json.loads(path.read_text(encoding="utf-8"))["properties"]


def _spell_ids() -> set[str]:
    path = ROOT / "content" / "spells" / "spells.json"
    return {s["id"] for s in json.loads(path.read_text(encoding="utf-8"))["spells"]}


# --- the table is complete --------------------------------------------------------------

# Every ability the plan's tables name (revamp plan §8.2, §8.3) and every one the owner
# named in round 2 ("flaming, frost, shock, keen, ghost touch, bane vs a chosen foe, holy,
# speed, defending ..."). The CRB's melee and ranged tables, and its armour and shield
# tables, read 2026-10-05 from legacy.aonprd.com.
BOOK_WEAPON = {
    "flaming", "frost", "shock", "flaming-burst", "icy-burst", "shocking-burst", "keen",
    "bane", "holy", "unholy", "axiomatic", "anarchic", "ghost-touch", "speed", "defending",
    "merciful", "vicious", "wounding", "thundering", "disruption", "vorpal",
    "brilliant-energy", "dancing", "spell-storing", "distance", "returning", "seeking",
    "throwing", "ki-focus", "mighty-cleaving",
}
BOOK_ARMOUR = {
    "fortification-light", "fortification-moderate", "fortification-heavy",
    "spell-resistance-13", "spell-resistance-15", "spell-resistance-17",
    "spell-resistance-19", "energy-resistance", "energy-resistance-improved",
    "energy-resistance-greater", "invulnerability", "shadow", "shadow-improved",
    "shadow-greater", "slick", "slick-improved", "slick-greater", "ghost-touch-armour",
    "arrow-catching", "arrow-deflection", "bashing", "blinding", "animated", "etherealness",
    "reflecting", "undead-controlling", "wild", "glamered",
}


def test_every_book_ability_the_owner_wants_working_has_an_entry():
    """'Every book property works' (owner, round 2). Before this file there was no
    property vocabulary at all: 26 weapon and 32 armour entries lived as catalogue items,
    seven of the CRB's weapon abilities (disruption, spell storing, distance, seeking, ki
    focus, mighty cleaving) and four of its shield and armour ones (arrow deflection,
    reflecting, undead controlling, wild) were missing outright."""
    props = es.properties()
    assert BOOK_WEAPON <= set(props), sorted(BOOK_WEAPON - set(props))
    assert BOOK_ARMOUR <= set(props), sorted(BOOK_ARMOUR - set(props))
    for pid in BOOK_WEAPON:
        assert props[pid]["gear"] == ["weapon"], pid
    for pid in BOOK_ARMOUR:
        assert set(props[pid]["gear"]) <= {"armour", "shield"}, pid


def test_every_old_catalogue_ability_has_a_home_for_the_migration():
    """All 26 weapon and 32 armour entries in magic-items.json move here (contracts
    §2.2), their ids kept as aliases for old saves. An old id with no home is an old
    sword that loads as nothing. Energy resistance was five entries per tier, one per
    energy; it is one entry with a choice now, so each alias carries the energy it meant."""
    raw = json.loads((ROOT / "content" / "materials" / "magic-items.json")
                     .read_text(encoding="utf-8"))["materials"]
    old = [m["id"] for m in raw if m["kind"] in ("weapon_property", "armour_property")]
    assert len(old) == 58
    homeless = [o for o in old if es.from_alias(o) is None]
    assert homeless == []
    assert es.from_alias("mi-energy-resistance-cold-improved") == (
        "energy-resistance-improved", {"energy": "cold"})
    # Pathfinder folded 3.5's silent moves into shadow (CRB shadow: Stealth, built with
    # invisibility AND silence).
    assert es.from_alias("mi-silent-moves")[0] == "shadow"
    assert es.property("mi-flaming")["id"] == "flaming"


def test_the_table_validates_against_the_real_spell_list():
    """The old bane named `summon-monster-4` and thundering `shout`; the book prints
    summon monster I and blindness/deafness. And the Spells bench spells the first
    `summon-monster-1`: a requirement naming `summon-monster-i` is a spell nobody can ever
    know, and its +5 DC would be permanent. The whole table, every id checked."""
    assert es.all_property_problems(_raw_entries(), spell_ids=_spell_ids()) == []
    props = es.properties()
    assert props["bane"]["spells"] == [["summon-monster-1"]]
    assert props["thundering"]["spells"] == [["blindness-deafness"]]


def test_book_numbers_the_old_catalogue_had_wrong_are_the_books_now():
    """Read against the CRB tables on AoN, 2026-10-05. The old catalogue priced energy
    resistance, shadow, slick and glamered as bonus equivalents (+2, +1, +1, +1) where the
    book prints gold outside the +10; gave energy resistance caster level 7/11/15 where the
    book prints 3/7/11; and returning CL 9 where the book prints 7."""
    p = es.properties()
    assert es.price_of(p["energy-resistance"]) == {"gp": 18000}
    assert es.price_of(p["energy-resistance-improved"]) == {"gp": 42000}
    assert es.price_of(p["energy-resistance-greater"]) == {"gp": 66000}
    assert [p[k]["cl"] for k in ("energy-resistance", "energy-resistance-improved",
                                 "energy-resistance-greater")] == [3, 7, 11]
    assert es.price_of(p["shadow"]) == {"gp": 3750}
    assert es.price_of(p["slick-greater"]) == {"gp": 33750}
    assert es.price_of(p["glamered"]) == {"gp": 2700}
    assert es.price_of(p["etherealness"]) == {"gp": 49000}
    assert p["returning"]["cl"] == 7
    assert es.price_of(p["vorpal"]) == {"plus": 5} and p["vorpal"]["cl"] == 18
    assert p["shadow"]["spells"] == [["invisibility"], ["silence"]]   # both, not either


def test_scaled_prices_are_the_printed_ones():
    """The ring and wondrous bonuses are priced by the square of the bonus (Table:
    Estimating Magic Item Gold Piece Values). Checked against the printed price lists,
    not the formula against itself: ring of protection, amulet of natural armour, cloak
    of resistance, bracers of armour and the belts as AoN prints them."""
    p = es.properties()
    printed = {
        "deflection": {1: 2000, 2: 8000, 3: 18000, 4: 32000, 5: 50000},
        "natural-armour": {1: 2000, 2: 8000, 3: 18000, 4: 32000, 5: 50000},
        "resistance": {1: 1000, 2: 4000, 3: 9000, 4: 16000, 5: 25000},
        "armour-bonus": {1: 1000, 8: 64000},
        "ability-strength": {2: 4000, 4: 16000, 6: 36000},
        "ability-charisma": {2: 4000, 4: 16000, 6: 36000},
    }
    for pid, prices in printed.items():
        for bonus, gp in prices.items():
            assert es.price_of(p[pid], bonus) == {"gp": gp}, (pid, bonus)
    with pytest.raises(ValueError):
        es.price_of(p["ability-strength"], 3)        # belts come in +2, +4, +6
    assert es.bind("deflection", {"bonus": 3})[0]["amount"] == 3


# --- nothing narrative, everything executable ------------------------------------------

# The one pre-existing type a property uses that the engine does not run: the cast path
# rolls no caster level check against SR (effectspec `spell_resistance`, docs/spells.md
# §5.1). Lane C builds it (contracts §4). The new types wait in `es.AWAITING_READER`.
# When a reader lands and its type becomes executable, the last assertion below fails
# until this ledger shrinks with it, so it cannot go stale in either direction.
WAITING_OUTSIDE_THE_LEDGER = {"spell_resistance"}

NEW_TYPES = ["crit_range", "extra_attack", "enhancement_raise", "enhancement_to_ac",
             "fortification", "ignore_armour", "deflect_ranged", "weapon_lethality", "slay",
             "item_power"]


def test_every_property_document_is_executable_or_waits_on_a_named_reader():
    """47 of 170 catalogue items were narrative. Now no document anywhere in the table is
    narrative and every bound document validates. One that is not executable today is
    either a new type in `AWAITING_READER` (its reader named there) or spell resistance,
    which its property's not_yet names. A property with no documents (a rule a reader
    asks of its tag) must say which reader and what waits."""
    seen_waiting = set()
    for pid, prop in es.properties().items():
        for pick in es.sample_choices(prop):
            for doc in es.bind(prop, pick):
                assert es.validate(doc) == [], (pid, doc)
                for nested in es._walk_docs(doc):
                    assert nested.get("type") != "narrative", pid
                if not es.executable(doc):
                    seen_waiting.add(doc["type"])
                    if doc["type"] not in es.AWAITING_READER:
                        assert doc["type"] in WAITING_OUTSIDE_THE_LEDGER, (pid, doc["type"])
                        assert any(doc["type"] in w for w in prop["not_yet"]), pid
        if not prop["documents"]:
            assert prop.get("reads_tag") and prop["not_yet"], pid
    assert seen_waiting - set(es.AWAITING_READER) == WAITING_OUTSIDE_THE_LEDGER


def test_the_new_types_are_in_the_catalogue_and_honest_about_what_runs_them():
    """Each new type must be findable and serialise with the catalogue the homebrew editor
    builds its forms from. The contract fixed `engine: True` for all ten; the first full
    suite run refused that (tests/test_effectspec_extensions.py: 'a type claims the engine
    runs it and nothing does' — ten claimed, none ran). So each is marked not executable
    in `AWAITING_READER` with its reader's site, and the builder's warning says it waits.
    Lane C deletes a line when its reader lands."""
    ids = [t["id"] for c in es.catalogue()["categories"] for t in c["types"]]
    assert set(es.AWAITING_READER) <= set(NEW_TYPES)
    for t in NEW_TYPES:
        assert ids.count(t) == 1, t
        _, etype = es.find(t)
        assert etype.blocked, f"{t} must say what reads it"
        if t in es.AWAITING_READER:
            assert not es.executable({"type": t})
            assert etype.blocked.startswith("Not run yet: its reader")
            assert es.AWAITING_READER[t] in etype.blocked
        for f in etype.fields:
            if f.vocab:
                assert f.vocab in es.VOCAB, (t, f.id)
    json.dumps(es.catalogue())


SAMPLES = [
    ({"type": "crit_range", "multiply": 2}, "Doubles the threat range"),
    ({"type": "extra_attack", "on": "full_attack", "count": 1},
     "One extra attack on a full attack, at full base attack bonus"),
    ({"type": "enhancement_raise", "amount": 2}, "Enhancement bonus +2"),
    ({"type": "fortification", "percent": 50},
     "50% chance to turn a critical hit or sneak attack into an ordinary hit"),
    ({"type": "ignore_armour", "cannot_harm": ["undead", "construct", "object"]},
     "Ignores armour and shield bonuses to AC; cannot harm undead, construct, object"),
    ({"type": "slay", "natural": 20}, "Slays outright on a natural 20"),
    ({"type": "item_power", "spell": "ethereal-jaunt", "uses": "per_day", "uses_count": 1},
     "Casts ethereal jaunt (1× per day)"),
    ({"type": "damage", "dice": "1d10", "damage_type": "fire", "lethality": "lethal",
      "trigger": "crit", "per_multiplier": True},
     "1d10 fire damage per step of the weapon's critical multiplier, on a critical hit"),
]


@pytest.mark.parametrize("spec,line", SAMPLES)
def test_each_new_type_validates_and_reads_as_a_sentence(spec, line):
    """A card that prints the type's id tells a player nothing; flaming burst's card has to
    say why a x3 axe deals 2d10."""
    assert es.validate(spec) == [], spec
    assert es.render(spec) == line


def test_the_new_types_refuse_what_would_do_nothing_with_the_fix_named():
    """An effect that is authored and does nothing is the failure docs/homebrew-rules.md
    §1 exists for: a threat range multiplied by 1, an enhancement raised by 0, a
    fortification of 0%, an item power that neither casts nor does nor says."""
    assert "Keen is 2" in es.validate({"type": "crit_range", "multiply": 1})[0]
    assert "Bane is 2" in es.validate({"type": "enhancement_raise", "amount": 0})[0]
    assert es.validate({"type": "fortification", "percent": 0})
    assert es.validate({"type": "ignore_armour", "cannot_harm": ["ghost"]})
    assert es.validate({"type": "deflect_ranged"})                  # turns nothing
    assert es.validate({"type": "slay", "natural": 21})
    for bad in ({"type": "item_power", "uses": "unlimited"},
                {"type": "item_power", "spell": "haste", "tell": "and also this",
                 "uses": "unlimited"}):
        assert any("exactly one" in p for p in es.validate(bad)), bad
    for t in ("crit_range", "fortification", "ignore_armour", "weapon_lethality"):
        spec = {"type": t, "trigger": "hit"}
        assert any("standing property" in p for p in es.validate(spec)), t


def test_an_item_power_says_how_often_in_the_one_spelling_every_effect_has():
    """The contract first wrote a power's uses as `{"per": "day", "n": 1}`; every effect
    already carries `uses`/`uses_count` (COMMON), and two spellings of one fact is how the
    same fact ends up disagreeing. A power with no `uses` at all would be at will by
    accident, so it is refused; a tell with a number in it is a mechanic in prose."""
    ok = {"type": "item_power", "spell": "spell-turning", "uses": "per_day",
          "uses_count": 1}
    assert es.validate(ok) == []
    missing = es.validate({"type": "item_power", "spell": "spell-turning"})
    assert any("at will by accident" in p for p in missing)
    numbered = es.validate({"type": "item_power", "tell": "It heals 5 hit points.",
                            "uses": "unlimited"})
    assert any("carries no number" in p for p in numbered)


def test_vicious_hurts_the_wielder_in_the_word_that_already_meant_them():
    """The contract proposed `recipient: "wielder"`. "self" — "The one who has it" — has
    meant exactly that since recipients existed; a second spelling would leave every
    reader handling both."""
    vicious = es.bind("vicious")
    assert [d.get("recipient", "target") for d in vicious] == ["target", "self"]
    assert "wielder" not in {o["id"] for o in es.VOCAB["recipient"]}
    assert es.render(vicious[1]).endswith("on whoever has it")


# --- bane, the chosen foe, and counting as magic ------------------------------------------

def test_bane_without_a_foe_is_refused():
    """The old bane's numbers sat in a note ("against the designated foe"), and nothing
    read the note, so every reader would apply +2 and +2d6 to every creature. A property
    that asks a question is answered before it is bound, and humanoids and outsiders are
    answered by subtype, as the book's table says ('pick one subtype')."""
    with pytest.raises(ValueError, match="choose its foe"):
        es.bind("bane")
    with pytest.raises(ValueError, match="by subtype"):
        es.bind("bane", {"foe": "humanoid"})
    with pytest.raises(ValueError, match="not a foe"):
        es.bind("bane", {"foe": "bandit"})
    with pytest.raises(ValueError, match="not a choice this property asks"):
        es.bind("flaming", {"foe": "undead"})
    undead = es.bind("bane", {"foe": "undead"})
    assert all(d["when"] == {"target": {"type": "undead"}} for d in undead)
    goblins = es.bind("bane", {"foe": {"type": "humanoid", "subtype": "goblinoid"}})
    assert all(d["when"] == {"target": {"subtype": "goblinoid"}} for d in goblins)
    assert all("choice_key" not in d for d in undead + goblins)
    assert es.property_lines("bane", {"foe": "undead"})[1] == \
        "2d6 untyped damage against undead, on a hit"
    assert "against the chosen foe" in es.property_lines("bane")[1]


def test_bane_raises_the_enhancement_rather_than_standing_beside_it():
    """Written as the plan first had it — a combat_mod +2 of type enhancement — bane on a
    +1 sword goes through `dice.stack` as two enhancement bonuses, and 1e keeps the better
    ONE: +2 to hit. The book's +1 bane sword is +3 against its foe ('its enhancement bonus
    is +2 better than its actual bonus'). Measured here, so nobody writes it back."""
    as_plan_wrote_it = stack([Modifier(1, "+1 sword", "enhancement"),
                              Modifier(2, "bane", "enhancement")])
    assert sum(m.value for m in as_plan_wrote_it) == 2              # the defect
    doc = es.properties()["bane"]["documents"][0]
    assert doc["type"] == "enhancement_raise" and doc["amount"] == 2
    raised = 1 + doc["amount"]
    assert raised == 3                                               # the book
    # Owner, round 4 Q8: the raised bonus counts toward the DR thresholds — a +1 bane
    # sword passes DR/cold iron and DR/silver against its foe, as a +3 sword does.
    assert {"cold_iron", "silver"} <= set(es.strikes_as_for_enhancement(raised))
    assert "cold_iron" not in es.strikes_as_for_enhancement(1)


def test_counts_as_magic_follows_the_glossary_thresholds():
    """There was no magic-weapon channel ('the app has no magic-weapon channel to ask yet
    (stage 9)', engine.py). The CRB glossary's DR thresholds: +1 magic, +3 cold iron and
    silver, +4 adamantine, +5 the four alignments."""
    assert es.strikes_as_for_enhancement(0) == ()
    assert es.strikes_as_for_enhancement(1) == ("magic",)
    assert set(es.strikes_as_for_enhancement(3)) == {"magic", "cold_iron", "silver"}
    assert "adamantine" in es.strikes_as_for_enhancement(4)
    assert set(es.strikes_as_for_enhancement(5)) >= {"good", "evil", "lawful", "chaotic"}
    for trait in es.strikes_as_for_enhancement(5):
        assert trait in es.STRIKES_AS


def test_alignment_traits_are_spelled_as_the_bestiary_prints_its_damage_reduction():
    """The contract wrote `law` and `chaos`. `Reduction.bypassed_by` compares whole words
    with the stat block, and the bestiary prints 'DR 10/chaotic' (10 blocks), 'DR
    5/lawful' (4) and 'cold iron or lawful' (3) — never law or chaos. An axiomatic blade
    spelled `law` would bounce off every one of them."""
    from rules.sheet import Reduction

    creatures = json.loads((ROOT / "content" / "bestiary" / "creatures.json")
                           .read_text(encoding="utf-8"))["creatures"]
    words = set()
    for c in creatures:
        for r in c.get("reductions") or ():
            if isinstance(r, dict):
                for part in str(r.get("bypass") or "").lower().replace(" and ", " or ") \
                        .split(" or "):
                    words.add(part.strip())
    for alignment in ("good", "evil", "lawful", "chaotic"):
        assert alignment in words, alignment
        assert alignment in es.STRIKES_AS
    assert "law" not in words and "chaos" not in words
    assert Reduction(10, "chaotic").bypassed_by(("chaotic",))
    assert Reduction(5, "magic").bypassed_by(tuple(es.strikes_as_for_enhancement(1)))
    assert not Reduction(10, "chaotic").bypassed_by(("chaos",))


def test_the_holy_family_carries_alignment_as_data_and_says_nothing_checks_it():
    """Alignment is not tracked (owner ruling 2026-10-05, round 4 Q7): holy and its kin
    neither check the maker's alignment nor give the wrong wielder a negative level. The
    clauses stay in the data for the day alignment arrives, and each property says out
    loud that nothing reads them — including that the +2d6 'when target alignment evil'
    has no reader in `_when_holds`, so it fires against nobody yet."""
    pairs = {"holy": ("good", "evil"), "unholy": ("evil", "good"),
             "axiomatic": ("lawful", "chaotic"), "anarchic": ("chaotic", "lawful")}
    for pid, (is_, hurts) in pairs.items():
        p = es.properties()[pid]
        assert p["requires"]["creator_alignment"] == is_
        assert p["wielder"] == {"alignment": hurts, "negative_levels": 1}
        docs = es.bind(p)
        assert {"type": "strikes_as", "target": is_, "book": True,
                "source": f"property:{pid}"} in docs
        assert any(d.get("when") == {"target": {"alignment": hurts}} for d in docs)
        waits = " ".join(p["not_yet"]).lower()
        assert "alignment is not tracked" in waits and "_when_holds" in waits
        assert not any(d["type"] == "negative_level" for d in docs)
    # The validator holds every future entry to the same honesty.
    holy = dict(es.properties()["holy"], not_yet=[])
    problems = es.property_problems(holy)
    assert any("alignment is not tracked" in p for p in problems)
    assert any("Say so in not_yet" in p for p in problems)


# --- the shape rules ----------------------------------------------------------------------

def test_a_choice_key_and_the_when_that_asks_for_it_must_agree():
    """A `when` naming a choice the document does not carry is never filled, and an
    unfilled clause is dropped — bane applying to nobody, the opposite failure of the
    note-only bane applying to everybody."""
    no_key = es.validate({"type": "damage", "dice": "2d6", "damage_type": "untyped",
                          "lethality": "lethal", "trigger": "hit",
                          "when": {"target": {"choice": "foe"}}})
    assert any("carries no choice_key" in p for p in no_key)
    wrong = es.validate({"type": "damage", "dice": "2d6", "damage_type": "untyped",
                         "lethality": "lethal", "trigger": "hit", "choice_key": "energy",
                         "when": {"target": {"choice": "foe"}}})
    assert any("must name the same choice" in p for p in wrong)
    # A document whose target is filled by the choice is not missing its target...
    assert es.validate({"type": "resistance", "amount": 10, "choice_key": "energy"}) == []
    # ...and once bound it carries the real one.
    assert es.bind("energy-resistance", {"energy": "sonic"})[0]["target"] == "sonic"
    with pytest.raises(ValueError, match="not a energy"):
        es.bind("energy-resistance", {"energy": "force"})


def test_wielded_and_worn_work_only_on_the_standing_effects_an_item_grants():
    """A ring's fast healing and a helm's darkvision are standing effects granted while
    the item is worn and removed with it (the `carried` mechanism). A plain modifier needs
    no trigger — a worn item's modifiers are read while it is worn — so `worn` on a
    combat_mod is refused with the fix named, rather than accepted and read twice."""
    assert es.validate({"type": "fast_healing", "amount": 1, "trigger": "worn"}) == []
    assert es.validate({"type": "sense", "target": "darkvision", "range": 60,
                        "trigger": "worn"}) == []
    assert es.validate({"type": "negative_level", "amount": 1, "trigger": "wielded"}) == []
    refused = es.validate({"type": "combat_mod", "target": "ac", "amount": 1,
                           "bonus_type": "deflection", "trigger": "worn"})
    assert refused and "needs no trigger" in refused[0]
    assert {"wielded", "worn"} <= set(es.ITEM_TRIGGERS)
    assert es.render({"type": "fast_healing", "amount": 1, "trigger": "worn"}) == \
        "Fast healing 1, while worn"


def test_a_worn_trigger_is_never_registered_as_a_ward():
    """`Engine._executes` treats any non-`on_cast` trigger outside ITEM_TRIGGERS as a
    ward. Before `wielded` and `worn` joined the list, a ring's fast healing written with
    one would have stood in the scene waiting for a trigger no ward ever sees."""
    from rules.engine import Engine

    assert not Engine._executes(object.__new__(Engine),
                                {"type": "fast_healing", "amount": 1, "trigger": "worn"})


def test_per_multiplier_and_the_other_flags_are_booleans_in_their_one_place():
    """`book`'s rule, given the day it was added: a "yes" string is a second spelling of
    the fact for every reader. per_multiplier belongs on crit damage alone — 'strikes as
    silver per multiplier step' is not a rule — and stacks on bleed alone."""
    crit = {"type": "damage", "dice": "1d10", "damage_type": "fire",
            "lethality": "lethal", "trigger": "crit"}
    for key in ("per_multiplier", "house", "stacks", "suppressible"):
        problems = es.validate({**crit, key: "yes"})
        assert any("true or false" in p for p in problems), key
    assert es.validate({**crit, "trigger": "hit", "per_multiplier": True})
    assert es.validate({"type": "damage", "dice": "1d6", "damage_type": "fire",
                        "lethality": "lethal", "trigger": "hit", "stacks": True})
    assert es.validate({**crit, "book": True, "house": True})


def test_a_bad_table_stops_the_load_with_every_problem_named(tmp_path, monkeypatch):
    """Validated on load: a property priced twice, a vorpal at plus 6 and a narrative
    document must stop the load with each named — not ship as a sword that does
    nothing."""
    bad = [
        {**_raw_entries()[0], "id": "twice-priced", "gp": 2000, "aliases": {}},
        {**_raw_entries()[0], "id": "too-big", "plus": 6, "aliases": {}},
        {**_raw_entries()[0], "id": "prose", "aliases": {},
         "documents": [{"type": "narrative", "target": "It glows.", "book": True}]},
    ]
    path = tmp_path / "magic-properties.json"
    path.write_text(json.dumps({"properties": bad}), encoding="utf-8")
    monkeypatch.setattr(es, "_properties_path", lambda: path)
    es._property_table.cache_clear()
    try:
        with pytest.raises(es.BadProperties) as err:
            es.properties()
        text = str(err.value)
        assert "twice-priced: give exactly one price" in text
        assert "too-big: plus is the book's bonus equivalent" in text
        assert "prose > document 1: is narrative" in text
    finally:
        es._property_table.cache_clear()


def test_bind_hands_out_copies_and_never_the_table():
    """The table is the cache's own. A reader that edited a bound document in place would
    change every item carrying the property for the rest of the process."""
    docs = es.bind("flaming")
    docs[0]["dice"] = "9d6"
    assert es.properties()["flaming"]["documents"][0]["dice"] == "1d6"
    assert docs[0]["source"] == "property:flaming"


def test_weapon_restrictions_are_the_books_own_sentences():
    """Each restriction is a sentence of the ability's own text (CRB, read 2026-10-05):
    'Only piercing or slashing melee weapons can be keen'; 'A vorpal weapon must be a
    slashing melee weapon'; 'must be a bludgeoning melee weapon' (disruption); dancing
    'only on melee weapons'; brilliant energy 'melee weapons, thrown weapons, and
    ammunition'. The tables a property appears on are random-generation tables, not
    restrictions, and are not read as such."""
    p = es.properties()
    assert p["keen"]["requires"] == {"melee": True,
                                     "damage_types_any": ["piercing", "slashing"]}
    assert p["vorpal"]["requires"] == {"melee": True, "damage_types_any": ["slashing"]}
    assert p["disruption"]["requires"] == {"melee": True,
                                           "damage_types_any": ["bludgeoning"]}
    assert p["dancing"]["requires"] == {"melee": True}
    assert p["brilliant-energy"]["requires"] == {"launcher": False}
    assert p["returning"]["requires"] == {"thrown": True}
    for pid in ("flaming", "holy", "ghost-touch", "speed", "wounding", "merciful"):
        assert not {"melee", "ranged", "thrown"} & set(p[pid]["requires"]), pid
    assert p["ki-focus"]["requires"]["creator_class"] == "monk"
    assert p["spell-storing"]["requires"]["creator_caster_level"] == 12


def test_the_working_traits_lane_d_asked_for_exist():
    """Contracts §5: lane D's circle materials name these, and a trait the vocabulary
    does not know refuses every essence that carries it."""
    for trait in ("night_only", "eager", "skittish", "heavy", "volatile", "pure"):
        spec = {"type": "working", "trait": trait}
        assert es.validate(spec) == [], trait
        assert es.render(spec) and "_" not in es.render(spec)

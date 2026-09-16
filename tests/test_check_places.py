"""The places checker, and the two ways a checker like it goes wrong.

`tools/check_places.py` is what a World Bible session runs on an export before shipping
it. It is standalone — standard library and `docs/place-vocabulary.json`, nothing else —
because it has to run inside a repo that does not contain Pathfinder GM, and a checker
that agrees with the consumer only because it imports the consumer cannot be copied
anywhere.

That independence is bought with a reimplementation, and a reimplementation drifts. So the
two things tested hardest here are not the checks themselves:

1. **`parse_id` must agree with `places.terrain_of`** on every shape of id, including the
   malformed ones. A checker that passes an id the engine would read differently is worse
   than no checker, because it is trusted.
2. **`place-vocabulary.json` on disk must be what the tables produce today.** The whole
   argument for generating it is that a hand-copied list goes stale in the copy nobody
   looks at — and a generated list nobody regenerates is the same defect wearing a
   script.

The defect the checker exists for, measured 2026-09-15: an authored id in the format the
original ask 3 specified (`{settlement}:{slug}`, no terrain segment) gives a place whose
name the consumer does not already know a twenty-by-twenty field of open ground.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
from django.conf import settings

from rules import places

TOOLS = Path(settings.BASE_DIR, "tools")
VOCAB = Path(settings.BASE_DIR, "docs", "place-vocabulary.json")


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def checker():
    return _load("check_places")


# --- the reimplementation, against the thing it reimplements ------------------------------

WELL_FORMED = [
    "5bbd0c40345f~urban:the-market",
    "5bbd0c40345f~urban:the-market^1",
    "5bbd0c40345f~urban:the-market^-1",
    "5bbd0c40345f~forest:the-approach",
    "5bbd0c40345f~underground:the-sump",
]

# Every way one arrives wrong. Three of these are where the checker is deliberately
# STRICTER than `terrain_of`, and finding that out is what this file is for: asked
# `5bbd0c40345f~urban:` the engine answers "urban" quite happily, because its only job is
# to say what ground an id stands on and it is never asked whether the id names a place.
# The checker is asked exactly that, so it refuses an id with no spot on the end, no
# parent in front, or no colon at all.
MALFORMED = [
    "5bbd0c40345f:the-market",          # the ask-3 format: no ground in it
    "5bbd0c40345f~urban",               # no spot
    "~urban:the-market",                # no parent
    "5bbd0c40345f~:the-market",         # empty ground
    "5bbd0c40345f~urban:",              # empty spot
    "the-market",
    "",
]


@pytest.mark.parametrize("pid", WELL_FORMED)
def test_parse_id_reads_the_ground_the_engine_reads(checker, pid):
    """The one that matters. `terrain_of` is the engine's whole spatial derivation — it
    parses and never looks anything up — so for any id an export would actually carry,
    the checker's answer and the engine's have to be the same word."""
    mine = checker.parse_id(pid)
    assert mine is not None, pid
    assert mine[1] == places.terrain_of(pid), pid


@pytest.mark.parametrize("pid", MALFORMED)
def test_the_checker_is_stricter_and_never_looser(checker, pid):
    """The safe direction, stated as the rule. A checker that ACCEPTED an id the engine
    read differently would be the dangerous failure — it is trusted, and the export would
    ship. Refusing one the engine could still get a word out of only costs an author a
    better id."""
    assert checker.parse_id(pid) is None, pid


def test_the_ask_3_format_is_reported_as_unparseable(checker):
    """The defect, as an assertion. This id is *accepted* by the engine in the sense that
    nothing raises — it simply describes a place standing on nothing."""
    assert checker.parse_id("5bbd0c40345f:the-windcatcher-yard") is None
    assert places.terrain_of("5bbd0c40345f:the-windcatcher-yard") == ""


def test_a_storey_keeps_its_ground(checker):
    parent, terrain, slug, storey = checker.parse_id("5bbd0c40345f~urban:the-market^2")
    assert (parent, terrain, slug, storey) == ("5bbd0c40345f", "urban", "the-market", 2)


# --- the generated vocabulary ---------------------------------------------------------------

def test_the_vocabulary_on_disk_is_what_the_tables_produce_today():
    """Generated rather than transcribed, for the reason CLAUDE.md gives — and then
    actually regenerated, which is the half a script cannot enforce on its own."""
    fresh = _load("export_place_vocab").build()
    assert json.loads(VOCAB.read_text(encoding="utf-8")) == fresh, (
        "docs/place-vocabulary.json is stale — run tools/export_place_vocab.py")


def test_the_vocabulary_carries_every_word_an_author_may_write():
    vocab = json.loads(VOCAB.read_text(encoding="utf-8"))
    assert set(vocab["ventures"]) == set(places.VENTURES)
    assert [row["place"] for row in vocab["implied"]] == [spot for _w, (spot, _a)
                                                          in places.IMPLIED]
    assert vocab["most_places"] == places.MOST_SPOTS
    assert vocab["most_implied"] == places.MOST_IMPLIED
    assert vocab["id_grammar"]["separators"] == {"ground": places.SEP, "spot": ":",
                                                 "storey": places.STOREY}


def test_the_proposed_half_says_it_is_proposed():
    """`clutter` and `footing` have no reader — no code turns "dense" into pillars. A
    checker that reported them with the same confidence as the terrain list would be
    claiming the engine enforces something it has never seen."""
    vocab = json.loads(VOCAB.read_text(encoding="utf-8"))
    assert vocab["clutter"]["status"] == "proposed"
    assert vocab["footing"]["status"] == "proposed"


# --- it has to run where Pathfinder GM is not -----------------------------------------------

def test_the_checker_imports_nothing_from_this_app():
    """It gets copied into the World Bible repo beside the vocabulary. An import of
    `rules.places` would work here and fail there, which is the worst place to find out."""
    src = (TOOLS / "check_places.py").read_text(encoding="utf-8")
    for smell in ("from rules", "import rules", "django", "from world", "import world"):
        assert smell not in src, smell


def test_the_checker_runs_as_a_script_on_a_real_export():
    """End to end, through `python check_places.py`, because that is how it is used and
    an `argparse` that will not start is not caught by calling `check_place` directly.

    This asserted `"no play.places[]" in out.stdout` until 2026-09-15, when a World Bible
    export at schema 1.3 put 72 of them in the shipped fixture and the assertion became a
    statement about what the fixture happened to lack. What is worth pinning is that the
    script runs and passes a real export — so it runs against whichever of the two shipped
    worlds is there, and says which.
    """
    for world in ("pangrella-campaign.json", "aurvantis-campaign.json"):
        path = Path(settings.BASE_DIR, "fixtures", world)
        if not path.exists():
            continue
        out = subprocess.run(
            [sys.executable, str(TOOLS / "check_places.py"), str(path),
             "--vocab", str(VOCAB), "--tier", "2"],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        assert out.returncode == 0, f"{world}:\n{out.stdout}\n{out.stderr}"
        assert "0 with problems" in out.stdout, f"{world}:\n{out.stdout}"


def test_the_shipped_worlds_pass_their_own_checker():
    """The two fixtures are what every other test loads, so a place list that does not
    satisfy the contract would be a bad example baked into everything. Asserted on the
    library rather than the script, so a failure names the place."""
    import json

    checker = _load("check_places")
    vocab = json.loads(VOCAB.read_text(encoding="utf-8"))
    for world in ("pangrella-campaign.json", "aurvantis-campaign.json"):
        path = Path(settings.BASE_DIR, "fixtures", world)
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        places = (data.get("play") or {}).get("places") or []
        if not places:
            continue
        known = {str(p.get("id")) for p in places}
        entities = {str(e.get("id")) for e in data.get("entities") or []}
        for place in places:
            problems, _notes = checker.check_place(place, vocab, known, entities, 2)
            assert problems == [], f"{world} {place.get('id')}: {problems}"


# --- the checks themselves ------------------------------------------------------------------

P = "5bbd0c40345f"


def _place(**over) -> dict:
    base = {"id": f"{P}~urban:the-market", "name": "the market",
            "about": "Windcatchers over every stall.", "parent": P, "terrain": "urban",
            "exits": [f"{P}~urban:the-gate"], "described_only": False, "origin": "world"}
    base.update(over)
    return base


def _run(checker, places_list, tier=1) -> tuple[list[str], list[str]]:
    vocab = json.loads(VOCAB.read_text(encoding="utf-8"))
    known = {str(p["id"]) for p in places_list}
    problems, notes = [], []
    for place in places_list:
        p, n = checker.check_place(place, vocab, known, {P}, tier)
        problems += p
        notes += n
    return problems, notes


def test_a_well_formed_pair_has_nothing_wrong_with_it(checker):
    """A checker that never passes is a checker somebody turns off."""
    pair = [_place(), _place(id=f"{P}~urban:the-gate", name="the gate",
                             about="The way in and out.",
                             exits=[f"{P}~urban:the-market"])]
    problems, _notes = _run(checker, pair)
    assert problems == []


@pytest.mark.parametrize("over, expect", [
    ({"id": f"{P}:the-market"}, "does not parse"),
    ({"id": f"{P}~moon:the-market"}, "is not one the consumer knows"),
    ({"terrain": "forest"}, "the id wins"),
    ({"about": "Three stalls and 2 carts."}, "a digit in `about`"),
    ({"origin": "found"}, "origin 'found'"),
    ({"exits": ["nowhere-at-all"]}, "is not a place in this export"),
    ({"parent": "deadbeefdead"}, "is not an entity in this export"),
    ({"miles": 4}, "carries no distance"),
    ({"name": ""}, "no name"),
])
def test_each_way_a_place_arrives_broken(checker, over, expect):
    """One row per thing that has to be caught, because a checker is only ever as good as
    the case nobody wrote a row for."""
    problems, _ = _run(checker, [_place(**over),
                                 _place(id=f"{P}~urban:the-gate", name="the gate",
                                        about="Out.", exits=[])])
    assert any(expect in p for p in problems), (expect, problems)


def test_a_stranded_place_is_found(checker):
    """Reachability, which no single place can see. The consumer walks exits; a place
    nothing exits to is somewhere no party can stand."""
    vocab = json.loads(VOCAB.read_text(encoding="utf-8"))
    group = [_place(exits=[]), _place(id=f"{P}~urban:the-attic", name="the attic",
                                      about="Dust.", exits=[])]
    problems, _notes = checker.check_group(P, group, None, vocab)
    assert any("not reachable" in p for p in problems), problems


def test_a_one_way_exit_is_a_note_and_a_dangling_one_is_not(checker):
    """The fix for a false positive found by running it: an exit to a place that is not
    in the export was being reported as one-way as well as missing, which describes it
    wrongly — the party cannot walk in either."""
    vocab = json.loads(VOCAB.read_text(encoding="utf-8"))
    one_way = [_place(exits=[f"{P}~urban:the-gate"]),
               _place(id=f"{P}~urban:the-gate", name="the gate", about="Out.", exits=[])]
    _p, notes = checker.check_group(P, one_way, None, vocab)
    assert any("one-way" in n for n in notes), notes

    dangling = [_place(exits=["nowhere"])]
    _p2, notes2 = checker.check_group(P, dangling, None, vocab)
    assert not any("one-way" in n for n in notes2), notes2


def test_two_places_cannot_share_an_id(checker):
    """Everything the campaign overlay remembers is keyed by the id, so a duplicate is
    one place with two descriptions rather than two places."""
    vocab = json.loads(VOCAB.read_text(encoding="utf-8"))
    problems, _ = checker.check_group(P, [_place(exits=[]), _place(exits=[])], None, vocab)
    assert any("share the id" in p for p in problems), problems


def test_the_settlement_words_that_would_mint_a_place_are_reported(checker):
    """The "why did it not make a docks?" check, pointed the other way: a town whose own
    prose says port and has no docks is a list poorer than the generator it replaces."""
    vocab = json.loads(VOCAB.read_text(encoding="utf-8"))
    town = {"id": P, "kind": "CITY", "name": "Harbourton", "summary": "",
            "facts": {"Trade": "A port town, and the quay is its living."},
            "sections": [{"title": "Life", "paragraphs": ["Ships come and go."]}]}
    _p, notes = checker.check_group(P, [_place(exits=[])], town, vocab)
    assert any("the docks" in n for n in notes), notes


# --- tier 2 and tier 3 ------------------------------------------------------------------------

@pytest.mark.parametrize("over, expect", [
    ({"size_ft": {"width": 4, "depth": 80, "height": None}}, "squares or metres"),
    ({"size_ft": {"width": 400, "depth": 80, "height": None}}, "over 300 ft"),
    ({"size_ft": {"width": 80, "depth": 80}}, "no height"),
    ({"clutter": "busy"}, "clutter 'busy' is not one of"),
    ({"vertical": "vertiginous"}, "vertical 'vertiginous' is not one of"),
    ({"storeys": {"up": -1, "down": 0}}, "a count of floors"),
    ({"size_ft": {"width": 80, "depth": 80, "height": None},
      "storeys": {"up": 1, "down": 0}}, "storeys under open sky"),
])
def test_tier_two_catches_a_room_that_cannot_be_built(checker, over, expect):
    good = {"size_ft": {"width": 80, "depth": 80, "height": None}, "clutter": "some",
            "footing": "firm", "vertical": "ledge"}
    problems, _ = _run(checker, [_place(**{**good, **over})], tier=2)
    assert any(expect in p for p in problems), (expect, problems)


def test_tier_two_is_silent_at_tier_one(checker):
    """The tiers are shippable one at a time. A tier-1 export is a complete export, and a
    checker that scolds it for tier-2 fields it never promised is one nobody runs."""
    problems, _ = _run(checker, [_place(exits=[])], tier=1)
    assert problems == []


@pytest.mark.parametrize("over, expect", [
    ({"blocked": [[99, 2]]}, "outside the"),
    ({"blocked": [[1]]}, "each is [x, y]"),
    ({"floor": {"nope": 5}}, "is not 'x,y'"),
    ({"floor": {"1,1": 40}}, "nothing can stand on it"),
    ({"parapet": {"0,1": -3}}, "a height in feet"),
])
def test_tier_three_catches_squares_that_are_not_in_the_room(checker, over, expect):
    """A heightmap that reaches outside its own grid, or a dais taller than the ceiling
    over it. Both draw a room the engine cannot build and neither is visible by reading
    the JSON."""
    base = {"size_ft": {"width": 30, "depth": 30, "height": 10}, "clutter": "some",
            "footing": "firm", "vertical": "none"}
    problems, _ = _run(checker, [_place(**{**base, **over})], tier=3)
    assert any(expect in p for p in problems), (expect, problems)

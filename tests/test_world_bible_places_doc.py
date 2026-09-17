"""The places-and-races handoff, pinned against the tables it describes.

`docs/places-and-races-for-world-bible.md` tells another program which words this one
understands: fourteen terrains, four vertical kinds, nine ventures, eight cue rows that
mint a place out of a settlement's own facts. Every one of those is transcribed from a
Python table into prose, which is the exact shape CLAUDE.md names as a recurring defect —
"when you fix a rule, grep for every copy of it", because the copy nobody looks at carries
on shipping the old rule. The race half of the handoff is generated from its table for
this reason; the places half cannot be, because it is an argument rather than a list.

So it is checked instead. If somebody adds a terrain, renames a vertical kind or teaches
the app a new venture, this fails on the same day rather than after a World Bible session
has built a month of exports against a list that moved.

The id grammar is checked by behaviour, not by spelling. Measured 2026-09-15, which is
what put the document's **B.1** there: the format the original ask 3 specified
(`{settlement}:{slug}`, no terrain segment) gives an authored place whose name this app
does not already know a twenty-by-twenty field of open ground — the blank battlefield that
the whole of stages 1 to 7 existed to remove. A place the app happens to recognise by slug
survives it by accident, which is why a spot-check on `the-market` would have proved the
wrong thing.
"""
from __future__ import annotations

from pathlib import Path

from django.conf import settings

from rules import biomes, floorplan, places

DOC = "docs/places-and-races-for-world-bible.md"


def _doc() -> str:
    return Path(settings.BASE_DIR, DOC).read_text(encoding="utf-8")


# --- the id grammar, as behaviour ---------------------------------------------------------

def test_an_authored_place_without_its_terrain_gets_the_blank_field():
    """The measurement behind B.1. `terrain_of` parses the id and nothing else — no
    lookup, no world — so a missing `~terrain` is not a cosmetic difference: it is the
    difference between a room and a featureless square."""
    bare = "5bbd0c40345f:the-windcatcher-yard"
    shape = floorplan.shape_for(bare, places.terrain_of(bare))
    assert places.terrain_of(bare) == ""
    assert (shape.width, shape.height) == (20, 20), shape
    assert shape.about == floorplan.OPEN.about, "no longer the blank field; update the doc"


def test_the_same_place_with_its_terrain_is_a_room():
    """And the fix, which is one segment of the id."""
    named = "5bbd0c40345f~urban:the-windcatcher-yard"
    assert places.terrain_of(named) == "urban"
    shape = floorplan.shape_for(named, "urban")
    assert (shape.width, shape.height) != (20, 20)
    assert shape.about == floorplan.BY_TERRAIN["urban"].about


def test_the_terrain_segment_survives_a_storey():
    """A floor of a building is the same id with `^1` on it, and the ground it stands on
    has to read the same from up there."""
    assert places.terrain_of("5bbd0c40345f~urban:the-market^1") == "urban"


# --- the vocabularies the document hands over ---------------------------------------------

def test_every_terrain_the_engine_knows_is_offered_to_the_author():
    """Fourteen words, and the document lists them as the only legal values. A fifteenth
    that nobody wrote down is a terrain World Bible can never send."""
    doc = _doc()
    for terrain in sorted(biomes.BIOMES):
        assert f"`{terrain}`" in doc, f"{terrain} is not offered in {DOC}"


def test_the_document_offers_no_terrain_the_engine_would_refuse():
    """The other direction, and the one that actually misleads: a word in the handoff
    that the parser has never heard of produces a place standing on nothing."""
    doc = _doc()
    # The list is two lines long now and was one when this was written, so it is found by
    # the sentence that introduces it rather than by the first word of it — a test that
    # breaks when a vocabulary grows past one line is a test that punishes the vocabulary
    # for growing.
    lines = doc.splitlines()
    start = next(i for i, ln in enumerate(lines) if "the consumer knows, and no other" in ln)
    # From after the introducing sentence, which names the FIELD in backticks and would
    # otherwise be read as a terrain called "terrain".
    block = " ".join(lines[start:start + 4]).split("no other word:")[-1]
    offered = {w.strip(" `,.") for w in block.split()
               if w.startswith("`") and w.strip(" `,.").isalpha()}
    unknown = offered - set(biomes.BIOMES)
    assert not unknown, unknown
    assert {"water", "underwater", "deck"} <= offered, offered


def test_every_vertical_kind_is_described():
    """The four words are the whole of how a place is shaped upward, and the document is
    where an author learns which one to write."""
    doc = _doc()
    kinds = {s.vertical for s in
             list(floorplan.BY_SPOT.values()) + list(floorplan.BY_TERRAIN.values())}
    kinds.add(floorplan.Shape().vertical)
    for kind in sorted(kinds):
        assert f"`{kind}`" in doc, f"vertical kind {kind!r} is undocumented"


def test_the_default_vertical_is_the_one_the_document_calls_the_default():
    """"ledge is the default, and that is deliberate" — the standing instruction to bias
    generated places toward verticality. If the dataclass default moves, that paragraph
    is telling another program to do the opposite of what this one does."""
    assert floorplan.Shape().vertical == "ledge"
    assert "`ledge` is the default" in _doc()


def test_every_venture_is_listed():
    """The ground a party goes into rather than walks to. Listed so an author knows which
    places the app already makes and need not author."""
    doc = _doc()
    for venture in sorted(places.VENTURES):
        assert f"`{venture}`" in doc, f"venture {venture!r} is not in {DOC}"


def test_every_cue_word_that_mints_a_place_is_in_the_table():
    """B.2's table is the interface between a settlement's prose and its rooms — "why did
    it not make a docks?" — so an author has to be able to see which words do it. All of
    them, not a sample: the one left out is the one nobody writes."""
    doc = _doc().lower()
    for words, (place, _about) in places.IMPLIED:
        assert place in doc, f"{place!r} is not in the cue table"
        for word in words:
            assert word in doc, f"{word!r} mints {place!r} and is not in the cue table"


def test_the_two_ceiling_heights_are_stated_in_feet():
    """The document must not teach anybody to write levels — that is this app's unit, and
    an export that carries it is silently wrong the day the unit changes. It states the
    two heights in feet, so the feet and the levels have to agree here."""
    doc = _doc()
    # Substrings without the markdown round them: the prose may be re-emphasised, and a
    # test that breaks on a pair of asterisks is a test somebody deletes.
    assert f"{floorplan.LOW * 5} feet of ceiling is a house" in doc
    assert f"{floorplan.HALL * 5} feet is a hall" in doc


def test_the_ceiling_the_doc_states_is_the_one_the_generator_can_reach():
    """Three numbers became a table on 2026-09-15, twice in one day.

    First: the engine and the checker disagreed about what six counted, and this app's own
    generator made seven places for a settlement its own checker flagged. Then the six
    itself went — "there is no town or city that has 2 places. 2 places is a rest stop" —
    and a settlement holds what its own scale says it holds.

    So what a document may state is the table, not a number, and the largest of it is what
    a checker compares against because that is the most any settlement may hold.
    """
    assert places.MOST_IN_A_SETTLEMENT == max(places.PLACES_BY_SCALE.values())
    doc = _doc()
    for scale, n in places.PLACES_BY_SCALE.items():
        assert f"{scale} of {_words(n)}" in doc, (
            f"the document does not say a {scale} holds {n}")

def _words(n: int) -> str:
    return {3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight",
            9: "nine", 10: "ten", 12: "twelve", 16: "sixteen",
            18: "eighteen", 20: "twenty", 24: "twenty-four"}.get(n, str(n))


def test_the_generator_cannot_exceed_the_ceiling_it_publishes():
    """The finding itself, as an assertion rather than as a comment. A settlement whose
    own words earn it two extra places gets the base draw plus both, and that total is
    what a checker must be told about."""
    import json

    from django.conf import settings

    vocab = json.loads(Path(settings.BASE_DIR, "docs",
                            "place-vocabulary.json").read_text(encoding="utf-8"))
    assert vocab["most_places"] == places.MOST_IN_A_SETTLEMENT
    assert vocab["most_generated"] == places.MOST_SPOTS
    assert vocab["most_implied"] == places.MOST_IMPLIED
    # And the per-minted-parent cap is published as its own thing, because conflating the
    # two is what started this.
    assert vocab["most_children_minted_in_play"] == places.MOST_CHILDREN


def test_a_generated_town_that_earns_two_extras_is_not_over_its_own_limit():
    """Measured: settlement id 000000000001, whose words earn a docks and a mine head,
    came out at seven and was noted by the checker at six."""
    import json

    from django.conf import settings

    class Loc:
        id = "000000000001"; name = "Portmine"; kind = "CITY"; scale = "town"
        facts = {"Trade": "A port town with a quay, and a mine at its back."}
        prose = ""; places = []

    got = places.home_set(Loc())
    vocab = json.loads(Path(settings.BASE_DIR, "docs",
                            "place-vocabulary.json").read_text(encoding="utf-8"))
    assert len(got) > places.MOST_SPOTS, "the case that found this no longer reproduces"
    assert len(got) <= vocab["most_places"], (
        f"the generator makes {len(got)} and publishes a ceiling of "
        f"{vocab['most_places']}")


# --- the stale copy this document was written to replace ----------------------------------

def test_the_original_ask_no_longer_shows_an_id_that_builds_a_blank_field():
    """`docs/for-world-bible.md` ask 3 predates the spatial authority and its worked
    example used `{settlement}:{slug}`. Both documents go to the same reader, and the one
    with the older example is the one they would copy."""
    older = Path(settings.BASE_DIR, "docs", "for-world-bible.md").read_text(
        encoding="utf-8")
    assert "5bbd0c40345f:the-" not in older, "ask 3 still shows an id with no terrain in it"
    assert "places-and-races-for-world-bible.md" in older, "ask 3 does not point at its successor"

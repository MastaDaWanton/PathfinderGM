"""The tavern the party stands in is not a tavern somewhere else (`stands-elsewhere`).

Measured on the owner's save of 2026-10-01: the party walked into a place the plan had
founded as `kind="tavern"` under a name of its own, and then into a room founded inside
it. 17 `stands-elsewhere` findings in the save, and 13 of them read "there is no tavern
in this place at all" while the party stood in that tavern or its back room — on "the
roar of the tavern", "The tavern is quiet around you", "the tavern's heavy door", "Each
street takes you further from the tavern". Six of the 13 went unrepaired and shipped with
the finding attached; every rewrite asked for one was told to move the beat out of the
tavern the party was in. Every one of the 13 was a false positive: the detector compared
the page's "tavern" with the place's NAME, and a founded place's name is its own.

The fix is not a special case for "tavern": the place's kind, and the kinds and names of
the places it stands inside, are where the party is (`rules.places.words_for_here`), and
the kinds of every founded place are places that exist here (`kinds_of`).

The first cut of this fix named that function `what_it_is`, which `rules/places.py`
already defines (a settlement's scale in words): the second definition shadowed the
first and broke the opening's "a village of a few hundred people" — seven tests in
test_who_you_are_with.py and test_c_opening_words.py. `test_the_scale_words_survive`
below keeps the two apart.

After, on the same 17 findings: the 13 tavern findings are gone (each named "the tavern",
which is now the place they stand in); the four others — the stables and the tannery the
page walked the party past, which that town does not have, and a lane and an alley in the
back streets — are still found. On the committed replay corpus (146 drafts) the count is
12 before and 12 after.
"""
from __future__ import annotations

from gm import narration
from rules import places
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from world.loader import load_cached

WORLD = load_cached("fixtures/aurvantis-campaign.json")
VORMOOR = next(s["id"] for s in WORLD.play["settlements"] if s.get("name") == "Vormoor")


def _engine():
    s = Scene(location_id=VORMOOR)
    pc = instantiate("guildhand", scene=s, name="Spree")
    pc.kind = "pc"
    s.add(pc)
    e = Engine(s, Dice(seed=3), world=WORLD)
    e.place_party()
    return e, pc


def _run(e, pc, *raws):
    out = e.run(e.validate([{"actor": pc.ref, "because": "t", **r} for r in raws],
                           origin="author:test")).outcomes
    assert all(o.status == "resolved" for o in out), [o.tell for o in out]


def _in_the_kettle(back_room=False):
    """The party in a founded tavern with a name of its own (and, asked for, in a room
    founded inside it) — the shape of the owner's save, on the fixture world."""
    e, pc = _engine()
    _run(e, pc, {"op": "found", "params": {"name": "the Copper Kettle", "kind": "tavern"}},
         {"op": "travel", "params": {"place": "the Copper Kettle"}})
    if back_room:
        _run(e, pc, {"op": "found", "params": {"name": "the back room", "kind": "tavern",
                                               "parent": "the Copper Kettle"}},
             {"op": "travel", "params": {"place": "the back room"}})
    return e, pc


def _found(e, text):
    return narration.stands_elsewhere(text, here=e.here().name,
                                      places=tuple(p.name for p in e.places()),
                                      **narration.site_words(e))


def _found_before(e, text):
    """The call as it was: the place's name and the names of the places, nothing more."""
    return narration.stands_elsewhere(text, here=e.here().name,
                                      places=tuple(p.name for p in e.places()))


class TestTheTavernTheyStandIn:
    SENTENCES = (
        "The tavern is quiet around you, the only sounds the crackle of the hearth.",
        "He leans in, his voice a low rasp that barely carries over the roar of the tavern.",
        "He looks over his shoulder at the tavern's heavy door, then back to you.",
        "The question hangs in the thick, smoky air of the tavern.",
    )

    def test_the_measured_shapes_were_flagged_and_are_not_now(self):
        e, _ = _in_the_kettle()
        for text in self.SENTENCES:
            assert _found_before(e, text), text      # the defect, as it shipped
            assert _found(e, text) == [], text

    def test_leaving_it_is_not_standing_in_another_one(self):
        """"You leave the woman's words hanging in the smoke of the tavern as you turn
        your back on her" and "Each street takes you further from the tavern" were both
        read as the party standing in a tavern the town does not have."""
        e, _ = _in_the_kettle()
        for text in ("You leave her words hanging in the smoke of the tavern as you turn "
                     "your back on her.",
                     "Each street takes you further from the tavern."):
            assert _found(e, text) == [], text

    def test_a_room_inside_it_is_inside_the_tavern(self):
        """Five of the 13 were in the room founded inside the tavern: "the muffled sounds
        of the tavern" is the building the room is in."""
        e, _ = _in_the_kettle(back_room=True)
        assert e.here().name == "the back room"
        text = "The world outside, the muffled sounds of the tavern, fades to nothing."
        assert _found_before(e, text)
        assert _found(e, text) == []
        assert _found(e, "You are in the Copper Kettle, behind a heavy curtain.") == []

    def test_a_place_the_town_does_not_have_is_still_found(self):
        """The four findings the fix keeps: a tannery walked past in a town that has
        none is still an invention, in a tavern or out of one."""
        e, _ = _in_the_kettle()
        got = _found(e, "You pass the pungent tang of the tannery and the smithy beyond.")
        assert got and got[0][0] in ("the tannery", "the smithy")

    def test_a_tavern_that_exists_is_somewhere_else_when_they_are_not_in_it(self):
        """The kind is a place that EXISTS here: named from the market it is no
        invention, and walking into it is a place they did not go to."""
        e, pc = _in_the_kettle()
        _run(e, pc, {"op": "travel", "params": {"place": "the market"}})
        assert e.here().name == "the market"
        assert _found(e, "The tavern across the way is loud tonight.") == []
        got = _found(e, "You step into the tavern and shake off the rain.")
        assert got and got[0][0] == "the tavern"
        # And the repair is told it exists, not that it was invented.
        review = narration.review("You step into the tavern and shake off the rain. "
                                  "What do you do?", here=e.here().name,
                                  places=tuple(p.name for p in e.places()),
                                  **narration.site_words(e))
        f = next(f for f in review.findings if f.kind == "stands-elsewhere")
        assert "no tavern" not in f.detail and "did not go there" in f.fix_hint


class TestWhatItIs:
    def test_its_name_its_kind_and_what_it_is_in(self):
        e, _ = _in_the_kettle(back_room=True)
        words = places.words_for_here(e.here(), e.places())
        assert words[0] == "back room"
        assert {"tavern", "copper kettle", "way in"} <= set(words)

    def test_the_street_it_opens_off_is_not_inside_it(self):
        """`outside=False` stops at the settlement room a building opens off."""
        e, _ = _in_the_kettle(back_room=True)
        words = places.words_for_here(e.here(), e.places(), outside=False)
        assert "copper kettle" in words and "way in" not in words

    def test_a_generated_room_is_its_own_name_only(self):
        e, _ = _engine()
        assert places.words_for_here(e.here(), e.places()) == ("way in",)

    def test_the_scale_words_survive(self):
        assert places.what_it_is("hamlet") == "a hamlet"

    def test_the_review_reads_it_off_the_engine(self):
        e, _ = _in_the_kettle()
        assert narration.site_words(e)["here_is"][:2] == ("copper kettle", "tavern")
        assert "tavern" in narration.site_words(e)["kinds_here"]

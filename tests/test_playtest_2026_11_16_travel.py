"""Travel, ventures and same-named places: playtest 2026-11-16 (Vesna Kroll, 0.3.8).

Every venture of a kind is minted from the same stock spots, so a city with two sewers holds
two "the sewers", two "the main channel"; the place finder returned the first in the list,
and from inside and on top of the gardens' sewers the walks went half an hour across town to
the great square's. Replayed from play-038-data, beats 228-234.
"""
from __future__ import annotations

import pytest

from gm import interpret, judgement
from rules import places
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world import loader

MIRABALOS = "7ef5e373c993"
WORLD = loader.load_cached("fixtures/pangrella-campaign.json")


class _Empty:
    """Dice under which nothing lives in a venture: every d100 comes up 100."""

    def __init__(self, real):
        self.real = real

    def __getattr__(self, name):
        return getattr(self.real, name)

    def roll(self, notation, modifiers=None, label="", visibility="hidden"):
        if notation == "1d100":
            return self.real.given(100, modifiers, label, notation)
        return self.real.roll(notation, modifiers, label, visibility)


def _city():
    s = Scene(location_id=MIRABALOS)
    s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, _Empty(Dice(seed=3)), world=WORLD)
    e.place_party()
    return s, e


def _run(e, *raws):
    intents = e.validate([{"actor": "pc", "because": "t", "visibility": "hidden", **r}
                          for r in raws], origin="author:test")
    return e.run(intents).outcomes


def _place(e, name):
    return next(p for p in e.places() if p.name == name)


def _two_sewers():
    """The great square's sewers and the gardens', both entered once, party in the
    gardens' — the save's state at beat 228."""
    s, e = _city()
    e.place_party(_place(e, "the great square").id)
    _run(e, {"op": "venture", "params": {"kind": "sewers"}})
    e.place_party(_place(e, "the gardens").id)
    _run(e, {"op": "venture", "params": {"kind": "sewers"}})
    assert s.at.endswith("the-gardens/the-sewers")
    return s, e


def test_the_nearest_of_two_same_named_places_wins():
    """#40/#42: `places.find` gave the first "the main channel" in the list. Nearest in
    the place tree now wins, as CircleMUD's `get_obj_vis` scans the room before the
    world list."""
    s, e = _two_sewers()
    known = e.places()
    assert places.find(known, "the main channel", near=s.at).id.startswith(
        f"{MIRABALOS}~underground:the-gardens/the-sewers/")
    gardens = _place(e, "the gardens").id
    assert places.find(known, "the sewers", near=gardens).id.endswith("the-gardens/the-sewers")
    square = _place(e, "the great square").id
    assert places.find(known, "the sewers", near=square).id.endswith(
        "the-great-square/the-sewers")


def test_standing_over_the_gardens_sewers_goes_down_into_them():
    """#42: at the gardens, "I go down into the sewers" was planned travel "the sewers" +
    venture off the gardens; the walk went half an hour to the great square's sewers and
    the venture was then refused for not being at the gardens."""
    s, e = _two_sewers()
    e.place_party(_place(e, "the gardens").id)
    out = _run(e, {"op": "travel", "params": {"place": "the sewers"}},
               {"op": "venture", "params": {"kind": "sewers", "parent": "the gardens"}})
    assert s.at.endswith("the-gardens/the-sewers"), s.at
    assert all(o.status == "resolved" for o in out), [o.tell for o in out]
    assert "great square" not in " ".join(o.tell for o in out)


def test_a_stock_spot_this_venture_lacks_is_refused_not_walked_to_across_town():
    """#40, beat 228: the gardens' sewers were seeded without a sump, and "along the main
    channel to the sump" climbed out, crossed three districts and arrived at the great
    square's sump after half an hour. Said underground, "the sump" means this sewer's."""
    s, e = _two_sewers()
    was = s.at
    if any(p.name == "the sump" and p.parent == was for p in e.places()):
        pytest.skip("this seed gave the gardens' sewers a sump")
    out = _run(e, {"op": "travel", "params": {"place": "the sump"}})
    assert out[-1].status == "refused"
    assert "no sump in the sewers you are in" in out[-1].tell
    assert s.at == was
    # Its own main channel is a step away and still walked to.
    out = _run(e, {"op": "travel", "params": {"place": "the main channel"}})
    assert s.at.startswith(was + "/"), s.at


def test_a_known_grate_at_the_end_of_a_walk_is_no_second_journey():
    """#41, beat 230: "Go back to the sewers under the gardens" walked to the gardens and
    the venture said "One journey a turn — the rest of the way is the next turn's", and
    was still logged resolved."""
    s, e = _two_sewers()
    e.place_party(_place(e, "the great square").id)
    out = _run(e, {"op": "travel", "params": {"place": "the gardens"}},
               {"op": "venture", "params": {"kind": "sewers", "parent": "the gardens"}})
    assert s.at.endswith("the-gardens/the-sewers"), [o.tell for o in out]
    assert out[-1].status == "resolved"
    assert "One journey a turn" not in out[-1].tell


def test_a_venture_whose_drop_is_refused_is_not_resolved(monkeypatch):
    """#41's second half: a deferred drop logged "resolved"."""
    s, e = _city()
    e.place_party(_place(e, "the gardens").id)
    real = e._op_travel
    monkeypatch.setattr(e, "_op_travel", lambda i, p: e._refuse(i, "barred") if
                        "sewers" in str(i.params.get("place")) else real(i, p))
    out = _run(e, {"op": "venture", "params": {"kind": "sewers"}})
    assert out[-1].status == "refused"


def test_out_of_the_crypt_and_down_into_the_sewers_chains():
    """#31, beat 214: "I climb back out of the crypt and go down into the city's sewers"
    planned a venture off the graveyard from inside the crypt, refused as "You are at the
    crypt, not the graveyard". The walk out is the turn's journey; the drop follows."""
    s, e = _city()
    e.place_party(_place(e, "the graveyard").id)
    _run(e, {"op": "venture", "params": {"kind": "crypt"}})
    assert "the-crypt" in s.at
    out = _run(e, {"op": "venture", "params": {"kind": "sewers", "parent": "the graveyard"}})
    assert out[-1].status == "resolved", out[-1].tell
    assert s.at.endswith("the-graveyard/the-sewers"), s.at


def test_already_in_the_venture_is_no_refusal():
    """#42's tail: the venture beside a travel that already took the party in."""
    s, e = _two_sewers()
    out = _run(e, {"op": "venture", "params": {"kind": "sewers", "parent": "the gardens"}})
    assert out[-1].status == "resolved" and "already" in out[-1].tell


def test_down_into_a_crypt_under_the_town_is_no_change_of_country():
    """#26/#33: the crypt under the city's graveyard told "The ground changes: barrows,
    battlefields and cursed ground" going down and "streets, yards and rooftops" coming
    up. A town's own underground is the town."""
    s, e = _city()
    e.place_party(_place(e, "the graveyard").id)
    down = " ".join(o.tell for o in _run(e, {"op": "venture", "params": {"kind": "crypt"}}))
    assert "The ground changes" not in down and "You go down under" in down
    up = " ".join(o.tell for o in _run(e, {"op": "travel", "params": {"place": "the graveyard"}}))
    assert "The ground changes" not in up and "You come back up into" in up


def test_what_lives_down_there_is_not_left_behind():
    """#39, beat 223: "Left behind: the mite" for a creature only ever "further in"."""
    s, e = _city()
    e.place_party(_place(e, "the great square").id)
    e.dice = Dice(seed=3)                       # let something live there
    for _ in range(12):
        _run(e, {"op": "venture", "params": {"kind": "sewers"}})
        if any(not a.is_pc for a in s.actors.values()):
            break
        e.place_party(_place(e, "the great square").id)
    lives = [a for a in s.actors.values() if not a.is_pc]
    if not lives:
        pytest.skip("nothing came to live in the sewers on this seed")
    up = " ".join(o.tell for o in _run(e, {"op": "travel",
                                           "params": {"place": "the great square"}}))
    assert "Left behind" not in up, up


def test_a_district_is_not_a_person_sought():
    """#45, beat 234: the clicked "I go to the great square." logged a population miss
    for a person called "great square"."""
    assert judgement.person_sought("I go to the great square.") == ""
    assert judgement.person_sought("I go to the east crossing.") == ""
    assert judgement.person_sought("I go to the blacksmith.") == "blacksmith"


def test_leaving_a_venture_owes_the_walk_out_to_its_parent():
    """#31: "climb back out of the crypt" owed no op. Out of a venture is up to the place
    it hangs off (Inform's EXIT from the container you are in)."""
    s, e = _city()
    e.place_party(_place(e, "the graveyard").id)
    _run(e, {"op": "venture", "params": {"kind": "crypt"}})
    frame = {"actions": [{"act": "leave", "place": "the crypt", "span": "climb out of the crypt"}]}
    known = e.places()
    assert "travel" in interpret.ops_for(frame, s, known)
    assert interpret.travel_choices(frame, s, known, WORLD.get(MIRABALOS)) == ("the graveyard",)


def test_the_reader_is_shown_two_moves_as_two_acts():
    """#31/#34: the reader read "find a sewer grate and go down into the sewers" as one
    search. Demonstrations of a find-then-go and a climb-out-then-go are its fix
    (docs/structured-turn.md: the reader's examples, not a keyword list)."""
    acts = {said: [a["act"] for a in f["actions"]] for said, f in interpret._DEMOS}
    assert acts["I find the trapdoor and drop down into the cellars."] == ["search", "go"]
    assert acts["I clamber up out of the cellar and go down to the docks."] == ["leave", "go"]

"""A walk to a fixture of the room moves the token (the gate, 2026-11-11).

The owner: "the character didn't move when he should have, the narration let him go up
the stairs but the character never moved on the map". The turn log of that turn: the line
"I walk up the stair onto the wall-walk above the gate" was read as
`go: the stair (within_place, fixture stair)` and `go: the wall-walk above the gate`; the
act table built nothing for either ("a move inside the place: no travel"); the plan wrote
`travel` to "the wall-walk above the gate", which resolved "You are already at the gate.";
positions stayed {'pc': [2, 3]}; and the planned slot wrote "You climb the stone stairs
and step onto the wall-walk". Neither the tells check nor the read-back flagged it: the
only tell said where the party was (the gate), which the wall-walk does not contradict,
and the read-back's place question counts a walk inside a place as staying.
"""
from __future__ import annotations

from gm import acts_to_ops, beat_verify, interpret
from gm.checks import beat_verified
from rules import fixtures
from rules.bestiary import instantiate

from test_map_fixtures import _at, _kind

GATE = "5bbd0c40345f~urban:the-gate"
LINE = "I walk up the stair onto the wall-walk above the gate"
# The reading as the owner's turn should have read it (the second walk now names its
# fixture: the gate's gallery is "the wall-walk", fixtures.json `names`).
READING = {"question": False, "claims": [], "actions": [
    {"act": "go", "place": "the stair", "within_place": True, "fixture": "stair",
     "span": "walk up the stair"},
    {"act": "go", "place": "the wall-walk above the gate", "within_place": True,
     "fixture": "gallery", "span": "onto the wall-walk above the gate"}]}


def _run(engine, intents):
    return engine.run(engine.validate(intents, origin="author:test"))


def test_the_owners_line_moves_the_token_up_onto_the_wall_walk():
    """The line itself: two walks inside the gate, each now a real `move` the engine
    disposes of — to the stair, then up it onto the wall-walk — and the token ends up
    there at the wall-walk's level. Out of a fight it costs no time; it still happens."""
    s, e, pc = _at(GATE)
    clock = s.clock_minutes
    wall = _kind(s.grid, "gallery")[0]
    assert wall["name"] == "the wall-walk", "the gate's raised floor is not called so"
    rows = acts_to_ops.table(READING, s, sentence=LINE)
    built = [i for r in rows for i in r.intents]
    assert [i["op"] for i in built] == ["move", "move"], [r.record() for r in rows]
    res = _run(e, built)
    at = tuple(s.positions[pc.ref])
    assert at[2:] == (wall["level"],) and list(at[:2]) in wall["squares"], \
        [o.tell for o in res.outcomes]
    tells = " ".join(o.tell for o in res.outcomes)
    assert "up onto the wall-walk" in tells, tells
    assert s.clock_minutes == clock, "a walk inside the place took time"


def test_going_back_down_moves_the_token_back_to_the_floor():
    """ "I go back down": the reader's closed `floor`, from up on the wall-walk, is a move
    to the stair's foot, at floor level."""
    s, e, pc = _at(GATE)
    _run(e, [i for r in acts_to_ops.table(READING, s, sentence=LINE) for i in r.intents])
    assert s.positions[pc.ref][2] > 0
    down = {"question": False, "claims": [], "actions": [
        {"act": "go", "place": "the ground", "within_place": True, "fixture": "floor",
         "span": "go back down"}]}
    rows = acts_to_ops.table(down, s, sentence="I go back down")
    res = _run(e, [i for r in rows for i in r.intents])
    at = tuple(s.positions[pc.ref])
    assert (at[2] if len(at) > 2 else 0) == 0, [o.tell for o in res.outcomes]
    assert "back down to the floor" in " ".join(o.tell for o in res.outcomes)


def test_a_walk_to_the_bar_stands_beside_it_not_in_it():
    """A solid fixture is walked TO: the free floor beside it, never its own square."""
    s, e, pc = _at("5bbd0c40345f~urban:the-tavern")
    bar = _kind(s.grid, "counter")[0]
    square, why = fixtures.walk_to(s, "counter", pc)
    assert square is not None and not why
    assert list(square[:2]) not in bar["squares"] and square[:2] not in s.grid.blocked


def test_no_room_on_the_wall_walk_is_refused_with_the_reason():
    """Somebody on every square: the walk is refused in words, never a move into them."""
    s, e, pc = _at(GATE)
    wall = _kind(s.grid, "gallery")[0]
    from rules.bestiary import instantiate

    for p in wall["squares"]:
        guard = instantiate("guildhand", scene=s, name="Guard")
        s.add(guard, zone="near")
        s.positions[guard.ref] = (*p, wall["level"])
    square, why = fixtures.walk_to(s, "gallery", pc)
    assert square is None and "no room on the wall-walk" in why


def test_the_plans_travel_to_the_place_already_stood_in_is_dropped():
    """The plan's `travel` to "the wall-walk above the gate" answered "You are already at
    the gate." and stood in for the walk. With the reading walking inside the place it is
    dropped, logged — even beside a walk out to the market the same words make."""
    s, e, pc = _at(GATE)
    reading = {**READING, "actions": [
        *READING["actions"], {"act": "go", "place": "the market", "span": "then the market"}]}
    rows = acts_to_ops.table(reading, s, sentence=LINE)
    raw = [{"op": "travel", "actor": "pc", "params": {"place": "the wall-walk above the gate"}},
           {"op": "travel", "actor": "pc", "params": {"place": "the market"}}]
    notes: list = []
    out = acts_to_ops.walk_in_place(raw, rows, reading, s, e.places(), notes=notes)
    assert [r["params"]["place"] for r in out] == ["the market"], out
    assert any("walk inside the place" in n for n in notes), notes


def test_the_reader_may_answer_a_raised_part_and_the_floor():
    """The closed `fixture` answer covers the wall-walk (the gallery kind) and the way back
    down (`floor`); `ground` keeps both and drops a word off the list."""
    kinds = interpret.fixture_kinds()
    assert "gallery" in kinds and fixtures.FLOOR in kinds and kinds[0] == "none"
    frame, dropped = interpret.ground({"question": False, "claims": [], "actions": [
        {"act": "go", "place": "the ground", "within_place": True, "fixture": "floor",
         "span": "go back down"}]}, "I go back down")
    assert frame["actions"][0].get("fixture") == "floor", (frame, dropped)


def test_the_read_back_asks_where_in_the_place_and_flags_the_wall_walk_never_reached():
    """The read-back's half: where the place has a raised floor a stair reaches, the page's
    "step onto the wall-walk" is asked and judged against the token's own level. On the
    owner's turn the token was on the ground."""
    s, e, pc = _at(GATE)
    got = beat_verify._height_of(s, pc)
    assert got == {"heights": ("up on the wall-walk", "down on the floor"),
                   "height": "down on the floor"}
    facts = beat_verify.Facts(start="the gate", end="the gate", places=("the gate",),
                              **got)
    text = ("You climb the stone stairs and step onto the wall-walk, gaining a vantage "
            "point above the gate.")
    claims = beat_verify.claims_of({"player_height": [
        {"where": "up on the wall-walk",
         "quote": "step onto the wall-walk, gaining a vantage point"}]}, facts)
    kept, _dropped = beat_verify.validate(claims, text, facts)
    found = beat_verify.diff(kept, facts, text)
    assert [d.category for d in found] == ["height"], found
    assert found[0].line == "You are down on the floor."
    assert beat_verified._KIND["height"][0] in beat_verified.KINDS, \
        "an undeclared finding kind discards the check's findings"
    # And the question is asked only where a stair reaches a raised floor.
    s.grid.fixtures = [f for f in s.grid.fixtures if f["kind"] not in ("gallery", "stair")]
    assert beat_verify._height_of(s, pc) == {}


def test_going_back_down_never_walks_the_party_out_of_town():
    """Live on this fix, 2026-11-11: "I go back down" was read `go, within_place, fixture
    floor`, the table built the move to the stair's foot, and the plan ALSO wrote a travel
    to the outskirts; `unasked_travel` stands aside for any moving act, so the party left
    Xylorvotha for the desert and the move then ran on the outskirts' ground. When every
    walk the words make is inside the place, no travel is the player's."""
    s, e, pc = _at(GATE)
    _run(e, [i for r in acts_to_ops.table(READING, s, sentence=LINE) for i in r.intents])
    down = {"question": False, "claims": [], "actions": [
        {"act": "go", "within_place": True, "fixture": "floor", "span": "go back down"}]}
    rows = acts_to_ops.table(down, s, sentence="I go back down")
    raw = [{"op": "travel", "actor": "pc", "params": {"place": "the outskirts"}},
           *[i for r in rows for i in r.intents]]
    out = acts_to_ops.walk_in_place(raw, rows, down, s, e.places(), notes=[])
    assert [r["op"] for r in out] == ["move"], out
    # A walk inside AND a walk out keeps the walk out.
    both = {"question": False, "claims": [], "actions": [
        *down["actions"], {"act": "go", "place": "the market", "span": "head to the market"}]}
    raw = [{"op": "travel", "actor": "pc", "params": {"place": "the market"}}]
    assert acts_to_ops.walk_in_place(raw, rows, both, s, e.places(), notes=[]) == raw


def test_the_bar_is_the_counter_even_when_the_reader_says_barrel():
    """The Copper Kettle, 2026-11-12: "I draw my rapier and step behind the bar" was read
    `fixture: barrel`, and the walk stood the player beside the barrel in the open, an
    ogre a square off. The room calls its counter "the bar"; the walker's words win over
    the reader's kind. Words that name nothing here keep the reader's answer, and a walk
    back down (`floor`) is never turned into the stair its words mention."""
    s, e, pc = _at("5bbd0c40345f~urban:the-tavern")
    g = s.grid
    assert fixtures.held_to_words(g, "barrel", "behind the bar step behind the bar") == "counter"
    assert fixtures.held_to_words(g, "barrel", "to the barrel") == "barrel"
    assert fixtures.held_to_words(g, "counter", "over to the counters") == "counter"
    assert fixtures.held_to_words(g, "table", "the corner seat") == "table"
    assert fixtures.held_to_words(g, fixtures.FLOOR, "back down the stair") == fixtures.FLOOR
    reading = {"question": False, "claims": [], "actions": [
        {"act": "go", "place": "behind the bar", "within_place": True, "fixture": "barrel",
         "span": "step behind the bar"}]}
    rows = acts_to_ops.table(reading, s, sentence="I step behind the bar")
    moved = [i for r in rows for i in r.intents if i["op"] == "move"]
    assert moved and "the bar" in moved[0]["because"], [r.record() for r in rows]


def test_in_a_fight_the_bar_is_stood_behind_away_from_the_foe():
    """Same turn: even walked to the right fixture, the nearest side of the bar was the
    ogre's. In a fight the walk takes the side the bar covers from every standing foe
    (CRB p.195 cover, the grid's own `cover_between`); out of a fight, the nearest."""
    from rules.grid import distance

    s, e, pc = _at("5bbd0c40345f~urban:the-tavern")
    bar = [tuple(p) for p in _kind(s.grid, "counter")[0]["squares"]]
    calm, _ = fixtures.walk_to(s, "counter", pc)
    foe = s.add(instantiate("guildhand", scene=s, name="Bruiser"), zone="near")
    # The foe on the player's own side of the bar, by the square a calm walk takes.
    s.positions[foe.ref] = min(
        ((x, y) for x in range(s.grid.width) for y in range(s.grid.height)
         if (x, y) not in s.grid.blocked and (x, y) not in s.occupied()
         and (x, y) != calm[:2] and s.grid.passable((x, y))
         and s.grid.cover_between((x, y), foe.size, (*calm[:2], 0), pc.size,
                                  solid_only=True) == "none"),
        key=lambda p: distance(p, calm[:2]))
    there = s.positions[foe.ref]
    s.sides = {"party": [pc.ref], "foes": [foe.ref]}
    square, why = fixtures.walk_to(s, "counter", pc)
    assert square is not None and not why
    assert s.grid.cover_between(there, foe.size, square, pc.size, solid_only=True) != "none", \
        (square, there)
    assert min(distance(square[:2], b) for b in bar) <= 5


def test_in_a_fight_the_walk_to_the_bar_fits_the_round():
    """Live, 2026-11-12, after the far-side fix: the bar's far side was 35 ft away with 30
    ft to spend; the move the table built was refused as illegal at every one of seven
    attempts and the turn fell to narration. In a fight the walk ends on a square this
    round's movement reaches (the engine's own `reachable`), or is refused in words.

    And never on an exposed side when the bar has a covered one: the next live try took
    the one side in reach, beside the bruiser in the open, and was sapped at AC 15."""
    s, e, pc = _at("5bbd0c40345f~urban:the-tavern")
    bar = [tuple(p) for p in _kind(s.grid, "counter")[0]["squares"]]
    foe = s.add(instantiate("guildhand", scene=s, name="Bruiser"), zone="near")
    s.sides = {"party": [pc.ref], "foes": [foe.ref]}
    s.initiative, s.turn = [(pc.ref, 10), (foe.ref, 5)], 0
    g = s.grid
    for start in [(x, y) for x in range(g.width) for y in range(g.height)
                  if g.passable((x, y)) and (x, y) not in g.blocked and not g.ground((x, y))
                  and (x, y) != tuple(s.positions[foe.ref][:2])]:
        s.positions[pc.ref] = start
        square, why = fixtures.walk_to(s, "counter", pc)
        there = tuple(s.positions[foe.ref])

        def covered(p):
            return g.cover_between(there, foe.size, (*p[:2], 0), pc.size,
                                   solid_only=True) != "none"
        sides = {(b[0] + dx, b[1] + dy) for b in bar
                 for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))} - set(bar)
        if square is None:
            continue
        reach = g.reachable(start, pc.speed_feet, size=pc.size,
                            occupied=s.occupied(ignore=pc.ref))
        assert square[:2] in reach, (start, square, pc.speed_feet)
        if any(covered(p) and g.passable(p) and p not in g.blocked for p in sides):
            assert covered(square), (start, square, there)


def test_hiding_behind_the_bar_walks_there_first():
    """Live 2026-11-12, twice in two fights: "duck behind the nearest stall" and "slip
    around behind the bar" were read as stealth with the fixture as its `place`; no walk
    was built, the player stayed in the open and the hide was refused. Stealth whose place
    names a fixture of this room moves there first, then hides; one naming nothing here
    ("into the crowd") moves nobody."""
    s, e, pc = _at("5bbd0c40345f~urban:the-tavern")

    def built(place):
        reading = {"question": False, "claims": [], "actions": [
            {"act": "stealth", "place": place, "span": f"slip {place}"}]}
        return [i["op"] for r in acts_to_ops.table(reading, s, sentence=f"I slip {place}")
                for i in r.intents]

    assert built("behind the bar")[:1] == ["move"], built("behind the bar")
    assert "move" not in built("into the crowd")


def test_foes_on_both_sides_still_leave_cover_from_one():
    """The market, 2026-11-12: a lookout north and a cutpurse south of the nearest stall,
    no square of it covered from both, and "duck behind the nearest stall" was refused
    outright though one side hid the player from the cutpurse. The walk takes the reachable
    square covered from the most foes; it is refused only when none covers from any."""
    s, e, pc = _at("5bbd0c40345f~urban:the-tavern")
    g = s.grid
    west = s.add(instantiate("guildhand", scene=s, name="West"), zone="near")
    east = s.add(instantiate("guildhand", scene=s, name="East"), zone="near")
    # One foe at the bar's west end, one off its north-east corner: the square behind it
    # from both is out of this round's reach, a square behind it from one is not.
    s.positions[pc.ref], s.positions[west.ref], s.positions[east.ref] = (4, 4), (4, 6), (6, 5)
    s.sides = {"party": [pc.ref], "foes": [west.ref, east.ref]}
    s.initiative, s.turn = [(pc.ref, 10), (west.ref, 5), (east.ref, 4)], 0
    square, why = fixtures.walk_to(s, "counter", pc)
    assert square is not None, why
    assert any(g.cover_between(s.positions[f.ref], f.size, square, pc.size, solid_only=True)
               != "none" for f in (west, east)), square
    assert square[:2] in g.reachable((4, 4), pc.speed_feet, size=pc.size,
                                     occupied=s.occupied(ignore=pc.ref))


def test_the_nearest_stall_is_the_one_walked_to():
    """The market, 2026-11-12: "duck behind the nearest stall" walked the player 30 ft to
    a stall that hid them from both thugs, past the nearest one. The owner: "if i say go to
    the nearest stall that is were i should go unless its not possible for some reason".
    The walk takes the nearest of the kind it can reach a side of, wherever cover is."""
    from rules.grid import distance

    s, e, pc = _at("5bbd0c40345f~urban:the-market")
    stalls = _kind(s.grid, "stall")
    assert len(stalls) > 1
    south = s.add(instantiate("guildhand", scene=s, name="Cutpurse"), zone="near")
    north = s.add(instantiate("guildhand", scene=s, name="Lookout"), zone="near")
    s.sides = {"party": [pc.ref], "foes": [south.ref, north.ref]}
    s.initiative, s.turn = [(pc.ref, 10), (south.ref, 5), (north.ref, 4)], 0
    # Found by search: from here the most-covered square of any stall was 30 ft west,
    # the nearest stall covers from one thug only.
    s.positions[pc.ref], s.positions[south.ref], s.positions[north.ref] = \
        (14, 7), (13, 14), (15, 0)
    here = (14, 7)
    near = min(stalls, key=lambda f: min(distance(here, tuple(p)) for p in f["squares"]))
    square, why = fixtures.walk_to(s, "stall", pc)
    assert square is not None, why
    assert min(distance(square[:2], tuple(p)) for p in near["squares"]) <= 5, (square, near)


def test_drawing_the_rapier_puts_it_in_hand():
    """Live 2026-11-12, three fights running: "I draw my rapier and duck behind the
    nearest stall" was read `use: my rapier`, owed no op, and the page said "You draw
    your rapier" with the rapier still on the belt. A carried weapon used is drawn."""
    from rules import goods

    s, e, pc = _at("5bbd0c40345f~urban:the-tavern")
    goods.stow(pc, "rapier")
    assert "rapier" not in str(pc.equipped or "").lower()
    reading = {"question": False, "claims": [], "actions": [
        {"act": "use", "object": "my rapier", "span": "draw my rapier"}]}
    built = [i for r in acts_to_ops.table(reading, s, sentence="I draw my rapier")
             for i in r.intents]
    assert [i["op"] for i in built] == ["wear"], built
    e.run(e.validate([dict(built[0], because="draws")]))
    assert "rapier" in str(pc.equipped or "").lower()
    again = [i for r in acts_to_ops.table(reading, s, sentence="I draw my rapier")
             for i in r.intents]
    assert again == []                       # already in hand: nothing to draw


def test_a_square_named_by_its_coordinate_is_walked_to():
    """The owner, 2026-11-12: "display coordinates on the map so that the user can be
    precise about where he wants to stand even outside of combat". The board prints
    letters across and numbers down (03-offers-and-map.js `sqName`); a walk naming one
    goes there, a solid one is refused in words, and nothing else reads as a square."""
    s, e, pc = _at("5bbd0c40345f~urban:the-tavern")
    g = s.grid
    assert fixtures.square_name((0, 0)) == "A1" and fixtures.square_name((2, 4)) == "C5"
    assert fixtures.square_name((27, 0)) == "AB1"
    free = next((c, r) for r in range(g.height) for c in range(g.width)
                if (c, r) not in g.blocked and g.passable((c, r))
                and (c, r) not in s.occupied() and not g.ground((c, r)))
    solid = next(iter(sorted(g.blocked)))

    def walk(place):
        reading = {"question": False, "claims": [], "actions": [
            {"act": "go", "place": place, "within_place": True, "span": f"go to {place}"}]}
        return acts_to_ops.table(reading, s, sentence=f"I go to {place}")

    [row] = walk(fixtures.square_name(free).lower())
    assert [i["params"]["square"][:2] for i in row.intents] == [list(free)], row.intents
    [row] = walk(fixtures.square_name(solid))
    assert not row.intents and "solid" in row.nowhere
    assert fixtures.square_said(g, "I GO TO THE BAR") is None
    assert fixtures.square_said(g, "A1 or B2") is None

"""Hex sites are real sites, and a rumoured way in is found at its landmark (playtest
2026-11-20 #1 and #2; research note docs/research/2026-11-20-hex-sites.md).

Every test runs once per export (`worlds`): fixes are world-agnostic (2026-09-28).
"""
from __future__ import annotations

import pytest

from gm import acts_to_ops, judgement
from rules import cards as cards_mod
from rules import dungeons, heard_places, hexes, ontheway
from rules import places as places_mod
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene


def _party(world, town=None, seed=3):
    town = town or world.play["settlements"][0]["id"]
    s = Scene(location_id=town)
    pc = instantiate("guildhand", scene=s, name="PC")
    pc.kind = "pc"
    pc.hp = pc.hp_base = 60
    s.add(pc)
    e = Engine(s, Dice(seed=seed), world=world)
    e.place_party("")
    return s, e, pc


@pytest.fixture
def quiet_road(monkeypatch):
    monkeypatch.setattr(ontheway, "road", lambda *a, **k: None)


def _move(e, to, face=20):
    r = e.run(e.validate([{"op": "hex_move", "actor": "pc", "params": {"hex": list(to)}}]))
    if r.awaiting:
        r = e.resume(face)
    return r


def _to_a_site(world, seed=3):
    from tests.test_hex_travel import _site_town

    s, e, pc = _party(world, _site_town(world), seed=seed)
    g = e.hex_world()
    to = next((h for h in e.hex_reach(g) if hexes.site_of(g, *h)), None)
    if to is None:
        pytest.skip("no site beside this town")
    _move(e, to)
    r = e.run(e.validate([{"op": "hex_enter", "actor": "pc", "params": {}}]))
    went = [o for o in r.outcomes if o.op == "venture"][0]
    assert went.status == "resolved", went.tell
    return s, e, pc, went


def _search(e, take=20):
    r = e.run(e.validate([{"op": "check", "actor": e.scene.pc().ref,
                           "params": {"skill": "perception", "search": True, "take": take}}]))
    if r.awaiting:
        r = e.resume(take)
    return [o for o in r.outcomes if o.op == "check"][0]


def test_a_hex_site_always_holds_its_dungeon_at_its_own_head(worlds, quiet_road):
    """Playtest 2026-11-20 #1: the ruins in the forest hex were the venture door's bare
    head and two spots ("the way in", "the open middle"): the 20% way down missed, the 50%
    inhabitant missed, and five searches found nothing. A hex site's way in is always
    there, at the head the party arrives at and searches."""
    s, e, pc, went = _to_a_site(worlds)
    head = next(p for p in s.founded if p["id"] == s.at)
    assert head.get("deeper"), "the site holds no dungeon"
    assert head["deeper"]["spot"] == head["id"]
    assert head["deeper"].get("concept"), "the site's dungeon has no story"


def test_searching_a_hex_site_finds_its_rooms_inhabitants_and_treasure(worlds, quiet_road):
    """Searching in a site must be able to find what is there: taking 20 at the head beats
    the way down's CRB secret-door DC 20 for any PC with a Perception bonus, and the rooms
    behind it are real places with stock (B/X), a climax and a reward."""
    s, e, pc, went = _to_a_site(worlds)
    head_id = s.at
    head = next(p for p in s.founded if p["id"] == head_id)
    if not head["deeper"]["found"]:
        _search(e)
    assert head["deeper"]["found"], "a search taking 20 at the site found nothing"
    rooms = [p for p in s.founded if (p.get("dungeon") or {}).get("of") == head_id]
    assert len(rooms) >= 4
    roles = {p["dungeon"]["role"] for p in rooms}
    assert {"entrance", "climax"} <= roles
    assert any(p["dungeon"]["stock"] == "monster" for p in rooms)
    assert any(p["dungeon"]["cache_gp"] for p in rooms)
    assert any(dungeons.is_quest(c) for c in cards_mod.quests(s))


def test_a_hex_site_is_the_same_site_every_time(worlds, quiet_road):
    """Seeded so every visit is the same: two campaigns that walk into the same hex site
    get the same way in, the same rooms and the same story, whatever their dice."""
    def rooms(seed):
        s, e, pc, _ = _to_a_site(worlds, seed=seed)
        head = next(p for p in s.founded if p["id"] == s.at)
        dungeons.mint(e, head, head["deeper"])
        return (head["deeper"]["feature"]["name"], head["deeper"]["concept"]["tag"],
                [(p["id"], p["dungeon"]["stock"]) for p in s.founded
                 if (p.get("dungeon") or {}).get("of") == head["id"]])

    assert rooms(3) == rooms(11)


def test_an_ordinary_venture_still_rolls_for_its_way_down(worlds):
    """Only the site the world put in a hex is guaranteed its dungeon: a cave gone into
    off the town's outskirts still rolls `dungeons.chance` (the owner's 2026-11-15
    percentage), so the town's ground does not fill up with dungeons."""
    s, e, pc = _party(worlds)
    assert not e._is_hex_site(f"{s.location_id}~underground:the-outskirts/the-cave", "cave")


# --- a rumoured way in, found at its landmark ------------------------------------------

def _woods(e, s):
    """An outside place of the town to hang the rumour off (any world)."""
    out = [p for p in e.places() if places_mod.setting_of(p.id) == "outside"
           and places_mod.location_of(p.id) == s.location_id and p.origin != "venture"]
    if not out:
        pytest.skip("no outside place in this town")
    return out[0]


def _heard_mine(e, s, name="the old mine"):
    woods = _woods(e, s)
    heard_places.record(s, {"name": name, "kind": "mine head", "landmark": woods.id},
                        said_by="c2", line="the treasure deep in the old mine off the woods")
    e.place_party(woods.id)
    assert s.at == woods.id
    return woods


def test_searching_at_a_heard_places_landmark_finds_it(worlds, quiet_road):
    """Playtest 2026-11-20 #2: the carter's rumour put "the old mine" (kind "mine head")
    off the woods; "I search the woods for the cave everyone has a story about" ran tracks
    and secret doors, and the mine was never findable. A search at the landmark looks for
    the heard place, and finding it goes in by the venture door, onto the seeded head the
    town's rumour was spread about."""
    s, e, pc = _party(worlds)
    woods = _heard_mine(e, s)
    out = _search(e)
    head = places_mod.venture_set(woods, "mine")[0]
    assert s.at == head.id, out.tell
    assert "the old mine" in out.tell
    assert not heard_places.ventures_at(s, woods, e.places())


def test_the_heard_place_is_found_whatever_name_the_reader_kept(worlds, quiet_road):
    """The reader may keep the place under a name that is no venture's label ("the
    workings"); the town's rumour card for the venture off that landmark says which it
    is, so it is still the mine that is found."""
    s, e, pc = _party(worlds)
    woods = _heard_mine(e, s, name="the workings")
    head = places_mod.venture_set(woods, "mine")[0]
    assert heard_places.ventures_at(s, woods, e.places()) == []
    cards_mod.open_card(s, cards_mod.Card(id="rumour-x", title="talk", facts=["talk"],
                                          tags=(cards_mod.TAG_RUMOUR,), place=head.id))
    assert [k for _h, k in heard_places.ventures_at(s, woods, e.places())] == ["mine"]
    _search(e)
    assert s.at == head.id


def test_a_low_search_at_the_landmark_finds_nothing_and_says_nothing(worlds, quiet_road):
    """A miss says nothing of what was there (CRB p.564's rule for a missed check)."""
    s, e, pc = _party(worlds)
    woods = _heard_mine(e, s)
    r = e.run(e.validate([{"op": "check", "actor": pc.ref,
                           "params": {"skill": "perception", "search": True}}]))
    if r.awaiting:
        r = e.resume(1)
    out = [o for o in r.outcomes if o.op == "check"][0]
    if out.rolls[0].total >= hexes.FIND_DC["mine"]:
        pytest.skip("this PC's Perception beats the DC on a 1")
    assert s.at == woods.id
    assert "old mine" not in out.tell


def test_a_search_read_as_elsewhere_at_the_landmark_is_built_as_the_search(worlds):
    """The reader read #28 `search`, object "the cave everyone has a story about", place
    "the woods", with no `where`: "elsewhere", which owed no op. Standing at the landmark
    of a heard way in, it is the engine's search."""
    s, e, pc = _party(worlds)
    _heard_mine(e, s)
    frame = {"actions": [{"act": "search", "object": "the cave everyone has a story about",
                          "place": "the woods",
                          "span": "search the woods for the cave everyone has a story about"}]}
    rows = acts_to_ops.table(frame, s, places=e.places(), sentence=frame["actions"][0]["span"])
    built = [b for r in rows for b in r.intents]
    assert any(b["op"] == "check" and b["params"].get("search") for b in built), built


def test_going_to_a_heard_way_in_ventures_and_founds_no_building(worlds):
    """"I go to the old mine": `go_to_heard_place` founded a mine head called the old
    mine beside the woods, a building with no way down; the rumoured way in is the venture
    off its landmark."""
    s, e, pc = _party(worlds)
    woods = _heard_mine(e, s)
    reading = {"actions": [{"act": "go", "place": "the old mine"}]}
    raw = judgement.go_to_heard_place([], "I go to the old mine", s, known=e.places(),
                                      reading=reading)
    assert [r["op"] for r in raw] == ["venture"]
    assert raw[0]["params"] == {"kind": "mine", "parent": woods.id}

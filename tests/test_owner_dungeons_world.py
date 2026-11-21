"""The owner's 2026-11-17 bug list, items 1-5, 7 and 8 (docs: the plan at
pgm-work/owner-bugs-plan-2026-11-18.md). Each test names the item and what was measured in
the owner's own saves (frag: the dungeon run; jack: Featherperch)."""
from __future__ import annotations

from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from world.loader import load_cached

WORLD = load_cached("fixtures/pangrella-campaign.json")


def _party(seed=3):
    town = WORLD.play["settlements"][0]["id"]
    s = Scene(location_id=town)
    pc = instantiate("guildhand", scene=s, name="PC")
    pc.kind = "pc"
    pc.hp = pc.hp_base = 40
    s.add(pc)
    e = Engine(s, Dice(seed=seed), world=WORLD)
    e.place_party()
    return s, e, pc


def _travel(e, pc, where):
    raw = {"op": "travel", "actor": pc.ref, "because": "t", "params": {"place": where}}
    return e.run(e.validate([raw], origin="author:test"))


def test_first_arrival_tells_the_places_own_words():
    """Owner bug 2026-11-17 #1 (jack transcript 287): walking to the cistern told only
    "You are at the cistern now"; its own text, "under the street, and older than it", was
    never said, though places merely walked through had theirs. The first visit says it,
    a second visit does not repeat it."""
    s, e, pc = _party()
    from rules import places as places_mod

    target = next(p for p in e.places() if p.about and p.id != s.at
                  and places_mod.storey_of(p.id) == 0
                  and places_mod.setting_of(p.id) == "in"
                  and not getattr(p, "described_only", False))
    first = " ".join(o.tell for o in _travel(e, pc, target.name).outcomes)
    assert s.at == target.id, first
    about = str(target.about).strip().rstrip(".")
    assert f": {about}." in first, first
    back = s.places_been()[0]
    _travel(e, pc, places_mod.find(e.places(), back).name)
    again = " ".join(o.tell for o in _travel(e, pc, target.name).outcomes)
    assert f": {about}." not in again, again


# --- #2: the room searched, and treasure in monster rooms --------------------------------

def _loot_scene():
    from rules.sheet import load_pc

    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    rat = instantiate("guildhand", scene=s, name="dire rat")
    s.add(rat)
    rat.hp = -20
    s.props.append({"name": "a hoard of bright things", "owner": "", "state": "intact",
                    "turn": 0, "at": s.at,
                    "contents": {"purse": {"gp": 70}, "goods": {}}})
    return s, rat


def _turn(scene, actions, plan=None):
    from gm import acts_to_ops

    frame = {"question": False, "actions": [dict(a) for a in actions], "claims": []}
    rows = acts_to_ops.table(frame, scene)
    raw = acts_to_ops.apply(list(plan or [{"op": "narrate_only"}]), rows, frame, scene)
    raw = acts_to_ops.order(raw, rows)
    engine = Engine(scene, Dice(seed=1))
    return engine.run(engine.validate(raw)).outcomes


def test_searching_the_area_empties_the_rooms_hoard(monkeypatch):
    """Owner bug 2026-11-17 #2 (frag, turn 831): "Search the area for more loot" was read
    `loot: the area`, the dead rat's empty body was looted again ("has nothing left worth
    taking") and the 70 gp hoard on the same floor stayed shut. The room's containers are
    emptied when the words name no body."""
    from gm import interpret
    from rules import holding

    monkeypatch.setattr(interpret, "_READINGS", {})
    s, rat = _loot_scene()
    out = _turn(s, [{"act": "loot", "target": "the area"}],
                plan=[{"op": "loot", "actor": "pc", "params": {"from_": rat.ref}}])
    told = " ".join(o.tell for o in out)
    assert holding.coin_in(s.props[-1]) == 0, told
    assert "empties a hoard of bright things: 70 gold" in told, told


def test_looting_a_named_body_leaves_the_room_alone(monkeypatch):
    """The other half of #2: "loot the dire rat" means the rat, not the hoard beside it."""
    from gm import interpret
    from rules import holding

    monkeypatch.setattr(interpret, "_READINGS", {})
    s, rat = _loot_scene()
    _turn(s, [{"act": "loot", "target": "the dire rat"}])
    assert holding.coin_in(s.props[-1]) == 7000


def test_a_hoard_not_named_as_a_box_can_be_opened(monkeypatch):
    """#2: 16 of the 44 treasure containers the dungeon writes have no noun on the closed
    container list ("a hoard of bright things", "a sarcophagus"), so "open the hoard" was
    never a container at all."""
    from gm import interpret

    monkeypatch.setattr(interpret, "_READINGS", {})
    s, _rat = _loot_scene()
    out = _turn(s, [{"act": "other", "object": "the hoard"},
                    {"act": "look", "object": "what's inside"}])
    assert "Inside: 70 gold" in " ".join(o.tell for o in out)


def test_monster_rooms_roll_for_treasure():
    """#2: frag's six rooms held treasure only in the climax — a monster room had no roll
    at all. B/X gives a monster room 3 in 6. Over 60 dungeons, some non-climax monster rooms
    hold a cache, near half of them."""
    from rules import dungeons

    hit = rooms = 0
    for k in range(60):
        for rec in dungeons.generate(f"~ruins:x{k}/the-ruins", "ruins", f"x{k}/spot",
                                     "ruins", dungeons.FEATURES["ruins"][0], 1):
            d = rec["dungeon"]
            if d["stock"] == "monster" and d["role"] != "climax":
                rooms += 1
                hit += bool(d["cache_gp"])
    assert rooms > 20 and 0.3 < hit / rooms < 0.7, (hit, rooms)


# --- #3: every dungeon's leader can be placed --------------------------------------------

def test_every_tag_places_its_leader_at_low_apl():
    """Owner bug 2026-11-17 #3 (frag): 12 of the 33 dungeon tags could not place their
    leader for a lone level-1 PC. The rat-king's leader (a wererat or a rat swarm, CR 2)
    fell back to one 5 hp dire rat, built up as the boss. Every tag's leader now fits at
    APL -1, 0 and 1 (the climax's hard draw), except the weeping ghost at APL -1: the
    bestiary has no ghost at CR 1 or under, and there the tag's own creatures stand in
    untitled (`stock_room`)."""
    from rules import dungeons, encounter_budget as eb

    missing = []
    for key, tag in dungeons.story()["tags"].items():
        rows = dungeons._spec_rows(tag["leader"])
        for apl in (-1, 0, 1):
            if eb.choose(rows, apl, 100, lambda n: 0, kind="guarded", most=1) is None:
                missing.append((key, apl))
    assert missing == [("weeping-ghost", -1)], missing


def test_the_rat_king_is_a_man():
    """#3: the urchin says the rats do what a man tells them; every leader the rat-king
    tag can draw is a man (the beggar, the wererat), never a swarm."""
    from rules import dungeons

    tag = dungeons.story()["tags"]["rat-king"]
    assert "rat-swarm" not in tag["leader"].get("creatures", [])
    assert "red cap" not in tag["ally"]["notes"]


# --- #4: the same person is never made twice by an article -------------------------------

def test_a_newcomer_with_a_present_actors_name_is_that_actor():
    """Owner bug 2026-11-17 #4 (frag): the beat reader called "lost urchin" new while "the
    lost urchin" (c38) stood in the room, and seen-people made a second urchin; "Left
    behind: the lost urchin, the lost urchin" followed. A newcomer whose words are a
    present actor's name, articles aside, is that actor and nobody new is made."""
    from play.aftermath import seen_people
    from rules.sheet import load_pc
    from tests.beat_reader import stub

    pang = WORLD
    s = Scene(location_id=pang.play["settlements"][0]["id"])
    s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, Dice(seed=3), world=pang)
    e.place_party()
    kid = instantiate("guildhand", scene=s, name="the lost urchin")
    s.add(kid)
    text = "A lost urchin huddles in the shadows, watching you with wide eyes."
    reading = stub.read(text, s, engine=e, who={"a lost urchin": "new"},
                        new=[("a lost urchin", "", "lost urchin", "person")])
    before = set(s.people)
    rows = seen_people.step(stub.ctx(s, reading, text=text, engine=e, world=pang, turn=3))
    assert set(s.people) == before, rows
    assert any(r.get("same_as") == kid.ref for r in rows), rows


# --- #5: a step to a square is no trip elsewhere -----------------------------------------

def test_a_walk_to_a_square_drops_the_plans_travel():
    """Owner bug 2026-11-17 #5 (jack, turn 83): "I move to G3" built the move to G3, and the
    plan's travel to the outskirts ran beside it — an hour's walk, the flying squirrel
    beside G3 "left behind". A walk to a square is a step inside the place, even when the
    reader did not say `within_place`."""
    from gm import acts_to_ops
    from rules import fixtures
    from tests.test_map_fixtures import _at

    s, e, pc = _at("5bbd0c40345f~urban:the-tavern")
    g = s.grid
    free = next((c, r) for r in range(g.height) for c in range(g.width)
                if (c, r) not in g.blocked and g.passable((c, r))
                and (c, r) not in s.occupied() and not g.ground((c, r)))
    name = fixtures.square_name(free)
    reading = {"question": False, "claims": [], "actions": [
        {"act": "go", "place": name, "span": f"I move to {name}"}]}
    rows = acts_to_ops.table(reading, s, sentence=f"I move to {name}")
    built = [i for r in rows for i in r.intents]
    raw = [{"op": "travel", "actor": "pc", "params": {"place": "the outskirts"}}, *built]
    notes: list = []
    out = acts_to_ops.walk_in_place(raw, rows, reading, s, e.places(), notes=notes)
    assert [r["op"] for r in out] == ["move"], (out, notes)


# --- #7: no crowd where the map is empty -------------------------------------------------

JACK_197 = ("You labor through the bustling traffic of the north crossing, your limbs heavy "
            "and slow, before arriving at the great square. You scan the nearby stalls and "
            "crowds, searching for someone who can point you toward the inn. What do you do?")


def test_a_crowd_with_nobody_on_the_map_is_cut():
    """Owner bug 2026-11-17 #7 (jack, transcript 197): the page showed bustling traffic and
    crowds with nobody on the map but Jack. Crowds are never given bodies, so with nobody
    but the party here the crowd sentences go; with anybody here, or a crowd the turn's
    own tells name, they stay."""
    from gm import narration

    text, cut = narration.cut_crowd_from_nowhere(JACK_197, anyone_here=False)
    assert len(cut) == 2 and "crowd" not in text and "traffic" not in text, text
    assert text.endswith("What do you do?")
    assert narration.crowd_from_nowhere(JACK_197, anyone_here=True) == []
    assert narration.crowd_from_nowhere(JACK_197, False, "A crowd gathers to watch.") == []


# --- #8: "the stranger" is never a thing ------------------------------------------------

def test_a_capitalised_kind_of_thing_is_lowercased_not_made_a_stranger():
    """Owner bug 2026-11-17 #8 (frag, 8 times): the name filter replaced every capitalised
    word it did not know, and "your Lucerne hammer" came back "your the stranger hammer".
    Between a possessive or an article and a lowercase noun the word is a kind of thing,
    so it is lowercased; a person the narrator invented is still un-named."""
    from gm import narration

    out, _ = narration.unname_strangers(
        "You close the distance and swing your Lucerne hammer in a devastating blow.", set())
    assert "your lucerne hammer" in out and "stranger" not in out, out
    out, gone = narration.unname_strangers("In the doorway, Vorgath grins at you.", set())
    assert "Vorgath" not in out and gone, out


def test_the_known_names_hold_the_sheets_weapons_abilities_and_skills():
    """#8: the weapon on frag's own sheet, the six abilities and the skills are names the
    GM may use ("Charisma" was un-named too)."""
    from gm.agent import GMAgent

    s, e, pc = _party()
    pc.weapons = ["lucerne-hammer"]
    agent = GMAgent.__new__(GMAgent)
    agent.engine, agent.world = e, WORLD
    known = agent._known_names()
    assert {"Lucerne hammer", "Charisma", "Diplomacy"} <= known

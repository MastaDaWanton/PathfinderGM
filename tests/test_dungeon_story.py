"""A dungeon's story: a concept chosen before any room, and rooms built from it
(rules/dungeons.py `concept_for`, content/dungeons/).

The owner, 2026-11-16: "A proper dungeon cannot just be random rooms and it must hold a
cohesive story/pattern." Measured before this, on 0.3.9: every dungeon's rooms came from
one list of six names per kind of ground, shuffled ("the guardroom", "the ossuary", "the
sealed vault" whatever the place was), each monster room drew whatever the bestiary had
for the terrain, and nothing in the rooms said who built the place, what happened to it or
who holds it now — the narrator had nothing to ground a history in, so it had none.
"""
from __future__ import annotations

import re

import pytest

from rules import cards, dungeons, npcs, places, states
from rules import bestiary
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world import loader

VYRAKON = "5bbd0c40345f"
WORLD = loader.load_cached("fixtures/pangrella-campaign.json")
SLOTS_BUILDERS = {"builders", "users", "town", "where"}
SLOTS_TAGS = {"leader", "lair", "ally", "town", "where", "age"}


@pytest.fixture
def always(monkeypatch):
    monkeypatch.setattr(dungeons, "chance", lambda *a, **k: 100)


def _run(engine, op, params):
    intents = engine.validate([{"op": op, "actor": "pc", "because": "t", "params": params,
                                "visibility": "hidden"}], origin="author:test")
    return engine.run(intents).outcomes


def _engine(seed=11):
    s = Scene(location_id=VYRAKON)
    s.add(load_pc("fixtures/pc-kesst.json"))
    return s, Engine(s, Dice(seed=seed), world=WORLD)


def _slots_in(text: str) -> set[str]:
    return set(re.findall(r"\{(\w+)\}", text))


# --- the authored data ---------------------------------------------------------------------

def test_the_tags_are_thirty_to_forty_whole_situations_every_part_real():
    """The owner's "cohesive story" is the tag: each one gives enemies, a leader, an
    ally, a complication, a signature reward and places for every family it fits, and
    every creature and codex person it names exists. A tag naming a bestiary id that
    does not exist would stock its rooms with nobody, silently."""
    st = dungeons.story()
    tags = st["tags"]
    assert 30 <= len(tags) <= 40, len(tags)
    book = bestiary.imported()
    index = npcs.index()
    for tid, t in tags.items():
        for part in ("enemies", "leader"):
            spec = t[part]
            assert spec.get("people") or spec.get("creatures"), (tid, part)
            for cid in spec.get("creatures") or ():
                assert cid in book, (tid, cid)
                # The world owns its own races: no people of the bestiary's in a tag.
                assert book[cid].get("creature_type") != "humanoid" or cid == "wererat", cid
            for base in spec.get("people") or ():
                assert base in index and index[base]["rank"] < 2, (tid, base)
        assert t["leader"]["title"].startswith("the "), tid
        assert t["ally"]["people"] in index, tid
        assert t["complication"] and t["reward"]["container"] and t["reward"]["said"], tid
        assert t["places"], tid
        for fam, rows in t["places"].items():
            assert fam in ("built", "natural", "dug") and len(rows) == 3, (tid, fam)
        assert len(t["traces"]) == 2 and t["revelation"] and t["rumour"], tid
        assert "{where}" in t["quest"], tid
        for text in (t["ally"]["notes"], t["complication"], t["revelation"], t["rumour"],
                     t["quest"], *t["traces"]):
            assert _slots_in(text) <= SLOTS_TAGS, (tid, text)
        # One sentence: the brief shows a person's note up to its first full stop.
        assert t["ally"]["notes"].count(". ") == 0, (tid, t["ally"]["notes"])


def test_every_kind_and_builder_has_a_story_and_traps_that_fit_it():
    """Every venture kind that can hold a way down has builders, every builder has a tag
    for each ground it is built in, its traps exist, and a builder's slot words are only
    the ones the code fills."""
    st = dungeons.story()
    trap_ids = set(dungeons.traps())
    for kind in dungeons.FEATURES:
        fam = dungeons.family(kind)
        builders = [b for b, row in st["builders"].items()
                    if kind in row["kinds"] and fam in row["rooms"]]
        assert builders, kind
        for bid in builders:
            tags = [t for t, row in st["tags"].items() if fam in row["places"]
                    and ("any" in row["builders"] or bid in row["builders"])]
            assert tags, (kind, bid)
    for bid, b in st["builders"].items():
        assert set(b["traps"]) <= trap_ids, bid
        for fam, rows in b["rooms"].items():
            assert len(rows) == 3, (bid, fam)
        for text in b["traces"]:
            assert _slots_in(text) <= SLOTS_BUILDERS, (bid, text)
    for row in st["users"] + st["ruin"]:
        assert _slots_in(row.get("trace", "")) <= SLOTS_BUILDERS, row["id"]


# --- the concept ---------------------------------------------------------------------------

def test_a_concept_answers_the_ruin_questions_and_is_the_same_every_time():
    """Worlds Without Number's questions, each answered: type, age, builders and purpose,
    how ruined, previous users, current inhabitants, why unlooted, local attitude, tag.
    Seeded off the venture: asked again, the same story."""
    head = f"{VYRAKON}~underground:the-market/the-sewers"
    c = dungeons.concept_for(WORLD, head, "sewers", VYRAKON)
    for key in ("kind", "age", "builders", "purpose", "ruined", "users", "inhabitants",
                "unlooted", "attitude", "tag"):
        assert c[key], key
    assert c == dungeons.concept_for(WORLD, head, "sewers", VYRAKON)
    assert dungeons.concept_for(WORLD, head, "rooftops", VYRAKON) is None


def test_builders_and_users_are_the_worlds_own_names_or_generic_ones():
    """Ground every name: a builder drawn from the world is one of its peoples, nations or
    factions, by name; with no world, the row's generic words — never an invented name.
    And the second layer is never the builders again."""
    known = ({e.name for e in WORLD.entities.values()}
             | {f["name"] for f in WORLD.factions})
    st = dungeons.story()
    generic = ({b["who"] for b in st["builders"].values()}
               | {u["who"] for u in st["users"]})
    grounded = 0
    for i in range(300):
        kind = sorted(dungeons.FEATURES)[i % len(dungeons.FEATURES)]
        c = dungeons.concept_for(WORLD, f"{VYRAKON}~x:y/z-{i}", kind, VYRAKON)
        for layer in ("builders", "users"):
            who = c[layer]["who"]
            if c[layer]["entity"]:
                grounded += 1
                assert any(name in who for name in known), who
            else:
                assert who in generic, who
        assert not c["users"]["entity"] or c["users"]["entity"] != c["builders"]["entity"]
        bare = dungeons.concept_for(None, f"{VYRAKON}~x:y/z-{i}", kind, VYRAKON)
        assert bare["builders"]["who"] in generic and bare["users"]["who"] in generic
    assert grounded > 100, grounded


# --- the rooms -----------------------------------------------------------------------------

def test_rooms_are_the_builders_then_the_tag_with_the_lair_last_and_a_trace_each():
    """The rooms come from the concept: the builders' rooms from the way in, the tag's
    places deeper, the leader's lair the climax; five or six rooms, so the loop is always
    there; the setback a trap of the builders' own where one is in reach; and every room
    one trace of its history, the last the revelation — no slot left unfilled."""
    st = dungeons.story()
    for i in range(120):
        kind = sorted(dungeons.FEATURES)[i % len(dungeons.FEATURES)]
        head = f"{VYRAKON}~x:the-market/the-{kind}-{i}"
        c = dungeons.concept_for(WORLD, head, kind, VYRAKON)
        slots = dungeons.slots_of(c, town="Pangrella", where=f"the {kind} off the market")
        rooms = dungeons.generate(head, kind, head + "/spot", "ruins",
                                  dungeons.FEATURES[kind][0], 3, concept=c, slots=slots)
        b = st["builders"][c["builders"]["id"]]
        t = st["tags"][c["tag"]]
        fam = c["family"]
        names = [r["name"] for r in rooms]
        assert len(rooms) in (5, 6) and len(set(names)) == len(names)
        assert sum(bool(r["exits"]) for r in rooms) == 2                 # the loop
        assert names[0] == b["rooms"][fam][0][0]
        assert names[-1] == t["places"][fam][-1][0] == slots["lair"]
        assert set(names) <= {n for n, _ in b["rooms"][fam]} | {n for n, _ in t["places"][fam]}
        d = [r["dungeon"] for r in rooms]
        assert d[-1]["role"] == "climax" and d[-1]["stock"] == "monster"
        assert d[1]["stock"] == "special"                               # the ally's room
        assert d[-1]["trace"] == dungeons.fill(t["revelation"], slots)
        for x in d:
            assert x["trace"] and "{" not in x["trace"], x
            if x["trap"]:
                own = [k for k in b["traps"] if dungeons.traps()[k]["cr"] <= 4]
                assert x["trap"]["id"] in own or not own, (c["builders"]["id"], x["trap"])
        again = dungeons.generate(head, kind, head + "/spot", "ruins",
                                  dungeons.FEATURES[kind][0], 3, concept=c, slots=slots)
        assert again == rooms


def test_a_sealing_trap_shuts_the_way_back_until_lifted_at_its_printed_dc(always):
    """A tomb's sealing trap: the falling portcullis (6d6, Reflex 20 avoids, DC 25
    Strength lifts it, as d20pfsrd prints it). Sprung, the way back out is shut and the
    walk refused until it is lifted."""
    s, engine = _engine(seed=4)
    spot = engine.here()
    head = "~ruins:x/the-ruins"
    rooms = dungeons.generate(head, "ruins", spot.id, "ruins", dungeons.FEATURES["ruins"][0], 1)
    rooms[0]["dungeon"]["door"] = None
    trap = {"id": "falling-portcullis", "on": "room", "found": False, "armed": True}
    rooms[0]["dungeon"]["trap"] = trap
    s.founded.extend(rooms)
    s.move("pc", rooms[0]["id"])
    s.pc().hp = s.pc().hp_max = 300
    _rolls, fx, said = dungeons.spring(engine, trap, [s.pc()])
    assert rooms[0]["dungeon"]["door"] == {"name": "the fallen portcullis", "state": "stuck",
                                           "force": 25}
    assert any("way back" in b for b in said)
    out = _run(engine, "travel", {"place": spot.id})
    assert s.at == rooms[0]["id"] and "stuck" in out[-1].tell
    s.pc().abilities["str"] = 60
    forced = _run(engine, "break_in", {"how": "force"})
    assert forced[-1].dc == 25 and rooms[0]["dungeon"]["door"]["state"] == "open"


# --- in play -------------------------------------------------------------------------------

def _found(kind="cave", seed=11):
    s, engine = _engine(seed)
    s.pc().hp = s.pc().hp_max = 400
    _run(engine, "venture", {"kind": kind})
    head = next(p for p in s.founded if p["id"] == s.at)
    concept = head["deeper"]["concept"]
    assert concept and not any(p.get("origin") == "dungeon" for p in s.founded)
    _run(engine, "travel", {"place": head["deeper"]["spot"]})
    while not head["deeper"]["found"]:
        _run(engine, "check", {"skill": "perception", "search": True})
    return s, engine, head, concept


def test_walking_the_rooms_tells_each_trace_meets_the_ally_and_finds_the_leader(always):
    """End to end through the ops a turn plans. The concept is on the way down's record
    before any room exists; each room's first entry tells its trace; the second room
    holds the tag's ally, a real friendly person whose note says what they know; the
    climax holds the tag's leader by its title; the quest is titled from the concept."""
    s, engine, head, concept = _found()
    tag = dungeons.story()["tags"][concept["tag"]]
    quest = next(c for c in cards.quests(s) if dungeons.is_quest(c))
    assert quest.title.split()[0] == tag["quest"].split()[0] and "below the cave" in quest.title
    rooms = [p for p in s.founded if (p.get("dungeon") or {}).get("of") == head["id"]]
    s.pc().abilities["str"] = 60
    told = {}
    for r in rooms:
        if s.in_encounter:
            s.end_encounter()
        out = _run(engine, "travel", {"place": r["id"]})
        if s.at != r["id"]:
            _run(engine, "break_in", {"how": "force"})
            out = _run(engine, "travel", {"place": r["id"]})
        assert s.at == r["id"], [o.tell for o in out]
        told[r["id"]] = " ".join(o.tell for o in out)
    for r in rooms:
        assert r["dungeon"]["trace"] in told[r["id"]], r["name"]
    ally_room = rooms[1]
    allies = [a for a in s.people.values() if a.at == ally_room["id"] and not a.is_pc]
    assert len(allies) == 1
    ally = allies[0]
    assert ally.name == f"the {tag['ally']['as']}"
    assert states.attitude_of(ally) == "friendly"
    assert ally.notes and "{" not in ally.notes and ally.notes in told[ally_room["id"]]
    climax = rooms[-1]["dungeon"]
    if climax["foes"]:
        boss = s.people[climax["foes"][0]]
        assert boss.name == tag["leader"]["title"]
        assert tag["leader"]["title"] in told[rooms[-1]["id"]].lower()


def test_the_boss_is_the_tags_leader_and_defeating_it_finishes_the_quest(always):
    """The quest contract kept: completion still reads the climax room's foes. The
    leader brought in there is the boss; down, the quest is finished."""
    for seed in range(11, 40):
        s, engine, head, concept = _found(seed=seed)
        rooms = [p for p in s.founded if (p.get("dungeon") or {}).get("of") == head["id"]]
        last = rooms[-1]
        s.move("pc", last["id"])
        place = places.find(engine.places(), last["id"])
        fx, _bits = dungeons.arrived(engine, place)
        if last["dungeon"]["foes"]:
            break
    else:
        pytest.fail("no seed stocked a leader")
    for ref in last["dungeon"]["foes"]:
        s.people[ref].hp = -20
    assert dungeons.completion(engine, head["id"]) == "boss"


def test_a_dungeon_made_before_concepts_keeps_its_rooms(always):
    """Old saves: rooms already generated are kept as they were — no concept is laid
    over them, no trace told, the old stocking used. A way down recorded before concepts
    and not yet found gets one when its rooms are made."""
    s, engine = _engine(seed=11)
    _run(engine, "venture", {"kind": "cave"})
    head = next(p for p in s.founded if p["id"] == s.at)
    deeper = head["deeper"]
    deeper.pop("concept")
    old = dungeons.generate(head["id"], "cave", deeper["spot"], "underground",
                            deeper["feature"], 1)
    s.founded.extend(old)
    before = [dict(r) for r in old]
    deeper["found"] = True
    assert dungeons.mint(engine, head, deeper) == []
    assert [r["name"] for r in old] == [r["name"] for r in before]
    assert "concept" not in deeper and dungeons.concept_of(head) is None
    title, _fact = dungeons.quest_words(engine, head)
    assert title.startswith("Clear what lies below")
    # Not yet minted, recorded before concepts: it gets one at the find.
    s2, engine2 = _engine(seed=11)
    _run(engine2, "venture", {"kind": "cave"})
    head2 = next(p for p in s2.founded if p["id"] == s2.at)
    head2["deeper"].pop("concept")
    dungeons.mint(engine2, head2, head2["deeper"])
    assert dungeons.concept_of(head2) is not None


def test_the_town_talks_of_a_way_down_before_it_is_found_once(monkeypatch):
    """The hook (the WWN review's "no reason to go there"): in a settlement with a way
    down still unfound, the local attitude reaches the player as talk — a rumour card
    the pull puts in front of the narrator while nobody has carried it, ambient after,
    and resolved once the way down is found."""
    monkeypatch.setattr(dungeons, "chance", lambda *a, **k: 100)
    s, engine = _engine(seed=3)
    s.at = engine.here().id
    dungeons.spread_rumours(engine)
    rumours = [c for c in cards.load(s) if c.is_(cards.TAG_RUMOUR)]
    assert len(rumours) == dungeons.RUMOURS_PER_TOWN
    card = rumours[0]
    assert card.facts[0].startswith(tuple(
        dungeons.fill(a["said"], {"town": "Pangrella"})[:12]
        for a in dungeons.story()["attitudes"]))
    assert "{" not in card.facts[0]
    pulled = cards.thread_to_pull(s, recent=[], turn=1, world=WORLD)
    assert pulled and pulled["id"] == card.id
    cards.note_mentions(s, card.facts[0], turn=2)
    assert not any(c.id == card.id for _n, _w, c in cards.salience(s, recent=[], turn=20))
    # Asked twice, still one.
    dungeons.spread_rumours(engine)
    assert len([c for c in cards.load(s) if c.is_(cards.TAG_RUMOUR)]) == 1
    # Found: no longer talk.
    made = next(places.venture_set(p, k) for p in engine.places() for k in dungeons.FEATURES
                if places.venture_set(p, k)[0].id == card.place)
    kind = places.venture_kind(made[0])
    head = made[0].as_dict()
    dungeons.on_entering(WORLD, s, head, kind, [m.id for m in made[1:]])
    head["deeper"]["found"] = True
    s.founded.extend([head] + [m.as_dict() for m in made[1:]])
    dungeons.settle(engine)
    assert not cards.find(s, card.id).live

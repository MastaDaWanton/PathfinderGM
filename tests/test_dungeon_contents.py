"""The owner's 0.5.0 dungeon (playtest 2026-11-23, items 6-10, O7, O8): what a dungeon
holds is settled once, by the dungeon, and is there the first time; its hoard is things;
its spirit can be spoken to and does not punch; a smith does not gather water off a
dungeon floor."""
from __future__ import annotations

import random
from types import SimpleNamespace

import pytest

from rules import benches, bestiary, dungeons, gathering, ontheway, pricing, scope
from rules import treasure

from tests.test_dungeon_story import _climax_of, _found, _run  # noqa: F401


@pytest.fixture
def always(monkeypatch):
    monkeypatch.setattr(dungeons, "chance", lambda *a, **k: 100)


def _box_in(s, room_id):
    return next(p for p in s.props if p.get("at") == room_id
                and str(p.get("origin", "")).startswith("rule:treasure/"))


def test_the_boss_hoard_is_things_and_they_land_usable(always):
    """O8: "a haunted coffer guarded by a poltergeist held 150 gp and nothing else". The
    coffer is now laid out by Ultimate Equipment's rule (the largest reward that fits, then
    lesser ones, the rest coin). The climax box holds things with little coin left over,
    and emptying it puts a potion on the shelf as a drinkable and a weapon on the weapons
    list, not a name in the pack."""
    s, engine, head, last, told = _climax_of("weeping-ghost", 11)
    box = _box_in(s, last["id"])
    things = dict(box["contents"]["goods"])
    coin = int(box["contents"]["purse"].get("gp", 0))
    assert things and coin * 5 < last["dungeon"]["cache_gp"], box
    pc = s.pc()
    engine._empty_box(SimpleNamespace(id="t", because="t"), pc, box)
    assert not box["contents"]["goods"]
    kinds = {box["hoard"].get(n, "gem").split(":", 1)[0] for n in things}
    assert "alchemy" in kinds and "weapon" in kinds, kinds
    for name in things:
        gid = box["hoard"].get(name, "")
        if gid.startswith("alchemy:"):
            row = next(st for st in pc.stock.values() if st.name == name)
            assert set(row.how) & {"drink", "coat", "apply"}, row.how
        elif gid.startswith("weapon:"):
            assert gid.split(":", 1)[1] in pc.weapons, (gid, pc.weapons)
        assert name not in pc.goods or not gid, name


def test_hoards_mix_potions_magic_arms_and_gems():
    """Over 60 low-level hoards (the APL 1 climax's 312 gp, the 2-in-6 strongbox's 45) every
    kind of reward turns up, and coin is under a tenth of the value laid out."""
    kinds, coin, total = set(), 0, 0
    for i in range(60):
        gp = 312 if i % 2 else 45
        things, ids, left = treasure.hoard(random.Random(i), gp)
        kinds |= {ids.get(n, "gem").split(":", 1)[0] for n in things}
        coin += left
        total += gp
    assert {"alchemy", "magic", "weapon", "gem"} <= kinds, kinds
    assert coin * 10 < total, (coin, total)


def test_the_haunt_has_its_body_and_the_dagger_in_its_lair(always):
    """O8: "no body, no precious item that is keeping the poltergeist tied here". The
    weeping ghost's revelation says its body lies in the lair with a knife in its back;
    both are now things on the room's ground, told on the first entry."""
    s, engine, head, last, told = _climax_of("weeping-ghost", 11)
    here = [p["name"] for p in s.props if p.get("at") == last["id"]]
    assert "the body on the stain" in here and "dagger" in here, here
    assert "dagger still in its back" in told


def test_the_climax_is_priced_a_row_above_the_party():
    """O7, "almost no loot": the boss's coffer was priced as an average fight's (CRB
    Treasure Values per Encounter at the APL). A guarded fight is drawn a step over the
    party, so its treasure is the next row: over 200 seeds at APL 1 the climax's mean
    is near the CR 2 row (550 gp), not the CR 1 row (260 gp)."""
    vals = []
    for i in range(200):
        rooms = dungeons.generate(f"head-{i}", "ruins", "spot", "ruins",
                                  dungeons.FEATURES["ruins"][0], 1)
        vals.append(rooms[-1]["dungeon"]["cache_gp"])
    assert 450 < sum(vals) / len(vals) < 650, sum(vals) / len(vals)


def test_no_road_table_between_dungeon_rooms(always, monkeypatch):
    """Item 7: "The road is not empty: two chickens are on it" in the death room. A room
    under a ruin had the ruin's terrain, so the walk between rooms rolled the road's
    encounter table; the fight it started then kept the room from being stocked until the
    second visit (O7: the poltergeist and the coffer appeared only on the return). Every
    hop below is now the dungeon's own, and no road or street roll is made there."""
    s, engine, head, concept = _found(kind="ruins")
    rooms = [p for p in s.founded if (p.get("dungeon") or {}).get("of") == head["id"]]
    for r in rooms:
        if r["dungeon"]["door"]:
            r["dungeon"]["door"]["state"] = "open"
    calls = []
    monkeypatch.setattr(ontheway, "road", lambda *a, **k: calls.append("road"))
    monkeypatch.setattr(ontheway, "street", lambda *a, **k: calls.append("street"))
    for r in rooms[:3]:
        if s.in_encounter:
            s.end_encounter()
        _run(engine, "travel", {"place": r["id"]})
    assert not calls, calls


def test_gathering_in_a_dungeon_room_draws_nothing_off_the_open_ground(always, monkeypatch):
    """Item 10: an hour's gathering in the narthex drew a clockwork spy sitting on "the
    find of a lifetime". A dungeon's rooms are stocked by the dungeon; the open-ground
    forage table is not asked there."""
    s, engine, head, concept = _found(kind="ruins")
    room = next(p for p in s.founded if (p.get("dungeon") or {}).get("of") == head["id"])
    s.move("pc", room["id"])
    monkeypatch.setattr(gathering, "roll", lambda *a, **k: pytest.fail("rolled"))
    assert engine._gathering_encounter(s.pc(), "ruins", 1, "the smith's supplies",
                                       found={"water": 8}, effects=[]) == ""


def test_water_is_gathered_only_where_water_is():
    """Item 10: "8x Water, came up perfect" in a dry vestibule, and a guarded 24x more.
    Water listed no ground, which the smith's shelf reads as every ground: a desert, a
    ruin, a dungeon floor. It lists its ground now."""
    def water(biome):
        return any(m.id == "water" for m in benches.obtainable("blacksmith", "gathered",
                                                               biome=biome))
    assert not water("ruins") and not water("desert") and not water("underground")
    assert water("grassland") and water("forest") and water("coast")


def test_the_poltergeist_hurls_with_telekinesis_and_has_no_fist():
    """Item 9: the poltergeist "lashes out with an unarmed strike" (+2). Bestiary 2: "A
    poltergeist has no method of attacking apart from telekinesis", a ranged attack of +3.
    The import had put the ability's prose in the ranged column, nothing read it, and the
    body fell back to the fist."""
    pg = bestiary.instantiate("poltergeist")
    printed = pg.stat_block_attacks()
    assert not printed["melee"]
    (tk,) = printed["ranged"][0]
    assert tk["name"] == "telekinesis" and tk["bonuses"] == [3] and tk["dice"] == "3d6"
    assert pg.wielded_key() == "telekinesis"


def test_the_ghost_is_who_the_player_talks_to(always):
    """Item 8: "I talk to the ghost" logged population-miss "ghost" with the poltergeist
    the quest is about in the room. A bodiless undead answers to "ghost" and "spirit",
    read off its block's type and subtype."""
    s, engine, head, last, told = _climax_of("weeping-ghost", 11)
    pg = bestiary.instantiate("poltergeist", scene=s)
    s.add(pg)
    s.move(pg.ref, last["id"])
    assert scope.in_the_room(s, "the ghost") in (pg.ref, *last["dungeon"]["foes"])
    assert {"ghost", "spirit"} <= bestiary.kind_names("poltergeist")
    assert "ghost" not in bestiary.kind_names("wolf")


def test_the_three_words_are_written_and_an_old_save_gets_them(always):
    """Item 6: "the same three words written over and over"; reading them gave nothing,
    because no words existed. The trace names them now, and a dungeon minted with the old
    sentence (the owner's save stands in one) is mended on load."""
    trace = dungeons.story()["tags"]["weeping-ghost"]["traces"][1]
    words = trace.split(":", 1)[1].strip(" .").split()
    assert len(words) == 3, trace
    s, engine, head, last, told = _climax_of("weeping-ghost", 11)
    room = next(p for p in s.founded if (p.get("dungeon") or {}).get("layer") == "tag")
    old = next(iter(dungeons._RETIRED_TRACES))
    room["dungeon"]["trace"] = old
    dungeons.mend_traces(engine)
    assert room["dungeon"]["trace"] == trace


def test_a_gem_sells_at_its_value_a_sword_at_half():
    """Ultimate Equipment, treasure types B and C: gems "can generally be traded for their
    full value". A hoard's garnet is worth its grade's 100 gp at a counter."""
    assert pricing.what_a_shop_pays_for_goods("garnet") == 100.0
    assert pricing.what_a_shop_pays_for_goods("longsword") == 7.5


def test_a_hoard_is_the_same_every_time_and_spends_its_value():
    """The same chest holds the same things whenever it is first opened (seeded), and the
    things and coin add to the value laid out."""
    a = treasure.hoard(random.Random(5), 550)
    assert a == treasure.hoard(random.Random(5), 550)
    things, ids, coin = a
    price = {n: p for pool in treasure._rewards().values() for n, p, _i in pool}
    assert sum(price[n] * c for n, c in things.items()) + coin == pytest.approx(550)

"""What the place maps know beyond the towns stood in (phase 5 of docs/place-map-v2-build-plan.md):
towns an NPC named aloud, and the nations whose map the party read.

The owner's rulings of 2026-11-18 that these hold:
- a town is heard of from what an NPC SAYS only (decision 7), checked against the world's
  own settlements, so a made-up name is never learned (models read, code validates);
- the map is sold at general stores only, of the store's own nation, about 5 gp, 0.5 lb, and
  sells back at the usual rate (decision 6);
- reading takes about 10 minutes; a second copy of a map already read teaches nothing; what a
  map teaches is never forgotten.

And one defect the towns list closes: before it, "Koradin" in a carter's line was read by the
places call as a place THIS town lacked, recorded as heard of, and the next walk there founded
a "Koradin" inside the walls.

World-agnostic (the standing instruction of 2026-09-28): each runs on Aurvantis, Pangrella and
the synthetic world.
"""
from __future__ import annotations

from play import atlas
from play.aftermath import places_heard
from rules import goods, maps, market, pricing
from rules import gear as gear_mod
from rules.bestiary import instantiate
from tests.beat_reader import stub
from tests.test_atlas import _party, _settlement_ids


def _other_town(world, sid):
    """Another settlement of the world, by name."""
    return next(world.get(i) for i in _settlement_ids(world) if i != sid)


def _says(world, line: str, towns=(), places=(), by_player=False):
    """One line in a beat, said by an NPC (or the player), the places call's answer stubbed
    with `towns`, and the beat's places step applying it."""
    sid = _settlement_ids(world)[0]
    s, e, pc = _party(world, sid)
    speaker = pc if by_player else instantiate("guildhand", scene=s, name="the carter")
    if not by_player:
        s.add(speaker)
    text = f"The carter leans on the wheel. '{line}'"
    said = [{"who": speaker.ref, "to": "you", "line": line}]
    prefix = " ".join(line.split()[:3])
    reading = stub.read(text, s, engine=e, said=said, lines={prefix: (speaker.ref, "you")},
                        towns=[(prefix, t) for t in towns],
                        places=[(prefix, *p) for p in places])
    ctx = stub.ctx(s, reading, text=text, engine=e, said=said, turn=12, stage="beat")
    return s, e, places_heard.step(ctx), reading, speaker


def test_a_town_an_npc_names_is_heard_of_once(worlds):
    """Named in a carter's line, the town is known from then on, with who said it; named
    again, the first telling stands."""
    sid = _settlement_ids(worlds)[0]
    far = _other_town(worlds, sid)
    line = f"I came down the road from {far.name} two days back."
    s, e, rows, _reading, carter = _says(worlds, line, towns=[far.name])
    assert s.heard_towns[far.id]["who"] == "the carter" and s.heard_towns[far.id]["turn"] == 12
    assert [r["kind"] for r in rows] == ["heard-of-town"]
    from rules import heard_towns

    assert heard_towns.record(s, far.id, who="somebody else") == {}
    assert s.heard_towns[far.id]["who"] == "the carter"
    # On the wire, by the speaker's name; never the speaker's ref.
    heard = atlas.known_places(e, worlds)["heard"]
    assert heard[far.id]["who"] == "the carter" and carter.ref not in str(heard)


def test_a_made_up_town_is_refused(worlds):
    """A name that is no settlement of this world teaches nothing, and says why."""
    line = "My cousin farms out past Varnholt Mere, near the old ford."
    s, e, rows, reading, _ = _says(worlds, line, towns=["Varnholt Mere"])
    assert s.heard_towns == {} and rows == []
    assert any(d.get("why") == "no town of that name" for d in reading.dropped)


def test_the_players_own_line_teaches_no_town(worlds):
    """The player saying a town's name is not being told of it."""
    sid = _settlement_ids(worlds)[0]
    far = _other_town(worlds, sid)
    s, e, rows, _reading, _ = _says(worlds, f"I am bound for {far.name}.", towns=[far.name],
                                    by_player=True)
    assert s.heard_towns == {}


def test_a_town_named_is_not_a_place_in_this_town(worlds):
    """The defect: the places call listed the far town as a place this town lacked. A name
    that is one of the world's settlements is dropped from the places, never founded here."""
    sid = _settlement_ids(worlds)[0]
    far = _other_town(worlds, sid)
    line = f"Take the north road to {far.name}, it is a long day."
    s, e, rows, reading, _ = _says(worlds, line, towns=[far.name],
                                   places=[(far.name, "other", "none")])
    assert all(h["name"].lower() != far.name.lower() for h in s.heard_places)
    assert any(d.get("why") == "a town elsewhere" for d in reading.dropped)
    assert far.id in s.heard_towns


def test_the_map_is_sold_at_general_stores_only():
    """Every counter of the market and every place's own counter: the map is on the general
    store's shelf and no other."""
    shops = [market.COUNTER_PREFIX + str(x["id"]) for x in market._shops()]
    selling = [k for k in shops + ["tavern", "smithy", "laboratory", "tannery", "market"]
               if any(getattr(g, "key", "") == maps.KEY for g in goods.goods_at(k))]
    assert selling == [market.COUNTER_PREFIX + "general"]


def test_a_bought_map_is_of_the_stores_nation_and_read_once(worlds):
    """Bought in a town, it is named for that town's nation; read, it takes ten minutes and
    puts the nation among the maps read; read again, nothing changes and no time passes.
    Carried, it weighs 0.5 lb and is worth its 5 gp."""
    sid = _settlement_ids(worlds)[0]
    s, e, pc = _party(worlds, sid)
    nation = maps.nation_of(worlds, sid)
    good = goods.good(maps.KEY)
    from dataclasses import replace

    called = maps.named(worlds, sid)
    assert called == f"map of {worlds.get(nation).name}"
    goods.deliver(s, pc, replace(good, name=called), 1)
    mid = next(k for k, st in pc.stock.items() if st.base == called)
    t0 = s.clock_minutes
    first = e.run(e.validate([{"op": "use_item", "actor": pc.ref,
                               "params": {"item": mid, "how": "read"}}],
                             origin="author:test")).outcomes[0]
    assert first.status == "resolved" and s.maps_read == [nation]
    assert s.clock_minutes - t0 == maps.READ_MINUTES
    assert called in first.tell
    second = e.run(e.validate([{"op": "use_item", "actor": pc.ref,
                                "params": {"item": mid, "how": "read"}}],
                              origin="author:test")).outcomes[0]
    assert s.maps_read == [nation] and s.clock_minutes - t0 == maps.READ_MINUTES
    assert "nothing" in second.tell
    assert pc.stock[mid].count == 1   # reading spends no copy
    assert gear_mod._good_weight(called, 1) == 0.5
    assert pricing.goods_worth(called) == 5.0 and goods.unit_price(called) == 5.0
    assert atlas.known_places(e, worlds)["maps"] == [nation]


def test_known_places_survive_a_save(tmp_path):
    """Heard towns and maps read are saved with the scene and read back (a real save and
    load, the way tests/test_drink_in_a_fight.py proves its record)."""
    from django.test import override_settings

    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        c = cm.new_campaign("map-knowledge-saved")
        c.scene.heard_towns = {"a1b2c3": {"who": "the carter", "from": "", "line": "x",
                                          "turn": 3}}
        c.scene.maps_read = ["n1"]
        again = cm.Campaign.load(c.save())
        assert again.scene.heard_towns == c.scene.heard_towns
        assert again.scene.maps_read == ["n1"]


# --- across country between wild places -------------------------------------------------------

def _reaches_town(world):
    """A settlement with two or more reaches of open ground round it, and a party there."""
    from rules import outskirts

    for sid in _settlement_ids(world):
        s, e, pc = _party(world, sid)
        reaches = [p for p in e.places() if outskirts.is_reach(p)]
        if len(reaches) >= 2:
            return s, e, pc, reaches
    return None


def test_every_reach_is_one_step_from_every_other(worlds):
    """The owner, 2026-11-19: every reach joins every other, and the way is as long as the
    farther reach lies from town. Before, the desert to the ridgelines was walked back
    through the outskirts: both reaches' miles, 3 + 4 on Ashwatch."""
    import pytest

    from play import exits
    from rules import outskirts

    got = _reaches_town(worlds)
    if got is None:
        pytest.skip("no settlement here has two reaches of open ground")
    s, e, pc, reaches = got
    a, b = reaches[0], reaches[1]
    assert b.id in a.exits and a.id in b.exits
    e.place_party(a.id)
    row = next(x for x in exits.exits(e, worlds) if x["id"] == b.id)
    assert row["group"] == "outside" and not row["journey"]
    far = max((a, b), key=lambda p: p.miles)
    want = outskirts.hop_minutes(far, far, "town", pc.speed_feet)
    assert outskirts.hop_minutes(a, b, "town", pc.speed_feet) == want
    t0 = s.clock_minutes
    out = e.run(e.validate([{"op": "travel", "actor": pc.ref, "params": {"place": b.id}}],
                           origin="author:test")).outcomes
    assert s.at == b.id, out[-1].tell
    assert s.clock_minutes - t0 == want


def test_the_region_draws_a_known_way_between_wild_places():
    """The way across country is on the Region as a track between the two hexes, drawn from
    the chart's own edges (what the exits row offers), never worked out on the page."""
    from pathlib import Path

    src = (Path(__file__).resolve().parent.parent / "play" / "static" / "js"
           / "places-board.js").read_text(encoding="utf-8")
    region = src[src.index("function nationMap("):src.index("function downArrow(")]
    assert "(v.pf.edges || []).forEach(ed =>" in region

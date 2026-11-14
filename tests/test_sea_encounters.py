"""A day at sea meets something, now and then (`ontheway.sea`, `Engine._met_at_sea`,
`_pirates_come_aboard`, `_sea_settled`); a storm grounds the bow (`states.NO_RANGED_WEAPONS`);
a long board opens filling its box (03-offers-and-map.js `flatTurned`, 24-map-zoom.js).

Owner, 2026-11-13: "fix what isnt fixed yet before we cut a release". Measured the same day:
a voyage rolled weather and nothing else — no pirate sail, no sea creature, the ship-to-ship
bands reachable only by a scheme or a test — and a storm's "-8 Perception" landed while its
"ranged weapon attacks impossible" (CRB p.438) was read by nothing: a bow loosed in a gale
hit as on a calm day.
"""
from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from rules import encounter_budget, npcs, ontheway, ships, states
from rules.activeeffect import ActiveEffect
from rules.dice import Dice
from tests.test_ships_at_sea import _at_port, _journey
from tests.test_ships import _do


def _forced(monkeypatch, kind: str, aggressive: bool = True):
    """The day's check, made to find `kind` once (then nothing), the creature drawn by the
    real budgeted picker."""
    real = ontheway._the_land
    left = [kind]

    def sea(dice, level=1, *, apl=None, danger=1.0):
        if not left:
            return None
        left.pop()
        if kind == "creature":
            got = real(dice, "water", level, apl, keep=ontheway.open_water)
            return ontheway.Meeting(kind="creature", roll=90, creature=got.row,
                                    template=str(got.row["id"]), count=got.count,
                                    aggressive=aggressive)
        return ontheway.Meeting(kind=kind, roll=50, count=0, aggressive=kind == "pirates",
                                template=str((npcs.choose(["pirate"], level) or {}).get("id")))

    monkeypatch.setattr(ontheway, "sea", sea)


def _quiet_weather(monkeypatch):
    monkeypatch.setattr(ships, "day_at_sea", lambda dice, level: "calm")


# --- the table -------------------------------------------------------------------------------

def test_the_day_at_sea_is_one_published_check_and_volatility_moves_only_the_danger():
    """One check a day at the road's published 20% (UW p.127's rate; one a day as PF2e's GMG
    rolls travel). Over 6,000 seeded days: the hit rate at the uneasy default sits near 20%,
    half the hits are a passing sail, and lawless water doubles the pirates and creatures
    while leaving the merchant and the patrol where they were."""
    counts = {}
    for danger in (1.0, 2.0):
        dice = Dice(seed=11)
        got = [ontheway.sea(dice, 3, apl=3, danger=danger) for _ in range(6000)]
        kinds = [m.kind for m in got if m is not None]
        counts[danger] = {k: kinds.count(k) for k in ("merchant", "naval", "pirates",
                                                     "creature")}
    calm = counts[1.0]
    assert 1050 <= sum(calm.values()) <= 1350, calm           # 20% of 6,000 = 1,200
    assert 0.4 <= (calm["merchant"] + calm["naval"]) / sum(calm.values()) <= 0.6, calm
    wild = counts[2.0]
    assert wild["pirates"] + wild["creature"] > 1.6 * (calm["pirates"] + calm["creature"])
    assert abs(wild["merchant"] - calm["merchant"]) < 0.25 * calm["merchant"], (calm, wild)


def test_the_open_sea_stocks_salt_water_creatures_only():
    """The bestiary's `water` biome is fresh and salt together: an otter, a naiad, a kappa
    and a river drake were all a ship's possible mid-ocean meeting."""
    from rules import bestiary

    rows = bestiary.search(biome="water", cr_max=4, stated=True, limit=5000)
    kept = {r["name"] for r in rows if ontheway.open_water(r)}
    assert {"Shark", "Sahuagin", "Squid", "Sea Hag"} <= kept, kept
    assert not kept & {"Otter", "Naiad", "Kappa", "River Drake", "Electric Eel",
                       "Medium Fire Elemental"}, kept


# --- what it does on the voyage ----------------------------------------------------------------

def test_a_passing_sail_is_told_and_the_ship_sails_on_after(monkeypatch):
    scene, engine, _pc = _at_port()
    _journey(engine)
    _quiet_weather(monkeypatch)
    _forced(monkeypatch, "merchant")
    out = _journey(engine)
    assert "merchantman" in out.tell, out.tell
    assert any(e.get("kind") == "sea_encounter" and e.get("origin") == "rule:sea-encounter"
               for e in out.effects)
    assert not scene.sea and engine.aboard().days_left > 0, "the day stops at the meeting"
    _journey(engine)
    assert scene.location_id == "6953424c8a82", "sailed on to Zhilvarnia"


def test_a_pirate_sail_closes_and_boards_the_party_deck_budgeted_as_wandering(monkeypatch):
    """Pirates are the existing bands: sighted at `distant`; the party runs or closes, and a
    pirate ship that comes alongside boards THEIR deck, where the fight starts. The boarders
    are the rail's count trimmed by the wandering mix: at most the challenging budget."""
    for seed in range(4):
        scene, engine, pc = _at_port(seed=seed)
        _journey(engine)
        _quiet_weather(monkeypatch)
        _forced(monkeypatch, "pirates")
        out = _journey(engine)
        assert "Pirates" in out.tell and scene.sea["range"] == "distant", out.tell
        theirs = engine.vessel(scene.sea["theirs"])
        assert theirs is not None and ships.kind_of_id(theirs.id) == theirs.kind
        refused = _journey(engine)
        assert refused.status == "refused" and "sheer off" in refused.tell
        _do(engine, "close")
        out = _do(engine, "close")
        foes = scene.sea["foes"]
        assert foes and "over the rail" in out.tell, out.tell
        ours = ships.deck_of(engine.aboard())
        assert all(scene.people[r].at == ours for r in foes), "they board OUR deck"
        assert all(scene.people[r].name.endswith("pirate") for r in foes)
        assert scene.initiative and set(foes) <= set(scene.sides["them"])
        each = encounter_budget.xp_of(npcs.choose(["pirate", "sailor"], pc.level))
        apl = encounter_budget.party_apl(scene)
        assert len(foes) == 1 or len(foes) * each <= encounter_budget.budget(
            apl + encounter_budget.TIERS["challenging"]), (len(foes), each, apl)


def test_the_voyage_goes_on_once_the_boarders_are_down(monkeypatch):
    scene, engine, pc = _at_port()
    _journey(engine)
    _quiet_weather(monkeypatch)
    _forced(monkeypatch, "pirates")
    _journey(engine)
    _do(engine, "close")
    _do(engine, "close")
    assert _journey(engine).status == "refused", "not while there is fighting on deck"
    for ref in scene.sea["foes"]:
        scene.people[ref].hp = -20
    scene.initiative = []
    out = _journey(engine)
    assert "cut loose" in out.tell and not scene.sea, out.tell
    assert scene.location_id == "6953424c8a82", out.tell


def _pirates_sighted(monkeypatch, seed=4, their_kind=None):
    scene, engine, pc = _at_port(seed=seed)
    _journey(engine)
    _quiet_weather(monkeypatch)
    _forced(monkeypatch, "pirates")
    _journey(engine)
    if their_kind:
        theirs = engine.vessel(scene.sea["theirs"])
        theirs.kind = their_kind
        engine._keep_vessel(theirs)
    return scene, engine, pc


def test_running_from_pirates_at_equal_speed_is_a_contest_of_helms(monkeypatch):
    """Measured 2026-11-13: sheering off at `distant` always escaped, so a pirate sail was
    a fight only for a party that wanted one. Two hulls of 60 ft now race on opposed
    helm checks (Profession (sailor), or Wisdom untrained), engine-rolled and hidden; over
    twelve seeds both outcomes happen, and each is told with the two totals."""
    outcomes = set()
    for seed in range(12):
        scene, engine, _pc = _pirates_sighted(monkeypatch, seed)
        assert engine.aboard().speed == engine.vessel(scene.sea["theirs"]).speed == 60
        out = _do(engine, "sheer off")
        chase = next(e["chase"] for e in out.effects if e.get("chase"))
        assert "the helms" in out.tell and len(out.rolls) >= 2, out.tell
        assert all(r.visibility == "hidden" for r in out.rolls)
        if chase == "escaped":
            assert not scene.sea and "only the sea" in out.tell
            _journey(engine)
            assert scene.location_id == "6953424c8a82"
        else:
            assert chase == "lost" and scene.sea["range"] == "closing", out.tell
        outcomes.add(chase)
    assert outcomes == {"escaped", "lost"}, outcomes


def test_a_faster_pirate_gains_every_leg_and_boards(monkeypatch):
    """A galley (90 ft) against the party's sailing ship (60 ft): the faster hull gains a
    band a leg, no roll, and alongside she comes across."""
    scene, engine, _pc = _pirates_sighted(monkeypatch, their_kind="galley")
    out = _do(engine, "sheer off")
    assert not out.rolls and "she is the faster" in out.tell and scene.sea["range"] == "closing"
    out = _do(engine, "sheer off")
    assert scene.sea["range"] == "alongside" and scene.sea["foes"], out.tell
    assert scene.initiative


def test_a_slower_pirate_is_left_behind(monkeypatch):
    scene, engine, _pc = _pirates_sighted(monkeypatch, their_kind="keelboat")
    _do(engine, "close")                                     # bowshot
    out = _do(engine, "sheer off")
    assert scene.sea["range"] == "distant" and "the faster hull is yours" in out.tell
    out = _do(engine, "sheer off")
    assert not scene.sea and "only the sea" in out.tell


def test_boarding_the_pirates_starts_the_fight_on_their_deck(monkeypatch):
    scene, engine, _pc = _at_port()
    _journey(engine)
    _quiet_weather(monkeypatch)
    _forced(monkeypatch, "pirates")
    _journey(engine)
    _do(engine, "close")
    _do(engine, "close")                               # they come across first
    scene.initiative = []
    for ref in scene.sea["foes"]:
        scene.people[ref].hp = -20
    out = _do(engine, "board")
    theirs = engine.vessel(scene.sea["theirs"])
    assert scene.at == ships.deck_of(theirs), out.tell
    assert scene.initiative, "pirates on their own deck do not wait to be talked to"
    for ref in scene.sea["foes"]:
        scene.people[ref].hp = -20
    scene.initiative = []
    engine._sea_settled()
    assert ships.vessel_of(scene.at) == engine.aboard().id and engine.aboard().bound_for, \
        "a party left on the cut-loose ship is stood back on its own"


def test_a_sea_creature_comes_at_you_and_a_swimmer_holds_the_water(monkeypatch):
    """Measured 2026-11-13: every square of sea round the hull was solid ground to
    everybody, so a shark could only fight by standing on the planks. A swimmer now waits
    in the water at the rail, beside the player, and the fight starts."""
    from rules import water

    scene, engine, pc = _at_port()
    _journey(engine)
    _quiet_weather(monkeypatch)
    _forced(monkeypatch, "creature")
    out = _journey(engine)
    met = next(e for e in out.effects if e.get("kind") == "sea_encounter")
    assert met["refs"], out.tell
    deck = ships.deck_of(engine.aboard())
    assert all(scene.people[r].at == deck for r in met["refs"])
    assert scene.initiative and set(met["refs"]) <= set(scene.sides["them"])
    swimmers = [r for r in met["refs"] if water.swim_speed(scene.people[r]) > 0]
    assert swimmers, "the Bestiary's sea creatures swim"
    for r in swimmers:
        assert scene.afloat(r) and scene.positions[r][:2] in scene.grid.water
        assert scene.people[r].water_row(scene.afloat(r)) == water.SWIMMER
    assert "alongside her, at the rail" in out.tell, out.tell


def _deck_with(kind="sailing ship"):
    from rules.bestiary import instantiate
    from tests.test_deck_fixtures import _aboard

    s, e, pc = _aboard(kind)
    shark = instantiate("shark", scene=s, name="the shark")
    s.add(shark, zone="near")
    return s, e, pc, shark


def _beside(s, square):
    """A square of the deck orthogonally beside a water square, free."""
    g = s.grid
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        p = (square[0] + dx, square[1] + dy)
        if g.inside(p) and p not in g.blocked and p not in g.water:
            return p
    return None


def test_the_sea_round_the_hull_is_open_to_a_swimmer_and_shut_to_a_walker():
    from rules import water

    s, e, pc, shark = _deck_with()
    g = s.grid
    assert g.water and g.water <= g.blocked, "water stays solid ground to the planks"
    rail = {tuple(p) for f in g.fixtures if f["kind"] == "rail" for p in f["squares"]}
    assert rail <= g.water, "the rail stands in the sea beside the hull"
    start = next(p for p in sorted(g.water) if _beside(s, p))
    deck_sq = _beside(s, start)
    assert water.swim_speed(shark) > 0
    swim = g.reachable(start, 60, swims="speed")
    assert deck_sq in swim, "a swimmer climbs aboard from the water"
    assert any(p in g.water for p in swim), "and swims along the side"
    walk = g.reachable(deck_sq, 60)
    assert not any(p in g.water for p in walk), "a walker's route never crosses the sea"


def test_a_swimmer_bites_from_the_water(monkeypatch):
    """The fight from the water: the shark in a rail square beside the player strikes
    without coming aboard."""
    s, e, pc, shark = _deck_with()
    g = s.grid
    start = next(p for p in sorted(g.water) if _beside(s, p))
    s.positions[pc.ref] = _beside(s, start)
    s.positions[shark.ref] = start
    e.run(e.validate([{"op": "begin_encounter",
                       "params": {"sides": {"you": [pc.ref], "them": [shark.ref]}}}]))
    s.turn = [r for r, _ in s.initiative].index(shark.ref)
    res = e.run(e.validate([{"op": "attack", "actor": shark.ref, "target": pc.ref,
                             "visibility": "hidden", "because": "t"}]))
    out = res.outcomes[-1]
    assert out.op == "attack" and out.status != "refused", out.tell
    assert s.positions[shark.ref][:2] == start, "it struck from where it swam"


def test_anyone_may_go_over_the_side_and_is_then_in_the_water():
    from rules import water

    from tests.test_map_fixtures import _move

    s, e, pc, shark = _deck_with()
    g = s.grid
    start = next(p for p in sorted(g.water) if _beside(s, p))
    s.positions[pc.ref] = _beside(s, start)
    s.positions.pop(shark.ref, None)
    assert water.swim_speed(pc) == 0
    assert e._swims(pc, start) == "over" and e._swims(pc, s.positions[pc.ref]) == ""
    out = _move(e, pc.ref, start).outcomes[-1]
    assert out.status != "refused", out.tell
    assert tuple(s.positions[pc.ref][:2]) == start and s.afloat(pc.ref)
    assert pc.water_row(s.afloat(pc.ref)) in (water.SWIMMING, water.OFF_BALANCE)
    assert not pc.water_row(), "the deck itself is dry"


def test_a_creature_that_does_not_come_at_you_surfaces_and_goes(monkeypatch):
    scene, engine, _pc = _at_port()
    _journey(engine)
    _quiet_weather(monkeypatch)
    _forced(monkeypatch, "creature", aggressive=False)
    before = set(scene.people)
    out = _journey(engine)
    assert "down again" in out.tell and set(scene.people) == before, out.tell
    assert not scene.initiative


def test_a_river_meets_nothing_from_the_sea_table(monkeypatch):
    scene, engine, _pc = _at_port()
    _journey(engine, to="Elyrielle")
    _forced(monkeypatch, "pirates")
    _journey(engine, to="Elyrielle")
    assert scene.location_id == "d677be869434" and not scene.sea


# --- the storm's ranged half ---------------------------------------------------------------------

def _stormy(pc):
    pc.apply_effect(ActiveEffect(
        name="a storm at sea", kind="situation", key="storm-at-sea",
        source="rule:storm-at-sea", origin="rule:storm-at-sea",
        tags=states.tags_for("storm-at-sea"), duration="rounds", rounds_left=100))


def test_a_storm_refuses_a_bow_and_says_why_but_not_a_blade():
    """CRB p.438: "Storms make ranged weapon attacks impossible". The effect carries the
    tag; the attack op asks it, never the effect's name."""
    from tests.test_nonlethal_strikes import _fight, _swing

    scene, engine = _fight()
    pc = scene.pc()
    pc.weapons.append("shortbow")
    pc.equipped = "shortbow"
    pc.goods["arrows"] = 20
    _stormy(pc)
    out = _swing(engine, "pc", "c1", weapon="shortbow")
    assert out.status == "refused" and "storm" in out.tell, out.tell
    out = _swing(engine, "pc", "c1", weapon="rapier")
    assert out.status != "refused", out.tell
    # A throw is a ranged weapon attack too.
    scene, engine = _fight()
    pc = scene.pc()
    pc.weapons.append("dagger")
    pc.equipped = "dagger"
    _stormy(pc)
    out = _swing(engine, "pc", "c1", weapon="dagger", thrown=True)
    assert out.status == "refused" and "storm" in out.tell, out.tell


def test_a_storm_keeps_its_tag_across_a_save():
    """A `situation` effect's tags are what was stored (only conditions are re-derived on
    load), so the tag must be written with it."""
    from rules.activeeffect import ActiveEffect as AE, from_dict

    eff = AE(name="a storm at sea", kind="situation", key="storm-at-sea",
             tags=states.tags_for("storm-at-sea"), duration="rounds", rounds_left=50)
    assert states.NO_RANGED_WEAPONS in from_dict(eff.as_dict()).tags


def test_the_storm_at_sea_lands_the_tag(monkeypatch):
    scene, engine, pc = _at_port()
    _journey(engine)
    monkeypatch.setattr(ships, "day_at_sea", lambda dice, level: "storm")
    _journey(engine, days=1)
    assert pc.has_state(states.NO_RANGED_WEAPONS) and pc.has_state("weather.storm")


# --- old ship ids ------------------------------------------------------------------------------

def test_every_vessel_id_minted_carries_its_kind():
    """`places.for_scene` derives a ship's rooms from the place id alone (`ships.rooms_at`),
    and an id without its kind gets none. Proved not to reach a save instead of given a
    fallback: before f01af11c (the commit that put the kind in the id) nothing outside a
    test ever wrote `scene.vessels` or a non-empty `scene.sea` — `_keep_vessel` writes back
    a vessel already read from the scene, and `_op_sea` refuses with no other ship — so no
    save holds a `ship-<hex>` id. Every door that mints one since carries the kind."""
    for kind in ships.VESSELS:
        vid = ships.vessel_id("port", kind, 3)
        assert ships.kind_of_id(vid) == kind
        assert ships.rooms_at(ships.deck_of(ships.Vessel(id=vid, name="x", kind=kind, hp=1)))
    for scale in ships.BY_SCALE:
        for v in ships.offered_at("7ef5e373c993", scale, n=3):
            assert ships.kind_of_id(v.id) == v.kind
    assert ships.kind_of_id(ships.passenger_ship("p", "town", river=True).id) == "keelboat"


# --- the long board's opening view ---------------------------------------------------------------

NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize("w,h,box,turned", [
    (6, 17, (692, 272), True),      # the deck measured 2026-11-13: 15% of the box's width
    (17, 6, (692, 272), False),     # already lies along the box
    (6, 17, (300, 520), False),     # a phone's tall box
    (24, 24, (692, 272), False),    # a square room: never turned
    (12, 20, (692, 272), False),    # long, but not twice as long
])
def test_a_long_flat_board_is_turned_to_lie_along_its_box(w, h, box, turned):
    from pagesource import TABLE_SCRIPTS

    src = (TABLE_SCRIPTS / "03-offers-and-map.js").read_text(encoding="utf-8")
    start = src.index("function flatTurned(g)")
    body = src[start:src.index("\n}\n", start) + 3]
    script = ("const document = {querySelector: () => ({getBoundingClientRect: () => ("
              + json.dumps({"width": box[0], "height": box[1]}) + ")}),"
              " getElementById: () => null};\n" + body
              + f"\nprocess.stdout.write(String(flatTurned({{width: {w}, height: {h}}})));")
    got = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30)
    assert got.stdout == str(turned).lower(), got.stderr

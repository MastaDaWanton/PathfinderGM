"""Hiring, the arena, browsing shops and duplicate places: playtest 2026-11-17b items 17, 20,
21, 23, 24, 26, 27, 29 and playtest 2026-11-17 item 10 (Vesna Kroll, Mirabalos, 0.4.2)."""
from __future__ import annotations

from types import SimpleNamespace

from gm import acts_to_ops, interpret, planned
from rules import arena, goods, hirelings, keepers, places, population, requests, scope, states
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene

TOWN = "town1"
ARENA = f"{TOWN}~urban:the-arena"


def _party(work="caravan-guard", gp=200, at=None):
    s = Scene(location_id=TOWN)
    if at:
        s.at = at
    s.clock_minutes = 12 * 60
    pc = instantiate("guildhand", scene=s, name="Vesna")
    pc.kind = "pc"
    pc.purse = {"gp": gp}
    s.add(pc)
    other = instantiate("guildhand", scene=s, name="man in corner")
    s.add(other)
    s.population = {"p1": {"id": "p1", "ref": other.ref, "home": TOWN,
                           "life": {"work": work, "axes": {"thrift": 50}}}}
    return s, Engine(s, Dice(seed=3)), pc, other


def _run(e, raw):
    return e.run(e.validate(raw, origin="author:test")).outcomes


# --- hiring ------------------------------------------------------------------------------


def test_a_hire_asked_is_the_wage_door_and_pays_no_xp():
    """#21: "I'll hire you for a week, to guard me. Name your price" was a Diplomacy favour
    (6 vs 14 the turn before; this time granted) that paid 150 XP and hired nobody. Read as
    `request asks_for: hire`, the built check goes to the hirelings' door: a week up front,
    the bond, no roll and no XP."""
    s, e, pc, sword = _party()
    rows = acts_to_ops.table({"actions": [{"act": "request", "asks_for": "hire",
                                           "object": "hire you for a week, to guard me",
                                           "span": "I'll hire you for a week"}]}, s)
    built = [i for r in rows for i in r.intents]
    assert built and built[0]["params"]["request"] == "hire"
    built[0]["target"] = sword.ref
    xp = int(pc.xp or 0)
    before = goods.in_copper(pc.purse)
    out = _run(e, built)
    assert sword.has_state(states.HIRED) and sword.has_state(states.TRAVELS_WITH_YOU)
    assert before - goods.in_copper(pc.purse) == hirelings.week_cp(s, sword)
    assert int(pc.xp or 0) == xp and not out[0].rolls
    assert "a week's wages in advance" in out[0].tell


def test_a_hire_of_somebody_who_is_no_sword_is_refused_unrolled():
    """#20's other half: a man who is no mercenary is not made one by being asked."""
    s, e, pc, baker = _party(work="baker")
    out = _run(e, [{"op": "check", "actor": pc.ref, "target": baker.ref,
                    "params": {"skill": "diplomacy", "request": "hire"}}])
    assert not baker.has_state(states.HIRED) and not out[0].rolls
    assert "does not hire out a sword" in out[0].tell


def test_the_reader_and_the_engine_hold_the_same_request_kinds():
    assert tuple(interpret.REQUESTS) == requests.KINDS and requests.HIRE in requests.KINDS


def test_the_newcomer_a_seek_for_a_sellsword_finds_is_a_sellsword():
    """#17: "look for a sellsword for hire" was read `seek`, the finder missed
    (work:caravan-guard), and the plan's "man in corner" had no trade, so he could never be
    hired. The one newcomer of that turn now carries the trade the player looked for."""
    raw = [{"op": "introduce", "params": {"who": "woman by the hearth", "how": "already_here"}}]
    frame = {"actions": [{"act": "seek", "target": "a sellsword for hire",
                          "span": "look for a sellsword for hire"}]}
    out = acts_to_ops.trade_sought(raw, frame)
    assert out[0]["params"]["trade"] == "sellsword"
    s, e, pc, _ = _party()
    s.population = {}
    got = _run(e, out)
    ref = got[0].effects[0]["actors"][0]["ref"]
    assert hirelings.hires_out(s, s.actors[ref])
    # And without the trade, the same newcomer is nobody's sword (the playtest's case).
    s, e, pc, _ = _party()
    s.population = {}
    got = _run(e, [{"op": "introduce", "params": {"who": "woman by the hearth"}}])
    assert not hirelings.hires_out(s, s.actors[got[0].effects[0]["actors"][0]["ref"]])


def test_a_newcomer_with_a_trade_of_their_own_is_left_alone():
    raw = [{"op": "introduce", "params": {"who": "a baker"}}]
    frame = {"actions": [{"act": "seek", "target": "a sellsword"}]}
    assert "trade" not in acts_to_ops.trade_sought(raw, frame)[0]["params"]


def test_a_sword_for_hire_knows_their_own_rate():
    """#20: asked his rate, he said "My rate depends on the danger" and named none."""
    s, e, pc, sword = _party()
    knows = " ".join(planned.known_to(e, sword.ref))
    day = goods.purse_line(goods.coins_for(hirelings.day_cp(s, sword)), e._coins_here())
    assert "hires out as a sword" in knows and day in knows
    s, e, pc, baker = _party(work="baker")
    assert "hires out" not in " ".join(planned.known_to(e, baker.ref))


# --- shops named by their keeper ---------------------------------------------------------


def _city():
    names = ("the market", "the laboratory", "the smithy", "the tavern", "the granary")
    return [places.Place(id=f"{TOWN}~urban:{n[4:]}", name=n) for n in names]


def test_a_shop_named_by_its_keeper_is_the_towns_own_place():
    """#26: "Head to the alchemist's" founded "the alchemist's â€¦ a laboratory" beside the
    city's laboratory; 2026-11-17 #10: "the general store" founded a second one off the
    granary while its keeper stood in the market."""
    known = _city()
    assert places.find(known, "the alchemist's").name == "the laboratory"
    assert places.find(known, "the general store").name == "the market"
    assert places.find(known, "the blacksmith's").name == "the smithy"
    assert places.find(known, "the weaponsmith's shop").name == "the market"
    # A keeper's title alone is a person, not a place.
    assert places.find(known, "the alchemist") is None


def test_found_refuses_a_second_shop_the_town_already_has():
    s = Scene(location_id=TOWN)
    e = Engine(s, Dice(seed=1))
    e.places = lambda: _city()
    out = e._op_found(SimpleNamespace(params={"name": "the alchemist's", "parent": "the market"},
                                      id="i1", because="", op="found"), {})
    assert out.status == "refused" and "the laboratory" in out.tell


# --- a society list as a place's description ---------------------------------------------


def test_an_authored_about_that_is_a_town_fact_is_not_the_places():
    """#27: the market was "(Patrilineal clans, Zhilakai nobility, artisan guilds)", the
    city's Social Classes fact written as the market's `about` by the export."""
    loc = SimpleNamespace(
        facts={"Social Classes": "Patrilineal clans, Zhilakai nobility, artisan guilds"},
        places=[{"id": f"{TOWN}~urban:the-market", "name": "the market",
                 "about": "Patrilineal clans, Zhilakai nobility, artisan guilds."},
                {"id": f"{TOWN}~urban:the-well", "name": "the well",
                 "about": "The water everyone draws from."}])
    got = {p.name: p.about for p in places._authored(loc)}
    assert "Patrilineal" not in got["the market"] and got["the market"]
    assert got["the well"] == "The water everyone draws from."


# --- titles look only in this town -------------------------------------------------------


def test_a_title_never_finds_a_character_in_another_town():
    """#23: "the master of the arena" matched "Apprentice to Xylorvotha's master craftsman"
    on "master" and was refused "in Xylorvotha, not here"."""
    arin = SimpleNamespace(kind="CHARACTER", name="Arin Vexarion", parent_id="far",
                           facts={"Role": "Apprentice to Xylorvotha's master craftsman"})
    far = SimpleNamespace(name="Xylorvotha")
    here = SimpleNamespace(name="Mirabalos", facts={})
    world = SimpleNamespace(entities={"a": arin},
                            get=lambda i: {"far": far, TOWN: here}.get(i))
    s = Scene(location_id=TOWN)
    got = scope.look_for(world, "the master of the arena", s, TOWN)
    assert got["scope"] != scope.ELSEWHERE and "Xylorvotha" not in got["line"]
    # A name said is still the world's to place.
    assert scope.look_for(world, "Arin Vexarion", s, TOWN)["scope"] == scope.ELSEWHERE


# --- the arena -----------------------------------------------------------------------------


def _at_the_arena():
    s, e, pc, _ = _party(at=ARENA)
    master = instantiate("guildhand", scene=s, name="the master of the games")
    master.world_entity_id = keepers.entity_id(ARENA)
    s.add(master)
    return s, e, pc, master


def test_the_house_stages_a_knockout_bout_by_the_budget():
    """#24: "Put me in the next bout" built nothing; the master gave speeches. Now the
    house puts up one opponent inside the party's average encounter, the purse is the
    book's treasure for that CR, and the fight is on."""
    s, e, pc, master = _at_the_arena()
    out = _run(e, [{"op": "bout", "actor": pc.ref, "params": {}}])
    assert out[0].status != "refused", out[0].tell
    fx = out[0].effects[0]
    foe = s.actors[fx["against"]]
    assert s.in_encounter and pc.has_state(states.IN_A_BOUT) and foe.has_state(states.IN_A_BOUT)
    assert fx["purse_cp"] == arena.purse_cp(fx["cr"])
    # One a day.
    s.end_encounter()
    again = _run(e, [{"op": "bout", "actor": pc.ref, "params": {}}])
    assert again[0].status == "refused" and "tomorrow" in again[0].tell


def test_a_bout_is_refused_where_no_arena_is():
    s, e, pc, _ = _party(at=f"{TOWN}~urban:the-market")
    out = _run(e, [{"op": "bout", "actor": pc.ref, "params": {}}])
    assert out[0].status == "refused" and "arena" in out[0].tell


def test_the_winner_takes_the_purse_and_the_bout_ends_on_both():
    s, e, pc, master = _at_the_arena()
    out = _run(e, [{"op": "bout", "actor": pc.ref, "params": {}}])
    foe = s.actors[out[0].effects[0]["against"]]
    before = goods.in_copper(pc.purse)
    foe.take_damage(foe.hp + 5, lethality="nonlethal")
    foe.apply_nonlethal_state()
    line = e._settle_xp()
    assert "purse" in line
    assert goods.in_copper(pc.purse) - before == out[0].effects[0]["purse_cp"]
    assert not pc.has_state(states.IN_A_BOUT) and not foe.has_state(states.IN_A_BOUT)


def test_blows_between_the_bouts_fighters_are_nonlethal():
    s, e, pc, master = _at_the_arena()
    out = _run(e, [{"op": "bout", "actor": pc.ref, "params": {}}])
    foe = s.actors[out[0].effects[0]["against"]]
    hp = foe.hp
    for _ in range(6):
        _run(e, [{"op": "attack", "actor": pc.ref, "target": foe.ref, "params": {}}])
    assert foe.hp == hp


def test_words_to_the_house_asking_for_a_bout_stage_one():
    """Live 2026-11-18: "I tell the master of the games to put me in the next bout." was read
    `talk`; the plan was a `say`, and nothing was staged. At an arena the closed question
    adds the bout; anywhere else it is never asked."""
    s, e, pc, master = _at_the_arena()
    frame = {"actions": [{"act": "talk", "target": "the master of the games",
                          "span": "tell the master of the games to put me in the next bout"}]}
    asked = []
    raw = acts_to_ops.bout_spoken([{"op": "say", "params": {"words": "x"}}], frame, s,
                                  ask=lambda span: asked.append(span) or "bout")
    assert [r["op"] for r in raw] == ["say", "bout"] and asked
    s, e, pc, _ = _party(at=f"{TOWN}~urban:the-market")
    asked.clear()
    raw = acts_to_ops.bout_spoken([], frame, s, ask=lambda span: asked.append(span) or "bout")
    assert raw == [] and not asked


def test_a_look_over_a_sellers_wares_is_a_browse_that_opens_the_counter():
    """#29: "look over what potions they have for sale" was read `look` (twice, live) and no
    counter opened. The closed question turns it into the `buy` it is, in place."""
    frame = {"actions": [{"act": "look", "object": "what potions they have for sale",
                          "span": "look over what potions they have for sale"},
                         {"act": "look", "object": "the room", "span": "look around"}]}
    got = interpret.browsed(frame, ask=lambda span: "browse" if "sale" in span else "")
    assert got == ["look over what potions they have for sale"]
    assert [a["act"] for a in frame["actions"]] == ["buy", "look"]
    assert interpret.bought(frame) == "what potions they have for sale"
    assert interpret.browsed({"actions": [{"act": "look", "object": "x", "span": "x"}]}) == []

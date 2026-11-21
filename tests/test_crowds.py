"""The engine's crowd (rules/crowds.py). Owner, 2026-11-18, on the crowd cut of owner bug
2026-11-17 #7: "even during the day in markets there has never once been a crowd spawned",
so with the cut every market at noon read deserted. A crowd is engine state now: laid by the
hour on the place's own squares, said on arrival and in the brief, thinned by the clock,
scattered by a fight, and hiding in it is the book's cover (CRB p.433, City Streets)."""
from __future__ import annotations

from rules import crowds
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from world.loader import load_cached

WORLD = load_cached("fixtures/pangrella-campaign.json")
TOWN = "5bbd0c40345f"          # Pangrella, a town
NOON = 12 * 60
NIGHT = 23 * 60 + 30


def _here(label="the-market", clock=NOON, loc=TOWN):
    s = Scene(location_id=loc)
    s.at = f"{loc}~urban:{label}"
    s.clock_minutes = clock
    pc = instantiate("guildhand", scene=s, name="PC")
    pc.kind = "pc"
    s.add(pc, zone="near")
    e = Engine(s, Dice(seed=3), world=WORLD)
    e.lay_the_ground()
    e._crowd_settle(quiet=True)
    return s, e, pc


def _told(res):
    return " ".join(o.tell for o in res.outcomes)


def test_a_town_market_at_noon_holds_a_crowd_on_its_own_squares():
    """The market at noon had nobody but the party on the map, every time. Now its crowd
    stands on open squares of the market's map, as difficult ground (2 squares to enter)."""
    s, e, pc = _here()
    crowd = crowds.standing(s)
    assert crowd is not None
    assert crowd.squares and set(map(tuple, crowd.added)) <= s.grid.difficult
    assert not set(map(tuple, crowd.squares)) & s.grid.blocked


def test_no_crowd_at_night_in_a_village_or_upstairs():
    assert crowds.standing(_here(clock=NIGHT)[0]) is None
    assert not crowds.busy(f"{TOWN}~urban:the-market", "village", NOON)
    assert not crowds.busy(f"{TOWN}~urban:the-inn^1", "city", 19 * 60)
    assert crowds.busy(f"{TOWN}~urban:the-tavern", "town", 19 * 60)
    assert crowds.busy(f"{TOWN}~urban:the-great-square", "city", NOON)
    assert not crowds.busy(f"{TOWN}~urban:the-cistern", "city", NOON)


def test_arriving_at_a_busy_market_says_the_crowd():
    """Jack's walk to the great square (transcript 197) is the shape: the arrival tells the
    crowd the engine laid, and the brief carries it every beat it stands."""
    s, e, pc = _here("the-tavern")
    market = next(p for p in e.places() if p.id.endswith(":the-market"))
    raw = {"op": "travel", "actor": pc.ref, "because": "t", "params": {"place": market.name}}
    res = e.run(e.validate([raw], origin="author:test"))
    assert s.at == market.id
    assert "The market is crowded at this hour." in _told(res), _told(res)
    from gm import prompts

    brief = prompts.scene_brief(WORLD, s, WORLD.get(TOWN), [])
    assert "CROWD at the market" in brief


def test_the_crowd_thins_when_the_hour_turns():
    s, e, pc = _here()
    before = set(s.grid.difficult)
    crowd = crowds.standing(s)
    s.clock_minutes = NIGHT
    res = e.run([])
    assert crowds.standing(s) is None
    assert "thins out" in _told(res), _told(res)
    assert s.grid.difficult == before - set(map(tuple, crowd.added))


def test_a_fight_scatters_the_crowd_until_the_slot_turns():
    """CRB p.433: "If crowds see something obviously dangerous, they'll move away". The fight
    ending does not bring it back the same hour; the next busy slot does."""
    s, e, pc = _here()
    s.initiative, s.turn = [(pc.ref, 10)], 0
    res = e.run([])
    assert "scatters away from the fight" in _told(res), _told(res)
    assert crowds.standing(s) is None
    s.end_encounter()
    assert "crowded" not in _told(e.run([]))
    s.clock_minutes = 15 * 60 + 5
    assert "The market is crowded at this hour." in _told(e.run([]))
    assert crowds.standing(s) is not None


def test_hiding_in_the_crowd_is_cover_from_anyone_not_beside_you():
    """Stealth while watched is refused in the open (CRB p.106); the crowd "provides cover
    for anyone who does so, enabling a Stealth check" (CRB p.433)."""
    s, e, pc = _here()
    crowd = {tuple(q) for q in crowds.standing(s).squares}
    g = s.grid
    spot = next(q for q in sorted(crowd) if 3 <= q[0] < g.width - 3)
    s.positions[pc.ref] = spot
    watcher = instantiate("guildhand", scene=s, name="the watchman")
    s.add(watcher, zone="near")
    far = next(((x, y) for y in range(g.height) for x in range(g.width)
                if (x, y) not in crowd and (x, y) not in g.blocked
                and max(abs(x - spot[0]), abs(y - spot[1])) in (3, 4)
                and g.line_of_sight((x, y), spot)), None)
    assert far is not None
    s.positions[watcher.ref] = far
    assert e._watched_in_the_open(pc) is None
    near = next((x, y) for y in range(spot[1] - 1, spot[1] + 2)
                for x in range(spot[0] - 1, spot[0] + 2)
                if (x, y) != spot and (x, y) not in g.blocked and g.passable((x, y)))
    s.positions[watcher.ref] = near
    assert e._watched_in_the_open(pc) is watcher


def test_a_crowd_survives_closing_the_app():
    from rules.engine import Manifestation

    s, e, pc = _here()
    crowd = crowds.standing(s)
    back = Manifestation.from_dict(crowd.as_dict())
    assert (back.what, back.source, back.terrain) == ("crowd", s.at, "difficult")

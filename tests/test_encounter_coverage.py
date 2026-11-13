"""The encounter budget's known gaps, covered (owner 2026-11-13: "cover the stuff that isnt
covered like the guards").

Measured before this:
  * a wanted lone level-1 PC who swung in a square of four watchmen met all four:
    `Engine._law_joins` brought in every guard standing, 540 XP of CR 1/3s against a lone
    level-1's 135 XP average budget (`rules/encounter_budget.py`, APL -1);
  * a scheme's `bring_in` arrived at its authored count whatever the party was:
    a-small-favour's two guards and three hunters at a lone first-level PC;
  * a place's danger rating (`rules/volatility.py`) moved nothing: a lawless road and a
    calm one rolled the same 20% a watch.
"""
from __future__ import annotations

from types import SimpleNamespace

from rules import encounter_budget as eb
from rules import gathering, ontheway, schemes, states, volatility
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world import loader

WORLD = loader.load_cached("fixtures/pangrella-campaign.json")
TOWN = "58b90a214ada"
MARKET = f"{TOWN}~urban:the-market"
SOURCE = "scheme:a-small-favour/failure"


def _wanted_table(seed: int, guards: int = 4):
    s = Scene(location_id=TOWN)
    pc = load_pc("fixtures/pc-kesst.json")          # level 1, alone: APL -1
    s.add(pc)
    e = Engine(s, Dice(seed=seed), world=WORLD)
    e.place_party(MARKET)
    tag = states.wanted_tag(TOWN)
    pc.apply_effect(ActiveEffect(name="wanted", kind="situation", key=f"{SOURCE}:{tag}",
                                 source=SOURCE, origin=SOURCE,
                                 duration="until-dismissed", tags=(tag,)))
    watch = [s.add(instantiate("watchman", scene=s, name=f"watchman {i + 1}"), zone="far")
             for i in range(guards)]
    return s, e, pc, watch


def _swing(e, target):
    return e.run(e.validate([{"op": "attack", "actor": "pc", "target": target,
                              "because": "t", "params": {}}], origin="author:test"))


def _hard_cap(apl: int) -> int:
    """The most the guarded tier ever buys: its hardest band's budget."""
    top = max(eb.TIERS[name] for name, _ in eb.MIX["guarded"])
    return eb.budget(apl + top)


def test_a_wanted_lone_first_level_pc_meets_a_budgeted_watch_not_all_four():
    """Four watchmen (135 XP each) in the square: all four came in before, 540 XP against
    a hard cap of 400. Now at most the guarded tier's budget joins, never none, and the
    rest are SAID to hang back — never silently gone."""
    joined_counts = set()
    for seed in range(20):
        s, e, pc, watch = _wanted_table(seed)
        thug = s.add(instantiate("thug", scene=s, name="a thug"), zone="near")
        res = _swing(e, thug.ref)
        them = [w for w in watch if w.ref in s.sides.get("them", ())]
        assert 1 <= len(them) < 4, (seed, s.sides)
        assert sum(135 for _ in them) <= _hard_cap(-1), seed
        held = [w for w in watch if w not in them]
        tells = " ".join(o.tell or "" for o in res.outcomes)
        for w in held:
            assert w.ref in s.actors, "a held guard is still standing in the scene"
            assert w.name in tells and "shouting the alarm" in tells, tells
        joined_counts.add(len(them))
    assert joined_counts <= {1, 2}, joined_counts


def test_striking_a_guard_rallies_only_what_the_budget_holds():
    """`rally` brought a struck guard's kind in whole — the same four watchmen came
    through this door whenever the first blow fell on one of them."""
    for seed in range(20):
        s, e, pc, watch = _wanted_table(seed)
        _swing(e, watch[0].ref)
        them = [w for w in watch if w.ref in s.sides.get("them", ())]
        assert watch[0] in them, "the guard the words struck is always in"
        assert len(them) * 135 <= _hard_cap(-1), (seed, len(them))


def test_a_watch_inside_the_least_budget_comes_whole_and_rolls_nothing():
    """One watchman at a lone level-1 is 135 XP, the average budget itself: no d100 is
    spent asking, so the wanted tests' single guard keeps its dice."""
    s, e, pc, watch = _wanted_table(3, guards=1)
    thug = s.add(instantiate("thug", scene=s, name="a thug"), zone="near")
    res = _swing(e, thug.ref)
    assert watch[0].ref in s.sides["them"]
    assert not any(r.label == "how hard the watch is" for o in res.outcomes
                   for r in (o.rolls or ()))


# --- volatility on land ---------------------------------------------------------------------

def test_nothing_stated_is_the_published_rate_exactly():
    """No shipped export carries the rating: every table must roll as it did."""
    assert volatility.scale(None, MARKET) == 1.0
    assert volatility.scale(WORLD, MARKET, base=volatility.SETTLED_DEFAULT) == 1.0
    assert volatility.scale(WORLD, f"{TOWN}~forest:@the-outskirts") == 1.0
    assert gathering.bands(1.0) == gathering.BANDS
    for seed in range(200):
        a = ontheway.road(Dice(seed=seed), 6, "forest", 3)
        b = ontheway.road(Dice(seed=seed), 6, "forest", 3, danger=1.0)
        assert (a and (a.kind, a.roll, a.count)) == (b and (b.kind, b.roll, b.count))


def _world_rated(level: int):
    ent = SimpleNamespace(id="land", parent_id=None, volatility=level, places=[])
    return SimpleNamespace(get=lambda i: ent if i == "land" else None,
                           ancestors=lambda i: [])


def test_a_lawless_road_meets_more_trouble_than_a_calm_one():
    """Over 600 seeded six-hour watches in the forest: the creature and the weather move
    with the ground's rating (calm a third of the wild rate, lawless twice), travellers
    and tolls do not."""
    def tally(level):
        d = volatility.scale(_world_rated(level), "land~forest:the-wood")
        out = {"creature": 0, "weather": 0, "travellers": 0, "toll": 0}
        for seed in range(600):
            m = ontheway.road(Dice(seed=seed), 6, "forest", 3, danger=d)
            if m is not None:
                out[m.kind] += 1
        return out

    calm, uneasy, lawless = tally(0), tally(2), tally(4)
    trouble = lambda t: t["creature"] + t["weather"]
    assert trouble(calm) < trouble(uneasy) < trouble(lawless), (calm, uneasy, lawless)
    assert trouble(lawless) > 4 * trouble(calm), (calm, lawless)
    # Friendly bands stay near their published share (20% x 40% of 600 = 48).
    assert abs((lawless["travellers"] + lawless["toll"]) - 48) < 25, lawless
    assert abs((calm["travellers"] + calm["toll"]) - 48) < 25, calm


def test_a_lawless_street_has_more_thieves_and_a_calm_one_fewer():
    def thieves(d):
        n = 0
        for seed in range(3000):
            m = ontheway.street(Dice(seed=seed), 1, danger=d)
            n += bool(m and m.kind in ontheway.STREET_DANGER)
        return n

    assert thieves(1 / 1.5) < thieves(1.0) < thieves(4.0)


def test_a_lawless_forage_meets_more_creatures():
    lawless, calm = gathering.bands(2.0), gathering.bands(1 / 3)
    width = lambda bands, k: next(hi - lo + 1 for lo, hi, kind in bands if kind == k)
    assert width(lawless, "creature") == 36 and width(calm, "creature") == 6
    assert width(lawless, "rich") == width(calm, "rich") == 20


# --- schemes' hostile arrivals ----------------------------------------------------------------

def _scheme_engine(seed):
    s = Scene(location_id=TOWN)
    s.add(load_pc("fixtures/pc-kesst.json"))
    return SimpleNamespace(scene=s, dice=Dice(seed=seed))


def test_a_schemes_hostile_bring_in_fits_the_budget():
    """a-small-favour's three hunters at a lone level-1 PC: three thugs (135 XP each) are
    405 XP, an opening's budget tops at 200 (challenging at APL -1). Now one comes."""
    for seed in range(30):
        e = _scheme_engine(seed)
        n = schemes._hostile_count(e, {"count": 3, "side": "them"}, "thug", "hunter")
        assert n * 135 <= eb.budget(-1 + eb.TIERS["challenging"]), (seed, n)
        g = schemes._hostile_count(e, {"count": 2, "side": "them"}, "watchman", "guard")
        assert 1 <= g and g * 135 <= _hard_cap(-1), (seed, g)


def test_a_witness_is_not_a_fight_and_comes_as_written():
    e = _scheme_engine(0)
    assert schemes._hostile_count(e, {"count": 3, "side": ""}, "thug", "mourner") == 3
    assert schemes._hostile_count(e, {"count": 3, "side": "pc"}, "thug", "friend") == 3

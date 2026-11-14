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
    a hard cap of 400. Then the first budget priced only the guards, so the thug the
    player struck (135 XP) stood on the side for free: thug plus two watchmen, 405 XP, on 5
    of 20 seeds — over the hard cap. Now the struck thug is counted, the whole side stays
    inside the tier, and the rest are SAID to hang back — never silently gone."""
    joined_counts = set()
    for seed in range(20):
        s, e, pc, watch = _wanted_table(seed)
        thug = s.add(instantiate("thug", scene=s, name="a thug"), zone="near")
        res = _swing(e, thug.ref)
        them = [w for w in watch if w.ref in s.sides.get("them", ())]
        assert thug.ref in s.sides["them"], "the one the words struck is always in"
        assert len(them) < 4, (seed, s.sides)
        assert 135 * (1 + len(them)) <= _hard_cap(-1), (seed, len(them))
        held = [w for w in watch if w not in them]
        tells = " ".join(o.tell or "" for o in res.outcomes)
        for w in held:
            assert w.ref in s.actors, "a held guard is still standing in the scene"
            assert w.name in tells and "shouting the alarm" in tells, tells
        joined_counts.add(len(them))
    assert joined_counts <= {0, 1}, joined_counts


def test_a_struck_merchant_is_counted_against_the_watch():
    """A merchant (400 XP, CR 1) struck by a wanted lone level-1 PC already fills the
    hard tier's 400 alone: before, the watch priced only itself and one more watchman came
    in on top (535 XP). Now the merchant is the side's one, and the watch hangs back."""
    for seed in range(20):
        s, e, pc, watch = _wanted_table(seed)
        merchant = s.add(instantiate("merchant", scene=s, name="a merchant"), zone="near")
        res = _swing(e, merchant.ref)
        assert s.sides["them"] == [merchant.ref], (seed, s.sides)
        tells = " ".join(o.tell or "" for o in res.outcomes)
        assert "shouting the alarm" in tells, tells


def test_striking_a_guard_rallies_only_what_the_budget_holds():
    """`rally` brought a struck guard's kind in whole — the same four watchmen came
    through this door whenever the first blow fell on one of them."""
    for seed in range(20):
        s, e, pc, watch = _wanted_table(seed)
        _swing(e, watch[0].ref)
        them = [w for w in watch if w.ref in s.sides.get("them", ())]
        assert watch[0] in them, "the guard the words struck is always in"
        assert len(them) * 135 <= _hard_cap(-1), (seed, len(them))


def _square(seed: int, template: str, n: int = 4):
    """A lone level-1 PC (APL -1), not wanted, among `n` of a kind."""
    s = Scene(location_id=TOWN)
    s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, Dice(seed=seed), world=WORLD)
    e.place_party(MARKET)
    them = [s.add(instantiate(template, scene=s, name=f"{template} {i + 1}"), zone="near")
            for i in range(n)]
    return s, e, them


def test_a_gang_rallying_to_a_struck_thug_is_priced():
    """Four thugs, the first struck: `rally` brought the other three in unpriced, all four
    on the side (540 XP against a lone level-1's hard cap of 400). Now kin are priced like
    the watch (guarded tier, struck one counted) and the held are said to hang back
    watching."""
    for seed in range(20):
        s, e, thugs = _square(seed, "thug")
        res = _swing(e, thugs[0].ref)
        side = s.sides["them"]
        assert thugs[0].ref in side
        assert 135 * len(side) <= _hard_cap(-1), (seed, side)
        tells = " ".join(o.tell or "" for o in res.outcomes)
        for t in thugs[1:]:
            if t.ref not in side:
                assert t.name in tells and "watching" in tells, tells


def test_a_model_proposed_fight_cannot_sweep_the_square_in():
    """A turn's plan (no origin) declaring all four watchmen "them" against a lone
    level-1 PC put all four in the initiative (540 XP, hard cap 400): only the extra law
    was priced. Now the declared foes are priced; a document's staged fight (`start:`)
    comes as written, priced at its source."""
    for seed in range(20):
        s, e, watch = _square(seed, "watchman")
        refs = [w.ref for w in watch]
        res = e.run(e.validate([{"op": "begin_encounter", "because": "t", "params": {
            "sides": {"pc": ["pc"], "them": refs}}}]))
        side = s.sides["them"]
        assert 1 <= len(side) and 135 * len(side) <= _hard_cap(-1), (seed, side)
        held = set(refs) - set(side)
        assert not held & {r for r, _ in s.initiative}, "a held guard has no turn"
        tells = " ".join(o.tell or "" for o in res.outcomes)
        for w in watch:
            if w.ref not in side:
                assert w.name in tells and "shouting the alarm" in tells, tells
    s, e, watch = _square(0, "watchman")
    refs = [w.ref for w in watch]
    e.run(e.validate([{"op": "begin_encounter", "because": "t", "params": {
        "sides": {"pc": ["pc"], "them": refs}}}], origin="start:test"))
    assert s.sides["them"] == refs


def test_a_monster_companion_counts_at_its_cr():
    """A claimed stone golem (CR 11, 12,800 XP) carries `level` 1 from `instantiate` and
    counted as a level-1 member: party [3, 1], APL 1. By the Bestiary's Monsters as PCs
    ("Treat the monster's CR as class levels") it is an 11th-level member."""
    s = Scene(location_id=TOWN)
    pc = load_pc("fixtures/pc-kesst.json")
    pc.level = 3
    s.add(pc)
    e = Engine(s, Dice(seed=1))
    golem = s.add(instantiate("stone-golem", scene=s))
    e._travels_with_you(golem)
    assert eb.party_levels(s) == [3, 11]
    assert eb.party_apl(s) == 6
    merchant = instantiate("merchant", scene=s)
    assert eb.companion_level(merchant) == 3, "a classed person keeps their class level"


def test_budgets_run_past_cr_20():
    """`rung` clamped every index above 20 to CR 20: an APL 20 party's epic fight (CR 23)
    was priced at 307,200 XP, a quarter of Table 12-2's 819,200."""
    assert eb.budget(23) == 819_200
    assert eb.budget(25) == 1_638_400          # the CRB table's last row
    assert eb.budget(30) == 9_830_400          # the doubling carried on
    assert eb.budget(40) == eb.budget(30)
    assert eb.encounter_index(2 * 1_638_400) == 27
    assert eb.apl([20] * 6) == 21 and eb.budget(eb.apl([20] * 6) + 3) == 1_228_800


def test_a_watch_inside_the_least_budget_comes_whole_and_rolls_nothing():
    """A lone level-5 PC (APL 3, average 800 XP): the struck thug and one watchman are
    270 XP, inside it, so no d100 is spent asking and the side comes whole."""
    s, e, pc, watch = _wanted_table(3, guards=1)
    pc.level = 5
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

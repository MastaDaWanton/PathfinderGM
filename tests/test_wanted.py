"""The wanted state and the three readers that make it bite (docs/wanted.md,
docs/quest-schemes-plan.md §6.6).

Measured before this: `state.wanted.<town>` was named in the plan and granted by
nothing, and nothing read it — a scheme could write "the watch wants you" as an outcome
and the gate, the counter and the guards would carry on as if it had not. A consequence
no reader asks about is a paragraph, not a consequence.

Every test here grants the state the only way it may be granted — an `ActiveEffect`
through `Actor.apply_effect`, tags spelled by `states.wanted_tag` — and the last one
proves the law-2 promise: one `remove_effects(source=...)` and every bite is gone.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

from play import campaign as cm
from rules import pricing, states
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.crafting import Stock
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world import loader

WORLD = loader.load_cached("fixtures/pangrella-campaign.json")
# Zhilgoroth rather than Pangrella since schema 1.5, and the reason is the finding this
# change turned up: the shipped quest chain asks a settlement for five rooms by name — a
# market, somewhere to sleep, a gate, somewhere to pray and a hall — and **only 3 of
# Pangrella's 12 settlements have all five. 6 of Aurvantis's 64.**
#
# A campaign that begins anywhere else gets a chain whose places fall back to whatever is
# nearest: measured here, a scheme wanting somewhere to sleep put its meeting at the
# gatehouse. `tools/check_places.py` publishes the requirement now
# (`scheme_place_kinds`), so a world can be told before it ships rather than after.
TOWN = "58b90a214ada"
MARKET = f"{TOWN}~urban:the-market"
ELSEWHERE = "a1b2c3d4e5f6"
SOURCE = "scheme:a-small-favour/failure"



def _named(kind: str) -> str:
    """A room in this town of the kind a quest would ask for, by whatever it is called
    here. Elyrielle has a cathedral and no temple; both are somewhere to pray, and
    `schemes.PLACE_KINDS` is the one table that says so."""
    from rules import places as _places
    from rules import schemes as _schemes

    rooms = {p.name for p in _places.home_set(WORLD.get(TOWN))}
    for name in _schemes.PLACE_KINDS.get(kind, ()):
        if name in rooms:
            return name
    raise AssertionError(f"{TOWN} has nowhere a quest's {kind!r} could go")

def _table(seed=3):
    s = Scene(location_id=TOWN)
    pc = load_pc("fixtures/pc-kesst.json")
    s.add(pc)
    e = Engine(s, Dice(seed=seed), world=WORLD)
    e.place_party(MARKET)
    return s, e, pc


def _run(engine, op, params, actor="pc"):
    intents = engine.validate([{"op": op, "actor": actor, "because": "t", "params": params}],
                              origin="author:test")
    return engine.run(intents).outcomes[-1]


def _refused(out) -> bool:
    """A refusal is a printable Outcome with nothing done (`Engine._refuse`)."""
    return out.effects == []


def _want(pc, town=TOWN, how="wanted", source=SOURCE):
    """Granted the way a scheme outcome grants it: one effect, one source."""
    tag = states.wanted_tag(town) if how == "wanted" else states.suspected_tag(town)
    return pc.apply_effect(ActiveEffect(name=how, kind="situation", key=f"{source}:{tag}",
                                        source=source, origin=source,
                                        duration="until-dismissed", tags=(tag,)))


def _jar(potency=5.8, tier="rare"):
    return Stock(base="Blackthorn Draught", concentration=1, tier=tier, potency=potency,
                 count=1, specs=[{"type": "heal", "dice": "1d4"}])


# --- the vocabulary -----------------------------------------------------------------------

def test_a_warrant_is_not_slept_off():
    """The trap `rules/states.py` names for every family: `clear_states("recovery.rest")`
    sweeps whatever answers it, so a warrant that carried `recovery.rest` — or sat under
    `state.unable` — would be gone by morning, or would stop the fugitive taking a
    turn. Neither tag may answer for it, and a night's rest must leave it standing."""
    _, _, pc = _table()
    _want(pc)
    for family in ("state.down", "state.unable", "state.impaired", "recovery"):
        assert not pc.has_state(family), f"the warrant answers for {family}"
    assert pc.can_act() and not pc.is_down
    pc.rest("night")
    assert states.standing_with_the_law(pc, TOWN) == "wanted", "a night's sleep cleared it"


def test_the_town_is_in_the_tag_and_a_warrant_elsewhere_answers_nothing_here():
    """Skyrim keeps its bounty per hold for this reason: a crime in one town is nothing
    to the next town's guard. The leaf is the town's durable id, and `has_state` is a
    prefix match at a DOT boundary — `state.wanted.abc` must not answer for
    `state.wanted.abcd`, which a plain `startswith` would have said yes to."""
    _, _, pc = _table()
    _want(pc, town=ELSEWHERE)
    assert states.standing_with_the_law(pc, TOWN) == ""
    assert states.standing_with_the_law(pc, ELSEWHERE) == "wanted"
    assert pc.has_state("state.wanted"), "the family question still answers"
    # And an id with a dot in it cannot fork the family.
    assert "." not in states.town_tag("town.one/two")
    _want(pc, town="abc")
    assert states.standing_with_the_law(pc, "abcd") == ""


def test_suspected_is_the_lesser_and_wanted_wins_when_both_are_held():
    _, _, pc = _table()
    _want(pc, how="suspected")
    assert states.standing_with_the_law(pc, TOWN) == "suspected"
    _want(pc, how="wanted", source="rule:caught-red-handed")
    assert states.standing_with_the_law(pc, TOWN) == "wanted"


# --- reader one: the gate -----------------------------------------------------------------

def test_the_gate_refuses_the_wanted_with_the_fix_named():
    """The plan's own sentence: "travel through a gate refuses (with the fix named:
    leave by another way, clear the name)". Refused as a printable outcome — a raise
    here is a 502 that deletes the player's sentence (stage 7's measurement)."""
    s, e, pc = _table()
    _want(pc)
    out = _run(e, "travel", {"place": "the gate"})
    assert _refused(out), out.tell
    assert "wanted" in out.tell and "clear your name" in out.tell.lower()
    assert "another way" in out.tell
    assert s.at == MARKET, "refused, and yet moved"


def test_the_open_road_is_the_gate_by_another_name():
    """Leaving town by biome — "I head into the forest" — never touches the gate place,
    so a gate-only check let a wanted character walk out of the walls by not naming
    them. A travel by BIOME off urban ground is the road out, and it is watched.

    Grassland since 2026-09-28: the forest this used to ask for is not around
    Zhilgoroth, and a move onto ground the world does not have is now refused for THAT
    reason first (Lane B, `absent_ground`), which would pass this test for the wrong one.
    """
    s, e, pc = _table()
    _want(pc)
    out = _run(e, "travel", {"biome": "grassland"})
    assert _refused(out), out.tell
    assert "wanted" in out.tell, out.tell
    assert s.at == MARKET


def test_ground_ventured_into_is_the_other_way_out():
    """The refusal's fix has to be true. `venture` is its own op and its own door —
    the sewers under the market, a cave in the hills — and a wanted character goes
    down it unrefused; and once made, the place is a travel by name that the gate
    reader leaves alone. The refusal names it once it exists."""
    s, e, pc = _table()
    _want(pc)
    out = _run(e, "venture", {"kind": "cave"})
    assert not _refused(out), out.tell
    cave = s.at
    assert cave != MARKET
    back = _run(e, "travel", {"place": "the market"})
    assert not _refused(back), back.tell
    refused = _run(e, "travel", {"place": "the gate"})
    assert _refused(refused)
    assert "cave" in refused.tell.lower(), f"the way out exists and was not named: {refused.tell}"
    again = _run(e, "travel", {"place": cave})
    assert not _refused(again), again.tell
    assert s.at == cave


def test_the_suspected_are_warned_at_the_gate_and_let_through():
    """The difference between the two states, at the one door where it is felt: a
    warning line in the tell, and the party on the far side of it."""
    s, e, pc = _table()
    _want(pc, how="suspected")
    out = _run(e, "travel", {"place": "the gate"})
    assert not _refused(out), out.tell
    assert "look twice" in out.tell and s.at.endswith(":the-gate")


def test_a_warrant_in_another_town_does_not_shut_this_gate():
    s, e, pc = _table()
    _want(pc, town=ELSEWHERE)
    out = _run(e, "travel", {"place": "the gate"})
    assert not _refused(out), out.tell


def test_moving_inside_the_walls_is_not_watched():
    """Wanted is not house arrest: the tavern and the temple are still yours."""
    s, e, pc = _table()
    _want(pc)
    for spot in (_named("lodging"), _named("temple")):
        out = _run(e, "travel", {"place": spot})
        assert not _refused(out), out.tell


def _outskirts(e):
    from rules import places as places_mod

    return next(p for p in e.places() if p.name == "the outskirts" and places_mod.is_ring(p.id))


@pytest.fixture
def quiet_streets(monkeypatch):
    """Nothing met on the way, so the walk measured is the watch's and not a hawker's."""
    from rules import ontheway

    monkeypatch.setattr(ontheway, "street", lambda dice, level=1: None)
    monkeypatch.setattr(ontheway, "road", lambda *a, **k: None)


def test_a_gate_passed_through_is_a_gate_the_watch_stands_at(quiet_streets):
    """Item 9 (e) of the 2026-09-30 playtest: the warrant was read once, against where the
    walk ENDED, so a wanted character walking outskirts → market — through the gate, the
    one place the watch stands — reached the market in 32 of 40 seeded runs on the owner's
    save (the other 8 were stopped short by a meeting). Every hop asks the watch now, and
    the first way out is asked before anything is spent: refused, with the rule's own
    sentence, and still outside the walls."""
    s, e, pc = _table()
    e.place_party(_outskirts(e).id)
    _want(pc)
    for seed in range(40):
        e.dice = Dice(seed=seed)
        out = _run(e, "travel", {"place": "the market"})
        assert _refused(out), out.tell
        assert "the gate is where the watch stands" in out.tell
        assert s.at == _outskirts(e).id


def test_a_walk_the_watch_stops_half_way_ends_at_the_last_place_it_could_reach(quiet_streets):
    """The other half of asking at every hop: a walk out of town from somewhere further in
    than the gate is not refused outright any more — it is walked as far as the law lets
    it, to the last place before the gate, and stopped there with the rule's sentence and
    the "got no further" line the meetings use. Before, the whole walk was asked about at
    its end and refused from where it began, as though the streets on the way did not
    exist."""
    from rules import places as places_mod

    s, e, pc = _table()
    out_id = _outskirts(e).id
    known = e.places()

    def first_way_out(hops):
        """Where on the route the first entrance is (a gate, or a crossing of the walls:
        `places.ENTRANCES`), or -1."""
        names = [places_mod.find(known, h).name for h in hops]
        return next((i for i, n in enumerate(names) if n in places_mod.ENTRANCES), -1)

    start = next(p.id for p in known
                 if places_mod.setting_of(p.id) == "in"
                 and first_way_out(places_mod.route(known, p.id, out_id)) >= 1)
    hops = places_mod.route(known, start, out_id)
    names = [places_mod.find(known, h).name for h in hops]
    gate_at = first_way_out(hops)
    e.place_party(start)
    _want(pc)
    out = _run(e, "travel", {"place": "the outskirts"})
    assert not _refused(out), out.tell
    assert s.at == hops[gate_at - 1], (names, s.at)
    assert "the gate is where the watch stands" in out.tell
    assert f"got no further than {names[gate_at - 1]}" in out.tell
    eff = out.effects[0]
    assert eff["stopped_short"] and eff["watch_stopped"] and eff["meant_for"] == "the outskirts"
    # The streets walked are on the record; the gate it never reached is not.
    assert set(hops[:gate_at]) <= set(s.places_been())
    assert hops[gate_at] not in s.places_been()


def test_a_way_past_the_gate_goes_round_the_arch_it_only_passes(quiet_streets):
    """`knows.way-past-gate` (a scheme's witness, a smuggler's door) always opened the open
    road and never the gate itself. Asked hop by hop, the gate on the way out to the
    grassland would have refused the very character the tag was granted to; a gate only
    passed through is gone round, and walking TO it is still walking into the watch."""
    s, e, pc = _table()
    _want(pc)
    pc.apply_effect(ActiveEffect(name="a way out", kind="situation", key="test:way",
                                 source="test", origin="test", duration="until-dismissed",
                                 tags=("knows.way-past-gate",)))
    out = _run(e, "travel", {"biome": "grassland"})
    assert not _refused(out), out.tell
    assert s.at != MARKET
    e.place_party(MARKET)
    assert _refused(_run(e, "travel", {"place": "the gate"}))


# --- reader two: prices and the counter -----------------------------------------------------

def test_the_wanted_pay_half_again_and_are_paid_less():
    """This app's multiplier, stated in `rules/pricing.py` and nowhere else: the book
    has no rule, and the traditions either refuse or ignore. Both columns move — a
    fence who charges a fugitive more pays them less for the same reason."""
    _, _, pc = _table()
    jar = _jar()
    open_price = pricing.worth(jar)
    open_offer = pricing.what_a_shop_pays(jar)
    assert pricing.worth(jar, buyer=pc, town=TOWN) == open_price
    _want(pc)
    assert pricing.worth(jar, buyer=pc, town=TOWN) == round(open_price * pricing.WANTED_MARKUP, 2)
    assert pricing.what_a_shop_pays(jar, seller=pc, town=TOWN) == \
        round(open_offer / pricing.WANTED_MARKUP, 2)
    # Elsewhere, the open price.
    assert pricing.worth(jar, buyer=pc, town=ELSEWHERE) == open_price


def test_the_suspected_pay_more_and_nobody_refuses_them():
    _, _, pc = _table()
    _want(pc, how="suspected")
    jar = _jar()
    assert pricing.markup_for(pc, TOWN) == pricing.SUSPECTED_MARKUP
    assert 1.0 < pricing.SUSPECTED_MARKUP < pricing.WANTED_MARKUP
    assert pricing.worth(jar, buyer=pc, town=TOWN) > pricing.worth(jar)


@pytest.fixture
def counter(tmp_path):
    """A live campaign with a stallholder in the scene, so the trade panel opens."""
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        c.scene.location_id = TOWN
        c.engine().place_party(MARKET)
        c.scene.add(instantiate("guildhand", scene=c.scene, name="the stallholder"))
        c.save()
        yield c
        cm._LIVE.clear()


def _panel(body=None):
    return Client().post("/api/trade", data=json.dumps(body or {}),
                         content_type="application/json")


def test_the_counter_refuses_the_wanted_with_the_reason_named(counter):
    """The panel's half of the reader. `_merchant_here` alone would have answered
    "there is nobody here to trade with", which is a lie with a merchant in the scene
    and names no fix; the refusal says wanted, and which door is still open."""
    c = counter
    pc = c.scene.pc()
    _want(pc)
    c.save()
    r = _panel()
    assert r.status_code == 409, r.content
    why = r.json()["error"]
    assert "wanted" in why and "clear your name" in why.lower()
    r = Client().post("/api/trade/do", data=json.dumps({"op": "buy", "item": "x"}),
                      content_type="application/json")
    assert r.status_code == 409 and "wanted" in r.json()["error"]


def test_the_counter_opens_to_the_suspected_at_a_markup(counter):
    c = counter
    pc = c.scene.pc()
    pc.add_stock(_jar())
    plain = _panel()
    assert plain.status_code == 200, plain.content
    before = {row["id"]: row["gp"] for row in plain.json()["theirs"]}
    mine_before = plain.json()["mine"][0]["gp"]
    _want(pc, how="suspected")
    c.save()
    marked = _panel()
    assert marked.status_code == 200, marked.content
    assert marked.json()["law"] == "suspected"
    after = {row["id"]: row["gp"] for row in marked.json()["theirs"]}
    assert after and all(after[k] == round(before[k] * pricing.SUSPECTED_MARKUP, 2)
                         for k in after)
    assert marked.json()["mine"][0]["gp"] < mine_before


# --- reader three: the guards -------------------------------------------------------------

def _brawl(s, e, pc):
    """A thug to swing at and a watchman minding his own business, both here."""
    thug = s.add(instantiate("thug", scene=s, name="a thug"), zone="near")
    guard = s.add(instantiate("watchman", scene=s, name="a watchman"), zone="far")
    intents = e.validate([{"op": "attack", "actor": "pc", "target": thug.ref,
                           "because": "t", "params": {}}], origin="author:test")
    e.run(intents)
    return thug, guard


def test_a_guard_joins_against_the_wanted_when_a_fight_starts():
    """The plan: "guards join a fight against the player through the existing
    join-fight door". Before this a watchman watched a wanted man start a brawl and
    stayed a bystander — off the initiative, on the map, painted as nobody's."""
    s, e, pc = _table()
    _want(pc)
    thug, guard = _brawl(s, e, pc)
    assert s.in_encounter
    assert guard.ref in s.sides["them"], s.sides
    assert guard.ref in [r for r, _ in s.initiative]


def test_a_guard_stays_out_of_a_fight_nobody_is_wanted_for():
    """`rally` already keeps a watchman out of a fight between the player and a thug —
    civilians stay civilians. The warrant is the only thing that changes that."""
    s, e, pc = _table()
    thug, guard = _brawl(s, e, pc)
    assert s.in_encounter
    assert all(guard.ref not in refs for refs in s.sides.values()), s.sides


def test_anyone_tagged_as_the_law_joins_and_a_warrant_elsewhere_brings_nobody():
    """`role.guard` is the vocabulary's word for who keeps the law, so a named captain
    spawned off a different template joins too; and the town is read off the ground
    the fight is on, so being wanted in the next town over brings no one."""
    s, e, pc = _table()
    _want(pc)
    thug = s.add(instantiate("thug", scene=s, name="a thug"), zone="near")
    captain = s.add(instantiate("guildhand", scene=s, name="the captain"), zone="far")
    captain.apply_effect(ActiveEffect(name="captain of the watch", kind="situation",
                                      key="role:captain", source="rule:test",
                                      duration="until-dismissed", tags=(states.GUARD,)))
    e.run(e.validate([{"op": "attack", "actor": "pc", "target": thug.ref,
                       "because": "t", "params": {}}], origin="author:test"))
    assert captain.ref in s.sides["them"]

    s2, e2, pc2 = _table()
    _want(pc2, town=ELSEWHERE)
    thug2, guard2 = _brawl(s2, e2, pc2)
    assert all(guard2.ref not in refs for refs in s2.sides.values())


# --- removal: one call, every bite gone -------------------------------------------------------

def test_clearing_the_name_is_one_removal_and_every_bite_evaporates():
    """Law 2, proved on this state: the gate refuses and the counter marks up while the
    effect is held; `remove_effects(source=...)` — the scheme's "justice" outcome, or a
    GM rule — takes the one record, and the gate opens and the price falls with nothing
    else touched. No second store to forget, no flag to reset."""
    s, e, pc = _table()
    jar = _jar()
    open_price = pricing.worth(jar)
    _want(pc)
    assert _refused(_run(e, "travel", {"place": "the gate"}))
    assert pricing.worth(jar, buyer=pc, town=TOWN) > open_price

    gone = pc.remove_effects(source=SOURCE)
    assert len(gone) == 1 and states.wanted_tag(TOWN) in gone[0].tags

    assert states.standing_with_the_law(pc, TOWN) == ""
    assert pricing.worth(jar, buyer=pc, town=TOWN) == open_price
    out = _run(e, "travel", {"place": "the gate"})
    assert not _refused(out), out.tell
    assert s.at.endswith(":the-gate")
    assert "wanted" not in out.tell and "look twice" not in out.tell

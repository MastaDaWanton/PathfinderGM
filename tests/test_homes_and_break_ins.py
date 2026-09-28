"""The still-not-built list of 2026-09-27: a door that stays open to a friend, homes for
keepers and for the characters the world wrote, and breaking in.

Researched before building (sources in docs/the-population.md, "Built: the still-not-
built list"):
  * Stardew Valley: a bedroom opened at two hearts "is permanently unlocked even if the
    heart meter goes below 2 hearts".
  * Pierre lives in his shop and Belethor sleeps upstairs in his: a keeper under a roof
    lives on the premises; reachable after hours, and not trading.
  * PF1e Core Rulebook: a good wooden door, locked, breaks at DC 18 (Table 13-2 and the
    Breaking Items table agree for it); an average lock is Disable Device DC 25, +10
    without thieves' tools, trained only; Perception hears the sound of battle at -10 and
    a whisper at 15, +10 for a sleeping listener.
  * Skyrim: trespass and lockpicking are crimes when seen, with a warning before the
    fine — here, suspected the first time and wanted the next.
"""
from __future__ import annotations

import pytest

from gm import judgement
from rules import attitude, keepers, population, residency, states
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world.loader import load_cached

WORLD = load_cached("fixtures/aurvantis-campaign.json")
VORMOOR = WORLD.by_name("Vormoor", kind="CITY").id
HOUR = 60


def _town(clock=10 * HOUR, seed=3):
    s = Scene(location_id=VORMOOR)
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.clock_minutes = clock
    e = Engine(s, Dice(seed=seed), world=WORLD)
    e.place_party()
    return s, e


def _friend(s, e, regard):
    rec = population.note(s, "a woman selling bread")
    rec["life"].update(work="baker", work_name="baker", mobility="resident")
    ref = judgement.embody_sought(s, "I talk to the woman selling bread.", WORLD)
    body = s.people[ref]
    attitude.set_regard(body, regard, "test")
    elsewhere = next(p for p in e.places() if p.id != s.at)
    e.run(e.validate([{"op": "travel", "params": {"place": elsewhere.name}}],
                     origin="author:test"))
    return rec, body


def _call(e, who, visit=True):
    return e.run(e.validate([{"op": "call_on", "params": {"who": who, "visit": visit}}],
                            origin="author:test")).outcomes[0]


def _walk_away(e):
    s = e.scene
    street = next(p for p in e.places() if p.id != s.at and not p.id.endswith("house"))
    e._journeyed = ""
    e.run(e.validate([{"op": "travel", "params": {"place": street.name}}],
                     origin="author:test"))


# --- once a friend ------------------------------------------------------------------------

def test_once_let_in_as_a_friend_the_door_stays_open_when_the_friendship_cools():
    s, e, = _town(10 * HOUR)                      # met by day
    rec, body = _friend(s, e, regard=80)
    s.advance(12 * HOUR)                          # called on at ten at night: home
    first = _call(e, "woman selling bread")
    assert "lets you in" in first.tell
    assert s.pc().has_state(f"bond.welcome.{rec['id']}")
    _walk_away(e)
    attitude.set_regard(body, 45, "test")        # indifferent now
    s.advance(4 * HOUR)                           # two in the morning: only a friend opens
    again = _call(e, "woman selling bread")
    assert "lets you in" in again.tell, again.tell


def test_the_welcome_is_not_for_somebody_who_now_hates_you():
    s, e = _town(10 * HOUR)
    rec, body = _friend(s, e, regard=80)
    s.advance(12 * HOUR)
    first = _call(e, "woman selling bread")
    assert "lets you in" in first.tell
    _walk_away(e)
    attitude.set_regard(body, 5, "test")         # hostile
    again = _call(e, "woman selling bread")
    assert "lets you in" not in again.tell


# --- keepers' and the world's homes ---------------------------------------------------------

def _keeper_at(s, e, name):
    place = next(p for p in e.places() if p.name == name)
    e.run(e.validate([{"op": "travel", "params": {"place": place.name}}],
                     origin="author:test"))
    k = keepers.keeper_in(s, place.id)
    assert k is not None, f"nobody keeps {name}"
    return place, k


def test_a_keeper_under_a_roof_lives_at_the_shop_and_is_knocked_up_at_night():
    s, e = _town(10 * HOUR)
    e.run(e.validate([{"op": "found", "params": {"name": "the smithy", "kind": "smithy"}}],
                     origin="author:test"))
    place, keeper = _keeper_at(s, e, "the smithy")
    assert keepers.lives_in(place.id)
    _walk_away(e)
    s.advance(16 * HOUR)                          # two in the morning
    out = e.run(e.validate([{"op": "travel", "params": {"place": place.name}}],
                           origin="author:test")).outcomes[0]
    assert out.status == "refused" and "woken by the knocking" in out.tell


def test_a_stall_keeper_has_a_house_to_call_at_and_goes_there_when_the_stall_shuts():
    s, e = _town(10 * HOUR)
    place, keeper = _keeper_at(s, e, "the market")
    attitude.set_regard(keeper, 80, "test")
    _walk_away(e)
    call = _call(e, keeper.name, visit=False)
    assert call.status == "resolved", call.tell
    house = call.effects[0]["house"]
    s.advance(10 * HOUR)                          # eight in the evening: the stall is shut
    _walk_away(e)
    assert keeper.at == house


def test_a_character_the_world_wrote_is_called_on_by_name():
    s, e = _town(22 * HOUR)
    person = next(x for x in WORLD.entities.values()
                  if x.kind == "CHARACTER" and x.parent_id == VORMOOR)
    got = e._callee(person.name)
    assert isinstance(got, dict) and got["kind"] == "world", got
    call = _call(e, person.name, visit=False)
    assert call.status == "resolved", call.tell
    assert f"{person.name}'s house" in call.tell


# --- breaking in -----------------------------------------------------------------------------

def _house(s, e, clock_after=None, regard=45):
    rec, body = _friend(s, e, regard=regard)
    call = _call(e, "woman selling bread", visit=False)
    house = call.effects[0]["house"]
    street = call.effects[0]["street"]
    e._journeyed = ""
    e.run(e.validate([{"op": "travel", "params": {"place": street}}], origin="author:test"))
    for a in list(s.actors.values()):              # an empty street: no witnesses
        if not a.is_pc:
            s.move(a.ref, residency.offstage(VORMOOR, f"away-{a.ref}"))
    if clock_after is not None:
        s.clock_minutes = clock_after
    return rec, body, house


def _break(e, how="force", who=""):
    from rules.engine import _NeedsPlayerRoll  # noqa: F401 — the roll is the player's

    s = e.scene
    s.pc().abilities["str"] = 30                    # certain to break it
    return e.run(e.validate([{"op": "break_in", "actor": "pc",
                              "params": {"who": who, "how": how}}], origin="author:test"))


def test_the_player_rolls_to_break_the_door():
    s, e = _town(10 * HOUR)
    _house(s, e)
    res = e.run(e.validate([{"op": "break_in", "actor": "pc", "params": {"how": "force"}}],
                           origin="author:test"))
    assert res.awaiting is not None and res.awaiting["dc"] == 18


def test_a_door_forced_while_she_is_out_opens_and_stays_broken():
    s, e = _town(10 * HOUR)
    rec, body, house = _house(s, e)
    res = _break(e)
    res = e.resume(20) if res.awaiting else res
    out = next(o for o in res.outcomes if o.op == "break_in")
    assert "gives" in out.tell and s.at == house
    assert next(p for p in s.founded if p["id"] == house)["door"] == "broken"
    assert not states.standing_with_the_law(s.pc(), VORMOOR), "nobody saw it"


def test_picking_a_lock_without_training_is_refused_with_the_other_way_named():
    s, e = _town(10 * HOUR)
    _house(s, e)
    pc = s.pc()
    pc.ranks.pop("disable device", None)
    pc.flat_skills.pop("disable device", None)
    res = e.run(e.validate([{"op": "break_in", "actor": "pc", "params": {"how": "pick"}}],
                           origin="author:test"))
    out = res.outcomes[0]
    assert out.status == "refused" and "trained only" in out.tell and "forced" in out.tell


def test_seen_breaking_in_is_suspected_and_twice_is_wanted():
    s, e = _town(10 * HOUR)
    rec, body, house = _house(s, e)
    watcher = population.embody(s, "a watchman", "guildhand", world=WORLD)
    assert watcher.ref in s.actors
    res = _break(e)
    res = e.resume(1) if res.awaiting else res   # a one: the door holds, and it is seen
    assert states.standing_with_the_law(s.pc(), VORMOOR) == "suspected"
    res = _break(e)
    res = e.resume(1) if res.awaiting else res
    assert states.standing_with_the_law(s.pc(), VORMOOR) == "wanted"


def test_a_guardhouse_is_not_a_shop_and_is_not_knocked_at():
    """Measured by the storeys suite: walking into the guardhouse at midnight was refused
    as if it were a baker's."""
    s, e = _town(0)
    guard = next((p for p in e.places() if p.name == "the guildhall"), None)
    if guard is None:
        pytest.skip("no civic building under a roof here")
    _keeper_at(s, e, guard.name)
    _walk_away(e)
    s.clock_minutes = 24 * HOUR + 2 * HOUR
    out = e.run(e.validate([{"op": "travel", "params": {"place": guard.name}}],
                           origin="author:test")).outcomes[0]
    assert out.status == "resolved", out.tell


def test_the_players_words_are_read_as_breaking_in():
    assert judgement.breaks_in("I kick in her door.") == ("her", "force")
    assert judgement.breaks_in("I pick the lock on her door.") == ("her", "pick")
    assert judgement.breaks_in("I break into the bread seller's house.") == ("bread seller",
                                                                             "force")
    assert judgement.breaks_in("I break into song.") == ("", "")
    raw = judgement.inject_break_in([{"op": "travel", "params": {"place": "her house"}}],
                                    "I break into her house.", Scene(location_id=VORMOOR))
    assert [r["op"] for r in raw] == ["break_in"]


# --- found live, 2026-09-27 (the `homes` script, gemma-4-12B) --------------------------------

def test_prose_may_not_open_a_door_the_engine_held():
    """Live: the engine rolled "The door ... holds." and the prose wrote "The wood groans
    and splinters under the force of your boot ... The door flies inward"."""
    from gm import narration

    beat = ("The wood groans and splinters under the force of your boot, and finally gives "
            "way. The door flies inward. What do you do?")
    kinds = [f.kind for f in narration.review(
        beat, doors=[{"opened": False, "how": "force"}]).findings]
    assert "contradicts-the-engine" in kinds
    held = "The door shudders under your boot but holds. What do you do?"
    assert not narration.opens_a_held_door(held)
    # And a door that did give may be written giving.
    assert "contradicts-the-engine" not in [f.kind for f in narration.review(
        beat, doors=[{"opened": True, "how": "force"}]).findings]


def test_a_break_in_turn_spawns_nobody_and_takes_no_lock():
    """Live: "I pick the lock on her door" came back with `give item="lock on her door"`
    ("Kesst Vayr takes lock on her door"), and "I kick in her door" with a thug spawned
    as "new" — who then witnessed the break-in and made the character suspected."""
    raw = judgement.inject_break_in(
        [{"op": "give", "params": {"item": "lock on her door", "to": "pc"}},
         {"op": "spawn", "params": {"template": "thug", "name": "new"}},
         {"op": "break_in", "params": {"who": "her", "how": "pick"}}],
        "I pick the lock on her door.", Scene(location_id=VORMOOR))
    assert [r["op"] for r in raw] == ["break_in"]


def test_the_outcome_written_into_a_break_in_is_ignored_not_refused():
    """Live: `break_in` with `success` cost an attempt, and the repair after it invented a
    thug."""
    from rules.intents import parse_all

    got = parse_all([{"op": "break_in", "params": {"how": "force", "success": True}}])
    assert got[0].params.get("how") == "force" and "success" not in got[0].params


def test_when_the_rewrite_fails_the_door_still_stays_shut():
    """Live: the held-door rewrite was asked for and the model kept "the metal yields to
    your touch with a satisfying, hollow click" — the beat shipped unrepaired. The cut is
    the backstop, as it is for the dead and for false claims."""
    from gm import narration

    beat = ("You kneel at the door in the grey light. The lock is a simple, rusted thing, "
            "and the metal yields to your touch with a hollow click. Inside, the air is "
            "heavy and sweet.")
    text, cut = narration.hold_the_door(beat, [{"opened": False, "how": "pick"}])
    assert cut and "Inside" not in text and "yields" not in text
    assert text.startswith("You kneel at the door") and "door stays shut" in text
    same, none = narration.hold_the_door(beat, [{"opened": True, "how": "pick"}])
    assert same == beat and not none

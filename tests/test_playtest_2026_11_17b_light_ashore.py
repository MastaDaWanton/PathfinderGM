"""Playtest 2026-11-17 (b), the light / ashore / rest lane: items 1, 2, 3, 6, 9 and R1.

Vesna Kroll on 0.4.1 (master cf3d37f3). Each test names the turn and what was measured.
"""
from __future__ import annotations

from gm import acts_to_ops
from rules import places as places_mod
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from tests.test_ships_and_piracy import held_at_quay  # noqa: F401
from world import loader

WORLD = loader.load_cached("fixtures/pangrella-campaign.json")
TOWN = "7ef5e373c993"                                  # Mirabalos, the playtest's port city
MARKET = f"{TOWN}~urban:the-market"


def _table(at=MARKET):
    s = Scene(location_id=TOWN)
    s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, Dice(seed=3), world=WORLD)
    e.place_party(at)
    return s, e


def _run(e, intents):
    return e.run(e.validate([dict(i, because=i.get("because") or "t") for i in intents],
                            origin="author:test")).outcomes


# --- #6: "go ashore" from her own deck --------------------------------------------------

def test_go_ashore_from_her_own_deck_walks_down_the_gangplank(held_at_quay):
    """#6 (T433): "I go ashore and ask the harbourmaster…" from the Red Gull's deck, tied up
    at Mirabalos, was read `go: ashore`; the table answered 'You don't know of anywhere
    called "ashore" here', no travel was built, and she asked a harbourmaster who stood on
    the quay."""
    scene, engine, pc, ship = held_at_quay
    rows = acts_to_ops.table({"question": False, "claims": [], "actions": [
        {"act": "go", "place": "ashore", "span": "go ashore"}]}, scene,
        places=tuple(engine.places()))
    assert not rows[0].nowhere, rows[0].nowhere
    assert [i["op"] for i in rows[0].intents] == ["travel"], rows[0].intents
    out = next(o for o in _run(engine, rows[0].intents) if o.op == "travel")
    assert "You step ashore." in out.tell, out.tell
    assert engine.aboard() is None and engine.here().name == "the docks"


def test_ashore_means_nothing_on_land():
    """Not aboard, "ashore" names no place: the walk is refused as nowhere, never a guess."""
    s, e = _table()
    assert places_mod.the_settlement(e.places(), "ashore", MARKET) is None


# --- #3 and #1: a fresh torch lit, and a torch that burns out ---------------------------

def test_lighting_a_fresh_torch_lights_one_from_the_shelf():
    """#3 (T429): "I light a fresh torch and climb back up…", torches on the shelf, built no
    light: "a fresh torch" is not `same` as "torch", and the page struck one anyway. The
    shelf's own name found whole among the words, among the things that light only."""
    from tests.test_items_and_trade_2026_11_17 import _bought, _frame, _scene, _turn

    for said in ("a fresh torch", "the last good torch",
                 "a torch with my flint and steel"):
        scene = _scene()
        _bought(scene, "torch", 3)
        _bought(scene, "flint and steel")
        _rows, raw = _turn(scene, _frame({"act": "use", "object": said}))
        lit = [r for r in raw if r.get("op") == "use_item"]
        assert len(lit) == 1 and lit[0]["params"]["item"].startswith("torch"), (said, raw)


def test_a_torch_burning_out_is_told_as_going_out():
    """#1 (T427): her torch ran out in her sleep as "Normal light 20 ft, one step brighter
    out to 40 ft wears off Vesna Kroll", and the page said "You strike a torch, and its
    flame pushes back the gloom". The tell names the torch and says it is gone."""
    from tests.test_items_and_trade_2026_11_17 import _bought, _frame, _scene, _turn

    scene = _scene()
    _bought(scene, "torch", 3)
    _rows, raw = _turn(scene, _frame({"act": "use", "object": "a torch"}))
    e = Engine(scene, Dice(seed=1))
    e.run(e.validate(raw))
    assert scene.pc().has_state("light.carried")
    out = _run(e, [{"op": "rest", "actor": "pc", "params": {"kind": "night"}}])
    ended = next(o for o in out if o.op == "ended")
    assert "torch burns out, and its light is gone" in ended.tell, ended.tell
    assert "wears off" not in ended.tell
    assert not scene.pc().has_state("light.carried")


# --- #2: a pending level and a second sleep inside the day ------------------------------

def test_a_level_earned_settles_in_a_sleep_that_heals_nothing():
    """#2 (T427): "Enough to advance — it will settle with a night's sleep" since T413,
    then eight hours slept 4 h 40 min after a full night were refused whole ("nothing heals
    and nothing is recovered") and the level waited with no word of when. Healing is once a
    day (CRB p.191); the level is not tied to that rest (CRB, Advancing Your Character)."""
    from rules import xp as xp_mod

    s, e = _table()
    pc = s.pc()
    _run(e, [{"op": "rest", "actor": "pc", "params": {"kind": "night"}}])
    level = pc.level
    told = e.award_xp(pc, xp_mod.total_for(level + 1) - pc.xp, "a test")
    assert "settle with a night's sleep" in told
    hp = pc.hp
    out = _run(e, [{"op": "rest", "actor": "pc", "params": {"kind": "night"}}])
    rest = next(o for o in out if o.op == "rest")
    assert "already had a full night's rest" in rest.tell, rest.tell
    assert pc.level == level + 1, rest.tell
    assert f"Level {level + 1} settles all the same" in rest.tell, rest.tell
    assert pc.hp >= hp


# --- #9: the player's quotation and the reply beside it ---------------------------------

def test_a_cut_sentence_leaves_the_quote_marks_either_side():
    """#9 (T445): the price cut from the head of the barkeep's reply was '" \'A room and a
    hot meal will cost you three gold and a few silver.', taking the close of the player's
    question and the open of the reply, and the page read 'What do I owe you? I can get you
    a seat and a plate, but the bed stays separate,' the one behind the bar says'."""
    from rules import intents

    page = ('You look at the Korvu behind the bar and ask, "A room for the night, and a hot '
            'meal. What do I owe you?" \'A room and a hot meal will cost you three gold and a '
            'few silver. I can get you a seat and a plate, but the bed stays separate,\' the '
            'one behind the bar says flatly.')
    claim = next(c for c in intents.find_outcome_claims(page) if c.why == "states a price")
    assert claim.sentence.startswith("A room and a hot meal will cost")
    cut = " ".join(intents.cut_sentence(page, claim.sentence).split())
    assert 'What do I owe you?" \'I can get you a seat' in cut, cut
    out, _gone = intents.cut_outcome_claims(page)
    assert 'What do I owe you?" \'I can get you a seat' in out, out


def test_a_plain_question_is_not_told_as_a_demand():
    """#9 (T445): '"… What do I owe you?" I ask the barkeep' was written 'You look at the
    Korvu behind the bar and demand, "…"'. How the player spoke is theirs."""
    from gm.planned import plain_speech

    typed = '"A room for the night, and a hot meal. What do I owe you?" I ask the barkeep.'
    wrote = 'You look at the Korvu and demand, "A room for the night, and a hot meal. ' \
            'What do I owe you?"'
    assert plain_speech(wrote, typed).startswith("You look at the Korvu and ask, \"A room")
    assert plain_speech('You snap, "Get out."', "I tell him to get out") \
        == 'You say, "Get out."'
    # Their own verb stands.
    own = 'You demand, "Pay me."'
    assert plain_speech(own, 'I demand, "Pay me."') == own


# --- R1: a box looked into at the end of a walk ----------------------------------------

def test_a_box_opened_where_the_walk_ends_is_looked_into():
    """R1 (2026-11-17): "I go to the broken pen and open the gaoler's box to see what's
    inside" from the cells read `go`, `other: the gaoler's box`, `look` (intended); the
    look-in asked for the box in the cells, found none, and the 50 gp went unsaid."""
    s, e = _table()
    docks = places_mod.find(e.places(), "the docks")
    s.props.append({"name": "a gaoler's box", "owner": "", "state": "intact", "turn": 0,
                    "at": docks.id, "contents": {"purse": {"gp": 50}, "goods": {}}})
    frame = {"question": False, "claims": [], "actions": [
        {"act": "go", "place": "the docks", "span": "go to the docks"},
        {"act": "other", "object": "the gaoler's box", "span": "open the gaoler's box"},
        {"act": "look", "commit": "intended", "object": "what's inside",
         "span": "to see what's inside"}]}
    rows = acts_to_ops.table(frame, s, places=tuple(e.places()))
    raw = acts_to_ops.apply([{"op": "travel", "actor": "pc", "params": {"place": "the docks"}},
                             {"op": "narrate_only"}], rows, frame, s)
    raw = acts_to_ops.order(raw, rows)
    told = " ".join(o.tell for o in _run(e, raw))
    assert "Inside: 50 " in told and "gold" in told, told

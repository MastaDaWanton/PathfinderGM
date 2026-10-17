"""Scenery the narration invented is not a weapon until something puts it on the ledger.

The report of 2026-10-16 (a real player's 0.2.19 game, a market fight, free narrator):

  * "Your dagger skids past her hip and clatters against a clay pot … the pot shatters into
    shards that spray outward" — nothing in the engine broke anything;
  * the next beat, "a heavy wooden crate sits partially overturned, its contents of iron
    nails" — more scenery nobody recorded;
  * and the fight-beats lane found the hole under both: "grab a shard of the broken pot"
    minted the shard (`Engine._op_give`'s "the world never runs out") and an improvised
    attack took any `params.item` with no prop behind it. Invented scenery, changed by
    prose, became a usable weapon.

The rule now (gm/scenery.py has the prior art): a pick-up from nowhere and an improvised weapon must name
something on the props ledger or in hand (`Engine._picked_from_nowhere`,
`Engine._improvised_unheld`). The narration's scenery gets onto the ledger through one
door before the plan runs (gm/scenery.py): one closed question of the passages the player
read — shown here (quoted, the quote checked in code), commonplace here, or not here.
"""
from __future__ import annotations

import json

import pytest

from gm import scenery
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

SHARD = "shard of the broken pot"
SHATTERS = ("Your dagger skids past her hip and clatters against a clay pot on the nearest "
            "stall; the pot shatters into shards that spray outward across the cobbles.")
HOLDS = ("Your dagger skids past her hip and clangs off a clay pot on the nearest stall; "
         "the pot rocks on its shelf but holds.")


@pytest.fixture
def market():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="the woman with the braid"))
    return s


def _woman(s):
    return next(r for r, a in s.actors.items() if a.name == "the woman with the braid")


def _grab_and_stab(s):
    return [{"op": "give", "actor": "pc", "params": {"item": SHARD, "to": "pc"},
             "because": "the player picked it up to use it"},
            {"op": "attack", "actor": "pc", "target": _woman(s),
             "params": {"weapon": "improvised", "item": SHARD}}]


# --- the engine: nothing from nowhere ---------------------------------------------------------

def test_a_shard_nothing_broke_is_neither_picked_up_nor_swung(market):
    """The report's turn, with nothing on the ledger: before 2026-10-16 the give minted the
    shard ("the world never runs out") and the attack opened a fight swinging it. Now the
    pick-up is refused with what lies here named, the swing is refused, and no fight
    opens — a blow with a thing that does not exist is not first violence."""
    engine = Engine(market, Dice(seed=4))
    res = engine.run(engine.validate(_grab_and_stab(market)))
    give, attack = res.outcomes[0], res.outcomes[1]
    assert give.status == "refused" and "no shard of the broken pot here" in give.tell
    assert "Nothing loose lies here" in give.tell
    assert SHARD not in market.pc().goods
    assert attack.status == "refused" and "not in hand and none lies here" in attack.tell
    assert not market.in_encounter, "a swing of nothing opens no fight"
    assert not market.awaiting, "and asks for no die"


def test_a_thing_on_the_ledger_is_picked_up_and_swung(market):
    """The same turn with the shard lying here on the ledger: picked up, swung at -4."""
    market.place_prop(SHARD, state="intact")
    engine = Engine(market, Dice(seed=4))
    res = engine.run(engine.validate(_grab_and_stab(market)))
    assert res.outcomes[0].status != "refused"
    assert SHARD in market.pc().goods
    assert market.in_encounter, "the first blow with a real thing opens the fight"


def test_a_carried_thing_is_swung_without_a_record(market):
    """A goods line is in hand: "I hit him with the chair leg" I carry needs no ledger."""
    market.pc().goods["chair leg"] = 1
    engine = Engine(market, Dice(seed=4))
    res = engine.run(engine.validate([{"op": "attack", "actor": "pc", "target": _woman(market),
                                       "params": {"weapon": "improvised",
                                                  "item": "chair leg"}}]))
    assert res.outcomes[0].status != "refused"


def test_a_documents_give_is_still_the_documents_word(market):
    """An origin-stamped give (a test, the author's cheat, a jar) is not a pick-up from
    nowhere: the document says it exists."""
    engine = Engine(market, Dice(seed=4))
    engine.run(engine.validate([{"op": "give", "params": {"item": "pebble", "to": "pc"}}],
                               origin="author:test"))
    assert "pebble" in market.pc().goods


# --- the scenery step: what the narration showed is ledgered first ----------------------------

def _asker(answer, quote=""):
    asked = []

    def ask(place, passages, thing):
        asked.append((place, passages, thing))
        return answer, quote

    ask.asked = asked
    return ask


def test_a_shard_the_page_showed_shattering_is_ledgered_and_then_swung(market):
    """What the player read is what is there (the owner's rule for people, 2026-10-01,
    applied to things): a pot the page showed shattering left shards, and grabbing one
    works. The quote is checked in code to be the page's own narration."""
    engine = Engine(market, Dice(seed=4))
    raw = _grab_and_stab(market)
    ask = _asker(scenery.SHOWN, "the pot shatters into shards")
    rows = scenery.ground(raw, engine, [SHATTERS], ask_fn=ask)
    assert [r["thing"] for r in rows] == [SHARD] and rows[0]["ledgered"]
    assert len(ask.asked) == 1, "asked once, though the plan names it twice"
    rec = market.prop_named(SHARD)
    assert rec["origin"] == "narrated" and rec["quote"] == "the pot shatters into shards"
    res = engine.run(engine.validate(raw))
    assert res.outcomes[0].status != "refused" and SHARD in market.pc().goods


def test_a_shown_answer_whose_quote_misses_is_kept_as_fitting_not_refused(market):
    """Biased toward allowing (the coordinator, 2026-10-17): reading about a torch and then
    hearing "there is no torch here" breaks play harder than the old minting did. A reader
    that says "shown" with a quote that paraphrases or is not on the page is not refused for
    the quote: the thing is ledgered as fitting the place, and the row says the quote
    missed. The refusals are the answers that name WHY a thing is not there."""
    engine = Engine(market, Dice(seed=4))
    rows = scenery.ground([{"op": "give", "actor": "pc", "params": {"item": "torch",
                                                                   "to": "pc"}}],
                          engine, ["Torches gutter in their iron brackets."],
                          ask_fn=_asker(scenery.SHOWN, "a torch burns on the wall"))
    assert rows[0]["ledgered"] and "quote is not the narration" in rows[0]["note"]
    assert market.prop_named("torch")["origin"] == "commonplace"


def test_a_refusal_of_a_thing_every_word_of_which_is_on_the_page_is_overruled(market):
    """Held out, 2026-10-17: "The fishwife hurls a bucket of eel water at your feet" came
    back "only if something had broken" for "the bucket", 2 runs of 2. A refusal that the
    thing was never shown or is a piece of something unbroken is overruled when every word
    of the player's name for it is in the narration — so the shard beside a pot that
    "rocks but holds" stays refused ("shard", "broken" are not on the page), and a thing
    the page says was carried off (`ELSEWHERE`) is never overruled."""
    bucket = "The fishwife hurls a bucket of eel water at your feet."
    got = scenery.decide("the market", (), [bucket], "the bucket",
                         ask_fn=_asker(scenery.BROKEN))
    assert got["ledger"] and "every word" in got["why"]
    got = scenery.decide("the market", (), [HOLDS], SHARD, ask_fn=_asker(scenery.BROKEN))
    assert not got["ledger"]
    gone = "The guard pulls the torch from its bracket and carries it off."
    got = scenery.decide("the gate", (), [gone], "the torch",
                         ask_fn=_asker(scenery.ELSEWHERE))
    assert not got["ledger"]
    said = "'I'll break this bottle over your skull,' he snarls."
    got = scenery.decide("the tavern", (), [said], "the bottle",
                         ask_fn=_asker(scenery.WRONG_PLACE))
    assert not got["ledger"], "speech is blanked: a bottle only spoken of is not on the page"


def test_the_reader_is_told_what_kind_of_place_it_is():
    asked = _asker(scenery.COMMON)
    scenery.decide("the tavern", ("a tavern or inn", "inside a building"), ["Loud."],
                   "a stool", ask_fn=asked)
    assert asked.asked[0][0] == "the tavern (a tavern or inn; inside a building)"


def test_a_commonplace_thing_is_ledgered_and_a_thing_not_here_is_not(market):
    engine = Engine(market, Dice(seed=4))
    give = [{"op": "give", "actor": "pc", "params": {"item": "stone", "to": "pc"}}]
    scenery.ground(give, engine, [HOLDS], ask_fn=_asker(scenery.COMMON))
    assert market.prop_named("stone")["origin"] == "commonplace"
    scenery.ground(_grab_and_stab(market), engine, [HOLDS], ask_fn=_asker(scenery.ABSENT))
    assert market.prop_named(SHARD) is None


def test_nothing_is_asked_about_what_is_already_somewhere(market):
    """In hand, on the ledger, coin, a hand-over with a giver: the engine answers those
    itself, and the reader is not asked (`Engine.unrecorded_thing`)."""
    engine = Engine(market, Dice(seed=4))
    market.pc().goods["chair leg"] = 1
    market.place_prop("lantern", state="intact")
    raw = [{"op": "give", "params": {"item": "lantern", "to": "pc"}},
           {"op": "give", "params": {"item": "5 gp", "to": "pc"}},
           {"op": "give", "params": {"item": "apple", "to": "pc", "from_": _woman(market)}},
           {"op": "attack", "actor": "pc", "target": _woman(market),
            "params": {"weapon": "improvised", "item": "chair leg"}}]
    ask = _asker(scenery.SHOWN, "x")
    assert scenery.ground(raw, engine, [HOLDS], ask_fn=ask) == [] and not ask.asked


def test_in_a_fight_a_steal_of_a_thing_on_the_ground_is_a_pick_up(market):
    """In a fight "I grab a shard of the broken pot" names no holder, and the act table
    builds a Steal at the foe (`acts_to_ops._take` — right for "I take what he was
    carrying"). A thing she does not carry that lies here is stooped for, not stolen;
    a thing she does carry is still a Steal."""
    engine = Engine(market, Dice(seed=4))
    woman = _woman(market)
    market.actors[woman].goods["purse"] = 1
    raw = [{"op": "attack", "actor": "pc", "target": woman,
            "params": {"manoeuvre": "steal", "item": SHARD}},
           {"op": "attack", "actor": "pc", "target": woman,
            "params": {"manoeuvre": "steal", "item": "purse"}}]
    rows = scenery.ground(raw, engine, [SHATTERS],
                          ask_fn=_asker(scenery.SHOWN, "the pot shatters into shards"))
    assert raw[0] == {"op": "give", "actor": "pc", "because": "the player picked it up",
                      "params": {"item": SHARD, "to": "pc"}}
    assert raw[1]["params"]["manoeuvre"] == "steal", "what she carries is still stolen"
    assert [r["thing"] for r in rows] == [SHARD, SHARD]       # ledgered, then picked up


def test_with_the_reader_off_nothing_is_asked_and_the_refusal_stands(market):
    engine = Engine(market, Dice(seed=4))
    assert scenery.ground(_grab_and_stab(market), engine, [SHATTERS], ask_fn=None) == []
    assert market.prop_named(SHARD) is None


def test_the_question_is_closed_and_shows_its_demonstrations():
    """One enum answer and a quote; the demonstrations carry the case the report needs —
    a shard of a pot no passage shows broken is not here."""
    msgs = scenery.messages("the market", HOLDS, SHARD)
    assert scenery.SCHEMA["properties"]["answer"]["enum"] == list(scenery.ANSWERS)
    shown = [json.loads(m["content"])["answer"] for m in msgs if m["role"] == "assistant"]
    assert set(shown) == set(scenery.ANSWERS)
    assert any("shard of a broken pot" in m["content"] for m in msgs if m["role"] == "user")
    assert msgs[-1]["content"].endswith(f"The thing: {SHARD}")

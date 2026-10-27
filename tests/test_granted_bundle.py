"""A thing the narration describes that the engine has already given the player is theirs
already: never a second, dataless item in the pack.

The owner's 0.2.21 report (2026-10-27, planned narration), turn-log rows 71-78:

  * a grioth holding a guarded find gave way, and the engine paid the find into the
    satchel — "The herbs find the grioth held is yours now: 18× Monkshood, 18× Caranator,
    12× Coldwood";
  * the planned slot showing that tell wrote "you find a bundle of herbs — 18 Monkshood,
    18 Caranator, and 12 Coldwood — left behind in its wake": a possession with no act and
    no place, given a scene of its own on the ground;
  * "I take the bundle of herbs" was a pick-up from nowhere, the scenery reader answered
    "shown here" (true of the page — it was never told what had been given), the bundle was
    ledgered as narrated, and the give put `"bundle of herbs": 1` into the goods: one item
    with no catalogue entry beside the 48 herbs it described.

The cure (rules/engine.py `_mark_granted`, gm/scenery.py `ALREADY`): the grant is
remembered on the props ledger as a payment is, the reader is shown it and names which one
the page's thing IS, and the take answers "already in the pack" — Inform's "can't take
what's already taken" rule. The tell says the act and where the herbs went, so a slot has no
gap to fill with a find on the ground. Synthetic scenes only; the owner's save stays out of
the repository.
"""
from __future__ import annotations

import pytest

from gm import planned, scenery
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

HERBS = {"monkshood": 18, "caranator": 18, "coldwood": 12}
NAMES = {"monkshood": "Monkshood", "caranator": "Caranator", "coldwood": "Coldwood"}
PAGE = ("As it retreats, you find a bundle of herbs—18 Monkshood, 18 Caranator, and 12 "
        "Coldwood—left behind in its wake.")


@pytest.fixture
def wood():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    return s, Engine(s, Dice(seed=3))


def _guard_leaves(s, e):
    """A guarded find booked under a guard that has gone (the reaction's "gives way"),
    then settled: the herbs go into the satchel."""
    from rules.bestiary import instantiate

    guard = instantiate("thug", scene=s, name="grioth")
    s.add(guard)
    s.guarded_finds.append({"guard": guard.ref, "guard_name": "grioth", "what": "herbs find",
                            "found": dict(HERBS), "stock": [], "fresh": True,
                            "names": dict(NAMES), "at": s.at})
    s.remove(guard.ref)
    return e._settle_guarded_finds().strip()


def _asker(answer, quote="", given=""):
    asked = []

    def ask(place, passages, thing, shown=()):
        asked.append({"place": place, "passages": passages, "thing": thing,
                      "given": list(shown)})
        return answer, quote, given

    ask.asked = asked
    return ask


def _take(e, item, count=1):
    return e.run(e.validate([{"op": "give", "actor": "pc", "because": "the player took it",
                              "params": {"item": item, "to": "pc", "count": count}}]))


def test_the_guard_gone_the_tell_says_the_herbs_went_into_the_pack(wood):
    """The tell was "The herbs find the grioth held is yours now: …" — no act, no place —
    and the planned slot that showed it wrote the herbs "left behind in its wake" on the
    ground. It now says the act and where they went."""
    s, e = wood
    line = _guard_leaves(s, e)
    assert "yours now" not in line
    assert line.startswith("With the grioth gone, ") and "gathers up the herbs it held" in line
    assert "puts it all in the pack: 18× Monkshood, 18× Caranator, 12× Coldwood" in line
    pc = s.pc()
    assert all(pc.inventory.get(i, 0) == n for i, n in HERBS.items())
    grant = e.granted_here(pc)
    assert [g["name"] for g in grant] == ["the herbs the grioth held"]
    assert grant[0]["held_by"] == pc.ref and not grant[0].get("at"), \
        "a grant is in the pack, never lying anywhere"


def test_the_owners_take_of_the_bundle_is_already_in_the_pack_and_mints_nothing(wood):
    """The report's turn, end to end through the scenery step and the give: the reader is
    shown the grant with what the satchel holds of it now, answers that the bundle IS it,
    and the take says so. Before: `goods["bundle of herbs"] == 1`, a thing with no data."""
    s, e = wood
    _guard_leaves(s, e)
    pc = s.pc()
    goods_before, satchel_before = dict(pc.goods), dict(pc.inventory)
    raw = [{"op": "give", "actor": "pc", "params": {"item": "bundle of herbs", "to": "pc"}}]
    ask = _asker(scenery.ALREADY, given="1")
    rows = scenery.ground(raw, e, [PAGE], ask_fn=ask)
    assert ask.asked[0]["given"] == [
        "the herbs the grioth held: 18× Monkshood, 18× Caranator, 12× Coldwood"]
    assert rows == [{"kind": "scenery", "thing": "bundle of herbs",
                     "answer": scenery.ALREADY, "already": "the herbs the grioth held"}]
    assert s.prop_named("bundle of herbs") is None, "not ledgered as scenery"
    out = _take(e, "bundle of herbs").outcomes[0]
    assert out.status == "resolved" and out.effects[0]["how"] == "already"
    assert out.tell == ("The bundle of herbs is the herbs the grioth held, already in "
                        f"{pc.name}'s pack: 18× Monkshood, 18× Caranator, 12× Coldwood. "
                        "Nothing more is picked up.")
    assert pc.goods == goods_before and "bundle of herbs" not in pc.goods
    assert pc.inventory == satchel_before
    # Asked once: the name is tied to the grant now, so the next turn does not ask again.
    assert not e.unrecorded_thing("the bundle of herbs", pc)


def test_a_herb_since_spent_is_not_claimed_in_the_pack(wood):
    """What the grant says is read off the satchel when it is said: the record keeps ids,
    never counts to spend from (law 2)."""
    s, e = wood
    _guard_leaves(s, e)
    pc = s.pc()
    pc.inventory["coldwood"] = 0
    grant = e.granted_here(pc)[0]
    assert e.granted_line(pc, grant) == "18× Monkshood, 18× Caranator"
    for iid in HERBS:
        pc.inventory[iid] = 0
    e.known_as(grant, "bundle of herbs")
    out = _take(e, "bundle of herbs").outcomes[0]
    assert "used up now" in out.tell and "bundle of herbs" not in pc.goods


def test_the_reader_is_offered_already_only_when_something_was_given():
    """A reader shown no grant cannot answer that the thing is one: the answer is not in
    the call's grammar (an enum, which Ollama enforces), and a model answer of it anyway
    is read as no answer."""
    plain = scenery.schema_for(())
    assert scenery.ALREADY not in plain["properties"]["answer"]["enum"]
    assert "given" not in plain["properties"]
    one = scenery.schema_for(("the herbs: 2× Bitterroot",))
    assert scenery.ALREADY in one["properties"]["answer"]["enum"]
    assert one["properties"]["given"]["enum"] == ["", "1"] and "given" in one["required"]
    msgs = scenery.messages("the wood", PAGE, "bundle of herbs",
                            ("the herbs the grioth held: 18× Monkshood",))
    assert "(1) the herbs the grioth held: 18× Monkshood" in msgs[-1]["content"]
    assert "Given to the player here" not in scenery.messages("the wood", PAGE, "x")[-1][
        "content"]


def test_an_already_answer_naming_no_grant_it_was_shown_ledgers_nothing():
    """Code checks the number: one grant needs none, and a number naming nothing shown is
    no answer — so nothing is ledgered and nothing minted, and the engine's refusal stands."""
    two = ("the herbs the grioth held: 18× Monkshood", "the herbs Kesst gathered: 4× Sukake")
    got = scenery.decide("the wood", (), [PAGE], "bundle of herbs",
                         ask_fn=_asker(scenery.ALREADY, given="7"), given=two)
    assert got["given"] is None and not got["ledger"] and got["answer"] == "unread"
    got = scenery.decide("the wood", (), [PAGE], "bundle of herbs",
                         ask_fn=_asker(scenery.ALREADY, given=""), given=two[:1])
    assert got["given"] == 0
    got = scenery.decide("the wood", (), [PAGE], "bundle of herbs",
                         ask_fn=_asker(scenery.ALREADY, given="2"), given=two)
    assert got["given"] == 1


def test_a_thing_beside_the_grant_is_still_scenery(wood):
    """Given things listed, a different thing on the same page is still ledgered as the
    page showed it: the grant does not swallow everything near it."""
    s, e = wood
    _guard_leaves(s, e)
    page = PAGE + " A broken branch lies across the path."
    raw = [{"op": "give", "actor": "pc", "params": {"item": "broken branch", "to": "pc"}}]
    rows = scenery.ground(raw, e, [page], ask_fn=_asker(
        scenery.SHOWN, "A broken branch lies across the path", ""))
    assert rows[0]["ledgered"] and "already" not in rows[0]
    assert _take(e, "broken branch").outcomes[0].status == "resolved"
    assert s.pc().goods.get("broken branch") == 1


def test_grants_are_told_only_for_this_place_since_the_party_came(wood):
    """"Recently or this scene": a grant made somewhere else, or before the party last
    arrived here, is not offered as what the page here is describing."""
    s, e = wood
    pc = s.pc()
    s.arrived = s.clock_minutes
    e._mark_granted(pc, "the herbs Kesst gathered", {"bitterroot": 2}, {"bitterroot": "Bitterroot"})
    pc.carry("bitterroot", 2)
    assert [g["name"] for g in e.granted_here(pc)] == ["the herbs Kesst gathered"]
    s.clock_minutes += 60
    s.arrived = s.clock_minutes
    assert e.granted_here(pc) == [], "the party came back since: an old grant is not this scene's"


def test_a_second_hour_of_the_same_gathering_adds_to_one_record(wood):
    """One record per label: a day's foraging is not one record an hour."""
    s, e = wood
    pc = s.pc()
    for _ in range(3):
        e._mark_granted(pc, "the herbs Kesst gathered", {"bitterroot": 2})
    recs = [r for r in s.props if r.get("kind") == "granted"]
    assert len(recs) == 1 and recs[0]["granted"]["ids"] == {"bitterroot": 6}
    for n in range(Engine.GRANTS_KEPT + 3):
        e._mark_granted(pc, f"the find number {n}", {"bitterroot": 1})
    assert len([r for r in s.props if r.get("kind") == "granted"]) == Engine.GRANTS_KEPT


def test_a_narrated_sprig_of_a_known_herb_is_one_herb_not_the_plans_count(wood):
    """(b) A ledgered narrated thing that names a catalogue herb resolves to that herb in
    the satchel (`ingredients.by_name`), never a dataless goods line — and it is ONE thing,
    as every props record is: "I take the 18 monkshood" off a page that showed a sprig
    minted all eighteen through the plan's count (law 3: no model authors a number)."""
    s, e = wood
    pc = s.pc()
    rec = s.place_prop("sprig of monkshood", state="intact")
    rec["origin"] = "narrated"
    before = pc.inventory.get("monkshood", 0)
    out = _take(e, "sprig of monkshood", count=18).outcomes[0]
    assert out.status == "resolved"
    assert pc.inventory.get("monkshood", 0) == before + 1
    assert "sprig of monkshood" not in pc.goods


def test_herbs_already_carried_and_nothing_lying_here_say_so(wood):
    """"I take the monkshood" with six in the satchel and none on the ledger: answered as
    the payment is ("already carries"), nothing minted. It was "There is no monkshood here
    … nothing has put one here", which reads as though the six were gone."""
    s, e = wood
    pc = s.pc()
    pc.carry("monkshood", 6)
    out = _take(e, "monkshood").outcomes[0]
    assert out.status == "resolved" and out.effects[0]["how"] == "already"
    assert f"{pc.name} already carries 6× Monkshood" in out.tell
    assert pc.inventory["monkshood"] == 6


def test_a_documents_give_of_a_granted_name_still_gives(wood):
    """A cheat's or a test's give (origin stamped) is the document's word: the already-door
    answers only a player's own pick-up."""
    s, e = wood
    _guard_leaves(s, e)
    pc = s.pc()
    e.known_as(e.granted_here(pc)[0], "bundle of herbs")
    e.run(e.validate([{"op": "give", "params": {"item": "monkshood", "to": "pc"}}],
                     origin="author:test"))
    assert pc.inventory["monkshood"] == 19


def test_the_planned_slot_is_told_the_act_not_a_possession(wood):
    """(c) Why the slot wrote the herbs on the ground: its whole instruction was the tell,
    and "is yours now" carries no act and no place, so the model gave the possession a
    scene ("you find a bundle … left behind in its wake"). The slot now carries the act
    and where the herbs went, word for word from the engine."""
    from rules.engine import Outcome

    s, e = wood
    line = _guard_leaves(s, e)
    outs = [Outcome(intent_id="i1", op="move", tell="Kesst moves to near (40 ft)."),
            Outcome(intent_id="", op="stance",
                    tell="The grioth gives way as you close and leaves the thicket to you."),
            Outcome(intent_id="", op="stance", tell=line)]
    slots = planned.build_plan(e, "Approach the Grioth", outs)
    said = " ".join(sl["say"] for sl in slots if sl["key"].startswith("fact"))
    assert "puts it all in the pack" in said and "yours now" not in said

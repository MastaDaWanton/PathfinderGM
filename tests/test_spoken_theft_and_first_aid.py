"""A spoken theft, an item named with an extra word, and spoken first aid.

Measured 2026-10-08 by the deeds lane, with the local model, in the released game (0.2.11),
and reproduced on this branch with the live reader and planner before any fix:

1. "I take an apple from the fruit seller without paying" — the act→op table built
   `give item=apple from_=c1 to=pc`, the engine read every `from_` as a hand-over, and the
   tell said "the fruit seller hands Kesst Vayr apple". Nothing was marked stolen.
2. "I take another apple from the fruit seller and walk off" — `item="another apple"` was
   not `same` as the seller's "apple" line, so the seller kept all twenty and an apple came
   out of nothing; "walk off" was read `leave` with no place, which owed a travel with
   only the roads out of town to choose from, and Kesst walked to the road to Scrapden.
   "one of the apples" did the same as "another apple".
3. "I give first aid to the wounded porter" — the deeds lane's plans were
   `check skill=heal` with no target 3 times of 3 (no patient found, the porter bled on);
   this branch's repro got `use_item medical_kit_01`, `check sense motive` and
   `use_item bandage_1` for three phrasings. "I use the Heal skill on the porter" was
   refused by the means gate: "Kesst Vayr has no spell, ability or item by that name".

Every test drives the real engine and names the measurement it guards. The two targeted
questions (`interpret.confirm_take`, `interpret.confirm_first_aid`) are measured live, not
here: 16 of 16 and 12 of 12 on lines written apart from their demonstrations (gemma-4-12B,
2026-10-08); in the suite they are stood in by the function the test hands the table.
"""
from __future__ import annotations

import pytest

from gm import acts_to_ops, interpret, means
from rules import firstaid, holding
from rules.activeeffect import ActiveEffect
from rules import states
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc
from tests._places import stand_on

AB = {k: 10 for k in ("str", "dex", "con", "int", "wis", "cha")}


@pytest.fixture(autouse=True)
def _no_readings(monkeypatch):
    monkeypatch.setattr(interpret, "_READINGS", {})


def _person(s, ref, name, hp=9, **extra):
    d = {"name": name, "kind": "npc", "hp": hp, "hp_max": max(hp, 9), "abilities": dict(AB)}
    d.update(extra)
    who = s.add(from_dict(d, ref=ref))
    who.at = s.at
    return who


def _street(*, dying=0):
    s = Scene(location_id="5bbd0c40345f")
    stand_on(s, "urban")
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    pc.at = s.at
    _person(s, "c1", "the fruit seller", goods={"apple": 20, "pear": 6})
    for n in range(dying):
        hurt = _person(s, f"c{2 + n}", ("the wounded porter", "the carter")[n], hp=-2)
        hurt.apply_hp_state()
        assert firstaid.dying(hurt)
    return s, pc, Engine(s, Dice(seed=7))


def _run(e, raw, face=15):
    res = e.run(e.validate(raw))
    for _ in range(10):
        if not res.awaiting:
            break
        res = e.resume(face=face)
    assert not res.awaiting
    return res.outcomes


def _take(item, **extra):
    """The give the act→op table builds for "I take <item> from the fruit seller"."""
    return {"op": "give", "actor": "pc", "because": "the player took it",
            "params": {"item": item, "to": "pc", "from_": "c1", **extra}}


# --- 1. a take from a person is a take -----------------------------------------------------

def test_a_take_from_the_seller_is_a_theft_not_a_gift():
    """Measured: "I take an apple from the fruit seller without paying" was planned
    `give item=apple from_=c1 to=pc` and told as "the fruit seller hands Kesst Vayr apple",
    with nothing marked stolen. The player acting is the taker; the seller did not hand it
    over, so it is still hers, and the props ledger says so."""
    s, pc, e = _street()
    out = _run(e, [_take("apple")])[0]
    assert "hands" not in out.tell
    assert "takes the apple from the fruit seller, who did not hand it over" in out.tell
    eff = out.effects[0]
    assert eff["how"] == "took_from" and eff["to"] == pc.ref and eff["from"] == "c1"
    assert s.people["c1"].goods["apple"] == 19 and pc.goods["apple"] == 1
    rec = s.prop_named("apple")
    assert rec["owner"] == "c1" and rec["stolen"] is True and rec["held_by"] == pc.ref


def test_a_hand_over_by_the_holder_is_still_a_hand_over():
    """The other reading of the same give: the holder acting is the giver (Inform's giving
    action), which is how `confirm_takes` writes a thing the player was OFFERED. Nothing is
    stolen; the 2026-10-03 rule that the actor of a give is the one handing it over
    stands."""
    s, pc, e = _street()
    out = _run(e, [{"op": "give", "actor": "c1", "because": "she holds one out",
                    "params": {"item": "apple", "to": "pc", "from_": "c1"}}])[0]
    assert out.tell.startswith("the fruit seller hands Kesst Vayr")
    assert out.effects[0]["how"] == "handed"
    assert not (s.prop_named("apple") or {}).get("stolen")


def test_a_price_is_consent_and_a_companion_s_pack_is_the_party_s():
    """A price paid makes it a sale (docs/items-have-owners.md: "a price is consent"), and
    somebody travelling with the player hands over what is asked — neither is a theft."""
    s, pc, e = _street()
    pc.purse = {"cp": 50}
    out = _run(e, [_take("apple", price="1 cp")])[0]
    assert out.effects[0]["how"] == "handed"
    friend = _person(s, "c9", "Drenn", goods={"rope": 1})
    friend.apply_effect(ActiveEffect(
        name="travels with you", kind="bond", key="company:c9:travels",
        source="company:c9", origin="company:c9", duration="until-dismissed",
        tags=(states.TRAVELS_WITH_YOU,)))
    out = _run(e, [{"op": "give", "actor": "pc", "because": "x",
                    "params": {"item": "rope", "to": "pc", "from_": "c9"}}])[0]
    assert out.effects[0]["how"] == "handed"
    assert not (s.prop_named("rope") or {}).get("stolen")


def test_the_dead_hand_nothing_over_and_own_nothing():
    """A `from_` naming a corpse read as "the dead thug hands Kesst Vayr a sap". Taken from
    a body it is the loot op's rule — no owner kept, nothing stolen — and said as a body."""
    s, pc, e = _street()
    body = _person(s, "c5", "the dead thug", goods={"sap": 1})
    body.die("a blow")
    out = _run(e, [{"op": "give", "actor": "pc", "because": "x",
                    "params": {"item": "sap", "to": "pc", "from_": "c5"}}])[0]
    assert out.tell == "Kesst Vayr takes the sap from the dead thug's body."
    assert not (s.prop_named("sap") or {}).get("stolen")


# --- 2. what the holder actually carries ---------------------------------------------------

@pytest.mark.parametrize("said", ["another apple", "one of the apples", "a ripe apple"])
def test_an_extra_word_still_takes_the_seller_s_own_apple(said):
    """Measured: "another apple" and "one of the apples" did not match the seller's "apple"
    line; she kept all twenty and the apple was minted. The holder's own list is matched
    against the words (`holding.named_among`), never the other way round."""
    s, pc, e = _street()
    out = _run(e, [_take(said)])[0]
    assert s.people["c1"].goods["apple"] == 19
    assert pc.goods == {**pc.goods, "apple": 1} and said not in pc.goods
    assert "takes the apple from the fruit seller" in out.tell
    assert s.prop_named("apple")["stolen"] is True


def test_a_thing_the_holder_does_not_carry_is_refused_not_minted():
    """A take from a person never comes out of the air: "a melon" from a seller with only
    apples and pears is refused, and no melon appears in anybody's pack. Before, the
    open-pockets rule minted it."""
    s, pc, e = _street()
    out = _run(e, [_take("melon")])[0]
    assert out.status == "refused"
    assert "the fruit seller has no melon" in out.tell
    assert "melon" not in pc.goods and s.people["c1"].goods == {"apple": 20, "pear": 6}


def test_a_take_with_nobody_named_finds_the_holder_by_the_same_words():
    """The holder search (no `from_`) asks the same question of everybody here: "another
    apple" with nobody named is the seller's apple, taken from her."""
    s, pc, e = _street()
    out = _run(e, [{"op": "give", "actor": "pc", "because": "x",
                    "params": {"item": "another apple", "to": "pc"}}])[0]
    assert s.people["c1"].goods["apple"] == 19
    assert out.effects[0]["how"] == "took_from"


def test_a_second_take_with_no_holder_named_comes_from_the_same_hands():
    """Live on this branch: "I take one of the pears from the fruit seller, then a melon"
    read the melon with no target; nobody here carried one and the world-never-runs-out
    rule minted it — "Kesst Vayr takes the melon". The second take comes out of the hands
    the first named (the frame's own structure), so the melon is refused: she has none."""
    s, pc, e = _street()
    frame = _frame({"act": "take", "object": "one of the pears",
                    "target": "the fruit seller", "span": "take one of the pears"},
                   {"act": "take", "object": "a melon", "span": "then a melon"})
    rows = acts_to_ops.table(frame, s, sentence="x")
    assert [r.intents[0]["params"].get("from_") for r in rows] == ["c1", "c1"]
    outs = _run(e, [r.intents[0] for r in rows])
    assert s.people["c1"].goods["pear"] == 5 and pc.goods.get("pear") == 1
    assert outs[1].status == "refused" and "melon" not in pc.goods


def test_a_take_off_that_names_nothing_takes_nothing_off():
    """Live on this branch, the same line: the planner wrote two `take_off` ops with no
    item beside the takes, and the empty item was read as the armour — Kesst's leather came
    off in the market, armour class 15 to 13. Nothing named is nothing taken off."""
    s, pc, e = _street()
    worn, ac = pc.armour, pc.ac()
    assert worn and worn != "none"
    out = _run(e, [{"op": "take_off", "actor": "pc", "because": "x", "params": {}}])[0]
    assert out.status == "refused" and "Name what Kesst Vayr takes off" in out.tell
    assert pc.armour == worn and pc.ac() == ac


def test_named_among_reads_the_list_not_the_words():
    """The vocabulary is the holder's: the longest of their names standing whole in the
    words, plural forgiven; a name that is only part of a word does not count."""
    store = {"apple": 3, "red apple": 1, "pear": 2}
    assert holding.named_among(store, "another red apple") == "red apple"
    assert holding.named_among(store, "one of the apples") == "apple"
    assert holding.named_among(store, "a pineapple") is None
    assert holding.named_among(store, "a melon") is None


# --- the table: a steal, and a take that was offered ---------------------------------------

def _frame(*actions):
    return {"question": False, "claims": [], "actions": [dict(a) for a in actions]}


def test_a_spoken_steal_is_built_as_a_take_out_of_a_fight_and_left_to_the_manoeuvre_in_one():
    """The reader's `steal` act ("pick a pocket, steal, filch") built nothing, so a theft
    in words was whatever the planner guessed. Out of a fight it is the take's give; in a
    fight it is the combat manoeuvre the fight's plan writes."""
    s, pc, e = _street()
    frame = _frame({"act": "steal", "object": "a pear", "target": "the fruit seller",
                    "span": "steal a pear from the fruit seller"})
    rows = acts_to_ops.table(frame, s, sentence="I steal a pear from the fruit seller")
    assert rows[0].intents == [{"op": "give", "actor": "pc", "because": "the player took it",
                                "params": {"item": "pear", "to": "pc", "from_": "c1"}}]
    _run(e, rows[0].intents)
    assert s.people["c1"].goods["pear"] == 5 and s.prop_named("pear")["stolen"] is True
    s.initiative, s.turn = [("pc", 20), ("c1", 5)], 0
    assert s.in_encounter
    rows = acts_to_ops.table(frame, s, sentence="I steal a pear from the fruit seller")
    assert not rows[0].intents and "manoeuvre" in rows[0].note


def test_a_take_the_holder_offered_is_handed_over():
    """`confirm_takes` asks, with the last beat, whether the holder offered it. "offered"
    makes the holder the one acting — a hand-over; "taken" (or no answer) leaves the player
    acting — a take. Without the question "I take the purse he holds out" would be filed as
    a theft by this branch's engine rule. A steal is never asked."""
    s, pc, e = _street()
    frame = _frame({"act": "take", "object": "the pear", "target": "her",
                    "span": "take the pear from her"})
    asked = []

    def offered(beat, span):
        asked.append((beat, span))
        return "offered"

    rows = acts_to_ops.table(frame, s, sentence="I take the pear from her")
    rows[0].intents[0]["params"]["from_"] = "c1"     # "her": the one here
    handed = acts_to_ops.confirm_takes(rows, frame, s, recent=["She holds out a pear."],
                                       ask=offered)
    assert asked == [("She holds out a pear.", "take the pear from her")]
    assert handed and rows[0].intents[0]["actor"] == "c1"
    out = _run(e, rows[0].intents)[0]
    assert out.effects[0]["how"] == "handed"

    rows = acts_to_ops.table(_frame({"act": "take", "object": "an apple",
                                     "target": "the fruit seller", "span": "take an apple"}),
                             s, sentence="I take an apple from the fruit seller")
    assert not acts_to_ops.confirm_takes(rows, frame, s, ask=lambda b, x: "taken")
    assert rows[0].intents[0]["actor"] == "pc"
    steal = _frame({"act": "steal", "object": "a pear", "target": "the fruit seller"})
    rows = acts_to_ops.table(steal, s, sentence="I steal a pear")
    acts_to_ops.confirm_takes(rows, steal, s, ask=lambda b, x: pytest.fail("asked"))
    assert rows[0].intents[0]["actor"] == "pc"


def test_walking_off_under_the_open_sky_owes_no_road_out_of_town():
    """Measured: "…and walk off" read `leave` with no place; the street is under the sky, so
    `_leaving` answered "settlement", a travel was owed with only the roads out to choose
    from, and Kesst left Vormoor for the road to Scrapden over an apple. A bare leave
    outdoors names nothing to leave; "leave town" still leaves the settlement, and a bare
    leave under a roof still leaves the building."""
    s, pc, e = _street()
    places = e.places()
    bare = {"act": "leave", "span": "walk off"}
    assert interpret._leaving(bare, s, places) == ""
    assert "travel" not in interpret.ops_for(_frame(bare), s, places)
    town = {"act": "leave", "place": "town", "span": "leave town"}
    assert interpret._leaving(town, s, places) == "settlement"
    assert "travel" in interpret.ops_for(_frame(town), s, places)
    hall = next(p for p in places if p.name == "the guildhall")
    s.at = pc.at = hall.id
    assert interpret._leaving(bare, s, places) == "building"


# --- 3. first aid ----------------------------------------------------------------------------

def test_a_heal_check_with_no_target_tends_the_one_who_is_dying():
    """Measured: `check skill=heal` with no target, 3 plans of 3 — `firstaid.patient_of`
    found no patient, the check rolled against the plan's DC, and the porter bled on. The
    engine's own state names the patient when exactly one creature here is dying."""
    s, pc, e = _street(dying=1)
    out = _run(e, [{"op": "check", "actor": "pc", "because": "first aid",
                    "params": {"skill": "heal", "dc": {"band": "easy"}}}], face=19)[0]
    assert out.dc["value"] == firstaid.DC
    porter = s.people["c2"]
    assert porter.has_state("state.down.stable") and not firstaid.dying(porter)


def test_two_dying_and_none_named_is_not_the_engine_s_choice():
    """With two dying and no target, choosing one would be the engine deciding for the
    player; the check stays an ordinary Heal check and nobody is stabilised by it."""
    s, pc, e = _street(dying=2)
    _run(e, [{"op": "check", "actor": "pc", "because": "first aid",
              "params": {"skill": "heal", "dc": {"band": "easy"}}}], face=19)
    assert all(firstaid.dying(s.people[r]) for r in ("c2", "c3"))


def test_the_heal_skill_named_is_held_not_an_unknown_power():
    """Measured: "I use the Heal skill on the porter" was read `means: power, power: Heal`
    and refused — "Kesst Vayr has no spell, ability or item by that name … has no powers
    yet". Heal is a skill every character may try (the Core Rulebook's untrained use; the
    check itself refuses a trained-only skill with the reason). Fly is not given away: the
    Fly skill is for a creature that already flies."""
    s, pc, e = _street(dying=1)
    heal = {"act": "use", "object": "Heal", "target": "the porter", "means": "power",
            "power": "Heal", "span": "use the Heal skill on the porter"}
    judged = means.judge(_frame(heal), s)
    assert judged and judged[0].get("held") == ["skill", "heal"]
    assert not means.overreach(_frame(heal), s)
    assert means.backed_ops(judged) == ["check"]
    assert means.held_power(s, "the Heal skill") == ("skill", "heal")
    fly = {"act": "go", "place": "the wall", "means": "power", "power": "fly",
           "span": "fly over the city wall"}
    assert means.overreach(_frame(fly), s)


def test_first_aid_in_words_is_built_whole_with_the_patient():
    """The table builds the Heal check the rule stabilises with, the dying person as its
    target, and the plan's own Heal check (no target) is replaced by it. Named as the skill
    it needs no question; "give first aid" is asked (`interpret.confirm_first_aid`), and a
    deed the question calls something else, or one aimed at somebody not dying, builds
    nothing."""
    s, pc, e = _street(dying=1)
    named = _frame({"act": "use", "object": "Heal", "target": "the porter",
                    "means": "power", "power": "Heal",
                    "span": "use the Heal skill on the porter"})
    rows = acts_to_ops.table(named, s, sentence="I use the Heal skill on the porter")
    assert acts_to_ops.first_aid(rows, named, s) == ["first aid to the wounded porter"]
    assert rows[0].intents == [{"op": "check", "actor": "pc", "target": "c2",
                                "params": {"skill": "heal", "dc": {"band": "average"}},
                                "because": "the player gave first aid"}]
    plan = [{"op": "check", "actor": "pc", "params": {"skill": "heal", "dc": "average"}}]
    raw = acts_to_ops.apply(plan, rows, named, s)
    assert [r for r in raw if r.get("op") == "check"] == rows[0].intents
    _run(e, raw, face=19)
    assert s.people["c2"].has_state("state.down.stable")

    said = _frame({"act": "other", "object": "first aid", "target": "the wounded porter",
                   "span": "give first aid to the wounded porter"})
    rows = acts_to_ops.table(said, s, sentence="I give first aid to the wounded porter")
    assert not acts_to_ops.first_aid(rows, said, s)               # no reader, no guess
    s2, _pc, _e = _street(dying=1)
    rows = acts_to_ops.table(said, s2, sentence="x")
    assert acts_to_ops.first_aid(rows, said, s2, ask=lambda span, who: "first aid")
    assert rows[0].intents[0]["target"] == "c2"
    rows = acts_to_ops.table(said, s2, sentence="x")
    assert not acts_to_ops.first_aid(rows, said, s2, ask=lambda span, who: "something else")
    calm = _frame({"act": "other", "object": "first aid", "target": "the fruit seller",
                   "span": "give first aid to the fruit seller"})
    rows = acts_to_ops.table(calm, s2, sentence="x")
    assert not acts_to_ops.first_aid(rows, calm, s2, ask=lambda span, who: "first aid")


def test_a_wound_bandaged_is_the_dying_person_s_first_aid():
    """Live on this branch: "I kneel beside the porter and bandage his wound to stop the
    bleeding" read the bandaging with `target: his wound` — no person — so nothing was
    built, the plan was `narrate_only`, and the page wrote "you have stopped the bleeding"
    over an engine that had done nothing. Aimed at no person, the deed is put to the
    question about the one creature here who is dying; with two dying it is not."""
    s, pc, e = _street(dying=1)
    frame = _frame({"act": "other", "target": "the porter", "span": "kneel beside the porter"},
                   {"act": "use", "object": "bandage", "target": "his wound",
                    "span": "bandage his wound to stop the bleeding"})
    rows = acts_to_ops.table(frame, s, sentence="x")
    asked = []

    def ask(span, who):
        asked.append(span)
        return "first aid" if "bandage" in span else "something else"

    assert acts_to_ops.first_aid(rows, frame, s, ask=ask) == ["first aid to the wounded porter"]
    assert rows[1].intents[0]["target"] == "c2" and not rows[0].intents
    s2, _pc, _e = _street(dying=2)
    rows = acts_to_ops.table(frame, s2, sentence="x")
    acts_to_ops.first_aid(rows, frame, s2, ask=ask)
    assert not rows[1].intents


def test_one_first_aid_per_patient_a_turn():
    """Live: "I kneel by the porter and try to stabilise him" was two actions aimed at him
    (`other`, then `other` tried). One Heal check, not two."""
    s, pc, e = _street(dying=1)
    frame = _frame({"act": "other", "target": "the porter", "span": "kneel by the porter"},
                   {"act": "other", "commit": "tried", "target": "the porter",
                    "span": "try to stabilise him"})
    rows = acts_to_ops.table(frame, s, sentence="x")
    assert len(acts_to_ops.first_aid(rows, frame, s, ask=lambda span, who: "first aid")) == 1

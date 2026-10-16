"""Asking for something is a roll, what it pays is the engine's, and nothing else pays.

Measured 2026-10-16 on a real player's game (0.2.19, the free narrator), turn-log rows
11-19: after helping a carter, the player asked where to stay and then asked "for fair
compensation for helping". The reader gave two `talk` acts; the engine resolved a `say`
and nothing was rolled. The narrator, with no answer to the request, wrote one: the carter
pulled "a small, weathered coin" out of a pouch and handed it over. The read-back DID read
that hand-over (`changed_hands: something else, c1 -> pc`) and skipped it, because the
thing was not one the engine had a name for. Next turn, "I take the coin" was planned
`give item=coin to=pc` from nobody, and the engine counted "a single copper piece, all
anybody counted out" into the purse: the world minted the prose's coin. The owner: she
"should have rolled diplomacy when speaking about payment".

The rules (rules/requests.py has the full text): Core Rulebook p.93, Diplomacy, Make
Request — at least indifferent, the attitude's DC plus Charisma, "give simple aid" +0,
"additional requests +5 per request", "if a request is refused, the result does not
change with additional checks". Core Rulebook p.159, Hireling, untrained: 1 sp per day.

Synthetic scenes and paraphrased lines only; nothing of the player's save is used.
"""
from __future__ import annotations

from gm import acts_to_ops, beat_verify as bv, interpret
from rules import attitude, goods, requests
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict

from test_a_take_is_not_a_boast import SAM


def _scene(cha_mod_ability: int = 10):
    """The player and one carter, a labourer with a purse in her kit (thug template:
    `kit.cutpurse`, 2d4 sp), at a known Charisma so the book's DC is arithmetic."""
    s = Scene(location_id="5bbd0c40345f")
    s.add(from_dict(dict(SAM), ref="pc"))
    carter = instantiate("thug", scene=s, name="the carter")
    carter.abilities["cha"] = cha_mod_ability
    s.add(carter)
    return s, carter


def _asked(scene, frame, plan=None):
    rows = acts_to_ops.table(frame, scene, sentence="")
    return rows, acts_to_ops.apply(list(plan or [{"op": "narrate_only", "because": "t"}]),
                                   rows, frame, scene)


PAY_ME = {"question": False, "claims": [], "actions": [
    {"act": "talk", "target": "them", "says": "where to stay"},
    {"act": "request", "object": "fair pay for the help", "asks_for": "payment"}]}


def _purse_cp(actor) -> int:
    return goods.in_copper(actor.purse)


def test_a_request_for_payment_rolls_diplomacy_at_the_attitude_dc():
    """0 of 8 asking-for-pay lines rolled anything before (a `talk` owes a `say`). The
    request is the player's own Diplomacy roll, suspended for the popup, against the
    book's DC: indifferent 15 + Cha +0 + simple aid +0 = 15 — never a band the plan
    chose."""
    s, carter = _scene()
    rows, plan = _asked(s, PAY_ME)
    built = [r for r in plan if r.get("op") == "check"]
    assert built == [{"op": "check", "actor": "pc", "target": carter.ref,
                      "params": {"skill": "diplomacy", "request": "payment"},
                      "because": "the player asks the carter for payment"}]
    e = Engine(s, Dice(seed=1))
    e.run(e.validate(plan))
    assert s.awaiting and s.awaiting["label"] == "Diplomacy check"
    assert s.awaiting["dc"] == attitude.INFLUENCE_DC["indifferent"] == 15


def test_a_granted_request_pays_a_labourers_day_wage_out_of_their_purse():
    """Success pays one untrained hireling's day (CRB p.159, 1 sp = 10 cp), moved from
    the carter's real purse into the player's by the engine, with a record the read-back
    can see (`from` c1, `to` pc). Before, the only coin of the exchange was the prose's."""
    s, carter = _scene()
    _rows, plan = _asked(s, PAY_ME)
    e = Engine(s, Dice(seed=1))
    e.run(e.validate(plan))
    pc_before = _purse_cp(s.pc())
    res = e.resume(20)
    paid = [x for o in res.outcomes for x in (o.effects or [])
            if x.get("kind") == "give" and x.get("item") == "coin"]
    assert paid and paid[0]["from"] == carter.ref and paid[0]["to"] == "pc"
    assert _purse_cp(s.pc()) - pc_before == requests.wage_cp() == 10
    tell = " ".join(o.tell for o in res.outcomes)
    assert "the carter pays" in tell and "labourer's day wage" in tell, tell
    # Asked again the same day: paid already, nothing rolled, nothing moves.
    e.run(e.validate(plan))
    assert not s.awaiting
    assert _purse_cp(s.pc()) - pc_before == 10


def test_a_refused_request_pays_nothing_and_stays_refused():
    """Failure moves no coin and says so in plain words; the same request again that day
    is refused unrolled ("the result does not change with additional checks", CRB p.93)."""
    s, carter = _scene()
    _rows, plan = _asked(s, PAY_ME)
    e = Engine(s, Dice(seed=1))
    e.run(e.validate(plan))
    pc_before, carter_before = _purse_cp(s.pc()), _purse_cp(carter)
    res = e.resume(1)
    tell = " ".join(o.tell for o in res.outcomes)
    assert "says no and pays nothing: nothing changes hands" in tell, tell
    assert _purse_cp(s.pc()) == pc_before and _purse_cp(carter) == carter_before
    res = e.run(e.validate(plan))
    assert not s.awaiting
    assert "already said no to that today" in " ".join(o.tell for o in res.outcomes)


def test_each_further_request_is_five_harder():
    """"Additional requests: +5 per request" — a favour asked after a refused payment is
    rolled against 15 + 5."""
    s, carter = _scene()
    _rows, plan = _asked(s, PAY_ME)
    e = Engine(s, Dice(seed=1))
    e.run(e.validate(plan))
    e.resume(1)
    favour = {"question": False, "claims": [], "actions": [
        {"act": "request", "object": "to hold the gate", "asks_for": "favour"}]}
    _rows, plan2 = _asked(s, favour)
    e.run(e.validate(plan2))
    assert s.awaiting and s.awaiting["dc"] == 20


def test_nobody_worse_than_indifferent_hears_a_request():
    """"If a creature's attitude toward you is at least indifferent, you can make
    requests" — an unfriendly carter is refused without a roll, and nothing moves."""
    s, carter = _scene()
    e = Engine(s, Dice(seed=1))
    e.settle_attitude(carter, "unfriendly", None, "t")
    _rows, plan = _asked(s, PAY_ME)
    res = e.run(e.validate(plan))
    assert not s.awaiting
    assert "will do you no favours" in " ".join(o.tell for o in res.outcomes)


def test_a_carter_with_an_empty_purse_pays_nothing_and_says_so():
    """The pay comes from what the person carries: none on them, none paid — never a
    coin out of the air."""
    s, carter = _scene()
    carter.kit_pending = {}
    carter.purse = {}
    _rows, plan = _asked(s, PAY_ME)
    e = Engine(s, Dice(seed=1))
    e.run(e.validate(plan))
    before = _purse_cp(s.pc())
    res = e.resume(20)
    assert _purse_cp(s.pc()) == before
    assert "carries no coin to pay with" in " ".join(o.tell for o in res.outcomes)


def test_a_plain_question_rolls_nothing():
    """Asking where to stay is talk, a `say` the plan writes — no check is built. And a
    request whose `asks_for` is outside the closed list (a hosted provider does not hold
    the schema) is demoted to talk in `ground`, never rolled on a guess."""
    s, _carter = _scene()
    frame = {"question": False, "claims": [], "actions": [
        {"act": "talk", "target": "the carter", "says": "where I should stay"}]}
    rows, plan = _asked(s, frame)
    assert not any(r.get("op") == "check" for r in plan)
    assert rows[0].ops == ["say"]
    line = "I ask the carter for help"
    grounded, dropped = interpret.ground({"actions": [
        {"act": "request", "span": line[2:], "target": "the carter", "object": "help",
         "asks_for": "a horse"}]}, line)
    assert grounded["actions"][0]["act"] == "talk"
    assert grounded["actions"][0]["says"] == "help"
    assert "request.asks_for='a horse'" in dropped


def test_the_reader_schema_holds_what_is_asked_for_to_the_closed_list():
    """The per-act alternative for `request` carries `asks_for` as an enum the sampler
    enforces (enums held 6/6 on this stack: memory `ollama-schema-enforcement`)."""
    alts = interpret.per_act_schema()["properties"]["actions"]["items"]["anyOf"]
    req = next(a for a in alts if a["properties"]["act"] == {"const": "request"})
    assert req["properties"]["asks_for"] == {"type": "string",
                                             "enum": list(requests.KINDS)}
    assert "asks_for" in req["required"]
    assert tuple(interpret.REQUESTS) == requests.KINDS


def test_the_built_request_survives_the_plan_doors_to_validation():
    """Measured live 2026-10-16 on this branch: the built `check diplomacy target=c5`
    went through `aim_the_sway` (which drops a social check's band) and then
    `fill_bare_checks`, which put `dc: average` straight back — and validation refused
    it five plans running ("the DC for diplomacy on a named person is the engine's"), the
    turn degraded to narration, and the narration handed over a pouch. The band filler
    leaves a targeted Diplomacy or Intimidate check alone, as validation requires."""
    from gm import judgement

    s, carter = _scene()
    _rows, plan = _asked(s, PAY_ME)
    raw = judgement.aim_the_sway(plan, "I ask her for fair pay for the help", s)
    raw = judgement.fill_bare_checks(raw)
    check = next(r for r in raw if r.get("op") == "check")
    assert "dc" not in check["params"]
    e = Engine(s, Dice(seed=1))
    e.run(e.validate(raw))
    assert s.awaiting and s.awaiting["label"] == "Diplomacy check"
    # And an untargeted check still gets its band (the 60-turn audit's climb lines).
    assert judgement.fill_bare_checks([{"op": "check", "params": {"skill": "climb"}}])[0][
        "params"]["dc"] == {"band": "average"}


# --- the prose cannot hand over what the engine did not give ---------------------------------

def _facts(outcomes=()):
    return bv.Facts(start="the road", end="the road", places=("the road",),
                    people=(bv.Person("pc", "Wren", pc=True), bv.Person("c1", "the carter")),
                    outcomes=tuple(outcomes))


SENTENCE = "The carter digs out a worn coin and hands it over with a grunt."


def _hand_over(item=bv.OTHER_THING, frm="c1"):
    c = bv.Claim("hands", {"item": item, "from": frm, "to": "pc"},
                 "hands it over with a grunt", sentence=SENTENCE, valid=True)
    return c


def test_prose_cannot_hand_the_player_an_unlisted_thing_the_engine_never_gave():
    """The read-back's own claim on the owner's turn was `something else`, c1 -> pc, and
    `diff` skipped every unlisted thing: 0 contradictions for a coin the engine never
    gave. Now a hand-over from a person, on a turn nothing came into the player's hands,
    is a contradiction — asked once more as a question a reader can answer."""
    said = [{"op": "say", "status": "resolved", "effects": [{"kind": "said", "to": "c1"}]}]
    found = bv.diff([_hand_over()], _facts(said), SENTENCE)
    assert [d.category for d in found] == ["hands"]
    assert "Nothing was given to the player" in found[0].fact
    q = bv.question(found[0], _facts(said))
    assert "something else" not in q and "handed over or given to you" in q


def test_a_paid_request_or_a_floor_pickup_is_not_flagged():
    """Precision: the engine's own payment (a check whose record moved coin to the
    player) backs the page's hand-over, and a thing picked up off the floor is the
    world's and is not judged."""
    paid = [{"op": "check", "status": "resolved", "effects": [
        {"kind": "give", "item": "coin", "count": 10, "from": "c1", "to": "pc"}]}]
    assert bv.diff([_hand_over()], _facts(paid), SENTENCE) == []
    assert bv.diff([_hand_over(frm=bv.FLOOR)], _facts(), SENTENCE) == []


def test_the_page_may_count_out_the_coin_a_granted_request_paid():
    """The claims scrubber backs purse words for a check that paid, as it does for a
    sale: the engine's payment is not cut from the page as invented."""
    from rules import intents

    o = {"op": "check", "verdict": "success", "rolls": [], "effects": [
        {"kind": "give", "item": "coin", "count": 10, "from": "c1", "to": "pc"}]}
    plain = {"op": "check", "verdict": "success", "rolls": [], "effects": []}
    assert intents.claims_the_engine_backs([o]) > intents.claims_the_engine_backs([plain])


# --- a take of what nobody holds mints nothing ---------------------------------------------

def test_taking_a_coin_nobody_holds_mints_nothing():
    """The owner's turn 19: "I take the coin" after the prose invented one was planned
    `give item=coin to=pc` from nobody, and the purse gained "a single copper piece, all
    anybody counted out". Now nothing changes hands, and the refusal says so plainly."""
    s, _carter = _scene()
    frame = {"question": False, "claims": [], "actions": [
        {"act": "take", "object": "the coin"}]}
    _rows, plan = _asked(s, frame)
    gives = [r for r in plan if r["op"] == "give"]
    assert [g["params"] for g in gives] == [{"item": "coin", "to": "pc"}]
    before = dict(s.pc().purse)
    e = Engine(s, Dice(seed=1))
    res = e.run(e.validate(gives))
    assert s.pc().purse == before
    assert res.outcomes[0].status == "refused"
    assert "Nobody here is holding any coin out to" in res.outcomes[0].tell


def test_coin_from_a_named_holder_who_counted_none_mints_nothing():
    """The same coin, "offered" by the carter (`confirm_takes` makes the holder the one
    acting): she counted none out, so none moves — ask her for payment instead."""
    s, carter = _scene()
    before = dict(s.pc().purse)
    e = Engine(s, Dice(seed=1))
    res = e.run(e.validate([{"op": "give", "actor": carter.ref,
                             "params": {"item": "coin", "to": "pc"}}]))
    assert s.pc().purse == before
    assert "has counted out no coin" in res.outcomes[0].tell


def test_a_counted_amount_from_nobody_mints_nothing():
    """"5 gp" taken from nobody with no pile of it lying here came "from the world, which
    never runs out" — a number nobody counted (law 3)."""
    s, _carter = _scene()
    before = dict(s.pc().purse)
    e = Engine(s, Dice(seed=1))
    res = e.run(e.validate([{"op": "give", "actor": "pc",
                             "params": {"item": "gp", "count": 5, "to": "pc"}}]))
    assert s.pc().purse == before
    assert res.outcomes[0].status == "refused"


def test_taking_the_coin_a_request_paid_is_that_coin_not_another():
    """After a granted request, "I take the coin" is the payment already in the purse
    (`_mark_payment`), never a second one."""
    s, _carter = _scene()
    _rows, plan = _asked(s, PAY_ME)
    e = Engine(s, Dice(seed=1))
    e.run(e.validate(plan))
    e.resume(20)
    after_pay = _purse_cp(s.pc())
    res = e.run(e.validate([{"op": "give", "actor": "pc",
                             "params": {"item": "coin", "to": "pc"}}]))
    assert _purse_cp(s.pc()) == after_pay
    assert "already in" in res.outcomes[0].tell

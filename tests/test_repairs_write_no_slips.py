"""Our own repairs and backstops, writing slips the narrator never made (2026-11-02).

The lane before this one (docs/narration-faithfulness.md) read the two player reports of
2026-11-01 against their tells: at least 7 of 37 shipped slips were written by our own
repairs, and its bench showed more. Each test below reproduces one, on synthetic scenes,
with what was measured in its docstring (the bench: 17 non-fight lines x 3 on gemma-4-12B,
scratch copies of a report save; nothing of the save is here):

  * the move repair wrote "held in the guardhouse" over "released", beside "is let go";
  * the move check flagged the escort's own "lead you out toward the market";
  * the presence repair made the keepers the tell had "come to the market" already here;
  * the hour repair wrote "the early morning" over a wait "through the night";
  * the no-time-passed backstop fired on the night in the cell, 672 minutes on the clock;
  * the unshown-deed backstop wrote a payment no op made;
  * the trade check cut "accepts the commission for 1 gold, 4 silver" and the fine's
    "accepts your payment", the first rewritten "for 0 gold, 0 silver, and 0 copper";
  * "pay the fine" at the plea became a give to the officer, read as a bribe;
  * "I agree to his price and pay" at the smith made no op at all.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from gm import acts_to_ops
from gm import beat_verify as bv
from gm import narration
from rules import commission, goods, trial
from tests.test_commission import _Face, _blank, _engine, _smith
from tests.test_commission import world  # noqa: F401 — the module's world fixture
from tests.test_trial import _check, _condemned, _run, _taken_for_theft, _tells, _wait


def _facts(outcomes=(), **kw):
    base = dict(start="the guardhouse", end="the guardhouse",
                places=("the guardhouse", "the market"),
                people=(bv.Person("pc", "Pell Arrow", pc=True), bv.Person("c1", "the reeve"),
                        bv.Person("c2", "the stallholder")),
                clock=5 * 1440 + 8 * 60, outcomes=tuple(outcomes), pc_ref="pc")
    base.update(kw)
    return bv.Facts(**base)


def _claim(category, sentence, **slots):
    return bv.Claim(category, slots, sentence, sentence=sentence, valid=True)


def _ctx(e, res, *, was_at, was_clock):
    return SimpleNamespace(engine=e, scene=e.scene, was_at=was_at, was_clock=was_clock,
                           outcomes=tuple(res.outcomes), acting="", intimate=False)


# --- the move -------------------------------------------------------------------------------

def test_the_escorts_walk_out_of_the_hold_is_the_tell_not_a_move():
    """Bench 2026-11-02, the night in the cell, 3 runs of 3: the trial's tell leads the
    player "out of the guardhouse toward the market, hands held" while the scene stands at
    the hold (the walk is the next turn's); the move check flagged the page's "lead you out
    of the guardhouse toward the market", and the repair wrote "seize your arms and hold
    you" over the engine's own sentence. On the escort's walk (`trial.custody` stage
    `walk`) no move claim is judged."""
    s, e, pc, g, _ = _condemned()
    was_at, was_clock = s.at, s.clock_minutes
    res = _wait(e)                                       # the night passes; the walk
    assert trial.custody(pc).payload["stage"] == "walk"
    facts = bv.facts_from(_ctx(e, res, was_at=was_at, was_clock=was_clock))
    assert facts.led and not facts.let_go
    led_out = _claim("move", "They lead you out of the hold toward the square.",
                     place=bv.UNLISTED_PLACE)
    assert bv.diff([led_out], facts) == []
    assert [d.category for d in bv.diff([led_out], _facts(led=False))] == ["move"]


def test_a_cell_in_the_hold_is_not_a_cellar():
    """Bench 2026-11-02, 2 of 3 cell nights: "you sit in the damp, cramped cell" was judged
    set underground at a guardhouse ("there is no cave, tunnel, cellar"), and the repair
    wrote "the damp, cramped guardhouse" beside "the night passes in the cell". With the
    player held at the hold, a cell is where the engine has them."""
    s, e, pc, g, _ = _condemned()
    facts = bv.facts_from(_ctx(e, SimpleNamespace(outcomes=[]), was_at=s.at,
                               was_clock=s.clock_minutes))
    assert set(facts.settings) == {"inside a building", "underground"}


def test_let_go_is_in_the_move_fact_so_the_rewrite_keeps_them_free():
    """Bench 2026-11-02 (the fine, round 1): the fact "the player did not move; they are
    still at the guardhouse" turned "you are released from the guardhouse" into "you are
    held in the guardhouse" beside the tell "is let go, the matter closed". When the
    engine ended custody this turn and the player is still at the hold (a town with
    nowhere outside to put them), the fact says they are free."""
    released = _claim("move", "You are released from the hold.", place=bv.UNLISTED_PLACE)
    found = bv.diff([released], _facts(let_go=True))
    assert [d.category for d in found] == ["move"]
    assert "let go and are free" in found[0].fact
    assert "let go" not in bv.diff([released], _facts())[0].fact


def test_ruling_let_go_the_player_walks_out_of_the_hold():
    """The owner's call of 2026-11-03: released, the player walks out of the hold, as the
    tell already said ("drops the charges, and <the player> walks out of the guardhouse")
    while the scene kept them inside — and the read back then judged every page that let
    them leave as a move the engine never made. Fined and let go, the party is at the
    town's own place outside (`trial.walk_out`, never the hold, the gallows or the gate),
    the tell names it, and a page that releases them is no move to cut."""
    s, e, pc, g, _ = _taken_for_theft()
    pc.purse = {"gp": 30}
    hold = s.at
    _check(e, "diplomacy", g.ref, face=1)                # guilty: the plea
    was_at, was_clock = s.at, s.clock_minutes
    res = _wait(e)                                       # sentence: fined, let go
    t = _tells(res)
    assert s.at != hold and trial.custody(pc) is None
    out = e.here()
    assert f"walks out of the gaol to {out.name}" in t, t
    assert any(x.get("kind") == "moved" and x.get("to") == out.id
               for o in res.outcomes for x in o.effects)
    facts = bv.facts_from(_ctx(e, res, was_at=was_at, was_clock=was_clock))
    assert facts.let_go and facts.end != facts.start
    released = _claim("move", "You are released from the hold.", place=bv.UNLISTED_PLACE)
    assert bv.diff([released], facts) == []
    # And the talk with the watch ends with the walk (live 2026-11-03: it was told on its
    # own a turn later, "no longer here; the conversation with them is over").
    assert not e.talking_to()


def test_ruling_talked_out_walks_out_too():
    """Another door out of custody, a Diplomacy made at questioning (charges dropped): it
    ends outside the hold, told. (No proof at all goes through the same `_release`.)"""
    from rules import attitude

    s, e, pc, g, _ = _taken_for_theft()
    hold = s.at
    attitude.set_regard(g, 95, "test")                   # helpful: the talk can be made
    res = _check(e, "diplomacy", g.ref, face=20)         # talked out
    assert trial.custody(pc) is None and s.at != hold, _tells(res)
    assert "free to go" in _tells(res) and "walks out of" in _tells(res)


def test_every_repair_is_shown_the_beats_own_tells(monkeypatch):
    """Every repair that wrote a slip on the bench of 2026-11-02 was told its one fact and
    nothing else that happened: "held" against "let go", "already here" against "comes to
    the market". The rewrite is now shown the beat's tells (as the page may say them: no
    roll arithmetic) in front of its fact."""
    from gm import agent as agent_mod
    from gm import checks

    sentence = "You are released from the hold."
    text = f"The reeve waves you off. {sentence}"

    class Member:
        REWRITE = True

        @staticmethod
        def find(ctx):
            return [SimpleNamespace(kind="beat-moves-player", sentences=(sentence,),
                                    weight=4, detail="",
                                    fix_hint="The player did not move.")] \
                if sentence in ctx.text else []

        @staticmethod
        def backstop(ctx, text, left):
            return text, []

    asked = []

    def chat(messages, *a, **k):
        asked.append(messages)
        return SimpleNamespace(text='{"sentence": "You are free to go."}', seconds=0.0,
                               model="stub", json=lambda: {"sentence": "You are free to go."})

    monkeypatch.setattr(checks, "owner_of", lambda kind: Member)
    monkeypatch.setattr(agent_mod.client, "chat", chat)
    monkeypatch.setattr(agent_mod, "tells_gate", lambda agent, ctx: None)
    monkeypatch.setattr("gm.checks.narration_in_quotes.quoted_narration",
                        lambda *a, **k: [])
    me = SimpleNamespace(engine=SimpleNamespace(scene=SimpleNamespace(
        pc=lambda: SimpleNamespace(name="Pell Arrow"), actors={})),
        prose_model="stub", prose_host="", prose_provider="ollama", prose_key="",
        _TRUTH_CALLS=3, _lift=lambda t: t)
    let_go = SimpleNamespace(tell="The reeve passes sentence on Pell Arrow. Pell Arrow is "
                                  "let go, the matter closed.")
    rolled = SimpleNamespace(tell="Pell Arrow makes the Diplomacy check by 3 (14 against "
                                  "DC 11).")
    ctx = SimpleNamespace(text=text, said=[], door="turn", outcomes=(let_go, rolled))
    finding = Member.find(ctx)[0]
    out, notes, _ = agent_mod.GMAgent._repair_sentences(me, text, [finding], ctx)
    user = asked[0][-1]["content"]
    assert "is let go, the matter closed" in user
    assert user.index("let go") < user.index("What is true: The player did not move.")
    assert "14 against" not in user, "a roll's arithmetic never reaches the page"
    assert "You are free to go." in out


def test_an_initialled_name_turns_into_you_whole():
    """The fight bench of 2026-11-03 (1 turn baseline, 3 after), the engine's own line put
    in a cut sentence's place: "Pallo Farrow hits you S. With the mwk guisarme." The PC is
    "Corvin T."; `\\b` cannot follow the initial's full stop, so only "Corvin" turned into
    "you", and the stranded "S." read as a sentence end and capitalised the next word.
    The whole name goes; a stop that also ended the sentence stays."""
    swap = narration.pc_to_second_person
    assert swap("Pallo Farrow hits Corvin T. with the mwk guisarme.", "Corvin T.") == (
        "Pallo Farrow hits you with the mwk guisarme.", 1)
    assert swap("The blow catches Corvin T. Then the room spins.", "Corvin T.")[0] == \
        "The blow catches you. Then the room spins."
    assert swap("It strikes Corvin T.", "Corvin T.")[0] == "It strikes you."
    assert swap("Corvin T.'s blade flashes.", "Corvin T.")[0] == "Your blade flashes."
    assert swap("'Corvin T.!' he shouts.", "Corvin T.")[0] == "'Corvin T.!' he shouts."
    assert swap("Against Kesst’s temple, Kesst Vayr swings.", "Kesst Vayr")[0] == \
        "Against your temple, you swing."
    # The readers of the name share the pattern: the third-person check sees it whole.
    found = narration.review("Corvin T. draws a blade.", pc_name="Corvin T.").findings
    assert any(f.kind == "third-person-pc" for f in found)


def _gated_agent(gate):
    """A stand-in agent with `_tells_refuse` and a scripted gate, as `_groom` sets it."""
    from gm import agent as agent_mod

    me = SimpleNamespace(_turn_gate=gate, mention_rows=[])
    me._tells_refuse = lambda *a: agent_mod.GMAgent._tells_refuse(me, *a)
    return me


def test_every_repair_outside_the_sentence_repair_passes_the_tells_gate(monkeypatch):
    """The sweep of 2026-11-02: only `_repair_sentences` stood behind the tells gate; the
    outcome-claim, state-claim, wrong-actor, misnamed, deed, blow and answer repairs wrote
    words the beat's tells never saw. `_tells_refuse` reads only the sentences a repair
    ADDED, and refuses when one breaks a tell the replaced words did not (an original that
    broke it too is not held against the rewrite). Each decision is a `tells-gate` row."""
    asked = []

    def gate(sentences, passage, label="repair"):
        asked.append((label, list(sentences)))
        return any("pay" in s for s in sentences)

    me = _gated_agent(gate)
    before = "You nod. The smith waits."
    assert me._tells_refuse("deeds", before, "You nod and pay him. The smith waits.")
    assert me.mention_rows[-1] == {"kind": "tells-gate", "repair": "deeds", "added": 1,
                                   "broke": True, "refused": True}
    # The original said it too: not refused for it.
    assert not me._tells_refuse("outcome-claims", "You pay the smith.",
                                "You pay the smith again.")
    assert asked[-1] == ("outcome-claims: original", ["You pay the smith."])
    # Nothing added, nothing asked; no gate (a test, the check off), nothing refused.
    n = len(asked)
    assert not me._tells_refuse("misnamed", before, before) and len(asked) == n
    assert not _gated_agent(None)._tells_refuse("answer", before, "You pay.")


def test_the_answer_that_breaks_a_tell_is_not_put_on_the_page(monkeypatch):
    """One of the seven, end to end: `_answer_the_question` puts a quoted answer before the
    hand-back; one that breaks a tell is refused and the beat stays as it was."""
    from gm import agent as agent_mod

    monkeypatch.setattr(agent_mod.client, "chat", lambda *a, **k: SimpleNamespace(
        text="", seconds=0.0, model="stub",
        json=lambda: {"answer": "'You paid me already, and I thank you,' he says."}))
    me = _gated_agent(lambda sentences, passage, label="repair": True)
    me.prose_model = me.prose_host = me.prose_key = ""
    me.prose_provider = "ollama"
    me.last_said = []
    who = SimpleNamespace(name="the smith", ref="c1")
    text = "The smith turns the blank over. What do you do?"
    out, notes, _ = agent_mod.GMAgent._answer_the_question(me, text, who, "did I pay?", "")
    assert out == text and "broke one of the beat's tells" in notes[0]
    assert me.last_said == []


def test_a_remake_is_judged_against_the_refused_tell_it_was_remade_for(monkeypatch):
    """Live 2026-11-03: the refused "pays nothing more: the smith took the fee with the
    job" caught "You hand over the coins as agreed"; the remake prompt said only "the
    engine decided …", the remake wrote "You agree to his price and pay the fee", and the
    whole-beat re-read passed it. Now the remake is told the engine REFUSED it, and each
    sentence of the remake is put to the second read against that very tell: still
    paying, it is cut."""
    from gm import planned

    refused = ("Pell Arrow pays nothing more: the smith took the fee with the job, and the "
               "dagger will be ready to collect here in 1 hour.")
    out = planned.Planned(text="", slots=[], model="stub")
    out.slots.append({"key": "fact1", "max": 220,
                      "wrote": "You nod. You hand over the coins as agreed.", "tells": [],
                      "messages": [{"role": "system", "content": "plan"},
                                   {"role": "user", "content": 'Now write slot "fact1"'}],
                      "reply": "{}"})
    asked = []

    def call_slot(s, messages, who, **kw):
        asked.append(messages)
        reply = SimpleNamespace(text='{"text": "You nod. You agree to his price and pay '
                                     'the fee."}', seconds=0.0, model="stub")
        return reply, {"text": "You nod. You agree to his price and pay the fee."}

    monkeypatch.setattr(planned, "call_slot", call_slot)

    def faith(text, tells):
        if "hand over the coins" in text:
            return bv.TellsRead(clashes=[bv.TellClash(
                "You hand over the coins as agreed.", tells[0], 1, "hand over the coins",
                confirmed=True)], calls=2)
        return bv.TellsRead(calls=1)                     # the whole re-read passes it

    seconds = []

    def second(sentence, tell):
        seconds.append((sentence, tell))
        return "cannot both be true" if "pay the fee" in sentence else "says nothing about it"

    faith.second = second
    planned._tells_kept(out, ("stub", "", "ollama", ""), faith, [refused], refused=[refused])
    ask = asked[0][-1]["content"]
    assert "REFUSED" in ask and "did not happen" in ask
    assert ("You agree to his price and pay the fee.", refused) in seconds
    assert out.slots[0]["wrote"] == "You nod.", "still paying: cut, never kept"
    assert not out.remade[0]["passed"] and out.remade[0]["remade_against_tell"]


# --- presence and the hour ------------------------------------------------------------------

def test_a_keeper_who_comes_to_open_the_counter_arrived():
    """Bench 2026-11-02, 3 of 3 runs of "I wait until morning": the tell "the stallholder
    comes to the market and opens the counter" (`Engine._comings_settles`, effect kind
    `arrives`) beside a page that had them "arrive to open their counters" was judged "has
    been here all along", and the repair wrote it so. The clock's own arrival records are
    arrivals."""
    comes = {"op": "comings", "status": "resolved",
             "tell": "The stallholder comes to the market and opens the counter.",
             "effects": [{"kind": "arrives", "ref": "c2", "at": "m", "origin": "rule:hours"}]}
    arrived = _claim("arrived", "The stallholder arrives to open the counter.", who="c2")
    assert bv.diff([arrived], _facts([comes])) == []
    assert [d.category for d in bv.diff([arrived], _facts())] == ["presence"]
    back = dict(comes, effects=[{"kind": "back", "ref": "c2"}])
    assert bv.diff([arrived], _facts([back])) == []


def test_the_hour_a_sentence_is_set_for_is_the_engines_record_not_a_word_list():
    """The owner's direction (no regex reading English): `_hour_told` matched a list of hour
    words in the tell against the claim's quote. Now the engine records the appointment
    (`scheduled`, the next first light on a death sentence), and an hour claim in that part
    of the day is the appointment; another part of the day is still judged."""
    s, e, pc, g, res = _condemned()
    when = [x["scheduled"] for o in res.outcomes for x in o.effects if "scheduled" in x]
    assert when and (when[0] % 1440) // 60 in bv.PARTS["dawn"]
    facts = bv.facts_from(_ctx(e, res, was_at=s.at, was_clock=s.clock_minutes))
    hang = _claim("hour", "You will hang when the sun comes up.", part="dawn")
    assert bv._hour(facts) not in bv.PARTS["dawn"] | bv.PARTS["midday"]   # the test bites
    assert not [d for d in bv.diff([hang], facts) if d.category == "hour"]
    noon = _claim("hour", "The noon bell rings out.", part="midday")
    assert [d.category for d in bv.diff([noon], facts)] == ["hour"]


def test_a_long_wait_is_told_through_the_hours_it_passed():
    """Bench 2026-11-02, 3 of 3 runs of "I wait until morning" (816 minutes from 18:24):
    "you wait through the long, quiet hours of the night until the first light" was judged
    against 08:00 alone, and the repair wrote "through the long, quiet hours of the early
    morning". Any hour the clock stood in this turn is true; a part of the day the turn
    never touched is still judged, and with no start known the clock now is."""
    night = _claim("hour", "You wait through the long hours of the night.", part="night")
    wait = _facts(clock=5 * 1440 + 8 * 60, was_clock=4 * 1440 + 18 * 60 + 24)
    assert bv.diff([night], wait) == []
    assert [d.category for d in bv.diff([night], _facts())] == ["hour"]
    noon = _claim("hour", "The midday sun beats down.", part="midday")
    assert [d.category for d in bv.diff([noon], wait)] == ["hour"]
    short = _facts(clock=5 * 1440 + 8 * 60, was_clock=5 * 1440 + 7 * 60 + 50)
    assert [d.category for d in bv.diff([night], short)] == ["hour"]


def test_a_night_the_engine_passed_is_not_cut_for_a_refused_rest(monkeypatch):
    """Bench 2026-11-02, the night in the condemned cell, 2 of 3 runs: the rest was refused
    ("still in conversation …") while the trial passed 672 minutes; the no-time-passed
    backstop cut "the hours bleed into one another as you sit in the dim, damp cell" — the
    trial's own "the night passes in the cell" — and wrote the refusal in its place. Hours
    on the clock went by, whatever was refused; a refused rest on an unmoved clock is still
    asked."""
    from tests.test_time_kept import REFUSAL, ROOM
    from tests.test_time_kept import _ctx as time_ctx
    from gm.checks import time_kept

    rest = {"op": "rest", "status": "refused", "tell": REFUSAL}
    ctx, seen = time_ctx(monkeypatch, 3, reading=None, outcomes=[rest], text=ROOM,
                         was=1825, now=1825 + 672)
    assert time_kept.find(ctx) == [] and seen == []
    ctx, _seen = time_ctx(monkeypatch, 3, reading=None, outcomes=[rest], text=ROOM)
    assert time_kept.find(ctx)


# --- payments -------------------------------------------------------------------------------

def test_coin_for_work_or_a_fine_is_a_payment_the_engine_made():
    """Bench 2026-11-02: "the smith accepts the commission for 1 gold, 4 silver, and 3
    copper" (commission r1) and "accepts your payment of six gold pieces" (the fine r1)
    were each cut as "no sale was made this turn" — and the commission's rewrite first
    made it "for 0 gold, 0 silver, and 0 copper pieces". The engine's commission (`cp`)
    and fine (`paid_cp`) are payments."""
    settled = _claim("trade", "The smith accepts the commission for 1 gold.",
                     item=bv.OTHER_THING, seller="c1", buyer="pc", settled=True)
    job = {"op": "commission", "status": "resolved", "tell": "takes the job",
           "effects": [{"kind": "commission", "cp": 143, "ref": "pc", "keeper": "c1"}]}
    fine = {"op": "trial", "status": "resolved", "tell": "pays 6 gold pieces",
            "effects": [{"kind": "fine", "cp": 600, "paid_cp": 600}]}
    haggle = {"op": "haggle", "status": "refused", "tell": "no", "effects": []}
    assert bv.diff([settled], _facts([job])) == []
    assert bv.diff([settled], _facts([fine, haggle])) == []
    assert [d.category for d in bv.diff([settled], _facts([haggle]))] == ["trade"]
    # And a price agreed for work already paid, refused: coins handed over again on the
    # page are a payment the engine never took (the rerun of 2026-11-03, 3 of 3 pages).
    again = {"op": "commission", "status": "refused", "effects": [],
             "tell": "Pell Arrow pays nothing more: the smith took the fee with the job."}
    assert [d.category for d in bv.diff([settled], _facts([again]))] == ["trade"]


def test_a_hand_over_the_engine_moved_nothing_for_is_not_owed_to_the_page():
    """Bench 2026-11-02, "I agree to his price and pay" (2 of 3 runs), and the live check
    that day: read `sell` and `give` with nothing built for either, and the unshown-deed
    backstop wrote the agreement and the payment as done on a turn no op paid anything.
    A hand-over the table built nothing for and no op of its kind resolved is not owed; a
    gesture ("give him a nod") still is, and so is one whose op ran."""
    reading = {"question": False, "claims": [], "actions": [
        {"act": "sell", "target": "his", "span": "agree to his price"},
        {"act": "give", "span": "pay"},
        {"act": "give", "target": "him", "object": "a nod", "span": "give him a nod"}],
        "table": [{"act": "sell", "ops": [], "missing": "nothing was named to sell"},
                  {"act": "give", "ops": [], "note": "nothing named to hand over"},
                  {"act": "give", "ops": [], "note": "'a nod' is not a thing",
                   "gesture": True}]}
    line = "I agree to his price and pay and give him a nod"
    owed = [d["act"] for d in narration.owed_deeds(reading, line, ())]
    assert owed == ["give"] and narration.moved_nothing(reading, 1, "give", ())
    paid = [{"op": "give", "status": "resolved", "tell": "hands"}]
    assert not narration.moved_nothing(reading, 1, "give", paid)
    from gm import deed_reader

    assert [d["span"] for d in deed_reader.deeds_of(reading, line, ())] == ["give him a nod"]


def test_paying_the_fine_at_the_plea_is_the_sentences_payment_never_a_bribe():
    """The owner's slip 2 of 2026-11-01 and the bench of 2026-11-02 (2 of 3 runs): "I say
    nothing more and pay the fine" at the plea was planned as a give of 6 gold to the
    officer; the engine read coin handed to the law by somebody held as a bribe ("pushes
    it back: looking the other way would take …") beside the sentence's own "pays 6 gold
    pieces". The give is dropped (`fold_the_fine`), the reading's "pay the fine" builds
    nothing and refuses nothing, and the sentence takes the fine — once."""
    s, e, pc, g, _ = _taken_for_theft()
    pc.purse = {"gp": 30}
    _check(e, "diplomacy", g.ref, face=1)                # guilty: the plea, a fine to come
    assert acts_to_ops.fine_pending(s, pc)
    plan = [{"op": "give", "actor": "pc", "target": g.ref,
             "params": {"item": "gp", "count": 6, "to": g.ref}},
            {"op": "narrate_only", "because": "t"}]
    notes: list = []
    assert acts_to_ops.fold_the_fine(plan, s, notes) == plan[1:] and notes
    # And with nobody named to take it — the after-bench's own run: "6 gp" and the
    # bracelet with no `to` were read as the player picking them up, refused, and told as
    # "the silver bracelet remains safely in your possession". Gone too.
    nobody = [{"op": "give", "actor": "pc", "params": {"item": "gp", "count": 6}},
              {"op": "give", "actor": "pc", "params": {"item": "apple"}}]
    assert acts_to_ops.fold_the_fine(nobody, s) == []
    frame = {"question": False, "claims": [], "actions": [
        {"act": "give", "object": "the fine", "span": "pay the fine"}]}
    rows = acts_to_ops.table(frame, s)
    assert not rows[0].intents and not rows[0].missing
    assert acts_to_ops.refusal(rows) == "", "the turn is not refused 'not carrying the fine'"
    before = goods.in_copper(pc.purse)
    res = _run(e, acts_to_ops.apply(plan, rows, frame, s))
    t = _tells(res)
    assert "pushes it back" not in t and "looking the other way" not in t, t
    assert "The fine is" in t and trial.custody(pc) is None, t
    assert before - goods.in_copper(pc.purse) == next(
        x["paid_cp"] for o in res.outcomes for x in o.effects if x.get("kind") == "fine")


def test_the_condemned_may_still_bribe_the_jailer():
    """The fold is the fine's alone: with a death sentence there is no fine, and coin to
    the law in the cell is the bribe the ruling offers ("pay the jailer to look away")."""
    s, e, pc, g, _ = _condemned()
    assert not acts_to_ops.fine_pending(s, pc)
    plan = [{"op": "give", "actor": "pc", "target": g.ref,
             "params": {"item": "gp", "count": 6, "to": g.ref}}]
    assert acts_to_ops.fold_the_fine(plan, s) == plan


# --- a price agreed at the smith -----------------------------------------------------------

AGREE = {"question": False, "claims": [], "actions": [
    {"act": "sell", "target": "his", "span": "agree to his price"},
    {"act": "give", "span": "pay"}]}


def test_agreeing_the_keepers_price_takes_the_job_at_the_engines_price(world, monkeypatch):
    """Bench 2026-11-02, 3 of 3 runs of "I agree to his price and pay" the turn after the
    smith spoiled the first try: read `sell: his price`, `give: pay`, the table built
    nothing ("nothing was named to sell"), and the plan paid 10 gold, 1 gold, or nothing
    — never the job's price. The keeper asked for work today (`commission.asked_of`) takes
    the job again at the engine's own price, once for the two deeds, and the plan's coin
    beside it is dropped."""
    e, pc = _engine(world, carry=(("iron", 2), ("charcoal", 2), ("ash-haft", 2)))
    _blank(e, pc)
    smith, _ = _smith(e)
    monkeypatch.setattr(commission, "keeper_roll",
                        lambda engine, keeper, step: _Face(int(step.dc) - 6)(engine, keeper,
                                                                             step))
    first = e.run(e.validate([{"op": "commission", "actor": "pc", "because": "t",
                               "params": {"who": smith.ref, "item": "the dagger"}}]))
    assert first.outcomes[0].effects[0].get("spoiled")
    assert commission.asked_of(e.scene, pc, smith)["how"] == "spoiled"
    monkeypatch.setattr(commission, "keeper_roll",
                        lambda engine, keeper, step: _Face(int(step.dc) + 2)(engine, keeper,
                                                                             step))
    rows = acts_to_ops.table(AGREE, e.scene)
    built = [b for r in rows for b in r.intents]
    assert [b["op"] for b in built] == ["commission"]
    assert built[0]["params"] == {"who": smith.ref, "item": "the dagger", "agree": True}
    plan = [{"op": "give", "actor": "pc", "target": smith.ref,
             "params": {"item": "gp", "count": 10, "to": smith.ref}}]
    raw = acts_to_ops.apply(plan, rows, AGREE, e.scene)
    assert [r["op"] for r in raw] == ["commission"], raw
    # A coin `sell` the reading's `sell` would let stand, which `inject_payment` turns into
    # gives (the rerun of 2026-11-03, 1 of 3), goes the same way.
    sold = [{"op": "sell", "actor": "pc", "target": smith.ref,
             "params": {"item": "gold-piece-1", "to": smith.ref}}]
    assert [r["op"] for r in acts_to_ops.apply(sold, rows, AGREE, e.scene)] == ["commission"]
    purse = goods.in_copper(pc.purse)
    out = e.run(e.validate(raw)).outcomes[0]
    assert out.status == "resolved" and "takes the job" in out.tell, out.tell
    assert purse - goods.in_copper(pc.purse) == out.effects[0]["cp"] > 0
    # Agreed again: already paid, nothing more taken, and the engine says so — refused,
    # from the player's side. Told as a resolved "Nothing more is owed", the rerun of
    # 2026-11-03 had the player hand the coins over again on 3 of 3 pages.
    again = e.run(e.validate(acts_to_ops.apply([], acts_to_ops.table(AGREE, e.scene),
                                               AGREE, e.scene))).outcomes[0]
    # Worded as a payment in the past since 2026-11-05 (`commission.paid_before`): "pays
    # nothing more: the smith took the fee with the job" was still told as coin taken now.
    assert again.status == "refused" and "earlier, when the job was taken" in again.tell \
        and "no coin changes hands" in again.tell, again.tell
    assert goods.in_copper(pc.purse) == purse - out.effects[0]["cp"]


def test_no_work_asked_today_agrees_nothing(world):
    """With no work asked of anybody here today, "agree to his price" is what it was: no
    commission is invented from the words."""
    e, pc = _engine(world)
    _smith(e)
    rows = acts_to_ops.table(AGREE, e.scene)
    assert not [b for r in rows for b in r.intents]
    assert json.dumps(rows[0].record())

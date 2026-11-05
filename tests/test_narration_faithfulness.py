"""The extra step of planned narration: the beat read against its own tells (2026-11-02).

The owner, 2026-11-02: "anything we can do about the narration slips? perhaps a extra step
in the preparation of the narration even if it adds a few seconds". Three slips seen live on
the integration build the day before, each a sentence that cannot be true beside one of its
beat's own tells, and none of a shape the read back's typed slots read:

  * a theft written as failed: the tell had the bracelet taken, the page "it remains on the
    tray" (a negation claims no change of hands);
  * a fine garbled: the tell had the player pay six gold and the bracelet go back to its
    owner, the page had the player "hold the six gold pieces and the silver bracelet";
  * a scheduled hour: the tell said hanged "at first light", the page twice "at six in the
    evening" (the hour slot reads the clock now, not an hour something is set for).

`beat_verify.against_tells` asks per sentence, against all the beat's tells, for a closed
verdict naming the tell and the clashing words; code checks both (and, under the "second"
veto a bench can still pick, a second read asks again with the order swapped — measured on
full turns on 2026-11-03 and set aside: tests/test_tells_veto.py). `planned._tells_kept` remakes only a slot holding a confirmed clash,
reads the remake again, and cuts what still clashes. Every slot it caught is logged for
training to `auto-corrections.jsonl`, never the player's own `corrections.jsonl`
(the owner, 2026-11-02: "also log the narration corrections for training").

The names and prose here are synthetic; the bench numbers are in
docs/narration-faithfulness.md.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from gm import beat_verify as bv
from gm import planned


class _Reply:
    def __init__(self, text, model="stub"):
        self.text, self.seconds, self.model = text, 0.0, model

    def json(self):
        return json.loads(self.text)


def _chat(*replies):
    """A chat that answers in order and records what it was asked."""
    queue = [r if isinstance(r, str) else json.dumps(r) for r in replies]
    asked: list = []

    def chat(messages, *a, **k):
        asked.append((messages, k))
        if not queue:
            raise AssertionError("asked more than the test scripted")
        said = queue.pop(0)
        if said == "FAIL":
            raise RuntimeError("the model wrote nothing")
        return _Reply(said)

    chat.asked = asked
    return chat


THEFT = ["Pell Arrow takes the copper ring from the tinker, who did not hand it over; it is "
         "still theirs. Seen by the watchman: there will be a warrant for theft."]
FINE = ["The reeve passes sentence on Pell Arrow. The fine is 6 gold pieces; Pell Arrow pays 6 "
        "gold pieces. Taken back to their owners: copper ring to the tinker."]
HANGED = ["The reeve passes sentence: Pell Arrow is to hang at first light tomorrow for "
          "murder. Until then, the condemned cell."]


def _verdicts(*rows):
    """The first read's answer, one row per sentence: (verdict, fact, words)."""
    return {str(i): {"verdict": v, "fact": f, "words": w} for i, (v, f, w) in
            enumerate(rows, 1)}


# --- the read ---------------------------------------------------------------------------

def test_a_theft_written_as_failed_is_a_clash_the_second_read_keeps(monkeypatch):
    """Under the "second" veto (`beat_verify.tells_veto`, the default until 2026-11-03,
    kept for a bench's baseline). The live slip: the tell had the ring taken, the page said it "remains on the tray".
    The `changed_hands` slot reads a change of hands and a negation claims none, so the read
    back passed it. Read against the tell, it is a contradiction quoted in the sentence's
    own words, and the second read (fact first) keeps it."""
    text = ("You reach toward the tinker's tray with quick fingers. The copper ring glints, "
            "but it remains on the tray. The tinker hums to himself.")
    chat = _chat(_verdicts(("not about it", "none", ""),
                           ("contradicts", "F1", "it remains on the tray"),
                           ("not about it", "none", "")),
                 {"answer": "cannot both be true"})
    monkeypatch.setenv("PATHFINDER_GM_TELLS_VETO", "second")
    got = bv.against_tells(text, THEFT, who="Pell Arrow", chat=chat)
    assert [(c.words, c.n) for c in got.clashes] == [("it remains on the tray", 1)]
    assert got.clashes[0].sentence == "The copper ring glints, but it remains on the tray."
    assert got.calls == 2 and not got.refused and not got.dropped
    # The premise is the tell, numbers off; the player is named so "you" can be read.
    first = chat.asked[0][0][-1]["content"]
    assert "F1. Pell Arrow takes the copper ring" in first
    assert "the player's character is Pell Arrow" in first
    # Fact FIRST on the second read: the first had the sentences after the facts too, but
    # the confirming read is one fact and one sentence, the fact leading.
    second = chat.asked[1][0][-1]["content"]
    assert second.index("FACT") < second.index("SENTENCE")


def test_a_clash_it_cannot_point_at_costs_nothing():
    """The grounding: "contradicts" must name a fact on the list and copy at least two of
    the sentence's own words. A verdict that quotes words the sentence does not have is
    dropped, and nothing is asked again (Huang et al. 2024: an ungrounded self-critique
    makes things worse, so an ungrounded verdict is not acted on)."""
    text = "You count out the coins for the reeve. The clerk nods."
    chat = _chat(_verdicts(("contradicts", "F1", "you keep the six gold pieces"),
                           ("contradicts", "none", "The clerk nods")))
    got = bv.against_tells(text, FINE, who="Pell Arrow", chat=chat)
    assert not got.clashes and len(got.dropped) == 2 and got.calls == 1
    assert {d["why"] for d in got.dropped} == {
        "the clashing words are not the sentence's own", "no fact named"}


def test_the_second_read_refuses_a_false_alarm(monkeypatch):
    """Under the "second" veto (a bench's baseline since 2026-11-03): only a clash the second read calls "cannot both be true" costs a sentence; a
    "tells it" there is refused and the slot stands (RARR: edit only on a disagreement)."""
    text = "The reeve names the fine, and you pay it in gold."
    chat = _chat(_verdicts(("contradicts", "F1", "you pay it in gold")),
                 {"answer": "tells it"})
    monkeypatch.setenv("PATHFINDER_GM_TELLS_VETO", "second")
    got = bv.against_tells(text, FINE, who="Pell Arrow", chat=chat)
    assert not got.clashes and [c.words for c in got.refused] == ["you pay it in gold"]


def test_a_read_that_fails_judges_nothing():
    got = bv.against_tells("The reeve frowns.", FINE, chat=_chat("FAIL"))
    assert got.error and not got.clashes and got.calls == 1


def test_the_premises_are_the_tells_with_the_numbers_and_the_xp_off():
    """The tells as the narrator may tell them (`narration.page_line`): no roll arithmetic,
    no damage amount — and the XP line, bookkeeping no sentence tells, gone; a price stays."""
    got = bv.tell_premises([
        "Pell Arrow makes the sleight of hand check by 9. You gain 100 XP for the sleight of "
        "hand check (DC 12) (6,000 of 9,000 for level 4).",
        "Pell Arrow hits the tinker with the dagger for 5 piercing.",
        "", "Pell Arrow buys the lantern for 2 sp.",
        "Pell Arrow buys the lantern for 2 sp."])
    assert got == ["Pell Arrow makes the sleight of hand check.",
                   "Pell Arrow hits the tinker with the dagger.",
                   "Pell Arrow buys the lantern for 2 sp."]


def test_the_schema_holds_one_verdict_per_sentence_and_only_listed_facts():
    s = bv.tells_schema(3, 2)
    assert s["required"] == ["1", "2", "3"]
    item = s["properties"]["2"]
    assert item["properties"]["fact"]["enum"] == ["none", "F1", "F2"]
    assert item["properties"]["verdict"]["enum"] == list(bv.TELL_VERDICTS)


# --- the remake, slot by slot -------------------------------------------------------------

def _beat(*slots):
    """A planned beat as `_write_slots` leaves it: each slot's text and its kept call."""
    out = planned.Planned(text="", slots=[], model="stub")
    for key, text in slots:
        out.slots.append({"key": key, "max": 220, "wrote": text, "tells": [],
                          "messages": [{"role": "system", "content": "plan"},
                                       {"role": "user", "content": f'Now write slot "{key}"'}],
                          "reply": json.dumps({"text": text})})
    return out


def _faith(chat):
    return lambda text, tells: bv.against_tells(text, tells, who="Pell Arrow", chat=chat)


def _remakes(monkeypatch, *texts):
    """`planned.call_slot` answering the remake(s) in order; what each was asked."""
    asked = []
    queue = list(texts)

    def call_slot(s, messages, who, **kw):
        asked.append(messages)
        reply = _Reply(json.dumps({"text": queue.pop(0)}))
        return reply, reply.json()

    monkeypatch.setattr(planned, "call_slot", call_slot)
    return asked


WHO = ("stub", "", "ollama", "")


def test_a_clashing_slot_is_remade_with_its_tell_named_and_kept_when_it_passes(monkeypatch):
    """The theft again, now through the step: only the act slot holding the clash is asked
    again — its own kept call, the sentence and the tell it breaks named — the remake is
    read again and stands; the slot before it is not touched (RARR's over-editing)."""
    out = _beat(("fact1", "You reach for the copper ring, but it remains on the tray."),
                ("reply", "'Mind your hands,' the tinker says."))
    asked = _remakes(monkeypatch, "You snatch the copper ring from the tray and pocket it.")
    chat = _chat(_verdicts(("contradicts", "F1", "it remains on the tray"),
                           ("not about it", "none", "")),
                 _verdicts(("agrees", "F1", "")))
    planned._tells_kept(out, WHO, _faith(chat), THEFT)
    assert [s["wrote"] for s in out.slots] == [
        "You snatch the copper ring from the tray and pocket it.",
        "'Mind your hands,' the tinker says."]
    ask = asked[0][-1]["content"]
    assert "it remains on the tray" in ask and "Pell Arrow takes the copper ring" in ask
    assert out.remade[0]["passed"] and out.remade[0]["slot"] == "fact1"
    assert out.remade[0]["prompt"][-1]["content"] == 'Now write slot "fact1"', \
        "the training prompt is the slot's call without the correction appended"
    assert [r["pass"] for r in out.faith] == ["beat", "remade fact1"]
    assert any("asked again, fixed" in n for n in out.notes)


def test_a_clean_beat_costs_one_read_and_changes_nothing(monkeypatch):
    out = _beat(("fact1", "You pay the reeve six gold pieces."),
                ("still", "The clerk's quill scratches on."))
    asked = _remakes(monkeypatch)
    chat = _chat(_verdicts(("agrees", "F1", ""), ("not about it", "none", "")))
    planned._tells_kept(out, WHO, _faith(chat), FINE)
    assert len(chat.asked) == 1 and not asked and not out.remade
    assert [s["wrote"] for s in out.slots] == ["You pay the reeve six gold pieces.",
                                              "The clerk's quill scratches on."]


def test_a_remake_that_still_clashes_is_cut_and_logged_rejected_only(monkeypatch, tmp_path,
                                                                     settings):
    """The fine garbled: "You hold the six gold pieces and the copper ring" against the
    tell that has them paid and given back. The remake breaks the tell again, so the
    clashing sentence is cut and the rest of the slot stands. The training log gets the
    slot as rejected-only — in `auto-corrections.jsonl`, never the player's log."""
    settings.CAMPAIGN_DIR = str(tmp_path / "campaigns")
    out = _beat(("fact1", "The reeve names the fine. You hold the six gold pieces and the "
                          "copper ring for the tinker."))
    _remakes(monkeypatch, "You keep the coins in your fist.")
    chat = _chat(_verdicts(("agrees", "F1", ""),
                           ("contradicts", "F1", "You hold the six gold pieces")),
                 _verdicts(("contradicts", "F1", "keep the coins in your fist")))
    planned._tells_kept(out, WHO, _faith(chat), FINE)
    assert out.slots[0]["wrote"] == "The reeve names the fine."
    rec = out.remade[0]
    assert not rec["passed"] and rec["remade"] == "You keep the coins in your fist."
    assert rec["stood"] == "The reeve names the fine."

    from play import corrections

    c = SimpleNamespace(id="synthetic", turn_log=[],
                        transcript=[{"who": "gm", "kind": "setup", "text": "The reeve "
                                                                          "names the fine."}])
    agent = SimpleNamespace(last_tells_remade=out.remade, last_prose_messages=[{"x": 1}],
                            last_prose_model="stub", prose_model="stub",
                            last_narration="planned", last_prose_slots=out.slots)
    assert corrections.log_auto(c, 0, agent=agent, player_input="I pay the fine",
                                brief="the court", facts=FINE) == 1
    root = tmp_path / "training"
    assert not (root / "corrections.jsonl").exists(), "the player's log stays theirs"
    line = json.loads((root / "auto-corrections.jsonl").read_text(encoding="utf-8"))
    assert line["label"] == "rejected-only" and line["kind"] == "tells-check"
    assert line["rejected"].endswith("copper ring for the tinker.")
    assert line["remade"] == "You keep the coins in your fist." and not line["remade_passed"]
    assert "You hold the six gold pieces" in line["reason"]
    assert line["input"]["facts"] == FINE and line["input"]["narration"] == "planned"
    # Every slot's own call repeats the plan (108-118 KB a record on the bench): the input
    # keeps what each slot wrote, and the caught slot's call is the record's own prompt.
    assert all("messages" not in s for s in line["input"]["slots"])
    assert line["prompt"][-1]["content"] == 'Now write slot "fact1"'
    assert line["campaign"] == "synthetic" and line["beat"] == 0 and line["id"]


def test_an_act_slot_with_nothing_left_gets_the_engines_line(monkeypatch):
    """The scheduled hour: "hanged at six in the evening" against "at first light", the
    slot's only sentence, its remake no better. An act is never left off the page: the
    engine's own line, numbers off, stands in (the groom makes the name "you")."""
    out = _beat(("fact1", "You will be hanged at six in the evening."))
    out.slots[0]["tells"] = HANGED
    _remakes(monkeypatch, "At six in the evening the rope waits.")
    chat = _chat(_verdicts(("contradicts", "F1", "hanged at six in the evening")),
                 _verdicts(("contradicts", "F1", "At six in the evening")))
    planned._tells_kept(out, WHO, _faith(chat), HANGED)
    assert out.slots[0]["wrote"] == HANGED[0]
    assert out.remade[0]["stood"] == HANGED[0] and not out.remade[0]["passed"]


def test_a_remake_that_is_not_whole_prose_is_not_used(monkeypatch):
    """Measured on the bench's first run (2026-11-02): a matter slot's remake came back
    "… beyond the east crossing. (Note: This matter remains as your objective." — the
    model talking to us, its bracket open — and the second read let it stand. A remake with
    an unclosed bracket, or that the page's own checks fault, is not read again: the
    clashing sentence is cut, and the record says why."""
    out = _beat(("matter", "You must buy supplies for the long road ahead."))
    _remakes(monkeypatch, "You must buy supplies for the road. (Note: This matter remains.")
    chat = _chat(_verdicts(("contradicts", "F1", "You must buy supplies")))
    planned._tells_kept(out, WHO, _faith(chat), HANGED)
    assert len(chat.asked) == 1, "the broken remake is never read"
    assert out.slots[0]["wrote"] == "" and out.slots[0]["dropped"]
    assert out.remade[0]["remade_broken"] == "an unclosed bracket"
    assert not out.remade[0]["passed"]


def test_an_unread_beat_stands_as_written(monkeypatch):
    out = _beat(("fact1", "You will be hanged at six in the evening."))
    asked = _remakes(monkeypatch)
    planned._tells_kept(out, WHO, _faith(_chat("FAIL")), HANGED)
    assert out.slots[0]["wrote"] == "You will be hanged at six in the evening."
    assert not asked and any("not answered" in n for n in out.notes)


# --- our own repairs made two of the three slips ---------------------------------------------
#
# Found on the bench of 2026-11-02 by reading each slipped beat's drafts beside its page: the
# narrator had written "hanging at first light" and "snatching it from the tray"; the read
# back's hour and attempt judgements flagged them, and their repairs wrote the slips.

def _facts(outcomes, clock):
    return bv.Facts(start="the guardhouse", end="the guardhouse", places=("the guardhouse",),
                    people=(bv.Person("pc", "Pell Arrow", pc=True),
                            bv.Person("c1", "the reeve"), bv.Person("c2", "the tinker")),
                    clock=clock, outcomes=tuple(outcomes), pc_ref="pc")


def _hour_claim(part, sentence):
    return bv.Claim("hour", {"part": part}, sentence, sentence=sentence, valid=True)


def test_an_hour_the_tell_sets_is_not_the_clock_now():
    """The owner's slip 3: at six in the evening the tell said "to hang at first light
    tomorrow", the narrator wrote "hanging at first light", and the hour judgement read it
    as the time now and had it rewritten "at six in the evening" (on the bench too, with
    "until dawn" made "until evening" a second time). An hour the engine set something for
    this turn (an effect's `scheduled` minute) is its appointment and is not judged against
    the clock. Only an appointment: the gold beat `finalized` (a refusal "opens at first
    light", the page "the pre-dawn light is just beginning" at 01:28) keeps its true alarm,
    and an hour no record sets is judged as before."""
    evening = 4 * 1440 + 18 * 60
    sentence = "The reeve sentences you to hang at first light."
    # Since 2026-11-03 the engine's own record says when (`scheduled`), never the words.
    tells = [{"op": "trial", "status": "resolved", "tell": HANGED[0],
              "effects": [{"kind": "sentence", "death": True,
                           "scheduled": 5 * 1440 + 6 * 60}]}]
    assert not [d for d in bv.diff([_hour_claim("dawn", sentence)], _facts(tells, evening))
                if d.category == "hour"]
    # A tell that only SAYS first light (a shop's hours, the gold beat `finalized`) sets
    # nothing, and the page's dawn-now is still judged against the clock.
    pre_dawn = "Outside, the pre-dawn light is just beginning to bleed into the gray."
    said_only = [{"op": "trial", "status": "resolved", "tell": HANGED[0], "effects": []}]
    assert [d.category for d in bv.diff([_hour_claim("dawn", pre_dawn)],
                                        _facts(said_only, evening))] == ["hour"]
    found = bv.diff([_hour_claim("dawn", "Dawn light spills into the cell.")],
                    _facts([{"op": "say", "status": "resolved", "tell": "x", "effects": []}],
                           evening))
    assert [d.category for d in found] == ["hour"]


def test_a_failed_sleight_of_hand_whose_theft_happened_is_not_asked():
    """The owner's slip 1: the Sleight of Hand check missed, and the engine still resolved
    the theft ("takes the silver bracelet …, who did not hand it over … Seen by the
    guardsman"): a miss is the theft seen, not undone. The attempt judgement asked the
    failed check, read "snatching it from the tray" as the attempt succeeding, and the
    repair — told "what was tried is not done" — wrote "failing to snatch it". A failed
    check whose deed the engine did anyway (a thing taken into the checker's hands later
    that turn) is not asked; a failed check with no such deed still is."""
    check = {"op": "check", "status": "resolved", "verdict": "failure", "actor": "pc",
             "rolls": [{"label": "Sleight of Hand check"}], "tell": "misses", "effects": []}
    took = {"op": "give", "status": "resolved", "actor": "pc", "tell": THEFT[0],
            "effects": [{"kind": "give", "item": "copper ring", "from": "c2", "to": "pc",
                         "how": "took_from"}]}
    assert bv.attempts_of(_facts([check, took], 600)) == []
    assert [a.verdict for a in bv.attempts_of(_facts([check], 600))] == ["failure"]


def test_a_repair_that_breaks_a_tell_is_refused_and_the_sentence_stands(monkeypatch):
    """The gate (`GMAgent._repair_sentences`): a rewrite the member would keep is read
    against the beat's own tells, and refused when it breaks one the original did not —
    and no backstop then cuts the original."""
    from gm import agent as agent_mod
    from gm import checks

    original = "The reeve sentences you to hang at first light."
    fixed = "The reeve sentences you to hang at six in the evening."
    text = f"You plead. {original} The cell door shuts."

    class Member:
        REWRITE = True

        @staticmethod
        def find(ctx):
            return [SimpleNamespace(kind="beat-hour", sentences=(original,), weight=3,
                                    detail="", fix_hint="")] if original in ctx.text else []

        @staticmethod
        def backstop(ctx, text, left):
            return text.replace(original, ""), ["cut"]

    finding = Member.find(SimpleNamespace(text=text))[0]
    monkeypatch.setattr(checks, "owner_of", lambda kind: Member)
    monkeypatch.setattr(agent_mod.client, "chat",
                        lambda *a, **k: _Reply(json.dumps({"sentence": fixed})))
    me = SimpleNamespace(engine=SimpleNamespace(scene=SimpleNamespace(
        pc=lambda: SimpleNamespace(name="Pell Arrow"), actors={})),
        prose_model="stub", prose_host="", prose_provider="ollama", prose_key="",
        _TRUTH_CALLS=3, _lift=lambda t: t)
    asked = []
    monkeypatch.setattr(agent_mod, "tells_gate",
                        lambda agent, ctx: (lambda s, p: asked.append(s) or s == fixed))
    ctx = SimpleNamespace(text=text, said=[], door="turn")
    monkeypatch.setattr("gm.checks.narration_in_quotes.quoted_narration",
                        lambda *a, **k: [])
    out, notes, _ = agent_mod.GMAgent._repair_sentences(me, text, [finding], ctx)
    assert original in out and fixed not in out
    assert asked == [fixed, original]
    assert any("broke one of the beat's own tells" in n for n in notes)
    assert not any(n == "cut" for n in notes), "the backstop does not cut a protected sentence"


# --- the switch, the log and the report ----------------------------------------------------

def test_the_check_is_always_on_with_no_switch(tmp_path, settings, monkeypatch):
    """The owner's ruling of 2026-11-02: the tells check is always on, with no Settings
    switch. It shipped for a day as a house rule `tells_check`, writable through
    /api/homebrew/rules (`set_active`) — a switch with no control on any page. No house rule
    names it now: a request to turn it off writes nothing, and only the bench's environment
    variable, which the app never sets, stops it."""
    from rules import houserules

    settings.CAMPAIGN_DIR = str(tmp_path / "campaigns")
    monkeypatch.delenv("PATHFINDER_GM_TELLS_CHECK", raising=False)
    assert "tells_check" not in houserules.DEFAULTS
    assert planned.tells_check_on()
    rules, _problems = houserules.set_active({"tells_check": False})
    assert "tells_check" not in rules and "tells_check" not in houserules.active()
    assert planned.tells_check_on()
    monkeypatch.setenv("PATHFINDER_GM_TELLS_CHECK", "0")
    assert not planned.tells_check_on()


def test_the_machine_log_is_capped_and_rides_the_report(tmp_path, settings, monkeypatch):
    settings.CAMPAIGN_DIR = str(tmp_path / "campaigns")
    from play import corrections

    monkeypatch.setattr(corrections, "AUTO_KEPT", 3)
    c = SimpleNamespace(id="synthetic", turn_log=[],
                        transcript=[{"who": "gm", "kind": "setup", "text": "x"}])
    record = {"slot": "fact1", "prompt": [{"role": "user", "content": "p" * 1500}],
              "rejected": "bad", "clashes": [], "remade": "good", "passed": True,
              "stood": "good"}
    agent = SimpleNamespace(last_tells_remade=[record], last_narration="planned",
                            last_prose_messages=[], prose_model="stub")
    for _ in range(6):
        corrections.log_auto(c, 0, agent=agent, player_input="", brief="", facts=[])
    lines = corrections.auto_log_path().read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3 and json.loads(lines[-1])["label"] == "pair"
    sent = corrections.auto_for_report()
    assert sent and len(sent.splitlines()) == 3
    from play import report

    assert "auto-corrections" in report.WITH_THE_SAVE


def test_a_disk_that_refuses_loses_the_record_not_the_turn(tmp_path, settings, monkeypatch):
    settings.CAMPAIGN_DIR = str(tmp_path / "campaigns")
    from play import corrections

    def refuse(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(corrections, "_input_entry", refuse)
    c = SimpleNamespace(id="synthetic", turn_log=[], transcript=[{"text": "x"}])
    agent = SimpleNamespace(last_tells_remade=[{"slot": "fact1"}])
    assert corrections.log_auto(c, 0, agent=agent, player_input="", brief="",
                                facts=[]) == 0
    assert c.turn_log[-1]["kind"] == "auto-correction-lost"


def test_the_machine_corrections_export_as_their_own_sets():
    """`tools/corrections_to_pairs.convert_auto`: a passing remake is a DPO pair whose
    prompt is the slot's own call; a failed one is only a rejected KTO example."""
    from tools import corrections_to_pairs as ctp

    base = {"kind": "tells-check", "prompt": [{"role": "user", "content": "write fact1"}],
            "rejected": "it remains on the tray", "rejected_raw": '{"text": "it remains on '
                                                                 'the tray"}'}
    sets = ctp.convert_auto([
        {**base, "id": "a", "remade": "you pocket it", "remade_raw": '{"text": "you pocket '
                                                                     'it"}',
         "remade_passed": True, "label": "pair"},
        {**base, "id": "b", "remade": "still there", "remade_passed": False,
         "label": "rejected-only"},
        {"kind": "something else"}])
    dpo, kto = sets["pairs.tells.dpo.jsonl"], sets["examples.tells.kto.jsonl"]
    assert [p["meta"]["id"] for p in dpo] == ["a"]
    assert dpo[0]["chosen"][0]["content"] == '{"text": "you pocket it"}'
    assert [(k["meta"]["id"], k["label"]) for k in kto] == [
        ("a", False), ("a", True), ("b", False), ("b", False)]


@pytest.mark.parametrize("words,sentence,ok", [
    ("it remains on the tray", "The ring glints, but it remains on the tray.", True),
    ("remains", "It remains on the tray.", False),          # one word is no quote
    ("it stays put", "It remains on the tray.", False),     # not the sentence's own
    ("“six in the evening”", "You hang at six in the evening.", True),
])
def test_the_clash_must_be_quoted_from_the_sentence(words, sentence, ok):
    assert bv._clash_quoted(words, sentence) is ok

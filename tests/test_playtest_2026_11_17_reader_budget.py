"""The reader's prompt budget, and the reader and scope slips: playtest 2026-11-17 (Vesna
Kroll, 0.4.0, round 3) and N4/N5 of 2026-11-16.

Each test names the item and what the turn did. The lines are the playtest's own; the
scenes are rebuilt on the fixture world's Mirabalos, the city the save was played in.
"""
from __future__ import annotations

from gm import acts_to_ops, interpret, judgement, prompts
from rules import dungeons, fixtures, holding
from rules.dice import Dice
from rules.engine import Engine, Scene, reported_speech
from rules.sheet import load_pc
from world import loader

MIRABALOS = "7ef5e373c993"
WORLD = loader.load_cached("fixtures/pangrella-campaign.json")


class _Empty:
    """Dice under which nothing lives in a venture: every d100 comes up 100."""

    def __init__(self, real):
        self.real = real

    def __getattr__(self, name):
        return getattr(self.real, name)

    def roll(self, notation, modifiers=None, label="", visibility="hidden"):
        if notation == "1d100":
            return self.real.given(100, modifiers, label, notation)
        return self.real.roll(notation, modifiers, label, visibility)


def _city():
    s = Scene(location_id=MIRABALOS)
    s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, _Empty(Dice(seed=3)), world=WORLD)
    e.place_party()
    return s, e


def _run(e, *raws):
    intents = e.validate([{"actor": "pc", "because": "t", "visibility": "hidden", **r}
                          for r in raws], origin="author:test")
    return e.run(intents).outcomes


def _place(e, name):
    return next(p for p in e.places() if p.name == name)


# --- N4: the reader's prompt and its window -----------------------------------------------

# The worst characters-a-token a player's own world has measured on the shipped model
# (gm/window.py: "Their text ran about 3.2 characters a token").
WORST_RATIO = 3.2


def test_the_readers_prompt_fits_its_window_at_the_worst_measured_ratio():
    """N4: the reader's prompt was 50,142 characters against the client's 49,988-character
    budget (3.25 characters a token learned in play), so `window.fit` cut the first
    demonstration pair from the front on every reading, and said so only in a log line.
    Measured 2026-11-17 on the shipped model: 15,850 tokens of the 16,384 window, leaving
    534 for a 400-token reply. Every new demonstration must now pay for itself here."""
    budget = int((prompts.NUM_CTX - interpret.READ_TOKENS - prompts.SAFETY_TOKENS)
                 * WORST_RATIO)
    longest = "I " + "walk on " * 60          # a long line, as players write them
    size = sum(len(m["content"]) for m in interpret.messages(longest))
    assert size <= budget, (f"the reader's prompt is {size} characters, over its "
                            f"{budget}-character budget: trim a demonstration first")


def test_an_over_budget_reader_prompt_is_said_in_the_log(monkeypatch, caplog):
    """N4: the overflow was silent but for the client's generic cut line. The reader now
    says itself that its own demonstrations are being cut."""
    from gm import client, window

    monkeypatch.setattr(window, "prompt_budget_chars", lambda *a, **k: 1000)

    class _Reply:
        text = "{}"

        def json(self):
            return {"question": False, "actions": [], "claims": []}

    monkeypatch.setattr(client, "chat", lambda *a, **k: _Reply())
    with caplog.at_level("WARNING", logger="pathfindergm"):
        interpret.interpret("I sit down.", model="m", host="h")
    assert any("reader's prompt" in r.getMessage() for r in caplog.records), caplog.text


def test_demonstrations_are_compact_json():
    """N4: the spaces of ", " and ": " were 2,755 of the prompt's 15,850 tokens."""
    reply = interpret._demo_reply(interpret._DEMOS[0][1])
    assert ", " not in reply.replace('", "', "") and '": ' not in reply, reply[:120]


# --- #45: a stance is no deed -------------------------------------------------------------

def test_a_stance_phrase_read_as_a_thing_used_is_dropped():
    """#45: "Torch in one hand and dagger in the other, I go through into the beast's
    pool" came back `use`, object and span both the stance phrase; it was looked up as a
    thing, refused "There is no torch in one hand and dagger in the other here", and the
    page told her light and blade gone on the walk into the lair."""
    line = "Torch in one hand and dagger in the other, I go through into the beast's pool."
    raw = {"question": False, "actions": [
        {"act": "use", "object": "Torch in one hand and dagger in the other",
         "span": "Torch in one hand and dagger in the other"},
        {"act": "go", "place": "the beast's pool", "span": "I go through into the beast's pool"}]}
    frame, dropped = interpret.ground(raw, line)
    assert [a["act"] for a in frame["actions"]] == ["go"], frame
    assert any("no deed" in d for d in dropped), dropped
    # A use with words of its own stands: "light the torch".
    frame, _ = interpret.ground({"actions": [{"act": "use", "object": "the torch",
                                              "span": "light the torch"}]},
                                "I light the torch.")
    assert [a["act"] for a in frame["actions"]] == ["use"]


# --- #43: a door is no person -------------------------------------------------------------

def _shut_door():
    """The gardens' sewers entered and a room beyond with a stuck door, the party at its
    near side: the save's broken pen before the beast's pool."""
    s, e = _city()
    e.place_party(_place(e, "the gardens").id)
    _run(e, {"op": "venture", "params": {"kind": "sewers"}})
    here = s.at
    beyond = {"id": here + "/the-beasts-pool", "name": "the beast's pool", "parent": here,
              "origin": "dungeon", "kind": "pool",
              "dungeon": {"door": {"name": "a good wooden door", "state": "stuck",
                                   "force": 16}}}
    s.founded.append(beyond)
    return s, e, beyond


def test_a_shoulder_to_a_shut_door_is_the_door_forced_not_a_person_struck():
    """#43, T399: "I throw my shoulder against the door to the beast's pool again" was read
    `attack, target: the door to the beast's pool`; nobody answered to it, and the turn
    was an HTTP 422 "Nobody here answers to the door to the beast's pool" — while the same
    door forced in other words a turn earlier had worked."""
    s, e, beyond = _shut_door()
    assert dungeons.shut_door_named(s, "the door to the beast's pool") == "the beast's pool"
    assert dungeons.shut_door_named(s, "the stuck door") == "the beast's pool"
    assert dungeons.shut_door_named(s, "the toll-keeper") == ""
    frame = {"question": False, "actions": [
        {"act": "attack", "target": "the door to the beast's pool", "blow": "shove",
         "span": "throw my shoulder against the door to the beast's pool again"}]}
    rows = acts_to_ops.table(frame, s, places=e.places(), sentence="")
    assert [r.act for r in rows] == ["break_in"], [r.record() for r in rows]
    assert rows[0].ops == ["break_in"] and not rows[0].missing
    assert acts_to_ops.victims(rows, frame, s, ask=lambda *a: []) == []
    assert interpret.broken_into(frame) == ("the beast's pool", "force")
    # Opened, the door is no longer there to be named.
    beyond["dungeon"]["door"]["state"] = "open"
    assert dungeons.shut_door_named(s, "the door to the beast's pool") == ""


# --- #23: past somebody in plain sight ----------------------------------------------------

def test_a_sneak_at_somebody_beside_a_walk_is_asked_too():
    """#23, T367: "I step past the toll-keeper and go on into the turnkey's room" came back
    `stealth, target: the toll-keeper`; 0.4.0's question only asked a stealth with no
    target, so the Stealth ran and was refused for want of cover in plain sight."""
    frame = {"actions": [
        {"act": "stealth", "target": "the toll-keeper", "span": "step past the toll-keeper"},
        {"act": "go", "place": "the turnkey's room", "span": "go on into the turnkey's room"}]}
    asked = []

    def ask(span):
        asked.append(span)
        return "a way to go"

    assert interpret.unhidden(frame, ask=ask) == ["step past the toll-keeper"]
    assert [a["act"] for a in frame["actions"]] == ["go"]
    # Slipping past a sentry unseen is still the hiding it says.
    frame = {"actions": [
        {"act": "stealth", "target": "the sentry", "span": "slip past the sentry unseen"},
        {"act": "go", "place": "the yard", "span": "into the yard"}]}
    assert interpret.unhidden(frame, ask=lambda span: "hides") == []
    assert [a["act"] for a in frame["actions"]] == ["stealth", "go"]


# --- #14: down the grate after a walk -----------------------------------------------------

def test_down_into_the_venture_under_where_a_walk_ended_is_no_second_journey():
    """#14, T351: "head to the gardens, down the grate, and back through the culvert to the
    cells" walked to the gardens, and the planner's plain travels on into the sewers'
    rooms were both refused "One journey a turn"."""
    s, e = _city()
    e.place_party(_place(e, "the gardens").id)
    _run(e, {"op": "venture", "params": {"kind": "sewers"}})
    sewers = s.at
    inner = next(p for p in e.places() if p.parent == sewers)
    e.place_party(_place(e, "the great square").id)
    out = _run(e, {"op": "travel", "params": {"place": "the gardens"}},
               {"op": "travel", "params": {"place": inner.name}})
    assert all("One journey a turn" not in o.tell for o in out), [o.tell for o in out]
    assert s.at == inner.id, s.at
    # Two journeys elsewhere are still two.
    e.place_party(_place(e, "the gardens").id)
    out = _run(e, {"op": "travel", "params": {"place": "the great square"}},
               {"op": "travel", "params": {"place": "the cathedral"}})
    assert "One journey a turn" in out[-1].tell


# --- #36: the floor of a room is no open ground ------------------------------------------

def test_a_walk_across_a_room_with_nothing_near_is_not_open_ground():
    """#36, T385: in a row of prison cells the move tell said "moves 10 ft, out in open
    ground", and the page had her "step forward into the open ground" underground."""

    class _Grid:
        fixtures = [{"name": "the cot", "squares": [(9, 9)], "level": 0, "kind": "furniture"}]

        def ground(self, sq):
            return 0

    assert fixtures.where_said(_Grid(), (0, 0), (2, 0), indoors=True) == \
        "out in the middle of the floor"
    assert fixtures.where_said(_Grid(), (0, 0), (2, 0)) == "out in open ground"


# --- #4: thanks are a deed of speech ------------------------------------------------------

def test_thanking_somebody_is_told_as_thanks():
    """#4, T335: "I thank the priest…" was told "speaks to the priest of the cathedral, to
    the effect that thank the priest"."""
    assert reported_speech("Vesna Kroll", " to the priest", "thank the priest.") == \
        "Vesna Kroll thanks the priest."
    assert reported_speech("Vesna Kroll", "", "thank him") == "Vesna Kroll thanks him"
    assert "to the effect that" in reported_speech("Vesna", "", "the ship sails at dawn")


# --- #3 and N5: a quotation is quoted, once ----------------------------------------------

def test_a_piece_of_the_players_quotation_is_quoted_whole():
    """#3, T333: the plan's say was "I need healing. What will it cost?" of the player's
    "Father, I need healing. What will it cost?" — the address dropped, so it was not
    marked quoted, and the page retold it "asking what the cost will be"."""
    line = '"Father, I need healing. What will it cost?"'
    out = judgement.own_words_only(
        [{"op": "say", "params": {"words": "I need healing. What will it cost?", "to": "c29"}}],
        line)
    assert out[0]["params"] == {"words": "Father, I need healing. What will it cost?",
                                "to": "c29", "quoted": True}, out


def test_the_same_line_said_twice_is_said_once():
    """N5: on "Father, I'm badly hurt. Can you heal me? I can pay." the plan wrote two
    says, the whole line and "I can pay.", and the engine told it twice."""
    line = '"Father, I\'m badly hurt. Can you heal me? I can pay." I show him my coin.'
    notes: list = []
    out = judgement.own_words_only(
        [{"op": "say", "params": {"words": "Father, I'm badly hurt. Can you heal me? I can pay."}},
         {"op": "say", "params": {"words": "I'm badly hurt. Can you heal me? I can pay."}},
         {"op": "narrate_only", "params": {}}], line, notes=notes)
    assert [o["op"] for o in out] == ["say", "narrate_only"], out
    assert any("twice" in n for n in notes), notes
    # Two different lines to two people both stand.
    out = judgement.own_words_only(
        [{"op": "say", "params": {"words": "Wait here.", "to": "c1"}},
         {"op": "say", "params": {"words": "Come with me.", "to": "c2"}}],
        'I tell Ann "Wait here." and Bob "Come with me."')
    assert len(out) == 2


# --- #7: a trader knows the price ---------------------------------------------------------

def test_the_market_master_knows_what_the_partys_goods_fetch_here():
    """#7, T338: asked who buys silk by the bale and what it fetches, the master of the
    market named places and gave no price, though the trade code held one."""
    from gm import planned
    from rules import keepers
    from rules import trade as trade_mod

    s, e = _city()
    e.place_party(_place(e, "the market").id)
    key = next(k for k in trade_mod.ROWS if "silk" in trade_mod.ROWS[k][0].lower())
    trade_mod.add_lot(s, key, 40, "pc", 0, MIRABALOS)
    master = keepers.master_here(s)
    assert master is not None
    known = planned._goods_known(e, master, "the master of the market")
    assert known and "silk" in known[0] and "before any haggling" in known[0], known
    # Nobody else is handed the market's book.
    pc = s.pc()
    assert planned._goods_known(e, pc, "you") == []


# --- #16: the table is held to the sheet -------------------------------------------------

def test_what_the_player_carries_is_a_fact_the_table_talk_is_read_against():
    """#16, T355: over a wrong refusal ("There is no one of my torches here") the table
    said "You don't have any torches in your pack" while she had three; the read had no
    sheet to hold it to."""
    from play import table_talk

    s, e = _city()
    s.pc().goods["torch"] = 3

    class _C:
        scene = s
        turn_log: list = []

    _said, checked = table_talk.scene_facts(_C())
    assert "torch" in holding.carried_list(s.pc())
    assert any("carries" in line and "torch" in line for line in checked), checked

"""The watcher's background calls answer small, once, and are capped at what they ask for.

Measured 2026-10-08. The player's log had four watcher calls at their 900-token cap on
prompts of only 824 to 844 tokens, each discarded and asked again. Reproduced with the
real prompts on the shipped model (igorls/gemma-4-12B-it-heretic): `_ask` led the cards
and the undercurrent calls with `think` unsent, Gemma 4 thinks by default, and all 900
tokens went into the thinking channel, 4 calls of 4: `done_reason=length`, content "",
19 to 21 s each, then a second call. With `think=False` the same calls answered in 35 to
43 tokens, `done_reason=stop`, 4 of 4.

And the log's one watcher-sized call of 8,195 tokens is the signature of a prompt too
long for the window: Ollama keeps about half of a 16,384 window when one message alone
overflows it (208,663 characters came back as 8,195, measured the same day). The cards
look sent every live card and every actor in the scene, and neither list stops growing.
"""
from __future__ import annotations

import pytest

from gm import client, watcher


class _Reply:
    def __init__(self, text='{"item": "a tarnished locket", "band": "modest"}',
                 done="stop", tokens=18):
        self.text, self.done_reason, self.reply_tokens = text, done, tokens
        self.seconds, self.model = 0.1, "fake"

    @property
    def cut_off(self):
        return self.done_reason == "length"

    def json(self):
        import json
        return json.loads(self.text)


CFG = {"model": "gemma", "host": "http://localhost:11434"}
GARNISH_SCHEMA = {"type": "object",
                  "properties": {"item": {"type": "string", "maxLength": 80},
                                 "band": {"type": "string", "enum": sorted(watcher.BANDS)}},
                  "required": ["item", "band"]}


def _record(monkeypatch, replies):
    asked = []

    def chat(messages, model, host, **kw):
        asked.append(kw)
        r = replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(watcher.client, "chat", chat)
    return asked


def test_every_look_leads_with_thinking_off_and_a_cap_sized_to_its_answer(monkeypatch):
    """Thinking on spent the whole 900 tokens 4 of 4 on the shipped model; the answers
    themselves were 18 to 43 tokens."""
    for job, fn in ((_garnish_job(), watcher._propose_garnish),
                    (_undercurrent_job(), watcher._propose_undercurrent),
                    (_cards_job(cards=3), watcher._propose_cards)):
        asked = _record(monkeypatch, [_Reply('{"x": 1}')])
        fn(job, CFG)
        assert asked[0]["think"] is False
        assert asked[0]["num_predict"] < 900 or fn is watcher._propose_cards
        assert len(asked) == 1


def test_a_reply_cut_at_its_cap_is_not_asked_again(monkeypatch):
    """It was: one look became two full-length calls, the second as doomed as the first."""
    asked = _record(monkeypatch, [_Reply("", done="length", tokens=105), _Reply()])
    with pytest.raises(watcher.RanAway):
        watcher._ask([{"role": "user", "content": "x"}], CFG, GARNISH_SCHEMA)
    assert len(asked) == 1


def test_a_model_that_refuses_the_think_key_is_asked_once_without_it(monkeypatch):
    asked = _record(monkeypatch, [client.ModelUnavailable("HTTP Error 400"), _Reply()])
    assert watcher._ask([{"role": "user", "content": "x"}], CFG, GARNISH_SCHEMA)["band"]
    assert [a["think"] for a in asked] == [False, None]


def test_a_wedged_ollama_is_not_asked_twice(monkeypatch):
    asked = _record(monkeypatch, [client.ModelStalled("stalled"), _Reply()])
    with pytest.raises(client.ModelStalled):
        watcher._ask([{"role": "user", "content": "x"}], CFG, GARNISH_SCHEMA)
    assert len(asked) == 1


def test_the_caps_are_read_from_the_schema_and_fit_the_largest_answer():
    """The garnish's largest answer is about 140 characters; the cap was 900 tokens."""
    longest = watcher.max_answer_chars(GARNISH_SCHEMA)
    assert 100 < longest < 200
    assert watcher.answer_tokens(longest) < 150
    assert watcher.max_answer_chars({"type": "string"}) is None
    assert watcher.max_answer_chars({"type": "array", "items": {"type": "string",
                                                                 "maxLength": 5}}) is None


def test_the_cards_answer_is_bounded_by_the_cards_shown():
    """`changes` had no maxItems, `id` was any string, a new card any number of facts
    and people: nothing but the token cap bounded the answer."""
    job = _cards_job(cards=3, refs=4)
    schema = watcher.cards_schema(job)
    changes = schema["properties"]["changes"]
    assert changes["maxItems"] == 3
    assert changes["items"]["properties"]["id"]["enum"] == [k["id"] for k in job["cards"]]
    new = schema["properties"]["new"]["properties"]
    assert new["facts"]["maxItems"] == 3
    assert set(new["people"]["items"]["enum"]) == set(job["refs"])
    assert watcher.max_answer_chars(schema) is not None


def test_a_string_the_grammar_cut_at_its_cap_is_refused_not_kept():
    """Ollama enforces maxLength by stopping the string mid-word at exactly the cap
    (probed 3 of 3: "As the first grey light of dawn creeps o"). The undercurrent's cap
    was 300, the same as its validator's limit, so a sentence cut mid-word was kept."""
    known = frozenset()
    cut = "a" * 18 + " " + "word " * 100
    assert watcher._valid_thread({"action": "advance",
                                  "sentence": cut[:watcher.THREAD_LEN + 20]}, known) is None
    assert watcher._valid_fact(cut[:watcher.FACT_LEN[1] + 20], known) is None
    assert watcher._valid_garnish({"item": "x" * 80, "band": "modest"}, known) is None


def test_the_cards_look_shows_a_bounded_deck_and_cast(tmp_path, monkeypatch):
    """Thirty live cards and two hundred people on the board, as a long campaign makes:
    the look is shown the most recently touched cards and a capped list of people."""
    from django.test import override_settings

    from play import campaign as cm
    from rules import cards
    from rules.bestiary import instantiate
    from rules.sheet import load_pc

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        watcher._reset()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        watcher._jobs_for(c)                       # first sight
        for n in range(200):
            c.scene.add(instantiate("guildhand", scene=c.scene, name=f"hand {n}"),
                        zone="near")
        for n in range(30):
            cards.open_card(c.scene, cards.Card(id=f"k{n}", title=f"Matter number {n}",
                                                facts=["It is still open."],
                                                origin="author:test"), turn=n)
        for _ in range(watcher.CARD_TURNS_BETWEEN_LOOKS + 1):
            c.turn_log.append({"kind": "turn"})
        job = next(j for j in watcher._jobs_for(c) if j["job"] == "cards")
    assert len(job["cards"]) == watcher.MAX_CARDS
    assert len(job["refs"]) <= watcher.MAX_REFS
    asked = []
    monkeypatch.setattr(watcher.client, "chat",
                        lambda m, *a, **k: asked.append(m) or _Reply('{"changes": [], "new": null}'))
    watcher._propose_cards(job, CFG)
    chars = sum(len(m["content"]) for m in asked[0])
    assert chars < 12000, f"{chars} characters for one look at the cards"


# --- jobs ------------------------------------------------------------------------------

def _garnish_job():
    return {"job": "garnish", "campaign": "x", "ref": "c3", "who": "the bandit",
            "snapshot": {}, "thread": "", "cast": ["Mira", "the bandit"],
            "known": frozenset({"Mira"})}


def _undercurrent_job():
    return {"job": "undercurrent", "campaign": "x", "was": "", "thread": "",
            "recent": ["player: I look around."], "hooks": [], "known": frozenset()}


def _cards_job(cards=3, refs=2):
    return {"job": "cards", "campaign": "x", "turn": 4, "known": frozenset(),
            "refs": {f"c{n}": f"person {n}" for n in range(refs)},
            "recent": ["player: I look around."],
            "cards": [{"id": f"k{n}", "title": f"Matter {n}", "facts": ["Open."],
                       "kind": "situation", "objectives": [], "stage": "open",
                       "clock": 0, "secret": False, "people": []} for n in range(cards)]}

"""The turn prompt fits the window, and we are the ones who decide what goes.

Measured 2026-09-08 on the shipped Pangrella export, simulating Ollama's own
`chatPrompt` rule against the real assembled prompt:

  * the history was an unbounded list that nothing trimmed, and the whole of it was
    passed to the model every turn;
  * the prompt passed the 16,384-token window at **turn 46** out of combat;
  * Ollama then dropped messages from the front, taking the worked examples first —
    all 24 of them gone by **turn 57** — and one exchange of real play per turn after
    that, for the rest of the campaign;
  * nothing was reported to the caller. The only trace was a debug line in Ollama's
    own server log.

So the first symptom of a full window was not the game forgetting, it was the prose
falling apart, because the demonstrations went before any play did. These tests pin
that we cut instead, in a stated order, and that we say what we cut.
"""
import json

from gm import prompts


def _exchange(n: int, beat: int = 850):
    return [{"role": "user", "content": f"I ask the trader about seal {n}"},
            {"role": "assistant", "content": "x" * beat}]


def _history(turns: int):
    out = []
    for n in range(turns):
        out += _exchange(n)
    return out


def _chars(messages):
    return sum(len(m.get("content") or "") for m in messages)


def test_two_hundred_turns_still_fit_the_budget():
    """At turn 46 the old code handed the server a prompt it had to cut itself."""
    brief = "HERE: the market.\n" + ("a fact about this place\n" * 40)
    for turns in (10, 46, 60, 120, 200):
        report: dict = {}
        messages = prompts.call_one_messages(
            brief, _history(turns), "I ask him who checks the seals", report=report)
        assert _chars(messages) <= prompts.PROMPT_BUDGET_CHARS, (
            f"{turns} turns built a {_chars(messages):,}-char prompt against a "
            f"{prompts.PROMPT_BUDGET_CHARS:,} budget")


def test_the_player_line_and_the_briefing_always_survive():
    """Whatever else goes, the turn is still a turn: who is asking, and the rules."""
    for turns in (0, 46, 200, 500):
        messages = prompts.call_one_messages(
            "HERE: the market.", _history(turns), "I draw the seal from my satchel")
        assert messages[0]["role"] == "system"
        assert "HERE: the market." in messages[0]["content"]
        assert messages[-1] == {"role": "user",
                                "content": "I draw the seal from my satchel"}


def test_a_kept_stretch_never_opens_on_a_reply():
    """Ollama counts messages, not exchanges, and cuts between a question and its
    answer — leaving a reply with nothing it was replying to. We never do."""
    history = _history(200)
    messages = prompts.call_one_messages("HERE: the market.", history, "I ask again")
    kept = [m for m in messages[1:-1] if m["content"] not in
            {json.dumps(e["reply"]) for e in prompts.EXAMPLES}]
    # The first thing after the examples that came out of the history is a player line.
    tail_of_history = [m for m in messages if m.get("content", "").startswith("I ask the trader")]
    first = messages.index(tail_of_history[0]) if tail_of_history else None
    assert first is not None
    assert messages[first]["role"] == "user"
    assert kept, "the whole history was dropped"


def test_the_newest_turns_outlast_the_worked_examples():
    """The cut order, where it actually bites. A model that has lost the thread
    writes a well-formed wrong scene, so the last few turns rank above the examples."""
    head = [{"role": "system", "content": "brief"}]
    examples = [{"role": "user", "content": "e" * 400},
                {"role": "assistant", "content": "e" * 400}]
    history = _history(20)
    tail = [{"role": "user", "content": "now"}]

    # A budget with room for the recent turns but not for the examples as well.
    report: dict = {}
    packed = prompts.pack(head, examples, history, tail, budget=3200, report=report)
    assert report["examples"] is False, "the examples should go before the newest turns"
    assert packed[-1] == tail[0]
    assert history[-1] in packed, "the most recent beat was cut before the examples"


def test_the_examples_survive_when_only_old_history_has_to_go():
    head = [{"role": "system", "content": "brief"}]
    examples = [{"role": "user", "content": "e" * 200},
                {"role": "assistant", "content": "e" * 200}]
    report: dict = {}
    packed = prompts.pack(head, examples, _history(40), [{"role": "user", "content": "now"}],
                          budget=6000, report=report)
    assert report["examples"] is True
    assert report["dropped"] > 0
    assert examples[0] in packed


def test_the_cut_is_reported():
    """A cut nobody records is the failure this whole function exists to end."""
    report: dict = {}
    prompts.call_one_messages("HERE: the market.", _history(200), "I ask again",
                              report=report)
    assert report["dropped"] > 0
    assert report["kept"] > 0
    assert report["budget"] == prompts.PROMPT_BUDGET_CHARS

    quiet: dict = {}
    prompts.call_one_messages("HERE: the market.", _history(2), "I ask again",
                              report=quiet)
    assert quiet["dropped"] == 0


def test_the_prose_call_fits_too_with_its_tells_and_earlier_beats():
    """The second call grows its own head and tail, and used to grow them AFTER the
    budget had already decided the prompt fitted: `call_prose_messages` built the turn
    prompt and then replaced the system message and the final user message with larger
    ones, so the tells and up to two earlier beats arrived behind the check."""
    messages = prompts.call_prose_messages(
        "HERE: the market.", _history(200), "I ask him who checks the seals",
        tells=[f"The engine decided thing number {n}" for n in range(40)],
        earlier=["y" * 4000, "z" * 4000])
    assert _chars(messages) <= prompts.PROMPT_BUDGET_CHARS, (
        f"the prose prompt was {_chars(messages):,} chars against a "
        f"{prompts.PROMPT_BUDGET_CHARS:,} budget")
    assert "What the engine decided" in messages[-1]["content"]
    assert prompts.PROSE_AFTER_EXTRA.strip()[:40] in messages[0]["content"]


def test_the_intents_only_call_fits_too():
    messages = prompts.call_one_intents_only(
        "HERE: the market.", _history(200), "I ask again")
    assert _chars(messages) <= prompts.PROMPT_BUDGET_CHARS


def test_the_window_is_named_once():
    """Two copies of a constant is the trap CLAUDE.md names, and this one would fail
    silently: a prompt budgeted for one window, sent to another."""
    from gm import client

    assert client.prompts.NUM_CTX is prompts.NUM_CTX
    src = (client.__file__ or "")
    assert src
    with open(src, encoding="utf-8") as fh:
        assert "16384" not in fh.read(), "the window is written down twice"


def test_the_budget_leaves_the_model_room_to_answer():
    """gm/client.py's own comment records the other way this fails: a 4,086-token
    prompt against a 4,096-token window died mid-sentence on every turn of a live
    scene, because the window holds the answer as well as the question."""
    spare = prompts.NUM_CTX - (prompts.PROMPT_BUDGET_CHARS / prompts.CHARS_PER_TOKEN)
    assert spare >= prompts.MAX_COMPLETION_TOKENS

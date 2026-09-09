"""What happened in the turns the context budget cut.

Before this, a campaign could run past turn 46, the oldest exchanges would leave the
prompt, and nothing anywhere remembered they had happened — see
`tests/test_prompt_budget.py` for that measurement.

Three rules, each with a reason that is not a preference, and each pinned here:

  * built from the engine's own outcomes, so it cannot invent anything;
  * written once and never re-summarised, because the one direct comparison available
    puts recursive summarisation last of every approach measured (35.3% against 94.4%
    for full context) and names repeated re-compression as the cause;
  * no numbers at all, because an entry disagreeing with the sheet is the stale
    near-miss that the retrieval literature measures as the most damaging thing you
    can put in a prompt (56.4% down to 45.9% from one related-but-wrong passage,
    while wholly irrelevant text did no harm).
"""
from gm import ledger, prompts
from play import campaign as C
from rules.dice import Dice
from rules.engine import Engine


def _entry(text, hist, turn=0, at="the market"):
    return {"turn": turn, "hist": hist, "at": at, "text": text}


def test_an_entry_is_built_from_what_the_engine_decided():
    c = C.new_campaign("slice", seed=7)
    eng = c.engine()
    out = eng.run(eng.validate([{
        "op": "quest", "because": "the errand",
        "params": {"title": "The export seals", "objectives": ["find the stamp"]}}]))
    entry = ledger.note(out.outcomes, turn=3, hist=6, where="the market",
                        names={r: a.name for r, a in c.scene.actors.items()})
    assert entry is not None
    assert "The export seals" in entry["text"]
    assert entry["hist"] == 6


def test_no_number_ever_reaches_the_ledger():
    """The second law: an entry carrying a number is a parallel store of a fact the
    engine already holds, and the prompt then carries two versions of it."""
    c = C.new_campaign("slice", seed=7)
    eng = c.engine()
    out = eng.run(eng.validate([{
        "op": "quest", "because": "x",
        "params": {"title": "The 3 seals of Oorvieth", "objectives": ["a"]}}]))
    entry = ledger.note(out.outcomes, turn=1, hist=2, where="the market")
    assert entry is not None
    assert not any(ch.isdigit() for ch in entry["text"]), entry["text"]


def test_a_turn_worth_nothing_is_remembered_as_nothing():
    """A Perception check is not a thing worth carrying forty turns. A ledger that
    records everything is a second transcript, not a memory."""
    scene = C.new_campaign("slice", seed=7).scene
    eng = Engine(scene, Dice(seed=1))
    out = eng.run(eng.validate([{"op": "narrate_only", "because": "quiet", "params": {}}]))
    assert ledger.note(out.outcomes, turn=1, hist=2) is None


def test_a_run_of_identical_entries_collapses():
    """Ten of ten paragraphs ending the same way is this project's oldest measured
    smell, and a ledger is the cheapest place in the app to spend the whole budget
    saying one thing over and over."""
    entries: list[dict] = []
    for n in range(6):
        ledger.keep(entries, _entry("you spoke with the clerk", hist=n * 2))
    assert len(entries) == 1
    assert entries[0]["hist"] == 10, "the collapsed entry keeps the latest position"

    ledger.keep(entries, _entry("you went to the approach", hist=12))
    assert len(entries) == 2


def test_the_ledger_holds_a_cap():
    entries: list[dict] = []
    for n in range(ledger.ENTRY_CAP + 50):
        ledger.keep(entries, _entry("you went to place " + chr(97 + n % 26) + "x" * (n // 26), hist=n))
    assert len(entries) == ledger.ENTRY_CAP


def test_the_block_only_covers_turns_the_window_no_longer_carries():
    """A fact in the prompt twice is the parallel store the second law forbids. The
    ledger's `hist` and the packer's `dropped` are counted in the same units — history
    messages — so the boundary is exact rather than approximate."""
    entries = [_entry("you went to the approach", hist=4),
               _entry("you sold to the trader", hist=20)]
    early = ledger.block(entries, before_hist=10)
    assert "approach" in early
    assert "trader" not in early, "an entry still present verbatim was repeated"

    assert ledger.block(entries, before_hist=0) == ""


def test_the_block_keeps_the_most_recent_of_the_forgotten_turns():
    """Newest first while the budget lasts, then back into reading order."""
    entries = [_entry(f"you went to place {n}".replace(str(n), "abcdefgh"[n]), hist=n)
               for n in range(8)]
    out = ledger.block(entries, before_hist=100, budget=90)
    assert out.count("  * ") < 8, "the budget was not enforced"
    assert "place h" in out, "the newest forgotten turn was the first to be dropped"


def test_the_ledger_reaches_the_prompt_and_the_prompt_still_fits():
    history, entries = [], []
    for n in range(60):
        history += [{"role": "user", "content": f"I ask about seal {n}"},
                    {"role": "assistant", "content": "x" * 850}]
        ledger.keep(entries, _entry(f"you went to place {'abcdefghij'[n % 10]}",
                                    hist=len(history), turn=n))
    report: dict = {}
    messages = prompts.call_one_messages(
        "HERE: the market.", history, "I ask again", report=report, ledger=entries)
    total = sum(len(m.get("content") or "") for m in messages)
    assert total <= prompts.PROMPT_BUDGET_CHARS
    assert report["dropped"] > 0
    assert report["remembered"] > 0
    assert "EARLIER" in messages[0]["content"], "the ledger never reached the prompt"


def test_a_call_with_no_history_gets_the_whole_ledger():
    """The prose call is handed `[]` by design, so nothing is present verbatim and the
    whole ledger is outside its window. Counting only what was 'dropped' would give it
    an empty memory on the one call that actually writes the page."""
    entries = [_entry("you went to the approach", hist=40)]
    messages = prompts.call_prose_messages(
        "HERE: the market.", [], "I look around", tells=["The road is quiet."],
        ledger=entries)
    assert "approach" in messages[0]["content"]


def test_the_campaign_saves_and_reloads_its_ledger(tmp_path, settings):
    settings.CAMPAIGN_DIR = str(tmp_path)
    c = C.new_campaign("slice", seed=7)
    ledger.keep(c.ledger, _entry("you went to the approach", hist=4))
    c.save()
    back = C.Campaign.load(c.path())
    assert [e["text"] for e in back.ledger] == ["you went to the approach"]


def test_what_was_said_is_kept_in_the_players_own_words():
    """docs/memory-policy.md reserved one model call at eviction for exactly this — the
    part the engine does not own. Once speech had an op, the call became unnecessary:
    the words are in an effect the engine wrote. A promise made forty turns ago is the
    most useful thing a ledger can hold and the thing a summariser would most likely
    have got wrong."""
    c = C.new_campaign("slice", seed=7)
    eng = c.engine()
    eng.run(eng.validate([{"op": "spawn", "because": "the stall",
                           "params": {"template": "guildhand", "count": 1,
                                      "name": "the clerk"}}]))
    from gm import judgement

    raw = judgement.inject_say(
        [], 'I tell the clerk "I will bring the jar back before the gate shuts"',
        c.scene)
    out = eng.run(eng.validate(raw))
    entry = ledger.note(out.outcomes, turn=9, hist=18, spoke_with="the clerk",
                        where="the market",
                        names={r: a.name for r, a in c.scene.actors.items()})
    assert "bring the jar back" in entry["text"]
    # And only once. With the fallback firing as well it read "you spoke with the
    # clerk, told the clerk, ..." — the same fact twice, in the one place built to
    # keep a fact from appearing twice.
    assert entry["text"].count("the clerk") == 1, entry["text"]

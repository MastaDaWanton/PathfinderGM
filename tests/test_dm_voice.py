"""The GM at the table: table talk under a beat and `/gm` answers in the GM's own voice.

The owner, 2026-11-05, writing a ruling on the GM's Rulings page: "[I knock my knuckles
against the table, pointing right at you.] Bold move. Roll an Intimidate check!" — and then,
of the existing `/gm`: "it's not JSON but it doesn't feel like asking your GM". The answers
were two to five sentences of plain prose behind a "The GM, out of character:" label, and the
engine's own answers were a printout ("WHERE: … id: …").

What these tests hold is what keeps a voice honest, each from a defect measured somewhere in
this project before:

* it hears only what the player saw: no creature's roll, no hidden die, no DC;
* no model authors a number (the third law), and a retold record keeps every number it had;
* no name the moment never used (World Bible's "ground every name");
* no copied example and no repeated action: the worst tic this project ever measured was
  its own template (docs/narrator-guards.md), and Friends & Fables' players keep a list of
  its GM's favourite things;
* it is never in the narrator's history and never a `who: "gm"` beat, which a dozen readers
  feed back to the narrator.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from gm import client as gm_client
from gm.client import ModelUnavailable
from play import table_talk as tt
from rules import houserules
from rules.dice import Roll
from rules.engine import Outcome


# --- the voices ------------------------------------------------------------------------

def test_the_voices_file_and_the_house_rule_name_the_same_gms():
    """Settings validates `dm_voice` against `houserules.DM_VOICES` without reading content;
    a voice in one list and not the other is a card that can be pressed and never held."""
    assert tuple(tt.voices()) == houserules.DM_VOICES
    for v in tt.voices().values():
        for key in ("name", "blurb", "manner", "never", "examples", "ooc_examples"):
            assert v.get(key), f"{v['id']} has no {key}"
        assert len(v["examples"]) >= 4 and len(v["ooc_examples"]) >= 2


def test_no_example_carries_a_name_or_a_number_a_gm_could_copy_into_another_world():
    """An example's names travel: "Two out of nine, Kesst" taught to a GM in somebody else's
    game is a name from the wrong world on the page. Examples speak to "you"."""
    for v in tt.voices().values():
        for ex in v["examples"] + v["ooc_examples"]:
            said = ex["said"]
            assert not any(ch.isdigit() for ch in said), said
            for name in ("Kesst", "Borin", "Thessaly", "Delyth", "Sootspar", "Aldric"):
                assert name not in said, said


def test_most_examples_open_without_an_action():
    """The shape of a demonstration becomes the shape of the output (CLAUDE.md): five
    examples all opening "[I grin.]" would teach a GM that grins every turn."""
    for v in tt.voices().values():
        opened = sum(ex["said"].startswith("[") for ex in v["examples"])
        assert opened * 2 <= len(v["examples"]), f"{v['id']}: {opened} of {len(v['examples'])}"


def test_both_settings_are_written_and_read_back(tmp_path):
    rules, problems = houserules.set_active({"table_talk": "always", "dm_voice": "dry"})
    assert not problems
    assert houserules.active()["table_talk"] == "always"
    assert houserules.table_talk() == "always"
    assert houserules.dm_voice() == "dry"
    _, problems = houserules.set_active({"table_talk": "sometimes", "dm_voice": "angry"})
    assert any("table talk" in p for p in problems)
    assert any("GM voice" in p for p in problems)
    assert houserules.dm_voice() == "dry", "a refused value must not move the setting"


def test_settings_offers_every_voice_by_name():
    cards = tt.voice_cards()
    assert [c["id"] for c in cards] == list(houserules.DM_VOICES)
    assert all(c["name"] and c["blurb"] for c in cards)


# --- what it hears ---------------------------------------------------------------------

@pytest.fixture
def camp():
    from play import campaign as C

    c = C.new_campaign("slice", seed=7)
    eng = c.engine()
    eng.run(eng.validate([{"op": "spawn", "because": "the cellar",
                           "params": {"template": "guildhand", "count": 1,
                                      "name": "the clubman"}}]))
    return c


def _pc_ref(c):
    return tt._pc_ref(c.scene)


def _foe_ref(c):
    return next(r for r, a in c.scene.people.items() if not a.is_pc)


def test_only_the_players_outcomes_reach_it_and_never_a_creatures(camp):
    pc, foe = _pc_ref(camp), _foe_ref(camp)
    res = SimpleNamespace(outcomes=[
        Outcome("i1", "attack", actor=foe, tell="the clubman swings at you and misses",
                rolls=[Roll("1d20", [20], label="attack", visibility="hidden")]),
        Outcome("i2", "check", actor=pc, tell="You shove him into the rack (14 against 12).",
                verdict="success"),
    ])
    kinds, facts = tt.moments(camp, res)
    said = " ".join(facts)
    assert "clubman swings" not in said, "a creature's outcome is not the player's to hear"
    assert "natural" not in said, "a creature's hidden twenty is a secret"
    assert "14" not in said and "12" not in said, "the arithmetic is the engine's (plain_tell)"
    assert "shove him into the rack" in said


def test_a_bonus_for_how_it_was_done_is_said_with_its_reason_and_never_its_number(camp):
    pc = _pc_ref(camp)
    res = SimpleNamespace(outcomes=[Outcome(
        "i1", "check", actor=pc, tell="You talk your way past the gate.",
        dc={"value": 15, "circumstance": 2, "circumstance_why": "you wear the guild's colours"},
        rolls=[Roll("1d20", [20], label="Bluff", visibility="player")])])
    kinds, facts = tt.moments(camp, res)
    assert "bend" in kinds and "natural" in kinds
    said = " ".join(facts)
    assert "you wear the guild's colours" in said
    assert "15" not in said
    assert tt.wanted(kinds, facts, "big")


def test_a_refusal_is_a_big_moment_and_an_ordinary_step_is_not(camp):
    pc = _pc_ref(camp)
    refused = SimpleNamespace(outcomes=[Outcome(
        "i1", "cast", status="refused", actor=pc, tell="no such spell",
        for_a_person="You don't know a spell called fireball. Nothing is rolled.")])
    kinds, facts = tt.moments(camp, refused)
    assert kinds == ["refused"] and tt.wanted(kinds, facts, "big")
    plain = SimpleNamespace(outcomes=[Outcome("i2", "move", actor=pc,
                                              tell="You cross to the bar.")])
    kinds, facts = tt.moments(camp, plain)
    assert not tt.wanted(kinds, facts, "big")
    assert tt.wanted(kinds, facts, "always")
    assert not tt.wanted(kinds, facts, "off")


def test_the_player_going_down_is_said_once_not_every_turn_after(camp):
    pc = camp.scene.pc()
    pc.hp = -1
    nothing = SimpleNamespace(outcomes=[])
    kinds, _ = tt.moments(camp, nothing)
    assert "you_down" in kinds
    kinds, _ = tt.moments(camp, nothing)
    assert "you_down" not in kinds


# --- the checks ------------------------------------------------------------------------

def test_a_line_with_a_number_is_dropped():
    """The third law: no model authors a number. A GM saying "that's a 17" has made one up."""
    line, why = tt.check("Nice, that's a 17 against her.", "", [])
    assert not line and why == "a number"


def test_a_name_the_moment_never_used_is_dropped():
    allowed = "What happened: You shove Ruk Halloran's captor into the rack."
    assert tt.check("Ruk owes you one now.", allowed, [])[0]
    line, why = tt.check("I bet Mirabel saw that.", allowed, [])
    assert not line and "Mirabel" in why


def test_a_copied_example_is_dropped():
    copied = tt.voices()["dry"]["examples"][2]["said"]
    line, why = tt.check(copied, "", [])
    assert not line and why == "copied an example"


def test_a_repeated_action_is_cut_and_the_words_kept():
    recent = ["[I lean back and grin.] That worked."]
    line, why = tt.check("[I lean back, grinning.] Clever use of the rack.", "", recent)
    assert line == "Clever use of the rack.", line


def test_a_repeated_line_is_dropped():
    recent = ["That one is going in the stories."]
    line, why = tt.check("Oh, that one is going in the stories!", "", recent)
    assert not line and why == "repeats a recent line"


def test_tidy_keeps_one_action_two_sentences_and_no_speaker_label():
    said = tt.tidy('GM: "[I laugh.] Bold. Very bold. [I wink.] Roll it."')
    assert said == "[I laugh.] Bold. Very bold.", said


# --- after the beat --------------------------------------------------------------------

def _agent():
    return SimpleNamespace(prose_model="m", prose_host="h", prose_provider="ollama",
                           prose_key="", _intimate_beat=lambda: False)


def _refusal(c):
    return SimpleNamespace(outcomes=[Outcome(
        "i1", "cast", status="refused", actor=_pc_ref(c), tell="no such spell",
        for_a_person="You have no spell called fireball. Nothing is rolled.")])


def test_table_talk_goes_on_the_page_and_never_into_the_history(camp, monkeypatch):
    houserules.set_active({"table_talk": "big"})
    asked = []

    def fake(messages, *a, **k):
        asked.append(messages)
        return SimpleNamespace(text="[I laugh.] No fireball spell in your book, friend. "
                                    "Grab a torch.")

    monkeypatch.setattr(gm_client, "chat", fake)
    history = list(camp.history)
    camp.transcript.append({"who": "player", "text": "I cast fireball"})
    tt.after_the_beat(camp, _agent(), _refusal(camp))
    last = camp.transcript[-1]
    assert last["who"] == "table" and last["kind"] == "table"
    assert last["text"].startswith("[I laugh.]")
    assert camp.history == history
    # What it was asked holds the moment and nothing behind the screen.
    ask = asked[0][-1]["content"]
    assert "fireball" in ask and "Nothing is rolled" in ask
    # The voice's own examples ride as earlier turns.
    assert sum(m["role"] == "assistant" for m in asked[0]) == len(tt.voice()["examples"])


def test_off_asks_nothing(camp, monkeypatch):
    houserules.set_active({"table_talk": "off"})
    monkeypatch.setattr(gm_client, "chat", lambda *a, **k: pytest.fail("off must not ask"))
    n = len(camp.transcript)
    tt.after_the_beat(camp, _agent(), _refusal(camp))
    assert len(camp.transcript) == n


def test_a_dropped_line_leaves_nothing_on_the_page_and_says_why_in_the_scene(camp, monkeypatch):
    houserules.set_active({"table_talk": "big"})
    monkeypatch.setattr(gm_client, "chat",
                        lambda *a, **k: SimpleNamespace(text="That's a 3. Ouch."))
    n = len(camp.transcript)
    tt.after_the_beat(camp, _agent(), _refusal(camp))
    assert len(camp.transcript) == n
    assert camp.scene.said["table:log"][-1]["dropped"] == "a number"


def test_no_model_costs_the_turn_nothing(camp, monkeypatch):
    houserules.set_active({"table_talk": "always"})

    def down(*a, **k):
        raise ModelUnavailable("Ollama is not running")

    monkeypatch.setattr(gm_client, "chat", down)
    n = len(camp.transcript)
    tt.after_the_beat(camp, _agent(), _refusal(camp))
    assert len(camp.transcript) == n


def test_the_finish_of_every_turn_calls_it_after_the_world_has_answered():
    """`_finish` is the one place say, roll, combat, cast and the benches end a turn; the
    talk comes after the creatures' turns and the death check, so it reacts to the whole
    turn, and before the save, so it is on disk with the beat."""
    import ast
    from pathlib import Path

    # Walked as a syntax tree, not read as text (tests/test_suite_isolation.py's ceiling on
    # source pins): the line each call in `_finish` sits on, in order.
    tree = ast.parse(Path(__file__).resolve().parent.parent.joinpath(
        "play", "views.py").read_text(encoding="utf-8"))
    finish = next(n for n in tree.body
                  if isinstance(n, ast.FunctionDef) and n.name == "_finish")
    lines: dict[str, list[int]] = {}
    for node in ast.walk(finish):
        if isinstance(node, ast.Call):
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
            lines.setdefault(name, []).append(node.lineno)
    talk = lines["after_the_beat"][0]
    assert max(lines["_run_npc_turns"]) < talk
    assert max(lines["_the_player_died"]) < talk
    assert any(n > talk for n in lines["save"]), "the talk is on disk with the beat"


# --- /gm in the GM's voice ------------------------------------------------------------

RECORD = "ME: Kesst Vayr, 2/9 hit points.\n  id: c0\n  conditions: none"


def test_a_short_record_is_retold_and_must_keep_every_number(camp, monkeypatch):
    houserules.set_active({"table_talk": "big"})
    monkeypatch.setattr(gm_client, "chat", lambda *a, **k: SimpleNamespace(
        text="[I glance at your sheet.] Kesst Vayr, you're on 2 of 9 hit points."))
    entry = tt.voiced_record(camp, "how am i doing", RECORD)
    assert entry["voiced"] and entry["record"] == RECORD
    assert "2 of 9" in entry["text"]


def test_a_retelling_that_moves_a_number_gives_the_plain_record(camp, monkeypatch):
    monkeypatch.setattr(gm_client, "chat", lambda *a, **k: SimpleNamespace(
        text="Kesst Vayr, you're on 3 of 9 hit points."))
    entry = tt.voiced_record(camp, "how am i doing", RECORD)
    assert entry == {"who": "gm", "kind": "aside", "text": RECORD}


def test_a_retelling_that_drops_a_name_gives_the_plain_record(camp, monkeypatch):
    monkeypatch.setattr(gm_client, "chat", lambda *a, **k: SimpleNamespace(
        text="You're on 2 of 9 hit points."))
    entry = tt.voiced_record(camp, "how am i doing", RECORD)
    assert "voiced" not in entry


def test_a_long_record_is_handed_over_open_with_one_line(camp, monkeypatch):
    long = "CARRYING:\n" + "\n".join(f"  Rope Coil {i}" for i in range(40))
    monkeypatch.setattr(gm_client, "chat", lambda *a, **k: SimpleNamespace(
        text="[I slide the list across.] Here's everything you're hauling."))
    entry = tt.voiced_record(camp, "what am i carrying", long)
    assert entry["voiced"] and entry["open"] and entry["record"] == long
    assert "Rope" not in entry["text"]


def test_off_takes_the_actions_out_of_a_gm_answer(camp, monkeypatch):
    houserules.set_active({"table_talk": "off"})
    monkeypatch.setattr(gm_client, "chat", lambda *a, **k: SimpleNamespace(
        text="[I glance at your sheet.] Kesst Vayr, you're on 2 of 9 hit points."))
    entry = tt.voiced_record(camp, "how am i doing", RECORD)
    assert "[" not in entry["text"]
    assert "Do not describe your own actions" in tt.ooc_voice_block()


def test_the_ooc_prompt_carries_the_voice_in_the_system_message_only():
    from gm import prompts

    msgs = prompts.out_of_character_messages("BRIEF", "who runs this town",
                                             voice=tt.ooc_voice_block(tt.voice("grim")))
    assert "WHO YOU ARE: the Grim GM" in msgs[0]["content"]
    assert msgs[1]["content"] == "who runs this town"


def test_the_page_draws_the_gm_at_the_table_and_its_record():
    from pagesource import table_source

    src = table_source()
    assert 'b.who === "table"' in src and "tableSaid(" in src
    assert 'class="gmrecord"' in src
    assert ".beat.attable" in src


# --- what each line is for (the owner's first game, 2026-11-05) -------------------------
#
# Six lines, all praise: "A bold claim!", "Pure audacity! I love the nerve.", "That tongue
# poke was priceless.", "I love this chaos!" Two were said over REFUSALS ("You've secured
# the contract, and now the path ahead is clear!" over a refused request), where a GM's one
# job is to say why it did not happen. "Love" three times, and one line only retold the beat.

def _scripted(monkeypatch, *replies):
    said = list(replies)
    asked = []

    def fake(messages, *a, **k):
        asked.append(messages)
        return SimpleNamespace(text=said.pop(0) if said else "")

    monkeypatch.setattr(gm_client, "chat", fake)
    return asked


def test_each_request_and_each_example_carries_its_job():
    msgs = tt.table_messages(tt.voice("gleeful"), ["Refused: no such spell."], "", "",
                             tt.job_for(["natural", "refused"]))
    assert msgs[-1]["content"].startswith("YOUR JOB: " + tt.JOBS["refused"])
    shown = [m["content"] for m in msgs if m["role"] == "user"][:-1]
    assert all(s.startswith("YOUR JOB: ") for s in shown)
    # A quiet turn is a short line, never silence: on "always", the owner's first packaged
    # game (2026-11-07) got the dash the quiet example demonstrated, and no GM at all.
    quiet = [ex for ex in tt.voice()["examples"] if ex.get("kind") == "quiet"]
    assert quiet and all(ex["said"] != tt.SILENCE for ex in quiet)
    assert "dash" not in tt.JOBS["quiet"]


def test_a_refusal_line_that_never_says_why_is_asked_again_for_the_reason(camp, monkeypatch):
    houserules.set_active({"table_talk": "big"})
    asked = _scripted(monkeypatch, "[I grin wide.] Pure audacity! What a move.",
                      "No fireball for you: you don't have that spell.")
    tt.after_the_beat(camp, _agent(), _refusal(camp))
    assert len(asked) == 2, "one targeted remake, no more"
    assert "say why" in asked[1][-1]["content"]
    assert camp.transcript[-1]["text"] == "No fireball for you: you don't have that spell."


def test_a_refusal_line_still_without_a_reason_is_dropped(camp, monkeypatch):
    houserules.set_active({"table_talk": "big"})
    _scripted(monkeypatch, "Pure audacity!", "What a move, honestly.")
    n = len(camp.transcript)
    tt.after_the_beat(camp, _agent(), _refusal(camp))
    assert len(camp.transcript) == n
    assert camp.scene.said["table:log"][-1]["dropped"] == "never said why it was refused"


def test_a_dash_is_silence_and_nothing_goes_on_the_page(camp, monkeypatch):
    houserules.set_active({"table_talk": "always"})
    _scripted(monkeypatch, "-")
    plain = SimpleNamespace(outcomes=[Outcome("i1", "move", actor=_pc_ref(camp),
                                              tell="You cross to a bench and sit.")])
    n = len(camp.transcript)
    tt.after_the_beat(camp, _agent(), plain)
    assert len(camp.transcript) == n
    assert camp.scene.said["table:log"][-1]["dropped"] == "chose silence"


def test_a_line_that_retells_the_story_is_dropped():
    beat = "You walk away from the trestle table and reach the centre of the bustling market."
    assert tt.echoes("Off you go: you reach the centre of the bustling market.", beat)
    assert not tt.echoes("Nicely done. Where to now?", beat)


def test_the_same_praise_word_twice_in_a_row_is_dropped():
    recent = ["[I grin wide.] Pure audacity! I love the nerve."]
    line, why = tt.check("Oh, I love this chaos!", "", recent)
    assert not line and why.startswith("praise word again")
    assert tt.check("That was clever.", "", recent)[0]


# --- the GM's welcome (owner, 2026-11-06: "the GM should give an introduction on the
# first turn") -------------------------------------------------------------------------

def test_the_welcome_is_said_once_names_only_the_table_and_never_enters_the_history(
        camp, monkeypatch):
    houserules.set_active({"table_talk": "big"})
    asked = []
    pc = camp.scene.pc().name
    # Where the scene opens (the engine's place), not the town (live check 2026-11-07).
    place = camp.engine().here().name

    def fake(messages, *a, **k):
        asked.append(messages)
        return SimpleNamespace(text=f"[I set my notes down.] Welcome, {pc}. We begin in "
                                    f"{place}. Talk to me like you would at a table, "
                                    "and ask me anything with /gm.")

    monkeypatch.setattr(gm_client, "chat", fake)
    history = list(camp.history)
    tt.introduction(camp, _agent())
    tt.introduction(camp, _agent())
    welcomes = [b for b in camp.transcript if b.get("welcome")]
    assert len(welcomes) == 1 and len(asked) == 1, "once per campaign"
    assert welcomes[0]["who"] == "table"
    assert camp.history == history
    table = asked[0][-1]["content"]
    assert pc in table and place in table
    assert all(t in table for t in tt.TABLE_TIPS)


def test_a_welcome_naming_somebody_the_table_never_gave_is_dropped(camp, monkeypatch):
    houserules.set_active({"table_talk": "big"})
    monkeypatch.setattr(gm_client, "chat", lambda *a, **k: SimpleNamespace(
        text="Welcome! Tonight you meet the dread lord Zarnak in his tower."))
    tt.introduction(camp, _agent())
    assert not [b for b in camp.transcript if b.get("welcome")]
    assert "Zarnak" in camp.scene.said["table:log"][-1]["dropped"]


def test_off_means_no_welcome_and_no_model_means_none_either(camp, monkeypatch):
    houserules.set_active({"table_talk": "off"})
    monkeypatch.setattr(gm_client, "chat", lambda *a, **k: pytest.fail("off must not ask"))
    tt.introduction(camp, _agent())
    camp.scene.said.pop("table:welcomed", None)
    houserules.set_active({"table_talk": "big"})

    def down(*a, **k):
        raise ModelUnavailable("no Ollama")

    monkeypatch.setattr(gm_client, "chat", down)
    tt.introduction(camp, _agent())
    assert not [b for b in camp.transcript if b.get("welcome")]


def test_a_new_story_is_opened_with_the_welcome_after_the_opening_beat():
    """`campaign.open_the_story` is the one door every new campaign opens through; the
    welcome is asked there, after the opening, and only on the written opening."""
    import ast
    from pathlib import Path

    tree = ast.parse(Path(__file__).resolve().parent.parent.joinpath(
        "play", "campaign.py").read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
              and n.name == "open_the_story")
    calls = [(n.lineno, getattr(n.func, "attr", getattr(n.func, "id", "")))
             for n in ast.walk(fn) if isinstance(n, ast.Call)]
    line = {name: ln for ln, name in calls}
    assert line["_after_the_opening"] < line["introduction"]



# --- mend, don't drop (the owner's first packaged game, 2026-11-07) ----------------------

def test_a_welcome_tripping_a_check_is_asked_again_once_and_kept(camp, monkeypatch):
    """The welcome said "English" and was dropped whole, so a new campaign opened with no
    GM at all. Now the fault is named and asked for once more."""
    houserules.set_active({"table_talk": "big"})
    pc = camp.scene.pc().name
    asked = _scripted(monkeypatch, f"Welcome, {pc}. In plain English: talk to me.",
                      f"Welcome, {pc}. Talk to me the way you would at a table.")
    tt.introduction(camp, _agent())
    welcomes = [b for b in camp.transcript if b.get("welcome")]
    assert len(asked) == 2 and '"English"' in asked[1][-1]["content"]
    assert len(welcomes) == 1 and "English" not in welcomes[0]["text"]


def test_table_talk_tripping_a_check_is_mended_once(camp, monkeypatch):
    houserules.set_active({"table_talk": "always"})
    asked = _scripted(monkeypatch, "Bold, very bold, like Zarnak himself.",
                      "Bold. Now let's see what you do next.")
    plain = SimpleNamespace(outcomes=[Outcome("i1", "move", actor=_pc_ref(camp),
                                              tell="You cross to the bar.")])
    tt.after_the_beat(camp, _agent(), plain)
    assert len(asked) == 2
    assert camp.transcript[-1]["text"] == "Bold. Now let's see what you do next."

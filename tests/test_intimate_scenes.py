"""An intimate scene at an explicit table gets its own briefing, at the end of the prompt,
and the table's own passages as demonstrations — between adults only, enforced in code.

Measured 2026-10-01 on the owner's save: with content on "explicit", the two beats the
player asked for in so many words — "We go all the way" and "we climax together and then
clean up and get dressed" — came out metaphorical, and the pipeline had not softened them:
the model's drafts reached the page unedited but for a recurring-phrase polish. The cause
was one ~350-character line against the whole briefing — 13,103 characters of turn
briefing and 13,634 of worked examples written in a restrained register. Instruction
volume lost to demonstration volume (CLAUDE.md), so this beat changes the balance instead
of the wording (gm/intimate.py has the design and its sources).

No explicit text anywhere in here: the demonstrations are neutral stand-ins
("DEMO-PASSAGE-ONE: a placeholder line"), which prove the injection, the placement and the
caps without being what the owner will put there.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from django.conf import settings
from django.test import Client, override_settings

from gm import intimate, judgement, narration, prompts, state_claims
from rules import population
from rules.bestiary import instantiate
from rules.engine import Scene
from rules.sheet import load_pc

# Stand-ins for the narrator's own recent beats. The owner's beats are not copied here;
# these carry the same KINDS of description (`intimate._WARM`) in words fit for a test.
WARM = ("Her lips find yours and she kisses you hard, a low moan in her throat as she "
        "arches into you, her breath against your neck. What do you do?")
WARM_BEFORE = ("She draws you down beside her, her body against yours, her hand at your "
               "hip. What do you do?")
COLD = ("The innkeeper wipes the counter and names the price of a room for the night. "
        "Rain runs off the eaves. What do you do?")
# Two kinds only (breath, lips): a secret told close, which is not a scene.
WHISPER = ("She leans close, her breath against your ear, her lips almost touching it as "
           "she tells you the name. What do you do?")


@pytest.fixture
def scene():
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("guildhand", scene=s, name="Mira"), zone="near")
    return s


@pytest.fixture
def data(tmp_path):
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        yield tmp_path


# --- detection --------------------------------------------------------------------------


@pytest.mark.parametrize("line, earlier", [
    # The owner's two lines, measured: both came back metaphorical at an explicit table.
    ("We go all the way", [WARM_BEFORE, WARM]),
    ("we climax together and then clean up and get dressed", [WARM_BEFORE, WARM]),
    # A sexual line with a person in it detects even before the scene is warm.
    ("we climax together and then clean up and get dressed", [COLD]),
    # Continue keeps the standing action (the 2026-09-18 ruling): in an intimate scene
    # that action is the scene.
    (prompts.CARRY_ON, [WARM_BEFORE, WARM]),
    ("I kiss her neck and let her lead", [WARM]),
])
def test_an_intimate_beat_is_detected(scene, line, earlier):
    hit, why = intimate.reads_intimate(line, earlier, scene)
    assert hit, why


@pytest.mark.parametrize("line, earlier, why", [
    ("I pay for the room", [COLD], "the scene is not intimate"),
    # Even straight after an intimate beat: paying is not carrying the scene on.
    ("I pay for the room", [WARM_BEFORE, WARM], "the player's line turns elsewhere"),
    ("she hugs her brother goodbye", [COLD], "the scene is not intimate"),
    ("I go all the way to the docks", [COLD], "the scene is not intimate"),
    ("I kiss my mother goodbye on the cheek", [COLD], "the scene is not intimate"),
    # A strong word with nobody in it.
    ("I wait for the climax of the play", [COLD], "the scene is not intimate"),
    # Two kinds of warm description, a secret told close: under the bar of three.
    ("I kiss her hand in thanks", [WHISPER], "the scene is not intimate"),
    ("I get dressed and pay what I owe", [WARM_BEFORE, WARM],
     "the player's line turns elsewhere"),
])
def test_an_ordinary_beat_is_not(scene, line, earlier, why):
    """A misfire would put the table's intimate passages in front of an ordinary beat."""
    assert intimate.reads_intimate(line, earlier, scene) == (False, why)


def test_nobody_to_be_with_and_a_fight_are_not_intimate(scene):
    alone = Scene(location_id="5bbd0c40345f")
    alone.add(load_pc("fixtures/pc-kesst.json"))
    assert intimate.reads_intimate("We go all the way", [WARM], alone)[0] is False
    scene.initiative = [("pc", 15)]
    scene.turn = 0
    assert scene.in_encounter
    assert intimate.reads_intimate("We go all the way", [WARM], scene) == (
        False, "a fight is running")


def test_a_hostile_person_is_nobody_to_be_intimate_with(scene):
    """The blow detector is skipped for an intimate beat because nobody here is
    hostile; a hostile person is never the scene's partner."""
    from rules import states
    from rules.engine import Engine

    mira = next(a for a in scene.actors.values() if not a.is_pc)
    Engine(scene)._set_attitude(mira, "hostile", None, "test")
    assert states.attitude_of(mira) == "hostile"
    assert intimate.partners(scene) == []


def test_the_owners_soft_beats_were_invisible_to_the_old_vocabulary():
    """Measured on the owner's save: `narration.intimate` read none of five intimate
    beats as sexual, and missed the player's own "I test her vulva…" outright. The
    detection reads the scene with its own wider vocabulary, and the guard's list now
    carries the anatomical words."""
    assert narration.intimate("I test her vulva to see if she is ready")
    assert not narration.intimate(WARM)          # still a vocabulary of explicit words
    assert len(intimate.warm_kinds([WARM])) >= intimate.WARM_AT


# --- the decision: explicit, detected, adults only -------------------------------------


def test_fade_is_unchanged_and_reads_nothing(scene, data):
    """"fade" behaves exactly as before: no decision, no file created, the fade line."""
    d = intimate.decide("We go all the way", [WARM_BEFORE, WARM], scene, content="fade")
    assert (d.mode, d.fired, d.demonstrations) == ("", False, None)
    assert not intimate.demonstrations_path().exists()


def test_explicit_and_detected_and_adults_fires(scene, data):
    d = intimate.decide("We go all the way", [WARM_BEFORE, WARM], scene, content="explicit")
    assert d.fired and d.mode == "intimate"
    assert d.as_log()["fired"] is True


def test_explicit_but_ordinary_is_todays_prompt(scene, data):
    d = intimate.decide("I pay for the room", [COLD], scene, content="explicit")
    assert (d.mode, d.fired, d.demonstrations) == ("", False, None)


def test_a_minor_present_never_gets_the_briefing_and_the_scene_fades(scene, data):
    """Adults only, without exception: somebody here whose population record is a minor
    (rules/lives.py) — the briefing never fires, and the prose gets the FADE line even at
    an explicit table."""
    from world.loader import load_cached

    world = load_cached("fixtures/aurvantis-campaign.json")
    town = world.by_name("Vormoor", kind="CITY").id
    s = Scene(location_id=town)
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("guildhand", scene=s, name="Mira"), zone="near")
    rec = population.note(s, "a boy selling apples")
    seller = instantiate("guildhand", scene=s, name="apple-seller")
    s.add(seller)
    rec["ref"] = seller.ref
    d = intimate.decide("We go all the way", [WARM_BEFORE, WARM], s, content="explicit")
    assert d.mode == "fade" and not d.fired and d.demonstrations is None


@pytest.mark.parametrize("line, earlier", [
    ("We go all the way, while the boy sleeps in the next room", [WARM_BEFORE, WARM]),
    ("We go all the way", [WARM_BEFORE, WARM + " A child is singing in the yard."]),
])
def test_a_child_named_in_the_scene_fades_it(scene, data, line, earlier):
    d = intimate.decide(line, earlier, scene, content="explicit")
    assert d.mode == "fade" and not d.fired


def test_the_fade_line_is_forced_at_an_explicit_table(monkeypatch):
    from rules import houserules

    monkeypatch.setattr(houserules, "content", lambda: "explicit")
    assert "fade to black" in prompts.content_line(fade=True)
    assert "fade to black" not in prompts.content_line()


# --- the prompt ---------------------------------------------------------------------------


DEMOS = [{"player": "I go on with what we are doing.",
          "reply": {"narration": "DEMO-PASSAGE-ONE: a placeholder line."}},
         {"player": "I go on.", "reply": {"narration": "DEMO-PASSAGE-TWO: another."}}]


def _prose(scene_mode="", demonstrations=None):
    return prompts.call_prose_messages(
        "BRIEF", [], "We go all the way", ["Nothing mechanical."],
        earlier=[WARM], scene_now_block="SCENE-NOW", scene_mode=scene_mode,
        demonstrations=demonstrations)


def test_the_intimate_briefing_replaces_the_turn_briefing_not_joins_it():
    """One 350-character line against the whole briefing; the owner's two beats came out
    metaphorical, unedited by the pipeline. So the beat's own briefing REPLACES the
    13,103-character turn briefing and the restrained worked examples — and keeps the
    laws: no number, the names, the hand-back, adults only. The one law it relaxes is the
    owner's ruling of 2026-10-01: here the narrator may act and speak for the player's
    character."""
    msgs = _prose("intimate", DEMOS)
    system = msgs[0]["content"]
    assert system.startswith(prompts.INTIMATE_BRIEFING)
    assert "Build the turn out of four moves" not in system
    assert "show the wound" not in system
    assert prompts.SAY_TAGS.strip() in system
    flat = " ".join(prompts.INTIMATE_BRIEFING.split())
    for law in ("never write a number", "Name only the people and places",
                "you may write what the player's character does and says",
                "asking what they DO",
                "Never anyone who is a child", '"intents": []'):
        assert law in flat
    shown = json.dumps(msgs)
    assert all(e["reply"]["narration"][:40] not in shown for e in prompts.EXAMPLES)


def test_the_note_goes_last_the_authors_note_slot():
    """SillyTavern and KoboldAI both measure the end of the context as the slot that
    steers; the note follows the tells and the scene as it stands."""
    msgs = _prose("intimate", DEMOS)
    last = msgs[-1]["content"]
    assert last.endswith(prompts.intimate_note(True))
    assert last.index("SCENE-NOW") < last.index(prompts.intimate_note(True))
    assert "passages you wrote earlier" in prompts.intimate_note(True)
    assert "passages" not in prompts.intimate_note(False)


def test_the_demonstrations_go_in_as_example_turns():
    """As turns, the way Continue's examples do (`call_one_messages(examples=…)`), between
    the system message and the beat — not pasted into the system text."""
    msgs = _prose("intimate", DEMOS)
    assert "DEMO-PASSAGE-ONE" not in msgs[0]["content"]
    assert msgs[1] == {"role": "user", "content": "I go on with what we are doing."}
    assert msgs[2]["role"] == "assistant"
    assert json.loads(msgs[2]["content"])["narration"].startswith("DEMO-PASSAGE-ONE")
    assert json.loads(msgs[4]["content"])["narration"].startswith("DEMO-PASSAGE-TWO")
    assert len(msgs) == 6


def test_no_demonstrations_on_file_means_no_examples_at_all():
    msgs = _prose("intimate", [])
    assert [m["role"] for m in msgs] == ["system", "user"]


def test_the_ordinary_and_fade_prompts_carry_no_demonstration_and_no_note(monkeypatch):
    from rules import houserules

    monkeypatch.setattr(houserules, "content", lambda: "explicit")
    for mode in ("", "fade"):
        msgs = _prose(mode)
        shown = json.dumps(msgs)
        assert "DEMO-PASSAGE" not in shown and "THIS BEAT: an intimate" not in shown
        assert msgs[0]["content"].startswith(prompts.BRIEFING[:200])
    assert "fade to black" in _prose("fade")[0]["content"]


def test_the_relaxation_is_the_intimate_beats_alone():
    """The owner's ruling (2026-10-01): the narrator may speak for the player's character
    in an explicit intimate scene ONLY. The turn briefing keeps its rule."""
    assert "The player says only what their character does" in prompts.BRIEFING
    assert "may write what their character does and says" in prompts.intimate_note(True)


def test_the_grammar_ceiling_still_clamps_and_only_a_flag_lifts_it():
    """The owner asked for 3,000 characters; `maxLength` stops compiling between 2,000
    and 2,100 on both models measured (HTTP 500 on llama3.1, "failed to parse grammar" on
    gemma-4 12B). So 3,000 never reaches the grammar: a big `max_chars` is still clamped,
    and only the explicit `unbounded` flag leaves the ceiling out."""
    clamped = prompts.prose_schema(max_chars=3000)["properties"]["narration"]
    assert clamped["maxLength"] == prompts.GRAMMAR_MAXLENGTH_CEILING == 1800
    free = prompts.prose_schema(800, max_chars=3000, unbounded=True)
    assert "maxLength" not in free["properties"]["narration"]
    assert "minLength" not in free["properties"]["narration"]
    assert prompts.INTIMATE_LENGTH == 3000 and "3,000" in prompts.INTIMATE_BRIEFING
    # ~3.8 characters a token (measured on gemma, prompts.CHARS_PER_TOKEN's note): the
    # budget covers the ask and the JSON around it.
    assert prompts.INTIMATE_NUM_PREDICT * 3.6 > prompts.INTIMATE_LENGTH + 600
    assert intimate.PASSAGE_CHARS == prompts.INTIMATE_LENGTH


def test_a_reply_the_budget_cut_off_is_salvaged():
    """With no `maxLength`, the token budget can end the string: "Unterminated string"
    lost 1,068 characters of good prose on 2026-09-04. The narration is read up to the
    cut, escapes kept, and trimmed to its last whole sentence by the caller."""
    cut = '{"narration": "DEMO-ONE: a line. She says \\"stay\\". DEMO-TWO is cu'
    got = intimate.narration_from_cut_reply(cut)
    assert got == 'DEMO-ONE: a line. She says "stay". DEMO-TWO is cu'
    assert narration.trim_unfinished(got)[0] == 'DEMO-ONE: a line. She says "stay".'
    whole = '{"narration": "DEMO-ONE.", "suggestions": ["I st'
    assert intimate.narration_from_cut_reply(whole) == "DEMO-ONE."
    assert intimate.narration_from_cut_reply('{"suggestions": []}') == ""
    assert intimate.narration_from_cut_reply('{"narration": "DEMO \\') == "DEMO"


# --- the owner's file ---------------------------------------------------------------------


def test_the_path_is_the_data_folders_not_the_bundles(data):
    """CLAUDE.md: never anchor a path on `__file__` in code that will be frozen."""
    assert intimate.demonstrations_path() == (
        Path(settings.CAMPAIGN_DIR).parent / "homebrew" / "style" / "intimate.txt")
    assert intimate.demonstrations_path().is_relative_to(data)
    assert not intimate.demonstrations_path().is_relative_to(Path(intimate.__file__).parent.parent)


def test_the_file_is_created_holding_only_a_header(data):
    d = intimate.read_demonstrations()
    path = intimate.demonstrations_path()
    assert path.exists() and d.examples == [] and d.chars == 0
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines and all(ln.startswith("#") or not ln.strip() for ln in lines)
    header = path.read_text(encoding="utf-8")
    for said in ("Up to 3 are shown", "No names", "Keep the setting neutral",
                 "under about 3,000 characters", 'beginning "> "',
                 "read fresh on every beat", "Explicit", "an adult", "1.)", "---"):
        assert said in header


def test_a_file_the_owner_made_first_is_never_touched(data):
    """The owner may write the file before the build that reads it ships: it is created
    only when missing, never overwritten and never given the header."""
    path = intimate.demonstrations_path()
    path.parent.mkdir(parents=True)
    path.write_text("DEMO-PASSAGE-ONE: a placeholder line.\n", encoding="utf-8")
    intimate.ensure_file()
    d = intimate.read_demonstrations()
    assert path.read_text(encoding="utf-8") == "DEMO-PASSAGE-ONE: a placeholder line.\n"
    assert d.examples[0]["reply"]["narration"] == "DEMO-PASSAGE-ONE: a placeholder line."


def test_the_file_is_read_live(data):
    path = intimate.ensure_file()
    path.write_text(intimate.HEADER + "DEMO-PASSAGE-ONE: a placeholder line.\n",
                    encoding="utf-8")
    first = intimate.read_demonstrations()
    assert [e["reply"]["narration"] for e in first.examples] == [
        "DEMO-PASSAGE-ONE: a placeholder line."]
    path.write_text(intimate.HEADER + "> I stay.\nDEMO-PASSAGE-ONE: a placeholder line.\n"
                    "---\nDEMO-PASSAGE-TWO: another placeholder.\n", encoding="utf-8")
    again = intimate.read_demonstrations()
    assert [e["player"] for e in again.examples] == ["I stay.",
                                                     intimate.DEFAULT_PLAYER_LINE]
    assert again.chars == sum(len(e["player"]) + len(e["reply"]["narration"])
                              for e in again.examples)


def _file(*parts: str) -> None:
    """Write the examples file: the header, then `parts` one per line."""
    intimate.ensure_file().write_text(intimate.HEADER + "\n".join(parts) + "\n",
                                      encoding="utf-8")


def test_the_budget_takes_whole_passages_and_turns_them_over(data):
    """Up to three passages and 9,000 characters a beat, never one cut part-way, and
    which ones turns over with the beat so a long file is all used across a scene."""
    parts = []
    for n in range(1, 6):
        parts += ([] if n == 1 else ["---"]) + [f"> I go on {n}.",
                                                f"DEMO-PASSAGE-{n}: a placeholder line."]
    _file(*parts)
    shown = {}
    for beat in range(5):
        d = intimate.read_demonstrations(beat)
        assert len(d.examples) == intimate.MAX_PASSAGES == 3 and d.on_file == 5
        shown[beat] = [e["reply"]["narration"][:14] for e in d.examples]
    assert shown[0] == ["DEMO-PASSAGE-1", "DEMO-PASSAGE-2", "DEMO-PASSAGE-3"]
    assert shown[3] == ["DEMO-PASSAGE-4", "DEMO-PASSAGE-5", "DEMO-PASSAGE-1"]
    assert intimate.read_demonstrations(7).examples == intimate.read_demonstrations(2).examples
    assert {x for v in shown.values() for x in v} == {f"DEMO-PASSAGE-{n}" for n in range(1, 6)}


def test_a_long_passage_is_flagged_and_never_cut(data):
    long = ("DEMO-PASSAGE-LONG: a placeholder sentence. " * 75).strip()   # 3,224 characters
    # Two long ones fit the 9,000; the third would not, and is passed over WHOLE for the
    # short one after it — never cut down to fit.
    _file(long, "---", long, "---", long, "---", "DEMO-PASSAGE-TWO: a placeholder line.")
    d = intimate.read_demonstrations(0)
    assert d.examples and all(
        e["reply"]["narration"] in (long, "DEMO-PASSAGE-TWO: a placeholder line.")
        for e in d.examples)
    assert d.chars <= intimate.TOTAL_CHARS
    assert any("over the 9,000 total" in s for s in d.skipped)
    assert sum("over the 3,000 the narrator can write" in w for w in d.warnings) == 3


def test_numbered_headers_separate_passages_too(data):
    """The owner's draft numbers its passages ("1.)", "2.)"); dashes work as well, and a
    numbered or dashed line inside a comment separates nothing."""
    _file("# 9.)", "1.)", "> I stay.", "DEMO-PASSAGE-ONE: a placeholder line.",
          "2.)", "DEMO-PASSAGE-TWO: another.", "3)", "DEMO-PASSAGE-THREE: a third.",
          "-----", "DEMO-PASSAGE-FOUR: a fourth.")
    passages, dropped = intimate.parse(
        intimate.demonstrations_path().read_text(encoding="utf-8"))
    assert [(p.n, p.player, p.narration.split(":")[0]) for p in passages] == [
        (1, "I stay.", "DEMO-PASSAGE-ONE"),
        (2, intimate.DEFAULT_PLAYER_LINE, "DEMO-PASSAGE-TWO"),
        (3, intimate.DEFAULT_PLAYER_LINE, "DEMO-PASSAGE-THREE"),
        (4, intimate.DEFAULT_PLAYER_LINE, "DEMO-PASSAGE-FOUR")]
    assert dropped == []


def test_a_name_recurring_across_passages_is_flagged(data):
    """A name shown to the model in two passages comes back in play as a person who
    does not exist (`invented-name`): noted in the turn log, never blocking."""
    _file("> I stay.", "DEMO-PASSAGE-ONE: you and Selka stay.", "---",
          "DEMO-PASSAGE-TWO: Selka laughs. You stay too.", "---",
          "DEMO-PASSAGE-THREE: you wait while Orren sleeps.")
    d = intimate.read_demonstrations(0)
    assert len(d.examples) == 3
    names = [w for w in d.warnings if w.startswith("names recurring")]
    assert names and "Selka" in names[0] and "Orren" not in names[0]
    assert "You" not in names[0]


def test_a_passage_naming_a_child_is_never_shown(data):
    intimate.ensure_file().write_text(
        intimate.HEADER + "DEMO-PASSAGE-ONE: the girl watches.\n---\n"
                          "DEMO-PASSAGE-TWO: a placeholder line.\n", encoding="utf-8")
    d = intimate.read_demonstrations()
    assert [e["reply"]["narration"] for e in d.examples] == [
        "DEMO-PASSAGE-TWO: a placeholder line."]
    assert any("names a child" in s for s in d.skipped)


# --- the pipeline must not mangle the beat ---------------------------------------------


def test_the_scenes_own_sentences_are_not_conditions(scene):
    """Probed 2026-10-01: "lies flat on her back" read as prone, "left dazed" as dazed —
    each a rewrite or a cut of the scene's own sentence. Off for an intimate beat; the
    weapon and purse questions stay."""
    line = "Mira lies flat on her back on the bed. You are left dazed and breathless."
    assert state_claims.state_claims(line, scene)
    assert not state_claims.state_claims(line, scene, conditions=False)
    held = "Mira's sword clatters to the floor."
    assert state_claims.state_claims(held, scene, conditions=False) == \
        state_claims.state_claims(held, scene)


def test_the_detectors_misread_the_scenes_own_sentences():
    """The two misreads the exemptions below exist for, as the detectors stand.
    "Mira grabs your hair and pulls you down to her" is an undeclared blow, and its repair
    asks for the beat again "threatening, squaring up or reaching". And, measured live
    2026-10-01 on the first briefed beat, "her body is tense but welcoming" read as Quin
    Nutmeg "down or dead" — `_FELLED` holds "body", for a corpse."""
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("guildhand", scene=s, name="Mira"), zone="near")
    assert judgement.attacked_by(s, "Mira grabs your hair and pulls you down to her.")
    assert narration.contradicts_state(
        "Quin Nutmeg draws you close. Her body is tense but welcoming.",
        {"Quin Nutmeg": {"alive": True, "hurt": False}})


def test_a_rewrite_of_an_intimate_beat_keeps_its_register():
    msgs = prompts.narration_repair_messages("A passage.", "A complaint.",
                                             keep=prompts.INTIMATE_KEEP)
    assert msgs[0]["content"].endswith(prompts.INTIMATE_KEEP)
    assert prompts.INTIMATE_KEEP not in prompts.narration_repair_messages(
        "A passage.", "A complaint.")[0]["content"]


# --- through the path the player clicks -------------------------------------------------


@pytest.fixture
def live(tmp_path, monkeypatch):
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        from play import campaign as cm
        from play import concurrency
        from rules import houserules

        cm._LIVE.clear()
        concurrency.reset_for_tests()
        monkeypatch.setattr(houserules, "content", lambda: "explicit")
        cm.set_active("adults")
        c = cm.current("adults")
        # The fixture world opens on a chase; this scene is a quiet room.
        c.scene.initiative = []
        c.scene.add(instantiate("guildhand", scene=c.scene, name="Mira"), zone="near")
        c.transcript += [{"who": "gm", "kind": "setup", "text": WARM_BEFORE},
                         {"who": "player", "text": "I kiss her"},
                         {"who": "gm", "kind": "setup", "text": WARM}]
        c.save()
        yield cm, c
        cm._LIVE.clear()


def _say(monkeypatch, beat, line, first_raw=None):
    """One turn through /api/say with the plan stubbed and every model call answered
    with `beat` — or, for the FIRST call (the prose), with `first_raw` verbatim. The
    calls' keyword arguments are kept on `_say.kwargs`."""
    from gm import client as gm_client
    from gm.agent import TurnPlan
    from gm.client import Reply
    from play import views

    def plan(agent, *a, **kw):
        agent.last_said = []
        agent.intimate = None
        return TurnPlan(narration="", intents=agent.engine.validate(
            [{"op": "narrate_only", "because": "t"}]))

    seen: list = []
    _say.kwargs = []

    def chat(messages, *a, **k):
        seen.append(messages)
        _say.kwargs.append(k)
        if first_raw is not None and len(seen) == 1:
            return Reply(first_raw, 0.1, "stub")
        return Reply(json.dumps({"narration": beat, "suggestions": ["I stay"]}), 0.1, "stub")

    monkeypatch.setattr(views.GMAgent, "plan_turn", plan)
    monkeypatch.setattr(gm_client, "chat", chat)
    r = Client().post("/api/say", data=json.dumps({"text": line}),
                      content_type="application/json")
    assert r.status_code == 200
    return r, seen


def _prose_row(cm):
    return next(row for row in reversed(cm.current().turn_log) if row.get("kind") == "prose")


def test_an_intimate_beat_through_the_view_is_briefed_injected_and_logged(live, monkeypatch):
    cm, c = live
    intimate.ensure_file().write_text(
        intimate.HEADER + "DEMO-PASSAGE-ONE: a placeholder line.\n---\n"
                          "DEMO-PASSAGE-TWO: another placeholder.\n", encoding="utf-8")
    beat = ("Mira answers you without a word, and the two of you go on. " * 12
            + "What do you do?")
    r, seen = _say(monkeypatch, beat, "We go all the way")
    prose_call = seen[0]
    assert prose_call[0]["content"].startswith(prompts.INTIMATE_BRIEFING)
    assert "DEMO-PASSAGE-ONE" in json.dumps(prose_call)
    row = _prose_row(cm)["intimate"]
    assert row["fired"] is True and row["demos"] == 2
    assert row["demo_chars"] == (len("DEMO-PASSAGE-ONE: a placeholder line.")
                                 + len("DEMO-PASSAGE-TWO: another placeholder.")
                                 + 2 * len(intimate.DEFAULT_PLAYER_LINE))
    # Counts only: the passages themselves never reach the turn log.
    assert "DEMO-PASSAGE" not in json.dumps(cm.current().turn_log)


# Neutral sentences of the kinds an intimate beat is made of, each one a misread by a
# check written for fights: an undeclared blow, a prone body, a body "down or dead".
SCENE_WORDS = ("Mira grabs your hair and pulls you down to her. Her body is tense but "
               "welcoming against yours. Mira lies flat on her back on the bed, laughing "
               "under her breath. The candle on the sill has burned low and the room is "
               "quiet except for the two of you. She says your name once, softly, and "
               "does not look away. Outside, a cart goes by on the wet street and is gone. "
               "Neither of you is in any hurry now, and the night has a long way to run. "
               "She draws the blanket up over both of you and settles there. "
               "What do you do?")


def _misreads(repairs) -> list[str]:
    return [x for x in repairs if "undeclared blow" in x or "state claim" in x
            or "contradicts-the-engine" in x]


def test_the_scenes_own_sentences_survive_the_checks_on_an_intimate_beat(live, monkeypatch):
    """Through the view: on a briefed beat none of the three fight checks fires on the
    scene's own sentences."""
    cm, c = live
    r, seen = _say(monkeypatch, SCENE_WORDS, "We go all the way")
    row = _prose_row(cm)
    assert row["intimate"]["fired"] is True
    assert _misreads(row["repairs"]) == []


def test_the_same_sentences_on_an_ordinary_beat_are_still_checked(live, monkeypatch):
    """The exemption is the briefed beat's only: the same words after "I pay for the
    room" still go to the fight checks, which is what makes the test above mean
    anything."""
    cm, c = live
    r, seen = _say(monkeypatch, SCENE_WORDS, "I pay for the room")
    row = _prose_row(cm)
    assert row["intimate"]["fired"] is False
    assert _misreads(row["repairs"])


def test_an_ordinary_beat_through_the_view_injects_nothing(live, monkeypatch):
    cm, c = live
    intimate.ensure_file().write_text(
        intimate.HEADER + "DEMO-PASSAGE-ONE: a placeholder line.\n", encoding="utf-8")
    beat = "Mira counts the coins into her apron and nods. " * 10 + "What do you do?"
    r, seen = _say(monkeypatch, beat, "I pay for the room")
    assert all("DEMO-PASSAGE" not in json.dumps(m) for m in seen)
    assert not seen[0][0]["content"].startswith(prompts.INTIMATE_BRIEFING)
    assert _prose_row(cm)["intimate"]["fired"] is False


def test_an_empty_file_is_logged_and_the_briefing_still_fires(live, monkeypatch):
    cm, c = live
    beat = "Mira answers you without a word, and the two of you go on. " * 12 + "What?"
    r, seen = _say(monkeypatch, beat, "We go all the way")
    assert seen[0][0]["content"].startswith(prompts.INTIMATE_BRIEFING)
    assert any(row.get("kind") == "intimate" and row.get("note") ==
               "no demonstrations on file" for row in cm.current().turn_log)


def test_the_minors_guard_after_the_prose_still_runs_on_this_path(live, monkeypatch):
    """The briefing fired (adults only at the time), and the beat the model wrote brought
    a child in. Written in words `narration.intimate` does not know — the owner's scene
    measured five of five intimate beats invisible to it — and still discarded whole,
    because a briefed beat counts as sexual whatever its vocabulary."""
    cm, c = live
    beat = ("Mira holds you close, and a boy is watching from the doorway. " * 8
            + "What do you do?")
    assert not narration.intimate(beat)
    r, seen = _say(monkeypatch, beat, "We go all the way")
    assert seen[0][0]["content"].startswith(prompts.INTIMATE_BRIEFING)
    shown = next(b for b in reversed(r.json()["transcript"]) if b.get("who") == "gm")
    assert "boy" not in shown["text"]
    assert any(row.get("kind") == "refused-beat" for row in cm.current().turn_log)


def test_the_intimate_prose_call_has_no_ceiling_and_its_own_budget(live, monkeypatch):
    """The owner's 3,000 characters on the briefed beat: no `maxLength` and a token budget
    of 1,100 instead; the ordinary beat keeps the 1,800 clamp and its 1,400."""
    cm, c = live
    beat = SCENE_WORDS
    _say(monkeypatch, beat, "We go all the way")
    first = _say.kwargs[0]
    assert "maxLength" not in first["schema"]["properties"]["narration"]
    assert first["num_predict"] == prompts.INTIMATE_NUM_PREDICT == 1100
    _say(monkeypatch, beat, "I pay for the room")
    first = _say.kwargs[0]
    assert first["schema"]["properties"]["narration"]["maxLength"] == 1800
    assert first["num_predict"] == 1400


def test_a_budget_death_on_an_intimate_beat_ships_its_whole_sentences(live, monkeypatch):
    """Not the holding line: the narration is salvaged from the cut reply and trimmed
    back to its last whole sentence, and the attempt says so."""
    cm, c = live
    cut = json.dumps({"narration": SCENE_WORDS.replace(" What do you do?", "")})
    cut = cut[:cut.index("Neither of you") + len("Neither of you is in")]
    r, seen = _say(monkeypatch, SCENE_WORDS, "We go all the way", first_raw=cut)
    row = _prose_row(cm)
    assert any("narration salvaged" in a["note"] for a in row["attempts"])
    shown = next(b for b in reversed(r.json()["transcript"]) if b.get("who") == "gm")
    assert "The candle on the sill has burned low" in shown["text"]
    assert "Neither of you is in" not in shown["text"]
    assert "The moment holds" not in shown["text"]


PC_SPEECH = ("You pull her closer. \"Stay with me tonight,\" you whisper against her hair, "
             "and you tell her you have wanted this since the market. You kiss her slowly. "
             "She answers by drawing you down beside her, her hand at your hip. "
             "The candle on the sill has burned low and the room is quiet. "
             "Outside, a cart goes by on the wet street and is gone. "
             "Neither of you is in any hurry now, and the night has a long way to run. "
             "What do you do?")


def test_the_narrator_may_speak_for_the_player_on_an_intimate_beat(live, monkeypatch):
    """The owner's ruling (2026-10-01, "yes it can speak for the character"), for the
    explicit intimate scene only. The line the narrator gives the player's character is
    kept, and the beat's turn-log row records the exemption.

    Measured the same day, and the reason there is no check to switch off: run through
    the whole pipeline, this beat's "Stay with me tonight," you whisper reached the page
    unchanged on an ORDINARY beat too. Nothing in gm/checks or narration catches the
    narrator speaking for the player — that rule has only ever been the turn briefing's
    sentence, which stands on every other beat (`test_the_relaxation_is_the_intimate_
    beats_alone`)."""
    cm, c = live
    r, seen = _say(monkeypatch, PC_SPEECH, "We go all the way")
    shown = next(b for b in reversed(r.json()["transcript"]) if b.get("who") == "gm")
    assert '"Stay with me tonight," you whisper' in shown["text"]
    row = _prose_row(cm)["intimate"]
    assert any("speaks for the player's character" in e for e in row["exempt"])
    r, seen = _say(monkeypatch, PC_SPEECH, "I pay for the room")
    assert "exempt" not in _prose_row(cm)["intimate"]
    assert seen[0][0]["content"].startswith(prompts.BRIEFING[:200])

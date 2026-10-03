"""People and names: Lane C of the 2026-10-03 playtest (docs/playtest-2026-10-03.md,
items 13-16; docs/people-and-names.md).

Every case below is built from the owner's two Zhilvarnia saves — the player's own lines
and the narrator's own beats, as they reached the page — and names what went wrong there:

  13. `I give a friendly wink and say "just trying to start a conversation and see what
      is happening here."` was read `talk, target: say "just trying…"`, and an actor (c4)
      was minted with that phrase as his NAME. It printed in prose, tells and the ledger,
      and was still being spoken to ten turns later.
  14. "The laborer—a man named Korvu…": Korvu is one of the world's peoples, and the
      laborer c11 was renamed "Korvu", true name and all.
  15. Every line of "the man" was tagged to c1, the servant carrying jugs, who was in none
      of those beats; the PC's own lines were booked as the servant's and the clerk's;
      c6's face was placed after "The man in the heavy coat (c4)".
  16. '"A piece of work like this," you say, your voice dropping into a sultry lilt…' —
      the narrator speaking for the PC at an ordinary table, after the plan's invented
      `say` had already been dropped.
"""
from __future__ import annotations

from types import SimpleNamespace

from gm import interpret, judgement, narration, speech
from rules import names, population
from rules.bestiary import instantiate
from rules.engine import Scene

WINK = ('I give a friendly wink and say "just trying to start a conversation and see '
        'what is happening here."')
SAY_PHRASE = 'say "just trying to start a conversation and see what is happening here."'


def _scene(*people):
    s = Scene(location_id="t")
    pc = instantiate("guildhand", scene=s, name="Kesst Vayr")
    pc.kind = "pc"
    s.add(pc)
    made = []
    for name, extra in people:
        a = instantiate("guildhand", scene=s, name=name)
        for k, v in extra.items():
            setattr(a, k, v)
        s.add(a)
        made.append(a)
    return s, made


# --- item 13: quoted words are never a person ------------------------------------------

def test_the_players_quoted_words_are_not_a_name():
    """The phrase c4 was minted under, refused by its shape; the descriptions the corpus
    really uses pass."""
    assert "quoted words" in names.not_a_name(SAY_PHRASE)
    assert names.not_a_name("ask him about the docks")
    assert names.not_a_name("Just trying to start a conversation and see.")
    for ok in ("the woman who sold me bread", "a Korvu porter", "man in the heavy coat",
               "the tailor who mended my cloak last week", "old woman mending nets",
               "the smith's boy", "the man at the bar.", "O'Brien"):
        assert names.not_a_name(ok) == "", ok
    assert not population.names_a_person(SAY_PHRASE)


def test_the_reading_turns_a_quoted_target_into_what_is_said():
    """The owner's reading, as recorded in the turn log, grounded again: the target goes,
    the quotation becomes `says`, and nobody is sought."""
    raw = {"question": False, "claims": [], "actions": [
        {"act": "other", "target": "a friendly wink"},
        {"act": "talk", "target": SAY_PHRASE}]}
    frame, dropped = interpret.ground(raw, WINK)
    talk = frame["actions"][1]
    assert "target" not in talk
    assert talk["says"] == ("just trying to start a conversation and see what is "
                            "happening here.")
    assert any("speech, not somebody" in d for d in dropped)
    interpret.remember(WINK, frame)
    try:
        assert judgement.person_sought(WINK) == ""
        assert interpret.ops_for(frame) == ["say"]
    finally:
        interpret._READINGS.clear()


def test_the_detector_introduces_nobody_from_quoted_words():
    """Even with the bad reading still in hand, the introduce detector refuses the
    phrase: `_introducible` asks the shape too."""
    raw = {"question": False, "claims": [], "actions": [{"act": "talk", "target": SAY_PHRASE}]}
    interpret.remember(WINK, {"question": False, "claims": [], "actions": raw["actions"]})
    try:
        assert judgement._introducible(WINK) == ""
    finally:
        interpret._READINGS.clear()


def test_the_engine_refuses_to_introduce_quoted_words_and_says_why():
    from rules.dice import Dice
    from rules.engine import Engine

    s, _ = _scene()
    e = Engine(s, Dice(seed=1))
    before = set(s.people)
    res = e.run(e.validate([{"op": "introduce", "because": "t",
                             "params": {"who": SAY_PHRASE}}], origin="author:test"))
    assert set(s.people) == before, "c4 was minted under the player's words"
    assert "quoted words" in res.outcomes[0].tell
    assert "`say`" in res.outcomes[0].tell


# --- item 14: a people's name is never a person's --------------------------------------

LABORER_BEAT = ("The laborer—a man named Korvu, his face etched with the deep lines of a "
                "life spent under heavy loads—stops his struggle and looks up.")


def test_a_peoples_name_is_refused_as_a_persons():
    """The beat that renamed c11 "Korvu". The people's names come from the scene's own
    heritages here (no world): nothing is a list of Pangrella's names."""
    s, (laborer,) = _scene(("lone laborer", {"heritage": "Korvu"}))
    refused: list = []
    got = judgement.apply_introductions(s, LABORER_BEAT, "I walk up to the laborer",
                                        refused=refused)
    assert got == []
    assert laborer.name == "lone laborer"
    assert refused == [(laborer.ref, "Korvu", "a people of this world")]
    # And a person's name in the same sentence still lands.
    got = judgement.apply_introductions(
        s, LABORER_BEAT.replace("Korvu", "Aethorin Vex"), "I walk up to the laborer")
    assert got == [(laborer.ref, "Aethorin Vex")]


def test_the_face_line_reads_as_a_people_never_as_a_name():
    """The backstop line the model copied: "The merchant with a heavy pack is a Korvu: …"
    → "a man named Korvu". Both copies of the rule changed together."""
    from play import opening

    said = narration.a_face_for("merchant with a heavy pack",
                                "Korvu: Korvu have four limbs ending in sharp talons.")
    assert said.startswith("The merchant with a heavy pack is of the Korvu people: ")
    assert " a Korvu" not in said
    assert opening.face_line("The watchman", "Korvu: tall.").startswith(
        "The watchman is of the Korvu people: ")


# --- item 15: lines and faces on the right person ---------------------------------------

BEAT_2 = ("The man on the stool blinks, his eyes darting to the door, then to the man at "
          "the bar, and finally back to you. He finds his voice, but it is cracked. "
          "'What is going on?' he repeats, though this time it is a question. What do you "
          "do?")


def test_a_tag_on_somebody_the_beat_never_shows_is_withdrawn():
    """Market-talk beat 2: tagged to c1, the servant carrying jugs, who is nowhere in it;
    the page makes "the man" the speaker. Six beats ran this way, each opening a
    conversation with the servant."""
    s, (servant,) = _scene(("the servant carrying jugs two at a time", {}))
    said = [{"who": servant.ref, "to": "you", "line": "What is going on?"}]
    rows = judgement.doubt_tags(s, BEAT_2, said)
    assert said[0]["who"] == "" and said[0]["was"] == servant.ref
    assert rows and "the man the speaker" in rows[0]["why"]
    assert judgement.hailed_by(s, BEAT_2, said=said) == []


def test_a_tag_on_somebody_the_beat_shows_is_kept():
    """The control: the servant on the page, the tag stands — a tag is only ever
    withdrawn on the page's word, never re-pointed."""
    s, (servant,) = _scene(("the servant carrying jugs two at a time", {}))
    beat = BEAT_2.replace("The man on the stool", "The servant")
    said = [{"who": servant.ref, "to": "you", "line": "What is going on?"}]
    assert judgement.doubt_tags(s, beat, said) == []
    assert said[0]["who"] == servant.ref


CLERK_BEAT = (
    "You catch the clerk's eye, tilting your head just enough to let a hint of "
    "playfulness enter your gaze as you gesture to the heavy crate. \"A piece of work like "
    "this,\" you say, your voice dropping into a sultry lilt that seems to hang in the dry "
    "air of the counting house, \"deserves a bit more respect than just being weighed. "
    "It's a rare find, and I suspect you have a very keen eye for what is truly "
    "valuable.\" You let the silence stretch for a heartbeat, watching him. The clerk "
    "stops his work, the scale settling. How do you follow up?")
CLERK_LINE = "I smile and flirt with the clerk and offer the crate for coin."


def test_the_players_own_line_is_nobodys_on_the_board():
    """Items save beat 32: both halves of Kesst's line were booked as the clerk's (c12),
    by the sentence-before rule, because no clause rule knew "you" as a speaker."""
    from gm.checks._quotes import pc_lines, speakers

    s, (clerk,) = _scene(("the clerk of the counting house", {}))
    lines = [ln for _, _, ln in pc_lines(CLERK_BEAT, (), "Kesst Vayr")]
    assert lines == ["A piece of work like this,",
                     "deserves a bit more respect than just being weighed. It's a rare "
                     "find, and I suspect you have a very keen eye for what is truly "
                     "valuable."]
    assert all(ref == "" for *_, ref in speakers(CLERK_BEAT, (), dict(s.actors)))
    assert judgement.hailed_by(s, CLERK_BEAT) == []


def test_the_page_pinned_description_is_that_person_not_a_new_man():
    """Market-talk beat 14: "The man in the heavy coat (c4)" spoke, and the attribution
    found "man", made c6 out of a record and gave him c4's lines."""
    from play.aftermath.speaker_real import _Room

    s, (c4,) = _scene(("somebody", {}))
    narr = f"The man in the heavy coat ({c4.ref}) leans against a timber post."
    room = _Room(SimpleNamespace(scene=s, attribution=None), narr)
    kinds = [(k, ident) for _a, _b, k, ident in room.mentions(narr)]
    assert kinds == [("board", c4.ref)]


def test_a_face_is_not_placed_beside_another_persons_sentence():
    beat = ("Beside you, the servant (c1) shifts the jugs. The man in the heavy coat (c4) "
            "leans against a timber post. A man by the stalls watches. What do you do?")
    out = narration.place_the_face(beat, "man", "The man is of the Korvu people: x.",
                                   ref="c6")
    assert "timber post. The man is of the Korvu" not in out
    assert "A man by the stalls watches. The man is of the Korvu" in out


# --- item 16: the narrator never speaks for the player's character ----------------------

def _ctx(text, player, said=(), intimate=False):
    s, _ = _scene(("the clerk of the counting house", {}))
    return SimpleNamespace(text=text, player_text=player, said=tuple(said), scene=s,
                           intimate=intimate)


def test_the_invented_line_is_found_and_cut():
    """Items beat 32, after `own_words_only` had already dropped the plan's invented
    `say`: the page gave Kesst 38 words she never wrote. Nothing caught it, because the
    rule had only ever been the prompt's."""
    from gm import checks
    from gm.checks import speaks_for_player as sfp

    assert checks.owner_of("speaks-for-the-player") is sfp
    ctx = _ctx(CLERK_BEAT, CLERK_LINE)
    found = sfp.find(ctx)
    assert [f.kind for f in found] == ["speaks-for-the-player"]
    assert found[0].sentences[0].startswith('"A piece of work like this," you say')
    assert all(s in CLERK_BEAT for s in found[0].sentences)
    out, notes = sfp.backstop(ctx, CLERK_BEAT, found)
    assert "piece of work" not in out and "you say" not in out
    assert "as you gesture to the heavy crate. You let the silence stretch" in out
    assert '"' not in out
    assert notes


def test_the_players_own_words_said_back_pass():
    """Market-talk beat 4: "You speak clearly, 'Just trying to start a conversation…'" —
    the player's own words, which the narrator may say."""
    from gm.checks import speaks_for_player as sfp

    beat = ("You stand before him. You speak clearly, 'Just trying to start a "
            "conversation and see what is happening here.' What do you do?")
    assert sfp.find(_ctx(beat, WINK)) == []


def test_an_invented_line_gives_way_to_the_players_quoted_words():
    from gm.checks import speaks_for_player as sfp

    beat = ("You lean on the bar. \"Two silver, and not a copper more,\" you say. The "
            "barkeep shrugs. What do you do?")
    player = 'I lean on the bar and say "Is there work going?"'
    ctx = _ctx(beat, player)
    found = sfp.find(ctx)
    assert found
    out, _ = sfp.backstop(ctx, beat, found)
    assert "Two silver" not in out
    assert "You say, “Is there work going?”" in out


def test_the_intimate_table_is_exempt():
    """The owner's ruling of 2026-10-01: at an explicit table's intimate scene, and only
    there, the narrator may speak for the player's character."""
    from gm.checks import speaks_for_player as sfp

    assert sfp.find(_ctx(CLERK_BEAT, CLERK_LINE, intimate=True)) == []


def test_a_tag_naming_the_player_is_the_players_line():
    from gm.checks import speaks_for_player as sfp

    beat = "The clerk waits. 'I could take it off your hands,' comes the answer. Well?"
    said = [{"who": "pc", "to": "", "line": "I could take it off your hands,"}]
    assert sfp.find(_ctx(beat, CLERK_LINE, said=said))


# --- existing saves are repaired on load -------------------------------------------------

def test_an_old_save_gives_both_misnamed_people_their_descriptions_back():
    """c4 named with the player's words and c11 named after his people, as the saves
    hold them: c4 gets the description the page pinned to his ref, c11 his record's own
    words, and the record and the cast follow. A second load changes nothing."""
    from rules import person_words
    from rules.sheet import Actor

    s, _ = _scene()
    c4 = Actor(ref="c4", name=SAY_PHRASE, from_template="guildhand")
    s.add(c4)
    rec4 = population.note(s, SAY_PHRASE)
    rec4["ref"] = "c4"
    s.cast.append({"who": SAY_PHRASE, "turn": 4, "ref": "c4"})
    c11 = Actor(ref="c11", name="Korvu", true_name="Korvu", from_template="guildhand",
                heritage="Korvu")
    s.add(c11)
    rec11 = population.note(s, "lone laborer")
    rec11["ref"] = "c11"
    transcript = [{"who": "gm", "text": "The man in the heavy coat (c4) leans against a "
                                        "timber post."}]
    done = {r: (old, new) for r, old, new in
            person_words.heal_phrase_names(s, None, transcript)}
    assert done == {"c4": (SAY_PHRASE, "man in the heavy coat"),
                    "c11": ("Korvu", "lone laborer")}
    assert rec4["phrase"] == "man in the heavy coat"
    assert s.cast[-1]["who"] == "man in the heavy coat"
    assert c11.true_name == "", "no world to draw a name from: none, never 'Korvu'"
    assert person_words.heal_phrase_names(s, None, transcript) == []

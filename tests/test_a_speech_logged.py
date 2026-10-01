"""Item 1 of docs/playtest-2026-09-30.md: NPC speech missing from the conversation log.

"not sure if the ratfolk was talking to me but if he was then the conversation wasn't
stored in the conversation log." Measured over Sam's save: 37 of 43 real NPC lines reached
the log; 6 did not, at beats 0, 3, 33 and 49. The causes, each held here:

  1. the opening threw its speech records away (`opening_prose._ask` lifted the tags and
     discarded them), so the cage owner's opening lines never logged — the Q48 test passed
     only because it built the records by hand;
  2. an untagged line the page attributes to somebody on the board wrote a miss row and
     no `said` record, and a beat whose lines held no "you" was not read at all;
  3. rule 3 did not carry a sentence-initial "They", rule 2 ignored a tagged line before;
  4. a rewrite that reworded a tagged quote lost its speaker.

Replayed on the save's own beats, the new rules attribute beat 0 to the cage owner twice,
beat 3 to the cage owner once, and beat 49's run-on to the guard twice — the 5 lines of
those beats that were missing.

The beats below are the save's own text, verbatim.
"""
from __future__ import annotations

import json

import pytest
from django.test import override_settings

from gm import speech
from play import aftermath
from play.aftermath import speaker_real

BEAT_0 = (
    "In the cleared space at the middle, a fighter lies where the last blow put them, and "
    "the crowd has gone quiet in the wrong way. The cage owner, a Ratfolk with "
    "grey-streaked fur and a stoop to their frame, speaks over a shoulder while one hand "
    "clears the crowd. 'Went down in the second and has not got up,' the cage owner says, "
    "their voice steady. 'The last one who looked wanted paying first, and I am not paying "
    "twice.'\n\nThe cage owner stops at the edge of the cleared ground and steps back to "
    "let you through. What do you do?")
BEAT_3 = (
    "The pressure of your hands against the jagged wound works. The wound is deep, and the "
    "man's condition is critical, but the immediate threat of him bleeding out into the "
    "dirt of the back streets has been checked for now. \n\nThe cage owner watches your "
    "hands with unblinking eyes, their expression unreadable but their posture tense. They "
    "lean in slightly, their voice a dry rasp that cuts through the heavy silence of the "
    "surrounding crowd. \n\n\"He's still with us, but the road is long and his blood is "
    "thin. You've stopped the worst of it, but he's fading. You'll need to work fast if "
    "you want him to see the next hour.\"\n\nWhat do you do?")
BEAT_49 = (
    "The Ratfolk guard pauses, his hand still resting on his pommel. He looks at you, then "
    "at the crowd of skeptical-faced locals, and a slow, knowing grin spreads across his "
    "muzzle. 'A brothel, eh?' He chuckles, the sound raspy in his throat. 'There’s a place "
    "tucked down in the back streets, just past the tannery. Not the finest place for a "
    "gentleman's reputation, but the women there are... accommodating.' He winks at you, "
    "then gestures with a thumb toward the cluster of buildings leading away from the "
    "gate. 'If you're looking for \"freedom,\" that's the place to find it. Just watch "
    "your coin.' He goes back to his post. What do you do?")


@pytest.fixture
def sam(tmp_path):
    """A campaign with the opening's two people standing by: the cage owner and the
    beaten fighter, as Sam's save names them."""
    from play import campaign as cm
    from rules.bestiary import instantiate
    from rules.sheet import load_pc

    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        owner = c.scene.add(instantiate("guildhand", scene=c.scene,
                                        name="the cage owner")).ref
        fighter = c.scene.add(instantiate("guildhand", scene=c.scene,
                                          name="the beaten fighter")).ref
        c._opening_said = []
        c.scene.conversation_log = []
        yield {"c": c, "owner": owner, "fighter": fighter}


def _people(c, text, said):
    return speaker_real.step(aftermath.context("people", "turn", c, text=text, said=said))


def test_the_openings_untagged_lines_are_the_cage_owners_and_are_logged(sam):
    """Beat 0: two lines, "'…,' the cage owner says" and its run-on. Neither holds "you",
    so the old reader returned before reading them; now both are booked and logged."""
    c, owner = sam["c"], sam["owner"]
    c.transcript.append({"who": "gm", "kind": "setup", "text": BEAT_0})
    aftermath.after_opening(c)
    log = [e for e in c.scene.conversation_log if e["kind"] == "line"]
    assert [(e["who"], e["src"]) for e in log] == [(owner, "page"), (owner, "page")]
    assert [e["text"] for e in log] == [ln.strip() for ln in speech.lines(BEAT_0)]
    assert [r["who"] for r in c.transcript[-1]["said"]] == [owner, owner]


def test_the_openings_own_speaker_tags_are_kept(sam, monkeypatch):
    """The written opening's tags were lifted and thrown away. `_ask` now hands the
    records back, read against the people the opening was written with."""
    from play import opening_prose

    c, owner = sam["c"], sam["owner"]

    class _Reply:
        text = json.dumps({"opening": "The cage owner turns. <say who=\"the cage owner\" "
                                      "to=you>'You took your time.'</say>",
                           "suggestions": []})

        def json(self):
            return json.loads(self.text)

    monkeypatch.setattr(opening_prose.client, "chat", lambda *a, **k: _Reply())
    heard: list = []
    text, _ = opening_prose._ask([], {"model": "m"}, opening_prose._roster(c), heard)
    assert text == "The cage owner turns. 'You took your time.'"
    assert heard == [{"who": owner, "to": "you", "line": "You took your time."}]
    # And `after_opening` puts them on the beat and logs them as tagged.
    c._opening_said = heard
    c.transcript.append({"who": "gm", "kind": "setup", "text": text})
    aftermath.after_opening(c)
    assert c.transcript[-1]["said"][0]["who"] == owner
    (entry,) = [e for e in c.scene.conversation_log if e["kind"] == "line"]
    assert (entry["who"], entry["src"]) == (owner, "tag")


def test_a_sentence_initial_they_carries_the_cage_owner(sam):
    """Beat 3: the line stands in its own paragraph after "They lean in slightly…", which
    names nobody; the "They" carries the nearest person described before it."""
    c, owner = sam["c"], sam["owner"]
    said: list = []
    _people(c, BEAT_3, said)
    assert [(r["who"], r["to"], r["from"]) for r in said] == [(owner, "you", "page")]


def test_a_run_on_after_a_tagged_line_is_the_same_speaker(sam):
    """Beat 49: "'A brothel, eh?'" was tagged to the guard, and his two lines after it in
    the same paragraph were not — rule 2 read only untagged lines before."""
    from rules.bestiary import instantiate

    c = sam["c"]
    guard = c.scene.add(instantiate("guildhand", scene=c.scene, name="guard")).ref
    said = [{"who": guard, "to": "you", "line": "A brothel, eh?"}]
    rows = _people(c, BEAT_49, said)
    assert [r["who"] for r in said] == [guard, guard, guard]
    assert [r.get("from") for r in said[1:]] == ["page", "page"]
    assert any(r.get("booked") == guard and r.get("lines") == 2 for r in rows)


def test_in_a_fight_a_board_line_is_still_booked_and_nobody_is_made(sam, monkeypatch):
    c, owner = sam["c"], sam["owner"]
    monkeypatch.setattr(type(c.scene), "in_encounter", property(lambda self: True))
    said: list = []
    before = set(c.scene.actors)
    _people(c, BEAT_0, said)
    assert [r["who"] for r in said] == [owner, owner]
    assert set(c.scene.actors) == before


def test_a_reworded_tagged_line_is_realigned_to_its_quote():
    """Cause 4: a rewrite reworded a tagged quote and the record matched nothing. Six in
    ten words shared and one candidate: the record follows its line."""
    from play.views import _realigned

    text = "Gorm nods. 'Depends on the lady, friend, and on your purse.' He waits."
    records = [{"who": "c8", "to": "you", "line": "Depends on the lady and your purse."}]
    (moved,) = _realigned(records, [], text)
    assert moved["line"] == "Depends on the lady, friend, and on your purse."
    assert moved["realigned"] is True
    # A quote that merely shares a few words is not the same line.
    assert _realigned(records, [], "Gorm nods. 'The lady is busy tonight.'") == []

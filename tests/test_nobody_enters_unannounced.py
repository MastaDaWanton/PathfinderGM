"""People may enter a scene, but they enter in the prose.

Reported 2026-09-24 with the panel on screen. Korgath Varn, mid-conversation, spoke of
"the elder-quarter, where the oldest things in Vormoor are kept by those who remember the
world before the Long Peace" — and the next state showed **elder c9 · Bystander** standing
in the lane, with Korgath's own line now carrying "The elder is an Orc: Powerfully
built…" in the middle of it. *"an elder was brought into the scene mid conversation with
no description of him coming into the lane he just spawned in ... they need to enter in
the prose as well ... the conversation would not continue as if nothing happened."*

Three faults, each measured on that beat:

  1. The speech stripper capped a quotation at 300 characters; Korgath's third line ran
     to 600, so the stripper left it as narration and every reader downstream took a
     character's words for the narrator's.
  2. The cast ledger read "the elder-quarter" as "the elder": a role word followed by a
     hyphen is half of a compound, not a person.
  3. Promotion stood anybody the ledger booked in the room. A person only spoken OF —
     in somebody's line, or in a clause about somewhere else — is a mention, and a
     mention has no body.
"""
from __future__ import annotations

from gm import judgement, narration
from rules.bestiary import instantiate
from rules.engine import Scene

KORGATH = (
    "Korgath watches you, his tusks gleaming in the low light. He lets out a slow, raspy "
    "chuckle. 'A man of focus. I can respect that,' he says, his voice dropping to a "
    "conspiratorial rasp. 'Most people talk of safety because they lack the stomach for "
    "the truth. If you truly don't care for the safety, then you're looking for the "
    "shortcuts—the ones that bypass the guild's oversight and the long walk through the "
    "official gates. ' He leans in closer. 'If it's the leaf you want, and the path to it "
    "is what matters, then we have a choice. We can go to the lower docks, where the "
    "shadow-market breathes in the salt-mist, or we can head toward the elder-quarter, "
    "where the oldest things in Vormoor are kept by those who remember the world before "
    "the Long Peace. The elder keeps them, and the elder does not forget a face. ' He taps "
    "a thick, scarred finger on the table. 'Which path will you take? '. What do you do?")


def _scene():
    s = Scene(location_id="t")
    pc = instantiate("guildhand", scene=s, name="Spree")
    pc.kind = "pc"
    s.add(pc)
    korgath = instantiate("guildhand", scene=s, name="Korgath Varn")
    s.add(korgath)
    return s, pc, korgath


class TestALongSpeechIsStillSpeech:
    def test_the_third_line_is_stripped_with_the_rest(self):
        plain = narration.unquoted(KORGATH)
        assert "elder-quarter" not in plain
        assert "Korgath watches you" in plain and "He leans in closer." in plain

    def test_and_so_the_ledger_books_nobody_out_of_it(self):
        s, pc, korgath = _scene()
        before = len(s.cast)
        judgement.note_cast(s, KORGATH, turn=3)
        assert [e["who"] for e in s.cast[before:]] == []


class TestAHyphenIsACompound:
    def test_the_elder_quarter_is_a_quarter(self):
        s, pc, korgath = _scene()
        judgement.note_cast(s, "You take the road toward the elder-quarter.", turn=3)
        assert not any(e["who"] == "elder" for e in s.cast)

    def test_the_elder_alone_is_a_person(self):
        s, pc, korgath = _scene()
        judgement.note_cast(s, "An elder steps out of the doorway ahead of you.", turn=3)
        assert any(e["who"] == "elder" for e in s.cast)


class TestOnlySomebodyInTheRoomIsPromoted:
    def test_a_person_who_arrives_in_the_prose_is_stood_in_the_scene(self):
        s, pc, korgath = _scene()
        beat = ("Korgath stops for a moment and looks behind him as an elder begins "
                "walking toward the two of you, slow on a stick.")
        added = judgement.note_cast(s, beat, turn=3)
        made = judgement.promote_cast(s, added, beat=beat)
        assert made == ["elder"]
        assert any(a.name == "elder" for a in s.actors.values())

    def test_a_person_only_spoken_of_stays_a_mention(self):
        s, pc, korgath = _scene()
        beat = ("Korgath shrugs. The elder of the far quarter is the one who remembers "
                "it, or so people say.")
        added = judgement.note_cast(s, beat, turn=3)
        made = judgement.promote_cast(s, added, beat=beat)
        assert made == []
        assert not any(a.name == "elder" for a in s.actors.values())
        # ...and the mention is kept, with nobody behind it.
        assert any(e["who"] == "elder" and not e.get("ref") for e in s.cast)

    def test_the_test_itself_is_narration_only(self):
        assert judgement.present_in_scene(
            "'A woman waits by the door,' he says. You are alone.", "woman") is False
        assert judgement.present_in_scene(
            "A woman waits by the door.", "woman") is True

    def test_with_no_beat_to_judge_against_nobody_is_refused(self):
        """Conservative: most callers promote without the beat, and the 2026-09-18
        lesson is that a person kept off the board is worse than one wrongly on it."""
        assert judgement.present_in_scene("", "boy") is True
        assert judgement.present_in_scene("A boy darts between the stalls.", "boy") is True
        assert judgement.present_in_scene("There is a man in the corner.", "man") is True
        assert judgement.present_in_scene(
            "The guards at the gate are sharp tonight.", "guard") is False

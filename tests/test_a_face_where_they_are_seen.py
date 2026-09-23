"""A face is said where the person is seen, not at the end of the beat.

Reported 2026-09-22, with the beat on screen:

> *"the description of Ashla is tagged to the end as an after thought. if she was next to
> drenn she should have been described right after i saw drenn."*

What the page showed, after a long paragraph that had introduced Drenn and then Ashla:

    … They gesture slightly to the space between you, inviting a conversation away from
    the passing throng. What do you do? Ashla ironvale: Orc: Powerfully built, prominent
    lower tusks, thick hide that resists minor scarring.

Three faults in one line, and the position is only the one that was reported:

  1. **Position.** The backstop appended, always — after the hand-back, eight sentences
     after the person was named. That reads as an afterthought because it structurally
     is one.
  2. **The name was mangled**: `definite(name).capitalize()` lowercases everything after
     the first letter, so "Ashla Ironvale" became "Ashla ironvale". CLAUDE.md already
     records `capitalize()` eating a name once ("Troop, Goblin"); this is the second
     time, in a different file.
  3. **Two colons doing one job.** `names.appearance_for` already joins the people and
     their body line with one — "Orc: Powerfully built…" — so the label added a second
     and the result read as a stat block rather than as something a person would notice.
"""
from __future__ import annotations

from gm import narration

BODY = "Orc: Powerfully built, prominent lower tusks, thick hide that resists minor scarring."
BEAT = ("You weave through the crowd until you reach the centre of the exchange. "
        "There, standing amidst a cluster of fabrics, is Drenn Ironvale. "
        "Ashla Ironvale keeps a pace behind them, watching the road. "
        "Drenn moves forward and stops just before you. What do you do?")


class TestTheLine:
    def test_the_name_keeps_its_capitals(self):
        """The reported string said "Ashla ironvale"."""
        said = narration.a_face_for("Ashla Ironvale", BODY)
        assert "Ashla Ironvale" in said
        assert "ironvale" not in said

    def test_it_reads_as_a_sentence_rather_than_a_stat_block(self):
        said = narration.a_face_for("Ashla Ironvale", BODY)
        assert said.startswith("Ashla Ironvale is an Orc: ")
        assert said.count(":") == 1

    def test_the_article_agrees(self):
        assert narration.a_face_for("X", "Orc: tall.").startswith("X is an Orc")
        assert narration.a_face_for("X", "Korvu: tall.").startswith("X is a Korvu")

    def test_the_bodys_own_case_is_left_alone(self):
        """`opening._clause`'s rule: lower-casing reads better on "Powerfully built" and
        turns "Korvu have four limbs" into "korvu have four limbs", which is this app
        respelling one of the world's own names."""
        said = narration.a_face_for("the drover", "Korvu: Korvu have four limbs.")
        assert "Korvu have four limbs" in said

    def test_a_residents_own_words_keep_the_label_form(self):
        """Free text from the world's `Appearance` fact: there is no reliable sentence to
        make of it without writing it ourselves."""
        said = narration.a_face_for("Drenn Ironvale", "favors plain dress")
        assert said == "Drenn Ironvale: favors plain dress"

    def test_a_common_noun_takes_its_article(self):
        assert narration.a_face_for("sailor", "Orc: tall.").startswith("The sailor is")

    def test_nothing_in_nothing_out(self):
        assert narration.a_face_for("", BODY) == ""
        assert narration.a_face_for("Ashla", "") == ""


class TestWhereItGoes:
    def _placed(self, name, beat=BEAT):
        return narration.place_the_face(beat, name, narration.a_face_for(name, BODY))

    def test_it_follows_the_sentence_that_names_them(self):
        out = self._placed("Ashla Ironvale")
        assert "watching the road. Ashla Ironvale is an Orc" in out

    def test_it_is_no_longer_behind_the_hand_back(self):
        out = self._placed("Ashla Ironvale")
        assert out.rstrip().endswith("What do you do?")

    def test_a_shared_surname_does_not_steal_the_position(self):
        """Measured on the reported beat: `_sentences_about` matches on STEMS, which is
        right for "the crier working through the notices" answering to "the crier" and
        wrong here — "Ashla Ironvale" matched DRENN Ironvale's sentence on the surname,
        and the face landed before she had been mentioned at all. It read correctly in
        that beat by luck and would not in the next one."""
        out = self._placed("Ashla Ironvale")
        drenn = out.index("is Drenn Ironvale")
        face = out.index("Ashla Ironvale is an Orc")
        hers = out.index("Ashla Ironvale keeps a pace")
        assert drenn < hers < face

    def test_a_descriptor_for_a_name_still_finds_its_sentence(self):
        beat = "The crier works through the notices. You wait. What do you do?"
        out = narration.place_the_face(
            beat, "the crier working through the notices",
            narration.a_face_for("the crier working through the notices", BODY))
        assert out.index("is an Orc") < out.index("You wait")

    def test_somebody_the_beat_never_names_is_still_said_before_the_hand_back(self):
        """The case the append was written for — a person the prose used without ever
        calling them anything. Appending is right; appending AFTER the question is not."""
        beat = "The queue shuffles forward and nobody speaks. What do you do?"
        out = narration.place_the_face(beat, "Marra",
                                       narration.a_face_for("Marra", BODY))
        assert out.rstrip().endswith("What do you do?")
        assert "Marra is an Orc" in out

    def test_a_beat_with_no_hand_back_takes_it_at_the_end(self):
        beat = "The queue shuffles forward and nobody speaks."
        out = narration.place_the_face(beat, "Marra",
                                       narration.a_face_for("Marra", BODY))
        assert out.rstrip().endswith(".")
        assert "Marra is an Orc" in out

    def test_nothing_is_edited_only_added(self):
        """The rule this file keeps everywhere: a deterministic backstop may add a
        sentence and may cut one, never edit one."""
        out = self._placed("Ashla Ironvale")
        for sentence in ("You weave through the crowd until you reach the centre of the "
                         "exchange.",
                         "There, standing amidst a cluster of fabrics, is Drenn Ironvale.",
                         "Ashla Ironvale keeps a pace behind them, watching the road.",
                         "Drenn moves forward and stops just before you."):
            assert sentence in out

    def test_an_empty_line_changes_nothing(self):
        assert narration.place_the_face(BEAT, "Ashla Ironvale", "") == BEAT

    def test_somebody_introduced_by_speaking_is_still_described_where_they_speak(self):
        """Found 2026-09-23 reviewing the fix above: the naming sentence was looked up in
        `unquoted()` prose, which collapses each quotation to a space, and then searched
        for in the ORIGINAL with `find` — which missed whenever the person had said
        anything, and fell back to appending after the hand-back. People are named
        when they speak, so this was the common case wearing the reported fault."""
        beat = ('Drenn nods. Ashla Ironvale says "we should go" and looks at the road. '
                'What do you do?')
        out = narration.place_the_face(beat, "Ashla Ironvale",
                                       narration.a_face_for("Ashla Ironvale", BODY))
        assert "looks at the road. Ashla Ironvale is an Orc" in out
        assert out.rstrip().endswith("What do you do?")

    def test_a_full_stop_inside_speech_does_not_cut_the_sentence(self):
        beat = ('Ashla Ironvale says "We go. Now." and turns away. What do you do?')
        out = narration.place_the_face(beat, "Ashla Ironvale",
                                       narration.a_face_for("Ashla Ironvale", BODY))
        assert '"We go. Now." and turns away. Ashla Ironvale is an Orc' in out


class TestTheViewUsesIt:
    def test_the_page_no_longer_capitalises_the_name_away(self):
        from pathlib import Path

        views = Path("play/views.py").read_text(encoding="utf-8")
        assert "definite(who.name).capitalize()" not in views
        assert "narration_mod.a_face_for(who.name, who.appearance)" in views
        assert "narration_mod.place_the_face(" in views

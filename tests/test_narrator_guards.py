"""The narrator's guards, and the two authored lines that were the narrator's worst tic.

Design record: docs/narrator-guards.md. What was measured before anything here existed,
2026-09-17:

  * `spooter.json` — eleven beats, four kills, **four byte-identical sentences**: "The
    blow does not so much fell sailor as unmake them — it carries through, and what
    folds to the ground is a ruin, dead before it lands." The player quoted "they are
    unmade" back as the phrase the narrator used "almost every single time I 1 punch an
    enemy". It was `press_the_death`'s top rung, one line deep, appended after grooming
    where no review could see it, with the actor's bare name pasted in ("fell sailor").
  * Why it fired every time: the model wrote a wounded man, `cut_dead_men_walking`
    deleted any sentence in which the freshly dead did anything not in `_DEAD_MAY` —
    "the sailor crumples to the deck and does not move" has none of those words — and
    with no death left on the page the template landed.
  * A sixty-turn baseline (gemma-4 12B, `--script long`): 58/60 clean, openings at 7%,
    and yet "the transition from the" in 12 of 53 beats, "to your left the" in 9, "the
    silence of the" in 7 — invisible to every check, which read openings and whole
    sentences only. And `keep_the_thread`'s one anchor sentence verbatim in 4 beats,
    carrying "who I should speak to about work outside the walls" — the player's own
    first person — into the narration: one of the run's two faults, caused by us.
"""
from __future__ import annotations

import pytest

from gm import judgement, narration
from rules.engine import Scene


def _death(**over) -> dict:
    d = {"name": "sailor", "margin": 40, "hp_max": 11, "family": "bludgeoning",
         "subj": "he", "obj": "him", "poss": "his"}
    d.update(over)
    return d


# --- the death line ---------------------------------------------------------------------


def test_four_kills_no_longer_read_the_same():
    """The defect: four of four identical. A pool walked least-recently-used cannot
    hand the same line twice running, and the word the player quoted is gone."""
    said: dict = {}
    lines = [narration.death_line(_death(), said) for _ in range(4)]
    assert len(set(lines[:3])) == 3, lines
    assert lines[3] != lines[2]
    assert all("unma" not in line.lower() for line in lines)


def test_the_pool_is_walked_whole_before_a_line_returns():
    """The first cut inverted the pick and, once a pool of three had been used, gave the
    third line for ever — caught on the fifth kill of the smoke test. The oldest line is
    the one that comes back."""
    said: dict = {}
    first = [narration.death_line(_death(), said) for _ in range(3)]
    fourth = narration.death_line(_death(), said)
    fifth = narration.death_line(_death(), said)
    assert fourth == first[0] and fifth == first[1]


def test_every_line_in_every_pool_says_dead():
    """`death_on_the_page` is the one judge of whether a death reached the page, so a
    backstop whose own sentence it could not recognise would be pressed twice. Every
    line, every family, every bucket, both numbers."""
    for fam, buckets in narration._DEATHS.items():
        for bucket, pool in buckets.items():
            assert len(pool) >= 3, (fam, bucket)
            for line in pool:
                for subj, obj, poss in (("he", "him", "his"), ("they", "them", "their")):
                    out = narration._fill(line, "the sailor", subj, obj, poss)
                    assert narration.death_on_the_page(out, "the sailor"), out
                    assert "{" not in out and "}" not in out, out


def test_a_bare_noun_takes_the_article_and_a_name_does_not():
    """"fell sailor as unmake them": the actor was named `sailor` and the template
    pasted it in unchanged."""
    assert narration.definite("sailor") == "the sailor"
    assert narration.definite("guards") == "the guards"
    assert narration.definite("Grist Hollowmark") == "Grist Hollowmark"
    assert narration.definite("the watchman") == "the watchman"
    line = narration.death_line(_death(name="sailor"), {})
    assert "the sailor" in line.lower()
    assert " sailor as" not in line


def test_a_group_reads_as_a_group():
    """`guards (c8) - dead` was a real scene entry. A plural actor gets plural verbs and
    a capital letter wherever it opens a sentence, mid-line included."""
    for fam in narration._DEATHS:
        for bucket in ("barely", "ruinous", "overkill"):
            d = _death(name="guards", family=fam, subj="they", obj="them", poss="their",
                       margin={"barely": 1, "ruinous": 6, "overkill": 40}[bucket])
            out = narration.death_line(d, {})
            assert "the guards is" not in out and "they is" not in out, out
            assert "the guards has" not in out and "they has" not in out, out
            assert ". the guards" not in out, out
            assert out[0].isupper(), out


def test_the_axes_are_the_blow_and_the_margin():
    """ROM's share-of-the-victim and CircleMUD's attack-type pools: the same actor dies
    differently by what hit them and by how far past dead it went."""
    assert narration.death_family("bludgeoning and piercing") == "bludgeoning"
    assert narration.death_family("fire") == "fire"
    assert narration.death_family("electricity") == "other"
    assert narration.death_bucket(1, 11) == "barely"
    assert narration.death_bucket(6, 11) == "ruinous"
    assert narration.death_bucket(11, 11) == "overkill"
    fire = narration.death_line(_death(family="fire"), {})
    club = narration.death_line(_death(family="bludgeoning"), {})
    assert fire != club


def test_press_the_death_is_the_backstop_and_leaves_a_committed_death_alone():
    text = "You swing and the sailor drops, dead before he hits the deck. What do you do?"
    same, added = narration.press_the_death(text, [_death()], said={})
    assert same == text and not added


# --- the killing sentence survives ------------------------------------------------------


def test_a_fresh_kills_own_sentence_is_not_a_dead_man_walking():
    """The mechanism behind four-of-four: the model's death sentence was cut as a
    corpse acting, and the template filled the hole."""
    beat = ("Your fist connects with a wet crack. The sailor crumples to the deck and "
            "does not move. Somebody screams. What do you do?")
    kept, cut = narration.cut_dead_men_walking(beat, ["sailor"], fresh=["sailor"])
    assert not cut and "crumples" in kept
    # Without the fresh list the old rule stands, which is what the long-dead need.
    kept2, cut2 = narration.cut_dead_men_walking(beat, ["sailor"])
    assert cut2 == ["The sailor crumples to the deck and does not move."]


def test_the_long_dead_still_may_not_collapse_again():
    """"the stranger collapses" two turns after he died is the resurrection the cut
    exists for; freshness is this turn's kills only."""
    beat = "The stranger collapses again with a groan. What do you do?"
    kept, cut = narration.cut_dead_men_walking(beat, ["stranger"], fresh=["sailor"])
    assert cut


def test_a_fresh_dead_man_who_speaks_is_still_cut():
    """Freshness spares the killing sentence, not the corpse's next line. (Not "spits
    blood": a sentence about the dead man's blood was already protected, rightly.)"""
    beat = "The sailor spits at you and swears. What do you do?"
    kept, cut = narration.cut_dead_men_walking(beat, ["sailor"], fresh=["sailor"])
    assert cut, "speech is not a death"


# --- the death is a finding -------------------------------------------------------------


def test_a_death_left_off_the_page_is_a_finding_with_the_facts_named():
    """The repair that has held everywhere here is the one handed something specific
    to write. The hint carries who, by what, and how far past dead — in words."""
    r = narration.review("You swing and the sailor staggers back, clutching his chest. "
                         "What do you do?", deaths=[_death()])
    kinds = {f.kind for f in r.findings}
    assert "death-left-off-the-page" in kinds
    f = next(f for f in r.findings if f.kind == "death-left-off-the-page")
    assert f.weight == 3
    assert "the sailor" in f.fix_hint and "bludgeoning" in f.fix_hint
    assert "carries through" in f.fix_hint          # the overkill bucket, in words
    assert not any(ch.isdigit() for ch in f.fix_hint), "no number reaches the model"


def test_a_death_on_the_page_raises_nothing():
    r = narration.review("You swing and the sailor drops, dead before he hits the deck. "
                         "What do you do?", deaths=[_death()])
    assert "death-left-off-the-page" not in {f.kind for f in r.findings}


# --- the narrator measured against itself -----------------------------------------------

EARLIER = [
    "The transition from the forge's heat to the drafty hallway is jarring. A cart "
    "rattles past outside. What do you do?",
    "You step out. The transition from the dim shop to the white street makes you "
    "blink. A dog barks somewhere. What do you do?",
    "The transition from the quiet lane to the market's roar is sudden. A woman is "
    "shouting prices. What do you do?",
]


def test_recurring_phrases_sees_what_the_opening_check_cannot():
    """"the transition from the" in 12 of 53 beats, never at the start of a turn, and
    never a whole sentence repeated — so nothing saw it."""
    now = ("Rain has started. The transition from the warm taproom to the yard is a "
           "shock. What do you do?")
    tics = narration.recurring_phrases(now, EARLIER)
    assert tics and tics[0][0] == "the transition from the" and tics[0][1] == 3
    r = narration.review(now, earlier=EARLIER)
    f = next(f for f in r.findings if f.kind == "recurring-phrase")
    assert "'the transition from the'" in f.fix_hint


def test_two_uses_are_not_yet_a_tic():
    now = ("Rain has started. The transition from the warm taproom to the yard is a "
           "shock. What do you do?")
    assert narration.recurring_phrases(now, EARLIER[:2]) == []


def test_function_words_speech_and_the_hand_back_are_not_tics():
    """"and then it is" is English; "What do you do?" is the required hand-back; a
    character may say the same thing every day."""
    earlier = ["Nobody moves, and then it is over. 'Mind the step, friend.' What do you "
               "do?"] * 5
    now = "The rain stops, and then it is quiet. 'Mind the step, friend.' What do you do?"
    assert narration.recurring_phrases(now, earlier) == []


def test_a_lifted_clause_is_caught_on_its_third_appearance_and_not_its_second():
    """Six words shared with two recent beats is a clause being copied. Not one:
    calibrated on the baseline, "any of the last eight" fired on 29 of 56 beats, most
    of them a beat honestly continuing the scene of the beat before it."""
    line = "The old man ahead of you shifts his weight off the bad leg. What do you do?"
    now = ("Behind you the old man ahead of you shifts his weight off the bad leg again. "
           "What do you do?")
    assert narration.recurring_phrases(now, [line]) == []
    tics = narration.recurring_phrases(now, [line, "Rain. What do you do?", line])
    assert tics and tics[0][1] == 2
    assert len(tics[0][0].split()) == narration.LIFT_LENGTH


def test_a_proper_name_recurring_is_the_world_not_a_formula():
    """"the Guild of Salt and Timber" every few beats is where the player is."""
    earlier = ["You cross to the Guild of Salt and Timber. The doors are shut. What do you do?"] * 4
    now = "The Guild of Salt and Timber has lit its lamps. What do you do?"
    assert narration.recurring_phrases(now, earlier) == []


def test_self_repetition_and_compression_measure_a_run():
    same = ["The heavy oak door groans as you push it wide and step into the gloom "
            "beyond it. What do you do?"] * 6
    varied = [
        "The heavy oak door groans as you push it wide. What do you do?",
        "Rain finds the back of your neck before you find the gate. What do you do?",
        "Somebody is singing badly two streets over. What do you do?",
        "The smith does not look up from the blade on his anvil. What do you do?",
        "Your boots are louder on the flagstones than you would like. What do you do?",
        "A child stares at your sword and then at your face. What do you do?",
    ]
    assert narration.self_repetition(same)["score"] == 1.0
    assert narration.self_repetition(varied)["score"] < 0.2
    assert narration.compression_ratio(same) > narration.compression_ratio(varied)
    assert narration.compression_ratio([]) == 0.0


# --- the thread anchor ------------------------------------------------------------------


def test_the_thread_anchor_no_longer_repeats_itself():
    """One anchor shape, four times in fifty-three beats. Five shapes, least recently
    used."""
    thread = {"subject": "the two guards", "doing": "following"}
    said: dict = {}
    outs = {narration.keep_the_thread("You push into the house. What do you do?",
                                      thread, said=said)[0] for _ in range(5)}
    assert len(outs) == 5
    assert all("the two guards" in o and o.endswith("What do you do?") for o in outs)


def test_a_question_is_not_an_engagement():
    """"I ask who I should speak to about work outside the walls" set the thread to a
    clause carrying the player's own "I", and the anchor shipped it as the narrator's."""
    s = Scene()
    judgement.update_thread(s, "I ask who I should speak to about work outside the walls")
    assert s.thread == {}
    judgement.update_thread(s, "I ask the smith about the ore he uses")
    assert "smith" in s.thread.get("subject", "")
    # An existing engagement stands when a question follows it.
    judgement.update_thread(s, "I ask what he would charge to mend a blade")
    assert "smith" in s.thread.get("subject", "")


def test_a_first_person_subject_never_reaches_the_page_as_the_narrators():
    """Belt and braces: a clause subject is refused outright, and a first-person token
    that somehow arrives is turned to the second person before it is placed."""
    out, anchored = narration.keep_the_thread(
        "The room is empty. What do you do?",
        {"subject": "who I should speak to", "doing": "talking to"}, said={})
    assert anchored == ""
    out, anchored = narration.keep_the_thread(
        "The room is empty. What do you do?",
        {"subject": "the man I saw at the gate", "doing": "following"}, said={})
    assert anchored and "the man you saw at the gate" in out
    assert not narration.narrator_in_first_person(out)


# --- our lines are never shown back as the model's --------------------------------------


def test_added_sentences_are_taken_back_out_of_what_the_model_is_shown():
    """Xu et al.: what the model is shown of its own past is what it reinforces. The
    beat the transcript keeps is whole; the beat the prose call is shown is the model's
    own."""
    before = "Your fist connects. Somebody screams. What do you do?"
    after, _ = narration.press_the_death(before, [_death()], said={})
    added = narration.added_sentences(before, after)
    assert len(added) >= 1 and any("dead" in a for a in added)
    shown = narration.strip_added(after, added)
    assert shown == before
    assert narration.strip_added(after, None) == after


def test_the_said_store_survives_a_save(tmp_path):
    """The walk through a pool lives on the scene, so a reload does not start every
    pool again at its first line."""
    from django.test import override_settings

    from play import campaign as cm
    from rules.sheet import load_pc

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        narration.death_line(_death(), c.scene.said)
        narration.death_line(_death(), c.scene.said)
        walked = dict(c.scene.said)
        assert walked == {"death:bludgeoning/overkill": [0, 1]}
        c.save()
        cm._LIVE.clear()
        again = cm.current()
        assert again.scene.said == walked
        cm._LIVE.clear()

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


# --- the scene as it stands now, last in the prompt -------------------------------------


class _Body:
    def __init__(self, name, *, pc=False, hp=10, down=False, dead=False, states=()):
        self.name, self.is_pc, self.hp, self.is_down = name, pc, hp, down or dead
        self._states = set(states) | ({"state.down.dead"} if dead else set())

    def has_state(self, tag: str) -> bool:
        return any(s == tag or s.startswith(tag + ".") for s in self._states)


class _Scene:
    def __init__(self, actors, *, fight=False, heat=None, thread=None):
        self.actors, self.in_encounter = actors, fight
        self.heat, self.thread, self.at = heat or {}, thread or {}, "market"


def test_a_quiet_town_gets_no_scene_block():
    """Empty when nothing is notable, so a quiet town is not told it is quiet."""
    from gm import prompts

    s = _Scene({"pc": _Body("Kesst", pc=True), "c1": _Body("the smith")})
    assert prompts.scene_now(s) == ""


def test_the_scene_block_names_the_dead_the_hostile_and_the_fight():
    """Measured with a screenshot: two dead in the square, the crowd scattering, and the
    beat opened on "a cacophony of commerce". The facts were in the brief's middle; this
    puts them last, assembled from state at the moment of writing."""
    from gm import prompts

    s = _Scene({"pc": _Body("Kesst", pc=True),
                "c7": _Body("the man", dead=True, hp=-9),
                "c8": _Body("the guards", states=("attitude.hostile",))},
               fight=True,
               heat={"note": "the player just killed the man in front of onlookers"},
               thread={"subject": "the crier", "doing": "watching"})
    block = prompts.scene_now(s)
    assert block.startswith("THE SCENE AS IT STANDS NOW")
    for fact in ("a fight is running", "dead on the ground here: the man",
                 "hostile towards the player: the guards", "in front of onlookers",
                 "watching the crier"):
        assert fact in block, fact
    assert not any(ch.isdigit() for ch in block)


def test_the_two_blocks_go_last_in_the_prose_prompt():
    """After the tells, where the shipped narrators put their author's note."""
    from gm import prompts

    msgs = prompts.call_prose_messages(
        "WORLD: Test.", [], "I look around.", ["The smith nods."],
        scene_now_block="THE SCENE AS IT STANDS NOW: a fight is running.",
        pull="STILL OPEN, NEAREST TO HAND: Find the salt — ask the harbourmaster.")
    last = msgs[-1]["content"]
    assert last.index("What the engine decided") < last.index("THE SCENE AS IT STANDS NOW")
    assert last.rstrip().endswith("ask the harbourmaster.")


# --- one thread to pull, chosen in code ---------------------------------------------------


def _table():
    from rules import cards
    from rules.engine import Scene

    s = Scene()
    s.at = "market"
    quest = cards.Card(id="q-salt", title="Find the missing salt",
                       facts=["Marra asked for word of the salt."],
                       keys=cards.keys_from("Find the missing salt", "Marra asked for word"),
                       tags=(cards.TAG_QUEST,), people=["c2"], kind="quest",
                       objectives=[{"text": "Ask the harbourmaster where the salt went",
                                    "done": False}], giver="c2", reward="a season's salt")
    strain = cards.Card(id="strain-vyrakon", title="What is wrong in Vyrakon",
                        facts=["Border tolls have doubled since the spring."],
                        keys=cards.keys_from("border tolls doubled spring"),
                        tags=(cards.TAG_STRAIN,), place="market")
    cards.open_card(s, quest, turn=0)
    cards.open_card(s, strain, turn=0)
    return s, cards


def test_the_pick_is_the_card_most_of_the_scene_points_at():
    """Ruskin's criteria count: the strain card is pinned here and the player's line
    names it (two of its keys); the quest is merely open (1). A world card qualifies
    only because the player SPOKE of it — pinned here alone would not do."""
    s, cards = _table()
    ranked = cards.salience(s, recent=[], player_text="I ask about the border tolls.",
                            turn=3)
    assert [c.id for _, _, c in ranked] == ["strain-vyrakon", "q-salt"]
    assert ranked[0][1] == ["here", "spoken"] and ranked[1][1] == ["open"]
    pull = cards.thread_to_pull(s, recent=[], player_text="I ask about the border tolls.",
                                turn=3)
    assert pull["title"] == "What is wrong in Vyrakon" and not pull["urgent"]
    assert pull["kind"] == "situation"


def test_the_worlds_own_cards_are_not_pulled_for_being_here():
    """Measured on the first run: fifty of fifty beats carried a pull, the same town
    strain or guild description up to eight times running, because "pinned to this
    place" was a criterion and one loose key in three beats made anything "recent".
    Ambient cards are the brief's business; they are pulled only when raised."""
    s, cards = _table()
    ranked = cards.salience(s, recent=["The smith hammers on."],
                            player_text="I look around.", turn=3)
    assert [c.id for _, _, c in ranked] == ["q-salt"]
    # The quest is the player's own matter and qualifies on "open" alone; it is not
    # quiet yet, so the pull says so without the "for a while" clause.
    pull = cards.thread_to_pull(s, recent=[], player_text="I look around.", turn=3)
    assert pull["title"] == "Find the missing salt" and "for a while" not in pull["text"]


def test_a_quiet_quest_gains_urgency_and_is_named_without_a_number():
    """Twenty transcript entries is about ten turns of play — the unit the constants
    are in, which the first cut got wrong by half."""
    s, cards = _table()
    pull = cards.thread_to_pull(s, recent=[], player_text="I look around.", turn=24)
    assert pull["title"] == "Find the missing salt" and pull["kind"] == "quest"
    assert "open" in pull["why"] and "quiet" in pull["why"] and "urgent" in pull["why"]
    assert pull["since"] == 24
    assert "Ask the harbourmaster" in pull["text"] and "for a while" in pull["text"]
    assert not any(ch.isdigit() for ch in pull["text"])


def test_time_alone_raises_nothing():
    """An old situation from another town is not a candidate because it is old."""
    s, cards = _table()
    s.at = "docks"
    ranked = cards.salience(s, recent=[], player_text="I look at the boats.", turn=24)
    assert [c.id for _, _, c in ranked] == ["q-salt"], "only the open quest qualifies"


def test_a_mention_is_written_back_and_the_matter_rests():
    """The write-back, and the cooldown it feeds. A card the beat just carried is
    marked mentioned, loses its urgency, and is not pulled again for about two turns
    of play — the first run pulled the same card eight times running because the beat
    that mentioned it put its words in the window that scored it."""
    s, cards = _table()
    carried = cards.note_mentions(
        s, "The harbourmaster spits. 'Salt? The salt went north with the toll-men.'",
        turn=11)
    assert carried == ["Find the missing salt"]
    assert cards.find(s, "q-salt").mentioned == 11
    # Resting: nothing else is the player's matter here, so nothing is pulled.
    assert cards.thread_to_pull(s, recent=[], player_text="I look around.", turn=12) is None
    # Past the cooldown it is back, and no longer quiet.
    pull = cards.thread_to_pull(s, recent=[], player_text="I look around.", turn=16)
    assert pull["title"] == "Find the missing salt"
    assert "quiet" not in pull["why"] and not pull["urgent"]
    # One identity word is a coincidence.
    assert cards.note_mentions(s, "You buy a pinch of salt for the road.", turn=17) == []


def test_identity_is_the_title_the_objectives_the_people_and_the_names_in_the_facts():
    """"between", "power" and "resources" are on most cards in the shipped world; the
    Khy'vyr and the Nirkor are on one. Sentence-opening capitals are not names."""
    from rules import cards

    c = cards.Card(id="s", title="What is wrong in Zhilvarnia",
                   facts=["Tensions between Khy'vyr and Nirkor populations are elevated. "
                          "Competition for land and resources drives it."],
                   keys=cards.keys_from("Zhilvarnia", "Tensions between Khy'vyr and Nirkor "
                                        "populations are elevated. Competition for land "
                                        "and resources drives it."))
    ident = cards.identity_keys(c, ["Marra"])
    assert "khy'vyr" in ident and "nirkor" in ident and "zhilvarnia" in ident
    assert "marra" in ident
    for loose in ("tensions", "between", "populations", "competition", "resources",
                  "elevated", "land"):
        assert loose not in ident, loose
    assert len(ident) < len(c.keys)
    # A beat about the two peoples carries the card; a beat about tensions in general
    # does not.
    assert cards._identity_hits(ident, "The Nirkor quarter is quiet; a Khy'vyr boy runs.") == 2
    assert cards._identity_hits(ident, "Tensions and competition for resources everywhere.") == 0


def test_review_asks_for_a_dropped_thread_only_for_an_urgent_uncarried_quest():
    """Eight fires in fifty turns on the first run, six of them on the world's strain
    cards with rewrites that came back unchanged. A quest the player took on is the
    matter that must not go quiet; a town's politics is colour."""
    pull = {"title": "Find the missing salt", "kind": "quest",
            "fact": "Ask the harbourmaster where the salt went",
            "keys": ["find", "missing", "salt", "harbourmaster"],
            "people": ["Marra"], "since": 24, "urgent": True}
    quiet = "The smith hammers on. Rain starts. What do you do?"
    r = narration.review(quiet, pull=pull)
    f = next(f for f in r.findings if f.kind == "drops-the-thread")
    assert f.weight == 2 and "harbourmaster" in f.fix_hint
    carried = "The smith hammers on. 'Marra was asking after you,' he says. What do you do?"
    assert "drops-the-thread" not in {f.kind for f in narration.review(carried, pull=pull).findings}
    assert "drops-the-thread" not in {
        f.kind for f in narration.review(quiet, pull=dict(pull, urgent=False)).findings}
    assert "drops-the-thread" not in {
        f.kind for f in narration.review(quiet, pull=dict(pull, kind="situation")).findings}


# --- what the model is shown of its own past -----------------------------------------------


def test_own_prose_is_the_narrators_setup_beats_stripped_of_ours_twelve_deep():
    """Measured on the first run after the guards: `transcript[-8:]` filtered to the GM
    left the twelve-beat phrase check four beats to read (it fired once in fifty turns),
    and the watcher's award line — filed as setup — was shown back as narration and
    opened four of the last nineteen beats in that register."""
    transcript = []
    for i in range(20):
        transcript.append({"who": "player", "text": f"I do thing {i}."})
        transcript.append({"who": "gm", "kind": "setup", "text": f"Beat {i} happens. What do you do?",
                           **({"added": ["The sailor drops, dead."]} if i == 19 else {})})
        if i % 5 == 0:
            transcript.append({"who": "gm", "kind": "consequence",
                               "text": "You gain 200 XP for moving a matter along: x (200 of 2,000)."})
    transcript[-1]["text"] = "Beat 19 happens. The sailor drops, dead. What do you do?"
    shown = narration.own_prose(transcript)
    assert len(shown) == 12
    assert shown[-1] == "Beat 19 happens. What do you do?"
    assert not any("XP" in s for s in shown)
    assert not any(ch.isdigit() for s in shown for ch in s if "Beat" not in s)
    assert narration.own_prose([]) == []


def test_the_watchers_award_is_an_engine_line():
    import inspect

    from gm import watcher

    src = inspect.getsource(watcher)
    assert '"kind": "setup"' not in src, "an award filed as narration is a template taught"
    assert src.count('"kind": "consequence"') >= 2


# --- the model that is not there ----------------------------------------------------------


def test_a_connection_dropped_mid_request_is_the_model_being_absent(monkeypatch):
    """Turn 59 of 60: Ollama restarted with the request already sent, urllib raised a
    bare `RemoteDisconnected` from `getresponse()`, and the player-facing path was a
    500 instead of the 503 that says "start Ollama"."""
    import http.client
    import urllib.request

    from gm import client

    def boom(*a, **k):
        raise http.client.RemoteDisconnected("Remote end closed connection without response")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    with pytest.raises(client.ModelUnavailable) as err:
        client.chat([{"role": "user", "content": "hi"}], "any-model", "http://localhost:1")
    assert "cannot reach" in str(err.value)
    with pytest.raises(client.ModelUnavailable):
        client._hosted([{"role": "user", "content": "hi"}], "m", "http://x", "openai",
                       "key", False, 0.5, 5, 10)


def test_the_audit_knows_an_absent_model_from_a_bad_turn():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools import narrator_audit as audit

    assert audit._unreachable(503, '{"error": "cannot reach Ollama at http://localhost"}')
    assert audit._unreachable(0, "RemoteDisconnected: Remote end closed connection")
    assert audit._unreachable(503, "gemma did not answer within 600s.")
    assert not audit._unreachable(410, "the character is dead")
    assert not audit._unreachable(502, "The GM could not produce a legal turn.")


def test_mentioned_survives_the_card_round_trip():
    from rules import cards

    c = cards.Card(id="x", title="A matter", mentioned=7)
    assert cards.Card.from_dict(c.as_dict()).mentioned == 7


# --- a rescue that does not arrive ------------------------------------------------------


def test_the_fallback_prose_call_does_not_wait_ten_minutes():
    """Measured on the first sixty-turn run after the guards: the 12B lost the scene,
    the 4B fallback was asked, and Ollama never answered — until `client.chat`'s
    600-second timeout returned it. One turn, ten minutes. The primary keeps the
    generous timeout (a cold load is genuinely slow); the fallback gets two minutes."""
    import ast
    import inspect

    from gm import agent

    assert agent.FALLBACK_TIMEOUT <= 180 < agent.PRIMARY_TIMEOUT
    src = inspect.getsource(agent)
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "narrate_turn")
    body = ast.get_source_segment(src, fn) or ""
    assert "FALLBACK_TIMEOUT" in body and "PRIMARY_TIMEOUT" in body

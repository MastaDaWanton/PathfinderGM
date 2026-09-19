"""`/gm` answers about any place or thing the world's record holds, and says so when it
does not.

"I want … the /gm speaks naturally to the user … any system or place should be able to be
asked about and an answer given. Just like if I was asking my GM in real life." Until
2026-09-18 it could match a rules entry by name and a world entity spelled exactly, and
"what is this town's council?" found nothing.

Measured before anything was built, on the shipped Aurvantis export (422 documents): a
BM25 index in SQLite's FTS5 ranks Vormoor and its four residents first for a question about
Vormoor, every Sootspar for "who are the Sootspars", Drenn Ironvale for his name — and
scores a question the world has no words for ("the winged clans", which are another
world's) near zero. docs/gm-questions.md carries the prior art and the numbers.
"""
from __future__ import annotations

import pytest

from play import campaign as cm, gm_search


@pytest.fixture(scope="module")
def world():
    w = cm.load_cached(cm._resolve_world_source("fixtures/aurvantis-campaign.json"))
    gm_search.forget(w)
    yield w
    gm_search.forget(w)


def test_a_named_person_is_found_and_a_named_place_brings_its_people(world):
    hits = gm_search.search(world, "who is Drenn Ironvale?")
    assert hits and hits[0].name == "Drenn Ironvale" and hits[0].kind == "character"
    hits = gm_search.search(world, "who is the most powerful person in Vormoor", limit=5)
    names = [h.name for h in hits]
    assert names[0] == "Vormoor"
    assert set(names[1:]) & {"Korgath Varn", "Mokra Sootspar", "Drenn Ironvale", "Zasha Sootspar"}
    hits = gm_search.search(world, "who are the Sootspars", limit=4)
    assert hits and all("Sootspar" in h.name for h in hits)


def test_a_question_the_world_has_no_words_for_finds_nothing(world):
    """The refusal is the code's, on a score threshold: an 8B model told to say
    "unknown" does so 37.6% of the time (FaithEval), so it is never asked."""
    assert gm_search.search(world, "what are the winged clans") == []
    assert gm_search.search(world, "who is Zorblax Quinn of the Emerald Cabal") == []
    # And a question whose words the world DOES hold is not refused for being oblique:
    # "the war with the flightless" finds the Gnome people, whose record carries both.
    assert gm_search.search(world, "what happened in the war with the flightless")
    assert "nothing filed" in gm_search.nothing_filed("what are the winged clans")
    assert "winged" in gm_search.nothing_filed("what are the winged clans")


def test_raw_text_is_made_a_query_fts5_accepts(world):
    """`Saltmakers' guild` and `want?` are FTS5 syntax errors as written; tokens are quoted
    and OR-joined (the default AND is what sank another project's full-text baseline)."""
    assert gm_search.match_expression("what do the Saltmakers' guild want?") == \
        '"saltmakers guild" OR "guild want" OR "saltmakers" OR "guild" OR "want"'
    # Does not raise, whatever the punctuation.
    gm_search.search(world, "who's the ruler? (of Vormoor) — and why!")


def test_a_name_made_of_ordinary_words_is_lifted_by_its_phrase(world):
    """"the Long Peace" scored -3.9 on tokens alone — below the threshold, the same as a
    question the world has no words for — and -7.8 with the phrase "long peace" in the
    query. Noise ("is there a temple here", -1.7) did not move."""
    hits = gm_search.search(world, "what is the Long Peace")
    assert hits and all("Long Peace" in h.name for h in hits)
    assert gm_search.search(world, "is there a temple here") == []


def test_the_same_name_at_the_same_kind_is_one_passage(world):
    hits = gm_search.search(world, "who is Drenn Ironvale", limit=4)
    assert [h.name for h in hits].count("Drenn Ironvale") == 1


def test_the_thing_named_outright_comes_first_whatever_bm25_said(world):
    """For "tell me about the Kragmoor Horde" three shorter rows — the founding, the
    accord, a faction within it — outscored the nation by half a point (BM25 favours a
    short document), and with three passages shown the nation itself was cut off."""
    hits = gm_search.search(world, "tell me about the Kragmoor Horde")
    assert hits[0].name == "Kragmoor Horde" and hits[0].kind == "nation"
    assert hits[0].facts, "the nation's own record, not an event about it"


def test_the_count_of_matches_is_the_codes_to_state(world):
    """"The records list three individuals with that surname" was said of the Sootspars,
    of whom the record holds a dozen — the model was shown three and counted them."""
    hits = gm_search.search(world, "who are the Sootspars")
    assert len(hits) == 3 and hits[0].matched > 3
    text = gm_search.passages(world, hits, "who are the Sootspars")
    assert "the best 3 of" in text and "there are more than these" in text
    one = gm_search.search(world, "who is Drenn Ironvale", limit=1)
    assert one[0].matched >= 1


def test_here_and_this_town_are_the_place_the_engine_knows():
    for q in ("what is this town's council", "is there a temple here", "who runs the city",
              "what do people around here eat"):
        assert gm_search.asks_about_here(q), q
    assert not gm_search.asks_about_here("who is Drenn Ironvale")


def test_the_paraphrase_gap_is_closed_by_intent_not_embeddings():
    assert "Formal Power" in gm_search.intent_keys("who runs this town")
    assert "Tension" in gm_search.intent_keys("what is the trouble here about")
    assert "Architecture" in gm_search.intent_keys("what do the buildings look like")
    assert "Daily Norms" in gm_search.intent_keys("what do people eat")
    assert gm_search.intent_keys("who is Drenn Ironvale") == ()


def test_the_dossier_is_the_whole_record_of_the_place_with_the_asked_fact_first(world):
    vormoor = world.by_name("Vormoor", kind="CITY")
    notes = gm_search.dossier(world, vormoor, "who runs this town")
    assert notes.startswith("THE GM'S NOTES ON VORMOOR")
    # Every PUBLIC fact; the hidden ones stay with the GM. Measured 2026-09-18 (item
    # 9): the first `/gm` answer of the session handed over "a shadow power in the form
    # of an old veterans' league" because this wrote every fact and put Shadow Power
    # among the first four for any "who runs" question.
    for key in vormoor.facts:
        if gm_search.tier_of(key) == "public":
            assert f"  {key}:" in notes, key
        else:
            assert f"  {key}:" not in notes, key
    assert "Shadow Power" in vormoor.facts and "  Shadow Power:" not in notes
    first_fact = notes.split("\n")[1]
    assert first_fact.startswith("  Formal Power:") or first_fact.startswith("  Governance:")
    assert "Places inside it: the well, the market, the guildhall" in notes
    assert "People who live here:" in notes and "Drenn Ironvale" in notes


def test_passages_label_the_source_in_code(world):
    hits = gm_search.search(world, "who is Drenn Ironvale")
    text = gm_search.passages(world, hits, "who is Drenn Ironvale")
    assert text.startswith("WHAT THE WORLD'S OWN RECORD SAYS")
    assert "* Drenn Ironvale — character, in Vormoor." in text
    assert len(text) <= gm_search.PASSAGE_BUDGET + 400


def test_the_index_is_built_once_and_fast(world):
    import time

    gm_search.forget(world)
    t0 = time.monotonic()
    gm_search.index_for(world)
    built = time.monotonic() - t0
    assert built < 2.0, built
    con1, _ = gm_search.index_for(world)
    con2, _ = gm_search.index_for(world)
    assert con1 is con2


def test_only_a_name_the_world_has_never_used_is_refused_in_code(world):
    """The refusal is the code's, so it has to be sure. A proper name with a word in no
    document ("Grimble", "Hollin Stair"), or a lowercase head phrase the world has none
    of ("the winged clans"), is refused; a question for a reading is not, even when this
    world's prose happens never to say "fight" or "advice" (measured: neither appears in
    1.28 MB of Aurvantis), and a name the world does hold ("the Salt Guild" — salt, guild)
    goes on to the model with whatever the record found."""
    assert gm_search.unfiled(world, "who is Grimble") == ["grimble"]
    assert gm_search.unfiled(world, "where is Hollin Stair") == ["hollin", "stair"]
    assert gm_search.unfiled(world, "tell me about the Winged Clans") == ["winged"]
    assert gm_search.unfiled(world, "what are the winged clans") == []   # clans: 71 documents
    assert gm_search.unfiled(world, "who is the harbourmaster") == ["harbourmaster"]
    for q in ("what should I do next?", "any advice?", "any advice about the fight",
              "what do you think of this", "is this a good idea", "what is the plan",
              "what is the Salt Guild", "who is the blacksmith", "what is at the market",
              "who is Drenn Ironvale", "tell me about the well"):
        assert gm_search.unfiled(world, q) == [], q
    said = gm_search.nothing_filed("who is Grimble", ["grimble"],
                                   "THE GM'S NOTES ON VORMOOR (city):\n  Formal Power: a council.")
    assert "never mentions grimble" in said and "Formal Power: a council" in said


def test_a_proper_name_is_a_capitalised_word_that_is_not_the_first():
    assert gm_search.proper_noun("who is Drenn Ironvale")
    assert gm_search.proper_noun("tell me about Vormoor")
    assert not gm_search.proper_noun("Who guards the gate")
    assert not gm_search.proper_noun("what should I do next?")
    assert not gm_search.proper_noun("GM, what is the plan")


def test_the_notes_and_the_record_go_after_the_question_with_the_one_instruction():
    from gm import prompts

    msgs = prompts.out_of_character_messages(
        "WORLD: Test.", "who runs this town?", "",
        notes="THE GM'S NOTES ON VORMOOR (city):\n  Formal Power: a clan council.",
        record="WHAT THE WORLD'S OWN RECORD SAYS ABOUT WHAT WAS ASKED:\n  * Vormoor — city.")
    user = msgs[-1]["content"]
    assert user.startswith("who runs this town?")
    assert user.index("THE GM'S NOTES") < user.index("WHAT THE WORLD'S OWN RECORD")
    assert "say so plainly rather than filling it in" in user
    plain = prompts.out_of_character_messages("WORLD: Test.", "how many hit points do I have")
    assert plain[-1]["content"] == "how many hit points do I have"


def test_the_gm_answer_path_uses_the_record_and_names_its_sources():
    import inspect

    from play import views

    src = inspect.getsource(views._ask_the_gm)
    assert "gm_search.search" in src and "gm_search.dossier" in src
    assert "nothing_filed" in src and "gm_search.unfiled" in src
    assert "from the world's record" in src
    # The deterministic backstop: a model that is down leaves the record itself.
    assert "here is the record as it stands" in src
    assert "_name_the_refs(" in src


def test_the_source_label_names_only_the_rows_the_answer_drew_on():
    """Measured live 2026-09-18: under "who guards the gate" the label read "Dunvale
    (city); Dustgate (city); Wynreach (city)" — three weak hits the answer never touched;
    it had come from the notes on the town. A source label the code writes is a claim,
    and it has to be true."""
    from play import views

    hits = [gm_search.Hit(kind="city", name="Dunvale", score=-5.8),
            gm_search.Hit(kind="city", name="Dustgate", score=-5.1),
            gm_search.Hit(kind="character", name="Drenn Ironvale", score=-15.0),
            gm_search.Hit(kind="event", name="Cinderwarren joins the Long Peace", score=-7.8)]
    said = ("My notes mention a weekly rest-day observed by the guard. Drenn Ironvale is "
            "the healer here. The Long Peace was joined by Cinderwarren among others.")
    assert [h.name for h in views._sources_used(hits, said)] == \
        ["Drenn Ironvale", "Cinderwarren joins the Long Peace"]
    assert views._sources_used(hits, "Nothing in my notes covers that.") == []


def test_an_engine_ref_in_the_answer_becomes_the_name_it_stands_for():
    """Measured live 2026-09-18: "you could focus on the immediate confrontation with
    c1" — the brief names people as "the apprentice minding the door (c1)" and the model
    took the shorter handle. Repaired from the scene's own actors, in code."""
    from types import SimpleNamespace as NS

    from play import views

    scene = NS(actors={"c1": NS(name="the apprentice minding the door"),
                       "c2": NS(name="the stranger")})
    fixed = views._name_the_refs(
        "Focus on the confrontation with c1, or ask the stranger (c2) about C1's master.",
        scene)
    assert fixed == ("Focus on the confrontation with the apprentice minding the door, or "
                     "ask the stranger about the apprentice minding the door's master.")
    # A ref the scene does not hold is left alone, as is text with no actors behind it.
    assert views._name_the_refs("see c9", scene) == "see c9"
    assert views._name_the_refs("with c1", NS(actors={})) == "with c1"

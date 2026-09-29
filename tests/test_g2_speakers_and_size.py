"""The two defects the Phase-2 live gate (G2) measured, 2026-09-29, in the running app:
gemma-4-12B on Aurvantis, the wizard Ysolde in Halhollow — a village.

1. **An untagged speaker the prose invents is never made real.** Turn "I sit on the edge of
   the canal and wait there for two hours, watching the market." The beat brought on "a man
   in a stained leather apron" who spoke to the player — "'That's a long way to sit and
   watch a man work,' he says… 'You looking for something specific, or just waiting for the
   world to start?'" The turn log: `speech-tags {tagged: 0, lines: 2, hails_tagged: [],
   hails_guessed: []}`, `mentions {unknown: 2}`; the scene's people stayed pc, c1, c2 — he
   got no body, no conversation opened, and `conversation_log` stayed empty.
   `speaker_real` embodied only a speaker matched to a `<say>` tag, and tagging is all or
   nothing per beat (4 of 8 beats tagged, 2026-09-25). The owner's Q5 ruling covers him:
   a person the prose introduces who speaks to the player becomes real.

2. **The turn narrator calls a village a city.** Same session: "the city's heavy traffic is
   less frequent", in Halhollow. The opening's size check guarded only the opening.
"""
from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import pytest

from gm import judgement, speech
from gm.checks import size_words
from play import aftermath
from play.aftermath import conversation_log, speaker_real
from rules import places

from _a_truth import WORLD, context, scene_at

HALHOLLOW = WORLD.by_name("Halhollow")


def _place(location, name: str) -> str:
    return next(p.id for p in places.home_set(location) if p.name == name)


def _small_and_city(world):
    """(a village or town, a city) the world sized — each export has both."""
    sized = [e for e in world.entities.values()
             if size_words._stated_scale(e) and places._settled(e, "")]
    small = next(e for e in sized if size_words._stated_scale(e) == "village") \
        if any(size_words._stated_scale(e) == "village" for e in sized) \
        else next(e for e in sized if size_words._stated_scale(e) == "town")
    city = next(e for e in sized if size_words._stated_scale(e) == "city")
    return small, city


# --- defect 1: the man in the stained leather apron ------------------------------------------

APRON = ("You settle on the worn stone lip of the canal and let the hours go by. Barges nose "
         "past, and the market's noise rises and falls behind you. A man in a stained "
         "leather apron stops beside you, wiping his hands on a rag. 'That's a long way to "
         "sit and watch a man work,' he says, nodding at the lock-keeper. 'You looking for "
         "something specific, or just waiting for the world to start?'")


def _halhollow(people=(), world=WORLD, location=None):
    location = location or HALHOLLOW
    agent, _ = scene_at(_place(location, "the market"), people, world=world,
                        location=location)
    engine = agent.engine
    campaign = SimpleNamespace(scene=engine.scene, world=world, transcript=[],
                               engine=lambda: engine)
    return engine, engine.scene, campaign


def _book(scene, text, world=WORLD):
    """What `_finish` does before the "people" stage: the prose's people on the ledger
    and into the population, as records with no body."""
    introduced = judgement.note_cast(scene, text, turn=4)
    judgement.record_people(scene, introduced, turn=4, world=world)
    return introduced


def test_the_apron_man_who_spoke_untagged_is_embodied_and_the_conversation_opens():
    """G2: 0 tags, 2 lines, both to the player; he stayed a description. Now he walks on
    through the arrival door with a square and a face, both lines are his, `hailed_by`
    opens the conversation, and the conversation log gets his two lines."""
    engine, scene, campaign = _halhollow([("Ysolde's companion", "guildhand")])
    _book(scene, APRON)
    said: list[dict] = []           # the prose call tagged nothing
    assert judgement.hailed_by(scene, APRON, said=said) == []
    before = set(scene.actors)
    rows = aftermath.run("people", aftermath.context("people", "turn", campaign,
                                                     engine=engine, text=APRON, said=said))
    made = set(scene.actors) - before
    assert len(made) == 1, rows
    ref = made.pop()
    man = scene.actors[ref]
    assert man.name == "man in a stained leather apron"
    assert man.appearance, "a face from the world's own pools"
    assert scene.positions.get(ref), "every arrival has a square (item 14)"
    assert [r["kind"] for r in rows] == ["speaker-real"] and rows[0]["made"] == ref
    assert rows[0]["untagged"] == 2
    assert [r["line"] for r in said] == speech.lines(APRON)
    assert all(r["who"] == ref and r["made"] == ref and r["to"] == "you" for r in said)
    # The hail opens the conversation, through the engine's own door, as `_finish` does.
    assert judgement.hailed_by(scene, APRON, said=said) == [ref]
    assert engine.join_talk(man, how="they spoke to you")
    assert [a.ref for a in engine.talking_to()] == [ref]
    # And the "beat" stage logs his two lines.
    campaign.transcript.append({"who": "player", "text": "I sit and wait."})
    campaign.transcript.append({"who": "gm", "text": APRON})
    aftermath.run("beat", aftermath.context("beat", "turn", campaign, engine=engine,
                                            text=APRON, said=said, beat_index=1))
    log = scene.conversation_log
    assert [(e["who"], e["kind"]) for e in log] == [(ref, "line"), (ref, "line")]
    assert [e["text"] for e in log] == speech.lines(APRON)


def test_the_apron_man_is_embodied_in_every_world(worlds):
    """World-agnostic: the step reads no Aurvantis name. In each export's first sized
    settlement the same beat makes one man, labelled by the page's descriptor."""
    small, _city = _small_and_city(worlds)
    engine, scene, campaign = _halhollow(world=worlds, location=small)
    _book(scene, APRON, world=worlds)
    said: list[dict] = []
    rows = speaker_real.step(aftermath.context("people", "turn", campaign, engine=engine,
                                               text=APRON, said=said))
    made = [r for r in rows if r.get("made")]
    assert len(made) == 1
    assert scene.actors[made[0]["made"]].name == "man in a stained leather apron"
    assert len(said) == 2


def test_a_pronoun_alone_embodies_nobody():
    """'…,' he says, with no person described anywhere in the beat: there is nobody to
    make, and a body out of a bare "he" is the phantom this project keeps paying for."""
    engine, scene, campaign = _halhollow()
    text = ("The market thins as the light goes. 'You've been sitting there since noon,' "
            "he says. 'Waiting for someone?'")
    _book(scene, text)
    said: list[dict] = []
    before = set(scene.actors)
    rows = speaker_real.step(aftermath.context("people", "turn", campaign, engine=engine,
                                               text=text, said=said))
    assert set(scene.actors) == before and said == []
    assert rows and all(not r.get("made") for r in rows)


def test_a_speaker_already_on_the_board_is_attributed_not_duplicated():
    """The man with the apron is already an actor (the plan introduced him): the line is
    his, and that is attribution — `hailed_by` and the tags' business — not a body. No
    second man walks on, and the row says who the line was read to."""
    engine, scene, campaign = _halhollow([("man in a stained leather apron", "guildhand")])
    ref = next(r for r, a in scene.actors.items() if a.name.startswith("man in"))
    _book(scene, APRON)
    said: list[dict] = []
    before = set(scene.actors)
    rows = speaker_real.step(aftermath.context("people", "turn", campaign, engine=engine,
                                               text=APRON, said=said))
    assert set(scene.actors) == before
    assert said == [] and all(not r.get("made") for r in rows)
    assert any(ref in r.get("why", "") and "on the board" in r["why"] for r in rows), rows


def test_a_line_not_to_the_player_makes_nobody():
    """"'Fine weather,' the carter tells the drover" is not a hail: the ruling is about a
    person who speaks TO the player."""
    engine, scene, campaign = _halhollow()
    text = ("A carter in a patched coat leans on his wagon by the well. 'Fine weather for "
            "it,' the carter tells the drover beside him.")
    _book(scene, text)
    said: list[dict] = []
    before = set(scene.actors)
    speaker_real.step(aftermath.context("people", "turn", campaign, engine=engine,
                                        text=text, said=said))
    assert set(scene.actors) == before and said == []


def test_one_body_per_person_however_many_lines_and_phrases():
    """Two lines, one said by "a woman with a basket" and one by "the woman": one woman,
    not two — one embodiment per person per beat."""
    engine, scene, campaign = _halhollow()
    text = ("A woman with a basket of eggs stops at your elbow. 'You're new here,' she "
            "says. The woman shifts the basket. 'You'll want the clan-hall for supper,' "
            "the woman adds.")
    _book(scene, text)
    said: list[dict] = []
    before = set(scene.actors)
    speaker_real.step(aftermath.context("people", "turn", campaign, engine=engine,
                                        text=text, said=said))
    made = set(scene.actors) - before
    assert len(made) == 1
    assert {r["who"] for r in said} == made and len(said) == 2


def test_the_people_stage_may_add_a_made_record_and_only_that():
    """The contract (§2.3) widened by exactly one thing: the "people" stage may add a
    record for an untagged line on the page, carrying `made`. A record added without
    `made`, or at the "beat" stage, is still refused and put back."""
    from play.aftermath import _said_kept

    before = [{"who": "c2", "to": "", "line": "Go."}]
    ok = before + [{"who": "c5", "to": "you", "line": "You there.", "made": "c5",
                    "from": "page"}]
    assert _said_kept(before, ok, "people") == ""
    assert _said_kept(before, before + [{"who": "c5", "to": "you", "line": "x"}], "people")
    assert _said_kept(before, ok, "beat")


# --- defect 2: the village the page called a city --------------------------------------------

def _ctx_in(location, text, world=WORLD, spot="the market"):
    agent, _ = scene_at(_place(location, spot), world=world, location=location)
    return context(agent, text)


def test_the_citys_heavy_traffic_in_a_village_is_flagged_and_put_back():
    """G2: "the city's heavy traffic is less frequent", in Halhollow, a village. Found,
    the repair names the scale, and the backstop says village."""
    text = ("You wait on the canal's edge. By late afternoon the city's heavy traffic is "
            "less frequent, and the lock-keeper sits down at last.")
    ctx = _ctx_in(HALHOLLOW, text)
    (f,) = size_words.find(ctx)
    assert f.kind == "size-words" and "the city's" in f.detail
    assert f.fix_hint.startswith("Halhollow is a village of a few hundred people")
    assert "say village" in f.fix_hint
    assert f.sentences == ("By late afternoon the city's heavy traffic is less frequent, "
                           "and the lock-keeper sits down at last.",)
    fixed, notes = size_words.backstop(ctx, text, [f])
    assert "the village's heavy traffic" in fixed and "city" not in fixed and notes
    assert size_words.find(dataclasses.replace(ctx, text=fixed)) == []


def test_the_road_to_the_city_of_another_place_is_not_flagged():
    """"the city of Brackgate" is another place (the look-ahead `in_its_own_words`
    already keeps), and so is a real city of the world named in the sentence."""
    for text in ("A carter mentions the road to the city of Brackgate, three days east.",
                 "Harpost, the city to the north, is a week away by cart."):
        assert size_words.find(_ctx_in(HALHOLLOW, text)) == [], text


def test_a_citys_own_the_city_is_not_flagged(worlds):
    """A city is a city: its own "the city" is the world's word and right."""
    _small, city = _small_and_city(worlds)
    spot = places.home_set(city)[0].name
    text = "The city's heavy traffic is less frequent after dark."
    assert size_words.find(_ctx_in(city, text, world=worlds, spot=spot)) == []


def test_a_small_place_called_a_city_is_flagged_in_every_world(worlds):
    """World-agnostic, through `places.scale_of`: each export's small settlement is found
    and put back to its own scale word."""
    small, _city = _small_and_city(worlds)
    scale = size_words._stated_scale(small)
    spot = places.home_set(small)[0].name
    text = "The city's heavy traffic is less frequent after dark."
    ctx = _ctx_in(small, text, world=worlds, spot=spot)
    (f,) = size_words.find(ctx)
    assert f.fix_hint.startswith(f"{small.name} is a {scale}")
    fixed, _ = size_words.backstop(ctx, text, [f])
    assert fixed == f"The {scale}'s heavy traffic is less frequent after dark."


def test_city_scale_words_and_the_town_word_in_a_village():
    """The rest of the size vocabulary, and "the town" for a village; the backstop puts
    each back or cuts the sentence."""
    text = ("Halhollow is a sprawling settlement of districts and thoroughfares. The "
            "town's bell rings twice.")
    ctx = _ctx_in(HALHOLLOW, text)
    (f,) = size_words.find(ctx)
    for w in ("sprawling", "districts", "thoroughfares", "the town's"):
        assert repr(w) in f.detail, w
    fixed, _ = size_words.backstop(ctx, text, [f])
    assert fixed == ("Halhollow is a settlement of lanes and lanes. The village's bell "
                     "rings twice.")


def test_what_is_not_a_size_claim_is_left_alone():
    """"lies sprawling in the mud" is a man; a character's own words are theirs; "the
    City Watch" is a name."""
    for text in ("A drunk lies sprawling in the mud by the well.",
                 "'The city is where the money is,' he says, spitting.",
                 "Two of the City Watch stand at the well."):
        assert size_words.find(_ctx_in(HALHOLLOW, text)) == [], text


def test_outside_a_settlement_it_does_nothing():
    """On open ground there is no settlement for the page to misname."""
    approach = f"{HALHOLLOW.id}~forest:the-approach"
    agent, _ = scene_at(approach, location=HALHOLLOW)
    ctx = context(agent, "Somewhere beyond the trees, the city's bells ring.")
    assert size_words.find(ctx) == []


def test_the_size_check_is_a_registered_member():
    from gm import checks

    assert size_words in checks.registered()
    assert size_words.DOORS == frozenset({"plan", "turn", "outcome"})

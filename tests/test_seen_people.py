"""People the player can see are in the scene; people only heard of are records, placed
where they were said to be (owner's ruling, 2026-10-01).

"show described people in the scene. if i can see them they should be in the scene as a
fully made person ready to be interacted with and saved if not already existing." It
overturns the ruling of 2026-09-27 that the prose only records people.

Every test here names a measurement from the owner's own save (Sam, 2026-10-01; the beats
below are written for the tests in the same shape, not copied from it):

1. Gorm, the barkeep, told the player about a human woman who lives in "the house three
   streets over". The population recorded her TWICE — p16 'human woman' from the beat's
   narration and p17 'human woman' heard from Gorm — and both at the Velvet Veil, where the
   talk happened, not where she lives.
2. "I enter the house of the human woman Grom spoke of": the plan's `call_on` "human woman"
   was refused "There is more than one — which human woman do you mean?", and the finder
   wrote `population-miss` seven times for the words human, woman, grom, speak.
3. The beat then showed "a figure … It is a woman" at the top of the stairs; she was never
   an actor, the next turn's condition on 'woman' was refused (unknown ref), and every "her"
   after it went to Quin Nutmeg, the only woman the engine held.
"""
from __future__ import annotations

import pytest

from gm import judgement
from play import aftermath
from rules import attitude, granted, keepers, names, places, population
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world import loader

WORLD = loader.load_cached("fixtures/aurvantis-campaign.json")
LEDGERWARREN = WORLD.by_name("Ledgerwarren", kind="CITY").id
GATE = f"{LEDGERWARREN}~urban:the-gate"
HUMAN = next(k for k, v in names.peoples(WORLD).items() if v == "Human")


def _run(e, plan):
    return e.run(e.validate(plan, origin="author:test"))


@pytest.fixture
def veil():
    """The Velvet Veil, off the gate, with its barkeep, who gave his name in play."""
    scene = Scene(location_id=LEDGERWARREN)
    scene.add(load_pc("fixtures/pc-kesst.json"))
    engine = Engine(scene, Dice(seed=3), world=WORLD)
    engine.place_party(GATE)
    _run(engine, [{"op": "found", "because": "t",
                   "params": {"name": "the Velvet Veil", "parent": "the gate",
                              "kind": "tavern"}}])
    there = places.find(engine.places(), "the Velvet Veil")
    _run(engine, [{"op": "travel", "because": "t", "params": {"place": there.id}}])
    gorm = keepers.keeper_in(scene, there.id)
    gorm.name = gorm.true_name = "Gorm Vesper"
    return scene, engine, gorm


def _beat(scene, text, turn, world=WORLD):
    """The prose door as `views._finish` runs it: the ledger, the records, then the
    "people" stage's bodies."""
    introduced = judgement.note_cast(scene, text, turn=turn)
    recs = judgement.record_people(scene, introduced, turn=turn, world=world, beat=text)
    rows = judgement.embody_seen(scene, turn=turn, world=world, beat=text)
    return introduced, recs, rows


# --- B. heard of: one record, not where the talk happened ----------------------------------

TOLD = ("Gorm leans on the bar. You remind him that he told you a moment ago that a "
        "human woman lives there, and he grunts.")


def test_the_woman_gorm_spoke_of_is_one_record_and_not_in_the_tavern(veil):
    """Measured: p16 and p17, both 'human woman', both at the Velvet Veil. Now the
    narration's report and the barkeep's yes are one record, heard of from Gorm, with no
    place — she lives three streets over, not in the tavern — and a resident."""
    scene, engine, gorm = veil
    turn = 95
    _, recs, rows = _beat(scene, TOLD, turn)
    assert rows == []                               # heard of: nobody walks in
    found = granted.detect("it is a human woman who lives there right?",
                           [{"who": gorm.ref, "line": "Aye. A human woman. She is there."}],
                           WORLD, scene)
    assert found and found[0]["elsewhere"] is True
    rec = granted.grant(scene, found[0], turn=turn)
    women = [r for r in scene.population.values() if "woman" in r["phrase"]]
    assert [r["id"] for r in women] == [rec["id"]]
    assert rec["spot"] == "" and rec["spot"] != scene.at
    assert rec.get("seen") is False and rec["heard_from"] == gorm.ref
    assert rec["life"]["mobility"] == "resident"
    # A grant of somebody elsewhere promises nobody HERE: the tavern's next stranger is
    # not bound to it.
    assert rec["granted"]["place"] == ""
    assert granted.claim(scene, scene.at, gender="woman") is None
    # And the finder does not put her in the tavern by her schedule either.
    assert population.find(scene, "human woman", world=WORLD).scope == population.ELSEWHERE


def test_the_asked_for_words_given_back_with_a_yes_are_a_yes():
    """Replayed 2026-10-01 on the owner's save: asked "It is a human woman who lives there,
    right?", Gorm answered "'A woman, aye,' he rasps" — and the yes-reader, which wanted the
    line to OPEN with yes, recorded nobody; the finder then logged a miss for her."""
    assert granted.affirms("A woman, aye. But 'woman' is a broad word in a place like this.")
    assert granted.affirms("A human woman, yes.")
    assert not granted.affirms("A woman? No, not here.")
    assert not granted.affirms("A woman, no.")


def test_an_answer_about_somebody_elsewhere_records_her_without_a_yes(veil):
    """Replayed 2026-10-01: asked "it is a human woman who lives in the house 3 streets
    over, right?", Gorm answered with the house's blue shutters and "a woman alone in a
    house like that" — no opening yes, so nothing recorded her, and the call on "the human
    woman Grom spoke of" next turn found nobody. About somebody elsewhere, an answer that
    speaks of her is enough; a "no" still is not."""
    scene, engine, gorm = veil
    asked = "I ask Gorm: it is a human woman who lives in the house 3 streets over, right?"
    beat = ("Gorm grips the counter. 'Three streets over. The house with the blue "
            "shutters. A woman alone in a house like that does not take kindly to "
            "strangers.' He looks back at your hands.")
    found = granted.detect(asked, [], WORLD, scene, text=beat)
    assert found and found[0]["by"] == gorm.ref and found[0]["elsewhere"]
    rec = granted.grant(scene, found[0], turn=12)
    assert rec["spot"] == "" and rec["heard_from"] == gorm.ref
    assert population.find(scene, "the human woman Grom spoke of",
                           world=WORLD).people == [rec]
    assert not granted.detect(asked, [], WORLD, scene,
                              text="'No woman lives there,' Gorm says. 'Not for years.'")
    # Somebody asked about HERE still needs a yes: that grant binds the next body made.
    assert not granted.detect("any human women here?", [], WORLD, scene,
                              text="'A woman alone in a place like this,' Gorm mutters.")


def test_a_person_only_spoken_of_in_the_narration_is_no_body_and_has_no_place(veil):
    """The prose door used to record everybody at the party's spot: the elder of another
    quarter, spoken of, stood in the tavern as a record."""
    scene, engine, gorm = veil
    _, recs, rows = _beat(scene, "Gorm tells you that an old man lives across the "
                                 "river and owes him money.", 40)
    assert rows == [] and recs
    assert recs[0]["spot"] == "" and recs[0].get("seen") is False
    assert not any(a.name.endswith("old man") for a in scene.actors.values())


# --- C. the finder: who told, and a slip of a name ------------------------------------------

def _two_women(scene, gorm):
    """One woman seen here, one heard of from Gorm — the duplicate the save held."""
    here = population.note(scene, "human woman", turn=90)
    told = population.note(scene, "human woman", turn=95, spot="", heard_from=gorm.ref,
                           fresh=True)
    return here, told


def test_the_woman_grom_spoke_of_is_the_one_heard_from_gorm(veil):
    """Measured: "human woman Grom spoke of" — seven population-miss rows (human, woman,
    grom, speak) and "which human woman do you mean?". "spoke of" says who told the player,
    not who she is; "Grom" is one transposition from Gorm."""
    scene, engine, gorm = veil
    population.drain_misses()
    here, told = _two_women(scene, gorm)
    for phrase in ("human woman Grom spoke of", "the human woman Gorm spoke of",
                   "the woman Gorm told me about", "the human woman that Gorm mentioned"):
        got = population.find(scene, phrase, world=WORLD)
        assert got.people == [told], phrase
    # Even with another woman standing right here: the one Gorm spoke of was asked for.
    assert population.find(scene, "the woman Gorm spoke of", world=WORLD).people == [told]
    assert population.drain_misses() == []
    # Without the clause it is still the honest question.
    assert population.find(scene, "human woman", world=WORLD,
                           rings=(population.HERE, "settlement")).scope != population.NONE


def test_a_slip_is_forgiven_only_when_one_name_is_that_close(veil):
    """Damerau (1964): about 80% of misspellings are one edit. "Grom" is Gorm; but with a
    Grim in town as well, "Grom" is a guess between two and is corrected to nobody."""
    scene, engine, gorm = veil
    assert population.near_name(scene, "Grom") == ("gorm", gorm.ref)
    assert population.correct_names(scene, "Grom's house") == "Gorm's house"
    other = instantiate("guildhand", scene=scene, name="Grim Hollow")
    other.true_name = "Grim Hollow"
    scene.add(other)
    assert population.near_name(scene, "Grom") == ("", "")
    # Never a common word: the slip is read only against the names of people held.
    assert population.correct_names(scene, "the woman") == "the woman"


def test_a_miss_is_logged_once_however_many_readers_asked(veil):
    """Measured: seven identical population-miss rows in one turn."""
    scene, engine, gorm = veil
    population.note(scene, "old fisherman", turn=1)
    population.drain_misses()
    for _ in range(7):
        population.find(scene, "the lamplighter with the pole", world=WORLD)
    rows = population.drain_misses()
    assert len(rows) == 1 and rows[0]["kind"] == "population-miss"


def test_the_call_on_keeps_who_told_the_player(veil):
    """Measured: the plan's `call_on` carried who="human woman" and dropped "Grom spoke
    of", and the engine refused "There is more than one". The player's clause rides along
    now, and the engine calls on the woman Gorm spoke of."""
    scene, engine, gorm = veil
    here, told = _two_women(scene, gorm)
    plan = [{"op": "call_on", "params": {"who": "human woman", "visit": True}}]
    out = judgement.inject_call_on(plan, "I enter the house of the human woman Grom "
                                         "spoke of.", scene)
    who = out[0]["params"]["who"]
    assert who.startswith("human woman") and "Grom spoke of" in who
    callee = engine._callee(who)
    assert not isinstance(callee, str), callee
    assert callee["key"] == told["id"]
    # Replayed 2026-10-01: the plan wrote who="new2", the introduce placeholder, and the
    # call was refused "Nobody the party has met answers to 'new2'". The player's words
    # name her, so they are used.
    plan = [{"op": "call_on", "params": {"who": "new2", "visit": True}}]
    out = judgement.inject_call_on(plan, "I go to the house of the human woman Grom "
                                         "spoke of.", scene)
    who = out[0]["params"]["who"]
    assert who.startswith("human woman") and engine._callee(who)["key"] == told["id"]
    # A pronoun or a ref is left as it was.
    plan = [{"op": "call_on", "params": {"who": "her", "visit": True}}]
    assert judgement.inject_call_on(plan, "I go to the house Gorm spoke of", scene)[0][
        "params"]["who"] == "her"


# --- A. seen: a full person at once ------------------------------------------------------------

FIGURE = ("The door gives under your hand. At the top of the stairs, a figure is silhouetted "
          "against the lamplight. It is a woman, her face mostly in shadow, and she does not "
          "move.")


def test_a_figure_the_beat_shows_is_a_woman_with_a_body_and_a_square(veil):
    """Measured: "a figure … It is a woman" stayed prose; "/cheat the woman … pounces on
    me" was refused (unknown ref 'woman', then no creature 'woman') and "her" went to Quin
    Nutmeg in another room. Now she walks on as a woman, she/her, on a square, with the
    life her record rolled, and the finder's "the woman" is her."""
    scene, engine, gorm = veil
    _, recs, rows = _beat(scene, FIGURE, 104)
    made = [r["made"] for r in rows if r.get("made")]
    assert len(made) == 1, rows
    woman = scene.people[made[0]]
    assert woman.ref in scene.actors and woman.at == scene.at
    assert woman.name == "woman" and woman.pronouns == "she/her"
    assert woman.has_state("role.bystander")        # in the room, not in a fight
    assert scene.positions.get(woman.ref)            # a square from the moment she is seen
    rec = population.of_ref(scene, woman.ref)
    assert rec is not None and rec.get("life")       # saved, with her life
    assert population.find(scene, "the woman", world=WORLD).people == [rec]
    # The same beat again does not make her twice.
    assert judgement.embody_seen(scene, turn=104, world=WORLD) == []
    _, _, again = _beat(scene, "The woman at the top of the stairs watches you.", 106)
    assert not [r for r in again if r.get("made")]


def test_somebody_heard_of_and_then_shown_is_that_one_person_with_a_body(veil):
    """Replayed 2026-10-01: "there is no sign of the woman" booked her as heard of; the
    next beat's "You find the woman standing in the entryway" made nobody, because the
    ledger read the definite "the woman" as somebody already booked and returned nothing.
    And the call on "the human woman Grom spoke of" missed her because the roll had given
    the unseen woman the town's Ratfolk face, which ruled out "human"."""
    scene, engine, gorm = veil
    scene.cast.clear()
    _, recs, rows = _beat(scene, "You search the street, but there is no sign of the "
                                 "woman, and the shutters stay closed.", 20)
    heard = [r for r in recs if "woman" in r["phrase"]]
    assert heard and heard[0].get("seen") is False and not rows
    rec = heard[0]
    rec["heard_from"] = gorm.ref
    assert population.find(scene, "the human woman Grom spoke of",
                           world=WORLD).people == [rec]
    _, _, rows = _beat(scene, "You find the woman standing in the entryway, her hands "
                              "clasped.", 22)
    made = [r["made"] for r in rows if r.get("made")]
    assert len(made) == 1 and rec["ref"] == made[0], rows
    assert len([r for r in scene.population.values() if "woman" in r["phrase"]]) == 1


def test_a_crowd_is_scenery_not_people(veil):
    """"a crowd of drinkers" is not N actors: a plural or a counted group is no one person
    with one life (`record_people`), and a group is the troop door's to make."""
    scene, engine, gorm = veil
    before = set(scene.actors)
    _, _, rows = _beat(scene, "A crowd of drinkers fills the room, and a few laborers sit "
                              "by the hearth in heavy silence.", 20)
    assert set(scene.actors) == before and not [r for r in rows if r.get("made")]


def test_in_a_fight_the_prose_makes_nobody(veil):
    """The fight's rule stands (`GMAgent._undeclared_arrivals`): an arrival in a fight is
    the plan's `spawn`, never the prose's."""
    scene, engine, gorm = veil
    scene.initiative = [("pc", 15), (gorm.ref, 8)]
    scene.turn = 0
    assert scene.in_encounter
    _, _, rows = _beat(scene, "A man in a leather apron stands by the door, watching.", 30)
    assert not [r for r in rows if r.get("made")]
    assert any(r.get("why") == "in a fight the prose brings nobody in" for r in rows)


def test_no_more_than_the_cap_from_one_beat(veil):
    """A beat that reads as five strangers is likelier a misread than a crowd scene; the
    rest stay records the player can still find."""
    scene, engine, gorm = veil
    text = ("A tall woman leans on the bar. A bald man sits by the fire. A young sailor "
            "stands at the door. An old smith nods at you. A thin clerk waits by the stairs.")
    _, recs, rows = _beat(scene, text, 50)
    made = [r for r in rows if r.get("made")]
    assert len(made) == judgement.SEEN_CAP
    assert any("more than" in str(r.get("why", "")) for r in rows)


def test_somebody_held_elsewhere_in_town_walks_in_rather_than_twice(veil):
    """"saved if not already existing": somebody the party met at the gate, written into
    the tavern by the prose by every word of what they go by, is that person — not a
    second one with a second face. (The save's case was the cage owner, met in the back
    streets and written hunched over a ledger in the Velvet Veil.)"""
    scene, engine, gorm = veil
    owner = instantiate("guildhand", scene=scene, name="the old fisherman")
    scene.arrive(owner, place_id=GATE)
    count = len(scene.people)
    _, _, rows = _beat(scene, "The old fisherman is hunched over a mug at the far table.", 60)
    assert len(scene.people) == count, rows
    assert owner.at == scene.at and owner.ref in scene.actors
    assert any(r.get("same_as") == owner.ref for r in rows)


def test_the_figure_in_her_own_house_is_the_householder(veil):
    """The owner's flow, fixed end to end: the call on her founds her house and walks the
    party in; the beat's "a figure at the top of the stairs … It is a woman" is her, not a
    second woman."""
    scene, engine, gorm = veil
    rec = population.note(scene, "human woman", turn=95, spot="", heard_from=gorm.ref)
    rec["life"]["mobility"] = "resident"
    # Gorm told them the way: the knowledge tag the call reads (`_knows_home`).
    scene.pc().apply_effect(ActiveEffect(
        name="knows", kind="knowledge", key=f"knows-home:{rec['id']}",
        source=f"home:{rec['id']}", origin="told", duration="until-dismissed",
        tags=(f"knows.home.{rec['id']}",)))
    out = _run(engine, [{"op": "call_on", "params": {"who": "human woman Gorm spoke of",
                                                     "visit": True}}])
    call = out.outcomes[0]
    assert call.status == "resolved", call.tell
    her = scene.people[rec["ref"]]
    # Replayed 2026-10-01: made in the tavern to be called on, she stayed in the tavern,
    # and her own door went unanswered ("The human woman is at the Velvet Veil").
    assert "Velvet Veil" not in call.tell and her.at != GATE + "/the-velvet-veil"
    if scene.at != call.effects[0]["house"]:
        # Not let in at this regard: make her friendly and knock again.
        attitude.set_regard(her, 80, "test")
        out = _run(engine, [{"op": "call_on", "params": {"who": her.ref, "visit": True}}])
        call = out.outcomes[0]
    assert scene.at == call.effects[0]["house"] and her.ref in scene.actors, call.tell
    count = len(scene.people)
    introduced = judgement.note_cast(scene, FIGURE, turn=104)
    judgement.record_people(scene, introduced, turn=104, world=WORLD, beat=FIGURE)
    rows = judgement.embody_seen(scene, turn=104, world=WORLD, beat=FIGURE)
    assert len(scene.people) == count, rows
    assert any(r.get("same_as") == her.ref for r in rows)
    # A figure who comes in is somebody arriving, not the householder.
    came = "A hooded figure enters from the street behind you and stands by the door."
    introduced = judgement.note_cast(scene, came, turn=108)
    judgement.record_people(scene, introduced, turn=108, world=WORLD, beat=came)
    rows = judgement.embody_seen(scene, turn=108, world=WORLD, beat=came)
    assert [r for r in rows if r.get("made")], rows
    # She was granted nothing here, but her people came from the record's own words.
    assert her.pronouns in ("she/her", "")


def test_a_child_the_beat_shows_stands_here_and_the_adults_only_rule_sees_him(veil):
    """Embodying who is seen must never open a door the minor rules close: a boy shown in
    the doorway is an actor whose record is a minor, and `a_child_in` — the guard under the
    intimate briefing — reads him from the room, with no word of him in the next beat."""
    scene, engine, gorm = veil
    _, _, rows = _beat(scene, "A small boy stands in the doorway, watching you.", 70)
    made = [r["made"] for r in rows if r.get("made")]
    assert made
    rec = population.of_ref(scene, made[0])
    assert "minor" in (rec["life"].get("tags") or [])
    assert judgement.a_child_in(scene, "The fire crackles.")


def test_the_step_runs_in_the_people_stage_after_the_speaker_is_made_real():
    """`speaker_real` (ORDER 10) must see this beat's records without bodies, or a hail
    tagged to a ref nobody held could never be given to its speaker."""
    members = {m.__name__.rsplit(".", 1)[-1]: m for m in aftermath.registered()}
    seen, speaker = members["seen_people"], members["speaker_real"]
    assert seen.STAGE == speaker.STAGE == "people" and seen.ORDER > speaker.ORDER


def test_seen_and_heard_are_read_from_the_sentence():
    """The test that decides a body: placed or acting here, and no report of somebody's
    words about them."""
    assert judgement.seen_in_beat(FIGURE, "figure") == judgement.SEEN
    assert judgement.seen_in_beat(TOLD, "human woman") == judgement.HEARD
    assert judgement.seen_in_beat("'There is a woman upstairs,' he says.", "woman") == \
        judgement.HEARD
    assert judgement.seen_in_beat("If a guard sees you, run.", "guard") == judgement.HEARD
    # Replayed 2026-10-01: the player standing, and a woman who exists only in stories,
    # were read as a woman here, and a phantom walked on with a face. The cue must be hers.
    ghost = ("You have been chasing a ghost, a woman who exists in the stories of the "
             "desperate. You are still standing before him, and the search for the woman "
             "has just become a search for why the lie persists.")
    assert judgement.seen_in_beat(ghost, "woman") != judgement.SEEN
    # And talk of her is not her: recorded with no place, not where the party stands.
    asked = ("The question you posed, concerning the woman three streets over, hangs in "
             "the air.")
    assert judgement.seen_in_beat(asked, "woman") == judgement.HEARD
    assert judgement.seen_in_beat("You see a woman by the well, mending a net.",
                                  "woman") == judgement.SEEN
    assert judgement.seen_in_beat("A man who stands in the doorway eyes your purse.",
                                  "man") == judgement.SEEN
    assert judgement._gendered(FIGURE, "figure") == "woman"
    assert judgement._gendered("A figure waits by the well.", "figure") == "figure"

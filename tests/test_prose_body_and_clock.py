"""The body and the clock on the page (the owner's reports of 2026-10-05).

1. *"prose acts like im okay but im literally starving and days past the last rest. the
   prose should reflect this."* Sidebar: Life 18 of 73, Hunger "starving", Rest "past a
   day awake — Will save every active hour, DC 107". The beat was a calm walk down the
   road to Grotburrow with no hunger, wound or tiredness in it. The brief had said
   "18/73 hp" mid-cast-list and nothing of hunger, thirst or sleep.
2. *"says its afternoon but prose says morning."* "I sleep" at day 6, 09:49; the engine
   rested eight hours; the beat at 17:49 opened "The morning air is cold" and, a sentence
   later, "the gray morning". The beat reader reported only the second (its hour slot held
   one claim), that sentence was repaired, and the first shipped.
3. The Rest line's DC 107 is the awake DC counting HOURS awake (121) rather than saves
   made: ninety-seven hours the clock charged without a single save had each raised it.

Every case is read off the owner's save (sammy.json, transcript beats 63 and 65, turn log
rows 41-45) — the beats' own sentences, the clock, the sheet.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from gm import beat_verify as bv
from gm import prompts
from gm.checks import body_shown, land_described
from rules import survival
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc, to_dict

DAY = 24 * 60
HOUR = 60

# Beat 63, as the owner read it (sammy.json): Sammy at 18/73, five days unfed and unslept.
CALM_WALK = (
    "The heavy, stagnant air of Vormoor's inner workings falls away as you pass the "
    "crossroads, where the dust kicked up by passing carts is the only thing that marks the "
    "fork in the path. You travel the stretch of road leading out of the settlement, the "
    "buildings thinning and the ground turning from packed earth to the hard-packed soil of "
    "the farmland. Now, the road to Grotburrow stretches before you, a ribbon of dirt "
    "cutting through the vast, lonely expanse of the fields. The silence here is heavy, "
    "broken only by the distant, low lowing of cattle and the dry whistle of the wind "
    "across the grass. You stop, your head turning toward the silence of the road, and the "
    "only sound is the wind whistling through the grass. What do you do?")

# Beat 65 as drafted, before the beat-hour repair rewrote its second sentence (turn log
# row 42: the repair's own "before" and the transcript's "after").
WOKE_AT_DUSK = (
    "The morning air is cold and tastes of dust, and your muscles ache from the stiffness "
    "of the earth. You wake to find the sun high enough to turn the gray morning into a "
    "harsh, golden glare. The silence of the farm is absolute, save for the rhythmic "
    "flapping of a loose tarp somewhere in the distance. Your body feels heavy, your "
    "muscles protesting the lack of a proper bed, and the dry air has left your throat "
    "parched. What do you do?")


@pytest.fixture
def sammy():
    """The owner's character as the sheet stood at beat 63: 18 of 73, 121 hours since
    food, water or sleep (fed/watered/awake minutes 7,282 in the save)."""
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    pc = from_dict(d, ref="pc")
    pc.kind = "pc"
    pc.hp_max, pc.hp = 73, 18
    pc.fed_minutes = pc.awake_minutes = 121 * HOUR
    pc.watered_minutes = 0
    return pc


def _scene(pc, clock=5 * DAY + 9 * HOUR + 49):
    s = Scene(location_id="bde94b038cba")
    s.add(pc)
    s.clock_minutes = clock
    return s


def _ctx(scene, text):
    return SimpleNamespace(scene=scene, text=text)


# --- 3. the Rest line's DC ------------------------------------------------------------------

def test_the_rest_line_no_longer_reads_dc_107(sammy):
    """121 hours awake, no save yet made: the panel read "Will save every active hour,
    DC 107" — past any Will save, so only a natural 20 could ever pass it. The book's
    starvation, thirst and forced-march DCs rise per CHECK made; so does this now."""
    rest = next(n for n in sammy.summary()["needs"] if n["id"] == "sleep")
    assert rest["state"].startswith("past a day awake")
    assert rest["state"].endswith("DC 10"), rest["state"]


def test_inside_a_long_stretch_the_save_still_rises_an_hour_at_a_time(sammy):
    """The owner's design kept: inside `pass_hours` one save IS one hour, so the climb
    the design asked for ("hour forty is not trivial") is unchanged there."""
    sammy.awake_minutes = 24 * HOUR
    sammy.fed_minutes = sammy.watered_minutes = 0
    asked = []
    real = survival._check

    def spy(actor, kind, dc, dice, save="", against=""):
        out = real(actor, kind, dc, dice, save, against)
        if kind == "Exhaustion":
            asked.append(dc)
            out["passed"] = True        # keep going, so the climb shows
        return out

    survival._check = spy
    try:
        survival.pass_hours(sammy, 4, Dice(seed=1))
    finally:
        survival._check = real
    assert asked == [10, 11, 12, 13]


def test_a_night_clears_the_saves_made(sammy):
    sammy.awake_checks = 9
    survival.sleep(sammy, 8)
    assert sammy.awake_checks == 0
    assert from_dict(to_dict(sammy)).awake_checks == 0
    sammy.awake_checks = 4
    assert from_dict(to_dict(sammy)).awake_checks == 4


# --- 1. the body reaches the brief ------------------------------------------------------------

def test_the_strains_are_the_engine_facts_in_words(sammy):
    """One derivation for the brief and the check: wounds at 18/73, five days without
    food, five days without sleep — and no digit anywhere (law 3)."""
    got = {s.key: s.words for s in survival.strains(sammy)}
    assert set(got) == {"wounds", "hunger", "sleep"}
    assert got["wounds"].startswith("gravely hurt")
    assert "five days without food" in got["hunger"]
    assert "five days without sleep" in got["sleep"]
    assert not any(ch.isdigit() for w in got.values() for ch in w)


def test_a_rested_fed_whole_body_carries_nothing(sammy):
    sammy.hp = sammy.hp_max
    sammy.fed_minutes = sammy.awake_minutes = 0
    assert survival.strains(sammy) == []
    assert prompts.body_now(sammy) == ""


def test_the_body_goes_last_in_the_prose_prompt(sammy):
    """The brief carried "18/73 hp" mid-cast-list and the beat was a calm walk; the body
    now closes the scene block, the slot the shipped narrators keep for what must not be
    got wrong (docs/narrator-guards.md D6)."""
    block = prompts.scene_now(_scene(sammy))
    assert "THE PLAYER'S BODY" in block
    assert "starving" in block and "without sleep" in block and "gravely hurt" in block
    assert not any(ch.isdigit() for ch in block)


# --- 2. the clock reaches the brief -------------------------------------------------------------

def test_a_turn_that_crosses_the_day_says_so_last(sammy):
    """'I sleep' at 09:49, woken at 17:49: the brief's top line said afternoon and the beat
    said "The morning air is cold". The hour the turn carried them into goes last."""
    s = _scene(sammy, clock=5 * DAY + 17 * HOUR + 49)
    line = prompts.hour_now(s, was_clock=5 * DAY + 9 * HOUR + 49)
    assert "it was morning when the player spoke" in line
    assert "afternoon" in line.split("it is now", 1)[1]
    assert "TIME PASSED THIS TURN" in prompts.scene_now(s, was_clock=5 * DAY + 9 * HOUR + 49)


def test_a_turn_that_stays_in_its_hour_says_nothing_of_it(sammy):
    """A line that is always there is a formula the prose copies; a beat that stays in one
    part of the day is not in danger of this."""
    s = _scene(sammy, clock=5 * DAY + 10 * HOUR)
    assert prompts.hour_now(s, was_clock=5 * DAY + 9 * HOUR + 49) == ""
    assert prompts.hour_now(s, was_clock=None) == ""


def test_the_engine_stamps_the_clock_before_each_batch(sammy):
    s = _scene(sammy)
    from rules.places import home_set
    from world.loader import load_cached

    world = load_cached("fixtures/aurvantis-campaign.json")
    e = Engine(s, Dice(seed=2), world=world)
    e.place_party(next(iter(home_set(world.get("bde94b038cba")))).id)
    before = s.clock_minutes
    res = e.run(e.validate([{"op": "rest", "actor": "pc", "because": "I sleep",
                             "params": {"kind": "night"}}]))
    assert res.clock_before == before
    assert s.clock_minutes - before >= 8 * HOUR


# --- 2. the hour read back: every sentence, not one ------------------------------------------

def _facts(clock):
    return bv.Facts(start="the road to Grotburrow", end="the road to Grotburrow",
                    places=("the road to Grotburrow",),
                    people=(bv.Person("pc", "Sammy", pc=True),), clock=clock)


def test_both_mornings_at_17_49_are_contradictions():
    """'The morning air' at 17:49 after sleeping from 9:49. The reader's hour was ONE
    object, so the reading named "the gray morning" and never "The morning air is cold";
    the repair mended the one it was told of and the other shipped. A list reports both,
    and each is judged against the clock."""
    answer = {"player_ends_at": {"place": "the road to Grotburrow", "quote": ""},
              "changed_hands": [], "trades": [], "harmed": [], "arrived": [], "left": [],
              "time_of_day": [{"part": "morning", "quote": "The morning air is cold"},
                              {"part": "morning",
                               "quote": "turn the gray morning into a harsh, golden glare"}]}
    facts = _facts(5 * DAY + 17 * HOUR + 49)
    kept, _dropped = bv.validate(bv.claims_of(answer, facts), WOKE_AT_DUSK, facts)
    found = [d for d in bv.diff(kept, facts, WOKE_AT_DUSK) if d.category == "hour"]
    assert len(found) == 2
    assert found[0].sentence.startswith("The morning air is cold")
    assert found[1].sentence.startswith("You wake to find the sun")


def test_an_hour_recorded_as_one_object_still_reads():
    """The bench's gold and the tests' scripted replies hold the old single object."""
    facts = _facts(5 * DAY + 17 * HOUR + 49)
    claims = bv.claims_of({"time_of_day": {"part": "afternoon", "quote": "x y z"}}, facts)
    assert [(c.category, c.slots["part"]) for c in claims] == [("hour", "afternoon")]


def test_the_hour_slot_is_a_list_in_the_schema():
    s = bv.schema(_facts(0))["properties"]["time_of_day"]
    assert s["type"] == "array"


# --- 1. the body held to the page --------------------------------------------------------------

def test_a_starving_pc_at_18_of_73_walked_a_calm_road(sammy):
    """The owner's beat 63, read with the sheet as it stood: the page shows nothing of the
    wounds, the hunger or the five sleepless days. One finding, naming only those, on a
    sentence about the player that does not say the hour."""
    found = body_shown.find(_ctx(_scene(sammy), CALM_WALK))
    assert [f.kind for f in found] == ["body-left-off-the-page"]
    f = found[0]
    for words in ("gravely hurt", "starving", "without sleep"):
        assert words in f.fix_hint
    assert f.sentences and f.sentences[0].startswith("You travel the stretch of road")
    assert not any(ch.isdigit() for ch in f.fix_hint)


def test_a_body_the_page_shows_is_left_alone(sammy):
    """Beat 65 shows the fatigue ("your muscles ache"), the parched throat and the heavy
    body; with the sheet fed, rested and whole except for the fatigue it has nothing to
    find. Generous on purpose: the benefit of the doubt costs nothing."""
    sammy.hp = sammy.hp_max
    sammy.fed_minutes = sammy.awake_minutes = 0
    sammy.add_condition("fatigued", source="sleeping rough")
    assert body_shown.find(_ctx(_scene(sammy), WOKE_AT_DUSK)) == []


def test_the_models_own_lack_of_food_is_hunger_shown():
    """Live, 2026-10-05: "the lack of food makes your head swim with a dull, hollow ache"
    was written by the model, missed by the family, and a pool line for hunger was put
    beneath it."""
    assert body_shown.shown("The lack of food makes your head swim. What now?", "hunger")


def test_a_half_mended_body_keeps_its_rewrite(sammy):
    """Live, 2026-10-05: the rewrite carried the hunger and not the wound; `find` named the
    rewritten sentence again, and the repair threw away the half that held. A sentence
    that already carries the body is never the anchor, so the next finding names another
    sentence and the rewrite stands."""
    half = ("You travel the road, your empty stomach twisting at every step. "
            "You stop by the fence. What do you do?")
    found = body_shown.find(_ctx(_scene(sammy), half))
    assert found and found[0].sentences == ("You stop by the fence.",)
    assert "starving" not in found[0].fix_hint


def test_another_persons_belly_is_not_the_players(sammy):
    """The family word must sit in a sentence about the player."""
    text = "The farmer pats his belly and laughs. You walk on. What do you do?"
    assert body_shown.missing(_ctx(_scene(sammy), text))


def test_the_backstop_writes_what_is_missing_and_never_twice_running(sammy):
    """When the rewrite does not hold: an authored line per strain, worst first, two at
    most, before the hand-back, least-recently-used per campaign — and the detector
    recognises its own lines (D1: the death line that was not, measured four of four)."""
    s = _scene(sammy)
    ctx = _ctx(s, CALM_WALK)
    first, notes = body_shown.backstop(ctx, CALM_WALK, body_shown.find(ctx))
    assert len(notes) == 2 and first.rstrip().endswith("What do you do?")
    assert len(body_shown.authored_in(first)) == 2
    second, _ = body_shown.backstop(ctx, CALM_WALK, body_shown.find(ctx))
    assert body_shown.authored_in(first) != body_shown.authored_in(second)


def test_every_authored_line_shows_its_own_strain():
    """A backstop the detector cannot see is a backstop that fires every beat."""
    for cell, pool in body_shown.POOL.items():
        key = cell.split(":")[0]
        for line in pool:
            assert body_shown.shown(line, key), line
            assert not any(ch.isdigit() for ch in line)


def test_a_fight_is_left_to_its_blows(sammy):
    fighting = SimpleNamespace(in_encounter=True, pc=lambda: sammy, said={})
    assert body_shown.find(_ctx(fighting, CALM_WALK)) == []


# --- the coordinator's addendum: terrain that is not here ----------------------------------------

def test_a_desert_sun_on_the_mountain_by_vormoor_is_not_here():
    """Beat 71: "boulders weathered by the desert sun" on the mountain off the road to
    Grotburrow — farmland underfoot, the desert only in Vormoor's far ring. A desert seen
    in the distance is a view; a desert sun on the stones is a place the party is not in."""
    from tests.test_b_checks import _ctx as land_ctx, _engine

    s, e = _engine(at="bde94b038cba~farmland:@the-outskirts")
    here = "To your left, the path is bordered by boulders weathered by the desert sun."
    found = land_described.find(land_ctx(here, s, e))
    assert [f.kind for f in found] == ["absent-ground"]
    view = "Far to the south, the desert shimmers on the horizon."
    assert land_described.find(land_ctx(view, s, e)) == []


def test_a_reach_a_walk_out_is_not_underfoot_until_the_party_is_in_it():
    """The terrain lane made Vormoor's badlands a reach two hours out and put its ground
    in the near ring; merged as built, "the desert sun" on the farmland outskirts passed
    again (2026-10-05). A reach is a place of its own: its ground is not here from the
    fields, and it is here once the party stands in it."""
    from tests.test_b_checks import _ctx as land_ctx, _engine

    here = "To your left, the path is bordered by boulders weathered by the desert sun."
    s, e = _engine(at="bde94b038cba~farmland:@the-outskirts")
    assert [f.kind for f in land_described.find(land_ctx(here, s, e))] == ["absent-ground"]
    s, e = _engine(at="bde94b038cba~desert:@the-badlands")
    assert land_described.find(land_ctx(here, s, e)) == []


def test_the_ground_here_reads_the_places_own_words():
    """One reader of the ground here, so a place that carries its own terrain is picked
    up in one spot (lane fix/ventured-place-terrain)."""
    ctx = SimpleNamespace(
        scene=SimpleNamespace(at="bde94b038cba~farmland:@the-road-to-x/the-mountain"),
        engine=SimpleNamespace(here=lambda: SimpleNamespace(name="the mountain")))
    assert land_described.ground_here(ctx) == {"farmland", "mountain"}

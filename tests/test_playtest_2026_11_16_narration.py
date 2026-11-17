"""The narration of the 2026-11-16 playtest (Vesna Kroll on 0.3.8: a ship taken by threat,
then the crypts and sewers; log pgm-work/playtest-2026-11-16.md, the item numbers below).
Each test names what the page said."""
from __future__ import annotations

from types import SimpleNamespace

from gm import agent, beat_verify as bv, planned
from gm.checks import body_shown
from rules import cards
from rules.dice import Dice
from rules.engine import Engine, Outcome, Scene
from rules.sheet import load_pc

PC = bv.Person("pc", "Vesna Kroll", pc=True)
CAPTAIN = bv.Person("c19", "the captain", "Korvu")


def facts(*outcomes, **kw):
    base = dict(start="the main channel", end="the main channel",
                places=("the main channel",), people=(PC, CAPTAIN), clock=47172,
                outcomes=tuple(outcomes))
    base.update(kw)
    return bv.Facts(**base)


def claim(category, sentence="The sentence as written.", **slots):
    return bv.Claim(category, slots, quote=sentence, sentence=sentence, valid=True)


def _check(skill, verdict="success", effects=()):
    return {"intent_id": "i1", "op": "check", "status": "resolved", "actor": "pc",
            "verdict": verdict, "rolls": [{"label": f"{skill} check", "visibility": "player"}],
            "dc": {"value": 12, "band": "average"}, "effects": list(effects),
            "because": "meticulously inspecting the masonry for hidden passages",
            "tell": f"Vesna Kroll makes the {skill.lower()} check by 4."}


SEARCH_READ = {"question": False, "actions": [
    {"act": "search", "object": "a hidden passage", "span": "go over every brick"}]}


# --- #50 and #53: a search made over nothing, told as a find ---------------------------------

def test_a_search_made_over_nothing_is_asked_as_finding_nothing():
    """#50: Survival 16 over DC 12, no effect, and the model wrote "Your methodical search
    reveals nothing but solid, unyielding masonry" — true. The attempts question, told "the
    attempt works", called it a contradiction, and the repair wrote "reveals a hidden
    passage concealed within the masonry": the save still has the culvert `found: false`.
    #53: Perception 10 over DC 8, the slot wrote "a hidden seam behind a bricked-up
    opening". A made search with no effect found nothing: a find is now the contradiction,
    and nothing found agrees."""
    f = facts(_check("Survival"), searching=True)
    [a] = bv.attempts_of(f)
    assert a.empty and a.verdict == "failure"
    found = bv.diff([claim("attempt", "Your search reveals a hidden passage.",
                           attempt="a1", shown="succeeds")], f)
    assert [(d.kind, d.category) for d in found] == [("contradiction", "attempt")]
    assert "find nothing" in found[0].fact and "the attempt works" not in found[0].fact
    assert bv.diff([claim("attempt", "It reveals nothing but solid masonry.",
                          attempt="a1", shown="fails")], f) == []
    # Perception needs no reading: it is the search skill.
    assert bv.attempts_of(facts(_check("Perception")))[0].empty


def test_a_search_that_found_something_or_was_not_a_search_is_asked_as_before():
    """The engine records a find as the roll's effect (`dungeons.searched`'s way down), and
    a Survival check the player's line was not read as a search is any other check."""
    way = {"kind": "way_down_found", "feature": "a bricked-up culvert", "at": "x"}
    assert bv.attempts_of(facts(_check("Perception", effects=[way])))[0].verdict == "success"
    assert not bv.attempts_of(facts(_check("Survival")))[0].empty
    assert not bv.found_nothing(_check("Perception", verdict="failure"))
    opposed = dict(_check("Perception"), dc={"value": 14, "basis": "opposed"})
    assert not bv.found_nothing(opposed)


class _Roll:
    def as_dict(self):
        return {"label": "Perception check", "visibility": "player"}


def test_the_act_slot_is_told_a_made_search_found_nothing():
    """#53's slot was asked "The engine decided this: Vesna Kroll makes the perception check
    by 2. The player had said: … to find the hidden passage in this wall" and wrote the
    passage found. It is now told the search turned up nothing."""
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    engine = Engine(s, Dice(seed=3))
    made = Outcome("i1", "check", verdict="success", actor="pc", rolls=[_Roll()],
                   tell="Kesst Vayr makes the perception check by 2.",
                   because="searching for a bricked-up opening")
    say = next(x["say"] for x in planned.build_plan(
        engine, "I search the wall for the hidden passage.", [made]) if x["key"] == "fact1")
    assert "turns up NOTHING" in say
    found = Outcome("i1", "check", verdict="success", actor="pc", rolls=[_Roll()],
                    tell="Kesst Vayr makes the perception check by 2.",
                    effects=[{"kind": "way_down_found", "feature": "a culvert", "at": "x"}])
    say = next(x["say"] for x in planned.build_plan(
        engine, "I search the wall.", [found]) if x["key"] == "fact1")
    assert "NOTHING" not in say


# --- #5: the ship yielded, cut as a gift nobody made ------------------------------------------

def test_a_ship_yielded_to_the_player_is_not_a_thing_nobody_gave():
    """#5: the slot wrote "The captain is shaken by your words, casting aside their weapon to
    yield the ship to you", the read-back took it as `something else` handed from the captain
    to the player, judged "Nothing was given to the player", and cut it: the page never said
    the Red Gull was hers. The engine's `ship_taken` effect is the thing that came to her."""
    taken = {"op": "check", "status": "resolved", "actor": "pc", "verdict": "success",
             "rolls": [{"label": "Intimidate check"}],
             "effects": [{"kind": "yields", "ref": "c19"},
                         {"kind": "ship_taken", "vessel": "v1", "by": "pc"}]}
    gift = claim("hands", "casting aside their weapon to yield the ship to you",
                 item=bv.OTHER_THING, **{"from": "c19", "to": "pc"})
    assert bv.diff([gift], facts(taken)) == []
    # With no ship taken, the same claim is still the gift the engine never made.
    untaken = dict(taken, effects=[{"kind": "yields", "ref": "c19"}])
    assert [d.category for d in bv.diff([gift], facts(untaken))] == ["hands"]


# --- #10: another town's matter on the page at sea --------------------------------------------

def test_a_matter_of_another_town_is_not_pulled_where_the_party_is():
    """#10: on the Red Gull's deck the matter slot was handed Kalimnar's strain, raised by
    "merchant" in the tells, and wrote it "ripple through the port … the north crossing and
    … the great square". A matter of the world there is not heard here; the player's own
    quest from another town still is."""
    s = Scene()
    s.at = "ship-sailing-ship-f4bd~deck:the-deck"
    strain = cards.Card(id="kalimnar-strain", title="Economic competition between clans "
                        "and merchants", facts=["Merchants and clans compete."],
                        keys=cards.keys_from("economic competition clans merchants"),
                        tags=(cards.TAG_STRAIN,), place="02e5ebf1ed76")
    cards.open_card(s, strain, turn=0)
    line = "I hunt the merchants' ships along the clans' trade route."
    assert cards.salience(s, recent=[], player_text=line, turn=3) == []
    s.at = "02e5ebf1ed76~urban:the-docks"
    assert [c.id for _, _, c in cards.salience(s, recent=[], player_text=line, turn=3)] \
        == ["kalimnar-strain"]


# --- #25 and #46: the wound in every beat ---------------------------------------------------

def test_the_body_is_owed_once_an_hour_or_when_it_changes():
    """#25: badly hurt from day 32 on, and the check owed it on every beat: 25 of the 26
    beats from 202 to 247 said "your body aching", most put there by this check's own
    rewrite, and #46 handed the wounds to a gardener. Told once, the strain is owed again an
    hour of game time later, or at once when it changes."""
    pc = load_pc("fixtures/pc-kesst.json")
    pc.hp_max, pc.hp = 26, 13
    s = Scene(location_id="7ef5e373c993")
    s.add(pc)
    s.clock_minutes = 47000
    assert [x.key for x in body_shown.owed(s)] == ["wounds"]
    body_shown.note_told(s, "You limp along, your wounds throbbing. What do you do?")
    assert body_shown.owed(s) == []
    ctx = SimpleNamespace(scene=s, text="You walk on to the main channel. What do you do?")
    assert body_shown.find(ctx) == [] and "BODY" not in planned.prompts.scene_now(s)
    s.clock_minutes += body_shown.RETELL_MINUTES
    assert [x.key for x in body_shown.owed(s)] == ["wounds"]
    s.clock_minutes -= body_shown.RETELL_MINUTES
    pc.hp = 5                                   # worse: told again at once
    assert [x.words for x in body_shown.owed(s)] == ["gravely hurt, wounds that hurt with "
                                                     "every movement"]


def test_a_body_shown_when_not_owed_does_not_push_the_next_telling_away():
    """The model's own unprompted ache leaves the clock where the last owed telling put it."""
    pc = load_pc("fixtures/pc-kesst.json")
    pc.hp_max, pc.hp = 26, 13
    s = Scene(location_id="7ef5e373c993")
    s.add(pc)
    s.clock_minutes = 1000
    body_shown.note_told(s, "Your wounds throb.")
    s.clock_minutes = 1050
    body_shown.note_told(s, "Your wounds throb.")
    s.clock_minutes = 1000 + body_shown.RETELL_MINUTES
    assert body_shown.owed(s)


# --- #38: a slot's sentence rewritten in place, taken for cut --------------------------------

def test_a_slot_sentence_rewritten_in_place_is_not_taken_for_cut():
    """#38: the body repair turned "You emerge into the gardens, leaving the mite behind in
    the dark." into "You limp into the gardens, your body aching with every step as you
    leave the mite behind in the dark.", `keep_act_slots` no longer knew the sentence for
    the slot's, and pasted the travel tell raw beside it ("The ground changes: streets,
    yards and rooftops. … It takes half an hour. Left behind: the mite.")."""
    old = "You emerge into the gardens, leaving the mite behind in the dark."
    new = ("You limp into the gardens, your body aching with every step as you leave the "
           "mite behind in the dark.")
    slots = ({"key": "fact1", "wrote": old,
              "tells": ["The ground changes: streets, yards and rooftops. You are at the "
                        "gardens now. Left behind: the mite."]},)
    before, after = f"{old} What do you do?", f"{new} What do you do?"
    assert agent.keep_act_slots(before, after, slots, rewrites={new: old}) == (after, [])
    # Without the record of the rewrite it is the paste the page carried.
    text, notes = agent.keep_act_slots(before, after, slots)
    assert "The ground changes" in text and notes


def test_a_stand_in_line_drops_the_roll_when_the_rest_tells_the_outcome():
    """The #5 replay after the fix: a repair cut the yield's slot and the stand-in read
    "You make the intimidate check. The captain is shaken. …" — the roll's own sentence,
    pasted. Dropped when the rest of the tell says what came of it; kept when it is all."""
    line = planned.engine_line(["Vesna Kroll makes the intimidate check by 12. The captain "
                                "is shaken. The Red Gull is yours.",
                                "Vesna Kroll misses the perception check by 6."])
    assert line == ("The captain is shaken. The Red Gull is yours. Vesna Kroll misses the "
                    "perception check.")


def test_a_taken_twenty_is_no_natural_twenty_to_the_table():
    """The search lane's live take-20 turn: the table said "That natural twenty is a gift".
    A taken 20 is built as a given 1d20 face labelled "taking 20", and no die was rolled."""
    from play import table_talk
    from rules.dice import Roll

    def kinds(label):
        o = Outcome("i1", "check", verdict="success", actor="pc",
                    rolls=[Roll("1d20", [20], label=label, visibility="player")],
                    tell="Vesna Kroll searches the main channel and finds nothing.")
        s = Scene(location_id="7ef5e373c993")
        s.add(load_pc("fixtures/pc-kesst.json"))
        o.actor = s.pc().ref
        return table_talk.moments(SimpleNamespace(scene=s), SimpleNamespace(outcomes=[o]))[0]

    assert "natural" not in kinds("Perception — searching, taking 20")
    assert "natural" in kinds("Perception check")


# --- #36: a creature further in, written as here ----------------------------------------------

def test_a_creature_further_in_is_not_given_the_aside():
    """#36: the venture's tell put the mite "further in"; with nobody else here the aside
    slot wrote "A small fey moves among the shadows, continuing its silent work in the
    dark". Kept far with no square, out of a fight, it is nobody the player can see."""
    from rules.bestiary import instantiate

    s = Scene(location_id="7ef5e373c993")
    s.add(load_pc("fixtures/pc-kesst.json"))
    mite = instantiate("thug", scene=s, name="mite")
    s.add(mite)
    s.zones[mite.ref] = "far"
    s.positions.pop(mite.ref, None)
    engine = Engine(s, Dice(seed=3))
    walked = Outcome("i1", "travel", actor="pc", tell="You are at the sewers now.")
    keys = [x["key"] for x in planned.build_plan(engine, "I look around.", [walked])]
    assert "aside" not in keys
    s.zones[mite.ref] = "near"
    keys = [x["key"] for x in planned.build_plan(engine, "I look around.", [walked])]
    assert "aside" in keys

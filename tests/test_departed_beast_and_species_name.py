"""The beast that left and stayed, and the kind that introduced itself as a name.

The owner, 2026-10-09, playing 0.2.12 (sammy.json, the ridgelines above an Aurvantis
town): prospecting for ore, "Making for one last seam, you find an Aelzeldra there before
you. The Aelzeldra holds the ground between you and the seam". The player rested twelve
hours in front of it; the page said "The Aelzeldra is gone. There is no sign of the
beast" while the engine kept it on its seam; then, asked "What is your name", it answered
"I am Aelzeldra" — "it introduced itself as its species like it was a name".

What the save and the code showed (docs/departed-beast-and-species-name.md):

  * Aelzeldra is no species. She is a named hag of a Society adventure (PFS 1-50), one of
    the 6,406 spreadsheet rows whose ground is a guess, drawn onto a seam by the forage's
    creature table and called "an Aelzeldra" by its tell.
  * `judgement.name_the_nameless` then gave her her template's name as a true name and a
    Goblin's body line — a copy of the arrival's "is this a person?" rule that never had
    the rule in it — and both readers were shown her as "c28: Aelzeldra — human".
  * The read back DID have a slot for the departure (`left`), and the second read refused
    it: "does this sentence say that Aelzeldra goes out of the place?" of "The Aelzeldra
    is gone." was answered no.
"""
from __future__ import annotations

import json

import pytest

from gm import beat_reader, beat_verify as bv, judgement, mentions
from play import campaign as cm
from rules import bestiary, gathering, ontheway
from rules.bestiary import instantiate
from rules.engine import Scene
from rules.sheet import load_pc
from tests.beat_verify import gold as G


@pytest.fixture(scope="module")
def world():
    return cm.load_cached(cm._resolve_world_source("fixtures/aurvantis-campaign.json"))


@pytest.fixture
def town(world):
    s = Scene(location_id=world.by_name("Vormoor", kind="CITY").id)
    s.add(load_pc("fixtures/pc-kesst.json"))
    return s


class _Dice:
    """Dice that answer by label: `answers[label]` (a number, or a list taken in turn);
    anything not given rolls 1."""

    def __init__(self, **answers):
        self.answers = {k.replace("_", " "): v for k, v in answers.items()}

    def roll(self, notation, label="", visibility=""):
        got = self.answers.get(label, 1)
        if isinstance(got, list):
            got = got.pop(0) if got else 1
        return type("R", (), {"total": int(got)})()


# --- the land: only what the book puts there ------------------------------------------------

def _window(biome: str, level: int, stated: bool) -> list[dict]:
    low, high = gathering._cr_window(level, False)
    return [r for r in bestiary.search(biome=biome, cr_min=low, cr_max=high, stated=stated,
                                       limit=9999)
            if r.get("cr_value") is not None
            and r.get("creature_type") not in ("humanoid", "outsider", "undead")]


def test_the_forage_draws_only_what_the_book_puts_on_the_ground():
    """Measured 2026-10-09 in the hills at fifth level, the owner's seam: 151 of the 197
    creatures the forage could draw were spreadsheet rows with a guessed ground — Aelzeldra,
    Thora Petska, Doctor Oathsday, Mrs. Pedipalp, a Restraining Chair, a Supply Sack. The
    Bestiary's own encounter tables list kinds and never a named somebody. Every pick of
    the forage's table is now a block whose ground is stated, and the hag is not among
    them."""
    everything = _window("hills", 5, stated=False)
    stated = _window("hills", 5, stated=True)
    assert any(r["id"] == "aelzeldra" for r in everything), "the guessed pool held her"
    assert 20 <= len(stated) < len(everything)
    drawn = set()
    for k in range(1, len(stated) + 1):
        row = gathering.creature_for("hills", 5, _Dice(what_lives_here=k))
        assert bestiary.ground_stated(row), row["name"]
        drawn.add(row["id"])
    assert "aelzeldra" not in drawn and len(drawn) == len(stated)


@pytest.mark.parametrize("biome", ["forest", "hills", "mountain", "swamp", "desert",
                                   "grassland", "tundra", "coast", "underground", "urban"])
@pytest.mark.parametrize("level", [1, 3, 5, 8, 12])
def test_every_ground_still_has_something_living_on_it(biome, level):
    """Narrowing the draw must not empty the land: measured from first to twelfth level the
    stated windows hold 18 to 116 creatures on every biome but the planes (and water at
    twelfth, 9)."""
    assert len(_window(biome, level, stated=True)) >= 10


def test_the_road_and_the_night_draw_from_the_same_ground():
    """`ontheway.road` and `ontheway.night` drew from the same guessed pool as the forage;
    both ask `ground_stated` now (the caravan's `foes_from_the_land` too)."""
    pool = bestiary.search(biome="hills", cr_min=max(1 / 3, 5 - ontheway.BELOW),
                           cr_max=max(1, 5 + ontheway.ABOVE), stated=True, limit=400)
    for k in (1, len(pool) // 2, len(pool)):
        met = ontheway.road(_Dice(the_road=1, what_is_on_the_road=10,
                                  what_lives_out_here=k), 6, "hills", level=5)
        assert met is not None and met.kind == "creature"
        assert bestiary.ground_stated(met.creature)
        slept = ontheway.night(_Dice(the_night=1, what_lives_out_here=k), 8, "hills", 5)
        assert slept is not None and bestiary.ground_stated(slept.creature)


def test_one_creature_on_the_ground_is_not_a_crash(monkeypatch):
    """A stated window can hold exactly one creature, and "1d1" is refused notation
    (`gathering.pick_index`: 53 of 100 desert prospects crashed on it, 2026-10-06). The road
    and the night pick through the same function now."""
    one = [bestiary.imported()["wyvern"]]
    monkeypatch.setattr(bestiary, "search", lambda **kw: list(one))

    class Strict(_Dice):
        def roll(self, notation, label="", visibility=""):
            assert notation != "1d1", "one of one is not rolled"
            return super().roll(notation, label, visibility)

    met = ontheway.road(Strict(the_road=1, what_is_on_the_road=10), 6, "hills", level=5)
    assert met.creature["id"] == "wyvern"
    assert ontheway.night(Strict(the_night=1), 8, "hills", 5).creature["id"] == "wyvern"


# --- a kind is called by its kind ------------------------------------------------------------

def test_a_kind_spawned_without_a_name_goes_by_its_kind():
    """The forage spawned its creature under the stat block's own name, so the board held a
    somebody called "Aelzeldra" (and would have held one called "Wyvern"): every name
    reader in the app takes a capitalised name for a proper one. A printed kind goes by its
    kind, lower-case, the way the hand-written townsfolk read; a name actually given is
    kept; and a spreadsheet row's name is left as written, because that is where the
    adventures' named individuals live."""
    assert instantiate("wyvern").name == "wyvern"
    assert instantiate("wyvern", name="Wyvern").name == "wyvern"
    assert instantiate("wyvern", name="Grisk").name == "Grisk"
    assert instantiate("wolf-dire").name == "dire wolf", "the index's 'Wolf, Dire'"
    assert instantiate("guildhand").name == "guildhand"
    assert instantiate("aelzeldra").name == "Aelzeldra", "her name, in the book"


def test_the_forage_tell_says_what_it_met():
    """"you find an Aelzeldra there before you" is what made a name read as a species."""
    wyvern = bestiary.imported()["wyvern"]
    met = gathering.Encounter("creature", 80, creature=wyvern, aggressive=False)
    assert "you find a wyvern there before you" in gathering.describe(met, "ore", "hills")
    dire = gathering.Encounter("guarded", 99, creature=bestiary.imported()["wolf-dire"])
    assert "a dire wolf sitting on it" in gathering.describe(dire, "ore", "hills")


def test_the_engines_own_seam_creature_is_a_kind(town, world):
    """End to end through the engine's forage door: the creature on the board, the tell,
    and the booked find all call it by its kind."""
    from rules.engine import Engine
    from rules.dice import Dice

    engine = Engine(town, Dice(7), world=world)
    pc = town.pc()
    effects: list = []
    wyvern = bestiary.imported()["wyvern"]
    monkey = gathering.roll
    gathering.roll = lambda biome, level, dice: gathering.Encounter(
        "creature", 80, creature=wyvern, aggressive=False)
    try:
        clause = engine._gathering_encounter(pc, "hills", 5, "ore", found={"iron-ore": 2},
                                             effects=effects)
    finally:
        gathering.roll = monkey
    ref = effects[-1]["ref"]
    assert town.actors[ref].name == "wyvern"
    assert "a wyvern there before you" in clause and "The wyvern holds the ground" in clause
    assert town.guarded_finds[-1]["guard_name"] == "wyvern"


# --- no people's face, no name, for a creature that is no person ----------------------------

def test_a_creature_gets_no_peoples_face_and_no_name(world, town):
    """`name_the_nameless` runs every turn and had no copy of the arrival's rule
    (`bestiary.is_a_person`): the owner's hag arrived faceless, and on the next turn was
    given "Aelzeldra" as a true name and "Goblin: Small, wiry, sharp-toothed …" as a face —
    which the brief then gave the narrator as fact, and the page wrote "its small, wiry
    frame". A save that already holds them is put back; a name the player gave their
    creature is kept; a person still gets both."""
    hag = instantiate("aelzeldra", scene=town)
    town.add(hag)
    judgement.name_the_nameless(town, world)
    assert hag.true_name == "" and hag.appearance == ""

    hag.true_name, hag.appearance = "Aelzeldra", "Goblin: Small, wiry, sharp-toothed."
    judgement.name_the_nameless(town, world)
    assert hag.true_name == "" and hag.appearance == "", "the owner's save, put back"

    pet = instantiate("wyvern", scene=town)
    town.add(pet)
    pet.name = pet.true_name = "Bob"
    judgement.name_the_nameless(town, world)
    assert pet.true_name == "Bob", "the player's own naming stays"

    clerk = instantiate("guildhand", scene=town, name="clerk")
    town.add(clerk)
    judgement.name_the_nameless(town, world)
    assert clerk.true_name and clerk.appearance, "a person is still named and given a face"


def test_the_readers_are_told_what_a_creature_is_not_human(town):
    """Both readers were shown the hag as "c28: Aelzeldra — human" (the sheet's default
    race). Measured on the owner's own rest beat through the read back, three reads each
    (2026-10-09): told "human", the reader found no departure at all, 0 of 3 — the live
    result; told "monstrous humanoid", it read "The Aelzeldra is gone." as her leaving 3 of
    3."""
    hag = instantiate("aelzeldra", scene=town)
    town.add(hag)
    clerk = instantiate("guildhand", scene=town, name="clerk")
    town.add(clerk)
    shown = {p["ref"]: p["what"] for p in mentions.people(town)}
    assert shown[hag.ref] == "monstrous humanoid"
    assert "human" in shown[clerk.ref], "a person with no people keeps their race"


def test_the_readers_are_told_a_persons_people(town):
    """Replaying the owner's name turn with the hag's borrowed Goblin face gone, the
    narrator wrote the goblin figure c29 as "the goblin" — a Goblin in its brief, and
    "guildhand, human" to the readers — and the read back took "The goblin grins" for the
    goblin with a scarred cheek held across town: an `absent` finding on the goblin in 6 of
    6 replays, one of them rewritten to "The goblin is nowhere to be seen" while he stood
    there. A person of the world's own people is shown to the readers as that people."""
    figure = instantiate("guildhand", scene=town, name="figure")
    figure.heritage = "Goblin"
    town.add(figure)
    shown = {p["ref"]: p["what"] for p in mentions.people(town)}
    assert shown[figure.ref] == "guildhand, Goblin"


# --- the departure the engine never made -------------------------------------------------------

# The reader's answer on the bench beat `gone-while-you-slept` (the owner's draft, cut to
# the sentences the label needs), as gemma-4-12B gave it 3 of 3 on 2026-10-09.
GONE_READ = {"player_ends_at": {"place": "the ridgelines", "quote": ""},
             "changed_hands": [], "trades": [], "harmed": [], "arrived": [],
             "left": [{"who": "c28", "quote": "The Aelzeldra is gone."}],
             "time_of_day": [{"part": "dawn", "quote": "cold and silent in the dawn light"}]}


def test_a_departure_the_engine_never_made_is_a_contradiction():
    """The engine kept the creature on its seam (`state.holding-ground` lifts only for a
    fight or a player who closes on it), so "The Aelzeldra is gone." contradicts it."""
    beat = G.by_id("gone-while-you-slept")
    facts = G.facts(beat)
    reading = bv.read(beat["text"], facts, model="stub",
                      chat=lambda *a, **k: type("R", (), {
                          "text": json.dumps(GONE_READ), "json": lambda s: GONE_READ})())
    found = bv.diff(reading.claims, facts, beat["text"])
    assert [(d.category, d.sentence) for d in found] == [
        ("presence", "The Aelzeldra is gone.")]
    assert found[0].fact == "Aelzeldra is still here."


def test_the_second_read_asks_whether_they_have_gone():
    """The second read keeps a contradiction only on a "yes". Asked "does this sentence say
    that Aelzeldra goes out of the place?" of "The Aelzeldra is gone.", gemma answered no 3
    of 3 on the bench, and the alarm the first read had right every time was refuted.
    Probed (two asks each, temperature 0): "…has left the place, or is gone from it?" 0/2;
    "…is no longer here?" 2/2 but 0/2 on "a boy … slips out into the rain"; the wording
    kept, 2/2 on both and 0/2 on two sentences that keep the creature there. On the bench
    after it: the presence alarm 3 of 3, nothing else falsely alarmed."""
    claim = bv.Claim("left", {"who": "c28"}, "The Aelzeldra is gone.",
                     sentence="The Aelzeldra is gone.", valid=True)
    facts = G.facts(G.by_id("gone-while-you-slept"))
    d = bv.Discrepancy("contradiction", "presence", "Aelzeldra is still here.",
                       "The Aelzeldra is gone.", claim=claim)
    q = bv.question(d, facts)
    assert "has gone — left, or no longer here?" in q and "goes out of" not in q


# --- what they are is never who they are ---------------------------------------------------------

def test_a_kind_and_a_people_are_refused_as_a_name(world, town):
    """`name_refusal`: a person's people (item 14, "a man named Korvu") and a creature's
    own kind (the 2026-10-09 report) never become their name, before anything else is
    asked — even of somebody already named."""
    wyvern = instantiate("wyvern", scene=town)
    town.add(wyvern)
    assert beat_reader.name_refusal(town, world, wyvern.ref, "Wyvern") == \
        "what they are, not who"
    assert beat_reader.name_refusal(town, world, wyvern.ref, "the Dragon") == \
        "what they are, not who"
    assert beat_reader.name_refusal(town, world, wyvern.ref, "Grisk") == ""
    clerk = instantiate("guildhand", scene=town, name="clerk")
    town.add(clerk)
    assert beat_reader.name_refusal(town, world, clerk.ref, "Goblin") == \
        "a people of this world"


def test_a_worlds_non_humanoid_peoples_are_peoples_too():
    """Pangrella's peoples include ones no rulebook calls humanoid (Khra'gix, Khy'vyr): the
    world's own PEOPLE entities are read, whatever their bodies."""
    pangrella = cm.load_cached(cm._resolve_world_source("fixtures/pangrella-campaign.json"))
    s = Scene(location_id=next(e.id for e in pangrella.entities.values()
                               if str(e.kind).upper() == "CITY"))
    s.add(load_pc("fixtures/pc-kesst.json"))
    man = instantiate("guildhand", scene=s, name="man")
    s.add(man)
    for people in ("Khra'gix", "Khy'vyr", "Korvu"):
        assert beat_reader.name_refusal(s, pangrella, man.ref, people) == \
            "a people of this world", people


def _ctx(scene, reading, text, world=None):
    from gm.checks import BeatContext

    return BeatContext(
        door="turn", text=text, player_text="What is your name?", engine=None,
        scene=scene, world=world, location=None, reading=None, outcomes=(), tells=(),
        said=(), attribution=reading, brief="", brief_facts={}, pull=None, was_at="",
        acting="", turn=0)


def test_a_line_giving_ones_kind_as_a_name_is_found_and_cut(town):
    """The page side (`gm/checks/kind_as_name.py`): the reader's own answer — this name,
    this person's, this line theirs — compared with the engine's vocabularies in code. The
    repair is one targeted rewrite of the line; what still gives the kind is cut with its
    speech clause."""
    from tests.beat_reader import stub

    from gm.checks import kind_as_name

    wyvern = instantiate("wyvern", scene=town)
    town.add(wyvern)
    text = ('The wyvern lowers its head. "I am Wyvern. Go back down the hill," it says. '
            'The wind drops.')
    reading = stub.read(text, town, lines={"I am Wyvern": (wyvern.ref, "you")},
                        names={wyvern.ref: "Wyvern"})
    found = kind_as_name.find(_ctx(town, reading, text))
    assert [f.kind for f in found] == ["kind-as-name"]
    assert found[0].sentences == ("I am Wyvern. Go back down the hill,",)
    assert "no name to give" in found[0].fix_hint
    out, notes = kind_as_name.backstop(_ctx(town, reading, text), text, found)
    assert "I am Wyvern" not in out and "The wind drops." in out and notes


def test_a_real_name_and_somebody_elses_word_are_left_alone(town):
    """A name that is a name is the reader's and the engine's business, not this check's;
    and the kind in a line somebody else speaks is them talking about it."""
    from tests.beat_reader import stub

    from gm.checks import kind_as_name

    wyvern = instantiate("wyvern", scene=town)
    town.add(wyvern)
    clerk = instantiate("guildhand", scene=town, name="clerk")
    town.add(clerk)
    text = '"I am Grisk," the wyvern says. "Mind the Wyvern," the clerk says.'
    reading = stub.read(text, town, lines={"I am Grisk": (wyvern.ref, "you"),
                                           "Mind the": (clerk.ref, "you")},
                        names={wyvern.ref: "Grisk"})
    assert kind_as_name.find(_ctx(town, reading, text)) == []

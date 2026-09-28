"""Two actors may not share one name, and a name the living share is not a corpse acting.

Measured 2026-09-27 in the fight audit (`tools/narrator_audit.py --script fight --turns
12`, gemma-4-12B, docs/wrong-actor.md "Paired runs"): the scene's names were
['Kesst Vayr', 'Borin Lyraxys', 'thug', 'thug']. The spawn door had minted the second
"thug" with exactly the first one's name, and nothing checked. One of them died, and from
then on every door that finds people by name answered for both:

  * `GMAgent._groom`'s `cut_dead_men_walking` cut "The thug lets out a desperate, rattling
    groan and shuffles forward…" on the LIVING thug's own turn — the one sentence that
    said who was acting — and a rewrite call had to put a thug back;
  * the brief told the model "dead on the ground here: thug" beside "hostile towards the
    player: thug".

Two fixes, at the two places the defect lives. The minter names the newcomer apart
("second thug", the engine's own "a hand" / "a second hand" idiom); the cut declines when
the words it matched name a living actor as well — Inform asks "which do you mean?" when
words fit two things, and with nobody to ask, the cut does nothing.
"""
from __future__ import annotations

import pytest

from gm import narration
from rules.bestiary import instantiate, name_apart
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc
from world.loader import load_cached

WORLD = load_cached("fixtures/aurvantis-campaign.json")
VORMOOR = WORLD.by_name("Vormoor", kind="CITY").id

# The audit's sentence, on the living thug's own turn.
GROAN = ("The thug lets out a desperate, rattling groan and shuffles forward, raising "
         "his fists toward you.")


@pytest.fixture
def table():
    s = Scene(location_id=VORMOOR)
    s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, Dice(seed=5), world=WORLD)
    e.place_party()
    return s, e


# --- the mint -----------------------------------------------------------------------------

def test_the_spawn_door_names_the_second_thug_apart(table):
    """The audit's scene held ['Kesst Vayr', 'Borin Lyraxys', 'thug', 'thug']. A spawn of
    two thugs is now "thug" and "second thug"."""
    s, e = table
    e.run(e.validate([{"op": "spawn", "because": "the fight",
                       "params": {"template": "thug", "count": 2, "name": "thug"}}]))
    names = sorted(a.name for a in s.actors.values() if not a.is_pc)
    assert names == ["second thug", "thug"], names


def test_a_later_spawn_is_named_apart_from_the_dead_too(table):
    """The audit's collision was a living thug and a dead one: a body on the floor still
    wears its name, so a thug arriving after the first died is the second thug."""
    s, e = table
    first = s.add(instantiate("thug", scene=s, name="thug"))
    first.hp = -5
    e.run(e.validate([{"op": "spawn", "because": "reinforcements",
                       "params": {"template": "thug", "count": 1, "name": "thug"}}]))
    assert sorted(a.name for a in s.actors.values() if not a.is_pc) == \
        ["second thug", "thug"]


def test_ordinals_count_on_and_keep_the_article(table):
    s, _ = table
    for _ in range(3):
        s.add(instantiate("thug", scene=s, name="thug"))
    assert sorted(a.name for a in s.actors.values() if not a.is_pc) == \
        ["second thug", "third thug", "thug"]
    s.add(instantiate("thug", scene=s, name="a hand"))
    assert name_apart(s, "a hand") == "a second hand"
    s.add(instantiate("guildhand", scene=s, name="an elf"))
    assert name_apart(s, "an elf") == "a second elf"


def test_a_template_name_is_told_apart_as_well(table):
    """No name given: two wolves off one stat block were two actors called "Wolf"."""
    s, _ = table
    s.add(instantiate("wolf", scene=s))
    assert instantiate("wolf", scene=s).name == "second Wolf"


def test_a_resident_of_the_world_keeps_their_own_name(table):
    """Somebody in particular is never renumbered: a world entity id means a person the
    world named, and "second Drenn Ironvale" would be a stranger wearing his name."""
    s, _ = table
    s.add(instantiate("guildhand", scene=s, name="Drenn Ironvale", world_entity_id="x1"))
    again = instantiate("guildhand", scene=s, name="Drenn Ironvale", world_entity_id="x1")
    assert again.name == "Drenn Ironvale"


def test_a_name_nobody_here_wears_is_unchanged(table):
    s, _ = table
    s.add(instantiate("thug", scene=s, name="thug"))
    assert name_apart(s, "man with a thick neck") == "man with a thick neck"
    assert name_apart(s, "thugs") == "thugs"
    # Without a scene there is nobody to be told apart from — the troop's member pattern.
    assert name_apart(None, "thug") == "thug"


def test_a_troop_member_is_not_numbered(table):
    """`troops.form` instantiates a throwaway member for its name and hit points; told
    apart from a Raider already here, the unit's members would have been "second Raider"."""
    from rules import troops

    s, _ = table
    s.add(instantiate("raider", scene=s))
    unit = troops.form("raider", 6, scene=s)
    assert unit.troop.member_name == "Raider", unit.troop.member_name


# --- the cut ------------------------------------------------------------------------------

def test_the_living_thugs_groan_survives_when_the_dead_one_shares_his_name():
    """The audit's scene exactly: two actors named "thug", one dead. Before, the groan —
    the living thug's own turn — was cut as a dead man walking."""
    kept, cut = narration.cut_dead_men_walking(GROAN, ["thug"], living=["thug"])
    assert kept == GROAN and cut == []


def test_the_second_thug_named_for_himself_or_as_the_thug_is_the_living_one():
    """After the mint fix the living one is "second thug", and the model still writes
    "the thug" for him — so a living name CONTAINING the words spares the sentence."""
    for beat in (GROAN, GROAN.replace("The thug", "The second thug")):
        kept, cut = narration.cut_dead_men_walking(beat, ["thug"], living=["second thug"])
        assert cut == [], beat


def test_the_dead_are_still_cut_when_the_words_pick_them_out():
    """The guard is about ambiguity, not a hole. The dead "second thug" named in full
    beside a living "thug" is still a corpse acting; so is a dead thug with no living
    namesake at all."""
    beat = "The second thug staggers up and swings at you."
    _, cut = narration.cut_dead_men_walking(beat, ["second thug"], living=["thug"])
    assert cut == [beat]
    _, cut = narration.cut_dead_men_walking(GROAN, ["thug"], living=["Borin Lyraxys"])
    assert cut == [GROAN]
    _, cut = narration.cut_dead_men_walking(GROAN, ["thug"])
    assert cut == [GROAN]


def test_a_dead_name_is_matched_as_a_whole_word():
    """Word boundaries came in with the longest-first alternation: "thug" is not the start
    of "thuggish", and a dead "thug" does not cut a sentence about thuggish manners."""
    beat = "A thuggish grin spreads across the bartender's face as he steps closer."
    assert narration.cut_dead_men_walking(beat, ["thug"]) == (beat, [])


class _World:
    name, secret, premise, entities = "Testholme", "", {}, {}
    unwritten, chronology, factions = [], [], []

    def ancestors(self, _):
        return []


def test_through_the_groom_the_living_thug_keeps_his_turn():
    """The audit's scene through the real door, with both actors named "thug" as a save
    from before the mint fix still holds them: `_groom` builds the living list itself,
    so the groan survives on the living thug's own turn, and the same sentence with the
    only thug dead is still cut. No model call — every step here is deterministic."""
    from gm.agent import GMAgent

    s = Scene()
    s.add(load_pc("fixtures/pc-kesst.json"))
    dead = s.add(instantiate("thug", scene=s, name="thug"))
    alive = s.add(instantiate("thug", scene=s, name="thug"))
    alive.name = "thug"                      # the twins an old save holds
    dead.hp = -6
    gm = GMAgent(_World(), Engine(s, Dice(seed=1)))
    out, repairs, _ = gm._groom(GROAN, hand_back=False, claims=False, rewrite=False,
                                acting="thug")
    assert "rattling groan" in out, repairs
    assert not any("dead stayed dead" in r for r in repairs), repairs

    alive.hp = -3
    out, repairs, _ = gm._groom(GROAN, hand_back=False, claims=False, rewrite=False)
    assert "rattling groan" not in out
    assert any("dead stayed dead" in r for r in repairs), repairs


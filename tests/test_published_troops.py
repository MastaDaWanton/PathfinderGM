"""The corpus's own troop blocks arrive as crowds.

`docs/the-crowd.md` (group 9) shipped the troop rules and recorded these blocks as
deliberately left alone:

    "The corpus's own 22 troop-subtype blocks (a goblin troop at 52 hp, an imperial
     infantry troop at 126) still spawn as ordinary actors. Their `subtype` is stripped
     before the Actor is built, which is the easy half to fix — but a published troop's hit
     points ARE the unit's pool and its member count is nowhere in the data, so giving them
     attrition would mean inventing a number per block. The troop *rules* without the
     attrition would leave a readout saying '1 of 1'. Left alone rather than half-built."

The count is not in the block. It is in the SUBTYPE, and that is the half the note missed
(Archives of Nethys, read 2026-09-20):

    "A troop of Small or Medium creatures consists of approximately 12 to 30 creatures."
    "A single troop occupies a 20-foot-by-20-foot square, equal in size to a Gargantuan
     creature."

Twenty feet is four squares, so the stated footprint is 4x4 = sixteen squares, and
`troops.size_for` puts one person in each — the player's ruling, which replaced the
subtype's fixed size band. Sixteen is therefore the count at which the published footprint
and this app's own ruling agree, and it sits inside the stated band. A member's share of
the pool is the pool over sixteen, rounded up, and the count falls out of the pool from
there — so nothing is invented per block and two troops of different toughness do not come
out identical.

(The note said 22 blocks; the imported corpus holds 23.)
"""
from __future__ import annotations

import pytest

from rules import bestiary, troops
from rules.engine import Scene


def _blocks() -> list[tuple[str, dict]]:
    return [(k, v) for k, v in bestiary.imported().items()
            if troops.is_a_published_troop(v)]


BLOCKS = _blocks()


def test_the_corpus_still_ships_troop_blocks():
    """If this ever drops to zero, a re-import has lost the subtype and every troop in the
    game has quietly become one creature again."""
    assert len(BLOCKS) >= 20, len(BLOCKS)


@pytest.mark.parametrize("key", [k for k, _ in BLOCKS])
def test_every_published_troop_spawns_as_a_unit(key):
    """The whole fix, over every block the corpus ships rather than a chosen one."""
    s = Scene(location_id="t")
    actor = bestiary.instantiate(key, scene=s)
    assert actor.troop is not None, f"{key} spawned as a single creature"
    t = actor.troop
    # Inside the band the subtype states, and standing in the square it gives them.
    assert troops.published_member_count_is_sane(t.members), (key, t.members)
    assert actor.size == "gargantuan", (key, actor.size, t.members)
    assert t.members == t.members_max


@pytest.mark.parametrize("key,doc", BLOCKS)
def test_the_published_hit_points_are_the_pool_untouched(key, doc):
    """"A published troop's hit points ARE the unit's pool." Deriving a member count must
    not restate the block's own number — a troop that arrives tougher or weaker than it was
    written is a corpus this app disagrees with."""
    s = Scene(location_id="t")
    actor = bestiary.instantiate(key, scene=s)
    assert actor.hp == actor.hp_max == int(doc["hp"]), key


@pytest.mark.parametrize("key,doc", BLOCKS)
def test_the_roster_starts_full_and_agrees_with_the_pool(key, doc):
    """The set-up arithmetic and the attrition arithmetic are the same function, so a block
    cannot start out disagreeing with itself: settling a full pool must move nobody."""
    s = Scene(location_id="t")
    actor = bestiary.instantiate(key, scene=s)
    was = actor.troop.members
    assert troops.settle(actor.troop, actor.hp) == 0, key
    assert actor.troop.members == was


def test_a_published_troop_loses_members_as_it_is_hurt():
    """The readout the note refused to ship half of: "the troop rules without the attrition
    would leave a readout saying '1 of 1'"."""
    s = Scene(location_id="t")
    actor = bestiary.instantiate("hobgoblin-phalanx-troop", scene=s)
    t = actor.troop
    assert (t.members, t.member_hp) == (16, 8)        # 126 hp over the 20-foot square
    actor.hp -= 40
    fell = troops.settle(t, actor.hp)
    assert fell == 5 and t.members == 11
    assert "11 of" in troops.tell_of(t, actor.name, fell)
    actor.hp = 0
    troops.settle(t, actor.hp)
    assert t.members == 0, "reducing a troop to 0 hit points causes it to break up"


def test_an_ordinary_creature_is_not_a_crowd():
    """The guard on the whole change: only the subtype makes a unit."""
    s = Scene(location_id="t")
    assert bestiary.instantiate("black-bear", scene=s).troop is None


def test_the_unit_is_worth_what_it_was_and_the_members_share_it():
    """`xp_owed` pays for the members who actually fell when the rest run, so a member's
    share has to exist and has to add up to about the block's own value."""
    s = Scene(location_id="t")
    actor = bestiary.instantiate("hobgoblin-phalanx-troop", scene=s)
    t = actor.troop
    assert t.member_xp > 0
    assert abs(t.member_xp * t.members - actor.xp_value) <= t.members


# --- naming a member, and admitting when the name does not have one ----------------------

@pytest.mark.parametrize("block,member", [
    ("Imperial Archers Troop", "imperial archer"),
    ("Troop, Cultist", "cultist"),
    ("Profaned Paladin Troop", "profaned paladin"),
    ("Giant Bee Troop", "giant bee"),
])
def test_a_unit_name_that_names_its_members(block, member):
    assert troops.one_of(block) == member


@pytest.mark.parametrize("block", [
    "Cult Rabble",            # a member of a cult rabble is not a "cult"
    "Avalanche Legion",       # nor of an avalanche legion an "avalanche"
    "Hobgoblin Phalanx Troop",
    "Irgal's Axe Troop",      # a company named for somebody is not a kind of person
])
def test_a_unit_name_that_does_not_name_its_members(block):
    """These answer with nothing, and `tell_of` says "eight of them go down" — true, and
    it reads properly. Deciding that a member of a Cult Rabble is a "cultist" would be
    chasing vocabulary, which is the losing move CLAUDE.md records."""
    assert troops.one_of(block) == ""


def test_the_tell_reads_properly_either_way():
    made_up = troops.Troop(member="x", member_name="", member_hp=5, member_xp=10,
                           members=5, members_max=13)
    assert "8 of them go down" in troops.tell_of(made_up, "Cult Rabble", 8)
    named = troops.Troop(member="x", member_name="imperial archer", member_hp=8,
                         member_xp=10, members=7, members_max=15)
    assert "8 imperial archers go down" in troops.tell_of(named, "Imperial Archers Troop", 8)
    assert "one imperial archer goes down" in troops.tell_of(named, "Imperial Archers Troop", 1)

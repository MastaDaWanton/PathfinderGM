"""The board changing the roll — flanking, higher ground and cover.

Measured 2026-09-14, and the finding is that the geometry was all there and none of it was
connected. `grid.flanking` had been written, tested and **never called** by anything
outside its own tests; the word "cover" did not appear in `rules/engine.py` at all. So a
character could spend a turn manoeuvring behind an enemy, and a spider could take a ceiling
twenty feet up, and the dice knew nothing about either.

`rules/position.py` is the route that was missing, and it deliberately arrives at the swing
the same way `compulsion.penalty_against` does: as bare `Modifier`s added by the engine,
because every one of these depends on where *both* creatures are and the sheet knows only
its own body.

The rules, and the one invention:

    flanking      +2 melee              aonprd.com/Rules.aspx?ID=183
    higher ground +1 melee, +0 ranged   Table 8-5, aonprd.com/Rules.aspx?ID=180
    cover         +4 AC, +2 Reflex      aonprd.com/Rules.aspx?ID=181
    soft cover    +4 AC, no Reflex      same page

**How high is higher ground is not a rule.** Table 8-5 prints the +1 and defines no
threshold; two Paizo rules threads asking the question close with no FAQ and no errata.
`position.HIGHER_GROUND_SQUARES` is this project's answer — one square, the smallest
difference the engine can represent — and it is a named constant so there is one place to
argue with it.
"""
from __future__ import annotations

from rules import position
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.grid import Grid


def _board():
    """Foe in the middle, an ally either side of it, on a bare map."""
    s = Scene(location_id="t")
    a = instantiate("guildhand", scene=s, name="A")
    s.add(a, at=(4, 5))
    b = instantiate("guildhand", scene=s, name="B")
    s.add(b, at=(6, 5))
    foe = instantiate("guildhand", scene=s, name="Foe")
    foe.hp = foe.hp_base = 60
    s.add(foe, at=(5, 5))
    s.grid = Grid()
    return s, Engine(s, Dice(seed=1), world=None), a, b, foe


def _values(mods):
    return [(m.value, m.source) for m in mods]


# --- flanking -------------------------------------------------------------------------

def test_two_allies_on_opposite_sides_flank():
    """The function that was written and never called."""
    s, _e, a, _b, foe = _board()
    assert _values(position.attack_mods(s, a, foe)) == [(2, "flanking with B")]


def test_one_ally_out_of_line_does_not_flank():
    s, _e, a, b, foe = _board()
    s.positions[b.ref] = (6, 6)          # diagonal, not opposite
    assert position.attack_mods(s, a, foe) == []


def test_a_body_on_another_level_is_not_flanking_with_you():
    """Flanking is a fact about one plane: the line is drawn between two squares, and a
    creature twenty feet up is not on the other side of anything."""
    s, _e, a, b, foe = _board()
    s.positions[b.ref] = (6, 5, 3)
    assert position.attack_mods(s, a, foe) == []


def test_an_enemy_does_not_help_you_flank():
    """Allegiance lives on the scene rather than the actor, and it is only populated
    inside an encounter — so this states the sides explicitly, the way a fight does."""
    s, _e, a, b, foe = _board()
    s.sides = {"pc": [a.ref], "them": [b.ref, foe.ref]}
    assert position.attack_mods(s, a, foe) == []


# --- higher ground --------------------------------------------------------------------

def test_higher_ground_is_worth_one_to_a_melee_swing():
    s, _e, a, _b, foe = _board()
    s.positions[a.ref] = (4, 5, position.HIGHER_GROUND_SQUARES)
    assert (1, "higher ground") in _values(position.attack_mods(s, a, foe))


def test_higher_ground_is_worth_nothing_to_a_bow():
    """Table 8-5 gives ranged a +0 in as many words, which is a rule and not an
    oversight — height helps you swing down at somebody, not aim at them."""
    s, _e, a, _b, foe = _board()
    s.positions[a.ref] = (4, 5, 4)
    assert position.attack_mods(s, a, foe, {"category": "ranged"}) == []


def test_standing_below_is_worth_nothing():
    s, _e, a, _b, foe = _board()
    s.positions[foe.ref] = (5, 5, 3)
    assert not [m for m in position.attack_mods(s, a, foe) if "higher" in m.source]


# --- cover ----------------------------------------------------------------------------

def test_a_wall_between_is_worth_four_to_the_defender():
    s, _e, a, _b, foe = _board()
    s.positions[foe.ref] = (5, 3)
    s.grid.blocked = {(5, 4)}
    assert position.cover_of(s, a, foe) == "cover"
    assert _values(position.ac_mods(s, a, foe)) == [(4, "cover")]
    assert _values(position.reflex_mods(s, s.positions[a.ref], foe)) == [(2, "cover")]


def test_a_body_in_the_way_is_worth_four_and_no_reflex():
    """Soft cover's whole distinction: a bystander stops an arrow and does nothing about
    a fireball. A rule that read the AC number alone would get that wrong, in the
    player's favour, and never be noticed."""
    s, _e, a, b, foe = _board()
    s.positions[foe.ref] = (7, 5)        # B at (6,5) now stands between them
    assert position.cover_of(s, a, foe) == "soft"
    assert _values(position.ac_mods(s, a, foe)) == [(4, "soft cover")]
    assert position.reflex_mods(s, s.positions[a.ref], foe) == []


def test_walled_in_is_total_cover():
    s, _e, a, _b, foe = _board()
    s.positions[foe.ref] = (5, 3)
    s.grid.blocked = {(5, 4), (4, 4), (6, 4), (4, 3), (6, 3),
                      (5, 2), (4, 2), (6, 2)}
    assert position.cover_of(s, a, foe) == "total"


def test_nothing_in_the_way_is_nothing():
    s, _e, a, _b, foe = _board()
    assert position.cover_of(s, a, foe) == ""
    assert position.ac_mods(s, a, foe) == []


# --- the scene that has no map --------------------------------------------------------

def test_a_scene_with_no_map_gets_no_position_bonuses():
    """"We are not tracking that" is an answer. A mapless scene takes the GM's word for
    where people are, and deriving a flanking bonus from a zone word would be the engine
    asserting a fact nobody gave it."""
    s, _e, a, _b, foe = _board()
    s.grid = None
    assert position.attack_mods(s, a, foe) == []
    assert position.cover_of(s, a, foe) == ""
    assert position.ac_mods(s, a, foe) == []


# --- and that it reaches a real swing --------------------------------------------------

def _swing(e, actor_ref, target_ref):
    raw = {"op": "attack", "actor": actor_ref, "because": "t",
           "target": target_ref, "params": {}}
    return e.run(e.validate([raw], origin="author:test"))


def test_the_flank_reaches_the_attack_roll_itself():
    """The end the module exists for. A green suite with an inert pipeline is the exact
    defect this work has been unpicking, so this drives the real op and reads the
    breakdown the dice popup would show."""
    s, e, _a, _b, foe = _board()
    npc = next(r for r in s.actors if s.actors[r].name == "A")
    res = _swing(e, npc, foe.ref)

    rolled = [r for o in res.outcomes for r in (o.rolls or [])]
    assert rolled, "no roll came back from the swing"
    sources = [m.source for r in rolled for m in r.modifiers]
    assert any("flanking" in s_ for s_ in sources), sources


def test_total_cover_refuses_the_swing_rather_than_penalising_it():
    """"You cannot make an attack against a target that has total cover" is a refusal,
    not a modifier, and the reason names the geometry so the model can act on it."""
    s, e, a, _b, foe = _board()
    s.positions[foe.ref] = (5, 3)
    s.grid.blocked = {(5, 4), (4, 4), (6, 4), (4, 3), (6, 3),
                      (5, 2), (4, 2), (6, 2)}
    res = _swing(e, a.ref, foe.ref)
    tells = " ".join(o.tell for o in res.outcomes).lower()
    assert "total cover" in tells, tells

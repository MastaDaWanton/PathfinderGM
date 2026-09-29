"""Phase 3, I4: `scope.in_the_room` breaks ties by the whole name and the head noun, not by
a word counted twice (fix-interfaces §3.4).

What Lane D measured on 2026-09-28 and worked around in `hooks.resolve_target` only:

  * **A shared family name won the tie.** The shown name and the true name were scored
    separately and added, so a keeper called "Gribbet Sootspar" twice over scored the
    shared "Sootspar" twice — two, the same as the giver "Bregan Sootspar" scored for his
    given name and family name — and came first in the room, so "find Bregan Sootspar"
    answered with the keeper.
  * **A relative clause was read as the person.** On the Bobby playtest (turn 4), "the
    girl that the watchman described to me" shared "watchman" with the watchman and with
    nobody else; with him in the room the finder answered: the watchman, the one person
    the sentence says she is not.

Every scene test runs on the three worlds.
"""
from __future__ import annotations

from rules import population, schemes, scope
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

WORK_HOUR = 10 * 60


def _market(world):
    row = (world.play.get("settlements") or [])[0]
    s = Scene(location_id=row["id"])
    s.add(load_pc("fixtures/pc-kesst.json"))
    s.clock_minutes = WORK_HOUR
    e = Engine(s, Dice(seed=5), world=world)
    e.place_party(schemes._place_for(e, "market", {})["id"])
    population.drain_misses()
    return s, e


def _person(s, name, true_name=""):
    a = instantiate("guildhand", scene=s, name=name)
    if true_name:
        a.true_name = true_name
    s.add(a)
    return a


def test_a_keeper_sharing_the_givers_family_name_does_not_win(worlds):
    """The keeper arrives first and carries the family name in both its names; the giver,
    a scheme's cast member, has only the one. That is the exact shape that scored two
    against the giver's two and won on order."""
    s, _e = _market(worlds)
    keeper = _person(s, "Gribbet Sootspar", true_name="Gribbet Sootspar")
    giver = _person(s, "Bregan Sootspar")
    giver.true_name = ""
    assert list(s.actors).index(keeper.ref) < list(s.actors).index(giver.ref)
    for phrase in ("Bregan Sootspar", "find Bregan Sootspar", "Bregan", "bregan sootspar"):
        assert scope.in_the_room(s, phrase) == giver.ref, phrase
        assert scope.look_for(worlds, phrase, s, s.location_id)["ref"] == giver.ref, phrase
    assert scope.in_the_room(s, "Gribbet") == keeper.ref


def test_a_true_name_behind_a_description_is_still_said_whole(worlds):
    """A giver shown by a description until met ("the healer at the well") and a keeper
    named in full: the giver's true name said whole is the giver."""
    s, _e = _market(worlds)
    keeper = _person(s, "Gribbet Sootspar", true_name="Gribbet Sootspar")
    giver = _person(s, "the healer at the well", true_name="Bregan Sootspar")
    assert scope.in_the_room(s, "Bregan Sootspar") == giver.ref
    assert scope.in_the_room(s, "the healer") == giver.ref
    assert scope.in_the_room(s, "Gribbet Sootspar") == keeper.ref


def test_the_girl_the_watchman_described_is_the_girl_not_the_watchman(worlds):
    """Bobby, turn 4, with the watchman present: the finder must answer with the girl's
    record, never with the watchman the clause mentions."""
    s, _e = _market(worlds)
    watchman = _person(s, "the watchman waving traffic through")
    girl = population.note(s, "a girl mending a net")
    for phrase in ("the girl that the watchman described to me",
                   "the girl that the watchman described",
                   "the girl whom the watchman mentioned",
                   "the girl who the watchman told me about"):
        assert scope.in_the_room(s, phrase) == "", phrase
        found = scope.look_for(worlds, phrase, s, s.location_id)
        assert found["scope"] == scope.HERE, (phrase, found)
        assert found.get("record") == girl["id"], (phrase, found)
        assert found.get("ref", "") != watchman.ref
    # He is still who "the watchman" means.
    assert scope.in_the_room(s, "the watchman") == watchman.ref
    assert scope.in_the_room(s, "the watchman at the gate") == watchman.ref


def test_the_man_who_sold_me_bread_is_the_head_noun(worlds):
    """"the man who sold me bread" means a man; the clause is what he did, and a baker
    whose name happens to hold "Bread" is not who is meant by it."""
    s, _e = _market(worlds)
    _person(s, "Hollis Breadwater", true_name="Hollis Breadwater")
    assert scope.head_phrase("the man who sold me bread") == "the man"
    assert scope.head_phrase("the girl that the watchman described to me") == "the girl"
    # A determiner after a preposition is not a clause.
    assert scope.head_phrase("the man at that stall") == "the man at that stall"
    assert scope.in_the_room(s, "the man who sold me bread") == ""


def test_the_clause_does_not_send_the_player_to_a_watchman_elsewhere(worlds):
    """With nobody here and no girl anywhere, the world is asked whom the phrase names,
    not whom its clause mentions. Before, `matches` read every word of the phrase, so a
    world CHARACTER whose Role held the clause's noun was answered as "elsewhere" — the
    player sent across the world after the person who did the describing. Measured on
    the base, 2026-09-29, one per world: "the girl that the guildmaster described to me"
    answered "Bregan Sootspar, guildmaster, is in Ashwatch"; "…the healer described…"
    answered "Wenna Cobbe, healer, is in Brindle Ford"."""
    import re

    s, _e = _market(worlds)
    who = word = None
    for ent in worlds.entities.values():
        if getattr(ent, "kind", "") != "CHARACTER":
            continue
        role = str((getattr(ent, "facts", {}) or {}).get("Role") or "")
        words = [w for w in re.findall(r"[a-z]{5,}", role.lower()) if w != "girl"]
        if words:
            who, word = ent, words[0]
            break
    assert who is not None, f"{worlds.name}: some character has a Role"
    phrase = f"the girl that the {word} described to me"
    got = scope.look_for(worlds, phrase, s, s.location_id)
    by_the_clause = {e.name for e in worlds.entities.values()
                     if getattr(e, "kind", "") == "CHARACTER" and scope.matches(e, word)
                     and not scope.matches(e, "girl")}
    assert who.name in by_the_clause
    assert got.get("who") not in by_the_clause, (phrase, got)

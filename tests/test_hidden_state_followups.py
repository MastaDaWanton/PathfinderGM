"""The hidden-state lane's "what's left" list, built (2026-10-30, fix/hidden-state-followups).

feat/hidden-state made hiding hold across turns, and listed what it did not reach. Measured
on its head (66e654e8) before this branch, each of these was open:

  1. a `cast` or `use_ability` at an invisible, unfound player was never asked — only
     attacks and manoeuvres were gated — and a touch spell rolled no miss chance at all;
  2. the player's search was an average-DC check against nothing: a hidden NPC could not
     be found by anybody, and a scheme's `state.hidden` had no DC ("nothing to find");
  3. the refusal of Stealth-while-watched named "a diversion first", and nothing made one;
  4. mass invisibility and invisibility sphere ended each creature's on its own attack,
     the 180 ft and 10 ft rules unread, and sphere members could not see each other;
  5. every Stealth check capped the hider at half speed — the -5 band did not exist;
  6. an invisible creature using Stealth was found at its Stealth result, not result +20;
  7. the read-back's `unseen` question had never been measured.

The rules (quotes checked against the raw AoN pages, aonprd.com, on 2026-10-30): Aiming a
Spell (Rules.aspx?Name=Aiming%20a%20Spell), Invisibility (Rules.aspx?ID=431), Concealment,
Stealth and Perception (Skills.aspx), Bluff, and the three invisibility spells
(SpellDisplay.aspx). rules/awareness.py and rules/engine.py carry the quotes.
"""
from __future__ import annotations

import pytest

from rules import awareness, spells
from rules.activeeffect import ActiveEffect
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.grid import Grid
from rules.intents import IntentError
from rules.sheet import from_dict, load_pc, to_dict
from tests._places import stand_on
from tests.test_hidden_state import _drink, _finish, _tells


def _board(fight=True, seed=7, thug_at=(6, 5), pc_at=(5, 5), size=20):
    s = Scene(location_id="5bbd0c40345f", grid=Grid(size, size))
    s.add(load_pc("fixtures/pc-kesst.json"), at=pc_at)
    s.add(instantiate("thug", scene=s, name="the thug"), at=thug_at)
    stand_on(s, "urban")
    s.clock_minutes = 12 * 60
    if fight:
        s.sides = {"us": ["pc"], "them": ["c1"]}
        s.initiative = [("pc", 20), ("c1", 10)]
        s.round, s.turn = 1, 0
    for a in s.actors.values():
        a.hp = a.hp_max = 500
    return s, Engine(s, Dice(seed=seed))


def _wizard(s, ref="c2", at=(9, 5), prepared=None, npc=True):
    d = to_dict(load_pc("fixtures/pc-caster.json"))
    d["kind"] = "npc" if npc else "pc"
    d["name"] = "the hedge wizard"
    d["prepared"] = prepared or {"magic-missile": 2, "burning-hands": 2, "acid-splash": 3}
    w = s.add(from_dict(d, ref=ref), at=at)
    w.hp = w.hp_max = 500
    return w


def _hide(actor, source="scheme:test/1"):
    """A scheme's hiding (rules/schemes.py `_do` "hide"): a bare `state.hidden`."""
    actor.apply_effect(ActiveEffect(name="hidden", kind="situation", key=f"{source}:hidden",
                                    source=source, origin=source,
                                    duration="until-dismissed", tags=("state.hidden",)))


# --- 1. spells and abilities at somebody unfound -----------------------------------------

def test_a_spell_at_an_unfound_player_is_refused_by_what_its_aim_needs():
    """Only attacks and manoeuvres were gated at 66e654e8: a hedge wizard's magic missile
    at the invisible player validated and would have landed. Aiming a Spell (CRB p.213):
    "You must be able to see or touch the target, and you must specifically choose that
    target"; Concealment (p.196): "you can attack into a square that you think he
    occupies". So a targeted spell names only the search; an area spell names a guessed
    square too."""
    s, e = _board()
    _wizard(s)
    s.sides = {"us": ["pc"], "them": ["c1", "c2"]}
    _drink(s, e)
    with pytest.raises(IntentError) as err:
        e.validate([{"op": "cast", "actor": "c2", "target": "pc", "because": "x",
                     "params": {"spell": "magic-missile"}}])
    assert err.value.code == "unseen_target"
    assert '"search": true' in str(err.value) and '"guess": true' not in str(err.value)
    with pytest.raises(IntentError) as err:
        e.validate([{"op": "cast", "actor": "c2", "target": "pc", "because": "x",
                     "params": {"spell": "burning-hands"}}])
    assert '"guess": true' in str(err.value) and "burning-hands" in str(err.value)


def test_a_pinpoint_serves_a_touch_or_an_area_but_never_a_targeted_spell():
    """A pinpointed invisible creature "still benefits from total concealment" (CRB p.564),
    and a targeted spell needs a target the caster can SEE or touch. The pinpoint is enough
    for an area at that square and for acid splash's ranged touch (its description's own
    "ranged touch attack"; it has no touch_attack spec), not for magic missile."""
    s, e = _board()
    w = _wizard(s)
    s.sides = {"us": ["pc"], "them": ["c1", "c2"]}
    _drink(s, e)
    awareness.pinpoint(s, w, s.actors["pc"], "test")
    assert e._cast_needs(spells.get("acid-splash"), 1) == "locate"
    assert e._cast_needs(spells.get("magic-missile"), 1) == "sight"
    assert e._cast_needs(spells.get("burning-hands"), 1) == "square"
    with pytest.raises(IntentError) as err:
        e.validate([{"op": "cast", "actor": "c2", "target": "pc", "because": "x",
                     "params": {"spell": "magic-missile"}}])
    assert "see or touch" in str(err.value)
    for spell in ("acid-splash", "burning-hands"):
        plan = e.validate([{"op": "cast", "actor": "c2", "target": "pc", "because": "x",
                            "params": {"spell": spell}}])
        assert [i.op for i in plan] == ["cast"], spell


def test_an_area_spell_cast_at_a_guess_lands_on_a_square_the_die_picked():
    """The fix the refusal names, resolved: `guess` on a cast is the engine's die among the
    open squares within 30 ft (where a hunch points, CRB p.564), never on the caster's own
    square, and told as a guess. A spell with no area cannot be cast at a guess."""
    s, e = _board()
    _wizard(s)
    s.sides = {"us": ["pc"], "them": ["c1", "c2"]}
    _drink(s, e)
    res = e.run(e.validate([{"op": "cast", "actor": "c2", "because": "x",
                             "params": {"spell": "burning-hands", "guess": True}}]))
    out = next(o for o in res.outcomes if o.op == "cast")
    assert out.status != "refused", out.tell
    assert "guesses somebody is" in out.tell
    aim = next(x for x in out.effects if x.get("kind") == "cast").get("aim") or {}
    assert aim.get("kind") == "point" and aim.get("value") != "9,5"
    res = e.run(e.validate([{"op": "cast", "actor": "c2", "because": "x",
                             "params": {"spell": "magic-missile", "guess": True}}]))
    assert "no area" in res.outcomes[-1].tell


def test_the_players_spell_and_ability_at_a_hidden_npc_are_refused_at_the_door():
    """The player is asked the same rule (2026-10-30), refused at the door in words — an
    IntentError would be a planner retry rewriting the player's own deed — and nothing
    is spent."""
    s = Scene(location_id="5bbd0c40345f", grid=Grid(20, 20))
    pc = _wizard(s, ref="pc", at=(5, 5), npc=False)
    s.add(instantiate("thug", scene=s, name="the thug"), at=(9, 5))
    stand_on(s, "urban")
    e = Engine(s, Dice(seed=7))
    _hide(s.actors["c1"])
    before = dict(pc.prepared)
    res = e.run(e.validate([{"op": "cast", "actor": "pc", "target": "c1", "because": "x",
                             "params": {"spell": "magic-missile"}}]))
    out = res.outcomes[-1]
    assert out.status == "refused" and "Search for them first" in out.tell, out.tell
    assert pc.prepared == before
    res = e.run(e.validate([{"op": "use_ability", "actor": "pc", "target": "c1",
                             "because": "x", "params": {"ability": "rage"}}]))
    assert res.outcomes[-1].status == "refused"
    assert "does not know where they are" in res.outcomes[-1].tell


def test_a_touch_spell_rolls_the_miss_chance_a_blow_does(monkeypatch):
    """`_touches` rolled no miss chance before 2026-10-30, so a touch spell at a pinpointed
    invisible creature landed on every hit where a sword missed half of them. Concealment
    is a property of the attack (CRB p.196); the one reader is `_concealment_of`."""
    from rules import engine as engine_mod

    s, e = _board()
    w = _wizard(s, prepared={"acid-splash": 3})
    _drink(s, e)
    awareness.pinpoint(s, w, s.actors["pc"], "test")
    monkeypatch.setattr(engine_mod, "d20_succeeds", lambda roll, ac: True)
    state = {"rolls": [], "tells": []}
    e._touches(engine_mod.Intent(op="cast", actor="c2"), w, s.actors["pc"],
               spells.get("acid-splash"), {"touch": "ranged"}, {}, state)
    assert any("miss chance (invisible" in str(r.get("label")) for r in state["rolls"]), state


# --- 2. the player finds what hides ------------------------------------------------------

def test_the_players_search_finds_a_hidden_npc_at_its_dc():
    """Before: the player's search was "the ordinary Perception check it always was", and a
    scheme's bare `state.hidden` answered "nothing to find" — a hidden NPC could never be
    found. Now the player's own roll is set against each hiding at its DC: a Stealth
    result, or the hider's 10 when it hid with nobody watching ("Taking 10", CRB p.86).
    Found, the PLAYER holds `knows.where.c1`, and the NPC is seen."""
    s, e = _board(fight=False, thug_at=(9, 5))
    pc, thug = s.actors["pc"], s.actors["c1"]
    _hide(thug)
    dc = awareness.notice_dcs(s, pc, thug)[0]
    assert dc == 10 + awareness._stealth_bonus(thug) + 2, "its 10, +1 per 10 ft (20 ft)"
    assert not awareness.sees(s, pc, thug)
    res = _finish(e, e.run(e.validate([{
        "op": "check", "actor": "pc", "because": "looks",
        "params": {"skill": "perception", "search": True}}])), face=19)
    assert awareness.knows_where(s, pc, thug), _tells(res)
    assert any(t.startswith("knows.where.c1") for x in pc.effects for t in x.tags)
    assert "finds where the thug is" in _tells(res)
    assert awareness.sees(s, pc, thug)


def test_a_failed_search_says_nothing_of_anyone_hidden():
    """A creature's failed search is told "finds nothing"; the player's is not, or the
    page would learn somebody is hidden (CRB p.564: "tell him that the character has
    missed, regardless of the result")."""
    s, e = _board(fight=False, thug_at=(9, 5))
    thug = s.actors["c1"]
    _hide(thug)
    thug.add_buff("skill_mod", "stealth", 60, source="test: a shadow")
    res = _finish(e, e.run(e.validate([{
        "op": "check", "actor": "pc", "because": "looks",
        "params": {"skill": "perception", "search": True}}])), face=2)
    assert not awareness.knows_where(s, s.actors["pc"], thug)
    assert "hidden" not in _tells(res) and "thug" not in _tells(res)


def test_an_invisible_npc_is_the_tables_dc_for_the_player_and_a_found_one_takes_fifty():
    """Invisibility (CRB p.564): DC 20 to notice, +20 to pinpoint, +20 holding still. An
    NPC under the condition is 40/60 to the player while still; pinpointed, a blow at it
    still meets the 50% miss chance."""
    s, e = _board()
    thug = s.actors["c1"]
    thug.add_condition("invisible", 10, source="test", origin="author:test")
    assert awareness.notice_dcs(s, s.actors["pc"], thug)[:2] == (40, 60)
    awareness.pinpoint(s, s.actors["pc"], thug, "test")
    assert e._concealment_of(s.actors["pc"], thug)[0] == 50


def test_the_player_cannot_strike_an_unfound_npc_but_may_guess_the_square():
    """The NPCs' rule, asked the other way (Concealment, CRB p.196). Refused by name with
    the ways round; `guess` with the player's own `square` ("have the player choose the
    space", CRB p.564) is a real attack when the NPC is there — through the miss chance —
    and a swing at air told only as a miss when not."""
    s, e = _board()
    thug = s.actors["c1"]
    _hide(thug)
    out = e.run(e.validate([{"op": "attack", "actor": "pc", "target": "c1",
                             "because": "x"}])).outcomes[-1]
    assert out.status == "refused" and "nowhere to go" in out.tell
    res = _finish(e, e.run(e.validate([{"op": "attack", "actor": "pc", "because": "swing",
                                        "params": {"guess": True, "square": [6, 5]}}])))
    labels = [str(r.label) for o in res.outcomes for r in o.rolls]
    assert any("miss chance (unnoticed)" in lab for lab in labels), (labels, _tells(res))
    res = _finish(e, e.run(e.validate([{"op": "attack", "actor": "pc", "because": "swing",
                                        "params": {"guess": True, "square": [4, 4]}}])))
    out = next(o for o in res.outcomes if o.op == "attack")
    assert out.verdict == "miss" and "swings blind" in out.tell and "thug" not in out.tell


def test_an_npc_that_hides_by_stealth_is_found_by_the_players_search():
    """The NPC's own Stealth (behind a wall, so it may hide) is held as the player's is,
    and the player's search is set against its result."""
    s, e = _board(fight=False, thug_at=(12, 5))
    for y in range(2, 9):
        s.grid.blocked.add((8, y))
    thug = s.actors["c1"]
    thug.add_buff("skill_mod", "stealth", 40, source="test: a cutpurse's practice")
    res = e.run(e.validate([{"op": "check", "actor": "c1", "because": "hides",
                             "params": {"skill": "stealth",
                                        "opposed_by": {"ref": "pc", "skill": "perception"}}}]))
    assert thug.has_state(awareness.SNEAKING), _tells(res)
    assert not awareness.sees(s, s.actors["pc"], thug)
    s.actors["pc"].add_buff("skill_mod", "perception", 60, source="test: an eagle's eye")
    _finish(e, e.run(e.validate([{"op": "check", "actor": "pc", "because": "looks",
                                  "params": {"skill": "perception", "search": True}}])))
    assert awareness.sees(s, s.actors["pc"], thug)


# --- 3. a diversion to hide --------------------------------------------------------------

def _open_ground(fight=False):
    s, e = _board(fight=fight, thug_at=(11, 5))
    for y in range(7, 12):
        s.grid.blocked.add((3, y))          # a wall to slip behind, within a dash
    pc = s.actors["pc"]
    pc.add_buff("skill_mod", "bluff", 30, source="test: a silver tongue")
    pc.add_buff("skill_mod", "stealth", 30, source="test: a quiet foot")
    return s, e, pc


def test_a_bluff_diversion_lets_the_player_hide_while_watched():
    """Stealth, CRB p.106: "If your observers are momentarily distracted (such as by a
    Bluff check), you can attempt to use Stealth ... if you can get to an unobserved place
    of some kind. This check, however, is made at a –10 penalty because you have to move
    fast." At 66e654e8 the refusal named "a diversion first" and nothing could make one.
    Now the Bluff (against the thug's Sense Motive) holds `state.diverting`; the Stealth
    check that follows walks to the nearest square out of his sight and rolls at -10."""
    s, e, pc = _open_ground()
    alone = e.run(e.validate([{"op": "check", "actor": "pc", "because": "hide",
                               "params": {"skill": "stealth", "opposed_by": {
                                   "ref": "c1", "skill": "perception"}}}]))
    assert alone.outcomes[-1].status == "refused"
    res = _finish(e, e.run(e.validate([
        {"op": "check", "actor": "pc", "because": "shout",
         "params": {"skill": "bluff", "diversion": True}},
        {"op": "check", "actor": "pc", "because": "hide",
         "params": {"skill": "stealth", "opposed_by": {"ref": "c1",
                                                       "skill": "perception"}}}])))
    assert "draws the thug's eyes away" in _tells(res)
    assert "slips into cover" in _tells(res)
    assert pc.has_state(awareness.SNEAKING), _tells(res)
    assert tuple(s.positions["pc"][:2]) != (5, 5)
    mods = [m.source for o in res.outcomes for r in o.rolls for m in r.modifiers]
    assert any("diversion" in m for m in mods)
    assert e._diversion(pc) is None, "spent by the check"


def test_a_diversion_that_fools_nobody_leaves_the_watcher_watching():
    s, e, pc = _open_ground()
    pc.add_buff("skill_mod", "bluff", -80, source="test: a poor liar")
    res = _finish(e, e.run(e.validate([
        {"op": "check", "actor": "pc", "because": "shout",
         "params": {"skill": "bluff", "diversion": True}},
        {"op": "check", "actor": "pc", "because": "hide",
         "params": {"skill": "stealth", "opposed_by": {"ref": "c1",
                                                       "skill": "perception"}}}])), face=1)
    assert "fools nobody" in _tells(res)
    assert res.outcomes[-1].status == "refused" and not pc.has_state(awareness.HIDDEN)


def test_the_reader_builds_the_bluff_and_the_stealth_from_its_closed_answers():
    """No word list: the reader's `stealth` action carries `pace` and `diversion` as
    sampler-held enums (`interpret.per_act_schema`), and the act table builds the Bluff
    ahead of the Stealth check, the hurried one at `pace: full`."""
    from gm import acts_to_ops, interpret

    alts = interpret.per_act_schema()["properties"]["actions"]["items"]["anyOf"]
    sneak = next(a for a in alts if a["properties"]["act"].get("const") == "stealth")
    assert sneak["properties"]["pace"]["enum"] == ["careful", "hurried"]
    assert sneak["properties"]["diversion"]["enum"] == ["none", "bluff"]
    s, e = _board(fight=False, thug_at=(11, 5))
    frame = {"question": False, "claims": [], "actions": [
        {"act": "stealth", "span": "duck behind the cart", "pace": "hurried",
         "diversion": "bluff"}]}
    rows = acts_to_ops.table(frame, s)
    built = [i for r in rows for i in r.intents]
    assert [(i["params"]["skill"], i["params"].get("diversion"), i["params"].get("pace"))
            for i in built] == [("bluff", True, None), ("stealth", None, "full")]
    kept, _dropped = interpret.ground({"actions": [
        {"act": "stealth", "span": "dash for the woodpile", "pace": "hurried",
         "diversion": "nonsense"}]}, "I dash for the woodpile")
    assert kept["actions"][0].get("pace") == "hurried"
    assert "diversion" not in kept["actions"][0]


# --- 4. one invisibility for several -----------------------------------------------------

def _group(e, spell_id, targets, recipient="pc"):
    spell = spells.get(spell_id)
    return e._run_specs([x for x in spells.effects_at(spell, 7)
                         if x.get("type") == "apply_condition"],
                        {"caster": "pc", "targets": list(targets), "rounds": 70,
                         "recipient": recipient, "source": spell.name,
                         "origin": f"spell:{spell_id}", "self_ok": True})


def _ally(s, at=(4, 4)):
    s.add(instantiate("thug", scene=s, name="the hired sword"), at=at)
    s.sides = {"us": ["pc", "c2"], "them": ["c1"]}
    s.actors["c2"].hp = s.actors["c2"].hp_max = 500
    return s.actors["c2"]


def test_mass_invisibility_breaks_for_the_whole_group_on_anyones_attack():
    """Invisibility, Mass (CRB p.302): "the effect moves with the group and is broken when
    anyone in the group attacks. Individuals in the group cannot see each other." The lane
    ended each creature's on its own attack (the document's note said so). The brief for
    this branch read it as each attack ending only its own; the page's contrast with the
    sphere ("negate the invisibility only for themselves") and with its own next sentence
    ("broken for any individual who moves") says the whole group."""
    s, e = _board()
    ally = _ally(s)
    _group(e, "invisibility-mass", ["pc", "c2"])
    pc = s.actors["pc"]
    assert pc.has_state(awareness.INVISIBLE) and ally.has_state(awareness.INVISIBLE)
    assert not awareness.sees(s, pc, ally), "members cannot see each other"
    res = _finish(e, e.run(e.validate([{"op": "attack", "actor": "c2", "target": "c1",
                                        "because": "stab"}])))
    assert not ally.has_state(awareness.INVISIBLE)
    assert not pc.has_state(awareness.INVISIBLE), _tells(res)
    assert "breaks the invisibility they shared" in _tells(res)


def test_mass_invisibility_breaks_for_the_one_who_goes_past_180_feet():
    """"The spell is broken for any individual who moves more than 180 feet from the
    nearest member of the group" — asked of the mover, on the map."""
    s, e = _board(fight=False, size=60)
    ally = _ally(s)
    _group(e, "invisibility-mass", ["pc", "c2"])
    res = e.run(e.validate([{"op": "move", "actor": "c2", "because": "walks off",
                             "params": {"square": [45, 4]}}]))
    assert not ally.has_state(awareness.INVISIBLE), _tells(res)
    assert s.actors["pc"].has_state(awareness.INVISIBLE), "the one left standing keeps it"
    assert "too far from the others" in _tells(res)


def test_the_sphere_holds_together_around_its_recipient():
    """Invisibility Sphere (CRB p.302): "Those affected by this spell can see each other
    ... Any affected creature moving out of the area becomes visible ... Affected creatures
    (other than the recipient) who attack negate the invisibility only for themselves. If
    the spell recipient attacks, the invisibility sphere ends." The 10 ft emanation moves
    with its recipient."""
    s, e = _board()
    ally = _ally(s)
    third = s.add(instantiate("thug", scene=s, name="the porter"), at=(5, 6))
    s.sides["us"].append(third.ref)
    third.hp = third.hp_max = 500
    _group(e, "invisibility-sphere", ["c2", third.ref], recipient="pc")
    pc = s.actors["pc"]
    assert all(a.has_state(awareness.INVISIBLE) for a in (pc, ally, third)), \
        "the recipient is always inside"
    assert awareness.sees(s, pc, ally) and awareness.sees(s, ally, third)
    assert not awareness.sees(s, s.actors["c1"], pc)
    # A member walking out of the 10 ft becomes visible; the others keep it.
    e.run(e.validate([{"op": "move", "actor": "c2", "because": "wanders",
                       "params": {"square": [4, 9]}}]))
    assert not ally.has_state(awareness.INVISIBLE) and pc.has_state(awareness.INVISIBLE)
    # A member's attack ends only its own.
    _finish(e, e.run(e.validate([{"op": "attack", "actor": third.ref, "target": "c1",
                                  "because": "stab"}])))
    assert not third.has_state(awareness.INVISIBLE) and pc.has_state(awareness.INVISIBLE)


def test_the_recipients_attack_or_walk_ends_the_sphere_for_the_others():
    s, e = _board()
    ally = _ally(s, at=(5, 6))
    _group(e, "invisibility-sphere", ["c2"], recipient="pc")
    pc = s.actors["pc"]
    e.run(e.validate([{"op": "move", "actor": "pc", "because": "strides off",
                       "params": {"square": [5, 0]}}]))
    assert pc.has_state(awareness.INVISIBLE) and not ally.has_state(awareness.INVISIBLE), \
        "the centre moved and left the member outside"
    s2, e2 = _board()
    ally2 = _ally(s2, at=(5, 6))
    _group(e2, "invisibility-sphere", ["c2"], recipient="pc")
    _finish(e2, e2.run(e2.validate([{"op": "attack", "actor": "pc", "target": "c1",
                                     "because": "stab"}])))
    assert not s2.actors["pc"].has_state(awareness.INVISIBLE)
    assert not ally2.has_state(awareness.INVISIBLE)


# --- 5. the -5 band ----------------------------------------------------------------------

def test_a_hurried_hiding_takes_minus_five_and_keeps_full_speed():
    """Stealth, CRB p.106: "When moving at a speed greater than half but less than your
    normal speed, you take a -5 penalty." At 66e654e8 every hiding carried `state.slowed`
    and the band did not exist. `pace: full` (the reader's `hurried`) puts the -5 on the
    roll and lays `sneaking-fast`, with no slowing; careful keeps the half speed."""
    s, e = _board(fight=False, thug_at=(12, 5))
    for y in range(2, 9):
        s.grid.blocked.add((8, y))
    pc = s.actors["pc"]
    pc.add_buff("skill_mod", "stealth", 40, source="test")
    res = _finish(e, e.run(e.validate([{
        "op": "check", "actor": "pc", "because": "dash",
        "params": {"skill": "stealth", "pace": "full",
                   "opposed_by": {"ref": "c1", "skill": "perception"}}}])))
    mods = [(m.source, m.value) for o in res.outcomes for r in o.rolls for m in r.modifiers]
    assert ("moving faster than half speed", -5) in mods
    assert pc.has_state(awareness.SNEAKING) and not pc.has_state("state.slowed")
    assert pc.speed_feet == 30 and "full speed" in _tells(res)
    _finish(e, e.run(e.validate([{
        "op": "check", "actor": "pc", "because": "creep",
        "params": {"skill": "stealth", "opposed_by": {"ref": "c1", "skill": "perception"}}}])))
    assert pc.has_state("state.slowed") and pc.speed_feet == 15
    assert sum(1 for x in pc.effects if awareness.SNEAKING in x.tags) == 1, "one hiding"


def test_pace_and_diversion_are_held_to_their_skills():
    s, e = _board(fight=False)
    with pytest.raises(IntentError):
        e.validate([{"op": "check", "actor": "pc", "because": "x",
                     "params": {"skill": "climb", "pace": "full", "dc": {"band": "easy"}}}])
    with pytest.raises(IntentError):
        e.validate([{"op": "check", "actor": "pc", "because": "x",
                     "params": {"skill": "stealth", "diversion": True}}])


# --- 6. the +20 on a Stealth result ------------------------------------------------------

def test_an_invisible_creature_using_stealth_is_found_at_its_result_plus_twenty():
    """The Invisibility table (CRB p.564) reads "Using Stealth | Stealth Check +20". The
    lane read the +20 as the condition's own Stealth bonus and added nothing, so a result
    of 30 was noticed at 30. Perception's own table settles it: "Notice a creature using
    Stealth: Opposed by Stealth" with the DC modifier "Creature or object is invisible
    +20" — the same +20 that makes "Notice a visible creature 0" the DC 20 — while the
    condition's +20/+40 is a bonus on the Stealth roll (Stealth, CRB p.106). 50 to notice,
    70 to pinpoint."""
    s, e = _board()
    _drink(s, e)
    pc = s.actors["pc"]
    pc.apply_effect(ActiveEffect(name="Hidden", kind="condition", key="sneaking",
                                 source="rule:stealth", origin="rule:stealth",
                                 tags=("state.hidden.stealth", "state.slowed"),
                                 payload={"result": 30, "at": s.at}))
    assert awareness.notice_dcs(s, s.actors["c1"], pc)[:2] == (50, 70)
    pc.effects[-1].payload["result"] = 5
    assert awareness.notice_dcs(s, s.actors["c1"], pc)[:2] == (40, 60), \
        "a poor roll never makes an invisible body easier to find than standing still"


# --- 7. the read-back's unseen question --------------------------------------------------

def test_the_unseen_confirmation_asks_what_the_first_read_asked():
    """tools/unseen_bench.py on 28 hand-labelled beats, gemma-4-12B, two runs: the first
    read caught 14/14 and alarmed 0/14 clean beats, but the second read refuted "The gate
    guard tells you to move along" both runs (recall 13/14) — its question named looking,
    turning and aiming, and not the first read's "speaking to you". The two lists agree."""
    from gm import beat_verify as bv
    from tests.beat_verify import unseen_gold as G

    assert len(G.BEATS) >= 16
    assert sum(1 for b in G.BEATS if b["flag"]) >= 8
    assert sum(1 for b in G.BEATS if not b["flag"]) >= 8
    facts = G.facts(G.BEATS[0])
    c = bv.Claim("unseen", {"who": "c1"}, "x")
    d = bv.Discrepancy("contradiction", "unseen", "", "s", "", c, ref="c1")
    q = bv.question(d, facts)
    for word in ("speaking to you", "reaching for you", "looking at you", "striking"):
        assert word in q or word.replace("looking at you", "looking at you (the") in q
    assert "speaking to you" in bv._UNSEEN_SYSTEM and "reaching for you" in bv._UNSEEN_SYSTEM


# --- found driving the live app, 2026-10-30 ----------------------------------------------

def test_a_built_diversion_or_search_is_not_given_a_band():
    """Live, the diversion scenario: the reading's built `check bluff diversion=true` was
    given `dc: average` by `fill_bare_checks` and refused seven plans running ("a diversion
    is rolled against every watcher's sense motive ... Drop the dc"), until the turn fell
    to the fallback. A search is the same shape."""
    from gm import judgement

    out = judgement.fill_bare_checks([
        {"op": "check", "actor": "pc", "params": {"skill": "bluff", "diversion": True}},
        {"op": "check", "actor": "pc", "params": {"skill": "perception", "search": True}},
        {"op": "check", "actor": "pc", "params": {"skill": "climb"}}])
    assert [("dc" in r["params"]) for r in out] == [False, False, True]


def test_the_books_inverted_spell_names_are_found_as_said():
    """Live, a wizard 13: "I cast mass invisibility on Bran and Wenna" matched only the
    one-word Invisibility, and the means gate refused "mass invisibility" as no spell of
    hers while printing "Invisibility, Mass" in the same refusal's list."""
    from gm import judgement

    for said, want in (("I cast mass invisibility on Bran", "invisibility-mass"),
                       ("greater invisibility on me", "invisibility-greater"),
                       ("I cast mass cure light wounds", "cure-light-wounds-mass"),
                       ("I cast invisibility", "invisibility")):
        assert judgement.spell_in_words(said).id == want, said


def test_the_players_cast_is_the_spell_their_words_name_at_everyone_aimed_at():
    """Live, the same turn after the name fix: the plan's third attempt was `magic-missile`
    at Bran and `magic-missile` at Wenna — the allies the player meant to hide — and it
    validated, because `inject_cast` stands down once the plan casts anything. The named
    spell is put back, an `at` list is the `target` list, and two casts of a spell with
    plural targets ("creatures") are one casting."""
    from gm import judgement

    s = Scene(location_id="5bbd0c40345f")
    d = to_dict(load_pc("fixtures/pc-caster.json"))
    d["level"] = 13
    d["spellbook"] = list(d["spellbook"]) + ["invisibility-mass"]
    d["prepared"] = {"invisibility-mass": 1, "magic-missile": 2}
    s.add(from_dict(d, ref="pc"))
    s.add(instantiate("thug", scene=s, name="Bran"))
    s.add(instantiate("thug", scene=s, name="Wenna"))
    said = "I cast mass invisibility on Bran and Wenna."
    planned = [{"op": "cast", "actor": "pc", "params": {"spell": "magic-missile", "at": "c1"}},
               {"op": "cast", "actor": "pc", "params": {"spell": "magic-missile", "at": "c2"}}]
    assert judgement.the_named_spell(planned, said, s) == [
        {"op": "cast", "actor": "pc", "params": {"spell": "invisibility-mass"},
         "target": ["c1", "c2"]}]
    listed = [{"op": "cast", "actor": "pc",
               "params": {"spell": "mass invisibility", "at": ["c1", "c2"]}}]
    assert judgement.the_named_spell(listed, said, s)[0]["target"] == ["c1", "c2"]

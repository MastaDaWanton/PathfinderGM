"""A thrown flask is a splash weapon (alchemy plan §16.2, contracts §7).

CRB, Throw Splash Weapon (aonprd.com/Rules.aspx?Name=Throw%20Splash%20Weapon): "make a
ranged touch attack against the target. Thrown splash weapons require no weapon
proficiency ... A hit deals direct hit damage to the target and splash damage to all
creatures within 5 feet of the target ... target a specific grid intersection. Treat this
as a ranged attack against AC 5 ... If you miss the target, roll 1d8 ... count a number of
squares in the indicated direction equal to the range increment of the throw ... it deals
splash damage to all creatures in that square and in all adjacent squares."

Measured before any of this (build/alchemy, 3bbd361): `use_item how=throw` landed every
effect on its target with no roll at all ("That attack is not emitted here", the op's own
docstring), nobody beside the target was touched (`SPLASH_RADIUS_FT` was read nowhere),
and a miss could not happen.
"""
from __future__ import annotations

import pytest

from rules.bestiary import instantiate
from rules.crafting import Stock
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError, parse
from rules.sheet import from_dict, load_pc

FIRE = [{"type": "damage", "dice": "1d6", "damage_type": "fire", "route": "struck"},
        {"type": "burning", "dice": "1d6", "rounds": 1, "dc": 15, "smother_bonus": 2,
         "route": "struck"}]
TANGLEFOOT = [{"type": "apply_condition", "target": "entangled", "route": "struck",
               "duration": {"amount": 4, "unit": "round"}},
              {"type": "save_gate", "target": "ref", "dc": 15, "route": "struck",
               "on_failure": [{"type": "apply_condition", "target": "glued",
                               "duration": {"amount": 4, "unit": "round"}}]}]


def _board(specs=FIRE, *, seed=7, gap=4):
    """Kesst, a thug `gap` squares east of her, and a second thug beside the first."""
    s = Scene(location_id="5bbd0c40345f")
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="the thug"))
    s.add(instantiate("thug", scene=s, name="the other thug"))
    pc.stock["flask#1"] = Stock(base="Alchemist's Fire", count=3, specs=[dict(x) for x in specs])
    e = Engine(s, Dice(seed=seed))
    e._ensure_encounter("pc")
    s.positions["pc"] = (2, 10)
    s.positions["c1"] = (2 + gap, 10)
    s.positions["c2"] = (3 + gap, 10)
    s.resync_zones()
    return s, e


def _throw(e, face, **params):
    res = e.run(e.validate([{"op": "use_item", "actor": "pc", "because": "she throws it",
                             "params": {"item": "flask#1", "how": "throw", **params}}]))
    prompt = res.awaiting
    if res.status != "complete":
        res = e.resume(face=face)
    return prompt, res


def _told(res) -> str:
    return " ".join(o.tell for o in res.outcomes)


def test_a_thrown_flask_rolls_a_ranged_touch_attack_and_splashes_the_neighbour():
    """The plan's first lane-3 test: a thrown alchemist's fire rolls a ranged touch
    attack, and on a hit deals 1 fire to whoever stands 5 ft from the target. Before:
    no roll, no splash."""
    s, e = _board()
    # A guard in chainmail, built rather than printed: a stat block with no AC note (the
    # hand-written thug) prints one AC for touch and all, which is the data's limit, not
    # the rule's.
    s.remove("c1")
    thug = s.add(from_dict({"name": "the guard", "kind": "npc", "hp": 12, "hp_max": 12,
                            "armour": "chainmail",
                            "abilities": {k: 10 for k in ("str", "dex", "con", "int",
                                                          "wis", "cha")}}, ref="c1"))
    s.positions["c1"] = (6, 10)
    e.join_fight("c1")
    other = s.actors["c2"]
    before = other.hp
    prompt, res = _throw(e, 19, to="c1")
    assert prompt is not None and prompt["die"] == "1d20"
    # Touch AC, not full AC: the guard's chainmail (+6) does not count against a flask.
    ff = e._flat_footed(thug)
    assert prompt["dc"] == thug.touch_ac(ff, attacker=s.pc())
    assert prompt["dc"] == thug.ac(flat_footed=ff) - 6
    # No nonproficiency penalty, and Dexterity, not Strength.
    sources = [m["source"] for m in prompt["breakdown"]]
    assert not any("proficient" in x for x in sources), sources
    assert "Dex" in sources and "Str" not in sources
    told = _told(res)
    assert "breaks on the guard" in told
    assert thug.hp < thug.hp_max
    assert other.hp == before - 1, told        # the book's 1 point of splash
    assert any(e2.get("kind") == "splash" for o in res.outcomes for e2 in o.effects)


def test_the_thrower_beyond_five_feet_is_not_splashed_and_the_dose_is_spent_once():
    s, e = _board()
    pc = s.pc()
    hp = pc.hp
    _throw(e, 19, to="c1")
    assert pc.hp == hp
    assert pc.stock["flask#1"].count == 2


def test_a_miss_scatters_by_the_d8_and_splashes_where_it_lands():
    """"count a number of squares ... equal to the range increment of the throw": 20 ft
    is inside the first 10-ft increment? No — 20 ft is the SECOND increment, so two
    squares. The broken flask lies where it landed (`Scene.place_prop`), and the d8 is
    rolled and kept."""
    s, e = _board(gap=4)
    prompt, res = _throw(e, 1, to="c1")                      # a natural 1 misses
    attack = next(o for o in res.outcomes if o.op == "attack")
    assert any(r.die == "1d8" for r in attack.rolls)
    prop = s.prop_named("broken Alchemist's Fire")
    assert prop is not None and prop.get("square")
    aim = s.positions["c1"]
    dx, dy = prop["square"][0] - aim[0], prop["square"][1] - aim[1]
    # Two squares in one of the eight directions (clamped to the board's edge).
    assert max(abs(dx), abs(dy)) in (1, 2) and (dx == 0 or dy == 0 or abs(dx) == abs(dy))
    assert "misses the thug (natural 1)" in _told(res)
    assert s.actors["c1"].hp == s.actors["c1"].hp_max or "breaks" in _told(res)


def test_the_range_increment_costs_two_a_step_and_five_is_the_most():
    """−2 per full range increment past the first; a thrown weapon "has a maximum range
    of five range increments" (CRB). Past it nothing is thrown and nothing is spent."""
    s, e = _board(gap=5)                                       # 25 ft: two increments
    prompt, _ = _throw(e, 19, to="c1")
    assert any(m["source"].startswith("range (25 ft") and m["value"] == -4
               for m in prompt["breakdown"]), prompt["breakdown"]
    s2, e2 = _board(gap=11)                                    # 55 ft: past 50
    out = e2.run(e2.validate([{"op": "use_item", "actor": "pc", "because": "t",
                               "params": {"item": "flask#1", "how": "throw",
                                          "to": "c1"}}]))
    assert out.status == "complete"
    assert "past a thrown flask's reach" in _told(out)
    assert s2.pc().stock["flask#1"].count == 3


def test_a_grid_intersection_is_ac_5_and_splashes_the_four_squares_it_touches():
    s, e = _board(gap=4)
    corner = [7, 10]           # the corner shared by c1 (6,10) and c2 (7,10)
    prompt, res = _throw(e, 12, square=corner)
    assert prompt["dc"] == 5
    told = _told(res)
    assert s.actors["c1"].hp == s.actors["c1"].hp_max - 1, told
    assert s.actors["c2"].hp == s.actors["c2"].hp_max - 1, told


def test_with_no_map_a_miss_shatters_wide(monkeypatch):
    """No map, no squares to count: the miss lands nowhere anyone stands (plan §16.2,
    proposed). The fight's gate lays a map, so it is held off here."""
    s = Scene(location_id="5bbd0c40345f")
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="the thug"))
    pc.stock["flask#1"] = Stock(base="Alchemist's Fire", count=1, specs=list(FIRE))
    e = Engine(s, Dice(seed=3))
    monkeypatch.setattr(e, "_splash_gate", lambda a, d: "")
    assert not s.has_grid
    _, res = _throw(e, 1, to="c1")
    assert "shatters somewhere wide of everyone" in _told(res)


def test_parse_refuses_a_model_writing_the_splash_mode():
    """The flask's documents ride the attack the engine emits; a model writing
    `mode: splash` with its own dice would be authoring a number."""
    with pytest.raises(IntentError):
        parse({"op": "attack", "actor": "pc", "target": "c1",
               "params": {"mode": "splash", "flask": {"struck": []}}})


def test_the_fire_burns_next_round_and_rolling_puts_it_out():
    """"On the round following a direct hit, the target takes an additional 1d6 ... a
    full-round action to attempt to extinguish the flames ... DC 15 Reflex save. Rolling on
    the ground provides the target a +2 bonus" (CRB, alchemist's fire)."""
    s, e = _board()
    _throw(e, 19, to="c1")
    thug = s.actors["c1"]
    assert thug.has_state("state.burning")
    hp = thug.hp
    # Rolled over to the next round: the clinging fire burns once, then is gone.
    s.turn = len(s.initiative) - 1
    s.advance_turn()
    assert thug.hp < hp
    assert not thug.has_state("state.burning")
    assert any(h.get("kind") == "damage" and h.get("ref") == "c1" for h in s.hazards)


def test_extinguish_is_a_reflex_save_with_the_rolling_bonus_and_water_smothers():
    s, e = _board()
    _throw(e, 19, to="c1")
    thug = s.actors["c1"]
    out = e.run(e.validate([{"op": "extinguish", "actor": "c1", "because": "he rolls",
                             "params": {"roll": True}}]))
    roll = out.outcomes[0].rolls[0]
    assert any(m.source == "rolling on the ground" and m.value == 2 for m in roll.modifiers)
    assert ("go out" in out.outcomes[0].tell) == (not thug.has_state("state.burning"))
    with pytest.raises(IntentError, match="no document behind this number"):
        e.validate([{"op": "burn", "actor": "c1", "params": {"to": "c1", "dice": "9d6"}}])
    s.pc().effects.clear()
    refused = e.run(e.validate([{"op": "extinguish", "actor": "pc", "params": {}}]))
    assert "not on fire" in refused.outcomes[0].tell


def test_a_tanglefoot_hit_entangles_and_a_failed_reflex_glues():
    """The bag (CRB): a hit entangles; a failed DC 15 Reflex save also glues the target
    to the floor, "unable to move", until a DC 17 Strength check or 15 slashing to the
    goo frees it. The catalogue gave two entangles and no glue."""
    s, e = _board(TANGLEFOOT, seed=1)
    _, res = _throw(e, 19, to="c1")
    thug = s.actors["c1"]
    assert thug.has_state("state.held.entangled")
    glued = thug.has_state("state.held.glued")
    told = _told(res)
    assert "Reflex save" in told
    if glued:
        assert thug.speed_feet == 0
        assert thug.movement_modes() == {"land": 0}
        with pytest.raises(IntentError, match="0 ft of movement"):
            e.validate([{"op": "move", "actor": "c1", "because": "t",
                         "params": {"square": [9, 12]}}])
        for _ in range(12):
            out = e.run(e.validate([{"op": "break_free", "actor": "c1", "because": "t",
                                     "params": {"how": "strength"}}]))
            if not thug.has_state("state.held.glued"):
                assert "tears free" in out.outcomes[0].tell
                break
        assert not thug.has_state("state.held.glued")
        assert thug.has_state("state.held.entangled")          # half speed stays


def test_a_made_reflex_save_does_not_claim_the_bag_did_nothing():
    """Measured live (alchemy lane C): "Tanglefoot Bag has no effect on Mott. Mott is
    entangled for 4 rounds." The save holds off the glue; the entangle still lands."""
    for seed in range(1, 12):
        s, e = _board(TANGLEFOOT, seed=seed)
        _, res = _throw(e, 19, to="c1")
        if not s.actors["c1"].has_state("state.held.glued"):
            told = _told(res)
            assert "has no effect" not in told, told
            assert "holds off the worst of" in told and "entangled" in told
            return
    pytest.fail("no seed made the save")


def test_a_harmful_spell_in_a_flask_takes_the_struck_creature_as_its_target():
    """The owner's ruling (open point 5): a harmful spell may go into a thrown flask, the
    struck creature its target — drunk, the drinker would be."""
    s, e = _board([])
    s.pc().stock["flask#1"] = Stock(base="Flask of Acid Splash", count=1,
                                    holds_spell="acid-splash", caster_level=1)
    pc_hp = s.pc().hp
    _, res = _throw(e, 19, to="c1")
    thug = s.actors["c1"]
    assert thug.hp < thug.hp_max, _told(res)
    assert any(x.get("kind") == "damage" and x.get("ref") == "c1"
               and x.get("origin") == "item:flask#1"
               for o in res.outcomes for x in o.effects)
    assert s.pc().hp == pc_hp

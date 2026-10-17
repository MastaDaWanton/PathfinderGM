"""The weapon the player names is the weapon swung — drawn first, and paid for in a fight.

Measured live on master, 2026-10-16 (scratch copy of the owner's save, Kesst Vayr with a
rapier in hand and a dagger on the belt): "I draw my dagger and stab the shopkeeper" was
read by the live reader as `attack, object: my dagger, target: the shopkeeper`. Nothing
below the reader looked at the object, the plan wrote no `weapon`, and the engine swung
what was in hand — "Kesst Vayr's attack with the rapier misses…", the prose "the blade of
your rapier". And a plan that DID name the dagger had it swung straight off the belt, the
rapier still in hand, no draw ever made.

The rules (Core Rulebook p.186, Draw or Sheathe a Weapon, aonprd.com/Rules.aspx?ID=140):
"Drawing a weapon so that you can use it in combat ... requires a move action"; "if you
have a base attack bonus of +1 or higher, you may draw a weapon as a free action combined
with a regular move". Quick Draw (p.132): "a free action instead of as a move action". A
full attack is a full-round action, so after a draw that cost a move action one attack is
left. The engine holds one weapon (`Actor.equipped`), so the draw is the `wear` door every
draw already goes through (docs/creature-rearms.md) and the one in hand goes back to the
belt: one move action, the price of either legal way to do it with a one-handed weapon
(drop it, a free action, and draw; or draw into the free hand).
"""
from __future__ import annotations

import json

from gm import acts_to_ops
from gm import agent as agent_mod
from gm import interpret
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

from _a_truth import VORMOOR, WORLD


def _fight(seed: int = 3, *, gap: int = 1, level: int | None = None):
    """Kesst, rapier in hand and a dagger carried, in a fight with a thug `gap` squares
    east; her turn."""
    s = Scene(location_id="5bbd0c40345f")
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    if level is not None:
        pc.level = level
    assert pc.equipped == "rapier" and "dagger" in pc.weapons
    thug = s.add(instantiate("thug", scene=s, name="the thug"))
    thug.hp = thug.hp_base = 200         # never dropped by the first swing
    e = Engine(s, Dice(seed=seed))
    e._ensure_encounter("pc")
    s.positions["pc"] = (2, 10)
    s.positions["c1"] = (2 + gap, 10)
    s.resync_zones()
    s.turn = next(i for i, (r, _) in enumerate(s.initiative) if r == "pc")
    return s, e, pc


def _play(e, raw: list[dict]):
    """Run the list, answering every popup with a middling face; (outcomes, popups)."""
    res = e.run(e.validate(raw))
    popups = []
    while res.status != "complete":
        popups.append(dict(res.awaiting))
        res = e.resume(face=min(11, int(res.awaiting["max"])))
    return res.outcomes, popups


def _blow(**params) -> dict:
    return {"op": "attack", "actor": "pc", "target": "c1", "because": "she stabs him",
            "params": params}


# --- the engine: named, drawn, swung -------------------------------------------------------

def test_a_carried_weapon_named_is_drawn_before_it_is_swung():
    """The dagger named: drawn through `wear` in front of the blow, the popup and the tell
    name the dagger, and it is the weapon in hand after. Before: "Attack with dagger" off
    the belt, the rapier still `equipped`, and no draw at all."""
    s, e, pc = _fight()
    outs, popups = _play(e, [_blow(weapon="dagger")])
    assert [o.op for o in outs][:2] == ["wear", "attack"], [o.tell for o in outs]
    assert outs[0].tell.startswith("Kesst Vayr draws the dagger")
    assert popups and popups[0]["label"] == "Attack with dagger"
    assert "dagger" in outs[1].tell and "rapier" not in outs[1].tell, outs[1].tell
    assert pc.equipped == "dagger"


def test_the_weapon_in_hand_is_not_drawn_again():
    s, e, pc = _fight()
    outs, _ = _play(e, [_blow(weapon="rapier")])
    assert [o.op for o in outs] == ["attack"]


def test_at_base_attack_zero_the_draw_is_the_move_action():
    """Kesst is a 1st-level rogue (BAB +0): the draw spends her move, so a thug two
    squares off cannot be closed on after it, and the blow is refused for reach — where
    without the draw the closing step would have walked her in (`_close_before`)."""
    s, e, pc = _fight(gap=3)
    outs, popups = _play(e, [_blow(weapon="dagger")])
    assert s.move_spent.get("pc") == s.round
    assert [o.op for o in outs] == ["wear", "attack"], [o.tell for o in outs]
    assert not popups, "nothing should be rolled out of reach"
    assert s.positions["pc"] == (2, 10), "no step after a draw that took the move"


def test_with_base_attack_one_the_draw_rides_the_closing_step():
    """BAB +1 (a 2nd-level rogue): "you may draw a weapon as a free action combined with
    a regular move" — the draw spends nothing, and the step in to strike still comes."""
    s, e, pc = _fight(gap=3, level=2)
    assert pc.bab >= 1
    outs, popups = _play(e, [_blow(weapon="dagger")])
    assert [o.op for o in outs][:3] == ["wear", "move", "attack"], [o.tell for o in outs]
    assert popups and popups[0]["label"] == "Attack with dagger"


def test_after_a_draw_a_full_attack_is_one_blow():
    """An 8th-level rogue (BAB +6) has two iteratives; drawing first leaves the standard
    action, one attack — the d20 is asked for once, not twice."""
    s, e, pc = _fight(level=8)
    assert pc.bab >= 6
    outs, popups = _play(e, [_blow(weapon="dagger", full_attack=True)])
    attacks = [p for p in popups if p["label"] == "Attack with dagger"]
    assert len(attacks) == 1, [p["label"] for p in popups]


def test_quick_draw_makes_the_draw_free():
    """With Quick Draw the draw costs nothing: the move is unspent and the full attack
    keeps both swings."""
    s, e, pc = _fight(level=8)
    pc.feats = list(pc.feats) + ["quick draw"]
    assert pc.has_state("action.draw.free"), "Quick Draw's document grants the tag"
    outs, popups = _play(e, [_blow(weapon="dagger", full_attack=True)])
    assert s.move_spent.get("pc") != s.round
    assert len([p for p in popups if p["label"] == "Attack with dagger"]) == 2


def test_a_draw_after_a_move_at_base_attack_zero_leaves_no_blow():
    """The draw as the SECOND move action: Kesst walked this round, so drawing takes the
    rest of the turn, and the blow is refused in words, nothing rolled."""
    s, e, pc = _fight()
    s.move_spent["pc"] = s.round
    outs, popups = _play(e, [_blow(weapon="dagger")])
    assert not popups
    assert outs[-1].op == "attack" and "no blow is left" in outs[-1].tell, outs[-1].tell


def test_a_coup_de_grace_after_a_draw_in_a_fight_is_refused():
    """A coup de grâce is a full-round action (CRB p.197); drawing first spent a move
    action of that round, so the stroke is refused in words, nothing rolled."""
    s, e, pc = _fight()
    thug = s.actors["c1"]
    thug.nonlethal = thug.hp + 3
    thug.apply_hp_state()
    outs, popups = _play(e, [_blow(weapon="dagger", coup_de_grace=True)])
    assert [o.op for o in outs][:2] == ["wear", "attack"], [o.tell for o in outs]
    assert "takes the whole round" in outs[1].tell, outs[1].tell
    assert not popups


def test_a_refused_draw_never_swings_the_weapon_off_the_belt(monkeypatch):
    """When the draw is refused (here, a hand that cannot take it), the named weapon is
    still not in hand — the blow is refused in words, never swung with the dagger from the
    belt nor with the rapier in its place."""
    s, e, pc = _fight()
    monkeypatch.setattr(Engine, "_hands_clash", lambda self, actor, **kw:
                        "The goo holds the hand fast." if kw.get("weapon_key") else "")
    outs, popups = _play(e, [_blow(weapon="dagger")])
    assert not popups
    assert pc.equipped == "rapier"
    assert "not in Kesst Vayr's hand" in outs[-1].tell, [o.tell for o in outs]
    assert not any(o.op == "attack" and o.rolls for o in outs)


def test_out_of_a_fight_the_draw_costs_nothing_and_opens_the_fight_with_the_dagger():
    """Out of a fight there is no turn to spend: the draw happens, the blow opens the
    battle (the gate defers the swing), and the blow it carries is the dagger's."""
    s = Scene(location_id="5bbd0c40345f")
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="the thug"))
    e = Engine(s, Dice(seed=3))
    res = e.run(e.validate([_blow(weapon="dagger")]))
    ops = [o.op for o in res.outcomes]
    assert ops[:2] == ["wear", "attack"], [o.tell for o in res.outcomes]
    joined = next(x for x in res.outcomes[1].effects if x.get("kind") == "battle_joined")
    assert joined["params"]["weapon"] == "dagger"
    assert pc.equipped == "dagger"


# --- the reading: the words name it ------------------------------------------------------

def _scene():
    s = Scene(location_id="5bbd0c40345f")
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    thug = s.add(instantiate("thug", scene=s, name="the thug"))
    return s, pc, thug


def _rows(s, actions):
    frame = {"question": False, "claims": [], "actions": actions}
    rows = acts_to_ops.table(frame, s)
    acts_to_ops.victims(rows, frame, s)
    notes = acts_to_ops.weapons(rows, frame, s)
    return rows, notes


def test_the_attacks_object_is_the_weapon():
    """The live reading of "I draw my dagger and stab him" (gemma, 2026-10-16, 2 of 2)."""
    s, pc, thug = _scene()
    rows, _ = _rows(s, [{"act": "attack", "object": "my dagger", "target": "the thug"}])
    assert rows[0].weapon == "dagger"
    assert rows[0].intents[0]["params"]["weapon"] == "dagger"


def test_a_use_just_before_the_blow_names_its_weapon():
    """The live reading of "I pull out my dagger and slash at the smith": `use` then a
    bare `attack` (2 of 2)."""
    s, pc, thug = _scene()
    rows, _ = _rows(s, [{"act": "use", "object": "my dagger"},
                        {"act": "attack", "target": "the thug"}])
    assert rows[1].weapon == "dagger"


def test_a_weapon_not_carried_is_the_turns_refusal():
    s, pc, thug = _scene()
    rows, _ = _rows(s, [{"act": "attack", "object": "my greataxe", "target": "the thug"}])
    assert acts_to_ops.refusal(rows) == "Kesst Vayr is not carrying a greataxe."
    # And no blow of the player's is struck with something else in its place.
    plan = [{"op": "attack", "actor": "pc", "target": thug.ref, "params": {}}]
    assert acts_to_ops.strike_with(plan, rows, s) == []


def test_the_players_own_dagger_even_when_the_thug_carries_one():
    """The bestiary thug carries a dagger too; "my dagger" is still hers (the first cut
    of this check read it as his, 2026-10-16)."""
    s, pc, thug = _scene()
    assert "dagger" in thug.weapons
    rows, _ = _rows(s, [{"act": "attack", "object": "my dagger", "target": "the thug"}])
    assert rows[0].weapon == "dagger"


def test_a_weapon_the_one_struck_holds_is_theirs_not_the_players():
    """"I strike his club" — the thug's club, and she has none — is never refused as a
    club she does not carry."""
    s, pc, thug = _scene()
    thug.weapons, thug.equipped = ["club"], "club"
    rows, _ = _rows(s, [{"act": "attack", "object": "his club", "target": "the thug"}])
    assert rows[0].weapon == "" and not rows[0].missing


def test_a_weapon_picked_up_earlier_in_the_sentence_is_not_refused():
    s, pc, thug = _scene()
    rows, _ = _rows(s, [{"act": "take", "object": "the handaxe"},
                        {"act": "attack", "object": "the handaxe", "target": "the thug"}])
    assert not rows[1].missing


def test_words_that_name_no_weapon_are_left_to_the_plan():
    s, pc, thug = _scene()
    rows, _ = _rows(s, [{"act": "attack", "object": "my blade", "target": "the thug"}])
    assert rows[0].weapon == "" and not rows[0].missing


def test_strike_with_overrules_the_plans_weapon_and_leaves_a_manoeuvre_alone():
    s, pc, thug = _scene()
    rows, _ = _rows(s, [{"act": "attack", "object": "my dagger", "target": "the thug"}])
    plan = [{"op": "attack", "actor": "pc", "target": thug.ref, "params": {}},
            {"op": "attack", "actor": "pc", "target": thug.ref,
             "params": {"weapon": "rapier"}},
            {"op": "attack", "actor": "pc", "target": thug.ref,
             "params": {"manoeuvre": "disarm", "item": "club"}}]
    out = acts_to_ops.strike_with(plan, rows, s)
    assert [r["params"].get("weapon") for r in out] == ["dagger", "dagger", None]


def test_a_blow_declared_again_is_not_refused_as_a_repeat():
    """Live, 2026-10-16, on the scratch save: "I draw my dagger and stab him" was refused
    for reach (the draw took her move); the next line, "I draw my rapier and stab him",
    planned the same `attack c1` with the same reason, the repeat guard refused it twice,
    and the turn degraded to narration. A blow the reading declares this turn is the player
    asking again, as a sale asked again already is (`_does_what_was_declared`)."""
    from gm import judgement
    from rules.intents import parse_all

    s, pc, thug = _scene()
    first = parse_all([{"op": "attack", "actor": "pc", "target": thug.ref,
                        "because": "the player attacks the thug"}])
    line = "I draw my rapier and stab him"
    interpret.remember(line, {"question": False, "claims": [], "actions": [
        {"act": "attack", "object": "my rapier", "target": "him"}]})
    again = parse_all([{"op": "attack", "actor": "pc", "target": thug.ref,
                        "because": "the player attacks the thug"}])
    v = judgement.review(line, again, s, previous=judgement._signature(first))
    assert not any(f.kind == "repeats-the-last-turn" for f in v.objections), v.objections


# --- the whole turn ---------------------------------------------------------------------

class _Reply:
    def __init__(self, text):
        self.text, self.seconds, self.model = text, 0.0, "fake"

    def json(self):
        return json.loads(self.text)


def test_the_measured_line_through_the_turn_stabs_with_the_dagger(monkeypatch):
    """The 2026-10-16 line end to end: the reading the live reader gave, a plan that
    names no weapon (what the planner wrote on master), and the turn that resolves — the
    dagger drawn, then the dagger's blow. Before: the rapier's."""
    s = Scene(location_id=VORMOOR.id)
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    e = Engine(s, Dice(seed=3), world=WORLD)
    e.place_party()
    thug = s.add(instantiate("thug", scene=s, name="the thug"))
    e._ensure_encounter("pc")
    s.positions["pc"] = (2, 10)
    s.positions[thug.ref] = (3, 10)
    s.resync_zones()
    s.turn = next(i for i, (r, _) in enumerate(s.initiative) if r == "pc")
    line = "I draw my dagger and stab the thug"
    interpret.remember(line, {"question": False, "claims": [], "actions": [
        {"act": "attack", "object": "my dagger", "target": "the thug",
         "span": "draw my dagger and stab the thug"}]})
    monkeypatch.setattr(agent_mod.client, "chat", lambda *a, **k: _Reply(json.dumps({
        "narration": "", "intents": [{"op": "attack", "actor": "pc", "target": thug.ref,
                                      "because": "she stabs him", "params": {}}]})))
    gm = agent_mod.GMAgent(WORLD, e)
    plan = gm.plan_turn(line, history=[])
    blows = [i for i in plan.intents if i.op == "attack"]
    assert blows and blows[0].params.get("weapon") == "dagger", plan.intents
    res = e.run(plan.intents)
    while res.status != "complete":
        assert "dagger" in res.awaiting["label"].lower() or "sneak" in \
            res.awaiting["label"].lower(), res.awaiting["label"]
        res = e.resume(face=min(11, int(res.awaiting["max"])))
    told = " ".join(o.tell for o in res.outcomes)
    assert "draws the dagger" in told and "rapier" not in told, told

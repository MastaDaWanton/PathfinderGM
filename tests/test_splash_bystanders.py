"""A bystander a thrown flask hurts reacts by who they are (owner's ruling, 2026-10-06).

"if the bystander is a combatant they might fight the thrower but if they are a civilian
assuming they did not die they should run away."

Measured by alchemy lane C before it: a market master caught by a flask's splash swung at
the struck creature, not the thrower. The splash moved nobody's attitude and drew nobody
into the fight (the sword and spell doors both call `attitude.harmed`; the flask did not),
so whatever the bystander did next was the model's guess. RimWorld's caravans are the
split ruled here: guards defend, the trader leaves (rimworldwiki.com/wiki/Trade).
"""
from __future__ import annotations

from rules import attitude as attitude_mod
from rules import residency
from rules.bestiary import instantiate
from rules.crafting import Stock
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import from_dict, load_pc

FIRE = [{"type": "damage", "dice": "1d6", "damage_type": "fire", "route": "struck"},
        {"type": "burning", "dice": "1d6", "rounds": 1, "dc": 15, "smother_bonus": 2,
         "route": "struck"}]


def _market(*bystanders, seed=7):
    """Kesst, a thug four squares east, and each bystander (template, name) beside the
    thug — off the fight's sides, as a person in the room is until they join it."""
    s = Scene(location_id="5bbd0c40345f")
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    s.add(instantiate("thug", scene=s, name="the thug"))
    made = [s.add(instantiate(t, scene=s, name=n)) for t, n in bystanders]
    pc.stock["flask#1"] = Stock(base="Alchemist's Fire", count=3,
                                specs=[dict(x) for x in FIRE])
    e = Engine(s, Dice(seed=seed))
    e._ensure_encounter("pc", "c1")
    s.positions["pc"] = (2, 10)
    s.positions["c1"] = (6, 10)
    for i, a in enumerate(made):
        s.positions[a.ref] = [(6, 11), (7, 10), (5, 9)][i]
    s.resync_zones()
    return s, e, made


def _throw(e):
    res = e.run(e.validate([{"op": "use_item", "actor": "pc", "because": "she throws it",
                             "params": {"item": "flask#1", "how": "throw", "to": "c1"}}]))
    if res.status != "complete":
        res = e.resume(face=19)
    return res


def _told(res) -> str:
    return " ".join(o.tell for o in res.outcomes)


def test_a_splashed_guard_turns_on_the_thrower_and_a_splashed_shopkeeper_runs():
    """The owner's two cases on one throw: the watchman (the law's `role.guard`) comes
    into the fight against the player, hostile; the guildhand (a commoner) survives the
    1 point of splash and leaves the scene for home — through `Scene.move`, so he is
    still in the campaign, not destroyed."""
    s, e, (guard, keeper) = _market(("watchman", "the watchman"),
                                    ("guildhand", "the stallkeeper"))
    sides_before = {k: list(v) for k, v in s.sides.items()}
    assert not any(guard.ref in v or keeper.ref in v for v in sides_before.values())
    res = _throw(e)
    told = _told(res)
    pc_side = next(k for k, v in s.sides.items() if "pc" in v)
    against = [k for k in s.sides if k != pc_side]
    assert any(guard.ref in s.sides[k] for k in against), (s.sides, told)
    assert attitude_mod.of(guard) == "hostile"
    assert "the watchman, caught in the splash, turns on" in told.lower(), told
    # The shopkeeper ran: out of the room and the order, alive, at home off stage.
    assert keeper.ref not in s.actors
    assert keeper.ref in s.people and keeper.hp > 0
    assert residency.is_offstage(keeper.at), keeper.at
    assert keeper.ref not in [r for r, _ in s.initiative]
    assert "runs from the fight" in told, told
    kinds = {fx.get("kind") for o in res.outcomes for fx in o.effects}
    assert {"joins_fight", "flees"} <= kinds


def test_who_fights_back_is_read_off_the_creature_never_its_name():
    """Combatant or civilian from the data: the law's tag, a fighting template, a martial
    stat block (every Hit Die a d10 — the printed Guard's 3d10), or somebody hostile with
    a weapon. A Merchant's 4d8 and a guildhand's commoner block run. A man NAMED "the guard"
    on a commoner's block runs too: the name is not the reading."""
    s, e, made = _market(("guard", "the town guard"), ("merchant", "the merchant"),
                         ("guildhand", "the guard"))
    town_guard, merchant, named_guard = made
    assert e.fights_back(town_guard)
    assert not e.fights_back(merchant)
    assert not e.fights_back(named_guard)
    assert e.fights_back(s.actors["c1"])                 # the thug template
    e.settle_attitude(merchant, "hostile")
    assert e.fights_back(merchant)                      # hostile, and armed


def test_the_struck_creature_is_harmed_like_a_sword_victim():
    """The flask's own target had no `attitude.harmed` either: an indifferent man the
    player set alight stayed indifferent. Now the throw is the sword door's rule."""
    s = Scene(location_id="5bbd0c40345f")
    pc = s.add(load_pc("fixtures/pc-kesst.json"))
    man = s.add(from_dict({"name": "the drover", "kind": "npc", "hp": 30, "hp_max": 30,
                           "abilities": {k: 10 for k in ("str", "dex", "con", "int",
                                                         "wis", "cha")}}, ref="c1"))
    pc.stock["flask#1"] = Stock(base="Alchemist's Fire", count=3,
                                specs=[dict(x) for x in FIRE])
    e = Engine(s, Dice(seed=7))
    s.positions["pc"] = (2, 10)
    s.positions["c1"] = (4, 10)
    assert attitude_mod.of(man) != "hostile"
    _throw(e)
    assert man.hp < man.hp_max
    assert attitude_mod.of(man) == "hostile"


def test_a_bystander_already_in_the_fight_keeps_its_side_and_a_companion_never_runs():
    """Only a bystander reacts: the second thug on the thug's side stays on it (it does
    not "turn on" anybody twice), and a companion caught in the splash is the party's —
    its regard drops (harm's rule) and it neither flees nor changes sides."""
    from rules import states
    from rules.activeeffect import ActiveEffect

    s, e, (other, friend) = _market(("thug", "the other thug"), ("guildhand", "Bob"))
    e.join_fight(other.ref)
    friend.apply_effect(ActiveEffect(name="travels with you", kind="situation",
                                     key="company", source="company:t",
                                     duration="until-dismissed",
                                     tags=(states.TRAVELS_WITH_YOU,)))
    side_of_other = next(k for k, v in s.sides.items() if other.ref in v)
    res = _throw(e)
    assert other.ref in s.sides[side_of_other]
    assert friend.ref in s.actors, _told(res)
    assert "Bob, caught in the splash" not in _told(res)

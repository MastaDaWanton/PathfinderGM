"""The attack-shape combat feats and extra attacks (implementation lane D, 2026-11-22;
docs/implementation-audit-2026-11-22.md §5 "Lane D").

Measured on impl/base 16bd4daf before this lane: Combat Expertise, Deadly Aim, Piranha
Strike, Vital Strike, Cleave, Rapid Shot and a flurry were unknown params to the attack op
(refused at parse, "unknown param"), so a character holding the feat could not use it at
all; no feat document existed for any of them, nor for Improved Critical, Critical Focus,
Mobility or the Two-Weapon Fighting chain (the sheet called them "not computed"); the app
had no off hand (`Actor.shield_bash`: "no second swing is offered"); a monk's flurry was on
the monk's `_not_yet` list. Each test quotes the rule and drives the engine or the sheet.
"""
from __future__ import annotations

import pytest

from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.intents import IntentError
from rules.sheet import from_dict


def _tot(mods) -> int:
    return sum(m.value for m in mods)


def _pc(level=8, feats=(), weapons=("longsword",), cls="fighter", **extra):
    data = {"name": "Brakka", "kind": "pc", "class": cls, "level": level,
            "abilities": {"str": 16, "dex": 18, "con": 12, "int": 14, "wis": 14, "cha": 10},
            "hp": 80, "weapons": list(weapons), "equipped": weapons[0], "feats": list(feats)}
    data.update(extra)
    return from_dict(data)


def _fight(actor, foes=1, seed=4):
    """The actor beside `foes` thugs on a board: the first east of them, the second
    south-east of the actor and beside the first, the third south of the actor and
    beside the second — a chain a Great Cleave can follow."""
    s = Scene(location_id="5bbd0c40345f")
    a = s.add(actor)
    a.hp = a.hp_max = 500
    them = []
    for i in range(foes):
        t = s.add(instantiate("thug", scene=s, name=f"thug {i + 1}"))
        t.hp = t.hp_max = 500
        them.append(t)
    e = Engine(s, Dice(seed=seed))
    e._ensure_encounter(a.ref, them[0].ref)
    s.positions[a.ref] = (6, 10)
    for i, t in enumerate(them):
        s.positions[t.ref] = [(7, 10), (7, 11), (6, 11)][i]
    s.resync_zones()
    return s, e, a, them


def _run(e, raw):
    for r in raw:
        r.setdefault("visibility", "hidden")
        r.setdefault("because", "test")
    return e.run(e.validate(raw, origin="author:test"))


# --- declared options: Combat Expertise, Deadly Aim, Piranha Strike ------------------------

def test_combat_expertise_trades_attack_for_dodge_until_the_next_turn():
    """CRB: "-1 penalty on melee attack rolls and combat maneuver checks to gain a +1
    dodge bonus to your Armor Class. When your base attack bonus reaches +4, and every +4
    thereafter, the penalty increases by -1 and the dodge bonus increases by +1 ... The
    effects of this feat last until your next turn." At BAB +8 that is -3/+3. Before: the
    param was refused at parse, and the AC never moved."""
    s, e, a, (thug,) = _fight(_pc(feats=["Combat Expertise"]))
    ac, atk = a.ac(), _tot(a.attack_modifiers())
    res = _run(e, [{"op": "attack", "actor": a.ref, "target": thug.ref,
                    "params": {"combat_expertise": True}}])
    swing = res.outcomes[0]
    assert ("Combat Expertise", -3) in [(m.source, m.value) for m in swing.rolls[0].modifiers]
    assert "Combat Expertise" in swing.tell
    assert a.ac() == ac + 3 and _tot(a.attack_modifiers()) == atk - 3
    assert _tot(a.cmb_modifiers()) == _tot(_pc(feats=["Combat Expertise"]).cmb_modifiers()) - 3
    # Law 2: the stance is an effect; its end takes the numbers with it.
    a.tick_effects()
    assert a.ac() == ac and _tot(a.attack_modifiers()) == atk


def test_combat_expertise_is_refused_with_a_ranged_weapon_and_without_the_feat():
    """"You can only choose to use this feat when you declare that you are making an
    attack or a full-attack action with a melee weapon." A stance laid by a bow shot would
    be +3 AC for nothing."""
    s, e, a, (thug,) = _fight(_pc(feats=["Combat Expertise"], weapons=("longbow",)))
    with pytest.raises(IntentError, match="melee weapon"):
        e.validate([{"op": "attack", "actor": a.ref, "target": thug.ref,
                     "params": {"combat_expertise": True}}], origin="author:test")
    s, e, a, (thug,) = _fight(_pc(feats=[]))
    with pytest.raises(IntentError, match="does not have Combat Expertise"):
        e.validate([{"op": "attack", "actor": a.ref, "target": thug.ref,
                     "params": {"combat_expertise": True}}], origin="author:test")


def test_deadly_aim_is_power_attack_for_ranged_weapons_only():
    """CRB: "-1 penalty on all ranged attack rolls to gain a +2 bonus on all ranged damage
    rolls", scaling every +4 base attack. BAB +8: -3/+6, and nothing on a longsword."""
    a = _pc(feats=["Deadly Aim"], weapons=("longbow", "longsword"))
    plain = _tot(a.attack_modifiers("longbow"))
    assert _tot(a.attack_modifiers("longbow", choices=("deadly_aim",))) == plain - 3
    assert _tot(a.damage_modifiers("longbow", choices=("deadly_aim",))) \
        == _tot(a.damage_modifiers("longbow")) + 6
    assert _tot(a.attack_modifiers("longsword", choices=("deadly_aim",))) \
        == _tot(a.attack_modifiers("longsword"))


def test_piranha_strike_is_a_light_weapon_and_never_with_power_attack():
    """CRB (Piranha Strike): "When wielding a light weapon ... -1 penalty on all melee
    attack rolls and combat maneuver checks to gain a +2 bonus on all melee damage rolls
    ... This feat cannot be used in conjunction with the Power Attack feat." """
    a = _pc(feats=["Weapon Finesse", "Piranha Strike", "Power Attack"],
            weapons=("shortsword", "longsword"))
    assert _tot(a.damage_modifiers("shortsword", choices=("piranha_strike",))) \
        == _tot(a.damage_modifiers("shortsword")) + 6
    s, e, a, (thug,) = _fight(a)
    with pytest.raises(IntentError, match="Power Attack"):
        e.validate([{"op": "attack", "actor": a.ref, "target": thug.ref,
                     "params": {"piranha_strike": True, "power_attack": True}}],
                   origin="author:test")
    with pytest.raises(IntentError, match="light melee weapon"):
        e.validate([{"op": "attack", "actor": a.ref, "target": thug.ref,
                     "params": {"weapon": "longsword", "piranha_strike": True}}],
                   origin="author:test")


# --- Vital Strike -----------------------------------------------------------------------

def test_vital_strike_rolls_the_weapon_dice_again_and_never_multiplies_them():
    """CRB: "Roll the weapon's damage dice for the attack twice ... These extra weapon
    damage dice are not multiplied on a critical hit, but are added to the total."
    Improved: three times. So a longsword is 3d8 on a hit, and 1d8x2 + 2d8 = 4d8 on a
    critical. The player rolls the dice the popup names."""
    s, e, a, (thug,) = _fight(_pc(level=12, feats=["Vital Strike", "Improved Vital Strike"]))
    res = e.run(e.validate([{"op": "attack", "actor": a.ref, "target": thug.ref,
                             "visibility": "player", "because": "test",
                             "params": {"vital_strike": True}}], origin="author:test"))
    assert res.awaiting["die"] == "1d20"
    res = e.resume(15)                                    # a hit, no threat
    assert res.awaiting["die"] == "3d8", res.awaiting
    res = e.resume(12)
    assert "Vital Strike" in res.outcomes[0].tell
    # The critical: crit dice x2 plus the two extra, never x2 of all three.
    s, e, a, (thug,) = _fight(_pc(level=12, feats=["Vital Strike", "Improved Vital Strike"]))
    res = e.run(e.validate([{"op": "attack", "actor": a.ref, "target": thug.ref,
                             "visibility": "player", "because": "test",
                             "params": {"vital_strike": True}}], origin="author:test"))
    res = e.resume(19)                                    # longsword threatens 19-20
    res = e.resume(18)                                    # confirmed
    assert res.awaiting["die"] == "4d8", res.awaiting


def test_vital_strike_is_the_attack_action_not_a_full_attack():
    """"When you use the attack action": a full attack carrying it is refused."""
    s, e, a, (thug,) = _fight(_pc(level=12, feats=["Vital Strike"]))
    with pytest.raises(IntentError, match="attack action"):
        e.validate([{"op": "attack", "actor": a.ref, "target": thug.ref,
                     "params": {"vital_strike": True, "full_attack": True}}],
                   origin="author:test")


# --- Cleave and Great Cleave --------------------------------------------------------------

def _cleave(feats, seed):
    return _fight(_pc(level=6, feats=["Power Attack", *feats]), foes=3, seed=seed)


def test_cleave_carries_one_blow_on_to_a_foe_beside_the_first_and_drops_the_guard():
    """CRB: "If you hit ... can make an additional attack ... against a foe that is
    adjacent to the first and also within reach. You can only make one additional attack
    per round with this feat ... -2 penalty to your Armor Class until your next turn."
    Seed 4 hits the first thug and misses the second."""
    s, e, a, thugs = _cleave(["Cleave"], seed=4)
    ac = a.ac()
    res = _run(e, [{"op": "attack", "actor": a.ref, "target": thugs[0].ref,
                    "params": {"cleave": True}}])
    blows = [o for o in res.outcomes if o.op == "attack"]
    assert [o.verdict for o in blows] == ["hit", "miss"]
    assert "Cleave" in blows[0].tell and blows[1].intent_id.endswith("cleave1")
    assert a.ac() == ac - 2
    a.tick_effects()
    assert a.ac() == ac


def test_plain_cleave_stops_after_one_and_great_cleave_goes_on_while_it_hits():
    """Great Cleave: "If you hit, you can continue to make attacks against foes adjacent
    to the previous foe ... You cannot attack an individual foe more than once." With
    every swing landing, Cleave makes two blows and Great Cleave three (one per thug)."""
    def blows(feats):
        for seed in range(1, 200):
            s, e, a, thugs = _cleave(feats, seed)
            for t in thugs:
                t.armour, t.flat_ac = "none", 1       # every swing hits
            res = _run(e, [{"op": "attack", "actor": a.ref, "target": thugs[0].ref,
                            "params": {"cleave": True}}])
            got = [o for o in res.outcomes if o.op == "attack"]
            if all(o.verdict == "hit" for o in got):
                return got
        raise AssertionError("no seed hit every swing")

    assert len(blows(["Cleave"])) == 2
    great = blows(["Cleave", "Great Cleave"])
    assert len(great) == 3
    assert len({o.effects[0]["ref"] for o in great if o.effects}) == 3   # each foe once


def test_cleave_is_refused_on_a_full_attack():
    s, e, a, thugs = _cleave(["Cleave"], seed=4)
    with pytest.raises(IntentError, match="attack action"):
        e.validate([{"op": "attack", "actor": a.ref, "target": thugs[0].ref,
                     "params": {"cleave": True, "full_attack": True}}], origin="author:test")


# --- Rapid Shot and Manyshot ----------------------------------------------------------------

def test_rapid_shot_adds_a_shot_at_the_highest_bonus_and_takes_two_off_every_shot():
    """CRB: "When making a full-attack action with a ranged weapon, you can fire one
    additional time this round at your highest bonus. All of your attack rolls take a -2
    penalty." BAB +8: +8/+3 becomes +8/+3/+8, each -2."""
    a = _pc(feats=["Point-Blank Shot", "Rapid Shot"], weapons=("longbow",))
    assert a.attack_plan("longbow", True) == [("longbow", 0), ("longbow", 1)]
    assert a.attack_plan("longbow", True, ("rapid_shot",)) \
        == [("longbow", 0), ("longbow", 1), ("longbow", 0)]
    assert _tot(a.attack_modifiers("longbow", choices=("rapid_shot",))) \
        == _tot(a.attack_modifiers("longbow")) - 2
    s, e, a, (thug,) = _fight(a)
    with pytest.raises(IntentError, match="full attack"):
        e.validate([{"op": "attack", "actor": a.ref, "target": thug.ref,
                     "params": {"rapid_shot": True}}], origin="author:test")


def test_manyshot_lands_a_second_arrow_with_the_first_and_no_second_critical():
    """CRB: "your first attack fires two arrows. If the attack hits, both arrows hit.
    Apply precision-based damage (such as sneak attack) and critical hit damage only once
    for this attack." The second arrow is damage with no roll to hit, and a second arrow
    leaves the quiver."""
    for seed in range(1, 60):
        s, e, a, (thug,) = _fight(_pc(feats=["Point-Blank Shot", "Rapid Shot", "Manyshot"],
                                      weapons=("longbow",)), seed=seed)
        a.goods["arrows"] = 40
        res = _run(e, [{"op": "attack", "actor": a.ref, "target": thug.ref,
                        "params": {"full_attack": True}}])
        swing = res.outcomes[0]
        if "Manyshot" in swing.tell:
            break
    else:
        raise AssertionError("no seed hit with the first arrow")
    labels = [r.label for r in swing.rolls]
    # first shot: attack, (confirm?), damage; second arrow: damage only; then the -5 shot.
    assert labels[0].startswith("Attack") and labels[1].startswith("Damage") \
        and labels[2].startswith("Damage"), labels
    assert "CRITICAL" not in labels[2]
    assert a.goods.get("arrows", 0) <= 40 - 3      # three shots loosed, two at once


# --- Improved Critical, Critical Focus, Mobility -------------------------------------------

def test_improved_critical_doubles_the_threat_once_and_only_on_its_weapon():
    """CRB: "When using the weapon you selected, your threat range is doubled", and keen
    "doesn't stack with any other effect that expands the threat range of a weapon (such as
    the keen edge spell or the Improved Critical feat)". Longsword 19-20 -> 17-20."""
    a = _pc(level=9, feats=["Improved Critical (longsword)"], weapons=("longsword", "rapier"))
    assert a.weapon("longsword")["crit_range"] == 17
    assert a.weapon("rapier")["crit_range"] == 18
    assert _pc(level=9, weapons=("longsword",)).weapon("longsword")["crit_range"] == 19


def test_critical_focus_adds_four_to_the_confirmation_roll_only():
    """CRB: "+4 circumstance bonus on attack rolls made to confirm critical hits." The
    confirmation roll the player sees carries it; the attack roll before it does not."""
    s, e, a, (thug,) = _fight(_pc(level=9, feats=["Critical Focus"]))
    res = e.run(e.validate([{"op": "attack", "actor": a.ref, "target": thug.ref,
                             "visibility": "player", "because": "test", "params": {}}],
                           origin="author:test"))
    assert not any(b["source"] == "Critical Focus" for b in res.awaiting["breakdown"])
    res = e.resume(19)
    assert res.awaiting["label"].startswith("Confirm critical")
    assert any(b["source"] == "Critical Focus" and b["value"] == 4
               for b in res.awaiting["breakdown"])


def test_mobility_is_four_dodge_against_an_attack_of_opportunity_for_moving():
    """CRB: "+4 dodge bonus to Armor Class against attacks of opportunity caused when you
    move out of or within a threatened area", and lost with Dex. The swing a move draws is
    stamped `provoked_by: movement` by the engine (`_swings_at`)."""
    a = _pc(feats=["Dodge", "Mobility"])
    assert a.ac(provoked_by="movement") == a.ac() + 4
    s, e, a, (thug,) = _fight(a)
    calm = a.ac(flat_footed=True)
    s.acted.update({a.ref, thug.ref})            # past the surprise: the thug may react
    res = _run(e, [{"op": "move", "actor": a.ref, "params": {"square": [4, 10]}}])
    aoo = [o for o in res.outcomes if o.op == "attack"]
    assert aoo, [o.tell for o in res.outcomes]
    assert aoo[0].dc["value"] in (a.ac() + 4, calm + 4)      # 15 + 4: AC 19, measured


# --- Two-Weapon Fighting ----------------------------------------------------------------------

def test_two_weapon_penalties_are_the_tables_and_the_feat_relieves_them():
    """CRB Table 8-7: -6/-10 normally, -4/-8 with a light off-hand weapon; Two-Weapon
    Fighting lessens the primary's by 2 and the off hand's by 6 (-2/-2 light). The off
    hand adds half Strength; Double Slice makes it whole."""
    plain = _pc(weapons=("longsword", "shortsword", "handaxe"))
    base = _tot(plain.attack_modifiers("longsword"))
    assert _tot(plain.attack_modifiers("longsword", hand="primary", off_light=True)) == base - 4
    assert _tot(plain.attack_modifiers("shortsword", hand="off", off_light=True)) == base - 8
    twf = _pc(feats=["Two-Weapon Fighting"], weapons=("longsword", "shortsword"))
    assert _tot(twf.attack_modifiers("longsword", hand="primary", off_light=True)) == base - 2
    assert _tot(twf.attack_modifiers("shortsword", hand="off", off_light=True)) == base - 2
    assert _tot(twf.attack_modifiers("longsword", hand="primary", off_light=False)) == base - 4
    assert _tot(twf.damage_modifiers("shortsword", hand="off")) == 1           # Str +3 halved
    ds = _pc(feats=["Two-Weapon Fighting", "Double Slice"], weapons=("longsword", "shortsword"))
    assert _tot(ds.damage_modifiers("shortsword", hand="off")) == 3


def test_improved_and_greater_add_the_off_hands_minus_five_and_minus_ten():
    """ITWF: "a second attack with it, albeit at a -5 penalty"; GTWF: "a third ... -10"."""
    a = _pc(level=11, feats=["Two-Weapon Fighting", "Improved Two-Weapon Fighting",
                             "Greater Two-Weapon Fighting"], weapons=("longsword", "shortsword"),
            abilities={"str": 16, "dex": 20, "con": 12, "int": 10, "wis": 10, "cha": 10})
    plan = a.attack_plan("longsword", True, (), "shortsword")
    assert [p for p in plan if p[0] == "shortsword"] == [("shortsword", 0), ("shortsword", 1),
                                                         ("shortsword", 2)]


def test_a_two_weapon_full_attack_through_the_engine_rolls_each_hand_its_own():
    """The path the combat bar posts: one full attack naming the off hand. The off-hand
    swing carries the off hand's penalty, named."""
    s, e, a, (thug,) = _fight(_pc(feats=["Two-Weapon Fighting"],
                                  weapons=("longsword", "shortsword")))
    res = _run(e, [{"op": "attack", "actor": a.ref, "target": thug.ref,
                    "params": {"full_attack": True, "off_hand": "shortsword"}}])
    atk = [r for r in res.outcomes[0].rolls if r.label.startswith("Attack")]
    assert [r.label for r in atk] == ["Attack with longsword"] * 2 + ["Attack with short sword"]
    assert any("off hand" in m.source for m in atk[2].modifiers)
    assert any("primary hand" in m.source for m in atk[0].modifiers)


def test_a_two_handed_weapon_leaves_no_off_hand():
    s, e, a, (thug,) = _fight(_pc(weapons=("greatsword", "dagger")))
    with pytest.raises(IntentError, match="both hands"):
        e.validate([{"op": "attack", "actor": a.ref, "target": thug.ref,
                     "params": {"full_attack": True, "off_hand": "dagger"}}],
                   origin="author:test")


# --- the monk's flurry and ki ----------------------------------------------------------------

@pytest.mark.parametrize("level,printed", [
    (1, [-1, -1]), (8, [6, 1, 6, 1]), (15, [13, 8, 3, 13, 8, 3])])
def test_a_flurry_is_the_monk_tables_own_column(level, printed):
    """CRB Table: Monk, flurry of blows attack bonus: -1/-1 at 1st, +6/+6/+1/+1 at 8th,
    +13/+13/+8/+8/+3/+3 at 15th — the monk level as base attack, two-weapon fighting's -2
    and its 0/-5/-10 ladder. Before: no flurry existed (the monk's `_not_yet`)."""
    m = _pc(level=level, cls="monk", weapons=("unarmed",))
    assert "flurry" in m.attack_choices()
    got = sorted((_tot(m.attack_modifiers("unarmed", i, choices=("flurry",)))
                  - m.ability_mod("str") for _, i in m.attack_plan("unarmed", True,
                                                                  ("flurry",))), reverse=True)
    assert got == sorted(printed, reverse=True)


def test_a_flurry_is_lost_in_armour_and_refused_with_a_longsword():
    """CRB: "When wearing armor, using a shield, or carrying a medium or heavy load, a monk
    loses ... flurry of blows"; and it is "unarmed strikes or ... a special monk weapon"."""
    m = _pc(level=4, cls="monk", weapons=("unarmed", "longsword"), armour="chain shirt")
    assert "flurry" not in m.attack_choices()
    m = _pc(level=4, cls="monk", weapons=("longsword", "unarmed"))
    s, e, m, (thug,) = _fight(m)
    with pytest.raises(IntentError, match="monk weapons"):
        e.validate([{"op": "attack", "actor": m.ref, "target": thug.ref,
                     "params": {"weapon": "longsword", "full_attack": True, "flurry": True}}],
                   origin="author:test")


def test_ki_buys_one_more_blow_in_a_flurry_and_none_outside_it():
    """CRB Ki Pool: "By spending 1 point from his ki pool, a monk can make one additional
    attack at his highest attack bonus when making a flurry of blows attack." Before: the
    monk's `_not_yet` said there was no flurry to add an attack to."""
    s, e, m, (thug,) = _fight(_pc(level=8, cls="monk", weapons=("unarmed",)))
    _run(e, [{"op": "use_ability", "actor": m.ref, "params": {"ability": "ki extra attack"}}])
    assert len(m.attack_plan("unarmed", True, ("flurry",))) == 5
    assert len(m.attack_plan("unarmed", False)) == 1
    assert len(m.attack_plan("unarmed", True)) == 2


# --- the combat bar offers what the character can do ---------------------------------------

def test_the_combat_bar_offers_each_option_only_to_its_holder():
    """The bar's buttons are `Actor.attack_choices()`: nobody is offered a feat they do
    not hold, and the two-weapon plan is drawn from the engine's own rule."""
    from play.views import _attack_slots

    bare = _attack_slots(_pc(weapons=("longsword",)))
    assert bare["options"] == []
    held = _attack_slots(_pc(feats=["Power Attack", "Vital Strike", "Two-Weapon Fighting"],
                             level=8, weapons=("longsword", "shortsword")))
    assert {o["id"] for o in held["options"]} == {"power_attack", "vital_strike"}
    assert "shortsword" in held["off_hands"]
    twf = held["plans"]["off:shortsword"]
    assert [p["hand"] for p in twf] == ["primary", "primary", "off"]
    assert twf[0]["bonus"] == held["plans"][""][0]["bonus"] - 2


def test_the_validators_refuse_a_malformed_threat_range_and_attack_choice():
    """Detect mechanically: a feat document's `crit_range` that is not a doubling on the
    named weapon, and a class feature's `attack_choice` the attack op does not carry."""
    from rules import classbuilder, classfeatures

    assert classbuilder.validate_feat_document("improved-critical",
                                               {"crit_range": {"multiply": 1}})
    assert classbuilder.validate_feat_document("improved-critical",
                                               {"crit_range": {"multiply": 2}}) == []
    bad = classfeatures.validate("monk", {"flurry-of-blows": {
        "name": "x", "source": "y", "attack_choice": {"id": "flurrry"}}})
    assert any("attack_choice" in p for p in bad)

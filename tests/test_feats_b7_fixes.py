"""Feat loop batch 7, lane fixes: negative energy's one family, Power Attack's stance and
the b6-rules leftovers (content/feats/mechanics/b7-fixes.json)."""
from __future__ import annotations

from rules import states
from rules.bestiary import instantiate
from rules.engine import Scene


# --- 1. negative energy heals: one tag family (owner ruling 2026-11-09) -------------------

def test_inflict_mends_a_deaths_embrace_cleric_and_a_cure_does_not_hurt_her():
    """Owner ruling 2026-11-09: "Inflict spells heal creatures with a negative energy
    affinity: channel.negative.heals, not only type.undead." Measured before b7: a Death's
    Embrace cleric at 3 hp cast inflict light wounds on herself and went DOWN — the cast loop
    asked `type.undead` and Necromantic Affinity's `energy.negative.affinity`, and never the
    channel's tag. Death's Embrace says nothing of cure spells, so a cure still heals her."""
    from tests.test_audit_magic import _cleric, records, run, said, scene_with

    pc = _cleric(level=8)
    pc.domains = ["Death", "War"]
    assert pc.has_state(states.NEGATIVE_HEALS_CHANNEL)
    s, e = scene_with(pc)
    pc.hp = 3
    res = run(e, "cast", spell="inflict-light-wounds", at="pc")
    assert pc.hp > 3, said(res)
    assert records(res, "heal")
    assert "answers to negative energy" in said(res)
    before = pc.hp
    run(e, "cast", spell="cure-light-wounds", at="pc")
    assert pc.hp >= before


def test_the_undead_hold_the_family_by_their_type():
    """One vocabulary: the cast loop asks `energy.negative.heals`, never `type.undead`
    beside a second tag, so the undead must answer it by their type (`states.type_tags`)."""
    z = instantiate("zombie", scene=Scene(location_id="5bbd0c40345f"))
    assert z.has_state(states.NEGATIVE_HEALS)
    assert z.has_state(states.NEGATIVE_HEALS_SPELLS)
    assert not z.has_state(states.NEGATIVE_HEALS_CHANNEL)
    wolf = instantiate("wolf", scene=Scene(location_id="5bbd0c40345f"))
    assert not wolf.has_state(states.NEGATIVE_HEALS)


# --- 2. Power Attack lasts until the next turn --------------------------------------------

def test_power_attack_holds_until_the_next_turn_on_a_later_blow_and_a_manoeuvre():
    """CRB Power Attack: "You must choose to use this feat before making an attack roll,
    and its effects last until your next turn." Measured before b7: the -3/+6 rode only the
    declared swing — a second blow in the round (an attack of opportunity is the same
    path) and a trip carried none of it. Now both do, and the round's end takes it away."""
    from tests.test_feats_b4_moves import _attack, _board, _pc, _rolls

    pc = _pc("fighter", feats=["Power Attack"], equipped="rapier")
    pc.abilities["str"] = 16
    s, e = _board(pc, ("thug", (6, 5)), faces={"Attack with": 15})
    _attack(e, power_attack=True)
    assert pc.has_state("buff.stance.power-attack")
    second = _rolls(_attack(e), "Attack with")
    assert any(str(m.get("source", "")).startswith("Power Attack")
               for m in second[0]["modifiers"]), second
    assert any(m.source.startswith("Power Attack") for m in pc.cmb_modifiers("trip"))
    pc.tick_effects(1)
    assert not pc.has_state("buff.stance.power-attack")
    assert not any(m.source.startswith("Power Attack") for m in pc.cmb_modifiers("trip"))


# --- 4. the b6-rules leftovers --------------------------------------------------------------

def test_cornugon_trip_throws_the_chain_to_trip_at_range_without_falling_back():
    """Cornugon Trip (Cheliax): "You may throw your spiked chain (as if it were a thrown
    weapon with a range increment of 10 feet) and can make trip attacks when throwing it.
    Failing at this attack does not knock you prone." Measured before b7: a spiked chain
    has no range increment, so a trip at a foe 15 feet off was refused out of reach."""
    from tests.test_feats_b4_moves import _attack, _board, _pc

    pc = _pc("fighter", feats=["Exotic Weapon Proficiency (spiked chain)", "Cornugon Trip"],
             equipped="spiked-chain")
    pc.weapons = list(pc.weapons) + ["spiked-chain"]
    assert pc.weapon("spiked-chain").get("range_ft") == 10
    s, e = _board(pc, ("thug", (8, 5)))
    pc.add_buff("combat_mod", "cmb", -60, source="test: always fails by 10")
    res = _attack(e, weapon="spiked-chain", manoeuvre="trip", thrown=True)
    out = res.outcomes[0]
    assert out.status == "resolved", out.tell
    assert not pc.has_state("state.position.prone"), out.tell
    assert "spiked-chain" not in pc.weapons
    plain = _pc("fighter", feats=["Exotic Weapon Proficiency (spiked chain)"],
                equipped="spiked-chain")
    assert not plain.weapon("spiked-chain").get("range_ft")


def test_sorcerous_strike_delivers_the_bloodline_ray_on_an_unarmed_hit():
    """Sorcerous Strike (UC): "If you make a successful unarmed strike against an
    opponent, in addition to dealing your unarmed strike damage, you can spend a swift
    action to deliver the effects of the chosen bloodline power to that opponent."
    Measured before b7: no document and no reader, so a hit fist carried nothing."""
    from tests.test_class_spellcasting import forge
    from tests.test_feats_b4_moves import _attack, _board

    pc = forge("sorcerer", class_choices={"bloodline": {"pick": "elemental",
                                                          "variant": "fire"}})
    pc.feats = list(pc.feats) + ["Improved Unarmed Strike", "Sorcerous Strike (elemental ray)"]
    s, e = _board(pc, ("thug", (6, 5)), faces={"Attack with": 19})
    res = _attack(e, weapon="unarmed")
    uses = [o for o in res.outcomes if o.op == "use_ability"]
    assert uses and uses[0].status == "resolved", [o.tell for o in res.outcomes]
    assert any(x.get("kind") == "damage" for x in uses[0].effects or ()), uses[0].tell
    assert s.swift_spent.get("pc") == s.round


def _blessed(foe, amount=2):
    from rules.activeeffect import ActiveEffect

    foe.apply_effect(ActiveEffect(
        name="bless", kind="buff", key="bless", source="Bless", origin="spell:bless",
        duration="rounds", rounds_left=10, payload={"cast": {"cl": 3, "by": "x"}},
        modifiers=[{"kind": "combat_mod", "target": "attack", "amount": amount,
                    "bonus_type": "morale"}]))


def test_shatterspell_suppresses_a_spell_by_a_narrow_margin_and_dispels_by_ten():
    """Shatterspell (ARG) by Spell Sunder (UC): a sunder check against CMD + 5; "suppresses
    the effect for 1 round, or 2 rounds if she exceeded the CMD by 5 to 9 ... by 10 or
    more, the effect is dispelled." Measured before b7: no document; the feat's line was
    Shatterspell's whole effect. The die shows 10; the CMB is set so the margin is known."""
    from tests.test_feats_b4_moves import _board, _pc, _run

    pc = _pc("fighter", 12, feats=["Shatterspell"])
    s, e = _board(pc, ("thug", (6, 5)), faces={"Kesst Vayr's sunder": 10})
    foe = s.actors["c1"]
    _blessed(foe)
    cmd = sum(m.value for m in foe.cmd_modifiers(False, maneuver="sunder", attacker=pc)) + 5
    cmb = sum(m.value for m in pc.cmb_modifiers("sunder", defender=foe))
    pc.add_buff("combat_mod", "cmb", cmd - cmb - 10 + 2, source="test: margin 2")
    before = sum(m.value for m in foe.attack_modifiers())
    res = _run(e, {"op": "use_ability", "actor": "pc", "params": {"ability": "Shatterspell",
                                                                  "to": "c1"}})
    out = res.outcomes[-1]
    assert out.status == "resolved", out.tell
    assert sum(m.value for m in foe.attack_modifiers()) == before - 2, out.tell
    assert foe.has_state("suppressed.spell")
    foe.tick_effects(1)
    assert not foe.has_state("suppressed.spell")
    assert sum(m.value for m in foe.attack_modifiers()) == before
    assert pc.pool("shatterspell").current == 0        # BAB 12: once a day
    pc.pool("shatterspell").current = 1
    pc.add_buff("combat_mod", "cmb", 10, source="test: margin 12")
    s.standard_spent.pop("pc", None)
    out = _run(e, {"op": "use_ability", "actor": "pc", "params": {"ability": "Shatterspell",
                                                                  "to": "c1"}}).outcomes[-1]
    assert "dispelled" in out.tell, out.tell
    assert not any(x.origin == "spell:bless" for x in foe.effects)

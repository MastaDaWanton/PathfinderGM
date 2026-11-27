"""Feat loop b5-core's smaller base rules, each through the engine.

- The whip threatens nothing (CRB, Weapon Descriptions: "you don't threaten the area into
  which you can make an attack"). Measured before: a whip threatened as a reach weapon
  (rules/reactions.py `reach_with`), so a whip-wielder took attacks of opportunity out to
  15 feet and Improved Whip Mastery granted what everybody already had.
- Hard-Headed's "+1 bonus on attack rolls ... made using a helmet": the weapons table has
  carried the dwarven boulder helmet all along; its document said no helmet existed.
"""
from __future__ import annotations

from rules import reactions
from tests.test_feats_b4_moves import _board, _pc


def test_a_whip_threatens_nothing_until_improved_whip_mastery():
    for feats, threatens in (((), False),
                             (("Weapon Focus", "Whip Mastery", "Improved Whip Mastery"), True)):
        pc = _pc("fighter", level=6, feats=feats, weapons=("whip",))
        pc.equipped = "whip"
        s, e = _board(pc, ("thug", (7, 5)))
        zone = reactions.threatened_by(s, "pc")
        assert bool(zone) is threatens, feats
        if threatens:
            # "your natural reach plus 5 feet": ten feet for a Medium body, adjacent too.
            assert (7, 5) in zone and (6, 5) in zone and (8, 5) not in zone


def test_hard_headed_adds_one_to_a_helmet_blow_and_nothing_to_a_sword():
    def to_hit(feats, key):
        pc = _pc("fighter", feats=feats, weapons=("helmet-dwarven-boulder", "longsword"))
        return sum(m.value for m in pc.attack_modifiers(key))

    assert to_hit(("Hard-Headed",), "helmet-dwarven-boulder") == \
        to_hit((), "helmet-dwarven-boulder") + 1
    assert to_hit(("Hard-Headed",), "longsword") == to_hit((), "longsword")


# --- costly material components (rules/components.py) ---------------------------------------

def _stoneskin(goods=0):
    from tests.test_readied_action import _caster

    pc = _caster("pc", prepared=("stoneskin",))
    if goods:
        pc.goods["costly spell components"] = goods
    s, e = _board(pc, ("thug", (15, 15)))
    from tests.test_feats_b4_moves import _run

    res = _run(e, {"op": "cast", "actor": "pc", "target": "pc", "visibility": "hidden",
                   "params": {"spell": "stoneskin"}})
    return pc, res.outcomes[-1]


def test_stoneskin_needs_its_250_gp_of_diamond_dust_on_hand():
    """Measured before: `component_cost` was read by nothing, and stoneskin's 250 gp of
    granite and diamond dust was free. Without it the spell is refused and the slot kept;
    with it the casting annihilates 250 gp of the stock."""
    pc, out = _stoneskin()
    assert out.status == "refused" and out.code == "no_component", out.tell
    from rules import casting

    assert casting.prepared_count(pc, "stoneskin") == 1, "nothing was spent"
    pc, out = _stoneskin(goods=300)
    assert out.status == "resolved", out.tell
    assert pc.goods.get("costly spell components") == 50
    assert any(x.get("kind") == "component_spent" for x in out.effects)


def test_a_negligible_component_is_never_asked():
    """The owner's instruction: no bat guano. Magic missile (no M) and a spell whose
    material has no listed cost cast with nothing carried."""
    from rules import components, spells

    assert components.kind(spells.get("magic-missile")) == ""
    assert components.kind(spells.get("fireball")) == ""
    assert components.kind(spells.get("stoneskin")) == "M"



# --- ferocity (Bestiary, Universal Monster Rules) -------------------------------------------

def test_a_ferocious_creature_below_zero_fights_on_staggered_and_loses_a_point_a_round():
    """Ferocity (UMR): "remains conscious and can continue fighting even if its hit point
    total is below 0. The creature is still staggered and loses 1 hit point each round."
    Measured before: the `ferocity` tag laid staggered and the body went on to `dying`
    anyway — `is_down`, out of the fight, rolling to stabilise like anyone."""
    from rules.activeeffect import ActiveEffect
    from rules.bestiary import instantiate
    from rules.engine import Scene

    s = Scene(location_id="5bbd0c40345f")
    boar = instantiate("thug", scene=s, name="the boar")
    boar.apply_effect(ActiveEffect(name="ferocity", kind="situation", key="ferocity",
                                   source="Ferocity", origin="test", tags=("ferocity",)))
    boar.hp = 2
    boar.take_damage(4)
    boar.apply_hp_state()               # what the engine asks after every blow
    assert boar.hp == -2
    assert not boar.is_down, "fights on below 0"
    assert boar.has_state("state.impaired.staggered")
    assert not boar.has_condition("dying") and not boar.has_condition("unconscious")
    boar.run_periodic("round", 1)
    assert boar.hp == -3, "a hit point a round"
    boar.take_damage(50)
    boar.apply_hp_state()
    assert boar.is_dead, "still dies at minus its Constitution"

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

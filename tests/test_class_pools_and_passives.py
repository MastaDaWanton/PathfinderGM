"""Lane F of the 2026-11-22 implementation audit: class pools, passive documents and
descriptors.

Measured before any of this (docs/implementation-audit-2026-11-22.md §2, §5 Lane F):

- a saved barbarian held Extra Rage and raged 4 + Con + 2/level rounds, exactly as many as
  one without it — the class file's formula was the whole maximum and no feat document
  could reach a pool; Extra Ki, Extra Channel, Extra Lay On Hands and Extra Performance
  did nothing either;
- Improved Channel's +2 DC was nowhere: a channel's DC took only its domain's terms.

Every test goes through the real sheet (`classes.apply`, the load door) or the engine's
own `validate`/`run`.
"""
from __future__ import annotations

from rules import class_abilities as ca
from rules import classes, feats as feats_mod

from tests.test_class_ability_executor import _board, _pc, _use


def _max(actor, pid):
    classes.apply(actor)
    return actor.pool(pid).maximum


def test_extra_rage_adds_six_rounds_and_two_copies_add_twelve():
    """Audit 2026-11-22: the save holding Extra Rage raged 4 + Con + 2/level rounds, the
    same as without it. CRB: 'You can rage for 6 additional rounds per day … its effects
    stack.'"""
    plain = _pc("barbarian", 3)
    base = _max(plain, "rage")
    once = _pc("barbarian", 3, feats=["extra rage"])
    assert _max(once, "rage") == base + 6
    twice = _pc("barbarian", 3, feats=["extra rage", "extra rage"])
    assert _max(twice, "rage") == base + 12
    # A fresh pool starts full, so the extra rounds are there to spend at once.
    assert twice.pool("rage").current == base + 12


def test_each_extra_feat_reaches_its_own_pool():
    """Extra Ki +2, Extra Performance +6, Extra Lay On Hands +2, Extra Channel +2 — each
    measured against the same character without the feat."""
    cases = [("monk", 6, "extra ki", "ki", 2),
             ("bard", 3, "extra performance", "bardic performance", 6),
             ("paladin", 4, "extra lay on hands", "lay on hands", 2)]
    for cls, level, feat, pid, more in cases:
        assert _max(_pc(cls, level, feats=[feat]), pid) == _max(_pc(cls, level), pid) + more, feat
    doc = next(d for d in ca.documents()["cleric"]["abilities"] if d["key"] == "channel energy")
    plain, extra = _pc("cleric", 3), _pc("cleric", 3, feats=["extra channel"])
    assert ca.uses_left(extra, doc)[1] == ca.uses_left(plain, doc)[1] + 2
    ca.ensure_pool(extra, doc)
    assert extra.pool("channel energy").maximum == ca.uses_left(plain, doc)[1] + 2


def test_a_feat_aimed_at_a_pool_nothing_defines_is_refused_at_load():
    """A `pool.<id>` target nothing reads would be a feat that silently does nothing; the
    validator names the targets that are read."""
    from rules import classbuilder

    bad = classbuilder.validate_feat_document("extra-rage", {"modifiers": [
        {"type": "combat_mod", "target": "pool.rgae", "amount": 6}]})
    assert bad and "read by nothing" in bad[0] and "pool.rage" in bad[0]
    assert not classbuilder.validate_feat_document("extra-rage",
                                                   feats_mod.documents()["extra-rage"])


def test_improved_channel_raises_the_channel_dc_by_two():
    """Audit 2026-11-22: Improved Channel (CRB, +2 to the DC of your channel energy) had no
    document. Measured on a cleric's harm-undead burst, with and without the feat."""
    dcs = []
    for feats in ([], ["improved channel"]):
        pc = _pc("cleric", 3, feats=feats, domains=["War", "Good"])
        s, e = _board(pc, ("skeleton", (6, 5)), face=2)
        s.actors["c1"].hp = s.actors["c1"].hp_max = 60
        out, _ = _use(e, "Channel Energy (harm)")
        dcs.append(next(x["dc"] for x in out.effects if x.get("kind") == "save"))
    assert dcs[1] == dcs[0] + 2, dcs

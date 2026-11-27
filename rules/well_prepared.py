"""Well-Prepared (Advanced Player's Guide; aonprd.com FeatDisplay.aspx?ItemName=Well-Prepared,
read 2026-11-27): "Once per day, when confronted with a situation that calls for a particular
mundane item of equipment, you may make a Sleight of Hand check with a DC of 10 plus the
item's cost in gold pieces to "happen" to have such an item on your person. For example,
having a crowbar would be DC 12, whereas a flask of acid would be DC 20. The item must be
something you can easily carry ... You cannot have magical items using this feat, nor can
you have specific items, such as the key to a particular door ... You must pay for these
items normally."

The item is the general store's own row (`goods.goods_at("market")`, the Core goods tables)
matched by the player's words (`goods.match_want`, the counter's one matcher), so its price
is the book's and nothing is invented; the coin moves through `goods.spend`, the item through
`goods.deliver`, the buy's own two doors. Once a day is an effect on the user on the one
ticker (`well-prepared.spent`). Not offered: the Special's Survival in place of Sleight of
Hand ("At the GM's option").

shortcut: "easily carry" is read as gear and weapons the store sells (no mount, no cart);
upgrade when goods carry a bulk the engine can weigh against the pack.
"""
from __future__ import annotations

from .activeeffect import ActiveEffect

TAG = "skill.sleight-of-hand.well-prepared"
SPENT = "well-prepared.spent"
DAY_ROUNDS = 14400


def door(engine, intent, actor, mods, partial):
    from . import goods
    from .engine import Outcome

    if not actor.has_state(TAG):
        return engine._refuse(intent, f"{actor.name} does not have the Well-Prepared feat. "
                                      f"Nothing is rolled.")
    if actor.has_state(SPENT):
        return engine._refuse(intent, f"{actor.name} has already been well prepared once "
                                      f"today. Nothing is rolled.")
    want = str(intent.params.get("item") or "").strip()
    rows = [g for g in goods.goods_at("market") if g.kind in ("gear", "weapon")]
    found, _near = goods.match_want(want, rows) if want else (None, [])
    if found is None:
        return engine._refuse(intent, (f"No mundane item the store sells answers "
                                       f"\"{want}\"; Well-Prepared finds only those. "
                                       f"Nothing is rolled.") if want else
                              "Name the mundane item to have about you. Nothing is rolled.")
    price_cp = int(round(float(found.price_gp) * 100))
    if goods.in_copper(actor.purse) < price_cp:
        return engine._refuse(intent, f"The {found.name} must be paid for, and "
                                      f"{actor.name} has not the coin. Nothing is rolled.")
    dc = 10 + int(float(found.price_gp))
    roll = engine._roll_or_suspend(intent, actor, list(mods),
                                   label="Sleight of Hand check (Well-Prepared)", dc=dc,
                                   partial=partial)
    actor.apply_effect(ActiveEffect(
        name="well prepared", kind="situation", key="well-prepared", source="Well-Prepared",
        origin="rule:feat-well-prepared", duration="rounds", rounds_left=DAY_ROUNDS,
        tags=(SPENT,)))
    effects = [{"ref": actor.ref, "kind": "well_prepared", "item": found.name, "dc": dc,
                "total": roll.total, "origin": "rule:feat-well-prepared"}]
    if roll.total < dc:
        return Outcome(intent_id=intent.id, op="check", actor=actor.ref, rolls=[roll],
                       effects=effects,
                       tell=f"{actor.name} pats every pocket for a {found.name.lower()} "
                            f"(Sleight of Hand {roll.total} against DC {dc}); none turns up.",
                       because=intent.because)
    actor.purse, _ok = goods.spend(actor.purse, price_cp)
    got, said = goods.deliver(engine.scene, actor, found, 1)
    return Outcome(intent_id=intent.id, op="check", actor=actor.ref, rolls=[roll],
                   effects=effects + got,
                   tell=f"{actor.name} happens to have a {found.name.lower()} about them "
                        f"(Sleight of Hand {roll.total} against DC {dc}, Well-Prepared), and "
                        f"it was paid for: {found.price_gp:g} gp.",
                   because=intent.because)

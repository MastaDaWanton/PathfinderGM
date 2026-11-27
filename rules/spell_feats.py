"""Feat loop batch 5, lane b5-spells (2026-11-26): the questions this lane's feats ask that no
reader answered yet, each asked of the documents and the vocabulary, never of a feat's name.

- Who cast it: Schooled Resolve's "mind-affecting spells and effects from vampires" is a
  save `against` "vampire_mind" (`save_words`), added beside the spell's own words where
  the cast's and the creature's saves already add Witchbreaker's "hag_or_witch".

Text read on aonprd.com FeatDisplay pages 2026-11-26.
"""
from __future__ import annotations

VAMPIRE_MIND = "vampire_mind"


def is_vampire(actor) -> bool:
    """A vampire by its stat block (`vampire`, `vampire-lord`, `enlightened-vampire` ...):
    the bestiary's own family, as Witchbreaker's hags are found (`feat_events`)."""
    if actor is None:
        return False
    getter = getattr(actor, "_creature_doc", None)
    doc = getter() if callable(getter) else None
    return _doc_is_vampire(doc or {})


def _doc_is_vampire(doc: dict) -> bool:
    cid = str(doc.get("id") or "").strip().lower()
    return cid == "vampire" or cid.startswith("vampire-") or cid.endswith("-vampire")


def origin_is_vampire(origin) -> bool:
    text = str(origin or "")
    if not text.startswith("creature:"):
        return False
    from . import bestiary

    return _doc_is_vampire(bestiary.raw(text.split(":", 1)[1]) or {})


def save_words(words, *, caster=None, origin="") -> tuple[str, ...]:
    """`words` (what a save is against) with "vampire_mind" added when the effect is
    mind-affecting and a vampire's — its cast, or its own ability by the origin stamp."""
    words = (words,) if isinstance(words, str) else tuple(words or ())
    # "This does not stack with the normal bravery bonus on saves against fear effects":
    # a vampire's fear effect is bravery's alone, which is the same number once.
    if "mind-affecting" in words and "fear" not in words and (
            is_vampire(caster) or origin_is_vampire(origin)):
        return words + (VAMPIRE_MIND,)
    return words


# --- Spell Chain -----------------------------------------------------------------------------
# Demon Hunter's Handbook: "Whenever you make a successful caster level check to overcome a
# target's spell resistance, the next ally who also has this feat that attempts to overcome
# the same target's spell resistance can roll twice ... taking the better result. This
# benefit must be used within 1 round or else it is lost." The success lays a one-round mark
# on the target naming who made it (`Engine._resists`); the next holder's check spends it.
CHAIN = "chain.spell"                   # the feat document's tag
CHAINED = "mark.spell-chain"            # the one-round mark on the resisting creature


def chained(engine, caster, target, roll):
    """The better of `roll` and a second die when another holder's success marked this
    target; the mark is spent either way."""
    if not caster.has_state(CHAIN):
        return roll
    def ally(ref) -> bool:
        other = engine.scene.actors.get(str(ref or ""))
        return other is not None and other is not caster and not engine._against(caster,
                                                                                 other)

    mark = next((e for e in target.effects if CHAINED in (e.tags or ())
                 and ally((e.payload or {}).get("by"))), None)
    if mark is None:
        return roll
    target.remove_effects(match=lambda e, m=mark: e is m)
    again = engine.dice.d20(list(roll.modifiers), label=f"{roll.label} (Spell Chain, the "
                            f"second die)", visibility="player" if caster.is_pc else "hidden")
    return again if again.total > roll.total else roll


def chain_mark(caster, target) -> None:
    from .activeeffect import ActiveEffect

    if not caster.has_state(CHAIN):
        return
    target.remove_effects(match=lambda e: CHAINED in (e.tags or ()))
    target.apply_effect(ActiveEffect(
        name="a way through its resistance", kind="effect", key="spell-chain",
        source=f"{caster.name}'s spell", origin="rule:spell-chain", duration="rounds",
        rounds_left=1, tags=(CHAINED,), payload={"by": caster.ref}))


# --- Covering Defense --------------------------------------------------------------------------
# APG: "When you use the total defense action while using a light, heavy, or tower shield,
# you can provide a cover bonus to AC against all attacks to an adjacent ally your size or
# smaller. This cover bonus is equal to your shield's shield bonus and lasts until the
# beginning of your next turn." Read live off the board on the ally's AC line: the bearer
# holds the document's tag and the total defense stance (a one-round effect), so the cover
# goes when the stance does. Cover is the board's own `cover` type, so it does not stack
# with the cover a wall gives (`position.ac_mods`).
COVERS = "guard.covering-defense"


def covering(defender) -> list:
    from . import position, states
    from .dice import Modifier
    from .sheet import current_moment
    from .tables import SIZE_ORDER

    scene = getattr(current_moment(), "scene", None)
    here = getattr(scene, "actors", None) or {}
    if defender.ref not in here:
        return []

    def size(a) -> int:
        s = str(getattr(a, "size", "") or "medium").lower()
        return SIZE_ORDER.index(s) if s in SIZE_ORDER else SIZE_ORDER.index("medium")

    out = []
    for ref, guard in here.items():
        if ref == defender.ref or guard.is_down or not guard.has_state(COVERS) \
                or not guard.has_state(states.TOTAL_DEFENSE) \
                or not position._same_side(scene, defender.ref, ref) \
                or size(defender) > size(guard):
            continue
        shield = guard.shield_stats() or {}
        if str(guard.shield or "none") in ("none", "buckler") or not shield.get("ac"):
            continue
        try:
            feet = scene.distance_between(defender.ref, ref)
        except Exception:  # noqa: BLE001 - an unplaced body is unmeasured
            feet = None
        if feet is not None and int(feet) <= 5:
            out.append(Modifier(int(shield["ac"]), f"{guard.name}'s shield (Covering "
                                                   f"Defense)", "cover"))
    return out

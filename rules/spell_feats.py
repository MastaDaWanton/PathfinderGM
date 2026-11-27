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


# --- Saving Shield ---------------------------------------------------------------------------
# APG: "Whenever an adjacent ally is the target of an attack, you can, as an immediate
# action, grant that adjacent ally a +2 shield bonus to AC. You must be wielding a light
# shield, heavy shield, or tower shield to use this feat." Asked as the blow is aimed, before
# the target's AC is read (`Engine._attack` at `target_ac`): the first holder beside the
# target with a shield on the arm and an immediate action left spends it (`_spend_swift`,
# immediate) and lays the +2 for the round — a shield bonus, so it is worth nothing to an
# ally whose own shield gives as much, and is then not spent (owner call: the engine uses
# it for the guard, when it helps).
SAVES_ALLY = "guard.saving-shield"


def saving_shield(engine, attacker, defender) -> list[str]:
    from .activeeffect import ActiveEffect

    scene = engine.scene
    if not scene.in_encounter or defender.is_down:
        return []
    if any(e.key == "saving-shield" for e in defender.effects):
        return []
    own = int((defender.shield_stats() or {}).get("ac", 0) or 0)
    if own >= 2:
        return []
    for guard in scene.actors.values():
        if guard is defender or guard is attacker or guard.is_down \
                or not guard.has_state(SAVES_ALLY) or engine._against(guard, defender) \
                or str(guard.shield or "none") in ("none", "buckler"):
            continue
        gap = engine._gap_ft(guard, defender)
        if gap is None or gap > 5 or engine._swift_refusal(guard, True, "Saving Shield"):
            continue
        engine._spend_swift(guard, immediate=True, what="Saving Shield")
        defender.apply_effect(ActiveEffect(
            name="a shield thrust across", kind="buff", key="saving-shield",
            source=f"{guard.name}'s shield", origin="rule:saving-shield", duration="rounds",
            rounds_left=1, modifiers=[{"kind": "combat_mod", "target": "ac", "amount": 2,
                                       "bonus_type": "shield", "note": "Saving Shield"}]))
        return [f"{guard.name} thrusts a shield across {defender.name} (+2 armour class)."]
    return []


# --- Arcane School Spirit ------------------------------------------------------------------
# Gnomes of Golarion: "the target takes a -2 penalty on saving throws made to resist the
# next spell of this school that you cast". The ability (content/class-abilities/
# feats-b5-spells.json) lays the penalty as an effect tagged `mark.school-spirit.<school>`;
# the save against the holder's next spell of that school spends it (`Engine._cast_save`).
# shortcut: the penalty answers any caster's spell of the school until a holder's spends
# it; give the mark its maker's ref (`vs`) when a fight shows two school-spirit gnomes.
SCHOOL_SPIRIT = "spirit.arcane-school"          # the feat document's tag
SCHOOL_MARK = "mark.school-spirit."


def spend_school_mark(caster, target, spell) -> None:
    school = str(getattr(spell, "school", "") or "").strip().lower()
    if caster is None or not school or not caster.has_state(SCHOOL_SPIRIT):
        return
    target.remove_effects(match=lambda e: SCHOOL_MARK + school in (e.tags or ()))


# --- Drunken Brawler ---------------------------------------------------------------------------
# Faiths of Purity: "When you drink a tankard of ale or strong alcohol, you take a -2 penalty
# on Reflex saving throws, but gain a number of temporary hit points equal to your level, and
# gain a +2 alchemical bonus on Fortitude and Will saving throws. These bonuses lasts an hour
# or until the temporary hit points gained by this effect are spent, whichever occurs first.
# The penalties last for a full hour." Laid by the drink op on a gear row marked `alcohol`.
BRAWLER = "drink.brawler"                       # the feat document's tag
HOUR = 600                                      # rounds


def drunken_brawler(actor) -> str:
    from .activeeffect import ActiveEffect

    if not actor.has_state(BRAWLER):
        return ""
    lvl = int(getattr(actor, "level", 1) or 1)
    actor.gain_temp_hp(lvl, source="Drunken Brawler", rounds=HOUR,
                       origin="rule:drunken-brawler")
    courage = [{"kind": "save_mod", "target": t, "amount": 2, "bonus_type": "alchemical",
                "note": "Drunken Brawler"} for t in ("fort", "will")]
    # Feat loop b6-partials: "These bonuses last an hour or until the temporary hit points
    # gained by this effect are spent, whichever occurs first. The penalties last for a
    # full hour." The +2s ride the temporary hit points' own effect, so the pool's
    # emptying takes them (law 2); the -2 Reflex is its own hour. A better pool that kept
    # this one from landing leaves the +2s on the hour's effect instead.
    pool = next((e for e in actor.effects if e.kind == "temp_hp"
                 and e.source == "Drunken Brawler"), None)
    if pool is not None:
        pool.modifiers = [m for m in pool.modifiers if m.get("note") != "Drunken Brawler"] \
            + courage
    actor.apply_effect(ActiveEffect(
        name="the ale's courage", kind="buff", key="drunken-brawler", source="ale",
        origin="rule:drunken-brawler", duration="rounds", rounds_left=HOUR,
        modifiers=([] if pool is not None else courage)
        + [{"kind": "save_mod", "target": "ref", "amount": -2, "bonus_type": "",
            "note": "Drunken Brawler"}]))
    return (f" The drink settles warm in {actor.name}'s belly: {lvl} temporary hit points, "
            f"steadier in body and will, a step slower to dodge, for an hour.")

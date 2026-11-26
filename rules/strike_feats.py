"""Feat loop b4, lane b4-combat (2026-11-26): the critical feats, shots and blows.

The engine calls these at moments it already knows (the confirmed critical, the range
increment, the flank, the blow that landed); nothing here names a feat by its name — a
document's tag says what it holds (law 1), and every number lands as an ActiveEffect
through the one applicator with a tell (laws 2 and 3).

Sources: each benefit is the book's (content/feats/feats.json, the OGL sheet), checked
against aonprd.com FeatDisplay on 2026-11-26. Prior art: Foundry PF1 leaves every critical
feat to the table (a chat-card note, no applicator); Owlcat's Pathfinder: Kingmaker models
the CRB critical feats as `AddCriticalHitTrigger`-style components that apply a buff on a
confirmed critical with a Fortitude DC of 10 + BAB — read from the community's decompiled
blueprint references, no primary source loadable, so said so here.
"""
from __future__ import annotations

from .activeeffect import ActiveEffect

# --- the critical feats (CRB p.119-122 and the Dragonslayer's Handbook) -----------------
#
# Each row is a document tag. `save`: the Fortitude DC 10 + BAB the CRB critical feats
# share. `fail` / `made`: (condition, rounds) — rounds a number, a dice notation, or None
# for "permanently". `adds`: "The effects of this feat do not stack. Additional hits
# instead add to the duration" (Sickening, Staggering, Stunning). `spares`: the conditions
# that leave the creature untouched ("This feat has no effect on exhausted creatures").
CRITICAL_ROWS: dict[str, dict] = {
    # Blinding Critical (CRB): "permanently blinded. A successful Fortitude save reduces
    # this to dazzled for 1d4 rounds ... no effect on creatures that do not rely on eyes".
    "critical.blinding": {"feat": "Blinding Critical", "save": True,
                          "fail": ("blinded", None), "made": ("dazzled", "1d4"),
                          "spares": ("blinded",), "immunity": "blinded"},
    # Deafening Critical (CRB): "permanently deafened. A successful Fortitude save reduces
    # the deafness to 1 round ... no effect on deaf creatures."
    "critical.deafening": {"feat": "Deafening Critical", "save": True,
                           "fail": ("deafened", None), "made": ("deafened", 1),
                           "spares": ("deafened",), "immunity": "deafened"},
    # Exhausting Critical (CRB): "immediately becomes exhausted. This feat has no effect
    # on exhausted creatures."
    "critical.exhausting": {"feat": "Exhausting Critical", "fail": ("exhausted", None),
                            # a fatigued creature is exhausted in fatigue's place
                            "spares": ("exhausted",), "replaces": ("fatigued",),
                            "immunity": "exhausted"},
    # Tiring Critical (CRB): "becomes fatigued. This feat has no additional effect on a
    # fatigued or exhausted creature."
    "critical.tiring": {"feat": "Tiring Critical", "fail": ("fatigued", None),
                        "spares": ("fatigued", "exhausted"), "immunity": "fatigued"},
    # Sickening Critical (CRB): "sickened for 1 minute ... Additional hits instead add to
    # the effect's duration."
    "critical.sickening": {"feat": "Sickening Critical", "fail": ("sickened", 10),
                           "adds": True, "immunity": "sickened"},
    # Staggering Critical (CRB): "staggered for 1d4+1 rounds. A successful Fortitude save
    # reduces the duration to 1 round."
    "critical.staggering": {"feat": "Staggering Critical", "save": True,
                            "fail": ("staggered", "1d4+1"), "made": ("staggered", 1),
                            "adds": True, "immunity": "staggered"},
    # Stunning Critical (CRB): "stunned for 1d4 rounds. A successful Fortitude save
    # reduces this to staggered for 1d4 rounds."
    "critical.stunning": {"feat": "Stunning Critical", "save": True,
                          "fail": ("stunned", "1d4"), "made": ("staggered", "1d4"),
                          "adds": True, "immunity": "stunned"},
}
# Flaying Critical (Dragonslayer's Handbook): "a -1 penalty to its natural armor bonus for
# the duration of the encounter. This penalty is cumulative, but cannot reduce an
# opponent's natural armor bonus below 0." Its own shape: a typed penalty, not a condition.
FLAYING = "critical.flaying"
TAGS = tuple(CRITICAL_ROWS) + (FLAYING,)
# What a fight's end sweeps (`Engine.end_encounter`): "for the duration of the encounter".
ENDS_WITH_FIGHT = "duration.encounter"


def _rounds(engine, spec, label: str):
    if spec is None:
        return None
    if isinstance(spec, int):
        return spec
    return max(1, engine.dice.roll(str(spec), label=label, visibility="hidden").total)


def _lay(defender, key: str, rounds, origin: str, source: str, adds: bool) -> int | None:
    """Lay `key` from this feat; a running one from it is lengthened when the feat says
    additional hits add to the duration (never two copies). Returns the rounds it holds."""
    from . import states

    mine = next((e for e in defender.effects if e.origin == origin and e.key == key), None)
    if mine is not None and adds and rounds is not None and mine.rounds_left is not None:
        mine.rounds_left += int(rounds)
        return mine.rounds_left
    if mine is not None and rounds is None:
        mine.rounds_left, mine.duration = None, "until-dismissed"
        return None
    if mine is not None:
        mine.rounds_left = max(int(mine.rounds_left or 0), int(rounds))
        return mine.rounds_left
    from .tables import CONDITIONS

    defender.apply_effect(ActiveEffect(
        name=CONDITIONS.get(key, {}).get("name", key), kind="condition", key=key,
        source=source, origin=origin,
        duration="until-dismissed" if rounds is None else "rounds", rounds_left=rounds,
        tags=states.tags_for(key)))
    return rounds


def _span(rounds) -> str:
    if rounds is None:
        return "permanently"
    return f"for {rounds} round{'s' if rounds != 1 else ''}"


def critical_riders(engine, actor, defender, held: list[str]) -> list[dict]:
    """The rows of `CRITICAL_ROWS` (and Flaying) among `held` — the critical feats the
    engine's `_critical_feat` already narrowed to one unless Critical Mastery — on the
    creature a confirmed critical just struck."""
    from . import states
    from .dice import d20_succeeds

    out: list[dict] = []
    for tag in held:
        row = CRITICAL_ROWS.get(tag)
        if row is None:
            continue
        origin = f"rule:feat-{row['feat'].lower().replace(' ', '-')}"
        source = f"{actor.name}'s {row['feat']}"
        why = states.immune_to(defender, row["immunity"], row["immunity"])
        if why:
            out.append({"effect": {"ref": defender.ref, "kind": "rider_refused",
                                   "rider": row["immunity"], "origin": origin},
                        "tell": f"{defender.name} is immune ({why}); {row['feat']} does "
                                f"nothing."})
            continue
        if any(defender.has_state(states.tags_for(s)[0]) for s in row.get("spares", ())):
            out.append({"effect": {"ref": defender.ref, "kind": "rider_refused",
                                   "rider": row["fail"][0], "origin": origin},
                        "tell": f"{defender.name} is already {row['spares'][0]}; "
                                f"{row['feat']} adds nothing."})
            continue
        key, spec = row["fail"]
        rec: dict = {"ref": defender.ref, "kind": "condition", "origin": origin}
        if row.get("save"):
            dc = 10 + int(actor.bab)
            roll = engine.dice.d20(defender.save_modifiers("fort"),
                                   label=f"Fortitude save ({row['feat']}, DC {dc})",
                                   visibility="hidden")
            rec.update(save=roll.total, dc=dc)
            if d20_succeeds(roll, dc):
                key, spec = row["made"]
        for gone in row.get("replaces", ()):
            defender.remove_effects(match=lambda e, g=gone: e.kind == "condition"
                                    and e.key == g)
        rounds = _rounds(engine, spec, f"{row['feat']} (rounds)")
        held_for = _lay(defender, key, rounds, origin, source, bool(row.get("adds")))
        rec.update(condition=key, rounds=held_for)
        said = (f" (Fortitude {rec['save']} against {rec['dc']})" if "save" in rec else "")
        out.append({"effect": rec,
                    "tell": f"{actor.name}'s critical leaves {defender.name} {key} "
                            f"{_span(held_for)}{said} ({row['feat']})."})
    if FLAYING in held:
        out.extend(_flay(actor, defender))
    return out


def _natural_armour(defender) -> int:
    """The natural armour bonus the defender's AC carries, before any flaying."""
    return sum(m.value for m in defender.ac_modifiers()
               if (m.type or "") == "natural armour" and m.value > 0)


def _flay(actor, defender) -> list[dict]:
    origin = "rule:feat-flaying-critical"
    have = _natural_armour(defender)
    mine = next((e for e in defender.effects if e.origin == origin), None)
    cut = int((mine.payload or {}).get("cut", 0)) if mine else 0
    if have <= cut:
        return [{"effect": {"ref": defender.ref, "kind": "rider_refused",
                            "rider": "natural armour", "origin": origin},
                 "tell": f"{defender.name} has no natural armour left to flay "
                         f"(Flaying Critical)."}]
    cut += 1
    defender.remove_effects(match=lambda e: e.origin == origin)
    defender.apply_effect(ActiveEffect(
        name="Flayed hide", kind="situation", key="flayed", source=f"{actor.name}'s "
        f"Flaying Critical", origin=origin, tags=(ENDS_WITH_FIGHT,), payload={"cut": cut},
        modifiers=[{"kind": "combat_mod", "target": "ac", "amount": -cut,
                    "bonus_type": "natural armour", "note": "Flaying Critical"}]))
    return [{"effect": {"ref": defender.ref, "kind": "penalty", "target": "natural armour",
                        "amount": -cut, "origin": origin},
             "tell": f"{actor.name}'s critical tears {defender.name}'s hide: natural "
                     f"armour {-cut} for the rest of the fight (Flaying Critical)."}]


# --- range: Far Shot, Distance Thrower ---------------------------------------------------
FAR_SHOT = "range.far-shot"                  # CRB: "-1 penalty per full range increment"
DISTANCE_THROWER = "range.thrown.less-2"     # UC: "reduce your penalty ... by 2"


def range_penalty(actor, increments: int, thrown: bool) -> int:
    """The attack penalty for `increments` full range increments past the first (CRB:
    -2 each), as the shooter's feats change it."""
    pen = -(1 if actor.has_state(FAR_SHOT) else 2) * int(increments)
    if thrown and actor.has_state(DISTANCE_THROWER):
        pen = min(0, pen + 2)
    return pen


# --- cover and concealment: Improved Precise Shot, Elven Accuracy ------------------------
# Improved Precise Shot (CRB): "Your ranged attacks ignore the AC bonus granted to targets
# by anything less than total cover, and the miss chance granted to targets by anything
# less than total concealment." Total cover is refused before this is asked.
PRECISE_PAST_COVER = "shot.past-partial-cover"
# Elven Accuracy (APG): "If you miss due to concealment when making a ranged attack with a
# longbow or shortbow (including composite bows), you can reroll your miss chance roll one
# time" — taken always, since a reroll of a miss can only help.
BOW_REROLL = "miss_chance.reroll.bow"
_BOWS = ("longbow", "shortbow", "composite-longbow", "composite-shortbow")


def cover_kept(actor, weapon: dict, mods: list) -> list:
    """The board's cover terms this shot still meets."""
    if weapon.get("category") == "ranged" and actor.has_state(PRECISE_PAST_COVER):
        return []
    return mods


def bow_reroll(actor, weapon: dict, weapon_key: str) -> bool:
    if weapon.get("category") != "ranged" or not actor.has_state(BOW_REROLL):
        return False
    return base_key(weapon, weapon_key) in _BOWS


def base_key(weapon: dict, weapon_key) -> str:
    """The table key a blow's weapon answers to: a crafted one's base, else its own."""
    from . import weapons as weapons_mod

    base = str(weapon.get("crafted_base") or weapon_key or "").strip().lower()
    return str(weapons_mod.key_for(base) or base).replace(" ", "-")


# --- improvised weapons: Catch Off-Guard, Throw Anything --------------------------------
# Catch Off-Guard (CRB): "You do not suffer any penalties for using an improvised melee
# weapon. Unarmed opponents are flat-footed against any attacks you make with an
# improvised melee weapon." Throw Anything (CRB): "You do not suffer any penalties for
# using an improvised ranged weapon" (its +1 on thrown splash weapons is a modifier).
IMPROVISED_MELEE = "proficiency.improvised.melee"
IMPROVISED_THROWN = "proficiency.improvised.ranged"


def _improvised(weapon: dict, key) -> bool:
    return str(key or "").strip().lower() == "improvised" \
        or "improvised" in (weapon.get("traits") or ())


def improvised_waived(actor, key, weapon: dict, thrown: bool) -> bool:
    """Whether the -4 for an improvised weapon is waived by the wielder's feat."""
    if not _improvised(weapon, key):
        return False
    ranged = thrown or weapon.get("category") == "ranged"
    return actor.has_state(IMPROVISED_THROWN if ranged else IMPROVISED_MELEE)


def unarmed(actor) -> bool:
    """No weapon in hand and no natural weapon, nor a fist that counts as armed (CRB,
    Unarmed Attacks: Improved Unarmed Strike or a monk's strike is "considered armed")."""
    from . import classfeatures
    from .sheet import STRIKES_EITHER_WAY

    return actor.wielded_key() == "unarmed" and not (
        actor.has_state(STRIKES_EITHER_WAY) or actor.has_state(classfeatures.UNARMED_STRIKE))


def caught_off_guard(actor, defender, key, weapon: dict) -> bool:
    return (defender is not None and weapon.get("category") != "ranged"
            and _improvised(weapon, key) and actor.has_state(IMPROVISED_MELEE)
            and unarmed(defender))


# --- flanking without the geometry: Gang Up, Overwhelm -----------------------------------
# Gang Up (APG): "You are considered to be flanking an opponent if at least two of your
# allies are threatening that opponent, regardless of your actual positioning."
# Overwhelm (Dragonslayer's Handbook): "... if at least one ally who also has this feat is
# threatening that opponent and the opponent is at least two size categories larger than
# the larger of you or your ally". The attacker must still threaten the foe (a flank is a
# melee fact: `position._melee` is asked before this).
GANG_UP = "flank.gang-up"
OVERWHELM = "flank.overwhelm"


def _threatening(scene, ref, defender) -> bool:
    from . import reactions
    from .grid import footprint

    there = scene.positions.get(defender.ref)
    if there is None:
        return False
    return any(reactions.threatens(scene, ref, sq, defender.size)
               for sq in footprint((there[0], there[1]), defender.size or "medium"))


def flank_by_feat(scene, actor, defender, same_side) -> list:
    """The allies a Gang Up or Overwhelm holder counts as flanking with, or []."""
    if not (actor.has_state(GANG_UP) or actor.has_state(OVERWHELM)) \
            or not _threatening(scene, actor.ref, defender):
        return []
    from .classfeatures import size_steps

    allies = [a for ref, a in scene.actors.items()
              if ref not in (actor.ref, defender.ref) and not a.is_down
              and same_side(scene, actor.ref, ref) and _threatening(scene, ref, defender)]
    if actor.has_state(GANG_UP) and len(allies) >= 2:
        return allies
    if actor.has_state(OVERWHELM):
        return [a for a in allies if a.has_state(OVERWHELM)
                and min(size_steps(actor, defender), size_steps(a, defender)) >= 2]
    return []


def alone(actor, scene, feet: int) -> bool:
    """Desperate Battler's question: no ally of `actor`'s within `feet`, and no aid another
    on it. Measured on the board; with no map nobody is measured near, so only the aid is
    asked. Allies are the declared sides' (`position._same_side`)."""
    from . import position

    if actor is None or scene is None:
        return False
    if any(str((e.payload or {}).get("aid") or "") for e in actor.effects):
        return False
    for ref in getattr(scene, "actors", {}) or {}:
        if ref == actor.ref or not position._same_side(scene, actor.ref, ref):
            continue
        try:
            gap = scene.distance_between(actor.ref, ref)
        except Exception:  # noqa: BLE001 - an unplaced body is unmeasured
            gap = None
        if gap is not None and int(gap) <= int(feet):
            return False
    return True


# --- the weapon a feat names, widened: Martial Versatility, Martial Mastery --------------
# Martial Versatility (ARG): "Choose one combat feat you know that applies to a specific
# weapon (e.g., Weapon Focus). You can use that feat with any weapon within the same
# weapon group." Martial Mastery (ARG): "Each combat feat you have that applies to a
# specific weapon ... can be used with all weapons in the same weapon group." The feat's
# own parenthetical stays its target; `target_groups` is what `sheet._scope_holds` and
# `feat_events.has_weapon_focus` widen it by.
MARTIAL_MASTERY = "feat.weapon.whole-group"


def widen(actor, doc):
    """`doc` with `target_groups` when the bearer's versatility reaches it, else `doc`."""
    if not doc or not doc.get("target") or getattr(actor, "_widening", False):
        return doc
    from . import weapons as weapons_mod

    target = str(doc["target"]).strip().lower()
    if not weapons_mod.has(target):
        return doc
    if not (actor.has_state(MARTIAL_MASTERY) or _versatile_in(actor, doc)):
        return doc
    groups = weapons_mod.groups_of(target)
    return dict(doc, target_groups=sorted(groups)) if groups else doc


def _versatile_in(actor, doc) -> bool:
    from . import feats as feats_mod

    want = {str(doc.get("id") or ""), str(doc.get("name") or "").strip().lower()}
    actor._widening = True
    try:
        for raw in getattr(actor, "feats", None) or ():
            mine = feats_mod.document(raw)
            if mine and mine["id"] == "martial-versatility":
                picked = str(mine.get("target") or "").strip().lower()
                if picked in want or picked.replace(" ", "-") in want:
                    return True
    finally:
        actor._widening = False
    return False


# --- damage reduction passed: Greater Penetrating Strike, Punch Through ------------------
# Greater Penetrating Strike (CRB): "Your attacks made with weapons selected with Weapon
# Focus ignore up to 10 points of damage reduction. This amount is reduced to 5 points for
# damage reduction without a type (such as DR 10/-)." Punch Through (Demon Hunter's
# Handbook): a full-round single attack that "hits and deals damage to the target, all of
# your allies with this feat ignore up to 5 points of damage reduction against the same
# target for 1 round. This feat does not apply to damage reduction without a type".
GREATER_PENETRATING = "dr.penetrating.greater"
PUNCH_THROUGH = "dr.punch-through"
PUNCHED = "rule:feat-punch-through"
CLEAVING_FINISH_UNLIMITED = "attack.cleaving-finish.unlimited"   # Improved Cleaving Finish


def dr_traits(actor, defender, weapon_key) -> tuple[str, ...]:
    from . import feat_events
    from .sheet import IGNORES_DR, IGNORES_TYPED_DR, current_moment

    out: list[str] = []
    if actor.has_state(GREATER_PENETRATING) and feat_events.has_weapon_focus(actor, weapon_key):
        out += [f"{IGNORES_TYPED_DR}:10", f"{IGNORES_DR}:5"]
    scene = getattr(current_moment(), "scene", None)
    if scene is not None and actor.has_state(PUNCH_THROUGH):
        from . import position

        for e in defender.effects:
            by = str((e.payload or {}).get("by") or "")
            if e.origin == PUNCHED and by and by != actor.ref \
                    and position._same_side(scene, by, actor.ref):
                out.append(f"{IGNORES_TYPED_DR}:5")
                break
    return tuple(out)


def punch_through(actor, defender, dealt: int) -> list[dict]:
    """The mark a Punch Through blow that dealt damage leaves for the bearer's allies."""
    if dealt <= 0 or defender.is_dead:
        return []
    defender.remove_effects(match=lambda e: e.origin == PUNCHED
                            and (e.payload or {}).get("by") == actor.ref)
    defender.apply_effect(ActiveEffect(
        name=f"opened by {actor.name}", kind="situation", key=f"punched-{actor.ref}",
        source=f"{actor.name}'s Punch Through", origin=PUNCHED, duration="rounds",
        rounds_left=1, payload={"by": actor.ref}))
    return [{"effect": {"ref": defender.ref, "kind": "situation", "what": "punched through",
                        "by": actor.ref, "origin": PUNCHED},
             "tell": f"{actor.name}'s blow opens a way through {defender.name}'s hide: "
                     f"allies who fight as {actor.name} does pass 5 of its damage "
                     f"reduction for a round (Punch Through)."}]


# --- the threat range against one foe: Slayer's Knack -----------------------------------
# Slayer's Knack (UC): "choose one of your favored enemy types. Against enemies of that
# type, the threat range of any weapon you wield is doubled. This effect does not stack
# with any other effect that expands a weapon's threat range." The pick is the feat's
# parenthetical; a row a keen edge or Improved Critical already doubled
# (`crit_range_printed`) is left as it is.
SLAYERS_KNACK = "crit.favored-enemy.doubled"


def threat_from(actor, defender, weapon: dict) -> int:
    low = int(weapon.get("crit_range") or 20)
    if defender is None or weapon.get("crit_range_printed") is not None \
            or not actor.has_state(SLAYERS_KNACK):
        return low
    from . import classfeatures, feats as feats_mod
    from .sheet import doubled_threat

    for raw in getattr(actor, "feats", None) or ():
        doc = feats_mod.document(raw)
        if doc and SLAYERS_KNACK in (doc.get("tags") or ()) and doc.get("target") \
                and classfeatures.holds({"target": "$pick"}, actor,
                                        {"target_actor": defender}, str(doc["target"])):
            return doubled_threat(low, 2)
    return low


# --- the guard against a weapon group: Defensive Weapon Training ------------------------
# Defensive Weapon Training (UC): "Choose a weapon group from the fighter's weapon training
# class ability list (except natural weapons). You gain a +2 dodge bonus on AC when an
# opponent attacks you using a weapon from that group. If you also have the weapon training
# class feature in the selected group, your dodge bonus from this feat increases to +3."
# Its effects do not stack: the best one pick gives is the one taken.
GUARDS_GROUP = "ac.dodge.weapon-group"


def guard_against(defender, attacker, weapon: dict, weapon_key, flat_footed: bool) -> list:
    from .dice import Modifier

    if flat_footed or defender.loses_dex_to_ac or not defender.has_state(GUARDS_GROUP) \
            or weapon.get("natural"):
        return []
    from . import classfeatures, feats as feats_mod, weapons as weapons_mod

    groups = weapons_mod.groups_of(base_key(weapon, weapon_key))
    trained = {classfeatures._group_word(c["pick"])
               for c in classfeatures.chosen(defender, "weapon training")} \
        if str(defender.char_class or "").lower() == "fighter" and defender.level >= 5 else set()
    best = 0
    for raw in getattr(defender, "feats", None) or ():
        doc = feats_mod.document(raw)
        if not doc or GUARDS_GROUP not in (doc.get("tags") or ()):
            continue
        group = classfeatures._group_word(str(doc.get("target") or ""))
        if group and group in groups:
            best = max(best, 3 if group in trained else 2)
    return [Modifier(best, f"Defensive Weapon Training ({group_name(groups)})", "dodge")] \
        if best else []


def group_name(groups) -> str:
    return ", ".join(sorted(groups)) or "the group"


# --- the declared one-blow options (sheet.ATTACK_CHOICES) --------------------------------
# Each is its feat document's `choice`; the numbers that ride the roll are the document's
# `when.choice` terms, and what happens around the roll is here.
#
# "As a full-round action, you can make a single ... attack": Death or Glory (UC), Punch
# Through (Demon Hunter's Handbook), Cockatrice Strike (APG). The round is the coup de
# grace's (`Engine._coup_round_spent`, `_coup_paid`).
WHOLE_ROUND = {"death_or_glory": "Death or Glory", "punch_through": "Punch Through",
               "cockatrice_strike": "Cockatrice Strike"}
# Cockatrice Strike's "against a dazed, flat-footed, paralyzed, staggered, stunned, or
# unconscious foe" (flat-footed is asked of the engine at the blow).
_COCKATRICE_FOES = ("state.impaired.dazed", "state.held.paralyzed",
                    "state.impaired.staggered", "state.unable.stunned",
                    "state.down.unconscious", "state.unable.dazed")


def whole_round(params) -> str:
    """The full-round option this attack declares, by name, or ""."""
    return next((name for c, name in WHOLE_ROUND.items() if (params or {}).get(c)), "")


def choice_refusal(actor, w: dict, declared, params) -> str:
    """Why one of this lane's options cannot ride this swing, or "" (called beside
    `feat_events.choice_refusal` from `Engine._attack_choice_refusal`)."""
    params = params or {}
    full = bool(params.get("full_attack")) or params.get("iteration") is not None
    ranged = w.get("category") == "ranged" or bool(params.get("thrown"))
    key = base_key(w, params.get("weapon") or "")
    unarmed_key = key in ("unarmed", "unarmed-strike") \
        or str(w.get("name") or "").lower().startswith("unarmed")
    for c, name in WHOLE_ROUND.items():
        if c in declared and (full or params.get("coup_de_grace") or params.get("manoeuvre")):
            return f"{name} is one attack as a full-round action; make it on its own."
    if "death_or_glory" in declared and ranged:
        return f"Death or Glory is a melee attack, not a {w['name']}."
    if "deadly_finish" in declared and ranged:
        return f"Deadly Finish rides a melee attack, not a {w['name']}."
    if "reckless_aim" in declared and not ranged:
        return "Reckless Aim is a shot or a throw, not a melee blow."
    if "two_handed_throw" in declared:
        if not params.get("thrown") or w.get("category") == "ranged":
            return "Two-Handed Thrower is a weapon thrown, with both hands."
        if str(getattr(actor, "shield", "") or "none").lower() not in ("", "none") \
                or params.get("off_hand"):
            return (f"{actor.name} needs both hands free of a shield or a second weapon "
                    f"to throw two-handed.")
    for c, name in (("cockatrice_strike", "Cockatrice Strike"), ("hamatulatsu", "Hamatulatsu")):
        if c in declared and not unarmed_key:
            return f"{name} is an unarmed strike, not a blow with a {w['name']}."
    return ""


def target_refusal(engine, actor, defender, params) -> str:
    """Why this foe is the wrong one for a declared option, or "" (asked at validation,
    where the foe is known)."""
    params = params or {}
    if defender is None:
        return ""
    from .tables import SIZE_ORDER

    size = str(defender.size or "medium").lower()
    if params.get("death_or_glory") and (size not in SIZE_ORDER or SIZE_ORDER.index(size)
                                         < SIZE_ORDER.index("large")):
        return (f"Death or Glory is made against a creature Large or larger; "
                f"{defender.name} is {size}.")
    if params.get("reckless_aim"):
        from . import position

        if not position.engaged_with_friend(engine.scene, actor, defender):
            return (f"Reckless Aim is a shot at a foe engaged in melee, and nobody of "
                    f"{actor.name}'s side is fighting {defender.name}.")
    if params.get("cockatrice_strike") and not (
            any(defender.has_state(t) for t in _COCKATRICE_FOES)
            or engine._flat_footed(defender)):
        return (f"Cockatrice Strike is made against a dazed, flat-footed, paralyzed, "
                f"staggered, stunned or unconscious foe; {defender.name} is none of these.")
    return ""


# --- the next attack: Opening Volley, Bullseye Shot, Death or Glory's answer ------------
# An effect whose payload says which attack spends it: `{"next_attack": {"category":
# "melee", "vs": <ref>}}` - "the next melee attack roll you make against the opponent"
# (Opening Volley, UC), "the next ranged attack roll you make before the end of your turn"
# (Bullseye Shot, Faiths of Purity). Its terms are its own modifiers, scoped by `vs` the
# way aid another's are; the roll they ride removes it.
NEXT_ATTACK = "next_attack"
NEXT_RANGED = "next-attack.ranged"           # a class-ability `self` effect's own tag


def _spend_next(actor, weapon: dict, defender) -> None:
    cat = "ranged" if weapon.get("category") == "ranged" else "melee"

    def spent(e) -> bool:
        if cat == "ranged" and NEXT_RANGED in (e.tags or ()):      # Bullseye Shot's use
            return True
        want = (e.payload or {}).get(NEXT_ATTACK)
        if not isinstance(want, dict):
            return False
        if want.get("category") and want["category"] != cat:
            return False
        return not want.get("vs") or (defender is not None and want["vs"] == defender.ref)
    actor.remove_effects(match=spent)


def lay_next_attack(actor, name: str, origin: str, amount: int, bonus_type: str,
                    category: str, vs: str = "", rounds: int = 1, targets=("attack",)):
    actor.remove_effects(match=lambda e: e.origin == origin
                         and ((e.payload or {}).get(NEXT_ATTACK) or {}).get("vs", "") == vs)
    actor.apply_effect(ActiveEffect(
        name=name, kind="buff", key=f"{origin}-{vs}", source=name, origin=origin,
        duration="rounds", rounds_left=rounds,
        payload={NEXT_ATTACK: {"category": category, **({"vs": vs} if vs else {})}},
        modifiers=[{"kind": "combat_mod", "target": t, "amount": amount,
                    "bonus_type": bonus_type, "note": name, **({"vs": vs} if vs else {}),
                    "when": {"weapon": {"ranged": category == "ranged"}}}
                   for t in targets]))


def after_roll(engine, intent, actor, defender, weapon_key, weapon, atk, state, choices):
    """Once a swing's attack roll is down, hit or miss: the next-attack bonuses it spent,
    Reckless Aim's lowered guard and its natural 1 (`Engine._op_attack`)."""
    _spend_next(actor, weapon, defender)
    if not state.get("glory_said"):
        state["glory_said"] = True
        for p in death_or_glory_answer(engine, actor, defender, choices):
            state["effects"].append(p["effect"])
            state["tells"].append(p["tell"])
    if "reckless_aim" not in choices:
        return
    if not state.get("reckless_said"):
        state["reckless_said"] = True
        actor.apply_effect(ActiveEffect(
            name="aiming recklessly", kind="buff", key="reckless aim",
            source="Reckless Aim", origin="rule:feat-reckless-aim", duration="rounds",
            rounds_left=1, modifiers=[{"kind": "combat_mod", "target": "ac", "amount": -1,
                                       "bonus_type": "untyped", "note": "Reckless Aim"}]))
        state["tells"].append(f"{actor.name} takes the shot recklessly (Reckless Aim): "
                              f"-1 armour class until their next turn.")
    if atk.natural == 1:
        _reckless_miss(engine, actor, defender, weapon_key, weapon, state)


def _reckless_miss(engine, actor, defender, weapon_key, weapon, state) -> None:
    """Reckless Aim (Blood of Fiends): "when you roll a natural 1 on a ranged attack roll
    made with this bonus, you automatically hit a random adjacent creature that threatens
    your intended target" - the weapon's own damage, through the one damage door."""
    from . import reactions
    from .grid import footprint
    from .sheet import attacker_traits

    there = engine.scene.positions.get(defender.ref)
    if there is None:
        return
    squares = footprint((there[0], there[1]), defender.size or "medium")
    near = [a for ref, a in sorted(engine.scene.actors.items())
            if ref not in (actor.ref, defender.ref) and not a.is_down
            and (g := engine._gap_ft(a, defender)) is not None and g <= 5
            and any(reactions.threatens(engine.scene, ref, sq, defender.size)
                    for sq in squares)]
    if not near:
        return
    pick = near[0] if len(near) == 1 else near[engine.dice.roll(
        f"1d{len(near)}", label="Reckless Aim (who is hit)", visibility="hidden").total - 1]
    dmg = engine.dice.roll(weapon["damage"], actor.damage_modifiers(weapon_key,
                                                                     defender=pick),
                           label=f"Damage ({weapon['name']}, Reckless Aim)",
                           visibility="hidden")
    hit = engine._apply_damage(pick, max(1, dmg.total), weapon["type"],
                               traits=tuple(weapon.get("strikes_as") or ())
                               + attacker_traits(actor))
    hit["origin"] = "rule:feat-reckless-aim"
    state["rolls"].append(dmg.as_dict())
    state["effects"].append(hit)
    state["tells"].append(f"The wild shot finds {pick.name} instead, beside "
                          f"{defender.name}: {hit.get('amount', dmg.total)} damage "
                          f"(Reckless Aim, natural 1).")


# --- a critical given away: Butterfly's Sting -------------------------------------------
# Butterfly's Sting (Faiths of Purity): "When you confirm a critical hit against a
# creature, you can choose to forgo the effect of the critical hit and grant a critical
# hit to the next ally who hits the creature with a melee attack before the start of your
# next turn. Your attack only deals normal damage, and the next ally automatically
# confirms the hit as a critical." Declared with the swing (`butterfly_sting`).
STING = "rule:feat-butterfly-s-sting"


def on_confirm(actor, defender, choices, state) -> None:
    if not state.get("crit") or "butterfly_sting" not in choices:
        return
    state["crit"] = False
    defender.remove_effects(match=lambda e: e.origin == STING)
    defender.apply_effect(ActiveEffect(
        name=f"marked by {actor.name}", kind="situation", key=f"sting-{actor.ref}",
        source=f"{actor.name}'s Butterfly's Sting", origin=STING, duration="rounds",
        rounds_left=1, payload={"by": actor.ref}))
    state["effects"].append({"ref": defender.ref, "kind": "situation", "what": "stung",
                             "by": actor.ref, "origin": STING})
    state["tells"].append(f"{actor.name} lets the critical go and marks the opening on "
                          f"{defender.name}: the next ally to strike it in melee lands a "
                          f"critical (Butterfly's Sting).")


def stung_critical(engine, actor, defender, weapon: dict) -> bool:
    """Whether this melee hit is the ally's critical a Butterfly's Sting gave; spends it."""
    if weapon.get("category") == "ranged":
        return False
    from . import position

    for e in list(defender.effects):
        by = str((e.payload or {}).get("by") or "")
        if e.origin == STING and by and by != actor.ref \
                and position._same_side(engine.scene, by, actor.ref):
            defender.remove_effects(match=lambda x, k=e: x is k)
            return True
    return False


# --- once a blow has landed (`Engine._op_attack`, beside `feat_events.after_hit`) --------
SPEAR_DANCER = "hit.dazzle.two-handed-reach"
OPENING_VOLLEY = "hit.ranged.opens-melee"


def glory_bonus(actor) -> int:
    """Death or Glory's +4, "an additional +1 on this bonus at base attack bonus +11, +16,
    and +20 (for a maximum of +7 at base attack +20)"."""
    bab = int(actor.bab)
    return 4 + sum(1 for at in (11, 16, 20) if bab >= at)


def death_or_glory_answer(engine, actor, defender, choices) -> list[dict]:
    """"After you resolve your attack, the opponent you attack can spend an immediate
    action to make a single melee attack against you with the same bonuses." Taken by
    the foe whenever it can (an extra blow only helps it): its immediate action spent
    through the one door (`Engine._spend_swift`), the bonuses a next-attack effect against
    the bearer alone, the swing queued as an owed one."""
    from . import position

    if "death_or_glory" not in choices or defender.is_down or defender.is_dead \
            or defender.blocking_key("attack"):
        return []
    if position.out_of_reach(engine.scene, defender, actor, defender.wielded_key()) \
            is not None:
        return []
    if engine._spend_swift(defender, True, "Death or Glory") is not None:
        return []
    n = glory_bonus(actor)
    lay_next_attack(defender, f"Death or Glory's answer to {actor.name}",
                    "rule:feat-death-or-glory", n, "untyped", "melee", vs=actor.ref,
                    targets=("attack", "damage", "crit_confirm"))
    raw = {"op": "attack", "actor": defender.ref, "target": actor.ref,
           "because": "Death or Glory", "visibility": "player" if defender.is_pc else "hidden",
           "params": {"full_attack": False, "reaction": "death_or_glory"}}
    return [{"effect": {"ref": defender.ref, "kind": "owed_swing", "attack": raw,
                        "target": actor.ref, "origin": "rule:feat-death-or-glory"},
             "tell": f"{defender.name} answers the all-or-nothing blow with one of its "
                     f"own, at +{n} as well (Death or Glory)."}]


def _reach_two_handed(weapon: dict, weapon_key) -> bool:
    from . import weapons as weapons_mod

    return int(weapon.get("hands", 1) or 1) >= 2 and weapon.get("category") != "ranged" \
        and weapons_mod.has_trait(base_key(weapon, weapon_key), "reach")


def after_hit(engine, intent, actor, defender, weapon_key, weapon, state, choices) -> list:
    from . import feat_events

    out: list[dict] = []
    dealt = int(state.get("dealt") or 0)
    melee = weapon.get("category") != "ranged"
    crit = bool(state.get("crit"))
    # Deadly Finish (UC): "When you hit with a melee attack and reduce your opponent to -1
    # or fewer hit points, you can force that opponent to succeed at a Fortitude save
    # (DC 15 + the damage your attack dealt) or die." Declared (`deadly_finish`).
    if "deadly_finish" in choices and melee and not defender.is_dead and defender.hp <= -1:
        out += _deadly_finish(engine, actor, defender, dealt, state)
    if "punch_through" in choices:
        out += punch_through(actor, defender, dealt)
    # Spear Dancer (Faiths of Purity): "Each time you hit a creature with a two-handed reach
    # weapon that you have Weapon Focus in, the creature is dazzled for 1 round."
    if actor.has_state(SPEAR_DANCER) and _reach_two_handed(weapon, weapon_key) \
            and feat_events.has_weapon_focus(actor, weapon_key) and not defender.is_dead:
        from . import states

        if not states.immune_to(defender, "dazzled", "dazzled"):
            defender.add_condition("dazzled", rounds=1, source=f"{actor.name}'s Spear Dancer",
                                   origin="rule:feat-spear-dancer")
            out.append({"effect": {"ref": defender.ref, "kind": "condition",
                                   "condition": "dazzled", "rounds": 1,
                                   "origin": "rule:feat-spear-dancer"},
                        "tell": f"The long blade's dance leaves {defender.name} dazzled "
                                f"for a round (Spear Dancer)."})
    # Opening Volley (UC): "Whenever you deal damage with a ranged attack, you gain a +4
    # circumstance bonus on the next melee attack roll you make against the opponent. This
    # attack must occur before the end of your next turn."
    if actor.has_state(OPENING_VOLLEY) and not melee and dealt > 0 and not defender.is_dead:
        lay_next_attack(actor, f"Opening Volley against {defender.name}",
                        "rule:feat-opening-volley", 4, "circumstance", "melee",
                        vs=defender.ref, rounds=2)
        out.append({"effect": {"ref": actor.ref, "kind": "buff", "what": "opening volley",
                               "vs": defender.ref, "origin": "rule:feat-opening-volley"},
                    "tell": f"The shot opens {defender.name} up: +4 on {actor.name}'s next "
                            f"melee attack against them, before the end of their next turn "
                            f"(Opening Volley)."})
    if crit and "hamatulatsu" in choices:
        out += _hamatulatsu(actor, defender)
    if crit and "cockatrice_strike" in choices:
        out += _cockatrice(engine, actor, defender, state)
    return out


def _deadly_finish(engine, actor, defender, dealt: int, state) -> list[dict]:
    from .dice import d20_succeeds

    dc = 15 + max(0, dealt)
    origin = "rule:feat-deadly-finish"
    roll = engine.dice.d20(defender.save_modifiers("fort"),
                           label=f"Fortitude save (Deadly Finish, DC {dc})",
                           visibility="hidden")
    state["rolls"].append(roll.as_dict())
    if d20_succeeds(roll, dc):
        return [{"effect": {"ref": defender.ref, "kind": "save", "save": "fort",
                            "made": True, "dc": dc, "origin": origin},
                 "tell": f"{defender.name} clings to life (Fortitude {roll.total} against "
                         f"{dc}, Deadly Finish)."}]
    defender.die(f"{actor.name}'s Deadly Finish")
    return [{"effect": {"ref": defender.ref, "kind": "condition", "condition": "dead",
                        "save": roll.total, "dc": dc, "origin": origin},
             "tell": f"{actor.name} finishes it: {defender.name} dies (Fortitude "
                     f"{roll.total} against {dc}, Deadly Finish)."}]


def _hamatulatsu(actor, defender) -> list[dict]:
    """Hamatulatsu (ISWG): "If you critically hit a foe with your unarmed strike while
    doing piercing damage ... the foe [becomes] sickened for 1 round (or staggered for 1
    round if the target is already sickened). Multiple critical hits in a round against a
    single foe do not increase the duration" - a refresh at 1 round, never longer."""
    from . import states

    origin = "rule:feat-hamatulatsu"
    if defender.is_dead:
        return []
    key = "staggered" if defender.has_state(states.tags_for("sickened")[0]) else "sickened"
    if states.immune_to(defender, key, key):
        return []
    defender.add_condition(key, rounds=1, source=f"{actor.name}'s Hamatulatsu", origin=origin)
    return [{"effect": {"ref": defender.ref, "kind": "condition", "condition": key,
                        "rounds": 1, "origin": origin},
             "tell": f"The piercing strike's pain leaves {defender.name} {key} for a round "
                     f"(Hamatulatsu)."}]


def _cockatrice(engine, actor, defender, state) -> list[dict]:
    """Cockatrice Strike (APG): "If that attack is a critical hit, the target is petrified
    unless it succeeds on a Fortitude saving throw with a DC of 10 + 1/2 your character
    level + your Wisdom modifier. This is a supernatural polymorph effect." """
    from . import states
    from .dice import d20_succeeds

    origin = "rule:feat-cockatrice-strike"
    if defender.is_dead or states.immune_to(defender, "petrification", "petrified"):
        return []
    dc = 10 + int(actor.level) // 2 + actor.ability_mod("wis")
    roll = engine.dice.d20(defender.save_modifiers("fort"),
                           label=f"Fortitude save (Cockatrice Strike, DC {dc})",
                           visibility="hidden")
    state["rolls"].append(roll.as_dict())
    if d20_succeeds(roll, dc):
        return [{"effect": {"ref": defender.ref, "kind": "save", "save": "fort",
                            "made": True, "dc": dc, "origin": origin},
                 "tell": f"{defender.name}'s flesh stiffens and holds (Fortitude "
                         f"{roll.total} against {dc}, Cockatrice Strike)."}]
    defender.add_condition("petrified", source=f"{actor.name}'s Cockatrice Strike",
                           origin=origin)
    return [{"effect": {"ref": defender.ref, "kind": "condition", "condition": "petrified",
                        "save": roll.total, "dc": dc, "origin": origin},
             "tell": f"{defender.name} turns to stone where the blow struck (Fortitude "
                     f"{roll.total} against {dc}, Cockatrice Strike)."}]


# --- the monk's strike feats -------------------------------------------------------------
# Cornugon Stun (Cheliax): "You may use Stunning Fist when making melee attacks with special
# monk weapons as well as when making unarmed attacks." The Stunning Fist charge armed for
# the fist is spent through a weapon with the `monk` trait too.
MONK_WEAPON_STUN = "charge.stunning-fist.monk-weapons"
STUNNING_PIN = "grapple.pin.stunning-fist"


def monk_weapon_carries(actor, key: str, e) -> bool:
    if not actor.has_state(MONK_WEAPON_STUN) or not str(e.origin or "").endswith(
            "/stunning fist"):
        return False
    from . import weapons as weapons_mod

    k = str(weapons_mod.key_for(key) or key)
    return weapons_mod.has(k) and weapons_mod.has_trait(k, "monk") \
        and weapons_mod.get(k).get("category") != "ranged"


def perfect_strike(engine, actor, weapon_key, weapon, atk, mods, state):
    """Perfect Strike (APG): "You can roll your attack roll twice and take the higher
    result. If one of these rolls is a critical threat, the other roll is used as your
    confirmation roll (your choice if they are both critical threats)." The charge armed
    by the feat's use (`charge.roll_twice`) on a kama, nunchaku, quarterstaff, sai or
    siangham; the second die is the engine's, shown in the tell. Both threats: the higher
    attacks and the other confirms - the choice that keeps the better hit."""
    if "perfect" in state or not any(
            (e.payload or {}).get("charge", {}).get("roll_twice")
            for e in engine._charges_for(actor, weapon_key, weapon)):
        return atk
    other = engine.dice.roll("1d20", mods, label=f"Attack with {weapon['name']} "
                             f"(Perfect Strike, second die)", visibility="player")
    state["rolls"].append(other.as_dict())
    low = int(weapon.get("crit_range") or 20)
    a_threat, b_threat = (atk.natural or 0) >= low, (other.natural or 0) >= low
    if a_threat or b_threat:
        keep, spare = (atk, other) if (a_threat and (not b_threat or atk.total >= other.total)) \
            else (other, atk)
        state["perfect"] = {"confirm_face": int(spare.natural or 1)}
    else:
        keep = atk if atk.total >= other.total else other
        state["perfect"] = {}
    state["tells"].append(f"{actor.name} strikes with perfect intent: two dice, "
                          f"{atk.total} and {other.total}, and the {keep.total} stands "
                          f"(Perfect Strike).")
    return keep


def kept_confirm(engine, mods, weapon, state):
    """The confirmation Perfect Strike's other die already is, or None to roll one."""
    face = (state.get("perfect") or {}).get("confirm_face")
    if not face:
        return None
    state["perfect"]["confirm_face"] = None
    return engine.dice.given(int(face), mods, f"Confirm critical ({weapon['name']}, "
                                               f"Perfect Strike's other die)")


def stunning_pin(engine, actor, defender) -> list[dict]:
    """Stunning Pin (UC): "Whenever you pin an opponent, you can spend a swift action to
    make a Stunning Fist attempt against that opponent." Taken when a use and the swift
    action are left: the bearer's own Stunning Fist document, armed and delivered on the
    pinned foe by the charge's one door (`Engine._deliver_charges`)."""
    if not actor.has_state(STUNNING_PIN):
        return []
    from . import class_abilities as ca

    doc, _ = ca.find(actor, "stunning fist")
    if not doc or not doc.get("charge"):
        return []
    ca.ensure_pool(actor, doc)
    pool = actor.pool("stunning fist")
    if pool is None or pool.current < 1:
        return []
    if engine._spend_swift(actor, False, "Stunning Pin") is not None:
        return []
    rdoc, _ = ca.resolved(actor, doc, "")
    actor.spend_pool("stunning fist", 1)
    actor.apply_effect(ActiveEffect(
        name=str(doc.get("name") or "Stunning Fist"), kind="buff", key="stunning pin",
        source="Stunning Pin", origin=ca.origin_of(doc), duration="rounds", rounds_left=1,
        tags=("buff.charged",),
        payload={"charge": engine._resolve_charge(actor, rdoc, rdoc["charge"])}))
    out = [{"effect": {"ref": actor.ref, "kind": "resource", "pool": "stunning fist",
                       "spent": 1, "left": pool.current, "origin": "rule:feat-stunning-pin"},
            "tell": f"{actor.name} drives a stunning blow into the pinned {defender.name} "
                    f"(Stunning Pin)."}]
    return out + engine._deliver_charges(actor, defender, "unarmed",
                                         weapon=actor.weapon("unarmed"))

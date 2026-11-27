"""What a held feat does when something happens in a fight: feat loop b3, 2026-11-26.

The b3 martial list is full of feats that answer an EVENT rather than a roll: "when you
confirm a critical hit", "when a critical hit is confirmed on you", "when your attack
reduces an enemy to negative hit points". A roll's `when` cannot carry them, because no
roll is being built at that moment; the attack loop has to say what just happened and ask
who cares. This module is that question, and nothing in it names a feat: a document's
`triggers` list says which event it answers and what it does, and the engine calls
`fire(...)` at the three moments it already knows about (the confirm, the blow that
lands, the fall).

Each trigger, validated by `problems` (rules/classbuilder.py calls it):

- `on`: `crit_dealt` (the bearer confirmed a critical), `crit_taken` (one was confirmed
  on the bearer), `felled` (the bearer's attack took a foe below 0 hit points or killed
  it — "negative hit points", "-1 or fewer": the same line), `hit` (a blow landed).
- `when`: the roll grammar's clauses — `bearer` (a held state: `buff.stance.rage`),
  `weapon` (melee), `critical`, `nonlethal` — answered by `classfeatures.holds`.
- `foe`: `{"hd_gte_bearer": true}` (Thrill of the Kill's "at least as many Hit Dice as
  you") or `{"cr_gte_level": true}` (Raging Deathblow's "CR equal to or greater than your
  character level", aonprd).
- `gain`: `{"pool": "rage", "amount": 1, "crit_extra": 1, "beyond_max": false}` — a pool
  the bearer holds gains rounds. `beyond_max` is Raging Deathblow's "extra round of rage
  for that day ... lost" at the next rest: the maximum is raised by an effect the night's
  rest clears (`duration.until-rest`), so the round is real and the rest takes it back.
- `once_per_round`: "You can only gain this benefit once per round" — a spent marker,
  one round on the one ticker (`spent.<feat id>`), shared by every trigger of the document.

Prior art: Foundry PF1 leaves these to the table (its "script calls" fire on an item's
use, not on a critical); Owlcat's Pathfinder: Kingmaker models Gore Fiend's family as
`AddInitiatorAttackWithWeaponTrigger` / `AddTargetAttackWithWeaponTrigger` components with
`CriticalHit` and `ReduceHPToZero` flags — an event and a condition on a document, the shape
taken here. (Read from the community's decompiled-blueprint references; no primary source
was loadable, so this paragraph says so.)
"""
from __future__ import annotations

import re

from .activeeffect import ActiveEffect

UNTIL_REST = "duration.until-rest"          # sheet.UNTIL_REST: a rest takes it back

EVENTS = ("crit_dealt", "crit_taken", "felled", "hit")
_KEYS = frozenset({"on", "when", "foe", "gain", "once_per_round"})
_GAIN_KEYS = frozenset({"pool", "amount", "crit_extra", "beyond_max"})
_FOE_KEYS = frozenset({"hd_gte_bearer", "cr_gte_level"})


def problems(at: str, triggers, doc: dict) -> list[str]:
    """Everything wrong with a document's `triggers`, each with the fix named."""
    from . import classfeatures, effectspec

    if not isinstance(triggers, list) or not triggers:
        return [f"{at}.triggers: a list, like [{{\"on\": \"crit_dealt\", \"gain\": "
                f"{{\"pool\": \"rage\", \"amount\": 1}}}}]."]
    out: list[str] = []
    for i, t in enumerate(triggers):
        where = f"{at}.triggers[{i}]"
        if not isinstance(t, dict):
            out.append(f"{where}: an object.")
            continue
        bad = sorted(set(t) - _KEYS)
        if bad:
            out.append(f"{where}: unknown key(s) {', '.join(bad)}; a trigger carries "
                       f"{', '.join(sorted(_KEYS))}.")
        if t.get("on") not in EVENTS:
            out.append(f"{where}.on: one of {', '.join(EVENTS)}.")
        gain = t.get("gain")
        if not isinstance(gain, dict) or not str(gain.get("pool") or "").strip() \
                or set(gain) - _GAIN_KEYS:
            out.append(f"{where}.gain: {{\"pool\": \"rage\", \"amount\": 1}}, with "
                       f"optional crit_extra and beyond_max.")
        foe = t.get("foe")
        if foe is not None and (not isinstance(foe, dict) or set(foe) - _FOE_KEYS):
            out.append(f"{where}.foe: {{\"hd_gte_bearer\": true}} or "
                       f"{{\"cr_gte_level\": true}}.")
        when = t.get("when")
        if isinstance(when, dict) and when:
            rest = {k: v for k, v in when.items() if k != "bearer"}
            if rest:
                out.extend(effectspec.when_problems(rest, f"{where}.when"))
            out.extend(classfeatures._check_when(
                {"bearer": when["bearer"]} if "bearer" in when else None, where, doc))
    return out


def is_hag_or_witch(actor) -> bool:
    """A hag (the bestiary's `*-hag` family: green, sea, annis, night) or a witch (the
    class, or a stat block's witch levels): Witchbreaker's foes."""
    if actor is None:
        return False
    if str(getattr(actor, "char_class", "") or "").strip().lower() == "witch":
        return True
    getter = getattr(actor, "_creature_doc", None)
    doc = getter() if callable(getter) else None
    return _doc_is_hag_or_witch(doc or {})


def _doc_is_hag_or_witch(doc: dict) -> bool:
    cid = str(doc.get("id") or "").strip().lower()
    if cid == "hag" or cid.endswith("-hag"):
        return True
    return "witch" in str(doc.get("class_levels") or "").lower()


def origin_is_hag_or_witch(origin) -> bool:
    """Whether a `creature:<template>` stamp names a hag or a witch."""
    text = str(origin or "")
    if not text.startswith("creature:"):
        return False
    from . import bestiary

    return _doc_is_hag_or_witch(bestiary.raw(text.split(":", 1)[1]) or {})


def _hit_dice(actor) -> int:
    from . import class_abilities

    try:
        return int(class_abilities.hit_dice_of(actor))
    except Exception:  # noqa: BLE001 — a sheet with no printed block counts its level
        return int(getattr(actor, "level", 1) or 1)


def _cr(actor) -> float:
    getter = getattr(actor, "_creature_doc", None)
    doc = (getter() if callable(getter) else None) or {}
    try:
        return float(doc.get("cr_value") if doc.get("cr_value") is not None
                     else getattr(actor, "level", 1))
    except (TypeError, ValueError):
        return float(getattr(actor, "level", 1) or 1)


def fire(actor, event: str, ctx: dict, *, foe=None, crit: bool = False) -> list[dict]:
    """Run every trigger of `actor`'s feats that answers `event`. Returns outcome
    pieces `{"effect": record, "tell": text}`, the riders' shape. `ctx` is the blow's roll
    context (`Actor._roll_context`), so a `when` reads the weapon as a roll term does."""
    from . import classfeatures, feats as feats_mod

    out: list[dict] = []
    seen: set[str] = set()
    for raw in getattr(actor, "feats", None) or ():
        doc = feats_mod.document(raw)
        if not doc or doc["id"] in seen or not doc.get("triggers"):
            continue
        seen.add(doc["id"])
        spent = f"spent.{doc['id']}"
        for t in doc["triggers"]:
            if t.get("on") != event:
                continue
            if t.get("once_per_round") and actor.has_state(spent):
                continue
            if not classfeatures.holds(t.get("when"), actor, {**ctx, "critical": crit}):
                continue
            if event == "felled" and foe is not None and not (foe.is_dead or foe.hp < 0):
                continue
            want = t.get("foe") or {}
            if foe is not None and want.get("hd_gte_bearer") \
                    and _hit_dice(foe) < _hit_dice(actor):
                continue
            if foe is not None and want.get("cr_gte_level") \
                    and _cr(foe) < int(getattr(actor, "level", 1) or 1):
                continue
            piece = _gain(actor, doc, t.get("gain") or {}, crit)
            if piece is None:
                continue
            out.append(piece)
            if t.get("once_per_round"):
                actor.apply_effect(ActiveEffect(
                    name=f"{doc['name']} (spent this round)", kind="situation",
                    key=spent, source=doc["name"], origin=f"rule:feat-{doc['id']}",
                    duration="rounds", rounds_left=1, tags=(spent,)))
    return out


def _gain(actor, doc: dict, gain: dict, crit: bool) -> dict | None:
    """A pool gain: capped at the pool's maximum unless `beyond_max`, when the maximum
    itself is raised by an effect a night's rest clears."""
    pid = str(gain.get("pool") or "").strip().lower()
    pool = actor.pool(pid)
    if pool is None:
        return None
    n = int(gain.get("amount", 1) or 1) + (int(gain.get("crit_extra", 0) or 0) if crit else 0)
    origin = f"rule:feat-{doc['id']}"
    if gain.get("beyond_max"):
        actor.apply_effect(ActiveEffect(
            name=f"{doc['name']}: {n} more {pid}", kind="buff", source=doc["name"],
            origin=origin, stacking="stack", tags=(UNTIL_REST,),
            modifiers=[{"kind": "combat_mod", "target": f"pool.{pid}", "amount": n,
                        "bonus_type": "untyped", "note": doc["name"]}]))
        pool.maximum += n
        pool.current += n
    else:
        if pool.current >= pool.maximum:
            return None
        before = pool.current
        pool.current = min(pool.maximum, pool.current + n)
        n = pool.current - before
    return {"effect": {"ref": actor.ref, "kind": "resource", "pool": pid, "gained": n,
                       "left": pool.current, "origin": origin},
            "tell": f"{actor.name} draws {n} more round{'s' if n != 1 else ''} of "
                    f"{pid} from it ({doc['name']})."}


# --- the attack loop's moments (feat loop b3) ---------------------------------------------
#
# Called by small hooks in the attack loop (`Engine._b3_*`). The logic lives here, beside
# the triggers, so the shared engine carries short calls and no feat's name: each feat is
# asked by its document's tag (law 1), each number lands through the one damage funnel
# (`Engine._apply_damage`) or as a named `Modifier` on the blow's own damage roll.

FOIL = "flank.foil"                       # Flanking Foil: the bearer's hits leave the mark
CLEAVING_FINISH = "attack.cleaving-finish"
VIOLENT_DISPLAY = "display.on-precision-or-critical"
BETRAYING_BLOW = "nonlethal.betraying-blow"
HOLD_THE_BLADE = "reaction.disarm-on-flank"
HAMMER_THE_GAP = "damage.consecutive-hits"
KNOCKOUT_ARTIST = "damage.unarmed-precision"


def blow_ctx(actor, weapon_key, weapon, defender) -> dict:
    ctx = actor._roll_context(weapon_key, defender=defender)
    if weapon.get("category") == "ranged":
        ctx["weapon"] = dict(ctx["weapon"], category="ranged", ranged=True)
    return ctx


def _daily(actor, key: str):
    """(document, pool) of a held feat whose `budget` names `key` and has a use left
    today — the uses a day are a pool named for the feat, refreshed by a night's rest (the
    shape `rules/luck.py` gives a luck feat's) — or (None, None)."""
    from . import feats as feats_mod, resources

    for raw in getattr(actor, "feats", None) or ():
        doc = feats_mod.document(raw)
        formula = ((doc or {}).get("budget") or {}).get(key)
        if not formula:
            continue
        pool = resources.define(actor, {"id": doc["id"], "max": str(formula),
                                        "refresh": "rest.night", "source": doc["name"]})
        if pool.current > 0:
            return doc, pool
    return None, None


def _use(actor, doc, pool, what: str) -> dict:
    actor.spend_pool(pool.id, 1)
    return {"ref": actor.ref, "kind": "resource", "pool": pool.id, "spent": 1,
            "left": pool.current, "what": what, "origin": f"rule:feat-{doc['id']}"}


def negate_precision(defender, dice: str, why: str, state) -> tuple[str, str]:
    """Survivor (ISWG): "Once per day, if you are struck by a critical hit or sneak attack,
    you can spend an immediate action to negate the critical or the sneak attack damage,
    making the attack a normal hit." The sneak attack half, asked before the dice are
    rolled and once per swing (the damage stage is re-entered on every resume). Taken the
    first time it can be (owner call: the engine spends a defender's once-a-day guard)."""
    if not dice or "sneak_total" in state:
        return dice, why
    if state.get("precision_negated"):
        return "", why
    doc, pool = _daily(defender, "negate_critical_or_precision")
    if doc is None:
        return dice, why
    state["precision_negated"] = True
    state.setdefault("effects", []).append(_use(defender, doc, pool, "sneak attack"))
    state.setdefault("tells", []).append(
        f"{defender.name} twists from the opening at the last instant: the blow lands, "
        f"but not where it was aimed ({doc['name']}).")
    return "", why


def half_nonlethal(defender, amount: int, state, lethality: str) -> tuple[int, int]:
    """Resilient Brute (ARG): "Once per day, when a creature confirms a critical hit
    against you, you may treat half the damage as nonlethal damage. You cannot use this
    ability if you are immune to nonlethal damage. When your base attack bonus reaches
    +10, you may use this ability an additional time per day." (lethal, nonlethal) of a
    critical's damage, the half marked at the confirm (`crit_events`)."""
    if not state.get("half_nonlethal") or lethality == "nonlethal" or amount <= 1:
        return amount, 0
    state.pop("half_nonlethal", None)
    spared = amount // 2
    return amount - spared, spared


def crit_events(engine, actor, defender, weapon_key, weapon, state, choices=()) -> None:
    """A critical just confirmed: the defender's guard against it (Survivor's negation,
    Resilient Brute's half nonlethal), then the attacker's `crit_dealt` triggers and the
    defender's `crit_taken` (Gore Fiend's both halves)."""
    doc, pool = _daily(defender, "negate_critical_or_precision")
    if doc is not None:
        state["crit"] = False
        _land([{"effect": _use(defender, doc, pool, "critical hit"),
                "tell": f"{defender.name} rolls with the blow at the last instant: it "
                        f"lands as an ordinary hit, no critical ({doc['name']})."}], state)
        return
    doc, pool = _daily(defender, "critical_half_nonlethal")
    if doc is not None and not defender.immune_to_nonlethal():
        state["half_nonlethal"] = True
        _land([{"effect": _use(defender, doc, pool, "critical hit"),
                "tell": f"{defender.name} takes the critical on muscle and bone: half of "
                        f"it will only bruise ({doc['name']})."}], state)
    crit_trade(engine, actor, defender, weapon, state, choices)
    ctx = blow_ctx(actor, weapon_key, weapon, defender)
    pieces = fire(actor, "crit_dealt", ctx, foe=defender, crit=True)
    pieces += fire(defender, "crit_taken", {"weapon": ctx["weapon"]}, foe=actor, crit=True)
    _land(pieces, state)


def _land(pieces, state) -> None:
    for p in pieces:
        state.setdefault("effects", []).append(p["effect"])
        if p.get("tell"):
            state.setdefault("tells", []).append(p["tell"])


def _spent(actor, tag: str) -> bool:
    return actor.has_state(f"spent.{tag}")


def _spend(actor, tag: str, name: str) -> None:
    actor.apply_effect(ActiveEffect(
        name=f"{name} (spent this round)", kind="situation", key=f"spent.{tag}",
        source=name, origin=f"rule:feat-{tag}", duration="rounds", rounds_left=1,
        tags=(f"spent.{tag}",)))


def has_weapon_focus(actor, weapon_key) -> bool:
    """Weapon Focus in this weapon, by the document's own `target` (the parenthetical)."""
    from . import feats as feats_mod, weapons as weapons_mod

    want = {str(weapon_key or "").lower(), str(weapons_mod.key_for(str(weapon_key or ""))
                                                or "").lower()}
    from . import strike_feats

    for raw in getattr(actor, "feats", None) or ():
        doc = strike_feats.widen(actor, feats_mod.document(raw))
        if doc and doc["id"] == "weapon-focus" and (
                str(doc.get("target") or "").strip().lower().replace(" ", "-") in want
                or (doc.get("target_groups") and set(doc["target_groups"])
                    & weapons_mod.groups_of(str(weapon_key or "")))):
            return True
    return False


def after_hit(engine, intent, actor, defender, weapon_key, weapon, state, choices) -> list[dict]:
    """What the attacker's (and the struck defender's) feats answer once a blow landed."""
    out: list[dict] = []
    ctx = blow_ctx(actor, weapon_key, weapon, defender)
    crit = bool(state.get("crit"))
    melee = weapon.get("category") != "ranged"
    blow = (state.get("blows") or [{}])[-1]
    dealt = int(state.get("dealt") or 0)
    # The fall: Thrill of the Kill, Raging Deathblow — once per foe per swing.
    fell = state.setdefault("felled_fired", [])
    if (defender.is_dead or defender.hp < 0) and defender.ref not in fell:
        fell.append(defender.ref)
        out += fire(actor, "felled", ctx, foe=defender, crit=crit)
    # Flanking Foil (UC): "Whenever you hit an adjacent opponent with a melee attack, until
    # the start of your next turn, that opponent does not gain any flanking bonus on attack
    # rolls while it is flanking you and cannot deal sneak attack damage to you."
    gap = engine._gap_ft(actor, defender)
    if melee and actor.has_state(FOIL) and gap is not None and gap <= 5 \
            and not defender.is_dead:
        from .precision import FOILED

        defender.apply_effect(ActiveEffect(
            name=f"foiled by {actor.name}", kind="situation", key=f"foiled.{actor.ref}",
            source=f"{actor.name}'s Flanking Foil", origin="rule:feat-flanking-foil",
            duration="rounds", rounds_left=1, tags=(FOILED,), payload={"by": actor.ref}))
        out.append({"effect": {"ref": defender.ref, "kind": "situation", "what": "foiled",
                               "by": actor.ref, "origin": "rule:feat-flanking-foil"},
                    "tell": f"{actor.name}'s blow turns {defender.name}'s angle: no flanker's "
                            f"edge against {actor.name} until their next turn."})
    out += _cleaving_finish(engine, intent, actor, defender, weapon_key, melee)
    out += _violent_display(engine, actor, weapon_key, state, crit)
    out += _betraying_blow(engine, actor, defender, blow, melee, dealt, state)
    out += _hold_the_blade(engine, intent, actor, defender, weapon, state, melee, dealt)
    out += push_after_hit(engine, actor, defender, choices, state,
                          bool(intent.params.get("power_attack")))
    # Feat loop b4-maneuver: Gory Finish's demoralize behind a blow that fells.
    from . import maneuver_feats

    out += maneuver_feats.gory_finish(engine, actor, defender, choices, state)
    out += maneuver_feats.unseat(engine, intent, actor, defender, weapon_key, choices)
    out += _ferocious_loyalty(engine, actor, defender)          # feat loop b5-other
    return out


LOYAL = "ferocious-loyalty"
LOYAL_ORIGIN = "rule:feat-ferocious-loyalty"


def _ferocious_loyalty(engine, actor, defender) -> list[dict]:
    """Ferocious Loyalty (Blood of the Moon): "Whenever an ally with this feat is rendered
    helpless or killed within 30 feet of you, you gain a +2 morale bonus on attack rolls
    for 1 minute or until the foe responsible is rendered helpless or killed, whichever
    comes first." Asked at the blow that does it: each holder on the fallen's side within
    30 feet takes the +2 (10 rounds, `payload.foe` the striker), and a blow that fells a
    foe somebody's +2 is held against ends it. shortcut: only a blow is seen to fell —
    a spell that renders the ally helpless lays nothing; upgrade when a fall is an event
    every door raises."""
    from . import feats as feats_mod
    from . import position as position_mod

    down = defender.is_dead or defender.is_helpless
    if not down:
        return []
    out: list[dict] = []
    for ref, other in engine.scene.actors.items():
        gone = other.remove_effects(match=lambda e: e.origin == LOYAL_ORIGIN and (
            e.payload or {}).get("foe") == defender.ref)
        if gone:
            out.append({"effect": {"ref": ref, "kind": "effect_ended", "what": gone[0].name,
                                   "origin": LOYAL_ORIGIN},
                        "tell": f"{other.name}'s fury at {defender.name} is spent."})
    if LOYAL not in feats_mod._held(defender):
        return out
    for ref, other in engine.scene.actors.items():
        if other is defender or other is actor or other.is_down                 or LOYAL not in feats_mod._held(other)                 or not position_mod._same_side(engine.scene, ref, defender.ref):
            continue
        gap = engine._gap_ft(other, defender)
        if gap is None or gap > 30:
            continue
        other.apply_effect(ActiveEffect(
            name="ferocious loyalty", kind="buff", key="ferocious loyalty",
            source="Ferocious Loyalty", origin=LOYAL_ORIGIN, duration="rounds",
            rounds_left=10, payload={"foe": actor.ref},
            modifiers=[{"kind": "combat_mod", "target": "attack", "amount": 2,
                        "bonus_type": "morale"}]))
        out.append({"effect": {"ref": ref, "kind": "buff", "buff": "ferocious loyalty",
                               "rounds": 10, "foe": actor.ref, "origin": LOYAL_ORIGIN},
                    "tell": f"{defender.name} falls, and {other.name} rounds on "
                            f"{actor.name} in fury (Ferocious Loyalty): +2 to hit for a "
                            f"minute."})
    return out


def _cleaving_finish(engine, intent, actor, defender, weapon_key, melee) -> list[dict]:
    """Cleaving Finish (UC): "If you make a melee attack, and your target drops to 0 or
    fewer hit points as a result of your attack, you can make another melee attack using
    your highest base attack bonus against another opponent within reach. You can make
    only one extra attack per round with this feat." Taken always (it only hurts a foe)."""
    from . import position as position_mod, reactions as reactions_mod, states

    from .strike_feats import CLEAVING_FINISH_UNLIMITED     # Improved Cleaving Finish (b4)

    if not melee or defender.hp > 0 or not actor.has_state(CLEAVING_FINISH) \
            or (_spent(actor, "cleaving-finish")
                and not actor.has_state(CLEAVING_FINISH_UNLIMITED)) \
            or not engine.scene.has_grid:
        return []
    pick = None
    for ref, foe in engine.scene.actors.items():
        if ref in (actor.ref, defender.ref) or foe.is_down \
                or ref not in engine.scene.positions or foe.has_state(states.BYSTANDER) \
                or reactions_mod._allied(engine.scene, actor.ref, ref):
            continue
        if position_mod.out_of_reach(engine.scene, actor, foe, weapon_key) is None:
            pick = foe
            break
    if pick is None:
        return []
    _spend(actor, "cleaving-finish", "Cleaving Finish")
    raw = {"op": "attack", "actor": actor.ref, "target": pick.ref,
           "id": f"{intent.id or 'attack'}-finish", "because": "Cleaving Finish",
           "visibility": intent.visibility or ("player" if actor.is_pc else "hidden"),
           "params": {"weapon": weapon_key, "iteration": 0,
                      **({"power_attack": True} if intent.params.get("power_attack")
                         else {})}}
    return [{"effect": {"ref": actor.ref, "kind": "owed_swing", "attack": raw,
                        "target": pick.ref, "origin": "rule:feat-cleaving-finish"},
             "tell": f"{defender.name} drops, and {actor.name} carries the blow on into "
                     f"{pick.name} (Cleaving Finish)."}]


def _violent_display(engine, actor, weapon_key, state, crit) -> list[dict]:
    """Violent Display (Blood of the Moon): "When you land a successful sneak attack or
    confirm a critical hit against a creature with a weapon with which you have Weapon
    Focus, you can use Dazzling Display as an immediate action" — Dazzling Display's own
    demoralize of every foe within 30 feet who can see the bearer (CRB), through the one
    door (`Engine._free_demoralize`). Taken when the immediate action is free."""
    from . import awareness

    if not actor.has_state(VIOLENT_DISPLAY) or not (crit or state.get("sneak_total")) \
            or not has_weapon_focus(actor, weapon_key) or state.get("violent_display"):
        return []
    if engine._spend_swift(actor, True, "Violent Display"):
        return []
    state["violent_display"] = True
    foes = [a for a in engine.scene.actors.values()
            if a is not actor and not a.is_down and engine._against(actor, a)
            and awareness.sees(engine.scene, a, actor)
            and ((g := engine._gap_ft(actor, a)) is None or g <= 30)]
    return engine._free_demoralize(actor, foes, "Violent Display") if foes else []


def _betraying_blow(engine, actor, defender, blow, melee, dealt, state) -> list[dict]:
    """Betraying Blow (Bastards of Golarion): a melee blow of nonlethal damage at a creature
    only the bearer threatens: Bluff against its Sense Motive, extra nonlethal equal to
    half the difference (the whole difference if it is friendly or helpful), never more
    than the bearer's Hit Dice."""
    from . import class_abilities, states
    from .sheet import Situation

    if not melee or dealt <= 0 or not blow.get("nonlethal") or defender.is_down \
            or not actor.has_state(BETRAYING_BLOW) \
            or not Situation(actor, engine.scene).sole_threat(defender):
        return []
    bluff = engine.dice.d20(actor.skill_modifiers("bluff", opposed=True),
                            label="Bluff (Betraying Blow)", visibility="player")
    sense = engine.dice.d20(defender.skill_modifiers("sense motive", opposed=True),
                            label=f"{defender.name}'s Sense Motive", visibility="hidden")
    state.setdefault("rolls", []).extend([bluff.as_dict(), sense.as_dict()])
    diff = max(0, bluff.total - sense.total)
    warm = states.attitude_of(defender) in ("friendly", "helpful")
    extra = min(diff if warm else diff // 2, class_abilities.hit_dice_of(actor))
    said = (f"{actor.name}'s Bluff {bluff.total} against {defender.name}'s Sense Motive "
            f"{sense.total}")
    if extra <= 0:
        return [{"effect": {"ref": defender.ref, "kind": "rider_resisted",
                            "rider": "betraying blow", "origin": "rule:feat-betraying-blow"},
                 "tell": f"{said}: {defender.name} sees it coming (Betraying Blow)."}]
    more = engine._apply_damage(defender, extra, str(blow.get("type") or "bludgeoning"),
                                lethality="nonlethal")
    more["origin"] = "rule:feat-betraying-blow"
    return [{"effect": more, "tell": f"{said}: the blow lands where {defender.name} trusted "
                                     f"it would not, {more.get('amount', extra)} more "
                                     f"nonlethal (Betraying Blow)."}]


def _hold_the_blade(engine, intent, actor, defender, weapon, state, melee, dealt) -> list[dict]:
    """Hold the Blade (Dragon Empires Primer), the struck defender's: "Whenever an enemy
    deals damage to you with a melee weapon as part of a flanking attack or sneak attack,
    you can make a combat maneuver check to disarm against that opponent as an immediate
    action. You must have at least one hand free ... you take a -4 penalty to your AC
    until your next turn. You can only use this feat once per round." Taken when it can
    be (owner call: the engine takes a reaction whose only price is the defender's AC)."""
    from . import position as position_mod

    if not melee or dealt <= 0 or defender.is_down or not defender.has_state(HOLD_THE_BLADE) \
            or _spent(defender, "hold-the-blade") or weapon.get("natural") \
            or str(weapon.get("name") or "").lower().startswith("unarmed"):
        return []
    flank = position_mod.flanking_with(engine.scene, actor, defender, weapon)
    if not flank and not state.get("sneak_total"):
        return []
    if not _hand_free(defender):
        return []
    if engine._spend_swift(defender, True, "Hold the Blade"):
        return []
    _spend(defender, "hold-the-blade", "Hold the Blade")
    defender.apply_effect(ActiveEffect(
        name="holding the blade", kind="buff", key="holding the blade",
        source="Hold the Blade", origin="rule:feat-hold-the-blade", duration="rounds",
        rounds_left=1, modifiers=[{"kind": "combat_mod", "target": "ac", "amount": -4,
                                   "bonus_type": "untyped", "note": "Hold the Blade"}]))
    out = [{"effect": {"ref": defender.ref, "kind": "buff", "what": "holding the blade",
                       "modifiers": [{"target": "ac", "amount": -4}],
                       "origin": "rule:feat-hold-the-blade"},
            "tell": f"{defender.name} grabs for {actor.name}'s weapon as it bites (Hold the "
                    f"Blade), dropping their guard for it."}]
    out += engine._rider_feat_maneuver(
        intent, defender, actor, {"maneuver": "disarm", "rider": "hold the blade",
                                  "weapon_key": "unarmed"},
        "rule:feat-hold-the-blade", state)
    return out


def _hand_free(actor) -> bool:
    """At least one hand not holding a weapon: no two-handed weapon in hand, and not a
    weapon in one hand with a shield on the other arm."""
    try:
        w = actor.weapon(actor.wielded_key())
    except Exception:  # noqa: BLE001 — nothing wielded is a free pair of hands
        return True
    if str(w.get("name") or "").lower().startswith("unarmed"):
        return True
    if int(w.get("hands", 1) or 1) >= 2:
        return False
    return not actor.shield_stats()


def damage_terms(engine, intent, actor, defender, weapon, state, mult, lethality,
                 denied_dex) -> list:
    """Terms on the blow's own damage roll, past the crit scaling (each multiplied here
    when the book says it is). Hammer the Gap (UC): "each consecutive hit against the same
    opponent deals extra damage equal to the number of previous consecutive hits you have
    made against that opponent this turn. This damage is multiplied on a critical hit."
    Knockout Artist (UC): "When you use your unarmed strike to deal nonlethal damage and
    sneak attack damage to an opponent denied his Dexterity bonus to AC, you gain a +1
    bonus on the damage roll per each sneak attack damage die you roll" — a bonus on the
    damage roll, so multiplied as the roll's own bonuses are."""
    from .dice import Modifier, stack
    from .sheet import ATTACK_CHOICES

    out = []
    # What the funnel holds that a critical never multiplies (`damage_unmultiplied`):
    # Raging Brutality's Constitution, asked with the blow's options and whose turn it is.
    ctx = blow_ctx(actor, intent.params.get("weapon") or actor.wielded_key(), weapon,
                   defender)
    ctx.update({c: True for c in ATTACK_CHOICES if intent.params.get(c)})
    ctx["own_turn"] = engine.scene.current_ref() == actor.ref
    out.extend(stack(actor._buff_mods("combat_mod", "damage_unmultiplied", ctx)))
    if actor.has_state(HAMMER_THE_GAP) and intent.params.get("full_attack"):
        run = 0
        for b in reversed(state.get("blows") or ()):
            if b.get("ref") != defender.ref or b.get("result") != "hit":
                break
            run += 1
        if run:
            out.append(Modifier(run * mult, f"Hammer the Gap ({run} before)"
                                + (f" x{mult}" if mult > 1 else "")))
    dice = str(state.get("sneak_dice") or "")
    if actor.has_state(KNOCKOUT_ARTIST) and dice and denied_dex \
            and str(lethality) == "nonlethal" \
            and str(weapon.get("name") or "").lower().startswith("unarmed"):
        n = int(dice.split("d")[0] or 0)
        if n:
            out.append(Modifier(n * mult, f"Knockout Artist ({n} dice)"
                                + (f" x{mult}" if mult > 1 else "")))
    return out


def precision_dice(engine, intent, actor, defender, weapon_key, weapon, state, partial) -> list:
    """A held feat's own precision dice (`precision` entries): Precise Strike's "+1d6
    points of precision damage with each successful melee attack" while flanking with an
    ally who has it. Refused where sneak attack is — an immune body, a concealed foe
    (Shadow Strike lets less-than-total through) — by the same readers
    (`Engine._concealment_of`, `precision.immune`). Never multiplied on a critical."""
    from . import classfeatures, feats as feats_mod, precision
    from .dice import Modifier

    entries = []
    for raw in getattr(actor, "feats", None) or ():
        doc = feats_mod.document(raw)
        for e in (doc or {}).get("precision") or ():
            entries.append((doc, e))
    if not entries or precision.immune(defender) or precision.foiled(actor, defender):
        return []
    chance = engine._concealment_of(
        actor, defender, ranged=(weapon or {}).get("category") == "ranged")[0]
    if chance >= 50 or (chance and not actor.has_state(precision.THROUGH_CONCEALMENT)):
        return []
    ctx = blow_ctx(actor, weapon_key, weapon, defender)
    out = []
    for n, (doc, e) in enumerate(entries):
        if not classfeatures.holds(e.get("when"), actor, ctx):
            continue
        key = f"precision_{doc['id']}_{n}"
        if key not in state:
            roll = engine._roll_or_suspend_stage(
                intent, actor, [], f"{doc['name']} ({e['dice']})", None, partial, state,
                str(e["dice"]))
            state[key] = roll.total
            state.setdefault("rolls", []).append(roll.as_dict())
        out.append(Modifier(int(state[key]), f"{doc['name']} ({e['dice']})"))
    return out


# --- declared options (feat loop b3): sheet.ATTACK_CHOICES' last four ---------------------

RAGING = "buff.stance.rage"
FATIGUED = "fatigued"          # the condition Furious Finish leaves, by the table's key
BREATH_BARRED = "state.breath-barred"
GROUNDED = "state.grounded"


def choice_refusal(actor, w: dict, declared, params=None) -> str:
    """Why one of this lane's options cannot ride this swing, or "" (called from
    `Engine._attack_choice_refusal`, after the feat itself is checked held)."""
    if "furious_finish" in declared:
        # Furious Finish (UC): "While raging, when you use the Vital Strike feat".
        if "vital_strike" not in declared:
            return "Furious Finish rides Vital Strike: declare both."
        if not actor.has_state(RAGING):
            return "Furious Finish is used while raging."
    if "pushing_assault" in declared:
        # Pushing Assault (APG): "a two-handed weapon attack modified by the Power Attack
        # feat".
        if not (params or {}).get("power_attack"):
            return "Pushing Assault rides Power Attack: declare both."
        if int(w.get("hands", 1) or 1) < 2 or w.get("category") == "ranged":
            return f"Pushing Assault is a two-handed weapon's, not a {w['name']}'s."
    return ""


def _no_larger(actor, defender) -> bool:
    from .tables import SIZE_ORDER

    order = list(SIZE_ORDER)
    mine = str(getattr(actor, "size", "medium") or "medium").lower()
    theirs = str(getattr(defender, "size", "medium") or "medium").lower()
    return order.index(theirs) <= order.index(mine) if mine in order and theirs in order \
        else True


def power_damage(actor, defender, weapon: dict, choices, power: bool) -> bool:
    """Whether Power Attack's damage rides this blow: not when Pushing Assault trades it
    for the push (APG: "you can choose to push the target 5 feet directly away from you
    instead of dealing the extra damage from Power Attack") at a foe no larger than the
    bearer. Its -1 to hit stands either way."""
    if power and "pushing_assault" in choices and defender is not None \
            and _no_larger(actor, defender):
        return False
    return power


def _breathes(defender) -> bool:
    getter = getattr(defender, "_creature_doc", None)
    doc = (getter() if callable(getter) else None) or {}
    # Squeezed: the corpus's prose breaks words ("breath weapo n", young red dragon).
    return "breathweapon" in "".join(str(doc.get("special_attacks") or "").lower().split())


def _flies(defender) -> bool:
    return bool((defender.movement_modes() or {}).get("fly"))


def crit_trade(engine, actor, defender, weapon, state, choices) -> None:
    """Dragonslayer (Dragonslayer's Handbook): on a confirmed critical against a foe with a
    breath weapon, "forgo the extra critical damage to instead prevent your foe from using
    its breath weapon for a number of rounds equal to twice the critical multiplier".
    Wingclipper (same): against a creature that flies, "prevent it from flying for a
    number of rounds equal to twice the critical multiplier of your attack. Opponents that
    are flying at the time ... must succeed at a DC 20 Fly check to avoid taking falling
    damage". The extra damage goes (`crit_traded`, read where the multiplier is set)."""
    from . import sheet as sheet_mod

    rounds = 2 * int(weapon.get("crit_mult") or 2)
    if "dragonslayer" in choices and _breathes(defender):
        state["crit_traded"] = "dragonslayer"
        defender.apply_effect(ActiveEffect(
            name="breath choked", kind="situation", key="breath choked",
            source=f"{actor.name}'s Dragonslayer", origin="rule:feat-dragonslayer",
            duration="rounds", rounds_left=rounds, tags=(BREATH_BARRED,)))
        _land([{"effect": {"ref": defender.ref, "kind": "situation", "what": "breath barred",
                           "rounds": rounds, "origin": "rule:feat-dragonslayer"},
                "tell": f"{actor.name}'s critical goes for the throat instead of the kill: "
                        f"{defender.name} cannot breathe its fire for {rounds} rounds "
                        f"(Dragonslayer)."}], state)
        return
    if "wingclipper" in choices and _flies(defender):
        state["crit_traded"] = "wingclipper"
        was_aloft = bool(sheet_mod.aloft(defender))
        defender.apply_effect(ActiveEffect(
            name="wings clipped", kind="situation", key="wings clipped",
            source=f"{actor.name}'s Wingclipper", origin="rule:feat-wingclipper",
            duration="rounds", rounds_left=rounds, tags=(GROUNDED,)))
        pieces = [{"effect": {"ref": defender.ref, "kind": "situation", "what": "grounded",
                              "rounds": rounds, "origin": "rule:feat-wingclipper"},
                   "tell": f"{actor.name}'s critical tears at the wing instead: "
                           f"{defender.name} cannot fly for {rounds} rounds (Wingclipper)."}]
        if was_aloft:
            pieces += _fall_or_fly(engine, defender, state)
        _land(pieces, state)


def _fall_or_fly(engine, defender, state) -> list[dict]:
    """A Fly check against DC 20, or down to the floor of its square with 1d6 per 10 feet
    fallen (CRB, Falling: "1d6 points of damage per 10 feet fallen")."""
    roll = engine.dice.d20(defender.skill_modifiers("fly"), label=f"{defender.name}'s Fly "
                           f"(DC 20)", visibility="hidden")
    state.setdefault("rolls", []).append(roll.as_dict())
    if roll.total >= 20:
        return [{"effect": {"ref": defender.ref, "kind": "check", "skill": "fly",
                            "total": roll.total, "dc": 20, "origin": "rule:feat-wingclipper"},
                 "tell": f"{defender.name} glides down under control (Fly {roll.total} "
                         f"against DC 20)."}]
    scene = engine.scene
    spot = scene.positions.get(defender.ref)
    floor = scene.grid.ground(spot) if scene.grid is not None and spot else 0
    feet = max(0, (int(spot[2]) - floor) * 5) if spot and len(spot) > 2 else 0
    scene.positions[defender.ref] = (spot[0], spot[1], floor) if spot else spot
    out = [{"effect": {"ref": defender.ref, "kind": "position", "fell": feet,
                       "origin": "rule:feat-wingclipper"},
            "tell": f"{defender.name} falls {feet} feet (Fly {roll.total} against DC 20)."}]
    dice = feet // 10
    if dice:
        hurt = engine.dice.roll(f"{dice}d6", label=f"Falling ({feet} ft)", visibility="hidden")
        state.setdefault("rolls", []).append(hurt.as_dict())
        hit = engine._apply_damage(defender, max(1, hurt.total), "bludgeoning")
        hit["origin"] = "rule:feat-wingclipper"
        out.append({"effect": hit, "tell": f"The ground takes {hit.get('amount', 0)} from "
                                           f"{defender.name}."})
    return out


def furious_finish(engine, actor, choices, notation: str, state):
    """Furious Finish (UC): "While raging, when you use the Vital Strike feat, you can
    choose not to roll your damage dice and instead deal damage equal to the maximum roll
    possible on those damage dice. If you do, your rage immediately ends, and you are
    fatigued (even if you would not normally be)." The dice total, or None. Run once per
    swing (the damage stage is re-entered on every resume)."""
    import re

    if "furious_finish" not in choices or "vital_strike" not in choices:
        return None
    if "furious_max" in state:
        return state["furious_max"]
    stance = next((e for e in actor.effects if RAGING in e.tags), None)
    if stance is None:
        return None
    top = sum(int(n or 1) * int(m) for n, m in re.findall(r"(\d*)d(\d+)", str(notation)))
    state["furious_max"] = top
    records, said = engine._end_class_stance(actor, stance)
    if not actor.has_state("state.impaired.fatigued"):
        actor.add_condition(FATIGUED, None, source="Furious Finish",
                            origin="rule:feat-furious-finish")
        records.append({"ref": actor.ref, "kind": "condition", "condition": FATIGUED,
                        "origin": "rule:feat-furious-finish"})
    state.setdefault("effects", []).extend(records)
    state.setdefault("tells", []).extend(
        [f"{actor.name} pours the whole rage into the blow: {notation} at its maximum, "
         f"{top} (Furious Finish), and the rage is spent."] + list(said))
    return top


def push_after_hit(engine, actor, defender, choices, state, power) -> list[dict]:
    """Pushing Assault's push, once the hit has landed: 5 feet directly away, 10 on a
    critical, provoking nothing (`Engine._shove`, the one copy of forced movement)."""
    if "pushing_assault" not in choices or not power \
            or defender.is_down or not _no_larger(actor, defender):
        return []
    steps = 2 if state.get("crit") else 1
    moved = 0
    for _ in range(steps):
        if not engine._shove(actor, defender, toward=False):
            break
        moved += 1
    return [{"effect": {"ref": defender.ref, "kind": "position", "pushed": moved * 5,
                        "origin": "rule:feat-pushing-assault"},
             "tell": (f"The blow drives {defender.name} back {moved * 5} feet (Pushing "
                      f"Assault)." if moved else
                      f"{defender.name} has nowhere to be pushed to (Pushing Assault).")}]


def ally_holds(engine, actor, want: dict) -> bool:
    """Whether an ally of `actor` holds `want["state"]` within `within_ft` — or, failing
    that, an ally holding both the state and the feat `far_feat` within `far_ft` who can
    see `actor`. A class ability's `requires_ally` and `self.ends_when.ally` (feat loop b3):
    Sympathetic Rage's "adjacent to an ally who is raging", and Warleader's Rage's "persist
    as long as your ally is within 30 feet of you and can see you". With no board nobody is
    adjacent, and the answer is no — a rage nobody can be shown to stand beside fails
    closed, as flanking does."""
    from . import awareness, feats as feats_mod

    state = str(want.get("state") or "")
    near = int(want.get("within_ft", 5) or 5)
    far_feat = str(want.get("far_feat") or "")
    far = int(want.get("far_ft", 0) or 0)
    for other in engine.scene.actors.values():
        if other is actor or other.is_down or engine._against(actor, other) \
                or not other.has_state(state):
            continue
        gap = engine._gap_ft(actor, other)
        if gap is None:
            continue
        if gap <= near:
            return True
        if far_feat and gap <= far and far_feat in feats_mod._held(other) \
                and awareness.sees(engine.scene, actor, other):
            return True
    return False


# --- casting in an animal's shape (feat loop b3) -------------------------------------------

ANIMAL_FORM = "form.animal"                       # the wild shape document's own tag
SPEAKS_IN_FORM = "casting.form.verbal"            # Wild Speech
CASTS_IN_FORM = "casting.form.natural"            # Natural Spell


def shaped_casting_refusal(actor, spell) -> str:
    """Why a spell cannot be cast in an animal's shape, or "".

    CRB, Druid (wild shape, as beast shape): the druid "loses her ability to speak while
    in animal form"; Natural Spell (CRB): "You can complete the verbal and somatic
    components of spells while using wild shape ... You can also use any material
    components or focuses you possess, even if such items are melded within your current
    form"; Wild Speech (UM): verbal components and speech, "However, it does not give you
    the ability to cast spells requiring somatic components unless you also have the
    Natural Spell feat, or cast spells with material components merged into your form."
    Measured before: a druid shaped as a wolf cast cure light wounds with nothing asked."""
    if not actor.has_state(ANIMAL_FORM):
        return ""
    if actor.has_state(CASTS_IN_FORM):
        return ""
    comps = {str(c).strip().upper() for c in getattr(spell, "components", None) or ()}
    if "V" in comps and not actor.has_state(SPEAKS_IN_FORM):
        return (f"{actor.name} has an animal's throat and cannot speak the words of "
                f"{spell.name} (Natural Spell or Wild Speech would let them). Nothing is "
                f"spent.")
    if "S" in comps:
        return (f"{actor.name} has paws, not hands, for the gestures of {spell.name} "
                f"(Natural Spell would let them). Nothing is spent.")
    if comps & {"M", "F", "DF", "M/DF", "F/DF"}:
        return (f"The components of {spell.name} are melded into {actor.name}'s animal "
                f"shape (Natural Spell would let them use them). Nothing is spent.")
    return ""


# --- companions (feat loop b3) ---------------------------------------------------------------

HANDLES_BIRDS = "handle.birds-of-prey"            # Falconer's Art's Handle Animal half
# Birds of prey (ISWG, Falconer's Art: "such as eagles, falcons, hawks, and owls"): the
# companion catalogue's one bird (eagle, hawk or owl) and the bestiary's raptors by name.
_RAPTORS = ("eagle", "falcon", "hawk", "owl", "kestrel", "osprey")
# Falconer's Art's three bonuses, "chosen at the time this animal companion is gained" —
# the feat's parenthetical on the sheet: Falconer's Art (dodge).
FALCONER_PICKS = {
    "dodge": {"kind": "combat_mod", "target": "ac", "amount": 1, "bonus_type": "dodge"},
    "attack": {"kind": "combat_mod", "target": "attack", "amount": 1, "bonus_type": "morale"},
    "will": {"kind": "save_mod", "target": "will", "amount": 2, "bonus_type": "morale"},
}


def bird_of_prey(animal) -> bool:
    from . import animal_companion

    bond = animal_companion.bond_of(animal)
    if bond is not None and str((bond.payload or {}).get("animal") or "") == "bird":
        return True
    getter = getattr(animal, "_creature_doc", None)
    doc = (getter() if callable(getter) else None) or {}
    words = f"{doc.get('id') or ''} {getattr(animal, 'name', '')}".lower()
    return any(re.search(rf"(?<![a-z]){w}s?(?![a-z])", words) for w in _RAPTORS)


def companion_mods(master, animal_key: str) -> list[dict]:
    """What the master's feats lay on their companion's bond: Falconer's Art (ISWG): "if
    you have a bird of prey as an animal companion, your animal companion gains one of
    the following bonuses chosen at the time this animal companion is gained: a +1 dodge
    bonus to AC, a +1 morale bonus on all attack rolls, or a +2 morale bonus on all Will
    saves" — the sheet's parenthetical names it; none named, none laid."""
    from . import feats as feats_mod

    if str(animal_key or "") != "bird":
        return []
    out = []
    for raw in getattr(master, "feats", None) or ():
        doc = feats_mod.document(raw)
        if not doc or doc["id"] != "falconer-s-art":
            continue
        pick = str(doc.get("target") or "").strip().lower()
        for word, mod in FALCONER_PICKS.items():
            if word in pick:
                out.append(dict(mod, note="Falconer's Art"))
                break
    return out

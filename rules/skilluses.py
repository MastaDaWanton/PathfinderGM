"""Skill uses with their own DC, action and consequence (lane E, 2026-11-22).

docs/implementation-audit-2026-11-22.md §5, lane E: "rows keyed `skill.<skill>.<use>` with
the DC formula, the action cost and the outcome ... resolved through `_op_check` and the one
applicator. Feats target the use id." The rows live in content/rules/skill-uses.json; this
module reads them and resolves the uses the engine had no door for:

  * feint (Bluff): the target denied Dex to AC against the feinter's next melee attack, a
    `state.feinted.<feinter>` tag on an ActiveEffect the attack spends (`feinted`,
    `spend_feint`); Improved Feint makes it a move action and Greater Feint adds
    `state.exposed.feinted` until the feinter's next turn, both read off the standing tags
    a feat document in content/feats/mechanics/skills.json grants;
  * tumble (Acrobatics): one check against each foe's CMD (+2 for each foe after the
    first, +10 at more than half speed), a `movement.unprovoking.<foe>` waiver each foe
    beaten, read by `reactions.provoked_by_move` and spent by the move;
  * monster lore (Knowledge): DC 10 + CR by the type's Knowledge, the facts recalled told
    and nothing else, `knows.creature.<template>` on the one who recalled;
  * long-term care (Heal): `care.long-term` on the patient, read by `Actor.rest`;
  * Dazzling Display (Intimidate): one roll, demoralize every foe within 30 feet who sees.

First aid and stopping bleeding stay in rules/firstaid.py, which was already their door.

Prior art (docs/research/2026-11-22-lane-e.md): Owlcat's Kingmaker kept bonuses able to aim
at one use of a merged skill, which is why the row id is what a feat names; Foundry PF1 and
PCGen model feint only as a context note on the sheet — nothing applies its consequence —
which is the gap this closes. The rules text is the Core Rulebook's, quoted in each row.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .reactions import TUMBLED_PAST as UNPROVOKING

ACTIONS = ("free", "none", "move", "standard", "full-round", "time")

FEINT = "skill.bluff.feint"
TUMBLE = "skill.acrobatics.tumble"
LORE = "skill.knowledge.monster-lore"
CARE = "skill.heal.long-term-care"
DISPLAY = "skill.intimidate.dazzling-display"

# The tags. A feint is per feinter (the ref in the leaf, as `knows.where.<ref>` is), so a
# second attacker's blow finds nothing; Greater Feint's is under `state.exposed`, which
# `Actor.loses_dex_to_ac` already reads for every attacker.
FEINTED = "state.feinted"
EXPOSED_BY_FEINT = "state.exposed.feinted"
KNOWS_CREATURE = "knows.creature"
LORE_TRIED = "lore.tried.creature"
LONG_TERM_CARE = "care.long-term"
FEINT_SOURCE = "rule:feint"
TUMBLE_SOURCE = "rule:tumble"
# Disengaging Feint's document tag (feat loop b2): a feint that buys a step away.
DISENGAGING_FEINT = "skill.bluff.feint.disengaging"

# The check params that send a check to its use's own door (`Engine._op_check`), each
# written by the act table from the reader's closed answers (gm/acts_to_ops.py).
OWN_DOORS = {("bluff", "feint"): "feint", ("acrobatics", "tumble"): "tumble",
             ("heal", "care"): "long_term_care", ("intimidate", "display"): "dazzling_display"}
CHECK_FLAGS = frozenset(flag for _skill, flag in OWN_DOORS)


def _base():
    from django.conf import settings

    return Path(settings.BASE_DIR)


@lru_cache(maxsize=1)
def rows() -> dict[str, dict]:
    """Every row, validated on first load (a bad row is refused with the fix named)."""
    data = json.loads((_base() / "content" / "rules" / "skill-uses.json")
                      .read_text(encoding="utf-8"))
    out = {k: v for k, v in data.items() if not k.startswith("_")}
    problems = validate(out)
    if problems:
        raise ValueError("content/rules/skill-uses.json: " + " | ".join(problems))
    return out


def row(use_id: str) -> dict:
    return rows()[use_id]


def validate(table: dict) -> list[str]:
    """Each row: its id's skill is a skill, its action one of ACTIONS, its formula
    readable with the names it declares, its anchor present."""
    from . import resources
    from .tables import SKILLS

    problems: list[str] = []
    for uid, r in table.items():
        parts = str(uid).split(".")
        if len(parts) != 3 or parts[0] != "skill":
            problems.append(f"{uid}: an id is skill.<skill>.<use>.")
        skill = str(r.get("skill") or "")
        if skill != "knowledge" and skill not in SKILLS:
            problems.append(f"{uid}: skill {skill!r} is not a skill (rules/tables.py SKILLS).")
        if str(r.get("action") or "") not in ACTIONS:
            problems.append(f"{uid}: action is one of {', '.join(ACTIONS)}.")
        if r.get("dc") is not None:
            trouble = resources.check(str(r["dc"]), tuple(r.get("dc_names") or ()))
            if trouble:
                problems.append(f"{uid}.dc: {trouble}")
        anchor = r.get("resolved_by") or {}
        if not anchor.get("file") or not anchor.get("find"):
            problems.append(f"{uid}: resolved_by names the file and a literal piece of it.")
        for t, sk in (r.get("by_type") or {}).items():
            if sk not in SKILLS:
                problems.append(f"{uid}.by_type.{t}: {sk!r} is not a skill.")
    return problems


def dc(use_id: str, subject, **names) -> int:
    """The row's DC, read off the subject's sheet plus what only the reader knows."""
    from . import resources

    r = row(use_id)
    value = resources.evaluate(r["dc"], subject, names or None)
    # A subject whose tag makes the use harder against them, the row's `harder_with`
    # (feat loop b1): Stone-Faced's "the DC for Sense Motive checks to get a hunch about
    # you is 25 rather than 20" — the `faster_with` shape, asked of the subject.
    harder = r.get("harder_with") or {}
    if (harder.get("tag") and getattr(subject, "has_state", None)
            and subject.has_state(harder["tag"])):
        value = max(value, int(harder["dc"]))
    return value


# --- the action a use costs in a fight ------------------------------------------------------

def _action_of(actor, r: dict) -> str:
    faster = r.get("faster_with") or {}
    if faster.get("tag") and actor.has_state(faster["tag"]):
        return str(faster["action"])
    return str(r["action"])


def _no_action_left(engine, actor, action: str, what: str) -> str:
    """Why this actor has no such action left this round, or "". Only in a fight."""
    scene = engine.scene
    if not scene.in_encounter:
        return ""
    name = actor.name
    if action == "move":
        if scene.move_spent.get(actor.ref) == scene.round:
            return f"{name} has already used this turn's move action; {what} is a move action."
    elif action == "standard":
        if scene.standard_spent.get(actor.ref) == scene.round \
                or any(engine._acted_in_batch(actor)):
            return (f"{name} has already used this turn's standard action; {what} is a "
                    f"standard action.")
    elif action == "full-round":
        return engine._coup_round_spent(actor, what)
    elif action in ("swift", "immediate"):
        # The one swift-or-immediate budget (`Engine._swift_refusal`, feat loop b2).
        return engine._swift_refusal(actor, action == "immediate", what)
    return ""


def _spend_action(engine, actor, action: str) -> None:
    """The round's record of the action spent (`Scene.move_spent`/`standard_spent`, the
    drink's and the draw's stores — no counter beside them)."""
    scene = engine.scene
    if not scene.in_encounter:
        return
    if action in ("move", "full-round"):
        scene.move_spent[actor.ref] = scene.round
    if action in ("standard", "full-round"):
        scene.standard_spent[actor.ref] = scene.round
    if action in ("swift", "immediate"):
        engine._spend_swift(actor, action == "immediate")


def _target(engine, intent):
    refs = [r for r in intent.targets() if r and r != intent.actor]
    return engine.scene.actors.get(refs[0]) if refs else None


def _total(mods) -> int:
    from .dice import stack

    return sum(m.value for m in stack(list(mods)))


def _outcome(intent, *, rolls=(), dc_value=None, basis="", verdict=None, margin=None,
             effects=(), tell=""):
    from . import dc as dc_mod
    from .engine import Outcome

    return Outcome(
        intent_id=intent.id, op="check", rolls=list(rolls),
        dc=(dc_mod.ResolvedDC(value=dc_value, band=None, basis=basis).as_dict()
            if dc_value is not None else None),
        verdict=verdict, margin=margin, effects=list(effects), tell=tell,
        because=intent.because)


def _int_score(actor):
    """The Int score, or None for a body that has none (an ooze, a skeleton: Int "—" is
    stored as no key at all, `bestiary._carries_no_coin`). A person of the world with no
    block and no score is a person, not a mindless thing (`deeds._sapient`'s reading)."""
    score = (getattr(actor, "abilities", None) or {}).get("int")
    if score in (None, ""):
        return None if actor._creature_doc() else 10
    try:
        return int(score)
    except (TypeError, ValueError):
        return None


def _humanoid(actor) -> bool:
    """Asked of the type tags (law 1). A body with no type at all is a person of the
    world, as every hand-made townsman is."""
    return actor.has_state("type.humanoid") or not actor.has_state("type")


# --- feint ------------------------------------------------------------------------------------

def feint(engine, intent, actor, mods, partial):
    """Bluff to feint (CRB, Bluff and Combat): the row's DC, its penalties, its action, and
    success as the target denied Dex to AC against the feinter's next melee attack."""
    from .dice import Modifier
    from .activeeffect import ActiveEffect

    r = row(FEINT)
    target = _target(engine, intent)
    if target is None:
        return engine._refuse(intent, f"{actor.name} feints at nobody: a feint is made "
                                      f"against one foe. Nothing is rolled.")
    if not engine.scene.in_encounter:
        return engine._refuse(intent, f"A feint is a move in a fight, and there is no fight "
                                      f"with {target.name}. Nothing is rolled.")
    if target.is_down or target.has_state("state.helpless"):
        return engine._refuse(intent, f"{target.name} has no guard left to draw: a blow at "
                                      f"them already finds no defence. Nothing is rolled.")
    wits = _int_score(target)
    if wits is None or wits <= 0:
        return engine._refuse(intent, f"{target.name} has no mind to fool: a feint against "
                                      f"a creature lacking an Intelligence score is "
                                      f"impossible. Nothing is rolled.")
    action = _action_of(actor, r)
    # Disengaging Feint (UC): "As a standard action, use Bluff to feint ... Instead of
    # denying that opponent his Dexterity bonus to AC, a successful feint allows you to
    # move up to your speed without provoking an attack of opportunity from the opponent
    # you feinted for leaving the square you start in" (feat loop b2).
    disengage = bool(intent.params.get("disengage"))
    if disengage and not actor.has_state(DISENGAGING_FEINT):
        return engine._refuse(intent, f"{actor.name} does not know how to feint to slip "
                                      f"away (Disengaging Feint). Nothing is rolled.")
    if disengage:
        action = "standard"
    spent = _no_action_left(engine, actor, action, "a feint")
    if spent:
        return engine._refuse(intent, spent + " Nothing is rolled.", code="action_spent")
    mods = list(mods)
    pen = r["penalties"]
    if wits <= 2:
        mods.append(Modifier(int(pen["animal_intelligence"]),
                             f"{target.name} has an animal's wits"))
    elif not _humanoid(target):
        mods.append(Modifier(int(pen["non_humanoid"]), f"{target.name} is no humanoid"))
    try:
        trained = target.printed_skill("sense motive") is not None \
            or bool((target.ranks or {}).get("sense motive"))
        sense = _total(target.skill_modifiers("sense motive", ctx={"against": "feint"})) \
            if trained else 0
    except Exception:  # noqa: BLE001 — a sheet with no Sense Motive reads as untrained
        sense = 0
    value = dc(FEINT, target, sense_motive=sense)
    basis = (f"feint: 10 + BAB {target.bab} + Wis {target.ability_mod('wis'):+d}, or 10 + "
             f"Sense Motive {sense:+d} if trained, the higher")
    roll = engine._roll_or_suspend(intent, actor, mods, label="Bluff check (feint)",
                                   dc=value, partial=partial)
    _spend_action(engine, actor, action)
    margin = roll.total - value
    from . import dc as dc_mod

    cost = {"move": " as a move action", "standard": ""}.get(action, "")
    if margin < 0:
        return _outcome(intent, rolls=[roll], dc_value=value, basis=basis,
                        verdict="failure", margin=margin,
                        tell=f"{actor.name} feints at {target.name}{cost} and misses the "
                             f"bluff check by {-margin}: {target.name} is not fooled.")
    out = r["outcome"]
    if disengage:
        # The tumble's own waiver (`movement.unprovoking.<ref>`), which the next move
        # spends: the move's swings are asked of the square it leaves, the one it began in.
        actor.apply_effect(ActiveEffect(
            name=f"slipping away from {target.name}", kind="situation",
            key=f"tumble-{target.ref}", source=TUMBLE_SOURCE, origin="rule:feat-disengaging-feint",
            duration="rounds", rounds_left=1, tags=(f"{UNPROVOKING}.{target.ref}",)))
        return _outcome(intent, rolls=[roll], dc_value=value, basis=basis,
                        verdict="success", margin=margin,
                        effects=[{"ref": actor.ref, "kind": "tumble", "past": target.ref,
                                  "origin": "rule:feat-disengaging-feint"}],
                        tell=f"{actor.name} feints at {target.name} and makes the bluff "
                             f"check{dc_mod.by(margin)}: {target.name} lunges at the "
                             f"opening, and {actor.name} can step away without a swing "
                             f"from them.")
    target.apply_effect(ActiveEffect(
        name=f"feinted by {actor.name}", kind="situation", key=f"feinted-by-{actor.ref}",
        source=FEINT_SOURCE, origin="rule:feint", duration="rounds",
        # shortcut: the round ticker runs at the top of the round, so 2 lasts through the
        # feinter's next turn and a little past it; a per-turn clock would end it exactly.
        rounds_left=int(out["rounds"]), tags=(f"{FEINTED}.{actor.ref}",),
        payload={"by": actor.ref,
                 **({"until_hit": True} if actor.has_state(RAGE_STANCE)
                    and actor.has_state(unforbidden_tag("bluff", "feint")) else {})}))
    effects = [{"ref": target.ref, "kind": "condition", "condition": "feinted",
                "by": actor.ref, "origin": "rule:feint"}]
    said = (f"{actor.name} feints at {target.name}{cost} and makes the bluff "
            f"check{dc_mod.by(margin)}: {target.name}'s guard is drawn, and {actor.name}'s "
            f"next melee attack on them, this turn or the next, finds them without their "
            f"Dexterity to their defence.")
    partners = _feint_partners(engine, actor)
    for ally in partners:
        # Feint Partner (UC): "Whenever an ally who also has this feat successfully feints
        # an opponent, that opponent also loses his Dexterity bonus to AC against the next
        # attack you make against him before the end of the feinting ally's next turn" —
        # the same per-feinter tag, in the partner's name, for the same rounds.
        target.apply_effect(ActiveEffect(
            name=f"feinted for {ally.name}", kind="situation", key=f"feinted-by-{ally.ref}",
            source=FEINT_SOURCE, origin="rule:feat-feint-partner", duration="rounds",
            rounds_left=int(out["rounds"]), tags=(f"{FEINTED}.{ally.ref}",),
            payload={"by": ally.ref, "partner_of": actor.ref}))
        effects.append({"ref": target.ref, "kind": "condition", "condition": "feinted",
                        "by": ally.ref, "origin": "rule:feat-feint-partner"})
    if partners:
        said += (f" Feint Partner: {_and(p.name for p in partners)}'s next blow at "
                 f"{target.name} finds the same opening.")
    if actor.has_state(out["greater_tag"]):
        target.apply_effect(ActiveEffect(
            name=f"off guard from {actor.name}'s feint", kind="situation",
            key=f"exposed-by-{actor.ref}", source=FEINT_SOURCE, origin="rule:greater-feint",
            duration="rounds", rounds_left=int(out["greater_rounds"]),
            tags=(EXPOSED_BY_FEINT,), payload={"by": actor.ref}))
        effects.append({"ref": target.ref, "kind": "condition", "condition": "exposed",
                        "by": actor.ref, "origin": "rule:greater-feint"})
        said += (f" Greater Feint: until {actor.name}'s next turn {target.name} keeps no "
                 f"Dexterity against anybody.")
    return _outcome(intent, rolls=[roll], dc_value=value, basis=basis, verdict="success",
                    margin=margin, effects=effects, tell=said)


# Feint Partner's tag (content/feats/mechanics/batch1-maneuvers.json), a teamwork feat:
# the feinter and the ally must both hold it.
FEINT_PARTNER = "teamwork.feint-partner"


def _feint_partners(engine, actor) -> list:
    """The feinter's allies in this fight who share Feint Partner with them."""
    from .position import _same_side

    scene = engine.scene
    if not actor.has_state(FEINT_PARTNER) or not (getattr(scene, "sides", None) or {}):
        return []
    return [o for ref, o in scene.actors.items()
            if ref != actor.ref and not o.is_down and o.has_state(FEINT_PARTNER)
            and _same_side(scene, actor.ref, ref)]


def _and(names) -> str:
    names = list(names)
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def feinted(defender, attacker, weapon: dict | None) -> bool:
    """Whether this blow is the feinter's next melee attack on a creature it feinted — or,
    for a Feint Partner's opening, the partner's next attack of any kind ("the next
    attack you make against him", UC)."""
    if defender is None or attacker is None or not weapon:
        return False
    tag = f"{FEINTED}.{attacker.ref}"
    if weapon.get("category") == "ranged" or weapon.get("thrown"):
        return any(tag in (e.tags or ()) and (e.payload or {}).get("partner_of")
                   for e in defender.effects)
    return defender.has_state(tag)


def spend_feint(defender, attacker, landed: bool = False) -> None:
    """The feint is used up by the attack that read it (Greater Feint's exposure stays
    its round: it is against everybody, not against the next blow). A raging feint made
    with Tantrum "lasts only until the first time you hit the target" (Gnomes of
    Golarion): its effect carries `until_hit`, and only a blow that landed spends it."""
    tag = f"{FEINTED}.{attacker.ref}"
    defender.remove_effects(match=lambda e: tag in (e.tags or ()) and (
        landed or not (e.payload or {}).get("until_hit")))


# A skill use let through an effect's ban on its skill (`Engine._forbidden_skill`):
# `skill.unforbidden.<skill>.<use>`. Tantrum's (content/feats/mechanics/batch1-
# maneuvers.json): "You may use the Bluff skill to feint while raging", which rage's ban on
# Charisma skills otherwise refuses; and its raging feint lasts until a blow lands.
UNFORBIDDEN = "skill.unforbidden"
RAGE_STANCE = "buff.stance.rage"


def unforbidden_tag(skill: str, use: str) -> str:
    return f"{UNFORBIDDEN}.{'-'.join(str(skill).strip().lower().split())}.{use}"


# --- tumble -----------------------------------------------------------------------------------

def _armour_slows(actor) -> bool:
    """Medium or heavy armour that slows this body (armour training lifts it), the
    Acrobatics refusal's own clause. Load is not modelled, so it is not asked."""
    suit = actor.armour_stats()
    weight = suit.get("move_weight", suit.get("weight"))
    return weight in ("medium", "heavy") and weight not in actor._armour_training()["unhindered"]


def tumble(engine, intent, actor, mods, partial):
    """Acrobatics to move through threatened squares without provoking (CRB, Acrobatics).

    One roll, set against each foe whose reach the move leaves: that foe's CMD, +2 for
    each foe already avoided this move (cheapest first, the reading kindest to the
    tumbler), +10 when the move runs past half speed. Each foe beaten gets a waiver tag on
    the tumbler (`movement.unprovoking.<ref>`) that `reactions.provoked_by_move` asks and
    the move spends; a foe not beaten swings as normal. The move itself is the next intent
    (`acts_to_ops` builds the two together)."""
    from . import grid as gridmod
    from . import reactions
    from .activeeffect import ActiveEffect
    from .dice import Modifier

    r = row(TUMBLE)
    scene = engine.scene
    square = intent.params.get("square")
    start = scene.positions.get(actor.ref)
    if not scene.in_encounter or not scene.has_grid or start is None or not square:
        return engine._refuse(intent, f"There is no foe's reach for {actor.name} to tumble "
                                      f"past here. Nothing is rolled.")
    if _armour_slows(actor):
        return engine._refuse(intent, f"{actor.name}'s armour slows them, and nobody can "
                                      f"tumble past foes in armour that does. Nothing is "
                                      f"rolled; the move provokes as any move does.")
    # Who would swing at this move, asked before any waiver is laid.
    watchers = [w for w, _ in reactions.provoked_by_move(scene, actor.ref, tuple(start),
                                                          tuple(square))]
    watchers = list(dict.fromkeys(watchers))
    if not watchers:
        return _outcome(intent, tell=f"{actor.name} moves without passing through anybody's "
                                     f"reach; there is nothing to tumble past.")
    far = gridmod.distance(tuple(start)[:2], tuple(square)[:2]) > actor.speed_feet // 2
    foes = sorted((scene.actors[w] for w in watchers if w in scene.actors),
                  key=lambda f: f.cmd())
    dcs = [(f, dc(TUMBLE, f, cmd=f.cmd(), avoided=i, full_speed=int(far)))
           for i, f in enumerate(foes)]
    hardest = max(v for _, v in dcs)
    roll = engine._roll_or_suspend(
        intent, actor, list(mods), label="Acrobatics check (tumble)", dc=hardest,
        partial=partial)
    rounds = int(r["outcome"]["rounds"])
    past, caught, effects = [], [], []
    for foe, value in dcs:
        # A term against THIS foe (feat loop b2): Underfoot's "+4 dodge bonus on Acrobatics
        # checks to move past opponents ... so long as they are larger than you", read with
        # the foe in the context (`when.target.larger`), so it lands on their DC alone.
        # The difference the foe makes, so a term that asks only the use (already in
        # `mods`) is not counted twice.
        against = sum(m.value for m in actor._feat_mods(
            "skill_mod", "acrobatics", {"skill_use": "tumble", "target_actor": foe},
            scoped=True)) - sum(m.value for m in actor._feat_mods(
                "skill_mod", "acrobatics", {"skill_use": "tumble"}, scoped=True))
        if roll.total + against >= value:
            actor.apply_effect(ActiveEffect(
                name=f"tumbling past {foe.name}", kind="situation", key=f"tumble-{foe.ref}",
                source=TUMBLE_SOURCE, origin="rule:tumble", duration="rounds",
                rounds_left=rounds, tags=(f"{UNPROVOKING}.{foe.ref}",)))
            past.append(foe.name)
            effects.append({"ref": actor.ref, "kind": "tumble", "past": foe.ref,
                            "dc": value, "origin": "rule:tumble"})
        else:
            caught.append(foe.name)
    pace = " at full speed (+10 to the DC)" if far else ""
    bits = [f"{actor.name} tumbles{pace}: Acrobatics {roll.total}."]
    if past:
        bits.append(f"Slips past {', '.join(past)} without opening a guard.")
    if caught:
        bits.append(f"Not quick enough past {', '.join(caught)}, who "
                    + ("gets a swing." if len(caught) == 1 else "get their swings."))
    return _outcome(intent, rolls=[roll], dc_value=hardest,
                    basis="tumble: each foe's CMD, +2 per foe after the first"
                          + (", +10 at full speed" if far else ""),
                    verdict="success" if not caught else "failure",
                    margin=roll.total - hardest, effects=effects, tell=" ".join(bits))


def waives(mover, watcher_ref: str) -> bool:
    """Whether a tumble got this mover past this watcher's swing."""
    return mover.has_state(f"{UNPROVOKING}.{watcher_ref}")


def spend_tumble(mover) -> None:
    """A tumble covers the one move it was rolled for."""
    mover.remove_effects(source=TUMBLE_SOURCE)


# --- monster lore -----------------------------------------------------------------------------

def lore_skill(creature) -> str:
    """The Knowledge that identifies this creature, by its type (the row's table)."""
    from . import bestiary

    doc = creature._creature_doc() if hasattr(creature, "_creature_doc") else None
    kind = str((doc or {}).get("creature_type") or "").strip().lower()
    if not kind:
        for t, _sk in row(LORE)["by_type"].items():
            if creature.has_state("type." + t.replace(" ", "-")):
                kind = t
                break
    if not kind and not getattr(creature, "from_template", "") and not bestiary.body_size(creature):
        kind = "humanoid"
    return row(LORE)["by_type"].get(kind or "humanoid", "knowledge (local)")


def is_lore_subject(engine, intent, actor) -> bool:
    """A Knowledge check aimed at a creature here, other than the checker: monster lore,
    whatever Knowledge the plan named (the creature's type picks it)."""
    if not str(intent.params.get("skill") or "").startswith("knowledge"):
        return False
    target = _target(engine, intent)
    return target is not None and not target.is_pc and target is not actor


def _cr_of(creature) -> int:
    doc = creature._creature_doc() if hasattr(creature, "_creature_doc") else None
    try:
        cr = float((doc or {}).get("cr_value") or 0)
    except (TypeError, ValueError):
        cr = 0.0
    if not cr:
        cr = float(max(1, getattr(creature, "hit_dice", 1) or 1)) - 1 or 0.5
    return int(cr)                      # CR 1/2 and below add nothing: DC 10


def _facts(creature) -> list[str]:
    """What there is to know about it, most useful first — read off the engine's own
    structured record of the creature (never its prose), so each fact told is one the
    engine acts on."""
    doc = creature._creature_doc() or {}
    name = str(doc.get("name") or creature.name)
    kind = str(doc.get("creature_type") or "").strip()
    sub = str(doc.get("subtype") or "").strip()
    out = []
    if kind:
        out.append(f"a {name} is {('an ' if kind[0] in 'aeiou' else 'a ') + kind}"
                   + (f" ({sub})" if sub else ""))
    saves = doc.get("flat_saves") or {}
    if saves:
        weak = min(saves, key=lambda k: saves[k])
        out.append({"fort": "its body is the weak point: it resists poison, sickness and "
                            "brute force poorly",
                    "ref": "it is slow to dodge: blasts and traps catch it",
                    "will": "its mind is the weak point: charms and fear take hold of it "
                            "easily"}[weak])
    for dr in doc.get("reductions") or ():
        if isinstance(dr, dict) and dr.get("amount"):
            by = str(dr.get("bypass") or "").strip()
            out.append(f"blows glance off it unless they are {by}" if by and by != "-"
                       else "it shrugs off part of every blow")
    imm = [str(x) for x in (doc.get("immune") or ()) if str(x).strip()]
    if imm:
        out.append(f"it cannot be hurt by {', '.join(imm)}")
    res = [str(x) for x in (doc.get("resist") or ()) if str(x).strip()]
    if res:
        out.append(f"it resists {', '.join(res)}")
    senses = str(doc.get("senses") or "").split(";")[0].strip()
    if senses:
        out.append(f"its senses: {senses}")
    return out


def monster_lore(engine, intent, actor, mods, partial):
    """Knowledge to identify a creature (CRB, Knowledge): DC 10 + CR in the type's
    Knowledge, one useful fact and one more per 5 over; no retry. Only the facts recalled
    reach the tell, so the narrator is fed what the character now knows and nothing
    else (law 3), and the knowing is a tag on the one who recalled."""
    from .activeeffect import ActiveEffect
    from .sheet import IllegalSheet
    from . import dc as dc_mod

    target = _target(engine, intent)
    skill = lore_skill(target)
    template = str(target.from_template or target.ref).strip().lower()
    if actor.has_state(f"{KNOWS_CREATURE}.{template}") \
            or actor.has_state(f"{LORE_TRIED}.{template}"):
        return engine._refuse(intent, f"{actor.name} has already searched their memory for "
                                      f"what they know of {target.name}; thinking on it "
                                      f"again teaches nothing new. Nothing is rolled.",
                              code="no_retry")
    value = dc(LORE, target, cr=_cr_of(target))
    try:
        # The creature recalled is what the check is about: Demonologist's "+2 bonus on
        # all Knowledge checks related to ... demons" and Demon Hunter's "+2 on Knowledge
        # (planes) checks to know the powers and abilities of demons" ask `when.target` of it.
        mods = actor.skill_modifiers(skill, ctx={"target_actor": target})
    except IllegalSheet:
        if value > 10:
            return engine._refuse(intent, f"{actor.name} has no training in {skill.title()}, "
                                          f"and nothing beyond common knowledge (DC 10) can "
                                          f"be recalled untrained. Nothing is rolled.")
        mods = actor.ability_check_modifiers("int")
    roll = engine._roll_or_suspend(intent, actor, list(mods),
                                   label=f"{skill.title()} check", dc=value, partial=partial)
    margin = roll.total - value
    basis = f"identify a creature: 10 + CR {_cr_of(target)}, {skill.title()}"
    if margin < 0:
        actor.apply_effect(ActiveEffect(
            name=f"tried to recall {target.name}", kind="knowledge",
            key=f"lore-tried-{template}", source="rule:monster-lore",
            origin="rule:monster-lore", tags=(f"{LORE_TRIED}.{template}",)))
        return _outcome(intent, rolls=[roll], dc_value=value, basis=basis,
                        verdict="failure", margin=margin,
                        effects=[{"ref": actor.ref, "kind": "lore", "of": template,
                                  "facts": 0}],
                        tell=f"{actor.name} misses the {skill} check by {-margin}: nothing "
                             f"useful about {target.name} comes to mind.")
    facts = _facts(target)
    known = facts[:max(1, 1 + margin // 5)]
    actor.apply_effect(ActiveEffect(
        name=f"knows {target.name}", kind="knowledge", key=f"knows-{template}",
        source="rule:monster-lore", origin="rule:monster-lore",
        tags=(f"{KNOWS_CREATURE}.{template}",), payload={"facts": known}))
    said = "; ".join(known) if known else f"{target.name} is nothing out of the ordinary"
    return _outcome(intent, rolls=[roll], dc_value=value, basis=basis, verdict="success",
                    margin=margin,
                    effects=[{"ref": actor.ref, "kind": "lore", "of": template,
                              "facts": len(known)}],
                    tell=f"{actor.name} makes the {skill} check{dc_mod.by(margin)} and "
                         f"recalls: {said}.")


# --- long-term care ---------------------------------------------------------------------------

def long_term_care(engine, intent, actor, mods, partial):
    """Heal's long-term care (CRB, Heal): DC 15, never on yourself, at most six patients;
    made, the patient heals at twice the rate for the next full night's rest
    (`care.long-term`, read by `Actor.rest` and spent by it)."""
    from .activeeffect import ActiveEffect
    from . import dc as dc_mod

    r = row(CARE)
    patient = _target(engine, intent)
    if patient is None or patient is actor:
        return engine._refuse(intent, f"{actor.name} cannot give long-term care to "
                                      f"themselves; it is given to somebody else. Nothing "
                                      f"is rolled.")
    tending = [a for a in engine.scene.actors.values()
               if any(e.source == "rule:long-term-care"
                      and (e.payload or {}).get("by") == actor.ref for e in a.effects)]
    if len(tending) >= int(r["outcome"]["most_patients"]) and patient not in tending:
        return engine._refuse(intent, f"{actor.name} already tends six patients, as many as "
                                      f"anybody can. Nothing is rolled.")
    value = dc(CARE, patient)
    roll = engine._roll_or_suspend(intent, actor, list(mods), label="Heal check (long-term "
                                   "care)", dc=value, partial=partial)
    margin = roll.total - value
    if margin < 0:
        return _outcome(intent, rolls=[roll], dc_value=value, verdict="failure",
                        margin=margin,
                        tell=f"{actor.name} misses the heal check by {-margin}: their care "
                             f"does {patient.name} no more good than rest alone.")
    patient.apply_effect(ActiveEffect(
        name=f"under {actor.name}'s care", kind="situation", key="long-term-care",
        source="rule:long-term-care", origin="rule:long-term-care",
        tags=(LONG_TERM_CARE,), payload={"by": actor.ref}))
    return _outcome(intent, rolls=[roll], dc_value=value, verdict="success", margin=margin,
                    effects=[{"ref": patient.ref, "kind": "condition",
                              "condition": "long-term care", "by": actor.ref,
                              "origin": "rule:long-term-care"}],
                    tell=f"{actor.name} makes the heal check{dc_mod.by(margin)}: under their "
                         f"care {patient.name} will heal twice as fast through the next "
                         f"full night's rest.")


# --- Dazzling Display -------------------------------------------------------------------------

def _focus_in_hand(actor) -> bool:
    """Weapon Focus in the weapon this body swings now (`wielded_key`)."""
    from . import feats as feats_mod
    from . import weapons as weapons_mod

    held = actor.wielded_key()
    for raw in actor.feats or ():
        doc = feats_mod.document(raw) or {}
        if doc.get("id") == "weapon-focus" and \
                weapons_mod.key_for(str(doc.get("target") or "")) == held:
            return True
    return False


# Motivating Display's tag (its feat document, feat loop b1).
MOTIVATES = "skill.intimidate.motivating-display"


def _motivate(engine, actor, total: int, side, range_ft: int):
    """Motivating Display (Blood of the Moon): "your Intimidate check while using Dazzling
    Display also applies to allies within 30 feet who can see you. The DC for this effect
    is the same as it would be to demoralize your allies. Each ally so affected gains a +1
    morale bonus on attack rolls and skill checks for the duration that it would normally
    be shaken" — Demoralize's 1 round + 1 per 5 over (`Engine._demoralize`), one effect per
    ally on the one ticker, morale-typed so it takes the best with other morale."""
    from . import attitude as attitude_mod
    from . import awareness
    from .activeeffect import ActiveEffect

    scene = engine.scene
    said, effects = [], []
    for ref in (scene.sides or {}).get(side, ()) if side else ():
        ally = scene.actors.get(ref)
        if ally is None or ally is actor or ally.is_down \
                or not awareness.sees(scene, ally, actor):
            continue
        gap = engine._gap_ft(actor, ally)
        if gap is not None and gap > range_ft:
            continue
        margin = total - attitude_mod.intimidate_dc(ally)
        if margin < 0:
            continue
        rounds = 1 + margin // 5
        ally.apply_effect(ActiveEffect(
            name="motivated", kind="buff", key="motivating-display",
            source=f"{actor.name}'s Motivating Display",
            origin="rule:feat-motivating-display", duration="rounds", rounds_left=rounds,
            modifiers=[{"kind": "combat_mod", "target": "attack", "amount": 1,
                        "bonus_type": "morale"},
                       {"kind": "skill_mod", "target": "all", "amount": 1,
                        "bonus_type": "morale"}]))
        effects.append({"ref": ally.ref, "kind": "buff", "buff": "motivated",
                        "rounds": rounds, "origin": "rule:feat-motivating-display"})
        said.append(f"{ally.name} takes heart from it: +1 morale on attacks and skill "
                    f"checks for {rounds} round{'s' if rounds != 1 else ''}.")
    return said, effects


def dazzling_display(engine, intent, actor, mods, partial):
    """Dazzling Display (CRB): a full-round action wielding the Weapon Focus weapon; one
    Intimidate check demoralizes every foe within 30 feet who can see it, each against
    its own DC (10 + HD + Wis), through the one Demoralize door (`Engine._demoralize`)."""
    from . import attitude as attitude_mod
    from . import awareness

    r = row(DISPLAY)
    scene = engine.scene
    if not actor.has_state(r["needs_tag"]):
        return engine._refuse(intent, f"{actor.name} does not have the Dazzling Display feat. "
                                      f"Nothing is rolled.")
    if not scene.in_encounter:
        return engine._refuse(intent, "A dazzling display is made in a fight, at foes; there "
                                      "is no fight here. Nothing is rolled.")
    if not _focus_in_hand(actor):
        return engine._refuse(intent, f"{actor.name} is not wielding the weapon they have "
                                      f"Weapon Focus in, and the display is made with it. "
                                      f"Nothing is rolled.")
    spent = _no_action_left(engine, actor, "full-round", "a dazzling display")
    if spent:
        return engine._refuse(intent, spent, code="action_spent")
    side = next((s for s, refs in (scene.sides or {}).items() if actor.ref in refs), None)
    foes = [a for s, refs in (scene.sides or {}).items() if s != side
            for a in (scene.actors.get(x) for x in refs)
            if a is not None and not a.is_down and awareness.sees(scene, a, actor)
            and ((engine._gap_ft(actor, a) is None) or engine._gap_ft(actor, a)
                 <= int(r["range_ft"]))]
    if not foes:
        return engine._refuse(intent, f"No foe within {r['range_ft']} feet can see "
                                      f"{actor.name}'s display. Nothing is rolled.")
    hardest = max(attitude_mod.intimidate_dc(f) for f in foes)
    roll = engine._roll_or_suspend(intent, actor, list(mods),
                                   label="Intimidate check (Dazzling Display)", dc=hardest,
                                   partial=partial)
    _spend_action(engine, actor, "full-round")
    bits = [f"{actor.name} makes a dazzling display with their weapon: Intimidate "
            f"{roll.total}."]
    effects: list[dict] = []
    for f in foes:
        said, fx = engine._demoralize(actor, f, roll.total - attitude_mod.intimidate_dc(f), "")
        bits.append(said)
        effects.extend(fx)
    if actor.has_state(MOTIVATES):
        said, fx = _motivate(engine, actor, roll.total, side, int(r["range_ft"]))
        bits.extend(said)
        effects.extend(fx)
    return _outcome(intent, rolls=[roll], dc_value=hardest,
                    basis="Dazzling Display: each foe's 10 + Hit Dice + Wis",
                    verdict="success" if effects else "failure",
                    margin=roll.total - hardest, effects=effects, tell=" ".join(bits))


# =============================================================================================
# Round 2 (skills-mind lane, 2026-11-22): the mind, social and knowledge skills
# =============================================================================================
#
# The rows are content/rules/skill-uses.json's; the rules text each quotes is the CRB's
# (d20pfsrd.com/skills/<skill>, read 2026-11-22). docs/research/2026-11-22-skills-mind.md
# has the prior art and what was left honestly not built: Linguistics (no language is ever
# a barrier in this game and no foreign or forged writing exists), Use Magic Device (no
# wand or scroll exists), Handle Animal (a companion obeys in character, the owner's
# ruling of 2026-10-01).

HUNCH = "skill.sense-motive.hunch"
ENCHANTMENT = "skill.sense-motive.enchantment"
LIE = "skill.sense-motive.lie"
ANSWER = "skill.knowledge.answer"
APPRAISE = "skill.appraise.value"
CASTING = "skill.spellcraft.identify-casting"
ITEM = "skill.spellcraft.identify-item"
PERFORM = "skill.perform.for-coin"

# What the reads leave on the reader (law 1: asked with has_state, never matched).
SENSED = "knows.sensed"                  # .<ref>: a read made today; "Retry? No"
KNOWS_LYING = "knows.lying"              # .<ref>: caught keeping something back
KNOWS_ENCHANTED = "knows.enchanted"      # .<ref>: seen to be under a spell's sway
KNOWS_LORE = "knows.lore"                # .<topic>.<field>: recalled
LORE_TRIED_TOPIC = "lore.tried.topic"    # .<topic>.<field>: tried and nothing came back
ROUNDS_A_DAY = 14400


def _slug(text: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-") or "thing"


def door_for(intent, actor, skill: str):
    """The round-2 door a player's own check of this skill takes, or None for the plain
    check. Each door reads its subject off the intent (its target, `item`, `about`) and
    refuses with the fix named when there is none to read."""
    if not getattr(actor, "is_pc", False):
        return None
    skill = str(skill or "").strip().lower()
    if skill == "sense motive":
        return sense_motive
    if skill == "appraise":
        return appraise
    if skill == "perform":
        return perform_for_coin
    if skill == "spellcraft" and intent.params.get("item"):
        return identify_item
    return None


def asks_the_world(intent) -> bool:
    """A Knowledge check about something the world's record names (`about`), not about a
    creature standing here: answered by `knowledge_answer`."""
    return str(intent.params.get("skill") or "").lower().startswith("knowledge") \
        and bool(str(intent.params.get("about") or "").strip())


# --- Sense Motive -----------------------------------------------------------------------------

_DOMINATING = frozenset({"dominate-person", "dominate-monster", "dominate-animal"})


def _enchanted_by(target):
    """(the spell, dominated) of an enchantment on this body, or (None, False). Read off
    the effect's own provenance stamp (`ActiveEffect.origin` = `spell:<id>`, written only
    by a door) and the spell's school, never the condition's words: charm person lands as
    an `attitude.*` step that a Diplomacy roll could have made too."""
    from . import spells as spells_mod

    best = None
    for e in getattr(target, "effects", ()) or ():
        origin = str(getattr(e, "origin", "") or "")
        if not origin.startswith("spell:"):
            continue
        sid = origin.split(":", 1)[1]
        try:
            spell = spells_mod.get(sid)
        except KeyError:
            continue
        if str(spell.school or "").lower() != "enchantment":
            continue
        if sid in _DOMINATING:
            return spell, True
        best = best or spell
    return best, False


def sense_motive(engine, intent, actor, mods, partial):
    """The player's own Sense Motive (CRB, Sense Motive), one read of one person:

      * set against that person's Bluff when the engine knows they are keeping something
        from the player (`schemes.keeps_secret`: a live secret card's `kept_by`, authored
        in the scheme document, never a model's word that somebody lied);
      * against DC 25 (15 if dominated) when a spell of enchantment holds them, read off
        the effect's own `spell:` stamp;
      * else a hunch, DC 20: whether they are what they seem.

    One roll answers all three. "Retry? No" (one read of a person a day,
    `knows.sensed.<ref>`). Made, the knowing is a tag on the reader (`knows.lying.<ref>`,
    `knows.enchanted.<ref>`), and the tell says what was read and nothing more: never
    what the secret is, which stays the GM's card. Failed, or out-bluffed, the book gives
    no read at all, and the tell is the same either way: a lie that held reads exactly as
    nothing to find."""
    from .activeeffect import ActiveEffect
    from . import schemes as schemes_mod

    target = _target(engine, intent)
    if target is None or target.is_pc:
        return engine._refuse(intent, f"{actor.name} names nobody to read: a Sense Motive is "
                                      f"made on one person here. Nothing is rolled.")
    if actor.has_state(f"{SENSED}.{target.ref}"):
        return engine._refuse(intent, f"{actor.name} has already read {target.name} today; "
                                      f"looking again tells nothing new. Nothing is rolled.",
                              code="no_retry")
    spell, dominated = _enchanted_by(target)
    hiding = schemes_mod.keeps_secret(engine.scene, target.ref)
    hunch = dc(HUNCH, target)
    roll = engine._roll_or_suspend(intent, actor, list(mods),
                                   label=f"Sense Motive check (reading {target.name})",
                                   dc=hunch, partial=partial, dc_shown=False)
    actor.apply_effect(ActiveEffect(
        name=f"read {target.name}", kind="knowledge", key=f"sensed-{target.ref}",
        source="rule:sense-motive", origin="rule:sense-motive", duration="rounds",
        rounds_left=ROUNDS_A_DAY, tags=(f"{SENSED}.{target.ref}",)))
    rolls, effects, said = [roll], [], []
    verdict, margin, dc_value, basis = "failure", None, hunch, "a hunch: DC 20"
    if hiding:
        try:
            bluff = target.skill_modifiers("bluff", opposed=True)
        except Exception:  # noqa: BLE001 — a body with no Bluff on its sheet bluffs at +0
            bluff = []
        # Rolled after the player's own die, so a resumed check never rolls it twice.
        theirs = engine.dice.d20(list(bluff), label=f"{target.name}'s Bluff (keeping it "
                                                    f"back)", visibility="hidden")
        rolls.append(theirs)
        margin = roll.total - theirs.total
        dc_value, basis = theirs.total, f"against {target.name}'s Bluff"
        if margin >= 0:
            verdict = "success"
            actor.apply_effect(ActiveEffect(
                name=f"knows {target.name} is keeping something back", kind="knowledge",
                key=f"lying-{target.ref}", source="rule:sense-motive",
                origin="rule:sense-motive", tags=(f"{KNOWS_LYING}.{target.ref}",)))
            effects.append({"ref": actor.ref, "kind": "knowledge", "of": target.ref,
                            "tag": f"{KNOWS_LYING}.{target.ref}",
                            "origin": "rule:sense-motive"})
            said.append(f"{target.name} is not telling {actor.name} the whole truth: "
                        f"something about the matter is being kept back")
    if spell is not None:
        need = dc(ENCHANTMENT, target, dominated=int(dominated))
        if roll.total >= need:
            verdict = "success"
            actor.apply_effect(ActiveEffect(
                name=f"knows {target.name} is under a spell", kind="knowledge",
                key=f"enchanted-{target.ref}", source="rule:sense-motive",
                origin="rule:sense-motive", tags=(f"{KNOWS_ENCHANTED}.{target.ref}",)))
            effects.append({"ref": actor.ref, "kind": "knowledge", "of": target.ref,
                            "tag": f"{KNOWS_ENCHANTED}.{target.ref}",
                            "origin": "rule:sense-motive"})
            said.append(f"{target.name} is not acting of their own will: "
                        + ("something has hold of them, and they do as they are bid"
                           if dominated else "a spell has turned how they feel"))
        if margin is None:
            margin, dc_value = roll.total - need, need
            basis = ("sense enchantment: DC 15, dominated" if dominated
                     else "sense enchantment: DC 25")
    if not hiding and spell is None:
        margin = roll.total - hunch
        if margin >= 0:
            verdict = "success"
            said.append(f"nothing in {target.name}'s manner is off: as far as {actor.name} "
                        f"can read them, they are what they seem")
    tell = (f"{actor.name} reads {target.name}: " + "; ".join(said) + "." if said else
            f"{actor.name} watches {target.name} closely and reads nothing either way.")
    return _outcome(intent, rolls=rolls, dc_value=dc_value, basis=basis, verdict=verdict,
                    margin=margin, effects=effects, tell=tell)


# --- Knowledge: answering a question from the world's own record -----------------------------

def topic_in(world, about: str, here: str = ""):
    """The world's best match for the words, or None. Found by the world's own index
    (play/gm_search.py, BM25 over the export), so every name in an answer is the world's:
    a question the record has no words for finds nothing, and nothing is rolled. "Here"
    and "this town" are the settlement the party stands in (`here`, the scene's
    location), as the /gm door reads them. `world` None is the loaded campaign's."""
    from play import gm_search
    from . import residency

    world = residency._world(world)
    about = " ".join(str(about or "").split())
    if world is None or not about:
        return None
    entity = world.get(here) if here and gm_search.asks_about_here(about) else None
    if entity is not None:
        name, kind, facts, text = entity.name, entity.kind, dict(entity.facts or {}), ""
        tid = entity.id
    else:
        hits = gm_search.search(world, about, limit=1)
        if not hits:
            return None
        h = hits[0]
        entity = world.get(h.entity_id) if h.entity_id else None
        name, kind, facts, text = h.name, getattr(entity, "kind", "") or h.kind, \
            dict(h.facts or {}), str(h.text or "")
        tid = h.entity_id or _slug(f"{h.kind}-{h.name}")
    return {"id": tid, "name": name, "kind": str(kind or "").lower(), "facts": facts,
            "text": text, "summary": str(getattr(entity, "summary", "") or "")}


def _topic(engine, about: str):
    return topic_in(getattr(engine, "world", None), about,
                    str(getattr(engine.scene, "location_id", "") or ""))


def _field_of(key: str, kind: str) -> str:
    r = row(ANSWER)
    k = " ".join(str(key or "").split()).lower()
    return r["fields"].get(k) or r["by_kind"].get(kind) or r["by_kind"]["_default"]


def _first(text: str, cap: int = 240) -> str:
    """The first sentence of a fact, at most `cap` characters: a recalled answer, not
    the record read out."""
    import re

    t = " ".join(str(text or "").split())
    m = re.match(r"(.+?[.!?])(\s|$)", t)
    t = m.group(1) if m else t
    return t if len(t) <= cap else t[:cap].rsplit(" ", 1)[0] + "…"


def answer_field(topic: dict, asked: str, about: str = "") -> tuple[str, list[tuple[str, str]]]:
    """(the Knowledge that answers it, its facts): the field of a fact the question names
    by the record's own key ("the history of Branford" names its History), else the
    plan's field when the subject holds facts in it, else the subject's own field (its
    kind's), else its fullest field. A fact the record repeats under two keys (World Bible
    weaves a town's Urban Life into its Social Classes) is told once."""
    import re

    r = row(ANSWER)
    by_field: dict[str, list[tuple[str, str]]] = {}
    seen: set[str] = set()
    named = ""
    words = " " + " ".join(re.findall(r"[a-z]+", str(about or "").lower())) + " "
    for k, v in topic["facts"].items():
        key = " ".join(str(k).split()).lower()
        said = " ".join(str(v).split()).lower()
        if key in r["never"] or said in seen:
            continue
        seen.add(said)
        field = _field_of(k, topic["kind"])
        by_field.setdefault(field, []).append((k, str(v)))
        if not named and f" {key} " in words:
            named = field
    if named:
        return named, by_field[named]
    own = _field_of("", topic["kind"])
    asked = str(asked or "").strip().lower()
    if asked in by_field:
        return asked, by_field[asked]
    if own in by_field or not by_field:
        return own, by_field.get(own, [])
    best = max(by_field, key=lambda f: len(by_field[f]))
    return best, by_field[best]


def knowledge_answer(engine, intent, actor, partial):
    """Knowledge to answer a question (CRB, Knowledge): "a DC of 10 (for really easy
    questions), 15 (for basic questions), or 20 to 30 (for really tough questions)"; no
    retry; untrained, no DC above 10. The subject is the world's (`_topic`); which
    Knowledge answers is the record's own fact keys (the row's `fields`, `answer_field`).
    The tiers are the /gm door's (play/gm_search.py `tier_of`) at Knowledge (local)'s own
    DCs, which that door already uses: what it is and what anybody there knows ("rulers
    and laws"), DC 10; its rumours ("common rumour"), DC 15; what is kept ("hidden
    organisations"), DC 20. A
    person's own `Secret` is never recalled (the row's `never`): it is theirs, not lore.
    Only what was recalled reaches the tell, and the knowing is a tag on the recaller."""
    from .activeeffect import ActiveEffect
    from .sheet import IllegalSheet
    from . import words
    from play import gm_search

    r = row(ANSWER)
    topic = _topic(engine, str(intent.params.get("about") or ""))
    if topic is None:
        return engine._refuse(intent, f"Nothing {actor.name} could have heard of goes by "
                                      f"that name in this world; there is nothing to "
                                      f"recall. Nothing is rolled.", code="unknown_topic")
    skill, facts = answer_field(topic, str(intent.params.get("skill") or ""),
                                str(intent.params.get("about") or ""))
    key = f"{_slug(topic['id'])}.{_slug(skill)}"
    if actor.has_state(f"{KNOWS_LORE}.{key}") or actor.has_state(f"{LORE_TRIED_TOPIC}.{key}"):
        return engine._refuse(intent, f"{actor.name} has already searched their memory for "
                                      f"what {skill.title()} holds on {topic['name']}; "
                                      f"thinking on it again teaches nothing new. Nothing is "
                                      f"rolled.", code="no_retry")
    tiers = {k: int(v) for k, v in r["tiers"].items()}
    try:
        mods, cap = actor.skill_modifiers(skill), None
    except IllegalSheet:
        mods, cap = actor.ability_check_modifiers("int"), tiers["really_easy"]
    roll = engine._roll_or_suspend(intent, actor, list(mods), label=f"{skill.title()} check",
                                   dc=tiers["really_easy"], partial=partial)
    total = roll.total if cap is None else min(roll.total, cap)
    recalled: list[str] = []
    if total >= tiers["really_easy"]:
        # World Bible's summary is a role word ("Village", "Person") or a sentence.
        what = " ".join(str(topic["summary"] or topic["kind"]).split())
        recalled.append(f"{topic['name']}: {_first(what)}".rstrip(".") if " " in what
                        else f"{topic['name']} is {words.a(what.lower())}")
    reach = {gm_search.PUBLIC: "basic", gm_search.RUMOUR: "tough",
             gm_search.HIDDEN: "really_tough"}
    # The deepest first: a fact a check reached at 20 is what the roll was for, and the
    # answer holds `most_facts` at most.
    deep = {gm_search.HIDDEN: 0, gm_search.RUMOUR: 1, gm_search.PUBLIC: 2}
    for k, v in sorted(facts, key=lambda kv: deep[gm_search.tier_of(kv[0])]):
        if total >= tiers[reach[gm_search.tier_of(k)]]:
            recalled.append(f"{k.lower()}: {_first(v)}".rstrip("."))
    if not topic["facts"] and topic["text"] and total >= tiers["basic"]:
        recalled.append(_first(topic["text"]).rstrip("."))
    recalled = recalled[:1 + int(r["most_facts"])]
    margin = roll.total - tiers["really_easy"]
    basis = (f"answer a question in {skill.title()}: 10 what it is and what anybody "
             f"knows, 15 rumour, 20 what is kept" + (" (untrained: no higher than 10)"
                                                     if cap else ""))
    fx = {"ref": actor.ref, "kind": "lore", "of": topic["id"], "field": skill,
          "facts": len(recalled), "origin": "rule:knowledge-answer"}
    if not recalled:
        actor.apply_effect(ActiveEffect(
            name=f"tried to recall {topic['name']}", kind="knowledge", key=f"lore-tried-{key}",
            source="rule:knowledge-answer", origin="rule:knowledge-answer",
            tags=(f"{LORE_TRIED_TOPIC}.{key}",)))
        return _outcome(intent, rolls=[roll], dc_value=tiers["really_easy"], basis=basis,
                        verdict="failure", margin=margin, effects=[fx],
                        tell=f"{actor.name} searches their memory for {topic['name']} and "
                             f"nothing of it comes back.")
    actor.apply_effect(ActiveEffect(
        name=f"recalls {topic['name']}", kind="knowledge", key=f"lore-{key}",
        source="rule:knowledge-answer", origin="rule:knowledge-answer",
        tags=(f"{KNOWS_LORE}.{key}",), payload={"facts": recalled, "about": topic["id"]}))
    return _outcome(intent, rolls=[roll], dc_value=tiers["really_easy"], basis=basis,
                    verdict="success", margin=margin, effects=[fx],
                    tell=f"{actor.name} recalls what {skill.title()} holds on "
                         f"{topic['name']}: " + "; ".join(recalled) + ".")


# --- Appraise ---------------------------------------------------------------------------------

def _worth_gp(actor, name: str) -> float:
    """The thing's open-counter worth, by the one pricing door: its own record (forged,
    bought, enchanted) or a stock jar, else the Core tables by name."""
    from . import pricing
    from . import tradecraft

    rec = tradecraft._record(actor, name)
    if rec:
        return float(pricing.worth(rec))
    for st in (getattr(actor, "stock", None) or {}).values():
        if str(getattr(st, "name", "") or "").strip().lower() == name.strip().lower():
            return float(pricing.worth(st))
    return float(pricing.goods_worth(name))


def appraise(engine, intent, actor, mods, partial):
    """Appraise a thing carried (CRB, Appraise): "A DC 20 Appraise check determines the
    value of a common item. If you succeed by 5 or more, you also determine if the item
    has magic properties ... If you fail the check by less than 5, you determine the price
    of that item to within 20% of its actual value. If you fail this check by 5 or more,
    the price is wildly inaccurate." A standard action; "additional attempts to Appraise
    an item reveal the same result" (the first answer is kept in `Scene.dealings`, the
    judge's own store). The value is the pricing door's (`pricing.worth`), the number every
    counter pays by; a miss is that number moved by a hidden roll inside the row's band."""
    from . import goods
    from . import tradecraft

    owner = engine.scene.actors.get(intent.target or "") or actor
    said = str(intent.params.get("item") or "").strip()
    name = tradecraft.carries(owner, said) if said else ""
    if not name:
        return engine._refuse(intent, (f"{owner.name} is not carrying {said}" if said else
                                       f"{actor.name} names nothing to appraise")
                              + ": an Appraise is made on a thing in hand. Nothing is rolled.")
    key = tradecraft.dealing_key("appraise", actor.ref, name.lower())
    seen = engine.scene.dealings.get(key)
    if seen:
        return _outcome(intent, tell=str(seen.get("tell") or ""))
    spent = _no_action_left(engine, actor, "standard", "an appraisal")
    if spent:
        return engine._refuse(intent, spent + " Nothing is rolled.", code="action_spent")
    out = row(APPRAISE)["outcome"]
    value_dc = dc(APPRAISE, actor)
    roll = engine._roll_or_suspend(intent, actor, list(mods), label="Appraise check",
                                   dc=value_dc, partial=partial)
    _spend_action(engine, actor, "standard")
    margin = roll.total - value_dc
    true_gp = _worth_gp(owner, name)
    seen_gp = true_gp
    if margin < 0:
        lo, hi = out["near_miss"] if margin > -5 else out["wild"]
        pct = engine.dice.roll("1d100", label="Appraise's error", visibility="hidden").total
        seen_gp = true_gp * (float(lo) + (float(hi) - float(lo)) * (pct - 1) / 99.0)
    seen_cp = int(round(seen_gp * 100))
    worth = goods.purse_line(goods.coins_for(seen_cp), engine._coins_here())
    if margin >= 0:
        tell = f"{actor.name} appraises {name} (Appraise {roll.total}): it is worth {worth}."
        if margin >= int(out["magic_by"]):
            tell += (" And there is magic in it." if tradecraft.is_magic(owner, name)
                     else " There is no magic in it.")
    else:
        tell = (f"{actor.name} appraises {name} (Appraise {roll.total}) and puts it at "
                f"{worth}.")
    engine.scene.dealings[key] = {"tell": tell, "said_cp": seen_cp}
    return _outcome(intent, rolls=[roll], dc_value=value_dc, basis="a common item: DC 20",
                    verdict="success" if margin >= 0 else "failure", margin=margin,
                    effects=[{"ref": actor.ref, "kind": "appraised", "item": name,
                              "said_cp": seen_cp, "origin": "rule:appraise"}], tell=tell)


# --- Spellcraft -------------------------------------------------------------------------------

def identify_item(engine, intent, actor, mods, partial):
    """Spellcraft to identify a magic item's properties, in play: the one identify there
    is (`knowledge.identify`, the circle bench's own door: DC 15 + the item's caster
    level, the curse at 10 over, once per item per day) handed this roll. The bench and
    the table are one rule and one record (`magic.known` on the item), not two."""
    from . import knowledge as knowledge_mod
    from . import tradecraft

    said = str(intent.params.get("item") or "").strip()
    name = tradecraft.carries(actor, said) if said else ""
    rec = tradecraft._record(actor, name) if name else None
    if not rec:
        return engine._refuse(intent, f"{actor.name} has no magic item called "
                                      f"{said or 'that'} in hand to study. Nothing is "
                                      f"rolled.")
    try:
        need = knowledge_mod.identify_dc(rec)
    except Exception:  # noqa: BLE001 — a record with no layer has no caster level to read
        need = 15
    roll = engine._roll_or_suspend(intent, actor, list(mods),
                                   label=f"Spellcraft check (identify {name})", dc=need,
                                   partial=partial)
    day = engine.scene.clock_minutes // (24 * 60)
    got = knowledge_mod.identify(actor, rec, roll.total, day=day)
    result = got.get("result")
    if result == "none":
        tell = f"{actor.name} studies {name}: there is no magic in it to know."
    elif result == "fail":
        tell = (f"{actor.name} studies {name} and cannot make out what its magic does; "
                f"another day may tell more.")
    else:
        tell = f"{actor.name} studies {name} and learns what its magic does."
        if result == "curse":
            tell += (f" And more: {got.get('curse')}." if got.get("cursed")
                     else " There is no curse on it.")
    return _outcome(intent, rolls=[roll], dc_value=int(got.get("dc") or need),
                    basis="identify a magic item: 15 + its caster level",
                    verdict="failure" if result == "fail" else "success",
                    margin=got.get("margin"),
                    effects=[{"ref": actor.ref, "kind": "identified", "item": name,
                              "result": result, "learned": list(got.get("learned") or ()),
                              "origin": "rule:spellcraft-identify"}], tell=tell)


def _same_side(scene, a, b) -> bool:
    if a.has_state("bond.travels-with-you"):
        return True
    return any(a.ref in refs and b.ref in refs for refs in (scene.sides or {}).values())


def identify_casting(engine, out, caster, spell, level) -> dict | None:
    """Spellcraft to identify a spell as it is being cast (CRB: DC 15 + spell level, no
    action, no retry, "you must clearly see the spell as it is being cast"): each player
    character trained in Spellcraft who sees a cast made by somebody not on their side
    rolls it. A cast nobody here identified names no spell: the cast's own tell says "a
    spell" where it said the spell's name, so the narrator cannot say what the character
    does not know. Amends the tell and rolls of `out` in place and returns the record of
    the attempt for its effects, or None when nobody here watched."""
    from . import awareness

    scene = engine.scene
    if caster is None or caster.is_pc or not spell or not getattr(spell, "name", ""):
        return None
    watchers = [a for a in scene.actors.values()
                if a.is_pc and a is not caster and not a.is_down
                and awareness.sees(scene, a, caster)]
    if not watchers or _same_side(scene, caster, watchers[0]):
        return None
    need = dc(CASTING, caster, spell_level=int(level or 0))
    knew = []
    for pc in watchers:
        if not int((pc.ranks or {}).get("spellcraft", 0) or 0):
            continue                     # trained only
        roll = engine.dice.d20(list(pc.skill_modifiers("spellcraft")),
                               label=f"{pc.name}'s Spellcraft (identify the casting)",
                               visibility="hidden")
        out.rolls.append(roll)
        if roll.total >= need:
            knew.append(pc.name)
    if knew:
        out.tell = (f"{out.tell} {' and '.join(knew)} knows the casting at once: "
                    f"{spell.name}.").strip()
    else:
        out.tell = out.tell.replace(spell.name, "a spell", 1).replace(spell.name, "the spell")
    return {"kind": "identified", "spell": spell.id, "by": list(knew), "dc": need,
            "origin": "rule:spellcraft-identify"}


# --- Perform ----------------------------------------------------------------------------------

def perform_for_coin(engine, intent, actor, mods, partial):
    """Perform to earn money (CRB, Perform): the book's table, DC 10 a routine performance
    (1d10 cp), 15 enjoyable (1d10 sp), 20 great (3d10 sp), 25 memorable (1d6 gp), 30
    extraordinary (3d6 gp), for an evening's work in a settlement. "Retries are allowed,
    but they don't negate previous failures": each failure today puts +2 on every row
    of the next attempt (`Scene.dealings`). The coin goes to the purse, the evening to
    the clock and the body (`Engine._work_hours`, a day's work's own door)."""
    from . import goods
    from . import places as places_mod
    from . import tradecraft

    r = row(PERFORM)
    scene = engine.scene
    if scene.initiative:
        return engine._refuse(intent, "Not in the middle of a fight.")
    loc = engine.world.get(scene.location_id) if (engine.world and scene.location_id) else None
    if loc is None or places_mod.setting_of(scene.at) != "in":
        return engine._refuse(intent, "There is nobody out here to pay for a performance: "
                                      "performing for coin is done in a settlement. Nothing "
                                      "is rolled.")
    day = scene.clock_minutes // (24 * 60)
    key = tradecraft.dealing_key("perform", actor.ref, day)
    failed = int((scene.dealings.get(key) or {}).get("failed", 0))
    table = sorted(((int(d), pay) for d, pay in r["table"].items()), reverse=True)
    lowest = table[-1][0] + 2 * failed
    roll = engine._roll_or_suspend(intent, actor, list(mods), label="Perform check (for coin)",
                                   dc=lowest, partial=partial)
    worked, body = engine._work_hours(actor, int(r["hours"]))
    got = next((pay for d, pay in table if roll.total >= d + 2 * failed), None)
    coins = engine._coins_here()
    town = getattr(loc, "name", "") or "the town"
    paid = 0
    if got is None:
        scene.dealings[key] = {"failed": failed + 1}
        tell = (f"{actor.name} performs in {town} through the evening (Perform "
                f"{roll.total}) and nobody stops to pay.")
    else:
        paid = engine.dice.roll(got["dice"], label="Perform's takings",
                                visibility="hidden").total * int(got["cp_each"])
        actor.purse = goods.credit(actor.purse, paid)
        tell = (f"{actor.name} performs in {town} through the evening, {got['said']} "
                f"(Perform {roll.total}), and takes "
                f"{goods.purse_line(goods.coins_for(paid), coins)}. {actor.name} now has "
                f"{goods.purse_line(actor.purse, coins)} in hand.")
    if body:
        tell += f" The evening costs them: {body}."
    return _outcome(intent, rolls=[roll], dc_value=lowest,
                    basis="earn a living: DC 10, 15, 20, 25, 30 by the book's table"
                          + (f", +{2 * failed} for today's failures" if failed else ""),
                    verdict="success" if got else "failure", margin=roll.total - lowest,
                    effects=[{"ref": actor.ref, "kind": "time", "minutes": worked * 60,
                              "origin": "rule:perform"},
                             {"ref": actor.ref, "kind": "earned", "paid_cp": paid,
                              "origin": "rule:perform"}],
                    tell=tell)

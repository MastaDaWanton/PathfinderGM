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

    return resources.evaluate(row(use_id)["dc"], subject, names or None)


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
        sense = _total(target.skill_modifiers("sense motive")) if trained else 0
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
    target.apply_effect(ActiveEffect(
        name=f"feinted by {actor.name}", kind="situation", key=f"feinted-by-{actor.ref}",
        source=FEINT_SOURCE, origin="rule:feint", duration="rounds",
        # shortcut: the round ticker runs at the top of the round, so 2 lasts through the
        # feinter's next turn and a little past it; a per-turn clock would end it exactly.
        rounds_left=int(out["rounds"]), tags=(f"{FEINTED}.{actor.ref}",),
        payload={"by": actor.ref}))
    effects = [{"ref": target.ref, "kind": "condition", "condition": "feinted",
                "by": actor.ref, "origin": "rule:feint"}]
    said = (f"{actor.name} feints at {target.name}{cost} and makes the bluff "
            f"check{dc_mod.by(margin)}: {target.name}'s guard is drawn, and {actor.name}'s "
            f"next melee attack on them, this turn or the next, finds them without their "
            f"Dexterity to their defence.")
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


def feinted(defender, attacker, weapon: dict | None) -> bool:
    """Whether this blow is the feinter's next melee attack on a creature it feinted."""
    if defender is None or attacker is None or not weapon \
            or weapon.get("category") == "ranged" or weapon.get("thrown"):
        return False
    return defender.has_state(f"{FEINTED}.{attacker.ref}")


def spend_feint(defender, attacker) -> None:
    """The feint is used up by the attack that read it (Greater Feint's exposure stays
    its round: it is against everybody, not against the next blow)."""
    tag = f"{FEINTED}.{attacker.ref}"
    defender.remove_effects(match=lambda e: tag in (e.tags or ()))


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
        if roll.total >= value:
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
        mods = actor.skill_modifiers(skill)
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
    return _outcome(intent, rolls=[roll], dc_value=hardest,
                    basis="Dazzling Display: each foe's 10 + Hit Dice + Wis",
                    verdict="success" if effects else "failure",
                    margin=roll.total - hardest, effects=effects, tell=" ".join(bits))

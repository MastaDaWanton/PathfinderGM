"""The readied action (CRB, Combat, Special Initiative Actions, "Ready";
aonprd.com/Rules.aspx?ID=201, read 2026-11-26).

"Readying is a standard action. It does not provoke an attack of opportunity (though the
action that you ready might do so) ... specify the action you will take and the conditions
under which you will take it. Then, anytime before your next action, you may take the
readied action in response to that condition. The action occurs just before the action
that triggers it ... For the rest of the encounter, your initiative result is the count on
which you took the readied action, and you act immediately ahead of the character whose
action triggered your readied action ... If you come to your next action and have not yet
performed your readied action, you don't get to take the readied action ... If you take
your readied action in the next round, before your regular turn comes up, your initiative
rises to that new point in the order of battle, and you do not get your regular action
that round." With its three named uses: distracting spellcasters (a readied attack before
a cast — the cast's concentration check for being struck), readying to counterspell
(Spellcraft DC 15 + spell level to identify, then the same spell, or dispel magic with a
dispel check, ruins the cast), and a brace weapon set against a charge (double damage on a
hit against a charging character).

Prior art: Foundry PF1 keeps no readied-action automation (the GM moves the combatant in
the tracker by hand); Roll20's sheets roll the attack and leave the order to the GM;
Owlcat's Kingmaker/WotR dropped Ready entirely (no trigger language a CRPG could parse). So
the trigger here is a closed list the engine can answer, never words: the player picks one
on the combat bar ("models read, code validates", owner 2026-10-03), and the hooks below
ask it of the act about to resolve.

The store is the one effect store: an `ActiveEffect` on the readier carrying the trigger's
tag (`action.readied.<trigger>`) and what was readied in its payload. Taken, it is removed
and the readier's slot in the order moves to just before the trigger's maker; not taken by
the readier's next turn, it lapses there (`lapse`, asked from `Scene._next_able`).

shortcut: the engine knows where a move ENDS, not its route (`reactions.provoked_by_move`
says why it will not invent one), so "a foe comes into reach" fires when the move lands in
reach, not as it crosses the edge; a foe that passes through and out again is not seen.
"""
from __future__ import annotations

from .activeeffect import ActiveEffect

READIED = "action.readied"

# The triggers the engine can answer, each with the words the bar and the tells use.
TRIGGERS = {
    "enters_reach": "a foe comes within reach",
    "attacks_me": "a foe attacks them",
    "casts": "a foe begins casting a spell",
    "charges_me": "a foe charges them",
}
# What may be readied: a single attack, or a counterspell (CRB, Magic, Counterspells).
# A readied charge is Rhino Charge's alone (`READY_CHARGE`), and not built (see the report).
ACTIONS = ("attack", "counterspell")
# Feat tags read here, each a feat document's `tags` line:
STRIKE_BACK = "ready.strike-back"      # Strike Back (CRB): a melee foe out of reach
PATIENT = "ready.patient"              # Patient Strike: readied as a full-round action
MASKED = "counterspell.masked"         # Spell Bluff: +4 on the counterspeller's DC
# The two dispel spells "can be used to counterspell another spellcaster, and you don't
# need to identify the spell he's casting" (CRB, dispel magic): a dispel check, 1d20 +
# caster level against DC 11 + the caster's level.
DISPELS = ("dispel-magic", "greater-dispel-magic")


def tag(trigger: str) -> str:
    return f"{READIED}.{trigger}"


def held(actor) -> ActiveEffect | None:
    """The readied action this creature holds, or None."""
    return next((e for e in getattr(actor, "effects", ()) or ()
                 if READIED in (e.tags or ())), None)


def refusal(actor, trigger: str, action: str, patient: bool = False) -> str:
    """Why this cannot be readied, or "" — the engine's rule, asked by the op and the bar."""
    if trigger not in TRIGGERS:
        return f"A readied action needs a trigger the table can see: {', '.join(TRIGGERS)}."
    if action not in ACTIONS:
        return f"What can be readied here: {', '.join(ACTIONS)}."
    if action == "counterspell":
        from . import casting

        if not casting.is_caster(actor):
            return f"{actor.name} casts no spells to counter one with."
        if trigger != "casts":
            return "A counterspell is readied against a foe beginning a spell."
    if patient and (action != "attack" or not actor.has_state(PATIENT)):
        return "Only Patient Strike readies an attack as a full-round action."
    return ""


def effect(actor, trigger: str, action: str, patient: bool, rnd: int) -> ActiveEffect:
    # Two rounds as a backstop only: it lapses at the holder's next turn (`lapse`), which
    # is never more than one round-top away.
    return ActiveEffect(
        name="readied action", kind="buff", key="readied", source="Ready",
        origin="rule:ready", duration="rounds", rounds_left=2,
        tags=(READIED, tag(trigger)),
        payload={"trigger": trigger, "action": action, "patient": bool(patient),
                 "round": int(rnd)})


def said(action: str, trigger: str) -> str:
    what = "a counterspell" if action == "counterspell" else "an attack"
    return f"{what} for when {TRIGGERS.get(trigger, trigger)}"


def op_ready(engine, intent):
    """The `ready` op: a standard action (Patient Strike's full-round one) in a fight."""
    from . import skilluses
    from .engine import Outcome

    actor = engine.scene.actors[intent.actor]
    p = intent.params or {}
    trigger, action = str(p.get("trigger") or ""), str(p.get("action") or "")
    patient = bool(p.get("patient"))
    if not engine.scene.in_encounter:
        return engine._refuse(intent, "Readying an action is for a fight, and no fight is on.")
    why = refusal(actor, trigger, action, patient)
    if why:
        return engine._refuse(intent, why, code="not_readied")
    cost = "full-round" if patient else "standard"
    spent = skilluses._no_action_left(engine, actor, cost, "readying an action")
    if spent:
        return engine._refuse(intent, spent, code="action_spent")
    skilluses._spend_action(engine, actor, cost)
    actor.remove_effects(match=lambda e: READIED in (e.tags or ()))
    actor.apply_effect(effect(actor, trigger, action, patient, engine.scene.round))
    return Outcome(
        intent_id=intent.id, op="ready", actor=actor.ref,
        effects=[{"ref": actor.ref, "kind": "readied", "trigger": trigger,
                  "action": action, "patient": patient, "origin": "rule:ready"}],
        tell=(f"{actor.name} holds ready {said(action, trigger)}"
              + (" (Patient Strike, the whole round)" if patient else "") + "."),
        because=intent.because)


# --- taking it ---------------------------------------------------------------------------

def _foes_holding(engine, maker_ref: str, trigger: str):
    from . import awareness
    from .reactions import _allied

    scene = engine.scene
    maker = scene.actors.get(maker_ref or "")
    if maker is None:
        return
    for ref, a in list(scene.actors.items()):
        e = held(a)
        if e is None or ref == maker_ref or tag(trigger) not in (e.tags or ()) \
                or a.is_down or _allied(scene, ref, maker_ref) or a.blocking_key("attack"):
            continue
        if not awareness.sees(scene, a, maker):
            continue
        yield a, e


def _taken(engine, actor, maker_ref: str) -> None:
    """The readied action spent: the effect off, and the readier's count the trigger's,
    just ahead of it."""
    scene = engine.scene
    actor.remove_effects(match=lambda e: READIED in (e.tags or ()))
    order = list(scene.initiative)
    roll = next((v for r, v in order if r == maker_ref), None)
    if roll is None or not any(r == actor.ref for r, _ in order):
        return
    holder = scene.turn_holder()
    order = [(r, v) for r, v in order if r != actor.ref]
    at = next(i for i, (r, _) in enumerate(order) if r == maker_ref)
    # The trigger's own count: a stable sort keeps the readier ahead of it (`Scene.enrol`).
    order.insert(at, (actor.ref, roll))
    scene.initiative = order
    scene._point_at(holder)


def _blow(engine, actor, e, foe_ref: str, because: str, **params) -> dict:
    extra = {"patient_readied": True} if (e.payload or {}).get("patient") else {}
    return {"op": "attack", "actor": actor.ref, "target": foe_ref, "because": because,
            "params": {"full_attack": False, "reaction": "readied", **extra, **params},
            "visibility": "player" if actor.is_pc else "hidden"}


def _reaches(engine, actor, foe) -> bool:
    from . import position

    return position.out_of_reach(engine.scene, actor, foe, actor.equipped) is None


def before(engine, raw: dict) -> list[dict]:
    """The readied attacks owed in front of this act (`Engine._drive`, beside the attacks
    of opportunity): a foe's blow at the readier, a charge's blow at the readier, a foe's
    cast. A counterspell is the cast's own question (`counterspell`)."""
    from . import weapons

    scene = engine.scene
    if not scene.in_encounter or (raw.get("params") or {}).get("reaction"):
        return []
    op, maker = raw.get("op"), str(raw.get("actor") or "")
    params = raw.get("params") or {}
    out: list[dict] = []
    if op == "attack":
        aimed = {str(raw.get("target") or "")} | set(
            str(t) for t in (raw.get("targets") or ()))
        charging = params.get("charge") and params.get("charged") is not None
        foe = scene.actors.get(maker)
        if foe is None:
            return []
        for trigger in (("charges_me",) if charging else ()) + ("attacks_me",):
            for a, e in _foes_holding(engine, maker, trigger):
                if a.ref not in aimed or (e.payload or {}).get("action") != "attack":
                    continue
                if any(x.get("actor") == a.ref for x in out):
                    continue
                if _reaches(engine, a, foe):
                    # Set against the charge; "braced" only with a brace weapon, the one
                    # the book's double damage is for (`weapons.has_trait`).
                    extra = {"vs_charge": True} if trigger == "charges_me" else {}
                    if extra and weapons.has_trait(a.equipped or "", "brace"):
                        extra["braced"] = True
                elif a.has_state(STRIKE_BACK) and _melee(engine, raw, foe):
                    # Strike Back (CRB): "against any foe that attacks you in melee, even
                    # if the foe is outside of your reach".
                    extra = {"strike_back": True}
                else:
                    continue
                out.append(_blow(engine, a, e, maker,
                                 f"{a.name}'s readied attack as {foe.name} "
                                 f"{'charges' if trigger == 'charges_me' else 'attacks'}",
                                 **extra))
                _taken(engine, a, maker)
    elif op == "cast":
        caster = scene.actors.get(maker)
        for a, e in _foes_holding(engine, maker, "casts"):
            if (e.payload or {}).get("action") != "attack" or caster is None:
                continue
            if not _ranged(a) and not _reaches(engine, a, caster):
                continue
            out.append(_blow(engine, a, e, maker,
                             f"{a.name}'s readied attack as {caster.name} begins a spell"))
            _taken(engine, a, maker)
        if out and "struck_from" not in params:
            # Distracting spellcasters (CRB, Ready): the cast reads its wounds against these.
            raw["params"] = dict(params, struck_from=engine._wounds_left(caster))
    return out


def _ranged(actor) -> bool:
    try:
        return str((actor.weapon(actor.equipped) or {}).get("category") or "") == "ranged"
    except Exception:  # noqa: BLE001 - nothing named in hand is the body
        return False


def _melee(engine, raw, foe) -> bool:
    try:
        w = foe.weapon((raw.get("params") or {}).get("weapon") or foe.equipped)
    except Exception:  # noqa: BLE001 - a body with nothing named swings its body
        return True
    return str((w or {}).get("category") or "melee") != "ranged"


def on_arrival(engine, outcome) -> list[dict]:
    """A foe's move that ended inside a readier's reach (trigger `enters_reach`)."""
    from . import grid as gridmod
    from . import reactions

    scene = engine.scene
    if not scene.in_encounter or not scene.has_grid:
        return []
    went = next((x for x in outcome.effects or () if x.get("kind") == "position"
                 and x.get("from") is not None and x.get("to") is not None), None)
    if went is None or tuple(went["from"])[:2] == tuple(went["to"])[:2]:
        return []
    ref = str(went.get("ref") or "")
    mover = scene.actors.get(ref)
    if mover is None or mover.is_down:
        return []
    start = set(gridmod.footprint(tuple(went["from"])[:2], mover.size))
    end = set(gridmod.footprint(tuple(went["to"])[:2], mover.size))
    out: list[dict] = []
    for a, e in _foes_holding(engine, ref, "enters_reach"):
        if (e.payload or {}).get("action") != "attack":
            continue
        zone = reactions.threatened_by(scene, a.ref, mover.size)
        if not (end & zone) or (start & zone):
            continue
        out.append(_blow(engine, a, e, ref,
                         f"{a.name}'s readied attack as {mover.name} comes within reach"))
        _taken(engine, a, ref)
    return out


def counterspell(engine, intent, caster, spell, level: int, state: dict, pool: str):
    """A readied counterspell against this cast (CRB, Magic, Counterspells): the readier
    identifies it (Spellcraft DC 15 + spell level, +4 against Spell Bluff, `MASKED`) and
    casts the same spell, or dispel magic and wins the dispel check; either way its slot
    is spent and the cast is ruined — an Outcome, after the caster's slot, as concentration
    is lost. None when nobody counters. The readier's dice are the engine's, as the
    identification's are (`skilluses.identify_casting`)."""
    from . import casting
    from . import spells as spells_mod
    from .engine import Outcome, _roll_from_dict

    if spell is None or (intent.params or {}).get("reaction"):
        return None
    for a, e in list(_foes_holding(engine, caster.ref, "casts")):
        if (e.payload or {}).get("action") != "counterspell":
            continue
        rolls = []
        how, source = "", None
        same = casting.castable_now(a, spell) and casting.cast_source(a, spell)
        if same:
            need = 15 + int(level or 0) + (4 if caster.has_state(MASKED) else 0)
            ctx = {"skill_use": "identify-casting", "spell_known": casting.knows(a, spell)}
            roll = engine.dice.d20(list(a.skill_modifiers("spellcraft", ctx=ctx)),
                                   label=f"{a.name}'s Spellcraft (identify to counter)",
                                   visibility="hidden")
            rolls.append(roll)
            if int((a.ranks or {}).get("spellcraft", 0) or 0) and roll.total >= need:
                how, source, used = "the same spell", same, spell
        if source is None:
            for sid in DISPELS:
                try:
                    d = spells_mod.get(sid)
                except KeyError:
                    continue
                src = casting.castable_now(a, d) and casting.cast_source(a, d)
                if not src:
                    continue
                mine = casting.spell_caster_level(a, d)
                theirs = casting.caster_level(caster) or int(
                    getattr(caster, "level", 1) or 1)
                check = engine.dice.d20([], label=f"{a.name}'s dispel check "
                                                  f"(1d20 + {mine} against {11 + theirs})",
                                        visibility="hidden")
                rolls.append(check)
                if check.total + mine >= 11 + theirs:
                    how, source, used = d.name, src, d
                break
        _taken(engine, a, caster.ref)
        if source is None:
            state.setdefault("tells", []).append(
                f"{a.name} tries to counter the spell and cannot.")
            for r in rolls:
                state.setdefault("rolls", []).append(r.as_dict())
            continue
        spent_pool = source.get("pool") or ""
        if spent_pool and int(source.get("cost", 1) or 0):
            a.spend_pool(spent_pool, int(source.get("cost", 1) or 1))
        if source.get("key") and casting.prepared_count(a, source["key"]) > 0:
            casting.unprepare(a, source["key"], 1)
        return Outcome(
            intent_id=intent.id, op="cast",
            rolls=[_roll_from_dict(r) for r in state.get("rolls", [])] + rolls,
            effects=[{"ref": caster.ref, "kind": "countered", "spell": spell.id,
                      "name": spell.name, "by": a.ref, "with": used.id, "slot": pool,
                      "slots_left": casting.pool_left(caster, pool),
                      "origin": "rule:counterspell"}],
            tell=(f"{caster.name} begins {spell.name}, and {a.name} answers with "
                  f"{how} as a counterspell: the spell is ruined"
                  + ("." if casting.at_will(level) else ", and its slot with it.")),
            because=intent.because)
    return None


def lapse(scene, ref: str) -> list[dict]:
    """A readied action not taken by its holder's next turn is lost (CRB, Ready)."""
    who = scene.people.get(ref)
    if who is None or held(who) is None:
        return []
    who.remove_effects(match=lambda e: READIED in (e.tags or ()))
    return [{"kind": "effect_ended", "ref": ref, "what": "readied action",
             "origin": "rule:ready"}]

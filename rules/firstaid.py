"""First aid: a Heal check that stops somebody dying.

The rule, from the Core Rulebook's Heal skill (d20pfsrd, Heal, fetched for the fix pass
and confirmed by its critic, docs/fix-interfaces.md §1.4 C4):

    First Aid: You usually use first aid to save a dying character. If a character has
    negative hit points and is losing hit points (at the rate of 1 per round, 1 per
    hour, or 1 per day), you can make him stable. A stable character regains no hit
    points but stops losing them. ... DC 15. Action: standard.

Why it exists now (design C §4.2, measured 2026-09-28): nothing in the engine let a Heal
check stabilise anybody. `_op_check` resolved a Heal like any other skill and said "makes
the heal check by 3", and the dying patient went on losing a hit point a round, because
the only way off the ladder was the patient's own Constitution roll in `bleed_out`. The
two starts written for the bonesetter and the ferryman hand the player exactly that
check, so without this they handed over a roll that could not do the one thing it was for.

The DC is the rule's and never the plan's: a model that writes `dc: 10` on a first-aid
check is not asked. The patient's condition changes through the sheet's own condition
door, the same one `bleed_out` uses when the patient manages it alone, so the two routes
to stable cannot disagree about what stable is.

Losable by design (owner's ruling Q17): an untreated patient bleeds out under the
engine's own rule. Nothing here stops that; it only gives the player the rule's answer.
"""
from __future__ import annotations

DC = 15
SKILL = "heal"


def dying(actor) -> bool:
    """Asked of the vocabulary, not by condition name (law 1)."""
    return bool(actor is not None and actor.has_state("state.down.dying")
                and not actor.has_state("state.down.dead"))


def bleeding(actor) -> bool:
    """A bleed running on them (`state.wound.bleeding`, `Engine._rider_bleed` and every
    other bleed door), asked of the vocabulary."""
    return bool(actor is not None and actor.has_state("state.wound.bleeding")
                and not actor.has_state("state.down.dead"))


def needs_aid(actor) -> bool:
    """What a DC 15 Heal check is for: somebody dying, or somebody bleeding — "Bleeding
    can be stopped by a DC 15 Heal check" (CRB, Appendix 2 / Bestiary UMR, Bleed). The
    bleed's own tell promised that from the day it was laid; until lane E (2026-11-22)
    nothing kept the promise (the audit's measurement: `firstaid` treated only the
    dying, and `Actor.heal` removed no bleed)."""
    return dying(actor) or bleeding(actor)


def patient_of(engine, intent):
    """The dying or bleeding creature a Heal check is aimed at, or None when this is not
    first aid. A bleeding healer may bind their own wound; nobody dying is awake to."""
    if str(intent.params.get("skill") or "").strip().lower() != SKILL             or intent.params.get("care"):
        return None
    named = [ref for ref in intent.targets() if ref and ref != intent.actor]
    for ref in named:
        if ref in engine.scene.actors:
            who = engine.scene.actors[ref]
            if needs_aid(who):
                return who
    if named:
        return None             # aimed at somebody who is not dying: a Heal check of
        #                         another kind (a poison, a disease, long-term care)
    # Aimed at nobody: the one creature here who is dying, when there is exactly one — the
    # engine's own state answers "on whom", never the words. Measured 2026-10-08 (the deeds
    # lane, local model): "I give first aid to the wounded porter" was planned as
    # `check skill=heal` with no target 3 times of 3, so this found no patient, the check
    # rolled against the plan's DC, and the porter bled on. Two or more dying and none
    # named is a choice the engine will not make for the player.
    here = [a for ref, a in engine.scene.actors.items()
            if ref != intent.actor and needs_aid(a)]
    if not here and bleeding(engine.scene.actors.get(intent.actor)):
        return engine.scene.actors[intent.actor]
    return here[0] if len(here) == 1 else None


def stanch(patient, by: str) -> tuple[str, list[dict]]:
    """Every bleed on them stops: the effects carrying `state.wound.bleeding` are removed,
    so their damage stops with them (law 2). `by` names what stopped it, for the tell and
    the record. ("", []) when nothing was bleeding."""
    gone = patient.remove_effects(match=lambda e: any(
        t == "state.wound.bleeding" or t.startswith("state.wound.bleeding.")
        for t in (e.tags or ())))
    if not gone:
        return "", []
    return (f"{patient.name} stops bleeding.",
            [{"kind": "condition_removed", "ref": patient.ref, "condition": "bleed",
              "by": by}])


def settle(healer, patient, succeeded: bool) -> tuple[str, list[dict]]:
    """What the check did to the patient: (the tell's clause, the effects). One DC 15
    check does both jobs it is for: the dying made stable, a bleed stopped."""
    was_dying, was_bleeding = dying(patient), bleeding(patient)
    if not succeeded:
        still = " and ".join(w for w, on in (("dying", was_dying), ("bleeding", was_bleeding))
                             if on) or "as they were"
        return (f" {patient.name} is still {still}.", [])
    said, effects = [], []
    if was_bleeding:
        line, fx = stanch(patient, "first aid")
        if line:
            who = "their own wound" if healer is patient else f"{patient.name}'s wound"
            said.append(f"{healer.name} binds {who}: {line}")
            effects += fx
    if was_dying:
        # The one writer of the rung (`Actor.stabilise`), shared with the patient's own
        # Constitution check and with any healing that leaves them negative.
        patient.stabilise("first aid")
        said.append(f"{healer.name} stops {patient.name} losing blood: {patient.name} is "
                    f"stable, no longer dying, and no better than that.")
        effects.append({"kind": "condition", "ref": patient.ref, "condition": "stable",
                        "by": "first aid"})
    return (" " + " ".join(said) if said else "", effects)


def stabilise(engine, healer, patient):
    """First aid as a door of its own — for anybody the engine rolls for (a companion, a
    healer the scene brings in): the Heal check at the rule's DC, hidden, and the
    result. Returns the Outcome."""
    from . import dc as dc_mod
    from .engine import Outcome

    mods = healer.skill_modifiers(SKILL)
    roll = engine.dice.d20(mods, label=f"{healer.name} Heal check", visibility="hidden")
    margin = roll.total - DC
    tell = (f"{healer.name} makes the heal check{dc_mod.by(margin)}." if margin >= 0
            else f"{healer.name} misses the heal check by {-margin}.")
    if not needs_aid(patient):
        return Outcome(intent_id="", op="check", rolls=[roll],
                       dc=dc_mod.ResolvedDC(value=DC, band=None).as_dict(),
                       verdict="success" if margin >= 0 else "failure", margin=margin,
                       effects=[], tell=f"{tell} {patient.name} was not dying.")
    said, effects = settle(healer, patient, margin >= 0)
    return Outcome(intent_id="", op="check", rolls=[roll],
                   dc=dc_mod.ResolvedDC(value=DC, band=None).as_dict(),
                   verdict="success" if margin >= 0 else "failure", margin=margin,
                   effects=effects, tell=tell + said)

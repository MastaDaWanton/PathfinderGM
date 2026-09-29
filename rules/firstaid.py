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


def patient_of(engine, intent):
    """The dying creature a Heal check is aimed at, or None when this is not first aid."""
    if str(intent.params.get("skill") or "").strip().lower() != SKILL:
        return None
    for ref in intent.targets():
        if ref and ref != intent.actor and ref in engine.scene.actors:
            who = engine.scene.actors[ref]
            if dying(who):
                return who
    return None


def settle(healer, patient, succeeded: bool) -> tuple[str, list[dict]]:
    """What the check did to the patient: (the tell's clause, the effects)."""
    if not succeeded:
        return (f" {patient.name} is still dying.", [])
    patient.remove_condition("dying")
    patient.add_condition("stable", source="first aid")
    return (f" {healer.name} stops {patient.name} losing blood: {patient.name} is stable, "
            f"no longer dying, and no better than that.",
            [{"kind": "condition", "ref": patient.ref, "condition": "stable",
              "by": "first aid"}])


def stabilise(engine, healer, patient):
    """First aid as a door of its own — for anybody the engine rolls for (a companion, a
    healer the scene brings in): the Heal check at the rule's DC, hidden, and the
    result. Returns the Outcome."""
    from . import dc as dc_mod
    from .engine import Outcome

    mods = healer.skill_modifiers(SKILL)
    roll = engine.dice.d20(mods, label=f"{healer.name} Heal check", visibility="hidden")
    margin = roll.total - DC
    tell = (f"{healer.name} makes the heal check by {margin}." if margin >= 0
            else f"{healer.name} misses the heal check by {-margin}.")
    if not dying(patient):
        return Outcome(intent_id="", op="check", rolls=[roll],
                       dc=dc_mod.ResolvedDC(value=DC, band=None).as_dict(),
                       verdict="success" if margin >= 0 else "failure", margin=margin,
                       effects=[], tell=f"{tell} {patient.name} was not dying.")
    said, effects = settle(healer, patient, margin >= 0)
    return Outcome(intent_id="", op="check", rolls=[roll],
                   dc=dc_mod.ResolvedDC(value=DC, band=None).as_dict(),
                   verdict="success" if margin >= 0 else "failure", margin=margin,
                   effects=effects, tell=tell + said)

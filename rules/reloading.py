"""Reloading a crossbow (CRB, Equipment, Weapon Descriptions; aonprd.com, read 2026-11-26).

"Crossbow, hand ... You can draw a hand crossbow back by hand. Loading a hand crossbow is a
move action that provokes attacks of opportunity." "Crossbow, light ... Loading a light
crossbow is a move action that provokes attacks of opportunity." "Crossbow, heavy ...
Loading a heavy crossbow is a full-round action that provokes attacks of opportunity."
"Normally, operating a light crossbow requires two hands ... you can shoot, but not load,
a light crossbow with one hand." And Rapid Reload's Normal: "A character without this feat
needs a move action to reload a hand or light crossbow ... or a full-round action to load
a heavy crossbow" — so without the feat a light crossbow fires once a round, full attack
or none ("you may fire that weapon as many times in a full-attack action as you could
attack if you were using a bow" is the feat's gift). A repeating crossbow is reloaded by
its lever, a free action, while its case of five lasts.

Measured before (feat loop b4-moves' Crossbow Mastery): "a crossbow already fires every
iterative of a full attack for anyone and never provokes for its reload, so the feat waives
nothing the engine would have asked".

The state is a tag on an `ActiveEffect`: a crossbow shot in a fight is left unloaded
(`weapon.unloaded.<key>`), and the next shot with it is met by its reload first, through
the one door a reload comes by (`Engine._op_reload`, spliced in front as a draw is),
spending the reload's action from the turn's ledgers. Out of a fight time is not short and
nothing is unloaded.

shortcut: a repeating crossbow's case of five is not counted (its lever is free, its new
case a full-round action); the exotic crossbows past the CRB's (crank, double, launching,
slaver's) keep no reload. shortcut: a reload's own attack of opportunity is the shot's
(rules/shooting.py provokes once per attack op from the same watchers, whose one swing a
round a second provocation would not get anyway); upgrade for Combat Reflexes watchers.
"""
from __future__ import annotations

from .activeeffect import ActiveEffect

UNLOADED = "weapon.unloaded"
RAPID = "reload.rapid"            # Rapid Reload's tag, its chosen crossbow in the leaf
MASTERY = "reload.mastery"        # Crossbow Mastery: any crossbow reloads free

# The base weapon's reload, by the book's own words above.
RELOAD = {
    "hand-crossbow": "move", "light-crossbow": "move", "underwater-light-crossbow": "move",
    "heavy-crossbow": "full-round", "underwater-heavy-crossbow": "full-round",
    "repeating-hand-crossbow": "free", "repeating-light-crossbow": "free",
    "repeating-heavy-crossbow": "free",
}
# Rapid Reload: "reduced to a free action (for a hand or light crossbow), a move action (for
# heavy crossbow ...)".
_RAPID = {"move": "free", "full-round": "move"}


def base(actor, key: str) -> str:
    from . import shooting

    return shooting._base(actor, key) if key else ""


def _rapid_for(actor) -> set:
    from . import weapons

    out = set()
    for tag in actor.standing_tags():
        tag = str(tag)
        if tag.startswith(RAPID + "."):
            leaf = tag[len(RAPID) + 1:]
            out.add(weapons.key_for(leaf) or leaf.replace(" ", "-"))
    return out


def action(actor, key: str) -> str:
    """The reload's action for this weapon in this hand: "" for a weapon with none (not a
    crossbow the table knows), else free, move or full-round."""
    b = base(actor, key)
    act = RELOAD.get(b, "")
    if not act or act == "free":
        return act
    if actor.has_state(MASTERY):
        return "free"
    rapid = _rapid_for(actor)
    if b in rapid or b.replace("underwater-", "") in rapid:
        return _RAPID.get(act, act)
    return act


def one_shot(actor, key: str) -> bool:
    """Whether a full attack with this weapon is one shot: its reload costs an action a
    full attack has no room for."""
    return action(actor, key) in ("move", "full-round")


def unloaded(actor, key: str) -> bool:
    return actor.has_state(f"{UNLOADED}.{base(actor, key) or key}")


def after(engine, intent, outcome) -> None:
    """A crossbow shot in a fight leaves it unloaded, unless it reloads free."""
    scene = engine.scene
    if not scene.in_encounter or intent.op != "attack" or outcome.status != "resolved" \
            or (intent.params or {}).get("manoeuvre"):
        return
    actor = scene.actors.get(intent.actor or "")
    if actor is None:
        return
    key = str((intent.params or {}).get("weapon") or actor.equipped or "")
    if not one_shot(actor, key) or not outcome.rolls:    # a shot loosed, not a refusal
        return
    b = base(actor, key)
    actor.apply_effect(ActiveEffect(
        name=f"{b.replace('-', ' ')} unloaded", kind="situation", key=f"unloaded-{b}",
        source="a shot", origin="rule:reload", tags=(f"{UNLOADED}.{b}",),
        duration="until-dismissed"))


def before(engine, raw: dict) -> dict | None:
    """The reload owed in front of this shot, as an intent (`Engine._op_reload`), or None."""
    if raw.get("op") != "attack" or (raw.get("params") or {}).get("manoeuvre"):
        return None
    actor = engine.scene.actors.get(str(raw.get("actor") or ""))
    if actor is None:
        return None
    key = str((raw.get("params") or {}).get("weapon") or actor.equipped or "")
    if not unloaded(actor, key):
        return None
    return {"op": "reload", "actor": actor.ref, "id": f"{raw.get('id') or 'shot'}-reload",
            "target": None, "visibility": "hidden", "because": "reloading before the shot",
            "params": {"weapon": key}}


def op_reload(engine, intent):
    from . import skilluses
    from .engine import Outcome

    actor = engine.scene.actors[intent.actor]
    key = str((intent.params or {}).get("weapon") or actor.equipped or "")
    b = base(actor, key)
    if not unloaded(actor, key):
        return Outcome(intent_id=intent.id, op="reload", tell="", status="resolved")
    act = action(actor, key)
    name = b.replace("-", " ")
    if engine.scene.in_encounter and act in ("move", "full-round"):
        why = skilluses._no_action_left(engine, actor, act, f"loading the {name}")
        if why:
            return engine._refuse(intent, f"The {name} is not loaded. {why}",
                                  code="action_spent")
        skilluses._spend_action(engine, actor, act)
    actor.remove_effects(match=lambda e: f"{UNLOADED}.{b}" in (e.tags or ()))
    said = {"free": "", "move": " (a move action)", "full-round": " (the whole round)"}
    return Outcome(intent_id=intent.id, op="reload", actor=actor.ref,
                   effects=[{"ref": actor.ref, "kind": "reloaded", "weapon": b,
                             "action": act, "origin": "rule:reload"}],
                   tell=f"{actor.name} loads the {name}{said.get(act, '')}.",
                   because=intent.because)


def refusal(actor, key: str) -> str:
    """The shot refused when the crossbow is still unloaded (its reload was refused)."""
    if not unloaded(actor, key):
        return ""
    return (f"The {base(actor, key).replace('-', ' ')} is not loaded, and loading it needs "
            f"an action this turn no longer has. Nothing is shot.")

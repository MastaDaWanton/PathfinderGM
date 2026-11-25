"""Combat styles: the stance a style feat embodies, held as one `ActiveEffect`.

Ultimate Combat, Style Feats (d20pfsrd.com/feats/style-feats, read 2026-11-22): "You can
use a swift action to enter the stance employed by a style feat. Although you cannot use a
style feat before combat begins, the style you are in persists until you spend a swift
action to switch to a different combat style. You can use a feat that has a style feat as
a prerequisite only while in the stance of the associated style."

So the stance is a state (law 1): an effect tagged `style.<feat id>` (Crane Style is
`style.crane-style`), laid by `Engine._op_style` and asked by every follow-up feat's
document as `when: {"bearer": {"state": "style.crane-style"}}` — remove the effect and the
numbers go with it (law 2). One style at a time: entering a second takes the first off.
Which feats are styles is the index's own `style` tag (content/feats/feats.json), never a
list written here.

Foundry PF1 models a stance as a buff toggled by hand on the sheet, and Owlcat's
Wrath of the Righteous as an activatable ability that switches the others off — the
second is this shape. Neither ends the stance with the fight; the book's "persists until
you switch" is read here as lasting the fight (`Scene.end_encounter` lifts it), because a
style "cannot be used before combat begins" and the next fight starts without one (owner
call, b2-styles 2026-11-22).
"""
from __future__ import annotations

from .activeeffect import ActiveEffect

# The tag root every stance answers to: `has_state("style")` is "in any style".
ROOT = "style"
# What the stance's origin is stamped with, as the feat stances are (`rule:feat-<id>`).
ORIGIN = "rule:feat-{}"


def tag(feat_id: str) -> str:
    return f"{ROOT}.{feat_id}"


def is_style(feat) -> bool:
    """A style feat by the index's own tag (Crane Style, Snake Style ...)."""
    return ROOT in [str(t).lower() for t in (getattr(feat, "tags", None) or ())]


def held(actor) -> list:
    """The style feats this creature has, in sheet order (the feats, resolved)."""
    from . import feats as feats_mod

    out, seen = [], set()
    for raw in getattr(actor, "feats", None) or ():
        feat, _ = feats_mod.resolve(raw)
        if feat is not None and is_style(feat) and feat.id not in seen:
            seen.add(feat.id)
            out.append(feat)
    return out


def current(actor) -> list[str]:
    """The feat ids of the styles this creature stands in now (one, by the book)."""
    out = []
    for e in getattr(actor, "effects", None) or ():
        for t in e.tags or ():
            t = str(t)
            if t.startswith(ROOT + "."):
                out.append(t[len(ROOT) + 1:])
    return out


def stance(feat) -> ActiveEffect:
    """The effect that is the stance: no numbers of its own — the feats' documents carry
    them and ask for the tag."""
    return ActiveEffect(
        name=feat.name, kind="buff", key=f"style {feat.id}", source=feat.name,
        origin=ORIGIN.format(feat.id), duration="until-dismissed", tags=(tag(feat.id),))


def is_stance(effect) -> bool:
    return any(str(t).startswith(ROOT + ".") for t in effect.tags or ())


def refusal(actor, feat_id: str, in_encounter: bool) -> str:
    """Why this creature cannot enter this style now, or "" (the swift action aside)."""
    from . import feats as feats_mod

    feat = next((f for f in held(actor) if f.id == feat_id), None)
    if feat is None:
        try:
            named = feats_mod.get(feat_id).name
        except KeyError:
            return f"There is no combat style called {feat_id!r}."
        return f"{actor.name} does not know {named}."
    if not in_encounter:
        return (f"{feat.name} is a fighting stance: a style is entered in a fight, "
                f"never before it begins.")
    verdict = feats_mod.meets(actor, feat)
    if verdict["unmet"]:
        return f"{actor.name} cannot use {feat.name}: needs {', '.join(verdict['unmet'])}."
    if feat.id in current(actor):
        return f"{actor.name} is already in {feat.name}."
    return ""


def npc_stance(scene, ref: str, raw_intents):
    """A creature that knows a style takes its stance on its first turn of a fight, the
    swift action spent first, as a GM running it by the book would: a style known is a
    style used. The first one its sheet lists; never a second once it stands in one."""
    actor = scene.actors.get(ref) if scene is not None else None
    if actor is None or not scene.in_encounter or not isinstance(raw_intents, list) \
            or current(actor):
        return raw_intents
    for feat in held(actor):
        if not refusal(actor, feat.id, True):
            return [{"op": "style", "actor": ref, "params": {"style": feat.id},
                     "because": "its fighting stance"}, *raw_intents]
    return raw_intents

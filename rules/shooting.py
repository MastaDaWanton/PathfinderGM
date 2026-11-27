"""A ranged attack made in a threatened square provokes (CRB, Combat, Table 8-2: "Attack
(ranged) — standard action — attack of opportunity: yes"; aonprd.com/Rules.aspx?ID=171), and
so does a whip's lash: "Attacking with a whip provokes attacks of opportunity as if you used
a ranged weapon" (Whip Mastery's Normal, UC).

Measured before (feat loop b4-moves' Sword and Pistol): the dispatch `Engine.
_reactions_before` asked manoeuvres, casting, drinking and pick-ups and nothing else, so an
archer loosed point-blank into an ogre's face for free, and every feat that waives the
provocation (Sword and Pistol, Whip Mastery) waived nothing.

Asked once per attack op: a full attack's shots are one op here, so its first shot is the
one the watchers answer — and 1e's one attack of opportunity a round per watcher is what a
second shot would meet anyway, short of Combat Reflexes.
shortcut: one provocation per attack op, not one per shot; upgrade if a Combat Reflexes
watcher should answer each iterative shot.

Waivers, each a feat document's tag:
- `attack.unprovoking.<weapon key>` — Whip Mastery's "You no longer provoke attacks of
  opportunity when attacking with a whip" (`attack.unprovoking.whip`).
- `attack.unprovoking.sword-and-pistol` — Sword and Pistol (UC): "When you use the Two-Weapon
  Fighting feat while wielding a melee weapon and a crossbow or firearm, your attacks with the
  crossbow or firearm provoke no attacks of opportunity from foes that you threaten with your
  melee weapon."
"""
from __future__ import annotations

UNPROVOKING = "attack.unprovoking"
SWORD_AND_PISTOL = f"{UNPROVOKING}.sword-and-pistol"


def _base(actor, key: str) -> str:
    from . import weapons

    try:
        w = actor.weapon(key)
    except Exception:  # noqa: BLE001 - nothing named is the body
        return ""
    return str(w.get("crafted_base") or weapons.key_for(
        str(w.get("key") or w.get("name") or key)) or key or "")


def _ranged(actor, key: str) -> bool:
    try:
        return str(actor.weapon(key).get("category") or "") == "ranged"
    except Exception:  # noqa: BLE001
        return False


def provoking_weapon(actor, params: dict) -> str:
    """The key of the weapon this attack provokes for, or "" — a ranged weapon (a thrown one
    included), or a whip, in either hand of the op."""
    if params.get("manoeuvre") or params.get("coup_de_grace") or params.get("squares_off"):
        return ""
    keys = [str(params.get("weapon") or actor.equipped or "")]
    if params.get("off_hand"):
        keys.append(str(params["off_hand"]))
    for key in keys:
        if not key:
            continue
        base = _base(actor, key)
        if (params.get("thrown") and key == keys[0]) or _ranged(actor, key) or base == "whip":
            if actor.has_state(f"{UNPROVOKING}.{base or key}"):
                continue
            return key
    return ""


def provoked(engine, raw: dict) -> list[dict]:
    """The attacks of opportunity this attack owes, spent off each watcher's allowance."""
    from . import reactions

    scene = engine.scene
    params = raw.get("params") or {}
    if not scene.in_encounter or params.get("reaction") or not scene.has_grid:
        return []
    actor = scene.actors.get(str(raw.get("actor") or ""))
    if actor is None:
        return []
    key = provoking_weapon(actor, params)
    if not key:
        return []
    fired = reactions.provoked_by_action(scene, actor.ref)
    if fired and actor.has_state(SWORD_AND_PISTOL) and params.get("off_hand"):
        # The melee weapon is the other of the two hands; its threatened squares spare
        # the foes in them.
        other = next((k for k in (str(params.get("weapon") or actor.equipped or ""),
                                  str(params.get("off_hand") or ""))
                      if k and k != key and not _ranged(actor, k)), "")
        crossbow = "crossbow" in _base(actor, key)
        if other and crossbow:
            reach, gap = reactions.reach_with(actor, other)
            here = scene.positions.get(actor.ref)
            from . import grid as gridmod

            mine = set(gridmod.threatened_squares(here, actor.size, reach=reach)) if here \
                else set()
            if gap and here:
                mine -= set(gridmod.threatened_squares(here, actor.size,
                                                       reach=gridmod.SQUARE_FT))
            fired = [(w, r) for w, r in fired
                     if not any(sq in mine for sq in gridmod.footprint(
                         tuple(scene.positions[w][:2]), scene.actors[w].size))]
    out: list[dict] = []
    for watcher, reaction in fired:
        if not engine._spend_reaction(watcher, reaction.budget):
            continue
        out.append({
            "op": reaction.op, "actor": watcher, "target": actor.ref,
            "because": (f"{actor.name} lashed out with the whip within reach"
                        if _base(actor, key) == "whip" else
                        f"{actor.name} made a ranged attack within reach"),
            "params": {"full_attack": False, "reaction": reaction.id},
            "visibility": "player" if scene.actors[watcher].is_pc else "hidden",
        })
    return out

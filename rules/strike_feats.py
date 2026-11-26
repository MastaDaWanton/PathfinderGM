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

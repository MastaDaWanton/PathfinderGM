"""The dispel check (CRB, Magic, dispel magic; aonprd.com SpellDisplay.aspx?ItemName=dispel
magic and ...=greater dispel magic, read 2026-11-27).

"Targeted Dispel: One object, creature, or spell is the target of the dispel magic spell.
You make one dispel check (1d20 + your caster level) and compare that to the spell with
highest caster level (DC = 11 + the spell's caster level). If successful, that spell ends.
If not, compare the same result to the spell with the next highest caster level. Repeat
this process until you have dispelled one spell affecting the target, or you have failed
to dispel every spell." "... (maximum +10)." "You automatically succeed on your dispel
check against any spell that you cast yourself." Greater dispel magic: the check's caster
level is "maximum +20", and "you can dispel one spell for every four caster levels you
possess, starting with the highest level spells and proceeding to lower level spells";
used to counterspell it gains "a +4 bonus on the dispel check".

Foundry PF1 keeps no dispel automation (a chat card with the check; the GM deletes the
buff by hand); PCGen has none. What the engine needs that neither keeps is the CASTER LEVEL
of each effect: a stamp on the effect's payload (`stamp`), laid once by the cast that put
it there, so the DC is the effect's own and never a guess. The removal is the one
applicator's (`Actor.remove_effects`): the contribution goes with the record.

shortcut: an effect with no stamp (a potion drunk, an effect saved before 2026-11-27) is
taken at caster level 1 — a potion's printed minimum for a 1st-level spell; upgrade when
consumables stamp their item's caster level.
"""
from __future__ import annotations

from .dice import Modifier, stack

STAMP = "cast"
# The cap on the caster level a dispel check adds, by the spell that rolls it.
CAPS = {"dispel-magic": 10, "dispel-magic-greater": 20}
GREATER = "dispel-magic-greater"
COUNTER_BONUS = {"dispel-magic-greater": 4}
# The lists whose casters cast divine spells (CRB, Magic: "Divine spells"). The class file
# may say so itself with `casting.tradition`.
DIVINE_LISTS = ("cleric", "druid", "paladin", "ranger", "adept", "inquisitor", "oracle",
                "warpriest", "shaman")

# Feat tags read here, each a feat document's `tags` line.
TENACIOUS = "dispel.tenacious.transmutation"   # Tenacious Transmutation (APG)
SYNERGY = "dispel.synergy"                     # Dispel Synergy (UC)


def is_divine(actor) -> bool:
    from . import casting

    data = casting.caster_data(actor) or {}
    if data.get("tradition"):
        return str(data["tradition"]) == "divine"
    return str(data.get("list") or "") in DIVINE_LISTS


def stamp(scene, caster, spell, cl: int, level: int, origin: str, refs) -> None:
    """Write the cast's own facts on every effect it laid: caster level, caster, school,
    tradition, and the metamagic the dispel reads (Tenebrous Spell). Re-stamped on the
    creatures this cast reached, so a second casting's refresh carries the new level."""
    from . import metamagic

    rec = {"cl": int(cl), "by": caster.ref, "spell": spell.id, "level": int(level),
           "school": str(getattr(spell, "school", "") or "").lower(),
           "divine": is_divine(caster),
           "tenebrous": metamagic.flag(spell, "tenebrous"),
           "tenacious": caster.has_state(TENACIOUS)}
    reached = set(refs or ()) | {caster.ref}
    for ref, who in scene.actors.items():
        for e in who.effects:
            if e.origin != origin:
                continue
            if ref in reached or STAMP not in (e.payload or {}):
                e.payload = {**(e.payload or {}), STAMP: dict(rec)}
                extra = [str(t) for t in getattr(spell, "effect_tags", None) or ()
                         if str(t) not in (e.tags or ())]
                if extra:
                    e.tags = tuple(e.tags or ()) + tuple(extra)
    # "Not cumulative with similar effects" (CRB, haste): a creature this spell reached
    # that already held its tag from another source keeps the newer one only — the two
    # are the same terms, so the numbers are the book's either way (owner call, b6-rules).
    for tag in getattr(spell, "effect_tags", None) or ():
        for ref in reached:
            who = scene.actors.get(ref)
            if who is not None and any(e.origin == origin for e in who.effects):
                who.remove_effects(match=lambda e, t=str(tag): e.origin != origin
                                   and t in (e.tags or ()))


def cast_of(effect) -> dict:
    return dict((effect.payload or {}).get(STAMP) or {})


def spells_on(actor) -> list[dict]:
    """The spells on a creature, one entry per casting (its effects together: haste's five
    terms are one spell), highest caster level first — the order the check walks."""
    groups: dict[tuple, dict] = {}
    for e in actor.effects:
        if not str(e.origin or "").startswith("spell:"):
            continue
        c = cast_of(e)
        key = (e.origin, e.source, c.get("by", ""))
        g = groups.setdefault(key, {"origin": e.origin, "source": e.source,
                                    "cl": int(c.get("cl") or 1), "cast": c,
                                    "effects": []})
        g["effects"].append(e)
    return sorted(groups.values(), key=lambda g: (-g["cl"], -int(g["cast"].get("level") or 0)))


def dc_of(group: dict) -> tuple[int, str]:
    """11 + the effect's caster level, and Tenacious Transmutation's +2 (APG: "The DC of
    caster level checks to dispel or remove your transmutations increases by 2")."""
    c = group["cast"]
    dc = 11 + int(group["cl"])
    if c.get("tenacious") and c.get("school") == "transmutation":
        return dc + 2, " (Tenacious Transmutation +2)"
    return dc, ""


def check_mods(dispeller, cl: int, spell_id: str, against: dict, light: str = "",
               counter: bool = False) -> list[Modifier]:
    """1d20's terms: the capped caster level, the dispeller's funnel terms on a caster
    level check made to dispel (Atheist Abjurations' +2, a `combat_mod` on `caster_level`
    `when: {"against": "dispel_divine"}`), greater dispel's +4 to counter, and Tenebrous
    Spell's light terms (Inner Sea Magic: "Any attempts at dispelling a tenebrous spell in
    darkness or dim light take a -2 penalty on the dispel check ... Attempts to dispel a
    tenebrous spell in bright light gain a +4 bonus")."""
    cap = CAPS.get(spell_id, 10)
    mods = [Modifier(min(int(cl), cap), f"caster level (max +{cap})")]
    words = ("dispel",)
    if against.get("divine") and str(against.get("by_school") or "") == "abjuration":
        words += ("dispel_divine",)
    if hasattr(dispeller, "_buff_mods"):
        mods += list(dispeller._buff_mods("combat_mod", "caster_level", {"against": words}))
    if counter and COUNTER_BONUS.get(spell_id):
        mods.append(Modifier(COUNTER_BONUS[spell_id], "greater dispel, to counter"))
    if against.get("tenebrous"):
        if light in ("dark", "dim"):
            mods.append(Modifier(-2, "tenebrous spell in the dark"))
        elif light == "bright":
            mods.append(Modifier(4, "tenebrous spell in bright light"))
    return stack(mods)


def targeted(engine, dispeller, target, cl: int, spell_id: str, by_school: str,
             origin: str) -> tuple[list[dict], list[str], list]:
    """A targeted dispel at one creature: one roll, walked down its spells by caster level;
    greater dispel ends one per four caster levels. Returns (effects, tells, rolls)."""
    groups = spells_on(target)
    if not groups:
        return ([{"kind": "dispel_check", "ref": target.ref, "found": 0}],
                [f"No spell holds on {target.name} for the dispel to end."], [])
    budget = max(1, int(cl) // 4) if spell_id == GREATER else 1
    pos = engine.scene.positions.get(target.ref)
    light = engine.scene.light_at(tuple(pos[:2]) if pos else None)
    rolls, effects, ended, held = [], [], [], []
    roll = None
    for g in groups:
        if len(ended) >= budget:
            break
        c = g["cast"]
        dc, why = dc_of(g)
        if c.get("by") == dispeller.ref:
            beat, total = True, None
        else:
            mods = check_mods(dispeller, cl, spell_id,
                              {"divine": c.get("divine"), "by_school": by_school,
                               "tenebrous": c.get("tenebrous")}, light)
            if roll is None or c.get("tenebrous"):
                # One roll for the walk (the book's "compare the same result"); a tenebrous
                # spell's light terms are its own, so its total is rolled with them.
                roll = engine.dice.d20(mods, label=f"{dispeller.name}'s dispel check",
                                       visibility="hidden")
                rolls.append(roll)
            total = roll.total
            beat = total >= dc
        effects.append({"kind": "dispel_check", "ref": target.ref, "spell": g["source"],
                        "origin": origin, "dc": dc, "total": total, "beat": beat})
        if not beat:
            held.append(f"{g['source']} ({total} against DC {dc}{why})")
            continue
        ended.append(g)
        effects.extend(_end(engine, target, g, origin))
    tells = []
    if ended:
        lingering = [g["source"] for g in ended if _lingers(g)]
        tells.append(f"The dispel ends {', '.join(g['source'] for g in ended)} on "
                     f"{target.name}."
                     + (f" {', '.join(lingering)} holds one round more before it fades "
                        f"(Tenacious Transmutation)." if lingering else ""))
        syn = _synergy(engine, dispeller, target)
        if syn:
            effects.append(syn[0])
            tells.append(syn[1])
    if held:
        tells.append(f"The dispel fails against {', '.join(held)}.")
    return effects, tells, rolls


def _lingers(group: dict) -> bool:
    c = group["cast"]
    return bool(c.get("tenacious")) and c.get("school") == "transmutation"


def _end(engine, target, group: dict, origin: str) -> list[dict]:
    """End one spell through the applicator. Tenacious Transmutation: "even if the spell is
    negated, its effects persist for 1 additional round before dissipating" — its clock set
    to one round, the one ticker ends it."""
    mine = {id(e) for e in group["effects"]}
    if _lingers(group):
        for e in group["effects"]:
            e.rounds_left, e.duration = 1, "rounds"
        return [{"kind": "dispelled", "ref": target.ref, "spell": group["source"],
                 "origin": origin, "lingers": 1}]
    target.remove_effects(match=lambda e: id(e) in mine)
    return [{"kind": "dispelled", "ref": target.ref, "spell": group["source"],
             "origin": origin}]


def _synergy(engine, dispeller, target):
    """Dispel Synergy (UC): "If you successfully dispel an ongoing magical effect on an
    opponent, that opponent takes a -2 penalty on saving throws against your spells until
    the end of your next turn" — three save terms scoped to the dispeller (`vs`, the
    cast save's `attacker_actor`) and to spells, for this turn and the next (two ticks)."""
    from .activeeffect import ActiveEffect

    if not dispeller.has_state(SYNERGY) or not engine._against(dispeller, target):
        return None
    target.apply_effect(ActiveEffect(
        name="Dispel Synergy", kind="buff", key="dispel-synergy",
        source=f"{dispeller.name}'s Dispel Synergy", origin="rule:feat-dispel-synergy",
        duration="rounds", rounds_left=2,
        modifiers=[{"kind": "save_mod", "target": s, "amount": -2,
                    "bonus_type": "untyped", "vs": dispeller.ref,
                    "when": {"against": "spell"}, "note": "Dispel Synergy"}
                   for s in ("fort", "ref", "will")]))
    return ({"kind": "buff", "ref": target.ref, "source": "Dispel Synergy", "amount": -2,
             "origin": "rule:feat-dispel-synergy"},
            f"{target.name} takes -2 on saves against {dispeller.name}'s spells until the "
            f"end of {dispeller.name}'s next turn (Dispel Synergy).")


def counter_check(engine, counterer, cl: int, spell_id: str, by_school: str, caster,
                  spell) -> tuple[bool, object, int]:
    """A dispel check made to counter `caster`'s `spell` as it is cast (CRB: "If the
    target is a spellcaster ... you make a dispel check against the caster level of the
    spell being cast"): (beat, roll, dc)."""
    from . import casting, metamagic

    theirs = casting.spell_caster_level(caster, spell) or int(getattr(caster, "level", 1) or 1)
    dc = 11 + int(theirs)
    if caster.has_state(TENACIOUS) and str(spell.school or "").lower() == "transmutation":
        dc += 2
    pos = engine.scene.positions.get(caster.ref)
    light = engine.scene.light_at(tuple(pos[:2]) if pos else None)
    mods = check_mods(counterer, cl, spell_id,
                      {"divine": is_divine(caster), "by_school": by_school,
                       "tenebrous": metamagic.flag(spell, "tenebrous")}, light, counter=True)
    roll = engine.dice.d20(mods, label=f"{counterer.name}'s dispel check (to counter, "
                                       f"DC {dc})", visibility="hidden")
    return roll.total >= dc, roll, dc

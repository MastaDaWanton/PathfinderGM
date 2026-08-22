"""Read a creature's defences out of its stat block and into specs the engine can hold.

The same move `tools/convert_effects.py` made for ingredients, applied to the bestiary. An
ingredient's mechanics were derived at read time until a person was allowed to correct one,
at which point deriving became wrong: the next parse overwrites the edit. So the parse
becomes a starting point written into the file, and `effects_converted` marks what nobody
has looked at.

What was actually broken here is narrower and worse than "the data is unstructured".
`rules/bestiary._NOT_ON_THE_SHEET` drops `immune`, `resist`, `senses` and `weaknesses` when
a bestiary row becomes an `Actor`, and `Actor` has no field for any of them — so a frost
giant took full damage from cold, a devil took full damage from fire, and 1,243 immunity
terms and 419 resistances sat in the content directory being read by nothing.

`reductions` is deliberately not converted. It is already structured, already loaded onto
`Actor.reductions`, and already applied in `take_damage`. Converting it would put the same
fact in two places, which is the failure CLAUDE.md names: the fix ships from the copy
nobody looked at.

What can be read mechanically is read; what cannot is kept as narrative rather than
guessed at or dropped. A claim the schema cannot hold is still a claim the book made.
"""
from __future__ import annotations

import re

from . import effectspec

# The energy names a resistance can carry, mapped onto the schema's damage types. The
# bestiary writes "negative energy" where the vocabulary says "negative"; everything else
# matches by name. Measured across the repaired file, this is the complete vocabulary —
# acid, cold, electricity, fire, sonic, negative energy and nothing else.
ENERGY = {"acid": "acid", "cold": "cold", "electricity": "electricity", "fire": "fire",
          "sonic": "sonic", "negative energy": "negative", "negative": "negative",
          "positive energy": "positive", "positive": "positive", "force": "force"}

# Immunity terms that name a damage type the engine can act on at the point of damage.
# Everything else — "undead traits", "paralysis", "mind-affecting effects" — is a real
# immunity and is kept, but it answers a question `take_damage` does not ask, so it is
# recorded and left for the condition and save paths to consult.
IMMUNE_DAMAGE = dict(ENERGY, **{
    "bludgeoning": "bludgeoning", "piercing": "piercing", "slashing": "slashing",
    "poison": "poison", "nonlethal damage": "untyped",
})

# "vulnerable to fire", "vulnerability to cold", "vulnerable to critical hits". The first
# two are the 1e rule — half again as much damage from that type — and the third is not a
# damage type at all, which is why this reads the energy rather than the whole phrase.
_VULNERABLE = re.compile(
    r"vulnerab(?:le|ility) to (?:the )?([a-z ]+?)(?:\s+damage)?\s*(?:,|;|$)", re.I)

# `Senses` is prose with a rigid vocabulary: "darkvision 60 ft., low-light vision;
# Perception +10". Seven of the senses in it have a schema entry; the rest are real and
# have none, and go to narrative rather than being dropped or bent into the nearest one.
_SENSE_WORDS = {
    "darkvision": "darkvision", "darkvison": "darkvision", "low-light vision": "low_light",
    "scent": "scent", "tremorsense": "tremorsense", "tremorsens e": "tremorsense",
    "blindsense": "blindsense", "see invisibility": "see_invisible",
    "true seeing": "true_seeing",
}
_SENSE_RE = re.compile(
    r"\b(" + "|".join(sorted((re.escape(w) for w in _SENSE_WORDS), key=len, reverse=True))
    + r")\b(?:\s+(\d+)\s*ft)?", re.I)

# Senses with no schema entry, kept by name so nothing is silently lost. Blindsight is the
# one that matters most — 157 creatures have it and it is not blindsense.
_UNMAPPED_SENSES = re.compile(
    r"\b(blindsight|all-around vision|see in darkness|lifesense|greensight|thoughtsense"
    r"|darksense|deathwatch|arcane sight|life sight|second sight|trace teleport)\b"
    r"(?:\s+(\d+)\s*ft)?", re.I)


def _spec(type_id: str, **fields) -> dict:
    # Every creature defence is a standing trait rather than something that wears off, so
    # none of these carry a duration. An immunity that expires is a spell, not a monster.
    return {"type": type_id, **fields}


def from_creature(creature: dict) -> list[dict]:
    """Every defence in one stat block, as specs, in the order the block prints them."""
    out: list[dict] = []

    for term in creature.get("immune") or ():
        out.append(_spec("immunity", target=term.strip().lower()))

    for term in creature.get("resist") or ():
        # `rules/statblock.RESISTANCE` has already guaranteed the shape, so this split
        # cannot fail on repaired data — but the editor can save anything, so a term that
        # does not split is kept rather than dropped.
        energy, _, amount = term.strip().lower().rpartition(" ")
        if amount.isdigit() and energy in ENERGY:
            out.append(_spec("resistance", target=ENERGY[energy], amount=int(amount)))
        else:
            out.append(_spec("narrative", target=f"Resist {term}"))

    text = creature.get("weaknesses") or ""
    for m in _VULNERABLE.finditer(text):
        what = m.group(1).strip().lower()
        if what in ENERGY:
            out.append(_spec("vulnerability", target=ENERGY[what]))
        else:
            # "vulnerable to critical hits", "vulnerable to sunlight". Real, and not a
            # damage type — dropping them would quietly make the creature tougher.
            out.append(_spec("narrative", target=f"Vulnerable to {what}"))
    # Weaknesses that are not a vulnerability at all: "light sensitivity" on 162 creatures,
    # "vampire weaknesses" on 64. Named rules with their own text, kept whole.
    rest = _VULNERABLE.sub("", text).strip(" ,;.")
    if rest:
        out.append(_spec("narrative", target=rest))

    senses = creature.get("senses") or ""
    seen: set[str] = set()
    for m in _SENSE_RE.finditer(senses):
        sense = _SENSE_WORDS[m.group(1).lower()]
        if sense in seen:
            continue
        seen.add(sense)
        spec = _spec("sense", target=sense)
        if m.group(2):
            spec["range"] = int(m.group(2))
        out.append(spec)
    for m in _UNMAPPED_SENSES.finditer(senses):
        feet = f" {m.group(2)} ft." if m.group(2) else ""
        out.append(_spec("narrative", target=f"{m.group(1).lower()}{feet}"))

    # Spell resistance is a number the engine has no field for yet. Recorded as narrative
    # so it reaches the GM rather than being invisible, and named exactly so that when a
    # spell-resistance check exists this is greppable.
    if creature.get("sr"):
        out.append(_spec("narrative", target=f"Spell resistance {creature['sr']}"))

    return out


def derive(creature: dict) -> dict:
    """A creature with its `effects` filled in, for the editor to show.

    Declared on the `creatures` Kind as its `derive` hook rather than baked into the
    content files. Baking would put every immunity in two places — `immune` and `effects`
    — and the editor shows both, so correcting one would leave the other saying the old
    thing and nothing would report the disagreement.

    An `effects` list that is already there is left alone: that is a person's answer, or a
    homebrew creature saying something the parse cannot, and either way it outranks a
    re-reading of the prose.
    """
    if creature.get("effects"):
        return creature
    out = dict(creature)
    out["effects"] = from_creature(creature)
    # The same flag ingredients carry, meaning the same thing: a machine read the prose and
    # nobody has checked it. The editor clears it on save.
    out["effects_converted"] = bool(out["effects"])
    return out


def convert(creature: dict) -> tuple[list[dict], list[str]]:
    """Specs for one creature, and any that the schema refused.

    Refusals are returned rather than raised: a run over 7,133 creatures that stops at the
    first malformed one tells you nothing about the other 7,132.
    """
    specs, problems = [], []
    for spec in from_creature(creature):
        found = effectspec.validate(spec)
        if found:
            problems.append(f"{creature.get('id', '?')}: {found[0]}")
            # Held loosely rather than lost, the same way convert_effects.py does it.
            specs.append(_spec("narrative", target=str(spec.get("target", "")),
                               note=f"needs review: {found[0]}"))
            continue
        specs.append(spec)
    return specs, problems

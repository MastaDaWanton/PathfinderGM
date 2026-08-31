"""The state vocabulary: every condition, as hierarchical tags.

Stage 1 of docs/states-effects-tells.md. Conditions have been flat strings, and every
question about them was its own hand-rolled test: lootability checked `hp <= 0 or
has_condition("unconscious")`, the walking-dead prose cut built a name list from
`hp <= 0`, `can_act` read a flag off the condition table, and the three drifted — a
petrified actor was lootable by one test and alive by another. A tag hierarchy makes
them one question with one answer: "anything under `state.down`?"

The vocabulary is additive and homebrew-safe on purpose. A key nobody registered
self-tags under `condition.<key>`, so an authored class's new state participates in
prefix queries the day it is written, and nothing anywhere matches exact strings.

Tags are dot-paths. A query matches a tag when it names the tag exactly or a prefix of
it at a dot boundary: `state.down` matches `state.down.dead` and not `state.downhill`.
"""
from __future__ import annotations

# Every shipped condition, with the tags it grants. Two families carry most questions:
#   state.down.*    — out of the fight and beyond objecting: lootable, un-attackable
#                     in any meaningful sense, and never again an actor in prose.
#   state.unable.*  — cannot take actions right now (may still be very much alive).
# They overlap where 1e overlaps them: the dying are both down and unable; the
# stunned are unable and emphatically not down.
TAGS: dict[str, tuple[str, ...]] = {
    "dead":        ("state.down.dead", "state.unable"),
    "dying":       ("state.down.dying", "state.unable"),
    "unconscious": ("state.down.unconscious", "state.unable"),
    "stable":      ("state.down.stable", "state.unable"),
    "petrified":   ("state.down.petrified", "state.unable"),
    "helpless":    ("state.down.helpless",),
    "paralyzed":   ("state.unable.paralyzed", "state.held"),
    "pinned":      ("state.held.pinned",),
    "grappled":    ("state.held.grappled",),
    "stunned":     ("state.unable.stunned",),
    "dazed":       ("state.unable.dazed",),
    "cowering":    ("state.unable.cowering",),
    "nauseated":   ("state.impaired.nauseated",),
    "staggered":   ("state.impaired.staggered",),
    "disabled":    ("state.impaired.disabled",),
    "fatigued":    ("state.impaired.fatigued",),
    "exhausted":   ("state.impaired.exhausted",),
    "sickened":    ("state.impaired.sickened",),
    "shaken":      ("state.fear.shaken",),
    "frightened":  ("state.fear.frightened",),
    "panicked":    ("state.fear.panicked",),
    "fascinated":  ("state.unable.fascinated",),
    "confused":    ("state.impaired.confused",),
    "blinded":     ("state.senses.blinded",),
    "deafened":    ("state.senses.deafened",),
    "dazzled":     ("state.senses.dazzled",),
    "invisible":   ("state.hidden.invisible",),
    "prone":       ("state.position.prone",),
    "flat-footed": ("state.position.flat-footed",),
    "bleed":       ("state.wound.bleeding",),
    "entangled":   ("state.held.entangled",),
    # The stances play has already minted. Buffs, not states: they are worn by choice.
    "blood armament": ("buff.stance.blood-armament",),
    "blood rage":     ("buff.stance.blood-rage",),
    "coagulated plate": ("buff.stance.coagulated-plate",),
    # The price of coming back: somebody paid the priests, and now the debt sits
    # on the character. Clockless — the world decides when it is called in.
    "life debt": ("state.obligation.life-debt",),
}


def tags_for(key: str) -> tuple[str, ...]:
    """The tags a condition key grants. Unknown keys self-tag, so homebrew plays."""
    key = (key or "").strip().lower()
    if not key:
        return ()
    known = TAGS.get(key)
    if known:
        return known
    return (f"condition.{key.replace(' ', '-')}",)


def matches(tag: str, query: str) -> bool:
    """Whether `tag` answers `query` — exact, or prefix at a dot boundary."""
    return tag == query or tag.startswith(query + ".")


def any_match(keys, query: str) -> bool:
    """Whether any condition key in `keys` grants a tag answering `query`."""
    q = (query or "").strip().lower()
    return any(matches(t, q) for k in keys for t in tags_for(k))


# What an immunity, written as a stat block writes it, actually protects against.
#
# 1e attaches immunity to what an effect IS — a sleep effect, a fear effect, a poison —
# and not to the condition it happens to produce, and the difference is the whole reason
# this is a table rather than a string comparison. 469 shipped creatures are immune to
# sleep, and sleep immunity does NOT stop a creature falling unconscious from hit-point
# loss, non-lethal damage or a coup de grâce; 759 carry "undead traits", which is a
# bundle the Bestiary defines once and every entry then refers to.
#
# Keys are the words stat blocks use. Values are the condition keys and the descriptors
# they cover; a descriptor is matched against what an EFFECT declares itself to be, so
# "immune to fear" stops a fear effect that would shake you and leaves the shaken you get
# from something else alone.
IMMUNITY_COVERS: dict[str, tuple[str, ...]] = {
    "sleep": ("sleep",),
    "paralysis": ("paralyzed", "paralysis"),
    "stun": ("stunned", "stun"),
    "fear": ("shaken", "frightened", "panicked", "cowering", "fear"),
    "mind-affecting": ("confused", "fascinated", "charm", "compulsion",
                       "mind-affecting"),
    "mind affecting": ("confused", "fascinated", "charm", "compulsion",
                       "mind-affecting"),
    "poison": ("poison", "nauseated", "sickened"),
    "disease": ("disease",),
    "bleed": ("bleed",),
    "fatigue": ("fatigued",),
    "exhaustion": ("exhausted", "fatigued"),
    "nausea": ("nauseated",),
    "blindness": ("blinded",),
    "deafness": ("deafened",),
    "death effects": ("death",),
    "energy drain": ("energy drain",),
    # The Bestiary's own bundle, expanded once here rather than in every consumer.
    "undead traits": ("sleep", "paralyzed", "paralysis", "stunned", "stun",
                      "disease", "poison", "fatigued", "exhausted",
                      "confused", "fascinated", "charm", "compulsion",
                      "mind-affecting", "bleed", "death", "nauseated", "sickened"),
    "construct traits": ("sleep", "paralyzed", "paralysis", "stunned", "stun",
                         "disease", "poison", "fatigued", "exhausted",
                         "confused", "fascinated", "charm", "compulsion",
                         "mind-affecting", "bleed", "death", "nauseated",
                         "sickened"),
    "elemental traits": ("sleep", "paralyzed", "paralysis", "stunned", "stun",
                         "poison", "bleed"),
}


def immunity_blocks(immunities, condition_key: str = "",
                    descriptors=()) -> str:
    """Which immunity stops this condition, or "" if none does.

    Answers with the immunity's own words so a refusal can print them. Both halves are
    consulted: the condition a creature cannot suffer, and the descriptors the effect
    declares itself to carry — an effect that says it is a fear effect is stopped by
    immunity to fear whatever condition it was going to apply.
    """
    key = (condition_key or "").strip().lower()
    said = {str(d).strip().lower() for d in (descriptors or ()) if str(d).strip()}
    for raw in immunities or ():
        name = " ".join(str(raw).split()).strip().lower()
        covers = IMMUNITY_COVERS.get(name)
        if covers is None:
            # An unlisted immunity still protects against its own name, so a homebrew
            # "immune to petrification" works the day it is written — the same
            # self-tagging courtesy `tags_for` extends to an unregistered condition.
            covers = (name,)
        if key and key in covers:
            return str(raw)
        if said & set(covers):
            return str(raw)
        # A stat block writes the noun and the condition table holds the adjective:
        # "immune to petrification" against the `petrified` condition. Matched on a
        # five-character stem, which is long enough that `sleep` does not answer for
        # `slept-in` and short enough that every inflection in the corpus lands.
        if key and len(name) >= 5 and (key.startswith(name[:5])
                                       or name.startswith(key[:5])):
            return str(raw)
    return ""

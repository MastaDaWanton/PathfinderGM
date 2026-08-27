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

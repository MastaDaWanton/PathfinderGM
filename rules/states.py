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
#
# `state.down.fallen` is the narrower half of `state.down`: a body on the floor whose
# story resolves on its own — it bleeds out, it stabilises, it is already dead. The
# other two members of the family are living creatures held in place, and the difference
# decides who gets quietly removed from the scene. Without it `tidy_the_fallen` aged a
# petrified enemy out as a corpse two turns after the fight, statue and all, and
# `downed.resolve` offered a paralyzed character a nap they would never wake from.
#
# The `recovery.*` family says what ENDS a state, which is a fact about the condition and
# so belongs here rather than in a list at each site that ends things. Four sites carried
# the same four names — heal, rest, the downed resolution and resurrection — and the
# copies had already drifted: travel forgot `stable`, and only resurrection is entitled
# to remove `dead`.
#
#   recovery.hit-points  being back above 0 hit points undoes it
#   recovery.rest        a night's sleep ends it: the stale states that otherwise
#                        quietly poison every roll for the rest of the campaign
#
# Sweeping an existing `state.*` family instead is the trap, and it is one keystroke
# from the obvious implementation: `state.unable` contains `dead`, so a night's sleep
# would raise a corpse; `state.held` contains `paralyzed`, so it would cure paralysis;
# `state.senses` contains `blinded` and `deafened`, which in 1e end only with a spell.
TAGS: dict[str, tuple[str, ...]] = {
    "dead":        ("state.down.dead", "state.down.fallen", "state.unable"),
    "dying":       ("state.down.dying", "state.down.fallen", "state.unable",
                    "recovery.hit-points"),
    "unconscious": ("state.down.unconscious", "state.down.fallen", "state.unable",
                    "recovery.hit-points"),
    "stable":      ("state.down.stable", "state.down.fallen", "state.unable",
                    "recovery.hit-points"),
    "petrified":   ("state.down.petrified", "state.unable"),
    # Helpless has always carried `can_act: False` in the condition row and no
    # `state.unable` tag, so the flag and the vocabulary disagreed about it: the tag
    # layer said a bound prisoner could act and the row said they could not.
    "helpless":    ("state.down.helpless", "state.unable"),
    "paralyzed":   ("state.unable.paralyzed", "state.held"),
    "pinned":      ("state.held.pinned", "recovery.rest"),
    "grappled":    ("state.held.grappled", "recovery.rest"),
    "stunned":     ("state.unable.stunned",),
    "dazed":       ("state.unable.dazed", "recovery.rest"),
    "cowering":    ("state.unable.cowering", "recovery.rest"),
    # Nauseated is impaired, not unable: 1e allows it "a single move action per turn"
    # and stops the rest. The condition row carried `can_act: False`, which the engine's
    # guard read as a block on attack, move AND check — denying the one action the rules
    # allow. What it stops is stated in BLOCKS rather than by a boolean that cannot say.
    "nauseated":   ("state.impaired.nauseated", "recovery.rest"),
    "staggered":   ("state.impaired.staggered", "recovery.rest"),
    "disabled":    ("state.impaired.disabled", "recovery.hit-points"),
    "fatigued":    ("state.impaired.fatigued",),
    "exhausted":   ("state.impaired.exhausted",),
    "sickened":    ("state.impaired.sickened", "recovery.rest"),
    "shaken":      ("state.fear.shaken", "recovery.rest"),
    "frightened":  ("state.fear.frightened", "recovery.rest"),
    "panicked":    ("state.fear.panicked", "recovery.rest"),
    "fascinated":  ("state.unable.fascinated", "recovery.rest"),
    "confused":    ("state.impaired.confused",),
    "blinded":     ("state.senses.blinded",),
    "deafened":    ("state.senses.deafened",),
    "dazzled":     ("state.senses.dazzled", "recovery.rest"),
    "invisible":   ("state.hidden.invisible",),
    "prone":       ("state.position.prone", "recovery.rest"),
    "flat-footed": ("state.position.flat-footed", "recovery.rest"),
    "bleed":       ("state.wound.bleeding",),
    "entangled":   ("state.held.entangled", "recovery.rest"),
    # The stances play has already minted. Buffs, not states: they are worn by choice.
    "blood armament": ("buff.stance.blood-armament",),
    "blood rage":     ("buff.stance.blood-rage",),
    "coagulated plate": ("buff.stance.coagulated-plate",),
    # The price of coming back: somebody paid the priests, and now the debt sits
    # on the character. Clockless — the world decides when it is called in.
    "life debt": ("state.obligation.life-debt",),
    # 1e's attitude track, in the book's own order. `rules/effectspec.py` has offered
    # an `attitude` effect type since the spell import — thirty-three spells set one,
    # charm person among them — and it shipped `engine=False` with the note "no check
    # in the app consults an attitude yet", because there was nowhere for the answer
    # to live. Here is the somewhere.
    #
    # Not under `state.*`: an attitude stops no action and impairs no roll. It is a
    # fact about how somebody feels towards you, and its whole job is to be READ — by
    # the brief, so the narrator writes the merchant as a merchant who likes you, and
    # by whatever later asks whether this creature would fight. And no `recovery.*`:
    # what ends a charm is the effect's own clock, not a night's sleep, and putting
    # one here would have every sweep in the app cure infatuation.
    "hostile":     ("attitude.hostile",),
    "unfriendly":  ("attitude.unfriendly",),
    "indifferent": ("attitude.indifferent",),
    "friendly":    ("attitude.friendly",),
    "helpful":     ("attitude.helpful",),
}

# The track in the book's order, worst to best. Ordered because the question asked of
# it is nearly always a comparison — "friendly or better" — and a set cannot answer it.
ATTITUDES: tuple[str, ...] = (
    "hostile", "unfriendly", "indifferent", "friendly", "helpful")


def attitude_of(actor, default: str = "") -> str:
    """Where this creature sits on the track, or `default` if nobody has said.

    One reader for one question, so no site ever matches `"friendly"` as a string —
    the same rule every other family here lives under.
    """
    for step in reversed(ATTITUDES):
        if actor is not None and actor.has_state(f"attitude.{step}"):
            return step
    return default


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


# What a state stops an actor DOING, as opposed to what it makes them.
#
# This replaces the `can_act` boolean that sat on the condition rows. A boolean has to
# answer "can this creature act?" with one bit, and 1e's incapacities are not all total:
# a nauseated character may take a single move action and nothing else, so the flag
# blocked all three of the ops the engine guards and denied them the one the rules
# allow. Naming the ops lets the vocabulary say what each state actually stops.
#
# The flag and the tag tree also drifted, because both were hand-written and nothing
# compared them: measured across the 31 shipped conditions they disagreed on three —
# `fascinated` (tagged unable, flagged able), `helpless` (flagged unable, untagged) and
# `nauseated` (flagged unable, and wrongly). There is now one list, and
# `test_the_vocabulary_is_the_only_authority_on_acting` keeps it the only one.
#
# Keys are tag prefixes, so an unregistered homebrew state under `state.unable.*`
# stops actions the day it is written without being added here.
ACTIONS: tuple[str, ...] = ("attack", "move", "check", "cast")

BLOCKS: dict[str, frozenset[str]] = {
    # Unable is total, and always has been: this is the family the ten conditions that
    # take no turn at all belong to.
    "state.unable": frozenset(ACTIONS + ("any",)),
    # "The only action such a character can take is a single move action per turn."
    "state.impaired.nauseated": frozenset(("attack", "check", "cast")),
}


def stops(tags, action: str = "any") -> bool:
    """Whether a state carrying `tags` stops `action`.

    `action` is one of ACTIONS, or "any" for the general question — may this creature
    take *any* action at all. "any" is answered only by a state that stops everything,
    which is why a nauseated character is not "unable" while still being refused an
    attack.

    Takes the tags an effect actually carries rather than re-deriving them from its
    key, because the two are not the same thing: an ability document may append its own
    tags on top of `tags_for` (`rules/engine.py`, `_apply_ability_document`), and
    `Actor.has_state` reads the carried tags. A second derivation here would be a
    second vocabulary — the exact fault this stage exists to remove.

    One question with one answer, asked by the turn gate (`play/views.py`), the intent
    guard (`rules/engine.py`) and the sheet alike. They used to answer it separately:
    a petrified character was handed a turn by the first, planned by the GM, and then
    refused by the second as a legality error — which regenerates rather than repairs,
    so the turn burned the retry loop and died as a 502 the player saw as a blank page.
    """
    want = (action or "any").strip().lower()
    return any(want in stopped and matches(str(tag), prefix)
               for tag in tags or ()
               for prefix, stopped in BLOCKS.items())


def blocking(keys, action: str = "any") -> str:
    """The condition key that stops `action`, or "" — for a caller holding only keys.

    Prefer `stops` with the effect's own tags where they are to hand.
    """
    return next((k for k in keys or () if stops(tags_for(k), action)), "")


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

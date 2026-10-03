"""Talking somebody round, by the book.

`rules/states.py` has held 1e's attitude track since the spell import, and said so:
thirty-three spells set an attitude, `effectspec` offered the type, and the note beside
it read "no check in the app consults an attitude yet". The track existed, the vocabulary
existed, the applicator existed — and the three skills a player actually reaches for did
nothing to it. `_op_check` rolled Diplomacy, printed the margin, awarded the XP for
beating a DC, and left the merchant exactly as hostile as they had been. A whole pillar of
the game ended at a number in a sentence.

Worse, the engine was already telling the model otherwise. The refusal that stops a plan
from simply declaring somebody helpful ends: "To move somebody by ordinary means, talk to
them and roll it: check skill=diplomacy, check skill=intimidate, check skill=bluff." That
was the app describing a feature it did not have.

**The rules, from the Core Rulebook, and only the rules.** No number here is invented:

  Diplomacy, Influence Attitude — a DC of 25/20/15/10/0 by the target's current attitude
  (hostile to helpful), plus their Charisma modifier. One minute of continuous talk. On a
  success the attitude improves one step, and one more step for every 5 the check beats
  the DC by, to a limit of **two steps**. Fail by 4 or less and nothing moves; fail by 5
  or more and it worsens one step. A shift lasts 1d4 hours. You may not try the same
  creature twice in 24 hours.

  Intimidate, Change Attitude — DC 10 + the target's Hit Dice + their Wisdom modifier,
  one minute of conversation. Success makes them act friendly for 1d6x10 minutes.

**What Bluff is not — and, since 2026-10-01, a house rule that it is.** The book does
not put Bluff on this track: a lie is an opposed check against Sense Motive, and even a
believed one "doesn't determine the course of action the deceived person takes"
(Ultimate Intrigue p.182). This module kept it off for that reason. The owner overruled
it on 2026-10-01: a believed lie about who you are moves the listener by how they feel
about what you claimed ("the king of a nation", to a man who hates the rich and powerful,
cools him), and a caught lie is a small loss. That is not a lever here — Bluff is never
an influence check, has no DC off this table and no cooldown — it is a consequence of a
lie the engine already rolls: `Engine._lie_lands`, with the direction read from
content/rules/claims.json and the size from `steps_for` below. Said here so the old
paragraph is not read as still true.

**The simplification, named.** After an intimidated creature's friendliness lapses, the
book has them treat you as unfriendly and possibly report you. That is not implemented:
there is no "when this effect ends" trigger in the engine — wards fire each round or when
struck — and inventing a third trigger for one rule is how a mechanism ossifies around a
special case. The friendliness runs out and they are whatever they were. docs/attitude.md
carries this as an open gap rather than a quiet one.
"""
from __future__ import annotations

import re

from . import states

# The track, worst to best. `states.ATTITUDES` is the one definition; this is a name for
# it so that reading this file does not send anybody looking.
TRACK = states.ATTITUDES

# Where a creature sits when nobody has said anything about them. The book's own default
# for an NPC with no reason to care either way, and the reason a shift is computed from
# `of()` rather than from the absence of a tag.
DEFAULT = "indifferent"

# Core Rulebook, Diplomacy: the DC to influence a creature's attitude, by the attitude it
# starts at, before its Charisma modifier.
INFLUENCE_DC = {"hostile": 25, "unfriendly": 20, "indifferent": 15,
                "friendly": 10, "helpful": 0, "devoted": 0}

# Where a check can take somebody: helpful, the top of the book's track. The step above
# it is not a check's to give (`moved` clamps here), it is regard's — see below.
TOP_BY_CHECK = "helpful"

# --- regard: how somebody stands towards the player over time ---------------------------
#
# Asked for 2026-09-24: *"their attitude toward me quantified ... I want to be able to
# talk with them and increase that attitude until they Idolize/Love me."* The book's track
# is a state a check or a spell sets for hours; it has no memory. Regard is the memory —
# a score from 0 to 100 kept on the person as one effect (`set_regard`), which the track
# falls back to when nothing is holding a step, and which the panel shows as a number.
#
# The shape is Stardew Valley's hearts and Persona's social ranks: a small gain for
# talking, capped per day so a conversation cannot be farmed in an afternoon; a larger
# gain or loss when a check actually lands; a gift counts. Bands are wide enough that a
# step is a relationship and not a good roll, and `devoted` — the top — takes weeks of
# being somebody's friend, which is what "idolize" ought to cost.
REGARD_MAX = 100
# (floor, step): the score at which each step begins. Indifferent starts at 35, so a
# stranger — nobody has said anything and no regard is held — reads as indifferent.
BANDS = ((0, "hostile"), (15, "unfriendly"), (35, "indifferent"),
         (55, "friendly"), (75, "helpful"), (90, "devoted"))
REGARD_PER_TALK = 2         # an exchange in conversation
TALKS_A_DAY = 3             # ...and no more than this many count in a day
REGARD_PER_STEP = 8         # a Diplomacy success, per step it moved them
REGARD_LOST_ON_FAILURE = 5  # a Diplomacy failure by 5 or more
REGARD_RESENTMENT = 5       # an Intimidate that worked: they are cowed, and they remember
REGARD_GIFT = 3             # something handed over freely
# The effect that holds the score: one key, one source, replaced whole on every change
# so the one applicator is the only writer and `has_state(states.REGARD)` is the
# question "has anybody's opinion of the player been recorded at all".
REGARD_KEY = "regard"
REGARD_SOURCE = "regard"

# "A creature's attitude cannot be shifted more than two steps up in this way."
MOST_STEPS_UP = 2

# How long a shift lasts, and how long the talking takes. Both the book's.
SHIFT_DICE = "1d4"          # hours
INFLUENCE_MINUTES = 1
# "You cannot use Diplomacy to influence a given creature's attitude more than once in a
# 24 hour period."
COOLDOWN_MINUTES = 24 * 60

# Intimidate, Change Attitude: DC 10 + Hit Dice + Wisdom modifier, and the duration of
# the friendliness it buys.
INTIMIDATE_BASE_DC = 10
INTIMIDATE_DICE = "1d6"     # x10 minutes

# The two skills that move the track as influence checks, and how each does it. Bluff is
# absent from THIS list — a believed lie moves the track as a consequence, not as an
# influence check with a DC from the table; the module docstring says how.
LEVERS = ("diplomacy", "intimidate")

# Where on the track somebody will walk out of here with you (`Engine._op_company`). The
# book's own words decide it rather than a feel: friendly is "will chat, advise, offer
# limited help", and going somewhere with you is the first of those; indifferent "doesn't
# much care" and has no reason to leave their afternoon.
#
# Named HERE and compared with `step_of`, not spelled in the engine as a pair of literals.
# That was the first cut and it is precisely the thing law one forbids — a reader matching
# attitude strings instead of asking the vocabulary — caught auditing this work against
# the contract rather than by any test, because the three-laws ratchet counts literal
# CONDITION keys and an attitude word is not one.
COMES_ALONG = "friendly"

# Where a companion's own life opens to the player (the owner, 2026-10-01: "Their wants
# should appear naturally locked behind their attitude toward you"; gm/confide.py). The
# book's words again: friendly "will chat, advise, offer limited help" — so at most a hint
# that something is on their mind; helpful "will take risks to help you" — so the thing
# itself. Named here for the reason COMES_ALONG is.
CONFIDES_A_HINT = "friendly"
CONFIDES = "helpful"

# The bottom of the track: somebody who will act against you. Named HERE, like the step
# above, so no reader anywhere spells an attitude — the three-laws ratchet counts literal
# keys per file and caught the first cut of the watch's recognition doing exactly that.
HOSTILE = TRACK[0]


def of(actor, default: str = DEFAULT) -> str:
    """Where this creature sits on the track. Asked through the vocabulary, always.

    A step a check or a spell is holding answers first; with none held, the standing
    relationship answers (`regard_of`), so a shift that has run out leaves somebody
    where their history with the player puts them rather than back at indifferent."""
    held = states.attitude_of(actor, default="")
    if held:
        return held
    if actor is not None and actor.has_state(states.REGARD):
        return band_of(regard_of(actor))
    return default


def _regard_effect(actor):
    for e in getattr(actor, "effects", None) or ():
        if getattr(e, "key", "") == REGARD_KEY and states.REGARD in (getattr(e, "tags", ()) or ()):
            return e
    return None


def regard_of(actor) -> int:
    """The score, 0 to 100. A person nobody has recorded an opinion for sits at the
    floor of indifferent, which is where a stranger starts."""
    e = _regard_effect(actor)
    if e is None:
        return floor_of(DEFAULT)
    return max(0, min(REGARD_MAX, int(getattr(e, "amount", 0) or 0)))


def band_of(regard: int) -> str:
    """The step a score sits in."""
    step = BANDS[0][1]
    for floor, name in BANDS:
        if int(regard) >= floor:
            step = name
    return step


def floor_of(step: str) -> int:
    """Where a step begins on the score."""
    return next((floor for floor, name in BANDS if name == str(step or "").lower()),
                BANDS[0][0])


def set_regard(actor, value: int, source: str, *, payload: dict | None = None):
    """The one writer. Replaces the effect whole, keeping the day-count payload unless
    a new one is given, and returns the effect."""
    from .activeeffect import ActiveEffect

    old = _regard_effect(actor)
    kept = dict(getattr(old, "payload", None) or {}) if old is not None else {}
    if payload is not None:
        kept.update(payload)
    actor.remove_effects(source=REGARD_SOURCE)
    eff = ActiveEffect(name="regard", kind="bond", key=REGARD_KEY, source=REGARD_SOURCE,
                       origin=str(source or REGARD_SOURCE), duration="until-dismissed",
                       amount=max(0, min(REGARD_MAX, int(value))),
                       tags=(states.REGARD,), payload=kept)
    actor.apply_effect(eff)
    return eff


def nudge_regard(actor, delta: int, source: str) -> tuple[int, int]:
    """Move the score by `delta`; returns (before, after)."""
    before = regard_of(actor)
    after = max(0, min(REGARD_MAX, before + int(delta)))
    if after != before or _regard_effect(actor) is None:
        set_regard(actor, after, source)
    return before, after


def talked_today(actor, day: int) -> bool:
    """Record one exchange today; True if it still counts towards regard.

    The cap is per person per day — three exchanges — so a conversation is worth
    having and cannot be farmed by saying "hello" thirty times."""
    e = _regard_effect(actor)
    payload = dict(getattr(e, "payload", None) or {}) if e is not None else {}
    if int(payload.get("day", -1)) != int(day):
        payload = {"day": int(day), "talks": 0}
    if int(payload.get("talks", 0)) >= TALKS_A_DAY:
        return False
    payload["talks"] = int(payload.get("talks", 0)) + 1
    set_regard(actor, regard_of(actor), "talk", payload=payload)
    return True


def regard_said(name: str, before: int, after: int) -> str:
    """The tell for a change of standing, in words: a step crossed, or nothing.

    The number is the panel's to show and never the narrator's to hear — the third law.
    A change that stays within a step is carried on the outcome's effects and said
    nowhere, because "Korgath thinks a little better of you" after every sentence is a
    tic, and a step crossed is the one change worth a sentence."""
    was, now = band_of(before), band_of(after)
    if was == now:
        return ""
    return said(name, was, now)


def step_of(name: str) -> int:
    """The track as a number, so a shift is arithmetic. -1 for a word off the track."""
    try:
        return TRACK.index(str(name or "").strip().lower())
    except ValueError:
        return -1


def moved(name: str, steps: int) -> str:
    """Where a creature ends up, `steps` along the track from where they are.

    Clamped at both ends: there is nothing past helpful and nothing below hostile, and a
    check that would drive somebody off either end simply leaves them there.
    """
    at = step_of(name)
    if at < 0:
        at = step_of(DEFAULT)
    # Clamped at helpful, not at the end of the track: `devoted` is regard's to give.
    top = step_of(TOP_BY_CHECK)
    return TRACK[max(0, min(top, at + int(steps)))]


def influence_dc(target) -> int:
    """The Diplomacy DC for this creature, as the book states it.

    Computed by the engine and never proposed by the GM. This is a rule with a table
    behind it, not a judgement about how hard something looks, and the whole arrangement
    of this app is that the model proposes and the engine disposes — a plan that could
    name its own DC for talking somebody round could talk anybody into anything.
    """
    return INFLUENCE_DC.get(of(target), INFLUENCE_DC[DEFAULT]) + _mod(target, "cha")


def intimidate_dc(target) -> int:
    """Core Rulebook, Intimidate: 10 + Hit Dice + Wisdom modifier."""
    return INTIMIDATE_BASE_DC + _hit_dice(target) + _mod(target, "wis")


def dc_basis(target, skill: str) -> str:
    """Where `influence_dc` / `intimidate_dc` got their number, in the book's terms —
    "indifferent 15, Cha +2" — for the record a check leaves (`dc.ResolvedDC.basis`).

    Until 2026-10-03 the engine's own attitude DC was logged as a bare "DC 17", which
    could not be told apart from a number somebody chose; the clerk's average-band 10
    (playtest item 23) sat in the same log with nothing to show which was the book's."""
    if skill == "intimidate":
        return (f"Intimidate: {INTIMIDATE_BASE_DC} + {_hit_dice(target)} Hit Dice, "
                f"Wis {_mod(target, 'wis'):+d}")
    step = of(target)
    return f"{step} {INFLUENCE_DC.get(step, INFLUENCE_DC[DEFAULT])}, Cha {_mod(target, 'cha'):+d}"


def steps_for(margin: int) -> int:
    """How far a Diplomacy check moves somebody, from how far it beat the DC.

    One step for the success, one more per 5 over, capped at two up. Failure by 4 or less
    moves nobody; by 5 or more it costs a step — which is the half that makes the check
    worth thinking about rather than worth spamming.
    """
    margin = int(margin)
    if margin >= 0:
        return min(MOST_STEPS_UP, 1 + margin // 5)
    return -1 if margin <= -5 else 0


def _mod(actor, ability: str) -> int:
    """An ability modifier off whatever kind of sheet this is, or 0.

    Fails soft on purpose: a creature with no scores at all is every hand-written
    townsfolk's ancestor and a great many bestiary blocks, and a missing modifier must
    leave the book's base DC standing rather than raise.
    """
    fn = getattr(actor, "ability_mod", None)
    if callable(fn):
        try:
            return int(fn(ability))
        except Exception:
            return 0
    score = getattr(actor, "ability_score", None)
    if callable(score):
        try:
            return (int(score(ability)) - 10) // 2
        except Exception:
            return 0
    return 0


def _hit_dice(actor) -> int:
    """How many Hit Dice this creature has. A character's level is their Hit Dice, and a
    creature's stat block says so directly; either way, never less than one."""
    for name in ("hit_dice", "hd", "level"):
        got = getattr(actor, name, None)
        if callable(got):
            try:
                got = got()
            except Exception:
                got = None
        try:
            if got is not None:
                return max(1, int(got))
        except (TypeError, ValueError):
            continue
    return 1


# Asked outright for their name, who answers. Not a check in the book — the Core Rulebook
# has no roll for "what are you called" — so the track answers instead of a die, which is
# the whole point of having a track: indifferent is the default and a stranger with no
# reason to care will still tell you their name, while somebody who has no time for you or
# wants you gone will not. A refusal was reported as a bug on 2026-09-19 ("stranger on the
# stairs refuses to give his name") and the player's own earlier ruling was that refusing
# is fine — what was wrong was that it happened for no reason and could not be changed.
# Now it is a fact about the creature and Diplomacy moves it.
TELLS_NAME_FROM = "indifferent"


def tells_their_name(actor) -> bool:
    """Does this creature give their name for the asking?

    Indifferent or better, yes. Unfriendly or hostile, no — and `influence` is the
    documented way through, which is what makes the refusal actionable rather than a
    dead end.
    """
    return step_of(of(actor)) >= step_of(TELLS_NAME_FROM)


# --- harm: what hurting somebody does to how they feel -----------------------------------
#
# Measured 2026-09-28 (item 22.3): Bobby's Burning Hands caught a man and nothing about the
# man changed — no fight, no attitude, and a swing with a rapier moved nobody's attitude
# either. No rule anywhere turned harm into feeling. The PF1e book gives no line for "a
# creature you attack becomes hostile" (the Diplomacy table lists DCs only), so the shape
# is the engine's own, from the research of docs/design-e-magic.md §4.5:
#
#   * A stranger harmed moves to hostile, held as an ActiveEffect through the one
#     applicator (`Engine._set_attitude`, until dismissed). Regard drops to the hostile
#     floor with it, and nothing recovers it with time: only talk mends it (owner, Q36) —
#     `provocation.recover` only returns what `note_grudge` recorded, and harm records
#     none.
#   * Somebody on your side (travelling with you, or friendly and better) takes no step:
#     they lose HARMED regard (owner, Q35), RimWorld's "Harmed me" at the same weight as
#     its "Insulted", in the mapping `rules/provocation.py` already made.
#   * Already hostile: nothing more to lose.
#
# **Harm counts only when the source is perceived** (owner, Q34, for swords and spells
# alike — Q37). "If i shoot a blowdart from concealment or [pass] a stealth check then
# nobody saw that I did it so no one dislikes me for it or tries to fight me." The rule
# the book gives for attacking from hiding, applied to both doors (`perceived` below):
#
#   * Stealth (aonprd.com/Skills.aspx?ItemName=Stealth): "Your Stealth immediately ends
#     after you make an attack roll, whether or not the attack is successful (except when
#     sniping ...)". Sniping: "If you've already successfully used Stealth at least 10 feet
#     from your target, you can make one ranged attack and then immediately use Stealth
#     again. You take a -20 penalty on your Stealth check to maintain your obscured
#     location."
#   * Invisibility (aonprd.com/Rules.aspx?ID=431): "If an invisible creature strikes a
#     character, the character struck knows the location of the creature that struck him."
#
# So a hidden attacker within 5 ft (a blow in reach) is perceived; one 10 ft or more away
# who is invisible is not; one hidden by Stealth rolls Stealth at -20 against the victim's
# Perception, and stays unidentified on a result at least as high. A spell is held to the
# same rule as an arrow. Not sourced, and not applied: whether casting's verbal and
# somatic components give a hidden caster away (a later book's rule; not fetched).

from .provocation import INSULT as _INSULT  # noqa: E402

HARMED = _INSULT  # "Harmed me" weighs what "Insulted" does (RimWorld −15 each)

# **Charm and magical sleep, harm to an unfriendly eye only** (owner, 2026-09-28, the
# register's §3.4 row for I3: "yes if the people who saw are not friendly"). Lane E left
# both out — "a charm opening a fight would be absurd" (docs/design-e-magic.md §4.5) — and
# the owner ruled they count: when the source is perceived, AND only for the witnesses
# (the victim included) whose attitude towards the caster is below friendly. A friendly or
# helpful onlooker, and anybody travelling with you, does not turn on you for it. The
# families are the tags these conditions self-tag to (`charmed` and `asleep` are not in
# `states.TAGS`), asked as prefixes like every other.
#
# Magical sleep in the shipped spells lands as `unconscious`/`helpless` with the spell's
# own note saying it is sleep ("magical slumber", "asleep"), so a sleep effect is known by
# its effect document (`_sleep_spec`), the way `states.IMMUNITY_COVERS` knows a sleep
# effect by what it declares itself to be — measured over the corpus 2026-09-29: sleep,
# deep slumber, cloak of dreams, forgetful slumber, symbol of sleep and touch of slumber
# (six), and not night terrors, whose "ruined sleep" lands fatigue. A charm is known by
# the book's own classification, the enchantment (charm) subschool: its mechanics are
# prose (the charm lands later, through the mind gate), so there is no condition spec to
# read.
UNFRIENDLY_EYES_ONLY = ("condition.charmed", "condition.asleep", "condition.sleeping")

# The families a harmful or unpleasant condition sits in — asked as PREFIX questions of
# the vocabulary, never by name (the first law). Nauseated and sickened are the owner's
# own examples (`state.impaired`); charm and sleep since I3, behind the witness gate.
HARMFUL_STATES = ("state.down", "state.unable", "state.held", "state.impaired",
                  "state.fear", "state.senses", "state.wound", "state.helpless",
                  "state.position.prone", *UNFRIENDLY_EYES_ONLY)

_SLEEP_KEYS = frozenset(states.IMMUNITY_COVERS["sleep"])
_SLEEP_NOTE = re.compile(r"\b(?:slumber|asleep|sleeping|sleeps|falls? asleep)\b", re.I)


def harmful_condition(key: str) -> bool:
    """Whether landing this condition is harm, asked of its tags."""
    return any(states.matches(t, fam) for t in states.tags_for(str(key or ""))
               for fam in HARMFUL_STATES)


def gated_condition(key: str) -> bool:
    """Whether this condition is harm only to an unfriendly eye (charm, magical sleep)."""
    return any(states.matches(t, fam) for t in states.tags_for(str(key or ""))
               for fam in UNFRIENDLY_EYES_ONLY)


def _sleep_spec(spec: dict) -> bool:
    """An `apply_condition` that is a sleep effect: it lands a sleep condition by name, or
    lands unconscious or helpless and says, in its own note, that the creature sleeps."""
    key = str(spec.get("target") or "").strip().lower()
    if key in _SLEEP_KEYS:
        return True
    return key in ("unconscious", "helpless") and bool(_SLEEP_NOTE.search(
        str(spec.get("note") or "")))


def resents(actor) -> bool:
    """Whether this creature, seeing the caster charm or put somebody to sleep, holds it
    against them: below friendly, and not travelling with the party (owner's ruling)."""
    if actor is None or getattr(actor, "is_pc", False):
        return False
    if actor.has_state(states.TRAVELS_WITH_YOU):
        return False
    return step_of(of(actor)) < step_of(COMES_ALONG)


def harm_of(spell, caster_level: int) -> str:
    """How casting this spell on somebody harms them: "harm" when it rolls damage or lays
    a harmful condition on a failed save (Q34); "gated" when its only harm is a charm or a
    magical sleep, which counts only before an unfriendly eye (`resents`); "" when it does
    no harm. Invisibility's own definition of an attack is the line — "any spell
    targeting a foe or whose area or effect includes a foe" — with the owner's narrowing
    to harm."""
    from . import spells as spells_mod

    plan = spells_mod.casting_plan(spell, caster_level)
    if plan.get("kind") == "damage" and plan.get("dice"):
        return "harm"
    found = {"harm": False, "gated": False}

    def walk(specs) -> None:
        specs = [s for s in specs or [] if isinstance(s, dict)]
        # Sleep lands as a pair — unconscious ("magical slumber") and helpless, the second
        # with no note of its own — so a branch that is a sleep effect is sleep throughout.
        asleep = any(str(s.get("type", "")) == "apply_condition" and _sleep_spec(s)
                     for s in specs)
        for spec in specs:
            kind = str(spec.get("type", ""))
            if kind == "apply_condition":
                key = spec.get("target", "")
                if gated_condition(key) or _sleep_spec(spec) or (
                        asleep and str(key).strip().lower() in ("unconscious", "helpless")):
                    found["gated"] = True
                elif harmful_condition(key):
                    found["harm"] = True
            if kind == "damage" and spec.get("dice"):
                found["harm"] = True
            for key in ("on_failure", "on_success", "effects", "options"):
                walk(spec.get(key))
    walk(spells_mod.effects_at(spell, caster_level))
    if found["harm"]:
        return "harm"
    if found["gated"] or str(getattr(spell, "subschool", "") or "").lower() == "charm":
        return "gated"
    return ""


def harmful_spell(spell, caster_level: int) -> bool:
    """Whether casting this spell on somebody can harm them at all (`harm_of`)."""
    return bool(harm_of(spell, caster_level))


def perceived(engine, by, victim, *, rolls: list | None = None) -> bool:
    """Whether `victim` perceives who harmed them — the sniping rule above.

    Rolls (hidden, the engine's own dice) are appended to `rolls` when there is a Stealth
    contest, so the outcome carries them. A caller that suspends mid-resolution asks once
    and keeps the answer: a resume must not roll the contest again."""
    if by is None or victim is None or not by.has_state("state.hidden"):
        return True
    gap = engine._gap_ft(by, victim) if hasattr(engine, "_gap_ft") else None
    if gap is None:
        # No map: the zones say whether it was a blow in reach.
        zone = engine.scene.zones.get(victim.ref if by.is_pc else by.ref, "near")
        close = zone == "engaged"
    else:
        close = gap <= 5
    if close:
        return True
    if by.has_state("state.hidden.invisible"):
        return False
    from .dice import Modifier

    stealth = engine.dice.d20(list(by.skill_modifiers("stealth"))
                              + [Modifier(-20, "sniping, to stay hidden")],
                              label=f"{by.name} Stealth, sniping", visibility="hidden")
    notice = engine.dice.d20(list(victim.skill_modifiers("perception")),
                             label=f"{victim.name} Perception", visibility="hidden")
    if rolls is not None:
        rolls.extend([stealth.as_dict(), notice.as_dict()])
    return notice.total > stealth.total


def harmed(engine, victim, by, source: str, *, seen: bool | None = None,
           gated: bool = False) -> dict | None:
    """What being harmed by `by` does to how `victim` stands towards the player, through
    the one applicator. Returns the effect record (the tell is `harm_said`), or None when
    nothing moves: `by` is not the player (attitudes are towards the party, and the app
    keeps no per-observer ones), the victim is the player, is `by`, or is dead, or was
    already hostile.

    `seen` is `perceived(...)`'s answer when the caller already has it; asked here
    otherwise. Unseen harm changes no attitude and returns a `harm_unseen` record: the
    victim knows they were hurt, not by whom.

    `gated` is harm that only an unfriendly eye resents — a charm, a magical sleep
    (`harm_of` == "gated"): a victim who is friendly or better, or travels with you, is
    not moved by it at all (owner's ruling; `resents`)."""
    if victim is None or by is None or victim is by or not getattr(by, "is_pc", False):
        return None
    if getattr(victim, "is_pc", False) or victim.has_state("state.down.dead"):
        return None
    if gated and not resents(victim):
        return None
    if seen is None:
        seen = perceived(engine, by, victim)
    if not seen:
        return {"kind": "harm_unseen", "ref": victim.ref, "by": by.ref, "source": source}
    was = of(victim)
    if victim.has_state(states.TRAVELS_WITH_YOU) or step_of(was) >= step_of(COMES_ALONG):
        before, after = nudge_regard(victim, -HARMED, f"harmed by {by.name}")
        return {"kind": "attitude", "ref": victim.ref, "from": was, "to": of(victim),
                "why": "harmed", "regard": [before, after], "source": source}
    if was == HOSTILE:
        return None
    engine._set_attitude(victim, HOSTILE, None, source)
    return {"kind": "attitude", "ref": victim.ref, "from": was, "to": HOSTILE,
            "why": "harmed", "source": source}


def harm_said(record: dict | None, name: str) -> str:
    """The tell for a `harmed` record, in words (the third law)."""
    if not record:
        return ""
    if record.get("kind") == "harm_unseen":
        return f"{name} is hurt and cannot tell who did it."
    if record.get("regard"):
        before, after = record["regard"]
        line = regard_said(name, before, after)
        return line or f"{name} will not forget that."
    return said(name, record.get("from", DEFAULT), record.get("to", HOSTILE))


def said(who: str, was: str, now: str) -> str:
    """The tell, in words and never in numbers — the third law.

    The narrator is fed this and nothing else about the check: no DC, no margin, no step
    count. "Warmer towards you" is a thing a character can notice; "attitude +1" is not.
    """
    if was == now:
        return f"{who} is unmoved."
    # States, not movements. Written as movements — "warms to you" for friendly — the
    # line came out as "Grix cools: warms to you" the first time a threat moved somebody
    # DOWN the track to friendly, which is a sentence that says nothing. The direction is
    # the verb; the phrase is where they have ended up.
    phrase = {
        "hostile": "wants you gone, and is past talking",
        "unfriendly": "has no time for you",
        "indifferent": "is neither here nor there about you",
        "friendly": "is well disposed towards you",
        "helpful": "is on your side",
    }.get(now, now)
    verb = "warms" if step_of(now) > step_of(was) else "cools"
    return f"{who} {verb}: {phrase}."

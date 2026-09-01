"""Checking the GM's *choices* against what the player actually said.

The four validation checks in `rules/intents.py` ask whether an intent is legal. They
cannot ask whether it is sensible, and in play that turned out to be the bigger problem
once the plumbing worked. Observed against llama3.1:8b:

  * the player leaned on a gate post and asked a question, and the GM tripped the man;
  * the player said "drive my rapier into the man holding me" and the GM chose *overrun*,
    a manoeuvre that deals no damage at all;
  * the player wrote "a guild bravo steps out of the dark" and got two of them.

None of these is illegal. All three are detectable, because the player's own words are
evidence about what should have happened — and detecting mechanically then repairing
narrowly is the only shape of fix that has ever held on this project.

Two kinds of finding:

  **corrections** are applied silently and logged. Used where the right answer is
  unambiguous — dropping a manoeuvre the player never asked for leaves an ordinary
  attack, which is what they described.

  **objections** send the turn back for one targeted retry. Used where we can tell the
  GM is wrong but not what it should have done instead.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# --- What the player's words indicate -------------------------------------------------

# Deliberately narrow. A false positive here costs the player a turn, so every cue has to
# be something that only means what it says.
VIOLENCE = re.compile(
    r"\b(attack|attacks|attacking|strike|strikes|stab|stabs|stabbing|swing|swings|"
    r"slash|slashes|cut|cuts|kill|kills|shoot|shoots|fire at|fight|fights|fighting|"
    r"charge|charges|lunge|lunges|punch|punches|kick|kicks|hit|hits|run (?:him|her|them|it) through|"
    r"go for (?:him|her|them|it)|draw (?:my|the|her|his) (?:blade|sword|rapier|dagger|weapon|steel)|"
    r"drive (?:my|the) \w+ into|put (?:my|the) \w+ (?:in|into|through))\b",
    re.I,
)

# Social or quiet action, used only to decide that a turn was *not* violent.
PEACEFUL = re.compile(
    r"\b(ask|asks|say|says|tell|tells|talk|talks|speak|speaks|greet|greets|question|"
    r"questions|whisper|whispers|offer|offers|buy|buys|haggle|persuade|persuades|lie|"
    r"explain|explains|listen|listens|look|looks|watch|watches|examine|examines|"
    r"search|searches|wait|waits|walk|walks|follow|follows|read|reads|rest|"
    r"introduce|apologise|apologize|thank|thanks|nod|nods|smile|smiles)\b",
    re.I,
)

# Cues that name a specific manoeuvre. The player saying "sweep his legs" is asking for a
# trip; the GM answering with an overrun is not a matter of taste.
MANOEUVRE_CUES: dict[str, re.Pattern] = {
    "trip": re.compile(r"\b(trip|sweep|sweeps|hook (?:his|her|their|its) (?:leg|legs|ankle)|"
                       r"knock (?:him|her|them|it) (?:down|off (?:his|her|their|its) feet)|"
                       r"take (?:his|her|their|its) legs)\b", re.I),
    "grapple": re.compile(r"\b(grapple|grapples|grab|grabs|tackle|tackles|wrestle|wrestles|"
                          r"hold (?:him|her|them|it) down|pin (?:him|her|them|it)|take hold of)\b", re.I),
    "disarm": re.compile(r"\b(disarm|disarms|knock (?:the|his|her|their) \w+ (?:from|out of)|"
                         r"strike (?:the|his|her) \w+ from (?:his|her|their) (?:hand|hands|grip))\b", re.I),
    "bull rush": re.compile(r"\b(shove|shoves|barge|barges|bull rush|drive (?:him|her|them|it) back|"
                            r"push (?:him|her|them|it) back)\b", re.I),
    "overrun": re.compile(r"\b(overrun|run (?:him|her|them|it) over|barrel past|"
                          r"push (?:past|through) (?:him|her|them|it))\b", re.I),
    "sunder": re.compile(r"\b(sunder|sunders|break (?:his|her|their|the) \w+|smash (?:his|her|their|the) \w+|"
                         r"shatter)\b", re.I),
    "steal": re.compile(r"\b(steal|steals|lift (?:his|her|their) \w+|pick (?:his|her|their) pocket|"
                        r"snatch)\b", re.I),
    "dirty trick": re.compile(r"\b(dirty trick|throw (?:sand|dirt|dust)|blind (?:him|her|them|it))\b", re.I),
}

# The action is plainly meant to wound: a manoeuvre would be the wrong answer.
WOUNDING = re.compile(
    r"\b(stab|stabs|run (?:him|her|them|it) through|drive (?:my|the) \w+ (?:in|into)|"
    r"put (?:my|the) \w+ (?:in|into|through)|cut|cuts|slash|slashes|"
    r"open (?:his|her|their) throat|kill|kills|skewer)\b",
    re.I,
)

@dataclass
class Finding:
    kind: str          # what was wrong
    message: str       # for the log, and for a repair call if it is an objection
    intent_id: str = ""


@dataclass
class Review:
    corrections: list[Finding] = field(default_factory=list)
    objections: list[Finding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.objections

    def as_log(self) -> list[str]:
        return ([f"corrected: {c.message}" for c in self.corrections]
                + [f"objected: {o.message}" for o in self.objections])


# The params that say what a turn *is*. `dc` is deliberately excluded: the GM re-rolls a
# difficulty band every turn, so comparing full params never matched and the repeat went
# undetected even when the reason clause was word for word identical.
_IDENTIFYING = ("skill", "manoeuvre", "template", "save", "condition", "zone")


def _signature(intents) -> list[tuple]:
    """What a turn's intents amount to, for comparing one turn against the last."""
    return [
        (i.op, i.actor, str(i.target), (i.because or "").strip().lower(),
         tuple(str(i.params.get(k, "")).lower() for k in _IDENTIFYING))
        for i in intents
    ]


def review(player_text: str, intents, scene=None, previous=None) -> Review:
    """Compare what the GM decided against what the player asked for."""
    out = Review()
    text = player_text or ""
    violent = bool(VIOLENCE.search(text))
    peaceful = bool(PEACEFUL.search(text))

    # 0. The same turn over again. Measured: the player said "two guild bravos come round
    #    the corner, I turn and fight" and the GM replayed the previous turn — another
    #    Stealth check, carrying the previous turn's reason, "going over the wall while
    #    the lamp is away". The player's words had changed completely and the GM had not
    #    read them.
    #    Only when the repeat has mechanics in it. A run of social turns is narrate_only
    #    after narrate_only, legitimately — the live session died here when the player
    #    politely declined a trainer and the GM's "same" turn was the same *nothing*.
    #    Rolling the same check again is the GM not reading; saying nothing twice is
    #    just two quiet turns.
    if (previous and _signature(intents) == list(previous)
            and any(i.op != "narrate_only" for i in intents)):
        out.objections.append(Finding(
            "repeats-the-last-turn",
            f"you have proposed exactly the same thing as last turn, but the player "
            f"has said something new: {_quote(text)}. Read what they just did and "
            f"respond to that.",
        ))
        return out

    for intent in intents:
        if intent.op == "attack":
            man = intent.params.get("manoeuvre")

            # 1. Violence in a turn that contained none. The player asked a question and
            #    the GM tripped the man; there is no way to guess what it should have
            #    done instead, so the turn goes back.
            if not violent and peaceful and (scene is None or not scene.in_encounter):
                out.objections.append(Finding(
                    "unprovoked",
                    f"the player did not attack anyone — they wrote "
                    f"{_quote(text)}. Do not resolve an attack or a combat manoeuvre "
                    f"on a turn where nobody swung. If the moment is only talk, use "
                    f'{{"op": "narrate_only"}}.',
                    intent.id,
                ))
                continue

            if not man:
                continue

            # 2. A manoeuvre the player did not ask for, on an action plainly meant to
            #    wound. Dropping it leaves an ordinary attack, which is what they
            #    described, so this is corrected rather than argued about.
            cue = MANOEUVRE_CUES.get(man)
            asked_for_this = bool(cue and cue.search(text))
            asked_for_other = next(
                (k for k, rx in MANOEUVRE_CUES.items() if k != man and rx.search(text)),
                None,
            )
            if asked_for_this:
                continue
            if asked_for_other:
                intent.params["manoeuvre"] = asked_for_other
                out.corrections.append(Finding(
                    "wrong-manoeuvre",
                    f"player described a {asked_for_other}, GM chose {man}", intent.id))
            elif WOUNDING.search(text):
                intent.params.pop("manoeuvre")
                out.corrections.append(Finding(
                    "manoeuvre-for-a-wound",
                    f"player meant to wound, GM chose {man}; resolved as a plain attack",
                    intent.id))
            else:
                # The player named no manoeuvre at all. A manoeuvre is a specific
                # tactical choice with its own costs, and choosing one unasked changes
                # what the player's action *was* — so a plain attack is what they
                # described and a plain attack is what they get.
                #
                # Measured: "I attack the beast" came back as an overrun on five
                # consecutive attempts and the turn died on "attack: a overrun needs a
                # target". The previous rule only dropped an unrequested manoeuvre when
                # the player used an explicitly wounding verb — "stab", "cut", "kill" —
                # and "attack" is not one of them, so the commonest sentence in the game
                # fell through every branch.
                #
                # This only ever runs on the player's turn. `npc_turn` does not go
                # through `judgement.review`, so a thug may still choose to grapple.
                intent.params.pop("manoeuvre")
                out.corrections.append(Finding(
                    "manoeuvre-nobody-asked-for",
                    f"player did not describe a manoeuvre, GM chose {man}; resolved as "
                    f"a plain attack", intent.id))

        # There is deliberately no check on how many creatures a spawn creates. An
        # earlier version read the count out of the player's sentence and overrode the
        # GM with it, which had the boundary backwards: the player says what their
        # character does, and how many enemies are round the corner is the GM's to
        # decide from the world. `play/player_input.py` now stops that shape of input
        # reaching here at all.

    return out


_BARE_REF = re.compile(r"(?<![\w/])(c\d+|pc)\b(?!\s*[\"':])", re.I)


def name_refs(text: str, scene) -> str:
    """Replace bare refs in player-facing prose with the names they stand for.

    Observed: "the two bravos freeze, but c1 looks up from under their saps". Refs are
    the protocol's plumbing — they exist so the GM cannot invent people — and a player
    should never see one. Substituting is unambiguous, so it is done rather than argued
    about.
    """
    if not text or scene is None:
        return text

    def swap(m: re.Match) -> str:
        ref = m.group(1).lower()
        actor = getattr(scene, "actors", {}).get(ref)
        if actor is None:
            return m.group(0)
        return "you" if actor.is_pc else actor.name

    return _BARE_REF.sub(swap, text)


# A ref the GM invented for someone it wanted to exist: "thug1", "bravo_2", "guard1".
_INVENTED_REF = re.compile(r"^[a-z][a-z_]{2,}[ _-]?\d*$", re.I)

# What the player's words suggest the newcomers are. The animal cue is first because it
# is the more specific claim: "the guard dog" contains "guard", and with the human cue
# first the dog came out a watchman.
_TEMPLATE_CUES = (
    (re.compile(r"\b(dog|hound|mastiff)\b", re.I), "guard dog"),
    (re.compile(r"\b(watch|watchman|watchmen|guard|guards|soldier)\b", re.I), "watchman"),
    # Civilians the cast ledger introduces fight like the commoners they are —
    # promoting "the Kelvaxian merchant" into a warrior statblock would make
    # every shopkeeper a bruiser.
    (re.compile(r"\b(guildhand|clerk|servant|porter|merchant|trader|innkeeper|"
                r"barkeep|bartender|peddler|farmer|fisherman|beggar|urchin|"
                r"scribe|artisan)\b", re.I), "guildhand"),
)


def _can_be_fought(actor) -> bool:
    """Whether this creature is a plausible target for a fresh attack.

    "Not dead" was the first version, and the 2026-08-22 playtest showed why it is not
    enough: the only actor in the scene was the gatekeeper dying at 0 hp — dragged along
    from three scenes back — and every attack on the people the narration described was
    filled onto him. A man bleeding out on the ground is not the obvious reading of "I
    attack"; being the only body in the room must not make him one.

    The four literal keys this used to name were `state.down` minus the two it forgot,
    so a petrified thug at full hit points was a plausible target and "I attack" filled
    onto a statue — the same shape as the gatekeeper, by a different route.
    """
    if int(getattr(actor, "hp", 1)) <= 0:
        return False
    return not actor.has_state("state.down")


# Ops whose subject is a person and whose unnamed subject is the player. `attack` is
# deliberately absent: who you are hitting is never obvious from the op alone.
_SELF_OPS = {"heal", "temp_hp", "rest", "eat", "drink", "forage", "condition",
             "ability_damage", "resource", "give"}


def fill_obvious_targets(raw_intents, scene) -> list:
    """Give an attack the only creature it could possibly mean, before validation sees it.

    Run *before* `engine.validate`, and that placement is the whole point. The engine
    refuses an untargeted manoeuvre — correctly, it cannot guess who — with a `legality`
    error, and legality errors regenerate rather than repair. Measured in live play: "I
    attack the beast" produced an untargeted overrun and died on "attack: a overrun needs
    a target" five attempts running, with a single hostile standing in front of the
    character. Putting the repair in `review` did nothing at all, because `review` runs
    after the validation that had already killed the turn.

    Narrow on purpose. One candidate is not a guess; two is a choice, and choosing for the
    player is worse than asking them.
    """
    if scene is None or not isinstance(raw_intents, list):
        return raw_intents

    pc = scene.pc()

    # Ops that land on a person and default to the player when the GM names nobody.
    # Measured: "I go to my room, lock the door, and go to sleep" came back with an
    # untargeted `heal` beside the rest, and the whole turn died on "heal: needs
    # somebody to heal" — so being tired and unhurt made it impossible to go to bed.
    # There is no ambiguity to protect here the way there is with an attack: a heal
    # nobody is aimed at, on a turn the player spent resting, is aimed at the player.
    if pc is not None:
        filled = []
        for raw in raw_intents:
            if (isinstance(raw, dict)
                    and str(raw.get("op", "")).strip().lower() in _SELF_OPS
                    and not raw.get("actor") and not raw.get("target")
                    and not (raw.get("params") or {}).get("to")):
                raw = dict(raw, actor=pc.ref)
            filled.append(raw)
        raw_intents = filled

    candidates = [r for r, a in scene.actors.items()
                  if not a.is_pc and _can_be_fought(a)
                  and (pc is None or r != pc.ref)]
    if len(candidates) != 1:
        return raw_intents

    out = []
    for raw in raw_intents:
        if (isinstance(raw, dict) and str(raw.get("op", "")).strip().lower() == "attack"
                and not raw.get("target")
                and not (raw.get("params") or {}).get("to")):
            raw = dict(raw, target=candidates[0])
        out.append(raw)
    return out


# Starting a fight, said by the player about themselves. Deliberately narrower than the
# outcome-claim list: this creates a creature and an initiative order, so it must fire on
# a declaration and nothing else.
_VIOLENCE = re.compile(
    r"\b(?:attack|attacks|attacking|hit|hits|hitting|strike|strikes|striking"
    r"|punch|punches|punching|stab|stabs|stabbing|slash|slashes|slashing"
    r"|swing at|swings at|swinging at|swinging|draw on|draws on|drawing on"
    r"|charge|charges|charging|rush|rushes|rushing|jump|jumps|jumping"
    r"|tackle|tackles|tackling|grapple|grapples|grappling|shove|shoves|shoving"
    r"|throttle|throttles|throttling|pick a fight|picks a fight|picking a fight"
    r"|start a fight|starts a fight|starting a fight|take a swing|takes a swing"
    r"|taking a swing|square up|squares up|squaring up|kill|kills|killing"
    r"|fight|fights|fighting"
    # Violence at a distance. Missing entirely at first, so "I throw my dagger at him"
    # started no fight at all — and once it did, it opened toe to toe, which is the one
    # range a thrown dagger is not for.
    r"|throw|throws|throwing|hurl|hurls|hurling|lob|lobs|lobbing|sling|slings|slinging"
    r"|shoot|shoots|shooting|loose|looses|loosing|fire at|fires at|firing at"
    r"|pelt|pelts|pelting|snipe|snipes|sniping)\b", re.I)

# The ones that only make sense with ground between you. A fight opened by a thrown
# knife starts at that range; one opened by a punch starts in reach.
_AT_RANGE = re.compile(
    r"\b(?:throw|throws|throwing|hurl|hurls|hurling|lob|lobs|lobbing|sling|slings"
    r"|slinging|shoot|shoots|shooting|loose|looses|loosing|fire at|fires at|firing at"
    r"|pelt|pelts|pelting|snipe|snipes|sniping)\b", re.I)

# A distance the player actually stated. "I shoot him with my bow at 120 feet" is a fact
# about the fight and beats every default in this file; rounding it to `near` — three
# squares, fifteen feet — makes a nonsense of the weapon.
_STATED_FEET = re.compile(
    r"\b(?:at|from)?\s*(\d{1,4})\s*(?:ft\b|foot\b|feet\b|')", re.I)
_STATED_YARDS = re.compile(r"\b(?:at|from)?\s*(\d{1,4})\s*(?:yd\b|yds\b|yards?\b)", re.I)

# What a weapon opens at when the player names one but no distance. Not read from the
# weapons table because the table carries `crit_range` and no range increment at all —
# these are the Core Rulebook's own increments, and the ones that matter here.
_OPENS_AT = (
    (re.compile(r"\b(?:longbow|composite longbow)\b", re.I), 100),
    (re.compile(r"\b(?:shortbow|short bow|bow)\b", re.I), 60),
    (re.compile(r"\b(?:heavy crossbow)\b", re.I), 120),
    (re.compile(r"\b(?:crossbow)\b", re.I), 80),
    (re.compile(r"\b(?:sling)\b", re.I), 50),
    (re.compile(r"\b(?:javelin|spear)\b", re.I), 30),
    (re.compile(r"\b(?:dagger|knife|axe|hatchet|bottle|stone|rock)\b", re.I), 10),
)


def opening_feet(player_text: str) -> int | None:
    """How far apart this fight starts, in feet, or None to fall back to a zone."""
    text = str(player_text or "")
    m = _STATED_YARDS.search(text)
    if m:
        return max(5, int(m.group(1)) * 3)
    m = _STATED_FEET.search(text)
    if m:
        return max(5, int(m.group(1)))
    if not _AT_RANGE.search(text):
        return None
    for rx, feet in _OPENS_AT:
        if rx.search(text):
            return feet
    return None

# The commonest ways those verbs are used about nothing you can bleed. "I hit the road",
# "I strike a match", "I jump the queue" — each is a sentence a player will type, and
# each would otherwise conjure a thug and roll initiative.
#
# Kept per verb rather than as one shared noun list. Written shared first, "We charge the
# camp" stopped being a fight, because "camp" was in the list for the sake of "strike
# camp" — which is a different verb entirely.
_NOT_VIOLENCE = re.compile(
    r"\b(?:"
    r"hits?\s+(?:the\s+|a\s+|my\s+)?(?:road|hay|sack|deck|books|trail|bottle|mark)"
    r"|strikes?\s+(?:the\s+|a\s+|my\s+)?(?:match|light|camp|tent|bargain|deal|chord"
    r"|note|balance|flint|lucky)"
    r"|jumps?\s+(?:the\s+|a\s+|my\s+)?(?:queue|gap|ship|rope|claim|gun|conclusion)"
    r"|charges?\s+(?:the\s+|a\s+|my\s+)?(?:price|fee|coin|rate|toll)"
    r"|attacks?\s+(?:the\s+|a\s+|my\s+)?(?:problem|question|subject|topic|task|issue)"
    r"|shoves?\s+(?:the\s+|a\s+|my\s+)?(?:door|table|chair|box|cart|crate|shutter)"
    r")\b", re.I)


def wants_a_fight(player_text: str) -> bool:
    """Whether the player has just declared violence on somebody."""
    text = str(player_text or "")
    if not text or "?" in text:
        return False
    if _MUSING.search(text) or _NOT_VIOLENCE.search(text):
        return False
    return _player_is_the_one_swinging(text)


# Another subject sitting immediately in front of the verb.
_OTHER_SUBJECT = re.compile(r"\b(?:the|a|an|his|her|their|its|they|he|she|it)\s+\w+\s*$",
                            re.I)
_MINE = re.compile(r"\b(?:i|we|i'm|we're|i've|we've|i'll|we'll)\b", re.I)
# Anybody who is not the player, anywhere in front of the verb. An imperative has none of
# these; "He punches me in the ribs" has one and is a report rather than a declaration.
_THIRD_PARTY = re.compile(
    r"\b(?:he|she|it|they|them|the|a|an|his|her|their|its|someone|somebody|everyone"
    r"|anyone|nobody)\b", re.I)


def _player_is_the_one_swinging(text: str) -> bool:
    """Whether the violence in this sentence is the player's own doing.

    Co-occurrence with a first-person pronoun is not enough: "The thug attacks me"
    contains both and is a report of being attacked, which must not conjure a second
    thug — nor may "I watch as the thug attacks me". Whoever is named immediately in
    front of the verb is the one doing it.

    And the pronoun is not required at all, because the app writes its own suggestion
    chips as imperatives. Measured live: the chip under a tavern scene read "Just start
    swinging at him", it arrives in the box verbatim when clicked, and a rule demanding
    "I" ignored the app's own offer to start the fight.
    """
    m = _VIOLENCE.search(text)
    if not m:
        return False
    before = text[:m.start()]
    if _OTHER_SUBJECT.search(before):
        return False
    if _MINE.search(before[-80:]):
        return True
    # No subject at all in front of it: an imperative, which is the player speaking.
    return not _THIRD_PARTY.search(before)


# The words of a coup de grâce. A player finishing a downed creature writes one of
# these; a player picking a fresh fight does not. Kept deliberately narrow — a phrase
# here silences the fight-making repairs, and a loose match would silence them for a
# player who genuinely wants a war.
_FINISHING = re.compile(
    r"\b(?:put(?:ting)? (?:him|her|them|it) out of (?:his|her|their|its) misery"
    r"|out of (?:his|her|their|its) misery"
    r"|finish(?:ing)? (?:him|her|them|it) off"
    r"|coup de gr[aâ]ce|mercy (?:stroke|blow|kill)"
    r"|end(?:ing)? (?:his|her|their|its) suffering"
    r"|make sure (?:he|she|it|they)(?:'s| is| are)? (?:really |truly )?dead"
    r"|one (?:final|last) (?:blow|strike|time))\b", re.I)


def is_finishing_blow(player_text: str, scene) -> bool:
    """Whether these words are a coup de grâce on somebody already down.

    Both halves must hold: the sentence says finishing words, and the scene holds a
    downed non-player body for them to be about. The words alone are not enough — "one
    last strike" against a standing foe is a fight like any other.
    """
    if not _FINISHING.search(player_text or ""):
        return False
    return any(not getattr(a, "is_pc", False) and a.has_state("state.down")
               for a in (getattr(scene, "actors", {}) or {}).values())


def inject_fight(raw_intents, player_text: str, scene):
    """The player started a fight and there was nobody there to have it with.

    Measured in live play, four turns in a row: "I shoulder my way into the worst tavern
    on the street and pick a fight with the biggest bruiser in the room" came back as a
    paragraph about a hulking mass of muscle and tattoos, `outcomes: []`, no actor in the
    scene and no encounter. The GM has a `spawn` op, a `begin_encounter` op, a worked
    example of both and a briefing line, and narrated the fight instead of proposing it —
    which is this project's oldest lesson wearing new clothes.

    Same shape and the same defence as `repair_unknown_refs`: the player is not deciding
    who exists, they are declaring what *they* do, and the world owes them an opponent.
    The template comes from the same cue table, defaulting to the same thug.

    Fires only when there is genuinely nobody to fight — an existing enemy means
    `fill_obvious_targets` is the right tool and this one must stay out of its way.
    """
    if not isinstance(raw_intents, list) or scene is None:
        return raw_intents
    if not wants_a_fight(player_text):
        return raw_intents
    # A finishing blow is not a fight being started. Measured live (2026-08-27): "i
    # strike him one final time to put him out of his misery", aimed by the model —
    # correctly — at the stranger dying at -7, tripped the violence cue, found no
    # foe that _can_be_fought, and this function spawned its default thug for the
    # player to fight instead. A thug from nowhere, killed in the same paragraph,
    # 135 XP awarded, while the man being put out of his misery lay untouched.
    if is_finishing_blow(player_text, scene):
        return raw_intents
    # Anything the GM already proposed that makes a fight is left alone — but an
    # attack aimed at a corpse is not a fight. Measured live: "I attack it" (a
    # creature the prose had spent two turns describing) arrived as an attack on a
    # long-dead ref, this guard read "attack" and stood aside, and the player swung
    # at a body while the well-thing existed only in sentences. A dead target means
    # the fight still needs making.
    living = {r for r, a in (getattr(scene, "actors", {}) or {}).items()
              if not getattr(a, "is_pc", False) and getattr(a, "hp", 0) > 0
              and not a.has_state("state.down")}
    for raw in raw_intents:
        if not isinstance(raw, dict):
            continue
        op = str(raw.get("op", "")).lower()
        if op in ("spawn", "begin_encounter"):
            return raw_intents
        if op == "attack" and str(raw.get("target", "")) in living:
            return raw_intents
    # Somebody is already standing there: the player is not starting a fight, they are
    # swinging in one. `fill_obvious_targets` cannot help — it puts a target on an attack
    # that already exists, and the whole problem is that no attack was proposed at all.
    #
    # Measured in the tavern, round 2, three turns running: the encounter was live, the
    # player typed "I punch the bruiser in the face", the narration described the punch
    # landing, and the turn log read `outcomes: []`. No attack roll, nothing in the roll
    # tracker, and the thug's hit points moved only when the thug swung back.
    foes = [a for r, a in (getattr(scene, "actors", {}) or {}).items()
            if not getattr(a, "is_pc", False) and _can_be_fought(a)]
    if foes:
        pc = scene.pc() if hasattr(scene, "pc") else None
        if pc is None:
            return raw_intents
        target = min(foes, key=lambda a: (getattr(a, "hp", 0) <= 0, str(a.ref)))
        return list(raw_intents) + [{
            "op": "attack", "actor": getattr(pc, "ref", "pc"), "target": target.ref,
            "because": "the player said they attack"}]
    if getattr(scene, "in_encounter", False):
        # In a fight with nobody left to hit. Spawning a fresh opponent mid-encounter
        # would be inventing reinforcements the GM never called for — but the fight is
        # plainly over, and saying so is the one thing that pays out: XP and treasure
        # settle on the way *out* of an encounter.
        #
        # Found by `tools/narrator_audit.py` on its sixth turn: "I keep hitting him"
        # scored `combat-turn-did-nothing`, because the thug was already down and the
        # encounter had not closed, so the turn had nothing in it at all.
        if not any(str(r.get("op", "")).lower() == "end_encounter"
                   for r in raw_intents if isinstance(r, dict)):
            return list(raw_intents) + [{
                "op": "end_encounter",
                "because": "there is nobody left standing to fight"}]
        return raw_intents

    template = "thug"
    for cue, name in _TEMPLATE_CUES:
        if cue.search(player_text or ""):
            template = name
            break
    # As many as the player's own sentence says. The measured failure: "I move
    # towards the group of guards and clansmen and get ready to fight" spawned
    # exactly one watchman, and the player fought a crowd one man at a time,
    # fight after fight, because this repair hard-coded count=1.
    count = opponent_count(player_text)
    known = set(getattr(scene, "actors", {}) or {})
    refs = []
    i = 1
    while len(refs) < count:
        if f"c{i}" not in known:
            refs.append(f"c{i}")
        i += 1
    pc = scene.pc() if hasattr(scene, "pc") else None
    pc_ref = getattr(pc, "ref", "pc")
    return list(raw_intents) + [
        # Engaged, not near. You do not start a brawl with somebody fifteen feet away:
        # measured in the tavern, the man the player swung at was laid out three squares
        # off, out of reach of the punch that started the fight.
        {"op": "spawn", "because": "the player started a fight with somebody",
         "params": dict(
             {"template": template, "count": count,
              "zone": "near" if _AT_RANGE.search(player_text or "") else "engaged"},
             **({"distance_ft": feet} if (feet := opening_feet(player_text)) else {}))},
        {"op": "begin_encounter", "because": "the player started it",
         "params": {"sides": {"you": [pc_ref], "them": list(refs)}}},
        {"op": "attack", "actor": pc_ref, "target": refs[0],
         "because": "the player swung first"},
    ]


_NUMBER_WORDS = {"two": 2, "both": 2, "pair": 2, "couple": 2, "three": 3,
                 "few": 3, "several": 3, "four": 4, "five": 5, "six": 6,
                 "seven": 7, "eight": 8, "dozen": 12}
_COLLECTIVE = re.compile(
    r"\b(group|gang|mob|pack|band|crowd|squad|patrol|bunch)\b", re.I)
_PLURAL_FOES = re.compile(
    r"\b(men|guards|thugs|bandits|wolves|clansmen|soldiers|watchmen|bravos)\b", re.I)


def opponent_count(player_text: str) -> int:
    """How many the player's sentence says they are squaring up against.

    A stated number is honoured in full — no cap, by the player's own ruling: "if I
    run into a deadly situation I should have to reap what I've sown." A collective
    noun means four, a bare plural three, anything else one. Death is survivable by
    design (a patron pays for the raising), so the injector owes the player the
    fight they picked, not a safer one.
    """
    text = player_text or ""
    # A number with a unit after it is a measurement, not a head-count: "I shoot
    # the wolf at 40 feet" is one wolf, found the day this regex read forty.
    m = re.search(r"\b(\d{1,2})\b(?!\s*(?:-|\s)?\s*(?:feet|foot|ft|paces|yards|"
                  r"metres|meters|minutes|hours|rounds|gp|sp|cp)\b)", text)
    if m and 1 < int(m.group(1)):
        return int(m.group(1))
    for word, n in _NUMBER_WORDS.items():
        if re.search(rf"\b{word}\b", text, re.I):
            return n
    if _COLLECTIVE.search(text):
        return 4
    if _PLURAL_FOES.search(text):
        return 3
    return 1


def repair_unknown_refs(raw_intents, player_text: str, scene):
    """Create the people the GM was already talking about, instead of losing the turn.

    The recurring failure: the player writes "two guild bravos come round the corner",
    the GM answers with `attack thug1`, the ref registry refuses it — correctly, it must
    not be possible to invent people by naming them — and five attempts later the turn is
    gone. It has an example and a hint pointing at `spawn` and it still does this.

    So the repair is done in code rather than asked for again. This is narrow on purpose:
    it fires only when the unknown refs look like invented names rather than typos, the
    count comes from the *player's* sentence, and the result goes through the ordinary
    validation. Nothing is created that the player did not describe arriving.

    Returns amended raw intents, or None if this is not that problem.
    """
    known = set(getattr(scene, "actors", {}) or {})
    invented: list[str] = []
    for raw in raw_intents or []:
        if not isinstance(raw, dict):
            return None
        targets = raw.get("target")
        targets = targets if isinstance(targets, list) else [targets]
        # `opposed_by` too: a turn was lost to `opposed_by: {ref: "thug1"}` when only
        # actor and target were being repaired.
        opposed = (raw.get("params") or {}).get("opposed_by") or {}
        for ref in [raw.get("actor"), *targets, opposed.get("ref")]:
            if not isinstance(ref, str) or ref in known or ref in invented:
                continue
            if not _INVENTED_REF.match(ref) or re.fullmatch(r"c\d+|pc", ref, re.I):
                return None            # a real ref that is simply wrong: not our business
            invented.append(ref)

    if not invented or any(r.get("op") == "spawn" for r in raw_intents):
        return None

    template = "thug"
    for cue, name in _TEMPLATE_CUES:
        if cue.search(player_text or ""):
            template = name
            break

    # How many, from how many the GM itself named. Not from the player's sentence: the
    # player does not decide how many enemies are round the corner.
    count = len(invented)
    minted = [f"c{i}" for i in range(1, count + len(known) + 2)
              if f"c{i}" not in known][:count]
    if len(minted) < count:
        return None

    swap = dict(zip(invented, minted))
    params = {"template": template, "count": count}
    if count == 1:
        # The GM's invented ref usually *is* the fiction's name — it wrote `kaldrimia`
        # or `winged_woman`, not `npc7`. Spawning her as "thug" made every later tell
        # narrate the wrong person: the live fight read "the thug steps forward" about a
        # guildmate the scene had introduced by name. Only for one: two invented refs
        # cannot share a name, and picking which ref names the pair is a guess.
        cleaned = re.sub(r"\d+$", "", invented[0]).replace("_", " ").replace("-", " ").strip()
        if cleaned and cleaned != template:
            params["name"] = cleaned
    amended = [{"op": "spawn", "because": "they are already in the scene the GM described",
                "params": params}]
    for raw in raw_intents:
        raw = dict(raw)
        if isinstance(raw.get("actor"), str):
            raw["actor"] = swap.get(raw["actor"], raw["actor"])
        tgt = raw.get("target")
        if isinstance(tgt, str):
            raw["target"] = swap.get(tgt, tgt)
        elif isinstance(tgt, list):
            raw["target"] = [swap.get(t, t) for t in tgt]
        params = dict(raw.get("params") or {})
        if isinstance(params.get("opposed_by"), dict):
            ob = dict(params["opposed_by"])
            ob["ref"] = swap.get(ob.get("ref"), ob.get("ref"))
            params["opposed_by"] = ob
            raw["params"] = params
        amended.append(raw)
    return amended


_ATTACK_PARAMS = {"weapon", "full_attack", "manoeuvre", "power_attack", "iteration"}


def normalize_attacks(raw_intents, scene):
    """Straighten the attack shapes the model bends, before validation refuses them.

    Measured live: "I attack the closest person" died in SEVEN attempts across two
    models, every one a shape problem the correction loop could not teach past —
    `target` written into params (the schema rightly refuses unknown params), an
    invented `action` param, and a weapon name ('armed punch') filed as a manoeuvre.
    Each is a mechanical move, not a judgement call: the information is present and in
    the wrong pocket.

    Returns amended raw intents, or None when nothing needed straightening.
    """
    from rules import tables

    changed = False
    out: list[dict] = []
    for raw in raw_intents or []:
        if not (isinstance(raw, dict) and str(raw.get("op", "")).lower() == "attack"):
            out.append(raw)
            continue
        raw = dict(raw)
        params = dict(raw.get("params") or {})
        # The target belongs at the top level, and the model keeps pocketing it.
        if not raw.get("target") and isinstance(params.get("target"), str):
            raw["target"] = params["target"]
            changed = True
        # A weapon filed as a manoeuvre: legal manoeuvres are a closed set with an
        # alias table; anything a weapon lookup knows goes to `weapon`, anything
        # neither knows is dropped — a plain attack is what the player described.
        man = str(params.get("manoeuvre", "") or "").strip().lower()
        if man and man not in tables.MANEUVERS and \
                man not in tables.MANEUVER_ALIASES:
            params.pop("manoeuvre")
            if not params.get("weapon"):
                params["weapon"] = man
            changed = True
        # Unknown params ('action', 'target' now that it has moved) are refusals
        # waiting to happen; the schema names the legal five.
        for key in [k for k in params if k not in _ATTACK_PARAMS]:
            params.pop(key)
            changed = True
        raw["params"] = params
        out.append(raw)
    return out if changed else None


_TRADE_OPS = {"sell", "buy", "give", "take"}


def drop_unfulfillable_trades(raw_intents, scene):
    """Drop a trade aimed at somebody who is not there, instead of losing the turn.

    Measured in the adversarial audit: "I sell my legendary artifact collection to the
    nearest merchant for a million gold" made the model answer with `sell` to a ref
    called 'the merchant' — no such person — and the refs check refused it seven times
    across two models until the turn died as a 502. `repair_unknown_refs` rightly would
    not touch it: spawning a merchant because the player addressed one is inventing
    people, and a *sale* is not an attack the fiction already described arriving.

    So the sale is dropped and the rest of the turn survives. Nothing moves — which is
    the correct amount of movement for a transaction with nobody on the other side —
    and the narration (grounded, claims-scrubbed) says what it looked like to try.

    Returns amended raw intents, or None if this is not that problem.
    """
    known = set(getattr(scene, "actors", {}) or {})
    kept: list[dict] = []
    dropped = False
    for raw in raw_intents or []:
        if not isinstance(raw, dict):
            return None
        op = str(raw.get("op", "")).lower()
        params = raw.get("params") or {}
        if op in _TRADE_OPS:
            targets = raw.get("target")
            targets = targets if isinstance(targets, list) else [targets]
            refs = [r for r in [*targets, params.get("to"), params.get("from")]
                    if isinstance(r, str) and r]
            if any(r not in known for r in refs):
                dropped = True
                continue
        elif op == "check":
            # The same failure in a different op: "I pick the pocket of the first
            # person I see" became a Sleight of Hand opposed by a ref that was not
            # there. The check itself is the player's action and survives — against
            # the ground's flat difficulty, since the person the GM imagined resisting
            # does not exist to resist.
            opposed = params.get("opposed_by") or {}
            ref = opposed.get("ref") if isinstance(opposed, dict) else None
            if isinstance(ref, str) and ref and ref not in known:
                raw = dict(raw)
                fixed = dict(params)
                fixed.pop("opposed_by", None)
                fixed["dc"] = {"band": "average"}
                raw["params"] = fixed
                dropped = True
        kept.append(raw)
    if not dropped:
        return None
    if not kept:
        kept = [{"op": "narrate_only", "actor": "pc",
                 "because": "the person they addressed is not here", "params": {}}]
    return kept


def _refs_depend_on_spawn(intents, scene) -> bool:
    """Does any intent point at a creature that only a spawn in this list will create?"""
    known = set(getattr(scene, "actors", {}) or {})
    for intent in intents:
        candidates = [intent.actor, *intent.targets(),
                      intent.params.get("to"), intent.params.get("who")]
        for ref in candidates:
            if isinstance(ref, str) and re.fullmatch(r"c\d+", ref) and ref not in known:
                return True
    return False


def default_npc_action(scene, ref: str) -> list[dict] | None:
    """What a creature does when the GM cannot say.

    A thug whose turn fails validation used to "hesitate" — it stood still while the
    player was attacked by nobody, which reads as a bug even when it is a fallback. A
    creature in a fight that has an enemy in front of it swings; that is both better play
    and closer to what the GM was going to say anyway.

    Returns raw intents rather than an `Intent`, so they go through the same validation
    as anything else. Nothing here bypasses a check.
    """
    actor = scene.actors.get(ref)
    if actor is None or not actor.can_act() or actor.is_down:
        return None

    mine = next((side for side, refs in (scene.sides or {}).items() if ref in refs), None)
    enemies = [
        r for side, refs in (scene.sides or {}).items() if side != mine
        for r in refs if scene.conscious(r)
    ]
    if not enemies:
        return None

    # The most hurt enemy still standing: a creature that has been fighting knows who is
    # nearly down.
    target = min(enemies, key=lambda r: scene.actors[r].hp)
    return [{
        "op": "attack", "actor": ref, "target": target,
        "because": "it is in a fight and there is someone in front of it",
    }]


def _quote(text: str, limit: int = 120) -> str:
    text = " ".join((text or "").split())
    return repr(text if len(text) <= limit else text[:limit] + "…")


# --- the attack that lands on the wrong body ---------------------------------------------

# Words in an actor's display name that identify nobody: "the guildhand on the gate"
# matches on "guildhand" and "gate", never on "the" or "on".
_NAME_NOISE = {"the", "a", "an", "on", "of", "at", "in", "and", "or", "to", "with"}

# The player's own victim, read from their sentence: an attack verb, then the phrase.
# Deliberately requires a determiner, so "I attack him" (a pronoun, could be anybody)
# never matches and never triggers the repair.
_AIMED_AT = re.compile(
    r"\b(?:attack|strike|stab|slash|shoot|charge|rush|tackle|swing (?:at|on)|throw[^.]*?\bat"
    r"|run(?:ning)? [^.]*?through|cut(?:ting)? down|lunge at|go(?:ing)? for)\s+"
    r"(?:the|that|this|those|these)\s+([a-z][a-z \-']{2,40}?)(?=[,.!?;]|\s+(?:and|with|before|while|as)\b|$)",
    re.I)


def _name_words(name: str) -> set[str]:
    return {w for w in re.findall(r"[a-z']+", (name or "").lower())
            if w not in _NAME_NOISE}


def repair_misaimed_attack(raw_intents, player_text: str, scene):
    """Aim the attack at the person the player named, creating them if they must exist.

    The failure this repairs, verbatim from the 2026-08-22 playtest: the narration had
    introduced a winged woman; she was never spawned; the player wrote "I rush the winged
    woman and run her through", and the GM answered `attack c1` — a *valid* ref belonging
    to the gatekeeper dying at 0 hp, three scenes and one biome away. Every check passed,
    the wrong man was stabbed to -4, and the narrator then rewrote the fiction to agree
    with the engine ("it's Zara, the guildhand who was supposed to be watching the
    gate"). `repair_unknown_refs` never fired because nothing was unknown.

    So the mechanical test is disagreement between two names: the attack's target is a
    known actor none of whose name-words appear anywhere in the player's sentence, while
    the player's sentence names a victim — determiner and all — who matches no actor in
    the scene. Both halves must hold. A pronoun triggers nothing; naming the actual
    target triggers nothing; only aiming at somebody who does not exist while the intent
    aims at somebody who does.

    The repair spawns the named victim — a generic statblock under the fiction's own
    name, template picked from the player's wording — and moves the attack onto them.
    Returns None when there is nothing to do.
    """
    if not isinstance(raw_intents, list) or scene is None or not player_text:
        return None
    aimed = _AIMED_AT.search(player_text)
    if not aimed:
        return None
    victim_phrase = " ".join(aimed.group(1).split())
    victim_words = _name_words(victim_phrase)
    if not victim_words:
        return None

    actors = getattr(scene, "actors", {}) or {}
    # The player named somebody who is already here: nothing to repair, whatever the
    # intent says — second-guessing a match is how a repair becomes a bug.
    for a in actors.values():
        if victim_words & _name_words(getattr(a, "name", "")):
            return None

    def _aims_wrong(raw) -> bool:
        if not isinstance(raw, dict) or str(raw.get("op", "")).lower() != "attack":
            return False
        target = raw.get("target")
        # No target at all counts. The confirmation session found this the hard way:
        # the player wrote "I rush the careful walker", the model emitted an untargeted
        # attack, this function declined it — and `fill_obvious_targets` then handed it
        # to the only body in the yard, the gatekeeper, all over again. An attack with
        # nobody on it, on a turn where the player named somebody who does not exist,
        # is aimed at that somebody.
        if not target:
            return True
        if not isinstance(target, str) or target not in actors:
            return False
        return not (victim_words & _name_words(getattr(actors[target], "name", "")))

    if not any(_aims_wrong(raw) for raw in raw_intents):
        return None

    template = "thug"
    for cue, name in _TEMPLATE_CUES:
        if cue.search(victim_phrase) or cue.search(player_text):
            template = name
            break

    n = 1
    while f"c{n}" in actors:
        n += 1
    minted = f"c{n}"

    out = [{"op": "spawn", "because": f"the {victim_phrase} the player is attacking "
                                      f"was described but never created",
            "params": {"template": template, "count": 1, "name": victim_phrase}}]
    for raw in raw_intents:
        raw = dict(raw) if isinstance(raw, dict) else raw
        if _aims_wrong(raw):
            raw["target"] = minted
        out.append(raw)
    return out


# --- sleep, food and water declared at the table ----------------------------------------

# A declaration of sleep, not a mention of it. Anchored on the verb phrases a player
# actually types; "make camp" alone is not here because the playtest's own player made
# camp and then scouted for an hour.
_SLEEPS = re.compile(
    r"\b(?:sleep|go to sleep|bed down|turn in|doze off|get some (?:sleep|rest)"
    r"|rest (?:for the night|until (?:morning|dawn|daybreak)|till (?:morning|dawn)))\b",
    re.I)
_WONT_SLEEP = re.compile(r"\b(?:can't|cannot|won't|will not|don't|do not|no|never|without"
                         r"|before I|rather than)\s+(?:\w+\s){0,2}?sleep", re.I)
_EATS = re.compile(r"\b(?:eat|eats|eating|have (?:a|some) (?:meal|food|breakfast|supper"
                   r"|dinner)|chew|rations?)\b", re.I)
_DRINKS = re.compile(r"\b(?:drink|drinks|drinking|waterskin)\b", re.I)


def inject_survival(raw_intents, player_text: str, scene) -> list:
    """Make a declared sleep, meal or drink reach the engine, whatever the GM proposed.

    Measured in both 2026-08-22 sessions: "I sleep until morning" charged 20 minutes in
    one and nothing at all in the other, and "I eat from my rations and drink from my
    waterskin" reached the engine as narrate_only — so the survival clocks built that
    week could run out but never be answered. The prompt already carries a worked `rest`
    example and a briefing line saying to use it; both models ignored both. Detect
    mechanically, repair in code — the only kind of fix that has held.

    Conservative on purpose: a question mark anywhere skips the whole thing (asking about
    sleep is not sleeping), a negated sleep does not rest, and a fight in progress lets
    the engine's own legality check say why not.
    """
    if not isinstance(raw_intents, list) or not player_text or scene is None:
        return raw_intents
    if "?" in player_text:
        return raw_intents

    present = {str(r.get("op", "")).lower() for r in raw_intents if isinstance(r, dict)}
    pc = scene.pc()
    out = list(raw_intents)

    if _EATS.search(player_text) and "eat" not in present:
        out.append({"op": "eat", "because": "the player said they eat"})
    if _DRINKS.search(player_text) and "drink" not in present:
        out.append({"op": "drink", "because": "the player said they drink"})
    # Sleep last: you eat before you bed down, and the rest op's own legality check
    # still applies — mid-fight it is refused with the reason, not silently dropped.
    if (_SLEEPS.search(player_text) and not _WONT_SLEEP.search(player_text)
            and "rest" not in present and not getattr(scene, "in_encounter", False)
            and pc is not None and pc.hp >= 0):
        out.append({"op": "rest", "actor": pc.ref, "params": {"kind": "night"},
                    "because": "the player said they sleep"})
    return out


# --- things changing hands, declared at the table ----------------------------------------

# Taking, being given, buying. The verb has to be the player's own: "I buy a lantern",
# not "a lantern for sale". `pay`/`buy` are separated from `take`/`pick up` only so the
# reason clause reads truthfully in the log.
_ACQUIRES = re.compile(
    r"\bi\s+(?:take|takes|pick(?:\s+up)?|buy|buys|purchase|purchases|grab|grabs"
    r"|pocket|pockets|accept|accepts|collect|collects|claim|claims)\b", re.I)
_HANDS_OVER = re.compile(
    r"\bi\s+(?:give|gives|hand(?:\s+over)?|hands|pay|pays|drop|drops|sell|sells"
    r"|offer|offers|leave behind)\b", re.I)
# What was taken: the noun phrase after the verb, stopped at a clause boundary. Small
# and greedy-free on purpose — a whole sentence is not an item.
_THING = re.compile(
    r"\b(?:a|an|the|some|my|two|three|four|five|\d+)\s+([a-z][a-z' -]{2,28}?)"
    r"(?=\s*(?:[.,;!?]|\band\b|\bfrom\b|\bto\b|\bfor\b|\bwith\b|$))", re.I)


# Nouns that are never objects, however much they read like them after "I take". Found in
# a live save: the Inventory tab listed "offer" and "scene on" beside a traveller's outfit,
# because "I accept the offer" and "I take in the scene on the ridge" both parse as a
# player picking something up. Every one of these came off a real sentence or is the same
# shape as one — the list is a stop-list rather than a taste filter, so a word only earns
# a place here if it cannot be a physical thing you could put in a satchel.
_NOT_A_THING = frozenset("""
offer chance opportunity moment breath look glance peek listen turn seat rest care
time aim cover shelter refuge comfort courage heart hope faith note notice stock heed
charge lead hold blame credit risk oath vow name word advice counsel deal bargain
scene sight view air place position stand side part share step pace lay lie stroll
walk stairs road path route way route trail direction watch guard vigil pause breather
initiative action reaction move measure account stance grip liberty leave offence
umbrage pride solace revenge vengeance revenge stock example lesson point issue matter
""".split())

# Idioms where the verb is not acquisition at all. Matched on what immediately follows the
# verb, because "take in", "take note of" and "take stock of" are single verbs wearing two
# words — and "I take in the scene" is not a theft.
_IDIOM = re.compile(
    r"^\s*(?:in|note|stock|cover|charge|heed|aim|offence|offense|umbrage|refuge|shelter|"
    r"comfort|solace|pride|issue|leave|part|place|root|shape|effect|hold\s+of|"
    # A possessive in front of the idiom: "I take my leave", "I take our chances". The
    # first cut matched only what sat immediately after the verb, so "I take my leave of
    # the innkeeper" read on and came back with the innkeeper.
    r"(?:my|our|your|his|her|their)\s+(?:leave|turn|chances?|time|rest|place|position|"
    r"aim|revenge|vengeance|bearings|pick|seat|stand|due|share)|"
    r"a\s+(?:look|glance|peek|seat|moment|breath|break|rest|turn|step|walk|stroll|chance|"
    r"stand|hint|guess|dislike|liking|shine|swing|bow|knee))\b", re.I)


def _is_a_thing(item: str) -> bool:
    """Whether this noun phrase could be something you carry.

    The head noun is the one that decides — "the offer of a room" is an offer, and
    "a leather satchel" is a satchel. Read from the end, because English puts the head
    last: adjectives pile up in front of it.
    """
    words = [w for w in str(item or "").lower().replace("-", " ").split() if w]
    if not words:
        return False
    head = words[-1]
    if head.endswith("s") and head[:-1] in _NOT_A_THING:
        return False
    return head not in _NOT_A_THING


def inject_goods(raw_intents, player_text: str, scene) -> list:
    """Make a declared purchase or pick-up reach the engine.

    Same shape and the same reason as `inject_survival`. Fifty-four turns of one live
    game produced fifty-four `narrate_only` and a single `check`: the GM narrated a
    pouch of crystals, a room paid for and a key handed over, and not one of them
    existed anywhere the engine could see. An inventory nothing ever writes to is a
    field on a sheet, not a game.

    Conservative in the same way: a question is not a purchase, and only the player's
    own declaration counts — what the GM says is lying on the table is not something
    the player picked up.
    """
    if not isinstance(raw_intents, list) or not player_text or scene is None:
        return raw_intents
    if "?" in player_text:
        return raw_intents
    present = {str(r.get("op", "")).lower() for r in raw_intents if isinstance(r, dict)}
    # `sell` too, and that is not symmetry for its own sake. "I sell the Yarow Elixir"
    # matches `_HANDS_OVER`, so this fired first and wrote a `give` — the elixir left the
    # satchel for nothing, and `inject_sale` then bowed out because a `give` was already
    # present. A declared sale paid the player zero gold for as long as the order was the
    # other way round, and the whole trade feature was invisible behind it.
    if present & {"give", "sell", "buy"}:
        return raw_intents

    pc = scene.pc()
    if pc is None:
        return raw_intents

    for pattern, gains in ((_ACQUIRES, True), (_HANDS_OVER, False)):
        found = pattern.search(player_text)
        if not found:
            continue
        rest = player_text[found.end():]
        # "I take in the scene", "I take a moment", "I take cover". The verb is not
        # acquisition when these follow it, and reading on for a noun phrase is how an
        # afternoon's reflection became a line in the inventory.
        if _IDIOM.match(rest):
            continue
        thing = _THING.search(rest)
        if not thing:
            continue
        item = " ".join(thing.group(1).split()).strip(" -'")
        if not item or len(item) < 3:
            continue
        # And the noun itself has to be something a satchel could hold.
        if not _is_a_thing(item):
            continue
        params = {"item": item}
        if gains:
            params["to"] = pc.ref
        else:
            params["from_"] = pc.ref
        return list(raw_intents) + [{
            "op": "give", "params": params,
            "because": f"the player said they {'took' if gains else 'handed over'} it",
        }]
    return raw_intents


# --- selling something -----------------------------------------------------------------
#
# The ninth of these, and the reason is the usual one: the op exists, the prompt carries
# it, and the model does not emit it. Measured before the op existed at all — a whole
# haggle over a satchel of tinctures, four turns, every one of them `narrate_only`.
#
# Deliberately narrower than `inject_goods`. That one reads a noun phrase out of the
# sentence; this one does not have to, because what is being sold has to be something the
# character is actually carrying — so the *satchel* is the vocabulary, and a name that
# does not match a jar on the shelf is not a sale.
_SELLS = re.compile(
    r"\b(?:i\s+)?(?:sell|sells|selling|offer\s+to\s+sell|hand\s+over|trade\s+away|"
    r"part\s+with|flog|pawn|barter\s+away)\b", re.I)

# "how much for", "what will you give me for", "name a price for" — asking is not selling
# and must not move anything. This is the guard `inject_goods` gets from its "?" check,
# and it is written out here because a haggle is full of statements that are still
# questions: "twenty gold coins" ends in no question mark at all.
_JUST_HAGGLING = re.compile(
    r"\b(?:how\s+much|what\s+(?:will|would|can)\s+you|name\s+a\s+price|"
    r"what'?s?\s+it\s+worth|price\s+(?:for|these|this|them)|appraise)\b", re.I)


def _resolve_sold_item(raw_intents, pc) -> list:
    """Point a `sell` at a jar the character is actually holding.

    The model writes what a person would say — "sweetspire tea" — and the engine wants
    `sweetspire-tea#1`. Only exact-ish matches are taken: the id itself, the jar's name,
    or its base. A sell naming something the satchel has never heard of is left alone, so
    the engine's own refusal still names what she does have.
    """
    if not isinstance(raw_intents, list):
        return raw_intents
    stock = getattr(pc, "stock", {}) or {}
    if not stock:
        return raw_intents

    def _find(said: str) -> str:
        said = " ".join(str(said or "").split()).lower()
        if not said or said in stock:
            return ""
        for item in sorted(stock.values(),
                           key=lambda s: len(getattr(s, "name", "")), reverse=True):
            for candidate in (str(getattr(item, "name", "")),
                              str(getattr(item, "base", "")),
                              str(item.id).split("#")[0].replace("-", " ")):
                if candidate and candidate.lower() == said:
                    return item.id
        return ""

    out = []
    for entry in raw_intents:
        if isinstance(entry, dict) and str(entry.get("op", "")).lower() == "sell":
            params = dict(entry.get("params") or {})
            found = _find(params.get("item"))
            if found:
                entry = dict(entry, params=dict(params, item=found))
        out.append(entry)
    return out


def inject_sale(raw_intents, player_text: str, scene) -> list:
    """Make a declared sale reach the engine.

    Grounded in the satchel rather than in the sentence, which is the difference between
    this and `inject_goods`: the thing being sold has to be a jar the character is holding
    right now, so "I sell the draught" finds the draught and "I sell my soul" finds
    nothing and stays out of the way.
    """
    if not isinstance(raw_intents, list) or not player_text or scene is None:
        return raw_intents
    if "?" in player_text or _JUST_HAGGLING.search(player_text):
        return raw_intents

    pc = scene.pc()
    if pc is None or not getattr(pc, "stock", None):
        return raw_intents

    # Repair before deciding whether to inject. Measured in play, the turn after the
    # schema started *requiring* a `sell` when the player declares one: the model duly
    # emitted the op and named the jar the way a person would —
    #
    #     sell: Thessaly Corr is not carrying 'sweetspire tea'. They have:
    #     beeswax#1, betony-tea#1, ... sweetspire-tea#1, ...
    #
    # — with the thing she was selling sitting in that very list. The engine refused, the
    # turn died, and this injector had stood down because a `sell` was already present.
    #
    # Requiring the op and leaving its params to chance is half a fix. The injector is the
    # only thing here that knows the ids, so it corrects one rather than bowing to it.
    raw_intents = _resolve_sold_item(raw_intents, pc)

    present = {str(r.get("op", "")).lower() for r in raw_intents if isinstance(r, dict)}
    if "sell" in present or "give" in present:
        return raw_intents
    if not _SELLS.search(player_text):
        return raw_intents

    said = player_text.lower()
    # Longest name first, so "Yarow Elixir" wins over a jar merely called "Elixir".
    for item in sorted(pc.stock.values(),
                       key=lambda s: len(getattr(s, "name", "")), reverse=True):
        name = str(getattr(item, "name", "")).lower()
        base = str(getattr(item, "base", "")).lower()
        for candidate in (name, base):
            if candidate and len(candidate) > 3 and candidate in said:
                return list(raw_intents) + [{
                    "op": "sell", "actor": pc.ref,
                    "params": {"item": item.id},
                    "because": "the player said they were selling it",
                }]
    return raw_intents


# A declared risky action, by the verb that declares it. The same shape as the goods
# and survival injections and for the same reason: "I was able to sneak out of the
# tavern without a roll" — the narrator narrated the slipping-out and emitted
# `narrate_only`, and instructing it to demand checks is the fix that has never held
# here. The verbs are conservative: each one is an action 1e genuinely rolls for, and
# a sentence that merely mentions the word ("I could sneak…" is caught by the question
# guard; "the sneak thief" has no leading I-verb) does not fire.
_CHECK_VERBS = (
    ("stealth", r"sneak|slip\s+(?:out|past|away|by|through)|creep|skulk|tip.?toe"
                r"|hide\b|steal\s+(?:past|away|through)"),
    ("sleight of hand", r"pick\s+(?:\w+\s)?pockets?|pickpocket|palm\b|filch"),
    ("disable device", r"pick\s+the\s+lock|pick\s+(?:\w+\s)?locks?|disarm\s+the\s+trap"
                       r"|jimmy\b"),
    ("climb", r"climb|scale\s+the|clamber"),
    ("swim", r"swim\b"),
    ("acrobatics", r"leap|jump\s+(?:across|over|down|the)|vault|tumble|somersault"),
    ("escape artist", r"slip\s+(?:my|the|these)\s+(?:ropes?|bonds?|manacles?|chains?)"
                      r"|wriggle\s+(?:free|out)"),
    ("bluff", r"bluff|lie\s+to|deceive|trick\s+(?:him|her|them|the)|fool\s+(?:him|her|them|the)"),
    ("intimidate", r"intimidate|threaten|menace"),
    ("diplomacy", r"persuade|negotiate|talk\s+(?:him|her|them)\s+(?:down|into|out)"),
    ("disguise", r"disguise\s+(?:myself|as)|pose\s+as|pass\s+myself\s+off"),
    ("perception", r"search\s+(?:the|for|his|her|their)|eavesdrop|listen\s+at"),
    ("survival", r"track\s+(?:him|her|them|the)|follow\s+the\s+(?:trail|tracks)"),
)

_DECLARES = r"\bi\s+(?:try\s+to\s+|attempt\s+to\s+|carefully\s+|quietly\s+|quickly\s+)?"


def redirect_attacks_off_corpses(raw_intents, player_text: str, scene):
    """An attack aimed at the dead becomes an attack on somebody real.

    Read out of a live save: both refs in the scene were corpses, the prose had been
    describing guardsmen for three turns, and the model — forced to choose a legal
    ref — aimed every swing at a body. One living combatant means no encounter can
    form, so the combat bar never appeared while the player 'fought' a crowd that
    existed only in sentences. When the player's own words name opposition (the same
    template cues the spawn repair reads), the attack gets a freshly spawned target;
    when they do not, the swing at the corpse stands — kicking the fallen is a thing
    a player may genuinely mean.

    Returns amended raw intents, or None when nothing needed redirecting.
    """
    if not isinstance(raw_intents, list) or scene is None:
        return None
    # A coup de grâce is aimed at the body ON PURPOSE. Retargeting it would swing
    # the mercy stroke at a living bystander; spawning would invent an opponent for
    # somebody who asked for neither. The same guard silences inject_fight.
    if is_finishing_blow(player_text, scene):
        return None
    dead = {r for r, a in scene.actors.items()
            if not a.is_pc and a.is_down}
    living = [r for r, a in scene.actors.items()
              if not a.is_pc and not a.is_down]
    targets_dead = [r for r in raw_intents
                    if isinstance(r, dict) and str(r.get("op", "")).lower() == "attack"
                    and str(r.get("target", "")) in dead]
    if not targets_dead:
        return None
    if living:
        swap = living[0]
        out = [dict(r, target=swap) if r in targets_dead else r for r in raw_intents]
        return out
    template = None
    for cue, name in _TEMPLATE_CUES:
        if cue.search(player_text or ""):
            template = name
            break
    if template is None:
        return None                       # kicking the fallen: let it stand
    known = set(scene.actors)
    ref = next(f"c{i}" for i in range(1, len(known) + 3) if f"c{i}" not in known)
    out: list = [{"op": "spawn",
                  "because": "the fight the fiction has been describing",
                  "params": {"template": template, "count": 1}}]
    for r in raw_intents:
        out.append(dict(r, target=ref) if r in targets_dead else r)
    return out


def drop_premature_end(raw_intents) -> list:
    """The GM does not get to end the fight it is starting.

    Read out of a live save's own turn log: ['attack', 'end_encounter'],
    ['spawn', 'attack', 'end_encounter'], even ['end_encounter', 'attack'] — the
    model closes every fight in the same breath it opens one, so the combat bar
    never once appeared across a whole session of swinging. Ending an encounter is
    the ENGINE's call (it already ends fights when a side falls, in the NPC loop);
    an end_encounter travelling with an attack or a spawn is bookkeeping reflex,
    stripped here. One that travels alone — a surrender, a talk-down — survives.
    """
    if not isinstance(raw_intents, list):
        return raw_intents
    ops = {str(r.get("op", "")).lower() for r in raw_intents if isinstance(r, dict)}
    if "end_encounter" not in ops or not (ops & {"attack", "manoeuvre", "spawn"}):
        return raw_intents
    return [r for r in raw_intents
            if not (isinstance(r, dict)
                    and str(r.get("op", "")).lower() == "end_encounter")]


def drop_stray_checks(raw_intents, player_text: str) -> list:
    """A check the player never implied, riding a turn that already has its action.

    `fill_bare_checks` made bare checks survivable — and survivable includes the
    model's inventions: "I attack them" arrived with a check(climb) nobody asked for,
    and the player was handed a Climb popup mid-punch. When the turn carries an
    attack or manoeuvre, a check whose skill the player's own words do not reach
    (via the same verb table `inject_checks` reads) is the model decorating, and it
    is dropped.
    """
    import re as _re

    if not isinstance(raw_intents, list):
        return raw_intents
    has_attack = any(isinstance(r, dict) and
                     str(r.get("op", "")).lower() in ("attack", "manoeuvre")
                     for r in raw_intents)
    if not has_attack:
        return raw_intents
    said = (player_text or "").lower()
    out = []
    for r in raw_intents:
        if isinstance(r, dict) and str(r.get("op", "")).lower() == "check":
            skill = str((r.get("params") or {}).get("skill", "")).lower()
            verbs = dict(_CHECK_VERBS).get(skill)
            implied = skill and (skill in said or
                                 (verbs and _re.search(verbs, said, _re.I)))
            if not implied:
                continue
        out.append(r)
    return out


def fill_bare_checks(raw_intents) -> list:
    """A check with nothing to beat gets the average band, before validation sees it.

    `inject_checks` below used to leave its DC "to the engine's own default band" — a
    default that does not exist: `_check_params` refuses a check carrying neither `dc`
    nor `opposed_by`. So every injected check, and every bare check the model wrote,
    died in validation and lived or died on the retry loop learning the correction.
    Measured on the 60-turn audit: the four failed turns were climb, track and search
    lines — check verbs, every one. The band is a plain fact to fill, not a thing to
    ask a model to remember.
    """
    if not isinstance(raw_intents, list):
        return raw_intents
    out = []
    for raw in raw_intents:
        if (isinstance(raw, dict) and str(raw.get("op", "")).lower() == "check"):
            params = dict(raw.get("params") or {})
            if not params.get("dc") and not params.get("opposed_by"):
                raw = dict(raw)
                params["dc"] = {"band": "average"}
                raw["params"] = params
        out.append(raw)
    return out


def inject_checks(raw_intents, player_text: str, scene) -> list:
    """A declared risky action reaches the dice.

    Only when the GM's own plan rolled nothing: a turn that already carries a check,
    an attack or a manoeuvre is a turn where the dice are coming out anyway, and a
    second roll for the same sentence would be the injection double-charging. The DC
    comes from `fill_bare_checks`, which runs after this in the chain.
    """
    import re as _re

    if not isinstance(raw_intents, list) or not player_text or scene is None:
        return raw_intents
    if "?" in player_text:
        return raw_intents
    present = {str(r.get("op", "")).lower() for r in raw_intents if isinstance(r, dict)}
    if present & {"check", "attack", "manoeuvre", "save"}:
        return raw_intents
    pc = scene.pc()
    if pc is None:
        return raw_intents

    for skill, verbs in _CHECK_VERBS:
        if _re.search(_DECLARES + r"(?:" + verbs + r")", player_text, _re.I):
            return list(raw_intents) + [{
                "op": "check", "actor": pc.ref,
                "because": "the player declared it; the dice decide it",
                "params": {"skill": skill},
            }]
    return raw_intents


def inject_ability(raw_intents, player_text: str, scene) -> list:
    """A named class ability the player reached for reaches the engine.

    Same shape and the same reason as the survival and goods injections. The brief now
    lists what the character can do, and the model still narrates a spike being thrown
    and emits `narrate_only` — instructing it is the fix that has never held here.

    Matched on the ability's own name appearing in what the player typed, longest
    first so "Blood Pool Manifestation" is not read as "Blood Pool". A question is not
    a use.
    """
    if not isinstance(raw_intents, list) or not player_text or scene is None:
        return raw_intents
    if "?" in player_text:
        return raw_intents
    present = {str(r.get("op", "")).lower() for r in raw_intents if isinstance(r, dict)}
    if "use_ability" in present:
        return raw_intents

    pc = scene.pc()
    if pc is None or not getattr(pc, "paths", None):
        return raw_intents

    from rules import leveling

    said = player_text.lower()
    names = []
    for path in pc.paths:
        det = leveling.path_detail(pc.char_class or "", path)
        reached = leveling.control_blood_for(pc, path)
        for tier, listed in (det.get("tiers") or {}).items():
            if int(tier) <= reached:
                names += listed
    for name in sorted(set(names), key=len, reverse=True):
        if name.lower() in said:
            params = {"ability": name}
            # One hostile and nobody named is not a guess, the same rule
            # `fill_obvious_targets` applies to an attack.
            hostiles = [r for r, a in scene.actors.items()
                        if not a.is_pc and _can_be_fought(a)]
            if len(hostiles) == 1:
                params["to"] = hostiles[0]
            return list(raw_intents) + [{
                "op": "use_ability", "actor": pc.ref, "params": params,
                "because": f"the player used {name}"}]
    return raw_intents


# --- travel declared at the table --------------------------------------------------------

# Ground words a player actually types, mapped onto the canonical biomes. Deliberately
# nouns about *destination*: "the treeline", "the woods". "gate" and "road" name no ground.
_GROUND_WORDS = (
    (re.compile(r"\b(?:forest|woods|woodland|treeline|trees|thicket|copse)\b",
                re.I), "forest"),
    (re.compile(r"\b(?:jungle|rainforest)\b", re.I), "jungle"),
    (re.compile(r"\b(?:swamp|marsh|marshes|bog|fen|mire|quagmire|wetland)\b",
                re.I), "swamp"),
    (re.compile(r"\b(?:hills?|foothills|moor|moorland|downs|upland)\b", re.I), "hills"),
    (re.compile(r"\b(?:mountains?|peaks?|crags?)\b", re.I), "mountain"),
    (re.compile(r"\b(?:desert|dunes|badlands|wasteland|wastes|sands)\b",
                re.I), "desert"),
    (re.compile(r"\b(?:tundra|snowfield|icefield)\b", re.I), "tundra"),
    (re.compile(r"\b(?:coast|coastline|shore|shoreline|beach|seafront)\b",
                re.I), "coast"),
    (re.compile(r"\b(?:plains?|grassland|grasslands|steppe|meadows?|scrub|scrubland"
                r"|brushland|heath|heathland|savanna|savannah|veldt|prairie"
                r"|pastures?)\b", re.I), "grassland"),
    (re.compile(r"\b(?:farmland|fields|orchards?)\b", re.I), "farmland"),
    (re.compile(r"\b(?:underground|caves?|caverns?|tunnels|catacombs|mineshaft)\b",
                re.I), "underground"),
    (re.compile(r"\b(?:ruins?)\b", re.I), "ruins"),
    (re.compile(r"\b(?:city|town|streets|village|hamlet)\b", re.I), "urban"),
)
# The list above is longer than the ground the engine has fourteen names for, and that is
# the point. Measured in play: "I leave the step and walk out past the edge of Zhilvarnia
# into the open scrub" matched `_DEPARTS` cleanly and then found no ground word at all,
# because "scrub" was not among them — so the party stayed in `urban` while the narrator
# wrote dry underbrush and a sun overhead, the market stranger walked into the wilderness
# with them, and every biome-gated excursion stayed locked on ground that was no longer
# the ground they were standing on. Nothing here is a new mechanism; `travel` already
# sheds the stranger and moves the biome the moment it fires.
#
# Bare "brush", "wood" and "mine" are deliberately absent: "brush past the guard", "a
# wooden door" and "the sword is mine" are all commoner than the terrain reading, and a
# false travel is far worse than a missed one — it teleports the party mid-sentence.

# Going somewhere, not being somewhere: "I head for the treeline" travels, "I like these
# woods" does not, and "the forest looming ahead" is the GM's sentence rather than the
# player's. The verb and the ground must be in the same declaration.
_DEPARTS = re.compile(
    r"\b(?:head|heads|heading|make|makes|making|set out|setting out|strike out|walk"
    r"|walks|walking|travel|travels|travelling|traveling|leave|leaves|leaving|go|goes"
    r"|going|ride|rides|riding|march|marches|marching|flee|fleeing|run|running"
    r"|climb|climbs|climbing|descend|descends|push on|press on|make my way|slip out"
    # Going home is as common as setting out, and none of these were here: "Return to
    # Zhilvarnia" was one of the app's own suggestion chips, and "I turn back towards
    # the city walls" is how the same move gets typed. The ground-noun requirement
    # below keeps them honest — "I return the sword to him" has no ground in it.
    r"|return|returns|returning|turn back|turns back|turning back|double back"
    r"|retrace|retraces|retracing"
    r"|slip away)\b[^.!?]{0,60}?\b(?:for|to|towards?|into|out to|up to|down to|back to"
    r"|back towards?)\b",
    re.I)


# Settlement kinds, as World Bible writes them. A place of one of these kinds is
# somewhere with streets, which is `urban` as far as the ground underfoot is concerned.
_SETTLEMENT_KINDS = ("CITY", "TOWN", "VILLAGE", "SETTLEMENT")

# Talking about a journey is not taking one. "I think about going to Zhilvarnia one day"
# has a movement verb, a preposition and a real place in it, and the party must not be
# standing somewhere else by the end of the sentence. Checked on what comes *before* the
# departure, because that is where the deliberation sits — the same reason the existing
# rule reads "Should we head into the woods?" as a question rather than a march.
_MUSING = re.compile(
    r"\b(?:think|thinks|thinking|thought|consider|considers|considering|wonder|wonders"
    r"|wondering|dream|dreams|dreaming|imagine|imagines|imagining|plan|plans|planning"
    r"|hope|hopes|hoping|wish|wishes|wishing|talk|talks|talking|speak|speaks|speaking"
    r"|ask|asks|asking|remember|remembers|remembering|mean|means|meant"
    r"|suppose|supposes|maybe|perhaps|someday|one day)\b", re.I)


def _named_settlement(text: str, world) -> str:
    """A settlement of this world named in this clause, or "".

    The ground-noun list can only ever hold terrain words, and the commonest way of
    saying where you are going is to name the place: "Return to Zhilvarnia" is one of
    the app's own suggestion chips. Matched against the world's real entities rather
    than a pattern, which is the same "ground every name" rule the invented-name check
    works by — and it means a world with a town called Scrub still resolves correctly.

    Longest name first, so "Zhilvarnia Gate" is preferred over "Zhilvarnia" where both
    exist.
    """
    if world is None:
        return ""
    try:
        places = [e for e in world.entities.values()
                  if str(getattr(e, "kind", "") or "").upper() in _SETTLEMENT_KINDS]
    except Exception:                                  # pragma: no cover - guard
        return ""
    for place in sorted(places, key=lambda e: -len(str(getattr(e, "name", "") or ""))):
        name = str(getattr(place, "name", "") or "").strip()
        if name and re.search(rf"\b{re.escape(name)}\b", text, re.I):
            return name
    return ""


def inject_travel(raw_intents, player_text: str, scene, world=None) -> list:
    """Make a declared journey move the engine's ground.

    Playtest finding 8, and the confirmation session reproduced it exactly: "I head out
    the gates for the treeline" was narrated as a whole journey — city sounds fading,
    forest growing denser — and arrived as narrate_only. The biome stayed urban, so the
    forage tables were wrong and the city gatekeeper was still in the scene, because the
    travel op is also the scene transition and it never fired.

    Same shape as `inject_survival`: fire only on a declaration (movement verb and ground
    noun in the same clause), never on a question, never when the GM already proposed
    travel, never when the named ground is the ground already underfoot.
    """
    if not isinstance(raw_intents, list) or not player_text or scene is None:
        return raw_intents
    if "?" in player_text:
        return raw_intents
    if any(str(r.get("op", "")).lower() == "travel"
           for r in raw_intents if isinstance(r, dict)):
        return raw_intents

    m = _DEPARTS.search(player_text)
    if not m:
        return raw_intents
    if _MUSING.search(player_text[:m.start()]):
        return raw_intents
    # The ground named after the movement verb, so "I leave the city for the treeline"
    # reads as forest rather than urban: the destination clause is what is scanned.
    after = player_text[m.start():]
    for rx, biome in _GROUND_WORDS:
        if rx.search(after):
            if biome == getattr(scene, "biome", ""):
                return raw_intents
            return list(raw_intents) + [{
                "op": "travel", "because": "the player said they go",
                "params": {"biome": biome}}]

    # No terrain word, but the destination may be a place with a name. This matters more
    # since a market began requiring urban ground: leave town, come back by naming the
    # town, and without this the biome stays wherever you were and every stall is shut.
    named = _named_settlement(after, world)
    if named and getattr(scene, "biome", "") != "urban":
        return list(raw_intents) + [{
            "op": "travel", "because": f"the player said they go to {named}",
            "params": {"biome": "urban", "note": f"Back within {named}."}}]
    return raw_intents


# --- what the player has already declared ------------------------------------------------
#
# Nine injectors now, and each one exists because the model failed to propose something
# the player plainly said. That list grows once per feature, forever, which is the smell:
# it is linear in features and every entry is a repair applied after the fact.
#
# The fight schema shows the better shape. In combat `narrate_only` is not in the op enum
# at all, so "narrated the punch and proposed nothing" is not a reply the sampler can
# produce — prevented rather than repaired. The same trick generalises: when a declaration
# *is* detected, the turn schema can require that op to be present, and then the model
# picks the item, the target and the reason itself. An injector guessing those is strictly
# worse than the model choosing them with the scene in front of it.
#
# The injectors stay, demoted to backstop. Same doctrine as `right_body` under a brief
# that already states the fact: say it first, catch it after.
#
# --- going out for material --------------------------------------------------------------
#
# The eleventh, and the same measurement as every one before it. A live session typed
# "I get my water and then I go out to the forest to forage" and the narration invented
# the entire outcome — chanterelle mushrooms, identified by "your Survival skill",
# "added to your satchel" — while the engine ran nothing and the ingredients panel
# truthfully showed an empty satchel. The forage op has existed all along; only the door
# from a typed sentence was missing.
#
# The bare verb is the anchor — it is the word the live player actually typed, and it is
# unambiguous. The gather-family verbs only count with a plant noun as their object, so
# "I pick up the sword" and "I gather my things" cannot fire; a false forage charges an
# hour of world clock and a Survival toll to somebody who never asked to spend either.
_FORAGES = re.compile(r"\bforag(?:e|es|ing)\b", re.I)
_GATHERS_PLANTS = re.compile(
    r"\b(?:gather|pick|harvest|collect|look\s+for|search\s+for|hunt\s+for)\b"
    r"[^.!?]{0,30}?"
    r"\b(?:herbs?|plants?|mushrooms?|roots?|berries|flowers?|fungi|ingredients?|"
    r"reagents?)\b", re.I)
_FOR_HOURS = re.compile(r"\b(?:for\s+)?(\d{1,2})\s+hours?\b", re.I)


_LOOTS = re.compile(
    r"\b(?:loot|strip|rifle)\b|\bsearch\s+(?:the\s+)?(?:body|bodies|corpse)"
    r"|\btake\s+everything\b", re.I)


_BULK_ITEM = re.compile(r"\b(stuff|everything|belongings|wares|inventory|"
                        r"all (?:of )?(?:it|his|her|their|the)?)\b", re.I)


def bulk_give_is_a_loot(raw_intents, scene) -> list:
    """A give of "his stuff" when he is a corpse is the loot it meant.

    Measured live: the merchant was dead, the model proposed give item
    "merchants stuff" with nobody as giver, and the old world-branch minted the
    phrase as an object. Give's bulk handling moves goods and coin, but only
    loot strips a body properly — weapons, armour, the collapsed kit — so a
    bulk give that names a downed giver, or names nobody while a lootable body
    lies here, becomes that loot.
    """
    if not isinstance(raw_intents, list) or scene is None:
        return raw_intents
    bodies = [ref for ref, a in scene.actors.items()
              if not a.is_pc and a.is_down]
    out = []
    for r in raw_intents:
        if (isinstance(r, dict) and str(r.get("op", "")).lower() == "give"
                and _BULK_ITEM.search(str((r.get("params") or {}).get("item", "")))):
            frm = (r.get("params") or {}).get("from_") or (r.get("params") or {}).get("from")
            if frm in bodies or (not frm and bodies):
                out.append({"op": "loot", "actor": r.get("actor") or "pc",
                            "because": r.get("because") or "taking everything "
                                       "from the fallen",
                            "params": {"from_": frm or bodies[0]}})
                continue
        out.append(r)
    return out


def inject_loot(raw_intents, player_text: str, scene) -> list:
    """A declared looting reaches the engine — the corpse's pockets are its business.

    Twelfth injector, same measurement as the other eleven: "I loot the watchman I
    take everything" produced a paragraph of coins and a sword and moved nothing.
    Fires only when somebody down-or-dead is actually here; the body is the nearest
    such, because the player pointing at a specific corpse in a room of one is the
    common case and the engine's tell names what actually came off it either way.
    """
    if not isinstance(raw_intents, list) or not player_text or scene is None:
        return raw_intents
    if "?" in player_text or not _LOOTS.search(player_text):
        return raw_intents
    pc = scene.pc()
    if pc is None:
        return raw_intents
    bodies = [ref for ref, a in scene.actors.items()
              if not a.is_pc and a.is_down]

    # Repair before append: the schema REQUIRES the loot the player declared, so the
    # model emits one — and on the second turn of a live session it emitted it with no
    # `from_` at all, seven attempts died on "missing required param(s) from_", and
    # this injector stood aside because "a loot op is already present". A required op
    # the model cannot shape is this code's to shape: fill the body from the fallen,
    # or drop the op entirely when nobody lootable is here.
    out: list = []
    have_loot = False
    for r in raw_intents:
        if isinstance(r, dict) and str(r.get("op", "")).lower() == "loot":
            params = dict(r.get("params") or {})
            frm = params.get("from_") or params.get("from")
            if frm not in bodies:
                if not bodies:
                    continue                     # nobody to strip: the op goes, quietly
                r = dict(r)
                params.pop("from", None)
                params["from_"] = bodies[0]
                r["params"] = params
            have_loot = True
        out.append(r)
    if have_loot or not bodies:
        return out
    return out + [{
        "op": "loot", "actor": pc.ref,
        "because": "the player said they take it",
        "params": {"from": bodies[0]},
    }]


def inject_forage(raw_intents, player_text: str, scene) -> list:
    """Make a declared forage reach the engine.

    The params stay empty on purpose — no biome, no track. The engine reads the ground
    off the scene and refuses "nowhere in particular" with a printable reason, and the
    track defaults to herbalist; an injector guessing either would be overriding the one
    component that actually knows. Only a typed duration rides along.

    Not gated on company or a fight: `_too_busy_to_forage` refuses those with a reason
    the player can read, which is the same deliberate trade `inject_survival` documents
    for rest.
    """
    if not isinstance(raw_intents, list) or not player_text or scene is None:
        return raw_intents
    if "?" in player_text:
        return raw_intents
    present = {str(r.get("op", "")).lower() for r in raw_intents if isinstance(r, dict)}
    if "forage" in present:
        return raw_intents
    if not (_FORAGES.search(player_text) or _GATHERS_PLANTS.search(player_text)):
        return raw_intents

    pc = scene.pc()
    if pc is None:
        return raw_intents

    params: dict = {}
    hours = _FOR_HOURS.search(player_text)
    if hours:
        params["hours"] = max(1, min(48, int(hours.group(1))))
    return list(raw_intents) + [{
        "op": "forage", "actor": pc.ref, "params": params,
        "because": "the player said they forage",
    }]


# Read by running the injectors themselves rather than by a second copy of their patterns.
# CLAUDE.md records what a duplicated rule costs — a consequence rule was fixed in one
# prompt and left stale in the other, and the bug went on shipping from the copy nobody
# looked at.
_DECLARERS = (
    ("survival", lambda raw, text, scene, world: inject_survival(raw, text, scene)),
    # Sale before goods, the same order the live chain runs them in — and asking them in
    # the wrong order here is what surfaced the bug: "I sell the Yarow Elixir" came back
    # as both `give` and `sell`, which is one item leaving twice.
    ("sale", lambda raw, text, scene, world: inject_sale(raw, text, scene)),
    ("goods", lambda raw, text, scene, world: inject_goods(raw, text, scene)),
    ("ability", lambda raw, text, scene, world: inject_ability(raw, text, scene)),
    ("cast", lambda raw, text, scene, world: inject_cast(raw, text, scene)),
    ("checks", lambda raw, text, scene, world: inject_checks(raw, text, scene)),
    ("travel", lambda raw, text, scene, world: inject_travel(raw, text, scene, world)),
    # After travel, and the ordering is load-bearing: "I go out to the forest to forage"
    # must append travel first, so the intent list executes the move before the forage
    # rolls its tables — the other way round forages the old ground, or errors
    # "nowhere in particular" when there is none.
    ("forage", lambda raw, text, scene, world: inject_forage(raw, text, scene)),
    ("loot", lambda raw, text, scene, world: inject_loot(raw, text, scene)),
    ("fight", lambda raw, text, scene, world: inject_fight(raw, text, scene)),
)


def declared_ops(player_text: str, scene, world=None) -> list[str]:
    """The ops the player's own words already commit the turn to.

    Each injector is asked what it would add to an empty turn. Whatever it names is
    something the player has plainly declared, so the schema can insist on it up front
    instead of the injector bolting it on afterwards.
    """
    found: list[dict] = []
    for _, run in _DECLARERS:
        try:
            # Threaded, not run against a fresh empty list each time. Every injector bows
            # out when a competing op is already present, and that is the only thing
            # stopping one sentence from being read twice — "I sell the elixir" is a sale
            # *or* a handing-over, never both.
            found = list(run(found, player_text, scene, world) or found)
        except Exception:
            continue
    ops: list[str] = []
    for entry in found:
        op = str((entry or {}).get("op", "")).strip()
        if op and op not in ops:
            ops.append(op)
    return ops


# --- casting a spell ---------------------------------------------------------------------
#
# The tenth, and found the same way as the ninth: by playing. "I cast prestidigitation on
# the Sweetspire Tea to make it gleam like something far finer" produced a paragraph about
# blue light and a single `narrate_only`. No slot spent, no spell cast, nothing the engine
# saw.
#
# The `cast` op has worked for months — Magic Missile 1d4+1 x3, Burning Hands 5d4 at
# Reflex DC 12, saves and spell resistance all read off the spell. Only the door from a
# typed sentence was missing, which is exactly what the combat panel's Cast button was
# added for and exactly what a player who types instead of clicking never got.
#
# Grounded in what the character can actually cast, the same way `inject_sale` is grounded
# in the satchel. A wizard who says "I cast fireball" at level 1 gets no intent from this,
# and the narrator is free to tell them so — which is a better turn than a legality error
# that burns five attempts.
_CASTS = re.compile(
    r"\b(?:i\s+)?(?:cast|casts|casting|invoke|invokes|channel|channels)\b", re.I)

# Asking about a spell is not casting it.
_ABOUT_A_SPELL = re.compile(
    r"\b(?:what|which|how|can\s+i|could\s+i|do\s+i\s+know|prepare|memoris|memoriz|"
    r"learn|scribe|read)\b", re.I)


def inject_cast(raw_intents, player_text: str, scene) -> list:
    """Make a declared spell reach the engine."""
    if not isinstance(raw_intents, list) or not player_text or scene is None:
        return raw_intents
    if "?" in player_text or _ABOUT_A_SPELL.search(player_text):
        return raw_intents
    present = {str(r.get("op", "")).lower() for r in raw_intents if isinstance(r, dict)}
    if "cast" in present or "use_ability" in present:
        return raw_intents
    if not _CASTS.search(player_text):
        return raw_intents

    pc = scene.pc()
    if pc is None:
        return raw_intents

    from rules import casting, spells as spells_mod

    if not casting.is_caster(pc):
        return raw_intents

    # What they could actually cast right now. Prepared for a wizard, known for a
    # sorcerer; `knows` answers both, and the book is the vocabulary.
    said = player_text.lower()
    reachable = list(getattr(pc, "spellbook", []) or []) + list(
        (getattr(pc, "prepared", {}) or {}))
    best = ""
    for sid in reachable:
        try:
            spell = spells_mod.get(sid)
        except KeyError:
            continue
        name = str(getattr(spell, "name", "")).lower()
        # Longest name first, so "cure light wounds" is not beaten by "cure".
        if name and name in said and len(name) > len(best):
            best = name
            chosen = sid
    if not best:
        return raw_intents

    params = {"spell": chosen}
    # Somebody to aim it at, when the sentence names one of the people present.
    for ref, actor in scene.actors.items():
        if ref == pc.ref or not actor.name:
            continue
        if actor.name.lower() in said:
            params["at"] = ref
            break
    return list(raw_intents) + [{
        "op": "cast", "actor": pc.ref, "params": params,
        "because": "the player said they cast it",
    }]


def repair_bare_spawns(raw_intents, player_text: str):
    """A spawn the model could not shape is this code's to shape.

    Measured live: "I turn to fight the next group of guards" died in seven
    attempts across two models — six on "spawn: missing required param(s)
    template", the seventh after the model reached for `type` instead — and the
    player got a wall of red where a turn should have been. Same law as the loot
    repair above: the schema REQUIRES the op the model proposed, so the mechanical
    layer must be able to finish it. `type`/`kind`/`creature` are read as the
    template the model meant; a spawn still bare after that gets the template the
    player's own words cue (the fight injector's table), thug when they cue none.
    """
    if not isinstance(raw_intents, list):
        return raw_intents
    out = []
    for r in raw_intents:
        if isinstance(r, dict) and str(r.get("op", "")).lower() == "spawn":
            params = dict(r.get("params") or {})
            if not params.get("template"):
                for said in ("type", "kind", "creature", "who"):
                    if params.get(said):
                        params["template"] = str(params.pop(said))
                        break
            if not params.get("template"):
                template = "thug"
                for cue, name in _TEMPLATE_CUES:
                    if cue.search(player_text or ""):
                        template = name
                        break
                params["template"] = template
            r = dict(r, params=params)
        out.append(r)
    return out


# --- The scene thread: what the player is engaged in between ops ----------------------

_THREAD_VERBS = re.compile(
    r"\bI\s+(?:(follow|tail|shadow|track|pursue)|"
    r"(talk to|question|interrogate|speak (?:to|with)|ask|approach|"
    r"walk (?:up )?to|greet|browse|buy from|chat with)|"
    r"(watch|observe|study|keep an eye on)|"
    r"(wait for|look for|search for))\s+(.{3,60}?)\s*[.!?]?$", re.I)
# The Continue button's own instruction counts as a continue — measured live: the
# thread was empty, Continue arrived with no constraint at all, and a bread stall
# became a library between beats.
_THREAD_CONTINUES = re.compile(
    r"^\s*(?:i\s+)?(?:continue|keep(?:\s+(?:going|following|watching|at it))?|"
    r"carry on|press on|stay (?:on|with) (?:them|him|her|it)|"
    r"take no action\b)", re.I)
_THREAD_DOINGS = ("following", "talking to", "watching", "waiting for")


# At most two words after "the", end-anchored: unbounded, "I keep to the shadows
# in the market" captured "the shadows in the market" whole, and the brief then
# swore everybody was already standing in a place that is not a place.
_THREAD_WHERE = re.compile(
    r"\b(?:in|into|to|at|through|inside|around)\s+"
    r"(the\s+[a-z'-]+(?:\s+[a-z'-]+)?)\s*[.!?]?$", re.I)


def update_thread(scene, player_text: str, resolved_ops=None) -> None:
    """The engine's memory of what the player is engaged in, written mechanically.

    Measured live without it: "I follow the guards that walked away" and then
    "I continue to follow" — and the narrator, holding nothing but four words and
    a scene brief, dropped the guards and wrote a haunted house. The thread is
    state: a fresh declaration sets it, "continue" keeps it, a travel or a fight
    replaces the engagement (the fight IS the engagement now), and it ages out
    after six quiet turns rather than haunting a scene that moved on.
    """
    if scene is None:
        return
    ops = {str(o).lower() for o in (resolved_ops or ())}
    if ops & {"begin_encounter", "travel"}:
        scene.thread = {}
        return
    text = " ".join(str(player_text or "").split())
    # The place, the second live loss: the subject held but the setting drifted —
    # "following them in the market" became following them INTO the market they
    # were both already in. A named place in the player's own sentence sticks to
    # the thread, and a fresh engagement inherits it unless it names its own.
    where = None
    mw = _THREAD_WHERE.search(text)
    if mw:
        where = mw.group(1).strip()
    m = _THREAD_VERBS.search(text)
    if m:
        which = next(i for i in range(1, 5) if m.group(i))
        subject = m.group(5).strip()
        sw = _THREAD_WHERE.search(subject)
        if sw:
            where = sw.group(1).strip()
            subject = subject[:sw.start()].strip() or subject
        scene.thread = {"doing": _THREAD_DOINGS[which - 1],
                        "subject": subject, "age": 0,
                        "where": where or (scene.thread or {}).get("where", "")}
        return
    # Walking away ends the engagement, and until this it did not. Found in a live
    # session: the player spent a turn talking to a merchant, then wrote "I leave the
    # building and search the city for the largest group of powerful fighters I can
    # find" — and the thread was still telling the prose call, as fact, "the player is
    # currently talking to them… Keep them and the present surroundings in the scene;
    # DO NOT CHANGE LOCATION". The model obeyed it, and the next beat put the player
    # back in the room they had walked out of two turns earlier.
    #
    # Checked after `_THREAD_VERBS` on purpose: a sentence that both leaves and declares
    # a new engagement — "I walk over to them and ask their name" — sets the new thread
    # rather than clearing to nothing. Ageing was never going to catch this; the thread
    # rots after six turns of not continuing, and the scene had already been dragged
    # back twice by then.
    if scene.thread and _DEPARTS.search(text):
        scene.thread = {}
        return

    if where and not scene.thread:
        # A place with no engagement yet — "i leave and return to the market" —
        # still anchors: the engagement declared two turns later inherits it.
        scene.thread = {"where": where, "age": 0}
        return
    if scene.thread:
        if where:
            scene.thread["where"] = where
        if _THREAD_CONTINUES.match(text):
            scene.thread["age"] = 0
            return
        scene.thread["age"] = int(scene.thread.get("age", 0)) + 1
        if scene.thread["age"] > 6:
            scene.thread = {}


def thread_brief(scene) -> str:
    """The thread as a sentence of fact for the prose call, or ""."""
    t = getattr(scene, "thread", None) or {}
    if not t.get("subject"):
        return ""
    where = str(t.get("where") or "").strip()
    placed = (f" Both of them are ALREADY in {where}; nobody arrives at, enters "
              f"or heads toward {where} — they are there now." if where else "")
    return (f"STANDING THREAD (fact, not suggestion): the player is currently "
            f"{t.get('doing', 'engaged with')} {t['subject']}.{placed} Keep them "
            f"and the present surroundings in the scene; do not change location, "
            f"and do not drop or replace {t['subject']} unless the player does.")


# Distinct from `_DEPARTS` far above, which belongs to inject_travel and carries
# the capture groups that function reads — reusing the name silently rebound it
# and broke "Return to Zhilvarnia" the moment this was appended below it.
_WALKS_AWAY = re.compile(
    r"\bI\s+(?:leave|walk away|move on|head (?:to|for|out|back)|return to|"
    r"go (?:to|back)|depart|make my way)\b", re.I)


def player_departs(player_text: str) -> bool:
    """Whether this input is the player walking away from where they stand."""
    return bool(_WALKS_AWAY.search(str(player_text or "")))


# --- The cast ledger: people the prose introduced, held as scene state ----------------

_CAST_ROLES = ("merchants?|traders?|vendors?|stall ?keepers?|shopkeepers?|"
               "guards?|guardsmen|guardsman|watchmen|watchman|watchwoman|"
               "strangers?|priests?|priestess(?:es)?|labou?rers?|beggars?|"
               "nobles?|clansmen|clansman|clanswoman|artisans?|soldiers?|"
               "sailors?|innkeepers?|barkeeps?|bartenders?|thugs?|urchins?|"
               "elders?|farmers?|fishermen|fisherman|smiths?|scribes?|"
               "porters?|drovers?|peddlers?|fighters?|warriors?|mercenaries|"
               "mercenary|brawlers?|toughs?|swordsmen|swordsman|duellists?|"
               "men|man|women|woman|boys?|girls?|people|folk")
# A crowd is people. Counted where the prose counts them, capped by the same
# reading the fight injector uses for an uncounted group.
_CAST_GROUP = re.compile(
    r"\b(?:group|band|gang|pack|knot|circle|cluster|party|"
    r"pair|trio|handful)\s+of\s+(?:\w+\s+){0,2}(?:" + _CAST_ROLES + r")\b",
    re.I)
# Any-case adjectives, in any order: "an elderly Kelvaxian vendor" has the
# lowercase one first and the demonym second, and an ordered pattern missed it.
_CAST_INTRO = re.compile(
    r"\b(?:a|an|one|the)\s+((?:[A-Za-z'-]+\s+){0,3}"
    r"(?:" + _CAST_ROLES + r"))\b", re.I)
_CAST_MAX = 8


def note_cast(scene, gm_beat: str, turn: int = 0) -> list[str]:
    """People the narration introduced become ledger entries, mechanically.

    The haunted-house class of bug in its second form: prose invents a Kelvaxian
    merchant, the player answers him, and two beats later he has evaporated
    because he lived nowhere but the model's short memory. Role-phrases in a GM
    beat are read into `scene.cast`; the brief feeds them back as fact. Capped,
    deduplicated on the role's head word, and never containing anyone who is
    already a real actor.
    """
    if scene is None or not gm_beat:
        return []
    real = " ".join(a.name.lower() for a in scene.actors.values())
    heads = {str(e.get("who", "")).split()[-1].lower() for e in scene.cast}
    added = []
    # Groups first, and they are why this was widened: "a group of six men and
    # women gathered in a circle" registered NOBODY — the ledger only spoke
    # singular — so the scene held zero actors, and the next beat was free to
    # invent a merchant in a stall where six armed fighters had been standing.
    spans: list[tuple[int, int]] = []
    for m in _CAST_GROUP.finditer(gm_beat):
        from rules.bestiary import split_collective_name

        n, role = split_collective_name(" ".join(m.group(0).split()))
        # The prose's own number beats the collective's default: "a group of
        # six men" is six, not the four an uncounted "group" means. Stripped
        # from the name as well, or the ledger holds a person called "six man".
        lead = role.split()[0].lower() if role.split() else ""
        if lead in _NUMBER_WORDS or lead.isdigit():
            n = int(lead) if lead.isdigit() else _NUMBER_WORDS[lead]
            role = " ".join(role.split()[1:]) or role
        head = role.split()[-1].lower() if role.split() else ""
        if not head or head in heads or head in real:
            continue
        heads.add(head)
        spans.append(m.span())
        scene.cast.append({"who": role, "turn": int(turn),
                           "count": max(1, min(n, _PROMOTED_CAP))})
        added.append(role)
    for m in _CAST_INTRO.finditer(gm_beat):
        # A phrase already claimed by a group is not a second person: "a group
        # of six men" registered the group AND "group of six men" as somebody.
        # Overlap, not containment: the intro match opens on the article — "a
        # group of six men" — one word before the group match, so a
        # start-inside test let the whole phrase register a second time as
        # somebody called "group of six men".
        if any(m.start() < hi and lo < m.end() for lo, hi in spans):
            continue
        who = " ".join(m.group(1).split())
        # A role noun reached through "of" is not somebody arriving. The filler
        # between the article and the role is three arbitrary words, which is what
        # lets "a tall hooded stranger" through — and also let a figure of speech
        # through as a person. Found in a live session: "the memory of the woman's
        # end still hangs heavy in the air" put **the memory of the woman** in the
        # ledger, `cast_brief` fed her back as present, and the next beat re-staged
        # her in a room the player had already left.
        #
        # It drops the back-references too, which were never introductions either:
        # "one of the men", "the last of the guards". A real group keeps its own
        # path — `_CAST_GROUP` claims "a group of four men" before this loop runs.
        if " of " in f" {who} ":
            continue
        head = who.split()[-1].lower()
        if head in heads or head in real:
            continue
        heads.add(head)
        scene.cast.append({"who": who, "turn": int(turn)})
        added.append(who)
    # Old entries rot out: a bare "stranger" noted a dozen turns back fed a whole
    # invented library scene when a Continue arrived with nothing else to hold —
    # the ledger is the present cast, not a census of everyone ever mentioned.
    scene.cast = [e for e in scene.cast
                  if int(turn) - int(e.get("turn", 0)) <= 12]
    if len(scene.cast) > _CAST_MAX:
        scene.cast = scene.cast[-_CAST_MAX:]
    return added


def cast_brief(scene) -> str:
    """The ledger as a line of fact for the prose call, or ""."""
    entries = getattr(scene, "cast", None) or []
    if not entries:
        return ""
    names = "; ".join(str(e.get("who")) for e in entries if e.get("who"))
    return (f"ALSO PRESENT, introduced earlier (fact, keep them consistent, do "
            f"not re-introduce them): {names}.")


def clear_cast(scene) -> None:
    """Walking away leaves the prose-people behind with everything else —
    including the ones the ledger promoted to living actors."""
    if scene is None:
        return
    for e in scene.cast:
        ref = e.get("ref")
        if ref and ref in scene.actors and not scene.actors[ref].is_pc \
                and scene.actors[ref].hp > 0:
            scene.depart(ref)
    scene.cast = []


# --- Heat: what the bystanders just saw -----------------------------------------------

def note_heat(scene, outcomes) -> None:
    """A public killing is a fact the next beat must carry.

    Measured live: the player murdered a merchant in the middle of the market and
    the very next stall-keeper chatted amiably about silk. Witnesses were
    everywhere — the cast ledger held them — and nothing carried the event
    forward. A kill with the ledger non-empty (or any living non-PC watching)
    writes scene.heat; the brief states it until it cools.
    """
    if scene is None:
        return
    heat = dict(scene.heat or {})
    if heat:
        heat["age"] = int(heat.get("age", 0)) + 1
        scene.heat = {} if heat["age"] > 8 else heat
    killed = []
    for o in outcomes or []:
        for e in getattr(o, "effects", None) or []:
            if isinstance(e, dict) and e.get("kind") == "condition" \
                    and e.get("condition") == "dead":
                a = scene.actors.get(e.get("ref"))
                if a is not None and not getattr(a, "is_pc", False):
                    killed.append(a.name)
    if not killed:
        return
    watchers = bool(scene.cast) or any(
        not a.is_pc and not a.is_down
        for a in scene.actors.values())
    if watchers:
        scene.heat = {"note": f"the player just killed {', '.join(killed)} in "
                              f"front of onlookers", "age": 0}


def heat_brief(scene) -> str:
    t = getattr(scene, "heat", None) or {}
    if not t.get("note"):
        return ""
    return (f"WHAT THE CROWD JUST SAW (fact): {t['note']}. Bystanders react to "
            f"it — fear, scattering, someone running for the watch. Nobody "
            f"chats casually with the killer, and merchants do not approach.")


# --- Company: the person the player addresses must exist ------------------------------

_ADDRESSES = re.compile(
    r"\bI\s+(?:talk to|speak (?:to|with)|approach|walk (?:up )?to|greet|ask|"
    r"find)\s+(.{3,50}?)\s*[.!?]?$", re.I)
_CIVILIANS = re.compile(
    r"\b(merchant|trader|vendor|stall ?keeper|shopkeeper|innkeeper|barkeep|"
    r"bartender|peddler|farmer|fisherman|smith|scribe|artisan|priest|priestess|"
    r"beggar|laborer|labourer|porter|clerk|servant|guildhand|"
    # "I talk to the woman" — the person the prose put by the fire is a person,
    # and addressing them by nothing more than woman/man/stranger still means
    # somebody must be there to answer.
    r"woman|man|stranger|elder|girl|boy)\b", re.I)


def inject_company(raw_intents, player_text: str, scene):
    """The person the player turns to becomes a real actor, not a phantom.

    This deliberately reverses an older refusal ("spawning a merchant because the
    player addressed one is inventing people") — overruled by the player after a
    live session where "i talk to another merchant" produced a vivid stranger who
    was never added to the scene, could not be traded with (the panel gates on a
    living merchant actor), and evaporated on the next beat. The GM's narration
    already invented these people; making the addressed one real is bookkeeping,
    not invention. Civilians only, spawned peacefully, no encounter."""
    if not isinstance(raw_intents, list) or scene is None:
        return raw_intents
    m = _ADDRESSES.search(str(player_text or ""))
    if not m:
        return raw_intents
    role = _CIVILIANS.search(m.group(1))
    if not role:
        return raw_intents
    word = role.group(1).lower()
    for a in scene.actors.values():
        if not a.is_pc and a.hp > 0 and word in str(a.name).lower():
            return raw_intents                    # they already exist; talk away
    if any(isinstance(r, dict) and str(r.get("op", "")).lower() == "spawn"
           for r in raw_intents):
        return raw_intents
    return [{"op": "spawn",
             "because": "the player addressed somebody the scene had not made real",
             "params": {"template": "guildhand", "count": 1, "name": word,
                        "zone": "engaged"}}] + list(raw_intents)


_PROMOTED_CAP = 4


def promote_cast(scene, added) -> list[str]:
    """A person the ledger notes becomes a person the engine holds.

    The ruling, after the library beat: the place held but "there should have
    been a stranger" — the ledger knew about him and the scene did not, so he
    could not be attacked, addressed, traded with or found again. Every newly
    noted entry now spawns as a living civilian (the fight cues pick watchman-
    kinds for armed roles, guildhand for the rest), capped at four standing
    promoted civilians so a crowd scene does not flood the panel. The entry
    remembers its ref, so clearing the ledger walks its people off with it.
    """
    from rules.bestiary import instantiate

    if scene is None or not added or getattr(scene, "in_encounter", False):
        # Mid-fight, bystanders stay prose: joining a battle takes the spawn op's
        # initiative bookkeeping, not a quiet walk-on.
        return []
    standing = [e for e in scene.cast
                if e.get("ref") and e["ref"] in scene.actors
                and scene.actors[e["ref"]].hp > 0]
    counts = {str(e.get("who")): int(e.get("count", 1) or 1) for e in scene.cast}
    made = []
    # A group is bodies, plural. "a group of six men" that promotes one actor is
    # the same lie as a pair of guards being one guard: the fiction says six and
    # the dice know about one.
    wanted = []
    for phrase in added:
        wanted.extend([phrase] * max(1, counts.get(phrase, 1)))
    for phrase in wanted:
        if len(standing) + len(made) >= _PROMOTED_CAP:
            break
        template = "guildhand"
        for cue, name in _TEMPLATE_CUES:
            if cue.search(phrase):
                template = name
                break
        actor = instantiate(template, scene=scene, name=phrase)
        scene.add(actor) if hasattr(scene, "add") else scene.actors.update(
            {actor.ref: actor})
        scene.zones[actor.ref] = "near"
        for e in scene.cast:
            if e.get("who") == phrase and not e.get("ref"):
                e["ref"] = actor.ref
                break
        made.append(phrase)
    return made

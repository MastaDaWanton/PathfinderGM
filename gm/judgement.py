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

# --- Speech is not action ---------------------------------------------------------------
#
# Everything below this line reads the player's own words looking for a declaration —
# a swing, a wait, a target. None of it may read what the player's character SAID.
#
# Measured 2026-09-08, nine lines through `wants_a_fight`: three opened a fight and all
# three were speech. `I tell the clerk "I am a monk, I can handle myself in a fight or
# handle a bunch of others."` conjured guards and rolled initiative, because the scan
# ran over the whole raw line and the "I" inside the quotation answered the question
# "who is doing the swinging". Worst of the three: `I tell the guard "put down your
# sword, I do not want to fight"` — a line refusing a fight, which started one.
#
# Every tradition that has run this problem for decades solves it the same way, and
# none of them solve it with a better keyword list. Inform 7 captures what follows
# "about" or "that" as a value of the kind `topic` and says outright that it "does not
# try to understand automatically what that text might mean". LambdaMOO rewrites a
# leading quote mark into `say` before any verb lookup happens at all, and the rest of
# the line is then a payload handed to one verb, never re-tokenised. CircleMUD maps
# the apostrophe straight to its say handler. In none of them can a word inside speech
# reach the command table. See docs/speech-vs-action.md.
#
# So: redact first, detect second. Length-preserving, because the detectors below work
# in offsets — `_player_is_the_one_swinging` asks who is named in front of the verb.

# Double quotes only, straight or curly. Single quotes are deliberately NOT a delimiter:
# "I don't" and "the guard's blade" would each open one, and a redactor that swallows
# the rest of a line on an apostrophe is worse than the bug it fixes.
_QUOTED = re.compile(r"[\"“”‟]([^\"“”‟]*)"
                     r"[\"“”‟]?")

# Where a redaction stops. Speech runs to the end of its sentence and no further: "I
# tell him to move, then I draw my sword" is a line with a real declaration in it, and
# blanking to the end of the line would lose the sword.
_SENTENCE_END = re.compile(r"[.!?]|\bthen\b|;")

# "I tell the clerk I am a monk" — verb, addressee, then the message.
_TOLD = re.compile(
    r"\b(?:tell|tells|telling|told|warn|warns|warning|warned|assure|assures|assured"
    r"|promise|promises|promised|remind|reminds|reminded|inform|informs|informed"
    r"|threaten|threatens|threatened)\s+"
    r"(?:the\s+|a\s+|an\s+|my\s+|his\s+|her\s+|their\s+)?\w+\s+", re.I)

# "I say to the merchant ..." / "I shout ..." — verb, optional addressee, then it.
_SAID = re.compile(
    r"\b(?:say|says|saying|said|shout|shouts|shouted|yell|yells|yelled|whisper"
    r"|whispers|whispered|reply|replies|replied|answer|answers|answered|declare"
    r"|declares|declared|announce|announces|announced|insist|insists|insisted"
    r"|admit|admits|admitted|claim|claims|claimed|boast|boasts|boasted|brag|brags"
    r"|bragged|swear|swears|swore|vow|vows|vowed|explain|explains|explained)\b"
    r"(?:\s+to\s+(?:the\s+|a\s+|an\s+|my\s+|his\s+|her\s+|their\s+)?\w+)?[\s:,]*", re.I)

# "I ask the woman if she wants to pay" — the question itself starts at the complementiser.
_ASKED = re.compile(
    r"\b(?:ask|asks|asking|asked|beg|begs|begged|plead|pleads|pleaded)\s+"
    r"(?:the\s+|a\s+|an\s+|my\s+|his\s+|her\s+|their\s+)?\w+\s+"
    r"(?:if|whether|that|to|for|about)\s+", re.I)


def spoken(text: str) -> str:
    """The words the character said: everything `redact_speech` blanked, joined up.

    The inverse of the redactor rather than a second parser, so the two can never
    disagree about where the speech was — one rule, read twice.
    """
    line = str(text or "")
    hidden = redact_speech(line)
    runs, cur = [], []
    for a, b in zip(line, hidden):
        if a != b:
            cur.append(a)
        elif cur:
            runs.append("".join(cur).strip())
            cur = []
    if cur:
        runs.append("".join(cur).strip())
    return " ".join(r for r in runs if r).strip(" ,;:\"“”")


def was_speech(text: str) -> bool:
    """Whether the player's line has their character saying something.

    True when the redactor found anything to blank: a quoted span, or the complement
    of a speech verb. Used to decide that a turn which produced nothing owes the
    player an answer in the fiction rather than the parser's holding line.
    """
    line = str(text or "")
    return bool(line.strip()) and redact_speech(line) != line


def redact_speech(text: str) -> str:
    """The line with everything the character SAID blanked out, same length.

    Quoted spans go first, then the complement of a speech verb up to the end of its
    sentence. What is left is what the player's character DID, which is the only thing
    the detectors below are entitled to read.

    Asterisks are deliberately untouched. In the convention the player already knows —
    IRC's emote, the MUSH pose, every roleplay tool since — *asterisks are the action*
    and quotes are the speech, so an asterisked span is exactly what a declaration
    detector should be reading.
    """
    line = str(text or "")
    out = list(line)

    def blank(start: int, end: int) -> None:
        for i in range(max(0, start), min(len(out), end)):
            if not out[i].isspace():
                out[i] = " "

    for m in _QUOTED.finditer(line):
        blank(m.start(1), m.end(1))

    for rx in (_TOLD, _SAID, _ASKED):
        for m in rx.finditer(line):
            stop = _SENTENCE_END.search(line, m.end())
            blank(m.end(), stop.start() if stop else len(line))

    return "".join(out)


def narration_quotes_blanked(text: str) -> str:
    """A GM beat with every line of dialogue blanked out, the same length.

    The narrator's own side of the beat, which is the only part that puts people in the
    room. `redact_speech` is the same idea for the PLAYER's input, and the length is
    preserved for the same reason: the offsets are used afterwards — `note_cast` reads
    spans out of the beat and asks `zone_of_mention` about them, and a shortened string
    would point those at the wrong words.

    Both quote conventions, because the narrator uses both. Apostrophes inside a word are
    not openers: "the guard's" must not blank the rest of the paragraph.
    """
    line = str(text or "")
    out = list(line)
    # An apostrophe INSIDE a single-quoted line — "don't", "it's", "guild's" — is part
    # of the line, not its close: a close is an apostrophe not followed by a letter.
    # Without that, `'If it's the leaf you want …'` matched nothing at all, the whole
    # line stood as narration, and "the elder-quarter" in it booked an elder who was
    # then stood in the lane (2026-09-24).
    for m in re.finditer(r'"[^"]*"|“[^”]*”|'
                         r'(?<![A-Za-z])\'(?:[^\']|\'(?=[A-Za-z]))*\'(?![A-Za-z])', line):
        for i in range(m.start(), m.end()):
            if not out[i].isspace():
                out[i] = " "
    return "".join(out)


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
    # Violence is read off the line with the character's own speech blanked; a peaceful
    # cue is read off the whole line, because saying something IS the peaceful act.
    violent = bool(VIOLENCE.search(redact_speech(text)))
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
    (re.compile(r"\b(watch|watchman|watchmen|guard|guards|guardsman|guardsmen|"
                r"soldiers?|sentr(?:y|ies)|militia)\b", re.I), "watchman"),
    # The armed-stranger words with no block of their own in the corpus. A 13-hp thug is
    # the right scale for a brawler in a market; the corpus's answers for these words are
    # a CR 3 gnoll bruiser and a gillman knife-fighter, which is why `template_for` will
    # not take them (item 30, measured 2026-09-19).
    (re.compile(r"\b(thugs?|toughs?|brutes?|bruisers?|ruffians?|brawlers?|bravos?|"
                r"cutthroats?|mercenar(?:y|ies)|sellswords?|swordsm[ae]n|duellists?|"
                r"fighters?|warriors?|veterans?|hulks?|challengers?)\b", re.I), "thug"),
    # Civilians the cast ledger introduces fight like the commoners they are —
    # promoting "the Kelvaxian merchant" into a warrior statblock would make
    # every shopkeeper a bruiser.
    (re.compile(r"\b(guildhand|clerk|servant|porter|merchant|trader|innkeeper|"
                r"barkeep|bartender|peddler|farmer|fisherman|beggar|urchin|"
                r"scribe|artisan)\b", re.I), "guildhand"),
)


def _pc_level(scene) -> int:
    """The player's level, for the CR band a newcomer is chosen in. One is the answer for
    a scene with no player in it (a test, an NPC-only view) and the floor everywhere."""
    pc = scene.pc() if scene is not None and hasattr(scene, "pc") else None
    try:
        return max(1, int(getattr(pc, "level", 1) or 1))
    except (TypeError, ValueError):
        return 1


def template_for(phrase: str, level: int = 1, floor: str = "guildhand") -> str:
    """The stat block a person the prose introduced walks on with.

    Four hand-written cues were the whole vocabulary, so a raider became a 4-hp guildhand
    with a club while a Raider at 29 hp sat in the corpus, reachable by `spawn` today and
    by nothing else (2026-09-19, item 30). `npcs.choose` bands by CR and already has a
    townsfolk floor, so the corpus answers — but only when the block it picks IS this role.

    That last condition is the whole of the care here, and it was measured before it was
    written: asked at level 1, the chooser answers "bruiser" with a **gnoll** bruiser at
    CR 3, "fighter" with a *gillman* knife-fighter, "veteran" with a veteran *buccaneer*
    and "merchant" with a Tian merchant *sailor*. Matching one word and dragging a species
    in is worse than the floor — a CR 3 gnoll walking out of a market crowd is not the
    fiction anybody wrote. So the pick stands only when its id is the role word itself
    (raider, brigand, bandit, guard, watchman), and everything else keeps the floor the
    cues already gave: a dog for a dog, a watchman for the watch, a thug for a brawler.

    `floor` is what nothing matching at all means -- `guildhand` for somebody the prose
    introduced into a room, `thug` for somebody the fiction described arriving in the
    middle of the player's own action. Four copies of that cue loop existed before this,
    and CLAUDE.md's rule about grepping for every copy of a rule applies: they all come
    through here now.
    """
    from rules import npcs

    phrase = str(phrase or "")
    # The animal cue first and unconditionally: "the guard dog" contains "guard", and the
    # corpus answers "guard dog" with a Guard. It is a dog.
    for cue, name in _TEMPLATE_CUES:
        if cue.search(phrase):
            floor = name
            break
    if floor == "guard dog":
        return floor
    head = _role_head(phrase)
    if not head:
        return floor
    # Singular, because a block is one creature: "raiders" finds nothing, "raider" finds
    # the Raider.
    for word in (head, head[:-1] if head.endswith("s") else head):
        if not word:
            continue
        got = npcs.choose(word, max(1, int(level or 1))) or {}
        if str(got.get("id") or "").lower() == word:
            return str(got["id"])
    return floor


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
    if actor.has_state("state.down"):
        return False
    # And not somebody who is merely in the room. Measured 2026-09-18 with the map
    # open: nine non-player actors, seven of them promoted from prose — a guard,
    # traders, a boy, "nearby merchants" — every one a candidate for "him", and the
    # planner's attack on "the man" landed on a 4-hp bystander who had never been in
    # the fight. A bystander becomes fightable the moment they act or are acted on
    # (`Engine.join_fight`, `Engine._op_attack` lift the tag); until then "I attack"
    # cannot mean them. The player naming one by name goes round this — the plan
    # then carries the ref and nothing here fills anything.
    return not actor.has_state("role.bystander")


# Ops whose subject is a person and whose unnamed subject is the player. `attack` is
# deliberately absent: who you are hitting is never obvious from the op alone.
_SELF_OPS = {"heal", "temp_hp", "rest", "eat", "drink", "forage", "prospect", "found",
             "venture", "condition",
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
    # range a thrown dagger is not for. AT somebody, though: measured 2026-09-18, "I
    # throw my coat open to show them" started a fight with the apprentice, because
    # the bare verb was on this list and the model's actor-less attack was handed to
    # the player as the one swinging.
    r"|(?:throw|throws|throwing|hurl|hurls|hurling|lob|lobs|lobbing|sling|slings|"
    r"slinging)\s+(?:\w+\s+){0,3}at"
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


# Violence the player is declining. Found beside the speech bug, 2026-09-08: "I don't
# want to fight, I look for the door" contains no speech verb and no quotation, so the
# redactor leaves it whole and correctly so — and the old rule then read "fight", found
# an "I" in front of it and started one. Kept to the same clause and a short reach, so
# that "I don't hesitate, I attack the guard" is still a fight.
_DECLINED = re.compile(
    r"\b(?:don't|dont|do not|won't|wont|will not|would not|wouldn't|never|no need"
    r"|rather not|refuse to|instead of|without)\b[^,;.!?]{0,24}$", re.I)


def wants_a_fight(player_text: str) -> bool:
    """Whether the player has just declared violence on somebody.

    Reads the line with the character's own speech blanked out. Before that it read
    the raw line, and three of nine measured speech lines started a fight — see
    `redact_speech` above for the measurement and the traditions it follows.
    """
    text = redact_speech(player_text)
    if not text.strip() or "?" in text:
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
    if _DECLINED.search(before):
        return False
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
    # Speech is not action: the character's own words are blanked before any cue is
    # looked for here. See `redact_speech`.
    if not _FINISHING.search(redact_speech(player_text)):
        return False
    # Or helpless: the coup de grace is 1e's blow for exactly the creature that is bound
    # or paralysed, which stopped counting as down on 2026-09-25.
    return any(not getattr(a, "is_pc", False)
               and (a.has_state("state.down") or a.has_state("state.helpless"))
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
    # Speech is not action, and everything below reads this line for cues: the
    # opponent count, the opening range, the template. See `redact_speech`.
    player_text = redact_speech(player_text)
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

    # The corpus answers where it has a block for the role word itself, and `thug` is the
    # floor: these are people the fiction described arriving in the middle of the player's
    # own action, not shopkeepers (`template_for`, item 30).
    template = template_for(player_text or "", _pc_level(scene), floor="thug")
    # As many as the player's own sentence says. The measured failure: "I move
    # towards the group of guards and clansmen and get ready to fight" spawned
    # exactly one watchman, and the player fought a crowd one man at a time,
    # fight after fight, because this repair hard-coded count=1.
    count = opponent_count(player_text)
    from rules.bestiary import next_ref

    # Through the one minter, with the refs projected so far as `taken`. This was one
    # of four hand-copied lowest-free scans, and under containment every copy would
    # have re-minted a ref a living creature in the next room still wears.
    refs: list[str] = []
    while len(refs) < count:
        refs.append(next_ref(scene, taken=refs))
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


# Every number word prose actually writes, because a stated count is not a guess. Measured
# 2026-09-19: "a band of twelve raiders" had no entry for **twelve**, so the number was
# neither read nor stripped and the ledger booked a person literally called "twelve
# soldier" (item 30). The teens and the tens are in for the same reason; `score` is twenty
# and `dozen` was already here.
_NUMBER_WORDS = {"two": 2, "both": 2, "pair": 2, "couple": 2, "three": 3,
                 "few": 3, "several": 3, "four": 4, "five": 5, "six": 6,
                 "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
                 "twelve": 12, "dozen": 12, "thirteen": 13, "fourteen": 14,
                 "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
                 "nineteen": 19, "twenty": 20, "score": 20, "thirty": 30,
                 "forty": 40, "fifty": 50}
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
    # Speech is not action: a number the character SPEAKS is not a head-count. "I say
    # 'there were four of them last night'" is one opponent, not four.
    text = redact_speech(player_text)
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


_NUMBER_IN = re.compile(r"\b(?:\d{1,2}|" + "|".join(_NUMBER_WORDS) + r")\b", re.I)
# What a beat hangs off the end of a description and is no part of who they are: "the twelve
# raiders COMING UP THE ROAD", "the guards STANDING BY THE GATE". A participle clause is a
# thing they are doing, and a creature named for it keeps doing it forever.
_DOING_SOMETHING = re.compile(
    r"\s+(?:coming|going|walking|running|standing|waiting|approaching|closing|moving|"
    r"heading|riding|marching|charging|advancing|gathered|blocking|guarding|watching)\b.*$",
    re.I)


def _without_the_count(phrase: str) -> str:
    """"twelve raiders coming up the road" → "raiders". What is left is who they are.

    A name is not a head-count and not a stage direction. Both halves measured: the ledger
    held a person called "twelve soldier" (item 30) and a live spawn produced one creature
    called "twelve raiders coming up the road" (item 33's own check).
    """
    text = " ".join(str(phrase or "").split())
    text = _DOING_SOMETHING.sub("", text)
    words = text.split()
    while words and (words[0].lower() in _NUMBER_WORDS or words[0].isdigit()
                     or words[0].lower() in ("a", "an", "the", "some")):
        # "a pair of guards" is a collective phrase and `split_collective_name` reads it
        # properly downstream — stripping "pair" here left "of guards", which is nobody.
        if len(words) > 1 and words[1].lower() == "of":
            break
        words = words[1:]
    return " ".join(words) or text


def _touches_ref(raw: dict, refs: list[str]) -> bool:
    """Does this intent name one of these refs anywhere — actor, target, or `opposed_by`?
    The test for what to drop when the person it reaches for does not exist."""
    if not isinstance(raw, dict):
        return False
    targets = raw.get("target")
    targets = targets if isinstance(targets, list) else [targets]
    opposed = (raw.get("params") or {}).get("opposed_by") or {}
    named = [raw.get("actor"), *targets,
             opposed.get("ref") if isinstance(opposed, dict) else None]
    return any(isinstance(r, str) and r in refs for r in named)


def repair_unknown_refs(raw_intents, player_text: str, scene, world=None):
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
    # Speech is not action: the character's own words are blanked before any
    # cue is looked for here. See `redact_speech`.
    player_text = redact_speech(player_text)
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

    # Whose word were they created on? The narration describing people arriving is an
    # arrival, and this repair exists for it. The PLAYER naming somebody is a question, and
    # the world can answer it: "I turn to find the mayor" made a 13-hp Warrior-1 called
    # *mayor* in a town that has no mayor at all (2026-09-19, item 29). So when the invented
    # ref is a word out of the player's own sentence and the world places that person
    # elsewhere or nowhere, nobody is created; the op is dropped and the engine prints the
    # world's answer (`narrate_only`'s `not_here`, which `_op_narrate_only` tells).
    sought = person_sought(player_text)
    if sought and world is not None:
        from rules import scope as scope_mod

        for ref in invented:
            word = re.sub(r"[\d_-]+", " ", ref).strip().lower()
            if not word or not (_name_words(word) & _name_words(sought)):
                continue
            found = scope_mod.look_for(world, sought, scene,
                                       getattr(scene, "location_id", None))
            if found.get("scope") in (scope_mod.ELSEWHERE, scope_mod.NOWHERE):
                kept = [dict(r) for r in raw_intents
                        if not _touches_ref(r, invented)]
                kept.append({"op": "narrate_only",
                             "because": "the player looked for somebody who is not here",
                             "params": {"not_here": found["line"]}})
                return kept

    template = template_for(player_text or "", _pc_level(scene), floor="thug")

    # How many, from how many the GM itself named. Not from the player's sentence: the
    # player does not decide how many enemies are round the corner.
    count = len(invented)
    from rules.bestiary import next_ref

    minted: list[str] = []
    while len(minted) < count:
        minted.append(next_ref(scene, taken=minted))

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


_ATTACK_PARAMS = {"weapon", "full_attack", "manoeuvre", "power_attack", "iteration",
                  # Ours, never the model's: `check_the_target` hands an ambiguous
                  # attack back as a question through it.
                  "undecided",
                  # The object an improvised weapon is, and whether it left the hand
                  # (`inject_improvised`).
                  "item", "thrown"}


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
    # Speech is not action: the character's own words are blanked before any
    # cue is looked for here. See `redact_speech`.
    player_text = redact_speech(player_text)
    if not isinstance(raw_intents, list) or scene is None or not player_text:
        return None
    aimed = _AIMED_AT.search(player_text)
    if not aimed:
        return None
    victim_phrase = " ".join(aimed.group(1).split())
    victim_words = _name_words(victim_phrase)
    if not victim_words:
        return None
    # A thing is never a victim to create. "I strike the weapon and sunder it" read
    # "the weapon" as somebody the scene had not made real and spawned a thug named
    # "weapon" (2026-09-18); `aim_at_the_holder` owns that sentence and aims it at
    # whoever holds the thing.
    if names_a_thing(victim_phrase):
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

    template = template_for(victim_phrase, _pc_level(scene), floor="")
    if not template:
        template = template_for(player_text, _pc_level(scene), floor="thug")

    from rules.bestiary import next_ref

    minted = next_ref(scene)

    # As many as the phrase says, and the number is not part of their name. Measured live
    # 2026-09-19: "I charge the twelve raiders coming up the road" spawned ONE creature
    # called "twelve raiders coming up the road" with 29 hit points — the "twelve soldier"
    # family of bug at a site nobody had checked. `opponent_count` is the reader the fight
    # injector already uses, and at five and up the engine forms one unit of them
    # (`troops.UNIT_FROM`, item 33) rather than a dozen bodies.
    count = max(1, opponent_count(victim_phrase) if _NUMBER_IN.search(victim_phrase)
                else opponent_count(player_text))
    spawn_name = _without_the_count(victim_phrase)
    out = [{"op": "spawn", "because": f"the {victim_phrase} the player is attacking "
                                      f"was described but never created",
            "params": {"template": template, "count": count, "name": spawn_name}}]
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
    # Speech is not action: the character's own words are blanked before any
    # cue is looked for here. See `redact_speech`.
    player_text = redact_speech(player_text)
    if not isinstance(raw_intents, list) or not player_text or scene is None:
        return raw_intents
    if "?" in player_text:
        return raw_intents

    present = {str(r.get("op", "")).lower() for r in raw_intents if isinstance(r, dict)}
    pc = scene.pc()
    out = list(raw_intents)

    if _EATS.search(player_text) and "eat" not in present:
        out.append({"op": "eat", "because": "the player said they eat"})
    # A drunk potion is `use_item`, declared before this runs; the waterskin sip is
    # for the sentence that names no jar.
    if (_DRINKS.search(player_text) and "drink" not in present
            and "use_item" not in present):
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
scene action satisfaction job patience services service pleasure attention silence
on off up in out over under away back down
""".split())
# Measured in the masta save (2026-09-18): `goods` held "scene on" ×3 and
# "satisfaction" ×1 — the Continue directive ("I take no action. Carry the scene on…")
# read by `_ACQUIRES` as "I take … the scene on", and "pay for satisfaction" read as a
# purchase. Words for what is happening are not things.

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
    # The Continue directive is not the player's sentence: "I take no action. Carry
    # the scene on" put "scene on" into the goods three times (2026-09-18).
    if re.match(r"\s*I take no action\b", player_text, re.I):
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
# --- Coin by amount, out of the purse ------------------------------------------------------

_NUMBERS = {"one": 1, "a": 1, "an": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
            "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40,
            "fifty": 50, "hundred": 100}
_PAYS = re.compile(
    r"\bI\s+(?:pay|pays|give|gives|hand|hands|toss|tosses|slide|slides|throw|throws|"
    r"leave|leaves|offer|offers|put down|drop|drops|count out)\s+(?:(?:him|her|them|"
    r"the\s+\w+|\w+)\s+)?(?:over\s+)?"
    r"(\d+|" + "|".join(_NUMBERS) + r")\s+(gold|gp|silver|sp|copper|cp|platinum|pp|coins?)"
    r"(?:\s+(?:pieces?|coins?))?\b", re.I)
_COIN_ITEM = re.compile(r"(?:^|_|\b)(gold|silver|copper|platinum|gp|sp|cp|pp|coins?)(?:_|\b)",
                        re.I)


def inject_payment(raw_intents, player_text: str, scene) -> list:
    """Coin the player counts out leaves the purse, by amount, to the person paid.

    Measured in the brothel (2026-09-18): "I pay her ten gold" reached the engine as
    `sell gold_coins_10 to c16` — a sale of a stock item nobody carries — and was refused
    ("Masta is not carrying gold_coins_10") while the prose took the coin. The purse
    never moved. Money is a `give` of a denomination (`_op_give` already spends it and
    refuses a purse that cannot cover it); the player's own number is the amount and the
    addressee is who is paid. A `sell` or `give` the model wrote for coins is turned into
    the same op rather than left to be refused.
    """
    if not isinstance(raw_intents, list) or scene is None or not player_text:
        return raw_intents
    pc = scene.pc()
    if pc is None:
        return raw_intents
    text = redact_speech(player_text)
    m = _PAYS.search(text)
    out: list = []
    changed = False
    # The model's own coin op, whatever shape it took, becomes the give.
    said_n = None
    if m:
        n = m.group(1).lower()
        said_n = int(n) if n.isdigit() else _NUMBERS.get(n, 1)
    for raw in raw_intents:
        if isinstance(raw, dict) and str(raw.get("op", "")).lower() in ("sell", "give"):
            params = dict(raw.get("params") or {})
            item = str(params.get("item") or "")
            coin = _COIN_ITEM.search(item)
            bare_denom = re.fullmatch(r"(?i)gp|sp|cp|pp", item.strip())
            if coin and (str(raw.get("op", "")).lower() == "sell" or not bare_denom):
                # "gold_coins_10", "10 gold", "gold coins": the amount is the
                # player's own number first, then the item's, then the op's count.
                in_item = re.search(r"\d+", item)
                count = said_n or (int(in_item.group(0)) if in_item else 0) \
                    or int(params.get("count") or 0) or 1
                word = coin.group(1).lower()
                denom = {"gold": "gp", "silver": "sp", "copper": "cp",
                         "platinum": "pp"}.get(word, word if word in ("gp", "sp", "cp", "pp") else "gp")
                params = {"item": denom, "count": max(1, count), "from_": pc.ref}
                if raw.get("params", {}).get("to") in scene.actors:
                    params["to"] = raw["params"]["to"]
                raw = {"op": "give", "because": "the player paid in coin", "params": params}
                changed = True
        out.append(raw)
    if m is None:
        return out if changed else raw_intents
    if any(isinstance(r, dict) and str(r.get("op", "")).lower() == "give"
           and str((r.get("params") or {}).get("item", "")) in ("gp", "sp", "cp", "pp")
           for r in out):
        return out
    n = m.group(1).lower()
    count = int(n) if n.isdigit() else _NUMBERS.get(n, 1)
    word = m.group(2).lower()
    denom = {"gold": "gp", "silver": "sp", "copper": "cp", "platinum": "pp",
             "coin": "gp", "coins": "gp"}.get(word, word)
    # Who is paid: the person the sentence names, else the one the player is
    # engaged with, else the only other person here.
    outside = text.lower()
    to = next((ref for ref, a in scene.actors.items() if not a.is_pc
               and (str(a.name).split() or [""])[-1].lower() in outside
               and len((str(a.name).split() or [""])[-1]) > 2), None)
    if not to:
        engaged = engaged_refs(scene)
        others = [r for r, a in scene.actors.items() if not a.is_pc and not a.is_down]
        to = engaged[0] if len(engaged) == 1 else (others[0] if len(others) == 1 else None)
    params = {"item": denom, "count": count, "from_": pc.ref}
    if to:
        params["to"] = to
    return out + [{"op": "give", "because": "the player paid in coin", "params": params}]


# --- A thing swung or thrown ----------------------------------------------------------------

_THROWS = re.compile(
    r"\b(?:I\s+)?(?:throw|throws|hurl|hurls|toss|tosses|lob|lobs|fling|flings|sling|slings|"
    r"chuck|chucks|pitch|pitches)\s+(?:the|a|an|my|this|that|some)?\s*"
    r"([a-z][a-z' -]{1,30}?)\s+(?:at|into|toward|towards)\s+", re.I)
_SWINGS_WITH = re.compile(
    r"\b(?:hit|hits|strike|strikes|smash|smashes|club|clubs|bash|bashes|swing|swings|"
    r"beat|beats|brain|brains|crack|cracks)\s+(?:him|her|them|it|the\s+\w+|\w+)\s+"
    r"(?:with|using)\s+(?:the|a|an|my|this|that)?\s*([a-z][a-z' -]{2,30}?)"
    r"(?=[,.!?;]|\s+(?:and|as|until|before|while)\b|$)", re.I)
_A_REAL_WEAPON = re.compile(r"\b(?:sword|blade|dagger|knife|axe|spear|bow|club|mace|"
                            r"hammer|staff|sap|rapier|glaive|halberd|scimitar|flail|"
                            r"fist|fists|hand|hands)\b", re.I)


def inject_improvised(raw_intents, player_text: str, scene) -> list:
    """A thing thrown or swung is an improvised-weapon attack, and the thing is named.

    Measured 2026-09-18: "i pick up a chunk of wood and throw it at the man" came back
    as `give chunk of wood` and a `cast` ("Masta is a blood bending and does not cast
    spells"), then a `use_ability`; the pebble two turns later killed a man as an
    unarmed strike (37 to hit, 21 damage) with no object in the arithmetic at all. The
    Core Rulebook has the rule (`tables.WEAPONS["improvised"]`: -4, 1d4, thrown at
    10-foot increments). The player's attack this turn — the model's, or the one
    `inject_fight` adds — is given `weapon: improvised`, `item: <the thing>`, and
    `thrown` when it left the hand; a thing not yet carried is picked up first through
    the ordinary `give`, which finds the record lying here if there is one.
    """
    if not isinstance(raw_intents, list) or scene is None or not player_text:
        return raw_intents
    pc = scene.pc()
    if pc is None:
        return raw_intents
    text = redact_speech(player_text)
    thrown = _THROWS.search(text)
    swung = None if thrown else _SWINGS_WITH.search(text)
    m = thrown or swung
    if not m:
        return raw_intents
    thing = " ".join(m.group(1).split()).strip(" -'")
    if not thing or _A_REAL_WEAPON.search(thing) or thing.lower() in ("it", "them", "him", "her"):
        # "throw my dagger at him" is the dagger's own attack; "throw it" names nothing
        # this turn — the last thing picked up is the model's to say.
        if thing.lower() in ("it", "them"):
            # "I pick up a chunk of wood and throw it": the thing is what the same
            # sentence picked up; failing that, the one thing in the hands.
            taken = _ACQUIRES.search(text)
            named = _THING.search(text[taken.end():]) if taken else None
            if named and _is_a_thing(" ".join(named.group(1).split())):
                thing = " ".join(named.group(1).split()).strip(" -'")
            else:
                held = [n for n in getattr(pc, "goods", {}) if _is_a_thing(n)
                        and n.lower() not in ("traveler's outfit",)]
                if len(held) != 1:
                    return raw_intents
                thing = held[0]
        else:
            return raw_intents
    if not _is_a_thing(thing):
        return raw_intents
    out = []
    for raw in raw_intents:
        if isinstance(raw, dict) and str(raw.get("op", "")).lower() in ("cast", "use_ability") \
                and raw.get("actor") in (None, pc.ref):
            # The throw the model dressed as a spell or a power is the throw.
            continue
        out.append(raw)
    carried = any(n.lower() == thing.lower() for n in getattr(pc, "goods", {}))
    lying = scene.prop_on_the_ground(thing) if hasattr(scene, "prop_on_the_ground") else None
    if not carried and not any(isinstance(r, dict) and str(r.get("op", "")).lower() == "give"
                               and str((r.get("params") or {}).get("item", "")).lower() == thing.lower()
                               for r in out):
        out.insert(0, {"op": "give", "because": "the player picked it up to use it",
                       "params": {"item": lying["name"] if lying else thing, "to": pc.ref}})
    attacks = [r for r in out if isinstance(r, dict) and str(r.get("op", "")).lower() == "attack"
               and (r.get("actor") or pc.ref) == pc.ref]
    if not attacks:
        engaged = engaged_refs(scene)
        target = engaged[0] if len(engaged) == 1 else None
        if target is None:
            foes = [r for r, a in scene.actors.items() if not a.is_pc and _can_be_fought(a)]
            target = foes[0] if len(foes) == 1 else None
        attack = {"op": "attack", "actor": pc.ref, "because": f"the player threw the {thing}"
                  if thrown else f"the player swung the {thing}", "params": {}}
        if target:
            attack["target"] = target
        out.append(attack)
        attacks = [attack]
    for raw in attacks:
        params = dict(raw.get("params") or {})
        params.pop("manoeuvre", None)
        params["weapon"] = "improvised"
        params["item"] = lying["name"] if (lying and not carried) else thing
        if thrown:
            params["thrown"] = True
        raw["params"] = params
    return out


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
    # No floor on purpose: nothing recognised in the player's words means nobody new, and
    # the blow stands as kicking the fallen. The words the corpus knows now reach here too
    # ("the raiders keep coming" finds a Raider), which is the same widening item 30 asked
    # for everywhere else.
    template = template_for(player_text or "", _pc_level(scene), floor="")
    if not template:
        return None                       # kicking the fallen: let it stand
    from rules.bestiary import next_ref

    ref = next_ref(scene)
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


# "I use Blood Nova on the merchant": a capitalised name after a using verb, up to a
# preposition or the end. Capitalised on purpose — abilities are Title Case on every
# sheet, and "I use the rope on the door" must not read as an ability called "the rope".
_USES_A_NAMED_THING = re.compile(
    r"\bI\s+(?:use|activate|unleash|trigger|invoke|channel)\s+(?:my\s+)?"
    r"((?:[A-Z][\w'-]*)(?:\s+[A-Z][\w'-]*){0,4})"
    r"(?=\s+(?:on|at|against|upon|toward|towards)\b|[.,!;]|\s*$)")


def refuse_unknown_ability(raw_intents, player_text: str, scene) -> list:
    """A power the player named that nobody has does NOT become an assault.

    Measured live, twice, on 2026-09-02: "I use Blood Nova on the merchant" — an
    ability nobody wrote — came back from the model as `attack`, opened a fight with
    the merchant and every promoted bystander in the market, and the second time put
    Kesst on the floor. The model guessed what a thing it had never heard of does, and
    guessed violence. The schema forced nothing: nothing in the sentence is a fight cue.

    The declaration the player actually made is "I use <X>". When X is not an ability
    they have and not a jar they carry, the honest answer is the engine's own printed
    refusal — "no ability called Blood Nova; they can use: …" — and nothing else. So the
    model's guesses at what X does (an attack, a spawn, a fight) are dropped, and a
    `use_ability` naming X is put in their place; the resolver prints, the fight never
    starts. `inject_ability` above handles the case where X is real; this is its
    complement.
    """
    if not isinstance(raw_intents, list) or not player_text or scene is None:
        return raw_intents
    if "?" in player_text:
        return raw_intents
    m = _USES_A_NAMED_THING.search(str(player_text))
    if not m:
        return raw_intents
    name = " ".join(m.group(1).split())
    pc = scene.pc()
    if pc is None:
        return raw_intents
    from rules import leveling

    _path, found, _fx = leveling.find_ability(pc, name)
    if found:
        return raw_intents
    stock = getattr(pc, "stock", None) or {}
    low = name.lower()
    jar = next((k for k, v in stock.items()
                if low == k.lower() or low == str(getattr(v, "base", "")).lower()), None)
    if jar is not None:
        # X is a jar they carry. The first cut returned the list untouched here,
        # which let the model's own `heal` through beside the real potion; the jar
        # door is the only thing that may put a number on the sheet for it.
        return _jar_instead(raw_intents, pc.ref, jar, f"the player reached for {name}")
    # Every mechanical op in the list is the model's guess at what X does, and X does
    # not exist. The first cut dropped only the fight-makers; the next probe showed
    # the model reaching for `ability_damage con 1d4` on the merchant instead, and it
    # landed — three Constitution damage from a power nobody has. What stays is what
    # carries no number: narration, and a check or a move the sentence may also mean.
    kept = [r for r in raw_intents
            if isinstance(r, dict)
            and str(r.get("op", "")).lower() in ("narrate_only", "check", "move",
                                                  "travel", "use_ability")]
    if any(isinstance(r, dict) and str(r.get("op", "")).lower() == "use_ability"
           for r in kept):
        return kept
    return kept + [{"op": "use_ability", "actor": pc.ref,
                    "because": f"the player reached for {name}",
                    "params": {"ability": name}}]


# --- powers nobody named ------------------------------------------------------------
#
# `refuse_unknown_ability` above catches "I use Blood Nova on the merchant" — a power
# with a NAME. A psychic declaration usually has no name in it at all: "I read his
# mind", "I bend her will", "I use my psychic powers to make him hand it over". There
# is nothing capitalised to look up, so that door never opened and the sentence went
# to the model as ordinary prose, which narrated it as working.
#
# The line drawn here is what the declaration REACHES, not how forceful it is.
# Persuading, threatening, lying, seducing, bribing and pleading are ordinary social
# play and are left completely alone — they are skill checks and `inject_checks`
# already routes them. What fires is a declaration that reaches into somebody's mind:
# reading it, altering it, taking it over, or claiming a faculty that would.
_A_MIND = (r"(?:his|her|their|its|the\s+[\w'-]+(?:'s)?|[A-Z][\w'-]+(?:'s)?)\s+"
           r"(?:mind|thoughts|head|memories|memory|will|dreams|feelings)")

_PSYCHIC = re.compile(
    _DECLARES + r"(?:"
    # Reaching in to look: "I read his mind", "I probe the merchant's thoughts".
    r"(?:read|probe|scan|search|sift|rifle|enter|invade|peer\s+into|look\s+into|"
    r"reach\s+into|slip\s+into|dive\s+into)\s+(?:through\s+)?" + _A_MIND + r"|"
    # Reaching in to take over. Unambiguous verbs only — every one of these names a
    # supernatural effect in the rules, and none of them is a way of talking to
    # somebody. "Persuade", "convince" and "intimidate" are deliberately absent.
    r"(?:mind[\s-]?control|brainwash|dominate|beguile|bewitch|enthrall|enthral|"
    r"mesmeri[sz]e|hypnoti[sz]e|geas|befuddle)\b|"
    # "Charm" carries both meanings in English, and only one of them is the spell.
    # Charming a snake with a flute, or a room with your manner, is a performance —
    # it names the instrument it is done with, which the spell never does.
    r"charm\b(?![^.!?]{0,40}\bwith\s+(?:my\s+|a\s+|the\s+)?"
    r"(?:flute|pipe|pipes|song|singing|music|voice|lute|harp|drum|words|smile|"
    r"manner|charm|wit|story|tale))|"
    # Reaching in to change what is there. The "control of" arm is separate because
    # "seize control of his mind" puts two words between the verb and the mind.
    r"(?:bend|break|crush|shatter|overpower|override|seize|possess|invade|"
    r"take\s+over|control)\s+" + _A_MIND + r"|"
    # The instrument named outright. "I open the door with my mind" is telekinesis and
    # "I crush his will with my mind" is the reported sentence; neither has a verb this
    # pattern could have listed in advance, and both say plainly what they are done
    # with. "I make up my mind" and "I keep it in mind" have no `with`.
    r"[^.!?]{0,60}\b(?:with|using|through)\s+(?:my|the\s+power\s+of\s+my)\s+"
    r"(?:mind|thoughts|will\s*power|psychic\s+\w+)\b|"
    r"(?:seize|take|assume|wrest)\s+(?:control|possession|command)\s+(?:of|over)\s+"
    + _A_MIND + r"|"
    r"(?:erase|wipe|alter|rewrite|implant|plant|insert|push)\s+"
    r"(?:a\s+|an\s+|the\s+|his\s+|her\s+|their\s+)?"
    r"(?:suggestion|compulsion|thought|idea|command|memory|memories)\b|"
    # Claiming the faculty itself, whatever is then done with it.
    r"(?:use|reach\s+for|call\s+on|focus|channel)\s+(?:my\s+|the\s+)?"
    r"(?:psychic|psionic|telepathic|mental|mind)\s+"
    r"(?:powers?|abilit(?:y|ies)|gift|talent|magic|force|energy)\b|"
    r"(?:telepathically|psychically|telekinetically)\b|"
    r"(?:speak|talk|whisper|command|order|tell)\s+(?:to\s+)?"
    r"(?:him|her|them|it)\s+(?:with|through|inside)\s+(?:my\s+|his\s+|her\s+|their\s+)?"
    r"(?:mind|thoughts|head)\b"
    r")", re.I)

# What the player called it, for the refusal to name back at them. The engine's door
# prints "no ability called <X>" and lists what they do have, so this wants to be the
# player's own words rather than a label we invented.
_PSYCHIC_NAMES = (
    (re.compile(r"psionic", re.I), "psionics"),
    (re.compile(r"telepath", re.I), "telepathy"),
    (re.compile(r"telekine", re.I), "telekinesis"),
    (re.compile(r"hypnoti[sz]", re.I), "hypnotism"),
    (re.compile(r"mesmeri[sz]", re.I), "mesmerism"),
    (re.compile(r"\bgeas\b", re.I), "a geas"),
    (re.compile(r"domina|dominate", re.I), "domination"),
    (re.compile(r"charm|beguile|bewitch|enthral", re.I), "a charm"),
    (re.compile(r"brainwash|mind-?control|control\s+\w+\s+mind", re.I), "mind control"),
    (re.compile(r"memor", re.I), "memory-altering"),
    (re.compile(r"suggestion|compulsion", re.I), "a suggestion"),
)


# A faculty claimed outright, whatever is then done with it.
#
# Reported from the table 2026-09-17: "I use my godly powers to will the missing
# transport of refined salt to appear before me, since a god such as myself could easily
# do this at any point, instantly." The narrator wrote the cart arriving — a rift, a
# shockwave, merchants on their knees — and the salt was in the market.
#
# This is the 2026-09-09 psychic report one category over, and it got through for a
# reason worth naming: `_PSYCHIC`'s faculty arm listed the *adjectives* it knew —
# psychic, psionic, telepathic, mental, mind — so "godly" walked past a door built for
# exactly this sentence. An adjective list is a denylist, and a denylist for "ways of
# claiming a power you were never granted" has no end: godly, divine, cosmic, eldritch,
# reality-warping, and whatever the next player writes.
#
# So the adjective is not read at all. What fires is the SHAPE — reaching for a faculty
# — and the sheet decides, which is the rule the rest of this file already runs on: an
# ability that was never granted cannot be activated. `refuse_unnamed_power` stands down
# whenever an intent names an ability the character really has, so a cleric channelling
# and a wizard casting are untouched; what is left is a claim with nothing behind it,
# and the engine's own door answers it with the list of what they can actually do.
_CLAIMED_FACULTY = re.compile(
    r"\b(?:use|using|reach(?:ing)?\s+for|call(?:ing)?\s+(?:on|upon)|focus(?:ing)?|"
    r"channel(?:ling|ing)?|invok(?:e|ing)|exert(?:ing)?|wield(?:ing)?|"
    r"unleash(?:ing)?|draw(?:ing)?\s+(?:on|upon)|harness(?:ing)?)\s+"
    r"(?:my|the|his|her|their)\s+(?:own\s+)?"
    # At most two words of whatever they called it. Unread, deliberately.
    r"(?:[\w-]+\s+){0,2}"
    r"(?:powers?|abilit(?:y|ies)|magic|sorcery|divinity|godhood|godhead|"
    r"omnipotence|omniscience)\b",
    re.I)

# The same claim with a softer noun: "my divine might", "my godly strength". `might`,
# `force` and `strength` are not in the list above on purpose — "I use my last strength
# to push the door" is an ordinary turn, and a pattern that refused it would be worse
# than the one it was fixing.
#
# So this arm reads the SOURCE instead, and yes, that is a word list. It is a defensible
# one here for a reason the arm above is not: it is *additive*. The gate is the general
# shape; this only widens which nouns count when the sentence has already named
# somewhere a level 1 rogue cannot draw from. A miss here costs a phrasing, not the rule.
_CLAIMED_SOURCE = re.compile(
    r"\b(?:my|the|his|her|their)\s+(?:own\s+)?"
    r"(?:god(?:ly|like|-like|given)?|divine|holy|unholy|celestial|infernal|demonic|"
    r"cosmic|eldritch|arcane|psychic|psionic|supernatural|otherworldly|immortal)\s+"
    r"(?:[\w-]+\s+){0,1}"
    r"(?:powers?|abilit(?:y|ies)|might|magic|force|energy|strength|will|word|"
    r"command|touch|authority|nature)\b",
    re.I)

# Claiming to BE the thing, which is the same declaration with the faculty implied:
# "since a god such as myself", "as a god I can", "I am a deity". Speech is redacted
# before any of this runs, so a character boasting to a guard is untouched — a lie about
# what you are is a character's to tell.
_CLAIMS_GODHOOD = re.compile(
    r"\b(?:a|as\s+a|being\s+a|i\s+am\s+(?:a|an|the))\s+"
    r"(?:god|goddess|deity|demigod|divine\s+being|immortal)\b"
    r"|\bgod\s+such\s+as\s+(?:myself|me|i)\b"
    r"|\bmy\s+(?:godhood|godhead|divinity|divine\s+nature)\b",
    re.I)


# Declaring WHAT YOU ARE, rather than what you can do: "I reveal my true form as a
# divine being", "I shed my mortal guise", "I transform into a dragon". Reported with a
# screenshot, 2026-09-18, on 0.1.9: the line above produced no intent at all —
# nothing for `refuse_unnamed_power` to refuse — and the prose wrote the transformation
# as fact: the mud flash-freezing to glass, the stranger on his knees, "the silhouette
# isn't that of a man but something towering and ancient", and closed on "now that the
# truth is laid bare". A nature the sheet does not grant is the same declaration as a
# power the sheet does not grant, one level up, and it is answered at the door before
# any model is asked, the way `play.player_input.FIAT_CREATION` answers a wagon willed
# into being. Speech is redacted first: a character may CLAIM to be a god out loud —
# that is a lie or a boast, and theirs to tell.
_CLAIMS_A_NATURE = re.compile(
    r"\b(?:reveal|revealing|show|showing|unveil|unveiling|assume|assuming|take|taking)"
    r"\s+(?:my|its|the)\s+(?:true|real|divine|godly|celestial|infernal|dragon|"
    r"draconic|demonic|angelic|hidden|secret)\s+(?:form|nature|self|shape|aspect)\b"
    r"|\b(?:shed|shedding|drop|dropping|cast\s+off|let\s+go\s+of|let\s+fall)\s+"
    r"(?:my|the)\s+(?:mortal|human|false)\s+(?:form|guise|mask|shell|skin|disguise)\b"
    r"|\b(?:transform|transforms|transforming|turn|turning|change|changing|morph|"
    r"morphing|shift|shifting)\s+(?:myself\s+)?into\s+(?:a|an|my)\s+"
    r"(?:\w+\s+){0,2}(?:god|goddess|deity|dragon|demon|devil|angel|celestial|giant|"
    r"titan|beast|wolf|bear|serpent|fiend|spirit|true\s+form|divine\s+form)\b"
    r"|\bmy\s+(?:true|real|divine|godly)\s+(?:form|nature|self)\s+(?:is|as|to)\b"
    r"|\bi\s+am\s+(?:no|not)\s+(?:mere\s+)?(?:mortal|human|man|woman)\b",
    re.I)
# What on a sheet would make such a line an ability being used rather than a claim.
_SHAPE_ABILITIES = re.compile(
    r"shape|form|polymorph|transform|manifest|aspect|avatar|apotheosis|ascend|"
    r"divine|celestial|draconic|wild", re.I)


# The SHAPE of a claim about oneself, whatever it claims. A word list would be found a
# way around ("don't just do divine being or I will just find a way around it") — so
# the shape is caught and the SHEET says whether it is true. Five shapes: "I am / I'm /
# I have always been <a/an/the …>"; revealing or declaring what one is; "my true/secret/
# divine … form/nature/power"; unleashing what is "within me"; transforming into a thing.
_SELF_CLAIM = re.compile(
    r"\b(?:i(?:'m|’m| am)|i(?:'ve|’ve| have) always been|i was born)\s+"
    r"(?:actually\s+|really\s+|secretly\s+|truly\s+|in\s+truth\s+)?"
    r"(?P<pred>(?:a|an|the|no|not\s+(?:a|an))\s+[^.,;!?\"“”]{2,60})"
    r"|\b(?:reveal|reveals|revealing|show|shows|showing|unveil|unveils|unveiling|expose|"
    r"exposes|admit|admits|confess|confesses|announce|announces|declare|declares|"
    r"proclaim|proclaims|let\s+(?:them|him|her|you|everyone|the\s+\w+)\s+see)\s+"
    r"(?:to\s+\w+\s+)?(?:that\s+)?(?P<pred2>(?:i\s+am|i'm|i’m|myself\s+(?:as|to\s+be)|"
    r"what\s+i\s+(?:truly|really)\s+am|my\s+(?:true|real|secret|hidden|divine|godly|"
    r"ancient|inner|latent)\s+(?:form|nature|self|identity|power|powers|heritage|"
    r"lineage|blood|strength|gift|gifts|face))[^.,;!?\"“”]{0,60})"
    r"|\b(?P<pred3>my\s+(?:true|real|secret|hidden|divine|godly|ancient|inner|latent)\s+"
    r"(?:form|nature|self|identity|power|powers|heritage|lineage|blood|might|gift|gifts))\b"
    r"|\b(?:unleash|unleashes|release|releases|awaken|awakens|call\s+(?:up)?on|summon|"
    r"channel|draw\s+on|let\s+loose)\s+"
    r"(?P<pred4>(?:the\s+)?(?:\w+\s+){0,3}(?:within|inside|in)\s+me)\b"
    r"|\b(?:transform|turn|change|shift|morph)(?:s|ing)?\s+(?:myself\s+)?into\s+"
    r"(?P<pred5>(?:a|an|the|my)\s+[^.,;!?\"“”]{2,40})",
    re.I)
# What makes a predicate a claim about WHAT one is rather than a passing state ("I am
# tired", "I am the last in the queue"): a being, a rank, a lineage, a calling, a power.
_IDENTITY_HEAD = re.compile(
    r"\b(?:god|gods|goddess|deity|deities|divine|divinity|demigod|immortal|angel|"
    r"celestial|demon|devil|fiend|dragon|wyrm|lich|vampire|werewolf|beast|spirit|"
    r"ghost|titan|giant|elemental|king|queen|prince|princess|emperor|empress|heir|"
    r"heiress|lord|lady|noble|royal|royalty|chosen|prophet|prophesied|saint|messiah|"
    r"savio[u]r|herald|avatar|incarnation|reincarnation|vessel|champion|hero|legend|"
    r"legendary|master|grandmaster|archmage|wizard|sorcerer|sorceress|witch|warlock|"
    r"mage|necromancer|assassin|knight|paladin|general|captain|commander|warrior|"
    r"swordsman|swordswoman|fighter|rogue|thief|cleric|priest|priestess|druid|ranger|"
    r"monk|bard|barbarian|oracle|summoner|alchemist|inquisitor|magus|slayer|hunter|"
    r"shaman|merchant|guard|soldier|mercenary|noblewoman|nobleman|form|nature|self|"
    r"identity|power|powers|might|magic|gift|gifted|blood|lineage|heritage|descendant|"
    r"blessed|cursed|marked|being|creature|man|woman|human|mortal|elf|dwarf|orc|"
    r"halfling|gnome|tiefling|aasimar|asura|dragonborn|undead|spirit)s?\b", re.I)
_CLAIM_STOP = frozenset({"the", "a", "an", "my", "of", "and", "who", "that", "with",
                         "from", "this", "here", "there", "in", "on", "to", "for",
                         "within", "inside", "me", "am", "i", "actually", "really",
                         "truly", "secretly", "no", "not", "mere", "one", "true", "real",
                         "secret", "hidden", "very", "own"})


def _sheet_vocabulary(pc) -> set[str]:
    """Every word the sheet can vouch for: the name, the people, the class and its paths,
    the feats and powers, the background and the past the world bound to it."""
    bits: list[str] = []
    for attr in ("name", "race", "heritage", "char_class", "background", "gender"):
        bits.append(str(getattr(pc, attr, "") or ""))
    cd = getattr(pc, "class_data", None) or {}
    if isinstance(cd, dict):
        bits.append(str(cd.get("name", "") or ""))
    for attr in ("paths", "feats", "background_ties"):
        for x in (getattr(pc, attr, None) or []):
            bits.append(str(x))
    try:
        from rules import leveling

        bits.extend(str(n) for n in leveling.usable_names(pc))
    except Exception:  # noqa: BLE001 — an unreadable sheet vouches for nothing extra
        pass
    try:
        bits.extend(str(x) for x in (pc.carried() or []))
    except Exception:  # noqa: BLE001
        pass
    return {w for b in bits for w in re.findall(r"[a-z][a-z'’-]{2,}", b.lower())}


# The shape of producing a thing: taking it out, showing it, handing it over, putting it
# on. The VERB is what makes this a claim about having something — "the crown is heavy"
# is a sentence about a crown, and "I pull out my crown" is a claim that one is in the
# folds of your coat.
#
# Production and display only, and a DEFINITE article only. Both are narrowings made
# after measuring the first cut against a real sheet: a verb list that included offer,
# give and place turned "I offer him a drink" into a delusion beat, and `a`/`an` is
# somebody naming a kind of thing rather than asserting they have a particular one.
# A guard that fires on an innocuous line costs more than the one it catches.
_PRODUCE = re.compile(
    r"\b(?:i\s+)?(?:pull|pulls|take|takes|draw|draws|produce|produces|fish|fishes|"
    r"show|shows|display|displays|present|presents|brandish|brandishes|flash|flashes|"
    r"unroll|unrolls|unfurl|unfurls|unwrap|unwraps|hand|hands|don|dons|wear|wears|"
    # `hold` and `lift` only with a particle: "I hold up the crown" is a display and
    # "I hold the rope" is a grip.
    r"put|puts|holds?\s+(?:up|out|aloft)|lifts?\s+up)\b"
    r"(?:\s+(?:out|up|over|down|forth|on|off|into|in|it|them|him|her|about))*"
    r"\s+(?:to\s+\w+\s+|him\s+|her\s+|them\s+)?"
    r"(?P<art>my|the|his|her|their|our)\s+"
    r"(?P<thing>[a-z][a-z'’-]*(?:\s+[a-z][a-z'’-]*){0,2})", re.I)

# Where a captured phrase stops being the thing and starts being the rest of the
# sentence. "my crown and display it for all to see" is a crown.
_PHRASE_END = frozenset({
    "and", "or", "but", "then", "so", "as", "while", "before", "after", "if",
    "to", "for", "with", "at", "in", "on", "into", "onto", "from", "of", "it",
    "them", "him", "her", "all", "everyone", "up", "out", "over", "down", "off",
    "aloft", "away", "aside", "across", "toward", "towards", "against", "beside",
    "behind", "under", "above", "around", "through", "past", "by", "near", "when",
})

# Words that are never a possession claim even in that shape: parts of the body, and the
# ways and directions a person takes. Not a content list — a player cannot "find a way
# around" this one in any way that matters, because nothing follows from producing your
# own hand.
#
# `_NOT_A_POSSESSION`, not `_NOT_A_THING`: the first cut of this used the latter name and
# SHADOWED the abstract-noun set at the top of this file, which `_is_a_thing` reads — so
# "I accept the offer" started minting an item again and a chair leg stopped being one.
# Seven tests caught it. The abstract set is reused below rather than copied.
_NOT_A_POSSESSION = frozenset({
    "hand", "hands", "palm", "palms", "fist", "fists", "arm", "arms", "finger",
    "fingers", "thumb", "head", "face", "eyes", "eye", "chin", "shoulder",
    "shoulders", "chest", "foot", "feet", "leg", "legs", "back", "voice", "breath",
    "weight", "tongue", "teeth", "hair", "body", "self", "attention", "gaze", "look",
    "time", "care", "word", "words", "name", "hood", "way", "place", "seat", "step",
    "ground", "distance", "silence", "peace", "temper", "guard", "ear", "ears",
    "nose", "mouth", "lips", "knee", "knees", "elbow", "wrist", "waist", "hip",
    # What is ON the body rather than carried: a character showing their scars is
    # showing themselves.
    "scar", "scars", "wound", "wounds", "skin", "blood", "tattoo", "tattoos",
    "brand", "mark", "marks", "bruise", "bruises", "burn", "burns",
    # Ways and directions. "I take the true road north" is a route, not a thing in a
    # coat, and the first cut read it as a claim to own a road.
    "road", "path", "way", "route", "trail", "street", "lane", "stairs", "stair",
    "steps", "turn", "corner", "door", "gate", "north", "south", "east", "west",
    "left", "right", "lead", "reins", "first", "last",
})

# Taking something FROM somewhere is acquiring it, not claiming to have had it — and
# that is an action the engine already has doors for. "I take the bread from the stall"
# is a `give` or a buy; it is not a man producing bread out of his coat.
_FROM_SOMEWHERE = re.compile(r"^\s*(?:from|off|out of|in)\b", re.I)

# The smallest word that can be matched against the sheet by containment, so "sword"
# finds "longsword" and "axe" finds "battleaxe". Three, because the first cut used four
# AND passed anything shorter as vouched — which let "the sealed jar" through on the
# strength of "jar" being three letters, and the head noun is exactly the word that must
# be checked.
_STEM = 3


def _vouched_for(word: str, vouched: set[str]) -> bool:
    """Whether the sheet can account for this noun.

    Containment both ways and not equality: a player who says "I draw my sword" with a
    longsword on the sheet has drawn the thing they own, and the item this closes is
    explicit that the check "has to be able to tell those apart on a sheet, not on a
    word list".
    """
    word = word.strip().lower()
    if not word:
        return True
    if word in vouched:
        return True
    return any(word in v or v in word for v in vouched if len(v) >= _STEM)


def false_possession(player_text: str, scene) -> str:
    """The thing the player says they produce that the sheet cannot account for, or "".

    Item 37, reported 2026-09-20 with a screenshot. The player typed *"I pull out my
    crown and display it for all to see"* and the narrator produced one — "you reach into
    the folds of your traveler's outfit and produce the circlet … a heavy, brutal thing of
    worked metal", the yard falling silent around it. Their note: **"I have no crown to
    display."**

    Measured the same day against a sheet carrying one club: `false_claim` caught "I am
    the lost heir of the old kings" and caught NOTHING for "I pull out my crown", "I show
    them my royal seal", "I hand him the deed to the mill" or "I draw my longsword". So
    it was never about crowns: **any** gear the player named was conjured, a weapon they
    had never bought included.

    It is the possession half of a law this app already keeps for people. Group 8 built
    `rules/scope.py` so nobody is created on the strength of a phrase; things kept no such
    rule. The tradition is the same one that settled group 8 — Inform's parser looks
    through what is in scope, and when nothing matches it refuses: *"You can't see any
    such thing."* A noun does not enter play because somebody said it.

    **Shape, then sheet**, exactly as `false_claim` works and for the reason the player
    gave the first time: they would find a way around a word list, and they would. The
    shape is producing/showing/handing/wearing; the sheet then decides, out of everything
    it can vouch for — what is carried, worn, in the satchel, in the purse, and the props
    this character is holding.

    Returns the claim in the player's own words — "produce a crown you do not have" — so
    it can travel the door that already exists: the Bluff the room rolls against
    (`inject_false_claim`), the prose told it is false (`prompts.false_claim_block`), the
    finding that catches prose making it true, and the crowd's reaction. The 2026-09-18
    ruling was the player's own: *"It should read as my character being delusional and the
    people should see it similarly."* A man who flourishes a crown he does not have is
    exactly that act with a prop in it.
    """
    if scene is None or not player_text or "?" in player_text:
        return ""
    pc = scene.pc()
    if pc is None:
        return ""
    # A sheet that cannot answer the question judges nothing. The same discipline as
    # `fire_context` and `here` in the reviewer: a guard that guesses is worse than one
    # that abstains, and this one's failure mode is turning "I draw my sword" into a
    # delusion beat for a character whose gear simply could not be read.
    if not hasattr(pc, "carried"):
        return ""
    vouched = _sheet_vocabulary(pc)
    # What this character is holding by the props ledger, and what they have on: both are
    # things the sheet vouches for and neither is in `carried()`.
    for attr in ("equipped", "armour"):
        vouched |= {w for w in re.findall(r"[a-z][a-z'’-]{2,}",
                                          str(getattr(pc, attr, "") or "").lower())}
    for rec in (getattr(scene, "props", None) or []):
        if isinstance(rec, dict) and rec.get("held_by") == pc.ref:
            vouched |= {w for w in re.findall(r"[a-z][a-z'’-]{2,}",
                                              str(rec.get("name") or "").lower())}
    # `carried()` is "everything that could plausibly be damaged" — weapons, armour,
    # worn slots — and a crown in the pack is not that. The goods ledger is what "am I
    # carrying one" actually means, and it was the half this check could not see.
    for name in (getattr(pc, "goods", None) or {}):
        vouched |= {w for w in re.findall(r"[a-z][a-z'’-]{2,}", str(name).lower())}
    for iid, stock in (getattr(pc, "stock", None) or {}).items():
        vouched |= {w for w in re.findall(r"[a-z][a-z'’-]{2,}",
                                          f"{iid} {getattr(stock, 'base', '')}".lower())}

    # The generic word for a slot the sheet has something in. A character in a chain
    # shirt who says "I put on my armour" is putting on the armour they own, and the
    # sheet spells it "chain shirt" — a containment match cannot bridge that and should
    # not try to.
    if str(getattr(pc, "armour", "") or "").strip().lower() not in ("", "none"):
        vouched |= {"armour", "armor"}
    if str(getattr(pc, "equipped", "") or "").strip():
        vouched |= {"weapon", "blade", "arms"}

    for m in _PRODUCE.finditer(str(player_text)):
        phrase = " ".join(m.group("thing").split()).lower().strip()
        if not phrase:
            continue
        words: list[str] = []
        for w in re.findall(r"[a-z][a-z'’-]+", phrase):
            if w in _PHRASE_END:
                break
            words.append(w)
        if not words:
            continue
        phrase = " ".join(words)
        # The head noun is the last word of the phrase — "royal seal", "deed to the
        # mill" — and a claim is false only when NOTHING in it is accounted for. A
        # player who says "my father's sword" with a sword on the sheet has one.
        if any(w in _NOT_A_POSSESSION for w in words):
            continue
        # And an abstract noun is not a possession either — "I take the chance", "I
        # accept the offer". `_is_a_thing` is this file's own answer to that question,
        # reading the HEAD noun, and asking it here means one list rather than two.
        if not _is_a_thing(phrase):
            continue
        # Taken FROM somewhere — checked against what the capture ran over as well as
        # what follows it, since the phrase group may have swallowed the preposition.
        rest = (" ".join(m.group("thing").split()[len(words):]) + " "
                + str(player_text)[m.end():])
        if _FROM_SOMEWHERE.match(rest):
            continue        # an action the engine has doors for, not a claim
        if any(_vouched_for(w, vouched) for w in words):
            continue
        # Coin is its own question: the purse, not the pack.
        if re.search(r"\b(?:coin|coins|gold|silver|copper|purse|money)\b", phrase):
            if any(int(n) > 0 for n in (getattr(pc, "purse", None) or {}).values()):
                continue
        return f"produce {'a ' if m.group('art') in ('my', 'the') else ''}{phrase} " \
               f"you do not have"
    return ""


def _denied(text: str, start: int) -> bool:
    """Whether the words just before `start` deny the thing: "I am NOT a god"."""
    return bool(re.search(r"\b(?:not|no|never|n't|hardly)\s+(?:a|an|the|even\s+a)?\s*$",
                          text[max(0, start - 16):start], re.I))


def _as_they(claim: str) -> str:
    """The player's words, said about them: "I am the heir" → "are the heir"."""
    s = " ".join(claim.split())
    s = re.sub(r"^(?:i(?:'m|’m| am))\b", "are", s, flags=re.I)
    s = re.sub(r"^(?:i(?:'ve|’ve| have) always been)\b", "have always been", s, flags=re.I)
    s = re.sub(r"^i was born\b", "were born", s, flags=re.I)
    s = re.sub(r"\bmyself\b", "themselves", s, flags=re.I)
    s = re.sub(r"\bmy\b", "their", s, flags=re.I)
    s = re.sub(r"\bme\b", "them", s, flags=re.I)
    s = re.sub(r"\bi\b", "they", s, flags=re.I)
    return s


def false_claim(player_text: str, scene) -> str:
    """The player's own words for what they claim to be, when the sheet says otherwise.

    "" when the line makes no such claim, is a question, or is something the sheet
    vouches for. Otherwise the claim, in their words said about them — "reveal their
    true form as a divine being", "are the king's lost heir" — for the Bluff it becomes
    (`inject_false_claim`), the prose that has to write it as false
    (`prompts.false_claim_block`), the finding that catches prose which makes it true
    (`narration.review`, `grants-a-nature`), and the crowd's reaction (`note_heat`,
    kind "delusion").

    **Shape, then sheet.** The first cut listed gods and dragons; the player's answer
    was that they would find a way around a word list, and they would. What is caught
    now is the shape of asserting what one IS — "I am the …", "I reveal that I am …",
    "my true …", "the … within me", "into a …" — and the predicate must name a being,
    a rank, a lineage, a calling or a power (`_IDENTITY_HEAD`): "I am tired" and "I am
    the last in the queue" are states, not claims. Then the sheet decides. "I am a
    rogue" on a rogue's sheet, "I am a pit-fighter" with that background bound, "I
    unleash the blood in me" for a Blood Bender, a druid's "I turn into a bear": the
    words are the sheet's own and the line goes through to the injectors that route
    them. The same words on a sheet that has none of them are the claim.

    **Speech counts.** Elsewhere a boast inside quotation marks is the character's to
    tell and is redacted first. Here it is the clearest boast there is — "if I were to
    say aloud that I will reveal my true nature and then nothing happens … people
    should roll their eyes" — so a lie told out loud is a Bluff the room rolls against.
    A denial is not a claim ("I am not a god").

    The first cut of all this was a door: the line was handed back before any model
    was asked, the way fiat is. The player's own correction, 2026-09-18: "It should
    read as my character being delusional and the people should see it similarly."
    A claim is a boast, and a boast is a Bluff the room sees through or half-believes.
    So the turn PLAYS, with the engine holding the claim false.
    """
    if scene is None or not player_text or "?" in player_text:
        return ""
    text = str(player_text)
    pc = scene.pc()
    if pc is None:
        return ""
    vouched = _sheet_vocabulary(pc)
    # A power the sheet grants that reads like a form: Wild Shape, an aspect, an
    # avatar. Such a line is an ability being used and `inject_ability` routes it.
    shapeshifter = any(_SHAPE_ABILITIES.search(w) for w in vouched)

    candidates: list[str] = []
    for m in _SELF_CLAIM.finditer(text):
        pred = next((g for g in (m.group("pred"), m.group("pred2"), m.group("pred3"),
                                 m.group("pred4"), m.group("pred5")) if g), "")
        pred = " ".join(pred.split())
        if not pred or re.match(r"^(?:no|not)\b", pred, re.I) and not re.match(
                r"^no\s+mere\b", pred, re.I):
            continue                      # a denial is not a claim
        if not _IDENTITY_HEAD.search(pred):
            continue                      # a state, not what one is
        words = {w for w in re.findall(r"[a-z][a-z'’-]{2,}", pred.lower())} - _CLAIM_STOP
        heads = {w for w in words if _IDENTITY_HEAD.fullmatch(w)}
        # The sheet vouches when it holds the claim's head; a sheet with a form-granting
        # power behind it vouches for any talk of forms, shapes and turning into things.
        if heads & vouched:
            continue
        if shapeshifter and (m.group("pred5") or re.search(
                r"\b(?:form|shape|nature|self|aspect|guise|skin)s?\b", pred, re.I)):
            continue
        if words and words <= vouched:
            continue
        candidates.append(m.group(0))
    for rx in (_CLAIMS_A_NATURE, _CLAIMS_GODHOOD):
        m = rx.search(text)
        if m and not shapeshifter and not _denied(text, m.start()):
            candidates.append(m.group(0))
    if not candidates:
        # And the possession half of the same law (item 37). Routed through THIS
        # function rather than beside it, because everything a false claim already
        # travels — the Bluff the room rolls, the prose told to hold it false, the
        # finding that catches prose making it true, the crowd's reaction — is exactly
        # what a man flourishing a crown he does not have needs, and a second door
        # would be a second copy of all of it. The item's own words: "The answer is
        # already built and already ratified by the player — it just has the wrong door."
        return false_possession(text, scene)
    return _as_they(candidates[0].strip())


def claims_a_nature(player_text: str, scene) -> str:
    """Kept for the callers that asked the old question; the answer is the claim."""
    return false_claim(player_text, scene)


def inject_false_claim(raw_intents, player_text: str, scene) -> list:
    """A claim about what you are is a Bluff, and the room rolls to see through it.

    PF1e's own answer: convincing somebody of something untrue is Bluff against their
    Sense Motive, and the more outlandish the lie the harder it is — "I am a god" is
    at the far end. The check is the player's to roll, visibly; its verdict reaches the
    prose as a tell, and the prose is told what each verdict looks like on the faces
    around them (`prompts.false_claim_block`). Replaces a bare `narrate_only`, the
    way every injector here does, and never doubles a Bluff the model already wrote.
    """
    if not isinstance(raw_intents, list) or not false_claim(player_text, scene):
        return raw_intents
    for r in raw_intents:
        if isinstance(r, dict) and str(r.get("op", "")).lower() == "check":
            skill = str((r.get("params") or {}).get("skill", "")).lower()
            if skill in ("bluff", "intimidate"):
                return raw_intents
    kept = [r for r in raw_intents
            if not (isinstance(r, dict) and str(r.get("op", "")).lower() == "narrate_only")]
    kept.append({
        "op": "check", "actor": "pc",
        "params": {"skill": "bluff", "dc": {"band": "heroic"}},
        "because": "claiming to be what the sheet says they are not",
        "visibility": "player",
    })
    return kept


def _psychic_called(text: str) -> str:
    """What to name back at them — their own words, never a label we invented.

    The engine's door prints "no ability called <X>; they can use: …", and the whole
    value of that sentence is that it quotes the claim. A player who wrote "godly
    powers" and is told there is no ability called "psychic powers" has been answered
    about somebody else's turn.
    """
    for pattern, name in _PSYCHIC_NAMES:
        if pattern.search(text):
            return name
    claimed = _CLAIMED_FACULTY.search(text) or _CLAIMED_SOURCE.search(text)
    if claimed:
        # Their phrasing, minus the reaching verb and the possessive: "my godly powers"
        # reads back as "godly powers".
        said = re.sub(
            r"^(?:\w+(?:ing)?\s+)?(?:for\s+|on\s+|upon\s+)?(?:my|the|his|her|their)\s+"
            r"(?:own\s+)?", "", claimed.group(0).strip(), flags=re.I)
        return " ".join(said.split())
    if _CLAIMS_GODHOOD.search(text):
        return "godhood"
    return "psychic powers"


def refuse_unnamed_power(raw_intents, player_text: str, scene) -> list:
    """Reaching into somebody's mind is an ability or it is nothing.

    Reported from the table 2026-09-09: "I was able to break the game and use psychic
    powers to manipulate the people and story in ways that should not be possible."

    Two things were wrong and this is the second. The engine now refuses a mind changed
    with no document behind it (`rules/engine.py`, the `condition` gate), but that only
    catches the model WRITING an intent. A psychic sentence more often produced no
    mechanical intent at all — just `narrate_only` — and the narrator obligingly wrote
    the merchant handing the goods over. Nothing had to be refused, because nothing was
    ever proposed.

    So the declaration is turned into the one it actually is: "I use <a power>". The PC
    either has it or does not, and the engine's own door answers — "no ability called
    telepathy; they can use: …" — which is the same answer, in the same words, that
    naming a made-up power out loud already got. That is the GAS rule and it is the
    whole of the fix: an ability that was never granted cannot be activated.

    Speech is redacted first. "I tell the guard I can read minds" is a BOAST, and a
    character is entitled to lie about what they can do — measured on the same corpus
    that taught this file the difference between saying a thing and doing it.
    """
    if not isinstance(raw_intents, list) or not player_text or scene is None:
        return raw_intents
    if "?" in player_text:
        return raw_intents
    said = redact_speech(str(player_text))
    # Three doors into the same refusal: reaching into a mind, reaching for a faculty of
    # any name, or claiming to be the kind of thing that would not need one.
    if not (_PSYCHIC.search(said) or _CLAIMED_FACULTY.search(said)
            or _CLAIMED_SOURCE.search(said) or _CLAIMS_GODHOOD.search(said)):
        return raw_intents
    pc = scene.pc()
    if pc is None:
        return raw_intents

    # A power they really have, already routed by `inject_ability` or named outright,
    # stands. This is the complement of that door, never a second opinion on it.
    from rules import leveling

    for r in raw_intents:
        if not isinstance(r, dict):
            continue
        if str(r.get("op", "")).lower() in ("use_ability", "cast"):
            named = str((r.get("params") or {}).get("ability", "")).strip()
            if not named:
                return raw_intents          # a spell, or an ability the door picked
            _path, found, _fx = leveling.find_ability(pc, named)
            if found:
                return raw_intents

    name = _psychic_called(said)
    # Everything the model guessed is a guess about a power that was never granted.
    # `refuse_unknown_ability` learned this the expensive way: told to drop only the
    # fight-makers, the next probe came back with `ability_damage con 1d4` instead and
    # it landed. What survives is what carries no number and reaches no mind.
    from rules.intents import AMOUNT_OPS

    kept = []
    for r in raw_intents:
        if not isinstance(r, dict):
            continue
        op = str(r.get("op", "")).lower()
        if op in AMOUNT_OPS or op in ("condition", "compel", "spawn", "attack", "save"):
            continue
        kept.append(r)
    return kept + [{"op": "use_ability", "actor": pc.ref,
                    "because": f"the player reached for {name}",
                    "params": {"ability": name}}]


# --- a thing summoned that nothing grants ------------------------------------------
#
# `play/player_input.py` hands back the fiat phrasings — "I make a wagon of salt
# appear" — before a model is ever called, because there is no roll that could decide
# them. It deliberately leaves `summon`, `conjure` and `manifest` alone: those are spell
# vocabulary, a summoner is entitled to type them, and whether this character has one is
# a question for the sheet rather than a regex.
#
# This is that question. Same shape as `refuse_unnamed_power` above and the same rule
# underneath it: a thing that was never granted cannot be activated. A real summoner's
# turn produces a `cast`, which stands down untouched; what is left is a `spawn` nobody
# can account for, which is how a level 1 rogue's declaration puts a creature on the
# board.
_SUMMONS = re.compile(
    _DECLARES + r"(?:summon|conjure|manifest|materiali[sz]e)\b"
    r"(?:\s+up)?\s+(?:a|an|the|some|my|two|three|\d+)\b", re.I)

# What a player's turn may not do: put a thing in the world, or mint one into a purse.
# Both are bounded in `rules/intents.py` and neither is gated on anything the player
# has — `spawn` is the GM's op for reading opposition into a scene, and it does not stop
# being the GM's op because the model wrote it on the player's behalf.
_CREATING_OPS = ("spawn", "give")


def refuse_declared_creation(raw_intents, player_text: str, scene) -> list:
    """A creature summoned by somebody with nothing that summons does not arrive.

    The complement of the fiat handback in `play/player_input.py`, for the half that
    handback must not take: "I summon a celestial dog" is a legitimate sentence from a
    summoner and an empty claim from a rogue, and only the sheet knows which.

    Found 2026-09-17, by the player who reported the salt cart asking what else would
    get through — "I use my rope to explode the enemy" and its neighbours. The faculty
    fix had closed the phrasing they used and not the room behind it: naming anything
    mundane, or nothing at all, left `spawn` untouched.
    """
    if not isinstance(raw_intents, list) or not player_text or scene is None:
        return raw_intents
    if "?" in player_text:
        return raw_intents
    said = redact_speech(str(player_text))
    if not _SUMMONS.search(said):
        return raw_intents
    pc = scene.pc()
    if pc is None:
        return raw_intents

    from rules import leveling

    for r in raw_intents:
        if not isinstance(r, dict):
            continue
        op = str(r.get("op", "")).lower()
        if op == "cast":
            return raw_intents              # a spell; the spell's own door answers
        if op == "use_ability":
            named = str((r.get("params") or {}).get("ability", "")).strip()
            if not named:
                return raw_intents
            _path, found, _fx = leveling.find_ability(pc, named)
            if found:
                return raw_intents

    kept = [r for r in raw_intents
            if isinstance(r, dict)
            and str(r.get("op", "")).lower() not in _CREATING_OPS]
    return kept + [{"op": "use_ability", "actor": pc.ref,
                    "because": "the player reached for a summoning",
                    "params": {"ability": "a summoning"}}]


# "I drink my healing potion", "I quaff the elixir", "I throw the flask at c1",
# "I apply the salve": a using verb and, somewhere after it, a jar word. The jar itself
# is matched against the satchel by name; the sentence only has to be about one.
_USES_A_JAR = re.compile(
    r"\bI\s+(?:drink|quaff|swallow|down|gulp|sip|throw|hurl|lob|apply|smear|rub|"
    r"use|uncork|open)\b[^.!?]{0,60}?\b"
    r"(potion|draught|elixir|tincture|tea|philtre|philter|salve|poultice|vial|flask|"
    r"tonic|brew|remedy|antidote|oil|styptic|balm|unguent|jar)s?\b", re.I)


def _jar_instead(raw_intents, ref: str, item_id: str, because: str) -> list:
    """The list with every number-bearing op dropped and one `use_item` in its place.

    A model shown a potion still writes `heal 1d8+1` beside it — measured in the
    stage-7 probes — so the guess and the door cannot both stay: the door is the
    only source of the number, and the guess would land a second one.
    """
    from rules.intents import AMOUNT_OPS

    kept = [r for r in raw_intents
            if isinstance(r, dict)
            and str(r.get("op", "")).lower() not in AMOUNT_OPS
            and str(r.get("op", "")).lower() != "drink"]
    for r in kept:
        if (str(r.get("op", "")).lower() == "use_item"
                and str((r.get("params") or {}).get("item", "")).strip().lower() == item_id):
            return kept
    kept = [r for r in kept if str(r.get("op", "")).lower() != "use_item"]
    return kept + [{"op": "use_item", "actor": ref, "because": because,
                    "params": {"item": item_id, "how": "drink"}}]


# The ops a player turn's model reply may leave without an actor and mean the PC.
#
# `attack` is deliberately NOT here, and gets its own gated door inside the function: on
# a turn where the GM also moves somebody, an attack with no actor might be theirs, and
# filling it with the PC would aim the player's fist at the wrong body.
_ACTS_ITSELF = ("cast", "use_item", "use_ability", "hazard")


def fill_missing_actor(raw_intents, player_text: str, scene) -> list:
    """A `cast` with no actor on the player's turn is the player casting.

    Measured by the stage-8 verifiers, 2026-09-03: told to cast magic missile, the
    model wrote {"op": "cast", "params": {"spell": "magic missile", "at": "c2"}} six
    attempts of seven — the schema requires only `op` — and `_check_cast` refused
    "no such actor None" as a refs error, which regenerates rather than repairs, so
    every attempt burned on the same omission and the turn degraded to narration.
    The fix is a fill, not a schema change: `fill_obvious_targets` already fills the
    target the same way, and the actor of the player's own spell is not a guess.

    **And `attack`, read off a live save on 2026-09-17.** The same shape, the same cost,
    two weeks later: "I don my Extracorporeal Blood Armament and punch the guard in the
    back of the lower spine" produced `{"op": "attack", "actor": null}` on **seven
    consecutive attempts** — five from the narrator, then two more after the turn was
    handed to the fallback model — and every one was refused with `attack: unknown actor
    None`. Eighty-three seconds, seven model calls, and the turn degraded to narration:
    no roll, no initiative, no fight, and a guard the prose said had collapsed still
    standing at 11/11 in the scene list.

    The `cast` fix above was written for exactly this and `attack` was never added to it.
    It is not added to `_ACTS_ITSELF` now either, because an attack is the one op on this
    list that somebody else might plausibly be doing on the player's turn — so the fill
    is gated on the player's own words saying who is swinging, which is a question this
    file already answers for `wants_a_fight`.
    """
    if not isinstance(raw_intents, list) or scene is None:
        return raw_intents
    pc = scene.pc()
    if pc is None:
        return raw_intents
    # Speech redacted first, for the reason the top of this file gives at length: a
    # character who SAYS "I will punch him" has not swung at anybody.
    swinging = bool(player_text) and _player_is_the_one_swinging(
        redact_speech(str(player_text)))
    out = []
    for r in raw_intents:
        if isinstance(r, dict) and not r.get("actor"):
            op = str(r.get("op", "")).lower()
            if op in _ACTS_ITSELF or (op == "attack" and swinging):
                r = dict(r, actor=pc.ref)
        out.append(r)
    return out


def declare_use_item(raw_intents, player_text: str, scene) -> list:
    """A jar the player names is opened by the jar door, never by a written number.

    Stage 8's declarer. Measured twice on 2026-09-02 (docs/stage-7-plan.md): "I drink
    my healing potion" with an empty satchel came back as a bare `heal 1d8+1` — the
    prompt's own worked example — and the engine applied it. With a jar in the
    satchel the same sentence came back as `heal` beside the potion, so the number
    landed twice. The sentence declares one thing: a jar is being used. If the satchel
    holds one that matches, the turn gets `use_item` by id and every number-bearing
    op is dropped. If nothing matches, the turn gets `use_item` naming what was said,
    and the engine prints "not carrying that; they have: …" — the truth the player
    needs — and the numbers are dropped all the same, because there is no jar to
    supply one.
    """
    if not isinstance(raw_intents, list) or not player_text or scene is None:
        return raw_intents
    if "?" in player_text:
        return raw_intents
    m = _USES_A_JAR.search(str(player_text))
    if not m:
        return raw_intents
    pc = scene.pc()
    if pc is None:
        return raw_intents
    from rules.consumables import resolve_stock

    stock = getattr(pc, "stock", None) or {}
    # The words after the verb, e.g. "my healing potion" — the same resolver the jar
    # door uses, so the declarer and the engine cannot disagree about which jar.
    wanted = " ".join(str(player_text)[m.start():m.end()].split()[2:]).strip(".,!;").lower()
    iid, _fits = resolve_stock(stock, wanted)
    if iid is not None:
        return _jar_instead(raw_intents, pc.ref, iid,
                            "the player drinks it; the jar says what it does")
    # Nothing carried fits: the door prints "not carrying" with the real satchel, or
    # "which do you mean" when two fit, and the written numbers go all the same.
    return _jar_instead(raw_intents, pc.ref, " ".join(wanted.split()[-2:]) or wanted,
                        "the player reached for a jar")


def refuse_leaving_in_place(raw_intents, player_text: str, scene, world=None) -> list:
    """Told to leave, the model may not name the room the party is standing in.

    Measured live on 2026-09-01, twice in one probe: "I leave the merchant and head
    out" — with the schema demanding a `travel` and the brief listing the market, the
    gate and the tavern — came back as `travel place=the market`, the place the party
    was already in. The engine correctly answered "You are already at the market", and
    the merchant stayed in view. The generated place names are coarser than the
    fiction (a shop inside the market has no name of its own), which nothing here can
    fix; but a departure that goes nowhere is detectable, and the repo's rule is to
    repair it with a targeted call rather than a guess.

    Raised, not rewritten: an `IntentError` from inside the repair chain goes back
    through the planner's correction path, so the model is asked again with the places
    that WOULD have worked in front of it. Guessing one for it is the free-text `spot`
    coming back through a side door.
    """
    from rules.intents import IntentError

    if not isinstance(raw_intents, list) or scene is None:
        return raw_intents
    if not player_departs(player_text):
        return raw_intents
    travels = [r for r in raw_intents
               if isinstance(r, dict) and str(r.get("op", "")).lower() == "travel"]
    if not travels:
        return raw_intents
    from rules import places as places_mod

    location = None
    if world is not None and getattr(scene, "location_id", None):
        try:
            location = world.get(scene.location_id)
        except Exception:
            location = None
    known = places_mod.for_scene(location or getattr(scene, "location_id", None),
                                 getattr(scene, "at", ""))
    here = places_mod.find(known, getattr(scene, "at", "")) or (known[0] if known else None)
    if here is None or len(known) < 2:
        return raw_intents
    others = [p.name for p in known if p.id != here.id]
    for t in travels:
        params = t.get("params") or {}
        place = str(params.get("place") or "").strip()
        biome = str(params.get("biome") or "").strip().lower()
        stays = False
        if place:
            target = places_mod.find(known, place)
            stays = target is not None and target.id == here.id
        elif biome:
            stays = biome == here.terrain
        if stays:
            raise IntentError(
                f"travel: the party is already at {here.name}. They said they are "
                f"leaving — name where to: {', '.join(others)}.", "legality")
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

    # A move that changes ROOM without changing ground — a stall for the square, a
    # taproom for the street — is `travel` with a `place` now, and this injector
    # deliberately does not guess one.
    #
    # It was written and then removed: an extractor good enough to read "I go into the
    # tavern" also reads "I walk across the yard to the gate", which is movement inside
    # one scene rather than a new one, and the distinction is semantic. This file's own
    # doctrine, two hundred lines down, is that an injector guessing a value is strictly
    # worse than the model choosing it with the scene in front of it — and a guessed
    # place is worse than a guessed target, because it reaches the next brief as a
    # stated fact about where the party is standing.
    #
    # So the room change is documented in the briefing and accepted by the op, and the
    # model names it. What stops the old room being narrated back when the model stays
    # silent is `update_thread`, which now clears the engagement on a departure.
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
# "a search for ore": the same door as forage, for the ground's minerals. The nouns
# are the ore words, so "I search for the guard" and "I look for my purse" cannot
# fire; a false prospect charges hours and a Survival toll.
_PROSPECTS = re.compile(r"\bprospect(?:s|ing)?\b", re.I)
_ORE_WORDS = r"(?:ores?|minerals?|veins?|iron|copper|tin|silver|gold|lead|metal|seams?)"
_GATHERS_ORE = re.compile(
    # "search the hillside for ore", "look for a vein", "pan the stream for gold":
    # the verb, then "for", then the ore word within a couple of words — so "I look
    # at the silver ring" and "I search for the guard" cannot fire.
    r"\b(?:gather|search|look|hunt|scout|pan|dig|prospect)\b[^.!?]{0,30}?"
    r"\bfor\s+(?:\w+\s+){0,2}" + _ORE_WORDS + r"\b"
    # "dig out the iron", "mine the seam": the digging verbs need no "for".
    r"|\b(?:dig|mine)\b[^.!?]{0,20}?\b" + _ORE_WORDS + r"\b", re.I)


# "I wait at the market for ten hours", "I spend the whole day here", "we linger till
# evening": time the player means to pass. The playtest measured both as
# `narrate_only` with the clock unmoved, so a scheme keyed on the hours never came.
_WAITS = re.compile(
    r"\b(?:wait|linger|rest here|stay here|spend|pass|idle|kill time|while away)\b[^.]{0,40}?"
    r"\b(?:(\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten|twelve|half a|the whole|all|the rest of the)\s+"
    r"(hours?|hour|day|days|morning|afternoon|evening|night|watch))\b", re.I)
_WORDS_TO_N = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
               "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twelve": 12, "half a": 0.5,
               "the whole": 1, "all": 1, "the rest of the": 0.5}
_UNIT_HOURS = {"hour": 1, "hours": 1, "day": 10, "days": 10, "morning": 4, "afternoon": 4,
               "evening": 3, "night": 8, "watch": 4}


def inject_wait(raw_intents, player_text: str, scene) -> list:
    """Time the player says they pass becomes `advance_time`, in minutes."""
    # Speech is not action: the character's own words are blanked before any
    # cue is looked for here. See `redact_speech`.
    player_text = redact_speech(player_text)
    if not isinstance(raw_intents, list) or not player_text or scene is None:
        return raw_intents
    if "?" in player_text:
        return raw_intents
    present = {str(r.get("op", "")).lower() for r in raw_intents if isinstance(r, dict)}
    if present & {"advance_time", "rest", "forage", "prospect", "travel", "venture"}:
        return raw_intents
    m = _WAITS.search(player_text)
    if not m:
        return raw_intents
    n = m.group(1).lower() if m.group(1) else "1"
    count = float(n) if n.isdigit() else _WORDS_TO_N.get(n, 1)
    unit = m.group(2).lower()
    hours = count * _UNIT_HOURS.get(unit, 1)
    minutes = int(max(10, min(24 * 60, round(hours * 60))))
    pc = scene.pc()
    if pc is None:
        return raw_intents
    return [r for r in raw_intents if not (isinstance(r, dict) and str(r.get("op", "")).lower() == "narrate_only")] + [{
        "op": "advance_time", "actor": pc.ref,
        "params": {"amount": minutes, "unit": "minutes"},
        "because": "the player passed the time",
    }]


def inject_prospect(raw_intents, player_text: str, scene) -> list:
    """Make a declared search for ore reach the engine — `inject_forage`'s twin."""
    if not isinstance(raw_intents, list) or not player_text or scene is None:
        return raw_intents
    if "?" in player_text:
        return raw_intents
    present = {str(r.get("op", "")).lower() for r in raw_intents if isinstance(r, dict)}
    if "prospect" in present:
        return raw_intents
    if not (_PROSPECTS.search(player_text) or _GATHERS_ORE.search(player_text)):
        return raw_intents
    pc = scene.pc()
    if pc is None:
        return raw_intents
    params: dict = {}
    hours = _FOR_HOURS.search(player_text)
    if hours:
        params["hours"] = max(1, min(48, int(hours.group(1))))
    if "forage" in present:
        # The model heard "search the hillside for ore" and reached for the one
        # gathering op it knows (measured on the first live probe): the same
        # expedition, against the wrong stock list. Turned into the right one.
        out = []
        for r in raw_intents:
            if isinstance(r, dict) and str(r.get("op", "")).lower() == "forage":
                r = dict(r, op="prospect", params=dict(r.get("params") or {}, **params))
                r["params"].pop("track", None)
                r["params"].pop("biome", None)
            out.append(r)
        return out
    return list(raw_intents) + [{
        "op": "prospect", "actor": pc.ref, "params": params,
        "because": "the player said they search for ore",
    }]


# --- the doors places come in by (rules/places.py, doors two and three) ------------------

# "we set up at Marra's house", "we make this our base", "I claim the cellar as ours".
_FOUNDS = re.compile(
    r"\b(?:set\s+up|make|establish|claim|found|take)\s+(?:this\s+|it\s+)?"
    r"(?:(?:our|my|a|the)\s+)?(?:base|camp|home|headquarters|hideout|lair|safehouse|"
    r"workshop|shop|place)\b(?:\s+(?:of\s+operations))?(?:\s+(?:at|in|here\s+at)\s+(.{3,60}?))?"
    r"(?=[.,;!]|$)", re.I)
_FOUNDS_AS = re.compile(
    r"\b(?:claim|make|take)\s+(.{3,60}?)\s+as\s+(?:our|my)\s+(?:base|camp|home|"
    r"headquarters|hideout|lair|safehouse)\b", re.I)
# "I go down into the sewers", "I duck into the back alley behind the market", "I head
# out to the cave in the hills".
_VENTURE_KINDS = {
    "sewers": "sewers", "sewer": "sewers", "drains": "sewers", "undercity": "sewers",
    "cellar": "cellar", "cellars": "cellar", "vaults": "cellar", "basement": "cellar",
    "crypt": "crypt", "catacombs": "crypt", "tomb": "crypt", "tombs": "crypt",
    "rooftops": "rooftops", "roofs": "rooftops", "rooftop": "rooftops",
    "alley": "alley", "alleyway": "alley", "alleys": "alley", "back alley": "alley",
    "cave": "cave", "caves": "cave", "cavern": "cave", "caverns": "cave", "grotto": "cave",
    "mine": "mine", "mines": "mine", "mineshaft": "mine",
    "ruins": "ruins", "ruin": "ruins",
    "tower": "tower",
}
_VENTURES = re.compile(
    r"\b(?:go|head|climb|descend|duck|slip|venture|explore|enter|make\s+my\s+way|"
    r"make\s+for|search|walk)\b[^.!?]{0,30}?\b(?:the|a|an|some)?\s*"
    r"(" + "|".join(sorted(map(re.escape, _VENTURE_KINDS), key=len, reverse=True)) + r")\b"
    r"(?:\s+(?:by|behind|beside|off|near|beneath|under|below)\s+(?:the\s+)?(\w[\w' -]{2,30}?))?"
    r"(?=[.,;!]|\s+(?:and|to|for|with|in|of|on)\b|$)", re.I)


def inject_found(raw_intents, player_text: str, scene) -> list:
    """The player's declaration of a base becomes `found`, with the owner named if the
    place is somebody's ("Marra's house" → Marra, when Marra is here)."""
    if not isinstance(raw_intents, list) or not player_text or scene is None:
        return raw_intents
    if "?" in player_text:
        return raw_intents
    present = {str(r.get("op", "")).lower() for r in raw_intents if isinstance(r, dict)}
    if "found" in present:
        return raw_intents
    m = _FOUNDS_AS.search(player_text)
    where = m.group(1) if m else ""
    if not m:
        m = _FOUNDS.search(player_text)
        where = (m.group(1) or "") if m else ""
    if not m:
        return raw_intents
    pc = scene.pc()
    if pc is None:
        return raw_intents
    where = " ".join(where.split()).strip(" .,")
    name = where or "our base"
    owner = ""
    for r, a in scene.actors.items():
        if a.is_pc:
            continue
        # Any word of the name: "Marra's house" names Marra Vell by her first name.
        words = [w for w in re.findall(r"[A-Za-z][A-Za-z'-]+", str(a.name)) if len(w) >= 3]
        if any(re.search(r"\b" + re.escape(w) + r"(?:'s|’s)?\b", where, re.I) for w in words):
            owner = r
            break
    params = {"name": name[:60]}
    if owner:
        params["owner"] = owner
    return list(raw_intents) + [{
        "op": "found", "actor": pc.ref, "params": params,
        "because": "the player made this place theirs",
    }]


def inject_venture(raw_intents, player_text: str, scene) -> list:
    """Going into a kind of ground becomes `venture`, with the parent named when the
    sentence says ("the alley behind the market")."""
    if not isinstance(raw_intents, list) or not player_text or scene is None:
        return raw_intents
    if "?" in player_text:
        return raw_intents
    present = {str(r.get("op", "")).lower() for r in raw_intents if isinstance(r, dict)}
    if "venture" in present or "found" in present:
        return raw_intents
    m = _VENTURES.search(player_text)
    if not m or _MUSING.search(player_text[:m.start()]):
        return raw_intents
    pc = scene.pc()
    if pc is None:
        return raw_intents
    kind = _VENTURE_KINDS[m.group(1).lower()]
    params: dict = {"kind": kind}
    if m.group(2):
        params["parent"] = m.group(2).strip()
    # A GM-planned travel to the same idea is the same intent, and the venture makes
    # the place the travel could not find.
    out = [r for r in raw_intents
           if not (isinstance(r, dict) and str(r.get("op", "")).lower() == "travel")]
    return out + [{"op": "venture", "actor": pc.ref, "params": params,
                   "because": "the player went in"}]


def declare_leaving(raw_intents, player_text: str, scene, world=None) -> list:
    """The player is walking out: the turn must carry a `travel`, and the model must
    say to where.

    A DECLARER, not an injector — it never joins the live chain and never guesses a
    place. `inject_travel` refuses to invent a destination for a room change, and it is
    right to: a guessed place lands in the next brief as fact. But the review found
    that once a room keeps its people, nothing moved the PC for the commonest leaving
    sentence at all ("I leave the tavern" carries no ground word), and the merchant
    stayed in view. So the schema insists: `turn_schema(must_contain=("travel",))`
    makes the reply unsamplable without one, and the brief's place list makes a real
    destination the only thing it can choose. The model chooses; nothing guesses. A
    location with a single place has nowhere to go, and is left alone.
    """
    if not isinstance(raw_intents, list) or scene is None:
        return raw_intents
    if any(str((r or {}).get("op", "")).lower() == "travel" for r in raw_intents
           if isinstance(r, dict)):
        return raw_intents
    if not _WALKS_AWAY.search(str(player_text or "")):
        return raw_intents
    from rules import places as places_mod

    location = None
    if world is not None and getattr(scene, "location_id", None):
        try:
            location = world.get(scene.location_id)
        except Exception:
            location = None
    known = places_mod.for_scene(location or getattr(scene, "location_id", None),
                                 getattr(scene, "at", ""))
    if len(known) < 2:
        return raw_intents
    return list(raw_intents) + [{"op": "travel",
                                 "because": "the player is leaving; say to where"}]


_DECLARERS = (
    # Before survival: "I drink my healing potion" is a jar, not a waterskin, and
    # the survival injector stands down when a `use_item` is already in the list.
    ("jar", lambda raw, text, scene, world: declare_use_item(raw, text, scene)),
    ("survival", lambda raw, text, scene, world: inject_survival(raw, text, scene)),
    # Before travel, and only here: `inject_travel` bows out when a travel is already
    # present, so a leaving sentence that also names new ground still gets its one
    # travel from whichever declarer spoke first.
    ("leaving", lambda raw, text, scene, world: declare_leaving(raw, text, scene, world)),
    # Sale before goods, the same order the live chain runs them in — and asking them in
    # the wrong order here is what surfaced the bug: "I sell the Yarow Elixir" came back
    # as both `give` and `sell`, which is one item leaving twice.
    ("sale", lambda raw, text, scene, world: inject_sale(raw, text, scene)),
    ("goods", lambda raw, text, scene, world: inject_goods(raw, text, scene)),
    ("ability", lambda raw, text, scene, world: inject_ability(raw, text, scene)),
    ("cast", lambda raw, text, scene, world: inject_cast(raw, text, scene)),
    ("checks", lambda raw, text, scene, world: inject_checks(raw, text, scene)),
    # Speech last among the declarers, and deliberately: it never competes with any of
    # them. "I tell the smith I want to buy the axe" is a sale AND a line of dialogue,
    # and both belong in the turn — unlike the sale-or-handover pair above, where one
    # sentence must not be read twice.
    ("say", lambda raw, text, scene, world: inject_say(raw, text, scene)),
    ("travel", lambda raw, text, scene, world: inject_travel(raw, text, scene, world)),
    # After travel, and the ordering is load-bearing: "I go out to the forest to forage"
    # must append travel first, so the intent list executes the move before the forage
    # rolls its tables — the other way round forages the old ground, or errors
    # "nowhere in particular" when there is none.
    ("forage", lambda raw, text, scene, world: inject_forage(raw, text, scene)),
    ("prospect", lambda raw, text, scene, world: inject_prospect(raw, text, scene)),
    ("wait", lambda raw, text, scene, world: inject_wait(raw, text, scene)),
    ("found", lambda raw, text, scene, world: inject_found(raw, text, scene)),
    ("venture", lambda raw, text, scene, world: inject_venture(raw, text, scene)),
    ("loot", lambda raw, text, scene, world: inject_loot(raw, text, scene)),
    ("fight", lambda raw, text, scene, world: inject_fight(raw, text, scene)),
)


def inject_say(raw_intents, player_text: str, scene) -> list:
    """A line the player wrote as speech reaches the engine as a `say`.

    Detect mechanically, repair with a targeted call — the only shape of fix that has
    held here. Measured on the 2026-09-08 playtest: speech had no op among the
    forty-one, so it could only resolve to `narrate_only`; a narrate_only turn carries
    no tells; and a prose call with no tells to dress is exactly the turn that came
    back as "The moment holds". Actions in the same session worked, because every one
    of them had a door.

    Because this is a declarer, `declared_ops` finds it too, and the sampler then
    *requires* a `say` in the reply rather than hoping for one.
    """
    if not isinstance(raw_intents, list) or scene is None:
        return raw_intents
    if any(str((i or {}).get("op", "")) == "say" for i in raw_intents
           if isinstance(i, dict)):
        return raw_intents
    words = spoken(player_text)
    if not words:
        return raw_intents

    # Who they addressed, from the people actually here — never a name the engine does
    # not hold. The addressee is named OUTSIDE the speech ("I tell the clerk ..."), so
    # the redacted line is the right place to look for them.
    outside = redact_speech(player_text).lower()
    to = ""
    for ref, actor in (getattr(scene, "actors", {}) or {}).items():
        if getattr(actor, "is_pc", False):
            continue
        head = str(getattr(actor, "name", "") or "").strip().split()[-1:] or [""]
        if len(head[0]) > 2 and head[0].lower() in outside:
            to = ref
            break
    params = {"words": words}
    if to:
        params["to"] = to
    # Whether the player wrote a quotation or reported what they said. The tell reads
    # differently for each: quoting "she wants to pay for my services" back at the
    # narrator as though the character had said those words puts the player's own
    # framing, first person and all, inside somebody's mouth.
    if any(m.group(1).strip() for m in _QUOTED.finditer(str(player_text or ""))):
        params["quoted"] = True
    return list(raw_intents) + [{"op": "say", "because": "the player said it",
                                 "params": params}]


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

    # What they could reach at all. `casting.known_spells` answers it for every kind of
    # caster — the book a wizard carries, the repertoire a sorcerer knows, the whole class
    # list for a cleric or druid whose god is the book.
    #
    # This read `pc.spellbook + pc.prepared` until 2026-09-19, and both are empty for the
    # life of a cleric, so a cleric's declaration never became an intent: "I cast wall of
    # flame" fell through to prose, and the engine's own refusal — "Flame Strike is a level
    # 5 spell and Ted is a level 1 cleric" — was never reached (item 25). The vocabulary is
    # what a caster may CHOOSE from; whether they prepared it is the engine's question, and
    # the answer reaches the player as a sentence instead of a spell they did not cast.
    said = player_text.lower()
    reachable = [sp.id for level in casting.known_spells(
        pc, up_to=casting.highest_spell_level(pc)).values() for sp in level]
    reachable += [s for s in (getattr(pc, "prepared", {}) or {}) if s not in reachable]
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


_A_NUMBER = re.compile(r"\b(\d[\d,]*)\b")


def keep_the_authors_numbers(intents, wish: str):
    """The number in the wish is the number. Nobody else gets to round it.

    Measured live against gemma-4-12B: `/cheat I have 1000 gold` came back as
    `{"op": "give", "params": {"item": "gold", "count": 500}}` — half of what was
    asked for, resolved cleanly, tell and prose both confident about it.

    Runs on VALIDATED intents, after `parse_all`, and that is the load-bearing part.
    `_bounded` clamps `give.count` to 500 because "no model authors a number" — one
    authored value could otherwise mint a million gold into a hand-priced economy. So
    the model was not even the culprit here: a repair applied *before* validation was
    clamped straight back to 500 and the live probe read identically before and after
    the fix, which is how the real cause was found. The clamp is a rule about the
    MODEL, and on this one path the number is the author's own — they typed it.

    Deliberately narrow. It fires only when the wish names exactly ONE number, and it
    only ever rewrites `count` and `amount` — a wish with two numbers in it ("2 potions
    of 3 doses") cannot be resolved this way without guessing which belongs where, and
    guessing is what this exists to stop.
    """
    if not isinstance(intents, list):
        return intents
    found = _A_NUMBER.findall(str(wish or ""))
    if len(found) != 1:
        return intents
    wanted = int(found[0].replace(",", ""))
    for one in intents:
        params = getattr(one, "params", None)
        if not isinstance(params, dict):
            continue
        for key in ("count", "amount"):
            got = params.get(key)
            if isinstance(got, (int, float)) and not isinstance(got, bool) \
                    and int(got) != wanted:
                params[key] = wanted
    return intents


def split_plural_targets(raw_intents):
    """One ref per intent. A model that means several says so with several.

    Measured live on the first `/cheat I defeat all the enemies`, against
    gemma-4-12B: it answered the plural honestly with a single intent carrying
    `"to": ["c2", "c3"]`. Every op in the table takes ONE ref, `_known` did
    `ref in self.scene.actors` on the list, and `unhashable type: 'list'` reached
    Django as a 500 with a traceback.

    The engine now refuses that shape rather than dying on it, but refusing is the
    wrong answer to a request that was perfectly clear: the fan-out is what the model
    meant, it is mechanical, and it costs no second call. Detect in code, repair
    exactly what was found — the same shape as every fix in this file that held.
    """
    if not isinstance(raw_intents, list):
        return raw_intents
    out = []
    for raw in raw_intents:
        if not isinstance(raw, dict):
            out.append(raw)
            continue
        params = raw.get("params")
        many = params.get("to") if isinstance(params, dict) else None
        # `targets()` reads `target` too, and the same plural arrives there.
        if not isinstance(many, list):
            many = raw.get("target") if isinstance(raw.get("target"), list) else None
            key = "target"
        else:
            key = "to"
        refs = [r for r in (many or []) if isinstance(r, str) and r]
        if not refs:
            out.append(raw)
            continue
        for ref in refs:
            one = dict(raw)
            if key == "to":
                one["params"] = dict(params, to=ref)
            else:
                one["target"] = ref
            out.append(one)
    return out


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
                params["template"] = template_for(player_text or "", floor="thug")
            r = dict(r, params=params)
        out.append(r)
    return out


# --- The scene thread: what the player is engaged in between ops ----------------------

_THREAD_VERBS = re.compile(
    r"\b(?:I\s+|and\s+)(?:(follow|tail|shadow|track|pursue)|"
    r"(talk to|question|interrogate|speak (?:to|with)|ask|approach|"
    r"walk (?:up )?to|greet|browse|buy from|chat with)|"
    r"(watch|observe|study|keep an eye on)|"
    r"(wait for|look for|search for)|"
    # A standing piece of work: "I work the bellows", "and run the machine". The
    # ruling's own example (2026-09-18) — "if I am running a machine and a fight
    # breaks out … I will be running the machine" — and the first Continue replay,
    # where "work the bellows for the smith" set no thread at all.
    r"(work|run|operate|tend|mind|man|pump|crank|row|steer|hold|guard|haul|dig|stir|"
    r"sit at|stand at|keep working|go on working))\s+(.{3,60}?)\s*[.!?]?$", re.I)
# The Continue button's own instruction counts as a continue — measured live: the
# thread was empty, Continue arrived with no constraint at all, and a bread stall
# became a library between beats.
_THREAD_CONTINUES = re.compile(
    r"^\s*(?:i\s+)?(?:continue|keep(?:\s+(?:going|following|watching|at it))?|"
    r"carry on|press on|stay (?:on|with) (?:them|him|her|it)|"
    r"take no action\b)", re.I)
_THREAD_DOINGS = ("following", "talking to", "watching", "waiting for", "working at")
# What cannot be the subject of an engagement: a question word opening it, or the
# player's own first person anywhere in it. See `update_thread`.
_THREAD_CLAUSE = re.compile(
    r"^(?:who|whom|whose|what|which|where|when|why|how|whether|if)\b"
    r"|\b(?:i|i'm|i'll|i've|i'd|me|my|mine|myself)\b", re.I)
# Where a subject stops being somebody and starts being what was asked of them: "him
# what he carries downstream" is "him"; "the smith about the ore he uses" is "the
# smith". Measured 2026-09-18 on a sixty-turn audit, where the anchor sentence read
# "You have not let him what he carries downstream out of your sight".
_THREAD_TAIL = re.compile(r"\s+(?:what|whether|if|about|for|where|when|why|how|who|whom)\b.*$",
                          re.I)
# A bare pronoun is not a subject worth anchoring to: "him" has no content word for
# `keep_the_thread` to find, and the anchor it would write says "them" of "him".
_THREAD_PRONOUN = re.compile(r"^(?:him|her|them|it|you|me|us|this|that)$", re.I)


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
    # A fight that opened by a swing (`_ensure_encounter`, no `begin_encounter` op in
    # the list) is a fight all the same: the subject becomes the opponent, or the
    # anchor writes "you are still waiting for a challenger" into the beat that
    # squares the two off (measured, second live replay 2026-09-18).
    if getattr(scene, "in_encounter", False) and scene.thread.get("subject"):
        ops = ops | {"begin_encounter"}
    if ops & {"begin_encounter", "travel"}:
        # The fight IS the engagement now — and the person it was with survives it as
        # the opponent, so a plan's target can be checked against them and the brief
        # can name them. No subject, so the prose anchor and the brief stay silent
        # mid-fight. Measured 2026-09-18: clearing the thread here lost the challenger
        # the moment the fight began, and the first attack went to the wrong man.
        ref = scene.thread.get("ref") if "begin_encounter" in ops else None
        # The standing action survives the fight as a fact for Continue: "if I am
        # running a machine and a fight breaks out … I will be running the machine"
        # (the ruling, 2026-09-18). Not as the subject — the anchor and the brief stay
        # silent mid-fight — but as `standing`, which `standing_action` reads.
        held = {k: scene.thread[k] for k in ("doing", "subject") if scene.thread.get(k)}
        if scene.thread.get("standing") and not held:
            held = dict(scene.thread["standing"])
        new = {"opponent": ref} if ref and ref in scene.actors else {}
        if held and "begin_encounter" in ops:
            new["standing"] = held
        scene.thread = new
        return
    text = " ".join(str(player_text or "").split())
    # The place used to be read out of the player's own sentence here and written to
    # `thread["where"]` — a second writer of "where the party is" beside the engine's
    # place, and `scene_brief` printed both into one prompt, so a single brief could
    # assert two rooms (docs/intent-protocol.md §8: no field has two writers). The
    # writes are gone; the engine's `here()` is the one source and the brief is handed
    # it. `_THREAD_WHERE` survives for its other job: trimming the trailing place
    # phrase off the subject, so "I follow them into the market" engages with "them"
    # and not with "them into the market".
    m = _THREAD_VERBS.search(text)
    if m:
        which = next(i for i in range(1, 6) if m.group(i))
        subject = m.group(6).strip()
        sw = _THREAD_WHERE.search(subject)
        if sw:
            subject = subject[:sw.start()].strip() or subject
        # A subject has to be somebody or something, not a clause. Measured on the
        # 2026-09-17 sixty-turn baseline: "I ask who I should speak to about work
        # outside the walls" set the thread to *who I should speak to about work
        # outside the walls*, the anchor sentence then placed that in the narration,
        # and the player's own "I" shipped as the narrator's — one of the run's two
        # faults, caused by us. A question about whom to talk to engages nobody yet;
        # the existing thread, if any, stands.
        if _THREAD_CLAUSE.search(subject):
            return
        # And the somebody stops where the question begins: "him what he carries
        # downstream" is an engagement with him. If nothing but a pronoun is left, the
        # engagement already on the books is the one being continued.
        subject = _THREAD_TAIL.sub("", subject).strip().rstrip(",") or subject
        if _THREAD_PRONOUN.match(subject) and scene.thread:
            scene.thread["age"] = 0
            return
        scene.thread = {"doing": _THREAD_DOINGS[which - 1],
                        "subject": subject, "age": 0}
        # A subject that names somebody on the board is bound to them now; a role
        # nobody holds yet ("a challenger") waits for `promote_cast` to bind it.
        bind_thread(scene)
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

    if scene.thread:
        if _THREAD_CONTINUES.match(text):
            scene.thread["age"] = 0
            return
        scene.thread["age"] = int(scene.thread.get("age", 0)) + 1
        if scene.thread["age"] > 6:
            scene.thread = {}


def standing_action(scene) -> str:
    """The player's standing action as a sentence of fact for a Continue beat, or "".

    From the thread's own doing and subject ("waiting for a challenger", "talking to
    the woman"), or the `standing` a fight kept. Continue means this holds — the ruling
    of 2026-09-18 — and the world moves a beat around it."""
    t = getattr(scene, "thread", None) or {}
    doing = str(t.get("doing") or (t.get("standing") or {}).get("doing") or "").strip()
    subject = str(t.get("subject") or (t.get("standing") or {}).get("subject") or "").strip()
    if not subject:
        return ""
    return (f"THE PLAYER'S STANDING ACTION (fact): they go on {doing or 'engaged with'} "
            f"{subject}, exactly as before — do not drop it, do not change it, do not add "
            f"an action they did not take. THE WORLD MOVES ONE BEAT: the people here go on "
            f"with what they were doing and the next thing happens — an answer, a step, a "
            f"blow, an arrival, a consequence. Nobody merely waits.")


def thread_brief(scene, where: str = "") -> str:
    """The thread as a sentence of fact for the prose call, or "".

    `where` is the engine's own place name, handed down by the caller that has an
    engine — the brief cannot derive it, and it must never again be read out of the
    thread. Asserted only as what the engine knows ("you are ALREADY at"), never as
    where the subject is, because the subject is a free-text phrase and not a ref.
    """
    t = getattr(scene, "thread", None) or {}
    if not t.get("subject"):
        return ""
    where = str(where or "").strip()
    placed = (f" You are ALREADY at {where}; nobody arrives at, enters or heads "
              f"toward {where} — they are there now." if where else "")
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

# How many bodies a beat's prose may put on the board. The cap is about the PANEL and the
# board — four promoted civilians standing is a scene, twelve is a flood — and it is not a
# claim about the fiction: the ledger keeps the number the prose said (`_SAID_CAP`), so
# `cast_brief` tells the model twelve raiders when twelve arrived. Item 33 is what resolves
# the tension properly: twelve raiders are one unit of twelve, not twelve actors.
_PROMOTED_CAP = 4
# What a ledger entry may say arrived. High, because it is a record and not a roster; a
# number past this is prose being rhetorical ("a thousand of them"), not a head-count.
_SAID_CAP = 60


_CAST_ROLES = ("servants?|apprentices?|"
               "merchants?|traders?|vendors?|stall ?keepers?|shopkeepers?|"
               "guards?|guardsmen|guardsman|watchmen|watchman|watchwoman|"
               "strangers?|priests?|priestess(?:es)?|labou?rers?|beggars?|"
               "nobles?|clansmen|clansman|clanswoman|artisans?|soldiers?|"
               "sailors?|innkeepers?|barkeeps?|bartenders?|thugs?|urchins?|"
               "elders?|farmers?|fishermen|fisherman|smiths?|scribes?|"
               "porters?|drovers?|peddlers?|fighters?|warriors?|mercenaries|"
               "mercenary|brawlers?|toughs?|swordsmen|swordsman|duellists?|"
               # The words a beat uses for the man who squares off: measured on the
               # group-2 replay (2026-09-18), "the brute" was never booked, so the
               # sunder went to a named resident who happened to be standing there.
               "brutes?|bruisers?|ruffians?|challengers?|veterans?|hulks?|giants?|"
               "drunks?|dockhands?|sailors?|"
               # The words prose uses for armed strangers arriving, none of which were
               # here. Measured 2026-09-19: "a band of twelve raiders" booked NOTHING —
               # no ledger entry, no actor, not even a mention in `cast_brief` — while
               # the bestiary has shipped a Raider at 29 hp all along (item 30). And
               # `figures?`, because the reported beat's own words were "a line of
               # figures silhouetted against the gray morning light", which matched
               # nothing, so there was never a booked word for the next beat to
               # contradict.
               "raiders?|brigands?|bandits?|reavers?|marauders?|outlaws?|looters?|"
               "sellswords?|cutthroats?|deserters?|pirates?|bravos?|riders?|figures?|"
               "men|man|women|woman|boys?|girls?|people|folk")
# A crowd is people. Counted where the prose counts them, capped by the same
# reading the fight injector uses for an uncounted group.
_CAST_GROUP = re.compile(
    r"\b(?:group|band|gang|pack|knot|circle|cluster|party|column|line|row|score|"
    r"pair|trio|handful)\s+of\s+(?:\w+\s+){0,2}(?:" + _CAST_ROLES + r")\b",
    re.I)
# Any-case adjectives, in any order: "an elderly Kelvaxian vendor" has the
# lowercase one first and the demonym second, and an ordered pattern missed it.
#
# And the description that comes AFTER the role, when there is one: "the man in the
# leather apron", "a woman with a scarred face". Measured 2026-09-18 (the ring fight):
# the man who drew on the player was introduced as "the man in the leather apron",
# this pattern kept "man", the ledger already held "desperate man", and the head-word
# dedup below skipped him — so the man who swung first was never on the board, "him"
# resolved to a bystander, and a boy died. One optional article-led phrase: an optional
# participle or material or colour, then one noun, so "in the doorway watches" stops
# at the doorway and never books the verb.
# The words that can only be a QUALITY of the thing, never the thing. Named as a set as
# well as in the pattern, because the pattern can stop on one of them: "a man in a heavy,
# grease-stained leather apron" has a comma where the pattern wants the noun, so the tail
# came out " in a heavy" and the ledger booked a person called **man in a heavy** (measured
# live 2026-09-19). A description that ends on an adjective is not a description; the tail
# is dropped and the man is a man.
_TAIL_ADJECTIVES = ("leather", "iron", "steel", "red", "black", "grey", "gray", "white",
                    "blue", "green", "brown", "dark", "heavy", "ragged", "torn", "fine",
                    "plain", "long", "short", "broad")
# The adjective slot before the noun. It was a closed list plus -ed/-en, and the list is
# what decided whether a description survived whole: "a porter with a scarred forearm"
# kept its forearm because "scarred" ends in -ed, and "a man with a distinctive satchel"
# was booked as **man with a distinctive** because "distinctive" matched nothing. Measured
# live 2026-09-20, where one man collected three cards partly on the strength of it.
#
# Morphology rather than more vocabulary, for the reason CLAUDE.md gives about chasing
# words: the endings below are adjective-forming, and the slot stays NARROW on purpose —
# widening it to any word lets a verb in, because "a man with a sword lunges" would read
# "sword" as the adjective and "lunges" as the noun.
_ADJECTIVE_ENDINGS = r"[a-z]+(?:ed|en|ive|ous|ful|less|ish|ing)"
_CAST_TAIL = (r"(\s+(?:in|with)\s+(?:a|an|the)\s+"
              r"(?:(?:" + _ADJECTIVE_ENDINGS + r"|" + "|".join(_TAIL_ADJECTIVES) + r")"
              r"\s+)?[a-z]+)?")
# `(?!-)`: a role word with a hyphen after it is the first half of a compound and not
# a person — "the elder-quarter" is a quarter, "the guard-house" a house. Measured
# 2026-09-24: an "elder" was booked and stood in the lane out of exactly that phrase.
_CAST_INTRO = re.compile(
    r"\b(?:a|an|one|the)\s+((?:[A-Za-z'-]+\s+){0,3}"
    r"(?:" + _CAST_ROLES + r"))\b(?!-)" + _CAST_TAIL, re.I)
_ROLE_WORD = re.compile(r"\b(?:" + _CAST_ROLES + r")\b", re.I)


def _role_head(phrase: str) -> str:
    """The role word of a cast phrase — "man" for "man in the leather apron", the last
    word when no role word is in it ("Drenn Ironvale" → "ironvale")."""
    words = str(phrase or "").split()
    if not words:
        return ""
    roles = [w.lower() for w in words if _ROLE_WORD.fullmatch(w)]
    return roles[0] if roles else words[-1].lower()
_CAST_MAX = 8
# Words that cannot be part of a person's description: what separates "a tall hooded
# stranger" from "the weaver is a man".
_NOT_AN_ADJECTIVE = frozenset({
    "is", "are", "was", "were", "be", "been", "being", "a", "an", "the", "and", "or",
    "but", "of", "with", "other", "right", "wrong", "same", "some", "any", "no", "not",
    "this", "that", "these", "those", "his", "her", "their", "its", "my", "your", "our",
    "in", "on", "at", "to", "for", "from", "as", "by", "who", "whom", "which", "whose",
    "has", "have", "had", "than", "then", "there", "here", "where", "when", "if", "so",
    "very", "only", "just", "even", "still", "also", "too", "all", "both", "each",
    "every", "few", "many", "most", "several", "such", "what", "how",
})
# Heads that name a crowd, not a person to speak to.
# Words that describe a person without being one. Noting these as cast is what turns a
# passing phrase into a fixture: `cast_brief` then tells the model, every turn for the
# next twelve, that this person is present and must be kept consistent — so it keeps
# writing them in, and eventually writes them into things that are not people at all.
#
# Reported at the table, 2026-09-08, with a screenshot: "As for where the shadows do not
# reach, I speak of the Old the stranger cellar." A place name with a person pasted into
# it, article and all. Traced: the model said "the stranger" once, `note_cast` filed a
# person called "stranger", and the brief asserted them for twelve turns.
#
# "stranger" got into the model's mouth from our own examples — it is what
# `prompts.fill_enemy` renders {Current Enemy} as when there is no enemy, and the
# wall-climbing example used that token for a figure in a doorway who was never an enemy
# at all. That use is gone. This is the other half: even said once, it is not a person.
#
# Kept to words that cannot be anybody in particular. "man" and "woman" are NOT here on
# purpose — this game's scenes are full of "the man at the far bank" who is a real
# person the player will meet again.
_NOBODY_IN_PARTICULAR = frozenset({"people", "folk", "men", "women", "others"})

# Matched against the WHOLE phrase, not its last word: "a tall hooded stranger" is
# somebody, a bare "someone" is not anybody.
#
# "stranger" is deliberately NOT here, and the reason is an older incident pulling the
# other way. `test_a_noted_person_stands_in_the_scene` records it: a bare stranger in
# the prose, the player wanting to address him, and the engine not holding anyone — "the
# ledger knew about him and the engine did not, so he could not be attacked, addressed,
# or found again". Booking a bare stranger is that fix working.
#
# Which leaves the 2026-09-08 report — "the Old the stranger cellar", the word pasted
# into a place name, constantly — to be fixed at its source instead, and its source was
# ours: `prompts.fill_enemy` renders {Current Enemy} as "the stranger" when there is no
# enemy, and the wall-climbing example spent that token on a figure in a doorway who was
# never an enemy. Every out-of-combat turn showed the model the phrase twice. That is
# gone; see tests/test_the_stranger.py.
_A_WORD_NOT_A_PERSON = frozenset({"someone", "somebody", "anyone", "nobody"})

# Where a noted person stands, in the engine's own three words. Reported at the
# table, 2026-09-06, with the map open: a servant "beside you", a hooded man "at the
# far end of the corridor", a merchant and two guards — all five promoted to the same
# zone and laid out as one column three squares off, "not how the people should be
# lined up according to the prose". The prose says where they are in the same
# handful of phrases every time; those phrases are read, and the ledger carries the
# zone the engine places by (`SQUARES_BY_ZONE`: engaged 1, near 3, far 8 — 13th
# Age's engaged / nearby / far away, which the engine already speaks). Looked for in
# the words around the person, before and after, because English puts the place on
# either side: "beside you a woman", "a woman beside you".
_ZONE_CUES = (
    ("engaged", re.compile(
        r"\b(?:beside|next to|alongside|in front of|before|facing|against|over|"
        r"right beside|up beside|close beside) you\b"
        r"|\bat your (?:side|elbow|shoulder|table)\b"
        r"|\bsharing (?:the|your) (?:step|table|bench|doorway|wall)\b"
        r"|\bwithin (?:arm's |arm’s |an arm's )?reach\b"
        r"|\bclose enough to touch\b"
        r"|\b(?:grabs|grips|pins|seizes|shoves|catches|grapples) (?:you|your|at you)\b"
        r"|\bleans in(?:to)? (?:close|toward you|towards you)\b", re.I)),
    ("far", re.compile(
        r"\b(?:at|from|on|down|across|near|by|in|through) the (?:far|other|opposite) "
        r"(?:end|side|wall|corner|bank|door)\b"
        r"|\bacross the (?:room|hall|yard|square|street|lane|market|water|courtyard|"
        r"corridor|floor|bar|counter)\b"
        r"|\b(?:in|at|from|through) the (?:doorway|door|gate|gateway|entrance|"
        r"threshold|window|archway|shadows beyond|gloom)\b"
        r"|\b(?:down|up|along) the (?:street|lane|road|corridor|hall|passage|row)\b"
        r"|\bat the (?:back|rear|head|front) of the \w+\b"
        r"|\bsome (?:way|distance) (?:off|away|back)\b"
        r"|\b(?:a|several|some|twenty|thirty|forty|fifty) (?:paces|yards|feet) "
        r"(?:away|off|back|distant)\b",
        re.I)),
)
_ZONE_WINDOW = 90


def zone_of_mention(beat: str, start: int, end: int) -> str:
    """The zone the prose puts a person in, from the words around their mention.

    Engaged wins over far when both appear, because a person touching you is not
    also across the room; nothing said means `near`, the engine's own default.
    """
    lo, hi = max(0, start - _ZONE_WINDOW), min(len(beat), end + _ZONE_WINDOW)
    # The window stops at a sentence end on each side: "He stands at the far end.
    # Beside you, the servant …" must not hand the servant the far end.
    before = beat[lo:start]
    cut = max(before.rfind(". "), before.rfind("! "), before.rfind("? "))
    if cut >= 0:
        before = before[cut + 2:]
    after = beat[end:hi]
    cut = min([i for i in (after.find(". "), after.find("! "), after.find("? ")) if i >= 0],
              default=-1)
    if cut >= 0:
        after = after[:cut + 1]
    around = before + " " + beat[start:end] + " " + after
    for zone, rx in _ZONE_CUES:
        if rx.search(around):
            return zone
    return "near"


def _refers_back(who: str, head: str, this_beat: set[str],
                 booked_by_head: dict[str, list[str]]) -> bool:
    """Whether a DEFINITE mention is somebody the ledger already holds (item 36).

    Heim's familiarity condition is the account: an indefinite noun phrase creates a new
    file card, a definite refers to one that exists. `scene.cast` is that ledger, so the
    article is the evidence the head-word dedup never read — which is why one man could
    collect three cards.

    Three grounds, each measured rather than supposed (live, 2026-09-20):

    * the role word was booked by THIS beat — "shouting at a merchant … divided by the
      shouting merchant", the turn item 36 was reported from;
    * the ledger holds that role BARE — "merchant" booked, then "the merchant with the
      satchel": a bare card is a person nobody described yet, and a definite describing
      them is the description arriving, not a second body;
    * the description shares a word with a booked one of the same role — "a porter with a
      scarred forearm" then "the porter with the scarred forearm".

    And the case it must refuse, which is the whole reason this is not just "same head":
    "desperate man" booked, then "the man in the leather apron". Same role, no shared
    description, nothing bare — two men, and skipping the second is exactly how the man
    who swung first at the player was never put on the board (2026-09-18, item 16b).
    """
    booked = booked_by_head.get(head) or []
    if not booked:
        return False
    if head in this_beat:
        return True
    if any(b.strip() == head for b in booked):
        return True
    # The role word is dropped from both sides along with the stop words: it is what
    # they already have in common, and leaving it in would make every pair of phrases
    # sharing a role "the same person" — which is the dedup this replaces.
    def _describing(phrase: str) -> set[str]:
        return {w for w in phrase.lower().split()
                if w != head and w not in _NOT_AN_ADJECTIVE}

    mine = _describing(who)
    if not mine:
        return False
    return any(mine & _describing(b) for b in booked)


def note_cast(scene, gm_beat: str, turn: int = 0) -> list[str]:
    """People the narration introduced become ledger entries, mechanically.

    The haunted-house class of bug in its second form: prose invents a Kelvaxian
    merchant, the player answers him, and two beats later he has evaporated
    because he lived nowhere but the model's short memory. Role-phrases in a GM
    beat are read into `scene.cast`; the brief feeds them back as fact. Capped,
    deduplicated on the role's head word, and never containing anyone who is
    already a real actor.

    **Narration only.** Found live 2026-09-19 during group 7's check (item 34): the beat
    said, of the woman the player was asking her name, *"Most just call me the stranger"* —
    and a new person called **stranger** was booked and promoted onto the board, out of her
    own words about herself. What a character SAYS is not what the room contains: a person
    talked about is not a person present, and even a genuine announcement ("'Three raiders
    are coming!' he shouts") is a warning about people who have not arrived yet. The prose
    puts people in the room; dialogue does not. The blanked span keeps its length, so every
    offset below — the group spans, `zone_of_mention` — still lines up with the original.
    """
    if scene is None or not gm_beat:
        return []
    gm_beat = narration_quotes_blanked(gm_beat)
    real = " ".join(a.name.lower() for a in scene.actors.values())
    real_names = {a.name.lower() for a in scene.actors.values()}
    heads = {str(e.get("who", "")).split()[-1].lower() for e in scene.cast}
    # The whole phrases already booked, beside their heads: the head answers "is
    # this a bare repeat", the phrase answers "is this the same description".
    phrases = {str(e.get("who", "")).lower() for e in scene.cast}
    # A ledger entry's head is its ROLE word, which is not always its last word now
    # that a description can follow it ("man in the leather apron" → "man").
    heads |= {_role_head(str(e.get("who", ""))) for e in scene.cast}
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
        # The ledger records what the prose said — twelve is twelve. The cap belongs to
        # promotion, where bodies are made, not to the record of what arrived: clamping
        # here meant nothing downstream could ever know the fiction said twelve, and
        # `cast_brief` then told the model four (item 30). Item 33's unit reads this number.
        scene.cast.append({"who": role, "turn": int(turn),
                           "count": max(1, min(n, _SAID_CAP)),
                           "zone": zone_of_mention(gm_beat, *m.span())})
        added.append(role)
    # The role words THIS beat has booked, for the definite-reference rule below. Seeded
    # from the group loop above, which books in the same beat: a band booked as "twelve
    # raiders" is who "the raiders" means two sentences later.
    this_beat = {_role_head(w) for w in added}
    # And every phrase already on the ledger, filed under its role word, so a definite
    # can be compared with the people who share it.
    booked_by_head: dict[str, list[str]] = {}
    for e in scene.cast:
        booked_by_head.setdefault(_role_head(str(e.get("who", ""))), []).append(
            str(e.get("who", "")).lower())
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
        # The filler between the article and the role is up to three arbitrary words,
        # and arbitrary is what they were. Booked at the table, 2026-09-06: "is a man",
        # "other a woman", "right people", "Weaver's the stranger". A filler that is a
        # verb, an article, a pronoun or a possessive is not an adjective, so the
        # phrase is cut back to the adjectives after the last such word; a possessive
        # means a place ("the Weaver's …") and a generic plural is nobody in particular.
        words = who.split()
        keep = 0
        for i, w in enumerate(words[:-1]):
            low = w.lower()
            if low in _NOT_AN_ADJECTIVE:
                keep = i + 1
            if low.endswith(("'s", "’s")):
                keep = None
                break
        if keep is None:
            continue
        who = " ".join(words[keep:])
        head = who.split()[-1].lower()
        if head in _NOBODY_IN_PARTICULAR:
            continue
        if who.strip().lower() in _A_WORD_NOT_A_PERSON:
            continue
        # The description after the role rides along — "man in the leather apron" —
        # so two men with different descriptions are two men. The head stays the
        # role word: it is what the dedup and the fight cues read.
        tail = " ".join((m.group(2) or "").split())
        # A description cut off mid-phrase is not a description. Measured live 2026-09-19:
        # "a man in a heavy, grease-stained leather apron" booked a person called **man in
        # a heavy**, because the comma stood where the pattern wanted the noun. The comma is
        # the signal and the word is not: "the man in the scarred leather" ends on the same
        # word list and is a whole description, which the first version of this cut.
        if tail and tail.split()[-1].lower() in _TAIL_ADJECTIVES \
                and gm_beat[m.end():m.end() + 1] in (",", "-"):
            tail = ""
        if tail:
            who = f"{who} {tail}"
        # Dedup on the head word ONLY for a bare repeat. "the man" after "desperate
        # man" is the same man mentioned again; "the man in the leather apron" is a
        # second person, and skipping him is how the man who swung first at the
        # player was never on the board (2026-09-18). An exact repeat of a phrase is
        # always the same person, whatever the description.
        if who.lower() in phrases or who.lower() in real_names:
            continue
        if (head in heads or head in real) and len(who.split()) == 1:
            continue
        # One person, booked twice under two descriptions (item 36). Measured live
        # 2026-09-19: the ledger came back holding **merchant** and **shouting
        # merchant**, both at turn 82, out of one beat that wrote "he is currently
        # shouting at A merchant" and then "his attention is divided by THE shouting
        # merchant". The head-word dedup lets a second description through on purpose —
        # that is how the man who swung first got onto the board (2026-09-18) — so it
        # could not tell these apart from the words alone.
        #
        # The article can. Heim's novelty/familiarity condition is the standing account
        # and its own metaphor is this very ledger: an indefinite noun phrase creates a
        # new file card, a definite refers to one that exists ("File Change Semantics
        # and the Familiarity Theory of Definiteness", 1983). So an indefinite always
        # books, and a definite whose role word THIS BEAT has already booked is the same
        # person mentioned again.
        #
        # Held to the one beat deliberately, and the 2026-09-18 fix is why: "desperate
        # man" booked a turn earlier and "the man in the leather apron" now is two men,
        # and skipping the second is the exact defect that kept him off the board. Heim
        # allows a novel definite to be accommodated, which across beats is the common
        # case — a definite naming a head nobody booked still books here, unchanged.
        if m.group(0).split()[0].lower() == "the" \
                and _refers_back(who, head, this_beat, booked_by_head):
            continue
        this_beat.add(head)
        booked_by_head.setdefault(head, []).append(who.lower())
        heads.add(head)
        phrases.add(who.lower())
        scene.cast.append({"who": who, "turn": int(turn),
                           "zone": zone_of_mention(gm_beat, *m.span())})
        added.append(who)
    # Old entries rot out: a bare "stranger" noted a dozen turns back fed a whole
    # invented library scene when a Continue arrived with nothing else to hold —
    # the ledger is the present cast, not a census of everyone ever mentioned.
    scene.cast = [e for e in scene.cast
                  if int(turn) - int(e.get("turn", 0)) <= 12]
    if len(scene.cast) > _CAST_MAX:
        scene.cast = scene.cast[-_CAST_MAX:]
    return added


# The armed-stranger words, as one family. Inside a family a beat may not rename anybody:
# soldiers do not become raiders between one paragraph and the next, which is what the
# player reported on 2026-09-19 ("they were initially described as soldiers and then became
# raiders"). Across families it is left alone — a merchant who turns out to be a thug is a
# turn of the story, not a slip of the pen.
_ARMED_FAMILY = frozenset({
    "soldier", "soldiers", "raider", "raiders", "brigand", "brigands", "bandit", "bandits",
    "reaver", "reavers", "marauder", "marauders", "outlaw", "outlaws", "looter", "looters",
    "mercenary", "mercenaries", "sellsword", "sellswords", "warrior", "warriors",
    "fighter", "fighters", "swordsman", "swordsmen", "guard", "guards", "guardsman",
    "guardsmen", "watchman", "watchmen", "thug", "thugs", "brute", "brutes", "ruffian",
    "ruffians", "tough", "toughs", "bruiser", "bruisers", "pirate", "pirates",
    "cutthroat", "cutthroats", "deserter", "deserters", "bravo", "bravos", "rider",
    "riders", "figure", "figures",
})


def hold_the_booked_word(scene, text: str) -> tuple[str, list[str]]:
    """A band the ledger booked keeps the word it was booked under.

    The drift was held by nothing at all: one sentence of prompt text in `cast_brief`
    ("keep them consistent, do not re-introduce them") and no mechanical check anywhere.
    Measured on the reported turn — the scene opened on "the soldiers ahead of you" and by
    the next beat they were raiders, with nothing comparing the second word to the first.

    Narrow on purpose. It fires only when the ledger holds exactly ONE armed group, the
    beat uses a DIFFERENT armed word, and that word is booked nowhere — so a beat naming
    both soldiers and raiders is describing two bands and is left alone, and so is a beat
    introducing the first of anything. Speech is untouched: a character may call them
    whatever they like.
    """
    entries = [e for e in (getattr(scene, "cast", None) or [])
               if _role_head(str(e.get("who", ""))) in _ARMED_FAMILY]
    if not text or len(entries) != 1:
        return text, []
    booked = _role_head(str(entries[0].get("who", "")))
    booked_all = {_role_head(str(e.get("who", ""))) for e in (getattr(scene, "cast", None) or [])}
    booked_all |= {str(a.name).lower() for a in (getattr(scene, "actors", {}) or {}).values()}
    swapped: list[str] = []
    # Narration only, never a line of dialogue — the same split `creature_nouns_for_pc`
    # uses, and for the same reason: his words are his.
    parts = re.split(r'("[^"]*"|“[^”]*”|\'[^\']*\')', text)
    out = []
    for i, part in enumerate(parts):
        if i % 2:
            out.append(part)
            continue
        for word in sorted(_ARMED_FAMILY, key=len, reverse=True):
            if word == booked or word in booked_all:
                continue
            if not re.search(rf"\b{word}\b", part, re.I):
                continue
            # Plural for plural, singular for singular: the booked word carries its own
            # number, and "the raiders" must not become "the soldier".
            replacement = booked
            if word.endswith("s") and not booked.endswith("s"):
                replacement = booked + "s"
            elif not word.endswith("s") and booked.endswith("s"):
                replacement = booked[:-1]
            part = re.sub(rf"\b{word}\b", replacement, part, flags=re.I)
            swapped.append(f"{word} -> {replacement}")
        out.append(part)
    return "".join(out), swapped


def cast_brief(scene) -> str:
    """The ledger as a line of fact for the prose call, or ""."""
    entries = getattr(scene, "cast", None) or []
    if not entries:
        return ""
    # With the number the prose said, which the ledger holds again since item 30: a band of
    # twelve is twelve in the fiction whatever the board can hold, and the model was being
    # told four. The word is the word they were booked under — `hold_the_booked_word`
    # repairs a beat that renames them, and this is what it repairs to.
    bits = []
    for e in entries:
        who = str(e.get("who") or "")
        if not who:
            continue
        n = int(e.get("count", 1) or 1)
        bits.append(f"{who} ×{n}" if n > 1 else who)
    return (f"ALSO PRESENT, introduced earlier (fact, keep them consistent, keep the "
            f"same word for them, do not re-introduce them): {'; '.join(bits)}.")


# A bystander the prose has just put into the fight. The verbs are the ones a beat
# uses when somebody stops watching: read against each bystander's own name, within
# the sentence, so "the merchant flinches as the guard draws" brings in the guard
# and not the merchant.
_JOINS = (r"(?:draws|lunges|charges|attacks|swings|strikes|comes at you|steps in|"
          r"steps between|joins (?:the )?(?:fight|fray|brawl)|throws (?:him|her|them)self|"
          r"grabs (?:you|your)|seizes (?:you|your)|closes (?:in|with you)|"
          r"levels (?:a|his|her|their)|raises (?:a|his|her|their) (?:\w+ )?(?:club|blade|"
          r"sword|staff|spear|cudgel|fist|fists)|wades in|rushes (?:you|in|forward))")


# The words that say WHOSE side a joiner takes. On yours: they act against a foe by
# name, or for you in as many words. On theirs: they act against you. With nothing
# said, a person who stops watching to draw a blade is presumed against you — the
# fight is the player's, and a stranger's help is the surprise, not the rule.
_FOR_YOU = re.compile(
    r"\b(?:to your (?:aid|side|defence|defense|rescue)|at your side|beside you|"
    r"between you and|in front of you|(?:defends?|covers?|shields?|protects?|helps?) you|"
    r"on your side|with you|for you|alongside you|takes your (?:side|part))\b", re.I)
_AGAINST_YOU = re.compile(
    r"\b(?:at|on|toward|towards|for|into) you\b"
    r"|\byour (?:arm|throat|shoulder|wrist|face|chest|neck|legs?)\b", re.I)


def _side_taken(sentence: str, foes: list[str]) -> str:
    """Which side a sentence puts its joiner on: "pc" or "them"."""
    against_you = _AGAINST_YOU.search(sentence)
    for_you = _FOR_YOU.search(sentence)
    at_a_foe = any(
        re.search(r"\b(?:at|on|toward|towards|into|against|with)\s+(?:the\s+)?"
                  r"(?:\w+\s+){0,2}" + re.escape(f) + r"s?\b", sentence, re.I)
        for f in foes if f)
    if for_you or (at_a_foe and not against_you):
        return "pc"
    return "them"


def joiners(scene, gm_beat: str) -> list[tuple[str, str]]:
    """(ref, side) for each bystander this beat says has joined the fight, or [].

    "add allies joining on my side too" (2026-09-06): the side is read from the
    sentence — a guard who "steps between you and the thug" or "swings at the thug"
    joins on the player's side; one who "comes at you" joins against them.
    """
    if scene is None or not getattr(scene, "in_encounter", False) or not gm_beat:
        return []
    sides = getattr(scene, "sides", None) or {}
    foe_heads = [(str(scene.actors[r].name).split() or [""])[-1]
                 for s, refs in sides.items() if s not in ("pc", "you")
                 for r in refs if r in scene.actors]
    foe_heads = [h[:-1] if h.endswith("s") and len(h) > 3 else h for h in foe_heads]
    out = []
    for ref, actor in scene.actors.items():
        if actor.is_pc or actor.is_down or any(ref in refs for refs in sides.values()):
            continue
        head = (str(actor.name).split() or [""])[-1]
        if len(head) < 3:
            continue
        # Their name's head word — "guard" for "the hooded guard" — then the verb
        # within three words, so the verb is theirs: "the merchant flinches as the
        # hooded guard draws" is the guard's draw, four words from the merchant.
        rx = re.compile(r"\b" + re.escape(head) + r"s?\b(?:\s+\w+){0,3}?\s+" + _JOINS + r"\b",
                        re.I)
        for sentence in re.split(r"(?<=[.!?])\s+", gm_beat):
            if rx.search(sentence):
                out.append((ref, _side_taken(sentence, foe_heads)))
                break
    return out


def clear_cast(scene) -> None:
    """The ledger of prose-people the narrator introduced HERE is emptied.

    This used to depart the promoted ones too, because a room had no way to keep its
    people: walking away was the only door out of the scene. A room keeps them now —
    they are contained by the place, the party's view stops holding them, and the
    engine's own mover empties this ledger when the PC changes place. What is left of
    this door is the regex path's residual: the player said they were leaving and the
    model proposed no travel, so at least the ledger does not go on asserting "ALSO
    PRESENT" about people the player has walked away from in prose. Departs nobody.
    """
    if scene is None:
        return
    scene.cast = []


# --- Heat: what the bystanders just saw -----------------------------------------------

# The notable acts short of a killing that a crowd cannot fail to see. Reported with a
# screenshot, 2026-09-18: a longsword put through a merchant's crates in the open, and
# "the stranger on the step watches the arc of your sword, his face unmoving, and the
# crowd at the end of the street remains silent". Heat used to be written for a kill
# and nothing else, so nothing carried "he just attacked somebody's goods" into the
# next beat, and the model — which continues what is in front of it — wrote the crowd
# as it had been: watching.
_HEAT_PROPERTY = re.compile(
    r"\b(?:strike|strikes|hit|hits|smash|smashes|kick|kicks|hack|hacks|break|breaks|"
    r"shatter|shatters|implode|implodes|topple|topples|burn|burns|cut|cuts|slash|"
    r"slashes|stab|stabs|overturn|overturns|knock|knocks|split|splits|destroy|destroys|"
    r"swing|swings|swung|bring|brings|drive|drives|slam|slams|hurl|hurls)"
    r"\b[^.!?]{0,40}?\b(?:crates?|box(?:es)?|barrels?|stalls?|carts?|wagons?|doors?|"
    r"tables?|walls?|signs?|windows?|shutters?|posts?|beams?|ropes?|sacks?|goods|wares|"
    r"awnings?|benches?|counters?|shelves|shelf|jars?|pots?)\b", re.I)
_HEAT_BRANDISH = re.compile(
    r"\b(?:draw|draws|unsheathe|unsheathes|brandish|brandishes|level|levels)\s+"
    r"(?:my\s+|the\s+)?(?:sword|blade|longsword|axe|dagger|knife|weapon|spear|mace|"
    r"hammer|bow|crossbow)\b"
    r"|\bswing\w*\s+(?:my\s+|the\s+)?(?:sword|blade|longsword|axe|hammer|weapon|mace)\b",
    re.I)
_HEAT_SHOUT = re.compile(r"\b(?:shout|shouts|scream|screams|yell|yells|bellow|bellows|"
                         r"roar|roars|howl|howls)\b", re.I)
HEAT_TURNS = 8


def note_heat(scene, outcomes, player_text: str = "") -> None:
    """What the bystanders just saw is a fact the next beat must carry.

    Measured live: the player murdered a merchant in the middle of the market and
    the very next stall-keeper chatted amiably about silk. Witnesses were
    everywhere — the cast ledger held them — and nothing carried the event
    forward. A kill with the ledger non-empty (or any living non-PC watching)
    writes scene.heat; the brief states it until it cools.

    And since 2026-09-18, the acts short of a kill that a crowd sees just as well:
    an attack that landed on somebody standing here, a weapon put through somebody's
    goods, a blade drawn in the open, a shout. Each carries its `kind`, because the
    reaction the brief asks for differs — nobody runs for the watch over a kicked
    barrel, and nobody objects politely to a killing.
    """
    if scene is None:
        return
    heat = dict(scene.heat or {})
    if heat:
        heat["age"] = int(heat.get("age", 0)) + 1
        scene.heat = {} if heat["age"] > HEAT_TURNS else heat
    watchers = bool(scene.cast) or any(
        not a.is_pc and not a.is_down for a in scene.actors.values())
    if not watchers:
        return
    killed, struck = [], []
    for o in outcomes or []:
        for e in getattr(o, "effects", None) or []:
            if not isinstance(e, dict):
                continue
            a = scene.actors.get(e.get("ref"))
            if a is None or getattr(a, "is_pc", False):
                continue
            if e.get("kind") == "condition" and e.get("condition") == "dead":
                killed.append(a.name)
            elif e.get("kind") == "damage" and str(getattr(o, "op", "")) in ("attack", "damage"):
                struck.append(a.name)
    if killed:
        scene.heat = {"note": f"the player just killed {', '.join(killed)} in "
                              f"front of onlookers", "age": 0, "kind": "killing"}
        return
    if struck:
        scene.heat = {"note": f"the player just attacked {', '.join(sorted(set(struck)))} "
                              f"in front of onlookers", "age": 0, "kind": "violence"}
        return
    said = str(player_text or "")
    # A claim about what they are, made out loud, that the sheet holds false: the
    # crowd saw somebody announce they were a god and nothing happen. The Bluff's
    # verdict, when the engine rolled one, decides whether anybody half-believed it.
    claim = false_claim(said, scene)
    if claim:
        bluff = next((o for o in (outcomes or [])
                      if str(getattr(o, "op", "")) == "check"
                      and "bluff" in str(getattr(o, "tell", "")).lower()), None)
        took = bluff is not None and str(getattr(bluff, "verdict", "")) == "success"
        scene.heat = {"note": f"the player just declared, out loud and in front of "
                              f"onlookers, that they {claim} — and nothing happened"
                              + ("; the claim half-took with some of them" if took
                                 else "; nobody believed a word of it"),
                      "age": 0, "kind": "delusion"}
        return
    m = _HEAT_PROPERTY.search(said)
    if m:
        scene.heat = {"note": f"the player just went at somebody's goods in the open "
                              f"— {' '.join(m.group(0).split())} — in front of "
                              f"onlookers", "age": 0, "kind": "property"}
        return
    m = _HEAT_BRANDISH.search(said)
    if m:
        scene.heat = {"note": f"the player just drew a weapon in the open — "
                              f"{' '.join(m.group(0).split())} — in front of onlookers",
                      "age": 0, "kind": "threat"}
        return
    if _HEAT_SHOUT.search(redact_speech(said)):
        scene.heat = {"note": "the player just shouted in the open, in front of "
                              "onlookers", "age": 0, "kind": "threat"}


_HEAT_REACTS = {
    "killing": ("Bystanders react to it — fear, scattering, someone running for the "
                "watch. Nobody chats casually with the killer, and merchants do not "
                "approach."),
    "violence": ("The people here react to it NOW — flinching, backing off, somebody "
                 "shouting at the player or reaching for a weapon, somebody going for "
                 "the watch. Nobody stands and watches in silence."),
    "property": ("The people here react to it NOW — whoever owns the goods objects out "
                 "loud, the nearest person steps back or squares up, somebody says "
                 "something to the player about it. Nobody stands and watches in "
                 "silence."),
    "threat": ("The people nearest react to it NOW — a hand to a weapon, a step back, "
               "a word said to the player. Nobody stands and watches in silence."),
    "delusion": ("The people here react as people do to somebody announcing they are "
                 "what they plainly are not: an exchanged look, a step back, a laugh, "
                 "pity, somebody finding something else to look at — or, if the claim "
                 "half-took, unease and a muttered prayer. Nobody kneels. The claim "
                 "is false and stays false."),
}


def heat_brief(scene) -> str:
    t = getattr(scene, "heat", None) or {}
    if not t.get("note"):
        return ""
    react = _HEAT_REACTS.get(str(t.get("kind") or "killing"), _HEAT_REACTS["killing"])
    return f"WHAT THE CROWD JUST SAW (fact): {t['note']}. {react}"


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




# The sentence that makes somebody the player's opponent-to-be: they step up, square
# off, draw, come forward. Read against the person's own phrase within the sentence.
# Measured on the second live replay (2026-09-18): "a challenger" bound to "the woman in
# the shadows" — the one person promoted from the insult beat, who had merely recoiled
# — while "the man in the scarred leather vest … the predatory grin deepens … tensing as
# if ready to spring" was never promoted at all, because four scenery extras had used
# the cap. The sunder and the killing blow both went to the woman.
_CHALLENGES = re.compile(
    r"(?:steps? (?:forward|up|in|into the (?:circle|ring|open))|squares? (?:off|up)|"
    r"faces? you|comes? forward|pushes? (?:to the front|through the crowd)|"
    r"draws? (?:a|an|his|her|their|the) \w+|(?:his|her|their) hand (?:goes|drops|rests|"
    r"falls) to (?:a|the|his|her|their) (?:\w+ )?(?:hilt|blade|sword|club|weapon|axe|"
    r"dagger|knife)|meets? your (?:gaze|eyes|stare)|ready to spring|tens(?:es|ing) as if|"
    r"grin\w* (?:deepens|widens|spreads)|cracks? (?:his|her|their) knuckles|"
    r"rolls? (?:his|her|their) shoulders|challenges? you|accepts? (?:the|your) challenge|"
    r"answers? (?:the|your) challenge|spits? (?:at your feet|in the dirt)|"
    r"lunges?|swings?|strikes?|charges?|comes? at you)", re.I)


def challengers(beat: str, phrases) -> list[str]:
    """The cast phrases whose sentence in the beat carries a challenge cue."""
    if not beat:
        return []
    from .narration import unquoted

    out: list[str] = []
    last_named: str | None = None
    for sentence in re.split(r"(?<=[.!?])\s+", unquoted(beat)):
        low = sentence.lower()
        named = [p for p in phrases
                 if (ws := [w for w in _name_words(p) if len(w) >= 3])
                 and all(re.search(rf"\b{re.escape(w)}", low) for w in ws)]
        if _CHALLENGES.search(sentence):
            # The sentence's own people, else the pronoun's antecedent: "The man in
            # the scarred leather vest … the grin deepens. He shifts his weight, tensing
            # as if ready to spring" puts the cue one sentence after the name.
            who = named or ([last_named] if last_named and _PRONOUN_SUBJECT.search(sentence)
                            else [])
            for p in who:
                if p not in out:
                    out.append(p)
        if named:
            last_named = named[-1]
        elif _CAST_INTRO.search(sentence):
            # Somebody NOT in the list was named here: a pronoun in the next sentence
            # is theirs, not the last listed person's. Measured: "He … ready to
            # spring" bound to the woman two sentences back while the man of the
            # sentence between them was the one tensing.
            last_named = None
    return out


# The player going to look for somebody. Verbs of seeking and addressing, because both
# assume the person is there: "I turn to find the mayor" and "I ask the mayor for a reward"
# were the same turn on 2026-09-19, and the second is the one that produced a 13-hp Warrior
# called *mayor*.
_LOOKS_FOR = re.compile(
    r"\bI\s+(?:turn\s+to\s+find|turn\s+to|look\s+for|looks\s+for|search\s+for|seek\s+out|"
    r"seek|find|approach|approaches|go\s+to|walk\s+up\s+to|speak\s+to|speaks\s+to|"
    r"talk\s+to|talks\s+to|ask|asks|address|addresses|call\s+for|calls\s+for|summon|"
    r"summons|look\s+around\s+for)\s+"
    r"(?:the|a|an|my|to\s+the)?\s*([A-Za-z][A-Za-z' -]{2,40}?)"
    r"(?=[,.!?;]|\s+(?:and|about|for|to|if|that|what|where|who|whether|why|how)\b|$)",
    re.I)


def person_sought(player_text: str) -> str:
    """The person the player's own sentence goes looking for, or "".

    Read off the player's words, not the model's: item 29 is about *whose word* somebody
    exists on. The narration describing people arriving is an arrival and legitimate; the
    player naming somebody is a question, and a question may be answered "no".
    """
    m = _LOOKS_FOR.search(redact_speech(player_text or ""))
    if not m:
        return ""
    phrase = " ".join(m.group(1).split())
    # "the mayor of the town" is the mayor; "the stranger his name" is the stranger. The
    # capture runs to the next clause word, and neither tail is part of who they are.
    phrase = re.split(r"\s+(?:of|his|her|their|its|my|your)\s+", phrase, maxsplit=1)[0]
    return phrase.strip(" -'")


def absent_answer(scene, world, player_text: str, location_id: str | None = None) -> str:
    """The world's own sentence for a person the player named who is not here, or "".

    Empty for the two cases that are nobody's problem: they ARE here (much the commonest),
    and the phrase names nobody the world could rule on ("the man", "somebody"). Otherwise
    one of scope's two refusals, which the brief states as fact before the prose is written
    and the engine prints as a refusal if an op tried to reach them.
    """
    from rules import scope as scope_mod

    phrase = person_sought(player_text)
    if not phrase:
        return ""
    where = location_id if location_id is not None else getattr(scene, "location_id", None)
    found = scope_mod.look_for(world, phrase, scene, where)
    return str(found.get("line") or "")


def answer_the_absent(raw_intents, player_text: str, scene, world=None):
    """The world's answer is stated on every turn the player looks for somebody absent.

    Measured live 2026-09-19, twice: with the fact in the brief the model stopped inventing
    the mayor — and then said nothing about him either. "I find the mayor and grab him by
    the collar" came back as a plain `narrate_only` and a paragraph about the room, so the
    reported half of the bug was fixed and the *asked* half was not: the ruling was that
    the game should say the player could not find them.

    `repair_unknown_refs` can only answer when the model reached for a ref; this answers
    whether it did or not, which is the difference between a behaviour and a rule. The
    sentence rides on `narrate_only`'s `not_here` — stamped onto the one the plan already
    wrote, or appended — and `_op_narrate_only` prints it.
    """
    if not isinstance(raw_intents, list) or scene is None or world is None:
        return raw_intents
    if any(isinstance(r, dict) and (r.get("params") or {}).get("not_here")
           for r in raw_intents):
        return raw_intents
    said = absent_answer(scene, world, player_text)
    if not said:
        return raw_intents
    out = [dict(r) if isinstance(r, dict) else r for r in raw_intents]
    for raw in out:
        if isinstance(raw, dict) and str(raw.get("op", "")).lower() == "narrate_only":
            raw["params"] = dict(raw.get("params") or {}, not_here=said)
            return out
    return out + [{"op": "narrate_only",
                   "because": "the player looked for somebody who is not here",
                   "params": {"not_here": said}}]


_ASKS_A_NAME = re.compile(r"\b(?:your|his|her|their|the)\s+name\b|\bwho are you\b|"
                          r"\bwhat (?:are|do) (?:you|they|I) call\w*\b|\bname\?", re.I)
_EXAMINES = re.compile(
    r"\bI\s+(?:look|looks|study|studies|examine|examines|size up|sizes up|inspect|"
    r"inspects|watch|watches|eye|eyes|take in|takes in|appraise|appraises|scrutini[sz]e)\s+"
    r"(?:at\s+|over\s+|closely\s+at\s+)?(?:the|this|that|a|an)?\s*([a-z][a-z' -]{2,40}?)"
    r"(?:\s+(?:over|up and down|closely|carefully|more closely))?(?=[,.!?;]|\s+(?:and|as|"
    r"while|for)\b|$)", re.I)


def examined(player_text: str, scene) -> str | None:
    """The ref of the present person the player is looking over, or None.

    "I look the woman in the doorway over carefully" (group-3 replay, 2026-09-18) came
    back as posture and stillness and not one thing a stranger would see. The arrival
    check covers only newly booked people; this covers the ones already here."""
    if scene is None or not player_text:
        return None
    m = _EXAMINES.search(redact_speech(player_text))
    if not m:
        return None
    words = _name_words(m.group(1))
    if not words:
        return None
    best, score = None, 0
    for ref, a in (getattr(scene, "actors", {}) or {}).items():
        if a.is_pc:
            continue
        shared = len(words & _name_words(a.name))
        if shared > score:
            best, score = ref, shared
    return best


def name_the_nameless(scene, world) -> list[str]:
    """Every person here without a true name gets one, and a face — the actors a save
    holds from before the fields existed (c11 'woman', c16 'woman' on the play-test
    save had neither). Returns the refs named."""
    if scene is None or world is None:
        return []
    from rules import names as names_mod

    done = []
    for ref, a in (getattr(scene, "actors", {}) or {}).items():
        if a.is_pc or getattr(a, "true_name", ""):
            continue
        name = str(a.name or "")
        descriptor = not (name[:1].isupper() and not name.lower().startswith(("the ", "a ", "an ")))
        # Everybody leaves this loop with a face, whatever else is true of them. Item 32
        # (2026-09-19) turned on a hole here: a person carrying a real name and no world
        # id — a scheme's cast member, the opening companion when the roll gives a named
        # one — fell out at the `not descriptor` line before anything looked for an
        # appearance, and a keeper's synthetic `keeper:<place>` id resolves to no resident
        # so `resident_appearance` answered "". No appearance means no `Looks` clause in
        # the brief and nothing for the description check to require. Their people's own
        # body line is the fallback under both.
        if a.world_entity_id:
            a.true_name = a.name
            if not a.appearance:
                a.appearance = (names_mod.resident_appearance(world, a.world_entity_id)
                                or names_mod.appearance_for(world, scene.location_id, ref=ref))
            continue
        if not descriptor:
            a.true_name = a.name
            if not a.appearance:
                a.appearance = names_mod.appearance_for(world, scene.location_id, ref=ref)
            continue
        taken = [x.true_name for x in scene.actors.values() if getattr(x, "true_name", "")]
        taken += [x.name for x in scene.actors.values()]
        a.true_name = names_mod.true_name(world, scene.location_id, ref, taken)
        if not a.appearance:
            a.appearance = names_mod.appearance_for(world, scene.location_id, ref=ref)
        done.append(ref)
    return done


def settle_descriptions(scene, beat: str, player_text: str = "") -> list[str]:
    """Mark whoever this beat described, and return the refs it still owes a face.

    The rule, from item 32 (2026-09-19): the first beat in which an undescribed person
    acts, speaks or is addressed must say what they look like. Before this, the check ran
    over the phrases `note_cast` booked from *this turn's* prose and nothing else, so a
    keeper behind a counter, a scheme's cast, the opening companion and everyone promoted
    on an earlier turn could be referred to for the rest of the campaign with no sentence
    describing them — which is exactly what happened to Drenn Ironvale.

    Someone the beat describes is marked and never asked again. Someone the beat uses
    without describing is returned, and the caller appends their own line: the resident's
    Appearance fact, or their people's body line, both already on the actor.
    """
    from .narration import faceless

    if scene is None or not beat:
        return []
    addressed = _name_words(redact_speech(player_text or ""))
    owed: list[str] = []
    for ref, a in (getattr(scene, "actors", {}) or {}).items():
        if a.is_pc or getattr(a, "described", False):
            continue
        name = str(a.name or "")
        here = _mentions(beat, name)
        if not here and not (addressed & _name_words(name)):
            continue
        if here and not faceless(beat, name):
            # The beat did the job: a sentence about them carries a body word.
            a.described = True
            continue
        owed.append(ref)
    return owed


def _mentions(beat: str, name: str) -> bool:
    """Is this person in the beat at all — by the last word of their name, as `faceless`
    finds them? `faceless` answers False both for "described" and for "not there", so the
    two cases have to be told apart before one of them is treated as the other."""
    words = [w for w in re.findall(r"[a-z]+", str(name or "").lower()) if len(w) >= 3]
    if not words:
        return False
    return bool(re.search(rf"\b{re.escape(words[-1])}s?\b", beat, re.I))


def names_asked_for(scene, player_text: str = "") -> dict[str, str]:
    """Who the player just asked for a name, and the name each of them gives.

    The regression this exists for (2026-09-19, "stranger on the stairs refuses to give
    his name"): every promoted person carries a true name drawn from the world's own
    pools, and the brief deliberately never shows it — shown the name, the narrator used
    it before anybody had asked ("Soren's eyes narrow"). The half that was never built is
    the other direction. Asked outright, the model had no name to give and did the only
    thing left to it.

    So the name is handed over on exactly the turn it is asked for, to exactly the person
    asked, and never otherwise. The value is the name they give, or `""` when their
    attitude refuses (`attitude.tells_their_name`) — a refusal the player can do something
    about, which is what was asked for.

    Who was asked, in the same order of certainty `apply_introductions` uses: the unnamed
    person whose descriptor the player's own words name, else the only unnamed person
    here. Never the whole room: "what is your name" with six strangers standing about is
    a question to nobody in particular, and handing out six names is how the brief leaked
    them in the first place.
    """
    from rules import attitude as attitude_mod

    if scene is None or not player_text:
        return {}
    # The raw line, as `apply_introductions` reads it and for the same reason: the
    # question is speech, and the redactor blanks exactly the words that ask.
    if not _ASKS_A_NAME.search(player_text):
        return {}
    actors = getattr(scene, "actors", {}) or {}

    def _unnamed(a) -> bool:
        name = str(a.name or "")
        return not (name[:1].isupper() and not name.lower().startswith(("the ", "a ", "an ")))

    words = _name_words(redact_speech(player_text))
    here = [a for a in actors.values() if not a.is_pc and _unnamed(a)
            and getattr(a, "true_name", "") and a.true_name != a.name]
    # The BEST match, not every match, and the same rule `examined` uses. Measured live
    # 2026-09-19 on a copy of the `masta` save: "I turn to the woman in the corner and ask
    # her what her name is" matched both the woman in the corner and the woman, so two
    # names were offered and the beat ended with a second stranger volunteering hers to
    # nobody. One score short of the top is not who was asked.
    scored = sorted(((len(words & _name_words(a.name)), a) for a in here),
                    key=lambda pair: -pair[0])
    asked: list = []
    if scored and scored[0][0]:
        top = scored[0][0]
        best = [a for n, a in scored if n == top]
        # A tie is a question to nobody in particular: two women, "what is your name", and
        # there is no answering it without choosing for the player.
        asked = best if len(best) == 1 else []
    elif len(here) == 1:
        asked = here
    return {a.ref: (a.true_name if attitude_mod.tells_their_name(a) else "") for a in asked}


def apply_introductions(scene, beat: str, player_text: str = "") -> list[tuple[str, str]]:
    """A name given in play becomes the panel's name for that person.

    From `narration.introductions`: the speaker's head word finds the unnamed actor
    here (a descriptor name — lowercase, or "the …"); their display name becomes the
    name given, their true name too if none was held. A named person "introducing"
    themselves again changes nothing. Returns [(ref, name)] for the log."""
    from .narration import introductions

    if scene is None or not beat:
        return []
    out: list[tuple[str, str]] = []
    # The raw line, not the redacted one: "I ask the stranger for his name" is reported
    # speech, and the redactor blanks exactly the words that ask.
    asked = bool(_ASKS_A_NAME.search(player_text or ""))
    actors = getattr(scene, "actors", {}) or {}

    def _unnamed(a) -> bool:
        name = str(a.name or "")
        return not (name[:1].isupper() and not name.lower().startswith(("the ", "a ", "an ")))

    asked_words = _name_words(redact_speech(player_text or ""))
    # The person the player asked, if they asked anybody: the most certain answer there is,
    # and the one that was missing. Measured live 2026-09-19: asked for her name, the woman
    # in the corner said "you may call me Gorvothor" — and the panel kept "woman in the
    # corner". `introductions` read the speaker's head word as "low" (out of "a low,
    # resonant grind"), her true name is "Gorvothor Kragnir" so the equality below missed
    # the partial, and both women here answered to "woman", so every remaining branch
    # declined. The ref was known all along; nothing asked for it.
    was_asked = [actors[r] for r in names_asked_for(scene, player_text) if r in actors]
    for head, given in introductions(beat, asked_for_name=asked):
        # Whose name it is, in order of certainty: the person the player asked; the one the world holds THIS
        # name for (the brief gave it to them); the unnamed person the speaker's
        # head word names; the unnamed person the player addressed; the only unnamed
        # person here. Measured on the second group-3 replay (2026-09-18): six
        # descriptor-named people in the room, "'Gorvothor Kragnir,' he says" with no
        # role word in the sentence, and the panel kept "stranger".
        who = was_asked[0] if len(was_asked) == 1 else None
        if who is None:
            who = next((a for a in actors.values() if not a.is_pc
                        and str(getattr(a, "true_name", "")).lower() == given.lower()), None)
        if who is None and head:
            who = next((a for a in actors.values() if not a.is_pc and _unnamed(a)
                        and head in _name_words(a.name)), None)
        if who is None:
            addressed = [a for a in actors.values() if not a.is_pc and _unnamed(a)
                         and asked_words & _name_words(a.name)]
            if len(addressed) == 1:
                who = addressed[0]
        if who is None:
            unnamed = [a for a in actors.values() if not a.is_pc and _unnamed(a)]
            if len(unnamed) == 1:
                who = unnamed[0]
        if who is None or not _unnamed(who):
            continue
        _take_the_name(scene, who, given)
        out.append((who.ref, given))
    # And the narrator's own naming in passing — "The man—Korgath Varn—takes a slow
    # pull of his ale" (2026-09-24). Outside speech, so `introductions` skips it by
    # design; the head word finds the unnamed person the same way. A name somebody
    # here already carries is not taken twice.
    from .narration import named_in_apposition

    for head, given in named_in_apposition(beat):
        if any(str(a.name).lower() == given.lower() for a in actors.values()):
            continue
        who = next((a for a in actors.values() if not a.is_pc and _unnamed(a)
                    and head in _name_words(a.name)), None)
        if who is None:
            unnamed = [a for a in actors.values() if not a.is_pc and _unnamed(a)]
            if len(unnamed) == 1:
                who = unnamed[0]
        if who is None:
            continue
        _take_the_name(scene, who, given)
        out.append((who.ref, given))
    return out


def hailed_by(scene, beat: str) -> list[str]:
    """Who, in this beat, spoke to the player: refs of the people whose quoted line
    addresses "you".

    The second way a conversation opens (2026-09-24): being spoken to. NPC speech is
    prose, never an op, so the only record of it is the beat — a quoted span whose
    sentence, outside the quotes, names a person here, and whose words are aimed at the
    player. "'You're a long way from the interior,' he says" is a hail; "'Fine weather,'
    the carter tells the drover" is not. Attribution reuses the head-word and name-word
    matching the introductions use, in the same sentence or the one before.
    """
    from .narration import _QUOTED, _sentences, unquoted

    if scene is None or not beat:
        return []
    actors = getattr(scene, "actors", {}) or {}
    people = [(ref, a) for ref, a in actors.items() if not a.is_pc]
    if not people:
        return []
    out: list[str] = []
    sentences = _sentences(beat)
    for i, s in enumerate(sentences):
        for m in _QUOTED.finditer(s):
            if not re.search(r"\b(?:you|your|you're|you've|you'll)\b", m.group(0), re.I):
                continue
            outside = unquoted(s) + " " + (unquoted(sentences[i - 1]) if i else "")
            words = _name_words(outside)
            speaker = None
            # A named person first, by any word of their name; then a descriptor by
            # its role word ("the man", "the woman in the corner").
            for ref, a in people:
                mine = {w for w in _name_words(a.name) if len(w) >= 3}
                if mine and mine & words:
                    speaker = ref
                    break
            if speaker is None:
                role = _ROLE_WORD.search(outside)
                if role:
                    head = role.group(0).lower()
                    for ref, a in people:
                        if head in _name_words(a.name):
                            speaker = ref
                            break
            if speaker and speaker not in out:
                out.append(speaker)
    return out


def _take_the_name(scene, who, given: str) -> None:
    """The name on the page becomes the one the panel shows AND the one the world holds
    for them. Both, because a page name that survived `settle_introductions` is either
    the pool's own or one the story established first, and a true name left behind it
    would have the next introduction swap the story's name back out."""
    who.name = given
    who.true_name = given
    for e in scene.cast:
        if e.get("ref") == who.ref:
            e["who"] = given


def promote_cast(scene, added, beat: str = "", world=None) -> list[str]:
    """A person the ledger notes becomes a person the engine holds.

    The ruling, after the library beat: the place held but "there should have
    been a stranger" — the ledger knew about him and the scene did not, so he
    could not be attacked, addressed, traded with or found again. Every newly
    noted entry now spawns as a living civilian (the fight cues pick watchman-
    kinds for armed roles, guildhand for the rest), capped at four standing
    promoted civilians so a crowd scene does not flood the panel. The entry
    remembers its ref, so clearing the ledger walks its people off with it.
    """
    from rules import troops as troops_mod
    from rules.bestiary import instantiate

    if scene is None or not added:
        return []
    # Mid-fight they used to stay prose — "joining a battle takes the spawn op's
    # initiative bookkeeping, not a quiet walk-on" — and the consequence, measured
    # 2026-09-19, was that a band arriving mid-battle put **zero** bodies on the board,
    # which is exactly the turn where it matters most (item 30). They arrive now, and the
    # bookkeeping rule is kept rather than broken: they walk on as bystanders, in the room
    # and outside the initiative, and the two doors into a fight that already exist take
    # them from there — `joiners` when the beat says they draw, `attacked_by` when the beat
    # says they strike. Nobody is quietly inserted into the order.
    # The cap counts the promoted civilians STANDING, not the ledger entries that
    # still remember them. Measured 2026-09-18: the ledger is cleared after every
    # fight and the actors are not, so the count restarted at zero while nine
    # non-player actors stood on a five-by-five board.
    standing = [a for a in scene.actors.values()
                if not a.is_pc and a.hp > 0 and a.has_state("role.bystander")]
    counts = {str(e.get("who")): int(e.get("count", 1) or 1) for e in scene.cast}
    zones = {str(e.get("who")): str(e.get("zone") or "near") for e in scene.cast}
    made: list[str] = []
    refs: list[str] = []
    # A group is bodies, plural. "a group of six men" that promotes one actor is
    # the same lie as a pair of guards being one guard: the fiction says six and
    # the dice know about one.
    # A crowd the prose booked arrives as ONE unit with the combined hit points of its
    # members, not as four bodies standing in for twelve (item 33). This is where the cap
    # stopped fighting the fiction: "a band of twelve raiders" is a unit of twelve.
    units: list[str] = []
    for phrase in list(added):
        n = int(counts.get(phrase, 1) or 1)
        if n < troops_mod.UNIT_FROM:
            continue
        unit = troops_mod.form(template_for(phrase, _pc_level(scene)), n, scene=scene,
                               name=phrase if _plural_role(phrase) else "")
        scene.add(unit, zone=zones.get(phrase, "near"))
        from rules import states

        unit.add_condition(states.BYSTANDER_KEY, source="introduced by the scene")
        if getattr(scene, "grid", None) is not None:
            scene.place_by_zone([unit.ref])
        for e in scene.cast:
            if e.get("who") == phrase and not e.get("ref"):
                e["ref"] = unit.ref
                break
        made.append(phrase)
        refs.append(unit.ref)
        units.append(phrase)
    wanted = []
    for phrase in added:
        if phrase in units:
            continue
        # A bare plural role — "weary porters", "haggling traders", "nearby merchants"
        # — is scenery: it stays in the ledger for the prose to keep consistent and
        # never becomes ONE body with a plural name and 4 hp (the "local guards"
        # actor of the 2026-09-18 roster). A counted group arrives through
        # `_CAST_GROUP` with its count and is promoted body by body.
        if counts.get(phrase, 1) == 1 and _plural_role(phrase):
            continue
        # Only somebody the page put IN the scene. A person merely spoken of — "the
        # elder-quarter, where the elder keeps the oldest things" — is a mention, and
        # a mention stays on the ledger without a body. Reported 2026-09-24: an elder
        # named in Korgath's speech about another quarter was stood in the lane, mid-
        # conversation, with no sentence of him arriving, and the talk went on as if
        # he had always been there. The ruling: people may enter, but they enter in
        # the prose, and the conversation reacts.
        if not present_in_scene(beat, phrase):
            continue
        wanted.extend([phrase] * max(1, counts.get(phrase, 1)))
    # The people the beat put in front of the player go first and go over the cap:
    # the cap is about crowds, and the man who squared off is not the crowd.
    fronted = challengers(beat, wanted)
    wanted.sort(key=lambda p: p not in fronted)
    for phrase in wanted:
        if len(standing) + len(made) >= _PROMOTED_CAP and phrase not in fronted:
            break
        actor = instantiate(template_for(phrase, _pc_level(scene)), scene=scene, name=phrase)
        # Through the door. The fallback that wrote `scene.actors` directly would now
        # write into a derived view and vanish; `add` stamps the place and the zone —
        # the zone the prose put them in, so the map lays them out where the words did.
        scene.add(actor, zone=zones.get(phrase, "near"))
        # In the room, not in the fight. Law two: the fact travels as an effect whose
        # tag is `role.bystander`, lifted by the one door into a fight and by a blow
        # given or taken — never by a flag beside it.
        from rules import states

        actor.add_condition(states.BYSTANDER_KEY, source="introduced by the scene")
        # A name behind the descriptor and a face beside it, from the world's own
        # pools and bodies (rules/names.py) — the panel keeps showing the descriptor
        # until the name is given in play.
        if world is not None:
            from rules import names as names_mod

            taken = [a.true_name for a in scene.actors.values() if getattr(a, "true_name", "")]
            taken += [a.name for a in scene.actors.values()]
            actor.true_name = names_mod.true_name(world, scene.location_id, actor.ref, taken)
            actor.appearance = names_mod.appearance_for(world, scene.location_id,
                                                        ref=actor.ref)
        if getattr(scene, "grid", None) is not None:
            scene.place_by_zone([actor.ref])
        for e in scene.cast:
            if e.get("who") == phrase and not e.get("ref"):
                e["ref"] = actor.ref
                break
        made.append(phrase)
        refs.append(actor.ref)
    bind_thread(scene, refs, beat)
    return made


# How a beat puts somebody in the room, outside speech: they do something here, or the
# sentence places them in it. Grammar, not content — the same kind of list the phrase
# splitter keeps — and it is deliberately the loose half of a two-part test, since
# `narration.action_sentences` already answers "does this person act in this beat".
_PLACES_THEM_HERE = re.compile(
    r"\b(?:comes?|coming|walks?|walking|enters?|entering|approach(?:es|ing)?|steps?|"
    r"stepping|appears?|appearing|arrives?|arriving|push(?:es|ing)?|joins?|joining|"
    r"emerges?|emerging|stands?|standing|sits?|sitting|leans?|leaning|waits?|waiting|"
    r"kneels?|kneeling|crouch(?:es|ing)?|hunched|slumped|sprawled|lies|lying|"
    r"looks? up|turns? to|watch(?:es|ing)?|is here|are here|there (?:is|are|sits|"
    r"stands)|beside you|before you|"
    r"in front of you|behind you|next to you|across from you|at your (?:side|elbow|"
    r"shoulder))\b", re.I)


def present_in_scene(beat: str, phrase: str) -> bool:
    """Whether the beat, outside speech, puts this person in the room.

    Conservative on purpose, and the 2026-09-18 lesson is why: skipping a person the
    page put in the room is how the man who swung first was never put on the board.
    So the answer is YES unless the beat says otherwise — no beat to judge against is
    a yes; a person who acts or is placed here is a yes; and the only no is a person
    who appears in the narration solely as somebody spoken OF: "the elder of the far
    quarter", "the guards at the gate are sharp", or not in the narration at all,
    only in somebody's line."""
    from .narration import _sentences, action_sentences, unquoted

    if not beat or not phrase:
        return True
    plain = unquoted(beat)
    head = _role_head(phrase)
    if not head:
        return True
    about = [s for s in _sentences(plain) if re.search(rf"\b{re.escape(head)}s?\b", s, re.I)]
    if not about:
        return False                 # only ever inside speech
    if action_sentences(plain, [phrase]):
        return True
    if any(_PLACES_THEM_HERE.search(s) for s in about):
        return True
    elsewhere = re.compile(rf"\b{re.escape(head)}s?\s+(?:of|at|in|beyond|across|over in)"
                           rf"\s+the\s+\w+", re.I)
    return not all(elsewhere.search(s) for s in about)


def _plural_role(phrase: str) -> bool:
    """"weary porters" → True; "man in the leather apron", "boss" → False."""
    head = _role_head(phrase)
    if head in ("men", "women", "people", "folk", "guardsmen", "clansmen", "swordsmen",
                "fishermen", "watchmen"):
        return True
    if not head or not head.endswith("s") or head in ("boss",):
        return False
    singular = head[:-1] if not head.endswith("ies") else head[:-3] + "y"
    return bool(_ROLE_WORD.fullmatch(singular))


# --- The engagement: who the player is dealing with, as a ref ---------------------------

def bind_thread(scene, promoted: list[str] | None = None, beat: str = "") -> str | None:
    """Give the standing thread's subject a ref, when the scene can say whose it is.

    The thread's subject was a free phrase — "a challenger", "him", "the stranger" —
    and nothing tied it to an actor. Measured 2026-09-18, the ring fight: "wait for a
    challenger" bound to nobody, the challenger was promoted from the next beat as
    "desperate man", "tell him to come at me" continued the thread on a bare pronoun,
    and the first attack plan aimed at the man the player had spoken to all scene
    instead. From that wrong choice everything downstream was correct and a bystander
    died.

    Two ways to a ref, in order: an actor whose name shares a distinctive word with the
    subject; else the ONE person promoted this beat while the subject named a role
    nobody on the board held. Two promoted at once is a guess, and is not made.
    """
    if scene is None:
        return None
    t = getattr(scene, "thread", None) or {}
    subject = str(t.get("subject") or "")
    if not subject or t.get("ref") in (getattr(scene, "actors", {}) or {}):
        return t.get("ref")
    words = _name_words(subject) - {"him", "her", "them", "it", "man", "woman",
                                    "one", "someone", "somebody"}
    for a in scene.actors.values():
        if a.is_pc:
            continue
        if words and words & _name_words(a.name):
            t["ref"] = a.ref
            scene.thread = t
            return a.ref
    # Only while the engagement is fresh. Measured on the first live replay: "a
    # challenger" was still the subject three turns and one fight later, and the one
    # man promoted from the Continue beat — a watchman with a torch — was bound as
    # the challenger the player had waited for.
    if not promoted or int(t.get("age", 0) or 0) > 1:
        return None
    live = [r for r in promoted if r in scene.actors]
    if beat:
        # With the beat in hand, the one bound is the one the beat put in front of the
        # player — "steps forward", "squares off", "the grin deepens" — and nobody
        # else, however few were promoted. The woman in the shadows recoiled; she is
        # not the challenger.
        fronted = challengers(beat, [scene.actors[r].name for r in live])
        live = [r for r in live if scene.actors[r].name in fronted]
    if len(live) == 1:
        t["ref"] = live[0]
        scene.thread = t
        return live[0]
    return None


def engaged_refs(scene) -> list[str]:
    """Who the player is engaged with, as refs, most certain first — or [].

    In a fight: the conscious foes on the other sides, the one the thread marked as the
    opponent first. Out of one: the actor the thread is bound to. Never a bystander,
    never a body.
    """
    if scene is None:
        return []
    actors = getattr(scene, "actors", {}) or {}
    pc = scene.pc() if hasattr(scene, "pc") else None
    t = getattr(scene, "thread", None) or {}
    marked = t.get("opponent") or t.get("ref")
    out: list[str] = []
    if getattr(scene, "in_encounter", False):
        for side, refs in (getattr(scene, "sides", None) or {}).items():
            if pc is not None and pc.ref in refs:
                continue
            out.extend(r for r in refs if r in actors and _can_be_fought(actors[r]))
    elif marked in actors:
        # Out of a fight the one the player is engaged with IS engaged, bystander tag
        # or not — the player squaring up to him is how he stops being one. Only a
        # body is not.
        a = actors[marked]
        if int(getattr(a, "hp", 0)) > 0 and not a.has_state("state.down"):
            out.append(marked)
    if marked in out:
        out.remove(marked)
        out.insert(0, marked)
    return out


def check_the_target(raw_intents, player_text: str, scene, recent=()) -> list | None:
    """Hold the plan's attack to the person the player is engaged with.

    Runs after the target fills and before validation. The mechanical test: the
    player's own attack is aimed at a known actor whose name the player's sentence
    never uses — a pronoun, "the man" — while the scene knows who they are engaged
    with (`engaged_refs`) and it is somebody else. One engaged person: the attack is
    moved onto them with the fix named. Several, and the model's choice is one the
    recent beats mention: nobody chooses for the player — the attack is handed back
    as a question through the engine's own refusal (`params.undecided`), which reaches
    the page as "Which of them — …?" and costs nothing else.

    A player who NAMES their victim is never second-guessed: `repair_misaimed_attack`
    owns that sentence, and a match on the target's own name ends this at once.
    Returns amended intents, or the list unchanged when there is nothing to do.
    """
    if not isinstance(raw_intents, list) or scene is None:
        return raw_intents
    text = redact_speech(player_text or "")
    if _AIMED_AT.search(text):
        return raw_intents
    actors = getattr(scene, "actors", {}) or {}
    pc = scene.pc() if hasattr(scene, "pc") else None
    pc_ref = getattr(pc, "ref", "pc")
    engaged = engaged_refs(scene)
    if not engaged:
        return raw_intents
    said = " ".join(str(b) for b in (recent or ())[-2:]).lower()
    changed = False
    out = []
    for raw in raw_intents:
        if not (isinstance(raw, dict) and str(raw.get("op", "")).lower() == "attack"
                and (raw.get("actor") or pc_ref) == pc_ref):
            out.append(raw)
            continue
        target = raw.get("target")
        if not isinstance(target, str) or target not in actors or target in engaged:
            out.append(raw)
            continue
        if _name_words(text) & _name_words(actors[target].name):
            out.append(raw)                      # the player named this person
            continue
        raw = dict(raw)
        if len(engaged) == 1:
            raw["target"] = engaged[0]
            raw["because"] = (f"the player is engaged with {actors[engaged[0]].name}, "
                              f"not {actors[target].name}")
            changed = True
        else:
            live = list(engaged)
            if (_name_words(actors[target].name) & set(re.findall(r"[a-z']+", said))
                    and target not in live):
                live.append(target)
            params = dict(raw.get("params") or {})
            params["undecided"] = live
            raw["params"] = params
            changed = True
        out.append(raw)
    return out if changed else raw_intents


# --- The fight opened from their side ------------------------------------------------

# A blow struck, in the present tense the beats are written in. Finite forms only: an
# infinitive ("to strike") is an intention, and the guards below cut those.
#
# Two kinds of verb, because most of the old list was not violent at all. Measured
# 2026-09-25, six of six friendly sentences read as a blow at the player and
# `struck_first` rolled the barmaid's attack: "rushes over to you with a tankard", "grabs
# your hand and shakes it warmly", "throws a wink at you", "cuts you a slice of cheese",
# "charges you two silver", "slams a mug down in front of you". Any of thirty verbs
# followed ANYWHERE in the sentence by "you" or "your" was a blow.
#
# A verb that is a blow in itself — lunges, stabs, punches — still needs only the player
# in its sentence (the 2026-09-18 replay put 100 characters between "lunges" and "your
# shoulder", and that must still open the fight):
_BLOWS = (r"(?:lunges?|stabs?|slashes?|lashes? out|comes? at|punches?|tackles?|bashes?|"
          r"attacks?|strikes?)")
# ... except for the idioms that borrow them: "strikes up a conversation with you",
# "strikes a deal", "the offer strikes you as fair".
_BLOW_IDIOM = re.compile(
    r"\s*(?:up\b|a\s+(?:deal|bargain|match|pose|note|chord|balance|light|flint)\b|"
    r"you\s+(?:as|that)\b|(?:his|her|their)\s+(?:meal|food|plate|bowl|stew|work)\b)",
    re.I)
# A verb that usually is NOT a blow — somebody rushes over, grabs a hand, cuts bread,
# charges a price, throws a look — is one only with something that makes it one in the
# same sentence: a weapon, or a blow aimed at the player's body or guard.
_CONTACTS = (r"(?:swings?|thrusts?|hacks?|jabs?|kicks?|clubs?|swipes?|grabs?|seizes?|"
             r"rushes?|charges?|cuts?|drives?|smashes?|shoves?|slams?|hurls?|throws?|"
             r"brings? (?:\w+\s+){0,3}down)")
_WEAPON_NOUN = (r"(?:blade|sword|sabre|saber|scimitar|knife|knives|dagger|dirk|stiletto|"
                r"club|cudgel|axe|hatchet|mace|hammer|maul|spear|pike|halberd|glaive|"
                r"flail|whip|sap|fists?|knuckles|claws?|teeth|fangs|crossbow|bolt|arrow)")
_YOUR_BODY = (r"(?:throat|neck|face|jaw|head|skull|temple|chest|ribs|gut|belly|stomach|"
              r"back|shoulder|knees?|legs?|guard|shield|eyes?|nose|mouth|collar|hair|"
              r"windpipe|groin|spine)")
_AIMED = re.compile(
    r"\b(?:at|into|against)\s+(?:you|your)\b|\byour\s+" + _YOUR_BODY + r"\b|"
    r"\byou\s+(?:in|across|on)\s+the\s+" + _YOUR_BODY + r"\b|\b" + _WEAPON_NOUN + r"\b",
    re.I)
# What is thrown, cut or swung that is never a blow, and ends the question: a wink, a
# glance, a coin, a slice.
_GESTURE = re.compile(
    r"\b(?:wink|glance|look|smile|grin|nod|kiss|shrug|salute|greeting|word|question|"
    r"coin|coins|purse|slice|piece|share|price|fee|bargain|door|gate|shutter)s?\b", re.I)

_STRIKES_AT_YOU = re.compile(r"\b" + _BLOWS + r"\b(?:[^.!?]*?)\b(?:you|your)\b", re.I)
_BLOW_VERB = re.compile(_BLOWS, re.I)
_CONTACT_VERB = re.compile(r"\b" + _CONTACTS + r"\b", re.I)


def _a_blow_in(sentence: str):
    """Where the blow at the player starts in this sentence, or None.

    The whole sentence, not a window: measured live 2026-09-18 on the first replay, "He
    lunges, his weight shifting forward as he brings the notched broadsword in a
    desperate, overhead arc aimed at your shoulder" put 100 characters between the verb
    and "your", and an 80-character window let the fight go unopened again.
    """
    for m in _STRIKES_AT_YOU.finditer(sentence):
        verb = _BLOW_VERB.match(sentence, m.start())
        if not _BLOW_IDIOM.match(sentence, verb.end()):
            return m
    for m in _CONTACT_VERB.finditer(sentence):
        rest = sentence[m.end():]
        aimed = _AIMED.search(rest)
        if aimed is None:
            continue
        # The thing thrown, cut or swung comes before the aim: "throws a wink at you".
        if _GESTURE.search(rest[:aimed.start()]):
            continue
        return m
    return None
# What turns a blow into a threat, a feint, or somebody else's: these within four
# words before the verb, and the sentence opens no fight. "coils his muscles, waiting
# for you" (beat 31 of the ring fight) must not; "he lunges … as he tries to overwhelm
# your guard" (beat 33) must.
_NOT_A_BLOW = re.compile(
    r"\b(?:doesn't|does not|didn't|did not|not|never|without|nor|"
    r"as if to|as though to|threatens? to|threatening to|ready to|about to|"
    r"prepar\w+ to|poised to|waiting to|wants? to|means? to|would|could|might|"
    r"feints?|pretends? to|mimes?|before (?:he|she|they) can|if (?:he|she|they)|"
    r"you)\s+(?:\w+\s+){0,3}?$", re.I)
_PRONOUN_SUBJECT = re.compile(r"\b(he|she|they)\b", re.I)


def attacked_by(scene, gm_beat: str) -> list[tuple[str, str]]:
    """(ref, sentence) for each non-player actor this beat says struck at the player,
    outside a fight — the mirror of `inject_fight`.

    Measured 2026-09-18, the ring fight: "he lunges, the blade whistling through the air
    as he tries to overwhelm your guard with a heavy, horizontal sweep" — the plan was
    `narrate_only`, the beat had him swing, and the engine rolled nothing. The only door
    into an encounter was the model's `begin_encounter`; `inject_fight` opens one only
    when the PLAYER starts it, and `joiners` reads a bystander in only while a fight is
    already running. Three turns later the player was "put into combat" by his own sunder.

    The sentence's striker is found in code, in this order: an actor whose name's head
    word stands in the sentence before the verb; else a third-person pronoun, which is
    the most recent non-player actor named earlier in the beat; else nobody, and the
    sentence is left — a fight is not opened on a guess. The engine opens the fight
    from their side (`Engine.struck_first`).
    """
    if scene is None or not gm_beat or getattr(scene, "in_encounter", False):
        return []
    from .narration import unquoted

    actors = getattr(scene, "actors", {}) or {}
    people = [(r, a) for r, a in actors.items()
              if not a.is_pc and int(getattr(a, "hp", 0)) > 0 and not a.is_down]
    if not people:
        return []

    def heads(name: str) -> set[str]:
        return {w for w in _name_words(name) if len(w) >= 3}

    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    last_named: str | None = None
    for sentence in re.split(r"(?<=[.!?])\s+", unquoted(gm_beat)):
        low = sentence.lower()
        # Who this sentence names, for the pronoun that may follow in the next.
        named_here = [r for r, a in people
                      if any(re.search(rf"\b{re.escape(h)}s?\b", low) for h in heads(a.name))]
        m = _a_blow_in(sentence)
        if not m:
            if named_here:
                last_named = named_here[-1]
            continue
        before = sentence[:m.start()]
        if _NOT_A_BLOW.search(before + " "):
            if named_here:
                last_named = named_here[-1]
            continue
        # The striker: a name before the verb, else the pronoun's antecedent.
        striker = next((r for r, a in people
                        if any(re.search(rf"\b{re.escape(h)}s?\b", before, re.I)
                               for h in heads(a.name))), None)
        if striker is None and _PRONOUN_SUBJECT.search(before):
            striker = last_named
        if named_here:
            last_named = named_here[-1]
        if striker is None:
            # A blow at the player with nobody the code can name behind it. Not opened
            # on a guess — but said, so the turn log shows the sentence that was read
            # and left rather than a silence that looks like nothing happened.
            out.append((None, sentence.strip()))
            continue
        if striker in seen:
            continue
        seen.add(striker)
        out.append((striker, sentence.strip()))
    return out


# --- A thing is not a person -----------------------------------------------------------

# Objects the prose and the player talk about hitting: a strike at one of these is a
# strike at whoever holds it, never a person to spawn. Measured 2026-09-18: "I strike
# the weapon and sunder it" → the misaim repair read "the weapon" as a victim nobody had
# made real, spawned a THUG NAMED "weapon" with 13 hp, and the player killed it for XP.
_A_THING = frozenset({
    "weapon", "weapons", "blade", "sword", "club", "axe", "dagger", "knife", "spear",
    "staff", "cudgel", "mace", "hammer", "sap", "bow", "shield", "hilt", "haft",
    "table", "door", "chair", "stool", "bench", "barrel", "crate", "stall", "cart",
    "wall", "window", "rope", "chain", "lock", "gate", "bottle", "torch", "lantern",
    "sign", "post", "pole", "plank", "board", "wood", "rock", "stone", "pebble",
    "armor", "armour", "helm", "helmet", "cloak", "belt", "purse", "pouch", "bag",
})


_CHEAT_XP = re.compile(r"(\d[\d,]*)\s*(?:xp|experience(?: points?)?|exp)\b", re.I)
_CHEAT_COIN = re.compile(r"(\d[\d,]*)\s*(gold|gp|silver|sp|copper|cp|platinum|pp)\b", re.I)


def cheat_intents(wish: str, scene) -> list[dict]:
    """The author's wish as intents, read in code where the wish is a number.

    "/cheat I gain 2000 experience" did nothing twice (2026-09-18, items 1 and 20):
    no op carried experience, so the model had nothing to plan. Detected mechanically
    first — an amount of experience is an `xp` op, an amount of coin a `give` of the
    denomination — and only a wish these do not read goes to the model."""
    if scene is None or not wish:
        return []
    pc = scene.pc() if hasattr(scene, "pc") else None
    if pc is None:
        return []
    out: list[dict] = []
    m = _CHEAT_XP.search(wish)
    if m:
        out.append({"op": "xp", "because": "the author's word",
                    "params": {"amount": int(m.group(1).replace(",", "")),
                               "reason": "the author's word"}})
    m = _CHEAT_COIN.search(wish)
    if m:
        denom = {"gold": "gp", "silver": "sp", "copper": "cp", "platinum": "pp"}.get(
            m.group(2).lower(), m.group(2).lower())
        out.append({"op": "give", "because": "the author's word",
                    "params": {"item": denom, "count": int(m.group(1).replace(",", "")),
                               "to": pc.ref}})
    return out


def names_a_thing(phrase: str) -> bool:
    """Whether a victim phrase is an object — its head word, or all of it."""
    words = re.findall(r"[a-z']+", str(phrase or "").lower())
    return bool(words) and (words[-1] in _A_THING or all(w in _A_THING | _NAME_NOISE
                                                          for w in words))


_AT_THE_THING = re.compile(
    r"\b(?:strike|strikes|hit|hits|smash|smashes|break|breaks|sunder|sunders|shatter|"
    r"shatters|attack|attacks|swing (?:at|on)|swings (?:at|on)|cut|cuts|slash|slashes)\s+"
    r"(?:at\s+)?(?:the|his|her|their|that|this)\s+(?:\w+\s+){0,2}?(" +
    "|".join(sorted(_A_THING)) + r")\b", re.I)


def aim_at_the_holder(raw_intents, player_text: str, scene) -> list | None:
    """A strike at a thing somebody is holding is a strike at that somebody.

    The player wrote "I strike the weapon and sunder it"; the engine's sunder needs the
    PERSON as its target and refused five times ("a sunder needs a target"), and the
    misaim repair then made the thing a person. So: when the player's sentence names an
    object as what they hit and an attack in the plan has no target (or one that is a
    bystander), the target becomes the one person engaged with the player
    (`engaged_refs`), and a sunder the sentence asked for is set. Nobody engaged, or two:
    the list comes back unchanged and the ordinary paths speak.
    """
    if not isinstance(raw_intents, list) or scene is None:
        return raw_intents
    text = redact_speech(player_text or "")
    at_thing = _AT_THE_THING.search(text)
    # The sunder the player asked for is set whether or not anybody is engaged: on the
    # first live replay the plan came back a plain attack on the right man, and the
    # "sunder" in the player's own sentence reached nobody (the manoeuvre correction
    # only ever REMOVES a manoeuvre the player did not ask for).
    wants_sunder = bool(MANOEUVRE_CUES["sunder"].search(text))
    if not at_thing and not wants_sunder:
        return raw_intents
    engaged = engaged_refs(scene)
    actors = getattr(scene, "actors", {}) or {}
    pc = scene.pc() if hasattr(scene, "pc") else None
    pc_ref = getattr(pc, "ref", "pc")
    changed = False
    out = []
    for raw in raw_intents:
        if not (isinstance(raw, dict) and str(raw.get("op", "")).lower() == "attack"
                and (raw.get("actor") or pc_ref) == pc_ref):
            out.append(raw)
            continue
        raw = dict(raw)
        target = raw.get("target")
        aimed_at_a_thing = (not target or target not in actors
                            or actors[target].has_state("role.bystander"))
        if at_thing and aimed_at_a_thing and len(engaged) == 1:
            raw["target"] = engaged[0]
            raw["because"] = (f"the player struck at the {at_thing.group(1)} "
                              f"{actors[engaged[0]].name} is holding")
            changed = True
        params = dict(raw.get("params") or {})
        if wants_sunder and params.get("manoeuvre") != "sunder":
            params["manoeuvre"] = "sunder"
            raw["params"] = params
            changed = True
        out.append(raw)
    return out if changed else raw_intents

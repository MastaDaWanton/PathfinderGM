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
    if previous and _signature(intents) == list(previous):
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

# What the player's words suggest the newcomers are.
_TEMPLATE_CUES = (
    (re.compile(r"\b(watch|watchman|watchmen|guard|guards|soldier)\b", re.I), "watchman"),
    (re.compile(r"\b(dog|hound|mastiff)\b", re.I), "guard dog"),
    (re.compile(r"\b(guildhand|clerk|servant|porter)\b", re.I), "guildhand"),
)


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
    candidates = [r for r, a in scene.actors.items()
                  if not a.is_pc and not a.has_condition("dead")
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
    amended = [{"op": "spawn", "because": "they are already in the scene the GM described",
                "params": {"template": template, "count": count}}]
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
    if actor is None or not actor.can_act() or actor.hp <= 0:
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

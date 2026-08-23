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
    (re.compile(r"\b(guildhand|clerk|servant|porter)\b", re.I), "guildhand"),
)


def _can_be_fought(actor) -> bool:
    """Whether this creature is a plausible target for a fresh attack.

    "Not dead" was the first version, and the 2026-08-22 playtest showed why it is not
    enough: the only actor in the scene was the gatekeeper dying at 0 hp — dragged along
    from three scenes back — and every attack on the people the narration described was
    filled onto him. A man bleeding out on the ground is not the obvious reading of "I
    attack"; being the only body in the room must not make him one.
    """
    if int(getattr(actor, "hp", 1)) <= 0:
        return False
    return not any(actor.has_condition(c)
                   for c in ("dead", "dying", "unconscious", "stable"))


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
    if "give" in present:
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
    (re.compile(r"\b(?:forest|woods|woodland|treeline|trees)\b", re.I), "forest"),
    (re.compile(r"\b(?:jungle|rainforest)\b", re.I), "jungle"),
    (re.compile(r"\b(?:swamp|marsh|bog|fen)\b", re.I), "swamp"),
    (re.compile(r"\b(?:hills?|moor|downs|upland)\b", re.I), "hills"),
    (re.compile(r"\b(?:mountains?|peaks?|crags?)\b", re.I), "mountain"),
    (re.compile(r"\b(?:desert|dunes)\b", re.I), "desert"),
    (re.compile(r"\b(?:tundra|snowfield|icefield)\b", re.I), "tundra"),
    (re.compile(r"\b(?:coast|shore|beach|seafront)\b", re.I), "coast"),
    (re.compile(r"\b(?:plains?|grassland|steppe|meadows?)\b", re.I), "grassland"),
    (re.compile(r"\b(?:farmland|fields|orchards?)\b", re.I), "farmland"),
    (re.compile(r"\b(?:underground|caves?|caverns?|tunnels)\b", re.I), "underground"),
    (re.compile(r"\b(?:ruins?)\b", re.I), "ruins"),
    (re.compile(r"\b(?:city|town|streets)\b", re.I), "urban"),
)

# Going somewhere, not being somewhere: "I head for the treeline" travels, "I like these
# woods" does not, and "the forest looming ahead" is the GM's sentence rather than the
# player's. The verb and the ground must be in the same declaration.
_DEPARTS = re.compile(
    r"\b(?:head|heads|heading|make|makes|making|set out|setting out|strike out|walk"
    r"|walks|walking|travel|travels|travelling|traveling|leave|leaves|leaving|go|goes"
    r"|going|ride|rides|riding|march|marches|marching|flee|fleeing|run|running"
    r"|climb|climbs|climbing|descend|descends|push on|press on|make my way|slip out"
    r"|slip away)\b[^.!?]{0,60}?\b(?:for|to|towards?|into|out to|up to|down to)\b",
    re.I)


def inject_travel(raw_intents, player_text: str, scene) -> list:
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
    return raw_intents

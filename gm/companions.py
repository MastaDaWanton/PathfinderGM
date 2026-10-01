"""Companions heed what they are told — as themselves.

The owner's ruling, 2026-10-01: "I dont want control of companions they should take spoken
orders as their character dictates they would or would not and interpret those orders
according to their character as well." So there is no order button and no party-command
op. A companion — anybody holding `bond.travels-with-you` — hears what the player SAYS to
them, and their own turn decides, in character, whether and how to act on it.

This module gathers the two kinds of fact that decision needs and nothing else:

  * **what the player said to them** (`orders_for`): the player's own lines that name them
    or were spoken in a conversation they were in, newest first, a few at most. Read off
    the transcript and `Scene.conversation_log`, never inferred — an order the player did
    not give is not one;
  * **who they are** (`who_they_are`): the population record's trait words and how they
    show, the attitude step towards the player, and whether the player owns them (the
    constructs house rule: claimed, `bond.owned-by-you`, `devoted`). Words, never the axis
    scores or the regard number — no model sees a number (the third law).

What the turn may DO stays the engine's. The one mechanical refusal here is
`turning_on_the_party`: a companion's turn that strikes the player or the player's own
side is refused with the fix named, the same rule `Engine.struck_first` keeps for anybody
friendly — a friend who means harm has to stop being a friend first, and that is a change
the engine makes, never a slip of the prose. It exists because the creature examples the
companion's prompt used to share all aim at "pc".

Prior art, searched before building (2026-10-01):

  * Pathfinder's own answer is in Ultimate Campaign, "Controlling Companions"
    (aonprd.com/Rules.aspx?ID=1353): of its three models, GM control has the GM decide
    whether the creature is willing or able to do what the player wants, a sentient
    companion will not follow a suicidal order, and it warns that running a cohort as a
    second PC doubles the actions and brings choice paralysis. That is the owner's ruling
    in the book's words, and the reason there is no order button.
  * AD&D 1e's DMG checks a henchman's loyalty only when ordered into danger or a heroic
    act, and otherwise asks the DM to empathise and play them (1eonline.info/3dmg/
    loyalty.htm); Dungeon World's hirelings do what they are told unless it is
    dangerous, degrading or stupid (dungeonworldsrd.com). So the worked examples obey an
    ordinary order and weigh only a dangerous one against the character.
  * Ultima VII ran every companion on its own AI with no way to talk to it; reviews
    named that as what broke its combat (crpgaddict.blogspot.com, 2020-08). Dragon Age
    and Final Fantasy XII went the other way, with tactics scripts. Owlcat turned down
    scriptable companion AI for Kingmaker ("we'd play AI programming, not Pathfinder",
    gamebanshee.com). Both poles are refused here: no script, and no deaf companion.
  * Skyrim's followers turn down a crime in their own voice (en.uesp.net, Followers).
    A refusal is SAID — a narrate_only whose prose gives the reason — never a turn that
    silently does something else.

Deferred, not built (the research's strongest proposal, which the ruling leaves to the
owner): letting the ENGINE decide obedience for a dangerous order with 1e's own request
rule — Diplomacy's "make request" DCs by attitude, +10 for a dangerous favour
(d20pfsrd.com/skills/diplomacy) — with a helpful or devoted companion agreeing without
a check unless the order goes against their nature. The research also points to
"Too Good to be Bad" (arXiv 2511.04962): role-play fidelity drops for characters who
should refuse, so a model may lean towards obeying. The live replays measure how far.
"""
from __future__ import annotations

import re

from rules import states

# How many of the player's lines a companion's turn is shown. A handful: the newest
# order is what a turn acts on, and a long list of old ones reads as a standing script.
MAX_ORDERS = 3
# How far back in the transcript a line can still be an order this turn: the last few
# things the player typed, not the session.
RECENT_PLAYER_LINES = 6

_NOISE = {"the", "a", "an", "on", "of", "at", "in", "and", "or", "to", "with"}


def is_companion(actor) -> bool:
    return bool(actor is not None and not getattr(actor, "is_pc", False)
                and actor.has_state(states.TRAVELS_WITH_YOU))


def owned(actor) -> bool:
    return bool(actor is not None and actor.has_state(states.OWNED_BY_YOU))


def _name_words(name: str) -> set[str]:
    return {w for w in re.findall(r"[a-z']+", (name or "").lower())
            if w not in _NOISE and len(w) > 1}


def names_them(text: str, actor) -> bool:
    """Whether the player's line addresses or names this companion: every word of a
    one-word name ("Bob"), or the distinctive head of a descriptor ("the clockwork spy"
    is named by "spy")."""
    words = {w[:-2] if w.endswith("'s") else w.strip("'") for w in
             re.findall(r"[a-z']+", str(text or "").lower().replace("’", "'"))}
    mine = _name_words(getattr(actor, "name", ""))
    if not mine or not words:
        return False
    if len(mine) == 1:
        return bool(mine & words)
    head = (re.findall(r"[a-z']+", str(actor.name).lower()) or [""])[-1]
    return head in words or mine <= words


def orders_for(scene, ref: str, transcript=(), limit: int = MAX_ORDERS) -> list[str]:
    """What the player has lately said to this companion, newest first, at most `limit`.

    Two sources, because each misses what the other holds. The transcript has every
    line the player typed, including the reported ones ("I tell Bob to keep watch"),
    which the conversation log does not book — quoted words only, owner Q43 — and it is
    read for lines that NAME them. The conversation log has the quoted words said while
    they were the one being talked to (`to`, or among those in the conversation), which
    need not name them at all ("Keep watch." said to the one person you are talking to).
    """
    actor = (getattr(scene, "actors", {}) or {}).get(ref)
    if actor is None:
        return []
    from gm.prompts import CARRY_ON

    out: list[str] = []

    def add(line: str) -> None:
        line = " ".join(str(line or "").split())
        if not line or line == CARRY_ON:
            return
        low = line.lower()
        if any(low in o.lower() or o.lower() in low for o in out):
            return
        out.append(line)

    typed = [b for b in (transcript or []) if isinstance(b, dict)
             and b.get("who") == "player" and b.get("kind") != "aside"]
    for beat in reversed(typed[-RECENT_PLAYER_LINES:]):
        if names_them(beat.get("text", ""), actor):
            add(beat.get("text", ""))
    log = [e for e in (getattr(scene, "conversation_log", None) or [])
           if isinstance(e, dict) and e.get("who") == "you" and e.get("kind") == "line"]
    for e in reversed(log[-RECENT_PLAYER_LINES * 2:]):
        if e.get("to") == ref or ref in (e.get("among") or []):
            add(f'"{e.get("text", "")}"')
    return out[:limit]


# Words that put somebody to a task in reported speech: "I tell Bob to keep watch", "I ask
# the drover to fetch water", "I have Bob carry it". Within three words of the name.
_ORDERING = re.compile(
    r"\b(?:tell|tells|told|ask|asks|asked|order|orders|ordered|command|commands|"
    r"instruct|instructs|signal|signals|motion|motions|have|has|get|gets|send|sends|"
    r"direct|directs|bid|bids|wave|waves|nod|nods|gesture|gestures|whisper|whispers|"
    r"call|calls|shout|shouts|say|says)\b", re.I)


def addressed(scene, text: str) -> list[str]:
    """The companions the player's line speaks TO — never merely about.

    Detected in code (CLAUDE.md: detect mechanically, repair with a targeted call), two
    shapes: the name as a vocative inside the player's quoted words or opening their line
    ("Bob, keep watch", "Drover — the door!"), or a verb of telling a few words before the
    name in reported speech ("I tell Bob to keep watch"). "I look at Bob" is about Bob,
    and his answer is the narrator's ordinary business."""
    from gm import speech

    out = []
    raw = str(text or "")
    quoted = " ".join(speech.lines(raw))
    for ref, actor in (getattr(scene, "actors", {}) or {}).items():
        if not is_companion(actor) or actor.is_down:
            continue
        words = sorted(_name_words(actor.name), key=len, reverse=True)
        head = (re.findall(r"[a-z']+", str(actor.name).lower()) or [""])[-1]
        calls = [w for w in dict.fromkeys([head, *words]) if w]
        hit = False
        for w in calls:
            # At the start of the line, of a quotation, or of a sentence inside one:
            # "Bob, the door! Drover — stay close." calls on both.
            vocative = re.compile(rf"(?:^|[\"“'‘]\s*|[.!?]\s+)(?:hey\s+|oi\s+)?(?:the\s+)?"
                                  rf"{re.escape(w)}\s*[,!:—–-]", re.I)
            if vocative.search(raw.strip()) or vocative.search(quoted.strip()):
                hit = True
            for m in re.finditer(rf"\b{re.escape(w)}\b", raw, re.I):
                before = raw[max(0, m.start() - 40):m.start()]
                if _ORDERING.search(" ".join(before.split()[-4:])):
                    hit = True
            if hit:
                break
        if hit:
            out.append(ref)
    return out


def answer_facts(scene, actor, said: str, *, not_ready: bool = False) -> str:
    """What a companion's out-of-fight answer is told: who they are, who else is here by
    ref, and the player's words to them this turn.

    And what they have already told the player about their own life (gm/confide.py) —
    known to both, so nothing leaks — and, `not_ready`, that something personal is on
    their mind they will not say yet: asked "what is it?" after a hint, an answer told
    nothing would invent a want of its own."""
    from . import confide

    name = actor.name
    here = [f"{r} ({a.name})" for r, a in scene.actors.items()
            if r != actor.ref and not a.is_pc and scene.conscious(r)]
    pc = scene.pc()
    told = confide.told_line(scene, actor)
    return "\n".join([
        f"{name} ({actor.ref}) TRAVELS WITH the player. Who {name} is (fact): "
        f"{who_they_are(scene, actor)}",
        *([told] if told else []),
        *([f"{name} has something personal on their mind and is not ready to tell the "
           f"player what it is yet: they do not say what it is, and do not make "
           f"something up."] if not_ready else []),
        f"Here besides: {', '.join(here) if here else 'nobody'}"
        + (f"; the player is {pc.ref}." if pc is not None else "."),
        f"What the player just said: {' '.join(str(said or '').split())}",
        f"What does {actor.ref} do about it, as themselves?"])


def answers_on_the_page(text: str, answered) -> tuple[str, list[str]]:
    """Put back a companion's answer the beat left out: for each (actor, answer) whose
    actor the beat never names, the answer's own sentences go in before the closing
    question (or at the end). Returns (text, names put back)."""
    put = []
    for actor, said in answered or ():
        said = " ".join(str(said or "").split())
        if not said or names_them(text, actor):
            continue
        parts = re.split(r"(?<=[.!?])\s+", text.strip())
        if parts and parts[-1].endswith("?"):
            text = " ".join(parts[:-1] + [said, parts[-1]]).strip()
        else:
            text = f"{text.strip()} {said}".strip()
        put.append(actor.name)
    return text, put


def who_they_are(scene, actor) -> str:
    """The companion's character, as facts in words: owned or not, how they feel about
    the player, two or three trait words and how they show. Never a number."""
    from rules import attitude as attitude_mod, population as population_mod

    name = actor.name
    bits = []
    if owned(actor):
        bits.append(f"{name} belongs to the player, who claimed them, and is devoted to "
                    f"them: told plainly, {name} does it, as literally as it was said")
    else:
        mood = attitude_mod.of(actor)
        bits.append(f"{name} is {mood} towards the player — a friend who came along, "
                    f"not a servant, and free to say no")
    rec = population_mod.of_ref(scene, actor.ref)
    life = (rec or {}).get("life") or {}
    traits = [t for t in (life.get("traits") or []) if t][:3]
    if traits:
        bits.append(f"{name} is {', '.join(traits)}")
    shows = [s for s in (life.get("shows") or []) if s][:2]
    if shows:
        bits.append("in how they act: " + "; ".join(shows))
    # Their trade, which is half of "matched their background" (the owner's second
    # ruling, 2026-10-01): a carter swings a club the way a carter would.
    work = str(life.get("work_name") or "").strip()
    if work:
        bits.append(f"{name} is a {work} by trade")
    return ". ".join(bits) + "."


def foes_of(scene, ref: str) -> list[tuple[str, str]]:
    """Who the companion's side is fighting, standing, as (ref, name)."""
    sides = getattr(scene, "sides", None) or {}
    mine = next((s for s, refs in sides.items() if ref in refs), None)
    return [(r, scene.actors[r].name) for s, refs in sides.items() if s != mine
            for r in refs if r in scene.actors and scene.conscious(r)]


def turn_facts(scene, actor, orders: list[str]) -> str:
    """The block a companion's own turn is told, between its state and the question."""
    name = actor.name
    lines = [f"{name} TRAVELS WITH the player and came into this fight on the player's "
             f"side. Who {name} is (fact): {who_they_are(scene, actor)}"]
    foes = foes_of(scene, actor.ref)
    if foes:
        lines.append("The fight is against: "
                     + ", ".join(f"{r} ({n})" for r, n in foes) + ".")
    if orders:
        lines.append(f"What the player has said to {name}, newest first:")
        lines += [f"  - {o}" for o in orders]
        lines.append(f"{name} decides what to do with that as themselves: do it, do it "
                     f"their own way, or refuse. The engine decides what lands.")
    else:
        lines.append(f"The player has told {name} nothing this fight; {name} does what "
                     f"they would do.")
    return "\n".join(lines)


def on_their_own_turn(raw, scene, notes: list | None = None, addressed_refs=()):
    """In a fight, the PLAYER's plan does not act for a companion: their turn is their own.

    Measured on the companions replay, 2026-10-01: to "Bob, attack the thug! Drover, help
    me pin him down!" the player's plan wrote `move` for Bob and `attack` for the drover
    on the player's own turn — the drover struck before his own initiative came round,
    and Bob moved on the player's turn and again on his. That is the player controlling
    companions by speech, twice a round, and the decision the owner gave the companion
    (whether a timid drover closes with a thug at all) made by the planner instead. The
    words still reach them: `orders_for` reads the player's line on the companion's own
    turn. Out of a fight there is no turn of theirs to wait for, and the plan may act for
    a companion who would plausibly do it, as the brief's companion line asks.

    Only a companion who holds a place in the initiative; anybody else is untouched.

    And out of a fight, a companion the player's words were spoken TO (`addressed`): what
    they do about it is their own answer's to decide (`GMAgent.companion_answer`), not the
    planner's. Measured on the replay: "Drover, sneak up behind that thug and lift his
    purse" was planned as the drover's Stealth check, and the page said "He doesn't
    hesitate" of a companion rolled timid — the planner, asked to plan the whole turn,
    decided for him without reading who he is."""
    if not isinstance(raw, list):
        return raw
    actors = getattr(scene, "actors", {}) or {}
    if getattr(scene, "in_encounter", False):
        theirs = {r for r, _ in (getattr(scene, "initiative", None) or [])}
    else:
        theirs = set(addressed_refs or ())
    if not theirs:
        return raw
    kept = []
    for r in raw:
        ref = r.get("actor") if isinstance(r, dict) else None
        if (isinstance(ref, str) and ref in theirs
                and is_companion(actors.get(ref))):
            if notes is not None:
                notes.append(f"companion acts on their own turn: dropped "
                             f"{r.get('op')} by {actors[ref].name} from the player's plan")
            continue
        kept.append(r)
    return kept


# A reason that says the companion is NOT fighting: "they aren't fighting the thug", "too
# timid to engage", "stays back", "keeps their distance".
_NOT_FIGHTING = re.compile(
    r"(?:\b(?:not|never|without|instead\s+of|rather\s+than|too\s+\w+\s+to)|n[’']t)\s+"
    r"(?:\w+\s+){0,2}?(?:fight|fighting|attack|attacking|strike|striking|engage|"
    r"engaging|hit|hitting|close|closing)\b"
    r"|\b(?:stay|stays|staying|hang|hangs|hanging|hold|holds|holding|keep|keeps|keeping)"
    r"\s+(?:well\s+)?(?:back|clear|out\s+of\s+(?:it|reach|the\s+fight)|"
    r"(?:their|a|his|her|its)\s+(?:safe\s+)?distance)\b", re.I)


# A reason that says the companion is getting AWAY: "fleeing the immediate danger to fetch
# the watch", "bolts for the door", "backs off".
_GETTING_AWAY = re.compile(
    r"\b(?:flee|flees|fleeing|fled|run(?:s|ning)?\s+(?:off|away|for|to)|bolt(?:s|ing|ed)?|"
    r"escap(?:e|es|ing|ed)|retreat(?:s|ing|ed)?|back(?:s|ing|ed)?\s+(?:off|away)|"
    r"get(?:s|ting)?\s+away|fetch(?:es|ing)?|for\s+the\s+(?:door|exit)|"
    r"toward(?:s)?\s+the\s+(?:door|exit)|away\s+from)\b", re.I)


def move_against_its_reason(scene, ref: str, raw) -> str:
    """The refusal for a companion's `move` at a FOE whose own reason says they are getting
    away, or "".

    Measured on the companions replay, 2026-10-01: "Drover, run and fetch the watch!"
    came back `move` with the thug as its target "because they are fleeing the immediate
    danger to fetch the watch" — a move at somebody walks TOWARD them, and the engine
    closed the drover on the thug while the wind-up had him bolt for the exit."""
    if not isinstance(raw, list):
        return ""
    foes = {r for r, _ in foes_of(scene, ref)}
    for r in raw:
        if not isinstance(r, dict) or str(r.get("op", "")).lower() != "move":
            continue
        if (r.get("actor") or ref) != ref:
            continue
        params = r.get("params") if isinstance(r.get("params"), dict) else {}
        at = r.get("target") or params.get("toward")
        if at in foes and _GETTING_AWAY.search(str(r.get("because") or "")):
            name = scene.actors[at].name
            return (f"move: a move at {at} walks toward {name}, and the reason given — "
                    f"{str(r.get('because'))!r} — is getting away. Leaving the fight is "
                    f'{{"op": "narrate_only"}} saying so; a step back is a move with '
                    f'{{"zone": "far"}} and no target.')
    return ""


def attack_against_its_reason(ref: str, raw) -> str:
    """The refusal for a companion's `attack` whose own `because` says they are not
    fighting, or "".

    Measured on the companions replay, 2026-10-01: told "Drover, stay back and keep the
    crowd off me!", the drover's turn came back `attack` the thug "because they aren't
    fighting the thug, but are physically interceding to block the crowd" — the engine
    walked him onto the thug and struck. The reason is the companion's decision; the op
    was a slip of the hand, so the turn is sent back with that said."""
    if not isinstance(raw, list):
        return ""
    for r in raw:
        if not isinstance(r, dict) or str(r.get("op", "")).lower() != "attack":
            continue
        if (r.get("actor") or ref) != ref:
            continue
        why = str(r.get("because") or "")
        if _NOT_FIGHTING.search(why):
            return (f"attack: the reason given — {why!r} — says they are not fighting, "
                    f"and an attack is a blow. If they hold back, keep clear or stand "
                    f'guard, that is {{"op": "narrate_only"}} (or a move); if they do '
                    f"fight, say why they fight.")
    return ""


def attack_on_a_bystander(scene, ref: str, raw, orders=()) -> str:
    """The refusal for a companion's blow, in a fight, at somebody who is in neither side
    — unless the player's own words to them named that person — or "".

    Measured on the companions replay, 2026-10-01: told "keep the crowd off me", the
    drover's turn came back `attack` on the merchant watching from the side. Opening a
    second fight with an onlooker is the player's to order, never the companion's slip."""
    if not getattr(scene, "in_encounter", False) or not isinstance(raw, list):
        return ""
    sides = getattr(scene, "sides", None) or {}
    fighting = {r for refs in sides.values() for r in refs}
    actors = getattr(scene, "actors", {}) or {}
    for r in raw:
        if not isinstance(r, dict) or str(r.get("op", "")).lower() != "attack":
            continue
        if (r.get("actor") or ref) != ref:
            continue
        t = r.get("target")
        who = actors.get(t) if isinstance(t, str) else None
        if who is None or t in fighting or who.is_down:
            continue
        if any(names_them(o, who) for o in orders or ()):
            continue
        foes = foes_of(scene, ref)
        return (f"attack: {who.name} is not in this fight, and nobody told "
                f"{actors[ref].name} to go for them. The fight is against: "
                + (", ".join(f"{fr} ({fn})" for fr, fn in foes) or "nobody standing")
                + ". If they will not strike a foe, that is a narrate_only or a move.")
    return ""


def turning_on_the_party(scene, ref: str, raw) -> str:
    """The refusal for a companion's turn that strikes the player or their own side, or
    "" when it does not. Asked of the raw plan before it runs."""
    actor = (getattr(scene, "actors", {}) or {}).get(ref)
    if not is_companion(actor) or not isinstance(raw, list):
        return ""
    sides = getattr(scene, "sides", None) or {}
    mine = next((refs for refs in sides.values() if ref in refs), None) or []
    pc = scene.pc() if hasattr(scene, "pc") else None
    party = set(mine) | ({pc.ref} if pc is not None else set())
    party.discard(ref)
    for r in raw:
        if not isinstance(r, dict) or str(r.get("op", "")).lower() not in ("attack", "cast"):
            continue
        if (r.get("actor") or ref) != ref:
            continue
        targets = r.get("target")
        targets = targets if isinstance(targets, list) else [targets]
        aim = (r.get("params") or {}).get("at") if isinstance(r.get("params"), dict) else None
        hit = [t for t in [*targets, aim] if isinstance(t, str) and t in party]
        if hit:
            who = scene.actors[hit[0]]
            foes = foes_of(scene, ref)
            return (f"{actor.name} travels with the player and does not strike "
                    f"{'the player' if who.is_pc else who.name}, who is on their side. "
                    + (f"The fight is against: {', '.join(f'{r} ({n})' for r, n in foes)}. "
                       if foes else "")
                    + f"If {actor.name} will not do as they were told, that is a "
                      f'{{"op": "narrate_only"}} saying so.')
    return ""


# --- the manner of what they do -------------------------------------------------------
#
# The owner's ruling, 2026-10-01 (the second): "they can comply but it should be narrated
# that they did so in a way that was timid and matched their background." Obedience stays
# the companion's own decision (no engine gate); HOW they do whatever they do is the
# page's business, and it is held to it here the way every quality fix that held was
# (CLAUDE.md): told as facts, demonstrated in the examples, then DETECTED in code — a cue
# lexicon per temperament — and repaired with one targeted call when it is missing.
#
# The lexicon is derived from content/people/personality.json: each pole's `shows` line
# read for the bodily habit it implies in a deed ("keeps a door at their back" → glances
# at the way out, backs off), plus the words a page actually writes for it. The trait
# words themselves are NOT cues — "the timid drover" is a label, not a manner (CoMPosT,
# EMNLP 2023; `population.traits_named` counts labels apart). A pole with no entry here
# owes nothing in a deed — generous, tight-fisted, trusting, guarded, irreverent, untidy,
# humble are about money, belief and talk, and asking a sword-stroke to show thrift
# would make the repair invent a habit. A companion with no voiced trait owes nothing.

DEVOTED = "devoted"

_MANNER_SOURCE = {
    "timid": (
        r"hesitat\w*|trembl\w*|shak(?:y|ily|ing|es|en)|quak\w*|flinch\w*|falter\w*|"
        r"nervous\w*|swallow\w*|blanch\w*|white-knuckle\w*|winc(?:e|es|ed|ing)|"
        r"cower\w*|cring\w*|tentativ\w*|gingerly|wide-eyed|stammer\w*|stutter\w*|"
        r"whimper\w*|half-hearted\w*|reluctan\w*|unwilling\w*|"
        r"edg(?:e|es|ing|ed) (?:forward|closer|in|back|away|up)|"
        r"eyes? (?:half[- ]shut|screwed shut|squeezed shut|shut tight)|"
        r"glanc\w* (?:at|toward|towards|back at|over at) the (?:door|exit|way out|street|road|gate)|"
        r"back(?:s|ing|ed)? (?:away|off)|from behind (?:you|your)|behind your (?:back|shoulder)|"
        r"fear\w*|frighten\w*|scared|terrified|afraid|"
        r"heart (?:pounding|hammering|racing|in (?:his|her|their) throat)|"
        r"breath\w* (?:ragged|shallow|hitch\w*|catch\w*)|sweat\w*|clums(?:y|ily)|"
        r"wild(?:ly)? (?:swing|swings|swinging|flail\w*)|flail\w*|squeak\w*|"
        r"pale(?:s|d)?|white-faced|(?:his|her|their) (?:hands|knees|voice) (?:shake|shook|shaking)|"
        # Added after scoring the first replay by hand (2026-10-01): 5 of 5 undirected
        # timid wind-ups showed it — "eyes darting toward the nearest exit", "ready to
        # bolt", "knuckles white", "huddling close" — and the first lexicon caught 1.
        r"dart(?:s|ing|ed)?|bolt(?:s|ing)?|(?:nearest|an?) (?:exit|way out|escape)|"
        r"escape route|ready to (?:run|flee|bolt)|make a run for it|"
        r"knuckles? (?:white|whiten\w*)|wide-eyed|eyes? (?:go |went )?wide|"
        r"eyes widen\w*|wide eyes|huddl\w*|stays? (?:low|close behind)|half-step back"),
    "bold": (
        r"grin\w*|without (?:a (?:moment'?s |second'?s )?)?(?:hesitation|pause|a second thought)|"
        r"eager\w*|relish\w*|laugh\w*|whoop\w*|headlong|fearless\w*|charg(?:e|es|ed|ing)|"
        r"throws? (?:himself|herself|themselves|themself)|straight (?:at|for|in|into)|"
        r"first (?:in|to|into)|swagger\w*|gleeful\w*|delight\w*|"
        r"bar(?:e|es|ed|ing) (?:his|her|their) teeth|roar\w*|"
        r"(?:doesn't|does not|don't|never) (?:hesitate|wait|slow|flinch)|savage joy|"
        r"lunges? in|wades? in|dives? in"),
    "hot_tempered": (
        r"snarl\w*|curs(?:e|es|ed|ing)|swear\w*|swore|spit(?:s|ting)?|spat|furious\w*|"
        r"fury|rage\w*|raging|red-faced|bellow\w*|roar\w*|yell\w*|temper|savage\w*|"
        r"angr\w*|anger|through (?:gritted|clenched) teeth|growl\w*|hiss\w*"),
    "placid": (
        r"calm\w*|steady|steadily|unhurried|evenly|patient\w*|without fuss|unruffled|"
        r"level (?:voice|gaze|look|eyes)|measured|deliberate\w*|composed|"
        r"(?:no|without) (?:haste|hurry)|unbothered|as if it were (?:nothing|weather|chores?)"),
    "kind": (
        r"winc(?:e|es|ed|ing)|apolog\w*|sorry|gentle|gently|grimac\w*|piti\w*|pity|"
        r"regret\w*|(?:can't|cannot|can not) bear|merc(?:y|iful)|"
        r"pull\w* (?:the|his|her|their) (?:blow|punch|swing|stroke)|flat of|"
        r"(?:look|looks|looking|glanc\w*) away|hates? (?:this|it|doing)|softly|"
        r"careful (?:not|to)|(?:to|not to) (?:kill|hurt)|knock (?:him|her|them) down"),
    "hard": (
        r"cold\w*|flat(?:ly)?|without (?:a )?(?:flicker|pity|mercy|expression|feeling)\w*|"
        r"efficient\w*|businesslike|indifferen\w*|unmoved|blank\w*|hard-eyed|clinical\w*|"
        r"grim\w*|impassive\w*|expressionless"),
    "reserved": (
        r"silent\w*|silence|without a (?:word|sound)|wordless\w*|quiet(?:ly)?|"
        r"says nothing|tight-lipped|a single (?:nod|word|glance)|nod(?:s|ded|ding)?|mute\w*"),
    "gregarious": (
        r"chatter\w*|calls? out|calling out|laugh\w*|jok\w*|jest\w*|cheer\w*|banter\w*|"
        r"shout\w*|yell\w*|talk(?:s|ing)|running commentary|whoop\w*"),
    "proud": (
        r"flourish\w*|preen\w*|boast\w*|announc\w*|chin (?:up|high|raised|lifted)|"
        r"(?:make|making|makes) sure you (?:see|saw|notice)|swagger\w*|theatrical\w*|"
        r"show(?:s|ing)? off|with a bow|smug\w*|triumphant\w*|"
        r"(?:glance|look)\w* (?:back )?(?:at you|to you) (?:to see|for)"),
    "suspicious": (
        r"wary|warily|watch\w* (?:his|her|their|the \w+'s) hands|narrow\w*|sidelong|"
        r"squint\w*|distrust\w*|eyes? (?:never leav\w*|fixed on)|keeps? (?:an eye|one eye)|"
        r"guarded\w*"),
    "blunt": r"flat(?:ly)?|bluntly|plain(?:ly)?|without ceremony|no ceremony|straight out",
    "orderly": (
        r"precis\w*|neat\w*|methodical\w*|exact\w*|tid(?:y|ily)|"
        r"squar\w* (?:up|his|her|their)|adjust\w*|straighten\w*|careful\w*|measured"),
    "devout": (
        r"pray\w*|gods?|bless\w*|holy|saint\w*|sign of|invok\w*|invocation|amulet"),
    # The claimed construct (the house rule's `devoted`): obedience done literally, like a
    # mechanism. Its body is part of its manner — joints, gears, a click — so those count.
    DEVOTED: (
        r"without a (?:sound|word)|silent\w*|silence|mechanical\w*|precis\w*|exact\w*|"
        r"click\w*|whirr\w*|tick(?:s|ing)|unblinking|without (?:hesitation|pause|a pause)|"
        r"like a (?:key|machine|clock|piston|lock)|literal\w*|gears?|joints?|metal\w*|"
        r"clockwork|smooth\w*|instant\w*|obedien\w*|to the letter|as (?:it was|it is) told|"
        r"at once|servos?|ratchet\w*|grind\w*|iron|brass|steel|hinge\w*|"
        r"no (?:hesitation|pause|expression)|expressionless|unhesitating\w*"),
}
MANNER_CUES = {pole: re.compile(r"\b(?:" + src + r")\b", re.I)
               for pole, src in _MANNER_SOURCE.items()}
# Speech is the manner of the talkative and the blunt: a quotation in their sentences
# counts for them.
_SPOKEN_POLES = frozenset({"gregarious", "blunt"})
# "doesn't hesitate" is not a hesitation, "without fear" is not fear. A cue whose own
# words begin with the negation ("without a sound") is the cue and is kept.
_NEGATED = re.compile(r"(?:\bwithout|\bno|\bnot|\bnever|\bnor|n[’']t)\s+(?:\w+\s+){0,1}$", re.I)


def _pole_of_word(word: str) -> str:
    """The personality pole a trait word belongs to ("timid" → timid, "warm" → kind)."""
    from rules import lives

    w = str(word or "").strip().lower()
    for axis in lives.tables()["personality"]:
        for side in ("low", "high"):
            pole = axis[side]
            if w == pole["id"] or w in [x.lower() for x in pole.get("words") or ()]:
                return pole["id"]
    return ""


def dominant_pole(scene, actor) -> str:
    """The temperament a companion's deed owes the page, or "" when it owes none.

    A claimed construct is DEVOTED. Anybody else: the first of their voiced trait words
    (the loudest first, as `lives.roll` orders them) whose pole has a cue lexicon. Read
    from the trait WORDS, not `trait_ids`: the words are what the brief and the turn are
    told, so the check holds the page to what the model was shown."""
    if not is_companion(actor) and not owned(actor):
        return ""
    if owned(actor):
        return DEVOTED
    from rules import population as population_mod

    life = ((population_mod.of_ref(scene, actor.ref) or {}).get("life") or {})
    for word in life.get("traits") or ():
        pole = _pole_of_word(word)
        if pole in MANNER_CUES:
            return pole
    for pole in life.get("trait_ids") or ():
        if pole in MANNER_CUES:
            return pole
    return ""


_PRONOUN_START = re.compile(r"^\W*(?:he|she|they|it|his|her|their|its)\b", re.I)
_CONSTRUCT_WORDS = re.compile(r"\b(?:machine|construct|automaton|clockwork)\b", re.I)


def _names_or_is(sentence: str, actor) -> bool:
    if names_them(sentence, actor):
        return True
    return owned(actor) and bool(_CONSTRUCT_WORDS.search(sentence or ""))


def their_sentences(text: str, actor) -> list[str]:
    """The sentences of a passage about this companion: those that name them (a claimed
    construct also by "the machine"), and the pronoun run straight after one."""
    from . import narration as narration_mod

    out: list[str] = []
    following = False
    for s in narration_mod._sentences(text or ""):
        if _names_or_is(s, actor):
            out.append(s)
            following = True
        elif following and _PRONOUN_START.search(s):
            out.append(s)
        else:
            following = False
    return out


def manner_cues(text: str, pole: str) -> list[str]:
    """The cue words for `pole` found in `text`, negated ones left out."""
    pat = MANNER_CUES.get(pole)
    if pat is None or not text:
        return []
    from . import speech

    bare = speech.unquoted(text) if pole not in _SPOKEN_POLES else text
    found = []
    for m in pat.finditer(bare):
        if not re.match(r"(?:without|no|never|doesn't|does not|don't)\b", m.group(0), re.I) \
                and _NEGATED.search(bare[max(0, m.start() - 24):m.start()]):
            continue
        found.append(m.group(0).lower())
    if pole in _SPOKEN_POLES and speech.spans(text):
        found.append("(speaks)")
    return found


def shows_manner(text: str, actor, pole: str, *, whole: bool = False) -> bool:
    """Whether the companion's part of `text` carries a cue of `pole`. True when the pole
    owes nothing. `whole`: the passage is all theirs (their own fight turn), so a
    sentence about them that never names them still counts."""
    if not pole or pole not in MANNER_CUES:
        return True
    mine = their_sentences(text, actor)
    scope = " ".join(mine) if mine and not whole else (text if whole else "")
    return bool(manner_cues(scope, pole))


def manner_line(scene, actor, *, ordered: bool, op: str = "") -> str:
    """How this companion does what they do, as facts in words for a prose call: their
    nature and how it shows, their trade and people, how they feel about the player, and
    whether the deed was the player's order and against their grain. Never a number."""
    from rules import attitude as attitude_mod, population as population_mod
    from rules import faces as faces_mod

    name = actor.name
    pole = dominant_pole(scene, actor)
    bits = []
    if owned(actor):
        bits.append(f"{name} belongs to the player and is devoted: it does what it is told "
                    f"exactly, like a mechanism, without fear or flourish")
    else:
        life = ((population_mod.of_ref(scene, actor.ref) or {}).get("life") or {})
        traits = [t for t in (life.get("traits") or []) if t][:2]
        shows = [s for s in (life.get("shows") or []) if s][:2]
        if traits:
            bits.append(f"by nature {name} is {' and '.join(traits)}"
                        + (f" — {'; '.join(shows)}" if shows else ""))
        work = str(life.get("work_name") or "").strip()
        people = faces_mod.people_of(str(getattr(actor, "appearance", "") or ""))
        if work or people:
            bits.append(f"{name} is " + (f"a {work} by trade" if work else "")
                        + (" and " if work and people else "")
                        + (f"one of the {people}" if people else "")
                        + ", and does things the way that life taught them")
        bits.append(f"{name} is {attitude_mod.of(actor)} towards the player")
    if ordered and reluctant(pole, op):
        bits.append(f"{name} does this ONLY because the player told them to, against "
                    f"their own nerve — they do it, and it shows how little they want to")
    elif ordered:
        bits.append(f"{name} does this because the player told them to")
    else:
        bits.append(f"nobody told {name} to: this is their own doing")
    return (f"HOW {name} DOES IT (fact — show it in the verbs and the small details of "
            f"what they do; never name the trait): " + "; ".join(bits) + ".")


# The deeds a timid or soft-hearted companion does against the grain when told to.
_HARD_FOR_THE_TIMID = frozenset({"attack", "cast", "move", "check", "use_item"})


def reluctant(pole: str, op: str) -> bool:
    """Whether an ordered deed goes against this temperament: a timid one told to fight,
    sneak or close in; a soft-hearted one told to strike."""
    op = str(op or "").lower()
    return (pole == "timid" and op in _HARD_FOR_THE_TIMID) or (pole == "kind" and op == "attack")


# What the deed IS on the page: how a blow went and who it touched. A manner rewrite may
# change how a thing is done and never these. HOW they get there — steps forward, lunges,
# edges in, charges — is the manner itself and may change: the first cut held those too,
# and 4 of 5 repairs of a kind drover's ordered swing were thrown away for turning
# "steps forward" into "edges forward" (replay, 2026-10-01).
_ACT_WORDS = re.compile(
    r"\b(?:hit|hits|strike|strikes|struck|swing|swings|swung|stab\w*|slash\w*|"
    r"miss|misses|missed|block\w*|parr\w*|fall|falls|fell|drop\w*|"
    r"grab\w*|throw\w*|threw|shove\w*|trip\w*|disarm\w*|flee\w*|fled|"
    r"kill\w*|dead|dies|wound\w*|blood\w*|lands|landed|connect\w*|glanc\w* off|"
    r"crack\w*|knock\w*|stagger\w*|crumpl\w*|retreat\w*|run(?:s|ning)? away|ran away)\b",
    re.I)
_LANDING = re.compile(
    r"\b(?:hits|struck|lands|landed|connect\w*|wound\w*|blood\w*|kill\w*|dead|dies|"
    r"crumpl\w*|stagger\w*|falls|fell|knock\w* (?:him|her|them) (?:down|flat|out))\b", re.I)


def _stems(words) -> set[str]:
    return {w.lower()[:4] for w in words}


def act_kept(old: str, new: str, actor, people=()) -> str:
    """Why a manner rewrite of `old` into `new` changed the act, or "" when it did not:
    the companion still named, nobody added or lost, every deed word kept, no blow landed
    that the old sentence did not land, no number, about the same length."""
    if not new or not new.strip():
        return "empty"
    if not 0.6 <= len(new) / max(1, len(old)) <= 2.4:
        return "length"
    if re.search(r"\d", new) and not re.search(r"\d", old):
        return "a number"
    if _names_or_is(old, actor) and not _names_or_is(new, actor):
        return f"{actor.name} is no longer named"
    for who in people or ():
        if who is actor:
            continue
        if names_them(old, who) != names_them(new, who):
            return f"{who.name} added or lost"
    lost = _stems(_ACT_WORDS.findall(old)) - _stems(_ACT_WORDS.findall(new))
    if lost:
        return "the deed changed (" + ", ".join(sorted(lost)) + ")"
    landed = _stems(_LANDING.findall(new)) - _stems(_LANDING.findall(old))
    if landed:
        return "lands what the old one did not (" + ", ".join(sorted(landed)) + ")"
    # A pulled blow is the `lethality` rule's to decide, not a manner: measured on the
    # replay, a repair wrote "pull the blow" over a lethal swing.
    if _PULLED.search(new) and not _PULLED.search(old):
        return "pulls a blow the engine did not"
    return ""


_PULLED = re.compile(r"\b(?:pull\w* (?:the|his|her|their|a) (?:blow|punch|swing|stroke)|"
                     r"flat of|non-?lethal|to knock (?:him|her|them) (?:down|out))\b", re.I)


# --- speaking up, unasked ----------------------------------------------------------------
#
# The owner, 2026-10-01: "they should also interject their opinions on the things going on
# or the places we go." WHEN is decided here, in code, from what the engine knows — never
# by asking a model whether now is a good moment — and WHAT is the model's
# (`GMAgent.companion_interject`), checked before it reaches the page.
#
# Prior art (researched 2026-10-01, sources in tests/test_companions_manner.py):
#   * Dragon Age: Inquisition left party banter to chance, about one chance in ten to
#     fifteen minutes; players reported anything from twelve in a hundred hours to three
#     an hour, and patch 3 made it "less random to prevent extra-long periods where no
#     conversations would occur" (BioWare's own patch notes). So no dice here: a cadence
#     that cannot starve and cannot flood.
#   * Valve's response rules (Ruskin, GDC 2012): a line fires on criteria (what just
#     happened, who is speaking) and writes back a memory with an expiry so a running gag
#     is not played twice too close — the shape `population.quirk_due` already has here.
#     The memory is the conversation log itself: an interjection is booked there as
#     their speech with `src: "interject"`, and the cadence is read back off it, so there
#     is no second store to drift from what was said.
#   * Half-Life 2: Episode One's developer commentary: nagging and unsolicited hints made
#     players "hate Alyx" within minutes and were cut; a reaction that stepped aside was
#     liked. So an interjection is an opinion, never advice (`interjection_refusal`).
#   * Dragon Age: Inquisition also suppressed banter in combat and in conversation, and
#     Divinity: Original Sin 2 players modded out companions interrupting dialogue. So
#     never in a fight, and never while the player is talking to somebody else — except
#     on the beat they arrive somewhere, which ends a conversation anyway.

# Player turns between unprompted remarks when nothing in particular happened — the
# quirk's own cadence (`population.QUIRK_EVERY`), for the same reason: a small model
# cannot count "now and then", and every beat would be a tic.
INTERJECT_EVERY = 5
# And never closer than this, whatever happened: an arrival straight after a remark
# waits a turn.
INTERJECT_GAP = 2

_DEATH = re.compile(r"\b(?:dies|died|is dead|are dead|killed|stops moving|falls dead)\b", re.I)
# A remark that tells the player what to do — Alyx's lesson: "we should", "you ought",
# "let's" at the head of a clause inside their words.
_ADVICE = re.compile(
    r"(?:^|[.!?,;]\s*|[\"“]\s*)(?:we|you)\s+(?:should|ought|need to|must|have to|"
    r"had better|'d better)\b|(?:^|[.!?]\s*|[\"“]\s*)let'?s\b|\bwhy don't (?:we|you)\b",
    re.I)


def _interjections(scene) -> list[dict]:
    """Every unasked line a companion has spoken: their remarks, and their confidings
    (gm/confide.py), which hold the remark's gap too — a confession and an opinion on the
    weather back to back is two remarks too close."""
    return [e for e in (getattr(scene, "conversation_log", None) or [])
            if isinstance(e, dict) and e.get("src") in ("interject", "confide")]


def _turns_since(transcript, beat) -> int:
    """Player turns typed after transcript index `beat` (a big number when never)."""
    if beat is None:
        return 10 ** 6
    return sum(1 for b in list(transcript or [])[int(beat) + 1:]
               if isinstance(b, dict) and b.get("who") == "player")


def least_recently_heard(scene, refs) -> str:
    """Whose turn it is to speak: the companion longest silent in the conversation log
    (anybody never heard first), ties in the order given. Fair by construction, so one
    talkative companion cannot take every remark."""
    refs = list(refs)
    last: dict[str, int] = {}
    for e in getattr(scene, "conversation_log", None) or []:
        if isinstance(e, dict) and e.get("who") in refs:
            last[e["who"]] = int(e.get("n") or 0)
    return min(refs, key=lambda r: (last.get(r, -1), refs.index(r)))


def notable(outcomes) -> str:
    """What happened this beat worth a companion's opinion, as the tell, or "": a death, a
    lie told or seen through, somebody talked round, a deal, somebody joining or leaving,
    a refusal the world gave the player."""
    for o in outcomes or ():
        tell = str(getattr(o, "tell", "") or "")
        op = str(getattr(o, "op", "") or "")
        if not tell:
            continue
        if _DEATH.search(tell):
            return tell
        if op in ("buy", "sell", "company", "quest", "found", "loot"):
            return tell
        # Read off the tell's own words, never the effect records — the third law's
        # ratchet (tests/test_three_laws.py) keeps gm/ to the tells: a lie believed or
        # seen through, and a mind changed ("is now friendly", `regard_said`).
        if op == "check" and re.search(
                r"\b(?:believes it|sees through it|(?:is|are) now \w+|warms? to|"
                r"cools? towards?)\b", tell):
            return tell
        if str(getattr(o, "status", "") or "") == "refused":
            return tell
    return ""


def arrived_at(scene, moved: bool) -> dict | None:
    """The place the party walked into this beat, or None: {"id", "first"}. `moved` is
    the caller's (the view reads it off the travel outcome, as its `already_there`
    check does). `first` is a first visit — the place stands LAST in the order first
    stood in (`Scene.been`). A return to the newest place after a detour reads as a
    first visit: a known blind spot, and the cost is one remark that sounds new."""
    at = str(getattr(scene, "at", "") or "")
    if not moved or not at:
        return None
    been = scene.places_been() if hasattr(scene, "places_been") else []
    return {"id": at, "first": bool(been) and been[-1] == at}


def interjection_due(scene, transcript, outcomes, *, answered=(), talking=(),
                     moved: bool = False) -> dict | None:
    """Whether a companion speaks up this beat, and who and why: {"ref", "reason",
    "about", "arrived"} or None. Decided in code:

      * never in a fight, never while a roll waits, never on a beat a companion has
        already answered the player (they had their say);
      * never while the player is in conversation with somebody who is not a companion,
        unless the party just arrived somewhere;
      * never within INTERJECT_GAP turns of the last one;
      * then: arriving somewhere; else something notable (`notable`); else a quiet
        stretch of INTERJECT_EVERY turns since the last one.
    The speaker is the companion least recently heard."""
    if getattr(scene, "in_encounter", False) or getattr(scene, "awaiting", None):
        return None
    if answered:
        return None
    party = [r for r, a in (getattr(scene, "actors", {}) or {}).items()
             if is_companion(a) and not a.is_down and scene.conscious(r)]
    if not party:
        return None
    arrived = arrived_at(scene, moved)
    if not arrived and any(not is_companion(a) for a in talking or ()):
        return None
    marks = _interjections(scene)
    since = _turns_since(transcript, marks[-1].get("beat") if marks else None)
    if since < INTERJECT_GAP:
        return None
    event = notable(outcomes)
    if arrived:
        reason = "arrived"
    elif event:
        reason = "event"
    elif since >= INTERJECT_EVERY:
        reason = "moment"
    else:
        return None
    return {"ref": least_recently_heard(scene, party), "reason": reason,
            "about": event, "arrived": arrived}


def interject_facts(scene, actor, due: dict, *, place=None, beat: str = "") -> str:
    """What the remark's call is told: who speaks (in words), what it is about — the place
    by its real name and the world's own line about it, the turn's tell, or the beat's
    last sentences — and who is here by name. Never a number, never a ref.

    Never their wants, goal or hobby. The companions-manner lane put the want into one
    remark in three; the owner overruled it on 2026-10-01 ("they shouldnt just blurt out
    personal feelings without some kind of warm up"), and a companion's own life now
    reaches the page only through gm/confide.py, gated by their attitude."""
    from . import narration as narration_mod

    name = actor.name
    who = manner_line(scene, actor, ordered=False).split(": ", 1)[-1].rstrip(".")
    # "nobody told them to" is about deeds; a remark needs only who they are.
    who = re.sub(r";\s*nobody told .*$", "", who)
    about_place = str(getattr(place, "about", "") or "").strip()
    if due.get("reason") == "arrived" and place is not None:
        about = (f"the party has just arrived at {place.name}"
                 + (f" — {about_place}" if about_place else "")
                 + (f". {name} has never been here before."
                    if (due.get("arrived") or {}).get("first")
                    else f". {name} has been here before."))
    elif due.get("reason") == "event":
        about = f"what just happened — {due.get('about')}"
    else:
        tail = " ".join(narration_mod._sentences(beat)[-2:]) if beat else ""
        about = f"a quiet moment — {tail}" if tail else "a quiet moment"
    here = [a.name for a in scene.actors.values() if not a.is_pc and scene.conscious(a.ref)]
    return (f"Who speaks: {name} (fact): {who}.\nWhat it is about: {about}\n"
            f"People here: {', '.join(here) or name}.")


def interjection_refusal(line: str, actor, known: set[str], *, limit: int = 0) -> str:
    """Why a remark cannot go on the page, or "" when it can. `limit`: the longest it
    may run (the remark's own by default; a confiding share is allowed more)."""
    from . import narration as narration_mod
    from . import speech
    from .prompts import INTERJECT_MAX_CHARS

    if not line:
        return "is empty"
    if len(line) > (limit or INTERJECT_MAX_CHARS):
        return "is too long"
    if not speech.spans(line):
        return "has no words of theirs in quotation marks"
    if not _names_or_is(line, actor):
        return f"does not say it is {actor.name} speaking"
    if re.search(r"\d", line):
        return "has a number in it"
    bare = speech.unquoted(line)
    if "?" in bare or narration_mod.HAND_BACK.lower() in line.lower():
        return "hands the turn back"
    said = " ".join(speech.lines(line))
    if _ADVICE.search(said):
        return "tells the player what to do — say what they think or feel instead"
    invented = narration_mod.invented_names(line, known)
    if invented:
        return "names " + ", ".join(invented) + ", who is not here"
    return ""

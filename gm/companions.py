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


def answer_facts(scene, actor, said: str) -> str:
    """What a companion's out-of-fight answer is told: who they are, who else is here by
    ref, and the player's words to them this turn."""
    name = actor.name
    here = [f"{r} ({a.name})" for r, a in scene.actors.items()
            if r != actor.ref and not a.is_pc and scene.conscious(r)]
    pc = scene.pc()
    return "\n".join([
        f"{name} ({actor.ref}) TRAVELS WITH the player. Who {name} is (fact): "
        f"{who_they_are(scene, actor)}",
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

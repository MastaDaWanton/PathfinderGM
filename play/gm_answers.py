"""Out of character: the engine answering a question about itself.

The player asked for this in as many words, and the honest answer at the time was that
the app had no door for it. Every multiplayer text tradition has one — Diku and its
descendants ship an `ooc` channel, MUSH has `page` and `@emit`, and they exist because
somebody at the table always needs to ask about the game without their character doing
anything. This app had exactly one way out of the fiction, `/cheat`, and a cheat makes
a statement true rather than answering a question.

Three rules, and they are what make this worth having at all:

**The engine first, and only when it is sure.** Every line below is read off the engine,
which owns the state, or out of the rulebooks by name. A question answered by a language
model is a guess with good grammar — a recent benchmark of narrative consistency has the
best model contradicting an established fact within twenty turns in most runs — and the
whole point of asking the GM is to get the truth rather than the fiction's version of it.
What the engine does NOT hold — the town, its council, a name from the world — goes to
the model in `views._ask_the_gm`, grounded in the world's own record (docs/gm-questions.md)
and labelled as the GM's word rather than the engine's.

Measured live 2026-09-18, ten questions through `/api/say`, before the matching below was
tightened: nine were answered here and never reached the record — "is there a temple
here" got the Temple Sword, "who runs this town" the Town Watcher (a creature whose name
begins with "town"), "what do people around here eat" the roster, and "how many hit points
do I have" the pack, because "have" was a carrying word. A door that answers the wrong
question is worse than one that says nothing: it stops the right answer being sought.

**Nothing changes, and no time passes.** Asking is not a turn. Nothing is rolled, the
clock does not move, and no NPC gets to act because you wanted to check your own hit
points.

**It never enters the model's history.** An out-of-character exchange in the
conversation the narrator reads is a fact about the world as far as the narrator is
concerned, and it will write it into the fiction. The answer goes on the page and
stops there.

`gm_view` on the Rulesets bench decides whether the answer also carries the machine
layer — the ops the last turn proposed, what the repairs did, what the context budget
cut. That house rule existed with no reader anywhere in the app until this file.
"""
from __future__ import annotations

import re

from rules import cards as cards_mod
from rules import houserules, states

# What a question is about, matched as a PHRASE. These used to be bare word lists —
# "who", "have", "people", "day" — on the theory that a door that only opens for an
# exact word is a door people stop using. Measured live (module docstring), the bare
# words opened the door on nearly every question: "who runs this town" is not "who is
# here", and "how many hit points do I have" is not about the pack. The phrases are the
# ways people actually ask about the state, and a question that fits none of them is
# about the world, which is a different answerer's.
TOPICS = {
    "where": re.compile(
        r"\b(?:where (?:am i|are we|is this|do i stand|can i go|could i go)|"
        r"what (?:place|room|building) (?:is this|am i in)|exits?|which way (?:out|is)|"
        r"the map|what(?:'s|’s| is) (?:outside|nearby|around me|this place))\b", re.I),
    "who": re.compile(
        r"\b(?:who(?:'s|’s| is| else is| all is)?\s+(?:all\s+|else\s+)?"
        r"(?:here|around|present|nearby|with me|with us|standing here|"
        r"in (?:the|this) (?:room|scene|place))|"
        r"(?:people|everyone|anyone|npcs?) (?:here|around me|present|nearby|in the room)|"
        r"the (?:cast|roster)|who did i (?:meet|see))\b", re.I),
    "me": re.compile(
        r"\b(?:hit points?|hp|health|how (?:hurt|wounded|badly hurt|injured) am i|"
        r"am i (?:hurt|wounded|dying|ok|okay|alright|bleeding|poisoned|sick)|"
        r"how am i (?:doing|holding up)|"
        r"my (?:conditions?|states?|effects|buffs|wounds|sheet|status)|"
        r"what(?:'s|’s| is) wrong with me|what conditions)\b", re.I),
    "carrying": re.compile(
        r"\b(?:what am i carrying|what do i (?:have|carry|own)(?: on me| with me)?|"
        r"inventory|my (?:pack|bag|satchel|gear|items|belongings|purse|coins?|money|gold)|"
        r"how much (?:gold|money|coin) (?:do i have|have i got|is in my purse)|"
        r"what(?:'s|’s| is) in my (?:pack|bag|satchel|pockets?))\b", re.I),
    "quests": re.compile(
        r"\b(?:quests?|objectives?|my tasks?|what am i (?:supposed|meant) to (?:do|be doing)|"
        r"what (?:jobs?|tasks?|work) (?:do|have) i|open (?:jobs|tasks)|"
        r"what have i (?:agreed|promised) to do)\b", re.I),
    "time": re.compile(
        r"\b(?:what time|time is it|how late|what (?:day|hour) is it|the (?:world )?clock|"
        r"what day|how long (?:has it been|have i been here|since))\b", re.I),
    # "what happened" only when it is the whole question or about the last turn: "what
    # happened in the war with the flightless" is history, and the record's to answer.
    "last": re.compile(
        r"\b(?:what just happened|what happened(?:\s*[?.!]*\s*$| (?:there|then|to me|"
        r"last turn|on (?:my|the) last turn))|last turn|"
        r"why did (?:that|it|i|he|she|they) (?:fail|work|miss|hit|happen)|"
        r"what did i roll|the (?:roll|dice)|rolled|what went wrong)", re.I),
}


# A question the engine cannot answer however much of it it recognises.
#
# Reported 2026-09-17: "/gm what are the people around me doing in reaction to this?"
# was answered with a `WHO:` roster and a spell block, and the GM was never asked —
# because `answer()` returns as soon as any section produces a line, and "people"
# matched the `who` topic.
#
# The roster was not *wrong*, it was beside the point. The engine holds who is present
# and their hit points; it does not hold what they are doing about the bodies on the
# cobbles, and no amount of state will ever contain that. These questions ask for a
# reading of the scene, which is the one thing the GM is for.
#
# The engine's own lines are still gathered and handed to the model as grounding — the
# question does not stop being about the people who are actually there.
_WANTS_A_READING = re.compile(
    r"\b(?:doing|do(?:es)?\s+(?:it|he|she|they|that)|react(?:ing|ion|ions)?|"
    r"reacting|responding|response|thinking|think|feel(?:ing|s)?|"
    r"say(?:ing)?\s+about|make\s+of|looks?\s+like|seems?|mood|"
    r"watching|staring|happening\s+(?:around|to))\b", re.I)


def wants_a_reading(question: str) -> bool:
    """Is this a question about behaviour rather than about state?"""
    return bool(_WANTS_A_READING.search(str(question or "")))


def topics_for(question: str) -> list[str]:
    """Which sections answer this. Everything, when the question is empty — "/gm" on
    its own is "tell me the state" — and nothing when it fits no phrase."""
    asked = " ".join(str(question or "").split())
    if not asked:
        return list(TOPICS)
    return [name for name, pattern in TOPICS.items() if pattern.search(asked)]


def answer(campaign, engine, question: str) -> tuple[str, str]:
    """Whatever was asked, answered.

    Returns (kind, text), where kind is "engine" for something read straight off the
    state or the rulebooks and "gm" for something the model was asked. The two are
    labelled differently on the page and that difference is the point: the player must
    always be able to tell a fact from an opinion, however well the opinion reads.

    Three passes, cheapest and most certain first. What the engine holds, by phrase; then
    the shipped rules, looked up by name; and when both come up empty, "gm" — the
    world's own record and the model, in `views._ask_the_gm`, which runs `look_up` again
    so whatever the books did find is still handed over as grounding.
    """
    wanted = topics_for(question)
    out: list[str] = []
    for name in TOPICS:
        if name in wanted:
            out += _SECTIONS[name](campaign, engine)

    out += about_what_is_here(campaign, engine, question)

    found = look_up(campaign, engine, question)
    if found:
        out += found

    # A question about what people are *doing* goes to the GM even when the engine
    # recognised half of it. The state says who is standing there; only the GM can say
    # what they are doing about it. `_ask_the_gm` runs `look_up` itself, so whatever the
    # books did find is still handed over as grounding.
    if out and wants_a_reading(question):
        return "gm", ""

    if out:
        if houserules.gm_view():
            out += _machine(campaign)
        return "engine", "\n".join(out)
    return "gm", ""


def _where(c, engine) -> list[str]:
    here = engine.here()
    out = [f"WHERE: {getattr(here, 'name', 'nowhere named')}."]
    if getattr(here, "id", ""):
        out.append(f"  id: {here.id}")
    known = [p for p in (engine.places() or []) if getattr(p, "id", "") != getattr(here, "id", "")]
    if known:
        out.append("  from here you can name: " + ", ".join(
            str(getattr(p, "name", p)) for p in known[:8]))
    return out


def _who(c, engine) -> list[str]:
    people = [(r, a) for r, a in (c.scene.actors or {}).items() if not a.is_pc]
    if not people:
        out = ["WHO: nobody the engine holds is standing with you."]
    else:
        out = ["WHO:"]
        for ref, a in people:
            bits = [f"  {a.name} ({ref})"]
            if a.has_state("state.down.dead"):
                bits.append("dead")
            elif a.is_down:
                bits.append("down")
            else:
                bits.append(f"{a.hp}/{a.hp_max} hp")
            mood = states.attitude_of(a)
            if mood:
                bits.append(str(mood))
            out.append(" — ".join(bits))
    # People the prose introduced who are not on the board are a different answer, and
    # the difference is exactly the kind of thing worth being able to ask about.
    noted = [str(e.get("who")) for e in (getattr(c.scene, "cast", None) or [])
             if e.get("who")]
    if noted:
        out.append("  mentioned in the prose but not on the board: " + ", ".join(noted))
    return out


def _me(c, engine) -> list[str]:
    pc = c.scene.pc()
    if pc is None:
        return ["YOU: the engine is holding no character."]
    out = [f"YOU: {pc.name} — {pc.hp}/{pc.hp_max} hp."]
    held = sorted({t for cond in pc.conditions for t in states.tags_for(cond.key)})
    if held:
        out.append("  states: " + ", ".join(held))
    live = [e for e in (getattr(pc, "effects", None) or []) if e]
    if live:
        out.append(f"  effects running: {len(live)}")
        for e in live[:8]:
            src = getattr(e, "source", "") or getattr(e, "origin", "") or "unnamed"
            out.append(f"    {src}")
    return out


def _carrying(c, engine) -> list[str]:
    pc = c.scene.pc()
    items = list(getattr(pc, "inventory", None) or []) if pc is not None else []
    if not items:
        return ["CARRYING: nothing the engine holds."]
    out = ["CARRYING:"]
    for it in items[:40]:
        name = it.get("name") if isinstance(it, dict) else getattr(it, "name", str(it))
        n = it.get("count") if isinstance(it, dict) else getattr(it, "count", 1)
        out.append(f"  {name}" + (f" x{n}" if n and int(n) > 1 else ""))
    if len(items) > 40:
        out.append(f"  and {len(items) - 40} more")
    return out


def _quests(c, engine) -> list[str]:
    quests = cards_mod.quests(c.scene)
    live = [q for q in quests if q.live]
    if not live:
        return ["QUESTS: none open."]
    out = ["QUESTS:"]
    for q in live:
        out.append(f"  {q.title} — {q.stage}")
        for i, o in enumerate(q.objectives):
            out.append(f"    [{'x' if o.get('done') else ' '}] {o.get('text', '')}")
    return out


def _time(c, engine) -> list[str]:
    minutes = int(getattr(c.scene, "clock_minutes", 0) or 0)
    day, rest = divmod(minutes, 24 * 60)
    hour, minute = divmod(rest, 60)
    out = [f"TIME: day {day + 1}, {hour:02d}:{minute:02d} by the world clock."]
    if c.scene.in_encounter:
        out.append(f"  a fight is running, round {c.scene.round}")
    return out


def _last(c, engine) -> list[str]:
    """What the engine decided last turn, in its own words: the tells."""
    for entry in reversed(c.turn_log or []):
        outcomes = entry.get("outcomes")
        if not outcomes:
            continue
        out = ["LAST TURN, as the engine decided it:"]
        for o in outcomes:
            tell = str(o.get("tell") or "").strip()
            if tell:
                out.append(f"  {tell}")
            for roll in o.get("rolls") or []:
                out.append(f"    rolled {roll.get('total')} "
                           f"({roll.get('note') or roll.get('kind') or 'a roll'})")
        return out if len(out) > 1 else ["LAST TURN: the engine decided nothing."]
    return ["LAST TURN: nothing on the record yet."]


def _machine(c) -> list[str]:
    """The GM view. A house rule that had no reader anywhere in the app until now."""
    out = ["", "GM VIEW (the machine layer; Rulesets turns this off):"]
    entry = next((e for e in reversed(c.turn_log or []) if e.get("kind") == "turn"), None)
    if entry is None:
        return out + ["  no turn on the record yet."]
    for i in entry.get("intents") or []:
        out.append(f"  op {i.get('op')} — {i.get('because', '')}")
    for r in entry.get("repairs") or []:
        out.append(f"  repair: {r}")
    for r in entry.get("rejections") or []:
        out.append(f"  rejected: {r}")
    out.append(f"  ledger entries kept: {len(c.ledger or [])}")
    return out


_SECTIONS = {
    "where": _where, "who": _who, "me": _me, "carrying": _carrying,
    "quests": _quests, "time": _time, "last": _last,
}


# --- looking things up ------------------------------------------------------------------
#
# The player's ruling, and it is the right one: "I should be able to ask the GM
# anything, including questions about the world and questions about the system or the
# rules." The seven topics above answer where you are and what you carry. They had
# nothing to say about a spell, a feat, a creature, a faction or a rule, and a door that
# answers seven questions and refuses the eighth is a door people stop using.
#
# So: look it up. The app ships 26 MB of Pathfinder content and a whole world export,
# all of it keyed by name, and none of it needs a model to read. Ground every name —
# what comes back here is what the books and the export actually say, not what a model
# remembers about Pathfinder.

# Words that are never what a question is *about*. Without this, "what is the tavern
# like" looks up a spell called "like" and the search is worse than useless.
_NOISE = frozenset((
    "a an and the this that these those is are was were be been am do does did "
    "what which who whom whose when where why how can could may might will would "
    "shall should must i me my mine we us our you your he him his she her it its "
    "they them their of in on at to for from with without about into over under by "
    "as if or but not no here there anything something someone anyone tell know "
    "knows explain say says mean means work works recognise recognize see look "
    "looking got have has had get gets there's whats"
).split())

# Which catalogue a question is asking after, when it says so outright. Checked before
# the general sweep, so "the spell shield" finds the spell rather than the armour.
_HINTS = (
    ("spell", "spell"), ("spells", "spell"), ("cast", "spell"), ("casting", "spell"),
    ("feat", "feat"), ("feats", "feat"),
    ("weapon", "weapon"), ("weapons", "weapon"),
    ("creature", "creature"), ("monster", "creature"), ("beast", "creature"),
    ("condition", "state"), ("status", "state"),
    ("hazard", "hazard"), ("trap", "hazard"),
)


def _terms(question: str):
    """The phrases a question might be *about*, longest first.

    Hint words come out as well as noise: "do i recognize whatever this creature is"
    asked after a creature and got one called "Cask Creature", because the word that
    said which catalogue to look in was also handed to it as the thing to look for.
    """
    words = re.findall(r"[a-z][a-z-]+", str(question or "").lower())
    hints = {w for w, _ in _HINTS}
    kept = [w for w in words if w not in _NOISE and w not in hints and len(w) > 2]
    out = []
    # Longest phrases first: "power attack" must beat "attack", and "magic missile"
    # must beat "missile".
    for size in (3, 2, 1):
        for i in range(len(kept) - size + 1):
            out.append(" ".join(kept[i:i + size]))
    return out


def _hint(question: str) -> str:
    low = " " + " ".join(str(question or "").lower().split()) + " "
    for word, kind in _HINTS:
        if " " + word + " " in low:
            return kind
    return ""


# The shape of asking what a thing IS. A one-word term is looked up as a rules entry
# only inside this shape (or with a catalogue hint), because the catalogues are full of
# ordinary words filed as names: 2,137 of 7,135 creatures are one word (guards, acolyte,
# merchant, wolf), 380 spells (light, fear, jump, sleep, command, break), feats (run,
# dodge), weapons (club, net). Measured live 2026-09-18: "who guards the gate" was
# answered with the bestiary's *Guards* — an exact match, on a verb. "What is a ghost"
# and "what does fireball do" are asking about the entry; "is there light here" and
# "should I run" are about the scene, and go to the GM.
_DEFINITIONAL = re.compile(
    r"\b(?:what(?:'s|’s| is| are| does| do| was| were)|how (?:does|do)|explain|define|"
    r"describe|tell me about|meaning of|rules? (?:for|on|of|about))\b", re.I)


def asks_what_a_thing_is(question: str) -> bool:
    return bool(_DEFINITIONAL.search(str(question or "")))


def look_up(c, engine, question: str):
    """What the rulebooks say about whatever was named. May be empty.

    The world's own material is no longer looked up here by exact name — it is FOUND, by
    `play.gm_search`, which ranks the whole record and hands the model its passages.
    """
    terms = _terms(question)
    if not terms:
        return []
    hint = _hint(question)
    finders = ([f for f in _FINDERS if f.__name__ == "_find_" + hint] if hint
               else list(_FINDERS))
    # By term and THEN by finder, so the longest phrase wins across every catalogue
    # rather than the first catalogue winning with its worst match. A catalogue hint
    # ("the spell magic") is the player naming a thing, and a one-word start of a name
    # is allowed to find it; without one it is not (`_match`). And a one-word term is
    # tried at all only when the question asks what a thing is (`_DEFINITIONAL`).
    single_ok = bool(hint) or asks_what_a_thing_is(question)
    for term in terms:
        if " " not in term and not single_ok:
            continue
        for finder in finders:
            try:
                got = finder(c, engine, term, bool(hint))
            except Exception:
                got = []
            if got:
                return got
    return []


# --- matching a name, rather than searching for one -------------------------------------
#
# The catalogues' own `search()` functions are fuzzy: they score every row against the
# text and hand back the best, so they answer *something* for any input at all. Measured
# 2026-09-09, before this: "what does the spell fireball do" returned Arcane Mark, "what
# is power attack" returned a creature called Empowered Cyberplasm, and "how does a
# longsword work" returned the spell Lead Blades. A confident wrong answer is worse than
# no answer, and this door exists to be trusted.
#
# So these match a NAME. Exactly, then as a whole leading phrase, and never as a loose
# substring shorter than four characters.
_INDEX = {}


def _index(kind, build):
    if kind not in _INDEX:
        try:
            _INDEX[kind] = build()
        except Exception:
            _INDEX[kind] = {}
    return _INDEX[kind]


def _match(names: dict, term: str, named: bool = False):
    """The row whose name IS this, or begins with it. Never a loose contains.

    `named`: the question said which catalogue it meant ("the spell magic"), so a
    one-word start of a name is somebody naming the entry rather than speaking English.
    """
    term = " ".join(str(term or "").lower().split())
    if not term:
        return None
    if term in names:
        return names[term]
    if len(term) < 4:
        return None
    # A name that BEGINS with the term. Two words is somebody naming it ("power att…");
    # one word is not, unless the catalogue was named. Measured live 2026-09-18, three
    # of ten questions were answered by this clause and all three were wrong: "temple"
    # found the Temple Sword, "town" the Town Watcher, "winged" the spell Winged Sword —
    # each the only entry in its catalogue beginning with that ordinary word.
    if " " in term or named:
        starts = [n for n in names if n.startswith(term + " ")]
        if len(starts) == 1:
            return names[starts[0]]
    # A term found in the MIDDLE of a name has to be more than one word.
    #
    # Reported 2026-09-17: "/gm what are the people around me doing in reaction to
    # this?" came back with a roster and the full text of the spell **Negative
    # Reaction** — because "reaction" is one word of that spell's name and this clause
    # matched it. The docstring above already promised "never a loose contains", and at
    # word granularity this was exactly that.
    #
    # One ordinary English word is not somebody naming a rules entry; two in sequence
    # usually is, which is why "power attack" and "magic missile" still land. The cost
    # is that a single mid-name word no longer finds its entry, and that is the right
    # way round: failing to find a lookup sends the question to the GM, while finding
    # the wrong one answers a question nobody asked and stops the GM being asked at all.
    if " " not in term:
        return None
    whole = [n for n in names if (" " + n + " ").find(" " + term + " ") >= 0]
    return names[whole[0]] if len(whole) == 1 else None


# Pathfinder 1e's own mapping of creature type to the Knowledge skill that identifies
# one, which is the actual answer to "do I recognise this".
_KNOWLEDGE = {
    "aberration": "Knowledge (dungeoneering)", "animal": "Knowledge (nature)",
    "construct": "Knowledge (arcana)", "dragon": "Knowledge (arcana)",
    "fey": "Knowledge (nature)", "humanoid": "Knowledge (local)",
    "magical beast": "Knowledge (arcana)",
    "monstrous humanoid": "Knowledge (dungeoneering)",
    "ooze": "Knowledge (dungeoneering)", "outsider": "Knowledge (planes)",
    "plant": "Knowledge (nature)", "undead": "Knowledge (religion)",
    "vermin": "Knowledge (dungeoneering)",
}


def _find_creature(c, engine, term, named=False):
    """A creature by name — and the rule for whether the character knows it.

    NOT the stat block. Identifying a creature is a Knowledge check in these rules, and
    handing over its hit points because the player asked out of character would be
    playing the game for them. `/cheat` is the door for deliberately breaking that;
    this one answers what the rule IS.
    """
    from rules import bestiary

    rows = _index("creature", lambda: {
        str(v.get("name", k)).lower(): v
        for k, v in bestiary.everything().items() if isinstance(v, dict)})
    b = _match(rows, term, named)
    if not b:
        return []
    kind = str(b.get("creature_type") or "creature")
    skill = _KNOWLEDGE.get(kind.lower(), "the Knowledge skill for its kind")
    head = " ".join(str(x) for x in (b.get("name"), "—", b.get("size", ""), kind) if x)
    return [f"CREATURE: {head}, CR {b.get('cr', '?')}.",
            f"  identifying one is a {skill} check, DC 10 + its CR",
            "  its numbers are not yours for the asking; make the check in play"]


def _find_spell(c, engine, term, named=False):
    from rules import spells

    rows = _index("spell", lambda: {
        str(getattr(v, "name", k)).lower(): v for k, v in spells.all_spells().items()})
    s = _match(rows, term, named)
    if not s:
        return []
    out = ["SPELL: " + str(getattr(s, "name", term)) + "."]
    for label in ("school", "casting_time", "range", "duration", "saving_throw",
                  "components"):
        value = " ".join(str(getattr(s, label, "") or "").split())
        if value:
            out.append("  " + label.replace("_", " ") + ": " + value)
    text = " ".join(str(getattr(s, "description", "") or "").split())
    if text:
        out.append("  " + text[:600] + ("…" if len(text) > 600 else ""))
    return out


def _find_feat(c, engine, term, named=False):
    from rules import feats

    rows = _index("feat", lambda: {
        str(getattr(v, "name", k)).lower(): v for k, v in feats.all_feats().items()})
    f = _match(rows, term, named)
    if not f:
        return []
    out = ["FEAT: " + str(getattr(f, "name", term)) + "."]
    pre = " ".join(str(getattr(f, "prerequisites_text", "") or "").split())
    if pre:
        out.append("  needs: " + pre)
    for label in ("benefit", "normal"):
        text = " ".join(str(getattr(f, label, "") or "").split())
        if text:
            out.append("  " + label + ": " + text[:500] + ("…" if len(text) > 500 else ""))
    return out


def _find_weapon(c, engine, term, named=False):
    from rules import weapons

    rows = _index("weapon", lambda: {
        str(v.get("name", k)).lower(): v for k, v in weapons.all_weapons().items()})
    w = _match(rows, term, named)
    if not w:
        return []
    return ["WEAPON: {name} — {dmg} {kind}, crit {cr}/x{cm}, {prof} {cat}.".format(
        name=w.get("name"), dmg=w.get("damage", "?"), kind=w.get("type_text", ""),
        cr=w.get("crit_range", "20"), cm=w.get("crit_mult", 2),
        prof=w.get("prof", ""), cat=w.get("category", "")).replace("  ", " ")]


def _find_hazard(c, engine, term, named=False):
    from rules import hazards

    rows = _index("hazard", lambda: {str(n).lower(): n for n in hazards.names()})
    name = _match(rows, term, named)
    row = hazards.get(name) if name else None
    if not row:
        return []
    out = ["HAZARD: " + str(name) + "."]
    for k, v in row.items():
        if k != "id" and not isinstance(v, (dict, list)):
            out.append("  " + str(k) + ": " + str(v))
    return out[:10]


def _find_state(c, engine, term, named=False):
    """A condition, by the one tag vocabulary every system in the app speaks."""
    from rules import states

    rows = _index("state", lambda: {str(k).lower().replace("-", " "): k
                                    for k in states.TAGS})
    key = _match(rows, term, named)
    if not key:
        return []
    out = ["CONDITION: " + str(key) + ".",
           "  tags: " + ", ".join(states.tags_for(key))]
    stops = states.stops(key)
    if stops:
        out.append("  stops: " + ", ".join(sorted(stops)))
    return out


# The world's own export used to have a finder here too, by exact name, and it answered
# "who is Drenn Ironvale" with "IN THIS WORLD: Drenn Ironvale — CHARACTER. Person" —
# the whole of his summary — and then stopped the GM being asked. The record is read by
# `play.gm_search` now, ranked, and handed to the model as passages (docs/gm-questions.md).
_FINDERS = (_find_creature, _find_spell, _find_feat, _find_weapon, _find_hazard,
            _find_state)

# "this creature", "that thing", "it" — a question about somebody standing right here
# rather than about a name in a book. This is what the player actually asked on
# 2026-09-09, and the catalogue lookup could not help because they had not named
# anything: the creature was in front of them and the whole point was that they did not
# know what it was.
_THIS_ONE = re.compile(
    r"\b(?:this|that|the)\s+(?:creature|thing|monster|beast|animal|figure|one)\b"
    r"|\brecogni[sz]e\b|\bidentify\b|\bwhat is it\b", re.I)


def about_what_is_here(c, engine, question: str):
    """The identify rule, for whoever is actually standing here."""
    if not _THIS_ONE.search(str(question or "")):
        return []
    people = [a for a in (c.scene.actors or {}).values() if not a.is_pc]
    if not people:
        return ["Nothing is standing here that the engine holds, so there is nothing "
                "to recognise."]
    out = ["RECOGNISING WHAT IS HERE:"]
    for a in people:
        seen = a.name
        kind = ""
        template = getattr(a, "from_template", "") or ""
        if template:
            from rules import bestiary

            row = bestiary.lookup(template) or {}
            kind = str(row.get("creature_type") or "")
        skill = _KNOWLEDGE.get(kind.lower(), "") if kind else ""
        line = "  " + seen
        if skill:
            line += " — a " + kind + "; identifying it is a " + skill + " check"
        else:
            line += " — the engine has no creature type filed for them"
        out.append(line)
    out.append("  the difficulty is 10 + the creature's CR, and knowing more than its "
               "name is a check you make in play")
    out.append("  the engine will not hand over its numbers here; that is what /cheat "
               "is for, and it is a different thing on purpose")
    return out

"""Out of character: the engine answering a question about itself.

The player asked for this in as many words, and the honest answer at the time was that
the app had no door for it. Every multiplayer text tradition has one — Diku and its
descendants ship an `ooc` channel, MUSH has `page` and `@emit`, and they exist because
somebody at the table always needs to ask about the game without their character doing
anything. This app had exactly one way out of the fiction, `/cheat`, and a cheat makes
a statement true rather than answering a question.

Three rules, and they are what make this worth having at all:

**No model.** Every line below is read off the engine, which owns the state. A question
answered by a language model is a guess with good grammar — a recent benchmark of
narrative consistency has the best model contradicting an established fact within
twenty turns in most runs — and the whole point of asking the GM is to get the truth
rather than the fiction's version of it.

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

from rules import cards as cards_mod
from rules import houserules, states

# What a question is about. Matched loosely on purpose: somebody typing "/gm who is
# here again?" is asking the same thing as "/gm who", and a door that only opens for an
# exact word is a door people stop using.
TOPICS = {
    # Words are chosen to overlap as little as possible, because a question matches
    # every topic it touches and "who is here" answering with the map first is noise.
    # "here" and "me" are deliberately absent for that reason: they are in half of all
    # questions.
    "where": ("where", "place", "room", "exits", "leads", "map", "standing", "outside"),
    "who": ("who", "people", "person", "npc", "npcs", "present", "cast", "with"),
    "me": ("hp", "health", "hurt", "wounded", "condition", "conditions", "effects",
           "buff", "buffs", "sheet", "myself", "dying"),
    "carrying": ("carrying", "carry", "have", "inventory", "satchel", "pack", "items",
                 "gear", "coin", "money", "purse"),
    "quests": ("quest", "quests", "task", "tasks", "objective", "objectives", "job"),
    "time": ("time", "clock", "day", "hour", "late", "when"),
    "last": ("last", "happened", "just", "why", "roll", "rolled", "dice", "turn"),
}


def topics_for(question: str) -> list[str]:
    """Which sections answer this. Everything, when the question names nothing."""
    asked = " " + " ".join(str(question or "").lower().split()) + " "
    if not asked.strip():
        return list(TOPICS)
    found = [name for name, words in TOPICS.items()
             if any(f" {w} " in asked or asked.startswith(f" {w}") or
                    f" {w}?" in asked or f" {w}," in asked for w in words)]
    return found or []


def answer(campaign, engine, question: str) -> str:
    """The engine's own answer, as lines of plain fact."""
    wanted = topics_for(question)
    if not wanted:
        return _lost(question)
    out: list[str] = []
    for name in TOPICS:
        if name in wanted:
            out += _SECTIONS[name](campaign, engine)
    if houserules.gm_view():
        out += _machine(campaign)
    return "\n".join(out) if out else _lost(question)


def _lost(question: str) -> str:
    """A refusal that names the fix, in the style the classbuilder's validators use."""
    return ("The engine has nothing filed under that. Ask it about: "
            + ", ".join(sorted(TOPICS)) + ".\n"
            "For example: /gm who is here, /gm what am I carrying, /gm quests.\n"
            "Anything else is a question for the world rather than the engine, so ask "
            "it in play and somebody will answer.")


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

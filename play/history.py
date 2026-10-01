"""The character's history, for the Journal (owner, 2026-10-01): "a history section at the
bottom that will read the full history of the character read from the stored information
of the campaign".

**Engine facts, never prose.** Built from the turn log's outcome effects — the one store
complete from turn one and never trimmed (docs/memory-policy.md) — plus the opening card
(how it began), the quest cards (their titles and objectives), and the campaign's end.
Not from the transcript's prose, the model's history, or a model-written summary: the
narrator's words are already on the Table, and a history that re-tells them would carry
every invention the grooming missed. Not from the memory ledger either: it is capped at
400 entries and written for the prompt.

**One line per thing that happened, from an allow-list of effect kinds.** Crusader Kings
II's chronicle wrote down everything and its players called it filler; III dropped it for
a short list of memories per character. Dwarf Fortress's Legends reads the same engine
event records chronologically and by figure. So: places reached, people met, fights
joined and who fell, quests taken and finished, what changed hands, the rank reached, how
somebody came to feel about you — and not every roll, blow or word.

**Days, where the log can say.** Turn-log rows carry the world clock and the place from
2026-10-01 (`stamp`); a row written before then has neither, and those lines are listed
first, in order, under no day — an older campaign's history is told in sequence rather
than guessed into days.

**Refs never reach the page** (ruling 2026-09-28): every person is named through the
scene, the population record, or the name the conversation log kept when they spoke, and
a line about somebody with no name anywhere is left out rather than printed as "c6".
"""
from __future__ import annotations

import re

# The rows that carry outcomes the player's history is made of. The rest of the turn log
# is diagnostics (prose, mentions, speech-tags, truth-checks...).
EVENT_ROWS = ("turn", "resolution", "npc-turn", "level-up")


def stamp(c, entry: dict) -> dict:
    """When and where a turn-log row happened: the world clock and the place id. Written
    on the rows `history` reads, so a day can be put on what they record."""
    scene = c.scene
    entry.setdefault("clock", int(getattr(scene, "clock_minutes", 0) or 0))
    entry.setdefault("at", str(getattr(scene, "at", "") or ""))
    return entry


def _namer(c):
    """ref -> a name the player knows, or "" — never the ref itself."""
    from rules import population

    scene = c.scene
    pc = scene.pc()
    spoke = {}
    for e in getattr(scene, "conversation_log", None) or ():
        if isinstance(e, dict) and e.get("who") and e.get("name"):
            spoke.setdefault(str(e["who"]), str(e["name"]))

    def name(ref) -> str:
        ref = str(ref or "")
        if not ref:
            return ""
        if pc is not None and ref == pc.ref:
            return "you"
        actor = (getattr(scene, "people", None) or {}).get(ref) \
            or (getattr(scene, "actors", None) or {}).get(ref)
        if actor is not None and getattr(actor, "name", ""):
            return _the(str(actor.name))
        rec = population.of_ref(scene, ref)
        if rec and rec.get("phrase"):
            return _the(str(rec["phrase"]))
        return _the(spoke.get(ref, ""))
    return name


# A place whose name is a word of direction rather than a name — the outskirts read
# "outside" — is named from its own id instead: "You went to outside" was the first run.
_NOT_A_NAME = frozenset({"outside", "inside", "here", "there", "away"})


def _place_name(c, place_id: str) -> str:
    from rules import population

    if not place_id:
        return ""
    name = population._place_name(str(place_id), c.scene, c.world)
    if name.strip().lower() in _NOT_A_NAME:
        leaf = str(place_id).rsplit("/", 1)[-1].rsplit(":", 1)[-1].lstrip("@")
        name = leaf.replace("-", " ")
    return name


def _town_name(c, town_id: str) -> str:
    world = getattr(c, "world", None)
    loc = world.get(town_id) if world is not None and town_id else None
    return str(getattr(loc, "name", "") or "")


def _the(name: str) -> str:
    """"guard" → "the guard"; a name, or a phrase with its own article, as it is."""
    if name and name[:1].islower() and not re.match(r"(?:the|a|an|some|you)\b", name):
        return f"the {name}"
    return name


def _item_name(effect: dict, key: str = "item") -> str:
    """What a thing is called, not its key: a crafted jar is `power_leaf_tea#1` in the
    satchel and "Power leaf tea" on its own record, which the effect carries."""
    item = str(effect.get(key) or "")
    rec = (effect.get("satchel") or {}).get(item)
    if isinstance(rec, dict) and rec.get("name"):
        return str(rec["name"])
    return re.sub(r"#\d+$", "", item).replace("_", " ")


def _quest(c, card_id: str):
    from rules import cards as cards_mod

    card = cards_mod.find(c.scene, card_id)
    return None if card is None or getattr(card, "secret", False) else card


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


def _effect_lines(c, effect: dict, name, actor_of_intent: str) -> list[str]:
    """The sentence(s) one effect adds to the history, or [] for an effect that is not
    history. Second person, past tense: the Journal speaks to the player."""
    from rules import attitude as attitude_mod

    kind = effect.get("kind")
    if kind == "biome":
        if effect.get("place") and effect.get("place") != effect.get("was_place"):
            where = _place_name(c, effect["place"])
            return [f"You went to {where}."] if where else []
        return []
    if kind == "journey":
        where = str(effect.get("to_name") or "")
        if not where:
            return []
        return ([f"You travelled to {where}."] if effect.get("arrived")
                else [f"You set out for {where} and stopped short."])
    if kind == "place":
        return [f"You found {effect['name']}."] if effect.get("name") else []
    if kind == "quest":
        title = str(effect.get("title") or "")
        giver = name(effect.get("giver"))
        if not title:
            return []
        return [f"You took on “{title}”" + (f" for {giver}." if giver and giver != "you"
                                             else ".")]
    if kind == "quest_step":
        card = _quest(c, str(effect.get("id") or ""))
        if card is None:
            return []
        if effect.get("finished"):
            return [f"You finished “{card.title}”."]
        i = int(effect.get("objective") or 0) - 1
        objective = card.objectives[i]["text"] if 0 <= i < len(card.objectives) else ""
        return [f"Done, for “{card.title}”: {objective}."] if objective else []
    if kind == "battle_joined":
        foe = name(effect.get("target"))
        if not foe or foe == "you":
            who = name(effect.get("ref"))
            return [f"{_cap(who)} came at you, and a fight began."] if who and who != "you" else []
        return [f"A fight began with {foe}."]
    if kind == "condition":
        who = name(effect.get("ref"))
        cond = str(effect.get("condition") or "")
        if not who or who == "you":
            return []
        if cond == "dead":
            return [f"{_cap(who)} died."]
        if attitude_mod.step_of(cond) >= 0:
            # Where they ended up, in the tell's own words ("is well disposed towards
            # you"); the verb is the step, never a number.
            line = attitude_mod.said(who, "", cond).split(": ", 1)[-1]
            return [f"{_cap(who)} {line.rstrip('.')}."]
        return []
    if kind == "introduce":
        out = []
        for a in effect.get("actors") or ():
            who = name(a.get("ref")) or str(a.get("name") or "")
            if who and who != "you":
                out.append(f"You met {who}.")
        return out
    if kind == "company":
        who = name(effect.get("ref"))
        if not who or who == "you":
            return []
        return [f"{_cap(who)} joined you." if effect.get("travels")
                else f"{_cap(who)} went their own way."]
    if kind == "bought":
        n = int(effect.get("count") or 1)
        return [f"You bought {effect['item']}" + (f" ×{n}." if n > 1 else ".")] \
            if effect.get("item") else []
    if kind == "sold":
        return [f"You sold {effect['item']}."] if effect.get("item") else []
    if kind == "took":
        items = [str(i) for i in effect.get("items") or ()]
        whom = name(effect.get("from"))
        if not items or name(effect.get("ref")) != "you":
            return []
        return [f"You took {', '.join(items)}" + (f" from {whom}." if whom else ".")]
    if kind == "stolen":
        whom = name(effect.get("from"))
        if name(effect.get("ref")) != "you" or not effect.get("item"):
            return []
        return [f"You stole {effect['item']}" + (f" from {whom}." if whom else ".")]
    if kind == "give":
        item = _item_name(effect)
        taker = name(effect.get("ref"))
        giver = name(actor_of_intent)
        if not item or not taker:
            return []
        if taker == "you" and giver and giver != "you":
            return [f"{_cap(giver)} gave you {item}."]
        if giver == "you" and taker != "you":
            return [f"You gave {item} to {taker}."]
        return []
    if kind == "xp" and name(effect.get("ref")) == "you" and effect.get("amount"):
        return [f"You earned {int(effect['amount']):,} experience."]
    if kind == "wanted":
        town = _town_name(c, str(effect.get("town") or "")) or "the town"
        return [f"The watch of {town} wants you."]
    return []


def _row_lines(c, row: dict, name, seen: set) -> list[str]:
    if row.get("kind") == "level-up":
        return [f"You reached level {int(row['level'])}."] if row.get("level") else []
    actors = {str(i.get("id")): str(i.get("actor") or "")
              for i in row.get("intents") or () if isinstance(i, dict)}
    out: list[str] = []
    for o in row.get("outcomes") or ():
        # A resolution row repeats the outcomes of the turn it resumed (its intents are
        # numbered per turn), so the same outcome is told once.
        key = (o.get("intent_id"), o.get("op"), o.get("tell"))
        if key in seen:
            continue
        seen.add(key)
        if o.get("status") == "prevented" and o.get("op") != "journey":
            continue
        for effect in o.get("effects") or ():
            if isinstance(effect, dict):
                out += _effect_lines(c, effect, name, actors.get(str(o.get("intent_id")), ""))
    return out


def _began(c) -> str:
    """How it began: the opening card's errand, where the game opened."""
    from rules import cards as cards_mod

    card = cards_mod.find(c.scene, "opening")
    start = getattr(c.scene, "start", None) or {}
    where = str(start.get("where") or "") or str(getattr(c, "location", None) and
                                                 getattr(c.location, "name", "") or "")
    bits = []
    if where:
        bits.append(f"It began in {where}.")
    # The errand as the opening card keeps it, a whole sentence already ("You came
    # because somebody sent a runner for the bonesetter…"). Its title is that sentence
    # cut down for a heading, and spliced into "You had come for …" it read as nonsense.
    errand = next((f for f in (card.facts if card is not None else ())
                   if str(f).startswith("You came")), "")
    if errand:
        bits.append(str(errand))
    return " ".join(bits)


def history(c) -> dict:
    """{"began": str, "days": [{"day": int | None, "lines": [{"text", "at"}]}],
    "ended": str} — oldest first. `day` is None for the lines from before the turn log
    kept the clock."""
    name = _namer(c)
    seen: set = set()
    days: list[dict] = []
    last_text = ""
    for row in c.turn_log or ():
        if not isinstance(row, dict) or row.get("kind") not in EVENT_ROWS:
            continue
        if row.get("kind") == "turn":
            seen = set()                     # intent ids start again each turn
        clock = row.get("clock")
        day = int(clock) // (24 * 60) + 1 if isinstance(clock, int) else None
        for text in _row_lines(c, row, name, seen):
            if text == last_text:
                continue                     # the same thing twice running is once
            last_text = text
            if not days or days[-1]["day"] != day:
                days.append({"day": day, "lines": []})
            days[-1]["lines"].append({"text": text,
                                      "at": _place_name(c, row.get("at", ""))})
    ended = "You died." if getattr(c, "ended", "") == "died" else ""
    return {"began": _began(c), "days": days, "ended": ended}

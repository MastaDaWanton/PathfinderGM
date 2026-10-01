"""The suggestions are held to the sheet: a line that offers what the character cannot do
is dropped, and the page is never left with fewer than two to choose from.

Item 4 of the 2026-09-30 playtest. Sam, a bonesetter wizard with no healing spell, was
offered **"I use a healing spell to knit the flesh"**, and later **"I keep my hand on the
hilt of my blade as I navigate the crowd"** with a shortbow in hand and no blade anywhere.
The owner: "the example inputs should probably not suggest the use of spells if it isnt
going to be aware of what the character can do." The prose call writes the suggestions;
the brief lists what Sam can cast, and the model ignored it, because instructions lose
(CLAUDE.md). Nothing in code checked a suggestion against the sheet, and clicking one
passed every detector silently.

**Detect in code, with the turn's own detectors** — no second copy of any rule:

  * a named power ("I use Blood Nova on him") goes through `judgement.refuse_unknown_ability`,
    which asks `leveling.find_ability` and the satchel; a name it would refuse is dropped;
  * a named spell is read against the whole catalogue by `judgement.spell_in_words` (the
    resolver `inject_cast` now uses, word-bounded, so "cure light wounds" is not Light),
    and it must be one the character can cast now;
  * a generic magical line — "a spell", "cast", "magic", "channel energy", "pray to heal"
    — must be answerable by a spell they can cast now, and a healing one ("a healing
    spell", "to knit the flesh") by a spell of the healing subschool;
  * "my <thing>" must be something they carry (`judgement.possession_vocabulary`, the
    vocabulary `false_possession` reads), judged only when the head noun is a word for an
    item at all, so "my name", "my friend" and "my work" are never asked.

**Owner ruling B2, 2026-09-30:** what fails is DROPPED. If fewer than two remain, the page
is filled from plain options built from the scene — talk to somebody present, look
around, or a way out listed here — and never from the start's own lines.

Every beat's offered suggestions are logged on the beat's `prose` turn-log row
(`suggested`), so the next report can be traced from the save; a row of kind
`suggestion-sheet` names each line dropped, why, and what was filled.
"""
from __future__ import annotations

import re

STAGE = "beat"
# Before `suggestion_pronouns` (40): the model's lines are judged and logged as they came,
# and the pronoun repair then reads what survived.
ORDER = 30

LEAST = 2

# A first-person use of magic with no spell named: "I use a healing spell", "I cast",
# "with my magic", "I channel positive energy", "I pray over him to heal the wound".
_CASTS = re.compile(r"\b(?:cast|casts|casting)\b", re.I)
_MAGIC_USED = re.compile(
    r"\b(?:use|uses|using|weave|weaves|work|works|call\s+(?:on|up)|draw\s+on|with|"
    r"through|by)\s+(?:a|an|my|some|the|his|her)?\s*(?:\w+\s+){0,2}?"
    r"(?:spell|spells|magic|cantrip|cantrips|incantation|sorcery)\b", re.I)
_CHANNEL = re.compile(r"\bchannel(?:s|ing|led|ling)?\b[^.!?]{0,30}?\b(?:energy|divine|"
                      r"positive|negative|power\s+of)\b", re.I)
_PRAYS = re.compile(r"\bpray(?:s|ing|er|ers)?\b", re.I)
_HEALING = re.compile(r"\b(?:heal|heals|healing|cure|cures|curing|mend|mends|mending|knit|"
                      r"knits|knitting|restore|restores|restoring|close\s+(?:the|his|her|"
                      r"their)\s+wounds?)\b", re.I)
_MY = re.compile(r"\bmy\s+((?:[a-z][\w'’-]*\s+){0,3}?[a-z][\w'’-]*)"
                 r"(?=\s*(?:[.,;:!?\"“”]|$|\s+(?:of|and|or|as|to|in|on|at|for|with|from|"
                 r"into|onto|while|before|after|then|so|but|that|which|over|under|"
                 r"against|across|toward|towards|by|up|down|out|off|away|aside|back)\b))",
                 re.I)

# Words for a thing one could carry, beyond what the catalogues name: the generic ones a
# suggestion reaches for when it does not know the item ("my blade", "my pack").
_GENERIC_ITEMS = frozenset({
    "weapon", "weapons", "blade", "sword", "bow", "staff", "shield", "armour", "armor",
    "pack", "backpack", "satchel", "purse", "pouch", "kit", "tools", "spellbook", "book",
    "wand", "scroll", "potion", "cloak", "lantern", "torch", "rope", "dagger", "knife",
    "axe", "hammer", "mace", "club", "spear", "crossbow", "sling", "map", "key", "ring",
    "amulet", "symbol", "quiver", "arrows", "bolts", "helm", "helmet", "gauntlets", "flask",
    "vial", "bandages", "herbs", "medicine", "salve", "poultice", "lute", "instrument"})


def _item_nouns() -> frozenset:
    """Head nouns of everything the catalogues sell or the weapon table holds, plus the
    generic words — the vocabulary that decides whether "my X" is a claim to an item."""
    words = set(_GENERIC_ITEMS)
    try:
        from rules import goods as goods_mod, weapons as weapons_mod

        for key, w in weapons_mod.all_weapons().items():
            for name in (key.replace("-", " "), str(w.get("name") or "")):
                bits = re.findall(r"[a-z]+", name.lower())
                if bits:
                    words.add(bits[-1])
        for gid in goods_mod.catalogue_ids():
            bits = re.findall(r"[a-z]+", gid.split(":", 1)[-1].lower())
            if bits:
                words.add(bits[-1])
    except Exception:  # noqa: BLE001 — a table that cannot load leaves the generic words
        pass
    # A word for a thing that is also the ordinary word for something nobody carries.
    return frozenset(words - {"meal", "room", "bed", "night", "day", "week", "hour",
                              "fee", "toll", "passage", "service", "services"})


def castable(pc) -> list:
    """The spells this character could cast right now: a prepared caster's prepared
    copies (cantrips included), a spontaneous caster's known spells within the levels
    they cast, and a divine caster's cures when there is a prepared spell to give up for
    one (`casting.converts_spontaneously`)."""
    from rules import casting, spells as spells_mod

    if not casting.is_caster(pc):
        return []
    out, seen = [], set()

    def add(sp):
        if sp is not None and sp.id not in seen:
            seen.add(sp.id)
            out.append(sp)

    for sid, count in (getattr(pc, "prepared", None) or {}).items():
        if int(count or 0) >= 1:
            try:
                add(spells_mod.get(str(sid).removeprefix("domain:")))
            except KeyError:
                continue
    data = casting.caster_data(pc)
    known = casting.known_spells(pc, up_to=casting.highest_spell_level(pc))
    if data.get("prepare_from") == "known":
        for spells in known.values():
            for sp in spells:
                add(sp)
    elif data.get("kind") == "prepared":
        for lvl, spells in known.items():
            for sp in spells:
                if casting.converts_spontaneously(pc, sp) and lvl > 0 \
                        and casting.sacrifice_for(pc, lvl):
                    add(sp)
    return out


def _heals(sp) -> bool:
    return str(getattr(sp, "subschool", "") or "").strip().lower() == "healing"


def _channels(pc) -> bool:
    """Whether the class gives this character channelled energy — read off the class's
    own document and their abilities, never a class name."""
    import json

    try:
        from rules import leveling

        if any("channel" in str(n).lower() for n in leveling.usable_names(pc)):
            return True
    except Exception:  # noqa: BLE001
        pass
    try:
        return "channel energy" in json.dumps(getattr(pc, "class_data", None) or {}).lower()
    except (TypeError, ValueError):
        return False


def why_not(text: str, scene, items: frozenset | None = None) -> str:
    """Why this suggestion offers what the sheet cannot back, or "" when it is sound."""
    from gm import judgement

    pc = scene.pc() if scene is not None else None
    if pc is None or not str(text or "").strip():
        return ""
    line = str(text)
    spells = None

    def can_cast():
        nonlocal spells
        if spells is None:
            spells = castable(pc)
        return spells

    # A named power. A spell's name in Title Case reads the same way ("I use Magic
    # Missile on him"), so a name that IS a spell is the spell's question, below.
    m = judgement._USES_A_NAMED_THING.search(line)
    if m:
        name = " ".join(m.group(1).split())
        named = judgement.spell_in_words(name)
        if named is None or judgement._spell_words(named.name) != judgement._spell_words(name):
            out = judgement.refuse_unknown_ability([{"op": "narrate_only"}], line, scene)
            if any(isinstance(r, dict) and r.get("op") == "use_ability"
                   and str((r.get("params") or {}).get("ability") or "").lower()
                   == name.lower() for r in out):
                return f"names {name}, which {pc.name} does not have"

    # A named spell: judged when the line is about casting, or the name is two words or
    # more ("burning hands", "cure light wounds") — "I light a torch" is not Light.
    magical = bool(_CASTS.search(line) or _MAGIC_USED.search(line))
    named = judgement.spell_in_words(line)
    if named is not None and (magical or len(judgement._spell_words(named.name)) > 1):
        if not judgement._reachable_by_name(named, [sp.id for sp in can_cast()]):
            return f"names {named.name}, which {pc.name} cannot cast"
        return ""

    healing = bool(_HEALING.search(line))
    if _CHANNEL.search(line) and not _channels(pc):
        return f"channels energy, which {pc.name} cannot"
    if magical or (_PRAYS.search(line) and healing):
        castable_now = can_cast()
        if healing:
            if not any(_heals(sp) for sp in castable_now) and not _channels(pc):
                return f"heals with magic, and {pc.name} has no healing spell ready"
        elif not castable_now:
            return f"uses magic, and {pc.name} has no spell ready"

    # "My <thing>": a thing they carry, when the head noun is a word for a thing at all.
    nouns = items if items is not None else _item_nouns()
    vouched = None
    for mm in _MY.finditer(line):
        head = re.findall(r"[a-z][a-z'’-]*", mm.group(1).lower())[-1]
        if head not in nouns:
            continue
        if vouched is None:
            vouched = judgement.possession_vocabulary(scene, pc)
        if not judgement._vouched_for(head, vouched):
            return f"reaches for {pc.name}'s {head}, which is not on the sheet"
    return ""


def _label(actor) -> str:
    name = " ".join(str(getattr(actor, "name", "") or "").split())
    if not name:
        return ""
    if name[:1].isupper() or re.match(r"(?:the|a|an)\s", name, re.I):
        return name
    return f"the {name}"


def plain_options(ctx, have: list[str]) -> list[str]:
    """Lines built from the scene alone, in this order: talk to somebody present (the
    person in conversation first), look around, a way out listed here."""
    scene = ctx.scene
    out: list[str] = []
    actors = getattr(scene, "actors", {}) or {}
    people = [actors[r] for r in (ctx.talking_after or ()) if r in actors]
    people += [a for r, a in actors.items()
               if not getattr(a, "is_pc", False) and not getattr(a, "is_down", False)
               and a not in people]
    if people and _label(people[0]):
        out.append(f"I talk to {_label(people[0])}.")
    out.append("I look around.")
    try:
        engine = ctx.campaign.engine()
        from rules import places as places_mod

        here = engine.here()
        known = engine.places()
        for x in (getattr(here, "exits", None) or ()):
            p = places_mod.find(known, x)
            if p is not None and p.id != getattr(here, "id", None):
                out.append(f"I head to {p.name}.")
                break
    except Exception:  # noqa: BLE001 — a scene with no places offers the other two
        pass
    low = {h.strip().lower() for h in have}
    return [o for o in out if o.lower() not in low]


def _text(s) -> str:
    return s if isinstance(s, str) else str((s or {}).get("text") or "")


def _prose_row(campaign) -> dict | None:
    """This beat's `prose` row: the last one, looking back no further than the previous
    turn's `resolution` row (which closes every turn after its prose)."""
    for row in reversed(list(getattr(campaign, "turn_log", None) or [])):
        if not isinstance(row, dict):
            continue
        if row.get("kind") == "prose":
            return row
        if row.get("kind") == "resolution":
            return None
    return None


def step(ctx) -> list[dict]:
    campaign = ctx.campaign
    offered = list(getattr(campaign, "suggestions", None) or [])
    row = _prose_row(campaign)
    if row is not None:
        row["suggested"] = [_text(s) for s in offered]
    if not offered:
        return []
    items = _item_nouns()
    kept, dropped = [], []
    for s in offered:
        why = why_not(_text(s), ctx.scene, items)
        if why:
            dropped.append({"text": _text(s), "why": why})
        else:
            kept.append(s)
    if not dropped:
        return []
    filled: list[str] = []
    if len(kept) < LEAST:
        for line in plain_options(ctx, [_text(s) for s in kept]):
            if len(kept) >= LEAST:
                break
            kept.append(line)
            filled.append(line)
    campaign.suggestions = kept
    return [{"kind": "suggestion-sheet", "dropped": dropped, "filled": filled}]

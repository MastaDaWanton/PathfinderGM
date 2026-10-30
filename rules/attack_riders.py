"""What rides a printed hit: each rider word on a stat-block attack, read into a document
the engine can apply.

The gap (2026-10-30, found by the 0.2.24 monster-attacks lane): "bite +3 (1d6+1 plus
disease and paralysis)" was read into an attack carrying `riders: ["disease",
"paralysis"]`, and nothing ever fired them. A ghoul paralysed nobody, a rat swarm's
filth fever infected nobody, a giant spider's venom was a bite. Counted over the compiled
bestiary that day: 1,036 rider words on 161 distinct riders, led by grab 326, poison 191,
disease 64, bleed 42 (and 26 more "plus 1d8 bleed" the reader dropped), energy drain 40,
trip 36, burn 32, paralysis 31.

**Where the numbers come from.** A rider word names a universal monster rule (Bestiary,
Appendix 3; aonprd.com/UMR.aspx). The rule says what the rider does; the creature's own
block says how hard: "paralysis (1d4+1 rounds, DC 13, elves are immune to this effect)"
in Special Attacks, "Poison (Ex) Bite—injury; save Fort DC 14; frequency 1/round for 4
rounds; effect 1d2 Strength damage; cure 1 save" in Special Abilities. This module reads
those two fields into one document per rider. When the block prints no DC, the document
says which ability the UMR's formula uses (`dc_ability`: "10 + 1/2 [the creature's]
racial HD + [its] Constitution modifier", the Poison, Disease and Paralysis rules) and the
engine works it out from the live body. When the block prints no definition at all — a
giant centipede's "poison" with no Poison entry beside it — nothing is invented: the
document is `unsupported` with the reason, and the engine says the rider did not fire.

**Prior art.** Combat Manager (Kyle Olson, `CombatManagerCore/Affliction.cs`,
`FromSpecialAbility`) reads exactly this format with one regular expression into name,
cause, save type and DC, onset (a die and a unit, or "immediate"), frequency (a count and
a unit, with an optional "for N units" limit), the effect (ability damage, a second
ability damage, "X for N units", or other text) and the cure. That shape is kept here,
field for field, and extended where its single expression gave up: an effect of several
pieces ("1d4 Wisdom damage and confusion for 1 round") is read piece by piece, and a
piece no reader knows is kept in `unread` rather than taking the whole effect with it.

Nothing here is model output and nothing here rolls: the same block always reads the same
way. The compile (`compile_block`) stores what this returns on each attack as `rules`, and
the engine (`Engine._printed_riders`) applies them.
"""
from __future__ import annotations

import re

# --- the rider vocabulary ----------------------------------------------------------------

# A rider word as printed after "plus", and the universal monster rule it names. The
# manoeuvres are free combat manoeuvres on the hit, "without provoking an attack of
# opportunity" (Grab, Trip; Pull and Push "do not provoke"); `bonus` is Grab's "+4 bonus
# on combat maneuver checks to start and maintain a grapple".
MANEUVER_RIDERS = {
    "grab": {"maneuver": "grapple", "bonus": 4},
    "trip": {"maneuver": "trip"},
    "pull": {"maneuver": "drag"},
    "push": {"maneuver": "bull rush"},
    "bull rush": {"maneuver": "bull rush"},
    "bull rush attempt": {"maneuver": "bull rush"},
}
AFFLICTION_RIDERS = ("poison", "disease")
# A rider that names a disease rather than the word: "plus filth fever", "plus mummy rot".
# Read against the block's own Disease entry by that name.
NAMED_DISEASES = ("filth fever", "mummy rot", "insidious mummy rot", "bog rot",
                  "red plague", "popobala fever", "devil chills", "ghoul fever")
# Save-or-be riders whose condition and length the block states.
SAVE_CONDITION_RIDERS = {"paralysis": "paralyzed", "paralyzing touch": "paralyzed",
                         "stun": "stunned"}
ABILITY_NAMES = {"str": "Strength", "dex": "Dexterity", "con": "Constitution",
                 "int": "Intelligence", "wis": "Wisdom", "cha": "Charisma"}
_ABILITY_WORD = {"str": "str", "strength": "str", "dex": "dex", "dexterity": "dex",
                 "con": "con", "constitution": "con", "int": "int", "intelligence": "int",
                 "wis": "wis", "wisdom": "wis", "cha": "cha", "charisma": "cha"}
# Handled elsewhere already: a swarm's distraction is `Engine._distraction`.
HANDLED_ELSEWHERE = ("distraction",)

# The units an affliction's onset, frequency and limit are printed in, as rounds — the
# executor's clock (`Actor.run_periodic`): "1/minute" is every 10 rounds, "1/hour" every
# 600. A day is its own clock (`per: "day"`), crossed by `Scene.advance` — a disease's
# "1/day" is not 14,400 played rounds.
ROUNDS_PER = {"round": 1, "minute": 10, "hour": 600}
DAY_UNITS = {"day": 1, "week": 7}

# The conditions an affliction's effect, or a save-or-be rider, can name, as the
# condition keys `rules/states.py` knows. "confusion for 1 round" is the confused
# condition; "sleep" and "unconsciousness" are unconscious.
_CONDITION_WORDS = {
    "paralyzed": "paralyzed", "paralysis": "paralyzed", "paralyze": "paralyzed",
    "staggered": "staggered", "nauseated": "nauseated", "nausea": "nauseated",
    "sickened": "sickened", "confused": "confused", "confusion": "confused",
    "dazed": "dazed", "daze": "dazed", "stunned": "stunned", "stun": "stunned",
    "fatigued": "fatigued", "fatigue": "fatigued",
    "exhausted": "exhausted", "blinded": "blinded", "blindness": "blinded",
    "deafened": "deafened", "deafness": "deafened", "shaken": "shaken",
    "frightened": "frightened", "panicked": "panicked", "entangled": "entangled",
    "unconscious": "unconscious", "unconsciousness": "unconscious",
    "sleep": "unconscious", "asleep": "unconscious", "dazzled": "dazzled",
    "slowed": "staggered",
}

_SEP = r"\s*[;,]\s*"
_UNIT = r"(round|minute|hour|day|week)s?"
# One affliction entry, after its heading ("Poison (Ex)", "Disease (Su) Ghoul Fever :").
# The cause runs to the em dash the book prints ("Bite—injury"); the PDF also gave "Swarm—
# injury" with a space after the dash, and en dashes and plain hyphens elsewhere.
#
# "Ash Leprosy : Injury; save Fort 23; ... frequency 1 day" (the ash giant) prints no cause,
# no "DC" and no slash; the cause, the word and the slash are optional for that reason.
_AFFLICTION = re.compile(
    r"(?:(?P<cause>[A-Za-z][\w ,'/()-]*?)\s*[—–-]\s*|(?<=:\s))"
    r"(?P<vector>(?:contact|ingested|inhaled|"
    r"injury)(?:\s+or\s+(?:contact|ingested|inhaled|injury))?)" + _SEP
    + r"save\s+(?:(?P<save>Fort(?:itude)?|Ref(?:lex)?|Will)\s+)?(?:DC\s*)?(?P<dc>\d+)"
    + r"(?:\s*\([^()]*\))?"
    + r"(?:" + _SEP + r"onset\s+(?P<onset>[^;,]+?))?"
    + _SEP + r"frequency\s+(?P<frequency>[^;,]+?)"
    + _SEP + r"effect\s+(?P<effect>.+?)"
    + r"(?:" + _SEP + r"cure\s+(?P<cure>[^.;]+?))?\s*(?:\.(?=\s|$)|$)", re.I)
# The heading in front of an affliction entry: "Poison (Ex)", "Disease (Su) Filth fever:".
_HEADING = re.compile(r"\b(?P<kind>poison|disease|curse(?: and disease)?)\s*\((?:ex|su|"
                      r"sp)\)\s*(?:(?P<name>[A-Z][\w' -]*?)\s*:\s*)?$", re.I)


def _clean(text) -> str:
    """One space, plain quotes, and the dashes the import left as HTML entities: the
    serpentfolk's "Bite&#8211;injury" (seven blocks) read as no poison at all."""
    out = " ".join(str(text or "").replace("’", "'").replace("&#8211;", "–")
                   .replace("&#8212;", "—").split())
    # "Injury—bite" (the couatl): the vector and the cause the other way round.
    return re.sub(r"\b(injury|contact|ingested|inhaled)\s*([—–])\s*([A-Za-z]+)(?=\s*;)",
                  r"\3\2\1", out, flags=re.I)


def _ability(word: str) -> str:
    return _ABILITY_WORD.get(str(word or "").strip().lower().rstrip("."), "")


def _span(text: str) -> dict | None:
    """"1d4+1 rounds" -> {"dice": "1d4+1", "unit": "round"}; "immediate" -> dice 0."""
    t = _clean(text).lower()
    if t.startswith("immediate"):
        return {"dice": "0", "unit": "round"}
    m = re.match(r"^(\d+d\d+(?:\s*[+-]\s*\d+)?|\d+)\s*" + _UNIT, t)
    if not m:
        return None
    return {"dice": m.group(1).replace(" ", ""), "unit": m.group(2)}


def _frequency(text: str) -> dict | None:
    """"1/round for 6 rounds" -> every 1 round, 6 times; "1/day" -> every day, until
    cured; "once" -> one save, no repeat."""
    t = _clean(text).lower().replace("/ ", "/")
    if t.startswith("once"):
        return {"unit": "round", "count": 1, "limit": "1"}
    m = re.match(r"^(\d+)\s*/?\s*" + _UNIT + r"(?:\s+for\s+(\d+d\d+(?:[+-]\d+)?|\d+)\s+"
                 + _UNIT + r")?", t)
    if not m:
        return None
    count, unit = int(m.group(1)), m.group(2)
    out = {"unit": unit, "count": max(1, count), "limit": None}
    if m.group(3):
        # "1/round for 6 rounds" is six saves; "1/hour for 6 hours" six; "1/round for 1
        # minute" ten. Counted in firings of the frequency, so the executor counts down.
        limit_unit = m.group(4)
        n = m.group(3)
        if limit_unit != unit and n.isdigit():
            scale = (ROUNDS_PER.get(limit_unit, 0) or DAY_UNITS.get(limit_unit, 0) * 14400)
            base = (ROUNDS_PER.get(unit, 0) or DAY_UNITS.get(unit, 0) * 14400)
            n = str(max(1, int(n) * scale // max(1, base)))
        out["limit"] = n
    return out


def _effects(text: str) -> tuple[list[dict], list[str]]:
    """An affliction's effect, piece by piece: ability damage and drain, hit point damage,
    a condition for a while. What no reader knows is returned as unread."""
    effects: list[dict] = []
    unread: list[str] = []
    t = _clean(text)
    # "(the duration of the paralysis is cumulative with each failed save)": a note, read
    # by nobody, kept out of the pieces so "the duration" is not an effect.
    t = re.sub(r"\([^()]*\)", " ", t)
    pieces = [p.strip(" .") for p in re.split(r"\s*(?:,|;|\band\b|\bplus\b|\bthen\b)\s*",
                                              t, flags=re.I) if p.strip(" .")]
    for piece in pieces:
        low = piece.lower()
        m = re.match(r"^(\d+d\d+(?:\s*[+-]\s*\d+)?|\d+)\s+(?:points?\s+of\s+)?"
                     r"(str|strength|dex|dexterity|con|constitution|int|intelligence|wis|"
                     r"wisdom|cha|charisma)\b(?:\s+(damage|drain))?", low)
        if m:
            effects.append({"ability": _ability(m.group(2)),
                            "dice": m.group(1).replace(" ", ""),
                            "drain": m.group(3) == "drain"})
            continue
        m = re.match(r"^(\d+d\d+(?:\s*[+-]\s*\d+)?|\d+)\s+(?:points?\s+of\s+)?"
                     r"(acid|cold|electricity|fire|sonic|negative energy|bludgeoning)?\s*"
                     r"damage\b", low)
        if m:
            effects.append({"damage": m.group(1).replace(" ", ""),
                            "type": (m.group(2) or "untyped").replace(" energy", "")})
            continue
        # "nauseated for 1 round", "paralysis for 1d4 rounds", "confusion for 1 round",
        # "sleep for 1 minute", "staggered" (no length: while the affliction runs, the
        # Bestiary's sense of an effect with no duration — it ends with the next save).
        # "daze 1 round" and "staggered 1 round" print no "for".
        m = re.match(r"^(?:(?:the\s+)?(?:target|victim)\s+is\s+)?(?P<word>[a-z]+)"
                     r"(?:\s+(?:(?:for|lasting)\s+)?(?P<span>\d+(?:d\d+)?(?:[+-]\d+)?\s+"
                     r"(?:round|minute|hour|day)s?))?$", low)
        if m and m.group("word") in _CONDITION_WORDS:
            eff = {"condition": _CONDITION_WORDS[m.group("word")]}
            span = _span(m.group("span") or "")
            if span:
                eff["for"] = span
            effects.append(eff)
            continue
        unread.append(piece)
    return effects, unread


def _cure(text) -> int | None:
    """"2 consecutive saves" -> 2; "1 save" -> 1; "—" or a spell -> None (no saves cure
    it: it runs to its limit, or until magic ends it)."""
    m = re.match(r"^\s*(\d+)\s+(?:consecutive\s+)?saves?\b", _clean(text).lower())
    return int(m.group(1)) if m else None


def afflictions(doc: dict) -> list[dict]:
    """Every affliction the block's Special Abilities define, read whole.

    Each: `kind` (poison, disease, curse), `name`, `cause` (the attack the book says
    delivers it: "Bite", "Sting or tentacles"), `vector`, `save`, `dc`, `onset`,
    `frequency`, `effects`, `unread`, `cure`, and `printed` — the entry as the book
    wrote it, for the report and the tells' sake.
    """
    text = _clean((doc or {}).get("special_abilities"))
    out: list[dict] = []
    for m in _AFFLICTION.finditer(text):
        lead = text[max(0, m.start() - 80):m.start()]
        cause = (m.group("cause") or "").strip()
        # The lazy cause starts wherever the scan does, so it can carry the heading in
        # front of it ("Poison (Ex) Bite"): the heading goes back to the lead.
        split = list(re.finditer(r"\((?:ex|su|sp)\)\s*", cause, re.I))
        if split:
            lead = lead + " " + cause[:split[-1].end()].strip()
            cause = cause[split[-1].end():].strip()
        if not cause:
            # "Ash Leprosy : Injury; ...": the name stands where the cause would.
            named = re.search(r"([A-Z][\w' -]{2,40}?)\s*:\s*$", lead)
            cause = f"{named.group(1).strip()}:" if named else ""
        # The heading is in front of the cause ("Poison (Ex) Bite—"), or the cause is
        # itself the named thing ("Ghoul Fever : Bite—" read with the name inside it).
        name = ""
        head = _HEADING.search(lead + " " if lead.endswith(":") else lead)
        if ":" in cause:
            name, cause = (x.strip() for x in cause.rsplit(":", 1))
        hm = re.search(r"\b(poison|disease|curse)\s*\((?:ex|su|sp)\)\s*([^()]*)$",
                       lead + " " + name, re.I)
        kind = (hm.group(1).lower() if hm else head.group("kind").lower() if head else "")
        if not kind:
            # The ash giant's heading is three sentences before its entry ("Disease (Su)
            # While ash giants are immune to disease, ... Ash Leprosy : Injury; ..."): the
            # last heading before the entry is the one it belongs to.
            back = text[max(0, m.start() - 400):m.start()]
            last = list(re.finditer(r"\b([A-Za-z]+)\s*\((?:ex|su|sp)\)", back, re.I))
            if last and last[-1].group(1).lower() in ("poison", "disease", "curse"):
                kind = last[-1].group(1).lower()
        if not name and hm:
            tail = hm.group(2).strip(" :")
            name = tail if tail and len(tail) < 40 else ""
        if not kind:
            low = (lead + " " + name).lower()
            kind = "disease" if "disease" in low or "fever" in low or "rot" in low \
                else "poison" if "poison" in low or "venom" in low else ""
        # "save DC 13" with no save named (the cultist troop): the UMRs' "usually a
        # Fortitude save" for poison and disease.
        save = (m.group("save") or "fort").lower()[:3]
        save = {"for": "fort", "ref": "ref", "wil": "will"}[save]
        effects, unread = _effects(m.group("effect"))
        out.append({
            "kind": kind or "poison", "name": name, "cause": cause,
            "vector": m.group("vector").lower(), "save": save, "dc": int(m.group("dc")),
            "onset": _span(m.group("onset") or "") if m.group("onset") else None,
            "frequency": _frequency(m.group("frequency")),
            "effects": effects, "unread": unread,
            "cure": _cure(m.group("cure") or ""),
            "printed": (m.group(0)[split[-1].end():] if split else m.group(0)).strip(),
        })
    return out


def _special(doc: dict, word: str) -> str | None:
    """The parenthesis after `word` in Special Attacks — "paralysis (1d4+1 rounds, DC 13,
    elves are immune to this effect)" -> "1d4+1 rounds, DC 13, ..." — "" when the word is
    there bare, None when it is not there at all. The PDF broke words across columns
    ("bur n (1d6, DC 14)", "poiso n"), so a space inside the word is allowed."""
    text = _clean((doc or {}).get("special_attacks"))
    loose = r"\s?".join(re.escape(ch) for ch in word.replace(" ", ""))
    m = re.search(r"\b" + loose + r"\b\s*(?:\((?P<inner>[^()]*)\))?", text, re.I)
    if not m:
        return None
    return m.group("inner") or ""


def _ability_entry(doc: dict, word: str) -> str:
    """The Special Abilities entry headed `word` ("Stun (Ex) ..."), to its next heading."""
    text = _clean((doc or {}).get("special_abilities"))
    m = re.search(r"\b" + re.escape(word) + r"\s*\((?:ex|su|sp)\)\s*(?P<body>.*?)"
                  r"(?=\s[A-Z][\w' -]{2,40}\s*\((?:Ex|Su|Sp)\)|$)", text, re.I)
    return m.group("body") if m else ""


def _dc_in(text: str) -> int | None:
    m = re.search(r"\bDC\s*(\d+)", text or "", re.I)
    return int(m.group(1)) if m else None


def _save_in(text: str, default: str = "fort") -> str:
    m = re.search(r"\b(Fortitude|Fort|Reflex|Ref|Will)\b", text or "", re.I)
    if not m:
        return default
    return {"for": "fort", "ref": "ref", "wil": "will"}[m.group(1).lower()[:3]]


def _matches_cause(cause: str, attack: dict) -> bool:
    """Does the affliction's cause ("Bite", "Sting or tentacles", "Swarm", "Spear") name
    this attack? By the attack's natural kind, its key and its singular."""
    from .statblock_attacks import singular

    words = set(re.findall(r"[a-z]+", str(cause or "").lower()))
    words |= {singular(w) for w in words}
    names = {str(attack.get(k) or "").lower() for k in ("kind", "key", "name", "base")}
    names |= {singular(n) for n in names if n}
    names |= {n.split()[-1] for n in names if n}
    return bool(words & names)


def _affliction_for(doc: dict, rider: str, attack: dict) -> dict | None:
    found = afflictions(doc)
    if not found:
        return None
    if rider in NAMED_DISEASES:
        named = [a for a in found if rider in (a["name"] or "").lower()]
        if named:
            return named[0]
    want = "poison" if rider == "poison" else "disease"
    of_kind = [a for a in found if a["kind"] == want
               or (want == "disease" and a["kind"].startswith("curse"))]
    # A rider names its kind; the cause picks between two of one kind (a pit fiend's
    # bite carries a disease and a poison, a linnorm's bite one poison and its tail none).
    by_cause = [a for a in of_kind if _matches_cause(a["cause"], attack)]
    if by_cause:
        return by_cause[0]
    if len(of_kind) == 1:
        return of_kind[0]
    return None


def _grab_size(doc: dict) -> dict:
    """Grab's reach in sizes. The UMR: "this ability works only against opponents of the
    same size category or smaller" unless the block says otherwise — "grab (Huge)" in
    Special Attacks, "can grab Huge or smaller foes", "works against creatures of any
    size category" (the behir), "a foe of up to one size category larger"."""
    inner = (_special(doc, "grab") or "").strip().lower()
    body = _ability_entry(doc, "grab").lower()
    from .tables import SIZE_ORDER

    if "any size" in body:
        return {"any_size": True}
    m = re.search(r"\b(" + "|".join(SIZE_ORDER) + r")\b", inner) or re.search(
        r"\bgrab\s+(" + "|".join(SIZE_ORDER) + r")\s+or\s+smaller", body)
    if m:
        return {"max_size": m.group(1)}
    if "one size category larger" in body:
        return {"larger_by": 1}
    racial = re.search(r"\+(\d+)\s+racial bonus on grapple", body)
    return {"bonus": int(racial.group(1))} if racial else {}


def _then_on_hold(doc: dict) -> list[dict]:
    """What a hold this creature establishes does at once: constrict ("dealing bludgeoning
    damage in addition to any other effects caused by a successful check", Constrict
    UMR) and blood drain ("drains blood at the end of its turn if it grapples a foe,
    dealing Constitution damage", Blood Drain UMR)."""
    out: list[dict] = []
    c = _special(doc, "constrict")
    if c is not None:
        m = re.search(r"(\d+d\d+(?:\s*[+-]\s*\d+)?)", c)
        if m:
            out.append({"kind": "constrict", "dice": m.group(1).replace(" ", "")})
        else:
            out.append({"kind": "unsupported", "rider": "constrict",
                        "why": "the block prints constrict with no damage"})
    b = _special(doc, "blood drain")
    if b is not None:
        m = re.search(r"(\d+d\d+|\d+)\s+(str|strength|con|constitution|dex|dexterity)", b,
                      re.I)
        if m:
            out.append({"kind": "blood_drain", "dice": m.group(1),
                        "ability": _ability(m.group(2))})
        else:
            # "inflicting 1 point of Strength and Constitution damage" (the giant leech):
            # the one amount to each score named.
            body = _ability_entry(doc, "blood drain")
            m = re.search(r"(\d+d\d+|\d+)\s+points?\s+of\s+((?:Strength|Constitution)"
                          r"(?:\s+and\s+(?:Strength|Constitution))?)", body, re.I)
            if m:
                for word in re.findall(r"Strength|Constitution", m.group(2), re.I):
                    out.append({"kind": "blood_drain", "dice": m.group(1),
                                "ability": _ability(word)})
            else:
                out.append({"kind": "unsupported", "rider": "blood drain",
                            "why": "the block prints blood drain with no amount"})
    return out


def rule_for(doc: dict, rider: str, attack: dict) -> dict:
    """One rider word on one attack, as the document the engine applies.

    Always a dict with `rider` (the word as printed) and `kind`; `kind: "unsupported"`
    carries `why`, so a rider the engine cannot apply is said, never dropped.
    """
    word = " ".join(str(rider or "").lower().split())
    base = {"rider": word}
    amounts = attack.get("amounts") or {}
    if word in HANDLED_ELSEWHERE:
        return {**base, "kind": word}
    if word in MANEUVER_RIDERS:
        rule = {**base, "kind": "maneuver", **MANEUVER_RIDERS[word]}
        if word == "grab":
            rule.update(_grab_size(doc))
            rule["then"] = _then_on_hold(doc)
        if word in ("pull", "push"):
            inner = _special(doc, word) or ""
            m = re.search(r"(\d+)\s*f(?:ee)?\s?t", inner.replace(" ", ""), re.I) or \
                re.search(r"(\d+)\s*f\s?(?:ee)?\s?t", inner, re.I)
            rule["feet"] = int(m.group(1)) if m else 5
        return rule
    if word == "attach":
        # "The creature latches on when it hits with the listed attack. The creature is
        # grappled, but the target is not." (Attach UMR). And what a hold does, it does.
        return {**base, "kind": "attach", "then": _then_on_hold(doc)}
    if word in AFFLICTION_RIDERS or word in NAMED_DISEASES:
        aff = _affliction_for(doc, word, attack)
        if aff is None and attack.get("base") and word == "poison":
            # "mwk kukri +9 (1d4/18-20 plus poison)": a dose put on the blade, bought, and
            # listed in the gear line — the creature's equipment, not its body. 72 of the
            # 76 undefined poisons on 2026-10-30 were weapons like this.
            return {**base, "kind": "unsupported",
                    "why": "a poison applied to a made weapon: the dose is gear, and a "
                           "coating from the gear line is not read yet"}
        if aff is None:
            return {**base, "kind": "unsupported",
                    "why": f"the block names {word} on this attack and prints no "
                           f"{'Poison' if word == 'poison' else 'Disease'} entry that "
                           f"defines it (save, frequency, effect)"}
        if aff["frequency"] is None:
            return {**base, "kind": "unsupported",
                    "why": f"the {word}'s frequency could not be read: {aff['printed']!r}"}
        if not aff["effects"]:
            return {**base, "kind": "unsupported",
                    "why": f"the {word}'s effect could not be read: {aff['printed']!r}"}
        return {**base, "kind": "affliction", "affliction": aff}
    if word in SAVE_CONDITION_RIDERS:
        return _save_condition(doc, word, attack)
    if word == "bleed" or re.fullmatch(r"bleed \d+", word):
        amount = amounts.get("bleed") or (word.split()[1] if " " in word else "")
        if not amount:
            # "bleed (1d6)", "bleed (1)"; never "bleed (DC 13)", which is the Heal check.
            m = re.match(r"\s*(\d+d\d+(?:[+-]\d+)?|\d+)\s*$", _special(doc, "bleed") or "")
            amount = m.group(1) if m else ""
        if not amount:
            body = _ability_entry(doc, "bleed")
            m = re.search(r"(\d+d\d+|\d+)\s+(?:points?\s+of\s+)?bleed", body, re.I)
            amount = m.group(1) if m else ""
        if not amount:
            return {**base, "kind": "unsupported",
                    "why": "the block prints bleed with no amount"}
        return {**base, "kind": "bleed", "amount": amount}
    if word == "burn":
        inner = _special(doc, "burn")
        m = re.match(r"\s*(\d+d\d+(?:[+-]\d+)?)", inner or "")
        if not m:
            return {**base, "kind": "unsupported",
                    "why": "the block prints burn with no damage"}
        return {**base, "kind": "burn", "dice": m.group(1), "save": "ref",
                "dc": _dc_in(inner or ""), "dc_ability": "con"}
    if word == "energy drain":
        inner = _special(doc, "energy drain") or ""
        m = re.search(r"(\d+d\d+|\d+)\s+(?:negative\s+)?levels?", inner, re.I)
        body = _ability_entry(doc, "energy drain")
        if not m:
            m = re.search(r"(\d+d\d+|\d+)\s+negative\s+levels?", body, re.I)
        return {**base, "kind": "energy_drain", "levels": m.group(1) if m else "1",
                "dc": _dc_in(inner) or _dc_in(body), "dc_ability": "cha"}
    m = re.fullmatch(r"(str|dex|con|int|wis|cha) (damage|drain)", word)
    if m:
        amount = amounts.get(word)
        if not amount:
            return {**base, "kind": "unsupported", "why": "no amount was printed"}
        return {**base, "kind": "ability", "ability": m.group(1), "dice": amount,
                "drain": m.group(2) == "drain"}
    if word == "blood drain":
        got = [t for t in _then_on_hold(doc) if t["kind"] == "blood_drain"]
        if got:
            return {**base, **got[0]}
    return {**base, "kind": "unsupported",
            "why": f"no rule here applies {word!r} yet"}


def _save_condition(doc: dict, word: str, attack: dict) -> dict:
    """Paralysis and stun: a save or the condition, for as long as the block says.

    Paralysis (Bestiary UMR): "paralysis (1d4 rounds, DC 18)"; "unlike hold person ... does
    not permit saving throws each round"; the save "typically a Fortitude save (DC 10 +
    1/2 the creature's racial HD + Constitution modifier)". The ghoul's adds "elves are
    immune to this effect". Stun has no universal rule: each block defines its own
    ("must make a DC 23 save or be dazed for 1 round"), and without that entry it is not
    applied.
    """
    base = {"rider": word}
    condition = SAVE_CONDITION_RIDERS[word]
    inner = _special(doc, "paralysis" if condition == "paralyzed" else word) or ""
    head = "Paralysis" if condition == "paralyzed" else word.title()
    body = _ability_entry(doc, head) or (_ability_entry(doc, "paralyzing touch")
                                         if word == "paralyzing touch" else "")
    span = None
    m = re.search(r"(\d+d\d+(?:\s*[+-]\s*\d+)?|\d+)\s*(round|minute|hour)s?", inner, re.I)
    if m:
        span = {"dice": m.group(1).replace(" ", ""), "unit": m.group(2).lower()}
    m2 = re.search(r"\bor\s+(?:be\s+)?(?:become\s+)?(?P<cond>[a-z]+)\s+for\s+"
                   r"(?P<span>\d+(?:d\d+)?(?:\s*[+-]\s*\d+)?\s+(?:round|minute|hour)s?)",
                   body, re.I)
    if m2 and m2.group("cond").lower() in _CONDITION_WORDS:
        condition = _CONDITION_WORDS[m2.group("cond").lower()]
        span = span or _span(m2.group("span"))
    dc = _dc_in(inner) or _dc_in(body)
    if word == "stun" and (dc is None or not body):
        return {**base, "kind": "unsupported",
                "why": "stun has no universal monster rule and the block defines none here"}
    # "If an astral deva strikes an opponent twice in one round": a stun that needs two
    # hits is a rule about the round, not this hit.
    if re.search(r"\btwice\b|\btwo\b.*\bhits?\b|\bcritical\b", body, re.I) and word == "stun":
        return {**base, "kind": "unsupported",
                "why": f"this block's stun is conditional: {body[:120]!r}"}
    if span is None:
        # "Specific duration varies by creature" (Paralysis UMR): a block that prints none
        # has none to apply, and one is not made up.
        return {**base, "kind": "unsupported",
                "why": f"the block prints {word} with no duration"}
    immune = []
    for race, words in (("elf", r"\belves\b"), ("dwarf", r"\bdwarves\b")):
        if re.search(words + r"[^.]*\bimmune\b", inner + " " + body, re.I):
            immune.append(race)
    return {**base, "kind": "save_condition", "condition": condition,
            "save": _save_in(body or inner, "fort"), "dc": dc,
            "dc_ability": "con", "for": span, "immune_races": immune}


def rules_for(doc: dict, attack: dict) -> list[dict]:
    """The rider documents for one printed attack, in the order the book prints them."""
    return [rule_for(doc, r, attack) for r in attack.get("riders") or ()]


def unsupported(rules) -> list[str]:
    """The rider words in a list of rules the engine will not apply, for the counts."""
    return [r["rider"] for r in rules or () if r.get("kind") == "unsupported"]

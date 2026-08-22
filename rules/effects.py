"""Sifting the mechanics out of an ingredient's description.

The herb document is written for a person: "When dried and ground into a powder, the
mottled red and gray bark of this shrub is a boon to healers. When applied to a wound,
leechwort grants a +1 alchemical bonus on all Heal checks and a +2 alchemical bonus on
Heal checks to staunch bleeding." Two sentences, one of which is scene-setting and one of
which contains the only two numbers that matter.

Printing the whole paragraph as a crafted item's effect is what a recipe card must not do.
The card has to say *+1 Heal, +2 Heal to staunch bleeding* and keep the prose for whoever
wants it.

This is extraction, not interpretation. Every effect here is anchored on a number, a save,
a named condition or a named 1e mechanic, because those are the parts the engine and the
player can act on. Anything a pattern cannot claim is left in the description rather than
guessed at — a paraphrase that quietly drops a clause is worse than a paragraph.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .tables import ABILITY_FULL, CONDITIONS, SKILLS

# 1e's bonus types. Named so "+2 alchemical bonus on Heal checks" collapses to "+2 Heal"
# without the type being mistaken for the thing bonused.
BONUS_TYPES = (
    "alchemical", "circumstance", "competence", "deflection", "dodge", "enhancement",
    "inherent", "insight", "luck", "morale", "natural armor", "natural armour",
    "profane", "racial", "resistance", "sacred", "shield", "size", "untyped",
)

DAMAGE_KINDS = ("fire", "cold", "acid", "electricity", "sonic", "poison", "negative",
                "positive", "force", "bludgeoning", "piercing", "slashing", "subdual",
                "nonlethal", "non-lethal", "bleed")

SAVES = {"fort": "Fortitude", "fortitude": "Fortitude", "ref": "Reflex",
         "reflex": "Reflex", "will": "Will"}

_DIE = r"\d+d\d+(?:\s*[+\-]\s*\d+)?|\d+\s*-\s*\d+|\d+"
_TYPES = "|".join(BONUS_TYPES)


@dataclass
class Effect:
    kind: str          # bonus | penalty | heal | damage | ability | save | condition | ...
    text: str          # what the card shows
    scales: bool = False   # whether a chain's potency multiplier applies to it
    # The same finding as an authored effect (rules/effectspec.py). One parse, two
    # outputs: the line a card shows and the record an editor can open and correct.
    # Empty when the pattern found something no authored type can hold.
    spec: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"kind": self.kind, "text": self.text, "scales": self.scales,
                "spec": self.spec}


# Where a card line may end. Longer than this and it is a sentence, not a label.
CARD_CHARS = 52


def _clip(s: str) -> str:
    """Cut to a readable label on a word boundary.

    Measured: "+2 Constitution checks made to resist subdual damage from making a forced"
    stopped mid-phrase at the raw character cap, which reads as a bug on the card.
    """
    s = s.strip()
    if len(s) <= CARD_CHARS:
        return s
    # Prefer cutting at a clause joint; fall back to the last whole word.
    for joint in (" made to ", " when ", " while ", " from ", " for ", " that ", " which "):
        cut = s.lower().find(joint)
        if 12 <= cut <= CARD_CHARS:
            return s[:cut].strip()
    cut = s.rfind(" ", 0, CARD_CHARS)
    return (s[:cut] if cut > 12 else s[:CARD_CHARS]).strip() + "…"


def _target(s: str) -> str:
    """What a bonus applies to, cleaned for a label.

    Cleaned *before* the sign is attached: doing it after left "+1 all Heal checks",
    because the leading-word strip only ever looked at the front of the whole string and
    the front was "+1".
    """
    s = re.sub(r"\s+", " ", s or "").strip(" .,;:")
    s = re.sub(r"^(?:on|to|against|vs\.?|for)\s+", "", s, flags=re.I)
    s = re.sub(r"^(?:all|any)\s+", "", s, flags=re.I)
    # Trailing pointers back into the prose that mean nothing on a card of their own.
    s = re.sub(r"\s+(?:during|for|in|of)\s+(?:this|that|the)\s+"
               r"(?:time|duration|manner|way|period)\b.*$", "", s, flags=re.I)
    return s.strip(" .,;:")


def _tidy(s: str) -> str:
    return _clip(_target(s))


def _dur(text: str) -> str:
    m = re.search(r"\bfor\s+(" + _DIE + r"|one|two|three|four|six|eight|ten|twelve|24)\s*"
                  r"(round|minute|hour|day|week|month)s?\b", text, re.I)
    if not m:
        return ""
    return f"{m.group(1)} {m.group(2)}{'' if m.group(1) in ('one', '1') else 's'}"


# A condition is written as a noun as often as an adjective. The stem is matched and the
# endings allowed, so "confusion" finds `confused` and "unconsciousness" finds
# `unconscious` — without which Mad Cap, whose whole effect is a rage then a coma,
# extracted nothing but its DC.
# Written as explicit endings rather than a loose `\w*`, because a loose stem is how
# "deadly nightshade" became *Causes dead* — the worst kind of wrong, a mechanic on a card
# that the source never claimed.
_CONDITION_STEMS = {
    "confused": r"confus(?:ed|ion)",
    "unconscious": r"unconscious(?:ness)?|comatose|\bcoma\b",
    "nauseated": r"nause(?:a|ated|ous)",
    "sickened": r"sicken(?:ed|s|ing)?|sickness",
    "fatigued": r"fatigu(?:e|ed|es)",
    "exhausted": r"exhaust(?:ed|ion)",
    "paralyzed": r"paraly(?:zed|sed|sis)",
    "frightened": r"frighten(?:ed|s)?",
    "panicked": r"panick(?:ed|s)?",
    "staggered": r"stagger(?:ed|s)?",
    "stunned": r"stun(?:ned|s)?",
    "blinded": r"blind(?:ed|ness)?",
    "deafened": r"deafen(?:ed|s)?|deafness",
    "dazzled": r"dazzl(?:ed|es)?",
    "dazed": r"daze[ds]?",
    "shaken": r"shaken",
    "entangled": r"entangl(?:ed|es)?",
    "grappled": r"grappl(?:ed|es)?",
    "prone": r"prone",
    "helpless": r"helpless",
    "cowering": r"cower(?:ing|s)?",
    "fascinated": r"fascinat(?:ed|es)?",
    "dying": r"dying",
    "disabled": r"disabled",
    # "deadly" is not death. Bounded on purpose.
    "dead": r"dead\b|\bdies\b|\bslain\b",
}

# Verbs that genuinely undo a condition. "end" is deliberately absent: Allnight says
# "when the drug's effect ends, the user is exhausted", and reading that as *Ends
# exhausted* inverts the entire effect of the herb.
_CURES = r"cure|remove|negat|eliminat|immune|resist|ward off|throw off|prevent|relieve"


def _condition_pattern(key: str) -> str:
    """A word-boundaried stem match.

    This line was once written through a shell heredoc and the `\\b` arrived as a literal
    backspace byte — the pattern then matched nothing at all, silently, and every
    condition in the corpus went unextracted. It is the exact trap CLAUDE.md records, and
    it fails without raising. `tests/test_effects.py` asserts no control characters
    survive in this module.
    """
    stem = _CONDITION_STEMS.get(key)
    if stem is None:
        return rf"\b{re.escape(key)}\w*"
    # Not escaped: the table holds patterns, not literals. Escaping them turned
    # `confus(?:ed|ion)` into a search for that exact punctuation and every condition
    # stopped matching at once.
    return rf"\b(?:{stem})"


def _save_id(word: str) -> str:
    """"Fortitude" -> "fort", which is what the save dropdown stores."""
    w = (word or "").strip().lower()
    return {"fortitude": "fort", "reflex": "ref"}.get(w, w)


def _duration_spec(text: str) -> dict:
    """The duration as the editor stores it, rather than as a phrase."""
    m = re.search(r"\bfor\s+(" + _DIE + r")\s*"
                  r"(round|minute|hour|day|week|month)s?\b", text, re.I)
    if not m:
        return {}
    return {"amount": re.sub(r"\s+", "", m.group(1)), "unit": m.group(2).lower()}


def _qualifier(target: str, matched: str) -> str:
    """What is left of a bonus target once the thing it names is removed.

    "Heal checks to staunch bleeding" minus the Heal skill is "to staunch bleeding" —
    which is the entire difference between one entry's two bonuses.

    Both the stored id and the word a person writes are stripped. Removing only the id
    left "Constitution" behind when the match was `con`, and the line read
    "+2 Constitution Constitution".
    """
    words = {matched, ABILITY_FULL.get(matched, ""),
             {"fort": "fortitude", "ref": "reflex"}.get(matched, "")}
    rest = target
    for w in sorted((w for w in words if w), key=len, reverse=True):
        rest = re.sub(rf"\b{re.escape(w)}\w*", "", rest, flags=re.I)
    rest = re.sub(r"\b(?:checks?|rolls?|saves?|based)\b", "", rest, flags=re.I)
    rest = re.sub(r"[-–]\s*", " ", rest)
    rest = re.sub(r"\s+", " ", rest).strip(" .,;:")
    return rest if len(rest) > 2 else ""


def _modifier_type(target: str) -> tuple[str, str]:
    """Which modifier form a bonus belongs in, and the id its target dropdown wants.

    The corpus writes targets in words — "Heal checks", "saves vs fear", "attack rolls" —
    and each maps to a different vocabulary. Anything unrecognised becomes a situational
    modifier, which is the honest home for "checks to resist a forced march": a real
    effect the engine cannot compute, kept rather than dropped.
    """
    low = (target or "").lower()
    for key in SKILLS:
        if re.search(rf"\b{re.escape(key)}\b", low):
            return "skill_mod", key
    for key, name in ABILITY_FULL.items():
        if re.search(rf"\b(?:{key}|{name.lower()})\b", low):
            return "ability_mod", key
    for key, name in (("fort", "fortitude"), ("ref", "reflex"), ("will", "will")):
        if re.search(rf"\b(?:{key}|{name})\b", low):
            return "save_mod", key
    for key, words in (("attack", r"attack|to.hit"), ("damage", r"damage roll"),
                       ("ac", r"\bac\b|armou?r class"), ("cmb", r"\bcmb\b"),
                       ("cmd", r"\bcmd\b"), ("initiative", r"initiative"),
                       ("caster_level", r"caster level"),
                       ("spell_resistance", r"spell resistance")):
        if re.search(words, low):
            return "combat_mod", key
    return "situational_mod", target


def extract(text: str) -> list[Effect]:
    """The mechanical claims in a description, in the order they are made."""
    out: list[Effect] = []
    seen: set[str] = set()

    def add(kind: str, body: str, scales: bool = False, spec: dict | None = None):
        body = _tidy(body)
        if not body or body.lower() in seen:
            return
        seen.add(body.lower())
        out.append(Effect(kind, body, scales, spec=spec or {}))

    if not text:
        return out
    # The target of a bonus stops at a full stop, and "saves vs. fear" has one in the
    # middle of it — the label came out as "+2 saves vs". Normalised before matching
    # rather than special-cased in six patterns.
    text = re.sub(r"\bvs\.", "vs", text)
    duration = _dur(text)
    tail = f" for {duration}" if duration else ""
    dspec = _duration_spec(text)

    # Bonuses and penalties: "+2 alchemical bonus on Heal checks to staunch bleeding".
    for m in re.finditer(
        rf"([+\-–−]\s*\d+)\s*(?:{_TYPES})?\s*(bonus|penalty)\s+"
        rf"(?:on|to|against|vs\.?)\s+"
        rf"((?:(?!\s+and\s+an?\s*[+\-–−]\s*\d)[^.;)]){{2,90}})", text, re.I
    ):
        sign = m.group(1).replace(" ", "").replace("–", "-").replace("−", "-")
        if m.group(2).lower() == "penalty" and not sign.startswith("-"):
            sign = "-" + sign.lstrip("+")
        # Clipped before it reaches the spec, not only before the card line. A situational
        # target keeps its raw words, and one of them ran on into the next clause —
        # "+3 saves against chaotic magic, but the user becomes prone to erratic behavior"
        # — then had the duration appended to that.
        target = _clip(_target(m.group(3)))
        mtype, mtarget = _modifier_type(target)
        # "Heal checks to staunch bleeding" matches the Heal skill, and the qualifier is
        # the whole difference between Leechwort's two bonuses. Matching the skill and
        # dropping the rest turned them into the same effect twice.
        qualifier = _qualifier(target, mtarget) if mtype != "situational_mod" else ""
        btype = re.search(rf"({_TYPES})", m.group(0), re.I)
        # A duration already spelled out in the target must not be added a second time.
        # Word numbers too: Nightshade grants "+4 bonus to all Reflex saves for nine
        # hours", and a digits-only guard appended the sentence's other duration on top
        # of it — "+4 Reflex for nine hours for 30 minutes".
        carries_own = bool(re.search(
            r"\bfor\s+(?:\d|one|two|three|four|five|six|seven|eight|nine|ten|twelve|"
            r"twenty|thirty|sixty)", target, re.I))
        add("penalty" if sign.startswith("-") else "bonus", f"{sign} {target}",
            spec={"type": mtype, "amount": int(sign), "target": mtarget,
                  "bonus_type": (btype.group(1).lower() if btype else "untyped"),
                  **({"note": qualifier} if qualifier else {}),
                  **({"duration": dspec} if dspec and not carries_own else {})})

    # Healing. "restores 1d4 hit points", "heals 1d6 points of fire damage".
    for m in re.finditer(
        rf"\b(?:heal(?:s|ing)?|restor(?:es?|ing)|regain(?:s|ing)?|"
        rf"recover(?:s|ing)?|returns?|cures?)\s+"
        rf"(?:up to\s+)?({_DIE})\s*(?:points?\s+of\s+)?"
        rf"(?:(\w+)\s+)?(?:hit points?|hp|damage)\b", text, re.I
    ):
        kind = (m.group(2) or "").lower()
        what = f"{kind} damage" if kind in DAMAGE_KINDS else "hit points"
        nonlethal = kind in ("subdual", "nonlethal", "non-lethal")
        add("heal", f"Heals {m.group(1)} {what}", scales=True,
            spec={"type": "heal", "dice": m.group(1),
                  **({"lethality": "nonlethal"} if nonlethal else {})})

    # "roll 1-4 to see how many hit points were never done in the first place" — this
    # corpus states a good deal of its healing as an instruction to roll rather than as a
    # verb, and Comfrey and St John's-Wort say nothing else mechanical at all.
    for m in re.finditer(rf"\broll\s+({_DIE})\b[^.;]{{0,60}}?hit points?", text, re.I):
        add("heal", f"Heals {m.group(1)} hit points", scales=True,
            spec={"type": "heal", "dice": m.group(1)})

    # Percentages, which 1e does not use and this document does: "Bleeding damage is
    # considered 20% less", "heal 25% more quickly".
    for m in re.finditer(r"([^.;,]{3,44}?)\s+(?:is|are)?\s*(?:considered\s+)?"
                         r"(\d+)%\s+(less|more|faster|quicker|longer)", text, re.I):
        # No authored type holds a percentage; 1e has none. Kept as narrative so the
        # claim survives conversion instead of being dropped for want of a slot.
        add("percent", f"{_target(m.group(1))} {m.group(2)}% {m.group(3).lower()}",
            spec={"type": "narrative",
                  "target": f"{_target(m.group(1))} {m.group(2)}% "
                            f"{m.group(3).lower()}"})

    # Temporary hit points, fast healing — named mechanics the engine has.
    for m in re.finditer(rf"({_DIE})\s+temporary hit points?", text, re.I):
        add("temp_hp", f"{m.group(1)} temporary hit points{tail}", scales=True,
            spec={"type": "temp_hp", "dice": m.group(1),
                  **({"duration": dspec} if dspec else {})})
    for m in re.finditer(r"fast healing\s+(\d+)", text, re.I):
        add("fast_healing", f"Fast healing {m.group(1)}{tail}", scales=True,
            spec={"type": "fast_healing", "amount": int(m.group(1)),
                  **({"duration": dspec} if dspec else {})})

    # Ability score damage, which is not hit point damage and must not read like it.
    for m in re.finditer(
        rf"({_DIE})\s+(?:points?\s+of\s+)?(?:(temporary|permanent)\s+)?"
        rf"({'|'.join(list(ABILITY_FULL) + [v for v in ABILITY_FULL.values()])})\s+"
        rf"(damage|drain)", text, re.I
    ):
        word = m.group(3).lower()[:3]
        add("ability", f"{m.group(1)} {ABILITY_FULL[word]} "
                       f"{'drain' if m.group(4).lower() == 'drain' else 'damage'}"
                       + (" (permanent)" if (m.group(2) or "").lower() == "permanent" else ""),
            scales=True,
            spec={"type": "ability_drain" if m.group(4).lower() == "drain"
                          else "ability_damage",
                  "target": word, "dice": m.group(1)})

    # Damage dealt, when it is not healing and not an ability score.
    for m in re.finditer(rf"\b({_DIE})\s*(?:points? of\s+)?({'|'.join(DAMAGE_KINDS)})\s+damage",
                         text, re.I):
        if re.search(rf"(?:heals?|restores?|regains?|recovers?|cures?)\s+{re.escape(m.group(1))}",
                     text, re.I):
            continue
        add("damage", f"{m.group(1)} {m.group(2).lower()} damage", scales=True,
            # Subdual is a lethality, not a damage type. Recording it in both places is
            # how one fact ends up disagreeing with itself.
            spec={"type": "damage", "dice": m.group(1),
                  "damage_type": "untyped"
                  if m.group(2).lower() in ("subdual", "nonlethal", "non-lethal")
                  else m.group(2).lower(),
                  "lethality": "nonlethal"
                  if m.group(2).lower() in ("subdual", "nonlethal", "non-lethal")
                  else "lethal"})

    # Saves the effect calls for, and their DCs.
    for m in re.finditer(r"\b(Fort(?:itude)?|Ref(?:lex)?|Will)\s*(?:save)?\s*"
                         r"(?:\(\s*)?DC:?\s*(\d+)", text, re.I):
        add("save", f"{SAVES[m.group(1).lower()]} DC {m.group(2)}",
            spec={"type": "save_gate", "target": _save_id(m.group(1)),
                  "dc": int(m.group(2))})
    if not any(e.kind == "save" for e in out):
        m = re.search(r"\bDC:?\s*(\d+)", text)
        if m:
            add("save", f"DC {m.group(1)}",
                # No `target`: the source gives a DC and never says which save, and
                # choosing one would put a fact on the card that nobody wrote.
                spec={"type": "save_gate", "dc": int(m.group(1)),
                      "note": "the source names a DC without saying which save"})

    # An extra saving throw granted, which is a real and easily-missed effect.
    for m in re.finditer(r"\b(?:gain|grant|allow)\w*\s+(?:a|an|another)\s+"
                         r"(?:immediate\s+)?(Fort(?:itude)?|Ref(?:lex)?|Will)\s+save"
                         r"(?:\s+(?:vs\.?|against)\s+([^.;)]{2,45}))?", text, re.I):
        against = _tidy(m.group(2) or "")
        # An extra save is a permission, not a roll the engine makes on its own.
        add("save", f"Another {SAVES[m.group(1).lower()]} save"
                    + (f" vs. {against}" if against else ""),
            spec={"type": "permission",
                  "target": f"another {SAVES[m.group(1).lower()]} save"
                            + (f" against {against}" if against else "")})

    # Resistance and immunity, both of which 1e states as flat numbers or absolutes.
    for m in re.finditer(r"resistance to (\w+) damage(?:\s*\((\d+)\s*points?\))?", text, re.I):
        add("resistance", f"Resist {m.group(1).lower()}"
                          + (f" {m.group(2)}" if m.group(2) else "") + tail,
            spec={"type": "resistance", "target": m.group(1).lower(),
                  "amount": int(m.group(2)) if m.group(2) else 0,
                  **({"duration": dspec} if dspec else {})})
    for m in re.finditer(r"(\d+)\s+points? of resistance (?:to|against) (\w+)", text, re.I):
        add("resistance", f"Resist {m.group(2).lower()} {m.group(1)}{tail}",
            spec={"type": "resistance", "target": m.group(2).lower(),
                  "amount": int(m.group(1)),
                  **({"duration": dspec} if dspec else {})})
    for m in re.finditer(r"immunit(?:y|ies) to ([^.;)]{2,45})", text, re.I):
        # The capture usually swallows the duration, so appending the tail as well gave
        # "Immune to fire damage for 2 hours for 2 hours".
        what = re.sub(r"\s+for\s+.*$", "", _tidy(m.group(1)), flags=re.I)
        add("immunity", f"Immune to {what}{tail}",
            spec={"type": "immunity", "target": what,
                  **({"duration": dspec} if dspec else {})})

    # Conditions the effect inflicts or removes, matched on the stem so the document's
    # nouns find the engine's adjectives.
    #
    # Read sentence by sentence, and the duration taken from the sentence the condition is
    # in. A document-wide duration was attached to everything: Hydra Gall heals "1d4 HP
    # per round for 5 rounds" and separately causes nausea for an hour, and the card
    # confidently said the nausea lasted five rounds.
    for sentence in re.split(r"(?<=[.;])\s+", text):
        # Only when the sentence states one duration. Hydra Gall heals "for 5 rounds" and
        # sickens "for 1 hour" in a single sentence, and attaching the first to the
        # condition was a confidently wrong number. Saying nothing is the honest answer.
        durations = re.findall(r"\bfor\s+(?:" + _DIE + r"|one|two|three|four|six|eight|"
                               r"ten|twelve|24)\s*(?:round|minute|hour|day|week|month)s?",
                               sentence, re.I)
        local = _dur(sentence) if len(durations) == 1 else ""
        local_tail = f" for {local}" if local else ""
        for key, data in CONDITIONS.items():
            name = data.get("name", key)
            stem = _condition_pattern(key)
            if not re.search(stem, sentence, re.I):
                continue
            if re.search(rf"\b(?:{_CURES})\w*[^.;]{{0,40}}{stem}", sentence, re.I):
                add("condition", f"Ends {name.lower()}",
                    spec={"type": "remove_condition", "target": key})
            else:
                add("condition", f"Causes {name.lower()}{local_tail}",
                    spec={"type": "apply_condition", "target": key,
                          **({"duration": _duration_spec(sentence)}
                             if local else {})})

    return out


def summarise(text: str) -> list[str]:
    return [e.text for e in extract(text)]

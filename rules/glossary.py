"""What every named thing on the character sheet actually does.

"as of right now there is nowhere the user can look to see what any of the blood bender
abilities actually do" — the Class tab's path blocks carried the full text, but the level
table's grants, the class-features list and the racial traits were bare names. This
gathers one dictionary per character, `name → {text, source}`, and the sheet draws a
popover from it wherever a name appears.

Sources, in the order they win: the class's own path abilities and upgrades (the
document's text, verbatim), the class-wide entries below (written from the class data's
own statements — the summary, the overrides' whys), and the core-rules entries (CRB
paraphrase, one line each). A name none of them know gets an honest "the source does not
define it" from the page rather than an invented rule here.
"""
from __future__ import annotations

import re

# Core Rulebook features that appear on class tables as bare names. One line each,
# paraphrased — the point is "what is this", not the full rules text.
CORE = {
    "evasion": "On a successful Reflex save against an effect that allows half damage, "
               "take none instead. Light or no armour only.",
    "improved evasion": "As evasion, and even a failed Reflex save only deals half.",
    "uncanny dodge": "Never caught flat-footed by being surprised or attacked by an "
                     "unseen foe; keep your Dex bonus to AC.",
    "improved uncanny dodge": "As uncanny dodge, and you cannot be flanked except by a "
                              "rogue at least four levels higher.",
    "bonus feat": "An extra feat, chosen when the level is taken.",
    "unarmed strike": "Your fists are weapons: no attacks of opportunity for striking "
                      "unarmed, and the damage scales with level (the Fist column).",
    "darkvision": "See in total darkness, in black and white, to the listed range.",
    "darkvision 60 ft": "See in total darkness, in black and white, to 60 feet.",
    "ferocity": "Below 0 hit points you stay conscious and may keep acting, though "
                "staggered; you still die at the usual point.",
    "ferocity: keep fighting below 0": "Below 0 hit points you stay conscious and may "
                                       "keep acting, though staggered.",
    "fast movement": "A bonus to base land speed, already counted in the Speed line.",
    "trapfinding": "Perception to find, and Disable Device to disarm, traps of every "
                   "kind — including magical ones.",
    "sneak attack": "Extra dice of damage when the target is denied its Dex bonus or "
                    "you flank it.",
    "rage": "A pool of rounds of raging: +4 Str, +4 Con, +2 Will, -2 AC while it lasts.",
}

# The Blood Bending class-wide machinery, written from the class data's own statements
# rather than invented: the summary states the economy, the overrides state Blood Bond,
# and the paths' own text uses Blood Sense as a range.
BLOOD_BENDING = {
    "blood bond": "The class's whole economy: abilities are paid for in self-inflicted "
                  "non-lethal damage, and temporary hit points from its abilities stack "
                  "rather than overlap.",
    "blood sense": "The radius the class works in. Abilities that reach 'within Blood "
                   "Sense range' use this; the range grows with the levels that grant it.",
    "blood sense 60ft": "Sense and work blood within 60 feet. Abilities that reach "
                        "'within Blood Sense range' use this radius.",
    "control blood": "The class's tiering. Path abilities unlock by Control Blood level "
                     "(1a-5b): the letter is the path slot, the number its tier.",
    "blood dmg": "The Blood column on the class table — the damage die the class's own "
                 "abilities roll, separate from fist damage.",
}


def _clean(name: str) -> str:
    """A grant as written down to a glossary key: "control blood 1a" asks for "control
    blood", "blood sense 60ft" for itself and then "blood sense"."""
    return " ".join(str(name or "").lower().split())


def build(actor) -> dict:
    """Every name this character's sheet might show, with its text.

    Keys are lower-cased names; the page looks up case-insensitively and falls back to
    progressively shorter prefixes, so a table grant with a number on the end still
    finds its family entry.
    """
    out: dict[str, dict] = {}

    def add(name, text, source):
        key = _clean(name)
        if key and text and key not in out:
            out[key] = {"name": str(name), "text": str(text), "source": source}

    for key, text in CORE.items():
        add(key, text, "Core Rulebook")

    cls = getattr(actor, "class_data", None) or {}
    cls_name = cls.get("name", "the class")
    if str(cls.get("id", "")) == "blood bending" or "blood" in str(cls_name).lower():
        for key, text in BLOOD_BENDING.items():
            add(key, text, cls_name)

    # The paths: the document's own ability text, plus upgrades annotated as such.
    for pname, path in (cls.get("paths") or {}).items():
        abilities = path.get("abilities") or {}
        for aname, text in abilities.items():
            add(aname, text, f"{cls_name} — {path.get('name', pname)}")
        for up, base in (path.get("upgrades") or {}).items():
            base_text = abilities.get(base, "")
            add(up, f"Upgrade of {base}. {base_text}".strip(),
                f"{cls_name} — {path.get('name', pname)}")

    # Feats: the sheet already prints their effect beside them, but the glossary carries
    # them too so a feat named in a grants column answers the same click.
    from .tables import FEATS

    for feat in getattr(actor, "feats", []) or []:
        found = FEATS.get(_clean(feat))
        if found:
            add(found.get("name", feat),
                found.get("effect") or found.get("benefit") or "",
                found.get("source", "feat"))

    return out


def lookup(glossary: dict, name: str) -> dict | None:
    """The entry for a name as it appears on the sheet, tolerant of trailing numbers.

    "control blood 1a" tries itself, then drops trailing tokens that carry digits —
    which finds "control blood" — and "blood sense 60ft" finds "blood sense" the same
    way. Pure function of its inputs so the page's JS mirror cannot drift far.
    """
    key = _clean(name)
    while key:
        if key in glossary:
            return glossary[key]
        parts = key.split()
        if len(parts) > 1 and re.search(r"\d", parts[-1]):
            key = " ".join(parts[:-1])
        else:
            return None
    return None

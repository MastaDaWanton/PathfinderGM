"""The Bestiary's templates, applied to a printed creature by the printed rules.

The owner's direction, 2026-10-28: monsters the adventures supplied ("zombie shark",
"advanced wolf") are made here from a Bestiary creature and a Bestiary template, never
copied. Each template is a document (content/templates/*.json), read from Bestiary 1
(pp. 250-251, 288-289, 294-295) on 2026-10-28; this module is the one applier that reads
them. Prior art: the Foundry PF2e creature-template-applier applies a template to an NPC as
one effect and lists what needs judgment as "Still to do by hand" — right for changing a
live actor, and not available here, where the result is a creature the game ships and
nothing can be left for a person to finish. So:

- **Simple templates** (advanced, giant, young, celestial, fiendish) by their *rebuild*
  rules, as deltas on the printed totals: "+4 to all ability scores" is +2 to every
  Str-based attack and damage, Dex-based AC and Reflex, Con-based Fortitude and hit points,
  and so on. A delta keeps what the print hid inside a total (Weapon Focus, a ring of
  protection) where recomputing from scores would drop it. The Bestiary's quick rules are
  this delta written out for the common case; the rebuild form is the one that is exact.
- **Undead templates** (zombie, skeleton) are rebuilt whole: their rules replace Hit Dice,
  saves, abilities, feats, skills and attacks outright, so nothing hidden survives anyway.

Every application refuses what its rules refuse (a young dragon, a skeleton of an ooze)
with the rule quoted, and returns a stat block in the shape core.json's are, so the rest
of the game reads it as it reads a printed one.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

from pathfindergm import files

from .tables import SIZE_ORDER, SIZES

ABILITIES = ("str", "dex", "con", "int", "wis", "cha")
_ALL: dict[str, dict] | None = None


def all_templates() -> dict[str, dict]:
    global _ALL
    if _ALL is None:
        from django.conf import settings

        out: dict[str, dict] = {}
        for folder in (Path(settings.BASE_DIR) / "content" / "templates",
                       Path(settings.CAMPAIGN_DIR).parent / "homebrew" / "templates"):
            if not folder.is_dir():
                continue
            for path in sorted(folder.glob("*.json")):
                try:
                    doc = json.loads(path.read_text(encoding="utf-8"))
                except Exception as exc:
                    files.unreadable(path, exc)
                    continue
                if isinstance(doc, dict) and doc.get("id"):
                    out[str(doc["id"]).lower()] = doc
        _ALL = out
    return _ALL


# --- reading a printed block ------------------------------------------------------------------

def _mod(score) -> int | None:
    return None if score is None else (int(score) - 10) // 2


def hit_dice(block: dict) -> list[tuple[int, int]]:
    """[(count, die)] off the printed `hit_dice`, "4d8+12" -> [(4, 8)]."""
    text = str(block.get("hit_dice") or "").split(";")[-1]
    return [(int(n), int(d)) for n, d in re.findall(r"(\d+)\s*d\s*(\d+)", text)]


def total_hd(block: dict) -> int:
    return sum(n for n, _ in hit_dice(block))


def ac_parts(block: dict) -> dict[str, int]:
    """The printed AC's parts by kind: {"armor": 4, "dex": -1, "natural": 5, "size": -1}."""
    out: dict[str, int] = {}
    m = re.search(r"\(([^()]*)\)", str(block.get("ac_note") or ""))
    for part in (m.group(1).split(",") if m else ()):
        p = re.match(r"\s*([+-]\d+)\s+(.+?)\s*$", part.replace("–", "-").replace("—", "-"))
        if p:
            kind = p.group(2).strip().lower()
            out[kind] = out.get(kind, 0) + int(p.group(1))
    return out


def _ac_note(touch: int, flat: int, parts: dict[str, int]) -> str:
    inner = ", ".join(f"{v:+d} {k if k != 'dex' else 'Dex'}" for k, v in parts.items() if v)
    return f"touch {touch}, flat-footed {flat}" + (f" ({inner})" if inner else "")


def _touch_flat(block: dict) -> tuple[int, int]:
    m = re.search(r"touch\s+(\d+)\s*,\s*flat-footed\s+(\d+)", str(block.get("ac_note") or ""))
    return (int(m.group(1)), int(m.group(2))) if m else (int(block.get("flat_ac") or 10),) * 2


# --- the attack line, written back -----------------------------------------------------------

def render_attack(a: dict) -> str:
    """One parsed attack (`statblock_attacks`) back in the book's format:
    "2 claws +8 (1d6+4 plus grab)"."""
    count = int(a.get("count") or 1)
    name = re.sub(r"^\d+\s+", "", str(a.get("name") or ""))
    lead = f"{count} {name}" if count > 1 and not str(a.get("name", "")).startswith(str(count))\
        else name
    bonuses = "/".join(f"{int(b):+d}" for b in (a.get("bonuses") or [0]))
    dmg = str(a.get("dice") or "")
    flat = int(a.get("bonus") or 0)
    if flat:
        dmg += f"{flat:+d}"
    if a.get("crit_range") and int(a["crit_range"]) < 20:
        dmg += f"/{a['crit_range']}-20"
    if a.get("crit_mult") and int(a["crit_mult"]) != 2:
        dmg += f"/x{a['crit_mult']}"
    if a.get("nonlethal"):
        dmg += " nonlethal"
    for x in a.get("extra") or ():
        dmg += f" plus {x.get('dice')} {x.get('type', '')}".rstrip()
    for r in a.get("riders") or ():
        dmg += f" plus {r}"
    if a.get("automatic"):
        # "swarm (1d6 plus disease)": no bonus, because it makes no attack roll. Written
        # "+0" it read back as an attack rolled at +0, and an advanced rat swarm missed.
        return f"{name} ({dmg})"
    touch = " touch" if a.get("touch") and "touch" not in name.lower() else ""
    return f"{lead} {bonuses}{touch} ({dmg})"


def render_line(options: list[list[dict]]) -> str:
    return " or ".join(", ".join(render_attack(a) for a in opt) for opt in options if opt)


def _step_dice(dice: str, steps: int) -> tuple[str, bool]:
    """A die moved `steps` sizes along CRB Table 6-5 (`weapons.SIZE_DIE`). (die, moved): a
    die the table does not carry is left as printed and says so."""
    from .weapons import SIZE_DIE

    out = " ".join(str(dice or "").split()).lower()
    for _ in range(abs(steps)):
        nxt = SIZE_DIE.get(out, {}).get("large" if steps > 0 else "small")
        if nxt is None:
            return dice, False
        out = nxt
    return out, True


# --- applying ---------------------------------------------------------------------------------

def refusal(block: dict, tpl: dict) -> str:
    """Why the template's rules refuse this creature, or ""."""
    rules = tpl.get("refuse") or {}
    size = str(block.get("size") or "medium").lower()
    ctype = str(block.get("creature_type") or "").lower()
    sub = str(block.get("subtype") or "").lower()
    why = rules.get("why") or ""
    if size in (rules.get("sizes") or ()):
        return why or f"The {tpl['name']} template cannot be applied to a {size} creature."
    if ctype in (rules.get("types") or ()):
        return why or f"The {tpl['name']} template cannot be applied to {ctype}."
    if any(s in sub for s in rules.get("subtypes") or ()):
        return why or f"The {tpl['name']} template cannot be applied to this creature."
    grows = rules.get("grows") or {}
    if grows:
        name = " ".join(str(block.get("name") or "").lower().split())
        aged = ctype in (grows.get("age_types") or ()) and any(
            name.startswith(w + " ") for w in grows.get("age_words") or ())
        text = " ".join(str(block.get(f) or "") for f in
                        ("special_attacks", "special_abilities")).lower()
        fed = bool(grows.get("text")) and str(grows["text"]).lower() in text
        if aged or fed:
            return why or f"The {tpl['name']} template cannot be applied to this creature."
    if not hit_dice(block):
        return f"{block.get('name')}'s Hit Dice ({block.get('hit_dice')!r}) cannot be read."
    if tpl.get("max_hd") and total_hd(block) > int(tpl["max_hd"]):
        return f"More than {tpl['max_hd']} Hit Dice: the rules allow no {tpl['name']} of it."
    return ""


def apply(block: dict, template_id: str) -> tuple[dict | None, str]:
    """(the templated block, "") or (None, why the rules refuse it)."""
    tpl = all_templates().get(str(template_id).lower())
    if tpl is None:
        return None, f"no template {template_id!r} — one of {', '.join(sorted(all_templates()))}"
    why = refusal(block, tpl)
    if why:
        return None, why
    if tpl.get("kind") == "undead":
        return _undead(block, tpl)
    return _simple(block, tpl)


def apply_chain(block: dict, template_ids) -> tuple[dict | None, str]:
    """`apply` each template in order to a block already in hand ("young", then "zombie")."""
    for t in template_ids:
        block, why = apply(block, t)
        if block is None:
            return None, why
    return block, ""


def apply_all(base_id: str, template_ids) -> tuple[dict | None, str]:
    """A Bestiary creature with templates applied in order ("young", then "zombie")."""
    from . import bestiary

    block = bestiary.raw_block(base_id)
    if block is None:
        return None, f"no creature {base_id!r}"
    return apply_chain(dict(block), template_ids)


def _name(block: dict, tpl: dict) -> str:
    """"Advanced Wolf", "Shark Zombie": the book's own form (Human Zombie, Bestiary 1)."""
    base = str(block.get("name") or "")
    word = str(tpl["name"]).title()
    return f"{base} {word}" if tpl.get("name_after") else f"{word} {base}"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _simple(block: dict, tpl: dict) -> tuple[dict, str]:
    from . import statblock_attacks as sa

    out = dict(block)
    old = dict(block.get("abilities") or {})
    new = dict(old)
    for ab, d in (tpl.get("abilities") or {}).items():
        if new.get(ab) is not None:
            new[ab] = int(new[ab]) + int(d)
    dm = {ab: (_mod(new.get(ab)) or 0) - (_mod(old.get(ab)) or 0)
          if old.get(ab) is not None else 0 for ab in ABILITIES}
    hd = total_hd(block)
    size = str(block.get("size") or "medium").lower()
    i = SIZE_ORDER.index(size) if size in SIZE_ORDER else SIZE_ORDER.index("medium")
    new_size = SIZE_ORDER[max(0, min(len(SIZE_ORDER) - 1, i + int(tpl.get("size_steps") or 0)))]
    d_size_ac = SIZES[new_size]["attack_ac"] - SIZES[size]["attack_ac"]
    d_size_cm = SIZES[new_size]["cmb_cmd"] - SIZES[size]["cmb_cmd"]

    parts = ac_parts(block)
    nat_d = int(tpl.get("natural_armour") or 0)
    if "natural_armour_floor" in tpl and nat_d < 0:
        nat_d = max(nat_d, int(tpl["natural_armour_floor"]) - parts.get("natural", 0))
    touch, flat = _touch_flat(block)
    dex_d = dm["dex"]
    out["flat_ac"] = int(block.get("flat_ac") or 10) + dex_d + d_size_ac + nat_d
    touch += dex_d + d_size_ac
    flat += d_size_ac + nat_d + (min(_mod(new.get("dex")) or 0, 0) - min(_mod(old.get("dex")) or 0, 0))
    if parts:
        for k, v in (("dex", dex_d), ("size", d_size_ac), ("natural", nat_d)):
            if v:
                parts[k] = parts.get(k, 0) + v
    out["ac_note"] = _ac_note(touch, flat, parts)
    out["abilities"] = new
    out["size"] = new_size
    out["hp"] = max(1, int(block.get("hp") or 1) + dm["con"] * hd)
    out["hit_dice"] = _hd_with_bonus(block, dm["con"] * hd)
    saves = dict(block.get("flat_saves") or {})
    for s, ab in (("fort", "con"), ("ref", "dex"), ("will", "wis")):
        if saves.get(s) is not None:
            saves[s] = int(saves[s]) + dm[ab]
    out["flat_saves"] = saves
    if block.get("flat_initiative") is not None:
        out["flat_initiative"] = int(block["flat_initiative"]) + dm["dex"]
    if block.get("cmb") is not None:
        out["cmb"] = int(block["cmb"]) + dm["str"] + d_size_cm
    if block.get("flat_cmd") is not None:
        out["flat_cmd"] = int(block["flat_cmd"]) + dm["str"] + dm["dex"] + d_size_cm
    skills = dict(block.get("flat_skills") or {})
    for sk in skills:
        skills[sk] = int(skills[sk]) + dm.get(_SKILL_ABILITY.get(sk.split(" (")[0], ""), 0)
        if sk == "stealth":
            skills[sk] += (SIZES[new_size]["stealth"] - SIZES[size]["stealth"])
    if skills:
        out["flat_skills"] = skills

    unstepped = []
    lines = sa.of_block(block)
    finesse = any("weapon finesse" in str(f).lower() for f in block.get("feats") or ())
    for cat in ("melee", "ranged"):
        opts = lines.get(cat) or []
        for opt in opts:
            first = max((a["bonuses"][0] for a in opt if a.get("bonuses")), default=0)
            natural_count = sum(int(a.get("count") or 1) for a in opt if a.get("natural"))
            for a in opt:
                # Weapon Finesse uses Dex only when it is the better: the giant ghoul's
                # Str 17 now beats its Dex 13, so its claws move with the better of the
                # two, not with the Dex it no longer swings with (a giant ghoul's claws
                # were -2 to hit for growing stronger).
                fin = (max(_mod(new.get("str")) or 0, _mod(new.get("dex")) or 0)
                       - max(_mod(old.get("str")) or 0, _mod(old.get("dex")) or 0))
                to_hit = (dm["dex"] if cat == "ranged" else fin if finesse
                          else dm["str"]) + d_size_ac
                if not a.get("automatic"):          # a swarm rolls nothing to move
                    a["bonuses"] = [int(b) + to_hit for b in a.get("bonuses") or [0]]
                secondary = a.get("natural") and a.get("bonuses") and \
                    a["bonuses"][0] - to_hit <= first - 5
                share = 0.5 if secondary else (1.5 if (a.get("natural") and natural_count == 1)
                                               else 1.0)
                # A swarm's damage is its Hit Dice's (Bestiary 1 p. 313's table), with no
                # Strength in it to move.
                if (cat == "melee" or _thrown(a)) and not a.get("automatic"):
                    a["bonus"] = int(a.get("bonus") or 0) + math.floor(dm["str"] * share)
                steps = int(tpl.get("damage_dice_steps") or 0)
                if steps and a.get("dice"):
                    a["dice"], moved = _step_dice(a["dice"], steps)
                    if not moved:
                        unstepped.append(a["name"])
        if opts:
            out[cat] = render_line(opts)
    if out.get("melee"):
        first = (lines.get("melee") or [[{}]])[0][0]
        out["flat_attack"] = (first.get("bonuses") or [0])[0]
        out["flat_damage"] = f"{first.get('dice', '')}{int(first.get('bonus') or 0):+d}"

    # Celestial, fiendish: senses, defenses by Hit Dice, SR, a smite.
    if tpl.get("senses") and "darkvision" not in str(block.get("senses") or "").lower():
        out["senses"] = "; ".join(x for x in (str(block.get("senses") or ""), tpl["senses"]) if x)
    for row in tpl.get("defenses_by_hd") or ():
        lo, hi = row["hd"]
        if lo <= hd <= hi:
            have = {r.rsplit(" ", 1)[0].lower(): int(r.rsplit(" ", 1)[1])
                    for r in block.get("resist") or () if r.rsplit(" ", 1)[-1].isdigit()}
            for energy, n in (row.get("resist") or {}).items():
                have[energy] = max(have.get(energy, 0), int(n))
            out["resist"] = [f"{k} {v}" for k, v in have.items()]
            if row.get("dr"):
                out["reductions"] = list(block.get("reductions") or []) + [
                    {**row["dr"], "source": f"template:{tpl['id']}"}]
    add = int((tpl.get("cr") or {}).get("add") or 0)
    if (tpl.get("cr") or {}).get("if_hd_at_least") and hd < int(tpl["cr"]["if_hd_at_least"]):
        add = 0
    out["cr"] = shift_cr(str(block.get("cr") or "1"), add)
    out["cr_value"] = cr_value(out["cr"])
    if tpl.get("sr_over_cr"):
        out["sr"] = max(int(block.get("sr") or 0), int(cr_value(out["cr"])) + int(tpl["sr_over_cr"]))
    if tpl.get("special_attack"):
        out["special_attacks"] = ", ".join(x for x in (str(block.get("special_attacks") or ""),
                                                       tpl["special_attack"]) if x)
    unmoved = _shift_dcs(out, dm, int(tpl.get("dc") or 0))
    if unmoved:
        out["dcs_unmoved"] = unmoved
    return _finish(out, block, tpl, unstepped), ""


# What each special ability's save DC is built on, by the Bestiary's universal monster
# rules (Bestiary 1, Appendix 3, pp. 298-305, read from the book 2026-10-30): "DC 10 + 1/2
# ... HD + ... Con modifier" for breath weapon, burn, disease, distraction, paralysis,
# poison, stench and web; Str for trample ("10 + 1/2 creature's HD + creature's Str
# modifier") and engulf; Cha for fear, frightful presence and gaze. A block that says
# otherwise in its own words ("The save DC is Charisma-based", the ghoul's paralysis) is
# believed over this table.
_DC_BASIS = {"breath weapon": "con", "burn": "con", "disease": "con", "distraction": "con",
             "paralysis": "con", "poison": "con", "stench": "con", "web": "con",
             "trample": "str", "engulf": "str", "fear": "cha", "frightful presence": "cha",
             "gaze": "cha"}
_BASED = re.compile(r"\b(strength|dexterity|constitution|intelligence|wisdom|charisma)-based",
                    re.I)
# Where one described ability ends and the next begins: "Poison (Ex) ... saves. Web (Ex)":
# a heading at the start or after a sentence's end, so "Blood Drain (Ex)" is one heading
# and not "Blood " and "Drain (Ex)".
_ABILITY_HEAD = re.compile(r"(?:^|(?<=[.;:)] )|(?<=[.;:)]))"
                           r"(?=[A-Z][A-Za-z' -]{1,40}\s*\((?:Ex|Su|Sp)\))")


def _top_level_segments(text: str) -> list[str]:
    """`text` cut after each comma outside parentheses, the commas kept, so the pieces
    join back to exactly the text."""
    out, depth, start = [], 0, 0
    for i, ch in enumerate(text):
        depth += ch == "("
        depth -= ch == ")" and depth > 0
        if ch == "," and depth == 0:
            out.append(text[start:i + 1])
            start = i + 1
    out.append(text[start:])
    return [s for s in out if s]


def _dc_basis(segment: str, field: str) -> str:
    said = _BASED.search(segment)
    if said:
        return said.group(1)[:3].lower()
    head = segment.strip().lower()
    for name in sorted(_DC_BASIS, key=len, reverse=True):
        # The ability's own name leads its segment ("poison (DC 14)", "Poison (Ex)"), and
        # a poison's description says "Sting—injury; save Fort DC 17" after it.
        if head.startswith(name) or (field == "special_abilities"
                                     and re.match(rf"[a-z' -]*\b{name}\b", head)):
            return _DC_BASIS[name]
    return ""


def _shift_dcs(out: dict, dm: dict[str, int], flat: int) -> list[str]:
    """Move every printed special-ability DC by its ability's modifier change.

    A save DC is "10 + 1/2 HD + an ability modifier", so a template that changes the
    ability changes the DC: the giant's +4 Con is +2 on a poison's DC and its +4 Str +2 on
    a trample's; the young template's -4 takes 2 off both. Until 2026-10-30 only the
    advanced template moved a DC (its quick rules' flat +2, and only in Special Attacks),
    so a giant wyvern's sting was as easy to shrug off as a wyvern's. `flat` is that quick
    rule for a DC whose ability nothing names: advanced moves every score alike, so its +2
    is right whatever the basis; for the giant and the young, a DC of no known basis is
    left as printed and named in the returned list.
    """
    unmoved: list[str] = []
    # The block's own word on an ability, wherever it says it: "paralysis (1d4+1 rounds,
    # DC 13)" in Special Attacks is described, with its basis, in Special Abilities.
    described = {}
    for seg in _ABILITY_HEAD.split(str(out.get("special_abilities") or "")):
        said = _BASED.search(seg)
        name = re.match(r"\s*([A-Za-z' -]+?)\s*\((?:Ex|Su|Sp)\)", seg)
        if said and name:
            described[name.group(1).strip().lower()] = said.group(1)[:3].lower()
    for field in ("special_attacks", "special_abilities"):
        text = str(out.get(field) or "")
        if not re.search(r"\bDC\s+\d", text):
            continue
        if field == "special_abilities":
            segments = [s for s in _ABILITY_HEAD.split(text) if s]
        else:
            segments = _top_level_segments(text)
        moved = []
        for seg in segments:
            head = re.match(r"\s*([a-z' -]+)", seg.lower())
            ab = described.get(head.group(1).strip()) if head else None
            ab = ab or _dc_basis(seg, field)
            step = dm.get(ab, 0) if ab else flat
            if not ab and not flat and re.search(r"\bDC\s+\d", seg) and any(dm.values()):
                unmoved.append(seg.strip()[:60])
            moved.append(re.sub(r"\bDC\s+(\d+)", lambda m: f"DC {int(m.group(1)) + step}",
                                seg) if step else seg)
        out[field] = "".join(moved)
    return unmoved


_SKILL_ABILITY = {"acrobatics": "dex", "appraise": "int", "bluff": "cha", "climb": "str",
                  "craft": "int", "diplomacy": "cha", "disable device": "dex", "disguise": "cha",
                  "escape artist": "dex", "fly": "dex", "handle animal": "cha", "heal": "wis",
                  "intimidate": "cha", "knowledge": "int", "linguistics": "int",
                  "perception": "wis", "perform": "cha", "profession": "wis", "ride": "dex",
                  "sense motive": "wis", "sleight of hand": "dex", "spellcraft": "int",
                  "stealth": "dex", "survival": "wis", "swim": "str", "use magic device": "cha"}


def _thrown(a: dict) -> bool:
    from . import weapons

    row = weapons.all_weapons().get(str(a.get("base") or ""), {})
    return "thrown" in " ".join(str(t) for t in row.get("traits") or ()).lower()


def _hd_with_bonus(block: dict, add: int) -> str:
    text = str(block.get("hit_dice") or "")
    m = re.match(r"^(.*?\d+d\d+)\s*([+-]\s*\d+)?(.*)$", text)
    if not m:
        return text
    flat = int((m.group(2) or "0").replace(" ", "")) + add
    return f"{m.group(1)}{flat:+d}{m.group(3)}" if flat else f"{m.group(1)}{m.group(3)}"


def _finish(out: dict, base: dict, tpl: dict, unstepped=()) -> dict:
    name = _name(base, tpl)
    out["name"] = name
    out["id"] = _slug(name)
    out["templates"] = list(base.get("templates") or []) + [tpl["id"]]
    out["base"] = base.get("base") or base.get("id")
    out["source"] = f"{base.get('source', '')}; {tpl['name']} template, {tpl['source']}"
    out["notes"] = f"CR {out['cr']} {out.get('creature_type', '')}".strip()
    # The app's own words (the template document's `describe`), never a page's: a line a
    # bench or a GM can show for a creature no printed block describes.
    if tpl.get("describe"):
        noun = str(base.get("name") or "creature").lower()
        a_noun = ("an " if noun[:1] in "aeiou" else "a ") + noun
        out["description"] = str(tpl["describe"]).format(
            base=noun, a_base=a_noun, A_base=a_noun[:1].upper() + a_noun[1:])
    if unstepped:
        out["unstepped"] = sorted(set(unstepped))
    return out


# --- CR arithmetic ------------------------------------------------------------------------------

_LADDER = ["1/8", "1/6", "1/4", "1/3", "1/2"] + [str(n) for n in range(1, 31)]


def cr_value(cr: str) -> float:
    if "/" in str(cr):
        a, b = str(cr).split("/")
        return int(a) / int(b)
    return float(cr)


def shift_cr(cr: str, add: int) -> str:
    """CR moved `add` steps along the ladder 1/8 ... 1/2, 1, 2 ... (the young template's -1
    takes a CR 1 creature to 1/2, Bestiary 1 p. 295's own example being a CR 1/2 rat)."""
    cr = str(cr).strip()
    i = _LADDER.index(cr) if cr in _LADDER else 5
    return _LADDER[max(0, min(len(_LADDER) - 1, i + int(add)))]


# --- the undead: rebuilt whole ------------------------------------------------------------------

_SLAM = {"fine": "", "diminutive": "1", "tiny": "1d2", "small": "1d3", "medium": "1d4",
         "large": "1d6", "huge": "1d8", "gargantuan": "2d6", "colossal": "2d8"}
# Bestiary 1 Table 3-1, "Natural Attacks by Size" (p. 302): slam and claw share a row.
_HANDED = ("humanoid", "monstrous humanoid", "giant")


def _average(dice: str) -> float:
    """The mean of "2d6" (7.0), "1d8" (4.5), "1" (1.0); 0 for nothing readable."""
    m = re.fullmatch(r"\s*(\d+)d(\d+)\s*", str(dice or ""))
    if m:
        return int(m.group(1)) * (int(m.group(2)) + 1) / 2
    return float(dice) if str(dice or "").strip().isdigit() else 0.0


# A fly speed in a speed line, with its manoeuvrability: "fly 60 ft. (average)".
_FLY = re.compile(r",?\s*\bfly\s+\d+\s*(?:ft|feet)\.?(?:\s*\((?P<grade>[a-z]+)\))?", re.I)
# A block that says it flies by magic: "flight (Su)", "fly ... (Su)", "flies magically".
_MAGIC_FLIGHT = re.compile(r"\bflight\s*\((?:su|sp)\)|\bfl(?:y|ies)\b[^.;]{0,40}\(su\)"
                           r"|\bfl(?:y|ies)\s+magically|\bmagical\s+flight", re.I)


def _undead_flight(block: dict, rule: str) -> str:
    """The speed line after the template's Speed clause (`fly`, quoted in `fly_rule`).

    "none": a winged skeleton can't use its wings to fly. "clumsy": a winged zombie still
    flies, at clumsy. Either way, flight the block says is magical is kept as printed.
    Until 2026-10-30 both documents carried the clause and nothing read it, so a wyvern
    skeleton flew at its living speed and manoeuvrability."""
    note = str(block.get("speed_note") or "")
    if not rule or not _FLY.search(note):
        return note
    text = " ".join(str(block.get(f) or "") for f in
                    ("speed_note", "special_abilities", "special_attacks", "qualities"))
    if _MAGIC_FLIGHT.search(text):
        return note
    if rule == "none":
        return _FLY.sub("", note).strip(" ,")
    if rule in ("clumsy", "poor", "average", "good", "perfect"):
        def grade(m: re.Match) -> str:
            head = m.group(0)
            if m.group("grade"):
                return head.replace(f"({m.group('grade')})", f"({rule})")
            return f"{head} ({rule})"
        return _FLY.sub(grade, note)
    return note


def _cr_by_hd(tpl: dict, hd: int) -> str | None:
    for upper, cr in tpl.get("cr_by_hd") or ():
        if hd <= upper:
            return str(cr)
    return None


def _undead(block: dict, tpl: dict) -> tuple[dict | None, str]:
    from . import statblock_attacks as sa

    ctype = str(block.get("creature_type") or "").lower()
    size = str(block.get("size") or "medium").lower()
    groups = hit_dice(block)
    levels = sum(int(v) for v in (block.get("class_levels") or {}).values())
    if levels or block.get("class_levels") == {}:
        # The block's class line says which dice are class levels ("Goblin warrior 1"):
        # "drop HD gained from class levels (minimum of 1)" (p. 288), and a skeleton
        # treats a creature without racial HD "as if they have 1 racial HD" (p. 250).
        racial = max(1, total_hd(block) - levels)
    elif ctype == "humanoid" and not all(d == 8 for _, d in groups):
        racial = 1          # no class line read: a humanoid's non-d8 dice are a class's
    elif len(groups) == 1:
        racial = groups[0][0]
    else:
        return None, (f"{block.get('name')}'s Hit Dice {block.get('hit_dice')!r} mix racial and "
                      f"class dice, which the {tpl['name']} drops: rebuild it from its race.")
    hd = racial + int((tpl.get("bonus_hd_by_size") or {}).get(size, 0))
    cr = _cr_by_hd(tpl, hd)
    if cr is None:
        return None, f"{hd} Hit Dice is past the {tpl['name']} table's end."
    old = dict(block.get("abilities") or {})
    new = {ab: old.get(ab) for ab in ABILITIES}
    for ab, d in (tpl.get("abilities") or {}).items():
        if new.get(ab) is not None:
            new[ab] = int(new[ab]) + int(d)
    for ab in tpl.get("no_scores") or ():
        new.pop(ab, None)
    for ab, v in (tpl.get("set_scores") or {}).items():
        new[ab] = int(v)
    new = {k: v for k, v in new.items() if v is not None}
    s_mod, d_mod, c_mod, w_mod = (_mod(new.get("str")) or 0, _mod(new.get("dex")) or 0,
                                  _mod(new.get("cha")) or 0, _mod(new.get("wis")) or 0)
    bab = hd * 3 // 4
    size_ac = SIZES[size]["attack_ac"]
    size_cm = SIZES[size]["cmb_cmd"]
    feats = list(tpl.get("bonus_feats") or [])
    toughness = (max(3, hd) if "Toughness" in feats else 0)
    hp = max(1, hd * 9 // 2 + c_mod * hd + toughness)
    # Worn gear is not the creature's: the Bestiary's own human zombie and the printed
    # goblin zombie carry none (AC 12 and 13, a slam and nothing else), so a raised body
    # starts bare; arming it is a kit's business, as the skeleton's "sometimes a
    # skeleton's creator arms it" (p. 251) says.
    parts: dict[str, int] = {}
    natural = int((tpl.get("natural_armour_by_size") or {}).get(size, 0))
    ac = 10 + d_mod + size_ac + natural + sum(parts.values())
    touch = 10 + d_mod + size_ac + parts.get("deflection", 0)
    flat = ac - max(d_mod, 0)
    note_parts = {**parts, "dex": d_mod, "natural": natural, "size": size_ac}

    lines = sa.of_block(block)
    drop = set(tpl.get("drops_attacks") or ())
    natural_attacks: list[dict] = []
    for opt in lines.get("melee") or []:
        for a in opt:
            if a.get("natural") and a.get("key") not in drop and a.get("kind") not in drop \
                    and not any(n["key"] == a["key"] for n in natural_attacks):
                natural_attacks.append(dict(a))
    gains = tpl.get("gains_attack") or {}
    if gains.get("kind") == "slam":
        big = SIZE_ORDER[min(len(SIZE_ORDER) - 1, SIZE_ORDER.index(size) + int(gains.get("size_steps", 0)))]
        # One slam (the document's `slam_rule`): a base's own slams are the same blow, and
        # the zombie keeps the better die. Measured 2026-10-30: the hill giant zombie swung
        # "2 slams" and a third, where Paizo's printed one swings one.
        own = [a for a in natural_attacks if a.get("kind") == "slam"]
        dice = max([_SLAM[big]] + [str(a.get("dice") or "") for a in own], key=_average)
        natural_attacks = [a for a in natural_attacks if a.get("kind") != "slam"]
        natural_attacks.append({"name": "slam", "key": "slam", "count": 1, "natural": True,
                                "kind": "slam", "dice": dice, "riders": [], "extra": []})
    elif gains.get("kind") == "claw" and ctype in _HANDED:
        # "A creature with hands gains one claw attack per hand ... If the base creature
        # already had claw attacks with its hands, use the skeleton claw damage only if it's
        # better" (p. 250).
        #
        # A hand strikes once. A base whose hands already strike — its claws, or the slams
        # a giant's fists are printed as ("2 slams +13") — has those hands' attack already:
        # the skeleton keeps it, at the claw's die where that is better, and one per hand
        # now that no weapon fills one (the lizardfolk prints one claw beside its
        # morningstar). The first cut added two claws beside a hill giant's two slams:
        # four blows from two hands.
        own = next((a for a in natural_attacks if a.get("kind") in ("claw", "slam")), None)
        if own is None:
            natural_attacks.append({"name": "claws", "key": "claws", "count": 2, "natural": True,
                                    "kind": "claw", "dice": _SLAM[size], "riders": [], "extra": []})
        else:
            if _average(_SLAM[size]) > _average(str(own.get("dice") or "")):
                own.update(dice=_SLAM[size], name="claws", key="claws", kind="claw")
            if int(own.get("count") or 1) < 2:
                own["count"] = 2
                own["name"] = sa.singular(own["name"]) + "s" \
                    if not str(own["name"]).endswith("s") else own["name"]
    n_natural = sum(int(a.get("count") or 1) for a in natural_attacks)
    primary_kinds = {"bite", "claw", "gore", "slam", "sting", "talon", "talons"}
    # Its body's attacks only: the base's weapons were gear (above), and a zombie "retains
    # ... manufactured weapon attacks, and weapon proficiencies" means it can still swing
    # one it is handed, not that it was raised holding one.
    melee: list[list[dict]] = []
    if natural_attacks:
        for a in natural_attacks:
            secondary = a.get("kind") not in primary_kinds
            a["bonuses"] = [bab + s_mod + size_ac - (5 if secondary else 0)]
            share = 0.5 if secondary else (1.5 if n_natural == 1 else 1.0)
            a["bonus"] = math.floor(s_mod * share)
            # "retains none of the base creature's special attacks" (pp. 250, 288): grab
            # and trip ride the attack line and go with the rest.
            a["riders"] = []
            a["extra"] = []
        melee.append(natural_attacks)
    ranged: list[list[dict]] = []           # no weapon in hand, so nothing to loose

    out = dict(block)
    sub = [s.strip() for s in str(block.get("subtype") or "").split(",") if s.strip()]
    out.update({
        "creature_type": "undead", "alignment": tpl.get("alignment") or "NE",
        "subtype": ", ".join(s for s in sub if s not in _DROPPED_SUBTYPES),
        "abilities": new, "hp": hp, "hit_dice": f"{hd}d8" + (f"{hp - hd * 9 // 2:+d}" if hp - hd * 9 // 2 else ""),
        "flat_ac": ac, "ac_note": _ac_note(touch, flat, note_parts),
        "flat_saves": {"fort": hd // 3 + c_mod, "ref": hd // 3 + d_mod, "will": hd // 2 + 2 + w_mod},
        "flat_initiative": d_mod + (4 if "Improved Initiative" in feats else 0),
        "base_attack": bab, "cmb": bab + s_mod + size_cm,
        "flat_cmd": 10 + bab + s_mod + d_mod + size_cm,
        "melee": render_line(melee), "ranged": render_line(ranged),
        "speed_note": _undead_flight(block, str(tpl.get("fly") or "")),
        "feats": feats, "flat_skills": {}, "languages": [],
        "special_attacks": "", "immune": list(tpl.get("immune") or []),
        "reductions": [{**tpl["dr"], "source": f"template:{tpl['id']}"}] if tpl.get("dr") else [],
        "senses": "darkvision 60 ft.", "cr": cr, "cr_value": cr_value(cr), "sr": None,
        "qualities": list(tpl.get("qualities") or []),
        # A raised body is rot and bone: none of the base's hide, sinew or glands comes off
        # it (`rules/harvest.py` reads these tags and nothing else).
        "tags": [t for t in block.get("tags") or () if not str(t).startswith("harvest.")]
                + list(tpl.get("standing_tags") or []),
    })
    first = (melee or ranged or [[{}]])[0][0]
    out["flat_attack"] = (first.get("bonuses") or [None])[0]
    out["flat_damage"] = f"{first.get('dice', '')}{int(first.get('bonus') or 0):+d}"
    return _finish(out, block, tpl), ""


# Subtypes that "indicate kind" or alignment, which the undead templates drop (p. 250, 288).
_DROPPED_SUBTYPES = {"good", "evil", "lawful", "chaotic", "giant", "elf", "dwarf", "gnome",
                     "goblinoid", "halfling", "human", "orc", "reptilian", "augmented"}

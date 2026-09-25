"""Feats, and whether a character actually qualifies for one.

`content/feats/feats.json` holds all 1,478 as data — names, types, prose, sources and, most
of the point, **typed prerequisites**. `content/feats/mechanics/*.json` holds, for the feats
the engine computes with, a *document* in the class `grants` vocabulary (stage 8): "what
does this feat do to my attack roll?" is `document()`, read live by the sheet the way worn
gear is; "may this character take it?" is `meets`, here. Before stage 8 the first question
was answered by a hand-written Python table of sixteen and name-branches in the sheet.

**What `meets` will and will not claim.** About seven feats in ten have prerequisites that
are fully machine-checkable. The rest carry at least one clause the extractor could not
type — "gnome magic racial trait", "able to use drow spell-like abilities", "You must have
had friendly contact with an evil-aligned outsider" — and for those `meets` returns
`unknown` rather than True or False. A checker that quietly treated an unreadable
prerequisite as satisfied would let a character take a feat they have not earned, and the
only symptom would be a number that is wrong for the rest of the campaign. Saying "I cannot
tell, here is the sentence" is the honest answer and the useful one.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from pathfindergm import files


# Conditions the checker understands. A condition kind not in here is treated as unknown
# rather than ignored — see the module docstring.
CHECKABLE = {
    "ability", "bab", "caster_level", "character_level", "class_level", "skill_ranks",
    "feat", "race", "race_any", "size", "alignment",
}

# Kinds the extractor types but the sheet cannot answer yet. Listed separately from the
# genuinely unparsed text so it is clear which is a gap in the data and which is a gap in
# the character model.
NOT_YET = {"proficiency", "class_feature", "first_level_only", "mythic_tier"}

SIZE_ORDER = ("fine", "diminutive", "tiny", "small", "medium", "large", "huge",
              "gargantuan", "colossal")


@dataclass
class Feat:
    id: str
    name: str
    types: list[str] = field(default_factory=list)
    description: str = ""
    benefit: str = ""
    normal: str = ""
    special: str = ""
    source: str = ""
    race: str = ""
    prerequisites_text: str = ""
    prerequisites: list[dict] = field(default_factory=list)
    unparsed_prerequisites: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    multiples: bool = False
    goal: str = ""
    completion_benefit: str = ""

    @property
    def mechanical(self) -> dict:
        """The feat's mechanics document, if the engine computes with this feat."""
        return documents().get(self.id, {})

    @property
    def line(self) -> str:
        bits = [", ".join(t.title() for t in self.types)]
        if self.prerequisites_text:
            bits.append(f"Prereq: {self.prerequisites_text.rstrip('.')}")
        return " · ".join(b for b in bits if b)

    def as_dict(self) -> dict:
        d = dict(self.__dict__)
        d["line"] = self.line
        d["has_mechanics"] = bool(self.mechanical)
        return d


def from_dict(d: dict) -> Feat:
    known = Feat.__dataclass_fields__
    return Feat(**{k: v for k, v in d.items() if k in known})


_ALL: dict[str, Feat] | None = None
_META: dict = {}


def all_feats() -> dict[str, Feat]:
    """Every feat, shipped plus homebrew, layered the way spells and ingredients are.

    With no homebrew feats, built once per process (`rules.pristine`)."""
    global _ALL
    if _ALL is None:
        from django.conf import settings

        from . import pristine

        _ALL = pristine.memo(
            "feats", [Path(settings.CAMPAIGN_DIR).parent / "homebrew" / "feats"],
            _build_feats)
    return _ALL


def _build_feats() -> dict[str, Feat]:
    from django.conf import settings

    raw: dict[str, dict] = {}
    for folder in (Path(settings.BASE_DIR) / "content" / "feats",
                   Path(settings.CAMPAIGN_DIR).parent / "homebrew" / "feats"):
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                files.unreadable(path, exc)
                continue
            entries = data.get("feats") if isinstance(data, dict) else None
            if not isinstance(entries, list):
                entries = [data] if isinstance(data, dict) and data.get("id") else []
            if isinstance(data, dict):
                _META.update({k: v for k, v in data.items() if k != "feats"})
            for e in entries:
                if not e.get("id"):
                    continue
                # Merged, not replaced: a homebrew edit changing one field must not
                # drop the fifteen it never mentioned.
                raw.setdefault(e["id"], {}).update(e)
    return {k: from_dict(v) for k, v in raw.items()}


def meta() -> dict:
    all_feats()
    return dict(_META)


_BY_NAME: dict[str, Feat] | None = None


def _by_name() -> dict[str, Feat]:
    """Name -> feat, preferring the ordinary feat over its mythic namesake.

    155 mythic feats share a name with the feat they require. A plain dict comprehension
    let whichever came last win, so looking up "weapon finesse" returned *mythic* Weapon
    Finesse — and the character sheet printed its prerequisite ("Weapon Finesse.") beside
    Kesst's ordinary one. The ids were fixed for this; the name lookup had the same bug
    one layer up.
    """
    global _BY_NAME
    if _BY_NAME is None:
        out: dict[str, Feat] = {}
        for feat in all_feats().values():
            key = feat.name.strip().lower()
            if key not in out or ("mythic" in out[key].types
                                  and "mythic" not in feat.types):
                out[key] = feat
        _BY_NAME = out
    return _BY_NAME


def get(feat_id: str) -> Feat:
    key = (feat_id or "").strip().lower()
    found = all_feats().get(key)
    if found is None:
        # Sheets write feats as names, not ids: "weapon focus (rapier)".
        found = _by_name().get(key)
    if found is None:
        raise KeyError(f"no feat {feat_id!r}")
    return found


# --- mechanics as documents (stage 8) ---------------------------------------------------
#
# content/feats/mechanics/*.json, keyed by feat id, in the class `grants` vocabulary.
# A subfolder on purpose: `all_feats` globs content/feats/*.json as feat lists, and a
# mechanics file beside feats.json would have been read as one. The OGL text in
# feats.json is not edited; a document is the engine's reading of the benefit.
#
# Applied live, never stored: rules/sheet.py:_feat_mods reads these on every roll the
# way worn gear is read off the slots, so the feat list is the store and removing the
# string removes the term. Foundry v11 abandoned copying item effects onto the actor
# with an `origin` pointer for exactly the questions a stored copy raises — applied
# once, twice or never on a save that predates it — and this is the same choice.

_DOCS: dict[str, dict] | None = None


def documents() -> dict[str, dict]:
    """Every feat mechanics document, keyed by feat id, validated on first load.

    Load-time validation the way spells and creatures get it: a document with an
    unknown target or an unknown key is refused here with the fix named, rather than
    applied as nothing in play.
    """
    global _DOCS
    if _DOCS is None:
        from django.conf import settings

        from . import classbuilder

        out: dict[str, dict] = {}
        folder = Path(settings.BASE_DIR) / "content" / "feats" / "mechanics"
        for path in (sorted(folder.glob("*.json")) if folder.is_dir() else []):
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError(f"{path.name}: a map of feat id → document.")
            for fid, doc in data.items():
                if str(fid).startswith("_"):
                    continue                    # `_about` and its kin
                out[str(fid).strip().lower()] = doc
        problems = classbuilder.validate_feat_documents(out)
        if problems:
            raise ValueError("content/feats/mechanics: " + " | ".join(problems))
        _DOCS = out
    return _DOCS


def resolve(raw: str) -> tuple[Feat | None, str | None]:
    """The one normaliser: a sheet string → (the feat, its parenthetical target).

    Four normalisers used to disagree — `sheet._feat_name`, `_held`, `glossary._clean`,
    `homebrew._slug` — and the sheet stores lower-cased names while feats.json is keyed
    by id, so "Weapon Focus (rapier)", "weapon focus (rapier)" and "weapon-focus" all
    have to reach the same document. Name or id, the parenthetical stripped and kept.
    """
    import re

    from .tables import FEAT_TARGET_RE

    text = str(raw or "").strip()
    m = re.match(FEAT_TARGET_RE, text, re.IGNORECASE)
    name = m.group("feat").strip() if m else text
    target = m.group("target").strip().lower() if m else None
    try:
        return get(name), target
    except KeyError:
        return None, target


def needs_target(doc: dict | None) -> bool:
    """Whether a document binds to the sheet's parenthetical — Weapon Focus (rapier)."""
    if not doc:
        return False
    if any("$target" in str(t) for t in doc.get("tags") or ()):
        return True
    return any("$target" in str(v) for spec in doc.get("modifiers") or ()
               if isinstance(spec, dict) for v in (spec.get("scope") or {}).values())


def document(raw: str) -> dict | None:
    """The mechanics document for a feat as written on a sheet, or None.

    Carries `id`, `name` (the display name every term is labelled with) and `target`
    (the parenthetical, for `$target` scopes) on top of the authored fields.
    """
    feat, target = resolve(raw)
    if feat is None:
        return None
    doc = documents().get(feat.id)
    if doc is None:
        return None
    return {**doc, "id": feat.id, "name": feat.name, "target": target}


def _held(actor) -> set[str]:
    """Feat ids this character has, both as written and with any parenthetical dropped.

    A sheet says "weapon focus (rapier)" and a prerequisite says "Weapon Focus", and they
    have to match: without this every feat with a specialised prerequisite is refused.
    """
    import re

    out: set[str] = set()
    for raw in actor.feats:
        name = str(raw).strip().lower()
        out.add(name)
        out.add(re.sub(r"[^a-z0-9]+", "-", name).strip("-"))
        bare = re.sub(r"\s*\([^)]*\)", "", name).strip()
        out.add(bare)
        out.add(re.sub(r"[^a-z0-9]+", "-", bare).strip("-"))
    return out


def _check(actor, cond: dict) -> bool | None:
    """One condition against a character: True, False, or None for "cannot tell"."""
    kind = cond.get("kind")

    if kind == "ability":
        return actor.ability_score(cond["ability"]) >= int(cond["value"])
    if kind == "bab":
        return actor.bab >= int(cond["value"])
    if kind == "character_level":
        return actor.level >= int(cond["value"])
    if kind == "caster_level":
        from . import casting

        return casting.caster_level(actor) >= int(cond["value"])
    if kind == "class_level":
        # Single-classed for now, which is what the sheet models: a character is their
        # class at their level, or they are not that class at all.
        if (actor.char_class or "").strip().lower() != cond["class"]:
            return False
        return actor.level >= int(cond["value"])
    if kind == "skill_ranks":
        return actor.ranks.get(cond["skill"].strip().lower(), 0) >= int(cond["ranks"])
    if kind == "feat":
        return cond["feat"] in _held(actor) or cond["name"].strip().lower() in _held(actor)
    # A tag question, not a string match: the race document grants `race.<id>`
    # through `standing_tags`, and law one says ask the vocabulary.
    if kind == "race":
        return actor.has_state(f"race.{str(cond['race']).strip().lower()}")
    if kind == "race_any":
        return any(actor.has_state(f"race.{str(r).strip().lower()}") for r in cond["races"])
    if kind == "size":
        want, mine = cond["size"], (actor.size or "medium").strip().lower()
        if mine not in SIZE_ORDER or want not in SIZE_ORDER:
            return None
        if cond.get("or") == "smaller":
            return SIZE_ORDER.index(mine) <= SIZE_ORDER.index(want)
        if cond.get("or") == "larger":
            return SIZE_ORDER.index(mine) >= SIZE_ORDER.index(want)
        return mine == want
    if kind == "alignment":
        # The sheet has no alignment field. Answering False would refuse every
        # alignment-gated feat outright, which is a worse lie than admitting the gap.
        return None

    return None


def describe(cond: dict) -> str:
    """A condition in the words a player would use, for a refusal that can be acted on."""
    kind = cond.get("kind")
    if kind == "ability":
        return f"{cond['ability'].title()} {cond['value']}"
    if kind == "bab":
        return f"base attack bonus +{cond['value']}"
    if kind == "character_level":
        return f"character level {cond['value']}"
    if kind == "caster_level":
        return f"caster level {cond['value']}"
    if kind == "class_level":
        return f"{cond['class']} level {cond['value']}"
    if kind == "skill_ranks":
        return f"{cond['ranks']} ranks in {cond['skill'].title()}"
    if kind == "feat":
        return cond.get("name") or cond["feat"]
    if kind == "race":
        return cond["race"].title()
    if kind == "race_any":
        return " or ".join(r.title() for r in cond["races"])
    if kind == "size":
        tail = f" or {cond['or']}" if cond.get("or") else ""
        return f"{cond['size'].title()} size{tail}"
    if kind == "alignment":
        return ("non-" if cond.get("negated") else "") + cond["component"]
    if kind == "mythic_tier":
        return f"mythic tier {cond['value']}"
    return cond.get("text", kind or "?")


def meets(actor, feat) -> dict:
    """Does this character qualify?

    Returns `{"ok", "unmet", "unknown"}`. `ok` is True only when every condition was
    checkable *and* satisfied — an unreadable prerequisite makes the answer honest rather
    than optimistic, because a checker that assumes yes lets a character take something
    they have not earned and the symptom is a wrong number for the rest of the campaign.
    """
    if isinstance(feat, str):
        feat = get(feat)

    unmet: list[str] = []
    unknown: list[str] = list(feat.unparsed_prerequisites)

    for cond in feat.prerequisites:
        verdict = _check(actor, cond)
        if verdict is True:
            continue
        if verdict is False:
            unmet.append(describe(cond))
        else:
            unknown.append(describe(cond))

    return {"ok": not unmet and not unknown, "unmet": unmet, "unknown": unknown}


def available(actor, kind: str = "") -> list[Feat]:
    """Every feat this character definitely qualifies for, optionally of one type.

    "Definitely" is doing work: feats whose prerequisites could not be read are left out of
    this list and are reachable through `meets` with the sentence attached. A list that
    included them would be a list of feats that mostly cannot be taken.
    """
    want = kind.strip().lower()
    held = _held(actor)
    out = []
    for feat in all_feats().values():
        if want and want not in feat.types:
            continue
        if feat.id in held and not feat.multiples:
            continue
        if meets(actor, feat)["ok"]:
            out.append(feat)
    return sorted(out, key=lambda f: f.name.lower())


def search(text: str = "", kind: str = "", source: str = "", tag: str = "",
           limit: int = 60) -> list[Feat]:
    needle = text.strip().lower()
    out = []
    for feat in all_feats().values():
        if kind and kind.strip().lower() not in feat.types:
            continue
        if source and source.strip().lower() != feat.source.strip().lower():
            continue
        if tag and tag.strip().lower() not in feat.tags:
            continue
        if needle and needle not in feat.name.lower() \
                and needle not in feat.description.lower() \
                and needle not in feat.benefit.lower():
            continue
        out.append(feat)

    # Exact name, then name-starts-with, then name-contains, then prose. Ranking only on
    # "is it in the name" put Cartwheel Dodge above Dodge, which is the search failing at
    # the one query it will be given most.
    def rank(f: Feat) -> tuple:
        low = f.name.lower()
        if not needle:
            return (0, low)
        if low == needle:
            return (0, low)
        if low.startswith(needle):
            return (1, low)
        if needle in low:
            return (2, low)
        return (3, low)

    out.sort(key=rank)
    return out[:limit] if limit else out


__all__ = ["CHECKABLE", "Feat", "all_feats", "available", "describe", "from_dict", "get",
           "meets", "meta", "search"]

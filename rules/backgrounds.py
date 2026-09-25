"""Where a character was before the first turn — as a document, not a note.

"create an in depth, many option, background picker so you can spawn in as a person with
history in the world" (2026-09-14).

Before this, a character's history was two fields: `heritage`, which is a people, and
`notes`, which is free text nobody reads. So every PC arrived having done nothing and
known nobody, and the opening had to introduce them as a stranger every time — which is
exactly what `play/opening.py` does, because it is all it could do.

A background is the same shape of document as a race, a feat and a class ability, for the
same reasons:

- **modifiers** in the feat vocabulary (`skill_mod appraise 2 background`), read live off
  the sheet rather than baked into a number at creation, so removing the background
  removes its arithmetic;
- **tags** for what it makes true — `background.<id>` so anything can ask, and `knows.*`
  for what the character walks in already knowing, which is the half the narrator reads;
- **ties**, which are the point: a slot filled from *this world* at creation, so
  "you apprenticed to a smith" becomes "you apprenticed to Ariniel Thorne, at the market
  in Pangrella, and she still has your second-best hammer".

The ties are why this is not a personality quiz. The three laws say a state is a tag and
a tag is asked by prefix; a background that grants `knows.the-market-at-<town>` puts a
fact in the narrator's brief that it may state as true, and a scheme's `has(pc, knows.…)`
can open on it. A background is a way into the world's own material, not decoration on
the sheet.

**No background gives a number the Race Builder would charge for.** Two skill points and
a language is the ceiling, deliberately: 1e has no background system and the moment one
grants a combat bonus it is competing with feats, which are priced. What it grants
instead is *standing* — people who know you, places you can walk into, and things you are
assumed to know.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from django.conf import settings

from . import states
from pathfindergm import files

# What a tie can reach for in the world. Deliberately the same vocabulary the quest
# schemes fill their slots from (`rules/schemes.PLACE_KINDS`, its role words), because a
# background that knows a trader and a scheme that wants one should mean the same person.
TIE_PLACES = ("market", "lodging", "gate", "temple", "guildhall", "road", "wild")
TIE_ROLES = ("trader", "fixer", "kin", "guard officer", "standing", "healer")

# The ceiling. A background is standing, not power.
MAX_SKILL_POINTS = 2

_ALL: dict[str, dict] | None = None


def _dir() -> Path:
    return Path(settings.BASE_DIR) / "content" / "backgrounds"


def _homebrew() -> Path:
    return Path(settings.CAMPAIGN_DIR).parent / "homebrew" / "backgrounds"


def all_backgrounds() -> dict[str, dict]:
    """Every background, shipped then homebrew, the latter winning on a shared id."""
    global _ALL
    if _ALL is None:
        out: dict[str, dict] = {}
        for folder in (_dir(), _homebrew()):
            if not folder.is_dir():
                continue
            for path in sorted(folder.glob("*.json")):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except Exception as exc:
                    files.unreadable(path, exc)
                    continue
                entries = data.get("backgrounds") if isinstance(data, dict) else None
                if not isinstance(entries, list):
                    entries = [data] if isinstance(data, dict) and data.get("id") else []
                for e in entries:
                    if isinstance(e, dict) and e.get("id"):
                        out[str(e["id"])] = e
        _ALL = out
    return _ALL


def get(background_id: str) -> dict | None:
    return all_backgrounds().get(str(background_id or "").strip().lower())


def validate(doc: dict) -> list[str]:
    """Everything wrong with a background document, with the fix named.

    Same contract as the race and scheme validators: refuse on save, name the repair,
    and never let a document through that would silently do nothing.
    """
    problems: list[str] = []
    if not str(doc.get("id") or "").strip():
        problems.append("id: a background needs an id.")
    if not str(doc.get("name") or "").strip():
        problems.append("name: a background needs a name.")
    if not str(doc.get("summary") or "").strip():
        problems.append("summary: one line for the picker, or nobody can choose it.")

    points = 0
    for i, m in enumerate(doc.get("modifiers") or []):
        where = f"modifiers[{i + 1}]"
        if not isinstance(m, dict):
            problems.append(f"{where}: a modifier is an object.")
            continue
        kind = str(m.get("type") or "")
        if kind != "skill_mod":
            problems.append(
                f"{where}: a background grants skill_mod and nothing else — "
                f"{kind or 'nothing'} is priced territory and belongs to feats.")
            continue
        amount = int(m.get("amount", 0) or 0)
        if amount < 0:
            problems.append(f"{where}: a background does not take skill away.")
        points += amount
        if str(m.get("bonus_type") or "") != "background":
            problems.append(
                f"{where}: the bonus type is \"background\", so two backgrounds cannot "
                f"stack and a trait can still be taken beside it.")
    if points > MAX_SKILL_POINTS:
        problems.append(
            f"modifiers: {points} points of skill bonus, and the ceiling is "
            f"{MAX_SKILL_POINTS} — a background is standing, not power.")

    for i, tag in enumerate(doc.get("tags") or []):
        if not re.fullmatch(r"[a-z][a-z0-9.\-_$]*", str(tag)):
            problems.append(f"tags[{i + 1}]: {tag!r} is not a tag.")
        elif not str(tag).startswith(("knows.", "background.", "role.")):
            problems.append(
                f"tags[{i + 1}]: a background may make true knows.*, background.* or "
                f"role.* — not {tag!r}.")

    for i, tie in enumerate(doc.get("ties") or []):
        where = f"ties[{i + 1}]"
        if not isinstance(tie, dict):
            problems.append(f"{where}: a tie is an object.")
            continue
        if tie.get("place") and tie["place"] not in TIE_PLACES:
            problems.append(f"{where}: place is one of {', '.join(TIE_PLACES)}.")
        if tie.get("role") and tie["role"] not in TIE_ROLES:
            problems.append(f"{where}: role is one of {', '.join(TIE_ROLES)}.")
        if not tie.get("place") and not tie.get("role"):
            problems.append(f"{where}: a tie reaches for a place or a role; this does "
                            f"neither, so nothing fills it.")
        if not str(tie.get("says") or "").strip():
            problems.append(
                f"{where}: a tie needs a `says` — the sentence the narrator may state "
                f"as true. A tie nobody can say is a slot filled for nothing.")
        if "$who" not in str(tie.get("says", "")) and "$where" not in str(tie.get("says", "")):
            problems.append(
                f"{where}: `says` names neither $who nor $where, so it would read the "
                f"same in every world — which is the thing this is for.")
    return problems


def line(doc: dict) -> str:
    """The one sentence the forge shows under the name."""
    bits = [str(doc.get("summary") or "").strip()]
    for m in doc.get("modifiers") or []:
        if isinstance(m, dict) and m.get("type") == "skill_mod":
            bits.append(f"+{int(m.get('amount', 0) or 0)} {m.get('target', '')}")
    langs = doc.get("languages") or []
    if langs:
        bits.append("speaks " + ", ".join(str(x) for x in langs))
    return " · ".join(b for b in bits if b)


def catalogue() -> list[dict]:
    """Every background the picker offers, in the order a person would read them."""
    out = []
    for bid, doc in sorted(all_backgrounds().items(),
                           key=lambda kv: str(kv[1].get("name") or kv[0])):
        if validate(doc):
            continue
        out.append({
            "id": bid,
            "name": doc.get("name", bid.title()),
            "summary": doc.get("summary", ""),
            "line": line(doc),
            "group": doc.get("group", "other"),
            "traits": list(doc.get("traits") or []),
            "ties": [{"says": t.get("says", ""), "place": t.get("place", ""),
                      "role": t.get("role", "")} for t in doc.get("ties") or []],
            "languages": list(doc.get("languages") or []),
        })
    return out


def bind(engine, actor) -> list[dict]:
    """Fill this character's background ties from the world they are standing in.

    Called once, when the campaign begins. Everything a background says about the past
    is a slot until this runs: "you were apprenticed to a smith" is a sentence any world
    could produce, and "you were apprenticed to Ariniel Thorne at the market in
    Pangrella" is a fact about *this* one — which is the whole difference between a
    background and a personality quiz.

    The people come from the same door the quest schemes use, so a background that knows
    a trader and a scheme that wants one are talking about the same person; and the tag
    each tie grants lands through the one applicator with `origin` set, so it is as
    removable and as auditable as anything else.

    Returns what was bound, for the opening to say and for tests to read.
    """
    from .activeeffect import ActiveEffect
    from . import schemes as schemes_mod

    doc = get(getattr(actor, "background", ""))
    if not doc:
        return []
    bound: list[dict] = []
    taken: set = set()
    filled: dict = {}
    for i, tie in enumerate(doc.get("ties") or []):
        who = where = ""
        if tie.get("place"):
            got = schemes_mod._place_for(engine, tie["place"], {})
            if got:
                where = str(got.get("name") or "")
                filled[f"place{i}"] = got
        if tie.get("role"):
            # `place=False`: a tie is a fact about the character's PAST, so it wants the
            # world's name for somebody and not a body in the opening scene. Reported
            # 2026-09-20 — "drenn ironvale is named has a part of my background but does
            # not belong in the scene" — and reproduced on a clean scene, where binding
            # the `apprenticed` background added Ariniel Thorne as a second actor.
            got = schemes_mod._role_for(engine, f"tie{i}",
                                        {"role": tie["role"], "level": "pc"},
                                        filled, taken, place=False)
            if got:
                who = str(got.get("name") or "")
        says = str(tie.get("says") or "")
        # A tie whose people or places the world could not supply says nothing rather
        # than saying "$who". A half-filled sentence in the narrator's brief is worse
        # than a missing one: the brief is the half the model is allowed to believe.
        if ("$who" in says and not who) or ("$where" in says and not where):
            continue
        says = says.replace("$who", who).replace("$where", where)
        bound.append({"says": says, "who": who, "where": where})
    if bound:
        actor.apply_effect(ActiveEffect(
            name=str(doc.get("name") or doc["id"]), kind="background",
            key=f"background:{doc['id']}", source=f"background:{doc['id']}",
            origin=f"background:{doc['id']}", duration="until-dismissed",
            tags=tuple(doc.get("tags") or ())))
    return bound


def remembered(actor) -> list[str]:
    """The bound ties as sentences, off the effect the bind left behind."""
    return [str(x) for x in (getattr(actor, "background_ties", None) or [])]


def groups() -> list[str]:
    """The headings the picker sorts under, from the documents themselves."""
    seen: list[str] = []
    for entry in catalogue():
        if entry["group"] not in seen:
            seen.append(entry["group"])
    return seen


def acquaint(engine, actor, bound: list[dict]) -> str:
    """Make the person standing beside a local character somebody who knows them.

    Reported 2026-09-22, four sessions in: *"if you have picked a background and are know
    to the place you start then the person you start next to does not need to be a
    stranger. they could be a friend or travel companion."*

    They were right, and the shipped documents say so out loud: eleven of the fourteen
    backgrounds tie the character to a place in the settlement the game opens in — "You
    kept a pitch at $where and the neighbours still nod", "You grew up at $where and the
    room still quietens when you come in", `knows.every-face-here` — and the opening put
    a stranger beside every one of them. The text already knew (`campaign._standing`
    stops saying "a stranger here" once ties are bound); the SCENE did not.

    What this does NOT do is add anybody. That was reported as a defect on 2026-09-20 —
    "drenn ironvale is named as part of my background but does not belong in the scene" —
    and `bind` answers it with `place=False`, which stands. The person here is the one
    the opening already rolled; what changes is who they are to the player.

    Two facts, both through the one applicator each belongs to: the attitude track moves
    to friendly (1e's own word for somebody who "will chat, advise, offer limited help"),
    and `bond.knows-you` is the tag every reader asks by prefix. Returns their name, or
    "" when nobody qualified — a character with no local tie keeps the stranger they had,
    because being new somewhere is a legitimate way to start.
    """
    from . import attitude as attitude_mod
    from .activeeffect import ActiveEffect

    if actor is None or not any(str(b.get("where") or "").strip() for b in bound or []):
        return ""
    scene = getattr(engine, "scene", None)
    if scene is None:
        return ""
    # Whoever the opening put within speaking distance, and only them: this runs once,
    # before the first turn, when the scene holds the player and one other person.
    beside = [a for a in scene.actors.values() if not a.is_pc and not a.is_down]
    if len(beside) != 1:
        return ""
    who = beside[0]
    doc = get(getattr(actor, "background", "")) or {}
    source = f"background:{doc.get('id') or 'background'}"
    who.apply_effect(ActiveEffect(
        name="knows you", kind="bond", key=f"{source}:knows-you", source=source,
        origin=source, duration="until-dismissed", tags=(states.KNOWS_YOU,)))
    # To the step at which somebody walks out of here with you — the same named step
    # `_op_company` asks for, because being known here is what makes a companion
    # possible on turn one. Named through the track's own constant: the commit that
    # introduced `COMES_ALONG` so that no reader spells an attitude spelled one here.
    engine.settle_attitude(who, attitude_mod.COMES_ALONG, None, source)
    return str(who.name or "")

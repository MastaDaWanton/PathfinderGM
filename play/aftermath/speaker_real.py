"""A speaker the prose introduced, who spoke to the player, is made real (item 20.4).

Measured on the Bobby playtest, 2026-09-28, turn 9: in the woods "a man in a stained
leather jerkin" sharpened a skinning knife and spoke three lines to the player — "The road
to Grotburrow isn't for the faint of heart", "You looking for a shortcut, or just lost?".
The prose call tagged them to `new1`, a ref nobody held: `speech-tags` logged
`unknown_refs: ["new1"]`, 3 lines, 0 attributed. The man existed as a population record
only; nobody was hailed, no conversation opened, and he became an actor (c8) one turn
later, only because the player turned to him.

The owner's ruling (Q5, 2026-09-28): a speaker addressing the player gets a body through
the arrival door — but only when matched to the record this beat wrote. So, before the
hails are read (the "people" stage runs just before `hailed_by`):

  * the lines whose tag named nobody here (`who` empty, the claim kept in `was`), and to
    the player (`to` "you", or no `to` with "you" in the words);
  * the people this beat recorded at the party's spot with no body yet, whose words the
    page uses (`checks._people.names_person`) — PDNC's lesson (Vishnubhotla et al. 2023):
    attribution restricted to people already resolved went from 0.40 to 0.62;
  * exactly one such person, one claimed speaker: they walk on through the one door
    (`judgement.embody` → `Scene.arrive`, a square with it — the item-14 ruling), wearing
    the face their record rolled, and the lines are re-tagged to them (`"made": ref`).

Anything less certain changes nothing and says why in a row. In a fight the prose makes
no bodies at all (`GMAgent._undeclared_arrivals` rewrites the newcomer out), so this step
stands aside.
"""
from __future__ import annotations

import re

STAGE = "people"
ORDER = 10
DOORS = frozenset({"turn", "carry_on", "opening"})

_YOU = re.compile(r"\b(?:you|your|you're|you've|you'll)\b", re.I)


def _to_the_player(rec: dict) -> bool:
    to = str(rec.get("to") or "")
    return to == "you" or (not to and bool(_YOU.search(str(rec.get("line") or ""))))


def step(ctx) -> list[dict]:
    scene = ctx.scene
    lines = [r for r in (ctx.said or []) if not r.get("who") and _to_the_player(r)]
    if not lines:
        return []
    if getattr(scene, "in_encounter", False):
        return [{"kind": "speaker-real", "made": "", "lines": len(lines),
                 "why": "in a fight the prose brings nobody in"}]
    claimed = {str(r.get("was") or "") for r in lines}
    if len(claimed) != 1:
        return [{"kind": "speaker-real", "made": "", "lines": len(lines),
                 "why": f"lines claimed for {len(claimed)} different speakers"}]
    from gm.checks._people import names_person
    from gm.narration import unquoted

    narration = unquoted(ctx.text)
    here = getattr(scene, "at", None)
    held = set(getattr(scene, "actors", {}) or {})
    candidates = [rec for rec in (getattr(scene, "population", None) or {}).values()
                  if rec.get("spot") == here
                  and not (rec.get("ref") and rec["ref"] in held)
                  and names_person(narration, str(rec.get("phrase") or ""))]
    # One person, however many phrases the page recorded them under: two records whose
    # head words agree ("man in a stained leather jerkin", "man with the whetstone") are
    # the same man described twice; two different heads are two people.
    from gm.checks._people import head_of

    heads = {head_of(str(r.get("phrase") or "")) for r in candidates}
    if len(heads) != 1:
        return [{"kind": "speaker-real", "made": "", "lines": len(lines),
                 "why": f"{len(candidates)} people this beat could mean"}]
    rec = min(candidates, key=lambda r: int(re.sub(r"\D", "", str(r.get("id"))) or 0))
    from gm import judgement

    actor = judgement.embody(scene, str(rec["phrase"]), world=ctx.world, rec=rec)
    if not any(e.get("ref") == actor.ref for e in getattr(scene, "cast", []) or []):
        scene.cast.append({"who": rec["phrase"], "turn": int(rec.get("turn", 0) or 0),
                           "ref": actor.ref})
    for r in lines:
        r["who"] = actor.ref
        r["made"] = actor.ref
    return [{"kind": "speaker-real", "made": actor.ref, "phrase": rec["phrase"],
             "record": rec.get("id", ""), "lines": len(lines),
             "square": list(scene.positions.get(actor.ref) or [])
             if getattr(scene, "positions", None) else []}]

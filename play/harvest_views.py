"""The harvest sheet's API (docs/leatherworking-contracts.md §5.2; UI plan §6.9; lane C).

"Harvest the carcass" is a scene action across every craft, not a bench method: one sheet
over the table lists every part the body carries for every craft the character has, each
with its skill, DC, roll, odds, time and yield, and the dangers its body holds. The page
sends what the player chose — which carcass, which part, the face of their own d20, the
harvest game's defect area — and the server answers with every number (the bench's form of
"no model authors a number"; rules/harvest.py does the rules).

  GET  api/harvest                 the carcasses here that have something to take
  GET  api/harvest/<ref>           one carcass's sheet
  POST api/harvest/take            {creature, key, face?, danger_faces?} → the roll, the
                                   dangerous body's second rounds at the first cut, the part
                                   landed (a hide at once, at the unplayed grade), a token
                                   when the harvest game is to be played
  POST api/harvest/finish          {token, defects? | score?} → the hide re-graded

A part is taken by the roll whatever it says (no retry; plan §5.8), and what it gives is on
the shelf before the game is played, so a reload between the two loses nothing: the token
only re-grades. Tokens live in this process's memory, as the benches' do.
"""
from __future__ import annotations

import math
import secrets

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from rules import harvest, worldclass

from . import campaign as campaign_mod
from .apiutil import read_body

# Pending games, by campaign id then token: {"pending", "ref", "key", "name"}.
_PENDING: dict[str, dict[str, dict]] = {}


def _err(text: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"error": text}, status=status)


def _now(c) -> int:
    return int(c.scene.clock_minutes or 0)


def _clock(c) -> dict:
    minute = _now(c)
    hour, mins = (minute % 1440) // 60, minute % 60
    twelve = hour % 12 or 12
    return {"minute": minute, "day": minute // 1440 + 1,
            "label": f"Day {minute // 1440 + 1}, {twelve}:{mins:02d}"
                     f"{'am' if hour < 12 else 'pm'}"}


def _when(minute) -> str:
    if minute is None:
        return ""
    minute = int(minute)
    hour, mins = (minute % 1440) // 60, minute % 60
    return (f"Day {minute // 1440 + 1}, {hour % 12 or 12}:{mins:02d}"
            f"{'am' if hour < 12 else 'pm'}")


def _span(minutes: int) -> str:
    from rules import sky

    return sky.span_words(max(0, int(minutes)))


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def _ready(request):
    c = campaign_mod.current()
    pc = c.scene.pc()
    if pc is None:
        return None, None, _err("There is no character to do the work.", 409)
    return c, pc, None


def _carcasses(c) -> list:
    """The dead bodies in the party's place (never the player)."""
    return [a for a in c.scene.actors.values()
            if not getattr(a, "is_pc", False) and harvest.is_dead(a)]


def _danger_rows(carcass) -> list[dict]:
    return [{"kind": r["kind"], "words": r["words"], "dc": r["dc"], "faced": r["faced"],
             "dice": r["dice"]} for r in harvest.danger_rounds(carcass)]


def _row_view(p: dict, pc) -> dict:
    """One part as the sheet draws it: the server's numbers, the words the page prints."""
    from rules import leatherworker as lw

    out = dict(p)
    out["taken_words"] = _when(p.get("taken"))
    if p["branch"] in ("hide", "scales"):
        q = lw.quarters(p["units"])
        per = harvest._salt_per_unit()
        out["units_words"] = lw.units_word(q)
        out["salt_needed"] = int(math.ceil(q / 4 * per))
        out["salt_covers"] = harvest.salt_measures(pc) >= out["salt_needed"]
    else:
        out["units_words"] = "1"
    out["deed_words"] = ("Taking this is a deed others may hear of." if p.get("deed")
                         else "")
    out["need_words"] = (f"{p['skill'].title()} DC {p['dc']}, you need {p['need']} or better"
                         if p.get("need") is not None else
                         f"{p['skill'].title()} DC {p['dc']}: {p.get('impossible') or ''}")
    return out


def _sheet(c, pc, carcass) -> dict:
    now = _now(c)
    block = harvest.block_of(carcass) or {}
    ok, why = harvest.harvestable(carcass, now=now)
    rows = harvest.parts(carcass, pc, now=now) if ok or carcass.harvested else []
    every = harvest.parts(carcass, pc, now=now, every_craft=True) if ok else []
    mine = {r["key"] for r in rows}
    others: dict[str, dict] = {}
    for r in every:
        if r["key"] not in mine and r["taken"] is None:
            o = others.setdefault(r["craft"], {"craft": r["craft"],
                                               "craft_word": r["craft_word"], "count": 0})
            o["count"] += 1
    died = harvest.died_at_of(carcass, now)
    hours = int(harvest.rules().get("carcass_hours", 24))
    cr = block.get("cr") or ""
    return {
        "creature": {"ref": carcass.ref, "name": carcass.name,
                     "size": harvest.size_of(block).title(),
                     "cr": str(cr), "type": harvest.creature_kind(block),
                     "plan": harvest.plan_of(carcass),
                     "dead_minutes": now - died,
                     "dead_words": (f"Dead {_span(now - died)}." if now - died >= 1
                                    else "Dead a moment."),
                     "keeps_words": (f"It can be worked for {_span(died + hours * 60 - now)} "
                                     f"more." if ok else "")},
        "harvestable": ok, "why": why,
        "parts": [_row_view(r, pc) for r in rows if r["taken"] is None],
        "taken": [_row_view(r, pc) for r in rows if r["taken"] is not None],
        "others": sorted(others.values(), key=lambda o: o["craft"]),
        "dangers": _danger_rows(carcass) if ok else [],
        "clock_words": ("Hides keep 48 hours from the harvest; salt stops the clock, "
                        "one measure of curing salt a hide unit."),
        "salt": harvest.salt_measures(pc),
        "clock": _clock(c),
    }


@require_GET
def harvest_here(request):
    """The carcasses in the party's place, for the scene panel's Harvest button (UI plan
    §6.9: "only while the carcass is harvestable and the character has a craft that wants
    a part"). Humanoids never appear: the panel offers nothing on them to refuse.

    → {"carcasses": [{"ref", "name", "parts": int, "others": int}],
       "breathing": [{"ref", "name"}] (down and dying: not a carcass yet), "clock"}"""
    c, pc, refused = _ready(request)
    if refused:
        return refused
    now = _now(c)
    out = []
    for a in _carcasses(c):
        ok, _ = harvest.harvestable(a, now=now)
        if not ok:
            continue
        mine = [p for p in harvest.parts(a, pc, now=now) if p["taken"] is None]
        every = [p for p in harvest.parts(a, pc, now=now, every_craft=True)
                 if p["taken"] is None]
        if every:
            out.append({"ref": a.ref, "name": a.name, "parts": len(mine),
                        "others": len(every) - len(mine)})
    # A beast dropped in a fight usually lies DYING, not dead (1e's ladder: dead at -Con),
    # and is no carcass yet. Named so the page can say "finish it first" rather than show
    # nothing (measured live 2026-10-08: a wolf at -12 after the fight's last blow).
    breathing = [{"ref": a.ref, "name": a.name} for a in c.scene.actors.values()
                 if not getattr(a, "is_pc", False) and a.is_down and not harvest.is_dead(a)
                 and not harvest.banned(harvest.block_of(a)) and harvest.tagged(a)]
    c.save()            # `died_at` may have been stamped on a body from an older save
    return JsonResponse({"carcasses": out, "breathing": breathing, "clock": _clock(c)})


@require_GET
def harvest_sheet(request, ref: str):
    """One carcass's sheet.

    → {"creature": {"ref", "name", "size", "cr", "type", "plan", "dead_minutes",
                    "dead_words", "keeps_words"},
       "harvestable": bool, "why": str,
       "parts": [row], "taken": [row], "others": [{"craft", "craft_word", "count"}],
       "dangers": [{"kind", "words", "dc", "faced", "dice"}],
       "clock_words", "salt": int, "clock"}

    A row: {"key", "craft", "craft_word", "branch", "material", "name", "tier", "generic",
    "form", "skill", "dc", "bonus", "terms": [{"label", "value"}], "need", "impossible",
    "need_words", "units", "units_words", "minutes", "deed", "deed_words", "taken",
    "taken_words", "game": "harvest" | None, and for a hide "salt_needed", "salt_covers"}."""
    c, pc, refused = _ready(request)
    if refused:
        return refused
    carcass = c.scene.actors.get(str(ref or "").strip())
    if carcass is None or getattr(carcass, "is_pc", False):
        return _err("There is no such body here.", 404)
    if not harvest.is_dead(carcass):
        return _err(f"{_cap(harvest._the(carcass.name))} is still breathing: finish it first.",
                    409)
    body = _sheet(c, pc, carcass)
    c.save()
    return JsonResponse(body)


def _face(raw) -> tuple[int | None, str]:
    if raw is None:
        return None, ""
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        return None, "The face must be a number from 1 to 20."
    try:
        face = int(str(raw).strip())
    except ValueError:
        return None, "The face must be a number from 1 to 20."
    if not 1 <= face <= 20:
        return None, f"{face} is not a face of a d20."
    return face, ""


def _tuning(row: dict, plan: str = "") -> dict:
    g = dict(harvest.rules().get("game") or {})
    rank = worldclass.tier_rank(row.get("tier") or "common")
    band = dict(g.get("band") or {})
    band["narrow"] = rank >= 3
    return {"method": "harvest", "game": "harvest",
            "difficulty": round(min(0.95, float(g.get("difficulty", 0.45))
                                    + float(g.get("rarity_step", 0.05)) * max(0, rank - 1)), 4),
            "band": band, "seconds": g.get("seconds", 8),
            "surface": _surface(row), "plan": plan}


def _surface(row: dict) -> str:
    from rules import leatherworker as lw

    doc = lw.material(row.get("material") or "") or {}
    return str(doc.get("surface") or "")


@require_POST
def harvest_take(request):
    """Take one part: {"creature": ref, "key": "hide:wolf-pelt", "face": 1-20 (optional:
    the server rolls), "danger_faces": {"poison": 1-20, ...} (optional)}.

    At the first part taken off a dangerous body, each danger's second round is rolled
    first (docs/deeds-plan.md §13.3) with the same skill and bonus, against the creature's
    own DC; exposure only on a miss by 5 or more.

    → {"roll": {"face", "bonus", "total", "dc", "margin", "success", "terms"},
       "verdict": {"verdict", "natural", "word"},
       "dangers": [{"kind", "words", "dc", "face", "total", "margin", "exposed",
                    "doses", "save_dc", "tells"}],
       "part": {"key", "name", "craft"}, "stock": [{"key", "name", "form", "units",
       "grade", "material"}], "carried": [{"id", "name", "count"}], "grade": int | None,
       "lost": str, "salt_spent": int, "yielded": bool, "deed": str | None,
       "deed_record": {...} | None,
       "token": str | None, "tuning": {...} | None, "minutes", "mastery", "tells",
       "sheet": {...the carcass's sheet after...}, "clock"}"""
    c, pc, refused = _ready(request)
    if refused:
        return refused
    if c.scene.in_encounter:
        return _err("You are in a fight. The carcass waits until it is over.", 409)
    if c.scene.awaiting:
        return _err("There is a roll waiting on you at the table.", 409)
    body = read_body(request)
    ref = str(body.get("creature") or "").strip()
    key = str(body.get("key") or "").strip().lower()
    carcass = c.scene.actors.get(ref)
    if carcass is None or getattr(carcass, "is_pc", False):
        return _err("There is no such body here.", 404)
    now = _now(c)
    ok, why = harvest.harvestable(carcass, now=now)
    if not ok:
        return _err(f"Nothing can be taken off {harvest._the(carcass.name)}: {why}.", 409)
    every = {p["key"]: p for p in harvest.parts(carcass, pc, now=now, every_craft=True)}
    row = every.get(key)
    if row is None:
        return _err(f"{_cap(harvest._the(carcass.name))} has no part {key!r}.", 404)
    if row["taken"] is not None:
        return _err(f"The {row['name']} has already been taken, {_when(row['taken'])}.", 409)
    if key not in {p["key"] for p in harvest.parts(carcass, pc, now=now)}:
        return _err(f"Taking the {row['name']} is {row['craft_word']} work, and you are no "
                    f"{row['craft_word']}.", 409)
    face, bad = _face(body.get("face"))
    if bad:
        return _err(bad)
    given = body.get("danger_faces") or {}
    if not isinstance(given, dict):
        return _err("danger_faces must be {kind: face}.")

    engine = c.engine()
    dangers_out = []
    first = not any(not k.startswith("danger:") for k in (carcass.harvested or {}))
    if first:
        for rnd in harvest.danger_rounds(carcass):
            if rnd["faced"]:
                continue
            dface, bad = _face(given.get(rnd["kind"]))
            if bad:
                return _err(bad)
            if dface is None:
                dface = engine.dice.d20(label=f"Harvest: {rnd['words']}",
                                        visibility="player").faces[0]
            dtotal = dface + row["bonus"]
            got = harvest.face_danger(engine, pc, carcass, rnd["kind"], dtotal, now=now,
                                      dice=engine.dice)
            dangers_out.append({"kind": rnd["kind"], "words": rnd["words"], "dc": got["dc"],
                                "face": dface, "total": dtotal, "margin": got["margin"],
                                "exposed": got["exposed"], "doses": got.get("doses", 0),
                                "save_dc": got.get("save_dc"),
                                "tells": got["tells"]})
    if face is None:
        face = engine.dice.d20(label=f"Harvest: {row['name']}", visibility="player").faces[0]
    total = face + row["bonus"]
    got = harvest.take(pc, carcass, key, total, now=now, scene=c.scene, dice=engine.dice)
    c.scene.advance(row["minutes"])

    track = worldclass.get(row["craft"])
    progress = pc.track(row["craft"])
    award = worldclass.award_step(track, progress, method="harvest",
                                  ingredient_id=row["material"],
                                  rarity_rank=worldclass.tier_rank(row["tier"]),
                                  quality_index=0, success=bool(got["ok"]), name=row["name"],
                                  count=1, noun="part")
    token = None
    tuning = None
    if got.get("game"):
        token = secrets.token_urlsafe(16)
        _PENDING.setdefault(c.id, {})[token] = {"pending": got["game"], "ref": carcass.ref,
                                                "key": key, "name": row["name"]}
        tuning = _tuning(row, harvest.plan_of(carcass))
    tells = [t for d in dangers_out for t in d["tells"]] + list(got["tells"])
    r = row
    c.transcript.append({"who": "gm", "kind": "consequence", "text": " ".join(
        tells + [f"({r['skill'].title()} d20 {face}{r['bonus']:+d} = {total} vs DC "
                 f"{r['dc']}.)"] + ([got["lost"]] if got["lost"] else []))})
    c.save()
    return JsonResponse({
        "roll": {"face": face, "bonus": row["bonus"], "total": total, "dc": row["dc"],
                 "margin": got["margin"], "success": got["ok"], "terms": row["terms"]},
        "verdict": {"verdict": "success" if got["ok"] else "failure", "natural": face,
                    "word": "Success" if got["ok"] else "Failure"},
        "dangers": dangers_out,
        "part": {"key": key, "name": row["name"], "craft": row["craft"]},
        "stock": got["stock"], "carried": got["carried"], "grade": got["grade"],
        "lost": got["lost"], "salt_spent": got["salt_spent"], "yielded": got["yielded"],
        "deed": got.get("deed_tag"),
        # The deeds module's `deed` effect record (rules/deeds.py `record`), on the first
        # part of a deed-carcass only; None while the stub stands in.
        "deed_record": got.get("deed"),
        "token": token, "tuning": tuning, "minutes": row["minutes"],
        "mastery": {"lines": list(award.get("reasons") or []),
                    "total": award.get("total", progress.mp),
                    "level": award.get("level", progress.level),
                    "levelled": list(award.get("levelled") or [])},
        "tells": tells,
        "sheet": _sheet(c, pc, carcass),
        "clock": _clock(c),
    })


@require_POST
def harvest_finish(request):
    """The harvest game's result: {"token", "defects": 0..1 (the hole and score area the
    game left; preferred), or "score": 0..1 (read as 1 - score when no defects come)}.
    The server turns the area into the grade (UNIDO bands, plan §5.7), a near miss one
    worse and never better than 3, and re-shelves the hide at it.

    → {"grade": 0-4, "grade_words", "stock": [{"key", "name", "form", "units", "grade",
       "material"}], "tells", "sheet"}"""
    c, pc, refused = _ready(request)
    if refused:
        return refused
    body = read_body(request)
    token = str(body.get("token") or "")
    pend = None
    for t, p in list((_PENDING.get(c.id) or {}).items()):
        if token and secrets.compare_digest(t, token):
            pend = _PENDING[c.id].pop(t)
            break
    if pend is None:
        return _err("That hide is no longer waiting on the knife. It kept the grade it "
                    "came off at.", 409)
    defects = body.get("defects")
    if defects is None and body.get("score") is not None:
        try:
            defects = 1.0 - float(body.get("score"))
        except (TypeError, ValueError):
            defects = None
    if defects is None:
        return _err("The game sends its defect area (0 to 1).")
    try:
        defects = min(1.0, max(0.0, float(defects)))
    except (TypeError, ValueError):
        return _err("The defect area must be a number from 0 to 1.")
    got = harvest.regrade(pc, pend["pending"], defects)
    grade = got["grade"]
    words = "a reject: scraps only" if grade == 0 else f"grade {grade}"
    tell = f"{pc.name} works the {pend['name'].lower()} free: {words}."
    c.transcript.append({"who": "gm", "kind": "consequence", "text": tell})
    carcass = c.scene.actors.get(pend["ref"])
    c.save()
    return JsonResponse({"grade": grade, "grade_words": words, "stock": got["stock"],
                         "tells": [tell],
                         "sheet": _sheet(c, pc, carcass) if carcass is not None else None})

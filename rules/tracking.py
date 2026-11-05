"""Finding tracks: 1e's Survival check, against what the engine knows has crossed the ground.

Added 2026-10-09, from one live run (gemma-4-12B, Pangrella, turn 10): "I look for tracks in
the grass" rolled nothing — the reader called it a `search`, which owed no op, and the plan's
forage was struck as "not a forage" — and the narrator, with no tell to dress, wrote "a clear,
recent path... from a heavy cart" that no part of the engine held. Nothing in the world had
made a trail; the page invented one.

The rule (Core Rulebook p.107, Survival, "Follow Tracks"; d20pfsrd.com/skills/survival, read
2026-10-09): "To find tracks or to follow them for 1 mile requires a successful Survival
check", against a DC set by the ground — very soft 5 ("fresh snow, thick dust, wet mud"),
soft 10, firm 15 ("most normal outdoor surfaces (such as lawns, fields, woods, and the
like)"), hard 20 ("bare rock or an indoor floor, ... most streambeds") — and raised or lowered
by the creature's size, +1 for every 24 hours since the trail was made, and poor visibility
(moonlight +3, a moonless or overcast night +6). Untrained characters may make the check to
FIND tracks. It is "at least a full-round action", so no clock is charged here.

**What there is to find is the engine's, never the page's.** The trails are the people the
campaign holds whose record says the party saw them on this ground and who are not on it now
(`population` records: `seen_at`, `last_seen`), and the people standing here now, whose own
tracks lead to where they stand. A check that succeeds against ground nobody known has crossed
finds that nobody has — it does not find a trail the world never laid. A check that fails
finds no sign it can trust, which says nothing either way: the book's failure.

**A quarry is the engine's too** (2026-10-27, the owner's report on 0.2.21): "I continue to
track the caravan" — a caravan the narrator had invented at a hiring table and the engine never
held — rolled Survival, found the tracks of whoever the party had seen in the fields, and the
beat called them the caravan's; "I follow the tracks in search of the caravan" walked the
party a quarter hour to "the fields", a walk the plan made up, and the next track went
nowhere. Now a `track` names what it is after (`quarry`, the player's own words, kept only
when the reader says they name the maker and not the marks — `interpret.confirm_quarry`)
and the engine answers it from what it holds (`quarry_of`): somebody it knows, whose trail is
found or is not, or nothing at all — "no trail of the caravan crosses this ground", said
plainly, before any narrator can lay one. CircleMUD's `track` is the same answer in a MUD:
the target is looked up world-wide first, and "No one is around by that name" comes back
with no roll at all (tbaMUD src/graph.c, `do_track`).

**Following** a trail found (`follow`) walks the party to where its maker is now — the
engine's own record of them (`Actor.at`), within this settlement's ground; a trail that
leads off to another settlement is a journey, and is said so, not walked. One Survival check
for the whole walk, not one a mile: the CRB's per-mile check is for a trail across country,
and every walk here is inside one settlement's ground (said, not hidden).

Not built (said, not hidden): following a trail mile by mile across country, rain since the
trail was made, a group's -1 per three creatures, and the hour's wait before a retry
outdoors.
"""
from __future__ import annotations

from . import sky

# The ground's surface, by the place's terrain (rules/biomes.py LAND + coast, underground).
# The CRB names lawns, fields and woods as firm and bare rock and indoor floors as hard; the
# rest are read off its definitions: a snowfield and a fen hold "deep, clear impressions";
# sand and a beach yield "frequent but shallow" ones.
SURFACE = {
    "tundra": "very soft", "swamp": "very soft",
    "desert": "soft", "coast": "soft", "jungle": "soft",
    "grassland": "firm", "farmland": "firm", "forest": "firm", "hills": "firm",
    "ruins": "hard", "mountain": "hard", "urban": "hard", "underground": "hard",
}
SURFACE_DC = {"very soft": 5, "soft": 10, "firm": 15, "hard": 20}
# Size of the creature that made the trail (CRB p.107's table).
SIZE_DC = {"fine": 8, "diminutive": 4, "tiny": 2, "small": 1, "medium": 0, "large": -1,
           "huge": -2, "gargantuan": -4, "colossal": -8}
# Poor visibility, by the engine's own light (`Scene.ambient_light`): its "dim" is the book's
# moonlit night, its "dark" a place with no light at all.
LIGHT_DC = {"dim": 3, "dark": 6}


def ground(scene) -> tuple[str, int]:
    """(the surface's name, its base DC) where the party stands. Indoors is an indoor floor."""
    from . import places as places_mod

    at = str(getattr(scene, "at", "") or "")
    try:
        roofed = bool(at) and places_mod.is_indoors(at)
    except Exception:  # noqa: BLE001 — a place the floorplan cannot read is open ground
        roofed = False
    surface = "hard" if roofed else SURFACE.get(places_mod.terrain_of(at), "firm")
    return surface, SURFACE_DC[surface]


def trails(scene) -> list[dict]:
    """Every trail the engine knows on this ground: {ref, name, hours_ago, here, size}.

    People standing here (not the player, not who came with the party — their tracks are
    the party's own), then people the party saw here who have gone, newest first."""
    from . import population

    at = str(getattr(scene, "at", "") or "")
    now = int(getattr(scene, "clock_minutes", 0) or 0)
    out: list[dict] = []
    came = set(getattr(scene, "came_along", ()) or ())
    for ref, a in (getattr(scene, "actors", {}) or {}).items():
        if a.is_pc or ref in came or a.has_state("state.down.dead"):
            continue
        out.append({"ref": ref, "name": a.name, "hours_ago": 0, "here": True,
                    "size": str(getattr(a, "size", "medium") or "medium").lower()})
    present = {t["ref"] for t in out}
    people = getattr(scene, "people", {}) or {}
    gone = []
    for rec in (getattr(scene, "population", {}) or {}).values():
        ref = rec.get("ref")
        if not ref or ref in present or rec.get("seen_at") != at:
            continue
        body = people.get(ref)
        if body is None or body.is_pc or getattr(body, "at", None) == at:
            continue
        seen = rec.get("last_seen")
        if seen is None:
            continue
        gone.append({"ref": ref, "name": body.name,
                     "hours_ago": max(0, (now - int(seen)) // 60), "here": False,
                     "size": str(getattr(body, "size", "medium") or "medium").lower()})
    # A caravan that left from this ground (rules/jobs.py): its wagons' trail, held by the
    # job's own record of when it went, so "track the caravan" finds a thing that is real.
    from . import jobs as jobs_mod

    seen = present | {t["ref"] for t in gone}
    gone += [t for t in jobs_mod.trails_of(scene) if t["ref"] not in seen]
    gone.sort(key=lambda t: t["hours_ago"])
    return out + gone


def quarry_of(scene, phrase: str, world=None) -> dict | None:
    """{ref, name} of the one person the engine holds that `phrase` means, or None — the
    people finder's own answer (`population.find`), never a guess: an ambiguous phrase is
    nobody in particular, and a phrase that fits nobody the campaign has seen is nothing
    the engine holds (the caravan the narrator invented)."""
    from . import population

    phrase = " ".join(str(phrase or "").split())
    if not phrase or scene is None:
        return None
    # A caravan a job holds (rules/jobs.py) is several real people; the phrase that names
    # the group ("the caravan", "the wagons to Dustgate") means its master's trail, which
    # is the wagons'. Asked first: the finder would call four people ambiguous.
    from . import jobs as jobs_mod

    group = jobs_mod.group_named(scene, phrase)
    if group is not None and group["ref"] in (getattr(scene, "people", {}) or {}):
        return group
    try:
        found = population.find(scene, phrase, log_miss=False, world=world)
    except Exception:  # noqa: BLE001 — a phrase the finder cannot read is nobody it holds
        return None
    if found.scope not in (population.HERE, population.ELSEWHERE) or len(found.people) != 1:
        # A person the scene holds by their whole name, wherever they stand — a scheme's
        # cast never passes through the prose finder's rings. Measured on the owner's
        # 0.2.25 save: "Search the marsh and the edge for Kwolla Ashbourne" tracked with
        # `held: null` and told "nothing that has passed here is Kwolla Ashbourne" of a
        # woman the engine held at the marsh (`scope.held_by_whole_name`).
        from . import scope

        ref = scope.held_by_whole_name(scene, phrase)
        body = (getattr(scene, "people", {}) or {}).get(ref) if ref else None
        return {"ref": ref, "name": body.name} if body is not None else None
    ref = str(found.people[0].get("ref") or "")
    body = (getattr(scene, "people", {}) or {}).get(ref)
    if not ref or body is None or body.is_pc:
        return None
    return {"ref": ref, "name": body.name}


def same_ground(a: str, b: str) -> bool:
    """Whether two place ids are of one settlement's ground (the id's head, before `~`):
    a walk, not a journey."""
    return bool(a and b) and str(a).split("~", 1)[0] == str(b).split("~", 1)[0]


def after(scene, *, quarry: str, quarry_held: dict | None, found: list[dict],
          every: list[dict], follow: bool, beat_ground: bool,
          place_name) -> tuple[str, str]:
    """(what the tell adds about the quarry and the following, the place id the party
    walks to — "" for none). `found` is the trails the roll read, `every` every trail the
    engine knows on this ground; `beat_ground` whether the roll beat the ground itself;
    `place_name(id)` names a place.

    Said plainly, every branch, because the tell is the whole of what the page may say was
    found (law 3): a quarry nothing holds has no trail; a quarry held whose trail is not
    here has none here; one whose trail the roll did not read is not read; and a trail
    followed goes where its maker is now, or says why it does not."""
    words = quarry or ""
    if words and quarry_held is None:
        return (f"No trail of {words} crosses this ground: nothing that has passed here is "
                f"{words}, and there is no trail of {words} to follow.", "")
    target = None
    if quarry_held is not None:
        ref = quarry_held["ref"]
        target = next((t for t in found if t["ref"] == ref), None)
        if target is None:
            known_here = any(t["ref"] == ref for t in every)
            if not known_here:
                return (f"No trail of {quarry_held['name']} crosses this ground.", "")
            return (f"{quarry_held['name']}'s trail is not to be read from it."
                    + (" There is nothing to follow." if follow else ""), "")
    elif follow:
        away = [t for t in found if not t["here"]]
        target = away[0] if away else None
        if target is None:
            return ((" There is no trail here to follow." if beat_ground else
                     " No trail could be read to follow.").strip(), "")
    if target is None:
        return "", ""
    name = target["name"]
    if target["here"]:
        return f"{name}'s trail ends here, where {name} stands.", ""
    if not follow:
        return "", ""
    body = (getattr(scene, "people", {}) or {}).get(target["ref"])
    there = str(getattr(body, "at", "") or "")
    here = str(getattr(scene, "at", "") or "")
    if not there or there == here:
        return f"{name}'s trail turns back on itself and leads nowhere further.", ""
    if not same_ground(there, here):
        return (f"{name}'s trail leads off this ground toward another settlement: a "
                f"journey, not a walk, and it is not followed now.", "")
    return f"{name}'s trail is followed toward {place_name(there)}.", there


def dc_of(base: int, trail: dict, light: str) -> int:
    """The book's DC for one trail: the ground, the size, the days, the light."""
    return (base + SIZE_DC.get(trail.get("size", "medium"), 0)
            + int(trail.get("hours_ago", 0)) // 24 + LIGHT_DC.get(light, 0))


def said(name: str, total: int, base_dc: int, surface: str, found: list[dict],
         light: str) -> str:
    """The tell: the roll against the ground, and what was found — or that nothing was."""
    dark = " in the poor light" if light in LIGHT_DC else ""
    head = (f"{name} reads the {surface} ground for tracks{dark}: Survival {total} "
            f"against DC {base_dc + LIGHT_DC.get(light, 0)}.")
    if total < base_dc + LIGHT_DC.get(light, 0) and not found:
        return (f"{head} No sign {name} can trust; whether anything passed this way is not "
                f"to be read from it.")
    if not found:
        return (f"{head} There are no tracks here but the party's own: nobody has crossed "
                f"this ground lately.")
    bits = []
    for t in found:
        if t["here"]:
            bits.append(f"{t['name']}'s, leading to where they stand")
        elif t["hours_ago"] < 1:
            bits.append(f"{t['name']}'s, fresh, leading away")
        else:
            bits.append(f"{t['name']}'s, {sky.span_words(t['hours_ago'] * 60)} old, "
                        f"leading away")
    # "Nothing else" only when the roll beat the ground itself: a large beast's deep prints
    # can be read by a roll that would miss a man's, and that roll says nothing of men.
    rest = (" Nothing else has left a mark." if total >= base_dc + LIGHT_DC.get(light, 0)
            else " Nothing fainter can be read.")
    return f"{head} Tracks: " + "; ".join(bits) + "." + rest

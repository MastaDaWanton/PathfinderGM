"""Export the mocks' data from COPIES of the owner's saves (never the saves themselves).

    python docs/mock/place-map-v2/export.py <dir holding copies of jack.json and frag.json>

Writes data/town.json (Featherperch's `places_found.chart()` plus each place's exits row),
data/region.json (the settlements and wild places with their journey days, fogged by
`scene.been`) and data/site.json (frag's founded dungeon rooms). Mock tooling only.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pathfindergm.settings")
OUT = Path(__file__).resolve().parent / "data"


def main(saves: Path):
    import django
    django.setup()
    os.chdir(ROOT)  # world_source is relative to the repo
    from play.campaign import Campaign
    from play import places_found, exits as exits_mod
    from rules import journey, places as places_mod

    # --- Town: stand the copy of jack in Featherperch's inn, his `been` left as it is.
    c = Campaign.load(saves / "jack.json")
    world = c.world
    fp = world.by_name("Featherperch")
    sc = c.scene
    sc.location_id = fp.id
    sc.at = f"{fp.id}~urban:the-inn"
    eng = c.engine()
    chart = places_found.chart(eng, world)
    known = {p.id: p for p in eng.places()}
    chart["clock_minutes"] = sc.clock_minutes
    chart["settings"] = {pid: places_mod.setting_of(pid) for pid in known}
    # Each found place's full exits row, so the mocks can say where roads go.
    # MOCK ONLY: every place's exits row and name, so the page can replay the fog rule
    # client-side as you walk (the game asks the engine each state instead), and check
    # its replay against chart() on the first state.
    ids = sorted(known)
    chart["ids"] = ids
    chart["names"] = {pid: known[pid].name for pid in ids}
    chart["ways"] = exits_mod.ways_from(eng, world, ids)
    chart["been"] = [pid for pid in sc.places_been() if pid in known]
    (OUT / "town.json").write_text(json.dumps(chart, indent=1), encoding="utf-8")

    # --- Region: Featherperch, the towns one journey away and theirs, wild places by town.
    been_towns = {pid.split("~")[0] for pid in sc.places_been()}
    towns, roads, frontier = {}, [], [fp.id]
    for depth in range(2):
        nxt = []
        for tid in frontier:
            for leg in journey.legs_from(world, tid):
                key = tuple(sorted((tid, leg.to_id)))
                if key not in {tuple(sorted((r["a"], r["b"]))) for r in roads}:
                    roads.append({"a": tid, "b": leg.to_id, "days": leg.days_apart,
                                  "miles": leg.miles, "road": leg.road,
                                  "sea": bool(leg.by_sea), "by": str(getattr(leg, "by", "") or "")})
                if leg.to_id not in towns:
                    nxt.append(leg.to_id)
            towns.setdefault(tid, None)
        frontier = nxt
    for tid in frontier:
        towns.setdefault(tid, None)
    region = {"here": fp.id, "towns": [], "roads": roads, "wild": []}
    for tid in towns:
        loc = world.get(tid)
        region["towns"].append({
            "id": tid, "name": getattr(loc, "name", tid),
            "kind": getattr(loc, "kind", ""), "region": [a.name for a in world.ancestors(tid)][:2],
            "visited": tid in been_towns, "current": tid == fp.id})
    for pid in sc.places_been():
        tid, _, rest = pid.partition("~")
        if rest.startswith("urban:"):
            continue
        region["wild"].append({"id": pid, "town": tid, "setting": rest.split(":")[0],
                               "name": rest.split(":", 1)[1].lstrip("@").split("/")[-1]
                               .replace("-", " ")})
    (OUT / "region.json").write_text(json.dumps(region, indent=1), encoding="utf-8")

    # --- Site: frag's founded dungeon.
    frag = json.loads((saves / "frag.json").read_text(encoding="utf-8"))
    fs = frag["scene"]
    site = {"founded": fs.get("founded"), "at": fs.get("at"), "been": fs.get("been")}
    (OUT / "site.json").write_text(json.dumps(site, indent=1), encoding="utf-8")
    print("town", chart["found"], "found /", chart["visited"], "visited; region",
          len(region["towns"]), "towns; site keys", list((fs.get("founded") or {}))[:5])


if __name__ == "__main__":
    main(Path(sys.argv[1]))

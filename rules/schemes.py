"""Quest schemes: authored, world-agnostic stories the world does to the player.

docs/quest-schemes-plan.md §6 is the design of record. In one paragraph: a scheme is a
document — slots with no names, a visible quest card and a secret card with `$slot`
placeholders, storylet *steps* whose criteria are all things the engine measures, and
named *outcomes* that are effects. At open the slots are filled once from the world's
own cast, places and goods and frozen on the instance; every tick the steps whose
criteria hold are candidates and the one with the most criteria fires (Valve's rule
database, Ruskin GDC 2012); a step the player could witness comes back as an outcome
with a tell, a step they could not is silent — log and secret card only, because a
narrator that told the player what happened across town would be handing them
knowledge their character cannot hold. News is how the world reaches them afterwards,
by a carrier their character would meet. Nothing here is prose the model wrote;
nothing here is a number the author typed.

The three laws: every criterion is a `has_state` question or a place, clock or event
test; every grant travels as an `ActiveEffect` with source `scheme:<id>/<step|outcome>`;
every fired step is an `Outcome` with that provenance on the turn log.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from django.conf import settings

from . import cards as cards_mod
from . import places as places_mod
from .activeeffect import ActiveEffect

# --- the vocabulary -------------------------------------------------------------------------

ACTIONS = ("move", "hide", "kill", "bring_in", "open_card", "fact", "objective",
           "reveal_objective", "resolve", "grant", "news", "outcome")
CARRIERS = ("letter", "courier", "crier", "notice", "gossip", "kin", "invitation")
REACHES = ("kin", "town", "region")
PLACE_KINDS = {
    # slot kind -> the place names the settlement set uses, in order of preference
    "market": ("the market",), "lodging": ("the tavern", "the inn"),
    "gate": ("the gate",), "temple": ("the temple",), "guildhall": ("the guildhall",),
    "road": ("the gate",), "wild": (),
}
# The criteria grammar. Each is a regex over one criterion string; the validator refuses
# anything that matches none, naming these shapes.
_CRITERIA = {
    "at": re.compile(r"^(not\s+)?at\(\$(\w+)\)$"),
    "left": re.compile(r"^left\(\$(\w+)\)$"),
    "arrived": re.compile(r"^arrived\(\$(\w+)\)$"),
    "has": re.compile(r"^(not\s+)?has\((pc|\$\w+),\s*([a-z0-9.\-_]+)\)$"),
    "since": re.compile(r"^since\((open|campaign|[\w-]+)\)\s*>=\s*(\d+)h$"),
    "clock": re.compile(r"^clock\s*>=\s*(\d+)$"),
    "event": re.compile(r"^event:(\w+)(?:\(\$(\w+)\))?$"),
    "alive": re.compile(r"^(not\s+)?alive\(\$(\w+)\)$"),
    "present": re.compile(r"^(not\s+)?present\(\$(\w+)\)$"),
    "holds": re.compile(r"^(not\s+)?holds\(pc,\s*\$(\w+)\)$"),
}
SHAPES = ("at($place)", "left($place)", "arrived($place)", "has(pc, tag)",
          "has($slot, tag)", "since(open) >= 2h", "clock >= 600", "event:give($slot)",
          "alive($slot)", "present($slot)", "holds(pc, $item)")
# Criteria a player can change by acting. `since` and `clock` are not among them.
_PLAYER_CHANGEABLE = ("at", "left", "arrived", "has", "event", "alive", "present", "holds")
_DIGIT = re.compile(r"\d")
_SLOT = re.compile(r"\$(\w+)")

# Whether shipped schemes open on their own. The test suite turns this off in
# `conftest.py` the way it turns the written opening off: "The lost thing" opens in
# any settlement's market, which is the point of a world-agnostic scheme and the wrong
# thing to happen inside a test about temporary hit points.
ENABLED = True


# --- loading ---------------------------------------------------------------------------------

def _content_dir() -> Path:
    return Path(settings.BASE_DIR) / "content" / "schemes"


def homebrew_dir(make: bool = False) -> Path:
    p = Path(settings.CAMPAIGN_DIR).parent / "homebrew" / "schemes"
    if make:
        p.mkdir(parents=True, exist_ok=True)
    return p


def _read_folder(folder: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not folder.exists():
        return out
    for path in sorted(folder.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        entries = data.get("schemes") if "schemes" in data else ([data] if data.get("id") else [])
        for e in entries or []:
            if isinstance(e, dict) and e.get("id"):
                out[str(e["id"])] = e
    return out


def shipped() -> dict[str, dict]:
    return _read_folder(_content_dir())


def authored() -> dict[str, dict]:
    return _read_folder(homebrew_dir())


def all_schemes() -> dict[str, dict]:
    out = shipped()
    out.update(authored())
    return out


# --- validation, with the fix named ----------------------------------------------------------

def _criterion_kind(text: str) -> tuple[str, re.Match] | None:
    text = " ".join(str(text or "").split())
    for kind, rx in _CRITERIA.items():
        m = rx.match(text)
        if m:
            return kind, m
    return None


def _slots_named(text: str) -> set[str]:
    return set(_SLOT.findall(str(text or "")))


def validate(doc: dict) -> list[str]:
    """Every problem at once, each saying what to type."""
    problems: list[str] = []
    if not isinstance(doc, dict):
        return ["a scheme is an object"]
    sid = str(doc.get("id") or "")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", sid):
        problems.append("id: lower case and hyphens — 'the-lost-thing'.")
    slots = doc.get("slots") or {}
    if not isinstance(slots, dict) or not slots:
        problems.append("slots: a scheme names its people, places and things as slots.")
        slots = {}
    for name, spec in slots.items():
        if not isinstance(spec, dict) or not any(k in spec for k in ("role", "place", "item", "faction")):
            problems.append(f"slots.{name}: say what fills it — role, place, item or faction.")
        if isinstance(spec, dict) and spec.get("place") and spec["place"] not in PLACE_KINDS:
            problems.append(f"slots.{name}: a place kind is one of {', '.join(PLACE_KINDS)}.")

    def check_slots(text, at):
        for s in _slots_named(text):
            if s not in slots:
                problems.append(f"{at}: ${s} is not a slot of this scheme; declare it under slots.")

    def check_digits(text, at):
        if _DIGIT.search(str(text or "")):
            problems.append(f"{at}: {str(text)!r} carries a number — say it in words; the engine "
                            f"prices rewards and never lets a model author a number.")

    for i, card in enumerate(doc.get("cards") or []):
        at = f"cards[{i + 1}]"
        if not isinstance(card, dict) or not card.get("key") or not card.get("title"):
            problems.append(f"{at}: a card has a key and a title.")
            continue
        for field in ("title", "reward"):
            check_slots(card.get(field, ""), f"{at}.{field}")
            check_digits(card.get(field, ""), f"{at}.{field}")
        for f in card.get("facts") or []:
            check_slots(f, f"{at}.facts")
            check_digits(f, f"{at}.facts")
        for o in card.get("objectives") or []:
            check_slots(o, f"{at}.objectives")
            check_digits(o, f"{at}.objectives")
    keys = {c.get("key") for c in doc.get("cards") or [] if isinstance(c, dict)}
    for c in doc.get("opens") or []:
        if _criterion_kind(c) is None:
            problems.append(f"opens: {c!r} is not a criterion; the shapes are {', '.join(SHAPES)}.")
        check_slots(c, "opens")
    steps = doc.get("steps") or []
    if not steps:
        problems.append("steps: a scheme does something; write at least one step.")
    ids = set()
    for i, st in enumerate(steps):
        at = f"steps[{i + 1}]" + (f" ({st.get('id')})" if isinstance(st, dict) and st.get("id") else "")
        if not isinstance(st, dict) or not st.get("id"):
            problems.append(f"{at}: a step has an id.")
            continue
        if st["id"] in ids:
            problems.append(f"{at}: the id {st['id']!r} is used twice.")
        ids.add(st["id"])
        crits = st.get("criteria") or []
        if not crits:
            problems.append(f"{at}: a step needs criteria; it cannot fire on nothing.")
        changeable = False
        for c in crits:
            found = _criterion_kind(c)
            if found is None:
                problems.append(f"{at}: {c!r} is not a criterion; the shapes are {', '.join(SHAPES)}.")
                continue
            if found[0] in _PLAYER_CHANGEABLE:
                changeable = True
            check_slots(c, at)
        if crits and not changeable:
            problems.append(f"{at}: no criterion here is one the player could change — a step "
                            f"that fires on the clock alone is a cutscene; add at($place), "
                            f"has(pc, tag), present($slot) or an event.")
        for act in [st.get("action")] + list(st.get("also") or []):
            if not isinstance(act, dict) or act.get("do") not in ACTIONS:
                problems.append(f"{at}: action {act!r} — the vocabulary is {', '.join(ACTIONS)}.")
                continue
            if act["do"] in ("fact", "objective", "reveal_objective", "resolve", "open_card") \
                    and act.get("card") not in keys:
                problems.append(f"{at}: action names card {act.get('card')!r}, which is not "
                                f"one of this scheme's cards ({', '.join(sorted(k for k in keys if k))}).")
            if act["do"] == "news":
                if act.get("carrier") not in CARRIERS:
                    problems.append(f"{at}: news carrier is one of {', '.join(CARRIERS)}.")
                if act.get("reach") not in REACHES:
                    problems.append(f"{at}: news reach is one of {', '.join(REACHES)}.")
                check_digits(act.get("says", ""), f"{at}.news")
            if act["do"] == "outcome" and act.get("name") not in (doc.get("outcomes") or {}):
                problems.append(f"{at}: outcome {act.get('name')!r} is not declared under outcomes.")
            for k in ("who", "to", "text", "says"):
                check_slots(act.get(k, ""), at)
            check_digits(act.get("text", ""), at)
        tell = st.get("tell") or {}
        if not isinstance(tell, dict) or not any(k in tell for k in ("perceptible", "silent", "deferred", "teller")):
            problems.append(f"{at}: tell — say whether it is perceptible, silent, deferred or "
                            f"has a teller, and what it says.")
        else:
            for k, v in tell.items():
                check_slots(v, f"{at}.tell")
                check_digits(v, f"{at}.tell")
        # A twist: a step that grants the player knowledge about a person (knows.*) after
        # the open, or moves an outcome — must name its foreshadowing.
        grants = [a for a in [st.get("action")] + list(st.get("also") or [])
                  if isinstance(a, dict) and a.get("do") == "grant"]
        twisty = any("knows." in " ".join(a.get("tags") or []) for a in grants) and \
            any("kin" in t or "lie" in t or "never" in t
                for t in [str(st.get("tell", {}).get("perceptible", ""))])
        if (st.get("fairness") is not None or twisty) and not st.get("fairness"):
            problems.append(f"{at}: a twist needs foreshadowing — list under fairness the "
                            f"knows.* tags the brief must already have carried.")
    for name, out in (doc.get("outcomes") or {}).items():
        if not isinstance(out, dict):
            problems.append(f"outcomes.{name}: an outcome is an object.")
            continue
        if out.get("resolve") and out["resolve"] not in keys:
            problems.append(f"outcomes.{name}: resolves card {out['resolve']!r}, which is not one of "
                            f"this scheme's cards.")
        for g in out.get("grants") or []:
            check_slots(g.get("to", ""), f"outcomes.{name}")
            for tag in g.get("tags") or []:
                if not re.fullmatch(r"[a-z][a-z0-9.\-_]*", str(tag)):
                    problems.append(f"outcomes.{name}: {tag!r} is not a tag.")
    return problems


# --- slot filling -----------------------------------------------------------------------------

_ROLE_WORDS = {
    "trader": ("trader", "merchant", "shopkeeper", "stallholder", "dealer", "seller"),
    "fixer": ("fixer", "broker", "factor", "agent"),
    "kin": ("kin", "sibling", "cousin", "son", "daughter", "brother", "sister"),
    "guard officer": ("captain", "sergeant", "guard", "watch"),
    "standing": ("elder", "noble", "councillor", "master", "chief", "lord", "lady", "priest"),
    "companion": ("companion",),
}


def _place_for(engine, kind: str, spec: dict) -> dict | None:
    scene = engine.scene
    known = engine.places()
    if kind == "wild":
        found = engine.world.get(scene.location_id) if engine.world else None
        terrain = engine._terrain_hint(found) or "grassland"
        region = places_mod.region_set(scene.location_id, terrain)
        p = region[0]
        return {"kind": "place", "id": p.id, "name": p.name, "terrain": p.terrain,
                "region": True, "hours": int(spec.get("hours", 2) or 2)}
    for name in PLACE_KINDS.get(kind, ()):
        p = places_mod.find(known, name)
        if p is not None:
            return {"kind": "place", "id": p.id, "name": p.name, "terrain": p.terrain}
    # Nothing by that name: the first place that is not where the party stands.
    for p in known:
        if p.id != scene.at:
            return {"kind": "place", "id": p.id, "name": p.name, "terrain": p.terrain}
    return None


def _cast_candidates(engine) -> list[dict]:
    """The world's own people at this location, from play.cast, not yet on the board."""
    world = engine.world
    if world is None:
        return []
    play = getattr(world, "play", None) or {}
    here = str(engine.scene.location_id)
    on_board = {str(a.world_entity_id) for a in engine.scene.people.values() if a.world_entity_id}
    out = []
    for c in play.get("cast") or []:
        if not isinstance(c, dict) or str(c.get("id")) in on_board:
            continue
        if str(c.get("home_id") or "") == here:
            out.append(c)
    return out


def _role_for(engine, name: str, spec: dict, filled: dict, taken: set) -> dict | None:
    """A person for the role: a cast member of this place when there is one (grounded,
    their own name), else the townsfolk floor with a name from the world's naming
    (phase 3 brings the codex chooser). Placed where the slot says."""
    from .bestiary import instantiate

    scene = engine.scene
    words = _ROLE_WORDS.get(str(spec.get("role") or ""), (str(spec.get("role") or ""),))
    cast = [c for c in _cast_candidates(engine) if c.get("id") not in taken]
    pick = next((c for c in cast if any(w in str(c.get("role", "")).lower() for w in words)), None)
    if pick is None and cast:
        # Deterministic: the cast in its own order, so the same world fills the same slot.
        pick = cast[len(taken) % len(cast)]
    template = "guildhand" if spec.get("role") != "guard officer" else "watchman"
    if pick is not None:
        actor = instantiate(template, scene=scene, name=str(pick["name"]),
                            world_entity_id=str(pick["id"]))
        taken.add(str(pick["id"]))
    else:
        actor = instantiate(template, scene=scene)
    scene.add(actor)
    where = spec.get("at")
    if where and where.startswith("$") and where[1:] in filled and filled[where[1:]].get("id"):
        scene.move(actor.ref, filled[where[1:]]["id"])
    return {"kind": "actor", "ref": actor.ref, "name": actor.name,
            "entity": actor.world_entity_id or ""}


def _item_for(engine, spec: dict, filled: dict) -> dict | None:
    from . import ingredients

    biome = "grassland"
    ref = str(spec.get("biome") or "")
    if ref.startswith("$") and ref[1:] in filled:
        biome = str(filled[ref[1:]].get("terrain") or biome)
    pool = [i for i in ingredients.all_ingredients().values() if biome in (i.biomes or [])]
    pool = pool or list(ingredients.all_ingredients().values())
    if not pool:
        return None
    pick = sorted(pool, key=lambda i: i.name)[hash(engine.scene.location_id) % len(pool)]
    return {"kind": "item", "id": pick.id, "name": pick.name, "biome": biome}


def fill_slots(engine, doc: dict) -> dict:
    """Places first (people are put in them), then items (by the wild place's ground),
    then people. Frozen on the instance."""
    filled: dict = {}
    slots = doc.get("slots") or {}
    for name, spec in slots.items():
        if spec.get("place"):
            got = _place_for(engine, spec["place"], spec)
            if got:
                filled[name] = got
    for name, spec in slots.items():
        if spec.get("item"):
            got = _item_for(engine, spec, filled)
            if got:
                filled[name] = got
    taken: set = set()
    for name, spec in slots.items():
        if spec.get("role"):
            got = _role_for(engine, name, spec, filled, taken)
            if got:
                filled[name] = got
    for name, spec in slots.items():
        if spec.get("faction"):
            world = engine.world
            conflicts = ((getattr(world, "play", None) or {}).get("conflicts") or []) if world else []
            if conflicts:
                c = conflicts[0]
                filled[name] = {"kind": "faction", "name": str(c.get("faction") or "a faction"),
                                "wants": str(c.get("wants") or ""), "works_by": str(c.get("works_by") or ""),
                                "holds": str(c.get("holds") or ""), "undone_by": str(c.get("undone_by") or "")}
    return filled


def fill_text(text: str, filled: dict) -> str:
    def sub(m):
        s = filled.get(m.group(1))
        return str(s.get("name") or "") if s else m.group(0)
    return _SLOT.sub(sub, str(text or ""))


# --- instances ---------------------------------------------------------------------------------

def _instances(scene) -> list[dict]:
    return scene.schemes


def _find(scene, sid: str) -> dict | None:
    return next((i for i in scene.schemes if i.get("scheme") == sid), None)


def open_scheme(engine, doc: dict, turn: int = 0) -> dict:
    scene = engine.scene
    filled = fill_slots(engine, doc)
    inst = {"scheme": doc["id"], "opened_at": int(scene.clock_minutes),
            "opened_turn": int(turn), "slots": filled, "fired": {}, "skipped": [],
            "cards": {}, "outcome": "", "news": [], "visited": [], "last_at": scene.at}
    pc = scene.pc()
    for card in doc.get("cards") or []:
        if card.get("kind") == "quest":
            giver = filled.get(str(card.get("giver", "")).lstrip("$"), {}).get("ref", "")
            made = cards_mod.open_quest(
                scene, title=fill_text(card["title"], filled),
                objectives=[fill_text(o, filled) for o in card.get("objectives") or []],
                giver=giver, reward=fill_text(card.get("reward", ""), filled),
                facts=[fill_text(f, filled) for f in card.get("facts") or []],
                people=[giver] if giver else [], place=str(scene.at or ""),
                origin=f"scheme:{doc['id']}", turn=turn)
        else:
            n = sum(1 for c in cards_mod.load(scene) if c.id.startswith(f"scheme-{doc['id']}")) + 1
            made = cards_mod.open_card(scene, cards_mod.Card(
                id=f"scheme-{doc['id']}-{card['key']}-{n}", title=fill_text(card["title"], filled),
                facts=[fill_text(f, filled) for f in card.get("facts") or []],
                tags=(cards_mod.TAG_PLAY, "situation.scheme"),
                people=[s["ref"] for s in filled.values() if s.get("kind") == "actor"],
                place=str(scene.at or ""), origin=f"scheme:{doc['id']}",
                secret=bool(card.get("secret")), always_on=True), turn=turn)
        inst["cards"][card["key"]] = made.id
    for g in doc.get("grants_on_open") or []:
        _grant(scene, filled, g, f"scheme:{doc['id']}/open")
    scene.schemes.append(inst)
    return inst


def _who(scene, filled: dict, ref: str):
    if ref == "pc":
        return scene.pc()
    name = str(ref).lstrip("$")
    slot = filled.get(name) or {}
    return scene.people.get(slot.get("ref", "")) if slot.get("kind") == "actor" else None


def _grant(scene, filled: dict, g: dict, source: str) -> None:
    who = _who(scene, filled, str(g.get("to", "pc")))
    if who is None:
        return
    tags = tuple(str(t) for t in g.get("tags") or ())
    if not tags:
        return
    key = f"{source}:{'+'.join(tags)}"
    if any(e.key == key for e in who.effects):
        return
    who.apply_effect(ActiveEffect(name=tags[0].split(".")[-1].replace("-", " "),
                                  kind="situation", key=key, source=source, origin=source,
                                  duration="until-dismissed", tags=tags))


# --- criteria ----------------------------------------------------------------------------------

def _at(scene, slot: dict) -> bool:
    if not slot or slot.get("kind") != "place":
        return False
    if scene.at == slot["id"]:
        return True
    if slot.get("region"):
        return places_mod.terrain_of(scene.at) == slot.get("terrain") and \
            places_mod.terrain_of(scene.at) != places_mod.URBAN
    return False


def _holds(pc, slot: dict) -> bool:
    if pc is None or not slot:
        return False
    want = str(slot.get("name") or "").lower()
    return any(str(s.base).lower() == want and s.count > 0 for s in pc.stock.values()) \
        or str(slot.get("id") or "") in (pc.materials if hasattr(pc, "materials") else {})


def _criterion_holds(engine, inst: dict, doc: dict, text: str, events: list[dict]) -> bool:
    scene = engine.scene
    pc = scene.pc()
    filled = inst["slots"]
    found = _criterion_kind(text)
    if found is None:
        return False
    kind, m = found
    if kind == "at":
        neg, name = m.group(1), m.group(2)
        v = _at(scene, filled.get(name, {}))
        return (not v) if neg else v
    if kind == "left":
        return m.group(1) in inst.get("visited", []) and not _at(scene, filled.get(m.group(1), {}))
    if kind == "arrived":
        return any(e.get("event") == "travel" for e in events) and _at(scene, filled.get(m.group(1), {}))
    if kind == "has":
        neg, who, tag = m.group(1), m.group(2), m.group(3)
        actor = _who(scene, filled, who)
        v = bool(actor is not None and actor.has_state(tag))
        return (not v) if neg else v
    if kind == "since":
        anchor, hours = m.group(1), int(m.group(2))
        if anchor == "open":
            start = inst["opened_at"]
        elif anchor == "campaign":
            start = 0
        else:
            start = (inst["fired"].get(anchor) or {}).get("clock")
            if start is None:
                return False
        return scene.clock_minutes - start >= hours * 60
    if kind == "clock":
        return scene.clock_minutes >= int(m.group(1))
    if kind == "event":
        name, slot = m.group(1), m.group(2)
        for e in events:
            if e.get("event") != name:
                continue
            if slot:
                s = filled.get(slot) or {}
                if s.get("kind") == "actor" and e.get("to") == s.get("ref"):
                    return True
                if s.get("kind") == "item" and str(e.get("item", "")).lower() == str(s.get("name", "")).lower():
                    return True
                continue
            return True
        return False
    if kind in ("alive", "present"):
        neg, name = m.group(1), m.group(2)
        actor = _who(scene, filled, name)
        if kind == "alive":
            v = actor is not None and not actor.has_state("state.down.dead")
        else:
            v = actor is not None and actor.at == scene.at and not actor.has_state("state.hidden")
        return (not v) if neg else v
    if kind == "holds":
        neg, name = m.group(1), m.group(2)
        v = _holds(pc, filled.get(name, {}))
        return (not v) if neg else v
    return False


def _events_from(outcomes) -> list[dict]:
    """What happened this tick, in the engine's own words: op names and their people."""
    out = []
    for o in outcomes or []:
        op = str(getattr(o, "op", ""))
        for eff in getattr(o, "effects", None) or []:
            if not isinstance(eff, dict):
                continue
            if op == "travel" or eff.get("kind") == "travel":
                out.append({"event": "travel"})
            if op == "give" and eff.get("kind") in ("give", "took", "gave", "given", "handed", "bought"):
                # The give op's effect names the taker as `ref` and the thing as `item`.
                out.append({"event": "give", "to": eff.get("to") or eff.get("ref"), "item": eff.get("item")})
            if op == "quest_step":
                out.append({"event": "objective_done", "card": eff.get("id"), "n": eff.get("objective")})
            if op == "quest":
                out.append({"event": "quest_taken"})
            if op == "end_encounter":
                out.append({"event": "fight_ended"})
        if op == "travel" and not any(e.get("event") == "travel" for e in out):
            out.append({"event": "travel"})
    return out


# --- actions -----------------------------------------------------------------------------------

def _card(scene, inst: dict, key: str):
    cid = inst["cards"].get(key)
    return cards_mod.find(scene, cid) if cid else None


def _do(engine, inst: dict, doc: dict, act: dict, step_id: str, turn: int) -> None:
    scene = engine.scene
    filled = inst["slots"]
    source = f"scheme:{doc['id']}/{step_id}"
    what = act.get("do")
    if what == "move":
        who = _who(scene, filled, act.get("who", ""))
        to = filled.get(str(act.get("to", "")).lstrip("$")) or {}
        if who is not None and to.get("id"):
            scene.move(who.ref, to["id"])
    elif what == "hide":
        who = _who(scene, filled, act.get("who", ""))
        if who is not None:
            who.apply_effect(ActiveEffect(name="hidden", kind="situation", key=f"{source}:hidden",
                                          source=source, origin=source,
                                          duration="until-dismissed", tags=("state.hidden",)))
    elif what == "kill":
        who = _who(scene, filled, act.get("who", ""))
        if who is not None and not who.is_pc:
            who.hp = -abs(who.ability_score("con")) - 1
            who.apply_hp_state()
    elif what == "bring_in":
        role = str(act.get("role") or "watchman")
        template = "watchman" if "guard" in role or "watch" in role else "thug" if "thug" in role else "guildhand"
        born = engine._bring_in(template, count=int(act.get("count", 1) or 1), side=str(act.get("side") or ""))
        inst.setdefault("brought", []).extend(b["ref"] for b in born)
    elif what == "fact":
        card = _card(scene, inst, act.get("card", ""))
        if card is not None:
            cards_mod.touch(scene, card.id, fill_text(act.get("text", ""), filled), turn=turn, tick=False)
    elif what == "objective":
        card = _card(scene, inst, act.get("card", ""))
        if card is not None:
            cards_mod.objective_done(scene, card.id, int(act.get("n", 1)) - 1, turn=turn)
    elif what == "reveal_objective":
        card = _card(scene, inst, act.get("card", ""))
        if card is not None and card.kind == "quest":
            card.objectives.append({"text": fill_text(act.get("text", ""), filled), "done": False})
            card.clock_max = max(1, len(card.objectives))
            cards_mod._store(scene, card)
    elif what == "resolve":
        card = _card(scene, inst, act.get("card", ""))
        if card is not None:
            cards_mod.resolve(scene, card.id, how=str(act.get("how") or "resolved"), turn=turn)
    elif what == "grant":
        _grant(scene, filled, act, source)
    elif what == "news":
        inst["news"].append({"carrier": act.get("carrier"), "reach": act.get("reach"),
                             "delay": _hours(act.get("delay")), "says": fill_text(act.get("says", ""), filled),
                             "born": int(scene.clock_minutes), "born_turn": engine._scheme_tick,
                             "step": step_id})
    elif what == "outcome":
        _outcome(engine, inst, doc, str(act.get("name") or ""), turn)


def _hours(text) -> int:
    m = re.match(r"^\s*(\d+)\s*([hd])", str(text or "0h"))
    if not m:
        return 0
    n, unit = int(m.group(1)), m.group(2)
    return n * (24 if unit == "d" else 1)


def _outcome(engine, inst: dict, doc: dict, name: str, turn: int) -> str:
    """An ending: its grants through the applicator, its card resolved, its award."""
    scene = engine.scene
    out = (doc.get("outcomes") or {}).get(name)
    if not out or inst.get("outcome"):
        return ""
    inst["outcome"] = name
    source = f"scheme:{doc['id']}/{name}"
    lines = []
    for g in out.get("grants") or []:
        _grant(scene, inst["slots"], g, source)
    if out.get("resolve"):
        card = _card(scene, inst, out["resolve"])
        if card is not None and card.live:
            cards_mod.resolve(scene, card.id, how=str(out.get("how") or "resolved"), turn=turn)
    if out.get("award"):
        card = _card(scene, inst, out.get("resolve", "")) if out.get("resolve") else None
        line = engine.award_story(str(out["award"]), card.title if card else doc.get("title", ""))
        if line:
            lines.append(line.strip())
    inst["award_line"] = " ".join(lines)
    return name


# --- the tick ---------------------------------------------------------------------------------------

def tick(engine, outcomes) -> list:
    """Open what should open, then fire the one most specific step that holds, then
    deliver news that has arrived. Returns the outcomes the prose may see."""
    from .engine import Outcome

    scene = engine.scene
    pc = scene.pc()
    if pc is None:
        return []
    turn = int(getattr(engine, "turn", 0) or 0)
    engine._scheme_tick = int(getattr(engine, "_scheme_tick", 0)) + 1
    fired_now = engine._scheme_tick
    events = _events_from(outcomes)
    made: list = []
    if not ENABLED:
        return made
    docs = all_schemes()

    # Opening: shipped and authored schemes that have never opened in this campaign.
    for sid, doc in docs.items():
        if _find(scene, sid) is not None or validate(doc):
            continue
        probe = {"scheme": sid, "opened_at": 0, "slots": {}, "fired": {}, "visited": [],
                 "news": []}
        # `opens` criteria may name place slots before they are filled: test them on a
        # trial fill of the places only.
        trial = {}
        for name, spec in (doc.get("slots") or {}).items():
            if isinstance(spec, dict) and spec.get("place"):
                got = _place_for(engine, spec["place"], spec)
                if got:
                    trial[name] = got
        probe["slots"] = trial
        if all(_criterion_holds(engine, probe, doc, c, events) for c in doc.get("opens") or []):
            open_scheme(engine, doc, turn=turn)

    # Stepping: one step per instance per tick, the most specific.
    for inst in list(scene.schemes):
        doc = docs.get(inst["scheme"])
        if doc is None or inst.get("outcome"):
            continue
        # Where the player has been, for `left($place)`.
        for name, slot in inst["slots"].items():
            if slot.get("kind") == "place" and _at(scene, slot) and name not in inst["visited"]:
                inst["visited"].append(name)
        best = None
        for st in doc.get("steps") or []:
            if st["id"] in inst["fired"] and st.get("once", True):
                continue
            crits = st.get("criteria") or []
            if not all(_criterion_holds(engine, inst, doc, c, events) for c in crits):
                continue
            needs = [t for t in st.get("fairness") or [] if not pc.has_state(t)]
            if needs:
                inst.setdefault("skipped", []).append(
                    {"step": st["id"], "clock": scene.clock_minutes,
                     "why": "foreshadowing not on the brief: " + ", ".join(needs)})
                continue
            if best is None or len(crits) > len(best.get("criteria") or []):
                best = st
        if best is not None:
            tell = best.get("tell") or {}
            silent = "silent" in tell or "deferred" in tell
            for act in [best.get("action")] + list(best.get("also") or []):
                if isinstance(act, dict):
                    _do(engine, inst, doc, act, best["id"], turn)
            said = fill_text(tell.get("perceptible") or tell.get("silent") or tell.get("deferred") or tell.get("teller") or "", inst["slots"])
            inst["fired"][best["id"]] = {"clock": int(scene.clock_minutes), "turn": turn,
                                         "silent": silent, "tell": said}
            # The secret card carries what happened, seen or not.
            for key, cid in inst["cards"].items():
                card = cards_mod.find(scene, cid)
                if card is not None and card.secret and said:
                    cards_mod.touch(scene, cid, said, turn=turn, tick=False)
            extra = inst.get("award_line", "")
            inst["award_line"] = ""
            if not silent and said:
                made.append(Outcome(
                    intent_id="", op="scheme",
                    effects=[{"kind": "scheme", "scheme": doc["id"], "step": best["id"],
                              "origin": f"scheme:{doc['id']}/{best['id']}"}],
                    tell=said + (f" {extra}" if extra else ""), because="the world moves"))
            elif extra:
                made.append(Outcome(intent_id="", op="scheme",
                                    effects=[{"kind": "scheme", "scheme": doc["id"], "step": best["id"]}],
                                    tell=extra, because="the world moves"))
        # News arrives by a route the character would meet.
        kept = []
        for item in inst.get("news") or []:
            # Never on the tick it was born: word takes at least one beat to travel,
            # and a step and its gossip landing together read as one event.
            if scene.clock_minutes - item["born"] < item["delay"] * 60                     or item.get("born_turn") == fired_now:
                kept.append(item)
                continue
            arrived, how = _news_arrives(engine, inst, item)
            if not arrived:
                kept.append(item)
                continue
            slug = re.sub(r"[^a-z0-9]+", "-", str(item.get("step") or item["says"]).lower()).strip("-")[:32]
            _grant(scene, inst["slots"], {"to": "pc", "tags": [f"knows.news.{slug}"]},
                   f"scheme:{doc['id']}/news")
            made.append(Outcome(intent_id="", op="scheme",
                                effects=[{"kind": "news", "scheme": doc["id"], "carrier": item["carrier"]}],
                                tell=f"{how} {item['says']}", because="news travels"))
        inst["news"] = kept
        inst["last_at"] = scene.at
    return made


def _news_arrives(engine, inst: dict, item: dict) -> tuple[bool, str]:
    scene = engine.scene
    carrier = item.get("carrier")
    urban = places_mod.terrain_of(scene.at) == places_mod.URBAN
    if carrier in ("gossip", "crier", "notice", "kin", "invitation", "courier", "letter"):
        if not urban and carrier != "courier":
            return False, ""
    if carrier == "gossip":
        talker = next((a for a in scene.actors.values() if not a.is_pc), None)
        if talker is None:
            return False, ""
        return True, f"{talker.name} says, as gossip does:"
    if carrier == "crier":
        return True, "A crier calls it in the street:"
    if carrier == "notice":
        return True, "A notice is posted where people pass:"
    if carrier in ("letter", "courier"):
        return True, "A courier finds you with a folded letter:"
    if carrier == "kin":
        return True, "Someone who knew them seeks you out:"
    if carrier == "invitation":
        return True, "An invitation reaches you:"
    return False, ""


# --- helpers for tests and the bench ----------------------------------------------------------------

def hand_item(scene, actor, name: str, count: int = 1) -> None:
    """Put the named thing in a character's hands, the way loot or a gift would."""
    from .crafting import Stock

    actor.add_stock(Stock(base=str(name), tier="common", potency=1.0, craft=""), count)


def gm_view(scene) -> list[dict]:
    """What a scheme did and why — the table's own debugging, never the brief."""
    docs = all_schemes()
    out = []
    for inst in scene.schemes:
        doc = docs.get(inst["scheme"], {})
        out.append({"scheme": inst["scheme"], "title": doc.get("title", inst["scheme"]),
                    "slots": {k: v.get("name") for k, v in inst["slots"].items()},
                    "fired": inst.get("fired", {}), "skipped": inst.get("skipped", []),
                    "outcome": inst.get("outcome", ""), "news": inst.get("news", [])})
    return out

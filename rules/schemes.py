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
from pathfindergm import files

# --- the vocabulary -------------------------------------------------------------------------

ACTIONS = ("move", "hide", "kill", "bring_in", "open_card", "fact", "objective",
           "reveal_objective", "resolve", "grant", "remove", "news", "outcome")
# Slots every scheme has without declaring them: `$town` is the settlement the scheme
# opened in, as `states.town_tag` spells it, so a document can grant
# `state.wanted.$town` without knowing the world (the town leaf is never authored).
IMPLICIT_SLOTS = ("town",)
CARRIERS = ("letter", "courier", "crier", "notice", "gossip", "kin", "invitation")
REACHES = ("kin", "town", "region")
PLACE_KINDS = {
    # slot kind -> the place names the settlement set uses, in order of preference
    # Alternatives, best first, because a settlement is not obliged to have the grandest
    # version of anything. Widened 2026-09-16 after the checker reported 57 of Aurvantis's
    # 64 settlements as having nowhere a quest's `temple` could go — while many of them
    # had a cathedral or a shrine. Somewhere to pray is somewhere to pray, and a table
    # that only knew one word for it was measuring its own narrowness.
    "market": ("the market", "the merchants row"),
    "lodging": ("the tavern", "the inn"),
    "gate": ("the gate",),
    "temple": ("the temple", "the cathedral", "the shrine"),
    "guildhall": ("the guildhall", "the moot hall", "the counting house"),
    # The road is the open ground outside the walls, like the wild: a wanted player
    # who was shown a way past the watch reaches it by biome, never through the arch.
    # The fairness critic measured "fled" unreachable while the road WAS the gate.
    "road": (), "wild": (),
}
# The criteria grammar. Each is a regex over one criterion string; the validator refuses
# anything that matches none, naming these shapes.
_CRITERIA = {
    "at": re.compile(r"^(not\s+)?at\(\$(\w+)\)$"),
    "left": re.compile(r"^left\(\$(\w+)\)$"),
    "arrived": re.compile(r"^arrived\(\$(\w+)\)$"),
    "has": re.compile(r"^(not\s+)?has\((pc|\$\w+),\s*([a-z0-9.\-_$]+)\)$"),
    "since": re.compile(r"^since\((open|campaign|left\(\$\w+\)|[\w-]+)\)\s*>=\s*(\d+)([hd])$"),
    "clock": re.compile(r"^clock\s*>=\s*(\d+)$"),
    # `event:give($giver, $errand)`: the player handed THAT thing to THAT person this batch.
    # The second slot came 2026-11-01, when "Get it back to $sick before the fever turns"
    # ticked on walking into the tavern with the herb in the pack — `holds` and `present`
    # said the herb and the sick woman were in one room, and nothing was ever handed over.
    "event": re.compile(r"^event:(\w+)(?:\(\$(\w+)(?:,\s*\$(\w+))?\))?$"),
    "alive": re.compile(r"^(not\s+)?alive\(\$(\w+)\)$"),
    "present": re.compile(r"^(not\s+)?present\(\$(\w+)\)$"),
    "holds": re.compile(r"^(not\s+)?holds\(pc,\s*\$(\w+)\)$"),
    # `taken(errand)`: the player took on the quest card of that key (`cards.standing` OWN).
    # A card key, not a slot: what is asked is the player's standing to a card the scheme
    # opened. Written for the frame (a-small-favour's `guards-arrive`): measured on the
    # owner's 0.2.25 save, guards came for the stranger "asking after" the victim when
    # the errand had only reached the player through a go-between and was never taken.
    "taken": re.compile(r"^(not\s+)?taken\((\w+)\)$"),
}
SHAPES = ("at($place)", "left($place)", "arrived($place)", "has(pc, tag)",
          "has($slot, tag)", "has(pc, state.wanted.$town)", "since(open) >= 2h",
          "since(open) >= 2d", "since(left($market)) >= 1h", "clock >= 600",
          "event:give($slot)", "event:give($slot, $item)", "event:talk($slot)",
          "alive($slot)", "present($slot)", "holds(pc, $item)", "taken(cardkey)")
# The events `_events_from` reads out of a tick's outcomes. A criterion naming any other
# can never hold: `event:talk` was written into the design (docs/design-d-people.md
# §4.6) before anything emitted it, and the grammar alone would have accepted it and
# left the step dead without a word.
EVENTS = ("travel", "give", "talk", "objective_done", "quest_taken", "fight_ended")
# What a quest card's `hook` block may say (rules/hooks.py `ingredients`): words for the
# narrator, never a number and never a slot the scheme does not declare.
HOOK_FIELDS = ("motive", "doing", "withholds")
# Criteria a player can change by acting. `since` and `clock` are not among them;
# `has`/`holds` only when the subject is the player; `alive`/`present` only beside a
# place or event criterion (a person's state is the world's to change, not the
# player's — the fairness critic validated a step keyed on the victim's life alone).
_PLAYER_CHANGEABLE = ("at", "left", "arrived", "event", "taken")
# What a scheme may put on or take off a person. The most dangerous edit in the
# vocabulary is a `state.down` or `recovery.*` grant — a document could kill the
# player with no hit-point change — so the families are listed, with the fix named.
GRANTABLE = ("knows.", "state.wanted", "state.suspected", "state.hidden", "attitude.",
             "role.", "holds.")

# How many unfinished stories the world will have going at once before it stops
# starting new ones.
#
# There was no cap while two lines shipped, and none was needed: "The lost thing" and
# "A Small Favour" were the whole catalogue. Three more schemes were written on
# 2026-09-13 and the absence became the bug — five of the nine open at a market inside
# the first day, so a player who walked in got a fistful of quest cards at once, and a
# settlement carries about three cast members (Fantasia gives every town exactly three)
# so the fourth and fifth schemes filled their roles with visitors from elsewhere in the
# world. Adding content made the game worse, which is the signature of a missing limit
# rather than of bad content.
#
# Counted over *fresh starts* only. A scheme that opens on `has(pc, knows.…)` is the
# next chapter of something the player is already in — "A Small Favour" is five of them
# — and stopping a line halfway because two other stories are open would be the cap
# doing real damage. Nothing is ever lost to this: `opens` is re-tested every tick, so a
# scheme held back here starts the moment one of the others ends.
MAX_FRESH_OPEN = 2
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
        except Exception as exc:
            files.unreadable(path, exc)
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
        if not isinstance(spec, dict) or not any(k in spec for k in ("role", "place", "item", "faction", "from")):
            problems.append(f"slots.{name}: say what fills it — role, place, item, faction, or "
                            f"from: 'other-scheme.slot' to share another scheme's.")
        if isinstance(spec, dict) and spec.get("place") and spec["place"] not in PLACE_KINDS:
            problems.append(f"slots.{name}: a place kind is one of {', '.join(PLACE_KINDS)}.")
        if isinstance(spec, dict) and spec.get("held_by"):
            holder = slots.get(str(spec["held_by"]).lstrip("$"))
            if not spec.get("item"):
                problems.append(f"slots.{name}: held_by is for an item slot — the person "
                                f"who carries the thing.")
            elif not (isinstance(holder, dict) and (holder.get("role") or holder.get("from"))):
                problems.append(f"slots.{name}: held_by names a person slot of this scheme "
                                f"(a role), e.g. \"held_by\": \"rival\".")

    def check_slots(text, at):
        for s in _slots_named(text):
            if s in IMPLICIT_SLOTS:
                continue
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
        # The hook reaches the narrator word for word (`hooks.render`), so it is held to
        # what a card's title is held to: declared slots, no digits — and only the three
        # fields the pull reads, so a misspelt one is named instead of silently unread.
        hook = card.get("hook")
        if hook is not None:
            if not isinstance(hook, dict):
                problems.append(f"{at}.hook: an object with {', '.join(HOOK_FIELDS)}.")
            else:
                for k, v in hook.items():
                    if k not in HOOK_FIELDS:
                        problems.append(f"{at}.hook.{k}: not read — a hook says "
                                        f"{', '.join(HOOK_FIELDS)}.")
                        continue
                    if not isinstance(v, str) or not v.strip():
                        problems.append(f"{at}.hook.{k}: a sentence in words.")
                        continue
                    check_slots(v, f"{at}.hook.{k}")
                    check_digits(v, f"{at}.hook.{k}")
                if card.get("secret"):
                    problems.append(f"{at}.hook: a secret card is never pulled; the hook "
                                    f"belongs on the card the player can see.")
    keys = {c.get("key") for c in doc.get("cards") or [] if isinstance(c, dict)}
    for c in doc.get("opens") or []:
        found = _criterion_kind(c)
        if found is None:
            problems.append(f"opens: {c!r} is not a criterion; the shapes are {', '.join(SHAPES)}.")
        elif found[0] == "event" and found[1].group(1) not in EVENTS:
            problems.append(f"opens: {c!r} names an event nothing emits; the events are "
                            f"{', '.join(EVENTS)}.")
        check_slots(c, "opens")
    steps = doc.get("steps") or []
    if not steps:
        problems.append("steps: a scheme does something; write at least one step.")
    for i, g in enumerate(doc.get("grants_on_open") or []):
        for tag in (g.get("tags") or []) if isinstance(g, dict) else []:
            if not str(tag).startswith(GRANTABLE):
                problems.append(f"grants_on_open[{i + 1}]: a scheme may grant {', '.join(GRANTABLE)} — not {tag!r}.")
            if str(tag).startswith("knows.") and not str(g.get("say") or "").strip():
                problems.append(f"grants_on_open[{i + 1}]: a knows.* grant needs a `say` — what the "
                                f"player noticed, in a sentence the brief can carry — or the "
                                f"foreshadowing is a tag nobody sees.")
        if isinstance(g, dict):
            check_digits(g.get("say", ""), f"grants_on_open[{i + 1}].say")
            check_slots(g.get("say", ""), f"grants_on_open[{i + 1}].say")
            problems.extend(_charge_problems(g, f"grants_on_open[{i + 1}]"))
    for i, act in enumerate(doc.get("on_open") or []):
        if not isinstance(act, dict) or act.get("do") not in ACTIONS:
            problems.append(f"on_open[{i + 1}]: action {act!r} — the vocabulary is {', '.join(ACTIONS)}.")
        elif act["do"] in ("news", "outcome"):
            problems.append(f"on_open[{i + 1}]: {act['do']} belongs on a step, not on the open.")
        else:
            for k in ("who", "to", "text"):
                check_slots(act.get(k, ""), f"on_open[{i + 1}]")
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
        kinds_here = []
        for c in crits:
            found = _criterion_kind(c)
            if found is None:
                problems.append(f"{at}: {c!r} is not a criterion; the shapes are {', '.join(SHAPES)}.")
                continue
            kinds_here.append(found[0])
            if found[0] == "event" and found[1].group(1) not in EVENTS:
                problems.append(f"{at}: {c!r} names an event nothing emits; the events are "
                                f"{', '.join(EVENTS)}.")
            if found[0] == "taken" and not any(
                    isinstance(cd, dict) and cd.get("key") == found[1].group(2)
                    and cd.get("kind") == "quest" for cd in doc.get("cards") or []):
                problems.append(f"{at}: {c!r} names no quest card of this scheme; taken() "
                                f"takes a quest card's key ("
                                + ", ".join(sorted(str(cd.get("key")) for cd in doc.get("cards") or []
                                                   if isinstance(cd, dict)
                                                   and cd.get("kind") == "quest")) + ").")
            if found[0] in _PLAYER_CHANGEABLE:
                changeable = True
            if found[0] in ("has", "holds") and found[1].group(2) == "pc":
                changeable = True
            check_slots(c, at)
        if not changeable and any(k in ("alive", "present") for k in kinds_here) \
                and any(k in ("at", "arrived", "left", "event") for k in kinds_here):
            changeable = True
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
            # Two spellings for the same idea, and the wrong one is silent. `move`,
            # `hide` and `kill` name their subject `who`; `grant` and `remove` name it
            # `to`, and `_grant`/`_remove` default it to the player. So a `remove`
            # authored with `who` validates, reads correctly to a person, and takes the
            # tag off the PC instead. Caught the first time `remove` was ever used as a
            # step action, 2026-09-13.
            if act["do"] in ("grant", "remove") and "who" in act and "to" not in act:
                problems.append(
                    f"{at}: {act['do']} names its subject with \"to\", not \"who\" — as "
                    f"written this would act on the player. Use "
                    f"{{\"do\": \"{act['do']}\", \"to\": {act.get('who')!r}, ...}}.")
            if act["do"] == "open_card":
                card = next((c for c in doc.get("cards") or []
                             if isinstance(c, dict) and c.get("key") == act.get("card")),
                            None)
                if card is not None and not card.get("deferred"):
                    problems.append(
                        f"{at}: opens card {act.get('card')!r}, which is already on the "
                        f"board from the scheme's own open — mark it "
                        f"\"deferred\": true, or drop this action.")
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
            for tag in act.get("tags") or []:
                if not re.fullmatch(r"[a-z][a-z0-9.\-_$]*", str(tag)):
                    problems.append(f"{at}: {tag!r} is not a tag.")
                elif act["do"] in ("grant", "remove") and not str(tag).startswith(GRANTABLE):
                    problems.append(f"{at}: a scheme may grant or remove {', '.join(GRANTABLE)} "
                                    f"— not {tag!r}; a state that stops actions or ends "
                                    f"on rest is the engine's to write.")
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
        told = str((st.get("tell") or {}).get("perceptible", "")).lower() \
            if isinstance(st.get("tell"), dict) else ""
        twisty = any("knows." in " ".join(a.get("tags") or []) for a in grants) and \
            bool(re.search(r"\b(kin|lied?|lies|never)\b", told))
        outs = (doc.get("outcomes") or {})
        for a in [st.get("action")] + list(st.get("also") or []):
            if isinstance(a, dict) and a.get("do") == "outcome":
                o = outs.get(str(a.get("name") or "")) or {}
                lays_state = any(str(tg).startswith("state.") and str(g.get("to", "pc")) == "pc"
                                 for g in o.get("grants") or [] for tg in g.get("tags") or [])
                fails = str(o.get("how") or "") == "failed"
                if lays_state or fails:
                    twisty = True
            if isinstance(a, dict) and a.get("do") == "grant" and str(a.get("to", "pc")) == "pc" \
                    and any(str(tg).startswith("state.") for tg in a.get("tags") or []):
                twisty = True
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
        for g in list(out.get("grants") or []) + list(out.get("removes") or []):
            check_slots(g.get("to", ""), f"outcomes.{name}")
            for tag in g.get("tags") or []:
                if not re.fullmatch(r"[a-z][a-z0-9.\-_$]*", str(tag)):
                    problems.append(f"outcomes.{name}: {tag!r} is not a tag.")
                elif not str(tag).startswith(GRANTABLE):
                    problems.append(f"outcomes.{name}: a scheme may grant or remove "
                                    f"{', '.join(GRANTABLE)} — not {tag!r}.")
    # The other half of `deferred`: a card held back and never opened is a card that
    # simply does not exist, and the scheme reads as though it does.
    opened_by_step = {a.get("card") for st in steps if isinstance(st, dict)
                      for a in [st.get("action")] + list(st.get("also") or [])
                      if isinstance(a, dict) and a.get("do") == "open_card"}
    for card in doc.get("cards") or []:
        if isinstance(card, dict) and card.get("deferred") \
                and card.get("key") not in opened_by_step:
            problems.append(
                f"cards.{card.get('key')}: deferred, but no step opens it — add "
                f"{{\"do\": \"open_card\", \"card\": \"{card.get('key')}\"}} to a step, "
                f"or drop \"deferred\".")
    return problems


# --- slot filling -----------------------------------------------------------------------------

# Two readers. The cast is matched by substring, in any order; the codex chooser
# (`rules/npcs.py`) weighs them in THIS order, first word heaviest, so "someone of
# standing" is a noble before a sail master. A relationship is not a job — no codex
# has a block called "sister" that means one — so the kin words end in what the kin of
# a villager most often is, and the person's own name and world id still come from the
# cast; only the numbers come from the block.
_ROLE_WORDS = {
    "trader": ("trader", "merchant", "shopkeeper", "stallholder", "dealer", "seller"),
    "fixer": ("fixer", "broker", "factor", "agent"),
    "kin": ("kin", "sibling", "cousin", "son", "daughter", "brother", "sister",
            "farmer", "villager", "commoner"),
    "guard officer": ("guard", "captain", "sergeant", "watch", "officer", "constable"),
    "standing": ("elder", "noble", "councillor", "lord", "lady", "chief", "priest", "master"),
    "companion": ("companion",),
    # A tie role since the backgrounds shipped (the bonesetter's teacher) and missing
    # here, so "healer" was matched as the one word and nothing else: a world whose
    # healers are "physicians" or "herbalists" had none.
    "healer": ("healer", "physician", "herbalist", "midwife", "bonesetter", "surgeon",
               "apothecary", "chirurgeon"),
}


def role_words(role: str) -> tuple[str, ...]:
    """The words a role is matched by, for any reader that must agree with `_role_for`."""
    role = str(role or "")
    return _ROLE_WORDS.get(role, (role,) if role else ())


def _place_for(engine, kind: str, spec: dict) -> dict | None:
    scene = engine.scene
    known = engine.places()
    if kind in ("wild", "road"):
        found = engine.world.get(scene.location_id) if engine.world else None
        terrain = engine._terrain_hint(found) or "grassland"
        region = places_mod.region_set(scene.location_id, terrain)
        # The wild is where a travel by ground lands, the region's first place, so a
        # person put there is met on arrival; the road is the region's edge — the way
        # out — a place apart from it.
        p = region[2] if kind == "road" and len(region) > 2 else region[0]
        # Where the ground has a reach of the hinterland (`geography.Reach`), a travel by
        # ground lands THERE now ("the grasslands", 2026-10-05), so the wild is the reach
        # — a person put at the region's approach would stand in a place nobody arrives at.
        if kind == "wild" and found is not None:
            from . import outskirts as outskirts_mod

            reach = outskirts_mod.reach_of(engine._ring(found, scene.at), terrain)
            p = reach or p
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


# The sides a scheme's `bring_in` writes for people who come to fight the party. Anybody
# else it brings — a witness, a mourner, a side of "" — is not a fight and is not priced:
# the budget is what a fight may cost, and a witness costs nothing.
HOSTILE_SIDES = frozenset({"them", "foe"})


def _hostile_count(engine, act: dict, template: str, role: str) -> int:
    """How many of a `bring_in` arrive: the document's count, or, when they come to fight,
    as many as the encounter budget buys (`encounter_budget.most_of`), never fewer than
    one. Guards price as guards ("guarded"), anybody else as a document's staged fight
    ("opening").

    Measured 2026-11-13: a-small-favour's accusation brings "guard" x2 against the player
    and the wild's hunters x2 then x3; at a lone level-1 PC (APL -1, 135 XP average) two
    CR 1 guards are 800 XP, a CR 3 encounter, the fight the budget was written to end."""
    wanted = max(1, int(act.get("count", 1) or 1))
    if str(act.get("side") or "") not in HOSTILE_SIDES or wanted == 1:
        return wanted
    from . import bestiary
    from . import encounter_budget as eb

    each = eb.xp_of(bestiary.lookup(template) or {})
    hard = engine.dice.roll("1d100", label="how hard they come",
                            visibility="hidden").total
    kind = "guarded" if ("guard" in role or "watch" in role) else "opening"
    return eb.most_of(each, wanted, eb.party_apl(engine.scene), hard, kind=kind)


def _template_for(engine, role: str) -> str:
    """The stat block `bring_in` should put on the board for a role word.

    This used to be three hand-written names and nothing else:

        "watchman" if "guard" in role or "watch" in role
        else "thug" if "thug" in role else "guildhand"

    — so every role that was not a guard or a thug arrived as a guildhand. Named in
    docs/quest-schemes-plan.md §10 as still open, and measured on 2026-09-13 when a
    scheme about something eating a herd wrote `bring_in` with role "beast" and the
    thing that walked out of the scrub was a Commoner 1 who is "not paid enough to
    fight". The codex has seven thousand stat blocks and this asked it for none of them.

    The three originals stay as the floor rather than as the answer: `npcs.choose`
    already falls back to watchman for guard-shaped words, thug for thug-shaped ones and
    guildhand for everything else, so the wanted line's guards arrive exactly as before
    — `tests/test_wanted.py` and `test_a_small_favour.py` pin that — and anything else
    now gets a real creature near the party's level.
    """
    from . import npcs

    pc = engine.scene.pc()
    level = int(getattr(pc, "level", 1) or 1)
    got = npcs.choose(re.split(r"[\s,/]+", role.strip().lower()), level) or {}
    return str(got.get("id") or "guildhand")


def _starts_fresh(doc: dict) -> bool:
    """Whether this scheme begins a story rather than continuing one.

    A continuation is recognised by what it waits for: `has(pc, knows.…)` is knowledge
    only another scheme could have granted.
    """
    return not any(re.match(r"^\s*has\(pc,\s*knows\.", str(c))
                   for c in doc.get("opens") or [])


def _unfinished_fresh(scene, docs: dict) -> int:
    """Open instances of fresh-start schemes that have not reached an outcome."""
    return sum(1 for inst in scene.schemes
               if not inst.get("outcome")
               and _starts_fresh(docs.get(inst.get("scheme"), {})))


def _cast_candidates(engine, anywhere: bool = False) -> list[dict]:
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
        if str(c.get("home_id") or "") == here or anywhere:
            out.append(c)
    return out


def _fits_role(world, row: dict, words) -> bool:
    """Whether this cast member does the work, by their OWN entity's role fact.

    Item 8, measured 2026-09-28: every one of Aurvantis's 256 and Pangrella's 47 cast rows
    says `role: "Person"`, so nothing ever matched the row and every tie and every giver
    fell to the deterministic fallback — cast[0], Drenn Ironvale, first in every game.
    Their own entities say what they do ("Role: healer"); `geography.role_of` reads that,
    and whole words, so Pangrella's long role phrases still match.
    """
    from . import geography

    said = geography.role_of(world, row).lower()
    return bool(said) and any(re.search(r"\b" + re.escape(w) + r"\b", said) for w in words)


def _pick_person(engine, slot: str, words, taken: set) -> dict | None:
    """The world person who fills a part: seeded by the CAMPAIGN, never first-in-list.

    Preference, each pool id-sorted before the draw so the answer depends on the story
    seed and not on the export's order: somebody here whose own role fits; somebody
    anywhere whose role fits (a tie in the past can be "Wenna Cobbe of Brindle Ford");
    anybody here; anybody anywhere — a world name before a role word, which the playtest
    that found every role in a town named "standing" asked for.

    One list of the spoken-for across every binder (`Scene.spoken_for`), so a background
    tie and a quest giver are never the same person by accident (item 8.3).
    """
    from . import openings

    world = engine.world
    if world is None:
        return None
    scene = engine.scene
    spoken = openings.spoken_for(scene) | {str(t) for t in taken}

    def free(rows):
        return sorted((c for c in rows if str(c.get("id")) not in spoken),
                      key=lambda c: str(c.get("id")))
    here = free(_cast_candidates(engine))
    anywhere = free(_cast_candidates(engine, anywhere=True))
    rng = openings.rng_for(getattr(scene, "story_seed", 0) or 0,
                           f"cast:{slot}:{len(spoken)}")
    for pool in ([c for c in here if _fits_role(world, c, words)],
                 [c for c in anywhere if _fits_role(world, c, words)], here, anywhere):
        if pool:
            return pool[rng.randrange(len(pool))]
    return None


def _role_for(engine, name: str, spec: dict, filled: dict, taken: set,
              place: bool = True) -> dict | None:
    """A person for the role: a cast member of this place when there is one (grounded,
    their own name and world id), else nobody in particular named by the role. Either
    way the numbers come from the codex chooser — a stat block by the role's words
    near the party's level, docs/npc-codex.md — and a cast member's block is remembered
    in `homebrew/npcs/` so they have the same numbers next time. Placed where the slot
    says.

    `place=False` asks the same question and puts nobody in the scene — the caller wants
    the world's own name for somebody and not a body standing here. Backgrounds bind that
    way; a scheme that means to introduce somebody does not.
    """
    from . import npcs
    from . import openings
    from .bestiary import instantiate

    scene = engine.scene
    role = str(spec.get("role") or "")
    words = _ROLE_WORDS.get(role, (role,))
    pick = _pick_person(engine, name, words, taken)
    if pick is not None:
        taken.add(str(pick["id"]))
        openings.speak_for(scene, str(pick["id"]))
    pc = scene.pc()
    level = int(getattr(pc, "level", 1) or 1)
    # A slot may say `"named": true` for a person who should not be "Guard" — a rival
    # with a story block's numbers, name stripped, story left behind.
    named = bool(spec.get("named"))
    if pick is not None:
        template = npcs.block_for(str(pick["id"]), words, level, str(pick["name"]),
                                  prefer_named=named)
        actor = instantiate(template, scene=scene, name=str(pick["name"]),
                            world_entity_id=str(pick["id"]))
    else:
        # Named by the role asked for, not by the block: a Game Mastery Guide "Guard"
        # is a fine name in any world and an Inner Sea "Thrune Agent" is not.
        got = npcs.choose(words, level, prefer_named=named) or {}
        actor = instantiate(str(got.get("id") or "guildhand"), scene=scene,
                            name=role or str(got.get("role") or "someone"))
    if not place:
        # A name out of the world, and nobody put anywhere. Backgrounds need this: a tie
        # is about the PAST — "you fought where Drenn Ironvale took the bets" — and this
        # function, written for schemes that mean to stand somebody in front of the
        # player, was adding that person to the opening scene as a body with hit points.
        # Reported at the table 2026-09-20: "drenn ironvale is named has a part of my
        # background but does not belong in the scene."
        return {"kind": "name", "ref": "", "name": actor.name,
                "entity": actor.world_entity_id or ""}
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
    taken = {str(s.get("id")) for inst in engine.scene.schemes for s in inst.get("slots", {}).values()
             if s.get("kind") == "item"}
    pool = sorted(pool, key=lambda i: i.name)
    free = [i for i in pool if i.id not in taken] or pool
    seed = sum(ord(ch) for ch in f"{engine.scene.location_id}:{spec.get('item', '')}")
    pick = free[seed % len(free)]
    return {"kind": "item", "id": pick.id, "name": pick.name, "biome": biome}


def _place_held(engine, slots: dict, filled: dict) -> list[str]:
    """Put each item slot's thing in the hands of the person slot its `held_by` names, the
    way a gift or loot would (`hand_item`), once — the slot is marked `placed`. Returns the
    slot names placed.

    Measured on the owner's 0.2.25 report (2026-11-01): the-lost-thing's Anise was a label
    and nothing else. The truth card says the rival "took the $lost and is out at $wild
    with it", but no one carried it: killing and looting the rival gave 6 sp, and the
    `returned` step (`holds(pc, $lost)`) could never fire. A thing the story says somebody
    has is on them, so loot, a steal or a hand-over finds it (`_holds` reads the shelf by
    the slot's name)."""
    done: list[str] = []
    for name, spec in (slots or {}).items():
        if not isinstance(spec, dict) or not spec.get("item") or not spec.get("held_by"):
            continue
        slot = filled.get(name) or {}
        if slot.get("kind") != "item" or slot.get("placed"):
            continue
        holder = _who(engine.scene, filled, str(spec["held_by"]))
        if holder is None or getattr(holder, "is_pc", False):
            continue
        hand_item(engine.scene, holder, str(slot.get("name") or ""))
        slot["placed"] = str(holder.ref)
        done.append(name)
    return done


def fill_slots(engine, doc: dict) -> dict:
    """Places first (people are put in them), then items (by the wild place's ground),
    then people. Frozen on the instance. A slot written as {"from": "scheme.slot"}
    takes the filled slot of that scheme's instance, so a line's later quests keep
    the first quest's giver and captain rather than minting new people."""
    filled: dict = {}
    slots = dict(doc.get("slots") or {})
    for name, spec in list(slots.items()):
        src = str(spec.get("from") or "") if isinstance(spec, dict) else ""
        if src and "." in src:
            other, slot = src.split(".", 1)
            inst = _find(engine.scene, other)
            if inst is not None and slot in inst.get("slots", {}):
                filled[name] = dict(inst["slots"][slot])
                slots.pop(name)
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
    # The local set is only this scheme's own; `_role_for` also reads and writes the
    # scene's shared `spoken_for`, so a giver is never somebody's background tie.
    taken: set = set()
    for name, spec in slots.items():
        if spec.get("role"):
            got = _role_for(engine, name, spec, filled, taken)
            if got:
                filled[name] = got
    _place_held(engine, slots, filled)
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
        # A deferred card is declared here and opened later, by a step's `open_card`.
        # Everything a scheme knows at open used to arrive at open, which meant a line
        # could not hand the player a second quest partway through — the card had to be
        # on the board from the first turn, spoiling whatever it was about.
        if card.get("deferred"):
            continue
        _open_one_card(engine, inst, doc, card, filled, turn)
    inst["town"] = str(scene.location_id or "")
    for g in doc.get("grants_on_open") or []:
        _grant(scene, filled, g, f"scheme:{doc['id']}/open", inst)
    scene.schemes.append(inst)
    # What the open does to the world besides its cards and grants — a witness who
    # goes to ground the moment the name is wanted — without spending the first tick
    # on it. Silent by nature: the open itself is not a thing the player witnesses.
    done = []
    for act in doc.get("on_open") or []:
        if isinstance(act, dict):
            _do(engine, inst, doc, act, "open", turn)
            done.append(str(act.get("do")))
    if done:
        inst["fired"]["open"] = {"clock": int(scene.clock_minutes), "turn": turn,
                                 "silent": True, "tell": "", "actions": done}
    return inst


def _open_one_card(engine, inst: dict, doc: dict, card: dict, filled: dict,
                   turn: int) -> None:
    """Put one of a scheme's declared cards on the board.

    Its own function because two callers need it now and they must not drift: the open,
    and a step's `open_card`. `open_card` was in `ACTIONS` and accepted by the validator
    from the day the vocabulary was written and had no branch in `_do` at all, so a
    scheme that authored it passed every check and silently did nothing — the worst
    shape a feature can have, because nothing anywhere says no.
    """
    scene = engine.scene
    if card.get("kind") == "quest":
        giver = filled.get(str(card.get("giver", "")).lstrip("$"), {}).get("ref", "")
        made = cards_mod.open_quest(
                scene, title=fill_text(card["title"], filled),
                objectives=[fill_text(o, filled) for o in card.get("objectives") or []],
                giver=giver, reward=fill_text(card.get("reward", ""), filled),
                facts=[fill_text(f, filled) for f in card.get("facts") or []],
            people=[giver] if giver else [], place=str(scene.at or ""),
            origin=f"scheme:{doc['id']}", turn=turn,
            # A scheme that STARTS a story (`_starts_fresh`: somebody's favour, a debt to
            # collect, a lost thing) opens its quest unheard: nobody has put it to the
            # player yet. A beat that carries it to them makes it heard or offered
            # (`cards.note_heard`), and only the player takes it up (`Engine._op_quest`,
            # `acts_to_ops.take_ups`). Until 2026-10-27 it was the player's quest from
            # this moment (the owner's report: "not a request that i ever took or
            # heard"). A scheme that CONTINUES the player's own story — it opens on what
            # they know, `has(pc, knows.…)`: a name to clear, a price on their head —
            # is theirs already, as it always was.
            known="unheard" if _starts_fresh(doc) else "taken")
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


def _who(scene, filled: dict, ref: str):
    if ref == "pc":
        return scene.pc()
    name = str(ref).lstrip("$")
    slot = filled.get(name) or {}
    return scene.people.get(slot.get("ref", "")) if slot.get("kind") == "actor" else None


def _tags_of(scene, g: dict, inst: dict | None = None) -> tuple[str, ...]:
    """The tags a grant names, with `$town` spelled the way the readers spell it —
    the town the scheme OPENED in, off its instance, never the ground the player
    happens to stand on when a later step fires (the three-laws critic moved the
    party and watched a removal miss)."""
    from . import states

    where = (inst or {}).get("town") or scene.location_id
    town = states.town_tag(where)
    return tuple(str(t).replace("$town", town) for t in g.get("tags") or ())


def _remove(scene, filled: dict, g: dict, inst: dict | None = None) -> int:
    """Take off every effect whose tags answer one of the prefixes named — the one
    removal, so clearing a name evaporates every bite (docs/wanted.md)."""
    from . import states

    who = _who(scene, filled, str(g.get("to", "pc")))
    if who is None:
        return 0
    wanted = _tags_of(scene, g, inst)
    gone = who.remove_effects(match=lambda e: any(states.matches(str(tg), q)
                                                  for tg in e.tags for q in wanted))
    return len(gone)


def _charge_problems(g: dict, at: str) -> list[str]:
    """A warrant a scheme grants may say what it is for (`charge`), which the trial reads
    (rules/trial.py): one of the law's own charges, and only on a warrant."""
    if "charge" not in g:
        return []
    from . import trial

    kinds = tuple(trial.document()["charges"])
    if g.get("charge") not in kinds:
        return [f"{at}.charge: one of {', '.join(kinds)} — what the warrant is for."]
    if not any(str(t).startswith(("state.wanted", "state.suspected"))
               for t in g.get("tags") or ()):
        return [f"{at}.charge: a charge goes on a warrant — grant state.wanted.$town or "
                f"state.suspected.$town with it."]
    return []


def _grant(scene, filled: dict, g: dict, source: str, inst: dict | None = None) -> None:
    who = _who(scene, filled, str(g.get("to", "pc")))
    if who is None:
        return
    tags = _tags_of(scene, g, inst)
    if not tags:
        return
    key = f"{source}:{'+'.join(tags)}"
    if any(e.key == key for e in who.effects):
        return
    # The effect's name is what the brief will say the player noticed: a `say` in
    # the document's words, else the tag's leaf.
    said = fill_text(str(g.get("say") or ""), filled) if inst is not None or filled else str(g.get("say") or "")
    # What a warrant is for, when the document says (`charge`): the trial's evidence that
    # the watch accuses the player of it (rules/trial.py `charges`).
    payload = {"crime": str(g["charge"])} if g.get("charge") else {}
    who.apply_effect(ActiveEffect(name=said or tags[0].split(".")[-1].replace("-", " "),
                                  kind="situation", key=key, source=source, origin=source,
                                  duration="until-dismissed", tags=tags, payload=payload))


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
    if any(str(s.base).lower() == want and s.count > 0 for s in pc.stock.values()):
        return True
    # The satchel, by ingredient id: foraging writes it (`Actor.carry`), and the
    # playtest found the frame unreachable because only the shelf was read.
    iid = str(slot.get("id") or "").lower()
    inv = getattr(pc, "inventory", None) or {}
    return bool(iid) and int(inv.get(iid, 0) or 0) > 0
    return any(str(s.base).lower() == want and s.count > 0 for s in pc.stock.values()) \
        or str(slot.get("id") or "") in (pc.materials if hasattr(pc, "materials") else {})


def _item_is(said, slot: dict) -> bool:
    """Whether the thing a give named is the item slot's thing: its name or its id, with
    case, hyphens and spaces not counting ("marsh mallow" is the Marsh-Mallow the slot
    holds as `marsh-mallow`). The give op writes what the plan called it."""
    if not slot or slot.get("kind", "item") != "item":
        return False

    def norm(x) -> str:
        return " ".join(re.sub(r"[-_]+", " ", str(x or "").lower()).split())

    got = norm(said)
    return bool(got) and got in {norm(slot.get("name")), norm(slot.get("id"))} - {""}


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
        if "$town" in tag:
            from . import states

            tag = tag.replace("$town", states.town_tag(inst.get("town") or scene.location_id))
        actor = _who(scene, filled, who)
        v = bool(actor is not None and actor.has_state(tag))
        return (not v) if neg else v
    if kind == "since":
        anchor, hours = m.group(1), int(m.group(2)) * (24 if m.group(3) == "d" else 1)
        if anchor == "open":
            start = inst["opened_at"]
        elif anchor == "campaign":
            start = 0
        elif anchor.startswith("left("):
            start = (inst.get("left_at") or {}).get(anchor[6:-1])
            if start is None:
                return False
        else:
            start = (inst["fired"].get(anchor) or {}).get("clock")
            if start is None:
                return False
        return scene.clock_minutes - start >= hours * 60
    if kind == "clock":
        return scene.clock_minutes >= int(m.group(1))
    if kind == "event":
        name, slot, thing = m.group(1), m.group(2), m.group(3)
        for e in events:
            if e.get("event") != name:
                continue
            # A give is the PLAYER's give: something the world handed the giver (no
            # `from`), or another person's, is not the player returning anything. An event
            # with no `from` key at all is an older caller's and is read as before.
            if name == "give" and "from" in e and pc is not None \
                    and str(e.get("from") or "") != pc.ref:
                continue
            if thing and not _item_is(e.get("item"), filled.get(thing) or {}):
                continue
            if slot:
                s = filled.get(slot) or {}
                if s.get("kind") == "actor" and e.get("to") == s.get("ref"):
                    return True
                if s.get("kind") == "item" and _item_is(e.get("item"), s):
                    return True
                continue
            return True
        return False
    if kind == "taken":
        neg, key = m.group(1), m.group(2)
        card = _card(scene, inst, key)
        v = card is not None and cards_mod.standing(card) == cards_mod.OWN
        return (not v) if neg else v
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


def _events_from(outcomes, pc_ref: str = "") -> list[dict]:
    """What happened this tick, in the engine's own words: op names and their people.

    `talk` is an exchange between the player and one other person, from the `said` effect
    a `say` outcome carries (`Engine._op_say`): the player speaking to them, or them
    speaking to the player. `to` is always the other person, so `event:talk($giver)`
    reads as "the player and the giver spoke". Two people talking to each other within
    the player's hearing is not the player talking to either.

    Before this, the-lost-thing's `noticed` step could only key on the giver being
    present (Lane D moved it off the open), so the player "noticed" the giver keeping
    something back without ever having exchanged a word with them."""
    out = []
    for o in outcomes or []:
        op = str(getattr(o, "op", ""))
        for eff in getattr(o, "effects", None) or []:
            if not isinstance(eff, dict):
                continue
            if op == "say" and eff.get("kind") == "said":
                # An empty `who` is the player: `_op_say` speaks as the PC when the
                # intent names no actor.
                who, to = str(eff.get("who") or ""), str(eff.get("to") or "")
                mine = {"", str(pc_ref or "")}
                other = to if who in mine else who if to and to in mine else ""
                if other and other not in mine:
                    out.append({"event": "talk", "to": other})
            if op == "travel" or eff.get("kind") == "travel":
                out.append({"event": "travel"})
            if op == "give" and eff.get("kind") in ("give", "took", "gave", "given", "handed", "bought"):
                # The give op's effect names the taker as `ref` and the thing as `item`, and
                # who handed it over as `from` ("" when the world did: a pick-up, a gift
                # out of the air) — so `event:give` can ask that it was the player's hand.
                out.append({"event": "give", "to": eff.get("to") or eff.get("ref"),
                            "item": eff.get("item"), "from": str(eff.get("from") or "")})
            if op == "quest_step" and not eff.get("engine_owns"):
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
    cid = (inst.get("cards") or {}).get(key)
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
        # Through the one damage door, so the death is a provenanced number on the
        # record like any other, not a hit-point write above the ladder.
        who = _who(scene, filled, act.get("who", ""))
        if who is not None and not who.is_pc:
            amount = max(1, who.hp + abs(who.ability_score("con")) + 1)
            # The one damage door, in the room or out of it. Off-stage this used to write
            # `who.hp -= amount` because the door read the here-view and raised KeyError
            # for a victim at the lodging; the door reads the store now (2026-09-25),
            # so resistances and guards apply wherever the body is.
            hit = engine._apply_damage(who, amount, "untyped", lethality="lethal")
            if isinstance(hit, dict):
                hit["origin"] = source
                if who.at != scene.at:
                    hit["off_stage"] = True
            inst.setdefault("damage", []).append({"step": step_id, "who": who.ref,
                                                  "origin": source, "record": hit})
            who.apply_hp_state()
    elif what == "bring_in":
        role = str(act.get("role") or "watchman")
        template = _template_for(engine, role)
        side = str(act.get("side") or "")
        born = engine._bring_in(template, count=_hostile_count(engine, act, template, role),
                                side=side)
        inst.setdefault("brought", []).extend(b["ref"] for b in born)
        if side in HOSTILE_SIDES:
            # Priced by `_hostile_count`: not again when a model's fight wraps them.
            engine._mark_priced([b["ref"] for b in born], f"scheme:{doc['id']}")
        if "guard" in role or "watch" in role:
            for b in born:
                _grant(scene, {"_": {"kind": "actor", "ref": b["ref"]}},
                       {"to": "$_", "tags": ["role.guard"]}, source, inst)
    elif what == "fact":
        card = _card(scene, inst, act.get("card", ""))
        if card is not None:
            cards_mod.touch(scene, card.id, fill_text(act.get("text", ""), filled), turn=turn, tick=False)
    elif what == "objective":
        card = _card(scene, inst, act.get("card", ""))
        if card is not None:
            done = cards_mod.objective_done(scene, card.id, int(act.get("n", 1)) - 1, turn=turn)
            # The last objective resolves the card on its own; an outcome in the same
            # step still owes its award for it.
            if done is not None and not done.live:
                inst.setdefault("_resolved_now", []).append(str(act.get("card", "")))
    elif what == "reveal_objective":
        card = _card(scene, inst, act.get("card", ""))
        if card is not None and card.kind == "quest":
            card.objectives.append({"text": fill_text(act.get("text", ""), filled), "done": False})
            card.clock_max = max(1, len(card.objectives))
            cards_mod._store(scene, card)
    elif what == "resolve":
        card = _card(scene, inst, act.get("card", ""))
        # A card already finished stays finished: a later `moot` would otherwise turn an
        # errand the player had handed back (`returned`) into one they dropped.
        if card is not None and card.live:
            inst.setdefault("_resolved_now", []).append(str(act.get("card", "")))
            cards_mod.resolve(scene, card.id, how=str(act.get("how") or "resolved"), turn=turn)
    elif what == "grant":
        _grant(scene, filled, act, source, inst)
    elif what == "remove":
        _remove(scene, filled, act, inst)
    elif what == "open_card":
        key = str(act.get("card") or "")
        # Never twice. A step may be authored `once: false`, and a card opened on every
        # tick would stack identical quests on the board until the player stopped moving.
        if key and key not in inst["cards"]:
            card = next((c for c in doc.get("cards") or [] if c.get("key") == key), None)
            if card is not None:
                _open_one_card(engine, inst, doc, card, filled, turn)
    elif what == "news":
        inst["news"].append({"carrier": act.get("carrier"), "reach": act.get("reach"),
                             "delay": _hours(act.get("delay")), "says": fill_text(act.get("says", ""), filled),
                             "born": int(scene.clock_minutes), "born_tick": int(inst.get("ticks", 0)),
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
    # Removals first, grants after: justice lifts the warrant, and a bargain lifts it
    # and lays the lesser one down in the same breath.
    for g in out.get("removes") or []:
        _remove(scene, inst["slots"], g, inst)
    for g in out.get("grants") or []:
        _grant(scene, inst["slots"], g, source, inst)
    card = _card(scene, inst, out["resolve"]) if out.get("resolve") else None
    # Live now, or resolved by this same step's own `resolve` action a moment ago —
    # not by a model's quest_step, which already paid.
    was_live = bool(card is not None and (card.live or out["resolve"] in (inst.get("_resolved_now") or [])))
    if card is not None and was_live:
        if inst.get("_silent_step"):
            # Resolved out of the player's sight: the card waits, so the quest log
            # does not announce what the character has not learned. It lands with
            # the next perceptible step of this scheme.
            inst["pending_resolve"] = {"card": out["resolve"], "how": str(out.get("how") or "resolved")}
        else:
            cards_mod.resolve(scene, card.id, how=str(out.get("how") or "resolved"), turn=turn)
    # The award pays once: a card the GM's own quest_step already finished has been paid.
    # And only for the player's own matter: a quest they never took on is the world's
    # story moving, not theirs seen through. Measured on the owner's 0.2.25 save: the
    # sickness's `in-time` resolved "Bring Snik Dunmoor the Marsh-Mallow" — never heard of,
    # so its tell was hushed — and the award was still credited, 800 XP out of sight.
    # Asked before the resolve above changed nothing it reads (`standing` is `known`).
    theirs = card is None or card.kind not in cards_mod.TASKS \
        or cards_mod.standing(card) == cards_mod.OWN
    if out.get("award") and (card is None or was_live) and theirs:
        line = engine.award_story(str(out["award"]), card.title if card else doc.get("title", ""))
        if line:
            lines.append(line.strip())
    inst["award_line"] = " ".join(lines)
    return name


# --- the tick ---------------------------------------------------------------------------------------

_PROGRESS = ("objective", "reveal_objective")


def _rank(step: dict) -> tuple[int, int]:
    """How a step that holds is weighed against another (`tick`): one keyed on an event of
    this batch first, then the one with more criteria."""
    crits = step.get("criteria") or []
    keyed = any(str(c).strip().startswith("event:") for c in crits)
    return (1 if keyed else 0, len(crits))


def _progress_not_taken(scene, inst: dict, step: dict) -> str:
    """The title of the quest card this step's own action makes progress on, when the
    player has not taken it on (`cards.standing`); "" otherwise.

    The step still fires — the world's story moves whether or not the player took the
    errand, and the scheme's own tests hold it to that — but its outcome says whose the
    quest is (`not_own`), so the beat that tells it is read back for making it the
    player's goal (`planned.build_plan`, `GMAgent._not_their_goal`). Measured live
    2026-10-27 on a scratch Fizspark campaign, and on the owner's 0.2.21 save (row 82):
    walking out to the fields fired a-small-favour's `reached` — "the approach, the
    ground where Glowvine grows" — for a quest the player had only overheard, and the
    beat had them "searching the soil where the luminescent Glowvine is known to take
    root". Holding the step back until the quest was taken was tried first and broke
    eighteen scheme tests whose stories move without a take-up. The owner answered it
    (docs/known-matters.md §4.2, question 7): the step may tick, and on a quest the player
    has never heard of it says nothing at all (`_unheard_progress`, `tick`); this mark is
    for one they have heard of."""
    act = step.get("action") or {}
    if not isinstance(act, dict) or act.get("do") not in _PROGRESS:
        return ""
    cid = (inst.get("cards") or {}).get(str(act.get("card") or ""))
    card = cards_mod.find(scene, cid) if cid else None
    if card is None or card.kind != "quest" or cards_mod.standing(card) == cards_mod.OWN:
        return ""
    return card.title


def _unheard_progress(scene, inst: dict, step: dict) -> bool:
    """Whether this step's progress is on a quest the player has never heard of
    (`cards.standing` UNHEARD) — the owner's answer 7: such a step is silent."""
    act = step.get("action") or {}
    cid = (inst.get("cards") or {}).get(str((act or {}).get("card") or ""))
    card = cards_mod.find(scene, cid) if cid else None
    return card is not None and cards_mod.standing(card) == cards_mod.UNHEARD


def _heal_cast_grants(scene, docs: dict) -> None:
    """A scheme already open in a save gets the grants its document now makes to the
    people it cast. Measured on the owner's report of 2026-11-01: A Small Favour's captain
    was cast with no `role.guard` tag, so a wanted player stood beside him for six turns
    and he never came for them; the document grants `role.guard.officer` now, and a save
    from before would otherwise keep an untagged captain for ever. Idempotent: `_grant`
    skips a grant whose record is already on the person. The player's own grants are not
    replayed — those are story beats, given once."""
    for inst in scene.schemes:
        doc = docs.get(str(inst.get("scheme") or ""))
        # Finished stories too: a captain is still the law after the errand is over.
        if not doc:
            continue
        for g in doc.get("grants_on_open") or []:
            if not isinstance(g, dict):
                continue
            source = f"scheme:{doc['id']}/open"
            if str(g.get("to", "pc")) != "pc":
                _grant(scene, inst.get("slots") or {}, g, source, inst)
            elif g.get("charge"):
                # A warrant granted before warrants said what they were for: given its
                # charge, through the applicator (removed and granted again).
                pc = scene.pc()
                key = f"{source}:{'+'.join(_tags_of(scene, g, inst))}"
                old = next((e for e in (pc.effects if pc else ()) if e.key == key), None)
                if old is not None and not (old.payload or {}).get("crime"):
                    pc.remove_effects(match=lambda e, o=old: e is o)
                    _grant(scene, inst.get("slots") or {}, g, source, inst)


def tick(engine, outcomes) -> list:
    """Open what should open, then fire the one most specific step that holds, then
    deliver news that has arrived. Returns the outcomes the prose may see."""
    from .engine import Outcome

    scene = engine.scene
    pc = scene.pc()
    if pc is None:
        return []
    turn = int(getattr(engine, "turn", 0) or 0)
    events = _events_from(outcomes, pc.ref)
    made: list = []
    if not ENABLED:
        return made
    docs = all_schemes()
    _heal_cast_grants(scene, docs)

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
        if not all(_criterion_holds(engine, probe, doc, c, events)
                   for c in doc.get("opens") or []):
            continue
        if _starts_fresh(doc) and _unfinished_fresh(scene, docs) >= MAX_FRESH_OPEN:
            # The town is already doing enough to this player. Nothing is lost: the
            # criteria are re-tested every tick, so this opens the moment one of the
            # others ends.
            continue
        open_scheme(engine, doc, turn=turn)

    # Stepping: one step per instance per tick, the most specific.
    for inst in list(scene.schemes):
        doc = docs.get(inst["scheme"])
        if doc is None:
            continue
        # A scheme opened before its item had a holder (every save before 2026-11-01) is
        # given it now, once (`_place_held` marks the slot): the rival still alive and here
        # in the world is still the one who has it.
        if not inst.get("outcome"):
            _place_held(engine, doc.get("slots") or {}, inst.get("slots") or {})
        # An ended scheme still owes the player what it resolved out of their sight:
        # it keeps ticking, for perceptible steps only, until the banked line and the
        # deferred resolution have landed.
        owes = bool(inst.get("banked") or inst.get("pending_resolve") or inst.get("news"))
        if inst.get("outcome") and not owes:
            continue
        # The instance's own tick count, persisted with it: the live app builds a fresh
        # Engine per request, and a counter on the engine read 1 forever, so news born
        # on "tick 1" never arrived (playtest, 2026-09-08).
        inst["ticks"] = int(inst.get("ticks", 0)) + 1
        # Where the player has been, for `left($place)`.
        for name, slot in inst["slots"].items():
            if slot.get("kind") != "place":
                continue
            here_now = _at(scene, slot)
            if here_now and name not in inst["visited"]:
                inst["visited"].append(name)
            # The clock of leaving, per place, for `since(left($place))`: the fairness
            # critic measured `since(open)` starting the murder clock while the player
            # stood at the market between two short absences.
            was_here = name in (inst.get("here_last") or [])
            if was_here and not here_now:
                inst.setdefault("left_at", {})[name] = int(scene.clock_minutes)
        inst["here_last"] = [n for n, sl in inst["slots"].items()
                             if sl.get("kind") == "place" and _at(scene, sl)]
        best = None
        for st in doc.get("steps") or []:
            if st["id"] in inst["fired"] and st.get("once", True):
                continue
            if inst.get("outcome") and ("silent" in (st.get("tell") or {}) or "deferred" in (st.get("tell") or {})):
                continue
            crits = st.get("criteria") or []
            if not all(_criterion_holds(engine, inst, doc, c, events) for c in crits):
                continue
            needs = [t for t in st.get("fairness") or [] if not pc.has_state(t)]
            if needs:
                # One row per step and reason, its `last` moved on: appended every tick,
                # a twist held back for a long campaign grew the save by a row a tick
                # (audit 2026-11-07). `clock` stays when it was first held back.
                why = "foreshadowing not on the brief: " + ", ".join(needs)
                log = inst.setdefault("skipped", [])
                row = next((r for r in log if r.get("step") == st["id"]
                            and r.get("why") == why), None)
                if row is None:
                    log.append({"step": st["id"], "clock": scene.clock_minutes,
                                "last": scene.clock_minutes, "why": why})
                else:
                    row["last"] = scene.clock_minutes
                continue
            # Most specific first — and a step keyed on something that happened THIS batch
            # (`event:`) before any keyed on standing state. An event is now or never; the
            # state will still hold next tick. Found writing `event:give($sick, $herb)`: in
            # the tavern beside the sick woman, the sickness's four-criterion `seen` would
            # have outranked the hand-over every time until it fired, and the herb, given,
            # would have been gone with the quest left open for good.
            if best is None or _rank(st) > _rank(best):
                best = st
        if best is not None:
            tell = best.get("tell") or {}
            silent = "silent" in tell or "deferred" in tell
            # Asked before the step acts (its action may finish the card).
            theirs = _progress_not_taken(scene, inst, best)
            # The owner's answer 7 (2026-10-27): "if I am in the right spot and I get the
            # item that is fine but no mention should be made to me about anything since
            # my character would be unaware that I had an item someone wanted." A step on a
            # quest the player has never heard of ticks, and says nothing: no outcome, so
            # no tell, no planned slot and no line linking the place or the thing to the
            # errand. One they have heard of is different — they know of it — and keeps
            # its tell, marked `not_own` for the read-back.
            hushed = bool(theirs) and _unheard_progress(scene, inst, best)
            if hushed:
                silent = True
            inst["_silent_step"] = silent
            for act in [best.get("action")] + list(best.get("also") or []):
                if isinstance(act, dict):
                    _do(engine, inst, doc, act, best["id"], turn)
            inst.pop("_silent_step", None)
            inst.pop("_resolved_now", None)
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
            if silent:
                # Banked, not said: an XP line for a step the character did not see
                # would tell them the price was withdrawn out of sight (the leak
                # critic measured it). It rides the next perceptible tell — except a
                # line about an errand the player never heard of, which would name it.
                if extra and not hushed:
                    inst["banked"] = (inst.get("banked", "") + " " + extra).strip()
            else:
                pending = inst.pop("pending_resolve", None)
                if pending:
                    card = _card(scene, inst, pending["card"])
                    if card is not None and card.live:
                        cards_mod.resolve(scene, card.id, how=pending["how"], turn=turn)
                banked = inst.pop("banked", "")
                extra = " ".join(x for x in (banked, extra) if x)
                if said:
                    made.append(Outcome(
                        intent_id="", op="scheme",
                        effects=[{"kind": "scheme", "scheme": doc["id"], "step": best["id"],
                                  "origin": f"scheme:{doc['id']}/{best['id']}",
                                  **({"not_own": theirs} if theirs else {})}],
                        tell=said + (f" {extra}" if extra else ""), because="the world moves"))
                elif extra:
                    inst["banked"] = extra
        # News arrives by a route the character would meet.
        kept = []
        for item in inst.get("news") or []:
            # Never on the tick it was born: word takes at least one beat to travel,
            # and a step and its gossip landing together read as one event.
            if scene.clock_minutes - item["born"] < item["delay"] * 60                     or int(item.get("born_tick", -1)) >= int(inst.get("ticks", 0)):
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
        # Somebody the character can see and would hear it from: not the hidden, not
        # the dead, not the fight's other side. The leak critic measured the hidden
        # giver of the murder narrating the murder as gossip (2026-09-08).
        def can_talk(a):
            return (not a.is_pc and not a.has_state("state.hidden") and not a.is_down
                    and a.ref not in (scene.sides or {}).get("them", []))
        witness_refs = [s.get("ref") for s in inst["slots"].values()
                        if s.get("kind") == "actor"]
        talker = next((a for a in scene.actors.values() if can_talk(a) and a.ref in witness_refs
                       and not any(s.get("ref") == a.ref and n in ("giver", "victim")
                                   for n, s in inst["slots"].items())), None) \
            or next((a for a in scene.actors.values() if can_talk(a)
                     and not any(s.get("ref") == a.ref and n in ("giver", "victim")
                                 for n, s in inst["slots"].items())), None)
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


# --- who ticks a scheme's quest, and what is still missing -------------------------------------------
#
# A scheme's quest card is the scheme's: its objectives tick when a step's criteria hold,
# which are things the engine measures (a place reached, a thing held or handed over, a
# person present). The planner's `quest_step` and the watcher's `objective` are claims
# about the same objectives (`rules/objectives.py` judges them) and are checked against
# those same criteria — the one set of predicates, never a second reading of the words.

def card_owner(scene, card_id: str) -> tuple[dict, dict, str] | None:
    """The scheme instance that opened this card, its document and the card's key in it;
    None for a card no live document owns (a test's card, a scheme since removed)."""
    docs = all_schemes()
    for inst in scene.schemes:
        for key, cid in (inst.get("cards") or {}).items():
            if cid == card_id and inst.get("scheme") in docs:
                return inst, docs[inst["scheme"]], key
    return None


def ticking_steps(doc: dict, key: str, n: int) -> list[dict]:
    """The steps whose action ticks objective `n` (1-based) of the card `key`."""
    out = []
    for st in doc.get("steps") or []:
        for act in [st.get("action")] + list(st.get("also") or []):
            if isinstance(act, dict) and act.get("do") == "objective" \
                    and str(act.get("card") or "") == key and int(act.get("n", 1) or 1) == n:
                out.append(st)
                break
    return out


def criteria_hold(engine, inst: dict, doc: dict, step: dict, events) -> bool:
    return all(_criterion_holds(engine, inst, doc, c, list(events or []))
               for c in step.get("criteria") or [])


def unmet(engine, inst: dict, doc: dict, step: dict, events) -> list[str]:
    """What still stands between this step and firing, one plain sentence per criterion
    that does not hold — in the world's words, never a tag: a `has(pc, knows.…)` is said
    as "that has not come to light yet", because naming the tag would hand the player
    what their character does not know."""
    scene = engine.scene
    pc = scene.pc()
    me = pc.name if pc is not None else "You"
    filled = inst.get("slots") or {}

    def name(slot: str, fallback: str = "them") -> str:
        s = filled.get(slot) or {}
        return str(s.get("name") or fallback)

    said: list[str] = []
    for text in step.get("criteria") or []:
        if _criterion_holds(engine, inst, doc, text, list(events or [])):
            continue
        found = _criterion_kind(text)
        if found is None:
            continue
        kind, m = found
        if kind == "at":
            line = (f"{me} is still at {name(m.group(2), 'that place')}." if m.group(1)
                    else f"{me} is not at {name(m.group(2), 'that place')}.")
        elif kind in ("left", "arrived"):
            line = (f"{me} has not left {name(m.group(1), 'that place')}." if kind == "left"
                    else f"{me} has not come to {name(m.group(1), 'that place')}.")
        elif kind == "holds":
            line = (f"{me} still carries {name(m.group(2), 'it')}." if m.group(1)
                    else f"{me} does not carry {name(m.group(2), 'it')}.")
        elif kind == "present":
            line = (f"{name(m.group(2))} is here." if m.group(1)
                    else f"{name(m.group(2))} is not here.")
        elif kind == "alive":
            line = (f"{name(m.group(2))} is alive." if m.group(1)
                    else f"{name(m.group(2))} is dead.")
        elif kind == "event" and m.group(1) == "give":
            line = (f"{me} has not handed {name(m.group(3), 'it')} to {name(m.group(2))}."
                    if m.group(3) else f"{me} has not handed anything to {name(m.group(2))}."
                    if m.group(2) else f"{me} has not handed anything over.")
        elif kind == "event" and m.group(1) == "talk":
            line = f"{me} has not spoken with {name(m.group(2))}."
        elif kind == "event":
            line = "That has not happened yet."
        elif kind == "taken":
            card = _card(scene, inst, m.group(2))
            title = card.title if card is not None else "That errand"
            line = (f"{title} was taken on." if m.group(1)
                    else f"{title} has not been taken on.")
        elif kind in ("since", "clock"):
            line = "Not enough time has passed."
        else:
            line = "The matter has not come to that yet."
        if line not in said:
            said.append(line)
    return said


# --- a clue is a record, not a thing in the pack ---------------------------------------------------
#
# A scheme's clue is a `knows.clue.<leaf>` tag (wanted's witness, ledger and coin), granted
# by the step whose tell said what was found. The owner's 0.2.25 game: "Examine the coin
# more closely" at the shrine, the turn after "sewn into the coat is coin struck with a
# faction's mark", was refused "Corvin T. is not carrying the coin" — true of the pack and
# wrong as an answer, because the coin was never a thing to carry. Minting it as an item
# was weighed and refused: a ledger and a witness's word are clues too and neither is a
# thing, and a scheme handing out items is what the items lane is taking OUT of `give`.
# So a clue answers a look with its own record — the tell of the step that granted it.

def clue_named(scene, actor, phrase: str) -> dict | None:
    """The clue this actor holds that the phrase names, by the clue's own leaf ("the
    coin" is `knows.clue.coin`): `{"leaf", "record", "origin"}`, or None. The record is the
    granting step's own tell, frozen on the instance when it fired."""
    if actor is None:
        return None
    words = set(re.findall(r"[a-z]+", str(phrase or "").lower()))
    if not words:
        return None
    for eff in getattr(actor, "effects", ()) or ():
        for tag in eff.tags or ():
            if not str(tag).startswith("knows.clue."):
                continue
            leaf = str(tag).split(".")[-1]
            if not set(leaf.split("-")) <= words:
                continue
            source = str(eff.source or "")           # scheme:<id>/<step>
            sid, _, step = source.partition(":")[2].partition("/")
            inst = _find(scene, sid)
            record = str(((inst or {}).get("fired") or {}).get(step, {}).get("tell") or "")
            if record:
                return {"leaf": leaf, "record": record, "origin": source}
    return None


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

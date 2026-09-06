"""The event watcher, wired to something at last.

The "watcher" model role has been configured since the roles existed — deepseek-r1:8b,
chosen because a reasoning model suits reading a record and drawing a conclusion — and
it had ZERO call sites. `settings.py` said so out loud: "a model that is never loaded
and never called." Every campaign carried a live undercurrent from turn one (planted by
`new_campaign`) and nothing ever moved it; every corpse carried exactly what its spawn
kit rolled and nothing more personal than coin.

Three jobs now, all garnish on a game that works without them:

**The corpse garnish.** While the player is thinking, the watcher may add ONE flavour
item to a freshly dead actor — a locket, a half-burned note, a key. The model proposes
a name and a price band; the engine disposes: only a table-known item id, or an
explicitly-typed `Stock(kind="trinket")` whose price comes from the app's own pricing
formula through a closed band vocabulary, ever lands. No model-authored number or
mechanic touches the ledger.

**The living undercurrent.** Every `TURNS_BETWEEN_LOOKS` resolved turns, the watcher
reads the recent transcript against the GM's private note and either leaves it alone,
advances it one step, or — when the old thread has clearly resolved on stage — mints a
new one, preferring the world's own unused unwritten hooks. One sentence, rewritten in
place, never appended twice.

**The situation cards.** Every `CARD_TURNS_BETWEEN_LOOKS` resolved turns, the watcher
reads the last beats against the live cards (`rules/cards.py`) and says, per card,
keep, advance with one fact, or resolve — and may propose one new card. A talking turn
makes no tell, and this is how "she has the sealed jar" reaches the woman's card.

**Race safety is the design, not a bolt-on.** The player may loot the corpse, walk the
scene away, or the campaign may save mid-flight while the model is still thinking. So:

- `kick` runs in the request thread and builds *snapshots* (plain dicts, no live
  objects); the daemon thread only ever talks to the model and to `_PENDING` under a
  lock. It never touches a Campaign, so it can never race a save.
- `drain` runs in the next request's thread, re-reads the live campaign, and applies a
  proposal only if the world still matches the snapshot it was made against — the
  corpse still present, still down, its belongings untouched; the note byte-identical
  to the one the model read. Any mismatch is a silent drop. A deadline nobody notices.
- A model failure, a refused schema, an unreachable Ollama: silently nothing. Same rule
  as the narrator fallbacks — the watcher is a garnish, and a garnish must never cost a
  turn.
"""
from __future__ import annotations

import re
import threading

from . import client, narration as narration_mod

# How many resolved turns between looks at the undercurrent. Cheap either way — the
# call runs while the player is typing — but the note should move at the pace of scenes,
# not sentences.
TURNS_BETWEEN_LOOKS = 7
# How many resolved turns between looks at the situation cards. Oftener than the
# undercurrent, because a card is meant to move at the pace of a conversation:
# "as i seal the jar it seem to lose the initial situation" — a talking turn makes
# no tell, and without this nothing would ever put "she has the sealed jar" on the
# woman's card.
CARD_TURNS_BETWEEN_LOOKS = 3

# The closed price vocabulary. The model picks a word; the app's own `pricing` formula
# turns the tier into a number (inert, no specs — a locket is priced as a locket, about
# 4 sp / 1.5 gp / 5 gp). The model never writes a price.
BANDS = {"worthless": "common", "modest": "uncommon", "fine": "rare"}

_LOCK = threading.Lock()
_THREAD: threading.Thread | None = None
# Validated proposals waiting for the next request to apply them.
_PENDING: list[dict] = []
# Corpses already offered a garnish this process, by (campaign id, ref). One item per
# body, ever — and a corpse already down when the watcher first sees a campaign is not
# a *fresh* death, so it is pre-marked and left alone.
_GARNISHED: set[tuple[str, str]] = set()
# Resolved-turn count at the last undercurrent look, per campaign. In memory on
# purpose: a restart firing one look early is harmless.
_LAST_LOOK: dict[str, int] = {}
_LAST_CARD_LOOK: dict[str, int] = {}


def _reset() -> None:
    """Forget everything. For tests."""
    global _THREAD
    with _LOCK:
        _THREAD = None
        _PENDING.clear()
        _GARNISHED.clear()
        _LAST_LOOK.clear()
        _LAST_CARD_LOOK.clear()


# --- kick: decide what the watcher should look at, in the request thread ---------------

def kick(c):
    """Called after a finished, saved turn. Never blocks: snapshots are built here and
    the model call happens on a daemon thread. Returns the thread, or None."""
    global _THREAD
    if getattr(c, "ended", ""):
        return None
    with _LOCK:
        if _THREAD is not None and _THREAD.is_alive():
            # One flight at a time. A death this turn is seen again next turn — the
            # freshness marks are only made for jobs actually enqueued.
            return None
        jobs = _jobs_for(c)
        if not jobs:
            return None
        _THREAD = threading.Thread(target=_work, args=(jobs,), daemon=True,
                                   name="event-watcher")
        _THREAD.start()
        return _THREAD


def _jobs_for(c) -> list[dict]:
    """The snapshots. Pure data — nothing here survives into the worker but strings,
    dicts and a frozen name set."""
    jobs: list[dict] = []
    turns = sum(1 for e in c.turn_log if e.get("kind") == "turn")

    if c.id not in _LAST_LOOK:
        # First sight of this campaign. Anybody already dead died before the watcher
        # was looking, which is not a fresh death; and the undercurrent clock starts
        # from here rather than firing on a resumed save's whole history at once.
        _LAST_LOOK[c.id] = turns
        for ref, a in c.scene.actors.items():
            if not a.is_pc and _down(a):
                _GARNISHED.add((c.id, ref))
        return jobs

    known = _known(c)
    note = _note_content(c)

    ref = _fresh_corpse(c)
    if ref is not None:
        _GARNISHED.add((c.id, ref))
        a = c.scene.actors[ref]
        from play import opening

        jobs.append({
            "job": "garnish", "campaign": c.id, "ref": ref, "who": a.name,
            "snapshot": _belongings(a),
            "thread": opening.note_thread(note),
            "cast": [x.name for x in c.scene.actors.values() if x.name],
            "known": frozenset(known),
        })

    if turns - _LAST_LOOK[c.id] >= TURNS_BETWEEN_LOOKS:
        _LAST_LOOK[c.id] = turns
        from play import opening

        thread = opening.note_thread(note)
        jobs.append({
            "job": "undercurrent", "campaign": c.id, "was": note,
            "thread": thread,
            "recent": [f"{b.get('who', '?')}: {str(b.get('text', ''))[:300]}"
                       for b in c.transcript[-12:]],
            "hooks": [h for h in opening.hook_texts(c.world)
                      if h and h not in (thread or "")][:5],
            "known": frozenset(known),
        })

    # The situation cards (`rules/cards.py`). A snapshot of each live card and of
    # the people on the board, so the worker can neither touch the campaign nor
    # invent a person: a fact may name only names that appear here.
    from rules import cards as cards_mod

    live = [k for k in cards_mod.load(c.scene) if k.live]
    since = _LAST_CARD_LOOK.get(c.id, _LAST_LOOK[c.id])
    if live and turns - since >= CARD_TURNS_BETWEEN_LOOKS:
        _LAST_CARD_LOOK[c.id] = turns
        jobs.append({
            "job": "cards", "campaign": c.id, "turn": len(c.transcript),
            "cards": [{"id": k.id, "title": k.title, "facts": list(k.facts),
                       "stage": k.stage, "clock": k.clock, "secret": k.secret,
                       "people": [c.scene.actors[r].name if r in c.scene.actors else r
                                  for r in k.people]}
                      for k in live],
            "refs": {r: a.name for r, a in c.scene.actors.items() if not a.is_pc},
            "recent": [f"{b.get('who', '?')}: {str(b.get('text', ''))[:400]}"
                       for b in c.transcript[-8:]],
            "known": frozenset(known),
        })
    return jobs


def _down(a) -> bool:
    """The loot op's own test: only the down and the dead.

    It said so and was not: this asked one literal key, and measured at positive hit
    points it disagreed with the loot op on five of the six members of the family — dead,
    dying, helpless, petrified and stable — so a creature killed by Constitution damage
    at full health was never offered for looting, though the loot op would have stripped
    it happily.

    Both ask `Actor.is_down` now. They previously spelled it `hp <= 0 or state.down`,
    which is the same question except at exactly 0 hit points — where the creature is
    *disabled*: conscious, upright and taking turns, and being offered for looting.
    """
    return a.is_down


def _belongings(a) -> dict:
    """What the body carries, exactly. Compared wholesale at apply time: if one coin
    has moved since the proposal was made, somebody got there first and the garnish is
    dropped."""
    return {"weapons": list(a.weapons), "armour": str(a.armour or "none"),
            "purse": dict(a.purse), "inventory": dict(a.inventory),
            "stock": sorted(a.stock)}


def _carries_anything(snapshot: dict) -> bool:
    """A body spawned penniless was spawned penniless on purpose — `_assemble_kit`
    skips animals — and a wolf does not keep a locket in its fur."""
    return bool([w for w in snapshot["weapons"] if w and w != "unarmed"]
                or snapshot["armour"] != "none"
                or snapshot["purse"] or snapshot["inventory"] or snapshot["stock"])


def _fresh_corpse(c):
    """The newest down-and-not-yet-garnished body, or None. Newest by ref — encounter
    refs count up, so the highest c-number is the most recent arrival."""
    candidates = []
    for ref, a in c.scene.actors.items():
        if a.is_pc or not _down(a) or (c.id, ref) in _GARNISHED:
            continue
        if not _carries_anything(_belongings(a)):
            continue
        if any(getattr(s, "kind", "") == "trinket" for s in a.stock.values()):
            continue                     # garnished in a previous process
        candidates.append(ref)
    if not candidates:
        return None
    return max(candidates, key=lambda r: int(re.sub(r"\D", "", r) or 0))


def _known(c) -> set[str]:
    """Every name the watcher's output may use — the GM's own entitlement list."""
    from .agent import GMAgent

    try:
        return GMAgent(c.world, c.engine())._known_names()
    except Exception:
        return set()


def _note_content(c) -> str:
    """The GM's private note as it sits in history, verbatim, or ""."""
    i = _find_note(c.history)
    return str(c.history[i].get("content", "")) if i >= 0 else ""


def _find_note(history) -> int:
    from play import opening

    for i, m in enumerate(history or []):
        if str(m.get("content", "")).startswith(opening.NOTE_PREFIX):
            return i
    return -1


# --- the worker: model calls only, never the campaign ----------------------------------

def _work(jobs: list[dict]) -> None:
    """Run each job's model call and park what survives validation. Any failure —
    Ollama down, schema refused, junk reply — is silently nothing, the same rule as
    the narrator fallbacks: the watcher is garnish on a game that works without it."""
    from play import modelcfg

    try:
        cfg = modelcfg.for_role("watcher")
    except Exception:
        return
    for job in jobs:
        try:
            proposal = (_propose_garnish(job, cfg) if job["job"] == "garnish"
                        else _propose_cards(job, cfg) if job["job"] == "cards"
                        else _propose_undercurrent(job, cfg))
        except Exception:
            proposal = None
        if proposal:
            with _LOCK:
                _PENDING.append(proposal)


def _ask(messages: list[dict], cfg: dict, schema: dict,
         prefer_thinking: bool = False):
    """One model call, two attempts, thinking toggled between them.

    Measured live on deepseek-r1:8b: the garnish call died three of three times with
    thinking on — the ENTIRE budget went into Ollama's `thinking` channel (900 and
    2,000 tokens both ended `done_reason=length`, content "") because the format
    grammar constrains only the content, which never began; with `think=False` the
    same call answered a clean object in 0.4s. The undercurrent call, by contrast,
    succeeded two of two *with* thinking and its rewrites were better grounded in the
    transcript than the unthinking one's. So each job leads with what worked for it
    and retries the other way — which is also the attempt a watcher model that
    refuses or ignores the `think` key converges onto.
    """
    order = (None, False) if prefer_thinking else (False, None)
    for n, think in enumerate(order):
        try:
            reply = client.chat(
                messages, cfg["model"], cfg.get("host", "http://localhost:11434"),
                as_json=True, provider=cfg.get("provider", "ollama"),
                api_key=cfg.get("api_key", ""),
                temperature=0.4, num_predict=900,
                schema=schema, think=think)
            return reply.json()
        except (ValueError, client.ModelUnavailable):
            if n:
                raise


_SYSTEM = ("You are the event watcher for a Pathfinder game: you read what happened "
           "and decide one small thing. You answer only with the JSON asked for.")


def _propose_garnish(job: dict, cfg: dict) -> dict | None:
    thread = job.get("thread", "")
    note_line = (f"The campaign's hidden thread, which the player does not know: "
                 f"{thread}\n" if thread else "")
    data = _ask(
        [{"role": "system", "content": _SYSTEM},
         {"role": "user", "content":
             f"{job['who']} has just been killed. Present in the scene: "
             f"{', '.join(job['cast'])}.\n{note_line}"
             f"Name ONE small personal item found on the body — a keepsake, a note, a "
             f"key, a token. If the hidden thread fits, the item may quietly echo it. "
             f"Use no name of a person or place that does not already appear above.\n"
             f'Answer JSON: {{"item": "a short item name", "band": "worthless" | '
             f'"modest" | "fine"}} — band is what a market stall would pay.'}],
        cfg,
        {"type": "object",
         "properties": {"item": {"type": "string", "maxLength": 80},
                        "band": {"type": "string",
                                 "enum": sorted(BANDS)}},
         "required": ["item", "band"]})
    apply = _valid_garnish(data, job["known"])
    if apply is None:
        return None
    return {"job": "garnish", "campaign": job["campaign"], "ref": job["ref"],
            "who": job["who"], "snapshot": job["snapshot"], "apply": apply}


def _valid_garnish(data: dict, known) -> dict | None:
    """Detect mechanically. The model's answer becomes state only through here."""
    item = " ".join(str(data.get("item", "")).split()).strip(" .\"'")
    band = str(data.get("band", "")).strip().lower()
    if band not in BANDS:
        return None
    if not (3 <= len(item) <= 60) or item.lower() in ("none", "nothing"):
        return None
    # "Carried: " in front so no token sits sentence-initial, where the invented-name
    # check deliberately looks away.
    if narration_mod.invented_names(f"Carried: {item}.", set(known)):
        return None
    table = _table_id(item)
    if table:
        return {"kind": "table", "id": table}
    return {"kind": "trinket", "name": item, "band": band}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")


_TABLE: dict[str, str] | None = None


def _table_id(item: str) -> str:
    """The catalogue id this item already is, or "". Matched by id and by display
    name, because the model says "Woundwort" and the shelf files it under an id."""
    global _TABLE
    if _TABLE is None:
        found: dict[str, str] = {}
        try:
            from rules import ingredients as ing_mod

            for iid, ing in ing_mod.all_ingredients().items():
                found[_slug(iid)] = iid
                found[_slug(getattr(ing, "name", ""))] = iid
        except Exception:
            pass
        try:
            from rules import market as market_mod

            for m in market_mod.everything_priced():
                mid = str(getattr(m, "id", ""))
                if mid:
                    found[_slug(mid)] = mid
                    found[_slug(getattr(m, "name", ""))] = mid
        except Exception:
            pass
        found.pop("", None)
        _TABLE = found
    return _TABLE.get(_slug(item), "")


def _propose_undercurrent(job: dict, cfg: dict) -> dict | None:
    thread = job.get("thread", "")
    hooks = "".join(f"- {h}\n" for h in job.get("hooks", []))
    data = _ask(
        [{"role": "system", "content": _SYSTEM},
         {"role": "user", "content":
             (f"The campaign's hidden thread, known only to the GM: {thread}\n"
              if thread else "The campaign has no hidden thread yet.\n")
             + "What has happened at the table recently:\n"
             + "".join(f"{line}\n" for line in job.get("recent", []))
             + "\nDecide what the hidden thread should do next:\n"
               '- "keep": it is fine as it stands. This is the usual answer.\n'
               '- "advance": play has touched it; rewrite it one small step further '
               "along.\n"
               '- "new": it has clearly resolved on stage; replace it.\n'
             + (f"When writing a new thread, prefer one of the world's own unused "
                f"hooks:\n{hooks}" if hooks else "")
             + "Rules: the sentence is ONE sentence, and uses no name that does not "
               "already appear above.\n"
               'Answer JSON: {"action": "keep" | "advance" | "new", "sentence": '
               '"the whole rewritten thread, or empty for keep"}'}],
        cfg,
        prefer_thinking=True,
        schema={"type": "object",
         "properties": {"action": {"type": "string",
                                   "enum": ["keep", "advance", "new"]},
                        "sentence": {"type": "string", "maxLength": 300}},
         "required": ["action", "sentence"]})
    sentence = _valid_thread(data, job["known"])
    if sentence is None:
        return None
    return {"job": "undercurrent", "campaign": job["campaign"],
            "was": job["was"], "sentence": sentence,
            # Whether the old thread was concluded or only moved: the story award
            # (`Engine.award_story`) pays the two differently.
            "action": str(data.get("action", "")).strip().lower(),
            "thread": thread}


# --- the situation cards: what moved, in one sentence each ------------------------------

FACT_LEN = (15, 220)
TITLE_LEN = (8, 70)


def _propose_cards(job: dict, cfg: dict) -> dict | None:
    """Read the last few beats against the live cards and say what moved.

    Per card: keep (the usual answer), advance with ONE new fact, or resolve. At most
    one new card, for a situation that has plainly arisen and is on no card. Every
    fact is a sentence in the world's own terms; a fact that names a stranger, or
    carries a number, is refused here and never reaches the table.
    """
    deck = "".join(
        f"- [{k['id']}] {k['title']} ({k['stage']}, clock {k['clock']})"
        + (f"; with {', '.join(k['people'])}" if k["people"] else "") + "\n"
        + "".join(f"    - {f}\n" for f in k["facts"])
        for k in job.get("cards", []))
    people = "".join(f"- {r}: {n}\n" for r, n in (job.get("refs") or {}).items())
    data = _ask(
        [{"role": "system", "content": _SYSTEM},
         {"role": "user", "content":
             "The situation cards on the table (facts the engine keeps):\n" + deck
             + "\nThe people on the board, by ref:\n" + (people or "- nobody\n")
             + "\nWhat has happened at the table recently:\n"
             + "".join(f"{line}\n" for line in job.get("recent", []))
             + "\nFor each card decide:\n"
               '- "keep": nothing on it moved. This is the usual answer.\n'
               '- "advance": play touched it; give ONE new fact, one sentence, what is '
               "now true that was not.\n"
               '- "resolve": it is plainly settled on stage.\n'
               "And if a situation has plainly arisen that is on no card, propose one "
               "new card: a title and one to three facts, naming its people by ref. "
               "Otherwise leave it null.\n"
               "Rules: facts are one sentence each, no numbers, and use no name that "
               "does not already appear above.\n"
               'Answer JSON: {"changes": [{"id": "...", "action": "keep" | "advance" | '
               '"resolve", "fact": "..."}], "new": {"title": "...", "facts": ["..."], '
               '"people": ["c1"]} | null}'}],
        cfg,
        prefer_thinking=True,
        schema={"type": "object",
                "properties": {
                    "changes": {"type": "array", "items": {
                        "type": "object",
                        "properties": {"id": {"type": "string"},
                                       "action": {"type": "string",
                                                  "enum": ["keep", "advance", "resolve"]},
                                       "fact": {"type": "string", "maxLength": 240}},
                        "required": ["id", "action", "fact"]}},
                    "new": {"type": ["object", "null"],
                            "properties": {"title": {"type": "string", "maxLength": 80},
                                           "facts": {"type": "array",
                                                     "items": {"type": "string",
                                                               "maxLength": 240}},
                                           "people": {"type": "array",
                                                      "items": {"type": "string"}}},
                            "required": ["title", "facts", "people"]}},
                "required": ["changes", "new"]})
    if not isinstance(data, dict):
        return None
    known = job["known"]
    ids = {k["id"]: k for k in job.get("cards", [])}
    said = {w.lower() for line in job.get("recent", [])
            for w in re.findall(r"[A-Za-z][A-Za-z'-]+", line) if w[:1].islower()}
    changes = []
    for ch in data.get("changes") or []:
        if not isinstance(ch, dict) or str(ch.get("id", "")) not in ids:
            continue
        action = str(ch.get("action", "")).strip().lower()
        was = (ids[ch["id"]]["stage"], ids[ch["id"]]["clock"])
        if action == "advance":
            fact = _valid_fact(ch.get("fact", ""), known)
            if fact is None:
                continue
            changes.append({"id": ch["id"], "action": "advance", "fact": fact, "was": was})
        elif action == "resolve":
            changes.append({"id": ch["id"], "action": "resolve", "fact": "", "was": was})
    new = None
    raw = data.get("new")
    if isinstance(raw, dict):
        title = " ".join(str(raw.get("title", "")).split()).rstrip(".")
        facts = [f for f in (_valid_fact(x, known, strict=True, said=said)
                             for x in (raw.get("facts") or [])[:3]) if f]
        refs = [str(r) for r in (raw.get("people") or [])
                if str(r) in (job.get("refs") or {})]
        titles = {k["title"].lower() for k in job.get("cards", [])}
        if (TITLE_LEN[0] <= len(title) <= TITLE_LEN[1] and facts
                and title.lower() not in titles
                and _valid_fact(title + ".", known, strict=True, said=said) is not None
                and not re.search(r"[0-9]", title)):
            new = {"title": title, "facts": facts, "people": refs}
    if not changes and new is None:
        return None
    return {"job": "cards", "campaign": job["campaign"], "turn": job.get("turn", 0),
            "changes": changes, "new": new}


def _valid_fact(text, known, strict: bool = False, said: set | None = None) -> str | None:
    """One sentence, in bounds, no digits, no stranger — or None.

    `strict` keeps the leading word capitalised for the stranger check: a NEW card
    names its subject first ("Kaida's debt"), so the lower-casing trade below is
    wrong for it — unless the leading word was `said` at the table as a plain word
    ("work", in "I ask her for a day's work"), in which case "Work at the stall" is
    a title and not a person. A card may be titled only with words that were said
    or names the world knows."""
    s = " ".join(str(text or "").split())
    if not (FACT_LEN[0] <= len(s) <= FACT_LEN[1]):
        return None
    if not s.endswith((".", "!", "?")):
        s += "."
    if re.search(r"[.!?] ", s):
        return None                       # one sentence means one
    if re.search(r"[0-9]", s):
        return None                       # no model authors a number
    # The first word lower-cased before the check, unlike the undercurrent's: a card
    # fact is a plain sentence and "Work is scarce." is not somebody called Work.
    # The trade is a stranger who leads the sentence slipping through here; the
    # people on a card are refs, and the page's own un-namer still stands.
    lead = re.sub(r"['’]s$", "", s.split()[0].lower()) if s.split() else ""
    soften = (not strict) or (lead in (said or set()))
    head = s[:1].lower() + s[1:] if soften else s
    if narration_mod.invented_names(f"They say: {head}", set(known)):
        return None
    return s


def _valid_thread(data: dict, known) -> str | None:
    if str(data.get("action", "")).strip().lower() not in ("advance", "new"):
        return None
    s = " ".join(str(data.get("sentence", "")).split())
    if not (20 <= len(s) <= 300):
        return None
    if not s.endswith((".", "!", "?")):
        s += "."
    if re.search(r"[.!?]\s", s):
        return None                       # one sentence means one
    # "They say: " for the same sentence-initial blind spot as the garnish check.
    if narration_mod.invented_names(f"They say: {s}", set(known)):
        return None
    return s


# --- drain: apply what still holds, in the next request's thread -----------------------

def drain(c) -> bool:
    """Apply this campaign's pending proposals against the live state. Anything the
    world has moved out from under is dropped without a word. Saves if it changed."""
    with _LOCK:
        take = [p for p in _PENDING if p.get("campaign") == c.id]
        for p in take:
            _PENDING.remove(p)
    changed = False
    for p in take:
        try:
            if p["job"] == "garnish":
                changed = _apply_garnish(c, p) or changed
            elif p["job"] == "cards":
                changed = _apply_cards(c, p) or changed
            else:
                changed = _apply_undercurrent(c, p) or changed
        except Exception:
            continue                      # a broken proposal must never cost a turn
    if changed:
        c.save()
    return changed


def _apply_garnish(c, p: dict) -> bool:
    a = c.scene.actors.get(p["ref"])
    if a is None or a.is_pc or a.name != p["who"] or not _down(a):
        return False                      # gone, replaced, or back on their feet
    if _belongings(a) != p["snapshot"]:
        return False                      # somebody's hands got there first
    if p["apply"]["kind"] == "table":
        a.carry(p["apply"]["id"], 1)
        label = p["apply"]["id"]
    else:
        from rules.crafting import Stock

        item = Stock(base=p["apply"]["name"], tier=BANDS[p["apply"]["band"]],
                     kind="trinket", craft="trinket",
                     # The maker has said: not drunk, not thrown, not smeared on a
                     # blade. A non-empty `how` is how a Stock says so outright.
                     how=["keep"])
        a.add_stock(item, 1)
        label = item.name
    # Auditable, like everything else that moves state — the background loop must be
    # legible. The player-visible log strips this to nothing (no player rolls in it).
    c.turn_log.append({"kind": "watcher", "did": "garnish",
                       "ref": p["ref"], "item": label})
    return True


def _apply_cards(c, p: dict) -> bool:
    """Land the card proposals that still hold. A card the engine moved since the
    model read it — a different stage or clock — is left alone: the tell that moved
    it is the truer fact, and the model's was written against a table that is gone."""
    from rules import cards as cards_mod

    turn = len(c.transcript)
    changed = False
    lines: list[str] = []
    engine = None
    for ch in p.get("changes") or []:
        card = cards_mod.find(c.scene, ch["id"])
        if card is None or not card.live:
            continue
        if tuple(ch.get("was") or ()) != (card.stage, card.clock):
            continue
        if ch["action"] == "advance":
            cards_mod.touch(c.scene, card.id, ch["fact"], turn=turn, tick=True)
            c.turn_log.append({"kind": "watcher", "did": "card", "card": card.id,
                               "action": "advance", "fact": ch["fact"]})
            changed = True
        elif ch["action"] == "resolve":
            cards_mod.resolve(c.scene, card.id, turn=turn)
            c.turn_log.append({"kind": "watcher", "did": "card", "card": card.id,
                               "action": "resolve"})
            changed = True
        after = cards_mod.find(c.scene, card.id)
        if after is not None and after.stage == "resolved":
            # Resolving a situation pays: half a fight, the story award's "advance"
            # share, on its own line — "i should be receiving EXP for ... resolving
            # situations". Whether the model said resolve or an advance filled the
            # clock.
            engine = engine or c.engine()
            line = engine.award_story("advance", card.title).strip()
            if line:
                lines.append(line)
    new = p.get("new")
    if isinstance(new, dict) and new.get("title"):
        existing = {k.title.lower() for k in cards_mod.load(c.scene)}
        if new["title"].lower() not in existing:
            n = sum(1 for k in cards_mod.load(c.scene) if k.id.startswith("play-")) + 1
            people = [r for r in new.get("people") or [] if r in c.scene.actors]
            cards_mod.open_card(c.scene, cards_mod.Card(
                id=f"play-{n}", title=new["title"], facts=list(new["facts"]),
                tags=(cards_mod.TAG_PLAY,), people=people, place=str(c.scene.at or ""),
                origin="watcher"), turn=turn)
            c.turn_log.append({"kind": "watcher", "did": "card", "card": f"play-{n}",
                               "action": "new", "title": new["title"]})
            changed = True
    for line in lines:
        c.transcript.append({"who": "gm", "text": line, "kind": "setup"})
        c.turn_log.append({"kind": "watcher", "did": "story_award", "line": line})
    return changed


def _apply_undercurrent(c, p: dict) -> bool:
    from play import opening

    i = _find_note(c.history)
    if p["was"]:
        if i < 0 or str(c.history[i].get("content", "")) != p["was"]:
            return False                  # the note moved since the model read it
        c.history[i] = {"role": "user",
                        "content": opening.private_note(p["sentence"])}
    else:
        if i >= 0:
            return False                  # a note appeared; never write a second
        c.history.append({"role": "user",
                          "content": opening.private_note(p["sentence"])})
    c.turn_log.append({"kind": "watcher", "did": "undercurrent",
                       "note": p["sentence"]})
    # Resolving a situation pays. The CRB's story award — double a CR-equal-to-level
    # fight for a storyline concluded, and half of one here for a storyline moved —
    # lands as its own line on the page, since the watcher writes between turns and
    # has no beat to ride on. "i should be receiving EXP for ... resolving situations".
    line = c.engine().award_story(p.get("action", ""), p.get("thread", "")).strip()
    if line:
        c.transcript.append({"who": "gm", "text": line, "kind": "setup"})
        c.turn_log.append({"kind": "watcher", "did": "story_award", "line": line})
    return True

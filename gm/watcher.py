"""The event watcher, wired to something at last.

The "watcher" model role has been configured since the roles existed — deepseek-r1:8b
then, chosen because a reasoning model suits reading a record and drawing a conclusion,
and the narrator's own model since 2026-08-28 (`settings.MODELS` says why) — and it had
ZERO call sites. `settings.py` said so out loud: "a model that is never loaded
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

import json
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
# How many cards, and how many people by ref, one look at the cards is shown (`_jobs_for`).
MAX_CARDS = 8
MAX_REFS = 24
# The longest undercurrent sentence kept (`_valid_thread`). The schema allows a little
# more, so a sentence the grammar cut at its cap is refused rather than kept cut.
THREAD_LEN = 300

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
            # Bounded like the cards' refs below: everybody shown is an actor for good.
            "cast": [x.name for x in c.scene.actors.values() if x.name][-MAX_REFS:],
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
        # Bounded, both lists: every live card and every actor on the board went in, and
        # neither stops growing in a long campaign (a card keeps FACT_CAP facts, but the
        # cards themselves have no cap, and everybody the narration shows is an actor and
        # stays one). The prompt is one user message, and one message too long for the
        # window is the case Ollama answers by keeping about half of it (8,195 tokens of
        # a 16,384 window, measured 2026-10-08; the player's log has a call of exactly
        # that count). The cards touched most recently, and the people on them first.
        live = sorted(live, key=lambda k: -int(getattr(k, "touched", 0) or 0))[:MAX_CARDS]
        on_cards = [r for k in live for r in k.people if r in c.scene.actors]
        others = [r for r, a in c.scene.actors.items() if not a.is_pc]
        refs = list(dict.fromkeys(on_cards + others))[:MAX_REFS]
        jobs.append({
            "job": "cards", "campaign": c.id, "turn": len(c.transcript),
            "cards": [{"id": k.id, "title": k.title, "facts": list(k.facts),
                       "kind": k.kind, "objectives": [dict(o) for o in k.objectives],
                       "stage": k.stage, "clock": k.clock, "secret": k.secret,
                       "people": [c.scene.actors[r].name if r in c.scene.actors else r
                                  for r in k.people]}
                      for k in live],
            "refs": {r: c.scene.actors[r].name for r in refs
                     if not c.scene.actors[r].is_pc},
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

    Both ask `Actor.lootable` since 2026-09-25, when helpless left the down family and
    the loot op had to name it: one owner, so the two cannot drift again.
    """
    return a.lootable


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


class RanAway(ValueError):
    """The answer reached its token cap (`done_reason=length`). Not retried: the cap is
    sized to the largest answer the schema allows, so a reply that reaches it is writing
    something else (thinking, or whitespace between JSON tokens, which a JSON grammar
    permits without end), and the same call would do it again."""


# Tokens per character of a JSON answer, at the worst. JSON is punctuation-heavy and
# tokenises worse than prose: the probes of 2026-10-08 answered 134 characters in 40
# tokens and 48 characters in 18 (3.4 and 2.7 characters a token). Two characters a
# token, plus room for the braces and keys, is a cap no valid answer reaches.
_ANSWER_CHARS_PER_TOKEN = 2.0
_ANSWER_SLACK = 48
UNBOUNDED_ANSWER_TOKENS = 900


def answer_tokens(max_chars: int) -> int:
    """num_predict for an answer of at most `max_chars` characters."""
    return int(max_chars / _ANSWER_CHARS_PER_TOKEN) + _ANSWER_SLACK


# Room a model's own layout takes around one value or member: a newline, an indent, the
# comma and the space after the colon.
_LAYOUT = 8


def max_answer_chars(node: dict) -> int | None:
    """The longest JSON text `node` (a JSON schema) admits, or None when nothing bounds
    it (a string with no maxLength, an array with no maxItems).

    Read from the schema the call sends, so the cap and the schema cannot drift apart.
    It is a real bound only because Ollama enforces the bounds: probed 2026-10-08 on the
    shipped model, `maxLength: 40` held 3 of 3 (each string stopped at exactly 40
    characters, mid-word) and `maxItems: 2` held 3 of 3, as `enum` and `required` already
    had (0 of 6 for `contains`/`prefixItems`, which nothing here uses). A string is
    counted with a tenth more for escapes."""
    if not isinstance(node, dict):
        return None
    if "enum" in node:
        return max((len(json.dumps(v)) for v in node["enum"]), default=4)
    kinds = node.get("type")
    best = 0
    for kind in (kinds if isinstance(kinds, list) else [kinds]):
        if kind == "string":
            cap = node.get("maxLength")
            if cap is None:
                return None
            size = int(cap) + int(cap) // 10 + 2
        elif kind in ("integer", "number"):
            size = 12
        elif kind in ("boolean", "null"):
            size = 5
        elif kind == "array":
            cap, item = node.get("maxItems"), max_answer_chars(node.get("items") or {})
            if cap is None or item is None:
                return None
            size = 2 + int(cap) * (item + _LAYOUT)
        elif kind == "object":
            size = 2
            for key, sub in (node.get("properties") or {}).items():
                inner = max_answer_chars(sub)
                if inner is None:
                    return None
                size += len(json.dumps(key)) + 1 + inner + _LAYOUT
        else:
            return None
        best = max(best, size)
    return best


def _ask(messages: list[dict], cfg: dict, schema: dict):
    """One model call with thinking off, capped at what the largest valid answer needs.

    Measured 2026-10-08 on igorls/gemma-4-12B-it-heretic, the shipped watcher model, with
    the real prompts (scratchpad probe, two runs each): with `think` unsent, the cards and
    undercurrent calls spent all 900 tokens in Ollama's thinking channel, 4 of 4 —
    `done_reason=length`, 3,220 to 3,670 characters of thinking, content "" — in 19 to
    21 s, and were then retried. With `think=False` the same calls answered in 35 to 43
    tokens, `done_reason=stop`, 4 of 4, in 4 to 10 s. The player's log has the first half
    of that: four watcher calls at the 900-token cap on prompts of 824 to 844 tokens.

    It led with thinking for the cards and the undercurrent because deepseek-r1:8b, the
    watcher's model before 2026-08-28, wrote better-grounded undercurrent rewrites with
    it (two of two). That model is not the watcher now; Gemma 4 thinks by default, and
    `settings.MODELS` already rides `think=False` on every agent call for that reason.

    So: `think=False` first, always. A model that refuses the key (Ollama answers 400 for
    a model with no thinking to switch off, which reaches here as `ModelUnavailable`) is
    asked once more without it. A reply cut at its cap is `RanAway` and is NOT retried —
    it was retried before, which is how one look cost two full-length calls. The cap is
    the longest answer the schema allows (`max_answer_chars`), in tokens; a schema with
    no bound anywhere keeps the old 900.
    """
    longest = max_answer_chars(schema)
    num_predict = answer_tokens(longest) if longest is not None else UNBOUNDED_ANSWER_TOKENS
    reply = None
    for think in (False, None):
        try:
            reply = client.chat(
                messages, cfg["model"], cfg.get("host", "http://localhost:11434"),
                as_json=True, provider=cfg.get("provider", "ollama"),
                api_key=cfg.get("api_key", ""),
                temperature=0.4, num_predict=num_predict,
                schema=schema, think=think)
            break
        except client.ModelStalled:
            raise                          # a wedged Ollama is not asked twice
        except client.ModelUnavailable:
            if think is None:
                raise
    if reply.cut_off:
        raise RanAway(f"the answer reached its {num_predict}-token cap "
                      f"({reply.reply_tokens} tokens) and was not finished")
    return reply.json()


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
        # 80 against `_valid_garnish`'s 60: a name the grammar cut at its cap is
        # always refused, never kept half-written.
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
        # 320 against `_valid_thread`'s 300: it was 300 for both, so a sentence the
        # grammar cut mid-word at its cap was exactly long enough to be kept.
        schema={"type": "object",
         "properties": {"action": {"type": "string",
                                   "enum": ["keep", "advance", "new"]},
                        "sentence": {"type": "string", "maxLength": THREAD_LEN + 20}},
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
# The words a title may use without having been said: the small grammar of titles.
_TITLE_WORDS = frozenset({
    "the", "a", "an", "of", "and", "or", "for", "to", "in", "at", "on", "with", "from",
    "by", "into", "over", "under", "about", "task", "job", "work", "debt", "favour",
    "favor", "matter", "trouble", "question", "price", "deal", "bargain", "errand",
    "delivery", "search", "hunt", "watch", "wait", "missing", "lost", "stolen", "owed",
    "unpaid", "promise", "promised", "secret", "warning", "threat", "offer", "request",
    "who", "what", "where", "why", "how", "is", "are", "was", "has", "have", "not", "no",
})


def cards_schema(job: dict) -> dict:
    """The shape of a look at the cards, with every list and string bounded.

    It had none of the list bounds: `changes` could hold any number of entries naming any
    id, and a new card any number of facts and people, so the only cap on the answer was
    the token cap. Bounded now by what the job holds: one change per card shown, an id
    from those cards, an objective number a card has, at most three facts (all
    `_propose_cards` keeps), people from the refs shown. Ollama enforces `enum` and
    `maxItems` (`max_answer_chars` says what was probed), so the longest answer is
    known and the call's token cap is sized from it. The string caps sit above the
    validators' (FACT_LEN, TITLE_LEN), so a string the grammar cut is refused, not kept.
    """
    cards = job.get("cards") or []
    ids = [k["id"] for k in cards] or [""]
    most = max([len(k.get("objectives") or []) for k in cards] + [1])
    refs = list(job.get("refs") or {})
    people = ({"type": "array", "maxItems": min(len(refs), 6),
               "items": {"type": "string", "enum": refs}} if refs
              else {"type": "array", "maxItems": 0, "items": {"type": "string",
                                                               "maxLength": 1}})
    return {"type": "object",
            "properties": {
                "changes": {"type": "array", "maxItems": max(1, len(cards)), "items": {
                    "type": "object",
                    "properties": {"id": {"type": "string", "enum": ids},
                                   "action": {"type": "string",
                                              "enum": ["keep", "advance", "resolve",
                                                       "objective"]},
                                   "objective": {"type": "integer",
                                                 "enum": list(range(1, most + 1))},
                                   "fact": {"type": "string",
                                            "maxLength": FACT_LEN[1] + 20}},
                    "required": ["id", "action", "fact"]}},
                "new": {"type": ["object", "null"],
                        "properties": {"title": {"type": "string",
                                                 "maxLength": TITLE_LEN[1] + 10},
                                       "facts": {"type": "array", "maxItems": 3,
                                                 "items": {"type": "string",
                                                           "maxLength": FACT_LEN[1] + 20}},
                                       "people": people},
                        "required": ["title", "facts", "people"]}},
            "required": ["changes", "new"]}


def _propose_cards(job: dict, cfg: dict) -> dict | None:
    """Read the last few beats against the live cards and say what moved.

    Per card: keep (the usual answer), advance with ONE new fact, or resolve. At most
    one new card, for a situation that has plainly arisen and is on no card. Every
    fact is a sentence in the world's own terms; a fact that names a stranger, or
    carries a number, is refused here and never reaches the table.
    """
    deck = "".join(
        f"- [{k['id']}] {'QUEST: ' if k.get('kind') == 'quest' else ''}{k['title']} "
        f"({k['stage']}, clock {k['clock']})"
        + (f"; with {', '.join(k['people'])}" if k["people"] else "") + "\n"
        + "".join(f"    [{'x' if o.get('done') else ' '}] objective {i + 1}: {o.get('text', '')}\n"
                  for i, o in enumerate(k.get("objectives") or []))
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
               '- "objective": on a QUEST card, one of its objectives was plainly '
               'done on stage; give its number and, as the fact, what was done.\n'
               "And if a situation has plainly arisen that is on no card, propose one "
               "new card: a title and one to three facts, naming its people by ref. "
               "Otherwise leave it null.\n"
               "Rules: facts are one sentence each, no numbers, and use no name that "
               "does not already appear above.\n"
               'Answer JSON: {"changes": [{"id": "...", "action": "keep" | "advance" | '
               '"resolve" | "objective", "objective": 1, "fact": "..."}], '
               '"new": {"title": "...", "facts": ["..."], '
               '"people": ["c1"]} | null}'}],
        cfg,
        schema=cards_schema(job))
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
        elif action == "objective" and ids[ch["id"]].get("kind") == "quest":
            try:
                n = int(ch.get("objective") or 0)
            except (TypeError, ValueError):
                n = 0
            objs = ids[ch["id"]].get("objectives") or []
            if 1 <= n <= len(objs) and not objs[n - 1].get("done"):
                fact = _valid_fact(ch.get("fact", ""), known) or ""
                changes.append({"id": ch["id"], "action": "objective", "objective": n,
                                "fact": fact, "was": was})
    new = None
    raw = data.get("new")
    if isinstance(raw, dict):
        title = " ".join(str(raw.get("title", "")).split()).rstrip(".")
        facts = [f for f in (_valid_fact(x, known, strict=True, said=said)
                             for x in (raw.get("facts") or [])[:3]) if f]
        refs = [str(r) for r in (raw.get("people") or [])
                if str(r) in (job.get("refs") or {})]
        titles = {k["title"].lower() for k in job.get("cards", [])}
        # A card may be titled only with words that were said at the table or names
        # the world knows. Measured on the first live proposal: "The Warehouse Task",
        # in Title Case as models write titles, was refused by the stranger check for
        # "Warehouse" and "Task" — and "warehouse" was the prose's own word.
        heard = {w.lower() for line in job.get("recent", [])
                 for w in re.findall(r"[A-Za-z][A-Za-z'-]+", line)}
        heard |= {w.lower() for name in known for w in re.findall(r"[A-Za-z][A-Za-z'-]+", name)}
        heard |= {w.lower() for k in job.get("cards", [])
                  for w in re.findall(r"[A-Za-z][A-Za-z'-]+", k["title"] + " " + " ".join(k["facts"]))}
        words = [re.sub(r"['’]s$", "", w.lower()) for w in re.findall(r"[A-Za-z][A-Za-z'-]+", title)]
        if (TITLE_LEN[0] <= len(title) <= TITLE_LEN[1] and facts
                and title.lower() not in titles
                and words and all(w in heard or w in _TITLE_WORDS for w in words)
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
    if not (20 <= len(s) <= THREAD_LEN):
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
            # The fact has to be ABOUT the card: one of its identity words or one of
            # its people in the sentence. Measured 2026-09-18: a town's water-rights
            # strain card was advanced from inside a brothel on "the current
            # transaction is a private matter", and again on "the warrior's blade is
            # shattered", and paid 200 XP each time. A watcher that can advance any card
            # on any sentence is a card that advances every turn.
            # The test lives in `cards.about`, which also knows an errand's need: "he
            # considers the offer of work" was refused for "Find a bed you can pay for"
            # while the player's purse was empty (2026-10-03, item 25).
            fact = str(ch.get("fact") or "")
            if not cards_mod.about(card, fact, c.scene):
                c.turn_log.append({"kind": "watcher", "did": "card", "card": card.id,
                                   "action": "refused", "fact": fact[:200],
                                   "why": "the fact is not about this card"})
                continue
            cards_mod.touch(c.scene, card.id, ch["fact"], turn=turn, tick=True)
            c.turn_log.append({"kind": "watcher", "did": "card", "card": card.id,
                               "action": "advance", "fact": ch["fact"]})
            changed = True
        elif ch["action"] == "resolve":
            cards_mod.resolve(c.scene, card.id, turn=turn)
            c.turn_log.append({"kind": "watcher", "did": "card", "card": card.id,
                               "action": "resolve"})
            changed = True
        elif ch["action"] == "objective":
            # A quest's objective seen done on stage. The engine ticks it, and the
            # story award for the finished quest is paid below like any resolve.
            done = cards_mod.objective_done(c.scene, card.id, int(ch["objective"]) - 1,
                                            note=ch.get("fact", ""), turn=turn)
            if done is not None:
                c.turn_log.append({"kind": "watcher", "did": "card", "card": card.id,
                                   "action": "objective", "objective": ch["objective"]})
                changed = True
        after = cards_mod.find(c.scene, card.id)
        if after is not None and after.stage == "resolved":
            # Resolving a situation pays: half a fight, the story award's "advance"
            # share, on its own line — "i should be receiving EXP for ... resolving
            # situations". Whether the model said resolve or an advance filled the
            # clock.
            engine = engine or c.engine()
            line = engine.award_story("new" if after.kind == "quest" else "advance",
                                      card.title).strip()
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
        # An engine line, not narration: "consequence", like every other award and tell
        # `play/views.py` appends. Measured 2026-09-17 on the first sixty-turn audit
        # after the narrator guards: filed as "setup", the award — "You gain 200 XP for
        # moving a matter along: …" — was handed to the next prose call as "what you
        # narrated just before this", opened four of the last nineteen beats in that
        # register, and was the single largest phrase repeating across the run (seven
        # beats). The narrator's own prose, measured apart from it, had improved.
        c.transcript.append({"who": "gm", "text": line, "kind": "consequence"})
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
        # An engine line, not narration: "consequence", like every other award and tell
        # `play/views.py` appends. Measured 2026-09-17 on the first sixty-turn audit
        # after the narrator guards: filed as "setup", the award — "You gain 200 XP for
        # moving a matter along: …" — was handed to the next prose call as "what you
        # narrated just before this", opened four of the last nineteen beats in that
        # register, and was the single largest phrase repeating across the run (seven
        # beats). The narrator's own prose, measured apart from it, had improved.
        c.transcript.append({"who": "gm", "text": line, "kind": "consequence"})
        c.turn_log.append({"kind": "watcher", "did": "story_award", "line": line})
    return True

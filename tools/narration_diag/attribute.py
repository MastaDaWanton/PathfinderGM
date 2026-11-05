"""Where each narration error was born: the blind scorers' errors traced, in code, to the
sentence, the slot, the writer and the cause, and the bench's numbers with their intervals.

    python tools/narration_diag/attribute.py report <key.json> <results.jsonl,...> \\
        <scoreA.txt,...> <scoreB.txt,...> [--json out.json]
    python tools/narration_diag/attribute.py writers <results.jsonl>...

`report` takes the key from blind.py, every results file the sheets were made from, and
each scorer's answer files (comma-separated, one scorer per argument). `writers` needs no
scorer: who wrote each sentence of every page, as shares.

How an error is placed (no model involved):
  1. its quote is found on its page, and the sentence holding it is taken;
  2. the sentence is matched against every answer the planned narrator's slots gave (first
     answers, re-asks with their named fault, the tells check's remakes and the engine line
     it falls back to), then against every text change the pipeline made (diagtrace.py:
     the innermost function that first put that sentence on the page), then against the
     raw replies of every other writing call (the enemy-turn narrator, the free narrator, a
     repair's own model call), then against the engine's tells;
  3. if a slot wrote the sentence and something edited it afterwards, the quoted words
     decide whose the error is: in the slot's own words, the slot's; not there, the editor's;
  4. the cause, for a model-written error: are the quote's content words in the slot's own
     instruction (the plan asked for it), in the tell it was given (the tell's wording), in
     the shared prompt (the scene, the last beat, the people), or in none of them (the
     narrator's own invention). An omission (E6): no slot carried the tell (the plan), a
     slot wrote it and a repair cut it, or the slot never wrote it.

Matching is by sentence similarity (difflib, 0.9 for "the same sentence"): the groom's
second-person swap and the destutter change a few characters, never most of a sentence."""
from __future__ import annotations

import json
import math
import random
import re
import sys
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

SAME = 0.9
STOP = set("""a an the and or but of to in on at by for with from into onto over under as is are
was were be been being it its it's this that these those there here you your yours he she they
them his her their him we our i my me not no so than then up out off down very just still
now one two all any some each who whom what which when where how while has have had do does did
will would can could may might must shall should s t""".split())

# The writing calls (diagtrace's `who`, first frame) and what they are, for a sentence no
# slot wrote. Readers and checks (beat_reader, beat_verify, interpret, means…) write nothing
# onto the page and are never a sentence's source.
_WRITERS = (
    ("agent.narrate_outcome", "model: enemy-turn / consequence beat"),
    ("agent._free_draft", "model: free narrator (planned failed)"),
    ("agent.narrate_turn", "model: free narrator (planned failed)"),
    ("agent._answer_the_question", "repair (model): asked-and-unanswered"),
    ("agent._show_declared", "repair (model): declared deed shown"),
    ("agent._show_blows", "repair (model): blow shown"),
    ("agent._undeclared_blows", "repair (model): undeclared blow"),
    ("agent._undeclared_arrivals", "repair (model): undeclared arrival"),
    ("agent._repair_", "repair (model): "),
    ("agent.polish", "repair (model): polish"),
    ("agent.npc_turn", "model: enemy-turn plan"),
)


def norm(s: str) -> str:
    s = str(s or "").replace("’", "'").replace("‘", "'").replace(
        "“", '"').replace("”", '"').replace("—", " - ")
    return " ".join(s.lower().split()).strip(" \"'")


def sents(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?…])[\"'”’)]*\s+(?=[A-Z\"'“‘(])",
                     str(text or "").strip())
    return [p.strip() for p in parts if re.search(r"[A-Za-z]{2,}", p or "")]


PC_NAMES: list[str] = []


def _you(s: str) -> str:
    for n in PC_NAMES:
        if n:
            s = s.replace(norm(n), "you")
    return s


def sim(a: str, b: str) -> float:
    a, b = _you(norm(a)), _you(norm(b))
    if not a or not b:
        return 0.0
    if a in b and len(a) > 20 and len(a) >= 0.9 * len(b):
        return 1.0
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


def words(s: str) -> list[str]:
    return [w for w in re.findall(r"[a-z][a-z'\-]+", norm(s)) if w not in STOP and len(w) > 2]


def best(x: str, texts) -> tuple[float, str]:
    top, at = 0.0, ""
    for t in texts:
        for y in sents(t):
            v = sim(x, y)
            if v > top:
                top, at = v, y
    return top, at


def _json_strings(raw: str) -> list[str]:
    if "{" not in (raw or ""):
        return [raw or ""]
    try:
        data = json.loads(raw[raw.find("{"):raw.rfind("}") + 1])
    except ValueError:
        return [raw]
    out: list[str] = []

    def walk(v):
        if isinstance(v, str):
            out.append(v)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    walk(data)
    return out


def _reask_reason(redo: str) -> str:
    r = redo or ""
    for needle, why in (("reuses words", "copy of last beat"), ("own JSON", "page fault"),
                        ("stops before", "page fault"), ("narration, not speech",
                                                        "narration in quotes"),
                        ("is not about", "matter not its own"), ("puts work", "made-up work"),
                        ("own goal", "not the player's goal")):
        if needle in r:
            return why
    return "named fault"


def slot_kind(key: str, slot: dict | None = None) -> str:
    key = str(key or "")
    enemy = "@" in key
    base = key.split("@", 1)[0]
    if base.startswith("fact"):
        kind = "act (blow)" if slot and "THE BLOW" in str(slot.get("say") or "") else "act"
    else:
        kind = base or "?"
    return f"enemy turn: {kind}" if enemy else kind


class Turn:
    """One bench record, readied for provenance."""

    def __init__(self, rec: dict):
        self.rec = rec
        tr = rec.get("trace") or {}
        # The player's name folds to "you" for matching (the groom's second-person swap).
        PC_NAMES[:] = [tr.get("pc") or ""]
        self.planned = tr.get("planned") or []
        self.changes = sorted((c for c in tr.get("changes") or [] if c["fn"] not in _READERS),
                              key=lambda c: c["end"])
        self.chats = tr.get("chats") or []
        # Since 2026-11-04 an enemy's turn is a planned beat of its own (`planned.write(
        # acting=…)`), so a turn can hold several beats with the same slot keys: a slot is
        # named for its beat when that beat is somebody else's ("fact1@the wolf#2").
        def k_of(key: str, beat: int) -> str:
            p = self.planned[beat] if 0 <= beat < len(self.planned) else {}
            return f"{key}@{p['acting']}#{beat}" if p.get("acting") else str(key)

        self.slots: dict[str, dict] = {}
        for n, p in enumerate(self.planned):
            for s in p.get("slots") or []:
                self.slots.setdefault(k_of(s["key"], n), s)
        # Every text a slot produced, in order, labelled.
        self.slot_texts: list[tuple[str, str, str]] = []   # (writer, slot key, text)
        for a in tr.get("asks") or []:
            if a.get("text"):
                w = ("model: slot first answer" if not a.get("redo") else
                     f"model: slot re-ask ({_reask_reason(a['redo'])})")
                self.slot_texts.append((w, k_of(a["key"], a.get("beat", 0)), a["text"]))
        for b in tr.get("bestof") or []:
            for c in b.get("tried") or []:
                if c.get("text"):
                    self.slot_texts.append(("model: slot first answer",
                                            k_of(b["key"], b.get("beat", 0)), c["text"]))
        for n, p in enumerate(self.planned):
            for m in p.get("remade") or []:
                if m.get("remade"):
                    self.slot_texts.append(("model: tells-check remake", k_of(m["slot"], n),
                                            m["remade"]))
                stood = m.get("stood") or ""
                if stood and not m.get("passed") and sim(stood, m.get("rejected") or "") < 0.6:
                    self.slot_texts.append(("engine line: tells-check fallback",
                                            k_of(m["slot"], n), stood))
        # The pipeline's own repair notes (the turn log's prose row): they name a step the
        # trace cannot see inside a wrapper (the truth pass's registered checks).
        self.notes = [str(n) for row in rec.get("rows") or [] if row.get("kind") == "prose"
                      for n in row.get("repairs") or []]
        self.writing_chats = []
        for c in self.chats:
            first = (c.get("who") or "").split(" < ")[0]
            for prefix, label in _WRITERS:
                if first.startswith(prefix):
                    if label.endswith(": "):
                        label += first.split(".")[-1]
                    self.writing_chats.append((label, c))
                    break

    def pages(self) -> list[str]:
        return [b.get("text") or "" for b in self.rec.get("beats") or [] if b.get("who") == "gm"]

    def kinds(self) -> list[str]:
        return [b.get("kind") or "" for b in self.rec.get("beats") or [] if b.get("who") == "gm"]

    def provenance(self, x: str, kind: str = "") -> dict:
        """Who wrote the page sentence `x`: writer, slot, the model's own sentence it came
        from (`origin`), and the editor that changed it after (or "")."""
        top, at, writer, key = 0.0, "", "", ""
        for w, k, t in self.slot_texts:
            v, y = best(x, [t])
            if v > top:
                top, at, writer, key = v, y, w, k
        if top >= SAME:
            editor = ""
            if top < 0.98:
                editor = self._introducer(x) or ""
            return {"writer": writer, "slot": key, "origin": at, "editor": editor,
                    "match": round(top, 2)}
        # A writing call outside the slots.
        ctop, cat, clabel = 0.0, "", ""
        for label, c in self.writing_chats:
            v, y = best(x, _json_strings(c.get("raw") or ""))
            if v > ctop:
                ctop, cat, clabel = v, y, label
        intro = self._introducer(x, detail=True)
        if ctop >= SAME:
            return {"writer": clabel, "slot": "(beat outside the plan)" if "enemy" in clabel
                    or "free" in clabel else "(tail)", "origin": cat, "editor": "",
                    "match": round(ctop, 2)}
        if intro:
            fn, before = intro
            # What it was made from: the closest sentence before the change. If a slot or a
            # writing call wrote that one, the sentence is theirs, edited by `fn` (the
            # quote then decides whose an error in it is); otherwise `fn` wrote it.
            pv, py = best(x, [before])
            if pv >= 0.5:
                for w, k, t in self.slot_texts:
                    v, _ = best(py, [t])
                    if v >= SAME:
                        return {"writer": w, "slot": k, "origin": py, "editor": fn,
                                "match": round(pv, 2)}
                for label, c in self.writing_chats:
                    v, _ = best(py, _json_strings(c.get("raw") or ""))
                    if v >= SAME:
                        return {"writer": label, "slot": "(beat outside the plan)"
                                if "enemy" in label or "free" in label else "(tail)",
                                "origin": py, "editor": fn, "match": round(pv, 2)}
            return {"writer": f"repair/backstop: {fn}", "slot": "(tail)", "origin": "",
                    "editor": "", "derived_from": py if pv >= 0.5 else "",
                    "match": round(pv, 2)}
        etop = max((sim(x, t.get("tell") or "") for t in self.rec.get("tells") or []),
                   default=0.0)
        if etop >= 0.6:
            return {"writer": "engine line (page)", "slot": "(engine)", "origin": x,
                    "editor": "", "match": round(etop, 2)}
        if top >= 0.6:
            return {"writer": writer, "slot": key, "origin": at,
                    "editor": self._introducer(x) or "unknown edit", "match": round(top, 2)}
        if kind == "consequence":
            # A page the engine wrote itself (a death notice, the fight's end, what a body
            # leaves behind): no model call holds it and nothing rewrote it.
            return {"writer": "engine line (page)", "slot": "(engine)", "origin": x,
                    "editor": "", "match": 0.0}
        return {"writer": "unattributed", "slot": "?", "origin": "", "editor": "",
                "match": round(max(top, ctop), 2)}

    def _introducer(self, x: str, detail: bool = False):
        """The change that first put `x` on the page: of the changes whose result holds it
        and whose input did not, the earliest; among the nested ones that did it together,
        the named step (`_named`), not the helper it called."""
        hits = [c for c in self.changes
                if best(x, [c["after"]])[0] >= SAME and best(x, [c["before"]])[0] < SAME]
        c = _named(hits)
        if c is None:
            return None
        fn = c["fn"]
        if fn in _WRAPPERS:
            fn = self._named_by_note(x, c["before"]) or fn
        return (fn, c["before"]) if detail else fn

    def _named_by_note(self, x: str, before: str) -> str:
        """The repair note that best fits an edit made inside a wrapper: its check's name
        ("narration-in-quotes: cut …" → "note: narration-in-quotes")."""
        top, at = 0.0, ""
        xw = set(words(x)) | set(words(before))
        for n in self.notes:
            v = len(set(words(n)) & xw) / max(1, len(set(words(n))))
            if v > top:
                top, at = v, n
        if not at:
            return ""
        return "note: " + re.split(r"[:(]", at, maxsplit=1)[0].strip()[:60]


def locate(turn: Turn, page: str, quote: str) -> tuple[int, str]:
    """(page index, sentence) holding the quote; the best-overlapping sentence otherwise."""
    pages = turn.pages()
    idx = None
    m = re.match(r"P(\d+)", page or "")
    if m and 0 < int(m.group(1)) <= len(pages):
        idx = int(m.group(1)) - 1
    order = [idx] if idx is not None else []
    order += [i for i in range(len(pages)) if i != idx]
    q = norm(quote)
    for i in order:
        for s in sents(pages[i]):
            if q and q in norm(s):
                return i, s
    # A quote across a sentence end ("You look at the gnome and say. What do you do?"): the
    # sentence it begins with, never another that merely shares its words.
    for i in order:
        if q and q in norm(pages[i]):
            starts = [s for s in sents(pages[i]) if norm(s) and q.startswith(norm(s))]
            if starts:
                return i, max(starts, key=len)
    qw = set(words(quote))
    top, at, ai = 0.0, "", -1
    for i in order:
        for s in sents(pages[i]):
            sw = set(words(s))
            v = len(qw & sw) / max(1, len(qw))
            if v > top:
                top, at, ai = v, s, i
    return (ai, at) if top >= 0.5 else (-1, "")


def _share(q: list[str], pool: set[str]) -> float:
    return sum(1 for w in q if w in pool) / max(1, len(q))


def _grams(s: str, n: int = 3) -> set:
    """Runs of n words with at least two content words in them: "from your hand" is
    everyone's phrase, "pewter longsword ready" is the scene's."""
    w = re.findall(r"[a-z']+", _you(norm(s)))
    out = set()
    for i in range(len(w) - n + 1):
        run = w[i:i + n]
        if sum(1 for x in run if x not in STOP and len(x) > 2) >= 2:
            out.add(" ".join(run))
    return out


def cause(turn: Turn, prov: dict, quote: str) -> str:
    """Plan or prompt cause, or the narrator's own invention (the module note, step 4).

    The quote's content words that neither the slot's tells nor the player's line supply
    are the claim's own (`novel`). None: the claim is made of the tell's or the player's own
    words, misapplied. Most of them in the slot's instruction: the plan asked for it. A run
    of three words copied from the shared prompt (the scene, the last beat, the people):
    the prompt's context. Otherwise the narrator's own invention. Word overlap with the
    scene alone is not counted: a smith and a coin are in every smithy's scene, and a
    first cut that counted them filed an invented payment as "context"."""
    w = prov["writer"]
    if not w.startswith("model"):
        return "n/a (not a model's words)"
    q = words(quote)
    if not q:
        return "invention (no content words)"
    player = set(words(turn.rec.get("line") or ""))
    slot = turn.slots.get(prov.get("slot") or "")
    if slot is None:
        # A beat outside the plan: its prompt is not kept; only the tells.
        tells = set(words(" ".join(t.get("tell") or "" for t in turn.rec.get("tells") or [])))
        novel = [x for x in q if x not in tells and x not in player]
        if not novel:
            return "prompt: the tell's own wording"
        return "invention (outside the plan)"
    if prov.get("slot") == "doing" and not slot.get("tells"):
        # The engine decided nothing, and the slot is asked to show the player's line done
        # ("The player's character does what the player said … Show exactly that"): a deed
        # or a deal written as done on such a turn is the ask's. Measured on the bench's
        # first batches: "I take the job" with no tell came back "you accept the task".
        return "plan: the doing slot shows the player's line as done"
    tells = set(words(" ".join(slot.get("tells") or [])))
    say = set(words(slot.get("say") or "")) - tells - player
    novel = [x for x in q if x not in tells and x not in player]
    if not novel:
        from_player = _share(q, player) > _share(q, tells)
        return ("plan: the player's line in the slot" if from_player
                else "prompt: the tell's own wording")
    if _share(novel, say) >= 0.5:
        return "plan: the slot's instruction"
    sk = str(prov.get("slot") or "")
    beat = int(sk.rsplit("#", 1)[1]) if "#" in sk else 0
    p = turn.planned[beat] if beat < len(turn.planned) else {}
    # The shared prompt without its PLAN block: the plan lists every slot's own ask and
    # tells, which are not context but instruction (judged above).
    ctx = ((p.get("plan_user") or "").split("PLAN:", 1)[0] + " "
           + (p.get("plan_system") or ""))
    if _grams(quote) & _grams(ctx):
        return "prompt: copied from the shared context (scene, last beat, people)"
    return "invention"


def omission(turn: Turn, quote: str) -> dict:
    """An untold tell: which tell, whether a slot carried it, and where its words went."""
    tells = [t.get("tell") or "" for t in turn.rec.get("tells") or [] if t.get("tell")]
    tq = max(tells, key=lambda t: sim(quote, t), default="")
    if norm(quote) and any(norm(quote) in norm(t) for t in tells):
        tq = next(t for t in tells if norm(quote) in norm(t))
    carried = [k for k, s in turn.slots.items() if any(sim(tq, t) > 0.9 for t in s.get(
        "tells") or [])]
    dropped = [s for p in turn.planned for s in p.get("slots") or [] if s.get("dropped")]
    if not turn.planned:
        return {"writer": "model: enemy-turn / consequence beat" if turn.writing_chats else
                "unattributed", "slot": "(beat outside the plan)",
                "cause": "omission: outside the plan", "tell": tq}
    if not carried:
        return {"writer": "plan", "slot": "(no slot)", "cause":
                "omission: no slot carried the tell", "tell": tq}
    key = carried[0]
    tw = set(words(tq))
    pages = " ".join(turn.pages())
    # A sentence some answer of that slot wrote, about the tell, that is not on the page.
    # The latest answer first: an engine line the tells check put in a slot's place is
    # what a later cut took off the page, not the model's first answer it replaced.
    for w, k, t in reversed(turn.slot_texts):
        if k != key:
            continue
        for y in sents(t):
            if _share(words(y), tw) >= 0.4 and best(y, [pages])[0] < 0.8:
                return {"writer": "cut: " + (_cutter(turn, y) or "a slot re-ask or the "
                                                                  "tells check"),
                        "slot": key, "cause": "omission: written, then cut", "tell": tq}
    if any(s.get("key") == key for s in dropped):
        return {"writer": "plan", "slot": key, "cause": "omission: slot dropped", "tell": tq}
    # The slot's own ask told it to stop short ("…squaring up to them …, and stop there"):
    # the plan's, when the untold part is a consequence the ask's stopping point excludes.
    say = str((turn.slots.get(key) or {}).get("say") or "")
    if re.search(r"\bstop there\b|\bnothing more\b", say):
        return {"writer": "model: slot first answer", "slot": key,
                "cause": "omission: the slot's instruction stops short of it", "tell": tq}
    return {"writer": "model: slot first answer", "slot": key,
            "cause": "omission: the slot never wrote it", "tell": tq}


# Text-in, text-out calls that make a reading copy, never the page: speech blanked for a
# detector, a sentence normalised for comparison. Their output is not an edit.
_READERS = {"judgement.redact_speech", "judgement.narration_quotes_blanked",
            "narration.unquoted", "narration._same_words", "narration._field",
            "judgement._words_of"}
# The turn's own wrappers: an edit only they enclose was made by an unwrapped step.
_WRAPPERS = {"GMAgent._groom", "GMAgent.narrate_turn", "GMAgent._truth_pass",
             "GMAgent.narrate_outcome"}
# Helpers a named step calls to do its cutting or splicing: an edit is the caller's.
_HELPERS = {"narration._without", "narration._cut_sentences", "narration.strip_added",
            "narration._blanked", "narration.page_line", "GMAgent._lift"}


def _named(hits: list[dict]) -> dict | None:
    """Of nested changes that made one edit, the step that owns it: the first to finish
    that is not a helper, else its shallowest enclosing change below the turn's own
    wrappers (depth 3 and deeper: `narrate_turn` and `_groom` enclose everything)."""
    if not hits:
        return None
    first = hits[0]
    group = [c for c in hits if c["start"] <= first["start"] and c["end"] >= first["end"]]
    named = [c for c in group if c["fn"] not in _HELPERS and c["depth"] >= 3]
    if named:
        return max(named, key=lambda c: c["depth"])
    return min(group, key=lambda c: c["depth"])


def _cutter(turn: Turn, y: str) -> str:
    hits = [c for c in turn.changes
            if best(y, [c["before"]])[0] >= SAME and best(y, [c["after"]])[0] < 0.8]
    c = _named(hits)
    if c is not None:
        if c["fn"] in _WRAPPERS:
            return turn._named_by_note(y, c["after"]) or c["fn"]
        return c["fn"]
    for p in turn.planned:
        for m in p.get("remade") or []:
            if best(y, [m.get("rejected") or ""])[0] >= SAME and \
                    best(y, [m.get("stood") or ""])[0] < 0.8:
                return "tells check (remake/cut)"
    return ""


# --- scores -----------------------------------------------------------------------------

# The prose ratings of the last `load_scores` call: {id: (1-5 or None, note)}.
RATINGS: dict = {}
RATINGS_BY: list[dict] = []


def load_scores(paths: list[str]) -> tuple[dict, set]:
    """{id: [(code, page, quote)]} and the ids answered at all."""
    out: dict[str, list] = defaultdict(list)
    seen: set[str] = set()
    RATINGS.clear()
    for p in paths:
        for line in open(p, encoding="utf-8"):
            parts = [x.strip() for x in line.strip().strip("`").split("|")]
            if not parts or not re.fullmatch(r"D\d{4}", parts[0]):
                continue
            seen.add(parts[0])
            if len(parts) >= 2 and parts[1].lower() == "none":
                continue
            if len(parts) >= 3 and parts[1].upper() == "P":
                RATINGS[parts[0]] = (int(parts[2]) if parts[2][:1].isdigit() else None,
                                     parts[3] if len(parts) > 3 else "")
                continue
            if len(parts) >= 4:
                code = parts[1].upper()
                out[parts[0]].append((code, parts[2], parts[3].strip().strip('"“”')))
    return out, seen


def boot_ci(xs: list[float], reps: int = 4000, seed: int = 7) -> tuple[float, float]:
    if not xs:
        return float("nan"), float("nan")
    rnd = random.Random(seed)
    n = len(xs)
    means = sorted(sum(rnd.choice(xs) for _ in range(n)) / n for _ in range(reps))
    return means[int(0.025 * reps)], means[int(0.975 * reps)]


def kappa(a: list[bool], b: list[bool]) -> float:
    n = len(a)
    if not n:
        return float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def attribute_all(key: dict, recs: dict, scores: dict) -> list[dict]:
    rows = []
    turns: dict[str, Turn] = {}
    for did, errs in scores.items():
        k = key.get(did)
        if not k or k["job"] not in recs:
            continue
        t = turns.get(k["job"]) or turns.setdefault(k["job"], Turn(recs[k["job"]]))
        for code, page, quote in errs:
            row = {"id": did, **k, "code": code, "page": page, "quote": quote}
            if not code.startswith("E"):
                pi, s = locate(t, page, quote)
                pv = (t.provenance(s, t.kinds()[pi]) if s else
                      {"writer": "unattributed", "slot": "?"})
                writer = pv["writer"]
                # A broken page (Q) with an edit under it is the edit's: the words were the
                # slot's, the fragment ("…and say. What do you do?") is what the cut left.
                # A refusal, a lecture or a softening (R, M, S) is the words' writer's even
                # when a later edit swapped a name in it.
                mostly = _share(words(quote), set(words(pv.get("origin") or ""))) >= 0.6
                if pv.get("editor") and (code == "Q" or (code in "RMS" and not mostly)
                                         or (code not in "QRMS" and not _in_origin(quote,
                                                                                    pv))):
                    writer = f"repair/backstop: {pv['editor']}"
                row.update(sentence=s, writer=writer, slot=pv.get("slot"))
                row["cause"] = f"tag {code}"
            elif code == "E6" or page.strip() in ("-", ""):
                o = omission(t, quote)
                row.update(sentence="", writer=o["writer"], slot=o["slot"], cause=o["cause"],
                           tell=o["tell"])
            else:
                pi, s = locate(t, page, quote)
                if not s:
                    row.update(sentence="", writer="unattributed (quote not found)", slot="?",
                               cause="?")
                else:
                    pv = t.provenance(s, t.kinds()[pi])
                    writer = pv["writer"]
                    if pv.get("editor") and not _in_origin(quote, pv):
                        writer = f"repair/backstop: {pv['editor']}"
                    row.update(sentence=s, writer=writer, slot=pv.get("slot"),
                               origin=pv.get("origin", ""), editor=pv.get("editor", ""))
                    row["cause"] = cause(t, {**pv, "writer": writer}, quote)
            row["slot_kind"] = slot_kind(row.get("slot"), t.slots.get(row.get("slot") or ""))
            rows.append(row)
    return rows


def _in_origin(quote: str, pv: dict) -> bool:
    """Whether the quoted words are the slot's own: the span itself in the sentence the slot
    wrote (PC name folded), or every content word of it there. A shared majority is not
    enough — "you fail to snatch" shares three of four words with "you snatch", and the one
    it adds is the error."""
    origin = _you(norm(pv.get("origin") or ""))
    q = _you(norm(quote)).strip(" .,;:!?")
    if q and q in origin:
        return True
    qw = words(quote)
    return bool(qw) and _share(qw, set(words(pv.get("origin") or ""))) >= 1.0


def _writer_group(w: str) -> str:
    w = str(w or "")
    if w.startswith("repair/backstop: "):
        return "repair/backstop"
    if w.startswith("cut: "):
        return "repair/backstop (cut)"
    return w


def table(rows: list[dict], dims: tuple[str, ...], total: int) -> list[str]:
    c = Counter(tuple(r.get(d) or "?" for d in dims) for r in rows)
    out = [f"| {' | '.join(dims)} | errors | share |", "|" + "---|" * (len(dims) + 2)]
    for k, n in c.most_common():
        out.append(f"| {' | '.join(map(str, k))} | {n} | {n / max(1, total):.0%} |")
    return out


def report(argv: list[str]) -> None:
    key = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    recs = {}
    for p in argv[1].split(","):
        for raw in open(p, encoding="utf-8"):
            if raw.strip():
                r = json.loads(raw)
                recs[r["job"]] = r
    scorers = [x.split(",") for x in argv[2:] if not x.startswith("--")]
    out_json = argv[argv.index("--json") + 1] if "--json" in argv else ""
    if out_json:
        scorers = [x.split(",") for x in argv[2:argv.index("--json")]]
    ids = sorted(key)
    per_scorer = []
    for n, paths in enumerate(scorers):
        sc, seen = load_scores(paths)
        RATINGS_BY.append(dict(RATINGS))
        missing = [d for d in ids if d not in seen]
        per_scorer.append((sc, seen))
        print(f"\n## Scorer {chr(65 + n)}: {len(seen)} of {len(ids)} items answered"
              + (f" (missing {len(missing)}: {missing[:8]}…)" if missing else ""))
    # Errors a beat, by condition and by activity, per scorer.
    conds = sorted({k["cond"] for k in key.values()})
    print("\n### Errors a beat (Q excluded), bootstrap 95% interval")
    print("| condition | beats | " + " | ".join(
        f"scorer {chr(65 + n)}" for n in range(len(scorers))) + " | mean | any-error beats |")
    print("|---" * (3 + len(scorers)) + "|---|")
    for cond in conds:
        cids = [d for d in ids if key[d]["cond"] == cond]
        cells, means, anys = [], [], []
        for sc, seen in per_scorer:
            xs = [sum(1 for e in sc.get(d, []) if e[0].startswith("E")) for d in cids]
            lo, hi = boot_ci(xs)
            cells.append(f"{sum(xs) / len(xs):.3f} ({lo:.3f}-{hi:.3f}), n err {sum(xs)}")
            means.append(sum(xs) / len(xs))
            anys.append(sum(1 for x in xs if x) / len(xs))
        print(f"| {cond} | {len(cids)} | " + " | ".join(cells)
              + f" | {sum(means) / len(means):.3f} | "
              + "/".join(f"{a:.0%}" for a in anys) + " |")
    for cond in conds:
        print(f"\n### By activity ({cond}): errors a beat, scorers averaged (Q pages in brackets)")
        acts = sorted({key[d]["activity"] for d in ids if key[d]["cond"] == cond})
        print("| activity | beats | errors/beat | 95% interval (pooled) | Q pages |")
        print("|---|---|---|---|---|")
        for a in acts:
            aids = [d for d in ids if key[d]["cond"] == cond and key[d]["activity"] == a]
            pooled = [sum(1 for e in sc.get(d, []) if e[0].startswith("E")) for sc, _ in per_scorer
                      for d in aids]
            q = [sum(1 for e in sc.get(d, []) if e[0] == "Q") for sc, _ in per_scorer
                 for d in aids]
            lo, hi = boot_ci(pooled)
            print(f"| {a} | {len(aids)} | {sum(pooled) / len(pooled):.2f} | {lo:.2f}-{hi:.2f} "
                  f"| {sum(q) / len(per_scorer):.1f} |")
    # Paired comparison against base, item x rep.
    if "base" in conds and len(conds) > 1:
        print("\n### Paired against base (same item and rep), per scorer: fewer / more / "
              "sign-test p")
        by = defaultdict(dict)
        for d in ids:
            by[(key[d]["item"], key[d]["rep"])][key[d]["cond"]] = d
        for cond in conds:
            if cond == "base":
                continue
            cells = []
            for sc, _ in per_scorer:
                f = m = 0
                for v in by.values():
                    if "base" in v and cond in v:
                        a = sum(1 for e in sc.get(v[cond], []) if e[0].startswith("E"))
                        b = sum(1 for e in sc.get(v["base"], []) if e[0].startswith("E"))
                        f += a < b
                        m += a > b
                nn, k = f + m, min(f, m)
                p = min(1.0, 2 * sum(math.comb(nn, i) for i in range(k + 1)) / 2 ** nn) \
                    if nn else 1.0
                cells.append(f"{f}/{m}/p={p:.2f}")
            print(f"- {cond}: " + "; ".join(cells))
    # Agreement.
    if len(per_scorer) >= 2:
        (a, _), (b, _) = per_scorer[0], per_scorer[1]
        ha = [bool([e for e in a.get(d, []) if e[0].startswith("E")]) for d in ids]
        hb = [bool([e for e in b.get(d, []) if e[0].startswith("E")]) for d in ids]
        ca = [len([e for e in a.get(d, []) if e[0].startswith("E")]) for d in ids]
        cb = [len([e for e in b.get(d, []) if e[0].startswith("E")]) for d in ids]
        mean_a, mean_b = sum(ca) / len(ca), sum(cb) / len(cb)
        cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(ca, cb))
        va = math.sqrt(sum((x - mean_a) ** 2 for x in ca))
        vb = math.sqrt(sum((y - mean_b) ** 2 for y in cb))
        print("\n### Inter-scorer agreement (A, B)")
        print(f"- beat has an error: agree on {sum(x == y for x, y in zip(ha, hb))}/{len(ids)}"
              f" beats, Cohen's kappa {kappa(ha, hb):.2f}")
        print(f"- errors a beat: Pearson r {cov / (va * vb) if va and vb else float('nan'):.2f}")
        qa = [any(e[0] == "Q" for e in a.get(d, [])) for d in ids]
        qb = [any(e[0] == "Q" for e in b.get(d, [])) for d in ids]
        print(f"- Q pages: kappa {kappa(qa, qb):.2f}")
        matched = total = 0
        same_code = 0
        recs_turn = {}
        for d in ids:
            ea = [e for e in a.get(d, []) if e[0].startswith("E")]
            eb = [e for e in b.get(d, []) if e[0].startswith("E")]
            used = set()
            for e in ea:
                total += 1
                for j, f in enumerate(eb):
                    if j in used:
                        continue
                    if _same_error(e, f):
                        matched += 1
                        same_code += e[0] == f[0]
                        used.add(j)
                        break
        print(f"- A's errors that B also marked (same item, overlapping words): {matched}/"
              f"{total} ({matched / max(1, total):.0%}); of those, the same code: "
              f"{same_code}/{matched}")
    # Tags and prose ratings by condition, per scorer.
    print("\n### Tags (items carrying one) and prose rating (mean, 1-5), per scorer")
    print("| condition | items | " + " | ".join(
        f"{chr(65 + n)}: Q/R/M/S, rating" for n in range(len(scorers))) + " |")
    print("|---|---|" + "---|" * len(scorers))
    for cond in conds:
        cids = [d for d in ids if key[d]["cond"] == cond]
        cells = []
        for n, (sc, _seen) in enumerate(per_scorer):
            tags = "/".join(str(sum(1 for d in cids if any(e[0] == t for e in sc.get(d, []))))
                            for t in ("Q", "R", "M", "S"))
            rated = [RATINGS_BY[n].get(d, (None, ""))[0] for d in cids]
            rated = [x for x in rated if x]
            cells.append(f"{tags}, {sum(rated) / len(rated):.2f} (n {len(rated)})"
                         if rated else f"{tags}, -")
        print(f"| {cond} | {len(cids)} | " + " | ".join(cells) + " |")
    # Attribution, per scorer and pooled.
    all_rows = []
    for n, (sc, _) in enumerate(per_scorer):
        rows = attribute_all(key, recs, sc)
        for r in rows:
            r["scorer"] = chr(65 + n)
        all_rows += rows
    for cond in conds:
        rows = [r for r in all_rows if r["cond"] == cond and r["code"].startswith("E")]
        tot = len(rows)
        print(f"\n### Attribution, {cond}: {tot} errors over {len(per_scorer)} scorers")
        print("\n**Writer**")
        print("\n".join(table(rows, ("writer",), tot)))
        print("\n**Slot**")
        print("\n".join(table(rows, ("slot_kind",), tot)))
        print("\n**Cause**")
        print("\n".join(table(rows, ("cause",), tot)))
        print("\n**Slot x writer x cause**")
        print("\n".join(table([dict(r, writer=_writer_group(r["writer"])) for r in rows],
                              ("slot_kind", "writer", "cause"), tot)))
        print("\n**Code x writer**")
        print("\n".join(table([dict(r, writer=_writer_group(r["writer"])) for r in rows],
                              ("code", "writer"), tot)))
        for tag in ("Q", "R", "M", "S"):
            q = [r for r in all_rows if r["cond"] == cond and r["code"] == tag]
            if q:
                print(f"\n**{tag} tags ({len(q)}, over the scorers) by writer**")
                print("\n".join(table(q, ("writer",), len(q))))
    if out_json:
        Path(out_json).write_text(json.dumps(all_rows, indent=1, ensure_ascii=False),
                                  encoding="utf-8")


def _same_error(e, f) -> bool:
    if e[0] == f[0]:
        return True
    if e[1] != f[1] and "-" not in (e[1], f[1]):
        return False
    a, b = set(words(e[2])), set(words(f[2]))
    if not a or not b:
        return norm(e[2]) == norm(f[2])
    return len(a & b) / min(len(a), len(b)) >= 0.3 or sim(e[2], f[2]) >= 0.6


def writers(paths: list[str]) -> None:
    """Who wrote every page sentence, as shares, by condition (no scorer needed)."""
    by = defaultdict(Counter)
    for p in paths:
        for raw in open(p, encoding="utf-8"):
            if not raw.strip():
                continue
            r = json.loads(raw)
            t = Turn(r)
            for page, kind in zip(t.pages(), t.kinds()):
                for s in sents(page):
                    pv = t.provenance(s, kind)
                    w = pv["writer"] + (" (edited)" if pv.get("editor") else "")
                    by[r.get("cond", "?")][w] += 1
    for cond, c in by.items():
        tot = sum(c.values())
        print(f"\n### Page sentences by writer, {cond} ({tot} sentences)")
        print("| writer | sentences | share |\n|---|---|---|")
        for w, n in c.most_common():
            print(f"| {w} | {n} | {n / tot:.1%} |")


def _p(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(math.ceil(q * len(xs))) - 1)] if xs else float("nan")


def pipeline(paths: list[str]) -> None:
    """What the pipeline did, by condition, read off the traces (no scorer): seconds a
    turn (wall, and wall less Ollama's model loads), model calls, slot re-asks by reason,
    the tells check's remakes, the text changes by function, and the turns that errored."""
    by = defaultdict(list)
    for p in paths:
        for raw in open(p, encoding="utf-8"):
            if raw.strip():
                r = json.loads(raw)
                by[r.get("cond", "?")].append(r)
    for cond, rows in by.items():
        walls = [r["wall"] for r in rows]
        loads = [sum(c.get("load") or 0 for c in (r.get("trace") or {}).get("chats") or [])
                 for r in rows]
        net = [w - ld for w, ld in zip(walls, loads)]
        calls = [len((r.get("trace") or {}).get("chats") or []) for r in rows]
        print(f"\n### {cond}: {len(rows)} turns, {sum(1 for r in rows if r.get('error'))} "
              f"errored")
        print(f"- seconds a turn: median {_p(walls, .5):.1f}, p90 {_p(walls, .9):.1f}; "
              f"less model loads: median {_p(net, .5):.1f}, p90 {_p(net, .9):.1f} "
              f"(loads total {sum(loads):.0f} s); model calls median {_p(calls, .5)}")
        reasks, changes, remade = Counter(), Counter(), Counter()
        bestof = Counter()
        for r in rows:
            tr = r.get("trace") or {}
            for a in tr.get("asks") or []:
                if a.get("redo"):
                    reasks[_reask_reason(a["redo"])] += 1
            for c in tr.get("changes") or []:
                if c["depth"] <= 3 and c["fn"] not in _READERS:
                    changes[c["fn"]] += 1
            for pl in tr.get("planned") or []:
                for m in pl.get("remade") or []:
                    remade["remade"] += 1
                    remade["passed" if m.get("passed") else "cut or engine line"] += 1
            for b in tr.get("bestof") or []:
                bestof[f"picked candidate {b['picked'] + 1} of {len(b['tried'])}"] += 1
                bestof["candidates passing"] += sum(1 for c in b["tried"]
                                                    if c["verdict"] == "pass")
                bestof["candidates tried"] += len(b["tried"])
        print(f"- slot re-asks: {dict(reasks)}")
        print(f"- tells check: {dict(remade)}")
        if bestof:
            print(f"- best-of: {dict(bestof)}")
        print("- text changes (depth <= 3), by function: "
              + ", ".join(f"{k} {v}" for k, v in changes.most_common(25)))


if __name__ == "__main__":
    {"report": report, "writers": writers, "pipeline": pipeline}[sys.argv[1]](sys.argv[2:])

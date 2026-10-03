"""Scoring a reading of a beat against its gold labels (tests/beat_reader/gold.py).

Both sides of the bench are scored by this one function — the beat reader, and the regex
harvesters it replaced — from the same normalised answers, so a difference in the numbers
is a difference in the reading and never in the scoring:

    answers = {
      "mentions":  {gold phrase key: "cN" | "pc" | "nobody" | "new" , ...},
      "groups":    {gold phrase key: an id shared by every mention of one newcomer},
      "newcomers": [{"words", "where": "here" | "elsewhere" | "", "key": gold phrase key
                     of the newcomer's first mention, or None}],
      "lines":     {gold line prefix: "cN" | "you" | "nobody" | "new:<gold phrase key>" | ""},
      "to":        {gold line prefix: "cN" | "you" | ...},
      "places":    [{"words", "kind", "near": a town place name | "here" | "none"}],
      "placed":    [{"words", "at": a town place name}],
      "pronouns":  {ref: "he" | "she"},
    }

A missing question (the old labeller had no "lines") is scored as not answered.
"""
from __future__ import annotations

import re


def _norm(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(text or "").lower().replace("’", "'")))


def alts(gold: str) -> list[str]:
    return [a.strip() for a in str(gold).split("|")]


def _new_key(gold_answer: str) -> str | None:
    for a in alts(gold_answer):
        if a.startswith("new:"):
            return a[4:]
    return None


def align_mentions(case: dict, mentions) -> dict:
    """{gold phrase key: mention} — "the man#2" is the second mention whose words are
    "the man" (case-insensitive when no exact match)."""
    out = {}
    for key in case.get("people") or {}:
        phrase, _, nth = key.partition("#")
        nth = int(nth or 1)
        same = [m for m in mentions if m.phrase == phrase]
        if len(same) < nth:
            same = [m for m in mentions if m.phrase.lower() == phrase.lower()]
        if len(same) >= nth:
            out[key] = same[nth - 1]
    return out


def align_lines(case: dict, lines) -> dict:
    """{gold line prefix: line} — by the first words of what was said."""
    out = {}
    for key in case.get("lines") or {}:
        want = _norm(key)
        for ln in lines:
            if _norm(ln.words).startswith(want) and ln not in out.values():
                out[key] = ln
                break
    return out


def _right(gold: str, got: str, newcomer_ok: bool = True) -> bool:
    if "*" in alts(gold):
        return True
    for a in alts(gold):
        if a == got:
            return True
        if a.startswith("new:") and newcomer_ok and str(got).startswith("new"):
            return True
    return False


def _words_match(gold_words: str, got: str) -> bool:
    got = _norm(got)
    return any(_norm(w) and _norm(w) in got for w in alts(gold_words))


def score(case: dict, ans: dict) -> dict:
    """Per-question tallies for one case: {question: {"right": n, "of": n, ...}}."""
    out: dict = {}
    people = case.get("people") or {}

    # (a) who each mention is.
    if "mentions" in ans:
        right = of = unmarked = 0
        misses = []
        for key, gold in people.items():
            got = ans["mentions"].get(key)
            if got is None:
                unmarked += 1
                continue
            of += 1
            if _right(gold, got):
                right += 1
            else:
                misses.append(f"{key}: {got} (gold {gold})")
        out["mentions"] = {"right": right, "of": of, "unmarked": unmarked, "misses": misses}

    # newcomers grouped: two mentions of one newcomer share a group, two newcomers do not.
    if "groups" in ans:
        keys = [k for k, g in people.items() if _new_key(g) and not set(alts(g)) - {
            f"new:{_new_key(g)}"}]
        right = of = 0
        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                if a not in ans["groups"] or b not in ans["groups"]:
                    continue
                of += 1
                same_gold = _new_key(people[a]) == _new_key(people[b])
                same_got = ans["groups"][a] == ans["groups"][b]
                right += int(same_gold == same_got)
        out["grouping"] = {"right": right, "of": of}

    # (c) who is made a body here, and who is recorded as only spoken of.
    if "newcomers" in ans:
        gold_new = case.get("new") or {}
        key_of = {}                         # gold phrase key -> newcomer K
        for k, g in people.items():
            nk = _new_key(g)
            if nk:
                key_of[k] = nk
        for where in ("here", "elsewhere"):
            got = [n for n in ans["newcomers"] if n.get("where") == where]
            want = {k for k, v in gold_new.items()
                    if v["where"] in (where, "*") and not v.get("optional")}
            allowed = {k for k, v in gold_new.items() if v["where"] in (where, "*")}
            hit, wrong, matched = 0, [], set()
            for n in got:
                k = key_of.get(n.get("key") or "")
                if k is None:
                    k = next((g for g, v in gold_new.items()
                              if _words_match(v["head"], n.get("words", ""))
                              and g not in matched), None)
                if k in allowed and k not in matched:
                    hit += 1
                    matched.add(k)
                else:
                    wrong.append(n.get("words", ""))
            out[f"made_{where}"] = {"got": len(got), "right": hit, "want": len(want),
                                    "found": len(want & matched), "wrong": wrong}

    # (b) who speaks each line.
    if "lines" in ans:
        right = of = 0
        misses = []
        for key, gold in (case.get("lines") or {}).items():
            got = ans["lines"].get(key)
            if got is None:
                continue
            of += 1
            if str(got).startswith("new:"):
                k = got[4:]
                got_new = _new_key(people.get(k, "")) if k in people else None
                ok = any(a == f"new:{got_new}" for a in alts(gold)) or "*" in alts(gold)
            else:
                ok = _right(gold, got, newcomer_ok=False)
            right += int(ok)
            if not ok:
                misses.append(f"{key[:30]}: {got} (gold {gold})")
        out["lines"] = {"right": right, "of": of, "misses": misses}
    if "to" in ans and case.get("to"):
        right = of = 0
        for key, gold in case["to"].items():
            got = ans["to"].get(key)
            if got is None:
                continue
            of += 1
            right += int(_right(gold, got, newcomer_ok=False))
        out["to"] = {"right": right, "of": of}

    # (d) places a speaker named that the town lacks; people placed at the town's places.
    for q, gold_key, field in (("places", "places", "near"), ("placed", "placed", "at")):
        if q not in ans:
            continue
        gold = case.get(gold_key) or []
        got = list(ans[q])
        used: dict[int, int] = {}
        wrong, dup = [], 0
        attr_right = attr_of = kind_right = kind_of = 0
        for g_item in got:
            i = next((i for i, g in enumerate(gold)
                      if _words_match(g["words"], g_item.get("words", ""))), None)
            if i is None:
                wrong.append(g_item.get("words", ""))
                continue
            if i in used:
                dup += 1
                continue
            used[i] = 1
            g = gold[i]
            if g.get(field, "*") != "*":
                attr_of += 1
                attr_right += int(_right(g[field], g_item.get(field, "")))
            if q == "places" and g.get("kind", "*") != "*":
                kind_of += 1
                kind_right += int(_right(g["kind"], g_item.get("kind", "") or "other"))
        want = [i for i, g in enumerate(gold) if not g.get("optional")]
        out[q] = {"got": len(got), "want": len(want), "found": sum(1 for i in want if i in used),
                  "wrong": wrong, "duplicates": dup,
                  f"{field}_right": attr_right, f"{field}_of": attr_of,
                  **({"kind_right": kind_right, "kind_of": kind_of} if q == "places" else {})}

    # names the page gives: a gold name found on the right person; a name put on a person
    # the gold names nothing for, who has no proper name yet, is a wrong renaming.
    if "names" in ans and "names" in case:
        gold = case.get("names") or {}
        got = {str(n["who"]): n["name"] for n in ans["names"]}
        right = sum(1 for who, name in gold.items()
                    if any(_norm(a) == _norm(got.get(who, "")) for a in alts(name)))
        unnamed = {ref for ref, name, what in case["cast"]
                   if what != "pc" and not (name[:1].isupper()
                                            and not name.lower().startswith("the "))}
        wrong = [f"{w}={n}" for w, n in got.items() if w not in gold
                 and (w in unnamed or w.startswith("new:"))]
        out["names"] = {"right": right, "of": len(gold), "wrong": wrong}

    # pronouns the page settles for a they/them person.
    if "pronouns" in ans:
        gold = case.get("pronouns") or {}
        right = of = 0
        misses = []
        for ref in case.get("vague") or []:
            g = gold.get(ref, "not said")
            got = ans["pronouns"].get(ref, "not said")
            if g == "*" or "*" in alts(g) and got in ("not said", *alts(g)):
                continue
            of += 1
            ok = got in alts(g)
            right += int(ok)
            if not ok:
                misses.append(f"{ref}: {got} (gold {g})")
        out["pronouns"] = {"right": right, "of": of, "misses": misses}
    return out


def strict(tallies: dict) -> bool:
    """The whole beat right: every answered question right, nothing made or recorded that
    should not be, nothing required missed."""
    for q, t in tallies.items():
        if q in ("mentions", "lines", "to", "grouping", "pronouns", "names"):
            if t["right"] != t["of"] or t.get("wrong"):
                return False
        elif q.startswith("made_"):
            if t["wrong"] or t["found"] != t["want"]:
                return False
        elif q in ("places", "placed"):
            if t["wrong"] or t["duplicates"] or t["found"] != t["want"]:
                return False
            for k in ("near", "at", "kind"):
                if t.get(f"{k}_right", 0) != t.get(f"{k}_of", 0):
                    return False
    return True

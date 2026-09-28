"""Scoring a frame against the labelled one (tests/interpreter/gold.py).

The measures the literature on this uses (docs/the-interpreter.md): whole-frame exact
match, the acts in order, and slot precision/recall/F1 with lenient matching. Slots are
compared without case, punctuation, articles or determiners, and with a pronoun's forms
as one ("his face" and "him" point at the same man). A slot matches when the two are
equal after that, or one contains the other and they share at least half their words:
"the woman who sold me bread" and "woman who sold me bread" are the same answer, and
"the woman" is not.
"""
from __future__ import annotations

import re

_DROP = {"the", "a", "an", "some", "any"}
_PRONOUN = {"his": "him", "he": "him", "her": "her", "hers": "her", "she": "her",
            "they": "them", "their": "them", "theirs": "them"}


def norm(s) -> list[str]:
    words = re.findall(r"[a-z0-9']+", str(s or "").lower())
    return [_PRONOUN.get(w, w) for w in words if w not in _DROP]


def same(a, b) -> bool:
    x, y = norm(a), norm(b)
    if not x or not y:
        return not x and not y
    if x == y:
        return True
    short, long_ = (x, y) if len(x) <= len(y) else (y, x)
    joined, whole = " ".join(short), " ".join(long_)
    return joined in whole and len(short) / len(long_) >= 0.5


SLOTS = ("target", "object", "place", "time", "says")


def score(gold: list[dict], got: list[dict]) -> dict:
    """gold and got are parallel lists of frames. Returns the measures and the misses."""
    n = len(gold)
    frame_ok = acts_ok = question_ok = 0
    tp = fp = fn = 0
    act_tp = act_fp = act_fn = 0
    misses = []
    for g, p in zip(gold, got):
        ga = [a["act"] for a in g["actions"]]
        pa = [a["act"] for a in (p.get("actions") or [])]
        question_ok += bool(g.get("question")) == bool(p.get("question"))
        # Acts as multisets for F1; in order for the sequence measure.
        remaining = list(pa)
        for act in ga:
            if act in remaining:
                act_tp += 1
                remaining.remove(act)
            else:
                act_fn += 1
        act_fp += len(remaining)
        seq = ga == pa
        acts_ok += seq
        # Slots, over actions aligned by position where the act agrees.
        slot_ok = True
        for i, ga_ in enumerate(g["actions"]):
            pa_ = (p.get("actions") or [])[i] if i < len(p.get("actions") or []) else None
            for s in SLOTS:
                gv = ga_.get(s)
                pv = pa_.get(s) if pa_ is not None and pa_.get("act") == ga_["act"] else None
                if gv and pv and same(gv, pv):
                    tp += 1
                elif gv and pv:
                    fp += 1
                    fn += 1
                    slot_ok = False
                elif gv:
                    fn += 1
                    slot_ok = False
                elif pv:
                    fp += 1
                    slot_ok = False
        whole = seq and slot_ok and bool(g.get("question")) == bool(p.get("question"))
        frame_ok += whole
        if not whole:
            misses.append({"text": g["text"], "gold": g["actions"],
                           "got": p.get("actions"), "question": p.get("question")})

    def f1(t, f_p, f_n):
        prec = t / (t + f_p) if t + f_p else 1.0
        rec = t / (t + f_n) if t + f_n else 1.0
        return round(prec, 3), round(rec, 3), round(2 * prec * rec / (prec + rec), 3) if prec + rec else 0.0

    return {
        "n": n,
        "frame_exact": round(frame_ok / n, 3) if n else 0.0,
        "acts_in_order": round(acts_ok / n, 3) if n else 0.0,
        "question_accuracy": round(question_ok / n, 3) if n else 0.0,
        "act_p_r_f1": f1(act_tp, act_fp, act_fn),
        "slot_p_r_f1": f1(tp, fp, fn),
        "misses": misses,
    }

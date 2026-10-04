"""The beat-reader bench's labels hold together (tests/beat_reader/gold.py).

A bench is only as good as its labels, and a label that names a ref nobody in the cast
holds, a newcomer key nobody defines, or a phrase the finder never marks scores as a miss
for the reader when the fault is the gold's. The interpreter bench's own labels are kept
honest the same way (tests/test_interpreter_gold.py). Every check here fails with the case
named.
"""
from __future__ import annotations

import pytest

from gm import beat_reader, mentions, speech
from tests.beat_reader.gold import CASES
from tests.beat_reader.score import align_lines, align_mentions, alts

TEXT_CASES = [c for c in CASES if c.get("text")]


def _people(case) -> list[dict]:
    """The cast as `mentions.people` would give it, without building a scene."""
    return [{"ref": ref, "name": name, "true": "", "pc": what == "pc",
             "what": "" if what == "pc" else what, "dead": False}
            for ref, name, what in case["cast"]]


def test_the_cases_are_named_once_and_say_why():
    ids = [c["id"] for c in CASES]
    assert len(ids) == len(set(ids))
    for c in CASES:
        assert c.get("why"), f"{c['id']}: say which defect the case is for"
        assert c.get("text") or c.get("corpus"), f"{c['id']}: no text and no corpus beat"


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_every_answer_names_somebody_the_cast_holds(case):
    refs = {ref for ref, _, _ in case["cast"]}
    assert "pc" in refs
    refs |= {ref for ref, _, _ in case.get("away") or []}
    new = set(case.get("new") or {})
    ok = refs | {"nobody", "you", "*"} | {f"new:{k}" for k in new}
    for field in ("people", "lines", "to"):
        for key, gold in (case.get(field) or {}).items():
            for a in alts(gold):
                assert a in ok, f"{case['id']} {field} {key!r}: {a!r} is nobody here"
    for ref in case.get("vague") or []:
        assert ref in refs, f"{case['id']}: vague {ref} is not in the cast"
    for ref in (case.get("pronouns") or {}):
        assert ref in (case.get("vague") or []), f"{case['id']}: pronoun for {ref}, " \
                                                 f"who is not they/them"
    used = {a[4:] for f in ("people", "lines") for g in (case.get(f) or {}).values()
            for a in alts(g) if a.startswith("new:")}
    assert used <= new, f"{case['id']}: newcomer keys {used - new} are not defined"
    for k, v in (case.get("new") or {}).items():
        assert v["where"] in ("here", "elsewhere", "*") and v.get("head")


@pytest.mark.parametrize("case", TEXT_CASES, ids=lambda c: c["id"])
def test_every_labelled_phrase_is_one_the_finder_marks(case):
    """A gold phrase the finder never marks could never be answered: the bench would count
    the finder's miss against the reader. Measured while labelling, 2026-10-03: 'the man
    on the stool' is marked as 'The man' (the finder takes up to three describing words
    before a person noun, never the words after it)."""
    found = mentions.find(case["text"], _people(case))
    aligned = align_mentions(case, found)
    missing = set(case.get("people") or {}) - set(aligned)
    assert not missing, f"{case['id']}: the finder marks none of {sorted(missing)}; " \
                        f"it marks {[m.phrase for m in found]}"


@pytest.mark.parametrize("case", TEXT_CASES, ids=lambda c: c["id"])
def test_every_labelled_line_and_tag_is_on_the_page(case):
    lines = beat_reader.lines_of(case["text"])
    aligned = align_lines(case, lines)
    missing = set(case.get("lines") or {}) - set(aligned)
    assert not missing, f"{case['id']}: no line opens with {sorted(missing)}; the lines " \
                        f"are {[ln.words[:30] for ln in lines]}"
    on_page = [" ".join(ln.split()).lower() for ln in speech.lines(case["text"])]
    for ref, prefix in case.get("said") or []:
        assert any(ln.startswith(prefix.lower()) for ln in on_page), \
            f"{case['id']}: the tag for {prefix!r} matches no line"
        assert ref in {r for r, _, _ in case["cast"]} or ref == "c1", case["id"]


@pytest.mark.parametrize("case", [c for c in CASES if c.get("town")], ids=lambda c: c["id"])
def test_the_town_holds_where_the_party_stands(case):
    assert case["here"] in case["town"], f"{case['id']}: {case['here']} is not in its town"
    for field, key in (("places", "near"), ("placed", "at")):
        for item in case.get(field) or []:
            for a in alts(item.get(key, "*")):
                assert a in ("*", "here", "none") or a in case["town"], \
                    f"{case['id']} {field}: {a!r} is not a place of the town"

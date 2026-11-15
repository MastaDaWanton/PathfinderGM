"""The ruling bench's own code: the frozen set, the precedents and the combiner.

The bench is how the ruling judge is measured before it may reach play, so a quiet defect
here would forge the number that gates it.
"""
import json

from tools.ruling_bench import closed, score
from tools.ruling_bench.run import SET


def _data():
    return json.loads(SET.read_text(encoding="utf-8"))


def test_set_is_frozen_with_its_provenance():
    """The key used to be read from outside the repo, so no score could be reproduced from
    the branch. The set must carry both sources' hashes and its three splits."""
    d = _data()
    assert set(d["sources"]) == {"set1", "set2"}
    assert all(len(s["sha256"]) == 64 for s in d["sources"].values())
    n = {}
    for l in d["lines"]:
        n[l["split"]] = n.get(l["split"], 0) + 1
    assert n["set1"] == 152 and n["set2"] == 40 and n["rulings"] >= 1


def test_fights_are_read_from_the_scene():
    """The old runner hard-coded fights as {s4, s7}, so set2's fight t3 was judged as
    'not a fight'."""
    assert _data()["scenes"]["t3"]["fight"] is True


def test_precedents_never_show_the_lines_own_scene():
    """Leave-one-scene-out: a set1 line shown its own scene's rulings would be scored on
    an answer it was handed."""
    set1 = [l for l in _data()["lines"] if l["split"] == "set1"]
    p = closed.Precedents(set1)
    for l in set1[:20]:
        near = p.nearest(l["text"], l["scene"])
        assert near and all(x["scene"] != l["scene"] for x in near)
        assert {x["verdict"] for x in near} == {"say_yes", "roll", "refuse"}


def test_refusals_are_checked_before_anything_can_allow():
    """CoC-Seduce measured judges talked into passes; in the combiner a refusal answer
    wins over every answer that would let the line happen."""
    assert closed.combine({"rule_claim": "yes", "outcome": "certain"})["refuse"] == "false_rule"
    assert closed.combine({"power_used": "another", "outcome": "certain"})["refuse"] == "character"
    assert closed.combine({"unknown_fact": "secret"})["what"] == "oracle"
    assert closed.combine({"outcome": "certain", "seeks_hidden": "yes"})["verdict"] == "roll"
    assert closed.combine({"outcome": "certain"})["verdict"] == "say_yes"


def test_the_sheets_powers_are_the_judges_only_choices():
    thessaly = _data()["pcs"]["thessaly"]
    powers = closed.powers_of(thessaly)
    assert "magic missile" in powers and "prestidigitation" in powers
    assert "mage armor" not in powers  # the sheet says it is NOT prepared
    enum = closed.checklist_schema("v2", powers)["properties"]["power_used"]["enum"]
    assert enum[0] == "none" and enum[-1] == "another"


def test_score_counts_each_error_kind():
    lines = {"a": {"id": "a", "split": "x", "kind": "k", "author": "owner", "text": "",
                   "verdict": "refuse", "refuse": "false_rule", "roll": {}},
             "b": {"id": "b", "split": "x", "kind": "k", "author": "owner", "text": "",
                   "verdict": "roll", "refuse": None, "roll": {"what": "skill:Bluff"}}}
    rows = [{"id": "a", "ruling": {"verdict": "roll"}, "seconds": 1, "wall": 2},
            {"id": "b", "ruling": {"verdict": "say_yes"}, "seconds": 1, "wall": 2}]
    out = score.score(lines, rows)
    assert "VERDICT   0.0%" in out
    assert "lenient 100.0%" in out and "missed roll 100.0%" in out

"""Every yes/no param is read as one, whatever the model wrote (`intents.FLAG_PARAMS`).

Ponytail audit 2026-11-07, finding #5: `FLAG_PARAMS` exists because `bool("false")` is
True, but `coup_de_grace`, `search` and `diversion` were not on it, and `parse` read
`coup_de_grace` with a stray `bool()` of its own. Confirmed on 0.2.27: an attack with
`"coup_de_grace": "false"` parsed as True, which against a helpless target is an
automatic critical and a save-or-die. `follow` (track), `deliberate` and `immersed`
(hazard) are read the same way by the engine and joined them.
"""
from __future__ import annotations

import pytest

from rules import intents


def _attack(params):
    return intents.parse({"op": "attack", "actor": "pc", "target": "c1", "because": "t",
                          "params": params})


@pytest.mark.parametrize("word", ["false", "False", "no", "none", "0", "off"])
def test_coup_de_grace_written_as_a_no_word_is_no(word):
    """`"coup_de_grace": "false"` parsed as True on 0.2.27 — an execution."""
    assert _attack({"coup_de_grace": word}).params["coup_de_grace"] is False


def test_coup_de_grace_written_as_a_yes_is_yes():
    assert _attack({"coup_de_grace": "true"}).params["coup_de_grace"] is True
    assert _attack({"coup_de_grace": True}).params["coup_de_grace"] is True


def test_full_attack_written_as_a_word_is_read_as_one():
    assert _attack({"full_attack": "false"}).params["full_attack"] is False
    assert _attack({}).params.get("full_attack", False) is False


def test_search_written_as_false_is_not_a_search():
    """`search: "false"` on a perception check was a search on 0.2.27: the check went
    against the hiding's DC instead of the band the model gave."""
    got = intents.parse({"op": "check", "actor": "pc", "because": "t",
                         "params": {"skill": "perception", "search": "false",
                                    "dc": {"band": "easy"}}})
    assert got.params["search"] is False


def test_diversion_written_as_false_is_not_a_diversion():
    """`diversion: "false"` on a bluff with a band was refused on 0.2.27 as "a diversion
    is rolled against every watcher's sense motive" — a diversion nobody asked for."""
    got = intents.parse({"op": "check", "actor": "pc", "because": "t",
                         "params": {"skill": "bluff", "diversion": "false",
                                    "dc": {"band": "easy"}}})
    assert got.params["diversion"] is False


@pytest.mark.parametrize("op,params,key", [
    ("track", {"follow": "false"}, "follow"),
    ("hazard", {"rule": "falling", "deliberate": "false"}, "deliberate"),
    ("hazard", {"rule": "falling", "immersed": "no"}, "immersed"),
])
def test_other_yes_no_params_the_engine_reads_are_flags(op, params, key):
    got = intents.parse({"op": op, "actor": "pc", "because": "t", "params": params})
    assert got.params[key] is False


def test_a_false_search_still_gets_a_band_filled():
    """`judgement.fill_bare_checks` fills a missing band unless the check is engine-set.
    It read `search: "false"` with `bool()`, so it left the band out, and `parse` (which
    reads the word as no) then refused the check for having nothing to beat."""
    from gm import judgement

    raw = [{"op": "check", "actor": "pc", "because": "t",
            "params": {"skill": "perception", "search": "false"}}]
    got = judgement.fill_bare_checks(raw)
    assert got[0]["params"].get("dc") == {"band": "average"}
    intents.parse(got[0])


def test_the_plan_schema_types_the_new_flags_as_booleans():
    """A flag is a boolean at the sampler (`prompts._declared_op`); typed "string",
    the three could only ever be sampled as words."""
    from gm import prompts

    attack = prompts._declared_op("attack", ("pc", "c1"), ())
    check = prompts._declared_op("check", ("pc",), ())
    assert attack["properties"]["params"]["properties"]["coup_de_grace"]["type"] == "boolean"
    for key in ("search", "diversion"):
        assert check["properties"]["params"]["properties"][key]["type"] == "boolean"

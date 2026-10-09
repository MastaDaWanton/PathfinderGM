"""The bestiary's harvest tags and their validator (tools/harvest_tags.py; leatherworking
plan §5.3; contracts §5.1; lane C).

The owner's rule (Q9.2): the beasts carry the tags and the reader finds them. These pin the
shipped tags against the validator and the generated review, so a hand edit to a stat block
or a stale pass cannot ship a defect the pass was written to end.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from rules import bestiary, gathering, harvest


def _tagged_blocks():
    return [b for b in bestiary.imported().values()
            if any(str(t).startswith("harvest.") for t in b.get("tags") or ())]


def test_every_shipped_harvest_tag_passes_the_validator():
    """Plan §5.3's validators on every load: no harvest tag on a humanoid or a native
    outsider ("109 humanoids yielded a hide", inventory §0.4; deeds answer 3b), none naming
    a material no shelf holds, no true dragon tagged with another colour's dragonhide (the
    red dragon that offered all eleven colours)."""
    blocks = _tagged_blocks()
    assert len(blocks) > 1000
    problems = [p for b in blocks for p in harvest.validate_tags(b)]
    assert problems == [], problems[:10]


def test_a_true_dragon_carries_at_most_its_own_colour():
    """Inventory §0.4, from the tags' side: no block carries two dragonhides, and a true
    dragon's dragonhide is the one its own breath and alignment say."""
    hides = set(harvest.rules()["dragonhides"])
    for b in _tagged_blocks():
        mine = [t for t in b["tags"] if t.startswith("harvest.hide.")
                and t.split(".", 2)[2] in hides]
        assert len(mine) <= 1, b["id"]
        if mine:
            assert harvest.dragon_colour(b) == mine[0].split(".", 2)[2], b["id"]


def test_a_block_carries_one_named_hide_at_most():
    """The pass's own rule: the longest fragment wins, so a winter wolf is not also a wolf
    (the old reader offered both, `hides_from`'s list)."""
    for b in _tagged_blocks():
        hides = [t for t in b["tags"] if t.startswith("harvest.hide.")]
        assert len(hides) <= 1, (b["id"], hides)


def test_the_excursion_reader_and_the_harvest_read_one_grammar():
    """`gathering.harvest_tagged` and `harvest.tagged` read the same branches and refuse
    the same tags: a humanoid with a hand tag gives nothing to either."""
    class Body:
        from_template = ""
        effects = ()

        def __init__(self, block):
            self.block = block

        def standing_tags(self):
            return tuple(self.block.get("tags") or ())

    block = dict(bestiary.raw("aasimar"), tags=["harvest.hide.wolf-pelt"])
    import rules.harvest as h

    real = h.block_of
    try:
        h.block_of = lambda c: block if isinstance(c, Body) else real(c)
        assert gathering.harvest_tagged(Body(block), "leatherworker") == []
    finally:
        h.block_of = real
    wolf = dict(bestiary.raw("wolf"))
    from_reader = {m for b, m in harvest.tagged(wolf) if b in ("hide",)}
    h.block_of = lambda c: wolf if isinstance(c, Body) else real(c)
    try:
        from_excursion = {m.id for m in gathering.harvest_tagged(Body(wolf), "leatherworker")}
    finally:
        h.block_of = real
    assert from_reader <= from_excursion | {"sinew-thread"}


def test_the_tag_pass_and_its_review_are_fresh():
    """The forge's pattern: the review page is generated from the shipped files, so it can
    never disagree with what the game reads; `--check` fails when a stat block's tags or
    the review differ from what the pass would write."""
    path = Path(__file__).resolve().parents[1] / "tools" / "harvest_tags.py"
    spec = importlib.util.spec_from_file_location("harvest_tags_tool", path)
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    assert tool.main(["--check"]) == 0

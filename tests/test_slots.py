"""Magic item body slots.

The slot list is Ultimate Equipment p.206: "There are 15 categories of slotted wondrous
items. Armor, rings, and shields are described in other sections of this book, while the
11 other body slots are detailed below."
"""
from __future__ import annotations

import pytest

from rules.sheet import IllegalSheet, body_slots, from_dict, load_pc, to_dict
from rules.tables import SLOT_ORDER_LEFT, SLOT_ORDER_RIGHT, SLOTS


@pytest.fixture
def kesst():
    return load_pc("fixtures/pc-kesst.json")


def test_the_slot_list_is_the_books_fifteen_categories():
    """Eleven body slots plus armour, rings and shields."""
    assert set(SLOTS) == {
        "belt", "body", "chest", "eyes", "feet", "hands", "head", "headband", "neck",
        "shoulders", "wrists", "armor", "ring", "shield",
    }
    # Every slot appears exactly once down one side of the figure or the other.
    laid_out = list(SLOT_ORDER_LEFT) + list(SLOT_ORDER_RIGHT)
    assert sorted(laid_out) == sorted(SLOTS)
    assert len(laid_out) == len(set(laid_out))


def test_the_rules_defaults_are_two_rings_and_one_of_everything_else(kesst):
    assert len(kesst.slot_list("ring")) == 2
    for key in SLOTS:
        if key != "ring":
            assert len(kesst.slot_list(key)) == 1, key


def test_empty_slots_are_reported_rather_than_omitted(kesst):
    """Showing what is *not* filled is the entire reason for laying the slots out on a
    body, so a blank has to be a thing the sheet knows about."""
    slots = body_slots(kesst)
    head = next(s for s in slots["left"] if s["key"] == "head")
    assert head["items"] == [{"index": 0, "item": None, "empty": True,
                              "beyond_rules": False}]


def test_rings_go_up_to_ten(kesst):
    for _ in range(8):
        kesst.add_slot("ring")
    assert len(kesst.slot_list("ring")) == 10
    with pytest.raises(IllegalSheet, match="already has 10"):
        kesst.add_slot("ring")


def test_amulets_go_up_to_five(kesst):
    """The neck slot holds amulets, brooches, necklaces, periapts and scarabs."""
    for _ in range(4):
        kesst.add_slot("neck")
    assert len(kesst.slot_list("neck")) == 5
    with pytest.raises(IllegalSheet, match="already has 5"):
        kesst.add_slot("neck")


def test_single_slots_cannot_be_multiplied(kesst):
    """You get one head. The generous maxima are for rings and amulets only."""
    for key in ("head", "belt", "body", "chest", "eyes", "feet", "hands", "headband",
                "shoulders", "wrists", "armor", "shield"):
        with pytest.raises(IllegalSheet, match="already has 1"):
            kesst.add_slot(key)


def test_slots_past_the_rules_limit_are_marked_rather_than_hidden(kesst):
    """1e lets you benefit from two rings. The sheet records ten because players own
    more than they wear, but the extra eight are flagged so the display can say they are
    carried rather than working."""
    for _ in range(8):
        kesst.add_slot("ring")
    rings = next(s for s in body_slots(kesst)["right"] if s["key"] == "ring")
    assert rings["rules_limit"] == 2
    assert [i["beyond_rules"] for i in rings["items"]] == [False, False] + [True] * 8


def test_the_armour_slot_reads_from_the_worn_armour(kesst):
    """Two places that both say what someone is wearing is how they come to disagree, so
    the armour and shield slots are derived rather than stored."""
    armour = next(s for s in body_slots(kesst)["left"] if s["key"] == "armor")
    assert armour["items"][0]["item"] == "leather armour"
    assert armour["derived"] is True
    assert kesst.slots.get("armor") == [None]      # nothing was written to the store

    kesst.armour = "chainmail"
    armour = next(s for s in body_slots(kesst)["left"] if s["key"] == "armor")
    assert armour["items"][0]["item"] == "chainmail"


def test_the_filled_count_includes_the_derived_slots(kesst):
    """It reported "0 slots filled" on a page visibly showing leather armour, because it
    counted the store instead of the built slots."""
    assert body_slots(kesst)["filled"] == 1          # the armour
    kesst.set_slot("ring", 0, "ring of protection +1")
    assert body_slots(kesst)["filled"] == 2


def test_clearing_a_slot_empties_it(kesst):
    kesst.set_slot("neck", 0, "amulet of natural armour +1")
    assert kesst.slot_list("neck") == ["amulet of natural armour +1"]
    kesst.set_slot("neck", 0, "   ")
    assert kesst.slot_list("neck") == [None]


def test_the_last_slot_of_a_kind_cannot_be_removed(kesst):
    kesst.add_slot("neck")
    kesst.remove_slot("neck", 1)
    with pytest.raises(IllegalSheet, match="last slot"):
        kesst.remove_slot("neck", 0)


def test_removing_a_slot_takes_the_right_one(kesst):
    kesst.add_slot("ring")
    for i, item in enumerate(["a", "b", "c"]):
        kesst.set_slot("ring", i, item)
    kesst.remove_slot("ring", 1)
    assert kesst.slot_list("ring") == ["a", "c"]


def test_an_unknown_slot_is_refused(kesst):
    with pytest.raises(KeyError, match="no such body slot"):
        kesst.slot_list("cape")


def test_slots_survive_the_campaign_save(kesst):
    """The campaign round-trips through to_dict/from_dict on every turn."""
    kesst.add_slot("ring")
    kesst.set_slot("ring", 2, "ring of feather falling")
    kesst.set_slot("neck", 0, "amulet of natural armour +1")

    restored = from_dict(to_dict(kesst), ref="pc")
    assert restored.slot_list("ring") == [None, None, "ring of feather falling"]
    assert restored.slot_list("neck") == ["amulet of natural armour +1"]


def test_a_slot_the_build_no_longer_knows_is_dropped_on_load(kesst):
    """A save written by a future build with a slot this one has never heard of should
    load rather than crash — the unknown slot is simply not shown."""
    data = to_dict(kesst)
    data["slots"]["tail"] = ["ring of the monkey"]
    restored = from_dict(data, ref="pc")
    assert "tail" not in restored.slots

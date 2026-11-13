"""rules/volatility.py: a place's danger rating, read from the world or defaulted.

Owner, 2026-11-13: World Bible should rate places for danger and the rating should move
encounter and catastrophe chances. No shipped export carries the field yet, so the test
that matters most is that a world without it still answers (the default by ground), and
that a rating set on a nation reaches a city under it.
"""
from __future__ import annotations

from types import SimpleNamespace

from rules import volatility


class _World:
    def __init__(self, entities):
        self.entities = {e.id: e for e in entities}

    def get(self, entity_id):
        return self.entities.get(entity_id)

    def ancestors(self, entity_id):
        out, node = [], self.get(entity_id)
        while node and node.parent_id and self.get(node.parent_id):
            node = self.get(node.parent_id)
            out.append(node)
        return out


def _e(id_, parent=None, v=None, places=()):
    return SimpleNamespace(id=id_, parent_id=parent, volatility=v, places=list(places))


def test_a_world_without_the_field_defaults_by_ground():
    w = _World([_e("city1")])
    assert volatility.of(w, "city1~urban:the-market") == volatility.SETTLED_DEFAULT
    assert volatility.of(w, "city1~forest:@the-outskirts") == volatility.WILD_DEFAULT
    assert volatility.of(None, "city1~urban:the-market") == volatility.SETTLED_DEFAULT


def test_a_nations_rating_reaches_its_city_and_a_place_row_wins():
    w = _World([_e("nation", v=4), _e("city1", parent="nation",
                                      places=[{"id": "city1~urban:the-temple",
                                               "volatility": 0}])])
    assert volatility.of(w, "city1~urban:the-market") == 4
    assert volatility.of(w, "city1~urban:the-temple") == 0


def test_the_factor_is_the_published_rate_when_uneasy():
    assert volatility.factor(2) == 1.0
    assert volatility.factor(0) < 1.0 < volatility.factor(4)
    assert volatility.factor("nonsense") == 1.0

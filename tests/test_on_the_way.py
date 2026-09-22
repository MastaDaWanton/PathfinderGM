"""The way there is a thing that happens, and something can happen on it.

Two defects, both measured, both on 2026-09-21/22:

  1. The party stood at the roadside, said "I head into the city", and arrived at the
     market — two hops away through the gate and the square — having passed through
     nothing. `Place.exits` has been the move vocabulary since it was written and no
     code anywhere walked it. Measured across the two shipped worlds: 10,792 pairs of
     places have a route, the mean route is 2.726 hops, and 40 pairs have none at all.

  2. Nothing was ever rolled for crossing a town or a country. The only wandering check
     in the app was `gathering`'s, once per foraging expedition. A whole city could be
     walked end to end, every turn, for ever, and the streets were empty every time.
"""
from __future__ import annotations

import pytest

from rules import ontheway, places as places_mod
from rules.dice import Dice
from rules.places import Place


def _town():
    """Four places in a line: the way in — the square — the market — the lane."""
    return (
        Place(id="t~urban:the-way-in", name="the way in", about="", terrain="urban",
              exits=("t~urban:the-square",)),
        Place(id="t~urban:the-square", name="the square", about="", terrain="urban",
              exits=("t~urban:the-way-in", "t~urban:the-market")),
        Place(id="t~urban:the-market", name="the market", about="", terrain="urban",
              exits=("t~urban:the-square", "t~urban:the-lane")),
        Place(id="t~urban:the-lane", name="the lane", about="", terrain="urban",
              exits=("t~urban:the-market",)),
    )


class TestTheRoute:
    def test_the_way_across_town_is_every_place_between(self):
        town = _town()
        walk = places_mod.route(town, "t~urban:the-way-in", "t~urban:the-lane")
        assert [p.split(":")[-1] for p in walk] == ["the-square", "the-market", "the-lane"]

    def test_the_destination_is_the_last_hop_and_the_start_is_not_a_hop(self):
        town = _town()
        walk = places_mod.route(town, "t~urban:the-way-in", "t~urban:the-market")
        assert walk[-1] == "t~urban:the-market"
        assert "t~urban:the-way-in" not in walk

    def test_the_shortest_way_is_the_one_returned(self):
        """A ring: three hops the long way round, one the short way."""
        ring = (
            Place(id="r:a", name="a", about="", terrain="urban", exits=("r:b", "r:d")),
            Place(id="r:b", name="b", about="", terrain="urban", exits=("r:a", "r:c")),
            Place(id="r:c", name="c", about="", terrain="urban", exits=("r:b", "r:d")),
            Place(id="r:d", name="d", about="", terrain="urban", exits=("r:c", "r:a")),
        )
        assert places_mod.route(ring, "r:a", "r:d") == ("r:d",)

    def test_standing_where_you_are_going_is_no_route_at_all(self):
        town = _town()
        assert places_mod.route(town, "t~urban:the-market", "t~urban:the-market") == ()

    def test_a_place_with_no_path_to_it_answers_empty_and_not_a_guess(self):
        """40 of Aurvantis's 10,792 pairs are like this, and eight exit links are
        one-way. A caller that treated () as "refuse" would refuse moves that work."""
        town = _town() + (Place(id="t~urban:the-island", name="the island", about="",
                                terrain="urban", exits=()),)
        assert places_mod.route(town, "t~urban:the-square", "t~urban:the-island") == ()

    def test_every_shipped_settlement_can_be_crossed(self):
        """The measurement that set the street's odds, run as a test: if a world's
        places stop being connected the number in `ontheway` stops being true."""
        from world import loader

        w = loader.load("fixtures/pangrella-campaign.json")
        towns = w.of_kind("CITY") + w.of_kind("TOWN") + w.of_kind("VILLAGE")
        assert towns
        for s in towns:
            ps = places_mod.home_set(s)
            first = ps[0]
            for other in ps[1:]:
                assert places_mod.route(ps, first.id, other.id), \
                    f"{other.name} cannot be reached from {first.name} in {s.name}"


class _Fixed:
    """Dice that answer a written list in order, so a band can be aimed at."""

    def __init__(self, *faces):
        self.faces = list(faces)

    def roll(self, notation, modifiers=None, label="", visibility="hidden"):
        return Dice(seed=1).given(self.faces.pop(0), modifiers, label, notation)


class TestTheStreet:
    def test_most_hops_are_quiet(self):
        """8% per hop, derived from the published 20% per check and a measured mean
        route of 2.726 hops: 1 - 0.8 ** (1/2.726) = 0.0786."""
        dice = Dice(seed=7)
        hits = sum(1 for _ in range(2000) if ontheway.street(dice) is not None)
        assert 100 <= hits <= 220, hits          # 160 expected of 2000

    def test_a_crossing_of_average_length_comes_to_the_published_twenty_percent(self):
        quiet = (1 - ontheway.STREET_PERCENT / 100) ** 2.726
        assert 0.78 <= quiet <= 0.82

    def test_the_check_rolls_first_and_the_table_only_after_it_hits(self):
        """A quiet hop spends exactly one die. Two rolls, not one: the chance is
        derived from a published rate, the table is authored, and a single d100 would
        have tangled them into one number nobody could argue with separately."""
        dice = _Fixed(99)
        assert ontheway.street(dice) is None
        assert dice.faces == []

    def test_violence_is_four_bands_in_a_hundred(self):
        """The AD&D 1e city table's temper: beggars, pickpockets, brawls and the watch,
        and only rarely somebody who means it."""
        mean = [k for k, hi, *_ in ontheway.STREET if k == "trouble"]
        assert mean == ["trouble"]
        width = 100 - [hi for k, hi, *_ in ontheway.STREET if k == "cutpurse"][0]
        assert width == 4

    def test_the_cutpurse_is_grounded_in_the_corpus_and_not_invented(self):
        got = ontheway.street(_Fixed(1, 90), level=1)
        assert got is not None and got.kind == "cutpurse"
        assert got.template and got.template != "cutpurse"

    def test_the_bands_cover_the_whole_die(self):
        assert [hi for _k, hi, *_ in ontheway.STREET][-1] == 100
        for r in range(1, 101):
            assert ontheway._band(ontheway.STREET, r)


class TestTheRoad:
    def test_a_watch_is_six_hours_and_each_one_is_the_published_twenty_percent(self):
        """AoN, Step 4: Create Random Encounter Tables — "check four times per day ...
        with a 20% chance of an encounter each time". Used verbatim."""
        assert (ontheway.WATCH_HOURS, ontheway.ROAD_PERCENT) == (6, 20)
        assert 24 // ontheway.WATCH_HOURS == 4

    def test_a_quiet_road_rolls_once_a_watch_and_no_more(self):
        dice = _Fixed(50, 50)          # two watches, both missed
        assert ontheway.road(dice, hours=12, biome="plains") is None
        assert dice.faces == []

    def test_it_stops_rolling_at_the_first_hit(self):
        """"stop rolling if an encounter hits" — the party is not travelling any more."""
        dice = _Fixed(5, 70)           # watch one hits; band 70 is travellers
        got = ontheway.road(dice, hours=48, biome="plains")
        assert got is not None and got.after == 1
        assert dice.faces == []

    def test_a_part_watch_gets_a_part_share_of_the_check(self):
        """One hour outside the walls is not a dawn-to-noon march. Rounding every stub
        up to a whole watch would make the most common move in the game — the hour
        `_op_travel` charges for stepping outside — a 20% check every time."""
        dice = _Fixed(4)                      # 4 is under 20 and over the hour's share
        assert ontheway.road(dice, hours=1, biome="plains") is None
        dice = _Fixed(3, 70)                  # 3 is under the hour's share of 3
        assert ontheway.road(dice, hours=1, biome="plains") is not None

    def test_the_hours_walked_stop_where_the_meeting_did(self):
        met = ontheway.Meeting(kind="travellers", roll=70, after=2)
        assert ontheway.hours_walked(met, hours=30) == 12
        assert ontheway.hours_walked(met, hours=8) == 8     # a part-watch march
        assert ontheway.hours_walked(None, hours=30) == 30

    def test_what_lives_out_there_comes_from_the_book(self):
        got = ontheway.road(_Fixed(5, 10, 1), hours=6, biome="forest", level=1)
        assert got is not None and got.kind == "creature"
        assert got.creature and got.creature.get("name")
        assert got.creature.get("cr_value") is not None

    def test_ground_the_book_does_not_stock_is_not_silently_empty(self):
        """A biome with nothing in the CR window gives travellers, never a None that
        would have read as a quiet road after the check had already hit."""
        got = ontheway.road(_Fixed(5, 10), hours=6, biome="not-a-biome", level=1)
        assert got is not None and got.kind == "travellers"


class TestWhatItSays:
    @pytest.mark.parametrize("kind", [k for k, *_ in ontheway.STREET])
    def test_every_street_band_has_a_sentence(self, kind):
        said = ontheway.describe(ontheway.Meeting(kind=kind, roll=1), where="the lane")
        assert said and said[-1] == "."

    def test_the_sentence_names_no_name(self):
        """The engine has just created these people; introducing them is the
        narrator's job, and a name in a tell is a fact the prose then has to match."""
        met = ontheway.street(_Fixed(1, 30))
        assert met is not None
        assert "None" not in ontheway.describe(met)


class TestTheRestOfTheRoad:
    """The two bands the table shipped without, and the reason it shipped without them:
    "a washed-out ford, a toll, weather that costs a day — all of those want mechanics
    that do not exist yet, and an authored line with no teeth behind it is worse than no
    line". Both now have teeth the engine already had."""

    def test_the_bands_still_cover_the_whole_die(self):
        assert [hi for _k, hi in ontheway.ROAD][-1] == 100
        for r in range(1, 101):
            assert ontheway._band(ontheway.ROAD, r)

    def test_weather_brings_nobody(self):
        """The road itself is the meeting. A template drawn for it would have put a
        stranger in the rain with no reason to be there."""
        got = ontheway.road(_Fixed(5, 80), hours=6, biome="plains")
        assert got is not None and got.kind == "weather"
        assert got.count == 0 and not got.template

    def test_a_toll_brings_somebody_to_pay(self):
        got = ontheway.road(_Fixed(5, 95), hours=6, biome="plains")
        assert got is not None and got.kind == "toll"
        assert got.count == 1 and got.template

    def test_what_it_costs_is_hours_and_what_it_asks_is_coin(self):
        """Both are the engine's own currencies — `scene.advance` and `goods.spend` —
        and neither is a number invented for this table."""
        assert ontheway.WEATHER_HOURS and ontheway.TOLL_DICE

    def test_the_toll_is_asked_for_and_never_taken(self):
        """"Pay them or find another way" — the decision is the point of a toll, and an
        engine that deducted the coin would have made it a tax."""
        said = ontheway.describe(ontheway.Meeting(kind="toll", roll=95))
        assert "Pay them" in said


class TestTheWatchReadsTheWarrant:
    """The half the patrol band shipped without: a wanted character met the watch, was
    told they were looking at faces, and nothing followed."""

    def test_a_clean_name_gets_the_ordinary_patrol(self):
        said = ontheway.describe(ontheway.Meeting(kind="patrol", roll=80), law="")
        assert "You get no further" in said and "coming straight for you" not in said

    def test_a_suspected_name_is_looked_at_twice(self):
        said = ontheway.describe(ontheway.Meeting(kind="patrol", roll=80),
                                 law="suspected")
        assert "twice" in said

    def test_a_wanted_name_brings_them_at_you(self):
        said = ontheway.describe(ontheway.Meeting(kind="patrol", roll=80), law="wanted")
        assert "they have yours" in said and "coming straight for you" in said

    def test_the_law_is_only_read_by_the_patrol(self):
        """A beggar does not check your warrant."""
        for kind in ("press", "squabble", "hawker", "beggar", "cutpurse", "trouble"):
            plain = ontheway.describe(ontheway.Meeting(kind=kind, roll=1))
            wanted = ontheway.describe(ontheway.Meeting(kind=kind, roll=1), law="wanted")
            assert plain == wanted, kind

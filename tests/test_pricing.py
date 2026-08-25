"""What a thing is worth.

Measured against Sir Wantonious Maximus's real satchel — 34 crafted preparations, the
same ones an elderly woman at a market stall offered ten gold for and settled at
twenty-two.
"""
from __future__ import annotations

from rules import pricing


def jar(**kw):
    """A crafted preparation as the save actually stores it."""
    base = {"id": "x#1", "name": "X", "tier": "common", "potency": 1.0, "specs": []}
    return {**base, **kw}


def test_nothing_the_player_made_had_a_price_before_this():
    """The measurement that started it. 352 of the 663 raw materials carry an authored
    `price_gp` and the crafting bench reads it when you buy — but a tincture came off the
    bench with `potency`, `tier` and `rank` and no value field at all, so the one thing a
    herbalist actually produces was the one thing the game could not put a number on."""
    assert pricing.worth(jar(tier="rare", potency=5.8, specs=[{"type": "heal"}])) > 0


def test_a_thousandfold_potency_gap_becomes_a_two_hundredfold_price_gap():
    """The two extremes of one real shelf: a plain Yarow elixir at potency 1.25 against
    the Blackthorn purified draught at 1,335.61 — brewed by the same character, carried in
    the same satchel.

    Linear pricing makes the draught worth more than every reward in the campaign put
    together. A flat rarity band throws away the work that got it to 1,335. The chosen
    exponent keeps both true: it is plainly a treasure and it does not end the economy."""
    weak = pricing.worth(jar(tier="uncommon", potency=1.25, specs=[{"type": "heal"}]))
    strong = pricing.worth(jar(tier="uncommon", potency=1335.61,
                               specs=[{"type": "heal"}] * 4))
    ratio = strong / weak
    assert 1000 < strong / 1 < 2000, f"the draught came out at {strong}"
    assert 150 < ratio < 300, f"a thousandfold potency gap became {ratio:.0f}x in price"


def test_a_bottle_that_does_nothing_is_priced_as_a_bottle_that_does_nothing():
    """Over half the preparations in the live save read "nothing the engine can run" —
    they carry no executable spec, and no amount of potency makes them do anything.
    Measured on two tier-3 rares of identical potency from the same satchel: Firesnap
    Powder has one spec, Hawthorn Powder has none."""
    doing = jar(tier="rare", potency=5.8, specs=[{"type": "apply_condition"}])
    inert = jar(tier="rare", potency=5.8, specs=[])
    # Rounded to the copper on both sides — `worth` rounds once at the end, so
    # comparing against an unrounded product is off by fractions of a copper.
    assert pricing.worth(inert) == round(pricing.worth(doing) * pricing.INERT_FACTOR, 2)
    assert pricing.worth(inert) < pricing.worth(doing)


def test_the_prose_is_not_the_effect():
    """`specs` is the executable form; `effects` is the prose it was converted from. A jar
    can carry three lines of description and no spec at all — that is exactly what the
    bench prints as "nothing the engine can run" — and pricing the prose would pay full
    medicine price for a bottle of nothing."""
    talks = jar(tier="rare", potency=5.8, specs=[],
                effects=["Hawthorn: steadies the heart", "and calms the breath"])
    assert pricing.worth(talks) == pricing.worth(jar(tier="rare", potency=5.8, specs=[]))


def test_an_authored_price_wins_outright():
    """`price_gp` is a fact somebody wrote down about a real material — quicklime is 1gp
    because the catalogue says so. A formula that overrode it would be guessing over the
    top of an answer it already had."""
    assert pricing.worth({"id": "quicklime", "tier": "common", "price_gp": 1}) == 1.0
    assert pricing.worth({"id": "adamantine", "tier": "legendary", "price_gp": 3000}) == 3000


def test_rarity_climbs_and_nothing_untiered_is_sold_as_a_legendary():
    ladder = [pricing.worth(jar(tier=t, specs=[{"type": "heal"}]))
              for t in ("common", "uncommon", "rare", "exotic", "legendary")]
    assert ladder == sorted(ladder)
    # Anything the benches did not tier is common. The only safe direction.
    assert (pricing.worth(jar(tier="", specs=[{"type": "heal"}]))
            == pricing.worth(jar(tier="common", specs=[{"type": "heal"}])))


def test_a_shop_pays_half_so_a_haggle_has_room():
    it = jar(tier="rare", potency=5.8, specs=[{"type": "heal"}])
    assert pricing.what_a_shop_pays(it) == round(pricing.worth(it) * 0.5, 2)


def test_fractions_of_a_gold_piece_are_still_money():
    """A common inert preparation is worth about half a gold piece. Rounding that to
    "0 gp" would make a satchel of them free to take."""
    assert pricing.coin(0.5) == {"gp": 0, "sp": 5, "cp": 0}
    assert pricing.as_text(0.5) == "5 sp"
    assert pricing.as_text(1325.6) == "1,325 gp 6 sp"
    assert pricing.as_text(0) == "0 cp"


def test_the_whole_satchel_is_worth_far_more_than_twenty_two_gold():
    """The scene that prompted all of this. Thirty-four preparations including a
    potency-1,335 draught, and the offer was ten gold for the lot.

    She was not being stingy — nothing had reached her. Every turn of that haggle resolved
    to `narrate_only` and the purse was still empty afterwards."""
    satchel = [jar(tier="uncommon", potency=1335.61, specs=[{"type": "heal"}] * 4),
               jar(tier="legendary", potency=8.0, specs=[{"type": "save_gate"}]),
               *[jar(tier="rare", potency=5.8, specs=[{"type": "heal"}]) for _ in range(5)],
               *[jar(tier="common", potency=1.45, specs=[]) for _ in range(27)]]
    total = sum(pricing.worth(i) for i in satchel)
    assert total > 2000, f"the satchel came to {pricing.as_text(total)}"
    assert sum(pricing.what_a_shop_pays(i) for i in satchel) > 22

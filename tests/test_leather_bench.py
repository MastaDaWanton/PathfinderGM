"""The leather bench, rules side (docs/leatherworking-revamp-plan.md §6-§13, §17, §23.1 E;
docs/leatherworking-contracts.md §7, lane E).

Built on the merged lanes: lane D's material documents (`rules/materials.py`), lane B's
build (`rules/forge_items.py`) and lane G's places. Where a test needs a place it hands
`plan_step` the dict `places.leather_bench_here` answers, so the rules are tested apart
from the map. Each test names the defect it prevents, with the measurement where there was
one (docs/leatherworking-inventory.md, "Inv").
"""
from __future__ import annotations

import pytest

from rules import forge_items, inprogress
from rules import leatherworker as lw
from rules import worldclass as wc
from rules.sheet import from_dict, load_pc, to_dict
from rules.tables import ARMOUR

FIELD = {"at": "field", "tannery": None, "field_kit": True,
         "tiers": ("common", "uncommon"), "vats": False}
TANNERY = {"at": "tannery",
           "tannery": {"kind": "town", "place": "loc~urban:the-tannery", "keeper": None,
                       "rate_cp_per_hour": 10, "vat_rate_cp_per_day": 20, "vats": 4,
                       "vats_free": 0, "vat_units": 4},
           "field_kit": False, "tiers": ("common", "uncommon", "rare", "exotic", "legendary"),
           "vats": True, "name": "the tannery"}
NOWHERE = {"at": None, "tannery": None, "field_kit": False, "tiers": (), "vats": False}


@pytest.fixture
def pc():
    a = load_pc("fixtures/pc-kesst.json")
    a.inventory.clear()
    a.stock.clear()
    a.herb_known.clear()
    return a


def _level(pc, n: int):
    pc.track(lw.TRACK_ID).level = n
    return pc.track(lw.TRACK_ID)


def _rack(pc, now=0):
    return {p.key: p for p in lw.rack(pc, now)}


def _key(pc, form, *, material=None, pattern=None, part=None, now=0):
    for p in lw.rack(pc, now):
        if p.form != form:
            continue
        if material and p.material != material:
            continue
        if pattern and (p.hide is None or p.hide.pattern != pattern):
            continue
        if part and (p.hide is None or p.hide.part != part):
            continue
        return p.key
    raise AssertionError(f"no {form} on the rack: {[(p.key, p.form) for p in lw.rack(pc, now)]}")


def plan(pc, method, slots, *, where=FIELD, now=0, batch=1, **kw):
    rack = _rack(pc, now)
    s = {k: (rack[v] if isinstance(v, str) else rack[v[0]], 1 if isinstance(v, str) else v[1])
         for k, v in slots.items()}
    return lw.plan_step(pc, pc.track(lw.TRACK_ID), method, s, batch, where=where, now=now,
                        **kw)


def do(pc, p, tier=2, *, now=0, where=FIELD):
    assert not p.problems, p.problems
    made = lw.make(p, tier, now=now)
    lw.spend(pc, p.consumes)
    return lw.land(pc, p, made, now=now, where=where, setup_score=0.5)


def put(pc, form, material, **kw):
    h = lw.Hide(form=form, material=material, **kw)
    return f"stock:{lw.put_hide(pc, h)}"


# --- the shelf: every stage lands, and a bought hide is sold tanned --------------------------

def test_a_bought_hide_is_tanned_oak_bark_grade_2_by_its_size(pc):
    """A counter sells a hide tanned, never green (Harvest Parts; plan §9). Lane D's
    proposal: the document's `sold_as` form, oak bark, grade 2, units by size (plan §5.5).
    Measured before (Inv §0.5): a bought hide was a bare count with no form, no grade and no
    units, so every piece was flense-to-finish in one session."""
    pc.carry("deer-hide", 2)
    pc.carry("wolf-pelt", 1)
    pc.carry("horse-hide", 1)
    rack = _rack(pc)
    deer, wolf, horse = rack["inv:deer-hide"], rack["inv:wolf-pelt"], rack["inv:horse-hide"]
    assert (deer.form, deer.hide.tannage, deer.hide.grade, deer.quarters) == \
        ("leather", "oak-bark", 2, 4)
    assert wolf.form == "fur"                           # furred: tanned hair-on
    assert horse.quarters == 8                          # Large: two units
    assert not lw.freshness(deer.hide, 10 ** 6)["spoiled"], "tanned leather never spoils"


def test_lane_cs_green_hide_carries_its_48_hour_clock_and_salt_stops_it(pc):
    """Plan §6: the clock starts at the harvest and salt stops it. Measured (Inv §0.3):
    `picked_at` was None for everything skinned, so no clock ever ran. A green hide written
    through `put_hide` (lane C's door) spoils at 48 hours, not 47; salted, it keeps."""
    put(pc, "green", "deer-hide", quarters=4, grade=2, harvested_at=0)
    h = next(iter(lw.rack(pc))).hide
    assert lw.freshness(h, 47 * 60)["hours_left"] == 1
    assert not lw.freshness(h, 47 * 60 + 59)["spoiled"]
    assert lw.freshness(h, 48 * 60)["spoiled"]
    assert lw.rack(pc, 48 * 60)[0].spoiled
    salted = h.copy()
    salted.salted_at = 60
    assert not lw.freshness(salted, 30 * 24 * 60)["spoiled"], "six weeks salted"


def test_salt_takes_one_measure_a_unit_and_stamps_the_minute(pc):
    """Salt costs salt (owner answer 8, 2026-10-08): one measure per hide unit. The old Cure
    needed no salt at all (questions doc: "cure still needs no salt")."""
    put(pc, "green", "horse-hide", quarters=8, grade=2, harvested_at=0)
    pc.carry("curing-salt", 5)
    hide = _key(pc, "green")
    p = plan(pc, "salt", {"hide": hide, "salt": "inv:curing-salt"}, now=600)
    assert {pp.key: n for pp, n in p.consumes}["inv:curing-salt"] == 2
    do(pc, p, now=600)
    salted = next(x for x in lw.rack(pc, 600) if x.form == "salted")
    assert salted.hide.salted_at == 600
    assert pc.inventory["curing-salt"] == 3


def test_flense_then_brain_tan_in_the_field_with_no_wait(pc):
    """Level 1 field work (plan §17.1): flense a green hide, brain-tan the pelt at the kit.
    Brain tanning is a day of bench work and no wait (plan §8.1); the leather comes off the
    clock for good."""
    put(pc, "green", "deer-hide", quarters=4, grade=2, harvested_at=0)
    pc.carry("brain-paste", 2)
    do(pc, plan(pc, "flense", {"hide": _key(pc, "green")}))
    pelt = _key(pc, "pelt")
    p = plan(pc, "tan", {"hide": pelt, "tannin": "inv:brain-paste"})
    assert p.wait_minutes == 0 and p.minutes == 480
    do(pc, p)
    leather = next(x for x in lw.rack(pc) if x.form == "leather")
    assert leather.hide.tannage == "brain-paste" and leather.hide.harvested_at is None


def test_no_tannin_dries_rawhide_in_the_pack(pc):
    """Rawhide (plan §8.1): no tannin, stretched and dried, In progress carried: a day until
    the owner shortened the tan (2026-10-09), four hours now."""
    put(pc, "pelt", "deer-hide", quarters=4, grade=2)
    p = plan(pc, "tan", {"hide": _key(pc, "pelt")})
    assert (p.tannage, p.wait_minutes, p.wait_where) == ("rawhide", 240, "carried")
    got = do(pc, p)
    item = pc.stock[got[0]["key"]]
    block = inprogress.work_of(item, 0)
    assert block["where"] == "carried"
    assert "vats" not in block["result"], "a hide drying in the pack fills no vat"


# --- tanning in game time (plan §8) -----------------------------------------------------------

def test_a_tannage_is_not_collectable_before_its_minute(pc):
    """Plan §23.1 E: advance the clock to one minute short, then to the minute. Measured
    before (Inv §0.5): tanning was instant, so the tannin's time meant nothing."""
    _level(pc, 2)
    put(pc, "pelt", "deer-hide", quarters=4, grade=2)
    pc.carry("oak-bark", 1)
    p = plan(pc, "tan", {"hide": _key(pc, "pelt"), "tannin": "inv:oak-bark"},
             where=TANNERY)
    # Bark: 4 days 16 hours (the owner's shortened tan, 2026-10-09), slow_tan on oak x1.5,
    # fast_tan on deer x0.5.
    assert p.wait_minutes == int(round(6720 * 1.5 * 0.5))
    assert p.vats == 1
    got = do(pc, p, now=0, where=TANNERY)
    key, ready = got[0]["key"], got[0]["ready_at"]
    here = TANNERY["tannery"]["place"]
    early = inprogress.collect(pc, key, now=ready - 1, here=here)
    assert early["ok"] is False and "not ready yet" in early["why"]
    elsewhere = inprogress.collect(pc, key, now=ready, here="somewhere-else")
    assert elsewhere["ok"] is False and "Collect it at" in elsewhere["why"]
    done = inprogress.collect(pc, key, now=ready, here=here)
    assert done["ok"], done
    assert pc.stock[key].properties and not inprogress.work_of(pc.stock[key], ready)


# The waits before the owner's "shorten the tan" (2026-10-09), in minutes.
_OLD_WAITS = {"brain": 0, "rawhide": 1440, "mineral": 4320, "alum": 10080, "bark": 40320,
              "planar": 60480}
_OLD_THICK_BARK = 80640


def test_an_oak_bark_tan_took_42_days_and_now_takes_a_week(pc):
    """The final pass (2026-10-09) took a harvested hide to leather armour and measured it: a
    bark tan took 42 days in the vat (bark's 4 weeks x oak bark's slow_tan 1.5), 8 gp 4 sp of
    vat rent, before the hide could be hardened. The owner: "shorten the tan". Every wait is
    divided by six, so an oak-bark tan of a wolf pelt (no time trait of its own) is 7 days,
    and the order and ratios of the six tannages are what they were: fast ones stay fast,
    planar stays the longest of the plain waits."""
    rows = lw.bench_rules()["tannages"]
    for kind, old in _OLD_WAITS.items():
        assert int(rows[kind]["wait_minutes"]) * 6 == old, kind
    assert int(rows["bark"]["thick_wait_minutes"]) * 6 == _OLD_THICK_BARK
    order = sorted(_OLD_WAITS, key=lambda k: (int(rows[k]["wait_minutes"]), k))
    assert order == sorted(_OLD_WAITS, key=lambda k: (_OLD_WAITS[k], k))
    assert order[-1] == "planar"

    _level(pc, 2)
    put(pc, "pelt", "wolf-pelt", quarters=4, grade=2)
    pc.carry("oak-bark", 1)
    p = plan(pc, "tan", {"hide": _key(pc, "pelt"), "tannin": "inv:oak-bark"},
             where=TANNERY)
    assert p.problems == [], p.problems
    assert p.wait_minutes == 7 * 1440, "an oak-bark tan was 42 days (60480 minutes)"
    assert lw.tan_wait("bark", ["slow_tan"]) == p.wait_minutes
    assert "Then 7 days in the vat." in p.info
    # The rent is by the day, so it fell with the wait: one vat at the town's 2 sp a day.
    from rules import market

    assert p.vats == 1
    assert market.vat_cost(p.wait_minutes / 1440, p.vats) == 140
    assert market.vat_cost(60480 / 1440, 1) == 840


def test_the_cut_test_decides_the_tier_with_the_setup_half(pc):
    """The tan game in two halves (plan §8.3, UI §9): the tier comes from the strength steps
    at setup and the cut test at collection, under the ceiling the setup was worked at."""
    _level(pc, 2)
    put(pc, "pelt", "deer-hide", quarters=4, grade=1)
    pc.carry("oak-bark", 1)
    p = plan(pc, "tan", {"hide": _key(pc, "pelt"), "tannin": "inv:oak-bark"}, where=TANNERY)
    made = lw.make(p, 0)
    lw.spend(pc, p.consumes)
    got = lw.land(pc, p, made, now=0, where=TANNERY, setup_score=1.0)
    item = pc.stock[got[0]["key"]]
    block = inprogress.work_of(item, 0)
    block["result"]["cut_score"] = 1.0
    out = inprogress.collect(pc, got[0]["key"], now=got[0]["ready_at"],
                             here=TANNERY["tannery"]["place"])
    assert out["ok"]
    assert lw.Hide.from_stock(item).quality == p.step_ceiling


def test_bark_tanning_is_level_1_in_the_field_kit_and_waits_in_the_pack(pc):
    """The owner's "sure why not" (2026-10-09). Until then this test pinned "Bark tanning is
    learned at Leatherworker 2" and "needs a tannery": leather armour's body is hardened
    plates, Harden takes only bark- or planar-tanned leather, and bark was a level-2 tannage
    in a tannery's vat, so the final pass measured that a level-1 field leatherworker could
    make leather armour only from a BOUGHT hide (sold oak-bark tanned), never one they
    harvested. Now a level-1 leatherworker with the field kit bark-tans a fleshed wolf pelt
    with oak bark: In progress in the pack for the bark wait (oak's slow_tan, 7 days), no vat,
    no rent, collected anywhere — then cuts, hardens in the kit's kettle and assembles
    leather armour, every step at level 1 in the field."""
    assert lw.tannage_row("bark")["level"] == 1 and lw.tannage_row("bark")["where"] == "kit"
    for n in range(3):
        put(pc, "green", "wolf-pelt", quarters=4, grade=2, harvested_at=0)
        do(pc, plan(pc, "flense", {"hide": _key(pc, "green")}))
    pc.carry("oak-bark", 3)
    pelt = _key(pc, "pelt")
    p = plan(pc, "tan", {"hide": (pelt, 3), "tannin": "inv:oak-bark"}, batch=3, hair=False)
    assert p.problems == [], p.problems
    assert p.wait_minutes == 7 * 1440 and p.wait_where == "carried" and p.vats == 0
    assert "Then 7 days in your pack." in p.info, p.info
    assert lw.vat_rent_cp(None, FIELD, p.wait_minutes, p.vats) == 0
    got = do(pc, p, now=0)
    key, ready = got[0]["key"], got[0]["ready_at"]
    block = inprogress.work_of(pc.stock[key], 0)
    assert block["where"] == "carried" and block["result"]["vat"] is False
    assert inprogress.collect(pc, key, now=ready - 1, here="loc~wild:anywhere")["ok"] is False
    done = inprogress.collect(pc, key, now=ready, here="loc~wild:anywhere")
    assert done["ok"], done
    leather = _key(pc, "leather", material="wolf-pelt", now=ready)
    assert lw.Hide.from_stock(pc.stock[leather.split(":", 1)[1]]).tannage == "oak-bark"

    # Cut the suit's body (two wolves, Medium) and the lacing, harden the body, assemble.
    do(pc, plan(pc, "cut", {"hide": (leather, 2)}, product="leather armour", now=ready),
       now=ready)
    do(pc, plan(pc, "cut", {"hide": _key(pc, "leather", material="wolf-pelt", now=ready)},
                product="lacing", now=ready), now=ready)
    body = _key(pc, "panel", pattern="leather armour", now=ready)
    do(pc, plan(pc, "harden", {"piece": body}, now=ready), now=ready)
    plates = _key(pc, "plate", pattern="leather armour", now=ready)
    lacing = _key(pc, "lacing", now=ready)
    p = plan(pc, "assemble", {"body": plates, "fastenings": lacing}, masterwork=False,
             now=ready)
    assert p.problems == [], p.problems
    rec = do(pc, p, now=ready)[0]["record"]
    assert rec["base"] == "leather" and not forge_items.build(rec)["problems"]


def test_a_bark_tan_begun_at_a_tannery_still_goes_in_its_vat(pc):
    """What the tannery keeps for bark (2026-10-09): begun there, at level 1 now, the tan
    goes into a rented vat and is collected there, as before the ruling. The plan gave the
    vat no other advantage for bark — the wait is the pack's to the minute."""
    put(pc, "pelt", "wolf-pelt", quarters=4, grade=2)
    pc.carry("oak-bark", 1)
    slots = {"hide": _key(pc, "pelt"), "tannin": "inv:oak-bark"}
    vat = plan(pc, "tan", slots, where=TANNERY, hair=False)
    pack = plan(pc, "tan", slots, hair=False)
    assert vat.problems == [] and (vat.wait_where, vat.vats) == ("tannery", 1)
    assert vat.wait_minutes == pack.wait_minutes and vat.step_ceiling == pack.step_ceiling
    assert "in the vat" in vat.info


def test_mineral_tanning_is_still_level_2_and_a_tannerys(pc):
    """What stayed the tannery's when bark moved to the kit: mineral (and planar) still sit
    in a tannery's vat, mineral at Leatherworker 2. Each refusal says why in words."""
    put(pc, "pelt", "deer-hide", quarters=4, grade=2)
    pc.carry("salamander-ash-lye", 1)
    p = plan(pc, "tan", {"hide": _key(pc, "pelt"), "tannin": "inv:salamander-ash-lye"})
    assert any("Leatherworker 2" in x for x in p.problems), p.problems
    _level(pc, 2)
    p = plan(pc, "tan", {"hide": _key(pc, "pelt"), "tannin": "inv:salamander-ash-lye"})
    assert any("needs a tannery" in x for x in p.problems), p.problems


def test_no_vat_cap_a_full_tannery_still_takes_the_hides(pc):
    """The lead's ruling, 2026-10-08 (the owner's "no limit to how many things are
    crafting"): lane G proposed four vats and a "the vats here are full" refusal. A tannery
    whose every vat is in use (`vats_free` 0) still takes a tannage; the vats it needs are
    counted and rented, never a gate."""
    _level(pc, 2)
    put(pc, "pelt", "frostfallen-bison-hide", quarters=16, grade=2)
    pc.carry("oak-bark", 4)
    p = plan(pc, "tan", {"hide": _key(pc, "pelt"), "tannin": "inv:oak-bark"},
             where=TANNERY)
    assert not p.problems, p.problems
    assert p.vats == 1 and TANNERY["tannery"]["vats_free"] == 0
    assert not any("full" in x for x in p.problems)


def test_the_tannin_must_be_within_one_tier_of_the_hide(pc):
    """Today's rule, the one that worked (Inv §1): oak bark does not bite dragonhide."""
    _level(pc, 3)
    put(pc, "pelt", "red-dragonhide", quarters=8, grade=2)
    pc.carry("oak-bark", 2)
    p = plan(pc, "tan", {"hide": _key(pc, "pelt"), "tannin": "inv:oak-bark"},
             where=TANNERY)
    assert any("within one tier" in x for x in p.problems), p.problems


def test_a_thick_hide_is_limed_in_a_tannerys_pit(pc):
    """Plan §7: a thick hide's flense is a 3-day lime pit, a tannery's, In progress there."""
    put(pc, "green", "elk-hide", quarters=8, grade=2, harvested_at=0)
    p = plan(pc, "flense", {"hide": _key(pc, "green")})
    assert any("lime pit" in x for x in p.problems), p.problems
    p = plan(pc, "flense", {"hide": _key(pc, "green")}, where=TANNERY)
    assert (p.wait_minutes, p.wait_where) == (4320, "tannery")
    got = do(pc, p, where=TANNERY)
    block = inprogress.work_of(pc.stock[got[0]["key"]], 0)
    assert block["where"] == f"place:{TANNERY['tannery']['place']}"
    assert block["result"]["vat"] is False, "the lime pit fills no vat"


# --- Harden: no wax, vegetable leather only, the kit's small kettle -----------------------------

def test_harden_refuses_alum_and_brain_leather_and_needs_no_wax(pc):
    """Plan §7 and §23.1 E: "Harden's one enforced input was the wrong one" — the old bench
    refused Harden without a wax (`rules/leatherworker.py:916`), when cuir bouilli is water
    and heat on vegetable-tanned leather (prior art §3.5). Alum and brain leather are refused
    with the reason; bark leather hardens with nothing else on the bench."""
    for tannin, why in (("tawing-alum", "alum leather softens in water"),
                        ("brain-paste", "brain-tanned leather is soft")):
        key = put(pc, "panel", "deer-hide", quarters=8, grade=2, tannage=tannin,
                  pattern="leather armour", part="body")
        p = plan(pc, "harden", {"piece": key})
        assert any(why in x for x in p.problems), (tannin, p.problems)
    key = put(pc, "panel", "goat-hide", quarters=8, grade=2, tannage="oak-bark",
              pattern="leather armour", part="body")
    p = plan(pc, "harden", {"piece": key})
    assert not p.problems, p.problems
    assert lw.METHOD_SLOTS["harden"] == ("piece",), "no wax slot"


def test_the_kits_small_kettle_hardens_common_hides_and_not_rare(pc):
    """The owner's answer 3 (2026-10-08): "add a small kettle to the field kit" — the kit
    Hardens common and uncommon hides, so plain leather armour is makeable at level 1 in the
    field; rare and up still need the tannery's kettle."""
    assert lw.method_level("harden") == 1
    key = put(pc, "panel", "deer-hide", quarters=8, grade=2, tannage="oak-bark",
              pattern="leather armour", part="body")
    assert not plan(pc, "harden", {"piece": key}).problems
    _level(pc, 2)
    rare = put(pc, "panel", "manticore-hide", quarters=8, grade=2, tannage="ironbark-tannin",
               pattern="leather armour", part="body")
    p = plan(pc, "harden", {"piece": rare})
    assert any("need a tannery" in x for x in p.problems), p.problems
    assert not plan(pc, "harden", {"piece": rare}, where=TANNERY).problems


# --- the Craft rule on failure (plan §11) --------------------------------------------------------

def test_a_fail_by_4_keeps_every_input_and_by_5_ruins_half(pc):
    """The book's Craft rule: a fail by 4 or less loses the time and nothing else; by 5 or
    more half the raw materials. Measured (Inv §1, `play/craft_views.py:656`): the old bench
    spent every input on any failure."""
    put(pc, "green", "deer-hide", quarters=4, grade=2, harvested_at=0)
    pc.carry("curing-salt", 4)
    p = plan(pc, "salt", {"hide": _key(pc, "green"), "salt": "inv:curing-salt"})
    assert lw.failure_losses(p, 4) == []
    lost = lw.failure_losses(p, 5)
    assert sum(n for _, n in lost) == 1, "half of two, rounded down"
    assert lost[0][0].key == "inv:curing-salt", "the cheaper thing goes first"


def test_a_minigame_miss_after_a_success_takes_nothing_more(pc):
    """Plan §11: "a minigame miss after a successful roll never takes materials; only the
    d20 does". A score of 0 makes the product at Crude and spends exactly the step's
    inputs."""
    pc.carry("deer-hide", 2)
    p = plan(pc, "cut", {"hide": "inv:deer-hide"}, product="leather armour")
    want = {pp.key: n for pp, n in p.consumes}
    do(pc, p, tier=0)
    assert want == {"inv:deer-hide": 2}
    assert "deer-hide" not in pc.inventory
    panels = next(x for x in lw.rack(pc) if x.form == "panel")
    assert panels.hide.quality == 0


# --- Cut, Stitch, Laminate (plan §5.5, §7, §12) ---------------------------------------------------

def test_cut_combines_hides_of_one_kind_and_returns_the_offcut(pc):
    """Plan §5.5: a Medium suit's body is 2 units, one Large hide or two Medium; smaller
    hides combine at Cut. The offcut goes back on the rack, never lost."""
    pc.carry("deer-hide", 1)
    p = plan(pc, "cut", {"hide": "inv:deer-hide"}, product="leather armour")
    assert any("carry more of it" in x for x in p.problems), p.problems
    pc.carry("horse-hide", 1)
    p = plan(pc, "cut", {"hide": "inv:horse-hide"}, product="boots")
    do(pc, p)
    forms = sorted((x.form, x.quarters) for x in lw.rack(pc) if x.material == "horse-hide")
    assert forms == [("leather", 6), ("panel", 2)]


def test_a_grip_is_cut_only_from_a_grip_capable_hide(pc):
    """Owner Q3.1 and Q7.4: grips come from grip-capable hides, and the forge takes them."""
    pc.carry("deer-hide", 1)
    pc.carry("viper-skin", 1)
    assert any("does not make a grip" in x
               for x in plan(pc, "cut", {"hide": "inv:deer-hide"}, product="grip").problems)
    assert not plan(pc, "cut", {"hide": "inv:viper-skin"}, product="grip").problems


def test_laminate_takes_two_of_one_leather_and_records_a_pass(pc):
    """Plan §12: two leathers of one material and tannage into one of the same units, a
    strengthening pass the build multiplies by 1.5."""
    _level(pc, 2)
    pc.carry("deer-hide", 1)
    p = plan(pc, "laminate", {"piece": "inv:deer-hide"})
    assert any("takes two" in x for x in p.problems)
    pc.carry("deer-hide", 1)
    p = plan(pc, "laminate", {"piece": "inv:deer-hide"})
    do(pc, p)
    out = next(x for x in lw.rack(pc) if x.material == "deer-hide")
    assert (out.count, out.hide.passes, out.quarters) == (1, 1, 4)


# --- the step ceiling (plan §5.7, §11) -------------------------------------------------------------

def test_a_grade_3_hide_cannot_make_better_than_fine(pc):
    """Plan §5.7 (Wurm Online's rule on the UNIDO grades): grade 3 caps the work at Fine,
    whatever the hands could do, and the cap is said in words."""
    _level(pc, 3)
    key = put(pc, "leather", "deer-hide", quarters=4, grade=3, tannage="willow-bark")
    p = plan(pc, "cut", {"hide": key}, product="cloak")
    assert p.step_ceiling == 2 and p.grade_cap == 2
    assert any("grade 3" in w for w in p.ceiling_why)
    made = lw.make(p, 9)
    assert made[0][0].quality == 2


def test_the_tannins_ceiling_trait_moves_the_ceiling(pc):
    """Plan §8.1: ceiling_up +1 (oak, tara, ironbark), ceiling_down −1 (willow, alum)."""
    _level(pc, 2)
    up = put(pc, "leather", "deer-hide", quarters=4, grade=1, tannage="oak-bark")
    down = put(pc, "leather", "goat-hide", quarters=4, grade=1, tannage="willow-bark")
    hands = wc.ceiling_index(pc.track(lw.TRACK_ID))
    assert plan(pc, "cut", {"hide": up}, product="cloak").step_ceiling == hands + 1
    assert plan(pc, "cut", {"hide": down}, product="cloak").step_ceiling == hands - 1


# --- Assemble: the record, masterwork by the book, DCs (plan §7, §13) ----------------------------

def _suit(pc, body_material="deer-hide", *, product="leather armour", form="plate",
          tannage="oak-bark", quality=2, grade=1, worked=None, passes=0, creature=""):
    body = put(pc, form, body_material, quarters=8, grade=grade, tannage=tannage,
               quality=quality, passes=passes, pattern=product, part="body",
               worked=list(worked if worked is not None else
                           (["stitch"] if form == "panel" else ["harden"])),
               creature=creature)
    lacing = put(pc, "lacing", "deer-hide", quarters=1, grade=1, tannage="oak-bark",
                 quality=2)
    return body, lacing


def test_assemble_writes_the_forges_record_with_a_table_key(pc):
    """Plan §13.1: the record is the forge's (pieces, gear, a table key in `base`). Measured
    (Inv §0.1): the old bench put the item's NAME in `base`, and the suit was "not built on
    any suit the rules know". The lacing's piece says what it is; nothing computed is
    stored."""
    body, lacing = _suit(pc)
    p = plan(pc, "assemble", {"body": body, "fastenings": lacing}, masterwork=False)
    assert p.dc == 10 + ARMOUR["leather"]["ac"]
    got = do(pc, p, tier=2)
    rec = got[0]["record"]
    assert rec["base"] == "leather" and rec["base"] in ARMOUR
    assert (rec["gear"], rec["slot"], rec["craft"]) == ("armour", "armor", "leatherworker")
    assert rec["pieces"]["body"]["material"] == "deer-hide"
    assert rec["pieces"]["fastenings"]["form"] == "lacing"
    assert rec["base_for"] == ["studded leather", "armored coat"]
    # The consumables it was worked with, one per kind (plan §14.6): oak bark has no mark,
    # and the record does not say so, which is the tanner's to learn by Grade.
    assert rec["marks"] == ["oak-bark"]
    assert not forge_items.build(rec)["problems"]
    st = next(s for s in pc.stock.values() if getattr(s, "record", None))
    back = from_dict(to_dict(pc))
    assert any(getattr(s, "record", {}).get("id") == rec["id"]
               for s in back.stock.values()), "the record survives a save"
    assert st.slot == "armor"


def test_a_dragonhide_suit_is_masterwork_at_sound(pc):
    """Owner Q3.4, the book wins. Measured (Inv §0.7): a dragonhide suit was not masterwork
    without the Tool step. At Sound, with no DC 20 asked: masterwork by its nature."""
    _level(pc, 3)
    body, lacing = _suit(pc, "red-dragonhide", product="hide armour", form="panel",
                         tannage="dragonblood-tannin", quality=1)
    p = plan(pc, "assemble", {"body": body, "fastenings": lacing}, where=TANNERY)
    assert not p.problems, p.problems
    assert p.always_masterwork and p.masterwork_why == "masterwork by its nature"
    got = do(pc, p, tier=1, where=TANNERY)
    rec = got[0]["record"]
    assert rec["quality_index"] == 1 and rec["masterwork"] is True
    assert forge_items.build(rec)["masterwork"] is True


def test_no_dc_creep_a_red_dragonhide_suit_is_the_books_dc(pc):
    """Plan §7: the book's Craft DC, 10 + the armour bonus. Measured (Inv §1): the old chain
    asked DC 38 for a red dragonhide suit (5 + 5 x tier + 2 a stage)."""
    _level(pc, 3)
    body, lacing = _suit(pc, "red-dragonhide", product="hide armour", form="panel",
                         tannage="dragonblood-tannin")
    p = plan(pc, "assemble", {"body": body, "fastenings": lacing}, where=TANNERY)
    assert p.dc == 10 + ARMOUR["hide armour"]["ac"] == 14


def test_masterwork_needs_a_curried_soft_body_and_flawless_a_tooled_one(pc):
    """Plan §13.4: Superior at Assemble needs a masterwork-ready body (hardened plates, or a
    curried soft body), else the work stops at Fine; aiming adds the book's DC 20. Flawless
    needs a tooled body (plan §7, proposed)."""
    _level(pc, 3)
    soft, lacing = _suit(pc, "elk-hide", product="hide armour", form="panel", quality=4)
    p = plan(pc, "assemble", {"body": soft, "fastenings": lacing})
    assert p.step_ceiling == 2 and "not curried" in p.masterwork_why
    curried, lacing2 = _suit(pc, "elk-hide", product="hide armour", form="panel", quality=4,
                             worked=["stitch", "curry"])
    p = plan(pc, "assemble", {"body": curried, "fastenings": lacing2})
    assert p.step_ceiling == 3 and p.dc == 20
    assert any("tooled" in w for w in p.ceiling_why)


def test_studs_are_the_forges_finish(pc):
    """Owner Q1.3: "leatherworking makes the base and the forge ... finishes it". Steel
    studs on a leather body are studded leather, the forge's; the leather bench refuses them
    with where to go."""
    body, _ = _suit(pc)
    pc.carry("steel-studs", 1)
    pc.carry("iron-buckle", 1)
    p = plan(pc, "assemble", {"body": body, "fastenings": "inv:steel-studs"})
    assert any("smith's anvil" in x for x in p.problems), p.problems
    assert not plan(pc, "assemble", {"body": body, "fastenings": "inv:iron-buckle"}).problems


def test_hide_armour_wants_a_thick_hide(pc):
    """Plan §14.4: hide armour is "the tanned skin of particularly thick-hided beasts"."""
    pc.carry("deer-hide", 2)
    p = plan(pc, "cut", {"hide": "inv:deer-hide"}, product="hide armour")
    assert any("thick hide" in x for x in p.problems), p.problems


def test_the_worked_example_to_the_integer(pc, monkeypatch):
    """Plan §13.3's worked example, end to end through the bench's own record: a Fine hide
    armour, Leatherworker 2, elk body laminated once, deer lacing, no lining, the plan's
    proposed elk and deer lists. AC 4 -> 7, ACP -3 -> -4, Survival +3, max Dex 4 -> 5,
    hardness 0 (rounded toward zero)."""
    docs = {
        "elk-hide": {"id": "elk-hide", "name": "Elk Hide", "kind": "hide",
                     "armour": [{"type": "combat_mod", "target": "ac", "amount": 2,
                                 "bonus_type": "material"},
                                {"type": "gear_mod", "target": "acp", "amount": -2},
                                {"type": "skill_mod", "target": "survival", "amount": 2,
                                 "bonus_type": "material"}]},
        "deer-hide": {"id": "deer-hide", "name": "Deer Hide", "kind": "hide",
                      "armour": [{"type": "gear_mod", "target": "acp", "amount": 2},
                                 {"type": "gear_mod", "target": "max_dex", "amount": 2},
                                 {"type": "gear_mod", "target": "hardness", "amount": -2}]},
    }
    real = forge_items.material
    monkeypatch.setattr(forge_items, "material", lambda mid: docs.get(str(mid)) or real(mid))
    _level(pc, 2)
    body, lacing = _suit(pc, "elk-hide", product="hide armour", form="panel", passes=1,
                         worked=["stitch", "curry"])
    p = plan(pc, "assemble", {"body": body, "fastenings": lacing}, masterwork=False)
    assert p.step_ceiling == 2, p.ceiling_why
    rec = do(pc, p, tier=2)[0]["record"]
    b = forge_items.build(rec)
    row = forge_items.armour_row(ARMOUR["hide armour"], b)
    assert (row["ac"], row["acp"], row["max_dex"]) == (7, -4, 5)
    assert row["hardness_delta"] == 0
    survival = [s for s in b["specs"] if s.get("target") == "survival"]
    assert survival and survival[0]["amount"] == 3


def test_a_generic_hides_beast_rides_onto_the_piece(pc):
    """Contracts §4.1 and lane B's note: a generic hide's numbers are derived from its
    creature on read, so the bench copies the stock's `creature` onto the record's piece
    (`forge_items.build` asks `harvest.inherited`, lane C's, which may not exist yet)."""
    body, lacing = _suit(pc, "generic-fur-hide", product="cloak", form="panel",
                         creature="dire-wolf")
    p = plan(pc, "assemble", {"body": body}, masterwork=False)
    assert not p.problems, p.problems
    rec = do(pc, p, tier=1)[0]["record"]
    assert rec["pieces"]["body"]["creature"] == "dire-wolf"
    assert rec["gear"] == "worn" and rec["slot"] == "shoulders"
    assert not forge_items.build(rec)["problems"]


# --- where you work ----------------------------------------------------------------------------

def test_no_kit_and_no_tannery_nothing_works_and_says_so(pc):
    pc.carry("deer-hide", 2)
    p = plan(pc, "cut", {"hide": "inv:deer-hide"}, product="leather armour", where=NOWHERE)
    assert any("field kit" in x for x in p.problems), p.problems


def test_rare_hides_need_a_tannery_and_level_2(pc):
    """Plan §10, §17.1: the kit reaches common and uncommon; rare and up need a tannery and
    Leatherworker 2 (legendary 3), each said with the level that allows it."""
    key = put(pc, "leather", "manticore-hide", quarters=8, grade=2, tannage="ironbark-tannin")
    p = plan(pc, "cut", {"hide": key}, product="cloak")
    assert any("needs Leatherworker 2" in x for x in p.problems), p.problems
    _level(pc, 2)
    p = plan(pc, "cut", {"hide": key}, product="cloak")
    assert any("need a tannery" in x for x in p.problems), p.problems
    assert not plan(pc, "cut", {"hide": key}, product="cloak", where=TANNERY).problems


def test_a_masterwork_kit_roll_adds_two_circumstance(pc):
    """Plan §13.6 (Core p.158, UE p.77): a kit roll made at Superior is masterwork artisan's
    tools, +2 circumstance on the craft's checks. Read off the record, never a name, and
    kept out of `check_terms`, whose Craft-ranks term is pinned last."""
    assert lw.kit_terms(pc) == []
    rec = {"id": "superior-goat-kit-roll", "name": "Superior Goat Kit Roll", "kind": "crafted",
           "craft": "leatherworker", "gear": "worn", "base": "kit roll", "slot": "",
           "quality_index": 3, "product": "kit roll", "pieces": {"body": {"material": "goat-hide"}}}
    pc.add_stock(forge_items.stock_item(rec), 1)
    assert lw.kit_terms(pc) == [{"label": "masterwork kit roll (circumstance)", "value": 2}]
    pc.carry("deer-hide", 2)
    p = plan(pc, "cut", {"hide": "inv:deer-hide"}, product="leather armour")
    assert p.bonus == lw.check_bonus(pc, 1) + 2


def test_every_method_names_its_game_band_in_a_real_unit(pc):
    """Owner Q8.3 and contracts §11.1: every band a number and a bar as well as a colour, in
    its real unit (prior art §3.9). Grade has no game."""
    units = {"fraction", "strength", "celsius", "spi", "minutes", "percent"}
    for m in lw.METHODS:
        row = lw.method_row(m)
        band = (row.get("tuning") or {}).get("band")
        if m == "grade":
            assert band is None
            continue
        assert band and band["unit"] in units, m
        lo, hi = band["target"]
        assert lo < hi, m

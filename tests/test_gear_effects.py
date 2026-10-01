"""What carried gear does (content/rules/gear.json, rules/gear.py).

The owner, 2026-10-01: "I have items like hemp, flint and steel, tent, trail rations and
so on. They are listed as having no effect. but they should have effects: a tent should
decrease the chance of being attacked in my sleep and protect me from the elements to a
degree. A bedroll should negate the negative of waking up fatigued after sleeping on the
floor or ground and a degree of protection from the cold. a blanket is a degree of
protection from the cold. trail rations reset my hunger, a backpack allows me to carry
more than a couple of things / increases my carry weight. ink and paper allow me to write
notes or draw maps using ink and paper."

Measured before any of this, on a copy of the owner's Sam save: nine of the ten things in
the pack read "for show, no effect in play" on the Equipment tab; `rest` rolled no night
check at all, so a tent had nothing to lower; nothing in the engine woke anybody fatigued
for sleeping on the ground, so a bedroll had nothing to spare; eating consumed nothing;
there was no carrying capacity for a backpack to raise; nothing could be written down.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from django.test import Client, override_settings

sys.path.insert(0, str(Path(__file__).parent))

from rules import gear, ontheway  # noqa: E402
from rules.crafting import Stock  # noqa: E402
from rules.dice import Dice  # noqa: E402
from rules.engine import Engine, Scene  # noqa: E402
from rules.sheet import load_pc  # noqa: E402

THE_OWNERS_PACK = ("backpack", "bedroll", "blanket", "hemp rope", "ink and paper",
                   "trail rations", "tent", "flint and steel")


def _camp(place: str, carried=(), seed: int = 3):
    from _a_truth import VORMOOR, WORLD

    s = Scene(location_id=VORMOOR.id)
    pc = load_pc("fixtures/pc-kesst.json")
    s.add(pc)
    for name in carried:
        pc.add_stock(Stock(base=name, craft=""), 1)
    e = Engine(s, Dice(seed=seed), world=WORLD)
    e.place_party(place)
    return s, e, pc


def _rest(e):
    return e.run(e.validate([{"op": "rest", "actor": "pc", "params": {"kind": "night"}}]))


@pytest.fixture
def quiet_night(monkeypatch):
    """No night check: what the ground does is measured alone."""
    monkeypatch.setattr(ontheway, "night", lambda *a, **k: None)


def _approach():
    from _a_truth import APPROACH

    return APPROACH


def _tundra():
    from _a_truth import VORMOOR

    return f"{VORMOOR.id}~tundra:the-approach"


# --- the document --------------------------------------------------------------------------

def test_the_gear_document_validates():
    """Every row says what it does in words, and every number is written in the row:
    `amount` an integer the document carries, never a model's."""
    assert gear.validate() == []


def test_every_thing_in_the_owners_pack_says_what_it_does():
    """Nine of ten read 'for show, no effect in play' on 2026-10-01; each now has a row
    and the row has words."""
    for name in THE_OWNERS_PACK:
        key, row = gear.row_for(name)
        assert row is not None, name
        assert gear.does(name), name


def test_a_name_is_matched_whole_never_as_a_substring():
    """A rope dart is a weapon, not a rope."""
    assert gear.row_for("rope dart") == (None, None)
    assert gear.row_for("Hemp  Rope")[0] == "hemp rope"


def test_what_the_book_does_not_print_is_said_to_be_a_house_rule():
    """The tent, the bedroll and the blanket have no rules text in 1e (CRB p.158); every
    number on them is this table's, and the row says so in the owner's words."""
    for key in ("tent", "bedroll", "blanket", "backpack"):
        assert "owner" in gear.items()[key]["house_rule"], key


# --- the Equipment tab ---------------------------------------------------------------------

def test_the_equipment_tab_no_longer_says_no_effect():
    """`_carried` is the Equipment tab's one list. A bought bedroll is a stock jar with no
    specs, and every reader took that for nothing at all."""
    from play.views import _carried

    pc = load_pc("fixtures/pc-kesst.json")
    for name in THE_OWNERS_PACK:
        pc.add_stock(Stock(base=name, craft=""), 1)
    rows = {r["name"]: r for r in _carried(pc)}
    for name in THE_OWNERS_PACK:
        assert rows[name]["known"] is True, name
        assert rows[name]["line"] == gear.does(name), name


def test_rations_are_eaten_not_drunk():
    """Trail rations sit on the consumables shelf ("rations" is in the name) and
    `consumables.plan` answered "ok" to drinking any harmless jar, so they were offered
    Drink. Their row says eat."""
    from play.views import _carried

    pc = load_pc("fixtures/pc-kesst.json")
    pc.add_stock(Stock(base="trail rations", craft=""), 5)
    row = next(r for r in _carried(pc) if r["name"] == "trail rations")
    assert [a["label"] for a in row["acts"]] == ["Eat"]
    assert row["acts"][0]["body"] == {"item": "trail-rations#1", "how": "eat"}


# --- trail rations -------------------------------------------------------------------------

def test_eating_rations_resets_hunger_and_spends_one():
    """'trail rations reset my hunger'. Before, `eat` reset the clock and spent nothing,
    so ten days of rations were ten days for ever."""
    s = Scene(location_id="5bbd0c40345f")
    pc = load_pc("fixtures/pc-kesst.json")
    s.add(pc)
    pc.add_stock(Stock(base="trail rations", craft=""), 10)
    pc.fed_minutes = 50 * 60
    pc.hunger_checks = 2
    e = Engine(s, Dice(seed=1))
    out = e.run(e.validate([{"op": "eat", "actor": "pc",
                             "params": {"item": "trail rations"}}])).outcomes[0]
    assert pc.fed_minutes == 0 and pc.hunger_checks == 0
    assert pc.stock["trail-rations#1"].count == 9
    assert "9 left" in out.tell and out.effects[0]["origin"] == "item:trail-rations#1"


def test_eating_what_you_do_not_carry_is_refused_with_what_you_do():
    s = Scene(location_id="5bbd0c40345f")
    pc = load_pc("fixtures/pc-kesst.json")
    s.add(pc)
    pc.fed_minutes = 600
    e = Engine(s, Dice(seed=1))
    out = e.run(e.validate([{"op": "eat", "actor": "pc",
                             "params": {"item": "trail rations"}}])).outcomes[0]
    assert not out.effects and "Nothing in the pack is food" in out.tell
    assert pc.fed_minutes == 600


def test_the_last_ration_leaves_the_pack():
    s = Scene(location_id="5bbd0c40345f")
    pc = load_pc("fixtures/pc-kesst.json")
    s.add(pc)
    pc.add_stock(Stock(base="trail rations", craft=""), 1)
    e = Engine(s, Dice(seed=1))
    e.run(e.validate([{"op": "eat", "actor": "pc", "params": {"item": "rations"}}]))
    assert "trail-rations#1" not in pc.stock


# --- the bedroll: sleeping rough ------------------------------------------------------------

def test_sleeping_on_the_ground_without_a_bedroll_wakes_you_stiff(quiet_night):
    """The owner's 'negative of waking up fatigued after sleeping on the floor or ground':
    the engine had no such rule (1e has none; only medium or heavy armour fatigues a
    sleeper). It is the camp row `sleeping-rough`: fatigued for two hours."""
    s, e, pc = _camp(_approach())
    out = _rest(e).outcomes[0]
    cond = next(x for x in pc.effects if x.kind == "condition" and x.key == "fatigued")
    assert cond.rounds_left == 2 * 600
    assert "wakes stiff" in out.tell and "bedroll would have spared it" in out.tell


def test_a_bedroll_spares_it_and_says_so(quiet_night):
    """'A bedroll should negate the negative'. Asked by tag (`gear.bedding`), not by the
    word bedroll, so anything a row says is bedding spares it."""
    s, e, pc = _camp(_approach(), ("bedroll",))
    out = _rest(e).outcomes[0]
    assert not pc.has_condition("fatigued")
    assert "The bedroll kept the ground off" in out.tell


def test_a_bed_in_town_is_a_bed(quiet_night):
    """Only out on the ground (`setting_of` outside or under): the inn is not the floor."""
    from _a_truth import MARKET

    s, e, pc = _camp(MARKET)
    _rest(e)
    assert not pc.has_condition("fatigued")


def test_selling_the_bedroll_takes_its_bedding_away():
    """The pack is the store (stage 8's ruling for feats): nothing was copied onto the
    sheet, so nothing is left behind."""
    pc = load_pc("fixtures/pc-kesst.json")
    pc.add_stock(Stock(base="bedroll", craft=""), 1)
    assert pc.has_state("gear.bedding")
    pc.take_stock("bedroll#1", 1)
    assert not pc.has_state("gear.bedding")


# --- the blanket, the bedroll, the tent: cold ----------------------------------------------

def test_cold_protection_lands_only_on_a_cold_save_while_resting():
    """'a blanket is a degree of protection from the cold': +2 circumstance on a Fortitude
    save whose context is cold and resting, each item its own source (1e: circumstance
    bonuses stack unless from the same source). A plain Fortitude save is unchanged."""
    pc = load_pc("fixtures/pc-kesst.json")
    plain = sum(m.value for m in pc.save_modifiers("fort"))
    for name in ("blanket", "bedroll", "tent", "blanket"):
        pc.add_stock(Stock(base=name, craft=""), 1)
    cold = pc.save_modifiers("fort", {"against": "cold", "resting": True})
    assert sum(m.value for m in pc.save_modifiers("fort")) == plain
    terms = sorted((m.source, m.value, m.type) for m in cold if m.type == "circumstance")
    assert terms == [("bedroll", 2, "circumstance"), ("blanket", 2, "circumstance"),
                     ("tent", 2, "circumstance")]


def test_a_night_on_frozen_ground_rolls_the_books_cold(quiet_night):
    """CRB Cold Dangers: 'a Fortitude save each hour (DC 15, +1 per previous check) or
    take 1d6 points of nonlethal damage'. Measured on the first run: the rolling did not
    stop at unconsciousness, and a 9 hp sleeper took 18 nonlethal, the overflow landing
    as lethal. It stops at staggered now."""
    s, e, pc = _camp(_tundra(), seed=7)
    out = _rest(e).outcomes[0]
    dcs = [r.label for r in out.rolls if "Fortitude" in r.label]
    assert dcs and dcs[0].endswith("DC 15)")
    assert pc.nonlethal <= pc.hp_max and pc.hp > 0


def test_a_tent_and_a_bedroll_keep_the_cold_out(quiet_night):
    """'protect me from the elements to a degree'. Measured before this clause: tent,
    bedroll and blanket still failed 5 of 8 saves on the tundra and the wizard went down,
    the +2s no match for a DC climbing to 22. The book's check is for 'an unprotected
    character'; a pitched tent with bedding is protected (the row's house reading)."""
    s, e, pc = _camp(_tundra(), ("tent", "bedroll"), seed=7)
    out = _rest(e).outcomes[0]
    assert not [r for r in out.rolls if "Fortitude" in r.label]
    assert pc.nonlethal == 0 and "sleeps warm" in out.tell


def test_the_cited_cold_hazard_rolls_the_save_its_source_names():
    """hazards.json's cold row said 'on a failed Fortitude save' and rolled the damage with
    no save at all. One save an hour now, read in the cold context."""
    s, e, pc = _camp(_approach(), ("cold-weather outfit",))
    out = e.run(e.validate([{"op": "hazard", "actor": "pc",
                             "params": {"rule": "cold", "hours": 2, "to": "pc"}}])).outcomes[0]
    saves = [r for r in out.rolls if "Fortitude" in r.label]
    assert len(saves) >= 1
    assert any(m.source == "cold-weather outfit" and m.value == 5
               for m in pc.save_modifiers("fort", {"against": "cold"}))


# --- the tent: the night's check -----------------------------------------------------------

def test_a_tent_halves_the_chance_of_being_found_in_the_night():
    """'a tent should decrease the chance of being attacked in my sleep'. The night's
    check is the road's (20% a six-hour watch, AoN Step 4), over an eight-hour night:
    measured over seeds 0-299 on forest at level 1, 86 nights met something in the open
    and 48 under canvas."""
    open_ground = sum(ontheway.night(Dice(seed=n), 8, "forest", 1) is not None
                      for n in range(300))
    tent = sum(ontheway.night(Dice(seed=n), 8, "forest", 1, scale=0.5) is not None
               for n in range(300))
    assert 60 <= open_ground <= 110
    assert tent < open_ground * 0.65


def test_the_tents_scale_is_read_from_its_row():
    pc = load_pc("fixtures/pc-kesst.json")
    assert gear.night_scale(pc) == (1.0, "")
    pc.add_stock(Stock(base="tent", craft=""), 1)
    assert gear.night_scale(pc) == (0.5, "tent")


def test_something_that_comes_in_the_night_breaks_it(monkeypatch):
    """1e's natural healing is for 'a full night's rest (8 hours of sleep or more)': a
    wolf six hours in is no healing, the clock moved six hours, and the fight opens."""
    from rules.ontheway import Meeting

    monkeypatch.setattr(ontheway, "night", lambda *a, **k: Meeting(
        kind="creature", roll=5, creature={"name": "wolf", "id": "wolf"},
        template="wolf", count=1, after=1, aggressive=True))
    s, e, pc = _camp(_approach(), ("tent",))
    pc.hp = pc.hp_max - 3
    hurt = pc.hp
    out = _rest(e).outcomes[0]
    assert pc.hp == hurt
    assert s.clock_minutes == 6 * 60
    assert s.in_encounter
    assert "The night is broken" in out.tell
    assert any(x.get("kind") == "night-check" for x in out.effects)


# --- the backpack: carrying capacity -------------------------------------------------------

def test_carrying_capacity_is_the_books_table():
    """CRB Table 7-4, and its Tremendous Strength rule above 29 (Str 30 is the 20 row x4)."""
    assert gear.capacity(10) == (33, 66, 100)
    assert gear.capacity(18) == (100, 200, 300)
    assert gear.capacity(30) == (532, 1064, 1600)
    assert gear.capacity(10, "small") == (24, 49, 75)


def test_a_backpack_lets_you_carry_more():
    """'a backpack allows me to carry more ... / increases my carry weight'. The book's
    number is the masterwork backpack's (UE p.56): Strength counts 1 higher for carrying
    capacity. Shown, not enforced: encumbrance is the owner's later batch (E9)."""
    pc = load_pc("fixtures/pc-kesst.json")
    without = gear.load(pc)
    pc.add_stock(Stock(base="backpack", craft=""), 1)
    with_pack = gear.load(pc)
    assert with_pack["str_bonus"] == 1 and with_pack["str_bonus_from"] == "backpack"
    assert with_pack["light"] > without["light"]
    assert with_pack["lb"] == without["lb"] + 2          # the pack weighs 2 lb
    assert with_pack["enforced"] is False


def test_carried_weight_counts_measured_goods_by_their_unit():
    """Fifty feet of hemp rope is 10 lb, not fifty ropes; ten days of rations 10 lb."""
    pc = load_pc("fixtures/pc-kesst.json")
    base = gear.load(pc)["lb"]
    pc.add_stock(Stock(base="hemp rope", craft=""), 50)
    pc.add_stock(Stock(base="trail rations", craft=""), 10)
    assert gear.load(pc)["lb"] == base + 20


# --- ink and paper: notes and maps ---------------------------------------------------------

@pytest.fixture
def camp(tmp_path):
    from play import campaign as cm

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns", ALLOWED_HOSTS=["*"]):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        yield c
        cm._LIVE.clear()


def _post(url, body):
    r = Client().post(url, data=json.dumps(body), content_type="application/json")
    return r.status_code, r.json()


def test_writing_needs_ink_and_paper(camp):
    """'ink and paper allow me to write notes': without them the page says why."""
    code, d = _post("/api/write", {"kind": "note", "text": "the gate shuts at dusk"})
    assert code == 400 and "ink and paper" in d["error"]
    assert camp.scene.writings == []


def test_a_note_written_is_kept_through_a_save(camp):
    from play import campaign as cm

    camp.scene.pc().add_stock(Stock(base="ink and paper", craft=""), 1)
    code, d = _post("/api/write", {"kind": "note", "title": "Gate",
                                   "text": "the gate shuts at dusk"})
    assert code == 200
    assert d["writings"]["pages"][-1]["text"] == "the gate shuts at dusk"
    cm._LIVE.clear()
    again = cm.current()
    assert again.scene.writings[-1]["title"] == "Gate"


def test_a_map_is_the_engines_chart_not_the_players_words(camp):
    """A drawn map is the places stood in and the ways out of each, as the fog-of-war
    chart knows them when it is drawn."""
    camp.scene.pc().add_stock(Stock(base="ink and paper", craft=""), 1)
    code, d = _post("/api/write", {"kind": "map"})
    assert code == 200, d
    page = d["writings"]["pages"][-1]
    assert page["kind"] == "map" and page["lines"]
    assert any("(here)" in line for line in page["lines"])

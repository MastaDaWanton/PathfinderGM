"""Bought manuals are read at their own bench, and weigh what a book weighs.

Measured 2026-10-08 by the leatherworking knowledge lane: every craft's manuals were sold at
counters (rules/goods.py `MANUAL_TABLES`) and paid mastery on a first reading, but the only
route in play/ that read one was play/herb_views.py `herb_manual`, which looks up herbal
manuals only. A bought smithing, enchanting or alchemy manual could never be opened. The
Equipment tab said "Not weighed, the rules have no weight for: <manual name>" of every one.

Driven through the Django test client on a real campaign, with the real manual files, the
real `knowledge.read_manual` and the books bought through the real `goods.deliver`.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from django.test import Client, override_settings
from django.urls import resolve

from play import alchemy_views, enchant_views, forge_views
from play import campaign as cm
from rules import gear, goods, knowledge
from rules.sheet import load_pc

ROOT = Path(__file__).resolve().parents[1]

# bench -> (the craft whose books it reads, the counter table they are sold from, its track)
BENCHES = {
    "forge": (knowledge.BLACKSMITH, "smithing-manuals", "blacksmith"),
    "enchant": (knowledge.ENCHANTER, "enchanting-manuals", "enchanter"),
    "alchemy": (knowledge.ALCHEMIST, "alchemy-manuals", "alchemist"),
}


@pytest.fixture
def client(tmp_path):
    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        for v in (forge_views, enchant_views, alchemy_views):
            v._PENDING.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"), start_id="quiet-the-bread-stall")
        pc = c.scene.pc()
        pc.inventory.clear()
        pc.stock.clear()
        pc.goods.clear()
        pc.herb_known.clear()
        pc.manuals_read.clear()
        pc.purse = {"gp": 50}
        c.save()
        yield Client()
        cm._LIVE.clear()


def _pc():
    return cm.current().scene.pc()


def _buy(table: str, manual_id: str):
    """The counter's own path: the good off its table, delivered as a purchase is."""
    good = next(g for g in goods.table_goods(table) if g.key == manual_id)
    c = cm.current()
    goods.deliver(c.scene, c.scene.pc(), good)
    c.save()
    return good


def post(client, url, body):
    return client.post(url, data=json.dumps(body), content_type="application/json")


def test_each_bench_has_a_manual_route():
    for bench in BENCHES:
        assert resolve(f"/api/{bench}/manual").func.__name__ == f"{bench}_manual"


@pytest.mark.parametrize("bench", sorted(BENCHES))
def test_a_bought_manual_is_read_at_its_bench_and_pays_its_mastery_once(client, bench):
    """The defect: a bought smithing, enchanting or alchemy manual had no reader anywhere,
    so its price bought nothing. Now it is listed on the bench's state, read through
    `knowledge.read_manual`, its hours pass on the scene clock, and the first reading pays
    the craft's `manual.mastery` (5) on the craft's own track; the second pays nothing."""
    craft, table, track = BENCHES[bench]
    manual = next(m for _, m in sorted(knowledge.manuals(craft).items()) if m.get("teaches"))
    assert client.get(f"/api/{bench}/state").json()["manuals"] == []
    _buy(table, manual["id"])
    listed = client.get(f"/api/{bench}/state").json()["manuals"]
    assert [(m["id"], m["read"]) for m in listed] == [(manual["id"], False)]
    before = int(cm.current().scene.clock_minutes or 0)
    mp_before = _pc().track(track).mp

    first = post(client, f"/api/{bench}/manual", {"item": manual["id"]})
    assert first.status_code == 200, first.content[:300]
    got = first.json()
    assert got["first"] and got["revealed"], got
    assert all(r["text"] for r in got["revealed"]), "every fact learned is said in words"
    paid = sum(l["mp"] for l in got["mastery"]["lines"])
    assert paid == int(knowledge.lore(craft)["manual"]["mastery"]) == 5
    assert _pc().track(track).mp == mp_before + 5
    assert int(cm.current().scene.clock_minutes) - before == int(manual["hours"]) * 60
    assert got["manuals"][0]["read"] is True
    assert manual["id"] in _pc().manuals_read

    again = post(client, f"/api/{bench}/manual", {"item": manual["name"]}).json()
    assert not again["first"] and not again["mastery"]["lines"] and not again["revealed"]


@pytest.mark.parametrize("bench", sorted(BENCHES))
def test_a_bench_refuses_a_book_not_in_the_pack_or_not_its_crafts(client, bench):
    """Reading a book you do not have is refused by name; another craft's book is refused
    at this bench with its name (the smith's bench must not read a herbal, and a tanner's
    book is the leather bench's), and nothing is learned or paid."""
    craft, _table, track = BENCHES[bench]
    mine = next(iter(knowledge.manuals(craft).values()))
    r = post(client, f"/api/{bench}/manual", {"item": mine["id"]})
    assert r.status_code == 400 and mine["name"] in r.json()["error"]
    other = next(iter(knowledge.manuals(knowledge.HERBALIST).values()))
    _pc().goods[other["name"]] = 1
    cm.current().save()
    r = post(client, f"/api/{bench}/manual", {"item": other["id"]})
    assert r.status_code == 400 and "not a book for this bench" in r.json()["error"]
    assert post(client, f"/api/{bench}/manual", {"item": "no such book"}).status_code == 400
    assert _pc().track(track).mp == 0 and not _pc().manuals_read


@pytest.mark.parametrize("bench", sorted(BENCHES))
def test_every_manual_sold_for_a_bench_teaches_something_there(client, bench):
    """Every book of the craft, bought at its counter and read at its bench, teaches at
    least one fact or says what it writes: a manual whose every row named an id nothing
    holds would be a book that takes hours and teaches nothing (`manual_keys` skips those
    ids silently). Measured while building this: six of the nine alchemy books are
    formularies with no `teaches` row, and the first reading of one said "nothing new in
    it" of a book holding fifteen formulae."""
    from rules import survival

    craft, table, _track = BENCHES[bench]
    for mid in sorted(knowledge.manuals(craft)):
        # Nine alchemy books are some seventy hours of reading (a formulary is an hour an
        # entry): the reader eats, drinks and sleeps between them, or the awake clock
        # (rightly) puts them down before the last, as it did on the first run of this.
        survival.eat(_pc())
        survival.drink(_pc())
        survival.sleep(_pc())
        _buy(table, mid)
        r = post(client, f"/api/{bench}/manual", {"item": mid})
        assert r.status_code == 200, (mid, r.content[:300])
        got = r.json()
        assert got["revealed"] or "Formulary" in got["note"],             f"{mid} taught nothing at the {bench}: {got}"
        assert sum(l["mp"] for l in got["mastery"]["lines"]) == 5, mid


def test_a_formulary_says_what_it_writes_and_pays_its_reading_once(client):
    """Alchemy plan §6: "Reading an unread formulary: +5 once per book", which nothing paid
    before this. Its formulae are still copied through the Formulary's own route; the
    reading says how many are not yet in the book, and the transcript says so too."""
    book = knowledge.manuals(knowledge.ALCHEMIST)["the-flask-makers-formulary"]
    _buy("alchemy-manuals", book["id"])
    got = post(client, "/api/alchemy/manual", {"item": book["id"]}).json()
    n = len(book["formulae"])
    assert got["note"].startswith(f"It writes down {n} formulae not yet in your formula book")
    assert sum(l["mp"] for l in got["mastery"]["lines"]) == 5
    assert "nothing new" not in cm.current().transcript[-1]["text"]


def test_reading_waits_until_the_fight_is_over(client):
    """A reading is hours of the clock: in a fight it is refused, as the leather bench's is,
    and the clock does not move."""
    manual = next(iter(knowledge.manuals(knowledge.BLACKSMITH).values()))
    _buy("smithing-manuals", manual["id"])
    c = cm.current()
    c.scene.initiative = [c.scene.pc().ref]
    c.scene.turn = 0
    c.save()
    before = int(c.scene.clock_minutes or 0)
    r = post(client, "/api/forge/manual", {"item": manual["id"]})
    assert r.status_code == 409 and "fight" in r.json()["error"]
    assert int(cm.current().scene.clock_minutes or 0) == before


# --- weight -------------------------------------------------------------------------------

@pytest.mark.parametrize("table", sorted(goods.MANUAL_TABLES))
def test_every_bought_manual_is_weighed(client, table):
    """Measured 2026-10-08: the Equipment tab said "Not weighed, the rules have no weight
    for: <manual name>" of every bought manual, in every craft. A manual is a small
    written book: Ultimate Equipment's 50-page journal, 1 lb (`gear.MANUAL_LB`)."""
    pc = _pc()
    empty = gear.load(pc)["lb"]
    books = sorted(knowledge.manuals(goods.MANUAL_TABLES[table]))
    for mid in books:
        _buy(table, mid)
    got = gear.load(pc)
    assert not got["unknown"], got["unknown"]
    assert got["lb"] == pytest.approx(empty + gear.MANUAL_LB * len(books))


def test_a_looted_or_handed_manual_weighs_the_same(client):
    """A book handed over or looted sits in `goods` under its name, not on the shelf; it
    weighs the same, and the loot picker's weight (`defeat._stock_weight`) agrees with
    the load for a bought one."""
    from rules import defeat

    pc = _pc()
    empty = gear.load(pc)["lb"]
    manual = next(iter(knowledge.manuals(knowledge.ENCHANTER).values()))
    pc.goods[manual["name"]] = 2
    assert gear.load(pc)["lb"] == pytest.approx(empty + 2 * gear.MANUAL_LB)
    assert not gear.load(pc)["unknown"]
    pc.goods.clear()
    _buy("enchanting-manuals", manual["id"])
    shelf = next(s for s in pc.stock.values() if s.base == manual["name"])
    assert defeat._stock_weight(shelf) == pytest.approx(gear.MANUAL_LB)


def test_a_manual_row_may_carry_its_own_weight(monkeypatch):
    """`lb` on a manual row overrides the default, so a heavy folio can be written in."""
    manual = dict(next(iter(knowledge.manuals(knowledge.BLACKSMITH).values())), lb=3)
    monkeypatch.setattr(knowledge, "manual_named", lambda said, craft=None: manual)
    assert gear.manual_weight(manual["name"], 2) == 6.0
    monkeypatch.setattr(knowledge, "manual_named", lambda said, craft=None: None)
    assert gear.manual_weight("rope") is None


# --- the page -----------------------------------------------------------------------------

def test_each_bench_footer_offers_its_manuals_through_the_cores_one_dialog():
    """The route alone was not the fix: the herb bench has had `api/herb/manual` since
    0.2.4 and no page ever called it. Each bench's footer offers Manuals when the state
    lists a carried book, and opens the bench core's one dialog on its own route; the
    dialog is written once in 29-bench-core.js, not copied three times."""
    js = ROOT / "play" / "static" / "js" / "table"
    core = (js / "29-bench-core.js").read_text(encoding="utf-8")
    assert "h.manuals = function" in core
    for bench, shell in (("forge", "40-forge-shell.js"), ("enchant", "45-enchant-shell.js"),
                         ("alchemy", "50-alchemy-shell.js")):
        src = (js / shell).read_text(encoding="utf-8")
        assert f"data-{bench}-manuals" in src, shell
        assert f'"/api/{bench}/manual"' in src, shell
        assert "core.manuals(" in src, shell
        assert "s.manuals.length" in src, f"{shell}: Manuals shows only when a book is carried"


def test_a_reading_says_where_each_property_acts(client):
    """Seen live 2026-10-08: The Ironmonger's Daybook listed 53 facts, "+2 hardness" twice
    under Iron with nothing to say one was the blade's and one the plate's. Each metal row
    now carries `where`, in the forge ledger's own words; an essence's trait says where it
    acts in its own words, so its rows carry none."""
    _buy("smithing-manuals", "the-ironmongers-daybook")
    rows = post(client, "/api/forge/manual", {"item": "the-ironmongers-daybook"}).json()["revealed"]
    iron = [r for r in rows if r["id"] == "iron"]
    assert {"In a weapon", "In armour"} <= {r["where"] for r in iron}, iron
    _buy("enchanting-manuals", "a-primer-of-motes")
    rows = post(client, "/api/enchant/manual", {"item": "a-primer-of-motes"}).json()["revealed"]
    assert rows and not any(r.get("where") for r in rows)


def test_a_handed_over_manual_survives_a_reload():
    """Measured 2026-10-08, live on scratch data: a looted "Fire and Water: A Journeyman's
    Notes" put in `goods` was gone when the app next loaded the save. The load-time heal
    of words minted into things (`campaign._heal_minted_goods`) judged three of the 33
    manual names to be no thing at all and threw them away; every manual now stays."""
    from play.campaign import _heal_minted_goods
    from rules.engine import Scene

    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    pc = s.pc()
    names = {m["name"]: 1 for m in knowledge.manuals().values()}
    pc.goods.update(names)
    pc.goods["brunt of the weight"] = 1
    _heal_minted_goods(s)
    assert pc.goods == names, set(names) - set(pc.goods)

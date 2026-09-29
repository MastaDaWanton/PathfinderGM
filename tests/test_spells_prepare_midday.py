"""Preparing into the rest of the day: a slot spent today is not an open slot.

The owner's screenshot, 2026-09-29. Ysolde Marrach, wizard 1, two level 1 slots. She had
prepared Burning Hands and Magic Missile and cast Burning Hands; `_op_cast` spent the slot
and the prepared copy together (rules/casting.py, "the morning's preparation"). She then
pressed Prepare on Burning Hands again, and it was ALLOWED: the room check read slots per
day minus spells held, 2 - 1 = 1, and forgot the slot spent that morning. The Spells tab
then showed:

  * Level 1 "1 of 2 left" in the sockets;
  * a Burning Hands card "1 prepared · 1 of 2 level 1 slots left";
  * a Magic Missile card "1 prepared · 1 of 2 level 1 slots left", so two cards each
    claimed the one free slot;
  * and on the next Prepare, in red at the column's top, the raw endpoint sentence
    "Ysolde Marrach has 2 level 1 slots and has already prepared 2".

The sourced rule (Archives of Nethys, Core Rulebook, Magic > Arcane Spells, "Preparing
Wizard Spells", fetched 2026-09-29): "When preparing spells for the day, a wizard can
leave some of these spell slots open. Later during that day, he can repeat the
preparation process as often as he likes... He cannot, however, abandon a previously
prepared spell to replace it with another one or fill a slot that is empty because he has
cast a spell in the meantime. That sort of preparation requires a mind fresh from rest."

The owner's house rule (2026-09-29) keeps the second clause and departs from the rest:
"prepare is fine whenever for the sake of user experience but once a slot is used is un
fillable until after a long rest." So preparing and unpreparing are free at any time, with
no preparation time on the clock (the book's "at least 15 minutes" is not charged) and
swapping the spell in an UNSPENT slot allowed (the book's no-abandon clause is not
enforced); a slot SPENT today stays spent until the night's rest (`rest.night`), and
unpreparing never turns it back into an open one. Cantrips are untouched: at will, never
spent, room = the 0-level count less the cantrips held.

The page half is checked by rendering `tabSpells` from 05-sheet.js in node against the
real sheet, the way tests/test_i5_spells_page.py does.
"""
from __future__ import annotations

import re

import pytest
from django.test import Client

from rules import casting
from rules.bestiary import instantiate
from rules.dice import Dice
from rules.engine import Engine
from rules.sheet import from_dict, full_sheet, load_pc, to_dict

from pagesource import TABLE, TABLE_SCRIPTS
from test_i5_spells_page import _render, _tree

BOOK = ("acid-splash", "light", "daze", "burning-hands", "magic-missile", "shield",
        "sleep")


def ysolde(prepared=None):
    """The owner's wizard: level 1, Int 18, so two level 1 slots and three cantrips."""
    d = to_dict(load_pc("fixtures/pc-kesst.json"))
    d.update({"class": "wizard", "level": 1, "ranks": {}, "name": "Ysolde Marrach"})
    d["abilities"]["int"] = 18
    d["spellbook"] = list(BOOK)
    d["prepared"] = dict({"burning-hands": 1, "magic-missile": 1, "acid-splash": 1,
                          "light": 1} if prepared is None else prepared)
    pc = from_dict(d, ref="pc")
    casting.define_slots(pc)
    return pc


def _cast(scene, spell: str, at: str = "c1"):
    """The real cast, through the engine, in a fight already running (a first harmful
    cast outside one opens the fight and defers; tests/test_e_magic_harm.py)."""
    if "c1" not in list(scene.actors):
        scene.add(instantiate("thug", scene=scene, name="the thug"))
    scene.initiative = [("pc", 20), ("c1", 10)]
    scene.sides = {"pc": ["pc"], "them": ["c1"]}
    scene.round, scene.turn = 1, 0
    e = Engine(scene, Dice(seed=5))
    return e.run(e.validate([{"op": "cast", "actor": "pc", "because": "she speaks",
                              "params": {"spell": spell, "at": at}}]))


def _prepare(action: str, spell: str):
    return Client().post("/api/spells/prepare", data={"action": action, "spell": spell},
                         content_type="application/json")


@pytest.fixture
def campaign(tmp_path, settings):
    settings.CAMPAIGN_DIR = str(tmp_path)
    from play import campaign as campaign_mod

    c = campaign_mod.begin_with(ysolde())
    pc = c.scene.pc()
    pc.prepared = {"burning-hands": 1, "magic-missile": 1, "acid-splash": 1, "light": 1}
    casting.define_slots(pc)
    c.save()
    return c


def _reload():
    from play import campaign as campaign_mod

    return campaign_mod.current()


def _level(sheet_spells: dict, lvl: int) -> dict:
    return next(s for s in sheet_spells["slots"] if s["level"] == lvl)


# --- the rule ---------------------------------------------------------------------------

def test_the_owners_screenshot_prepare_again_after_casting_is_refused(campaign):
    """Ysolde: two level 1 slots, Burning Hands and Magic Missile prepared, Burning Hands
    cast. Measured before the fix: Prepare Burning Hands again returned 200 and she held
    two level 1 spells with one unspent slot. Now it is refused with the reason in plain
    words, and nothing changes: not the prepared list, not the loadout, not the pools."""
    c = campaign
    _cast(c.scene, "burning-hands")
    pc = c.scene.pc()
    assert casting.slots_left(pc, 1) == 1 and casting.prepared_count(pc, "burning-hands") == 0
    c.save()
    before = (dict(pc.prepared), dict(pc.loadout or {}), casting.slots_left(pc, 1))

    res = _prepare("prepare", "burning-hands")
    assert res.status_code == 409
    body = res.json()
    assert body["error"] == "No open level 1 slot today. Unprepare one first."
    assert body["level"] == 1 and body["spell"] == "burning-hands"
    # The raw sentence the owner saw is gone for good.
    assert "has already prepared" not in body["error"]
    pc = _reload().scene.pc()
    assert (dict(pc.prepared), dict(pc.loadout or {}), casting.slots_left(pc, 1)) == before


def test_unpreparing_frees_the_unspent_slot_and_never_the_spent_one(campaign):
    """The house rule: swapping the spell in an UNSPENT slot is allowed any time. After the
    cast, unpreparing Magic Missile opens exactly one slot (the unspent one), Burning
    Hands goes into it, and a second Prepare is refused: the spent slot stayed spent. With
    the old rule (slots per day minus held) the second would have made it 2 held in 1."""
    c = campaign
    _cast(c.scene, "burning-hands")
    c.save()
    assert _prepare("unprepare", "magic-missile").status_code == 200
    res = _prepare("prepare", "burning-hands")
    assert res.status_code == 200
    assert _level(res.json()["spells"], 1)["open"] == 0
    again = _prepare("prepare", "burning-hands")
    assert again.status_code == 409
    assert again.json()["error"] == "No open level 1 slot today. Unprepare one first."
    pc = _reload().scene.pc()
    assert casting.prepared_count(pc, "burning-hands") == 1
    assert casting.slots_left(pc, 1) == 1


def test_a_slot_left_open_in_the_morning_can_be_filled_later(campaign):
    """The book's first clause, kept: "a wizard can leave some of these spell slots open.
    Later during that day, he can repeat the preparation process". Magic Missile is
    unprepared before anything is cast, so both slots are unspent and one is open; Shield
    goes into it with no time on the clock (the owner's house rule: prepare is fine
    whenever)."""
    c = campaign
    clock = c.scene.clock_minutes
    res = _prepare("unprepare", "magic-missile")
    assert _level(res.json()["spells"], 1)["open"] == 1
    res = _prepare("prepare", "shield")
    assert res.status_code == 200
    row = _level(res.json()["spells"], 1)
    assert (row["held"], row["left"], row["open"], row["blocked"]) == (
        2, 2, 0, "No open level 1 slot today. Unprepare one first.")
    assert _reload().scene.clock_minutes == clock, "preparing charges no time"


def test_every_slot_spent_says_it_comes_back_after_a_long_rest(campaign):
    """Both level 1 slots cast: the reason is the spent one, in the owner's words, and a
    night's rest (`rest.night`, the pools' refresh) is what opens them again."""
    c = campaign
    _cast(c.scene, "burning-hands")
    _cast(c.scene, "magic-missile")
    pc = c.scene.pc()
    assert casting.slots_left(pc, 1) == 0 and casting.held_at(pc, 1) == 0
    c.save()
    res = _prepare("prepare", "sleep")
    assert res.status_code == 409
    assert res.json()["error"] == ("Every level 1 slot is spent for today; they come back "
                                   "after a long rest.")
    # Unpreparing has nothing to give back; the room stays shut.
    assert casting.open_slots(pc, 1) == 0
    pc.refresh_pools("rest.night")
    assert casting.open_slots(pc, 1) == 2 and casting.prepare_refusal(pc, 1) == ""


def test_unprepare_cannot_turn_a_spent_slot_into_an_open_one():
    """The rule the owner kept, at the function: after one cast from two slots, dropping
    every level 1 spell leaves ONE open slot, not two."""
    pc = ysolde()
    s = _scene_for(pc)
    _cast(s, "burning-hands")
    casting.unprepare(pc, "magic-missile", 99)
    assert casting.held_at(pc, 1) == 0
    assert casting.unspent_slots(pc, 1) == 1 and casting.open_slots(pc, 1) == 1


def test_the_morning_and_the_warning_read_the_same_room():
    """`empty_slots` (the sheet's "slots stand empty" warning) and `ensure_prepared` read
    `open_slots` too: after the cast the warning names no empty level 1 slot, because a
    spent slot is not empty, and a refill mid-day puts nothing into it."""
    pc = ysolde()
    _cast(_scene_for(pc), "burning-hands")
    assert 1 not in casting.empty_slots(pc)
    got = casting.ensure_prepared(pc, reason="test")
    assert not any(casting._level(pc, sid) == 1 for sid in got["added"])
    assert casting.held_at(pc, 1) == 1


def test_cantrips_keep_their_own_rule():
    """At will, never spent: casting Acid Splash touches no pool and no count, and the
    cantrip room is the 0-level count less the cantrips held (3 - 2 = 1), whatever has
    been cast. The fourth cantrip is refused with the cantrip sentence."""
    pc = ysolde()
    s = _scene_for(pc)
    _cast(s, "acid-splash")
    _cast(s, "acid-splash")
    assert casting.prepared_count(pc, "acid-splash") == 1
    assert casting.open_slots(pc, 0) == 1 and casting.prepare_refusal(pc, 0) == ""
    casting.prepare(pc, "daze")
    assert casting.open_slots(pc, 0) == 0
    assert casting.prepare_refusal(pc, 0) == ("No open cantrip slot today: Ysolde Marrach "
                                              "holds 3 cantrips. Unprepare one first.")


def _scene_for(pc):
    from rules.engine import Scene

    s = Scene(location_id="5bbd0c40345f")
    s.add(pc)
    return s


# --- the page ---------------------------------------------------------------------------

def _after_the_cast(tmp_path, **cast):
    pc = ysolde()
    s = _scene_for(pc)
    for spell in cast.get("spells", ("burning-hands",)):
        _cast(s, spell)
    sp = full_sheet(pc)["spells"]
    return sp, _render(sp, tmp_path)


def test_the_slot_count_is_said_once_in_the_levels_header(tmp_path):
    """The screenshot's two cards each said "1 of 2 level 1 slots left". The count is the
    level header's now, exactly once in the page, and no card carries it; each card
    says its own state, "1 prepared"."""
    sp, out = _after_the_cast(tmp_path)
    html = out["html"]
    assert html.count("slots left") == 1
    els = _tree(html)
    heads = [e for e in els if e["tag"] == "h4" and "sx-levelhead" in e["attrs"].get("class", "")]
    lvl1 = next(h for h in heads if h["text"].strip().startswith("Level 1"))
    assert "1 of 2 slots left" in lvl1["text"]
    cards = [e for e in els if e["tag"] == "article"]
    assert [c["attrs"]["aria-label"] for c in cards] == ["Magic Missile"]
    assert "slots left" not in cards[0]["text"] and "1 prepared" in re.sub(
        r"\s+", " ", cards[0]["text"])


def test_prepare_is_disabled_with_its_reason_beside_it(tmp_path):
    """No open level 1 slot: every level 1 Prepare, on the card and in the grimoire, is
    disabled and described by a visible reason. The card's points at the line under the
    level header, which is the endpoint's own sentence; a grimoire row carries the short
    form in the row. Measured before: the button stayed live and the press came back as
    red text at the column's top."""
    sp, out = _after_the_cast(tmp_path)
    els = _tree(out["html"])
    blocked = _level(sp, 1)["blocked"]
    assert blocked == "No open level 1 slot today. Unprepare one first."
    by_id = {e["attrs"]["id"]: e for e in els if e["attrs"].get("id")}
    card_prep = [e for e in els if e["tag"] == "button" and e["attrs"].get("data-action") == "prepare"
                 and any(a["tag"] == "article" for a in e["ancestors"])]
    assert card_prep
    for b in card_prep:
        assert "disabled" in b["attrs"]
        assert by_id[b["attrs"]["aria-describedby"]]["text"].strip() == blocked
    rows = {e["attrs"]["data-spell"]: e for e in els if e["attrs"].get("class") == "gx-row"}
    for sid in ("burning-hands", "shield", "sleep"):
        btn = next(e for e in els if rows[sid] in e["ancestors"]
                   and e["attrs"].get("data-action") == "prepare")
        assert "disabled" in btn["attrs"] and "draggable" not in rows[sid]["attrs"]
        why = by_id[btn["attrs"]["aria-describedby"]]
        assert rows[sid] in why["ancestors"]
        assert why["text"].strip() == "No open slot; unprepare one first."
    # A cantrip with room left is still offered: level 0 has its own rule.
    daze = next(e for e in els if rows["daze"] in e["ancestors"]
                and e["attrs"].get("data-action") == "prepare")
    assert "disabled" not in daze["attrs"]


def test_a_spent_level_says_so_in_the_owners_words(tmp_path):
    sp, out = _after_the_cast(tmp_path, spells=("burning-hands", "magic-missile"))
    html = out["html"]
    assert "Spent for today; it comes back after a long rest." in html


def test_the_sockets_have_three_states_named_in_words(tmp_path):
    """The owner (2026-09-29): "perhaps a red bubble instead of a bronze one to indicate
    a spent slot". After the cast: one bronze (Magic Missile waiting), one red (spent),
    none dark; each socket is named ("Level 1 slot: spent today") and the line under
    them says "1 ready, 1 spent, 0 open", so colour is never the only carrier (WCAG
    1.4.1). The cantrip row stays bronze: cantrips are never spent."""
    sp, out = _after_the_cast(tmp_path)
    els = _tree(out["html"])
    levels = [e for e in els if e["attrs"].get("class") == "sock-level"]
    lvl1 = next(l for l in levels if l["text"].strip().startswith("Level 1"))
    gems = [e for e in els if lvl1 in e["ancestors"] and e["tag"] == "i"]
    assert [g["attrs"]["class"] for g in gems] == ["gem lit", "gem spent"]
    assert [g["attrs"]["aria-label"] for g in gems] == [
        "Level 1 slot: prepared, ready", "Level 1 slot: spent today"]
    assert "1 ready, 1 spent, 0 open" in lvl1["text"]
    cantrips = next(l for l in levels if l["text"].strip().startswith("Cantrips"))
    assert not [e for e in els if cantrips in e["ancestors"] and e["tag"] == "i"
                and "spent" in e["attrs"].get("class", "")]


def test_the_spent_gem_is_the_pages_own_red():
    """No new colour: the spent stone is drawn from the palette's blood tokens (--alarm,
    --bloodglow, --blood), and any literal in its rule already appears elsewhere in the
    stylesheet."""
    css = TABLE.read_text(encoding="utf-8")
    style = css[css.index("<style>"):css.index("</style>")]
    rule = re.search(r"\.gem\.spent \{(.*?)\n  \}", style, re.S).group(1)
    for token in ("var(--alarm)", "--bloodglow", "var(--blood)"):
        assert token in rule
    rest = style.replace(rule, "")
    for hexcol in set(re.findall(r"#[0-9a-fA-F]{6}\b", rule)):
        assert hexcol in rest, f"{hexcol} is a new colour"


def test_refusals_are_quiet_and_beside_the_spell():
    """An endpoint refusal is never raw red text at the top: the `.sx-say.err` red is
    gone, and `spellsRefused` puts the sentence in the card, row or cantrip line the
    pressed button belongs to. The strip label that read "COMPONEN…" is a short word and
    the strip has no ellipsis to cut the next one."""
    js = (TABLE_SCRIPTS / "05-sheet.js").read_text(encoding="utf-8")
    css = TABLE.read_text(encoding="utf-8")
    assert ".sx-say.err" not in css and "spellsSay(e.message" not in js
    assert 'closest(".spcard, .gx-row, .sx-cantrip")' in js
    assert "spellsRefused(spell, e.message" in js
    strip = re.search(r"\.spcard-strip dt \{[^}]*\}", css).group(0)
    assert "ellipsis" not in strip
    card = js[js.index("function spellCard("):js.index("function grimoireIndex(")]
    assert '["Parts", (k.components' in card and '["Components", (k.components' not in card

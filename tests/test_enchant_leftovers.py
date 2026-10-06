"""Enchanting leftovers (wave 2): what the lanes and the final pass left measured and unfixed.

Each test names the defect as it was measured on build/enchanting e566dc9 with the same
records, before the fix on build/enchanting-leftovers.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from rules import curses, forge_items, magic_layer
from rules.sheet import full_sheet, situated
from tests._board import face_to_face
from tests.test_curses import Script
from tests.test_enchant_c2 import _armed_with, _cursed, _gutter_dice
from tests.test_enchant_engine import _fight, _foe, _hits, _run, _swing, _table

ROOT = Path(__file__).resolve().parent.parent
TABLE_JS = ROOT / "play" / "static" / "js" / "table"
SHELL = TABLE_JS / "45-enchant-shell.js"


def _forged(rid: str, base: str = "longsword", name: str | None = None) -> dict:
    return forge_items.record_for_base(base, gear="weapon", quality_index=3, item_id=rid,
                                       name=name or rid.replace("-", " ").title())


def _wear(e, item):
    return _run(e, [{"op": "wear", "actor": "pc", "because": "t",
                     "params": {"item": item}}]).outcomes[0]


def _throw(s, e, foe, face=10):
    face_to_face(s, b=foe.ref)
    s.turn = [r for r, _ in s.initiative].index("pc")
    r = _run(e, [{"op": "attack", "actor": "pc", "target": foe.ref, "visibility": "player",
                  "params": {"thrown": True}, "because": "t"}])
    first = r.awaiting
    r = e.resume(face)
    while r.awaiting:
        r = e.resume(int(r.awaiting["min"]))
    return first, next(o for o in r.outcomes if o.op == "attack")


# --- 1. "draw my longsword" ---------------------------------------------------------------------

def test_a_forged_longsword_is_drawn_by_the_words_a_player_uses():
    """Measured: with the Superior Iron Longsword in the pack, "longsword", "my longsword"
    and "sword" were each refused "Kesst Vayr is not carrying longsword." —
    `crafted_record` matched only the record's id or its whole name. One match is that
    sword."""
    for said in ("longsword", "my longsword", "sword", "the Longsword"):
        s, e = _table()
        pc = s.pc()
        pc.add_stock(forge_items.stock_item(_forged("sil1", name="Superior Iron Longsword")))
        out = _wear(e, said)
        assert out.tell == "Kesst Vayr draws the Superior Iron Longsword.", (said, out.tell)
        assert pc.equipped == "sil1"


def test_two_forged_swords_are_asked_about_by_name_never_guessed_between():
    """Two carried records answer to "sword": the engine names both and draws neither."""
    s, e = _table()
    pc = s.pc()
    pc.add_stock(forge_items.stock_item(_forged("sil1", name="Superior Iron Longsword")))
    pc.add_stock(forge_items.stock_item(_forged("fss", "short sword", "Fine Steel Short Sword")))
    out = _wear(e, "sword")
    assert "the Superior Iron Longsword and the Fine Steel Short Sword" in out.tell
    assert out.tell.endswith("Which one?") and pc.equipped == "rapier"
    assert _wear(e, "longsword").tell == "Kesst Vayr draws the Superior Iron Longsword."


def test_the_loose_word_never_turns_a_plain_weapon_into_a_forged_one():
    """`Actor.weapon("rapier")` and every reader that asks `crafted_record` by key stay
    exact: Kesst's plain rapier is still the table's rapier with a forged rapier in the
    pack, and "rapier" draws the plain one she carries."""
    s, e = _table()
    pc = s.pc()
    pc.add_stock(forge_items.stock_item(_forged("frap", "rapier", "Fine Iron Rapier")))
    assert pc.crafted_record("rapier") is None
    assert "crafted_record" not in pc.weapon("rapier")
    _wear(e, "dagger")
    assert _wear(e, "rapier").tell == "Kesst Vayr draws the rapier."


# --- 2. the sheet's attack list -----------------------------------------------------------------

def test_the_sheet_lists_the_forged_weapon_in_hand_with_its_to_hit():
    """Measured: with the Superior Iron Longsword drawn, `full_sheet` offense.attacks held
    the rapier and the dagger only, so the Combat card had no to-hit for the weapon being
    swung (rechecked after lane C2's refresh_worn: still missing)."""
    s, e = _table()
    pc = s.pc()
    pc.add_stock(forge_items.stock_item(_forged("sil1", name="Superior Iron Longsword")))
    _wear(e, "sil1")
    rows = {a["key"]: a for a in full_sheet(pc)["offense"]["attacks"]}
    row = rows["sil1"]
    assert row["name"] == "Superior Iron Longsword" and row["equipped"] is True
    assert not rows["rapier"]["equipped"]
    assert row["attack"]["total"] == sum(m.value for m in pc.attack_modifiers("sil1"))
    assert row["damage_dice"] == "1d8" and row["crit"] == "19-20/x2"
    assert row["swings"] == [row["attack"]["total"]]


# --- 3. thrown weapons --------------------------------------------------------------------------

def test_a_thrown_dagger_rolls_dexterity_to_hit_and_keeps_strength_on_damage():
    """CRB, Combat: the ranged attack bonus is BAB + Dex, and "When you hit with a melee or
    thrown weapon ... add your Strength modifier to the damage result". Measured: a thrown
    dagger rolled BAB + Str, as if it were stabbed — the popup's breakdown read "Str"."""
    s, e = _table()
    pc = s.pc()
    pc.abilities.update({"str": 16, "dex": 14})       # Finesse does not help: Str is better
    stab = [m.source for m in pc.attack_modifiers("dagger")]
    throw = [m.source for m in pc.attack_modifiers("dagger", thrown=True)]
    assert "Str" in stab and "Dex" not in stab
    assert "Dex" in throw and "Str" not in throw
    assert [m.source for m in pc.damage_modifiers("dagger")] == ["Str"]
    foe = _foe(s)
    _fight(s, e, foe)
    _wear(e, "dagger")
    asked, out = _throw(s, e, foe)
    sources = [b["source"] for b in asked["breakdown"]]
    assert "Dex" in sources and "Str" not in sources, sources
    assert "lies where it fell" in out.tell


def test_the_sheet_says_a_thrown_weapons_own_to_hit():
    """The Combat card printed "thrown to-hit not known": the row now carries it."""
    s, e = _table()
    pc = s.pc()
    pc.abilities.update({"str": 16, "dex": 14})
    rows = {a["key"]: a for a in full_sheet(pc)["offense"]["attacks"]}
    assert rows["dagger"]["thrown_attack"]["total"] == sum(
        m.value for m in pc.attack_modifiers("dagger", thrown=True))
    assert "thrown_attack" not in rows["rapier"]


# --- 4. picking up a crafted weapon ---------------------------------------------------------------

def test_a_thrown_forged_dagger_picked_back_up_writes_no_goods_and_is_in_hand():
    """Measured: a thrown Fine Iron Dagger picked back up left `goods: {"fdag": 1}` (a
    nameless second line for a thing still on the shelf), stayed out of the hand
    (`equipped: unarmed`) although the tell said "it is in hand again", and the tell
    called it "the fdag"."""
    s, e = _table()
    pc = s.pc()
    pc.add_stock(forge_items.stock_item(_forged("fdag", "dagger", "Fine Iron Dagger")))
    _wear(e, "fdag")
    foe = _foe(s)
    _fight(s, e, foe)
    _throw(s, e, foe)
    assert pc.equipped == "unarmed"
    prop = s.props[-1]["name"]
    r = _run(e, [{"op": "give", "actor": "pc", "because": "t",
                  "params": {"item": prop, "to": "pc"}}])
    tell = " ".join(o.tell for o in r.outcomes if o.op == "give")
    assert "takes the fine iron dagger back up off the ground" in tell, tell
    assert "fdag" not in tell
    assert dict(pc.goods) == {} and pc.equipped == "fdag" and "fdag" in pc.stock


# --- 7. curse drawbacks ---------------------------------------------------------------------------

BLURRED = (61, 55)            # drawback -> blurred sight
STUNNED = (61, 52)            # drawback -> stunned once a day


def test_blurred_sight_rides_the_wielder_on_every_roll_and_is_felt_on_the_draw():
    """CRB: "Character's vision is blurry (-2 penalty on attack rolls, saves, and skill
    checks requiring vision)". Measured: lane F put its terms in the weapon's `specs`, which
    belong to that weapon's own swing — the wielder's Fortitude had no -2, and nothing ever
    found the curse (it acts only through roll terms)."""
    s, e, pc = _armed_with(_cursed("blur", BLURRED))
    with situated(s):
        fort = [(m.value, m.source) for m in pc.save_modifiers("fort")]
        dagger = [(m.value, m.source) for m in pc.attack_modifiers("dagger")]
        seen = [(m.value, m.source) for m in pc.skill_modifiers("Perception")]
    assert (-2, "Blur") in fort and (-2, "Blur") in dagger and (-2, "Blur") in seen
    assert pc.item_records("blur")[0]["magic"]["known"]["curse"] is True


def _strike_at(e, hour: int, minute: int):
    real = e.scene._dice.roll

    def roll(notation, mods=None, label="", visibility="hidden"):
        if label.endswith("which hour"):
            return e.dice.given_total(hour, notation, [], label=label)
        if label.endswith("which minute"):
            return e.dice.given_total(minute, notation, [], label=label)
        if "1d4" in str(notation):
            return e.dice.given_total(3, notation, [], label=label)
        return real(notation, mods, label=label, visibility=visibility)

    e.scene._dice.roll = roll


def test_the_stunning_drawback_strikes_once_a_day_at_its_own_minute():
    """CRB drawback: "Character is stunned for 1d4 rounds ... (or randomly, 1/day)".
    Measured: its `apply_condition` with `periodic: "day"` had no reader — a whole day
    with the blade in hand changed nothing and said nothing. Now the day's minute is rolled
    (hour, then minute), the stun lands through the applicator when the clock crosses it,
    and the first strike finds the curse."""
    s, e, pc = _armed_with(_cursed("stunner", STUNNED))
    s.clock_minutes = 9 * 60
    _strike_at(e, 15, 31)                     # the day's minute: 14:30
    before = s.advance(minutes=60)            # 09:00 -> 10:00, the minute is rolled
    assert not pc.has_condition("stunned")
    assert not any("stun" in line for line in before["ended"])
    s.clock_minutes = 14 * 60 + 29
    hit = s.advance(minutes=1)                # crosses 14:30
    assert pc.has_condition("stunned"), hit["ended"]
    line = next(x for x in hit["ended"] if "stunned" in x)
    assert line.startswith("Kesst Vayr is stunned by the stunner for 3 rounds.")
    assert "The stunner is cursed. Drawback: once a day" in line
    assert pc.item_records("stunner")[0]["magic"]["known"]["curse"] is True
    # Once that day: the rest of it passes without another.
    later = s.advance(minutes=8 * 60)
    assert not any("stunned by" in x for x in later["ended"])


def test_a_stun_inside_a_long_wait_is_told_as_past_and_leaves_nothing_on():
    s, e, pc = _armed_with(_cursed("stunner", STUNNED))
    s.clock_minutes = 0
    _strike_at(e, 5, 1)                       # 04:00
    out = s.advance(minutes=8 * 60)
    assert not pc.has_condition("stunned")
    assert any("left Kesst Vayr stunned for 3 rounds along the way" in x for x in out["ended"])


def test_an_unknown_stunning_blade_says_nothing_until_it_strikes():
    """Hidden means hidden (law 3): drawn, put away, carried — no line names it."""
    s, e, pc = _armed_with(_cursed("stunner", STUNNED))
    s.clock_minutes = 12 * 60
    _strike_at(e, 20, 1)
    out = s.advance(minutes=30)
    assert not any("stun" in x.lower() or "cursed" in x for x in out["ended"])
    _wear(e, "rapier")
    out = s.advance(minutes=10)
    assert not any("stunner" in x.lower() for x in out["ended"])


def _shaky_cloak():
    cloak = {"id": "shaky-cloak", "name": "Shaky Cloak", "gear": "cloak", "slot": "shoulders"}
    adds = {"powers": [{"recipe": "mi-cloak-resistance-1"}]}
    plan = magic_layer.plan(cloak, adds, binder={"level": 5})
    curse = curses.roll(Script(36, 1), cloak, dict(plan, adds=adds))      # unreliable
    return magic_layer.write(cloak, adds, binding={"level": 5}, curse=curse)


def test_an_unreliable_cloak_of_resistance_can_fail_the_save_it_exists_for():
    """CRB: "Each time the item is activated, there is a 5% chance ... that it does not
    function." Measured: the unreliable cloak's d% was rolled for blows aimed at its wearer
    (`_worn_gutters`, for AC it does not give) and never for a save, so its +1 never once
    failed where it mattered. Rolled once per save now, with the die shown."""
    s, e = _table()
    pc = s.pc()
    pc.wear(_shaky_cloak(), 0)

    def save():
        return _run(e, [{"op": "save", "actor": "pc", "because": "t", "visibility": "hidden",
                         "params": {"save": "fort", "dc": 12}}]).outcomes[0]

    _gutter_dice(e, 3)
    off = save()
    assert "Shaky Cloak" not in [m.source for m in off.rolls[0].modifiers]
    assert "The shaky cloak's magic gutters and does nothing this time (3 on d%)." in off.tell
    assert [r.label for r in off.rolls] == ["Fortitude save", "Shaky Cloak: does it work?"]
    _gutter_dice(e, 50)
    on = save()
    assert "Shaky Cloak" in [m.source for m in on.rolls[0].modifiers]
    assert "gutters" not in on.tell
    # Read only inside the save: the next roll in the batch still has its cloak.
    assert "Shaky Cloak" in [m.source for m in pc.save_modifiers("fort")]


def test_a_ring_that_lends_no_save_is_not_rolled_for_one():
    """The d% is the item's use: a save reads only what lends saves, so an unreliable
    sword in hand is not rolled — and does not "gutter" — when its bearer saves."""
    s, e, pc = _armed_with(_cursed("shaky", (36, 1)))
    _gutter_dice(e, 3)
    out = _run(e, [{"op": "save", "actor": "pc", "because": "t", "visibility": "hidden",
                    "params": {"save": "fort", "dc": 12}}]).outcomes[0]
    assert len(out.rolls) == 1 and "gutters" not in out.tell


def test_unreliable_armour_of_spell_resistance_can_fail_against_a_spell():
    """Measured: SR from an unreliable item was read on every cast and never rolled for, so
    its rating never failed. A spell reaching the wearer is its use now."""
    from tests.test_e_magic_harm import board
    from tests.test_item_powers import _cast_at

    band = {"id": "shaky-band", "name": "Shaky Band", "slot": "ring",
            "specs": [{"type": "spell_resistance", "amount": 19, "gutters_pct": 5,
                       "origin": "item:shaky-band"}],
            "magic": {"schema": 1, "enhancement": 0, "properties": [], "flat": [],
                      "powers": [], "curse": curses.roll(Script(36, 1), {"gear": "ring"},
                                                         {"caster_level": 5})}}
    s, e, man = board(fight=True)
    who = s.actors[man]
    who.hp = who.hp_max = 100
    who.wear(band, 0)
    _gutter_dice(e, 2)
    out, asked = _cast_at(s, e, who, 1)
    assert not any(a.startswith("Caster level check") for a in asked), asked
    assert "Shaky Band's magic gutters" in out.tell or "shaky band's magic gutters" in out.tell
    assert who.hp < 100


# --- 8. disarming a clinging weapon -----------------------------------------------------------------

def test_a_clinging_blade_will_not_be_disarmed_and_the_curse_is_found():
    """CRB, -2 cursed sword: it "can be gotten rid of only by means of break enchantment,
    limited wish, miracle, remove curse, or wish". Measured: a disarm knocked the specific
    cursed blade to the ground — the one door out of the hand `_clinging` was never asked
    at (sell, give, take off and wearing something else all were)."""
    s, e, pc = _armed_with(_cursed("leech", (91,)))
    foe = _foe(s)
    _fight(s, e, foe)
    face_to_face(s, b=foe.ref)
    foe.add_buff("combat_mod", "cmb", 40, source="test", rounds=100)
    s.turn = [r for r, _ in s.initiative].index(foe.ref)
    r = _run(e, [{"op": "attack", "actor": foe.ref, "target": "pc", "because": "t",
                  "params": {"manoeuvre": "disarm"}}])
    while r.awaiting:                         # the attack of opportunity it provokes: missed
        r = e.resume(1)
    out = [o for o in r.outcomes if o.op == "attack"][-1]
    assert out.tell.startswith("The thug disarms Kesst Vayr by"), out.tell
    assert pc.equipped == "leech", out.tell
    assert "will not leave Kesst Vayr's hand" in out.tell
    assert "The leech is cursed." in out.tell
    assert not any(p.get("from_") == "leech" for p in s.props)
    assert any(x.get("kind") == "kept" for x in out.effects)


# --- 6. small UI ---------------------------------------------------------------------------------

def _node(js: str):
    out = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def _fn(src: str, head: str) -> str:
    start = src.index(head)
    depth, i = 0, src.index("{", start)
    while True:
        depth += {"{": 1, "}": -1}.get(src[i], 0)
        i += 1
        if depth == 0:
            return src[start:i]


def test_a_read_down_phial_says_less_than_a_whole_mote_not_zero():
    """Seen in the final pass: a one-mote essence read to 0.9 of a phial showed "0 motes"
    beside "0.9 on your shelf". The engine counts whole motes (full x tenths, rounded down),
    so it is said as what it is."""
    src = SHELL.read_text(encoding="utf-8")
    fn = _fn(src, "E.moteWords = function")
    got = _node("var E = {};" + fn + ";console.log(JSON.stringify([0, 1, 4, null].map(E.moteWords)))")
    assert got == ["less than a whole mote", "1 mote", "4 motes", ""]
    for name in ("46-enchant-shelf.js", "48-enchant-working.js"):
        assert "E.moteWords(" in (TABLE_JS / name).read_text(encoding="utf-8"), name


def test_a_live_score_rising_a_band_rings_the_stages_tier_up_once():
    """`enchant.tier.up` was registered and the stage had `flourish("tierUp")`, and no
    bench ever called it. The shell now watches the live score with the strip's own band
    rule (0.015 either side of a bound), so a needle resting on an edge rings once."""
    src = SHELL.read_text(encoding="utf-8")
    fn = _fn(src, "function tierWatch(")
    got = _node(fn + ";var w = tierWatch({names: ['a','b','c','d','e']});"
                "console.log(JSON.stringify([0.1, 0.21, 0.22, 0.19, 0.21, 0.23, 0.5, 0.45]"
                ".map(w)))")
    assert got == [False, False, True, False, False, False, True, False]
    assert re.search(r'if \(rose\(s\)\) flourish\("tierUp"\);', src)
    assert re.search(r'kind === "tierUp"\) \{\s*if \(!staged\) E\.sound\("enchant\.tier\.up"\);',
                     src)


def test_the_top_bars_quiet_buttons_take_talks_phone_size():
    """Measured at 390x844 (scratch server, the circle open, on this branch and on master
    alike): the top bar was 403px wide, its end group 273px (Talk 64, Music 87, Settings
    106 at desktop padding and tracking), so the whole page scrolled sideways. With Music
    and Settings at Talk's phone size the bar measured 390 at 390 and 360 at 360."""
    html = (ROOT / "play" / "templates" / "play" / "table.html").read_text(encoding="utf-8")
    phone = html[html.index("Phone: the story is the page"):]
    phone = phone[:phone.index("\n  }\n")]
    assert ".topend > .v2-btn.is-quiet { min-height: 36px; padding: 6px 10px;" in phone
    assert ".topend { gap: 6px; }" in phone


def test_closing_the_conversion_notice_returns_to_the_method_strip_not_close():
    """Measured in the final pass: the notice opens on the circle's first state, while the
    layer's Close holds focus (the method strip is not drawn yet), and closing it put focus
    back on Close, one Enter from leaving the circle."""
    src = SHELL.read_text(encoding="utf-8")
    body = _fn(src, "function showConversions(")
    assert 'back.id === "enchant-close") core.focusFirst();' in body

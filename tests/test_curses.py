"""Curses (enchanting plan §11, contracts §7, lane F) on the REAL table and the REAL layer.

The owner's rulings (docs/enchanting-answers.md): book curses, hidden — a Bind missed by 5
or more takes FLAWED, the item works and carries a curse from the book's table, and WHICH
curse stays hidden until identified by 10 or found the hard way (rounds 1 and 4 Q2); the
gender, race and alignment changes, polymorph, the incurable disease and the compulsion to
attack are dropped and the d% re-scaled over the rest (round 4 Q3). Each test names the
defect it prevents.
"""
from __future__ import annotations

import json

import pytest

from rules import curses, effectspec, knowledge, magic_layer
from rules.dice import Dice, Modifier, stack
from rules.sheet import _when_holds


# --- builders --------------------------------------------------------------------------------

def forged(rid="cursed-longsword", head="steel", base="longsword", q=3):
    return {"id": rid, "name": "Longsword", "kind": "crafted", "craft": "blacksmith",
            "count": 1, "gear": "weapon", "base": base, "slot": "hands",
            "quality_index": q, "masterwork": q >= 3,
            "pieces": {"head": {"material": head, "passes": 1},
                       "haft": {"material": "ash-haft", "passes": 0},
                       "fittings": {"material": "brass-guard", "passes": 0}},
            "quench": None, "finish": [], "flaws": [], "smith": {"level": 3, "perks": {}},
            "schema": 3}


def ring(rid="cursed-ring"):
    return {"id": rid, "name": "Ring", "gear": "ring", "slot": "ring"}


class Script:
    """Dice that answer what the test says, so every row of the table can be reached."""

    def __init__(self, *faces):
        self.faces = list(faces)

    def __call__(self, n):
        face = self.faces.pop(0) if self.faces else 1
        assert 1 <= face <= n, f"scripted {face} on a d{n}"
        return face


ADDS = {"enhancement": 1, "properties": [{"id": "flaming"}]}


def flawed(script, record=None, adds=ADDS, level=10):
    """A flawed binding as lane E will do it: plan, roll the curse, write the layer."""
    rec = record or forged()
    plan = magic_layer.plan(rec, adds, binder={"level": level})
    curse = curses.roll(script, rec, dict(plan, adds=adds))
    return magic_layer.write(rec, adds, binding={"level": level}, curse=curse, day=3), curse


def every_path():
    """One scripted die sequence per row of every table: the top row, then each sub-row."""
    out = []
    for top in curses.rows():
        lo = top["d100"][0]
        if not top.get("table"):
            out.append((f"{top['id']}", [lo]))
            continue
        for sub in curses.sub_table(top["table"]):
            if sub.get("table"):
                for sub2 in curses.sub_table(sub["table"]):
                    out.append((f"{top['id']}:{sub['id']}:{sub2['id']}",
                                [lo, sub["d100"][0], sub2["d100"][0], 1, 1]))
            else:
                out.append((f"{top['id']}:{sub['id']}", [lo, sub["d100"][0], 1, 1]))
    return out


PATHS = every_path()


# --- the table ---------------------------------------------------------------------------------

def test_the_top_table_is_the_books_d_percent_unchanged():
    """The owner dropped rows of the SUB-tables, never a family: the book's seven
    families keep their printed ranges (CRB Cursed Items: 01-15 delusion ... 91-100 a
    specific cursed item)."""
    assert [(r["id"], tuple(r["d100"])) for r in curses.rows()] == [
        ("delusion", (1, 15)), ("opposite", (16, 35)), ("intermittent", (36, 45)),
        ("requirement", (46, 60)), ("drawback", (61, 75)), ("different", (76, 90)),
        ("specific", (91, 100))]
    assert curses.ROWS == curses.rows()


def test_the_rows_the_owner_dropped_are_gone_and_said_so():
    """Owner round 4 Q3: gender, race and alignment changes, polymorph, the incurable
    disease and the compulsion to attack are dropped. Each is absent from the drawback
    table AND listed in `dropped` with its reason, so the identify card can never name
    one and the next reader knows it was a ruling, not an oversight."""
    names = " ".join(r["name"].lower() for r in curses.sub_table("drawback"))
    for word in ("gender", "race", "alignment", "polymorph", "disease", "attack"):
        assert word not in names
    dropped = " ".join(d["name"].lower() for d in curses.table()["dropped"]
                       if d["table"] == "drawback")
    for word in ("gender", "race", "alignment", "polymorph", "disease", "attack"):
        assert word in dropped
    assert all(d["why"] for d in curses.table()["dropped"])


def test_no_kept_row_reads_alignment():
    """No alignment is tracked (owner round 4 Q7): a row reading it could never fire.
    Measured on the book's dependent table: 'in the hands of a creature of particular
    alignment' (91-95) — waived with its note."""
    blob = json.dumps(curses.table()["tables"]).lower()
    assert "alignment" not in blob
    assert any("alignment" in d["name"].lower() and d["table"] == "dependent"
               for d in curses.table()["dropped"])


def _largest_remainder(widths):
    total = sum(widths)
    exact = [w * 100 / total for w in widths]
    base = [int(e) for e in exact]
    for i in sorted(range(len(widths)), key=lambda i: (-(exact[i] - base[i]), i))[
            :100 - sum(base)]:
        base[i] += 1
    return base


@pytest.mark.parametrize("name", ["intermittent", "dependent", "requirement", "drawback"])
def test_the_rescale_is_the_rule_not_an_eye(name):
    """"The d% is re-scaled over the rest" (owner round 4 Q3). A hand re-scale drifts:
    each kept row's width is its book width (an even split where the book prints a list
    with no die) spread over 100 by the largest remainder, and the stored ranges are
    exactly that, contiguous from 1 to 100."""
    rows = curses.sub_table(name)
    widths = [(r["book_d100"][1] - r["book_d100"][0] + 1) if r.get("book_d100") else 1
              for r in rows]
    want = _largest_remainder(widths)
    got = [r["d100"][1] - r["d100"][0] + 1 for r in rows]
    assert got == want
    assert rows[0]["d100"][0] == 1 and rows[-1]["d100"][1] == 100
    assert all(a["d100"][1] + 1 == b["d100"][0] for a, b in zip(rows, rows[1:]))


def test_a_broken_table_is_refused_with_the_fix_named():
    """A gap in a d% range would leave a face that names no row and crash the Bind."""
    data = curses.table()
    data["tables"]["drawback"][3]["d100"][0] += 1
    problems = curses.table_problems(data)
    assert problems and "gap or overlap" in problems[0]


def test_every_curse_document_is_the_vocabulary_and_the_books_number():
    """No model authors a number (law 3): every document a curse adds validates in the
    effect vocabulary and is marked `book`."""
    for r in curses.sub_table("drawback"):
        for d in r.get("documents") or ():
            assert d.get("book") is True
            assert effectspec.validate(curses._filled(d, 7)) == []


# --- the roll and the seam ---------------------------------------------------------------------

@pytest.mark.parametrize("label,faces", PATHS, ids=[p[0] for p in PATHS])
def test_every_row_rolls_writes_and_reads_without_naming_itself(label, faces):
    """Every row reachable by the die must come out as a curse the layer can carry, and
    WHICH one must not leak (owner round 4 Q2): the curse's id and its words appear in
    neither the true layer, nor the card's believed layer, nor the item card, nor a
    failed or intent-only identify, nor the tell an unknown curse gets."""
    rec, curse = flawed(Script(*faces))
    path = label.split(":")
    assert curse["row"] == path[0] and curse["id"] == "curse:" + label
    words = curses.describe(curse)
    assert words
    true = magic_layer.layer(rec)
    seen = magic_layer.layer(rec, believed=True)
    card = knowledge.item_card(rec)
    pc = type("PC", (), {"herb_known": {}, "stock": {}})()
    failed = knowledge.identify(pc, json.loads(json.dumps(rec)), 0, day=1)
    intent = knowledge.identify(pc, json.loads(json.dumps(rec)), 18 + 9, day=1)
    assert intent["result"] == "intent"
    said = curses.tell(curse, "longsword", known=False)
    blob = json.dumps([true, seen, card, failed, intent, said])
    assert curse["id"] not in blob
    assert words not in blob
    # The believed layer is the maker's intent, curse or no curse.
    assert seen == magic_layer.layer(magic_layer.write(forged(), ADDS, binding={"level": 10},
                                                      day=3), believed=True)


def test_delusion_applies_nothing_and_the_card_still_shows_the_plus():
    """CRB: "no magical power other than to deceive". The terms the engine reads carry no
    +1 (which is how it is found the hard way); the card shows the maker's intent."""
    rec, _ = flawed(Script(1))
    true, seen = magic_layer.layer(rec), magic_layer.layer(rec, believed=True)
    assert true["specs"] == [] and true["riders"] == [] and true["strikes_as"] == []
    assert {(s["target"], s["amount"]) for s in seen["specs"]} == {("attack", 1),
                                                                   ("damage", 1)}


def test_opposite_turns_bonuses_into_penalties_and_the_flame_on_its_bearer():
    """CRB: "weapons that impose penalties on attack and damage rolls rather than
    bonuses". Measured before the seam existed: a flawed +1 flaming sword hit at +1 and
    burned the foe. Now it hits at -1 beside masterwork's +1 (a penalty is untyped and
    always stacks: the two cancel), and its flame is `recipient: self`."""
    rec, _ = flawed(Script(16))
    lay = magic_layer.layer(rec)
    atk = [s for s in lay["specs"] if s["target"] == "attack"]
    assert [(s["amount"], s["bonus_type"]) for s in atk] == [(-1, "untyped")]
    mods = [Modifier(1, "masterwork", "enhancement")] + [
        Modifier(s["amount"], "curse", "") for s in atk]
    assert sum(m.value for m in stack(mods)) == 0
    assert [r.get("recipient") for r in lay["riders"]] == ["self"]
    assert lay["strikes_as"] == [] and lay["enhancement"] == -1
    assert "magic" not in magic_layer.strikes_as_against(lay, lambda when: True)


def test_a_drawback_save_is_the_books_dc_and_rides_the_bearer():
    """CRB drawback: "Will save daily or lose 1 Intelligence", DC 10 + the item's caster
    level. On a weapon it rides the wielder (`wielded`), on a ring the wearer (`worn`),
    stamped with the item's origin and never the curse's name (law 3)."""
    will_int = next(r for r in curses.sub_table("drawback") if r["id"] == "will-int")
    rec, curse = flawed(Script(61, will_int["d100"][0]))
    gate = magic_layer.layer(rec)["wielded"][0]
    assert gate["type"] == "save_gate" and gate["target"] == "will"
    assert gate["dc"] == 10 + curse["cl"] == 10 + 10      # flaming's CL 10
    assert gate["on_failure"][0]["target"] == "int"
    assert gate["origin"] == "item:cursed-longsword" and gate["source"] == "binding"
    r = magic_layer.write(ring(), {"powers": [{"recipe": "mi-ring-protection-1"}]},
                          binding={"level": 6},
                          curse=dict(curse, gear="ring", cl=5))
    assert magic_layer.layer(r)["worn"][0]["dc"] == 15


def test_blurred_sight_is_three_untyped_penalties_through_the_funnel():
    """CRB: "-2 penalty on attack rolls, saves, and sight-based skill checks", each a
    standing modifier through the funnel, not a note — on the BEARER's list (`wielded` for
    a blade), because a weapon's `specs` belong to its own swing alone: measured
    2026-10-06 (enchanting leftovers), in `specs` it left the wielder's saves untouched and
    put its -2 on that sword's swings only (tests/test_enchant_leftovers.py)."""
    row = next(r for r in curses.sub_table("drawback") if r["id"] == "blurred")
    rec, _ = flawed(Script(61, row["d100"][0]))
    lay = magic_layer.layer(rec)
    pens = {(s["type"], s["target"]) for s in lay["wielded"] if s.get("amount") == -2}
    assert pens == {("combat_mod", "attack"), ("save_mod", "fort"), ("save_mod", "ref"),
                    ("save_mod", "will"), ("skill_mod", "perception")}
    assert not any(s.get("amount") == -2 for s in lay["specs"])


def test_a_dependent_item_fails_closed_until_the_situation_is_known():
    """Dependent (CRB: "functions only in specific situations"): every document gets the
    situation as a `when` clause, read by `_when_holds` like bane's foe. A roll whose
    context does not carry the fact drops the term, so the item does nothing rather than
    everything (a dependent curse that worked everywhere would be no curse)."""
    day = next(r for r in curses.sub_table("dependent") if r["id"] == "daylight")
    dep = next(r for r in curses.sub_table("intermittent") if r["id"] == "dependent")
    rec, _ = flawed(Script(36, dep["d100"][0], day["d100"][0]))
    lay = magic_layer.layer(rec)
    for doc in lay["specs"] + lay["riders"]:
        assert doc["when"]["daylight"] is True
        assert _when_holds(doc["when"], {}) is False
        assert _when_holds(doc["when"], {"daylight": True}) is True
        assert _when_holds(doc["when"], {"daylight": False}) is False


def test_the_phase_row_is_a_phase_of_the_day_not_a_planet():
    """Owner round 4 Q10: "this is not earth" — the book's astrological row became a
    phase of the day, rolled from rules/sky.py's phases."""
    from rules import sky

    ph = next(r for r in curses.sub_table("dependent") if r["id"] == "phase")
    dep = next(r for r in curses.sub_table("intermittent") if r["id"] == "dependent")
    rec, curse = flawed(Script(36, dep["d100"][0], ph["d100"][0], 3))
    assert curse["detail"]["phase"] == sky.PHASES[2]
    assert magic_layer.layer(rec)["specs"][0]["when"]["day_phase"] == sky.PHASES[2]
    assert f"at {sky.PHASES[2]}" in curses.describe(curse)


def test_an_unreliable_item_gutters_on_one_to_five():
    """CRB: "a 5% chance (01-05 on d%) that it does not function"."""
    unrel = next(r for r in curses.sub_table("intermittent") if r["id"] == "unreliable")
    rec, curse = flawed(Script(36, unrel["d100"][0]))
    assert curses.gutters(curse, 5) and not curses.gutters(curse, 6)
    assert all(d["gutters_pct"] == 5 for d in magic_layer.layer(rec)["specs"])
    assert not curses.gutters({"row": "delusion"}, 1)


def test_a_requirement_unmet_silences_the_item_until_a_day_it_is_met():
    """Plan §11.2: "Unmet, the layer is suppressed until met". The day's facts come from
    the engine; a fact not sent changes nothing (empty is not absent); the change is told
    without naming the curse while it is hidden."""
    use = next(r for r in curses.sub_table("requirement") if r["id"] == "daily-use")
    rec, curse = flawed(Script(46, use["d100"][0]))
    assert magic_layer.layer(rec)["specs"]
    quiet, said = curses.settle_day(rec, {"used": False}, day=4)
    assert magic_layer.layer(quiet)["specs"] == []
    assert said == ["The magic in the Longsword has gone quiet."]
    assert curse["id"] not in json.dumps(said)
    same, nothing = curses.settle_day(quiet, {"slept_double": True}, day=5)
    assert same == quiet and nothing == []
    back, said = curses.settle_day(quiet, {"used": True}, day=5)
    assert magic_layer.layer(back)["specs"] and said == [
        "The magic in the Longsword stirs again."]
    assert rec["magic"]["curse"].get("state") == {}      # pure: the argument untouched


def test_a_blade_only_requirement_never_lands_on_a_ring():
    """"Draw blood every day" is a weapon's (plan §11.2). A ring that rolled it would carry
    a requirement it could never meet; the die steps to the next row that fits instead of
    rerolling, which keeps every other row's odds."""
    blood = next(r for r in curses.sub_table("requirement") if r["id"] == "draw-blood")
    curse = curses.roll(Script(46, blood["d100"][0]), ring(), {"caster_level": 5})
    assert curse["detail"]["requirement"] != "draw-blood"
    curse = curses.roll(Script(46, blood["d100"][0]), forged(), {"caster_level": 5})
    assert curse["detail"]["requirement"] == "draw-blood"


def test_a_completely_different_effect_is_like_for_like_and_the_same_on_every_read():
    """Plan §11.2: "another property of the same plus". Chosen at the roll and recorded,
    so the item does not change from one read to the next; the substitute fits the vessel
    and replaces the flame, the +1 stays."""
    rec, curse = flawed(Script(76, 1))
    sub = curse["detail"]["instead"]["properties"]["flaming"]
    prop = effectspec.property(sub["id"])
    assert prop["plus"] == effectspec.property("flaming")["plus"] and sub["id"] != "flaming"
    lay = magic_layer.layer(rec)
    assert effectspec.property_tag(sub["id"]) in lay["tags"]
    assert "property.flaming" not in lay["tags"]
    assert not any(d.get("source") == "property:flaming" for d in
                   lay["specs"] + lay["riders"])
    assert {(s["target"], s["amount"]) for s in lay["specs"]
            if s.get("source") == "enhancement"} == {("attack", 1), ("damage", 1)}
    assert magic_layer.layer(rec) == lay


def test_the_specific_cursed_item_is_minus_two_and_clings_until_lifted():
    """Plan §11.2: the "-2 cursed" shape, and "can only be discarded after ... remove
    curse" (CRB). Lifting it (Cleanse, remove curse at DC 10 + CL) keeps the rest."""
    rec, curse = flawed(Script(91))
    lay = magic_layer.layer(rec)
    assert {(s["target"], s["amount"], s["bonus_type"]) for s in lay["specs"]} == {
        ("attack", -2, "untyped"), ("damage", -2, "untyped")}
    assert curses.clings(rec) and curses.lift_dc(curse) == 20
    clean = curses.lift(rec)
    assert not curses.clings(clean) and clean["magic"]["known"]["curse"] is True
    assert {(s["target"], s["amount"]) for s in magic_layer.layer(clean)["specs"]} == {
        ("attack", 1), ("damage", 1)}


def test_a_cosmetic_drawback_is_noticed_at_once_and_changes_no_number():
    """CRB drawbacks like hair that grows an inch an hour are facts for the narrator,
    never numbers; anyone can see them, so the curse is found the moment it is carried."""
    rec, curse = flawed(Script(61, 1))
    assert curse["detail"]["drawback"] == "hair-grows" and curses.noticed(curse)
    assert magic_layer.layer(rec)["specs"] == magic_layer.layer(rec, believed=True)["specs"]
    assert curses.tell(curse, "longsword", known=True).startswith("The longsword is cursed.")


def test_a_real_dice_roll_lands_on_a_row_every_time():
    """The engine rolls with `dice.Dice`; 300 seeds must each give a curse the layer
    carries, so no face of any table falls between rows."""
    for seed in range(300):
        rec, curse = flawed(Dice(seed=seed))
        assert curse["row"] in {r["id"] for r in curses.rows()}
        magic_layer.layer(rec)


def test_a_malformed_curse_changes_nothing_and_never_crashes_the_layer():
    """A save carrying a curse from a later table must still load: the reader of the
    layer is in every attack, and a crash there ends the turn."""
    assert curses.documents({"row": "no-such-row"}, {}) == {}
    assert curses.documents(None, {}) == {}
    assert curses.describe({}) == ""

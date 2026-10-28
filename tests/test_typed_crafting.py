"""A craft typed at the table makes the craft's base item for real (rules/typed_craft.py).

The report, 2026-10-28: "My wife tries to level up blacksmithing through narration and
didn't get real items or experience." Reproduced before any change, on gemma-4-12B: of
eleven typed craft lines ("I forge a dagger at the anvil", "I brew a basic healing
draught", "I tan this hide into leather" …) the reader filed ten as `other` and one as
`cast`. `other` owes no op: nothing was rolled, nothing spent, nothing made, no mastery —
and the narrator wrote the forging done. The plan's one craft op, `craft`, paid mastery
from a tier the model chose and made no item at all.

The owner's ruling the same day: a typed craft line makes the base item through the
bench's own rules (roll, DC, place, materials, time, failure, mastery), points to the bench
for finer work, and refuses anything beyond base in words that send the player there.

Every test here runs on the shipped content — real metals, herbs, reagents and hides — not
fakes: the forge's own tests fake the material lanes, and a typed line has to work on what
ships.
"""
from __future__ import annotations

import pytest

from gm import acts_to_ops, interpret
from gm import beat_verify as bv
from rules import typed_craft
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc


@pytest.fixture(scope="module")
def world():
    from world.loader import load_cached

    return load_cached("fixtures/aurvantis-campaign.json")


def _engine(world, *, kit: str | None = "smith's field kit", carry=(), hides=()):
    town = world.by_name("Vormoor", kind="CITY").id
    s = Scene(location_id=town)
    pc = load_pc("fixtures/pc-kesst.json")
    s.add(pc)
    s.clock_minutes = 10 * 60
    e = Engine(s, Dice(seed=3), world=world)
    e.place_party()
    pc.inventory.clear()
    pc.stock.clear()
    if kit:
        pc.goods[kit] = 1
    for key, n in carry:
        pc.carry(key, n)
    if hides:
        from rules import leatherworker as lw

        for mid, form in hides:
            lw.put_hide(pc, lw.make_hide(mid, form=form, harvested_at=s.clock_minutes))
    return e, pc


def _make(e, craft, item, words="", work="plain", faces=(15, 15, 15, 15)):
    """The make op as the act->op table builds it, every step's die the player's own."""
    r = e.run(e.validate([{"op": "make", "actor": "pc",
                           "params": {"craft": craft, "item": item, "words": words,
                                      "work": work},
                           "because": "the player works at their craft"}]))
    asked = []
    faces = list(faces)
    while r.awaiting:
        asked.append(r.awaiting["label"])
        r = e.resume(faces.pop(0))
    out = next(o for o in r.outcomes if o.op == "make")
    return out, asked


def _named(pc, name):
    return [st for st in pc.stock.values() if st.name == name]


# --- blacksmithing -----------------------------------------------------------------------------

def test_typed_smithing_gave_no_item_and_no_mastery(world):
    """The report itself. Before: "I forge a dagger" made nothing and paid nothing. Now the
    forge's own chain runs — Forge (a bar and fuel into a dagger's blank, DC 12) then
    Assemble (the blank and a haft) — two of the player's d20s, 150 minutes, and an Iron
    Dagger in the pack at Sound, the plain book item, with Blacksmith mastery paid."""
    e, pc = _engine(world, carry=(("iron", 2), ("charcoal", 2), ("ash-haft", 1)))
    before = e.scene.clock_minutes
    out, asked = _make(e, "blacksmith", "a dagger", "forge a dagger at the anvil")
    assert out.status == "resolved" and out.verdict == "success", out.tell
    assert asked == ["Blacksmithing: Forge", "Blacksmithing: Assemble"]
    assert len(_named(pc, "Iron Dagger")) == 1
    assert pc.inventory.get("iron") == 1 and pc.inventory.get("charcoal") == 1
    assert "ash-haft" not in pc.inventory
    assert pc.track("blacksmith").mp > 0 or pc.track("blacksmith").level > 1
    assert e.scene.clock_minutes - before == 150
    made = [ef for ef in out.effects if ef.get("kind") == "made"]
    assert made[-1]["item"] == "Iron Dagger" and made[-1]["to"] == "pc"
    assert made[-1]["quality"] == "Sound"
    # The tell points to the bench for finer work, and the effect carries which bench.
    assert "forge bench" in out.tell
    assert {"kind": "bench", "bench": "forge"}.items() <= next(
        ef for ef in out.effects if ef.get("kind") == "bench").items()


def test_no_forge_here_is_refused_in_words_and_nothing_changes(world):
    """Inform's check rule: the missing thing named, and the action stopped before anything
    changes — no die, no time, no material."""
    e, pc = _engine(world, kit=None, carry=(("iron", 2), ("charcoal", 1), ("ash-haft", 1)))
    before = (dict(pc.inventory), e.scene.clock_minutes)
    out, asked = _make(e, "blacksmith", "a dagger")
    assert out.status == "refused" and out.code == "no_forge" and asked == []
    assert "no forge here" in out.tell and "forge bench" in out.tell
    assert (dict(pc.inventory), e.scene.clock_minutes) == before


def test_no_iron_is_refused_naming_what_is_missing(world):
    e, pc = _engine(world, carry=(("charcoal", 1), ("ash-haft", 1)))
    out, asked = _make(e, "blacksmith", "an iron spear")
    assert out.status == "refused" and out.code == "no_material" and asked == []
    assert "no iron to forge a spear" in out.tell
    # Short, not missing: measured live, "no metal … (2 carried, 3 needed)" said both.
    e, pc = _engine(world, carry=(("iron", 2), ("charcoal", 1), ("ash-haft", 1)))
    out, asked = _make(e, "blacksmith", "a chain shirt")
    assert out.code == "no_material" and asked == []
    assert "not enough metal to forge a chain shirt" in out.tell and "2 are in the pack" \
        in out.tell


def test_ore_at_a_field_kit_is_refused_because_smelting_needs_a_smithy(world):
    e, pc = _engine(world, carry=(("iron-ore", 4), ("charcoal", 4), ("ash-haft", 1)))
    out, _asked = _make(e, "blacksmith", "a dagger")
    assert out.code == "needs_smithy" and "smithy's furnace" in out.tell


def test_a_special_metal_named_is_refused_and_sent_to_the_bench(world):
    """"A mithral longsword": a special material is finer work, never half-made."""
    e, pc = _engine(world, carry=(("iron", 2), ("charcoal", 2), ("ash-haft", 1)))
    out, asked = _make(e, "blacksmith", "a mithral longsword")
    assert out.status == "refused" and out.code == "beyond_base" and asked == []
    assert out.tell.startswith("Kesst Vayr makes nothing.") and "forge bench" in out.tell
    assert pc.inventory.get("iron") == 2


def test_finer_work_read_from_the_words_is_refused_to_the_bench(world):
    """The reader's closed `work` answer: masterwork, a finish, an enchantment."""
    e, pc = _engine(world, carry=(("iron", 2), ("charcoal", 2), ("ash-haft", 1)))
    out, asked = _make(e, "blacksmith", "a masterwork dagger", work="finer")
    assert out.code == "beyond_base" and asked == [] and "forge bench" in out.tell


def test_a_spoiled_forge_ruins_half_by_the_books_rule_and_makes_no_dagger(world):
    """Missed by 9 at Forge (d20 1 +2 against DC 12): half of what was on the anvil is
    ruined (CRB Craft, `blacksmith.failure_losses`), the failed step still teaches, the
    chain stops there, and the verdict is the work's — no dagger."""
    e, pc = _engine(world, carry=(("iron", 1), ("charcoal", 1), ("ash-haft", 1)))
    out, asked = _make(e, "blacksmith", "a dagger", faces=(1,))
    assert asked == ["Blacksmithing: Forge"]
    assert out.verdict == "failure"
    assert not _named(pc, "Iron Dagger")
    assert "spoiled" in out.tell and "Missed by 9" in out.tell
    assert sum(pc.inventory.get(k, 0) for k in ("iron", "charcoal")) == 1
    assert pc.track("blacksmith").mp == 1


def test_the_chain_goes_on_from_where_the_work_stands(world):
    """A blank already forged is assembled, not forged again: one die, one step."""
    e, pc = _engine(world, carry=(("iron", 1), ("charcoal", 1), ("ash-haft", 2)))
    _make(e, "blacksmith", "a dagger", faces=(15, 1))       # the blank, then a spoiled fit
    assert [st.name for st in pc.stock.values()] == ["Iron Blank (Dagger)"]
    out, asked = _make(e, "blacksmith", "a dagger")
    assert asked == ["Blacksmithing: Assemble"] and out.verdict == "success"
    assert len(_named(pc, "Iron Dagger")) == 1


def test_a_fight_refuses_the_work(world):
    e, pc = _engine(world, carry=(("iron", 2), ("charcoal", 2), ("ash-haft", 1)))
    e.scene.initiative = [("pc", 12)]
    e.scene.turn = 0
    out, asked = _make(e, "blacksmith", "a dagger")
    assert out.code == "in_a_fight" and asked == []


# --- the other crafts ------------------------------------------------------------------------

def test_typed_herbalism_brews_the_herb_and_grinds_a_poultice(world):
    """"Brew a tea from the angelica": Brew, the herb bench's Herbalist 1 method, makes its
    infusion (a leaf); "a poultice" is Grind then Mix. Both by the bench's own settle."""
    e, pc = _engine(world, kit=None, carry=(("angelica", 2), ("althaea", 2)))
    out, asked = _make(e, "herbalist", "a tea", "brew a tea from the angelica")
    assert asked == ["Herbalism: Angelica Infusion"] and out.verdict == "success"
    assert _named(pc, "Angelica Infusion") and pc.inventory.get("angelica") == 1
    out, asked = _make(e, "herbalist", "a poultice", "grind the althaea into a poultice")
    assert len(asked) == 2 and _named(pc, "Althaea Poultice")
    assert pc.track("herbalist").mp > 0


def test_typed_herbalism_refuses_a_tincture_and_asks_which_herb(world):
    e, pc = _engine(world, kit=None, carry=(("angelica", 2), ("althaea", 2)))
    out, _ = _make(e, "herbalist", "a tincture", "steep a tincture of althaea")
    assert out.code == "beyond_base" and "herb bench" in out.tell
    out, _ = _make(e, "herbalist", "a tea", "brew a tea")
    assert out.code == "which_herb" and "Althaea" in out.tell and "Angelica" in out.tell


def test_typed_alchemy_bottles_a_book_formula(world):
    """"A flask of acid": the classic every alchemist starts with, by Calcine (green
    vitriol to a calx) then Bottle (into a clay flask, the splash family's vessel)."""
    e, pc = _engine(world, kit="alchemist's field kit",
                    carry=(("green-vitriol", 2), ("clay-flask", 1), ("distilled-water", 1)))
    out, asked = _make(e, "alchemist", "a flask of acid", faces=(18, 18))
    assert asked == ["Alchemy: Calcine", "Alchemy: Bottle"], out.tell
    assert out.verdict == "success" and _named(pc, "Acid")
    assert "clay-flask" not in pc.inventory


def test_typed_alchemy_refuses_what_no_known_formula_is_called(world):
    e, pc = _engine(world, kit="alchemist's field kit", carry=(("green-vitriol", 2),))
    out, _ = _make(e, "alchemist", "a basic healing draught")
    assert out.code == "no_item" and "Alchemist's fire" in out.tell


def test_typed_leatherwork_tans_a_hide_and_makes_boots(world):
    """"Tan this hide into leather": Flense then Tan; an oak-bark tan soaks In progress
    and the chain stops there. "A pair of boots" from tanned leather: Cut, Stitch,
    Assemble."""
    e, pc = _engine(world, kit="leatherworker's field kit",
                    carry=(("oak-bark", 1),), hides=(("deer-hide", "green"),))
    out, asked = _make(e, "leatherworker", "leather", "tan this hide into leather")
    assert asked == ["Leatherworking: Flense", "Leatherworking: Tan"], out.tell
    assert out.verdict == "success" and "In progress" in out.tell
    e, pc = _engine(world, kit="leatherworker's field kit", carry=(("linen-thread", 1),),
                    hides=(("cowhide", "leather"),))
    out, asked = _make(e, "leatherworker", "a pair of boots")
    assert asked == ["Leatherworking: Cut", "Leatherworking: Stitch",
                     "Leatherworking: Assemble"], out.tell
    assert _named(pc, "Cowhide Boots")


def test_typed_enchanting_is_sent_to_the_circle(world):
    """No plain enchantment exists: every one is a property chosen at the circle on a
    vessel the craft requires to be masterwork. Refused, never half-made."""
    e, pc = _engine(world, kit=None)
    out, asked = _make(e, "enchanter", "my sword")
    assert out.code == "at_the_bench" and asked == []
    assert "enchanting circle" in out.tell


def test_every_craft_has_a_typed_door_and_a_bench_pointer():
    assert set(typed_craft.CRAFTS) == set(interpret.CRAFTS)
    for craft in typed_craft.CRAFTS:
        assert typed_craft.get(craft) is not None, craft
        assert typed_craft.BENCHES[craft]["key"], craft


# --- the reader and the act->op table ---------------------------------------------------------

def test_a_craft_act_is_built_whole_into_make(world):
    """The reader's `craft` act owes `make`, built here and never asked of the plan."""
    e, pc = _engine(world)
    frame = {"question": False, "claims": [], "actions": [
        {"act": "craft", "craft": "blacksmith", "work": "plain", "object": "a dagger",
         "place": "the anvil", "span": "forge a dagger at the anvil"}]}
    rows = acts_to_ops.table(frame, e.scene)
    assert rows[0].intents == [{"op": "make", "actor": "pc", "params": {
        "craft": "blacksmith", "work": "plain", "item": "a dagger",
        "words": "forge a dagger at the anvil"},
        "because": "the player works at their craft"}]
    # A craft only meant ("I want to forge a sword tomorrow") owes nothing this turn.
    frame["actions"][0]["commit"] = "intended"
    assert acts_to_ops.table(frame, e.scene)[0].intents == []


def test_the_plans_own_craft_paid_mastery_for_nothing_and_is_dropped(world):
    """Before: the plan could write `craft track=blacksmith recipe=dagger tier=common` and
    the engine paid mastery with no item, no roll and nothing spent. `craft` and `make`
    are code's only: out of the plan's op enum, and dropped from a plan that writes one."""
    from gm import prompts
    from rules.intents import CODE_ONLY_OPS

    assert {"craft", "make"} <= CODE_ONLY_OPS
    e, pc = _engine(world)
    frame = {"question": False, "claims": [], "actions": [
        {"act": "craft", "craft": "blacksmith", "work": "plain", "object": "a dagger"}]}
    rows = acts_to_ops.table(frame, e.scene)
    plan = [{"op": "craft", "actor": "pc", "params": {"track": "blacksmith",
                                                      "recipe": "dagger"}},
            {"op": "check", "actor": "pc", "params": {"skill": "craft (weapons)"}}]
    notes: list = []
    got = acts_to_ops.apply(plan, rows, frame, e.scene, notes=notes)
    assert [r["op"] for r in got] == ["make"], notes
    enum = prompts.turn_schema()["properties"]["intents"]["items"]["properties"]["op"]["enum"]
    assert enum and "craft" not in enum and "make" not in enum


def test_the_reader_offers_craft_with_two_closed_choices():
    alt = next(a for a in interpret.per_act_schema()["properties"]["actions"]["items"]["anyOf"]
               if a["properties"]["act"]["const"] == "craft")
    assert alt["properties"]["craft"]["enum"] == list(interpret.CRAFTS)
    assert alt["properties"]["work"]["enum"] == list(interpret.WORKS)
    # A craft outside the enum (a hosted model that ignores the schema) is `other`.
    frame, dropped = interpret.ground({"question": False, "claims": [], "actions": [
        {"act": "craft", "craft": "cooking", "object": "a stew"}]}, "I cook a stew.")
    assert frame["actions"][0]["act"] == "other" and dropped


# --- the read-back ----------------------------------------------------------------------------

PC = bv.Person("pc", "Kesst Vayr", pc=True)
SPOILED = {"intent_id": "i1", "op": "make", "status": "resolved", "actor": "pc",
           "verdict": "failure",
           "rolls": [{"label": "Blacksmithing: Forge", "visibility": "player"}],
           "effects": [{"ref": "pc", "kind": "bench", "craft": "blacksmith",
                        "bench": "forge", "target": "Dagger"}],
           "tell": "Kesst Vayr forges iron into the blank of a dagger, and the work is "
                   "spoiled."}


def test_a_beat_that_forges_the_dagger_the_engine_spoiled_is_a_contradiction():
    """The narrator never makes an item: the make's verdict is an attempt the read-back
    asks about, "making Dagger by hand", and a page that shows it made is wrong."""
    facts = bv.Facts(start="the forge", end="the forge", places=("the forge",),
                     people=(PC,), clock=600, outcomes=(SPOILED,))
    att = bv.attempts_of(facts)
    assert [(a.code, a.verdict) for a in att] == [("a1", "failure")]
    assert bv._attempt_line(att[0], facts) == (
        "a1: you (the player) — Blacksmithing: Forge: making Dagger by hand")
    said = "You draw the finished dagger from the quench, bright and true."
    claim = bv.Claim("attempt", {"attempt": "a1", "shown": "succeeds"}, quote=said,
                     sentence=said, valid=True)
    assert [d.category for d in bv.diff([claim], facts, said)] == ["attempt"]


REFUSED = {"intent_id": "i2", "op": "make", "status": "refused", "actor": "pc",
           "code": "beyond_base", "rolls": [],
           "effects": [{"ref": "pc", "kind": "bench", "craft": "blacksmith",
                        "bench": "forge", "target": "a mithral longsword"}],
           "tell": "Kesst Vayr makes nothing. Mithral is rare metal: a longsword of it is "
                   "finer work than a plain one. Finer work is done at the forge bench."}


def test_a_refused_craft_shown_made_is_a_contradiction():
    """Measured live 2026-10-28: "I forge a mithral longsword" was refused, and the planned
    beat read "quenching and tempering the rare metal to create a masterwork blade. The
    mithral longsword emerges with a flawless finish". The tell had listed the finer work
    the bench does (now it names none: `typed_craft.pointer`), and the read-back asked
    nothing, because a refused outcome had no attempt. A refused make is one now."""
    facts = bv.Facts(start="the forge", end="the forge", places=("the forge",),
                     people=(PC,), clock=600, outcomes=(REFUSED,))
    att = bv.attempts_of(facts)
    assert [(a.code, a.verdict) for a in att] == [("a1", "failure")]
    said = "The mithral longsword emerges with a flawless finish."
    claim = bv.Claim("attempt", {"attempt": "a1", "shown": "succeeds"}, quote=said,
                     sentence=said, valid=True)
    assert [d.category for d in bv.diff([claim], facts, said)] == ["attempt"]
    assert "quench" not in typed_craft.pointer("blacksmith")


# --- the pointer -----------------------------------------------------------------------------

def test_the_bench_is_offered_under_the_beat_once_never_opened(world):
    """The owner: "we should try to direct people to the forge menu". One line per bench
    after the beat, its key the page's door (02-state.js `BENCH_DOORS`)."""
    from pathlib import Path
    from types import SimpleNamespace

    from play import views

    e, pc = _engine(world, carry=(("iron", 2), ("charcoal", 2), ("ash-haft", 1)))
    out, _ = _make(e, "blacksmith", "a dagger")
    c = SimpleNamespace(transcript=[])
    views._point_to_the_bench(c, [out, out])
    # Never kind "bench": a beat's kind is its class on the page, and `.bench` is the herb
    # bench's fixed full-screen layer — live, a "bench" line covered the people buttons
    # (tools/table_hit_test.js, 2026-10-28).
    assert c.transcript == [{"who": "gm", "kind": "benchline", "bench": "forge",
                             "text": typed_craft.bench_line("blacksmith")}]
    assert "masterwork" in c.transcript[0]["text"]
    js = Path("play/static/js/table/02-state.js").read_text(encoding="utf-8")
    for row in typed_craft.BENCHES.values():
        assert f"  {row['key']}: [\"data-" in js, row["key"]


MADE = {"intent_id": "i1", "op": "make", "status": "resolved", "actor": "pc",
        "verdict": "success",
        "rolls": [{"label": "Blacksmithing: Assemble", "visibility": "player"}],
        "effects": [{"ref": "pc", "kind": "made", "craft": "blacksmith",
                     "item": "Iron Dagger", "to": "pc"},
                    {"ref": "pc", "kind": "bench", "craft": "blacksmith", "bench": "forge",
                     "target": "Dagger"}]}


def test_a_thing_made_on_the_page_that_no_make_made_is_a_contradiction():
    """Measured live 2026-10-28, after the refusal fix: the refused mithral longsword's
    beat ended "Your efforts produce nothing but a duller blade of common steel", and the
    attempt question passed it (the mithral DID fail). Nothing asked what the page said
    was made. Now, on a typed craft's beat only, a call of its own lists the made things
    against the engine's codes, and anything else made is a contradiction."""
    from gm.checks import beat_verified

    refused = bv.Facts(start="the forge", end="the forge", places=("the forge",),
                       people=(PC,), clock=600, outcomes=(REFUSED,))
    assert bv.crafted(refused) and bv.made_things(refused) == []
    steel = "Your efforts produce nothing but a duller blade of common steel."
    claims = bv.claims_of({"made": [{"item": bv.OTHER_THING, "quote": steel}]}, refused)
    for c in claims:
        c.sentence, c.valid = steel, True
    found = bv.diff(claims, refused, steel)
    assert [d.category for d in found] == ["made"]
    assert "made nothing" in found[0].fact
    assert "made or produced something" in bv.question(found[0], refused)
    # What the engine made is no contradiction; anything beside it is.
    made = bv.Facts(start="the forge", end="the forge", places=("the forge",),
                    people=(PC,), clock=600, outcomes=(MADE,))
    ok = bv.Claim("made", {"item": "Iron Dagger"}, quote="x", sentence="x", valid=True)
    assert bv.diff([ok], made, "x") == []
    assert bv.made_schema(made)["properties"]["made"]["items"]["properties"]["item"][
        "enum"] == ["Iron Dagger", bv.OTHER_THING]
    assert beat_verified._KIND["made"] == ("beat-makes-item", 3)
    assert "beat-makes-item" in beat_verified.KINDS
    # Asked on no other beat.
    assert not bv.crafted(bv.Facts(start="x", end="x", places=(), people=(PC,),
                                   clock=600, outcomes=()))

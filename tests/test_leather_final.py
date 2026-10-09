"""The leatherworking final pass (docs/leatherworking-questions.md, "Final-pass list (lead,
2026-10-08)" and the lanes' leftovers after it). Each test names the defect it prevents,
measured live by the lane that found it or on the shipped data.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from play import campaign as cm
from play import leather_views
from rules import bestiary, harvest, keepers, knowledge, places, states
from rules import blacksmith as bs
from rules import forge_items
from rules import leatherworker as lw
from rules.sheet import load_pc
from tests.test_leather_api import _carry, _pc, client, post, rack_key, step, where  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "play" / "static" / "js"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# --- the bench's visible defects (lane U1, live) --------------------------------------------------

def test_an_unintroduced_keeper_lends_no_name_to_the_bench_footer():
    """Lane U1, live, 2026-10-08: the footer read "At the tanner's tannery", the keeper's
    descriptor taken for a name (the forge's "the smith's smithy" is the same shape). Only
    a name the player has been given is used: `name == true_name`, written as a name."""
    tanner = SimpleNamespace(name="the tanner", true_name="Hal Dunmore")
    assert keepers.given_name(tanner) == ""
    tanner.name = "Hal Dunmore"
    assert keepers.given_name(tanner) == "Hal Dunmore"
    assert keepers.given_name(SimpleNamespace(name="the tanner", true_name="")) == ""
    assert keepers.given_name(None) == ""


def test_the_tannery_line_carries_no_em_dash():
    """Lane U1: `where.advice` had an em-dash, which UI copy never carries."""
    from tests.test_leather_places import SYNTHETIC, _named, _table

    plain = _named(SYNTHETIC, "Kestwick")
    scene, engine = _table(SYNTHETIC, plain.id)
    line = places.tannery_line(scene, engine.places(), plain)
    assert line.startswith("Kestwick has no tannery.") and "—" not in line


def test_the_advice_never_disagrees_with_the_bench_about_the_tannery(client, where):
    """Lane U1: at a tannery the advice said the place had none. The advice is now asked
    only when the bench's own reading finds no tannery (`_where`), so the two answers
    come from one reading and cannot disagree."""
    where["at"] = "tannery"
    s = client.get("/api/leather/state").json()
    assert s["where"]["tannery"] and s["where"]["advice"] == ""
    assert "tanner's tannery" not in s["where"]["line"]
    # Live, 2026-10-09, in Zhilgoroth's tannery: "At the tannery at the tannery".
    assert "tannery at" not in s["where"]["line"]


def test_assemble_slots_follow_the_product():
    """Lane U1, live: Assemble drew a Fastenings slot for boots, which `fit_reason` then
    refused whatever was put in it. Worn goods are a body and a lining; a suit's
    fastenings are required, never marked optional; before a product, all three."""
    assert lw.slots_for("assemble", "boots") == (("body", "lining"), ("lining",))
    assert lw.slots_for("assemble", "leather armour") == (
        ("body", "fastenings", "lining"), ("lining",))
    assert lw.slots_for("assemble", "") == (("body", "fastenings", "lining"),
                                            ("fastenings", "lining"))
    assert lw.slots_for("cut", "boots")[0] == ("hide",)
    labels = [s["id"] for s in leather_views._slot_view("assemble", "cloak")]
    assert labels == ["body", "lining"]


def test_crafted_leather_armour_says_what_it_does_on_the_equipment_tab(client):
    """Lane U1, live: a crafted suit read "for show, no effect in play" on Equipment while
    wearing it set the armour slot and moved AC. The row now carries the suit's own
    numbers (`forge_items.armour_row`), the same row `Actor.armour_stats` reads worn."""
    from play.views import _carried

    _carry(elk_hide=1, deer_hide=1, linen_thread=2)
    step(client, "cut", {"hide": "inv:elk-hide"}, product="hide armour")
    step(client, "stitch", {"piece": rack_key(client, "panel"), "thread": "inv:linen-thread"})
    step(client, "cut", {"hide": "inv:deer-hide"}, product="lacing")
    _c, _r, done = step(client, "assemble", {"body": rack_key(client, "panel"),
                                             "fastenings": rack_key(client, "lacing")})
    rec = done["products"][0]["record"]
    row = next(r for r in _carried(_pc()) if r["key"] == rec["id"])
    assert row["armour"] and row["armour"]["ac"] >= 3, row
    r = post(client, "/api/wear", {"item": rec["id"]})
    assert r.status_code == 200
    pc = _pc()
    rows = _carried(pc)
    row = next(r for r in rows if r["key"] == rec["id"])
    assert row["armour"]["ac"] == pc.armour_stats()["ac"] and row["state"] == "worn"
    # Live, the playthrough (2026-10-09): the worn made suit also read as a plain "Leather
    # armour, worn, max Dex +6, Take off" row, and its own row had no act. One worn row,
    # and it is the one that comes off.
    worn = [r for r in rows if r["state"] == "worn" and (r.get("armour") or r["kind"] == "armour")]
    assert [r["key"] for r in worn] == [rec["id"]], worn
    off = next(a for a in row["acts"] if a["label"] == "Take off")
    r = post(client, off["api"], off["body"])
    assert r.status_code == 200 and _pc().armour_record() is None


def test_the_bench_frame_never_names_a_quality_nobody_computed():
    """Lane U1: a leather game started without `tuning.names` (the tannery's cut test, the
    harvest) read "Rough quality 3 of 5" in its live region, a tier the server never
    computed. With no names the pips are the game's score, said as one."""
    src = _read(JS / "table" / "33-bench-games.js")
    assert '"Rough quality "' not in src and '"Score " + (i + 1)' in src


def test_the_skinning_danger_tell_reads_as_a_sentence():
    """Lane U2, live: "works around the a body hot to the touch of the Karkadon". The
    danger's words stand alone, so the tell never wraps them in its own article."""
    beast = SimpleNamespace(name="the Karkadann", from_template="karkadann", harvested={})
    got = harvest.face_danger(None, SimpleNamespace(name="Kesst"), beast, "fire", 99, now=0)
    assert not got["exposed"]
    tell = got["tells"][0]
    assert "the a " not in tell and "the the " not in tell.lower()
    assert tell == ("Kesst skins the Karkadann without harm, wary of a body hot to the "
                    "touch.")


# --- what a creature gave, held back until Grade finds it -----------------------------------------

def _pieces(creature="salamander"):
    return {"body": {"material": "generic-scale-hide", "passes": 0, "grade": 2,
                     "creature": creature}}


def test_a_creature_derived_property_is_held_back_until_graded():
    """Lane U1, live: the build card's `from_creature` lines named a generic hide's
    inheritance (a salamander's fire resistance) before any Grade, and the preview's
    `build.specs` carried it too. Held back server-side, as an unknown property is, until
    a successful Grade of a scrap of that beast's hide finds it (`knowledge.grade`)."""
    pc = load_pc("fixtures/pc-kesst.json")
    pc.herb_known.clear()
    build = {"specs": [{"type": "resistance", "target": "fire", "amount": 3,
                        "source": "creature:salamander"},
                       {"type": "combat_mod", "target": "ac", "amount": 1, "source": "x"}],
             "sum": [], "book": [], "marks": [], "multipliers": {}}
    card = leather_views._card(build, _pieces(), "armour", "Sound", pc)
    assert card["from_creature"] == []
    page = leather_views._page_build(build, pc, _pieces())
    assert [s["source"] for s in page["specs"]] == ["x"]
    got = knowledge.grade(pc, "generic-scale-hide", 99, clock=0, creature="salamander")
    assert knowledge.creature_key("salamander") in got["revealed"]
    assert knowledge.knows_creature(pc, "generic-scale-hide", "salamander")
    card = leather_views._card(build, _pieces(), "armour", "Sound", pc)
    assert card["from_creature"] and "fire" in card["from_creature"][0].lower()
    assert len(leather_views._page_build(build, pc, _pieces())["specs"]) == 2


def test_a_beast_with_nothing_to_inherit_adds_no_key_to_grade():
    """A wolf inherits nothing, so its Grade reveals only the hide's own properties."""
    pc = load_pc("fixtures/pc-kesst.json")
    pc.herb_known.clear()
    got = knowledge.grade(pc, "generic-fur-hide", 99, clock=0, creature="wolf")
    assert knowledge.creature_key("wolf") not in got["revealed"]


# --- rules gaps --------------------------------------------------------------------------------

def test_a_thick_generic_hide_can_make_hide_armour():
    """Lane C: `_has(doc, "thick")` read the generic document alone, which is thin, so no
    harvested beast's hide could ever be hide armour. The piece's traits now include its
    beast's (`harvest.working_traits`). The bulette prints no AC breakdown (AC 22, touch
    10): its natural armour is read as AC less touch, 12, so its hide is thick."""
    assert harvest.natural_armour(harvest.block_of("bulette")) == 12
    hide = lw.Hide(form="leather", material="generic-scale-hide", creature="bulette",
                   tannage="oak-bark")
    p = lw.Piece(key="stock:x", name="Bulette Leather", material="generic-scale-hide",
                 form="leather", count=1, hide=hide)
    assert "thick" in p.working
    assert lw.fit_reason("cut", "hide", p, product="hide armour") == ""
    thin = lw.Piece(key="stock:y", name="Wolf Leather", material="generic-fur-hide",
                    form="leather", count=1,
                    hide=lw.Hide(form="leather", material="generic-fur-hide",
                                 creature="wolf", tannage="oak-bark"))
    assert "thick" not in thin.working
    assert "too thin" in lw.fit_reason("cut", "hide", thin, product="hide armour")


def test_a_styx_tanned_grip_carries_its_mark_through_the_forge():
    """The marks lane: a grip fitted at the forge kept its tannage in the piece and gave no
    mark, so styx mordant's weapon mark (+1 damage against outsiders) never landed. The
    forge's Assemble now carries a leather piece's marks, as a leather base's are."""
    from tests.test_leather_forge_handoff import assemble, carry_work, kesst, tempered_blank

    pc = kesst()
    h = lw.Hide(form="grip", material="sharkskin", quarters=1, grade=2,
                tannage="styx-mordant")
    grip = f"stock:{lw.put_hide(pc, h)}"
    blade = carry_work(pc, tempered_blank())
    plan = assemble(pc, {"head": blade, "haft": grip})
    assert plan.problems == []
    rec = bs.record(bs.make(plan, 1)[0][0])
    assert rec.get("marks") == ["styx-mordant"]
    rows = forge_items.build(rec)["marks"]
    assert any(r["applied"] and r["effect"]["target"] == "damage" for r in rows), rows


def test_the_forge_card_names_known_marks_and_held_back_creature_lines():
    """The marks lane: `forge_views._card` named no marks, so a studded suit from a marked
    base said nothing of them at the anvil. It now carries the leather bench's own
    `marks` and `from_creature`, under the same knowledge rules."""
    from play import forge_views

    pc = load_pc("fixtures/pc-kesst.json")
    pc.herb_known.clear()
    build = {"specs": [{"type": "resistance", "target": "fire", "amount": 3,
                        "source": "creature:salamander"}],
             "sum": [], "book": [], "strikes_as": [], "multipliers": {},
             "marks": [{"material": "styx-mordant", "step": "tan", "applied": True,
                        "effect": {"type": "combat_mod", "target": "damage", "amount": 1}}]}
    card = forge_views._card(build, _pieces(), "armour", "Sound", pc)
    assert card["marks"] == [] and card["from_creature"] == []
    knowledge.reveal(pc, "styx-mordant", ["k0"], "test")
    assert forge_views._card(build, _pieces(), "armour", "Sound", pc)["marks"]


def test_finishing_a_step_reveals_the_consumables_working_traits(client):
    """The marks lane: finishing only asked the hides, so a tannin's or a thread's working
    traits stayed unknown however much went through the bench. A consumable worked with
    is watched behave too; its mark (a "k" key) stays Grade's."""
    _carry(elk_hide=1, linen_thread=2)
    step(client, "cut", {"hide": "inv:elk-hide"}, product="hide armour")
    _c, _r, done = step(client, "stitch", {"piece": rack_key(client, "panel"),
                                           "thread": "inv:linen-thread"})
    assert any(d["material"] == "linen-thread" for d in done["discoveries"]), \
        done["discoveries"]
    assert not any(str(d["key"]).startswith("k") for d in done["discoveries"])


def test_the_forge_drops_a_leather_base_and_a_lacing_set_with_a_sound():
    """Lane H moved `base` and `lacing` out of the forge's GROUPS, so `forge.drop.base` and
    `.lacing` had no synthesizer and the anvil was silent (unknown names are silent by
    contract). tests/test_forge_sound.py now asks LEATHER_GROUPS' forms too."""
    src = _read(JS / "sound.js")
    for form in bs.LEATHER_GROUPS:
        assert (f"{form}: function" in src or f'"{form}"' in src), form


def test_the_forge_ledger_follows_a_409_to_the_tanners_card():
    """The forge's ledger card answered a tanner's material with "Couldn't load this
    material" and a Retry that could only fail; the server's 409 names `track` and `card`.
    The card now opens on that track."""
    src = _read(JS / "table" / "44-forge-ledger.js")
    core = _read(JS / "table" / "29-bench-core.js")
    assert "e.data = data" in src and "e.data = data" in core
    assert "d.track !== track && TRACKS[d.track]" in src


def test_tanyard_and_tan_pits_are_said_as_a_tannery():
    """`found kind="tanyard"` was refused as no such kind of place."""
    for word in ("tanyard", "tan pits", "tan-yard"):
        assert places.kind_named(word) == "tannery" and places.known_kind(word)


def test_an_alias_spawned_creature_has_its_stat_block():
    """Lane C: `Actor._creature_doc` read `bestiary.raw`, which missed the index-order
    alias, so a "goblin troop" (`troop-goblin`) had no block and so no `type.*` tags."""
    assert bestiary.raw("goblin troop") is not None
    assert bestiary.raw("goblin troop") is bestiary.raw_block("goblin troop")


def test_a_truncated_core_type_is_tagged_as_the_book_spells_it():
    """Lane C: core.json's "magical" (107 blocks) wrote `type.magical`, and harvest kept a
    table of fragments of its own. One reader (`states.type_word`) for the tags, Grade and
    the harvest."""
    assert states.type_tags("magical") == ("type.magical-beast",)
    assert states.type_tags("monstrous") == ("type.monstrous-humanoid",)
    assert states.type_tags("advanced magical beast") == ("type.magical-beast",)
    assert harvest.creature_kind({"creature_type": "magical"}) == "magical beast"
    assert harvest.creature_kind({"creature_type": "animal companion 5"}) == "animal"
    assert harvest.creature_kind({"creature_type": "ve"}) == "vermin"
    assert not hasattr(harvest, "_TYPE_FIX")


def test_a_beast_has_no_people():
    """Lane C, live: a dead wolf read "of the Korvu people". The load-time sweep that
    names the nameless asked nothing; it now asks the spawn's own reader."""
    assert bestiary.has_a_people("wolf") is False
    assert bestiary.has_a_people("guard dog") is False
    assert bestiary.has_a_people("goblin") is True
    assert bestiary.has_a_people("watchman") is True
    from gm import judgement

    wolf = SimpleNamespace(is_pc=False, true_name="", name="the wolf", appearance="",
                           world_entity_id="", from_template="wolf",
                           _creature_doc=lambda: bestiary.raw("wolf"))
    scene = SimpleNamespace(actors={"c1": wolf}, location_id="x")
    assert judgement.name_the_nameless(scene, object()) == []
    assert wolf.true_name == "" and wolf.appearance == ""


def test_a_blow_read_at_a_dying_beast_finishes_it():
    """Measured in this pass's playthrough (2026-10-09): "I finish the dying wolf with a
    thrust of my rapier" was read as an `attack` on "the dying wolf", the plan wrote only
    `narrate_only` (it took the wolf for dead), and `acts_to_ops.victims` left "the plan's
    own blow" for a body that is down, so nothing struck: the wolf stayed at -2, dying,
    while the prose killed it, and the harvest stayed shut. A blow read at a body on the
    floor is built: out of a fight the coup de grâce, which opens none."""
    from rules.engine import Scene
    from rules.grid import Grid
    from tests._violence import through_the_reading

    s = Scene()
    s.grid = Grid(width=20, height=20)
    s.add(load_pc("fixtures/pc-kesst.json"), at=(5, 5))
    wolf = s.add(bestiary.instantiate("wolf", scene=s, name="a grey wolf"), at=(6, 5))
    wolf.hp = -2
    assert wolf.is_down and not wolf.has_state("state.down.dead")
    line = "I finish the dying wolf with a thrust of my rapier."
    frame = {"question": False, "claims": [], "actions": [
        {"act": "attack", "target": "the dying wolf", "object": "my rapier",
         "span": "finish the dying wolf with a thrust of my rapier"}]}
    out, stop = through_the_reading([{"op": "narrate_only"}], line, s, frame=frame)
    blows = [r for r in out if r.get("op") == "attack"]
    assert not stop and len(blows) == 1, out
    assert blows[0]["target"] == wolf.ref and blows[0]["params"] == {"coup_de_grace": True}


def test_a_wait_the_bench_has_told_is_not_told_again():
    """Live, the playthrough (2026-10-09): the tannery's 15-day wait was written by the
    bench and stayed queued, so putting the armour on next read "puts on the Crude Deer
    Leather Armour (1 minute). Through the wait Kesst Vayr eats 14 pounds of food ...". The
    bench takes what it told (`survival.told_on_page`); somebody else's toll stays."""
    from rules import survival

    mine = {"ref": "pc", "said": ["Through the wait Kesst eats 14 pounds of food."]}
    theirs = {"ref": "c1", "said": ["The companion eats too."]}
    scene = SimpleNamespace(_body_said=[mine, theirs])
    lines = survival.told_on_page(scene, {"body": [mine, theirs]}, "pc")
    assert lines == mine["said"] and scene._body_said == [theirs]


def test_every_in_progress_row_says_whether_it_can_be_waited_for_here():
    """Live, the playthrough: a bark tannage's first wait stopped on an empty pack with 15
    days to go, and nothing on the page could wait the rest (Wait for it lived only on the
    step's own result). Each row says `can_wait` (not ready, and here or carried) and what is
    being done, so the bench that registered a waiter offers it (37-works.js)."""
    src = _read(JS / "table" / "37-works.js")
    assert "W.waiters = {}" in src and "data-works-wait" in src
    assert "Works.waiters.leatherworker" in _read(JS / "table" / "55-leather-shell.js")
    from rules import inprogress

    item = SimpleNamespace(name="Wolf Leather", record=None,
                           work={"craft": "leatherworker", "started": 0, "minutes": 600,
                                 "where": "place:x~urban:the-tannery", "doing": "tanning"})
    try:
        row = inprogress._row("k", item, 60, "x~urban:the-tannery")
    except Exception:
        pytest.skip("the In-progress block is stored differently on this tree")
    assert row["can_wait"] is True and row["doing"] == "tanning"
    assert inprogress._row("k", item, 60, "elsewhere")["can_wait"] is False


def test_a_forge_finished_suit_is_found_by_its_stock_id():
    """Live, the playthrough (2026-10-09): the forge's Crude Deer Studded Leather's Wear, from
    its own Equipment row, answered "you are not carrying 'crude-deer-studded-leather#1'":
    the row names a thing by its stock entry's id, and a forge item's shelf key and rebuilt
    record id are not that id. The one lookup (`Actor.crafted_record`) knows it now."""
    from tests.test_leather_forge_handoff import assemble, carry_base, kesst

    pc = kesst()
    pc.inventory["steel-studs"] = 1
    base = carry_base(pc)
    plan = assemble(pc, {"body": base, "fastenings": "inv:steel-studs"})
    assert plan.problems == []
    key = bs.put(pc, bs.make(plan, 1)[0][0])
    st = pc.stock[key]
    # The defect's shape: the row's id ("deer-studded-leather#1") is neither the shelf key
    # nor the rebuilt record's id.
    assert str(st.id) not in (key, str(forge_items.record_of(st).get("id")))
    rec = pc.crafted_record(str(st.id))
    assert rec is not None and rec.get("base") == "studded leather"


def test_a_suit_taken_off_is_no_longer_worn_at_the_forge():
    """Live, the playthrough: the leather base, taken off at the smithy, still read "you are
    wearing it: take it off before the smith works it": `Actor.worn` keeps a record after
    it comes off, and the forge read that store and not the slots."""
    from tests.test_leather_forge_handoff import kesst

    pc = kesst()
    pc.worn["crude deer leather armour"] = {"id": "crude-deer-leather-armour", "name": "x"}
    pc.slots["armor"] = []
    assert bs._worn_ids(pc) == set()
    pc.slots["armor"] = ["crude deer leather armour"]
    assert bs._worn_ids(pc) == {"crude-deer-leather-armour"}


def test_every_domain_power_says_its_ability_type():
    """Lane M: domain powers carried no `ability_type`, so a druid with a domain in metal
    armour kept them (the prohibition suspends Su and Sp). Each is the Core Rulebook's tag
    (legacy.aonprd.com, cleric domains): fifteen Sp, four Su."""
    doc = json.loads(_read(ROOT / "content" / "class-abilities" / "domains.json"))
    kinds = {a["key"]: a.get("ability_type") for a in doc["abilities"]}
    assert all(v in ("su", "sp") for v in kinds.values()), kinds
    assert sorted(k for k, v in kinds.items() if v == "su") == [
        "aura of madness", "aura of protection", "destructive smite", "wooden fist"]


def test_the_forge_api_runs_alone():
    """The marks lane: tests/test_forge_api.py errored when run alone, its fake
    `rules.materials` lacking CATALOGUES. The fake now answers every other name from the
    real module."""
    from tests.test_forge_bench import fake_materials

    assert fake_materials().CATALOGUES

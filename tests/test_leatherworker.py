"""The leatherworker track, its materials, and the tannery's chain rules.

Every test names the decision it pins, because the decisions are the deliverable: the
generic framework in `rules/worldclass.py` was built so a second track would be three
files and no new code paths, and this suite is the measurement that it was.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rules import bestiary, effectspec, herbprep
from rules import leatherworker as lw
from rules import worldclass as wc

TRACK_FILE_DIR = Path("content/world-classes")
MATERIALS_FILE = Path("content/materials/leatherworker-materials.json")


@pytest.fixture(autouse=True)
def _fresh_material_cache():
    """The module caches materials for the app's lifetime; a test that redirects the
    homebrew directory must not inherit another test's cache, or poison the next."""
    lw._MATERIALS = None
    yield
    lw._MATERIALS = None


def _shipped() -> list[dict]:
    return json.loads(MATERIALS_FILE.read_text(encoding="utf-8"))["materials"]


# --- the track ------------------------------------------------------------------------------

def test_track_loads_through_the_generic_framework():
    """The whole point of `worldclass.py` being generic: leatherworker is a file, not a
    code path. It must load through the same `load_dir` herbalist does, unchanged."""
    tracks = wc.load_dir(TRACK_FILE_DIR)
    assert "leatherworker" in tracks
    t = tracks["leatherworker"]
    assert t.name == "Leatherworker"
    assert t.max_level == 5
    assert len(t.thresholds) == 4


def test_tier_ladder_walks_common_to_legendary_in_order():
    """Five levels, five tiers, strictly ascending. A track whose level 3 worked exotic
    material would let `preview`'s ceiling check pass chains the design gates."""
    t = wc.load_dir(TRACK_FILE_DIR)["leatherworker"]
    ranks = [wc.tier_rank(l.max_tier)
             for l in sorted(t.levels, key=lambda x: x.level)]
    assert ranks == [1, 2, 3, 4, 5]


def test_methods_gate_across_levels():
    """The station ladder: rawhide work at 1, tanning at 2, hardening (cuir bouilli) at
    4, masterwork tooling at 5. `unlocked_methods` accumulates — nothing expires."""
    t = wc.load_dir(TRACK_FILE_DIR)["leatherworker"]
    assert "stitch" in t.unlocked_methods(1)
    assert "tan" not in t.unlocked_methods(1)
    assert "tan" in t.unlocked_methods(2)
    assert "harden" not in t.unlocked_methods(3)
    assert "harden" in t.unlocked_methods(4)
    assert "tool" not in t.unlocked_methods(4)
    assert "tool" in t.unlocked_methods(5)


def test_level_five_deed_is_the_material_not_the_method():
    """The herbalist's measured lesson, applied before it can recur: a deed that needs
    a level-5 method can never open level 5. Working legendary hide by any successful
    means satisfies the deed — `tool` is the mastery that follows, not the gate."""
    t = wc.load_dir(TRACK_FILE_DIR)["leatherworker"]
    assert t.milestones.get(5) == "legendary-hide"
    assert t.deed_done(tier="legendary", success=True) == "legendary-hide"
    assert t.deed_done(tier="exotic", success=True) == ""
    assert t.deed_done(tier="legendary", success=False) == ""


# --- the materials --------------------------------------------------------------------------

def test_material_ids_are_unique():
    ids = [m["id"] for m in _shipped()]
    dupes = {i for i in ids if ids.count(i) > 1}
    assert not dupes, f"duplicate material ids: {sorted(dupes)}"


def test_all_five_tiers_are_populated_and_the_file_is_big_enough():
    """The brief's target was 110+ entries across every tier — a tier with two entries
    is a rules gate with nothing behind it. Counted, not assumed."""
    entries = _shipped()
    assert len(entries) >= 110, f"only {len(entries)} materials"
    by_tier = {}
    for m in entries:
        by_tier[m["tier"]] = by_tier.get(m["tier"], 0) + 1
    print("per tier:", by_tier)
    for tier in wc.TIERS:
        assert by_tier.get(tier, 0) >= 8, f"{tier} is thin: {by_tier.get(tier, 0)}"


def test_every_authored_effect_validates():
    """Zero invalid specs. An effect that looks authored and fails `validate` is the
    silent do-nothing failure docs/homebrew-rules.md exists to prevent — anything the
    vocabulary cannot hold was supposed to be a `narrative` spec or plain prose."""
    offenders = []
    for m in _shipped():
        for i, spec in enumerate(m.get("effects") or []):
            problems = effectspec.validate(spec, f"{m['id']} effect {i + 1}")
            offenders.extend(problems)
    for p in offenders:
        print(p)
    assert not offenders, f"{len(offenders)} invalid effect specs"


def test_same_tier_hides_are_not_reskins():
    """Materials must feel different: within one tier, no two hides may share an
    identical effect set. Ten dragonhides share statistics by the book, so their colour
    identity is carried as a spec — this is the test that keeps it there."""
    by_tier: dict[str, dict[str, str]] = {}
    for m in _shipped():
        if m["kind"] != "hide":
            continue
        key = json.dumps(m.get("effects") or [], sort_keys=True)
        clash = by_tier.setdefault(m["tier"], {}).get(key)
        assert clash is None, \
            f"{m['id']} and {clash} are {m['tier']} hides with identical effects"
        by_tier[m["tier"]][key] = m["id"]


def test_every_hide_names_a_creature_the_bestiary_has():
    """`from_creatures` is the joint between loot and bench: a fallen creature's name
    is matched against these fragments. A fragment no bestiary name contains is a hide
    no fight can ever yield."""
    names = [c.get("name", "").lower() for c in bestiary.imported().values()]
    orphans = []
    for m in _shipped():
        if m["kind"] != "hide":
            continue
        frags = [f.lower() for f in m.get("from_creatures") or []]
        assert frags, f"{m['id']} has no from_creatures"
        if not any(any(f in n for n in names) for f in frags):
            orphans.append(m["id"])
    assert not orphans, f"hides no creature yields: {orphans}"


def test_hides_from_prefers_the_longest_fragment():
    """'worg, winter wolf' must resolve to the winter wolf pelt before the plain wolf
    pelt — the longest matched fragment is the most specific claim."""
    found = lw.hides_from("worg, winter wolf")
    assert found, "no hide matched a winter wolf"
    assert found[0].id == "winter-wolf-pelt"


def test_raw_hide_window_matches_the_herbalist_animal_clock():
    """A hide is an animal part. `lw.FRESH_HOURS` restates `herbprep.ANIMAL_HOURS`
    rather than importing it so the module reads standalone; this is the pin that
    keeps the two numbers from drifting — the stale-copy trap, pre-empted."""
    assert lw.FRESH_HOURS == herbprep.ANIMAL_HOURS
    for m in _shipped():
        if m["kind"] == "hide":
            assert m.get("fresh_hours"), f"{m['id']} has no freshness window"


# --- the chain rules ------------------------------------------------------------------------

def _chain(methods, mats, product="satchel", name=""):
    return lw.Chain(methods=list(methods), material_ids=list(mats),
                    product=product, name=name)


def test_a_legal_level_one_chain_has_no_problems():
    """The refusals are only trustworthy if a chain that follows every rule sails: a
    deer-hide satchel — flense, cure, cut, stitch, with thread — at level 1."""
    r = lw.preview(1, _chain(["flense", "cure", "cut", "stitch"],
                             ["deer-hide", "linen-thread"]))
    assert r.problems == []
    assert r.name == "Deer Satchel"
    assert r.tier == "common"
    # DC from tier rank + stages, the same two terms crafting._dc uses: 10 base + 6.
    assert r.dc == 10 + 2 * 3


def test_stitching_an_uncured_hide_is_refused_because_it_rots():
    """The defining refusal: raw hide is meat, and a seam through meat is a bag of rot.
    Refused before any roll, with the fix in the sentence."""
    r = lw.preview(1, _chain(["flense", "cut", "stitch"],
                             ["deer-hide", "linen-thread"]))
    assert any("rots" in p for p in r.problems), r.problems
    # And curing first clears it — the refusal teaches a rule that can be followed.
    ok = lw.preview(1, _chain(["flense", "cure", "cut", "stitch"],
                              ["deer-hide", "linen-thread"]))
    assert not any("rots" in p for p in ok.problems)


def test_hardening_untanned_hide_is_refused():
    """Cuir bouilli is done to leather: raw hide in the kettle is glue. Not a tier gate
    in costume — a level 5 crafter with every method still gets refused."""
    r = lw.preview(5, _chain(["flense", "cure", "cut", "harden", "stitch"],
                             ["boar-hide", "hardening-wax", "linen-thread"],
                             product="armour piece"))
    assert any("never tanned" in p for p in r.problems), r.problems
    ok = lw.preview(5, _chain(["flense", "tan", "cut", "harden", "stitch"],
                              ["boar-hide", "oak-bark", "hardening-wax",
                               "linen-thread"],
                              product="armour piece"))
    assert not any("never tanned" in p for p in ok.problems)


def test_spoiled_raw_hide_is_refused_and_fresh_is_not():
    """Freshness is a clock, not a flag, and it is only read when the caller carries
    one: a 60-hour hide against a 48-hour window is refuse; the same hide at 10 hours
    is fine; a stock entry with no age is assumed fresh, as every caller without a
    clock wants."""
    methods = ["flense", "cure", "cut", "stitch"]
    mats = ["deer-hide", "linen-thread"]
    old = {"deer-hide": {"count": 1, "age_hours": 60}, "linen-thread": 1}
    r = lw.preview(1, _chain(methods, mats), stock=old)
    assert any("spoiled" in p for p in r.problems), r.problems

    fresh = {"deer-hide": {"count": 1, "age_hours": 10}, "linen-thread": 1}
    assert not any("spoiled" in p
                   for p in lw.preview(1, _chain(methods, mats), fresh).problems)
    unstated = {"deer-hide": 1, "linen-thread": 1}
    assert not any("spoiled" in p
                   for p in lw.preview(1, _chain(methods, mats), unstated).problems)


def test_the_tannin_must_be_within_one_tier_of_the_hide():
    """Oak bark cannot bite dragonhide. The ladder is why high-tier tannins exist at
    all — without the gate, one sack of bark tans the whole bestiary."""
    r = lw.preview(5, _chain(["flense", "tan", "cut", "stitch"],
                             ["red-dragonhide", "oak-bark", "dragon-sinew"],
                             product="armour piece"))
    assert any("cannot bite" in p for p in r.problems), r.problems
    ok = lw.preview(5, _chain(["flense", "tan", "cut", "stitch"],
                              ["red-dragonhide", "dragonblood-tannin",
                               "dragon-sinew"],
                              product="armour piece"))
    assert not any("cannot bite" in p for p in ok.problems)


def test_barding_refuses_a_hide_too_small_for_it():
    """The piece has to come out of the hide: a cat does not contain a warhorse."""
    r = lw.preview(1, _chain(["flense", "cure", "cut", "stitch"],
                             ["cat-pelt", "linen-thread"], product="barding"))
    assert any("bigger beast" in p for p in r.problems), r.problems
    ok = lw.preview(1, _chain(["flense", "cure", "cut", "stitch"],
                              ["horse-hide", "linen-thread"], product="barding"))
    assert not any("bigger beast" in p for p in ok.problems)


def test_methods_beyond_the_level_are_named_with_where_they_are_learned():
    """The refusal teaches the ladder: a level 1 crafter reaching for the tanning vat
    is told the level that grants it, in the same phrasing the herbalist bench uses."""
    r = lw.preview(1, _chain(["flense", "tan", "cut", "stitch"],
                             ["deer-hide", "oak-bark", "linen-thread"]))
    assert any("learned at Leatherworker 2" in p for p in r.problems), r.problems


def test_two_same_tier_hides_change_the_product():
    """The reskin test at the bench rather than in the file: the same chain over a
    winter wolf pelt and a snow leopard pelt must come out with different effect sets —
    cold resistance is not a stealth bonus wearing fur."""
    methods = ["flense", "tan", "cut", "stitch"]
    wolf = lw.preview(2, _chain(methods, ["winter-wolf-pelt", "bog-liquor",
                                          "sinew-thread"], product="cloak"))
    cat = lw.preview(2, _chain(methods, ["snow-leopard-pelt", "bog-liquor",
                                         "sinew-thread"], product="cloak"))
    strip = lambda specs: {json.dumps({k: v for k, v in s.items() if k != "from"},
                                      sort_keys=True) for s in specs}
    assert strip(wolf.specs) != strip(cat.specs)
    assert any(s.get("type") == "resistance" for s in wolf.specs)
    assert any(s.get("type") == "skill_mod" for s in cat.specs)


def test_homebrew_hide_layers_over_the_shipped_set(tmp_path, monkeypatch):
    """Modularity is the brief: a hide dropped in homebrew/materials just works, and a
    homebrew copy of a shipped id wins — the `worldclass.tracks()` overlay, verified
    on this module rather than assumed from the pattern."""
    from django.conf import settings

    home = tmp_path / "homebrew" / "materials"
    home.mkdir(parents=True)
    (home / "glass-cat-hide.json").write_text(json.dumps({
        "id": "glass-cat-hide", "name": "Glass Cat Hide", "kind": "hide",
        "tier": "rare", "size": "small", "fresh_hours": 48, "source": "skinned",
        "from_creatures": ["cat"],
        "effects": [{"type": "skill_mod", "target": "stealth", "amount": 3,
                     "bonus_type": "circumstance"}],
    }), encoding="utf-8")
    # `materials()` reads CAMPAIGN_DIR's *parent*, as tracks() does.
    monkeypatch.setattr(settings, "CAMPAIGN_DIR", str(tmp_path / "campaigns"))
    lw._MATERIALS = None

    loaded = lw.materials()
    assert "glass-cat-hide" in loaded
    assert loaded["glass-cat-hide"].tier == "rare"
    # And it is immediately craftable, not merely listed.
    r = lw.preview(3, _chain(["flense", "tan", "cut", "stitch"],
                             ["glass-cat-hide", "ironbark-tannin", "silk-thread"],
                             product="boots"))
    assert r.problems == []
    assert r.tier == "rare"
    # The shipped set is layered under, not replaced.
    assert "deer-hide" in loaded


def test_skinning_belongs_to_the_field_not_the_bench():
    """`skin` is the excursion over a carcass; every material already carries
    `source: skinned`. Allowing it in a bench chain would double-count the field
    action and quietly hand out its stage MP twice."""
    r = lw.preview(1, _chain(["skin", "flense", "cure", "cut", "stitch"],
                             ["deer-hide", "linen-thread"]))
    assert any("over a carcass" in p for p in r.problems), r.problems


def test_an_unknown_product_pattern_raises_rather_than_guessing():
    with pytest.raises(lw.CraftError):
        lw.preview(1, _chain(["cut"], ["deer-hide"], product="codpiece"))


# --- phase two: the dispatchable surface ----------------------------------------------------

class _Crafter:
    """A stand-in for a sheet Actor: the two attributes `check_terms` reads."""

    def __init__(self, level=5, int_mod=2):
        self.level = level
        self._int = int_mod

    def ability_mod(self, which):
        return self._int if which == "int" else 0


def test_chain_from_body_is_tolerant_of_a_partial_bench_post():
    """The bench previews on every click, including the first one when nothing has been
    chosen. A missing key must be an empty chain, not a 500 — `preview` already answers
    an empty chain with readable problems, and a stack trace would replace them."""
    empty = lw.chain_from_body({})
    assert empty.methods == [] and empty.material_ids == []
    assert lw.preview(1, empty).problems  # readable, not an exception

    full = lw.chain_from_body({
        "methods": ["Flense", " cure "], "materials": ["Deer-Hide"],
        "name": "Hunting Bag", "product": "SATCHEL",
    })
    assert full.methods == ["flense", "cure"]
    assert full.material_ids == ["deer-hide"]
    assert full.product == "satchel"
    assert full.name == "Hunting Bag"
    # Both spellings, because five benches are being written in parallel.
    assert lw.chain_from_body({"material_ids": ["deer-hide"],
                               "pattern": "cloak"}).product == "cloak"


def test_stock_from_body_keeps_dict_entries_and_coerces_counts():
    """Stock is inventory, not recipe — parsed by its own function so two identical
    chains are not unequal because one crafter was richer."""
    got = lw.stock_from_body({"stock": {"Deer-Hide": "2",
                                        "linen-thread": {"count": 1, "age_hours": 3},
                                        "junk": "not a number"}})
    assert got["deer-hide"] == 2
    assert got["linen-thread"]["age_hours"] == 3
    assert "junk" not in got


def test_check_terms_are_itemised_and_intelligence_based():
    """Craft is Int-based in PF1e. Herbalism reads Wisdom for its own authored reason,
    and copying that here would have made the tannery a wisdom craft by accident.
    Itemised because '+9' says nothing and 'Leatherworker 5, half level +2, Int +2'
    says which of the three to improve."""
    terms = lw.check_terms(_Crafter(level=5, int_mod=2), 5)
    assert [t["value"] for t in terms] == [5, 2, 2]
    assert terms[-1]["label"] == "Intelligence"
    assert lw.check_bonus(_Crafter(level=5, int_mod=2), 5) == 9
    # No actor is still a legal question: the chain's legality never depends on who
    # is standing at the bench.
    assert lw.check_bonus(None, 3) == 3


def test_preview_carries_bonus_terms_and_chance_only_with_an_actor():
    chain = _chain(["flense", "cure", "cut", "stitch"],
                   ["deer-hide", "linen-thread"])
    bare = lw.preview(1, chain)
    assert (bare.bonus, bare.terms, bare.chance) == (0, [], 0)

    withact = lw.preview(5, chain, actor=_Crafter(level=5, int_mod=2))
    assert withact.bonus == 9
    # DC 16 against +9 needs a 7 on the die: 14 faces in 20, so 70%.
    assert withact.chance == 70
    # A chain with problems is never attempted, so it is never a percentage.
    broken = lw.preview(1, _chain(["stitch"], ["deer-hide"]),
                        actor=_Crafter(level=1, int_mod=2))
    assert broken.problems and broken.chance == 0


def test_result_as_dict_carries_the_whole_bench_contract():
    """The dispatcher reads one shape for five crafts; a field missing here is a blank
    panel on the bench with nothing to explain it."""
    d = lw.preview(5, _chain(["flense", "tan", "cut", "stitch", "tool"],
                             ["deer-hide", "oak-bark", "linen-thread"],
                             product="armour piece"),
                   actor=_Crafter()).as_dict()
    for key in ("name", "tier", "rank", "stages", "dc", "risky", "problems",
                "effects", "specs", "consumes", "output", "bonus", "terms",
                "chance"):
        assert key in d, f"as_dict is missing {key}"


# --- phase two: the output contract ---------------------------------------------------------

def test_masterwork_is_reachable_and_is_read_off_the_chain():
    """**The enchanting economy depends on this.** The enchanter requires a masterwork
    vessel and armour is one of its item classes, so if masterwork leather were
    unreachable the whole chain would dead-end.

    Measured: the cheapest masterwork leather armour is Leatherworker 5 (tool is a
    level-5 method), DC 18 — deer hide + oak bark + linen thread, flense → tan → cut →
    stitch → tool, five stages, base 10 + 8. A level-5 character with Int +2 crafts it
    at 60%. It is read off the *chain*, not the tier: a legendary hide left untooled is
    not masterwork, and a common hide tooled by a master is.
    """
    mw = lw.preview(5, _chain(["flense", "tan", "cut", "stitch", "tool"],
                              ["deer-hide", "oak-bark", "linen-thread"],
                              product="armour piece"))
    assert mw.problems == []
    assert mw.dc == 18
    assert mw.output["masterwork"] is True
    assert mw.output["armour"] == "leather"
    assert lw.preview(5, _chain(["flense", "tan", "cut", "stitch", "tool"],
                                ["deer-hide", "oak-bark", "linen-thread"],
                                product="armour piece"),
                      actor=_Crafter(level=5, int_mod=2)).chance == 60

    # Untooled: everything else identical, no masterwork.
    plain = lw.preview(5, _chain(["flense", "tan", "cut", "stitch"],
                                 ["deer-hide", "oak-bark", "linen-thread"],
                                 product="armour piece"))
    assert plain.output["masterwork"] is False
    # And a legendary hide left untooled is still not masterwork.
    legendary = lw.preview(5, _chain(["flense", "tan", "cut", "stitch"],
                                     ["red-dragonhide", "dragonblood-tannin",
                                      "dragon-sinew"], product="armour piece"))
    assert legendary.tier == "legendary"
    assert legendary.output["masterwork"] is False


def test_masterwork_is_unreachable_below_level_five():
    """Tool is the masterwork finish and it is learned at 5 — so the enchanter's vessel
    requirement is a real progression gate, not a formality."""
    r = lw.preview(4, _chain(["flense", "tan", "cut", "stitch", "tool"],
                             ["deer-hide", "oak-bark", "linen-thread"],
                             product="armour piece"))
    assert any("Tool is learned at Leatherworker 5" in p for p in r.problems)


def test_studs_make_it_studded_leather_and_the_key_is_a_real_armour_row():
    """The armour key is read off the bench, not the pattern: studs are what turn
    leather armour into studded leather. Verified against `tables.ARMOUR` because a key
    the sheet has never heard of would equip as nothing and report no error."""
    from rules.tables import ARMOUR

    studded = lw.preview(5, _chain(["flense", "tan", "cut", "stitch", "tool"],
                                   ["deer-hide", "oak-bark", "linen-thread",
                                    "steel-studs"], product="armour piece"))
    assert studded.output["armour"] == "studded leather"
    assert studded.output["armour"] in ARMOUR

    # Every pattern's key, whatever it is, must exist in the table or be None.
    for product in lw.PRODUCTS:
        out = lw.preview(5, _chain(["flense", "tan", "cut", "stitch"],
                                   ["horse-hide", "oak-bark", "linen-thread"],
                                   product=product)).output
        assert out["armour"] is None or out["armour"] in ARMOUR


def test_untanned_work_carries_no_armour_row():
    """PF1e's leather armour is leather. Cured rawhide is a garment — still craftable,
    but it must not claim an armour row it cannot fill."""
    raw = lw.preview(5, _chain(["flense", "cure", "cut", "stitch", "tool"],
                               ["deer-hide", "curing-salt", "linen-thread"],
                               product="armour piece"))
    assert raw.problems == []
    assert raw.output["tanned"] is False
    assert raw.output["armour"] is None
    assert raw.output["masterwork"] is True   # tooled rawhide is still fine work


def test_every_product_maps_to_a_body_slot_or_is_carried():
    """A satchel that occupied the shoulders slot would fight a cloak for it. Carried
    goods say so — slot None, wearable False — rather than leaving the bench to guess
    from the absence of a slot."""
    expected = {"cloak": "shoulders", "boots": "feet", "bracers": "wrists",
                "gloves": "hands", "belt": "belt", "cap": "head",
                "armour piece": "armor"}
    for product, slot in expected.items():
        out = lw.preview(5, _chain(["flense", "tan", "cut", "stitch"],
                                   ["horse-hide", "oak-bark", "linen-thread"],
                                   product=product)).output
        assert out["slot"] == slot, product
        assert out["wearable"] is True
        assert out["how"] == ["wear"]

    for carried in ("satchel", "sheath", "straps"):
        out = lw.preview(1, _chain(["flense", "cure", "cut", "stitch"],
                                   ["deer-hide", "curing-salt", "linen-thread"],
                                   product=carried)).output
        assert out["slot"] is None and out["wearable"] is False
        assert out["how"] == ["carry"]
        # Nothing the tannery makes is spent by using it.
        assert out["usable"] is False


# --- phase two: icons -----------------------------------------------------------------------

def test_every_kind_has_its_own_glyph_and_none_is_herbalism_s():
    """A hide must never render as a herb — the reported bug, caused by one icon for
    'content'. Herbalism owns 🌿 herb, 🍄 fungus, 🦴 monster part, ☠️ poison."""
    kinds = {m["kind"] for m in _shipped()}
    missing = kinds - set(lw.KIND_GLYPH)
    assert not missing, f"kinds with no glyph: {sorted(missing)}"

    glyphs = list(lw.KIND_GLYPH.values())
    assert len(glyphs) == len(set(glyphs)), "two kinds share a glyph"
    assert not set(glyphs) & {"🌿", "🍄", "🦴", "☠️"}, "herbalism's glyphs reused"

    # And the material carries it, so the shelf needs no lookup table of its own.
    assert lw.get("deer-hide").glyph == lw.KIND_GLYPH["hide"]
    assert lw.get("oak-bark").glyph == lw.KIND_GLYPH["tannin"]


# --- phase two: method tooltips --------------------------------------------------------------

def test_every_method_has_structured_help():
    """The tooltip's three questions: what it does to my numbers, what it needs on the
    bench, and what I would reach for it to accomplish. A method with prose but no
    structured help renders an empty tooltip and teaches nothing."""
    data = json.loads((TRACK_FILE_DIR / "leatherworker.json")
                      .read_text(encoding="utf-8"))
    track = wc.load_dir(TRACK_FILE_DIR)["leatherworker"]
    every = track.unlocked_methods(track.max_level)
    help_ = data.get("method_help") or {}
    for method in every:
        assert method in help_, f"{method} has no method_help"
        for key in ("does", "needs", "for"):
            assert help_[method].get(key), f"{method}.{key} is empty"
        assert method in data["method_descriptions"], method
    # No orphans either: help for a method the track does not have is a stale copy.
    assert set(help_) == set(every)


# --- phase two: acquisition ------------------------------------------------------------------

def test_every_material_says_how_it_is_obtained():
    """The acquisition hub dispatches on `obtain`; an entry without one is a material
    no excursion can ever turn up, invisible rather than merely rare."""
    kinds = {"harvested", "gathered", "mined", "bought"}
    for m in _shipped():
        assert m.get("obtain") in kinds, f"{m['id']}: {m.get('obtain')!r}"
        if m["obtain"] == "bought":
            assert m.get("price_gp"), f"{m['id']} is bought with no price"
        if m["obtain"] in ("gathered", "mined"):
            assert m.get("biomes"), f"{m['id']} is {m['obtain']} from nowhere"


def test_skinning_a_winter_wolf_offers_its_pelt_and_no_other_beast_s_hide():
    """The flagship excursion. Without the creature filter, skinning a deer offered
    dragonhide — the whole point of asking the scene rather than listing the shelf."""
    got = [m.id for m in lw.obtainable("harvested", creature="worg, winter wolf")]
    assert "winter-wolf-pelt" in got
    assert got[0] == "winter-wolf-pelt", "the specific pelt must lead"
    assert "deer-hide" not in got
    assert "red-dragonhide" not in got
    # Any carcass yields the general goods, which is why sinew is not creature-tagged.
    assert "sinew-thread" in got
    # And no carcass in the scene yields nothing at all, rather than the whole shelf.
    assert lw.obtainable("harvested") == []


def test_gathering_a_forest_offers_bark_not_hide():
    got = [m.id for m in lw.obtainable("gathered", biome="forest")]
    assert "oak-bark" in got
    assert not any(lw.get(i).kind == "hide" for i in got)
    # The ground is asked: mangrove is a salt-coast tannin and does not grow inland.
    assert "mangrove-bark" not in got
    assert "mangrove-bark" in [m.id for m in lw.obtainable("gathered", biome="coast")]


def test_acquisition_excursions_declare_what_the_scene_must_provide():
    for key, spec in lw.ACQUISITION.items():
        assert spec["id"] == key
        assert spec["label"] and spec["requires_note"]
        assert spec["obtain"] in ("harvested", "gathered", "mined", "bought")
        assert spec["requires"] in ("creature", "biome", "market")
    assert lw.ACQUISITION["skin"]["label"] == "Skin the carcass"


def test_the_shared_shelf_does_not_leak_another_craft_s_materials():
    """`content/materials/` is one shelf for five benches. Measured before the craft
    filter: `obtainable("gathered", biome="forest")` answered with six blacksmith
    entries out of eleven — ash haft, living steel and friends. Worse than clutter, an
    inert haft on the bench raised the result's tier and DC, because the rank rule
    reads the rarest thing present."""
    mine = lw.materials()
    for foreign in ("living-steel", "oak-haft", "darkwood-haft"):
        assert foreign not in mine, f"{foreign} leaked onto the tannery shelf"
    # Shared kind names are exactly why the filter is by craft and not by kind:
    # `treatment` appears in all four shelf files and `fitting` in two.
    assert "curing-salt" in mine
    with pytest.raises(KeyError):
        lw.get("living-steel")

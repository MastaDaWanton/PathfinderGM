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

"""Enchanting: the track, the materials corpus, and the chain rules.

The enchanter is the second world class through `rules/worldclass.py`, and the point of
these tests is that it got there **without the framework changing** — the track is a
file, the materials are a file, and the chain rules mirror `rules/crafting.py`'s contract
(problems before rolling, refusals as sentences, homebrew layered over shipped).

The corpus tests measure the shipped file the way the herbalism tests measured theirs,
because the failure they prevent is the same one: an authored effect that does not
validate is a card line the engine will never run, discovered by a player mid-session
rather than by a test.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rules import effectspec
from rules import enchanter as en
from rules import worldclass as wc

SHIPPED = Path("content/materials/enchanter-materials.json")


@pytest.fixture
def track():
    return wc.get("enchanter")


@pytest.fixture
def corpus():
    return json.loads(SHIPPED.read_text(encoding="utf-8"))["materials"]


def _full_chain(material_ids, item="longsword", methods=None, name=""):
    return en.Chain(
        methods=methods or ["attune", "scribe", "focus", "channel", "bind", "seal"],
        material_ids=list(material_ids), item=item, name=name)


MASTERWORK_SWORD = {"masterwork": True, "kind": "weapon"}


# --- the track ---------------------------------------------------------------------------

def test_the_track_loads_through_the_generic_framework():
    """`load_dir` reads the enchanter with no code path of its own — the framework's
    stated design goal ("three more files rather than three more code paths"), asserted
    on the second file to actually arrive."""
    tracks = wc.load_dir("content/world-classes")
    track = tracks["enchanter"]
    assert track.max_level == 5
    assert track.at(1).methods == ["attune", "scribe", "bind", "seal"]
    assert "enchanter's sanctum" in track.at(5).tools


def test_level_one_can_complete_a_working():
    """Bind and seal are level-1 methods, and this pins why: a track whose only
    completable craft sits at level 3 can never earn the mastery to reach level 3 —
    the herbalist deed deadlock, one level down. Found live: the first draft gated
    bind at 3 and a level-2 shadowstuff chain came back refused."""
    result = en.preview(
        1, en.Chain(methods=["attune", "scribe", "bind", "seal"],
                    material_ids=["fire-mote", "quartz-focus", "silver-ink",
                                  "white-chalk"],
                    item="dagger"),
        item={"masterwork": True, "kind": "weapon"})
    assert result.problems == []


def test_tier_gating_walks_common_to_legendary_in_order(track):
    """Levels 1-5 unlock the five tiers in `wc.TIERS` order, no skips and no repeats.
    A track whose level 3 said "exotic" would quietly hand level-4 material to a
    level-3 character through every ceiling comparison in `preview`."""
    ranks = [wc.tier_rank(track.at(n).max_tier) for n in range(1, 6)]
    assert ranks == [1, 2, 3, 4, 5]


def test_methods_accumulate(track):
    """You do not forget how to bind when you learn to imbue."""
    assert set(track.unlocked_methods(3)) == {
        "attune", "scribe", "bind", "seal", "focus", "channel", "imbue"}
    assert track.unlocked_methods(1) == ["attune", "scribe", "bind", "seal"]


def test_the_level_five_deed_is_reachable_from_level_four(track):
    """The herbalist's `_deeds_note` records the trap this pins: a level-5 deed that
    needs level-5 material can never be earned. The enchanter's ladder is empower —
    an Enchanter 4 empowering an exotic working produces a legendary-tier result,
    and that success is the deed."""
    result = en.preview(
        4,
        _full_chain(["thundering-essence", "ruby-focus", "auric-ink", "void-chalk"],
                    methods=["attune", "scribe", "focus", "channel", "bind",
                             "empower", "seal"]),
        item=MASTERWORK_SWORD)
    assert result.problems == []
    assert result.tier == "legendary" and result.empowered
    assert track.deed_done(tier=result.tier, success=True) == "legendary-binding"


# --- the materials corpus ----------------------------------------------------------------

def test_material_ids_are_unique(corpus):
    """Duplicate ids merge silently in `read_folder` — the second entry would shadow
    the first with no error anywhere, which is how a corpus loses an entry nobody
    notices is gone."""
    ids = [m["id"] for m in corpus]
    dupes = {i for i in ids if ids.count(i) > 1}
    assert not dupes, f"duplicate material ids: {sorted(dupes)}"


def test_every_tier_is_populated(corpus):
    """The brief's target: at least 100 materials, all five tiers stocked. A tier with
    two entries is a level of the track with nothing to do."""
    by_tier = {t: [m for m in corpus if m["tier"] == t] for t in wc.TIERS}
    for tier, entries in by_tier.items():
        assert len(entries) >= 10, f"{tier}: only {len(entries)} materials"
    assert len(corpus) >= 100, f"only {len(corpus)} materials in the shipped file"


def test_every_authored_effect_validates(corpus):
    """Zero invalid specs, offenders printed. The herbalism corpus's lesson applied
    up front: an effect that fails `effectspec.validate` is prose wearing a spec's
    clothes — it renders on a card and does nothing when the engine is asked, the
    exact silent failure `docs/homebrew-rules.md` §1 names. Measured over `effects`
    and `drawbacks` both, because a drawback that stopped validating would stop
    costing, and enchanting's materials are supposed to cost."""
    bad = []
    for m in corpus:
        for where in ("effects", "drawbacks"):
            for i, spec in enumerate(m.get(where) or []):
                problems = effectspec.validate(spec, f"{m['id']}.{where}[{i}]")
                bad.extend(problems)
    for line in bad:
        print(line)
    assert not bad, f"{len(bad)} invalid effect specs (printed above)"


def test_the_shipped_file_loads_through_materials():
    """The loader reads the same file the corpus tests measure, so a schema drift
    between file and loader cannot pass one and fail the other."""
    loaded = en.materials()
    assert "flaming-essence" in loaded
    assert loaded["quartz-focus"].capacity == 1
    assert loaded["diamond-focus"].fragile


# --- refusals ----------------------------------------------------------------------------

def test_binding_without_a_focus_is_refused():
    """The essence has to live somewhere. Without this check a bindless chain would
    price and roll like a real one and produce an enchantment no stone anchors."""
    result = en.preview(
        3, _full_chain(["flaming-essence", "quicksilver-ink", "white-chalk"]),
        item=MASTERWORK_SWORD)
    assert any("Binding needs a focus" in p for p in result.problems)


def test_quartz_cannot_hold_a_storm():
    """Focus capacity gates essence tier: a common stone anchoring an exotic essence
    is refused in the circle, before anything is risked, not discovered as a mishap."""
    result = en.preview(
        4, _full_chain(["thundering-essence", "quartz-focus", "auric-ink",
                        "void-chalk"]),
        item=MASTERWORK_SWORD)
    assert any("cannot hold" in p for p in result.problems)


def test_a_non_masterwork_vessel_is_refused():
    """The book's own gate: only masterwork items take enchantment. Checked against
    what the caller asserts, and an unvouched item (item=None) is refused too —
    assuming masterwork would wave every rusty sword through."""
    chain = _full_chain(["flaming-essence", "sapphire-focus", "quicksilver-ink",
                         "white-chalk"])
    said_plain = en.preview(3, chain, item={"masterwork": False, "kind": "weapon"})
    said_nothing = en.preview(3, chain, item=None)
    assert any("masterwork" in p for p in said_plain.problems)
    assert any("masterwork" in p for p in said_nothing.problems)


def test_two_essences_of_one_family_are_refused():
    """One essence per family per vessel: red and black dragon ichor share the fire
    and acid split — red is fire, black is acid — so the same-family pair here is
    flaming essence over red dragon ichor, both family `fire`. Two fire bindings are
    not a hotter sword; the seat is taken."""
    result = en.preview(
        5, _full_chain(["flaming-essence", "red-dragon-ichor", "diamond-focus",
                        "auric-ink", "void-chalk"],
                       methods=["attune", "scribe", "focus", "channel", "imbue",
                                "bind", "seal"]),
        item=MASTERWORK_SWORD)
    assert any("same family" in p or "never two" in p for p in result.problems)


def test_seal_before_bind_is_refused():
    """Order matters in a ritual the way it does in a pot: sealing a binding that has
    not happened yet is the enchanting shape of grinding the tea."""
    result = en.preview(
        3, _full_chain(["flaming-essence", "sapphire-focus", "quicksilver-ink",
                        "white-chalk"],
                       methods=["attune", "scribe", "focus", "seal", "channel",
                                "bind"]),
        item=MASTERWORK_SWORD)
    assert any("nothing has been bound yet" in p for p in result.problems)


def test_methods_are_gated_by_level():
    """Focus is learned at Enchanter 2; a level-1 chain that reaches for it says so
    rather than silently working — crafting's phrasing, kept, so the two benches
    read alike."""
    result = en.preview(
        1, _full_chain(["fire-mote", "quartz-focus", "silver-ink", "white-chalk"]),
        item=MASTERWORK_SWORD)
    assert any("learned at Enchanter 2" in p for p in result.problems)


def test_two_essences_need_imbue():
    """More than one essence in a working is imbuing, learned at 3 — the restriction
    that lifts itself when earned, herbalism's infusion rule transplanted. Both halves
    pinned: the missing method at 2, and the level gate when it is written anyway."""
    ids = ["fire-mote", "tide-mote", "amethyst-focus", "iron-gall-ink", "white-chalk"]
    without = en.preview(2, _full_chain(ids), item=MASTERWORK_SWORD)
    written = en.preview(
        2, _full_chain(ids, methods=["attune", "scribe", "focus", "channel",
                                     "imbue", "bind", "seal"]),
        item=MASTERWORK_SWORD)
    assert any("put imbue in" in p for p in without.problems)
    assert any("Imbue is learned at Enchanter 3" in p for p in written.problems)


# --- the finished binding ----------------------------------------------------------------

def test_a_flaming_binding_carries_its_fire_rider():
    """The output of a successful chain is the enchanted item's standing effect list —
    a flaming working must put a fire `damage` spec on it, marked with where it came
    from, or the finished sword is a name with nothing behind it."""
    result = en.preview(
        3, _full_chain(["flaming-essence", "sapphire-focus", "quicksilver-ink",
                        "white-chalk"]),
        item=MASTERWORK_SWORD)
    assert result.problems == []
    riders = [s for s in result.specs
              if s.get("type") == "damage" and s.get("damage_type") == "fire"]
    assert riders and riders[0]["from"] == "Flaming Essence"
    assert result.name == "Flaming Longsword"
    assert all(not effectspec.validate(s) for s in result.specs)


def test_effects_are_prose_and_specs_are_structure():
    """The split the shared bench spine expects, and the one this module did not have
    when it was written alone: `effects` held structured dicts under a name the spine
    renders as strings. A card shows `effects`; the engine runs `specs`; both come off
    one walk so they cannot disagree about what the item does."""
    result = en.preview(
        3, _full_chain(["flaming-essence", "sapphire-focus", "quicksilver-ink",
                        "white-chalk"]),
        item=MASTERWORK_SWORD)
    assert all(isinstance(line, str) for line in result.effects)
    assert all(isinstance(spec, dict) for spec in result.specs)
    assert len(result.effects) == len(result.specs)
    assert "1d6 fire damage" in " ".join(result.effects)
    # And as_dict carries everything the spine reads, by name.
    d = result.as_dict()
    for key in ("name", "tier", "rank", "stages", "dc", "risky", "problems",
                "effects", "specs", "consumes", "output", "bonus", "terms", "chance"):
        assert key in d, f"as_dict is missing {key}"


def test_the_output_is_an_inventory_item():
    """`Result.output` is what the player receives, in the shape the sheet stores:
    identified, masterwork, with its standing specs and what it was made of. Without
    it the bench can only describe an enchantment it cannot hand over."""
    result = en.preview(
        3, _full_chain(["flaming-essence", "sapphire-focus", "quicksilver-ink",
                        "white-chalk"]),
        item={"masterwork": True, "kind": "weapon", "weapon": "longsword"})
    out = result.output
    assert out["kind"] == "crafted" and out["craft"] == "enchanter"
    assert out["masterwork"] is True and out["count"] == 1
    assert out["weapon"] == "longsword" and out["usable"] and not out["wearable"]
    assert out["properties"] == ["Flaming Essence"]
    assert all(isinstance(line, str) for line in out["effects"])


def test_a_drawback_rides_in_the_standing_effects():
    """Shadowstuff dims its bearer, and the dimming is part of the binding: the
    drawback spec appears in the finished spec list, marked, so an enchantment
    cannot quietly drop its price on the way to the sheet."""
    result = en.preview(
        2, _full_chain(["shadowstuff", "amethyst-focus", "iron-gall-ink",
                        "white-chalk"],
                       item="cloak"),
        item={"masterwork": True, "kind": "armour"})
    assert result.problems == []
    dims = [s for s in result.specs if s.get("drawback")]
    assert dims and dims[0]["target"] == "perception" and dims[0]["amount"] == -2
    assert dims[0] in result.drawbacks


def test_off_type_binding_costs_five_dc_not_a_refusal():
    """Fire motes want weapons: bound to armour the working is +5 DC — the material
    resisting — not impossible. A refusal here would delete the book's whole
    against-the-grain space; a free pass would delete the materials' character."""
    chain = _full_chain(["fire-mote", "quartz-focus", "silver-ink", "white-chalk"],
                        item="breastplate")
    on_armour = en.preview(3, chain, item={"masterwork": True, "kind": "armour"})
    on_weapon = en.preview(3, chain, item=MASTERWORK_SWORD)
    assert on_armour.problems == [] and on_weapon.problems == []
    assert on_armour.dc == on_weapon.dc + en.OFF_TYPE_DC


def test_ghost_residue_only_binds_at_night():
    """Scene state gates the working the way spoilage gates the pot: refused when the
    scene says daylight, noted when there is no clock to ask — checking against a
    clock nobody supplied is how every pre-clock caller would have broken."""
    chain = _full_chain(["ghost-residue", "sapphire-focus", "quicksilver-ink",
                         "bone-chalk"])
    by_day = en.preview(3, chain, item=MASTERWORK_SWORD, at_night=False)
    no_clock = en.preview(3, chain, item=MASTERWORK_SWORD, at_night=None)
    assert any("only binds at night" in p for p in by_day.problems)
    assert no_clock.problems == []
    assert any("only binds at night" in n for n in no_clock.notes)


def test_a_mishap_on_a_diamond_loses_the_stone():
    """The diamond holds anything and cracks on a mishap — lost, not spent. Said on
    the preview, before the roll, because which stone to risk is the player's choice
    and a cost only visible after the dice is not a choice."""
    fragile = en.preview(
        5, _full_chain(["storm-heart", "diamond-focus", "phoenix-quill-ink",
                        "diamond-dust-line"]),
        item=MASTERWORK_SWORD)
    sturdy = en.preview(
        3, _full_chain(["flaming-essence", "sapphire-focus", "quicksilver-ink",
                        "white-chalk"]),
        item=MASTERWORK_SWORD)
    assert "cracks" in fragile.mishap and "lost" in fragile.mishap
    assert "survives" in sturdy.mishap
    # And a focus is never on the consumed list: success returns it to the pouch.
    assert "diamond-focus" not in fragile.consumes
    assert "storm-heart" in fragile.consumes


# --- dispatch, acquisition, glyphs -------------------------------------------------------

def test_chain_from_body_is_tolerant_about_shape():
    """The spine posts one body to whichever mode is active, so the parse must survive
    a list, a comma-joined string, and keys meant for the other mode. A 500 on a form
    that looked fine is the failure this prevents; real validation is `preview`'s job,
    where a problem can be shown."""
    listed = en.chain_from_body({
        "methods": ["attune", "scribe", "bind", "seal"],
        "materials": ["fire-mote", "quartz-focus"], "item": "dagger"})
    joined = en.chain_from_body({
        "methods": "attune, scribe, bind, seal",
        "materials": "Fire-Mote, Quartz-Focus", "vessel": "dagger",
        "enhancement": "+3"})
    assert listed.methods == joined.methods == ["attune", "scribe", "bind", "seal"]
    assert listed.material_ids == joined.material_ids == ["fire-mote", "quartz-focus"]
    assert joined.item == "dagger"
    assert en.chain_from_body({}).methods == []


def test_check_terms_are_itemised_and_intelligence_based():
    """d20 + track level + half character level + Int, itemised. Enchanting imposes a
    structure rather than reading one, which is the Intelligence half of the sheet —
    and the terms are listed rather than summed because "+9" says nothing about which
    of the three to go and improve."""
    class Stub:
        level = 6

        def ability_mod(self, which):
            return 3 if which == "int" else 0

    terms = en.check_terms(Stub(), 4)
    assert [t["value"] for t in terms] == [4, 3, 3]
    assert en.check_bonus(Stub(), 4) == 10
    assert "Intelligence" in terms[-1]["label"]


def test_every_material_says_where_it_comes_from():
    """The craft-action button is the hub for obtaining materials, so a material with
    no `obtain` is one the hub can never offer — invisible, with nothing to say why.
    Gathered and mined entries must name biomes and harvested ones a creature, or the
    excursion has no way to decide what turns up."""
    mats = en.materials()
    mine = [m for m in mats.values()
            if m.id in _shipped_ids()]
    assert mine, "the shipped catalogue did not load"
    for m in mine:
        assert m.obtain in ("bought", "mined", "harvested", "gathered"), \
            f"{m.id}: {m.obtain!r} is not an acquisition kind"
        if m.obtain in ("gathered", "mined"):
            assert m.biomes, f"{m.id} is {m.obtain} but names no biome"
        if m.obtain == "harvested":
            assert m.biomes or m.from_creature, \
                f"{m.id} is harvested but names neither creature nor place"


def test_the_shelf_walk_skips_files_that_are_not_shelves():
    """`content/materials` is a shared folder, not a homogeneous shelf, and this module
    reads all of it. Measured when the second mode's catalogue landed there: all 170
    priced magic-item entries loaded as enchanting materials, every one of them honestly
    carrying `obtain: "bought"` — so `obtainable("bought")` offered to sell the player a
    Ring of Protection +1 as a crafting material. Found by driving the loader, not by
    reading it. A neighbour's file in another shape (the alchemist's spell potions, whose
    list lives under `potions`) must also load as nothing rather than raising."""
    loaded = en.materials()
    assert "mi-flaming" not in loaded and "mi-ring-protection-1" not in loaded
    assert "fire-mote" in loaded, "skipping went too far and took the shelf with it"
    for m in en.obtainable("bought"):
        assert not m.id.startswith("mi-"), f"{m.id} is a magic item, not a material"


def test_obtainable_narrows_to_where_you_are_standing():
    """A fire mote is skimmed off a forge or a lava vent, not out of a bog. The filter
    is what makes an excursion a place rather than a shop with weather."""
    mountain = {m.id for m in en.obtainable("gathered", biome="mountain")}
    swamp = {m.id for m in en.obtainable("gathered", biome="swamp")}
    assert "fire-mote" in mountain and "fire-mote" not in swamp
    assert "ghost-residue" in swamp
    dragons = {m.id for m in en.obtainable("harvested", creature="red dragon")}
    assert "red-dragon-ichor" in dragons and "lich-dust" not in dragons


def test_acquisition_excursions_are_declared():
    """The play layer wires the UI; the track declares the data. Every excursion needs
    an id, a label, a real obtain kind and what it needs, or the hub cannot draw it."""
    assert en.ACQUISITION
    for excursion in en.ACQUISITION:
        assert excursion["obtain"] in ("bought", "mined", "harvested", "gathered")
        for key in ("id", "label", "needs", "blurb"):
            assert excursion.get(key), f"{excursion.get('id')}: missing {key}"


def test_every_kind_has_a_distinct_glyph():
    """One emoji per kind, none of them herbalism's 🌿🍄🦴☠️. A shared glyph makes two
    benches look like one shelf at a glance, which is the whole thing icons are for."""
    glyphs = en.KIND_GLYPH
    kinds = {m.kind for m in en.materials().values() if m.id in _shipped_ids()}
    assert kinds <= set(glyphs), f"kinds with no glyph: {kinds - set(glyphs)}"
    assert len(set(glyphs.values())) == len(glyphs), "two kinds share a glyph"
    assert not (set(glyphs.values()) & {"🌿", "🍄", "🦴", "☠️"}), \
        "herbalism's glyphs must never be reused"


def test_method_help_matches_method_descriptions(track):
    """Both sets are authored by hand in one file, and a method that gains a tooltip
    while losing its description (or the reverse) is a bench that explains half of
    itself. Each entry needs all three fields — does, needs, for — because the tooltip
    has three jobs and a player scanning for the DC should not have to read prose."""
    data = json.loads(Path("content/world-classes/enchanter.json")
                      .read_text(encoding="utf-8"))
    described = set(data["method_descriptions"])
    helped = set(data["method_help"])
    assert described == helped, f"only described: {described - helped}; " \
                                f"only helped: {helped - described}"
    assert described == {m for l in track.levels for m in l.methods}
    for method, help_text in data["method_help"].items():
        for key in ("does", "needs", "for"):
            assert help_text.get(key), f"{method}: method_help has no {key!r}"


def _shipped_ids() -> set[str]:
    """The ids from this track's own file. `materials()` reads the whole folder as one
    shared shelf, so a test that measures 'my catalogue' has to say which is mine."""
    return {m["id"] for m in json.loads(SHIPPED.read_text(encoding="utf-8"))["materials"]}


# --- homebrew ----------------------------------------------------------------------------

def test_homebrew_materials_layer_over_shipped(tmp_path, monkeypatch):
    """A homebrew essence just works beside the shipped set, and a homebrew copy of a
    shipped id merges over it field by field — the `worldclass.tracks()` pattern,
    pinned here because the failure it prevents (a stale user copy shadowing a
    corrected shipped one, or the reverse) is invisible until someone's fixed
    material silently is not."""
    from django.conf import settings

    hb = tmp_path / "homebrew" / "materials"
    hb.mkdir(parents=True)
    (hb / "moon-essence.json").write_text(json.dumps({
        "id": "moon-essence", "name": "Moon Essence", "kind": "essence",
        "tier": "rare", "family": "light", "adjective": "Moonlit",
        "effects": [{"type": "narrative", "target": "Glows under an open sky"}],
    }), encoding="utf-8")
    # A partial override of a shipped entry: only the name, so the merge (not
    # replacement) is what keeps the effects.
    (hb / "flaming-essence.json").write_text(json.dumps({
        "id": "flaming-essence", "name": "Balefire Essence",
    }), encoding="utf-8")

    monkeypatch.setattr(settings, "CAMPAIGN_DIR", str(tmp_path / "campaigns"))
    monkeypatch.setattr(en, "_MATERIALS", None)

    loaded = en.materials()
    assert "moon-essence" in loaded
    assert loaded["moon-essence"].tier == "rare"
    assert loaded["flaming-essence"].name == "Balefire Essence"
    # The merge kept what the override did not send: the fire rider survives.
    assert loaded["flaming-essence"].effects, \
        "homebrew override replaced the entry instead of merging over it"
    # And the homebrew essence goes straight through a chain, unmodified code.
    result = en.preview(
        3, _full_chain(["moon-essence", "sapphire-focus", "quicksilver-ink",
                        "white-chalk"]),
        item=MASTERWORK_SWORD)
    assert result.problems == []
    assert result.name == "Moonlit Longsword"

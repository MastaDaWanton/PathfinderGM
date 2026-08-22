"""One place that knows what kinds of content exist.

Seven modules each grew their own copy of the same twenty lines: glob `content/<thing>`,
glob `homebrew/<thing>`, accept either a file holding a list or a file holding one entry,
merge field by field rather than replacing. `classes`, `spells`, `feats`, `weapons`,
`ingredients`, `worldclass` and `bestiary` — seven copies of a rule, which CLAUDE.md names
as the reason a fix ships from the copy nobody looked at.

They had already drifted, which is the other half of that lesson: some merged and some
replaced, and some read a bare object file while others read only a file holding a list.

The visible cost was the editor. `open_thing` read `if bench_id in ("ingredients",
"consumables")`, so seven of the nine benches could create content and never correct it —
a shipped creature, feat, weapon or spell would not open at all.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rules import registry


@pytest.fixture
def mine(tmp_path, settings):
    """A homebrew directory belonging to nobody but this test."""
    settings.CAMPAIGN_DIR = str(tmp_path / "campaigns")
    return tmp_path / "homebrew"


# --- the declarations ---------------------------------------------------------------------

def test_every_kind_declares_where_it_lives_and_what_it_holds():
    for kind in registry.KINDS.values():
        assert kind.folder and kind.key and kind.label
        assert kind.fields, f"{kind.id} declares no fields, so nothing can build a form"


def test_every_kind_can_be_named():
    assert registry.get("creatures").label == "Creatures"
    with pytest.raises(LookupError, match="no such kind"):
        registry.get("dragons")


def test_the_catalogue_carries_the_fields_a_form_needs():
    """The builder draws its form from this rather than carrying one per bench, so a new
    kind of content is one entry here instead of a loader, a route and a template."""
    kinds = {k["id"]: k for k in registry.catalogue()}
    assert len(kinds) >= 9
    fields = {f["name"]: f for f in kinds["ingredients"]["fields"]}
    assert fields["name"]["required"]
    assert fields["effects"]["type"] == "effects"
    assert "forest" in fields["biomes"]["choices"]


# --- one loader, not seven -----------------------------------------------------------------

def test_a_file_holding_a_list_is_read(mine):
    (mine / "creatures").mkdir(parents=True)
    (mine / "creatures" / "pack.json").write_text(json.dumps(
        {"creatures": [{"id": "grue", "name": "Grue"}, {"id": "wyrm", "name": "Wyrm"}]}),
        encoding="utf-8")
    got = registry.read_folder(mine / "creatures", "creatures")
    assert set(got) == {"grue", "wyrm"}


def test_a_file_holding_one_thing_is_read_too(mine):
    """An import writes a list and the editor writes one file per thing. Reading only the
    first shape is what made a saved homebrew ingredient appear in the editor when
    reopened and never reach play — with no error anywhere."""
    (mine / "creatures").mkdir(parents=True)
    (mine / "creatures" / "grue.json").write_text(
        json.dumps({"id": "grue", "name": "Grue"}), encoding="utf-8")
    assert "grue" in registry.read_folder(mine / "creatures", "creatures")


def test_unreadable_files_are_skipped_rather_than_fatal(mine):
    (mine / "creatures").mkdir(parents=True)
    (mine / "creatures" / "broken.json").write_text("{not json", encoding="utf-8")
    (mine / "creatures" / "grue.json").write_text(
        json.dumps({"id": "grue", "name": "Grue"}), encoding="utf-8")
    assert list(registry.read_folder(mine / "creatures", "creatures")) == ["grue"]


def test_homebrew_merges_over_shipped_field_by_field(mine):
    """Replacing would silently drop the tier, the biomes and the harvesting notes the
    editor never asked about — correcting one bonus would delete everything else."""
    (mine / "ingredients").mkdir(parents=True)
    (mine / "ingredients" / "woundwort.json").write_text(
        json.dumps({"id": "woundwort", "name": "Woundwort of Mine"}), encoding="utf-8")

    merged = registry.load_raw("ingredients")["woundwort"]
    assert merged["name"] == "Woundwort of Mine"
    assert merged.get("biomes"), "the shipped biomes were dropped"


def test_shipped_alone_is_readable_with_no_homebrew_at_all(mine):
    assert len(registry.load_raw("ingredients")) > 100


# --- opening anything for correction ----------------------------------------------------------

@pytest.mark.parametrize("kind,thing", [
    ("ingredients", "woundwort"),
    ("creatures", "goblin"),
    ("feats", "power-attack"),
    ("items", "glaive"),
    ("spells", "fireball"),
    ("classes", "wizard"),
])
def test_a_shipped_thing_opens_on_every_bench(kind, thing, mine):
    """Two of these worked before and four did not: `open_thing` named ingredients and
    consumables in an `if`, and every other bench could create but never correct. A
    shipped entry that cannot be opened is a conversion nobody can undo."""
    found = registry.find(kind, thing)
    assert found, f"{kind}/{thing} would not open"
    assert found.get("name")


def test_something_that_is_not_there_says_so(mine):
    assert registry.find("creatures", "tarrasque-of-the-mind") is None


def test_yours_wins_over_shipped_when_opening(mine):
    (mine / "ingredients").mkdir(parents=True)
    (mine / "ingredients" / "woundwort.json").write_text(
        json.dumps({"id": "woundwort", "name": "Corrected Woundwort"}), encoding="utf-8")
    assert registry.find("ingredients", "woundwort")["name"] == "Corrected Woundwort"


def test_a_broken_shipped_loader_reports_empty_rather_than_falling_over(monkeypatch):
    """The homebrew page asks every kind at once, so one kind failing must not take the
    page down with it."""
    monkeypatch.setitem(registry.KINDS, "creatures",
                        registry.Kind(id="creatures", label="Creatures",
                                      folder="creatures", key="creatures",
                                      shipped_loader="nowhere:at_all",
                                      fields=[registry.Field("name", "Name")]))
    assert registry.shipped("creatures") == {}


# --- writing ---------------------------------------------------------------------------------

def test_saving_writes_to_your_directory_and_never_the_shipped_one(mine):
    before = Path("content/ingredients/herbs-and-parts.json").read_text(encoding="utf-8")
    path = registry.save("ingredients", {"id": "moonbell", "name": "Moonbell"})
    assert path.parent == registry.homebrew_dir("ingredients")
    assert Path("content/ingredients/herbs-and-parts.json").read_text(
        encoding="utf-8") == before


def test_something_saved_is_read_back(mine):
    registry.save("creatures", {"id": "grue", "name": "Grue", "cr": "3"})
    assert registry.find("creatures", "grue")["cr"] == "3"


def test_saving_something_with_no_id_is_refused(mine):
    with pytest.raises(ValueError, match="needs an id"):
        registry.save("creatures", {"name": "Nameless"})


# --- through the wire ---------------------------------------------------------------------------

def test_the_page_can_ask_for_every_kind(client):
    kinds = client.get("/api/kinds").json()["kinds"]
    assert {k["id"] for k in kinds} >= {"creatures", "npcs", "items", "classes"}


@pytest.mark.parametrize("bench,thing", [
    ("creatures", "goblin"), ("feats", "power-attack"), ("spells", "fireball"),
])
def test_every_bench_opens_over_http(client, bench, thing):
    d = client.get(f"/api/bench/{bench}/open/{thing}").json()
    assert d["source"] == "shipped"
    assert d["name"]
    assert "effects" in d and "description" in d


# --- the two that a concurrent change caught -------------------------------------------------

def test_the_biome_choices_are_derived_rather_than_retyped():
    """They were the fourteen names written out again — a second copy that agreed on the
    day it was written and drifts the first time somebody adds a biome to one and not the
    other."""
    from rules import biomes

    assert tuple(registry.BIOME_CHOICES) == tuple(biomes.BIOMES)
    assert tuple(registry.CLIMATE_CHOICES) == tuple(biomes.CLIMATES)


def test_a_creature_edits_its_lists_without_overwriting_the_printed_line():
    """`environment` is the book's own prose — "temperate or cold hills" — and `biomes` is
    what was read out of it. Declaring a *list* editor over `environment` would have
    written a biome list on top of the sentence and thrown the original away."""
    fields = {f.name: f for f in registry.get("creatures").fields}
    assert fields["environment"].type == "textarea"
    assert fields["biomes"].type == "list"
    assert fields["climates"].type == "list"


def test_one_field_name_means_one_thing_across_kinds():
    """A list called `environment` on an NPC and prose called `environment` on a creature
    is how the creature field went wrong to begin with."""
    for kind in registry.KINDS.values():
        for f in kind.fields:
            if f.name == "environment":
                assert f.type == "textarea", f"{kind.id}.environment is a {f.type}"
            if f.name == "biomes":
                assert f.type == "list", f"{kind.id}.biomes is a {f.type}"


# --- the bench, the form, and what a save keeps -----------------------------------------

def test_every_bench_opens_a_builder_rather_than_two_of_them(client):
    """`builder` was set by hand on `consumables` and `ingredients` and left off the other
    seven, so a creature, feat, weapon or spell could be listed and never corrected — even
    after `registry.find` and `open_thing` could already handle all nine. It is derived
    from the kind declaration now, which is the same declaration the form is drawn from."""
    for bench_id in registry.KINDS:
        d = client.get(f"/api/bench/{bench_id}").json()
        assert d["bench"]["builder"] == "effects", bench_id


def test_the_form_is_drawn_from_the_declaration_and_not_written_into_the_page():
    """Four inputs — name, kind, description, effects — were written into home.html, which
    is why only the two benches those four suited could be edited at all: a creature has a
    CR and a size and neither had anywhere to go."""
    page = Path("play/templates/play/home.html").read_text(encoding="utf-8")
    assert "function draftField(" in page
    assert 'KINDS' in page and '"/api/kinds"' in page
    # The three hardcoded inputs are gone from the markup. Matched on the attribute rather
    # than on the handler line, because the handler line is quoted in the comment that
    # explains why it went.
    for gone in ('id="d-name"', 'id="d-kind"', 'id="d-desc"'):
        assert gone not in page, gone
    assert 'data-draft=' in page


def test_saving_a_creature_keeps_the_fields_its_kind_declares(mine, client):
    """The old save wrote five keys. A creature through it kept its name, kind,
    description and effects and lost its CR, its size and its terrain — and because
    homebrew merges over shipped field by field, the loss was invisible until something
    asked for a missing one."""
    r = client.post("/api/bench/creatures/save", data=json.dumps({
        "id": "grue", "name": "Grue", "cr": "3", "size": "large",
        "creature_type": "aberration", "environment": "lightless caves",
        "biomes": ["underground"], "climates": ["cold"], "hp": 30, "flat_ac": 15,
        "effects": [{"type": "immunity", "target": "cold"}],
    }), content_type="application/json")
    assert r.status_code == 200

    back = registry.find("creatures", "grue")
    assert back["cr"] == "3" and back["size"] == "large"
    assert back["biomes"] == ["underground"] and back["climates"] == ["cold"]
    assert back["hp"] == 30 and back["flat_ac"] == 15


def test_a_field_the_kind_does_not_declare_is_not_written(mine, client):
    """Read from the declaration rather than from the body, so a client cannot put keys
    into a content file that nothing will ever read back."""
    client.post("/api/bench/creatures/save", data=json.dumps({
        "id": "grue", "name": "Grue", "nonsense": "should not be stored",
    }), content_type="application/json")
    assert "nonsense" not in registry.find("creatures", "grue")


def test_every_row_a_bench_draws_can_be_opened(client):
    """Turning the builder on for all nine surfaced two ways a row could point at nothing.
    A row that 404s when clicked is worse than no row: the page drew it a moment earlier.

    The creatures bench lists the four hand-written townsfolk and the registry's loader
    pointed at `bestiary.imported`, which is the two content files and knows nothing about
    them. The feats bench listed `rules.tables.FEATS`, keyed "weapon finesse" with a space,
    while `rules.feats` — what the registry resolves — is keyed by slug.
    """
    for bench_id in registry.KINDS:
        rows = client.get(f"/api/bench/{bench_id}").json()["rows"]
        for row in [r for r in rows if r.get("id")][:5]:
            r = client.get(f"/api/bench/{bench_id}/open/{row['id']}")
            assert r.status_code == 200, f"{bench_id}/{row['id']}: {r.json()}"


def test_a_bench_that_lists_nothing_clickable_would_have_a_builder_nobody_can_reach(client):
    """`classes`, `worldclasses`, `items` and `feats` emitted rows with no id at all, so
    no `data-open` was drawn and the form could not be opened from any of them."""
    for bench_id in ("classes", "worldclasses", "items", "feats", "creatures"):
        rows = client.get(f"/api/bench/{bench_id}").json()["rows"]
        assert rows and all(r.get("id") for r in rows), bench_id


def test_the_feats_bench_stops_hiding_the_imported_list(client):
    """It showed the 16 the sheet applies by hand and said "16 shipped" — accurate about
    itself, and quietly sitting on 1,474 feats the app had already imported."""
    rows = client.get("/api/bench/feats").json()["rows"]
    assert len(rows) > 100

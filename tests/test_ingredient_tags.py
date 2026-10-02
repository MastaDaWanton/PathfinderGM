"""The herbalism revamp's ingredient tags, checked mechanically.

`docs/herbalism-revamp-plan.md` §5 gives every ingredient a `part`, every structured
effect a `route`, and the bench's reagents `solvent`, `base_for` and `neutralizer`. The
bench keys its tables on those words (Brew makes an infusion of a leaf and a decoction of
a root; a herbal product drops every `external` effect), so a missing or misspelled tag
does not fail loudly. It falls through to a default and the bench quietly does the wrong
thing. These tests are where a bad tag is refused by name.

Measured before the tagging pass, 2026-10-02: all 161 entries carried no `part`, and none
of the 150 entries with structured effects carried a `route`. Every one of them read as a
swallowed leaf, so Comfrey's root, Leechwort's bark and a Basilisk Eye all reached the
bench as the same thing, and Mistveil Fern's partial incorporeality was a herbal tea.
"""
from __future__ import annotations

import json
from pathlib import Path

from rules import ingredients as ing

CORPUS = Path("content/ingredients/herbs-and-parts.json")

# External effects on entries that are *not* hybrid. Each is a non-magical use that is
# still not the herbalist's: it acts on an object, on another creature, or through a
# poison meant for someone else. Pinned by hand, because "plainly non-herbal" is a
# judgement a person made (docs/herbalism-hybrid-review.md lists the same calls).
NON_HERBAL_EXTERNAL = {
    "darkroot": "titan gum glues objects together",
    "dragon-flower": "the growing flower's stench fouls an area for anyone near it",
    "dwarven-oak": "oakdeath strengthens a poison meant for someone else",
    "goblin-rouge": "a waterproof ink",
    "golden-maple-leaves": "an additive for alchemical items such as tanglefoot bags",
    "halfling-thistle": "shinewater takes rust off a weapon",
    "lish-nut": "the eater's smell sickens vermin that touch them",
    "meadow-giant": "white sanguine is smeared on a blade with a poison",
    "monkshood": "juice smeared on a weapon as a poison",
    "orticusp": "night venom strengthens a poison meant for someone else",
    "selpeme-blossom": "the scent frightens animals: it acts on them, not the wearer",
    "wild-fireclover": "mindfire strengthens a poison meant for someone else",
}

# Saps that are not a salve body. The owner's rule is "grinding of any bark and tree sap
# makes a base for salves"; these two saps are a blistering purgative poison and an
# opiate taken by mouth, and neither is something you would thicken a salve with.
NOT_A_SALVE_BASE = {
    "euphorbia": "milky juice that raises weeping blisters on skin",
    "poppy-tears": "an opiate gum taken by mouth",
}


def _raw() -> list[dict]:
    return json.loads(CORPUS.read_text(encoding="utf-8"))["ingredients"]


def test_every_entry_names_a_real_part():
    """Every shipped entry states its part, and the part is one the bench knows.

    Read from the file, not the built Ingredient: `from_dict` fills a missing part from
    the kind, which is right for an old save and wrong for the shipped corpus, where a
    missing tag would hide behind the default. Before the tagging pass 161 of 161
    entries had none."""
    bad = {e["id"]: e.get("part") for e in _raw() if e.get("part") not in ing.PARTS}
    assert bad == {}, f"no part, or a part outside {ing.PARTS}: {bad}"


def test_every_structured_effect_names_a_real_route():
    """Every structured effect says how it reaches the body.

    An absent route reads as `ingest`, so an untagged external effect would be kept on a
    herbal product rather than dropped. 0 of the 150 entries with effects had a route
    before the tagging pass."""
    bad = [f"{e['id']} effect {i + 1}: {f.get('route')!r}"
           for e in _raw() for i, f in enumerate(e.get("effects") or [])
           if f.get("route") not in ing.ROUTES]
    assert bad == [], f"no route, or one outside {ing.ROUTES}: {bad}"


def test_external_effects_belong_to_hybrids_or_to_plainly_non_herbal_entries():
    """An effect that reaches outside the body is alchemy's (plan §5.2). It may sit on a
    hybrid entry, which the alchemist can also reach, or on one of the hand-pinned
    non-herbal entries above. Anything else is an external effect that only the
    herbalist's shelf carries, which means nobody can ever make it.

    The pinned list is checked in the other direction too, so it cannot rot: a pinned id
    that became hybrid, or stopped having an external effect, is a stale exemption."""
    stray, stale = [], []
    for e in _raw():
        external = any(f.get("route") == "external" for f in e.get("effects") or [])
        if external and not e.get("hybrid") and e["id"] not in NON_HERBAL_EXTERNAL:
            stray.append(e["id"])
        if e["id"] in NON_HERBAL_EXTERNAL and (e.get("hybrid") or not external):
            stale.append(e["id"])
    assert stray == [], f"external effects on non-hybrid entries: {stray}"
    assert stale == [], f"stale non-herbal exemptions: {stale}"


def test_monster_parts_are_hybrid():
    """A monster part is on both shelves: the owner names Basilisk Eye and Phoenix
    Feather as the type case. 20 monster parts ship; an untagged one would vanish from
    the alchemist's bench."""
    bad = [e["id"] for e in _raw() if e["kind"] == "monster part" and not e.get("hybrid")]
    assert bad == []


def test_bark_sap_and_resin_are_salve_bases():
    """The owner's rule: "grinding of any bark and tree sap makes a base for salves".
    A bark entry without `base_for` cannot thicken a salve, and a salve with no base is
    refused, so a player holding Leechwort bark would be told they have nothing to make
    one with."""
    missing = [e["id"] for e in _raw()
               if e.get("part") in ("bark", "sap", "resin")
               and "salve" not in (e.get("base_for") or [])
               and e["id"] not in NOT_A_SALVE_BASE]
    assert missing == [], f"bark, sap or resin with no salve base: {missing}"
    by_id = {e["id"]: e for e in _raw()}
    stale = [i for i in NOT_A_SALVE_BASE
             if i not in by_id or by_id[i].get("part") not in ("sap", "resin", "bark")]
    assert stale == [], f"stale exemptions: {stale}"


def test_every_tag_survives_the_load():
    """`from_dict` builds the Ingredient and drops every key without a field. That is how
    the preparation tags for 55 ingredients once loaded, merged and vanished. Each new
    field is compared between the file and the built object."""
    built = ing.all_ingredients()
    for e in _raw():
        got = built[e["id"]]
        assert got.part == e["part"], e["id"]
        assert got.hybrid == bool(e.get("hybrid")), e["id"]
        assert got.base_for == list(e.get("base_for") or []), e["id"]
        assert got.routes == [f["route"] for f in e.get("effects") or []], e["id"]


def test_the_bench_reagents_are_reachable_through_ingredients():
    """Infuse needs oil, Steep needs alcohol or vinegar, a salve needs a base, and
    Neutralize spends a neutralizer. Before this pass the herbalist's shelf held none of
    them: the only oil, spirits, vinegar and wax were alchemist materials the herbalist
    module never read, so every one of those methods had nothing to work with."""
    shelf = ing.reagents()
    solvents = {r.solvent for r in shelf.values()}
    assert {"oil", "alcohol", "vinegar"} <= solvents, solvents
    assert any(r.part == "wax" and "salve" in r.base_for for r in shelf.values())
    assert any(r.neutralizer >= 1 for r in shelf.values())
    for rid, r in shelf.items():
        assert ing.get(rid) is r, rid
        assert ing.reagent_named(r.name) is r, rid
        assert r.part in ing.PARTS, rid
        assert not r.forageable, rid
        if r.solvent:
            assert r.solvent in ing.SOLVENTS and r.liquid, rid
        assert set(r.base_for) <= set(ing.BASE_FORMS), rid


def test_reagents_are_not_herbs():
    """The reagents live on the materials shelf, not in the herb corpus. Merged into
    `all_ingredients()` they would turn up in foraging, in the herbarium's count and as a
    scheme's random gift ("a jar of vinegar, found growing in the marsh")."""
    herbs = ing.all_ingredients()
    assert not set(ing.reagents()) & set(herbs)
    assert all(i.kind != "reagent" for i in herbs.values())


def test_reagents_are_for_sale_where_alchemy_is():
    """A reagent nobody can buy is a method nobody can use. The alchemist's counter draws
    every priced, bought material for "alchemist" and "herbalist"
    (content/rules/stall-lines.json); each reagent must be in that pool."""
    from rules import market

    pool = {str(getattr(m, "id", "")) for m in market.priced_from(("alchemist", "herbalist"))}
    missing = sorted(set(ing.reagents()) - pool)
    assert missing == [], f"reagents no counter sells: {missing}"


def test_an_old_save_loads_with_the_defaults():
    """An ingredient written before these fields existed must come out as the bench saw
    it then: a swallowed leaf (or organ, or fungus), no base, no solvent, no
    neutralizer, herbal only. The homebrew editor writes strings, so "yes", "2" and a
    comma list are read too."""
    old = ing.from_dict({"id": "x", "name": "X", "effects": [{"type": "heal", "dice": "1"}]})
    assert (old.part, old.base_for, old.neutralizer, old.solvent, old.hybrid) == \
        ("leaf", [], 0, "", False)
    assert old.routes == ["ingest"]
    assert ing.from_dict({"id": "y", "name": "Y", "kind": "monster part"}).part == "organ"
    assert ing.from_dict({"id": "z", "name": "Z", "kind": "fungus"}).part == "fungus"

    edited = ing.from_dict({"id": "w", "name": "W", "hybrid": "yes", "neutralizer": "2",
                            "base_for": "salve, balm", "solvent": " Oil "})
    assert (edited.hybrid, edited.neutralizer, edited.base_for, edited.solvent) == \
        (True, 2, ["salve", "balm"], "oil")
    assert ing.from_dict({"id": "v", "name": "V", "hybrid": "no"}).hybrid is False


def test_an_unknown_route_is_treated_as_external():
    """A typo must close, not open. "skn" read as the default `ingest` would put an
    effect on the herbalist's bench that nobody decided belonged there; read as
    `external`, the shelf card says "alchemy only" and someone fixes the typo."""
    assert ing.route_of({}) == "ingest"
    assert ing.route_of({"route": "Skin"}) == "skin"
    assert ing.route_of({"route": "skn"}) == "external"


def test_as_dict_carries_the_new_fields_round_trip():
    """The editor and the API read `as_dict`. A field it leaves out is a field the page
    cannot show and a save cannot write back."""
    comfrey = ing.get("comfrey")
    again = ing.from_dict(comfrey.as_dict())
    for name in ("part", "base_for", "neutralizer", "solvent", "hybrid", "routes"):
        assert getattr(again, name) == getattr(comfrey, name), name

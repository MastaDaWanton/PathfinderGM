"""A product is used where its effects are tagged to work: the Use button's places.

The owner, 2026-10-02: "build a use button for products that lets you choose based on
the ingredient/products tagged places eyes/wounds/ingest". Measured before this file:
Drink was the only way to use a salve, and drinking one landed EVERY effect it carried,
the eye-salve's sight and the wound-closing alike, because the jar door ignored the
`route` every herbal effect carries (docs/herbalism-contracts.md §2).
"""
from __future__ import annotations

from rules import consumables
from rules.crafting import Stock
from rules.dice import Dice
from rules.engine import Engine, Scene
from rules.sheet import load_pc

EYE_SALVE = [
    {"type": "skill_mod", "target": "perception", "amount": 2, "bonus_type": "alchemical",
     "duration": {"amount": 1, "unit": "hour"}, "route": "eyes"},
    {"type": "heal", "amount": 3, "route": "wound"},
]


def _board(specs, form=None):
    s = Scene(location_id="5bbd0c40345f")
    s.add(load_pc("fixtures/pc-kesst.json"))
    engine = Engine(s, Dice(seed=5))
    s.pc().stock["jar#1"] = Stock(base="Salve", count=2, effects=["x"], specs=specs,
                                  **({"form": form} if form else {}))
    return s, engine


def _use(engine, how, route="", to="pc"):
    params = {"item": "jar#1", "how": how, "to": to, **({"route": route} if route else {})}
    return engine.run(engine.validate([
        {"op": "use_item", "actor": "pc", "params": params}])).outcomes[0]


def test_on_the_eyes_only_what_works_in_the_eyes_lands():
    """The eye salve on the eyes gives the Perception bonus and heals nothing: the heal
    is tagged to a wound."""
    scene, engine = _board(EYE_SALVE)
    pc = scene.pc()
    pc.hp = pc.hp_max - 5
    out = _use(engine, "apply", "eyes")
    assert pc.hp == pc.hp_max - 5
    assert any(getattr(e, "kind", "") == "buff" for e in pc.effects), out.tell
    assert "eyes" in out.tell


def test_on_a_wound_only_the_wound_effect_lands():
    scene, engine = _board(EYE_SALVE)
    pc = scene.pc()
    pc.hp = pc.hp_max - 5
    _use(engine, "apply", "wound")
    assert pc.hp == pc.hp_max - 2
    assert not any(getattr(e, "kind", "") == "buff" for e in pc.effects)


def test_drinking_a_salve_is_refused_with_where_it_does_work():
    """Drink is the swallowed route. A salve has nothing that works swallowed, so drinking
    it is refused at validation (the planner's retry gets the reason) naming the places it
    does work, and no dose is spent."""
    import pytest
    from rules.intents import IntentError

    scene, engine = _board(EYE_SALVE)
    with pytest.raises(IntentError) as caught:
        _use(engine, "drink")
    said = str(caught.value)
    assert "nothing in" in said and "on the eyes" in said and "on a wound" in said
    assert scene.pc().stock["jar#1"].count == 2


def test_a_form_that_cannot_carry_a_place_does_not_offer_it():
    """A tincture is drops on the tongue (herbal-products.json routes: ingest), so even
    an eye effect in it is not offered on the eyes: the form decides the places."""
    tincture = Stock(base="Tincture", count=1, form="tincture", specs=[
        {"type": "heal", "amount": 2, "route": "ingest"},
        {"type": "skill_mod", "target": "perception", "amount": 1, "route": "eyes",
         "duration": {"amount": 1, "unit": "hour"}}])
    assert consumables.routes_of(tincture) == ["ingest"]


def test_a_jar_from_before_routes_drinks_exactly_as_it_did():
    """No route reads as swallowed, so every jar made before routes existed (and every
    alchemist's potion) still drinks with all its effects."""
    scene, engine = _board([{"type": "heal", "amount": 4}])
    pc = scene.pc()
    pc.hp = pc.hp_max - 6
    _use(engine, "drink")
    assert pc.hp == pc.hp_max - 2


def test_a_poultice_goes_on_somebody_else_and_the_tell_says_whose_wound():
    """Treating another person close by (the Project Zomboid health panel's shape): the
    heal lands on them, the dose is the user's, and the tell names whose wound it was."""
    from rules.bestiary import instantiate

    scene, engine = _board([])
    pc = scene.pc()
    other = scene.add(instantiate("thug", scene=scene, name="Bob"))
    other.hp = max(1, other.hp_max - 5)
    before = other.hp
    pc.stock["jar#1"] = Stock(base="Poultice", count=1, effects=["x"],
                              specs=[{"type": "heal", "amount": 3, "route": "wound"}])
    out = _use(engine, "apply", "wound", to=other.ref)
    assert other.hp == min(other.hp_max, before + 3)
    assert f"{other.name}'s wound" in out.tell


def test_the_sheet_offers_use_with_only_the_places_it_works(tmp_path):
    """The Equipment row's Use carries the menu the page draws: one entry per place this
    jar works, with what it does there, and the people it can go on. An eye salve offers
    the eyes and a wound and no Drink, because nothing in it works swallowed."""
    from django.test import Client, override_settings

    from play import campaign as cm
    from play import views

    with override_settings(CAMPAIGN_DIR=tmp_path / "campaigns"):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        c.scene.pc().stock["jar#1"] = Stock(base="Eye Salve", count=1, effects=["x"],
                                            specs=EYE_SALVE)
        c.save()
        rows = Client().get("/api/sheet").json()["equipment"]["carried"]
        cm._LIVE.clear()
    row = next(r for r in rows if r.get("name") == "Eye Salve")
    labels = [a["label"] for a in row["acts"]]
    assert "Use" in labels and "Drink" not in labels
    use = next(a for a in row["acts"] if a["label"] == "Use")
    assert [m["route"] for m in use["menu"]] == ["eyes", "wound"]
    assert use["menu"][0]["body"] == {"item": row["key"], "how": "apply", "route": "eyes"}
    assert "Perception" in use["menu"][0]["line"]
    assert use["targets"][0] == {"ref": "pc", "name": "Yourself"}

"""Every harvested material has a shipped creature it comes off, or is named here.

Option D (2026-10-29) took 5,545 rows out of the bestiary, and with them the only bodies
some carcass parts came off. Measured 2026-10-30 (review of 0.2.23): `glowlizard-hide`'s one
source was an adventure's Glowlizard, and the white dragon ichor's were four adventures'
named white dragons — no shipped creature carries either now, by tag (tools/harvest_tags.py)
or by name. Thirteen `from_creatures` fragments that matched a 0.2.22 block match nothing
shipped (black bear, boreal wolf, deer, dire stag, cave bear, sabre-tooth, snow leopard,
noble salamander, glowlizard, adder, bull, fire drake); every one of those materials but
the glowlizard hide still has a live source by another fragment or tag, and a fragment is
still read against a World Bible world's own creatures by name, so none is deleted.

This pins the list: a material that loses its last shipped source fails here, by name, so
it is a decision and not a silent loss. The open ones are the owner's call — a shipped
creature to carry them, a price on a shelf, or the World Bible creature that supplies them.
"""
from __future__ import annotations

import sys
from pathlib import Path

from django.conf import settings

# Made by rule, not off a named creature: the generic hides by type, sinew, gut and
# horsehair cords, tallow, brain paste, neatsfoot oil, bone chalk and the storm heart
# (rules/harvest.py `GENERIC`, `PLAIN_SINEW`; the generic rule by creature type).
BY_RULE = {"bone-chalk", "brain-paste", "currier-tallow", "generic-chitin",
           "generic-feather-hide", "generic-fur-hide", "generic-scale-hide", "generic-shell",
           "generic-smooth-hide", "gut-cord", "horsehair-cord", "neatsfoot-oil",
           "sinew-thread", "storm-heart"}

# No shipped creature, measured 2026-10-30. The first three had none at 0.2.22 either
# (no shipped great wyrm, frost worm, greasefish or giant eel); the last two lost theirs to
# option D.
OPEN = {"dragon-heart-blood", "frostworm-chill-gland", "slick-jelly",
        "glowlizard-hide", "white-dragon-ichor"}


def _sourceless() -> set[str]:
    sys.path.insert(0, str(Path(settings.BASE_DIR) / "tools"))
    import harvest_tags as ht

    from rules import bestiary, materials

    store = bestiary.imported()
    tagged = {str(t).split(".")[-1] for b in store.values() for t in b.get("tags") or ()
              if str(t).startswith("harvest.")}
    names = [ht._words(b.get("name")) for b in store.values()]
    out = set()
    for mid, doc in materials.all().items():
        if doc.get("obtain") != "harvested" or mid in tagged:
            continue
        frags = [str(f).lower() for f in doc.get("from_creatures") or []]
        if not any(ht._has_phrase(n, f) for f in frags for n in names):
            out.add(mid)
    return out


def test_no_harvested_material_loses_its_last_source_unnamed():
    got = _sourceless()
    new = got - BY_RULE - OPEN
    assert not new, f"harvested materials with no shipped source: {sorted(new)}"
    healed = OPEN - got
    assert not healed, f"these have a source now; take them off OPEN: {sorted(healed)}"

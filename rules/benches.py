"""One table, five crafts.

Every track module — `crafting` for herbalism, then `blacksmith`, `leatherworker`,
`alchemist` and `enchanter` — answers to the world class's own id. This is the table
that maps one to the other, so the acquisition hub, the market and the shelves can ask
"whose materials are these" without an `if herbalism` growing a branch per craft, and a
sixth craft is a module plus one line here rather than an edit to every view.

It used to route the old /craft/ page's chains as well (`chain_from_body`, `preview`,
`result_field`, the `MOVED` refusals and the enchanter's "By the book" mode). Every craft
moved to its own step bench at the table between 2026-10-02 and 2026-10-08, the page's
tabs became doors, and the routes those chains served were deleted on 2026-11-08 (audit
finding #20): nothing a player could click reached them, and the forge's chain skipped
rent and let natural 1s and 20s decide, against the live forge's rule.
"""
from __future__ import annotations

from importlib import import_module

# Track id -> module path. The id is the world class's own id, so a bench, a character's
# progress and the routing table all agree on one spelling.
BENCHES: dict[str, str] = {
    "herbalist": "rules.crafting",
    "blacksmith": "rules.blacksmith",
    "leatherworker": "rules.leatherworker",
    "alchemist": "rules.alchemist",
    "enchanter": "rules.enchanter",
}


class UnknownBench(KeyError):
    pass


def module_for(track_id: str):
    """The module that owns this craft's materials and checks."""
    key = (track_id or "").strip().lower()
    path = BENCHES.get(key)
    if path is None:
        raise UnknownBench(
            f"no bench for {track_id!r}. Known: {', '.join(sorted(BENCHES))}")
    return import_module(path)


def glyphs() -> dict[str, dict[str, str]]:
    """Every craft's material icons, keyed by track.

    Herbalism's live here because its shelf reads the ingredient corpus rather than a
    materials module; the other four export their own, so a craft that invents a new
    kind of material gets an icon by editing its own file.
    """
    out: dict[str, dict[str, str]] = {
        # The original four, from the herb corpus.
        "herbalist": {"herb": "🌿", "fungus": "🍄", "monster part": "🦴",
                      "poison": "☠️",
                      # Oil, spirits, vinegar, beeswax and the neutralizers (Lane A,
                      # content/materials, kind "reagent").
                      "reagent": "🫗"},
    }
    for track in BENCHES:
        if track == "herbalist":
            continue
        try:
            mod = import_module(BENCHES[track])
        except ImportError:                    # pragma: no cover - guard
            continue
        got = getattr(mod, "KIND_GLYPH", None)
        if isinstance(got, dict):
            out[track] = dict(got)
    return out


# A glyph for every station, per craft. Materials got their icons from each craft's own
# module; methods did not, so every forge, tannery, laboratory and circle station on the
# bench rendered as the fallback crate — eleven identical boxes where the herb bench has
# a still, a mortar and a teapot. Kept here rather than in four modules because a method
# name is the bench's vocabulary and this is the bench's routing table; a craft that
# wants to override declares its own `METHOD_GLYPH` and it wins.
METHOD_GLYPHS: dict[str, dict[str, str]] = {
    "herbalist": {
        "grind": "⚗️", "mix": "🥣", "brew": "🫖", "extract": "🔪",
        "infuse": "✨", "neutralize": "🧪",
        # The step bench's new methods (docs/herbalism-revamp-plan.md §6). Preserve,
        # distill, purify, refine and catalyst crafting were retired on 2026-10-02 and
        # left the Herbalist document, so their glyphs went with them.
        "dry": "🌾", "reduce": "♨️", "steep": "🍶",
    },
    "blacksmith": {
        "smelt": "🔥", "forge": "🔨", "quench": "💧", "flux": "🧱", "rivet": "🔩",
        "alloy": "⚗️", "temper": "🌡️", "draw": "🧲", "fold": "📐", "hone": "🪒",
        "polish": "✨",
    },
    "leatherworker": {
        "skin": "🔪", "flense": "🪒", "cure": "🧂", "tan": "🛢️", "oil": "🧴",
        "dye": "🎨", "cut": "✂️", "tool": "🖋️", "stitch": "🧵", "harden": "🔥",
        "line": "🧶",
    },
    # The alchemy revamp's nine (2026-10-06); `rules.alchemist.METHOD_GLYPH` is the
    # module's own map and wins. Seal became Bottle; precipitate, stabilize and catalyze
    # left the track, so their glyphs went with them.
    "alchemist": {
        "dissolve": "💧", "calcine": "🔥", "filter": "🧫", "distill": "⚗️",
        "react": "💥", "sublime": "☁️", "bottle": "🧴", "transmute": "🜍",
        "assay": "🔍",
    },
    # The circle's eight (enchanting revamp, 2026-10-05). The new bench draws icon masks
    # (UI plan §4); these serve only the old /craft/ page's station chips.
    "enchanter": {
        "prepare": "🖋️", "attune": "🧿", "bind": "🔗", "refine": "⚗️", "unbind": "⛓️",
        "cleanse": "☀️", "read": "👁️", "identify": "🔍",
    },
}


def method_glyphs(track_id: str) -> dict[str, str]:
    """The station icons for one craft. A module's own map wins over the table above."""
    key = (track_id or "").strip().lower()
    try:
        mod = module_for(key)
    except UnknownBench:
        return dict(METHOD_GLYPHS.get(key, {}))
    own = getattr(mod, "METHOD_GLYPH", None)
    if isinstance(own, dict) and own:
        return dict(own)
    return dict(METHOD_GLYPHS.get(key, {}))


def acquisitions() -> list[dict]:
    """Every excursion every craft offers, each tagged with the track that owns it.

    The craft-action button on the play page is the one hub for *getting* materials —
    "craft action should be the hub for mining, skinning, etc... all the actions that
    obtain world class materials/reagents" — so it needs one list rather than five
    imports. Each craft declares its own; the hub only sorts and asks what is possible
    here, which keeps "where does dragonfire coal come from" an answer in the
    blacksmith's own file.
    """
    out: list[dict] = []
    for track, path in BENCHES.items():
        try:
            mod = import_module(path)
        except ImportError:                    # pragma: no cover - guard
            continue
        table = getattr(mod, "ACQUISITION", None)
        # A dict keyed by id, or a plain list of specs that already carry one. The
        # enchanter writes the list form, and requiring a dict here dropped all five of
        # its methods on the floor without a word: skimming essence, cutting foci,
        # harvesting the slain, buying inks and commissioning a vessel were absent from
        # the craft hub entirely, which left an enchanter with no way to obtain a single
        # material through the interface.
        if isinstance(table, dict):
            items = list(table.items())
        elif isinstance(table, (list, tuple)):
            items = [(str(s.get("id") or ""), s) for s in table if isinstance(s, dict)]
        else:
            continue
        for key, spec in items:
            entry = {"track": track, "id": str(spec.get("id") or key)}
            entry.update({k: v for k, v in spec.items() if k != "id"})
            entry["requires"] = gate_of(spec)
            # Namespaced, because two crafts may both offer "gather" and the hub has to
            # know whose gathering it is running.
            entry["key"] = f"{track}:{entry['id']}"
            out.append(entry)
    return sorted(out, key=lambda e: (e["track"], e["id"]))


# What an excursion needs before it can be run at all. The hub asks one question and the
# benches answered it in three vocabularies: blacksmith and leatherworker write
# `"requires": "biome"`, the alchemist writes `"needs": "biome"`, and the enchanter writes
# `"needs": {"biome": True}`. Only the first was ever read, so every alchemist and
# enchanter method came back ungated — "Mine salts and ores" was offered on a city street
# while the blacksmith's "Prospect for ore" was correctly greyed out beside it, and
# alchemist gathering skipped the "leave the scene first" rule the other tracks obey.
_GATES = ("carcass", "creature", "biome", "market")


def gate_of(spec: dict) -> str:
    """The one gate this excursion needs, whichever way its bench spelled it."""
    raw = spec.get("requires", spec.get("needs", ""))
    if isinstance(raw, dict):
        # `{"market": True, "craft": (...)}` — the craft half is an extra condition the
        # bench checks for itself; the gate is the one the hub knows how to test.
        for g in _GATES:
            if raw.get(g):
                return g
        return ""
    text = str(raw or "").strip().lower()
    return text if text in _GATES else ""


def obtainable(track: str, obtain_kind: str, *, biome=None, creature=None) -> list:
    """What one craft's excursion could turn up here. [] if it does not offer one."""
    try:
        mod = module_for(track)
    except UnknownBench:
        return []
    fn = getattr(mod, "obtainable", None)
    if fn is None:
        return []
    return list(fn(obtain_kind, biome=biome, creature=creature))

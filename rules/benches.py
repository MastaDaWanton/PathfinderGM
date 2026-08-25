"""One interface, five crafts.

Every track module — `crafting` for herbalism, then `blacksmith`, `leatherworker`,
`alchemist`, `enchanter` and the enchanter's second, book-faithful `magicitem` mode —
was written to the same public surface on purpose: `TRACK_ID`, `CraftError`, `Chain`,
`chain_from_body`, `preview` returning problems before anything is rolled, and a
`Result` whose `as_dict` carries the same keys. Each of the four books says the same
thing in its integration notes: *the routing table does not exist yet*.

This is that table. It exists so the bench view can say "preview this chain" without an
`if herbalism` growing a branch per craft, and so a sixth craft is a module plus one
line here rather than an edit to every view.

Two deliberate accommodations, both because uniformity was asked of modules that were
written in parallel by different hands:

  Optional fields are read with `getattr` and a default. Herbalism's `Result` carries
  `concentrating` and `consumes_raw` because two doses make one of the next band; a
  forge has no such notion, and demanding the field of it would be the routing table
  dictating semantics to the crafts rather than serving them.

  Extra keyword arguments are filtered against each `preview`'s real signature. The
  herbalist's pot cares what the world clock says (hides and herbs spoil); a binding
  circle cares whether it is night; a forge cares about neither. Passing everything to
  everyone would make each module carry parameters it has no use for.
"""
from __future__ import annotations

import inspect
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

# Modes that sit beside a track rather than being one: the enchanter's second tab is
# Pathfinder's own magic-item creation, running on the same world class and level but a
# different rulebook. Keyed by mode id, valued by (track it belongs to, module).
MODES: dict[str, tuple[str, str]] = {
    "magic-item": ("enchanter", "rules.magicitem"),
}


class UnknownBench(KeyError):
    pass


def module_for(track_id: str, mode: str = ""):
    """The module that owns this bench. `mode` selects a secondary tab if there is one.

    A mode whose module has not been written yet raises `UnknownBench` rather than
    ImportError, so a half-built tab is refused the same way an unknown one is instead
    of 500ing at the player.
    """
    key = (track_id or "").strip().lower()
    if mode:
        found = MODES.get(mode.strip().lower())
        if not found or found[0] != key:
            raise UnknownBench(f"no {mode!r} bench for {track_id!r}")
        try:
            return import_module(found[1])
        except ImportError as exc:            # pragma: no cover - guard, not a path
            raise UnknownBench(f"{mode!r} is declared but not built: {exc}") from exc
    path = BENCHES.get(key)
    if path is None:
        raise UnknownBench(
            f"no bench for {track_id!r}. Known: {', '.join(sorted(BENCHES))}")
    return import_module(path)


def modes_for(track_id: str) -> list[dict]:
    """The secondary tabs this track offers, for the page to draw."""
    key = (track_id or "").strip().lower()
    out = []
    for mode_id, (owner, path) in MODES.items():
        if owner != key:
            continue
        try:
            mod = import_module(path)
        except ImportError:
            continue
        out.append({"id": mode_id,
                    "name": getattr(mod, "MODE_NAME", mode_id.replace("-", " ").title()),
                    "blurb": getattr(mod, "MODE_BLURB", "")})
    return out


def supports(track_id: str, mode: str = "") -> bool:
    """Whether this bench can actually preview a chain yet.

    Asked before the page offers a craft button, because "the module exists" and "the
    module can take a chain" were briefly different things while the five were being
    written, and a button that 500s is worse than one that is honestly greyed.
    """
    try:
        mod = module_for(track_id, mode)
    except UnknownBench:
        return False
    return hasattr(mod, "preview") and hasattr(mod, "chain_from_body")


# What is being made, as each bench happens to spell it. The forge reads `base` or
# `item`, the tannery `product` or `pattern`, the enchanter `item`, herbalism `base` —
# four benches, four vocabularies for one question, which is the same drift that left
# `requires` and `needs` disagreeing about excursion gates.
#
# The page copes by sending the value under all four names at once. That works and is
# one bench away from not working, and it means anything else driving these endpoints —
# a test, a tool, a future mobile client — has to know the whole list. Normalised here
# instead, so a bench may keep its own word and callers only need one.
SHAPE_ALIASES = ("base", "item", "product", "pattern", "shape", "shaping", "base_item")


def shape_of(body: dict) -> str:
    """The thing being made, whichever of its names the caller used."""
    for key in SHAPE_ALIASES:
        said = str((body or {}).get(key) or "").strip()
        if said:
            return said
    return ""


def with_shape(body: dict) -> dict:
    """The body with every alias filled in, so each bench finds its own spelling."""
    said = shape_of(body)
    if not said:
        return dict(body or {})
    return dict(body or {}, **{k: said for k in SHAPE_ALIASES})


def chain_from_body(track_id: str, body: dict, mode: str = ""):
    mod = module_for(track_id, mode)
    if hasattr(mod, "chain_from_body"):
        return mod.chain_from_body(with_shape(body))
    raise UnknownBench(f"{track_id} cannot read a chain from the bench yet")


def preview(track_id: str, level: int, chain, mode: str = "", **kw):
    """Preview a chain at whichever bench owns it.

    Keyword arguments are filtered to what this module's `preview` actually accepts —
    see the module docstring. `track_id` is passed positionally only to herbalism,
    whose signature predates the table and takes it first.
    """
    mod = module_for(track_id, mode)
    fn = mod.preview
    params = inspect.signature(fn).parameters
    passable = {k: v for k, v in kw.items() if k in params}
    if "track_id" in params:                       # rules.crafting.preview
        return fn(track_id, level, chain, **passable)
    return fn(level, chain, **passable)


def result_field(result, name: str, default=None):
    """One field off any craft's Result, present or not.

    The bench reads eight fields off a Result and only six are universal. Rather than
    make every module declare a `concentrating` it has no opinion about, the reader
    supplies the default — the routing table accommodating the crafts, not the reverse.
    """
    return getattr(result, name, default)


def glyphs() -> dict[str, dict[str, str]]:
    """Every craft's material icons, keyed by track.

    Herbalism's live here because its shelf reads the ingredient corpus rather than a
    materials module; the other four export their own, so a craft that invents a new
    kind of material gets an icon by editing its own file.
    """
    out: dict[str, dict[str, str]] = {
        # The original four, from the herb corpus.
        "herbalist": {"herb": "🌿", "fungus": "🍄", "monster part": "🦴",
                      "poison": "☠️"},
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
        "grind": "⚗️", "mix": "🥣", "brew": "🫖", "preserve": "🧊", "extract": "🔪",
        "distill": "⚱️", "purify": "💧", "infuse": "✨", "neutralize": "🧪",
        "refine": "💎", "catalyst crafting": "🌟",
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
    "alchemist": {
        "calcine": "🔥", "dissolve": "💧", "filter": "🧫", "precipitate": "🧂",
        "react": "💥", "stabilize": "⚖️", "sublime": "☁️", "catalyze": "💠",
        "seal": "🧴",
    },
    "enchanter": {
        "attune": "🧿", "scribe": "🖋️", "bind": "🔗", "seal": "📿", "focus": "💎",
        "channel": "⚡", "imbue": "✨", "empower": "⭐", "awaken": "👁️",
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

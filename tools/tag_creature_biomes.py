"""Give every creature and NPC the ground it lives on.

The two halves of the bestiary know different things. The 782 stat blocks parsed out of the
printed Bestiaries carry an **Environment** line — "warm deserts", "any underground",
"cold mountains" — and the 6,406 from the variant and NPC spreadsheet carry nothing at all:
the column exists and is empty in every row. So a swamp encounter could be built from a
tenth of the book and the rest was unreachable.

This is a mechanical pass, deliberately. No model is asked where a hobgoblin lives: the
prose is parsed by `rules/biomes.parse_environment`, and the 6,406 that have no prose are
tagged from what they *do* carry, by four routes each weaker than the one before — an exact
name in the printed Bestiary, a species inside a longer name ("Frost Giant Battle Priest"),
a subtype, the creature type, and failing all of those, "any land".

The type and subtype tables are not written here. They are **derived from core.json**, the
one source that has both a type and a habitat, so the claim "a giant lives in mountains" is
a count over the twenty-four giants the book printed rather than something plausible that
somebody typed. What is written here is only the list of subtypes that describe how a
creature works rather than where it lives — `incorporeal`, `swarm`, `shapechanger` — because
that is a fact about the rules and not a habitat anybody could count.

Everything a creature did not state itself is flagged `biomes_inferred`, exactly as
ingredients are, and `biomes_from` records which route produced it, so the weakest ones
can be counted and doubted on their own rather than hidden inside a single bit.

Run:  python tools/tag_creature_biomes.py
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rules import biomes  # noqa: E402

HERE = Path(__file__).resolve().parent.parent
CORE = HERE / "content" / "bestiary" / "core.json"
SPREAD = HERE / "content" / "bestiary" / "creatures.json"

# core.json's Type column came out of a PDF and was split on whitespace, so it says
# "magical" where the spreadsheet says "magical beast" and "construc" where it means
# construct. Joining the two files on the raw string silently loses 162 creatures — the
# whole of magical beast and monstrous humanoid — and nothing reports it.
_CORE_TYPE_FIX = {
    "magical": "magical beast",
    "monstrous": "monstrous humanoid",
    "construc": "construct",
}

# The spreadsheet's own drift, in the other direction: a handful of rows carry a template
# or a companion level in the Type column.
_SPREAD_TYPE_FIX = {
    "outsider familiar": "outsider",
    "elemental": "outsider",          # core files elementals as outsiders with a subtype
}

# Subtypes that say how a creature works rather than where it lives, plus the ones that
# only echo the creature type and so should be answered by the type instead. Derived
# profiles for the first group are noise: the eight incorporeal core creatures with a
# specific habitat are half coastal by accident of which four the book printed, which
# would have filed every ghost in the spreadsheet on a beach.
MECHANICAL_SUBTYPES = {
    "incorporeal", "shapechanger", "swarm", "mythic", "mythicma", "troop", "augmented",
    "good", "evil", "lawful", "chaotic", "colossus", "blight", "phantom", "changeling",
    "animal", "plant", "dragon", "humanoid", "outsider", "fungus",
}

# A biome joins a group's profile when a third of the group's members that named a habitat
# at all live there. Below that it is one or two creatures out of twenty and the profile
# stops meaning anything.
_BIOME_FLOOR = 0.34
# ...and a group needs four such members before it votes. Three was enough to give
# `reptilian` an underground-only profile off the back of two kobolds.
_MIN_SPECIFIC = 4
# Climate is rarer and blunter: it is carried only when half the whole group agrees, so
# `cold` (nine core creatures, all of them arctic) survives and nothing else does.
_CLIMATE_FLOOR = 0.5
# A group that mostly says "any" has no habitat to derive, and the handful of members that
# do name one are not evidence about the rest. Measured: 52 core constructs, 47 of them
# "any", and the five left over voted the whole type into swamps — which would have put all
# 217 spreadsheet golems, robots and animated objects in a bog.
_ANY_CEILING = 0.5

# Core names that are ordinary English before they are creatures. Measured on the word
# match below: `gray` caught eleven rows on the title in "Gilgar the Gray", and `fallen`
# five on "Fallen Mercenary". Neither is the Bestiary creature of that name.
_NAME_TITLES = {"gray", "fallen"}


def tokens(raw: str) -> list[str]:
    return [t.strip() for t in (raw or "").split(",") if t.strip()]


def core_type(c: dict) -> str:
    t = (c.get("creature_type") or "").strip().lower()
    return _CORE_TYPE_FIX.get(t, t)


def spread_type(c: dict) -> str:
    t = (c.get("creature_type") or "").strip().lower()
    if t.startswith("animal companion"):
        return "animal"
    for prefix in ("advanced ", "augmented "):
        if t.startswith(prefix):
            t = t[len(prefix):]
    return _SPREAD_TYPE_FIX.get(t, t)


def spread_subtypes(c: dict) -> list[str]:
    """Subtype tokens, with the spreadsheet's `augmented x` prefixes taken off.

    164 rows read "augmented humanoid" — a template applied to a person, not a habitat.
    The prefix is stripped so `augmented human` still reaches the human rules, and the bare
    word `augmented` is in the mechanical list so it never votes on its own.
    """
    out = []
    for t in tokens(c.get("subtype")):
        if t.startswith("augmented "):
            t = t[len("augmented "):]
        out.append(t)
    return out


def build_profiles(core: list[dict]) -> dict[tuple[str, str], tuple[list[str], list[str]]]:
    """What core.json's own creatures say about each type and subtype.

    Only the creatures that named a habitat vote on biomes: a group whose members mostly
    say "any" has no habitat of its own, and counting the expansion would hand every group
    all thirteen biomes and call it evidence.
    """
    groups: dict[tuple[str, str], list[biomes.Environment]] = collections.defaultdict(list)
    for c in core:
        env = biomes.parse_environment(c.get("environment") or "")
        if not env.biomes:
            continue
        groups[("type", core_type(c))].append(env)
        for t in tokens(c.get("subtype")):
            if t not in MECHANICAL_SUBTYPES:
                groups[("sub", t)].append(env)

    out: dict[tuple[str, str], tuple[list[str], list[str]]] = {}
    for key, entries in groups.items():
        specific = [e for e in entries if not e.unrestricted]
        found: list[str] = []
        if (len(specific) >= _MIN_SPECIFIC
                and (len(entries) - len(specific)) / len(entries) < _ANY_CEILING):
            counts = collections.Counter(b for e in specific for b in e.biomes)
            found = [b for b in biomes.BIOMES
                     if counts[b] / len(specific) >= _BIOME_FLOOR]
        climates = collections.Counter(cl for e in entries for cl in e.climates)
        kept = [c for c in biomes.CLIMATES
                if climates[c] / len(entries) >= _CLIMATE_FLOOR]
        if found:
            out[key] = (found, kept)
    return out


def tag_core(core: list[dict]) -> collections.Counter:
    """Every core creature, from its own Environment line."""
    counts: collections.Counter = collections.Counter()
    for c in core:
        env = biomes.parse_environment(c.get("environment") or "")
        c["biomes"] = env.biomes
        c["climates"] = env.climates
        c["biomes_any"] = env.unrestricted
        # False, and only here: this is the one source that stated it. Everything below
        # this line is a guess and says so. It stays False for the one stat block whose
        # Environment line is blank, because nothing was guessed for it either — it is
        # untagged, which the empty list and the empty `biomes_from` both say.
        c["biomes_inferred"] = False
        c["biomes_from"] = "environment" if env.biomes else ""
        counts["environment" if env.biomes else "none"] += 1
    return counts


def uninvert(name: str) -> str:
    """"Giant, Frost" -> "frost giant".

    The printed Bestiary indexes by species and the spreadsheet writes plainly, so the two
    files spell the same creature two ways. Without this, every one of the 226 giants in
    the spreadsheet misses the giant that was printed.
    """
    parts = [p.strip() for p in name.split(",")]
    return (f"{parts[1]} {parts[0]}" if len(parts) == 2 else name).lower()


def name_forms(core: list[dict]) -> dict[str, dict]:
    """Every spelling of a core creature's name that is worth matching on."""
    out: dict[str, dict] = {}
    for c in core:
        if not c.get("biomes"):
            continue
        for form in {c["name"].strip().lower(), uninvert(c["name"])}:
            # Four characters, because "roc" and "ape" inside a longer word or a name is
            # noise, and because nothing shorter carries a habitat worth borrowing.
            if len(form) >= 4 and form not in _NAME_TITLES:
                out.setdefault(form, c)
    return out


def longest_form(name: str, forms: dict[str, dict]) -> dict | None:
    """The longest core name that appears in this one as whole words.

    Longest first so "Fire Giant Captain" reaches the fire giant on the warm mountains
    rather than the giant profile's generic ones. Contiguous word runs rather than a regex
    over every core name: 900 patterns against 6,406 names took minutes, this takes a
    second, and it cannot match half a word.
    """
    words = re.findall(r"[a-z']+", name.lower())
    for size in range(len(words), 0, -1):
        for i in range(len(words) - size + 1):
            hit = forms.get(" ".join(words[i:i + size]))
            if hit is not None:
                return hit
    return None


def borrow(twin: dict, label: str) -> tuple[list[str], list[str], bool, str]:
    """Everything a core creature knows about its ground, copied onto another row."""
    return (list(twin["biomes"]), list(twin["climates"]),
            bool(twin["biomes_any"]), label)


def tag_spread(spread: list[dict], core: list[dict],
               profiles: dict) -> collections.Counter:
    by_name = {c["name"].strip().lower(): c for c in core}
    forms = name_forms(core)
    counts: collections.Counter = collections.Counter()

    for c in spread:
        found: list[str] = []
        climates: list[str] = []
        unrestricted = False
        route = ""

        twin = by_name.get(c["name"].strip().lower())
        if twin is not None and twin.get("biomes"):
            # The printed stat block for the same creature. Still a guess: the spreadsheet
            # row is a variant or a named NPC of that species, not the block itself.
            found, climates, unrestricted, route = borrow(twin, "name")

        if not found:
            twin = longest_form(c["name"], forms)
            if twin is not None:
                # "Hobgoblin Archer", "Frost Giant Battle Priest", "Boggard Brute" — the
                # species is in the name and the book printed its ecology. A weaker claim
                # than an exact match, and recorded as a different route so it can be
                # counted and doubted separately.
                found, climates, unrestricted, route = borrow(twin, "name-word")

        subs = spread_subtypes(c)
        native = "native" in subs and spread_type(c) == "outsider"

        if not found:
            # A native outsider lives on the Material Plane by definition, and the outsider
            # profile is `planar`. Without this the 211 native outsiders — every summoned
            # thing and half the adventure-path villains — are filed off-world.
            if native:
                found, unrestricted, route = list(biomes.LAND), True, "subtype"
            else:
                for t in subs:
                    if t in MECHANICAL_SUBTYPES:
                        continue
                    hit = profiles.get(("sub", t))
                    if hit:
                        found += [b for b in hit[0] if b not in found]
                        climates += [x for x in hit[1] if x not in climates]
                        route = "subtype"

        if not found:
            hit = profiles.get(("type", spread_type(c)))
            if hit:
                found, climates, route = list(hit[0]), list(hit[1]), "type"

        # Last, after every route, because any of them can contradict the subtype: "Mother
        # of Oblivion" is a native outsider whose name contains the core creature Oblivion,
        # whose line is "any (Negative Energy Plane)". `native` is the stronger statement,
        # so the plane comes off and what is left falls through to the floor below.
        if native and "planar" in found:
            found = [b for b in found if b != "planar"]

        if not found:
            # Nothing left to read. "Any land" rather than nothing at all, because a
            # creature with no biome is invisible to every query the tags exist for, and
            # the flag says plainly that this is the floor and not an observation.
            found, unrestricted, route = list(biomes.LAND), True, "floor"

        c["biomes"] = [b for b in biomes.BIOMES if b in found]
        c["climates"] = [x for x in biomes.CLIMATES if x in climates]
        c["biomes_any"] = unrestricted
        c["biomes_inferred"] = True
        c["biomes_from"] = route
        counts[route] += 1
    return counts


def write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    core_doc = json.loads(CORE.read_text(encoding="utf-8"))
    spread_doc = json.loads(SPREAD.read_text(encoding="utf-8"))
    core, spread = core_doc["creatures"], spread_doc["creatures"]

    core_counts = tag_core(core)
    profiles = build_profiles(core)
    spread_counts = tag_spread(spread, core, profiles)

    write(CORE, core_doc)
    write(SPREAD, spread_doc)

    print("--- profiles derived from core.json ---")
    for kind, name in sorted(profiles, key=lambda k: (k[0], k[1])):
        found, climates = profiles[(kind, name)]
        print(f"  {kind:4} {name:22} {found}"
              + (f"  climate {climates}" if climates else ""))

    print()
    print(f"core.json    {len(core)}")
    print(f"  from its own Environment line   {core_counts['environment']}")
    print(f"  no biome at all                 {core_counts['none']}")
    print()
    print(f"creatures.json  {len(spread)}")
    print(f"  from an exact name match        {spread_counts['name']}")
    print(f"  from a species in the name      {spread_counts['name-word']}")
    print(f"  from a subtype                  {spread_counts['subtype']}")
    print(f"  from the creature type alone    {spread_counts['type']}")
    print(f"  nothing to read: any land       {spread_counts['floor']}")
    print()

    both = core + spread
    print(f"whole bestiary  {len(both)}")
    print(f"  stated        {sum(1 for c in both if not c['biomes_inferred'])}")
    print(f"  inferred      {sum(1 for c in both if c['biomes_inferred'])}")
    print(f"  unrestricted  {sum(1 for c in both if c['biomes_any'])}")
    print(f"  with climate  {sum(1 for c in both if c['climates'])}")
    print(f"  no biome      {sum(1 for c in both if not c['biomes'])}")
    print()
    counts = collections.Counter(b for c in both for b in c["biomes"])
    print("biome spread:")
    for b in biomes.BIOMES:
        specific = sum(1 for c in both if b in c["biomes"] and not c["biomes_any"])
        print(f"  {counts[b]:6}  {b:12} ({specific} of them a stated habitat"
              f" rather than an expansion of 'any')")
    print()
    print("climate spread:")
    for cl in biomes.CLIMATES:
        print(f"  {sum(1 for c in both if cl in c['climates']):6}  {cl}")


if __name__ == "__main__":
    main()

"""The bestiary's harvest tags: what comes off each beast, in the one tag vocabulary.

The owner, leatherworking round 9 (Q9.2): "apply the tags to the beasts and just have a
reader in skinning to find the relevant tag with that no list is necessary." This is the
one-time data pass that applies them (docs/leatherworking-revamp-plan.md §5.3; contracts §5.1;
lane C), and `rules/harvest.py` is the reader. The grammar is docs/campaign-format.md's:

    harvest.hide.<material-id>           a named hide          (leatherworker)
    harvest.hide.generic.<surface>       a generic hide        (leatherworker)
    harvest.sinew / harvest.sinew.<id>   sinew                 (leatherworker)
    harvest.blood.<id>                   a quench blood        (the forge)
    harvest.reagent.<id>                 a gland, a humour     (alchemy)
    harvest.essence.<id>                 an ichor, an essence  (enchanting)
    harvest.part.<id>                    a monster part        (herbalism)
    harvest.plan.<plan>                  the body plan the bench's 3D hide is drawn from
    harvest.danger.<kind>                a dangerous body: poison, acid, fire, cold,
                                         electricity, sonic (docs/deeds-plan.md §13.2)

**Names are read HERE, once, and never by the game.** The catalogue's `from_creatures` name
fragments and a short list of species words propose which block gets which part and which
surface; the proposals are written as tags, every one of them listed in
docs/harvest-tags-review.md for the owner's review (the forge's pattern), and the reader
asks the tags. That is the owner's rule turned the right way round: the measured defects —
a red dragon offered all eleven colours, 109 humanoids yielded a hide, "Bugbear" matched
"bear" — were the GAME matching names at play time. Here every fragment is matched as whole
words, restricted to the hide document's own creature type, and a block may carry one named
hide at most (the longest fragment wins: a winter wolf is not also a wolf).

**What is read from fields, not names**: a true dragon's colour (its breath's energy and
shape and its printed good or evil, `harvest.dragon_colour`); dangers (`harvest
.derive_dangers`); the bans (humanoids and native outsiders get nothing, and the validator
refuses a tag on one); the generic rule's type; the essences of the alignment subtypes.

Every tag written is checked by `harvest.validate_tags` before anything is written; a
refused tag stops the pass with the fix named.

    python tools/harvest_tags.py            # write the tags and the review
    python tools/harvest_tags.py --check    # exit 1 if a file or the review is stale
"""
from __future__ import annotations

import collections
import html
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pathfindergm.settings")

import django  # noqa: E402

django.setup()

from rules import harvest, ingredients, materials  # noqa: E402

BESTIARY = ROOT / "content" / "bestiary"
FILES = ("core", "creatures", "mounts")
REVIEW = ROOT / "docs" / "harvest-tags-review.md"

# --- the tool's word lists (proposals, reviewed; the game never reads a name) --------------

SURFACE_WORDS = {
    "feather": ("bird", "eagle", "hawk", "owl", "roc", "raven", "crow", "vulture", "falcon",
                "parrot", "peacock", "ostrich", "emu", "axe beak", "heron", "stork", "condor",
                "pelican", "albatross", "goose", "swan", "duck", "chicken", "rooster",
                "thunderbird", "terror bird", "dodo", "kingfisher", "magpie"),
    "scale": ("snake", "serpent", "viper", "python", "cobra", "adder", "asp", "boa",
              "anaconda", "lizard", "crocodile", "alligator", "caiman", "gecko", "iguana",
              "monitor", "chameleon", "dinosaur", "allosaurus", "tyrannosaurus", "triceratops",
              "stegosaurus", "ankylosaurus", "deinonychus", "velociraptor", "brachiosaurus",
              "elasmosaurus", "parasaurolophus", "iguanodon", "compsognathus", "drake",
              "wyvern", "pteranodon", "basilisk", "sea snake", "rattlesnake", "mamba",
              "krait", "pangolin", "armadillo"),
    "smooth": ("shark", "whale", "dolphin", "orca", "eel", "frog", "toad", "slug", "octopus",
               "squid", "ray", "manta", "hippopotamus", "elephant", "mammoth", "mastodon",
               "rhinoceros", "walrus", "seal", "newt", "fish", "pike", "barracuda", "piranha",
               "leech", "worm", "bat", "pig", "boar", "salamander", "axolotl", "catfish",
               "megalodon", "sturgeon", "gar", "grindylow", "jellyfish", "slugs"),
    "shell": ("turtle", "tortoise", "crab", "lobster", "clam", "oyster", "snail", "nautilus",
              "hermit crab", "isopod", "crayfish", "shrimp"),
}
# Vermin that are not chitin, and the order the lists are asked in (shell before scale:
# a "snapping turtle" is a shell).
SURFACE_ORDER = ("shell", "feather", "smooth", "scale")
PLAN_WORDS = {
    "serpent": ("snake", "serpent", "viper", "python", "cobra", "adder", "asp", "boa",
                "anaconda", "eel", "worm", "naga", "rattlesnake", "mamba", "krait", "leech"),
    "long": ("lizard", "crocodile", "alligator", "caiman", "gecko", "iguana", "monitor",
             "salamander", "weasel", "ferret", "otter", "wolverine", "mink", "newt",
             "drake", "chameleon"),
}

# Hide documents matched by a field rule rather than a name (the reader's own functions).
FIELD_RULES = {
    # Angelskin is the skin of an angel (the book), read off the subtype.
    "angelskin": lambda b: harvest.creature_kind(b) == "outsider"
    and "angel" in harvest.subtypes(b),
}
# Non-leather materials matched by a field rule: (branch, material) -> predicate.
_TRUE = harvest.is_true_dragon


def _colour_is(colour):
    return lambda b: harvest.dragon_colour(b) == colour


def _outsider_with(*subs):
    return lambda b: harvest.creature_kind(b) == "outsider" and bool(
        harvest.subtypes(b) & set(subs))


OTHER_FIELD_RULES = {
    ("blood", "dragon-blood"): lambda b: harvest.creature_kind(b) == "dragon",
    ("reagent", "dragon-bile"): _TRUE,
    ("essence", "red-dragon-ichor"): _colour_is("red-dragonhide"),
    ("essence", "blue-dragon-ichor"): _colour_is("blue-dragonhide"),
    ("essence", "white-dragon-ichor"): _colour_is("white-dragonhide"),
    ("essence", "green-dragon-ichor"): _colour_is("green-dragonhide"),
    ("essence", "black-dragon-ichor"): _colour_is("black-dragonhide"),
    ("essence", "dragon-scale-catalyst"): _TRUE,
    ("essence", "holy-essence"): _outsider_with("good"),
    ("essence", "unholy-essence"): _outsider_with("evil"),
    ("essence", "anarchic-essence"): _outsider_with("chaotic"),
    ("essence", "axiomatic-essence"): _outsider_with("lawful"),
    ("essence", "celestial-tears"): _outsider_with("angel", "archon", "azata", "agathion"),
    ("essence", "angel-feather"): _outsider_with("angel"),
    ("essence", "fiend-ash"): _outsider_with("demon", "devil", "daemon"),
    ("sinew", "dragon-sinew"): _TRUE,
}
# Name fragments for materials that carry none (the enchanter's), read once here.
EXTRA_FRAGMENTS = {
    "lich-dust": ["lich"], "phoenix-ember": ["phoenix"], "phoenix-quill-ink": ["phoenix"],
}
# Fragments refused by hand (each a measured false match in this pass's first draft).
REFUSED_FRAGMENTS = {
    # "dragon" on the dragonhides, the dragon-hide grip and the tannin matched every
    # dragon-named block whatever its colour: the defect this pass exists to end.
    "dragon", "wyrm", "angel", "fiend",
}
# Per material, a fragment refused after review: the Shadow the umbral distillate names is
# an incorporeal undead with no body to cut, and "shadow" alone reached a shadow sea
# serpent, a shadow rat swarm and every NPC called Shadow-something.
REFUSED_FRAGMENT_FOR = {"umbral-distillate": {"shadow"}}
# A block a fragment wrongly reached, by material, after review of the first draft:
# a wolf SPIDER is no wolf, an ant LION no lion, a moray no electric eel.
EXCLUDE: dict[str, set[str]] = {
    "boreal-wolf-pelt": {"giant-wolf-spider", "gigantic-wolf-spider"},
    "cat-fur": {"ant-lion-giant", "ant-lion-giant-adult", "giant-ant-lion"},
    "electric-eel-skin": {"advanced-giant-moray-eel", "eel-giant-moray", "silt-eel"},
}
# Undead and constructs have no living body to harvest: a bear skeleton gives no bear
# hairs and a zombie purple worm no venom (measured in the first draft: 14 such rows).
# Except the parts that ARE of the undead: ectoplasm off a ghost, a lich's dust.
UNDEAD_OK = {"ectoplasm-residuum", "lich-dust"}


def _words(text: str) -> str:
    text = html.unescape(str(text or "")).lower()
    # Index-style names: "Scorpion, Giant" -> "giant scorpion".
    if "," in text:
        head, _, tail = text.partition(",")
        text = f"{tail.strip()} {head.strip()}"
    return " ".join(re.findall(r"[a-z0-9]+", text))


def _has_phrase(name: str, phrase: str) -> bool:
    phrase = _words(phrase)
    return bool(phrase) and re.search(rf"\b{re.escape(phrase)}s?\b", name) is not None


def merged() -> dict[str, dict]:
    """The blocks as the game reads them (`bestiary._build_imported`'s merge: core wins)."""
    from rules import bestiary

    return {k: dict(v) for k, v in bestiary._build_imported().items()}


def _doc_type(doc: dict) -> str:
    return str(doc.get("creature_type") or "").replace("-", " ").strip().lower()


def named_hides() -> list[dict]:
    out = []
    for mid, doc in sorted(materials.all().items()):
        if doc.get("catalogue") != "leatherworker-materials" or doc.get("kind") != "hide":
            continue
        if mid in harvest.GENERIC.values() or doc.get("obtain") != "harvested":
            continue
        out.append(doc)
    return out


def _fragments(doc_or_frags) -> list[str]:
    frags = doc_or_frags if isinstance(doc_or_frags, list) else (
        doc_or_frags.get("from_creatures") or [])
    return [f for f in (str(x).strip().lower() for x in frags)
            if f and f not in REFUSED_FRAGMENTS]


def _surface(block: dict, name: str) -> str:
    kind = harvest.creature_kind(block)
    for surface in SURFACE_ORDER:
        if any(_has_phrase(name, w) for w in SURFACE_WORDS[surface]):
            return surface
    if kind == "vermin":
        return "chitin"
    if kind == "dragon":
        return "scale"
    if "aquatic" in harvest.subtypes(block) and "fly" not in str(
            block.get("speed_note") or "").lower():
        return "smooth"
    return "fur"


def _plan(block: dict, name: str, surface: str) -> str:
    if surface in ("chitin", "shell"):
        return "carapace"
    for plan in ("serpent", "long"):
        if any(_has_phrase(name, w) for w in PLAN_WORDS[plan]):
            return plan
    if surface == "feather" or (harvest.creature_kind(block) == "dragon"
                                and "fly" in str(block.get("speed_note") or "").lower()):
        return "winged"
    return "quadruped"


def _other_materials() -> list[tuple[str, str, list[str], str]]:
    """(branch, material id, fragments, type filter) for every other craft's carcass part:
    the forge's quench bloods, alchemy's glands and reagents, enchanting's essences, the
    herbalist's monster parts. What has no branch in the grammar is listed as unmapped."""
    out = []
    for mid, doc in sorted(materials.all().items()):
        if doc.get("obtain") != "harvested" or doc.get("retired"):
            continue
        cat, kind = doc.get("catalogue"), doc.get("kind")
        if cat == "blacksmith-materials" and kind == "quenchant":
            branch = "blood"
        elif cat == "alchemist-materials" and kind in ("gland", "reagent", "essence",
                                                       "catalyst"):
            branch = "reagent"
        elif cat == "enchanter-materials" and kind in ("essence", "catalyst", "ink"):
            branch = "essence"
        elif cat == "leatherworker-materials" and kind == "thread" and doc.get("from_creatures"):
            branch = "sinew"
        else:
            continue
        frags = [f for f in _fragments(EXTRA_FRAGMENTS.get(mid) or doc)
                 if f not in REFUSED_FRAGMENT_FOR.get(mid, set())]
        out.append((branch, mid, frags, _doc_type(doc)))
    for iid, ing in sorted(ingredients.all_ingredients().items()):
        if str(getattr(ing, "kind", "")) != "monster part":
            continue
        # The name less its part word ("Dire Boar Tusk" -> "dire boar"), else the
        # ingredient's `source`: the source alone said "dire" and reached every dire
        # beast in the book (39 rows in the first draft).
        words = str(getattr(ing, "name", "")).lower().split()
        stem = " ".join(words[:-1]) if len(words) > 1 else ""
        frags = [stem] if len(stem.split()) >= 2 else [
            str(getattr(ing, "source", "") or stem).lower()]
        out.append(("part", iid, [f for f in frags if f], ""))
    return out


def unmapped() -> list[tuple[str, str]]:
    """Carcass materials no branch of the grammar takes, with the reason, for the review."""
    out = []
    for mid, doc in sorted(materials.all().items()):
        if doc.get("obtain") != "harvested" or doc.get("retired"):
            continue
        cat, kind = doc.get("catalogue"), doc.get("kind")
        if cat == "leatherworker-materials" and kind in ("oil", "tannin"):
            out.append((mid, f"a leather {kind}: the grammar has no fat or gall branch "
                             f"(lane W / the owner)"))
        elif cat == "blacksmith-materials" and kind in ("fuel", "alloy", "fitting"):
            out.append((mid, f"a forge {kind}: the forge's branch is blood only"))
        elif cat == "enchanter-materials" and kind in ("chalk",):
            out.append((mid, "no creature named in its document"))
        elif cat == "leatherworker-materials" and kind == "thread" \
                and not doc.get("from_creatures") and mid != harvest.PLAIN_SINEW:
            out.append((mid, "a common thread every counter sells; not a carcass part"))
    return out


def plan_tags(blocks: dict[str, dict]) -> tuple[dict[str, list[str]], dict]:
    """{block id: tags} and the review's facts."""
    hides = named_hides()
    others = _other_materials()
    facts = collections.defaultdict(list)
    out: dict[str, list[str]] = {}
    for bid, block in sorted(blocks.items()):
        if harvest.banned(block):
            continue
        kind = harvest.creature_kind(block)
        subs = harvest.subtypes(block)
        if "incorporeal" in subs:
            continue
        name = _words(block.get("name") or bid)
        tags: list[str] = []
        # The named hide: a field rule, a true dragon's own colour, else the longest
        # whole-word fragment within the document's own creature type.
        best, best_len = None, (0, 0)
        colour = harvest.dragon_colour(block)
        swarm = "swarm" in subs
        if colour:
            best = colour
        elif not swarm:
            for doc in hides:
                mid = doc["id"]
                if mid in (harvest.rules().get("dragonhides") or {}):
                    continue
                if mid in FIELD_RULES:
                    if FIELD_RULES[mid](block):
                        best, best_len = mid, (99, 0)
                    continue
                want = _doc_type(doc)
                if want and want != kind:
                    continue
                if bid in EXCLUDE.get(mid, set()):
                    continue
                # The longest fragment wins; on a tie, the document that names it FIRST
                # (a salamander is the salamander hide's first word and the noble
                # salamander hide's second).
                for i, frag in enumerate(_fragments(doc)):
                    score = (len(frag), -i)
                    if _has_phrase(name, frag) and score > best_len:
                        best, best_len = mid, score
        hide_giving = not swarm and (bool(best) or kind in harvest.GENERIC_TYPES)
        surface = ""
        if best:
            tags.append(f"harvest.hide.{best}")
            surface = str((materials.get(best) or {}).get("surface") or "")
            facts["named"].append((best, bid, block.get("name")))
        elif hide_giving:
            surface = _surface(block, name)
            tags.append(f"harvest.hide.generic.{surface}")
            facts["generic"].append((surface, bid, block.get("name")))
        if hide_giving:
            tags.append("harvest.sinew")
            tags.append(f"harvest.plan.{_plan(block, name, surface or 'fur')}")
        # Every other craft's parts.
        for branch, mid, frags, want in others:
            if kind in ("undead", "construct") and mid not in UNDEAD_OK:
                continue
            rule = OTHER_FIELD_RULES.get((branch, mid))
            if rule is not None:
                hit = bool(rule(block))
            else:
                if want and want != kind:
                    continue
                hit = any(_has_phrase(name, f) for f in frags)
            if hit and bid not in EXCLUDE.get(mid, set()):
                tags.append(f"harvest.{branch}.{mid}")
                facts[branch].append((mid, bid, block.get("name")))
        # A named sinew (a dragon's, a wyvern's) is the beast's sinew: not plain sinew too.
        if any(t.startswith("harvest.sinew.") for t in tags):
            tags = [t for t in tags if t != "harvest.sinew"]
        if not tags:
            continue
        for kind_ in harvest.derive_dangers(block):
            tags.append(f"harvest.danger.{kind_}")
            facts["danger"].append((kind_, bid, block.get("name")))
        out[bid] = list(dict.fromkeys(tags))
    return out, facts


def _merge_tags(old, new: list[str]) -> list[str]:
    """A block's own non-harvest tags kept (the watchman's `role.guard`), its harvest tags
    replaced by this pass's."""
    keep = [t for t in (old or []) if not str(t).startswith("harvest.")]
    return keep + list(new)


def apply(tags: dict[str, list[str]], *, write: bool) -> list[str]:
    """Write the tags into every file's row with that id (the merged block is what the game
    reads, and a row in both files must not disagree). Returns the stale files."""
    stale = []
    for stem in FILES:
        path = BESTIARY / f"{stem}.json"
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        changed = False
        for row in data.get("creatures") or []:
            bid = row.get("id")
            want = _merge_tags(row.get("tags"), tags.get(bid, []))
            have = list(row.get("tags") or [])
            if want != have:
                changed = True
                if want:
                    row["tags"] = want
                else:
                    row.pop("tags", None)
        if not changed:
            continue
        stale.append(stem)
        if write:
            if stem == "mounts":
                path.write_text(_mounts_text(raw, data), encoding="utf-8")
            else:
                path.write_text(json.dumps(data, indent=1, ensure_ascii=False),
                                encoding="utf-8")
    return stale


def _mounts_text(raw: str, data: dict) -> str:
    """mounts.json is laid out by hand, several fields to a line; its rows gain a `tags`
    line after `biomes_from` instead of the whole file being re-laid."""
    out = raw
    for row in data.get("creatures") or []:
        start = out.find(f'"id": "{row["id"]}"')
        if start < 0:
            continue
        end = out.find('"biomes_from":', start)
        close = out.find("}", end)
        seg = out[start:close]
        seg = re.sub(r',\s*"tags": \[[^\]]*\]', "", seg)
        tags = row.get("tags")
        if tags:
            seg += ",\n     \"tags\": " + json.dumps(tags, ensure_ascii=False)
        out = out[:start] + seg + out[close:]
    return out


def review(tags: dict[str, list[str]], facts: dict, blocks: dict[str, dict]) -> str:
    lines = ["# Harvest tags: the bestiary pass, for review", "",
             "Generated by `tools/harvest_tags.py` from `content/bestiary/*.json`; do not edit "
             "by hand (`--check` says whether it is stale). The owner's rule (leatherworking "
             "Q9.2): the beasts carry harvest tags and the harvest's reader "
             "(`rules/harvest.py`) finds them; the game never reads a creature's name. The "
             "names were read once, here, to propose the tags below, and every proposal is "
             "listed for review. A wrong row is fixed by adding the block to the tool's "
             "`EXCLUDE` (or a fragment to `REFUSED_FRAGMENTS`) and running it again.", ""]
    total = len(blocks)
    tagged_n = len(tags)
    lines += ["## Counts", "",
              f"- Blocks in the merged bestiary: {total}",
              f"- Blocks given harvest tags: {tagged_n}",
              f"- Humanoids and native outsiders (never harvested): "
              f"{sum(1 for b in blocks.values() if harvest.banned(b))}",
              f"- Named hides placed: {len(facts['named'])}; generic hides: "
              f"{len(facts['generic'])}",
              f"- Quench bloods: {len(facts['blood'])}; alchemy parts: "
              f"{len(facts['reagent'])}; essences: {len(facts['essence'])}; herbalist parts: "
              f"{len(facts['part'])}; named sinew: {len(facts['sinew'])}",
              f"- Dangerous bodies: {len(set(b for _, b, _ in facts['danger']))} "
              f"({', '.join(f'{k} {n}' for k, n in sorted(collections.Counter(k for k, _, _ in facts['danger']).items()))})",
              ""]
    pois = [b for b in blocks.values() if "harvest.danger.poison" in tags.get(b.get("id"), [])]
    runs = sum(1 for b in pois if harvest._poison_runs(b))
    paragraphs = sum(1 for b in pois if harvest.poison_paragraph(b))
    lines += ["## Poison rounds", "",
              f"Of {len(pois)} tagged poisonous bodies, {paragraphs} print a poison paragraph "
              f"and {runs} parse to a save and an effect (`effects.extract`, which reads the "
              f"abbreviated \"effect 1d2 Con\" since this pass; docs/deeds-plan.md §13.4 "
              f"measured 34 of 79 before). The rest run no poison round: a poison nobody "
              f"printed is never invented.", ""]
    lines += ["## Named hides", "", "| Hide | Block | Name |", "|---|---|---|"]
    for mid, bid, nm in sorted(facts["named"]):
        lines.append(f"| {mid} | `{bid}` | {nm} |")
    lines += ["", "## Generic hides that are not fur", "",
              "Animals and magical beasts default to fur; these were proposed otherwise from "
              "the block's words and fields.", "", "| Surface | Block | Name |", "|---|---|---|"]
    for surface, bid, nm in sorted(facts["generic"]):
        if surface != "fur" and surface != {"vermin": "chitin", "dragon": "scale"}.get(
                harvest.creature_kind(blocks.get(bid)), ""):
            lines.append(f"| {surface} | `{bid}` | {nm} |")
    for branch, title in (("blood", "Quench bloods (the forge)"),
                          ("reagent", "Alchemy parts"), ("essence", "Essences (enchanting)"),
                          ("part", "Herbalist parts"), ("sinew", "Named sinew")):
        lines += ["", f"## {title}", "", "| Material | Block | Name |", "|---|---|---|"]
        for mid, bid, nm in sorted(facts[branch]):
            lines.append(f"| {mid} | `{bid}` | {nm} |")
    lines += ["", "## Carcass materials no branch takes", "",
              "The old excursions turned these up off a carcass by name; the grammar has no "
              "branch for them, so they are not tagged (bought where a counter sells them).",
              "", "| Material | Why |", "|---|---|"]
    for mid, why in unmapped():
        lines.append(f"| {mid} | {why} |")
    unplaced = [d["id"] for d in named_hides()
                if d["id"] not in {m for m, _, _ in facts["named"]}]
    lines += ["", "## Named hides no block carries", "",
              ", ".join(unplaced) or "None.", ""]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    check = "--check" in argv
    blocks = merged()
    tags, facts = plan_tags(blocks)
    problems = []
    for bid, ts in tags.items():
        b = dict(blocks[bid], tags=ts)
        problems += harvest.validate_tags(b)
    if problems:
        print("Refused, nothing written:")
        for p in problems[:50]:
            print("  " + p)
        return 1
    stale = apply(tags, write=not check)
    text = review(tags, facts, blocks)
    if check:
        old = REVIEW.read_text(encoding="utf-8") if REVIEW.exists() else ""
        if stale or old != text:
            print(f"stale: {', '.join(stale) or 'the review'}")
            return 1
        print("fresh")
        return 0
    REVIEW.write_text(text, encoding="utf-8")
    print(f"tagged {len(tags)} blocks; wrote {', '.join(stale) or 'nothing new'}; "
          f"review at {REVIEW.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

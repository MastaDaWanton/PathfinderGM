"""Write out every ingredient, with a prompt asking a model to tag it.

`rules/herbprep.py` gave every ingredient six preparation flags and defaults that keep
the 161 already authored behaving exactly as they did. Which means all 161 currently
say the same thing: grind it, mix it, brew it, keep it a week. That is safe and it is
not interesting, and the answers are already sitting in the harvesting notes and the
descriptions — "the shell must be cracked", "the sap ignites", "dries to a powder".

This writes two files: the whole corpus in a form a chat model can read, and a prompt
that asks for the tags back as JSON keyed by id. Nothing here decides anything. The
model's answer comes back through `tools/apply_herb_tags.py`, which validates it
against the real ids before it touches the content.

The herbalism revamp (2026-10-02) added a second set of tags: `part`, a `route` on every
structured effect, `hybrid`, `base_for`, `solvent` and `neutralizer`
(docs/herbalism-contracts.md section 2). The shipped corpus carries all of them already,
tagged by hand, so the export shows the current values beside each entry and the prompt
asks only for corrections. `apply_herb_tags.py` reads the six preparation flags and
nothing else; a corrected part or route goes into the corpus by hand, and
`tests/test_ingredient_tags.py` validates it there.

It also writes `docs/herbalism-hybrid-review.md`, the page the owner checks the hybrid
calls on. That page was hand-assembled the first time (Lane A, 2026-10-02) and went stale
the moment the relevance pass changed the effects under it, so it is generated here now:
each effect by route comes from the corpus, and only the "why" of each call is written
by a person (`WHY` below). `--before <corpus.json>` adds a section listing every entry
whose effects differ from that older copy, old then new; without it the section already
on the page is carried over unchanged.

Run it against a scratch data directory, or a homebrew herb from your own data lands in
the docs:

    PATHFINDER_GM_DATA=<scratch dir> python tools/export_herbs_for_tagging.py \\
        [--before <older herbs-and-parts.json>]
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pathfindergm.settings")

import django  # noqa: E402

django.setup()

OUT = Path(__file__).resolve().parents[1] / "docs"

PROMPT = """You are tagging a Pathfinder 1e herbalism corpus for a solo play app.

Each ingredient below needs six preparation flags. They govern what a player is allowed
to do with it at the crafting bench, so the answers have to follow from what the entry
actually says — not from what the herb is called, and not from real-world herbalism.

The flags, and what each one means mechanically:

  needs_extraction  The usable part is inside something: a shell, a husk, a pod, a
                    gland, a sac, bark that must be stripped, a stone in a fruit.
                    Nothing else can be done to it until it is out.

  volatile          It reacts badly to being worked: it ignites, burns, blisters,
                    fumes, explodes, corrodes, or is a contact poison in the raw. It
                    must be neutralised before it can be ground.

  can_grind         It can be reduced to powder at all. Say no for things that are wet,
                    fleshy, gelatinous, liquid, or that the text says must stay whole.

  mix_raw           It can go straight into a cold mixture. Say no if the text implies
                    the whole form is inert and it must be broken down first.

  brew_raw          It can go straight into the pot. Say no if it needs grinding first
                    to give anything up. This flag also decides whether the herb can be
                    infused into a finished tincture raw, so weigh it accordingly.

  animal            It came from a creature: gland, blood, scale, horn, ichor, carapace,
                    venom, organ, hide. These spoil in 48 hours rather than a week.

Rules for your answer:

* Default to the ordinary case. Most herbs are leaves and roots: they grind, they mix
  raw, they brew raw, they are not volatile, they need no extraction. Only depart from
  that when the entry gives you a reason.
* Quote your reason. For every flag you set away from the default, give the phrase from
  the entry that justifies it. If you cannot quote one, do not set the flag.
* Do not invent. If an entry is too thin to judge, leave it at defaults and say so.
* `kind` is a strong hint for `animal` — "monster part" is almost always yes — but read
  the text, because a few are plants growing on creatures.

Each ingredient also already carries the herbalism tags below, shown as its current
values. Check them against the text and propose a change only where the text disagrees.

  part         What of it is used. One of: leaf, flower, root, bark, berry, seed, sap,
               resin, fungus, gland, organ, bone, horn, feather, scale, eye, shell, oil,
               wax, mineral, liquid. Read it off the text ("the bark", "the sap", "the
               root"). If the text never says, leave the default: leaf for a herb,
               organ for a monster part, fungus for a fungus.

  route        On each effect: how that effect reaches the body. One of:
                 ingest    eaten, drunk, chewed, a tea, a pill
                 skin      rubbed on, a salve, a lotion, a worn patch
                 eyes      dropped in or smeared on the eyes or eyelids
                 wound     bound on, packed into or washed over a wound
                 inhale    smoked, snorted, breathed as incense or vapour
                 external  the effect reaches OUTSIDE the body or changes what
                           others perceive: invisibility, light, flight, charming
                           another, a cloud over an area, a coating on a blade or
                           arrow that acts on a target, incorporeality, a ward
                           on a place or an object
               An effect on or in the taker's own body is never external, even when it
               is magical: seeing the invisible through an eye salve is `eyes`, an
               immunity swallowed is `ingest`, fire resistance rubbed on is `skin`.

  hybrid       true when any effect is magical: planar flora, every monster part,
               anything supernatural. A hybrid appears on both the herbalist's and the
               alchemist's shelves. Every `external` effect should be on a hybrid,
               unless it is plainly not herbalism at all (a glue, an ink, a blade poison).

  base_for     ["salve"] for every bark, sap and resin: ground bark and tree sap
               thicken a salve. ["cream"] for a slippery, mucilaginous root, shoot
               or gel (marshmallow, mallow). Otherwise [].

  solvent, neutralizer   Leave these alone. Only the bench's reagents (oil, spirits,
               vinegar, lime, charcoal, clay) carry them, and those live on the
               materials shelf, not in this list.

Answer with JSON only, in exactly this shape, one object per ingredient you are
changing from the defaults or from its current tags. Omit any ingredient you are
leaving alone. Give `routes` as a full list, one per effect, in the order shown:

{
  "adder-s-tongue": {
    "needs_extraction": false,
    "volatile": true,
    "can_grind": true,
    "mix_raw": false,
    "brew_raw": true,
    "animal": false,
    "part": "leaf",
    "routes": ["wound"],
    "hybrid": false,
    "why": {"volatile": "the sap blisters skin", "mix_raw": "inert until crushed",
            "routes": "the ointment is laid on the wound"}
  }
}

The ingredients follow.
"""


# --- the hybrid review ------------------------------------------------------------------
#
# Why each call was made, by entry id. Lane A wrote these while tagging; the relevance pass
# (Lane A2) corrected the ones its changes made untrue. Everything else on the page is read
# from the corpus, so this is the only part that can go stale, and it says *why*, which
# the data cannot.
WHY = {
    # The doubtful calls: a reasonable reading goes the other way.
    "gloomwraith-tendril": "The plan (section 5.2) cites this as route `eyes`, an eye cream. The entry's own text says the tendrils are boiled into a syrup and ingested, so every effect is tagged `ingest`. Either way the herbalist can make it; the question is the product form.",
    "shadowvine": "Ingested, but the Stealth is the user blending into shadows: it changes what others see, so `external` (alchemy only), cut to +2 for a common herb. The relevance pass gave the herbalist the dark's endurance instead, a Fortitude bonus against negative energy (`ingest`).",
    "mistveil-fern": "Taken by inhaling spores (a herbal route), but partial incorporeality is the owner's own example of external, so both of its effects stay `external`. The relevance pass added a shallow breath for Escape Artist (`inhale`).",
    "cockatrice-beak": "The paste goes on boots, not skin, and ignoring difficult terrain works through the gear: `external`. Could be read as a body effect on the wearer's movement. The relevance pass added a tea against petrification (`ingest`).",
    "dracolisk-scale": "Powder sprinkled over armour, not the body: the petrification ward and its -2 Dexterity are both `external`. The relevance pass added the powder swallowed in honey against petrification (`ingest`).",
    "ice-lotus": "Icewalker oil climbs ice like spider climb, now +4 Climb there. Movement magic, like flight, so `external`; if the oil is rubbed on the feet it could be `skin`. The relevance pass added cold resistance drunk and fire resistance rubbed on.",
    "frostbloom": "Hybrid only because 10 points of fire resistance is spell strength. Route `skin`, per the owner's example. If this is ordinary herbcraft, unmark hybrid. (The stored 0 the text contradicted is 10 now.)",
    "starbloom": "Hybrid because seeing in complete darkness is darkvision. Brewed as a tea, so `ingest`. Chasmyre Leaf (low-light vision) was left non-hybrid by the same reasoning.",
    "ironbark-moss": "Hybrid because chewing it for +2 natural armour is barkskin by another name. Route `ingest`.",
    "aelfengrape": "Hybrid for the glow and the elven wizards who made it. Eaten, so `ingest`. The DC the parser found was its crafting DC and is gone; the light is not a structured effect.",
    "cloth-of-gold": "Speak with animals is a spell effect, so hybrid. It is chewed and works in the chewer's own head, so `ingest`, not external.",
    "djinn-blossoms": "Planar. The worn blossom's breeze guards against gases from outside the body, so `external`. The perfume is worn on the skin, `skin`, and its breath drawn in is `inhale`.",
    "banshee-wail-essence": "Inhaled, and the effect is the user's own amplified voice, so `inhale`. Arguably it changes what others hear, which would make it external.",
    "henna": "\"Magically reactive\" makes it hybrid. A tattoo pigment and a cooling paste, so every effect is `skin`.",
    "harpy-vocal-cord": "Charm person cast on another is `external`, now a Will DC 15 save that sets the target's attitude to friendly. Before the relevance pass a herbal product carried only the -2 Diplomacy; now the drinker's own voice and ear are the herbalist's (`ingest`).",
    "salamander-ember-gland": "The 10-ft burst of flame is `external`; the 1d4 burn to the drinker is `ingest`. Before the relevance pass a herbal product carried only the burn; now it carries the heat kept inside too (resist cold, initiative).",
    "wendigo-antler": "The scattered dust's aura against undead is `external`, and so is the -2 Constitution curse it costs, so a herbal product never carries the cost without the aura. The relevance pass added the broth: resist cold 10 (`ingest`).",
    "imperial-willow": "The bark tea is ordinary herbcraft, `ingest`. Hybrid only for the heartwood that strengthens nearby magic and song (`external`).",
    "spriggan-tree": "Hybrid for the acorns' enlarge magic, now a +2 size bonus to Strength (`external`). The bark tea against parasites is `ingest`.",
    "twilight-dagger": "Hybrid only because it grows in magic-soaked lands and its sap \"carries a faint charge\". Drunk it is `ingest`; smeared, `skin`.",
    "cave-star": "Hybrid because its effect is light (the owner lists illumination as external), a manifest now. A glowing plant could be plain bioluminescence; if so it is a non-herbal external like the ink and the glue. The relevance pass added a tea and an eyewash.",
    "fey-cherry": "Protection from evil, eaten: a ward, but on the eater, so `ingest` (the owner: \"an immunity swallowed = ingest\"), typed as the spell types it (deflection, resistance).",
    "coldwood": "Fey-grown wood for weapons and armour. Tagged part `bark`, because the vocabulary has no `wood`, which also makes it a salve base under the bark rule. Its worked-item effects are `external`; the bark tea is `ingest`.",
    "rowan": "Wood that protects against magic. Part `bark` for the same reason as Coldwood. Its worked-item effects are `external`; the berries are `ingest`.",
    # The rest of the hybrids.
    "basilisk-eye": "Monster part. A paste for the eyes against gaze attacks and petrification: `eyes`, the body's own defence.",
    "behemoth-hide": "Monster part. Tanned and worn as a patch for natural armour: `skin`. Part `organ` (no `hide` in the vocabulary).",
    "blackthorn": "Repels evil outsiders \"as garlic repels vampires\", strewn or worn: a ward in an area, `external`. The sloes, eaten or laid on a cut, are the herbalist's.",
    "blueweed": "Powder sprinkled to ritually purify an object: works on the object, `external`. The wash and the tea are the herbalist's.",
    "breeam": "Smoke that sears undead in an area: `external`. Breathed by whoever lit it, `inhale`.",
    "chimera-horn": "Monster part, snorted: every effect `inhale`.",
    "dire-boar-tusk": "Monster part, snorted: `inhale`.",
    "dreamcap": "Grows in enchanted groves; prophetic dreams. Eaten: `ingest`.",
    "dryad-s-tears": "The odour repels lycanthropes (`external`); the berries' save against lycanthropy is the eater's own (`ingest`).",
    "elysium": "An antimagic field where it grows, and a ward while carried: both `external`. Eaten, and as a gel on the skin, the herbalist's.",
    "faerie-grass": "Stepping on the patch confuses: the growing plant acts on passers-by, `external`. Steeped as a tea it is `ingest`.",
    "flame-clove": "Elemental fire added to alchemist's fire is `external`; eaten, it warms the eater (`ingest`).",
    "frostgiant-marrow": "Monster part, boiled into a broth: `ingest`.",
    "glowvine": "Blossoms shed torchlight: `external`. The petal eyewash is `eyes`.",
    "grave-mold": "Psionic, can raise a simulacrum. The ounce eaten against disease is `ingest`; dusted in a wound, `wound`.",
    "griffon-talon": "Monster part, a salve on the hands for melee attacks: `skin`.",
    "hawthorn": "Pollen in the eyes sees fey through invisibility: `eyes` (the owner's \"seeing the unseen via an eye salve\"). The berry tea is `ingest`.",
    "horsetail": "Same text as Blueweed: ritual purification of an object, `external`. In a cut, or as a tea, the herbalist's.",
    "hrondis-tears": "Wrapped on a weapon's hilt so it strikes incorporeal undead: `external`. Brewed and drunk, `ingest`.",
    "hydra-gall": "Monster part, distilled and drunk: `ingest`.",
    "hypericum": "Sprinkled on a place or person for exorcisms and summonings: `external`. Drunk, or laid on a wound in oil, the herbalist's.",
    "kraken-ink": "Monster part, runes inscribed on the skin for water breathing: `skin`.",
    "lakeleaf": "Rubbed into meat, or lengthening gentle repose: works on things and spells, `external`. Chewed, or laid on skin, the herbalist's.",
    "manticore-spine": "Monster part. A tincture on ammunition is a coating that acts on a target (`external`); the mishandling sting is `skin`; dilute on a wound it numbs (`wound`).",
    "menhirite": "Planar. The sap heals a wound (`wound`); the ring's holy ground acts on whoever stands in it (`external`).",
    "nahre-lotus": "Planar. A dead lotus thrown as a blight is `external`; the living lotus's water, drunk, is `ingest`.",
    "orevine": "Planar. Draws metal out of the ground: `external`. The metal-heavy decoction is `ingest`.",
    "phoenix-feather": "Monster part, burned and inhaled for fire immunity: `inhale`. An immunity taken into the body is herbal.",
    "rue": "Second sight, brewed and drunk: `ingest`. The eyewash is `eyes`.",
    "salamander-orchids": "Planar. Touching it burns (`skin`); worked into flaming weapons (`external`); a petal eaten (`ingest`).",
    "sphinx-whisker": "Monster part, burned and the smoke inhaled: `inhale`. Part `feather` (no `hair` in the vocabulary).",
    "sukake": "Strengthens a divination (`external`). Eaten alone, a narcotic and an opened mind's eye: `ingest`.",
    "tahtoalehti": "The wish: `external`, kept as the one wish the app can grant, a +1 inherent bonus. The blossom eaten is `ingest`.",
    "tamarisk": "Burning it repels reptilian creatures: `external`. Its manna, eaten, is `ingest`.",
    "trollheart-sap": "Monster part, distilled into a tonic: `ingest`. Its fast healing, which the drink path never ran, is 2d4 healing now. Part `organ` (the heart).",
    "vervain": "Incense that strengthens turning undead in the area: `external`. The tea is `ingest`.",
    "wispweed": "Smoke for telepathy between those inside it: `external`. Breathed by the burner, `inhale`.",
    "wyrmfang-venom": "Monster part. Applied to a weapon (`external`); the handling risk is `skin`; a trace swallowed against venom is `ingest`.",
    "xian-tao": "Peach of immortality, eaten: `ingest`.",
    # Calls on entries that are not hybrid.
    "damiana": "Incense whose vapours raise Charisma for anyone in them. An area, but each person inhales it into their own body, and it is plain herbcraft: `inhale`, not hybrid.",
    "levisticum": "A love potion makes the drinker warm to the one who served it. It acts in the drinker's own body (`ingest`); it is not the user charming another. Myrtle the same.",
    "myrtle": "As Levisticum.",
    "calendula": "\"Helps divine someone's future lover\": folk divination. Sense Motive, `ingest`. Not hybrid.",
    "mistletoe": "Its bonus against transformation, polymorph included, is from an extract drunk: `ingest`. Left non-hybrid because the protection is the body's own.",
    "tugwort": "Resistance against slashing and piercing from an infusion: `ingest`. Left non-hybrid; could be read as magical.",
    "chasmyre-leaf": "Low-light sight from a leaf on the eyelids: `eyes`, natural, not hybrid.",
    "scorpion": "Filed as kind `herb`, but its text is a scorpion's powdered body. Part `shell`. The kind looks wrong.",
}
DOUBTFUL = ("gloomwraith-tendril", "shadowvine", "mistveil-fern", "cockatrice-beak",
            "dracolisk-scale", "ice-lotus", "frostbloom", "starbloom", "ironbark-moss",
            "aelfengrape", "cloth-of-gold", "djinn-blossoms", "banshee-wail-essence",
            "henna", "harpy-vocal-cord", "salamander-ember-gland", "wendigo-antler",
            "imperial-willow", "spriggan-tree", "twilight-dagger", "cave-star",
            "fey-cherry", "coldwood", "rowan")
NOT_HYBRID_CALLS = ("damiana", "levisticum", "myrtle", "calendula", "mistletoe", "tugwort",
                    "chasmyre-leaf", "scorpion")
CHANGES_START, CHANGES_END = "<!-- changes:start -->", "<!-- changes:end -->"


def _by_route(item) -> str:
    """Each effect as "`route`: card line", one per line in a table cell."""
    from rules import ingredients as ing

    return "<br>".join(f"`{ing.route_of(spec)}`: {line}" for line, spec in item.pairs)


def _effect_list(effects) -> str:
    from rules import effectspec
    from rules import ingredients as ing

    return "; ".join(f"`{ing.route_of(s)}` {effectspec.render(s)}" for s in effects) or "nothing"


def _changes(before_path: Path | None, everything, review: Path) -> str:
    """The section listing every changed entry, old then new, one line each."""
    if before_path is None:
        old = review.read_text(encoding="utf-8") if review.exists() else ""
        if CHANGES_START in old and CHANGES_END in old:
            return old[old.index(CHANGES_START):old.index(CHANGES_END) + len(CHANGES_END)]
        return ""
    before = {e["id"]: e for e in
              json.loads(before_path.read_text(encoding="utf-8"))["ingredients"]}
    lines = [CHANGES_START, "",
             "## What the relevance pass changed (Lane A2)", "",
             "Three rulings of the owner, 2026-10-02, applied to every entry: the app's "
             "mechanics are the truth and each description says what the herb does in the "
             "app; every herb has at least three discoverable traits with at least one "
             "herbal-route benefit; and every effect is a complete structured document "
             "the engine runs (executable type, integer duration, typed bonus, a route). "
             "The tests are `tests/test_herb_relevance.py` and "
             "`tests/test_herb_effects_are_documents.py`; their docstrings carry the "
             "before and after counts. Each line below is one entry: what its effects "
             "were, then what they are. Routes in backticks.", ""]
    n = 0
    for iid, item in sorted(everything.items(), key=lambda kv: kv[1].name.lower()):
        old = before.get(iid)
        if old is None or old.get("effects") == item.effects:
            continue
        was, now = _effect_list(old.get("effects") or []), _effect_list(item.effects)
        if was == now:
            now += " (the same lines; bonus types or duration fields made structured)"
        lines.append(f"- **{item.name}.** Was: {was}. Now: {now}.")
        n += 1
    lines += ["", f"{n} entries changed.", "", CHANGES_END]
    return "\n".join(lines)


def write_review(everything, before_path: Path | None) -> Path:
    from collections import Counter

    from rules import ingredients as ing

    review = OUT / "herbalism-hybrid-review.md"
    changes = _changes(before_path, everything, review)
    hybrids = [i for i in everything.values() if i.hybrid]
    monsters = sum(1 for i in hybrids if i.kind == "monster part")
    every = Counter(r for i in everything.values() for r in i.routes)
    hyb = Counter(r for i in hybrids for r in i.routes)
    parts = Counter(i.part for i in everything.values())

    def counted(c: Counter) -> str:
        return ", ".join(f"{k} {v}" for k, v in c.most_common())

    def table(ids) -> list[str]:
        rows = ["| Entry | Kind | Part | Each effect, by route | Why |", "|---|---|---|---|---|"]
        for iid in ids:
            item = everything[iid]
            rows.append(f"| {item.name} | {item.kind} | {item.part} | {_by_route(item)} "
                        f"| {WHY.get(iid, '')} |")
        return rows

    rest = sorted((i.id for i in hybrids if i.id not in DOUBTFUL),
                  key=lambda k: everything[k].name.lower())
    out = [
        "# Herbalism: the hybrid review", "",
        "Written 2026-10-02 by Lane A of the herbalism revamp, for the owner to check by "
        "hand, and regenerated by `tools/export_herbs_for_tagging.py` after the relevance "
        "pass (Lane A2). The tags and effects live in "
        "`content/ingredients/herbs-and-parts.json`; everything on this page except the "
        "\"why\" of each call is read from that file, so the routes below are the ones "
        "that ship.", "",
        "**The rule** (`docs/herbalism-revamp-plan.md` section 5.2, and the owner's "
        "ruling): an entry is `hybrid` when any of its effects is magical (planar flora, "
        "monster parts, anything supernatural), and it then appears on both the "
        "herbalist's and the alchemist's shelves. Every structured effect carries a "
        "`route`. The herbalist can carry an effect only by `ingest`, `skin`, `eyes`, "
        "`wound` or `inhale`; an `external` effect (it reaches outside the body, or "
        "changes what others perceive) is alchemy's and is dropped from a herbal "
        "product. Since the relevance pass, every hybrid also has at least one effect "
        "the herbalist can use.", "",
    ]
    if changes:
        out += [changes, ""]
    out += [
        "## The counts", "",
        f"- **{len(hybrids)} hybrid entries** of {len(everything)}: all {monsters} monster "
        f"parts and {len(hybrids) - monsters} plants and fungi.",
        f"- **Routes, all entries:** {counted(every)} ({sum(every.values())} effects).",
        f"- **Routes, hybrid entries:** {counted(hyb)}.",
        f"- **Parts:** {counted(parts)}.",
        f"- **Bases:** "
        + ", ".join(f"{form} {sum(1 for i in everything.values() if form in i.base_for)}"
                    for form in ing.BASE_FORMS) + ".",
        "",
        f"## The doubtful calls first ({len(DOUBTFUL)})", "",
        "These are the ones where a reasonable reading goes the other way. Each says which "
        "way it was called and what the alternative is.", "",
        *table(DOUBTFUL), "",
        f"## The rest of the hybrids ({len(rest)})", "",
        *table(rest), "",
        "## Calls on entries that are not hybrid", "",
        "Not part of the hybrid review, but judgement calls of the same kind.", "",
        *table(NOT_HYBRID_CALLS), "",
        "Twelve non-hybrid entries carry an `external` effect because what they do is not "
        "the taker's body: Darkroot (glue), Dragon Flower (the growing flower's stench over "
        "an area), Goblin Rouge (ink), Halfling Thistle (rust remover), Golden Maple Leaves "
        "(an additive for alchemical items), Lish Nut (the eater's smell sickens vermin), "
        "Selpeme Blossom (the scent frightens animals), Monkshood and Meadow Giant (blade "
        "coatings), and the poison boosters Dwarven Oak, Orticusp and Wild Fireclover. They "
        "are pinned by name in `tests/test_ingredient_tags.py`, and since the relevance "
        "pass each has a body use the herbalist can make as well. Whether the alchemist "
        "should be able to reach their external halves (by marking them hybrid) is still "
        "an open question.", "",
        "## Parts the text does not name", "",
        "19 entries never say which part is used, and were left at the contract's "
        "default, `leaf`: Aconite, Allnight, Amaranth, Anise, Belladonna, Blackthorn, Cave "
        "Star, Dittany, Halfling Thistle, Henna, Monkshood, Orticusp, Sherpa's Friend, St. "
        "John's-Wort, Tamarisk, Wittlewort, Wolfweed, Wordwood, Woundwort. Some have a "
        "well-known answer outside the text (anise seed, belladonna berry, aconite root); "
        "the text was followed rather than real-world herbalism, as the tagging prompt "
        "asks.", "",
        "## Vocabulary gaps", "",
        "The part vocabulary is fixed by `docs/herbalism-contracts.md` section 2. Four "
        "kinds of thing in the corpus have no word of their own, and were filed under the "
        "nearest:", "",
        "- **wood** (Coldwood, Rowan) as `bark`, which also makes them salve bases;",
        "- **hide** (Behemoth Hide) as `organ`;",
        "- **hair or whisker** (Sphinx Whisker) as `feather`;",
        "- **stem or stalk** (Golden Embrace, Meadow Giant, Mallow's shoots, Wild "
        "Fireclover) as `leaf`.", "",
        "## What the engine cannot run yet", "",
        "Found while making every effect one the engine runs, and worked around in the "
        "data rather than fixed, because `rules/` belongs to other lanes:", "",
        "- `remove_condition` reaches the drink path as a `condition` intent carrying "
        "`remove`, and the op takes `ends`: any jar holding one raises IntentError and "
        "loses every other effect with it. No herb ends a condition until "
        "`rules/consumables.py` sends `ends`.",
        "- `engine._to_rounds` reads `int(amount)`, so a duration in dice crashes the "
        "condition and buff ops. Every herb duration is an integer (each die its average "
        "rounded up).",
        "- `speed` is `engine=False` in the catalogue though the drink path maps it, and "
        "`fast_healing` has no drink-path mapping at all; neither is used.",
        "",
    ]
    review.write_text("\n".join(out), encoding="utf-8")
    return review


def main() -> int:
    from rules import ingredients as ing

    before_path = None
    if "--before" in sys.argv:
        before_path = Path(sys.argv[sys.argv.index("--before") + 1])

    OUT.mkdir(parents=True, exist_ok=True)
    everything = ing.all_ingredients()

    rows = []
    for iid, item in sorted(everything.items(), key=lambda kv: kv[1].name.lower()):
        rows.append({
            "id": iid,
            "name": item.name,
            "kind": getattr(item, "kind", ""),
            "tier": getattr(item, "tier", ""),
            "description": " ".join(str(getattr(item, "text", "") or "").split()),
            "harvesting": " ".join(
                str(getattr(item, "harvesting", "") or "").split()),
            # Each card line with its route. A line the extractor could not structure
            # has no effect behind it and so no route; it is shown with null rather than
            # dropped, because the model should still read what it says.
            "effects": [{"line": line, "route": ing.route_of(spec) if spec else None}
                        for line, spec in item.pairs],
            "part": item.part,
            "hybrid": item.hybrid,
            "base_for": list(item.base_for),
        })

    data = OUT / "herbs-for-tagging.json"
    data.write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n",
                    encoding="utf-8")

    # And a readable version, because a person has to check the answer.
    lines = [f"# Ingredients to tag ({len(rows)})", "",
             "Generated by `tools/export_herbs_for_tagging.py`. The prompt for a chat "
             "model is in `docs/herb-tagging-prompt.md`; the machine-readable corpus "
             "is `docs/herbs-for-tagging.json`.", ""]
    for r in rows:
        tags = f"{r['part']}" + (" · hybrid" if r["hybrid"] else "") + (
            f" · base for {', '.join(r['base_for'])}" if r["base_for"] else "")
        lines.append(f"## {r['name']}  \n`{r['id']}` · {r['kind']} · {r['tier']} · {tags}")
        if r["description"]:
            lines.append("")
            lines.append(r["description"])
        if r["harvesting"]:
            lines.append("")
            lines.append(f"**Harvesting.** {r['harvesting']}")
        if r["effects"]:
            lines.append("")
            lines.append("**Effects.** " + "; ".join(
                f"{e['line']} ({e['route']})" if e["route"] else e["line"]
                for e in r["effects"]))
        lines.append("")
    (OUT / "herbs.md").write_text("\n".join(lines), encoding="utf-8")

    prompt = OUT / "herb-tagging-prompt.md"
    prompt.write_text(
        PROMPT + "\n```json\n"
        + json.dumps(rows, indent=1, ensure_ascii=False)
        + "\n```\n", encoding="utf-8")

    print(f"{len(rows)} ingredients")
    print(f"  {data}          machine-readable corpus")
    print(f"  {OUT / 'herbs.md'}                      readable, for checking by eye")
    print(f"  {prompt}   paste this into Claude")
    print(f"  prompt is {len(prompt.read_text(encoding='utf-8')):,} characters")
    print(f"  {write_review(everything, before_path)}   the hybrid review")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

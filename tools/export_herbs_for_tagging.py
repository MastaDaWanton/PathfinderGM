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

Run it against a scratch data directory, or a homebrew herb from your own data lands in
the docs:

    PATHFINDER_GM_DATA=<scratch dir> python tools/export_herbs_for_tagging.py
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
               thicken a salve. Otherwise [].

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


def main() -> int:
    from rules import ingredients as ing

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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

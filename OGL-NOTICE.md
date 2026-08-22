# Open Game Licence — attribution and status

Pathfinder 1st Edition rules content is Open Game Content under the **Open Game Licence
v1.0a**. The licence requires that it travel with the content, so this file and a verbatim
copy of the licence must ship with any build.

## What in this repo is Open Game Content

`content/spells/spells.json` — 3,040 Pathfinder 1st Edition spells, imported from The
Spell Codex spreadsheet. Names, schools, subschools, descriptors, class lists, components,
ranges, durations, saving throws and descriptions are Open Game Content and each entry
records the sourcebook it came from. The `tags` field on each spell is *not* Open Game
Content: it is this app's own derived index for searching, defines nothing, and is read by
no rule.

`content/bestiary/core.json` — 782 creatures parsed from the six Pathfinder Bestiary PDFs,
including their ecology (environment, organization, treasure). Each entry records which
Bestiary it came from.

`content/bestiary/creatures.json` — 6,406 Pathfinder 1st Edition stat blocks imported
from a monster spreadsheet. Names, challenge ratings, ability scores, hit points, armour
classes, saves, attacks, damage reduction, immunities, skills, feats and descriptions are
Open Game Content, and each entry records the sourcebook it came from.

`content/ingredients/herbs-and-parts.json` mixes sources: entries drawn from Pathfinder
material are Open Game Content, and the setting-specific flora are the user's own.

The structural tables in `rules/tables.py`:

- ability modifier, BAB and saving-throw progressions, iterative attack rules
- the class entries (hit die, BAB type, good saves, skill ranks, class skill lists)
- the skill list with key abilities, trained-only and armour-check flags
- condition effects, weapon and armour statistics, size modifiers
- the difficulty class table used by `rules/dc.py`

Nothing under `world/`, `gm/`, `play/`, `fixtures/` or `docs/` is Open Game Content.
`fixtures/pangrella-campaign.json` is a World Bible export and carries no rules content at
all — that boundary is deliberate and is documented in `docs/campaign-format.md`.

## Before shipping a build

1. **Add `OGL.txt` containing the verbatim licence.** It is not reproduced here on
   purpose: it must be an authoritative copy, taken from
   [paizo.com/pathfinderRPG/prd/openGameLicense.html](https://paizo.com/pathfinderRPG/prd/openGameLicense.html)
   or [d20pfsrd.com/opengamelicense](https://www.d20pfsrd.com/opengamelicense/), not
   retyped. A paraphrased or truncated licence does not satisfy section 10.
2. **Fill in Section 15** of that copy with the declarations of every source actually
   used, in the order required. At minimum this build derives from the Pathfinder
   Roleplaying Game Reference Document and the System Reference Document.
3. **Add the required notices to the packaged app** — the licence must reach the user, not
   just the repository.

## Still to decide

`docs/product-brief.md` names three candidate SRD sources for bulk content (monsters,
spells, items, feats). Each carries its own Section 15 declarations and its own cleaning
cost, and d20PFSRD alters some names for OGL compliance — which matters when matching
against Paizo's own reference. **Evaluate and settle that before importing any bulk
content**, because the attribution obligations arrive with the data and are painful to
reconstruct afterwards.

## Trademarks

This project is not published, endorsed by, or affiliated with Paizo Inc. Product Identity
— including the Pathfinder name and logo — is not licensed by the OGL and must not be used
to describe or brand this application.

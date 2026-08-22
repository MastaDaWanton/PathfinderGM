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

`content/feats/feats.json` — 1,474 Pathfinder 1st Edition feats imported from an OGL feat
spreadsheet. Names, types, prerequisites, benefits and the normal/special clauses are Open
Game Content, and each entry records the sourcebook it came from. The typed
`prerequisites` array is this app's own machine-readable restatement of the prerequisite
text, which is also carried verbatim beside it.

`content/weapons/weapons.json` — 456 Pathfinder 1st Edition weapons. Cost, damage,
critical, range, weight, damage type and special qualities are Open Game Content. The
component columns (head, haft, grip, guard) are the author's own additions for the
crafting system and are not Open Game Content.

**This file records no per-weapon source.** The workbook it came from has no source
column, so unlike the spells, creatures and feats there is nothing saying which book each
weapon is from. All 456 therefore appear in `tools/ogl_sources.py` as unattributed, and
they are the bulk of the 597 such entries. Weapon statistics are among the most widely
reprinted Open Game Content in Pathfinder and the great majority will be Core Rulebook,
Ultimate Combat and Ultimate Equipment — but "will be" is not an attribution, and the
gap is recorded here rather than guessed at.

## Before shipping a build

1. ~~**Add `OGL.txt` containing the verbatim licence.**~~ **Done.** `OGL.txt` holds the
   licence as supplied by the project owner. It has not been paraphrased, reflowed or
   truncated. Anyone re-verifying it should compare against
   [paizo.com/pathfinderRPG/prd/openGameLicense.html](https://paizo.com/pathfinderRPG/prd/openGameLicense.html)
   or [d20pfsrd.com/opengamelicense](https://www.d20pfsrd.com/opengamelicense/).
2. **Fill in Section 15** — *outstanding, and larger than it looks.* `OGL.txt` currently
   carries only the two declarations that came with the licence text: the Open Game
   Licence itself and the System Reference Document. Section 6 requires the exact
   COPYRIGHT NOTICE of **every** source whose Open Game Content is distributed, and this
   build's content was imported in bulk. Run:

   ```bash
   python tools/ogl_sources.py --full
   ```

   As measured on the current content: **12,319 entries across 682 distinct sources**, and
   **597 entries record no source at all** — 456 of them the weapons, which arrived with
   no source column. Those cannot be attributed and must either gain a source or be
   dropped before a build ships. The 682 also span more than one
   publisher — Rappan Athuk, Sword of Air and The Lost City of Barakus are Frog God
   Games, not Paizo — so this is not one boilerplate block.

   Two honest ways forward, and it is the project owner's call which:

   - **Narrow what ships.** Restrict the bundled content to a small set of books whose
     Section 15 declarations can be reproduced exactly, and treat the rest as data the
     user imports themselves. This is the cheap and safe option.
   - **Collect the declarations.** Copy each book's own Section 15 verbatim. Correct, and
     a large amount of careful transcription for 682 sources.

   `tools/ogl_sources.py` exists so this stays a mechanical check rather than a memory
   exercise: a source it lists that this file does not is an attribution the build owes
   and does not have. Re-run it after any content import.
3. **Add the required notices to the packaged app** — the licence must reach the user, not
   just the repository. `OGL.txt` is served at `/licence` and must also be added to the
   PyInstaller bundle's data files when the spec is written.

## Still to decide

`docs/product-brief.md` names three candidate SRD sources for bulk content (monsters,
spells, items, feats). Each carries its own Section 15 declarations and its own cleaning
cost, and d20PFSRD alters some names for OGL compliance — which matters when matching
against Paizo's own reference.

This was written as "settle it **before** importing any bulk content, because the
attribution obligations arrive with the data and are painful to reconstruct afterwards".
The content was imported first. The warning was right, and item 2 above is the cost.

## Trademarks

This project is not published, endorsed by, or affiliated with Paizo Inc. Product Identity
— including the Pathfinder name and logo — is not licensed by the OGL and must not be used
to describe or brand this application.

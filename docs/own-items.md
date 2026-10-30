# Our own versions of the adventures' items

*Built 2026-10-29 on branch build/bestiary-rebuild, after step 6 (option D). The owner's
words, 2026-10-28: "pull some adventure path specific items and descriptions to write your
own version we dont need licencing for".*

## What may be kept, and what may not

Paizo's legal page (Carrion Crown Player's Guide, p. 2,
<https://downloads.paizo.com/CarrionCrown_PlayersGuide.pdf>) declares as Product Identity
"proper names (characters, deities, etc.), dialogue, plots, storylines, locations,
characters, artwork, and trade dress", and the rest — "the game mechanics" — Open Game
Content. Paizo's CTO posted the same standard wording on paizo.com and said some products
vary (<https://paizo.com/threads/rzs2mz9c>). A broader form in later Player Companions
("all adjectives, names, titles, and descriptive terms derived from proper nouns") was seen
only in a search snippet and **could not be confirmed** from a primary page; it is treated
as binding anyway, so "Shoanti" and "Razmiri" are not used as adjectives either.

So each item keeps the printed numbers, gets a name and words of our own, and loses any
rule that worked only for a named faith, order or place. The one place an original is
named is the row's `source`, the AoN page its numbers were read from — the catalogue
requires it (`materials.recipe_problems`), and it is a citation, not our item's name.

## How the list was made

A script over the source spreadsheet's `Gear` and `OtherGear` columns listed every piece
carried only by the 5,649 removed rows and by no rulebook row or Bestiary block: 4,310
distinct pieces, 390 in three or more blocks. Most are ordinary gear, plot props (keys,
maps, a named villain's ring) or rulebook items that happen to appear only in adventures
(Ultimate Equipment's aegis of recovery, ioun stones) — those are open rulebook content
under option D and are not this work. The setting's own items among them were read on
Archives of Nethys by a research pass, checked by a second pass (which corrected nine of
its own first readings), and written where the catalogue's grammar can carry every effect.

## Built (tools/own_items.py → content/materials/magic-items.json)

| Ours | The original | Read from | Kept | Dropped / not read yet |
|---|---|---|---|---|
| Lodestar Compass | Wayfinder | [AoN](https://aonprd.com/MagicWondrousDisplay.aspx?FinalName=Wayfinder) | 500 gp, CL 5, *light* at will | its society; +2 Survival vs becoming lost (no roll reads "lost") and the ioun-stone slot (no ioun stones) are `not_yet` |
| Wardstar Medallion | Sihedron Medallion | [AoN](https://aonprd.com/MagicWondrousDisplay.aspx?FinalName=Sihedron%20Medallion) | 3,500 gp, CL 5, +1 resistance on saves, *false life* 1/day | the runelord's scrying through it; *gentle repose* on a corpse is `not_yet` |
| Wardstar Ring | Sihedron Ring | [AoN](https://aonprd.com/MagicRingsDisplay.aspx?FinalName=Sihedron+Ring) | 35,000 gp, CL 9, +3 deflection AC, +3 resistance on saves, constant *endure elements*, glamered clothing at will | the runelords' agents and their scrying |
| Iron Saint's Mask | Holy Mask of the Living God | [AoN](https://www.aonprd.com/MagicWondrousDisplay.aspx?FinalName=Holy+Mask+of+the+Living+God) | 2,100 gp, CL 1, +2 competence Heal and Intimidate, *cure light wounds* and *cause fear* 1/day each | "If Razmir is your patron": works for anybody; the 3.5-era 84 XP cost; the maker's 5 ranks each in Heal and Intimidate are `not_yet` |
| War Paint (Black, Blue, Orange, Red, Silver, Yellow) | Shoanti War Paint | [AoN](https://aonprd.com/MagicWondrousDisplay.aspx?FinalName=Shoanti%20War%20PaintOrange) | one dose, 24 hours, CL 7: blur (20% miss) 1,800 gp; +30 ft speed, DR 1/—, fire resistance 10, +3 deflection AC, +5 Perception 900 gp each | the people who made it; putting it on as a full-round provoking action is `not_yet` |

## Not built, and why

| The original | Why not |
|---|---|
| Green and White war paint | Green adds +1 to the wearer's own inspire courage, which nothing reads as a bonus to raise; White's +4 is only against energy drain and negative energy, and no bonus condition (`effectspec.AGAINST`) says that yet. |
| Mask of the Mantis | Three charges a day shared among four powers. The catalogue has no shared pool: as four powers it would give twelve uses, which is a mechanic the book does not print. Needs a charge pool on `item_power`. |
| Glorious Tabard (lesser, greater) | Its bonuses apply only against evil outsiders and evil auras — no condition says that yet — and the book limits it to one god's crusaders. |
| Hellknight plate | For anyone without the prestige class it "functions the same as a suit of masterwork full plate", which the tables already have. |
| Sihedron tomes, runewell amulets | Unique artifacts tied to a plot's runewells; no price or making. |
| Robe of the Pure Legion | Its numbers appear only in two Society scenarios; no primary page was found. |
| Harrow deck | No rules of its own; a focus for a setting spell. |
| Pesh, flayleaf, cytillesh | Drugs and a poison with addiction rules; the game has no addiction yet. (Pesh and flayleaf's numbers are also in the GameMastery Guide, a rulebook.) |
| Named deities' holy symbols, faction badges, plot keys and maps | No mechanics; a plain holy symbol is the same thing. |

## Where they appear

Like the Core wondrous items: as recipes on the enchanting bench, and worn by name
(`magicitem.worn_specs`). No market sells catalogue wondrous items, Core or ours; that is
the catalogue's existing design, not something this adds. The app's own people (Table
14-9) spend their magic column on weapon and armour enhancement only (`rules/npc_gear.py`);
buying wondrous items with it is a separate change.

## Sources

- Carrion Crown Player's Guide (legal page): <https://downloads.paizo.com/CarrionCrown_PlayersGuide.pdf>
- Paizo forum, standard OGL declaration: <https://paizo.com/threads/rzs2mz9c>
- The AoN pages in the table above, each read 2026-10-29.

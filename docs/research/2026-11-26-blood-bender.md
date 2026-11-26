# Research note, 2026-11-26: the Blood Bender's missing abilities (owner ask A2)

Lane fix/blood-bender. The ask: "read the blood bender again it is missing things in the
abilities section. even at lvl 1 I should be able to take non-lethal dmg to give my
Extracorporeal blood armament things like corrosive, keen, or vicious."

## The source, read again

The author's own document is `Downloads/Blood Bending.docx` (the class file's `source`; the
PDF it also names is not on this machine). Extracted in full with python-docx: 121 lines,
every level of the table and all four paths. The Armament's whole sentence:

> Extracorporeal Blood Armament: Free action gauntlets dealing (Blood DMG + Fist DMG + STR
> mod) piercing/bludgeoning or non-lethal damage. Apply special abilities (Corrosive, Keen,
> Vicious, Advancing) by paying Non-Lethal costs per turn. Applies 1 blood stack per hit.

What it settles: the four abilities by name, that the price is non-lethal damage, and that it
is paid **per turn**. What it does not settle: how much, how many at once, and whether a level
gates them. The document's XML was checked for a lost equation (the DCs elsewhere were lost
that way, docs/homebrew-rules.md §4.8): the sentence has no math object; the amount was never
written.

## PF1e rules used (primary sources)

- **Keen** (CRB): doubles the threat range; piercing or slashing melee only; does not stack
  with other threat-range doublings. +1 price.
  https://legacy.aonprd.com/coreRulebook/magicItems/weapons.html#keen
- **Vicious** (CRB): +2d6 to the foe and 1d6 to the wielder on a hit. +1 price.
  https://legacy.aonprd.com/coreRulebook/magicItems/weapons.html#vicious
- **Corrosive** (APG p.287): +1d6 acid on a hit. +1 price.
  https://www.aonprd.com/MagicWeaponsDisplay.aspx?ItemName=Corrosive
- **Advancing** (Ultimate Equipment p.134): +2 price; "Once per round, when the wielder
  damages a creature in melee", a 5-foot step as a swift action, and −2 on attacks until the
  start of the wielder's next turn. Melee only.
  https://www.aonprd.com/MagicWeaponsDisplay.aspx?ItemName=Advancing
- The magic-weapon rule that the same special ability cannot be on one weapon twice (UE
  weapon special abilities). https://legacy.aonprd.com/ultimateEquipment/magicArmsAndArmor/weaponSpecialAbilities.html
- **Magus, Arcane Pool** (UM): the book's own class feature that lays special abilities on a
  weapon temporarily. 1 point, swift action, 1 minute; a budget of +1 at 1st, +1 per four
  levels; special abilities from 5th; uses do not stack and a new use ends the old.
  https://www.aonprd.com/ClassDisplay.aspx?ItemName=Magus
- **Kineticist, Burn** (OA): the book's class that pays for its abilities in non-lethal
  damage — 1 per character level per point of burn, accepted per use, capped per round and in
  total. https://www.aonprd.com/ClassDisplay.aspx?ItemName=Kineticist

## Other traditions

- **Pathfinder: Wrath of the Righteous (CRPG)** ports Arcane Weapon as one activation that
  locks the chosen enhancements in for its duration; each property costs one point of the
  enhancement budget. Source is a community wiki (fextralife), so treat the details as
  unconfirmed: https://pathfinderwrathoftherighteous.wiki.fextralife.com/Arcane+Weapon+Enchantment
- **This codebase's own precedent**: Blood Rage is a stance with a per-round upkeep
  (`drain`, spent in played rounds by `Scene._drain_periodic`), and the enchanter's layer
  (`rules/magic_layer.py`) is the one reader of keen, corrosive and vicious on a weapon row.
- **The class's own price for a +1**: Blood Booster, "+1 to the modifier — 2d6 non-lethal
  dmg" (class file; the .docx lost the number).

Abandoned elsewhere, and why it matters here: the Magus's "using it again ends the first
use" means you cannot top up a held weapon. Wrath of the Righteous keeps that limit. For a
cost paid every turn it is pointless (each property is already paid for one at a time), so
it is not copied.

## Chosen

- **Which**: the four the sentence names. Corrosive, keen and vicious are built through the
  enchanter's property documents (`content/rules/magic-properties.json`), so the armament's
  keen is the same keen a forged scimitar has. Advancing has no property document and the
  engine has no swift 5-foot step after a hit, so it is **refused with that reason**, never
  silently laid.
- **Cost**: the class's own price for +1, from Blood Booster: **2d6 non-lethal per +1 of the
  property's book price, per turn**. Corrosive, keen and vicious are +1 each, so 2d6 each.
  It is paid when chosen (this turn) and again at the top of each round of a fight while it
  holds. Blood Bond makes it non-lethal, so Blood Buffer never reduces it (a price, not an
  attack: `_pay_hp_cost`'s rule).
- **Duration**: until dismissed (choose it again), until the armament is dismissed, or until
  time passes out of a fight. Nobody pays "per turn" across an hour's walk, so a stretch of
  time with no turns lets it go, and the end is told.
- **How many**: no cap but the price. The text sets none, and the Magus budget is a pool the
  Blood Bender does not have. The same ability cannot be laid twice (UE).
- **Level**: Control Blood 1, with the armament itself. The text puts the special abilities
  in the armament's own sentence and gives them no level.

## Rejected

- The Magus budget (+1 at 1st, a property only from 5th). The owner says a level-1 bender
  must be able to do it, and the text names no budget.
- 1d6 per +1 (a guess of mine), and Burn's 1 per character level. Both are invented numbers,
  and the class prints its own figure for a +1.
- Blood Booster's doubling for each further +1. That rule is about stacking one stat. Reading
  it onto different properties is a stretch, so it is listed as an owner call instead.
- Pay once and hold for a minute (the Magus's duration). The text says per turn.
- A separate store of armament properties. One `ActiveEffect` per property, through
  `Actor.apply_effect`, read by the granted weapon's row. Remove it and keen evaporates.

## Second pass (check of the above)

I re-read the sources for the two claims the build rests on:

1. Advancing is +2 and melee-only (AoN page fetched).
2. Arcane Pool's limits are as quoted (AoN magus page fetched).

The Wrath of the Righteous details come from a wiki, and I say so above. Blood Booster's
"2d6" comes from the class JSON, not the .docx: its sentence in the .docx is "+." with the
number lost. Its origin, probably the PDF, could not be confirmed. So the price rests on a
number this machine cannot trace to the author. That is the first owner call.

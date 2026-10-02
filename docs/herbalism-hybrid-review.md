# Herbalism: the hybrid review

Written 2026-10-02 by Lane A of the herbalism revamp, for the owner to check by hand.
The tags live in `content/ingredients/herbs-and-parts.json`; this page is generated from that file, so the routes below are the ones that ship.

**The rule** (`docs/herbalism-revamp-plan.md` section 5.2, and the owner's ruling): an entry is `hybrid` when any of its effects is magical (planar flora, monster parts, anything supernatural), and it then appears on both the herbalist's and the alchemist's shelves. Every structured effect carries a `route`. The herbalist can carry an effect only by `ingest`, `skin`, `eyes`, `wound` or `inhale`; an `external` effect (it reaches outside the body, or changes what others perceive) is alchemy's and is dropped from a herbal product.

Everything was tagged by reading each entry's own text. No model was used.

## The counts

- **63 hybrid entries** of 161: all 20 monster parts and 43 plants and fungi.
- **Routes, all entries:** ingest 121, external 60, skin 36, wound 26, inhale 16, eyes 6 (265 effects).
- **Routes, hybrid entries:** external 45, ingest 30, skin 12, inhale 8, eyes 4, wound 1.
- **Parts:** leaf 63, flower 18, root 17, berry 12, sap 9, bark 8, fungus 7, organ 5, seed 4, horn 4, bone 3, gland 3, resin 2, feather 2, liquid 1, eye 1, scale 1, shell 1.

## The doubtful calls first (24)

These are the ones where a reasonable reading goes the other way. Each says which way it was called and what the alternative is.

| Entry | Kind | Part | Each effect, by route | Why |
|---|---|---|---|---|
| Gloomwraith Tendril | monster part | organ | `ingest`: -3 saves against fear effects due to lingering dread for 4 hours<br>`ingest`: +4 Perception against invisible or hidden creatures, while the syrup lasts for 4 hours | The plan (section 5.2) cites this as route `eyes`, an eye cream. The entry's own text says the tendrils are boiled into a syrup and ingested, so both effects are tagged `ingest`. Either way the herbalist can make it; the question is the product form. |
| Shadowvine | herb | leaf | `external`: +5 Stealth for 3 hours | Ingested, but the +5 Stealth is the user blending into shadows: it changes what others see, so `external` (alchemy only). Arguably a body effect like night vision. |
| Mistveil Fern | herb | leaf | `external`: -3 physical damage dealt due to their reduced solidity for 10 minutes<br>`external`: +2 Armour class partially incorporeal; blows pass part-way through for 10 minutes | Taken by inhaling spores (a herbal route), but partial incorporeality is the owner's own example of external. Both effects `external`. |
| Cockatrice Beak | monster part | horn | `external`: Immune to difficult terrain for 6 hours | The paste goes on boots, not skin, and the effect (ignoring difficult terrain) works through the gear. Tagged `external`. Could be read as a body effect on the wearer's movement. |
| Dracolisk Scale | monster part | scale | `external`: -2 Dexterity for 8 hours | Powder sprinkled over armour, not the body. Its one structured effect (the -2 Dex drawback) tagged `external` with the armour working. The resistance to petrification is not a structured effect yet. |
| Ice Lotus | herb | flower | `external`: DC 35 | Icewalker oil gives spider climb on ice. Movement magic, like flight, so `external`. If the oil is rubbed on the feet it could be `skin`. |
| Frostbloom | herb | flower | `skin`: -3 Dexterity for 4 hours<br>`skin`: Resist fire for 4 hours | Hybrid only because 10 points of fire resistance is spell strength. Route `skin`, per the owner's example. If this is ordinary herbcraft, unmark hybrid. (The stored resistance amount is 0; the text says 10.) |
| Starbloom | herb | flower | `ingest`: -4 checks in bright environments for 6 hours<br>`ingest`: +2 Will moonlit clarity, while the tea lasts for 1 hour | Hybrid because seeing in complete darkness is darkvision. Brewed as a tea, so `ingest`. Chasmyre Leaf (low-light vision) was left non-hybrid by the same reasoning. |
| Ironbark Moss | fungus | fungus | `ingest`: +2 Armour class natural armor bonus for 2 hours | Hybrid because chewing it for +2 natural armour is barkskin by another name. Route `ingest`. |
| Aelfengrape | herb | berry | `ingest`: DC 15 | Hybrid for the glow and the elven wizards who made it. Its only structured effect is a DC the parser found; tagged `ingest` because the grapes are eaten. The light is not a structured effect. |
| Cloth of Gold | herb | flower | `ingest`: Speak with animals for one round; chew a flower or six leaves<br>`ingest`: +4 Handle Animal while the effect lasts for 1 minute | Speak with animals is a spell effect, so hybrid. It is chewed and works in the chewer's own head, so `ingest`, not external. |
| Djinn Blossoms | herb | flower | `external`: +2 saves to resist inhaled poisons, gases, and spells for 24 hours<br>`skin`: +2 Charisma skill for 24 hours<br>`skin`: DC 20 | Planar. The worn blossom's breeze guards against gases from outside the body, so `external`. The perfume (+2 Charisma skills, and its craft DC) is worn on the skin, so `skin`. |
| Banshee Wail Essence | monster part | liquid | `inhale`: +5 Intimidate for 4 hours | Inhaled, and the effect is the user's own amplified voice, so `inhale`. Arguably it changes what others hear, which would make it external. |
| Henna | herb | leaf | `skin`: Magically reactive pigment, fit for verdexes and tattoo-work<br>`skin`: +2 Craft preparing magical concoctions that call for it | "Magically reactive" makes it hybrid. A tattoo pigment, so both effects are `skin`. |
| Harpy Vocal Cord | monster part | organ | `ingest`: -2 Diplomacy for 24 hours<br>`external`: DC 15 | Charm person cast on another is `external`. The -2 Diplomacy drawback is `ingest`. A herbal product would carry only the drawback, which may mean the herbalist should not be offered it at all. |
| Salamander Ember Gland | monster part | gland | `external`: 1d6 fire damage<br>`ingest`: 1d4 fire damage | The 10-ft burst of flame is `external`; the 1d4 burn to the drinker is `ingest`. A herbal product would carry only the drawback. |
| Wendigo Antler | monster part | horn | `external`: -2 Constitution due to the antler’s lingering curse for 1 hour | Scattered dust making an aura that repels undead is external. Its one structured effect is the -2 Con curse on the user, tagged `external` with the aura it pays for, so a herbal product never carries a cost with no benefit. |
| Imperial Willow | herb | bark | `ingest`: Heals 4 non-lethal damage<br>`external`: DC 20 | The bark tea (heals 4 nonlethal) is ordinary herbcraft, `ingest`. Hybrid only for the heartwood that augments a druid's spell (`external`). |
| Spriggan Tree | herb | bark | `ingest`: DC 15 | Hybrid for the acorns' enlarge magic, which is not a structured effect yet. The structured effect is the bark tea against parasites, `ingest`. |
| Twilight Dagger | herb | sap | `ingest`: A cactus of magic-soaked lands; its sap carries a faint charge<br>`ingest`: 1d2 temporary hit points for 1 hour | Hybrid only because it grows in magic-soaked lands and its sap "carries a faint charge". Both effects `ingest`. |
| Cave Star | herb | leaf | `external`: DC 10 | Hybrid because its effect is light (the owner lists illumination as external). A glowing plant could be plain bioluminescence; if so it is a non-herbal external like the ink and the glue. |
| Fey Cherry | herb | berry | `ingest`: DC 15 | Protection from evil, eaten: a ward, but on the eater, so `ingest` (the owner: "an immunity swallowed = ingest"). |
| Coldwood | herb | bark | `external`: Iron-strong wood with none of iron's harm to fey; weapons and armour can be made of it<br>`external`: +1 Will vs fey magic, carrying worked coldwood for 1 hour | Fey-grown wood for weapons and armour. Tagged part `bark`, because the vocabulary has no `wood`, which also makes it a salve base under the bark rule. Both effects act through worked items, `external`. |
| Rowan | herb | bark | `external`: Rowan-wood items always get a save against magic that would affect them<br>`external`: +2 Will vs spells, wielding worked rowan for 1 hour | Wood that protects against magic. Part `bark` for the same reason as Coldwood. Both effects act through worked items, `external`. |

## The rest of the hybrids (39)

| Entry | Kind | Part | Each effect, by route | Why |
|---|---|---|---|---|
| Basilisk Eye | monster part | eye | `eyes`: -4 Perception for 6 hours<br>`eyes`: Immune to gaze attacks for 6 hours | Monster part. A paste for the eyes against gaze attacks: `eyes`, the body's own defence. |
| Behemoth Hide | monster part | organ | `skin`: +3 Armour class natural armor bonus for 12 hours | Monster part. Tanned and worn as a patch for natural armour: `skin`. Part `organ` (no `hide` in the vocabulary). |
| Blackthorn | herb | leaf | `external`: +2 Will vs the powers of evil outsiders and demons, while strewn or worn for 1 hour | Repels evil outsiders "as garlic repels vampires", strewn or worn: a ward in an area, `external`. |
| Blueweed | herb | leaf | `external`: +1 Will vs curses and evil magic, once the object is ritually purified for 1 hour | Powder sprinkled to ritually purify an object: works on the object, `external`. |
| Breeam | herb | bark | `external`: The smoke turns undead in a 10 ft diameter for 1d4 minutes, as a 1st-level cleric<br>`external`: +2 Will vs fear caused by undead, within the smoke for 10 minutes | Smoke that turns undead in an area: `external`. |
| Chimera Horn | monster part | horn | `inhale`: +3 saves against chaotic magic for 4 hours<br>`inhale`: -3 Wisdom for 4 hours<br>`inhale`: Causes prone for 4 hours | Monster part, snorted: all three effects `inhale`. |
| Dire Boar Tusk | monster part | bone | `inhale`: +3 Strength for 1 hour, but the user becomes… | Monster part, snorted: `inhale`. |
| Dreamcap | fungus | fungus | `ingest`: +3 knowledge checks related to future events for 6 hours<br>`ingest`: Causes dazed for 1 minute | Grows in enchanted groves; prophetic dreams. Eaten: `ingest`. |
| Dryad's Tears | herb | berry | `external`: The odour repels lycanthropes as blackthorn repels outsiders<br>`ingest`: +2 Fortitude vs contracting lycanthropy for 1 hour | The odour repels lycanthropes (`external`); the save against lycanthropy is the eater's own (`ingest`). |
| Elysium | herb | leaf | `external`: Where it grows, the ground is under an antimagic field; pulled up, the effect ends<br>`external`: +2 Will vs spells while the fresh plant is carried for 1 hour | An antimagic field where it grows, and while carried: both `external`. |
| Faerie Grass | herb | leaf | `external`: DC 20 | Stepping on the patch disorients: the growing plant acts on passers-by, `external`. |
| Flame Clove | herb | root | `external`: DC 15 | Elemental fire. Keeps food hot and doubles alchemist's fire: `external`. |
| Frostgiant Marrow | monster part | bone | `ingest`: -2 Initiative for 12 hours<br>`ingest`: Resist cold 10 for 12 hours | Monster part, boiled into a broth: `ingest`. |
| Glowvine | herb | flower | `external`: DC 20 | Blossoms shed torchlight: `external`. |
| Grave Mold | fungus | fungus | `ingest`: +3 Fortitude bonus against all disease for 6 days | Psionic, can raise a simulacrum. The ounce eaten against disease is `ingest`. |
| Griffon Talon | monster part | horn | `skin`: +2 Attack rolls with melee weapons for 2 hours | Monster part, a salve on the hands for melee attacks: `skin`. |
| Hawthorn | herb | flower | `eyes`: Pollen in the eyes reveals faeries and fey creatures<br>`eyes`: +2 Perception to notice fey for 1 hour | Pollen in the eyes sees fey through invisibility: `eyes` (the owner's "seeing the unseen via an eye salve"). |
| Horsetail | herb | leaf | `external`: +1 Will vs curses and evil magic, once the object is ritually purified for 1 hour | Same text as Blueweed: ritual purification of an object, `external`. |
| Hrondis' Tears | herb | flower | `external`: A flower of one rite, known to few<br>`external`: +1 Will while its rite is observed for 1 hour | Wrapped on a weapon's hilt so it strikes incorporeal undead: `external`. |
| Hydra Gall | monster part | organ | `ingest`: -3 Constitution for 1 hour<br>`ingest`: Heals 1d4 hit points<br>`ingest`: Causes nauseated | Monster part, distilled and drunk: `ingest`. |
| Hypericum | herb | leaf | `external`: +2 Will vs possession and the influence of summoned spirits for 1 hour | Sprinkled on a place or person for exorcisms and summonings: `external`. |
| Kraken Ink | monster part | gland | `skin`: -2 Charisma for 8 hours | Monster part, runes inscribed on the skin for water breathing: `skin`. |
| Lakeleaf | herb | leaf | `external`: DC 15 | Rubbed into meat, or doubles gentle repose: works on things and spells, `external`. |
| Manticore Spine | monster part | bone | `external`: -4 Attack rolls on struck targets for 1 minute<br>`skin`: DC 12 | Monster part. A tincture on ammunition is a coating that acts on a target (`external`); the mishandling sting is `skin`. |
| Menhirite | herb | sap | `wound`: Heals 6 hit points<br>`external`: Causes dead | Planar. The sap heals a wound (`wound`); the ring that raises the dead acts on corpses (`external`). |
| Nahre Lotus | herb | flower | `external`: 2d6 Constitution damage<br>`external`: Fortitude DC 12<br>`external`: Causes dead | Planar. A dead lotus thrown as a blight: all three effects `external`. |
| Orevine | herb | root | `external`: DC 20 | Planar. Draws metal out of the ground: `external`. |
| Phoenix Feather | monster part | feather | `inhale`: -3 concentration-based checks for 2 hours<br>`inhale`: Immune to fire damage for 2 hours | Monster part, burned and inhaled for fire immunity: `inhale`. An immunity taken into the body is herbal. |
| Rue | herb | leaf | `ingest`: Second sight: spirits and magic are visible for the duration<br>`ingest`: +2 Perception to notice spirits and magical auras for 1 hour | Second sight, brewed and drunk: `ingest`. |
| Salamander Orchids | herb | flower | `skin`: 1d6 fire damage<br>`external`: DC 30 | Planar. Touching it burns (`skin`); used to craft flaming weapons (`external`). |
| Sphinx Whisker | monster part | feather | `inhale`: +4 Intelligence for 3 hours | Monster part, burned and the smoke inhaled: `inhale`. Part `feather` (no `hair` in the vocabulary). |
| Sukake | herb | berry | `ingest`: DC 13 | Maximizes a divination. The structured effect is its narcotic save, from eating the fruit: `ingest`. |
| Tahtoalehti | herb | flower | `external`: DC 40 | The wish: `external`. |
| Tamarisk | herb | leaf | `external`: The burning plant repels reptilian creatures, snake to dragon<br>`external`: +2 Will vs the abilities of reptilian creatures, in the smoke for 10 minutes | Burning it repels reptilian creatures: `external`. |
| Trollheart Sap | monster part | organ | `ingest`: Heals 2 hit points<br>`ingest`: Fast healing 2 for 10 minutes | Monster part, distilled into a tonic for fast healing: `ingest`. Part `organ` (the heart). |
| Vervain | herb | leaf | `external`: Burned as incense: +1 effective level to turning or rebuking undead nearby, for an hour<br>`external`: +1 Will vs the abilities of undead, within the incense for 1 hour | Incense that strengthens turning undead in the area: `external`. |
| Wispweed | herb | leaf | `external`: DC 15 | Smoke for telepathy between those inside it: `external`. |
| Wyrmfang Venom | monster part | gland | `external`: 1d8 poison damage<br>`skin`: DC 15 | Monster part. Applied to a weapon (`external`); the handling risk is `skin`. |
| Xian Tao | herb | berry | `ingest`: Immune to poison and disease, large bonuses to saving t | Peach of immortality, eaten: `ingest`. |

## Calls on entries that are not hybrid

Not part of the hybrid review, but judgement calls of the same kind.

| Entry | Kind | Part | Each effect, by route | Why |
|---|---|---|---|---|
| Damiana | herb | leaf | `inhale`: +1 Charisma within the incense vapours for 1 hour | Incense whose vapours raise Charisma for anyone in them. An area, but each person inhales it into their own body, and it is plain herbcraft: `inhale`, not hybrid. |
| Levisticum | herb | leaf | `ingest`: +2 Diplomacy toward the one who served the potion for 1 hour | A love potion makes the drinker warm to the one who served it. It acts in the drinker's own body (`ingest`); it is not the user charming another. Myrtle the same. |
| Myrtle | herb | leaf | `ingest`: +2 Diplomacy toward the one who served the potion for 1 hour | As Levisticum. |
| Calendula | herb | flower | `ingest`: +2 Sense Motive in matters of the heart for 1 hour | "Helps divine someone's future lover": folk divination. The structured effect is Sense Motive, `ingest`. Not hybrid. |
| Mistletoe | herb | berry | `ingest`: +3 saves against any transformation process, whether…<br>`ingest`: 1d4 Constitution damage<br>`ingest`: 1 Constitution damage<br>`ingest`: DC 19 | +3 against transformation including polymorph, from an extract drunk: `ingest`. Left non-hybrid because the protection is the body's own. |
| Tugwort | herb | root | `ingest`: Resist slashing 3 for 8 hours | Resistance 3 against slashing for 8 hours, from an infusion: `ingest`. Left non-hybrid; could be read as magical. |
| Chasmyre Leaf | herb | leaf | `eyes`: Low-light vision for 1 hour, crushed and applied to the eyelids<br>`eyes`: +2 Perception in dim light for 1 hour | Low-light vision from a leaf on the eyelids: `eyes`, natural, not hybrid. |
| Scorpion | herb | shell | `ingest`: +2 Fortitude vs poison; powdered and brewed for 1 hour<br>`ingest`: Eases an existing poisoning | Filed as kind `herb`, but its text is a scorpion's powdered body. Part `shell`. The kind looks wrong. |

Twelve non-hybrid entries carry an `external` effect because what they do is not the taker's body: Darkroot (glue), Dragon Flower (the growing flower's stench over an area), Goblin Rouge (ink), Halfling Thistle (rust remover), Golden Maple Leaves (an additive for alchemical items), Lish Nut (the eater's smell sickens vermin), Selpeme Blossom (the scent frightens animals), Monkshood and Meadow Giant (blade coatings), and the poison boosters Dwarven Oak, Orticusp and Wild Fireclover. They are pinned by name in `tests/test_ingredient_tags.py`. Their poisons and coatings are alchemy's under the owner's rule; whether the alchemist should be able to reach them (by marking them hybrid) is an open question.

## Parts the text does not name

19 entries never say which part is used, and were left at the contract's default, `leaf`: Aconite, Allnight, Amaranth, Anise, Belladonna, Blackthorn, Cave Star, Dittany, Halfling Thistle, Henna, Monkshood, Orticusp, Sherpa's Friend, St. John's-Wort, Tamarisk, Wittlewort, Wolfweed, Wordwood, Woundwort. Some have a well-known answer outside the text (anise seed, belladonna berry, aconite root); the text was followed rather than real-world herbalism, as the tagging prompt asks.

## Vocabulary gaps

The part vocabulary is fixed by `docs/herbalism-contracts.md` section 2. Four kinds of thing in the corpus have no word of their own, and were filed under the nearest:

- **wood** (Coldwood, Rowan) as `bark`, which also makes them salve bases;
- **hide** (Behemoth Hide) as `organ`;
- **hair or whisker** (Sphinx Whisker) as `feather`;
- **stem or stalk** (Golden Embrace, Meadow Giant, Mallow's shoots, Wild Fireclover) as `leaf`.

## Effects that look misparsed

Noticed while tagging, left alone because fixing effects is outside this pass:

- Barbarian Chew applies `stunned` (the text says it extends a rage);
- Chimera Horn applies `prone` (the text says "prone to erratic behavior");
- Frostbloom's fire resistance is stored as 0 (the text says 10);
- Menhirite and Nahre Lotus apply `dead`, and Skull Orchid removes it;
- 55 `save_gate` effects carry the parser's note "the source names a DC without saying which save"; many of those DCs are the crafting DC printed at the end of the text ("DC: 15."), not a save. Each was routed by how the entry's main use is taken.

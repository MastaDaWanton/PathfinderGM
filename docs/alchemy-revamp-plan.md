# Alchemy revamp: the plan

Drafted 2026-10-05 from ten rounds of the owner's answers (`docs/alchemy-questions.md`, all
binding). The inventory it answers is `docs/alchemy-inventory.md` (cited **inv §n**), and the
prior-art sweep is `docs/alchemy-prior-art.md` (cited **art §n**). The interface half is
`docs/alchemy-ui-plan.md`. The lane contracts are `docs/alchemy-contracts.md`. Nothing here is
built yet.

Numbers marked **(proposed)** are my defaults. They need tuning or a ruling, and every one lives
in a rule row so it can be tuned without a code change. Everything else is the owner's decision
as given. Where a new mechanic needed a source, the primary source is cited in place and listed
again in §22.

This plan follows `docs/herbalism-revamp-plan.md` and `docs/blacksmithing-revamp-plan.md`
wherever the owner said "as herbalism" or "as the forge". It says so rather than repeating them.

The code it refers to is master at 1f88ada, merged into `alchemy/research` (488b293). That
includes the forge revamp, so `rules/materials.py`, `rules/knowledge.py`, `rules/forge_items.py`,
`29-bench-core.js` and `bench-stage/` all exist and are reused here.

---

## 1. What alchemy is for

The same three kinds of fun as herbalism and the forge, in the same order:
1. **hands-on craft** at the bench;
2. **discovery** of what reagents do and which formulae exist;
3. **a way to be seen** through the world's renown system. The class hands out nothing
   automatically.

**Alchemy's own flavour is containment** (owner, Q1.1). Volatile things are handled well:
- a reaction is held inside its band;
- the stakes of a volatile step are stated before the roll;
- a failure by 5 or more is a real flare, not a sentence.

Herbalism is about *what you brew*; smithing is about *what you put together*. Alchemy is about
**what you dare to combine, and what it carries forward**: traits travel from reagent to salt
to flask, and the alchemist chooses what goes into the bottle.

**The boundaries** (owner, Round 2):

| Boundary | Ruling |
|---|---|
| Which PF1e alchemy | **Craft (alchemy) items and potions.** Bombs, mutagens and extracts wait for a PF1e alchemist character class, which the app does not have (inv §0.10). |
| Herbalism | **Body against outside.** Herbalism keeps what works on or in the body. Alchemy keeps potions, transmutation, and anything that reaches outside. The door is **two-way**: the 63 hybrid herbs sit on the alchemy shelf, and their 49 `external` effects finally have a bench (inv §0.7). |
| Poisons | **Split by route.** Herbalism owns the body's own (ingested, on a wound). Alchemy owns the ones that reach outside (thrown, inhaled clouds, contact traps). |
| Enchanting | **Single-use is alchemy's** (potions, oils, elixirs, flasks). Anything that keeps working is enchanting's. The enchanter keeps consuming a `holds_spell` potion as a stand-in for knowing the spell (enchanting answers, Round 1: a missing prerequisite is +5 DC, and a potion holding the spell meets it). |

**And it has to matter in play.** Today a bought alchemist's fire does nothing. A brewed one
deals 2d6 with no attack roll. A potion of haste narrates its speed and costs 1,750 gp of
materials to make something that sells for 60 gp (inv §0). The engine half (§16) is not
optional. Without it, the data pass would ship 139 well-formed documents that still do nothing.

---

## 2. The owner's decisions (2026-10-05)

Condensed from `docs/alchemy-questions.md`, "The owner's answers". Questions are cited by
number.

| Area | Decision |
|---|---|
| Fun (Q1.1) | Craft, then discovery, then a way to be seen. Flavour: containment. |
| Scope (Q1.2) | Craft (alchemy) items and potions. No bombs, mutagens or extracts. |
| Spell potions, who (Q1.3) | **Anyone, through a learned formula.** The formula and its reagents stand in for the spell, as the enchanter's rule does. |
| Numbers (Q1.4) | **The book's numbers win, with house top-ups**, as the forge. |
| Hybrid herbs (Q2.1) | Two-way door. |
| Magic items (Q2.2) | Single-use is alchemy's. |
| Poisons (Q2.3) | Split by route. |
| Transmutation (Q2.4) | A **Transmute** method: a material into another of its kind, one band rarer, at a cost. Level 3. |
| Methods (Q3.1) | **Calcine, Dissolve, Distill, Filter, React, Sublime, Bottle**, plus **Transmute** (and Assay, which is knowledge, not a craft step). Precipitate folds into Dissolve and Filter. Stabilize becomes a **stabilizer ingredient**. Catalyze becomes a **catalyst trait** that is never spent. |
| Volatility (Q3.2) | **Made real.** A failed roll by 5 or more on a volatile step applies the stated mishap to the alchemist, through the effect system. A minigame miss only lowers quality. |
| Concentration (Q3.3) | **As herbalism.** Two make one at ×1.5, uncapped, each step harder. |
| Handler's tax (Q3.4) | **`toxic_to_handle`**, a working trait that hurts the alchemist at the bench unless they are protected. |
| Product families (Q4.1) | **Potion, oil, splash flask, cloud, tool**, and **salts and spirits** as sellable intermediates. |
| Spell potions, how (Q4.2) | **A formula plus reagents that carry the right trait** ("any reagent with lightness serves a potion of fly"). |
| Which spells (Q4.3) | **The owner's own rule:** "I want potions to hold any spell and the max spell level should be 1/2 alchemy level with a minimum of 1. I understand that this allows personal range spells to become ranged, i am okay with this." |
| Prices (Q4.4) | Book prices for book items, the tier ladder for house products, quality multiplying both, material prices checked against them. |
| Reagent discovery (Q5.1) | **Assay** plus the herb routes. Volatile and toxic assays are dangerous for real. |
| Formula discovery (Q5.2) | **Books and experiment.** A fixed table, never secret per world. |
| Hints (Q5.3) | **A count of the possible formulae, never their names.** |
| Starting knowledge (Q5.4) | Homeland reagents, and the four book classics as formulae. |
| Levels (Q6.1) | L1 Dissolve, Calcine, Bottle, common and uncommon, the four classics, 1st-level potions. L2 Distill, Filter, React, rare and exotic. L3 Sublime, Transmute, legendary. Spell level grows by the Q4.3 rule. |
| Perks (Q6.2) | Herbalism's four (potency, duration, quality, yield), plus **Containment**. |
| Where (Q6.3) | **Field kit plus a laboratory.** A lab is rented in town by the hour, or owned. It is needed for rare and above, and for Distill and Sublime. |
| Quality on book items (Q6.4) | Stronger, longer, softer drawbacks, worth more. **Each tier above Sound adds +1 caster level** to a spell potion. |
| Traits (Q7.1) | **At least three discoverable traits per reagent, one a drawback, in two layers**: product traits and working traits. |
| Inheritance (Q7.2) | **Atelier's model.** Family slots, and the player picks. Traits travel through intermediates. Same-named traits add, capped by level. Finished goods are dead ends. |
| Apparatus (Q7.3) | Working traits only. **Vessels decide the product family.** Catalysts are never spent. |
| Inert and legendary (Q7.4) | Three traits each. **Prima materia** gets a wild trait. **Philosopher's mercury** becomes a catalyst that is never spent. |
| Throwing (Q8.1) | **The book's splash rules**: a ranged touch attack, 1 splash within 5 ft, and a miss lands nearby. |
| Effect types (Q8.2) | **All executable**: speed, senses, light, area clouds, burning next round, glued and entangled, "against X only". |
| Shop items (Q8.3) | **The same documents as crafted ones**, bought at Sound quality. |
| Stacking (Q8.4) | **The owner's answer:** "Normally no but if you have the stacking house rule switched on then yes." By the book, alchemical bonuses take the highest. With `magic_stacking` on, they stack. It is one switch, read by the stacking funnel, not a second rule. |
| Bench (Q9.1) | Its own bench, from the shared parts. The old `/craft/` Alchemy tab retires. |
| Stage (Q9.2) | Field kit and laboratory, with **procedural 3D glassware whose liquid colour and level are live**. |
| Minigames (Q9.3) | **Real operations**, each a band you stop inside. Generous to start, with numbers and bars as well as colour. |
| Volatile work (Q9.4) | **A visible reaction gauge, and a real flare on a failed roll.** Reduced motion is respected. |
| Old saves (Q10.1) | **Convert.** |
| Old potions (Q10.2) | **Keep every potion id and `holds_spell` exactly.** |

**Cross-craft rulings that bind this plan** (herbalism, the forge, and the leatherworking
rounds):
- the d20 decides success;
- one minigame per method climbs quality, and it is always played;
- three levels, then endless perks;
- real intermediates;
- typed effect documents with at least three discoverable traits;
- book wins, plus house top-ups;
- one material, many shelves;
- no model authors a number;
- world-agnostic fixes;
- an **"In progress" section for every craft**, with game-time countdowns until collected
  (owner, leatherworking Q9.3);
- a **metal tag** on armour and weapons (owner, leatherworking Q7.3).

The last two are **shared infrastructure that the enchanting lanes build first**. This plan
consumes them through a named interface (§16.11, contracts §10) and does not build them.

---

## 3. What the research changes

From `docs/alchemy-prior-art.md`, plus the primary sources checked for this plan (§22):

- **Fix the book items before adding anything** (art §6.2). Eleven book-against-catalogue
  contradictions are listed in questions §11. §5.4 is that fix, done first and done by hand.
- **Traits through intermediates is Atelier's**, and Atelier also shows the cap and the dead
  end (art §3, §6.3). Ryza adds same-named levels, passes traits through intermediates even
  while they are inactive, and makes finished goods "DEAD ENDS". Yumia took traits out of
  synthesis and players called it shallow, so traits stay bound to the materials that carry
  them.
- **A fixed formula table keyed on tags**, never secret per world:
  - Minecraft dropped per-world brewing as "not much fun".
  - Noita's per-seed recipes fell to the data files in about a week.
  - Noita's everyday reactions key on tags.

  So formulae key on **essences**: tags in the one vocabulary (§5.3, §10).
- **Delivery form is a choice of vessel, never an inference** (art §4, §6.6). Minecraft's
  gunpowder makes a splash potion and dragon's breath a lingering cloud. Today the bench infers
  drink, throw or coat from what happens to be harmful, which is how a sunrod became a blade
  coating (inv §0.2).
- **Failure that leaves nothing keeps being removed** (art §0.5, §6.5). Monster Hunter, Outward
  and Morrowind all show it. So a minigame miss after a successful roll never costs materials.
  The book's fail-by-5 rule stays, and the mishap is the one place alchemy keeps chance, stated
  before the roll.
- **Transmutation needs a budget, not a lockout** (art §6.7). WoW walked back real-time
  transmute cooldowns three times. Transmute is costed in materials and game time.
- **Real operations give honest bands** (art §5):
  - distillation's heads, hearts and tails;
  - calcination to a white calx;
  - the sublimate re-forming as a crust above;
  - the colour stages of the Great Work.

  Every crafting minigame the earlier sweeps found was softened after launch, so the bands
  start generous.
- **What the book says, checked for this plan** (§22):
  - the splash weapon rules and the 1d8 miss scatter;
  - alchemist's fire's "full-round action … DC 15 Reflex … rolling on the ground +2";
  - the tanglefoot bag's glue and its 2d4-round brittleness;
  - fog cloud's 20% / 50% concealment;
  - the light levels and the sunrod's 30 / 60 ft;
  - the potion price, and "never lower than the minimum level needed to cast the needed spell";
  - the alchemist's lab's +2;
  - the wizard's copying rules (DC 15 + spell level, the scroll is used up on success);
  - the APG alchemist's formula book, which "add[s] formulae … just like a wizard adds spells".

---

## 4. Progression

### 4.1 Levels 1 to 3

| Level | Methods | Materials | Formulae | Where |
|---|---|---|---|---|
| 1 | **Dissolve, Calcine, Bottle, Assay** | common, uncommon | the four classics known from the start; any classic once learned; 1st-level spell potions | field kit |
| 2 | **Distill, Filter, React** | rare, exotic | (spell level by the Q4.3 rule, §11.1) | Distill at a laboratory |
| 3 | **Sublime, Transmute** | legendary | | Sublime and Transmute at a laboratory |

- **Mastery thresholds:** 25 to reach level 2, and 65 to reach level 3. These are herbalism's
  and the forge's, kept equal on purpose ("the two tracks are meant to pace the same").
- **Removed:**
  - the level 4 and 5 rows;
  - the 25/65/50/100 curve;
  - the `legendary-work` milestone and its deed;
  - Seal (renamed Bottle), Precipitate, Stabilize and Catalyze as methods.
- **Their tests are retired and their defects re-pinned against the new gates.** That is what
  `test_legendary_catalyst.py` was for herbalism.

### 4.2 Endless levels (4 and up)

Two perk picks per level, and the same perk twice is allowed. Perks are stored on
`Progress.perks` and read live, exactly as the other two crafts (stage 8's rule: never a stored
`ActiveEffect` per perk). `content/world-classes/alchemist.json` gains the `endless` block with
the herbalist's shape (`base` 50, `step` 10, `picks_per_level` 2).

| Perk | Per pick **(proposed)** |
|---|---|
| Potency | +5% to the potency multiplier of everything you make (benefits only) |
| Duration | +10% to duration |
| Quality | +1 to the quality ceiling |
| Yield | +5% chance per Bottle of one extra unit. The engine rolls it and shows the roll. |
| **Containment** | −1 DC on volatile steps, and the mishap is one die step smaller (1d6 → 1d4 → 1d3 → 1, never below 1 point). |

**The endless levels also raise the spell level.** The owner's rule (§11.1) reads the
Alchemist level itself, so endless levels carry spell potions up to 9th level at Alchemist 18.
That is the alchemy-specific reason the endless levels matter more here than at the other
benches.

### 4.3 The quality ceiling

As herbalism §4.3 and `worldclass.CEILING_BY_LEVEL`:
- level 1 is Fine;
- level 2 is Superior;
- level 3 is Flawless;
- each Quality perk adds one step (Flawless +1, +2 and so on).

The minigame score is spread under the ceiling, and the server turns it into the tier
(`crafting.tier_from_score`).

### 4.4 Mastery sources

As herbalism §4.4, through `worldclass.award_step` and `award_bonus`:

| Source | Award |
|---|---|
| Each successful step | 1, plus 1 per rarity band above common |
| Quality | +1 at Superior, +2 at Flawless or higher |
| Firsts | +3 each: first property learned, first product family made, first reagent worked, **first formula written** (by any route) |
| Reading an unread formulary | +5 once per book (§10.5) |

`REPEAT_LIMIT` and `MISHAP_LIMIT` stay, keyed on (method, material). The legacy per-recipe
`worldclass.award` stops being called for the alchemist; the engine's `craft` op keeps it only
for old saves.

---

## 5. The materials pass

### 5.1 Today

All counts are measured, from inv §3:
- **139 materials:** reagent 46, gland 23, solvent 16, vessel 13, salt 11, treatment 11,
  essence 10, catalyst 9.
- **72 effect entries:** 67 executable and 5 narrative.
- **Per material:**
  - 70 have no effects at all;
  - 5 are narrative only;
  - 61 carry one effect;
  - 3 carry two;
  - **none carries three**.
  - In total, **75 of 139 (54%) carry nothing executable.**
- **40 materials** appear in no effect and no spell potion. They are recipe-table names, or
  unused.
- **30 effectless materials** exist only as spell-potion keys: the animal hairs, feathers, gum
  arabic, talc and the rest.
- **No working layer** exists (how a reagent behaves at the bench).
- **The handler's tax lands on the drinker.** Quicksilver's and lead dust's "to the handler"
  damage is a product effect, so whoever drinks or is hit by the product pays it.
- **Notes the engine never reads:** "undead only", "burns again the following round", "a
  15-foot cone".
- **The alchemist does not read through the shared door.** `rules/alchemist.py:256` has its own
  loader. Because `knowledge.MATERIAL_LISTS` (`rules/knowledge.py:61`) knows only the forge's
  fields, `knowledge.property_keys` returns **0 for all 139** (re-confirmed on 488b293).

### 5.2 The material document

Every field defaults, so an old file still loads. This is the rule that `herbprep.Prep` and the
forge's material document both follow. The document is read through **`rules/materials.py`**,
the one door the forge built, so the alchemist's private loader retires.

```json
{
  "id": "brimstone", "name": "Brimstone", "kind": "reagent", "tier": "common",
  "form": "powder", "material": null,
  "color": [0.86, 0.78, 0.22],
  "product": [
    {"type": "damage", "dice": "1d6", "damage_type": "fire", "route": "struck",
     "essence": "fire", "grade": 1},
    {"type": "apply_condition", "target": "sickened", "duration": {"amount": 1, "unit": "round"},
     "route": "ingest", "essence": "decay", "drawback": true},
    {"type": "skill_mod", "target": "stealth", "amount": -2, "bonus_type": "untyped",
     "duration": {"amount": 1, "unit": "hour"}, "route": "carried", "drawback": true}
  ],
  "working": [
    {"type": "working", "trait": "volatile"},
    {"type": "working", "trait": "solid"}
  ],
  "mishap": {"type": "damage", "dice": "1d6", "damage_type": "fire",
             "recipient": "self", "note": "the charge flashes in the crucible"},
  "toxic": null,
  "book": false,
  "price_gp": 0.5, "craft_dc": null, "text": "...", "biomes": ["mountain"], "obtain": "mined"
}
```

*(The trait values above are illustrative. The data pass sets the real ones, §5.10.)*

| Field | Meaning |
|---|---|
| `product` | **Product traits**: what the material puts into a bottle. Each is a complete typed effect document. Each carries a `route` (§5.3), one `essence` (§5.3), a `grade` (default 1), and `drawback: true` where it is a cost to the user. |
| `working` | **Working traits** (§5.5): how it behaves at the bench. They never reach the product. |
| `mishap` | One effect document, **volatile materials only**. What a fail by 5 or more does to the alchemist (§8). |
| `toxic` | One effect document, **`toxic_to_handle` materials only**. What working it unprotected does (§8.4). |
| `color` | The liquid or powder colour the stage draws. It is content, sent by the server, never chrome (UI plan §4). This puts the colour on the document, which the forge left as an open item in `forge_views.py` (forge contracts §15.6). |
| `form`, `material` | As the forge: a form of a shared material. `lead-dust` is a form of `lead`, and `powdered-silver` of `silver` (the 9 existing links, inv §3). |
| `book` | Marks a material whose numbers are printed in the book. Its book effects carry `"book": true` individually and are never scaled. |

`effects` (today's field) is read as `product` by `materials.normalise`, so an old homebrew file
still loads. That is the same trick the forge's normaliser uses for its legacy `effects`.

### 5.3 Routes and essences

**Routes.** The herb vocabulary (`ingest`, `skin`, `eyes`, `wound`, `inhale`, `external`)
gains three alchemy routes:
- `struck`: what a thrown flask does to whoever it hits;
- `area`: what a cloud does to everyone in it;
- `carried`: a drawback that lands on whoever carries the product.

A product family carries only the routes it can deliver (§12.1). A trait it cannot deliver is
shown dimmed, with the reason in words. It is **dropped, never silently kept**: herbalism's rule
(herbalism plan §5.2).

**Essences** are the tags formulae key on (§10). There is one per product trait, in the one
vocabulary as `essence.<name>`, asked by prefix. This is Noita's tag-keyed reactions, and
Witcher 1 and 2's "substances" where any carrier serves (art §3, §4). The vocabulary is
deliberately small, after the Angry GM's advice to keep descriptors few (herbalism plan §3).
It lives in a rule row, `content/rules/alchemy-essences.json`. The 18 essences below are
**(proposed)**:

| Essence | What it carries |
|---|---|
| fire, frost, acid, storm, thunder | the five energies (fire, cold, acid, electricity, sonic) |
| light, shadow | illumination, and darkness, concealment and invisibility |
| vigour | healing, temporary hit points, fast healing |
| purity | removing or suppressing conditions, poison, disease |
| ward | resistance, damage reduction, saves, armour class |
| might | Strength and Constitution, attack and damage |
| grace | Dexterity, land speed |
| mind | Intelligence, Wisdom, Charisma, emotion |
| lightness | flight, climbing, jumping, falling softly |
| sight | senses and divination |
| binding | entangle, glue, hold, compulsion |
| decay | poison, necromancy, sickness |
| change | transmutation of form, size, substance |

The same rule row holds the **derivation table** that reads a spell's essences out of its
descriptors, its effect types and its school (§11.3). It is derived at load and never stored,
exactly as `rules/spells.py` derives `range_value`.

### 5.4 The book fix (do this first)

By hand, from art §1.1 and the primary sources in §22. **No model writes a book number.** Each
book item becomes a **formula** whose core is the book's effect (§10.1); the reagents feed it.

| Item | Today (inv §0.2, questions §11) | The book, which wins | Craft DC |
|---|---|---|---|
| Alchemist's fire | 2d6 fire, no roll, no splash | ranged touch, 10 ft increment, 1d6 fire, 1 fire splash, **1d6 the next round** unless put out (full-round action, DC 15 Reflex, +2 rolling on the ground, water smothers) | 20 |
| Acid flask | as a coating or a sum | ranged touch, 10 ft increment, 1d6 acid, 1 acid splash | 15 |
| Antitoxin | two non-stacking +1s, so +1 | **+5 alchemical** on Fortitude against poison, 1 hour | 25 |
| Tanglefoot bag | two entangles, no glue | ranged touch, 10 ft increment: **entangled** (−2 attack, −4 Dex); DC 15 Reflex or **glued** to the floor (a flier falls instead); break free with DC 17 Strength or 15 slashing to the goo; brittle after **2d4 rounds**; Huge and larger unaffected | 25 |
| Sunrod | a blade coating, 1d4 fire | struck as a standard action: **normal light 30 ft, raised one step a further 30 ft, 6 hours** | 25 |
| Smokestick | drinkable, smoke narrated | lit: a **10-ft cube treated as fog cloud** (20% concealment within 5 ft, 50% beyond), 1 minute | 20 |
| Thunderstone | missing | thrown at a square (20 ft increment, the intersection is AC 5): 10-ft-radius spread, **DC 15 Fortitude or deafened 1 hour** | 25 |
| Tindertwig | missing | lights a torch as a standard action, not a full-round action | 20 |
| Liquid ice, itching powder | coatings (no vessel) | made through a vessel like everything else; the family decides delivery | catalogue |
| Antiplague | refused by its own Filter rule | Filter strips drawbacks (§7), so it no longer needs a harm to strip | 25 |
| Restricted damage (sunmetal, saint's tallow) | hurts the living | `when: {target: {type: undead}}` read by the damage path (§16.7) | |
| Handler effects (quicksilver, lead dust) | product damage | `toxic` working document (§8.4) | |
| Personal-range potions (5) | allowed with no rule | **allowed by the owner's rule** (§11). They are no longer a contradiction. | |
| Potion prices | 6 to 60 gp | 50 gp × spell level × caster level (§11.4) | |
| Weapon table's "Alchemist's fire" | 200 gp siege ammunition | stays excluded from shops (`goods.py:620`). Shops sell the splash flask (§12.4). | |

The Craft DCs are art §1.1's table, cross-checked against Pathfinder Unchained's difficulty list
(art §8). Smokestick, tindertwig and thunderstone come from the core table only (art §8); this
plan uses them and says so.

**Holy water is not Craft (alchemy)** (art §1.1). It stays out of the formula table. Its
"undead and evil outsiders only" shape is still built (§16.7), because sunmetal and saint's
tallow need the same reader.

### 5.5 Working traits

Each is a typed document the bench reads. None reaches the product.
`effectspec.WORKING_TRAITS` (the forge's list, `rules/effectspec.py:76`) gains the alchemy
traits below. All band percentages are **(proposed)**.

| Trait | Effect at the bench | Grounding |
|---|---|---|
| `volatile` | the step carries a mishap (§8); +3 DC for each volatile past the first (today's `VOLATILE_DC_STEP`, kept) | inv §1, the owner's Q3.2 |
| `stabilizer` | cancels one volatile input's surcharge and mishap. This is Stabilize as an ingredient (Q3.1): quenching clay is "the physical half of stabilize" today. | art §5, sulphur "fixing" mercury |
| `catalyst` | **never spent**; widens the step's band by 20%, or does its named job (§5.8) | Q3.1, Q7.3 |
| `apparatus` | never spent; a vessel that is really equipment (crystal retort, adamantine crucible) widens one method's band by 20% | Q7.3 |
| `solvent:<kind>` | `water`, `alcohol`, `vinegar`, `oil`, `acid`. Dissolve needs one, and some solids dissolve only in one kind. | herb `solvent` field, kept |
| `solid`, `liquid` | which methods take it: Calcine and Sublime take solids, Distill takes liquids | art §5 |
| `combustible` | refused at Calcine ("it burns away, it does not calcine") | art §5, calcination |
| `slow_to_dissolve` | the Dissolve band is 30% narrower | Q7.1's own example |
| `light_sensitive` | an intermediate left unsealed loses one grade a day | Q7.1's example |
| `corrosive` | refused in a metal vessel (asks the metal tag, §16.11); burns through a field kit's cloth filter | Q7.1's example |
| `toxic_to_handle` | §8.4 | Q3.4 |
| `wild` | prima materia only (§5.8) | Q7.4 |

**Vessel traits** decide the product family (Q7.3, §12.1): `drinkable` (a vial), `shatters`
(a clay or thin glass flask), `bursts` (a bladder), `struck` (a casing or a stone), `stick` (a
rod or a twig), plus `fireproof`, `warded` and `lead_lined`. They modify a step and never a
product's numbers.

### 5.6 What the traits must add up to

The relevance rules, mirroring herbalism's `test_herb_relevance.py` and the forge's §5.7:
- **At least three discoverable properties per material** (Q7.1), counting product traits,
  working traits, the mishap and the toxic document. **At least one is a drawback.** Vessels,
  solvents, catalysts and apparatus meet the three through working traits.
- **No narrative effects.** Every product trait passes `effectspec.executable` *after* the
  vocabulary lane (§16) has made speed, senses, light, clouds, burning and glue executable.
- **Every material is relevant.** It feeds a method, fills a formula's essence, or is a vessel,
  solvent, stabilizer or catalyst. A test pins it.
- **Small house numbers, by tier.** The forge's `TIER_CEILING` (common ±2, uncommon ±2, rare
  ±3, exotic ±3, legendary ±4, `rules/materials.py:58`) bounds every flat house number. A
  matching dice ceiling bounds house dice **(proposed)**:

  | Tier | Common | Uncommon | Rare | Exotic | Legendary |
  |---|---|---|---|---|---|
  | Largest house die | 1d4 | 1d6 | 2d6 | 3d6 | 4d6 |

  Book effects are exempt, being the book.

### 5.7 Hybrid herbs, and the basilisk-eye collision

**The two-way door (Q2.1).** The alchemy shelf is the alchemist's materials **plus every
ingredient with `hybrid: true`** (63 today). No herb document is copied: the herb *is* the
material, one document on two shelves (the owner's "one material, many shelves"). Two things
happen to a hybrid on the alchemy shelf:
1. Its herb effects are read as product traits, **all routes included**. The 49 `external`
   effects that the herb bench drops as "alchemy only" now have a bench.
2. Each of its effects gains an `essence` in the data pass, which the herb bench ignores.

The contract already promises this (`docs/campaign-format.md:343`). This makes it true.

**The collision (urgent, fixed in lane 1).** `basilisk-eye` is the id of both a herb
(`content/ingredients/herbs-and-parts.json`, hybrid, rare) and an alchemist gland:
- `knowledge.resolve("basilisk-eye")` returns the gland, because materials are asked first
  (`rules/knowledge.py:214-218`).
- `knowledge.py:16-17` claims the two id spaces are disjoint, and that
  `tests/test_alchemist.py` pins it. The test (`:601-617`) compares material files only with
  each other.
- `herb_known["basilisk-eye"]` is one entry shared by both documents (`_store_id`, 390-401).
- Once the hybrid door opens, the herb appears on the alchemy shelf **under the same id as the
  gland**. The collision stops being latent at that moment.

**The fix:**
- **Merge the two into the herb document.** It is the same object, an intact basilisk eye, and
  the herb is already hybrid.
- The gland's alchemy trait moves onto the herb as an `external` product trait: the Fortitude
  DC 15 save or staggered 1d4 rounds, with its narrative half typed or dropped.
- The alchemist row is deleted.
- Old stock with that id already resolves to the herb.
- `knowledge.py`'s comment is corrected.
- The test is widened to **every material id against every ingredient id**. Its docstring
  names the measured collision.

### 5.8 The inert, the keys and the legendary transformers

- **The 40 inert materials** each get three traits in the pass (Q7.4). Most become vessels,
  solvents or stabilizers with working traits. Saltpetre becomes the volatile oxidiser it is,
  and sal ammoniac a sublimate.
- **The 30 spell-potion keys** (bull hairs, owl feathers, cat fur and the rest) get real product
  traits whose essences fit the spells they keyed (Witcher's substances):
  - bull hairs carry `might`;
  - owl feathers carry `mind`;
  - eagle feathers carry `lightness`.

  The keys stop being keys, and every one of them still serves its old potion through its
  essence.
- **Prima materia** carries the `wild` working trait. In a step it **copies one product trait
  of another input**, chosen by the player, at grade 1. It is never a trait of its own. This is
  "becomes anything the chain asks" made into a rule.
- **Philosopher's mercury** carries `catalyst`, never spent. At Transmute it makes the exchange
  **one for one** instead of two for one (§9). Today Catalyze consumes it like anything else
  (inv §3).
- **Orichalcum grains and world-egg shell** become legendary catalysts or apparatus. The pass
  proposes each job, and the owner reviews the table.

### 5.9 Prices against the book

Q4.4: material prices are checked against the book items they feed. The book says raw
materials are **one third** of an alchemical item's price (Craft, art §1.1) and **one half** of
a potion's (Brew Potion, art §1.2).

The data lane computes, for every formula, the **cheapest legal set of bought inputs** and
lists in the review table every formula whose inputs cost more than that fraction of its book
price. Today's worst case is haste: 1,750 gp of azoth and crystal retort against a 750 gp
potion (inv §0.4). Most of that disappears once the crystal retort becomes `apparatus` and
is never spent. The owner reviews the rest.

### 5.10 How the pass is done

The forge's pipeline (blacksmithing plan §5.8):
1. Export the 139 materials, the 63 hybrid herbs and the 44 spell potions to a tagging file
   (`tools/alchemy_export.py`).
2. **Fill the book entries by hand** from §5.4.
3. Draft house traits, essences, working traits, mishaps and toxic documents **with model help
   inside the validator's fences**: types, routes, essences, tier ceilings, at least one
   drawback, at least three properties. Nothing invalid can land.
4. Validate mechanically. Then **the owner reviews the house numbers, the essences and the
   mishaps as a table** in `docs/alchemy-review.md`, as the forge's house modifiers were
   reviewed.
5. Rewrite each material's `text` to say what it does in the app (the owner's herb rule: the
   description follows the mechanics).

---

## 6. Trait inheritance: Atelier's model

Q7.2, made concrete. Sources: art §3 (Ryza, Sophie) and §6.3.

### 6.1 The pool

At every step, the inputs' product traits form a **pool**:
- **Each distinct material contributes its traits once**, whatever the count. Count is batch
  size (§15.2), not strength. Two units of brimstone are two flasks, not a stronger one.
  Concentration (§7.2) is the way to make one stronger.
- An **intermediate's traits enter the pool as they are**, grades and all. That is how a
  well-made salt carries its traits into the flask (Ryza: "Any traits you dump in at any level
  will be available at the end").
- **Prima materia** adds a copy of one trait the player picks from another input (§5.8).

### 6.2 Same-named traits add

Two traits have the same name when they have the same `type`, `target`, `damage_type` or
condition, and `route`. Two fire-damage traits are the same; a fire-damage trait and a
fire-resistance trait are not. Same-named traits **merge**, and **their grades add**
(Ryza: "Critical Lv 2 and a Critical Lv 5 will yield a Critical Lv 7").
- **The grade cap is the Alchemist level (proposed).** At Alchemist 1 nothing merges past
  grade 1. At Alchemist 6 a trait can reach grade 6. Ryza caps by alchemy level; tying the cap
  to the level means the endless levels still deepen it, one step a level.
- **What a grade means** lives in a rule row, `content/rules/alchemy-grades.json`, one line per
  effect shape **(proposed)**:

  | Shape | Grade *g* gives |
  |---|---|
  | dice | *g* × the dice count (1d6 at grade 3 is 3d6) |
  | flat amount (a bonus, a resistance, hit points) | *g* × the amount |
  | a save DC | +2 per grade above 1 |
  | a condition's duration | × *g* |
  | a duration of a bonus | the longest of the merged traits |

- **Drawbacks merge the same way.** Two sickening drawbacks are one sickening drawback at
  grade 2.
- Sophie's pairwise combining into named higher traits is **not** taken. Ryza dropped it for
  level addition only (art §7), and one merge rule is enough to learn.

### 6.3 Slots: the player picks

Each product family has **slots** (§12.1): a potion 3, an oil 2, a splash flask 2, a cloud 2, a
tool 1 **(proposed, following Atelier's three and the Physick flask's two, art §3, §4)**.
- **A finished good carries at most its slots in benefits.** The player picks which, from the
  pool's traits that the family can deliver. The rest are shown, dimmed, with the reason ("a
  potion has three slots; this would be a fourth").
- **A formula's core takes one slot** (§10.1). An alchemist's fire therefore carries its book
  core plus one inherited trait, and a spell potion its spell plus two.
- **Drawbacks take no slot and are never optional.** If you carry a benefit from a material,
  that material's drawbacks come with it, as they do in Morrowind and Oblivion (art §3).
  **Filter** is the method that strips them (§7). Its precedent is Skyrim's Purity perk:
  "All negative effects are removed from created potions."
- **Intermediates** (solution, calx, spirit, filtrate, admixture, sublimate) carry **every**
  trait in the pool, up to 6 **(proposed)**. When the pool is larger, the player picks the 6.
  Traits pass through intermediates whether or not the final family can use them (Ryza's
  "even while inactive").
- **Finished goods are dead ends** (Ryza). A potion, oil, flask, cloud or tool is never an
  input, and the bench refuses it with that reason.

### 6.4 What quality does to traits

Quality multiplies (herbal-quality.json, the shared ladder):
- benefits by `potency`;
- durations by `duration`;
- drawbacks by `drawback` (Crude ×1.25 … Flawless ×0.25, "softer drawbacks").

Perks multiply on top. A **book core** follows the same columns, except that a spell potion's
quality becomes **caster level** instead (§11.3). Rounding follows `consumables.scale`: the flat
part of the dice, with positive bonuses rounded up.

### 6.5 Worked example

*(The trait values are illustrative; the data pass sets the real ones.)*

The player is at Alchemist 2, playing for a house splash flask:
1. **Dissolve** brimstone (fire 1d6 struck, grade 1; drawback: −2 Stealth carried) in naphtha
   (fire 1d6 struck, grade 1; drawback: sickened 1 round ingest), with strong spirits as the
   solvent. The **solution** pools fire at grade 2 (1 + 1, inside the cap of 2), and carries
   both drawbacks.
2. **Filter** the solution. The filtrate keeps fire grade 2 and **sheds both drawbacks**; the
   precipitate, a salt, lands on the shelf too.
3. **Bottle** the filtrate in a clay flask (`shatters`, so the splash flask family, 2 slots).
   The mix matches no formula, so this is a **house compound** with two free slots. The player
   picks fire grade 2, which is **2d6 fire on a direct hit**.

Had the player bottled the same filtrate as **alchemist's fire** (a known formula, §10), the
book core would take one slot and the fire trait would satisfy its essence. The free slot could
then carry one more trait. The book's 1d6, next-round 1d6 and splash stay the book's.

The house route reaches 2d6 because it spent a Filter step, a second fire reagent and level 2.
It does not burn next round and it has no book splash: splash is a property of the book
formula's core (§16.2). **Whether house splash flasks should splash at all is open point 3.**

---

## 7. Methods

Each method is one bench session: drop, see the time and the stakes, roll the d20, play the
minigame, and the result lands on the shelf. Per-method numbers live in
`content/world-classes/alchemist.json` → `bench.methods`, the forge's shape
(`blacksmith.json:146`). Times and potency figures are **(proposed)**.

| Method | Level | In | Out | Where | World time per unit | Notes |
|---|---|---|---|---|---|---|
| **Dissolve** | 1 | a solid and a solvent | a **solution** (liquid). Undissolved solid falls out as a **precipitate** (the solid end, Q3.1). | kit | 10 min | Needs a `solvent:` of the kind the solid takes. The old prose rule "needs a solvent" is now checked (inv §1). |
| **Calcine** | 1 | a solid | a **calx** (a salt) | kit | 1 h | Refused for `combustible` materials. Drives off nothing of value: traits carry. |
| **Bottle** | 1 | a liquid or powder, and a **vessel** | the finished product; the **vessel decides the family** | kit | 10 min, plus any setting time (§12.3) | Matches a formula or makes a house compound (§10). Picks the slots (§6.3). Replaces Seal; it must still come last. |
| **Assay** | 1 | a pinch | knowledge | kit | 10 min | §13.2. No quality and no minigame, like tasting and the forge's assay. |
| **Distill** | 2 | a liquid | a **spirit** (sellable). Two make one at ×1.5 (concentration). | **lab** | 2 h | Alchemy's iconic operation, free again now that herbalism retired it. |
| **Filter** | 2 | a solution or admixture | a **filtrate** with every drawback stripped, plus a **precipitate** (the solid end) | kit | 20 min | Its real job is the purity rule (§6.3). Potency ×0.9, the cost of safety (herbalism's Neutralize ratio). It is never refused for "nothing to strip": the precipitate is still a product. |
| **React** | 2 | two or more inputs, one of them a liquid medium | an **admixture**: the pools merge and same-named traits add | kit | 30 min | The volatile heart of the craft. It has the reaction gauge (UI §9). |
| **Sublime** | 3 | a solid | a **sublimate** (a salt). Two make one at ×1.5 (concentration). | **lab** | 4 h | The crust that re-forms above (art §5). |
| **Transmute** | 3 | two of a material (or one with a catalyst) | one of the same kind, one band rarer | **lab** | 1 day, through **In progress** | §9. |

### 7.1 The check and the DC

**The check:** d20 + Alchemist level + half character level + Intelligence (today's
`check_terms`, kept). Add **+2 circumstance at a laboratory**. That is the book's alchemist's
lab: "provides a +2 circumstance bonus on Craft (alchemy) checks" (UE p.77, CRB p.158).

**No natural 1 or 20** on a bench check. The CRB's naturals cover attacks and saves, not
skills, and both revamped benches already apply this (`crafting.check_odds:1913`). The old
alchemy tab's naturals (`craft_views.py:624`) retire with the tab.

**The DC of a step:**
- **Intermediate steps:** the hardest input's DC (stated `craft_dc`, else 5 + 5 × rarity
  rank), as herbalism and the forge do.
- **Bottle with a formula:** the formula's DC.
  - A classic uses the book Craft DC (§5.4).
  - A spell potion uses **5 + caster level**: "The DC to create a magic item is 5 + the caster
    level for the item" (CRB magic item creation, art §1.2). The +5 per missing prerequisite
    does not apply, because the formula stands in for the spell (Q1.3).
- **Bottle without a formula:** the hardest input's DC.
- **Plus:**
  - concentration, 2*n* at concentration step *n* (herbalism's curve, `herbal-methods.json:106`);
  - +3 for each volatile input past the first;
  - −1 per Containment pick on a volatile step;
  - a stabilizer cancels one volatile's surcharge.
- **No per-stage creep.** Each step is its own roll now, so the old "+2 per stage past the
  first" means nothing and goes (forge plan §7).

**Failure:** the PF1e Craft rule. Fail by 4 or less and you lose the time but keep the
materials. Fail by 5 or more and **half the materials are ruined**, rounded down with at least
1 when there were 2 or more (`blacksmith.failure_losses`, kept) **(proposed: the forge's
rounding rather than herbalism's)**. **On a volatile step, the mishap applies as well** (§8).

### 7.2 Concentration

As herbalism §5.3 (Q3.3):
- **Distill** concentrates liquids and **Sublime** concentrates solids.
- Two units make one at ×1.5 potency and ×1.5 duration, uncapped.
- Each concentration moves the result one rarity band rarer, and step *n* adds 2*n* to the DC.

Concentration multiplies **magnitude**; it never adds grades. Grades come only from distinct
materials merging (§6.2). Minecraft's 1.9 ban on stacking extend with strengthen (art §4) is the
caution, and the DC curve is the brake herbalism already uses.

### 7.3 Order rules

- **Bottle comes last.** A bottled product is a dead end (§6.3).
- **Distill takes liquids, and Calcine and Sublime take solids** (the `solid` and `liquid`
  working traits).
- **React needs a liquid medium:** a solution, a spirit, a solvent, or a herbal intermediate
  that pours (today's rule, kept).
- **A volatile input** can enter any step, and that step carries its mishap.

---

## 8. Volatility made real

Q3.2 and Q9.4. Volatility is "the one rule herbalism has no counterpart for" (questions Q3.2).
Today it is a DC surcharge plus a sentence that nothing applies (inv §0.8).

### 8.1 Stated before the roll

The check response carries a **mishap line** built from the volatile inputs' `mishap`
documents, with stabilizers and Containment already applied:

> If this fails by 5 or more: 1d6 fire to you (brimstone). Half the materials are ruined.

It is rendered by `effectspec.render`, and the page shows it in `--alarm` words above the Roll
button (UI §6.5). The player chooses the risk knowing it. That is what keeps the one
chance-based loss in the craft fair (art §6.5).

### 8.2 Applied on a fail by 5 or more

- Every volatile input that is not stabilized applies its `mishap` **to the alchemist**, as
  intents through the engine's validation, stamped `origin: rule:mishap:<material>`.
- Damage goes through `_apply_damage`, and conditions land as `ActiveEffect`s. Resistance,
  damage reduction and temporary hit points all apply, with no line of their own.
- A mishap whose effect is an area (a `recipient: area` document) catches whoever stands next
  to the bench, through `areas.burst_cells`. **(proposed:** only the fire, acid and thunder
  mishaps of rare and above have an area.)
- **A minigame miss never triggers a mishap.** It lowers quality only (Q3.2). On the stage, the
  reaction gauge's overshoot is a small flare, but it is a quality signal.
- The tell names what happened ("The crucible flashes; brimstone fire catches Kesst's sleeve
  for 4."). The narrator gets the tell and nothing else (law 3).

### 8.3 Containment and stabilizers

- **Containment** (perk, per pick): −1 DC on volatile steps, and each mishap's dice one step
  smaller, never below 1 point (§4.2).
- **A stabilizer** in the step (quenching clay, fuller's earth, or whatever the pass
  assigns) cancels **one** volatile input's surcharge and mishap. This is Stabilize as an
  ingredient (Q3.1), as the forge made Flux an ingredient of Smelt. The preview names which
  volatile it cancelled.
- The old **two-volatiles refusal** and `needs_stabilizer` refusal **go**. A second volatile is
  now a priced risk (+3 DC and a second mishap), not a wall. Phlogiston keeps its warning, and
  the choice is the player's.

### 8.4 Toxic to handle

Q3.4. The quicksilver and lead dust tax moves from the product to the bench:
- A material with `toxic_to_handle` applies its `toxic` document **to the alchemist at the
  start of every step that uses it**: a Fortitude save or a point of Constitution damage, as
  the pass sets it.
- **Unless the alchemist is protected.** Protection is either of:
  - **mask and gloves**, a new goods row (proposed 5 gp), carried;
  - **a laboratory's fume hood**, which every laboratory has **(proposed)**.
- The bench says which before the roll ("Quicksilver: Fort DC 13 or 1 Con damage, unless you
  wear a mask and gloves").
- **It reaches the product only if the trait is meant to be a poison.** It then needs its own
  `product` trait with a `struck` or `area` route.

---

## 9. Transmute

Q2.4. Level 3, at a laboratory. WoW's transmutes are the model, costed in materials and game
time and never in real-time cooldowns (art §3, §6.7).

- **Input:** two units of material A. With a `catalyst` that names Transmute (philosopher's
  mercury, never spent), one unit.
- **Output:** one unit of material B, where:
  - B has **the same kind** as A;
  - B is **exactly one rarity band rarer**;
  - B **shares at least one essence** with A.

  The candidates are derived from the shelf at load, so a world's own reagents get transmutes
  for free (world-agnostic). **The player picks B from the candidates.** It is a choice, never
  a roll for which.
- **Shared metals.** Alchemy forms of forge metals transmute by the same rule: lead dust can
  become powdered silver if the data gives them a shared essence and adjacent bands. The output
  is a **form** of the forge metal (`material_of`), "one material, many shelves". It does not
  become a bar; the forge has no step that takes powder.
- **DC:** 10 + 5 × the output's band rank: uncommon 15, rare 20, exotic 25, legendary 30
  **(proposed)**.
- **Time:** one day, in the **In progress** section (§16.11) **(proposed)**. The Great Work sits
  on the bench while you adventure, and it is collected when it is done.
- **The minigame** is the colour stages in order: nigredo, albedo, citrinitas, rubedo (art §5,
  UI §9).
- **The economy check.** The data lane lists every transmute pair where the output's price is
  more than three times the inputs' **(proposed ratio)**. The owner reviews them, because a
  money machine is a balance call, not a rule.

---

## 10. Formulae

### 10.1 The formula row

A formula is a fixed, learnable row (Q5.2): "never secret per world" (art §4). It lives in
`content/rules/alchemy-formulae.json` (authored) plus the derived spell rows (§11).

```json
{
  "id": "alchemists-fire", "name": "Alchemist's fire", "kind": "classic", "book": true,
  "family": "splash",
  "requires": {"essences": {"fire": 1}},
  "core": [
    {"type": "damage", "dice": "1d6", "damage_type": "fire", "route": "struck", "book": true},
    {"type": "burning", "dice": "1d6", "rounds": 1, "save": {"type": "ref", "dc": 15},
     "smother_bonus": 2, "route": "struck", "book": true}
  ],
  "splash": {"amount": 1, "damage_type": "fire"},
  "range_increment_ft": 10,
  "craft_dc": 20, "price_gp": 20, "minutes": 10,
  "level": 1, "tier": "common",
  "source": "CRB p.160; AoN item page"
}
```

| Kind | Rows | Core | Notes |
|---|---|---|---|
| `classic` | the CRB eight (acid, alchemist's fire, antitoxin, smokestick, sunrod, tanglefoot bag, thunderstone, tindertwig) and the catalogue's own (antiplague, liquid ice, itching powder, flash powder, smelling salts, alchemical grease, alkali flask, vermin repellent, bladeguard, holy weapon balm) | the book's effect, `book: true` | 18 rows (`docs/alchemy.md`'s recipe table). The non-CRB ten get house cores, inside the tier ceilings, and the owner reviews them. |
| `spell` | one per spell (§11) | the spell's own effect documents at the potion's caster level | the 44 shipped potions are **authored** rows and win over the derived ones |
| *(no formula)* | | none | a **house compound**: inherited traits only, priced on the tier ladder (§12.4) |

`requires` names **essences with minimum grades** and, where needed, a family. It never names
materials (Q4.2). The 44 spell potions' exact material sets become essence requirements that
their old materials still satisfy (§5.8), so every old recipe still makes its potion.

### 10.2 Matching at Bottle

When the player bottles:
1. The **vessel** fixes the family.
2. If the player chose a **known formula**, the bench checks the mix against its `requires`
   and says in words what is missing ("needs lightness at grade 2; you have grade 1").
3. If the player chose **Experiment** (no formula), the bench looks for formulae whose
   **signature** matches the mix exactly. A signature is the family plus the set of essences
   present in the mix. **Experiment discovery**:
   - if exactly **one** formula within reach has that signature, and the roll succeeds, the
     product **is** that formula and the formula is written into the alchemist's formulary
     ("found by experiment, day 14"; +3 mastery). This is Guild Wars 2's "this looks like
     something", and Outward's and Tears of the Kingdom's "making it right writes it down"
     (art §4, §6.4).
   - if **several** match, the product is a house compound, and the bench says how many it
     could have been ("This fits 3 formulae. A writing would tell you which.");
   - if **none** match, it is a house compound.

   **Authored formulae win their signature.** A mix that matches an authored row exactly is
   that row, whatever derived rows share it.

### 10.3 The possible-formulae count (Q5.3)

While the player builds a mix, at any step, the bench shows:

> This could still become 4 formulae. You know 1 of them: Antitoxin.

- **Definition.** Formula F *could still become* from mix M when all of these hold:
  - F's family accepts M's vessel, or no vessel is chosen yet;
  - every essence present in M is in F's `requires` (more can be added, nothing can be taken
    away);
  - F is **within reach**: its level is no higher than the alchemist's, its spell level is no
    higher than the Q4.3 cap, and its tier is under the rarity ceiling.
- **Unknown formulae are counted, never named.** Known formulae are named, since the player
  already knows them.
- **Essences the player has not yet discovered still count.** The count is a hint about what
  the reagents really are, which is GW2's design (herbalism prior art §4). It never names an
  unknown trait.
- **No hints beyond the count** (Q5.3 refused naming the nearest formula).

**Measured on a draft essence mapping** (a scratch script over the corpus, not committed; the
mapping itself is the data lane's to finish and the owner's to review):

| | Count |
|---|---|
| Corpus spells whose effects are fully executable once speed and sense execute (§11.2) | 791 (781 today) |
| … within reach at Alchemist 1 to 3 (1st level and below) | 143 |
| … at Alchemist 6 (3rd level and below) | 476 |
| A mix holding only `change`, at Alchemist 1 | 44 formulae |
| … only `mind` | 41 |
| … only `binding` | 32 |
| The biggest bucket: family potion, essences {binding, mind} | 120 formulae share it (hold, charm, compulsion) |
| Corpus formulae with a **unique** signature (essence set only) | 19 of 791 |
| … if the spell level is added to the signature | 157 of 791 |

**What that measurement decides.** A small essence vocabulary cannot give 791 spells unique
signatures, and a large one would stop being learnable. So:
- **experiment finds a corpus spell formula only when its signature is unique within reach**;
- **the rest come from writings** (§10.4).

The count still tells the player how close they are. The **classics and the 44 authored
potions are pinned unique** by test, so experiment always finds them. This is what Q5.2's
"both ways" means at this scale. **Open point 4** asks whether that split is what the owner
wants.

### 10.4 Writings: the other way in

The book's own way: the APG alchemist "can also add formulae to his book just like a wizard
adds spells to his spellbook, using the same costs, pages, and time requirements" and "may
study a wizard's spellbook" (§22). The wizard's rules are in the CRB (§22).

| Route | Check | Cost | Time | Notes |
|---|---|---|---|---|
| **A scroll** of the spell | Alchemist check, DC 15 + spell level | the CRB spellbook writing cost (5, 10, 40, 90, 160, 250, 360, 490, 640, 810 gp by level) | 1 h study, plus 1 h per spell level to write | On success the scroll is used up: "a spell successfully copied from a magic scroll disappears from the parchment". A failure leaves the scroll, and the alchemist cannot try that spell again for a week (CRB). |
| **A spellbook** (borrowed or looted) | the same | the same | the same | The book is untouched. |
| **A caster who knows it** (a companion, or a teacher NPC) | none | the teacher's fee; nothing for a companion | 1 h per spell level | A teacher is gated by attitude, as confiding is (`rules/confiding.py`). A companion obeys in character (the 2026-10-01 ruling). |
| **A formulary** (a goods item) | none | its price | hours to read | Herbal manuals' shape: each lists formula ids and pays +5 mastery once. Sold at alchemists' stalls and found as loot. |
| **A potion in hand** | Alchemist check, DC 15 + spell level | **the potion is spent** | 1 h | House rule **(proposed)**, mirroring the enchanter's disenchant (enchanting answers, Round 2). |
| **An alchemist teacher** | none | fee | 1 h | Any formula, including classics. Needs the new `alchemist` occupation (§14). |

### 10.5 The formulary

The alchemist's known formulae are stored per character. One knowledge store is the forge's
rule (`Actor.herb_known`, keyed by id, forge contracts §6). Formula ids are prefixed `formula:`
so they never meet a material id. That is the lesson of §5.7.

The **Formulary** (UI §6.7) lists known formulae with how each was learned. It is the
herbarium's counterpart for recipes. A converted alchemist's formulary is filled from their
save (§18).

---

## 11. The spell-potion rule

The owner's Q4.3, Q1.3 and Q6.4, made executable.

### 11.1 The rule

- **Any spell may be a potion.** That includes personal range: it then works on whoever drinks
  it. The owner accepted that explicitly, and overruled the book's 3rd-level cap and its
  personal-range ban (CRB: "Spells with a range of personal cannot be made into potions").
- **The highest spell level an alchemist can brew = max(1, floor(Alchemist level / 2)).**

  | Alchemist | 1 to 3 | 4 to 5 | 6 to 7 | 8 to 9 | 10 to 11 | 12 to 13 | 14 to 15 | 16 to 17 | 18+ |
  |---|---|---|---|---|---|---|---|---|---|
  | Highest spell level | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |

  0-level spells are within reach from level 1, and are priced at half a level (§11.4).
- **The formula and its reagents stand in for the spell** (Q1.3). No caster level and no
  prepared spell are needed. The gates are the formula, the level, and the reagents' rarity.
- **The spell's level** is the lowest level it has on any list (`Spell.min_level`)
  **(proposed)**. The book uses the creator's own class list; this app's creator has none, so
  it takes the most favourable.

### 11.2 Which spells can be bottled today

A potion must carry complete typed documents (no narrative effects, the cross-craft rule). So a
spell formula is offered **only when every effect the spell carries is executable**. Measured
on 488b293 (scratch script):

| | Spells |
|---|---|
| In the corpus | 3,040 |
| With fully executable effects | **781** |
| … once `speed` and `sense` execute (§16.3) | **791** |
| … of those, with no harmful effect on the target | 66, then 76 |

- **The rest open by themselves as the spell corpus is reviewed.** Every spell whose
  narrative lines become typed becomes a formula, with no alchemy change. This is a ratchet,
  not a list to maintain.
- **The 44 shipped potions are authored rows.** They win over the derived ones, and keep their
  ids and `holds_spell` (§18). Their 20 narrative lines and 7 speed or sense lines must become
  typed (§16.9). Until a potion is fully typed, old stock stays usable, but no new one is
  brewed.
- **Harmful spells.** By the book the drinker is the target, so a potion of *hold person* holds
  its drinker. The owner's "any spell" keeps them available. The bench says plainly who the
  target is ("The drinker is the target: this would hold you"). **Open point 5** asks whether
  harmful spells should go into splash flasks instead.

### 11.3 Caster level, quality, and the drinker

- **Caster level = the minimum caster level for the spell's level, plus one for each quality
  tier above Sound** (Q6.4). The book sets the floor: "never lower than the minimum level needed
  to cast the needed spell" (CRB magic item creation).
  - The minimum caster level is read from the **class documents** (`rules/casting.py`): the
    lowest character level at which any class on the spell's lists casts that spell level,
    converted to caster level. That gives CL 1, 3, 5 for 1st to 3rd level on the wizard, cleric
    and druid lists, which is what the book's potion table prints (CRB potions: 50, 300, 750
    gp).
  - Where a list has no class document, use 2 × spell level − 1, and CL 1 for a 0-level spell
    **(proposed)**.
- **Crude** potions are at the minimum caster level, since the book allows nothing lower.
  Their price and shelf life follow the quality ladder.
- **The drinker is both target and caster.** The book: "The drinker of a potion is both the
  effective target and the caster of the effect (though the potion indicates the caster level,
  the drinker still controls the effect)." Area spells are centred on the drinker
  **(proposed)**.
- **Oils.** A spell whose target is an object or a weapon (magic weapon, keen edge, align
  weapon) is an **oil**. That is read from the spell's `targets` line, as the 4 shipped oils
  already are. The book: "oils are applied externally rather than imbibed".
- **Resolution** goes through the spell's own structured half:
  - `spells.effects_at(spell, cl)` fills the dice;
  - `spells.roll_duration` fixes how long;
  - the drink door delivers it as intents, stamped `origin: item:<id>` and `source: spell:<id>`.

  A potion and a cast of the same spell therefore resolve through the same documents. An
  authored potion (one of the 44) uses its own documents instead.
- **Using one** is a standard action that provokes (CRB potions).
- **Identifying one** is an Alchemist check, DC 15 + spell level, holding it for a round. That
  is the book's Perception DC, and the APG alchemist's "identify potions as if using detect
  magic" (§22). It reveals what the potion is; it does not teach the formula. The
  potion-in-hand route (§10.4) does that.

### 11.4 Price and time

- **Price** = 50 gp × spell level × caster level, with a 0-level spell counting as ½ (CRB
  potions).
  - **Quality reaches the price only through caster level.** Q4.4 says quality multiplies both
    kinds of price; for a spell potion the book already multiplies by caster level, which
    quality raised, and multiplying again would count quality twice. **Open point 6** confirms
    this reading.
  - Crude takes the quality ladder's ×0.5.
- **Brewing time** follows the Brew Potion feat: "2 hours if its base price is 250 gp or less,
  otherwise … 1 day for each 1,000 gp in its base price" (CRB feats). The CRB's other line, "1
  day" in Creating Potions, contradicts it (art §1.2). The feat is used, because it is the
  later rule and the one the alchemist class follows.
  - The Bottle step itself is the 10-minute minigame.
  - The potion then **sets** in the **In progress** section until the brewing time has passed.
    It cannot be drunk or sold before it is collected. That is herbalism's steeping jar rule,
    generalised.

### 11.5 The enchanter

The contract is unchanged (Q10.2):
- `holds_spell` and `caster_level` sit on every spell potion's stock row (`crafting.Stock`
  114-115);
- `magicitem._potion_for` (401-409) consumes one as the prerequisite spell;
- `tests/test_magicitem.py:207` and `:254` stay green.

Under the owner's rule many more spells now have potions, so the enchanter's stand-in reaches
further. That is intended (Q1.3: "stated once for both").

---

## 12. Products and vessels

### 12.1 The families

The vessel decides the family (Q7.3). The family decides delivery, action, slots and which
routes it carries. Actions follow the book. Slots, keeping times and actions without a book
line are **(proposed)**.

| Family | Vessels (working trait) | Used by | Action | Slots | Routes it carries | Keeps |
|---|---|---|---|---|---|---|
| **Potion** | glass vial, lead-glass vial, warded phial (`drinkable`) | drinking | standard, provokes (CRB) | 3 | ingest | indefinitely (the book's potions do not spoil) |
| **Oil** | the same vials | coating a weapon, or applying to skin | standard, provokes (CRB) | 2 | skin, weapon | indefinitely |
| **Splash flask** | clay flask, salamander-glass flask (`shatters`); waxed bladder (`bursts`, no splash) | throwing: a ranged touch attack (§16.2) | standard | 2 | struck (and carried drawbacks) | 1 year |
| **Cloud** | stoneware pot, brass casing (`struck`) | throwing at a square, or lighting where you stand | standard | 2 | area, inhale | 1 year |
| **Tool** | rod, stick, twig vessels (`stick`) | its book function: strike a sunrod, light a tindertwig or smokestick | standard (the book's tindertwig: standard instead of full-round) | 1 | its function | indefinitely |
| **Salt / spirit** (intermediates) | none | selling, or as an input | | carries up to 6 (§6.3) | all | salts indefinitely; spirits 1 year; solutions and admixtures 3 days |

- **Smokestick and sunrod are tools, thunderstone is a cloud, and tanglefoot is a splash flask
  that bursts.** Each takes the family whose delivery the book describes.
- **Hybrid herbs' external effects** reach the world through these families. Shadowvine's
  concealment, for example, becomes a cloud.

### 12.2 The product record

Bottle writes a stock row. It stores **ids and grades, never computed numbers** (the forge's
read-live rule, forge contracts §4):

```json
{
  "id": "fine-alchemists-fire", "name": "Fine Alchemist's Fire",
  "kind": "crafted", "craft": "alchemist", "count": 3,
  "family": "splash", "vessel": "clay-flask",
  "formula": "alchemists-fire", "spell": null, "caster_level": null, "holds_spell": null,
  "quality": "fine", "quality_index": 2,
  "traits": [{"from": "naphtha", "key": "damage.fire.struck", "grade": 1}],
  "drawbacks": [],
  "alchemist": {"level": 2, "perks": {"potency": 0, "duration": 0}},
  "ready_minute": 0, "bought": false, "schema": 4
}
```

`alchemy_items.build(record)` (new, the counterpart of `forge_items.build`) computes the specs
on read:
- the core, scaled by quality (or by caster level for a spell);
- the picked traits at their grades;
- the drawbacks;
- the splash, range increment, action and `how`.

`Stock.specs` is filled from it **at load, and stamped with the build version**. CLAUDE.md's
lesson about derived caches applies: compare the version, not a timestamp. So a corrected
material document fixes every old bottle on the next load.

### 12.3 Time, and the In progress section

Most steps finish in minutes of world time. **Three things wait in In progress** (§16.11):
1. a spell potion setting for its Brew Potion time (§11.4);
2. a Transmute (§9);
3. any step whose world time is longer than 8 hours **(proposed threshold)**, such as a large
   Sublime batch.

Each sits with a game-time countdown until it is collected, and is unusable until then.

### 12.4 Prices

Q4.4, through `rules/pricing.py`:
- **Book classics** have their book price (§5.4).
- **Spell potions** are 50 × spell level × caster level (§11.4).
- **House compounds and intermediates** use the tier ladder (`pricing.TIER_BASE`) × the potency
  factor. Both kinds of price are multiplied by the quality price column
  (`herbal-quality.json` `price`), except that a spell potion's quality goes through caster
  level only (§11.4).
- **The shop buys at half** (`SHOP_BUYS_AT`, unchanged).

### 12.5 Shop items are the same documents (Q8.3)

- `goods.GEAR` rows for alchemist's fire, antitoxin and sunrod, plus new rows for acid,
  tanglefoot bag, smokestick, tindertwig and thunderstone at book prices, **resolve to the
  formula's product at Sound quality**.
  - Buying one writes the same stock row a crafted one has, with `bought: true` and no traits.
  - One item, whether bought or made.
- The stall line `alchemist` (`content/rules/stall-lines.json:49-53`) stocks them.
- `gear.json`'s tindertwig row (now `not_yet`: "no fire or light to make") is replaced by the
  tool, once the light model exists (§16.4).
- **Potions on sale** in markets are spell potions at Sound quality and the book price, drawn
  from the formula table within the settlement's size band. That band is the existing market
  rule; no new one.

---

## 13. Discovering reagents

### 13.1 Knowledge

`rules/knowledge.py` already serves the herb and forge shelves. It gains alchemy:
- `MATERIAL_LISTS` counts `product`, `working`, `mishap` and `toxic`. That alone ends
  "0 property keys for all 139" (inv §0.5).
- One store: `Actor.herb_known`, keyed by material id (forge contracts §6). The collision fix
  (§5.7) makes that safe.
- **The narrator never learns an unknown property** (law 3, herbalism §8.1). Making a product
  reveals every trait the product actually carries, Skyrim's rule.

### 13.2 Assay (Q5.1)

- **Cost:** a pinch (a tenth of a unit, tracked as tenths, as the forge's slivers are), and
  10 minutes.
- **The check:** the player's Alchemist check against the study DC (10 + 5 per band), −1 for
  each known material of the same kind, at most −4. That is `knowledge.assay_dc`, reused as is.
  Comparison against known references is what makes the forge's assay easier, and it holds for
  reagents too.
- **The result:** one positive and one negative property, preferring unknowns.
- **Dangerous for real:**
  - assaying a **volatile** reagent and failing by 5 or more applies its `mishap`;
  - assaying a **toxic_to_handle** reagent unprotected applies its `toxic` document, whatever
    the roll.

  These go through `knowledge.apply_danger`, the forge's door for reactive metals.
- **Working a material** (any successful step) reveals its working traits, as at the forge.
- **Tasting a hybrid herb** at the herb bench still works, and teaches the herb's traits on both
  shelves, because it is one document.

### 13.3 People, books and the codex

- **Teachers:** the new `alchemist` occupation (§14), plus the herbalism `teaches` route.
- **Libraries:** the herbalism route, reused.
- **Manuals:** a goods table of alchemy manuals, `content/rules/alchemy-manuals.json`, beside
  `herbal-manuals.json`. They teach reagent properties, and the formularies of §10.4 teach
  formulae.
- **The Codex** is the reagent ledger, the herbarium's and the smith's ledger's counterpart,
  with "3 of 7 known" counts. It is on hover at the bench and a Journal section (UI §6.8).

### 13.4 Starting knowledge (Q5.4)

- the common reagents of the homeland's trade, by biome, as herbalism's homeland rule (how =
  "homeland");
- the four classics as formulae: alchemist's fire, acid flask, antitoxin, tanglefoot bag.

---

## 14. Where you work

Q6.3. The forge's kit-and-smithy rule (blacksmithing plan §10), mirrored.

**The field kit** (crucible, spirit lamp, a rack of vials, a funnel and cloth):
- methods: Dissolve, Calcine, Filter, React, Bottle and Assay;
- materials: common and uncommon;
- anywhere you stand.

It is a goods item, `alchemist's field kit` **(proposed 25 gp, 5 lb**, the price and weight of
the UE alchemy crafting kit). That kit itself only supplies extract components and gives no
bonus to Craft (§22), so the app's kit is a house item at the book kit's price.

**A laboratory** adds:
- methods: Distill, Sublime and Transmute;
- materials: rare and above;
- **+2 circumstance** on every check (the book's alchemist's lab);
- **protection** from `toxic_to_handle` (a fume hood).

There are two kinds:
- **A town laboratory:** a place whose keeper's occupation carries the new `alchemy` tag. That
  occupation does not exist today. `content/people/occupations.json` has none, and "apothecary"
  is a match word of `healer`, which stays herbalism's. You pay by the hour: `market.lab_rent`,
  **proposed 2 sp an hour** (the forge's 1 sp, doubled for the glassware). The keeper may teach
  (§10.4).
- **Your own laboratory:** founded through the places system's `found` door. The owner holds
  `holds.place.<slug>`, as for any founded place, and the place is tagged `laboratory`.
  **(proposed:** founding one needs the book's alchemist's lab, 200 gp, 40 lb, installed there.)

**Every city gets a laboratory, and towns and villages get one only when their own words imply
it** **(proposed)**. That is the forge's ruling for smithies (forge contracts §13.3), applied
the same way, and it is **open point 7**.

Which you are at is read from the scene's place (`places.laboratory_here`, the shape of
`places.smithy_here:2042`), never from the player's words.

---

## 15. The bench, rules side

### 15.1 The flow

As herbalism §9 and the forge §11:
- the d20 decides success;
- the minigame climbs the tier under the ceiling;
- always played;
- the server receives a score in 0..1 and answers with the tier;
- **the page never computes a number**: not the DC, not the grade sum, not the possible-formulae
  count, not the mix colour.

### 15.2 Bulk

**Every method batches** **(proposed)**. One roll and one game cover the stack, one tier for
all of it, and world time grows with the batch. That is herbalism's and the forge's rule; the
forge's no-bulk exception was for finished weapons, and flasks are consumables.
- A fail by 5 or more ruins half the stack's materials.
- The mishap applies **once**, not once per unit. It is one flash in one crucible
  **(proposed)**.

### 15.3 Recipes

A recipe is a saved sequence of steps with material ids and the vessel. Loading one sets up the
bench; you still roll and still play (herbalism §9.6).

Old `campaign.recipes` rows with `craft: "alchemy"` are dropped with a note (Q10.1, §18). The
forge's open item 3 (no recipe API) is not repeated: the alchemy API has `recipe` from the
start (contracts §8).

### 15.4 What the module becomes

`rules/alchemist.py`'s chain bench (`Chain`, `preview`, `_potion_for` with exact sets) retires
with the `/craft/` tab. `rules/alchemist.py` becomes the step bench, the shape of
`blacksmith.py`'s second half:
- `plan_step`, `METHODS`, `fit_reason`;
- `make`, `land`, `spend`;
- `failure_losses`, `check_terms`.

Formulae live in a new `rules/formulae.py`, and the product maths in a new
`rules/alchemy_items.py`.

**Grep every copy** (CLAUDE.md). The old method words also live in:
- `rules/benches.py` (`METHOD_GLYPHS`);
- `content/world-classes/alchemist.json`;
- `gm/judgement.py`, `gm/narration.py`, `gm/brief/market_master.py` and
  `gm/checks/repair_claimed.py`;
- `play/craft_views.py`, `play/views.py` and `play/templates/play/table.html`;
- `docs/alchemy.md`;
- `tests/test_alchemist.py` and `tests/test_crafting.py`.

The first bench lane's job is the full list.

---

## 16. The engine half

What makes an alchemical product matter in a fight. Every gap below was confirmed in code on
488b293.

### 16.1 The drink door already works

`_op_use_item` (`engine.py:11320`) plans through `consumables.plan` and runs the intents through
validation with `origin: item:<id>`. Drinking needs only:
- the new types to execute (§16.3 to §16.8);
- `when` clauses to be forwarded (§16.7);
- spell potions to resolve through the spell's documents (§11.3).

### 16.2 A thrown flask is a real attack (Q8.1)

Today a throw lands its effects on the target with no roll (`engine.py:11329-11331`, "That attack
is not emitted here"), and `SPLASH_RADIUS_FT` is read nowhere (`consumables.py:45`). The CRB rules
(§22):
- "To attack with a splash weapon, make a ranged touch attack against the target."
- "Thrown splash weapons require no weapon proficiency, so you don't take the –4
  nonproficiency penalty."
- "A hit deals direct hit damage to the target and splash damage to all creatures within 5 feet
  of the target."
- "You can instead target a specific grid intersection. Treat this as a ranged attack against
  AC 5."
- "If you miss the target, roll 1d8. This determines the misdirection of the throw, with 1
  falling short (off-target in a straight line toward the thrower), and 2 through 8 rotating
  around the target creature or grid intersection in a clockwise direction. Then, count a number
  of squares in the indicated direction equal to the range increment of the throw. After you
  determine where the weapon landed, it deals splash damage to all creatures in that square and
  in all adjacent squares."
- Range: "a cumulative –2 penalty for each full range increment … A thrown weapon has a maximum
  range of five range increments."

**The build:**
- `use_item how=throw` **emits an `attack` intent** in a new `splash` mode instead of resolving
  the effects. The dose is committed first, as today. The attack op owns the roll, which is the
  op's own docstring's intent.
- **Touch AC.** `Actor.touch_ac` (`sheet.py:2540`) is today reachable only through a stat
  block's printed touch attack (`engine.py:5202`). The splash mode uses it.
- **Range increments.** The engine has none (`range_ft` is only a reach exemption,
  `position.py:307`). The splash mode adds the −2 per full increment and the five-increment
  maximum, through a helper the weapon path can adopt later. Changing every bow is outside this
  plan; it is listed as a follow-up.
- **No nonproficiency penalty.**
- **A hit:**
  - the direct effects land on the target;
  - the **splash** (the formula's `splash` row) lands on every creature within 5 ft, through
    `areas.burst_cells` and `areas.caught`.
- **A miss:**
  - the engine rolls 1d8 for direction and counts range-increment squares;
  - it places the landing square through `Scene.place_prop(…, square=…)`, which already takes a
    square (`engine.py:1466`);
  - it deals splash to the landing square and the squares adjacent to it.
- **With no map,** a miss lands nowhere anyone stands, and the tell says it shattered wide
  **(proposed)**.
- **A grid intersection** is a valid aim at AC 5. That is how a cloud or a thunderstone is
  thrown.
- **A natural 1** follows the attack op's existing rule. Nothing is new.
- **Attitude and the battle gate.** A throw at somebody not on the thrower's side opens the
  fight through the battle gate, exactly as a first swing does (`_op_cast`'s docstring, Q31,
  Q37).

### 16.3 Speed and senses

- **Speed:** flip `engine=True` on `speed` (`effectspec.py:620-625`). The `consumables` branch
  (406-419) and the `speed_feet` funnel (`sheet.py:1594-1623`) already exist; today the flag
  sends them to narration (inv §4).
  - Climb, swim and fly need their own readers in movement. Those that have none are named in
    the lane report, never silently dropped.
- **Senses:** `sense` executes as an `ActiveEffect` granting `sense.darkvision`,
  `sense.low_light` or `sense.see_invisibility` for its duration (one vocabulary,
  `states.py:60-68` already reserves `sense.*`). Readers:
  - **see invisibility:** the attack path's concealment from `state.hidden.invisible`
    (`sheet.py:1745-1770`) is ignored by an attacker who has it;
  - **darkvision and low-light vision:** read by the light model (§16.4).

### 16.4 Light (sunrod, tindertwig)

**There is no light model** (`reactions.py:532-538`: "the map has no light level yet"). The CRB's
four levels (§22):
- bright;
- normal;
- dim: "Creatures within this area have concealment (20% miss chance in combat)";
- darkness: "creatures without darkvision are effectively blinded", which is 50%.

The light sources are a torch (20 ft normal, 40 ft raised) and a sunrod (30 and 60 ft, 6 hours).

**The build, minimal and book-shaped:**
- `Scene.light_at(square) -> "bright" | "normal" | "dim" | "dark"`, from:
  - the ambient level, by the clock and `places.roofed`;
  - every light source in the scene: a `light` effect on an actor (it moves with its carrier)
    or a manifest on a square.
- A new effect type, `light`: `{radius_ft, raised_ft, duration}`.
- **The reader** is the attack op's miss chance:
  - a target in dim light has 20% concealment, unless the attacker has low-light vision within
    twice the radius, or darkvision;
  - in darkness, 50%, unless the attacker has darkvision.

  That reuses `Actor.concealment()`. No second miss-chance path.
- **Tindertwig** lights a torch as a standard action, which needs a `light` effect on the torch
  carrier. `gear.json`'s `not_yet` on tindertwig is removed.
- **Open point 8** asks whether the light model should also drive Stealth and Perception.
  **(proposed:** later, not in this plan.)

### 16.5 Area clouds (smokestick, flash powder, thunderstone)

- A cloud is a `manifest` (the existing type: shape, size, terrain, and an `on_enter` effects
  list, `engine.py:12595`), laid at the landing square or where the user stands.
- **Fog concealment is fixed to the book.** Today obscuring squares are opaque and count as
  total cover (`grid.py:317`, `:377`), so smoke makes a target untargetable. The book's fog
  cloud: "A creature within 5 feet has concealment (attacks have a 20% miss chance). Creatures
  farther away have total concealment (50% miss chance, and the attacker can't use sight to
  locate the target)."
  - The fix is in `Actor.concealment` and the cover reader. It also corrects the *fog cloud*
    spell's own manifest, which is the book's rule anyway.
  - It is a shared-reader change, so it gets its own tests against the spell (§20).
- **Thunderstone:** a `save_gate` (Fortitude DC 15, deafened 1 hour) with `recipient: area` and a
  10-ft-radius burst at the landing square. `state.senses.deafened` already exists
  (`states.py:221`).
- **Flash powder** (a catalogue classic): the same shape, with dazzled or blinded. Its numbers
  are a house core, and the owner reviews them.

### 16.6 Burning next round, and putting it out

The book's alchemist's fire (§22): "On the round following a direct hit, the target takes an
additional 1d6 points of damage. If desired, the target can use a full-round action to attempt
to extinguish the flames before taking this additional damage. Extinguishing the flames
requires a DC 15 Reflex save. Rolling on the ground provides the target a +2 bonus on the save.
Leaping into a large body of water or magically extinguishing the flames automatically smothers
the fire."

**The build:**
- **A new effect type, `burning`:** `{dice, rounds, save, smother_bonus}`. It lands as an
  `ActiveEffect` granting **`state.burning`**, with a `periodic` damage entry per round (the
  executor exists: `activeeffect.py:66-78`, `sheet.run_periodic:960`). It ends after `rounds`.
  This is PF2e's persistent damage shape (art §2.1), with the book's numbers.
- **A new op, `extinguish`:**
  - a full-round action, refused unless the actor has `state.burning`;
  - a Reflex save at the effect's DC, +2 when the player says they roll on the ground;
  - success removes the effect;
  - standing in water (a terrain read) smothers it outright.

  `hazards.json:31` records the per-creature fire as `not_yet`. This builds it, and the hazard
  row can use it too.
- The narrator is told by tells: "Fire clings to the ogre's hide", and "Kesst rolls in the dirt;
  the flames go out".

### 16.7 "Against X only"

`when` is read only for worn gear (`_standing_mods`, `sheet.py:1094`, through `_when_holds`
4870-4955). `consumables._spec_to_intents` never forwards it, and timed buffs ignore it
(`sheet.py:3812`). So a "+2 against undead" potion applies against everything, and damage that
only hurts undead cannot be said at all.

**The build:**
- `when` is forwarded on every consumable spec, and becomes a validated `COMMON` field in
  `effectspec` (today it is unvalidated).
- `_when_holds` is evaluated:
  - **on damage**, against the struck creature: sunmetal filings and saint's tallow deal nothing
    to the living;
  - **on timed buffs**, against the roll's `ctx`.
- A ratchet test pins both.

### 16.8 Entangled and glued (tanglefoot)

- `state.held.entangled` exists (`states.py:227`) and halves speed through `state.slowed`. Its
  −2 attack and −4 Dex are the condition's data. Confirm both are read; that is the lane's first
  measurement.
- **New: `state.held.glued`:**
  - speed 0;
  - a flier "must make a DC 15 Reflex save or be unable to fly … and fall";
  - Huge and larger are unaffected;
  - the goo "becomes brittle and fragile after 2d4 rounds" (the duration).
- **A new op, `break_free`:**
  - a DC 17 Strength check, or 15 slashing damage dealt to the goo;
  - hitting the goo is automatic, and the damage roll counts (§22);
  - "Once free, the creature can move (including flying) at half speed."
- **Casting while entangled:** "concentration check with a DC of 15 + the spell's level". This
  is read by `_op_cast` if a concentration check exists. If it does not, the lane names that gap
  and does not build a concentration system inside this plan.

### 16.9 Typing the 44 potions' narrative lines

The 20 narrative and 7 speed or sense lines (measured, §11.2) each get a typed document:

| Potion | Typed as |
|---|---|
| invisibility | `apply_condition invisible`, ends on attack |
| blur | `concealment` 20 |
| heroism (skills) | `skill_mod` on all skills |
| lesser restoration | `ability_restore` (exists) |
| delay poison | `suppress_condition poisoned` |
| neutralize poison | `remove_condition poisoned`, plus `immunity poison` |
| remove paralysis | `remove_condition paralyzed` |
| align weapon | `strikes_as` alignment. `STRIKES_AS` is extensible (forge contracts §2). |
| keen edge | an item rider that doubles the threat range |
| longstrider, expeditious retreat, haste, spider climb, fly | `speed` (§16.3) |
| darkvision, see invisibility | `sense` (§16.3) |

Those that need a new reader are:
- enlarge and reduce person (size);
- endure elements;
- comprehend languages;
- pass without trace;
- water breathing;
- gaseous form;
- protection from energy (an absorbing pool);
- protection from evil's mental and summoned-contact clauses.

These land as `permission` tags granted for the duration. `permission` becomes executable **as
a tag grant**: one vocabulary, an `ActiveEffect`, and a tell. Each tag's reader is listed in the
lane report as built or not built. A tag that nothing reads is honest; prose that pretends is
not. The ledger in the `states-effects-tells` skill records which readers are still promised.

### 16.10 Stacking: one switch (Q8.4)

- **The book:** "bonuses of the same type are not cumulative (do not 'stack'), only the greater
  bonus granted applies" (CRB Getting Started, Common Terms). `dice.stack` (`dice.py:51-73`)
  already does exactly that for `alchemical`. That is why today's antitoxin is +1 (inv §0.2).
- **The owner:** with the `magic_stacking` house rule on, they stack.
  - The house rule's own text (`houserules.py:16-23`) is: different sources add, and the same
    source reapplies.
  - **Today it is read only by `gain_temp_hp`** (`sheet.py:2676-2684`), and the funnel never
    sees it.
- **The build:** `dice.stack(mods, *, magic_stacking)` reads the switch. With it on, two typed
  bonuses from **different `source`s** add, and the same source keeps the better
  (`Modifier.source`, `dice.py:33`).
  - Every caller passes the switch through `houserules.magic_stacking()`.
  - One switch, one funnel. No alchemy-only path.
- **What that reaches.** The house rule's text says typed bonuses "join it when the engine
  executes them at all", so the switch reaches **every typed bonus**, not only alchemical ones.
  That matches the rule as written, and it also changes enhancement, morale and the rest when the
  switch is on. **Open point 2** confirms the scope.

### 16.11 Shared infrastructure this plan consumes

Both pieces are built by the **enchanting lanes first**. Alchemy names the interface it needs
and does not build either. The full shapes are in contracts §10.

**In progress** (owner, leatherworking Q9.3).
- **Alchemy needs:**
  - add a row (craft `alchemist`, a label, the product's stock dict, the started and ready
    minutes);
  - list the rows with game-time countdowns;
  - collect one once it is ready;
  - and **the engine's use door must refuse an uncollected product.**
- **Until it lands,** alchemy uses herbalism's `Stock.ready_minute` (`crafting.py:131`), which
  the use door already refuses (`engine.py` steeping check). The rows migrate into In progress
  when it ships.

**The metal tag** (owner, leatherworking Q7.3). Alchemy asks it in three places:
1. `corrosive` refuses a metal vessel (§5.5);
2. gray ooze core and aqua regia damage **metal** gear on a hit (`object_damage` against the
   struck creature's metal-tagged armour and weapon, the book's ooze shape);
3. the vessel list knows which vessels are metal (iron flask, brass casing), and so neither
   shatters.

### 16.12 Tells

Law 3: every application emits a tell, and the narrator is fed tells only. New tells:
- the splash (who it caught);
- the miss ("the flask breaks two squares behind the ogre");
- burning and extinguishing;
- glued and breaking free;
- a light coming on, and the smoke rising;
- the mishap at the bench;
- the potion's spell taking hold, by the spell's own name ("the haste takes; Kesst moves like
  water").

---

## 17. How it obeys the three laws

1. **One vocabulary.**
   - Essences are `essence.*` tags.
   - Working traits are `working.*`.
   - The new states are `state.burning`, `state.held.glued`, `sense.*` and the permission tags.
   - Formulae match on essence **sets**, never on material names or strings.
2. **One applicator.**
   - Drinking, splashing, burning, gluing, light, clouds and mishaps all land as `ActiveEffect`s
     or as damage through `_apply_damage`, with `origin: item:<id>` or `rule:mishap:<id>`.
   - Quality, grades and perks scale the document **before** it is applied.
   - Stacking stays in `dice.stack`. Nothing is added outside the funnel.
3. **Severed tells; no model authors a number.**
   - Book numbers are typed by hand.
   - House numbers are drafted inside validator fences and reviewed by the owner.
   - Grades come from data, the tier comes from the player's score through the server, and the
     caster level comes from the rule.
   - Validators refuse, with the fix named:
     - a material with fewer than three properties, no drawback, a narrative trait, or a house
       number over its tier ceiling;
     - a formula whose core is not executable;
     - an authored formula whose signature is not unique.

---

## 18. Migrating old saves

The owner chose **convert** (Q10.1, Q10.2). A version-stamped migration, `alchemy_v2`, runs once
per character. Its shape is `worldclass.MIGRATIONS` (516), as herbalism and the forge did.

1. **Levels.** Old levels 4 and 5 (and any higher, which granted nothing) keep their number as
   **endless levels**, with their perk picks banked. The picker opens on the first visit to the
   bench, and nothing is spent until the player chooses. Banked mastery carries over. The old
   level-5 milestone is dropped.
   - **Note:** under the owner's spell rule an old Alchemist 3 now brews 1st-level potions only.
     They needed 4 for 2nd. That is the rule, and their stock is untouched.
2. **Stock.** Every row with `craft: "alchemist"` stays usable and sellable, marked **old
   work**, with its specs exactly as they are. Old work is not re-derived; new work is built on
   read (§12.2).
3. **Spell potions keep every id and `holds_spell` exactly** (Q10.2), and `caster_level` too.
   That is pinned by `tests/test_magicitem.py:207` and `:254`, and a new test loads an old save
   and spends its potion at the enchanter.
4. **Recipes.** `campaign.recipes` rows with `craft: "alchemy"` are dropped, with one note in the
   session log naming them (Q10.1).
5. **Knowledge.**
   - A converted alchemist knows every property of every material they have crafted with, where
     the save records it.
   - They know the four classics, and **every formula whose product they hold or have made**,
     since they made it.
6. **The `basilisk-eye` gland** in old stock already resolves to the merged herb (§5.7).
7. **Proof.** Run the migration against a read-only copy of the owner's save in the scratchpad,
   and against Bobby, and round-trip through save and load.

---

## 19. World Bible

Fixes are world-agnostic (the 2026-09-28 standing instruction). `docs/from-world-bible.md`
asks nothing of alchemy today (inv §9).
- **A world's reagents** need the same fields as ours, as optional fields with defaults in
  `docs/campaign-format.md`:
  - `product` (with `route`, `essence`, `grade`, `drawback`);
  - `working`, `mishap`, `toxic`, `color`;
  - `form` and `material`.
- **`play.materials[]`** (`campaign-format.md:350`) is described as forge material. It is
  widened to every craft, with a `shelves` field. One material, many shelves.
- **A world's herbs** keep `hybrid`, and each effect gains an optional `essence`.
- **Formulae are not exported.** The table is fixed and world-agnostic (Q5.2). A world's
  reagents feed it through their essences, and its spells feed it through the spell corpus.
- **Places and people.** A world's laboratories and alchemists, through the `alchemy` occupation
  tag and a `laboratory` place tag, in the existing place and people rows.
- **What the next export should carry** is listed in `docs/from-world-bible.md`, beside the
  forge's list.

---

## 20. Build order (lanes)

| # | Lane | Contents | Writes |
|---|---|---|---|
| 1 | **Shelf door and the collision** | **The `basilisk-eye` merge and the widened id test (urgent, §5.7)**; the alchemist reads through `rules/materials.py`; `normalise` maps `effects` to `product`; hybrid herbs on the alchemy shelf; `knowledge` counts the alchemy fields | `rules/materials.py`, `rules/knowledge.py`, `content/ingredients/herbs-and-parts.json` (the merge only), `content/materials/alchemist-materials.json` (the deleted row only) |
| 2 | **Vocabulary** | `essence` and `grade` on effects; the new routes; the alchemy `WORKING_TRAITS`; `speed` and `sense` executable; the new types `light` and `burning`; `permission` as a tag grant; `when` as a validated field | `rules/effectspec.py` |
| 3 | **Engine readers** | §16.2 to §16.10: the splash attack, range increments and scatter, burning and `extinguish`, glued and `break_free`, the light model, sense readers, fog concealment, area clouds, `when` on consumables and damage, spell potions through the spell's documents, and the stacking switch | `rules/engine.py`, `rules/sheet.py`, `rules/consumables.py`, `rules/areas.py`, `rules/dice.py`, `rules/states.py`, `rules/intents.py` |
| 4 | **Data pass** | §5: the book fix by hand, essences, traits, mishaps and toxic documents in fences, the review table, text rewrites, the 44 potions typed (§16.9), price checks | `content/materials/alchemist-*.json`, `content/ingredients/herbs-and-parts.json` (essences only), `tools/alchemy_*.py`, `docs/alchemy-review.md` |
| 5 | **Formulae** | §10 and §11: the formula table, derived spell formulae, signatures, matching, the count, writings, the formulary store, caster level and price | `rules/formulae.py`, `content/rules/alchemy-formulae.json`, `content/rules/alchemy-essences.json` |
| 6 | **Bench rules and API** | §4, §6, §7, §8, §9, §12, §15: levels, perks, inheritance and slots, the nine methods, volatility, Transmute, products, In progress use, the API | `rules/alchemist.py`, `rules/alchemy_items.py`, `content/world-classes/alchemist.json`, `content/rules/alchemy-grades.json`, `play/alchemy_views.py`, `pathfindergm/urls.py` (alchemy routes only) |
| 7 | **Places** | §14: the `alchemist` occupation, town laboratories, hourly rent, the owned laboratory, the field kit | `rules/places.py`, `rules/market.py`, `content/people/occupations.json` |
| 8 | **Prices and shops** | §12.4 and §12.5: book prices, potion prices, shop items as documents, the stall line, manuals and formularies | `rules/pricing.py`, `rules/goods.py`, `content/rules/gear.json`, `content/rules/stall-lines.json`, `content/rules/alchemy-manuals.json` |
| 9 | **Migration and World Bible** | §18 and §19 | `rules/worldclass.py` (the migration entry), `docs/campaign-format.md`, `docs/from-world-bible.md` |
| U1 to U5 | **UI and 3D** | the UI plan's lanes | `play/static/…` |

**Why this order.**
- Lane 1 comes first because the collision becomes live the moment the hybrid door opens, and
  every later lane reads the shelf through the door it builds.
- Lanes 2 and 3 make a hand-written alchemist's fire **do something in a fight** before any of
  the 139 documents are rewritten. The data pass can then be checked in play, not just by
  validators ("verify end to end, on real regenerated content").

Lane 2 depends on 1. Lane 3 depends on 2. Lanes 4 and 5 depend on 2, and run in parallel. Lane
6 depends on 4 and 5. Lanes 7 and 8 can run beside 6. Lane 9 is last. The flat UI shell (U1) can
start as soon as lane 6's API exists.

### 20.1 Tests each lane must add

Each names the defect it prevents in its docstring.

- **Lane 1:**
  - no material id equals an ingredient id (`basilisk-eye` was both, and `resolve` returned the
    gland);
  - `knowledge.property_keys` is at least 3 for every alchemy material (it was 0 for all 139);
  - a hybrid herb resolves on the alchemy shelf (`alchemist.get("phoenix-feather")` raised
    KeyError).
- **Lane 2:**
  - `speed` and `sense` are executable (a potion of longstrider produced no intents);
  - a `when` clause is validated.
- **Lane 3:**
  - a thrown alchemist's fire **rolls a ranged touch attack**, and on a hit deals 1 fire to an
    ally standing 5 ft away (today: no roll, no splash);
  - a miss lands range-increment squares away, by the 1d8, and splashes there;
  - the target burns 1d6 next round unless `extinguish` succeeds (DC 15, +2 rolling);
  - a tanglefoot hit glues on a failed DC 15 Reflex, and `break_free` at DC 17 Strength frees;
  - a sunrod raises the light at 30 ft, and dim light gives 20% concealment, which darkvision
    ignores;
  - a smokestick's fog gives 20% within 5 ft and 50% beyond, **and the *fog cloud* spell now
    does too** (both were total cover);
  - sunmetal damage does nothing to a living target;
  - **two antitoxins give +5, not +10, with `magic_stacking` off; antitoxin plus a different
    alchemical +2 give +7 with it on** (one switch, one funnel);
  - a potion of haste moves the drinker 30 ft faster (it narrated).
- **Lane 4:**
  - every material has at least 3 properties and at least 1 drawback, with no narrative
    traits;
  - house numbers are within the tier ceilings;
  - the book items match §5.4 by set comparison;
  - every material is relevant;
  - every one of the 44 potions is fully typed;
  - every formula's cheapest inputs are listed against the book fraction.
- **Lane 5:**
  - the classics and the 44 have unique signatures;
  - the possible-formulae count on a fixed mix equals a hand count;
  - an experiment writes a formula only when its signature is unique within reach;
  - the spell level cap is max(1, floor(level / 2)) at 1, 3, 4, 17 and 18;
  - caster level is the book minimum plus one per tier above Sound;
  - a potion's price is 50 × spell level × caster level (a haste potion sold for 60 gp against
    the book's 750).
- **Lane 6:**
  - a minigame miss after a successful roll never costs materials;
  - a fail by 5 or more on a volatile step applies the stated mishap, once per batch, and a
    stabilizer cancels one;
  - same-named traits add, capped at the level;
  - a potion carries at most 3 benefits, and drawbacks come along unless Filtered;
  - a finished good is refused as an input;
  - **preview potency reaches the stock** (`preview` multiplied it and the stock said 1.0, inv
    §0.1);
  - Transmute refuses two bands, or a different kind;
  - a toxic step without protection applies its document.
- **Lane 9:**
  - an old Alchemist 5 save loads as level 5 with picks banked;
  - an old potion of invisibility still stands in at the enchanter.

---

## 21. Open points for the owner

Everything marked **(proposed)** is open to tuning in playtest; it all lives in rule rows. These
are the choices I could not settle from the rounds:

1. **The essence vocabulary.** Eighteen essences (§5.3). Fewer makes formulae collide more; more
   makes them harder to learn. Accept the 18, or adjust?
2. **The stacking switch's reach** (§16.10). Wiring `magic_stacking` into the funnel as the house
   rule's own text says makes it reach **every typed bonus** from different sources (enhancement,
   morale and the rest), not only alchemical. Is that intended, or should the switch reach
   alchemical bonuses only?
3. **Do house splash flasks splash?** By the book, splash belongs to the named splash weapons.
   **(proposed:** only formula cores carry splash; a house flask hits its target only.)
4. **Experiment against writings for spell potions** (§10.3). On the draft mapping, 19 of 791
   corpus spells have a unique essence signature (157 with the spell level added), so most spell
   formulae can only come from writings. The classics and the 44 are always findable by
   experiment. Is that split right?
5. **Harmful spells in a potion** (§11.2). By the book and your rule, the drinker is the target,
   so a potion of *hold person* holds its drinker. Keep that, or let harmful spells go into
   splash flasks (thrown, the struck creature as the target)? That would be a further house
   rule.
6. **Quality and a spell potion's price** (§11.4). I read Q4.4 plus Q6.4 as "quality raises
   caster level, and the book price follows caster level", without multiplying a second time.
   Confirm?
7. **Every city gets a laboratory** (§14), as the forge's ruling did for smithies?
8. **The light model's reach** (§16.4). This plan uses light for miss chance only. Should it
   also drive Stealth and Perception now, or later?
9. **Learning a formula from a potion in hand** (§10.4), as a house rule mirroring the
   enchanter's disenchant. The potion is spent. Keep it?
10. **Transmute's economy** (§9). Pairs whose output is worth more than three times the inputs go
    to you as a review table. Is three the right flag?
11. **Icons.** The alchemy bench needs about 20 glassware and method icons from game-icons.net
    (CC BY 3.0), downloaded the way the forge's were (forge contracts §13.1). May the lead
    download them?
12. **The PF1e alchemist character class's extract list** (408 spells) is not used. Your rule
    makes every spell eligible, so the list adds nothing for now. Confirm it stays unused until
    a PF1e alchemist class exists?

---

## 22. Sources for the new mechanics

Primary sources (Paizo rule text on Archives of Nethys and the legacy PRD), checked 2026-10-05:

| Rule | Source |
|---|---|
| Throw splash weapon: ranged touch, no proficiency, splash within 5 ft, intersection AC 5, 1d8 miss scatter | https://www.aonprd.com/Rules.aspx?Name=Throw%20Splash%20Weapon&Category=Special%20Attacks |
| Range increments: −2 per increment, thrown maximum five | https://legacy.aonprd.com/coreRulebook/equipment.html (weapon qualities, Range) |
| Alchemist's fire: next-round 1d6, full-round extinguish, DC 15 Reflex, +2 rolling, water smothers; 10 minutes with a lab | https://www.aonprd.com/EquipmentMiscDisplay.aspx?ItemName=Alchemist%27s%20fire |
| Tanglefoot bag: entangled, glued, DC 17 Strength or 15 slashing, flier falls, brittle after 2d4 rounds, Huge immune, concentration DC 15 + spell level | https://www.aonprd.com/EquipmentMiscDisplay.aspx?ItemName=Tanglefoot%20bag |
| Acid, smokestick (as fog cloud), sunrod, thunderstone, tindertwig, antitoxin, holy water | https://legacy.aonprd.com/coreRulebook/equipment.html (Special Substances and Items) |
| Fog cloud: 20% within 5 ft, total concealment beyond | https://legacy.aonprd.com/coreRulebook/spells/fogCloud.html |
| Light levels, darkvision, torch and sunrod radii | https://legacy.aonprd.com/coreRulebook/additionalRules.html (Vision and Light) |
| Catching on fire: Reflex DC 15, +4 rolling (general fire; alchemist's fire prints +2) | https://www.aonprd.com/Rules.aspx?Name=Catching%20on%20Fire&Category=Fire%20Effects |
| Potions: price, drinker as target and caster, standard action, provokes, oils, identify DC 15 + spell level | https://legacy.aonprd.com/coreRulebook/magicItems/potions.html |
| Magic item creation: personal range barred, caster level never below the minimum to cast, DC 5 + CL | https://legacy.aonprd.com/coreRulebook/magicItems/magicItemCreation.html |
| Alchemist's lab +2 circumstance, 200 gp, 40 lb | https://www.aonprd.com/EquipmentMiscDisplay.aspx?ItemName=Alchemist%27s%20lab |
| Alchemy crafting kit, 25 gp, 5 lb, no Craft bonus | https://www.aonprd.com/EquipmentMiscDisplay.aspx?ItemName=Alchemy%20crafting%20kit |
| Copying spells: DC 15 + spell level, 1 hour, scroll used up on success, a week before retrying, spellbook costs | https://legacy.aonprd.com/coreRulebook/magic.html (Arcane Magical Writings) |
| The APG alchemist's formula book, identifying potions, Brew Potion as a bonus feat | https://legacy.aonprd.com/advancedPlayersGuide/baseClasses/alchemist.html |
| Bonus types do not stack; the greater applies | https://legacy.aonprd.com/coreRulebook/gettingStarted.html (Common Terms) |
| Brew Potion time (2 hours, or 1 day per 1,000 gp) | https://legacy.aonprd.com/coreRulebook/feats.html (art §1.2) |

Game and research precedents are cited from `docs/alchemy-prior-art.md` by section.

**Could not confirm:**
- whether Paizo's FAQ resolves Brew Potion's two times (art §8);
- the minimum caster levels of the 6-level casters' lists. The plan reads them from the app's
  class documents rather than from a printed table, and says so (§11.3).

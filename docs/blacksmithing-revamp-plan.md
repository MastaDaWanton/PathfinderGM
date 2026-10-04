# Blacksmithing revamp: the plan

Drafted 2026-10-03 from five rounds of the owner's answers. The prior-art sweep it leans on is
`docs/blacksmithing-prior-art.md` (97 sources, with a critic pass). The interface half is
`docs/blacksmithing-ui-plan.md`. Nothing here is built yet. Numbers marked **(proposed)** are my
defaults and need tuning or a ruling; everything else is the owner's decision as given.

This plan follows `docs/herbalism-revamp-plan.md` wherever the owner said "same as Herbalism",
and says so rather than repeating it.

---

## 1. What blacksmithing is for

The same three kinds of fun as herbalism, in the same order: **hands-on craft** at the anvil,
**discovery** of what each metal does, and a **way to be seen** through the world's renown
system (not something the class hands out).

What is new is the **build**. A weapon or a suit of armour is made of pieces, each piece is a
material, and each material carries small typed numbers. Choosing an iron head on an ash haft
with brass fittings is a decision with visible consequences on the sheet. Herbalism is about
*what* you brew; smithing is about *what you put together*.

**And it has to matter in play.** Today a forged sword is correct data that changes no roll
(§12). The engine half of this plan is not optional: without it, the data pass would ship 112
well-formed documents that do nothing.

---

## 2. The owner's decisions (2026-10-03)

| Area | Decision |
|---|---|
| Book or ours | **The book's effects**, in the correct (typed, executable) format. And **more** from each material: at least 3 modifiers for weapons and 3 for armour, so where the book gives fewer, house modifiers make up the rest and "both win". |
| Every material | Gets **at least one negative**. Example given: iron is heavy and slow, so +1 damage, −1 to hit, and one more positive. Keep the numbers **small**, so the materials can be worked up without becoming overpowered. (The base was later set at ±2; see "Base value" below.) |
| How many | **3 weapon modifiers + 3 armour modifiers** per structural material. |
| Pieces | Weapons: **head, haft, fittings**. Armour: **body, fastenings, lining**. Each piece is one material and adds its modifiers. |
| Weighting | The **main piece counts in full**, the other two count **half**, before rounding. The book's special powers (adamantine through hardness, cold iron against fey, silver against lycanthropes) come **only from the main piece**, as the book says ("only the most prevalent material"). |
| Rounding | Numbers are **rounded down to the nearest whole number** on the final product. |
| Strengthen | The smithing concentration. **Two bars make one strengthened bar, every modifier ×1.5**, bonuses and negatives alike. **Each Blacksmith level after the first cuts the negatives by 10%.** |
| Two layers | Every material has **item effects** (what the finished item does) and **working traits** (how it behaves at the forge). |
| Consumables | Fuels and fluxes carry **working traits only**. Quenchants carry working traits plus **one small "quench mark"** they leave on the item. |
| Discovery | **Assay** replaces tasting, and study, teachers, libraries and manuals work as for herbs. |
| Assay | Costs **a sliver** (a tenth of a bar, or one ore), takes **10 minutes**, reveals **one positive and one negative** property. No danger, except for reactive metals (noqual, abysium), where it is real. |
| Levels | **Same as Herbalism**: levels 1–3 open methods and rarity, then endless levels with two perk picks each. |
| Methods | **Trim and add**: Smelt, Alloy, Forge, Quench, Temper, Fold, Hone, Assemble, Finish, Strengthen, Assay. Flux becomes an ingredient of Smelt, Draw merges into Forge, Polish into Hone, Rivet becomes Assemble. |
| Chain | **Real intermediates** land on the shelf: ingot, named alloy bar, blank, plate, then the finished item. Each is sellable. |
| Masterwork | An item finished at **Superior or better is masterwork** (+1 attack, or −1 armour check penalty), so the enchanter can use it. Higher tiers add to the material modifiers instead. |
| Where | **Field kit + smithy.** The kit does common and uncommon work anywhere. A smithy, either a town forge you pay to use or one you found and own, opens rare and above, plus Smelt and Alloy, which need a real furnace. |
| Bench rules | **Same as Herbalism**: the d20 decides success, a minigame per method climbs the quality tier, always played, a bulk stack shares one result, and the PF1e fail rule applies. |
| Heat | **Heat inside each game.** The metal's colour cools as you work; strike in the right band; reheat mid-game at a small time cost. Nothing carries between steps. |
| On the sheet | A **real, wieldable item**. Its material modifiers apply only to its own attacks, its book powers bypass DR, and the sheet names every number's source. Worn armour changes AC, armour check penalty, max Dex and speed. |
| Old saves | **Convert**, as Herbalism did. |
| Shared metals | **One material, many shelves.** Mithral is one document; the leatherworker's mithral fittings and the enchanter's mithral filings are forms of it. Learning mithral at the forge teaches it everywhere. |
| UI | Its **own bench**, built from the herb bench's parts. The stage shows the kit on the ground or a smithy; the work is **built from its pieces** in 3D; **engraved icons** as for herbs. See the UI plan. |
| Base value | **House modifiers start at ±2, not ±1** (ruled after the first draft). A half-weight piece then gives ±1 instead of rounding to nothing. |
| The five open points | All accepted as proposed: negatives round **toward zero**; **no bulk at Assemble** for finished weapons and armour; skymetal names **wait on the licensing decision**; skipping Temper **leaves a real flaw** (`brittle`). |

---

## 3. What the research changes

From `docs/blacksmithing-prior-art.md`:

- **Fix the book entries before adding anything.** Eleven catalogue entries contradict the
  printed rules (§5.2 of the sweep): mithral's proficiency claim, fire-forged steel's condition
  on the wrong item, viridium's disease, abysium's invented save, horacalcum by armour weight,
  singing steel's invented Perform bonus, and inubrix and noqual missing their drawbacks
  (noqual: +20% spell failure on armour, +5,000 gp to enchant). §5.3 of this plan is that fix.
- **Two layers is prior art, not invention.** Pathfinder Unchained's raw-material traits (easily
  worked, flawless, malleable, pure) are the working layer; WoW and ESO split base material from
  typed add-ins the same way.
- **Do not model physics.** Dwarf Fortress's creator could not finish per-material physics data.
  We use a few typed fields per material, which is what Wurm Online does (a small modifier
  vector against iron).
- **Every smithing minigame that shipped was softened afterwards** (KCD2 patch 1.2, RuneScape 3,
  OSRS, Vintage Story). Start generous, and **show heat as a number and bar as well as a
  colour**: KCD2's first patch made cooling readable, and colour alone fails accessibility.
- **Better metal, tighter window** (OSRS Giants' Foundry). Rarity can make the minigame harder
  without raising the DC.
- **Quality multiplies on top of material and never replaces it** (Dwarf Fortress). A crude
  adamantine sword is still adamantine.
- **No random quality**, and no losses after a successful roll (WoW removed Inspiration for "a
  lack of decision making and agency"). Materials are lost only to the d20, as in herbalism.
- **Fold helps dirty metal most.** Pattern welding was a fix for uneven bloom iron. That is a
  grounded rule: Fold cancels *slaggy*, and adds little to good steel.
- **Assaying is comparison.** Touchstone and spark testing classify against known references.
  Each metal you already know makes the next assay easier (§9.2).
- **Licensing.** The Core and Ultimate Equipment materials are Open Game Content. The skymetal
  names and *nexavaran* come from Adventure Path books whose declarations make proper names
  Product Identity. Same caution as the bestiary (`docs/bestiary-licensing.md`): the mechanics
  are open, the names are an open question. **This plan does not rename anything**; §15.2 lists
  the eleven entries for the owner's licensing call.

---

## 4. Progression

### 4.1 Levels 1–3

| Level | Opens | Materials | Where |
|---|---|---|---|
| 1 | **Forge, Quench, Assemble, Assay**, and Smelt at a smithy | common, uncommon | field kit (Smelt needs a furnace) |
| 2 | **Alloy, Temper, Fold, Hone, Strengthen, Finish** (mundane treatments) | rare, exotic | Alloy, Fold and Strengthen at a smithy |
| 3 | **Legendary material, and Finish with sacred and planar treatments** (holy anointing, ghost-salt blanching, styx water) | legendary | smithy |

Level 3 mirrors herbalism's Neutralize: the last level opens the dangerous and the sacred.
**(proposed)**

Mastery thresholds stay at 25 and 65, as for the herbalist (`blacksmith.json` already copies the
herbalist's thresholds on purpose: "the two tracks are meant to pace the same").

**Removed:** the level 4 and 5 rows, the `legendary-metal` milestone and its deed, Draw and
Polish as methods, Flux as a method, Rivet. Their tests are retired and their defects re-pinned
against the new gates, as `test_legendary_catalyst.py` was for herbalism.

### 4.2 Endless levels (4 and up)

Pick two perks per level; the same one twice is allowed. Stored as live-read documents on
`Progress.perks`, exactly as herbalism (stage 8's rule: never a stored `ActiveEffect` per perk).

| Perk | Per pick **(proposed)** |
|---|---|
| Potency | +5% to the **bonus** modifiers of everything you make |
| Hardening | −5% to the **negative** modifiers, on top of the per-level cut |
| Quality | +1 to the quality ceiling |
| Yield | +5% chance per Smelt or Forge of one extra ingot or blank; the engine rolls it and shows the roll |

Threshold curve: 50 + 10 × (level − 3), as herbalism. **(proposed)**

### 4.3 The negative cut

The owner's rule: each Blacksmith level after the first cuts the negatives by 10%. Applied
multiplicatively with Hardening, and **floored at 50%** so a negative never vanishes
**(proposed: the floor)**. At level 6 with two Hardening picks: 0.9^5 × 0.95^2 ≈ 0.53 of the
raw negative.

### 4.4 The quality ceiling and masterwork

| Standing | Ceiling |
|---|---|
| Level 1 | Fine |
| Level 2 | Superior (masterwork reachable) |
| Level 3 | Flawless |
| Each Quality perk | +1 |

**Masterwork** is Superior or better: the book's +1 attack for a weapon, or −1 armour check
penalty for armour. It is a typed effect on the item with `origin: rule:masterwork`, not a
material modifier, so it never scales with Strengthen.

### 4.5 Mastery sources

As herbalism §4.4: each successful step (1, +1 per rarity band above common), the quality
bonus (+1 at Superior, +2 at Flawless or higher), firsts (learn a property, make a product
kind, work a new material: +3 each), and reading an unread smithing manual (+5 once each).
`REPEAT_LIMIT` and `MISHAP_LIMIT` stay, keyed on (method, material).

---

## 5. Materials: the data pass

### 5.1 Today

From the inventory (all counts measured):
- 112 materials: metal 21, ore 20, fitting 16, alloy 15, quenchant 11, fuel 10, treatment 10,
  flux 9.
- 55 have effects, 57 have none. Of 63 effect specs, **40 are `narrative`** (prose, not
  executable). **None carries a route, a piece or a duration.**
- Under the herb trait rule, materials have 0 (58), 1 (47) or 2 (7) traits. **None has 3.**

### 5.2 The material document

Every field defaults, so an old file still loads (the same rule as `herbprep.Prep`).

```json
{
  "id": "iron", "name": "Iron", "kind": "metal", "form": "bar", "tier": "common",
  "pieces": {"weapon": ["head", "fittings"], "armour": ["body", "fastenings"]},
  "weapon": [
    {"type": "combat_mod", "target": "damage", "amount": 2, "bonus_type": "material"},
    {"type": "combat_mod", "target": "attack", "amount": -2, "bonus_type": "material"},
    {"type": "gear_mod",   "target": "hardness", "amount": 2}
  ],
  "armour": [
    {"type": "combat_mod", "target": "ac", "amount": 2, "bonus_type": "material"},
    {"type": "gear_mod",   "target": "acp", "amount": -2},
    {"type": "gear_mod",   "target": "hardness", "amount": 2}
  ],
  "working": [
    {"type": "working", "trait": "forgiving", "note": "wide heat band"}
  ],
  "quench_mark": null,
  "book": false,
  "forms": ["ore:iron-ore", "ingot", "bar"]
}
```

| Field | Meaning |
|---|---|
| `form` | ore, ingot, bar, alloy bar, blank, plate, haft, grip, guard, fuel, flux, quenchant, treatment. A *form* of a material, not a separate material (the "one material, many shelves" ruling). |
| `pieces` | Which piece slots it can fill, per gear kind. Woods fill `haft`; leathers and wraps fill `haft` (grip) or `lining`; metals fill head/body and fittings/fastenings. |
| `weapon` / `armour` | **At least 3 effect documents each**, **at least 1 negative each**, all executable. Only structural materials have these. |
| `working` | Working traits (§5.5). Every material has at least one. |
| `quench_mark` | One effect, quenchants only (§5.6). |
| `book` | Marks a material whose book effects are in the lists. Book effects carry `"book": true` individually: they are applied **from the main piece only**, never weighted, never scaled by Strengthen or quality (§6.3). |
| `forms` | The chain of forms it passes through, so a prospected ore and a bought bar are the same material. |

**`bonus_type: "material"`** is new. Two material bonuses on the same roll would only meet if
two items applied to one roll, which the item scope (§12.2) prevents for attack and damage. For
AC, armour material folds into the **armour bonus** and shield material into the **shield
bonus**, as the book does for gold armour's −2 AC. **(proposed)**

### 5.3 Two new effect types

The vocabulary (`rules/effectspec.py`) has 26 types. Metals need two more, rather than prose:

| Type | Targets | Why |
|---|---|---|
| `gear_mod` | `acp`, `max_dex`, `asf`, `weight_pct`, `hardness`, `hp_per_inch`, `category` (armour weight class for movement only), `speed_penalty` | The item's own numbers. Mithral's "−3 ACP, +2 max Dex, −10% spell failure, half weight, one category lighter for movement" is five `gear_mod`s, all executable, where today it is one prose line. |
| `strikes_as` | `cold_iron`, `silver`, `adamantine`, and later others | What the weapon counts as for damage reduction and hardness. Read by the damage path (§12.3). Today `Reduction.bypassed_by` exists and nothing ever passes it a trait. |

Both get validators in `effectspec.validate`, renderers in `effectspec.render`, and entries in
the catalogue so the homebrew bench can author them.

### 5.4 The book fix (do this first)

Every entry in the sweep's §5.2 table is corrected to the printed rule, with the book's numbers
as `"book": true` effects. Then house modifiers top each list up to 3. Examples:

| Material | Book effects (main piece only, fixed) | House top-up to 3 (scaled) |
|---|---|---|
| **Mithral** (armour) | `gear_mod` acp +3 (penalty 3 lighter, min 0), max_dex +2, asf −10, weight_pct −50, category −1 (movement only) | already ≥3; house negative: `gear_mod` hardness −5 vs steel (book hardness 15) |
| **Mithral** (weapon) | `strikes_as` silver, `gear_mod` weight_pct −50 | +2 `combat_mod` attack (light in the hand); negative: −2 damage |
| **Adamantine** (weapon) | `strikes_as` adamantine (ignores hardness < 20) | +2 damage; negative: `gear_mod` weight_pct +10 |
| **Adamantine** (armour) | `damage_reduction` 1/2/3 by armour weight | +2 AC; negative: ACP −2 (it does not flex) |
| **Cold iron** (weapon) | `strikes_as` cold_iron | +2 attack vs fey (`when`); negative: −2 hardness (forged low, it is softer) |
| **Alchemical silver** (weapon, Finish) | `strikes_as` silver, `combat_mod` damage −1 (slashing and piercing only, min 1) | it is a treatment, not a piece: one house mod, +2 damage vs lycanthropes |
| **Noqual** (armour) | asf **+20** (all casting), save +2 vs spells, object +4 vs magic, weight −50, category −1, max_dex +2, acp +3 (3 lighter); **+5,000 gp to enchant** | already ≥3 |
| **Abysium** | carrier `apply_condition` sickened while carried and 1d4 hours after (no save) | +2 damage (it burns); negative: the carrier effect *is* the negative |

The book's prices (+3,000 gp for an adamantine weapon, ×2 for cold iron, and so on) go into
`price_gp` per form so the market and the Appraise check agree with the book.

### 5.5 Working traits

From Pathfinder Unchained, plus grounded ones from the sweep's §3. Each is a typed document the
bench reads; none reaches the finished item.

| Trait | Effect at the bench | Source |
|---|---|---|
| `easily_worked` | step time ×0.5 | Unchained |
| `flawless` | no DC increase for masterwork | Unchained |
| `malleable` | a fail by 5+ ruins nothing | Unchained |
| `pure` | roll the Craft check twice, keep the better | Unchained |
| `slaggy` | quality ceiling −1 until Fold is applied | bloomery iron |
| `sulfurous` | (fuel) heat band +10% wider, but a Crude result also adds a `hot_short` flaw (−1 hardness) | raw coal |
| `clean_heat` | (fuel) no flaw risk | charcoal, coke |
| `quench_sensitive` | the quench band is 30% narrower; brine cracks it on a miss | high-carbon steel |
| `narrow_window` | heat bands 20% narrower (rarity makes the game harder, not the DC) | Giants' Foundry |
| `forgiving` | heat bands 20% wider | common iron, bronze |
| `reactive` | assaying it is dangerous (noqual, abysium) | the owner's assay ruling |

Fluxes: `cleans_slag` (cancels `slaggy` at Smelt), `weld_aid` (Fold and Strengthen bands wider).
**(proposed: all band percentages)**

### 5.6 Quench marks

Each quenchant leaves one small effect on what it hardens, plus its working trait (water: none;
brine: hard but `quench_sensitive` risk; oil: soft and safe).

| Quenchant | Mark **(proposed)** |
|---|---|
| Troll blood | `fast_healing` 1, once per day, 1 minute (needs the periodic executor, §12.6) |
| Wyvern blood | the first wound each day: `save_gate` Fort DC 17, on failure 1d4 Con damage (a hit trigger) |
| Dragon blood | `resistance` 2 to the dragon's energy type (armour) or +1 energy damage (weapon) |
| Blessed water | +1 damage vs undead. Not `strikes_as` good: in the book, alignment DR needs magic, and a quench is not magic |
| Glacier melt | `resistance` cold 1 |
| Styx water | +1 damage vs outsiders; negative: the wielder −1 on Will saves |
| Mercury bath | `gear_mod` hardness +1 |

### 5.7 Relevance, as herbalism's

- **Every material is relevant.** It fills a piece, feeds a method (fuel, flux, quenchant), or
  finishes an item. A test pins it (herbalism's `test_herb_relevance.py` pattern).
- **Three traits to discover.** Structural materials have 3 + 3 + working ≥ 7; fuels, fluxes and
  quenchants need at least 3 between working traits and the mark.
- **No narrative effects.** Every effect is executable (herbalism's
  `test_herb_effects_are_documents.py`).
- **Small numbers, base 2.** House modifiers start at ±2 (the owner's ruling). A ceiling per tier
  for any one house modifier: common ±2, uncommon ±2, rare ±3, exotic ±3, legendary ±4.
  **(proposed: the ceilings above 2)** Book effects are exempt, being the book.

### 5.8 How the pass is done

The same pipeline as the herb tagging:
1. Export the 112 entries with their text to a tagging file.
2. Fill the book entries **by hand from the sweep's tables** (no model authors a book number).
3. Draft the house modifiers with model help **inside the validator's fences** (types, targets,
   tier ceilings, at least one negative), so nothing invalid can land.
4. Validate mechanically, then **the owner reviews the house modifiers** as a table, since
   balance is a judgment call, as the herb hybrid rows were.
5. Rewrite each material's `text` to say what it does in the app (the owner's herb rule: the
   description follows the mechanics).

Unify the shared metals at the same time (§2, "one material, many shelves"): the alchemist,
enchanter and leatherworker copies (cinnabar, quicksilver, mithral dust, adamantine dust,
silver ink, cold-iron studs, mithral fittings and the rest, listed in the inventory) become
`forms` of one material document each.

---

## 6. Pieces and the item maths

### 6.1 Pieces

| Gear | Main piece | Second | Third |
|---|---|---|---|
| Weapon | **head** (blade, axe head, hammer head, spearhead) | **haft** (haft, grip, shaft) | **fittings** (guard, pommel, rivets, collar) |
| Armour | **body** (plates, links, scales) | **fastenings** (buckles, rivets, straps) | **lining** (padding, leather) |
| Shield | **body** (boards or plate) | **fastenings** (boss, rim) | **lining** (straps, grip) |

A weapon with no metal fittings (a club, a quarterstaff) has the head and haft as the same
piece of wood. A piece may be "none" where the base item has no such part.

### 6.2 The sum

For each modifier target (attack, damage, AC, ACP, hardness...):

```
raw      = Σ over pieces of: value × weight(piece) × strengthen(piece)
              weight: main 1.0, others 0.5
              strengthen: 1.5 ^ passes on that piece's bar
bonuses  = raw_bonus × quality(item) × (1 + potency perks)
negatives = raw_negative × negative_cut(level, hardening)        (quality never worsens a negative)
final    = round each target's total down to a whole number
```

**"Rounded down"** is read as **toward zero**, so −1.5 becomes −1, not −2. That is the reading
that keeps the owner's "small numbers" intent for negatives. (Accepted 2026-10-03.)

Quality multipliers on bonuses **(proposed)**: Crude ×0.75, Sound ×1, Fine ×1.25, Superior ×1.5,
Flawless ×1.75, each +N another ×0.25.

### 6.3 What is not in the sum

- **Book effects** come from the main piece only, unweighted, unscaled: DR bypass, adamantine's
  DR 3/—, mithral's −3 ACP. The book's number is the number.
- **Masterwork** (+1 attack, −1 ACP) is its own effect from the quality tier.
- **The quench mark** is applied once, unscaled.
- **Finish treatments** add their own effect, unscaled, and obey the book's restrictions
  (alchemical silver cannot go on adamantine, cold iron or mithral).

### 6.4 Worked example

A Fine longsword. Head: iron, Strengthened once. Haft: ash. Fittings: brass. Smith level 2.

At the owner's base of ±2:

| Target | Iron head (×1, ×1.5) | Ash haft (×0.5) | Brass fittings (×0.5) | Bonus / negative | After quality (×1.25) and cut (×0.9) | Final |
|---|---|---|---|---|---|---|
| damage | +2 × 1.5 = +3 | 0 | 0 | +3 / 0 | +3.75 | **+3** |
| attack | −2 × 1.5 = −3 | +2 × 0.5 = +1 | 0 | +1 / −3 | +1.25 − 2.7 = −1.45 | **−1** |
| hardness | +2 × 1.5 = +3 | 0 | +2 × 0.5 = +1 | +4 / 0 | +5 | **+5** |

Bonuses and negatives are summed separately per target, scaled (quality on bonuses, the cut on
negatives), then added and rounded toward zero once. Shown on the item card exactly like this
(UI plan §6.6), so the rounding is never a mystery.

**Why the base is 2:** at ±1, a half-weight haft or fitting gave ±0.5 and usually rounded to
nothing, which made those pieces pointless. At ±2 every piece moves a number. (Ruled
2026-10-03.)

---

## 7. Methods

| Method | In | Out | Level | Where | Notes |
|---|---|---|---|---|---|
| **Smelt** | ore + fuel (+ flux) | ingot | 1 | smithy | Flux cancels `slaggy`. Exotic+ metal needs a rare+ fuel (today's rule, kept). |
| **Alloy** | 2+ ingots in a ratio window | named alloy bar (steel, bronze, brass...) | 2 | smithy | A recipe table names every alloy and its window (Vintage Story's model). An unlisted pair still gives the "novel alloy" rank step, but under a real name. |
| **Forge** | bar + fuel | blank (blade, head) or plate | 1 | kit | The shape is **picked from the engine's list** of weapon and armour families, never typed. Draw merges in here. |
| **Quench** | blank + quenchant | hardened blank | 1 | kit | Applies the quench mark. Brine, water, oil: hard to soft, risky to safe. |
| **Temper** | hardened blank | tempered blank | 2 | kit | Removes the brittleness a quench leaves. Without it, a quenched item keeps `brittle` (−1 hardness, a natural 1 against it risks breaking). (Accepted 2026-10-03.) |
| **Fold** | bar or blank | folded bar | 2 | smithy | Cancels `slaggy`; on clean metal, only +1 hardness. Makes pattern steel from two steels. |
| **Hone** | blank | honed blank | 2 | kit | The edge. Polish merges in here. Required for Superior and up on edged weapons. |
| **Assemble** | head + haft + fittings (or body + fastenings + lining) | the finished item | 1 | kit | Where pieces join and the item's numbers are computed (§6.2). |
| **Finish** | item + treatment | finished item | 2 (3 for sacred) | kit | Bluing, oil-blackening, etching, plating, gilding, blanching, anointing. Today treatments have no method. |
| **Strengthen** | 2 bars of one material | 1 strengthened bar | 2 | smithy | Every modifier ×1.5. Forge-welding heat, so a smithy. Repeatable. |
| **Assay** | a sliver | knowledge | 1 | kit | §9.2. No quality, no minigame. Mirrors tasting, which also has none. |

**Masterwork chain:** a Superior result at Assemble needs a Tempered and (for edged weapons)
Honed head. That keeps the book's masterwork as earned work.

**DC:** the book's Craft DCs (simple weapons 12, martial 15, exotic 18, armour 10 + AC bonus) at
Forge and Assemble; intermediate steps use the material's DC as today. No per-stage +2 creep:
each step is its own roll now, so stacking DCs across a chain no longer means anything.

---

## 8. Products

- **Ingots and bars**: stackable, sellable, weigh what the book says (a bar is 1 lb **(proposed)**).
- **Blanks and plates**: one piece each, sellable to other smiths, carry their material and any
  quench mark.
- **Hafts, grips, guards**: bought or carved (woodworking stays outside this plan; bought for
  now).
- **Finished weapons, armour and shields**: one item each. **No bulk at Assemble** for weapons
  and armour (accepted 2026-10-03): Smelt, Alloy, Forge and Strengthen keep bulk for bars and
  ingots, but a stack of ten identical longswords from one minigame is the Bannerlord exploit
  shape.

Every product records its build (`pieces`, materials, passes, quality, mark, finish) so the
item card can show the sum, and so an old item can be re-derived if a material document changes
(the read-live rule: the record stores ids and passes, the numbers are computed on read).

---

## 9. Discovery

### 9.1 Knowledge

The herbalism knowledge store and functions are generalised rather than copied:
`rules/herbknowledge.py` is hard-wired to `ingredients.get`. It becomes `rules/knowledge.py`
over any material document, with `Actor.herb_known` read as the herb shelf of one
`Actor.known` store **(proposed; migration keeps herb_known loading)**. A property is one
positional key per effect and working trait, as today.

### 9.2 Assay

- Costs a sliver: a tenth of a bar (bars track tenths) or one ore. 10 minutes. The player's own
  Craft roll, DC by rarity, as study is.
- Reveals one positive and one negative property (the owner's ruling, mirroring tasting).
- **Comparison makes it easier**: −1 DC for each known material of the same kind, max −4
  (touchstone against known needles). **(proposed)**
- **Reactive metals are dangerous.** Assaying noqual or abysium applies the material's own
  carrier effect for real (abysium: sickened 1d4 hours), as tasting a poison does.
- Working a material (any successful step) reveals its working traits, since you watched it
  behave.

### 9.3 People and books

Smiths in settlements teach (the herbalism `teaches` route); a library and smithing manuals
work as herbalism manuals. A new goods table of smithing manuals, like the herbal manuals added
in 0.2.4.

### 9.4 The smith's ledger

The herbarium's counterpart: every material you have met, known and unknown counts, shown on
hover at the bench and as a Journal section. UI plan §6.7.

---

## 10. Where you smith

**The field kit** (camp anvil, bellows, field hearth, bucket, whetstone): Forge, Quench, Temper,
Hone, Assemble, Finish, Assay, common and uncommon materials, anywhere you stand.

**A smithy** adds Smelt, Alloy, Fold, Strengthen, and rare-and-above materials:
- **A town smithy**: a place whose keeper is a smith. You pay by the hour (the market's rate
  table, proposed 1 sp per hour). The keeper may also teach (§9.3).
- **Your own smithy**: founded through the places system's `found` door. The owner holds
  `holds.place.<slug>` as an `ActiveEffect`, as for any founded place. This retires the
  2026-08-25 ruling "leave fixed tools alone until property ownership exists": property
  ownership exists now.

Which you are at is read from the scene's place (`places.for_scene`) and its tags, never from
the player's words.

---

## 11. The bench, rules side

Same as herbalism §9, with smithing's games:

- The d20 Craft roll decides success; the minigame climbs the tier under your ceiling.
- Always played; Smelt, Alloy, Forge and Strengthen batch (one game, one tier for the stack,
  time grows with the batch).
- Fail by 4 or less: time lost, materials kept. Fail by 5+: half the materials ruined (rounded
  down, at least 1 when there were 2+), unless the material is `malleable`.
- **Heat inside each game** (the owner's ruling): the metal's colour cools; striking in band
  scores; a reheat costs a few seconds of game time and 5 minutes of world time **(proposed)**;
  nothing carries between steps. Heat is shown as **colour, a labelled bar and a number**
  (KCD2's patch; accessibility).

The nine games are specified in the UI plan §9. The server receives a score in 0..1 and
answers with the tier; the page never computes a number.

---

## 12. The engine half

What makes a forged item matter. Each item here was confirmed in code by the inventory.

### 12.1 A forged item can be wielded and worn

- `Actor.weapon(key)` resolves a **crafted weapon record** (in `stock` or `worn`) to its base
  weapon's statistics plus the computed build. Today it knows the Core table, the 456-row
  weapons file, granted weapons and natural attacks, and not the thing you just made.
- The engine's `wear` op accepts a crafted record. Today it sets `equipped` and `armour` from
  table keys only.
- Armour: `Actor.armour` resolves a crafted armour record the same way, so AC, max Dex, ACP,
  spell failure, speed and weight come from the build.

### 12.2 Item-scoped modifiers (and the open door it closes)

`Actor._standing_mods(kind, target)` reads every worn record's specs **with no weapon scope**.
Measured by the inventory: a masterwork +1 attack record in the hands slot applies to **every**
attack, and a grip's CMD +2, oil-blackening's Stealth +1 and horacalcum's initiative would apply
without their conditions. The stage 8 verifiers logged this door; it is still open.

The fix: `_standing_mods` takes the roll context (the same `ctx` `_feat_mods` already takes), and
a weapon record's attack and damage specs apply **only when `ctx.weapon` is that record**. Armour
specs apply while the record is in the armour slot. The `scope` / `when` grammar the feats use
(`_scope_holds`, `_when_holds`) is reused, not duplicated. A ratchet test pins it: a +1 masterwork
dagger in the off hand does not touch the longsword's roll.

### 12.3 Damage knows the material

- A weapon's `strikes_as` effects become the `traits` passed to `_apply_damage`. Today weapon
  hits pass none (`engine.py` ~5270), so `Reduction.bypassed_by` (sheet.py ~203, "nothing in the
  app produces silvered weapons yet") never fires.
- Adamantine ignores hardness below 20 on sunder and object attacks (`object_damage`).
- `damage_reduction()` and `resistance()` read the worn armour's build (adamantine DR 1/2/3,
  fire-forged resistance 2), which they do not today.

### 12.4 On-hit riders

Viridium's leprosy (Fort DC 12) and greenblood on a crit, wyvern blood's first-wound venom, and
fire-forged steel's "+1d4 fire for 2 rounds after 10 fire damage": hit-triggered effects through
the existing `save_gate` and `damage` executors, with a `trigger` (hit, crit, first wound per
day). One applicator: each lands as an `ActiveEffect` with `origin: item:<id>`.

### 12.5 Carrier effects

Abysium sickens whoever carries it, and for 1d4 hours after. That is an `ActiveEffect` granted
by **carrying** (source `item:<id>`), removed when the item leaves the pack, which then applies a
1d4-hour lingering effect. Viridium's daily leprosy save unless kept in a lead-lined scabbard is
the same mechanism with a daily save.

### 12.6 The periodic executor

Troll blood's fast healing needs `ActiveEffect.periodic` to have a consumer beyond `spend_pool`.
The ledger lists this as "promised, not built". It is built here (heal and damage per round or
per day), with tests, because the quench marks depend on it.

### 12.7 Prospecting reaches the forge

`_op_prospect` writes `Stock(craft="smithing")` while the bench filters on `"blacksmith"`, so
prospected ore probably never reaches the forge (inferred by the inventory, **not yet run**).
Verify by running it, then fix it, and let prospecting yield every mined material, not only
`kind == "ore"` at rare and below.

### 12.8 Tells

Law 3: every effect application emits a tell. New tells: "the cold iron bites past its
resistance", "the adamantine edge shears the lock", "the abysium in your pack turns your
stomach". The narrator is fed these and nothing else about the materials.

---

## 13. How it obeys the three laws

1. **One vocabulary.** Material powers are tags (`strikes_as.cold_iron`), asked by prefix.
   Working traits are tags the bench asks (`working.slaggy`). No string matching on names.
2. **One applicator.** Every number travels as an effect: item modifiers through the
   `_standing_mods` funnel with the item scope, riders and carrier effects as `ActiveEffect`s with
   `origin: item:<id>`. Nothing is added outside the funnel. Remove the item and its contribution
   evaporates.
3. **Severed tells; no model authors a number.** Book numbers are entered by hand from the
   sweep's tables. House numbers are drafted inside validator fences and reviewed by the owner.
   Validators refuse a material with fewer than 3 weapon or armour modifiers, no negative, a
   narrative effect, or a house number over its tier ceiling, with the fix named.

---

## 14. Migrating old saves

The owner chose **convert**:
- **Levels above 3** become endless levels with perks picked on first load (herbalism's picker).
- **Old crafted items** ("Iron Work" records with flat specs) are re-derived: the main material
  is inferred from the record's name and specs, haft and fittings default to plain (ash and
  iron, value 0), old masterwork stays masterwork. The old record is kept beside the new build
  for one version, so a bad inference can be undone.
- **Stock of removed intermediate kinds** stays usable and sellable.
- **Old recipes** that name removed methods (draw, polish, flux, rivet) load with those steps
  mapped onto the new ones (draw → forge, polish → hone, flux → a Smelt ingredient, rivet →
  assemble).

---

## 15. World Bible and licensing

### 15.1 World Bible

Fixes are world-agnostic. A world's own metals need the same fields: `pieces`, `weapon`,
`armour`, `working`, `quench_mark`, `forms`. Add them to `docs/campaign-format.md` as optional
fields with defaults, and to `docs/from-world-bible.md` as what the next export should carry. A
world's local metal can stand in for iron or silver (Terraria's twin ores) with its own vector.

### 15.2 Licensing (the owner's call, not this plan's)

The eleven entries named from Adventure Path and Campaign Setting books (the five skymetal ores
and metals: abysium, djezet, horacalcum, inubrix, noqual, siccatite; and nexavaran steel) carry
the same exposure as the bestiary's AP names. The mechanics stay; the names wait on the owner's
licensing decision (`docs/bestiary-licensing.md`).

---

## 16. Build order (lanes)

| # | Lane | Contents | Writes |
|---|---|---|---|
| 1 | **Vocabulary** | `gear_mod`, `strikes_as`, `working`, `bonus_type: material`, triggers; validators and renderers | `rules/effectspec.py` |
| 2 | **Engine readers** | §12.1–12.5: wieldable crafted items, item-scoped `_standing_mods`, damage traits, armour from the build, on-hit riders, carrier effects | `rules/sheet.py`, `rules/engine.py` |
| 3 | **Periodic executor** | §12.6 | `rules/activeeffect.py`, `rules/sheet.py` (tick) |
| 4 | **Data pass** | §5: book fix by hand, house modifiers in fences, the owner's review table, text rewrites, shared metals unified | `content/materials/*.json` |
| 5 | **Bench rules** | §4, §6, §7: levels, perks, the item maths, the 11 methods, intermediates, masterwork, smithy and kit gating | `rules/blacksmith.py`, `content/world-classes/blacksmith.json`, `rules/worldclass.py` |
| 6 | **Knowledge** | §9: `rules/knowledge.py`, assay, teachers, manuals, the ledger | `rules/herbknowledge.py` → `rules/knowledge.py`, `rules/goods.py` |
| 7 | **Places** | §10: town smithy keepers and hourly rent, the owned smithy | `rules/places.py`, `rules/market.py` |
| 8 | **Migration** | §14 | `rules/sheet.py` load path, `rules/blacksmith.py` |
| 9+ | **UI and 3D** | the UI plan's lanes | `play/static/...`, `play/forge_views.py` |

**Why this order:** lanes 1–3 make a hand-written material document *do something in a fight*
before any of the 112 are rewritten. Then the data pass can be checked in play, not just by
validators ("verify end to end, on real regenerated content").

Lanes 1 and 3 can run in parallel. Lane 2 depends on 1. Lane 4 depends on 1. Lanes 5–8 depend on
4. The UI lanes can start their flat shell (UI plan lane U1) as soon as lane 5's API exists.

### 16.1 Tests each lane must add

Each names the defect it prevents in its docstring:
- **Lane 2:** a masterwork dagger worn in the off hand does not raise the longsword's attack
  (the measured open door); a cold iron sword's hit on a DR 5/cold iron fey deals full damage; a
  mithral shirt's armour check penalty and max Dex reach the sheet.
- **Lane 4:** every structural material has ≥3 weapon and ≥3 armour modifiers and ≥1 negative
  each; no narrative effects; every book material's book effects match the sweep's table (a
  set comparison); house numbers within tier ceilings; every material relevant; ≥3 discoverable
  properties each.
- **Lane 5:** the item maths on the worked example (§6.4) to the integer; rounding toward zero;
  book effects never scaled; no ingredients lost on a minigame miss after a successful roll.
- **Lane 6:** assaying reveals one benefit and one drawback; assaying abysium sickens.
- **Lane 8:** an old "Iron Work" save loads and keeps its masterwork.

---

## 17. The owner's answers to the open points (2026-10-03)

All five were accepted as proposed, with one change:
1. **Rounding:** negatives round **toward zero** (−1.5 → −1).
2. **Bulk at Assemble:** off for finished weapons and armour; bars and ingots still batch.
3. **Half-weight pieces:** solved by a different lever: **every house modifier starts at ±2**
   instead of ±1, so a half-weight piece gives ±1 (§5.7, §6.4).
4. **Skymetal names:** wait on the bestiary licensing decision (§15.2).
5. **Temper:** skipping it leaves a real flaw, `brittle` (§7).

Still proposed and open to tuning in playtest: the tier ceilings above ±2, the quality
multipliers, the negative-cut floor of 50%, the band percentages of the working traits, and the
quench marks' sizes.

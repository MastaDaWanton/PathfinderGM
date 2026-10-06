# Enchanting revamp: the plan

Drafted 2026-10-05 from three rounds of the owner's answers (`docs/enchanting-answers.md`). The
prior-art sweep it leans on is `docs/enchanting-prior-art.md` (with its critic pass). The
interface half is `docs/enchanting-ui-plan.md`; the lane contracts are
`docs/enchanting-contracts.md`. Nothing here is built yet.

Numbers marked **(proposed)** are my defaults and need tuning or a ruling; everything else is the
owner's decision as given, the printed rule (cited), or a fact measured in the code on master
e028885 (file and line given). Where the owner's answers pull against each other I say so and
pick a reading, and the reading goes into the open points (§22).

This plan follows `docs/herbalism-revamp-plan.md` and `docs/blacksmithing-revamp-plan.md`
wherever the cross-craft rulings bind it, and says so rather than repeating them.

---

## 1. What enchanting is for

The same three kinds of fun as the other crafts, in the same order: **hands-on craft** at the
circle, **discovery** of what essences do and what a found item really is, and a **way to be
seen** through the world's renown system (not something the class hands out).

What is enchanting's own is **the layer**. A sword is the smith's work: its pieces, metals,
quench and quality. The enchanter does not make a new sword; they put magic **on top of that
sword**, and the sword keeps everything it was. The same blade can be raised from +1 to +2 a
season later, because the book prices an upgrade as the difference ("the cost to add additional
abilities to an item is the same as if the item was not magical, less the value of the original
item", CRB p. 553, prior art §1.3). Unchained wrote *Scaling Items* because items were "sold and
forgotten" (prior art §1.7). Here the cherished blade grows.

**And it has to matter in play.** Measured on master e028885:
- Enchanting from `/craft/` cannot happen. The page sends `item` as the Shaping text string;
  `enchanter.preview` does `dict(item or {})` (`rules/enchanter.py:495`), so the string is a 400
  and the empty string is `{}`, and **every essence binding is refused "not masterwork"**
  (`enchanter.py:492-500`). Only wondrous items pass the book mode.
- The output is a **new** `Stock` record (`play/craft_views.py:677-686`) that drops the forged
  build: no `pieces`, no `strikes_as`, and no `weapon` field, so `Actor.weapon` never finds it.
- Only flat +N enhancement through `combat_mod` reaches a roll. `damage`, `resistance`,
  `damage_reduction`, `bleed`, `fast_healing`, `spell_effect`, `sense` and `immunity` have **no
  reader** on enchanted or catalogue items (`Actor._standing_mods`, `sheet.py:1038-1111`, reads
  only the int `amount` of six kinds).
- 14 of 81 essences and 47 of 170 catalogue items are **narrative-only** (keen, ghost touch,
  speed, vorpal, defending, fortification...).
- There is no magic-weapon property vocabulary and no "counts as magic" for damage reduction
  (`engine.py:5381-5382`: "the app has no magic-weapon channel to ask yet (stage 9)").
- The help text describes rules the code does not enforce: scribe, focus, channel and awaken
  have no code (`content/world-classes/enchanter.json` `method_help`).
- Bane's +2 and +2d6 sit in a `note` ("against the designated foe"), so any reader would apply
  them against every foe (`magic-items.json` `mi-bane`, `enchanter-materials.json` `bane-essence`).
- Noqual's `enchant_surcharge_gp` 5000 (`blacksmith-materials.json:2142`) has no reader.
- `magicitem.py` carries `price_gp`, `cost_gp` and `hours` and never charges them, and never
  moves the clock (`magicitem.py:320-324`, "a later economy can charge them").

The engine half (§8, §9) is not optional. Without it the data pass would ship 170 well-formed
recipes that change no roll.

---

## 2. The owner's decisions

### 2.1 Enchanting's own (2026-10-05, three rounds)

| Area | Decision |
|---|---|
| Who | **The Enchanter class, book-flavoured.** Its level stands in for caster level. A known spell, or a potion or scroll holding it (the book's "another magic item or spellcaster"), is a prerequisite; **each missing one is +5 DC, never a refusal**. |
| Layer | **A layer on top, capacity from quality.** The forged item keeps its pieces, materials and build; the +N and properties go on top within the book's +10. A Superior (masterwork) piece holds the book limit; Flawless and +N pieces hold a little more (Ultima Online's exceptional items). |
| Cost | **Essences are the cost**: found, harvested or bought, priced to follow the book, plus time scaled by power. |
| Failure | **Book curses, hidden.** Miss by 5+ and the item works but carries a hidden curse from the book's table, found by identifying well (beat the DC by 10) or the hard way. Materials are not lost. |
| Discovery | **Disenchant + identify + the herb routes** (study, teachers, libraries, manuals). Identify graded by the roll. |
| Minigames | **Order, matching and timed windows.** Lay components in order, match essence to vessel, bind at timed windows (planetary hours from the game clock). **No freehand drawing.** |
| Engine | **Every book property works.** A magic-weapon property vocabulary, readers for every effect type, "counts as magic" for DR, through the one applicator with tells. |
| Levels | **Same as the others.** L1 common/uncommon, L2 rare/exotic, L3 legendary, then endless perks: potency, quality, yield, and **capacity** (+1 to what an item holds, within +10). |
| Products | **Arms, armour, wondrous items, rings**, on vessels from the forge and the leatherworker. Wands, staves and scrolls wait (charges and spell use). |
| Modes | **One craft; essences feed both.** A catalogue item is a known recipe of essences and a vessel; free-form binding makes your own. Same bench, rules and curses. |
| Bench | **Its own bench from the shared parts** (`29-bench-core.js`), with a 3D stage: the item on a circle of chalk and inks, lit by candles and the essence's glow. |
| Old saves | **Convert.** Levels above 3 become endless levels with perks picked on first load; old enchanted items keep their +N and specs, re-derived onto the new layer where possible, the old record kept beside them for one version. |

### 2.2 Cross-craft rulings that bind this plan

- The d20 decides success; **one minigame per method** climbs quality (Crude → Sound → Fine →
  Superior → Flawless → Flawless +N), the ceiling set by level; **always played**.
- Levels 1-3, then **endless levels, two perk picks each** (the same perk twice allowed), perks
  stored as live-read documents on `Progress.perks` (stage 8's rule).
- **Real intermediates** land on the shelf.
- Materials carry **typed effect documents, never narrative**, and **at least 3 discoverable
  traits**. **Book effects win, house modifiers top up.** **One material, many shelves.**
- **No model authors a number.** **Fixes are world-agnostic**: every data gap also names the
  World Bible field.
- **An "In progress" section for every craft** (owner, 2026-10-05, leatherworking Q9.3): work
  that is not finished sits there with a countdown on game time until it is collected. This plan
  **builds it as shared infrastructure** (§15), because enchanting is the first craft built after
  the ruling, and it is designed for herbalism's steeping, tanning, alchemy and forge work too.
- **A metal tag on armour and weapons** (owner, leatherworking Q7.3: "there are spells that affect
  metal"). Enchanting needs it (the book's cold iron and noqual surcharges and the material
  affinities read it, §6.6), so **this plan builds the tag** (§16) and one reader; the spell
  readers and the druid rule are noted for the leatherworking plan.

---

## 3. What the research changes

From `docs/enchanting-prior-art.md`:

- **Keep the book's frame** (§5.1): DC 5 + caster level, +5 per missing prerequisite, +5 to
  hurry for half the time; prices bonus² × 2,000 (weapons) or × 1,000 (armour); +1 to +5
  enhancement, +10 total, at least +1 before a property; half price to make; 8 hours per 1,000 gp
  of base price; one item at a time; upgrades priced as the difference, +50% for an added power on
  a body-slot item. The current circle mode's DC (10 + 5 × rank) is a house scale that the
  revamp **retires**: one DC for both modes now (owner, "same bench, rules and curses").
- **Capacity tied to the vessel** is what every lasting system did (§0.4): PF1e's +10, PF2e's
  "property runes = potency", Pillars' 12-point budget, Ars Magica's opening cost by material,
  Ultima Online's exceptional bonus (armour 450 → 500). The UO bonus is **small**, and so is ours
  (§6.3).
- **Never destroy or worsen an item after a successful roll** (Diablo IV took eighteen months to
  undo exactly that; UO's failed imbue costs ingredients, never the item). Here even a failure by
  5+ keeps the item and the essences; it is the curse that costs.
- **Show the odds before the roll** (UO shows the imbuing chance; hidden odds drew the MapleStory
  fine). The curse line is printed before the roll (§11.1).
- **Refuse rolled perks and flaws** (Unchained's secret GM rolls). The curse is the book's one
  random table, rolled by the engine only after a failure by 5 or more, and recorded (§11).
- **Order is the craft; matching is the skill; windows come from the clock** (§5.5): Hávamál's
  carve-read-stain-test, Egil's carve-then-redden, Noita's slot order; Ars Magica's material
  affinity table; the Key of Solomon's planetary hour. **No freehand drawing** (Arx Fatalis).
- **Discovery shapes** (§5.3): unravel teaches the property *type*, "the magnitude is irrelevant"
  (Skyrim); a rune translates itself the first time you use it (ESO); identify is graded (PF1e);
  Egil's repair of mis-carved runes is "unmake, burn, re-carve", which is what Unbind does to a
  curse (§13).
- **Nothing that feeds itself** (§5.6, Skyrim's Fortify loop): an enchanted item never raises
  the Enchanter check (§4.5).
- **Licensing** (§1.8): the PF1e item text is Open Game Content; generic ability names are safe.
  Ars Magica is CC BY-SA 4.0: we borrow the *idea* of affinities, never its table text (§7.4).

---

## 4. Who enchants, and the check

### 4.1 Caster level

Anyone with the Enchanter world class enchants. **Enchanter level is the caster level** for every
rule that asks the creator's caster level (the owner's ruling; the book's Master Craftsman does
the same with Craft ranks, CRB p. 130). Endless levels count: an Enchanter 7 has caster level 7.

The **item's** caster level is the book's: the highest of each property's printed CL and
3 × the enhancement bonus ("the higher of the two caster level requirements must be met", CRB
magic weapons). It sets the DC (§4.2), the aura strength (§12.1) and the identify DC.

### 4.2 The DC

```
DC  = 5 + item caster level                                    (book)
    + 5 per prerequisite not met                                (book; the owner: never a refusal)
    + 5 if hurried (half the time)                              (book)
    − the circle's helps: catalyst, material affinity           (§7.3, §6.6; proposed sizes)
```

Prerequisites that cost +5 each:
- **Each prerequisite spell** the enchanter neither knows (`casting.knows`) nor holds in a
  carried potion or scroll (`Stock.holds_spell`, consumed in the making). The book allows the
  spell "through another magic item or spellcaster" (prior art §1.2).
- **The caster level requirement**: the enchanter's level below what the book asks of the
  creator (arms and armour: the higher of 3 × the enhancement and each property's CL; rings and
  wondrous items: the entry's printed construction line, e.g. Ring of Protection's "at least three
  times the bonus").
  **(proposed: counted as a prerequisite.)** The book calls it a "special prerequisite"; whether
  it can be skipped for +5 DC is argued both ways and no Paizo FAQ settles it (prior art §7). The
  owner's "never a refusal" decides it here, and it is open point Q4.
- **An alignment requirement** (holy: "creator must be good"): the app tracks no player
  alignment (`casting.py:746`, "with no alignment in play"), so this prerequisite is **waived and
  said so** in the notes, until the owner rules on alignment (Q7).

The **item creation feat** is the class itself; the book makes it the one mandatory prerequisite,
and here holding the Enchanter track is that.

**Rarity still locks** (the cross-craft levels ruling): an essence above your level's band is
refused with "Enchanter 2 for rare", not made harder.

### 4.3 The check

`d20 + Enchanter level + half character level + Intelligence`, itemised as today
(`enchanter.check_terms`, `enchanter.py:297-312`). Kept: it is the same three-term check every
Enchanter step rolls, and the inventory's reason for it ("a player who switches tabs does not
find their bonus quietly changing", `docs/enchanting.md`) now applies to one bench.

**Naturals.** `craft_views._one_craft` applies a natural 1 and 20 to this check today
(`craft_views.py:616-627`). 1e excludes skill and ability checks from the natural rule (CRB
p. 180; `dice.d20_succeeds` is the one reader and is never asked by a skill check). The revamp
drops it: the total against the DC decides, as at the herb and forge benches.

### 4.4 Showing the odds

Before every roll the working card prints: the DC with each term ("caster level 10; no Flame
Blade, +5; Mars hour, wider windows"), the bonus, "you need 12 or better", and two lines in words:
"Miss by 1 to 4: the binding does not take; you keep the essences" and "Miss by 5 or more: it
takes, flawed, with a hidden curse". The odds are never hidden (UO; the MapleStory fine).

### 4.5 No feedback loop

No item, potion or perk an enchanter makes adds to the Enchanter check (Skyrim's Fortify loop,
prior art §5.6). The check reads the three terms above and the circle's materials, nothing worn.
A ratchet test pins it (§21, lane E).

---

## 5. Progression

### 5.1 Levels 1-3

| Level | Opens | Essences | Ceiling | Tools |
|---|---|---|---|---|
| 1 | **Prepare, Attune, Bind, Read, Identify, Unbind**: the whole ritual in miniature | common, uncommon | Fine | chalk, salt, a pot of ink, a candle ring |
| 2 | **Refine** (draw an essence from its source; condense two into one), **more than one new property in one working** | rare, exotic | Superior | inscription set, jeweller's loupe, phials |
| 3 | **Cleanse** (lift a curse and keep the rest), legendary essences | legendary | Flawless | a silvered bell, a sanctum's quiet (§14) |

The heart of the craft stays at level 1, as `docs/enchanting.md` learned ("a deed that requires
the level it gates can never be earned"). Level 3 mirrors herbalism's Neutralize and the forge's
sacred finishes: the last level opens the dangerous and the sacred. **(proposed: what L2 and L3
open beyond rarity.)**

Mastery thresholds 25 and 65, as both other tracks. **Removed:** levels 4 and 5 as fixed rows,
the `legendary-binding` milestone and its deed, and the methods scribe, focus, channel, seal,
imbue, empower and awaken (their jobs are folded into §10's methods; old recipes map, §19).

### 5.2 Endless levels (4 and up)

Two picks per level, the same twice allowed, stored on `Progress.perks`, threshold
50 + 10 × (level − 3) as the other tracks.

| Perk | Per pick **(proposed sizes)** |
|---|---|
| Potency | +5% to the **house top-ups** of everything you bind (book numbers never scale, §7.2) |
| Quality | +1 to the quality ceiling |
| Yield | +5% chance per working that one essence is not consumed; the engine rolls it and shows the roll |
| Capacity | +1 to what an item you bind holds, never past the book's +10 (the owner's own example) |

### 5.3 Mastery sources

As herbalism §4.4 and the forge §4.5: each successful step (1, +1 per rarity band above common),
the quality bonus (+1 at Superior, +2 at Flawless or higher), firsts (+3: learn a property, bind
a property for the first time, identify an item, unbind an item), and +5 for reading an unread
enchanting manual. `REPEAT_LIMIT` and `MISHAP_LIMIT` keyed on (method, essence).

---

## 6. The magic layer

### 6.1 Where it lives

The layer is a field on the **vessel's own record**, never a new record. A forged weapon's
contract record (`docs/blacksmithing-contracts.md` §4, written by `blacksmith.record`,
`rules/blacksmith.py:1629`) gains one optional key:

```json
"magic": {
  "schema": 1,
  "enhancement": 1,
  "properties": [
    {"id": "flaming", "plus": 1, "essence": "flaming-essence", "choice": null},
    {"id": "bane", "plus": 1, "essence": "bane-essence", "choice": {"type": "undead"}}
  ],
  "flat": [ {"id": "shadow", "gp": 3750, "essence": "shadowstuff"} ],
  "binding": {"quality_index": 3, "level": 2, "perks": {"potency": 0}},
  "caster_level": 10,
  "motes_spent": 60,
  "curse": null,
  "known": {"intent": true, "curse": false, "how": "made"},
  "made_day": 41
}
```

- **Ids, never numbers** (the forge's read-live rule): the record stores which properties and
  essences, the choice and the binding quality; every number is computed on read by the layer
  builder (§6.7), so a corrected essence document corrects every item that carries it.
- `enhancement` and `properties[].plus` are the book's bonus equivalents; `flat` holds the
  abilities the book prices in gold (shadow, slick, glamered, energy resistance, etherealness,
  undead controlling, impervious), which **sit outside the +10** (prior art §1.3: "the cap counts
  bonus equivalents only", a reading).
- `curse` is the hidden curse record (§11), or null. `known` is what the owner of the item knows
  (§12): a maker knows the intent of their own work; a found item knows nothing.
- On the shelf the forge keeps an item as a `crafting.Stock` with its build in `forge.*` tags
  (`blacksmith.to_stock`, `record_of` at `forge_items.py:449`). The layer travels the same way:
  a new defaulted `Stock.magic: dict | None` field, written by `as_dict` only when set, so an old
  save round-trips byte for byte (the herbalism `Stock` rule, `crafting.py:115-121`). The existing
  `Stock.enhancement` and `Stock.properties` are **derived** from the layer for old readers, not
  stored twice.

### 6.2 What can carry a layer

| Vessel | From | Gate |
|---|---|---|
| Weapon, armour, shield | the forge (`forge_items.is_forged`); the leatherworker's armour records (leatherworking Q7.1 makes them the forge's armour record) | **Superior or better** (masterwork; the book: "only a masterwork weapon can become a magic weapon") |
| Bought or found masterwork arms and armour | the market, loot | a record is made for it on first touch: `forge_items.record_for_base(base, quality_index=3)` with the base's **default pieces** (§16.2), the same inference the forge migration uses for old "Iron Work" (`blacksmith.migrate_old_record`, `blacksmith.py:1100`) |
| Ring, amulet, circlet | the forge (new jewellery shapes, cross-craft ask in §20) | any quality; quality sets capacity (§6.3) |
| Cloak, boots, belt, gloves, bracers | the leatherworker | any quality; the book asks no masterwork for wondrous items (`magicitem.VESSEL_RULES`, kept) |

The bench picks a vessel **from the rack**, never from typed text: that is the fix for the
`/craft/` defect, by construction.

### 6.3 Capacity

The owner's three statements pull against each other, so here is the reading and why.

- "added on top **within the book's +10**" (round 1) and "capacity (+1 to what an item holds,
  **within +10**)" (round 2): the book's +10 is never passed, and a capacity perk must be able to
  matter, so the ordinary capacity has to sit **below** +10 for some vessels.
- "A Superior piece holds **the book limit**; Flawless and +N pieces hold **a little more**".

**Reading taken (proposed):** "the book limit" is the masterwork gate (Superior is what the book
lets you enchant at all), and capacity counts bonus equivalents:

| Vessel quality | Arms and armour hold | Wondrous items and rings hold |
|---|---|---|
| Crude, Sound, Fine | nothing (not masterwork) | 1 power |
| Superior (masterwork) | **+8 (proposed)** | 2 powers |
| Flawless | **+9 (proposed)** | 3 powers |
| Flawless +1 and above | **+10**, the book's cap | 3 + N powers |
| Each Capacity perk (the binder's) | +1, never past +10 | +1 power |

A +5 vorpal sword (+10) is legendary work either way, so it needs a Flawless +1 vessel or a
binder with Capacity perks: the smith and the enchanter both matter at the top. Ultima Online's
exceptional bonus is about +10% of the cap, and so is one quality step here.

**The other reading** (Q1): Superior holds the full +10, and "a little more" means room for
gold-priced abilities outside the +10 (one per step above Superior; Capacity perks add one each).
The data and engine are the same under both; only `capacity()` changes. The owner picks.

Flat-priced abilities (`flat`) never count against capacity under the taken reading **(proposed)**.

### 6.4 Pricing

Every price is the book's, computed, never authored (`magicitem.market_price`, `craft_cost`
kept):

- Arms: (total bonus)² × 2,000 gp; armour and shields: (total bonus)² × 1,000 gp; plus flat
  abilities at their printed gold.
- Wondrous items and rings: the catalogue price where the book prints one; free-form wondrous
  powers by the book's formula table (ability bonus² × 1,000; deflection² × 2,000; resistance² ×
  1,000; competence skill² × 100; continuous spell effect spell level × CL × 2,000; command word ×
  1,800; per-day uses divide by 5 ÷ uses), prior art §1.4. Several powers on one **slotted** item:
  each added power +50%; on a slotless item, 100% / 75% / 50% (book).
- **Upgrading**: "the same as if the item was not magical, less the value of the original item"
  (book). Adding flaming to a +1 sword: 8,000 − 2,000 = 6,000 gp market, half to make.
- The masterwork cost "does not influence the base price" (book): the vessel's own value is the
  smith's, never re-charged.

### 6.5 Essences are the cost: motes

The book's making cost is half the market price of the increment. The owner made **essences**
that cost. Two needs meet in one unit:

- an essence must say **what** it binds (fire → flaming), and
- the book's squared prices mean the **amount** needed depends on what is already on the item.

ESO solved the same pair with two runes, *essence* (the effect) and *potency* (the strength)
(prior art, ESO). So: every essence document carries **`motes`**, its potency, where
**1 mote = 100 gp of the book's making cost (proposed)**; and an essence that grants a property
carries `grants`. A working needs:

1. one granting essence for **each new property** (the identity), and
2. essences whose motes sum to at least **the making cost ÷ 100**, rounded up.

Plain **arcane essence** (I-V, the old enhancement ladder) grants the +N steps and is the
general mote supply; motes left over in a granting essence count too. A bought essence costs its
motes × 100 gp at an enchanter's shop, so the gold route is the book's price exactly; found and
harvested essences are the free route the owner wanted.

**Worked example.** A Superior cold iron longsword (forged, so its head is cold iron). Make it
+1 flaming:
- total bonus +2: market 2² × 2,000 = 8,000 gp; making cost 4,000 gp = **40 motes**;
- cold iron: "adding any magical enhancements to a cold iron weapon costs an additional 2,000
  gp", once (prior art §1.3) = **20 motes (proposed: the full 2,000, read as a making cost)**;
- needs: one Flaming Essence (grants flaming), one Arcane Essence I (grants +1), and 60 motes
  between everything in the circle;
- item CL max(10, 3 × 1) = 10, so **DC 15**, +5 without Flame Blade known or carried, +5 if the
  binder is below Enchanter 10 (§4.2): an Enchanter 2 rolls against **DC 25**;
- time: 8 hours per 1,000 gp of the 8,000 gp base price = 64 hours (§6.8).

### 6.6 The vessel's material

Read from the item's material tags (§16), never from its name:
- **Cold iron**: +20 motes on the first enhancement, once, named on the cost line.
- **Noqual**: "any magic item incorporating noqual costs +5,000 gp to create": +50 motes, the
  first reader of `enchant_surcharge_gp` (`blacksmith-materials.json:2142`).
- **Affinity** (Ars Magica's idea, not its table): an essence family names the materials that
  suit it ("fire suits red gold, ruby, copper"; "against the dead suits silver"). Each matching
  material in the vessel's pieces widens Attune's matching seats (§10) and takes **−1 DC, max −2
  (proposed)**. Silver against lycanthropes and iron against fey line up with the book's
  alchemical silver and cold iron. The affinity lists live in the essence documents (§7) and are
  owner-reviewed house data.

### 6.7 The layer builder

`rules/magic_layer.py` (new) turns `record["magic"]` into effect documents, and
`forge_items.build(record)` merges its output into the build it already returns, so every
existing reader (attack scope, armour row, riders, carried effects, DR traits) sees the layer
without a second door:

```
build(record) -> {... forge keys ...,
                  "magic": {"specs", "riders", "strikes_as", "powers", "capacity",
                            "total_bonus", "caster_level", "price_gp", "aura", "problems"}}
```

- `+N` on a weapon: `combat_mod` attack and damage, `bonus_type: enhancement`, origin
  `item:<id>`; it competes best-only with masterwork's +1 enhancement to attack (the book: the
  masterwork bonus does not stack with an enhancement bonus).
- `+N` on armour or a shield: an enhancement to the armour (or shield) bonus, folded into the
  suit's row as `armour_row` folds material AC.
- Properties: the documents in §8's table, each stamped `origin: item:<id>` and
  `source: property:<id>`.
- Quality: house top-ups × the quality multiplier (the forge's ladder, Crude 0.75 ... +0.25 per
  step) × (1 + potency perks); house drawbacks softened by the same steps, floored at 50%; book
  numbers untouched (§7.2).
- The curse (§11) is applied last, and only the engine sees it (the player sees the item as they
  believe it to be, §12.4).

### 6.8 Time

The book: **8 hours of work per 1,000 gp of base price, minimum 8 hours**; hurried, 4 hours per
1,000 gp at +5 DC. For an upgrade the base price is the increment's **(reading)**. The working's
hours become a **countdown in the In-progress section** (§15): calendar game time at the book's
8-hour working day, so 64 hours of work is **8 days** on the clock **(proposed)**.

The book's "adventuring nets 2 hours of 4" is replaced: the owner asked for countdowns that move
with game time, so the circle keeps working while you travel (Q5). The book's **one item at a
time** stays: one binding in progress per enchanter **(proposed; Q5)**.

---

## 7. Essences and the data pass

### 7.1 Today

117 entries in `content/materials/enchanter-materials.json`: essence 81, focus 7, ink 5, chalk 4,
salt 2, vessel 7, catalyst 6, treatment 5. Tiers: common 18, uncommon 16, rare 26, exotic 36,
legendary 21. 170 entries in `magic-items.json`: weapon property 26, armour property 32, wondrous
112. Measured narrative-only: 14 essences, 47 catalogue items. At least one book number is wrong
in the catalogue: Ring of Protection +4 carries caster level 20, where the book prints "CL 5th"
for every bonus and makes "a level at least three times the bonus" a separate construction
requirement (CRB rings, read for this plan). The catalogue folded the two together. The book fix
comes first, as the forge's §5.4 did.

### 7.2 The essence document

Read through `rules/materials.py`, the one door to every craft material (forge contracts §3).
Every field defaults, so an old file loads.

```json
{
  "id": "flaming-essence", "name": "Flaming Essence", "kind": "essence", "tier": "rare",
  "material": "flaming-essence", "form": "phial",
  "grants": {"property": "flaming"},
  "motes": 18,
  "family": "fire", "planet": "mars", "polarity": "weapon",
  "affinity": ["red-gold", "copper", "ruby"],
  "house": [
    {"type": "resistance", "damage_type": "fire", "amount": 2, "house": true},
    {"type": "skill_mod", "target": "stealth", "amount": -1, "house": true}
  ],
  "working": [{"type": "working", "trait": "eager"}],
  "color": "#e0703a",
  "obtain": "bought", "price_gp": 1800, "biomes": [], "from_creature": null,
  "text": "..."
}
```

| Field | Meaning |
|---|---|
| `grants` | The property (§8) or power it gives: the **book** effect. Applied exactly as printed, never scaled. |
| `motes` | Potency, the cost unit (§6.5). Priced so the book's making cost is met: `price_gp = motes × 100`. |
| `planet` | Its planetary hour (§17). |
| `polarity` | `weapon`, `armour`, `ward` (rings, cloaks) or `any`: the old `prefers`, now a matching-seat rule (§10) instead of a +5 DC. |
| `affinity` | Materials that suit it (§6.6). |
| `house` | **House top-ups**, scaled by binding quality (§6.7): small, typed, at least one per essence. Drawbacks where the lore already had one (shadowstuff dims, vicious bites, the old `drawbacks` field). |
| `working` | Bench traits (§7.3). |
| `color` | Content colour for the stage's glow (the UI plan's rule: colour that belongs to the thing lives in the scene). Moves the forge's `play/forge_views.py` colour table into documents, as the forge's own still-open point 6 asked. |

**Three discoverable traits, at least**: the granted property, the house top-ups, the planet,
the polarity, the affinity and the working traits are each a property key (`knowledge.property_keys`).
Every essence has ≥ 3; the validator refuses fewer, with the fix named.

**No narrative.** Every `grants` resolves to an executable property (§8); the validator refuses
`narrative`, as the forge's lane C does for metals.

House top-up size ceilings by tier (the forge's §5.7 shape): common ±1, uncommon ±1, rare ±2,
exotic ±2, legendary ±3 **(proposed)**. Smaller than the forge's base ±2 because a layer stacks
on the smith's own modifiers.

### 7.3 The other circle materials

| Kind | Job now | Notes |
|---|---|---|
| **Chalk, salt** | Prepare's circle (the order game's pieces). Consumed by Prepare. | Tier sets which essences the circle can hold: a white chalk circle holds common and uncommon (proposed). |
| **Ink** | The sigils Prepare cuts. Consumed by Prepare. | The old ink tiers kept; silver ink is a form of silver (one material, many shelves). |
| **Focus (gem)** | **The stone of a ring or amulet**, set at Prepare. A ring's focus tier caps the rarest power it takes. | Replaces the old capacity number, which the vessel's quality now carries (§6.3). Arms and armour need none. The diamond keeps its character: on a curse result (§11) a fragile focus cracks. |
| **Catalyst** | −DC at Bind (powdered pearl −2, adamantine dust −3, kept). Consumed. | |
| **Treatment** | Vessel prep at Prepare (etching acid, warding oil, moonlit varnish lifting `night_only`). | |
| **Vessel** entries (7) | **Retired as materials**: vessels are real records now (§6.2). | Their `requires` prose becomes the rack's reasons. |

Working traits (typed documents the bench reads, none reaching the item) **(proposed)**:
`night_only` (ghost residue: binds only between dusk and dawn, or in the Moon's hour, as today),
`eager` (Bind windows 10% wider), `skittish` (Attune seats drift), `heavy` (Refine draws fade
faster), `volatile` (Read is dangerous: reading it applies its house drawback for an hour, the
forge's reactive-assay shape), `pure` (roll Bind twice, keep the better: Unchained's raw-material
trait).

### 7.4 Catalogue items become recipes

The owner: "a catalogue item is a known recipe of essences and a vessel". Each of the 170 entries
becomes:

```json
{"id": "mi-ring-protection-1", "name": "Ring of Protection +1", "vessel": "ring",
 "book": [{"type": "combat_mod", "target": "ac", "amount": 1, "bonus_type": "deflection"}],
 "spells": ["shield-of-faith"], "caster_level": 5, "price_gp": 2000,
 "essences": [{"grants": "deflection", "count": 1}], "tier": "uncommon"}
```

A recipe is **known** through discovery (§12): identifying one, unbinding one, a teacher, a
manual. Free-form binding is the same bench without a recipe: pick properties within capacity,
priced by §6.4.

### 7.5 How the pass is done

The forge's pipeline (blacksmithing plan §5.8): export to a tagging file; fill every **book**
number by hand from the AoN tables (prior art §1.3, and the armour table read for this plan from
https://legacy.aonprd.com/coreRulebook/magicItems/armor.html); draft house top-ups with model help
**inside validator fences**; validate; **the owner reviews the house table**
(`docs/enchanting-review.md`, as `docs/blacksmithing-review.md`); rewrite each `text` to say what
the item does in the app. Shared materials (silver ink, adamantine dust, mithral filings, ruby)
become `forms` of one material document each.

---

## 8. The property vocabulary and every reader

Every book weapon and armour ability, and every wondrous effect type, gets an executable document
and a reader. The new effect types live in `rules/effectspec.py`; the book's ability table (price,
CL, spells, restrictions, and each ability's bundle of effect documents) lives in
`content/rules/magic-properties.json`, entered by hand from AoN and validated on load
(contracts §2.2); properties are tags (`property.flaming`) asked by prefix, never by string match
on a name (law 1).

### 8.1 New vocabulary

**As built, the vocabulary differs from this table in six places** (lane A, 2026-10-05; the
reasons are in `docs/enchanting-contracts.md` §2.1, which is the shape to build against):
`not_with` became a `stacking` group; bane is `enhancement_raise`, not a `combat_mod`
enhancement (which `dice.stack` swallows beside the sword's own +1); the alignment traits are
`lawful` and `chaotic` (the bestiary's words); `ignore_armour.except` became `cannot_harm`;
item powers count uses in the existing `uses`/`uses_count`; vicious's wielder is
`recipient: "self"`. Choices are filled by `effectspec.bind`, so `_when_holds` gains no choice
key.

| Addition | Shape | Why |
|---|---|---|
| `crit_range` | `{"multiply": 2, "not_with": "feat.improved-critical"}` | keen |
| `crit_rider` | `damage` with `trigger: crit` and `per_multiplier: true` | the bursts, thundering (×3 weapon: 2d10) |
| `extra_attack` | `{"on": "full_attack", "count": 1, "not_with": "spell.haste"}` | speed |
| `enhancement_to_ac` | `{"max": "enhancement"}`, a per-turn choice | defending |
| `fortification` | `{"percent": 25}` | negates a crit or sneak attack on d% |
| `ignore_armour` | `{"except": ["undead", "construct", "object"]}` | brilliant energy |
| `item_power` | `{"spell": <id> or "effect": {...}, "uses": {"per": "day", "n": 1}}` | activated abilities and wondrous spell effects |
| `deflect_ranged` | `{"per": "round", "save": {"reflex": 20}}` | arrow deflection, arrow catching |
| `STRIKES_AS` gains | `magic`, `good`, `evil`, `law`, `chaos` | counts as magic (§9) |
| Triggers gain | `wielded`, `worn` (a standing `ActiveEffect` while the item is held or worn, removed with it; the `carried` mechanism, `sheet.py:855-880`) | negative levels on the wrong wielder, fast healing, senses |
| `choice` on a property | `{"type": "undead"}`, `{"damage_type": "fire"}`, `{"subtype": "goblinoid"}` | bane's foe, energy resistance's type, chosen at Attune, stored on the record |

Every addition gets a validator, a renderer and a catalogue entry (`effectspec.validate`,
`render`, `catalogue`), so the homebrew editor can author them.

### 8.2 Weapon abilities (CRB, AoN; price and CL read for this plan)

| Ability | Book | Document | Reader (site) |
|---|---|---|---|
| Flaming / Frost / Shock | +1; CL 10 / 8 / 8 | `damage` 1d6 fire/cold/electricity, `trigger: hit` | `Engine._item_riders` (`engine.py:11170`), today forged-only: extended to the layer |
| Flaming / Icy / Shocking burst | +2; CL 12 / 10 / 10 | as above + `crit_rider` 1d10 per multiplier step | riders + new crit rider on a confirmed crit |
| Keen | +1; CL 10; piercing or slashing | `crit_range` ×2, not with Improved Critical | threat test, `engine.py:5213` (`natural >= weapon["crit_range"]`) through `weapon_row` |
| Bane | +1; CL 8 | `combat_mod` attack +2 enhancement and `damage` 2d6, both `when: {"target": <choice>}`; +2 counts for DR too (§9) | `_when_holds` (`sheet.py:4840`) gains the choice key; the note-only bug is closed by the `when` |
| Holy / Unholy / Axiomatic / Anarchic | +2; CL 7 | `damage` 2d6 `when target alignment`; `strikes_as` good/evil/law/chaos; wielder negative level `trigger: wielded` | creature alignment from the bestiary field (`bestiary.py:482`); the wielder clause waits on Q7 |
| Ghost touch | +1; CL 9 | `strikes_as: ghost_touch` | exists (`engine.py:5373-5393`) |
| Speed | +3; CL 7 | `extra_attack`, not with haste | the full-attack builder |
| Defending | +1; CL 8; melee | `enhancement_to_ac`, chosen on the attack (a param from the combat bar, never from a model) | `Actor.ac_modifiers` for the round |
| Merciful | +1; CL 5 | `damage` 1d6 nonlethal rider; lethality `either` | the lethality system (`weapons.lethality_of`) |
| Vicious | +1; CL 9; melee | `damage` 2d6 to target, 1d6 to wielder, `trigger: hit` | riders with `recipient: wielder` |
| Wounding | +2; CL 10 | `bleed` 1, stacking | an `ActiveEffect` with `periodic: [{"damage": 1}]` per round (`Actor.run_periodic`, built at the forge revamp) |
| Thundering | +1; CL 5 | `crit_rider` 1d8 sonic + `save_gate` Fort DC 14 deafened | crit rider, `save_gate` executor |
| Disruption | +2; CL 14; bludgeoning | `save_gate` Will DC 14 or destroyed, `when target.type undead` | `save_gate` with `Actor.die` (the one door, `sheet.py`) |
| Vorpal | +5; CL 18; slashing melee | on a natural 20 confirmed crit, `die` unless the target has no head or is immune to crits | crit path + `coup_de_grace.crit_immunity` (the reader to reuse) |
| Brilliant energy | +4; CL 16 | `ignore_armour` | the attack's AC: armour and shield bonuses dropped |
| Dancing | +4; CL 15; melee | `item_power`: the weapon fights 4 rounds as a scene actor at the wielder's attack bonus | a scene actor ("seen people are real" plumbing), the largest single reader; built last (§21, lane C2) |
| Spell storing | +1; CL 12 | `item_power` holding one targeted spell of 3rd level or lower, released on a hit | the cast door with `origin: item:<id>` |
| Distance, returning, seeking, throwing | +1 each | range ×2; returns before your next turn; no concealment miss; a thrown range increment | the ranged attack path, `Scene.out_of_hand` for returning |
| Ki focus, mighty cleaving | +1 each | class-ability passthrough; one more Cleave attack | `find_ability` for the feat action; Cleave has no branch today (states-effects-tells ledger), so mighty cleaving waits on it and says so |

### 8.3 Armour and shield abilities (CRB armour table, read for this plan)

| Ability | Book | Document | Reader |
|---|---|---|---|
| Fortification light / moderate / heavy | +1 / +3 / +5; CL 13 | `fortification` 25 / 50 / 75 | crit confirmation and sneak attack, d% rolled by the engine and shown |
| Spell resistance 13 / 15 / 17 / 19 | +2 / +3 / +4 / +5; CL 15 | `spell_resistance` N | the cast path's SR check (`engine.py:11840` reads a spell's SR line; no creature carries an SR number today, `engine.py:11677`): the caster level check d20 + CL vs SR, built here |
| Energy resistance, improved, greater | +18,000 / 42,000 / 66,000 gp | `resistance` 10 / 20 / 30, `choice` damage type | `Actor.resistance` (`sheet.py:2768`) reads the layer through the armour build |
| Invulnerability | +3; CL 18 | `damage_reduction` 5/magic | `Actor.damage_reduction` (`sheet.py:2800`) through the build |
| Shadow / slick (and improved, greater) | +3,750 / 15,000 / 33,750 gp | `skill_mod` competence +5 / +10 / +15 | `_standing_mods` (exists) |
| Ghost touch (armour) | +3; CL 15 | counts against incorporeal touch attacks; wearable by the incorporeal | the incorporeal attack path |
| Arrow catching, arrow deflection | +1 / +2 | `deflect_ranged` | ranged attacks at the bearer |
| Bashing | +1 | shield bash two sizes up, +1 attack and damage | the shield bash weapon row (the book: shield enhancement never reaches a bash, so bashing is the only route) |
| Blinding | +1 | `item_power` 2/day: 20 ft, Reflex DC 14 or blinded 1d4 rounds | `use_item` op (§8.5) |
| Animated | +2 | the shield guards for 4 rounds without a hand | hands accounting |
| Etherealness, reflecting, undead controlling | +49,000 gp / +5 / +49,000 gp | `item_power` (ethereal jaunt 1/day; spell turning 1/day; control undead 26 HD/day) | `use_item` op through the cast door |
| Wild | +3 | armour bonus kept in wild shape | the druid's wild shape (merged 1f88ada) reads it |
| Glamered | +2,700 gp | `item_power` at will: looks like clothing | a tell; no number |

### 8.4 Wondrous items and rings

Every effect type the catalogue uses gets a reader on **worn** items, catalogue or layered:

| Type | Reader built here |
|---|---|
| `combat_mod`, `skill_mod`, `save_mod`, `ability_mod`, `speed`, `concealment` | exists (`_standing_mods`) |
| `resistance`, `damage_reduction` | extended from the forged suit to every worn record and catalogue slot item |
| `immunity` | a worn immunity refuses conditions in that family at the applicator (`Actor.apply_effect`), with a tell |
| `sense` | `sense.*` tags in `standing_tags()` while worn (darkvision, see invisibility) |
| `fast_healing` | a `worn` standing `ActiveEffect` with `periodic: [{"heal": N}]` |
| `spell_effect` (continuous) | the spell's own document as a `worn` effect, `origin: item:<id>`, CL the item's |
| `spell_effect` (command, per day) | `item_power` through `use_item` |
| `negative_level`, `bleed` | through `ActiveEffect` (curse drawbacks, wounding) |

### 8.5 Item powers

One op, `use_item {item, power}`, validated by the engine, never written by a model with an
amount: the power's spell or effect document runs through the existing cast door with
`origin: item:<id>`, the item's caster level, and uses tracked on the record per day
(`run_periodic("day")` resets them, the day boundary the clock already crosses,
`engine.py:1104`). The combat bar and the sheet show each power with uses left.

### 8.6 Tells

Every application emits a tell (law 3): "The blade bursts into flame", "The bane edge knows the
dead", "Your armour turns the blow from a vital place" (fortification), "The spell breaks on
your armour's resistance". The narrator is fed tells and nothing else about the layer.

---

## 9. Counts as magic

From the CRB glossary, Damage Reduction (read for this plan,
https://legacy.aonprd.com/coreRulebook/glossary.html): "Weapons with an enhancement bonus of +3
or greater can ignore some types of damage reduction, regardless of their actual material or
alignment": cold iron or silver at +3, adamantine at +4, alignment at +5. "Any weapon with at
least a +1 magical enhancement bonus on attack and damage rolls overcomes" DR/magic (Bestiary,
universal monster rules). "Ammunition fired from a projectile weapon with an enhancement bonus of
+1 or higher is treated as a magic weapon for the purpose of overcoming damage reduction", and
takes its alignment (glossary).

The layer builder emits these as `strikes_as` traits, so the existing door
(`traits=struck_as + attacker_traits(actor)` into `_apply_damage`, `engine.py:5394`, and
`Reduction.bypassed_by`, `sheet.py:213`) does all the work:

| Enhancement | Adds |
|---|---|
| +1 or more | `magic` |
| +3 or more | `cold_iron`, `silver` |
| +4 or more | `adamantine` (for DR only: it does not ignore hardness) |
| +5 or more | `good`, `evil`, `lawful`, `chaotic` |
| holy / unholy / axiomatic / anarchic | its own alignment, at any + |
| bane against its foe | +2 to the enhancement for this test **(reading: Q8)** |

**Incorporeal.** The book's "immune to all nonmagical attack forms" is built where the comment
says it was missing (`engine.py:5381`): a blow without the `magic` trait does nothing to an
incorporeal defender (with a tell), a magic one deals half, ghost touch full (the existing half).

---

## 10. Methods

| Method | Level | In | Out | Minigame | Notes |
|---|---|---|---|---|---|
| **Prepare** | 1 | a vessel from the rack + chalk, salt, ink (+ a focus for a ring or amulet, + a treatment) | **a prepared vessel**: the item with its circle and sigils cut (sellable to other enchanters) | **Order**: lay the circle and cut the sigils in their sequence, with a test step before sealing (Hávamál) | Unchained's "prepare the vessel" step. Ceiling of the later Bind: Prepare's tier + 1 (proposed). |
| **Attune** | 1 | a prepared vessel + the essences | **an attuned vessel**: essences seated, not yet bound; holds for a day, then the essences drift back to the shelf unharmed (proposed) | **Matching**: each essence to the seat whose sign (planet, polarity, affinity) it answers | Choices are made here: bane's foe, resistance's energy. An unknown essence translates itself when seated (ESO). |
| **Bind** | 1 | an attuned vessel (+ catalyst) | the item, **into In progress** for the book's time (§6.8) | **Timed windows**: bind at the crests of the circle's pulse; the essence's planetary hour widens the windows | **The book's creation check** (§4.2). Curses come from here only (§11). Hurry is a toggle on Bind. |
| **Refine** | 2 | a raw source (ghost residue, a mote cluster, dragon ichor) or two essences of one family | a refined essence (more motes per phial, Cennini's first draw the deepest) | **Timed windows, diminishing draws**: draw at the crest; each draw is paler; stop when you choose | The craft's real intermediate besides the vessel. |
| **Unbind** | 1 | a magic item | knowledge, residue, and the vessel back without its layer (§13) | **Order, reversed**: unpick the sigils last-cut first | Disenchanting. A curse goes with the layer (Egil: shave, burn, re-carve). |
| **Cleanse** | 3 | a cursed item whose curse is known | the item without its curse, the rest kept | **Order** (the curse's sigils only) | DC 10 + item CL, the book's remove curse DC (CRB cursed items, read for this plan). |
| **Read** | 1 | a pinch (a tenth of a phial) | one trait of an essence | none (tasting and assay have none) | 10 minutes. `volatile` essences are dangerous to read. |
| **Identify** | 1 | an item | graded knowledge (§12) | none | Once per item per day (book). |

**DCs for the steps that are not the creation check (proposed):** Prepare and Attune use the
material DC by rarity that herbalism and the forge use for intermediate steps; Refine the
source's; Unbind 10 + the item's CL; Read and Identify as §12.

### 10.1 Failure, step by step

The cross-craft PF1e rule, adapted to the owner's enchanting rulings:

| Step | Miss by 1-4 | Miss by 5+ |
|---|---|---|
| Prepare | time lost, chalk and ink spent, vessel untouched | the same (a spoiled circle is chalk) |
| Attune | time lost, essences back on the shelf | the same **(proposed: essences are never lost before Bind)** |
| **Bind** | **the binding does not take**: time lost, essences kept, the vessel stays attuned **(proposed: the cross-craft rule; the book wastes materials)** | **it takes, flawed**: the item works and carries a hidden curse (§11); essences spent into it; **a fragile focus cracks** |
| Refine, Unbind | time lost, nothing spent | half the source ruined (Refine); the item's layer is lost with nothing learned (Unbind) |

A miss on the **minigame** after a successful roll lowers quality only, never takes materials
(herbalism §3).

### 10.2 Quality

The Bind minigame sets the binding's quality, under the ceiling (L1 Fine, L2 Superior, L3
Flawless, +1 per Quality perk), and under **Prepare's and Attune's tiers + 1 (proposed)**, so a
careless circle limits the work: real intermediates mattering. Quality scales the house top-ups
and softens house drawbacks (§6.7), and raises the item's resale value. It never touches a book
number.

---

## 11. Curses

### 11.1 When

Only a Bind that misses by 5 or more. The engine then rolls d% on the book's table (CRB, Cursed
Items, read for this plan: https://legacy.aonprd.com/coreRulebook/magicItems/cursedItems.html),
records the row and its detail in `magic.curse`, and **does not show it**. The verdict word is
honest: the player rolled their own d20 and saw the margin, so the bench says **FLAWED** ("It
took, but something went wrong in the binding") and never pretends to a clean success. What is
hidden is **which** curse (§12). This is the reading of "hidden" that keeps the dice honest
**(proposed; Q2 offers hiding the margin instead)**.

### 11.2 The table, made executable

Each row becomes typed documents. Rows the app cannot or should not run are marked; the owner
rules on them (Q3).

| d% | Book | Here **(proposed)** |
|---|---|---|
| 01-15 | Delusion: no magic but to deceive | The layer applies nothing. The item card shows what the maker intended; roll terms show the truth (no "+1 enhancement" term), which is how it is found the hard way. |
| 16-35 | Opposite effect or target | Every layer number signs-flips ("weapons that impose penalties on attack and damage rolls rather than bonuses", book); a rider strikes the wielder. |
| 36-45 | Intermittent: unreliable / dependent / uncontrolled | Unreliable: 5% per use the magic gutters (the engine rolls, the log says so). Dependent: works only in its planet's hour, or only at night, chosen by the engine's roll and recorded. Uncontrolled is folded into unreliable. |
| 46-60 | Requirement | An executable subset: eat twice as much (the survival counters, `fed_minutes` doubled); sleep twice as much; draw blood daily (weapons); use the item daily. Unmet, the layer is suppressed until met (`suppressed.magic` on the item). |
| 61-75 | Drawback (the book's own d% sub-table) | Executable rows kept: blurry vision −2 to sight checks, attacks and saves; one or two negative levels while wielded or worn; a daily Will or Fort save or 1 point of Int, Wis, Cha, Con, Str or Dex damage (`save_gate` on the day clock, `run_periodic("day")`); cannot cast arcane, divine or any spells. Cosmetic rows (hair, skin, a mark, a weeping sound, a ridiculous look, colder or warmer air) are **tells**, facts the narrator is given, never numbers. **Refused pending the owner**: changes of gender, race or alignment, polymorph, the incurable disease, a compulsion to attack. |
| 76-90 | Completely different effect | The engine picks another property of the same plus from the same family pool and records it. |
| 91-100 | A specific cursed item | The `−2 cursed` shape: opposite effect at −2, and the item **clings**: it cannot be put down until the curse is lifted ("can only be discarded after ... remove curse", book). |

Lifting a curse: the *remove curse* spell (caster level check DC 10 + item CL, book), Cleanse at
Enchanter 3 (§10), or Unbind, which unmakes the whole layer (§13).

---

## 12. Identify and discovery

### 12.1 Identify, graded

The book (Spellcraft, CRB, prior art §1.6): DC 15 + the item's caster level, 3 rounds, **once
per item per day** ("additional attempts reveal the same results"), elves +2. The roll is the
better of the Enchanter check and the character's Spellcraft **(proposed)**.

| Result | Learned |
|---|---|
| Fail | nothing; try again tomorrow |
| Succeed | **the intent**: every property, its +, its powers and uses; the item's recipe becomes known |
| Beat by 10 | **and the curse**, by name and effect |

Before identifying, detect magic's aura strength is shown from the CL (CRB detect magic, read for
this plan: faint 5th or lower, moderate 6th-11th, strong 12th-20th, overwhelming 21st+).

### 12.2 The hard way

The ESO and Final Fantasy IX routes: the first time a property fires in play ("the blade bursts
into flame"), it becomes known; the first time a curse's clause fires (a daily save, a gutter, a
roll term missing), the curse becomes known. Each is a tell and a line in the item's card.

### 12.3 What an enchanter learns

`rules/knowledge.py` (built at the forge revamp over any material) gains essences and recipes:
- **Read** a pinch: one trait (the herb rule: one benefit and one drawback where there is one).
- **Attune**: an unknown essence's polarity and planet show when it is seated.
- **Bind**: the granted property is known once bound.
- **Identify**: the recipe of a catalogue item.
- **Unbind**: the **types** of property the item carried, never their magnitude ("the magnitude
  is irrelevant", Skyrim), and the recipe if it was one.
- **Teachers** (an enchanter in a settlement, the herbalism `teaches` route), **libraries** and
  **manuals** (a goods table, `content/rules/enchanting-manuals.json`, as the herbal and smithing
  manuals).
- **Questions the world answers** (Earthdawn, prior art §5.3): a named item from World Bible can
  carry a knowledge chain ("who made it", "what it was made against"); the card shows the
  question, the world holds the answer. Data-ready here; authored items only (§20).

### 12.4 What the sheet shows

An unidentified found item reads "Longsword (magic, moderate aura)". The maker's own item reads as
intended, with "not identified" under it until a curse check has been passed or the curse has
shown itself. The sheet never shows a number the engine does not apply: under a delusion the
card's "+1" is marked "as the maker intended", and the roll's terms are the truth.

---

## 13. Disenchanting (Unbind)

- Unbinding strips the **layer**; the vessel survives as the smith's work, unenchanted
  **(proposed; Q6)**. Skyrim and Kanai's Cube destroy the item; this plan keeps the smith's half
  because the layer is the enchanter's and the pieces are not.
- It teaches the property types (§12.3) and returns **residue**: a quarter of the layer's motes
  as Arcane Residue **(proposed)**, Ultima Online's unravelling.
- A cursed layer goes with everything else. That is the cheap cure and its price is the layer.
- An item whose recipe is legendary needs Enchanter 3 to unbind (the rarity lock).

---

## 14. Where you enchant

The book: "a fairly quiet, comfortable, and well-lit place ... Any place suitable for preparing
spells is suitable." **(proposed)**
- **Anywhere quiet**: Prepare, Attune, Read, Identify, Bind, at camp or in a rented room. Not in
  a fight, not on the move.
- **A sanctum** (an owned place founded with the `sanctum` tag, `holds.place.<slug>`, the places
  system's `found` door) or **a town enchanter's circle** (a keeper whose occupation is enchanter,
  rented by the hour as the forge's smithy, `market.forge_rent`'s shape): Refine and Cleanse, and
  legendary work.
- The place is read from the scene (`places.for_scene`), never from the player's words.

---

## 15. The In-progress section (shared infrastructure)

### 15.1 What exists

Herbalism's steeping jar is the one precedent: `Stock.ready_minute` (`crafting.py:131-133`),
`how: ["steeping"]`, `settle_steeping` called only from the bench's own requests
(`bench_views._ready`, `bench_views.py:236`), and a "Steeping" group in the satchel with "ready in
3 days" (`31-bench-satchel.js:24-32`, 72-76). No countdown UI exists anywhere else; leatherworking's
cure and tan are chain methods with no timer (`leatherworker.py:842`).

### 15.2 Prior art

EVE Online's industry window lists jobs with time remaining, and when a timer reaches zero the
job's button becomes **Deliver**, which moves the product into the station's hangar
(https://wiki.eveuniversity.org/Manufacturing **[W]**): the owner's "sit ... before they can be
collected", exactly. Stardew Valley's machines show no time left in the base game, and players
added it: several of the most-installed mods do nothing but show time remaining on hover, and one
("Machine Status") lists every machine in every location as busy, ready or waiting
(https://www.nexusmods.com/stardewvalley/mods/11177 **[S]**). A list across all places, sorted by
ready, is what players built for themselves. PF1e's own timing is the book's ("8 hours of work per
1,000 gp"; "a character can work on only one item at a time"), prior art §1.2.

### 15.3 The model

**One store, no parallel list.** Work in progress is a `Stock` entry with `ready_minute` set,
as the jar already is. Every craft's waiting thing (a jar, a binding, a hide in the vat, a cooling
casting) is an entry in `actor.stock` with a `work` field:

```json
"work": {
  "craft": "enchanter",
  "label": "Binding a +1 flaming longsword",
  "started": 57600, "minutes": 11520,
  "where": "carried" | "place:<place id>",
  "state": "working" | "ready",
  "collect": true,
  "result": { ... craft-owned, hidden from the page ... }
}
```

- **Working**: the countdown runs on the world clock. The item cannot be used, worn or sold
  (`how: ["in_progress"]`, the steeping declaration generalised; the engine's use door already
  refuses a steeping jar, `engine.py:11271-11280`).
- **Ready**: the minute has passed. It **stays** in the section until collected (the owner's
  rule). Herbalism's jars move to this rule: `settle_steeping`'s silent lift becomes a ready state
  and a Collect **(the owner's ruling applied to steeping; old jars already past their minute
  load as ready)**.
- **Collect**: moves the result onto the shelf (for a binding, writes the layer onto the vessel's
  record and lifts `in_progress`). Work held at a place is collected there ("Collect at the
  tannery").
- **Where**: `carried` work travels with you (a jar, a wrapped binding); `place:<id>` work stays
  there (a tanning vat). The countdown runs either way.
- **Cancel**: each craft says what it means (a binding cancelled: the vessel returns unenchanted,
  the essences are spent, said before the confirm).
- **Limits**: a craft may cap concurrent work (the enchanter: one, the book's rule); jars are
  uncapped.

`rules/inprogress.py` (new) is the one door:

```python
inprogress.begin(actor, stock_key, *, craft, minutes, now, where="carried", label, result) -> dict
inprogress.entries(actor, now) -> list[dict]      # view rows for the page, sorted ready-first
inprogress.settle(actor, now) -> list[str]        # names newly ready (for tells)
inprogress.collect(actor, key, *, now, here) -> dict   # {ok, said, product} or a refusal in words
inprogress.cancel(actor, key, *, now) -> dict
inprogress.CRAFTS   # registry: craft id -> {collect(entry, actor), cancel(entry, actor), icon, limit}
```

A craft registers its `collect` and `cancel` functions; the section knows nothing about any one
craft.

### 15.4 The clock

`Scene.advance` (`engine.py:1104`) is "the one door" for time. It gains one call per actor,
`inprogress.settle(actor, clock)`, and adds "<name> is ready to collect" to its `ended` list, the
pattern `tick_pools` already uses ("is ready"). That is the tell (law 3) and the reason the
section never needs its own ticker: game time moves only through that door, so the countdowns move
exactly when it does. No real-time timer runs anywhere.

### 15.5 Who uses it

| Craft | Work | Where |
|---|---|---|
| Enchanter | a binding (§6.8) | carried (proposed; Q5) |
| Herbalist | steeping jars (tincture 2 weeks, acetum 1 week) | carried |
| Leatherworker | tanning, curing (the leatherworking plan sets times) | at the tannery or camp |
| Alchemist | long brews, when that plan lands | either |
| Blacksmith | none today; any future long step (annealing, a casting cooling) | the smithy |

---

## 16. The material tag (shared infrastructure)

### 16.1 Today

No armour or weapon row carries a material (`tables.ARMOUR`, `tables.py:538`; `weapons.json`).
Metal is decided by a name list, `armour.METAL_ARMOUR` and `METAL_SHIELDS` (`armour.py:201-204`),
read by `wears_metal` (`armour.py:207`), which therefore calls a forged mithral-on-darkwood shield
metal by its name and a forged noqual breastplate metal only because "breastplate" is on the list.
Forged items know their metals through `pieces[*].material`.

### 16.2 The tag

`rules/item_tags.py` (new): `material_tags(thing) -> tuple[str, ...]` and
`has_material(thing, prefix) -> bool`, in the one vocabulary (a `material.*` family registered in
`rules/states.py`, asked through `states.matches`, never by string):

- `material.metal`, `material.metal.<material id>` (iron, cold_iron, silver, mithral, noqual...);
  `material.leather.<id>`, `material.wood.<id>`, `material.cloth`, `material.stone`.
- **Forged records**: from each piece's material document (`kind` metal, alloy, fitting → metal),
  with `material.main.<id>` for the main piece (the book's "only the most prevalent material").
- **Table armour and weapons**: a default piece set per base (`content/rules/base-pieces.json`,
  new: chain shirt → steel body, steel fastenings, padded lining; club → oak; longbow → yew,
  horn, gut **(proposed data)**). The same table gives a bought masterwork item its record (§6.2),
  so one file serves both jobs.
- **Leather records**: from the leatherworker's hide and fittings (studded leather's studs are
  metal fittings; the druid rule then reads the tag, not a name).

### 16.3 Readers

Built here: the enchanting cost line (cold iron, noqual) and Attune's affinity (§6.6), and
`armour.wears_metal` rewritten on the tag (the name lists retired, the inubrix house clause keeps
working). **Noted for the leatherworking plan and the spells pass:** heat metal, chill metal,
rusting grasp, shocking grasp's +3 against metal armour, and the druid's no-metal rule (spells and
supernatural abilities lost until 24 hours after removing it).

---

## 17. Planetary hours

The Key of Solomon's rule: work a planet's power in its day and hour (prior art §4). Day and night
each split into twelve hours; the first hour after sunrise belongs to the day's planet, then the
Chaldean order: Saturn, Jupiter, Mars, Sun, Venus, Mercury, Moon.

The app has no sunrise: night is a fixed 18:00-06:00 window (`craft_views._is_night`,
`craft_views.py:88-96`) and the engine's dawn is 06:00 (`engine.py:15342`). So every planetary
hour is 60 minutes here, starting at 06:00, and the day's planet is the day number in the
Chaldean weekday order (day 1 the Sun's) **(proposed)**. If a world later has seasons, the hours
become unequal through the same function.

`rules/sky.py` (new): `planet_of_day(day)`, `hour_at(clock) -> {planet, starts, ends}`,
`next_hour(planet, clock) -> minutes`.

Each essence family names its planet in data (`planet`), a house mapping grounded in the Key of
Solomon's correspondences: fire and war Mars; frost and endings Saturn; storm and rule Jupiter;
holy and light the Sun; charm, slickness and glamer Venus; speed, keenness and returning Mercury;
the dead, ghosts and the ethereal the Moon **(proposed; owner review in the essence table)**.

**Inside the hour:** Bind's windows ×1.5 wider **(proposed)**: rarity and timing make the game
easier or harder, never the DC (the forge's Giants' Foundry finding). The bench shows "Hour of
Mars, 42 minutes left" or "Mars hour in 3 hours 10 minutes" with **Wait for it**, which advances
the clock through the one door.

---

## 18. How it obeys the three laws

1. **One vocabulary.** Properties are `property.*` tags, materials `material.*` tags, curses
   `curse.*` tags; readers ask by prefix. Bane's foe is a `when` clause, never a note.
2. **One applicator.** Layer numbers enter through the funnel the forge built (`_standing_mods`
   with the weapon scope, `armour_row`, `_item_riders`, `damage_reduction`, `resistance`); worn
   and wielded effects (negative levels, fast healing, senses) are `ActiveEffect`s with
   `origin: item:<id>`, granted with the item and removed with it. Item powers run through the
   cast door. Remove the item and its contribution evaporates. No second ticker: the In-progress
   section settles inside `Scene.advance`.
3. **Severed tells; no model authors a number.** Every price, mote count, DC, capacity and time
   is computed from the book's formulas or the documents. Book numbers are entered by hand from
   AoN; house numbers are drafted inside validator fences and reviewed by the owner. Validators
   refuse an essence with fewer than 3 traits, a `narrative` grant, a house number over its tier
   ceiling, or a property without a document, with the fix named.

---

## 19. Migrating old saves

The owner chose **convert**:
- **Progress.** Enchanter levels 4 and 5 become endless levels; their picks are banked and chosen
  on first load (herbalism's picker). The track gains the `endless` block and per-level
  `ceiling`, and `worldclass.migrate_enchanter` stamps the schema (the shape of
  `migrate_blacksmith`, `worldclass.py:495`).
- **Old enchanted items** (`craft: "enchanter"`, flat `specs`, `enhancement`, `properties` as
  names): re-derived onto the layer where possible. The vessel becomes a record (`weapon` or
  `armour` set: `record_for_base` with default pieces, Superior; otherwise a wondrous record by
  `slot`); `enhancement` becomes `magic.enhancement`; each property name is matched to the
  vocabulary by id. Specs that match nothing stay on the record as `legacy_specs`, read as today.
  **The old record is kept beside it for one version**, so a bad inference can be undone.
- **Old essences and foci** stay usable: their documents gain `motes` and `grants` in the data
  pass; ids do not change.
- **Old recipes** naming removed methods load mapped: attune and scribe → Prepare; focus and
  channel → Attune; bind and seal → Bind; imbue → (allowed at L2); empower and awaken → dropped
  with a note.
- **Steeping jars** become In-progress entries; past their minute, they load as ready.

---

## 20. World Bible

Fixes are world-agnostic. Added to `docs/campaign-format.md` as optional, defaulted fields, and to
`docs/from-world-bible.md` as what the next export should carry:
- **Essences** a world's own creatures and places yield: the essence document's fields (§7.2),
  with `grants` limited to the vocabulary (§8). A world's essence carries its own `planet` and
  `affinity`.
- **Materials**: every material the world names carries `kind` (metal, leather, wood...) so the
  material tag (§16) works on a world's own metals.
- **Sky** (optional): `sky.planets` (names in day order) and day length, defaulting to the seven
  classical planets and the fixed 06:00 dawn.
- **Named magic items**: properties by vocabulary id, an optional curse, and an optional
  knowledge chain (Earthdawn's questions, §12.3).
- **Creature harvest tags** (the leatherworking Q9.2 ruling) carry essence tags as well
  (`harvest.essence.fire`), so a slain fire creature yields fire essence by the same reader.

Cross-craft asks (for those plans, not built here): the forge's Forge method gains **ring band,
amulet and circlet** shapes; the leatherworker's products (cloak, boots, belt, gloves, bracers)
write records with `slot` and quality so they can be vessels.

---

## 21. Build order (lanes)

| # | Lane | Contents | Writes |
|---|---|---|---|
| A | **Vocabulary** | §8.1 additions, the book's ability table by hand from AoN, `STRIKES_AS` additions, triggers `wielded`/`worn`, `choice`; validators, renderers | `rules/effectspec.py`, `content/rules/magic-properties.json` |
| B | **Layer and tags** | `rules/magic_layer.py`, the merge into `forge_items.build`, capacity, pricing, motes, aura, `record_for_base`; `rules/item_tags.py`, `content/rules/base-pieces.json`, `armour.wears_metal` on the tag, the `material.*` family | `rules/magic_layer.py`, `rules/forge_items.py`, `rules/item_tags.py`, `rules/armour.py`, `rules/states.py`, `content/rules/base-pieces.json` |
| C | **Engine readers** | §8.2-8.5, §9: riders and crit riders on layered items, keen, speed, defending, fortification, SR, brilliant energy, counts as magic, incorporeal immunity, worn wondrous readers, `use_item`, bleed, the `inprogress.settle` call in `Scene.advance`; dancing and spell storing last (C2) | `rules/sheet.py`, `rules/engine.py`, `rules/activeeffect.py`, `rules/intents.py` |
| D | **Data pass** | §7: book fix, essence fields, catalogue → recipes, house top-ups in fences, `docs/enchanting-review.md` | `content/materials/enchanter-materials.json`, `content/materials/magic-items.json`, `rules/materials.py`, `tools/enchant_*.py` |
| E | **Bench rules and API** | §4, §5, §10: the check and DC, methods, failure, quality, levels and perks, the layer write, motes spent, hurry, places | `rules/enchanter.py`, `rules/magicitem.py`, `content/world-classes/enchanter.json`, `rules/worldclass.py`, `play/enchant_views.py` |
| F | **Curses, identify, unbind** | §11-13, manuals | `rules/curses.py`, `content/rules/curses.json`, `rules/knowledge.py`, `content/rules/enchanting-manuals.json` |
| G | **In progress and sky** | §15, §17; the `Stock.magic` and `Stock.work` fields | `rules/inprogress.py`, `rules/sky.py`, `rules/crafting.py`, `play/bench_views.py` (the steeping call), `play/works_views.py` |
| H | **Migration and World Bible** | §19, §20 | the load path, `docs/campaign-format.md`, `docs/from-world-bible.md` |
| U | **UI and 3D** | `docs/enchanting-ui-plan.md` | `play/static/...` |

**Why this order** is the forge's: A, B and C make a hand-written layer **do something in a
fight** before any of the 170 entries are rewritten, so the data pass is checked in play.
G has no dependency and starts at once. A and G in parallel; B after A; C after A and B; D after
A; E after B and D; F after B; H after E. The UI shell starts when E's API exists.

### 21.1 Tests each lane must add

Each names the defect it prevents in its docstring:
- **A:** every property id in §8.2-8.3 has a document that validates and is `executable`
  (today: 47 of 170 catalogue entries and 14 of 81 essences were narrative); bane without a
  `choice` is refused.
- **B:** a +1 layer on a forged longsword keeps its pieces and `strikes_as` (today the enchanter
  wrote a new record that dropped the build); capacity refuses +9 on a Superior vessel and allows
  it on Flawless; upgrading +1 → +1 flaming costs 6,000 gp market, 30 motes (book's difference);
  a cold iron vessel's first enhancement adds 20 motes, once; noqual adds 50
  (`enchant_surcharge_gp` was unread); `wears_metal` is false for a darkwood shield and true for a
  forged noqual breastplate.
- **C:** a bane (undead) sword adds +2d6 against a skeleton and nothing against a bandit (the
  note-only bane applied everywhere); a keen scimitar threatens on 15-20; a +1 sword passes DR
  5/magic and a +3 sword DR 5/silver; a nonmagical sword deals nothing to a ghost; a worn ring
  of protection +1 adds deflection AC and the cast path refuses a spell against SR 15 on a low
  roll; removing the item removes every contribution (a sweep over all property ids).
- **D:** every essence has ≥3 traits and no narrative; every catalogue book number matches the
  AoN table (a set comparison: Ring of Protection +4 at CL 5 with a creator level of 12, not
  CL 20); house numbers within ceilings.
- **E:** an enchantment started from the real bench API reaches the sheet (the path the player
  clicks: `/craft/` could never pass the masterwork gate); a missing spell is +5 DC, never a
  refusal; a miss by 1-4 keeps the essences; the check never reads a worn item (Skyrim's loop);
  no natural 1 or 20 on the check.
- **F:** a miss by 5+ records a curse that `entries` and the item card never reveal; identify by
  9 over shows the intent only, by 10 the curse; identify twice in one day returns the same
  result; Unbind teaches types and returns a quarter of the motes.
- **G:** a tincture is not collectable on day 13 and is on day 14 (herbalism's pinned case, moved
  to the section); a ready binding stays until collected; `Scene.advance` across the ready minute
  adds "is ready to collect" once; work at a place cannot be collected elsewhere; planetary hour
  of day 1 at 06:00 is the Sun's and at 07:00 Venus's.
- **H:** an old "Longsword +1" enchanter record loads as a layered record keeping its +1, the old
  record kept beside it.

---

## 22. Open points for the owner

1. **Capacity reading (§6.3).** Taken: Superior +8, Flawless +9, Flawless +1 and up +10, Capacity
   perk +1 each within +10. Alternative: Superior holds the full +10, and Flawless, +N and the
   perk add room for gold-priced abilities outside it.
2. **How hidden is a curse (§11.1).** Taken: the d20 and margin are shown, the verdict says
   FLAWED, and only *which* curse is hidden. Alternative: hide the margin on Bind so the player
   cannot tell a flawed binding from a clean one until identified.
3. **Curse rows (§11.2).** Keep or drop: changes of gender, race and alignment, polymorph, the
   incurable disease, the compulsion to attack. Proposed: dropped, the d% re-scaled over the rest.
4. **Caster level requirement (§4.2).** Taken: a level below the item's CL is one more +5 DC, not
   a refusal. Alternative: hard gate (no flaming below Enchanter 10).
5. **Countdowns (§6.8, §15).** Taken: the book's working days run on the calendar while you
   travel; one binding in progress at a time; the binding is carried. Alternatives: progress only
   while resting or at a sanctum (the book's "adventuring nets 2 hours of 4"); more than one at a
   time as a perk.
6. **Unbind keeps the vessel (§13).** Taken: the layer goes, the smith's item stays, a quarter of
   the motes come back. Alternative: the item is destroyed (Skyrim, Kanai's Cube).
7. **Alignment.** Holy and its kin need the wielder's alignment for the negative level, and the
   holy prerequisite needs the maker's. The app tracks none for the player. Waive both (taken),
   or rule how alignment enters play.
8. **Bane and DR (§9).** Does bane's +2 against its foe count toward the +3/+4/+5 DR thresholds?
   Taken: yes (a reading; no source found either way in this pass).
9. **Numbers to tune** (all proposed): 1 mote = 100 gp; cold iron's +2,000 as 20 motes; house
   top-up ceilings ±1/±1/±2/±2/±3; affinity −1 DC max −2; planetary hour windows ×1.5; Bind
   ceiling at Prepare/Attune + 1; residue one quarter; attuned vessels hold a day; perk sizes.
10. **Planet mapping (§17)** and the house top-ups: in the owner's review table with the data pass.

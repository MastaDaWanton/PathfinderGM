# Leatherworking revamp: inventory

What the Leatherworker world class is today, measured on `origin/master` at e028885 (0.2.8),
2026-10-04, before any design. Same purpose as the inventories behind the herbalism and forge
plans: real counts from running Python against the shipped files, with `file:line`
references, and the defects found while measuring. Where a claim was **run**, it says so;
where it was only read in code, it says that instead.

Probe scripts lived in the session scratchpad and are not committed. They ran against a
throwaway data directory and the `pc-kesst.json` fixture, the way `tests/test_benches.py`
does.

---

## 0. Headlines

1. **Leather armour made at the bench cannot be worn as armour.** Measured: a masterwork
   studded leather made from deer hide and steel studs is refused by the Equipment tab's
   engine path with *"The Deer Armour is not built on any suit the rules know ('Deer
   Armour')"*. `crafting.from_stock_dict` copies the item's *name* into `base`
   (`rules/crafting.py:386`), and the engine reads `base` before `armour`
   (`rules/engine.py:14964`). The older `/api/wear` path without an `op` puts the name in the
   armour slot and leaves the table key alone, so AC does not move (measured: 15 before,
   15 after). Either way, the AC 3 of studded leather and the masterwork −1 ACP never reach
   the sheet.
2. **Every armour-typed hide bonus is swallowed.** Hide AC is typed `armour` (pinned by
   `tests/test_aggregator.py:321`), so it never stacks with the suit's own armour bonus.
   Measured: a bulette-plate suit at +5 armour-typed AC came out as `leather` (AC 2), and
   the sheet's AC modifiers list only "leather armour +2". 13 hide specs do nothing on any
   suit.
3. **Skinning is not skinning.** Measured on the live excursion endpoint
   (`play/craft_views.py:1240`):
   - The carcass is never used up. Six skinnings of one wolf ran, three succeeded, and the
     wolf was still in the scene.
   - Three successes yielded brain paste, neatsfoot oil and sinew, and no wolf pelt. The pick
     is `pool[(face * (i + 3)) % len(pool)]` (`:1364`), a deterministic index over hides
     plus six generic carcass goods.
   - The DC is `10 + (ceiling − 1) × 3` (`:1351`), set by the *crafter's* level rather than
     the beast. A Leatherworker 5 skins a wolf at DC 22; a Leatherworker 1 at DC 10.
   - A good roll multiplies the haul (`batch = 1 + margin // 5`, `:1399`), so one wolf can
     give several pelts.
   - `pc.carry(mid, n)` is called without `at_minute` (`:1402`), so **the 48-hour spoilage
     clock never starts**. Measured: `picked_at` is `None` for everything skinned.
4. **The name match reaches the wrong creatures.** Measured over the 7,138-creature bestiary
   with `hides_from` (`rules/leatherworker.py:320`):
   - A red dragon offers **all 11 dragonhides**, every colour, because each also carries the
     fragment `dragon`.
   - 109 humanoids, 41 undead, 25 outsiders and 7 constructs yield a hide. "Battle Mage"
     yields bat-wing leather, "Bugbear Guard" yields bear hide, "Acolyte of Hecate" yields a
     cat pelt, "Belkzen Warchief" yields elk hide, and a "Bear Skeleton" yields a bear hide.
   - Only 93 of 262 animals, 55 of 265 magical beasts and 20 of 118 dragons yield any hide.
     Lion, elephant, mammoth, shark, tyrannosaurus, giant spider and troll yield none.
   - Every carcass, a human's included, yields the six generic goods: sinew, gut cord,
     horsehair cord, neatsfoot oil, tallow and brain paste.
5. **Nothing intermediate survives a session.** The bench's stock is the satchel's bare counts
   (`play/craft_views.py:241-260`), and no record carries `tanned` or `cured`. Measured: a
   wolf pelt cannot be cut and stitched in a later session (*"You cannot stitch an uncured
   hide"*), so every piece is flense to finish in one chain. Tanning is instant.
6. **The data is mostly prose.** 96 of 171 effect specs (56%) are `narrative`. 52 of 127
   materials carry only narrative, 14 carry nothing, and no material has three traits of any
   kind. Tannin, wax and thread prose leaks onto the finished item: measured, a boar-hide
   suit lists "The standard tanning agent for common and uncommon hides" as an effect.
7. **Methods that do nothing.**
   - **Cure** needs no salt (measured: `flense → cure → cut → stitch` with no curing salt has
     no problems).
   - **Line** changes nothing (measured: two hides give the same specs with or without it).
   - **Tool** is the only road to masterwork, so a dragonhide suit is not masterwork without
     it (measured: `masterwork: False`). The book says dragonhide armour is masterwork by its
     nature.
   - The tools listed per level (skinning knife, fleshing beam, half-moon knife and the rest)
     are read by nothing.
8. **The forge already reaches into leather.** `rules/blacksmith.py:966` says "Leather, hide
   and padded are the tanner's". `FORGED_ARMOUR` (`:967`) is the eight metal suits only.
   - The forge catalogue holds its own leather pieces: `leather-grip` (haft or lining),
     `sharkskin-grip`, `dragonhide-grip` (linked to `red-dragonhide`) and `angelskin-binding`
     (lining).
   - Only three materials can fill an armour **lining** at all: lead, leather-grip and
     angelskin-binding.
   - A hide cannot fill the armour **body**, so the forge's piece model cannot build hide or
     leather armour today.

---

## 1. The track: `content/world-classes/leatherworker.json`

170 lines. Thresholds `[25, 65, 50, 100]` (`:7-12`), the herbalist's curve kept on purpose
(`_thresholds_note`, `:6`). Five levels (`:23-90`):

| Level | Max tier | Tools (declared, read by nothing) | Methods |
|---|---|---|---|
| 1 | common | skinning knife, fleshing beam | skin, flense, cure, cut, stitch |
| 2 | uncommon | tanning rack, bark vats | tan, oil |
| 3 | rare | dye vats, half-moon knife, stitching pony | dye, line |
| 4 | exotic | wax kettle, hardening trough | harden |
| 5 | legendary | master tannery | tool |

- **Milestone** at 5: the `legendary-hide` deed, "any successful piece worked from legendary
  hide" (`:13-22`). This is the shape herbalism and the forge both removed.
- **`method_descriptions`** (`:91-103`) and **`method_help`** (`:105-161`) give each of the 11
  methods prose plus does/needs/for. Several `needs` lines are not enforced: cure's curing
  salt, cut's half-moon knife, and the tannery tools.
- **`fixed_tools`** (`:163-169`) is "declared and deliberately unread", parked by the
  2026-08-25 ruling until property ownership existed. The forge plan retired that ruling for
  smithies (`docs/blacksmithing-revamp-plan.md` §10).

### What each method does in code (`rules/leatherworker.py`)

| Method | Potency | Enforced need | Notes |
|---|---|---|---|
| skin | — | refused at the bench (`:676`) | Field action. Its excursion is §4. |
| flense | — | must precede cure or tan on a raw hide (`:868`) | |
| cure | — | **none** | `curing-salt` is not required. Measured. |
| cut | — | assembles `straps` | |
| stitch | — | thread on the bench (`:908`), hide cured or tanned (`:847`) | assembles 10 of 11 products |
| tan | — | a tannin within one tier of the hide (`:893-907`) | The one rule that makes the tannin ladder matter. |
| oil | ×1.10 | an oil | |
| dye | — | a dye | Mordant salts are not required. |
| line | — | two hides | **No effect.** Every hide's specs are gathered whether or not you line (`_gathered_specs`, `:955`). Measured. |
| harden | ×1.25 | a wax, and tanned (`:858`) | Cuir bouilli. |
| tool | ×1.25 | must be last (`FINISHING`, `:68`) | Sets `masterwork` (`:777`). |

**DC** (`_dc`, `:943-952`): the highest authored `craft_dc` on the bench, else `5 + 5 × tier
rank`, **plus 2 per stage after the first**. The +2 creep is the rule the forge plan removed
("each step is its own roll now"). Measured: a red-dragonhide suit without tool is DC 38; a
bulette suit with harden and tool is DC 30.

**Potency rounding** (`:136-150`): benefits round **up**, costs toward zero. Measured: steel
studs' +1 AC becomes **+2** under tool's ×1.25 (ceil 1.25). Any multiplier above 1 doubles
every +1. The forge rounds everything toward zero.

**Check** (`check_terms`, `:502-521`): d20 + track level + half character level + **Int**.
Clamped 5–95 for the label (`:528`).

**Products** (`PRODUCTS`, `:99-125`), 11 of them: armour piece, barding, cloak, boots, bracers,
gloves, belt, cap, satchel, sheath, straps. Each has a `min_size` against the largest hide
(`_size_problems`, `:924`).

**Armour key** (`_armour_key`, `:737-754`): `leather`, or `studded leather` when a fitting
whose id or name contains "stud" is on the bench. Nothing else. **Hide armour, padded,
lamellar and the Ultimate Equipment leathers are unreachable.** A bulette, purple-worm or
dragonhide suit comes out as `leather`, AC 2. Measured for bulette and red dragonhide.

**Output** (`_output`, `:757-787`): `kind: crafted`, flat `specs`, `masterwork`, `tanned`,
`armour`, `slot`, `wearable`, `how`. It has no `gear`, no `base` and no `pieces`, so
`forge_items.is_forged` is false and none of the forge's readers apply.

**Mastery and failure** go through the engine's `craft` op (`play/craft_views.py:616-700`).
**Inputs are spent on any failure** (`:656`). The book's rule, which herbalism and the forge
adopted, keeps them on a fail by 4 or less.

**Spoilage** (`_spoilage_problems`, `:792`) works only if the stock record carries
`age_hours`. The bench never passes one (§5), so the rule is live in tests and dead in play.

---

## 2. The catalogue: `content/materials/leatherworker-materials.json`

**127 materials**, 3,233 lines, `"craft": "leatherworker"` at file level.

| Kind | common | uncommon | rare | exotic | legendary | total |
|---|---|---|---|---|---|---|
| hide | 14 | 15 | 13 | 10 | 13 | **65** |
| tannin | 4 | 3 | 2 | 2 | 1 | 12 |
| dye | 5 | 3 | 2 | 1 | 1 | 12 |
| thread | 5 | 2 | 2 | 1 | 1 | 11 |
| oil | 3 | 1 | 2 | 1 | 1 | 8 |
| fitting | 4 | 2 | 1 | 1 | 0 | 8 |
| treatment | 3 | 2 | 0 | 1 | 0 | 6 |
| wax | 2 | 1 | 1 | 1 | 0 | 5 |
| **total** | 40 | 29 | 23 | 18 | 17 | 127 |

- **How each is obtained:** harvested 80, bought 27, gathered 13, mined 7. Under the older
  `source` field: skinned 65, bought 25, rendered 16, foraged 12, smithed 9.
- **Hide sizes:** large 22, huge 19, medium 13, small 8, gargantuan 3. Each hide has one
  fixed size, whatever the size of the beast. A young dragon and a great wyrm give the same
  "huge" hide.
- **Clock:** `fresh_hours: 48` on all 65 hides, and nothing else.
- **`craft_dc`** is authored on 13 entries: 11 dragonhides at 30, kraken hide at 32 and
  tarrasque plate at 35.
- **`risky`** is set on 33 entries.

### Effects

| Type | Count |
|---|---|
| `narrative` | **96** |
| `resistance` | 30 |
| `skill_mod` | 24 |
| `combat_mod` (all `ac`, typed `armour`) | 13 |
| `save_mod` | 4 |
| `damage_reduction` | 4 |
| **total** | 171 |

- Specs per material: 0 specs on 14, 1 on 72, 2 on 24, 3 on 17. None has 3 *executable* specs.
- 61 materials carry at least one executable spec. 52 carry only narrative. The 14 with
  nothing are mostly common dyes, threads and fittings.
- **Dragonhides** (11, all legendary): each is `resistance <energy> 5`, plus two narrative
  lines. One of those reads "Takes enchantment as masterwork armour" while the code requires
  `tool` for masterwork.
- **No hide has a drawback in executable form.** Every "check penalty one worse" (boar,
  crocodile, dire boar, ankheg, cave bear, bulette, purple worm) is narrative.

### Links to the forge (lane C's `material` field)

Eight leatherworker fittings point at a forge parent (`tools/forge_data_pass.py:1009`):
iron-buckle → iron, brass-buckle → brass, steel-studs → steel, bronze-rings → bronze,
silver-clasps → silver, cold-iron-studs → cold-iron, mithral-fittings → mithral,
adamantine-buckles → adamantine. `materials.material_of` resolves them, and each parent's
`forms` lists them (measured, e.g. mithral: `fitting:mithral-fittings`). The reverse link also
exists: the forge's `dragonhide-grip` names `red-dragonhide` as its parent, so
`red-dragonhide.forms` is `['hide', 'grip:dragonhide-grip']`.

The leatherworker copies are still **flat**. They have no `pieces`, `weapon`, `armour` or
`working`, and `materials.is_forge` is false for all 127 leatherworker documents, so the
forge's validator never judges them. Steel studs carry `+1 AC armour`, and the other seven
fittings carry narrative or nothing.

### Dead weight

- `forageable` (13 true) is read by nothing on this shelf.
- `effects_converted` is a migration flag.
- `source` is superseded by `obtain`, and kept only as the old blacksmith join key.
- `fresh_hours` is read, but never armed in play (§4).
- **Treatments.** `curing-salt` is not needed by cure. `mordant-salts` is not needed by dye.
  Nothing reads `liming-quicklime`, `tawing-alum` or `brain-paste`, the field tan. 5 of the 6
  treatments are therefore unused by any rule. `planar-quench` is only prose.
- **Fittings** other than studs do nothing at the bench but add their text.
- **Tannins.** All 12 are narrative-only. Their single job (the one-tier rule) is real, but
  their stated traits (hemlock "halves tanning time", mangrove "salt-proof", sumac "tans
  white") are prose with no time or effect behind them.

---

## 3. How the shelf is loaded

- `leatherworker.materials()` (`rules/leatherworker.py:289`) loads the file claiming
  `leatherworker`, plus homebrew, unfiltered.
- `rules/materials.py` reads the same file as one of its four `CATALOGUES` (`:43`) and
  normalises it. `KINDS` (`:49`) are the eight forge kinds, so hide, tannin, thread, oil, dye
  and wax are outside the forge's vocabulary.
- `rules/knowledge.py:29` already says the generalised knowledge store covers "the
  leatherworker's bench too". No leatherworker property is discoverable today, because no
  leatherworker document has typed traits to discover.

---

## 4. How hides are obtained today

The craft-action hub (`rules/benches.py:259 acquisitions`) lists four leatherworker
excursions (`ACQUISITION`, `rules/leatherworker.py:355-387`):

| Excursion | Gate | Pool |
|---|---|---|
| Skin the carcass | a downed creature in the scene (`_fallen`, `play/craft_views.py:1095`) | `obtainable("harvested", creature=name)`: name-fragment hides plus 6 generic goods |
| Strip bark and gather | biome | 13 gathered |
| Dig for salt and mineral | biome | 7 mined |
| Buy from the market | urban ground in a settlement | 27 priced |

All four run through one generic endpoint, `craft_excursion` (`play/craft_views.py:1240-1435`):
one d20 + the craft's `check_bonus`, an hours slider capped at 12, a haul drawn by modular
index, and a batch multiplier from the margin. The defects measured in §0.3 and §0.4 are this
endpoint's.

**Four crafts harvest the same carcass separately.** Each runs its own excursion with its own
d20, and none consumes the body:

| Craft | Excursion | Example of what it takes |
|---|---|---|
| Leatherworker | `skin` | hides, sinew |
| Blacksmith | `harvest` (`rules/blacksmith.py:359`) | dragon blood, wyrmsteel, dragonhide-grip, angelskin-binding |
| Alchemist | `harvest-reagents` (`rules/alchemist.py:374`) | dragon bile |
| Enchanter | `reliquary-harvest` (`rules/enchanter.py:666`) | the dragon ichors, dragon-scale catalyst |

**What the excursion reads.** It matches the scene actor's display name (`a.name`). A wolf the
narrator has renamed "the grey one", or a named NPC, matches nothing. The bestiary's
`creature_type`, `size` and `cr` are never consulted.

**World Bible.** There is no export field for a world's own fauna or its hides. A world's own
beast yields only the generic goods.

**Pinned by.** `tests/test_benches.py:209` (skinning puts something in the satchel),
`tests/test_leatherworker.py:567` (a winter wolf offers its pelt, never another beast's), and
`tests/test_leatherworker.py:131` (every hide names a creature the bestiary has). That last
test passes *because* of the substring false positives.

---

## 5. How leather armour reaches play

| Path | What happens | Measured |
|---|---|---|
| Old bench `armour piece` | Output `armour: "leather"` or `"studded leather"`, flat specs, no `gear` or `base` | yes |
| `/api/wear` with no `op` (`play/views.py:4512`, the `[data-wear]` buttons) | `Actor.wear` puts the name in the armour slot. `actor.armour` (the table key) is unchanged | yes: AC 15 → 15, key stays `leather` |
| `/api/wear` with `op: "wear"` (the engine's `_op_wear`, `rules/engine.py:14815`) | `_wear_crafted` reads `base` ("Deer Armour") before `armour` and refuses | yes: "not built on any suit the rules know" |
| `armour_stats` (`rules/sheet.py:797`) | Reads `ARMOUR[actor.armour]` unless a **forged** record is in the slot | read |
| Masterwork on a leather record | Nothing reads it for armour. The forge's −1 ACP comes from `forge_items.build` on forged records only | read, and the probe shows ACP unchanged |
| Hide specs on a worn record | `_standing_mods` reads worn records' flat specs (`rules/sheet.py:1038`). Resistances, skills and saves would apply. Armour-typed AC is swallowed by the suit (§0.2) | AC part measured |

**Leather armour gaps.**
- `tables.ARMOUR` (`rules/tables.py:538-566`) has the 12 CRB suits: padded, leather, studded
  leather and `hide armour` are there; leather lamellar, armored coat, quilted cloth and
  wooden armour (Ultimate Equipment) are not.
- `tables.py:436-437` gives leather and hide hardness 2, 5 hp per inch.
- The forge leaves those four CRB suits to "the tanner" (`rules/blacksmith.py:966`), and the
  tanner can only produce two of them, neither of which can currently be worn (above).

**The enchanter** requires a masterwork vessel (`rules/enchanter.py:496`) and lists the
leatherworker as a source (`:679-680`). A leather record's `masterwork` flag satisfies it, so
an enchanted leather suit is possible on paper. It would then be worn through the same broken
path.

---

## 6. The old `/craft/` Leatherworking tab

`play/craft_views.py:42` declares the discipline. It is the generic chain bench
(`play/templates/play/craft.html`): shelf, methods in order, product pattern, preview, batch
craft. It has **no `moved` flag**, so it is live, while herbalism's tab says "at the table now"
(`:33-37`). The herbalism UI plan kept the old bench for the other crafts "until each is
revamped" (`docs/herbalism-ui-plan.md` §1).
- Method glyphs: `rules/benches.py:239-243`.
- Material glyphs: `KIND_GLYPH`, `rules/leatherworker.py:43`.
- The bench stage's 3D props (`play/static/js/bench-stage/05-props.js`, `06-tools.js`) mention
  leather only as texture. There is no tannery stage.

---

## 7. Tests that pin it

`tests/test_leatherworker.py`: **39 tests**. Together with `tests/test_benches.py`, 62 pass in
7.1 s (run 2026-10-04). Grouped by what the revamp would do to them:

| Group | Tests (line) | Fate under a revamp |
|---|---|---|
| Track shape | 37, 48, 57, 70 (level-5 deed) | retire or re-pin, as herbalism retired its level 4–5 tests |
| Catalogue | 83, 89, 102, 116 (same-tier hides not reskins), 131 (bestiary names), 147, 555 | keep the intent; 131 needs real matching (§0.4) |
| Clock | 155 (48 h equals the herbalist's animal clock), 210 | keep, and arm it in play |
| Chain refusals | 172, 184, 196, 229, 243, 253, 261, 309, 318 | rewrite for step-by-step |
| Bench contract | 336, 357, 368, 382, 398 | rewrite for the new API |
| Output | 413, 449 (masterwork only at 5), 458 (studs make studded), 478, 490 | rewrite against the shared armour record |
| UI data | 517 (glyphs), 535 (method help) | keep |
| Acquisition | 567, 581, 590, 599 | keep the intent, fix matching |

Elsewhere:
- `tests/test_aggregator.py:321`: hide AC must be typed `armour`.
- `tests/test_benches.py:85, 109, 123, 199-260, 319-336, 370`: the hub and the old tab.
- `tests/test_forge_materials.py:110`: one material, many shelves.
- `tests/test_herbalist_endless.py:22`: leatherworker is one of the "others" that keep the old
  level shape.
- `tests/test_api_robustness.py:58`.

---

## 8. Stale documentation

`docs/leatherworking.md` (445 lines) is the design record for the shipped track.
- Integration note 6 says nothing applies a worn item's specs. That is no longer true:
  `_standing_mods` does, except that armour-typed AC is swallowed.
- It presents masterwork odds (DC 18, 60% at level 5) as a working path to an enchantable
  suit. That suit cannot be worn (§5).
- Its winter-wolf example assumes the 48-hour clock starts at skinning. The clock never
  starts (§4).

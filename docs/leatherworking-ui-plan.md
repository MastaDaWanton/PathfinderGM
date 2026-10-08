# Leatherworking bench: the UI and 3D plan

Drafted 2026-10-05. This is the interface half of `docs/leatherworking-revamp-plan.md`; the
rules, numbers and engine lanes live there, and the lane shapes are in
`docs/leatherworking-contracts.md`. It is planned to the depth of
`docs/blacksmithing-ui-plan.md` and uses the same two design skills (`design-taste-frontend`,
`frontend-design`) under the owner's standing instruction: **keep the colours, images and
textures; change structure and behaviour** (redesign, preserve).

Sources:
- the owner's round 8 answers (`docs/leatherworking-questions.md`, Q8.1 to Q8.4) and the round 9
  ruling on an **In progress** section (Q9.3);
- `docs/leatherworking-prior-art.md` §3 (the real variables a tanner controls, with their
  ranges) and §6 (what games softened);
- the herb bench and the forge as built on master 1f88ada (`play/static/js/table/29` to `44`,
  `bench-stage/`, `forge-stage/`, `bench-games/`, `forge-games/`), read for what can be reused
  (§3).

Numbers marked **(proposed)** are mine and wait on tuning or a ruling.

---

## 0. Design read and dials

**Design read.** Reading this as: a crafting workbench inside a desktop game, for one player who
wants the hunt to end in something they wear, in the app's own dark leather, brass and
candlelight language, built in the table's vanilla numbered modules on `theme-v2.css` tokens and
the hand-written WebGL stage the herb bench and the forge already share. The skill's default stack
(React, Tailwind, Motion) is set aside by its own "one system per project" rule, as the herb and
forge plans record.

**Mode.** Redesign, preserve. Nothing about the app's palette, type or textures changes.

**What is different from the forge, in one line:** leather is about **the hide and the clock**.
A smith reads heat and fit; a tanner reads the hide (its size, its grade, its defects) and how
long it has been out of the animal. So the stage's centre is a **hide on a beam or a frame**, not
an anvil, and the work order gains a **clock line** for anything green or tanning.

| Surface | VARIANCE | MOTION | DENSITY | Why |
|---|---|---|---|---|
| **Stage** (beam, frame, kettle, vats, the hide, games) | 6 | **7** | 2 | One less than the forge: no fire and no sparks. The juice is the knife, the steam off the kettle, the curl of the scraping, the dye taking. |
| **Chrome** (rack, method strip, work order, footer) | 4 | **3** | 6 | Matches the table, the herb bench and the forge exactly. |

---

## 1. Decisions that bind this plan

| Question | Owner's answer (2026-10-05) |
|---|---|
| Q8.1 Bench | **Its own bench**, built from the herb bench's and the forge's parts. The stage is a **field kit on the ground or a tannery yard**; the work is **built from its pieces in 3D**; **engraved icons**. |
| Q8.2 Games | **The grounded set**: flense, tan, harden, stitch, tool, cut, and the harvest, each on a real controllable variable. |
| Q8.3 Tuning | **Generous, with Steady mode**, and every band shown **as a number and a bar** as well as a colour. |
| Q8.4 Old tab | **A "moved" card** when the new bench ships, as herbalism's. |
| Q9.3 In progress | **Every craft's unfinished work sits in one In progress section**, with countdowns that move with game time, until it is collected. |
| Q5.1 Harvest | **One "Harvest the carcass" action** for every craft the character has. That is a scene action, not a bench method, so it gets its own small surface (§6.9). |

**Carried over unchanged** from the herb bench and the forge: the full-screen layer over the table
(z 35) on `BenchCore`, the method strip with lock reasons in words, the d20 throw and the brass
verdict word, the minigame strip with Steady mode, the paper tag and its quality ladder, the
forge's build card, the perk picker, app-wide sound, the one-second rule, render on demand.

**Shared infrastructure this plan consumes and does not build** (contracts §6): the cross-craft
**In progress** section is built by the Enchanting lanes. The leather bench registers its work
there and links to it; it never draws its own list of timers.

---

## 2. Audit of today's Leatherworking tab

**Read from the code and the inventory, not driven live in this pass.** Lane U2 drives it live
on scratch data at 1600×900 before it changes anything, and records what it saw in its report
(the forge's audit found two defects only visible live: the herbalism card's two-second flash and
the shelf's scroll jump).

What is there (inventory §6, `play/craft_views.py:42`, `play/templates/play/craft.html`):
- the generic chain bench: the full catalogue of 127 materials as a shelf with emoji glyphs
  (`KIND_GLYPH`, `rules/leatherworker.py:43`), most of them greyed by tier;
- eleven method stations including **Skin**, which refuses at the bench, and **Line**, which
  measurably does nothing;
- a product pattern picker over 11 products; a preview whose Effects list carries tannin and wax
  prose onto the finished item (inventory §0.6: "The standard tanning agent for common and
  uncommon hides" on a boar-hide suit);
- a batch Craft button that spends every input on any failure (`play/craft_views.py:656`).

**Keep:** the tooled leather panels and clasps; Cinzel small caps; reasons in words; the itemised
check terms.

**Retire on this bench:** emoji glyphs; the all-materials wall; the eleven-station grid; the
product pattern picker as free choice (the engine names every shape); Skin and Line as stations;
the herb cauldron metaphor.

**Defects to look for when driving it live** (seen on the other tabs): the two-second
"Herbalism is at the table now" flash on selecting another tab, and the shelf's scroll jump.

---

## 3. What is reused, and what is new

Measured on master 1f88ada (lines, and mentions of anvil, hearth, smith, forge or heat):

| Module | Lines | Forge words | Reuse |
|---|---|---|---|
| `table/29-bench-core.js` | 662 | 8 | **As is.** Layer, focus trap, Esc stack, keys, clock, footer, flourish layer. The leather bench is its third `BenchCore.mount`. |
| `bench-stage/00-math.js` to `04-particles.js` | 1,449 | n/a | **As is.** Renderer, maths, biome ground, particles. |
| `bench-stage/02-meshes.js` | 258 | n/a | As is, plus the hide and the leather families (§7.3). |
| `table/33-bench-games.js` (the strip frame) | 1,195 | n/a | **As is**, through the registration the forge's U3 lane made extensible (`BenchGameDefs[method]`). The leather games add **one gauge type**, the clock-and-band gauge (§6.4); the heat gauge stays the forge's. |
| `table/34-bench-tag.js` (paper tag, ladder) | 246 | n/a | As is; the hide's **grade cap** is drawn on the ladder (§6.5). |
| `table/36-bench-perks.js` | 333 | n/a | As is: the forge's U5 lane parameterised it by track. |
| `table/41-forge-rack.js` | 260 | 28 | **The pattern**, not the file: the leather rack is its own file with leather groups (§6.2). |
| `table/43-forge-order.js` | 434 | 44 | **The pattern and the build card.** The piece slots and "Show the sum" are the same shape; the build card is the forge's, opened through a shared function (contracts §11.1). |
| `table/44-forge-ledger.js` | 699 | n/a | Parameterised by track (as `36-bench-perks.js` was), so one ledger card serves both shelves: the forge's assay and the leather Grade differ only in words. |
| `forge-stage/02-families.js` | 532 | 10 | The **haft** family, reused to show a grip being wrapped (§7.3). |
| `forge-stage/00-heat.js`, `01-props.js`, `03-smithy.js`, `04-fx.js` | 947 | 79 | Not reused. A tannery has no hot metal. |

**What is new:** the leather shell (`45`), rack (`46`), stage adapter (`47`), work order (`48`),
the harvest surface (`50`), `leather-games/`, `tannery-stage/`, `leather.css`. Roughly the forge's
new-code size, smaller in the stage because the renderer is done.

---

## 4. Tokens

**No new colours, fonts or textures.** The leather bench maps onto the bench's semantic layer
exactly as the forge does:

```css
.leather {
  --bench-ground: var(--sunk);
  --bench-ink: var(--ink);
  --bench-quiet: var(--dim);
  --bench-accent: var(--gold);        /* the one accent: active method, Roll, ceiling */
  --bench-warn: var(--alarm);         /* ruined hides, spoiling soon, a deed warning */
  --bench-light: var(--candle);
  --bench-radius: 3px;
}
```

**The hide's colour is content, not chrome.** Fur, scale and leather tones, the tannage's own
colour (alum white, bark tan, brain and smoke brown, a planar tannage's sheen) and dye colours
appear **only in the 3D scene and as the 8px swatch** beside a rack row, the forge's rule for heat
and metal swatches. The swatch never carries meaning alone: the name is always beside it.

**Grade** reads by words and by shape, never by hue: "Grade 1" to "Grade 4" and "Reject", with a
small notch count on the hide icon (four notches for grade 1 down to one), so colour-blind
players read it the same way.

**The spoil clock** reads in words first ("spoils in 31 hours", "salted: keeps") and as a short
segmented strip of 8 segments (6 hours each) with no filled background track (pre-flight
§14). Under 12 hours left the row's text turns `--alarm` **and** gains the word "soon".

**Icons** from game-icons.net (CC BY 3.0, credited in About, the manual and
`docs/asset-licences.md`), rendered as gilt masks like the herb and forge icons. The lead downloads
them on the owner's approval, as for the forge (forge contracts §13.1).

| Group | Icons (proposed names) |
|---|---|
| Forms | green hide, salted hide, pelt, leather roll, rawhide, panel, hardened plate, scales, grip wrap, lacing |
| Consumables | salt sack, tannin bark, alum, oil flask, wax cake, thread spool, dye pot |
| Methods | flensing knife (Flense), salt (Salt), vat (Tan), slicker (Curry), round knife (Cut), needle and awl (Stitch), kettle (Harden), mallet and stamp (Tool), dye brush (Dye), layered sheets (Laminate), buckle (Assemble), magnifier (Grade) |
| States | green, salted, spoiling, tanning, struck through, hardened, laminated ×N, grade notches |
| Harvest | skinning knife, carcass, horn, fang, blood vial, essence (the other crafts' parts use their own bench's icons) |

---

## 5. Layout

### 5.1 The layer

The leather bench opens over the table as its own layer (`#leather`, `role="dialog"`,
`aria-modal="true"`, z 35), mounted on `BenchCore` like the herb bench and the forge. It opens
from a **Leatherwork** button in the left column beside Herbalism and Smithing
(`play/templates/play/table.html`, the `.door` buttons). The old `/craft/` Leatherworking tab
becomes the moved card (§13). Esc, focus trap, the clock and closing behave exactly as the other
two benches; opening it while another bench is open is refused by the core, as today.

### 5.2 Desktop grid, 1600×900

```
┌ #leather ───────────────────────────────────────────────────────────────────────────────────┐
│ Leatherwork [Flense][Salt][Tan][Curry][Cut][Stitch][Harden][Tool][Dye][Laminate][Assemble][Grade] [Close] │ 56px
├ rack 280px ───────┬─ stage, minmax(620px, 1fr) ────────────────────────┬─ work order 340px ──┤
│ Search your rack  │                                                     │ ┌ piece slots ─────┐ │
│ [What fits ▾]     │   the wolf pelt stretched on the frame,            │ │ Body   ▣ Wolf     │ │
│ Green hides       │   flesh side up, the fleshing beam beside it       │ │        leather ×1 │ │
│  ▣● Wolf pelt     │   (field kit on forest floor, or tannery yard)     │ │ Fasten ▣ Sinew    │ │
│     spoils in 31h │                                                     │ │        lacing     │ │
│ Leather           │                                                     │ │ Lining ▢ empty    │ │
│  ▣● Deer leather  │ ┌ minigame strip ─────────────────────────────────┐ │ └──────────────────┘ │
│     Grade 2  2    │ │ DEPTH ▕──[▓▓▓]──▏ 0.6 of thickness  Space to    │ │ ┌ paper tag ───────┐ │
│ Tannins           │ │ stroke   holes 0   Fine                          │ │ │ Hide armour      │ │
│  ▣ Oak bark   3   │ └──────────────────────────────────────────────────┘ │ │ ladder, ceiling, │ │
│ Can't use now     │ 1 pelt. 40 minutes. DC 16, you need 11 or better.  │ │ grade cap marked │ │
│  ▢ Bulette hide   │              [ Roll Craft ]                        │ │ └──────────────────┘ │
│   needs a tannery │                                                     │ Build: AC +1, ACP −1 │
│                   │                                                     │ [ Show the sum ]     │
├───────────────────┴─────────────────────────────────────────────────────┴──────────────────────┤
│ Day 14, 6:20pm  At the field kit  Leatherworker 1 ──── 8 / 25  In progress (2)  Recipes  Ledger  Steady ○ │ 44px
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

- **Grid:** `280px minmax(620px, 1fr) 340px`; rows `56px 1fr 44px`, the forge's.
- **The footer** names where you are ("At the field kit", "At Hollin's tannery, 2 sp a day per
  vat") and carries **In progress (N)**, which opens the shared section (§6.8).
- Twelve methods do not fit at 1280: the strip goes to icons with names on hover and focus there,
  as the forge's eleven do.

### 5.3 Other sizes

As the forge plan §5.3: the 3440×1440 ultrawide caps content at 2,000px with the ground filling the
width; 1280×720 narrows the rack to 240px and the order to 300px; under 1180px the stage stacks on
top at 56vh; under 768px a single column, every game with a tap form.

---

## 6. Components

### 6.1 Method strip

Twelve methods in the order a tanner works: Flense, Salt, Tan, Curry, Cut, Stitch, Harden, Tool,
Dye, Laminate, Assemble, Grade. Locked methods show a lock and the reason in words:
"Leatherworker 2", **"Needs a tannery"** (location lock, the forge's "Needs a smithy"), or
**"Needs a vat: the tannery here is full"**. Keys 1 to 9, 0, - and = pick; arrows move.

### 6.2 The rack (left)

The forge rack's pattern for leather:
- Only what you **carry**, plus anything waiting for you at the tannery you are standing in
  (shown under "Here at the tannery", with Collect when ready).
- **Groups, in working order:** Green hides, Salted hides, Pelts (flensed), Leather and rawhide,
  Panels and plates, Bases and grips, Tannins, Oils and waxes, Threads and lacing, Dyes, Fittings,
  Finished work, Old work.
- **A row:** form icon with the rarity rim and grade notches, the swatch, the name, the count in
  **hide units** where the form is a hide ("Wolf pelt 1 Medium", "Bison hide 4 units"), state
  badges (green, salted, hardened, laminated ×2), the grade word, and a "?" while anything is
  unknown.
- **Green hides carry their clock** on the row, in words and the segmented strip (§4). Carrying
  curing salt shows "salted as you go: kept" instead, and the salt sack's own count beside it, so
  the reason the clock stopped is visible (revamp plan §6.4).
- **Can't use now** carries its reason: "needs a tannery for rare hides", "Leatherworker 2 for
  bark tanning", "not tanned: alum leather will not harden", "a hide this small makes gloves, not
  a suit (needs 2 units)".
- **No scroll jump** (the old tab's defect): the list is redrawn in place, scrollTop read before
  and restored after, the focused row found again by its key. The forge rack's code is the model.
- **Empty state** for the method: "Nothing you carry can be flensed." with **Buy at the market**
  in a settlement and **Everything I carry**.

### 6.3 Stage

- **Composition at the field kit:** a fleshing beam at centre (a log on two legs, angled), the
  stretching frame behind it, the kit roll open on the ground with knives, awl, needles and
  mallet; a small pot over a fire for brain tanning and for Harden only where the rules allow it
  there (revamp plan §10). Camera at about 35° looking down the beam.
- **At a tannery:** a yard of packed earth, sunk vats in a row behind, a drying rack with hides
  hung, the hardening kettle on its stand, a currier's table. Town tannery and founded tannery
  differ by ground (**proposed**: flagstones and a lean-to for a town tannery; packed earth and a
  plank shed for a founded one). CC0 textures at 1K, at most 300 KB each, in
  `docs/asset-licences.md`.
- **Light:** daylight or night fill from the scene clock, as the herb stage, plus a lantern at
  night. The kettle and the vats give steam, not light. **No flicker loop**, so the idle-zero-frames
  rule holds without the forge's hearth exception.
- **The work** sits on the beam, the frame or the table, built from its pieces (§7.3).
- **Info line** in plain words under the stage: "1 pelt. 40 minutes. DC 16, you need 11 or
  better." For a tannage it adds the wait: "Then 4 weeks in the vat. Ready Day 42."
- **Roll Craft** is the only gold-filled button, disabled with its reason beside it ("Put a
  tanned leather in the body slot").
- **WebGL fallback:** the engraved icon at 160px on the ground colour; every game runs in its 2D
  strip.

### 6.4 Minigame strip

The shared frame, unchanged in shape (meter left, input hint centre, live tier right, time thread
on top). Leather games add **one gauge type** to the frame's registry: a **band gauge** with named
bands printed under it, a needle, the target band outlined (shape, not only colour), and the
number in its real unit: fraction of thickness for Flense and the harvest, liquor strength
"weak, medium, strong" plus a number for Tan, °C and seconds for Harden, stitches per inch for
Stitch, minutes since wetting for Tool, percent fat for Curry. Each game declares its unit; the
frame prints it. This is Q8.3's "number and bar as well as a colour".

### 6.5 The work order (right)

**Piece slots** at the top, labelled by what is being made:
- a suit or shield: **Body, Fastenings, Lining**, the forge's armour pieces;
- a grip: **Grip** (one slot, the hide) and the haft it will wrap, shown greyed with "the forge
  fits it to a weapon" (revamp plan §13);
- worn goods (cloak, boots, belt and the rest): **Body** and **Lining** where they have one;
- a step that is not assembly (Flense, Salt, Tan, Curry, Cut, Harden, Tool, Dye, Laminate): the
  method's inputs (the hide, the tannin, the salt), as the forge shows Bar and Fuel at Forge.

Each slot is a drop target and a button: filled, it shows icon, swatch, name, grade and passes
("laminated ×1"), with × to take it off; empty, it says what goes there and pressing it sends the
keyboard to the rack's first row that fits.

Under the slots, the **paper tag** (`34-bench-tag.js`): the product, form, and the ladder with
your ceiling and **the hide's grade cap** marked on the rung where it stops ("Grade 2 hide:
Superior is the most it allows"). Where the body is a book always-masterwork material (dragonhide,
eel hide, angelskin, darkleaf cloth), the tag says "masterwork by its nature" on every rung, so the
player is not told to chase Superior for it.

At the bottom, the **build summary** (one short line per target, then book powers in words: "the
armour itself is immune to fire") and **Show the sum**, which opens the forge's build card
unchanged (same component, same server shape).

**The base hand-off line.** When the product is a base the forge finishes (studded leather,
armoured coat, steel lamellar), the order says so under the tag: "A base: the forge finishes it
into studded leather. It can be worn as leather armour until then." (revamp plan §13).

### 6.6 The build card

The forge's card (forge UI plan §6.6), reused: one row per target, one column per piece, raw,
after quality and the negative cut, final, "rounded toward zero". Book effects listed separately
("from the body, by the book: masterwork; the suit is immune to fire; energy resistance costs 25%
less to enchant"). Marks are listed separately too, one line each ("from the salamander oil: fire
resistance 1"). It opens from the item's row on the sheet and in the inventory, as the forge's
does.

### 6.7 The ledger card and the Journal

`44-forge-ledger.js` parameterised by track. The card: icon and swatch, name, which creatures it
comes from **in words the player has met** (never a hidden bestiary list), known properties with
how each was learned ("graded, day 14", "taught by Hollin"), one line per unknown, and the
actions **Grade** (a scrap, 10 minutes) and **Ask a tanner** when one is in the scene. The
Journal section lists every hide met, "3 of 7 known", with an "Unknowns first" filter, beside the
herbarium and the materials ledger.

### 6.8 In progress (consumed, not built here)

The shared section is the Enchanting lanes' (contracts §6.1). This bench:
- shows **In progress (N)** in the footer, N being this character's unfinished work across every
  craft, and opens the shared section on click;
- registers each tanning as an entry (revamp plan §8.3): the hide, the tannage, **where** it is
  ("in the vat at Hollin's tannery", "in your pack"), the countdown in game time ("ready Day 42,
  6am: 9 days"), and **Collect** when ready and reachable;
- shows the same entry in the rack under "Here at the tannery" when you stand where it waits.

What the countdown looks like is the shared section's decision. The bench only guarantees that
every entry it registers has a name, a place and a ready minute from the server.

### 6.9 The harvest surface (new, cross-craft)

**Harvest the carcass** is a scene action, not a bench method (revamp plan §5). It opens from:
- the downed creature's row in the scene panel ("Harvest" beside it, only while the carcass is
  harvestable and the character has a craft that wants a part);
- the table's craft-actions hub, where today's four excursions are.

It is a **sheet over the table** (not a full bench layer), mounted on `BenchCore` with its own
small layer at z 35 so Esc and the focus trap are the same:

```
┌ Harvest the carcass: Winter wolf (Large, CR 5) ─────────────────────── [Close] ┐
│ Dead 20 minutes. Parts keep 48 hours from the harvest; salt stops the clock.   │
│                                                                                │
│ Leatherworking                                                                 │
│  ▣ Winter wolf pelt   2 units   Survival DC 20, you need 13 or better  [Take] │
│  ▣ Sinew              1         Survival DC 20                          [Take] │
│ Alchemy                                                                        │
│  ▣ Frost gland        1         Heal DC 20, you need 15 or better       [Take] │
│ Taken                                                                          │
│  ▢ Fangs (Enchanting) taken Day 14, 6:02pm                                     │
└────────────────────────────────────────────────────────────────────────────────┘
```

- One row per part, grouped by craft, each with its skill, DC, odds, time and yield, from the
  server. A part already taken shows "taken" with when; nothing can be taken twice.
- **Take** throws the d20 (the same dice and verdict word) and, for a hide, plays the **harvest
  game** (§9), which sets the hide's grade.
- **A deed warning** for parts whose taking is a deed (revamp plan §5.6): the row reads "Taking
  this is a deed others may hear of" in `--alarm` words, and Take opens a confirm: **Take it** /
  **Leave it**.
- **Humanoids never appear**: the scene panel offers no Harvest on them at all, so there is
  nothing to refuse in words.

---

## 7. The 3D stage

### 7.1 What is built new

Under `play/static/js/tannery-stage/`, beside `bench-stage/` and `forge-stage/`, on the shared
renderer:

| File | Contents |
|---|---|
| `00-hide.js` | The hide mesh (§7.2): an outline per creature body plan, scaled by size, with fur, scale, smooth or chitin surfaces; the defects the harvest left (holes, scores) drawn into it; its state (green, salted, flensed, tanned, hardened) changing its surface. |
| `01-props.js` | Fleshing beam, stretching frame, kit roll, round knife, awl and needles, stitching pony, mallet and stamps, slicker, brain-tan pot, hardening kettle, sunk vat, drying rack, currier's table. Low-poly, built in code like the herb tools and the forge props. |
| `02-pieces.js` | The leather families (§7.3): suit body panel, hardened plates for lamellar, a shield blank, a cloak drape, boots, a grip wrap that winds onto the forge's haft family. |
| `03-yard.js` | The tannery yard: ground, vats in a row, the rack, the lean-to or shed. Field-kit scenes reuse `bench-stage/03-ground.js`. |
| `04-fx.js` | Scraping curls (reusing `04-particles.js`), salt grains, kettle steam, the liquor's ripple, the dye bleeding in, a stamp's impression. |

### 7.2 The hide

- **Outline by body plan, not per creature.** Quadruped, long-bodied (crocodile, worm), winged,
  serpent, and a carapace for vermin chitin and shells. The creature's harvest tag names the plan
  (revamp plan §5.3); an untagged one uses quadruped.
- **Size** from its hide units, so a Large pelt fills the frame and a Small one sits in its middle.
- **Surface** from the material's server-sent `surface` (fur, scale, smooth, feather, chitin) and
  colour. Flensing removes the fur side by side as strokes land; tanning shifts the colour to the
  tannage's; Harden darkens and slightly shrinks it (the real cue, PA §3.5).
- **Defects stay visible.** The holes and scores the harvest game left are drawn into the hide and
  stay through every later step, so a Grade 3 hide looks like one.

### 7.3 Built from pieces

As the forge's families: parametric meshes joined at fixed sockets. A suit body panel takes its
cut from the base (leather, hide, padded, lamellar); fastenings show as lacing, buckles, rings or
studs on it; a lining shows as a fur or felt edge at the collar. Quality shows as surface finish
(rough edges at Crude, burnished edges and even stitching at Flawless). Tooling shows as the
stamped pattern; dye as colour. Armour shows as the body piece on the table, not a whole suit on a
stand **(proposed, the forge's rule)**.

### 7.4 Performance

Render on demand, as the herb and forge stages. There is no flame, so idle draws zero frames with
no exception; steam and the liquor ripple run only while a game is live. A test pins zero frames
over 10 idle seconds (herb plan §13.6).

---

## 8. Copy

Plain, in-world, sentence case, **no em-dashes or en-dashes in new strings** (the herb plan §8
rules; the lane greps for both).

| Label | Intent |
|---|---|
| Roll Craft | start a step |
| Take / Take it / Leave it | harvest a part; confirm a deed |
| Grade / Ask a tanner | learn a hide |
| Collect | take finished work out of In progress |
| Show the sum | open the build card |
| Save recipe / Load | recipes |
| Close | leave the bench |

Reasons keep the good grammar the old tab had and add the clock: "This hide spoils in 6 hours:
salt it or tan it", "Alum leather will not harden: it softens in water", "The vats here are full
until Day 18", "A hide this small makes gloves, not a suit", "Bulette hide needs a tannery".

---

## 9. Minigames

Rules in the revamp plan §11. Every game: mouse, keyboard, Steady mode, a 2-second first-time card,
generous to start (the sweep's strongest finding, PA §6: every crafting game it found was softened
after launch), each band a **number and a bar as well as a colour**, and **rarer hides narrow the
window** (the forge's "better metal, tighter window", from OSRS Giants' Foundry). No game needs a
long press; every hold has a toggle form in Steady mode.

The seven the owner named (Q8.2), each on the real variable from PA §3.9:

| Game | The real variable (source) | On the stage | In the strip | Mouse | Keyboard | Steady mode |
|---|---|---|---|---|---|---|
| **Harvest** | knife depth along the cut line; defect area, scored against UNIDO grades 1 to 4 and reject (PA §3.1) | the knife opens the line from throat to tail and around the legs; the hide peels back | a depth gauge (fraction of thickness, the "too deep" band hatched) and a defects counter; the grade it is heading for, live | drag along the line | ← → advance, ↑ ↓ depth | the line advances by itself at half speed; depth bands ×1.5 |
| **Flense** | scrape angle and pressure without cutting through (PA §3.2) | strokes over the beam, flesh and fat curl away, the hide brightens | pressure gauge with the clean band and the "through" band hatched; a stroke counter | click and drag a stroke | Space strokes, ↑ ↓ pressure | pressure drifts at half speed; band ×1.5 |
| **Tan** | liquor strength raised in steps, then the cut test: "struck through" when the tan runs the full cross-section (PA §3.3) | the hide in the vat or pot, the liquor darkening step by step; then a cut and its cross-section | a strength gauge with the step marks; at the end a cross-section bar showing how far the tan has run | click to step up the liquor when the hide has taken the last | Space steps; C cuts | steps auto-advance on a beat, you only confirm |
| **Harden** | water heat against time; soft if under, shrunk and brittle if over (PA §3.5, our synthesis, labelled) | the piece dipped into the kettle, steam, the piece darkening and shrinking | a two-axis band: °C on the gauge, seconds on the time thread; a size meter showing 7/8 (good) and 2/3 (brittle) | click to dip, click to lift | Space dips and lifts | heat drifts at half speed; band ×1.5; dip and lift are presses, never a hold |
| **Stitch** | stitch pitch and rhythm: 8 to 9 SPI rough, 10 to 12 good, 14 to 18 fine (PA §3.6) | two needles saddle-stitching along the seam | a beat ring per stitch and a pitch reading in SPI | click on the beat | Space | ring window ×1.6; tempo ×0.75 |
| **Tool** | casing moisture: the leather returned to its colour but still cool; no published percentage, so time since wetting (PA §3.6) | the leather darkens when wetted and lightens as it dries; stamps strike the pattern | a "since wetting" gauge in minutes with the casing band; a strike counter | click to strike | Space strikes, W re-wets | the drying runs at half speed |
| **Cut** | following the pattern line | the round knife follows a chalk line on the leather | a deviation gauge (millimetres off the line) | drag along the line | ← → steer, Space advances | auto-advance, steer only; band ×1.5 |

**The other methods** (not in the owner's list, so each is **(proposed)**): one game per method is
the cross-craft rule, so these are the smallest honest games for the step.

| Game | The real variable | In the strip | Steady mode |
|---|---|---|---|
| **Salt** | coverage to the edges (salt at 25% of green weight to 1:1, PA §3.1) | a coverage map of the hide; strokes fill it | coverage ×1.5 per stroke |
| **Curry** | fat worked in: healthy 2 to 10% fat, 12 to 20% water (PA §3.4) | a fat gauge in % with the band | drift ×0.5 |
| **Dye** | an even take | the forge's Finish game (coverage strokes), with a dye colour | as the forge's |
| **Laminate** | glue spread then clamp in time | a spread coverage strip, then a beat to clamp | window ×1.6 |
| **Assemble** | lacing or buckles seated | the forge's Assemble beat game, with lacing in place of rivets | as the forge's |

**Grade has no minigame** (the forge's Assay and herb tasting have none): a short flex-and-look
animation on the stage, then the result in words.

**The tan game in two halves.** A bark tannage runs for weeks of game time. The strength steps are
played when the hide goes into the vat; the cut test is played at Collect. The tier is decided
from both halves' scores, and it is the server's (revamp plan §8.3). If the player collects from
In progress somewhere without the bench open, the cut test opens as a strip on its own.

**No game depends on the cursor art.** Each draws its own reticle (the knife edge, the needle,
the stamp face).

---

## 10. Motion and juice

Every animation has a reason (feedback, state change, hierarchy). Short and reduced-motion forms
throughout, as the forge plan §10.

| Event | Stage | Chrome | Reduced motion / Short |
|---|---|---|---|
| Open the bench | the kit roll unrolls, the hide settles on the beam | layer fade 200ms | fade only |
| Switch method | tools swap on the kit roll (450ms) | strip underline slides 160ms | crossfade 120ms |
| Drop into a slot | the piece lays onto the frame or table | the slot fills | slot fills, no motion |
| A good stroke or stitch | a clean curl, a pull of thread, a soft creak | the pip fills | pip only |
| A miss | a nick, a dull scrape | the hint changes | same, no motion |
| A hole in the harvest | the hide tears at the point; it stays torn | defects counter ticks | counter only |
| Harden | steam plume, the piece shrinks a little | none | no steam |
| Tier up | the leather sheens | the ladder rung brightens 180ms | instant |
| Flawless | the brass word over the work, a gilt glint | none | the word only |
| Product lands | it lifts and flies to its rack row (500ms) | the row pulses once | the row highlights |
| Failure | the work tears or dulls, the stage dims 30% for 600ms | the loss in words | dim only |
| Tanning starts | the hide sinks into the vat | the In progress count ticks up once | count only |

**The one-second rule** holds: flourishes run in `#rv-layer` with `pointer-events: none`, any
click skips them, and the rack, slots and Close stay live.

---

## 11. Sound

On the app-wide buses, a new **leather** bus with its own volume in Sound settings beside Bench and
Forge. Synthesised like the forge's (no recorded assets needed to start):
- `leather.open`, `leather.method.<name>`, `leather.drop.<form>`, `leather.roll`;
- `leather.knife` (the harvest and Cut; pitch by hide surface: fur soft, scale sharp),
  `leather.tear`, `leather.scrape`, `leather.salt`, `leather.slosh` (vat), `leather.cut-test`,
  `leather.steam`, `leather.stitch.pull`, `leather.stamp` (pitch by casing), `leather.brush`,
  `leather.clamp`, `leather.buckle`;
- `leather.tier.up`, `leather.flawless`, `leather.fail`, `leather.land`, `leather.grade`;
- `ambience.tannery` (water, a distant yard) or the biome ambience at the field kit.

Unknown events are silent, so callers never guard (forge contracts §11).

---

## 12. Engineering shape

**Files** (the numbering continues the forge's):
- `play/static/js/table/45-leather-shell.js` (the layer on `BenchCore`, the method strip, the info
  line, Roll, the game call, results);
- `46-leather-rack.js`, `47-leather-stage.js` (the adapter onto `tannery-stage/`, global
  `window.TanneryStage`), `48-leather-order.js` (slots, tag with the grade cap, the base hand-off
  line, the shared build card);
- `50-harvest.js` (the cross-craft harvest sheet, §6.9);
- `play/static/js/leather-games/*.js`, one file per game, registered on `BenchGameDefs`;
- `play/static/js/tannery-stage/*.js` (§7.1);
- `play/static/css/leather.css`, after `bench.css` and `forge.css`, existing tokens only;
- `play/leather_views.py` (the bench API) and `play/harvest_views.py` (the harvest API), routes
  registered **above any catch-all** (the herb bench's route-order bug, pinned by
  `test_bench_routes`).

**The stage interface** mirrors `ForgeStage`: `window.TanneryStage = {available(), mount(host),
unmount(), setScene({kind: "kit"|"town"|"owned", biome, roofed, minute}), setTool(method),
setWork({product, base, pieces: {slot: {material, color, surface, grade, passes, defects}},
quality_index}), game(method), flourish(kind), productRect(), reducedMotion(bool)}`. Without
WebGL every call is a no-op and `available()` is false.

**The server contract** (the three laws): the page sends the method, the material ids per slot,
the batch and the game score (0..1). The server answers with the tier, the clamped score, the
product and its computed build, mastery lines, discoveries, the time passed, and any In progress
entry it registered. **The page never computes a number**, including the grade, the clock, the
hide units and the build sum.

**Lazy loading:** the leather chunk and its stage load on first open, never on the table's first
paint (the forge left this open, forge contracts §15.1; this bench should not repeat it).

---

## 13. The old tab: the moved card

When this bench ships, `play/craft_views.py` gives the Leatherworking discipline a `moved` string,
exactly as Herbalism's (`play/craft_views.py:33-37`): "Leatherworking is at the table now: open the
bench from the table to work one step at a time." The page draws the card with an **Open the
bench** button. The old chain code for leather retires with it, its tests re-pinned (inventory §7,
revamp plan §17). The four leather excursions leave the craft-actions hub; the hub shows **Harvest
the carcass** in their place when a carcass is in the scene, and keeps Strip bark, Dig for salt and
Buy at the market as they are.

If the two-second flash of the herbalism card on other tabs is still present when lane U7 drives
it, fix it there (the forge's U7 was given the same job).

---

## 14. Verification (before it is called done)

1. **Live, on scratch data**, every method at 1280×720, 1600×900, 1920×1080, 3440×1440 and under
   1180px, at the field kit and at a tannery. Screenshots in the lane report.
2. **Reduced motion and Steady mode:** every game playable, no shake, no hold longer than one
   press.
3. **Keyboard only:** open, pick a method, fill the slots, roll, play, close; open the harvest
   sheet, take a part, close.
4. **Contrast:** dimmed rack rows, reasons, the clock strip and its words, the tag, the build card
   and every gauge label, measured against their real backgrounds, AA.
5. **The one-second test** and **idle zero frames**.
6. **End to end in play** (the path the player actually clicks, the standing instruction): kill a
   wolf, harvest its pelt from the scene, salt it, flense, tan, make a leather base, carry it to
   the forge and finish studded leather, wear it, and read the AC rise on the sheet of
   `pc-kesst` (15 to 16, the owner's proof of done, revamp plan §14). Start a bark tannage at a
   tannery, leave, pass the days, come back and Collect from In progress.
7. **Packaged build:** open the bench in `win-unpacked` on a throwaway data dir.

---

## 15. Pre-flight (the skill's matrix, adapted to a game screen)

| Check | Status |
|---|---|
| Design read and dials | §0, split by surface |
| Redesign audit | §2 (read, and to be driven live by U2) |
| Zero em-dashes and en-dashes in new strings | §8; the lane greps |
| One theme, one accent | dark; gold only; hide, tannage and dye colours are scene content (§4) |
| Shape lock | 3px; circles for rings, swatches and grade notches |
| Button contrast, no CTA wraps | Roll Craft, Take, Collect: one or two words |
| Labels above fields | the rack search |
| No eyebrows; plain group headings | §6.2 |
| One label per intent | §8 |
| Motion motivated, reduced motion | §10 |
| No idle loop | §7.4 (no flame at all) |
| Empty, loading, error states | §6.2, §6.3, as the herb plan §7 |
| No filled-track progress bars | the clock strip is segmented with no track; gauges are banded |
| Icons from a library | game-icons.net, credited |
| No emoji | retired (§2) |
| z-index | the herb plan's scale; leather layer and harvest sheet at 35, one open at a time |
| Mobile collapse | §5.3 |

---

## 16. Build order

| # | Lane | Contents | Depends on |
|---|---|---|---|
| U1 | **Shell, flat** | the layer on `BenchCore`, method strip with level and place locks, the rack with clocks, the work order with slots, grade cap and build card, Roll and the d20, results to the rack, the In progress link, all on the flat engraved-icon stage. **Playable end to end before any 3D.** | rules lane E's API (contracts §7) |
| U2 | **Harvest sheet** | `50-harvest.js`, the scene panel's Harvest button, the hub entry, the deed confirm | rules lane C's API |
| U3 | **Games** | the twelve games in the shared frame, the band gauge, Steady mode | U1, U2 (the harvest game) |
| U4 | **Stage** | `tannery-stage/`: hide, props, yard, pieces, fx | U1 (parallel with U3) |
| U5 | **Ledger and perks** | the ledger parameterised by track, the Journal section, Grade, the perk picker for leather | rules lane F |
| U6 | **Sound** | the leather bus and its events | U3 |
| U7 | **The old tab** | the moved card, the hub change, the old chain's retirement | U1 |

**Why this order** is the forge's: a flat, working bench first, so the rules lanes are checked in
the real UI before any modelling, and tuning the games happens on the cheapest build.

---

## 17. Open points for the owner (UI)

1. **Five more games.** The owner named seven (Q8.2). Salt, Curry, Dye, Laminate and Assemble
   need one each under "one minigame per method, always played"; §9 proposes the smallest honest
   ones and reuses two of the forge's. Accept, or fold any of them into a neighbouring step?
2. **The tan game in two halves** (§9): strength steps at setup, the cut test at Collect. Accept,
   or play the whole game at setup and make Collect a plain button?
3. **Harvest as a sheet over the table** rather than inside the bench layer (§6.9), because it
   is a scene action that serves four crafts. Accept?
4. **The button name.** "Leatherwork" beside "Herbalism" and "Smithing". "Tanning" reads
   narrower than the craft; "Leatherworking" is long for the left column at 1280.
5. **Tannery grounds** (§6.3): flagstones and a lean-to for a town tannery, packed earth and a
   shed for a founded one.

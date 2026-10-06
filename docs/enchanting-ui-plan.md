# Enchanting bench: the UI and 3D plan

Drafted 2026-10-05. This is the interface half of `docs/enchanting-revamp-plan.md`; the rules,
numbers and engine lanes live there. It is planned to the depth of
`docs/blacksmithing-ui-plan.md` and uses the same two design skills (`design-taste-frontend`,
`frontend-design`) under the owner's standing instruction: **keep the colours, images and
textures; change structure and behaviour** (redesign, preserve).

Sources:
- today's Enchanting tab and the two built benches, read in code (§2, §3). **The audit here is
  from the code, not a live session**; lane U1 repeats it live on scratch data before building,
  as the forge's audit was done;
- `docs/enchanting-prior-art.md` §4-§5 (order, matching, windows, what was abandoned);
- the herb and forge benches as built: `play/static/js/table/29-44`, `bench-stage/`,
  `forge-stage/`, `bench-games/`, `forge-games/`.

---

## 0. Design read and dials

**Design read.** A ritual workbench in a desktop game, for a solo Pathfinder player who wants
magic to feel made, not bought. The language stays the app's own: dark tooled leather, brass,
Cinzel small caps, candlelight. Vanilla JS in the table's numbered modules, the existing
`theme-v2.css` tokens, the hand-written WebGL stage (the app bundles no third-party JS).

**Mode.** Redesign, preserve. The skill's default stack (React, Tailwind, Motion) is set aside
by its own "one system per project" rule, as both earlier bench plans record.

**What is different from the forge, in one line:** the forge is about **heat and assembly**; the
circle is about **sequence, fit and timing**. A smith reads the colour of the metal; an enchanter
reads where each essence wants to sit and when the light crests. So the stage gets a **circle and
a candle ring** instead of a hearth, and the right column becomes **the working**: the vessel,
its seats, what it can hold, and what it costs.

| Surface | VARIANCE | MOTION | DENSITY | Why |
|---|---|---|---|---|
| **Stage** (circle, candles, vessel, essence glow, games) | 6 | **7** | 2 | The boldness lives here: chalk lines drawing on, candles guttering, essence light pouring into the work. One step calmer than the forge's sparks: a ritual, not a forge. |
| **Chrome** (shelf, method strip, the working, footer, In progress) | 4 | **3** | 6 | Matches the table and both benches. Hover and press feedback only. |

**Where the boldness is spent:** the moment of binding, when the candle ring's light runs around
the circle and into the item. Everything around it is quiet.

---

## 1. Decisions that bind this plan

| Question | Owner's answer (2026-10-05) |
|---|---|
| Bench | **Its own bench, built from the shared parts** (`29-bench-core.js`). |
| Stage | **The item on a circle of chalk and inks, lit by candles and the essence's glow.** |
| Minigames | **Order, matching and timed windows.** No freehand drawing. |
| Modes | **One craft**: a catalogue item is a known recipe; free-form binding on the same bench. No second tab. |
| In progress | **A section for every craft** where unfinished work sits with countdowns on game time until collected (leatherworking Q9.3). Built here as a shared panel (§6.10). |
| Old tab | The forge and herb precedent: `/craft/` Enchanting becomes a card that opens the bench (owner rulings Q8.4 for leather, applied the same way). |

**Carried over from the herb and forge benches:** the full-screen layer over the table (z 35),
`BenchCore.mount` for the layer, focus, Esc, keys, clock and footer; the method strip; the d20
throw and the brass verdict word (`BenchCore.rollD20`); the minigame strip with Steady mode; the
quality ladder on a paper tag; the perk picker (`BenchPerks`, a new track row); app-wide sound;
the one-second rule; render on demand.

---

## 2. Audit of today's Enchanting tab (from the code)

**What is there** (`play/templates/play/craft.html`, inline JS, 1,415 lines):
- The `/craft/` page's Enchanting tab still uses the **old chain bench**: a shelf of all 117
  materials with emoji glyphs (`enchanter.KIND_GLYPH`: ✨ 💎 🖋️ 🜏 ⭐ 🔮 📿 🧿, and 🪄 🧿 📿 for
  the book mode), method station buttons that build a chain, a free-text **Shaping** field, a
  footer with Craft, batch, Save recipe and the mastery line.
- A second row of **mode** buttons (`renderModes`, craft.html:670-684): "the circle" and "By the
  book", two crafts on one track.
- The preview and craft posts send `item: SHAPE`, the Shaping text (craft.html:1118-1120,
  1289-1292). With no shapes declared for the Enchanter the page sends `""`, the server reads
  `{}`, and **every essence binding is refused "not masterwork"** (revamp plan §1).

**Keep:** reasons in words (the refusal grammar of `docs/enchanting.md`, "A quartz cannot hold a
storm", is good copy); the itemised check terms; the mishap line printed before the roll (now the
curse line); the tooled panels and clasps; Cinzel.

**Retire on the bench:** the emoji glyphs; the mode row (one craft now); the free-text Shaping
field (a vessel is picked from the rack, never typed); the all-materials wall; the station grid;
the method names nobody's code enforced (scribe, focus, channel, seal, imbue, empower, awaken).

---

## 3. What is reused, and what is new

Measured line counts (lane recon, 2026-10-05):

| Module | Lines | Reuse |
|---|---|---|
| `29-bench-core.js` | 662 | **As is.** `BenchCore.mount` with enchant ids; `rollD20`, `confirm`, `turnClock`, `fly`, `word`, `dim`, `minutes`, `span`. |
| `33-bench-games.js` | 1,195 | **As is**, plus registration of the enchant games (`track: "enchant"`), and one optional strip part: the **hour band** (§6.4), as the forge added the heat gauge. |
| `34-bench-tag.js` | 246 | As is: the binding's ladder. |
| `36-bench-perks.js` | 333 | One new `TRACKS` row: `enchanter`, prefix `enchant`, route `/api/enchant/perks`, perks potency, quality, yield, capacity. |
| `bench-stage/00-04` | 1,349 | **As is**: maths, renderer, meshes, grounds (`planks`, `rock`, the biomes), particles (`glint`, `ember`, `smoke`, `drop`). |
| `forge-stage/02-families.js` | 532 | **Reused** to build a forged vessel from its pieces on the circle, in its own material colours. |
| `forge-stage/03-smithy.js` | 163 | The stone-flag floor painter reused for a sanctum floor. |
| `40-forge-shell.js` | 1,085 | The pattern (mount, load, check, roll, game, finish, land), not the file. |
| `44-forge-ledger.js` | 699 | Hard-wired to the forge; the enchanter gets its own ledger file on the same pattern. |
| `31-bench-satchel.js` | 272 | Its Steeping group becomes a generic **In progress** group fed by the shared rows (§6.10). |

**New:** `45-enchant-shell.js`, `46-enchant-shelf.js`, `47-enchant-stage.js` (adapter),
`48-enchant-working.js`, `49-enchant-ledger.js`; `37-works.js` (the shared In-progress panel,
after the bench core it uses); `enchant-games/*.js`; `enchant-stage/*.js`; `enchant.css`,
`works.css`.

---

## 4. Tokens

**No new colours, fonts or textures.** The bench maps onto the bench's semantic layer, as the
forge does (`bench.css:19-30`, `forge.css:19-22`):

```css
.enchant {
  --bench-satchel-w: 280px;
  --bench-tag-w: 360px;            /* the working column carries seats and the cost line */
  /* inherits --bench-ground var(--sunk), --bench-ink var(--ink), --bench-quiet var(--dim),
     --bench-accent var(--gold), --bench-warn var(--alarm), --bench-light var(--candle),
     --bench-radius 3px from .bench */
}
```

**Essence colour is content, not chrome.** Each essence's `color` (from its document, revamp plan
§7.2) appears **only in the 3D scene, on the hour band's planet mark, and as an 8px swatch beside
the essence's name**, the forge's rule for heat and metal swatches. Chrome stays gold. **Chalk
white** is the circle's colour in the scene and nowhere else.

**The curse warning** uses `--alarm` in words only ("Miss by 5 or more: it takes, flawed, with a
hidden curse"), never a red panel.

**Quality** reads by metal and weight on the paper tag (Crude `--ash` ... Flawless `--gilt`), the
name always in words.

**Planet signs.** The seven classical planet symbols (☉ ☽ ♂ ☿ ♃ ♀ ♄) are Unicode
astronomical symbols, not emoji, but ♀ and ♂ render as emoji on some systems. They are set with
the text presentation selector (U+FE0E) and `font-variant-emoji: text`, always beside the
planet's name, and a test pins that none renders as an emoji glyph in the packaged app
**(proposed; if it fails in Electron, they become icons, Q-UI2)**.

**Icons** from game-icons.net (CC BY 3.0, credited in About, the manual and
`docs/asset-licences.md`), as gilt masks. About 26 new, **download to be approved** as the forge's
were (Q-UI1):

| Group | Icons |
|---|---|
| Methods | prepare (chalk circle), attune (linked rings), bind (knotwork), refine (dropper), unbind (broken chain), cleanse (sun rays), read (eye), identify (magnifier and sparkle) |
| Forms | essence phial, mote, chalk, salt bowl, ink pot, gem (focus), catalyst pouch, candle, ring, amulet, circlet, cloak, boots, belt, gloves, bracers |
| States | prepared, attuned, flawed (a cracked gem), unidentified (a veiled eye), in progress (hourglass), ready (an open hand) |

---

## 5. Layout

### 5.1 The layer

`#enchant`, `class="bench enchant"`, `role="dialog"`, `aria-modal="true"`, z 35, mounted through
`BenchCore.mount` (hash `#enchant`, `openWith "[data-enchant-open]"`). Opens from an
**Enchanting** button in the left column beside Herbalism and Smithing (`#side-who`,
`table.html:3436-3445`), and from the `/craft/` card.

### 5.2 Desktop grid, 1600×900

```
┌ #enchant ───────────────────────────────────────────────────────────────────────────────────┐
│ Enchanting  [Prepare][Attune][Bind][Refine][Unbind][Cleanse][Read][Identify]        [Close]  │ 56px
├ shelf 280px ─────┬─ stage, minmax(600px, 1fr) ───────────────────┬─ the working 360px ──────┤
│ Search the shelf │                                                │ Vessel                  │
│ [What fits ▾]    │      candles on the ring, the chalk circle,    │  ▣ Cold iron longsword  │
│ Vessels          │      the longsword at its centre               │    Superior · holds +8  │
│  ▣ Cold iron ... │                                                │ Seats                   │
│  ▣ Wolf cloak    │      essence phials on the circle's rim,       │  point  ◇ Flaming  ♂    │
│ Essences         │      each glowing its own colour               │  edge   ◇ Arcane I      │
│  ▣● Flaming   2  │                                                │  guard  ◇ empty         │
│  ▣● Arcane I  3  │ ┌ minigame strip ──────────────────────────────┐ │ Holds  ◆◆◇◇◇◇◇◇ │ +10     │
│ Circle           │ │ HOUR ♂ Mars, 42 min left   Space at the crest│ │ +2 of +8               │
│  ▣ White chalk 4 │ └──────────────────────────────────────────────┘ │ Costs 60 motes         │
│  ▣ Silver ink  2 │ Bind. 64 hours of work: ready in 8 days.        │  40 for +2, 20 cold iron│
│ In progress (1)  │ DC 25, you need 17 or better.                   │ ┌ paper tag ──────────┐ │
│  ⧗ Wolf cloak    │ Miss by 1 to 4: it does not take. You keep them.│ │ +1 Flaming Longsword│ │
│    ready in 2 d  │ Miss by 5+: it takes, flawed, hidden curse.     │ │ ─ ladder ─ ceiling  │ │
│ Can't use now    │              [ Roll Bind ]                      │ └─────────────────────┘ │
├──────────────────┴────────────────────────────────────────────────┴─────────────────────────┤
│ Day 41, 9:18am   At camp   Enchanter 2 ──── 31 / 65   Recipes  Ledger  In progress  Steady ○ │ 44px
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

- **Grid:** `280px minmax(600px, 1fr) 360px`; rows `56px 1fr 44px`.
- **The working** (right) replaces the forge's work order: the vessel, its seats, what it holds,
  what it costs, then the paper tag.
- **The info block** under the stage carries the two failure lines **before** the roll, in words
  (revamp plan §4.4). They are not a footnote: the curse is the craft's only risk.
- **The footer** names where you are ("At camp" / "In your sanctum" / "At Ysolde's circle, 2 sp
  an hour").

### 5.3 Other sizes

As the forge (UI plan §5.3): the 3440×1440 ultrawide caps content at 2,000px with the floor
filling the width; 1280×720 narrows the shelf to 240px and the working to 320px and the method
strip goes to icons with names on hover and focus; under 1180px the stage stacks on top at 56vh;
under 768px a single column, every game with a tap form.

---

## 6. Components

### 6.1 Method strip

Eight methods in craft order: Prepare, Attune, Bind, Refine, Unbind, Cleanse, Read, Identify.
Locks show the reason in words: "Enchanter 2" or "Needs a sanctum". Keys 1-8 pick; arrows move.
The three ritual methods are shown as one path ("Prepare, then Attune, then Bind") by the
**Next: Attune** button that appears after each step, the herb bench's next-step pattern.

### 6.2 The shelf (left)

The herb satchel's pattern:
- Only what you **carry**, grouped: Vessels, Prepared and attuned (the intermediates, with their
  quality word), Essences, Circle (chalk, salt, ink, treatments), Gems, Catalysts,
  **In progress** (this craft's rows from §6.10), Can't use now.
- A row: engraved form icon, the essence swatch, name, count (phials track tenths after a Read:
  "Flaming essence 1.9"), rarity rim, state badges (prepared, attuned, flawed, unidentified), and
  a "?" while anything is unknown.
- **Vessels** show their quality and what they hold: "Cold iron longsword, Superior, holds +8"; a
  vessel below masterwork reads "Fine: not masterwork, so it takes no arms magic" under **Can't
  use now**.
- Hover, focus or "?" opens the **ledger card** (§6.8).
- **No scroll jump** (the forge audit's defect): rows re-render in place.

### 6.3 Stage

- **Composition:** the chalk circle on the floor at centre, the vessel lying at its heart (a ring
  or amulet on a small cloth), candles at the circle's quarters and between them, the essence
  phials at the rim on their seats, an ink pot and chalk at the near edge. Camera about 50°
  looking down into the circle.
- **Ground:** at camp, the biome ground (`03-ground.js`); roofed, planks; a sanctum, stone flags
  (`forge-stage/03-smithy.js`'s painter) with a worn rug under the circle **(proposed)**.
- **Light:** the shader has three point lights (`01-gl.js`): the **candle ring** is the key light
  at the circle's centre (warm `--candle`, a slow flicker only while a game is live); the
  **essence glow** is the second, coloured by the seated essence and brightening as the binding
  climbs; the **flare** is the bind flash. Individual candle flames are emissive meshes with
  soft-point halos, not lights, so no shader change is needed. Day and night fill from the scene
  clock, as the herb stage.
- **The vessel:** a forged one is built from its pieces by `forge-stage/02-families.js`, in its
  own metals; jewellery and leather vessels from new simple families (§7.3).
- **Info block** under the stage (§5.2), in plain words.
- **Roll Bind** (or Roll Prepare, Roll Attune) is the only gold-filled button, disabled with its
  reason beside it ("Seat an essence first").
- **WebGL fallback:** the engraved icon at 160px on the ground colour; every game runs in its 2D
  strip, as both benches.

### 6.4 Minigame strip

The shared frame (meter left, hint centre, live tier right, time thread on top). Enchanting adds
an optional **hour band** (the forge added the heat gauge the same way): a strip of the day's
hours with the current planetary hour outlined, the essence's planet marked by its sign and
name, and the words "Mars hour, 42 minutes left" or "Mars hour in 3 hours". It tells the player
why the windows are wide or narrow. Shape and words, not colour alone.

### 6.5 The working (right)

**Vessel** at the top: the picked vessel's icon, name, quality and "holds +8", with "× back to
the shelf".

**Seats** under it: one row per seat on this vessel (a blade: point, edge, guard; armour: breast,
back, shoulders; a ring: stone, band; a cloak: clasp, hem). Each seat shows its **sign** (planet,
polarity, affinity in words) and what is seated, or "empty". During Attune the seats are the
drop targets; outside it they are read-only. A seated essence that asks a choice shows it in the
row: **Bane against [Undead ▾]**, **Resist [Fire ▾]**, listing only the engine's options.

**Holds**: ten pips for the book's +10 with the vessel's capacity marked by a notch and the
taken pips filled, "+2 of +8". Pips, not a filled track (the skill's ban), and the numbers in
words beside them. Gold-priced abilities listed under it ("Shadow, outside the +10").

**Costs**: the motes line and its parts in words ("40 for the +2, 20 for cold iron"), and the
time ("64 hours of work: ready in 8 days").

Then the **paper tag** (`34-bench-tag.js`): the product's name, the ladder with your ceiling,
and the ceiling Prepare and Attune set ("Prepared at Fine: Bind can reach Superior").

### 6.6 The item card's magic section

On the character sheet, the inventory and the shelf, an item with a layer gets a section under
the forge's build card: **+1, flaming (+1 equivalent), on a Superior cold iron longsword; caster
level 10; moderate aura**, each property in words with its book line ("+1d6 fire on a hit"), the
house top-ups with "from the binding, Fine", and its powers with uses left. An unidentified item
reads "Magic, moderate aura" and offers **Identify**. A maker's own item reads as intended with
"not identified" under it until its curse question is settled (revamp plan §12.4). The card never
shows a number the engine does not apply.

### 6.7 Identify and Read

**Identify** from the item card or the bench: one roll on the dice mat, then a card with the
graded result in words: "You learn what it was made to do" and the properties, or "You see the
curse in it too" with the curse named, or "Nothing yet. You can try again tomorrow." **Read** on a
`volatile` essence opens a confirm in `--alarm` words: "This essence bites the one who reads it.
Read it anyway?" **Read it** / **Keep it**.

### 6.8 The ledger card and the Journal ledger

The forge ledger's pattern for essences and recipes: icon and swatch, name, where it is found or
bought, known traits and how each was learned ("read, day 14", "seated, day 20", "taught by
Ysolde"), one line per unknown, and **Read** (a pinch, 10 minutes), **Ask an enchanter** (when one
is in the scene). Recipes known appear as a list under **Recipes** in the footer: loading one sets
up the vessel and seats; you still roll and play (herbalism §9.6). The Journal gains an "Essences
and recipes" section beside the herbarium and the materials ledger.

### 6.9 Footer, perks, settings

`BenchCore`'s footer: clock, place line, Enchanter level and mastery line, Recipes, Ledger,
**In progress** (opens §6.10), Steady mode. The perk picker is `BenchPerks` with the enchanter's
row. Settings gains an **Enchanting** volume beside Bench and Forge.

### 6.10 The In-progress panel (shared, every craft)

The owner's cross-craft section. One panel, opened from:
- a fourth door in the left column under Herbalism, Smithing, Enchanting: **In progress**, with
  the count of ready work in words when there is any ("In progress, 1 ready");
- the **In progress** button in every bench's footer;
- each bench's shelf shows only its own craft's rows in its **In progress** group, with the same
  countdown words.

```
┌ In progress ─────────────────────────────── [Close] ┐
│ Ready to collect                                    │
│  ▣ Tincture of feverfew       Ready since day 40    │
│    carried                         [ Collect ]      │
│ Working                                             │
│  ▣ +1 flaming longsword       ◔ ready in 6 days     │
│    carried, binding                 day 47, morning │
│  ▣ Wolf hide in the vat       ◑ ready in 2 days     │
│    at Brannoc's tannery    Collect at the tannery   │
└─────────────────────────────────────────────────────┘
```

- **Grouped by state, not craft**: Ready first, then Working sorted by soonest (what players built
  for Stardew themselves, revamp plan §15.2). Each row carries the craft's icon so the craft still
  reads at a glance.
- **A row:** item icon, name, where ("carried", "at Brannoc's tannery"), the countdown in words
  ("ready in 6 days", with the day and part of day under it), and a small **arc dial** for the
  fraction elapsed (a circle, the shape lock's exception for dials; no filled track).
- **Collect** is the row's one action, gold only on a ready row at hand. Away from the place it is
  replaced by the reason in words, "Collect at the tannery".
- **Stop** sits in the row's menu and always confirms with the craft's own consequence ("Stop the
  binding? The vessel comes back unenchanted. The essences are spent.").
- **Countdowns move with game time, never real time.** The rows come computed from the server
  (`ready_in` from the scene clock); the panel re-renders whenever the table's state updates or
  `BenchCore.turnClock` turns the clock. No `setInterval` anywhere.
- **Ready** lands as a tell in the log ("Your +1 flaming longsword is ready to collect"), the
  door's count updates, and nothing pops over play.
- **Empty state:** "Nothing is working. Steeping jars, bindings and hides in the vat wait here
  until they are ready." No button: the benches start work.
- **Collect** plays the bench's land flourish into the shelf row when a bench is open, or a quiet
  highlight of the inventory row when not.
- A non-modal panel (`role="dialog"`, `aria-modal="false"`) at z 34, under the bench layers,
  focus-returned to its opener on close, Esc closes it.

---

## 7. The 3D stage

### 7.1 What is built new

Under `play/static/js/enchant-stage/`, on `window.EnchantStageKit`, reusing `BenchStageKit` and
`ForgeStageKit.families`:

| File | Contents |
|---|---|
| `00-circle.js` | The chalk circle painted onto a ground canvas the way `03-ground.js` paints grounds: an outer and inner ring, the quarter marks, salt at the quarters, and the sigils cut in sequence, each stroke drawn on as Prepare's game scores it. Sigils come from a fixed rune set (Elder Futhark shapes, public domain), **never drawn by the player**. |
| `01-props.js` | Candles (lathe meshes with emissive flame and a soft halo), candle stubs as they burn down over a long working, phials, ink pot, chalk, salt bowl, a silvered bell, a small cloth for jewellery. Low-poly, built in code. |
| `02-vessels.js` | The families the forge has none of: ring (a torus with a gem socket), amulet (a disc on a chain), circlet, cloak (a folded drape), boots, belt, gloves, bracers. Forged weapons and armour come from `forge-stage/02-families.js`. |
| `03-room.js` | The sanctum floor (stone flags, a rug), a lectern and a shelf at the back; camp and roofed scenes reuse the grounds. |
| `04-fx.js` | Essence motes rising from a phial, the stream into the vessel on Bind, the light running around the candle ring, the bind flash, the cooled sigils fading to a faint scored line, smoke from a snuffed candle. Through `04-particles.js`. |

Adapter `47-enchant-stage.js`, global `window.EnchantStage`, mirroring `ForgeStage`:
`available() mount(host) unmount() setScene({kind: "camp"|"roofed"|"sanctum"|"hired", biome,
roofed, minute}) setTool(method) setVessel({gear, base, pieces, family, quality_index})
setSeats([{seat, essence, color, planet, seated}]) hour({planet, inside, minutes_left})
game(method) flourish(kind) productRect() reducedMotion(bool)`. Without WebGL every call is a
no-op and `available()` is false.

### 7.2 The circle as feedback

The circle is the progress of the ritual, drawn, not a meter:
- **Prepare** draws the rings and cuts the sigils one by one, as the order game places them; a
  wrong pick scuffs the chalk (a short smudge) and the right one redraws it clean.
- **Attune** lights each seat's mark in the essence's colour as it is matched; an unmatched
  seat's mark stays dull chalk.
- **Bind** runs the candle light around the ring toward the crest and pours the essence's glow
  into the vessel on each good press; at the end the sigils flash and cool.
- **Flawed** (a Bind missed by 5+): one candle gutters out and the glow settles a shade darker.
  It says something went wrong without saying what, which is the curse rule (revamp plan §11.1).

### 7.3 Performance

Render on demand, as both stages (`wake` the only `requestAnimationFrame` site). The candle
flicker would keep the loop alive, so it runs **only while a game is live**; idle, the candles are
lit steadily and the bench draws no frames. A test pins zero frames over 10 idle seconds, as both
earlier plans.

---

## 8. Copy

Plain, in-world, sentence case, **no em-dashes or en-dashes in new strings** (both benches' rule;
the lane greps for them).

| Label | Intent |
|---|---|
| Roll Prepare / Roll Attune / Roll Bind | start a step |
| Hurry it | the Bind toggle: half the time, +5 DC |
| Wait for the hour | advance the clock to the essence's planetary hour |
| Read / Read it / Keep it | learn an essence's trait |
| Identify | the graded check |
| Unbind / Unbind it | disenchant, after a confirm |
| Collect | take finished work from In progress |
| Stop | end work in progress, after a confirm |
| Ask an enchanter | learn from a keeper |
| Close | leave the bench |

Reasons keep `docs/enchanting.md`'s grammar: "Fine work is not masterwork: arms magic needs a
Superior vessel", "The circle is white chalk: it holds nothing rarer than uncommon", "Ghost
residue binds only by night, or in the Moon's hour", "This sword holds +8 and the working asks
+9", "You neither know Flame Blade nor carry a potion of it: +5 to the DC".

Verdict words: **SUCCESS**, **FAILURE**, and **FLAWED** for a Bind missed by 5 or more (revamp
plan §11.1), with the line "It took, but something went wrong in the binding."

---

## 9. Minigames

Rules in the revamp plan §10. Every game: mouse, keyboard, Steady mode, a 2-second first-time
card, generous to start (the forge sweep's strongest finding: every smithing game was softened
after launch), 5-8 seconds **(proposed)**, score 0..1 to the server, the server names the tier.

| Game | On the stage | In the strip | Mouse | Keyboard | Steady mode |
|---|---|---|---|---|---|
| **Prepare** (order) | The rings draw on; then the sigils, one per beat, as you pick the right piece: chalk, salt, then the inks in the order the shown sequence names; a **test** step (tap the bell) before sealing, Hávamál's *freista*. | The sequence as a row of glyph slots, the next one outlined; the pieces as buttons below it. | click the next piece | 1-6 pick a piece, Space places | no timer; a wrong pick costs half as much |
| **Attune** (matching) | Phials float at the rim; each seat on the vessel shows its sign. Drop each essence on the seat whose sign it answers; a right match lights the seat in the essence's colour. An unknown essence shows its sign when picked up (translate by use). | The seats with their signs in words; a match meter. | drag a phial to a seat, or click phial then seat | arrows choose, Enter seats, Backspace lifts | no timer; signs repeated in words beside every seat |
| **Bind** (timed windows) | Light runs round the candle ring toward the vessel; press as it crests at the vessel. Four to six crests. In the essence's planetary hour the crest is wider (the hour band says so). | The hour band; a crest ring per bind. | click at the crest | Space | windows ×1.6, the light ×0.5 speed |
| **Refine** (diminishing draws) | Draw the essence up the dropper from its source; each draw is paler than the last; press at the bubble's crest to draw clean; stop when you choose (Cennini's ultramarine). | Draw pips, each paler; purity meter; **Stop drawing**. | click at the crest; Stop | Space; S stops | crest ×1.6; no pressure to stop |
| **Unbind** (order, reversed) | The item's sigils glow; unpick them last-cut first; each unpicked one fades and its essence mist rises. | The sigil sequence shown reversed, next outlined. | click the next sigil | arrows and Space | no timer |
| **Cleanse** (order) | Only the curse's sigils glow, in a darker line among the rest; unpick those, leave the others. | The curse's sequence only. | click | arrows and Space | no timer; wrong sigils are refused, not scored |

**Read and Identify have no minigame** (tasting and assay have none): a short animation (the eye
over the phial; the magnifier over the item's sigils), then the result in words.

**No game depends on the cursor art.** Each draws its own reticle, as both benches' games do.
**No freehand drawing anywhere** (Arx Fatalis; the owner's ruling): the player picks, drops and
times; the circle draws itself.

---

## 10. Motion and juice

Every animation has a reason (feedback, state change, hierarchy). Short and reduced-motion forms
throughout.

| Event | Stage | Chrome | Reduced motion / Short |
|---|---|---|---|
| Open the bench | the candles light one by one round the circle (600ms) | layer fade 200ms | all lit at once, fade only |
| Switch method | the tools on the near edge swap (450ms) | strip underline slides 160ms | crossfade 120ms |
| Pick a vessel | it is laid at the circle's centre | the Vessel row fills | row fills, no arc |
| Seat an essence | the phial settles on its seat, the seat lights | the Seat row fills | row fills |
| A good press (Bind) | light pours into the vessel, a bell tone, 1° camera nudge 60ms | the pip fills | pip and tone only |
| A miss | the light falls short and fades | none | same, no motion |
| Tier up | the vessel glints | the ladder rung brightens 180ms | instant |
| Flawless | the brass word over the circle, gilt motes, 250ms stage-canvas shake | none | the word only |
| Flawed | one candle gutters out; the glow settles darker | the verdict word FLAWED | the word only |
| Into In progress | the vessel wraps in its cloth and flies to the shelf's In progress group (500ms) | the row pulses once | the row highlights |
| Collect | from the In progress row to its shelf or inventory row | the row pulses | highlight |

**The one-second rule** holds: flourishes run in `#rv-layer` with `pointer-events: none`; any
click skips them; the shelf, the working and Close stay live.

---

## 11. Sound

On the app-wide buses, a new **enchant** bus (three files: `BUSES` and `BUS_PREF` in
`sound.js`, the default in `prefs.js`, the slider in `home.html`), synthesised like the forge's:
- `enchant.open`, `enchant.method.<name>`, `enchant.roll`;
- `enchant.chalk` (a dry scrape per sigil), `enchant.salt`, `enchant.ink`, `enchant.bell` (the
  test step);
- `enchant.seat` with **pitch by planet** (Saturn lowest, the Moon highest), `enchant.unseat`;
- `enchant.bind.hit` (a struck bell), `enchant.bind.miss` (a muffled one); `enchant.miss`, the
  same muffled bowl under the name every circle game's miss rings (final pass, 2026-10-06);
- `enchant.draw`, `enchant.unpick`;
- `enchant.tier.up`, `enchant.flawless`, `enchant.flawed` (a bell slightly off its note), `enchant.fail`,
  `enchant.land`, `enchant.read`, `enchant.identify`;
- `works.ready` (a soft chime when work becomes ready), `works.collect`;
- `ambience.sanctum` (a still room, a candle's hiss) or the biome ambience at camp.

---

## 12. Engineering shape

**Files:**
- `play/static/js/table/45-enchant-shell.js` (mount, load, check, roll, game, finish, land),
  `46-enchant-shelf.js`, `47-enchant-stage.js` (adapter), `48-enchant-working.js` (vessel,
  seats, holds, costs, tag, item card section), `49-enchant-ledger.js`.
- `play/static/js/table/37-works.js`: the shared In-progress panel and the shelf group renderer
  (`window.Works = {open, close, rows(craft), group(host, craft), isOpen}`), used by every bench.
- `play/static/js/enchant-games/*.js`: prepare, attune, bind, refine, unbind, cleanse.
- `play/static/js/enchant-stage/*.js`: §7.1.
- `play/static/css/enchant.css` (after `bench.css`), `works.css`; existing tokens only.
- `play/enchant_views.py` and `play/works_views.py`, routes **above** any catch-all (the herb
  bench's route-order bug, `test_bench_routes`, is not repeated).

**The server contract** (the three laws): the page sends the method, the vessel key, the essence
per seat, any choice from the server's own list, the circle materials, hurry, and the game score
0..1. The server answers with the tier, the product, its **computed layer** (every number on the
card), the motes and time, the mastery lines, discoveries and the time passed. **The page never
computes a number**, including the holds pips, the motes and the countdowns.

**Lazy loading:** the enchant chunk and its stage load on first open, not on the table's first
paint (the forge's still-open point 1 is not repeated here).

---

## 13. Verification (before it is called done)

1. **Live, on scratch data** (`PATHFINDER_GM_DATA`), every method at 1280×720, 1600×900,
   1920×1080, 3440×1440 and under 1180px, at camp, roofed and in a sanctum. Screenshots in the
   lane report.
2. **Reduced motion and Steady mode:** every game playable; the candles do not flicker; no shake.
3. **Keyboard only:** open, pick a vessel, prepare, attune with a choice, bind, collect, close.
4. **Contrast:** dimmed shelf rows, reasons, the failure lines, the tag, the holds pips and the
   In-progress rows, measured against their real backgrounds, AA.
5. **The one-second test** and **idle zero frames**, including the candles.
6. **End to end in play** (the path the player clicks): forge a Superior cold iron longsword,
   enchant it +1 bane (undead) at the bench, wait out the countdown, collect it from In progress,
   wield it, hit a skeleton (DR 5/bludgeoning) and a ghost, and read the +2d6, the magic trait
   and the incorporeal half in the combat log. Then miss a Bind by 5+ on scratch data, see FLAWED,
   identify by 10, read the curse.
7. **The In-progress section across crafts:** a steeping tincture and a binding side by side,
   advance time across one ready minute, collect one, stop the other.
8. **Packaged build:** open the bench and the In-progress panel in `win-unpacked` on a throwaway
   data dir.

---

## 14. Pre-flight (the skill's matrix)

| Check | Status |
|---|---|
| Brief read and dials | §0, split by surface |
| Redesign audit | §2, from code; live repeat in U1 |
| Zero em-dashes and en-dashes in new strings | §8; the lane greps |
| One theme, one accent | dark; gold only. Essence colour, chalk and candlelight are scene content (§4) |
| Shape lock | 3px; circles only for dials, seats, pips and swatches |
| Button contrast, no CTA wraps | Roll Bind, Collect: one or two words |
| Labels above fields | the shelf search; choice selects labelled in their seat row |
| No eyebrows; plain group headings | §6.2, §6.10 |
| One label per intent | §8 (Collect everywhere; never "Claim" or "Take") |
| Motion motivated, reduced motion | §10 |
| No idle loop, no real-time timer | §7.3; §6.10 |
| Empty, loading, error states | §6.2, §6.10, the herb plan §7 |
| No filled-track progress bars | holds are pips; countdowns are words and an arc dial |
| Icons from a library | game-icons.net, credited; planet signs as text glyphs with names (§4) |
| No emoji | retired (§2); planet signs forced to text presentation |
| z-index | bench layers 35; In-progress panel 34 |
| Mobile collapse | §5.3; the In-progress panel becomes a full-width sheet under 768px |

---

## 15. Build order

| # | Lane | Contents | Depends on |
|---|---|---|---|
| U1 | **Enchant shell, flat** | the layer through `BenchCore.mount`, method strip with level and place locks, the shelf, the working (vessel, seats with choices, holds, costs, tag), the failure lines, Roll and the d20 with FLAWED, results into In progress, the item card's magic section; live audit of the old tab first. **Playable end to end before any 3D.** | rules lane E's API |
| U2 | **Games** | the six games on the shared frame, the hour band, Steady mode | U1 |
| U3 | **Stage** | `enchant-stage/`, the circle, candles, vessels (forge families reused), fx | U1 (parallel with U2) |
| U4 | **In progress** | `37-works.js`, `works.css`, the left-column door, every bench's shelf group (herb Steeping becomes it), the footer buttons | rules lane G's API |
| U5 | **Ledger, identify, perks** | ledger card, Journal section, Read and Identify cards, `BenchPerks` row | rules lane F |
| U6 | **Sound** | the enchant bus and its events, `works.*` | U2 |
| U7 | **The old tab** | `/craft/` Enchanting becomes the card that opens the bench; the mode row removed | U1 |

**Why this order** is both benches': a flat, working bench first, so the rules lanes are checked in
the real UI before any modelling; the minigames are where tuning happens, and tuning on a flat
build is cheapest. U4 does not wait on enchanting at all: herbalism's jars use it the day it lands.

---

## 16. Open points for the owner (UI)

1. **Q-UI1. Icons:** download about 26 game-icons.net icons (CC BY 3.0, credited as before)?
2. **Q-UI2. Planet signs:** text glyphs with the text presentation selector (taken), or icons if
   any renders as an emoji in the packaged app.
3. **Q-UI3. The In-progress door:** a fourth button in the left column (taken), or only from the
   benches' footers and the inventory.
4. **Q-UI4. Sanctum look:** stone flags and a rug (taken), or the founded place's own floor as the
   forge does for an owned smithy.

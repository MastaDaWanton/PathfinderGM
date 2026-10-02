# Herbalism bench: the UI plan

Drafted 2026-10-02. This is the interface half of `docs/herbalism-revamp-plan.md`; the rules,
numbers and lanes live there. The owner asked for it to be designed with the
`design-taste-frontend` skill, so the skill's process, rules and pre-flight check shape this
document. §0 says where the skill fits and where it does not.

Sources consulted:
- the audit of today's bench, done in the running app on scratch data at 1600×900 (§2);
- `docs/herbalism-prior-art.md`;
- three new references on crafting screens:
  - [Potion Craft and its lovingly well-crafted UI](https://medium.com/@saragiraltfdez/potion-craft-and-its-lovingly-well-crafted-ui-57670cec4e13): the interface is drawn in the same style as the world, and grinding is done by dragging into the mortar and working the pestle with the mouse;
  - [KCD2 alchemy guide](https://deltiasgaming.com/alchemy-guide-for-kingdom-come-deliverance-2/): bases on a shelf to the left and the recipe book to the right, as objects on the bench;
  - [Andersson, *Effects of Diegetic User Interface on Immersion*](https://www.theseus.fi/bitstream/handle/10024/862563/Andersson_Roni.pdf?sequence=2&isAllowed=y): players rated the diegetic version more immersive but **enjoyed the non-diegetic one more**, for its simplicity.

  That last finding is why this plan is a hybrid. The tool and its ground are in the world; the
  numbers, reasons and ladder are plain, readable interface.

---

## 0. Design read, dials, and how the skill applies

**Design read.** This is a redesign of an in-game crafting workbench, a desktop game screen. The
user is a solo Pathfinder player who wants the craft to feel tactile and rewarding. The design
language is the app's own dark leather, brass and candlelight, built with vanilla JS, the
existing `theme-v2.css` tokens, and three.js for the stage.

**Mode.** *Redesign, preserve* (skill §11). The owner's standing instruction is to keep colours,
images and textures unchanged and to use the design skills for UI work. The look stays; the
bench's structure and behaviour change.

**Where the skill applies and where it does not.** The skill is written for landing pages, and
its §13 marks dense product UI as out of scope. This plan uses what carries over:
- the brief read and dials;
- the redesign audit;
- the colour, shape and theme locks;
- the anti-tell list;
- the motion rules ("motion must be motivated", reduced motion, transform and opacity only, no
  scroll listeners);
- the accessibility checks (button, form and dimmed-text contrast);
- the z-index discipline;
- the empty, loading and error states;
- the zero em-dash rule, applied to every new string on the bench;
- the pre-flight matrix, adapted in §14.

It sets aside the skill's default stack. React, Tailwind, Motion, `next/font` and the
Phosphor/Tabler icon defaults are all out, by the skill's own "one system per project" rule:
this app is Django templates and numbered vanilla modules in `play/static/js/table/`, and
adding a framework for one screen would be a second system. The skill's §10 rule
"never mix Three.js with Motion in the same tree" is honoured because there is no Motion here
at all: chrome motion is CSS, and stage motion is three.js.

**The dials are split by surface.** One set for the whole bench would be wrong. The owner wants
"big and juicy" on the tool, and their standing instruction is "no motion that hinders menus" on
everything around it.

| Surface | VARIANCE | MOTION | DENSITY | Why |
|---|---|---|---|---|
| **Stage** (tool, ground, minigame, flourishes) | 6 | **8** | 2 | The owner chose "big and juicy". The stage is the one place the boldness is spent (frontend-design: "spend your boldness in one place"). |
| **Chrome** (satchel, method strip, tag, footer) | 4 | **3** | 6 | This matches the table's existing panels, with MOTION +0 from the current ~3: hover and press feedback only, and nothing moves on its own. Density stays high because a herbalist's satchel is a list of many things. |

---

## 1. Decisions that bind this plan

**From this round (2026-10-02):**

| Question | Owner's answer |
|---|---|
| Layout | **Stage first.** The 3D tool on its ground takes the middle. The satchel is narrow on the left, the result tag on the right, and the minigame rises from the bottom of the stage. |
| Where it opens | **Over the table**, as a full-screen layer. Closing it returns you to where you were. The stage clock shows scene time passing, and the ground is the scene you stand in. |
| Herb art | **Engraved icons only**, one brass icon per kind and part. |
| Other crafts | **The old bench stays** for Alchemy, Blacksmithing, Leatherworking and Enchanting until each is revamped. |

**Carried over from the revamp plan:**
- 3D tools with a flat UI;
- a wild forager's camp;
- big, juicy feedback that never holds a menu for more than one second;
- mouse, keyboard and Steady mode for every game;
- always play the minigame, with bulk stacks sharing one tier;
- the herbarium shown on hover at the bench and in the Journal;
- recipes that load the bench but still make you play;
- app-wide sound;
- the quality ladder Crude, Sound, Fine, Superior, Flawless, then +1, +2 and so on, with the
  ceiling set by level.

---

## 2. Audit of today's bench (skill §11.B)

Looked at live, on scratch data at 1600×900, with Acacia put through Grind and Brew.

**The current page.** Today `/craft/` is a separate page with five craft tabs (Herbalism,
Alchemy, Blacksmithing, Leatherworking, Enchanting) across three panels:
- **Ingredients:** a forage card, a search box, an "Only what I am carrying" toggle, then *every*
  ingredient in the game as jar tiles with emoji glyphs.
- **Crafting Chain:** eleven method stations in a grid, the chain row, a free-text "Shaping"
  input, and a small cauldron.
- **Preview:** a green name banner, a stats table, "Cannot be made", the effects, and "What the
  source says".

A footer bar holds **Craft**, **Save recipe** and the mastery bar. From the table, the
left-column link "Crafting bench" opens it, and the table also has a separate **Craft action**
panel for foraging.

**Tokens to preserve** (from `theme-v2.css` and `craft.html`):

| Role | Tokens |
|---|---|
| Fonts | `--display` Cinzel in small caps; `--body` Palatino |
| Surfaces | `--bg #0d0b09`, `--panel #161210`, `--sunk #0b0908`, `--edge #3a2f22` |
| Text | `--ink #e8ddc4`, `--dim #93866e`, `--ash #6d675e` |
| The one accent | `--gold #ddc48e`, `--accent #cfa964`, `--gold-dim #7d6845`, with `--gilt` |
| Alarm | `--alarm #b0483c` |
| Light | `--candle #f0c070` and `--ember` |
| Textures | `--tex-side-leather` (tooled panels), `--tex-card-leather`, `--tex-page-paper`, `--brass-grain` |
| Metalwork | the four clasps and four bosses |
| Bevels | `--bevel`, `--emboss`, `--sunken`, `--engraved` |
| Radius | **3px** everywhere |

**Patterns to preserve:**
- the tooled-leather panels with clasps;
- Cinzel small-caps headings;
- the reasons given in words ("You have no Acacia. Forage for it.");
- the itemised mastery line;
- the itemised check terms;
- search and filter on the shelf;
- "What the source says";
- the 0.2.3 d20 throw and the brass verdict word;
- the candle cursor. The skill bans custom cursors, but it is the owner's look, and preservation
  wins. §9.4 makes sure no precision game depends on where its hotspot is.

**Patterns to retire, on the herbalism bench only:**

| Pattern | Why it goes |
|---|---|
| Emoji glyphs | They read as placeholders, render differently on each OS, and the skill marks them as a tell. |
| The green `--brew` banner | It is a second accent, which breaks the colour lock. Liquid colour lives *inside* the 3D scene as content, never on the chrome. |
| The eleven-station grid | It makes a chain look like a spreadsheet, and five of its methods are gone. |
| The free-text "Shaping" box | A free-text field for something the engine names. |
| The full 161-ingredient shelf | It shows herbs you don't carry and properties you don't know, which breaks discovery. |
| The tiny cauldron | It was a placeholder for the stage. |

**Dial reading of today:** VARIANCE 3 (three equal panels), MOTION 2, DENSITY 6.

---

## 3. Token system for the bench

No new colours, fonts or textures. The only new token set is the bench's semantic layer, which
maps onto existing tokens:

```css
.bench {
  --bench-ground: var(--sunk);
  --bench-ink: var(--ink);
  --bench-quiet: var(--dim);
  --bench-accent: var(--gold);          /* the one accent: active method, Roll, ceiling */
  --bench-accent-deep: var(--gold-dim);
  --bench-warn: var(--alarm);           /* lost materials, danger on tasting */
  --bench-light: var(--candle);         /* stage light, ember glows */
  --bench-radius: 3px;                  /* shape lock: 3px, circles only for dials and dice */
}
```

**Quality is shown by metal and weight, never by hue.** Five hues would be five accents.

| Tier | Treatment |
|---|---|
| Crude | `--ash` text, no rim |
| Sound | `--dim` text, hairline `--edge` rim |
| Fine | `--ink` text, `--gold-dim` rim |
| Superior | `--gold` text, `--gold` rim, `--bevel` |
| Flawless (and +N) | `--gilt` fill on the label plate, `--engraved` text, and the +N in Cinzel numerals |

Every tier also carries its **name in words**, so colour is never the only signal (Game
Accessibility Guidelines; research §5).

**Type scale** (Palatino body at 16px, as now):

| Size | Use |
|---|---|
| 13px | reasons under tiles, hints, the footer |
| 15px | tile names, tag body |
| 18px | tag headings, method names |
| 24px Cinzel small caps | product name on the tag |
| 34px Cinzel | the live tier word under the minigame |

Numbers that tick (timers, scores, potency) use `font-variant-numeric: lining-nums tabular-nums`,
because Palatino's old-style figures jump as they change.

**Icons: engraved brass, from game-icons.net** (owner's choice). The skill's icon rule bans
hand-drawn SVG paths and wants a maintained library. game-icons.net is the maintained library for
fantasy objects (mortars, roots, glands, horns) that Phosphor and Tabler don't have.
- **Licence:** CC BY 3.0, so it needs attribution. Credits go in the app's About and the manual,
  each icon is recorded in `docs/asset-licences.md`, and the SVG files ship in
  `play/static/img/icons/`.
- **Rendering:** each SVG is used as a CSS `mask-image`, with `--gilt` behind it and a
  `drop-shadow` pair matching `--engraved`. That makes one set read as struck brass at any size.
- **Every leaf looking alike** is the cost the owner accepted. Tiles are told apart by name,
  rarity rim, state badge and count (§6.2), never by icon alone.
- **Icon set to confirm against the site's catalogue:**

  | Group | Icons |
  |---|---|
  | Parts | leaf, flower, root, bark, berry, seed, sap or resin, fungus, gland, organ, bone, horn, feather, scale, eye |
  | Methods | mortar, bowl, pot, drying rack, knife, crock, jar, dropper, pan |
  | States | dried, ground, neutralised, steeping |
  | Misc | lock, recipe book, taste, study |

**The z-index layers** (skill §6.F). They slot into the table's existing scale, read from
`table.html`: veil 20, popovers 30, deathveil 40, skip link 50, dice mat 60, verdict layer
65/66, gloss card 70.

| Layer | z |
|---|---|
| **Bench layer** | **35** |
| bench popovers (herbarium card, perk picker, confirms) | inside the layer's own stacking context |
| deathveil (tasting hemlock can kill you, and death must cover the bench) | 40 |
| dice mat (the Craft roll is thrown over the bench) | 60 |
| verdict word and flourishes (`#rv-layer`, reused) | 65/66 |

Every bench flourish runs in `#rv-layer` with `pointer-events: none`.

---

## 4. Layout

### 4.1 The layer

The bench opens over the table as a full-screen layer (`#bench`, `role="dialog"`,
`aria-modal="true"`). The table stays mounted underneath, so closing is instant and keeps your
place.

- **Opens from:** the left column's **Herbalism** button (new). "Crafting bench" stays as the
  route to the old bench for the other crafts. The table's **Craft action** panel gets a
  "Work at the bench" link too.
- **Closes on:** Esc, the Close button, or finishing a step and choosing Close. While a
  minigame is live, Esc asks "Stop and keep what you have?". Stopping scores the run so far, and
  materials are never lost to a stop (revamp plan §3).
- **Focus:** focus is trapped while open and returns to the Herbalism button on close.
- **Time:** the footer clock is the scene clock. Each step's time cost ticks it forward when you
  roll, with the clock's own animation from `09-clock.js`.
- **In `/craft/`:** the Herbalism tab on the old page becomes a single card with the button
  "Open the herbalism bench", which returns to the table with the layer open.

### 4.2 Desktop grid, 1600×900 (the reference size)

```
┌ #bench ────────────────────────────────────────────────────────────────────────────────┐
│ Herbalism        [Grind][Mix][Brew][Dry][Reduce][Extract][Infuse][Steep][Neutralize🔒]  [Close] │  method strip, 56px
├ satchel 300px ─┬─ stage, minmax(560px, 1fr) ─────────────────────┬─ tag 320px ──────────┤
│ Search         │                                                   │  ┌─ paper tag ─────┐ │
│ [What fits ▾]  │        3D mortar on the forest floor, lit by      │  │ Comfrey         │ │
│ Fresh herbs    │        the scene's light, the camera at 50°       │  │ Poultice        │ │
│  ▣ Comfrey  3  │                                                   │  │ bound on a wound│ │
│  ▣ Garlic   1  │        dropped: Comfrey ×2   (chips on the rim)   │  │ keeps 1 day     │ │
│ Powders        │                                                   │  │ ─ ladder ─      │ │
│  ▣ Barley   2  │                                                   │  │  Flawless       │ │
│ Can't use now  │                                                   │  │  Superior       │ │
│  ▢ Hemlock     │ ┌ minigame strip (rises after the roll) ────────┐ │  │▸ Fine  ◂ ceiling │ │
│   needs        │ │  crush ring        Space or click     Fine     │ │  │  Sound          │ │
│   neutralizing │ └────────────────────────────────────────────────┘ │  │  Crude          │ │
│ Steeping       │ 2 doses. 30 minutes. DC 12, you need 6 or better. │  │ Heals 1d4 → 1d4+1│ │
│  ⧗ Tincture,   │              [ Roll Craft ]                       │  └─────────────────┘ │
│    day 31      │                                                   │  Batch [ 2 ] all     │
├────────────────┴───────────────────────────────────────────────────┴──────────────────────┤
│ Day 14, 6:20pm    Herbalist 1 ──────── 8 / 25    Recipes    Herbarium    Steady mode ○  │  footer, 44px
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

- **Grid:** `grid-template-columns: 300px minmax(560px, 1fr) 320px`, with rows `56px 1fr 44px`.
  CSS Grid, not flex arithmetic (skill §3.E).
- **Alignment:** the satchel and tag are left-aligned text. The stage's info line and Roll are
  centred under the tool, because the tool is the centre of attention.
- **The stage is the one bold element.** The panels around it are the existing tooled leather
  with clasps, and the stage has *no* panel frame. Its ground fades into `--bg` through a radial
  vignette, so the kit sits in the dark like a camp at night.

### 4.3 Other sizes

| Viewport | Change |
|---|---|
| **3440×1440 (the owner's ultrawide)** | The stage would stretch to 2,700px. Cap the content at `max-width: 2000px` and centre it. The ground texture and vignette fill the full width, so there are no black bars, and the camera's field of view is clamped so the tool never shrinks below 38% of the stage height. The 0.2.x candle veil already had to handle this width (commit 54b23fc); test it again. |
| **1920×1080** | Same as the reference; the stage grows. |
| **1280×720** | Satchel 260px, tag 280px, method strip in icons with names on hover and focus. The minigame strip overlaps the bottom 30% of the stage rather than pushing it. |
| **Under 1180px** (the old bench's breakpoint, kept) | Stage on top at 56vh, method strip as a scrollable row, then the tag, then the satchel as a section. The page scrolls; nothing scrolls inside anything else. |
| **Under 768px** | Single column (skill §7, mobile override). The minigames still work: every game has a tap or click form (§9). |

---

## 5. The flow, screen by screen

| Step | What you see | What it reuses |
|---|---|---|
| **1. Open** | The layer fades in over the table (200ms). The last method used is active, and the tool is already on the ground. | the table stays mounted |
| **2. Pick a method** | The old tool lifts and fades (180ms); the new one drops and settles (450ms, §10). The satchel re-sorts into **What fits**, **Can't use now** (each with its reason) and **Steeping**. Locked methods show a lock icon and "Herbalist 2" in words. | `herbprep.can`, `crafting.prep_problem` |
| **3. Add ingredients** | Drag a tile to the tool, click it, or press Enter on it (drag is never required). It lands with the method's own sound and motion and appears as a chip on the tool's rim, with × to remove. The info line fills in: doses, time, DC, and "you need N+". | the bench's existing validation |
| **4. Roll** | **Roll Craft** is the screen's only gold-filled button. The 0.2.3 dice throw comes up over the bench, with the verdict word. On a **failure** the stage dims, the tag shows what was lost in words ("Missed by 6. Half the comfrey is ruined: 1 of 2 lost. 30 minutes passed."), and the controls come back. | `dice3d`, `22-roll-verdict.js` |
| **5. Play** | On a success the minigame strip rises (220ms). The tag's ladder climbs live as you score, the ceiling marker stays fixed, and the live tier word sits under the strip. It lasts about 6 seconds. | n/a |
| **6. Land** | The tier settles with its flourish (§10). The product rises off the tool and flies along a curve to its satchel tile (500ms), whose count ticks up. A result line slides into the tag: the itemised mastery, plus any discovery ("New: comfrey closes wounds."). | n/a |
| **7. Next** | If a recipe is loaded, its next method is offered as a button ("Next: Mix"). Otherwise the bench stays on this method, ready to go again. | n/a |

---

## 6. Components

### 6.1 Method strip

Nine methods in the order of the craft: Grind, Mix, Brew, Dry, Reduce, Extract, Infuse, Steep,
Neutralize.
- **Each button:** an engraved icon and its name in Cinzel small caps.
- **Active:** gilt underline plate and `--gold` text.
- **Locked:** `--ash` text, a lock icon, and the level in words in the button's label (never a
  tooltip only, which the skill's audit flags).
- **Keys:** 1-9 to pick, ← and → to move.
- **No eyebrow label** above the strip. The word "Herbalism" at its left is the only heading
  (skill §4.7, eyebrow restraint).

### 6.2 Satchel

- **Header:** a search box with a visible label ("Search your satchel", above the field, never a
  placeholder standing in for a label; skill §4.6). Beside it, a filter: **What fits** (the
  default), **Everything I carry**, **Crafted**.
- **Groups:** by state and part (Fresh herbs, Dried, Powders, Oils, Bases, Liquids, Monster
  parts, Crafted, Steeping). The group headings are plain text in `--dim` sentence case, not
  uppercase tracked labels.
- **What it shows:** only what you **carry**. Herbs you've met but don't carry live in the
  herbarium, not on the shelf. That retires the 161-tile wall.
- **A tile** is 56px tall, as a row, not a grid, because a list of names reads faster than a
  wall of identical icons. Each row has:
  - the engraved part icon;
  - the name;
  - a count on the right;
  - a rarity rim on the icon (hairline to gilt across common to legendary);
  - a state badge (dried, ground, neutralised);
  - a quality word for crafted items ("Fine");
  - a "?" after the name while any property is unknown.
- **Tile states:**

  | State | Look |
  |---|---|
  | **Fits** | full ink |
  | **Can't use now** | text at `--dim`, which still passes 4.5:1 on the panel and must be measured; a 13px reason line under the name ("needs neutralizing first", "already ground", "Herbalist 3 for legendary") |
  | **Locked** | lock icon plus the reason |
  | **Spoiling soon** | a time line, "spoils in 5h" |

  Dimming never relies on colour alone: the reason line is always there.
- **Hover or focus** opens the **herbarium card** (§6.6) beside the satchel. Hover is not
  required, since the card also opens on keyboard focus and on click of the "?".
- **Empty state** for the active method: "Nothing you carry can be ground." It offers two
  buttons: **Forage here** (it opens the table's Craft action) and **Everything I carry**.
- **Loading:** six skeleton rows shaped like tiles (no spinner, per skill §4.5).

### 6.3 Stage

- **The 3D tool:** one per method (revamp plan §9.3). It sits on a **ground plane**.
- **The camp backdrop is the ground.** There is no painted backdrop and no image to commission.
  The ground is a CC0 PBR texture chosen from the scene's biome and place:

  | Where you stand | Ground |
  |---|---|
  | forest | forest floor |
  | swamp | mud |
  | tundra | snow |
  | desert | sand and rock |
  | grassland | grass |
  | road | packed earth |
  | indoors (`places.roofed`) | plank table |
  | tavern | bar top |

  The ground fades to `--bg` through the vignette. The textures come from ambientCG or Poly
  Haven, CC0, recorded in `docs/asset-licences.md`.
- **Light:** a warm key from the camp fire or the room's lamp, and a cool fill by day or a moon
  fill by night (read from the clock). Plus `--candle` ember light that flares on hits.
- **Drop target:** while dragging, the tool's rim glows `--gold` in a ring, so there's a target
  shape as well as a colour.
- **Info line** under the tool, plain sentence case: "2 doses. 30 minutes. DC 12, you need 6 or
  better." Spelled out, not dot-separated (the skill rations middle dots, max 1 per line).
- **Roll Craft:** the one primary button, at most two words, never wrapping (skill §4.5).
  Disabled until something fits, with the reason beside it ("Add a herb to the mortar").
- **WebGL fallback:** if WebGL fails (rare in Electron), the stage shows the tool's engraved icon
  at 160px on the ground colour, and every game still runs in its 2D strip. The games never
  depend on the 3D scene.

### 6.4 Minigame strip

The strip is a 2D HUD (canvas or SVG) that rises from the bottom of the stage, 120px tall. The
game happens **on the tool**: the pestle strikes, the needle swings over the pot. The strip
carries the meter, the input hint ("Space or click"), the Steady mode badge when it's on, and
the live tier word in 34px Cinzel.
- **Same frame for every game:** a meter area on the left, the input hint in the centre, the
  live tier on the right, and a 2px time thread along the top. The thread is a progress line with
  no background track, which avoids the skill's banned filled-track bar.
- `aria-live="polite"` announces the tier when it changes, not every frame.
- Per-game layouts are in §9.

### 6.5 Result tag

A paper tag (`--tex-page-paper` under its existing dimming), pinned at the top of the right
column with a brass eyelet. It is the one piece of paper on the bench and holds the content:
- **Name** (24px Cinzel), then **form**, **how it's taken**, and **keeps** in plain lines.
- **The ladder:** a vertical list from Crude to your ceiling, with the current tier marked by a
  brass pointer and the ceiling by a hairline and "your ceiling" in words. Above the ceiling,
  one greyed rung reads, for example, "Flawless +1 at your next Quality perk", so the
  next goal is visible.
- **Numbers:** potency and duration as before and after ("Heals 1d4, at Fine 1d4+1"), drawbacks
  shown the same way, with known effects only and a "?" line for unknowns ("1 property unknown").
- **"What the source says"** stays as a disclosure.
- **Batch:** a stepper and an **all** button under the tag, with the bulk cost in words ("5 doses
  take 2h 30m and share one result").

### 6.6 Herbarium card (bench) and Herbarium section (Journal)

**The card** opens beside the satchel. It has:
- the engraved icon at 48px;
- the name;
- the biomes you found it in;
- known properties, one per line, with how you learned each in `--dim` ("tasted, day 14");
- one dash per unknown property ("unknown");
- two actions: **Study** (10 min, the player's roll) and **Taste** (uses 1 dose).

**Taste** always opens a confirm with the risk in plain words. If a study has flagged danger,
the confirm says so in `--alarm` ("You know this is dangerous: it can paralyse."). The confirm
button reads **Taste it**, and the cancel button **Keep it**.

**The Journal section** (`21-tab-journal.js`, beside History) shows every herb you've met as a
two-column list on desktop and one column on narrow screens. Each row has the icon, name, kind,
known and unknown counts ("3 of 5 known"), and the biomes; clicking expands the same card. A
filter toggles "Unknowns first". The empty state reads "No herbs yet. Forage or buy one and it
appears here."

### 6.7 Perk picker

Opened from the footer when perks are banked ("2 perks to pick"), and once on first load after
migration. It is a dialog with four perk choices in a 2×2 grid. They are not three equal cards,
and each is a button with the icon, name, its effect at your next pick ("+5% potency, total
+15%"), and how many you've taken. Pick two; the same one twice is allowed, and the second pick
of the same perk shows "×2". **Confirm** is disabled until two are chosen. Banked picks wait
without nagging: the footer label is the only reminder.

### 6.8 Footer

The footer shows:
- the scene clock;
- Herbalist level with a thin mastery bar (no background track: a brass line on the leather,
  with the numbers beside it);
- **Recipes**, which opens the recipe book (a popover listing your saved recipes; **Load**
  pre-drops the ingredients and sets the method);
- **Herbarium**, which opens the Journal section in place;
- the **Steady mode** toggle, mirrored from settings.

### 6.9 Settings additions (app-wide)

Settings gains a **Sound** group: a volume slider per bus (UI, dice, bench, ambience, combat)
plus master and mute. It also gains **Steady mode** and a **Flourishes** choice: Full (the
default, big and juicy) or Short, which keeps the sounds and word but drops shake and confetti.
Short is chosen automatically when the OS asks for reduced motion.

---

## 7. States checklist (skill §4.5)

| Surface | Loading | Empty | Error | Disabled |
|---|---|---|---|---|
| Satchel | skeleton rows | "Nothing you carry can be ground." with Forage and Everything | inline "Couldn't load your satchel. Retry" | n/a |
| Stage | ground renders first, then the tool fades in | "Add a herb to the mortar" | WebGL fallback (§6.3) | Roll disabled, with its reason |
| Roll | dice in flight | n/a | the server refused: the reason in words under Roll | n/a |
| Minigame | n/a | n/a | the tab lost focus: auto-pause with "Paused. Press Space to carry on." | n/a |
| Tag | "Put something on the tool to see what it makes" | same | n/a | n/a |
| Herbarium | skeleton | "No herbs yet." | inline retry | n/a |
| Perk picker | n/a | n/a | the save failed: picks kept and retry offered | Confirm until two are chosen |

**Losing focus pauses the game.** A minigame running while the player's attention is in another
window would score them for time they weren't there for.

---

## 8. Copy

The voice is the app's own: plain, in-world, specific, sentence case. Every new bench string
avoids em-dashes (skill §9.G).

**One label per intent** (skill §4.5):

| Label | Intent |
|---|---|
| Roll Craft | start a step |
| Taste it / Keep it | the taste confirm |
| Study | identify a herb |
| Save recipe / Load | recipes |
| Close | leave the bench |
| Forage here | gather material |
| Next: <method> | continue a recipe |

**Reasons** use the bench's existing grammar, because it already teaches:
- "it has to be extracted before anything else can be done with it";
- "it is volatile, neutralize it first" (re-punctuated without the dash).

**Numbers are real**, from the engine, never decorative. Times are written "30 minutes" and
"2 hours 30 minutes" in prose lines, and "30m" only in the compact info line.

---

## 9. Minigame screens

Each game's rules are in revamp plan §9.3. These are the screens:

| Game | On the tool (3D) | In the strip (2D) | Mouse | Keyboard | Steady mode |
|---|---|---|---|---|---|
| **Grind** | The pestle raises; a ring of light closes on the strike mark in the bowl. | 8 beat pips; each fills brass on a hit or cracks on a miss. | click | Space | tempo ×0.5, window ×1.6 |
| **Mix** | The paddle follows your stroke in the bowl; the base goes from lumpy to glossy. | The stroke guide (circle, figure-eight, fold) as a brass line; your trace in ink. | drag along the guide | arrows in the shown order, one press per segment | the guide waits for you instead of moving on |
| **Brew** | The fire under the pot; a needle on a brass dial on the pot's rim. | The heat band as a shaped notch on an arc (infusion low, decoction high). | click to feed, release to bank | ↑ / ↓ | toggles instead of holds; drift ×0.5 |
| **Dry** | 3-5 bundles hanging over smoke; each curls as it cures. | One small arc per bundle with its band marked; the bundle's number above it. | click the bundle | 1-5 | bands ×1.6 wider |
| **Reduce** | A pan with the level falling to a scored line. | The level gauge with the line; a scorch zone hatched. | click and release | ↑ / ↓, Space to pull off | toggles; drift ×0.5 |
| **Extract** | Knife and tongs over the part; a dotted incision path. | The path as a strip with nodes; your pace as a short needle. | drag along the path | hold → or toggle with Space (Steady mode), release at nodes | the path pauses at each node for you |
| **Infuse** | The oil crock in ashes; oil shimmers, then darkens if scorched. | Two lines, cold and scorch, with the band between them hatched; the fill thread along the top. | click to add embers | ↑ / ↓ | toggles; drift ×0.5 |
| **Steep** | Pouring spirit into the jar to the scored mark, then a twist-seal ring. | The jar's fill gauge with the mark; then a beat ring for the seal. | press to pour, release to stop; click on the beat | Space | pour speed ×0.5; seal window ×1.6 |
| **Neutralize** | Gloved dropper over the material; a needle swinging on a glass dial. | The volatility arc with the safe notch; each drop leaves a tick. | click per drop | Space per drop | the needle settles twice as fast |

- **No precision game depends on the cursor art.** Each draws its own reticle on the stage (the
  pestle tip, the knife point), so the candle cursor's hotspot is irrelevant to scoring. This
  matters because the owner saw a cursor-offset bug in 0.2.2.
- **Each game has a 2-second first-time card** ("Strike as the ring closes") that never shows
  again after you score Fine or better in that game. It can be reopened from a "?" on the strip.

---

## 10. Motion and juice

Every animation has a reason, the skill's §5 test: feedback, state change or hierarchy.

| Event | Stage (MOTION 8) | Chrome (MOTION 3) | Reason | Reduced motion / Short |
|---|---|---|---|---|
| Open the bench | the ground fades in, the tool settles | layer fade 200ms | state change | fade only |
| Switch method | old tool lifts out 180ms; new tool drops, overshoots 4% and settles, 450ms total | strip underline slides 160ms | state change | crossfade 120ms |
| Drop an ingredient | the item arcs onto the tool; method sound; a small dust or splash puff | the satchel count ticks | feedback | count ticks, no arc |
| Each minigame hit | particles (grit, steam, sparks); a camera nudge of 1.5° and 60ms; an ember flare | the strip pip fills | feedback | pip fills, sound plays |
| Tier up | the tag's pointer slides; the tool glints | a single 180ms brightening of the rung | hierarchy | instant move |
| Flawless | the 0.2.3 brass 3D word "Flawless" over the tool, gilt sparks, a 250ms screen shake | n/a | feedback | the word only, no shake or sparks |
| Product lands | the product rises, then a 500ms curve to the satchel tile | the tile pulses once | storytelling: where it went | the tile highlights |
| Failure | the stage dims 30% for 600ms and the tool shudders | the loss line slides into the tag | feedback | dim only |

**The one-second rule.** No flourish takes input away. Flourishes live in `#rv-layer` with
`pointer-events: none`. The satchel, strip, tag and Close stay live throughout, and any click
skips the flourish (it completes instantly). The test in §13 measures this.

**Performance** (skill §6.A). Chrome animates only `transform` and `opacity`. No
`requestAnimationFrame` loop runs while the bench is idle: the stage renders on demand
(input, a game tick, or a flourish) and stops when still, so an idle bench costs no GPU while
the owner reads.

---

## 11. Sound hooks

These are the bench's events on the app-wide sound system (revamp plan §11). Every event is a
bus and a name, so sound is wired once and assets can be swapped later:
- `bench.open`, `bench.method.<name>`, `bench.drop.<part>`, `bench.roll`;
- `bench.hit.<method>`, `bench.miss.<method>`;
- `bench.tier.up`, `bench.flawless`, `bench.fail`, `bench.land`;
- `bench.taste`, `bench.study`;
- `ambience.<biome>` under the stage while it is open.

---

## 12. Engineering shape

**Files** (the table's numbered module pattern):
- `play/static/js/table/30-bench-shell.js`: the layer, focus, keys, clock, footer.
- `31-bench-satchel.js`
- `32-bench-stage.js`: three.js, loaded on first open.
- `33-bench-games.js`: the shared frame.
- `bench-games/*.js`: one file per game.
- `34-bench-tag.js`
- `35-bench-herbarium.js`
- `36-bench-perks.js`

Styles go in a `bench` section of `theme-v2.css`, or `bench.css` linked after it. They use only
existing tokens and the semantic layer in §3.

**3D and assets:**
- **three.js:** reuse the version `dice3d.js` ships, with one renderer for the bench. Lazy-load
  the bench chunk and models on first open. The table's first paint must not pay for them (skill
  §6.E).
- **Models:** glTF with Draco, at most 5 MB together.
- **Ground textures:** 1K, at most 300 KB each.

**The server contract** (the three laws, revamp plan §13). The page sends method, ingredient
ids, batch, and the minigame score as 0..1. The server answers with:
- the tier;
- the clamped score;
- the product;
- the mastery lines;
- discoveries;
- the time passed.

The page never computes a tier, a number or an effect.

---

## 13. Verification (before it is called done)

1. **Live, in the running app, on scratch data.** Every method at:
   - 1280×720;
   - 1600×900;
   - 1920×1080;
   - **3440×1440**;
   - under 1180px.

   Screenshots of each go in the lane's report.
2. **Reduced motion** (emulated) and **Steady mode**: every game playable, no shake, no
   confetti.
3. **Keyboard only:** open, pick a method, add, roll, play, close, without the mouse.
4. **Contrast:** measure dimmed tile text, the reason lines, the tag on paper, and the Roll
   button against their real backgrounds. All must meet AA.
5. **The one-second test** (a test file, with its docstring naming the defect): during a
   Flawless flourish, click a satchel tile at 100ms. The click must land, and the shelf must
   respond within 100ms.
6. **Idle GPU:** the bench open and idle for 10 seconds draws zero frames, measured by a frame
   counter.
7. **Packaged build:** open the bench in `win-unpacked` on a throwaway data dir. three.js,
   models and textures load from the bundle, not a dev path.

---

## 14. Pre-flight (the skill's matrix, adapted to a game screen)

| Check | Status in this plan |
|---|---|
| Brief read declared | §0 |
| Dials explicit and reasoned | §0, split by surface |
| Redesign mode and audit | §2 |
| Zero em-dashes in bench strings | §8; the lane greps new strings for `—` and `–` |
| Theme lock (one theme) | dark only, as the whole app; no light section |
| Colour lock (one accent) | gold; `--brew` green retired from the chrome (§2, §3) |
| Shape lock | 3px; circles only for dials, dice, rings |
| Button contrast; no CTA wraps | Roll Craft is two words; measured in §13 |
| Form contrast; labels above fields | the satchel search (§6.2) |
| No eyebrows | none; group headings are plain sentence case |
| No duplicate intents | §8 |
| Motion motivated | §10, a reason per row |
| Reduced motion | §10, a column per row |
| No scroll listeners, no idle loop | §10 |
| Empty, loading, error states | §7 |
| No filled-track progress bars | the time thread and mastery line have no track |
| No decorative dots; middle dots rationed | the info line is spelled out |
| Icons from a library, none hand-drawn | game-icons.net, credited |
| No emoji | retired (§2) |
| z-index scale documented | §3 |
| Mobile collapse explicit | §4.3 |
| Custom cursor | kept by owner preference (§2); no game depends on it (§9) |

---

## 15. Build order

These lanes are the revamp plan's lanes 4-7, refined:

| # | Lane | Contents |
|---|---|---|
| 4a | **Shell** | The layer, the open and close routes, focus and keys, the footer and clock, the old page's Herbalism card. |
| 4b | **Satchel and tag** | Tiles, groups, reasons, filter and search, the herbarium card, the ladder, batch, recipes. |
| 4c | **Stage, flat** | The engraved-icon fallback stage, the info line, Roll and the d20 wiring, results flying to the satchel. **Playable end to end with 2D games, before any 3D.** |
| 5 | **Games** | The shared frame, then the nine games, each with mouse, keyboard and Steady mode. |
| 6 | **3D** | The renderer, the ground by biome, the nine tools, juice and flourishes, reduced motion. |
| 7 | **Sound** | The bus system and settings, then the bench events, then the rest of the app. |
| 3b | **Journal herbarium and perk picker** | They ride with the revamp plan's discovery and engine lanes. |

**Why the order matters:** 4c ships a fully working bench with flat stand-ins, so the rules lanes
can be verified in the real UI before any modelling starts. The research's main warning is that
minigames get softened after launch; tuning them on a flat build first is where that is cheapest.

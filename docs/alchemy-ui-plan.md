# Alchemy bench: the UI and 3D plan

Drafted 2026-10-05. This is the interface half of `docs/alchemy-revamp-plan.md`. The rules,
numbers and engine lanes live there, and are cited as **plan §n**. This plan has the same depth
as `docs/blacksmithing-ui-plan.md` and `docs/herbalism-ui-plan.md`. It uses the same two design
skills (`design-taste-frontend` and `frontend-design`) under the owner's standing instruction:
**keep the colours, images and textures, and change structure and behaviour** (redesign,
preserve).

Sources:
- the code map of the shared bench parts on master 1f88ada: `29-bench-core.js`, `bench-stage/`,
  `forge-stage/`, `33-bench-games.js`, `sound.js`, the icon registry and the templates (§3);
- `docs/alchemy-prior-art.md` §5 for the real operations;
- the owner's Round 9 answers (Q9.1 to Q9.4).

Numbers marked **(proposed)** are defaults for tuning.

---

## 0. Design read and dials

**Design read.** This is a crafting workbench in a desktop game, for a solo Pathfinder player
who wants the craft to feel physical. It uses the app's own language of dark leather, brass and
candlelight. It is vanilla JS in the table's numbered modules, with the existing `theme-v2.css`
tokens and the herb bench's hand-written WebGL stage. The app bundles no third-party JS.

**Mode.** Redesign, preserve. The skill's default stack (React, Tailwind, Motion) is set aside
by its own "one system per project" rule, exactly as the herb and forge UI plans record.

**What is different from the other two benches, in one line:** alchemy is about **liquid and
containment**. An alchemist reads two things: the colour and level of what is in the glass, and
whether the reaction is staying in its band. So the stage's subject is **glassware with live
liquid**, and the strip gains a **reaction gauge**. The right column becomes a **formula card**:
- the vessel;
- the formula, or Experiment;
- the possible-formulae count;
- the trait slots;
- the stakes.

| Surface | VARIANCE | MOTION | DENSITY | Why |
|---|---|---|---|---|
| **Stage** (glassware, flame, liquids, vapour, the flare) | 6 | **8** | 2 | "Big and juicy" lives here, and only here. Liquid, bubbles, vapour and the flare are the boldness this screen spends. |
| **Chrome** (shelf, method strip, formula card, footer) | 4 | **3** | 6 | Matches the table, the herb bench and the forge. Hover and press feedback only; nothing moves on its own. |

---

## 1. Decisions that bind this plan

| Question | Owner's answer (2026-10-05) |
|---|---|
| Layout (Q9.1) | **Its own bench**, built from the herb bench's parts, as the forge was. It opens over the table. The old `/craft/` Alchemy tab retires when it lands. |
| Stage (Q9.2) | **A field kit on the ground** (crucible, spirit lamp, a few vials) **and a laboratory** (alembic, athanor, retort), with **procedural 3D glassware whose liquid colour and level are live**. |
| Minigames (Q9.3) | **Real operations, each a band you stop inside**, with skill widening the band. Start generous. Every gauge is **a number and a bar as well as a colour**. |
| Volatile work (Q9.4) | **A visible reaction gauge** (number, bar and colour) that climbs while you work, and **a real flare on a failed roll**. Reduced motion is respected. |

**Carried over from the other benches:**
- the full-screen layer over the table (z 35);
- the method strip, the d20 throw and the brass verdict word;
- the minigame strip with Steady mode;
- the quality ladder on a paper tag;
- the perk picker, app-wide sound, the one-second rule, and render on demand;
- the **material colour comes from the server**. This time it lives on the material document
  (plan §5.2), not in a view's table (forge contracts §15.6).

---

## 2. Audit of today's Alchemy tab

**Read from the code and the inventory, not driven live.** Lane U1's first job is to drive it
live on scratch data at 1600×900, as the forge plan did, and to add anything this misses.

**What is there:**
- The Alchemy tab is still the old generic chain bench (`craft.html` `renderBench`). It renders
  from `STATE.disciplines` (`play/craft_views.py:38`).
- It shows:
  - every material as an emoji-glyph tile (`KIND_GLYPH`, `craft.html:637`);
  - a cauldron emoji as the drop target (`:811`, styled at `:356`);
  - a chain row and a preview.
- **The preview's itemised DC (`dc_terms`), its volatile marks and its mishap line never reach
  the page** (inv §5; `docs/alchemy.md:485-489` asked for them).
- A batch rolls one d20 per dose (`craft_views.py:493-613`). The revamped benches roll once for
  a stack.
- The roll honours natural 1 and 20 (`:624-627`). The revamped benches do not.

**Keep:**
- the tooled leather panels and clasps;
- Cinzel small caps;
- reasons in words;
- the itemised check terms (they move to the formula card, now actually shown);
- the candle cursor (no game depends on its hotspot).

**Retire on the alchemy bench:**
- emoji glyphs;
- the cauldron (a herb metaphor, and an emoji);
- the all-materials wall;
- the chain row;
- the per-dose dice;
- the naturals.

---

## 3. What is reused, and what is new

Measured by reading the shared parts on 1f88ada:

| Module | Lines | Reuse |
|---|---|---|
| `table/29-bench-core.js` | 662 | **As is.** `BenchCore.mount` gives the layer, focus trap, Esc stack, keys, clock turn, `rollD20`, `fly`, `word`, `dim`, `confirm`, `askStop` and the footer frame. It knows no craft, and `test_bench_core.py` pins that. |
| `bench-stage/00-math.js`, `03-ground.js`, `04-particles.js` | 637 | **As is.** Maths, biome ground for the field kit, and particles. The kinds include `steam`, `drop`, `splash` and `glint`. |
| `bench-stage/01-gl.js` | 554 | **Extended, never changed** (§7.3). It already has an alpha pass sorted by `mat.order`, a fresnel term, emissive, three point lights, and no face culling, so back faces already draw. |
| `bench-stage/02-meshes.js` | 258 | As is: `lathe`, `cylinder`, `sphere`, `ring`, `merge`. Glassware is lathes. |
| `forge-stage/01-props.js` `sweep` | | **Reused** for the bent necks: the alembic's beak, the retort's neck, the receiver's spout. A section is swept along a path. |
| `forge-stage/00-heat.js` | 197 | `seen(c)` and `light(c)` are reused for the athanor's coals and the spirit lamp's flame colour. Heat colour stays content. |
| `table/33-bench-games.js` | 1,195 | **As is**, plus one new gauge type (§6.4). Games register on `BenchGameDefs[method]` with `track: "alchemy"`. The `HEAT` gauge already serves Calcine, Distill and Sublime. |
| `table/34-bench-tag.js` | 246 | As is: the paper tag and ladder. |
| `table/36-bench-perks.js` | 333 | Already parameterised by track (`TRACKS`, 39-60). Alchemy adds one entry with five perks. |
| `bench-stage/05-props.js` glass | | The glass material (`alpha .1, fresnel .55, spec 1.4, shin 90`, `05-props.js:30`) is the starting point. The steep jar (`06-tools.js:802-870`) is the template for liquid in glass. |
| `table/31-bench-satchel.js` | | Its "Steeping" group (72-81, 144-156) is the pattern for the **In progress** group, until the shared section lands (§6.9). |

**New:** `table/50-54`, `alchemy-stage/00-04`, `alchemy-games/*` and the `alchemy` sound bus
(§12).

---

## 4. Tokens

**No new colours, fonts or textures.** The bench maps onto the bench's semantic layer, exactly
as the forge does (`forge.css:19-22` overrides only widths):

```css
.alchemy {
  --bench-satchel-w: 290px;   /* the shelf: longer names than the forge's metals */
  --bench-tag-w: 360px;       /* the formula card carries slots and stakes */
}
```

Every other token is the bench's own:
- `--bench-ground: var(--sunk)`;
- `--bench-ink: var(--ink)` and `--bench-quiet: var(--dim)`;
- `--bench-accent: var(--gold)`, the **one accent**: the active method, Roll and the ceiling;
- `--bench-warn: var(--alarm)`, for the mishap line, a dangerous assay and ruined materials;
- `--bench-light: var(--candle)`.

**Liquid colour is content, not chrome.** It is the same rule as heat colour at the forge and
liquid colour at the herb bench. The material's `color` (plan §5.2), and the mix colour the
server computes for a step, appear **only inside the 3D scene and as a swatch beside a name**.
Chrome stays gold.

**The reaction gauge's colours are content too**, like the heat gauge's scale: calm, rising,
and flare. The gauge never relies on colour. It carries a **number (0 to 100), a bar with the
safe band outlined, and the band's name in words** (calm, working, boiling over).

**Swatches.** An 8px disc beside the engraved icon, filled with the material's colour. It never
carries meaning alone; the name is always beside it.

**Quality** reads by metal and weight, never by hue, as the herb tag's ladder does (Crude
`--ash` … Flawless `--gilt`), with the name in words.

**Essences are words, not colours.** An essence chip is a small engraved label ("fire",
"lightness") in `--dim` ink on `--sunk`, never a coloured pill. Eighteen hues would be a second
palette, and colour alone would fail the accessibility guidelines.

**Icons** come from game-icons.net (CC BY 3.0), credited in About, the manual and
`docs/asset-licences.md`, and rendered as gilt masks like the herb and forge icons. Some are
already in the registry:
- `reagent.svg` (round-bottom flask);
- `tincture.svg`;
- `steep.svg`;
- `neutralize.svg` (eyedropper);
- `liquid.svg`.

New ones are needed for:
- **methods:** calcine, dissolve, distill, filter, react, sublime, bottle, transmute, assay;
- **forms:** vial, flask, bladder, casing, rod, salt, spirit, calx, crystal;
- **states:** volatile, toxic, catalyst, setting.

The icon **names must be confirmed on game-icons.net** by lane U1. This plan does not claim any
specific icon exists. **The download needs the owner's approval**, as the forge's did (plan
§21, open point 11).

---

## 5. Layout

### 5.1 The layer

- The bench opens over the table as its own full-screen layer: `#alchemy`, `role="dialog"`,
  `aria-modal="true"`, z 35, through `BenchCore.mount({layer: "alchemy", hash: "#alchemy",
  bodyClass: "alchemy-on", openWith: "[data-alchemy-open]", ...})`.
- It opens from an **Alchemy** button in the left column, beside Herbalism and Smithing
  (`table.html:3439-3443`).
- The old `/craft/` Alchemy tab becomes a "moved" card, as Herbalism and Blacksmithing did
  (`craft.html:685-770`).
- One bench at a time (`C.current`).
- Esc, the focus trap and the clock behave exactly as the other two benches.

### 5.2 Desktop grid, 1600×900

```
┌ #alchemy ──────────────────────────────────────────────────────────────────────────────────┐
│ Alchemy  [Calcine][Dissolve][Distill][Filter][React][Sublime][Bottle][Transmute][Assay] [Close] │ 56px
├ shelf 290px ─────┬─ stage, minmax(600px, 1fr) ──────────────────────┬─ formula card 360px ─┤
│ Search the shelf │                                                   │ Vessel  ▣ Clay flask │
│ [What fits ▾]    │   spirit lamp ▸ flask on a tripod, liquid amber   │  splash flask, 2 slots│
│ Reagents         │   at two thirds, slow bubbles                     │ Formula [Alchemist's ▾]│
│  ▣● Brimstone 4  │   (field kit on forest floor,                     │  or Experiment        │
│  ▣● Naphtha   2  │    or a laboratory bench with the alembic)        │ Could still become 2  │
│ Solvents         │                                                   │  (you know 1)         │
│  ▣● Strong sp. 3 │ ┌ minigame strip ────────────────────────────────┐│ Traits  ▣ fire 2     │
│ Salts and spirits│ │ REACTION ▕▓▓▓▓░░▏ 46 working   Space adds a drop ││         ▢ free slot  │
│  ▣● Fire calx 1  │ └────────────────────────────────────────────────┘│ Drawbacks: none       │
│ Hybrid herbs     │ 3 flasks. 30 minutes. DC 20, you need 12 or better.│ If this fails by 5:  │
│  ▣● Glowvine  2  │ If this fails by 5 or more: 1d6 fire to you.      │  1d6 fire to you     │
│ In progress      │              [ Roll Craft ]                       │ ┌ paper tag ───────┐ │
│  ▣ Haste, day 16 │                                                   │ │ Alchemist's Fire │ │
│ Can't use now    │                                                   │ │ ▸ Fine ◂ ceiling │ │
├──────────────────┴───────────────────────────────────────────────────┴──────────────────────┤
│ Day 14, 6:20pm   At the field kit   Alchemist 2 ──── 31 / 65   Formulary   Codex   Steady ○ │ 44px
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

- **Grid:** `290px minmax(600px, 1fr) 360px`; rows `56px 1fr 44px`.
- **The formula card** (right) replaces the forge's work order. From top to bottom:
  - the vessel;
  - the formula picker;
  - the possible-formulae count;
  - the trait slots;
  - drawbacks;
  - the stakes;
  - the paper tag.
- **The footer** names **where you are** ("At the field kit", "At Mirela's laboratory, 2 sp an
  hour", "In your laboratory"), because that decides which methods and materials are open, and
  whether the +2 and the fume hood apply.

### 5.3 Other sizes

As the forge plan §5.3:
- **3440×1440:** content caps at 2,000px, and the ground or bench fills the width.
- **1280×720:** the shelf narrows to 250px and the formula card to 320px. The method strip goes
  to icons, with names on hover and focus.
- **Under 1180px:** the stage stacks on top at 56vh.
- **Under 768px:** a single column, and every game has a tap form.

---

## 6. Components

### 6.1 Method strip

- Nine methods in craft order.
- A locked method shows a lock and the reason in words: "Alchemist 2", or **"Needs a
  laboratory"** (the forge's location lock).
- Keys 1 to 9 pick; the arrow keys move.

### 6.2 The shelf (left)

The herb satchel's and forge rack's pattern:
- **Only what you carry.**
- **Groups:**
  - Reagents;
  - Glands and essences;
  - Solvents;
  - Salts and spirits (intermediates);
  - Solutions and admixtures (they spoil in 3 days, and say so);
  - Hybrid herbs;
  - Catalysts and apparatus;
  - Vessels;
  - Finished work;
  - **In progress**;
  - Can't use now.
- **A row:**
  - the engraved form icon and the colour swatch;
  - the name and the count;
  - the rarity rim;
  - state badges (volatile, toxic, catalyst, concentrated ×2);
  - the grade on intermediates ("fire 2");
  - the quality word on finished work;
  - a "?" while anything is unknown.
- **Volatile and toxic are words with a shape**, never colour alone: a small flame glyph and the
  word "volatile", or a gloved-hand glyph and "toxic to handle".
- **Can't use now** carries its reason, for example:
  - "needs a laboratory";
  - "Alchemist 2 for rare";
  - "a finished potion cannot go back into the glass";
  - "it does not dissolve in spirits";
  - "it burns away; it will not calcine".
- **Hover, focus or "?"** opens the **Codex card** (§6.8).
- **The empty state:** "Nothing you carry can be dissolved.", with **Buy at the market** (in a
  settlement) and **Everything I carry**.
- **No scroll jump.** The list re-renders in place and keeps its scroll position (the forge
  audit's defect, not repeated).

### 6.3 Stage

- **Field kit** (common and uncommon work): on the biome ground from `03-ground.js`:
  - an iron tripod over a **spirit lamp** (a blue-yellow flame, the key light);
  - a **crucible** for Calcine;
  - a small **round-bottom flask** for Dissolve and React;
  - a **cloth filter in a funnel**;
  - a **rack of four vials** for Bottle.
  - The camera is at about 35°, looking across the kit.
- **Laboratory** (rare and up; Distill, Sublime, Transmute):
  - a **workbench** of dark planks;
  - the **athanor** (a brick furnace with its tower), whose coals are the key light;
  - the **alembic**: the cucurbit on the athanor, the head, and the beak running down to the
    **receiver**;
  - a **retort** in a sand bath;
  - a **bain-marie** pot;
  - an **aludel** (the sublimation vessel) for Sublime;
  - shelves of jars behind in soft focus;
  - a **fume hood** over the left end (it is what protects against toxic work, plan §8.4, so it
    is visible);
  - a window giving day or night fill from the scene clock.
- **The work is the liquid.** The active vessel holds the step's contents:
  - **colour** from the server's mix colour;
  - **level** from the volume;
  - **turbidity** (cloudy to clear) from the step's state.

  All three are live during the game (§7.4).
- **The info line** under the stage, in plain words: "3 flasks. 30 minutes. DC 20, you need 12
  or better."
- **The mishap line** is under it, in `--alarm` words, only on a volatile step: "If this fails
  by 5 or more: 1d6 fire to you (brimstone)." It comes from the server's check response
  (plan §8.1). The page never composes it.
- **Roll Craft** is the only gold-filled button. When it is disabled, its reason sits beside it
  ("Choose a vessel to bottle into").
- **WebGL fallback:** the engraved vessel icon at 160px on the ground colour, with a CSS
  liquid-level bar beside it (colour, level and the number). Every game runs in its 2D strip.

### 6.4 Minigame strip and the reaction gauge

The shared strip frame is unchanged in shape:
- the meter on the left;
- the input hint in the centre;
- the live tier on the right;
- the time thread on top.

Two gauges serve alchemy:
- **The heat gauge** (exists, `33-bench-games.js:356-439`) for Calcine, Distill and Sublime. The
  bands are named for the operation: "heads, hearts, tails" on Distill, "dull, calcining,
  fusing" on Calcine. The temperature is in °C, and the target band is outlined.
- **The reaction gauge** (new, the same frame). It is the alchemy half of the owner's Q9.4.
  - **A spec**, the exact shape of `HEAT`:

    ```
    REACTION: {label, band:[lo,hi], rise, settle, flare_at, start}
    ```

    The server's `opts.reaction` wins over the game's defaults, as `opts.heat` does.
  - **What it draws:**
    - a horizontal bar from 0 to 100;
    - the safe band outlined (a shape, not only a colour);
    - a needle;
    - the number;
    - the band's name in words: "calm", "working", "boiling over".
  - **Over `flare_at`** the hint changes to "Let it settle" in words, and the stage shows a
    small flare. **This is a quality signal only.** A minigame overshoot never triggers the
    mishap (plan §8.2).
  - It is used by React (drop by drop), Dissolve (the stir rate keeps the fizz in band) and
    Bottle (the vapour must be low when the stopper goes in).

### 6.5 The formula card (right)

From top to bottom:

1. **Vessel.** A slot, and the drop target for a vessel from the shelf. Filled, it shows the
   family in words and its slots ("splash flask, 2 slots; thrown"). It appears only on Bottle,
   because the vessel decides the family (plan §12.1).
2. **Formula.** A picker over **known formulae that fit this family**, plus **Experiment**.
   - Choosing a formula shows its requirement in words, with what is met and what is missing:
     "needs fire. You have fire 2." or "needs lightness at grade 2. You have 1."
   - Unknown formulae are never listed.
3. **Could still become N.** The possible-formulae count (plan §10.3), always visible while
   building:
   - "Could still become 4 formulae. You know 1: Antitoxin."
   - **Never an unknown name.** "Could still become 0" says "This mix matches no formula. It
     will bottle as your own compound."
   - The number updates from the server after each drop. The page never computes it.
4. **Traits** (Bottle and the intermediates):
   - one row per slot;
   - each slot is a picker over the pool's traits that the family can deliver;
   - a formula's core takes the first slot and is shown fixed, with a small book mark
     ("by the book");
   - the pool's other traits are listed under the slots, dimmed with their reason ("a potion
     cannot carry a struck trait", "no free slot");
   - grades are shown as numbers ("fire 2"), with the cap in words where it bites ("fire 3,
     capped at 2 by your level").
5. **Drawbacks.** Always listed, never optional (plan §6.3), each with its effect in words.
   "Filter would strip these" appears when Filter is open to the player.
6. **The stakes.** The mishap line again, and any toxic line ("Quicksilver: Fort DC 13 or 1 Con
   damage. You wear no mask."), in `--alarm` words.
7. **The paper tag** (`34-bench-tag.js`): the product name, its family, and the quality ladder
   with the ceiling. **For a spell potion, each rung also shows its caster level and price**
   ("Fine, CL 2, 100 gp"), because quality is caster level there (plan §11.3). Every number is
   the server's.

### 6.6 The volatile confirm

When a step carries a mishap, or an assay is dangerous, the Roll opens **no** modal; the line is
already on screen (§6.3). This is the forge's choice for routine steps.

A **second volatile** in one step (plan §8.3) asks once, with `BenchCore.confirm`:
"Two volatile reagents in one step. Both mishaps apply if it fails by 5 or more. Work it
anyway?", with **Work it** and **Take one out**.

### 6.7 The Formulary

The formula book, opened from the footer:
- known formulae grouped by family;
- for each: its requirement in essences, how it was learned ("found by experiment, day 14",
  "copied from a scroll, day 20", "taught by Mirela"), and its book source when it is a classic;
- **Learn from a writing** (plan §10.4), offered when a scroll, spellbook or formulary is
  carried. It shows the check, the DC, the cost in words, and the one-week wait after a failure;
- **Take it apart** on a carried potion (the house route, plan §10.4), with a confirm in
  `--alarm` words: "The potion is spent. Take it apart?".

### 6.8 The Codex card and the Journal codex

The herbarium's and smith's ledger's counterpart (`44-forge-ledger.js` is the pattern).

**The card** shows:
- icon and swatch, name, and where it is found or bought;
- known properties, each with how it was learned, in two groups:
  - **in the bottle** (product traits, with their essences as engraved words);
  - **at the bench** (working traits, the mishap and the toxic document);
- one "unknown" line per unknown;
- two actions: **Assay** (a pinch, 10 minutes) and **Ask an alchemist** (when one is in the
  scene).

**Assaying a volatile or toxic reagent** opens a confirm in `--alarm` words: "Quicksilver is
toxic to handle, and you wear no mask. Assay it anyway?", with **Assay it** and **Keep it**.

**The Journal section** "Alchemist's codex" sits beside the herbarium and the smith's ledger
(`21-tab-journal.js:155-179`), with "3 of 7 known" counts and an "Unknowns first" filter.

### 6.9 In progress

Until the **shared In progress section** lands (built by the enchanting lanes, plan §16.11), the
shelf's **In progress** group lists:
- setting potions and transmutes;
- a game-time countdown in words ("ready on day 16", "ready in 5 hours");
- **Collect** when ready.

The countdown moves with game time, never with real time. The group is the herb satchel's
Steeping group (`31-bench-satchel.js:72-81`), generalised. When the shared section ships, the
group becomes a link to it, and the rows move there (contracts §10).

### 6.10 Footer, perks, settings

As the forge:
- the clock and the place line;
- the Alchemist level and its mastery line;
- **Formulary**, **Codex** and Steady mode.

The perk picker is `36-bench-perks.js` with an `alchemist` track: Potency, Duration, Quality,
Yield and **Containment**. Containment's description is in words: "−1 DC on volatile steps, and
mishaps one die smaller."

Settings gains an **Alchemy** volume on the sound buses, beside Bench and Forge.

---

## 7. The 3D stage

### 7.1 What is built new

Under `play/static/js/alchemy-stage/`, beside `bench-stage/` and `forge-stage/`, on their
renderer:

| File | Contents |
|---|---|
| `00-glass.js` | Lathe **profiles** for every vessel: vial, round-bottom flask, cucurbit, alembic head, receiver, retort bulb, aludel, crucible, bain-marie pot, stoneware pot. The glass and glaze materials. The inner profile each liquid uses, offset inward by the wall thickness. |
| `01-apparatus.js` | The kit and the lab: tripod, spirit lamp, funnel and cloth, vial rack, athanor, sand bath, workbench, shelves, fume hood. **Bent necks and beaks via the forge's `sweep`.** |
| `02-liquid.js` | The liquid model (§7.3): fill plane, surface colour, turbidity, meniscus, bubbles, the pour stream, drips along a beak. |
| `03-lab.js` | The laboratory room: floor, back wall and shelves, window light from the clock. Field-kit scenes reuse `03-ground.js`. |
| `04-fx.js` | Vapour, the condensing drip, the calx whitening, the sublimate crust growing on the aludel's upper wall, the colour-stage wash for Transmute, **the flare**, and glass ticks. |

All of it is built in code, like the herb tools and the forge's families: no models, no
downloads, and within the herb plan's 5 MB budget with room to spare.

### 7.2 Glassware

- **The glass material** starts from `05-props.js:30`: `alpha .1`, fresnel `.55`, high
  specular, the alpha pass at order 3.
- **Thickness reads through the fresnel rim.** It is already in the shader (`01-gl.js:187-191`),
  so a vial's edge is brighter than its face.
- **No refraction.** The renderer has no environment map or screen-space pass, and adding one
  is out of scope.
- **Lathe profiles** are piecewise curves with a crease flag, the `K.mesh.lathe(profile, seg,
  crease)` contract (`02-meshes.js:41`).
- **The product vial** reuses `props.product(method, liquid)` (`05-props.js:155-185`), with the
  liquid colour from the server, so a bottled potion flies to the shelf in its own colour.

### 7.3 Live liquid: the fill plane

The technique is the standard one for liquid in a bottle without a fluid simulation: the Minions
Art liquid shader and its many ports ([S] https://steveimm.id/posts/liquid-wobble/ ;
https://www.patreon.com/minionsart/posts/unity-liquid-18245226). It works like this:
- **Clip at a world-space fill height.** The liquid mesh is the vessel's inner lathe. Fragments
  above the fill plane's world Y are discarded, so the level is one uniform. Animating it is one
  number per frame.
- **Back faces are the surface.** With culling off (it is already off: `01-gl.js` never enables
  `CULL_FACE`), the back faces seen through the cut are drawn in a flat **surface colour**,
  lighter than the body. `gl_FrontFacing` is WebGL 1 and needs no extension. This fakes the
  liquid's top without a cap mesh.
- **Wobble** (optional, Steady and reduced motion turn it off). The fill plane tilts a little
  against recent motion: a pour, a stir, a set-down. It is damped to rest in under a second, so
  it never keeps the render loop alive.
- **Turbidity** blends the body from clear (low alpha, the colour as a tint) to cloudy (high
  alpha, the existing `uPattern` noise at a fine scale). Dissolve's "stir until clear" is this
  number falling.

**The shader change** is additive and owned by one lane (U3):
- new uniforms `uFillY` (default `1e9`, meaning no clip), `uSurf` (the surface colour) and
  `uTurbid` (default 0);
- one branch, taken only when `uFillY` is below `1e8`.

**Herb and forge materials never set them**, so their output is unchanged. A test proves it: the
shader source still compiles with the defaults, and every herb and forge material leaves
`uFillY` at its default.

### 7.4 What the server drives, and what the stage only draws

The server sends, per step state:
- the active vessel;
- the **mix colour** (an RGB, computed from the inputs' `color`s weighted by amount);
- the **level** (0 to 1 of the vessel's volume);
- the **turbidity**;
- for Distill, the receiver's level.

During a game the strip reports progress, and the stage animates **between** the server's start
and end states. For example, Distill moves the cucurbit's level down and the receiver's level up
as the hearts run. The page never invents a colour. It only interpolates between two the server
sent. "The page never computes a number" holds: these are presentation values the server
authored.

### 7.5 The flare

The owner's Q9.4. **On a failed roll that triggers the mishap** (the server's roll response says
so):
- **Full motion:**
  - a bright additive burst at the vessel;
  - the glow light (`uFlarePos/Col`, which exists) spikes and decays over 400ms;
  - smoke particles rise;
  - the vessel shows a crack line (a decal on the glass), and its liquid level drops;
  - the stage canvas alone shakes, 250ms;
  - the brass verdict word reads **FLARE**.
- **Reduced motion:** the glow spike and the word only, with no shake, smoke or particles. The
  crack still shows, because it is a state, not a flourish.
- **It never blocks.** It runs on its own layer with `pointer-events: none`, and any click skips
  it (the one-second rule).

A **minigame overshoot** of the reaction gauge (§6.4) gets a smaller cousin: a puff of vapour and
a hiss, no crack, no shake. It is feedback about quality, not a mishap.

### 7.6 Performance

- **Render on demand**, as both stages do (`wake` is the only `requestAnimationFrame` site).
- **The spirit lamp's flicker and the bubbles run only while a game is live.** Idle, the flame
  is steady, the liquid is still, and the bench draws no frames.
- A test pins **zero frames over 10 idle seconds**, as `test_forge_stage.py:763` does.
- The alchemy chunk and its stage **load on first open**, not with the table. The forge still
  loads with the table (forge contracts §15.1); alchemy does not repeat that.

---

## 8. Copy

Plain, in-world, sentence case, **no em-dashes or en-dashes in new strings**. The lane greps
for both.

| Label | Intent |
|---|---|
| Roll Craft | start a step |
| Experiment | bottle with no formula chosen |
| Assay / Assay it / Keep it | test a reagent |
| Ask an alchemist | learn from a keeper |
| Learn from a writing | copy a formula |
| Take it apart | learn from a potion in hand |
| Collect | take finished work from In progress |
| Work it / Take one out | the second-volatile confirm |
| Formulary / Codex | the two books |
| Save recipe / Load | recipes |
| Close | leave the bench |

Reasons follow the good grammar the forge set:
- "It needs a laboratory: distilling takes a still."
- "It does not dissolve in spirits. Try water or vinegar."
- "A finished potion cannot go back into the glass."
- "Fire 3, capped at 2 by your level."

---

## 9. Minigames

The rules are in plan §7 and §8. Every game has:
- mouse, keyboard and Steady mode;
- a 2-second first-time card;
- a generous start (both sweeps' strongest finding);
- **rarer reagents narrowing the window** (the forge's "better metal, tighter window", from
  Giants' Foundry);
- a run of about 6 seconds **(proposed)**.

Bands are the operation's own (art §5), and are widened by the `catalyst` and `apparatus`
working traits (plan §5.5). All band numbers are **(proposed)**.

| Game | On the stage | In the strip | Mouse | Keyboard | Steady mode |
|---|---|---|---|---|---|
| **Calcine** | The crucible over the flame. The charge darkens, then whitens as it calcines, and fuses into slag if held too hot. | Heat gauge with a "calcining" band (the bar reads dull, calcining, fusing); a whiteness meter fills while in band. | click to feed the flame, release to bank | ↑ / ↓ | heat drift ×0.5; holds become toggles |
| **Dissolve** | The solid sinks into the solvent in the flask. The liquid clears as you stir. Stirring too hard splashes and fizzes. | Reaction gauge (the fizz) with a working band; a clarity meter rises while in band. | drag in circles at the guide's pace | ← → alternate in rhythm | stir rate ×0.5; band ×1.6 |
| **Distill** | The cucurbit on the athanor. Vapour climbs into the head, runs down the beak, and drips into the receiver, whose level rises. | Heat gauge on the still head, bands **heads, hearts, tails** (proposed 70-78, **78-88**, 88-100 °C, from the whisky cut's 78.3-82 °C widened for play, art §5). Score is the share of the run taken in hearts. | click to swap the receiver at the cut, and to feed or bank the fire | Space to swap; ↑ / ↓ heat | the hearts band ×1.5; drift ×0.5 |
| **Filter** | Pour the solution onto the cloth in the funnel. The filtrate runs clear below, and the precipitate gathers on the cloth. | A pour-rate bar with its band; over it, the funnel overflows (a puff); under it, the time thread runs out. | press to pour, release to stop | hold Space, or toggle in Steady | pour as a toggle; band ×1.6 |
| **React** | Drop by drop from a dropper into the flask. Each drop blooms colour; the liquid churns as the reaction climbs. | **Reaction gauge**: each drop raises it, and it settles over time. Keep it in the band until the reaction completes. | click per drop | Space per drop | the gauge settles ×1.5; band ×1.6 |
| **Sublime** | The solid heats in the aludel, and a crystal crust grows on the cool upper wall. Scrape it when it is thick, before it falls back. | Heat gauge with a **narrow** sublimation band; then a crust meter, and a scrape when it is ready. | click to strike in band, click the crust to scrape | Space; S to scrape | band ×1.5; crust growth ×0.5 |
| **Bottle** | The product pours into the vessel, and the stopper or seal goes in while the vapour is low. | A pour level to the vessel's mark, then a stopper ring timed against the reaction gauge's lull. | press to pour, click the ring | Space to pour, Space on the ring | pour as a toggle; ring window ×1.6 |
| **Transmute** | The Great Work in the aludel turns black, then white, then yellow, then red. Seal each stage as it peaks. | A colour-stage track named in words, **nigredo, albedo, citrinitas, rubedo** (art §5). Press as each stage peaks; out of order scores nothing. | click at each peak | Space at each peak | stages last ×1.5; a peak window ×1.6 |

- **Assay has no minigame**, like tasting and the forge's assay: a short wisp of colour as the
  pinch meets a drop of reagent on a glass slide, then the result in words.
- **The Transmute game is played when the work is put in.** Its result is the tier; the product
  then waits a day in In progress (plan §9). Nothing waits on a real-time clock.
- **No game depends on the cursor art.** Each draws its own reticle: the dropper tip, the stir
  guide, the swap mark.

---

## 10. Motion and juice

Every animation has a reason (feedback, a state change, or hierarchy). Short and reduced-motion
forms are given throughout.

| Event | Stage | Chrome | Reduced motion / Short |
|---|---|---|---|
| Open the bench | the lamp or athanor lights, and the glass fades in | layer fade 200ms | fade only |
| Switch method | the active vessel swaps: the old lifts out and the new sets down with a glass clink (450ms) | strip underline slides 160ms | crossfade 120ms |
| Drop into a step | the item arcs to the vessel; a powder hisses in, or a liquid pours and the level rises | the slot fills | the slot fills; the level jumps |
| A good beat (a drop in band, a clean cut) | a bloom of colour, a soft chime | the pip fills | the pip and the chime |
| Out of band | a dull fizz, vapour puffs | the hint changes in words | the same, with no motion |
| Tier up | the liquid glints | the ladder rung brightens 180ms | instant |
| Flawless | the brass word "Flawless" over the glass, gilt motes, 250ms shake of the stage canvas only | none | the word only |
| Product lands | the vial lifts and flies to its shelf row in its own colour (500ms) | the row pulses once | the row highlights |
| Failure, no mishap | the liquid clouds and dulls, and the stage dims 30% for 600ms | the loss line in words | dim only |
| **Failure with a mishap** | **the flare** (§7.5) | the mishap line in words, with what it did ("1d6 fire: 4 to you") | glow spike and word only |
| Formula found by experiment | the vessel glows gold once | a new line in the formulary, "Found by experiment" | the line only |

**The one-second rule** holds:
- flourishes run in `#rv-layer` with `pointer-events: none`;
- any click skips them;
- the shelf, the formula card and Close stay live.

---

## 11. Sound

A new **`alchemy`** bus, beside `bench` and `forge` (`sound.js:42`), with its preference
`sound.alchemy` (`prefs.js`) and a Settings slider in `home.html`. All sounds are synthesised,
like the forge's (`Sound.machine()` precedent): no recorded assets needed to start.

- `alchemy.open`, `alchemy.method.<name>`, `alchemy.drop.<form>` (powder, liquid, glass),
  `alchemy.roll`;
- `alchemy.pour`, `alchemy.stir`, `alchemy.bubble`, `alchemy.boil`, `alchemy.drip`,
  `alchemy.fizz`, `alchemy.hiss`;
- `alchemy.chime` (a Transmute stage, pitched up the colour stages);
- `alchemy.stopper` (a cork squeak, or a wax press);
- `alchemy.glass.tick`, and `alchemy.crack`;
- `alchemy.flare` (a low whump, then a crackle);
- `alchemy.tier.up`, `alchemy.flawless`, `alchemy.fail`, `alchemy.land`, `alchemy.assay`;
- `ambience.laboratory`: a low athanor roar and the odd glass tick, played through
  `Sound.loop`. At the field kit, the biome ambience.

Unknown events are silent (the forge contract), so callers never guard.

---

## 12. Engineering shape

**Files:**
- `play/static/js/table/50-alchemy-shell.js`: the layer through `BenchCore.mount`, the flow, the
  method strip, the stage column, the roll, the game call, and the footer. It mirrors
  `40-forge-shell.js`.
- `51-alchemy-shelf.js`: the shelf, with the In progress group.
- `52-alchemy-stage.js`: the adapter onto `alchemy-stage/`, as the global
  `window.AlchemyStage`.
- `53-alchemy-card.js`: the formula card (vessel, formula picker, count, slots, drawbacks,
  stakes, tag).
- `54-alchemy-books.js`: `window.AlchemyBooks.formulary(host)`, `.codex(host)`,
  `.card(materialId, anchorEl)`.
- `play/static/js/alchemy-games/*.js`: one file per game (8).
- `play/static/js/alchemy-stage/*.js`: §7.1.
- `play/static/css/alchemy.css` and `alchemy-games.css`, after `bench.css`, using existing
  tokens only (the forge's `test_forge_games.py:204` pattern pins this).
- `play/alchemy_views.py`: the API (contracts §8). Routes go **above any `api/alchemy/<id>`
  catch-all**; the herb bench's route-order bug, pinned by `test_bench_routes`, is not repeated.

**The server contract** (the three laws):
- **The page sends** the method, the material ids per role (inputs, solvent, vessel), the
  formula id or `experiment`, the picked traits, the batch, and the game score (0..1).
- **The server answers with:**
  - the info line, the DC and the "need N" figure;
  - the mishap and toxic lines;
  - the possible-formulae count;
  - the slots, with every trait's legality and reason;
  - the mix colour, level and turbidity;
  - the clamped score and the tier;
  - the product, its computed specs, and its caster level and price;
  - the mastery lines and discoveries;
  - the time passed.
- **The page never computes a number.** That includes the grade sum, the count and the colour.

**Lazy loading:** the alchemy chunk and its stage load on first open (§7.6).

---

## 13. Verification (before it is called done)

1. **Live, on scratch data** (`PATHFINDER_GM_DATA`, never `%LOCALAPPDATA%`), every method at
   1280×720, 1600×900, 1920×1080, 3440×1440 and under 1180px, at the field kit and at a
   laboratory. Screenshots go in the lane report.
2. **Reduced motion and Steady mode:** every game is playable; the lamp does not flicker; there
   is no wobble and no shake; the flare is its short form.
3. **Keyboard only:** open the bench, pick a method, drop, choose a vessel and a formula, roll,
   play, collect, close.
4. **Contrast:** dimmed shelf rows, reasons, the formula card's `--alarm` lines, the tag, and
   both gauges' labels, measured against their real backgrounds, at AA.
5. **The one-second test** and **idle zero frames** (the herb plan §13 and the forge's tests),
   including the lamp and the liquid.
6. **The shader change leaves the herb and forge stages unchanged.** Screenshot the herb bench's
   steep jar and the forge's anvil before and after lane U3 and compare them.
7. **End to end in play**, the path the player actually clicks (the standing "trace the real
   path first" instruction):
   - make an alchemist's fire at the field kit;
   - throw it at a creature on the map;
   - read the touch attack, the 1 splash on its neighbour and the next-round burn in the combat
     log;
   - extinguish it on another target;
   - brew a potion of cure light wounds at Fine, read CL 2 and 100 gp on the tag, drink it, and
     read the heal;
   - fail a volatile step by 5 or more on purpose (a scratch character with a low bonus), and
     read the mishap's damage on the sheet.

   The rules lanes' tests prove the engine; this proves the bench and the table.
8. **Packaged build:** open the bench in `win-unpacked` on a throwaway data dir, because a
   feature that only works under `runserver` is not finished.

---

## 14. Pre-flight (the skill's matrix)

| Check | Status |
|---|---|
| Brief read and dials | §0, split by surface |
| Redesign audit | §2 (from code, and lane U1 drives it live first) |
| Zero em-dashes in new strings | §8; the lane greps for `—` and `–` |
| One theme, one accent | dark; gold only. Liquid colour, the gauge scales and the swatches are scene content (§4) |
| Shape lock | 3px; circles for dials, rings, swatches |
| Button contrast, no CTA wraps | Roll Craft, two words |
| Labels above fields | the shelf search, the formula picker |
| No eyebrows; plain group headings | §6.2 |
| One label per intent | §8 |
| Motion motivated, reduced motion | §10, §7.5 |
| No idle loop | §7.6 |
| Empty, loading, error states | §6.2, §6.3 |
| No filled-track progress bars | both gauges have bands, not a filled track; the clarity and crust meters are pips; the mastery line has none |
| Icons from a library | game-icons.net, credited; names confirmed by U1 |
| No emoji | retired (§2) |
| z-index | the herb plan's scale; the alchemy layer at 35 |
| Mobile collapse | §5.3 |
| No colour-only meaning | essences are words; volatile and toxic carry a glyph and a word; gauges carry numbers |

---

## 15. Build order

| # | Lane | Contents | Depends on |
|---|---|---|---|
| U1 | **Alchemy shell, flat** | the layer through `BenchCore.mount`, the method strip with level and place locks, the shelf with In progress, the formula card (vessel, formula, count, slots, drawbacks, stakes, tag), Roll and the d20, results to the shelf, the old tab's "moved" card, the icon list for the owner. **Playable end to end, flat, before any 3D.** | rules lane 6 API |
| U2 | **Games** | the eight games in the shared frame; the reaction gauge in `33-bench-games.js`; the colour-stage track; Steady mode | U1 |
| U3 | **Stage** | `alchemy-stage/`: glassware, apparatus, the lab room, live liquid (the shader extension), fx, the flare | U1 (parallel with U2) |
| U4 | **Books and perks** | the Formulary, the Codex card and Journal section, the dangerous-assay confirm, the alchemist perk track | rules lanes 5 and 6 |
| U5 | **Sound** | the `alchemy` bus, its events and the setting | U2 |

**Why this order** is the herb and forge plans': a flat, working bench first, so the rules
lanes can be checked in the real UI before any modelling. The minigames are where tuning
happens, and tuning on a flat build is cheapest.

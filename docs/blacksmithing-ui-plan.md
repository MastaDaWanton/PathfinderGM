# Blacksmithing bench: the UI and 3D plan

Drafted 2026-10-03. This is the interface half of `docs/blacksmithing-revamp-plan.md`; the rules,
numbers and engine lanes live there. It is planned to the same depth as
`docs/herbalism-ui-plan.md`, and uses the same two design skills (`design-taste-frontend`,
`frontend-design`) under the owner's standing instruction: **keep the colours, images and
textures; change structure and behaviour** (redesign, preserve).

Sources:
- the audit of today's Blacksmithing tab, done live on scratch data at 1600×900 (§2);
- `docs/blacksmithing-prior-art.md` (heat colours, quench and temper bands, what games softened);
- the herb bench as built (`play/static/js/table/30-36`, `bench-stage/`, `bench-games/`), read for
  what can be reused (§3).

---

## 0. Design read and dials

**Design read.** A crafting workbench in a desktop game, for a solo Pathfinder player who wants
the craft to feel physical. The language is the app's own dark leather, brass and candlelight.
Vanilla JS in the table's numbered modules, the existing `theme-v2.css` tokens, and the herb
bench's hand-written WebGL stage (the app bundles no third-party JS; `32-bench-stage.js` header).

**Mode.** Redesign, preserve. The skill's default stack (React, Tailwind, Motion) is set aside by
its own "one system per project" rule, exactly as the herbalism UI plan §0 records.

**What is different from the herb bench, in one line:** the forge is about **heat and assembly**.
The two things a smith reads are the colour of the metal and how the pieces fit, so the stage
gets a live heat source and the right column becomes a **work order** with piece slots.

| Surface | VARIANCE | MOTION | DENSITY | Why |
|---|---|---|---|---|
| **Stage** (anvil, hearth, the work, games, sparks) | 6 | **8** | 2 | "Big and juicy" lives here, and only here. Fire, sparks, steam and the glow of hot metal are the boldness this screen spends. |
| **Chrome** (rack, method strip, work order, footer) | 4 | **3** | 6 | Matches the table and the herb bench. Hover and press feedback only; nothing moves on its own. |

---

## 1. Decisions that bind this plan

| Question | Owner's answer (2026-10-03) |
|---|---|
| Layout | **Its own bench**, built from the herb bench's parts, laid out for smithing: anvil at the centre, hearth to its left, rack and trough to its right. |
| Stage | **The kit on the ground, or a smithy.** In the field: camp anvil, bellows and field hearth on the biome ground. At a smithy: stone floor, furnace glow, quench trough. Hot metal glows by real heat colour and **is a light source**. |
| The work | **Built from its pieces.** Procedural families (straight blade, curved blade, axe head, hammer head, spearhead, haft, grip, guard, plate, mail), joined on the anvil and coloured by material. No per-weapon models. |
| Icons | **Engraved icons as for herbs**, with a small colour swatch so steel and bronze differ. |
| Heat | Inside each game; shown as colour, a labelled bar and a number. |

**Carried over from the herb bench:** the full-screen layer over the table (z 35), the method
strip, the d20 throw and brass verdict word, the minigame strip with Steady mode, the quality
ladder on a paper tag, the perk picker, app-wide sound, the one-second rule, render on demand.

---

## 2. Audit of today's Blacksmithing tab

Looked at live, scratch data, 1600×900, with Iron through Smelt, Forge and Quench.

**What is there:**
- **Ingredients** panel: a forage card, a search, an "Only what I am carrying" toggle, then
  **all 112 materials** as tiles with emoji glyphs (⛏ 🔥 💧 🔨), most greyed "beyond your tier".
- **Crafting Chain:** eleven method stations in a grid, the chain row, a free-text
  **Shaping** field ("axes-mortar, air-repeater…"), and **a cauldron** as the drop target.
- **Preview:** the green name banner reads **"Iron Work"**; Stages 3, DC 14, **Chance 0%**;
  "Cannot be made" lists "You have no Iron", "Forging needs a shape: say what is being made",
  "The forge is cold"; Effects: **"No mechanical effect could be read out of these."**
- Footer: Craft, Save recipe, "Blacksmith 1 · common / mundane", a 0 / 25 MP bar.

**Defects seen while auditing:**
- Selecting the Blacksmithing tab shows the **"Herbalism is at the table now"** card for about
  two seconds before the forge panels replace it.
- The shelf **jumps its scroll position** on every click.
- The cauldron and "Put something in the pot." are the herb bench's metaphor on a forge.

**Keep:** the tooled leather panels and clasps; Cinzel small caps; reasons in words ("The forge
is cold: smelting and forging burn fuel, and there is none in the charge" is good copy); the
itemised check terms; "What the source says"; the candle cursor (no game depends on its hotspot).

**Retire on the forge:** emoji glyphs; the green banner (a second accent); the eleven-station
grid; the free-text Shaping field (the engine names every shape); the all-materials wall; the
cauldron.

---

## 3. What is reused, and what is new

Measured by reading the herb bench (lines; "herb words" = mentions of herbs, satchel, mortar,
tasting):

| Module | Lines | Herb words | Reuse |
|---|---|---|---|
| `bench-stage/00-math.js`, `01-gl.js`, `03-ground.js`, `04-particles.js` | 1,191 | 5 | **As is.** Renderer, maths, biome ground, particles. |
| `bench-stage/02-meshes.js` | 258 | 4 | As is, plus new procedural meshes (§7.3). |
| `33-bench-games.js` (the strip frame) | 813 | 4 | **As is.** The forge games plug into the same frame. |
| `34-bench-tag.js` (paper tag, ladder) | 246 | 3 | As is; the forge adds the build card under it. |
| `36-bench-perks.js` | 253 | 9 | Parameterised by track. |
| `30-bench-shell.js` | 1,240 | 41 | Split: the layer, focus, keys, clock and footer become a shared `bench-core`; the herb-specific half stays. |
| `31-bench-satchel.js`, `35-bench-herbarium.js` | 561 | 53 | Patterns reused; the forge gets its own rack and ledger. |
| `05-props.js`, `06-tools.js` | 1,175 | 19 | Herb tools. The forge gets `forge-stage/` beside them. |

**The shell split is the first UI lane.** Without it the forge copies 1,240 lines of shell, and the
two benches drift apart: one Esc behaviour, one focus trap, one clock, one footer.

---

## 4. Tokens

**No new colours, fonts or textures.** The forge maps onto the bench's semantic layer:

```css
.forge {
  --bench-ground: var(--sunk);
  --bench-ink: var(--ink);
  --bench-quiet: var(--dim);
  --bench-accent: var(--gold);        /* the one accent: active method, Roll, ceiling */
  --bench-warn: var(--alarm);         /* ruined materials, a reactive assay */
  --bench-light: var(--candle);
  --bench-radius: 3px;
}
```

**Heat colour is content, not chrome.** The blackbody colours (dark red through yellow-white)
appear **only inside the 3D scene and on the heat gauge's scale**. Chrome stays gold. That is the
same rule the herb plan applied to liquid colour: colour that belongs to the thing lives in the
scene, never as a second accent on the panels.

**Material swatches** (the owner's choice): an 8px disc beside the engraved icon, filled with the
material's colour (iron grey, bronze, copper, gold, silver, mithral's blue-white). The disc is
content, like heat. It never carries meaning alone: the name is always beside it.

**Quality** reads by metal and weight, never by hue, exactly as the herb tag's ladder (Crude
`--ash` … Flawless `--gilt` plate), with the name in words. Masterwork gets its word too: the
Superior rung reads **"Superior · masterwork"** (the one middle dot on that line).

**Icons** from game-icons.net (CC BY 3.0, credited in About, the manual and
`docs/asset-licences.md`), rendered as gilt masks like the herb icons:

| Group | Icons |
|---|---|
| Forms | ore, ingot, bar, blank, plate, haft, grip, guard, rivets, mail, scales |
| Consumables | coal, charcoal, flux pouch, quench bucket, oil flask |
| Methods | furnace, crucible, anvil and hammer, quench, temper (flame), fold, whetstone, assemble (hammer and rivet), brush (finish), double bar (strengthen), magnifier and spark (assay) |
| States | hot, quenched, tempered, folded, strengthened ×N, slaggy, brittle |

---

## 5. Layout

### 5.1 The layer

The forge opens over the table as its own full-screen layer (`#forge`, `role="dialog"`,
`aria-modal="true"`, z 35), sharing `bench-core` with the herb bench. Opens from a **Smithing**
button in the left column, beside Herbalism; the old `/craft/` Blacksmithing tab becomes a card
that opens it, as the Herbalism tab did. Esc, focus trap, the scene clock and closing behave
exactly as the herb bench.

### 5.2 Desktop grid, 1600×900

```
┌ #forge ────────────────────────────────────────────────────────────────────────────────────┐
│ Smithing  [Smelt][Alloy][Forge][Quench][Temper][Fold][Hone][Assemble][Finish][Strengthen][Assay] [Close] │ 56px
├ rack 280px ──────┬─ stage, minmax(620px, 1fr) ───────────────────────┬─ work order 340px ────┤
│ Search your rack │                                                    │ ┌ piece slots ──────┐ │
│ [What fits ▾]    │   hearth glow ▸   ANVIL with the work on it   ◂ trough │ Head   ▣ Iron bar ×2│ │
│ Ore              │   (field kit on forest floor, or smithy stone)     │ │ Haft   ▣ Ash haft   │ │
│  ▣● Iron ore  4  │                                                    │ │ Fittings ▢ empty    │ │
│ Bars             │   the blade blank glows cherry red, lights the     │ └────────────────────┘ │
│  ▣● Iron bar  2  │   anvil and the smith's tools                       │ ┌ paper tag ─────────┐ │
│  ▣● Steel bar 1  │                                                    │ │ Longsword          │ │
│ Hafts and grips  │ ┌ minigame strip ─────────────────────────────────┐│ │ ─ ladder ─         │ │
│  ▣ Ash haft   1  │ │ HEAT ▕▓▓▓▓▓░░░▏ 880°C cherry  Space to strike  Fine ││ │▸ Fine ◂ ceiling   │ │
│ Fuel             │ └──────────────────────────────────────────────────┘│ └────────────────────┘ │
│  ▣ Charcoal   6  │ 1 blank. 45 minutes. DC 15, you need 9 or better.  │ Build: damage +1      │
│ Can't use now    │              [ Roll Craft ]                        │ attack −1, hardness +2│
│  ▢ Mithral bar   │                                                    │ [ show the sum ]      │
├──────────────────┴────────────────────────────────────────────────────┴───────────────────────┤
│ Day 14, 6:20pm   At the field kit   Blacksmith 1 ──── 8 / 25   Recipes   Ledger   Steady ○   │ 44px
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

- **Grid:** `280px minmax(620px, 1fr) 340px`; rows `56px 1fr 44px`. The stage is wider than the
  herb stage because the anvil, hearth and trough are a wider tableau than one tool.
- **The work order** (right) replaces the herb tag's single column: piece slots on top, the paper
  tag with the ladder under it, the build summary at the bottom.
- **The footer** names **where you are** ("At the field kit" / "At Brannoc's smithy, 1 sp an hour"),
  because that decides which methods and materials are open.

### 5.3 Other sizes

As the herb plan §4.3: the 3440×1440 ultrawide caps content at 2,000px with the ground filling
the width; 1280×720 narrows the rack to 240px and the work order to 300px, and the method strip
goes to icons with names on hover and focus; under 1180px the stage stacks on top at 56vh; under
768px a single column, every game with a tap form.

---

## 6. Components

### 6.1 Method strip

Eleven methods in craft order. Locked methods show a lock and the reason in words: "Blacksmith 2"
or **"Needs a smithy"** (new: a location lock, not only a level lock). Keys 1-9, 0 and - pick;
arrows move.

### 6.2 The rack (left)

The herb satchel's pattern, for metal:
- Only what you **carry**. Groups by form: Ore, Ingots, Bars, Blanks and plates, Hafts and grips,
  Fittings, Fuel, Flux, Quenchants, Treatments, Finished work.
- A row: engraved form icon, the material swatch, name, count, rarity rim, state badges (hot,
  quenched, folded, strengthened ×2, slaggy, brittle), the quality word for worked pieces, and a
  "?" while anything is unknown.
- **Can't use now** carries its reason: "needs a smithy", "Blacksmith 2 for rare", "slaggy: fold
  or flux it first".
- Hover, focus or "?" opens the **ledger card** (§6.7).
- Bars track tenths after an assay ("Iron bar 1.9").
- Empty state for the method: "Nothing you carry can be forged." with **Buy at the market** (when
  in a settlement) and **Everything I carry**.
- **No scroll jump**: the list re-renders in place and keeps its scroll position (today's defect).

### 6.3 Stage

- **Composition:** the anvil at centre, the hearth (field hearth or furnace mouth) to its left,
  the quench trough and tool rack to its right, camera at about 40° looking down the anvil.
- **Ground:** the field kit stands on the biome ground from `03-ground.js` (forest floor, snow,
  sand...). A smithy has its own ground: **stone flags** for a town smithy, **packed earth with a
  plank floor** for a founded one **(proposed)**. CC0 textures (ambientCG or Poly Haven), 1K, at
  most 300 KB each, recorded in `docs/asset-licences.md`.
- **Light:** the hearth is the key light, warm and flickering (a slow, low-amplitude intensity
  wobble, off under reduced motion). **Hot metal is a second light**: its colour and intensity
  follow its temperature (§7.2), so a blank at yellow heat lights the anvil and dims as it cools.
  Day or night fill from the scene clock, as the herb stage.
- **The work** sits on the anvil, built from its pieces (§7.3).
- **Info line** in plain words under the stage: "1 blank. 45 minutes. DC 15, you need 9 or better."
- **Roll Craft** is the only gold-filled button, disabled with its reason beside it ("Put a bar in
  the head slot").
- **WebGL fallback:** the engraved icon at 160px on the ground colour, and every game runs in its
  2D strip, as the herb bench.

### 6.4 Minigame strip

The herb bench's strip frame, unchanged in shape (meter left, input hint centre, live tier right,
time thread on top). Forge games add **the heat gauge**: a horizontal bar with the named bands
(dark red, cherry, orange, yellow, white) printed under it, a needle for the metal's temperature,
the target band outlined (shape, not only colour), and the number in °C. When the metal leaves the
band the hint changes to "Reheat: R" in words.

### 6.5 The work order (right)

**Piece slots** at the top: Head, Haft, Fittings (or Body, Fastenings, Lining for armour; the
labels follow the shape picked at Forge or Assemble). Each slot is a drop target and a button:
- filled: icon, swatch, name, passes ("strengthened ×1"), and "× from rack" to remove;
- empty: "Drop a bar here, or press Enter on one in the rack";
- not used by this item: "No fittings on a quarterstaff", greyed with the reason.

Under the slots, the **paper tag** (`34-bench-tag.js`): the product name, form and the quality
ladder with your ceiling, the Superior rung marked "masterwork".

At the bottom, the **build summary**: the final numbers in one short line per target ("damage
+1, attack −1, hardness +2") and the book powers in words ("strikes as cold iron"), then
**Show the sum**, which opens the build card (§6.6).

### 6.6 The build card

The worked sum from the revamp plan §6.4, as a table: one row per target, one column per piece,
then raw, after quality and the negative cut, and the final number with **"rounded toward zero"**
written under it. Book effects listed separately ("from the head, by the book: strikes as cold
iron"). This is where the owner's rounding rule stops being a mystery. The same card opens from the
item's row on the character sheet and in the inventory.

### 6.7 The ledger card and the Journal ledger

The herbarium's counterpart. The card: icon and swatch, name, where it is found or bought, known
properties with how each was learned ("assayed, day 14", "taught by Brannoc"), one line per unknown
("unknown"), and two actions: **Assay** (a sliver, 10 minutes) and **Ask a smith** (when one is in
the scene). Assaying a reactive metal opens a confirm in `--alarm` words: "Noqual reacts badly to
testing. Assay it anyway?" with **Assay it** and **Keep it**.

The Journal section lists every material met, with "3 of 7 known" counts and an "Unknowns first"
filter, beside the herbarium.

### 6.8 Footer, perks, settings

As the herb bench: the clock, the place line (new), Blacksmith level and mastery line, Recipes,
Ledger, Steady mode. The perk picker is the herb picker with the forge's four perks (Potency,
Hardening, Quality, Yield). Settings gains a **Forge** volume on the sound buses beside Bench.

---

## 7. The 3D stage

### 7.1 What is built new

Under `play/static/js/forge-stage/`, beside `bench-stage/`, using its renderer:

| File | Contents |
|---|---|
| `00-heat.js` | Temperature → colour and light (§7.2), the cooling curve per material, reheat. |
| `01-props.js` | Camp anvil, smithy anvil, field hearth, furnace mouth, bellows, quench bucket and trough, whetstone wheel, crucible and tongs, tool rack. Low-poly, built in code like the herb tools. |
| `02-families.js` | The procedural item families (§7.3). |
| `03-smithy.js` | The smithy room: floor, back wall with the furnace mouth, a hanging lamp. Field-kit scenes reuse `03-ground.js`. |
| `04-fx.js` | Sparks on a strike (reusing `04-particles.js`), quench steam, the vapour-jacket bubble, temper colour run, slag. |

### 7.2 Hot metal

- **Colour from temperature.** A small table from the sweep's §3.1 (black red 426–593 °C through
  white 1,315+), interpolated, drives the emissive colour of the work's mesh and the colour of a
  point light at the work. Below about 450 °C the emissive is off and the metal shows its own
  material colour.
- **Cooling.** Each game cools the work along a curve (faster for thin pieces and for
  `narrow_window` metals). Reheat (R, or click the hearth) pushes it back toward the hearth's
  temperature over a second or two.
- **Accessibility.** The colour never carries the game alone: the heat gauge (§6.4) shows the band
  and the number. Under "Steady mode" cooling runs at half speed.

### 7.3 Built from pieces

A family is a parametric mesh: length, width, curve and taper for a blade; head profile for an
axe or hammer; length and grip wrap for a haft; guard shape. The finished item is the head, haft
and fittings joined at fixed sockets. Material decides the surface: base colour, roughness, a
faint pattern for folded or pattern steel (a procedural banding in the shader), a hammer-scale
texture on unhoned work. Quality shows as surface finish (rough at Crude, mirror at Flawless).

Weapons map to families through their table entry (category, damage type, hands), so all 456 rows
get a shape without a model each. Armour shows as the body piece only (a plate, a fold of mail, a
row of scales) on the anvil, not a whole suit. **(proposed)**

### 7.4 Performance

Render on demand, as the herb stage (`wake` the only requestAnimationFrame site). The hearth's
flicker is the exception that would keep the loop alive, so it **only runs while a game is live**;
idle, the hearth is lit steadily and the bench draws no frames. A test pins zero frames over 10
idle seconds, as the herb plan §13.6.

---

## 8. Copy

Plain, in-world, sentence case, no em-dashes in new strings (the herb plan §8 rules).

| Label | Intent |
|---|---|
| Roll Craft | start a step |
| Assay / Assay it / Keep it | test a material |
| Ask a smith | learn from a keeper |
| Show the sum | open the build card |
| Reheat | in-game, back into the band |
| Save recipe / Load | recipes |
| Close | leave the forge |

Reasons keep today's good grammar: "The forge is cold: there is no fuel in the charge", "Forging
needs a smithy for rare metal", "It is slaggy: fold it or flux it at the smelt".

---

## 9. Minigames

Rules in the revamp plan §11. Every game: mouse, keyboard, Steady mode, a 2-second first-time card,
generous to start (the sweep's strongest finding), and **better metal narrows the window**.

| Game | On the stage | In the strip | Mouse | Keyboard | Steady mode |
|---|---|---|---|---|---|
| **Smelt** | Pump the bellows; the furnace mouth brightens; slag runs when you tap. | Furnace heat gauge with the smelting band; a tap marker when the slag is ready. | click to pump, click the tap | Space pumps, T taps | heat drifts at half speed; pumps as toggles |
| **Alloy** | Two crucibles pour into one; the stream thins as you ease off. | A ratio bar with the alloy's window outlined (bronze about 88/12). | hold to pour, release | hold Space, or toggle in Steady | pour ×0.5 speed, window ×1.5 |
| **Forge** | Strike the glowing blank on the marked spots; it lengthens and tapers. | The heat gauge with the forging band (cherry to orange); a beat ring for each strike. | click on the ring | Space; R to reheat | cooling ×0.5; ring window ×1.6 |
| **Quench** | Lift the blank from the fire; plunge; steam boils (the vapour jacket), then quiets. | The heat gauge with the plunge band; then a hold meter for how long it stays under. | click to plunge, release to lift | Space down and up | toggles instead of holds; bands ×1.5 |
| **Temper** | The oxide colour runs along the cleaned steel: straw, brown, purple, blue. | A colour track with the target band named (straw for an edge, blue for a spring). | click to pull from the heat | Space | colour run ×0.5 |
| **Fold** | Fold, then weld at yellow heat; sparks fly; the layer count rises. | Heat gauge with the welding band; fold count pips. | click to strike at welding heat | Space; R to reheat | cooling ×0.5 |
| **Hone** | The edge on the whetstone; a bright line follows your pass. | An angle band (hold the edge steady) and pass pips. | drag along the edge | ← and → hold the angle, Space passes | the angle band ×1.6 |
| **Assemble** | The head slides onto the haft; peen the rivets; the guard seats. | A beat ring per rivet and a fit meter. | click on the beat | Space | window ×1.6 |
| **Finish** | Brush the bluing or the etch on in even strokes; the colour takes. | A coverage map of the piece; strokes fill it. | drag strokes | arrows paint the next strip | strokes cover ×1.5 |
| **Strengthen** | Two bars stacked, welded at white-yellow heat without burning; they become one. | Heat gauge with the narrow welding band, the burning zone hatched above it. | click to strike in band | Space; R to reheat | band ×1.5 |

**Assay has no minigame** (tasting has none either): a short spark or touchstone animation on the
stage, then the result in words.

**No game depends on the cursor art.** Each draws its own reticle (the hammer face, the edge
line), as the herb games do.

---

## 10. Motion and juice

Every animation has a reason (feedback, state change, hierarchy). Short and reduced-motion forms
throughout.

| Event | Stage | Chrome | Reduced motion / Short |
|---|---|---|---|
| Open the forge | the hearth flares from embers, the anvil fades in | layer fade 200ms | fade only |
| Switch method | tools swap on the rack (old lifts out, new drops, 450ms) | strip underline slides 160ms | crossfade 120ms |
| Drop into a slot | the piece arcs to the anvil and seats; a metal clink | the slot fills | slot fills, no arc |
| A strike in band | sparks, a 1.5° camera nudge for 60ms, the anvil rings | the pip fills | pip and ring only |
| Out of band | dull thud, no sparks | the hint changes to Reheat | same, no motion |
| Quench | a plume of steam, a hiss, the glow dies | none | the glow dies, no steam |
| Tier up | the work glints | the ladder rung brightens 180ms | instant |
| Flawless | the brass word "Flawless" over the anvil, gilt sparks, 250ms shake of the stage canvas only | none | the word only |
| Product lands | the item lifts from the anvil and flies to its rack row (500ms) | the row pulses once | the row highlights |
| Failure | the work cracks or dulls, the stage dims 30% for 600ms | the loss line in words | dim only |

**The one-second rule** holds: flourishes run in `#rv-layer` with `pointer-events: none`; any click
skips them; the rack, slots and Close stay live.

---

## 11. Sound

On the app-wide buses (the herb bench's `Sound` module), a new **forge** bus:
- `forge.open`, `forge.method.<name>`, `forge.drop.<form>`, `forge.roll`;
- `forge.strike.hit` with **pitch by hardness** (bronze rings lower than steel, adamantine
  highest), `forge.strike.miss` (a dead thud);
- `forge.bellows`, `forge.quench` (hiss by bath: brine sharpest, oil softest), `forge.temper`,
  `forge.grind`, `forge.rivet`, `forge.weld`;
- `forge.tier.up`, `forge.flawless`, `forge.fail`, `forge.land`, `forge.assay`;
- `ambience.smithy` (a low furnace roar) or the biome ambience at the field kit.

Synthesised, like the device sounds (`Sound.machine()` precedent): no recorded assets needed to
start.

---

## 12. Engineering shape

**Files:**
- `play/static/js/table/29-bench-core.js`: the shared layer, focus, keys, clock, footer (split
  out of `30-bench-shell.js`; the herb bench keeps working on top of it).
- `play/static/js/table/40-forge-shell.js`, `41-forge-rack.js`, `42-forge-stage.js` (the
  adapter onto `forge-stage/`), `43-forge-order.js` (slots, tag, build card),
  `44-forge-ledger.js`; the games frame is `33-bench-games.js` reused.
- `play/static/js/forge-games/*.js`: one file per game.
- `play/static/js/forge-stage/*.js`: §7.1.
- `play/static/css/forge.css`, after `bench.css`, existing tokens only.
- `play/forge_views.py`: the forge API, routes above any `api/forge/<id>` catch-all (the herb
  bench's route-order bug, pinned by `test_bench_routes`, is not repeated).

**The server contract** (the three laws): the page sends the method, the material ids per slot,
the batch and the game score (0..1). The server answers with the tier, the clamped score, the
product and its **computed build** (every target's sum, as the build card shows it), the mastery
lines, discoveries and the time passed. **The page never computes a number**, including the build
sum: the card draws what the server sent.

**Lazy loading:** the forge chunk and its stage load on first open, never on the table's first
paint.

---

## 13. Verification (before it is called done)

1. **Live, on scratch data**, every method at 1280×720, 1600×900, 1920×1080, 3440×1440 and under
   1180px, at the field kit and at a smithy. Screenshots in the lane report.
2. **Reduced motion and Steady mode:** every game playable; the hearth does not flicker; no
   shake.
3. **Keyboard only:** open, pick a method, fill the slots, roll, play, close.
4. **Contrast:** dimmed rack rows, reasons, the tag, the build card and the heat gauge labels,
   measured against their real backgrounds, AA.
5. **The one-second test** and **idle zero frames** (herb plan §13), including the hearth.
6. **End to end in play:** forge a cold iron longsword at a smithy, wield it, hit a creature with
   DR/cold iron, and read the full damage in the combat log. Forge a mithral shirt, wear it, and
   read the ACP and max Dex on the sheet. (The rules lanes' tests prove the engine; this proves
   the path the player actually clicks.)
7. **Packaged build:** open the forge in `win-unpacked` on a throwaway data dir.

---

## 14. Pre-flight (the skill's matrix)

| Check | Status |
|---|---|
| Brief read and dials | §0, split by surface |
| Redesign audit | §2 |
| Zero em-dashes in new strings | §8; the lane greps for `—` and `–` |
| One theme, one accent | dark; gold only. Heat colour and swatches are scene content (§4) |
| Shape lock | 3px; circles for dials, rings, swatches |
| Button contrast, no CTA wraps | Roll Craft, two words |
| Labels above fields | the rack search |
| No eyebrows; plain group headings | §6.2 |
| One label per intent | §8 |
| Motion motivated, reduced motion | §10 |
| No idle loop | §7.4 |
| Empty, loading, error states | §6.2, §6.3, as the herb plan §7 |
| No filled-track progress bars | heat gauge has bands, not a filled track; mastery line has none |
| Icons from a library | game-icons.net, credited |
| No emoji | retired (§2) |
| z-index | the herb plan's scale; the forge layer at 35 |
| Mobile collapse | §5.3 |

---

## 15. Build order

| # | Lane | Contents | Depends on |
|---|---|---|---|
| U1 | **Core split** | `29-bench-core.js` out of the herb shell; the herb bench re-verified unchanged | none |
| U2 | **Forge shell, flat** | the layer, method strip with level and place locks, the rack, the work order with slots and the build card, Roll and the d20, results to the rack, all with the engraved-icon flat stage. **Playable end to end before any 3D.** | U1, rules lane 5 API |
| U3 | **Games** | the ten games in the shared frame, heat gauge, Steady mode | U2 |
| U4 | **Stage** | `forge-stage/`: props, smithy room, hot metal as light, the procedural families, fx | U2 (parallel with U3) |
| U5 | **Ledger and perks** | ledger card, Journal section, assay confirm, perk picker for the forge | rules lane 6 |
| U6 | **Sound** | the forge bus and its events | U3 |
| U7 | **The old tab** | `/craft/` Blacksmithing becomes the card that opens the forge; fix the two-second Herbalism-card flash on the other tabs while there | U2 |

**Why this order** is the herb plan's: a flat, working forge first, so the rules lanes can be
checked in the real UI before any modelling; the minigames are where tuning happens, and tuning on
a flat build is cheapest.

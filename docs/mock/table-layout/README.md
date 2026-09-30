# Table layout mock

A clickable layout study for the play table, to set beside the real one. It is **not part
of the app**: no Django view, no URL, nothing under `play/`, and `docs/` is not bundled
into the executable (see `pathfindergm.spec`). Nothing on it reaches the engine or a model.

## Opening it

From the repository root:

```
python -m http.server 8765 --bind 127.0.0.1
```

then open <http://127.0.0.1:8765/docs/mock/table-layout/>. It has to be served. Opened
as a file, the browser refuses the icon fetches, and the icon tiles come up empty. The
page links the real fonts, icons, cursor and `scene3d.js` under `play/static/` by
relative path, so it must be served from the root, not from this folder. Its materials
(leathers, paper, metal, the room and the device) are its own, in `textures/` (see "The
texture pass" and "The boiler room and the engine device").

The dashed strip across the top is the mock's own and not part of the design. **Viewing**
switches between Kesst Vayr (the recording's rogue) and Ysolde Marrach (the fixture
wizard), and says in words what the switch changes. **Wanted in Zhilvarnia** shows the shut
ways and their reasons. **Start again** goes back to the gate with the story and the gear
as they began.

A link can open any state directly, for sending the owner straight to a thing:
`#char=ysolde&mode=spells`, `#mode=map&view=3d&turn=1`, `#mode=map&view=places`, `#mode=equipment&fit=shoulders`,
`#talk=1`, `#hide=1`, `#wanted=1`.

## The texture pass

The owner, on the version below: "while attempting to keep the leather and bronze look get
textures from the internet for everything replacing mine with better ones. id like to
improve the quality of the look without changing the layout or the 3d styling." Every
material image is now a CC0 photograph, prepared by `textures/prepare.py` (resize, crop,
tint, and re-light by the page's one lamp; it downloads nothing) and credited file by file
in `textures/CREDITS.md`. Nothing under `play/` changed. The layout, the geometry, the
bevels, shadows, page stack, pressed controls and coins, the colour tokens and every
behaviour are as they were; the stylesheet's changes are image URLs, texture scales, the
gilt's new metal layer, and the room's depth layers.

- **The room** was a worn plank desk (Poly Haven, Wood Table Large), not black leather.
  (Since replaced by the owner's own boiler room: see the next section. The desk's reasons
  are kept here because they set the rules the boiler room was held to.)
  The owner on the first two tries: "the background texture is notably worse, I was hoping
  for something interesting, give it some depth but keep it dark". Those were leathers
  toned to the old texture's spread, which flattened them to wallpaper; one, a scarred
  black leather, read as a cobweb over the open ground of Spells and Equipment. The desk
  has its depth from its own normal map, lit by the page's lamp, so every plank edge, crack
  and nail hole is lit from the same side as the bevels; its occlusion map darkens the
  seams; a vignette falls to shadow at the far edges and a low warm pool rises where the
  embers do (both CSS, so they cost nothing and stay centred). It is cover-fitted and never
  repeats. Why it beats the grimoire leather: that was a black photograph whose light came
  from wherever it was photographed, and whose detail was mostly lost under the page's
  dimming; the desk keeps the room dark (the dim labels on it measure 5.00:1 at the worst
  2%, where the old measured 3.63) while showing a real surface lit the way the page is,
  and a book on a desk is what the table is.
- **Leathers**: the card leather (Brown Leather) and the sides' tooled leather (Fabric
  Leather 02) are real grain toned to the old colours, where the old card leather varied
  by 4 levels in 255.
- **The page** is paper now (ambientCG Paper 006) at the old page's dark, so the story's
  contrast is unchanged (12.16:1 at the median, was 12.19).
- **The metal**: the clasps and bosses keep their exact silhouettes and sizes, so they sit
  exactly where they did, but are re-made in photographed bronze and brass (ambientCG
  Metal 047 B and 048 C) and re-lit by the page's lamp. The old ones were one render
  mirrored into four corners, so its light was mirrored too. The gilt rings, gilt edges and
  coin rims keep their gradient and gain a brass grain over it; the four gilt-edged panels
  now draw the edge as a background clipped to their 3px border (a `border-image` takes one
  image, and the edge now needs two).
- **Contrast** was measured on every reading surface with its text removed, at the median
  and at the brightest 2% (the worst case for light text), before and after. Every surface
  holds 4.5:1 for the dimmest text on it. Two failed before and now pass: the desk under
  the book (dim labels 3.68:1, now 4.66) and the top bar (3.73, now 4.75). The fix was a
  tint on the card leather, not a token.

| Surface | Dimmest text | Before, median / worst 2% | After |
|---|---|---|---|
| Page (story) | story #d8cdb2 | 12.19 / 11.06 | 12.16 / 11.05 |
| Page head | dim #93866e | 4.93 / 4.66 | 4.97 / 4.58 |
| Desk under the book | dim #93866e | 4.21 / **3.68** | 5.12 / 4.66 |
| Top bar | dim #93866e | 4.33 / **3.73** | 5.29 / 4.75 |
| Sides (tooled) | side dim #b3a488 | 6.89 / 6.37 | 6.91 / 6.11 |
| Framed card | dim #93866e | 5.30 / 4.87 | 5.45 / 5.08 |
| Talk tray | talk dim #a99a80 | 6.93 / 6.86 | 7.12 / 7.02 |
| Equipment head | ink #e8ddc4 | 11.28 / 10.22 | 13.77 / 12.61 |
| Worn and wielded | side dim #b3a488 | 6.86 / 6.37 | 6.89 / 6.11 |
| Room (the ground) | dim #93866e | 5.53 / **3.63** | 5.20 / 5.00 |

Not replaced: the candle cursor (a drawn candlestick, not a material) and the fonts.

## The boiler room and the engine device

The owner supplied two of their own images on 2026-09-29 and cleared both for this public
repository (`textures/CREDITS.md`): a boiler room, "take this image and make it the
background", and a brass mechanism, to become a device that shows where a turn is. The
owner's notes that followed are answered point by point below.

### The room

- `room-boiler.jpg` is the owner's picture at 1800x1800, cover-fitted and never tiled,
  `background-position: 22% 47%` so the door and the lamps stay in view on a wide window
  and on a phone. `fixed`, so it does not scroll with the page.
- It is dimmed in CSS, not in the file: a wash from 65% black at the top to 70% at the
  foot, the vignette, and the embers' warm pool. The embers and the candle are as they were.
- One tint in the file, a highlight roll-off above a luminance knee of 0.22: its lamps and
  white gauge faces glow instead of blowing through the dimming. Without it the dim labels
  over the white gauge held 3.53:1 at the brightest 2% under the first dimming, and 3.93
  even under a deeper one, which had already sunk the room. The fix is the dimming and
  the roll-off; no token changed.
- Contrast, measured with the text removed, at the median and at the brightest 2% (the
  worst case for light text), against the desk of the pass before. Every other surface is
  unchanged to the second decimal.

| Where | Text | 1440, desk before | 1440, now | 1024, desk before | 1024, now |
|---|---|---|---|---|---|
| Open ground (Equipment) | dim #93866e | 5.20 / 5.00 | 5.29 / **4.64** | 5.38 / 5.01 | 5.22 / **4.62** |
| Open ground, reply line | dim #93866e | 5.24 / 5.00 | 5.24 / **4.59** | 5.45 / 5.28 | 5.30 / **4.64** |
| Open ground | gold #ddc48e | 10.93 / 10.53 | 11.12 / 9.77 | 11.32 / 10.54 | 10.97 / 9.72 |

  The whole visible ground at once (every pixel of room the panels leave, the dimmest text,
  dim #93866e): 4.85 at 375x812, 4.77 at 1024x768, 4.73 at 1440x900, worst 2%. All hold
  4.5:1; the room costs about 0.4 of the desk's margin, the price of a picture with lamps.

**Lifted again, and the story's leaf made see-through (2026-09-30).** The owner: "make the
text box background slightly transparent. also the background needs to be lighter again
only the background and not the UI".

- The room: the wash from 65% / 70% to 60% / 65.5%, the vignette from 49% / 86% to 44% /
  83%: **+16% mean luminance at 1440, +17% at 1024, +18% at 375** on top of the first
  lift (the room alone, every child of `body` hidden). The same proof as before: the
  computed styles of 32-109 UI elements per view identical, every changed pixel on the
  open room. Text on the open room still holds with the scrims already there: the
  Equipment reply line 4.78 at 1024 and 4.89 at 1440, "50 things" 4.87 and 5.06, worst 2%.
- The text box, read as the narration box (the book's page under the story, what the
  owner called "the narration box" the note before; the pen was left as it was): its fill
  is the page's own colour at 70% (`--leaf-a: .7` on `.bookin`), over a 4px
  `backdrop-filter` blur of the room. Only the fill: the text, the ring, the clasps and the
  head are not faded; the head keeps its opaque paper, so the see-through starts under its
  rule. The paper's grain (a spread of 5 levels in 255) gives way to the room's own. Where
  `backdrop-filter` is unsupported the room shows through unblurred at the same strength,
  measured too. Contrast of the story's colours over it, median / worst 2%, text removed,
  embers held, the device hidden:

| Width | story #d8cdb2 | player #8fb0c8 | dim #93866e | dim, no blur |
|---|---|---|---|---|
| 1792 | 11.97 / 10.81 | 8.29 / 7.49 | 5.29 / 4.78 | 5.29 / 4.74 |
| 1440 | 11.97 / 10.82 | 8.29 / 7.50 | 5.29 / 4.78 | 5.29 / 4.76 |
| 1024 | 11.97 / 11.01 | 8.30 / 7.63 | 5.29 / 4.87 | 5.29 / 4.83 |
| 375 | 11.97 / 10.74 | 8.29 / 7.44 | 5.29 / 4.74 | 5.29 / 4.74 |

  Opaque, the dim text measured 4.88 / 4.90 / 4.99 / 4.83. The floor is about 40%: the
  dim text holds 4.50 at 1792 there, and falls to 4.41 at 30%. 85% was tried first and the
  room did not show at all; 70% is where it shows, faintly, as the owner asked ("slightly").

**Lifted, the room only (2026-09-29).** The owner: "brighten background a bit as well",
then "i only want the background to be lighter not the UI". The room's own layers are the
only thing that changed: the wash went from 71% / 75% black to 65% / 70%, and the vignette
from 55% / 90% to 49% / 86% (all four are now `--room-*` variables on `body`, the one
element that paints the room). Measured with every child of `body` hidden, so the shot is
the room alone: **+19% mean luminance at 1440 and 1024, +20% at 375** (+31-34% in mean
L*). No overlay sat over both the room and the UI, so there was nothing to split: the
embers, the candle's pool and shade are unchanged and draw over everything as before.

The UI is unchanged: in the Table and Equipment views at all three widths, the old and new
page were shot with animations held and every changed pixel was mapped. All of them lie on
the open room (the gutters, the ground around the panels, the Equipment page's open
ground); the handful counted inside element boxes are rounded corners and boxes clipped by
a scrolled column, where the room shows through. The computed backgrounds, colours,
shadows, filters, borders, opacity and text shadows of 32-109 UI elements per view are
identical before and after.

Text on the open room is the Equipment page's list head and its reply line, and nothing
else at any of the three widths (a script walked every text node for a painted ancestor).
Under the lifted room the reply line's dim words fell to 4.36:1 at 1024, worst 2%, so a
local scrim now sits behind that head and the reply line only (`.eqlisthead`, `.eqsay`:
32% dark, feathered by its own shadow); the room was not dimmed back.

| Text on the open room | Before the lift | Lifted, no scrim | Lifted, with the scrim |
|---|---|---|---|
| Reply line, 1024 | 5.28 / 4.63 | 5.18 / **4.36** | 5.38 / 4.93 |
| Reply line, 1440 | 5.31 / 4.80 | 5.23 / 4.58 | 5.42 / 5.02 |
| "50 things, A to Z", 1440 | 5.39 / 4.76 | 5.32 / 4.54 | 5.49 / 4.99 |
| "50 things, A to Z", 1024 | 5.22 / 4.89 | 5.10 / 4.70 | 5.36 / 5.16 |
| "Everything you carry", 1440 | 11.12 / 9.96 | 10.93 / 9.47 | 11.37 / 10.67 |

### The device

**Cut out, not generated.** `prepare.py` isolates the mechanism from its grey studio
backdrop with PIL and numpy only (no model, no download): a smooth cubic surface fitted to
the backdrop well clear of the device (mean residual 2.5 levels), each pixel scored by its
distance from that surface and by colour (brass is yellow, the backdrop grey); below the
foot only colour counts, so the cast shadow on the floor is not kept; the device's own
component flood-filled and its holes closed; the edge eroded 1px and feathered 0.9px, and
the backdrop's colour taken back out of the part-covered edge pixels, so no grey halo sits
on a dark page. Hand fixes: the floor shadow rule above, and the tab (below). The frame is
lit by the page's one lamp (a gentle fall from upper left to lower right; the photograph
was lit flat). Five files, all in one box so they stack exactly: the frame, the chamber
behind the opening (the photograph's own movement at a third of its brightness), the
lip's shadow into the opening, the tab, and `device-geometry.js` (the measured points).

**Gears.** Two procedural SVG gears in the opening, 10 and 16 teeth on one module (8.5
photograph px), so the centre distance is 8.5 x (10 + 16) / 2 and the small gear turns
16/10 = **1.6** times for each turn of the large one, the other way. The large gear turns
1.4 times a second at speed. The mesh offset is worked out from the tooth counts (tooth
meets gap at the contact), so other counts mesh too. Each gear's brass gradient is
counter-rotated every frame, so its light stays in the room while it turns. First tried at
8 and 12 teeth on a larger module: at the drawn size they read as toy sprockets.

**States** (`#device[data-state]`):

| State | Gears | Lever | Lamp | Tab | Steam |
|---|---|---|---|---|---|
| idle | still | up | green, calm | in | none |
| running | turning | down | amber | in | a puff every third of a turn of the large gear |
| waiting (a roll owed) | eased to a stop | down | amber | in | a thin trickle, one small puff every 0.95 s |
| ready | ease to a stop, then a heartbeat | pops up with an overshoot | green, flaring then settling | slides out, glowing green | a burst at the halt |

Idle is lever up and a calm green: the table is ready for you, which is true whenever no
turn is running. The tab goes back in when the green settles to that idle glow, 2.6 s
after the lever, so it is out only while the green is the answer to a turn (see the open
questions).

**The ready sequence**, in the model's own clock (fixed 1/120 s steps, so a still frame of
any moment can be drawn exactly with `#devicet=ms`): the gears ease out over 520 ms
(never a snap), a burst of steam as they stop, a heartbeat of 700 ms ("the gears should
stop a heartbeat before the lever lifts up"), then in one beat the lever pops up on a
damped spring (to about -52 degrees against its -46 rest), the lamp turns green and
flares, and the tab slides out on a stiffer spring (overshooting by about a tenth of its
travel). The prose does not wait for any of it: it is already on the page from the moment
the response landed (the owner's ruling, below). Measured gear-stop to lever: **700-709 ms** in
the model in every run (one 8.3 ms step of rounding), and 653-741 ms on the wall clock in
eleven live turns in headless Chrome, where a capture or a slow frame holds a step for a
frame; 699-723 ms in the preview pane's own browser. The twelve-frame proof (screenshots, not committed) shows
the gears at 0 degrees a second at 3740 ms with the lever still down and the lamp amber,
and the lever moving, the lamp green and the tab coming out at 4440 ms.

**The tab** (the owner, circling it on a crop: "add a glowing bit that pops out green ...
it should only pop out when its green"). It is the small plate on the top plate's left
edge, standing 16px proud of the body in the photograph. `prepare.py` cuts it off the frame
at x < 530 (the crevice where it enters the body stays with the body, as the slot) and
lengthens it along its face so it can stand 16 photograph px further out than the
photograph shows and still reach into the slot, overshoot included. It lies under the
frame, so pulled in (29 photograph px to the right) none of it shows. Out, its face is lit
green (a copy of the piece through a colour matrix, screened onto it) and a green halo
outside the body blooms onto the brass beside it and spills faintly onto the frame or
panel beyond. The glow follows how far out it is, so it dims as it goes in. Out, it stands
10px proud of the body at 1440, 7px at 1024 and 3.6px on a phone, where, the device being
turned, it comes out upward.

**Steam** (the owner: puffs "in time with the gears", then "increase the smoke a bunch").
Soft sprites, each three lobes and a core lit from the lamp's side, moved by transform and
faded by opacity only, `pointer-events: none`. Running: a puff every third of a turn of the
large gear (about four a second; 16 in a 3.8 s turn), sizes varied, each living 1.7 s,
rising 2.7 device widths up the gutter (227px at 1440) and drifting left, away from the
story, billowing as it goes. The halt: four big puffs 70 ms apart that billow through the
heartbeat. Waiting: a lazy trickle. Idle: nothing but the burst's last wisp dispersing.
Where it reaches, measured at its densest (a frame with the steam against the same frame
without it, animations held): at 1440 x 212-351, and never nearer than 24px to any text or
control (the portrait's label) or 44px to the book's title; at 1024 x 249-352, nearest
34px (the title). It stays within the device's own right edge, so it never crosses the
story, and no text has smoke over it, so no text's contrast changes. On a phone it stays at
the device's foot (x 141-174, y 84-117), clear of the world's name and the bar's buttons.
Tried first: one radial gradient sized to the sprite's far corner and clipped round, which
scaled up for the burst into a grey disc with a hard rim; and puffs born at a third of their
size, which lost their density before they had any size, so a running turn showed wisps.

### Where it sits

The owner, in order: "too small ... it needs to be further up ... there is plenty of
space", then "have the device just below the top right corner". It is mounted on the
book's left gilt edge in the gutter between the left side panel and the centre column,
its top 24px below the side panel's top-right corner: just under the book's top-left
clasp's corner piece, so the corner and the clasp's arm along the top still show, and it is
bolted over the clasp's arm that runs down the edge. It takes the place of the book's left
boss (hidden where the device is). It is absolute: nothing in the layout moved, and the
gutter was not widened.

**On every tab with the left panel (2026-09-30).** It was a child of the book, so it
existed only on the Table tab (measured 0x0 on Map, Sheet, Equipment, Trade and Journal),
though Map keeps the pen and a turn can be taken there. It now belongs to the stage, the
table's frame, and CSS alone places it: its box is the centre column's grid area, the one
the book, the map and the sheet's pages fill (each at most 880px and centred in it), so it
hangs on the gilt edge of whatever the column holds, at every width, with nothing measured
in script. (A first version measured the column in script and set the offset once; a page
whose script ran before its layout settled kept a stale offset, -35,137 at 1792, off the
window's edge.) Where the window is wider than the panels and an 880px column, the column
is centred and the device hangs on its edge in the wider gutter, as it always did:

| Width | Table, Map and Sheet | Left panel's right edge | Centre column's left edge |
|---|---|---|---|
| 1024x768 | 291,161.4 60x173 | 300 | 318 |
| 1280x800 | 267,157 84x242 | 284 | 302 |
| 1440x900 | 267,157 84x242 | 284 | 302 |
| 1792x958 | 421,157 84x242 | 284 | 456 |
| 1920x1080 | 485,157 84x242 | 284 | 520 |
| 2560x1440 | 805,157 84x242 | 284 | 840 |

With the sheet hidden: 45,161 at 1024, 245,157 at 1440, 421,157 at 1792 and 485,157 at
1920 (the book's edge, as before). On the Table tab at 1440 and 1024 the device is the
same to the pixel as when it lived in the book (0 of 34,968 and 21,300 pixels differ round
it against 5b342c1; its box is 405d6d4's). No text or control is under it on Table, Map
(Flat and Places) or Sheet at any of the six widths. Measured on every tab:

| Tab | 1440x900 | 1024x768 |
|---|---|---|
| Table | 267,157 84x242 (as before, to the pixel) | 291,161 60x173 (as before) |
| Map (Flat, 3D, Places) | 267,157 84x242 | 291,161 60x173 |
| Sheet | 267,157 84x242 | 291,161 60x173 |
| Equipment, Trade, Journal | not shown: these tabs have no left panel and no pen | not shown |
| Table or Map, sheet hidden | 245,157: on the centre column's own left edge, as before | 45,161, as before |

On a phone it stays in the head bar on every tab. On Map and Sheet the content was moved
clear of it: the Map frame's left padding is 58px (the book's own), where at 26px the
device covered the first letter of "The ground"; at 1440 the Sheet's cards pad 48px on
the left, where the device covered the start of "Combat", the initiative box and the
weapons' names. At 1024 nothing was under it. The Map frame's left boss is hidden like the
book's. A turn taken on Table and followed through Map, Sheet, Equipment, Journal and back
ran as one sequence: the model's clock, the gears' angle and the steam carried across every
switch (the device's log shows one running, one ready, one halt and one lever-up), and it
is only drawn while its tab shows it.

| Width | Device | Box (x, y) | Clear of, on its left | Clear of, on its right |
|---|---|---|---|---|
| 1440x900 | 84 x 243px | 267-351, 157-399 | the side panel's content (the portrait frame, 264) by 3px; the tab out reaches its gilt line | the title (360) by 9px |
| 1024x768 | 60 x 173px | 291-351, 161-334 | the sheet column's content (270) by 21px, by 18px with the tab out | the title (366) by 15px |
| 375x812 | 30 x 87px, turned | 151-238, 91-121 | the world's name (ends 141) | Talk (starts 248) |

At 1024 it grew from 52px to 60px when it moved up: 60px had been refused while it hung
halfway down, because its top then covered the clasp's tip; at the top it is bolted over
that arm by design. On a phone there is no gutter, so it lies on its side in the head bar
between the world's name and Talk, turned a quarter so the lamp, lever and tab are at the
right and its lit side stays the top; the bar's height is its own and `scrollWidth` is 375.

### The border, 50% thicker

The owner: "make the border 50% thicker". Every gilt edge is 1.5 times its width, the
bevels and shadows scaled with it, and the corner fittings re-aligned to the new ring:

| Edge | Before | After |
|---|---|---|
| The book's ring and the framed cards' rings | 4px | 6px |
| Gilt-edged panels (the sides, the sheet column, Talk, the Equipment figure) | 3px | 4.5px (Chrome paints 4px at 1x, 4.5px at 2x) |
| The pen's (the desk's) edge | 1px | 1.5px |
| Clasp inset / boss inset | 24px / 21px | 25px / 22px, then registered on the ring (below) |

On a phone the border-drawn edges stay 3px (at 4.5px a 375px screen lost 3px of every
panel's content); the rings are drawn over their padding and cost no width, so they are
6px there too.

**The clasps registered on the ring (2026-09-29).** The owner marked the Map frame's
top-left corner: a line along the ring's top edge, another down its left edge, and an
arrow from the corner piece pointing down and in to the frame's inner corner. Read as:
the clasp's arms should lie along the gilt ring, not ride above and outside it, with the
corner piece over the frame's corner. Measured in the clasp image, the arms' centre lines
(the top arm at row 31.5 of 247, the side arm at column 27.6 of 340, drawn 96px wide) sat
3px above and 4.8px outside the ring's centre line; now both lie on it, the clasp 28px in
from the top or foot and 29px in from the side of its box (`--clasp-in-y`,
`--clasp-in-x`). The bosses were 2px out the same way and now centre on it too (24px). It
is one rule, so it holds on every framed surface (the book, the Map frame, the framed
cards) at every width.

**One border, not two (2026-09-30).** The owner: "there is some extra border or something
on the right and bottom of the narration box". It was the page stack from the 3D pass:
seven hard 1px offsets in the book's `box-shadow` (alternating #2e2519 and #574731-ish
browns, 1px to 7px out), meant as the leaves beneath the page along the edges away from
the lamp, which read as a second, 7px band outside the gilt ring on the right and the foot
only. It is removed; the book's depth is its cast shadow alone (`--sh-3`, down and right
from the one lamp, onto the desk and the room), and the ring is its outer edge on all four
sides. It was on the book only: the Map frame and the framed cards never had it. Measured
on 2x crops of the four corners at 1440 and 1024: the top-left is unchanged to the pixel,
and in the other three every changed pixel lies in that 7px strip outside the book's box,
none inside it, so the ring, the clasps and the bosses did not move.

### What the real app needs to adopt it

The owner's ruling, 2026-09-29, on the two questions this section used to end with
(holding the prose back for the device, and showing the turn's stages): "dont hold back
narration for it and dont worry about displaying what its doing." So the device knows only
what the app's client already knows, and never delays the story. The mock does the same:
one running state from Say to the response (compressed to about 4 s), the prose on the page
the moment the response lands, and the halt, heartbeat, lever, green, tab and burst playing
out alongside it; a roll owed is the one pause, because the engine really is waiting on the
player. Measured in a live turn: the prose is on the page at the response, and the lever
lifts about 1.2 s later (the 520 ms halt and the 700 ms heartbeat), with the tab out and
the steam's last burst still rising while the text is read.

- **running** is `busy(true)`: around the `post("/api/say")` in `takeTurn`
  (`04-combat-and-turns.js`), and likewise around `/api/roll` and `/api/combat/act`.
  `scene.busy` is not this flag (it is why the crafting hub is shut); the server's 409
  `data.busy` is the mid-turn lock.
- **the response** (the POST's reply, the `table:posted` event in `post()`, `02-state.js`)
  calls `Device.ready()` and renders at once. `ready()` returns nothing to wait on: the
  halt-then-green sequence runs on its own.
- **waiting** is a response with `s.awaiting` set (`showPopup`), resumed by `/api/roll`.
- The device's files are `device.js`, the `.device` rules in `mock.css`, the markup in
  `index.html` (`#device`, `#dv-slot`) and the five `textures/device-*` files.

## What changed in the second pass (the owner's verdict, point by point)

> "I like the design but Im not sure about how well it functions."

1. **"I dont see a way to actually choose my gear or access the equipment page."**
   Equipment is now a tab, and the gear section on the left ends in a labelled door
   ("Equipment, 50 things carried"). The page is three parts: the shelves down the side,
   the list of everything carried, and **Worn and wielded**: In hand, then every body slot
   the engine has, in its own order and with its own labels (`rules/tables.py` `SLOTS`,
   `SLOT_ORDER_LEFT`, `SLOT_ORDER_RIGHT`, read through `rules.sheet.body_slots`). Each row
   offers what can be done to it: **Wield**, **Wear**, **Take off**, **Use**, **Drop**.
   Choosing a slot shows only what fits it ("Fits the shoulders"). The head of the page
   says, in the interface's own words, "Wield and wear from what you carry. New things are
   bought at a counter", beside a **Go to Trade** button, and the Trade page says the
   other half: "Buy and sell here. What you buy goes into your pack, and you put it on
   from Equipment." That is the owner's ruling (the outfit page is for making a
   character; in play you buy at a shop and equip what you carry), said where it is used.
   The numbers across the head (AC, touch, flat-footed, the three saves) change as
   things go on, and every combination is the engine's (see "What is real").
2. **"without permanently displayed text telling me what they are it will be painfull
   when i have more gear."** Every icon now has its name beside it, always, with its
   quantity ("Arrows x20", "Silk rope 50 ft", "Candle 6 hours", in the engine's own units
   from `goods.unit_for`). The basket is extended to 50 things for Kesst and 27 for
   Ysolde. The shelves are the trade window's own, in its order, with their counts
   (Everything, Weapons, Armour, Consumables, Gear, Magic items, Valuables), and a shelf
   with nothing on it is not offered, as in the trade window. Each shelf is A to Z.
3. **"There is no spell button ... would a spell casting character have one?"** Yes. A
   caster gets the **Spells** tab and the **Spells** button beside Say; a non-caster gets
   neither, with no empty tab and no disabled button. The switch the owner could not find
   in the old Mock menu is now the first thing on the page, and the line beside it says
   "Kesst casts no spells, so there is no Spells tab and no Spells button." Foundry's PF1
   sheet does the same in code: it removes the spells tab for an actor with no
   spellcasting profile (source below).
4. **"the sheet is missing a ton of information from the available combat maneuvers and
   weapon attacks."** Sheet mode now opens on a Combat card: initiative, base attack,
   CMB, CMD with flat-footed, speed, each with what it is made of; every carried weapon
   with each swing of a full attack, damage and type, critical range and multiplier,
   range increment, hands, finesse, the weapon's traits and weight; the full attack in a
   sentence; and all ten combat manoeuvres plus feint, each with its bonus, whether it
   provokes, what success does and its limits. A Defence card follows with AC, touch,
   flat-footed and the three saves (each with its terms) and conditions. Where the engine
   has no number the page says **not known** in italics, never a guess (listed under
   "What the engine does not know").
5. **"I dont see a map or a communication tab."** Both are back: **Map** as a tab, **Talk**
   as a tray. See "Map is a tab, Talk is a tray" below.
6. **"the floating lights and the special cursor are gone and the corner pngs are not
   aligned."** The four-layer embers, the candle's shade and pool with its flicker, and
   the candlestick cursor are copied from the real table (`table.html` `#embers`,
   `#cursorshade`, `#cursorlight`, the `cursor-candle.png` rule, and the flicker loop in
   `06-trade-and-page.js`). The clasps were wrong because the first mock invented its own
   geometry (78px corners hung 14px outside the frame, so the whole piece sat off the
   edge). They are now placed exactly as the real table places them on `.card`: the
   pseudo-element reaches 34px past the panel, 96px corners sit 24px in (a 10px overhang,
   the arm lying along the gilt), and the four 40px bosses sit astride the edge 21px in.
   Screenshot-checked at 1440x900, 1024x768 and 375x812: each corner square covers its
   frame's corner the same way at all three. On a phone the book keeps its frame and
   clasps (the old phone layout hid them) and scrolls inside it instead.
7. **"I want everything to be more 3d."** One lamp for everything, the one `scene3d.js`
   lights the board with (`LIGHT = norm(-0.42, -0.78, 0.47)`: high, left, in front), so
   every lit edge is a top or left edge and every shadow falls down and to the right, half
   as far across as down. The book is a right-hand page: a stack of leaves shows along the
   edges away from the lamp, the page dips into a gutter at the binding, the gilt ring
   has a lit lip and throws a shadow onto the page, and the clasps cast theirs. Buttons
   stand on a lip and sink into it when pressed (a 3px press, the only movement, and it
   answers the pointer). Tabs and view switches sit in a recess and the chosen one is
   pressed in. The ability scores are struck coins with a glinting rim, a beaded inner
   ring and a sunk field with the score raised off it. Leather panels are embossed, their
   headings are tooled grooves, the pen is a trough cut into the desk, spell slots are
   domed gems. No hue, palette or texture is new.

Also: the footer's duplicate **Trade** button is gone (the tab is the one door).

## Map is a tab, Talk is a tray

The open question was "should the map become a tab and Talk stay a tray". Yes to both,
for different reasons.

**Map is a tab**, and it keeps the desk. The board is something to look at and plan on,
and it needs size: the app's own side-panel copy is 18px a square, "legible only as a
shape" by its own comment (`03-offers-and-map.js`), and even its tray was a second copy
at a readable size. So in Map mode the board takes the book's place, taller than the book
is (64% of the height against 45%), with Flat and 3D, turn left and right, and the floors
("the floor", "+10 ft") above it. The desk stays under it, because choosing a square
feeds the combat bar and the pen: a map that hid them would make the player switch back
to act. The two traditions agree on size and disagree on the rest: Foundry makes the
board the whole canvas, and Owlcat and Larian open a large map on a key (BG3 also keeps a
minimap). Neither lets it cover the controls you act with.

**Places: the town, under a fog of war (2026-09-29).** The owner, pointing at the empty
space in the Map head row: "add another button that displays the map you built in your
mock-up but with the fog of war only being able to see places conected to where you have
been before. and instead of displaying the number of places the rules know you display the
number of places found by the user."

- **The button.** "Places" sits in that space as its own button, apart from Flat and 3D,
  because it is a different map: the town, not the ground you stand on. Pressed, the board
  becomes the chart; pressed again (or Flat or 3D), it is the ground again as it was left.
  The ground's own controls keep their room but go out of use (hidden by visibility, not
  removed), so nothing in the head row moves under the pointer that pressed Places.
- **The drawing** is the other mock's (`mock/table-free`, `views.js`), the owner's
  favourite piece, its code carried over as it was (`places.js`): the spring layout over
  the exits alone, solid lines for next door and dashed for the ways outside the walls,
  your place filled, the places one way from you ringed, a pressed place giving the way
  there leg by leg with its time, "About N minutes on foot", and Walk there. It is inked on
  a parchment sheet (`textures/chart-paper.jpg`, the same Paper 006 as the book's page,
  left light) framed in the panels' gilt, with the pressed place's slip in the desk's
  leather beside it. The layout is worked out once over the whole town, so a place never
  moves as more is found; the sheet's frame closes in on what is found, and the ink (rings,
  lines, names) is sized in screen pixels, so names stay 13.5px whatever the scale. A name
  goes to the right of its place, or left, above or below where it would run into another
  (at 1024 and on a phone "north crossing" ran over the warrens' ring before that rule).
- **The fog**, by the owner's ruling: on the chart is every place visited this session and
  every place one way from any of them, by name; nothing else is drawn, no place, line or
  name. A place seen but not yet visited is written in italic in a paler ink with a paler
  ring. A way out of a seen place, not yet known, is a short stroke that fades into the
  paper, dashed if it leads outside the walls: the way is there, where it goes is not.
  Lines are drawn only for ways out of places you have been. Walks go by known ways only.
- **The visited set** starts at the gate, lives in memory and in `sessionStorage` (read and
  written inside try/catch, so a private window keeps it in memory only), and grows with
  every move: the exits row (`walk()`, the one place the mock moves you) and Walk there,
  leg by leg. The mock has no place chips in the pen, so there is no third way in. Start
  again sets it back to the gate.
- **Wanted**: the ways the watch holds are drawn in rubric with a bar across them, a third
  of the way out from the place they are shut from, and no walk goes through them.
- **The header** says what was found: "9 places found, 1 of them visited" at the gate, "10
  places found, 3 of them visited" after the market and the north crossing, "all of them
  visited" when there is nothing seen and unvisited; then the other mock's own "Solid lines
  are next door; dashed lead outside the walls." Both numbers, because a player reading
  "10 found" wants to know how much of it they have walked.
- **Contrast** on the parchment, median / darkest 2% of the paper (the worst case for dark
  ink): visited names #2a2019 8.6 / 6.1; seen names #3d3024 6.9 / 4.9.
- **In the real app** the chart needs two things the engine does not keep today: a
  persisted visited-places field on the campaign (the mock's `sessionStorage` set stands in
  for it), and the exits read live at each place, as `/api/state` already returns them for
  the place you are in. New places the engine creates would then join the chart the first
  time a way to them is seen from somewhere visited, with no change to the drawing.

**Talk is a tray**, because it goes with the story rather than replacing it: the lines
are read beside the beat that produced them and answered in the pen. The owner ruled it
openable and closeable with Ignore and Take your leave in it (Q42), and Foundry keeps its
chat in the sidebar beside the board for the same reason. Where it opens was measured: the
real app's slide-over covered the beat being read (`08-conversation.js`), so here the tray
takes the numbers' column and covers nothing of the book or the pen. With the sheet
hidden it takes a column of its own beside the book. On a phone it takes the whole stage
(laid over the book alone, the log was left 30px). As in the app, it never opens by
itself; the Talk button counts new lines ("2 new"), the log is dialogue only (Q43/Q44),
and the two ways out sit below the log, never inside its scroll.

## What is real

- **Exits**: `play/exits.py exits()` run on the Pangrella fixture for all 43 places in
  Zhilvarnia at 08:00, plain and wanted.
- **Story, suggestions, people, faces, what was said, the ground**:
  `tests/replay/2026-09-25-town-tags-retag-gemma4-12b.jsonl.gz`. The story is its turns
  asking the smith about his ore, walking to the gate and asking the gate guard what lies
  north, verbatim. The scene is the save made after them, still at the gate, loaded with
  the app's own `Campaign.load` and read through `play/views.py _state` (the function
  behind `/api/state`), so the map's grid, floors, rail, tokens and the 81 reachable
  squares are exactly what the page is sent. The 3D board is `play/static/js/scene3d.js`
  itself, loaded unchanged and handed that payload; the flat board is
  `03-offers-and-map.js renderMap`'s drawing on it. The player's private corpora are not
  used.
- **Every number on the sheet**: `rules.sheet.full_sheet` (behind `/api/sheet`) and
  `Actor.summary()` for `fixtures/pc-kesst.json` and `fixtures/pc-caster.json`. Each swing
  of an attack is `Actor.attack_modifiers` at that iteration. The wizard's slots, DCs and
  prepared spells are `casting.ensure_prepared` on the fixture, and each spell's range,
  duration, save and components are the engine's.
- **What wearing a thing does**: every reachable combination of armour, shield and slot
  items (16 for Kesst, 2 for Ysolde) was put on a scratch copy of the character and asked
  of the engine (`ac`, `touch_ac`, flat-footed, `save_modifiers`). The page looks the
  answer up; it never adds bonuses itself. So "Wearing it: AC 15 to 16, touch 13 to 14"
  on the Ring of Protection +1 is the engine's arithmetic, as is AC 18 with studded
  leather, buckler and ring together.
- **The replies** to Wield, Wear and Take off are the engine's own tells, word for word
  (`_op_wear`: "Kesst Vayr draws the sap.", "puts on the studded leather. Armour class 16
  to 17."; `play/views.py wear_item`: "puts on Cloak of Resistance +1 (shoulders)."). Where
  the engine has nothing to do it with, the reply says so, starting "Mock.".
- **The conversation log**: the recording predates `scene.conversation`, so the tray's
  entries are rebuilt from the `said` lines each GM beat carried, in the log's own shape
  (numbered, speaker, addressee, beat, day). The words are verbatim.
- **Example, not real**: everything in the pack beyond the fixture's weapons and armour
  and the outfit `rules/creation.py OUTFITS` grants at first level. The names are the
  engine's own where it has one (`goods.GEAR`, the weapons table, the magic-item
  catalogue), and each is filed and described by the engine: `goods.kind_of` and the
  server's shelf rules for its shelf, `goods.describe` for its line ("for show, no effect
  in play" is the owner's wording for the engine's "has no rules for it"). The same
  recorded story is shown for both characters.

`data.js` is generated by `build_data.py` (run it from the repository root). Nothing in it
is written by hand.

## What the engine does not know (shown as "not known" or refused)

Each of these was found by asking the engine for the number and not getting one.

- **Weight and load.** Only weapons have a weight (`weight_lb` in
  `content/weapons/weapons.json`). The armour table carries a class (light, medium,
  heavy), not pounds; the gear list (`goods.GEAR`) carries prices and no weights; there is
  no carrying capacity anywhere in `rules/`. The Equipment page says "7 lb that the
  engine knows of, from the four weapons ... Load is not tracked". The real sheet already
  says "Encumbrance is not tracked." Larian had to fix the inventory's weight display
  after launch (BG3 Patch 3), which argues for putting weight in before the list grows.
- **The light crossbow's range and weight.** The curated `light crossbow` entry answers
  `range_ft: None` and `weight_lb: None`, where the shortbow answers 60 ft and 2 lb. Shown
  as "range not known".
- **A thrown weapon's to-hit.** The attack table is computed for the weapon's category
  only, so the dagger's 10 ft range comes with "thrown to-hit not known" (for Ysolde it
  would be Dex, not Str).
- **Whether a manoeuvre provokes, in play.** `MANEUVERS` carries `provokes: True` on all
  ten, and the Sheet shows it, but nothing in `rules/` reads the key: no attack of
  opportunity is rolled for a manoeuvre, and Improved Trip and the rest do not switch it
  off. The page says so under the table.
- **Feint.** There is no feint action: `rules/intents.py` files "feint" as a Bluff check,
  and `rules/classfeatures.py` says the target losing its Dexterity to AC is not
  implemented. The row shows the Bluff bonus and "not known" for the rest.
- **An off hand.** The engine holds one weapon in hand (`Actor.equipped`); the shield is
  its own body slot. The Off hand box says "one weapon at a time".
- **Taking armour or a shield off.** `_op_wear` swaps one for another; nothing sets
  armour back to none. Take off on those rows is answered with a refusal.
- **Dropping anything.** There is no drop op (disarm is the only way a thing leaves a
  hand). Drop is answered with a refusal that points at selling it at a counter.
- **Filing by name.** `goods.kind_of` reads only the eleven curated weapons, so `sling`
  (a weapon to `weapons.has`) is "gear" to it and a `wear` op would refuse to wield it;
  arrows and crossbow bolts file under Gear, not Weapons; and `kind_of("leather armour")`
  is "gear" because the table's key is `leather`, so a `wear` op naming the armour by the
  sheet's own name would be refused. A bought wondrous item ("Cloak of Resistance +1") is
  also "gear" to `kind_of`; the mock files it under Magic items by the catalogue.
- **Regard in conversation.** The recording has no talk state (it predates it), so the
  tray shows who you are talking with and the two buttons, without the regard bar.

## The design decisions (standing)

- **Redesign, preserve.** The app's `:root` tokens copied verbatim, its textures' roles
  (now filled by the photographs in `textures/`), its gilt, clasps and bosses,
  Cinzel and the Palatino stack, its radius scale (2px controls, 3px surfaces, 12px
  suggestion seals, round medallions), and its engraved-bronze letter shadows. No new
  accent colour. One lighter step of `--dim` inside the leather sides, because the app's
  own value measured 3.0:1 there.
- **The story is the centrepiece.** A gilt-framed book in the middle, a drop cap on each
  GM passage, a 58ch measure at 18px (67 characters a line on the recorded beat). The book
  keeps at least 45% of the height; past that the desk's choices scroll and the pen stays.
- **One sheet, split round the story.** Who the character is on the left (portrait,
  name, what is in hand and worn, the door to Equipment), their numbers on the right. In
  Sheet mode the right side drops Defence and Saves, because the Defence card in the
  middle has them with their terms.
- **Moves come from the exits, and everything else is a chip**, each choice once.
- **Motion.** The embers and the candle's pool are ambient and pointer-transparent. A
  button pressed sinks 3px into its lip. Nothing lifts or slides on hover, and every line
  a reply lands in is held open beforehand, so a reply never pushes a button away (see
  "Tried and dropped").
- **Phone (375px).** The tabs keep their words and the row scrolls sideways, keeping the
  chosen tab in view. The book's inside scrolls with its head. The tables of attacks and
  manoeuvres fold into one labelled card a row. Equipment puts what is worn first, then
  the shelves (a sideways row) and the list. Map keeps the board and the pen and drops the
  choices, which are in Table.

## Tried and dropped in this pass

- **"In use first" sorting.** Pressing Wear moved the row to the top of the list, out
  from under the pointer: the one kind of motion the owner has ruled out. Now A to Z, and
  what is in use is marked where it stands.
- **Reply lines that appear.** The Equipment reply, the board's answer and the tray's
  answer each pushed the controls below them when they arrived. Each now has its line
  held open.
- **The tray over the book with the sheet hidden.** It hid "the merchant" and the right of
  the page and left the log four lines. It takes its own column instead.
- **The tray over the book alone on a phone.** 30px of log. It takes the stage.
- **The figure below the list at 1024px.** Fifty rows from the Wear buttons that fill it.
  It stays beside the list down to 960px and goes above it below that.
- **Three equal columns in the top bar at 1024px.** Seven tabs, Talk and the sheet toggle
  overran; the world's name gives way instead.
- **Tilting panels towards the cursor.** Not tried here because the real app already did
  and removed it: "The tilt that was here read as seasickness once the corner clasps gave
  the panels real weight; hardware does not flex" (`table.html`). Depth comes from light
  and shadow, not from movement.

## The research used

Prior art was gathered for this pass and checked by a second pass; claims it could not
confirm are marked.

- **Foundry VTT, PF1 system** (read from source, the strongest evidence here). Inventory
  is a labelled list in sections (weapons, armour and shields, equipment, consumables,
  gear, ammo, misc, trade goods, containers; `sheetSections.inventory` in
  [config.mjs](https://gitlab.com/foundryvtt_pathfinder1e/foundryvtt-pathfinder1/-/blob/master/module/config.mjs)),
  each row with quantity, value, weight and separate carried and equipped toggles, light,
  medium and heavy load meters, and empty sections removed
  ([actor-inventory-contents.hbs](https://gitlab.com/foundryvtt_pathfinder1e/foundryvtt-pathfinder1/-/blob/master/public/templates/actors/parts/actor-inventory-contents.hbs)).
  Adopted: labelled rows, shelves, empty shelves hidden, weight shown where known.
  The spells tab is removed for an actor with no spellcasting profile
  ([base-character-sheet.mjs](https://gitlab.com/foundryvtt_pathfinder1e/foundryvtt-pathfinder1/-/blob/master/module/applications/actor/abstract/base-character-sheet.mjs)).
  Adopted: no Spells tab for Kesst. The combat tab shows BAB with iteratives, one CMB box
  and a row per attack, and does **not** list the manoeuvres one by one
  ([character-combat.hbs](https://gitlab.com/foundryvtt_pathfinder1e/foundryvtt-pathfinder1/-/blob/master/public/templates/actors/character/character-combat.hbs)).
  Here the owner asked for every manoeuvre, so the mock lists all ten plus feint: a
  deliberate divergence. Foundry shows the full-attack line only as a tooltip; the mock
  writes it out.
- **Baldur's Gate 3 patch notes** (Larian's own): Patch 2 made Equip the default click
  and added rarity filters
  ([notes](https://forums.larian.com/ubbthreads.php?ubb=showflat&Number=890331)); Patch 3
  fixed the inventory's maximum weight
  ([notes](https://forums.larian.com/ubbthreads.php?ubb=showflat&Number=901393)); Patch 7
  added a list view to the spellbook and speaker portraits to dialogue history
  ([notes](https://forums.larian.com/ubbthreads.php?ubb=showflat&Number=948592)). Read as:
  icon grids without names were walked back, weight was a late fix, dialogue history is
  its own record. A community thread calls the inventory unwieldy
  ([thread](https://forums.larian.com/ubbthreads.php?ubb=showflat&Number=894823)); its
  claim that there is no search conflicts with guides and is not relied on.
- **Solasta** players complain of per-character inventories with no sorting tabs and of
  managing weight per character
  ([Steam thread](https://steamcommunity.com/app/1096530/discussions/0/3389534247566508297/)).
  Community evidence only.
- **Pathfinder: Wrath of the Righteous**: mods add inventory search, per-slot filters and
  subtype sorting ([mod 137](https://www.nexusmods.com/pathfinderwrathoftherighteous/mods/137),
  [mod 1114](https://www.nexusmods.com/pathfinderwrathoftherighteous/mods/1114)), which
  suggests the base game lacked them at some version. Not confirmed which. The map opens
  on M ([controls](https://pathfinderwrathoftherighteous.wiki.fextralife.com/Controls));
  whether it is full-screen was not confirmed.
- **Pathfinder: Kingmaker**: a pre-release Owlcat update planned the log as tabs
  (combat, dialogue, events; Kickstarter update 37, seen only as a search snippet, the page
  refused the request). Its spellbook layout (known spells in a central book, slots below)
  comes from a guide ([gamerguides](https://www.gamerguides.com/pathfinder-kingmaker/walkthrough)),
  not from Owlcat.
- **Disco Elysium** puts its dialogue in one column at the lower right that "flows
  upward", where Robert Kurvitz says players look
  ([Kotaku](https://kotaku.com/disco-elysiums-dialogue-system-is-as-addictive-as-any-s-1841046831)).
  Nothing found on what they tried first.
- **Foundry core** keeps chat and the combat tracker as tabs of one sidebar and had to add
  pop-outs so both can be seen at once ([combat](https://foundryvtt.com/article/combat/),
  [chat](https://foundryvtt.com/article/chat/)). Read as: do not make the player choose
  between the conversation and the fight, which is why Talk is a tray beside the book and
  not a tab that replaces it.
- **Could not confirm**: a BG3 inventory list view (only the spellbook got one), a Pillars
  of Eternity II inventory rework, WotR's offense page layout or whether it hides the
  spellbook for non-casters, Pathbuilder's attack cards, Solasta's preparation screen.
- **The app's own code**, which outranks all of the above for materials:
  `play/templates/play/table.html` (embers, candle, cursor, clasps, bosses, the abandoned
  tilt), `play/static/js/table/06-trade-and-page.js` (flicker, shelves, item icons),
  `08-conversation.js` (the tray, Ignore and Take your leave, never opening by itself),
  `03-offers-and-map.js` and `scene3d.js` (the boards and the one lamp), `05-sheet.js` (the
  slots, the Offense tab, the spell icons).

## How it was checked

Every tab for both characters was screenshotted at 1440x900 and 1024x768 with headless
Chrome through the `#char=...&mode=...` links, and at 375x812 in the preview pane's phone
emulation (headless Chrome will not make a window narrower than 500px, so its phone shots
are not evidence). At 375px the page measured `scrollWidth` 375 in all seven modes for both
characters and with the tray open; before the last two fixes it measured 427 (the tab row
sizing itself to its seven tabs) and 395 (the clasps' box). The Equipment actions, the
tray, the boards and the spell pages were driven in the page, with no console errors and
every file answering 200.

The device was checked over the DevTools protocol with true device emulation (so the
375px shots are real 375px layouts): its four states at 1440, 1024 and 375; the tab in and
out at each; a twelve-frame scripted turn at 1440 (and six frames each at 1024 and 375)
with the model's readings written under each frame; the steam's reach against every text
node and control at its densest; and live turns driven through Say, an exit and a roll
owed, with the device's log read after (gaps above; no console errors). Two defects were
found that way and fixed: steam stopped for good after the second turn (the halt turned
the gear past the next puff's mark, and the test for crossing it never fired again), and
the tab's clearance at 1024 was 18px, not the 14px first estimated.

## Open questions for the owner

- **The tab when idle.** Idle is a calm green lamp, and the tab is in, because the brief
  read "only in the ready state". It goes in 2.6 s after the lever, as the green settles.
  If "only pop out when its green" meant whenever the lamp is green, it would stay out at
  rest instead; that is one line.
- **The clasp's arm.** At the top of the gutter the device covers the lower part of the
  book's top-left clasp's descending arm (the corner piece and the top arm show). Keep, or
  drop the device below the clasp's tip (about 35px lower at 1440)?

- **Encumbrance.** Should the engine carry weights for gear and armour and a carrying
  capacity, so the Equipment page can show a load bar the way Foundry does? Today it can
  only show the weapons' pounds.
- **Take off and Drop.** Both are offered on every row and answered with a refusal,
  because the engine has neither for armour, shields or dropping. Keep the buttons as a
  promise, or hide them until the engine can?
- **Two weapons.** The engine holds one weapon. Is an off hand wanted (two-weapon
  fighting, a dagger with the rapier), or is one weapon and a shield slot the model?
- **Manoeuvres and provocation.** The sheet says every manoeuvre provokes because the
  engine's table does; no attack of opportunity is actually rolled. Worth wiring, with
  the Improved feats switching it off?
- **The desk in Map mode.** On a phone the choices are dropped so the board has room; on
  a desktop they stay and scroll. Is that the right split?

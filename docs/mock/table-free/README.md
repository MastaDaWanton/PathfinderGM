# Book and ledger: a free mock of the play table

The owner asked for a second mock with no limitations: "make it the best you can usable and
stylish whatever you want", for Pathfinder GM. This is it, in its second edition. It sits
beside `docs/mock/table-layout/` (the first mock, which preserved the app's leather and gilt)
and shares nothing with it but data.

It is **not part of the app**. There is no Django view and no URL, nothing under `play/`
changed, and `docs/` is not bundled (`pathfindergm.spec`). Nothing on the page reaches the
engine or a model. Every reply to a click is one of three things: real engine output copied
into `data.js`, a number computed from the real sheet, or a line that begins "Mock." and is
set in the interface's voice, never the narrator's.

## Opening it

From the repository root:

```
python -m http.server 8767 --bind 127.0.0.1
```

Then open <http://127.0.0.1:8767/docs/mock/table-free/>. It must be served from the root,
because it loads by relative path:

- the app's own `play/static/js/dice3d.js` and `play/static/js/scene3d.js`;
- the game-icons SVGs;
- the textures in `textures/`.

A file:// page cannot fetch the icons.

**Options** (top right) holds three groups:

- The page settings: the light (System, Day, Night) and the story text size (Smaller, Book,
  Larger).
- The character switch (Kesst the rogue, Ysolde the wizard). It is also in the strap at 1440
  and at the head of the Character and Spells views.
- The mock's scenes: go to the recorded fight, talk to the guard, stand at the market counter,
  be wanted in Zhilvarnia, start again.

## The second edition: what changed, and why the first read as generic

The owner reviewed the first edition (c4f2308): "its too flat and ultimately lack
originality pull in texture from the internet and make your design more unique".

He was right, and the frontend-design skill names exactly why:

- **It sat in a stock cluster.** Slate panels (#161a20 to #29303c) with a single verdigris
  accent is the skill's "near-black with a single bright accent" cluster, one of the defaults
  it lists as a tell.
- **Its structure was a template.** Every surface was the same flat rectangle with the same
  3px radius and the same grey hairline, which is the "SaaS-card kit" in a darker colour.
- **Its identity was in the words, not the look.** "Book" and "ledger" were only names: the
  book was a dark rectangle, and the ledger was a column of grey lines.
- **Nothing had a material, a thickness or a light.** The page did not look like it could
  exist anywhere.

The second edition keeps everything that worked:

- the structure: book and ledger, the rules in the margin beside the paragraph they caused,
  and the one dock that changes shape;
- every number opening to its parts;
- gear with its names always shown;
- the trade basket;
- every flow.

What changed is what things are made of.

## The design read

This is a long-session play surface for one person who reads for hours and fights now and
then. It is framed as a writing desk under one lamp: a book is written as you play, and the
rules keep their account on a ledger leaf bound in beside it. It is built from real materials
(CC0 and public-domain scans), in native CSS, with the app's own 3D board and dice.

The dials:

- **Variance 5**: this is an application, not a landing page.
- **Motion 3**: the owner's rule is motion only in answer to an action, or ambient behind
  content.
- **Density 6**: the page is airy and the ledger is dense.

**The idea, in two sentences.** The table is an open book on a lamplit desk, printed as a
facing-page edition. The GM's prose is on the right-hand page, and a leaf of blue-grey account
paper is tipped in on the left, where the rules keep their ledger in a clerk's hand beside the
paragraph each entry caused. Everything else is an object on the same desk, all lit from the
one direction the app's 3D board already uses:

- a leather strap for the bar;
- a loose sheet for the way ahead;
- wooden counters for the board;
- a baize tray for the dice.

The seam between the two voices is real in the architecture. The narrator is fed tells and
nothing else about mechanics, and no model authors a number (`CLAUDE.md`, the three laws). The
facing page shows that seam instead of hiding it. The Loeb Classical Library prints the
original on the left and the reading text on the right; here the left page is the engine's
account of what happened, and the right page is the story told from it.

### The plan, and the critique of it before any code

The first plan was cream paper, a high-contrast serif and a red accent. Checked against the
skill's list, that is cluster 1 almost exactly: warm cream, a serif display and a terracotta
accent. So the plan was revised before building:

- **Cream is not the ground.** The dominant surfaces are the dark walnut desk and the
  blue-grey ledger stock. The book's paper appears as a textured object with a torn edge,
  thickness and a shadow, never as a flat page background.
- **The accent is lapis, not red.** Ultramarine (#263f8e) was the dearest pigment in a
  scriptorium, and blue is one of a ledger's two ruling inks. It means "yours, open, go" and
  nothing else.
- **Red is confined to what a page flags.** It is the ruling ink's other colour, used for the
  rubricated initial and for debits: foes, spent, shut and damage.
- **The display face has no hairline contrast.** IM Fell English (the Fell types, 1670s) is a
  rough letterpress face whose ink spreads into the paper. It is used only for titles, names and
  the one initial, and it was checked against the skill's banned serifs.
- **The structure is one no template has.** A two-stock facing-page spread, with the rules
  kept on their own stock of paper.

### Research, and what it changed

Before designing, a second research pass covered book-object and narrative-game interfaces.
Primary sources were used where reachable; anything else is marked.

- **Obsidian, Pentiment.**
  - Each kind of writer gets its own script, designed by Lettermatic
    (<https://lettermatic.com/custom/pentiment>, and director interview
    <https://www.gamedeveloper.com/design/pentiment-director-explains-how-going-all-in-on-fonts-helped-elevate-the-medieval-detective-rpg->).
  - Patch 1.1 added instant text display, because watching the letters write themselves wore
    thin. The patch notes were reached only through reports: <https://www.gamespot.com/articles/pentiment-update-1-1-adds-new-minigame/1100-6509974/>.
  - **Taken:** three hands, one per voice (below).
  - **Refused:** any write-out animation. Text appears at once.
- **Glossed manuscripts.** The main text sits in the largest hand, and the gloss is written
  smaller around it (<https://sites.nd.edu/manuscript-studies/2015/09/17/reading-between-and-around-the-lines-an-introduction-to-glosses-and-commentaries/>).
  Initials are graded by importance, and rubrics are set in red (the Walters, W.269:
  <https://www.thedigitalwalters.org/Data/WaltersManuscripts/html/W269/description.html>;
  the Getty: <https://www.getty.edu/education/for_teachers/curricula/manuscripts/manuscripts_lesson01.html>).
  **Taken:**
  - the ledger as a gloss, in a smaller hand, keyed to its paragraph;
  - a three-line red initial only where a new place opens;
  - a lapis paragraph mark opening each of your turns. It first hung in the margin, but at 1440 that put it in the binding's shadow, so it moved inside the page.

  The Getty notes that medieval marginalia often have no relation to the text. The margin here
  is refused that freedom: every entry belongs to the paragraph beside it.
- **Ledgers and account books.**
  - Machine ruling was "always blue and red" (<https://bookbindersmuseum.org/collections/equipment/the-pen-ruling-machine/>).
  - The pages were debtor and creditor (<https://plainsightproject.org/early-double-entry-accounting>).
  - Marbled edges and endpapers were tamper-evident: a torn-out leaf breaks the pattern
    (<https://ucdculturalheritagecollections.com/2021/02/18/marbled-papers-a-brief-history-of-an-endangered-bookcraft/>).

  **Taken:**
  - blue lines every 22px and a red money rule before the figures;
  - "Carried forward" at the foot of the ledger leaf (hour, life, purse);
  - double-ruled totals in the basket;
  - the text block's marbled edge, which here means the record is append-only: nothing can be
    torn out.

  I found no archive source for "carried forward" itself. It is standard bookkeeping
  (<https://en.wikipedia.org/wiki/Ledger>).
- **Lucas Pope, Return of the Obra Dinn.** A late change forced visible covers and a dark
  border round the book, and it improved it (<https://dukope.com/devlogs/obra-dinn/tig-37/>).
  **Taken:** the book's leather boards show round the spread, on a dark desk.
- **Lucas Pope, Papers, Please on phones.** The desk was removed for readability: "I swung all
  the way to readability" (<https://dukope.com/devlogs/papers-please/mobile/>). **Taken:** at
  375px the desk and the cover shrink to a few pixels, and the page is nearly full bleed.
- **inkle, 80 Days and Sorcery!**
  - inkle rejected steampunk brass as "cheap and kitsch" (from a search excerpt of Road to the
    IGF: <https://www.gamedeveloper.com/design/road-to-the-igf-inkle-s-i-80-days-i->).
  - It judged Sorcery!'s material textures as not having "aged especially well"
    (<https://www.gamedeveloper.com/business/postmortem-i-steve-jackson-s-sorcery-i-series-by-inkle>).
  - Jon Ingold's rule: every screen shows "which bits are buttons… which are displays"
    (<https://www.vice.com/en/article/the-makers-of-mobile-hit-80-days-on-the-importance-of-amazing-ui-852/>).

  This was the most important warning, so the materials are held to a rule. Every material
  stands for something in the game:
  - paper is the record;
  - the blue stock is the rules' account;
  - leather is the book's binding;
  - marble is the append-only edge;
  - baize is where dice are thrown.

  None is ornament. There is no brass, no gilt, no rivets and no wax seals. Ingold's rule
  became this page's affordance rule (below).
- **Failbetter, Sunless Skies' reading redesign.**
  - The reading panel is centred and results stay on the page, scrolling up.
  - Vollkorn was chosen for period tone and readability.
  - Bright colour is reserved for interaction.
  - Source: <https://www.gamedeveloper.com/design/reading-by-gaslight-a-look-inside-sunless-skies-ui-redesign>.

  **Taken:** lapis only on what you can press or what is yours.
- **Text on textured grounds.**
  - NASA Ames (Scharff, Hill and Ahumada 2000) found that texture slowed reading mainly when
    text contrast was low (<https://ntrs.nasa.gov/search.jsp?R=20040088111>).
  - WebAIM says to test the lowest-contrast spot (<https://webaim.org/articles/contrast/>).

  **Taken:** every paper and stock texture was lightened to a narrow band, and contrast was
  measured at the darkest 2% of each texture, not only its average (see Contrast).

The first edition's research on CRPG and VTT play screens still stands, and is kept below it.

## The token system

### Three hands

- **The printer** is IM Fell English. It sets place names, people's names, section titles,
  the red initial and the paragraph mark. Its old-style numerals made "+1" read as "+I", so it
  never sets a number.
- **The book** is Literata, TypeTogether's face for long reading on screens. It sets the GM's
  prose, your own words (italic), suggestions (italic) and item names. The story is 20px at
  line-height 1.62 (18px on a phone).
- **The clerk** is Sofia Sans Semi Condensed, with tabular figures, in blue-black ink. It sets
  the ledger, every figure the engine decides (abilities, AC, life, prices, the clock) and
  every control label.

The measure is `var(--story-size) * 31.5`. It measured **66 characters a line** at 1440x900
and **59.5** at 1024x768, on the recording's gate paragraph.

### Palette

| Token | Day | Night (lamplight) | Job |
|---|---|---|---|
| `--paper` | `#f0e8d7` × paper grain | `#e9dcc2` × paper grain | the book, the loose sheet, the views |
| `--stock` | `#d9e0dc` × ledger fibre | `#d2d6cd` × ledger fibre | the rules' account paper |
| `--ink` | `#2a2019` | same | the book's iron-gall ink |
| `--ink-2` | `#463a2d` | same | secondary text on paper |
| `--lg-ink` / `--lg-ink-2` | `#1a2944` / `#313e57` | same | the clerk's blue-black |
| `--lapis` | `#263f8e` | same | the one accent: yours, open, go |
| `--rubric` | `#8e2317` | same | debit and rubrication |
| desk / leather | walnut and brown leather textures under a dark overlay | darker overlay | the room and the binding |

**Night is the same desk by lamplight, not an inverted interface.** The desk darkens, the
paper warms and dims a little, and the ink keeps its contrast. The research for the first
edition gave the reason: NN/g found light text grounds better for reading, and players often
play at night.

**The lamp's colour follows the hour.** It uses the engine's own `residency.day_part` words:
rose at dawn, faint by day, amber at dusk, a cold blue at night. It lights the desk from the
upper left and shifts over 2.4s, behind everything.

### One light

`scene3d.js` lights the 3D board with `LIGHT = (-0.42, -0.78, 0.47)`: from the upper left, and
above. Everything on this page is lit from the same place:

- **Shadows** fall to the lower right in that light's ratio (x : y = 0.42 : 0.78, about
  1 : 1.9). There are four elevations: `1px 2px 2px`, `2px 4px 5px`, `5px 9px 14px` and
  `11px 20px 34px`.
- **Raised controls** catch the light on their top-left edge and shade on the bottom right.
- **Board counters, sockets and initiative counters** are radial-lit from the upper left.
- **The binding** shades into the gutter.

### What things are made of

- **The desk.** Walnut (Poly Haven), under a darkening overlay and a vignette.
- **The book.** Leather boards (Poly Haven), larger than the text block. The text block's
  marbled edge (a 1720 Leiden endpaper) shows past the pages at the lower right. Two leaves lie
  on top:
  - **The ledger leaf** is blue-grey stock, the fibre of a backlit sheet of laid paper.
  - **The recto** is book paper, from a public-domain paper scan.

  Both have torn edges and a shadow, and the binding is shaded between them.
- **Torn edges.** An SVG `feTurbulence` plus `feDisplacementMap` filter is applied only to
  empty backing layers, so no letter is ever displaced.
- **The ledger's ruling.** It is painted on each entry, so it scrolls with the entries it rules.
- **Ink sits in the paper.** Every texture is a grey detail map, multiplied under its paper
  colour. Prose has a hair of ink spread (`text-shadow: 0 0 .6px`), and pictures of items are
  printed in the book's ink, not stamped on top.
- **The strap.** Leather with saddle stitching along its lower edge.
  - The chosen view is a paper thumb-index label pasted on the strap; the others are tooled
    into the leather (debossed text).
  - Life is a groove filled with lapis, which turns rubric when it runs low.
- **The loose sheet (the rail).** Book paper with a torn edge, lying on the desk to the right.
- **The board.** Printed on card:
  - inked hatching for walls;
  - a wash for the gallery;
  - lapis for the squares you can reach and rubric for the foes' reach;
  - turned wooden counters with shadows (lapis for you, rubric for foes).
- **Dice.** The app's `Dice3D` mat, re-dressed from outside by CSS:
  - a tray lined with lapis baize, with a wooden rim;
  - bone dice, with the landed face inked in lapis;
  - the terms on a ledger slip, and the verdict on a paper label.
- **Spells.** Slots are hollows pressed into the page, each holding a lit lapis bead when
  open. A spent slot is an empty hollow ringed in rubric. Prepared spells are cards lying on
  the sheet.
- **Footnotes.** A number's reasons open on a slip cut from the ledger's stock, with its money
  rule.
- **Trade.** The shop's counter book. The basket is kept on ledger stock with the money rule,
  and its total is double-ruled.

### The affordance rule (from Ingold)

- **Raised** is a paper tag with a lit top-left edge and a shadow: you can press it.
- **Pressed in** is debossed, and inked in lapis: it is the one chosen (a pressed tab, the Say
  toggle, the chosen target). The pen's line is pressed into the page too.
- **Printed** is ink on paper with no edge: it is information.
- **A figure with a dotted underline** is a footnote: press it for what it is made of.

## Contrast, measured on the textures

This is measured in the browser, by reading every seventh pixel of each texture multiplied by
its paper colour. It reports the median and the darkest 2% of the paper, not only the average,
because WebAIM says to test the lowest-contrast spot. The first measurement failed:

- `--ink-3` was at 3.35:1 at the darkest 2%.
- `--rubric` on the ledger stock was at 2.92:1 at night.

So the paper grain was lightened (to a band of 212 to 255) and the stock grain likewise (214
to 255), and `--ink-2`, `--ink-3`, `--lg-ink-2`, `--lapis` and `--rubric` were darkened.
After those changes:

| Text on | Ink | Day, median | Day, darkest 2% | Night, median | Night, darkest 2% |
|---|---|---|---|---|---|
| page paper | `--ink` (prose) | 10.99 | 9.05 | 9.89 | 8.17 |
| page paper | `--ink-2` | 7.62 | 6.27 | 6.85 | 5.66 |
| page paper | `--ink-3` | 5.78 | 4.76 | 5.21 | 4.30 |
| page paper | `--lapis` | 6.64 | 5.47 | 5.97 | 4.93 |
| page paper | `--rubric` | 6.03 | 4.97 | 5.43 | 4.48 |
| tag paper (buttons) | `--ink` | 11.78 | 9.69 | 10.63 | 8.76 |
| pressed paper (pen, chosen) | `--lapis` | 5.69 | 4.70 | 5.11 | 4.23 |
| ledger stock | `--lg-ink` | 9.05 | 7.60 | 8.25 | 6.95 |
| ledger stock | `--lg-ink-2` | 6.68 | 5.61 | 6.09 | 5.13 |
| ledger stock | `--rubric` | 5.44 | 4.57 | 4.96 | 4.18 |
| leather strap | `--on-leather` (#f1e5ca) | 12.27 | 11.14 at the lightest 2% | same | same |
| leather strap | `--on-leather-2` (#d6c3a0) | 8.89 | 8.07 at the lightest 2% | same | same |
| lapis button | `--on-lapis` | 8.54 | | | |

Every median passes 4.5:1. Four darkest-2% values fall between 4.18 and 4.48, all at night:

- `--ink-3` on page paper, 4.30;
- `--rubric` on page paper, 4.48;
- `--lapis` on pressed paper, 4.23;
- `--rubric` on ledger stock, 4.18.

Those spots are the texture's foxing specks. The worst case is small rubric text on the
ledger stock at night, used for "miss" and "hit, damage" in bold 14px.

Not included: the darkened edges of each sheet (a 40px inner shadow), where text does not
run.

## What the table does, and where

| Asked for | Where it is |
|---|---|
| The story, long-form | The book's right-hand page. Recorded prose verbatim; place headings in IM Fell, and a red initial where a place opens |
| The pen, Say, Continue, Craft action, suggestions | The dock. Enter acts; Say toggles speech (your line is set in quotes); Continue adds a beat and moves the clock (ruling 2026-09-18: the PC keeps their action, the world advances); Craft action opens hours (1 to 48) and the ways of gathering on this ground; suggestions fill the pen |
| Exits, journeys, shut ways | The rail's **From here**: Next door, Outside, Roads, with time in words (a shared time said once per group). Wanted in Zhilvarnia greys the watched ways; pressing one opens the engine's reason under it. The road to Xylorvotha asks before five days pass |
| Leaving mid-fight is a withdraw | The fight rail's **Ways out**: every way is a withdraw (your whole turn), and the line above says whose reach covers the way to the door before you commit. A committed withdraw rolls those foes' strikes and leaves the fight |
| Initiative, whose turn, round | The order of battle: a strip of ledger stock across the top, with wooden counters |
| Action economy, Strike, Full attack, Ability, Cast, Swift, Free, Commit, End turn | The combat dock. Actions are planned as chips and nothing happens until Commit. Full attack is refused once you have moved. Strike out of reach is refused with the squares named ("Borin Lyraxys is at E4, 15 ft from B4. Your rapier reaches 5 ft") |
| Targets with attitude | The fight rail's **Targets**, with distance from where you will stand after your planned move |
| 2D grid and 3D view | The board, Flat or 3D. Flat shows walls, the gallery and its rail, rough ground, reachable squares, foes' reach, the door, and your planned path. A move whose path leaves a threatened square says who gets the attack of opportunity; a single clean square is a 5-foot step and says it does not provoke. 3D is the app's own `Scene3D.render`, fed the same grid, turned in quarter turns; its reachable squares are clickable too |
| Dice | The app's own `Dice3D.land` for your rolls (attack, manoeuvre, haggle), set in a baize-lined dice tray: bone dice, the landed face inked in lapis. Foes' rolls are the engine's and go straight to the margin |
| The character | **Character**: portrait slot, abilities, saves, needs, features and feats, life, AC/touch/flat-footed, CMD, initiative, every weapon's to-hit (iteratives written +a/+b when there are any), damage, crit, type and range; every manoeuvre with its bonus and whether it provokes; every skill, class skills marked, trained-only ones "untrained" |
| Conditions, XP, body's needs | Bar (life, AC, touch, flat, conditions when any), rail (needs), Character (XP bar, needs with the engine's own detail) |
| Equipment | **Gear**: what is on you by slot, the purse in the world's coin, and what you carry with names always shown, kind tabs with counts, a find box, order by kind / name / value; Wield, Wear, Take off, Use, Drop on every row. 43 things for the rogue |
| Spells | **Spells** (casters only): sockets per level (a lit lapis bead is open, an empty hollow ringed in red is spent), prepared cards with the numbers on the card (range, target, save and DC), Details, Cast. Cast puts the spell on your turn as a chip under the pen; it is not sent. Rest and prepare (9 hours) brings slots back and pops the clock |
| Trade | Trade, only where somebody keeps a counter (the market, the merchants row), else it names the nearest counter. One basket holds buying and selling with steppers, the net price, a haggle roll, and "you are N short" before you can pay |
| Conversation | **Talk** on a person: the rail's top becomes the conversation (speech only), with regard, Ignore and Take your leave. Hide folds it to one line without ending it; it is sticky until you leave it (ruling 2026-09-24) |
| Journal, clock, map | **Journal**: matters in play, the road so far, what people said word for word. **Clock** in the bar; an hour or more pops a dial that sweeps the hours and counts the days, then closes itself (the margin keeps the record). **Map**: the 43 places of Zhilvarnia as the exits join them; press one for the route and Walk there |

## Research for the first edition: play screens

The standing instruction is to search before designing. A research pass collected primary
sources where they could be reached; claims it could not source are marked here as such.

- **Owlcat, Pathfinder: Kingmaker, "Update #37: the combat log, it's how we roll"**
  (<https://forum.owlcatgames.com/t/update-37-the-combat-log-its-how-we-roll/12771>): every
  combat line opens to every bonus and penalty with its source. Taken whole: the margin
  entries and the press-any-number breakdowns. (The Kickstarter copy returned 403; the content
  was confirmed from the forum post and search excerpts.)
- **Larian, Baldur's Gate 3, Nick Pechenin on the dice UI**
  (<https://www.gamedeveloper.com/design/tides-of-chaos-how-i-baldur-s-gate-3-i-tackles-the-rng-of-d-d-inspired-dice-rolls>):
  a minimalist single number confused players, who took the sum of bonuses for the DC; Larian
  moved to showing how the number is made. Taken: the total is always beside its parts and
  what it was against.
- **BG3 forums on the combat log**
  (<https://forums.larian.com/ubbthreads.php?ubb=showflat&Number=821911>): auto-scroll made it
  "near impossible to consult older entries". Taken: new beats land at their top, and never
  move a reader who has scrolled back.
- **BG3 Early Access Patch 7** (<https://forums.larian.com/ubbthreads.php?ubb=showflat&Number=807744>):
  the hotbar that auto-filled with every spell was replaced by decks, and turn order moved to
  the top centre. Taken: initiative across the top; the Cast menu lists only what is prepared,
  grouped by level.
- **Foundry VTT chat and combat**
  (<https://foundryvtt.com/article/chat/>, issue <https://github.com/foundryvtt/foundryvtt/issues/11456>,
  v13 notes <https://foundryvtt.com/releases/13.332>): rolls collapsed by default are
  "often problematic/tedious" to users; v13's fading UI and timed notifications drew
  complaints. Taken: breakdowns open and stay open; the toast carries nothing the ledger does
  not also keep; nothing fades while you read.
- **Owlcat, Wrath of the Righteous turn-based mode** (<https://wrath.owlcat.games/news/16>):
  the planned path shows the attacks of opportunity along it before you commit. Taken: the
  planned move names who strikes, and the ways out say it before a withdraw.
- **Failbetter, Sunless Sea post-mortem**
  (<https://www.gamedeveloper.com/audio/postmortem-failbetter-games-i-sunless-sea-i->): the
  separate combat screen "yanked the player out of our carefully layered atmosphere" and was
  scrapped. Taken as the structural decision: the fight happens on the same page as the story.
- **Failbetter, Fallen London redesign**
  (<https://community.failbettergames.com/t/dev-blog-insights-into-the-fallen-london-redesign/18507>):
  a card-flip animation made testers nauseous and was cut; a scroll bar that hid equipment
  from comparison was cut; information that affects a decision went back onto the card. Taken:
  no reveal animations on menus; spell cards carry range, target and save DC on their face;
  gear is a list you can see whole.
- **Disco Elysium, ZA/UM devblog on active checks**
  (<https://discoelysium.com/devblog/2016/10/06/active-skill-checks>): a check is shown as the
  attempt, with its odds, before commitment. Taken in spirit: the plan is a set of chips you
  can remove before Commit. I could not source any designer statement on the column's width.
- **Latitude, AI Dungeon** (<https://help.aidungeon.com/faq/how-to-play>, Heroes dev log #7
  <https://latitude.io/news/heroes-dev-logs/7>, the latter from search excerpts only): Do /
  Say / Story modes, Continue, and clickable suggested actions added because players did not
  feel creative enough, kept beside free text. Taken: Say as a mode of the one pen, Continue,
  suggestions that fill the pen.
- **inkle, Jon Ingold on text density**
  (<https://narrativenews.substack.com/p/inkles-jon-ingold-on-the-craft-of>): readers judge a
  wall of text before reading a word. Taken: a heading per place, generous leading, the
  measure held at 66.

- **Readability**: Bringhurst's 45 to 75 characters, 66 ideal (<http://webtypography.net/2.1.2>);
  Dyson and Haselgrove 2001 on screen line length
  (<https://www.researchgate.net/publication/220106760>); Rello, Pielot and Marcos, CHI 2016, on
  size (<https://pielot.org/2016/01/optimal-font-size-for-web-pages/>); NN/g on dark mode
  (<https://www.nngroup.com/articles/dark-mode/>).
- **Could not source**: how Solasta shows spell slots and its action bar (the dev diary
  returned 403); any inkle statement on 80 Days' clock. The dial here is not modelled on 80
  Days for that reason.

## Decisions, and what was rejected

- **Rejected: a combat log panel.** The app's table keeps rolls in a separate Rolls panel
  (`#panel-rolls`). Owlcat, Larian and Foundry all put the log in a panel, and all three then
  spent patches making it readable. The ledger leaf puts each roll beside its sentence, which a
  log cannot do.
- **Rejected: a separate combat screen** (Sunless Sea). The fight happens in the same book.
- **Rejected: an icon grid for gear.** The owner said icon-only is painful with lots of gear.
  Names, counts and a find box instead.
- **Rejected: decorative material.** Brass, gilt, rivets, wax seals, a candle and a quill are
  all refused. inkle called steampunk brass kitsch, and said Sorcery!'s textures aged badly.
  Every material here stands for part of the game.
- **Rejected: a write-out animation for the prose.** Pentiment added instant display after
  launch. Text appears at once.
- **Rejected: a desk on the phone.** Lucas Pope removed his desk on mobile. At 375px the page
  is nearly full bleed, with a few pixels of cover.
- **Rejected: IM Fell for figures.** Its old-style "1" reads as "I". Every number is set in the
  clerk's face.
- **Rejected: rotated sheets.** A tilted sheet looks more like a desk and reads worse. Every
  sheet lies square.
- **Rejected: boxes in the margin** (first edition). Entries are written on the ledger's rules.
  Where the leaf folds away (below 1240px), each entry becomes a slip of the same stock pasted
  above its paragraph.
- **Rejected: a candle flicker.** It would have been the one ambient motion. It was refused
  because a flickering light behind text is exactly the motion that makes a page harder to read.
- **Rejected: odds before a strike.** The player in 1e does not know a foe's AC. The to-hit is
  shown; the AC arrives with the roll.
- **Kept from the first mock:**
  - exits from the place graph, and one choice in one place;
  - shut ways that say why (now struck through in rubric), and the journey confirm;
  - gear from counters only.
- **Motion, all of it:**
  - a new beat fades in over 0.22s (it answers your action);
  - the counter and the phone sheet rise 0.2s when opened;
  - the dice tumble (the app's own);
  - the clock dial sweeps 1.4s when an hour or more passes;
  - the lamp shifts colour over 2.4s behind everything;
  - controls lift on hover and press in on click, over 0.12s.

  Menus and popovers open instantly and never move what was under the pointer. Reduced motion
  turns off the fades and rises.

## What is real and what is example

Real, generated by `build_data.py` (run from the repository root; nothing in `data.js` is
hand-written):

- **Exits**: `play/exits.py exits()` at all 43 places of Zhilvarnia at 08:00, plain and wanted.
- **The gate**: the story, suggestions and the two people with their faces, from
  `tests/replay/2026-09-25-town-tags-retag-gemma4-12b.jsonl.gz` (as the first mock).
- **The fight**: `tests/replay/2026-09-25-fight-bodies-gemma4-12b.jsonl.gz`, the save before
  turn 4: the 10x9 grid with its walls, rough square, raised gallery and rail; everyone's
  square; initiative (Borin Lyraxys 16, Kesst 9); round 1; the opening attack with its terms
  and DC explanation, the sneak attack, the damage, the tell, the XP; and the prose, verbatim.
  Borin's AC 13 and unarmed strike (+3, 1d3-1) are `full_sheet()` read back through
  `rules.sheet.from_dict`.
- **Both sheets**: `rules.sheet.full_sheet()` and `summary()` for `fixtures/pc-kesst.json` and
  `fixtures/pc-caster.json`, every term. Each manoeuvre's "provokes" is
  `rules.tables.MANEUVERS[...]["provokes"]` unless the sheet has its Improved feat. Weapon range
  is `rules.tables.WEAPONS[...]["range_ft"]`.
- **Counters and coin**: `rules.goods.goods_at("market")` (40 kinds), `goods_at("smithy")`,
  `goods_at("tavern")`, a slice of `table_goods("weapons")`; the coins are
  `rules.goods.coinage()` for Zhilvarnia ("Khy'vyr gold piece", coined by the app). Selling at
  half is `rules.pricing.SHOP_BUYS_AT`; the wanted markup of half again is
  `rules.pricing`'s own rule.
- **Spells**: `content/spells/spells.json` for the wizard's 26 book spells; slots are the
  sheet's pools (3 cantrips, 2 first-level). DC 13 plus level.
- **The clock's words**: `rules.residency.day_part()` for every hour.

Example, and said so on the page where it shows:

- The rogue's load past the fixture's rapier, dagger, leather armour and outfit (marked
  "(example)" on each row, at the Core tables' real prices); the wizard's spellbook row and
  kit; both purses.
- Attitudes ("indifferent", "hostile") and the 0 to 100 regard value: the recordings have none.
- Every d20 after the recorded opening; the foe's turn logic (close in, strike); the reach walk
  (Dijkstra, diagonals at one and a half squares, rough ground doubled, the gallery out of
  reach); the door at E9 (the square Kesst entered by in turn 0).
- The Craft action list; the haggle's Diplomacy roll against 15 and its ten per cent (the
  engine's real haggle caps the ask at a price agreed in talk).
- The two matter names are the recording's own; "the road so far" is built from this page's
  own moves.

Shown verbatim though flawed, because they are the recording's: "man with a thick" is a
naming defect of that session, and "I punch him in the face" rolled a rapier because the
recording predates the nonlethal-strikes fix.

## What the real app would need to adopt it

- **Fonts, bundled.** Literata and Sofia Sans Semi Condensed are both SIL OFL on Google Fonts.
  The mock links Google Fonts; the executable is offline, so the woff2 files (Literata
  variable roman and italic, Sofia Sans Semi Condensed variable) go into `play/static/fonts/`
  beside Cinzel with their OFL text, and an `@font-face` replaces the link. No other
  third-party asset is used.
- **A tell-to-beat link.** The margin needs each outcome attached to the beat it produced.
  The turn log already records outcomes per turn (`added_turn_log` in the recordings); the
  page needs the beat id alongside, and the rolls' `modifiers` and `dc.explain`, which the
  engine already produces.
- **Render the engine's answer before the prose.** Today the page waits for the turn. The
  margin entries could be sent as soon as the engine resolves, with the prose streaming after:
  the single change that most helps a slow local model.
- **Per-number terms on the sheet.** `full_sheet()` already returns terms for everything
  shown; the sheet view would render them as the breakdown cards.
- **Weapon ranges.** `rules.tables.WEAPONS["dagger"]` has no thrown range, so the Range column
  says "melee, 5 ft" for a dagger. A data gap to fill in the tables, not a UI one.
- **Distance for targets and the board's reach.** The engine already has the grid and reach
  (`rules/grid.py`, `Scene.positions`, the melee-reach refusals); the mock's own Dijkstra
  would be replaced by the server's `reachable` payload, which `scene3d.js` already reads.
- **Withdraw risk per exit.** The mock measures the path to one door. The engine would name,
  per way out, which foes' reach covers it.
- **A theme and size setting**, stored per viewer (the mock uses localStorage).

## What the real app would need to adopt it

- **Fonts, bundled.** IM Fell English, Literata and Sofia Sans Semi Condensed are all SIL OFL
  on Google Fonts. The mock links Google Fonts, but the executable is offline. The woff2 files
  (IM Fell English roman and italic, Literata variable roman and italic, Sofia Sans Semi
  Condensed variable) would go into `play/static/fonts/` beside Cinzel with their OFL text, and
  an `@font-face` would replace the link.
- **Textures, bundled.** The six files in `textures/` (551 KB) would go into
  `play/static/img/` with `textures/CREDITS.md`. They are CC0 or public domain, and the app
  already ships its own leather and paper jpgs there. No other third-party asset is used.
- **The SVG edge filter.** It is inline markup in the page (`#deckle`). Nothing to bundle.
- **A tell-to-beat link.** The ledger needs each outcome attached to the beat it produced.
  The turn log already records outcomes per turn (`added_turn_log` in the recordings); the
  page also needs the beat id, the rolls' `modifiers` and `dc.explain`. The engine already
  produces the last two.
- **Render the engine's answer before the prose.** Today the page waits for the whole turn.
  The ledger entries could be sent as soon as the engine resolves, with the prose streaming
  after. It is the single change that most helps a slow local model.
- **Per-number terms on the sheet.** `full_sheet()` already returns terms for everything
  shown. The sheet view would render them as the footnote slips.
- **Weapon ranges.** `rules.tables.WEAPONS["dagger"]` has no thrown range, so the Range column
  says "melee, 5 ft" for a dagger. This is a data gap in the tables, not a UI one.
- **Distance for targets and the board's reach.** The engine already has the grid and reach
  (`rules/grid.py`, `Scene.positions`, the melee-reach refusals). The mock's own reach walk
  would be replaced by the server's `reachable` payload, which `scene3d.js` already reads.
- **Withdraw risk per exit.** The mock measures the path to one door. The engine would name,
  for each way out, which foes' reach covers it.
- **A theme and size setting**, stored per viewer (the mock uses localStorage).

## Unfinished, honestly

- **The 3D view keeps the app's own brown materials.** Its light matches this page by
  construction, but its stone does not match the page's paper.
- **The dice keep dice3d.js's own gilt bevels.** Only the faces were re-coloured to bone, from
  outside.
- **The map is a spring layout of the exits.** Some labels touch ("west crossing" and "well"),
  and positions mean nothing geographic. "Walk there" moves you in one step, where the engine
  would walk each leg.
- **The body's needs do not change as time passes here,** not even across a five-day road.
- **The fight rules are simplified.** A five-foot step, a withdraw and attacks of opportunity
  follow the book in outline only. The withdraw measures the path to the door for every way
  out.
- **Iteratives have not been seen with real data.** They render as "+a/+b" when the sheet's
  `sequence` is above one, but both fixtures are level 1.
- **Contrast has four spots under 4.5:1 at night.** They are at the darkest 2% of the textures;
  the figures are in the table above.
- **The texture of the ledger leaf does not scroll with the story.** The leaf is a fixed sheet
  behind the text, while its ruling is painted on the entries and does scroll. At rest the two
  agree. While scrolling, the rules move over a still sheet, which a real book would not do.
- **Checked** in the browser at 1440x900, 1024x768 and 375x812, day and night, with no console
  errors, across every mode and flow above. Not checked in the packaged Electron app, since
  nothing here is part of it.

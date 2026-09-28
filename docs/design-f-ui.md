# Design F: the table's furniture

This is the Phase 0 research and design for Lane F of `docs/fix-plan-2026-09-28.md`. It covers
playtest items 7, 11 (the button), 18, and the frontend half of 21.1. Nothing in it has been
built.

## 1. Items covered

| Item | Ask | Lands in |
|---|---|---|
| 7.1 | A per-person log of what was said, both ways. Vocalisations are in italics, there is no scenery, and it reopens with its history | `Scene.conversation_log` (S4), `play/aftermath/conversation_log.py`, `08-conversation.js` |
| 7.2 | Vocalisations are captured even when they are untagged | `gm/speech.vocalisations()` |
| 7.3 | Closeable panels (Scene, Conversation, Map, Rolls, Sheet) that collapse to edge tabs. Conversation comes forward when someone starts talking. One system for both widths | S6: `table.html` + `07-panels.js` |
| 11 | A Spells button beside Say / Continue / Craft action / Trade | `#spellbtn`, `10-spells.js` |
| 18 | A clock pop-up for time changes of 1 hour or more | `#clockpop`, `09-clock.js` |
| 21.1 (front) | Cast attaches a chip to the input; the player writes the rest | `#attachments`, `10-spells.js`, `/api/say` `attachments` |

### What the code does today, read on `fixes-2026-09-28`

- **The sidebar.** `<aside>` (`table.html:1626`) holds `#sheet`, `#order`, `#mapwrap`, `#board`, `#talk`, `#gmview` and `#rolls`.
  - Under 760px it is a slide-over drawer opened from `#sheettab` (`table.html:1012-1105`, `01-core.js:59-84`).
  - `#maptray` is a left-edge tray.
- **Spoken lines.** Spoken lines tagged `<say>` are lifted into `{who,to,line}` (`gm/speech.py:208`).
  - The records whose line survived every rewrite are kept on the GM beat as `said`, inside `_finish` (`views.py:2194-2201`).
  - The transcript is persisted and never trimmed.
  - Nothing indexes it per person.
- **Refs.** Refs are "minted once and never reused" (`engine.py:167-170`), so a ref is a stable per-campaign key.
  - A person deleted from `Scene.people` takes their name with them, so a log must snapshot names.
- **The clock.** `scene.clock_minutes` counts from midnight of day 1.
  - `campaign.py:525` sets it to the opening hour × 60, and `residency.time_words` reads `clock % 1440` as the hour.
  - The `fmtClock` comment ("no notion of when the campaign started", `06-trade-and-page.js:270`) is stale.
  - The hour hand can be drawn from `clock % 720`.
- **Casting.** The Spells tab's Cast button posts `/api/cast` at once (`02-state.js:350`). The combat bar's Cast… menu reads `pc.castable`.

### A finding for Lane E

`rules/sheet._castable_summary` (`sheet.py:4197`) skips unprepared spells only when `prepared` is non-empty (`if prepared and not left`).

- A prepared caster with **nothing** prepared has `prepared == {}`, which is falsy. So every book spell is returned with `left: None`.
- For Bobby (item 21), Cast… would offer all 50 book spells, and the engine refuses every one. This is inferred from the code; I did not replay it.
- E owns the fix. F must not use `pc.castable` to decide whether someone casts spells (§5).

## 2. Prior art

### Panels

- **Foundry VTT v13** made the sidebar a full-height "cabinet", "collapsed by default in order to draw the eye to the canvas" (https://foundryvtt.com/releases/13.341).
  - The chat input shows on every tab.
  - While the sidebar is collapsed, a "minimalist chat notifications tray" shows recent messages briefly.
  - The v13 `Sidebar` API has `expand`, `collapse`, `toggleExpanded`, `changeTab` and a `popouts` record (https://foundryvtt.com/api/v13/classes/foundry.applications.sidebar.Sidebar.html).
- **Roll20** puts its tools in right-sidebar tabs. Double-clicking the chat icon pops chat into a browser window (https://help.roll20.net/hc/en-us/articles/360039675093-Text-Chat — known from a search summary only).
- **The WAI-ARIA APG Tabs pattern** (https://www.w3.org/WAI/ARIA/apg/patterns/tabs/): `tablist`/`tab`/`tabpanel`, arrows and Home/End, optional Delete to close. Automatic activation is fine when panels show "without noticeable latency". It **assumes one displayed panel**.

### Dialogue logs

- **Baldur's Gate 3's** history was "introduced… late in its Early Access period due to popular demand" (https://www.dualshockers.com/baldurs-gate-3-how-view-dialogue-history/ — secondary; I found no Larian note).
  - It is searchable chronologically or by region, and it names the speakers.
  - It records choice-based cinematics only. Banter and cutscenes are excluded.
- **Disco Elysium** writes dialogue as one scrolling column with the live choices at its foot.
  - A Steam thread reports that scrolling back left a player unable to reach the choices or leave the conversation (https://steamcommunity.com/app/632470/discussions/0/2149847423920750138/).
  - Fans built external script readers (Disco Elysium Scribe, FAYDE).
  - I could not confirm whether the game later changed this.
- **Ren'Py's history** (the visual-novel "backlog") records `kind`, `who` and `what` per entry. `config.history_length` bounds it (https://www.renpy.org/doc/html/history.html). The page gives no default.
- **Pentiment 1.1** "added an instant dialogue display option" (https://egmnow.com/pentiment-update-includes-a-new-minigame-and-instant-dialogue-option/). The source gives no reason.
- **Pillars and Owlcat's games**: I could not confirm their dialogue-history behaviour. Nothing relies on them.
- **MUD socials** make vocalisations a closed, *declared* vocabulary (`laugh`, `cackle`…). Continents MUD lists 364 (https://www.continentsmud.com/socials.php — search summary).

### Attribution accuracy

- **Muzny et al. 2017**: "an average F-score of 87.5 across three novels", and 90.4 precision at 65.1 recall when tuned for precision (https://aclanthology.org/papers/E/E17/E17-1044/).
- **On PDNC** (https://arxiv.org/html/2406.11380v3), BookNLP+ scores 98.6% on **explicit** quotes (speaker named at the verb) but 68.9% on implicit or anaphoric ones.
- **No published accuracy exists for vocalisation detection.** I found none. What transfers is this: a named speaker is nearly free, and a pronoun costs about a third.
- **Our own measurement** (`gm/speech.py:270`, 2026-09-25): tagging was "all or nothing per beat", 4 of 8.

### Time-skip clocks

- **Kingdom Come: Deliverance 2** skips time on "a 24-hour wheel" (https://www.thegamer.com/kingdom-come-deliverance-2-how-to-skip-time-sleep-lodging-wait/). Another guide mentions gold dawn, noon and dusk markers and a small clock during fast travel; I did not confirm those.
- **Don't Starve**'s clock is sixteen plain segments coloured by phase (https://dontstarve.wiki.gg/wiki/Day-Night_Cycle — fan wiki). It is the nearest precedent for a numeral-free face of strips.
- **Majora's Mask 3D** changed Double Time to skip "to any hour" (https://en.wikipedia.org/wiki/The_Legend_of_Zelda:_Majora%27s_Mask_3D).
  - The words-only "Dawn of the … Day" card is attested by a fan generator (https://github.com/Artenes/majoras-mask-daw-day-generator).
  - I did not verify its exact wording from a primary source.
- **Skyrim's wait menu**: UESP returned 404, so I did not use it.
- **The wagon-wheel effect** (https://en.wikipedia.org/wiki/Wagon-wheel_effect): rotation that is sampled per frame aliases.
  - One hand reads as turning backwards past 180° per frame, which is 30 rev/s at 60 Hz.
  - Legibility goes well before that point.

### Accessibility

- **WCAG 2.2.2** covers motion that starts automatically, "lasts more than five seconds", and runs beside other content (https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html).
- **WCAG 2.3.3** (AAA) requires that interaction-triggered motion "can be disabled", via `prefers-reduced-motion` (https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html).
- **Live regions** must exist in the DOM before content is injected. Their announcements vanish once read (https://www.sarasoueidan.com/blog/accessible-notifications-with-aria-live-regions-part-1/).
- **Popover API** (https://developer.mozilla.org/en-US/docs/Web/API/Popover_API/Using):
  - `popover="auto"` gives light dismiss and Esc, puts the popover next in Tab order after its invoker, and sets `aria-expanded` implicitly via `popovertarget`.
  - It has been Baseline since January 2025.

### Chips

- **VS Code chat** has inline `#` mentions *and* attachments "preserved in a draft and included when you send" (https://code.visualstudio.com/docs/chat/copilot-chat-context).
- **Discord** sends slash-command options as typed values, separate from the text (https://docs.discord.com/developers/interactions/application-commands). Its pill rendering is not in the primary docs.
- **Gutenberg PR #82042** fixed chips whose remove button's label bled into the chip's name. Each button now reads "Remove %s" (https://github.com/WordPress/gutenberg/pull/82042).

## 3. Tried and abandoned, and why

1. **Foundry v13's always-collapsed sidebar** had no built-in option to change it. At least two modules exist to reopen it on load and restore the last tab:
   - Nore's Interface Enhancements, https://github.com/noreaga/nores-interface-enhancements
   - Forien's UI Tweaks, https://foundryvtt.com/packages/forien-ui-tweaks

   **Lesson:** default to open, and remember each viewer's layout.
2. **One tab at a time.** Foundry's Sticky Sidebar exists to "pin up two sidebar tabs to be always visible" (https://foundryvtt.com/packages/sticky-sidebar): chat *and* combat, together. Our aside shows everything at once, so strict tabs would be a regression.

   **Lesson:** several panels open together. Tabs are for restoring and jumping.
3. **Separate-window pop-outs.**
   - Roll20's double-click pop-out produced long forum threads: accidental pop-outs, chat lost until a reload, and no setting to disable it.
     - https://app.roll20.net/forum/post/10548556/is-it-possible-to-prevent-chat-from-popping-out-or-get-it-back-where-it-started-without-reloading-the-screen
     - https://app.roll20.net/forum/post/9272395/how-to-turn-pop-out-chat-back-to-normal
   - Sticky Sidebar also patches Foundry chat popping out unexpectedly from a collapsed sidebar.
   - The packaged shell settles it anyway. `electron/main.js`'s `setWindowOpenHandler` sends every `window.open` to the external browser.

   **Lesson:** no separate windows.
4. **A partial history.** BG3 added its history only after demand, and it still excludes banter.

   **Lesson:** log every attributed line.
5. **A log that holds the live controls** (Disco Elysium, above).

   **Lesson:** Take your leave, Ignore and the input never sit inside the log's scroll region. Show "latest" when the reader has scrolled up.
6. **Animated flourish later given an off switch** (Pentiment).

   **Lesson:** the clock is short, dismissable, and still under reduced motion from day one.
7. **Backspace that eats chips.** In Vuetify #3069 (https://github.com/vuetifyjs/vuetify/issues/3069), Backspace to fix a typed letter also removed the last chip. The resolution isn't shown.

   **Lesson:** two steps.
8. **A vocalisation tag.** I rejected this before it was tried, for three reasons:
   - Speaker tagging was all-or-nothing, 4 of 8 beats. A `<vocal>` tag inherits that and costs demonstration volume (CLAUDE.md).
   - `speech.lift` wraps a tag's unquoted inner text in quote marks (`speech.py:245`), so `<say who=c1>grunts</say>` becomes a spoken line "grunts".
   - It would still need a detector fallback.

   **Lesson:** detect in code. Revisit only if measured recall is poor.

## 4. Recommended design

### 4.1 Panel system (7.3): one component, two modes

**Markup.** `<aside>` stays; 30+ rules select it. It gains `id="panels"` and contains:

- `#panelbar`: a toolbar of toggle buttons (`aria-pressed`, `aria-controls`), one per panel, closed or open. At the end is "Hide the column" (desktop only).
- Five `<section class="panel">`, each with:
  - a header: a disclosure button holding the title (`aria-expanded`) and a close button (`aria-label="Close the conversation panel"`);
  - a body.
- **Every existing id moves unchanged into a body.** So `renderTalk`, `renderMap`, `renderRolls`, `renderGmView` and `render()`'s `#sheet` block need no edits.

| Panel | Contains | Default |
|---|---|---|
| Sheet | `#sheet` | open |
| Scene | location line, `#order`, `#board`, `#gmview` | open |
| Conversation | `#convo` (§4.2), then `#talk` | open; body collapsed until the first conversation |
| Map | `#mapwrap` (its button still opens `#maptray`) | open |
| Rolls | `#rolls` | open |

**Order and ARIA.**

- The order is fixed and **never automatically reordered**. Moving text under a reader is worse than leaving it where it was.
- Because several panels show at once, this is a toolbar plus disclosures, not the APG tabs pattern.
- Tabs are used *inside* Conversation, where one person's log shows at a time.

**Collapse, close, restore.**

- Collapse hides the body and keeps the header in place.
- Close removes the section; its bar toggle reads unpressed.
- Restore comes from the bar, or from an edge tab.

**Two modes.**

- **Column mode** is today's docked column.
- **Drawer mode** is today's phone slide-over. It applies under 760px, or on desktop after "Hide the column", when the story takes the full width.
- The phone block's `aside` rules become `body.drawer aside` rules, written once.
- A few lines of inline script in `<head>` set `body.drawer` from `matchMedia("(max-width: 760px)")` and the saved layout **before first paint**, so a phone never flashes the column. A `change` listener keeps it current.

**Edge tabs.** `#edgetabs` (replacing `#sheettab`) holds `button.edgetab[data-panel]`:

- **Sheet**: always.
- **Scene**: while a fight is on.
- **Conversation**: while talking, or while there are unread lines, with a count.
- Map keeps its left-edge `#maptab`. Rolls is one tap away in the drawer's bar.

Opening an edge tab:

- slides the drawer in, expands and scrolls to that panel, and focuses its header;
- Esc, close, or a click outside (the existing rule at `01-core.js:73`) closes the drawer and returns focus to the tab;
- `#maptray` and the drawer stay mutually exclusive.

**What comes forward.** Both triggers are edge-triggered, and neither ever moves focus.

- **A conversation starts:** `scene.talk` goes from empty to non-empty, or a new entry arrives from someone present while Conversation is collapsed.
  - *Column:* restore, expand, and scroll into view inside the aside.
  - *Drawer:* **do not open** the drawer, which would cover the beat about to be read. Show the Conversation edge tab with its count instead, in the manner of Foundry's notification tray.
  - If the player closes Conversation mid-conversation, it stays closed until the *next* one starts.
- **A fight starts:** Scene expands (column) or its edge tab appears (drawer).

**Memory and motion.**

- Layout lives in `localStorage["pgm.table.panels.v1"]` as `{open:{}, collapsed:{}, docked:bool}`.
  - Every access is wrapped in try/catch. Unknown ids are ignored.
  - The key is versioned because Electron storage outlives reinstalls.
  - Unreadable means all open and docked (lesson 1).
- Slides reuse `.32s cubic-bezier(.2,.7,.3,1)`. There is none under `prefers-reduced-motion`.

### 4.2 The conversation log (7.1, 7.2)

**Persisted, not derived.** Deriving the log from the transcript's `said` would avoid a second record, but it fails four ways:

- a deleted person's name is gone by then;
- who was in the conversation at that moment is recorded nowhere;
- vocalisations would be re-detected on every read;
- "since last we met" and memory want a per-person index, not a rescan of a transcript that is never trimmed.

So the log is an **append-only index, written once per beat**. The page stays the source of truth.

**Entry** (types in §5):

```
{"n":412,"t":540,"beat":37,"who":"c4"|"you","name":"Drenn Ironvale",
 "to":"you"|"c1"|"","kind":"line"|"vocal","text":"Tell me, have you seen the leaf?",
 "among":["c4"],"src":"tag"|"player"|"tag-adjacent"|"named"|"pronoun"}
```

- An entry is in X's log when `who==X`, or `to==X`, or (`who=="you"` and X is in `among`).
- The cap is 300 per person, oldest dropped (open question 4).

**What is recorded per beat.**

1. **NPC lines:** every `said` record `_finish` keeps. Lines a groomer cut are never logged.
2. **The player's quoted lines** (`speech.lines(player_text)`), with `who:"you"`.
   - `to` is the only person in conversation; failing that, the first `to=you` speaker of the beat; failing that, empty.
   - Continue records nothing.
3. **Vocalisations**, from `speech.vocalisations()`.
   - The PC's come only from the player's own text ("I laugh", "*grunts*").
   - The PC's never come from GM prose, because the narrator does not decide what the PC did.

**`gm/speech.vocalisations(text, said, people)`** is a pure function beside the one scanner (`speech.py:1-30` says why there is only one).

- It reads `blanked(text)`, so nothing inside quotation marks is ever a vocalisation. A quoted "Hmph." is a line.
- It looks for a **closed list** of words, in the MUD-socials tradition:
  - *laugh, chuckle, giggle, cackle, snicker, snigger, chortle, guffaw, titter, grunt, groan, moan, sigh, huff, snort, scoff, sniff, sob, whimper, wail, gasp, growl, snarl, hiss, hum, whistle, cough, yelp, shriek, scream, tut;*
  - "clears (his|her|their) throat";
  - the same words as nouns after "lets out / gives / with / a bark of".

It then finds a speaker. The first tier that answers wins:

| Tier | Rule | Literature |
|---|---|---|
| `tag-adjacent` | The sentence holds a quotation whose `said` record has a `who`. "'Two days,' he says with a short laugh" | explicit, 98.6% |
| `named` | The subject before the verb is a present person's name or head noun. "Drenn grunts." | explicit |
| `pronoun` | Opens he/she/they, **exactly one** non-PC person was named or spoke in the previous sentence, and the pronouns agree | implicit, 68.9%, so only when unambiguous |
| none | nothing recorded | |

**It refuses:**

- negation within three tokens before the verb (*not, never, n't, without, stifles, holds back*);
- any subject that isn't a person in `people`: "the wind moans", "the kettle whistles", "laughter drifts", "the crowd laughs".

**The phrase recorded** runs from the verb (or from "lets out/gives") to the clause's end, at most ten words. "at you" sets `to:"you"`; "at the watchman" sets `to` to his ref if it resolves.

**No repair call.** A missed grunt costs one italic row. A wrong speaker is worse, and a model repair per beat costs local-model time (memory: slice-findings).

- So this runs at Muzny's high-precision operating point.
- A vocal word with no resolved speaker logs `{"kind":"vocal-miss"}` to `turn_log`, so recall can be measured before any tag is considered.

**Names.** Lane A is replacing `judgement._mentions`, which keys on a name's *last* word (item 4: "through"). F needs A's replacement as a public helper. Until then, `people` carries full names and first words only (open question 10).

**Panel (`08-conversation.js`).**

- **Person strip.** APG tabs: automatic activation, arrows, Home/End.
  - Order: the people in the conversation, then others present who have a log.
  - An "All" tab interleaves the current conversation.
  - An "Earlier…" `<select>` loads anyone else through `GET /api/conversation`.
- **Log.** `role="log"` with `aria-live="off"`, because the story already carries the same words.
  - Rows: `Drenn: "Tell me…"`; `You: "…"` in the player colour; *Drenn lets out a low, dry grunt.* in dim italics.
  - A divider shows where the day or the part of day changes ("Day 2 · evening", from `scene.day_part`).
- **Scrolling.** It auto-scrolls only if the reader was at the bottom. Otherwise a "↓ latest" button appears.
- **Controls.** `#talk` (regard, Ignore, Take your leave) sits **below** the scroll region, never inside it.
- **Unread.** Unread counts compare `entry.n` with a per-person `lastSeen` in `localStorage["pgm.table.convo.v1"]`.

### 4.3 The clock pop-up (18)

**When it fires.** Only on a render caused by **this page's own successful POST**.

- `post()` dispatches `table:posted` with the clock it held.
- `09-clock.js` arms on that event. On the next render hook it fires if `clock_minutes − armed ≥ 60`, then disarms.
- It never fires on load, on a resync from the other device, or on a reconnect.
- It covers every door with no server work: say, roll, cast, combat, forage hours, rest, "Some weeks later".
- So the plan's `scene.clock_minutes_before` is **dropped** (§5).
- It waits while a dice mat is open, and is skipped while the tab is hidden.

**Geometry.** Inline SVG, `viewBox 0 0 200 200`:

- **Bezel:** r=94, in the aside's gold gradient.
- **Face:** brass, r=86 (`#d9bd84 → #8a6f3e`).
- **Strips:** **twelve black strips** 6×16 from r=62 to r=78, at `i·30°`, `#0b0806`, with no numerals.
- **Hands:** black with a 1px gold edge.
  - Hour hand: to r=46, 7px wide.
  - Minute hand: to r=70, 4px wide.
  - A 5px boss at the centre.
- **Motion smear:** above 2 rev/s, a `conic-gradient` wedge trails the minute hand at 25%, so the spin reads as motion rather than strobe.
- **Placement:**
  - 168px, centred over `#story`, positioned inside `main` so it never covers the aside.
  - 136px on the phone.
  - Shadow only, no backdrop.

**Angles.** For `Δ = after − before`:

- The hour hand starts at `(before % 720)/2`° and travels `Δ/2`°.
- The minute hand starts at `(before % 60)·6`° and travels `Δ·6`°.
- **Always forward** through the whole span, never the short way back.
- Up to 12h the two are coupled exactly.
- Past 12h:
  - the hour hand makes whole turns, **capped at two**, then goes on to its true end;
  - the minute hand is capped at 14 turns (about 6 rev/s, far below the 30 rev/s reversal point);
  - the caption carries the days.

**Timing.** A fixed 4.0s, under WCAG 2.2.2's five seconds:

| Phase | Duration |
|---|---|
| fade and scale in | 200ms |
| hold the *before* face | 300ms |
| sweep (`easeInOutCubic`, one progress for both hands, `requestAnimationFrame`) | 2200ms |
| hold the *after* face | 900ms |
| fade out | 400ms |

**Caption at 24h or more, in words.** It counts *calendar days crossed* (`⌊after/1440⌋ − ⌊before/1440⌋`), not elapsed hours:

| Days crossed | Caption |
|---|---|
| 1 | "The next day" |
| 2–13 | "Two days later" … "Thirteen days later" |
| 14–20 | "Two weeks later" |
| 21–27 | "Three weeks later" |
| 28+ | "Some weeks later" (the resurrect card's words) |

Each is followed by " · " and `scene.day_part`, for example "The next day · evening".

**Screen readers.**

- The SVG is `aria-hidden`.
- `#clocksay` (`role="status"`, visually hidden, **in the DOM from load**) gets one sentence: "Three hours pass. It is now evening."

**Dismissal.**

- It never blocks input: `pointer-events:none` except on the face.
- A click on the face, or Esc, dismisses it.
- It never takes focus.
- A second qualifying turn restarts it from the current *after*.

**Reduced motion.** No spin and no scale. The *after* face shows for 1.6s with a static gold arc on the bezel from the old hour to the new, then the caption and status, and an opacity fade.

**Deferred.** A dusk/dawn tint stays off in v1.

**Dependency.** Until Lane B charges minutes for travel in town (16.5), only rests, waits, forage hours and journeys fire the clock.

### 4.4 The Spells button and the chip (11, 21.1 front)

**Button.** `<button type="button" id="spellbtn" class="quiet">Spells</button>` goes after Trade.

- It shows when `state.spellcasting.kind` is set (§5), not when `pc.castable` is non-empty (see the finding in §1).
- It joins the `body.resolving` disable rule (`table.html:147`).
- At 375px the row wraps five buttons onto two lines, the arrangement `table.html:1084-1091` already chose. This needs re-measuring.

**Picker.** `#spellpop[popover=auto]`, opened by `popovertarget`.

- **Placement:** placed above the button from `getBoundingClientRect`. A class-toggle fallback covers browsers without `showPopover` (older iOS on a LAN phone).
- **Data:** fetched from `GET /api/sheet` on open. That is the Spells tab's own `spells` block, so there is one source.
- **Layout:**
  - a find box when there are more than 12 entries;
  - **cantrips** first;
  - then each level with **slot pips** (`●●○` from `slots[].left/max`) and its prepared or known spells.
- **Unavailable spells** are greyed, with the **reason as visible text** ("no slot left at level 1", "not prepared"). A tooltip does not exist on a touch screen.
- **Nothing prepared:** a prepared caster with nothing prepared sees "Nothing prepared today." and a button to open the Spells tab.
- **No target picker.** Item 21.1 says the player writes the aim (open question 6).
- **Choosing** attaches the chip, closes the popover, and focuses `#input`.

**Chip markup:**

```html
<div id="attachments" role="group" aria-label="Attached to this turn">
  <span class="chip" data-kind="spell" data-id="burning-hands" aria-label="Spell: Burning Hands">
    <span class="chip-label" aria-hidden="true">✦ Burning Hands</span>
    <button type="button" class="chip-x" aria-label="Remove Burning Hands">×</button>
  </span>
</div>
```

**Placement.** The chip row sits inside `#sayform` just before `#input`, not inside the text.

- A `contenteditable` composer was rejected. It would break the real `<input>` that the iOS 16px rule, the sticky phone form and `player_input` depend on.
- Composers put attachments beside the text, as VS Code does.
- On the phone the chips take their own full-width line.

**Behaviour.**

- **One spell per turn.** A new one replaces the old, and the change is announced.
- **Placeholder:** "What do you do with Burning Hands? (or just Say)".
- **Removal:**
  - with ×, or Delete on the chip;
  - or with Backspace at caret 0 in an empty input: the first press selects the chip, the second removes it;
  - focus always returns to `#input`.
- **Announcements** go to `#saystatus` (`role="status"`, present from load): "Burning Hands attached. Write what you do with it, or press Say." and "… removed."
- **Sending:** the body is `{text, attachments:[{kind:"spell",id}]}`, and empty text is allowed when a chip is present.
- **Clearing:** chips clear with the input, only once the turn is taken. A 422, 412 or 409 keeps both.
- **Transcript:** a player beat with `attachments` renders its chip before the text.
- **The Spells tab's Cast button** now attaches and closes the sheet instead of posting `/api/cast`: 21.1's "one route".

## 5. What the Phase-1 seams must provide

### S3 — `/api/state` (additive; tolerant of absence)

| Key | Type | Notes |
|---|---|---|
| `scene.conversation` | `{"people":[Person],"recent":[Entry],"seq":int}` | **Amends** the plan's "empty list". Empty is `{"people":[],"recent":[],"seq":0}` |
| `…people[]` | `{"ref":str,"name":str,"present":bool,"talking":bool,"lines":int,"last":int}` | Talking first, then present, then by `last` descending; at most 30 |
| `…recent[]` | Entry | The last 80 entries involving anyone present or talking |
| `scene.day_part` | `str` | From a new public `residency.day_part(clock)` wrapping `_PARTS[slot_of(clock)]`, so the JS never copies the table |
| `spellcasting` (top level) | `{"kind":"prepared"\|"spontaneous"\|"","nothing_prepared":bool}` | From `casting.is_caster` and `prepared` |
| player beat `.attachments` | `[{"kind":"spell","id":str,"name":str}]` | Only when sent |
| ~~`scene.clock_minutes_before`~~ | — | **Dropped**; the client arms on its own POST |

**New read endpoint (S3).** `GET /api/conversation?with=<ref|all>&before=<n>&limit=<≤200>` returns `{"entries":[Entry],"more":bool}`, oldest first. An unknown ref returns an empty list.

### S3 — `/api/say` attachments

**Body.** `{"text":str,"carry_on":bool?,"attachments":[{"kind":"spell","id":str}]?}`

**Refused with 400** (a sentence for a person) when:

- there is more than one attachment (v1);
- `kind` is anything but `"spell"`;
- the `id` is not resolved by `spells.get`;
- the spell is not in the PC's book, known or prepared list ("Bobby does not know Fireball.");
- an attachment is combined with `carry_on`, `/gm` or `/cheat`.

**Rules for text.**

- Empty `text` is allowed when an attachment is present. The shown line is then `"I cast {name}."`.
- `player_input.check` runs only on non-empty text.

**Storage.** The attachment is stored on the player beat, and as `agent.attachments: list[dict]`, cleared each turn like `claim`. It is not acted on until Lane E.

### S4 — `Scene.conversation_log: list[dict]` plus `conversation_seq: int`

| Field | Type | |
|---|---|---|
| `n` | int | monotonic, never reused |
| `t` | int | `clock_minutes` |
| `beat` | int | transcript index (the GM beat, or the player beat for player lines) |
| `who` | str | ref or `"you"` |
| `name` | str | snapshot |
| `to` | str | `"you"`, ref, or `""` |
| `kind` | str | `"line"` or `"vocal"` |
| `text` | str | |
| `among` | list[str] | refs in conversation after the beat |
| `src` | str | `tag`, `player`, `tag-adjacent`, `named` or `pronoun` |

Missing keys load as `[]` and `0`. Unknown entry keys are kept.

### S3 — the aftermath step

- **Member shape:** `run(ctx: AfterBeat) -> None` with a module `ORDER: int`.
- **Call site:** called from `_finish` after the `said` block (`views.py:2215`).
- **Errors** are caught and logged as `{"kind":"aftermath-error","member","error"}`. A log line never fails a turn.

```python
@dataclass(frozen=True)
class AfterBeat:
    campaign: "Campaign"            # members write only their own Scene field
    scene: "Scene"
    beat_index: int                 # the GM beat just appended
    text: str                       # the beat as it stands on the page
    said: tuple[dict, ...]          # the Said records kept on it
    player_text: str                # "" for buttons / carry_on
    carry_on: bool
    attachments: tuple[dict, ...]
    talking_after: tuple[str, ...]  # engine.talking_to() refs after resolution
    people: dict                    # ref -> {"name", "pronouns", "is_pc"}
    outcomes: tuple
    clock_before: int               # noted by _finish's callers on entry (Lane B wants it)
    clock_after: int
```

### S6 — mount points and hooks

**`table.html` mount points.**

- `<aside id="panels">` containing:
  - `#panelbar`, with `button.panelbtn[data-panel]`;
  - `section.panel#panel-{sheet,scene,conversation,map,rolls}`, each with `.panelhead > button.paneltoggle[aria-expanded] + button.panelclose`, and `.panelbody#panel-<id>-body`.
- `#convo` (holding `#convo-people`, `#convo-log` and `#convo-latest`) sits above the moved `#talk`.
- `#edgetabs`.
- `#clockpop` inside `main`, and `#clocksay`.
- `#spellbtn` and `#spellpop[popover]`.
- `#attachments` before `#input`, and `#saystatus`.
- The pre-paint `body.drawer` script.
- Script tags for `07`–`10` via `{% asset %}`. S6 ships `08`–`10` as stubs, so G1 has no 404s.

**JS hooks.**

- In `02-state.js`:
  - `render()` keeps `prev = STATE` and calls `runRenderHooks(s, prev)` **before** `if (hold) return`;
  - `post()` dispatches `table:posted` `{url, clockBefore}` after its status checks;
  - the beat renderer draws `b.attachments`.
- `07-panels.js` exports `onRender(fn)` and `Panels = {open, close, collapse, expand, forward, mode}`.

## 6. Owned edits: confirm or amend

**S6: amend.** It also edits:

- `01-core.js`: replace `showSheet` and the drawer branches of the click and keydown listeners with `Panels` calls. Edit them rather than redeclaring them in `07`: a later classic script's `function showSheet` silently wins, which is the JS form of what `test_no_silent_shadowing.py` guards against in Python.
- `02-state.js`: the three hook lines.
- The stub files `08`–`10`.

**Lane F: confirm, plus additions.**

Confirmed from the plan:

- `08-conversation.js`, `09-clock.js`, `10-spells.js`;
- `play/aftermath/conversation_log.py`;
- `speech.vocalisations()` — only that. `lift` and `spans` are read by Lane A and stay untouched;
- `table.html` CSS for the three components.

Added:

- `04-combat-and-turns.js`: `takeTurn` (clears the chips) and `#sayform.onsubmit` (sends `attachments`, allows empty text). No lane owns these today.
- `02-state.js`: the `.castbtn` handler (attach instead of cast). This is in a different function from S6's hooks.

**Not F's:**

- `views.py` (S3 in Phase 1, E in Phase 2);
- `residency.day_part` (S3 or S5);
- the `_castable_summary` fix (E);
- the combat bar's Cast… (open question 8).

## 7. Packaged-app notes

- **No window pop-outs.** `setWindowOpenHandler` sends `window.open` to the external browser. Anything that "pops out" must stay in the page.
- **`minWidth: 1000`.** The packaged window never reaches the 760px layout, so drawer mode appears there only via "Hide the column". The phone layout is verified in a browser at 375×812; LAN phones use it for real.
- **New scripts** load through `{% asset %}`, whose content hash defeats the Electron disk cache that outlives reinstalls (`templatetags/assets.py:1-10`).
- **localStorage.**
  - It lives in user data, keyed by origin (127.0.0.1:8917).
  - The keys are versioned and unknown ids are ignored.
  - A changed port just means the default layout.
- **Popover.** Electron 33 is Chromium 130, and popover shipped in Chromium 114. This is inferred, not tested.
- **Reduced motion.** `prefers-reduced-motion` should follow Windows' "Animation effects" setting through Chromium. **Unconfirmed**: verify it by toggling the OS setting against the packaged build.
- **The pre-paint script** uses no template variables, which is the `PATHFINDER_BOOT` lesson at `table.html:1733`.

## 8. Tests and verification

### Python tests (`test_f_*`; docstrings name the measurement)

- **`test_f_vocalisations.py`**
  - "lets out a low, dry grunt" with a named subject → recorded.
  - A tag-adjacent laugh → the tag's speaker.
  - "he" between two men → nothing.
  - "wind moans", "kettle whistles", "laughter drifts", "crowd laughs" → nothing.
  - "does not laugh", "without a laugh" → nothing.
  - A quoted "Hmph." → a line, never a vocal.
  - Over R0's Bobby replay corpus with hand labels: **precision ≥ 95% (gated)**. Recall is reported, not gated.
- **`test_f_conversation_log.py`**
  - `said` lines are recorded with who/to/name/among.
  - Groomer-cut lines are absent.
  - Continue records no player line.
  - A deleted actor keeps their name.
  - The cap holds.
  - **The no-scenery invariant** over the corpus: every `line` entry's text is in `speech.lines()` of its beat or the player's text, and every `vocal` entry's text lies outside quotations.
- **`test_f_state_payload.py`**
  - The shapes of `scene.conversation`, `day_part` and `spellcasting`.
  - `/api/conversation` paging.
  - The four Bobby saves load with an empty log.
  - End to end: empty text plus a chip → the shown line is "I cast Burning Hands." and `attachments` is on the beat. The validation matrix is S3's.
- **`test_f_page.py`**
  - The mount ids are present.
  - `07`–`10` are loaded in order via `{% asset %}`.
  - **No top-level `function` name is declared in two table scripts.**
  - `#clocksay` and `#saystatus` are in the served HTML.
  - Reduced-motion rules cover `#clockpop`, `aside` and `.panel`.

### JS tests (node `vm` with stubbed DOM; skip without node, like `test_template_scripts.py`)

- **Clock:**
  - 08:00→09:00 = hour +30°, minute +360°.
  - 08:00→20:00 = hour **+360°**, not 0°.
  - 23:00→01:00 = +60°, not −300°.
  - 72h = two hour turns plus the remainder, the minute hand capped at 14 turns, and the caption "Three days later · …".
  - Δ=59 does not fire; Δ=60 does.
  - No fire on the initial render or on a resync.
- **Chip:**
  - A new chip replaces the old.
  - Backspace takes two steps.
  - The body carries `attachments`.
  - The chip survives a thrown 422.
- **Panels:**
  - Layout round-trips through a throwing `localStorage` stub, and defaults to all open.
  - "Forward" fires once per conversation start, and not after the player closes the panel.

### Browser checks (Claude Browser pane, own port, killed by port)

1. **At 1440×900:**
   - collapse, close and restore each of the five panels;
   - reload keeps the layout;
   - "Hide the column" gives edge tabs;
   - zero console errors.
2. **At 375×812:**
   - no horizontal scroll;
   - the story stays at least 34dvh;
   - Spells wraps with the other buttons;
   - each edge tab opens the drawer, and Esc returns focus to it.
3. **In a conversation:**
   - Conversation expands (column) or its tab shows a count (phone);
   - the log holds only quoted lines and italic vocal rows, matched against the same beats in the story.
4. **Rest 8h:**
   - the clock spins about 2.2s and dismisses on click;
   - a 30-minute act does not fire it;
   - with reduced motion emulated, a static end face and the caption.
5. **Spells → Burning Hands:**
   - the chip appears with focus in the input;
   - an empty Say → "I cast Burning Hands." with the chip in the transcript.

### Packaged check

`prove_shell --packaged` against a throwaway data directory seeded with the Bobby save, after cleaning `%TEMP%\_MEI*`.

- Repeat checks 1 and 3–5, plus the Windows animation toggle.
- **Pass:** identical behaviour and no console errors.

## 9. Open questions for the owner

1. **An in-page "wide" Conversation tray** (like the map tray), or is the panel enough? Separate windows are ruled out.
2. **The player's unquoted speech** ("I ask him about the girl"): log it as an indirect italic row, or quoted words only?
3. **NPC indirect speech** ("Drenn asks where you're headed"): log it, or treat it as narration? v1 treats it as narration.
4. **Per-person cap of 300?** And should existing saves be backfilled from the `said` already on their beats (since 2026-09-25)?
5. **The face:**
   - twelve identical strips, or a heavier one at twelve so the orientation reads?
   - brass (proposed) or dark?
   - hour hand capped at two turns?
   - dusk/dawn tint now or later?
6. **No target picker** in the Spells popover (21.1 supersedes item 11's picker). Agree?
7. **The phone never auto-opens the drawer** for a conversation; it shows a badged edge tab instead. Agree?
8. **Combat bar's Cast…:** route it through the same picker? If so, which lane owns `#cb-cast` in `04-combat-and-turns.js`?
9. **Opening lines:** log the opening companion's first lines? That needs the aftermath hook on the opening path, and `campaign.py` is Lane C's in Phase 2.
10. **Lane A's helper:** Lane A should publish its `_mentions` replacement (name or head noun, never the last word) as a public helper, named in `docs/fix-interfaces.md`.

# Research: first-time tutorials for every section (2026-11-21)

For `docs/tutorials-plan.md`. The owner asked for "a tutorial for each section that takes the
user through everything they need to know about a page or menu the first time they interact
with it and then a button to view those tutorials again". This note covers what the field
has measured and what it tried and then dropped. It was written before any design, as
CLAUDE.md requires.

**How to read the source marks:**
- **[read]**: the primary source was opened and read for this note.
- **[quoted]**: seen only in search snippets or quoted by another page.
- **[unconfirmed]**: could not be verified.

A critic pass checked this note before the plan was written. Its corrections are folded into
the text, and the claims it weakened are listed at the end.

---

## 1. What the UX research measured

### NN/g, "Mobile Tutorials: Wasted Effort or Efficiency Boost?" (Kendrick, 2020)

https://www.nngroup.com/articles/mobile-tutorials/ **[read]**

This is the measurement behind "deck-of-cards tutorials don't help". The study was
between-subjects, n=70, on four simple iOS apps, comparing a deck-of-cards tutorial against
skipping it.

| Measure | With tutorial | Without | Significant? |
|---|---|---|---|
| Task success | 91% | 94% | no |
| Time on task | 93.5 s | 85.2 s | no |
| Perceived ease (7-point) | 4.92 | 5.49 | yes, p = 0.047 |

So the people who read the tutorial found the tasks *harder*. The author limits this to
simple apps, and our app is not simple, so section 2's complex-game result matters more.

### NN/g, "Onboarding Tutorials vs. Contextual Help" (Laubheimer, 2023)

https://www.nngroup.com/articles/onboarding-tutorials/ **[read]**

- **Push revelations** are help shown out of context, at launch or at random. **Pull
  revelations** are help triggered by a signal that the user needs it now, such as coach
  marks or tooltips at the point of use.
- Pull is harder to build, because a bad guess at what the user needs gives you Clippy.
- Its guidelines are to make help:
  - easy to dismiss;
  - easy to find again;
  - progressively disclosed;
  - never a multistep procedure the user has to memorise;
  - never an explanation of conventional controls.
- It says walkthroughs are "dramatically overused".

### NN/g, "Instructional Overlays and Coach Marks for Mobile Apps" (Harley, 2014)

https://www.nngroup.com/articles/mobile-instructional-overlay/ **[read]**

- Show **one hint at a time**, in context, when the user reaches that section.
- **Chains of tips** get dismissed faster and make the app look intimidating.
- Users cannot read a hint and use the app at the same time, so a hint that covers the UI
  forces them to memorise it.
- Annotations must look non-interactive. Testers tried to tap a polished overlay in the
  Wimbledon iPad app.

### NN/g, "Mobile-App Onboarding" (Kendrick, 2020)

https://www.nngroup.com/articles/mobile-app-onboarding/ **[read]**

- Avoid onboarding "whenever possible" and spend the effort on usability instead.
- If you must have a deck, keep it to few cards, one concept per card, with a visible Skip.
- Instructional overlays should be timely, unobtrusive, optional, and shown at the first
  encounter with the feature.
- Error messages are teachable moments.

### NN/g, "Progressive Disclosure" (Nielsen, 2006)

https://www.nngroup.com/articles/progressive-disclosure/ **[read]**

Defer advanced material to a second level. More than two levels gets lost.

## 2. What games measured and changed

### Andersen et al., CHI 2012, "The Impact of Tutorials on Games of Varying Complexity"

https://grail.cs.washington.edu/projects/game-abtesting/chi2012/chi2012.pdf **[read]**, text
extracted from the PDF.

The study ran more than 45,000 players across three games (Refraction, Hello Worlds,
Foldit) and eight tutorial conditions.

- **Presence.** Tutorials helped only in Foldit, the most complex game. There,
  context-sensitive tutorials gave 75% more levels played and 29% longer play than no
  tutorial (the abstract hedges both as "as much as"). In the two simpler games they had no significant effect.
- **Context.** In Foldit, teaching a concept just before it is needed beat an up-front
  manual: 16% more play time and 40% more progress. The simpler games showed no difference.
- **Freedom.** "Stencils", which block everything except the action being taught, did not
  improve engagement in any of the three games.
- **On-demand help.** A help button improved Foldit, did nothing in Hello Worlds, and
  *hurt* retention in Refraction.
- The authors conclude that tutorials may not pay for themselves in games players can learn
  by experimenting.

**What this means here.** Pathfinder GM is a Foldit-class game in complexity: 1e rules,
five benches, several map levels. That is the class where in-context teaching paid off.
The same study is evidence against blocking stencils, and against a front-loaded manual.

### Crusader Kings III

Paradox, Dev Diary #16, "Tutorials and Tooltips and Encyclopedias, Oh My!"
https://forum.paradoxplaza.com/forum/developer-diary/ck3-dev-diary-16-tutorials-and-tooltips-and-encyclopedias-oh-my.1345581
**[quoted]**, snippets only.

- It describes a guided tutorial "as opposed to the menu-driven tutorials of past Paradox
  games".
- Tooltips nest inside tooltips, with a timer lock or an action lock.
- Concepts feed the encyclopedia and the tooltips from one source.

Martins and Zetterman (Paradox), "Deep Dive: Refreshing the Crusader Kings III tutorial
mode through optimized UX", Game Developer, 2024-09-12 **[read]**
https://gamedeveloper.com/design/deep-dive-refreshing-the-crusader-kings-iii-tutorial-mode-through-optimized-ux

**This is the abandonment that matters most here.**
- The original tutorial was **67 sequential boxes**.
- The article says both that "the tutorial has a significant impact on the retention rates
  of our players" and that *finishing* it "wasn't a major determining factor" in whether
  players kept playing. It never reconciles the two.
- New mechanics "aren't covered by the in-game tutorial" (our word for it: stale), and its
  windows did not resize to their text.
- The rework cut it to about one third and rewrote it. It added progressive disclosure on
  the character panel, and onboarding events with tooltip explanations.
- The old tutorial was kept for comparison. No outcome numbers are published.

### Baldur's Gate 3

- The options include "Show Tutorials" (on by default), "Reset Tutorials" (re-shows every
  seen tip), and Expand/Pin Tooltip. Source: the fan wiki, https://old.bg3.wiki/wiki/Options
  **[read, secondary]**.
- Players complain that tips vanish after 3–5 seconds and stack up:
  https://steamcommunity.com/app/1086940/discussions/0/3808408328760533890
  **[quoted, anecdotal]**.
- Swen Vincke has said Act 1 is the tutorial **[quoted]** (PC Gamer).
- A journal tab of past tutorials **[unconfirmed]**.

### Civilization VII

Firaxis's beginner's guide **[read]**:
https://civilization.2k.com/en-GB/civ-vii/news/civilization-vii-beginners-guide/

- Tutorial messages and advisors are "enabled by default the first time you play".
- Advisors give "advice rather than required mandates".
- An "Only Warnings" advisor level **[quoted]**: in snippets only, not on the page read.

Nothing primary was found on how the Civilopedia was designed.

### Pathfinder: Kingmaker / Wrath of the Righteous

Nothing primary was found on Owlcat's tutorial pop-ups or encyclopedia links **[unconfirmed]**.

A fan guide says Wrath's encyclopedia is "hidden away in a series of menus" and suits
reference better than learning:
https://pathfinderwrathoftherighteous.wiki.fextralife.com/New+Player+Help **[quoted]**.
Even as hearsay, it supports keeping the reference (our Manual) reachable from the point of
use and not only from a menu.

### Celia Hodent

GDC 2016, "The Gamer's Brain, Part 2: UX of Onboarding and Player Engagement",
https://gdcvault.com/play/1022951/ **[read, abstract only]**. The abstract covers onboarding
pitfalls and how the brain learns.

The phrases "learning by doing" and "onboarding can't make up for bad usability" are
attributed to her in snippets of a uxdesign.cc article that returned 403 **[quoted;
authorship unconfirmed]**. The plan does not rest on them. Andersen 2012 carries the same
point with numbers.

## 3. Accessibility

### WAI-ARIA APG, modal dialog pattern

https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/ **[read]**

- Tab is trapped inside the dialog, and Esc closes it.
- On open, focus goes to the first control, or to a `tabindex=-1` heading when there is
  much text. On close, focus returns to the control that opened it.
- `aria-modal` is used **only** when the outside really is inert. Otherwise screen-reader
  users are cut off from content that sighted users can reach.
- The APG notes that a non-modal dialog usually lets focus leave without closing.

### WCAG 2.2

**SC 2.4.11 Focus Not Obscured (Minimum), AA** **[read]**
https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html

At AA the focused control may be partially obscured; it fails only when it is *entirely*
hidden. The text calls a non-modal overlay that does not take focus "at risk of failing", not
a definite fail. A proper modal passes, and so does content the user opened, if Esc reveals
the focused item again.

**SC 1.4.13 Content on Hover or Focus, AA** **[read]**
https://www.w3.org/WAI/WCAG22/Understanding/content-on-hover-or-focus.html

Content shown on hover or focus must be dismissible, hoverable and persistent. Modals are out
of scope. That a click-opened card is also out of scope is the researcher's inference, not
the text's.

**Not re-read this session [unconfirmed here]:**
- 2.2.1 Timing Adjustable: why a hint must never auto-dismiss on a timer, as BG3's do.
- 2.2.2 Pause, Stop, Hide.
- 2.3.3 Animation from Interactions (AAA).
- 4.1.2 Name, Role, Value.

### Tour libraries' accessibility record

From GitHub issues **[read]**:

- **driver.js #376.** Steps were not announced and there was no focus trap. Fixed in 1.1.0.
- **driver.js #434.** axe failures. Fixed in 1.10.2.
- **Shepherd #3202.** Tab skipped the highlighted element. Fixed.
- **Intro.js #782 and #1017.** VoiceOver did not read the steps.
- **Intro.js #2087 and #2107.** The accessibility requests were closed by a stale-bot, not
  fixed.
- **Intro.js #2207 (2026).** Its highlight layer at z-index 9999998 **swallows clicks** on
  targets inside stacking contexts.

Intro.js #2207 is the 0.2.13 bug class exactly (memory: hidden-harvest-layer-clicks).

## 4. Libraries and licences (checked 2026-11-21)

Sources: GitHub API, npm, Bundlephobia.

| Library | Version | Licence | Size (min / gz) | Overlay |
|---|---|---|---|---|
| driver.js | 1.14.0 | **MIT** (LICENSE and package.json) | 47 / 15.2 KB, 0 deps | SVG cutout that takes clicks; `role=dialog`, `aria-live`, reduced-motion CSS |
| Shepherd.js | 16.0.0 | **AGPL-3.0 or paid commercial**. Last MIT release was 13.0.3 (2024-08-05); AGPL from 14.0.1 (2024-10-10). 13.x–14.x (exactly 13.0.3 to 14.5.1) pulled in the `@scarf/scarf` telemetry package. | 27.5 / 10.7 KB | SVG cutout |
| Intro.js | 8.7.0 | **AGPL-3.0 or paid commercial**. Free only before 2.0.0; npm shows AGPL from 2.5.0. | 73 / 20 KB | helper layer (see #2207) |

The driver.js repository has moved to github.com/nilbuild/driver.js.

**For a distributed .exe, AGPL is a real obligation.** Distributing it means offering the
source of the whole combined work under the AGPL, or buying a licence. Shepherd ≥14 and
Intro.js are therefore out. driver.js is the only permissive option.

### The no-library option, from the platform

**Sources:**
- MDN, "Using the Popover API": https://developer.mozilla.org/en-US/docs/Web/API/Popover_API/Using **[read]**
- MDN browser-compat-data 8.1.10 **[read]**

**What the Popover API gives:**
- `popover` renders in the **top layer**. That sidesteps z-index and stacking-context fights
  entirely, which is the Intro.js #2207 failure.
- `popover="manual"` does not light-dismiss. `auto` closes on an outside click or Esc.
- Closing from the keyboard returns focus to the invoker.
- An invoker creates an implicit anchor for CSS anchor positioning.

**Chromium support:**

| Feature | Chromium version |
|---|---|
| `<dialog>` | 37 |
| `inert` | 102 |
| `popover` | 114 |
| `anchor-name`, `@position-try` | 125 |
| `position-area` | 129 |

**Electron.** The app pins `electron ^33.2.1` (electron/package.json). Electron 33 is
Chromium 130 by my memory of the release table **[unconfirmed]**. Either way the app already
calls `showPopover` behind a feature check (05-sheet.js `detailPop`, 10-spells.js
`HAS_POPOVER`).

**A LAN phone or tablet** needs Safari 17 or Firefox 125 for `popover`, and Safari 26 or
Firefox 147 for anchor positioning. So the card must also place itself without anchor CSS.

## 5. Storing "seen", and versions

**Appcues** frequency options **[read]**:
https://docs.appcues.com/user-experiences-targeting/setting-up-flow-frequency
- Options are "Show once", "every time", "N times", and "Stop showing when completed".
- Seen state is per user.

**Pendo** **[read]**: https://support.pendo.io/hc/en-us/articles/51431704312603
- Seen state is per visitor ID.
- Opted-out visitors get no auto-launched guides, because Pendo cannot know what they have
  seen. Guides the user launches still work.

**Editing a tour does not re-show it.** That is true of Usetiful and PostHog **[quoted]**.
- To re-show, you restart the tour for everyone or mint a new tour id.
- Renaming a tour makes it a new tour (Usetiful).

**No vendor was found that re-shows only the changed steps.** A per-step version is our own
design, with no prior art behind it.

**Client-side seen state is fragile.** Intercom community posts say clearing cookies brings
tours back **[quoted, anecdotal]**.

## 6. Keeping the words true

**Vendors treat a missing anchor as a runtime incident.**
- Intercom logs a pointer whose target "isn't visible". It also skips a tour whose first
  target is missing, and stops a tour across pages:
  https://www.intercom.com/help/en/articles/2901130-track-and-resolve-your-product-tour-s-issues
  **[read]**
- Appcues, Intercom and PostHog all recommend a stable data attribute over a styling
  selector (`data-appcues`, `data-intercom-target`, `[data-attr]`) **[quoted]**.

**"Docs as Tests"** (Manny Silva, Doc Detective) runs documented steps against the product
**[quoted]**:
- https://www.npmjs.com/package/doc-detective
- FOSDEM 2025 slides

**A test that fails when a tour anchor vanishes** is our inference from the above. No tour
library was found doing it.

---

## 7. What is already in this codebase (prior art at home)

The best precedents are our own:

- **`content/rules/skills-explained.json` + `rules/skillhelp.py` + `tests/test_skill_help.py`.**
  Every "In this game" sentence names the file that makes it true and a literal piece of
  that file's code, and the test reads each one back: "a sentence cannot outlive the code
  it describes". The page is never shown the anchors. Tutorial text should be kept true by
  the same mechanism.
- **`skillhelp.js`.** A toggletip ("?"), built to WCAG 1.4.13 (dismissible, hoverable,
  persistent). It works by hover, focus and tap, is read through `aria-describedby`, and is
  "No third-party code, as everywhere in play/static/js".
- **`33-bench-games.js` first-time card.**
  - Every minigame (9 herbal, 10 forge, 8 alchemy, 6 enchanting, about 12 leather) already
    has a `first` card.
  - The card shows until the player scores 0.6, stored in `localStorage`
    (`pgm.games.seen.<method>`).
  - It starts the game by itself after 2 seconds.
  - This is the per-section first-interaction hint, already shipped, and the minigames do
    not need a second one.
- **The Region map's Travel panel** already teaches in place, for example "On foot, one hex a
  move: five hours … Press any hex you have seen to walk there". So does the forced-march
  line in `16-tab-map.js`. But that line **hardcodes** "DC 10, 2 more each hour, 1d6
  non-lethal". The same numbers live in `rules/survival.py` (`forced_march_dc`,
  `FORCED_MARCH_DAMAGE`), which is the drift this plan must not repeat.
- **`/manual`** has anchors: `#playing`, `#combat`, `#benches`, `#forge`, `#alchemy`, and so
  on. It is our Civilopedia, the pull reference.
- **The revamp notices.** The enchant, alchemy and leather shells show a "first time the
  bench opens after the revamp" notice. That is a version-stamped what's-new, done three
  times by hand.
- **`prefs.js`.** Per-machine preferences in `localStorage`, deliberately: "a quiet room is
  quiet whatever game is open".

## 8. Tried and abandoned (the field's, and ours)

| What | Who dropped it | Why |
|---|---|---|
| Long front-loaded tutorial | CK3 (67 boxes cut to ~⅓) | Finishing it was not a major retention factor (though the tutorial itself mattered); it no longer covered new mechanics |
| Deck-of-cards at launch | NN/g measured | No gain in success or time; users rated tasks harder |
| Menu-driven tutorial (a list you open) | CK2 → CK3 [quoted] | Replaced by guided, in-context teaching |
| Blocking stencils (only the taught action is clickable) | Andersen 2012 | No engagement gain in any game; ours would also block play |
| Up-front manual as the teacher | Andersen 2012 | Lost to just-in-time teaching in the complex game |
| Chains of coach marks | NN/g 2014 | Dismissed faster; look intimidating |
| Help that guesses when you need it (Clippy) | NN/g 2023 | Bad inference is worse than none |
| Timed tips that vanish | BG3 player complaints (anecdotal) | Unreadable; also WCAG 2.2.1 |
| Permissive tour libraries | Shepherd (MIT → AGPL 2024), Intro.js (→ AGPL 2016 at v2.0.0 per vendor; npm field from 2.5.0) | Licence changes after adoption |
| Full-screen click-catching highlight layers | Intro.js #2207; our own 0.2.13 | They eat clicks |

## 9. Claims the critic pass weakened

- "NN/g found tutorials get forgotten": the n=70 study measured success, time and perceived
  ease, not recall. The "forgotten" claim is the 2023 article's argument, not a measurement.
- "CK3's tutorial failed": Paradox published neither failure nor success numbers. They said
  the tutorial significantly affects retention *and* that finishing it was not a major
  factor; the first draft of this note quoted only the second.
- "A non-modal card over focus fails 2.4.11": only if it hides the control entirely.
- "Clippy" was attributed to Andersen too; Andersen tested no guessing help. NN/g only.
- Intro.js's AGPL date was given as ~2017; the vendor says v2.0.0 (2016-02-22).
- "BG3 has a tutorials journal": unconfirmed. Only the Reset Tutorials option is sourced, and
  only by a fan wiki.
- "Hodent: learning by doing": attribution unconfirmed. The plan cites Andersen instead.
- "Click-opened cards are outside 1.4.13": the researcher's inference, not the
  Understanding text.
- "Electron 33 = Chromium 130": from memory. The design does not depend on it, because it
  feature-detects as the house code already does.

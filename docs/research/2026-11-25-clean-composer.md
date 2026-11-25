# Research, lane ui/clean-composer (2026-11-25): a clean typing bar

The owner, 2026-11-25: "the bar where we are typing has become very crowded. lets organize
and hide the locations and other buttons so that it feels clean again."

## What sits in and around the bar today

Measured on the owner's own save (Shadow, in the death room, fighting a poltergeist) at
1400x950 on `integrate/0.5.1-impl` 435217e5. The desk's upper half (`.choices`) held
**836px of controls in a 283px box**, so it scrolled three screens deep above the pen.

| Control | Where | What it does | How often a player needs it |
|---|---|---|---|
| Text box (`#input`) and **Say** | pen | the turn itself | every turn |
| **Continue** | pen actions | keep to what you were doing, the world takes a beat (owner ruling 2026-09-18) | often |
| Attached chip (`#attachments`) | pen | the spell or place riding with the words | whenever something is attached |
| `?` (`help-table`) | pen actions | the table's tips again | rarely, but it is the same `?` every panel wears |
| **Craft action** | pen actions | opens the crafting hub (forage, prospect, skin, buy) | now and then, never in a fight or talk (disabled there) |
| **Spells** | pen actions | the spell picker; casters only | casters, out of a fight (the combat bar has its own Cast...) |
| Ways on (`#exits`) | choices | 0 to 11+ place buttons in up to three groups (Next door, Outside, Roads), each attaching a place chip | once per scene, at its end |
| Berths (`#passage-offer`) | choices | a harbourmaster's offered passages, only while talking to one | rare, and only then |
| Suggestions (`#suggestions`) | choices | the GM's three offers; a click fills the pen | most turns, as a prompt |
| Your abilities (`#abilities`) | choices | class abilities as buttons; a click acts at once | rarely out of a fight; in a fight the combat bar's Ability... does it |
| Combat bar (`#combatbar`) | choices | the fight's turn builder | every fight turn; the fight's own state, not the pen |

In the owner's dungeon the ways on alone were 11 buttons (8 Outside, 3 Roads) wearing
"withdraw" each: 13 lines of the 836px.

## How others keep a composer clean

**AI Dungeon.** The input is one line; the action modes (Do, Say, Story, See) sit behind a
single "Take a Turn" control rather than as a row of buttons. Sources:
https://help.aidungeon.com/faq/how-to-play, https://help.aidungeon.com/faq/do-mode,
https://help.aidungeon.com/faq/say-mode. (I could not confirm the current layout of the
menu from the docs alone; the help pages name the modes and the menu, not their pixels.)

**Discord.** One `+` inside the text field holds Upload a File and the apps; the field
stays a field. Users complained that the `+` opens a menu even with one option ("Why ...
do I need to double click to post a file?"), which is the cost of a tray: never put the
one thing people use every time behind it.
https://support.discord.com/hc/en-us/articles/25444343291031-File-Attachments-FAQ,
https://support.discord.com/hc/nl/community/posts/4403710910743. Stream's chat SDK, which
copies the pattern, renders a single action as a plain button instead of a one-item menu:
https://getstream.io/chat/docs/sdk/react/component-reference/message-composer/attachment-selector/

**Slack.** The March 2020 redesign added "a new lightning bolt icon next to the message
input field" that opens app shortcuts, so the actions sit behind one button beside the
field. https://slack.com/blog/productivity/simpler-more-organized-slack (A Stanford page
on folding the formatting toolbar is now behind a login and could not be checked.)

**ChatGPT (2025).** The composer's row of tool toggles was folded into one Tools menu beside
the `+`; a chosen tool is shown as a label on the bar, so the hidden choice stays visible
once made. https://bgr.com/tech/chatgpt-got-a-makeover-but-all-of-your-ai-tools-are-still-there
(secondary source; I could not find the matching OpenAI release-note entry).

**Foundry VTT.** The chat log keeps its roll modes as one drop-down, not as buttons.
Modules exist that turn it back into selector buttons (my inference: a row is some
players' preference, not the default). https://foundryvtt.com/article/chat/,
https://foundryvtt.com/packages/df-chat-enhance

**Baldur's Gate 3.** Early Access Patch 7 (February 2022, the Barbarian patch) made the
hotbar "more intuitive and less cluttered" by collecting "common actions, class-specific
actions, and spells and items into 'Decks'". https://steamdb.info/patchnotes/9069716
(403 to the critic pass; the quote was confirmed through Gamingbolt's coverage of the notes).

**Nielsen Norman Group, progressive disclosure.** Show what is frequently needed; defer the
rest to a secondary layer; get two things right, the split and the path ("It must be
obvious how users progress from the primary to the secondary disclosure levels"), with the
trigger in "a clearly visible spot" and "strong information scent"; levels beyond two
"typically have low usability". https://www.nngroup.com/articles/progressive-disclosure/

**NN/g, hidden navigation (the counter-evidence, borrowed).** A study of site navigation,
not composer actions, so borrowed here by analogy. On desktop, Slate's navigation hidden
behind a hamburger was used 17% of the time against a 42% average; BBC's "combo" (a
visible bar plus a "More" item) and 7Digital's fully visible navigation were both used over
43% of the time. Bloomberg, also a combo but with a low-contrast bar, managed 28%. Their
advice is clear, information-scent-heavy labels ("Menu", "Browse") if anything is hidden.
https://www.nngroup.com/articles/find-navigation-desktop-not-hamburger/

## What the traditions keep visible and what they hide

- Kept: the field, the send, and the one other action used most (Continue here).
- Hidden behind one labelled control: everything that is either rare or a set of choices
  (attachments, apps, tools, roll modes).
- The chosen thing is shown on the bar once chosen (ChatGPT's label; our chip already does it).
- A one-item menu is a defect (Discord, Stream): a tray with nothing but one button should
  be that button.
- The BBC pattern (the frequent things visible, the rest behind one labelled "More") did as
  well as everything visible; a hidden-only design did far worse. Labels with scent, then.

## Chosen

**Two labelled disclosures in the pen's action line, each one click from the text box:**

1. **Ways on (n)**: the whole ways-on row, unchanged inside (groups, shut ways with their
   reason line, withdraw marks), in a popover above the button. Picking a way attaches it as
   before and closes the popover; the chip in the pen is the visible "chosen" state. The
   button carries the count so the player knows there is somewhere to go without opening it,
   and wears the fight's alarm border while every way is a withdraw.
2. **More**: Craft action, Spells (casters) and Your abilities, grouped by purpose, in a
   popover. Each still does exactly what it did; the tray closes as it acts. When the tray
   would hold Craft action alone (no spells, no abilities), there is no More: Craft action
   stands in its place as a plain button (the one-item-menu rule, from the critic pass).

A door with nothing behind it is not drawn (no ways on: no Ways on button). Ways on with one
way still opens its popover: the way's time, its withdraw mark and a shut way's reason live
there, and a button whose name changed with the scene would move under the pointer.

Kept visible: the text box, Say, Continue, the attached chip, the GM's suggestions (most
turns, and they are offers into the pen itself), the harbourmaster's berths (only while
talking to one, and the conversation is about them), the combat bar (the fight's own
state, outside the pen), and the `?` (the same tips door every panel wears).

Native `popover="auto"` with `popovertarget`: Esc and a click outside close it, the browser
keeps `aria-expanded` on the button, and focus returns to it. Placed by measurement, as the
spell picker is (`placeSpellPicker`), because a LAN browser may lack CSS anchor positioning.
A browser with no popover at all gets the old inline rows.

## Rejected

- **One `+` tray holding everything, ways on included.** The ways on are a set of choices
  in their own right; NN/g's two-level rule and the count on the button argue for their own
  door. Putting them under More would make a move two decisions deep.
- **An icon-only `+`.** NN/g's advice for anything hidden is a label with scent; an icon
  says only "something is here". Text labels.

A critic pass (2026-11-25) checked every source above: it corrected the BG3 patch's date,
two misquoted NN/g phrases, an overclaim about Slack, and the reading of the hamburger
study, and raised the one-item-menu case adopted under Chosen.
- **Hiding the suggestions.** They are used most turns and go straight into the pen; hiding
  them would be Discord's complaint (the common thing behind a menu).
- **Hiding Continue.** The owner's ruling makes it a turn verb, used often.
- **Collapsing the combat bar.** It is the fight, not the pen; a fight's Commit turn and End
  turn must stay in view (tools/table_hit_test.js MUST_SHOW).
- **Ways on as a modal or a side drawer.** A popover over the story's foot keeps the desk's
  height fixed (the owner's motion rule: nothing moves under the pointer) and closes on Esc
  or a click outside; a modal would block reading the scene the choice depends on.
- **Remembering which tray was open across turns.** Nothing asked for it; each turn starts
  clean.

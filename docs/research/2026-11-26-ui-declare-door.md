# Research, lane ui/declare-door (2026-11-26): the combat bar's Declare behind a door

Owner ask A1, 2026-11-26: "put the combat declare section inside a button as well." The
"as well" is the clean-composer change in 0.5.1 (Ways on, More), whose note is
docs/research/2026-11-25-clean-composer.md. That note's sources (NN/g on progressive
disclosure and hidden navigation, Discord's one-item `+` menu, ChatGPT's tools menu, BG3's
decks) are not repeated here; this note adds what is particular to declared options.

## What was there

Measured on a copy of the owner's Shadow save, in the surprise round against the lost
scholar, at 1400x950 on master 3791c3f9 (shots-declare/before-1400x950.jpg):

| | before | after |
|---|---|---|
| combat bar | 446px | 219px |
| Declare block | 219px, open under the actions | one 34px button in the actions row |
| desk's choices box | 283px showing, 490px of content (scrolls) | 263px, nothing to scroll |
| GM's suggestions | below the fold of the box | in view |

Shadow's options: Fight defensively (with the blow, a toggle), Charge, Total defense,
Feint, Pin (as the action, each staging its own action) and Tumble (with the move, a
toggle). Six buttons in three labelled groups, each with its numbers.

## The rule the block serves

PF1e makes these choices before the roll they change: "You can choose to fight
defensively when attacking. If you do so, you take a –4 penalty on all attacks in a
round" (CRB p.182, https://aonprd.com/Rules.aspx?ID=131). Power Attack and Combat Expertise
are worded the same way ("You can choose to take a –1 penalty...", d20pfsrd). So a toggle
is a standing modifier on the turn being built. The consequence for the UI (my inference,
supported only by the BG3 complaints below): a toggle that is on must stay visible,
because it changes every blow staged after it.

## How others show a declared mode

**Neverwinter Nights (2002).** Power Attack, Expertise, Parry and the called shots are
"combat modes": toggles kept in the radial menu under Special Attacks. The fan wiki says a
mode assigned to a quickslot has that slot highlighted while it is active, and that modes
are cancelled by a non-combat action or by leaving combat. Sources: the search result
summaries of https://nwn.fandom.com/wiki/Combat_mode (the page itself answered 402 to a
direct fetch, so I could not read it whole). I could not confirm how the radial itself
shows an active mode.

**Neverwinter Nights 2 (abandoned design).** A 2006 fan-site repost of J.E. Sawyer's
official-forum posts says the radial would go, called slow, cumbersome and "overloaded with
functionality", and that modal actions (stealth, search, Rapid Shot, Power Attack) would sit
on "a modal menu that can be expanded or collapsed" (search summaries of
https://sorcerers.net/community/threads/neverwinter-nights-2-lead-designer-waves-radial-menu-goodbye.37370;
403 to a direct fetch, not Obsidian's own documentation). What is sourced: the modes left a
menu shared with everything else for a collapsible place of their own. That is the shape
chosen here: one door for the declared options only, not a slot in More.

**Baldur's Gate 3.** Great Weapon Master and Sharpshooter are toggleable passives in the
hotbar's passives (bg3.wiki: "a toggleable passive", flagged ToggledDefaultOn), on by
default once learned; guides tell players to turn them off there. https://primagames.com/tips/baldurs-gate-3-how-to-toggle-great-weapon-master-in-bg3,
https://attackofthefanboy.com/guides/how-to-toggle-great-weapon-master-and-sharpshooter-in-baldurs-gate-3/.
One Steam poster could not find how to turn it off
(https://steamcommunity.com/app/1086940/discussions/0/3808408328764918574), another turns
All In off at the start of every battle and asks for default-off
(https://steamcommunity.com/app/1086940/discussions/0/3808408328768492721, search snippet
only): a −5 to hit that is on without being seen is the complaint. Declared options here start off every fight and
the door says when one is on.

**Pathfinder: Wrath of the Righteous (Owlcat).** Abilities, some of which "can be switched
on and off", are placed on the action panel (https://pathfinderwrathoftherighteous.wiki.fextralife.com/Combat).
I could not confirm from the wiki how an active toggle is drawn, or whether Fight
Defensively sits in a group of its own; a 2021 Steam report says it changed AC but the
player could not tell whether it touched her attacks
(https://steamcommunity.com/app/1184370/discussions/0/3044984779768124127, from the search
summary only). Unsourced beyond that.

**ChatGPT's tools menu** (in the clean-composer note): the chosen tool is shown on the bar
once chosen, so the hidden choice stays visible.

## Chosen

- **One labelled door, "Declare", in the combat bar's actions row**, after Free… and before
  Clear, Commit turn and End turn: the builder's verbs, then the modifiers on them, then
  the turn's own buttons. The popover is the clean-composer one (`.penpop`, native
  `popover="auto"`, placed by measurement in 11-exits.js `placePenPop`, the same Esc,
  click-outside and focus-return behaviour). It holds the same three groups, drawn by the
  same `renderOptions`; nothing names an option in the page.
- **The shut door names what is declared**: "Declare · Fight defensively" for one toggle,
  "Declare · 2 on" for more, with the gilt border while any is on and the whole list as its
  title. This is close to NWN's highlighted quickslot (though NWN lights a slot the player
  placed, not a summary on a door) and ChatGPT's chosen-tool label. An option that
  stages its own action (Charge, Feint, Pin) is not named on the door: it shows in the plan
  above the actions as every staged action does.
- **A toggle keeps the popover open; an action folds it.** A player may declare two toggles
  in a row; an option that stages an action is a decision made, so the popover closes and the
  plan and Commit turn are in view, focus back on the door. The option pressed keeps focus
  across the redraw, so a keyboard player is not dropped to the page.
- **Opens above its whole row, not its door.** The actions wrap; above a door on the second
  line the popover covered Strike and Full attack (tools/table_hit_test.js at 1024x700).
- **No popover in the browser (Safari before 17 on the LAN):** the door goes and the band
  stands inline under the actions row with its gilt rule, as it did before.

## Rejected

- **Declare inside More.** More is the pen's, out of a fight; the declared options are the
  fight's. Two decisions deep for a −4 that rides every blow (NN/g's two-level rule, in the
  clean-composer note).
- **Each group its own door (blow, action, move).** Three doors for six options rebuilds the
  crowding the owner asked to remove.
- **Only a count on the door ("Declare (1)").** It says something is on, not what; the
  player has to open the door to learn whether that −4 is riding. Kept as the fallback for
  two or more, where names would not fit the row.
- **Moving the popover when the door's label grows.** The door widens when a toggle is
  named; re-placing the open popover would move it under the pointer that just pressed (the
  owner's motion rule). It is placed once, as it opens.
- **A chip for each toggle in the plan row.** The plan lists staged actions in the order
  Commit posts them; a toggle is not a step and has no order. The staged blow already
  carries the toggle in its label ("Strike the lost scholar (Fight defensively)").

## The hit test

tools/table_hit_test.js gained two things, both found while checking this:
- an open popover is in the top layer, so the boxes it sits in no longer clip it (its
  options sat inside the desk's 283px scroll box and would have counted as off screen);
- a control under an open popover the player opened is counted in `underPopover`, on the
  card's rules (never MUST_SHOW, never the focused element). Before this, 0.5.1's own Ways
  on, open at 1024x700, listed Strike, Full attack and Ability as "covered".

Results, in the fight, Declare shut / open / open with Fight defensively on / shut with it
on: 1400x950 clean in all four (open: 6 options checked, 0 covered); 1024x700 and 800x600
clean in all four (open: 2 and 3 controls under the popover, none of them MUST_SHOW).

A critic pass (2026-11-26) re-checked every source: it confirmed the CRB, d20pfsrd and NWN
claims (NWN from search summaries only), sourced the NWN2 designer's reason, swapped a
Steam thread that did not say what the note claimed, narrowed the WotR and BG3 wording,
and asked that the visibility rule be labelled an inference.

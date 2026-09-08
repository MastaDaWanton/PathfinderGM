# Quests, and the outfitting step

Built 2026-09-07 from one message: "is there a way we could have quest cards and track
active quests along with having a quest log" and "at the end of making your character
we need a buy screen to spend starting gold, this needs to happen before you start in
the sandbox."

## Quests

**What the traditions do.** Baldur's Gate 3's journal keeps two things apart: *objectives*
say what to do next, *steps* say what just happened, and only one objective is active
at a time ([journal structure](https://docs.baldursgate3.game/index.php?title=Journal_Structure_Overview),
[design guidelines](https://docs.baldursgate3.game/index.php?title=Journal_Design_Guidelines)).
The Elder Scrolls' quest stages taught that stages are not always in order and not all
are reached — a quest with two ways through skips some
([UESP](https://en.uesp.net/wiki/UESPWiki:Style_Guide/Quest_Layout)). Both auto-update
the journal from play rather than asking the player to write it.

**What this is.** A quest is a situation card (`docs/situation-cards.md`) of kind
`quest`, tagged `situation.quest`, with `objectives` (each `{text, done}`), a `giver`
(an actor ref, or a name the world knows) and a `reward` in words. It is a card so the
watcher, the brief and the story award work on it unchanged; the card's *facts* are the
steps, its *objectives* are what to do next, and its clock is the count of objectives
done. Always on: the brief shows it whenever it is live, objectives first, unticked
ones as `[ ]`, then "promised: …", then the facts.

**Doors.** The GM proposes `quest` when somebody gives the party a task and the player
takes it — title, objectives (one to six sentences), giver, reward. The engine refuses
a number anywhere on it (the engine prices rewards, never the model), a giver who is
nobody on the board, and a repeated title. `quest_step` ticks one objective by number
with a note; the watcher may propose the same tick when it sees an objective plainly
done on stage. The last objective done resolves the quest and pays the story award for
seeing a matter through — the one place a model's word moves experience, and only
through the engine's own award.

**The log.** The table page's character sheet has a Quests tab: underway first, with
the giver, the objectives (done ones struck through), the promise and the steps; then
finished. It is read off `/api/state`'s `quests`, which is `cards.quest_log(scene)`.

## Outfitting

The Core Rulebook's step between the sheet and the road. The forge rolls the class's
starting wealth into the purse (`creation.starting_purse`) and used to hand the
character straight to the sandbox with it unspent. Now "Create & play" lands on
`/outfit/` first: the weapon table at its printed prices (`cost_gp` from the weapons
content), armour and shields at the Core Rulebook's (`cost_gp` on the tables), and an
adventuring-gear list (`goods.GEAR`). A basket is bought all or nothing, with the
shortfall named; bought armour is worn and the old suit goes to the pack; gear lands in
`stock` the way anything the engine sells does. "Begin the sandbox" is the same door
"Play as X" uses. The class kit is still free, as it was.

Also fixed on the way: a new character began at the die plus Con while the loader added
Toughness to the maximum afterwards — 40 of 44 on the first day. The forge sets hit
points to the maximum once the sheet has loaded.
